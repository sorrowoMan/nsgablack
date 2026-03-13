import numpy as np

from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.evolution_solver import EvolutionSolver
from nsgablack.utils.wiring import attach_default_observability_plugins
from nsgablack.utils.wiring import attach_observability_profile
from nsgablack.utils.wiring import resolve_observability_preset


class _ToyProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="toy", dimension=2, bounds=[(-1.0, 1.0), (-1.0, 1.0)])

    def evaluate(self, x):
        arr = np.asarray(x, dtype=float)
        return float(np.sum(arr * arr))


def test_attach_default_observability_plugins_idempotent():
    solver = EvolutionSolver(_ToyProblem())
    attach_default_observability_plugins(
        solver,
        output_dir="runs",
        run_id="suite_test",
        enable_profiler=False,
        enable_decision_trace=True,
    )
    attach_default_observability_plugins(
        solver,
        output_dir="runs",
        run_id="suite_test",
        enable_profiler=False,
        enable_decision_trace=True,
    )
    names = [p.name for p in solver.plugin_manager.list_plugins(enabled_only=False)]
    assert "pareto_archive" in names
    assert "benchmark_harness" in names
    assert "module_report" in names
    assert "decision_trace" in names
    assert "sequence_graph" in names
    assert names.count("decision_trace") == 1


def test_attach_observability_profile_quickstart_profile():
    solver = EvolutionSolver(_ToyProblem())
    attach_observability_profile(
        solver,
        profile="quickstart",
        output_dir="runs",
        run_id="suite_test_quickstart",
    )
    names = [p.name for p in solver.plugin_manager.list_plugins(enabled_only=False)]
    assert "pareto_archive" in names
    assert "module_report" in names
    assert "benchmark_harness" not in names
    assert "profiler" not in names
    assert "decision_trace" not in names
    assert "sequence_graph" not in names


def test_resolve_observability_preset_rejects_unknown_profile():
    try:
        resolve_observability_preset("unknown")  # type: ignore[arg-type]
    except ValueError:
        return
    raise AssertionError("resolve_observability_preset should raise ValueError for unknown profile")
