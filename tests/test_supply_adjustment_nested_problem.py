from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


def _case_dir() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "examples"
        / "cases"
        / "supply_adjustment_nested"
        / "cases"
        / "supply_adjustment_nested"
    )


def _production_case_dir() -> Path:
    return _case_dir().parents[2] / "production_scheduling" / "cases" / "production_scheduling"


def _import_case_modules():
    import importlib.util
    case_dir = _case_dir()
    _load_module = lambda name, rel_path: importlib.util.module_from_spec(
        importlib.util.spec_from_file_location(name, str(case_dir / rel_path))
    )

    # Load via file paths to avoid sys.path pollution
    inner_spec = importlib.util.spec_from_file_location("inner_solver", str(case_dir / "inner_solver.py"))
    inner_mod = importlib.util.module_from_spec(inner_spec)
    sys.modules["inner_solver"] = inner_mod
    inner_spec.loader.exec_module(inner_mod)
    InnerProductionSolverConfig = inner_mod.InnerProductionSolverConfig

    from blackbase.resources import ResourceRequirement

    prob_spec = importlib.util.spec_from_file_location("supply_event_shift_problem", str(case_dir / "problem" / "supply_event_shift_problem.py"))
    prob_mod = importlib.util.module_from_spec(prob_spec)
    sys.modules["supply_event_shift_problem"] = prob_mod
    prob_spec.loader.exec_module(prob_mod)
    SupplyEventShiftProblem = prob_mod.SupplyEventShiftProblem

    audit_spec = importlib.util.spec_from_file_location("supply_adjustment_audit", str(case_dir / "reporting" / "supply_adjustment_audit.py"))
    audit_mod = importlib.util.module_from_spec(audit_spec)
    sys.modules["supply_adjustment_audit"] = audit_mod
    audit_spec.loader.exec_module(audit_mod)
    compute_supply_adjustment_audit = audit_mod.compute_supply_adjustment_audit

    return SupplyEventShiftProblem, compute_supply_adjustment_audit, InnerProductionSolverConfig, ResourceRequirement


def test_supply_shift_cap_prefers_small_day_gap_moves():
    SupplyEventShiftProblem, _, _, _ = _import_case_modules()
    supply = np.zeros((1, 31), dtype=float)
    supply[0, 1] = 100.0
    supply[0, 2] = 100.0
    supply[0, 10] = 10000.0

    problem = SupplyEventShiftProblem(
        base_supply=supply,
        bom_matrix=np.ones((1, 1), dtype=float),
        production_case_dir=_production_case_dir(),
        max_moved_events=2,
    )

    shifts = problem.decode_shifts(np.array([1.0, 2.0, 10.0], dtype=float))

    assert shifts.tolist() == [1, 2, 0]


def test_supply_adjustment_audit_reports_step_gap_metrics():
    SupplyEventShiftProblem, compute_audit, _, _ = _import_case_modules()
    supply = np.zeros((1, 31), dtype=float)
    supply[0, 3] = 50.0
    supply[0, 10] = 70.0

    problem = SupplyEventShiftProblem(
        base_supply=supply,
        bom_matrix=np.ones((1, 1), dtype=float),
        production_case_dir=_production_case_dir(),
        max_moved_events=100,
    )

    audit = compute_audit(problem, np.array([3.0, 8.0], dtype=float))
    summary = audit["move_summary"]

    assert summary["moved_events"] == 2
    assert summary["moved_days_total"] == 11
    assert summary["avg_moved_days"] == 5.5
    assert summary["max_moved_days"] == 8
    assert summary["events_le_7_days"] == 1
    assert summary["events_le_14_days"] == 2
    assert summary["events_gt_21_days"] == 0
    assert summary["moved_quantity_days"] == 710.0


def test_supply_adjustment_problem_keeps_l0_resource_requirements():
    SupplyEventShiftProblem, _, InnerProductionSolverConfig, ResourceRequirement = _import_case_modules()
    supply = np.zeros((1, 31), dtype=float)
    supply[0, 3] = 50.0
    outer_req = ResourceRequirement(threads=1, capabilities=("nested_eval",), memory_mb=256)
    inner_req = ResourceRequirement(threads=3, capabilities=("production_inner",), memory_mb=1024)
    cfg = InnerProductionSolverConfig(parallel_workers=9, resource_requirement=inner_req)

    problem = SupplyEventShiftProblem(
        base_supply=supply,
        bom_matrix=np.ones((1, 1), dtype=float),
        production_case_dir=_production_case_dir(),
        inner_solver_cfg=cfg,
        outer_task_requirement=outer_req,
        inner_resource_requirement=inner_req,
    )

    assert problem.outer_task_requirement.threads == 1
    assert problem.outer_task_requirement.memory_mb == 256
    assert problem.inner_resource_requirement.threads == 3
    assert cfg.effective_resource_requirement().threads == 3
    assert "production_inner" in cfg.effective_resource_requirement().capabilities
