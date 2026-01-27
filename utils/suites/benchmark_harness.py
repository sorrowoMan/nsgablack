"""
Authority suite: benchmark harness (unified experiment protocol).

This is intentionally lightweight: it only attaches a logger plugin.
"""

from __future__ import annotations

from typing import Optional

from ..plugins import BenchmarkHarnessConfig, BenchmarkHarnessPlugin


def attach_benchmark_harness(
    solver,
    *,
    output_dir: str = "runs",
    run_id: str = "run",
    seed: Optional[int] = None,
    log_every: int = 1,
    flush_every: int = 10,
    overwrite: bool = False,
):
    """
    Attach BenchmarkHarnessPlugin.

    This suite does NOT change algorithm behavior. It only standardizes output.
    """

    if not hasattr(solver, "add_plugin"):
        raise ValueError("attach_benchmark_harness: solver missing add_plugin()")

    cfg = BenchmarkHarnessConfig(
        output_dir=str(output_dir),
        run_id=str(run_id),
        seed=None if seed is None else int(seed),
        log_every=int(log_every),
        flush_every=int(flush_every),
        overwrite=bool(overwrite),
    )
    plugin = BenchmarkHarnessPlugin(config=cfg)

    if getattr(solver, "get_plugin", None) is not None and solver.get_plugin(plugin.name) is not None:
        # already attached
        return solver.get_plugin(plugin.name)

    solver.add_plugin(plugin)
    return plugin

