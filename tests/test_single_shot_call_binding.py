from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from nsgablack.adapters.multi_strategy.adapter import StrategyRouterAdapter
from nsgablack.adapters.nsga2 import NSGA2Adapter, NSGA2Config
from nsgablack.core.runtime_governance import commit_population_snapshot
from nsgablack.core.solver_helpers.bias_helpers import apply_bias_module
from nsgablack.core.solver_helpers.candidate_helpers import sample_random_candidate
from nsgablack.representation import RepresentationPipeline


def test_adapter_factory_body_type_error_is_not_retried() -> None:
    calls = 0

    def factory(unit_id=0):
        nonlocal calls
        del unit_id
        calls += 1
        raise TypeError("factory body failed")

    controller = StrategyRouterAdapter(strategies=[])
    with pytest.raises(TypeError, match="factory body failed"):
        controller._instantiate_role_adapter(factory, 0)

    assert calls == 1


def test_batch_mutator_body_type_error_is_not_retried() -> None:
    class Mutator:
        def __init__(self) -> None:
            self.calls = 0

        def mutate_batch(self, states, contexts=None):
            del states, contexts
            self.calls += 1
            raise TypeError("batch body failed")

    mutator = Mutator()
    pipeline = RepresentationPipeline(mutator=mutator)

    with pytest.raises(TypeError, match="batch body failed"):
        pipeline.mutate_batch([np.asarray([1.0])], contexts=[{}])

    assert mutator.calls == 1


def test_problem_sample_body_type_error_is_not_retried() -> None:
    class Problem:
        def __init__(self) -> None:
            self.calls = 0

        def sample(self, context=None):
            del context
            self.calls += 1
            raise TypeError("sample body failed")

    problem = Problem()
    with pytest.raises(TypeError, match="sample body failed"):
        sample_random_candidate(problem, context={"run": 1})

    assert problem.calls == 1


def test_bias_apply_body_type_error_is_not_retried() -> None:
    class Bias:
        def __init__(self) -> None:
            self.calls = 0

        def apply(self, objectives, context=None):
            del objectives, context
            self.calls += 1
            raise TypeError("bias body failed")

    bias = Bias()
    solver = SimpleNamespace(
        bias_module=bias,
        plugin_strict=False,
        context_store=None,
    )

    result = apply_bias_module(solver, np.asarray([2.0]), context={})

    assert result.tolist() == [2.0]
    assert bias.calls == 1


def test_crossover_body_type_error_is_not_retried() -> None:
    class Crossover:
        def __init__(self) -> None:
            self.calls = 0

        def crossover(self, first, second, context=None):
            del first, second, context
            self.calls += 1
            raise TypeError("crossover body failed")

    crossover = Crossover()
    control = SimpleNamespace(
        representation_pipeline=SimpleNamespace(crossover=crossover)
    )
    adapter = NSGA2Adapter(NSGA2Config(crossover_rate=1.0))

    with pytest.raises(TypeError, match="crossover body failed"):
        adapter._crossover(
            control,
            np.asarray([1.0]),
            np.asarray([2.0]),
            {},
        )

    assert crossover.calls == 1


def test_population_setter_body_type_error_is_not_retried() -> None:
    class Adapter:
        def __init__(self) -> None:
            self.calls = 0

        def set_population(self, population, objectives, violations):
            del population, objectives, violations
            self.calls += 1
            raise TypeError("setter body failed")

    adapter = Adapter()
    solver = SimpleNamespace(
        adapter=adapter,
        dimension=1,
        num_objectives=1,
        context_store=None,
    )

    handled = commit_population_snapshot(
        solver,
        np.asarray([[1.0]]),
        np.asarray([[2.0]]),
        np.asarray([0.0]),
    )

    assert handled is False
    assert adapter.calls == 1


def test_population_setter_solver_aware_form_is_bound_before_call() -> None:
    class Adapter:
        def __init__(self) -> None:
            self.calls = 0

        def set_population(self, solver, population, objectives, violations):
            del population, objectives, violations
            self.calls += 1
            assert solver is outer_solver
            return True

    adapter = Adapter()
    outer_solver = SimpleNamespace(
        adapter=adapter,
        dimension=1,
        num_objectives=1,
        context_store=None,
    )

    assert commit_population_snapshot(
        outer_solver,
        np.asarray([[1.0]]),
        np.asarray([[2.0]]),
        np.asarray([0.0]),
    ) is True
    assert adapter.calls == 1
