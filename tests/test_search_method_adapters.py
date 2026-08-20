from __future__ import annotations

import numpy as np

from blackbase.types import UnknownState
from nsgablack.adapters.gaussian_search import (
    GaussianSearchAdapter,
    GaussianSearchConfig,
)
from nsgablack.adapters.gradient_optimizer import (
    GradientOptimizerAdapter,
    GradientOptimizerConfig,
)
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.blank_solver import SolverBase


class _Control:
    def init_candidate(self, context):
        del context
        return UnknownState(values=np.array([0.5, -0.5]))

    def init_population(self, count, context):
        del context
        return tuple(
            UnknownState(values=np.array([float(index), 0.0]))
            for index in range(int(count))
        )

    def repair_candidate(self, candidate, context):
        del context
        return candidate


class _Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=2, bounds={"x0": (-1.0, 1.0), "x1": (-1.0, 1.0)})

    def evaluate(self, candidate):
        return np.asarray([np.sum(np.asarray(candidate, dtype=float) ** 2)])


def test_solver_base_exposes_side_effect_bounded_adapter_population_init() -> None:
    control = SolverBase(_Problem())

    population = control.init_population(3, {})

    assert len(population) == 3
    assert all(np.asarray(candidate).shape == (2,) for candidate in population)
    assert control.population is None
    assert control.evaluation_count == 0


def test_gaussian_search_is_feasibility_first_and_preserves_unknown_state() -> None:
    control = _Control()
    adapter = GaussianSearchAdapter(
        GaussianSearchConfig(population_size=2, mutation_scale=0.1),
    )
    adapter.setup(control)
    candidates = tuple(adapter.propose(control, {}))

    adapter.update(
        control,
        candidates,
        (np.asarray([[-100.0], [5.0]]), np.asarray([2.0, 0.0])),
        {},
    )

    best = adapter.get_population()
    assert best is not None
    assert isinstance(best[0], UnknownState)
    assert np.allclose(best[0].as_array(), candidates[1].as_array())
    assert adapter.best_violation == 0.0


def test_gaussian_search_checkpoint_restores_exact_rng_sequence() -> None:
    control = _Control()
    config = GaussianSearchConfig(
        population_size=3,
        mutation_scale=0.2,
        initialization="center",
    )
    original = GaussianSearchAdapter(config)
    original.setup(control)
    first = tuple(original.propose(control, {}))
    original.update(
        control,
        first,
        (np.asarray([[3.0], [2.0], [1.0]]), np.zeros(3)),
        {},
    )

    restored = GaussianSearchAdapter(config)
    restored.set_state(original.get_state())
    restored.setup(control)

    expected = tuple(original.propose(control, {}))
    actual = tuple(restored.propose(control, {}))
    assert all(
        np.allclose(left.as_array(), right.as_array())
        for left, right in zip(expected, actual)
    )


def test_gradient_optimizer_keeps_explicit_seed_across_setup() -> None:
    control = _Control()
    adapter = GradientOptimizerAdapter(
        GradientOptimizerConfig.from_method(
            "gradient.sgd",
            learning_rate=0.1,
        )
    )
    seed = UnknownState(values=np.array([7.0, 8.0]))

    assert adapter.set_population((seed,)) is True
    adapter.setup(control)
    proposed = tuple(adapter.propose(control, {}))

    assert np.allclose(proposed[0].as_array(), seed.as_array())


def test_gaussian_search_accepts_matrix_population_snapshot() -> None:
    adapter = GaussianSearchAdapter(
        GaussianSearchConfig(population_size=3, mutation_scale=0.1)
    )
    population = np.asarray([[1.0, 2.0], [3.0, 4.0]], dtype=float)

    assert adapter.set_population(
        population,
        np.asarray([[3.0], [7.0]], dtype=float),
        np.zeros(2, dtype=float),
    ) is True
    restored = adapter.get_population()
    assert restored is not None
    np.testing.assert_allclose(np.asarray(restored[0], dtype=float), population[0])
