"""Falsifiable BO semantics through the real Solver, Case and checkpoint paths."""
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
from blackbase.contracts import BatchDisposition
from blackbase.project import build_case, load_case_builder, run_case
from blackbase.resources import ResourceAllocator, ResourceContext, ResourceRequest
from nsgablack.adapters.bayesian_optimization import (
    BayesianOptimizationAdapter, BayesianOptimizationConfig, FixedRBFPosterior,
    FixedRBFConfig, LowerConfidenceBound)
from nsgablack.core.control_plane import BudgetController


PROJECT = Path(__file__).resolve().parents[1] / "examples" / "cases" / "algorithm_semantics"


@pytest.fixture
def grant():
    allocator = ResourceAllocator()
    lease = allocator.acquire(ResourceRequest(threads=1, workers=1), owner_id="bo_semantics", scope="optimization")
    try:
        yield ResourceContext.from_mapping(lease.resource_context(namespace="algorithm_semantics"))
    finally:
        allocator.release(lease)


def assemble(grant, output, **config):
    return build_case(load_case_builder(PROJECT, "synchronous_bo"), resource_context=grant,
        component_overrides={"config": {"output_dir": str(output), **config}})


class FixedOptimizer:
    """Fault fixture: explicit alternative optimizer proposes supplied rows."""
    component_state_mode = "stateless"
    def __init__(self, points):
        self.points = np.asarray(points, dtype=float)

    def describe(self):
        return {"type": "test_fixed_candidates/v1", "points": self.points.tolist()}

    def minimize(self, model, acquisition):
        return self.points.copy(), {"fixture": self.points.tolist()}


def replace_optimizer(solver, points):
    solver.adapter.optimizer = FixedOptimizer(points)


def dataset(solver):
    rows = solver.adapter.algorithm_unit.observations
    return [row["x"][0] for row in rows], [row["y"] for row in rows]


def test_exact_gp_lcb_and_normal_case_keep_acquisition_separate_from_truth(tmp_path, grant):
    solver = assemble(grant, tmp_path, max_steps=2, bias_weight=10.0)
    adapter = solver.adapter
    assert adapter.algorithm_unit is None
    assert adapter.get_state()["algorithm_unit"] is None
    run_case(solver)
    assert solver.resource_binding_audit["current"] is True
    assert solver.problem.calls == [0.0, 1.0, 0.5]
    assert solver.evaluation_count == 3
    assert dataset(solver) == ([0.0, 1.0, 0.5], [0.0625, 0.5625, 0.0625])
    grid = np.array([[0.25], [0.5], [0.75]])
    x = np.array([[0.0], [1.0]])
    kernel = lambda a, b: np.exp(-0.5 * (a[:, None, 0] - b[None, :, 0]) ** 2 / 0.25 ** 2)
    covariance = kernel(x, x) + 1e-8 * np.eye(2)
    cross = kernel(grid, x)
    mean = cross @ np.linalg.solve(covariance, [0.0625, 0.5625])
    std = np.sqrt(1 - np.sum(cross * np.linalg.solve(covariance, cross.T).T, axis=1))
    report = adapter.algorithm_unit.last_acquisition
    np.testing.assert_allclose(report["mean"], mean, atol=1e-12)
    np.testing.assert_allclose(report["std"], std, atol=1e-12)
    np.testing.assert_allclose(report["acquisition"], mean - 2 * std, atol=1e-12)
    assert report["selected_index"] == 1
    assert adapter.algorithm_unit.observations[-1]["y"] != float(solver.objectives[-1, 0])


def test_bo_r_repair_binds_final_version_and_keeps_duplicate_observations(tmp_path, grant):
    solver = assemble(grant, tmp_path)
    solver.setup()
    assert solver.step().committed
    replace_optimizer(solver, [[-0.1]])
    assert solver.step().committed
    assert solver.problem.calls == [0.0, 1.0, 0.0]
    x, y = dataset(solver)
    assert x == [0.0, 1.0, 0.0] and y == [0.0625, 0.5625, 0.0625]
    rows = solver.adapter.algorithm_unit.observations
    assert rows[0]["identity"] != rows[2]["identity"]
    event = solver.get_last_evaluation_event()
    from blackbase.types import CandidateBatch
    batch = CandidateBatch.from_dict(event.candidate_payload)
    assert batch.candidate_tokens[0] == rows[-1]["candidate_token"]
    assert batch.numeric_matrix[0, 0] == 0


def test_failed_problem_repair_does_not_evaluate_or_add_a_training_observation(tmp_path, grant, monkeypatch):
    from nsgablack.units.contracts import candidate_array
    solver = assemble(grant, tmp_path)
    solver.setup()
    solver.step()
    baseline = dataset(solver)
    events = len(solver.evaluation_evidence_journal.list_records())
    replace_optimizer(solver, [[-0.1]])
    original = solver.representation_pipeline.repair_batch
    def reject(candidates, *, contexts):
        if any(candidate_array(candidate)[0] < 0 for candidate in candidates):
            raise ValueError("BO-R rejected before evaluation")
        return original(candidates, contexts=contexts)
    monkeypatch.setattr(solver.representation_pipeline, "repair_batch", reject)
    with pytest.raises(ValueError, match="BO-R"):
        solver.step()
    assert dataset(solver) == baseline
    assert len(solver.problem.calls) == solver.evaluation_count == 2
    assert len(solver.evaluation_evidence_journal.list_records()) == events


@pytest.mark.parametrize("key", ["bo_owner", "bo_seed_index"])
def test_repair_cannot_erase_reserved_observation_binding_before_evaluation(tmp_path, grant, monkeypatch, key):
    from blackbase.types import UnknownState
    from nsgablack.units.contracts import candidate_array
    solver = assemble(grant, tmp_path)
    solver.setup()
    original = solver.representation_pipeline.repair_batch
    def erase(candidates, *, contexts):
        repaired = original(candidates, contexts=contexts)
        out = []
        for index, (before, after) in enumerate(zip(candidates, repaired, strict=True)):
            semantic = solver.semantic_candidate_state(before, candidate_index=index)
            metadata = dict(semantic.metadata)
            metadata.pop(key, None)
            out.append(UnknownState(candidate_array(after), metadata))
        return out
    monkeypatch.setattr(solver.representation_pipeline, "repair_batch", erase)
    with pytest.raises(ValueError, match=f"reserved algorithm metadata: {key}"):
        solver.step()
    assert solver.problem.calls == [] and solver.evaluation_count == 0
    assert solver.adapter.algorithm_unit is None


class RejectFirstInterior:
    policy_id = "test-reject-first-interior/v1"

    def select(self, candidates, feedback, context):
        count = feedback.candidate_count
        selected = ((1,) if count == 2 and candidates.numeric_matrix[0, 0] == 0.25 else tuple(range(count)))
        return BatchDisposition(count, selected, reason=self.policy_id)


def test_bo_a_full_observation_set_survives_partial_member_acceptance(tmp_path, grant):
    solver = assemble(grant, tmp_path)
    solver.set_evaluation_acceptance_policy(RejectFirstInterior())
    solver.setup()
    assert solver.step().committed
    replace_optimizer(solver, [[0.25], [0.75]])
    assert solver.step().committed
    assert solver.evaluation_count == 4
    assert dataset(solver) == ([0.0, 1.0, 0.25, 0.75], [0.0625, 0.5625, 0.0, 0.25])
    assert solver.adapter.algorithm_unit.accepted_values == [[0.75]]
    before = dataset(solver)
    solver.adapter.synchronize_observations(solver)
    assert dataset(solver) == before


def test_budget_cut_learns_only_rows_actually_evaluated(tmp_path, grant):
    solver = assemble(grant, tmp_path)
    solver.register_controller(BudgetController(max_evaluations=3))
    solver.setup()
    assert solver.step().committed
    replace_optimizer(solver, [[0.25], [0.75]])
    assert solver.step().committed
    assert solver.problem.calls == [0.0, 1.0, 0.25]
    assert dataset(solver) == ([0.0, 1.0, 0.25], [0.0625, 0.5625, 0.0])


def test_bo_f_update_failure_rolls_back_decisions_but_next_sync_learns_durable_event(tmp_path, grant, monkeypatch):
    solver = assemble(grant, tmp_path)
    solver.setup()
    assert solver.step().committed
    baseline = dataset(solver)
    revision = solver.adapter.algorithm_unit.model_revision
    authority = solver.get_population_authority_identity()
    original = solver.adapter.update

    def failing(*args):
        original(*args)
        raise RuntimeError("BO-F after fitting")

    monkeypatch.setattr(solver.adapter, "update", failing)
    with pytest.raises(RuntimeError, match="BO-F"):
        solver.step()
    assert dataset(solver) == baseline
    assert solver.adapter.algorithm_unit.model_revision == revision
    assert solver.get_population_authority_identity() == authority
    assert solver.problem.calls == [0.0, 1.0, 0.5]
    failed = solver.evaluation_evidence_journal.list_records(outcomes=("execution_failed",))
    assert len(failed) == 1
    monkeypatch.setattr(solver.adapter, "update", original)
    solver.adapter.synchronize_observations(solver)
    assert dataset(solver) == ([0.0, 1.0, 0.5], [0.0625, 0.5625, 0.0625])
    solver.adapter.synchronize_observations(solver)
    assert len(solver.adapter.algorithm_unit.observations) == 3
    assert len(solver.problem.calls) == 3


def test_portable_dataset_rejects_tampering_and_model_interpretation_change(tmp_path, grant):
    from copy import deepcopy
    solver = assemble(grant, tmp_path)
    solver.setup()
    solver.step()
    state = solver.adapter.get_state()
    target = BayesianOptimizationAdapter()
    target.set_state(state)
    np.testing.assert_allclose(target.model.posterior([[0.5]])[0], solver.adapter.model.posterior([[0.5]])[0])
    bad = deepcopy(state)
    # Portable Snapshot contents retain the original store scope and digest.
    from nsgablack.representation.structure_builders import decode_unit_value, encode_unit_value
    evidence = decode_unit_value(bad["algorithm_unit"]["payload"]["evidence"])
    evidence[0]["snapshot_data"]["tampered"] = True
    bad["algorithm_unit"]["payload"]["evidence"] = encode_unit_value(evidence)
    with pytest.raises(ValueError, match="digest"):
        BayesianOptimizationAdapter().set_state(bad)
    with pytest.raises(ValueError, match="interpretation"):
        BayesianOptimizationAdapter(model=FixedRBFPosterior(FixedRBFConfig(length_scale=0.5))).set_state(state)


def test_two_same_named_bo_instances_keep_observations_in_their_router_owner_paths(tmp_path, grant):
    from nsgablack.adapters import StrategyRouterAdapter, StrategySpec
    first = BayesianOptimizationAdapter()
    second = BayesianOptimizationAdapter(BayesianOptimizationConfig(initial_points=((0.2,), (0.8,))))
    solver = assemble(grant, tmp_path)
    solver.set_adapter(StrategyRouterAdapter(strategies=[StrategySpec(first, "first"),
        StrategySpec(second, "second")], total_batch_size=4, adapt_weights=False))
    solver.setup()
    assert solver.step().committed
    assert first.name == second.name
    assert first.algorithm_unit.owner_path != second.algorithm_unit.owner_path
    assert [row["x"] for row in first.algorithm_unit.observations] == [[0.0], [1.0]]
    assert [row["x"] for row in second.algorithm_unit.observations] == [[0.2], [0.8]]
    assert {tuple(row["identity"]) for row in first.algorithm_unit.observations}.isdisjoint(
        {tuple(row["identity"]) for row in second.algorithm_unit.observations})


def test_stateful_or_undeclared_acquisition_components_are_explicitly_rejected():
    class StatefulOptimizer(FixedOptimizer):
        component_state_mode = "stateful"
    with pytest.raises(TypeError, match="stateless"):
        BayesianOptimizationAdapter(optimizer=StatefulOptimizer([[0.5]]))


def test_individual_only_approximate_provider_is_not_misclassified_as_problem_truth(tmp_path, grant):
    class ApproximateIndividual:
        name = "approximate_individual_only"
        semantic_mode = "approximate"
        priority = 10
        def can_handle_individual(self, solver, x, context):
            return True
        def evaluate_individual(self, solver, x, context, individual_id=None):
            return [-100.0], 0.0
    solver = assemble(grant, tmp_path)
    solver.register_evaluation_provider(ApproximateIndividual())
    solver.setup()
    with pytest.raises(ValueError, match="EvaluationProvider"):
        solver.step()
    assert solver.problem.calls == [] and solver.evaluation_count == 0
    assert solver.adapter.algorithm_unit is None


def test_member_reference_cannot_be_rebound_to_different_numeric_values(tmp_path, grant):
    solver = assemble(grant, tmp_path)
    solver.setup()
    solver.step()
    solver.adapter.algorithm_unit.accepted_values[0] = [0.9]
    with pytest.raises(ValueError, match="exact Pool versions"):
        solver.adapter.get_solution_pool_roots()


def test_pool_retention_keeps_exact_active_members_but_training_uses_portable_events(tmp_path, grant):
    from nsgablack.core import PoolRetentionPolicy
    solver = assemble(grant, tmp_path, max_steps=4)
    solver.set_solution_pool_retention(PoolRetentionPolicy(idle_steps=1, retained_publications=1))
    run_case(solver)
    refs = solver.adapter.get_solution_pool_roots(solver)
    assert len(refs) == 1
    assert solver.solution_pool.read(refs).numeric_matrix.tolist() == solver.adapter.algorithm_unit.accepted_values
    assert len(solver.adapter.algorithm_unit.observations) == solver.evaluation_count == 5


def test_failed_unconsumed_event_is_portable_without_fitting_during_checkpoint_save(tmp_path, grant, monkeypatch):
    output = tmp_path / "failed_checkpoint"
    source = assemble(grant, output, max_steps=1)
    source.setup()
    source.step()
    original = source.adapter.update
    def failure(*args):
        original(*args)
        raise RuntimeError("failed pending dataset")
    monkeypatch.setattr(source.adapter, "update", failure)
    with pytest.raises(RuntimeError, match="pending dataset"):
        source.step()
    monkeypatch.setattr(source.adapter, "update", original)
    before = dataset(source)
    revision = source.adapter.algorithm_unit.model_revision
    state = source.adapter.get_state()
    assert len(state["pending_dataset_evidence"]) == 1
    assert dataset(source) == before and source.adapter.algorithm_unit.model_revision == revision
    path = source.get_plugin("checkpoint_resume").save_checkpoint(reason="failed-event-portable-dataset")
    target = assemble(grant, output, max_steps=1)
    assert target.get_plugin("checkpoint_resume").resume(str(path))
    assert target.evaluation_evidence_journal.list_records() == ()
    run_case(target)
    rows = target.adapter.algorithm_unit.observations
    assert [row["x"][0] for row in rows[:3]] == [0.0, 1.0, 0.5]
    assert len({tuple(row["identity"]) for row in rows}) == len(rows) == 4
    assert len(target.problem.calls) == 1 and target.evaluation_count == 4


def test_initial_failed_attempt_keeps_unit_absent_and_exports_pending_evidence(tmp_path, grant, monkeypatch):
    solver = assemble(grant, tmp_path)
    solver.setup()
    original = solver.adapter.update
    def failure(*args):
        original(*args)
        raise RuntimeError("initial BO failure")
    monkeypatch.setattr(solver.adapter, "update", failure)
    with pytest.raises(RuntimeError, match="initial BO failure"):
        solver.step()
    assert solver.adapter.algorithm_unit is None and solver.adapter.model.alpha is None
    state = solver.adapter.get_state()
    assert state["algorithm_unit"] is None and len(state["pending_dataset_evidence"]) == 1
    assert solver.adapter.algorithm_unit is None
    monkeypatch.setattr(solver.adapter, "update", original)
    solver.step()
    assert solver.problem.calls == [0.0, 1.0, 0.5]
    assert dataset(solver) == ([0.0, 1.0, 0.5], [0.0625, 0.5625, 0.0625])


def test_bo_c_real_saved_checkpoint_restores_in_a_fresh_python_process(tmp_path, grant):
    output = tmp_path / "restart"
    source = assemble(grant, output, max_steps=4)
    run_case(source)
    checkpoint, = (output / "checkpoints").glob("*_g000000_*.pkl")
    script = '''
import json, sys
from pathlib import Path
from blackbase.project import build_case, load_case_builder, run_case
from blackbase.resources import ResourceAllocator, ResourceContext, ResourceRequest
allocator=ResourceAllocator()
lease=allocator.acquire(ResourceRequest(threads=1,workers=1),owner_id="bo_restart",scope="optimization")
try:
    grant=ResourceContext.from_mapping(lease.resource_context(namespace="algorithm_semantics"))
    solver=build_case(load_case_builder(Path(sys.argv[1]),"synchronous_bo"),resource_context=grant,
        component_overrides={"config":{"output_dir":sys.argv[2],"max_steps":4}})
    assert solver.get_plugin("checkpoint_resume").resume(sys.argv[3])
    run_case(solver)
    unit=solver.adapter.algorithm_unit
    Path(sys.argv[4]).write_text(json.dumps({"x":[r["x"] for r in unit.observations],
        "y":[r["y"] for r in unit.observations],"identities":[r["identity"] for r in unit.observations],
        "calls":solver.problem.calls,"evaluations":solver.evaluation_count}),encoding="utf-8")
finally:
    allocator.release(lease)
'''
    result_path = tmp_path / "fresh_process.json"
    completed = subprocess.run([sys.executable, "-c", script, str(PROJECT), str(output),
        str(checkpoint), str(result_path)], capture_output=True, text=True, cwd=PROJECT.parents[2], timeout=90)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads(result_path.read_text(encoding="utf-8"))
    rows = source.adapter.algorithm_unit.observations
    assert result["x"] == [row["x"] for row in rows]
    assert result["y"] == [row["y"] for row in rows]
    assert len({tuple(identity) for identity in result["identities"]}) == len(rows)
    assert len(result["calls"]) == source.evaluation_count - 2
    assert result["evaluations"] == source.evaluation_count
