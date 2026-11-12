"""pymoo baseline comparison for the quality benchmark (requires pymoo).

Runs the framework's NSGA-II / NSGA-III against pymoo's equivalents with matched
operators (arithmetic crossover + Gaussian mutation) and an identical evaluation
budget, measuring IGD / Hypervolume on the analytical ZDT/DTLZ problems.

This is a *distribution* comparison (many seeds, same operator family, same
budget), not a bit-exact trajectory gate — that is the transparency suite's job.

Usage::

    python -m benchmarks.pymoo_baseline \
        --problems zdt1,zdt2,zdt3,zdt6,dtlz2_2,dtlz2_3 \
        --algorithms nsga2,nsga3 --seeds 11,29,47 \
        --population-size 100 --steps 100
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from benchmarks.quality_suite import (
    ALGORITHM_MIN_OBJECTIVES,
    SUITE,
    _compatible,
    _measure,
    _stats,
    initial_population,
    run_to_snapshot,
)

# pymoo has no SPEA2 and MOEA/D's replacement/neighbourhood semantics are not
# cleanly matched, so the baseline covers the two algorithms with a clean,
# well-defined pymoo equivalent and matched operators.
PYMOO_ALGORITHMS = ("nsga2", "nsga3")

# Map problem keys to (pymoo name, n_obj). DTLZ1/4 forms can differ between
# implementations, so the baseline sticks to the unambiguous ZDT + DTLZ2 set.
PYMOO_PROBLEM = {
    "zdt1": ("zdt1", None), "zdt2": ("zdt2", None), "zdt3": ("zdt3", None),
    "zdt6": ("zdt6", None), "dtlz2_2": ("dtlz2", 2), "dtlz2_3": ("dtlz2", 3),
}


def pymoo_run(algorithm, problem_name, population_size, steps, seed):
    """Run pymoo's NSGA2/NSGA3 with matched operators; return (F, n_eval)."""
    from pymoo.algorithms.moo.nsga2 import NSGA2
    from pymoo.algorithms.moo.nsga3 import NSGA3
    from pymoo.core.crossover import Crossover
    from pymoo.core.mutation import Mutation
    from pymoo.core.population import Population
    from pymoo.optimize import minimize
    from pymoo.problems import get_problem
    from pymoo.util.ref_dirs import get_reference_directions

    if algorithm not in PYMOO_ALGORITHMS or problem_name not in PYMOO_PROBLEM:
        raise ValueError(f"no clean pymoo baseline for {algorithm} x {problem_name}")

    class Arithmetic(Crossover):
        def __init__(self):
            super().__init__(2, 1, prob=1.0)

        def _do(self, problem, x, random_state=None, **kwargs):
            # Match the framework's whole-individual crossover: 10% clone the
            # first parent, else blend all variables (alpha ~ U(0,1) per var).
            if random_state.random() > 0.9:
                return x[0][None, :, :]
            alpha = random_state.random(x[0].shape)
            child = alpha * x[0] + (1.0 - alpha) * x[1]
            return child[None, :, :]

    class Gaussian(Mutation):
        def __init__(self):
            super().__init__(prob=1.0)

        def _do(self, problem, x, random_state=None, **kwargs):
            return np.clip(x + random_state.normal(0.0, 0.08, x.shape), 0.0, 1.0)

    spec = SUITE[problem_name]
    pymoo_name, n_obj = PYMOO_PROBLEM[problem_name]
    kwargs = {"n_var": spec["n_var"]}
    if n_obj is not None:
        kwargs["n_obj"] = n_obj
    problem = get_problem(pymoo_name, **kwargs)
    initial = Population.new("X", initial_population(seed, population_size, spec["n_var"]))
    common = dict(pop_size=population_size, sampling=initial,
                  crossover=Arithmetic(), mutation=Gaussian(),
                  eliminate_duplicates=False, n_offsprings=population_size)
    if algorithm == "nsga2":
        instance = NSGA2(**common)
        instance.tournament_type = "comp_by_rank_and_crowding"
    else:
        instance = NSGA3(ref_dirs=get_reference_directions(
            "das-dennis", spec["n_obj"], n_partitions=12), **common)
    result = minimize(problem, instance, ("n_eval", population_size * steps),
                      seed=seed, verbose=False)
    return np.asarray(result.pop.get("F"), dtype=float), int(result.algorithm.evaluator.n_eval)


def run(options):
    problems = list(options["problems"])
    algorithms = list(options["algorithms"])
    seeds = [int(s) for s in options["seeds"]]
    population_size = int(options["population_size"])
    steps = int(options["steps"])

    unknown_a = [a for a in algorithms if a not in PYMOO_ALGORITHMS]
    if unknown_a:
        raise ValueError(f"pymoo baseline supports {PYMOO_ALGORITHMS}, got {unknown_a}")
    unknown_p = [p for p in problems if p not in PYMOO_PROBLEM]
    if unknown_p:
        raise ValueError(f"no clean pymoo baseline problem mapping for {unknown_p}")
    if population_size < 5 or steps < 2 or not seeds:
        raise ValueError("pymoo baseline requires population_size>=5, steps>=2 and seeds")

    rows = []
    for algorithm in algorithms:
        for problem in problems:
            if not _compatible(algorithm, problem):
                continue
            per_seed = []
            for seed in seeds:
                # framework side
                _x, f, v, evals = run_to_snapshot(algorithm, problem, seed,
                                                  population_size, steps)
                front, igd_fw, hv_fw = _measure(problem, f, v)
                # pymoo side
                ref_f, ref_evals = pymoo_run(algorithm, problem, population_size, steps, seed)
                front_ref, igd_ref, hv_ref = _measure(problem, ref_f, np.zeros(len(ref_f)))
                if evals != ref_evals:
                    raise ValueError(f"budget mismatch: framework={evals} pymoo={ref_evals}")
                per_seed.append({
                    "seed": int(seed),
                    "evaluations": evals,
                    "framework": {"igd": igd_fw, "hv": hv_fw, "front_size": int(front.shape[0])},
                    "pymoo": {"igd": igd_ref, "hv": hv_ref, "front_size": int(front_ref.shape[0])},
                    "igd_delta": igd_fw - igd_ref,
                    "hv_delta": hv_fw - hv_ref,
                })
            rows.append({
                "algorithm": algorithm,
                "problem": problem,
                "seeds": seeds,
                "budget": population_size * steps,
                "framework_igd": _stats([r["framework"]["igd"] for r in per_seed]),
                "pymoo_igd": _stats([r["pymoo"]["igd"] for r in per_seed]),
                "framework_hv": _stats([r["framework"]["hv"] for r in per_seed]),
                "pymoo_hv": _stats([r["pymoo"]["hv"] for r in per_seed]),
                "per_seed": per_seed,
            })

    return {
        "schema": "nsgablack.pymoo_baseline/v1",
        "config": {
            "problems": problems,
            "algorithms": algorithms,
            "seeds": seeds,
            "population_size": population_size,
            "steps": steps,
            "evaluation_budget": population_size * steps,
            "operators": ("arithmetic crossover (rate 0.9) + Gaussian mutation (sigma 0.08); "
                          "matched between framework and pymoo"),
            "note": ("Distribution comparison at equal budget, not a trajectory gate. "
                     "SPEA2 (no pymoo equivalent) and MOEA/D (replacement semantics) are "
                     "excluded; DTLZ1/4 forms may differ between implementations."),
        },
        "results": rows,
    }


def _fmt(stats):
    return f"{stats['median']:.4f} ({stats['q1']:.4f}–{stats['q3']:.4f})"


def build_markdown(report):
    cfg = report["config"]
    lines = [
        "# nsgablack vs pymoo Baseline",
        "",
        f"- problems: {', '.join(cfg['problems'])}",
        f"- algorithms: {', '.join(cfg['algorithms'])}",
        f"- seeds: {', '.join(str(s) for s in cfg['seeds'])}",
        f"- budget: {cfg['evaluation_budget']} evaluations",
        "",
        "IGD is lower-better, HV is higher-better. Values are median (Q1–Q3).",
        "",
        "| Algorithm | Problem | framework IGD | pymoo IGD | framework HV | pymoo HV |",
        "|---|---|---|---|---|---|",
    ]
    for row in report["results"]:
        lines.append(f"| {row['algorithm']} | {row['problem']} | {_fmt(row['framework_igd'])} | "
                     f"{_fmt(row['pymoo_igd'])} | {_fmt(row['framework_hv'])} | "
                     f"{_fmt(row['pymoo_hv'])} |")
    lines.append("")
    return "\n".join(lines)


def _split_csv(value):
    return [part.strip() for part in str(value).split(",") if part.strip()]


def main(argv=None):
    parser = argparse.ArgumentParser(description="nsgablack vs pymoo baseline comparison")
    parser.add_argument("--problems", default="zdt1,zdt2,zdt3,zdt6,dtlz2_2,dtlz2_3",
                        help="comma-separated problem keys")
    parser.add_argument("--algorithms", default="nsga2,nsga3",
                        help="comma-separated algorithm names")
    parser.add_argument("--seeds", default="11,29,47", help="comma-separated integer seeds")
    parser.add_argument("--population-size", type=int, default=100)
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--output-dir", default="runs/pymoo_baseline")
    args = parser.parse_args(argv)

    options = {
        "problems": _split_csv(args.problems),
        "algorithms": _split_csv(args.algorithms),
        "seeds": [int(x) for x in _split_csv(args.seeds)],
        "population_size": args.population_size,
        "steps": args.steps,
    }
    report = run(options)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "pymoo_baseline_report.json"
    md_path = out / "pymoo_baseline_report.md"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    md_path.write_text(build_markdown(report), encoding="utf-8")
    print(f"[ok] wrote {json_path} and {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
