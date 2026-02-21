"""
MOEA/D suite (authority wiring).

This suite exists to reduce "forgot-to-wire" errors:
- It installs MOEADAdapter on a ComposableSolver-like base
- It attaches a ParetoArchivePlugin (recommended for meaningful MOEA/D output)

It does not introduce new algorithmic state; it only assembles components.
"""

from __future__ import annotations

from typing import Any, Optional


def attach_moead(
    solver: Any,
    *,
    config: Optional[Any] = None,
    archive: bool = True,
) -> Any:
    from ...core.adapters import MOEADAdapter, MOEADConfig
    from ...plugins import ParetoArchivePlugin

    cfg = config if config is not None else MOEADConfig()

    set_adapter = getattr(solver, "set_adapter", None)
    if not callable(set_adapter):
        raise RuntimeError("attach_moead requires solver.set_adapter(adapter)")
    set_adapter(MOEADAdapter(cfg))

    # Recommended: archive plugin
    if archive and getattr(solver, "add_plugin", None) is not None:
        try:
            pm = getattr(solver, "plugin_manager", None)
            if pm is not None and getattr(pm, "get", None) is not None and pm.get("pareto_archive") is not None:
                return solver
        except Exception:
            pass
        solver.add_plugin(ParetoArchivePlugin())

    return solver


