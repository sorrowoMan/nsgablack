"""
Authority suite: module report.

Attaches ModuleReportPlugin to write:
- module inventory (which plugins/pipeline/bias enabled)
- bias contribution stats (JSON + optional Markdown)
"""

from __future__ import annotations

from ..plugins import ModuleReportConfig, ModuleReportPlugin


def attach_module_report(
    solver,
    *,
    output_dir: str = "runs",
    run_id: str = "run",
    write_bias_markdown: bool = True,
):
    if not hasattr(solver, "add_plugin"):
        raise ValueError("attach_module_report: solver missing add_plugin()")

    cfg = ModuleReportConfig(
        output_dir=str(output_dir),
        run_id=str(run_id),
        write_bias_markdown=bool(write_bias_markdown),
    )
    plugin = ModuleReportPlugin(config=cfg)

    if getattr(solver, "get_plugin", None) is not None and solver.get_plugin(plugin.name) is not None:
        return solver.get_plugin(plugin.name)

    solver.add_plugin(plugin)
    return plugin

