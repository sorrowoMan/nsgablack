"""
Differential Evolution adapter.

This module is adapter-first:
- propose(): generate trial vectors
- update(): greedy replacement into internal population
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from ..algorithm_adapter import AlgorithmAdapter
from ...utils.context.context_keys import (
    KEY_ADAPTER_BEST_SCORE,
    KEY_BEST_OBJECTIVE,
    KEY_BEST_X,
    KEY_CONSTRAINT_VIOLATIONS,
    KEY_GENERATION,
    KEY_OBJECTIVES,
    KEY_POPULATION,
    KEY_POPULATION_REF,
    KEY_SNAPSHOT_KEY,
    KEY_STRATEGY_ID,
)


@dataclass
class DEConfig:
    population_size: int = 64
    batch_size: int = 32
    differential_weight: float = 0.7
    crossover_rate: float = 0.9
    strategy: str = "rand1bin"  # rand1bin / best1bin
    objective_aggregation: str = "sum"  # sum / first


class DifferentialEvolutionAdapter(AlgorithmAdapter):
    """Process-model DE adapter with propose/update contract."""

    context_requires = (KEY_GENERATION,)
    context_provides = (KEY_STRATEGY_ID, KEY_ADAPTER_BEST_SCORE, KEY_BEST_X, KEY_BEST_OBJECTIVE)
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "DE adapter maintains internal population state and performs greedy replacement.",
        "Population write-back is exposed through set_population().",
    )
    state_recovery_level = "L2"
    state_recovery_notes = "Restores internal population/objectives/violations for deterministic continuation."

    def __init__(
        self,
        config: Optional[DEConfig] = None,
        name: str = "de",
        priority: int = 0,
        **config_kwargs,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.config = self.resolve_config(
            config=config,
            config_cls=DEConfig,
            config_kwargs=config_kwargs,
            adapter_name="DifferentialEvolutionAdapter",
        )
        self.cfg = self.config
        self.population: Optional[np.ndarray] = None
        self.objectives: Optional[np.ndarray] = None
        self.violations: Optional[np.ndarray] = None
        self._last_target_indices: List[int] = []
        self._last_target_scores: np.ndarray = np.zeros(0, dtype=float)
        self._runtime_projection: Dict[str, Any] = {}
        self._rng = np.random.default_rng()

    def setup(self, solver: Any) -> None:
        self._rng = self.create_local_rng(solver)
        self.population = None
        self.objectives = None
        self.violations = None
        self._last_target_indices = []
        self._last_target_scores = np.zeros(0, dtype=float)
        self._runtime_projection = {KEY_STRATEGY_ID: str(self.cfg.strategy)}

    def propose(self, solver: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        self._ensure_population(solver, context)
        if self.population is None or self.population.shape[0] == 0:
            return []

        n = int(self.population.shape[0])
        batch = max(1, int(self.cfg.batch_size))
        target_indices = self._rng.integers(0, n, size=batch).tolist()
        target_scores = self._population_scores()
        out: List[np.ndarray] = []
        for idx in target_indices:
            target = np.asarray(self.population[idx], dtype=float)
            mutant = self._mutant_vector(idx)
            trial = self._binomial_crossover(target, mutant)
            repaired = solver.repair_candidate(trial, context)
            out.append(np.asarray(repaired, dtype=float))

        self._last_target_indices = target_indices
        if target_scores.shape[0] == n:
            self._last_target_scores = np.asarray([target_scores[i] for i in target_indices], dtype=float)
        else:
            self._last_target_scores = np.full(batch, np.inf, dtype=float)
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
        if candidates is None or len(candidates) == 0:
            return

        cand = np.asarray(candidates, dtype=float)
        obj = np.asarray(objectives, dtype=float)
        vio = np.asarray(violations, dtype=float).reshape(-1)
        cand_scores = self._scores(obj, vio)

        if self.population is None or self.population.shape[0] == 0:
            self.population = cand.copy()
            self.objectives = obj.copy()
            self.violations = vio.copy()
            self._sync_runtime_projection(context)
            return

        if self.objectives is None or self.violations is None:
            n = int(self.population.shape[0])
            m = int(obj.shape[1]) if obj.ndim == 2 else 1
            self.objectives = np.full((n, m), np.inf, dtype=float)
            self.violations = np.full(n, np.inf, dtype=float)

        if not self._last_target_indices or len(self._last_target_indices) != cand.shape[0]:
            keep = min(self.population.shape[0], cand.shape[0])
            self.population[:keep] = cand[:keep]
            self.objectives[:keep] = obj[:keep]
            self.violations[:keep] = vio[:keep]
            self._sync_runtime_projection(context)
            return

        for j, target_idx in enumerate(self._last_target_indices):
            if target_idx >= self.population.shape[0]:
                continue
            target_score = float(self._last_target_scores[j]) if j < len(self._last_target_scores) else np.inf
            if float(cand_scores[j]) <= target_score:
                self.population[target_idx] = cand[j]
                self.objectives[target_idx] = obj[j]
                self.violations[target_idx] = vio[j]
        self._sync_runtime_projection(context)

    def set_population(self, population: np.ndarray, objectives: np.ndarray, violations: np.ndarray) -> bool:
        pop, obj, vio = self.validate_population_snapshot(population, objectives, violations)
        self.population = pop.copy()
        self.objectives = obj.copy()
        self.violations = vio.copy()
        self._sync_runtime_projection({})
        return True

    def get_population(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
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
            "strategy": str(self.cfg.strategy),
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
        self._sync_runtime_projection({})

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
                self._sync_runtime_projection(context)
                return

        init_n = max(2, int(self.cfg.population_size))
        created = [np.asarray(solver.init_candidate(context), dtype=float) for _ in range(init_n)]
        self.population = np.asarray(created, dtype=float)
        self.objectives = None
        self.violations = None
        self._sync_runtime_projection(context)

    def _population_scores(self) -> np.ndarray:
        if self.objectives is None or self.violations is None:
            if self.population is None:
                return np.zeros(0, dtype=float)
            return np.full(self.population.shape[0], np.inf, dtype=float)
        return self._scores(self.objectives, self.violations)

    def _mutant_vector(self, target_index: int) -> np.ndarray:
        assert self.population is not None
        n = self.population.shape[0]
        if n < 4:
            return np.asarray(self.population[target_index], dtype=float)

        idxs = list(range(n))
        idxs.remove(target_index)
        r1, r2, r3 = self._rng.choice(idxs, size=3, replace=False)
        if str(self.cfg.strategy).lower() == "best1bin":
            scores = self._population_scores()
            best_idx = int(np.argmin(scores)) if scores.size else target_index
            base = self.population[best_idx]
        else:
            base = self.population[r1]
        return np.asarray(base + float(self.cfg.differential_weight) * (self.population[r2] - self.population[r3]), dtype=float)

    def _binomial_crossover(self, target: np.ndarray, mutant: np.ndarray) -> np.ndarray:
        trial = np.array(target, copy=True, dtype=float)
        dim = trial.shape[0]
        j_rand = int(self._rng.integers(0, dim))
        for j in range(dim):
            if self._rng.random() < float(self.cfg.crossover_rate) or j == j_rand:
                trial[j] = mutant[j]
        return trial

    def _scores(self, objectives: np.ndarray, violations: np.ndarray) -> np.ndarray:
        obj = np.asarray(objectives, dtype=float)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        vio = np.asarray(violations, dtype=float).reshape(-1)
        if str(self.cfg.objective_aggregation).lower() == "first":
            agg = obj[:, 0]
        else:
            agg = np.sum(obj, axis=1)
        return agg + (1e6 * vio)

    def _sync_runtime_projection(self, context: Dict[str, Any]) -> None:
        projection: Dict[str, Any] = {KEY_STRATEGY_ID: str(self.cfg.strategy)}
        if self.population is not None and self.objectives is not None and self.violations is not None and self.population.shape[0] > 0:
            scores = self._scores(self.objectives, self.violations)
            best_idx = int(np.argmin(scores))
            projection[KEY_ADAPTER_BEST_SCORE] = float(scores[best_idx])
            projection[KEY_BEST_X] = np.asarray(self.population[best_idx], dtype=float).copy()
            projection[KEY_BEST_OBJECTIVE] = np.asarray(self.objectives[best_idx], dtype=float).copy()
        if KEY_GENERATION in context:
            projection[KEY_GENERATION] = context[KEY_GENERATION]
        self._runtime_projection = projection
