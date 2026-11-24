"""人口组独立裸内核的配对与恢复行为；完整 benchmark 由标准 Project 执行。"""

import numpy as np
import pytest

from benchmarks.transparency_population import (
    PopulationReferenceKernel, make_population_adapter, make_population_pipeline,
    project_population, run_population_reference,
)
from nsgablack.core import BlackBoxProblem, ComposableSolver


ALGORITHMS = ("nsga2", "nsga3", "spea2", "moead", "de")


class AnalyticPairProblem(BlackBoxProblem):
    def __init__(self, objectives=2):
        super().__init__(dimension=8, objectives=["min"] * objectives, bounds=[(0.0, 1.0)] * 8)

    def evaluate(self, candidate):
        values = np.asarray(candidate)
        feedback = [np.sum(values * values), np.sum((values - 1.0) ** 2)]
        if len(self.objectives) == 3:
            feedback.append(np.sum((values - 0.5) ** 2))
        return np.asarray(feedback)


def advance(kernel, problem):
    candidates = np.clip(kernel.ask(), 0.0, 1.0)
    kernel.tell(candidates, np.asarray([problem.evaluate(row) for row in candidates]), np.zeros(len(candidates)))


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize("seed", [3, 17])
def test_population_reference_matches_each_framework_commit(algorithm, seed):
    problem = AnalyticPairProblem()
    solver = ComposableSolver(problem, adapter=make_population_adapter(seed, algorithm=algorithm),
                             representation_pipeline=make_population_pipeline(seed))
    solver.set_random_seed(seed)
    solver.setup()
    kernel = PopulationReferenceKernel(algorithm, seed)
    for _ in range(3):
        assert solver.step().committed
        advance(kernel, problem)
        actual, expected = project_population(solver), kernel.project()
        assert actual.keys() == expected.keys()
        for field in actual:
            if isinstance(actual[field], dict):
                assert actual[field].keys() == expected[field].keys()
                for key in actual[field]:
                    np.testing.assert_allclose(actual[field][key], expected[field][key], rtol=0., atol=1e-14)
            else:
                np.testing.assert_allclose(actual[field], expected[field], rtol=0.0, atol=1e-14)


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_population_bare_checkpoint_continues_exactly(algorithm):
    problem = AnalyticPairProblem(objectives=3)
    uninterrupted = PopulationReferenceKernel(algorithm, 41)
    for _ in range(2):
        advance(uninterrupted, problem)
    restored = PopulationReferenceKernel(algorithm, 41)
    restored.restore(uninterrupted.snapshot())
    for _ in range(3):
        advance(uninterrupted, problem)
        advance(restored, problem)
        assert restored.project() == uninterrupted.project()


def test_bare_reference_never_calls_adapter_algorithm_or_checkpoint_methods(monkeypatch):
    from nsgablack.adapters import NSGA2Adapter, MOEADAdapter, DifferentialEvolutionAdapter

    def forbidden(*args, **kwargs):
        raise AssertionError("bare reference called Adapter runtime")

    for adapter in (NSGA2Adapter, MOEADAdapter, DifferentialEvolutionAdapter):
        for method in ("propose", "update", "get_state", "set_state"):
            monkeypatch.setattr(adapter, method, forbidden)
    problem = AnalyticPairProblem()
    for algorithm in ALGORITHMS:
        result = run_population_reference(29, 3, lambda row: (problem.evaluate(row), 0.0), algorithm=algorithm)
        assert len(result["trace"]) == 3
        assert result["state"] == result["trace"][-1]["state"]
        assert np.shape(result["state"]["population"]) == (10, 8)
