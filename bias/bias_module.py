"""\
BiasModule - bias system facade.

Provides a solver-friendly wrapper around UniversalBiasManager with optional
caching and convenience helpers.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Callable, Dict, List, Optional
import copy
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
    KEY_INDIVIDUAL_ID,
    KEY_METRICS,
    KEY_POPULATION,
    KEY_PROBLEM_DATA,
)

logger = logging.getLogger(__name__)


class BiasModule:
    """Facade over UniversalBiasManager used by solvers and utilities."""
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Bias facade: aggregates algorithmic/domain bias contracts."

    def __init__(self):
        self._manager = UniversalBiasManager()

        # Runtime cache
        self._context_cache = None
        self.cache_enabled = True
        self.cache_max_items = 128
        self._bias_cache: "OrderedDict[Any, float]" = OrderedDict()
        self._bias_cache_version = 0

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
                cache_key = (
                    individual_id,
                    float(objective_value),
                    _x_bytes if _x_bytes is not None else np.asarray(x).tobytes(),
                    context.get(KEY_GENERATION, 0),
                    self._bias_cache_version,
                )
                cached = self._bias_cache.get(cache_key)
                if cached is not None:
                    self._bias_cache.move_to_end(cache_key)
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
            if len(self._bias_cache) >= self.cache_max_items:
                self._bias_cache.popitem(last=False)
            self._bias_cache[cache_key] = biased_value

        return biased_value

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
                    population=context.get(KEY_POPULATION, []),
                    metrics=metrics,
                    history=context.get(KEY_HISTORY, []),
                    problem_data=problem_data,
                )
            except Exception:
                return None

        try:
            ctx = copy.copy(self._context_cache)
            setattr(ctx, "generation", context.get(KEY_GENERATION, 0))
            setattr(ctx, "individual", x)
            setattr(ctx, "population", context.get(KEY_POPULATION, []))
            metrics = {
                "objective_value": objective_value,
                KEY_INDIVIDUAL_ID: individual_id,
                KEY_CONSTRAINT_VIOLATION: context.get(KEY_CONSTRAINT_VIOLATION, 0.0),
            }
            metrics.update(extra_metrics)
            setattr(ctx, "metrics", metrics)
            try:
                setattr(ctx, "history", context.get(KEY_HISTORY, []))
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
            self._bias_cache.clear()

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
