from __future__ import annotations

from typing import Any, Dict, Sequence

import numpy as np
import pytest

from nsgablack.adapters.algorithm_adapter import AlgorithmAdapter


class _DummyAdapter(AlgorithmAdapter):
    def __init__(self, value: float, name: str) -> None:
        super().__init__(name=name)
        self._value = float(value)

    def propose(self, solver: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        _ = solver
        budget = int((context.get("task") or {}).get("budget", 1))
        return [np.asarray([self._value], dtype=float) for _ in range(max(1, budget))]


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
        StrategyRouterAdapter,
        SAConfig,
        SimulatedAnnealingAdapter,
        StrategySpec,
    )

    adapter = StrategyRouterAdapter(
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


def test_multi_strategy_role_enable_policy_from_context():
    from nsgablack.adapters import StrategyRouterAdapter, StrategySpec

    adapter = StrategyRouterAdapter(
        strategies=[
            StrategySpec(adapter=_DummyAdapter(1.0, name="a"), name="a", weight=1.0),
            StrategySpec(adapter=_DummyAdapter(2.0, name="b"), name="b", weight=1.0),
        ],
        total_batch_size=4,
        adapt_weights=False,
        role_enable_policy=lambda role, ctx: role in set(ctx["context"].get("enabled_roles", [])),
    )
    adapter.setup(None)
    cands = adapter.propose(None, {"generation": 0, "enabled_roles": ["b"]})
    assert len(cands) > 0
    assert all(float(c[0]) == pytest.approx(2.0) for c in cands)


def test_multi_strategy_role_weight_policy_from_context():
    from nsgablack.adapters import StrategyRouterAdapter, StrategySpec

    adapter = StrategyRouterAdapter(
        strategies=[
            StrategySpec(adapter=_DummyAdapter(1.0, name="a"), name="a", weight=1.0),
            StrategySpec(adapter=_DummyAdapter(2.0, name="b"), name="b", weight=1.0),
        ],
        total_batch_size=12,
        adapt_weights=False,
        role_weight_policy=lambda role, w, ctx: (10.0 if role == ctx["context"].get("focus_role") else 1.0) * float(w),
    )
    adapter.setup(None)
    cands = adapter.propose(None, {"generation": 0, "focus_role": "b"})
    values = [float(c[0]) for c in cands]
    assert values.count(2.0) > values.count(1.0)


def test_multi_strategy_control_rules_enable_and_phase():
    from nsgablack.adapters import (
        MultiStrategyControlRule,
        StrategyRouterAdapter,
        StrategySpec,
    )

    adapter = StrategyRouterAdapter(
        strategies=[
            StrategySpec(adapter=_DummyAdapter(1.0, name="a"), name="a", weight=1.0),
            StrategySpec(adapter=_DummyAdapter(2.0, name="b"), name="b", weight=1.0),
        ],
        total_batch_size=6,
        adapt_weights=False,
        control_rules=(
            MultiStrategyControlRule(
                name="force_exploit_and_only_b",
                when=lambda ctx: int(ctx.get("generation", 0)) >= 0,
                set_phase="exploit",
                enable_roles=["b"],
            ),
        ),
    )
    adapter.setup(None)
    cands = adapter.propose(None, {"generation": 0})
    assert adapter._current_phase_name == "exploit"
    assert len(cands) > 0
    assert all(float(c[0]) == pytest.approx(2.0) for c in cands)


def test_multi_strategy_control_rules_dsl_without_lambda():
    from nsgablack.adapters import (
        MultiStrategyControlRule,
        StrategyRouterAdapter,
        StrategySpec,
    )

    adapter = StrategyRouterAdapter(
        strategies=[
            StrategySpec(adapter=_DummyAdapter(1.0, name="a"), name="a", weight=1.0),
            StrategySpec(adapter=_DummyAdapter(2.0, name="b"), name="b", weight=1.0),
        ],
        total_batch_size=8,
        adapt_weights=False,
        control_rules=(
            MultiStrategyControlRule(
                name="dsl_force_exploit_only_b",
                when_dsl={
                    "all": [
                        {"ge": ["$generation", 0]},
                        {"eq": ["$context.trigger", "on"]},
                    ]
                },
                then={
                    "set_phase": "exploit",
                    "enable_roles": ["b"],
                },
            ),
        ),
    )
    adapter.setup(None)
    cands = adapter.propose(None, {"generation": 0, "trigger": "on"})
    assert adapter._current_phase_name == "exploit"
    assert len(cands) > 0
    assert all(float(c[0]) == pytest.approx(2.0) for c in cands)

