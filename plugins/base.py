"""Plugin base classes and plugin manager."""

from __future__ import annotations

from abc import ABC
import copy
import time
import traceback
import warnings
from typing import Any, Dict, Mapping, Optional

import numpy as np

from ..utils.context.context_keys import (
    KEY_CONSTRAINT_VIOLATIONS,
    KEY_OBJECTIVES,
    KEY_POPULATION,
)


class Plugin(ABC):
    """Base class for all plugins."""

    # Optional context contract metadata (class-level defaults)
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = None

    def __init__(self, name: str, solver=None, priority: int = 0):
        """Create a plugin.

        Args:
            name: Plugin name.
            solver: Optional solver instance; can also be attached later.
            priority: Larger values run earlier.
        """
        self.name = name
        self.solver = solver
        self.enabled = True
        self.config: Dict[str, Any] = {}
        self.priority = priority

        # Optional semantics:
        # - is_algorithmic=True: plugin affects search behavior and should be audited.
        # - get_report(): returns a small dict persisted by reporting plugins.
        self.is_algorithmic = False
        self._profile = {"total_s": 0.0, "events": {}}

    def get_context_contract(self) -> Dict[str, Any]:
        """Return context contract metadata for this plugin."""
        return {
            "requires": getattr(self, "context_requires", ()),
            "provides": getattr(self, "context_provides", ()),
            "mutates": getattr(self, "context_mutates", ()),
            "cache": getattr(self, "context_cache", ()),
            "notes": getattr(self, "context_notes", None),
        }

    def create_local_rng(self, seed: Optional[int] = None, solver: Any = None) -> np.random.Generator:
        """Create a plugin-local RNG."""
        if seed is not None:
            return np.random.default_rng(int(seed))
        target = solver if solver is not None else self.solver
        if target is not None:
            fork = getattr(target, "fork_rng", None)
            if callable(fork):
                try:
                    rng = fork(self.name)
                    if isinstance(rng, np.random.Generator):
                        return rng
                except Exception:
                    pass
        return np.random.default_rng()

    def attach(self, solver):
        """Attach this plugin to a solver."""
        self.solver = solver

    def detach(self):
        """Detach this plugin from its solver."""
        self.solver = None

    def enable(self):
        """Enable this plugin."""
        self.enabled = True

    def disable(self):
        """Disable this plugin."""
        self.enabled = False

    def configure(self, **kwargs):
        """Update plugin config."""
        self.config.update(kwargs)

    def get_config(self, key: str, default=None):
        """Get one config value."""
        return self.config.get(key, default)

    # Lifecycle hooks (optional)
    def on_solver_init(self, solver):
        return None

    def on_population_init(self, population, objectives, violations):
        return None

    def on_generation_start(self, generation: int):
        return None

    def on_generation_end(self, generation: int):
        return None

    def on_step(self, solver, generation: int):
        return None

    def on_solver_finish(self, result: Dict[str, Any]):
        return None

    def get_report(self) -> Optional[Dict[str, Any]]:
        """Return a small algorithmic report; tool-only plugins should return None."""
        if not bool(getattr(self, "is_algorithmic", False)):
            return None
        try:
            return {"config": dict(self.config)}
        except Exception:
            return {"config": {}}

    def resolve_population_snapshot(self, solver=None):
        """Return (population, objectives, violations) with adapter-first fallback order.

        Priority:
        1) adapter.get_population()
        2) adapter runtime context projection
        3) solver.{population, objectives, constraint_violations}
        """
        target = solver if solver is not None else self.solver
        if target is None:
            return np.zeros((0, 0), dtype=float), np.zeros((0, 0), dtype=float), np.zeros((0,), dtype=float)

        adapter = getattr(target, "adapter", None)
        if adapter is not None:
            getter = getattr(adapter, "get_population", None)
            if callable(getter):
                try:
                    x, f, v = getter()
                    x_arr = np.asarray(x, dtype=float)
                    f_arr = np.asarray(f, dtype=float)
                    v_arr = np.asarray(v, dtype=float).reshape(-1)
                    if x_arr.ndim == 1:
                        x_arr = x_arr.reshape(1, -1) if x_arr.size > 0 else x_arr.reshape(0, 0)
                    if f_arr.ndim == 1:
                        f_arr = f_arr.reshape(-1, 1) if f_arr.size > 0 else f_arr.reshape(0, 0)
                    return x_arr, f_arr, v_arr
                except Exception:
                    pass
            projector = getattr(adapter, "get_runtime_context_projection", None)
            if callable(projector):
                try:
                    projection = projector(target)
                except Exception:
                    projection = None
                if isinstance(projection, dict):
                    try:
                        x = np.asarray(projection.get(KEY_POPULATION, np.zeros((0, 0))), dtype=float)
                        f = np.asarray(projection.get(KEY_OBJECTIVES, np.zeros((0, 0))), dtype=float)
                        v = np.asarray(
                            projection.get(KEY_CONSTRAINT_VIOLATIONS, np.zeros((0,))),
                            dtype=float,
                        ).reshape(-1)
                        if x.ndim == 1:
                            x = x.reshape(1, -1) if x.size > 0 else x.reshape(0, 0)
                        if f.ndim == 1:
                            f = f.reshape(-1, 1) if f.size > 0 else f.reshape(0, 0)
                        if x.size > 0 or f.size > 0:
                            return x, f, v
                    except Exception:
                        pass

        x = np.asarray(getattr(target, "population", np.zeros((0, 0))), dtype=float)
        f = np.asarray(getattr(target, "objectives", np.zeros((0, 0))), dtype=float)
        v = np.asarray(getattr(target, "constraint_violations", np.zeros((0,))), dtype=float).reshape(-1)
        if x.ndim == 1:
            x = x.reshape(1, -1) if x.size > 0 else x.reshape(0, 0)
        if f.ndim == 1:
            f = f.reshape(-1, 1) if f.size > 0 else f.reshape(0, 0)
        return x, f, v

    def commit_population_snapshot(
        self,
        population,
        objectives,
        violations,
        solver=None,
    ) -> bool:
        """Write back updated population snapshot.

        Priority:
        1) adapter.set_population / set_population_snapshot / update_population
        2) solver.write_population_snapshot(...) protocol
        """
        target = solver if solver is not None else self.solver
        if target is None:
            return False

        try:
            x_arr = np.asarray(population, dtype=float)
            f_arr = np.asarray(objectives, dtype=float)
            v_arr = np.asarray(violations, dtype=float).reshape(-1)
        except Exception:
            return False

        if x_arr.ndim == 1:
            x_arr = x_arr.reshape(1, -1) if x_arr.size > 0 else x_arr.reshape(0, 0)
        if f_arr.ndim == 1:
            f_arr = f_arr.reshape(-1, 1) if f_arr.size > 0 else f_arr.reshape(0, 0)

        adapter = getattr(target, "adapter", None)
        if adapter is not None:
            for method_name in ("set_population", "set_population_snapshot", "update_population"):
                setter = getattr(adapter, method_name, None)
                if not callable(setter):
                    continue
                try:
                    handled = setter(x_arr, f_arr, v_arr)
                except TypeError:
                    try:
                        handled = setter(target, x_arr, f_arr, v_arr)
                    except Exception:
                        handled = False
                except Exception:
                    handled = False
                if handled is not False:
                    return True

        writer = getattr(target, "write_population_snapshot", None)
        if callable(writer):
            try:
                return bool(writer(x_arr, f_arr, v_arr))
            except Exception:
                return False
        return False

    def __repr__(self):
        status = "enabled" if self.enabled else "disabled"
        return f"<{self.__class__.__name__}({self.name}, {status})>"


class PluginManager:
    """Manage plugin registration, lifecycle callbacks, and dispatch."""

    def __init__(
        self,
        short_circuit: bool = False,
        short_circuit_events: Optional[list] = None,
        *,
        strict: bool = False,
    ):
        self.plugins = []
        self.plugin_map = {}  # name -> plugin
        self.short_circuit = short_circuit
        self.short_circuit_events = set(short_circuit_events or [])
        self.strict = bool(strict)
        self._solver = None
        self._context_build_writers: Dict[str, str] = {}

    @staticmethod
    def _safe_values_differ(a: Any, b: Any) -> bool:
        if a is b:
            return False
        try:
            neq = a != b
            if isinstance(neq, bool):
                return bool(neq)
            # numpy arrays / pandas objects may return vectorized result
            return True
        except Exception:
            return True

    def _collect_changed_keys(self, before: Mapping[str, Any], after: Mapping[str, Any]) -> list[str]:
        keys = set(before.keys()) | set(after.keys())
        changed: list[str] = []
        for key in keys:
            if key not in before or key not in after:
                changed.append(str(key))
                continue
            if self._safe_values_differ(before[key], after[key]):
                changed.append(str(key))
        return changed

    def register(self, plugin: Plugin):
        """Register a plugin."""
        if plugin.name in self.plugin_map:
            raise ValueError(f"Plugin '{plugin.name}' already registered")

        self.plugins.append(plugin)
        # Keep stable order among same-priority plugins.
        self.plugins.sort(key=lambda p: p.priority, reverse=True)
        self.plugin_map[plugin.name] = plugin
        return plugin

    def unregister(self, plugin_name: str):
        """Unregister one plugin by name."""
        if plugin_name not in self.plugin_map:
            raise ValueError(f"Plugin '{plugin_name}' not found")

        plugin = self.plugin_map[plugin_name]
        self.plugins.remove(plugin)
        del self.plugin_map[plugin_name]

    def get(self, plugin_name: str) -> Optional[Plugin]:
        """Return plugin instance by name, or None."""
        return self.plugin_map.get(plugin_name)

    def enable(self, plugin_name: str):
        plugin = self.get(plugin_name)
        if plugin:
            plugin.enable()

    def disable(self, plugin_name: str):
        plugin = self.get(plugin_name)
        if plugin:
            plugin.disable()

    def trigger(self, event_name: str, *args, **kwargs):
        """Trigger an event on plugins.

        If short-circuit is enabled for this event, returns the first non-None
        handler result.
        """
        should_short_circuit = self.short_circuit and event_name in self.short_circuit_events

        for plugin in self.plugins:
            if not plugin.enabled:
                continue

            handler = getattr(plugin, event_name, None)
            if handler and callable(handler):
                try:
                    t0 = time.time()
                    result = handler(*args, **kwargs)
                    dt = max(0.0, float(time.time() - t0))
                    prof = getattr(plugin, "_profile", None)
                    if isinstance(prof, dict):
                        prof["total_s"] = float(prof.get("total_s", 0.0) or 0.0) + dt
                        events = prof.get("events")
                        if not isinstance(events, dict):
                            events = {}
                            prof["events"] = events
                        events[event_name] = float(events.get(event_name, 0.0) or 0.0) + dt

                    if should_short_circuit and result is not None:
                        return result
                    if (not should_short_circuit) and result is not None:
                        warnings.warn(
                            (
                                f"Plugin '{plugin.name}' returned a non-None result for event "
                                f"'{event_name}' (ignored). Enable short_circuit and add the event "
                                "to short_circuit_events to allow returning values."
                            ),
                            RuntimeWarning,
                            stacklevel=2,
                        )
                except Exception as e:
                    if self.strict:
                        raise RuntimeError(
                            f"Plugin '{plugin.name}' failed in event '{event_name}': {e}"
                        ) from e
                    print(
                        f"[WARNING] Plugin {plugin.name} failed to handle {event_name}: {e}\n"
                        f"{traceback.format_exc()}"
                    )

    def dispatch(self, event_name: str, *args, **kwargs):
        """Dispatch an event and return the last non-None result.

        For `on_context_build`, it also tracks which plugin changed which keys
        and stores attribution into `solver._context_build_writers`.
        """
        out = None
        context_writers: Dict[str, str] = {}
        is_context_build = (
            str(event_name) == "on_context_build"
            and len(args) >= 1
            and isinstance(args[0], dict)
        )
        for plugin in self.plugins:
            if not plugin.enabled:
                continue
            handler = getattr(plugin, event_name, None)
            if handler and callable(handler):
                before_ctx = None
                if is_context_build:
                    try:
                        before_ctx = copy.deepcopy(args[0])
                    except Exception:
                        before_ctx = dict(args[0])
                try:
                    result = handler(*args, **kwargs)
                except Exception as exc:
                    if self.strict:
                        raise RuntimeError(
                            f"Plugin '{plugin.name}' dispatch failed on event '{event_name}': {exc}"
                        ) from exc
                    warnings.warn(
                        (
                            f"Plugin '{plugin.name}' dispatch failed on event '{event_name}': {exc}\n"
                            f"{traceback.format_exc()}"
                        ),
                        RuntimeWarning,
                        stacklevel=2,
                    )
                    continue

                if is_context_build and before_ctx is not None:
                    after_ctx = result if isinstance(result, dict) else args[0]
                    if isinstance(after_ctx, dict):
                        changed = self._collect_changed_keys(before_ctx, after_ctx)
                        source = f"plugin.{plugin.name}"
                        for key in changed:
                            context_writers[str(key)] = source

                if result is not None:
                    out = result

        if is_context_build:
            self._context_build_writers = context_writers
            if self._solver is not None:
                try:
                    setattr(self._solver, "_context_build_writers", dict(context_writers))
                except Exception:
                    pass
        return out

    def on_solver_init(self, solver):
        """Notify all plugins that solver init has started."""
        self._solver = solver
        self._context_build_writers = {}
        try:
            setattr(solver, "_context_build_writers", {})
        except Exception:
            pass
        for plugin in self.plugins:
            if plugin.enabled:
                plugin.attach(solver)
                plugin.on_solver_init(solver)

    def on_population_init(self, population, objectives, violations):
        self.trigger("on_population_init", population, objectives, violations)

    def on_generation_start(self, generation: int):
        self.trigger("on_generation_start", generation)

    def on_generation_end(self, generation: int):
        self.trigger("on_generation_end", generation)

    def on_step(self, solver, generation: int):
        self.trigger("on_step", solver, generation)

    def on_solver_finish(self, result: Dict[str, Any]):
        self.trigger("on_solver_finish", result)

    def list_plugins(self, enabled_only: bool = False) -> list:
        """List plugins, optionally only enabled ones."""
        if enabled_only:
            return [p for p in self.plugins if p.enabled]
        return self.plugins.copy()

    def clear(self):
        """Clear all plugins."""
        self.plugins.clear()
        self.plugin_map.clear()

    def __len__(self):
        return len(self.plugins)

    def __repr__(self):
        enabled_count = sum(1 for p in self.plugins if p.enabled)
        return f"<PluginManager({len(self.plugins)} plugins, {enabled_count} enabled)>"
