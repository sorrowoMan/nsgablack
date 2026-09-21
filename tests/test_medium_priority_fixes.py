from __future__ import annotations

import numpy as np
import pytest

from blackbase.types import CandidateBatch
from nsgablack.adapters import PopulationPartition
from nsgablack.adapters.moead import MOEADAdapter, MOEADConfig
from nsgablack.adapters.vns import VNSAdapter, VNSConfig
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.evolution_solver import EvolutionSolver
from nsgablack.plugins.runtime.pareto_archive import ParetoArchiveConfig, ParetoArchivePlugin


def test_pareto_archive_truncates_with_crowding() -> None:
    plugin = ParetoArchivePlugin(config=ParetoArchiveConfig(keep_infeasible=True, max_size=2))
    X = np.array([[0.0], [1.0], [2.0]], dtype=float)
    F = np.array([[0.0, 2.0], [1.0, 1.0], [2.0, 0.0]], dtype=float)
    V = np.zeros(3, dtype=float)

    class _Solver:
        population = X
        objectives = F
        constraint_violations = V
        objective_names = ("f1", "f2")

        def set_pareto_snapshot(self, solutions, objectives):
            self.pareto_solutions = solutions
            self.pareto_objectives = objectives

    solver = _Solver()
    plugin.attach(solver)
    plugin.on_generation_committed(0, {"status": "committed"})
    kept = {tuple(row.tolist()) for row in plugin.archive_F}
    assert (0.0, 2.0) in kept
    assert (2.0, 0.0) in kept
    assert len(kept) == 2


class _PartitionedArchiveAdapter:
    def __init__(self, partitions) -> None:
        self._partitions = tuple(partitions)

    def get_population_partitions(self):
        return self._partitions


class _PartitionedArchiveSolver:
    population_authority_mode = "partitioned"
    objective_names = ("cost", "risk")

    def __init__(self, partitions, committed) -> None:
        self.adapter = _PartitionedArchiveAdapter(partitions)
        self._committed = dict(committed)
        self.pareto_solutions = None
        self.pareto_objectives = None

    def get_candidate_population_partitions(self):
        return dict(self._committed)

    def set_pareto_snapshot(self, solutions, objectives):
        self.pareto_solutions = solutions
        self.pareto_objectives = objectives


def _committed_batch(partition: PopulationPartition) -> CandidateBatch:
    return CandidateBatch.from_candidates(
        tuple(partition.population),
        candidate_tokens=partition.candidate_tokens,
    )


def test_pareto_archive_aggregates_aligned_committed_partitions() -> None:
    explorer = PopulationPartition(
        partition_id="explorer/population",
        population=np.asarray([[0.0], [1.0]], dtype=float),
        objectives=np.asarray([[0.0, 2.0], [2.0, 2.0]], dtype=float),
        violations=np.zeros(2, dtype=float),
        candidate_tokens=("explorer:0", "explorer:1"),
        metadata={"objective_labels": ["cost", "risk"]},
    )
    exploiter = PopulationPartition(
        partition_id="exploiter/population",
        population=np.asarray([[2.0], [3.0]], dtype=float),
        objectives=np.asarray([[2.0, 0.0], [3.0, 3.0]], dtype=float),
        violations=np.zeros(2, dtype=float),
        candidate_tokens=("exploiter:0", "exploiter:1"),
        metadata={"objective_labels": ["cost", "risk"]},
    )
    solver = _PartitionedArchiveSolver(
        (explorer, exploiter),
        {
            explorer.partition_id: _committed_batch(explorer),
            exploiter.partition_id: _committed_batch(exploiter),
        },
    )
    plugin = ParetoArchivePlugin()
    plugin.attach(solver)

    plugin.on_generation_committed(0, {"status": "committed"})

    assert {
        tuple(row.tolist()) for row in np.asarray(plugin.archive_F, dtype=float)
    } == {(0.0, 2.0), (2.0, 0.0)}
    assert np.array_equal(solver.pareto_objectives, plugin.archive_F)


def test_pareto_archive_rejects_incompatible_partition_dimensions() -> None:
    two_objectives = PopulationPartition(
        partition_id="explorer/population",
        population=np.asarray([[0.0]], dtype=float),
        objectives=np.asarray([[0.0, 2.0]], dtype=float),
        violations=np.zeros(1, dtype=float),
        candidate_tokens=("explorer:0",),
    )
    one_objective = PopulationPartition(
        partition_id="exploiter/population",
        population=np.asarray([[1.0]], dtype=float),
        objectives=np.asarray([[1.0]], dtype=float),
        violations=np.zeros(1, dtype=float),
        candidate_tokens=("exploiter:0",),
    )
    solver = _PartitionedArchiveSolver(
        (two_objectives, one_objective),
        {
            two_objectives.partition_id: _committed_batch(two_objectives),
            one_objective.partition_id: _committed_batch(one_objective),
        },
    )
    plugin = ParetoArchivePlugin()
    plugin.attach(solver)

    with pytest.raises(ValueError, match="different decision or objective dimensions"):
        plugin.on_generation_committed(0, {"status": "committed"})


def test_pareto_archive_rejects_uncommitted_partition_state() -> None:
    partition = PopulationPartition(
        partition_id="explorer/population",
        population=np.asarray([[0.0]], dtype=float),
        objectives=np.asarray([[0.0, 2.0]], dtype=float),
        violations=np.zeros(1, dtype=float),
        candidate_tokens=("explorer:0",),
    )
    stale_batch = CandidateBatch.from_candidates(
        (np.asarray([9.0]),),
        candidate_tokens=partition.candidate_tokens,
    )
    solver = _PartitionedArchiveSolver(
        (partition,),
        {partition.partition_id: stale_batch},
    )
    plugin = ParetoArchivePlugin()
    plugin.attach(solver)

    with pytest.raises(ValueError, match="committed CandidateBatch"):
        plugin.on_generation_committed(0, {"status": "committed"})


class _ToyProblem(BlackBoxProblem):
    def __init__(self, dim: int = 2) -> None:
        super().__init__(name="toy", dimension=int(dim), objectives=["f1", "f2"])

    def evaluate(self, candidate):
        arr = np.asarray(candidate, dtype=float)
        return np.array([arr[0], arr[1]], dtype=float)


def test_solver_sbx_can_generate_non_linear_offspring_when_eta_small() -> None:
    solver = EvolutionSolver(
        _ToyProblem(dim=64),
        pop_size=2,
        sbx_eta_c=0.1,
        crossover_rate=1.0,
        random_seed=7,
    )
    parents = np.vstack([np.zeros(64, dtype=float), np.ones(64, dtype=float)])
    offspring = solver.crossover(parents)
    # SBX should not degenerate to identity when eta is very small.
    assert not np.allclose(offspring, parents)


def test_update_pareto_solutions_keeps_front_boundaries_with_crowding() -> None:
    solver = EvolutionSolver(_ToyProblem(), pop_size=60, max_pareto_solutions=50)
    xs = np.linspace(0.0, 59.0, 60)
    solver.population = np.column_stack([xs, xs])
    solver.objectives = np.column_stack([xs, 59.0 - xs])
    solver.constraint_violations = np.zeros(60, dtype=float)
    solver.commit_candidate_population(solver.population, None)
    solver.update_pareto_solutions()
    kept_first_dim = set(np.asarray(solver.pareto_solutions["individuals"])[:, 0].astype(float).tolist())
    assert 0.0 in kept_first_dim
    assert 59.0 in kept_first_dim
    assert len(kept_first_dim) == 50


def test_moead_equal_decomposition_value_does_not_replace() -> None:
    adapter = MOEADAdapter(MOEADConfig())
    adapter.pop_F = np.array([[1.0, 1.0]], dtype=float)
    adapter.pop_V = np.array([0.0], dtype=float)
    adapter.weights = np.array([[0.5, 0.5]], dtype=float)
    adapter.ideal = np.array([0.0, 0.0], dtype=float)
    assert adapter._is_better_for_subproblem(np.array([1.0, 1.0], dtype=float), 0.0, 0) is False


def test_vns_sigma_is_capped() -> None:
    adapter = VNSAdapter(VNSConfig(base_sigma=0.5, scale=10.0, max_sigma=1.0))
    adapter.k = 4
    assert np.isclose(adapter._current_sigma(), 1.0)
