"""公共计数器保留 Problem 调用签名，目标与约束只按实际调用记账。"""
import inspect
from types import MappingProxyType

import numpy as np

from blackbase.types import Feedback
from benchmarks.transparency_core import ProblemMeter, compare


def test_meter_preserves_the_dispatch_signature_and_counts_one_objective_call():
    class Problem:
        def __init__(self):
            self.calls = 0
            self.constraint_calls = 0

        def evaluate(self, candidate):
            self.calls += 1
            return np.asarray([float(np.sum(np.asarray(candidate) ** 2))])

        def evaluate_constraints(self, candidate):
            self.constraint_calls += 1
            return np.asarray([-.5, .25])

    problem = Problem()
    signature = inspect.signature(problem.evaluate)
    meter = ProblemMeter(problem)
    assert inspect.signature(problem.evaluate) == signature
    f, v = meter.evaluate(np.asarray([2., 3.]))
    np.testing.assert_array_equal(f, [13.])
    assert v == .25
    assert problem.calls == problem.constraint_calls == len(meter.records) == 1
    assert meter.records == [{"x": [2., 3.], "f": [13.], "v": .25}]


def test_feedback_gradients_do_not_trigger_a_second_objective_or_constraint_call():
    class Problem:
        def __init__(self):
            self.gradient_calls = 0

        def evaluate(self, candidate):
            self.gradient_calls += 1
            return Feedback(objectives=[4.], gradients=[4.], constraints=[.2, -1.])

        def evaluate_constraints(self, candidate):
            raise AssertionError("Feedback already owns these constraint observations")

    meter = ProblemMeter(Problem())
    f, v = meter.evaluate(np.asarray([2.]))
    np.testing.assert_array_equal(f, [4.])
    assert v == .2
    assert meter.summary()["calls"] == meter.summary()["gradient_calls"] == 1


def test_comparison_ignores_mapping_order_and_reports_concrete_numeric_mismatch():
    assert compare({"x": [1., 2.], "a": None}, {"a": None, "x": [1. + 1e-12, 2.]}) is None
    assert "root.x[1]" in compare({"x": [1., 2.]}, {"x": [1., 2.1]})
    assert compare({"observed": False}, {"observed": 0}) is not None
    assert compare({"identity": 10**18}, {"identity": 10**18 + 1}) is not None
    assert compare({"counter": np.int64(10**18)}, {"counter": np.int64(10**18 + 1)}) is not None
    assert compare({"x": [1.]}, MappingProxyType({"x": [1.]})) is None


def test_normal_iteration_timing_excludes_bootstrap_and_uses_real_commits():
    from benchmarks.transparency_core import run_pair
    from benchmarks.transparency_population import specs
    spec = specs(population_size=10, steps=3)[0]
    result = run_pair(spec, seed=11, recovery=False)
    assert result["semantics"]["status"] == "passed", result["semantics"]
    overhead = result["overhead"]
    assert overhead["status"] == "measured"
    assert overhead["bootstrap"]["framework"]["evaluation_calls"] == 10
    assert overhead["normal_iterations"]["status"] == "measured"
    assert overhead["normal_iterations"]["framework"]["count"] == 2
    assert overhead["normal_iterations"]["reference"]["count"] == 2
    assert len(overhead["physical_attempt_timings"]) == 3
    assert all(row["status"] == "committed" for row in overhead["physical_attempt_timings"])
