"""
Pareto archive plugin with objective-space segmenting.

Each entry carries an objective-label signature derived from the problem's
objective names.  Entries with the same label set form a *segment*.
Dominance comparison only happens within a segment; cross-segment entries
are never compared.

When the objective space changes (labels added / removed) the old segment
is frozen for history and a new one is created.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..base import Plugin


def _label_key(labels: Sequence[str]) -> str:
    return ",".join(str(l).strip().lower() for l in labels)


@dataclass
class ParetoArchiveConfig:
    keep_infeasible: bool = False
    max_size: Optional[int] = None          # per-segment, when None unlimited
    update_every: int = 1
    freeze_on_label_change: bool = True     # keep old segments when objective space changes
    max_frozen_segments: int = 8            # cap on retained frozen segments
    label_source: str = "objective_names"   # solver attr / context key to read labels from


@dataclass
class _Segment:
    label_key: str
    labels: Tuple[str, ...]
    generation_first: int
    generation_last: Optional[int] = None   # None = still active
    X: Optional[np.ndarray] = None
    F: Optional[np.ndarray] = None
    V: Optional[np.ndarray] = None

    @property
    def active(self) -> bool:
        return self.generation_last is None

    def count(self) -> int:
        return 0 if self.F is None else int(self.F.shape[0])


class ParetoArchivePlugin(Plugin):
    is_algorithmic = True
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Reads solver population/objectives/violations or adapter population; "
        "updates runtime pareto snapshot (pareto_solutions/pareto_objectives). "
        "Objective-space labelling creates isolated segments; dominance is "
        "only compared within a segment."
    )

    provides_metrics = {"pareto_archive_size", "pareto_segment_count"}

    def __init__(
        self,
        name: str = "pareto_archive",
        *,
        config: Optional[ParetoArchiveConfig] = None,
    ) -> None:
        super().__init__(name=name)
        self.cfg = config or ParetoArchiveConfig()
        self._segments: Dict[str, _Segment] = {}
        self._last_update_generation: Optional[int] = None

    # ---- public helpers --------------------------------------------------

    @property
    def active_segment(self) -> Optional[_Segment]:
        for seg in self._segments.values():
            if seg.active:
                return seg
        return None

    @property
    def segment_count(self) -> int:
        return len(self._segments)

    def total_archive_size(self) -> int:
        return sum(seg.count() for seg in self._segments.values())

    # ---- Plugin hooks ----------------------------------------------------

    def on_generation_end(self, generation: int):
        if not self._should_update(int(generation)):
            return None
        self._update_from_solver(generation=int(generation))
        return None

    def on_solver_finish(self, _result):
        solver = self.solver
        if solver is None:
            return None
        final_generation = max(0, int(getattr(solver, "generation", 0) or 0) - 1)
        if self._last_update_generation == final_generation:
            self._write_pareto_snapshot(solver)
            return None
        self._update_from_solver(generation=final_generation)
        return None

    # ---- internal update -------------------------------------------------

    def _should_update(self, generation: int) -> bool:
        update_every = max(1, int(getattr(self.cfg, "update_every", 1) or 1))
        return int(generation) == 0 or (int(generation) % update_every) == 0

    def _update_from_solver(self, *, generation: int) -> None:
        solver = self.solver
        if solver is None:
            return

        X, F, V = self._get_population(solver)
        if X.size == 0:
            return

        labels = self._read_objective_labels(solver)
        lk = _label_key(labels)

        # ---- segment housekeeping -----------------------------------------
        active = self.active_segment
        if active is not None and active.label_key != lk:
            # objective space changed — freeze the old segment
            if self.cfg.freeze_on_label_change:
                active.generation_last = generation - 1
            else:
                self._segments.pop(active.label_key, None)
            active = None

        if active is None:
            # check if a frozen segment matches the new label key
            existing = self._segments.get(lk)
            if existing is not None and not existing.active:
                # re-activate — archive continues to accumulate
                existing.generation_last = None
                active = existing
            else:
                active = _Segment(
                    label_key=lk,
                    labels=tuple(labels),
                    generation_first=int(generation),
                )
                self._segments[lk] = active

        # ---- append new population ----------------------------------------
        if active.F is None:
            active.X = np.asarray(X, dtype=float)
            active.F = np.asarray(F, dtype=float)
            active.V = np.asarray(V, dtype=float).reshape(-1)
        else:
            active.X = np.vstack([active.X, np.asarray(X, dtype=float)])
            active.F = np.vstack([active.F, np.asarray(F, dtype=float)])
            active.V = np.concatenate([active.V, np.asarray(V, dtype=float).reshape(-1)])

        # ---- filter infeasible --------------------------------------------
        if not self.cfg.keep_infeasible and active.V is not None:
            feas = (active.V <= 0.0)
            active.X = active.X[feas]
            active.F = active.F[feas]
            active.V = active.V[feas]

        if active.F is None or active.F.size == 0:
            return

        # ---- non-dominated filter (within segment) ------------------------
        nd = self._nondominated_mask(active.F)
        active.X = active.X[nd]
        active.F = active.F[nd]
        active.V = active.V[nd]

        # ---- truncate per-segment -----------------------------------------
        max_size = self.cfg.max_size
        if max_size is not None and active.F.shape[0] > int(max_size):
            k = int(max_size)
            idx = self._select_by_crowding(active.F, k)
            active.X = active.X[idx]
            active.F = active.F[idx]
            active.V = active.V[idx]

        # ---- cap frozen segments ------------------------------------------
        self._trim_frozen_segments()

        self._write_pareto_snapshot(solver)
        self._last_update_generation = int(generation)

    # ---- objective label resolution ---------------------------------------

    def _read_objective_labels(self, solver: Any) -> List[str]:
        source = str(getattr(self.cfg, "label_source", "objective_names") or "objective_names")
        # 1) explicit attribute
        if hasattr(solver, source):
            value = getattr(solver, source, None)
            if isinstance(value, (list, tuple)):
                return [str(x) for x in value]
            if isinstance(value, str):
                return [value]

        # 2) from problem
        problem = getattr(solver, "problem", None)
        if problem is not None:
            for attr in ("objective_names", "objective_labels", "obj_names"):
                value = getattr(problem, attr, None)
                if isinstance(value, (list, tuple)):
                    return [str(x) for x in value]

        # 3) from adapter population dimension
        adapter = getattr(solver, "adapter", None)
        pop = getattr(adapter, "population", None)
        if pop is not None:
            try:
                dim = int(pop.shape[1])
                return [f"obj_{i}" for i in range(dim)]
            except Exception:
                pass

        # 4) last resort — use dimension of current F
        population = self._get_population(solver)
        if population[1].size > 0:
            dim = int(population[1].shape[1])
            return [f"obj_{i}" for i in range(dim)]

        return ["obj_0"]

    # ---- frozen segment housekeeping --------------------------------------

    def _trim_frozen_segments(self) -> None:
        max_frozen = max(0, int(getattr(self.cfg, "max_frozen_segments", 8) or 8))
        frozen = sorted(
            [s for s in self._segments.values() if not s.active],
            key=lambda s: (s.generation_last or 0),
        )
        while len(frozen) > max_frozen:
            oldest = frozen.pop(0)
            self._segments.pop(oldest.label_key, None)

    # ---- solver I/O -------------------------------------------------------

    def _get_population(self, solver: Any) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        return self.get_population_snapshot(solver)

    def _write_pareto_snapshot(self, solver: Any) -> None:
        setter = getattr(solver, "set_pareto_snapshot", None)
        if callable(setter):
            try:
                active = self.active_segment
                X = None if active is None else active.X
                F = None if active is None else active.F
                setter(X, F)
                return
            except Exception:
                return

        # fallback: write via solver write_snapshot (preferred) or log
        active = self.active_segment
        writer = getattr(solver, "write_snapshot", None)
        if callable(writer):
            try:
                writer(
                    pareto_solutions=None if active is None else np.asarray(active.X),
                    pareto_objectives=None if active is None else np.asarray(active.F),
                )
            except Exception:
                pass
        elif not callable(getattr(solver, "set_pareto_snapshot", None)):
            import warnings
            warnings.warn(
                "ParetoArchive._write_pareto_snapshot: solver has neither set_pareto_snapshot nor write_snapshot. "
                "Skipping pareto write."
            )
        try:
            segments_meta = [
                {
                    "label_key": seg.label_key,
                    "labels": list(seg.labels),
                    "active": seg.active,
                    "generation_first": seg.generation_first,
                    "generation_last": seg.generation_last,
                    "count": seg.count(),
                }
                for seg in self._segments.values()
            ]
            setattr(solver, "pareto_segments", segments_meta)
        except Exception:
            pass

    # ---- backward-compat: direct array-level update (no solver context) ----

    def _update_archive(self, X: np.ndarray, F: np.ndarray, V: np.ndarray) -> None:
        """Direct update without solver context — auto-labels from F dimension."""
        m = int(F.shape[1])
        labels = [f"obj_{i}" for i in range(m)]
        lk = _label_key(labels)
        active = self._segments.get(lk)
        if active is None:
            active = _Segment(label_key=lk, labels=tuple(labels), generation_first=0)
            self._segments[lk] = active
        if active.F is None:
            active.X = np.asarray(X, dtype=float)
            active.F = np.asarray(F, dtype=float)
            active.V = np.asarray(V, dtype=float).reshape(-1)
        else:
            active.X = np.vstack([active.X, np.asarray(X, dtype=float)])
            active.F = np.vstack([active.F, np.asarray(F, dtype=float)])
            active.V = np.concatenate([active.V, np.asarray(V, dtype=float).reshape(-1)])
        if not self.cfg.keep_infeasible:
            feas = (active.V <= 0.0)
            active.X = active.X[feas]
            active.F = active.F[feas]
            active.V = active.V[feas]
        if active.F.size == 0:
            return
        nd = self._nondominated_mask(active.F)
        active.X = active.X[nd]
        active.F = active.F[nd]
        active.V = active.V[nd]
        max_size = self.cfg.max_size
        if max_size is not None and active.F.shape[0] > int(max_size):
            k = int(max_size)
            idx = self._select_by_crowding(active.F, k)
            active.X = active.X[idx]
            active.F = active.F[idx]
            active.V = active.V[idx]

    @property
    def archive_X(self) -> Optional[np.ndarray]:
        seg = self.active_segment
        return None if seg is None else seg.X

    @archive_X.setter
    def archive_X(self, value: Optional[np.ndarray]) -> None:
        seg = self.active_segment
        if seg is not None:
            seg.X = value

    @property
    def archive_F(self) -> Optional[np.ndarray]:
        seg = self.active_segment
        return None if seg is None else seg.F

    @archive_F.setter
    def archive_F(self, value: Optional[np.ndarray]) -> None:
        seg = self.active_segment
        if seg is not None:
            seg.F = value

    @property
    def archive_V(self) -> Optional[np.ndarray]:
        seg = self.active_segment
        return None if seg is None else seg.V

    @archive_V.setter
    def archive_V(self, value: Optional[np.ndarray]) -> None:
        seg = self.active_segment
        if seg is not None:
            seg.V = value

    # ---- dominance / crowding ---------------------------------------------

    @staticmethod
    def _nondominated_mask(F: np.ndarray) -> np.ndarray:
        F = np.asarray(F, dtype=float)
        n = int(F.shape[0])
        dominated = np.zeros(n, dtype=bool)
        for i in range(n):
            if dominated[i]:
                continue
            fi = F[i]
            for j in range(n):
                if i == j or dominated[i]:
                    continue
                fj = F[j]
                if np.all(fj <= fi) and np.any(fj < fi):
                    dominated[i] = True
        return ~dominated

    @staticmethod
    def _select_by_crowding(F: np.ndarray, k: int) -> np.ndarray:
        F = np.asarray(F, dtype=float)
        n = int(F.shape[0])
        if k >= n:
            return np.arange(n, dtype=int)
        if n == 0:
            return np.array([], dtype=int)
        if F.ndim == 1:
            F = F.reshape(-1, 1)

        m = int(F.shape[1])
        crowd = np.zeros(n, dtype=float)
        for obj in range(m):
            order = np.argsort(F[:, obj])
            crowd[order[0]] = np.inf
            crowd[order[-1]] = np.inf
            fmin = float(F[order[0], obj])
            fmax = float(F[order[-1], obj])
            denom = fmax - fmin
            if denom <= 1e-12:
                continue
            for i in range(1, n - 1):
                prev_v = float(F[order[i - 1], obj])
                next_v = float(F[order[i + 1], obj])
                crowd[order[i]] += (next_v - prev_v) / denom

        selected = np.argsort(-crowd)[:k]
        return np.sort(selected.astype(int))
