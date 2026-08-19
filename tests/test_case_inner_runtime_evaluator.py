from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from blackbase.project import CaseFailure, CaseRunRequest, CaseRunResult
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
    assert runtime.last_request.inputs["candidate"] == [1.0, 2.0]
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
