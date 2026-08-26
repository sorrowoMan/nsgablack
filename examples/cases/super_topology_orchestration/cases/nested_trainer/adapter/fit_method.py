"""ML fit policy that delegates calibration to a standard Solver Case."""

from __future__ import annotations

from blackbase.project import CaseRunRequest, ExecutionControl
from blackbase.types import SolverResult


class NestedFitMethod:
    name = "fit.with_nested_solver/v1"

    def solve_calibration(self, case_runtime, *, target: float):
        request = CaseRunRequest(
            project_name=case_runtime.request.project_name,
            stage_name="trainer_inner_optimization",
            case_name="inner_solver",
            case_kind="solver",
            control=ExecutionControl.with_timeout(
                10.0,
                metadata={"semantic_scope": "trainer.calibration"},
            ),
            resource_request={
                "workers": 1,
                "threads": 1,
                "gpus": 0,
                "backend": "local",
                "device": "cpu",
            },
            budget_request={"evaluations": 2},
            component_overrides={"target": float(target)},
            metadata={"topology_edge": "trainer->solver"},
        )
        child = case_runtime.invoke(request)
        child.raise_for_failure("inner calibration Solver Case failed")
        result = SolverResult.from_dict(child.output)
        if result.best_solution is None:
            raise RuntimeError("inner Solver completed without an authoritative best solution")
        state = result.best_solution
        values = state.values if hasattr(state, "values") else state
        calibration = float(values[0])
        return calibration, child, result
