"""\
BiasModule - bias system facade.

Provides a solver-friendly wrapper around UniversalBiasManager with optional
caching and convenience helpers.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Callable, Dict, List, Optional
import copy
import hashlib
import json
import logging
import threading

import numpy as np

from .core.base import AlgorithmicBias, DomainBias, OptimizationContext
from .core.manager import UniversalBiasManager
from ..utils.context.context_keys import (
    KEY_CONSTRAINTS,
    KEY_CONSTRAINT_VIOLATION,
    KEY_GENERATION,
    KEY_HISTORY,
    KEY_HISTORY_REF,
    KEY_INDIVIDUAL_ID,
    KEY_METRICS,
    KEY_POPULATION,
    KEY_POPULATION_REF,
    KEY_PROBLEM_DATA,
    KEY_SNAPSHOT_KEY,
    KEY_BIAS_CACHE_FINGERPRINT,
)
from ..utils.context.context_store import ContextStore
from ..utils.context.snapshot_store import SnapshotStore

logger = logging.getLogger(__name__)


class BiasModule:
    """Facade over UniversalBiasManager used by solvers and utilities."""
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Bias facade: aggregates algorithmic/domain bias contracts."

    def __init__(
        self,
        *,
        cache_backend: str = "memory",
        cache_ttl_seconds: Optional[float] = 3600.0,
        cache_key_prefix: str = "bias_cache",
        cache_context_keys: Optional[List[str]] = None,
        cache_include_generation: bool = True,
    ):
        self._manager = UniversalBiasManager()

        # Runtime cache
        self._context_cache = None
        self.cache_enabled = True
        self.cache_max_items = 128
        self._bias_cache: "OrderedDict[Any, float]" = OrderedDict()
        self._bias_cache_version = 0
        self.cache_backend = str(cache_backend or "memory").strip().lower()
        self.cache_ttl_seconds = cache_ttl_seconds
        self.cache_key_prefix = str(cache_key_prefix or "bias_cache").strip()
        self.cache_context_keys = tuple(cache_context_keys or ())
        self.cache_include_generation = bool(cache_include_generation)
        self._cache_context_store: Optional[ContextStore] = None
        self._snapshot_store: Optional[SnapshotStore] = None
        self._snapshot_cache_key: Optional[str] = None
        self._snapshot_cache_payload: Optional[Dict[str, Any]] = None

        # Track best
        self.enable = True
        self._name = "BiasModule"
        self.history_best_x = None
        self.history_best_f = float("inf")

        # Callback for cache invalidation when bias params change
        self._param_change_handler = self._on_bias_param_change
        self._lock = threading.RLock()

        # Optional context contract (defaults empty for compatibility).
        self.context_requires = tuple(getattr(self, "context_requires", ()) or ())
        self.context_provides = tuple(getattr(self, "context_provides", ()) or ())
        self.context_mutates = tuple(getattr(self, "context_mutates", ()) or ())
        self.context_cache = tuple(getattr(self, "context_cache", ()) or ())
        self.context_notes = getattr(self, "context_notes", None)

    def get_context_contract(self) -> Dict[str, Any]:
        requires = set(getattr(self, "context_requires", ()) or ())
        provides = set(getattr(self, "context_provides", ()) or ())
        mutates = set(getattr(self, "context_mutates", ()) or ())
        cache = set(getattr(self, "context_cache", ()) or ())
        notes = [str(getattr(self, "context_notes", "") or "").strip()]

        for mgr in (
            getattr(self._manager, "algorithmic_manager", None),
            getattr(self._manager, "domain_manager", None),
        ):
            if mgr is None:
                continue
            for bias in getattr(mgr, "biases", {}).values():
                if bias is None or not hasattr(bias, "get_context_contract"):
                    continue
                try:
                    sub = bias.get_context_contract() or {}
                except Exception:
                    continue
                requires.update(sub.get("requires", ()) or ())
                provides.update(sub.get("provides", ()) or ())
                mutates.update(sub.get("mutates", ()) or ())
                cache.update(sub.get("cache", ()) or ())
                note = str(sub.get("notes", "") or "").strip()
                if note:
                    notes.append(note)

        note_text = " | ".join(x for x in notes if x)
        return {
            "requires": sorted(requires),
            "provides": sorted(provides),
            "mutates": sorted(mutates),
            "cache": sorted(cache),
            "notes": note_text or None,
        }

    def set_context_store(self, store: Optional[ContextStore]) -> None:
        """Attach a context store for context-backed cache."""
        if store is None:
            return
        if store is self._cache_context_store:
            return
        self._cache_context_store = store

    def set_snapshot_store(self, store: Optional[SnapshotStore]) -> None:
        """Attach a snapshot store for large context artifacts."""
        if store is None:
            return
        if store is self._snapshot_store:
            return
        self._snapshot_store = store
        self._snapshot_cache_key = None
        self._snapshot_cache_payload = None

    def set_cache_backend(self, backend: str) -> None:
        self.cache_backend = str(backend or "memory").strip().lower()

    def set_cache_context_keys(self, keys: Optional[List[str]]) -> None:
        self.cache_context_keys = tuple(keys or ())

    def set_cache_include_generation(self, include: bool) -> None:
        self.cache_include_generation = bool(include)

    @classmethod
    def from_universal_manager(cls, manager: UniversalBiasManager) -> "BiasModule":
        bias_module = cls()
        bias_module._manager = manager
        bias_module._register_existing_bias_callbacks()
        return bias_module

    def add(self, bias, weight: float = 1.0, name: Optional[str] = None) -> bool:
        with self._lock:
            return self._add_unlocked(bias=bias, weight=weight, name=name)

    def _add_unlocked(self, bias, weight: float = 1.0, name: Optional[str] = None) -> bool:
        if isinstance(bias, dict):
            bias_type = bias.get("type", "algorithmic")
            bias_params = bias.get("params", {})
            bias_obj = self._create_bias_from_dict(bias_type, bias_params)
            if bias_obj is None:
                return False
            if isinstance(bias_obj, DomainBias):
                added = self._manager.add_domain_bias(bias_obj)
            else:
                added = self._manager.add_algorithmic_bias(bias_obj)
            if added:
                self._register_bias_callbacks(bias_obj)
                self._bump_cache_version()
            return added

        if isinstance(bias, AlgorithmicBias):
            added = self._manager.add_algorithmic_bias(bias)
            if added:
                self._register_bias_callbacks(bias)
                self._bump_cache_version()
            return added

        if isinstance(bias, DomainBias):
            added = self._manager.add_domain_bias(bias)
            if added:
                self._register_bias_callbacks(bias)
                self._bump_cache_version()
            return added

        if callable(bias):
            from .domain import RuleBasedBias

            rule_bias = RuleBasedBias(
                rule_func=bias,
                weight=weight,
                name=name or "functional_bias",
            )
            added = self._manager.add_domain_bias(rule_bias)
            if added:
                self._register_bias_callbacks(rule_bias)
                self._bump_cache_version()
            return added

        logger.warning("Unsupported bias type: %s", type(bias))
        return False

    def compute_bias(
        self,
        x: np.ndarray,
        objective_value: float,
        individual_id: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> float:
        if isinstance(individual_id, dict) and context is None:
            context = individual_id
            individual_id = 0

        if context is None:
            context = {}
        context.setdefault(KEY_CONSTRAINTS, [])
        context.setdefault(KEY_GENERATION, 0)

        x_bytes = None
        if self.cache_enabled:
            try:
                x_bytes = np.asarray(x).tobytes()
            except Exception:
                x_bytes = None

        with self._lock:
            biased_value = self._compute_bias_value(
                x=x,
                objective_value=objective_value,
                individual_id=int(individual_id) if individual_id is not None else 0,
                context=context,
                _x_bytes=x_bytes,
            )

            if objective_value < self.history_best_f:
                self.history_best_f = float(objective_value)
                self.history_best_x = np.asarray(x, dtype=float).copy()

        return biased_value

    def compute_bias_vector(
        self,
        x: np.ndarray,
        objective_values: np.ndarray,
        individual_id: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> np.ndarray:
        if context is None:
            context = {}
        context.setdefault(KEY_CONSTRAINTS, [])
        context.setdefault(KEY_GENERATION, 0)

        obj_arr = np.asarray(objective_values, dtype=float).reshape(-1)
        out = obj_arr.copy()
        ind_id = int(individual_id) if individual_id is not None else 0

        x_bytes = None
        if self.cache_enabled:
            try:
                x_bytes = np.asarray(x).tobytes()
            except Exception:
                x_bytes = None

        with self._lock:
            for k in range(out.size):
                out[k] = self._compute_bias_value(
                    x=x,
                    objective_value=float(out[k]),
                    individual_id=ind_id,
                    context=context,
                    _x_bytes=x_bytes,
                )

            try:
                best_obj = float(np.min(obj_arr))
            except Exception:
                best_obj = float(obj_arr[0]) if obj_arr.size else float("inf")
            if best_obj < self.history_best_f:
                self.history_best_f = best_obj
                self.history_best_x = np.asarray(x, dtype=float).copy()

        return out

    def compute_bias_batch(
        self,
        xs: np.ndarray,
        objectives: np.ndarray,
        individual_ids: Optional[np.ndarray] = None,
        contexts: Optional[List[Dict[str, Any]]] = None,
    ) -> np.ndarray:
        xs_arr = np.asarray(xs)
        obj_arr = np.asarray(objectives, dtype=float)
        if obj_arr.ndim == 1:
            obj_arr = obj_arr.reshape(-1, 1)

        n = obj_arr.shape[0]
        out = obj_arr.copy()
        if individual_ids is None:
            individual_ids = np.arange(n)

        for i in range(n):
            ctx = contexts[i] if contexts is not None else None
            out[i] = self.compute_bias_vector(
                xs_arr[i],
                out[i],
                individual_id=individual_ids[i],
                context=ctx,
            )

        return out

    def _compute_bias_value(
        self,
        x: np.ndarray,
        objective_value: float,
        individual_id: int,
        context: Dict[str, Any],
        _x_bytes: Optional[bytes] = None,
    ) -> float:
        cache_key = None
        if self.cache_enabled:
            try:
                cache_key = self._build_cache_key(
                    x=x,
                    objective_value=objective_value,
                    individual_id=individual_id,
                    context=context,
                    x_bytes=_x_bytes,
                )
                cached = self._cache_get(cache_key)
                if cached is not None:
                    return cached
            except Exception as exc:
                logger.warning("Bias cache key creation failed; bypass cache: %s", exc)
                cache_key = None

        opt_context = self._get_or_update_context(
            x=x,
            objective_value=objective_value,
            individual_id=individual_id,
            context=context,
        )
        if opt_context is None:
            return objective_value

        bias_info = self._manager.compute_total_bias(x, opt_context)
        total_bias = float(bias_info.get("total_bias", 0.0))
        biased_value = objective_value + total_bias

        if cache_key is not None:
            self._cache_set(cache_key, biased_value)

        return biased_value

    def _cache_get(self, key: Any) -> Optional[float]:
        if not self.cache_enabled:
            return None
        if self.cache_backend == "context_store" and self._cache_context_store is not None:
            try:
                return self._cache_context_store.get(str(key), default=None)
            except Exception:
                return None
        cached = self._bias_cache.get(key)
        if cached is not None:
            self._bias_cache.move_to_end(key)
        return cached

    def _cache_set(self, key: Any, value: float) -> None:
        if not self.cache_enabled:
            return
        if self.cache_backend == "context_store" and self._cache_context_store is not None:
            try:
                ttl = self.cache_ttl_seconds
                self._cache_context_store.set(str(key), float(value), ttl_seconds=ttl)
            except Exception:
                return
            return
        if len(self._bias_cache) >= self.cache_max_items:
            self._bias_cache.popitem(last=False)
        self._bias_cache[key] = float(value)

    def _build_cache_key(
        self,
        *,
        x: np.ndarray,
        objective_value: float,
        individual_id: int,
        context: Dict[str, Any],
        x_bytes: Optional[bytes],
    ) -> Any:
        bias_name = str(getattr(self, "_name", "BiasModule"))
        version = int(self._bias_cache_version)
        generation = int(context.get(KEY_GENERATION, 0)) if self.cache_include_generation else None
        ctx_fp = self._build_context_fingerprint(context)
        x_hash = self._hash_bytes(x_bytes if x_bytes is not None else np.asarray(x).tobytes())
        obj = float(objective_value)

        if self.cache_backend == "context_store":
            parts = [
                f"{self.cache_key_prefix}:{bias_name}",
                f"v={version}",
                f"id={int(individual_id)}",
                f"obj={repr(obj)}",
                f"x={x_hash}",
                f"ctx={ctx_fp}",
            ]
            if generation is not None:
                parts.insert(5, f"gen={generation}")
            return ":".join(parts)

        if generation is None:
            return (
                bias_name,
                version,
                int(individual_id),
                obj,
                x_hash,
                ctx_fp,
            )
        return (
            bias_name,
            version,
            int(individual_id),
            obj,
            x_hash,
            generation,
            ctx_fp,
        )

    def _build_context_fingerprint(self, context: Optional[Dict[str, Any]]) -> str:
        if not isinstance(context, dict):
            return ""
        if KEY_BIAS_CACHE_FINGERPRINT in context:
            try:
                return str(context.get(KEY_BIAS_CACHE_FINGERPRINT) or "")
            except Exception:
                return ""
        keys = tuple(self.cache_context_keys or ())
        if not keys:
            return ""
        payload = {str(k): context.get(k) for k in keys}
        return self._stable_hash(payload)

    @staticmethod
    def _hash_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @classmethod
    def _stable_hash(cls, value: Any) -> str:
        try:
            payload = json.dumps(cls._normalize_value(value), sort_keys=True, separators=(",", ":"))
        except Exception:
            try:
                payload = repr(value)
            except Exception:
                payload = f"<{type(value).__name__}>"
        return hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest()

    @classmethod
    def _normalize_value(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, bytes):
            return {"__bytes__": hashlib.sha256(value).hexdigest(), "len": len(value)}
        if isinstance(value, np.ndarray):
            return {
                "__ndarray__": True,
                "dtype": str(value.dtype),
                "shape": list(value.shape),
                "hash": cls._hash_bytes(value.tobytes()),
            }
        if isinstance(value, (list, tuple)):
            return [cls._normalize_value(v) for v in value]
        if isinstance(value, dict):
            return {str(k): cls._normalize_value(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
        return repr(value)

    def _resolve_snapshot_payload(self, context: Dict[str, Any]) -> Dict[str, Any]:
        store = self._snapshot_store
        if store is None:
            return {}
        key = None
        try:
            key = context.get(KEY_POPULATION_REF) or context.get(KEY_SNAPSHOT_KEY) or context.get(KEY_HISTORY_REF)
        except Exception:
            key = None
        if not key:
            return {}
        key_text = str(key)
        if key_text == self._snapshot_cache_key and self._snapshot_cache_payload is not None:
            return dict(self._snapshot_cache_payload)
        try:
            record = store.read(key_text)
        except Exception:
            record = None
        if record is None:
            return {}
        payload = dict(record.data)
        self._snapshot_cache_key = key_text
        self._snapshot_cache_payload = payload
        return payload

    def _get_or_update_context(
        self,
        x: np.ndarray,
        objective_value: float,
        individual_id: int,
        context: Dict[str, Any],
    ) -> Optional[OptimizationContext]:
        extra_metrics = context.get(KEY_METRICS, {})
        if not isinstance(extra_metrics, dict):
            extra_metrics = {}

        snapshot_payload = self._resolve_snapshot_payload(context)

        if self._context_cache is None:
            try:
                problem_data = context.get(KEY_PROBLEM_DATA, {})
                if not isinstance(problem_data, dict):
                    problem_data = {}
                else:
                    problem_data = dict(problem_data)
                if KEY_CONSTRAINTS in context:
                    problem_data.setdefault(KEY_CONSTRAINTS, context.get(KEY_CONSTRAINTS, []))

                metrics = {
                    "objective_value": objective_value,
                    KEY_INDIVIDUAL_ID: individual_id,
                    KEY_CONSTRAINT_VIOLATION: context.get(KEY_CONSTRAINT_VIOLATION, 0.0),
                }
                metrics.update(extra_metrics)

                self._context_cache = OptimizationContext(
                    generation=context.get(KEY_GENERATION, 0),
                    individual=x,
                    population=snapshot_payload.get(KEY_POPULATION, []),
                    metrics=metrics,
                    history=snapshot_payload.get(KEY_HISTORY, []),
                    problem_data=problem_data,
                )
            except Exception:
                return None

        try:
            ctx = copy.copy(self._context_cache)
            setattr(ctx, "generation", context.get(KEY_GENERATION, 0))
            setattr(ctx, "individual", x)
            setattr(ctx, "population", snapshot_payload.get(KEY_POPULATION, []))
            metrics = {
                "objective_value": objective_value,
                KEY_INDIVIDUAL_ID: individual_id,
                KEY_CONSTRAINT_VIOLATION: context.get(KEY_CONSTRAINT_VIOLATION, 0.0),
            }
            metrics.update(extra_metrics)
            setattr(ctx, "metrics", metrics)
            try:
                setattr(ctx, "history", snapshot_payload.get(KEY_HISTORY, []))
                problem_data = context.get(KEY_PROBLEM_DATA, {})
                if not isinstance(problem_data, dict):
                    problem_data = {}
                else:
                    problem_data = dict(problem_data)
                if KEY_CONSTRAINTS in context:
                    problem_data.setdefault(KEY_CONSTRAINTS, context.get(KEY_CONSTRAINTS, []))
                setattr(ctx, "problem_data", problem_data)
            except Exception:
                pass
            return ctx
        except Exception:
            logger.error("Failed to prepare optimization context", exc_info=True)
            return None

    def enable_all(self):
        if hasattr(self._manager, "enable_all"):
            self._manager.enable_all()
        else:
            if hasattr(self._manager, "algorithmic_manager"):
                self._manager.algorithmic_manager.enable_all()
            if hasattr(self._manager, "domain_manager"):
                self._manager.domain_manager.enable_all()

    def disable_all(self):
        if hasattr(self._manager, "disable_all"):
            self._manager.disable_all()
        else:
            if hasattr(self._manager, "algorithmic_manager"):
                self._manager.algorithmic_manager.disable_all()
            if hasattr(self._manager, "domain_manager"):
                self._manager.domain_manager.disable_all()

    def get_bias(self, name: str):
        if hasattr(self._manager, "algorithmic_manager"):
            bias = self._manager.algorithmic_manager.get_bias(name)
            if bias is not None:
                return bias
        if hasattr(self._manager, "domain_manager"):
            bias = self._manager.domain_manager.get_bias(name)
            if bias is not None:
                return bias
        return None

    def remove_bias(self, name: str) -> bool:
        with self._lock:
            return self._remove_bias_unlocked(name)

    def _remove_bias_unlocked(self, name: str) -> bool:
        if hasattr(self._manager, "algorithmic_manager"):
            if self._manager.algorithmic_manager.remove_bias(name):
                self._bump_cache_version()
                return True
        if hasattr(self._manager, "domain_manager"):
            if self._manager.domain_manager.remove_bias(name):
                self._bump_cache_version()
                return True
        return False

    def list_biases(self) -> List[str]:
        biases = []
        if hasattr(self._manager, "algorithmic_manager"):
            biases.extend(self._manager.algorithmic_manager.list_biases())
        if hasattr(self._manager, "domain_manager"):
            biases.extend(self._manager.domain_manager.list_biases())
        return biases

    def to_universal_manager(self) -> UniversalBiasManager:
        return self._manager

    @property
    def algorithmic_manager(self):
        return getattr(self._manager, "algorithmic_manager", None)

    @property
    def domain_manager(self):
        return getattr(self._manager, "domain_manager", None)

    def _create_bias_from_dict(self, bias_type: str, params: Dict[str, Any]):
        try:
            from .algorithmic import (
                DiversityBias,
                ConvergenceBias,
                TabuSearchBias,
                PrecisionBias,
            )
            from .domain import ConstraintBias

            bias_map = {
                "diversity": (DiversityBias, params),
                "convergence": (ConvergenceBias, params),
                "tabu_search": (TabuSearchBias, params),
                "precision": (PrecisionBias, params),
                "constraint": (ConstraintBias, params),
            }

            if bias_type in bias_map:
                bias_class, bias_params = bias_map[bias_type]
                return bias_class(**bias_params)
        except Exception as exc:
            logger.warning("Could not import bias class: %s", exc)
        return None

    def clear(self):
        with self._lock:
            self._clear_unlocked()

    def _clear_unlocked(self):
        try:
            algo_mgr = getattr(self._manager, "algorithmic_manager", None)
            dom_mgr = getattr(self._manager, "domain_manager", None)
            if algo_mgr is not None and hasattr(algo_mgr, "biases"):
                algo_mgr.biases.clear()
            if dom_mgr is not None and hasattr(dom_mgr, "biases"):
                dom_mgr.biases.clear()
        except Exception:
            pass
        self.history_best_x = None
        self.history_best_f = float("inf")
        self._context_cache = None
        self._bump_cache_version()

    def __repr__(self):
        return f"BiasModule(biases={self.list_biases()}, enabled={self.enable})"

    def clear_cache(self):
        with self._lock:
            self._bump_cache_version()

    def _bump_cache_version(self):
        # caller holds lock when mutating bias/cache state
        self._bias_cache_version += 1
        self._bias_cache.clear()

    def _register_bias_callbacks(self, bias: Any):
        if bias is None:
            return
        try:
            register = getattr(bias, "register_param_change_callback", None)
            if callable(register):
                register(self._param_change_handler)
        except Exception:
            logger.debug(
                "Failed to register param change callback for bias %s",
                getattr(bias, "name", "<unknown>"),
                exc_info=True,
            )

    def _register_existing_bias_callbacks(self):
        for mgr in (
            getattr(self._manager, "algorithmic_manager", None),
            getattr(self._manager, "domain_manager", None),
        ):
            if mgr is None:
                continue
            for bias in getattr(mgr, "biases", {}).values():
                self._register_bias_callbacks(bias)

    def _on_bias_param_change(self, bias: Any):
        with self._lock:
            self._bump_cache_version()


def proximity_reward(x: np.ndarray, best_x: np.ndarray) -> float:
    distance = float(np.linalg.norm(np.asarray(x) - np.asarray(best_x)))
    return 1.0 / (1.0 + distance)


def improvement_reward(current_f: float, previous_f: float) -> float:
    return max(0.0, float(previous_f) - float(current_f))


def create_bias_module() -> BiasModule:
    return BiasModule()


def from_universal_manager(manager: UniversalBiasManager) -> BiasModule:
    return BiasModule.from_universal_manager(manager)
