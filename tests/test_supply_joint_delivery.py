"""Delivery units use real pool snapshots and a test-sealed Artifact ledger, no Solver run."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from blackbase.context import create_snapshot_store
from blackbase.project import CaseRunIdentity, case_import_context
from blackbase.resources import ArtifactAuthority, ArtifactBinding, ArtifactPublicationError, ArtifactPublisher, coerce_resource_context
from blackbase.types import CandidateBatch, Feedback, SolverResult
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.core.state.incumbent import IncumbentState
from nsgablack.core.state.solution_pool import SolutionPool

PROJECT = Path(__file__).resolve().parents[1] / "examples/cases/supply_adjustment_nested"


def sealed_fixture(publisher, name, value):
    """A unit fixture seal, not evidence that a real production child executed."""
    ref = publisher.publish(name, value, serializer="json")
    transaction = "unit-transaction-" + publisher.case_run_id + "-" + name
    publisher.reserve_publication(name, transaction)
    publisher.record_provisional_publication(name, transaction, ref)
    receipt = publisher.commit_publications(transaction, {name: ref}, metadata={
        "case_finalization_sealed": True, "unit_test_fixture": True,
    })[name]
    return ArtifactBinding(ref, receipt)


@pytest.fixture
def bundle(tmp_path):
    with case_import_context(PROJECT, "supply_adjustment_nested"):
        wrapper_type = importlib.import_module("solver.joint_case").JointSupplyCase
        problem_type = importlib.import_module("problem").SupplyEventShiftProblem
        config_type = importlib.import_module("inner_solver").InnerProductionSolverConfig
        projection = importlib.import_module("evaluation.production_case")
    cfg = config_type(seed=42, max_evaluations=64)
    supply = np.zeros((2, 31))
    supply[:, 0] = [1000, 500]
    supply[0, 3], supply[1, 4] = 50, 70
    bom = np.eye(2)
    problem = problem_type(base_supply=supply, bom_matrix=bom, production_case_dir=tmp_path,
                           inner_solver_cfg=cfg, max_moved_events=100)
    source = {}
    for name in ("bom", "supply"):
        path = tmp_path / (name + ".source")
        path.write_bytes((name + " original input").encode())
        source[name] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    candidate = np.array([1., 2.])
    adjusted = problem.apply_shifts(problem.decode_shifts(candidate))
    schedule = np.zeros((2, 31))
    schedule[:, 0] = [100, 70]
    total = float(schedule.sum())
    raw_objectives = np.array([-total, 2, 3])
    selection_objectives = np.array([-total + 10, 2, 3])
    parent_identity = CaseRunIdentity(project_run_id="joint-unit", root_run_id="joint-unit",
                                     case_run_id="outer-case", invocation_id="outer-call", depth=0)
    child_identity = CaseRunIdentity(project_run_id="joint-unit", root_run_id="joint-unit",
        case_run_id="child-case", invocation_id="child-call", parent_case_run_id="outer-case", depth=1)
    authority = ArtifactAuthority(root=str(tmp_path / "artifacts"), namespace="joint-unit")
    child_publisher = ArtifactPublisher(authority, project_run_id="joint-unit", case_run_id="child-case")
    publisher = ArtifactPublisher(authority, project_run_id="joint-unit", case_run_id="outer-case")
    inner = {
        "schema": "supply_adjustment_nested.production_summary/v1", "candidate_token": "chosen-token",
        "scenario_digest": projection.compute_scenario_digest(bom, adjusted), "source": source,
        "shifts": candidate.astype(int).tolist(), "schedule": schedule.tolist(), "total_output": total,
        "raw_objectives": [-total, 0., .5, .6, .7], "raw_constraints": [0.] * 5,
        "inner_config": projection.config_payload(cfg), "identity": child_identity.as_dict(),
        "inner_candidate_token": "inner-token", "inner_evaluation_id": "inner-event",
        "algorithm_steps": 1, "algorithm_evaluations": 8, "audit_evaluations": 1,
        "day0_max_abs_delta": 0., "resource_binding_current": True,
    }
    binding = sealed_fixture(child_publisher, "production_summary", inner)
    usage = {name: {"limit": cap, "committed": used, "charged_to_parent": used,
                   "returned_to_parent": cap - used, "outstanding_reserved": 0, "settlement_status": "settled"}
             for name, cap, used in (("evaluations", 64, 8), ("audit_evaluations", 1, 1))}
    info = {"candidate_token": "chosen-token", "scenario_digest": inner["scenario_digest"],
            "production_summary_binding": binding.as_dict(), "inner_case_identity": child_identity.as_dict(),
            "inner_budget_usage": usage,
            "raw_evaluation": {"objectives": raw_objectives.tolist(), "constraint_violation": 0.}}
    pool = SolutionPool(create_snapshot_store(backend="memory"), run_id="joint-unit")

    def put(token="chosen-token", information=None, values=None):
        information = info if information is None else information
        if information is info and token != info["candidate_token"]:
            # A different accepted proposal also needs its own valid child
            # result, rather than borrowing the selected token's evidence.
            other_inner = deepcopy(inner)
            other_identity = parent_identity.child(case_run_id="child-" + token)
            other_inner.update(candidate_token=token, identity=other_identity.as_dict())
            other_publisher = ArtifactPublisher(authority, project_run_id="joint-unit", case_run_id=other_identity.case_run_id)
            other_binding = sealed_fixture(other_publisher, "production_summary", other_inner)
            information = {**info, "candidate_token": token,
                "production_summary_binding": other_binding.as_dict(), "inner_case_identity": other_identity.as_dict()}
        return pool.put(CandidateBatch.from_candidates(
            [candidate.copy() if values is None else values], candidate_tokens=(token,)),
            stage="accepted", feedback=OptimizationFeedbackBatch.from_feedback(
                (Feedback(objectives=selection_objectives, info=information),), violations=[0.]))[0]

    selected_ref = put()
    incumbent = IncumbentState(candidate, selection_objectives, 0., -155., candidate_token="chosen-token")
    original_result = SolverResult(best_solution=candidate, best_objectives=selection_objectives,
        best_constraint_violation=0., best_candidate_token="chosen-token",
        artifact_refs={"preserved": binding.ref}, metadata={"preserved_metadata": "yes"})

    class Solver:
        def __init__(self):
            self.problem, self.adapter = problem, object()
            self.representation_pipeline, self.plugin_manager, self.evaluation_mediator = object(), object(), object()
            self.resource_context = coerce_resource_context({"threads": 1})
            self.supply_source = source
            self.resource_binding_audit = {"current": True}
            self.component_override_audit = {"applied": True}
            self.solution_pool = pool
            self.generation, self.evaluation_count = 2, 3
            self.case_runtime = None
        def get_incumbent(self): return incumbent
        def export_case_result(self, raw): return original_result
        def set_case_runtime(self, runtime): self.case_runtime = runtime
        def get_resource_context(self): return self.resource_context
        def set_resource_context(self, value): self.resource_context = coerce_resource_context(value)
        def run(self, *args, **kwargs): return (args, kwargs)

    class Runtime:
        identity = parent_identity
        artifact_publisher = publisher
        published = {}
        def publish_artifact(self, name, value, **kwargs):
            self.published[name] = deepcopy(value)
            return publisher.publish(name, value, **kwargs)

    solver, runtime = Solver(), Runtime()
    case = wrapper_type(solver).set_case_runtime(runtime)
    return SimpleNamespace(case=case, solver=solver, runtime=runtime, pool=pool, put=put, info=info,
                           inner=inner, binding=binding, publisher=publisher, child_publisher=child_publisher,
                           original_result=original_result, selected_ref=selected_ref, incumbent=incumbent)


def test_exact_accepted_ref_and_verified_child_are_the_only_joint_delivery_source(bundle):
    # Equal-valued proposals with another token must not replace the chosen identity.
    bundle.put(token="equal-values-other-token")
    result = bundle.case.export_case_result({})
    summary = bundle.runtime.published["joint_summary"]
    assert summary["accepted_solution_ref"] == bundle.selected_ref.as_dict()
    assert summary["candidate_token"] == "chosen-token"
    assert summary["raw_objectives"] == [-170., 2., 3.]
    assert summary["selection_objectives"] == [-160., 2., 3.]
    assert summary["production_raw_objectives"] == bundle.inner["raw_objectives"]
    assert summary["schedule"] == bundle.inner["schedule"]
    assert summary["day0_max_abs_delta"] == 0
    assert summary["outer_evaluations"] == 3
    assert result.artifact_refs["preserved"] == bundle.original_result.artifact_refs["preserved"]
    assert result.metadata["preserved_metadata"] == "yes"
    assert "schedule" not in result.metadata["joint_summary"]
    assert "joint_summary" in result.artifact_refs


def test_duplicate_accepted_versions_are_not_resolved_by_latest_or_value(bundle):
    bundle.put()
    with pytest.raises(RuntimeError, match="exactly one"):
        bundle.case.export_case_result({})
    assert not bundle.runtime.published


def test_equal_valued_other_candidate_cannot_fill_a_missing_incumbent_token(bundle):
    bundle.solver.get_incumbent = lambda: SimpleNamespace(candidate_token="missing-token", candidate=np.array([1., 2.]))
    bundle.solver.export_case_result = lambda _: SolverResult(best_candidate_token="missing-token")
    with pytest.raises(RuntimeError, match="exactly one"):
        bundle.case.export_case_result({})
    assert not bundle.runtime.published


@pytest.mark.parametrize("change", ["missing_binding", "token", "scenario", "lineage", "budget"])
def test_corrupt_selected_feedback_is_rejected_without_a_successful_fallback(bundle, change):
    information = deepcopy(bundle.info)
    if change == "missing_binding":
        del information["production_summary_binding"]
    elif change == "token":
        information["candidate_token"] = "another-token"
    elif change == "scenario":
        information["scenario_digest"] = "sha256:" + "0" * 64
    elif change == "lineage":
        information["inner_case_identity"]["parent_case_run_id"] = "another-parent"
    else:
        information["inner_budget_usage"]["evaluations"]["charged_to_parent"] = 0
    replacement = SolutionPool(create_snapshot_store(backend="memory"), run_id="joint-unit")
    replacement.put(CandidateBatch.from_candidates([np.array([1., 2.])], candidate_tokens=("chosen-token",)),
        stage="accepted", feedback=OptimizationFeedbackBatch.from_feedback(
            (Feedback(objectives=[-160., 2., 3.], info=information),), violations=[0.]))
    bundle.solver.solution_pool = replacement
    with pytest.raises((KeyError, ValueError, RuntimeError)):
        bundle.case.export_case_result({})
    assert not bundle.runtime.published


def test_sealed_binding_still_requires_the_actual_artifact_bytes(bundle):
    path = Path(bundle.binding.ref.uri)
    # DataRef is a local path in this filesystem fixture.
    path.write_bytes(b'{"tampered": true}')
    with pytest.raises(ArtifactPublicationError, match="verification"):
        bundle.case.export_case_result({})
    assert not bundle.runtime.published


def test_publish_errors_propagate_and_original_run_and_components_are_forwarded(bundle):
    assert bundle.case.run(max_steps=2) == ((), {"max_steps": 2})
    assert bundle.case.adapter is bundle.solver.adapter
    assert bundle.case.component_override_audit is bundle.solver.component_override_audit
    bundle.case.set_resource_context({"threads": 2})
    assert bundle.case.get_resource_context().threads == 2
    def reject(*args, **kwargs):
        raise OSError("publication unavailable")
    bundle.runtime.publish_artifact = reject
    with pytest.raises(OSError, match="publication unavailable"):
        bundle.case.export_case_result({})


def test_search_audit_preserves_same_vector_with_distinct_tokens_and_real_receipts(bundle):
    other = bundle.put(token="same-vector-new-token")
    result = bundle.case.export_case_result({})
    audit = bundle.runtime.published["candidate_search_audit"]
    assert "candidate_search_audit" in result.artifact_refs
    assert audit["accepted_candidate_count"] == 2
    assert audit["unique_vector_count"] == 1
    assert [row["candidate_token"] for row in audit["rows"]] == ["chosen-token", "same-vector-new-token"]
    assert [row["solution_ref"] for row in audit["rows"]] == [bundle.selected_ref.as_dict(), other.as_dict()]
    assert audit["shift_day_histogram"]["1"] == 2
    assert audit["shift_day_histogram"]["2"] == 2
    assert audit["shift_day_histogram"]["29"] == 0
    assert audit["unique_moved_event_count"] == 2
    assert all(row["moved_indices"] == [0, 1] and row["days"] == [1, 2] for row in audit["rows"])
    assert all("schedule" not in row and "adjusted_supply" not in row for row in audit["rows"])
    assert bundle.solver.evaluation_count == 3  # No audit reevaluation.


def test_corrupt_unselected_candidate_stops_the_entire_audit_before_publication(bundle):
    information = {**bundle.info, "candidate_token": "bad-unselected"}
    bundle.put(token="bad-unselected", information=information)
    with pytest.raises(ValueError, match="audit child publication"):
        bundle.case.export_case_result({})
    assert not bundle.runtime.published
