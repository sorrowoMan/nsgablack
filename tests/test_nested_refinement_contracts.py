"""Adversarial boundaries for recursively consumed projection views."""
import copy

import numpy as np
import pytest

from blackbase.contracts import BatchDisposition
from blackbase.types import CandidateBatch
from nsgablack.adapters import (
    MOEADAdapter, MultiStrategyConfig, PoolTaskSpec, RoleSpec,
    StrategyRouterAdapter, VNSAdapter, subpools,
)
from nsgablack.adapters.subpools import adapter_path
from nsgablack.core import BlackBoxProblem, ComposableSolver
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.core.state.pool_views import ObjectiveProjection
from nsgablack.plugins import CheckpointResumePlugin
from nsgablack.representation import RepresentationPipeline
from nsgablack.utils.runtime_contracts import inspect_runtime_contracts


class RouteProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["min", "min"], bounds=[(-20., 20.)])

    def evaluate(self, candidate):
        x = float(candidate[0])
        return [x * x, (x - 10.) ** 2]


class RouteOperators:
    context_requires = ("vns_k",)

    def initialize(self, problem, context):
        return np.array([8.])

    def mutate(self, candidate, context):
        return candidate - 1.


def refinement_phase(context):
    tasks = context["pool_tasks"]
    if tasks["coarse:0"]["status"] != "done":
        return "coarse"
    if not all(state["status"] == "done" for name, state in tasks.items()
               if name.startswith("fine:")):
        return "fine"
    return "return"


def make_solver(*, setup=True, fine_steps=2):
    producer = MOEADAdapter(name="directions", population_size=4, batch_size=2,
                           neighborhood_size=2, decomposition="weighted_sum")
    coarse = VNSAdapter(name="coarse", batch_size=1, restart_on_stagnation=False)
    def ready_phase(context):
        return refinement_phase(context) if producer.pool_views_ready else "bootstrap"
    router = StrategyRouterAdapter(name="nested", roles=[
        RoleSpec("producer", producer,
                 pool_task=PoolTaskSpec("fine_results", mode="compete", phases=("return",))),
        RoleSpec("coarse", coarse, pool_task=PoolTaskSpec(
            subpools.all(producer), steps=2, output="coarse_results", shuffle=False)),
        RoleSpec("fine", lambda i: VNSAdapter(name=f"fine_{i}", batch_size=2,
            restart_on_stagnation=False), n_units=2,
            pool_task=PoolTaskSpec(subpools.all(coarse), steps=fine_steps,
                                  output="fine_results", shuffle=False)),
    ], config=MultiStrategyConfig(total_batch_size=8, adapt_weights=False,
        phase_policy=ready_phase, phase_roles={
            "bootstrap": ["producer"], "coarse": ["coarse"], "fine": ["fine"], "return": ["producer"]}))
    solver = ComposableSolver(RouteProblem(), adapter=router,
        representation_pipeline=RepresentationPipeline(
            initializer=RouteOperators(), mutator=RouteOperators()))
    solver.set_random_seed(19)
    if setup:
        solver.setup()
        assert solver.step().committed
    return solver, router, coarse


def workers(router, role):
    return [unit.adapter for unit in router.units if unit.role == role]


def finish_coarse(solver, router):
    for _ in range(12):
        if workers(router, "coarse")[0].task_status["status"] == "done":
            return
        assert solver.step().committed
    pytest.fail("coarse refinement did not finish")


def pool_task_issues(solver):
    return [message for code, message in inspect_runtime_contracts(solver)
            if code == "solution-pool-task-contract-invalid"]


def test_bare_vns_is_not_a_projection_publisher():
    bare = VNSAdapter(name="bare")
    consumer = VNSAdapter(name="consumer")
    router = StrategyRouterAdapter(roles=[RoleSpec("bare", bare),
        RoleSpec("consumer", consumer, pool_task=PoolTaskSpec(
            subpools.all(bare), output="results"))])
    solver = ComposableSolver(RouteProblem(), adapter=router)
    assert any("no projection pool task with output" in message for message in pool_task_issues(solver))
    with pytest.raises(ValueError, match="no projection pool task with output"):
        workers(router, "consumer")[0].validate_pool_task(router)


def test_projected_task_dependency_cycle_is_rejected():
    a, b = VNSAdapter(name="a"), VNSAdapter(name="b")
    router = StrategyRouterAdapter(roles=[
        RoleSpec("a", a, pool_task=PoolTaskSpec(subpools.all(b), output="a_results")),
        RoleSpec("b", b, pool_task=PoolTaskSpec(subpools.all(a), output="b_results")),
    ])
    solver = ComposableSolver(RouteProblem(), adapter=router)
    assert len([message for message in pool_task_issues(solver) if "cycle" in message]) == 2
    with pytest.raises(ValueError, match="cycle"):
        workers(router, "a")[0].validate_pool_task(router)


def test_runtime_contract_requires_explicit_refinement_result_delivery():
    solver, _, coarse = make_solver(setup=False)
    coarse.get_pool_refinement_results = None
    assert any("get_pool_refinement_results" in message for message in pool_task_issues(solver))


def test_second_layer_zero_and_partial_admission_preserve_jobs_and_cursor():
    solver, router, _ = make_solver()
    finish_coarse(solver, router)
    fine = workers(router, "fine")

    class Acceptance:
        policy_id = "nested_refinement_contract"
        indices = ()

        def select(self, candidates, feedback, context):
            return BatchDisposition(len(candidates.semantic_states), self.indices)

    policy = Acceptance()
    solver.set_evaluation_acceptance_policy(policy)
    assert not solver.step().committed
    jobs = [copy.deepcopy(worker._local["jobs"]) for worker in fine]
    for worker in fine:
        assert solver.solution_pool.projection_subpools(adapter_path(router, worker.inner)) == ()
        assert worker.inner.current_score is None
        assert worker._local["steps"] == 0
        assert solver.solution_pool.input_remaining(worker._local["input"]) == 1

    policy.indices = (0,)
    assert solver.step().committed
    assert [worker._local["steps"] for worker in fine] == [1, 0]
    assert fine[1].inner.current_score is None
    assert solver.solution_pool.input_remaining(fine[1]._local["input"]) == 1
    solver.set_evaluation_acceptance_policy(None)
    assert solver.step().committed
    assert [worker._local["jobs"] for worker in fine] == jobs
    assert fine[1].inner._projection_frame == jobs[1][0]["projection"]
    assert len(solver.solution_pool.projection_subpools(adapter_path(router, fine[0].inner))) == 1


def test_second_layer_failure_rolls_back_already_staged_sibling_output(monkeypatch):
    solver, router, _ = make_solver()
    finish_coarse(solver, router)
    assert solver.step().committed  # Both second-layer baselines are now accepted.
    fine = workers(router, "fine")
    pool = solver.solution_pool
    before_pool = copy.deepcopy(pool.get_state()["subpool_metadata"])
    before_task = copy.deepcopy(fine[0]._local)
    before_x = fine[0].inner.current_x.copy()
    staged = []
    creator = list(adapter_path(router, fine[0].inner))

    def fail_after_sibling(*args, **kwargs):
        staged.extend(name for name, metadata in pool._subpool_metadata.items()
                      if metadata.get("created_by") == creator)
        assert staged
        assert pool.projection_subpools(creator) == ()
        raise RuntimeError("second fine worker failed")

    with monkeypatch.context() as patch:
        patch.setattr(fine[1].inner, "update", fail_after_sibling)
        with pytest.raises(RuntimeError, match="second fine worker failed"):
            solver.step()
    assert pool.get_state()["subpool_metadata"] == before_pool
    assert fine[0]._local == before_task
    np.testing.assert_array_equal(fine[0].inner.current_x, before_x)
    assert all(not pool.has_subpool(name) for name in staged)
    assert solver.step().committed
    assert len(pool.projection_subpools(creator)) == 1


def test_queued_child_survives_parent_republication_drop_and_checkpoint():
    source, first, coarse = make_solver(fine_steps=3)
    finish_coarse(source, first)
    assert source.step().committed
    original_jobs = [copy.deepcopy(worker._local["jobs"]) for worker in workers(first, "fine")]
    pool = source.solution_pool
    parent_names = pool.projection_subpools(adapter_path(first, coarse))
    for name in parent_names:
        metadata = pool.subpool_metadata(name)
        descriptor = pool.subpool_descriptor(name)
        pool.publish_projection_subpool(name, pool.subpool_refs(name),
            created_by=metadata["created_by"], slot=metadata["slot"],
            projection=ObjectiveProjection("weighted_sum", (.123, .877)),
            parent=metadata["parent"])
        assert pool.subpool_descriptor(name)["revision"] == descriptor["revision"] + 1
        pool.drop_subpool(name)

    target, second, _ = make_solver(setup=False, fine_steps=3)
    writer, reader = CheckpointResumePlugin(), CheckpointResumePlugin()
    writer.attach(source)
    reader.attach(target)
    payload = writer._build_payload(solver=source, reason="nested-refinement")
    target.queue_restore_envelope(lambda: reader._restore_payload(solver=target, payload=payload))
    target.setup()
    target._apply_pending_restore_envelopes()
    assert [worker._local["jobs"] for worker in workers(second, "fine")] == original_jobs
    assert all(not target.solution_pool.has_subpool(name) for name in parent_names)
    for _ in range(8):
        if all(worker.task_status["status"] == "done" for worker in workers(second, "fine")):
            break
        assert source.step().committed and target.step().committed
    assert all(worker.task_status["status"] == "done" for worker in workers(second, "fine"))
    for restored, original, jobs in zip(workers(second, "fine"), workers(first, "fine"), original_jobs):
        np.testing.assert_array_equal(restored.inner.current_x, original.inner.current_x)
        assert restored.inner.current_score == original.inner.current_score
        for job in jobs:
            names = target.solution_pool.children_subpools(job["source_descriptor"])
            assert len(names) == 1
            metadata = target.solution_pool.subpool_metadata(names[0])
            assert metadata["parent"] == job["source_descriptor"]
            assert metadata["projection"] == job["projection"]
            raw, _ = target.solution_pool.read_raw_feedback(target.solution_pool.subpool_refs(names[0]))
            assert raw.shape == (1, 2)


def test_single_objective_feedback_cannot_be_projected_twice():
    projection = ObjectiveProjection("weighted_sum", (.5,))
    feedback = OptimizationFeedbackBatch.from_arrays([[8.]], [0.])
    first = projection.apply(feedback)
    assert first.objectives[0, 0] == 4.
    with pytest.raises(ValueError, match="once"):
        projection.apply(first)
    np.testing.assert_array_equal(first.raw_objectives, [[8.]])


@pytest.mark.parametrize("corruption", ["source", "pool", "cycle", "projection"])
def test_second_layer_checkpoint_rejects_invalid_frozen_job(corruption):
    solver, router, _ = make_solver()
    finish_coarse(solver, router)
    assert solver.step().committed
    worker = workers(router, "fine")[0]
    before = copy.deepcopy(worker._local)
    invalid = worker.get_state()
    job = invalid["pool_task"]["jobs"][0]
    descriptor = job["source_descriptor"]
    if corruption == "source":
        job["source_view"] = "another_view"
    elif corruption == "pool":
        descriptor["pool_id"] = "another_pool"
        for ancestor in descriptor["ancestors"]:
            ancestor["pool_id"] = "another_pool"
    elif corruption == "cycle":
        descriptor["ancestors"].append({key: value for key, value in descriptor.items()
                                        if key != "ancestors"})
    else:
        job["projection"]["weights"] = [0., 0.]
    with pytest.raises(ValueError):
        worker.set_state(invalid)
    assert worker._local == before


@pytest.mark.parametrize("mismatch", ["projection", "ref"])
def test_restored_job_must_match_retained_queue_before_evaluation(mismatch, monkeypatch):
    solver, router, _ = make_solver(fine_steps=3)
    finish_coarse(solver, router)
    assert solver.step().committed
    fine = workers(router, "fine")
    worker = fine[0]
    valid_state = worker.get_state()
    restored_state = copy.deepcopy(valid_state)
    job = restored_state["pool_task"]["jobs"][0]
    if mismatch == "projection":
        job["projection"] = ObjectiveProjection("weighted_sum", (.123, .877)).as_dict()
    else:
        job["ref"] = next(copy.deepcopy(other["ref"])
            for sibling in fine for other in sibling._local["jobs"] if other["ref"] != job["ref"])
    # Each field remains structurally valid; the independent retained queue
    # detects that the restored execution payload no longer describes its input.
    worker.set_state(restored_state)
    before = copy.deepcopy(worker._local)
    before_pool = copy.deepcopy(solver.solution_pool.get_state()["subpool_metadata"])
    evaluated = []
    evaluate = solver.problem.evaluate

    def record_evaluation(candidate):
        evaluated.append(candidate.copy())
        return evaluate(candidate)

    monkeypatch.setattr(solver.problem, "evaluate", record_evaluation)
    with pytest.raises(ValueError, match="frozen input queue"):
        solver.step()
    assert evaluated == []
    assert worker._local == before
    assert solver.solution_pool.get_state()["subpool_metadata"] == before_pool
    worker.set_state(valid_state)
    assert solver.step().committed
    assert evaluated


def test_selected_result_keeps_exact_version_after_same_token_is_republished_and_restored():
    source, first, _ = make_solver(fine_steps=3)
    finish_coarse(source, first)
    assert source.step().committed
    original = workers(first, "fine")[0].inner
    selected = original.get_pool_refinement_results(source)
    assert selected == original.get_solution_pool_roots(source)
    selected_x = source.solution_pool.read(selected).numeric_matrix.copy()
    newer_x = selected_x[0] + 100.
    newer = source.solution_pool.put(CandidateBatch.from_candidates(
        [newer_x], candidate_tokens=(selected[0].candidate_token,)), stage="accepted",
        feedback=OptimizationFeedbackBatch.from_arrays([source.problem.evaluate(newer_x)], [0.]))
    assert newer != selected
    assert source.solution_pool.refs_for_tokens((selected[0].candidate_token,))[-1:] == newer
    assert original.get_pool_refinement_results(source) == selected
    assert original.get_solution_pool_roots(source) == selected

    target, second, _ = make_solver(setup=False, fine_steps=3)
    writer, reader = CheckpointResumePlugin(), CheckpointResumePlugin()
    writer.attach(source)
    reader.attach(target)
    payload = writer._build_payload(solver=source, reason="selected-version")
    target.queue_restore_envelope(lambda: reader._restore_payload(solver=target, payload=payload))
    target.setup()
    target._apply_pending_restore_envelopes()
    restored = workers(second, "fine")[0].inner
    assert restored.get_pool_refinement_results(target) == selected
    assert restored.get_solution_pool_roots(target) == selected
    np.testing.assert_array_equal(target.solution_pool.read(selected).numeric_matrix, selected_x)


def test_projected_checkpoint_without_selected_version_requires_explicit_migration():
    solver, router, _ = make_solver()
    finish_coarse(solver, router)
    assert solver.step().committed
    adapter = workers(router, "fine")[0].inner
    before = adapter.get_pool_refinement_results(solver)
    state = adapter.get_state()
    del state["current_pool_ref"]
    with pytest.raises(ValueError, match="explicit migration"):
        adapter.set_state(state)
    assert adapter.get_pool_refinement_results(solver) == before


@pytest.mark.parametrize("mismatch", ["pool", "candidate"])
def test_restored_selected_reference_must_match_scope_and_current_candidate(mismatch):
    solver, router, _ = make_solver()
    finish_coarse(solver, router)
    assert solver.step().committed
    adapter = workers(router, "fine")[0].inner
    original = adapter.get_pool_refinement_results(solver)[0]
    state = adapter.get_state()
    if mismatch == "pool":
        state["current_pool_ref"]["pool_id"] = "unrelated_pool"
    else:
        changed = CandidateBatch.from_candidates([adapter.current_x + 100.],
                                                candidate_tokens=(original.candidate_token,))
        state["current_pool_ref"] = solver.solution_pool.put(changed, stage="accepted")[0].as_dict()
    adapter.set_state(state)
    with pytest.raises(ValueError, match="another pool|differs from its current candidate"):
        adapter.get_pool_refinement_results(solver)
