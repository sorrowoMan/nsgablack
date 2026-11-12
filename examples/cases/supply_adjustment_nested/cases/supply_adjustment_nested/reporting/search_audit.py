"""Audit exact accepted candidate versions without evaluating them again."""
from __future__ import annotations

import hashlib
import json

import numpy as np

from blackbase.resources import ArtifactBinding
from blackbase.wire import thaw_wire_mapping
from cases.production_inner.runtime.task_contract import compute_scenario_digest, verified_source
from cases.supply_adjustment_nested.evaluation.production_case import config_payload


def build_candidate_search_audit(solver, runtime):
    pool, problem = solver.solution_pool, solver.problem
    refs = tuple(pool.select(stage="accepted"))
    if not refs:
        raise RuntimeError("supply candidate audit has no accepted pool versions")
    batch = pool.read(refs)
    raw, violations = pool.read_raw_feedback(refs)
    information = pool.read_raw_feedback_info(refs)
    if (raw.shape != (len(refs), 3) or violations.shape != (len(refs),)
            or len(information) != len(refs) or len(batch.candidate_tokens) != len(refs)
            or not np.all(np.isfinite(raw)) or not np.all(np.isfinite(violations))):
        raise ValueError("supply candidate audit feedback is malformed")
    evaluator = getattr(problem, "inner_runtime_evaluator", None)
    projection = getattr(getattr(evaluator, "projector", None), "__self__", None)
    source = projection.task_source(solver) if getattr(projection, "portable_inputs", False) else solver.supply_source
    current_source = verified_source(source, publisher=runtime.artifact_publisher)
    identity = runtime.identity.as_dict()
    expected_config = thaw_wire_mapping(config_payload(problem.inner_solver_cfg))
    histogram = {str(day): 0 for day in range(problem.days - 1)}
    event_counts = {}
    rows, vectors = [], set()
    for index, ref in enumerate(refs):
        token = ref.candidate_token
        candidate = np.asarray(batch.numeric_matrix[index], dtype=float)
        shifts = problem.decode_shifts(candidate)
        info = thaw_wire_mapping(information[index])
        if (batch.candidate_tokens[index] != token or info.get("candidate_token") != token
                or not np.array_equal(candidate, shifts) or violations[index] > 1e-7):
            raise ValueError("supply candidate audit has mismatched identity or illegal candidate")
        binding = ArtifactBinding.from_dict(info["production_summary_binding"])
        inner = json.loads(runtime.artifact_publisher.read_verified(binding))
        inner_identity = thaw_wire_mapping(info["inner_case_identity"])
        digest = compute_scenario_digest(problem.bom_matrix, problem.apply_shifts(shifts))
        if (inner.get("schema") not in {"supply_adjustment_nested.production_summary/v1", "supply_adjustment_nested.production_summary/v2"}
                or inner.get("candidate_token") != token or not np.array_equal(inner.get("shifts"), shifts)
                or inner.get("scenario_digest") != digest or info.get("scenario_digest") != digest
                or inner.get("identity") != inner_identity
                or inner_identity.get("parent_case_run_id") != identity["case_run_id"]
                or inner_identity.get("project_run_id") != identity["project_run_id"]
                or inner_identity.get("root_run_id") != identity["root_run_id"]
                or inner_identity.get("depth") != identity["depth"] + 1
                or inner.get("inner_config") != expected_config
                or binding.publication.case_run_id != inner_identity.get("case_run_id")
                or binding.publication.project_run_id != identity["project_run_id"]
                or any(inner.get("source", {}).get(name, {}).get("sha256") != current_source[name]["sha256"]
                       for name in ("bom", "supply"))):
            raise ValueError("supply candidate audit child publication disagrees with its proposal")
        schedule = np.asarray(inner["schedule"], dtype=float)
        inner_constraints = np.asarray(inner["raw_constraints"], dtype=float)
        inner_raw = np.asarray(inner["raw_objectives"], dtype=float)
        if (schedule.shape != (problem.bom_matrix.shape[0], problem.days)
                or inner_constraints.shape != (5,) or inner_raw.shape != (5,)
                or not all(np.all(np.isfinite(value)) for value in (schedule, inner_constraints, inner_raw))
                or np.any(schedule < 0) or np.any(inner_constraints > 1e-7)
                or np.any(schedule > problem.inner_solver_cfg.max_production_per_machine)
                or inner_raw[0] != -float(schedule.sum()) or inner["total_output"] != float(schedule.sum())):
            raise ValueError("supply candidate audit child result is malformed")
        moved = np.flatnonzero(shifts).astype(int)
        expected = np.array([-inner["total_output"], len(moved), int(shifts.sum())])
        if not np.allclose(raw[index], expected, rtol=0, atol=1e-7):
            raise ValueError("supply candidate audit original objectives disagree with its actual child")
        usage = thaw_wire_mapping(info["inner_budget_usage"])
        if type(inner["algorithm_evaluations"]) is not int or not 0 < inner["algorithm_evaluations"] <= problem.inner_solver_cfg.max_evaluations:
            raise ValueError("supply candidate audit child exceeded its evaluation budget")
        for name, consumed in (("evaluations", inner["algorithm_evaluations"]), ("audit_evaluations", 1)):
            value = usage[name]
            limit = problem.inner_solver_cfg.max_evaluations if name == "evaluations" else 1
            if (value["limit"] != limit or value["committed"] != consumed or value["charged_to_parent"] != consumed
                    or value["returned_to_parent"] != limit - consumed
                    or value["outstanding_reserved"] != 0 or value["settlement_status"] != "settled"):
                raise ValueError("supply candidate audit budget settlement is inconsistent")
        # This hash measures duplicate decision vectors only. It is never used
        # to resolve candidate identity, version, selection or pool membership.
        vector = np.asarray(shifts, dtype="<i8")
        vector_digest = "sha256:" + hashlib.sha256(str(vector.shape).encode("ascii") + b"\0" + vector.tobytes()).hexdigest()
        vectors.add(vector_digest)
        for day in shifts:
            histogram[str(int(day))] += 1
        for event in moved:
            key = str(int(event))
            event_counts[key] = event_counts.get(key, 0) + 1
        rows.append({"solution_ref": ref.as_dict(), "candidate_token": token,
            "decision_vector_sha256": vector_digest, "moved_indices": moved.tolist(),
            "days": shifts[moved].tolist(), "moved_count": len(moved), "total_advance_days": int(shifts.sum()),
            "raw_objectives": raw[index].tolist(), "raw_constraint_violation": float(violations[index]),
            "production_summary_binding": binding.as_dict(), "inner_case_identity": inner_identity,
            "inner_budget_usage": usage})
    pipeline = solver.representation_pipeline
    components = {}
    for name in ("initializer", "mutator", "repair"):
        component = getattr(pipeline, name, None)
        components[name] = {"class": None if component is None else type(component).__module__ + "." + type(component).__qualname__,
                            "policy": getattr(component, "policy", None)}
    return {"schema": "supply_adjustment_nested.candidate_search_audit/v1", "identity": identity,
            "source": current_source, "coverage": "all_current_accepted_pool_versions",
            "pipeline_components": components,
            "cap_projection_policy": getattr(problem, "cap_projection_policy", None),
            "inner_config": expected_config,
            "dimension": problem.dimension, "outer_evaluations": int(solver.evaluation_count),
            "accepted_candidate_count": len(rows), "unique_vector_count": len(vectors),
            "shift_day_histogram": histogram, "unique_moved_event_count": len(event_counts),
            "event_move_counts": event_counts, "rows": rows}
