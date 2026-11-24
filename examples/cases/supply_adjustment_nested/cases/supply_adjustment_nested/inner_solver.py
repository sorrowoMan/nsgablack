from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Tuple

import numpy as np

from blackbase.project import build_case, load_case_builder
from blackbase.resources import ResourceRequirement


@dataclass(frozen=True)
class InnerProductionSolverConfig:
    pop_size: int = 16
    generations: int = 3
    max_active_machines_per_day: int = 8
    max_production_per_machine: float = 3000.0
    seed: int = 42
    max_evaluations: int | None = None
    parallel: bool = False
    parallel_backend: str = "thread"
    parallel_workers: int = 1
    parallel_chunk_size: int | None = None
    parallel_strict: bool = False
    parallel_thread_bias_isolation: str = "disable_cache"
    resource_requirement: ResourceRequirement | Mapping[str, object] | None = None

    def effective_resource_requirement(self) -> ResourceRequirement:
        if isinstance(self.resource_requirement, ResourceRequirement):
            base = self.resource_requirement
        elif isinstance(self.resource_requirement, Mapping):
            base = ResourceRequirement.from_dict(self.resource_requirement)
        else:
            base = ResourceRequirement(
                threads=int(max(1, self.parallel_workers)),
                capabilities=("production_inner", "nested_eval"),
                metadata={"layer": "L2", "source": "supply_adjustment_nested.inner"},
            )
        caps = tuple(dict.fromkeys(tuple(base.capabilities) + ("production_inner", "nested_eval")))
        metadata = dict(base.metadata)
        metadata.setdefault("layer", "L2")
        metadata.setdefault("source", "supply_adjustment_nested.inner")
        return ResourceRequirement(
            threads=int(base.threads), gpus=int(base.gpus), resource_backend=str(base.resource_backend),
            device_tokens=tuple(base.device_tokens), memory_mb=base.memory_mb,
            gpu_memory_mb=base.gpu_memory_mb, capabilities=caps,
            timeout_seconds=base.timeout_seconds, metadata=metadata,
        )


def build_inner_production_solver(
    *, bom_matrix: np.ndarray, supply_matrix: np.ndarray,
    production_case_dir: Path, cfg: InnerProductionSolverConfig, resource_context=None,
):
    """Use the production Case's canonical builder with an explicit local scenario."""
    case_dir = Path(production_case_dir).resolve()
    if case_dir.parent.name != "cases" or not (case_dir / "build_solver.py").is_file():
        raise ValueError("production_case_dir must name a standard production Case")
    bom, supply = np.asarray(bom_matrix, dtype=float), np.asarray(supply_matrix, dtype=float)
    if bom.ndim != 2 or supply.ndim != 2 or bom.shape[1] != supply.shape[0]:
        raise ValueError("BOM and supply must have compatible two-dimensional shapes")
    machines, materials = bom.shape
    days = supply.shape[1]
    if days != 31:
        raise ValueError("nested production uses the original day0..30 planning window")
    req = cfg.effective_resource_requirement()
    argv = [
        "--solver", "multi-agent", "--cooperation", "phased",
        "--machines", str(machines), "--materials", str(materials), "--days", str(days),
        "--max-machines", str(cfg.max_active_machines_per_day),
        "--min-machines", "5", "--min-prod", "50",
        "--max-prod", str(int(cfg.max_production_per_machine)),
        "--penalty-objective", "--penalty-scale", "0.001", "--shortage-unit-penalty", "1.0",
        "--material-cap-ratio", "2.0", "--daily-floor-ratio", "0.7",
        "--donor-keep-ratio", "0.6", "--daily-cap-ratio", "1.0",
        "--reserve-ratio", "0.2", "--coverage-bonus", "0.3", "--budget-mode", "average",
        "--smooth-strength", "0.8", "--smooth-passes", "1",
        "--coverage-reward", "0.03", "--smoothness-penalty", "0.01", "--variance-penalty", "0.03",
        "--pop-size", str(max(8, cfg.pop_size)), "--generations", str(max(1, cfg.generations)),
        "--moead-pop-size", str(max(16, cfg.pop_size)), "--moead-neighborhood", "10",
        "--moead-nr", "2", "--moead-delta", "0.9", "--explorer-adapter", "moead",
        "--vns-batch-size", str(max(8, cfg.pop_size // 2)), "--vns-k-max", "3",
        "--vns-base-sigma", "0.2", "--exploiter-adapter", "vns",
        "--adapt-interval", "8", "--comm-interval", "5", "--seed", str(cfg.seed),
        "--parallel-backend", cfg.parallel_backend, "--parallel-workers", str(max(1, req.threads)),
        "--parallel-thread-bias-isolation", cfg.parallel_thread_bias_isolation,
        "--no-run-logs", "--no-bias-md", "--no-profile", "--no-decision-trace", "--no-export",
        "--pareto-export", "0", "--report-every", "100",
    ]
    if cfg.parallel:
        argv.append("--parallel")
    if cfg.parallel_strict:
        argv.append("--parallel-strict")
    if cfg.parallel_chunk_size is not None:
        argv.extend(("--parallel-chunk-size", str(cfg.parallel_chunk_size)))
    if cfg.max_evaluations is not None:
        if type(cfg.max_evaluations) is not int or cfg.max_evaluations < 1:
            raise ValueError("inner max_evaluations must be a positive integer")
        argv.extend(("--max-evaluations", str(cfg.max_evaluations)))
    builder = load_case_builder(case_dir.parents[1], case_dir.name, "solver")
    solver = build_case(builder, resource_context=resource_context, component_overrides={
        "argv": argv,
        "scenario": {"schema": "production_scheduling.scenario/v1",
                     "bom_matrix": (bom > 0).astype(int).tolist(), "supply_matrix": supply.tolist(),
                     "machine_weights": np.ones(machines).tolist()},
    })
    solver.l0_resource_requirement = req
    solver.resource_request = req.to_resource_request(label="supply_adjustment_inner")
    solver.accepted_parent_contracts = ("outer.default", "supply_adjustment_nested.outer")
    return solver, solver.problem


def extract_total_output(solver, problem) -> Tuple[float, np.ndarray]:
    """Read the complete authoritative incumbent; missing results are failures."""
    incumbent = solver.get_incumbent()
    if incumbent is None or not incumbent.candidate_token:
        raise RuntimeError("inner production has no authoritative evaluated incumbent")
    schedule = np.asarray(problem.decode_schedule(incumbent.candidate), dtype=float)
    if schedule.shape != (problem.machines, problem.days) or not np.all(np.isfinite(schedule)):
        raise RuntimeError("inner production incumbent contains an invalid schedule")
    return float(schedule.sum()), schedule.copy()