"""
Solver control-plane scaffold for custom workflows.

This base class provides optional bias + representation integration without
enforcing any specific optimization loop.
"""

from __future__ import annotations

import json
import logging
import random
import threading
import uuid
import warnings
import weakref
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

from .acceleration import AccelerationFacade, AccelerationRegistry, ExecutionResult
from .acceleration_helpers import maybe_accel_map, maybe_accel_run
from blackbase.context import StateStoreConfig
from .control_plane import (
    BaseController,
    ControlArbiter,
    EvaluationBudgetExceeded,
    RuntimeController,
)
from .evaluation_runtime import EvaluationMediator, EvaluationMediatorConfig, EvaluationProvider
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

import numpy as np

from blackbase.resources import (
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
    ComponentDependencyScheduler,
    apply_bias_module,
    build_context_store_or_memory,
    build_solver_context,
    build_snapshot_store_or_memory,
    build_snapshot_payload,
    build_snapshot_refs,
    collect_runtime_context_projection,
    ensure_snapshot_readable,
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
)
from blackbase.context.context_keys import (
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
from blackbase.plugin import report_soft_error
from ..utils.extension_contracts import (
    normalize_bias_output,
    normalize_candidate,
    stack_population,
)
from ..plugins import PluginManager

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _IncumbentCommit:
    """One authoritative in-memory incumbent commit."""

    state: IncumbentState | None
    candidate_ref: str | None
    revision: int


class SolverBase:
    """
    A minimal solver base that keeps the framework contracts intact.

    - Uses BlackBoxProblem for evaluation.
    - Optional bias_module and representation_pipeline.
    - No built-in optimization loop (step() is user/plugin defined).
    """

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
        snapshot_store_backend: str = "memory",
        snapshot_store_ttl_seconds: Optional[float] = None,
        snapshot_store_redis_url: str = "redis://localhost:6379/0",
        snapshot_store_key_prefix: str = "nsgablack:snapshot",
        snapshot_store_dir: Optional[str] = None,
        snapshot_store_serializer: str = "safe",
        snapshot_store_hmac_env_var: str = "NSGABLACK_SNAPSHOT_HMAC_KEY",
        snapshot_store_unsafe_allow_unsigned: bool = False,
        snapshot_store_max_payload_bytes: int = 8_388_608,
        context_inline_candidate_max_bytes: int = 4_096,
        runtime_context_projection_field_max_bytes: int = 4_096,
        runtime_context_projection_total_max_bytes: int = 32_768,
        snapshot_schema: str = "population_snapshot_v1",
        enable_convergence_monitor: bool = False,
        convergence_config: Optional[ConvergenceConfig] = None,
        enable_adaptive_parameters: bool = False,
        adaptive_config: Optional[AdaptiveParametersConfig] = None,
        enable_companion_orchestrator: bool = False,
        companion_config: Optional[CompanionOrchestratorConfig] = None,
    ) -> None:
        # Project the shared config (if supplied) into local store settings.
        # rest of __init__ continues to read them by their original names.
        if storage_config is not None:
            _sc = storage_config.as_dict()
            context_store_backend = _sc.get("context_store_backend", context_store_backend)
            context_store_ttl_seconds = _sc.get("context_store_ttl_seconds", context_store_ttl_seconds)
            context_store_redis_url = _sc.get("context_store_redis_url", context_store_redis_url)
            context_store_key_prefix = _sc.get("context_store_key_prefix", context_store_key_prefix)
            snapshot_store_backend = _sc.get("snapshot_store_backend", snapshot_store_backend)
            snapshot_store_ttl_seconds = _sc.get("snapshot_store_ttl_seconds", snapshot_store_ttl_seconds)
            snapshot_store_redis_url = _sc.get("snapshot_store_redis_url", snapshot_store_redis_url)
            snapshot_store_key_prefix = _sc.get("snapshot_store_key_prefix", snapshot_store_key_prefix)
            snapshot_store_dir = _sc.get("snapshot_store_dir", snapshot_store_dir)
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
        self._incumbent_candidate_ref: Optional[str] = None
        self._incumbent_context_projection_revision = 0
        self._incumbent_context_projection_error: Optional[Dict[str, Any]] = None
        self._restored_incumbent_projection_audit: Optional[Dict[str, Any]] = None
        self._runtime_projection_audit: Dict[str, Any] = {}
        self._runtime_projection_audit_report_signature: Any = None

        self.generation = 0
        self.evaluation_count = 0
        self._evaluation_budget = BudgetAccount.from_resource_context(
            "evaluations",
            self.resource_context,
        )
        self.running = False
        self.stop_requested = False
        self.max_steps = 1
        self.start_time = 0.0
        self.random_seed: Optional[int] = None
        self._rng = np.random.default_rng()
        self._rng_streams: Dict[str, np.random.Generator] = {}
        self.context_store_backend = str(context_store_backend or "memory")
        self.context_store_ttl_seconds = context_store_ttl_seconds
        self.context_store_redis_url = str(context_store_redis_url)
        self.context_store_key_prefix = str(context_store_key_prefix)
        self.context_store: ContextStore = self._build_context_store()
        self.snapshot_store_backend = str(snapshot_store_backend or "memory")
        self.snapshot_store_ttl_seconds = snapshot_store_ttl_seconds
        self.snapshot_store_redis_url = str(snapshot_store_redis_url)
        self.snapshot_store_key_prefix = str(snapshot_store_key_prefix)
        self.snapshot_store_dir = snapshot_store_dir
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
        self.snapshot_schema = str(snapshot_schema or "population_snapshot_v1")
        self.snapshot_store: SnapshotStore = self._build_snapshot_store()
        self._latest_snapshot_handle = None
        self._snapshot_generation = None
        self.snapshot_pre_evaluate_population = False
        self.context_store_update_on_build = True
        self._pending_plugin_order_updates: list[dict[str, Any]] = []

    def _build_context_store(self) -> ContextStore:
        return build_context_store_or_memory(
            backend=self.context_store_backend,
            ttl_seconds=self.context_store_ttl_seconds,
            redis_url=self.context_store_redis_url,
            key_prefix=self.context_store_key_prefix,
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

    def set_snapshot_store(self, store: SnapshotStore) -> None:
        self.snapshot_store = store

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
            except Exception:
                continue

    def prepare_fresh_run(self) -> None:
        """Reset state owned by one run without discarding explicit warm starts."""

        self._run_sequence = int(getattr(self, "_run_sequence", 0)) + 1
        run_scope = self._case_run_id() or f"solver-{id(self):x}"
        run_nonce = uuid.uuid4().hex[:12]
        self._active_run_id = (
            f"{run_scope}:solver-run:{self._run_sequence}:{run_nonce}"
        )
        self._runtime_projection_audit = {}
        self._runtime_projection_audit_report_signature = None
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
        self.pareto_solutions = None
        self.pareto_objectives = None
        self.history = []
        self.last_result = None
        self._latest_snapshot_handle = None
        self._snapshot_generation = None
        self._consumed_warm_starts = []
        self._proposal_sequence = 0
        self._candidate_sequence = 0
        with self._candidate_provenance_lock:
            self._candidate_provenance_by_object = {}
        self._active_candidate_provenance = []
        self._active_candidate_population_ref = None
        if hasattr(self, "last_step_summary"):
            self.last_step_summary = {}
        if hasattr(self, "scalarizer_fallback_count"):
            self.scalarizer_fallback_count = 0
        if hasattr(self, "result_quality_degraded"):
            self.result_quality_degraded = False
        if hasattr(self, "scalarizer_audit_complete"):
            self.scalarizer_audit_complete = True

    def get_resource_context(self) -> ResourceContext:
        return self.resource_context

    def set_case_runtime(self, runtime: Any) -> "SolverBase":
        """Accept the shared Case runtime without importing Project internals."""

        self.case_runtime = runtime
        return self

    def checkpoint_case_runtime(self) -> None:
        runtime = self.case_runtime
        checkpoint = getattr(runtime, "checkpoint", None)
        if callable(checkpoint):
            checkpoint()

    def export_case_result(self, raw_output: Any):
        """Project a completed Solver run into the shared Case result codec."""

        from .solver_result import build_solver_result

        return build_solver_result(self, raw_output)

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
    ) -> None:
        self.context_store_backend = str(backend or "memory")
        if ttl_seconds is not None:
            self.context_store_ttl_seconds = ttl_seconds
        if redis_url is not None:
            self.context_store_redis_url = str(redis_url)
        if key_prefix is not None:
            self.context_store_key_prefix = str(key_prefix)
        self.set_context_store(self._build_context_store())

    def set_snapshot_store_backend(
        self,
        backend: str,
        *,
        ttl_seconds: Optional[float] = None,
        redis_url: Optional[str] = None,
        key_prefix: Optional[str] = None,
        base_dir: Optional[str] = None,
        serializer: Optional[str] = None,
        hmac_env_var: Optional[str] = None,
        unsafe_allow_unsigned: Optional[bool] = None,
        max_payload_bytes: Optional[int] = None,
    ) -> None:
        self.snapshot_store_backend = str(backend or "memory")
        if ttl_seconds is not None:
            self.snapshot_store_ttl_seconds = ttl_seconds
        if redis_url is not None:
            self.snapshot_store_redis_url = str(redis_url)
        if key_prefix is not None:
            self.snapshot_store_key_prefix = str(key_prefix)
        if base_dir is not None:
            self.snapshot_store_dir = str(base_dir)
        if serializer is not None:
            self.snapshot_store_serializer = str(serializer)
        if hmac_env_var is not None:
            self.snapshot_store_hmac_env_var = str(hmac_env_var)
        if unsafe_allow_unsigned is not None:
            self.snapshot_store_unsafe_allow_unsigned = bool(unsafe_allow_unsigned)
        if max_payload_bytes is not None:
            self.snapshot_store_max_payload_bytes = int(max_payload_bytes)
        self.snapshot_store = self._build_snapshot_store()

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
            metadata=dict(metadata or {}),
        )

    def _register_candidate_provenance(
        self,
        candidate: Any,
        provenance: CandidateProvenance,
    ) -> None:
        array = np.asarray(candidate)
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
        current = np.asarray(candidate)
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
                    metadata=provenance.metadata,
                )
            self._register_candidate_provenance(candidate, provenance)
            out.append(provenance)
        return out

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
    def init_candidate(self, context: Optional[Dict[str, Any]] = None) -> np.ndarray:
        warm_start = self._take_warm_start_candidate()
        if warm_start is not None:
            return normalize_candidate(
                warm_start,
                dimension=self.dimension,
                name="warm_start.candidate",
            )
        pipeline = self.representation_pipeline
        initializer = None
        if pipeline is not None:
            initializer = getattr(pipeline, "initializer", None)
            if initializer is None:
                initializer = getattr(pipeline, "_initializer", None)
        if pipeline is not None and initializer is not None:
            init_fn = getattr(pipeline, "init", None)
            if not callable(init_fn):
                raise TypeError("representation pipeline must expose init(context)")
            init_context = dict(context or self.build_context())
            init_context[KEY_PROBLEM] = self.problem
            cand = init_fn(init_context)
        else:
            cand = self._random_candidate()
        return normalize_candidate(cand, dimension=self.dimension, name="init_candidate")

    def mutate_candidate(self, x: np.ndarray, context: Optional[Dict[str, Any]] = None) -> np.ndarray:
        pipeline = self.representation_pipeline
        mutator = None
        if pipeline is not None:
            mutator = getattr(pipeline, "mutator", None)
            if mutator is None:
                mutator = getattr(pipeline, "_mutator", None)
        if pipeline is not None and mutator is not None:
            out = pipeline.mutate(x, context)
        else:
            out = x
        return normalize_candidate(out, dimension=self.dimension, name="mutate_candidate")

    def repair_candidate(self, x: np.ndarray, context: Optional[Dict[str, Any]] = None) -> np.ndarray:
        pipeline = self.representation_pipeline
        if pipeline is not None and getattr(pipeline, "repair", None) is not None:
            repair_one = getattr(pipeline, "repair_one", None)
            if callable(repair_one):
                out = repair_one(x, context)
            else:
                out = pipeline.repair(x, context)
        else:
            out = x
        return normalize_candidate(out, dimension=self.dimension, name="repair_candidate")

    def encode_candidate(self, x: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        pipeline = self.representation_pipeline
        if pipeline is not None and getattr(pipeline, "encoder", None) is not None:
            return pipeline.encode(x, context)
        return x

    def decode_candidate(self, x: Any, context: Optional[Dict[str, Any]] = None) -> Any:
        """Decode a candidate from encoded space back to decision space.

        Capability check: looks for an explicit ``decode`` method on the
        pipeline (or its ``encoder`` component), **not** merely the presence
        of an ``encoder`` attribute.  This avoids silently returning the raw
        encoded value when only encoding (not decoding) is implemented.
        """
        pipeline = self.representation_pipeline
        if pipeline is None:
            return x
        # Prefer a decode method directly on the pipeline.
        decode_fn = getattr(pipeline, "decode", None)
        if callable(decode_fn):
            return decode_fn(x, context)
        # Fall back: look for decoder capability on the encoder sub-component.
        encoder_comp = getattr(pipeline, "encoder", None)
        if encoder_comp is not None:
            sub_decode = getattr(encoder_comp, "decode", None)
            if callable(sub_decode):
                return sub_decode(x, context)
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
        return self.population

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
        self.population = pop
        self.objectives = obj
        self.constraint_violations = vio
        self._persist_snapshot(
            population=pop,
            objectives=obj,
            violations=vio,
            include_pareto=True,
            include_history=True,
            include_decision_trace=True,
        )
        return True

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
        return snapshot_meta(
            population,
            objectives,
            violations,
            pareto_solutions=pareto_solutions,
            pareto_objectives=pareto_objectives,
            complete=complete,
        )

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
        return build_snapshot_payload(
            population,
            objectives,
            violations,
            pareto_solutions=pareto_solutions,
            pareto_objectives=pareto_objectives,
            history=history,
            decision_trace=decision_trace,
        )

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
    ) -> None:
        store = getattr(self, "snapshot_store", None)
        if store is None:
            return
        try:
            if population is None:
                population = getattr(self, "population", None)
            if objectives is None:
                objectives = getattr(self, "objectives", None)
            if violations is None:
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
        if key is None and self._latest_snapshot_handle is not None:
            if self._snapshot_generation == gen:
                key = self._latest_snapshot_handle.key
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
        # Cancellation/deadline must win before a durable snapshot commit.
        self.checkpoint_case_runtime()
        try:
            handle = store.write(
                payload,
                key=key,
                meta=meta,
                schema=self.snapshot_schema,
                ttl_seconds=self.snapshot_store_ttl_seconds,
            )
        except Exception as exc:
            report_soft_error(
                component="SolverBase",
                event="snapshot_store_write",
                exc=exc,
                logger=logger,
                context_store=self.context_store,
                strict=bool(getattr(self, "snapshot_strict", False)),
            )
            return
        self._latest_snapshot_handle = handle
        self._snapshot_generation = gen

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
            except Exception:
                pass
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
        ctx.update(
            build_snapshot_refs(
                key=str(handle.key),
                backend=str(handle.backend),
                schema=str(handle.schema),
                meta=dict(handle.meta or {}),
                has_pareto_solutions=getattr(self, "pareto_solutions", None) is not None,
                has_pareto_objectives=getattr(self, "pareto_objectives", None) is not None,
                has_history=getattr(self, "history", None) is not None,
                has_decision_trace=getattr(self, "decision_trace", None) is not None,
            )
        )

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
        return build_solver_context(
            self,
            individual_id=individual_id,
            constraints=constraints,
            violation=violation,
            individual=individual,
            report_soft_error_fn=report_soft_error,
            logger=logger,
        )

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
        except Exception:
            pass
        if phase and not getattr(error, "_nsgablack_error_phase", None):
            try:
                setattr(error, "_nsgablack_error_phase", str(phase))
            except Exception:
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
        on_error = getattr(manager, "on_error", None)
        if callable(on_error):
            on_error(error, error_context)

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

    def request_stop(self) -> None:
        self.stop_requested = True

    def setup(self) -> None:
        return None

    def step(self) -> None:
        return None

    def teardown(self) -> None:
        return None

    def run(self, max_steps: Optional[int] = None) -> Dict[str, Any]:
        self.validate_plugin_order()
        self.validate_control_plane()
        return run_solver_loop(self, max_steps=max_steps)

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
