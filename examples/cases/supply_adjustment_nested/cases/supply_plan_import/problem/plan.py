"""按当前同源数据重建供应变换，不继承旧排程或评分。"""
from __future__ import annotations

import importlib
from pathlib import Path

import numpy as np

from blackbase.project import case_import_context
from cases.artifact_delivery_check.solver.case import validate_joint_plan
from cases.production_inner.runtime.task_contract import compute_scenario_digest


def prepare_candidate_plan(plan, binding, *, production_case_dir=None):
    validate_joint_plan(plan, binding)
    project = Path(__file__).resolve().parents[3]
    with case_import_context(project, "supply_adjustment_nested"):
        runtime = importlib.import_module("runtime")
        case_dir = runtime.resolve_production_case_dir(production_case_dir)
        data = runtime.load_production_case_data(
            bom_path=None, supply_path=None, machines=len(plan["schedule"]),
            materials=len(plan["adjusted_supply"]), days=31, production_case_dir=case_dir)
        descriptor = importlib.import_module("evaluation.production_case").source_descriptor(data)
        problem_type = importlib.import_module("problem").SupplyEventShiftProblem
        problem = problem_type(base_supply=data.supply_matrix, bom_matrix=data.bom_matrix,
            production_case_dir=case_dir, max_moved_events=100)
    if any(plan["source"][name]["sha256"] != descriptor[name]["sha256"] for name in ("bom", "supply")):
        raise ValueError("imported plan source SHA256 differs from current canonical production data")
    candidate = np.asarray(plan["candidate"], dtype=float)
    shifts = np.asarray(plan["shifts"], dtype=float)
    if candidate.shape != (problem.dimension,) or shifts.shape != candidate.shape or not np.all(np.isfinite(candidate)):
        raise ValueError("imported plan has an invalid candidate shape or values")
    decoded = problem.decode_shifts(candidate)
    if not np.array_equal(candidate, decoded) or not np.array_equal(shifts, decoded):
        raise ValueError("imported plan is illegal under current today-fixed supply rules")
    adjusted = problem.apply_shifts(decoded)
    if (not np.array_equal(np.asarray(plan["adjusted_supply"], dtype=float), adjusted)
            or np.any(adjusted[:, 0] != data.supply_matrix[:, 0])
            or not np.allclose(adjusted.sum(axis=1), data.supply_matrix.sum(axis=1), rtol=0, atol=1e-7)
            or compute_scenario_digest(data.bom_matrix, adjusted) != plan["scenario_digest"]):
        raise ValueError("imported plan supply, today inventory or scenario disagrees with its candidate")
    return {"source": descriptor, "candidate": candidate.tolist(), "shifts": decoded.tolist(),
            "adjusted_supply": adjusted.tolist(), "scenario_digest": plan["scenario_digest"]}
