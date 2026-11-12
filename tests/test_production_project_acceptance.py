"""Real BOM/supply through the canonical builder, including interrupted search.

Search is deliberately small; these checks certify handoff/recovery, not quality
or convergence. Full Project execution and integer export use the quality runner.
"""
import copy
import json
import secrets
from pathlib import Path

import numpy as np
import pytest

from blackbase.project import build_case, load_case_builder
from blackbase.project.runtime import ProjectL0Runtime, ProjectRuntimeConfig
from blackbase.resources import CancellationRequested, ResourceOffer, ResourcePolicy, ResourceRequest
from blackbase.resources import CancellationRef, CancellationToken
from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin
from nsgablack.plugins.base import Plugin


PROJECT = Path(__file__).resolve().parents[1] / "examples/cases/production_scheduling"


@pytest.fixture
def production(tmp_path):
    runtime = ProjectL0Runtime(ProjectRuntimeConfig(
        offer=ResourceOffer(threads=1, gpus=0),
        policy=ResourcePolicy(max_workers=1, max_threads=1),
        default_request=ResourceRequest(threads=1, workers=1),
        namespace="production-acceptance", lease_backend="sqlite",
        lease_path="lease.sqlite", lease_ttl_seconds=120,
        lease_heartbeat_seconds=10, budgets={"evaluations": 256},
    ), project_root=tmp_path)
    lease = runtime.acquire_case("production_scheduling", stage_name="acceptance")
    context = runtime.resource_context(lease, case_name="production_scheduling")
    solvers = []

    def build(limit=64, extra=()):
        argv = ["--machines", "22", "--materials", "157", "--days", "31",
                "--solver", "multi-agent", "--cooperation", "directional",
                "--pop-size", "8", "--moead-pop-size", "4", "--moead-neighborhood", "2",
                "--quality-cycles", "1", "--explore-steps", "1",
                "--refine-directions", "2", "--refine-steps", "2", "--vns-batch-size", "2",
                "--max-evaluations", str(limit), "--generations", "16", "--seed", "42",
                "--parallel-backend", "thread", "--parallel-workers", "1",
                "--no-export", "--no-run-logs", *extra]
        solver = build_case(load_case_builder(PROJECT, "production_scheduling"),
                            resource_context=context, component_overrides={"argv": argv})
        assert solver.resource_binding_audit["current"]
        assert solver.problem.dimension == 22 * 31
        assert solver.problem.data.supply_matrix.shape == (157, 31)
        assert solver.problem.data.bom_matrix[:, 156].any()
        assert solver.problem.data.supply_matrix[156].sum() > 0
        solver.setup()
        solvers.append(solver)
        return solver

    try:
        yield build, runtime, tmp_path
    finally:
        for solver in solvers:
            solver.teardown()
        runtime.release(lease)
        runtime.close()


def finish(solver):
    while not solver.adapter.cursor.completed:
        assert solver.step().committed


def population(solver):
    # The owner is the original MOEA/D, behind its existing PoolTask wrapper.
    from tests.test_search_plan_pool_tasks import task_wrappers
    return task_wrappers(solver.adapter)["moead"].inner


def test_real_data_checkpoint_preserves_frozen_refinement_and_final_population(production, monkeypatch):
    build, _, folder = production
    source = build()
    assert source.step().committed  # MOEA/D members and direction views.
    assert source.step().committed  # Frozen VNS starting-point evaluation.
    assert source.step().committed  # Consume the pipeline mutator's own RNG before saving.
    key_env = "NSGABLACK_PRODUCTION_ACCEPTANCE_HMAC_KEY"
    monkeypatch.setenv(key_env, secrets.token_hex(32))
    config = CheckpointResumeConfig(checkpoint_dir=str(folder / "checkpoints"),
        strict=True, hmac_env_var=key_env, trusted_roots=(str(folder),), save_on_finish=False)
    writer = CheckpointResumePlugin(config=copy.deepcopy(config))
    writer.attach(source)
    checkpoint = writer.save_checkpoint(reason="real-production-refinement")
    assert checkpoint.is_file()
    frozen_refs = source.solution_pool.select()
    prefix_evaluations = source.evaluation_count
    finish(source)
    expected = population(source)
    expected_x, expected_f = expected.pop_X.copy(), expected.pop_F.copy()
    target = build()
    reader = CheckpointResumePlugin(config=copy.deepcopy(config))
    reader.attach(target)
    assert reader.resume(str(checkpoint))
    # Public resume queues a restore envelope until normal post-setup restore;
    # ordinary init hooks must already observe the restored prefix.
    observed = []

    class ObserveRestore(Plugin):
        def on_solver_init(self, solver):
            assert solver.evaluation_count == prefix_evaluations
            assert solver.solution_pool.select() == frozen_refs
            observed.append(True)

    target.add_plugin(ObserveRestore(name="acceptance_restore_observer"))
    target.run()
    assert observed == [True]
    assert target.adapter.cursor.completed
    actual = population(target)
    np.testing.assert_array_equal(actual.pop_X, expected_x)
    np.testing.assert_array_equal(actual.pop_F, expected_f)
    # The restored prefix retains exact references. New suffix proposals are
    # fresh publications, so their random record IDs need not match another
    # continuation; each must resolve to its own exact candidate and feedback.
    refs = actual.get_population_solution_refs(target)
    np.testing.assert_array_equal(target.solution_pool.read(refs).numeric_matrix, actual.pop_X)
    raw, _ = target.solution_pool.read_raw_feedback(refs)
    assert target.evaluation_count == source.evaluation_count
    # Production Bias changes the selection view. Verify raw evidence against
    # Problem, and selection feedback against the uninterrupted continuation.
    for candidate, row in zip(actual.pop_X, raw, strict=True):
        np.testing.assert_array_equal(row, target.problem.evaluate(candidate))
    (folder / "evidence.json").write_text(json.dumps({"checkpoint": "passed",
        "dimension": source.problem.dimension, "evaluations": source.evaluation_count,
        "committed_steps": source.run_progress_steps, "population_equal": True,
        "historical_refs_preserved": True, "final_member_refs_verified": True,
        "signed_checkpoint_file": str(checkpoint)}), encoding="utf-8")


def test_real_data_cancel_after_update_rolls_back_but_keeps_budget(production, monkeypatch):
    build, runtime, folder = production
    solver = build()
    assert solver.step().committed
    assert solver.step().committed
    before = copy.deepcopy(solver.adapter.get_state())
    pipeline_before = copy.deepcopy(solver.representation_pipeline.get_state())
    authority = solver.get_population_authority_identity()
    accepted = solver.solution_pool.select(stage="accepted")
    steps, evaluations = solver.run_progress_steps, solver.evaluation_count
    consumed = runtime.budget_authority.status("evaluations").committed
    original = solver.adapter.update

    def cancel_after_update(*args, **kwargs):
        original(*args, **kwargs)
        raise CancellationRequested("production acceptance: cancel after actual update")

    with monkeypatch.context() as patch:
        patch.setattr(solver.adapter, "update", cancel_after_update)
        with pytest.raises(CancellationRequested, match="after actual update"):
            solver.step()
    np.testing.assert_equal(solver.adapter.get_state(), before)
    np.testing.assert_equal(solver.representation_pipeline.get_state(), pipeline_before)
    assert solver.get_population_authority_identity() == authority
    assert solver.solution_pool.select(stage="accepted") == accepted
    assert solver.run_progress_steps == steps
    charged = solver.evaluation_count - evaluations
    assert charged == 2
    status = runtime.budget_authority.status("evaluations")
    assert status.committed == consumed + charged and status.reserved == 0
    finish(solver)
    (folder / "evidence.json").write_text(json.dumps({"cancel_rollback": "passed",
        "failed_attempt_evaluations_retained": charged, "resumed_to_plan_completion": True}),
        encoding="utf-8")


def test_real_data_evaluation_limit_stops_without_a_ghost_step(production):
    build, runtime, folder = production
    solver = build(limit=5)
    result = solver.run()
    assert solver.evaluation_count == 5
    assert result["termination_reason"] == "evaluation_budget_exhausted"
    assert solver.run_progress_steps == 2
    assert not solver.adapter.cursor.completed
    status = runtime.budget_authority.status("evaluations")
    assert status.committed == 5 and status.reserved == 0
    (folder / "evidence.json").write_text(json.dumps({"budget": "passed",
        "evaluations": 5, "committed_steps": solver.run_progress_steps,
        "termination_reason": result["termination_reason"], "plan_complete": False}), encoding="utf-8")


def test_explicit_missing_input_never_silently_becomes_random_data(production):
    build, _, folder = production
    with pytest.raises(FileNotFoundError):
        build(extra=("--bom", str(folder / "missing-bom.csv")))


def test_real_data_cancellation_token_stops_an_inflight_evaluation_batch(production, monkeypatch):
    build, runtime, folder = production
    solver = build()
    token = CancellationToken(CancellationRef(backend="memory"))

    class Control:
        def checkpoint(self):
            token.checkpoint()

    solver.set_case_runtime(Control())
    original = solver.problem.evaluate
    calls = []

    def evaluate(candidate):
        calls.append(candidate)
        if len(calls) == 3:
            token.cancel("real production third-call cancellation")
        return original(candidate)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(solver.problem, "evaluate", evaluate)
            with pytest.raises(CancellationRequested, match="third-call"):
                solver.step()
        assert len(calls) == solver.evaluation_count == 3
        assert solver.run_progress_steps == 0
        assert not solver.solution_pool.select(stage="accepted")
        status = runtime.budget_authority.status("evaluations")
        assert status.committed == 3 and status.reserved == 0
        (folder / "evidence.json").write_text(json.dumps({"inflight_cancel": "passed",
            "completed_evaluations": 3, "committed_steps": 0,
            "outstanding_reservations": 0}), encoding="utf-8")
    finally:
        solver.set_case_runtime(None)
        token.retire()
