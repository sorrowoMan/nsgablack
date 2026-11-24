"""Two real workers execute an outer Solver's standard child-Case batch."""
from __future__ import annotations

import multiprocessing
import tempfile

import numpy as np

from blackbase.project import execute_project
from blackbase.project.external_worker import ExternalCaseWorker
from blackbase.project.scaffold import add_case, create_project
from blackbase.resources import ResourceOffer, SQLiteTaskTransport, WorkerDescriptor


def run_worker(project, name, ready):
    worker = ExternalCaseWorker(
        SQLiteTaskTransport(project + "/.blackbase/tasks.sqlite"),
        WorkerDescriptor(worker_id=name, executor_backend="external",
                         capabilities=("project_case",), offer=ResourceOffer(threads=1)),
        allowed_project_root=project, lease_seconds=5, heartbeat_interval_seconds=.2,
    )
    ready.set()
    worker.run_forever(poll_interval_seconds=.01, max_tasks=1)


def test_outer_solver_batch_uses_external_cases_and_receipts(tmp_path, monkeypatch):
    # Worker processes inherit these writable paths; no sandbox escalation or
    # changes to the user's global TEMP configuration are needed.
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    monkeypatch.setenv("TEMP", str(scratch))
    monkeypatch.setenv("TMP", str(scratch))
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))
    project = create_project(tmp_path / "batch", framework="blackbase")
    child = add_case("inner", "solver", project_root=project)
    parent = add_case("outer", "solver", project_root=project)
    preparation = add_case("prepare", "solver", project_root=project)
    (preparation / "build_solver.py").write_text('''
class Prepare:
    def run(self):
        self.case_runtime.publish_artifact("dataset", {"factor": 2.0})
        return {"prepared": True}
def build_solver(config=None, *, resource_context=None, component_overrides=None):
    return Prepare()
''', encoding="utf-8")
    (child / "build_solver.py").write_text('''
import json
import os
import time
from blackbase.resources import BudgetAccount
class Inner:
    def __init__(self, resource_context):
        self.resource_context = resource_context
    def set_input_artifacts(self, refs):
        self.input_artifacts = dict(refs)
    def run(self):
        started = time.time()
        time.sleep(.25)
        self.case_runtime.checkpoint()
        account = BudgetAccount.from_resource_context("evaluations", self.resource_context)
        claim = account.reserve(1)
        account.consume(claim, 1)
        account.complete(claim)
        binding = self.case_runtime.request.input_artifact_bindings["dataset"]
        data = json.loads(self.case_runtime.artifact_publisher.read_verified(binding))
        value = float(self.case_inputs["candidate"][0]) * data["factor"]
        self.case_runtime.publish_artifact("answer", {"value": value})
        return {"value": value, "pid": os.getpid(), "started": started, "finished": time.time()}
def build_solver(config=None, *, resource_context=None, component_overrides=None):
    return Inner(dict(resource_context or {}))
''', encoding="utf-8")
    (parent / "build_solver.py").write_text('''
import json
import numpy as np
from blackbase.resources import ArtifactBinding
from blackbase.types import Feedback
from nsgablack.core import BlackBoxProblem, ComposableSolver, CaseInnerRuntimeEvaluator
class Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, objectives=["cost"], bounds=[(-2., 2.)])
        self.inner_runtime_evaluator = CaseInnerRuntimeEvaluator(
            case_name="inner", projector=project, max_workers=2,
            artifact_bindings={"dataset": "dataset"},
            resource_request={"workers": 1, "threads": 1}, budget_request={"evaluations": 2})
    def evaluate(self, candidate):
        raise AssertionError("must use standard child Cases")
def project(solver, candidate, result):
    binding = ArtifactBinding(ref=result.artifact_refs["answer"], publication=result.artifact_publications["answer"])
    data = json.loads(solver.case_runtime.artifact_publisher.read_verified(binding))
    return Feedback(objectives=np.array([data["value"]]), info={"child_run_id": result.identity.case_run_id,
        "receipt": binding.publication.receipt_digest})
class Outer:
    def __init__(self, context):
        self.solver = ComposableSolver(Problem(), resource_context=context)
    def set_input_artifacts(self, refs):
        self.solver.set_input_artifacts(refs)
    def set_case_runtime(self, runtime):
        self.solver.set_case_runtime(runtime)
    def set_resource_context(self, context):
        self.solver.set_resource_context(context)
    def get_resource_context(self):
        return self.solver.get_resource_context()
    def run(self):
        objectives, violations = self.solver.evaluate_population(np.array([[.25], [.75]]))
        evaluator = self.solver.problem.inner_runtime_evaluator
        return {"objectives": objectives, "violations": violations,
            "outer_evaluations": self.solver.evaluation_count,
            "children": [r.as_dict() for r in evaluator.last_batch_results],
            "feedback_ids": [f.info["child_run_id"] for f in self.solver.get_last_feedback_batch().items]}
def build_solver(config=None, *, resource_context=None, component_overrides=None):
    return Outer(resource_context)
''', encoding="utf-8")
    targets = {
        name: {"project_root": str(project), "l0": {
            "namespace": "batch.node." + name, "lease_backend": "sqlite",
            "lease_path": ".blackbase/node_" + name + ".sqlite",
            "offer": {"threads": 1},
            "policy": {"mode": "strict", "max_workers": 1, "max_threads": 1},
        }} for name in ("first", "second")
    }
    l0 = {
        "namespace": "batch.parent", "lease_backend": "sqlite",
        "lease_path": ".blackbase/parent.sqlite", "offer": {"threads": 1},
        "policy": {"mode": "strict", "max_workers": 1, "max_threads": 1},
        "default_request": {"workers": 1, "threads": 1}, "budgets": {"evaluations": 6},
        "nested_execution": {
            "case_names": ["inner"], "shared_filesystem": True, "max_inflight": 2,
            "queue_timeout_seconds": 10, "poll_interval_seconds": .01,
            "transport": {"backend": "sqlite", "path": ".blackbase/tasks.sqlite"},
            "targets": targets,
        },
    }
    (project / "project_config.py").write_text(
        "PROJECT_NAME = 'batch'\nL0 = " + repr(l0) +
        "\nSTAGES = [{'name': 'prepare', 'cases': ['prepare']}, "
        "{'name': 'run', 'cases': ['outer'], 'input_artifacts': "
        "{'outer': {'dataset': 'prepare.prepare.dataset'}}}]\n"
        "GROUPS = {'default': {'stages': ['prepare', 'run']}}\n",
        encoding="utf-8",
    )
    ctx = multiprocessing.get_context("spawn")
    processes = []
    successful = False
    try:
        for name in targets:
            ready = ctx.Event()
            process = ctx.Process(target=run_worker, args=(str(project), name, ready))
            process.start()
            processes.append(process)
            assert ready.wait(15), "test worker failed to start"
        result = execute_project(project, record=False)
        assert result.ok, [item.failure for item in result.case_results]
        output = result.case_results[-1].output
        np.testing.assert_allclose(output["objectives"], [[.5], [1.5]])
        assert output["outer_evaluations"] == 2
        children = output["children"]
        ids = tuple(child["request"]["identity"]["case_run_id"] for child in children)
        assert output["feedback_ids"] == ids
        assert len(set(ids)) == len({child["output"]["pid"] for child in children}) == 2
        assert max(child["output"]["started"] for child in children) < min(child["output"]["finished"] for child in children)
        for child in children:
            assert child["request"]["identity"]["attempt"] == 1
            assert child["budget_usage"]["evaluations"]["charged_to_parent"] == 1
            assert child["budget_usage"]["evaluations"]["returned_to_parent"] == 1
            assert child["artifact_publications"]["answer"]["case_run_id"] == child["request"]["identity"]["case_run_id"]
        successful = True
    finally:
        for process in processes:
            if not successful and process.is_alive():
                process.terminate()
            process.join(10)
            if process.is_alive():
                process.terminate()
                process.join(5)
        if successful:
            assert all(process.exitcode == 0 for process in processes)
