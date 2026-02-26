import numpy as np

from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.solver import BlackBoxSolverNSGAII
from nsgablack.utils.suites import attach_default_observability_plugins


class _ToyProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="toy", dimension=2, bounds=[(-1.0, 1.0), (-1.0, 1.0)])

    def evaluate(self, x):
        arr = np.asarray(x, dtype=float)
        return float(np.sum(arr * arr))


def test_attach_default_observability_plugins_idempotent():
    solver = BlackBoxSolverNSGAII(_ToyProblem())
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
    assert names.count("decision_trace") == 1
