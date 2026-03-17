from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class InnerProductionSolverConfig:
    pop_size: int = 16
    generations: int = 3
    max_active_machines_per_day: int = 8
    max_production_per_machine: float = 3000.0
    parallel: bool = False
    parallel_backend: str = "thread"
    parallel_workers: int = 1
    parallel_chunk_size: int | None = None
    parallel_strict: bool = False
    parallel_thread_bias_isolation: str = "disable_cache"


def build_inner_production_solver(
    *,
    bom_matrix: np.ndarray,
    supply_matrix: np.ndarray,
    production_case_dir: Path,
    cfg: InnerProductionSolverConfig,
):
    """Build a standard production scheduling solver for nested runtime."""
    import sys

    case_dir = Path(production_case_dir).resolve()
    if str(case_dir) not in sys.path:
        sys.path.insert(0, str(case_dir))

    for name in (
        "problem",
        "plugins",
        "adapter",
        "bias",
        "pipeline",
        "refactor_data",
        "build_solver",
        "working_integrated_optimizer",
    ):
        mod = sys.modules.get(name)
        mod_file = str(getattr(mod, "__file__", "") or "")
        if mod is not None and str(case_dir) not in mod_file:
            sys.modules.pop(name, None)

    from refactor_data import ProductionData
    from problem import ProductionConstraints, ProductionSchedulingProblem
    from build_solver import build_multi_agent_solver

    bom = np.asarray(bom_matrix, dtype=float)
    supply = np.asarray(supply_matrix, dtype=float)
    if bom.ndim != 2 or supply.ndim != 2:
        raise ValueError("bom_matrix/supply_matrix must be 2D arrays")

    machines, materials = bom.shape
    days = int(supply.shape[1])

    data = ProductionData(
        machines=int(machines),
        materials=int(materials),
        days=int(days),
        bom_matrix=np.asarray(bom > 0.0, dtype=bool),
        supply_matrix=np.asarray(supply, dtype=float),
        machine_weights=np.ones(int(machines), dtype=float),
        bom_path=None,
        supply_path=None,
    )

    constraints = ProductionConstraints(
        max_machines_per_day=int(cfg.max_active_machines_per_day),
        min_machines_per_day=5,
        min_production_per_machine=50,
        max_production_per_machine=int(cfg.max_production_per_machine),
        shortage_unit_penalty=1.0,
        include_penalty_objective=True,
        penalty_objective_scale=0.001,
    )
    problem = ProductionSchedulingProblem(data=data, constraints=constraints)

    class _Args:
        pass

    a = _Args()
    a.material_cap_ratio = 2.0
    a.daily_floor_ratio = 0.7
    a.donor_keep_ratio = 0.6
    a.daily_cap_ratio = 1.0
    a.reserve_ratio = 0.2
    a.coverage_bonus = 0.3
    a.budget_mode = "average"
    a.smooth_strength = 0.8
    a.smooth_passes = 1
    a.no_pipeline = False
    a.no_bias = False
    a.coverage_reward = 0.03
    a.smoothness_penalty = 0.01
    a.variance_penalty = 0.03
    a.pop_size = int(max(8, cfg.pop_size))
    a.explorer_adapter = "moead"
    a.exploiter_adapter = "vns"
    a.seed = 42
    a.moead_pop_size = int(max(16, cfg.pop_size))
    a.moead_neighborhood = 10
    a.moead_nr = 2
    a.moead_delta = 0.9
    a.vns_batch_size = int(max(8, cfg.pop_size // 2))
    a.vns_k_max = 3
    a.vns_base_sigma = 0.2
    a.adapt_interval = 8
    a.comm_interval = 5
    a.generations = int(max(1, cfg.generations))
    a.allow_infeasible_update = False
    a.parallel = bool(cfg.parallel)
    a.parallel_backend = str(cfg.parallel_backend)
    a.parallel_workers = int(max(1, cfg.parallel_workers))
    a.parallel_chunk_size = cfg.parallel_chunk_size
    a.parallel_verbose = False
    a.parallel_no_precheck = False
    a.parallel_strict = bool(cfg.parallel_strict)
    a.parallel_thread_bias_isolation = str(cfg.parallel_thread_bias_isolation)
    a.no_run_logs = True
    a.no_bias_md = True
    a.no_profile = True
    a.no_decision_trace = True
    a.decision_trace_flush_every = 10
    a.log_every = 10
    a.run_dir = None
    a.run_id = None
    a.report_every = 100
    a.no_export = True
    a.pareto_export = 0
    a.pareto_export_mode = "crowding"
    a.bom = None
    a.supply = None
    a.machines = int(machines)
    a.materials = int(materials)
    a.days = int(days)
    a.max_machines = int(cfg.max_active_machines_per_day)
    a.min_machines = 5
    a.min_prod = 50
    a.max_prod = int(cfg.max_production_per_machine)
    a.shortage_unit_penalty = 1.0
    a.penalty_objective = True
    a.penalty_scale = 0.001

    solver = build_multi_agent_solver(problem, a)
    solver.set_max_steps(int(a.generations))
    return solver, problem


def extract_total_output(solver, problem) -> Tuple[float, Optional[np.ndarray]]:
    """Best-effort extraction of total output from a production solver run."""
    x = getattr(solver, "best_x", None)
    if x is None:
        try:
            pop = np.asarray(getattr(solver, "population", None), dtype=float)
            obj = np.asarray(getattr(solver, "objectives", None), dtype=float)
            if pop.ndim == 2 and pop.shape[0] > 0:
                if obj.ndim == 2 and obj.shape[0] == pop.shape[0]:
                    idx = int(np.argmin(np.sum(obj, axis=1)))
                else:
                    idx = 0
                x = pop[idx]
        except Exception:
            x = None
    if x is None:
        return 0.0, None
    schedule = problem.decode_schedule(np.asarray(x, dtype=float))
    total_output = float(np.sum(schedule))
    return total_output, schedule
