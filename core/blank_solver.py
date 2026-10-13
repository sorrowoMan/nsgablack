"""
Solver control-plane scaffold for custom workflows.

This base class provides optional bias + representation integration without
enforcing any specific optimization loop.
"""

from __future__ import annotations
from blackbase.plugin import report_soft_error as _report_optional_failure

import copy
import hashlib
import json
import logging
import random
import threading
import time
import uuid
import weakref
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Tuple

from .acceleration import AccelerationFacade, AccelerationRegistry, ExecutionResult
from .acceleration_helpers import maybe_accel_map, maybe_accel_run
from blackbase.context import (
    AuthorityIdentity,
    AuthorityStore,
    SnapshotIdentity,
    StateStoreConfig,
    create_authority_store,
)
from blackbase.evaluation import (
    EVALUATION_EVIDENCE_ARCHIVE_KIND,
    EvaluationDispositionEnvelope,
    EvaluationDispositionVerificationReceipt,
    EvaluationEvidenceArchiveManifest,
    EvaluationEvidenceCoordinator,
    EvaluationEvidenceDeferred,
    EvaluationEvidenceInspection,
    EvaluationEvidenceInvalid,
    EvaluationEvidenceJournal,
    EvaluationEvidenceRecord,
    EvaluationEventEnvelope,
    create_evaluation_evidence_journal,
    evaluation_disposition_digest,
)
from blackbase.types import (
    CandidateBatch,
    UnknownState,
    decode_shared_value,
    encode_shared_value,
)
from .control_plane import (
    BaseController,
    ControlArbiter,
    EvaluationBudgetExceeded,
    RuntimeController,
)
from .evaluation_runtime import EvaluationMediator, EvaluationMediatorConfig, EvaluationProvider
from .evaluation_feedback import OptimizationFeedbackBatch
from .runtime_governance import (
    AdaptiveParametersConfig,
    AdaptiveParametersGovernor,
    CompanionOrchestrator,
    CompanionOrchestratorConfig,
    ConvergenceConfig,
    ConvergenceMonitor,
)
from .state.incumbent import (
    DEFAULT_INCUMBENT_POLICY_ID,
    CandidateProvenance,
    IncumbentState,
)
from .state.run_progress import RunProgressState
from .state.step_outcome import StepOutcome

import numpy as np

from blackbase.resources import (
    ArtifactBinding,
    BudgetAccount,
    BudgetClaim,
    ResourceContext,
    SharedBudgetExceeded,
    coerce_resource_context,
)

from .base import BlackBoxProblem
from .interfaces import (
    BiasInterface,
    RepresentationInterface,
    has_bias_module,
    has_numba,
    load_bias_module,
)
from .solver_helpers import (
    AUTHORITY_BEFORE_REF_KEY,
    EVALUATION_EVENT_SNAPSHOT_SCHEMA_V1,
    LAST_EVALUATED_BATCH_KEY,
    LAST_EVALUATION_EVENT_KEY,
    LAST_EVALUATION_DISPOSITION_KEY,
    POPULATION_AUTHORITY_KEY,
    POPULATION_PARTITIONS_KEY,
    POPULATION_SNAPSHOT_SCHEMA_V2,
    ComponentDependencyScheduler,
    apply_bias_module,
    build_context_store_or_memory,
    build_evaluation_event_snapshot_payload,
    build_solver_context,
    build_snapshot_store_or_memory,
    build_snapshot_payload,
    build_snapshot_refs,
    collect_runtime_context_projection,
    ensure_snapshot_readable,
    evaluation_event_envelope_from_snapshot,
    evaluate_individual_with_plugins_and_bias,
    evaluate_population_with_plugins_and_bias,
    get_solver_context_view,
    increment_evaluation_counter,
    get_best_snapshot_fields,
    run_solver_loop,
    sample_random_candidate,
    set_generation_value,
    set_pareto_snapshot_fields,
    snapshot_meta,
    strip_large_context_fields,
    validate_evaluation_event_snapshot,
    validate_population_snapshot_v2,
)
from nsgablack.context_keys import (
    KEY_BEST_CANDIDATE_REF,
    KEY_BEST_OBJECTIVE,
    KEY_BEST_X,
    KEY_CONSTRAINT_VIOLATIONS,
    KEY_CONSTRAINT_VIOLATIONS_REF,
    KEY_DECISION_TRACE,
    KEY_DECISION_TRACE_REF,
    KEY_HISTORY,
    KEY_HISTORY_REF,
    KEY_OBJECTIVES,
    KEY_OBJECTIVES_REF,
    KEY_PARETO_OBJECTIVES,
    KEY_PARETO_OBJECTIVES_REF,
    KEY_PARETO_SOLUTIONS,
    KEY_PARETO_SOLUTIONS_REF,
    KEY_POPULATION,
    KEY_POPULATION_REF,
    KEY_PROBLEM,
    KEY_SNAPSHOT_BACKEND,
    KEY_SNAPSHOT_KEY,
    KEY_SNAPSHOT_META,
    KEY_SNAPSHOT_SCHEMA,
)
from blackbase.context import ContextStore
from blackbase.context import SnapshotStore, make_snapshot_key
from blackbase.plugin import PluginLifecycleReceipt, report_soft_error
from ..utils.extension_contracts import (
    normalize_bias_output,
    normalize_candidate,
    stack_population,
)
from ..plugins import PluginManager

logger = logging.getLogger(__name__)

_SEMANTIC_METADATA_KEY = "candidate.semantic_metadata"
_CANDIDATE_BATCH_SNAPSHOT_KEY = "candidate_batch"
_CANDIDATE_PROVENANCE_SNAPSHOT_KEY = "candidate_provenance"
_CANDIDATE_PARTITIONS_SNAPSHOT_KEY = POPULATION_PARTITIONS_KEY


@dataclass(frozen=True)
class _IncumbentCommit:
    """One authoritative in-memory incumbent commit."""

    state: IncumbentState | None
    candidate_ref: str | None
    revision: int


from .semantic_extension import SolverSemanticExtension, CommittedStepError
from blackbase.runtime import OwnedField, FinalizationHooks, AuthorityRegistry
from blackbase.representation import representation_capabilities
from .state.population_authority import PopulationAuthority, IncumbentParticipant
from .state.run import RunSession
from .evidence_semantics import PopulationEvidenceSemantics


class SolverBase:
    """
    A minimal solver base that keeps the framework contracts intact.

    - Uses BlackBoxProblem for evaluation.
    - Optional bias_module and representation_pipeline.
    - No built-in optimization loop (step() is user/plugin defined).
    """

    population = OwnedField("population_authority", "population")
    objectives = OwnedField("population_authority", "objectives")
    constraint_violations = OwnedField("population_authority", "violations")
    _candidate_population_batch = OwnedField("population_authority", "candidate_batch")
    _candidate_population_provenance = OwnedField("population_authority", "candidate_provenance")
    _active_candidate_provenance = OwnedField("population_authority", "active_provenance")
    _candidate_population_partitions = OwnedField("population_authority", "partitions")
    population_authority_mode = OwnedField("population_authority", "mode")
    _latest_snapshot_handle = OwnedField("population_authority", "snapshot_handle")
    _snapshot_generation = OwnedField("population_authority", "snapshot_generation")
    _active_candidate_population_ref = OwnedField("population_authority", "active_population_ref")
    _snapshot_step_transaction = OwnedField("population_authority", "snapshot_transaction")

    _active_run_id = OwnedField("run_session", "run_id")
    _run_sequence = OwnedField("run_session", "sequence")
    generation = OwnedField("run_session", "generation")
    running = OwnedField("run_session", "running")
    stop_requested = OwnedField("run_session", "stop_requested")
    stop_reason = OwnedField("run_session", "stop_reason")
    _runtime_setup_complete = OwnedField("run_session", "setup_complete")
    _restore_collection_active = OwnedField("run_session", "collecting_restore")
    _restore_apply_active = OwnedField("run_session", "applying_restore")
    _restore_transaction_lock = OwnedField("run_session", "restore_lock")
    _pending_restore_envelopes = OwnedField("run_session", "pending_restore")
    _resume_loaded = OwnedField("run_session", "resume_loaded")
    _resume_cursor = OwnedField("run_session", "resume_cursor")
    _run_progress_steps = OwnedField("run_session", "steps")
    _run_progress_attempts = OwnedField("run_session", "attempts")
    _run_progress_consecutive_idle_attempts = OwnedField("run_session", "idle_attempts")
    _run_progress_elapsed_seconds = OwnedField("run_session", "elapsed")
    _run_progress_clock_started_at = OwnedField("run_session", "clock_started")
    _run_progress_deadline_remaining_seconds = OwnedField("run_session", "deadline_remaining")
    last_result = OwnedField("run_session", "result")
    last_step_outcome = OwnedField("run_session", "last_step_outcome")
    _post_teardown_finalization_active = OwnedField("run_session", "finalizing")
    _evaluation_budget = OwnedField("run_session", "evaluation_budget")

    def __init__(
        self,
        problem: BlackBoxProblem,
        bias_module: Optional[BiasInterface] = None,
        representation_pipeline: Optional[RepresentationInterface] = None,
        ignore_constraint_violation_when_bias: bool = False,
        plugin_strict: bool = False,
        snapshot_strict: bool = False,
        resource_context: Optional[Mapping[str, Any] | ResourceContext] = None,
        # ----------------------------------------------------------------
        # Preferred: pass a shared StateStoreConfig instead of the flat args.
        # If storage_config is provided, its fields override the flat args.
        # ----------------------------------------------------------------
        storage_config: Optional[StateStoreConfig] = None,
        context_store_backend: str = "memory",
        context_store_ttl_seconds: Optional[float] = None,
        context_store_redis_url: str = "redis://localhost:6379/0",
        context_store_key_prefix: str = "nsgablack:context",
        context_store_serializer: str = "safe",
        context_store_hmac_env_var: str = "NSGABLACK_CONTEXT_HMAC_KEY",
        context_store_unsafe_allow_legacy_pickle: bool = False,
        context_store_max_payload_bytes: int = 262_144,
        snapshot_store_backend: str = "memory",
        snapshot_store_ttl_seconds: Optional[float] = None,
        snapshot_store_redis_url: str = "redis://localhost:6379/0",
        snapshot_store_key_prefix: str = "nsgablack:snapshot",
        snapshot_store_dir: Optional[str] = None,
        snapshot_store_scope: Optional[str] = None,
        snapshot_store_serializer: str = "safe",
        snapshot_store_hmac_env_var: str = "NSGABLACK_SNAPSHOT_HMAC_KEY",
        snapshot_store_unsafe_allow_unsigned: bool = False,
        snapshot_store_max_payload_bytes: int = 8_388_608,
        context_inline_candidate_max_bytes: int = 4_096,
        runtime_context_projection_field_max_bytes: int = 4_096,
        runtime_context_projection_total_max_bytes: int = 32_768,
        snapshot_schema: str = "nsgablack.population_snapshot/v2",
        enable_convergence_monitor: bool = False,
        convergence_config: Optional[ConvergenceConfig] = None,
        enable_adaptive_parameters: bool = False,
        adaptive_config: Optional[AdaptiveParametersConfig] = None,
        enable_companion_orchestrator: bool = False,
        companion_config: Optional[CompanionOrchestratorConfig] = None,
    ) -> None:
        # Project the shared config (if supplied) into local store settings.
        # rest of __init__ continues to read them by their original names.
        self.run_session = RunSession()
        self.population_authority = PopulationAuthority()
        from .state.bias_state import BiasStateParticipant
        self._state_participants = [self.population_authority, IncumbentParticipant(self), BiasStateParticipant(self)]
        self.authorities = AuthorityRegistry()
        self.authorities.register("population", self.population_authority)
        self.authorities.register("incumbent", self._state_participants[1])
        self.authorities.register("progress", self.run_session, rollback_exempt_reason=self.run_session.rollback_exempt_reason)
        self.authorities.register("result", self.run_session, rollback_exempt_reason=self.run_session.rollback_exempt_reason)
        if storage_config is not None:
            _sc = storage_config.as_dict()
            context_store_backend = _sc.get("context_store_backend", context_store_backend)
            context_store_ttl_seconds = _sc.get("context_store_ttl_seconds", context_store_ttl_seconds)
            context_store_redis_url = _sc.get("context_store_redis_url", context_store_redis_url)
            context_store_key_prefix = _sc.get("context_store_key_prefix", context_store_key_prefix)
            context_store_serializer = _sc.get("context_store_serializer", context_store_serializer)
            context_store_hmac_env_var = _sc.get("context_store_hmac_env_var", context_store_hmac_env_var)
            context_store_unsafe_allow_legacy_pickle = _sc.get(
                "context_store_unsafe_allow_legacy_pickle",
                context_store_unsafe_allow_legacy_pickle,
            )
            context_store_max_payload_bytes = _sc.get(
                "context_store_max_payload_bytes",
                context_store_max_payload_bytes,
            )
            snapshot_store_backend = _sc.get("snapshot_store_backend", snapshot_store_backend)
            snapshot_store_ttl_seconds = _sc.get("snapshot_store_ttl_seconds", snapshot_store_ttl_seconds)
            snapshot_store_redis_url = _sc.get("snapshot_store_redis_url", snapshot_store_redis_url)
            snapshot_store_key_prefix = _sc.get("snapshot_store_key_prefix", snapshot_store_key_prefix)
            snapshot_store_dir = _sc.get("snapshot_store_dir", snapshot_store_dir)
            snapshot_store_scope = _sc.get("snapshot_store_scope", snapshot_store_scope)
            snapshot_store_serializer = _sc.get("snapshot_store_serializer", snapshot_store_serializer)
            snapshot_store_hmac_env_var = _sc.get("snapshot_store_hmac_env_var", snapshot_store_hmac_env_var)
            snapshot_store_unsafe_allow_unsigned = _sc.get("snapshot_store_unsafe_allow_unsigned", snapshot_store_unsafe_allow_unsigned)
            snapshot_store_max_payload_bytes = _sc.get("snapshot_store_max_payload_bytes", snapshot_store_max_payload_bytes)
            context_inline_candidate_max_bytes = _sc.get(
                "context_inline_candidate_max_bytes",
                context_inline_candidate_max_bytes,
            )
            runtime_context_projection_field_max_bytes = _sc.get(
                "runtime_context_projection_field_max_bytes",
                runtime_context_projection_field_max_bytes,
            )
            runtime_context_projection_total_max_bytes = _sc.get(
                "runtime_context_projection_total_max_bytes",
                runtime_context_projection_total_max_bytes,
            )
            snapshot_schema = _sc.get("snapshot_schema", snapshot_schema)
        # Keep reference so callers can introspect / rebuild config.
        self._storage_config = storage_config

        self._resource_context_explicit = resource_context is not None
        self.resource_context = coerce_resource_context(
            resource_context if resource_context is not None else {"scope": "optimization"}
        )
        self.case_runtime: Any | None = None

        self.problem = problem
        self.dimension = problem.dimension
        self.num_objectives = problem.get_num_objectives()
        self.var_bounds = problem.bounds

        self._bias_module_internal: Optional[BiasInterface] = None
        self.bias_module = bias_module
        self.enable_bias = bias_module is not None
        # If True, constraint violations will be ignored (set to 0) when bias is enabled.
        # Use only when constraints are fully handled by representation repair and/or bias penalties.
        self.ignore_constraint_violation_when_bias = bool(ignore_constraint_violation_when_bias)
        self.semantic_extensions: list[SolverSemanticExtension] = []
        self.finalization_hooks = FinalizationHooks()

        self._representation_internal: Optional[RepresentationInterface] = None
        self.representation_pipeline = representation_pipeline

        # Keep short-circuit hooks in capability layer.
        # - evaluate_population: plugin takeover (surrogate/cache/layered eval)
        # - evaluate_individual: per-candidate override
        self.plugin_manager = PluginManager(
            short_circuit=False,
            short_circuit_events=[],
            strict=bool(plugin_strict),
        )
        self._convergence_monitor = (
            ConvergenceMonitor(convergence_config) if bool(enable_convergence_monitor) else None
        )
        self._adaptive_governor = (
            AdaptiveParametersGovernor(adaptive_config) if bool(enable_adaptive_parameters) else None
        )
        self._companion_orchestrator = (
            CompanionOrchestrator(companion_config) if bool(enable_companion_orchestrator) else None
        )
        # L0: cross-cutting acceleration infrastructure (not plugin-ordered).
        # Backend factories are Case-local. A process-global registry lets one
        # concurrently built Case replace another Case's execution backend.
        self.accel = AccelerationFacade(AccelerationRegistry())
        self._accel_default_backends: dict[str, str] = {}
        # L3: runtime control-plane (slot/domain arbitration).
        self.control_arbiter = ControlArbiter(strict=bool(plugin_strict))
        self.runtime_controller = RuntimeController(arbiter=self.control_arbiter)
        # L4: single evaluation mediation entry.
        self.evaluation_mediator = EvaluationMediator(
            EvaluationMediatorConfig(
                allow_approximate=False,
                strict_conflict=True,
            )
        )
        self._plugin_scheduler = ComponentDependencyScheduler()
        self.plugin_strict = bool(plugin_strict)
        self.snapshot_strict = bool(snapshot_strict)

        self.population = None
        self.objectives = None
        self.constraint_violations = None
        self._last_individual_feedback = None
        self._last_feedback_batch: OptimizationFeedbackBatch | None = None
        self._last_evaluated_event_batch: CandidateBatch | None = None
        self._last_evaluated_event_feedback: OptimizationFeedbackBatch | None = None
        self._last_evaluated_event_provenance: tuple[CandidateProvenance, ...] = ()
        self._last_evaluated_event_arrays: tuple[
            np.ndarray,
            np.ndarray,
            np.ndarray,
        ] | None = None
        self._last_evaluation_event_id: str | None = None
        self._last_evaluation_event_identity: dict[str, Any] = {}
        self._last_evaluation_authority_before_ref: dict[str, Any] | None = None
        self._last_evaluation_authority_before_edge: dict[str, Any] | None = None
        self._last_evaluation_authority_after_edge: dict[str, Any] | None = None
        self._last_evaluation_event_snapshot_key: str | None = None
        self._last_evaluation_disposition: dict[str, Any] | None = None
        self._last_evaluation_evidence_record: dict[str, Any] | None = None
        self._evaluation_evidence_recovery_report: dict[str, Any] = {
            "status": "not_run",
            "run_id": None,
            "records": [],
        }
        self._evaluation_evidence_archive_staging: dict[str, Any] = {}
        self._incumbent_lock = threading.RLock()
        self._incumbent_commit = _IncumbentCommit(None, None, 0)
        self._incumbent: IncumbentState | None = None
        self.best_x: Optional[np.ndarray] = None
        self.best_objective: Optional[float] = None
        self.best_f: Optional[float] = None
        self.best_score: Optional[float] = None
        self.best_objectives: Optional[np.ndarray] = None
        self.best_constraint_violation: Optional[float] = None
        self._run_sequence = 0
        self._active_run_id: Optional[str] = None
        self._pending_warm_starts: list[dict[str, Any]] = []
        self._consumed_warm_starts: list[dict[str, Any]] = []
        self._proposal_sequence = 0
        self._candidate_sequence = 0
        self._candidate_provenance_by_object: dict[
            int,
            tuple[weakref.ReferenceType[np.ndarray], CandidateProvenance],
        ] = {}
        self._candidate_provenance_lock = threading.RLock()
        self._active_candidate_provenance: list[CandidateProvenance] = []
        self._active_candidate_population_ref: Optional[
            weakref.ReferenceType[np.ndarray]
        ] = None
        self._candidate_population_batch: CandidateBatch | None = None
        self._candidate_population_provenance: tuple[CandidateProvenance, ...] = ()
        self._incumbent_candidate_ref: Optional[str] = None
        self._incumbent_context_projection_revision = 0
        self._incumbent_context_projection_error: Optional[Dict[str, Any]] = None
        self._restored_incumbent_projection_audit: Optional[Dict[str, Any]] = None
        self._runtime_projection_audit: Dict[str, Any] = {}
        self._runtime_projection_audit_report_signature: Any = None
        self._teardown_error: Dict[str, Any] | None = None

        self.generation = 0
        self.evaluation_count = 0
        self._evaluation_budget = BudgetAccount.from_resource_context(
            "evaluations",
            self.resource_context,
        )
        self.running = False
        self.stop_requested = False
        self._runtime_setup_complete = False
        self._restore_collection_active = False
        self._restore_apply_active = False
        self._restore_transaction_lock = threading.RLock()
        self._pending_restore_envelopes: list[
            tuple[str, Callable[[], None]]
        ] = []
        self._resume_loaded = False
        self._resume_cursor = 0
        self._run_progress_steps = 0
        self._run_progress_attempts = 0
        self._run_progress_consecutive_idle_attempts = 0
        self._run_progress_elapsed_seconds = 0.0
        self._run_progress_clock_started_at: float | None = None
        self._run_progress_deadline_remaining_seconds: float | None = None
        self.max_steps = 1
        self.max_step_attempts: int | None = None
        self.max_consecutive_idle_attempts: int | None = None
        self.allow_legacy_step_outcomes = False
        self.start_time = 0.0
        self.random_seed: Optional[int] = None
        self._rng = np.random.default_rng()
        self._rng_streams: Dict[str, np.random.Generator] = {}
        self.context_store_backend = str(context_store_backend or "memory")
        self.context_store_ttl_seconds = context_store_ttl_seconds
        self.context_store_redis_url = str(context_store_redis_url)
        self.context_store_key_prefix = str(context_store_key_prefix)
        self.context_store_serializer = str(context_store_serializer or "safe")
        self.context_store_hmac_env_var = str(
            context_store_hmac_env_var or "NSGABLACK_CONTEXT_HMAC_KEY"
        )
        self.context_store_unsafe_allow_legacy_pickle = bool(
            context_store_unsafe_allow_legacy_pickle
        )
        self.context_store_max_payload_bytes = int(context_store_max_payload_bytes)
        self.context_store: ContextStore = self._build_context_store()
        self.snapshot_store_backend = str(snapshot_store_backend or "memory")
        self.snapshot_store_ttl_seconds = snapshot_store_ttl_seconds
        self.snapshot_store_redis_url = str(snapshot_store_redis_url)
        self.snapshot_store_key_prefix = str(snapshot_store_key_prefix)
        self.snapshot_store_dir = snapshot_store_dir
        self.snapshot_store_scope = snapshot_store_scope
        self.snapshot_store_serializer = str(snapshot_store_serializer or "safe")
        self.snapshot_store_hmac_env_var = str(
            snapshot_store_hmac_env_var or "NSGABLACK_SNAPSHOT_HMAC_KEY"
        )
        self.snapshot_store_unsafe_allow_unsigned = bool(snapshot_store_unsafe_allow_unsigned)
        self.snapshot_store_max_payload_bytes = int(snapshot_store_max_payload_bytes)
        self.context_inline_candidate_max_bytes = max(
            0,
            int(context_inline_candidate_max_bytes),
        )
        self.runtime_context_projection_field_max_bytes = max(
            0,
            int(runtime_context_projection_field_max_bytes),
        )
        self.runtime_context_projection_total_max_bytes = max(
            0,
            int(runtime_context_projection_total_max_bytes),
        )
        self.snapshot_schema = str(snapshot_schema or "nsgablack.population_snapshot/v2")
        self.snapshot_store: SnapshotStore = self._build_snapshot_store()
        from .state.solution_pool import SolutionPool
        self.solution_pool = SolutionPool(self.snapshot_store)
        self._state_participants.append(self.solution_pool)
        self.authorities.register("candidates", self.solution_pool)
        self.authority_store: AuthorityStore = self._build_authority_store()
        self.evaluation_evidence_journal: EvaluationEvidenceJournal = (
            self._build_evaluation_evidence_journal()
        )
        self.evaluation_evidence_semantics = PopulationEvidenceSemantics(self.snapshot_store, self.authority_store)
        self.evaluation_evidence_coordinator = EvaluationEvidenceCoordinator(
            self.evaluation_evidence_journal,
            self.snapshot_store,
            semantics=self.evaluation_evidence_semantics,
        )
        self._latest_snapshot_handle = None
        self._latest_authority_identity: AuthorityIdentity | None = None
        self._latest_evaluation_snapshot_handle = None
        self._latest_evaluation_disposition_snapshot_handle = None
        self._snapshot_generation = None
        self._snapshot_step_transaction: Optional[Dict[str, Any]] = None
        self.snapshot_pre_evaluate_population = False
        self.context_store_update_on_build = True
        self._pending_plugin_order_updates: list[dict[str, Any]] = []

    def _build_context_store(self) -> ContextStore:
        return build_context_store_or_memory(
            backend=self.context_store_backend,
            ttl_seconds=self.context_store_ttl_seconds,
            redis_url=self.context_store_redis_url,
            key_prefix=self.context_store_key_prefix,
            serializer=self.context_store_serializer,
            hmac_env_var=self.context_store_hmac_env_var,
            unsafe_allow_legacy_pickle=self.context_store_unsafe_allow_legacy_pickle,
            max_payload_bytes=self.context_store_max_payload_bytes,
            report_soft_error_fn=report_soft_error,
            logger=logger,
        )

    def _build_snapshot_store(self) -> SnapshotStore:
        base_dir = self.snapshot_store_dir or "runs/snapshots"
        return build_snapshot_store_or_memory(
            backend=self.snapshot_store_backend,
            ttl_seconds=self.snapshot_store_ttl_seconds,
            redis_url=self.snapshot_store_redis_url,
            key_prefix=self.snapshot_store_key_prefix,
            base_dir=base_dir,
            store_scope=self.snapshot_store_scope,
            serializer=self.snapshot_store_serializer,
            hmac_env_var=self.snapshot_store_hmac_env_var,
            unsafe_allow_unsigned=self.snapshot_store_unsafe_allow_unsigned,
            max_payload_bytes=self.snapshot_store_max_payload_bytes,
            context_store=self.context_store,
            report_soft_error_fn=report_soft_error,
            logger=logger,
        )

    def set_context_store(self, store: ContextStore) -> None:
        with self._incumbent_lock:
            self.context_store = store
            self._incumbent_context_projection_revision = -1
            self._incumbent_context_projection_error = {
                "revision": int(self._incumbent_commit.revision),
                "error_type": "ContextStoreReplaced",
                "message": "the authoritative incumbent must be published to the replacement ContextStore",
            }
            self._publish_incumbent_context(self._incumbent_commit)

    def set_snapshot_store(
        self,
        store: SnapshotStore,
        *,
        evaluation_evidence_journal: EvaluationEvidenceJournal | None = None,
        authority_store: AuthorityStore | None = None,
    ) -> None:
        if evaluation_evidence_journal is None:
            raise ValueError(
                "replacing SnapshotStore requires its paired "
                "EvaluationEvidenceJournal"
            )
        if not isinstance(evaluation_evidence_journal, EvaluationEvidenceJournal):
            raise TypeError(
                "evaluation_evidence_journal must implement "
                "EvaluationEvidenceJournal"
            )
        if authority_store is None:
            if str(getattr(store, "backend", "")).lower() != "memory":
                raise ValueError(
                    "replacing a durable SnapshotStore requires its paired "
                    "AuthorityStore"
                )
            authority_store = create_authority_store(
                "memory",
                authority_scope=f"{store.store_scope}:authority",
            )
        if not isinstance(authority_store, AuthorityStore):
            raise TypeError("authority_store must implement AuthorityStore")
        self._assert_snapshot_store_replacement_allowed()
        if not all(
            callable(getattr(store, name, None))
            for name in ("write", "read", "delete")
        ):
            raise TypeError("store must implement the SnapshotStore protocol")
        self.snapshot_store = store
        self.solution_pool.snapshots = store
        self.authority_store = authority_store
        self.evaluation_evidence_journal = evaluation_evidence_journal
        self.evaluation_evidence_semantics = PopulationEvidenceSemantics(self.snapshot_store, self.authority_store)
        self.evaluation_evidence_coordinator = EvaluationEvidenceCoordinator(
            self.evaluation_evidence_journal,
            self.snapshot_store,
            semantics=self.evaluation_evidence_semantics,
        )
        self._latest_authority_identity = None

    def _assert_snapshot_store_replacement_allowed(self) -> None:
        """Fail before constructing or assigning a replacement state pair."""

        if bool(getattr(self, "running", False)):
            raise RuntimeError("cannot replace state stores while Solver is running")
        stateful_fields = {
            "latest_snapshot": self._latest_snapshot_handle,
            "latest_authority": self._latest_authority_identity,
            "latest_evaluation_snapshot": self._latest_evaluation_snapshot_handle,
            "latest_disposition_snapshot": (
                self._latest_evaluation_disposition_snapshot_handle
            ),
            "snapshot_transaction": self._snapshot_step_transaction,
            "incumbent_candidate_ref": self._incumbent_candidate_ref,
            "evaluation_event_snapshot_key": self._last_evaluation_event_snapshot_key,
            "evaluation_evidence_record": self._last_evaluation_evidence_record,
            "solution_pool": True if self.solution_pool.record_count else None,
        }
        active_state = tuple(
            name for name, value in stateful_fields.items() if value is not None
        )
        if active_state:
            raise RuntimeError(
                "cannot replace SnapshotStore after state publication without an "
                f"explicit migration transaction: active={active_state!r}"
            )

    def set_evaluation_evidence_journal(
        self,
        journal: EvaluationEvidenceJournal,
    ) -> None:
        del journal
        raise RuntimeError(
            "EvaluationEvidenceJournal cannot be replaced independently; use "
            "set_snapshot_store(store, evaluation_evidence_journal=journal)"
        )

    def set_resource_context(
        self,
        context: Optional[Mapping[str, Any] | ResourceContext],
    ) -> "SolverBase":
        """Consume the Project L0 grant without allocating resources locally."""

        with self._evaluation_budget.locked():
            if self._evaluation_budget.active_claim_count > 0:
                raise RuntimeError(
                    "cannot replace ResourceContext while evaluation budget reservations are active"
                )
            self._resource_context_explicit = context is not None
            self.resource_context = coerce_resource_context(
                context if context is not None else {"scope": "optimization"}
            )
            self._evaluation_budget = BudgetAccount.from_resource_context(
                "evaluations",
                self.resource_context,
            )
        self._apply_resource_context_to_runtime()
        return self

    def shared_evaluation_budget_status(self) -> Optional[Dict[str, Any]]:
        """Return the current Project-wide evaluation budget audit view."""

        status = self._evaluation_budget.shared_status()
        if status is None:
            return None
        return dict(status.as_dict())

    @property
    def evaluation_budget_reserved(self) -> int:
        """Return unconsumed units held by active evaluation claims."""

        return int(self._evaluation_budget.active_reserved)

    def reset_evaluation_budget(self) -> None:
        """Cancel every unfinished claim before starting a fresh run."""

        self._evaluation_budget.cancel_all()

    def _case_run_id(self) -> Optional[str]:
        runtime = getattr(self, "case_runtime", None)
        request = getattr(runtime, "request", None)
        for holder in (runtime, request):
            identity = getattr(holder, "identity", None)
            value = getattr(identity, "case_run_id", None)
            if value:
                return str(value)
        return None

    def _clear_run_context_refs(self) -> None:
        store = getattr(self, "context_store", None)
        if store is None:
            return
        keys = (
            KEY_BEST_X,
            KEY_BEST_OBJECTIVE,
            KEY_BEST_CANDIDATE_REF,
            KEY_POPULATION_REF,
            KEY_OBJECTIVES_REF,
            KEY_CONSTRAINT_VIOLATIONS_REF,
            KEY_PARETO_SOLUTIONS_REF,
            KEY_PARETO_OBJECTIVES_REF,
            KEY_HISTORY_REF,
            KEY_DECISION_TRACE_REF,
            KEY_SNAPSHOT_KEY,
            KEY_SNAPSHOT_BACKEND,
            KEY_SNAPSHOT_SCHEMA,
            KEY_SNAPSHOT_META,
        )
        delete = getattr(store, "delete", None)
        set_value = getattr(store, "set", None)
        for key in keys:
            try:
                if callable(delete):
                    delete(key)
                elif callable(set_value):
                    set_value(key, None)
                elif isinstance(store, dict):
                    store.pop(key, None)
            except Exception as _fallback_error:
                _report_optional_failure(component=__name__, event='SolverBase._clear_run_context_refs.fallback_154', exc=_fallback_error)
                continue

    def prepare_fresh_run(self) -> None:
        """Reset state owned by one run without discarding explicit warm starts."""

        self._run_sequence = int(getattr(self, "_run_sequence", 0)) + 1
        run_scope = self._case_run_id() or f"solver-{id(self):x}"
        run_nonce = uuid.uuid4().hex[:12]
        self._active_run_id = (
            f"{run_scope}:solver-run:{self._run_sequence}:{run_nonce}"
        )
        self.solution_pool.reset(self._active_run_id)
        self._runtime_projection_audit = {}
        self._runtime_projection_audit_report_signature = None
        self._teardown_error = None
        self._purge_large_context_store()
        self._clear_run_context_refs()
        self.set_generation(0)
        self.evaluation_count = 0
        self.increment_evaluation_count(0)
        self.reset_evaluation_budget()
        self.clear_incumbent()
        self.population = None
        self.objectives = None
        self.constraint_violations = None
        self._last_individual_feedback = None
        self._last_feedback_batch = None
        self._last_evaluated_event_batch = None
        self._last_evaluated_event_feedback = None
        self._last_evaluated_event_provenance = ()
        self._last_evaluated_event_arrays = None
        self._last_evaluation_event_id = None
        self._last_evaluation_event_identity = {}
        self._last_evaluation_authority_before_ref = None
        self._last_evaluation_authority_before_edge = None
        self._last_evaluation_authority_after_edge = None
        self._last_evaluation_event_snapshot_key = None
        self._last_evaluation_disposition = None
        self._last_evaluation_evidence_record = None
        self._evaluation_evidence_recovery_report = {
            "status": "not_run",
            "run_id": self._active_run_id,
            "records": [],
        }
        self._evaluation_evidence_archive_staging = {}
        self.pareto_solutions = None
        self.pareto_objectives = None
        self.pareto_population_snapshot = None
        self.history = []
        self.last_result = None
        self._latest_snapshot_handle = None
        self._latest_authority_identity = None
        self._latest_evaluation_snapshot_handle = None
        self._latest_evaluation_disposition_snapshot_handle = None
        self._snapshot_generation = None
        self._snapshot_step_transaction = None
        self._consumed_warm_starts = []
        self._proposal_sequence = 0
        self._candidate_sequence = 0
        with self._candidate_provenance_lock:
            self._candidate_provenance_by_object = {}
        self._active_candidate_provenance = []
        self._active_candidate_population_ref = None
        self._candidate_population_batch = None
        self._candidate_population_provenance = ()
        self._run_progress_steps = 0
        self._run_progress_attempts = 0
        self._run_progress_consecutive_idle_attempts = 0
        self._run_progress_elapsed_seconds = 0.0
        self._run_progress_clock_started_at = None
        self._run_progress_deadline_remaining_seconds = None
        if hasattr(self, "last_step_summary"):
            self.last_step_summary = {}
        if hasattr(self, "scalarizer_fallback_count"):
            self.scalarizer_fallback_count = 0
        if hasattr(self, "result_quality_degraded"):
            self.result_quality_degraded = False
        if hasattr(self, "scalarizer_audit_complete"):
            self.scalarizer_audit_complete = True
        for extension in self.semantic_extensions:
            extension.prepare_run(self)
        reset_bias = getattr(self.bias_module, "reset_run_state", None)
        if callable(reset_bias):
            reset_bias()

    def get_resource_context(self) -> ResourceContext:
        return self.resource_context

    def set_case_runtime(self, runtime: Any) -> "SolverBase":
        """Accept the shared Case runtime without importing Project internals."""

        self.case_runtime = runtime
        publisher = getattr(runtime, "artifact_publisher", None)
        ledger = getattr(publisher, "publication_ledger", None)
        if ledger is not None:
            self.evaluation_evidence_coordinator.archive_verifier = ledger
        return self

    def checkpoint_case_runtime(self) -> None:
        runtime = self.case_runtime
        checkpoint = getattr(runtime, "checkpoint", None)
        if callable(checkpoint):
            checkpoint()

    def export_case_result(self, raw_output: Any):
        """Project a completed Solver run into the shared Case result codec."""

        from .solver_result import build_solver_result

        self.stage_evaluation_evidence_archives()
        return build_solver_result(self, raw_output)

    def stage_evaluation_evidence_archives(self) -> dict[str, Any]:
        """Stage canonical evidence archives into the Case finalization ledger."""

        runtime = self.case_runtime
        publisher = getattr(runtime, "artifact_publisher", None)
        publish_artifact = getattr(runtime, "publish_artifact", None)
        register_observer = getattr(runtime, "register_finalization_observer", None)
        ledger = getattr(publisher, "publication_ledger", None)
        if (
            runtime is None
            or publisher is None
            or ledger is None
            or not callable(publish_artifact)
            or not callable(register_observer)
        ):
            return {}
        self.evaluation_evidence_coordinator.archive_verifier = ledger
        run_id = str(self._active_run_id or self._evaluation_evidence_run_id())
        state = self._evaluation_evidence_archive_staging
        entries = state.setdefault("entries", {})
        staged: dict[str, Any] = {}
        for record in self.evaluation_evidence_journal.list_records(
            run_id=run_id,
            phases=("finalized", "abandoned"),
        ):
            if record.retention_released:
                continue
            if record.archive_binding is not None:
                binding = ArtifactBinding.from_dict(record.archive_binding)
                self.evaluation_evidence_coordinator.resume_archive_release(
                    record.event_id,
                    reader=publisher,
                )
                staged[record.event_id] = binding.ref
                continue
            artifact_name = f"evaluation-evidence-archive-{record.event_id}"
            existing = entries.get(artifact_name)
            if isinstance(existing, Mapping):
                staged[record.event_id] = existing["ref"]
                continue
            manifest = EvaluationEvidenceArchiveManifest.from_record(
                record,
                snapshots=self.snapshot_store,
            )
            ref = publish_artifact(
                artifact_name,
                manifest.canonical_bytes(),
                serializer="bytes",
                kind=EVALUATION_EVIDENCE_ARCHIVE_KIND,
                media_type="application/json",
                metadata=manifest.artifact_metadata(),
            )
            entries[artifact_name] = {
                "event_id": record.event_id,
                "manifest": manifest,
                "ref": ref,
            }
            staged[record.event_id] = ref

        if entries and not bool(state.get("observer_registered")):
            def release_after_authority_seal(publications: Mapping[str, Any]) -> None:
                for artifact_name, entry in tuple(entries.items()):
                    receipt = publications.get(artifact_name)
                    if receipt is None:
                        raise RuntimeError(
                            f"missing evidence archive receipt: {artifact_name}"
                        )
                    binding = ArtifactBinding(
                        ref=entry["ref"],
                        publication=receipt,
                    )
                    entry["binding"] = binding
                    self.evaluation_evidence_coordinator.archive_and_release(
                        entry["event_id"],
                        manifest=entry["manifest"],
                        binding=binding,
                    )
                    entry["released"] = True

            register_observer(
                release_after_authority_seal,
                name="nsgablack.evaluation_evidence_archive_release",
            )
            state["observer_registered"] = True
        return staged

    def get_resource_context_items(self) -> Dict[str, Any]:
        payload = self.resource_context.as_dict()
        return {
            "resource_context": payload,
            **self.resource_context.context_items(prefix="resource"),
        }

    def limit_workers_by_resource_context(self, requested: Optional[int]) -> Optional[int]:
        """Cap a Case-local worker request by the Project grant when one exists."""

        if not bool(self._resource_context_explicit):
            return requested
        granted = max(1, int(self.resource_context.threads or 1))
        if requested is None:
            return granted
        return max(1, min(int(requested), granted))

    def _apply_resource_context_to_runtime(self) -> None:
        cfg = getattr(self, "_parallel_cfg", None)
        if not isinstance(cfg, dict):
            self._validate_acceleration_defaults_against_resource_context()
            return
        requested = getattr(self, "_parallel_requested_max_workers", cfg.get("max_workers"))
        cfg["max_workers"] = self.limit_workers_by_resource_context(requested)
        extra_context = dict(cfg.get("extra_context") or {})
        extra_context.update(self.get_resource_context_items())
        cfg["extra_context"] = extra_context
        evaluator = getattr(self, "parallel_evaluator", None)
        if evaluator is not None:
            if hasattr(evaluator, "max_workers"):
                evaluator.max_workers = cfg["max_workers"]
            if hasattr(evaluator, "extra_context"):
                evaluator.extra_context = dict(extra_context)
        nested = getattr(self, "nested_parallel_evaluator", None)
        if nested is not None and hasattr(nested, "max_workers"):
            nested.max_workers = cfg["max_workers"]

        self._validate_acceleration_defaults_against_resource_context()

    def _validate_acceleration_defaults_against_resource_context(self) -> None:
        if not bool(self._resource_context_explicit):
            return
        for backend in tuple(self._accel_default_backends.values()):
            self._validate_acceleration_backend_against_resource_context(backend)

        summary = getattr(self, "l0_runtime_summary", None)
        if isinstance(summary, dict):
            summary["effective_resource_context"] = self.resource_context.as_dict()
            summary["resource_context_current"] = True

    def _validate_acceleration_backend_against_resource_context(self, backend: Any) -> None:
        if not bool(self._resource_context_explicit):
            return
        name = str(backend or "").strip().lower()
        if name not in {"gpu", "cuda", "cupy", "torch_cuda"}:
            return
        context = self.resource_context
        grant = dict(context.grant or {})
        tokens = tuple(grant.get("device_tokens", ()) or ())
        gpu_count = int(grant.get("gpus", 0) or 0)
        compute_backend = str(context.compute_backend or "").strip().lower()
        device = str(context.device or "").strip().lower()
        gpu_authorized = bool(
            gpu_count > 0
            or tokens
            or compute_backend in {"cuda", "gpu", "cupy", "torch_cuda"}
            or device.startswith(("cuda", "gpu"))
        )
        if not gpu_authorized:
            raise RuntimeError(
                f"acceleration backend '{name}' requires a GPU grant in ResourceContext"
            )

    def set_context_store_backend(
        self,
        backend: str,
        *,
        ttl_seconds: Optional[float] = None,
        redis_url: Optional[str] = None,
        key_prefix: Optional[str] = None,
        serializer: Optional[str] = None,
        hmac_env_var: Optional[str] = None,
        unsafe_allow_legacy_pickle: Optional[bool] = None,
        max_payload_bytes: Optional[int] = None,
    ) -> None:
        self.context_store_backend = str(backend or "memory")
        if ttl_seconds is not None:
            self.context_store_ttl_seconds = ttl_seconds
        if redis_url is not None:
            self.context_store_redis_url = str(redis_url)
        if key_prefix is not None:
            self.context_store_key_prefix = str(key_prefix)
        if serializer is not None:
            self.context_store_serializer = str(serializer)
        if hmac_env_var is not None:
            self.context_store_hmac_env_var = str(hmac_env_var)
        if unsafe_allow_legacy_pickle is not None:
            self.context_store_unsafe_allow_legacy_pickle = bool(
                unsafe_allow_legacy_pickle
            )
        if max_payload_bytes is not None:
            self.context_store_max_payload_bytes = int(max_payload_bytes)
        self.set_context_store(self._build_context_store())

    def set_snapshot_store_backend(
        self,
        backend: str,
        *,
        ttl_seconds: Optional[float] = None,
        redis_url: Optional[str] = None,
        key_prefix: Optional[str] = None,
        base_dir: Optional[str] = None,
        store_scope: Optional[str] = None,
        serializer: Optional[str] = None,
        hmac_env_var: Optional[str] = None,
        unsafe_allow_unsigned: Optional[bool] = None,
        max_payload_bytes: Optional[int] = None,
    ) -> None:
        self._assert_snapshot_store_replacement_allowed()
        proposed_backend = str(backend or "memory")
        proposed_ttl = (
            self.snapshot_store_ttl_seconds
            if ttl_seconds is None
            else ttl_seconds
        )
        proposed_redis_url = (
            self.snapshot_store_redis_url
            if redis_url is None
            else str(redis_url)
        )
        proposed_key_prefix = (
            self.snapshot_store_key_prefix
            if key_prefix is None
            else str(key_prefix)
        )
        proposed_base_dir = (
            self.snapshot_store_dir
            if base_dir is None
            else str(base_dir)
        )
        proposed_scope = (
            self.snapshot_store_scope
            if store_scope is None
            else str(store_scope)
        )
        proposed_serializer = (
            self.snapshot_store_serializer
            if serializer is None
            else str(serializer)
        )
        proposed_hmac = (
            self.snapshot_store_hmac_env_var
            if hmac_env_var is None
            else str(hmac_env_var)
        )
        proposed_unsafe = (
            self.snapshot_store_unsafe_allow_unsigned
            if unsafe_allow_unsigned is None
            else bool(unsafe_allow_unsigned)
        )
        proposed_max_bytes = (
            self.snapshot_store_max_payload_bytes
            if max_payload_bytes is None
            else int(max_payload_bytes)
        )
        resolved_base_dir = proposed_base_dir or "runs/snapshots"
        new_store = build_snapshot_store_or_memory(
            backend=proposed_backend,
            ttl_seconds=proposed_ttl,
            redis_url=proposed_redis_url,
            key_prefix=proposed_key_prefix,
            base_dir=resolved_base_dir,
            store_scope=proposed_scope,
            serializer=proposed_serializer,
            hmac_env_var=proposed_hmac,
            unsafe_allow_unsigned=proposed_unsafe,
            max_payload_bytes=proposed_max_bytes,
            context_store=self.context_store,
            report_soft_error_fn=report_soft_error,
            logger=logger,
        )
        new_journal = create_evaluation_evidence_journal(
            backend=proposed_backend,
            redis_url=proposed_redis_url,
            key_prefix=f"{proposed_key_prefix}:evaluation-evidence",
            base_dir=resolved_base_dir,
        )
        new_authority_store = create_authority_store(
            proposed_backend,
            redis_url=proposed_redis_url,
            key_prefix=f"{proposed_key_prefix}:authority",
            base_dir=resolved_base_dir,
        )
        self.set_snapshot_store(
            new_store,
            evaluation_evidence_journal=new_journal,
            authority_store=new_authority_store,
        )
        self.snapshot_store_backend = proposed_backend
        self.snapshot_store_ttl_seconds = proposed_ttl
        self.snapshot_store_redis_url = proposed_redis_url
        self.snapshot_store_key_prefix = proposed_key_prefix
        self.snapshot_store_dir = proposed_base_dir
        self.snapshot_store_scope = proposed_scope
        self.snapshot_store_serializer = proposed_serializer
        self.snapshot_store_hmac_env_var = proposed_hmac
        self.snapshot_store_unsafe_allow_unsigned = proposed_unsafe
        self.snapshot_store_max_payload_bytes = proposed_max_bytes

    # ------------------------------------------------------------------
    # Optional dependency accessors (mirrors core solver behavior)
    # ------------------------------------------------------------------
    @property
    def bias_module(self) -> Optional[BiasInterface]:
        """Return the active bias module.

        The getter is **pure** – it never modifies ``self``.  Lazy
        auto-loading is intentionally removed to avoid hidden state
        mutations during serialisation / pickling / property access in
        tests.  Call :meth:`init_bias_module` explicitly if you want the
        framework to auto-construct a default bias module.
        """
        if self._bias_module_internal is not None:
            return self._bias_module_internal
        # Return pre-initialised cached instance only (never create here).
        return getattr(self, "_bias_module_cached", None)

    @bias_module.setter
    def bias_module(self, value: Optional[BiasInterface]) -> None:
        self._bias_module_internal = value
        if value is not None:
            self.enable_bias = True
            # Invalidate any previously cached default.
            if hasattr(self, "_bias_module_cached"):
                delattr(self, "_bias_module_cached")

    def init_bias_module(self, force: bool = False) -> Optional[BiasInterface]:
        """Explicitly initialise the default bias module.

        This is the **sole** place where lazy auto-loading is permitted.
        Call it once during solver setup rather than relying on the
        property getter to do it implicitly.

        Args:
            force: If True, reinitialise even if a module is already present.

        Returns:
            The (possibly newly created) bias module, or None.
        """
        if not force and self._bias_module_internal is not None:
            return self._bias_module_internal
        if not force and hasattr(self, "_bias_module_cached"):
            return self._bias_module_cached  # type: ignore[return-value]
        if self.enable_bias or force:
            loaded = load_bias_module()
            # Store in dedicated cache slot, NOT _bias_module_internal, so
            # the setter contract (user-supplied vs auto-loaded) stays clear.
            self._bias_module_cached = loaded
            return loaded
        return None

    @property
    def representation_pipeline(self) -> Optional[RepresentationInterface]:
        return self._representation_internal

    @representation_pipeline.setter
    def representation_pipeline(self, value: Optional[RepresentationInterface]) -> None:
        self._representation_internal = value

    def enable_bias_module(self, enable: bool = True) -> None:
        self.enable_bias = enable
        if enable and self._bias_module_internal is None:
            self.init_bias_module()

    # ------------------------------------------------------------------
    # Plugin helpers
    # ------------------------------------------------------------------
    def add_plugin(
        self,
        plugin: Any,
        *,
        depends_on: Optional[Any] = None,
        before: Optional[Any] = None,
        after: Optional[Any] = None,
    ) -> "SolverBase":
        """Add plugin with explicit attach status tracking.
        
        Args:
            plugin: Plugin instance to add
            
        Returns:
            self for method chaining
            
        Raises:
            RuntimeError: In strict mode if attach fails
            
        Notes:
            - plugin_strict=True: attach failure raises exception immediately
            - plugin_strict=False (default): logs error, marks plugin as "attach_failed"
            - Plugin remains registered even if attach fails (for inspection)
            - Plugins with attach_failed=True will be skipped during lifecycle hooks
        """
        if bool(getattr(self, "running", False)):
            raise RuntimeError(
                "Cannot add plugin while solver is running. "
                "Register plugins during setup."
            )
        plugin_name = getattr(plugin, 'name', plugin.__class__.__name__)
        self.plugin_manager.register(plugin)
        self._plugin_scheduler.register_component(
            str(plugin_name),
            priority=int(getattr(plugin, "priority", 0) or 0),
        )

        declared_depends = getattr(plugin, "depends_on_plugins", None)
        declared_before = getattr(plugin, "before_plugins", None)
        declared_after = getattr(plugin, "after_plugins", None)
        apply_depends = depends_on if depends_on is not None else declared_depends
        apply_before = before if before is not None else declared_before
        apply_after = after if after is not None else declared_after
        try:
            self._plugin_scheduler.set_constraints(
                str(plugin_name),
                depends_on=apply_depends,
                before=apply_before,
                after=apply_after,
            )
            self._sync_plugin_execution_order()
        except Exception as exc:
            self.plugin_manager.unregister(str(plugin_name))
            self._plugin_scheduler.unregister_component(str(plugin_name))
            raise RuntimeError(
                f"Plugin '{plugin_name}' order constraints invalid: {exc}"
            ) from exc
        
        try:
            plugin.attach(self)
        except Exception as exc:
            error_msg = f"Plugin '{plugin_name}' attach failed: {exc}"
            
            if bool(getattr(self, "plugin_strict", False)):
                # Strict mode: unregister and raise
                self.plugin_manager.unregister(plugin_name)
                self._plugin_scheduler.unregister_component(str(plugin_name))
                raise RuntimeError(error_msg) from exc
            else:
                # Soft mode: mark as failed, log, continue
                plugin._attach_failed = True
                plugin._attach_error = str(exc)
                report_soft_error(
                    component="SolverBase",
                    event="plugin_attach",
                    exc=exc,
                    logger=logger,
                    context_store=self.context_store,
                    strict=False,
                    level="warning",  # Elevated from debug
                )
                logger.warning(
                    f"Plugin '{plugin_name}' registered but attach failed. "
                    f"It will be skipped during lifecycle hooks. Error: {exc}"
                )

        # Registration/attachment is assembly-time work.  ``on_solver_init`` is
        # a run lifecycle hook and is dispatched exactly once by ``run()``.
        
        return self

    def remove_plugin(self, plugin_name: str) -> None:
        if bool(getattr(self, "running", False)):
            raise RuntimeError(
                "Cannot remove plugin while solver is running."
            )
        self.plugin_manager.unregister(plugin_name)
        self._plugin_scheduler.unregister_component(str(plugin_name))
        self._sync_plugin_execution_order()

    def get_plugin(self, plugin_name: str) -> Any:
        return self.plugin_manager.get(plugin_name)

    def set_plugin_order(
        self,
        plugin_name: str,
        *,
        depends_on: Optional[Any] = None,
        before: Optional[Any] = None,
        after: Optional[Any] = None,
    ) -> None:
        self._set_plugin_order(
            plugin_name,
            depends_on=depends_on,
            before=before,
            after=after,
            allow_during_run=False,
        )

    def _set_plugin_order(
        self,
        plugin_name: str,
        *,
        depends_on: Optional[Any] = None,
        before: Optional[Any] = None,
        after: Optional[Any] = None,
        allow_during_run: bool,
    ) -> None:
        if bool(getattr(self, "running", False)) and not bool(allow_during_run):
            raise RuntimeError(
                "Cannot mutate plugin topology while solver is running. "
                "Use request_plugin_order() and let changes apply at the next generation boundary."
            )
        name = str(plugin_name)
        rules_backup = self._plugin_scheduler.snapshot_rules()
        try:
            self._plugin_scheduler.set_constraints(
                name,
                depends_on=depends_on,
                before=before,
                after=after,
            )
            self._sync_plugin_execution_order()
        except Exception:
            self._plugin_scheduler.restore_rules(rules_backup)
            self._sync_plugin_execution_order()
            raise

    def request_plugin_order(
        self,
        plugin_name: str,
        *,
        depends_on: Optional[Any] = None,
        before: Optional[Any] = None,
        after: Optional[Any] = None,
    ) -> None:
        self._pending_plugin_order_updates.append(
            {
                "plugin_name": str(plugin_name),
                "depends_on": depends_on,
                "before": before,
                "after": after,
            }
        )

    def _apply_pending_plugin_order_updates(self) -> None:
        pending = list(self._pending_plugin_order_updates)
        self._pending_plugin_order_updates.clear()
        for row in pending:
            self._set_plugin_order(
                row.get("plugin_name", ""),
                depends_on=row.get("depends_on"),
                before=row.get("before"),
                after=row.get("after"),
                allow_during_run=True,
            )

    def _sync_plugin_execution_order(self) -> None:
        order = self._plugin_scheduler.resolve_order_strict()
        self.plugin_manager.set_execution_order(order)

    def validate_plugin_order(self) -> None:
        try:
            self._sync_plugin_execution_order()
        except Exception as exc:
            raise RuntimeError(f"Plugin order validation failed: {exc}") from exc

    def validate_control_plane(self) -> None:
        try:
            self.runtime_controller.validate_configuration()
        except Exception as exc:
            raise RuntimeError(f"Runtime controller validation failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Control-plane wiring helpers (preferred over direct attribute writes)
    # ------------------------------------------------------------------
    def set_adapter(self, adapter: Any) -> None:
        setattr(self, "adapter", adapter)

    def set_strategy_controller(self, controller: Any) -> None:
        """Set a strategy controller adapter (serial or multi-strategy)."""
        setattr(self, "adapter", controller)

    def set_phase_controller(self, phases: Any, *, name: str = "serial_phase_controller") -> None:
        """Convenience: build a StrategyChainAdapter from phases."""
        try:
            from ..adapters.serial_strategy import StrategyChainAdapter, SerialPhaseSpec
        except Exception as exc:
            raise RuntimeError("StrategyChainAdapter is unavailable") from exc
        specs = []
        for item in phases:
            if isinstance(item, SerialPhaseSpec):
                specs.append(item)
                continue
            if isinstance(item, tuple) and len(item) >= 2:
                pname, adapter = item[0], item[1]
                steps = int(item[2]) if len(item) > 2 else -1
                specs.append(SerialPhaseSpec(name=str(pname), adapter=adapter, steps=steps))
                continue
            raise ValueError("phase entries must be SerialPhaseSpec or (name, adapter[, steps])")
        controller = StrategyChainAdapter(phases=specs, name=str(name))
        setattr(self, "adapter", controller)

    def set_bias_module(self, bias_module: Optional[BiasInterface], enable: Optional[bool] = None) -> None:
        self.bias_module = bias_module
        if enable is not None:
            self.enable_bias = bool(enable)
            if bool(enable) and bias_module is None:
                # Explicit enable with no provided module: init default if available.
                self.init_bias_module()
        elif bias_module is not None:
            self.enable_bias = True

    def set_bias_enabled(self, enable: bool) -> None:
        self.enable_bias = bool(enable)
        if bool(enable) and self._bias_module_internal is None and not hasattr(self, "_bias_module_cached"):
            self.init_bias_module()

    def set_representation_pipeline(self, pipeline: Optional[RepresentationInterface]) -> None:
        self.representation_pipeline = pipeline

    def has_bias_support(self) -> bool:
        if self._bias_module_internal is not None:
            return True
        return bool(has_bias_module())

    def has_numba_support(self) -> bool:
        return bool(has_numba())

    def register_controller(self, controller: BaseController) -> None:
        self.runtime_controller.register_controller(controller)

    def evaluation_batch_allowance(
        self,
        requested: int,
        *,
        context: Optional[Mapping[str, Any]] = None,
    ) -> int:
        """Return the controller-approved size for one evaluation batch."""
        requested_count = int(requested)
        if requested_count < 0:
            raise ValueError("requested evaluation count must be non-negative")
        with self._evaluation_budget.locked():
            ctx = dict(context) if context is not None else dict(self.build_context())
            ctx["evaluation_count"] = int(self.evaluation_count) + int(
                self._evaluation_budget.active_reserved
            )
            local_limit = int(
                self.runtime_controller.evaluation_allowance(
                    self,
                    requested=requested_count,
                    context=ctx,
                )
            )
            return self._evaluation_budget.allowance(
                requested_count,
                local_limit=local_limit,
            )

    def reserve_evaluation_batch(
        self,
        requested: int,
        *,
        context: Optional[Mapping[str, Any]] = None,
    ) -> BudgetClaim:
        """Atomically reserve hard-budget capacity before evaluation starts."""
        requested_count = int(requested)
        if requested_count < 0:
            raise ValueError("requested evaluation count must be non-negative")
        with self._evaluation_budget.locked():
            allowed = self.evaluation_batch_allowance(requested_count, context=context)
            if allowed < requested_count:
                raise EvaluationBudgetExceeded(
                    "evaluation request exceeds the remaining hard budget: "
                    f"requested={requested_count}, allowed={allowed}, "
                    f"evaluation_count={int(self.evaluation_count)}"
                )
            try:
                return self._evaluation_budget.reserve(requested_count)
            except SharedBudgetExceeded as exc:
                raise EvaluationBudgetExceeded(str(exc)) from exc

    def complete_evaluation_batch(
        self,
        claim: BudgetClaim,
    ) -> None:
        """Close a claim after every dispatched unit has been consumed."""

        self._evaluation_budget.complete(claim)

    def consume_evaluation_batch(
        self,
        claim: BudgetClaim,
        amount: int = 1,
    ) -> None:
        """Commit units immediately before evaluation work is dispatched."""

        consumed_now = int(amount)
        if consumed_now < 0:
            raise ValueError("consumed evaluation count must be non-negative")
        if consumed_now == 0:
            return
        with self._evaluation_budget.locked():
            self._evaluation_budget.consume(claim, consumed_now)
            self.increment_evaluation_count(consumed_now)

    def cancel_evaluation_batch(
        self,
        claim: BudgetClaim,
    ) -> None:
        """Release capacity after a failed or cancelled evaluation batch."""

        self._evaluation_budget.cancel(claim)

    def _evaluate_population_with_budget_retry(
        self,
        population: Any,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, bool]:
        """Converge a lifecycle-owned batch after losing a shared-budget race.

        Direct ``evaluate_population`` calls remain strict. Solver lifecycle
        code may use this helper to shrink a batch to the newly visible global
        allowance or stop cleanly when another Case won the final units.
        """

        current = np.asarray(population, dtype=float)
        if current.ndim == 1:
            current = current.reshape(1, -1) if current.size else current.reshape(0, self.dimension)
        truncated = False
        while int(current.shape[0]) > 0:
            try:
                objectives, violations = self.evaluate_population(current)
                if len(self._active_candidate_provenance) >= int(current.shape[0]):
                    self._active_candidate_provenance = (
                        self._active_candidate_provenance[: int(current.shape[0])]
                    )
                return current, objectives, violations, truncated
            except EvaluationBudgetExceeded:
                allowed = self.evaluation_batch_allowance(int(current.shape[0]))
                if allowed >= int(current.shape[0]):
                    raise
                truncated = True
                current = current[: max(0, int(allowed))]
                self._active_candidate_provenance = (
                    self._active_candidate_provenance[: max(0, int(allowed))]
                )
        return (
            np.empty((0, int(self.dimension)), dtype=float),
            np.empty((0, int(self.num_objectives)), dtype=float),
            np.empty((0,), dtype=float),
            truncated,
        )

    def register_evaluation_provider(self, provider: EvaluationProvider) -> None:
        self.evaluation_mediator.register_provider(provider)

    def unregister_evaluation_provider(self, provider: Any) -> None:
        self.evaluation_mediator.unregister_provider(provider)

    def configure_evaluation_policy(
        self,
        *,
        allow_approximate: bool | None = None,
        strict_conflict: bool | None = None,
    ) -> None:
        """Configure provider-selection semantics through the control plane."""

        self.evaluation_mediator.configure_policy(
            allow_approximate=allow_approximate,
            strict_conflict=strict_conflict,
        )

    def register_acceleration_backend(self, *, scope: str, backend: str, factory: Any) -> None:
        if not callable(factory):
            raise TypeError("acceleration backend factory must be callable")

        def resource_bound_factory(*args: Any, **kwargs: Any) -> Any:
            self._validate_acceleration_backend_against_resource_context(backend)
            instance = factory(*args, **kwargs)
            if hasattr(instance, "max_workers"):
                requested = getattr(instance, "max_workers", None)
                setattr(
                    instance,
                    "max_workers",
                    self.limit_workers_by_resource_context(requested),
                )
            return instance

        self.accel.register(scope=scope, backend=backend, factory=resource_bound_factory)

    def get_acceleration_backend(self, *, scope: str, backend: str = "default", **kwargs: Any) -> Any:
        return self.accel.get(scope=scope, backend=backend, **kwargs)

    def set_acceleration_default_backend(self, *, scope: str, backend: str) -> None:
        self._validate_acceleration_backend_against_resource_context(backend)
        self._accel_default_backends[str(scope)] = str(backend)

    def get_acceleration_default_backend(self, *, scope: str) -> Optional[str]:
        return self._accel_default_backends.get(str(scope))

    def accel_run(
        self,
        *,
        scope: str,
        task: str,
        payload: Mapping[str, Any],
        backend: Optional[str] = None,
        hints: Optional[Mapping[str, Any]] = None,
        context: Optional[Mapping[str, Any]] = None,
        inline_if_missing: bool = True,
    ) -> ExecutionResult:
        chosen = backend if backend is not None else self.get_acceleration_default_backend(scope=scope)
        if chosen is None and inline_if_missing:
            return maybe_accel_run(
                solver=self,
                scope=scope,
                task=task,
                payload=payload,
                backend=None,
                hints=hints,
                context=context,
            )
        return self.accel.run(
            scope=scope,
            task=task,
            payload=payload,
            backend=chosen,
            hints=hints,
            context=context,
        )

    def accel_map(
        self,
        *,
        scope: str,
        task: str,
        items: Iterable[Any],
        call: Any,
        backend: Optional[str] = None,
        hints: Optional[Mapping[str, Any]] = None,
        context: Optional[Mapping[str, Any]] = None,
        inline_if_missing: bool = True,
    ) -> ExecutionResult:
        chosen = backend if backend is not None else self.get_acceleration_default_backend(scope=scope)
        if chosen is None and inline_if_missing:
            return maybe_accel_map(
                solver=self,
                scope=scope,
                task=task,
                items=items,
                call=call,
                backend=None,
                hints=hints,
                context=context,
            )
        return self.accel.map(
            scope=scope,
            task=task,
            items=items,
            call=call,
            backend=chosen,
            hints=hints,
            context=context,
        )

    def accel_submit(
        self,
        *,
        scope: str,
        task: str,
        payload: Mapping[str, Any],
        backend: Optional[str] = None,
        hints: Optional[Mapping[str, Any]] = None,
        context: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        chosen = backend if backend is not None else self.get_acceleration_default_backend(scope=scope)
        if chosen is None:
            raise ValueError("accel_submit requires an explicit backend or a configured default backend")
        return self.accel.submit(
            scope=scope,
            task=task,
            payload=payload,
            backend=chosen,
            hints=hints,
            context=context,
        )

    def accel_map_async(
        self,
        *,
        scope: str,
        task: str,
        items: Iterable[Any],
        call: Any,
        backend: Optional[str] = None,
        hints: Optional[Mapping[str, Any]] = None,
        context: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        chosen = backend if backend is not None else self.get_acceleration_default_backend(scope=scope)
        if chosen is None:
            raise ValueError("accel_map_async requires an explicit backend or a configured default backend")
        return self.accel.map_async(
            scope=scope,
            task=task,
            items=items,
            call=call,
            backend=chosen,
            hints=hints,
            context=context,
        )

    def set_max_steps(self, max_steps: int) -> None:
        self.max_steps = int(max_steps)

    def set_max_step_attempts(self, max_step_attempts: int | None) -> None:
        self.max_step_attempts = (
            None
            if max_step_attempts is None
            else max(0, int(max_step_attempts))
        )

    def set_max_consecutive_idle_attempts(
        self,
        max_consecutive_idle_attempts: int | None,
    ) -> None:
        self.max_consecutive_idle_attempts = (
            None
            if max_consecutive_idle_attempts is None
            else max(0, int(max_consecutive_idle_attempts))
        )

    def set_legacy_step_outcome_compatibility(self, enabled: bool) -> None:
        """Explicitly opt into the temporary legacy outcome converter."""

        self.allow_legacy_step_outcomes = bool(enabled)

    def set_generation(self, generation: int) -> int:
        return set_generation_value(self, generation)

    def increment_evaluation_count(self, delta: int = 1) -> int:
        return increment_evaluation_counter(
            self,
            delta,
            report_soft_error_fn=report_soft_error,
            logger=logger,
        )

    @staticmethod
    def _candidate_serialized_size_bytes(candidate: Any) -> int:
        payload = json.dumps(
            np.asarray(candidate, dtype=float).reshape(-1).tolist(),
            ensure_ascii=False,
            allow_nan=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return len(payload)

    def _candidate_can_inline_in_context(self, candidate: Any) -> bool:
        limit = max(0, int(getattr(self, "context_inline_candidate_max_bytes", 0)))
        return self._candidate_serialized_size_bytes(candidate) <= limit

    @staticmethod
    def _apply_context_projection_patch(
        target: Any,
        values: Mapping[str, Any],
        delete_keys: Iterable[str],
    ) -> None:
        if target is None:
            return
        normalized_values = {str(key): value for key, value in values.items()}
        normalized_deletes = tuple(str(key) for key in delete_keys)
        if isinstance(target, dict):
            for key in normalized_deletes:
                target.pop(key, None)
            target.update(normalized_values)
            return
        apply_patch = getattr(target, "apply_patch", None)
        if bool(getattr(target, "supports_atomic_patch", False)) and callable(
            apply_patch
        ):
            apply_patch(normalized_values, delete_keys=normalized_deletes)
            return
        raise RuntimeError(
            "incumbent Context projection requires atomic apply_patch support"
        )

    def _incumbent_projection_patch(
        self,
        commit: _IncumbentCommit,
    ) -> tuple[Dict[str, Any], tuple[str, ...]]:
        state = commit.state
        if state is None:
            return {}, (
                KEY_BEST_X,
                KEY_BEST_CANDIDATE_REF,
                KEY_BEST_OBJECTIVE,
            )
        values: Dict[str, Any] = {KEY_BEST_OBJECTIVE: float(state.score)}
        if self._candidate_can_inline_in_context(state.candidate):
            values[KEY_BEST_X] = state.candidate.copy()
            return values, (KEY_BEST_CANDIDATE_REF,)
        if commit.candidate_ref:
            values[KEY_BEST_CANDIDATE_REF] = commit.candidate_ref
        return values, (KEY_BEST_X,) if commit.candidate_ref else (
            KEY_BEST_X,
            KEY_BEST_CANDIDATE_REF,
        )

    def _publish_incumbent_context(self, commit: _IncumbentCommit) -> bool:
        values, delete_keys = self._incumbent_projection_patch(commit)
        try:
            self._apply_context_projection_patch(
                getattr(self, "context_store", None),
                values,
                delete_keys,
            )
        except Exception as exc:
            self._incumbent_context_projection_error = {
                "revision": int(commit.revision),
                "error_type": exc.__class__.__name__,
                "message": str(exc),
            }
            report_soft_error(
                component="SolverBase",
                event="incumbent_context_projection",
                exc=exc,
                logger=logger,
                context_store=getattr(self, "context_store", None),
                strict=False,
            )
            return False
        self._incumbent_context_projection_revision = int(commit.revision)
        self._incumbent_context_projection_error = None
        return True

    def _incumbent_projection_audit_locked(self) -> Dict[str, Any]:
        incumbent_revision = int(self._incumbent_commit.revision)
        projection_revision = int(self._incumbent_context_projection_revision)
        projection_error = self._incumbent_context_projection_error
        current = (
            projection_revision == incumbent_revision
            and projection_error is None
        )
        return {
            "incumbent_revision": incumbent_revision,
            "incumbent_context_projection_revision": projection_revision,
            "incumbent_context_projection_current": bool(current),
            "incumbent_context_projection_error": (
                None if projection_error is None else dict(projection_error)
            ),
        }

    def get_incumbent_projection_audit(self) -> Dict[str, Any]:
        """Return transport-safe evidence about ContextStore publication."""

        with self._incumbent_lock:
            return self._incumbent_projection_audit_locked()

    def _record_restored_incumbent_projection_audit(
        self,
        audit: Optional[Mapping[str, Any]],
    ) -> None:
        """Keep saved publication evidence separate from the new live store."""

        with self._incumbent_lock:
            self._restored_incumbent_projection_audit = (
                None if audit is None else dict(audit)
            )

    def _persist_candidate_snapshot(
        self,
        candidate: Any,
        *,
        meta: Optional[Mapping[str, Any]] = None,
    ) -> Optional[str]:
        store = getattr(self, "snapshot_store", None)
        if store is None:
            if bool(getattr(self, "snapshot_strict", False)):
                raise RuntimeError(
                    "strict incumbent candidate persistence requires a SnapshotStore"
                )
            return None
        key = make_snapshot_key(
            prefix="incumbent",
            generation=int(getattr(self, "generation", 0)),
            suffix="best-candidate",
        )
        metadata = {
            **dict(meta or {}),
            "serialized_size_bytes": self._candidate_serialized_size_bytes(
                candidate
            ),
        }
        try:
            handle = store.write(
                {KEY_BEST_X: np.asarray(candidate, dtype=float).reshape(-1).copy()},
                key=key,
                meta=metadata,
                schema="nsgablack.incumbent_candidate.v1",
                ttl_seconds=self.snapshot_store_ttl_seconds,
            )
        except Exception as exc:
            report_soft_error(
                component="SolverBase",
                event="incumbent_candidate_snapshot_write",
                exc=exc,
                logger=logger,
                context_store=self.context_store,
                strict=bool(getattr(self, "snapshot_strict", False)),
            )
            return None
        return str(handle.key)

    def _persist_incumbent_candidate(self, state: IncumbentState) -> Optional[str]:
        return self._persist_candidate_snapshot(
            state.candidate,
            meta={
                "active_run_id": self._active_run_id,
                "evaluation_id": state.evaluation_id,
                "candidate_token": state.candidate_token,
            },
        )

    def _discard_staged_incumbent_candidate(self, candidate_ref: str) -> None:
        store = getattr(self, "snapshot_store", None)
        delete = getattr(store, "delete", None)
        if not callable(delete):
            return
        try:
            delete(str(candidate_ref))
        except Exception as exc:
            report_soft_error(
                component="SolverBase",
                event="incumbent_candidate_snapshot_discard",
                exc=exc,
                logger=logger,
                context_store=self.context_store,
                strict=False,
            )

    def project_incumbent_context(self, target: Any) -> None:
        """Project only bounded incumbent data or a SnapshotStore reference."""

        with self._incumbent_lock:
            commit = self._incumbent_commit
        values, delete_keys = self._incumbent_projection_patch(commit)
        self._apply_context_projection_patch(target, values, delete_keys)

    def get_incumbent(self) -> IncumbentState | None:
        """Return the complete authoritative incumbent for the active run."""

        with self._incumbent_lock:
            return self._incumbent_commit.state

    def export_incumbent_checkpoint_state(self) -> Dict[str, Any]:
        """Export incumbent and selection audit from one locked state view."""

        with self._incumbent_lock:
            incumbent = self._incumbent_commit.state
            policy_context = dict(
                getattr(
                    self,
                    "incumbent_scalarizer_context",
                    getattr(incumbent, "policy_context", {}) if incumbent else {},
                )
                or {}
            )
            return {
                "incumbent": None if incumbent is None else incumbent.as_dict(),
                "incumbent_projection": self._incumbent_projection_audit_locked(),
                "incumbent_selection": {
                    "policy_id": str(
                        getattr(
                            self,
                            "incumbent_scalarizer_id",
                            getattr(
                                incumbent,
                                "policy_id",
                                DEFAULT_INCUMBENT_POLICY_ID,
                            ),
                        )
                    ),
                    "policy_context": policy_context,
                    "failure_policy": getattr(
                        self,
                        "scalarizer_failure_policy",
                        "raise",
                    ),
                    "fallback_count": int(
                        getattr(self, "scalarizer_fallback_count", 0) or 0
                    ),
                    "result_quality_degraded": getattr(
                        self,
                        "result_quality_degraded",
                        False,
                    ),
                    "audit_complete": bool(
                        getattr(self, "scalarizer_audit_complete", True)
                    ),
                },
            }

    def _capture_incumbent_transaction_state(self) -> Dict[str, Any]:
        """Capture every mutable projection of the atomic incumbent commit."""

        with self._incumbent_lock:
            return {
                "commit": self._incumbent_commit,
                "incumbent": self._incumbent,
                "best_x": None if self.best_x is None else self.best_x.copy(),
                "best_objectives": (
                    None
                    if self.best_objectives is None
                    else self.best_objectives.copy()
                ),
                "best_constraint_violation": self.best_constraint_violation,
                "best_score": self.best_score,
                "best_objective": self.best_objective,
                "best_f": self.best_f,
                "candidate_ref": self._incumbent_candidate_ref,
                "projection_revision": self._incumbent_context_projection_revision,
                "projection_error": (
                    None
                    if self._incumbent_context_projection_error is None
                    else dict(self._incumbent_context_projection_error)
                ),
            }

    def _restore_incumbent_transaction_state(
        self,
        state: Mapping[str, Any],
    ) -> None:
        """Restore a pre-step incumbent and republish its Context projection."""

        staged_ref: str | None = None
        with self._incumbent_lock:
            current_ref = self._incumbent_candidate_ref
            previous_ref = state.get("candidate_ref")
            if current_ref and current_ref != previous_ref:
                staged_ref = str(current_ref)
            self._incumbent_commit = state["commit"]
            self._incumbent = state.get("incumbent")
            best_x = state.get("best_x")
            best_objectives = state.get("best_objectives")
            self.best_x = (
                None if best_x is None else np.array(best_x, dtype=float, copy=True)
            )
            self.best_objectives = (
                None
                if best_objectives is None
                else np.array(best_objectives, dtype=float, copy=True)
            )
            self.best_constraint_violation = state.get(
                "best_constraint_violation"
            )
            self.best_score = state.get("best_score")
            self.best_objective = state.get("best_objective")
            self.best_f = state.get("best_f")
            self._incumbent_candidate_ref = (
                None if previous_ref is None else str(previous_ref)
            )
            self._incumbent_context_projection_revision = int(
                state.get("projection_revision", -1)
            )
            projection_error = state.get("projection_error")
            self._incumbent_context_projection_error = (
                None
                if projection_error is None
                else dict(projection_error)
            )
            self._publish_incumbent_context(self._incumbent_commit)
        if staged_ref is not None:
            self._discard_staged_incumbent_candidate(staged_ref)

    def _validate_incumbent_commit(self, state: IncumbentState) -> None:
        """Validate a state before artifact staging and again before commit."""

        if not isinstance(state, IncumbentState):
            raise TypeError("incumbent commit requires an IncumbentState")

    def set_incumbent(
        self,
        incumbent: IncumbentState | Mapping[str, Any],
    ) -> IncumbentState:
        """Stage required artifacts, then commit one authoritative incumbent."""

        state = (
            incumbent
            if isinstance(incumbent, IncumbentState)
            else IncumbentState.from_dict(incumbent)
        )
        self._validate_incumbent_commit(state)
        best_x = state.candidate.copy()
        best_objectives = state.objectives.copy()
        candidate_ref: Optional[str] = None
        if not self._candidate_can_inline_in_context(state.candidate):
            candidate_ref = self._persist_incumbent_candidate(state)
        try:
            with self._incumbent_lock:
                # Snapshot persistence runs without the incumbent lock.  Recheck
                # here so a concurrent selection-policy change cannot commit a
                # state that was valid only at the beginning of staging.
                self._validate_incumbent_commit(state)
                commit = _IncumbentCommit(
                    state=state,
                    candidate_ref=candidate_ref,
                    revision=int(self._incumbent_commit.revision) + 1,
                )
                self.best_x = best_x
                self.best_objectives = best_objectives
                self.best_constraint_violation = state.constraint_violation
                self.best_score = state.score
                self.best_objective = state.score
                self.best_f = state.score
                self._incumbent = state
                self._incumbent_candidate_ref = candidate_ref
                self._incumbent_commit = commit
                self._publish_incumbent_context(commit)
        except Exception:
            if candidate_ref:
                self._discard_staged_incumbent_candidate(candidate_ref)
            raise
        return state

    def clear_incumbent(self) -> None:
        """Clear the atomic incumbent and every derived projection."""

        with self._incumbent_lock:
            commit = _IncumbentCommit(
                state=None,
                candidate_ref=None,
                revision=int(self._incumbent_commit.revision) + 1,
            )
            self._incumbent = None
            self.best_x = None
            self.best_objectives = None
            self.best_constraint_violation = None
            self.best_score = None
            self.best_objective = None
            self.best_f = None
            self._incumbent_candidate_ref = None
            self._incumbent_commit = commit
            self._publish_incumbent_context(commit)

    def set_warm_start(
        self,
        candidate: Any | IncumbentState,
        *,
        source_run_id: str | None = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> "SolverBase":
        """Queue a seed candidate for reevaluation in the next fresh run.

        Even when an ``IncumbentState`` is supplied, its old objectives and
        score are not trusted as facts of the new run.  The candidate must pass
        through the normal evaluation path before it can become authoritative.
        """

        if isinstance(candidate, IncumbentState):
            source_run_id = source_run_id or candidate.source_run_id
            seed = candidate.candidate
            inherited = {
                "source_evaluation_id": candidate.evaluation_id,
                "source_policy_id": candidate.policy_id,
                **dict(candidate.metadata),
                **dict(metadata or {}),
            }
        else:
            seed = candidate
            inherited = dict(metadata or {})
        if isinstance(seed, UnknownState):
            inherited[_SEMANTIC_METADATA_KEY] = encode_shared_value(
                dict(seed.metadata),
                path="warm_start.semantic_metadata",
            )
        seed_array = normalize_candidate(
            seed,
            dimension=self.dimension,
            name="warm_start.candidate",
        ).copy()
        warm_start_id = f"warm-start:{uuid.uuid4().hex}"
        self._pending_warm_starts.append(
            {
                "candidate": seed_array,
                "source_run_id": None if source_run_id is None else str(source_run_id),
                "warm_start_id": warm_start_id,
                "metadata": inherited,
            }
        )
        return self

    def _new_candidate_provenance(
        self,
        *,
        source_kind: str = "evaluation",
        source_run_id: Optional[str] = None,
        warm_start_id: Optional[str] = None,
        proposal_id: Optional[str] = None,
        parent_token: Optional[str] = None,
        transform_stage: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> CandidateProvenance:
        self._candidate_sequence = int(self._candidate_sequence) + 1
        token_scope = self._active_run_id or "unscoped"
        token = (
            f"{token_scope}:candidate:{self._candidate_sequence}:"
            f"{uuid.uuid4().hex[:8]}"
        )
        return CandidateProvenance(
            candidate_token=token,
            source_kind=source_kind,
            source_run_id=source_run_id,
            warm_start_id=warm_start_id,
            proposal_id=proposal_id,
            parent_token=parent_token,
            transform_stage=transform_stage,
            metadata=dict(metadata or {}),
        )

    def _register_candidate_provenance(
        self,
        candidate: Any,
        provenance: CandidateProvenance,
    ) -> None:
        array = (
            candidate.values
            if isinstance(candidate, UnknownState)
            else np.asarray(candidate)
        )
        object_id = id(array)
        solver_ref = weakref.ref(self)

        def _cleanup(reference: weakref.ReferenceType[np.ndarray]) -> None:
            solver = solver_ref()
            if solver is None:
                return
            with solver._candidate_provenance_lock:
                current = solver._candidate_provenance_by_object.get(object_id)
                if current is not None and current[0] is reference:
                    solver._candidate_provenance_by_object.pop(object_id, None)

        try:
            reference = weakref.ref(array, _cleanup)
        except TypeError:
            return
        with self._candidate_provenance_lock:
            self._candidate_provenance_by_object[object_id] = (
                reference,
                provenance,
            )

    def _lookup_candidate_provenance(
        self,
        candidate: Any,
    ) -> Optional[CandidateProvenance]:
        current = (
            candidate.values
            if isinstance(candidate, UnknownState)
            else np.asarray(candidate)
        )
        # A row view has a fresh Python object ID, but an exact memory relation
        # to the active batch. Resolve only that relation, never equal numbers
        # or a standalone evaluation's ordinal (which may name an older row).
        reference = self._active_candidate_population_ref
        active = None if reference is None else reference()
        if (active is not None and active.ndim == 2 and current.ndim == 1
                and current.shape == active.shape[1:] and current.dtype == active.dtype
                and current.strides == active.strides[1:] and active.strides[0] != 0
                and len(self._active_candidate_provenance) == len(active)
                and np.shares_memory(current, active)):
            offset = current.ctypes.data - active.ctypes.data
            row, remainder = divmod(offset, active.strides[0])
            if remainder == 0 and 0 <= row < len(active):
                return self._active_candidate_provenance[row]
        visited: set[int] = set()
        while isinstance(current, np.ndarray) and id(current) not in visited:
            object_id = id(current)
            visited.add(object_id)
            with self._candidate_provenance_lock:
                entry = self._candidate_provenance_by_object.get(object_id)
            if entry is not None:
                reference, provenance = entry
                if reference() is current:
                    return provenance
                with self._candidate_provenance_lock:
                    latest = self._candidate_provenance_by_object.get(object_id)
                    if latest is entry:
                        self._candidate_provenance_by_object.pop(object_id, None)
            base = getattr(current, "base", None)
            if not isinstance(base, np.ndarray):
                break
            current = base
        return None

    def prepare_candidate_provenance(
        self,
        candidates: Iterable[Any],
    ) -> list[CandidateProvenance]:
        """Assign one stable token to each proposed row before repair/evaluation."""

        self._proposal_sequence = int(self._proposal_sequence) + 1
        proposal_id = (
            f"{self._active_run_id or 'unscoped'}:proposal:"
            f"{self._proposal_sequence}"
        )
        out: list[CandidateProvenance] = []
        for candidate in candidates:
            provenance = self._lookup_candidate_provenance(candidate)
            if provenance is None:
                provenance = self._new_candidate_provenance(
                    source_kind="evaluation",
                    source_run_id=self._active_run_id,
                    proposal_id=proposal_id,
                )
            elif provenance.proposal_id is None:
                provenance = CandidateProvenance(
                    candidate_token=provenance.candidate_token,
                    source_kind=provenance.source_kind,
                    source_run_id=provenance.source_run_id,
                    warm_start_id=provenance.warm_start_id,
                    proposal_id=proposal_id,
                    parent_token=provenance.parent_token,
                    transform_stage=provenance.transform_stage,
                    metadata=provenance.metadata,
                )
            if isinstance(candidate, UnknownState):
                provenance = self._with_candidate_semantics(provenance, candidate)
            self._register_candidate_provenance(candidate, provenance)
            out.append(provenance)
        return out

    @staticmethod
    def _with_candidate_semantics(
        provenance: CandidateProvenance,
        state: UnknownState,
    ) -> CandidateProvenance:
        metadata = dict(provenance.metadata)
        metadata[_SEMANTIC_METADATA_KEY] = encode_shared_value(
            dict(state.metadata),
            path="candidate.semantic_metadata",
        )
        return CandidateProvenance(
            candidate_token=provenance.candidate_token,
            source_kind=provenance.source_kind,
            source_run_id=provenance.source_run_id,
            warm_start_id=provenance.warm_start_id,
            proposal_id=provenance.proposal_id,
            parent_token=provenance.parent_token,
            transform_stage=provenance.transform_stage,
            metadata=metadata,
        )

    def bind_candidate_batch(
        self,
        batch: CandidateBatch,
        provenance: Iterable[CandidateProvenance],
        *,
        activate: bool = True,
    ) -> tuple[list[np.ndarray], list[CandidateProvenance]]:
        """Bind both CandidateBatch views to the same stable candidate tokens."""

        records = list(provenance)
        refs = self.store_solutions(batch, stage="proposal", provenance=records)
        if refs:
            batch = self.solution_pool.read(refs, allow_pending=True)
        rows = list(batch.numeric_rows())
        if len(rows) != len(records):
            raise ValueError("candidate batch provenance must align with candidate rows")
        semantic_records = [
            self._with_candidate_semantics(record, state)
            for record, state in zip(records, batch.semantic_states)
        ]
        self.bind_candidate_provenance(rows, semantic_records, activate=activate)
        return rows, semantic_records

    def get_candidate_population_batch(self) -> CandidateBatch | None:
        """Return the authoritative semantic/numeric population view."""

        return self._candidate_population_batch

    def get_candidate_population_provenance(self) -> tuple[CandidateProvenance, ...]:
        """Return lineage aligned with :meth:`get_candidate_population_batch`."""

        return tuple(self._candidate_population_provenance)

    def _materialize_candidate_population(
        self,
        population: Any,
        candidate_tokens: Iterable[str | None] | None,
        *,
        sources: Iterable[
            tuple[CandidateBatch | None, Iterable[CandidateProvenance]]
        ] = (),
    ) -> tuple[CandidateBatch, tuple[CandidateProvenance, ...]]:
        """Build one token-aligned semantic population without committing it.

        Numeric Adapters remain free to own selection arrays, but any selected
        semantic row must name the token it selected.  This prevents equal
        numeric rows with different metadata from being rebound by value.
        """

        matrix = np.asarray(population, dtype=float)
        if matrix.ndim == 1:
            matrix = matrix.reshape(1, -1) if matrix.size else matrix.reshape(0, 0)
        if matrix.ndim != 2:
            raise ValueError("candidate population matrix must be two-dimensional")
        if matrix.shape[1] != int(self.dimension) and matrix.shape[0] > 0:
            raise ValueError(
                "candidate population dimension mismatch: "
                f"expected={self.dimension}, actual={matrix.shape[1]}"
            )

        source_by_token: dict[str, tuple[UnknownState, CandidateProvenance]] = {}
        has_semantic_metadata = False
        for batch, provenance_values in tuple(sources):
            if batch is None:
                continue
            records = tuple(provenance_values)
            if len(records) != len(batch.semantic_states):
                raise ValueError("candidate population source lineage is misaligned")
            for state, record, token in zip(
                batch.semantic_states,
                records,
                batch.candidate_tokens,
            ):
                has_semantic_metadata = has_semantic_metadata or bool(state.metadata)
                effective_token = token or record.candidate_token
                if effective_token != record.candidate_token:
                    raise ValueError("candidate batch token disagrees with provenance token")
                previous = source_by_token.get(record.candidate_token)
                if previous is not None:
                    previous_state, _ = previous
                    if (
                        not np.array_equal(
                            previous_state.as_array(),
                            state.as_array(),
                            equal_nan=True,
                        )
                        or previous_state.as_dict()["metadata"]
                        != state.as_dict()["metadata"]
                    ):
                        raise ValueError(
                            "one candidate token identifies multiple semantic states: "
                            f"{record.candidate_token}"
                        )
                source_by_token[record.candidate_token] = (state, record)

        raw_tokens = (
            (None,) * int(matrix.shape[0])
            if candidate_tokens is None
            else tuple(candidate_tokens)
        )
        if len(raw_tokens) != int(matrix.shape[0]):
            raise ValueError("candidate population tokens must align with population rows")

        # Setup-initialized members may be absent from the latest evaluation
        # and previous population window. Resolve explicit identities from the
        # pool; never manufacture replacement identities for those members.
        missing = tuple(dict.fromkeys(token for token in raw_tokens
                                      if token is not None and token not in source_by_token))
        if missing:
            latest = {ref.candidate_token: ref for ref in self.solution_pool.refs_for_tokens(missing)}
            refs = tuple(latest[token] for token in missing)
            values = self.solution_pool.read_provenance(refs, allow_pending=True)
            if any(value is None for value in values):
                raise ValueError("population candidate pool source is missing provenance")
            pooled = self.solution_pool.read(refs, allow_pending=True)
            for token, state, value in zip(missing, pooled.semantic_states, values):
                record = CandidateProvenance.from_dict(value)
                if record.candidate_token != token:
                    raise ValueError("population pool provenance disagrees with token")
                source_by_token[token] = state, record
                has_semantic_metadata = has_semantic_metadata or bool(state.metadata)

        states: list[UnknownState] = []
        records: list[CandidateProvenance] = []
        normalized_tokens: list[str] = []
        for index, (row, raw_token) in enumerate(zip(matrix, raw_tokens)):
            token = None if raw_token is None else str(raw_token).strip() or None
            source = None if token is None else source_by_token.get(token)
            if source is None and has_semantic_metadata:
                raise ValueError(
                    "semantic population selection must preserve candidate tokens; "
                    f"row {index} has token={token!r}"
                )
            if source is None:
                record = self._new_candidate_provenance(
                    source_kind="adapter_population",
                    source_run_id=self._active_run_id,
                )
                state = UnknownState(values=row, metadata={})
            else:
                source_state, record = source
                if not np.array_equal(
                    source_state.as_array(),
                    np.asarray(row, dtype=float).reshape(-1),
                    equal_nan=True,
                ):
                    raise ValueError(
                        "candidate token was reused for different numeric values: "
                        f"{record.candidate_token}"
                    )
                state = UnknownState(values=row, metadata=dict(source_state.metadata))
                # Slot membership is not a new candidate proposal. Multiple
                # slots or partitions can retain the same semantic identity.
            states.append(state)
            records.append(record)
            normalized_tokens.append(record.candidate_token)

        batch = CandidateBatch(
            semantic_states=tuple(states),
            numeric_matrix=matrix,
            candidate_tokens=tuple(normalized_tokens),
        )
        return batch, tuple(records)

    def commit_candidate_population(
        self,
        population: Any,
        candidate_tokens: Iterable[str | None] | None,
        *,
        sources: Iterable[
            tuple[CandidateBatch | None, Iterable[CandidateProvenance]]
        ] = (),
    ) -> CandidateBatch:
        """Commit one token-aligned population without guessing semantic identity."""

        batch, records = self._materialize_candidate_population(
            population,
            candidate_tokens,
            sources=sources,
        )
        self._candidate_population_batch = batch
        self._candidate_population_provenance = records
        self.bind_candidate_provenance(
            batch.numeric_matrix,
            records,
            activate=True,
        )
        return batch

    def export_candidate_population_checkpoint_state(self) -> dict[str, Any] | None:
        batch = self._candidate_population_batch
        if batch is None:
            return None
        return {
            "batch": batch.as_dict(),
            "provenance": [
                item.as_dict() for item in self._candidate_population_provenance
            ],
        }

    def restore_candidate_population_checkpoint_state(
        self,
        payload: Mapping[str, Any] | None,
    ) -> None:
        if not isinstance(payload, Mapping):
            self._candidate_population_batch = None
            self._candidate_population_provenance = ()
            return
        batch_payload = payload.get("batch")
        if not isinstance(batch_payload, Mapping):
            raise ValueError("candidate population checkpoint is missing its batch")
        batch = CandidateBatch.from_dict(batch_payload)
        raw_records = tuple(payload.get("provenance", ()) or ())
        if len(raw_records) != len(batch.semantic_states):
            raise ValueError("candidate population checkpoint lineage is misaligned")
        records = tuple(
            item
            if isinstance(item, CandidateProvenance)
            else CandidateProvenance.from_dict(item)
            for item in raw_records
        )
        for token, record in zip(batch.candidate_tokens, records):
            if token != record.candidate_token:
                raise ValueError(
                    "candidate population checkpoint token disagrees with lineage"
                )
        self._candidate_population_batch = batch
        self._candidate_population_provenance = records
        population = getattr(self, "population", None)
        if population is not None:
            values = np.asarray(population, dtype=float)
            if values.shape != batch.numeric_matrix.shape or not np.array_equal(
                values,
                batch.numeric_matrix,
                equal_nan=True,
            ):
                raise ValueError(
                    "candidate population checkpoint disagrees with numeric population"
                )
            self.bind_candidate_provenance(values, records, activate=True)

    def semantic_candidate_state(
        self,
        candidate: Any,
        *,
        candidate_index: int | None = None,
    ) -> UnknownState:
        """Resolve the semantic view associated with one numeric candidate row."""

        provenance = self.candidate_provenance_for(
            candidate,
            candidate_index=candidate_index,
        )
        metadata: dict[str, Any] = {}
        if provenance is not None:
            raw = provenance.metadata.get(_SEMANTIC_METADATA_KEY, {})
            if isinstance(raw, Mapping):
                decoded = decode_shared_value(dict(raw))
                metadata = dict(decoded) if isinstance(decoded, Mapping) else {}
        return UnknownState(
            values=np.asarray(candidate, dtype=float).reshape(-1).copy(),
            metadata=metadata,
        )

    def candidate_provenance_for(
        self,
        candidate: Any,
        *,
        candidate_index: int | None = None,
    ) -> CandidateProvenance | None:
        if candidate_index is not None:
            index = int(candidate_index)
            if 0 <= index < len(self._active_candidate_provenance):
                return self._active_candidate_provenance[index]
        return self._lookup_candidate_provenance(candidate)

    def bind_candidate_provenance(
        self,
        candidates: Iterable[Any],
        provenance: Iterable[CandidateProvenance],
        *,
        activate: bool = True,
    ) -> list[CandidateProvenance]:
        candidate_values = list(candidates)
        provenance_values = list(provenance)
        if len(candidate_values) != len(provenance_values):
            raise ValueError("candidate provenance must align with candidate rows")
        for candidate, record in zip(candidate_values, provenance_values):
            self._register_candidate_provenance(candidate, record)
        if activate:
            self._active_candidate_provenance = provenance_values
        return provenance_values

    def activate_candidate_provenance(
        self,
        population: Any,
        provenance: Iterable[CandidateProvenance],
    ) -> None:
        population_values = np.asarray(population)
        provenance_values = list(provenance)
        if population_values.ndim != 2 or population_values.shape[0] != len(
            provenance_values
        ):
            raise ValueError("active candidate provenance must align with population")
        self._active_candidate_provenance = provenance_values
        self._active_candidate_population_ref = weakref.ref(population_values)

    def _take_warm_start_candidate(self) -> Optional[np.ndarray]:
        if not self._pending_warm_starts:
            return None
        record = dict(self._pending_warm_starts.pop(0))
        candidate = np.asarray(record["candidate"], dtype=float).reshape(-1).copy()
        provenance = self._new_candidate_provenance(
            source_kind="warm_start_evaluated",
            source_run_id=record.get("source_run_id"),
            warm_start_id=record.get("warm_start_id"),
            metadata=record.get("metadata", {}),
        )
        self._register_candidate_provenance(candidate, provenance)
        self._consumed_warm_starts.append(provenance.as_dict())
        return candidate

    def incumbent_source_for(
        self,
        candidate: Any,
        *,
        candidate_index: Optional[int] = None,
        population: Any = None,
    ) -> dict[str, Any]:
        provenance = None
        active_population = (
            None
            if self._active_candidate_population_ref is None
            else self._active_candidate_population_ref()
        )
        population_values = None if population is None else np.asarray(population)
        if candidate_index is not None and active_population is population_values:
            index = int(candidate_index)
            if 0 <= index < len(self._active_candidate_provenance):
                provenance = self._active_candidate_provenance[index]
        if provenance is None:
            provenance = self._lookup_candidate_provenance(candidate)
        if provenance is None:
            provenance = self._new_candidate_provenance(
                source_kind="evaluation",
                source_run_id=self._active_run_id,
            )
            self._register_candidate_provenance(candidate, provenance)
        return {
            "candidate_token": provenance.candidate_token,
            "source": provenance.source_kind,
            "source_run_id": provenance.source_run_id,
            "warm_start_id": provenance.warm_start_id,
            "proposal_id": provenance.proposal_id,
            "parent_token": provenance.parent_token,
            "transform_stage": provenance.transform_stage,
            "metadata": dict(provenance.metadata),
        }

    def set_pareto_snapshot(self, solutions: Any, objectives: Any) -> None:
        set_pareto_snapshot_fields(
            self,
            solutions,
            objectives,
            report_soft_error_fn=report_soft_error,
            logger=logger,
        )

    def get_best_snapshot(self) -> Tuple[Optional[Any], Optional[float]]:
        return self._get_best_snapshot()

    def set_solver_hyperparams(
        self,
        *,
        pop_size: Optional[int] = None,
        max_generations: Optional[int] = None,
        mutation_rate: Optional[float] = None,
        crossover_rate: Optional[float] = None,
    ) -> None:
        if pop_size is not None:
            setattr(self, "pop_size", int(pop_size))
        if max_generations is not None:
            setattr(self, "max_generations", int(max_generations))
        if mutation_rate is not None:
            setattr(self, "mutation_rate", float(mutation_rate))
        if crossover_rate is not None:
            setattr(self, "crossover_rate", float(crossover_rate))

    # ------------------------------------------------------------------
    # Representation helpers (optional)
    # ------------------------------------------------------------------
    def store_solutions(self, batch, *, stage="initial", region="main", source=None, feedback=None, provenance=None):
        """Register candidate values before use; Units retain search relationships."""
        records = []
        provided = None if provenance is None else tuple(provenance)
        if provided is not None and len(provided) != len(batch.semantic_states):
            raise ValueError("pool provenance must align with candidate rows")
        for i, (state, token) in enumerate(zip(batch.semantic_states, batch.candidate_tokens)):
            record = self.candidate_provenance_for(state) if provided is None else provided[i]
            if record is None:
                record = CandidateProvenance(token, source_kind="pool_input", source_run_id=self._active_run_id)
            records.append(self._with_candidate_semantics(record, state).as_dict())
        return self.solution_pool.put(
            batch, stage=stage, region=region,
            source=source or getattr(getattr(self, "adapter", None), "name", "control"),
            generation=int(self.generation),
            attempt=int(self.export_run_progress_state().get("attempts_completed", 0)),
            feedback=feedback, provenance=records,
        )

    def set_solution_pool_retention(self, policy):
        """Configure candidate retention before the first publication."""
        if policy is not None:
            self.solution_pool_retention_roots()
        self.solution_pool.set_retention_policy(policy)

    def solution_pool_retention_roots(self):
        """Read declared local/child roots without mutating pool lifetime state."""
        roots = {}
        seen = set()
        def visit(adapter, path):
            if id(adapter) in seen:
                raise ValueError("pool retention requires distinct, acyclic Adapter owners")
            seen.add(id(adapter))
            refs = adapter.get_solution_pool_roots(self)
            if refs is None:
                raise ValueError(f"{adapter.name} must declare get_solution_pool_roots before pool retention")
            roots["adapter/" + "/".join(path)] = tuple(refs)
            for i, child in enumerate(adapter.step_transaction_children()):
                visit(child, (*path, f"{i}:{child.name}"))
        adapter = getattr(self, "adapter", None)
        if adapter is not None:
            visit(adapter, (adapter.name,))
        return roots

    def prepare_solution_pool_retention(self):
        """Sync explicit Unit roots after update, then stage one retention step."""
        if self.solution_pool.retention_policy is None:
            return
        roots = self.solution_pool_retention_roots()
        self.solution_pool.replace_roots("adapter/", roots)
        self.solution_pool.stage_retention_step()

    def read_solutions(self, refs, *, allow_pending=False):
        """Resolve references and bind both candidate views to their stable tokens."""
        refs = tuple(refs)
        batch = self.solution_pool.read(refs, allow_pending=allow_pending)
        saved = self.solution_pool.read_provenance(refs, allow_pending=allow_pending)
        provenance = [self._with_candidate_semantics(
            CandidateProvenance.from_dict(value) if value is not None else
            CandidateProvenance(token, source_kind="pool_input"), state)
            for value, token, state in zip(saved, batch.candidate_tokens, batch.semantic_states)]
        self.bind_candidate_provenance(batch.numeric_rows(), provenance, activate=False)
        for state, record in zip(batch.semantic_states, provenance):
            self._register_candidate_provenance(state, record)
        return batch

    def propose_solutions(self, refs):
        """Create explicit proposals from pool inputs, retaining source identities.

        Reading preserves identity. A new algorithm invocation creates a derived
        proposal so its origin and repair can change without rewriting the seed.
        """
        refs = tuple(refs)
        source = self.read_solutions(refs)
        records = []
        for ref, state in zip(refs, source.semantic_states):
            previous = self.candidate_provenance_for(state)
            record = self._new_candidate_provenance(
                source_kind="pool_handoff", source_run_id=previous.source_run_id,
                parent_token=ref.candidate_token, transform_stage="pool_handoff",
                metadata={**dict(previous.metadata), "solution_source_ref": ref.as_dict()},
            )
            record = self._with_candidate_semantics(record, state)
            self._register_candidate_provenance(state, record)
            records.append(record)
        batch = CandidateBatch(source.semantic_states, source.numeric_matrix,
                               tuple(r.candidate_token for r in records))
        for state, record in zip(batch.semantic_states, records):
            self._register_candidate_provenance(state, record)
        self.bind_candidate_provenance(batch.numeric_rows(), records, activate=False)
        return batch

    def _register_solution_value(self, value, provenance, *, stage):
        semantic = value
        if not isinstance(value, UnknownState):
            semantic = self.semantic_candidate_state(value)
        batch = CandidateBatch.from_candidates((semantic,), candidate_tokens=(provenance.candidate_token,))
        ref, = self.store_solutions(batch, stage=stage, provenance=(provenance,))
        pooled = self.solution_pool.read((ref,), allow_pending=True)
        row = pooled.numeric_matrix[0]
        self._register_candidate_provenance(row, provenance)
        self._register_candidate_provenance(pooled.semantic_states[0], provenance)
        return pooled.semantic_states[0] if isinstance(value, UnknownState) else row

    def init_candidate(self, context: Optional[Dict[str, Any]] = None) -> np.ndarray:
        from nsgablack.context_keys import KEY_SOLUTION_INPUT_REF
        input_ref = (context or {}).get(KEY_SOLUTION_INPUT_REF)
        if input_ref is not None:
            ref = self.solution_pool.take_input(input_ref)
            batch = self.propose_solutions((ref,))
            row = batch.numeric_matrix[0]
            record = self.candidate_provenance_for(batch.semantic_states[0])
            self._register_candidate_provenance(row, record)
            return row
        warm_start = self._take_warm_start_candidate()
        if warm_start is not None:
            normalized = normalize_candidate(
                warm_start,
                dimension=self.dimension,
                name="warm_start.candidate",
            )
            record = self.candidate_provenance_for(warm_start)
            self._register_candidate_provenance(normalized, record)
            return self._register_solution_value(normalized, record, stage="initial")
        pipeline = self.representation_pipeline
        if representation_capabilities(pipeline).supports("init"):
            init_fn = getattr(pipeline, "init", None)
            if not callable(init_fn):
                raise TypeError("representation pipeline must expose init(context)")
            init_context = dict(context or self.build_context())
            init_context[KEY_PROBLEM] = self.problem
            cand = init_fn(init_context)
        else:
            cand = self._random_candidate()
        normalized = normalize_candidate(cand, dimension=self.dimension, name="init_candidate")
        provenance = self._lookup_candidate_provenance(cand)
        if provenance is None:
            provenance = self._new_candidate_provenance(
                source_kind="initialization", source_run_id=self._active_run_id)
        if isinstance(cand, UnknownState):
            provenance = self._with_candidate_semantics(provenance, cand)
        self._register_candidate_provenance(normalized, provenance)
        return self._register_solution_value(normalized, provenance, stage="initial")

    def init_population(
        self,
        count: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> tuple[Any, ...]:
        """Create an unevaluated proposal batch for Adapter consumption.

        This is intentionally separate from ``initialize_population``: the
        lifecycle operation may evaluate, publish snapshots and fire Plugin
        hooks, while an Adapter proposal must remain side-effect bounded.
        """

        size = int(count)
        if size < 0:
            raise ValueError("population count must be non-negative")
        from nsgablack.context_keys import KEY_SOLUTION_INPUT_REF
        input_ref = (context or {}).get(KEY_SOLUTION_INPUT_REF)
        if input_ref is not None and size:
            refs = self.solution_pool.take_inputs(input_ref, size)
            batch = self.propose_solutions(refs)
            rows = batch.numeric_rows()
            records = [self.candidate_provenance_for(state) for state in batch.semantic_states]
            self.bind_candidate_provenance(rows, records, activate=False)
            return tuple(rows)
        return tuple(self.init_candidate(context) for _ in range(size))

    def mutate_candidate(self, x: Any, context: Optional[Dict[str, Any]] = None, *, unit=None, operator=None) -> Any:
        input_provenance = self._lookup_candidate_provenance(x)
        if input_provenance is None:
            input_provenance = self._new_candidate_provenance(
                source_kind="mutation_parent",
                source_run_id=self._active_run_id,
                transform_stage="mutation_input",
            )
            if isinstance(x, UnknownState):
                input_provenance = self._with_candidate_semantics(
                    input_provenance,
                    x,
                )
            self._register_candidate_provenance(x, input_provenance)
        x = self._register_solution_value(x, input_provenance, stage="mutation_parent")
        from ..representation.structure_builders import encode_unit_value, decode_unit_value
        x = decode_unit_value(encode_unit_value(x))
        self._register_candidate_provenance(x, input_provenance)
        pipeline = self.representation_pipeline
        if representation_capabilities(pipeline).supports("mutate"):
            kwargs = {} if operator is None else {"operator": operator}
            if unit is not None:
                kwargs["unit"] = unit
            out = pipeline.mutate(x, context, **kwargs)
        else:
            if unit is not None or operator is not None:
                raise ValueError("Unit mutation inputs require a configured mutator")
            out = x
        normalized = normalize_candidate(
            out,
            dimension=self.dimension,
            name="mutate_candidate",
        )
        provenance = self._new_candidate_provenance(
            source_kind="mutation",
            source_run_id=input_provenance.source_run_id or self._active_run_id,
            warm_start_id=input_provenance.warm_start_id,
            proposal_id=input_provenance.proposal_id,
            parent_token=input_provenance.candidate_token,
            transform_stage="mutate",
            metadata=input_provenance.metadata,
        )
        if isinstance(out, UnknownState):
            provenance = self._with_candidate_semantics(provenance, out)
            self._register_candidate_provenance(out, provenance)
        self._register_candidate_provenance(normalized, provenance)
        return self._register_solution_value(out if isinstance(out, UnknownState) else normalized,
                                             provenance, stage="mutation")

    def repair_candidate(self, x: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        input_provenance = self._lookup_candidate_provenance(x)
        if input_provenance is not None:
            x = self._register_solution_value(x, input_provenance, stage="repair_input")
            from ..representation.structure_builders import encode_unit_value, decode_unit_value
            x = decode_unit_value(encode_unit_value(x))
            self._register_candidate_provenance(x, input_provenance)
        pipeline = self.representation_pipeline
        if representation_capabilities(pipeline).supports("repair"):
            out = pipeline.repair(x, context)
        else:
            out = x
        normalized = normalize_candidate(out, dimension=self.dimension, name="repair_candidate")
        provenance = input_provenance
        if provenance is None and isinstance(out, UnknownState):
            provenance = self._new_candidate_provenance(
                source_kind="repair",
                source_run_id=self._active_run_id,
                transform_stage="repair",
            )
        elif provenance is not None:
            provenance = CandidateProvenance(
                candidate_token=provenance.candidate_token,
                source_kind=provenance.source_kind,
                source_run_id=provenance.source_run_id,
                warm_start_id=provenance.warm_start_id,
                proposal_id=provenance.proposal_id,
                parent_token=provenance.parent_token,
                transform_stage="repair",
                metadata=provenance.metadata,
            )
        if provenance is not None:
            if isinstance(out, UnknownState):
                provenance = self._with_candidate_semantics(provenance, out)
                self._register_candidate_provenance(out, provenance)
            self._register_candidate_provenance(normalized, provenance)
        value = out if isinstance(out, UnknownState) else normalized
        return value if provenance is None else self._register_solution_value(value, provenance, stage="repair")

    def encode_candidate(self, x: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        pipeline = self.representation_pipeline
        if representation_capabilities(pipeline).supports("encode"):
            return pipeline.encode(x, context)
        return x

    def decode_candidate(self, x: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        """Decode a candidate from encoded space back to decision space.

        Only the pipeline's declared ``RepresentationCapabilities`` enable
        decoding. A declared operation must have a callable implementation;
        component attribute names never grant a capability.
        """
        pipeline = self.representation_pipeline
        if pipeline is None:
            return x
        if representation_capabilities(pipeline).supports("decode"):
            return pipeline.decode(x, context)
        return x

    def initialize_population(
        self,
        pop_size: Optional[int] = None,
        evaluate: bool = True,
        context: Optional[Dict[str, Any]] = None,
    ) -> np.ndarray:
        size = int(pop_size or getattr(self, "pop_size", 0) or self.max_steps)
        if evaluate:
            size = self.evaluation_batch_allowance(size, context=context)
        population = []
        for _ in range(size):
            population.append(self.init_candidate(context))
        candidate_provenance = self.prepare_candidate_provenance(population)
        self.bind_candidate_provenance(population, candidate_provenance)
        if population:
            self.population = stack_population(
                population,
                name="initialize_population.population",
            )
        else:
            self.population = np.empty((0, int(self.dimension)), dtype=float)
        self.activate_candidate_provenance(self.population, candidate_provenance)

        if evaluate:
            (
                self.population,
                self.objectives,
                self.constraint_violations,
                budget_truncated,
            ) = self._evaluate_population_with_budget_retry(self.population)
            self._active_candidate_provenance = candidate_provenance[
                : int(self.population.shape[0])
            ]
            self.activate_candidate_provenance(
                self.population,
                self._active_candidate_provenance,
            )
            if budget_truncated and int(self.population.shape[0]) == 0:
                self.request_stop()
            self.plugin_manager.on_population_init(
                self.population, self.objectives, self.constraint_violations
            )
            try:
                self._runtime_governance_on_population_init(
                    self.population,
                    self.objectives,
                    self.constraint_violations,
                )
            except Exception:
                if bool(getattr(self, "plugin_strict", False)):
                    raise
        active_count = int(self.population.shape[0])
        active_records = tuple(self._active_candidate_provenance[:active_count])
        semantic_states = tuple(
            self.semantic_candidate_state(row, candidate_index=index)
            for index, row in enumerate(np.asarray(self.population, dtype=float))
        )
        source_batch = CandidateBatch(
            semantic_states=semantic_states,
            numeric_matrix=np.asarray(self.population, dtype=float),
            candidate_tokens=tuple(
                record.candidate_token for record in active_records
            ),
        )
        self.commit_candidate_population(
            self.population,
            source_batch.candidate_tokens,
            sources=((source_batch, active_records),),
        )
        return self.population

    def _evaluation_evidence_run_id(self) -> str:
        return str(
            self._active_run_id
            or self._case_run_id()
            or f"direct-solver-{id(self):x}"
        )

    def _population_authority_key(self, run_id: str | None = None) -> str:
        scope = str(run_id or self._evaluation_evidence_run_id()).strip()
        if not scope:
            raise ValueError("population authority requires a run_id")
        return f"population/{scope}"

    def get_population_authority_identity(self) -> AuthorityIdentity | None:
        """Return the current fenced population authority for this run."""

        identity = self.authority_store.current(self._population_authority_key())
        self._latest_authority_identity = identity
        return identity

    def _evaluation_evidence_snapshot_key(
        self,
        kind: str,
        event_id: str,
    ) -> str:
        kind_text = str(kind or "").strip().lower().replace("_", "-")
        if kind_text not in {"event", "disposition"}:
            raise ValueError(f"unsupported evaluation evidence snapshot kind: {kind}")
        digest = hashlib.sha256(
            (
                self._evaluation_evidence_run_id()
                + "\x00"
                + str(event_id)
                + "\x00"
                + kind_text
            ).encode("utf-8")
        ).hexdigest()
        return f"evaluation-evidence/{kind_text}/{digest}"

    def _remember_evaluation_evidence_record(
        self,
        record: EvaluationEvidenceRecord,
    ) -> EvaluationEvidenceRecord:
        self._last_evaluation_evidence_record = record.as_dict()
        if (
            record.status in {"committed", "rejected", "failed"}
            and record.disposition is not None
        ):
            self._last_evaluation_disposition = (
                EvaluationDispositionEnvelope.from_dict(
                    record.disposition
                ).as_dict()
            )
        elif record.status == "abandoned" and isinstance(
            self._last_evaluation_disposition,
            Mapping,
        ):
            last_event_id = str(
                self._last_evaluation_disposition.get("event_id", "")
            )
            if last_event_id == record.event_id:
                self._last_evaluation_disposition = None
        return record

    def get_last_evaluation_evidence_record(
        self,
    ) -> EvaluationEvidenceRecord | None:
        payload = self._last_evaluation_evidence_record
        if not isinstance(payload, Mapping):
            return None
        return EvaluationEvidenceRecord.from_dict(payload)

    def get_evaluation_evidence_recovery_report(self) -> dict[str, Any]:
        return copy.deepcopy(self._evaluation_evidence_recovery_report)

    def archive_evaluation_evidence(
        self,
        event_id: str,
        *,
        manifest: EvaluationEvidenceArchiveManifest | Mapping[str, Any],
        archive_binding: ArtifactBinding | Mapping[str, Any],
    ) -> dict[str, Any]:
        """Verify a ledger-backed archive, then release exact evidence pins."""

        receipt = self.evaluation_evidence_coordinator.archive_and_release(
            event_id,
            manifest=manifest,
            binding=archive_binding,
        )
        return receipt.as_dict()

    def release_evaluation_evidence_snapshots(
        self,
        event_id: str,
        *,
        manifest: EvaluationEvidenceArchiveManifest | Mapping[str, Any] | None = None,
        archive_binding: ArtifactBinding | Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Compatibility entry that now requires archive authority evidence."""

        if manifest is None or archive_binding is None:
            raise RuntimeError(
                "Snapshot retention release requires a ledger-verified "
                "Evaluation Evidence archive binding"
            )
        return self.archive_evaluation_evidence(
            event_id,
            manifest=manifest,
            archive_binding=archive_binding,
        )

    def record_evaluation_event(
        self,
        batch: CandidateBatch,
        feedback: OptimizationFeedbackBatch,
        provenance: Iterable[CandidateProvenance],
    ) -> None:
        """Record one complete evaluated batch without changing authority.

        Evaluation evidence and population authority are deliberately separate:
        acceptance may reject every row while the completed evaluations remain
        replayable and auditable.
        """

        if not isinstance(batch, CandidateBatch):
            raise TypeError("evaluation event requires CandidateBatch")
        if not isinstance(feedback, OptimizationFeedbackBatch):
            raise TypeError("evaluation event requires OptimizationFeedbackBatch")
        records = tuple(provenance)
        candidate_count = len(batch.semantic_states)
        if candidate_count != feedback.candidate_count:
            raise ValueError("evaluation event batch and feedback counts must match")
        if len(records) != candidate_count:
            raise ValueError("evaluation event provenance must align with batch rows")
        for token, record in zip(batch.candidate_tokens, records):
            if token != record.candidate_token:
                raise ValueError("evaluation event token disagrees with provenance")
        self._last_evaluated_event_batch = CandidateBatch.from_dict(batch.as_dict())
        self._last_evaluated_event_feedback = OptimizationFeedbackBatch(
            objectives=feedback.objectives,
            violations=feedback.violations,
            items=feedback.items,
            metadata=feedback.metadata,
        )
        self._last_evaluated_event_provenance = records
        event_arrays = (
            np.array(batch.numeric_matrix, dtype=float, copy=True),
            np.array(feedback.objectives, dtype=float, copy=True),
            np.array(feedback.violations, dtype=float, copy=True).reshape(-1),
        )
        for value in event_arrays:
            value.setflags(write=False)
        self._last_evaluated_event_arrays = event_arrays
        self._last_evaluation_event_id = uuid.uuid4().hex
        self._last_evaluation_event_snapshot_key = None
        self._last_evaluation_disposition = None
        self._last_evaluation_authority_after_edge = None
        authority_edge = self.get_population_authority_identity()
        authority_handle = getattr(self, "_latest_snapshot_handle", None)
        if authority_edge is None and authority_handle is not None:
            raise RuntimeError(
                "local population Snapshot has no fenced Authority edge"
            )
        if authority_edge is not None:
            self.snapshot_store.read_verified(authority_edge.snapshot)
            if authority_handle is not None:
                local_identity = self.snapshot_store.identity(authority_handle)
                if local_identity != authority_edge.snapshot:
                    raise RuntimeError(
                        "local population Snapshot is behind the current Authority edge"
                    )
        self._last_evaluation_authority_before_edge = (
            None if authority_edge is None else authority_edge.as_dict()
        )
        self._last_evaluation_authority_before_ref = (
            None if authority_edge is None else authority_edge.snapshot.as_dict()
        )
        progress = getattr(self, "run_progress_state", None)
        self._last_evaluation_event_identity = {
            "run_id": self._evaluation_evidence_run_id(),
            "logical_step": int(self.generation),
            "attempt": int(getattr(progress, "attempts_completed", 0)) + 1,
            AUTHORITY_BEFORE_REF_KEY: copy.deepcopy(
                self._last_evaluation_authority_before_ref
            ),
            "authority_before_edge": copy.deepcopy(
                self._last_evaluation_authority_before_edge
            ),
        }
        if self._last_evaluation_authority_before_ref is not None:
            self._last_evaluation_event_identity["authority_snapshot_key"] = str(
                self._last_evaluation_authority_before_ref["key"]
            )

    def export_evaluation_event_checkpoint_state(self) -> dict[str, Any] | None:
        """Export full semantic evaluation evidence without inventing lineage."""

        if (
            self._last_evaluated_event_batch is None
            or self._last_evaluated_event_feedback is None
        ):
            return None
        event_id = self._last_evaluation_event_id or uuid.uuid4().hex
        self._last_evaluation_event_id = event_id
        identity = dict(self._last_evaluation_event_identity)
        if self._last_evaluation_event_snapshot_key:
            identity["event_snapshot_key"] = str(
                self._last_evaluation_event_snapshot_key
            )
        identity[AUTHORITY_BEFORE_REF_KEY] = copy.deepcopy(
            self._last_evaluation_authority_before_ref
        )
        identity["authority_before_edge"] = copy.deepcopy(
            self._last_evaluation_authority_before_edge
        )
        if self._last_evaluation_authority_before_ref is None:
            identity.pop("authority_snapshot_key", None)
        else:
            identity["authority_snapshot_key"] = str(
                self._last_evaluation_authority_before_ref["key"]
            )
        return EvaluationEventEnvelope(
            event_id=event_id,
            candidate_codec="blackbase.candidate_batch/v1",
            candidate_payload=self._last_evaluated_event_batch.as_dict(),
            feedback_codec="nsgablack.optimization_feedback_batch/v1",
            feedback_payload=self._last_evaluated_event_feedback.as_dict(),
            provenance=tuple(
                item.as_dict() for item in self._last_evaluated_event_provenance
            ),
            identity=identity,
            evaluation_count=int(self.evaluation_count),
            semantic_complete=True,
        ).as_dict()

    def get_last_evaluation_event(self) -> EvaluationEventEnvelope | None:
        """Return the canonical immutable envelope for the latest evaluation."""

        payload = self.export_evaluation_event_checkpoint_state()
        if payload is None:
            return None
        return EvaluationEventEnvelope.from_dict(payload)

    def restore_evaluation_event_checkpoint_state(
        self,
        payload: Mapping[str, Any] | None,
    ) -> None:
        if payload is None:
            self.restore_evaluation_event_arrays(None, None, None)
            return
        envelope = EvaluationEventEnvelope.from_dict(payload)
        raw_authority_before = envelope.identity.get(AUTHORITY_BEFORE_REF_KEY)
        raw_authority_before_edge = envelope.identity.get("authority_before_edge")
        restored_authority_before = (
            None
            if raw_authority_before is None
            else SnapshotIdentity.from_dict(raw_authority_before).as_dict()
        )
        restored_authority_before_edge = (
            None
            if raw_authority_before_edge is None
            else AuthorityIdentity.from_dict(raw_authority_before_edge).as_dict()
        )
        if not envelope.semantic_complete:
            numeric = dict(envelope.candidate_payload)
            feedback = dict(envelope.feedback_payload)
            self.restore_evaluation_event_arrays(
                numeric.get("population"),
                feedback.get("objectives"),
                feedback.get("constraint_violations"),
            )
            self._last_evaluation_event_id = envelope.event_id
            self._last_evaluation_event_identity = dict(envelope.identity)
            self._last_evaluation_authority_before_ref = restored_authority_before
            self._last_evaluation_authority_before_edge = (
                restored_authority_before_edge
            )
            self._last_evaluation_event_snapshot_key = str(
                envelope.identity.get("event_snapshot_key", "") or ""
            ) or None
            return
        if envelope.candidate_codec != "blackbase.candidate_batch/v1":
            raise ValueError(
                f"unsupported evaluation candidate codec: {envelope.candidate_codec}"
            )
        if envelope.feedback_codec != "nsgablack.optimization_feedback_batch/v1":
            raise ValueError(
                f"unsupported evaluation feedback codec: {envelope.feedback_codec}"
            )
        batch = CandidateBatch.from_dict(envelope.candidate_payload)
        feedback = OptimizationFeedbackBatch.from_dict(envelope.feedback_payload)
        provenance = tuple(
            CandidateProvenance.from_dict(item) for item in envelope.provenance
        )
        self.record_evaluation_event(batch, feedback, provenance)
        self._last_evaluation_event_id = envelope.event_id
        self._last_evaluation_event_identity = dict(envelope.identity)
        self._last_evaluation_authority_before_ref = restored_authority_before
        self._last_evaluation_authority_before_edge = restored_authority_before_edge
        self._last_evaluation_event_snapshot_key = str(
            envelope.identity.get("event_snapshot_key", "") or ""
        ) or None

    def restore_evaluation_event_arrays(
        self,
        population: Any,
        objectives: Any,
        violations: Any,
    ) -> None:
        """Restore numeric event evidence without fabricating semantic lineage."""

        if population is None and objectives is None and violations is None:
            self._last_evaluated_event_batch = None
            self._last_evaluated_event_feedback = None
            self._last_evaluated_event_provenance = ()
            self._last_evaluated_event_arrays = None
            self._last_evaluation_event_id = None
            self._last_evaluation_event_identity = {}
            self._last_evaluation_authority_before_ref = None
            self._last_evaluation_authority_before_edge = None
            self._last_evaluation_event_snapshot_key = None
            self._last_evaluation_disposition = None
            return
        if population is None or objectives is None or violations is None:
            raise ValueError("evaluation event arrays must be present together")
        pop = np.asarray(population, dtype=float)
        obj = np.asarray(objectives, dtype=float)
        vio = np.asarray(violations, dtype=float).reshape(-1)
        if pop.ndim == 1:
            pop = pop.reshape(1, -1) if pop.size else pop.reshape(0, 0)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1) if obj.size else obj.reshape(0, 0)
        if pop.ndim != 2 or obj.ndim != 2:
            raise ValueError("evaluation event population/objectives must be 2D")
        if pop.shape[0] != obj.shape[0] or pop.shape[0] != vio.shape[0]:
            raise ValueError("evaluation event arrays must have matching rows")
        self._last_evaluated_event_batch = None
        self._last_evaluated_event_feedback = None
        self._last_evaluated_event_provenance = ()
        event_arrays = (
            np.array(pop, copy=True),
            np.array(obj, copy=True),
            np.array(vio, copy=True),
        )
        for value in event_arrays:
            value.setflags(write=False)
        self._last_evaluated_event_arrays = event_arrays
        self._last_evaluation_event_id = None
        self._last_evaluation_event_identity = {}
        self._last_evaluation_authority_before_ref = None
        self._last_evaluation_authority_before_edge = None
        self._last_evaluation_event_snapshot_key = None
        self._last_evaluation_disposition = None

    def write_evaluation_event_snapshot(self) -> str | None:
        """Publish and index the Event before any acceptance decision runs."""

        event_id = str(self._last_evaluation_event_id or "").strip()
        if not event_id:
            raise RuntimeError("cannot publish evaluation evidence without event_id")
        key = self._evaluation_evidence_snapshot_key("event", event_id)
        self._last_evaluation_event_snapshot_key = key
        self._last_evaluation_event_identity["event_snapshot_key"] = key
        coordinator = self.evaluation_evidence_coordinator
        reserved = coordinator.reserve_event(
            event_id=event_id,
            run_id=self._evaluation_evidence_run_id(),
            event_snapshot_key=key,
            authority_before_ref=self._last_evaluation_authority_before_edge,
            identity=dict(self._last_evaluation_event_identity),
            metadata={
                "authority_mode_before_decision": str(
                    self.population_authority_mode
                ),
            },
        )
        self._remember_evaluation_evidence_record(reserved)
        envelope_payload = self.export_evaluation_event_checkpoint_state()
        if envelope_payload is None:
            raise RuntimeError("Evaluation Event has no semantic envelope")
        envelope = EvaluationEventEnvelope.from_dict(envelope_payload)
        if envelope.event_id != event_id:
            raise RuntimeError("Evaluation Event envelope disagrees with journal")
        authority_before_ref = copy.deepcopy(
            self._last_evaluation_authority_before_ref
        )
        payload = build_evaluation_event_snapshot_payload(
            envelope,
            authority_before_ref=authority_before_ref,
        )
        record = {
            "data": payload,
            "key": key,
            "meta": {
                "created_at": float(time.time()),
                "event_id": event_id,
                "authority_before_key": (
                    None
                    if authority_before_ref is None
                    else authority_before_ref["key"]
                ),
            },
            "schema": EVALUATION_EVENT_SNAPSHOT_SCHEMA_V1,
            "ttl_seconds": self.snapshot_store_ttl_seconds,
            "generation": getattr(self, "generation", None),
            "publication": "evaluation_event",
        }
        handle = self._write_snapshot_record(
            record,
            strict=True,
        )
        if handle is None:
            raise RuntimeError("Evaluation Event Snapshot publication failed")
        if str(handle.key) != key:
            raise RuntimeError("Evaluation Event snapshot handle disagrees with journal")
        # ``mark_event_durable`` is a semantic transition, not an assertion
        # performed by the storage-agnostic journal.  Verify read-after-write
        # here so an eventually-consistent or faulty SnapshotStore cannot move
        # the record to ``pending`` while the Event evidence is still absent.
        try:
            durable_record = self.snapshot_store.read_verified(
                self.snapshot_store.identity(handle)
            )
            durable_envelope, durable_authority_before = (
                validate_evaluation_event_snapshot(
                    durable_record.data,
                    snapshot_schema=durable_record.schema,
                    expected_event_id=event_id,
                    expected_run_id=reserved.run_id,
                    expected_snapshot_key=key,
                )
            )
            if durable_envelope.event_id != event_id:
                raise ValueError("Evaluation Event payload disagrees with journal")
            if durable_authority_before is not None:
                self.snapshot_store.read_verified(durable_authority_before)
        except Exception as exc:
            raise RuntimeError(
                "Evaluation Event snapshot is not durably readable or valid after write"
            ) from exc
        try:
            pending = coordinator.confirm_event(
                event_id,
                expected_revision=reserved.revision,
            )
        except (EvaluationEvidenceDeferred, EvaluationEvidenceInvalid) as exc:
            raise RuntimeError(
                "Evaluation Event snapshot is not durably readable or valid after write"
            ) from exc
        self._remember_evaluation_evidence_record(pending)
        return key

    def prepare_evaluation_disposition(
        self,
        envelope: EvaluationDispositionEnvelope,
        *,
        disposition_snapshot_key: str = "",
    ) -> EvaluationEvidenceRecord:
        record = self.evaluation_evidence_coordinator.prepare_decision(
            envelope,
            disposition_snapshot_key=disposition_snapshot_key,
        )
        self._last_evaluation_disposition = envelope.as_dict()
        return self._remember_evaluation_evidence_record(record)

    def settle_evaluation_disposition(
        self,
        event_id: str,
    ) -> EvaluationEvidenceRecord:
        journal = self.evaluation_evidence_journal
        current = journal.get(event_id)
        if current is None:
            raise KeyError(f"unknown evaluation evidence event: {event_id}")
        if current.status == "abandoned":
            return self._remember_evaluation_evidence_record(current)
        if current.terminal_verified:
            return self._remember_evaluation_evidence_record(current)
        try:
            record = self.evaluation_evidence_coordinator.settle_decision(
                event_id,
                expected_revision=current.revision,
            )
        except (EvaluationEvidenceDeferred, EvaluationEvidenceInvalid) as exc:
            raise RuntimeError(
                "evaluation disposition destination is not durably readable: "
                f"{exc}"
            ) from exc
        return self._remember_evaluation_evidence_record(record)

    @staticmethod
    def _snapshot_event_id(
        payload: Mapping[str, Any],
        *,
        snapshot_schema: str,
    ) -> str:
        return PopulationEvidenceSemantics._snapshot_event_id(payload, snapshot_schema=snapshot_schema)

    def read_evaluation_event_snapshot(
        self,
        key: str,
    ) -> EvaluationEventEnvelope | None:
        """Read either the Event v1 record or its legacy population/v2 shape."""

        record = self.snapshot_store.read(str(key))
        if record is None:
            return None
        envelope, _ = validate_evaluation_event_snapshot(
            record.data,
            snapshot_schema=record.schema,
            expected_snapshot_key=str(key),
        )
        return envelope

    @staticmethod
    def _snapshot_disposition(
        payload: Mapping[str, Any],
    ) -> EvaluationDispositionEnvelope | None:
        return PopulationEvidenceSemantics._snapshot_disposition(payload)

    @staticmethod
    def _validate_event_authority_edge(
        envelope: EvaluationEventEnvelope,
        expected: AuthorityIdentity | None,
    ) -> AuthorityIdentity | None:
        return PopulationEvidenceSemantics._validate_event_authority_edge(envelope, expected)

    def inspect_event(
        self,
        record: EvaluationEvidenceRecord,
        snapshots: SnapshotStore,
    ) -> EvaluationEvidenceInspection:
        return self.evaluation_evidence_semantics.inspect_event(record, snapshots)

    def inspect_decision(
        self,
        record: EvaluationEvidenceRecord,
        snapshots: SnapshotStore,
    ) -> EvaluationEvidenceInspection:
        return self.evaluation_evidence_semantics.inspect_decision(record, snapshots)

    def _recover_pending_authority_commit(
        self,
        record: EvaluationEvidenceRecord,
    ) -> AuthorityIdentity | None:
        """Replay only a durable accepted Authority CAS, never domain execution."""

        if record.disposition is None or record.phase != "decision_ready":
            return None
        intent = EvaluationDispositionEnvelope.from_dict(record.disposition)
        if intent.status != "committed":
            return None
        event_record = self.snapshot_store.read(record.event_snapshot_key)
        destination = self.snapshot_store.read(intent.authority_snapshot_key)
        if event_record is None or destination is None:
            return None
        event_envelope, event_predecessor = validate_evaluation_event_snapshot(
            event_record.data,
            snapshot_schema=event_record.schema,
            expected_event_id=record.event_id,
            expected_run_id=record.run_id,
            expected_snapshot_key=record.event_snapshot_key,
        )
        observed = self._snapshot_disposition(destination.data)
        if observed is None or observed.as_dict() != intent.as_dict():
            raise RuntimeError(
                "pending Authority Snapshot does not carry its durable decision intent"
            )
        expected_mode = str(
            intent.metadata.get("authority_mode", "") or ""
        ).strip().lower()
        validate_population_snapshot_v2(
            destination.data,
            snapshot_schema=destination.schema,
            expected_authority_mode=expected_mode,
            require_semantic_identity=True,
        )
        event_ref = self.snapshot_store.identity(event_record)
        destination_ref = self.snapshot_store.identity(destination)
        self.snapshot_store.read_verified(event_ref)
        self.snapshot_store.read_verified(destination_ref)

        raw_before = getattr(record, "authority_before_ref", None)
        before = (
            None if raw_before is None else AuthorityIdentity.from_dict(raw_before)
        )
        self._validate_event_authority_edge(event_envelope, before)
        if before is not None and before.snapshot != event_predecessor:
            raise RuntimeError(
                "pending Authority intent disagrees with the Event predecessor"
            )
        authority_key = self._population_authority_key(record.run_id)
        current = self.authority_store.current(authority_key)
        expected_epoch = None if before is None else before.epoch
        if current is not None and (
            current.snapshot == destination_ref
            and current.caused_by_event_identity == event_ref
            and current.epoch == (1 if before is None else before.epoch + 1)
        ):
            if destination.data.get("solution_pool_ref") is not None:
                self.solution_pool.restore_publication(destination.data["solution_pool_ref"])
            return current
        if current != before:
            raise RuntimeError(
                "pending Authority intent lost its fencing epoch"
            )
        committed = self.authority_store.commit(
            authority_key,
            destination_ref,
            expected_epoch=expected_epoch,
            caused_by_event_identity=event_ref,
        )
        self._latest_authority_identity = committed
        self._latest_snapshot_handle = destination
        self._last_evaluation_authority_after_edge = committed.as_dict()
        if destination.data.get("solution_pool_ref") is not None:
            self.solution_pool.restore_publication(destination.data["solution_pool_ref"])
        return committed

    def _inspect_evaluation_disposition_destination(
        self,
        record: EvaluationEvidenceRecord,
    ) -> EvaluationEvidenceInspection:
        return self.evaluation_evidence_semantics._inspect_evaluation_disposition_destination(record)

    def reconcile_evaluation_evidence(
        self,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """Recover evidence through the same coordinator used by live steps."""

        target_run_id = str(run_id or self._active_run_id or "").strip()
        if not target_run_id:
            raise ValueError("evaluation evidence recovery requires a run_id")
        for record in self.evaluation_evidence_journal.list_unresolved(
            run_id=target_run_id
        ):
            if record.phase != "decision_ready":
                continue
            try:
                self._recover_pending_authority_commit(record)
            except Exception as _fallback_error:
                # The coordinator's read-only inspection below classifies the
                # durable evidence and keeps a lost fence retryable/auditable.
                _report_optional_failure(component=__name__, event='SolverBase.reconcile_evaluation_evidence.fallback_155', exc=_fallback_error)
                pass
        report = self.evaluation_evidence_coordinator.reconcile(
            run_id=target_run_id
        )
        report["unresolved_count"] = len(report.get("records", ()))
        if report.get("status") == "ok":
            report["status"] = "complete"
        for entry in report.get("records", ()):
            record = self.evaluation_evidence_journal.get(
                str(entry.get("event_id", ""))
            )
            if record is not None:
                self._remember_evaluation_evidence_record(record)
        self._evaluation_evidence_recovery_report = copy.deepcopy(report)
        return copy.deepcopy(report)

    def ensure_evaluation_evidence_ready_for_next_step(
        self,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """Converge prior evidence before Authority can advance again.

        ``AuthorityStore`` deliberately exposes only the current fenced edge.
        Letting a new step advance that edge while an older decision remains
        unsettled would make the older decision impossible to verify.  This
        preflight therefore reconciles all prior records and fails closed if
        any durable evidence is still unresolved.
        """

        target_run_id = str(run_id or self._evaluation_evidence_run_id()).strip()
        if not target_run_id:
            raise ValueError("evaluation evidence preflight requires a run_id")
        unresolved = self.evaluation_evidence_journal.list_unresolved(
            run_id=target_run_id
        )
        if not unresolved:
            return {
                "status": "complete",
                "run_id": target_run_id,
                "unresolved_count": 0,
                "records": [],
            }
        report = self.reconcile_evaluation_evidence(target_run_id)
        remaining = self.evaluation_evidence_journal.list_unresolved(
            run_id=target_run_id
        )
        if remaining:
            blockers = ", ".join(
                f"{record.event_id}:{record.phase}" for record in remaining
            )
            raise EvaluationEvidenceDeferred(
                "prior evaluation evidence must converge before the next "
                f"Authority step: {blockers}"
            )
        return report

    def export_evaluation_disposition_checkpoint_state(
        self,
    ) -> dict[str, Any] | None:
        """Export the latest Event -> disposition -> authority edge."""

        if self._last_evaluation_disposition is None:
            return None
        return EvaluationDispositionEnvelope.from_dict(
            self._last_evaluation_disposition
        ).as_dict()

    def restore_evaluation_disposition_checkpoint_state(
        self,
        payload: Mapping[str, Any] | None,
    ) -> None:
        if payload is None:
            self._last_evaluation_disposition = None
            return
        envelope = EvaluationDispositionEnvelope.from_dict(payload)
        self._last_evaluation_disposition = envelope.as_dict()

    def pending_snapshot_step_key(self) -> str | None:
        """Return the staged authority key without publishing it."""

        transaction = self._snapshot_step_transaction
        if not isinstance(transaction, Mapping):
            return None
        pending = transaction.get("pending")
        if not isinstance(pending, Mapping):
            return None
        key = str(pending.get("key", "") or "")
        return key or None

    def attach_evaluation_disposition_to_pending_snapshot(
        self,
        envelope: EvaluationDispositionEnvelope,
    ) -> bool:
        """Atomically couple a committed disposition to staged authority."""

        if not isinstance(envelope, EvaluationDispositionEnvelope):
            raise TypeError("envelope must be EvaluationDispositionEnvelope")
        self._last_evaluation_disposition = envelope.as_dict()
        transaction = self._snapshot_step_transaction
        if not isinstance(transaction, dict):
            return False
        pending = transaction.get("pending")
        if not isinstance(pending, dict):
            return False
        data = pending.get("data")
        if not isinstance(data, dict):
            raise RuntimeError("staged authority Snapshot has no mutable data envelope")
        data[LAST_EVALUATION_DISPOSITION_KEY] = envelope.as_dict()
        pending["authority_commit"] = self._authority_commit_plan(
            use_evaluation_edge=True,
        )
        return True

    def write_evaluation_disposition_snapshot(
        self,
        envelope: EvaluationDispositionEnvelope,
        *,
        force_key: str | None = None,
    ) -> str | None:
        """Publish a rejected/failed disposition without changing authority."""

        if not isinstance(envelope, EvaluationDispositionEnvelope):
            raise TypeError("envelope must be EvaluationDispositionEnvelope")
        self._last_evaluation_disposition = envelope.as_dict()
        if self.snapshot_store is None:
            return None
        key = str(
            force_key
            or self._evaluation_evidence_snapshot_key(
                "disposition",
                envelope.event_id,
            )
        )
        handle = self._write_snapshot_record(
            {
                "data": {LAST_EVALUATION_DISPOSITION_KEY: envelope.as_dict()},
                "key": key,
                "meta": {
                    "publication": "evaluation_disposition",
                    "event_id": envelope.event_id,
                    "status": envelope.status,
                },
                "schema": "nsgablack.evaluation_disposition_snapshot/v1",
                "ttl_seconds": self.snapshot_store_ttl_seconds,
                "generation": getattr(self, "generation", None),
                "publication": "evaluation_disposition",
            },
            strict=bool(getattr(self, "snapshot_strict", False)),
        )
        return None if handle is None else str(handle.key)

    def write_population_snapshot(
        self,
        population: np.ndarray,
        objectives: np.ndarray,
        violations: np.ndarray,
    ) -> bool:
        pop = np.asarray(population, dtype=float)
        obj = np.asarray(objectives, dtype=float)
        vio = np.asarray(violations, dtype=float).reshape(-1)
        if pop.ndim == 1:
            pop = pop.reshape(1, -1) if pop.size > 0 else pop.reshape(0, 0)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1) if obj.size > 0 else obj.reshape(0, 0)
        if obj.shape[0] != pop.shape[0] or vio.shape[0] != pop.shape[0]:
            return False
        batch = self._candidate_population_batch
        if batch is not None and (
            pop.shape != batch.numeric_matrix.shape
            or not np.array_equal(pop, batch.numeric_matrix, equal_nan=True)
        ):
            # A numeric-only writer cannot claim that semantic states and
            # candidate lineage still describe a different population.  The
            # next semantic-aware Solver step may establish a new CandidateBatch.
            self._candidate_population_batch = None
            self._candidate_population_provenance = ()
        self.population = pop
        self.objectives = obj
        self.constraint_violations = vio
        return self._persist_snapshot(
            population=pop,
            objectives=obj,
            violations=vio,
            include_pareto=True,
            include_history=True,
            include_decision_trace=True,
        )

    def write_partitioned_population_snapshot(self) -> bool:
        """Publish partition authority when no last-evaluated batch exists."""

        if str(getattr(self, "population_authority_mode", "single") or "single") != "partitioned":
            raise RuntimeError(
                "write_partitioned_population_snapshot requires partitioned authority"
            )
        return self._persist_snapshot(
            population=None,
            objectives=None,
            violations=None,
            include_pareto=True,
            include_history=True,
            include_decision_trace=True,
            resolve_defaults=False,
        )

    def begin_snapshot_step_transaction(self) -> None:
        """Begin one deferred authoritative Snapshot publication."""

        if self._snapshot_step_transaction is not None:
            raise RuntimeError("a Snapshot step transaction is already active")
        self._snapshot_step_transaction = {
            "schema": "nsgablack.snapshot_step_transaction/v1",
            "pending": None,
        }

    def commit_snapshot_step_transaction(self) -> None:
        """Durably publish the last staged authority under a fresh key."""

        transaction = self._snapshot_step_transaction
        if transaction is None:
            return
        pending = transaction.get("pending")
        if pending is None:
            self._snapshot_step_transaction = None
            return
        handle = self._write_snapshot_record(pending, strict=True)
        if handle is None:  # pragma: no cover - strict writes raise
            raise RuntimeError("authoritative Snapshot transaction did not publish")
        self._snapshot_step_transaction = None

    def rollback_snapshot_step_transaction(self) -> None:
        """Discard a staged authority without touching committed Snapshots."""

        self._snapshot_step_transaction = None

    def _snapshot_run_id(self) -> Optional[str]:
        for attr in ("run_id", "_run_id", "experiment_id"):
            rid = getattr(self, attr, None)
            if rid:
                return str(rid)
        return None

    def _build_snapshot_key(self) -> str:
        run_id = self._snapshot_run_id()
        generation = getattr(self, "generation", None)
        step = getattr(self, "step_count", None)
        prefix = run_id or self.snapshot_store_key_prefix or "snapshot"
        return make_snapshot_key(prefix=prefix, generation=generation, step=step)

    def _snapshot_meta(
        self,
        population: Optional[np.ndarray],
        objectives: Optional[np.ndarray],
        violations: Optional[np.ndarray],
        *,
        pareto_solutions: Optional[np.ndarray] = None,
        pareto_objectives: Optional[np.ndarray] = None,
        complete: bool = True,
    ) -> Dict[str, Any]:
        authority_mode = str(
            getattr(self, "population_authority_mode", "single") or "single"
        )
        meta = snapshot_meta(
            population,
            objectives,
            violations,
            pareto_solutions=pareto_solutions,
            pareto_objectives=pareto_objectives,
            complete=complete,
        )
        meta.update(
            {
                "population_snapshot_schema": POPULATION_SNAPSHOT_SCHEMA_V2,
                "authority_mode": authority_mode,
            }
        )
        event_arrays = self._last_evaluated_event_arrays
        meta.update(
            {
                "last_evaluated_population_shape": (
                    None if event_arrays is None else list(event_arrays[0].shape)
                ),
                "last_evaluated_objectives_shape": (
                    None if event_arrays is None else list(event_arrays[1].shape)
                ),
                "last_evaluated_violations_shape": (
                    None if event_arrays is None else list(event_arrays[2].shape)
                ),
            }
        )
        if authority_mode == "partitioned":
            export_partitions = getattr(
                self,
                "export_candidate_population_partitions_checkpoint_state",
                None,
            )
            partition_payload = (
                export_partitions() if callable(export_partitions) else None
            )
            partitions = (
                tuple(partition_payload.get("partitions", ()) or ())
                if isinstance(partition_payload, Mapping)
                else ()
            )
            meta.update(
                {
                    "population_shape": None,
                    "objectives_shape": None,
                    "violations_shape": None,
                    "partition_count": len(partitions),
                }
            )
        return meta

    def _prepare_snapshot_payload(
        self,
        population: Optional[np.ndarray],
        objectives: Optional[np.ndarray],
        violations: Optional[np.ndarray],
        *,
        pareto_solutions: Optional[np.ndarray] = None,
        pareto_objectives: Optional[np.ndarray] = None,
        history: Optional[Any] = None,
        decision_trace: Optional[Any] = None,
    ) -> Dict[str, Any]:
        stored_event_batch = self._last_evaluated_event_batch
        stored_event_feedback = self._last_evaluated_event_feedback
        stored_event_arrays = self._last_evaluated_event_arrays
        has_semantic_event = (
            stored_event_batch is not None and stored_event_feedback is not None
        )
        has_stored_event = stored_event_arrays is not None
        event_payload = build_snapshot_payload(
            (
                stored_event_arrays[0]
                if has_stored_event
                else population
            ),
            (
                stored_event_arrays[1]
                if has_stored_event
                else objectives
            ),
            (
                stored_event_arrays[2]
                if has_stored_event
                else violations
            ),
        )
        authority_mode = str(
            getattr(self, "population_authority_mode", "single") or "single"
        )
        if authority_mode == "partitioned":
            payload = build_snapshot_payload(
                None,
                None,
                None,
                pareto_solutions=pareto_solutions,
                pareto_objectives=pareto_objectives,
                history=history,
                decision_trace=decision_trace,
            )
            # Keep the partition event slot present even when no evaluation
            # has happened; v2 readers use this as a legacy authority hint.
            payload[LAST_EVALUATED_BATCH_KEY] = event_payload
        else:
            payload = build_snapshot_payload(
                population,
                objectives,
                violations,
                pareto_solutions=pareto_solutions,
                pareto_objectives=pareto_objectives,
                history=history,
                decision_trace=decision_trace,
            )
            if has_stored_event:
                payload[LAST_EVALUATION_EVENT_KEY] = event_payload
        payload[POPULATION_AUTHORITY_KEY] = {
            "schema": POPULATION_SNAPSHOT_SCHEMA_V2,
            "authority_mode": authority_mode,
        }
        if self.solution_pool.publication_ref() is not None:
            payload["solution_pool_ref"] = self.solution_pool.publication_ref()
        if self._last_evaluation_disposition is not None:
            payload[LAST_EVALUATION_DISPOSITION_KEY] = copy.deepcopy(
                self._last_evaluation_disposition
            )
        authority_batch = self._candidate_population_batch
        if authority_batch is not None and population is not None:
            numeric = np.asarray(population, dtype=float)
            if numeric.shape == authority_batch.numeric_matrix.shape and np.array_equal(
                numeric,
                authority_batch.numeric_matrix,
                equal_nan=True,
            ):
                payload[_CANDIDATE_BATCH_SNAPSHOT_KEY] = authority_batch.as_dict()
                payload[_CANDIDATE_PROVENANCE_SNAPSHOT_KEY] = [
                    item.as_dict()
                    for item in self._candidate_population_provenance
                ]
        if has_semantic_event:
            event_payload[_CANDIDATE_BATCH_SNAPSHOT_KEY] = (
                stored_event_batch.as_dict()
            )
            event_payload[_CANDIDATE_PROVENANCE_SNAPSHOT_KEY] = [
                item.as_dict()
                for item in self._last_evaluated_event_provenance
            ]
            event_payload["evaluation_event_envelope"] = (
                self.export_evaluation_event_checkpoint_state()
            )
        export_partitions = getattr(
            self,
            "export_candidate_population_partitions_checkpoint_state",
            None,
        )
        if callable(export_partitions):
            partition_payload = export_partitions()
            if partition_payload:
                payload[_CANDIDATE_PARTITIONS_SNAPSHOT_KEY] = partition_payload
        return payload

    def _authority_commit_plan(
        self,
        *,
        use_evaluation_edge: bool = False,
    ) -> dict[str, Any]:
        """Freeze the Authority fence that this publication is allowed to advance."""

        authority_key = self._population_authority_key()
        disposition_event_id = ""
        if isinstance(self._last_evaluation_disposition, Mapping):
            disposition_event_id = str(
                self._last_evaluation_disposition.get("event_id", "") or ""
            )
        is_current_evaluation = bool(
            use_evaluation_edge
            and self._snapshot_step_transaction is not None
            and disposition_event_id
            and disposition_event_id == str(self._last_evaluation_event_id or "")
        )
        if is_current_evaluation:
            raw_before = self._last_evaluation_authority_before_edge
            before = (
                None
                if raw_before is None
                else AuthorityIdentity.from_dict(raw_before)
            )
        else:
            before = self.authority_store.current(authority_key)

        if before is not None:
            if before.authority_key != authority_key:
                raise RuntimeError("Authority predecessor belongs to another key")
            if before.authority_scope != self.authority_store.authority_scope:
                raise RuntimeError("Authority predecessor belongs to another scope")

        caused_by: SnapshotIdentity | None = None
        event_handle = self._latest_evaluation_snapshot_handle
        if (
            is_current_evaluation
            and event_handle is not None
            and str(event_handle.key)
            == str(self._last_evaluation_event_snapshot_key or "")
        ):
            caused_by = self.snapshot_store.identity(event_handle)

        return {
            "authority_key": authority_key,
            "expected_epoch": None if before is None else before.epoch,
            "authority_before": before,
            "caused_by_event_identity": caused_by,
        }

    def _persist_snapshot(
        self,
        *,
        population: Optional[np.ndarray] = None,
        objectives: Optional[np.ndarray] = None,
        violations: Optional[np.ndarray] = None,
        include_pareto: bool = False,
        include_history: bool = False,
        include_decision_trace: bool = False,
        force_key: Optional[str] = None,
        complete: Optional[bool] = None,
        resolve_defaults: bool = True,
        publication: str = "authority",
    ) -> bool:
        store = getattr(self, "snapshot_store", None)
        if store is None:
            return False
        publication_kind = str(publication or "authority").strip().lower()
        if publication_kind not in {
            "authority",
            "evaluation_event",
            "evaluation_disposition",
        }:
            raise ValueError(f"unsupported Snapshot publication kind: {publication_kind}")
        try:
            if resolve_defaults and population is None:
                population = getattr(self, "population", None)
            if resolve_defaults and objectives is None:
                objectives = getattr(self, "objectives", None)
            if resolve_defaults and violations is None:
                violations = getattr(self, "constraint_violations", None)
        except Exception as exc:
            report_soft_error(
                component="SolverBase",
                event="snapshot_resolve_solver_state",
                exc=exc,
                logger=logger,
                context_store=self.context_store,
                strict=False,
            )

        pareto_solutions = getattr(self, "pareto_solutions", None) if include_pareto else None
        pareto_objectives = getattr(self, "pareto_objectives", None) if include_pareto else None
        history = getattr(self, "history", None) if include_history else None
        decision_trace = getattr(self, "decision_trace", None) if include_decision_trace else None

        is_complete = complete
        if is_complete is None:
            authority_mode = str(
                getattr(self, "population_authority_mode", "single") or "single"
            )
            if authority_mode == "partitioned":
                export_partitions = getattr(
                    self,
                    "export_candidate_population_partitions_checkpoint_state",
                    None,
                )
                partition_payload = (
                    export_partitions() if callable(export_partitions) else None
                )
                is_complete = bool(
                    isinstance(partition_payload, Mapping)
                    and tuple(partition_payload.get("partitions", ()) or ())
                )
            else:
                is_complete = objectives is not None and violations is not None

        meta = self._snapshot_meta(
            population=np.asarray(population) if population is not None else None,
            objectives=np.asarray(objectives) if objectives is not None else None,
            violations=np.asarray(violations) if violations is not None else None,
            pareto_solutions=np.asarray(pareto_solutions) if pareto_solutions is not None else None,
            pareto_objectives=np.asarray(pareto_objectives) if pareto_objectives is not None else None,
            complete=bool(is_complete),
        )

        key = force_key
        gen = getattr(self, "generation", None)
        if key is None:
            key = self._build_snapshot_key()

        payload = self._prepare_snapshot_payload(
            population=population,
            objectives=objectives,
            violations=violations,
            pareto_solutions=pareto_solutions,
            pareto_objectives=pareto_objectives,
            history=history,
            decision_trace=decision_trace,
        )
        record = {
            "data": copy.deepcopy(payload),
            "key": str(key),
            "meta": copy.deepcopy(meta),
            "schema": self.snapshot_schema,
            "ttl_seconds": self.snapshot_store_ttl_seconds,
            "generation": gen,
            "publication": publication_kind,
        }
        if publication_kind == "authority":
            record["authority_commit"] = self._authority_commit_plan()
        transaction = self._snapshot_step_transaction
        if publication_kind == "authority" and transaction is not None:
            transaction["pending"] = record
            return True
        return self._write_snapshot_record(
            record,
            strict=bool(getattr(self, "snapshot_strict", False)),
        ) is not None

    def _write_snapshot_record(
        self,
        record: Mapping[str, Any],
        *,
        strict: bool,
    ) -> Any:
        store = getattr(self, "snapshot_store", None)
        if store is None:
            if strict:
                raise RuntimeError("SnapshotStore is unavailable")
            return None
        # Cancellation/deadline must win before a durable snapshot commit.
        self.checkpoint_case_runtime()
        try:
            handle = store.write(
                record["data"],
                key=str(record["key"]),
                meta=dict(record.get("meta", {}) or {}),
                schema=str(record.get("schema", self.snapshot_schema)),
                ttl_seconds=record.get("ttl_seconds"),
                write_once=str(record.get("publication", "authority")) in {
                    "authority",
                    "evaluation_event",
                    "evaluation_disposition",
                },
            )
        except Exception as exc:
            report_soft_error(
                component="SolverBase",
                event="snapshot_store_write",
                exc=exc,
                logger=logger,
                context_store=self.context_store,
                strict=bool(strict),
            )
            if strict:
                raise
            return None
        publication_kind = str(record.get("publication", "authority"))
        if publication_kind == "authority":
            plan = record.get("authority_commit")
            if not isinstance(plan, Mapping):
                if strict:
                    raise RuntimeError(
                        "authoritative Snapshot publication omitted its Authority fence"
                    )
                return None
            try:
                snapshot_identity = store.identity(handle)
                store.read_verified(snapshot_identity)
                authority_identity = self.authority_store.commit(
                    str(plan.get("authority_key", "")),
                    snapshot_identity,
                    expected_epoch=plan.get("expected_epoch"),
                    caused_by_event_identity=plan.get(
                        "caused_by_event_identity"
                    ),
                )
            except Exception as exc:
                report_soft_error(
                    component="SolverBase",
                    event="authority_store_commit",
                    exc=exc,
                    logger=logger,
                    context_store=self.context_store,
                    strict=bool(strict),
                )
                if strict:
                    raise
                return None
            self._latest_authority_identity = authority_identity
            self._last_evaluation_authority_after_edge = (
                authority_identity.as_dict()
            )

        if publication_kind == "evaluation_event":
            self._latest_evaluation_snapshot_handle = handle
        elif publication_kind == "evaluation_disposition":
            self._latest_evaluation_disposition_snapshot_handle = handle
        else:
            self._latest_snapshot_handle = handle
            self._snapshot_generation = record.get("generation")
        return handle

    def read_snapshot(self, key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        store = getattr(self, "snapshot_store", None)
        if store is None:
            return None
        snap_key = key
        if snap_key is None and self._latest_snapshot_handle is not None:
            snap_key = self._latest_snapshot_handle.key
        if not snap_key:
            return None
        try:
            record = store.read(str(snap_key))
        except Exception as exc:
            report_soft_error(
                component="SolverBase",
                event="snapshot_store_read",
                exc=exc,
                logger=logger,
                context_store=self.context_store,
                strict=bool(getattr(self, "snapshot_strict", False)),
            )
            return None
        if record is None:
            return None
        return dict(record.data)

    def get_last_evaluated_batch_snapshot(
        self,
    ) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray | None]:
        """Return an isolated event view, never an authoritative population.

        Partition-aware consumers use this only for audit/checkpoint evidence.
        Population selection must continue through the single or partitioned
        authority APIs instead of treating this event as solver state.
        """

        def _copy(value: Any) -> np.ndarray | None:
            return None if value is None else np.array(value, copy=True)

        return (
            _copy(None if self._last_evaluated_event_arrays is None else self._last_evaluated_event_arrays[0]),
            _copy(None if self._last_evaluated_event_arrays is None else self._last_evaluated_event_arrays[1]),
            _copy(None if self._last_evaluated_event_arrays is None else self._last_evaluated_event_arrays[2]),
        )

    def _strip_large_context(self, ctx: Dict[str, Any]) -> None:
        strip_large_context_fields(ctx)

    def _purge_large_context_store(self) -> None:
        store = getattr(self, "context_store", None)
        if store is None:
            return
        get_value = getattr(store, "get", None)
        if callable(get_value):
            try:
                inline_best = get_value(KEY_BEST_X, None)
                if inline_best is not None and not self._candidate_can_inline_in_context(
                    inline_best
                ):
                    store.delete(KEY_BEST_X)
            except Exception as exc:
                report_soft_error(
                    component="SolverBase",
                    event="context_store_delete_oversized_incumbent",
                    exc=exc,
                    logger=logger,
                    context_store=self.context_store,
                    strict=False,
                    level="debug",
                )
        for key in (
            KEY_POPULATION,
            KEY_OBJECTIVES,
            KEY_CONSTRAINT_VIOLATIONS,
            KEY_PARETO_SOLUTIONS,
            KEY_PARETO_OBJECTIVES,
            KEY_HISTORY,
            KEY_DECISION_TRACE,
        ):
            try:
                store.delete(key)
            except Exception as exc:
                report_soft_error(
                    component="SolverBase",
                    event="context_store_delete_large_object",
                    exc=exc,
                    logger=logger,
                    context_store=self.context_store,
                    strict=False,
                    level="debug",
                )
                continue

    def _attach_snapshot_refs(
        self,
        ctx: Dict[str, Any],
        *,
        allow_write: bool = True,
    ) -> None:
        handle = self._latest_snapshot_handle
        if handle is None and allow_write:
            pop = getattr(self, "population", None)
            obj = getattr(self, "objectives", None)
            vio = getattr(self, "constraint_violations", None)
            if pop is not None or obj is not None or vio is not None:
                self._persist_snapshot(
                    population=pop,
                    objectives=obj,
                    violations=vio,
                    include_pareto=True,
                    include_history=True,
                    include_decision_trace=True,
                    complete=obj is not None and vio is not None,
                )
                handle = self._latest_snapshot_handle
        if handle is None:
            return
        if str(getattr(self, "population_authority_mode", "single") or "single") == "partitioned":
            for key in (
                KEY_POPULATION_REF,
                KEY_OBJECTIVES_REF,
                KEY_CONSTRAINT_VIOLATIONS_REF,
            ):
                ctx.pop(key, None)
                try:
                    self.context_store.delete(key)
                except Exception as exc:
                    report_soft_error(
                        component="SolverBase",
                        event="partitioned_snapshot_ref_delete",
                        exc=exc,
                        logger=logger,
                        context_store=self.context_store,
                        strict=False,
                        level="debug",
                    )
        snapshot_refs = build_snapshot_refs(
                key=str(handle.key),
                backend=str(handle.backend),
                schema=str(handle.schema),
                meta=dict(handle.meta or {}),
                has_pareto_solutions=getattr(self, "pareto_solutions", None) is not None,
                has_pareto_objectives=getattr(self, "pareto_objectives", None) is not None,
                has_history=getattr(self, "history", None) is not None,
                has_decision_trace=getattr(self, "decision_trace", None) is not None,
                authority_mode=str(
                    getattr(self, "population_authority_mode", "single") or "single"
                ),
            )
        if dict(handle.meta or {}).get("population_shape") is None:
            for key in (
                KEY_POPULATION_REF,
                KEY_OBJECTIVES_REF,
                KEY_CONSTRAINT_VIOLATIONS_REF,
            ):
                snapshot_refs.pop(key, None)
                ctx.pop(key, None)
                try:
                    self.context_store.delete(key)
                except Exception as exc:
                    report_soft_error(
                        component="SolverBase",
                        event="empty_authority_snapshot_ref_delete",
                        exc=exc,
                        logger=logger,
                        context_store=self.context_store,
                        strict=False,
                        level="debug",
                    )
        ctx.update(snapshot_refs)

    def set_random_seed(self, seed: Optional[int]) -> None:
        self.random_seed = None if seed is None else int(seed)
        self._rng = np.random.default_rng(self.random_seed)
        self._rng_streams = {}
        representation = getattr(self, "representation_pipeline", None)
        representation_seed = getattr(representation, "set_random_seed", None)
        if callable(representation_seed):
            representation_seed(self.random_seed)
        if self.random_seed is not None:
            try:
                random.seed(self.random_seed)
            except Exception as exc:
                report_soft_error(
                    component="SolverBase",
                    event="set_python_random_seed",
                    exc=exc,
                    logger=logger,
                    context_store=self.context_store,
                    strict=False,
                    level="debug",
                )

    def fork_rng(self, stream: str = "") -> np.random.Generator:
        key = str(stream or "_default")
        existing = self._rng_streams.get(key)
        if existing is not None:
            return existing
        child_seed = int(self._rng.integers(0, 2**63 - 1))
        child = np.random.default_rng(child_seed)
        self._rng_streams[key] = child
        return child

    def get_rng_state(self) -> Dict[str, Any]:
        return {"bit_generator_state": self._rng.bit_generator.state}

    def set_rng_state(self, state: Dict[str, Any]) -> None:
        if not isinstance(state, dict):
            return
        bit_state = state.get("bit_generator_state")
        if bit_state is None:
            return
        try:
            self._rng.bit_generator.state = bit_state
        except Exception as exc:
            report_soft_error(
                component="SolverBase",
                event="set_rng_state",
                exc=exc,
                logger=logger,
                context_store=self.context_store,
                strict=False,
                level="debug",
            )
            return
        self._rng_streams = {}

    # ------------------------------------------------------------------
    # Evaluation helpers
    # ------------------------------------------------------------------
    def _apply_runtime_governance_context(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        monitor = getattr(self, "_convergence_monitor", None)
        if monitor is not None:
            ctx = monitor.on_context_build(self, ctx) or ctx
        governor = getattr(self, "_adaptive_governor", None)
        if governor is not None:
            ctx = governor.on_context_build(self, ctx) or ctx
        companion = getattr(self, "_companion_orchestrator", None)
        if companion is not None:
            ctx = companion.on_context_build(self, ctx) or ctx
        return ctx

    def _runtime_governance_on_solver_init(self) -> None:
        monitor = getattr(self, "_convergence_monitor", None)
        if monitor is not None:
            monitor.on_solver_init(self)
        governor = getattr(self, "_adaptive_governor", None)
        if governor is not None:
            governor.on_solver_init(self)
        companion = getattr(self, "_companion_orchestrator", None)
        if companion is not None:
            companion.on_solver_init(self)

    def _runtime_governance_on_population_init(
        self,
        population: np.ndarray,
        objectives: np.ndarray,
        violations: np.ndarray,
    ) -> None:
        monitor = getattr(self, "_convergence_monitor", None)
        if monitor is not None:
            monitor.on_population_init(population, objectives, violations)
        governor = getattr(self, "_adaptive_governor", None)
        if governor is not None:
            governor.on_population_init(population, objectives, violations)

    def _runtime_governance_on_generation_end(self, generation: int) -> None:
        monitor = getattr(self, "_convergence_monitor", None)
        if monitor is not None:
            monitor.on_generation_end(self, generation)
        governor = getattr(self, "_adaptive_governor", None)
        if governor is not None:
            governor.on_generation_end(self, generation)
        companion = getattr(self, "_companion_orchestrator", None)
        if companion is not None:
            companion.on_generation_end(self, generation)

    def _runtime_governance_on_solver_finish(self, result: Dict[str, Any]) -> None:
        monitor = getattr(self, "_convergence_monitor", None)
        if monitor is not None:
            monitor.on_solver_finish(self, result)
        governor = getattr(self, "_adaptive_governor", None)
        if governor is not None:
            governor.on_solver_finish(self, result)

    def build_context(
        self,
        individual_id: Optional[int] = None,
        constraints: Optional[np.ndarray] = None,
        violation: Optional[float] = None,
        individual: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        context = build_solver_context(
            self,
            individual_id=individual_id,
            constraints=constraints,
            violation=violation,
            individual=individual,
            report_soft_error_fn=report_soft_error,
            logger=logger,
        )
        for extension in self.semantic_extensions:
            projected = extension.project_context(self, context)
            if not isinstance(projected, Mapping):
                raise TypeError(f"{extension.name}.project_context must return a Mapping")
            context = dict(projected)
        from nsgablack.context_keys import KEY_SOLUTION_POOL_REF, KEY_SOLUTION_POOL_TIME
        context[KEY_SOLUTION_POOL_REF] = self.solution_pool.publication_ref()
        context[KEY_SOLUTION_POOL_TIME] = self.solution_pool.timestamp.as_dict()
        return context

    def get_context(self) -> Dict[str, Any]:
        """Return a snapshot context for visualization/monitoring."""
        return get_solver_context_view(
            self,
            report_soft_error_fn=report_soft_error,
            logger=logger,
        )

    def _ensure_snapshot_readable(self, ctx: Dict[str, Any]) -> None:
        ensure_snapshot_readable(self, ctx)

    def _get_best_snapshot(self) -> Tuple[Optional[Any], Optional[float]]:
        return get_best_snapshot_fields(
            self,
            report_soft_error_fn=report_soft_error,
            logger=logger,
        )

    def _collect_runtime_context_projection(self) -> Dict[str, Any]:
        return collect_runtime_context_projection(
            self,
            report_soft_error_fn=report_soft_error,
            logger=logger,
        )

    def _build_evaluation_evidence_journal(self) -> EvaluationEvidenceJournal:
        base_dir = self.snapshot_store_dir or "runs/snapshots"
        return create_evaluation_evidence_journal(
            backend=self.snapshot_store_backend,
            redis_url=self.snapshot_store_redis_url,
            key_prefix=f"{self.snapshot_store_key_prefix}:evaluation-evidence",
            base_dir=base_dir,
        )

    def _build_authority_store(self) -> AuthorityStore:
        base_dir = self.snapshot_store_dir or "runs/snapshots"
        return create_authority_store(
            self.snapshot_store_backend,
            redis_url=self.snapshot_store_redis_url,
            key_prefix=f"{self.snapshot_store_key_prefix}:authority",
            base_dir=base_dir,
        )

    def get_runtime_projection_audit(self) -> Dict[str, Any]:
        """Return lightweight evidence for the latest Adapter telemetry gate."""

        from blackbase.context import detach_context_value

        return detach_context_value(
            self._runtime_projection_audit,
            path="runtime_projection_audit",
        )

    def _dispatch_error_once(
        self,
        error: BaseException,
        *,
        phase: Optional[str] = None,
        context: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """Dispatch one lifecycle error at most once across nested boundaries."""

        if bool(getattr(error, "_nsgablack_error_dispatched", False)):
            return
        try:
            setattr(error, "_nsgablack_error_dispatched", True)
        except Exception as _fallback_error:
            _report_optional_failure(component=__name__, event='SolverBase._dispatch_error_once.fallback_153', exc=_fallback_error)
            pass
        if phase and not getattr(error, "_nsgablack_error_phase", None):
            try:
                setattr(error, "_nsgablack_error_phase", str(phase))
            except Exception as _fallback_error:
                _report_optional_failure(component=__name__, event='SolverBase._dispatch_error_once.fallback_156', exc=_fallback_error)
                pass
        try:
            error_context = dict(self.build_context() or {})
        except Exception:
            error_context = {}
        error_context.update(dict(context or {}))
        error_phase = getattr(error, "_nsgablack_error_phase", None)
        if error_phase:
            error_context["error_phase"] = str(error_phase)
        error_context.update(
            dict(getattr(error, "_nsgablack_error_context", {}) or {})
        )
        manager = getattr(self, "plugin_manager", None)
        if manager is None:
            return
        receipt = getattr(self, "_run_plugin_receipt", None)
        try:
            if isinstance(receipt, PluginLifecycleReceipt):
                manager.finish_lifecycle(
                    receipt,
                    "on_error",
                    error,
                    error_context,
                )
            else:
                on_error = getattr(manager, "on_error", None)
                if callable(on_error):
                    on_error(error, error_context)
        except BaseException as dispatch_error:
            failures = tuple(
                {
                    "plugin": str(name),
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
                for name, exc in tuple(
                    getattr(dispatch_error, "errors", ()) or ()
                )
            ) or (
                {
                    "plugin": "plugin_manager",
                    "error_type": type(dispatch_error).__name__,
                    "message": str(dispatch_error),
                },
            )
            try:
                setattr(error, "_nsgablack_on_error_failures", failures)
            except Exception as _fallback_error:
                _report_optional_failure(component=__name__, event='SolverBase._dispatch_error_once.fallback_157', exc=_fallback_error)
                pass
            add_note = getattr(error, "add_note", None)
            if callable(add_note):
                add_note(f"Plugin on_error handlers also failed: {failures!r}")
            logger.error(
                "Plugin on_error dispatch failed while preserving the primary error",
                exc_info=(
                    type(dispatch_error),
                    dispatch_error,
                    dispatch_error.__traceback__,
                ),
            )

    def evaluate_individual(self, x: np.ndarray, individual_id: Optional[int] = None) -> Tuple[np.ndarray, float]:
        try:
            self.checkpoint_case_runtime()
            result = evaluate_individual_with_plugins_and_bias(self, x, individual_id)
            self.checkpoint_case_runtime()
            return result
        except BaseException as exc:
            self._dispatch_error_once(
                exc,
                phase="evaluate_individual",
                context={"individual_id": individual_id},
            )
            raise

    def evaluate_population(self, population: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        try:
            self.checkpoint_case_runtime()
            result = evaluate_population_with_plugins_and_bias(self, population)
            self.checkpoint_case_runtime()
            return result
        except BaseException as exc:
            self._dispatch_error_once(exc, phase="evaluate_population")
            raise

    def get_last_feedback_batch(self) -> OptimizationFeedbackBatch | None:
        """Return the last rich batch without changing the legacy evaluate API."""

        batch = self._last_feedback_batch
        if batch is None:
            return None
        return batch.with_arrays(batch.objectives, batch.violations)

    def _apply_bias(
        self,
        obj: np.ndarray,
        x: np.ndarray,
        individual_id: Optional[int],
        context: Dict[str, Any],
    ) -> np.ndarray:
        return apply_bias_module(
            self,
            obj,
            x,
            individual_id,
            context,
            report_soft_error_fn=report_soft_error,
            logger=logger,
            normalize_bias_output_fn=normalize_bias_output,
        )

    # ------------------------------------------------------------------
    # Minimal runtime loop (override step() for custom logic)
    # ------------------------------------------------------------------
    def _apply_runtime_control_slot(self, slot: str) -> None:
        from .solver_helpers import apply_runtime_control_slot

        apply_runtime_control_slot(self, slot=str(slot))

    def register_state_participant(self, participant) -> None:
        from blackbase.runtime import validate_runtime_participant
        validate_runtime_participant(participant)
        if self.running:
            raise RuntimeError("cannot change state participants during a run")
        if any(item.name == participant.name for item in self._state_participants):
            raise ValueError(f"duplicate state participant: {participant.name}")
        self._state_participants.append(participant)

    def register_semantic_extension(self, extension: SolverSemanticExtension) -> None:
        if not isinstance(extension, SolverSemanticExtension):
            raise TypeError("semantic extension must implement SolverSemanticExtension")
        if self.running:
            raise RuntimeError("cannot change semantic extensions during a run")
        if any(item.name == extension.name for item in self.semantic_extensions):
            raise ValueError(f"duplicate semantic extension: {extension.name}")
        self.semantic_extensions.append(extension)

    def prepare_step_extensions(self) -> None:
        for extension in self.semantic_extensions:
            extension.before_step(self)

    def notify_step_committed(self, outcome: StepOutcome) -> StepOutcome:
        if not outcome.committed:
            return outcome
        failures = []
        for extension in self.semantic_extensions:
            try:
                extension.after_step_committed(self, outcome)
            except BaseException as exc:
                failures.append((extension.name, exc))
        if failures:
            raise CommittedStepError(outcome, failures) from failures[0][1]
        return outcome

    def request_stop(self, reason: str | None = None) -> None:
        self.stop_requested = True
        if reason is not None:
            self.stop_reason = str(reason)

    def should_execute_step(self, step_index: int) -> bool:
        """Pre-step predicate evaluated before generation hooks and counters."""

        remaining = self._run_progress_deadline_remaining_seconds
        if remaining is not None:
            current = float(remaining)
            if self._run_progress_clock_started_at is not None:
                current -= max(
                    0.0,
                    float(time.monotonic() - self._run_progress_clock_started_at),
                )
            if current <= 0.0:
                self.request_stop("logical_deadline")
                return False
        return all(extension.should_execute_step(self, step_index)
                   for extension in self.semantic_extensions)

    def queue_restore_envelope(
        self,
        apply: Callable[[], None],
        *,
        source: str = "external",
    ) -> None:
        return self.run_session.queue_restore_envelope(apply, source=source)

    def _apply_pending_restore_envelopes(self) -> None:
        return self.run_session._apply_pending_restore_envelopes()

    def _start_run_progress_clock(self) -> None:
        return self.run_session._start_run_progress_clock()

    def _merge_run_progress_deadline_with_case_control(self) -> None:
        """Clamp logical run time to the active parent Case authorization."""

        runtime = getattr(self, "case_runtime", None)
        control = getattr(runtime, "control", None)
        deadline_at = float(getattr(control, "deadline_at", 0.0) or 0.0)
        parent_remaining = (
            None
            if deadline_at <= 0
            else max(0.0, deadline_at - time.time())
        )
        checkpoint_remaining = self._run_progress_deadline_remaining_seconds
        candidates = [
            float(value)
            for value in (checkpoint_remaining, parent_remaining)
            if value is not None
        ]
        self._run_progress_deadline_remaining_seconds = (
            min(candidates) if candidates else None
        )

    def _pause_run_progress_clock(self) -> None:
        return self.run_session._pause_run_progress_clock()

    def _record_completed_run_step(self) -> None:
        return self.run_session._record_completed_run_step()

    def _record_run_step_attempt(self, status: str) -> None:
        return self.run_session._record_run_step_attempt(status)

    @property
    def run_progress_steps(self) -> int:
        return self.run_session.run_progress_steps

    @property
    def run_progress_attempts(self) -> int:
        return self.run_session.run_progress_attempts

    @property
    def run_progress_consecutive_idle_attempts(self) -> int:
        return self.run_session.run_progress_consecutive_idle_attempts

    @property
    def run_progress_elapsed_seconds(self) -> float:
        return self.run_session.run_progress_elapsed_seconds

    def export_run_progress_state(self) -> dict[str, Any]:
        return self.run_session.export_run_progress_state()

    def restore_run_progress_state(
        self,
        payload: Mapping[str, Any] | None,
    ) -> None:
        return self.run_session.restore_run_progress_state(payload)

    def setup(self) -> None:
        for extension in self.semantic_extensions:
            extension.setup(self)

    def checkpoint_components(self) -> Mapping[str, Any]:
        """Return stable stateful components owned by this control plane.

        Checkpoint plugins use this surface instead of knowing framework-
        specific Provider, schedule or Representation attributes.
        """

        components: dict[str, Any] = {}
        components["solution_pool"] = self.solution_pool
        adapter = getattr(self, "adapter", None)
        if adapter is not None:
            components["adapter"] = adapter
        representation = getattr(self, "representation_pipeline", None)
        if representation is not None:
            components["representation"] = representation
        components["runtime_controller"] = self.runtime_controller
        bias = self.bias_module
        if callable(getattr(bias, "get_state", None)) and callable(getattr(bias, "set_state", None)):
            components["bias"] = bias
        for extension in self.semantic_extensions:
            declared = extension.checkpoint_components(self)
            if not isinstance(declared, Mapping):
                raise TypeError(f"{extension.name}.checkpoint_components must return a Mapping")
            for name, component in declared.items():
                if not isinstance(name, str) or not name.strip():
                    raise ValueError("checkpoint component name must be non-empty")
                if name in components:
                    raise ValueError(f"duplicate checkpoint component owner: {name}")
                components[name] = component
        return components

    def step(self) -> StepOutcome:
        raise NotImplementedError(
            f"{type(self).__name__}.step() must return a StepOutcome"
        )

    def teardown(self) -> None:
        self._teardown_runtime(())

    def _teardown_runtime(self, operations) -> None:
        """Attempt every declared cleanup and preserve the first failure."""
        from blackbase.project import attach_failure_evidence

        pending = list(operations)
        failures = []
        for extension in self.semantic_extensions:
            try:
                declared = extension.cleanup_components(self)
                if not isinstance(declared, Mapping):
                    raise TypeError("cleanup_components must return a Mapping")
                for name, operation in declared.items():
                    if not isinstance(name, str) or not name.strip() or not callable(operation):
                        raise TypeError("cleanup component requires a name and callable")
                    pending.append((f"{extension.name}.{name}", operation))
            except BaseException as exc:
                failures.append((f"{extension.name}.cleanup_components", exc))
        for name, operation in pending:
            try:
                operation()
            except BaseException as exc:
                failures.append((name, exc))
        if failures:
            primary = failures[0][1]
            attach_failure_evidence(primary, "solver_teardown", [
                {"phase": name, "error_type": type(exc).__name__, "message": str(exc)}
                for name, exc in failures
            ])
            raise primary

    def run(
        self,
        max_steps: Optional[int] = None,
        *,
        max_step_attempts: Optional[int] = None,
    ) -> Dict[str, Any]:
        from ..utils.runtime_contracts import validate_runtime_contracts
        validate_runtime_contracts(self)
        self.validate_plugin_order()
        self.validate_control_plane()
        return run_solver_loop(
            self,
            max_steps=max_steps,
            max_step_attempts=max_step_attempts,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _random_candidate(self) -> np.ndarray:
        return sample_random_candidate(
            problem=self.problem,
            var_bounds=self.var_bounds,
            dimension=self.dimension,
            rng=self._rng,
        )
