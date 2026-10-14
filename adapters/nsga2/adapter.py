"""
NSGA-II adapter.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from blackbase.call_binding import CallCandidate, invoke_bound_once

from ..unit_backed import UnitBackedAdapter, UnitField
from ...representation.structure_builders import PopulationUnitBuilder
from ...units.population_features import SELECTION_RANKING
from ..algorithm_adapter import AlgorithmAdapter
from ..population_pool_refs import (feedback_pool_bindings, align_pool_bindings, validate_pool_bindings,
                                   publish_population_view, validate_numeric_population_replacement)
from nsgablack.context_keys import (
    KEY_ADAPTER_BEST_OBJECTIVES,
    KEY_ADAPTER_BEST_SCORE,
    KEY_ADAPTER_BEST_X,
)
from ...utils.performance.fast_non_dominated_sort import FastNonDominatedSort


@dataclass
class NSGA2Config:
    population_size: int = 80
    offspring_size: int = 80
    crossover_rate: float = 0.9
    objective_aggregation: str = "sum"


class NSGA2Adapter(UnitBackedAdapter):
    pool_input_modes = ("initialize", "compete")
    publishes_subpools = True
    uses_pipeline_mutation = True
    unit_features = (SELECTION_RANKING,)
    accepts_proposal_replacement = True
    unit_builder_type = PopulationUnitBuilder
    unit_schema = PopulationUnitBuilder.unit_type.schema
    population = UnitField("population")
    objectives = UnitField("objectives")
    violations = UnitField("violations")
    _population_candidate_tokens = UnitField("candidate_tokens")

    context_requires = ()
    context_provides = (
        KEY_ADAPTER_BEST_X,
        KEY_ADAPTER_BEST_OBJECTIVES,
        KEY_ADAPTER_BEST_SCORE,
    )
    context_mutates = ()
    context_cache = ()
    context_notes = "Population-based NSGA-II adapter with propose/update loop."
    state_recovery_level = "L2"
    population_state_mode = "single"
    state_recovery_notes = "Restores population/objectives/violations and ranking state for deterministic continuation."

    def __init__(
        self,
        config: Optional[NSGA2Config] = None,
        name: str = "nsga2",
        priority: int = 0,
        **config_kwargs,
    ) -> None:
        super().__init__(name=name, priority=priority, unit_binding=config_kwargs.pop("unit_binding", None))
        self.config = self.resolve_config(
            config=config,
            config_cls=NSGA2Config,
            config_kwargs=config_kwargs,
            adapter_name="NSGA2Adapter",
        )
        self.cfg = self.config
        self.population: Optional[np.ndarray] = None
        self.objectives: Optional[np.ndarray] = None
        self.violations: Optional[np.ndarray] = None
        self._population_candidate_tokens: tuple[str | None, ...] = ()
        self._population_pool_bindings = ()
        self._rank: np.ndarray = np.zeros(0, dtype=int)
        self._crowding: np.ndarray = np.zeros(0, dtype=float)
        self._runtime_projection: Dict[str, Any] = {}
        self._rng = np.random.default_rng()

    def setup(self, control: Any) -> None:
        self._rng = self.create_local_rng(control)
        self.reset_unit()
        self._population_pool_bindings = ()
        self._rank = np.zeros(0, dtype=int)
        self._crowding = np.zeros(0, dtype=float)
        self._runtime_projection = {}

    def default_pool_input_count(self):
        return int(self.cfg.population_size)

    def get_solution_pool_roots(self, control):
        return validate_pool_bindings(self._population_pool_bindings, self.population,
            self._population_candidate_tokens, control=control, require=True)

    def propose(self, control: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        from nsgablack.context_keys import KEY_SOLUTION_INPUT_REF
        input_ref = context.get(KEY_SOLUTION_INPUT_REF)
        if input_ref is not None and control.solution_pool.input_remaining(input_ref):
            # Pool bootstrap receives ordinary repair/evaluation/admission. It
            # must not borrow the last sibling's population or bias projection.
            # Intake is a proposal count, not a free-slot count. Even a full
            # Unit can evaluate remaining seeds and select among them.
            return control.init_population(control.solution_pool.input_remaining(input_ref), context)
        self._ensure_population(control, context)
        if self.population is None or self.population.shape[0] == 0:
            return []
        self._refresh_ranking()

        out: List[np.ndarray] = []
        for _ in range(max(1, int(self.cfg.offspring_size))):
            i = self._tournament_pick()
            j = self._tournament_pick()
            # Operators receive drafts; in-place crossover/mutation must not
            # change the current Unit before acceptance.
            p1 = np.array(self.population[i], dtype=float, copy=True)
            p2 = np.array(self.population[j], dtype=float, copy=True)
            child = self._crossover(control, p1, p2, context)
            child = np.asarray(self.mutate_candidate(control, child, context), dtype=float)
            out.append(child)
        return out

    def update(
        self,
        control: Any,
        candidates: Sequence[np.ndarray],
        feedback: Any,
        context: Dict[str, Any],
    ) -> None:
        objectives, violations = feedback
        _ = context
        if candidates is None or len(candidates) == 0:
            return

        cand = np.asarray(candidates, dtype=float)
        obj = np.asarray(objectives, dtype=float)
        vio = np.asarray(violations, dtype=float).reshape(-1)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        candidate_tokens = self.candidate_tokens_for(control, candidates)
        member_inputs = self.member_inputs_for(control, candidates)
        incoming_bindings = feedback_pool_bindings(control, candidates, feedback, candidate_tokens,
            candidate_metadata=member_inputs["candidate_metadata"])

        if self.population is None or len(self.population) == 0 or self.objectives is None or self.violations is None:
            keep = (self._environmental_select(obj, vio, int(self.cfg.population_size))
                    if len(cand) > int(self.cfg.population_size) else np.arange(len(cand)))
            # Select once before installing members, keeping every semantic
            # input on the same rows. Custom member hooks see one publication.
            selected_inputs = {key: tuple(rows[i] for i in keep)
                               for key, rows in member_inputs.items()}
            change = self.algorithm_unit.initialize_population(cand[keep], obj[keep], vio[keep],
                candidate_tokens=tuple(candidate_tokens[i] for i in keep), **selected_inputs)
            incoming_bindings = tuple(incoming_bindings[i] for i in keep)
        else:
            self.algorithm_unit.require_current_feedback()
            merged_obj = np.vstack([self.objectives, obj])
            merged_vio = np.concatenate([self.violations, vio])
            keep = self._environmental_select(merged_obj, merged_vio, int(self.cfg.population_size))
            change = self.algorithm_unit.apply_selection(keep, cand, obj, vio, candidate_tokens=candidate_tokens, **member_inputs)

        self._population_pool_bindings = align_pool_bindings(
            self._population_pool_bindings, incoming_bindings, change)

        self._refresh_ranking()
        self._sync_runtime_projection()
        publish_population_view(self, control)

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
            # The snapshot setter asserts an unchanged row projection. This is
            # feedback refresh, not a new environmental selection.
            self.algorithm_unit.attach_feedback(obj, vio)
        else:
            self.algorithm_unit.initialize_population(pop, obj, vio)
            self._population_pool_bindings = (None,) * len(pop)
        self._refresh_ranking()
        self._sync_runtime_projection()
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
            raise ValueError("NSGA2 population tokens must align with population rows")
        self._population_candidate_tokens = tokens
        return True

    def get_population_snapshot(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
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
            "rng_state": copy.deepcopy(self._rng.bit_generator.state),
        }

    def _set_algorithm_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        self._population_pool_bindings = tuple(copy.deepcopy(state.get("population_pool_bindings", ())))
        if state.get("algorithm_unit") is not None:
            # UnitBackedAdapter restores exact Unit fields, without replaying
            # member hooks or temporarily misaligning custom row fields.
            rng_state = state.get("rng_state")
            if isinstance(rng_state, dict):
                self._rng.bit_generator.state = copy.deepcopy(rng_state)
            return
        pop = state.get("population")
        obj = state.get("objectives")
        vio = state.get("violations")
        if pop is None:
            self.algorithm_unit.clear_population()
        else:
            self.algorithm_unit.initialize_population(pop, obj, vio,
                candidate_tokens=tuple(state.get("candidate_tokens", ()) or ()))
        if self.population is not None and len(self._population_candidate_tokens) not in {
            0,
            int(self.population.shape[0]),
        }:
            raise ValueError("NSGA2 checkpoint tokens do not align with population")
        if self.population is not None and not self._population_candidate_tokens:
            self._population_candidate_tokens = (None,) * int(self.population.shape[0])
        rng_state = state.get("rng_state")
        if isinstance(rng_state, dict):
            self._rng.bit_generator.state = copy.deepcopy(rng_state)
        self._refresh_ranking()
        self._sync_runtime_projection()

    def _ensure_population(self, control: Any, context: Dict[str, Any]) -> None:
        if self.population is not None and self.population.shape[0] > 0:
            return

        # Cross-Adapter intake is explicit through the pool task above. A
        # shared snapshot or control.population can belong to another owner.
        n = max(2, int(self.cfg.population_size))
        created = [control.init_candidate(context) for _ in range(n)]
        self.algorithm_unit.initialize_population(created, candidate_tokens=self.candidate_tokens_for(control, created),
                                                  **self.member_inputs_for(control, created))
        self.rebuild_unit("initialize", context=context)

    def _after_unit_restore(self):
        validate_pool_bindings(self._population_pool_bindings, self.population, self._population_candidate_tokens)
        self._refresh_ranking()
        self._sync_runtime_projection()

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

        self._rank, self._crowding = self.algorithm_unit.feature(SELECTION_RANKING)

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

    def _crossover(self, control: Any, p1: np.ndarray, p2: np.ndarray, context: Dict[str, Any]) -> np.ndarray:
        if self._rng.random() > float(self.cfg.crossover_rate):
            return np.array(p1, copy=True)
        pipeline = getattr(control, "representation_pipeline", None)
        crossover = getattr(pipeline, "crossover", None) if pipeline is not None else None
        if crossover is not None and hasattr(crossover, "crossover"):
            c1, c2 = invoke_bound_once(
                crossover.crossover,
                (
                    CallCandidate(args=(p1, p2, context), label="with_context"),
                    CallCandidate(args=(p1, p2), label="without_context"),
                ),
            )
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
            projection[KEY_ADAPTER_BEST_X] = self.population[best_idx].copy()
            projection[KEY_ADAPTER_BEST_OBJECTIVES] = self.objectives[best_idx].copy()
            projection[KEY_ADAPTER_BEST_SCORE] = float(score[best_idx])
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
