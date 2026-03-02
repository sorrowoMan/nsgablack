"""
NSGA-II adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .algorithm_adapter import AlgorithmAdapter
from ...utils.context.context_keys import (
    KEY_BEST_OBJECTIVE,
    KEY_BEST_X,
    KEY_CONSTRAINT_VIOLATIONS,
    KEY_OBJECTIVES,
    KEY_POPULATION,
    KEY_POPULATION_REF,
    KEY_SNAPSHOT_KEY,
)
from ...utils.performance.fast_non_dominated_sort import FastNonDominatedSort


@dataclass
class NSGA2Config:
    population_size: int = 80
    offspring_size: int = 80
    crossover_rate: float = 0.9
    objective_aggregation: str = "sum"


class NSGA2Adapter(AlgorithmAdapter):
    context_requires = ()
    context_provides = (KEY_BEST_X, KEY_BEST_OBJECTIVE)
    context_mutates = ()
    context_cache = ()
    context_notes = "Population-based NSGA-II adapter with propose/update loop."

    def __init__(self, config: Optional[NSGA2Config] = None, name: str = "nsga2", priority: int = 0) -> None:
        super().__init__(name=name, priority=priority)
        self.cfg = config or NSGA2Config()
        self.population: Optional[np.ndarray] = None
        self.objectives: Optional[np.ndarray] = None
        self.violations: Optional[np.ndarray] = None
        self._rank: np.ndarray = np.zeros(0, dtype=int)
        self._crowding: np.ndarray = np.zeros(0, dtype=float)
        self._runtime_projection: Dict[str, Any] = {}
        self._rng = np.random.default_rng()

    def setup(self, solver: Any) -> None:
        self._rng = self.create_local_rng(solver)
        self.population = None
        self.objectives = None
        self.violations = None
        self._rank = np.zeros(0, dtype=int)
        self._crowding = np.zeros(0, dtype=float)
        self._runtime_projection = {}

    def propose(self, solver: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        self._ensure_population(solver, context)
        if self.population is None or self.population.shape[0] == 0:
            return []
        self._refresh_ranking()

        out: List[np.ndarray] = []
        for _ in range(max(1, int(self.cfg.offspring_size))):
            i = self._tournament_pick()
            j = self._tournament_pick()
            p1 = np.asarray(self.population[i], dtype=float)
            p2 = np.asarray(self.population[j], dtype=float)
            child = self._crossover(solver, p1, p2, context)
            child = np.asarray(solver.mutate_candidate(child, context), dtype=float)
            child = np.asarray(solver.repair_candidate(child, context), dtype=float)
            out.append(child)
        return out

    def update(
        self,
        solver: Any,
        candidates: Sequence[np.ndarray],
        objectives: np.ndarray,
        violations: np.ndarray,
        context: Dict[str, Any],
    ) -> None:
        _ = solver
        _ = context
        if candidates is None or len(candidates) == 0:
            return

        cand = np.asarray(candidates, dtype=float)
        obj = np.asarray(objectives, dtype=float)
        vio = np.asarray(violations, dtype=float).reshape(-1)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)

        if self.population is None or self.objectives is None or self.violations is None:
            self.population = cand.copy()
            self.objectives = obj.copy()
            self.violations = vio.copy()
        else:
            merged_pop = np.vstack([self.population, cand])
            merged_obj = np.vstack([self.objectives, obj])
            merged_vio = np.concatenate([self.violations, vio])
            keep = self._environmental_select(merged_obj, merged_vio, int(self.cfg.population_size))
            self.population = merged_pop[keep]
            self.objectives = merged_obj[keep]
            self.violations = merged_vio[keep]

        self._refresh_ranking()
        self._sync_runtime_projection()

    def set_population(self, population: np.ndarray, objectives: np.ndarray, violations: np.ndarray) -> bool:
        pop, obj, vio = self.validate_population_snapshot(population, objectives, violations)
        self.population = pop.copy()
        self.objectives = obj.copy()
        self.violations = vio.copy()
        self._refresh_ranking()
        self._sync_runtime_projection()
        return True

    def get_population(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        if self.population is None or self.objectives is None or self.violations is None:
            return np.zeros((0, 0), dtype=float), np.zeros((0, 0), dtype=float), np.zeros((0,), dtype=float)
        return (
            np.asarray(self.population, dtype=float),
            np.asarray(self.objectives, dtype=float),
            np.asarray(self.violations, dtype=float).reshape(-1),
        )

    def get_runtime_context_projection(self, solver: Any) -> Dict[str, Any]:
        _ = solver
        return dict(self._runtime_projection)

    def get_runtime_context_projection_sources(self, solver: Any) -> Dict[str, str]:
        _ = solver
        source = f"adapter.{self.__class__.__name__}"
        return {k: source for k in self._runtime_projection.keys()}

    def get_state(self) -> Dict[str, Any]:
        return {
            "population": None if self.population is None else self.population.tolist(),
            "objectives": None if self.objectives is None else self.objectives.tolist(),
            "violations": None if self.violations is None else self.violations.tolist(),
        }

    def set_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        pop = state.get("population")
        obj = state.get("objectives")
        vio = state.get("violations")
        self.population = None if pop is None else np.asarray(pop, dtype=float)
        self.objectives = None if obj is None else np.asarray(obj, dtype=float)
        self.violations = None if vio is None else np.asarray(vio, dtype=float).reshape(-1)
        self._refresh_ranking()
        self._sync_runtime_projection()

    def _ensure_population(self, solver: Any, context: Dict[str, Any]) -> None:
        if self.population is not None and self.population.shape[0] > 0:
            return

        pop = None
        obj = None
        vio = None
        reader = getattr(solver, "read_snapshot", None)
        if callable(reader):
            try:
                key = context.get(KEY_POPULATION_REF) or context.get(KEY_SNAPSHOT_KEY)
            except Exception:
                key = None
            try:
                payload = reader(key) if key else reader()
            except Exception:
                payload = None
            data = payload.data if hasattr(payload, "data") else payload
            if isinstance(data, dict):
                pop = data.get(KEY_POPULATION)
                obj = data.get(KEY_OBJECTIVES)
                vio = data.get(KEY_CONSTRAINT_VIOLATIONS)

        if pop is None:
            pop = getattr(solver, "population", None)
            obj = getattr(solver, "objectives", None)
            vio = getattr(solver, "constraint_violations", None)
        if pop is not None:
            pop_arr = np.asarray(pop, dtype=float)
            if pop_arr.ndim == 2 and pop_arr.shape[0] > 0:
                self.population = pop_arr.copy()
                if obj is not None and vio is not None:
                    self.objectives = np.asarray(obj, dtype=float).copy()
                    self.violations = np.asarray(vio, dtype=float).reshape(-1).copy()
                return

        n = max(2, int(self.cfg.population_size))
        created = [np.asarray(solver.init_candidate(context), dtype=float) for _ in range(n)]
        self.population = np.asarray(created, dtype=float)

    def _refresh_ranking(self) -> None:
        if self.population is None or self.population.shape[0] == 0:
            self._rank = np.zeros(0, dtype=int)
            self._crowding = np.zeros(0, dtype=float)
            return
        if self.objectives is None or self.violations is None:
            n = self.population.shape[0]
            self._rank = np.zeros(n, dtype=int)
            self._crowding = np.zeros(n, dtype=float)
            return

        fronts, rank = FastNonDominatedSort.sort(self.objectives, self.violations)
        crowding = np.zeros(self.population.shape[0], dtype=float)
        for front in fronts:
            dist = FastNonDominatedSort.calculate_crowding_distance(self.objectives, list(front))
            crowding += np.asarray(dist, dtype=float)
        self._rank = np.asarray(rank, dtype=int)
        self._crowding = crowding

    def _tournament_pick(self) -> int:
        assert self.population is not None
        n = int(self.population.shape[0])
        if n <= 1:
            return 0
        i, j = int(self._rng.integers(0, n)), int(self._rng.integers(0, n))
        if self._rank.size != n:
            return int(i)
        if self._rank[i] < self._rank[j]:
            return int(i)
        if self._rank[j] < self._rank[i]:
            return int(j)
        c_i = self._crowding[i] if self._crowding.size == n else 0.0
        c_j = self._crowding[j] if self._crowding.size == n else 0.0
        return int(i if c_i >= c_j else j)

    def _crossover(self, solver: Any, p1: np.ndarray, p2: np.ndarray, context: Dict[str, Any]) -> np.ndarray:
        if self._rng.random() > float(self.cfg.crossover_rate):
            return np.array(p1, copy=True)
        pipeline = getattr(solver, "representation_pipeline", None)
        crossover = getattr(pipeline, "crossover", None) if pipeline is not None else None
        if crossover is not None and hasattr(crossover, "crossover"):
            try:
                c1, c2 = crossover.crossover(p1, p2, context)
            except TypeError:
                c1, c2 = crossover.crossover(p1, p2)
            pick_second = bool(self._rng.random() < 0.5)
            return np.asarray(c2 if pick_second else c1, dtype=float)
        alpha = self._rng.random(p1.shape[0])
        return np.asarray((alpha * p1) + ((1.0 - alpha) * p2), dtype=float)

    def _environmental_select(self, objectives: np.ndarray, violations: np.ndarray, n_keep: int) -> np.ndarray:
        fronts, _ = FastNonDominatedSort.sort(objectives, violations)
        keep: List[int] = []
        for front in fronts:
            if len(keep) + len(front) <= n_keep:
                keep.extend(list(front))
                continue
            dist = FastNonDominatedSort.calculate_crowding_distance(objectives, list(front))
            ranked = sorted(list(front), key=lambda idx: float(dist[idx]), reverse=True)
            remain = max(0, n_keep - len(keep))
            keep.extend(ranked[:remain])
            break
        return np.asarray(keep, dtype=int)

    def _sync_runtime_projection(self) -> None:
        projection: Dict[str, Any] = {}
        if self.population is not None and self.objectives is not None and self.violations is not None and self.population.shape[0] > 0:
            score = self._objective_scores(self.objectives, self.violations)
            best_idx = int(np.argmin(score))
            projection[KEY_BEST_X] = self.population[best_idx].copy()
            projection[KEY_BEST_OBJECTIVE] = self.objectives[best_idx].copy()
        self._runtime_projection = projection

    def _objective_scores(self, objectives: np.ndarray, violations: np.ndarray) -> np.ndarray:
        obj = np.asarray(objectives, dtype=float)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        vio = np.asarray(violations, dtype=float).reshape(-1)
        if str(self.cfg.objective_aggregation).lower() == "first":
            agg = obj[:, 0]
        else:
            agg = np.sum(obj, axis=1)
        return agg + (1e6 * vio)
