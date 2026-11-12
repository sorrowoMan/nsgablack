"""
NSGA-III with hyperplane normalization and reference-direction niching.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np

from ..unit_backed import UnitField
from ...representation.structure_builders import ReferencePopulationBuilder

from ..nsga2 import NSGA2Adapter, NSGA2Config
from nsgablack.context_keys import KEY_MO_WEIGHTS


@dataclass
class NSGA3Config(NSGA2Config):
    divisions: int = 6


class NSGA3Adapter(NSGA2Adapter):
    unit_build_operations = ("initialize", "reference_directions")
    unit_builder_type = ReferencePopulationBuilder
    unit_schema = ReferencePopulationBuilder.unit_type.schema
    reference_points = UnitField("reference_points")
    normalization = UnitField("normalization")

    context_requires = ()
    context_provides = NSGA2Adapter.context_provides + (KEY_MO_WEIGHTS,)
    context_mutates = ()
    context_cache = ()
    context_notes = "NSGA-III with persistent ideal/extreme points, hyperplane normalization and perpendicular reference-line niching."
    state_recovery_level = "L2"
    state_recovery_notes = (
        "Inherits NSGA-II population snapshot roundtrip "
        "(get_state/set_state + get_population_snapshot/set_population_snapshot). "
        "Reference directions and hyperplane normalization history are restored through the Unit v2 codec; v1 checkpoints require explicit migration."
    )

    def __init__(
        self,
        config: Optional[NSGA3Config] = None,
        name: str = "nsga3",
        priority: int = 0,
        *,
        initializer=None,
        parent_selector=None,
        mutator=None,
        change=None,
        selector=None,
        pool_maintenance=None,
        repair=None,
        **config_kwargs,
    ) -> None:
        unit_binding = config_kwargs.pop("unit_binding", None)
        resolved = self.resolve_config(
            config=config,
            config_cls=NSGA3Config,
            config_kwargs=config_kwargs,
            adapter_name="NSGA3Adapter",
        )
        super().__init__(config=resolved, name=name, priority=priority, unit_binding=unit_binding,
                         initializer=initializer, parent_selector=parent_selector, mutator=mutator,
                         selector=selector, repair=repair, change=change, pool_maintenance=pool_maintenance)
        self.config = self.cfg
        self.cfg: NSGA3Config = resolved
        self.reference_points: np.ndarray = np.zeros((0, 0), dtype=float)

    def setup(self, control: Any) -> None:
        super().setup(control)

    def _ensure_population(self, control, context):
        # Initial candidates must be evaluated before any CV-based mating.
        # Preserve the original proposal objects and their provenance instead
        # of taking unbound array views out of an unevaluated Unit.
        if self.population is None or not len(self.population):
            return [self.init_candidate(control, context) for _ in range(max(2, int(self.cfg.population_size)))]
        return None

    def _tournament_pick(self):
        n = len(self.population)
        a, b = self._rng.integers(0, n, size=2)
        va, vb = self.violations[a], self.violations[b]
        if (va > 0 or vb > 0) and va != vb:
            return int(a if va < vb else b)
        return int(self._rng.choice((a, b)))

    def propose(self, control: Any, context: Dict[str, Any]):
        if not self.reference_points.size:
            problem = getattr(control, "problem", None)
            counter = getattr(problem, "get_num_objectives", None)
            n_obj = int(counter() if callable(counter) else getattr(problem, "num_objectives", 2))
            self._generate_reference_points(n_obj, max(1, int(self.cfg.divisions)))
        return super().propose(control, context)

    def _environmental_select(self, objectives: np.ndarray, violations: np.ndarray, n_keep: int) -> np.ndarray:
        from .normalization import update_normalization, associate, niche_select
        from ...utils.performance.fast_non_dominated_sort import FEASIBILITY_THRESHOLD
        feasible = np.flatnonzero(np.asarray(violations) <= FEASIBILITY_THRESHOLD)
        infeasible = np.flatnonzero(np.asarray(violations) > FEASIBILITY_THRESHOLD)
        infeasible = infeasible[np.argsort(np.asarray(violations)[infeasible], kind="stable")]
        if not len(feasible):
            return infeasible[:n_keep]
        f = np.asarray(objectives)[feasible]
        fronts, _ = self._sort_fronts(f, np.zeros(len(f)))
        self.normalization = update_normalization(self.normalization, f, fronts[0])
        if self.reference_points.size == 0 or self.reference_points.shape[1] != f.shape[1]:
            self._generate_reference_points(f.shape[1], max(1, int(self.cfg.divisions)))
        keep: List[int] = []
        for front in fronts:
            if len(keep) + len(front) <= n_keep:
                keep.extend(list(front))
                continue

            remain = max(0, n_keep - len(keep))
            if remain <= 0:
                break
            considered = np.asarray(keep + list(front), dtype=int)
            assignment, distances = associate(f[considered], self.reference_points, self.normalization)
            counts = np.bincount(assignment[:len(keep)], minlength=len(self.reference_points))
            selected = niche_select(np.asarray(front), remain, counts, assignment[len(keep):], distances[len(keep):], self._rng)
            keep.extend(selected.tolist())
            break
        selected = feasible[np.asarray(keep, dtype=int)]
        return np.concatenate((selected, infeasible[:max(0, n_keep-len(selected))]))

    def update(self, control, candidates, feedback, context):
        super().update(control, candidates, feedback, context)
        if not self.normalization and self.objectives is not None and len(self.objectives):
            from ...utils.performance.fast_non_dominated_sort import FEASIBILITY_THRESHOLD
            from .normalization import update_normalization
            feasible = np.flatnonzero(np.asarray(self.violations) <= FEASIBILITY_THRESHOLD)
            if len(feasible):
                f = self.objectives[feasible]
                fronts, _ = self._sort_fronts(f, np.zeros(len(f)))
                self.normalization = update_normalization({}, f, fronts[0])

    def _sort_fronts(self, objectives: np.ndarray, violations: np.ndarray):
        from ...utils.performance.fast_non_dominated_sort import fast_non_dominated_sort_optimized

        fronts, rank = fast_non_dominated_sort_optimized(objectives, violations)
        # Stable row order within an unordered front makes randomized niching
        # independent of the dominance graph traversal order.
        return [sorted(front) for front in fronts], rank

    def _generate_reference_points(self, n_obj: int, divisions: int) -> np.ndarray:
        self.rebuild_unit("reference_directions", objectives=n_obj, divisions=divisions)
        return self.ensure_unit().reference_points

    def _sync_runtime_projection(self) -> None:
        super()._sync_runtime_projection()
        if self.reference_points.size > 0:
            self._runtime_projection[KEY_MO_WEIGHTS] = self.reference_points.copy()
