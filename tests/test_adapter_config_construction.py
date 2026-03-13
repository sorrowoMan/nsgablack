from __future__ import annotations

import pytest


def test_vns_supports_inline_config_kwargs():
    from nsgablack.adapters import VNSAdapter

    adapter = VNSAdapter(batch_size=7, k_max=3, base_sigma=0.15)
    assert int(adapter.config.batch_size) == 7
    assert int(adapter.cfg.k_max) == 3
    assert float(adapter.config.base_sigma) == pytest.approx(0.15)


def test_sa_rejects_mixing_config_and_inline_kwargs():
    from nsgablack.adapters import SAConfig, SimulatedAnnealingAdapter

    with pytest.raises(ValueError):
        SimulatedAnnealingAdapter(
            config=SAConfig(),
            cooling_rate=0.9,
        )


def test_multi_strategy_supports_inline_config_kwargs():
    from nsgablack.adapters import (
        MultiStrategyControllerAdapter,
        SAConfig,
        SimulatedAnnealingAdapter,
        StrategySpec,
    )

    adapter = MultiStrategyControllerAdapter(
        strategies=[
            StrategySpec(
                adapter=SimulatedAnnealingAdapter(config=SAConfig(batch_size=1)),
                name="sa",
                weight=1.0,
            )
        ],
        total_batch_size=23,
        stagnation_window=5,
    )
    assert int(adapter.config.total_batch_size) == 23
    assert int(adapter.cfg.stagnation_window) == 5


def test_nsga2_validates_config_type():
    from nsgablack.adapters import NSGA2Adapter, VNSConfig

    with pytest.raises(TypeError):
        NSGA2Adapter(config=VNSConfig())
