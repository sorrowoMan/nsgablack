"""Self-contained multi-algorithm fusion effectiveness benchmark (no pymoo).

Compares a sequential hybrid against each single algorithm at the SAME evaluation
budget, on the analytical ZDT/DTLZ problems from ``quality_suite``::

    hybrid       = run(global,  split_steps) -> warm-start(refine, split_steps)
    baseline_a   = run(global,  total_steps)
    baseline_b   = run(refine,  total_steps)

The hybrid's final front is the non-dominated union of both phases' outputs.
``global`` explores broadly (NSGA-II); ``refine`` polishes the population from the
pool of already-found solutions (MOEA/D decomposition refinement or SPEA2 archive
refinement).

Fairness note: the framework always evaluates an initializer's population, so the
hybrid re-evaluates its warm-start population on the first refinement step (a
~1/total_steps overhead). This slightly handicaps the hybrid, so any improvement
over the baseline is reported *despite* that handicap.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from benchmarks.quality_suite import (
    ALGORITHMS,
    SUITE,
    _measure,
    _stats,
    run_to_snapshot,
)

FUSION_PAIRS = [
    ("nsga2", "moead"),
    ("nsga2", "spea2"),
]


def run_fusion(global_alg, refine_alg, problem_name, seed, population_size,
               total_steps, nsga3_divisions=12):
    if global_alg not in ALGORITHMS or refine_alg not in ALGORITHMS:
        raise ValueError(f"unknown fusion algorithm pair: {global_alg}, {refine_alg}")
    if problem_name not in SUITE:
        raise ValueError(f"unknown problem: {problem_name}")
    split = total_steps // 2
    refine_steps = total_steps - split
    budget = population_size * total_steps

    # Baselines: each algorithm alone for the full budget.
    _, fg, vg, eg = run_to_snapshot(global_alg, problem_name, seed, population_size,
                                    total_steps, nsga3_divisions=nsga3_divisions)
    front_g, igd_g, hv_g = _measure(problem_name, fg, vg)
    _, fr, vr, er = run_to_snapshot(refine_alg, problem_name, seed, population_size,
                                    total_steps, nsga3_divisions=nsga3_divisions)
    front_r, igd_r, hv_r = _measure(problem_name, fr, vr)

    # Hybrid: global then warm-started refinement; final front is the union.
    x1, f1, v1, e1 = run_to_snapshot(global_alg, problem_name, seed, population_size,
                                     split, nsga3_divisions=nsga3_divisions)
    _, f2, v2, e2 = run_to_snapshot(refine_alg, problem_name, seed, population_size,
                                    refine_steps, nsga3_divisions=nsga3_divisions,
                                    initial_values=x1)
    f_all = np.vstack([f1, f2])
    v_all = np.concatenate([v1, v2])
    front_h, igd_h, hv_h = _measure(problem_name, f_all, v_all)

    return {
        "problem": problem_name,
        "seed": int(seed),
        "global": global_alg,
        "refine": refine_alg,
        "population_size": population_size,
        "total_steps": total_steps,
        "budget": budget,
        "global_alone": {"igd": igd_g, "hv": hv_g, "evaluations": eg,
                         "front_size": int(front_g.shape[0])},
        "refine_alone": {"igd": igd_r, "hv": hv_r, "evaluations": er,
                         "front_size": int(front_r.shape[0])},
        "hybrid": {"igd": igd_h, "hv": hv_h, "evaluations": e1 + e2,
                   "phase_evaluations": [e1, e2], "front_size": int(front_h.shape[0])},
    }


def run(options):
    pairs = list(options["pairs"])
    problems = list(options["problems"])
    seeds = [int(s) for s in options["seeds"]]
    population_size = int(options["population_size"])
    total_steps = int(options["total_steps"])
    nsga3_divisions = int(options.get("nsga3_divisions", 12))

    if total_steps < 4:
        raise ValueError("fusion benchmark requires total_steps>=4 (>=2 per phase)")
    if not pairs or not problems or not seeds:
        raise ValueError("fusion benchmark requires pairs, problems and seeds")

    rows = []
    for global_alg, refine_alg in pairs:
        for problem in problems:
            per_seed = [run_fusion(global_alg, refine_alg, problem, seed, population_size,
                                   total_steps, nsga3_divisions=nsga3_divisions)
                        for seed in seeds]
            rows.append({
                "pair": f"{global_alg}->{refine_alg}",
                "global": global_alg,
                "refine": refine_alg,
                "problem": problem,
                "seeds": seeds,
                "budget": population_size * total_steps,
                "global_igd": _stats([r["global_alone"]["igd"] for r in per_seed]),
                "global_hv": _stats([r["global_alone"]["hv"] for r in per_seed]),
                "refine_igd": _stats([r["refine_alone"]["igd"] for r in per_seed]),
                "refine_hv": _stats([r["refine_alone"]["hv"] for r in per_seed]),
                "hybrid_igd": _stats([r["hybrid"]["igd"] for r in per_seed]),
                "hybrid_hv": _stats([r["hybrid"]["hv"] for r in per_seed]),
                "per_seed": per_seed,
            })

    return {
        "schema": "nsgablack.fusion_suite/v1",
        "config": {
            "pairs": [f"{a}->{b}" for a, b in pairs],
            "problems": problems,
            "seeds": seeds,
            "population_size": population_size,
            "total_steps": total_steps,
            "evaluation_budget": population_size * total_steps,
            "nsga3_divisions": nsga3_divisions,
            "note": ("Sequential hybrid (global then warm-started refinement) vs each single "
                     "algorithm at equal budget. Hybrid re-evaluates the warm-start population "
                     "on its first refinement step (handicap), so any win is reported despite "
                     "that overhead."),
        },
        "results": rows,
    }


def _fmt(stats):
    return f"{stats['median']:.4f} ({stats['q1']:.4f}–{stats['q3']:.4f})"


def build_markdown(report):
    cfg = report["config"]
    lines = [
        "# nsgablack Fusion Benchmark",
        "",
        f"- pairs: {', '.join(cfg['pairs'])}",
        f"- problems: {', '.join(cfg['problems'])}",
        f"- seeds: {', '.join(str(s) for s in cfg['seeds'])}",
        f"- budget: {cfg['evaluation_budget']} evaluations (pop {cfg['population_size']} × "
        f"{cfg['total_steps']} steps)",
        "",
        "IGD is lower-better, HV is higher-better. Values are median (Q1–Q3).",
        "",
        "| Pair | Problem | global IGD | refine IGD | hybrid IGD | global HV | hybrid HV |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in report["results"]:
        lines.append(f"| {row['pair']} | {row['problem']} | {_fmt(row['global_igd'])} | "
                     f"{_fmt(row['refine_igd'])} | {_fmt(row['hybrid_igd'])} | "
                     f"{_fmt(row['global_hv'])} | {_fmt(row['hybrid_hv'])} |")
    lines.append("")
    return "\n".join(lines)


def _split_csv(value):
    return [part.strip() for part in str(value).split(",") if part.strip()]


def main(argv=None):
    parser = argparse.ArgumentParser(description="nsgablack multi-algorithm fusion benchmark")
    parser.add_argument("--pairs", default="nsga2:moead,nsga2:spea2",
                        help="comma-separated 'global:refine' pairs")
    parser.add_argument("--problems", default="zdt1,zdt2,zdt3,zdt6,dtlz2_2,dtlz2_3,dtlz1_3,dtlz4_3",
                        help="comma-separated problem keys")
    parser.add_argument("--seeds", default="11,29,47", help="comma-separated integer seeds")
    parser.add_argument("--population-size", type=int, default=100)
    parser.add_argument("--total-steps", type=int, default=100,
                        help="total logical steps split evenly across the two phases")
    parser.add_argument("--nsga3-divisions", type=int, default=12)
    parser.add_argument("--output-dir", default="runs/fusion")
    args = parser.parse_args(argv)

    pairs = []
    for token in _split_csv(args.pairs):
        if ":" not in token:
            raise ValueError(f"fusion pair must be 'global:refine', got {token!r}")
        pairs.append(tuple(token.split(":", 1)))

    options = {
        "pairs": pairs,
        "problems": _split_csv(args.problems),
        "seeds": [int(x) for x in _split_csv(args.seeds)],
        "population_size": args.population_size,
        "total_steps": args.total_steps,
        "nsga3_divisions": args.nsga3_divisions,
    }
    report = run(options)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "fusion_report.json"
    md_path = out / "fusion_report.md"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    md_path.write_text(build_markdown(report), encoding="utf-8")
    print(f"[ok] wrote {json_path} and {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
