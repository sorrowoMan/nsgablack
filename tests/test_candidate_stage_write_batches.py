"""Private stage batching preserves identities and fails before evaluation."""
import numpy as np
import pytest
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context

from blackbase.types import UnknownState
from nsgablack.adapters import AlgorithmAdapter
from nsgablack.core import BlackBoxProblem, ComposableSolver, SolverBase
from nsgablack.core.state.solution_pool import BATCH_SCHEMA
from nsgablack.core.blank_solver import _CANDIDATE_POOL_WRITES
from nsgablack.representation import RepresentationPipeline


class Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=2, bounds=[(-1000., 1000.)] * 2, objectives=["min"])
        self.calls = 0

    def evaluate(self, x):
        self.calls += 1
        return [float(np.sum(np.asarray(x) ** 2))]


class Mutation:
    def mutate(self, candidate, context=None):
        candidate[0] += 1.
        return candidate


class Repair:
    def repair(self, candidate, context=None):
        candidate[1] = max(0., candidate[1])
        return candidate


def make_solver(backend, tmp_path):
    return SolverBase(Problem(), representation_pipeline=RepresentationPipeline(
        mutator=Mutation(), repair=Repair()), snapshot_store_backend=backend,
        snapshot_store_dir=str(tmp_path))


@pytest.mark.parametrize("backend", ["memory", "file"])
def test_200_candidates_four_stages_write_four_batches_without_readback(backend, tmp_path, monkeypatch):
    solver = make_solver(backend, tmp_path)
    writes, reads = [], []
    write, read = solver.snapshot_store.write, solver.snapshot_store.read_verified

    def observe_write(data, **kwargs):
        if kwargs.get("schema") == BATCH_SCHEMA:
            writes.append((data["stage"], tuple(data["batch"]["candidate_tokens"])))
        return write(data, **kwargs)

    def observe_read(identity):
        reads.append(identity)
        return read(identity)

    monkeypatch.setattr(solver.snapshot_store, "write", observe_write)
    monkeypatch.setattr(solver.snapshot_store, "read_verified", observe_read)
    solver.solution_pool.begin_attempt()
    tokens = []
    with solver._batch_candidate_pool_writes():
        for index in range(200):
            source = np.array([float(index), -2.])
            changed = solver.mutate_candidate(source)
            provenance = solver.candidate_provenance_for(changed)
            fixed = solver.repair_candidate(changed)
            repaired_provenance = solver.candidate_provenance_for(fixed)
            assert repaired_provenance.candidate_token == provenance.candidate_token
            assert provenance.parent_token != provenance.candidate_token
            tokens.append(provenance.candidate_token)
            np.testing.assert_array_equal(source, [float(index), -2.])
            np.testing.assert_array_equal(changed, [float(index + 1), -2.])
            np.testing.assert_array_equal(fixed, [float(index + 1), 0.])
            with pytest.raises(ValueError):
                fixed[0] = -99.
        assert writes == []  # Private immutable drafts, not published references.
    assert [stage for stage, _ in writes] == ["mutation_parent", "mutation", "repair_input", "repair"]
    assert all(len(saved) == 200 for _, saved in writes)
    assert writes[1][1] == writes[2][1] == writes[3][1] == tuple(tokens)
    assert reads == []
    assert solver.solution_pool.record_count == 4
    assert solver.solution_pool.select(stage=None) == ()


def test_semantic_metadata_and_same_token_versions_survive_batch_flush(tmp_path):
    solver = make_solver("memory", tmp_path)
    state = UnknownState([2., -3.], {"layout": {"shape": (2,)}, "model": "first"})
    provenance = solver._new_candidate_provenance(source_kind="test")
    solver.solution_pool.begin_attempt()
    with solver._batch_candidate_pool_writes():
        before = solver._register_solution_value(state, provenance, stage="repair_input")
        after = solver._register_solution_value(state.with_values([2., 0.]), provenance, stage="repair")
    records = list(solver.solution_pool._records.values())
    assert records[0].tokens == records[1].tokens == (provenance.candidate_token,)
    assert records[0].snapshot != records[1].snapshot
    assert dict(before.metadata) == dict(after.metadata) == dict(state.metadata)
    for record in records:
        value = solver.solution_pool._payload(record)[1].semantic_states[0]
        assert dict(value.metadata) == dict(state.metadata)
    assert state.values[1] == before.values[1] == -3.
    assert after.values[1] == 0.


def test_nested_batches_share_scope_and_failed_call_does_not_flush(tmp_path):
    solver = make_solver("memory", tmp_path)
    solver.solution_pool.begin_attempt()
    with pytest.raises(RuntimeError, match="operator failed"):
        with solver._batch_candidate_pool_writes():
            with solver._batch_candidate_pool_writes():
                solver.mutate_candidate(np.array([1., -1.]))
            raise RuntimeError("operator failed")
    assert solver.solution_pool.record_count == 0
    solver.mutate_candidate(np.array([1., -1.]))
    assert solver.solution_pool.record_count == 2  # The failed scope was cleared.


def test_outside_attempt_writes_remain_immediate(tmp_path):
    solver = make_solver("memory", tmp_path)
    with solver._batch_candidate_pool_writes():
        solver.mutate_candidate(np.array([1., -1.]))
        assert solver.solution_pool.record_count == 2
        assert len(solver.solution_pool.select(stage="mutation")) == 1


def test_caught_inner_failure_discards_only_inner_queued_values(tmp_path):
    solver = make_solver("memory", tmp_path)
    solver.solution_pool.begin_attempt()
    with solver._batch_candidate_pool_writes():
        solver.mutate_candidate(np.array([1., -1.]))
        with pytest.raises(RuntimeError, match="inner failed"):
            with solver._batch_candidate_pool_writes():
                solver.mutate_candidate(np.array([100., -1.]))
                raise RuntimeError("inner failed")
        solver.mutate_candidate(np.array([2., -1.]))
    records = list(solver.solution_pool._records.values())
    assert len(records) == 2
    assert all(len(record.tokens) == 2 for record in records)
    np.testing.assert_array_equal(solver.solution_pool._payload(records[1])[1].numeric_matrix[:, 0], [2., 3.])


def test_copied_context_does_not_share_a_write_queue_between_threads(tmp_path):
    solver = make_solver("memory", tmp_path)
    solver.solution_pool.begin_attempt()
    with solver._batch_candidate_pool_writes():
        solver.mutate_candidate(np.array([1., -1.]))
        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(copy_context().run, solver.mutate_candidate,
                            np.array([10., -1.])).result(timeout=5.)
        # The other thread uses immediate writes, never the parent's queue.
        assert solver.solution_pool.record_count == 2
    records = list(solver.solution_pool._records.values())
    assert len(records) == 4
    assert all(len(record.tokens) == 1 for record in records)


def test_closed_copied_context_releases_drafts_and_cannot_enqueue_again(tmp_path):
    solver = make_solver("memory", tmp_path)
    solver.solution_pool.begin_attempt()
    with solver._batch_candidate_pool_writes():
        solver.mutate_candidate(np.array([1., -1.]))
        captured = copy_context()
    pending = captured.get(_CANDIDATE_POOL_WRITES)
    assert not pending.active and pending.stages == {}
    captured.run(solver.mutate_candidate, np.array([2., -1.]))
    assert solver.solution_pool.record_count == 4


def test_population_initialization_batches_private_versions_and_preserves_tokens(tmp_path):
    solver = make_solver("memory", tmp_path)
    solver.solution_pool.begin_attempt()
    candidates = solver.init_population(200)
    records = list(solver.solution_pool._records.values())
    assert len(records) == 1 and records[0].stage == "initial"
    tokens = tuple(solver.candidate_provenance_for(candidate).candidate_token for candidate in candidates)
    assert records[0].tokens == tokens and len(set(tokens)) == 200


class Search(AlgorithmAdapter):
    def __init__(self):
        super().__init__(name="stage-search")
        self.counter = 0

    def get_state(self):
        return {"counter": self.counter}

    def set_state(self, state):
        self.counter = state["counter"]

    def propose(self, control, context):
        self.counter += 1
        return [control.mutate_candidate(np.array([float(i), -1.]), context) for i in range(4)]

    def update(self, control, candidates, feedback, context):
        pass


def test_stage_flush_failure_rolls_back_adapter_and_does_not_evaluate(monkeypatch):
    problem, adapter = Problem(), Search()
    solver = ComposableSolver(problem, adapter=adapter,
        representation_pipeline=RepresentationPipeline(mutator=Mutation(), repair=Repair()))
    write = solver.snapshot_store.write

    def fail_stage(data, **kwargs):
        if kwargs.get("schema") == BATCH_SCHEMA and data.get("stage") == "mutation":
            raise OSError("stage write failed")
        return write(data, **kwargs)

    monkeypatch.setattr(solver.snapshot_store, "write", fail_stage)
    with pytest.raises(OSError, match="stage write failed"):
        solver.step()
    assert problem.calls == solver.evaluation_count == 0
    assert adapter.counter == 0
    assert solver.solution_pool.record_count == 0
    assert solver.solution_pool.select(stage=None) == ()


def test_invalid_proposal_shape_fails_before_private_batches_are_written(monkeypatch):
    class InvalidSearch(Search):
        def propose(self, control, context):
            super().propose(control, context)
            return [np.zeros(3)]

    problem, adapter = Problem(), InvalidSearch()
    solver = ComposableSolver(problem, adapter=adapter,
        representation_pipeline=RepresentationPipeline(mutator=Mutation(), repair=Repair()))
    writes = []
    write = solver.snapshot_store.write

    def observe(data, **kwargs):
        if kwargs.get("schema") == BATCH_SCHEMA:
            writes.append(data["stage"])
        return write(data, **kwargs)

    monkeypatch.setattr(solver.snapshot_store, "write", observe)
    with pytest.raises(ValueError):
        solver.step()
    assert writes == [] and problem.calls == solver.evaluation_count == 0
    assert adapter.counter == 0 and solver.solution_pool.record_count == 0
