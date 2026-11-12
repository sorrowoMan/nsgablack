"""
Variable Neighborhood Search (VNS) as an AlgorithmAdapter.

The adapter owns neighborhood decisions and Unit alignment. Search operators
can be bound directly or resolved through the legacy RepresentationPipeline;
problem repair stays in the control plane before evaluation.
"""

from __future__ import annotations
import copy
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import numpy as np

from ..algorithm_adapter import AlgorithmAdapter
from ..change import ChangeRequest
from ..pool_results import PoolRefinementState
from ..selection import SelectionRequest
from ...units import UnitBinding, UnitBuildRequest, CANDIDATE_SCHEMA
from ...units import StructureBuildRequest
from ...representation.structure_builders import NeighborhoodUnitBuilder
from ...units.contracts import candidate_array
from ...representation.unit_builders import CandidateUnitBuilder
import warnings

from nsgablack.context_keys import (
    KEY_METADATA, KEY_MUTATION_SIGMA, KEY_SOLUTION_INPUT_REF, KEY_VNS_K,
)
from blackbase.types import UnknownState
from blackbase.contracts import BatchDisposition
from ...core.state.incumbent import CandidateProvenance
from ...core.state.solution_pool import SolutionRef


@dataclass
class VNSConfig:
    # number of candidates proposed per step
    batch_size: int = 32

    # neighborhood index range: k in [0, k_max]
    k_max: int = 5

    # sigma schedule: sigma = base_sigma * (scale ** k)
    base_sigma: float = 0.2
    scale: float = 1.6
    max_sigma: float = 10.0

    # accept if strictly better (with constraint penalty)
    accept_tolerance: float = 0.0

    # restart if no improvement after k_max neighborhoods
    restart_on_stagnation: bool = True

    # objective aggregation for multi-objective fallback scoring
    objective_aggregation: str = "sum"  # "sum" or "first"


class VNSAdapter(AlgorithmAdapter):
    """VNS adapter for ComposableSolver.

    A generated, unscored baseline rejected after real evaluation is retried
    through its initializer. Explicit inputs remain fixed for admission-policy
    retries; attempt/deadline limits still bound those retries. Checkpoints
    without a declared baseline origin conservatively keep their supplied point.
    Stagnation schedules a restart for the next proposal, retaining the last
    evaluated selection for a task that completes on this update.
    """
    operation_methods = {"initializer": "initialize", "mutator": "mutate", "selector": "select",
                         "change": "change", "pool_maintenance": "maintain"}
    pool_input_modes = ("initialize",)
    supports_pool_restart = True
    supports_objective_projection = True

    def default_pool_input_count(self):
        return 1

    @property
    def uses_pipeline_mutation(self):
        return self.get_bound_change() is None

    context_requires = ("generation",)
    context_optional = (KEY_METADATA, KEY_SOLUTION_INPUT_REF)
    context_provides = (KEY_VNS_K, KEY_MUTATION_SIGMA)
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "VNS writes neighborhood index/sigma into per-step context for mutator consumption.",
        "Use context-aware mutator to make neighborhood switching effective.",
    )
    state_recovery_level = "L1"
    state_recovery_notes = "Restores neighborhood structure, incumbent/pending Units and identity counter."
    unit_schema = CANDIDATE_SCHEMA
    unit_build_operations = ("fresh", "spawn", "refresh")
    unit_contract_mode = "owned"
    additional_unit_schemas = {"neighborhood": NeighborhoodUnitBuilder.unit_type.schema}
    additional_unit_build_operations = {"neighborhood": ("initialize",)}

    # Soft partner contracts (informational; no hard dependency).
    #
    # VNS itself is representation-agnostic. It communicates neighborhood changes
    # via `context` and expects the representation pipeline's mutator (or a wrapper)
    # to consume these keys.
    recommended_mutators = ["ContextGaussianMutation", "ContextSelectMutator"]

    def __init__(
        self,
        config: Optional[VNSConfig] = None,
        name: str = "vns",
        priority: int = 0,
        unit_binding: Optional[UnitBinding] = None,
        neighborhood_binding: Optional[UnitBinding] = None,
        initializer=None,
        mutator=None,
        selector=None,
        change=None,
        pool_maintenance=None,
        **config_kwargs,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.config = self.resolve_config(
            config=config,
            config_cls=VNSConfig,
            config_kwargs=config_kwargs,
            adapter_name="VNSAdapter",
        )
        self.cfg = self.config
        self.set_pool_maintenance(pool_maintenance)
        self.set_unit_binding(unit_binding or UnitBinding(CandidateUnitBuilder()))
        self.neighborhood_binding = neighborhood_binding or UnitBinding(NeighborhoodUnitBuilder())
        self._require_unit_binding(self.neighborhood_binding, slot="neighborhood")
        self.neighborhood_unit = None
        self._unit_counter = 0
        self._current_unit = None
        self._current_pool_token = None
        self._current_pool_ref = None
        self._current_provenance = None
        self._pending_units = []
        self._baseline_can_reinitialize = False
        self._baseline_event_id_before = None
        self._pending_baseline_token = None
        self._restart_pending = False
        self.k = 0
        self.current_x: Optional[np.ndarray] = None
        self.current_score: Optional[float] = None
        self._current_violation = None
        self._projection_frame = None
        self._warned_missing_operator = False
        self._last_context_projection: Dict[str, Any] = {}
        self._operator_rng = None
        self._selector_results = PoolRefinementState()
        for role, component in (("initializer", initializer), ("mutator", mutator), ("selector", selector)):
            if component is not None:
                self.set_operation(role, component)
        self.set_change(change)

    @property
    def current_unit(self):
        return self._current_unit

    @property
    def current_x(self):
        return None if self._current_unit is None else candidate_array(self._current_unit.to_candidate()).copy()

    @current_x.setter
    def current_x(self, candidate):
        # Directly supplied points are explicit inputs, even if their attached
        # provenance happens to say "initialization".
        self._baseline_can_reinitialize = False
        self._restart_pending = False
        self._current_provenance = None
        self._current_pool_token = None
        self._current_pool_ref = None
        if candidate is None:
            self._current_unit = None
            return
        self._current_unit = self._build_candidate_unit(candidate, {})

    def _build_candidate_unit(self, candidate, context):
        next_id = self._unit_counter + 1
        build_context = dict(context)
        build_context.setdefault(KEY_VNS_K, int(self.k))
        build_context.setdefault(KEY_MUTATION_SIGMA, float(self._current_sigma()))
        unit = self.unit_binding.build(UnitBuildRequest(
            f"{self.name}:candidate:{next_id}", candidate,
            purpose="fresh" if self._current_unit is None else "spawn",
        ), build_context)
        self._unit_counter = next_id
        return unit

    def ensure_neighborhood_unit(self):
        """Construct this search's static geometry only at an algorithm need."""
        if self.neighborhood_unit is None:
            unit = self.neighborhood_binding.build(StructureBuildRequest(
                f"{self.name}:neighborhoods", parameters=self._neighborhood_parameters()))
            if len(unit.scales) != int(self.cfg.k_max) + 1:
                raise ValueError("VNS neighborhood Unit must expose k_max + 1 neighborhoods")
            self.neighborhood_unit = unit
        return self.neighborhood_unit

    def _neighborhood_parameters(self):
        """Identify deferred construction inputs without calculating geometry."""
        return {"k_max": int(self.cfg.k_max), "base_sigma": float(self.cfg.base_sigma),
                "scale": float(self.cfg.scale), "max_sigma": float(self.cfg.max_sigma)}

    def _neighborhood_projection(self):
        """Report only geometry that has actually been constructed."""
        if self.neighborhood_unit is None:
            return {}
        return {KEY_VNS_K: int(self.k),
                KEY_MUTATION_SIGMA: float(self.neighborhood_unit.scales[int(self.k)])}

    @staticmethod
    def _provenance(control, candidate, **kwargs):
        lookup = getattr(control, "candidate_provenance_for", None)
        return lookup(candidate, **kwargs) if callable(lookup) else None

    @staticmethod
    def _bind_projection(control, candidate, provenance):
        if provenance is not None:
            control.bind_candidate_provenance([candidate], [provenance], activate=False)
        return candidate

    def _initialize_current(self, control, context):
        self._baseline_can_reinitialize = False
        self._restart_pending = False
        self._current_violation = None
        self._projection_frame = None
        self._current_pool_ref = None
        candidate = self.init_candidate(control, context)
        self._current_provenance = self._provenance(control, candidate)
        resolver = getattr(control, "semantic_candidate_state", None)
        if callable(resolver) and not isinstance(candidate, UnknownState):
            candidate = resolver(candidate)
        self._current_unit = self._build_candidate_unit(candidate, context)
        self._current_pool_token = None
        provenance = self._current_provenance
        # Only this internal initializer path may opt into a fresh attempt.
        # Pool intake, warm starts, supplied candidates and old checkpoints do
        # not acquire this permission merely by carrying an initialization tag.
        self._baseline_can_reinitialize = bool(
            context.get(KEY_SOLUTION_INPUT_REF) is None
            and provenance is not None
            and provenance.source_kind == "initialization"
            and provenance.warm_start_id is None
            and provenance.parent_token is None
            and not provenance.metadata.get("solution_source_ref")
        )

    def setup(self, control: Any) -> None:
        self.validate_unit_bindings()
        self.neighborhood_unit = None
        self._unit_counter = 0
        self._pending_units = []
        self._baseline_event_id_before = None
        self._pending_baseline_token = None
        self.k = 0
        self.current_x = None
        self.current_score = None
        self._current_violation = None
        self._projection_frame = None
        self._current_pool_token = None
        self._selector_results = PoolRefinementState()
        self._operator_rng = None
        if self.get_local_operator_bindings():
            self._operator_rng = self.create_local_rng(control)
            self.seed_operator_bindings(self._operator_rng)
        self._warn_if_pipeline_does_not_consume_context(control)
        self._last_context_projection = {}

    def _warn_if_pipeline_does_not_consume_context(self, control: Any) -> None:
        """Emit diagnostics without depending on the host source-code code page."""
        if self.get_bound_change() is not None:
            return
        if self._warned_missing_operator:
            return
        mutator = self.get_mutation_operator(control)
        if mutator is None:
            warnings.warn(
                "VNSAdapter pipeline has no declared mutate capability; VNS can only "
                "produce a fixed candidate or fail. Configure a context-aware "
                "ContextGaussianMutation or ContextSelectMutator.",
                RuntimeWarning,
                stacklevel=3,
            )
            self._warned_missing_operator = True
            return
        # Capability is declared by the pipeline; context consumption uses the
        # existing component contract, never a guess from parameter names.
        consumes = bool(getattr(mutator, "context_requires", ()) or getattr(mutator, "context_optional", ()))
        if not consumes:
            warnings.warn(
                "VNSAdapter found a mutator without declared context_requires. "
                "Neighborhood changes may degrade "
                "to fixed perturbations. Use ContextGaussianMutation, "
                "ContextSelectMutator, or another context-aware mutator.",
                RuntimeWarning,
                stacklevel=3,
            )
            self._warned_missing_operator = True

    def propose(self, control: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        self.ensure_neighborhood_unit()
        self._last_context_projection = self._neighborhood_projection()
        if self._restart_pending:
            self.initiate(control, context)
            self.current_score = None
            self._restart_pending = False
        if self.current_x is None:
            self.initiate(control, context)

        # Evaluate the seed itself before comparing neighbors. A pool restart
        # cannot silently assign the first neighbor's score to the input seed.
        if self.current_score is None:
            read_event = getattr(control, "get_last_evaluation_event", None)
            previous = read_event() if callable(read_event) else None
            self._baseline_event_id_before = None if previous is None else previous.event_id
            candidate = self._current_unit.to_candidate()
            if self._current_provenance is None:
                prepare = getattr(control, "prepare_candidate_provenance", None)
                if callable(prepare):
                    self._current_provenance, = prepare((candidate,))
            # Zero-admission repair restores the whole Adapter to its state
            # immediately after propose. Record identity here, before that
            # baseline, rather than depending on a repair-only side effect.
            self._pending_baseline_token = (
                None if self._current_provenance is None else self._current_provenance.candidate_token
            )
            self._pending_units = [self._current_unit]
            return [self._bind_projection(control, candidate, self._current_provenance)]

        return self.change(control, context)

    def initiate(self, control, context):
        """Obtain an unevaluated starting point; explicit pool intake keeps priority."""
        self._initialize_current(control, context)

    def change(self, control, context):
        """Generate neighborhood proposals; evaluation and repair remain outside."""

        sigma = float(self._current_sigma())
        ctx = dict(context)
        ctx[KEY_VNS_K] = int(self.k)
        ctx[KEY_MUTATION_SIGMA] = float(sigma)
        self._last_context_projection = {
            KEY_VNS_K: int(self.k),
            KEY_MUTATION_SIGMA: float(sigma),
        }

        out = []
        self._pending_units = []
        for _ in range(int(self.cfg.batch_size)):
            # Existing numeric mutators consume arrays. Preserve the semantic
            # envelope after numeric mutation. The control plane repairs later.
            template = self._current_unit.to_candidate()
            parent = self._bind_projection(control, self.current_x, self._current_provenance)
            if self.get_bound_change() is None:
                cand = self.mutate_candidate(control, parent, ctx)
            else:
                request = ChangeRequest(
                    np.asarray([candidate_array(parent)]),
                    source_refs=(() if self._current_pool_ref is None else (self._current_pool_ref,)),
                    parameters={"k": int(self.k), "sigma": sigma}, context=ctx,
                    unit_id=self._current_unit.unit_id,
                )
                cand = self.apply_change(control, parent, request, ctx, rng=self._operator_rng)
            provenance = self._provenance(control, cand)
            if isinstance(template, UnknownState) and not isinstance(cand, UnknownState):
                cand = template.with_values(cand)
            unit = self._build_candidate_unit(cand, ctx)
            self._pending_units.append(unit)
            out.append(self._bind_projection(control, unit.to_candidate(), provenance))
        return out

    def get_operator_unit(self):
        return self._current_unit

    def _proposal_contexts(self, proposed_count, context):
        return tuple({**context, KEY_VNS_K: int(self.k), KEY_MUTATION_SIGMA: float(self._current_sigma())}
                     for _ in range(proposed_count))

    def on_proposal_repair(self, control, repair, context):
        if repair.proposed_count != len(self._pending_units):
            raise ValueError("VNS repair must align with pending Units")
        if self.current_score is None and len(self._pending_units) == 1:
            for row, index in enumerate(repair.proposal_indices):
                if index == 0:
                    token = repair.after.candidate_tokens[row]
                    if self._pending_baseline_token is not None and self._pending_baseline_token != token:
                        raise ValueError("VNS baseline repair changed the proposal token")
                    self._pending_baseline_token = token
        for row in repair.changed_rows:
            index = repair.proposal_indices[row]
            old = self._pending_units[index]
            self._pending_units[index] = self.unit_binding.build(UnitBuildRequest(
                old.unit_id, repair.after.semantic_states[row], purpose="refresh"), context)

    def on_proposal_disposition(self, control, disposition: BatchDisposition, context) -> None:
        if disposition.proposed_count != len(self._pending_units):
            raise ValueError("VNS proposal disposition does not match pending Units")
        baseline = self.current_score is None and len(self._pending_units) == 1
        rejected_event = (
            self._evaluated_baseline_rejection(control, context)
            if baseline and not disposition.accepted_indices else None
        )
        self._pending_units = [self._pending_units[index] for index in disposition.accepted_indices]
        self._baseline_event_id_before = None
        self._pending_baseline_token = None
        if rejected_event is not None and self._baseline_can_reinitialize:
            # A normal rejected attempt commits Adapter attempt state. Defer
            # initialization until the next proposal; no score or logical step
            # is invented and the consumed evaluation remains durable.
            # This retries a starting point in the same search, not a new
            # refinement request. Previously evaluated selector results still
            # belong to the task and must remain deliverable/retained.
            evaluated_results = self._selector_results
            self.restart_search(control, context)
            self._selector_results = evaluated_results

    def _evaluated_baseline_rejection(self, control, context):
        """Require this dispatch's Event and exact repaired proposal token.

        Budget clipping and sibling cancellation also send zero dispositions.
        A reason string or a global evaluation counter cannot distinguish them
        from an actually evaluated child in a composite proposal.
        """
        token = self._pending_baseline_token
        metadata = context.get(KEY_METADATA, {})
        summary = metadata.get("evaluation_event", {}) if isinstance(metadata, Mapping) else {}
        event_id = summary.get("event_id") if isinstance(summary, Mapping) else None
        if not token or not event_id or event_id == self._baseline_event_id_before:
            return None
        read_event = getattr(control, "get_last_evaluation_event", None)
        event = read_event() if callable(read_event) else None
        if (event is None or not event.semantic_complete or event.event_id != event_id
                or token not in event.candidate_payload.get("candidate_tokens", ())):
            return None
        return event_id

    def update(
        self,
        control: Any,
        candidates: Sequence[np.ndarray],
        feedback: Any,
        context: Dict[str, Any],
    ) -> None:
        if candidates is None or len(candidates) == 0:
            return
        if self._pending_units and len(candidates) != len(self._pending_units):
            raise ValueError("VNS feedback does not match pending Units")

        best_idx, scores, violations, projection = self.chose(control, candidates, feedback, context)
        self.return_feedback(control, candidates, feedback, context, best_idx=best_idx,
                             best_score=float(scores[best_idx]), violations=violations,
                             projection=projection)
        from ..pool_maintenance import run_pool_maintenance
        run_pool_maintenance(self, control, candidates, feedback, context, rng=self._operator_rng)

    def chose(self, control, candidates, feedback, context):
        """Nominate an evaluated row under this task's unchanged comparison frame."""
        objectives, violations = feedback

        metadata = getattr(feedback, "metadata", {})
        projection = metadata.get("subpool_projection")
        if projection is not None:
            from nsgablack.core.state.pool_views import ObjectiveProjection
            # A projection task uses MOEA/D's feasibility-first order, not a
            # finite penalty that a sufficiently large objective can outweigh.
            projection = ObjectiveProjection.from_dict(dict(projection)).as_dict()
            scores = np.asarray(objectives, dtype=float)[:, 0]
            violations = np.asarray(violations, dtype=float)
            best_idx = min(range(len(scores)), key=lambda i:
                (violations[i] > 0, violations[i] if violations[i] > 0 else scores[i]))
        else:
            scores = self._scores(objectives, violations)
            best_idx = int(np.argmin(scores))
        if self.current_score is not None and projection != getattr(self, "_projection_frame", None):
            raise ValueError("VNS objective projection changed without restarting its task")
        selector_bound = self.get_bound_operator("selector") is not None
        if selector_bound:
            self._selector_results.scores(feedback, self._scores)
            self._selector_results.observe_best(control, candidates, feedback, best_idx,
                scores[best_idx], violations[best_idx])
            if self.current_score is not None:
                request = SelectionRequest("candidate", candidates, objectives, violations, 1,
                    scores=scores, parameters={"k": int(self.k), "sigma": float(self._current_sigma())},
                    context=context)
                best_idx, = self.select_indices(request, rng=self._operator_rng)
        return best_idx, scores, violations, projection

    def return_feedback(self, control, candidates, feedback, context, *, best_idx, best_score,
                        violations, projection):
        """Install an admitted evaluated row or advance the neighborhood state."""

        if self.current_score is None:
            self.current_score = best_score
            self._current_violation = float(violations[best_idx])
            self._projection_frame = projection
            self._accept_candidate(control, candidates, best_idx, context)
            self._capture_accepted_ref(control, feedback, best_idx)
            self._pending_units = []
            self.k = 0
            return

        improved = (best_score + float(self.cfg.accept_tolerance)) < float(self.current_score)
        if projection is not None:
            new_v, old_v = float(violations[best_idx]), self._current_violation
            if old_v is None:
                raise ValueError("VNS projected baseline is missing its constraint violation")
            if new_v > 0 or old_v > 0:
                improved = (new_v <= 0 < old_v) or (new_v > 0 and old_v > 0 and new_v < old_v)
        if improved:
            self.current_score = best_score
            self._current_violation = float(violations[best_idx])
            self._accept_candidate(control, candidates, best_idx, context)
            self._capture_accepted_ref(control, feedback, best_idx)
            self._pending_units = []
            self.k = 0
            self._last_context_projection = {
                KEY_VNS_K: int(self.k),
                KEY_MUTATION_SIGMA: float(self._current_sigma()),
            }
            return

        # no improvement: move to next neighborhood
        self._pending_units = []
        self.k += 1
        if self.k > int(self.cfg.k_max):
            if bool(self.cfg.restart_on_stagnation):
                self.k = 0
                # Keep the evaluated selection deliverable if this update
                # completes an enclosing task. Only a subsequent proposal
                # needs another point and advances the initializer's RNG.
                self._restart_pending = True
            else:
                self.k = int(self.cfg.k_max)
        self._last_context_projection = {
            KEY_VNS_K: int(self.k),
            KEY_MUTATION_SIGMA: float(self._current_sigma()),
        }

    def _current_sigma(self) -> float:
        return float(self.ensure_neighborhood_unit().scales[int(self.k)])

    def _accept_candidate(self, control, candidates, index, context):
        self._current_pool_token = self.candidate_tokens_for(control, candidates)[index]
        self._current_provenance = self._provenance(control, candidates[index])
        indexed = self._current_provenance is None
        if indexed:
            self._current_provenance = self._provenance(control, candidates[index], candidate_index=index)
        resolver = getattr(control, "semantic_candidate_state", None)
        candidate = candidates[index]
        if callable(resolver) and not isinstance(candidate, UnknownState):
            candidate = resolver(candidate, **({"candidate_index": index} if indexed else {}))
        previous = self._pending_units[index] if index < len(self._pending_units) else None
        if previous is not None:
            projected = previous.to_candidate()
            same_values = np.array_equal(candidate_array(projected), candidate_array(candidate), equal_nan=True)
            old_meta = projected.as_dict()["metadata"] if isinstance(projected, UnknownState) else {}
            new_meta = candidate.as_dict()["metadata"] if isinstance(candidate, UnknownState) else {}
            if same_values and old_meta == new_meta:
                self._current_unit = previous
                return
        # The mapped candidate was repaired or supplied directly: construct its
        # new structure instead of guessing an old identity from other rows.
        self._current_unit = self._build_candidate_unit(candidate, context)

    def get_current_candidates(self):
        return None if self._current_unit is None else (self._current_unit.to_candidate(),)

    def _capture_accepted_ref(self, control, feedback, index):
        """Bind the exact accepted row delivered alongside its evaluation.

        A token identifies a candidate lineage, not its selected version. Other
        tasks may subsequently publish a different version of the same token.
        Legacy direct update callers can omit this delivery, but cannot then
        export a result view that promises a specific evaluated candidate.
        """
        items = getattr(feedback, "items", ())
        value = items[index].info.get("accepted_solution_ref") if items else None
        ref = None if value is None else SolutionRef.from_dict(dict(value))
        if ref is not None:
            self._validate_selected_ref(control, ref)
        self._current_pool_ref = ref

    def _validate_selected_ref(self, control, ref):
        if ref.candidate_token != self._current_pool_token:
            raise ValueError("VNS selected solution reference does not match its token")
        # Reading verifies the pool scope, immutable record and row identity;
        # update runs before semantic commit, so accepted pending rows are legal.
        selected = control.solution_pool.read((ref,), allow_pending=True).semantic_states[0]
        current = None if self._current_unit is None else self._current_unit.to_candidate()
        if current is None:
            raise ValueError("VNS selected solution reference has no current Unit")
        same_values = np.array_equal(candidate_array(selected), candidate_array(current), equal_nan=True)
        selected_meta = selected.as_dict()["metadata"] if isinstance(selected, UnknownState) else {}
        current_meta = current.as_dict()["metadata"] if isinstance(current, UnknownState) else {}
        if not same_values or selected_meta != current_meta:
            raise ValueError("VNS selected solution reference differs from its current candidate")

    def restart_search(self, control, context):
        """Start a new task, retaining any already constructed static geometry."""
        self._current_unit = None
        self._current_pool_token = None
        self._current_pool_ref = None
        self._current_provenance = None
        self._pending_units = []
        self._baseline_can_reinitialize = False
        self._baseline_event_id_before = None
        self._pending_baseline_token = None
        self._restart_pending = False
        self.current_score = None
        self._current_violation = None
        self._projection_frame = None
        self._selector_results = PoolRefinementState()
        self.k = 0
        self._last_context_projection = self._neighborhood_projection()

    def get_solution_pool_roots(self, control):
        extra = (self._selector_results.roots(control)
                 if self.get_bound_operator("selector") is not None else ())
        if self.current_score is None:
            return extra
        if self._current_pool_ref is not None:
            return tuple(dict.fromkeys((self._current_pool_ref, *extra)))
        return tuple(dict.fromkeys((*control.solution_pool.refs_for_tokens((self._current_pool_token,)), *extra)))

    def get_pool_refinement_results(self, control):
        """Deliver one exact evaluated result, independently of trial storage.

        A custom nomination may decline the batch's best neighbor. Such an
        evaluated point remains the task's best result, with its own reference.
        """
        if self.get_bound_operator("selector") is not None:
            return self._selector_results.results(control)
        if self.current_score is None:
            return ()
        if self._current_pool_ref is None:
            raise ValueError("VNS refinement result requires an exact accepted solution reference")
        self._validate_selected_ref(control, self._current_pool_ref)
        return (self._current_pool_ref,)

    def get_runtime_context_projection(self, solver: Any) -> Dict[str, Any]:
        _ = solver
        return dict(self._last_context_projection)

    def get_runtime_context_projection_sources(self, solver: Any) -> Dict[str, str]:
        _ = solver
        source = f"adapter.{self.__class__.__name__}"
        return {str(k): source for k in self._last_context_projection.keys()}

    def _scores(self, objectives: np.ndarray, violations: np.ndarray) -> np.ndarray:
        obj = np.asarray(objectives, dtype=float)
        vio = np.asarray(violations, dtype=float).reshape(-1)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        mode = str(self.cfg.objective_aggregation).lower().strip()
        if mode == "first":
            agg = obj[:, 0]
        else:
            agg = np.sum(obj, axis=1)
        return agg + (1e6 * vio)

    def get_state(self) -> Dict[str, Any]:
        return {
            "operator_bindings": self.operator_bindings_state(),
            "operator_rng_state": (None if self._operator_rng is None else
                                   copy.deepcopy(self._operator_rng.bit_generator.state)),
            "selector_results": self._selector_results.as_dict(),
            "unit_contract": self.get_unit_contract(),
            "neighborhood_parameters": self._neighborhood_parameters(),
            "neighborhood_unit": (None if self.neighborhood_unit is None else
                                  self.neighborhood_binding.dump(self.neighborhood_unit)),
            "current_unit": None if self._current_unit is None else self.unit_binding.dump(self._current_unit),
            "unit_counter": self._unit_counter,
            "pending_units": [self.unit_binding.dump(unit) for unit in self._pending_units],
            "baseline_can_reinitialize": self._baseline_can_reinitialize,
            "baseline_event_id_before": self._baseline_event_id_before,
            "pending_baseline_token": self._pending_baseline_token,
            "restart_pending": self._restart_pending,
            "k": int(self.k),
            "current_x": None if self.current_x is None else candidate_array(self.current_x).tolist(),
            "current_score": None if self.current_score is None else float(self.current_score),
            "current_pool_token": self._current_pool_token,
            "current_pool_ref": None if self._current_pool_ref is None else self._current_pool_ref.as_dict(),
            "current_provenance": None if self._current_provenance is None else self._current_provenance.as_dict(),
            "current_violation": getattr(self, "_current_violation", None),
            "projection_frame": getattr(self, "_projection_frame", None),
        }

    def set_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        # Earlier checkpoints did not declare where the initial point came
        # from. Treat that origin conservatively as an explicit input.
        can_reinitialize = state.get("baseline_can_reinitialize", False)
        restart_pending = state.get("restart_pending", False)
        if type(can_reinitialize) is not bool:
            raise ValueError("VNS checkpoint baseline origin must be boolean")
        if type(restart_pending) is not bool:
            raise ValueError("VNS checkpoint pending restart must be boolean")
        baseline_before = state.get("baseline_event_id_before")
        baseline_token = state.get("pending_baseline_token")
        if any(value is not None and (not isinstance(value, str) or not value)
               for value in (baseline_before, baseline_token)):
            raise ValueError("VNS checkpoint baseline Event/token must be nonempty strings")
        selector_results = PoolRefinementState.from_dict(state.get("selector_results"))
        operator_rng = None
        if self.get_local_operator_bindings():
            rng_state = state.get("operator_rng_state")
            if not isinstance(rng_state, dict):
                raise ValueError("VNS bound operations require their saved RNG state")
            operator_rng = np.random.default_rng()
            operator_rng.bit_generator.state = copy.deepcopy(rng_state)
        if "unit_contract" in state and state["unit_contract"] != self.get_unit_contract():
            raise ValueError("VNS checkpoint Unit binding mismatch")
        if ("neighborhood_parameters" in state
                and state["neighborhood_parameters"] != self._neighborhood_parameters()):
            raise ValueError("VNS checkpoint neighborhood construction parameters mismatch")
        if ("neighborhood_unit" in state and state["neighborhood_unit"] is None
                and not {"unit_contract", "neighborhood_parameters"}.issubset(state)):
            raise ValueError("VNS inactive checkpoint requires binding and neighborhood construction identity")
        current = None
        counter = 0
        k = int(state.get("k", 0))
        saved_neighborhood = state.get("neighborhood_unit")
        neighborhood = (None if saved_neighborhood is None else
                        self.neighborhood_binding.restore(saved_neighborhood))
        if (neighborhood is not None and (len(neighborhood.scales) != int(self.cfg.k_max) + 1
                or not 0 <= k < len(neighborhood.scales))):
            raise ValueError("VNS checkpoint neighborhood structure does not match configuration")
        score = state.get("current_score")
        frame = state.get("projection_frame")
        violation = state.get("current_violation")
        if frame is not None:
            from nsgablack.core.state.pool_views import ObjectiveProjection
            frame = ObjectiveProjection.from_dict(frame).as_dict()
            if score is not None and (violation is None or not np.isfinite(violation)):
                raise ValueError("VNS projected checkpoint is missing its constraint baseline")
        provenance = state.get("current_provenance")
        provenance = None if provenance is None else CandidateProvenance.from_dict(provenance)
        token = state.get("current_pool_token")
        if token is not None and (provenance is None or provenance.candidate_token != token):
            raise ValueError("VNS checkpoint current provenance does not match its pool token")
        ref = state.get("current_pool_ref")
        ref = None if ref is None else SolutionRef.from_dict(dict(ref))
        if ref is not None and (ref.candidate_token != token or score is None):
            raise ValueError("VNS checkpoint selected solution reference does not match its baseline")
        if frame is not None and score is not None and ref is None:
            raise ValueError("VNS projected checkpoint requires explicit migration to an exact accepted solution reference")
        pending = [self.unit_binding.restore(unit) for unit in state.get("pending_units", ())]
        if "current_unit" in state:
            current = (None if state["current_unit"] is None
                       else self.unit_binding.restore(state["current_unit"]))
            counter = int(state["unit_counter"])
            if counter < 0:
                raise ValueError("VNS Unit counter must be nonnegative")
        elif "current_x" in state:
            if state["current_x"] is not None:
                raise ValueError("VNS legacy numerical checkpoint requires explicit Unit codec migration")
        if restart_pending and (current is None or score is None or pending):
            raise ValueError("VNS pending restart requires its evaluated current selection")
        if neighborhood is None and (
                current is not None or pending or counter != 0 or k != 0 or score is not None
                or state.get("current_x") is not None or token is not None or ref is not None
                or provenance is not None or violation is not None or frame is not None
                or selector_results.current is not None or selector_results.best is not None
                or can_reinitialize or baseline_before is not None or baseline_token is not None
                or restart_pending):
            raise ValueError("VNS active checkpoint requires its saved neighborhood Unit; explicit migration is required")
        with self.restoring_operator_bindings(state.get("operator_bindings")):
            self._current_unit = current
            self._operator_rng = operator_rng
            self._selector_results = selector_results
            self.neighborhood_unit = neighborhood
            self._unit_counter = counter
            self._pending_units = pending
            self._baseline_can_reinitialize = can_reinitialize
            self._baseline_event_id_before = baseline_before
            self._pending_baseline_token = baseline_token
            self._restart_pending = restart_pending
            self.k = k
            self.current_score = score
            self._current_violation = violation
            self._projection_frame = frame
            self._current_pool_token = token
            self._current_pool_ref = ref
            self._current_provenance = provenance
            self._last_context_projection = self._neighborhood_projection()
