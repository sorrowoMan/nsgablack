from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd

from nsgablack.core.base import BlackBoxProblem
from blackbase.resources import ResourceRequirement

from inner_solver import InnerProductionSolverConfig


@dataclass(frozen=True)
class SupplyEvent:
    material_idx: int
    day: int
    quantity: float


class SupplyEventShiftProblem(BlackBoxProblem):
    """Outer problem: shift whole supply events earlier to improve production metrics.

    Rules:
    - day0 is today: its inventory is fixed, with no inbound or outbound moves
    - day1 events retain their positions in the candidate vector but cannot move
    - each event can only move earlier, never later
    - each move is whole-event (no split)
    """

    context_requires = ()
    cap_projection_policy = "supply_event_cap/sha256-index-v1"
    context_provides = ("inner_metrics",)
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Optimize event-level early shifts on supply table with inner production evaluation.",
    )

    def __init__(
        self,
        *,
        base_supply: np.ndarray,
        bom_matrix: np.ndarray,
        production_case_dir: Path,
        inner_solver_cfg: InnerProductionSolverConfig | None = None,
        material_ids: np.ndarray | None = None,
        material_blacklist: np.ndarray | list[int] | set[int] | None = None,
        max_moved_events: int | None = None,
        outer_task_requirement: ResourceRequirement | dict | None = None,
        inner_resource_requirement: ResourceRequirement | dict | None = None,
    ) -> None:
        self.base_supply = np.asarray(base_supply, dtype=float)
        if self.base_supply.ndim != 2:
            raise ValueError("base_supply must be 2D (materials, days)")

        self.materials, self.days = self.base_supply.shape
        self.bom_matrix = np.asarray(bom_matrix, dtype=float)
        self.production_case_dir = Path(production_case_dir).resolve()
        self.inner_solver_cfg = inner_solver_cfg or InnerProductionSolverConfig()
        self.outer_task_requirement = _coerce_requirement(
            outer_task_requirement,
            fallback=ResourceRequirement(
                threads=1,
                capabilities=("nested_eval",),
                metadata={"layer": "L1", "source": "supply_adjustment_nested.outer_task"},
            ),
        )
        self.outer_resource_requirement = self.outer_task_requirement
        self.inner_resource_requirement = _coerce_requirement(
            inner_resource_requirement,
            fallback=self.inner_solver_cfg.effective_resource_requirement(),
        )
        self.max_moved_events = (
            None
            if max_moved_events is None or int(max_moved_events) <= 0
            else int(max_moved_events)
        )
        self.material_ids = (
            np.asarray(material_ids)
            if material_ids is not None and len(material_ids) == self.materials
            else np.arange(1, self.materials + 1)
        )
        if material_blacklist is None:
            self.material_blacklist = np.zeros(self.materials, dtype=bool)
        else:
            if isinstance(material_blacklist, np.ndarray) and material_blacklist.dtype == bool:
                if material_blacklist.size != self.materials:
                    raise ValueError("material_blacklist bool mask size mismatch")
                self.material_blacklist = np.array(material_blacklist, copy=True)
            else:
                ids = np.zeros(self.materials, dtype=bool)
                for item in material_blacklist:
                    mid = int(item)
                    if 1 <= mid <= self.materials:
                        ids[mid - 1] = True
                    elif 0 <= mid < self.materials:
                        ids[mid] = True
                self.material_blacklist = ids

        self.events: List[SupplyEvent] = []
        bounds = {}
        idx = 0
        for m in range(self.materials):
            if self.material_blacklist[m]:
                continue
            for d in range(1, self.days):
                qty = float(self.base_supply[m, d])
                if qty <= 0.0:
                    continue
                self.events.append(SupplyEvent(material_idx=m, day=d, quantity=qty))
                # Keep every original event position, including zero-width day1
                # variables, so tightening today's boundary does not renumber events.
                bounds[f"x{idx}"] = [0, d - 1]
                idx += 1

        super().__init__(
            name="SupplyEventShiftProblem",
            dimension=len(self.events),
            bounds=bounds,
            objectives=["maximize_output", "min_moved_events", "min_moved_days"],
        )

    def decode_shifts(self, x: np.ndarray) -> np.ndarray:
        arr = np.asarray(x, dtype=float).reshape(self.dimension)
        if arr.size == 0:
            return np.zeros(0, dtype=int)
        if not np.all(np.isfinite(arr)):
            raise ValueError("supply shift candidate must contain finite values")
        rounded = np.rint(arr)
        for i, ev in enumerate(self.events):
            rounded[i] = np.clip(rounded[i], 0, ev.day - 1)
        shifts = rounded.astype(int)
        # Hard cap moved event count at decode stage so export/runtime always respects it,
        # even when the outer solver temporarily keeps infeasible candidates.
        if self.max_moved_events is not None and self.max_moved_events >= 0:
            moved_idx = np.flatnonzero(shifts > 0)
            k = int(self.max_moved_events)
            if moved_idx.size > k:
                # A cardinality repair must not decide that short, long or
                # large-quantity moves are better. Use a versioned pure hash
                # projection, with no mutable or process-global RNG state.
                canonical = np.asarray(shifts, dtype="<i8").tobytes()
                salt = hashlib.sha256(
                    self.cap_projection_policy.encode("ascii") + b"\0"
                    + k.to_bytes(8, "little") + canonical
                ).digest()

                def projection_key(index):
                    event = self.events[int(index)]
                    identity = np.asarray(
                        [int(index), event.material_idx, event.day], dtype="<i8"
                    ).tobytes()
                    return hashlib.sha256(salt + identity).digest()

                keep_idx = set(int(i) for i in sorted(moved_idx, key=projection_key)[:k])
                for i in moved_idx:
                    if int(i) not in keep_idx:
                        shifts[int(i)] = 0
        return shifts

    def apply_shifts(self, shifts: np.ndarray) -> np.ndarray:
        shifts = self._validated_shifts(shifts)
        out = np.asarray(self.base_supply, dtype=float).copy()
        for i, ev in enumerate(self.events):
            shift = int(shifts[i])
            if shift <= 0:
                continue
            src_day = int(ev.day)
            dst_day = int(src_day - shift)
            qty = float(ev.quantity)
            out[ev.material_idx, src_day] -= qty
            out[ev.material_idx, dst_day] += qty
        return out

    def _validated_shifts(self, shifts: np.ndarray) -> np.ndarray:
        """Validate an already decoded move vector before applying or exporting it."""
        values = np.asarray(shifts, dtype=float)
        if values.shape != (self.dimension,):
            raise ValueError(f"decoded supply shifts must have shape ({self.dimension},)")
        if not np.all(np.isfinite(values)) or not np.array_equal(values, np.rint(values)):
            raise ValueError("decoded supply shifts must contain finite integers")
        for i, ev in enumerate(self.events):
            if not 0 <= values[i] <= ev.day - 1:
                raise ValueError(
                    f"supply event {i} shift must be in [0, {ev.day - 1}]; "
                    "day0 is today and cannot receive or release supply"
                )
        return values.astype(int)

    def evaluate(self, candidate: np.ndarray) -> np.ndarray:
        raise RuntimeError(
            "SupplyEventShiftProblem requires its formal production_inner Case evaluator; "
            "supply totals are not a production-output proxy"
        )

    def evaluate_constraints(self, candidate: np.ndarray) -> np.ndarray:
        # Shift rules are enforced by decode_shifts/apply_shifts.
        # Optional hard cap: moved events must be <= max_moved_events.
        if self.max_moved_events is None:
            return np.zeros(0, dtype=float)
        shifts = self.decode_shifts(candidate)
        moved_events = int(np.count_nonzero(shifts > 0))
        return np.array([float(moved_events - self.max_moved_events)], dtype=float)

    def export_adjusted_supply(self, x: np.ndarray, path: Path) -> Tuple[np.ndarray, pd.DataFrame]:
        shifts = self.decode_shifts(x)
        adjusted = self.apply_shifts(shifts)

        cols = {"material": self.material_ids.tolist()}
        for d in range(self.days):
            cols[str(d)] = adjusted[:, d].astype(float).tolist()
        df = pd.DataFrame(cols)

        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() == ".xlsx":
            df.to_excel(path, index=False, sheet_name="adjusted_supply")
        else:
            df.to_csv(path, index=False)
        return shifts, df

    def export_move_log(self, shifts: np.ndarray, path: Path) -> pd.DataFrame:
        shifts = self._validated_shifts(shifts)
        rows = []
        for i, ev in enumerate(self.events):
            s = int(shifts[i])
            if s <= 0:
                continue
            rows.append(
                {
                    "event_idx": i,
                    "material": int(self.material_ids[ev.material_idx]),
                    "quantity": float(ev.quantity),
                    "from_day": int(ev.day),
                    "to_day": int(ev.day - s),
                    "moved_days": s,
                    "quantity_days": float(ev.quantity) * float(s),
                }
            )
        df = pd.DataFrame(rows)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() == ".xlsx":
            df.to_excel(path, index=False, sheet_name="move_log")
        else:
            df.to_csv(path, index=False)
        return df


def _coerce_requirement(value: ResourceRequirement | dict | None, *, fallback: ResourceRequirement) -> ResourceRequirement:
    if isinstance(value, ResourceRequirement):
        return value
    if isinstance(value, dict):
        return ResourceRequirement.from_dict(value)
    return fallback
