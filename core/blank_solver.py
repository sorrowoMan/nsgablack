"""
Solver control-plane scaffold for custom workflows.

This base class provides optional bias + representation integration without
enforcing any specific optimization loop.
"""

from __future__ import annotations

import logging
import random
import warnings
from typing import Any, Dict, Optional, Tuple

from .config import StorageConfig, _apply_storage_config

import numpy as np

from .base import BlackBoxProblem
from .interfaces import (
    BiasInterface,
    RepresentationInterface,
    has_bias_module,
    has_numba,
    load_bias_module,
    load_representation_pipeline,
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
    resolve_best_snapshot_fields,
    run_solver_loop,
    sample_random_candidate,
    set_best_snapshot_fields,
    set_generation_value,
    set_pareto_snapshot_fields,
    snapshot_meta,
    strip_large_context_fields,
)
from ..utils.context.context_keys import (
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
    KEY_SNAPSHOT_BACKEND,
    KEY_SNAPSHOT_META,
    KEY_SNAPSHOT_SCHEMA,
)
from ..utils.context.context_store import ContextStore
from ..utils.context.snapshot_store import SnapshotStore, make_snapshot_key
from ..utils.engineering.error_policy import report_soft_error
from ..utils.extension_contracts import (
    normalize_bias_output,
    normalize_candidate,
    stack_population,
)
from ..plugins import PluginManager

logger = logging.getLogger(__name__)


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
        # ----------------------------------------------------------------
        # Preferred: pass a single StorageConfig instead of the flat args.
        # If storage_config is provided, its fields override the flat args.
        # ----------------------------------------------------------------
        storage_config: Optional[StorageConfig] = None,
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
        snapshot_schema: str = "population_snapshot_v1",
    ) -> None:
        # Merge StorageConfig (if supplied) into local flat variables so the
        # rest of __init__ continues to read them by their original names.
        if storage_config is not None:
            _sc = _apply_storage_config(storage_config, {})
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
            snapshot_schema = _sc.get("snapshot_schema", snapshot_schema)
        # Keep reference so callers can introspect / rebuild config.
        self._storage_config = storage_config

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
            short_circuit=True,
            short_circuit_events=["evaluate_population", "evaluate_individual"],
            strict=bool(plugin_strict),
        )
        self._plugin_scheduler = ComponentDependencyScheduler()
        self.plugin_strict = bool(plugin_strict)
        self.snapshot_strict = bool(snapshot_strict)

        self.population = None
        self.objectives = None
        self.constraint_violations = None

        self.generation = 0
        self.evaluation_count = 0
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
        self.snapshot_schema = str(snapshot_schema or "population_snapshot_v1")
        self.snapshot_store: SnapshotStore = self._build_snapshot_store()
        self._latest_snapshot_handle = None
        self._snapshot_generation = None
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
        self.context_store = store

    def set_snapshot_store(self, store: SnapshotStore) -> None:
        self.snapshot_store = store

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
        self.context_store = self._build_context_store()

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
        if self._representation_internal is not None:
            return self._representation_internal
        if not hasattr(self, "_representation_cached"):
            self._representation_cached = load_representation_pipeline()
        return self._representation_cached

    @representation_pipeline.setter
    def representation_pipeline(self, value: Optional[RepresentationInterface]) -> None:
        self._representation_internal = value
        if value is not None and hasattr(self, "_representation_cached"):
            delattr(self, "_representation_cached")

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
        
        attach_success = False
        try:
            plugin.attach(self)
            attach_success = True
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
        
        # Call on_solver_init only if attach succeeded
        if attach_success:
            try:
                if hasattr(plugin, "on_solver_init"):
                    plugin.on_solver_init(self)
            except Exception as exc:
                strict_init = bool(getattr(plugin, "raise_on_init_error", False)) or bool(
                    getattr(plugin, "strict_init", False)
                )
                if strict_init:
                    raise
                try:
                    import warnings

                    warnings.warn(
                        f"Plugin '{plugin_name}' init failed: {exc}",
                        RuntimeWarning,
                        stacklevel=2,
                    )
                except Exception as warn_exc:
                    report_soft_error(
                        component="SolverBase",
                        event="plugin_init_warning_emit",
                        exc=warn_exc,
                        logger=logger,
                        context_store=self.context_store,
                        strict=False,
                        level="debug",
                    )
        
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

    # ------------------------------------------------------------------
    # Control-plane wiring helpers (preferred over direct attribute writes)
    # ------------------------------------------------------------------
    def set_adapter(self, adapter: Any) -> None:
        setattr(self, "adapter", adapter)

    def set_bias_module(self, bias_module: Optional[BiasInterface], enable: Optional[bool] = None) -> None:
        self.bias_module = bias_module
        if enable is not None:
            self.enable_bias = bool(enable)
            if bool(enable) and bias_module is None:
                # Explicit enable with no provided module: init default if available.
                self.init_bias_module()
        elif bias_module is not None:
            self.enable_bias = True

    def set_enable_bias(self, enable: bool) -> None:
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

    def set_best_snapshot(self, best_x: Any, best_objective: Any) -> None:
        set_best_snapshot_fields(
            self,
            best_x,
            best_objective,
            report_soft_error_fn=report_soft_error,
            logger=logger,
        )

    def set_pareto_snapshot(self, solutions: Any, objectives: Any) -> None:
        set_pareto_snapshot_fields(
            self,
            solutions,
            objectives,
            report_soft_error_fn=report_soft_error,
            logger=logger,
        )

    def resolve_best_snapshot(self) -> Tuple[Optional[Any], Optional[float]]:
        return self._resolve_best_snapshot()

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
        pipeline = self.representation_pipeline
        initializer = getattr(pipeline, "initializer", None) if pipeline is not None else None
        if pipeline is not None and initializer is not None:
            cand = pipeline.init(self.problem, context)
        else:
            cand = self._random_candidate()
        return normalize_candidate(cand, dimension=self.dimension, name="init_candidate")

    def mutate_candidate(self, x: np.ndarray, context: Optional[Dict[str, Any]] = None) -> np.ndarray:
        pipeline = self.representation_pipeline
        if pipeline is not None and getattr(pipeline, "mutator", None) is not None:
            out = pipeline.mutate(x, context)
        else:
            out = x
        return normalize_candidate(out, dimension=self.dimension, name="mutate_candidate")

    def repair_candidate(self, x: np.ndarray, context: Optional[Dict[str, Any]] = None) -> np.ndarray:
        pipeline = self.representation_pipeline
        if pipeline is not None and getattr(pipeline, "repair", None) is not None:
            out = pipeline.repair.repair(x, context)
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
        population = []
        for _ in range(size):
            population.append(self.init_candidate(context))
        self.population = stack_population(population, name="initialize_population.population")

        if evaluate:
            self.objectives, self.constraint_violations = self.evaluate_population(self.population)
            self.plugin_manager.on_population_init(
                self.population, self.objectives, self.constraint_violations
            )
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

    def _resolve_best_snapshot(self) -> Tuple[Optional[Any], Optional[float]]:
        return resolve_best_snapshot_fields(
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

    def evaluate_individual(self, x: np.ndarray, individual_id: Optional[int] = None) -> Tuple[np.ndarray, float]:
        return evaluate_individual_with_plugins_and_bias(self, x, individual_id)

    def evaluate_population(self, population: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        return evaluate_population_with_plugins_and_bias(self, population)

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
