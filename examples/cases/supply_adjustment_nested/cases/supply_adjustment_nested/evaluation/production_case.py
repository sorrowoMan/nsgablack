"""将修复后的供应提案交给正式生产 Case；只消费有发布收据的排程。"""

from __future__ import annotations

from dataclasses import fields
import hashlib
import json
from pathlib import Path

import numpy as np

from blackbase.resources import ArtifactBinding
from blackbase.types import Feedback
from blackbase.wire import thaw_wire_mapping
from nsgablack.core.nested_solver import CaseInnerRuntimeEvaluator
from cases.production_inner.runtime.task_contract import (
    TASK_SCHEMA, PORTABLE_TASK_SCHEMA, compute_scenario_digest, production_code_manifest,
)


def source_descriptor(data):
    return {name: {"path": str(Path(path).resolve()),
                   "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}
            for name, path in (("bom", data.bom_path), ("supply", data.supply_path))}


def config_payload(config):
    # ResourceRequirement contains immutable mappings; export its public wire
    # representation rather than deepcopying a dataclass object graph.
    return {field.name: (value.as_dict() if callable(getattr(value, "as_dict", None)) else value)
            for field in fields(config) for value in (getattr(config, field.name),)}


class ProductionCaseProjection:
    def __init__(self, problem, *, source, portable_inputs=False):
        self.problem = problem
        self.source = source
        self.inner_config = config_payload(problem.inner_solver_cfg)
        self.portable_inputs = bool(portable_inputs)
        self.code_manifest = production_code_manifest(problem.production_case_dir) if self.portable_inputs else None
        self._portable_source = None

    def task_source(self, solver):
        if not self.portable_inputs:
            return self.source
        runtime = getattr(solver, "case_runtime", None)
        bindings = {} if runtime is None else dict(runtime.request.input_artifact_bindings)
        if not {"bom", "supply"} <= set(bindings):
            raise ValueError("portable production requires declared parent BOM and supply Artifact inputs")
        source = {}
        for name in ("bom", "supply"):
            binding = bindings[name]
            if binding.ref.checksum != "sha256:" + self.source[name]["sha256"]:
                raise ValueError("portable production Artifact source differs from the assembled supply model")
            suffix = Path(self.source[name]["path"]).suffix.lower()
            if binding.ref.metadata.get("source_suffix") != suffix:
                raise ValueError("portable production source format differs from the assembled supply model")
            source[name] = {"binding": binding.as_dict(), "sha256": self.source[name]["sha256"],
                            "suffix": suffix}
        if self._portable_source is not None and self._portable_source != source:
            raise ValueError("portable production input bindings changed during the same Case run")
        self._portable_source = source
        return source

    def task_for(self, solver, candidate, context):
        provenance = context.get("_candidate_provenance", {})
        token = provenance.get("candidate_token")
        if not isinstance(token, str) or not token:
            raise ValueError("formal supply evaluation requires the bound outer proposal token")
        shifts = self.problem.decode_shifts(candidate)
        if not np.array_equal(candidate, shifts):
            raise ValueError("production Case must receive the already repaired supply proposal")
        adjusted = self.problem.apply_shifts(shifts)
        source = self.task_source(solver)
        task = {
            "schema": PORTABLE_TASK_SCHEMA if self.portable_inputs else TASK_SCHEMA, "source": source,
            "machines": int(self.problem.bom_matrix.shape[0]),
            "materials": int(self.problem.materials), "days": int(self.problem.days),
            "shifts": shifts.tolist(), "candidate_token": token,
            "scenario_digest": compute_scenario_digest(self.problem.bom_matrix, adjusted),
            "inner_config": self.inner_config, "max_moved_events": self.problem.max_moved_events,
        }
        if self.portable_inputs:
            task["code_manifest"] = self.code_manifest
        else:
            task["production_case_dir"] = str(self.problem.production_case_dir)
        return {"task": task}

    def project(self, solver, candidate, result):
        task = thaw_wire_mapping(result.request.component_overrides)["task"]
        shifts = self.problem.decode_shifts(candidate)
        adjusted = self.problem.apply_shifts(shifts)
        expected_digest = compute_scenario_digest(self.problem.bom_matrix, adjusted)
        provenance = result.request.inputs.get("candidate_provenance", {})
        source = self.task_source(solver)
        if (task["source"] != source or task["inner_config"] != self.inner_config
                or task["scenario_digest"] != expected_digest
                or task["candidate_token"] != provenance.get("candidate_token")
                or not np.array_equal(task["shifts"], shifts)):
            raise ValueError("production result request disagrees with its repaired outer proposal")
        if "production_summary" not in result.artifact_refs or "production_summary" not in result.artifact_publications:
            raise ValueError("production result is missing its authoritative summary publication")
        binding = ArtifactBinding.from_dict({
            "ref": result.artifact_refs["production_summary"].as_dict(),
            "publication": result.artifact_publications["production_summary"].as_dict(),
        })
        summary = json.loads(solver.case_runtime.artifact_publisher.read_verified(binding))
        expected_schema = "supply_adjustment_nested.production_summary/v2" if self.portable_inputs else "supply_adjustment_nested.production_summary/v1"
        if (summary.get("schema") != expected_schema
                or summary.get("candidate_token") != task["candidate_token"]
                or summary.get("scenario_digest") != expected_digest
                or summary.get("source") != source
                or summary.get("inner_config") != self.inner_config
                or summary.get("identity") != result.identity.as_dict()
                or not np.array_equal(summary.get("shifts"), shifts)):
            raise ValueError("published production summary has a different scenario, recipe or identity")
        if self.portable_inputs and summary.get("code_manifest") != self.code_manifest:
            raise ValueError("published production code does not match its frozen task manifest")
        schedule = np.asarray(summary["schedule"], dtype=float)
        raw = np.asarray(summary["raw_objectives"], dtype=float)
        constraints = np.asarray(summary["raw_constraints"], dtype=float)
        if (schedule.shape != (self.problem.bom_matrix.shape[0], self.problem.days)
                or raw.shape != (5,) or not np.all(np.isfinite(schedule))
                or not np.all(np.isfinite(raw)) or not np.all(np.isfinite(constraints))
                or np.any(constraints > 1e-7) or np.any(schedule < 0)
                or np.any(schedule > self.problem.inner_solver_cfg.max_production_per_machine)
                or raw[0] != -float(schedule.sum()) or summary["total_output"] != float(schedule.sum())
                or summary["day0_max_abs_delta"] != 0 or not summary["resource_binding_current"]):
            raise ValueError("published production summary is invalid or hard-infeasible")
        cap = self.problem.inner_solver_cfg.max_evaluations
        if not 0 < summary["algorithm_evaluations"] <= cap:
            raise ValueError("production result exceeds its declared evaluation cap")
        for name, consumed in (("evaluations", summary["algorithm_evaluations"]), ("audit_evaluations", 1)):
            usage = result.budget_usage[name]
            if (usage["committed"] != consumed or usage["charged_to_parent"] != consumed
                    or usage["outstanding_reserved"] != 0 or usage["settlement_status"] != "settled"):
                raise ValueError("production result budget settlement disagrees with actual work")
        return Feedback(
            objectives=np.array([-schedule.sum(), np.count_nonzero(shifts), shifts.sum()], dtype=float),
            info={"candidate_token": task["candidate_token"], "scenario_digest": expected_digest,
                  "production_summary_binding": binding.as_dict(),
                  "inner_case_identity": result.identity.as_dict(),
                  "inner_budget_usage": thaw_wire_mapping(result.budget_usage)},
        )


def build_production_evaluator(problem, *, data, timeout_seconds, max_workers=1, portable_inputs=False):
    projection = ProductionCaseProjection(problem, source=source_descriptor(data), portable_inputs=portable_inputs)
    req = problem.inner_resource_requirement.to_resource_request(label="production_inner")
    return CaseInnerRuntimeEvaluator(
        case_name="production_inner", projector=projection.project,
        component_overrides_factory=projection.task_for, resource_request=req.as_dict(),
        budget_request={"evaluations": problem.inner_solver_cfg.max_evaluations, "audit_evaluations": 1},
        timeout_seconds=timeout_seconds,
        max_workers=max_workers,
        artifact_bindings={"bom": "bom", "supply": "supply"} if portable_inputs else {},
        termination={"mode": "cooperative_then_terminate", "grace_seconds": 2,
                     "kill_grace_seconds": 1, "poll_interval_seconds": .1},
    )
