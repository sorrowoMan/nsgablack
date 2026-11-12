"""
NSGA-II adapter.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from collections.abc import Mapping
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from blackbase.call_binding import CallCandidate, invoke_bound_once
from blackbase.types import UnknownState

from ..unit_backed import UnitBackedAdapter, UnitField
from ...representation.structure_builders import PopulationUnitBuilder
from ...units.population_features import SELECTION_RANKING
from ..algorithm_adapter import AlgorithmAdapter
from ..operations import OperatorBindingRestoreError
from ..parent_selection import ParentSelectionRequest
from ..selection import SelectionRequest
from ...core.state.solution_pool import SolutionRef
from ..population_pool_refs import (feedback_pool_bindings, align_pool_bindings, validate_pool_bindings,
                                   publish_population_view, validate_numeric_population_replacement, install_population_state)
from nsgablack.context_keys import (
    KEY_ADAPTER_BEST_OBJECTIVES,
    KEY_ADAPTER_BEST_SCORE,
    KEY_ADAPTER_BEST_X,
)
from ...utils.performance.fast_non_dominated_sort import (
    FastNonDominatedSort,
    fast_non_dominated_sort_optimized,
)


@dataclass
class NSGA2Config:
    population_size: int = 80
    offspring_size: int = 80
    crossover_rate: float = 0.9
    objective_aggregation: str = "sum"


class NSGA2Adapter(UnitBackedAdapter):
    pool_input_modes = ("initialize", "compete")
    publishes_subpools = True
    operation_methods = {"initializer": "initialize", "mutator": "mutate",
                         "parent_selector": "select", "selector": "select", "repair": "repair",
                         "change": "change", "pool_maintenance": "maintain"}
    unit_features = (SELECTION_RANKING,)
    accepts_proposal_replacement = True
    unit_builder_type = PopulationUnitBuilder
    unit_schema = PopulationUnitBuilder.unit_type.schema
    population = UnitField("population")
    objectives = UnitField("objectives")
    violations = UnitField("violations")
    _population_candidate_tokens = UnitField("candidate_tokens")

    @property
    def uses_pipeline_mutation(self):
        return self.get_bound_change() is None

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
        self.set_initializer(initializer)
        self.set_parent_selector(parent_selector)
        self.set_mutator(mutator)
        self.set_change(change)
        self.set_selector(selector)
        self.set_pool_maintenance(pool_maintenance)
        self.set_repair(repair)

    def setup(self, control: Any) -> None:
        self._rng = self.create_local_rng(control)
        self.reset_unit()
        self._population_pool_bindings = ()
        self._rank = np.zeros(0, dtype=int)
        self._crowding = np.zeros(0, dtype=float)
        self._runtime_projection = {}
        self.seed_operator_bindings(self._rng)

    def default_pool_input_count(self):
        return int(self.cfg.population_size)

    def get_solution_pool_roots(self, control):
        return validate_pool_bindings(self._population_pool_bindings, self.population,
            self._population_candidate_tokens, control=control, require=True)

    def get_population_solution_refs(self, control):
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
            candidates = self.init_population(control, control.solution_pool.input_remaining(input_ref), context)
            return (tuple(self.semantic_proposal(control, candidate) for candidate in candidates)
                    if self._operator_bindings() else candidates)
        if self.get_bound_operator("parent_selector") is not None:
            if self.population is None or not len(self.population):
                # Exact evaluated members do not exist yet. Bootstrap through
                # the normal repair/evaluation/admission path before selecting.
                return tuple(self.semantic_proposal(control, candidate) for candidate in
                             self.init_population(control, max(2, int(self.cfg.population_size)), context))
            self.ensure_unit().require_current_feedback()
            self._refresh_ranking()
            return (self._propose_changes(control, context) if self.get_bound_change() is not None
                    else self._propose_from_parent_refs(control, context))
        if self.get_bound_change() is not None:
            if self.population is None or not len(self.population) or self.objectives is None:
                return tuple(self.semantic_proposal(control, candidate) for candidate in
                             self.init_population(control, max(2, int(self.cfg.population_size)), context))
            self.ensure_unit().require_current_feedback()
            self._refresh_ranking()
            return self._propose_changes(control, context)
        from ...units.operator_inputs import mutation_unit_spec
        direct_spec = mutation_unit_spec(self.get_bound_mutator())
        needs_feedback = direct_spec is not None and (
            direct_spec.feedback_view != "none" or any(feature.feedback_view != "none" for feature in direct_spec.features))
        if (self.get_bound_initializer() is not None or needs_feedback) and (self.population is None or not len(self.population)):
            return tuple(self.semantic_proposal(control, candidate) for candidate in
                         self.init_population(control, max(2, int(self.cfg.population_size)), context))
        initialized = self._ensure_population(control, context)
        if initialized is not None:
            return tuple(self.semantic_proposal(control, candidate) for candidate in initialized)
        if self.population is None or self.population.shape[0] == 0:
            return []
        self._refresh_ranking()

        out: List[np.ndarray] = []
        exact_members = (
            self.get_population_solution_refs(control)
            if self._population_pool_bindings and all(self._population_pool_bindings)
            else ()
        )
        semantic_members = (
            control.read_solutions(exact_members).semantic_states if exact_members else ()
        )
        for _ in range(max(1, int(self.cfg.offspring_size))):
            i = self._tournament_pick()
            j = self._tournament_pick()
            # Operators receive drafts; in-place crossover/mutation must not
            # change the current Unit before acceptance.
            p1 = np.array(self.population[i], dtype=float, copy=True)
            p2 = np.array(self.population[j], dtype=float, copy=True)
            child = self._crossover(control, p1, p2, context)
            if semantic_members:
                # Arithmetic variation changes parameter values, not the
                # first parent's model interpretation. Record both parents
                # explicitly instead of guessing metadata from equal rows.
                semantic_child = semantic_members[i].with_values(child)
                origin, = control.prepare_candidate_provenance((semantic_child,))
                origin = replace(origin, source_kind="crossover",
                    parent_token=exact_members[i].candidate_token,
                    transform_stage="crossover",
                    metadata={**dict(origin.metadata), "crossover_parent_refs": (
                        exact_members[i].as_dict(), exact_members[j].as_dict()),
                        "parent_member_indices": (i, j)})
                control.bind_candidate_provenance((child,), (origin,), activate=False)
            mutated = self.mutate_candidate(control, child, context)
            if self.get_bound_mutator() is None:
                child = np.asarray(mutated, dtype=float)
            else:
                child = self.semantic_proposal(control, mutated)
            out.append(child)
        return out

    def _propose_changes(self, control, context):
        """The complete function owns operator order and offspring cardinality."""
        from ..parent_selection import parent_member_pool
        with parent_member_pool(self, control) as member_pool:
            return self._propose_changes_with_members(control, context, member_pool)

    def _propose_changes_with_members(self, control, context, member_pool):
        from ..change import ChangeRequest
        from ..change_batch import apply_function_change_batch
        from ..parent_selection import resolve_parent_selection, selected_parent_pool
        members = member_pool.refs
        count = max(1, int(self.cfg.offspring_size))
        out = []
        while len(out) < count:
            parent_selector = self.get_bound_operator("parent_selector")
            if parent_selector is None:
                slots = (self._tournament_pick(), self._tournament_pick())
                pair = tuple(members[i] for i in slots)
            else:
                request = ParentSelectionRequest(members, self._rank, self._crowding, 2,
                    {key: value for key, value in context.items()
                     if isinstance(key, str) and (value is None or type(value) in (str, bool, int, float))},
                    members=member_pool)
                result = parent_selector.select(request, pool=control.solution_pool, rng=self._rng)
                pair, slots = resolve_parent_selection(request, result)
            self._validate_parent_access(control, pair, members)
            parents = control.read_solutions(pair)
            anchor = control.propose_solutions(pair[:1]).semantic_states[0]
            remaining = count - len(out)
            with selected_parent_pool(control, member_pool, pair, slots) as selected:
                request = ChangeRequest(parents.numeric_matrix, source_refs=pair,
                    parameters={"algorithm": type(self).__name__}, context=context,
                    unit_id=self.get_unit_id(), max_outputs=remaining,
                    parent_pool=selected, parent_member_indices=slots)
                children = apply_function_change_batch(self, control, anchor, request, context,
                    rng=self._rng, max_outputs=remaining)
            if not children:
                break  # An explicit empty result is not an implicit retry loop.
            out.extend(self.semantic_proposal(control, child) for child in children)
        return out

    def _validate_parent_access(self, control, refs, members):
        """A parent selector must not enlarge an enclosing task's donors."""
        from ..change_access import current_change_access
        from ..change_pool import ChangePool
        access = current_change_access()
        if access is None:
            return
        scope = ChangePool(control.solution_pool,
            allowed_refs=(*access.seed_refs, *members), allowed_subpools=access.subpools,
            allow_main=access.allow_main)
        try:
            for name in scope.describe()["subpools"]:
                scope.subpool(name)
            if access.allow_main:
                scope.main()
            scope.read(refs)
        finally:
            scope.close()

    def _propose_from_parent_refs(self, control, context):
        from ..parent_selection import parent_member_pool
        with parent_member_pool(self, control) as member_pool:
            return self._propose_from_parent_members(control, context, member_pool)

    def _propose_from_parent_members(self, control, context, member_pool):
        from ..parent_selection import resolve_parent_selection
        count = max(1, int(self.cfg.offspring_size))
        request = ParentSelectionRequest(
            member_pool.refs, self._rank, self._crowding, count * 2,
            {key: value for key, value in context.items()
             if isinstance(key, str) and (value is None or type(value) in (str, bool, int, float))},
            members=member_pool,
        )
        result = self.get_bound_operator("parent_selector").select(
            request, pool=control.solution_pool, rng=self._rng)
        selected, slots = resolve_parent_selection(request, result)
        self._validate_parent_access(control, selected, request.population_refs)
        parents = control.read_solutions(selected)
        out = []
        for index in range(count):
            pair = selected[index * 2:index * 2 + 2]
            p1 = np.array(parents.numeric_matrix[index * 2], dtype=float, copy=True)
            p2 = np.array(parents.numeric_matrix[index * 2 + 1], dtype=float, copy=True)
            child = self._crossover(control, p1, p2, context)
            # Create the proposal through the normal pool handoff. Preserve
            # both exact parents as causal metadata, not implicit GC roots:
            # historical readability follows the pool's retention policy.
            proposal = control.propose_solutions(pair[:1])
            provenance = control.candidate_provenance_for(proposal.semantic_states[0])
            provenance = replace(provenance, source_kind="recombination", transform_stage="crossover",
                metadata={**dict(provenance.metadata), "parent_solution_refs": [ref.as_dict() for ref in pair],
                          "parent_member_indices": slots[index * 2:index * 2 + 2]})
            control.bind_candidate_provenance((child,), (provenance,), activate=False)
            mutated = self.mutate_candidate(control, child, context)
            out.append(self.semantic_proposal(control, mutated))
        return out

    # Compatibility for existing custom subclasses; common ownership is in the
    # Adapter operations contract rather than a second NSGA implementation.
    _semantic_proposal = staticmethod(UnitBackedAdapter.semantic_proposal)

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
        self.ensure_unit()

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
            keep = self._select_survivors(cand, obj, vio,
                min(len(cand), int(self.cfg.population_size)), context, control=control,
                solution_refs=tuple(None if value is None else SolutionRef.from_dict(value["ref"])
                                    for value in incoming_bindings),
                accepted_refs=tuple(SolutionRef.from_dict(value["ref"])
                                    for value in incoming_bindings if value is not None))
            # Select once before installing members, keeping every semantic
            # input on the same rows. Custom member hooks see one publication.
            selected_inputs = {key: tuple(rows[i] for i in keep)
                               for key, rows in member_inputs.items()}
            change = self.ensure_unit().initialize_population(cand[keep], obj[keep], vio[keep],
                candidate_tokens=tuple(candidate_tokens[i] for i in keep), **selected_inputs)
            incoming_bindings = tuple(incoming_bindings[i] for i in keep)
        else:
            self.ensure_unit().require_current_feedback()
            merged_obj = np.vstack([self.objectives, obj])
            merged_vio = np.concatenate([self.violations, vio])
            keep = self._select_survivors(np.vstack([self.population, cand]),
                merged_obj, merged_vio, min(len(merged_obj), int(self.cfg.population_size)), context,
                control=control,
                solution_refs=tuple(None if value is None else SolutionRef.from_dict(value["ref"])
                                    for value in (*self._population_pool_bindings, *incoming_bindings)),
                accepted_refs=tuple(SolutionRef.from_dict(value["ref"])
                                    for value in incoming_bindings if value is not None))
            change = self.ensure_unit().apply_selection(keep, cand, obj, vio, candidate_tokens=candidate_tokens, **member_inputs)

        self._population_pool_bindings = align_pool_bindings(
            self._population_pool_bindings, incoming_bindings, change)

        self._refresh_ranking()
        self._sync_runtime_projection()
        publish_population_view(self, control)
        from ..pool_maintenance import run_pool_maintenance
        run_pool_maintenance(self, control, candidates, feedback, context, rng=self._rng)

    def set_population_state(self, control, batch, feedback, *, solution_refs, provenance):
        install_population_state(self, control, batch, feedback, solution_refs=solution_refs, provenance=provenance)
        self._refresh_ranking()
        self._sync_runtime_projection()
        publish_population_view(self, control)
        return True

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
            self.ensure_unit().attach_feedback(obj, vio)
        else:
            self.ensure_unit().initialize_population(pop, obj, vio)
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
        state = {
            "population": None if self.population is None else self.population.tolist(),
            "objectives": None if self.objectives is None else self.objectives.tolist(),
            "violations": None if self.violations is None else self.violations.tolist(),
            "candidate_tokens": list(self._population_candidate_tokens),
            "population_pool_bindings": copy.deepcopy(list(self._population_pool_bindings)),
            "rng_state": copy.deepcopy(self._rng.bit_generator.state),
        }
        return state

    def _snapshot_algorithm_step_state(self):
        # Portable checkpoints retain their established compatibility fields;
        # rollback already carries all members exactly once in algorithm_unit.
        if (type(self)._get_algorithm_state is not NSGA2Adapter._get_algorithm_state
                or type(self)._set_algorithm_state is not NSGA2Adapter._set_algorithm_state):
            # An extension's additional local state has unknown ownership.
            # Keep its established explicit codec until it declares a snapshot.
            return copy.deepcopy(self._get_algorithm_state())
        return {
            "schema": "nsgablack.nsga2_step_transaction/v1",
            "population_pool_bindings": copy.deepcopy(self._population_pool_bindings),
            "rng_state": copy.deepcopy(self._rng.bit_generator.state),
            "rank": self._rank.copy(),
            "crowding": self._crowding.copy(),
            "runtime_projection": copy.deepcopy(self._runtime_projection),
        }

    def _restore_algorithm_step_state(self, state):
        if state.get("schema") != "nsgablack.nsga2_step_transaction/v1":
            # Accept a pre-refinement snapshot produced by get_state().
            if "schema" in state:
                raise ValueError("unsupported NSGA2Adapter step transaction schema")
            self._set_algorithm_state(state)
            return
        self._population_pool_bindings = tuple(copy.deepcopy(state.get("population_pool_bindings", ())))
        self._rng.bit_generator.state = copy.deepcopy(state["rng_state"])
        self._rank = np.array(state["rank"], dtype=int, copy=True)
        self._crowding = np.array(state["crowding"], dtype=float, copy=True)
        self._runtime_projection = copy.deepcopy(dict(state.get("runtime_projection", {})))

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
            if self.algorithm_unit is not None:
                self.algorithm_unit.clear_population()
        else:
            self.ensure_unit().initialize_population(pop, obj, vio,
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

    def _ensure_population(self, control: Any, context: Dict[str, Any]) -> Sequence[Any] | None:
        if self.population is not None and self.population.shape[0] > 0:
            return

        # Cross-Adapter intake is explicit through the pool task above. A
        # shared snapshot or control.population can belong to another owner.
        n = max(2, int(self.cfg.population_size))
        created = [self.init_candidate(control, context) for _ in range(n)]
        if any(isinstance(candidate, UnknownState) for candidate in created):
            # A semantic initial candidate is not a numeric population row.
            # Let normal repair/evaluation/admission establish aligned matrix,
            # feedback and exact pool membership before creating the Unit.
            return created
        self.ensure_unit().initialize_population(created, candidate_tokens=self.candidate_tokens_for(control, created),
                                                  **self.member_inputs_for(control, created))

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

        self._rank, self._crowding = self.ensure_unit().feature(SELECTION_RANKING)

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
        fronts, _ = fast_non_dominated_sort_optimized(objectives, violations)
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

    def _select_survivors(self, candidates, objectives, violations, count, context,
                          *, control=None, solution_refs=(), accepted_refs=()):
        """Select rows; member publication remains the PopulationUnit's job."""
        if self.get_bound_selector() is None:
            return (self._environmental_select(objectives, violations, count)
                    if len(candidates) > count else np.arange(len(candidates), dtype=int))
        from ..selection_pool import offered_pool
        from contextlib import nullcontext
        exact = (control is not None and len(solution_refs) == len(candidates)
                 and all(isinstance(ref, SolutionRef) for ref in solution_refs))
        unit = self.algorithm_unit
        old_count = (len(unit.population) if unit is not None and unit.population is not None
                     and unit.objectives is not None and unit.violations is not None else 0)
        scope = (offered_pool(control, solution_refs, objectives=objectives,
                             violations=violations, accepted_refs=accepted_refs,
                             unit=unit, member_rows=(tuple(range(old_count)) +
                                 (None,) * (len(candidates) - old_count)) if unit is not None else None)
                 if exact else nullcontext(None))
        with scope as offered:
            request = SelectionRequest("survivor", candidates, objectives, violations, count,
                parameters={"algorithm": type(self).__name__, "comparison": "multi_objective"},
                context=context, pool=offered)
            return self.select_indices(request, rng=self._rng)

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
