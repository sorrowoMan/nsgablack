import numpy as np
import pytest

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


class _DummyProblem:
    num_objectives = 2


class _DummySolver:
    def __init__(self, dim: int = 6) -> None:
        self.dimension = dim
        self.problem = _DummyProblem()
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


def _evaluate(candidates):
    arr = np.asarray(candidates, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    f1 = np.sum(arr * arr, axis=1)
    f2 = np.sum(np.abs(arr), axis=1)
    objectives = np.column_stack([f1, f2])
    violations = np.zeros(arr.shape[0], dtype=float)
    return objectives, violations


@pytest.mark.parametrize(
    "adapter",
    [
        DifferentialEvolutionAdapter(DEConfig(population_size=24, batch_size=12)),
        GradientDescentAdapter(GradientDescentConfig(max_directions=4)),
        PatternSearchAdapter(PatternSearchConfig(max_directions=4)),
        NSGA2Adapter(NSGA2Config(population_size=24, offspring_size=12)),
        NSGA3Adapter(NSGA3Config(population_size=24, offspring_size=12, divisions=4)),
        SPEA2Adapter(SPEA2Config(population_size=24, offspring_size=12, archive_size=24)),
    ],
)
def test_process_adapters_follow_propose_update_contract(adapter):
    solver = _DummySolver(dim=5)
    context = {"generation": 0}

    adapter.setup(solver)
    candidates = list(adapter.propose(solver, context))
    assert len(candidates) > 0
    objectives, violations = _evaluate(candidates)

    adapter.update(solver, candidates, objectives, violations, context)
    projection = adapter.get_runtime_context_projection(solver)
    assert isinstance(projection, dict)


@pytest.mark.parametrize(
    "adapter",
    [
        DifferentialEvolutionAdapter(DEConfig(population_size=16, batch_size=8)),
        NSGA2Adapter(NSGA2Config(population_size=16, offspring_size=8)),
        NSGA3Adapter(NSGA3Config(population_size=16, offspring_size=8, divisions=3)),
        SPEA2Adapter(SPEA2Config(population_size=16, offspring_size=8, archive_size=16)),
    ],
)
def test_population_based_adapters_support_set_population_contract(adapter):
    solver = _DummySolver(dim=4)
    pop = np.random.uniform(-1.0, 1.0, size=(16, 4))
    obj = np.column_stack([np.sum(pop * pop, axis=1), np.sum(np.abs(pop), axis=1)])
    vio = np.zeros(16, dtype=float)

    assert adapter.set_population(pop, obj, vio) is True
    projection = adapter.get_runtime_context_projection(solver)
    assert isinstance(projection, dict)


def test_nsga3_projection_contains_reference_points():
    solver = _DummySolver(dim=4)
    adapter = NSGA3Adapter(NSGA3Config(population_size=20, offspring_size=10, divisions=3))
    context = {"generation": 0}

    adapter.setup(solver)
    candidates = list(adapter.propose(solver, context))
    objectives, violations = _evaluate(candidates)
    adapter.update(solver, candidates, objectives, violations, context)

    projection = adapter.get_runtime_context_projection(solver)
    assert "mo_weights" in projection
    assert np.asarray(projection["mo_weights"], dtype=float).ndim == 2

