"""Default observability plugin bundle for quick, safe wiring."""

from __future__ import annotations

from typing import Any

from ...plugins import (
    BenchmarkHarnessConfig,
    BenchmarkHarnessPlugin,
    DecisionTraceConfig,
    DecisionTracePlugin,
    ModuleReportConfig,
    ModuleReportPlugin,
    ParetoArchivePlugin,
    ProfilerConfig,
    ProfilerPlugin,
    SequenceGraphConfig,
    SequenceGraphPlugin,
)


def _plugin_exists(solver: Any, name: str) -> bool:
    pm = getattr(solver, "plugin_manager", None)
    if pm is None:
        return False
    try:
        return pm.get(str(name)) is not None
    except Exception:
        return False


def attach_default_observability_plugins(
    solver: Any,
    *,
    output_dir: str = "runs",
    run_id: str = "run",
    overwrite: bool = True,
    enable_pareto_archive: bool = True,
    enable_benchmark: bool = True,
    benchmark_log_every: int = 1,
    benchmark_flush_every: int = 10,
    enable_module_report: bool = True,
    write_bias_markdown: bool = True,
    enable_profiler: bool = True,
    enable_decision_trace: bool = True,
    decision_trace_flush_every: int = 1,
    enable_sequence_graph: bool = True,
    sequence_graph_flush_every: int = 1,
    sequence_graph_trace_mode: str = "off",
    sequence_graph_trace_sample_rate: float = 0.02,
    sequence_graph_trace_max_events: int = 20000,
    sequence_graph_trace_seed: int | None = None,
) -> Any:
    """Attach a low-conflict default plugin set, skipping already registered names."""

    if enable_pareto_archive and not _plugin_exists(solver, "pareto_archive"):
        solver.add_plugin(ParetoArchivePlugin())

    if enable_benchmark and not _plugin_exists(solver, "benchmark_harness"):
        solver.add_plugin(
            BenchmarkHarnessPlugin(
                config=BenchmarkHarnessConfig(
                    output_dir=str(output_dir),
                    run_id=str(run_id),
                    log_every=max(1, int(benchmark_log_every)),
                    flush_every=max(1, int(benchmark_flush_every)),
                    overwrite=bool(overwrite),
                )
            )
        )

    if enable_module_report and not _plugin_exists(solver, "module_report"):
        solver.add_plugin(
            ModuleReportPlugin(
                config=ModuleReportConfig(
                    output_dir=str(output_dir),
                    run_id=str(run_id),
                    write_bias_markdown=bool(write_bias_markdown),
                )
            )
        )

    if enable_profiler and not _plugin_exists(solver, "profiler"):
        solver.add_plugin(
            ProfilerPlugin(
                config=ProfilerConfig(
                    output_dir=str(output_dir),
                    run_id=str(run_id),
                    overwrite=bool(overwrite),
                    flush_every=0,
                )
            )
        )

    if enable_decision_trace and not _plugin_exists(solver, "decision_trace"):
        solver.add_plugin(
            DecisionTracePlugin(
                config=DecisionTraceConfig(
                    output_dir=str(output_dir),
                    run_id=str(run_id),
                    overwrite=bool(overwrite),
                    flush_every=max(1, int(decision_trace_flush_every)),
                )
            )
        )

    if enable_sequence_graph and not _plugin_exists(solver, "sequence_graph"):
        solver.add_plugin(
            SequenceGraphPlugin(
                config=SequenceGraphConfig(
                    output_dir=str(output_dir),
                    run_id=str(run_id),
                    overwrite=bool(overwrite),
                    flush_every=max(1, int(sequence_graph_flush_every)),
                    trace_mode=str(sequence_graph_trace_mode),
                    trace_sample_rate=float(sequence_graph_trace_sample_rate),
                    trace_max_events=max(1, int(sequence_graph_trace_max_events)),
                    trace_seed=sequence_graph_trace_seed,
                )
            )
        )

    return solver
