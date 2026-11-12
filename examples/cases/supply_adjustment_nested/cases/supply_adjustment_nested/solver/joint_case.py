"""Identity-bound delivery of a joint supply and production result."""

from __future__ import annotations

from dataclasses import replace
import json
from typing import Mapping

import numpy as np

from blackbase.resources import ArtifactAuthority, ArtifactBinding, DataRef
from blackbase.wire import thaw_wire_mapping
from nsgablack.adapters import FixedCandidateAdapter
from cases.production_inner.runtime.task_contract import compute_scenario_digest, verified_source
from cases.supply_adjustment_nested.evaluation.production_case import config_payload
from cases.supply_adjustment_nested.reporting.search_audit import build_candidate_search_audit


class JointSupplyCase:
    """A standard Case facade; the wrapped Solver keeps its original run loop."""

    def __init__(self, solver):
        self.solver = solver
        self.problem, self.adapter = solver.problem, solver.adapter
        self.pipeline = self.representation_pipeline = solver.representation_pipeline
        self.plugin_manager, self.evaluation_mediator = solver.plugin_manager, solver.evaluation_mediator
        self.resource_context = solver.resource_context
        self.case_runtime = None
        self._input_artifact_refs = {}
        self._candidate_plan_binding = None
        self._candidate_plan_derived_from = None
        self._candidate_plan_applied = False

    @property
    def resource_binding_audit(self):
        return getattr(self.solver, "resource_binding_audit", {})

    @resource_binding_audit.setter
    def resource_binding_audit(self, value):
        self.solver.resource_binding_audit = value

    @property
    def component_override_audit(self):
        return getattr(self.solver, "component_override_audit", {})

    @component_override_audit.setter
    def component_override_audit(self, value):
        self.solver.component_override_audit = value

    @property
    def context_key_registry(self):
        return getattr(self.solver, "context_key_registry", ())

    @context_key_registry.setter
    def context_key_registry(self, value):
        self.solver.context_key_registry = value

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

    def set_input_artifacts(self, refs):
        """Cache references only; authority is checked after runtime injection."""
        self._input_artifact_refs = {
            name: value if isinstance(value, DataRef) else DataRef.from_dict(value)
            for name, value in dict(refs).items()
        }
        self._candidate_plan_applied = False
        self._candidate_plan_binding = None
        self._candidate_plan_derived_from = None
        return self

    def _apply_candidate_plan(self):
        request = getattr(self.case_runtime, "request", None)
        bindings = {} if request is None else dict(request.input_artifact_bindings)
        if not bindings and not self._input_artifact_refs:
            return
        if self._candidate_plan_applied:
            return
        projection = self.problem.inner_runtime_evaluator.projector.__self__
        source_names = {"bom", "supply"} if projection.portable_inputs else set()
        if source_names:
            projection.task_source(self.solver)
        allowed = source_names | {"candidate_plan"}
        if (set(bindings).difference(allowed) or set(self._input_artifact_refs) != set(bindings)
                or not source_names <= set(bindings)):
            raise ValueError("joint supply inputs disagree with declared source and candidate_plan bindings")
        if "candidate_plan" not in bindings:
            return
        binding = bindings["candidate_plan"]
        if not isinstance(binding, ArtifactBinding):
            binding = ArtifactBinding.from_dict(binding)
        if binding.ref != self._input_artifact_refs["candidate_plan"]:
            raise ValueError("candidate_plan input reference disagrees with its formal binding")
        initializer = self.solver.representation_pipeline.initializer
        setter = getattr(initializer, "set_candidate", None)
        if not isinstance(self.solver.adapter, FixedCandidateAdapter) or not callable(setter):
            raise ValueError("candidate_plan inputs require the supported evaluation-only fixed-candidate assembly")
        if self.solver.generation or self.solver.evaluation_count:
            raise RuntimeError("candidate_plan cannot replace the input of an already started Solver")
        if self.case_runtime is None or self.case_runtime.artifact_publisher is None:
            raise RuntimeError("candidate_plan requires the formal artifact authority")
        plan = json.loads(self.case_runtime.artifact_publisher.read_verified(binding))
        schema = plan.get("schema")
        imported = schema == "supply_adjustment_nested.candidate_plan/v1"
        if not imported and schema not in {"supply_adjustment_nested.joint_summary/v1", "supply_adjustment_nested.joint_summary/v2"}:
            raise ValueError("candidate_plan is not a supported joint supply summary")
        local_source = verified_source(self.solver.supply_source)
        if any(plan.get("source", {}).get(name, {}).get("sha256") != local_source[name]["sha256"]
               for name in ("bom", "supply")):
            raise ValueError("candidate_plan source SHA256 differs from the current supply problem")
        candidate = np.asarray(plan["candidate"], dtype=float)
        shifts = np.asarray(plan["shifts"], dtype=float)
        dimension = (self.problem.dimension,)
        if candidate.shape != dimension or shifts.shape != dimension or not np.all(np.isfinite(candidate)):
            raise ValueError("candidate_plan candidate and shifts have an invalid shape or values")
        decoded = self.problem.decode_shifts(candidate)
        if not np.array_equal(candidate, decoded) or not np.array_equal(shifts, decoded):
            raise ValueError("candidate_plan is illegal under the current today-fixed supply rules")
        adjusted = self.problem.apply_shifts(decoded)
        if (not np.array_equal(np.asarray(plan["adjusted_supply"], dtype=float), adjusted)
                or np.any(adjusted[:, 0] != self.problem.base_supply[:, 0])
                or (not imported and plan.get("day0_max_abs_delta") != 0)
                or plan.get("scenario_digest") != compute_scenario_digest(self.problem.bom_matrix, adjusted)):
            raise ValueError("candidate_plan supply projection or today's inventory disagrees with its candidate")
        producer_identity = plan.get("identity", {})
        if (producer_identity.get("case_run_id") != binding.publication.case_run_id
                or producer_identity.get("project_run_id") != binding.publication.project_run_id):
            raise ValueError("candidate_plan identity disagrees with its producer publication")
        if imported:
            origin = plan.get("derived_from")
            if not isinstance(origin, Mapping) or set(origin) != {"authority", "binding", "sha256"}:
                raise ValueError("imported candidate_plan has no explicit historical input trace")
            authority = ArtifactAuthority.from_dict(origin["authority"])
            historical = ArtifactBinding.from_dict(origin["binding"])
            if (historical.publication.authority_namespace != authority.namespace
                    or origin["sha256"] != historical.ref.checksum):
                raise ValueError("imported candidate_plan historical authority or byte digest disagrees")
        elif (not str(plan.get("candidate_token", "")).strip()
                or plan.get("accepted_solution_ref", {}).get("candidate_token") != plan["candidate_token"]):
            raise ValueError("candidate_plan identity disagrees with its producer publication")
        # Recipe/seed/cap are intentionally not inherited from a search result:
        # this Case's independently granted reevaluation configuration remains authoritative.
        setter(decoded)
        self._candidate_plan_binding = binding
        self._candidate_plan_derived_from = thaw_wire_mapping(plan["derived_from"]) if imported else None
        self._candidate_plan_applied = True

    def run(self, *args, **kwargs):
        self._apply_candidate_plan()
        return self.solver.run(*args, **kwargs)

    def export_case_result(self, raw_output):
        if self.case_runtime is None or self.case_runtime.artifact_publisher is None:
            raise RuntimeError("joint supply delivery requires the formal Case artifact authority")
        result = self.solver.export_case_result(raw_output)
        incumbent = self.solver.get_incumbent()
        if incumbent is None or not incumbent.candidate_token or result.best_candidate_token != incumbent.candidate_token:
            raise RuntimeError("joint supply delivery requires an identity-aligned incumbent")
        pool = self.solver.solution_pool
        matches = tuple(ref for ref in pool.select(stage="accepted")
                        if ref.candidate_token == incumbent.candidate_token)
        if len(matches) != 1:
            raise RuntimeError("joint incumbent must identify exactly one accepted SolutionPool version")
        ref = matches[0]
        batch = pool.read((ref,))
        if (tuple(batch.candidate_tokens) != (incumbent.candidate_token,)
                or not np.array_equal(batch.numeric_matrix[0], incumbent.candidate)):
            raise RuntimeError("accepted incumbent reference disagrees with the authoritative candidate")
        raw_rows, raw_violations = pool.read_raw_feedback((ref,))
        if (np.asarray(raw_rows).shape != (1, 3) or np.asarray(raw_violations).shape != (1,)
                or not np.all(np.isfinite(raw_rows)) or not np.all(np.isfinite(raw_violations))
                or raw_violations[0] > 1e-7):
            raise RuntimeError("accepted joint candidate has no hard-feasible original three-objective feedback")
        information = pool.read_raw_feedback_info((ref,))
        if len(information) != 1 or not isinstance(information[0], Mapping):
            raise RuntimeError("accepted joint candidate has no bound production feedback information")
        info = thaw_wire_mapping(information[0])
        if info.get("candidate_token") != incumbent.candidate_token:
            raise RuntimeError("accepted production feedback token disagrees with the incumbent")
        binding = ArtifactBinding.from_dict(info["production_summary_binding"])
        inner = json.loads(self.case_runtime.artifact_publisher.read_verified(binding))
        summary = self._joint_summary(incumbent, ref, np.asarray(raw_rows[0]), float(raw_violations[0]), info, binding, inner)
        if not bool(self.resource_binding_audit.get("current", False)):
            raise RuntimeError("joint supply delivery resource binding is stale")
        audit = build_candidate_search_audit(self.solver, self.case_runtime)
        refs = dict(result.artifact_refs)
        refs["joint_summary"] = self.case_runtime.publish_artifact(
            "joint_summary", summary, serializer="json", kind="joint-supply-production",
            metadata={"schema": summary["schema"], "scenario_digest": summary["scenario_digest"]},
        )
        refs["candidate_search_audit"] = self.case_runtime.publish_artifact(
            "candidate_search_audit", audit, serializer="json", kind="supply-candidate-search-audit",
            metadata={"schema": audit["schema"], "accepted_candidate_count": audit["accepted_candidate_count"]})
        # Matrices remain in the Artifact; only the delivery index is in the result.
        index = {name: summary[name] for name in (
            "schema", "candidate_token", "accepted_solution_ref", "scenario_digest", "raw_objectives",
            "total_output", "moved_events", "total_advance_days", "day0_max_abs_delta",
            "inner_case_identity", "inner_budget_usage", "outer_steps", "outer_evaluations",
        )}
        return replace(result, artifact_refs=refs, metadata={**dict(result.metadata), "joint_summary": index})

    def _joint_summary(self, incumbent, ref, raw_objectives, raw_violation, info, binding, inner):
        if not isinstance(inner, Mapping) or inner.get("schema") not in {
                "supply_adjustment_nested.production_summary/v1", "supply_adjustment_nested.production_summary/v2"}:
            raise ValueError("unsupported published production summary")
        shifts = self.problem.decode_shifts(incumbent.candidate)
        adjusted = self.problem.apply_shifts(shifts)
        scenario_digest = compute_scenario_digest(self.problem.bom_matrix, adjusted)
        inner_identity = thaw_wire_mapping(info["inner_case_identity"])
        identity = self.case_runtime.identity.as_dict()
        expected_config = thaw_wire_mapping(config_payload(self.problem.inner_solver_cfg))
        if (inner.get("candidate_token") != incumbent.candidate_token
                or inner.get("scenario_digest") != scenario_digest or info.get("scenario_digest") != scenario_digest
                or not np.array_equal(inner.get("shifts"), shifts)
                or inner.get("inner_config") != expected_config
                or inner.get("identity") != inner_identity
                or inner_identity.get("parent_case_run_id") != identity["case_run_id"]
                or inner_identity.get("root_run_id") != identity["root_run_id"]
                or inner_identity.get("project_run_id") != identity["project_run_id"]
                or inner_identity.get("depth") != identity["depth"] + 1
                or binding.publication.case_run_id != inner_identity.get("case_run_id")
                or binding.publication.project_run_id != inner_identity.get("project_run_id")):
            raise ValueError("published production result disagrees with joint scenario, recipe or lineage")
        source = verified_source(inner["source"], publisher=self.case_runtime.artifact_publisher)
        day0_delta = adjusted[:, 0] - self.problem.base_supply[:, 0]
        conservation_delta = adjusted.sum(axis=1) - self.problem.base_supply.sum(axis=1)
        if (np.any(day0_delta != 0) or np.max(np.abs(conservation_delta)) > 1e-7
                or inner.get("day0_max_abs_delta") != 0):
            raise ValueError("joint supply result changes today or fails material conservation")
        schedule = np.asarray(inner["schedule"], dtype=float)
        inner_objectives = np.asarray(inner["raw_objectives"], dtype=float)
        inner_constraints = np.asarray(inner["raw_constraints"], dtype=float)
        if (schedule.shape != (self.problem.bom_matrix.shape[0], self.problem.days)
                or inner_objectives.shape != (5,) or inner_constraints.shape != (5,)
                or not all(np.all(np.isfinite(values)) for values in (schedule, inner_objectives, inner_constraints))
                or np.any(schedule < 0) or np.any(schedule > self.problem.inner_solver_cfg.max_production_per_machine)
                or np.any(inner_constraints > 1e-7) or not inner.get("resource_binding_current")):
            raise ValueError("joint production schedule is malformed or hard-infeasible")
        total_output = float(schedule.sum())
        projected = np.array([-total_output, np.count_nonzero(shifts), shifts.sum()], dtype=float)
        if (inner_objectives[0] != -total_output or inner["total_output"] != total_output
                or not np.allclose(raw_objectives, projected, rtol=0, atol=1e-7)):
            raise ValueError("joint raw feedback disagrees with its bound production schedule")
        usage = thaw_wire_mapping(info["inner_budget_usage"])
        consumed_evaluations = inner["algorithm_evaluations"]
        cap = self.problem.inner_solver_cfg.max_evaluations
        if type(consumed_evaluations) is not int or not 0 < consumed_evaluations <= cap or inner["audit_evaluations"] != 1:
            raise ValueError("joint production work exceeds its declared budget")
        for name, consumed, limit in (("evaluations", consumed_evaluations, cap), ("audit_evaluations", 1, 1)):
            item = usage[name]
            if (item["limit"] != limit or item["committed"] != consumed or item["charged_to_parent"] != consumed
                    or item["outstanding_reserved"] != 0 or item["returned_to_parent"] != limit - consumed
                    or item["settlement_status"] != "settled"):
                raise ValueError("joint production budget settlement disagrees with the sealed work")
        return {
            "schema": ("supply_adjustment_nested.joint_summary/v2"
                       if inner["schema"].endswith("/v2") else "supply_adjustment_nested.joint_summary/v1"), "identity": identity,
            "candidate_token": incumbent.candidate_token, "accepted_solution_ref": ref.as_dict(),
            "candidate": np.asarray(incumbent.candidate).tolist(), "shifts": shifts.tolist(),
            "scenario_digest": scenario_digest, "source": source,
            "adjusted_supply": adjusted.tolist(), "raw_objectives": raw_objectives.tolist(),
            "raw_constraint_violation": raw_violation, "selection_objectives": incumbent.objectives.tolist(),
            "total_output": total_output, "moved_events": int(np.count_nonzero(shifts)),
            "total_advance_days": int(shifts.sum()), "day0_max_abs_delta": 0.0,
            "material_total_max_abs_delta": float(np.max(np.abs(conservation_delta))),
            "schedule": schedule.tolist(), "production_raw_objectives": inner_objectives.tolist(),
            "production_raw_constraints": inner_constraints.tolist(), "inner_config": expected_config,
            "inner_case_identity": inner_identity, "inner_candidate_token": inner["inner_candidate_token"],
            "inner_evaluation_id": inner["inner_evaluation_id"], "inner_budget_usage": usage,
            "production_summary_binding": binding.as_dict(), "production_summary": dict(inner),
            "candidate_plan_binding": None if self._candidate_plan_binding is None else self._candidate_plan_binding.as_dict(),
            "candidate_plan_derived_from": self._candidate_plan_derived_from,
            "outer_steps": int(self.solver.generation), "outer_evaluations": int(self.solver.evaluation_count),
        }
