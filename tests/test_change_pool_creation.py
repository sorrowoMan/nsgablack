"""Proposal-attached membership plans can freeze absent ordinary targets."""
from __future__ import annotations

import copy
from functools import partial

import numpy as np
import pytest
from blackbase.contracts import BatchDisposition
from blackbase.types import CandidateBatch

from nsgablack.adapters import ChangeBatchResult, ChangeResult, MOEADAdapter, NSGA2Adapter, PoolEdit, VNSAdapter
from nsgablack.adapters.change_access import scoped_change_access
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.core.control_plane import BudgetController
from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin
from nsgablack.representation import ClipRepair, RepresentationPipeline, UniformInitializer


class CreationSphere(BlackBoxProblem):
    def __init__(self, count=1):
        super().__init__(dimension=1, objectives=["minimize"] * count, bounds=[(-10., 10.)])
        self.calls = []

    def evaluate(self, candidate):
        row = np.array(candidate, dtype=float, copy=True)
        self.calls.append(row)
        return [float(row @ row)] * self.get_num_objectives()


def creation_child(request, *, rng, create=True):
    donor = request.pool.subpool("donor")
    plans = (request.pool.replace_members("created", donor.refs, create=create),
             request.pool.replace_members("empty", (), create=create))
    return ChangeResult(request.candidate - rng.uniform(.1, .2, size=1), edits=plans)


def creation_pair(request, *, rng):
    donor = request.pool.subpool("donor")
    empty = request.pool.replace_members("empty", (), create=True)
    shift = rng.uniform(.1, .2, size=1)
    return ChangeBatchResult(tuple(ChangeResult(request.candidate - shift * (index + 1),
        edits=(request.pool.replace_members(name, donor.refs, create=True), empty))
        for index, name in enumerate(("left", "right")[:request.max_outputs])))


def forged_creation(request, *, rng):
    del rng
    # Deliberately bypass the facade while constructing a valid-looking plan:
    # the result boundary must recheck both its destination and source refs.
    store = request.pool._pool
    edit = PoolEdit("created", store.subpool_refs("donor"),
        expected={"pool_id": store.pool_id, "name": "created", "absent": True})
    return ChangeResult(request.candidate - .1, edits=(edit,))


def make_solver(kind="vns", *, change=None, setup=True):
    if kind == "ga":
        adapter = NSGA2Adapter(population_size=4, offspring_size=4, change=change or creation_pair)
    elif kind == "moead":
        adapter = MOEADAdapter(population_size=4, neighborhood_size=4, batch_size=2, nr=2,
                               change=change or creation_child)
    else:
        adapter = VNSAdapter(batch_size=2, k_max=3, restart_on_stagnation=False,
                             change=change or creation_child)
    solver = ComposableSolver(CreationSphere(2 if kind == "moead" else 1), adapter=adapter,
        representation_pipeline=RepresentationPipeline(initializer=UniformInitializer(4., 4.),
                                                       repair=ClipRepair(-10., 10.)))
    solver.set_random_seed(259)
    if setup:
        solver.setup()
        refs = solver.store_solutions(CandidateBatch.from_candidates([[2.]], candidate_tokens=("donor",)),
                                      source="creation-test")
        solver.solution_pool.create_subpool("donor", refs)
    return solver


@pytest.mark.filterwarnings("ignore:MOEADAdapter did not detect an archive plugin:RuntimeWarning")
@pytest.mark.parametrize("kind", ["vns", "moead", "ga"])
def test_scalar_and_batch_change_edits_create_missing_and_empty_pools_only_on_commit(kind):
    solver = make_solver(kind)
    pool = solver.solution_pool
    donor = pool.subpool_refs("donor")
    assert solver.step().committed
    assert not pool.has_subpool("empty")
    assert solver.step().committed
    names = ("left", "right") if kind == "ga" else ("created",)
    for name in names:
        assert pool.subpool_refs(name) == donor
        assert pool.subpool_metadata(name)["published"] is True
        assert pool.subpool_metadata(name)["kind"] == "candidate_collection"
    assert pool.subpool_refs("empty") == ()
    assert pool.subpool_refs("donor") == donor
    np.testing.assert_array_equal(solver.read_solutions(donor).numeric_matrix, [[2.]])
    assert solver.evaluation_count == len(solver.problem.calls) == (3 if kind == "vns" else 8 if kind == "ga" else 6)


def test_create_false_keeps_the_missing_target_error_before_evaluation():
    solver = make_solver(change=partial(creation_child, create=False))
    assert solver.step().committed
    before = copy.deepcopy(solver.adapter.get_state())
    with pytest.raises(KeyError, match="does not exist"):
        solver.step()
    assert solver.adapter.get_state() == before
    assert not solver.solution_pool.has_subpool("created")
    assert solver.evaluation_count == len(solver.problem.calls) == 1


@pytest.mark.parametrize("allowed", [("donor",), ("created",)])
def test_result_precheck_rejects_forged_undeclared_destination_or_source(allowed, monkeypatch):
    solver = make_solver(change=forged_creation)
    assert solver.step().committed
    adapter = solver.adapter
    original = adapter.propose

    def restricted_propose(*args, **kwargs):
        with scoped_change_access((), subpools=allowed, allow_main=False):
            return original(*args, **kwargs)

    monkeypatch.setattr(adapter, "propose", restricted_propose)
    before = copy.deepcopy(adapter.get_state())
    with pytest.raises(ValueError, match="declared inputs"):
        solver.step()
    assert adapter.get_state() == before
    assert not solver.solution_pool.has_subpool("created")
    assert solver.evaluation_count == 1


def test_scoped_creation_succeeds_only_with_explicit_target_and_donor_names(monkeypatch):
    solver = make_solver()
    assert solver.step().committed
    original = solver.adapter.propose

    def restricted_propose(*args, **kwargs):
        with scoped_change_access((), subpools=("donor", "created", "empty"), allow_main=False):
            return original(*args, **kwargs)

    monkeypatch.setattr(solver.adapter, "propose", restricted_propose)
    assert solver.step().committed
    assert solver.solution_pool.subpool_refs("created") == solver.solution_pool.subpool_refs("donor")


@pytest.mark.parametrize("drift", ["absent-create", "recreate"])
def test_destination_drift_after_evaluation_rolls_back_plans_unit_rng_and_pool(drift, monkeypatch):
    solver = make_solver()
    assert solver.step().committed
    pool, adapter = solver.solution_pool, solver.adapter
    if drift == "recreate":
        pool.create_subpool("created")
    descriptor = pool.subpool_descriptor("created") if pool.has_subpool("created") else None
    before, manifest = copy.deepcopy(adapter.get_state()), pool.publication_ref()
    original = adapter.update

    def interfere(*args, **kwargs):
        original(*args, **kwargs)
        if pool.has_subpool("created"):
            pool.drop_subpool("created")
        pool.create_subpool("created")

    monkeypatch.setattr(adapter, "update", interfere)
    with pytest.raises(ValueError, match="identity|revision|uncommitted|committed"):
        solver.step()
    assert adapter.get_state() == before
    assert pool.publication_ref() == manifest
    assert not pool.has_subpool("empty")
    if descriptor is None:
        assert not pool.has_subpool("created")
    else:
        assert pool.subpool_descriptor("created") == descriptor
        assert pool.subpool_refs("created") == ()
    assert solver.evaluation_count == len(solver.problem.calls) == 3


def test_absent_target_appearing_between_callback_and_precheck_fails_before_evaluation(monkeypatch):
    solver = make_solver()
    assert solver.step().committed
    operation = solver.adapter.get_bound_change()
    ordinary = operation.change

    def appear(request, *, rng):
        result = ordinary(request, rng=rng)
        solver.solution_pool.create_subpool("created")
        return result

    monkeypatch.setattr(operation, "change", appear)
    before = copy.deepcopy(solver.adapter.get_state())
    with pytest.raises(ValueError, match="cutoff|uncommitted|target"):
        solver.step()
    assert solver.adapter.get_state() == before
    assert not solver.solution_pool.has_subpool("created")
    assert solver.evaluation_count == 1


def test_batch_creation_follows_budget_and_nonprefix_admission_not_unaccepted_sibling_edits():
    solver = make_solver("ga")
    assert solver.step().committed
    solver.register_controller(BudgetController(max_evaluations=solver.evaluation_count + 3))

    class OnlySecond:
        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), (1,))

    solver.set_evaluation_acceptance_policy(OnlySecond())
    assert solver.step().committed
    assert solver.solution_pool.has_subpool("right")
    assert not solver.solution_pool.has_subpool("left")
    assert solver.solution_pool.subpool_refs("right") == solver.solution_pool.subpool_refs("donor")
    assert solver.solution_pool.subpool_refs("empty") == ()
    assert len(solver._last_evaluated_event_batch.semantic_states) == 3
    assert solver.evaluation_count == len(solver.problem.calls) == 7


def test_zero_admission_discards_absent_and_empty_creation_plans():
    solver = make_solver("ga")
    assert solver.step().committed

    class Reject:
        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), ())

    solver.set_evaluation_acceptance_policy(Reject())
    assert not solver.step().committed
    assert all(not solver.solution_pool.has_subpool(name) for name in ("left", "right", "empty"))
    assert solver.evaluation_count == len(solver.problem.calls) == 8


def test_created_collections_survive_formal_restore_without_change_replay(tmp_path, monkeypatch):
    monkeypatch.setenv("NSGABLACK_CHECKPOINT_HMAC_KEY", "change-create-checkpoint")
    source = make_solver()
    assert source.step().committed and source.step().committed
    config = CheckpointResumeConfig(checkpoint_dir=str(tmp_path), save_on_finish=False, strict=True)
    writer = CheckpointResumePlugin(config=config)
    source.add_plugin(writer)
    checkpoint = writer.save_checkpoint(reason="change-created")
    assert checkpoint is not None
    state = copy.deepcopy(source.adapter.get_state())
    targets = {name: (source.solution_pool.subpool_refs(name), source.solution_pool.subpool_descriptor(name))
               for name in ("created", "empty", "donor")}
    restored = make_solver(setup=False)
    reader = CheckpointResumePlugin(config=config)
    restored.add_plugin(reader)

    def forbidden(*args, **kwargs):
        raise AssertionError("checkpoint must not reinitialize or replay change edits")

    with monkeypatch.context() as restore_only:
        restore_only.setattr(restored.representation_pipeline.initializer, "initialize", forbidden)
        restore_only.setattr(restored.adapter.get_bound_change(), "change", forbidden)
        assert reader.resume(str(checkpoint))
        restored.run(max_steps=0)
    assert restored.problem.calls == []
    assert restored.adapter.get_state() == state
    for name, (refs, descriptor) in targets.items():
        assert restored.solution_pool.subpool_refs(name) == refs
        assert restored.solution_pool.subpool_descriptor(name) == descriptor
    old_count = len(source.problem.calls)
    assert source.step().committed and restored.step().committed
    np.testing.assert_array_equal(restored.problem.calls, source.problem.calls[old_count:])
    assert restored.adapter._operator_rng.bit_generator.state == source.adapter._operator_rng.bit_generator.state
    for name, (refs, descriptor) in targets.items():
        assert restored.solution_pool.subpool_refs(name) == source.solution_pool.subpool_refs(name) == refs
        assert restored.solution_pool.subpool_descriptor(name) == source.solution_pool.subpool_descriptor(name) == descriptor
