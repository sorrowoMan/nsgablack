"""Exercise joint repair through formal generated Project/Case surfaces."""
from pathlib import Path
import pytest

from blackbase.project import execute_project
from blackbase.types import SolverResult
from nsgablack.project.scaffold import create_project, add_case


PIPELINE = '''
import numpy as np
from blackbase.types import CandidateBatch
from nsgablack.representation import RepresentationPipeline

def validate(state, context):
    return bool(state.metadata.get("unit_repaired") and np.all(state.values == 0.25))

class ProblemRepair:
    def initialize(self, problem, context):
        return np.array([0.8])
    def repair(self, candidate, context):
        return np.clip(candidate, 0., 1.)
    validate = staticmethod(validate)

class UnitRepair:
    def repair(self, unit, evidence, context):
        result = CandidateBatch.from_candidates(
            [state.with_values([0.25]).with_meta(unit_repaired=True) for state in evidence.after.semantic_states],
            candidate_tokens=evidence.after.candidate_tokens)
        unit.current = result.numeric_matrix[0].copy()
        return result
    def validate(self, unit, evidence, context):
        return bool(np.array_equal(unit.current, evidence.after.numeric_matrix[0]))

def build_pipeline():
    component = ProblemRepair()
    return RepresentationPipeline(initializer=component, repair=component)
'''

ADAPTER = '''
from nsgablack.adapters import GaussianSearchAdapter, CompositeAdapter, RoleAdapter
from ..pipeline.components import UnitRepair

def build_adapter():
    leaf = GaussianSearchAdapter(population_size=1)
    leaf.set_unit_repair(UnitRepair())
    return CompositeAdapter([RoleAdapter("worker", leaf)])
'''

PROBLEM = '''
from nsgablack.core import BlackBoxProblem
class Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["minimize"], bounds=[(0., 1.)])
    def evaluate(self, candidate):
        assert candidate[0] == 0.25
        return float(candidate[0] ** 2)
'''

SOLVER_BUILDER = '''
from nsgablack.core import ComposableSolver
from nsgablack.representation import JointRepairPolicy
from .adapter.components import build_adapter
from .pipeline.components import build_pipeline
from .problem.components import Problem

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    solver = ComposableSolver(Problem(), adapter=build_adapter(), representation_pipeline=build_pipeline(),
                              joint_repair_policy=JointRepairPolicy(), resource_context=resource_context)
    solver.set_max_steps(1)
    return solver
'''

ML_PROBLEM = '''
from mlblack.core import ModelRepresentation, LearningProblem, UnknownState, Feedback
class Representation(ModelRepresentation):
    def init(self, context):
        return UnknownState([0.8], {"model": "point"})
    def decode(self, state, context=None):
        return state.values.copy()
class Problem(LearningProblem):
    def evaluate(self, model, state, context=None):
        assert state.metadata["unit_repaired"] and state.values[0] == 0.25
        return Feedback(objectives=[float(state.values[0] ** 2)])
'''

ML_BUILDER = '''
from mlblack.integrations import build_learning_solver
from nsgablack.representation import JointRepairPolicy
from .adapter.components import build_adapter
from .pipeline.components import validate
from .problem.components import Problem, Representation

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    solver = build_learning_solver(problem=Problem(), representation=Representation(), adapter=build_adapter(),
        problem_validator=validate, joint_repair_policy=JointRepairPolicy(), resource_context=resource_context)
    solver.set_max_steps(1)
    return solver
'''

OUTER_PROBLEM = '''
from nsgablack.core.nested_solver import CaseInnerRuntimeEvaluator
from blackbase.types import TrainerResult
from .base import Problem as Base

def project(control, candidate, result):
    trained = TrainerResult.from_dict(result.output)
    assert trained.best_feedback.objectives[0] == 0.0625
    assert result.request.identity.depth == 1
    return [0.0625], 0.

class Problem(Base):
    def __init__(self):
        super().__init__()
        self.inner_runtime_evaluator = CaseInnerRuntimeEvaluator(
            case_name="learner", case_kind="trainer", projector=project)
    def evaluate(self, candidate):
        raise AssertionError("standard child Case must supply the outer evaluation")
'''


def make_project(tmp_path, policy):
    root = create_project(tmp_path / "joint_project")
    for name, kind in (("outer", "solver"), ("sibling", "solver"), ("learner", "trainer")):
        add_case(name, kind, project_root=root)
        case = root / "cases" / name
        for relative, source in {
            "pipeline/components.py": PIPELINE, "adapter/components.py": ADAPTER,
            "problem/components.py": ML_PROBLEM if kind == "trainer" else PROBLEM,
            "build_solver.py": ML_BUILDER if kind == "trainer" else SOLVER_BUILDER,
        }.items():
            (case / relative).write_text(source, encoding="utf-8")
    (root / "cases/outer/problem/base.py").write_text(PROBLEM, encoding="utf-8")
    (root / "cases/outer/problem/components.py").write_text(OUTER_PROBLEM, encoding="utf-8")
    config = {
        "PROJECT_NAME": "joint_project",
        "L0": {"namespace": "joint_project", "offer": {"threads": 4, "workers": 4, "gpus": 0},
               "policy": {"mode": "strict", "max_workers": 4, "max_threads": 4},
               "default_request": {"threads": 1, "workers": 1, "gpus": 0},
               "execution_backend": "local", "budgets": {"evaluations": 8},
               "lease_backend": "sqlite", "lease_path": ".blackbase/leases.sqlite",
               "artifacts": {"path": ".blackbase/artifacts", "allow_unsafe_serializers": False}},
        "STAGES": [{"name": "joint", "policy": policy, "cases": ["outer", "sibling"], "max_workers": 2,
                    "resource_requests": {"outer": {"threads": 2, "workers": 1}}}],
        "GROUPS": {"default": {"stages": ["joint"]}},
    }
    (root / "project_config.py").write_text("\n".join(f"{key} = {value!r}" for key, value in config.items()), encoding="utf-8")
    return root


@pytest.mark.parametrize("policy", ["serial", "parallel", "dag"])
def test_joint_repair_in_project_and_nested_ml_case(tmp_path, policy):
    root = make_project(tmp_path, policy)
    result = execute_project(root, run_id="joint-" + policy, record=True)
    assert result.ok, result.as_dict()
    assert len(result.case_results) == 2
    for case in result.case_results:
        solved = SolverResult.from_dict(case.output)
        assert solved.best_solution.metadata["unit_repaired"]
        assert solved.best_objectives[0] == 0.0625
        assert case.request.resource_context["namespace"]
    # Manifest recovery reuses completed Cases rather than repeating child evaluations.
    resumed = execute_project(root, resume_from=Path(result.manifest_path), record=False)
    assert resumed.ok and len(resumed.case_results) == 2
    assert resumed.resumed_from == result.manifest_path
    for original, reused in zip(result.case_results, resumed.case_results):
        assert reused.identity == original.identity
        assert (reused.started_at, reused.finished_at) == (original.started_at, original.finished_at)
        assert reused.output == original.output


def test_project_cancellation_in_repair_and_resume_keeps_successful_sibling(tmp_path):
    root = make_project(tmp_path, "parallel")
    config = root / "project_config.py"
    config.write_text(config.read_text(encoding="utf-8").replace(
        "'max_workers': 2,", "'max_workers': 2, 'failure_policy': 'continue',"), encoding="utf-8")
    pipeline = root / "cases/outer/pipeline/components.py"
    marker = tmp_path / "cancel-once"
    cancellation = '''        from pathlib import Path
        from blackbase.resources import CancellationRef, CancellationToken
        marker = Path(MARKER_PATH)
        if not marker.exists():
            marker.touch()
            resource = context["resource_context"]
            ref = CancellationRef.from_dict(resource["metadata"]["execution_control"]["cancellation"])
            CancellationToken(ref).cancel("cancel-inside-unit-repair")
'''
    cancellation = cancellation.replace("MARKER_PATH", repr(str(marker)))
    pipeline.write_text(PIPELINE.replace("        return result\n", cancellation + "        return result\n"), encoding="utf-8")
    first = execute_project(root, run_id="repair-cancel", record=True)
    assert not first.ok
    outer, sibling = first.case_results
    assert not outer.ok and "cancel-inside-unit-repair" in outer.error
    assert sibling.ok
    resumed = execute_project(root, resume_from=Path(first.manifest_path), record=False)
    assert resumed.ok, resumed.as_dict()
    assert resumed.case_results[1].finished_at == sibling.finished_at
    assert SolverResult.from_dict(resumed.case_results[0].output).best_objectives[0] == 0.0625
