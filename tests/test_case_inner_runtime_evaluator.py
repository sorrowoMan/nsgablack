from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from blackbase.project import CaseFailure, CaseRunRequest, CaseRunResult, ProjectConfigurationError
from blackbase.resources import ArtifactBinding, ArtifactPublicationReceipt, DataRef, TerminationPolicy
from blackbase.types import Feedback
from nsgablack.core import CaseInnerRuntimeEvaluator, ChildCaseExecutionError


class _Runtime:
    def __init__(self, *, fail: bool = False) -> None:
        self.request = CaseRunRequest(
            project_name="project",
            stage_name="outer",
            case_name="outer_solver",
            resource_context={"threads": 1, "grant": {"threads": 1, "workers": 1}},
        )
        self.fail = fail
        self.last_request: CaseRunRequest | None = None

    def checkpoint(self) -> None:
        return None

    def invoke(self, request: CaseRunRequest) -> CaseRunResult:
        self.last_request = request
        request = replace(request, identity=self.request.identity.child())
        if self.fail:
            return CaseRunResult(
                request=request,
                status="failed",
                exit_code=1,
                failure=CaseFailure(kind="InnerFailed", message="no solution"),
            )
        return CaseRunResult(
            request=request,
            status="succeeded",
            output={"objectives": [2.0], "violation": 0.5},
        )


class _Solver:
    generation = 4

    def __init__(self, runtime: _Runtime) -> None:
        self.case_runtime = runtime


def _project(_solver, _candidate, result: CaseRunResult):
    return result.output["objectives"], result.output["violation"]


def test_complete_inner_case_uses_public_request_and_explicit_projection() -> None:
    runtime = _Runtime()
    evaluator = CaseInnerRuntimeEvaluator(
        case_name="inner_solver",
        projector=_project,
        resource_request={"threads": 1},
        budget_request={"evaluations": 3},
        timeout_seconds=5.0,
    )

    objectives, violation = evaluator.evaluate(
        solver=_Solver(runtime),
        x=np.array([1.0, 2.0]),
        individual_id=7,
    )

    assert np.allclose(objectives, [2.0])
    assert violation == 0.5
    assert runtime.last_request is not None
    assert runtime.last_request.inputs["candidate"] == (1.0, 2.0)
    assert runtime.last_request.resource_context == {}
    assert runtime.last_request.budget_request == {"evaluations": 3}
    assert runtime.last_request.control.deadline_at > 0


def test_complete_inner_case_preserves_structured_failure() -> None:
    runtime = _Runtime(fail=True)
    evaluator = CaseInnerRuntimeEvaluator(case_name="inner_solver", projector=_project)

    with pytest.raises(ChildCaseExecutionError) as caught:
        evaluator.evaluate(
            solver=_Solver(runtime),
            x=np.array([1.0]),
            individual_id=1,
        )

    assert caught.value.result.failure is not None
    assert caught.value.result.failure.kind == "InnerFailed"
    assert evaluator.last_result is caught.value.result


def test_candidate_specific_configuration_keeps_identity_and_readonly_values() -> None:
    runtime = _Runtime()
    solver = _Solver(runtime)
    candidate = np.array([4.0, 9.0])
    observed = []

    class Provenance:
        def as_dict(self):
            return {"candidate_token": "bound-proposal", "metadata": {"origin": "test"}}

    def provenance_for(value):
        assert value is candidate
        return Provenance()

    solver.candidate_provenance_for = provenance_for

    def configure(_solver, values, context):
        with pytest.raises(ValueError):
            values[0] = -100
        with pytest.raises(ValueError):
            values.setflags(write=True)
        observed.append(context["_candidate_provenance"]["candidate_token"])
        context["_candidate_provenance"]["metadata"]["origin"] = "factory-local"
        return {"task": {"shifts": values.tolist()}, "mode": "dynamic"}

    evaluator = CaseInnerRuntimeEvaluator(
        case_name="inner_solver", projector=_project,
        component_overrides={"mode": "static", "default": 1},
        component_overrides_factory=configure,
        termination=TerminationPolicy(mode="cooperative_then_terminate", grace_seconds=.1),
        timeout_seconds=5,
    )
    evaluator.evaluate(solver=solver, x=candidate, individual_id=0)
    request = runtime.last_request
    assert np.array_equal(candidate, [4.0, 9.0])
    assert observed == ["bound-proposal"]
    assert request.component_overrides["task"]["shifts"] == (4.0, 9.0)
    assert request.component_overrides["mode"] == "dynamic"
    assert request.component_overrides["default"] == 1
    assert request.inputs["candidate_provenance"]["metadata"]["origin"] == "test"
    assert request.control.termination.requires_isolation


def test_invalid_configuration_is_rejected_before_child_dispatch() -> None:
    runtime = _Runtime()
    evaluator = CaseInnerRuntimeEvaluator(
        case_name="inner_solver", projector=_project,
        component_overrides_factory=lambda *_: ["invalid"],
    )
    with pytest.raises(TypeError, match="return a Mapping"):
        evaluator.evaluate(solver=_Solver(runtime), x=np.array([1.0]), individual_id=0)
    assert runtime.last_request is None
    assert evaluator.stats["calls"] == 0


def test_rich_child_feedback_preserves_receipt_link_for_pool_evidence() -> None:
    runtime = _Runtime()
    feedback = Feedback(
        objectives=np.array([2.0]), constraints=np.array([.5]),
        info={"inner_case_run_id": "producer:1", "binding_digest": "source-receipt"},
    )
    evaluator = CaseInnerRuntimeEvaluator(
        case_name="inner_solver", projector=lambda *_: feedback,
    )
    result = evaluator.evaluate(solver=_Solver(runtime), x=np.array([1.0]), individual_id=0)
    assert result is feedback
    assert result.info["inner_case_run_id"] == "producer:1"
    assert result.info["binding_digest"] == "source-receipt"
    assert evaluator.stats["success"] == 1


def test_parent_published_input_is_bound_by_name_to_child_request():
    runtime = _Runtime()
    ref = DataRef(uri="memory://bom", kind="artifact", backend="memory", checksum="sha256:" + "a" * 64)
    receipt = ArtifactPublicationReceipt(
        publication_id="source-publication", artifact_name="bom", ref=ref,
        project_run_id=runtime.request.identity.project_run_id,
        case_run_id="prepared-source", transaction_id="source-transaction",
        authority_namespace="test", committed_at=1.0,
        metadata={"case_finalization_sealed": True},
    )
    binding = ArtifactBinding(ref=ref, publication=receipt)
    runtime.request = replace(runtime.request, input_artifact_bindings={"source_bom": binding})
    evaluator = CaseInnerRuntimeEvaluator(
        case_name="inner_solver", projector=_project, artifact_bindings={"bom": "source_bom"},
    )
    evaluator.evaluate(solver=_Solver(runtime), x=np.array([1.0]), individual_id=0)
    assert runtime.last_request.input_artifact_bindings == {"bom": binding}
    assert runtime.last_request.input_artifacts == {"bom": ref}


def test_missing_parent_input_fails_before_child_dispatch():
    runtime = _Runtime()
    evaluator = CaseInnerRuntimeEvaluator(
        case_name="inner_solver", projector=_project, artifact_bindings={"bom": "absent"},
    )
    with pytest.raises(ProjectConfigurationError, match="missing artifact"):
        evaluator.evaluate(solver=_Solver(runtime), x=np.array([1.0]), individual_id=0)
    assert runtime.last_request is None
