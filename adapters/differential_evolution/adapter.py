"""
Differential Evolution adapter.

This module is adapter-first:
- propose(): generate trial vectors
- update(): greedy replacement into internal population
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from blackbase.contracts import BatchDisposition

from ..unit_backed import UnitBackedAdapter, UnitField
from ...representation.structure_builders import DifferentialPopulationBuilder
from ..algorithm_adapter import AlgorithmAdapter
from ..population_pool_refs import (feedback_pool_bindings, align_pool_bindings, validate_pool_bindings,
                                   publish_population_view, validate_numeric_population_replacement)
from nsgablack.context_keys import (
    KEY_ADAPTER_BEST_OBJECTIVES,
    KEY_ADAPTER_BEST_SCORE,
    KEY_ADAPTER_BEST_X,
    KEY_GENERATION,
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


class DifferentialEvolutionAdapter(UnitBackedAdapter):
    """Process-model DE adapter with propose/update contract."""
    pool_input_modes = ("initialize",)
    publishes_subpools = True
    # Trial replacement keeps its target index and pre-proposal comparison
    # score. No stored displacement or path cost depends on the trial vector.
    accepts_proposal_replacement = True
    unit_builder_type = DifferentialPopulationBuilder
    unit_schema = DifferentialPopulationBuilder.unit_type.schema
    population = UnitField("population")
    objectives = UnitField("objectives")
    violations = UnitField("violations")
    _population_candidate_tokens = UnitField("candidate_tokens")
    _last_target_indices = UnitField("target_indices")
    _last_target_scores = UnitField("target_scores")
    admission_unit_fields = ("target_indices", "target_scores")


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
        super().__init__(name=name, priority=priority, unit_binding=config_kwargs.pop("unit_binding", None))
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
        self._population_pool_bindings = ()
        self._initialization_target = None
        self._initialization_proposed_count = None
        self._last_target_indices: List[int] = []
        self._last_target_scores: np.ndarray = np.zeros(0, dtype=float)
        self._runtime_projection: Dict[str, Any] = {}
        self._rng = np.random.default_rng()

    def setup(self, control: Any) -> None:
        self._rng = self.create_local_rng(control)
        self.reset_unit()
        self._population_pool_bindings = ()
        self._initialization_target = None
        self._initialization_proposed_count = None
        self._last_target_indices = []
        self._last_target_scores = np.zeros(0, dtype=float)
        self._runtime_projection = {KEY_STRATEGY_ID: str(self.cfg.strategy)}

    def propose(self, control: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        from nsgablack.context_keys import KEY_SOLUTION_INPUT_REF
        input_ref = context.get(KEY_SOLUTION_INPUT_REF)
        have = 0 if self.population is None else len(self.population)
        if (input_ref is not None or not have or self.objectives is None or self.violations is None
                or self._initialization_target is not None and have < self._initialization_target):
            remaining = None if input_ref is None else control.solution_pool.input_remaining(input_ref)
            if self._initialization_target is None:
                capacity = max(2, int(self.cfg.population_size))
                self._initialization_target = capacity if remaining is None else min(capacity, remaining)
                if self._initialization_target < 2:
                    raise ValueError("DE initialization requires at least two selected pool candidates")
            count = remaining if remaining is not None else self._initialization_target - have
            candidates = control.init_population(count, context)
            self._last_target_indices, self._last_target_scores = [], np.zeros(0)
            self._initialization_proposed_count = len(candidates)
            return candidates

        n = int(self.population.shape[0])
        batch = max(1, int(self.cfg.batch_size))
        target_indices = self._rng.integers(0, n, size=batch).tolist()
        target_scores = self._population_scores()
        out: List[np.ndarray] = []
        for idx in target_indices:
            target = np.asarray(self.population[idx], dtype=float)
            mutant = self._mutant_vector(idx)
            trial = self._binomial_crossover(target, mutant)
            out.append(np.asarray(trial, dtype=float))

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
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        cand_scores = self._scores(obj, vio)
        candidate_tokens = self.candidate_tokens_for(control, candidates)
        member_inputs = self.member_inputs_for(control, candidates)
        incoming_bindings = feedback_pool_bindings(control, candidates, feedback, candidate_tokens,
            candidate_metadata=member_inputs["candidate_metadata"])

        if self._initialization_proposed_count is not None:
            if len(candidates) != self._initialization_proposed_count:
                raise ValueError("DE initialization feedback does not align with admitted candidates")
            capacity = int(self._initialization_target)
            if self.population is None or not len(self.population) or self.objectives is None or self.violations is None:
                keep = np.argsort(cand_scores, kind="stable")[:capacity] if len(cand) > capacity else np.arange(len(cand))
                change = self.algorithm_unit.initialize_population(cand[keep], obj[keep], vio[keep],
                    candidate_tokens=tuple(candidate_tokens[i] for i in keep),
                    **{name: tuple(rows[i] for i in keep) for name, rows in member_inputs.items()})
                incoming_bindings = tuple(incoming_bindings[i] for i in keep)
            else:
                scores = np.concatenate((self._population_scores(), cand_scores))
                keep = np.argsort(scores, kind="stable")[:capacity] if len(scores) > capacity else np.arange(len(scores))
                change = self.algorithm_unit.apply_selection(keep, cand, obj, vio,
                    candidate_tokens=candidate_tokens, **member_inputs)
            self._population_pool_bindings = align_pool_bindings(self._population_pool_bindings, incoming_bindings, change)
            self._initialization_proposed_count = None
            self._sync_runtime_projection(context)
            publish_population_view(self, control)
            return

        if self.population is None or self.population.shape[0] == 0:
            raise RuntimeError("DE.update requires population state created by propose()")

        candidate_count = int(cand.shape[0])
        objective_count = int(obj.shape[0]) if obj.ndim > 0 else 0
        if objective_count != candidate_count or vio.shape[0] != candidate_count:
            raise ValueError("DE candidate, objective, and violation counts must match")

        if self.objectives is None or self.violations is None:
            n = int(self.population.shape[0])
            m = int(obj.shape[1]) if obj.ndim == 2 else 1
            self.algorithm_unit.attach_feedback(np.full((n, m), np.inf, dtype=float),
                                                np.full(n, np.inf, dtype=float))

        if len(self._last_target_indices) != candidate_count:
            raise ValueError("DE feedback must align with pending target indices")
        if len(self._last_target_scores) != candidate_count:
            raise ValueError("DE feedback must align with pending target scores")

        self.algorithm_unit.require_current_feedback()
        accepted = []
        for j, target_idx in enumerate(self._last_target_indices):
            if target_idx < 0 or target_idx >= self.population.shape[0]:
                raise ValueError(f"DE target index {target_idx} is outside the population")
            target_score = float(self._last_target_scores[j])
            if float(cand_scores[j]) <= target_score:
                accepted.append(j)
        if accepted:
            change = self.algorithm_unit.replace_evaluated_rows(
                [self._last_target_indices[j] for j in accepted],
                cand[accepted], obj[accepted], vio[accepted],
                candidate_tokens=tuple(candidate_tokens[j] for j in accepted),
                **{name: tuple(rows[j] for j in accepted) for name, rows in member_inputs.items()},
            )
            self._population_pool_bindings = align_pool_bindings(self._population_pool_bindings,
                tuple(incoming_bindings[j] for j in accepted), change)
        self._sync_runtime_projection(context)
        publish_population_view(self, control)

    def default_pool_input_count(self):
        return max(2, int(self.cfg.population_size))

    def get_solution_pool_roots(self, control):
        return validate_pool_bindings(self._population_pool_bindings, self.population,
            self._population_candidate_tokens, control=control, require=True)

    def on_proposal_disposition(
        self,
        control: Any,
        disposition: BatchDisposition,
        context: Dict[str, Any],
    ) -> None:
        del control, context
        if self._initialization_proposed_count is not None:
            if disposition.proposed_count != self._initialization_proposed_count:
                raise ValueError("DE initialization disposition does not align with proposals")
            self._initialization_proposed_count = len(disposition.accepted_indices)
            return
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
        validate_numeric_population_replacement(self._population_pool_bindings, preserve_tokens=preserve_tokens)
        if preserve_tokens:
            self.algorithm_unit.attach_feedback(obj, vio)
        else:
            self.algorithm_unit.initialize_population(pop, obj, vio)
            self._population_pool_bindings = (None,) * len(pop)
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

    def _get_algorithm_state(self) -> Dict[str, Any]:
        return {
            "population": None if self.population is None else self.population.tolist(),
            "objectives": None if self.objectives is None else self.objectives.tolist(),
            "violations": None if self.violations is None else self.violations.tolist(),
            "candidate_tokens": list(self._population_candidate_tokens),
            "population_pool_bindings": copy.deepcopy(list(self._population_pool_bindings)),
            "initialization_target": self._initialization_target,
            "initialization_proposed_count": self._initialization_proposed_count,
            "strategy": str(self.cfg.strategy),
            "last_target_indices": list(self._last_target_indices),
            "last_target_scores": self._last_target_scores.tolist(),
            "rng_state": copy.deepcopy(self._rng.bit_generator.state),
        }

    def _set_algorithm_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        self._population_pool_bindings = tuple(copy.deepcopy(state.get("population_pool_bindings", ())))
        self._initialization_target = state.get("initialization_target")
        self._initialization_proposed_count = state.get("initialization_proposed_count")
        if (self._initialization_target is not None
                and (type(self._initialization_target) is not int or self._initialization_target < 2)):
            raise ValueError("DE checkpoint initialization target must be at least two")
        if (self._initialization_proposed_count is not None
                and (type(self._initialization_proposed_count) is not int or self._initialization_proposed_count < 0)):
            raise ValueError("DE checkpoint initialization proposal count must be nonnegative")
        pop = state.get("population")
        obj = state.get("objectives")
        vio = state.get("violations")
        if state.get("algorithm_unit") is None:
            self._last_target_indices = []
            self._last_target_scores = np.zeros(0)
            if pop is None:
                self.algorithm_unit.clear_population()
            else:
                self.algorithm_unit.initialize_population(pop, obj, vio,
                    candidate_tokens=tuple(state.get("candidate_tokens", ()) or ()))
        if self.population is not None and len(self._population_candidate_tokens) not in {
            0,
            int(self.population.shape[0]),
        }:
            raise ValueError("DE checkpoint tokens do not align with population")
        if self.population is not None and not self._population_candidate_tokens:
            self._population_candidate_tokens = (None,) * int(self.population.shape[0])
        self._last_target_indices = [
            int(index) for index in tuple(state.get("last_target_indices", ()) or ())
        ]
        self._last_target_scores = np.asarray(
            state.get("last_target_scores", ()) or (),
            dtype=float,
        ).reshape(-1)
        if len(self._last_target_indices) != len(self._last_target_scores):
            raise ValueError("DE checkpoint proposal bookkeeping is misaligned")
        rng_state = state.get("rng_state")
        if isinstance(rng_state, dict):
            self._rng.bit_generator.state = copy.deepcopy(rng_state)
        if state.get("algorithm_unit") is None:
            self._sync_runtime_projection({})

    def _after_unit_restore(self):
        validate_pool_bindings(self._population_pool_bindings, self.population, self._population_candidate_tokens)
        self._sync_runtime_projection({})

    def _population_scores(self) -> np.ndarray:
        if self.objectives is None or self.violations is None:
            if self.population is None:
                return np.zeros(0, dtype=float)
            return np.full(self.population.shape[0], np.inf, dtype=float)
        self.algorithm_unit.require_current_feedback()
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
            scores = self._population_scores()
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
