"""Self-contained single-objective CMA-ES convergence benchmark (no pymoo).

CMA-ES is single-objective, so it cannot be scored by IGD/Hypervolume like the
multi-objective suite. Instead this measures convergence to a known optimum:
run the framework's ``CMAESAdapter`` on standard single-objective functions and
report the best objective found after a fixed evaluation budget.

Usage::

    python -m benchmarks.single_objective_suite \
        --problems sphere,rosenbrock,rastrigin,ackley \
        --seeds 11,29,47 --n-var 10 --steps 250

The default CMA-ES cohort size (lambda) is the framework default of 4; use
``--cma-lambda`` to enlarge it (standard recommendation ~ 4 + 3*ln(n)).
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from blackbase.resources import ResourceContext
from nsgablack.adapters.cmaes import CMAESAdapter
from nsgablack.core import BlackBoxProblem, ComposableSolver

from benchmarks.quality_suite import _stats


class _SingleObjectiveProblem(BlackBoxProblem):
    optimum = 0.0

    def __init__(self, name, n_var, bounds, objective_fn):
        self._objective_fn = objective_fn
        super().__init__(name=name, dimension=int(n_var),
                         bounds=[bounds] * int(n_var), objectives=["min"])

    def evaluate(self, candidate, context=None):
        x = np.asarray(candidate, dtype=float)
        return np.array([self._objective_fn(x)], dtype=float)


def _sphere(x):
    return float(np.sum(x ** 2))


def _rosenbrock(x):
    return float(np.sum(100.0 * (x[1:] - x[:-1] ** 2) ** 2 + (x[:-1] - 1.0) ** 2))


def _rastrigin(x):
    n = len(x)
    return float(10.0 * n + np.sum(x ** 2 - 10.0 * np.cos(2.0 * np.pi * x)))


def _ackley(x):
    n = len(x)
    a = -20.0 * np.exp(-0.2 * np.sqrt(np.mean(x ** 2)))
    b = -np.exp(np.mean(np.cos(2.0 * np.pi * x)))
    return float(a + b + 20.0 + np.e)


PROBLEMS = {
    "sphere": {"fn": _sphere, "mean": 3.0, "bounds": (-5.0, 5.0)},
    "rosenbrock": {"fn": _rosenbrock, "mean": 0.0, "bounds": (-5.0, 10.0)},
    "rastrigin": {"fn": _rastrigin, "mean": 3.0, "bounds": (-5.12, 5.12)},
    "ackley": {"fn": _ackley, "mean": 5.0, "bounds": (-32.0, 32.0)},
}


def _make_problem(name, n_var):
    spec = PROBLEMS[name]
    return _SingleObjectiveProblem(name, n_var, spec["bounds"], spec["fn"])


def run_cma(problem_name, seed, n_var, steps, sigma=0.35, cma_lambda=None):
    if problem_name not in PROBLEMS:
        raise ValueError(f"unknown single-objective problem: {problem_name}")
    spec = PROBLEMS[problem_name]
    problem = _make_problem(problem_name, n_var)

    best = {"value": np.inf}
    original = problem.evaluate

    def tracked(candidate, *args, **kwargs):
        result = original(candidate, *args, **kwargs)
        value = np.asarray(result, dtype=float).reshape(-1)
        if value.size:
            best["value"] = min(best["value"], float(value[0]))
        return result

    problem.evaluate = tracked

    if cma_lambda is None:
        cma_lambda = max(4, 4 + int(3.0 * round(math.log(n_var))))

    mean = np.full(int(n_var), float(spec["mean"]), dtype=float)
    adapter = CMAESAdapter(mean, sigma=float(sigma), seed=int(seed))
    if int(cma_lambda) != 4:
        from nsgablack.adapters.cmaes.components import CMAParameters
        adapter = CMAESAdapter(mean, sigma=float(sigma), seed=int(seed),
                               parameters=CMAParameters(population_size=int(cma_lambda)))

    solver = ComposableSolver(
        problem,
        adapter=adapter,
        representation_pipeline=None,
        resource_context=ResourceContext(namespace="single_objective_local",
                                         grant={"threads": 1, "workers": 1}),
        plugin_strict=True,
        snapshot_strict=True,
    )
    solver.set_random_seed(int(seed))
    solver.enable_progress_log = False
    solver.run(max_steps=int(steps))

    return {
        "problem": problem_name,
        "seed": int(seed),
        "n_var": n_var,
        "cma_lambda": cma_lambda,
        "sigma": sigma,
        "evaluations": int(solver.evaluation_count),
        "best": float(best["value"]),
        "optimum": _SingleObjectiveProblem.optimum,
    }


def run(options):
    problems = list(options["problems"])
    seeds = [int(s) for s in options["seeds"]]
    n_var = int(options["n_var"])
    steps = int(options["steps"])
    sigma = float(options.get("sigma", 0.35))
    cma_lambda = options.get("cma_lambda")

    unknown = [p for p in problems if p not in PROBLEMS]
    if unknown:
        raise ValueError(f"unknown single-objective problems: {unknown}")
    if not seeds or steps < 1 or n_var < 2:
        raise ValueError("single-objective benchmark requires seeds, steps>=1 and n_var>=2")

    rows = []
    for problem in problems:
        per_seed = [run_cma(problem, seed, n_var, steps, sigma=sigma, cma_lambda=cma_lambda)
                    for seed in seeds]
        rows.append({
            "problem": problem,
            "n_var": n_var,
            "seeds": seeds,
            "optimum": _SingleObjectiveProblem.optimum,
            "cma_lambda": per_seed[0]["cma_lambda"],
            "sigma": sigma,
            "best": _stats([r["best"] for r in per_seed]),
            "evaluations": _stats([r["evaluations"] for r in per_seed]),
            "per_seed": per_seed,
        })

    return {
        "schema": "nsgablack.single_objective_suite/v1",
        "config": {
            "problems": problems,
            "seeds": seeds,
            "n_var": n_var,
            "steps": steps,
            "sigma": sigma,
            "cma_lambda": cma_lambda,
            "metric": "best objective found (lower is better; all problems have optimum 0.0)",
        },
        "results": rows,
    }


def build_markdown(report):
    cfg = report["config"]
    lines = [
        "# nsgablack Single-objective CMA-ES Benchmark",
        "",
        f"- problems: {', '.join(cfg['problems'])}",
        f"- seeds: {', '.join(str(s) for s in cfg['seeds'])}",
        f"- n_var: {cfg['n_var']} · steps: {cfg['steps']} · sigma: {cfg['sigma']}",
        "",
        "Best objective is lower-better; every problem has optimum 0.0.",
        "",
        "| Problem | n_var | lambda | best (median, Q1–Q3) | evaluations |",
        "|---|---|---:|---|---:|",
    ]
    for row in report["results"]:
        lines.append(f"| {row['problem']} | {row['n_var']} | {row['cma_lambda']} | "
                     f"{row['best']['median']:.6f} ({row['best']['q1']:.6f}–{row['best']['q3']:.6f}) | "
                     f"{row['evaluations']['median']:.0f} |")
    lines.append("")
    return "\n".join(lines)


def _split_csv(value):
    return [part.strip() for part in str(value).split(",") if part.strip()]


def main(argv=None):
    parser = argparse.ArgumentParser(description="nsgablack single-objective CMA-ES benchmark")
    parser.add_argument("--problems", default="sphere,rosenbrock,rastrigin,ackley",
                        help="comma-separated problem names")
    parser.add_argument("--seeds", default="11,29,47", help="comma-separated integer seeds")
    parser.add_argument("--n-var", type=int, default=10)
    parser.add_argument("--steps", type=int, default=250)
    parser.add_argument("--sigma", type=float, default=0.35)
    parser.add_argument("--cma-lambda", type=int, default=None,
                        help="CMA cohort size; default auto ~ 4 + 3*ln(n_var)")
    parser.add_argument("--output-dir", default="runs/single_objective")
    args = parser.parse_args(argv)

    options = {
        "problems": _split_csv(args.problems),
        "seeds": [int(x) for x in _split_csv(args.seeds)],
        "n_var": args.n_var,
        "steps": args.steps,
        "sigma": args.sigma,
        "cma_lambda": args.cma_lambda,
    }
    report = run(options)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "single_objective_report.json"
    md_path = out / "single_objective_report.md"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    md_path.write_text(build_markdown(report), encoding="utf-8")
    print(f"[ok] wrote {json_path} and {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
