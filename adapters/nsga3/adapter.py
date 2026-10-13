"""
NSGA-III style adapter.
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

    context_requires = ()
    context_provides = NSGA2Adapter.context_provides + (KEY_MO_WEIGHTS,)
    context_mutates = ()
    context_cache = ()
    context_notes = "NSGA-III style adapter with reference-point niching in environmental selection."
    state_recovery_level = "L2"
    state_recovery_notes = (
        "Inherits NSGA-II population snapshot roundtrip "
        "(get_state/set_state + get_population_snapshot/set_population_snapshot). "
        "Reference directions are restored through the configured Unit codec."
    )

    def __init__(
        self,
        config: Optional[NSGA3Config] = None,
        name: str = "nsga3",
        priority: int = 0,
        **config_kwargs,
    ) -> None:
        unit_binding = config_kwargs.pop("unit_binding", None)
        resolved = self.resolve_config(
            config=config,
            config_cls=NSGA3Config,
            config_kwargs=config_kwargs,
            adapter_name="NSGA3Adapter",
        )
        super().__init__(config=resolved, name=name, priority=priority, unit_binding=unit_binding)
        self.config = self.cfg
        self.cfg: NSGA3Config = resolved
        self.reference_points: np.ndarray = np.zeros((0, 0), dtype=float)

    def setup(self, control: Any) -> None:
        super().setup(control)
        problem = getattr(control, "problem", None)
        counter = getattr(problem, "get_num_objectives", None)
        n_obj = int(counter() if callable(counter) else getattr(problem, "num_objectives", 2))
        self.reference_points = self._generate_reference_points(n_obj, max(1, int(self.cfg.divisions)))

    def _environmental_select(self, objectives: np.ndarray, violations: np.ndarray, n_keep: int) -> np.ndarray:
        # Base NSGA-II front fill first.
        fronts, _ = self._sort_fronts(objectives, violations)
        keep: List[int] = []
        for front in fronts:
            if len(keep) + len(front) <= n_keep:
                keep.extend(list(front))
                continue

            remain = max(0, n_keep - len(keep))
            if remain <= 0:
                break
            selected = self._niching_pick(objectives, np.asarray(front, dtype=int), remain)
            keep.extend(selected.tolist())
            break
        return np.asarray(keep, dtype=int)

    def _sort_fronts(self, objectives: np.ndarray, violations: np.ndarray):
        from ...utils.performance.fast_non_dominated_sort import FastNonDominatedSort

        return FastNonDominatedSort.sort(objectives, violations)

    def _niching_pick(self, objectives: np.ndarray, front_indices: np.ndarray, remain: int) -> np.ndarray:
        if front_indices.size <= remain:
            return front_indices

        obj = np.asarray(objectives[front_indices], dtype=float)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        zmin = np.min(obj, axis=0)
        zmax = np.max(obj, axis=0)
        scale = np.where((zmax - zmin) > 1e-12, (zmax - zmin), 1.0)
        norm_obj = (obj - zmin) / scale

        if self.reference_points.size == 0 or self.reference_points.shape[1] != norm_obj.shape[1]:
            self.reference_points = self._generate_reference_points(norm_obj.shape[1], max(1, int(self.cfg.divisions)))
        refs = self.reference_points

        assoc = np.argmin(self._pairwise_dist(norm_obj, refs), axis=1)
        selected_local: List[int] = []
        niche_count = np.zeros(refs.shape[0], dtype=int)
        available = set(range(front_indices.size))
        while len(selected_local) < remain and available:
            niche = int(np.argmin(niche_count))
            candidates = [i for i in available if assoc[i] == niche]
            if len(candidates) == 0:
                niche_count[niche] = np.iinfo(np.int32).max
                continue
            if niche_count[niche] == 0:
                d = self._pairwise_dist(norm_obj[np.asarray(candidates, dtype=int)], refs[[niche]])[:, 0]
                pick = candidates[int(np.argmin(d))]
            else:
                pick = int(self._rng.choice(candidates))
            available.remove(pick)
            selected_local.append(pick)
            niche_count[niche] += 1
        return front_indices[np.asarray(selected_local, dtype=int)]

    def _generate_reference_points(self, n_obj: int, divisions: int) -> np.ndarray:
        self.rebuild_unit("reference_directions", objectives=n_obj, divisions=divisions)
        return self.algorithm_unit.reference_points

    def _pairwise_dist(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        aa = np.sum(a * a, axis=1, keepdims=True)
        bb = np.sum(b * b, axis=1, keepdims=True).T
        sq = np.maximum(aa + bb - (2.0 * (a @ b.T)), 0.0)
        return np.sqrt(sq)

    def _sync_runtime_projection(self) -> None:
        super()._sync_runtime_projection()
        if self.reference_points.size > 0:
            self._runtime_projection[KEY_MO_WEIGHTS] = self.reference_points.copy()
