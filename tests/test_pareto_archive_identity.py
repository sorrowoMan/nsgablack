import json
from types import SimpleNamespace

import numpy as np
import pytest
from blackbase.types import CandidateBatch, UnknownState
from nsgablack.adapters import NSGA2Adapter
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.plugins import ParetoArchivePlugin


class Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=2, objectives=["score"], bounds=[(-2, 2)] * 2)

    def evaluate(self, x):
        return float(np.sum(np.asarray(x) ** 2))


def test_archive_composable_result_is_exportable_with_identity():
    solver = ComposableSolver(Problem(), adapter=NSGA2Adapter(population_size=4, offspring_size=4))
    solver.add_plugin(ParetoArchivePlugin())
    result = solver.run(max_steps=2)
    solver.export_case_result(result)
    assert solver.pareto_population_snapshot.candidate_tokens
    assert all(solver.pareto_population_snapshot.candidate_tokens)


def test_equal_values_distinct_identity_and_checkpoint_alignment():
    batch = CandidateBatch.from_candidates(
        [UnknownState([0, 0], {"model": name}) for name in ("a", "b")],
        candidate_tokens=("a", "b"),
    )
    solver = SimpleNamespace(generation=1, objective_names=["score"],
                             get_candidate_population_batch=lambda: batch,
                             set_pareto_snapshot=lambda x, f: None)
    archive = ParetoArchivePlugin()
    archive.solver = solver
    archive._get_population = lambda _: (batch.numeric_matrix, np.zeros((2, 1)), np.zeros(2))
    archive._update_from_solver(generation=0)
    archive._update_from_solver(generation=1)
    assert archive.active_segment.count() == 2  # repeat tokens are replaced, equal values are retained
    restored = ParetoArchivePlugin()
    restored.set_state(json.loads(json.dumps(archive.get_state())))
    restored._write_pareto_snapshot(solver)
    snapshot = solver.pareto_population_snapshot
    assert snapshot.candidate_tokens == ("a", "b")
    assert [c.metadata["model"] for c in snapshot.candidates] == ["a", "b"]
    corrupt = archive.get_state()
    corrupt["segments"][0]["X"][0][0] = 99
    with pytest.raises(ValueError, match="row-aligned"):
        restored.set_state(corrupt)


def test_empty_archive_checkpoint_keeps_dimensions():
    batch = CandidateBatch.from_candidates([[0, 0]], candidate_tokens=("x",))
    solver = SimpleNamespace(generation=1, objective_names=["score"],
                             get_candidate_population_batch=lambda: batch,
                             set_pareto_snapshot=lambda x, f: None)
    archive = ParetoArchivePlugin()
    archive.solver = solver
    archive._get_population = lambda _: (batch.numeric_matrix, np.zeros((1, 1)), np.ones(1))
    archive._update_from_solver(generation=0)
    restored = ParetoArchivePlugin()
    restored.set_state(json.loads(json.dumps(archive.get_state())))
    assert restored.active_segment.X.shape == (0, 2)
    assert restored.active_segment.F.shape == (0, 1)
