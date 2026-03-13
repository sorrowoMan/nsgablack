"""Default observability plugin wiring for quick, safe assembly.

This module exposes two entrypoints:
- ``attach_default_observability_plugins``: low-level switches
- ``attach_observability_profile``: profile-based wrapper
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
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

ObservabilityProfile = Literal["quickstart", "default", "strict"]


@dataclass(frozen=True)
class ObservabilityPreset:
    """Resolved preset values for observability profile."""

    enable_pareto_archive: bool
    enable_benchmark: bool
    enable_module_report: bool
    enable_profiler: bool
    enable_decision_trace: bool
    enable_sequence_graph: bool
    benchmark_log_every: int = 1
    benchmark_flush_every: int = 10
    decision_trace_flush_every: int = 1
    sequence_graph_flush_every: int = 1
    sequence_graph_trace_mode: str = "off"
    sequence_graph_trace_sample_rate: float = 0.02
    sequence_graph_trace_max_events: int = 20000
    sequence_graph_trace_seed: int | None = None


_OBSERVABILITY_PRESETS: dict[str, ObservabilityPreset] = {
    # Fast smoke run: keep only low-overhead essentials.
    "quickstart": ObservabilityPreset(
        enable_pareto_archive=True,
        enable_benchmark=False,
        enable_module_report=True,
        enable_profiler=False,
        enable_decision_trace=False,
        enable_sequence_graph=False,
    ),
    # Balanced default for regular development.
    "default": ObservabilityPreset(
        enable_pareto_archive=True,
        enable_benchmark=True,
        enable_module_report=True,
        enable_profiler=True,
        enable_decision_trace=True,
        enable_sequence_graph=True,
    ),
    # Strict diagnosis: preserve more traces for post-mortem.
    "strict": ObservabilityPreset(
        enable_pareto_archive=True,
        enable_benchmark=True,
        enable_module_report=True,
        enable_profiler=True,
        enable_decision_trace=True,
        enable_sequence_graph=True,
        benchmark_flush_every=1,
        decision_trace_flush_every=1,
        sequence_graph_flush_every=1,
        sequence_graph_trace_mode="full",
        sequence_graph_trace_sample_rate=1.0,
        sequence_graph_trace_max_events=200000,
    ),
}


def resolve_observability_preset(profile: ObservabilityProfile = "default") -> ObservabilityPreset:
    """Return a resolved preset by profile name."""
    key = str(profile).strip().lower()
    if key not in _OBSERVABILITY_PRESETS:
        allowed = ", ".join(sorted(_OBSERVABILITY_PRESETS))
        raise ValueError(f"Unknown observability profile: {profile!r}. Allowed: {allowed}")
    return _OBSERVABILITY_PRESETS[key]


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


def attach_observability_profile(
    solver: Any,
    *,
    profile: ObservabilityProfile = "default",
    output_dir: str = "runs",
    run_id: str = "run",
    overwrite: bool = True,
    enable_pareto_archive: bool | None = None,
    enable_benchmark: bool | None = None,
    enable_module_report: bool | None = None,
    enable_profiler: bool | None = None,
    enable_decision_trace: bool | None = None,
    enable_sequence_graph: bool | None = None,
) -> Any:
    """Attach a profile-based observability wiring with optional overrides.

    This API is intended for scaffold/build entrypoints where users want
    plug-and-play behavior without wiring each plugin switch manually.
    """

    preset = resolve_observability_preset(profile)
    return attach_default_observability_plugins(
        solver,
        output_dir=str(output_dir),
        run_id=str(run_id),
        overwrite=bool(overwrite),
        enable_pareto_archive=(
            preset.enable_pareto_archive if enable_pareto_archive is None else bool(enable_pareto_archive)
        ),
        enable_benchmark=(preset.enable_benchmark if enable_benchmark is None else bool(enable_benchmark)),
        benchmark_log_every=int(preset.benchmark_log_every),
        benchmark_flush_every=int(preset.benchmark_flush_every),
        enable_module_report=(preset.enable_module_report if enable_module_report is None else bool(enable_module_report)),
        enable_profiler=(preset.enable_profiler if enable_profiler is None else bool(enable_profiler)),
        enable_decision_trace=(preset.enable_decision_trace if enable_decision_trace is None else bool(enable_decision_trace)),
        decision_trace_flush_every=int(preset.decision_trace_flush_every),
        enable_sequence_graph=(preset.enable_sequence_graph if enable_sequence_graph is None else bool(enable_sequence_graph)),
        sequence_graph_flush_every=int(preset.sequence_graph_flush_every),
        sequence_graph_trace_mode=str(preset.sequence_graph_trace_mode),
        sequence_graph_trace_sample_rate=float(preset.sequence_graph_trace_sample_rate),
        sequence_graph_trace_max_events=int(preset.sequence_graph_trace_max_events),
        sequence_graph_trace_seed=preset.sequence_graph_trace_seed,
    )
