from types import SimpleNamespace

import numpy as np
import pytest

from nsgablack.adapters.algorithm_adapter import AlgorithmAdapter
from nsgablack.adapters.multi_strategy import MultiStrategyControllerAdapter, StrategySpec
from nsgablack.utils.context.context_contracts import collect_solver_contracts, get_component_contract
from nsgablack.utils.context.context_keys import KEY_MUTATION_SIGMA, KEY_VNS_K


class _NoopAdapter(AlgorithmAdapter):
    def propose(self, solver, context):
        return []


class _LegacyContractObject:
    requires_context_keys = ("alpha", "beta")
    provides_context_keys = ("gamma",)
    mutates_context_keys = ("delta",)
    cache_context_keys = ("memo",)
    recommended_plugins = ("plugin.pareto_archive",)


def test_get_component_contract_supports_legacy_fields():
    contract = get_component_contract(_LegacyContractObject())
    assert contract is not None
    assert set(contract.requires) == {"alpha", "beta"}
    assert set(contract.provides) == {"gamma"}
    assert set(contract.mutates) == {"delta"}
    assert set(contract.cache) == {"memo"}
    assert "plugin.pareto_archive" in str(contract.notes or "")


def test_algorithm_adapter_contract_merges_legacy_and_context_fields():
    adapter = _NoopAdapter(name="noop")
    adapter.context_requires = ("generation",)
    adapter.requires_context_keys = (KEY_VNS_K,)
    adapter.context_provides = (KEY_MUTATION_SIGMA,)
    contract = get_component_contract(adapter)
    assert contract is not None
    assert "generation" in set(contract.requires)
    assert KEY_VNS_K in set(contract.requires)
    assert KEY_MUTATION_SIGMA in set(contract.provides)


def test_collect_solver_contracts_includes_multi_strategy_children():
    explorer = StrategySpec(adapter=_NoopAdapter(name="explorer"), name="explorer")
    exploiter = StrategySpec(adapter=_NoopAdapter(name="exploiter"), name="exploiter")
    controller = MultiStrategyControllerAdapter(strategies=[explorer, exploiter])
    solver = SimpleNamespace(
        representation_pipeline=None,
        bias_module=None,
        adapter=controller,
        plugin_manager=None,
    )
    contracts = collect_solver_contracts(solver)
    names = {name for name, _ in contracts}
    assert "adapter" in names
    assert "adapter.strategy.explorer" in names
    assert "adapter.strategy.exploiter" in names


def test_algorithm_adapter_population_snapshot_contract_validation():
    adapter = _NoopAdapter(name="noop")
    pop, obj, vio = adapter.validate_population_snapshot(
        population=np.array([[1.0, 2.0]], dtype=float),
        objectives=np.array([3.0], dtype=float),
        violations=np.array([0.0], dtype=float),
    )
    assert pop.shape == (1, 2)
    assert obj.shape == (1, 1)
    assert vio.shape == (1,)
    assert adapter.set_population(pop, obj, vio) is False


def test_algorithm_adapter_population_snapshot_contract_shape_mismatch_raises():
    adapter = _NoopAdapter(name="noop")
    with pytest.raises(ValueError):
        adapter.validate_population_snapshot(
            population=np.array([[1.0, 2.0], [3.0, 4.0]], dtype=float),
            objectives=np.array([[1.0]], dtype=float),
            violations=np.array([0.0, 0.0], dtype=float),
        )
