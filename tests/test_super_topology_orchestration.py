"""End-to-end proof for the complete Project/Case nesting topology."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from blackbase.project import execute_project
from blackbase.types import SolverResult, TrainerResult
from blackbase.wire import thaw_wire_value

from examples.cases.super_topology_orchestration.cases.outer_search.reporting.audit import evaluate_invariants


EXAMPLE_ROOT = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "cases"
    / "super_topology_orchestration"
)


@pytest.fixture(scope="module")
def topology_result(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("super_topology")
    project_root = tmp_path / "super_topology_orchestration"
    shutil.copytree(
        EXAMPLE_ROOT,
        project_root,
        ignore=shutil.ignore_patterns(".blackbase", "__pycache__", "*.pyc"),
    )

    return execute_project(
        project_root,
        run_id="super-topology-e2e",
        record=False,
    )


def test_super_topology_executes_with_authoritative_lineage_and_settlement(
    topology_result,
) -> None:
    from mlblack.core import LearningProblem, ModelRepresentation
    from mlblack.integrations import LearningSolver

    from examples.cases.super_topology_orchestration.cases.baseline_trainer.build_solver import (
        build_solver as build_baseline_trainer,
    )
    from examples.cases.super_topology_orchestration.cases.nested_trainer.build_solver import (
        build_solver as build_nested_trainer,
    )

    baseline = build_baseline_trainer()
    nested = build_nested_trainer()
    for trainer in (baseline, nested):
        assert isinstance(trainer, LearningSolver)
        assert isinstance(trainer.semantic_problem, LearningProblem)
        assert isinstance(trainer.model_representation, ModelRepresentation)
        assert type(trainer).fit is LearningSolver.fit

    result = topology_result

    assert result.ok
    assert [item.request.case_name for item in result.case_results] == [
        "baseline_solver",
        "baseline_trainer",
        "outer_search",
    ]
    baseline_solver, baseline_trainer, outer = result.case_results
    assert baseline_solver.ok and baseline_trainer.ok and outer.ok
    assert max(baseline_solver.started_at, baseline_trainer.started_at) < min(
        baseline_solver.finished_at,
        baseline_trainer.finished_at,
    )

    assert "baseline_solver.summary" in result.artifact_registry
    assert "baseline_trainer.summary" in result.artifact_registry
    assert "outer_search.topology_report" in result.artifact_registry
    assert (
        outer.request.input_artifact_bindings["solver_baseline"].publication
        == baseline_solver.artifact_publications["summary"]
    )
    assert (
        outer.request.input_artifact_bindings["trainer_baseline"].publication
        == baseline_trainer.artifact_publications["summary"]
    )
    assert outer.artifact_publications["topology_report"].receipt_digest
    assert outer.artifact_refs["topology_report"].size_bytes < 64_000
    assert outer.request.metadata["dag"]["dependencies"] == (
        "baseline_solver",
        "baseline_trainer",
    )
    assert outer.request.metadata["dag"]["inferred_artifact_dependencies"] == (
        "baseline_solver",
        "baseline_trainer",
    )

    solver_result = SolverResult.from_dict(outer.output)
    audit = dict(solver_result.metadata["super_topology"])
    assert audit["schema"] == "nsgablack.super_topology_audit/v2"
    assert audit["candidate_trainer_calls"] == 6
    assert tuple(audit["adapter_topology"]["phases"]) == (
        "explore",
        "vns_refine",
        "trust_region_refine",
        "de_refine",
    )
    assert dict(audit["adapter_topology"]["exploration"]["roles"]) == {
        "neighborhood_explorer": {"units": 2, "adapter": "VNSAdapter"},
        "region_probe": {"units": 1, "adapter": "TrustRegionDFOAdapter"},
    }
    assert all(audit["invariants"].values()), audit["invariants"]
    assert evaluate_invariants(audit) == dict(audit["invariants"])

    outer_identity = audit["outer_identity"]
    assert outer_identity["depth"] == 0
    for record in audit["nested_calls"]:
        trainer_identity = record["trainer_identity"]
        inner = record["inner"]
        inner_identity = inner["inner_identity"]

        assert trainer_identity["depth"] == 1
        assert trainer_identity["parent_case_run_id"] == outer_identity["case_run_id"]
        assert inner_identity["depth"] == 2
        assert inner_identity["parent_case_run_id"] == trainer_identity["case_run_id"]
        assert trainer_identity["root_run_id"] == outer_identity["root_run_id"]
        assert inner_identity["root_run_id"] == outer_identity["root_run_id"]

        assert record["trainer_status"] == "succeeded"
        assert inner["inner_status"] == "succeeded"
        assert record["trainer_resource_binding_current"] is True
        assert inner["inner_resource_binding_current"] is True
        assert record["trainer_resource_grant"]["threads"] == 2
        assert inner["inner_resource_grant"]["threads"] == 1
        assert record["trainer_deadline_at"] > 0
        assert 0 < inner["inner_deadline_at"] <= record["trainer_deadline_at"]

        trainer_budget = record["trainer_budget_usage"]["evaluations"]
        inner_budget = inner["inner_budget_usage"]["evaluations"]
        assert trainer_budget["limit"] == 3
        assert trainer_budget["charged_to_parent"] == 2
        assert trainer_budget["returned_to_parent"] == 1
        assert trainer_budget["settlement_status"] == "settled"
        assert inner_budget["limit"] == 2
        assert inner_budget["charged_to_parent"] == 1
        assert inner_budget["returned_to_parent"] == 1
        assert inner_budget["settlement_status"] == "settled"
        assert record["trainer_publication_digest"]

    child_audit = outer.metadata["runtime_audit"]["child_invocations"]
    assert not child_audit["pending_budget_settlements"]


@pytest.mark.parametrize(("path", "value", "check"), [
    (("dag", "dependencies"), [], "project_dag_dependencies"),
    (("baseline_publications", "trainer_baseline", "verified"), False, "artifact_authority_inputs"),
    (("nested_calls", 0, "trainer_identity", "parent_case_run_id"), "foreign", "solver_to_trainer"),
    (("nested_calls", 0, "inner", "inner_identity", "depth"), 99, "trainer_to_solver"),
    (("nested_calls", 0, "trainer_resource_grant", "threads"), 999, "resource_lineage"),
    (("nested_calls", 0, "trainer_resource_lineage", "lease_id"), "foreign", "resource_lineage"),
    (("nested_calls", 0, "trainer_budget_usage", "evaluations", "charged_to_parent"), 0, "budget_settlement"),
    (("nested_calls", 0, "trainer_cancellation", "namespace"), "foreign", "cancellation_deadline_lineage"),
    (("nested_calls", 0, "inner", "inner_cancellation", "deadline_at"), float("inf"), "cancellation_deadline_lineage"),
])
def test_topology_audit_rejects_changed_evidence(topology_result, path, value, check):
    audit = thaw_wire_value(SolverResult.from_dict(topology_result.case_results[-1].output).metadata["super_topology"])
    target = audit
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    assert evaluate_invariants(audit)[check] is False


def test_topology_audit_requires_nonempty_nested_evidence(topology_result):
    audit = thaw_wire_value(SolverResult.from_dict(topology_result.case_results[-1].output).metadata["super_topology"])
    audit["nested_calls"] = []
    audit["candidate_trainer_calls"] = 0
    checks = evaluate_invariants(audit)
    assert not any(checks[name] for name in (
        "solver_to_trainer", "trainer_to_solver", "resource_lineage",
        "budget_settlement", "cancellation_deadline_lineage",
    ))
    assert not any(evaluate_invariants({}).values())


def test_baseline_model_and_summary_share_finalization_authority(topology_result):
    baseline = topology_result.case_results[1]
    result = TrainerResult.from_dict(baseline.output)
    assert result.report["control_plane"] == "nsgablack.ComposableSolver"
    assert result.report["summary"]["committed_steps"] == 1
    assert result.report["summary"]["evaluation_count"] == 1
    assert result.best_feedback.loss < 1e-20
    assert result.best_model_ref == baseline.artifact_refs["best_model"]
    assert result.report["summary"]["weights"][1] == pytest.approx(0.7)
    assert len(result.history) == 1
    assert baseline.artifact_publications["summary"].transaction_id == (
        baseline.artifact_publications["best_model"].transaction_id
    )


def test_baseline_teardown_failure_cannot_start_artifact_finalization():
    from examples.cases.super_topology_orchestration.cases.baseline_trainer.build_solver import build_solver
    from examples.cases.super_topology_orchestration.cases.baseline_trainer.plugins.artifacts import BaselineArtifacts

    class RecordingArtifacts(BaselineArtifacts):
        started = False

        def begin_finalization(self, trainer, *, label="mlblack_result_finalization"):
            self.started = True
            return super().begin_finalization(trainer, label=label)

    trainer = build_solver()
    provider = RecordingArtifacts()
    trainer.set_artifact_provider(provider)
    original_teardown = trainer.teardown

    def fail_teardown():
        original_teardown()
        raise RuntimeError("teardown intentionally failed")

    trainer.teardown = fail_teardown
    with pytest.raises(RuntimeError, match="teardown intentionally failed"):
        trainer.fit()
    assert not provider.started
    assert not trainer.result_artifact_refs
