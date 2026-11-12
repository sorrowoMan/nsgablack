"""正式两 Case 发布/消费验收，不调用生产优化器。"""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import shutil

import pytest

from blackbase.project import case_import_context, execute_project
from blackbase.resources import ArtifactBinding, ArtifactPublisher
from blackbase.wire import thaw_wire_mapping

PROJECT = Path(__file__).resolve().parents[1] / "examples/cases/supply_adjustment_nested"


def _plan():
    schedule = [[0] * 31 for _ in range(2)]
    schedule[0][1], schedule[1][2] = 50, 70
    supply = [[100] * 31 for _ in range(3)]
    return {"schema": "supply_adjustment_nested.joint_summary/v1",
            "candidate_token": "proposal-token", "accepted_solution_ref": {
                "pool_id": "pool-1", "record_id": "record-1", "row": 0, "candidate_token": "proposal-token"},
            "source": {name: {"path": "/producer-only/" + name, "sha256": digit * 64}
                       for name, digit in (("bom", "a"), ("supply", "b"))},
            "scenario_digest": "sha256:" + "c" * 64,
            "schedule": schedule, "adjusted_supply": supply, "shifts": [1, 2],
            "raw_objectives": [-120, 2, 3], "total_output": 120,
            "day0_max_abs_delta": 0, "material_total_max_abs_delta": 0, "raw_constraint_violation": 0}


def _project(tmp_path, plan):
    root = tmp_path / "delivery"
    (root / "cases/producer").mkdir(parents=True)
    (root / "cases/__init__.py").write_text("", encoding="utf-8")
    (root / "cases/producer/__init__.py").write_text("", encoding="utf-8")
    shutil.copytree(PROJECT / "cases/artifact_delivery_check", root / "cases/artifact_delivery_check",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (root / "cases/producer/build_solver.py").write_text('''
from copy import deepcopy

class Producer:
    def __init__(self, context, plan): self.resource_context, self.plan = context, plan
    def run(self):
        plan = deepcopy(self.plan)
        plan['identity'] = self.case_runtime.identity.as_dict()
        plan['inner_case_identity'] = self.case_runtime.identity.child().as_dict()
        self.case_runtime.publish_artifact('joint_summary', plan, serializer='json')
        return {'published': True}

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    return Producer(resource_context, component_overrides['plan'])
'''.lstrip(), encoding="utf-8")
    (root / "project_config.py").write_text(f'''
PROJECT_NAME = 'delivery'
L0 = {{'namespace': 'delivery', 'offer': {{'threads': 1, 'gpus': 0}},
      'policy': {{'mode': 'strict', 'max_workers': 1, 'max_threads': 1}},
      'default_request': {{'workers': 1, 'threads': 1, 'memory_mb': 128}},
      'lease_backend': 'sqlite', 'lease_path': '.blackbase/leases.sqlite'}}
STAGES = [{{'name': 'produce', 'cases': ['producer'],
           'component_overrides': {{'producer': {{'plan': {plan!r}}}}}}},
          {{'name': 'read', 'cases': ['artifact_delivery_check'],
           'input_artifacts': {{'artifact_delivery_check': {{'joint_plan': 'produce.producer.joint_summary'}}}}}}]
GROUPS = {{'default': {{'stages': ['produce','read']}}}}
'''.lstrip(), encoding="utf-8")
    return root


def test_formal_delivery_publishes_a_small_receipt_without_opening_producer_paths(tmp_path):
    result = execute_project(_project(tmp_path, _plan()), run_id="delivery-check", record=False)
    assert result.ok, result.as_dict()
    producer, consumer = result.case_results
    receipt = consumer.output["delivery"]
    assert receipt["evaluations"] == 0
    assert receipt["total_output"] == 120
    assert receipt["machine_count"] == 2 and receipt["material_slots"] == 3 and receipt["days"] == 31
    assert receipt["candidate_token"] == "proposal-token"
    assert receipt["producer_identity"]["case_run_id"] == producer.identity.case_run_id
    assert receipt["consumer_identity"]["case_run_id"] == consumer.identity.case_run_id
    assert receipt["hostname"] and receipt["pid"] > 0
    assert "schedule" not in receipt and "adjusted_supply" not in receipt
    binding = ArtifactBinding(consumer.artifact_refs["delivery_receipt"],
                              consumer.artifact_publications["delivery_receipt"])
    reader = ArtifactPublisher.from_resource_context(consumer.request.resource_context,
        project_run_id=consumer.identity.project_run_id, case_run_id=consumer.identity.case_run_id)
    assert json.loads(reader.read_verified(binding)) == thaw_wire_mapping(receipt)
    upstream = ArtifactBinding(producer.artifact_refs["joint_summary"],
                               producer.artifact_publications["joint_summary"])
    import hashlib
    assert receipt["input_sha256"] == "sha256:" + hashlib.sha256(reader.read_verified(upstream)).hexdigest()


@pytest.mark.parametrize("change", ["output", "today", "conservation", "token", "source", "lineage"])
def test_delivery_rejects_inconsistent_sealed_payload(change):
    with case_import_context(PROJECT, "artifact_delivery_check"):
        validate = importlib.import_module("solver.case").validate_joint_plan
    from types import SimpleNamespace
    plan = deepcopy(_plan())
    plan["identity"] = {"case_run_id": "producer", "project_run_id": "project", "root_run_id": "root", "depth": 0}
    plan["inner_case_identity"] = {"case_run_id": "inner", "project_run_id": "project", "root_run_id": "root",
                                    "parent_case_run_id": "producer", "depth": 1}
    binding = SimpleNamespace(publication=SimpleNamespace(case_run_id="producer", project_run_id="project"))
    if change == "output": plan["raw_objectives"][0] = -121
    elif change == "today": plan["day0_max_abs_delta"] = 1
    elif change == "conservation": plan["material_total_max_abs_delta"] = -1
    elif change == "token": plan["accepted_solution_ref"]["candidate_token"] = "different"
    elif change == "source": plan["source"]["bom"]["sha256"] = "guess"
    else: plan["inner_case_identity"]["parent_case_run_id"] = "another-parent"
    with pytest.raises(ValueError):
        validate(plan, binding)
