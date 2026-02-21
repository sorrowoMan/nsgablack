from __future__ import annotations

import logging

import numpy as np
import pytest

from nsgablack.bias.core.base import BiasBase, OptimizationContext


class _MetricsBias(BiasBase):
    requires_metrics = ("foo",)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        return float((context.metrics or {}).get("foo", 0.0))


def _ctx(*, generation: int = 0, metrics=None) -> OptimizationContext:
    return OptimizationContext(
        generation=generation,
        individual=np.asarray([0.0], dtype=float),
        population=[],
        metrics=dict(metrics or {}),
        history=[],
        problem_data={},
    )


def test_missing_required_metrics_warns_once_per_generation(caplog: pytest.LogCaptureFixture) -> None:
    bias = _MetricsBias(name="guarded_bias", weight=1.0)
    bias.missing_metrics_policy = "warn"

    with caplog.at_level(logging.WARNING, logger="nsgablack.bias.core.base"):
        bias.compute_with_tracking(np.asarray([0.0], dtype=float), _ctx(generation=3, metrics={}))
        bias.compute_with_tracking(np.asarray([0.0], dtype=float), _ctx(generation=3, metrics={}))

    hits = [rec for rec in caplog.records if "missing required metrics" in rec.getMessage()]
    assert len(hits) == 1


def test_missing_required_metrics_error_policy_raises() -> None:
    bias = _MetricsBias(name="guarded_bias", weight=1.0)
    bias.missing_metrics_policy = "error"

    with pytest.raises(KeyError):
        bias.compute_with_tracking(np.asarray([0.0], dtype=float), _ctx(metrics={}))


def test_required_metrics_present_runs_without_warning(caplog: pytest.LogCaptureFixture) -> None:
    bias = _MetricsBias(name="guarded_bias", weight=2.0)
    bias.missing_metrics_policy = "warn"

    with caplog.at_level(logging.WARNING, logger="nsgablack.bias.core.base"):
        out = bias.compute_with_tracking(np.asarray([0.0], dtype=float), _ctx(metrics={"foo": 1.5}))

    assert out == pytest.approx(3.0)
    assert not [rec for rec in caplog.records if "missing required metrics" in rec.getMessage()]
