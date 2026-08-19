"""nsgablack Plugin system.

- ``Plugin`` inherits from ``blackbase.plugin.PluginBase`` and adds
  nsgablack-specific helpers (``get_population_snapshot``,
  ``commit_population_snapshot``, ``create_local_rng``).
- ``PluginManager`` is re-exported from blackbase (shared infrastructure).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np

from blackbase.call_binding import CallCandidate, invoke_bound_once
from blackbase.plugin import PluginBase, PluginManager, report_soft_error

logger = logging.getLogger(__name__)


class Plugin(PluginBase):
    """nsgablack Plugin with solver-specific helpers.

    Adds population snapshot access and RNG forking on top of the
    shared PluginBase lifecycle hooks.
    """

    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()

    def create_local_rng(self, seed: Optional[int] = None, solver: Any = None) -> np.random.Generator:
        """Create a plugin-local RNG, forking from the solver's RNG if possible."""
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
                except Exception as exc:
                    report_soft_error(
                        component="Plugin",
                        event="create_local_rng",
                        exc=exc,
                        logger=logger,
                        strict=False,
                        level="debug",
                    )
        return np.random.default_rng()

    def get_population_snapshot(self, solver=None):
        """Return (population, objectives, violations) with snapshot-first fallback order.

        Priority:
        1) solver.read_snapshot() (snapshot store)
        2) adapter.get_population()
        3) solver.{population, objectives, constraint_violations}
        """
        from blackbase.context.context_keys import (
            KEY_CONSTRAINT_VIOLATIONS,
            KEY_OBJECTIVES,
            KEY_POPULATION,
            KEY_POPULATION_REF,
            KEY_SNAPSHOT_KEY,
        )

        target = solver if solver is not None else self.solver
        if target is None:
            return np.zeros((0, 0), dtype=float), np.zeros((0, 0), dtype=float), np.zeros((0,), dtype=float)

        reader = getattr(target, "read_snapshot", None)
        if callable(reader):
            payload = None
            try:
                payload = reader()
            except Exception as exc:
                report_soft_error(
                    component="Plugin",
                    event="get_population_snapshot.reader_default",
                    exc=exc,
                    logger=logger,
                    strict=False,
                    level="debug",
                )
                payload = None
            if payload is None:
                getter = getattr(target, "get_context", None)
                if callable(getter):
                    try:
                        ctx = getter()
                    except Exception as exc:
                        report_soft_error(
                            component="Plugin",
                            event="get_population_snapshot.get_context",
                            exc=exc,
                            logger=logger,
                            strict=False,
                            level="debug",
                        )
                        ctx = None
                    if isinstance(ctx, dict):
                        key = ctx.get(KEY_POPULATION_REF) or ctx.get(KEY_SNAPSHOT_KEY)
                        if key:
                            try:
                                payload = reader(key)
                            except Exception as exc:
                                report_soft_error(
                                    component="Plugin",
                                    event="get_population_snapshot.reader_with_key",
                                    exc=exc,
                                    logger=logger,
                                    strict=False,
                                    level="debug",
                                )
                                payload = None
            if payload is not None:
                data = payload.data if hasattr(payload, "data") else payload
                if isinstance(data, dict):
                    try:
                        x = np.asarray(data.get(KEY_POPULATION, np.zeros((0, 0))), dtype=float)
                        f = np.asarray(data.get(KEY_OBJECTIVES, np.zeros((0, 0))), dtype=float)
                        v = np.asarray(
                            data.get(KEY_CONSTRAINT_VIOLATIONS, np.zeros((0,))),
                            dtype=float,
                        ).reshape(-1)
                        if x.ndim == 1:
                            x = x.reshape(1, -1) if x.size > 0 else x.reshape(0, 0)
                        if f.ndim == 1:
                            f = f.reshape(-1, 1) if f.size > 0 else f.reshape(0, 0)
                        if x.size > 0 or f.size > 0:
                            return x, f, v
                    except Exception as exc:
                        report_soft_error(
                            component="Plugin",
                            event="get_population_snapshot.payload_cast",
                            exc=exc,
                            logger=logger,
                            strict=False,
                            level="debug",
                        )

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
                except Exception as exc:
                    report_soft_error(
                        component="Plugin",
                        event="get_population_snapshot.adapter_get_population",
                        exc=exc,
                        logger=logger,
                        strict=False,
                        level="debug",
                    )
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
        except Exception as exc:
            report_soft_error(
                component="Plugin",
                event="commit_population_snapshot.cast",
                exc=exc,
                logger=logger,
                strict=False,
                level="debug",
            )
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
                    handled = invoke_bound_once(
                        setter,
                        (
                            CallCandidate(
                                args=(x_arr, f_arr, v_arr),
                                label="population",
                            ),
                            CallCandidate(
                                args=(target, x_arr, f_arr, v_arr),
                                label="solver_population",
                            ),
                        ),
                    )
                except Exception as exc:
                    report_soft_error(
                        component="Plugin",
                        event=f"commit_population_snapshot.{method_name}",
                        exc=exc,
                        logger=logger,
                        strict=False,
                        level="debug",
                    )
                    handled = False
                if handled is not False:
                    return True

        writer = getattr(target, "write_population_snapshot", None)
        if callable(writer):
            try:
                return bool(writer(x_arr, f_arr, v_arr))
            except Exception as exc:
                report_soft_error(
                    component="Plugin",
                    event="commit_population_snapshot.writer",
                    exc=exc,
                    logger=logger,
                    strict=False,
                    level="debug",
                )
                return False
        return False


__all__ = [
    "Plugin",
    "PluginBase",
    "PluginManager",
    "report_soft_error",
]
