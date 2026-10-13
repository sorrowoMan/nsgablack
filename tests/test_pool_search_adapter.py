import numpy as np
import pytest

from nsgablack.adapters import (
    PoolSearchAdapter, PoolSearchSpec, SimulatedAnnealingAdapter,
    NSGA2Adapter, NSGA3Adapter,
)
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.representation import RepresentationPipeline


class ConstantProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["min"], bounds=[(-100.,100.)])
    def evaluate(self, x):
        return [1.]


class Operator:
    def initialize(self, problem, context):
        return np.array([0.])
    def mutate(self, candidate, context):
        return candidate + 1.


def make_solver(count=100, batch_size=199, *, nested=False):
    producer = SimulatedAnnealingAdapter(name="seed_sa", batch_size=batch_size, random_seed=2)
    left = NSGA2Adapter(name="left", population_size=count, offspring_size=2)
    right = NSGA3Adapter(name="right", population_size=count, offspring_size=2)
    adapter = PoolSearchAdapter(producer, [PoolSearchSpec(left,count), PoolSearchSpec(right,count)],
                                stagnation_steps=1, recovery_steps=2)
    if nested:
        from nsgablack.adapters import CompositeAdapter
        adapter = CompositeAdapter([adapter], name="outer")
    operator = Operator()
    solver = ComposableSolver(ConstantProblem(), adapter=adapter,
        representation_pipeline=RepresentationPipeline(initializer=operator, mutator=operator))
    solver.setup()
    return solver, producer, left, right


def test_prepare_200_split_into_two_100_populations_then_wake_and_return():
    solver, producer, left, right = make_solver()
    assert solver.solution_pool.select() == ()
    assert solver.step().committed  # SA baseline: 1
    assert solver.step().committed  # 199 evaluated candidates
    assert solver.adapter.phase == "search"
    assert solver.adapter.prepared_count == 200
    assert len(solver.solution_pool.select()) == 200
    temperature = producer.temperature
    assert solver.step().committed  # pool inputs, 100 each
    assert len(left.population) == len(right.population) == 100
    assert set(left.get_population_candidate_tokens()).isdisjoint(right.get_population_candidate_tokens())
    assert producer.temperature == temperature
    assert solver.step().committed  # constant objective: stagnation
    assert solver.adapter.phase == "recovery"
    assert producer.temperature == temperature
    assert solver.step().committed  # explicit restart and baseline
    assert producer.temperature == producer.cfg.initial_temperature
    assert solver.step().committed  # recovery neighbors
    assert solver.adapter.phase == "return"
    assert solver.step().committed  # compete in both populations
    assert solver.adapter.phase == "search"
    assert len(left.population) == len(right.population) == 100
    assert solver.solution_pool.publication_ref()
    published = solver.snapshot_store.read_verified(solver.get_population_authority_identity().snapshot)
    assert published.data["solution_pool_ref"] == solver.solution_pool.publication_ref()
    assert solver.solution_pool.record_count < 50  # Private operator drafts leave the pool index.


def test_failure_rolls_back_pool_population_and_seed_cursors():
    solver, producer, left, right = make_solver(count=2, batch_size=3)
    solver.step()
    solver.step()
    before = solver.solution_pool.select()
    ordinary = right.update
    def failing(*args):
        ordinary(*args)
        raise RuntimeError("second population failed")
    right.update = failing
    with pytest.raises(RuntimeError, match="second population"):
        solver.step()
    assert solver.solution_pool.select() == before
    assert left.population is None and right.population is None
    assert solver.adapter.input_ids == {}
    right.update = ordinary
    assert solver.step().committed
    assert len(left.population) == len(right.population) == 2


def test_pool_and_orchestration_restore_keep_waiting_producer_and_private_units():
    from nsgablack.plugins import CheckpointResumePlugin
    source, producer, left, right = make_solver(count=2,batch_size=3)
    for _ in range(3):
        source.step()
    target, target_producer, target_left, target_right = make_solver(count=2,batch_size=3)
    writer = CheckpointResumePlugin()
    writer.attach(source)
    payload = writer._build_payload(solver=source, reason="pool-search")
    reader = CheckpointResumePlugin()
    reader.attach(target)
    reader._restore_payload(solver=target, payload=payload)
    assert target.adapter.phase == "search"
    assert target.adapter.ready_stamp == source.adapter.ready_stamp
    np.testing.assert_array_equal(target_left.population, left.population)
    np.testing.assert_array_equal(target_right.population, right.population)
    assert target_producer.temperature == producer.temperature
    published = target.snapshot_store.read_verified(target.get_population_authority_identity().snapshot)
    assert published.data["solution_pool_ref"] == target.solution_pool.publication_ref()
    assert target.step().committed
    assert target.adapter.phase == "recovery"


def test_pool_intake_retries_rejected_seeds_without_losing_allocation():
    from blackbase.contracts import BatchDisposition
    solver, producer, left, right = make_solver(count=2,batch_size=3)
    solver.step()
    solver.step()
    class Partial:
        policy_id = "partial-pool-intake"
        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), (0, 2))
    solver.set_evaluation_acceptance_policy(Partial())
    assert solver.step().committed
    assert len(left.population) == len(right.population) == 1
    assert solver.adapter.phase == "search" and solver.adapter.best_metric is None
    assert all(solver.solution_pool.input_remaining(key) == 1
               for key in solver.adapter.input_ids.values())
    solver.set_evaluation_acceptance_policy(None)
    assert solver.step().committed
    assert len(left.population) == len(right.population) == 2
    assert solver.adapter.phase == "search" and solver.adapter.stagnation == 0


def test_zero_admission_retains_valid_intake_for_next_attempt():
    from blackbase.contracts import BatchDisposition
    solver, producer, left, right = make_solver(count=2,batch_size=3)
    solver.step()
    solver.step()
    before = solver.solution_pool.select()
    class Reject:
        policy_id = "reject-intake"
        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), ())
    solver.set_evaluation_acceptance_policy(Reject())
    assert solver.step().status == "rejected"
    assert solver.solution_pool.select() == before
    assert len(solver.adapter.input_ids) == 2
    assert all(solver.solution_pool.input_remaining(key) == 2
               for key in solver.adapter.input_ids.values())
    solver.set_evaluation_acceptance_policy(None)
    assert solver.step().committed
    assert len(left.population) == len(right.population) == 2


def test_pool_checkpoint_is_required_even_in_non_strict_mode():
    from nsgablack.plugins import CheckpointResumePlugin, CheckpointResumeConfig
    solver, *_ = make_solver(count=2,batch_size=3)
    reader = CheckpointResumePlugin(CheckpointResumeConfig(strict=False))
    reader.attach(solver)
    with pytest.raises(ValueError, match="solution_pool"):
        reader._apply_component_states(solver, {})


def test_nested_pool_search_selects_its_candidates_under_outer_source():
    solver, producer, left, right = make_solver(count=2,batch_size=3,nested=True)
    for _ in range(4):
        assert solver.step().committed
    assert solver.adapter.adapters[0].phase == "recovery"
    assert len(left.population) == len(right.population) == 2
    assert all(p.partition_id.startswith("child:0:pool_search/")
               for p in solver.adapter.get_population_partitions())
