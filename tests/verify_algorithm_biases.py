"""Verification suite: process algorithms are adapters, not biases."""

import numpy as np

from nsgablack.core.adapters import (
    DEConfig,
    DifferentialEvolutionAdapter,
    GradientDescentAdapter,
    GradientDescentConfig,
    NSGA2Adapter,
    NSGA2Config,
    NSGA3Adapter,
    NSGA3Config,
    PatternSearchAdapter,
    PatternSearchConfig,
    SPEA2Adapter,
    SPEA2Config,
)


class _Problem:
    num_objectives = 2


class _Solver:
    def __init__(self, dim: int = 5) -> None:
        self.dimension = dim
        self.problem = _Problem()
        self.population = None
        self.objectives = None
        self.constraint_violations = None

    def init_candidate(self, context):
        _ = context
        return np.random.uniform(-1.0, 1.0, size=self.dimension)

    def mutate_candidate(self, x, context):
        sigma = float(context.get("mutation_sigma", 0.05))
        return np.asarray(x, dtype=float) + np.random.normal(0.0, sigma, size=len(x))

    def repair_candidate(self, x, context):
        _ = context
        return np.clip(np.asarray(x, dtype=float), -3.0, 3.0)


def _eval(candidates):
    arr = np.asarray(candidates, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    f1 = np.sum(arr * arr, axis=1)
    f2 = np.sum(np.abs(arr), axis=1)
    return np.column_stack([f1, f2]), np.zeros(arr.shape[0], dtype=float)


def test_imports():
    assert DifferentialEvolutionAdapter is not None
    assert GradientDescentAdapter is not None
    assert PatternSearchAdapter is not None
    assert NSGA2Adapter is not None
    assert NSGA3Adapter is not None
    assert SPEA2Adapter is not None


def test_all_process_algorithms_run_as_adapters():
    solver = _Solver()
    context = {"generation": 0}

    adapters = [
        DifferentialEvolutionAdapter(DEConfig(population_size=20, batch_size=10)),
        GradientDescentAdapter(GradientDescentConfig(max_directions=3)),
        PatternSearchAdapter(PatternSearchConfig(max_directions=3)),
        NSGA2Adapter(NSGA2Config(population_size=20, offspring_size=10)),
        NSGA3Adapter(NSGA3Config(population_size=20, offspring_size=10, divisions=3)),
        SPEA2Adapter(SPEA2Config(population_size=20, offspring_size=10)),
    ]

    for adapter in adapters:
        adapter.setup(solver)
        candidates = list(adapter.propose(solver, context))
        assert len(candidates) > 0
        objectives, violations = _eval(candidates)
        adapter.update(solver, candidates, objectives, violations, context)
        projection = adapter.get_runtime_context_projection(solver)
        assert isinstance(projection, dict)


def test_population_contract_for_population_based_adapters():
    solver = _Solver(dim=4)
    pop = np.random.uniform(-1.0, 1.0, size=(12, 4))
    obj = np.column_stack([np.sum(pop * pop, axis=1), np.sum(np.abs(pop), axis=1)])
    vio = np.zeros(12, dtype=float)

    for adapter in (
        DifferentialEvolutionAdapter(DEConfig(population_size=12, batch_size=6)),
        NSGA2Adapter(NSGA2Config(population_size=12, offspring_size=6)),
        NSGA3Adapter(NSGA3Config(population_size=12, offspring_size=6, divisions=2)),
        SPEA2Adapter(SPEA2Config(population_size=12, offspring_size=6)),
    ):
        ok = adapter.set_population(pop, obj, vio)
        assert ok is True
        assert isinstance(adapter.get_runtime_context_projection(solver), dict)

