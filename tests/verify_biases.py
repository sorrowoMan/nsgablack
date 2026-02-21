"""Verification suite for remaining bias layer semantics."""

import numpy as np

from nsgablack.bias.algorithmic import (
    AdaptiveConvergenceBias,
    ConvergenceBias,
    DiversityBias,
    TabuSearchBias,
)
from nsgablack.bias.core.base import OptimizationContext
from nsgablack.catalog.registry import get_catalog


def test_bias_imports_are_signal_level():
    assert DiversityBias is not None
    assert ConvergenceBias is not None
    assert AdaptiveConvergenceBias is not None
    assert TabuSearchBias is not None


def test_tabu_and_diversity_bias_compute_scalar():
    context = OptimizationContext(
        generation=3,
        individual=np.array([0.5, 0.2, -0.1]),
        metrics={
            "nearest_neighbor_distance": 0.3,
            "crowding_distance": 0.2,
            "population_density": 0.6,
        },
    )
    x = np.array([0.5, 0.2, -0.1])

    tabu = TabuSearchBias(weight=0.2, tabu_size=10)
    div = DiversityBias(weight=0.2)
    conv = ConvergenceBias(weight=0.2)

    for bias in (tabu, div, conv):
        value = bias.compute(x, context)
        assert isinstance(value, (int, float))


def test_catalog_keeps_process_algorithms_in_adapter_layer():
    catalog = get_catalog(refresh=True)
    keys = {entry.key for entry in catalog._entries}

    assert "adapter.de" in keys
    assert "adapter.nsga2" in keys
    assert "adapter.nsga3" in keys
    assert "adapter.spea2" in keys
    assert "adapter.pattern_search" in keys
    assert "adapter.gradient_descent" in keys

    assert "bias.de" not in keys
    assert "bias.nsga2_core" not in keys
    assert "bias.nsga3_core" not in keys
    assert "bias.spea2_core" not in keys
    assert "bias.pattern_search" not in keys
    assert "bias.gradient_descent" not in keys
