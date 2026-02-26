from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd

from nsgablack.core.base import BlackBoxProblem

from evaluation.production_inner_eval import ProductionInnerEvaluationModel


@dataclass(frozen=True)
class SupplyEvent:
    material_idx: int
    day: int
    quantity: float


class SupplyEventShiftProblem(BlackBoxProblem):
    """Outer problem: shift whole supply events earlier to improve production metrics.

    Rules:
    - day0 events are fixed (not adjustable)
    - each event can only move earlier, never later
    - each move is whole-event (no split)
    """

    context_requires = ()
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
        inner_model: ProductionInnerEvaluationModel,
        material_ids: np.ndarray | None = None,
        material_blacklist: np.ndarray | list[int] | set[int] | None = None,
        max_moved_events: int | None = None,
    ) -> None:
        self.base_supply = np.asarray(base_supply, dtype=float)
        if self.base_supply.ndim != 2:
            raise ValueError("base_supply must be 2D (materials, days)")

        self.materials, self.days = self.base_supply.shape
        self.inner_model = inner_model
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
                bounds[f"x{idx}"] = [0, d]
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
        shifts = np.rint(arr).astype(int)
        for i, ev in enumerate(self.events):
            if shifts[i] < 0:
                shifts[i] = 0
            if shifts[i] > ev.day:
                shifts[i] = ev.day
        # Hard cap moved event count at decode stage so export/runtime always respects it,
        # even when the outer solver temporarily keeps infeasible candidates.
        if self.max_moved_events is not None and self.max_moved_events >= 0:
            moved_idx = np.flatnonzero(shifts > 0)
            k = int(self.max_moved_events)
            if moved_idx.size > k:
                # Keep the most impactful shifts (larger moved quantity * moved days).
                score = np.array(
                    [float(self.events[i].quantity) * float(shifts[i]) for i in moved_idx],
                    dtype=float,
                )
                keep_local = np.argsort(-score)[:k]
                keep_idx = set(int(moved_idx[i]) for i in keep_local)
                for i in moved_idx:
                    if int(i) not in keep_idx:
                        shifts[int(i)] = 0
        return shifts

    def apply_shifts(self, shifts: np.ndarray) -> np.ndarray:
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

    def evaluate(self, x: np.ndarray) -> np.ndarray:
        shifts = self.decode_shifts(x)
        adjusted = self.apply_shifts(shifts)
        metrics = self.inner_model.evaluate_adjusted_supply(adjusted)

        moved_events = int(np.count_nonzero(shifts > 0))
        moved_days = int(np.sum(shifts))
        total_output = float(metrics["total_output"])

        return np.array([-total_output, float(moved_events), float(moved_days)], dtype=float)

    def evaluate_constraints(self, x: np.ndarray) -> np.ndarray:
        # Shift rules are enforced by decode_shifts/apply_shifts.
        # Optional hard cap: moved events must be <= max_moved_events.
        if self.max_moved_events is None:
            return np.zeros(0, dtype=float)
        shifts = self.decode_shifts(x)
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
                }
            )
        df = pd.DataFrame(rows)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() == ".xlsx":
            df.to_excel(path, index=False, sheet_name="move_log")
        else:
            df.to_csv(path, index=False)
        return df
