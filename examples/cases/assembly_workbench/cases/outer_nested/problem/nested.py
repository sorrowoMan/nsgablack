"""x 的评分委托完整的内层 Case；返回 y 不冒充外层候选 x。"""
from pathlib import Path
import numpy as np
from blackbase.project import CaseRunRequest, ExecutionControl
from blackbase.types import SolverResult
from nsgablack.core import BlackBoxProblem

class NestedResponseProblem(BlackBoxProblem):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()

    def __init__(self, *, inner_steps=2, output_dir=None):
        super().__init__(name="nested_response_design", dimension=1,
                         objectives=["min"], bounds=[(-2., 2.)])
        self.inner_steps, self.output_dir = int(inner_steps), output_dir
        self.case_runtime = None
        self.calls = []

    def set_case_runtime(self, runtime):
        self.case_runtime = runtime

    def evaluate(self, candidate):
        if self.case_runtime is None:
            raise RuntimeError("nested search requires the standard Project Case runtime")
        x = float(np.asarray(candidate).reshape(-1)[0])
        runtime = self.case_runtime
        sequence = len(self.calls)
        output = Path(self.output_dir) / "inner_calls" / f"call_{sequence:03d}"
        request = CaseRunRequest(project_name=runtime.request.project_name,
            stage_name="response_evaluation", case_name="inner_response", case_kind="solver",
            control=ExecutionControl.with_timeout(20.),
            resource_request={"threads": 1, "workers": 1, "gpus": 0, "backend": "local"},
            budget_request={"evaluations": self.inner_steps},
            component_overrides={"config": {"steps": self.inner_steps}, "output_dir": str(output)},
            inputs={"inner_task_payload": {"target": x, "outer_candidate": [x],
                    "source": "outer_nested", "sequence": sequence}},
            metadata={"edge": "outer_nested->inner_response"})
        child = runtime.invoke(request)
        child.raise_for_failure("conditional response Case failed")
        result = SolverResult.from_dict(child.output)
        state = result.best_solution
        values = state.values if hasattr(state, "values") else state
        y = float(values[0])
        inner_loss = float(np.asarray(result.best_objectives).reshape(-1)[0])
        objective = inner_loss + .05 * x ** 2
        receipt = child.artifact_publications["summary"]
        self.calls.append({"outer_candidate": [x], "best_response": y,
            "inner_loss": inner_loss, "outer_objective": objective,
            "parent_identity": runtime.identity.as_dict(), "identity": child.identity.as_dict(),
            "resource_grant": dict(child.request.resource_context.get("grant", {})),
            "parent_resource_grant": dict(runtime.resource_context.grant),
            "resource_binding_current": bool(dict(child.resource_usage.get("binding", {})).get("current", False)),
            "child_grant": child.request.child_grant.as_dict(),
            "budget_usage": dict(child.budget_usage),
            "control": child.control.as_dict(), "status": child.status,
            "started_at": child.started_at, "finished_at": child.finished_at,
            "inner_summary": dict(result.metadata["summary"]),
            "artifact_ref": child.artifact_refs["summary"].as_dict(),
            "artifact_publication": receipt.as_dict()})
        return [objective]
