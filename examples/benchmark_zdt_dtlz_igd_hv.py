"""Benchmark ZDT/DTLZ with IGD and 2D HV (within NSGABlack)."""

from __future__ import annotations

import csv
import json
import os
import random
import sys
import time
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.problems import DTLZ2BlackBox, ZDT1BlackBox, ZDT3BlackBox
from core.solver import BlackBoxSolverNSGAII
from solvers.multi_agent import MultiAgentBlackBoxSolver
from bias.bias import BiasModule

try:
    from solvers.moead import BlackBoxSolverMOEAD
    _HAVE_MOEAD = True
except Exception:
    BlackBoxSolverMOEAD = None
    _HAVE_MOEAD = False

from utils.metrics import (
    pareto_filter,
    hypervolume_2d,
    igd,
    reference_front_zdt1,
    reference_front_zdt3,
    reference_front_dtlz2,
)


BASE_SEED = 42
REPEATS = 3
POP_SIZE = 100
GENERATIONS = 80
REF_POINTS = 1000
OUTPUT_DIR = os.path.join(ROOT_DIR, "reports", "benchmark")
ENABLE_HV = False


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)


def _extract_objectives(result) -> np.ndarray:
    if isinstance(result, dict) and "pareto_objectives" in result:
        return np.asarray(result["pareto_objectives"], dtype=float)
    if isinstance(result, list) and result and isinstance(result[0], dict):
        return np.asarray([item["objectives"] for item in result], dtype=float)
    return np.zeros((0, 0), dtype=float)


def _build_l2_bias() -> BiasModule:
    bias = BiasModule()

    def l2_penalty(x, _constraints, _context):
        return {"penalty": float(np.linalg.norm(x))}

    bias.add_penalty(l2_penalty, weight=0.01, name="l2_penalty")
    return bias


def _run_nsga(problem) -> np.ndarray:
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = POP_SIZE
    solver.max_generations = GENERATIONS
    solver.enable_progress_log = False
    solver.enable_memory_optimization = False
    result = solver.run()
    return _extract_objectives(result)


def _run_nsga_bias(problem) -> np.ndarray:
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = POP_SIZE
    solver.max_generations = GENERATIONS
    solver.enable_progress_log = False
    solver.enable_memory_optimization = False
    solver.bias_module = _build_l2_bias()
    solver.enable_bias = True
    result = solver.run()
    return _extract_objectives(result)


def _run_nsga_diversity_init(problem) -> np.ndarray:
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = POP_SIZE
    solver.max_generations = GENERATIONS
    solver.enable_progress_log = False
    solver.enable_memory_optimization = False
    solver.enable_diversity_init = True
    solver.diversity_params["candidate_size"] = max(POP_SIZE * 5, 200)
    result = solver.run()
    return _extract_objectives(result)


def _run_moead(problem) -> Optional[np.ndarray]:
    if not _HAVE_MOEAD:
        return None
    solver = BlackBoxSolverMOEAD(problem)
    solver.population_size = POP_SIZE
    solver.max_generations = GENERATIONS
    solver.enable_progress_log = False
    result = solver.run()
    return _extract_objectives(result)


def _run_multi_agent(problem) -> np.ndarray:
    config = {
        "total_population": POP_SIZE,
        "max_generations": max(30, GENERATIONS // 2),
        "communication_interval": 5,
        "adaptation_interval": 5,
        "dynamic_ratios": False,
        "region_partition": False,
        "archive_enabled": True,
    }
    solver = MultiAgentBlackBoxSolver(problem=problem, config=config)
    result = solver.run()
    return _extract_objectives(result)


def _score_bias_small_norm(x, _constraints, _context):
    return {"score": 1.0 / (1.0 + float(np.linalg.norm(x)))}


def _run_multi_agent_score_bias(problem) -> np.ndarray:
    config = {
        "total_population": POP_SIZE,
        "max_generations": max(30, GENERATIONS // 2),
        "communication_interval": 5,
        "adaptation_interval": 5,
        "dynamic_ratios": True,
        "region_partition": False,
        "archive_enabled": True,
        "global_score_biases": [_score_bias_small_norm],
    }
    solver = MultiAgentBlackBoxSolver(problem=problem, config=config)
    result = solver.run()
    return _extract_objectives(result)


def _evaluate_solver(
    solver_fn: Callable,
    problem_factory: Callable,
    reference_front: np.ndarray,
    reference_point: np.ndarray,
    solver_name: str,
    problem_name: str,
    repeats: int,
    progress_state: Optional[Dict[str, int]] = None,
) -> Tuple[Dict[str, float], List[Dict[str, float]]]:
    igd_values: List[float] = []
    hv_values: List[float] = []
    times: List[float] = []
    pareto_sizes: List[int] = []
    run_records: List[Dict[str, float]] = []

    for i in range(repeats):
        if progress_state is not None:
            progress_state["current"] += 1
            print(
                f"Progress {progress_state['current']}/{progress_state['total']} | "
                f"{problem_name} | {solver_name} | run {i + 1}/{repeats}"
            )
        seed = BASE_SEED + i
        _set_seed(seed)
        problem = problem_factory()
        start = time.time()
        objectives = solver_fn(problem)
        if objectives is None:
            continue
        elapsed = time.time() - start

        objectives = pareto_filter(objectives)
        pareto_size = int(len(objectives))
        igd_value = igd(objectives, reference_front)
        if ENABLE_HV and objectives.size > 0 and objectives.shape[1] == 2:
            hv_value = hypervolume_2d(objectives, reference_point)
        else:
            hv_value = float("nan")

        pareto_sizes.append(pareto_size)
        igd_values.append(igd_value)
        if ENABLE_HV and not np.isnan(hv_value):
            hv_values.append(hv_value)
        times.append(elapsed)

        run_records.append(
            {
                "problem": problem_name,
                "solver": solver_name,
                "seed": seed,
                "igd": float(igd_value),
                "hv": float(hv_value),
                "pareto_size": pareto_size,
                "time_sec": float(elapsed),
            }
        )

    summary = {
        "igd_mean": float(np.mean(igd_values)),
        "igd_std": float(np.std(igd_values)),
        "hv_mean": float(np.mean(hv_values)) if (ENABLE_HV and hv_values) else float("nan"),
        "hv_std": float(np.std(hv_values)) if (ENABLE_HV and hv_values) else float("nan"),
        "time_mean": float(np.mean(times)),
        "pareto_mean": float(np.mean(pareto_sizes)),
    }
    return summary, run_records


def _save_results(
    run_records: List[Dict[str, float]],
    summary_records: List[Dict[str, float]],
    config: Dict[str, object],
) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    json_path = os.path.join(OUTPUT_DIR, "benchmark_results.json")
    csv_path = os.path.join(OUTPUT_DIR, "benchmark_results.csv")
    summary_csv_path = os.path.join(OUTPUT_DIR, "benchmark_summary.csv")
    report_path = os.path.join(OUTPUT_DIR, "benchmark_report.md")

    payload = {
        "config": config,
        "runs": run_records,
        "summary": summary_records,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=True)

    if run_records:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=run_records[0].keys())
            writer.writeheader()
            writer.writerows(run_records)

    if summary_records:
        with open(summary_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=summary_records[0].keys())
            writer.writeheader()
            writer.writerows(summary_records)

    _write_report(report_path, summary_records, config)


def _write_report(
    path: str,
    summary_records: List[Dict[str, float]],
    config: Dict[str, object],
) -> None:
    def fmt_mean_std(mean: float, std: float) -> str:
        if np.isnan(mean):
            return "N/A"
        return f"{mean:.4f} +/- {std:.4f}"

    lines = []
    lines.append("# Benchmark Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append("## Config")
    for key, value in config.items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## Summary (lower IGD is better)")
    lines.append("| Problem | Solver | IGD (mean +/- std) | Pareto | Time(s) |")
    lines.append("| --- | --- | --- | --- | --- |")
    for row in summary_records:
        lines.append(
            f"| {row['problem']} | {row['solver']} | "
            f"{fmt_mean_std(row['igd_mean'], row['igd_std'])} | "
            f"{row['pareto_mean']:.1f} | {row['time_mean']:.2f} |"
        )

    problems = sorted({row["problem"] for row in summary_records})
    lines.append("")
    lines.append("## Ranking by IGD")
    for problem in problems:
        rows = [r for r in summary_records if r["problem"] == problem]
        rows = sorted(rows, key=lambda r: r["igd_mean"])
        lines.append(f"- {problem}: " + ", ".join(r["solver"] for r in rows[:3]))

    lines.append("")
    lines.append("## Notes")
    lines.append("- Quality uses IGD and Pareto size.")
    lines.append("- Bias variants are not strictly comparable to unbiased baselines.")
    lines.append("")
    lines.append("## Conclusions")
    lines.append("- [ ] Fill in observations and decisions.")
    lines.append("")
    lines.append("## Next Steps")
    lines.append("- [ ] Add more solvers or bias combinations.")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> None:
    problem_specs = [
        {
            "name": "ZDT1",
            "factory": lambda: ZDT1BlackBox(dimension=30),
            "reference": lambda: reference_front_zdt1(REF_POINTS),
        },
        {
            "name": "ZDT3",
            "factory": lambda: ZDT3BlackBox(dimension=30),
            "reference": lambda: reference_front_zdt3(REF_POINTS),
        },
        {
            "name": "DTLZ2",
            "factory": lambda: DTLZ2BlackBox(dimension=12, n_objectives=2),
            "reference": lambda: reference_front_dtlz2(REF_POINTS, n_objectives=2),
        },
    ]

    solvers = {
        "NSGA-II": _run_nsga,
        "NSGA-II + DiversityInit": _run_nsga_diversity_init,
        "NSGA-II + L2Bias": _run_nsga_bias,
        "MOEA/D": _run_moead if _HAVE_MOEAD else None,
        "MultiAgent": _run_multi_agent,
        "MultiAgent + ScoreBias": _run_multi_agent_score_bias,
    }

    solver_names = [name for name, fn in solvers.items() if fn is not None]
    config = {
        "seed_base": BASE_SEED,
        "repeats": REPEATS,
        "pop_size": POP_SIZE,
        "generations": GENERATIONS,
        "reference_points": REF_POINTS,
        "enable_hv": ENABLE_HV,
        "solvers": solver_names,
        "problems": [spec["name"] for spec in problem_specs],
    }

    run_records: List[Dict[str, float]] = []
    summary_records: List[Dict[str, float]] = []
    progress_state = {
        "current": 0,
        "total": len(problem_specs) * len(solver_names) * REPEATS,
    }

    for spec in problem_specs:
        reference_front = spec["reference"]()
        reference_point = np.max(reference_front, axis=0) * 1.1

        print(f"\n=== {spec['name']} ===")
        for solver_name, solver_fn in solvers.items():
            if solver_fn is None:
                continue
            summary, runs = _evaluate_solver(
                solver_fn,
                spec["factory"],
                reference_front,
                reference_point,
                solver_name,
                spec["name"],
                REPEATS,
                progress_state,
            )
            summary_record = {
                "problem": spec["name"],
                "solver": solver_name,
                **summary,
            }
            summary_records.append(summary_record)
            run_records.extend(runs)

            print(
                f"{solver_name:22s} | IGD {summary['igd_mean']:.4f} +/- {summary['igd_std']:.4f} "
                f"| Pareto {summary['pareto_mean']:.1f} | Time {summary['time_mean']:.2f}s"
            )

    _save_results(run_records, summary_records, config)
    print(f"\nSaved results to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
