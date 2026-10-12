"""Outer Case wrapper owning Artifact inputs and final topology evidence."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from blackbase.resources import FilesystemArtifactPublicationLedger

from ..adapter import describe_topology
from ..reporting.audit import evaluate_invariants


class OuterSearchCase:
    def __init__(self, solver, *, component_overrides: Mapping[str, Any] | None = None) -> None:
        self.solver = solver
        self.problem = solver.problem
        self.adapter = solver.adapter
        self.representation_pipeline = solver.representation_pipeline
        self.pipeline = self.representation_pipeline
        self.plugin_manager = solver.plugin_manager
        self.evaluation_mediator = solver.evaluation_mediator
        self.resource_context = solver.resource_context
        self.component_override_audit = dict(component_overrides or {})
        self.input_artifacts = {}
        self.case_runtime = None

    def set_resource_context(self, context):
        self.solver.set_resource_context(context)
        self.resource_context = self.solver.resource_context
        return self

    def get_resource_context(self):
        return self.solver.get_resource_context()

    def set_case_runtime(self, runtime):
        self.case_runtime = runtime
        self.solver.set_case_runtime(runtime)
        self.problem.set_case_runtime(runtime)
        return self

    def set_input_artifacts(self, refs):
        self.input_artifacts = dict(refs)

    def run(self):
        required = {"solver_baseline", "trainer_baseline"}
        missing = sorted(required.difference(self.input_artifacts))
        if missing:
            raise RuntimeError(f"outer_search is missing authoritative inputs: {missing}")
        return self.solver.run(max_steps=4, max_step_attempts=8)

    def export_case_result(self, raw_output):
        result = self.solver.export_case_result(raw_output)
        nested_records = self.problem.invocation_records()
        publications = {}
        for name, binding in self.case_runtime.request.input_artifact_bindings.items():
            receipt = binding.publication
            ledger = FilesystemArtifactPublicationLedger(
                self.case_runtime.artifact_publisher.authority,
                project_run_id=receipt.project_run_id,
                case_run_id=receipt.case_run_id,
            )
            publications[name] = {"receipt": receipt.as_dict(), "verified": ledger.verify(receipt)}
        topology_audit = {
            "schema": "nsgablack.super_topology_audit/v2",
            "outer_identity": self.case_runtime.identity.as_dict(),
            "outer_cancellation": self.case_runtime.control.cancellation.as_dict(),
            "outer_resource_lineage": {
                "namespace": self.resource_context.namespace,
                "lease_id": self.resource_context.lease.get("lease_id"),
                "fencing_token": self.resource_context.lease.get("fencing_token"),
            },
            "outer_resource_grant": dict(self.resource_context.grant),
            "outer_resource_binding_current": bool(
                dict(getattr(self, "resource_binding_audit", {}) or {}).get(
                    "current",
                    False,
                )
            ),
            "baseline_inputs": {
                name: ref.as_dict() for name, ref in sorted(self.input_artifacts.items())
            },
            "baseline_publications": publications,
            "dag": dict(self.case_runtime.request.metadata.get("dag", {})),
            "adapter_topology": describe_topology(),
            "candidate_trainer_calls": len(nested_records),
            "nested_calls": nested_records,
        }
        topology_audit["invariants"] = evaluate_invariants(topology_audit)
        report_ref = self.case_runtime.publish_artifact(
            "topology_report",
            topology_audit,
            kind="orchestration-audit",
            metadata={
                "schema": topology_audit["schema"],
                "nested_call_count": len(nested_records),
            },
        )
        return replace(
            result,
            artifact_refs={**dict(result.artifact_refs), "topology_report": report_ref},
            metadata={**dict(result.metadata), "super_topology": topology_audit},
        )
