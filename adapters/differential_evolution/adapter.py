"""
Differential Evolution adapter.

This module is adapter-first:
- propose(): generate trial vectors
- update(): greedy replacement into internal population
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from blackbase.contracts import BatchDisposition

from ..algorithm_adapter import AlgorithmAdapter
from blackbase.context.context_keys import (
    KEY_ADAPTER_BEST_OBJECTIVES,
    KEY_ADAPTER_BEST_SCORE,
    KEY_ADAPTER_BEST_X,
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
    context_provides = (
        KEY_STRATEGY_ID,
        KEY_ADAPTER_BEST_SCORE,
        KEY_ADAPTER_BEST_X,
        KEY_ADAPTER_BEST_OBJECTIVES,
    )
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "DE adapter maintains internal population state and performs greedy replacement.",
        "Population write-back is exposed through set_population_snapshot().",
    )
    state_recovery_level = "L2"
    population_state_mode = "single"
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
        self._population_candidate_tokens: tuple[str | None, ...] = ()
        self._last_target_indices: List[int] = []
        self._last_target_scores: np.ndarray = np.zeros(0, dtype=float)
        self._runtime_projection: Dict[str, Any] = {}
        self._rng = np.random.default_rng()

    def setup(self, control: Any) -> None:
        self._rng = self.create_local_rng(control)
        self.population = None
        self.objectives = None
        self.violations = None
        self._population_candidate_tokens = ()
        self._last_target_indices = []
        self._last_target_scores = np.zeros(0, dtype=float)
        self._runtime_projection = {KEY_STRATEGY_ID: str(self.cfg.strategy)}

    def propose(self, control: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        self._ensure_population(control, context)
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
            repaired = control.repair_candidate(trial, context)
            out.append(np.asarray(repaired, dtype=float))

        self._last_target_indices = target_indices
        if target_scores.shape[0] == n:
            self._last_target_scores = np.asarray([target_scores[i] for i in target_indices], dtype=float)
        else:
            self._last_target_scores = np.full(batch, np.inf, dtype=float)
        return out

    def update(
        self,
        control: Any,
        candidates: Sequence[np.ndarray],
        feedback: Any,
        context: Dict[str, Any],
    ) -> None:
        objectives, violations = feedback
        _ = control
        if len(candidates) == 0:
            return

        cand = np.asarray(candidates, dtype=float)
        obj = np.asarray(objectives, dtype=float)
        vio = np.asarray(violations, dtype=float).reshape(-1)
        cand_scores = self._scores(obj, vio)
        candidate_tokens = self.candidate_tokens_for(control, candidates)

        if self.population is None or self.population.shape[0] == 0:
            raise RuntimeError("DE.update requires population state created by propose()")

        candidate_count = int(cand.shape[0])
        objective_count = int(obj.shape[0]) if obj.ndim > 0 else 0
        if objective_count != candidate_count or vio.shape[0] != candidate_count:
            raise ValueError("DE candidate, objective, and violation counts must match")

        if self.objectives is None or self.violations is None:
            n = int(self.population.shape[0])
            m = int(obj.shape[1]) if obj.ndim == 2 else 1
            self.objectives = np.full((n, m), np.inf, dtype=float)
            self.violations = np.full(n, np.inf, dtype=float)

        if len(self._last_target_indices) != candidate_count:
            raise ValueError("DE feedback must align with pending target indices")
        if len(self._last_target_scores) != candidate_count:
            raise ValueError("DE feedback must align with pending target scores")

        for j, target_idx in enumerate(self._last_target_indices):
            if target_idx >= self.population.shape[0]:
                raise ValueError(f"DE target index {target_idx} is outside the population")
            target_score = float(self._last_target_scores[j])
            if float(cand_scores[j]) <= target_score:
                self.population[target_idx] = cand[j]
                self.objectives[target_idx] = obj[j]
                self.violations[target_idx] = vio[j]
                tokens = list(self._population_candidate_tokens)
                if len(tokens) != int(self.population.shape[0]):
                    tokens = [None] * int(self.population.shape[0])
                tokens[target_idx] = candidate_tokens[j]
                self._population_candidate_tokens = tuple(tokens)
        self._sync_runtime_projection(context)

    def on_proposal_disposition(
        self,
        control: Any,
        disposition: BatchDisposition,
        context: Dict[str, Any],
    ) -> None:
        del control, context
        pending_count = len(self._last_target_indices)
        if disposition.proposed_count != pending_count:
            raise ValueError(
                "DE proposal disposition does not match pending target state: "
                f"proposed_count={disposition.proposed_count}, "
                f"pending_count={pending_count}"
            )
        if len(self._last_target_scores) != pending_count:
            raise ValueError(
                "DE pending target indices and scores must have the same length"
            )
        accepted = disposition.accepted_indices
        self._last_target_indices = [
            self._last_target_indices[index] for index in accepted
        ]
        self._last_target_scores = np.asarray(
            [self._last_target_scores[index] for index in accepted],
            dtype=float,
        )

    def set_population_snapshot(self, population: np.ndarray, objectives: np.ndarray, violations: np.ndarray) -> bool:
        pop, obj, vio = self.validate_population_snapshot(population, objectives, violations)
        preserve_tokens = (
            self.population is not None
            and np.asarray(self.population).shape == pop.shape
            and np.array_equal(self.population, pop, equal_nan=True)
            and len(self._population_candidate_tokens) == int(pop.shape[0])
        )
        self.population = pop.copy()
        self.objectives = obj.copy()
        self.violations = vio.copy()
        if not preserve_tokens:
            self._population_candidate_tokens = (None,) * int(pop.shape[0])
        self._sync_runtime_projection({})
        return True

    def get_population_candidate_tokens(self) -> tuple[str | None, ...] | None:
        if self.population is None:
            return ()
        if len(self._population_candidate_tokens) != int(self.population.shape[0]):
            return None
        return tuple(self._population_candidate_tokens)

    def set_population_candidate_tokens(
        self,
        candidate_tokens: Sequence[str | None],
    ) -> bool:
        tokens = tuple(candidate_tokens)
        expected = 0 if self.population is None else int(self.population.shape[0])
        if len(tokens) != expected:
            raise ValueError("DE population tokens must align with population rows")
        self._population_candidate_tokens = tokens
        return True

    def get_population_snapshot(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
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
            "candidate_tokens": list(self._population_candidate_tokens),
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
        self._population_candidate_tokens = tuple(state.get("candidate_tokens", ()) or ())
        if self.population is not None and len(self._population_candidate_tokens) not in {
            0,
            int(self.population.shape[0]),
        }:
            raise ValueError("DE checkpoint tokens do not align with population")
        if self.population is not None and not self._population_candidate_tokens:
            self._population_candidate_tokens = (None,) * int(self.population.shape[0])
        self._sync_runtime_projection({})

    def _ensure_population(self, control: Any, context: Dict[str, Any]) -> None:
        if self.population is not None and self.population.shape[0] > 0:
            return

        pop = None
        obj = None
        vio = None
        reader = getattr(control, "read_snapshot", None)
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
            pop = getattr(control, "population", None)
            obj = getattr(control, "objectives", None)
            vio = getattr(control, "constraint_violations", None)
        if pop is not None:
            pop_arr = np.asarray(pop, dtype=float)
            if pop_arr.ndim == 2 and pop_arr.shape[0] > 0:
                self.population = pop_arr.copy()
                batch_getter = getattr(control, "get_candidate_population_batch", None)
                batch = batch_getter() if callable(batch_getter) else None
                if (
                    batch is not None
                    and batch.numeric_matrix.shape == self.population.shape
                    and np.array_equal(
                        batch.numeric_matrix,
                        self.population,
                        equal_nan=True,
                    )
                ):
                    self._population_candidate_tokens = tuple(batch.candidate_tokens)
                else:
                    self._population_candidate_tokens = (None,) * int(pop_arr.shape[0])
                if obj is not None and vio is not None:
                    self.objectives = np.asarray(obj, dtype=float).copy()
                    self.violations = np.asarray(vio, dtype=float).reshape(-1).copy()
                self._sync_runtime_projection(context)
                return

        init_n = max(2, int(self.cfg.population_size))
        created = [control.init_candidate(context) for _ in range(init_n)]
        self._population_candidate_tokens = self.candidate_tokens_for(control, created)
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
        _ = context
        projection: Dict[str, Any] = {KEY_STRATEGY_ID: str(self.cfg.strategy)}
        if self.population is not None and self.objectives is not None and self.violations is not None and self.population.shape[0] > 0:
            scores = self._scores(self.objectives, self.violations)
            best_idx = int(np.argmin(scores))
            projection[KEY_ADAPTER_BEST_SCORE] = float(scores[best_idx])
            projection[KEY_ADAPTER_BEST_X] = np.asarray(
                self.population[best_idx],
                dtype=float,
            ).copy()
            projection[KEY_ADAPTER_BEST_OBJECTIVES] = np.asarray(
                self.objectives[best_idx],
                dtype=float,
            ).copy()
        self._runtime_projection = projection
