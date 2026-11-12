"""读取正式 Artifact 字节并交付轻量核验收据；不复制母池或重做求解。"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import socket

from blackbase.resources import ArtifactBinding, DataRef, coerce_resource_context


def _finite_vector(value, count, label):
    if not isinstance(value, list) or len(value) != count:
        raise ValueError(f"joint plan {label} has an invalid shape")
    if any(type(item) not in (int, float) or not math.isfinite(item) for item in value):
        raise ValueError(f"joint plan {label} must contain finite numeric values")
    return value


def validate_joint_plan(plan, binding):
    if not isinstance(plan, dict) or plan.get("schema") not in {
            "supply_adjustment_nested.joint_summary/v1", "supply_adjustment_nested.joint_summary/v2"}:
        raise ValueError("unsupported joint plan schema")
    identity, producer = plan.get("identity", {}), binding.publication
    if (identity.get("case_run_id") != producer.case_run_id
            or identity.get("project_run_id") != producer.project_run_id):
        raise ValueError("joint plan identity differs from its publication")
    token = plan.get("candidate_token")
    ref = plan.get("accepted_solution_ref", {})
    if (not isinstance(token, str) or not token.strip() or ref.get("candidate_token") != token
            or any(not isinstance(ref.get(name), str) or not ref[name] for name in ("pool_id", "record_id"))
            or type(ref.get("row")) is not int or ref["row"] < 0):
        raise ValueError("joint plan has no exact accepted candidate identity")
    inner = plan.get("inner_case_identity", {})
    if (inner.get("parent_case_run_id") != identity.get("case_run_id")
            or inner.get("project_run_id") != identity.get("project_run_id")
            or inner.get("root_run_id") != identity.get("root_run_id")
            or type(identity.get("depth")) is not int or inner.get("depth") != identity["depth"] + 1
            or not isinstance(inner.get("case_run_id"), str) or not inner["case_run_id"]):
        raise ValueError("joint plan inner lineage is invalid")
    source = plan.get("source", {})
    if set(source) != {"bom", "supply"} or any(
            not isinstance(source[name], dict)
            or re.fullmatch(r"[a-f0-9]{64}", str(source[name].get("sha256", ""))) is None
            for name in ("bom", "supply")):
        raise ValueError("joint plan source digests are invalid")
    if re.fullmatch(r"sha256:[a-f0-9]{64}", str(plan.get("scenario_digest", ""))) is None:
        raise ValueError("joint plan scenario digest is invalid")
    schedule, supply = plan.get("schedule"), plan.get("adjusted_supply")
    if not isinstance(schedule, list) or not schedule or not isinstance(supply, list) or not supply:
        raise ValueError("joint plan schedule and supply must be nonempty matrices")
    for label, matrix in (("schedule", schedule), ("adjusted_supply", supply)):
        for row in matrix:
            if any(value < 0 for value in _finite_vector(row, 31, label)):
                raise ValueError(f"joint plan {label} contains a negative value")
    raw = _finite_vector(plan.get("raw_objectives"), 3, "raw_objectives")
    total = math.fsum(math.fsum(row) for row in schedule)
    if raw[0] != -total or plan.get("total_output") != total:
        raise ValueError("joint plan output differs from its schedule")
    shifts = plan.get("shifts")
    if (not isinstance(shifts, list) or any(type(v) is not int or v < 0 for v in shifts)
            or raw[1] != sum(v > 0 for v in shifts) or raw[2] != sum(shifts)):
        raise ValueError("joint plan movement objectives differ from its shifts")
    if plan.get("day0_max_abs_delta") != 0 or plan.get("material_total_max_abs_delta") != 0:
        raise ValueError("joint plan does not declare fixed today and conserved material totals")
    violation = plan.get("raw_constraint_violation")
    if type(violation) not in (float, int) or not math.isfinite(violation) or violation > 1e-7:
        raise ValueError("joint plan is hard-infeasible")
    return {"candidate_token": token, "scenario_digest": plan["scenario_digest"],
            "source_sha256": {name: source[name]["sha256"] for name in ("bom", "supply")},
            "total_output": total, "machine_count": len(schedule), "material_slots": len(supply),
            "days": 31, "producer_identity": identity}


class ArtifactDeliveryCase:
    def __init__(self, *, resource_context=None, expected_node=None):
        if expected_node is not None and expected_node not in {"data", "risk", "local"}:
            raise ValueError("expected_node must be data, risk or local")
        self.resource_context = coerce_resource_context(resource_context)
        self.expected_node = expected_node
        self.case_runtime = None
        self._refs = {}

    def set_resource_context(self, value):
        self.resource_context = coerce_resource_context(value)
        return self

    def get_resource_context(self):
        return self.resource_context

    def set_case_runtime(self, runtime):
        self.case_runtime = runtime
        return self

    def set_input_artifacts(self, refs):
        self._refs = {name: ref if isinstance(ref, DataRef) else DataRef.from_dict(ref)
                      for name, ref in dict(refs).items()}

    def run(self):
        if self.case_runtime is None:
            raise RuntimeError("artifact delivery requires a formal Case runtime")
        self.case_runtime.checkpoint()
        request = self.case_runtime.request
        bindings = dict(request.input_artifact_bindings)
        if set(bindings) != {"joint_plan"} or set(self._refs) != {"joint_plan"}:
            raise ValueError("artifact delivery requires exactly its joint_plan binding")
        binding = bindings["joint_plan"]
        if not isinstance(binding, ArtifactBinding):
            binding = ArtifactBinding.from_dict(binding)
        if binding.ref != self._refs["joint_plan"]:
            raise ValueError("artifact delivery input ref differs from its publication binding")
        node = os.environ.get("BLACKBASE_JOINT_NODE", "")
        if self.expected_node is not None and node != self.expected_node:
            raise ValueError("artifact delivery ran on a different declared node")
        content = self.case_runtime.artifact_publisher.read_verified(binding)
        verified = validate_joint_plan(json.loads(content), binding)
        self.case_runtime.checkpoint()
        return {"schema": "supply_adjustment_nested.delivery_receipt/v1", **verified,
                "input_sha256": "sha256:" + hashlib.sha256(content).hexdigest(),
                "input_binding": binding.as_dict(), "consumer_identity": self.case_runtime.identity.as_dict(),
                "hostname": socket.gethostname(), "pid": os.getpid(), "node": node,
                "checks": ["publication_and_bytes", "candidate_and_lineage", "source_digest_format",
                           "schedule_and_objectives", "declared_today_and_material_conservation"],
                "evaluations": 0}

    def export_case_result(self, raw_output):
        ref = self.case_runtime.publish_artifact(
            "delivery_receipt", raw_output, serializer="json", kind="artifact-delivery-check")
        return {"status": "succeeded", "delivery": raw_output,
                "artifact_refs": {"delivery_receipt": ref.as_dict()}}
