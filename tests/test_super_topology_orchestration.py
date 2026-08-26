"""End-to-end proof for the complete Project/Case nesting topology."""

from __future__ import annotations

import shutil
from pathlib import Path

from blackbase.project import execute_project
from blackbase.types import SolverResult


EXAMPLE_ROOT = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "cases"
    / "super_topology_orchestration"
)


def test_super_topology_executes_with_authoritative_lineage_and_settlement(
    tmp_path: Path,
) -> None:
    from mlblack.core import LearningProblem, ModelRepresentation

    from examples.cases.super_topology_orchestration.cases.baseline_trainer.build_solver import (
        build_solver as build_baseline_trainer,
    )
    from examples.cases.super_topology_orchestration.cases.nested_trainer.build_solver import (
        build_solver as build_nested_trainer,
    )

    baseline = build_baseline_trainer()
    nested = build_nested_trainer()
    assert isinstance(baseline.problem, LearningProblem)
    assert isinstance(baseline.pipeline, ModelRepresentation)
    assert isinstance(nested.problem, LearningProblem)
    assert isinstance(nested.pipeline, ModelRepresentation)

    project_root = tmp_path / "super_topology_orchestration"
    shutil.copytree(
        EXAMPLE_ROOT,
        project_root,
        ignore=shutil.ignore_patterns(".blackbase", "__pycache__", "*.pyc"),
    )

    result = execute_project(
        project_root,
        run_id="super-topology-e2e",
        record=False,
    )

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
    assert audit["schema"] == "nsgablack.super_topology_audit/v1"
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
    assert all(audit["invariants"].values())

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
        assert trainer_budget["charged_to_parent"] == 1
        assert trainer_budget["returned_to_parent"] == 2
        assert trainer_budget["settlement_status"] == "settled"
        assert inner_budget["limit"] == 2
        assert inner_budget["charged_to_parent"] == 1
        assert inner_budget["returned_to_parent"] == 1
        assert inner_budget["settlement_status"] == "settled"
        assert record["trainer_publication_digest"]

    child_audit = outer.metadata["runtime_audit"]["child_invocations"]
    assert not child_audit["pending_budget_settlements"]
