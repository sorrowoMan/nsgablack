"""Strict formal Case facade around the canonical production Solver."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import os
import socket

import numpy as np

from blackbase.resources import ArtifactBinding, BudgetAccount, coerce_resource_context
from blackbase.wire import thaw_wire_mapping
from blackbase.project import case_import_context
from ..runtime.task_contract import PORTABLE_TASK_SCHEMA, prepare_task, production_code_manifest, verified_source


class PortableProductionInnerCase:
    """Build only after declared Artifact inputs and runtime have been bound.

    Field inspection and build-check never download sources or create a Solver.
    """
    def __init__(self, task, *, resource_context=None):
        self._task = deepcopy(thaw_wire_mapping(task))
        self._resource_context = coerce_resource_context(resource_context)
        self._case = None
        self.case_runtime = None
        self._inputs = None
        self._refs = {}
        self.resource_binding_audit = {}

    def __getattr__(self, name):
        case = self.__dict__.get("_case")
        if case is None:
            raise AttributeError(name)
        return getattr(case, name)

    def set_resource_context(self, context):
        self._resource_context = coerce_resource_context(context)
        if self._case is not None:
            self._case.set_resource_context(context)
        return self

    def get_resource_context(self):
        return self._resource_context

    def set_input_artifacts(self, refs):
        self._refs = dict(refs)
        return self

    def set_case_inputs(self, inputs):
        self._inputs = thaw_wire_mapping(inputs)
        return self

    def set_case_runtime(self, runtime):
        self.case_runtime = runtime
        return self

    def _build(self):
        if self._case is not None:
            return self._case
        runtime = self.case_runtime
        if runtime is None or self._inputs is None:
            raise RuntimeError("portable production requires its formal runtime and invocation inputs")
        bindings = dict(runtime.request.input_artifact_bindings)
        if set(bindings) != {"bom", "supply"} or set(self._refs) != {"bom", "supply"}:
            raise ValueError("portable production requires exactly the declared BOM and supply Artifact inputs")
        for name in ("bom", "supply"):
            declared = ArtifactBinding.from_dict(self._task["source"][name]["binding"])
            if declared != bindings[name] or declared.ref != self._refs[name]:
                raise ValueError("portable production task source disagrees with its declared input binding")
        prepared = prepare_task(self._task, publisher=runtime.artifact_publisher)
        solver, problem = prepared.build_solver(resource_context=self._resource_context.as_dict())
        case = ProductionInnerCase(solver, problem, prepared)
        case.set_case_runtime(runtime)
        case.set_case_inputs(self._inputs)
        self._case = case
        self.resource_binding_audit = case.resource_binding_audit
        return case

    def run(self):
        return self._build().run()

    def export_case_result(self, raw_output):
        return self._build().export_case_result(raw_output)

    def close(self):
        # An unbuilt facade owns no provider, executor or temporary directory.
        close = getattr(self._case.solver, "close", None) if self._case is not None else None
        if callable(close):
            close()


class ProductionInnerCase:
    def __init__(self, solver, problem, prepared):
        self.solver, self.problem, self.prepared = solver, problem, prepared
        self.adapter = solver.adapter
        self.pipeline = self.representation_pipeline = solver.representation_pipeline
        self.plugin_manager, self.evaluation_mediator = solver.plugin_manager, solver.evaluation_mediator
        self.resource_context = solver.resource_context
        self.case_runtime = None
        self.case_inputs = None

    @property
    def resource_binding_audit(self):
        return getattr(self.solver, "resource_binding_audit", {})

    @resource_binding_audit.setter
    def resource_binding_audit(self, value):
        self.solver.resource_binding_audit = value

    def set_resource_context(self, value):
        self.solver.set_resource_context(value)
        self.resource_context = self.solver.resource_context
        return self

    def get_resource_context(self):
        return self.solver.get_resource_context()

    def set_case_runtime(self, runtime):
        self.case_runtime = runtime
        self.solver.set_case_runtime(runtime)
        return self

    def set_case_inputs(self, inputs):
        inputs = thaw_wire_mapping(inputs)
        allowed = {"candidate", "context", "outer_generation", "outer_individual_id", "candidate_provenance"}
        if "candidate" not in inputs or set(inputs).difference(allowed):
            raise ValueError("production_inner requires the declared candidate invocation inputs")
        candidate = np.asarray(inputs["candidate"], dtype=float)
        decoded = self.prepared.outer_problem.decode_shifts(candidate)
        if candidate.shape != decoded.shape or not np.array_equal(decoded, self.prepared.task["shifts"]):
            raise ValueError("invoked candidate disagrees with the prepared production task")
        provenance = inputs.get("candidate_provenance")
        if not isinstance(provenance, dict) or provenance.get("candidate_token") != self.prepared.task["candidate_token"]:
            raise ValueError("invoked outer candidate provenance disagrees with task token")
        self.case_inputs = deepcopy(dict(inputs))

    def run(self):
        if self.case_runtime is None or self.case_inputs is None:
            raise RuntimeError("production_inner requires a complete formal Case invocation")
        if not self.case_runtime.control.termination.requires_isolation:
            raise RuntimeError("legacy production operators require formal child process isolation")
        self.case_runtime.checkpoint()
        case_dir = self.prepared.production_case_dir
        with case_import_context(case_dir.parents[1], case_dir.name):
            return self.solver.run()

    def export_case_result(self, raw_output):
        case_dir = self.prepared.production_case_dir
        with case_import_context(case_dir.parents[1], case_dir.name):
            return self._export_case_result(raw_output)

    def _export_case_result(self, raw_output):
        if self.case_runtime is None or self.case_inputs is None:
            raise RuntimeError("production_inner cannot publish without its formal runtime and inputs")
        result = self.solver.export_case_result(raw_output)
        incumbent = self.solver.get_incumbent()
        if incumbent is None or not incumbent.candidate_token or result.best_candidate_token != incumbent.candidate_token:
            raise RuntimeError("production_inner has no identity-aligned authoritative incumbent")
        schedule = np.asarray(self.problem.decode_schedule(incumbent.candidate), dtype=float)
        if schedule.shape != (self.problem.machines, self.problem.days) or not np.all(np.isfinite(schedule)):
            raise RuntimeError("production_inner incumbent schedule is invalid")
        context = self.get_resource_context().as_dict()
        metadata = context.get("metadata", {})
        if ("audit_evaluations" not in metadata.get("budget_handles", {})
                and "audit_evaluations" not in metadata.get("budget_authority", {}).get("budgets", {})):
            raise RuntimeError("production_inner requires an explicit audit_evaluations budget")
        account = BudgetAccount.from_resource_context("audit_evaluations", context)
        claim = account.reserve(1)
        try:
            account.consume(claim, 1)
            raw_objectives = np.asarray(self.problem.evaluate(incumbent.candidate), dtype=float).reshape(-1)
            raw_constraints = np.asarray(self.problem.evaluate_constraints(incumbent.candidate), dtype=float).reshape(-1)
        finally:
            account.complete(claim)
        if raw_objectives.shape != (5,) or not np.all(np.isfinite(raw_objectives)) or not np.all(np.isfinite(raw_constraints)):
            raise RuntimeError("production_inner requires the original five finite raw objectives and constraints")
        if (np.any(schedule < 0) or np.any(schedule > self.problem.constraints.max_production_per_machine)
                or np.any(raw_constraints > 1e-7)):
            raise RuntimeError("production_inner cannot publish a hard-infeasible schedule")
        verified_source(self.prepared.task["source"], publisher=self.case_runtime.artifact_publisher)
        model_path = self.prepared.production_case_dir / "problem/production_problem.py"
        portable = self.prepared.task["schema"] == PORTABLE_TASK_SCHEMA
        if portable and production_code_manifest(self.prepared.production_case_dir) != self.prepared.task["code_manifest"]:
            raise ValueError("production code changed after the task's frozen manifest was checked")
        summary = {
            "schema": ("supply_adjustment_nested.production_summary/v2"
                       if self.prepared.task["schema"] == PORTABLE_TASK_SCHEMA
                       else "supply_adjustment_nested.production_summary/v1"),
            "candidate_token": self.prepared.task["candidate_token"],
            "scenario_digest": self.prepared.task["scenario_digest"],
            "source": deepcopy(self.prepared.task["source"]),
            "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
            "shifts": list(self.prepared.task["shifts"]),
            "schedule": schedule.tolist(), "raw_objectives": raw_objectives.tolist(),
            "raw_constraints": raw_constraints.tolist(), "total_output": float(schedule.sum()),
            "selection_objectives": incumbent.objectives.tolist(),
            "inner_candidate_token": incumbent.candidate_token, "inner_evaluation_id": incumbent.evaluation_id,
            "inner_selection_policy": incumbent.policy_id,
            "algorithm_steps": int(self.solver.generation), "algorithm_evaluations": int(self.solver.evaluation_count),
            "audit_evaluations": 1, "inner_config": deepcopy(self.prepared.task["inner_config"]),
            "identity": self.case_runtime.identity.as_dict(), "resource_grant": dict(self.resource_context.grant),
            "hostname": socket.gethostname(), "pid": os.getpid(), "parent_pid": os.getppid(),
            "production_constraints": asdict(self.problem.constraints),
            "resource_binding_current": bool(self.resource_binding_audit.get("current", False)),
            "termination_requires_isolation": bool(self.case_runtime.control.termination.requires_isolation),
            "day0_max_abs_delta": float(np.max(np.abs(self.prepared.adjusted_supply[:, 0] - self.prepared.outer_problem.base_supply[:, 0]))),
        }
        if not summary["resource_binding_current"]:
            raise RuntimeError("production_inner resource binding is stale")
        if portable:
            summary["code_manifest"] = deepcopy(self.prepared.task["code_manifest"])
        evaluator = getattr(self.solver, "parallel_evaluator", None)
        dispatch_stats = getattr(evaluator, "last_dispatch_stats", None)
        if dispatch_stats is not None:
            # Runtime observations, distinct from configured worker counts.
            # This is the final raw batch, not the whole-run throughput.
            summary["parallel_last_dispatch"] = thaw_wire_mapping(dispatch_stats)
        aggregate_stats = getattr(evaluator, "raw_dispatch_stats", None)
        if aggregate_stats is not None:
            summary["parallel_raw_dispatch"] = thaw_wire_mapping(aggregate_stats)
        refs = dict(result.artifact_refs)
        refs["production_summary"] = self.case_runtime.publish_artifact(
            "production_summary", summary, serializer="json", kind="production-scheduling-summary",
            metadata={"schema": summary["schema"], "scenario_digest": summary["scenario_digest"]},
        )
        return replace(result, artifact_refs=refs, metadata={**dict(result.metadata), "production_summary": summary})
