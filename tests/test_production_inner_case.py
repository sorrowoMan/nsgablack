"""Small-data checks of canonical scenarios and complete isolated child Cases."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
import shutil

import numpy as np
import pandas as pd
import pytest

from blackbase.project import build_case, case_import_context, execute_project, load_case_builder
from blackbase.resources import ArtifactBinding, ArtifactPublisher
from blackbase.wire import thaw_wire_mapping

REPO = Path(__file__).resolve().parents[1]
SUPPLY_PROJECT = REPO / "examples/cases/supply_adjustment_nested"
PRODUCTION_CASE = REPO / "examples/cases/production_scheduling/cases/production_scheduling"


@pytest.fixture
def small_task(tmp_path):
    bom = np.zeros((8, 3), dtype=int)
    bom[np.arange(8), np.arange(8) % 3] = 1
    supply = np.zeros((3, 31), dtype=float)
    supply[:, 0] = 60000
    supply[0, 5], supply[1, 9] = 3000, 4000
    bom_path, supply_path = tmp_path / "bom.csv", tmp_path / "supply.csv"
    pd.DataFrame([(m, 1 + m % 3, 1) for m in range(8)], columns=["machine", "material", "required"]).to_csv(bom_path, index=False)
    pd.DataFrame({"material": [1, 2, 3], **{str(d): supply[:, d] for d in range(31)}}).to_csv(supply_path, index=False)
    adjusted = supply.copy()
    adjusted[0, 5] -= 3000
    adjusted[0, 4] += 3000
    adjusted[1, 9] -= 4000
    adjusted[1, 7] += 4000
    with case_import_context(SUPPLY_PROJECT, "production_inner"):
        digest_fn = importlib.import_module("cases.production_inner.runtime.task_contract").compute_scenario_digest
    task = {
        "schema": "supply_adjustment_nested.production_task/v1",
        "source": {name: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                   for name, path in (("bom", bom_path), ("supply", supply_path))},
        "machines": 8, "materials": 3, "days": 31,
        "shifts": [1, 2], "candidate_token": "outer-evaluated-proposal-1",
        "scenario_digest": digest_fn(bom, adjusted), "max_moved_events": 100,
        "production_case_dir": str(PRODUCTION_CASE),
        "inner_config": {"pop_size": 8, "generations": 1, "seed": 42, "max_evaluations": 64},
    }
    return task, bom, adjusted


def test_canonical_scenario_preserves_five_objectives_and_private_data(small_task):
    task, bom, adjusted = small_task
    with case_import_context(SUPPLY_PROJECT, "supply_adjustment_nested"):
        inner = importlib.import_module("inner_solver")
    cfg = inner.InnerProductionSolverConfig(**task["inner_config"])
    solver, problem = inner.build_inner_production_solver(
        bom_matrix=bom, supply_matrix=adjusted, production_case_dir=PRODUCTION_CASE, cfg=cfg,
        resource_context={"threads": 1},
    )
    assert problem.get_num_objectives() == 5
    assert problem.constraints.max_production_per_machine == 3000
    assert problem.constraints.min_production_per_machine == 50
    assert problem.constraints.min_machines_per_day == 5
    assert problem.constraints.max_machines_per_day == 8
    np.testing.assert_array_equal(problem.data.bom_matrix, bom)
    np.testing.assert_array_equal(problem.data.supply_matrix, adjusted)
    adjusted[0, 0] = -1
    assert problem.data.supply_matrix[0, 0] == 60000
    assert solver.random_seed == 42
    assert solver.resource_binding_audit["current"] is True
    assert solver.generation == solver.evaluation_count == 0


def test_parallel_problem_factory_keeps_scenarios_separate(small_task):
    _, bom, adjusted = small_task
    scenario = {"schema": "production_scheduling.scenario/v1", "bom_matrix": bom.tolist(), "supply_matrix": adjusted.tolist()}
    with case_import_context(PRODUCTION_CASE.parents[1], PRODUCTION_CASE.name):
        factory_type = importlib.import_module("problem.problem_factory").ProductionProblemFactory
        kwargs = dict(base_dir=str(PRODUCTION_CASE), bom=None, supply=None, machines=8, materials=3,
                      days=31, max_machines=8, min_machines=5, min_prod=50, max_prod=3000,
                      shortage_unit_penalty=1.0, penalty_objective=True, penalty_scale=.001)
        one = factory_type(**kwargs, scenario=scenario)
        other_scenario = deepcopy(scenario)
        other_scenario["supply_matrix"][0][4] += 17
        other = factory_type(**kwargs, scenario=other_scenario)
        first, second = one(), other()
    assert first is not second
    assert second.data.supply_matrix[0, 4] == first.data.supply_matrix[0, 4] + 17
    assert first.data.supply_path is second.data.supply_path is None


@pytest.mark.parametrize("change", ["source", "scenario", "day0", "unknown"])
def test_invalid_task_is_rejected_before_solver_run(small_task, change):
    task, _, _ = small_task
    task = deepcopy(task)
    if change == "source":
        task["source"]["supply"]["sha256"] = "0" * 64
    elif change == "scenario":
        task["scenario_digest"] = "sha256:" + "0" * 64
    elif change == "day0":
        task["shifts"][0] = 5
    else:
        task["guess_recipe"] = True
    builder = load_case_builder(SUPPLY_PROJECT, "production_inner")
    with pytest.raises(ValueError):
        build_case(builder, resource_context={"threads": 1}, component_overrides={"task": task})


def test_case_input_requires_the_exact_outer_identity(small_task):
    task, _, _ = small_task
    case = build_case(load_case_builder(SUPPLY_PROJECT, "production_inner"),
                      resource_context={"threads": 1}, component_overrides={"task": task})
    with pytest.raises(ValueError, match="provenance"):
        case.set_case_inputs({"candidate": [1, 2], "candidate_provenance": {"candidate_token": "different"}})
    with pytest.raises(ValueError, match="candidate"):
        case.set_case_inputs({"candidate": [0, 2], "candidate_provenance": {"candidate_token": task["candidate_token"]}})
    case.set_case_inputs({"candidate": [1, 2], "candidate_provenance": {"candidate_token": task["candidate_token"]}})


def test_real_child_case_is_isolated_budgeted_and_publishes_verified_summary(tmp_path, small_task):
    task, _, _ = small_task
    root = tmp_path / "formal_inner"
    (root / "cases").mkdir(parents=True)
    (root / "cases/__init__.py").write_text("", encoding="utf-8")
    for name in ("production_inner", "supply_adjustment_nested"):
        shutil.copytree(SUPPLY_PROJECT / "cases" / name, root / "cases" / name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "_artifacts"))
    parent = root / "cases/parent"
    parent.mkdir()
    (parent / "__init__.py").write_text("", encoding="utf-8")
    (parent / "build_solver.py").write_text('''
import os, random
import numpy as np
from blackbase.project import CaseRunRequest, ExecutionControl

class Parent:
    def __init__(self, context, task):
        self.resource_context, self.task = context, task
    def run(self):
        random.seed(771)
        np.random.seed(991)
        py_before, np_before = random.getstate(), np.random.get_state()
        children = []
        for index in range(2):
            child = self.case_runtime.invoke(CaseRunRequest(
                project_name="formal_inner", stage_name="inner", case_name="production_inner",
                resource_request={"workers": 1, "threads": 1, "gpus": 0, "memory_mb": 384},
                budget_request={"evaluations": 64, "audit_evaluations": 1},
                control=ExecutionControl(termination={"mode": "cooperative_then_terminate",
                    "grace_seconds": .2, "kill_grace_seconds": .2, "poll_interval_seconds": .02}),
                component_overrides={"task": self.task},
                inputs={"candidate": self.task["shifts"], "candidate_provenance": {
                    "candidate_token": self.task["candidate_token"]}},
            ))
            if not child.ok:
                raise RuntimeError(str(child.as_dict()))
            children.append(child.as_dict())
        np_after = np.random.get_state()
        unchanged = (random.getstate() == py_before and np_after[0] == np_before[0]
            and np.array_equal(np_after[1], np_before[1]) and np_after[2:] == np_before[2:])
        return {"children": children, "parent_rng_unchanged": unchanged, "parent_pid": os.getpid()}

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    return Parent(resource_context, component_overrides["task"])
'''.lstrip(), encoding="utf-8")
    (root / "project_config.py").write_text(f'''
PROJECT_NAME = "formal_inner"
L0 = {{"namespace": "formal_inner", "offer": {{"threads": 1, "gpus": 0}},
      "policy": {{"mode": "strict", "max_workers": 1, "max_threads": 1}},
      "default_request": {{"workers": 1, "threads": 1, "memory_mb": 512}},
      "lease_backend": "sqlite", "lease_path": ".blackbase/leases.sqlite",
      "lease_ttl_seconds": 30, "lease_heartbeat_seconds": 5,
      "budgets": {{"evaluations": 128, "audit_evaluations": 2}}}}
STAGES = [{{"name": "parent", "cases": ["parent"], "timeout_seconds": 90,
           "component_overrides": {{"parent": {{"task": {task!r}}}}}}}]
GROUPS = {{"default": {{"stages": ["parent"]}}}}
'''.lstrip(), encoding="utf-8")
    project = execute_project(root, run_id="production-inner-proof", record=False)
    assert project.ok, project.as_dict()
    parent_result = project.case_results[0]
    assert parent_result.output["parent_rng_unchanged"] is True
    children = parent_result.output["children"]
    summaries = []
    for child in children:
        summary = thaw_wire_mapping(child["output"]["metadata"]["production_summary"])
        summaries.append(summary)
        assert summary["pid"] != parent_result.output["parent_pid"]
        assert summary["termination_requires_isolation"] is True
        assert summary["raw_objectives"][0] == -summary["total_output"]
        assert len(summary["raw_objectives"]) == 5
        assert max(summary["raw_constraints"]) <= 1e-7
        assert summary["production_constraints"]["max_production_per_machine"] == 3000
        assert summary["candidate_token"] == task["candidate_token"]
        assert summary["scenario_digest"] == task["scenario_digest"]
        assert summary["day0_max_abs_delta"] == 0
        assert summary["resource_binding_current"] is True
        assert 0 < summary["algorithm_evaluations"] <= 64
        assert summary["audit_evaluations"] == 1
        assert child["identity"]["parent_case_run_id"] == parent_result.identity.case_run_id
        assert child["identity"]["depth"] == parent_result.identity.depth + 1
        for name, consumed in (("evaluations", summary["algorithm_evaluations"]), ("audit_evaluations", 1)):
            usage = child["budget_usage"][name]
            assert usage["committed"] == usage["charged_to_parent"] == consumed
            assert usage["outstanding_reserved"] == 0
            assert usage["settlement_status"] == "settled"
        binding = ArtifactBinding.from_dict({"ref": child["artifact_refs"]["production_summary"],
                                            "publication": child["artifact_publications"]["production_summary"]})
        reader = ArtifactPublisher.from_resource_context(child["request"]["resource_context"],
            project_run_id=child["identity"]["project_run_id"], case_run_id=child["identity"]["case_run_id"])
        assert json.loads(reader.read_verified(binding)) == summary
    assert summaries[0]["schedule"] == summaries[1]["schedule"]
    assert summaries[0]["raw_objectives"] == summaries[1]["raw_objectives"]
    assert summaries[0]["inner_candidate_token"] != summaries[1]["inner_candidate_token"]
