"""真实轨迹配对基准的独立参考、送评计数与恢复回归。"""
from copy import deepcopy

import numpy as np
import pytest

from benchmarks.transparency_trajectory import (
    TRAJECTORY_NAMES, TrajectoryReference, evaluate_trajectory,
    trajectory_reference,
)


def assert_same(left, right):
    if isinstance(left, dict):
        assert left.keys() == right.keys()
        for key in left:
            assert_same(left[key], right[key])
    elif left is None or right is None:
        assert left is right
    else:
        np.testing.assert_allclose(left, right, rtol=1e-10, atol=1e-12)


@pytest.mark.parametrize("name", TRAJECTORY_NAMES)
def test_reference_uses_every_injected_evaluation_and_survives_its_own_checkpoint(name):
    calls = []

    def evaluate(x):
        calls.append(np.asarray(x).copy())
        return evaluate_trajectory(name, x), 0.0

    reference = TrajectoryReference(name, 11, evaluate=evaluate)
    first = [reference.step() for _ in range(3)]
    saved = reference.checkpoint()
    saved_rng = deepcopy(saved["rng_state"])
    restored = TrajectoryReference.restore(saved, evaluate=evaluate)
    expected = [reference.step() for _ in range(3)]
    actual = [restored.step() for _ in range(3)]
    for left, right in zip(expected, actual):
        assert_same(left, right)
    np.testing.assert_allclose(np.asarray(calls[:sum(len(row["candidates"]) for row in first)]),
                               np.concatenate([row["candidates"] for row in first]))
    assert len(calls) == sum(len(row["candidates"]) for row in first + expected + actual)
    assert saved["rng_state"] == saved_rng


def test_reference_has_no_dependency_on_adapter_execution(monkeypatch):
    import nsgablack.adapters as adapters

    def forbidden(*args, **kwargs):
        raise AssertionError("independent reference must not execute an Adapter")

    for cls_name in ("SimulatedAnnealingAdapter", "VNSAdapter", "PatternSearchAdapter",
                     "GaussianSearchAdapter", "GradientDescentAdapter", "SingleTrajectoryAdaptiveAdapter",
                     "TrustRegionDFOAdapter", "TrustRegionNonSmoothAdapter", "TrustRegionSubspaceAdapter",
                     "TrustRegionMODFOAdapter", "MASAdapter"):
        cls = getattr(adapters, cls_name)
        for method in ("__init__", "propose", "update", "get_state", "set_state"):
            monkeypatch.setattr(cls, method, forbidden)
    for name in TRAJECTORY_NAMES:
        result = trajectory_reference(name, 17, 3,
            lambda x, name=name: (evaluate_trajectory(name, x), 0.0))
        assert len(result["trace"]) == 3


def test_gradient_trial_is_separately_evaluated_and_learning_rate_updates_after_trial():
    raw = TrajectoryReference("gradient_descent", 11)
    baseline, probes, trial = (raw.step() for _ in range(3))
    assert len(baseline["candidates"]) == len(trial["candidates"]) == 1
    assert len(probes["candidates"]) == 4
    assert probes["state"]["current"] == baseline["state"]["current"]
    assert probes["state"]["learning_rate"] == 0.15
    np.testing.assert_allclose(trial["candidates"][0], np.asarray(baseline["candidates"][0]) * 0.7)
    assert trial["state"]["current_score"] == trial["objectives"][0][0]
    assert trial["state"]["learning_rate"] == pytest.approx(0.1575)


def test_mas_reference_enters_real_fitted_surrogate_branch():
    raw = TrajectoryReference("mas", 11)
    first, second = raw.step(), raw.step()
    assert first["state"]["model_fitted"] is False
    assert second["state"]["model_fitted"] is True
    assert raw.model.n_estimators == 200
    saved = deepcopy(raw.rng.bit_generator.state)
    third = raw.step()
    assert third["state"]["history_count"] == 9
    expected_rng = np.random.default_rng()
    expected_rng.bit_generator.state = saved
    expected_rng.normal(size=(8, 2))  # 2 exploration + 6 model proposal points
    assert raw.rng.bit_generator.state == expected_rng.bit_generator.state


def test_injected_objectives_determine_reference_scores():
    result = trajectory_reference("pattern_search", 11, 2,
        lambda x: (np.asarray([123.0]), 0.0))
    assert result["state"]["best_score"] == 123.0
    assert result["state"]["step_size"] == pytest.approx(0.24)
