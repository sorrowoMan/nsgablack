"""Self-contained multi-objective quality benchmark (no pymoo).

Runs the framework's population adapters on analytical ZDT/DTLZ problems at a
fixed evaluation budget, measures IGD and hypervolume against analytical
reference fronts, and aggregates statistics across seeds.

Usage::

    python -m benchmarks.quality_suite \
        --problems zdt1,zdt2,zdt3,zdt6,dtlz2_2,dtlz2_3,dtlz1_3,dtlz4_3 \
        --algorithms nsga2,nsga3,spea2,moead \
        --seeds 11,29,47 \
        --population-size 100 --steps 100

The default operator recipe (Gaussian mutation sigma=0.08 + arithmetic
crossover rate 0.9) matches the framework's existing transparency benchmark and
is *not* the literature-standard SBX/PM recipe; this is stated in the report.
"""
from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path

import numpy as np

from blackbase.resources import ResourceContext
from nsgablack.adapters.moead import MOEADAdapter
from nsgablack.adapters.nsga2 import NSGA2Adapter
from nsgablack.adapters.nsga3 import NSGA3Adapter
from nsgablack.adapters.spea2 import SPEA2Adapter
from nsgablack.core import ComposableSolver
from nsgablack.representation import ClipRepair, GaussianMutation, RepresentationPipeline

from benchmarks.quality_metrics import hypervolume, igd, pareto_filter
from benchmarks.quality_problems import (
    DTLZProblem,
    ZDTProblem,
    dtlz_reference_front,
    zdt_reference_front,
)

SUITE = {
    "zdt1": {"problem": lambda: ZDTProblem(1), "n_obj": 2, "n_var": 30,
             "front": lambda: zdt_reference_front(1), "ref": [1.1, 11.0]},
    "zdt2": {"problem": lambda: ZDTProblem(2), "n_obj": 2, "n_var": 30,
             "front": lambda: zdt_reference_front(2), "ref": [1.1, 11.0]},
    "zdt3": {"problem": lambda: ZDTProblem(3), "n_obj": 2, "n_var": 30,
             "front": lambda: zdt_reference_front(3), "ref": [1.1, 11.0]},
    "zdt6": {"problem": lambda: ZDTProblem(6), "n_obj": 2, "n_var": 30,
             "front": lambda: zdt_reference_front(6), "ref": [1.1, 11.0]},
    "dtlz2_2": {"problem": lambda: DTLZProblem(2, 2), "n_obj": 2, "n_var": 11,
                "front": lambda: dtlz_reference_front(2, 2), "ref": [4.0, 4.0]},
    "dtlz2_3": {"problem": lambda: DTLZProblem(2, 3), "n_obj": 3, "n_var": 12,
                "front": lambda: dtlz_reference_front(2, 3), "ref": [4.0, 4.0, 4.0]},
    "dtlz1_3": {"problem": lambda: DTLZProblem(1, 3), "n_obj": 3, "n_var": 12,
                "front": lambda: dtlz_reference_front(1, 3), "ref": [1.0, 1.0, 1.0]},
    "dtlz4_3": {"problem": lambda: DTLZProblem(4, 3), "n_obj": 3, "n_var": 12,
                "front": lambda: dtlz_reference_front(4, 3), "ref": [4.0, 4.0, 4.0]},
}

ALGORITHMS = ("nsga2", "nsga3", "spea2", "moead")

# NSGA-III requires reference directions that only make sense for >= 3
# objectives, so it is only paired with many-objective problems.
ALGORITHM_MIN_OBJECTIVES = {"nsga3": 3}


class FixedInitializer:
    """Direct initializer with an explicit cursor; mirrors the transparency suite.

    Pinning the same initial population per (seed, size, n_var) makes the
    algorithm comparison fair: every algorithm on a given problem+seed starts
    from the identical population.
    """

    stateless = False

    def __init__(self, values):
        self.values = np.array(values, dtype=float, copy=True)
        self.cursor = 0

    def checkpoint_identity(self):
        return {"schema": "quality_suite.fixed_initializer/v1",
                "shape": list(self.values.shape),
                "sha256": sha256(self.values.tobytes()).hexdigest()}

    def initialize(self, problem, context=None):
        if self.cursor >= len(self.values):
            raise ValueError("quality initializer exhausted")
        result = np.array(self.values[self.cursor], copy=True)
        self.cursor += 1
        return result

    def get_state(self):
        return {"cursor": self.cursor}

    def set_state(self, state):
        if (set(state) != {"cursor"} or type(state["cursor"]) is not int
                or not 0 <= state["cursor"] <= len(self.values)):
            raise ValueError("invalid quality initializer cursor")
        self.cursor = state["cursor"]


def initial_population(seed, size, n_var):
    return np.random.default_rng(np.random.SeedSequence([int(seed), 7919])).uniform(
        0.0, 1.0, (int(size), int(n_var)))


def make_adapter(algorithm, seed, population_size, n_var, nsga3_divisions=12,
                 initial_values=None):
    if initial_values is None:
        values = initial_population(seed, population_size, n_var)
    else:
        values = np.asarray(initial_values, dtype=float)
    initializer = FixedInitializer(values)
    common = {"name": algorithm, "population_size": population_size, "initializer": initializer}
    if algorithm == "nsga2":
        return NSGA2Adapter(**common, offspring_size=population_size, crossover_rate=0.9,
                            mutator=GaussianMutation(sigma=0.08))
    if algorithm == "nsga3":
        return NSGA3Adapter(**common, offspring_size=population_size, crossover_rate=0.9,
                            mutator=GaussianMutation(sigma=0.08), divisions=int(nsga3_divisions))
    if algorithm == "spea2":
        return SPEA2Adapter(**common, offspring_size=population_size, crossover_rate=0.9,
                            mutator=GaussianMutation(sigma=0.08),
                            archive_size=population_size, k_nearest=1)
    if algorithm == "moead":
        return MOEADAdapter(**common, batch_size=population_size, neighborhood_size=5,
                            delta=0.9, nr=2, variation="de", de_F=0.5, de_CR=0.9,
                            random_seed=int(seed))
    raise ValueError(f"unknown algorithm: {algorithm}")


def run_to_snapshot(algorithm, problem_name, seed, population_size, steps,
                    nsga3_divisions=12, initial_values=None):
    """Run one algorithm for ``steps`` and return (X, F, V, evaluation_count)."""
    spec = SUITE[problem_name]
    problem = spec["problem"]()
    adapter = make_adapter(algorithm, seed, population_size, spec["n_var"],
                           nsga3_divisions=nsga3_divisions, initial_values=initial_values)
    pipeline = RepresentationPipeline(repair=ClipRepair(0.0, 1.0))
    solver = ComposableSolver(
        problem,
        adapter=adapter,
        representation_pipeline=pipeline,
        resource_context=ResourceContext(namespace="quality_suite_local",
                                         grant={"threads": 1, "workers": 1}),
        plugin_strict=True,
        snapshot_strict=True,
    )
    solver.set_random_seed(int(seed))
    solver.enable_progress_log = False
    solver.pop_size = int(population_size)
    solver.run(max_steps=int(steps))
    x, f, v = solver.adapter.get_population_snapshot()
    return (np.asarray(x, dtype=float), np.asarray(f, dtype=float),
            np.asarray(v, dtype=float).reshape(-1), int(solver.evaluation_count))


def _measure(problem_name, f, v):
    spec = SUITE[problem_name]
    feasible = f[v <= 1e-10] if v.size else f
    if feasible.ndim == 1:
        feasible = feasible.reshape(1, -1)
    front = pareto_filter(feasible) if feasible.size else np.zeros((0, spec["n_obj"]))
    reference = spec["front"]()
    return (front, float(igd(front, reference)),
            float(hypervolume(front, np.asarray(spec["ref"], dtype=float))))


def run_one(algorithm, problem_name, seed, population_size, steps, nsga3_divisions=12):
    x, f, v, evaluations = run_to_snapshot(algorithm, problem_name, seed, population_size,
                                           steps, nsga3_divisions=nsga3_divisions)
    front, igd_value, hv_value = _measure(problem_name, f, v)
    spec = SUITE[problem_name]
    return {
        "algorithm": algorithm,
        "problem": problem_name,
        "seed": int(seed),
        "n_obj": spec["n_obj"],
        "n_var": spec["n_var"],
        "evaluations": evaluations,
        "front_size": int(front.shape[0]),
        "igd": igd_value,
        "hv": hv_value,
    }


def _stats(values):
    arr = np.asarray(values, dtype=float)
    return {
        "median": float(np.median(arr)),
        "q1": float(np.percentile(arr, 25)),
        "q3": float(np.percentile(arr, 75)),
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "values": [float(x) for x in arr],
    }


def _compatible(algorithm, problem_name):
    min_obj = ALGORITHM_MIN_OBJECTIVES.get(algorithm, 1)
    return SUITE[problem_name]["n_obj"] >= min_obj


def run(options):
    problems = list(options["problems"])
    algorithms = list(options["algorithms"])
    seeds = [int(s) for s in options["seeds"]]
    population_size = int(options["population_size"])
    steps = int(options["steps"])
    nsga3_divisions = int(options.get("nsga3_divisions", 12))

    unknown = [p for p in problems if p not in SUITE]
    if unknown:
        raise ValueError(f"unknown problems: {unknown}")
    unknown_a = [a for a in algorithms if a not in ALGORITHMS]
    if unknown_a:
        raise ValueError(f"unknown algorithms: {unknown_a}")
    if population_size < 5 or steps < 2:
        raise ValueError("quality benchmark requires population_size>=5 and steps>=2")
    if not seeds:
        raise ValueError("quality benchmark requires at least one seed")

    skipped = [f"{algorithm}x{problem}" for algorithm in algorithms for problem in problems
               if not _compatible(algorithm, problem)]

    per_seed = []
    for algorithm in algorithms:
        for problem in problems:
            if not _compatible(algorithm, problem):
                continue
            for seed in seeds:
                per_seed.append(run_one(algorithm, problem, seed, population_size, steps,
                                        nsga3_divisions=nsga3_divisions))

    rows = []
    for algorithm in algorithms:
        for problem in problems:
            if not _compatible(algorithm, problem):
                continue
            entries = [r for r in per_seed
                       if r["algorithm"] == algorithm and r["problem"] == problem]
            rows.append({
                "algorithm": algorithm,
                "problem": problem,
                "n_obj": entries[0]["n_obj"],
                "n_var": entries[0]["n_var"],
                "population_size": population_size,
                "steps": steps,
                "budget": population_size * steps,
                "seeds": seeds,
                "igd": _stats([e["igd"] for e in entries]),
                "hv": _stats([e["hv"] for e in entries]),
                "per_seed": entries,
            })

    return {
        "schema": "nsgablack.quality_suite/v1",
        "config": {
            "problems": problems,
            "algorithms": algorithms,
            "seeds": seeds,
            "population_size": population_size,
            "steps": steps,
            "evaluation_budget": population_size * steps,
            "nsga3_divisions": nsga3_divisions,
            "skipped_combinations": skipped,
            "operators": ("GaussianMutation(sigma=0.08) + arithmetic crossover (rate 0.9); "
                          "MOEAD uses DE rand/1/bin variation"),
            "metrics": "IGD (analytical reference front) + exact hypervolume (documented reference point)",
            "note": ("Self-contained; no pymoo dependency. pymoo baseline comparison is blocked "
                     "by unavailable network access in the sandbox; scalarized DE, SBX/polynomial "
                     "mutation and the fusion/ensemble comparison are future additions."),
        },
        "results": rows,
    }


def _fmt(stats):
    return f"{stats['median']:.4f} ({stats['q1']:.4f}–{stats['q3']:.4f})"


def build_markdown(report):
    cfg = report["config"]
    lines = [
        "# nsgablack Quality Benchmark",
        "",
        f"- problems: {', '.join(cfg['problems'])}",
        f"- algorithms: {', '.join(cfg['algorithms'])}",
        f"- seeds: {', '.join(str(s) for s in cfg['seeds'])}",
        f"- population size: {cfg['population_size']} · steps: {cfg['steps']} "
        f"· evaluation budget: {cfg['evaluation_budget']}",
        f"- operators: {cfg['operators']}",
        "",
        "IGD is lower-better, hypervolume is higher-better. Values are "
        "median (Q1–Q3) across seeds.",
        "",
        "| Algorithm | Problem | IGD (median, Q1–Q3) | HV (median, Q1–Q3) |",
        "|---|---|---|---|",
    ]
    for row in report["results"]:
        lines.append(f"| {row['algorithm']} | {row['problem']} | "
                     f"{_fmt(row['igd'])} | {_fmt(row['hv'])} |")
    lines += ["", "## Per-seed detail", "",
              "| Algorithm | Problem | Seed | Evaluations | Front size | IGD | HV |",
              "|---|---|---:|---:|---:|---:|---:|"]
    for row in report["results"]:
        for entry in row["per_seed"]:
            lines.append(f"| {entry['algorithm']} | {entry['problem']} | {entry['seed']} | "
                         f"{entry['evaluations']} | {entry['front_size']} | "
                         f"{entry['igd']:.6f} | {entry['hv']:.6f} |")
    lines.append("")
    return "\n".join(lines)


def _split_csv(value):
    return [part.strip() for part in str(value).split(",") if part.strip()]


def main(argv=None):
    parser = argparse.ArgumentParser(description="nsgablack multi-objective quality benchmark")
    parser.add_argument("--problems", default="zdt1,zdt2,zdt3,zdt6,dtlz2_2,dtlz2_3,dtlz1_3,dtlz4_3",
                        help="comma-separated problem keys")
    parser.add_argument("--algorithms", default="nsga2,nsga3,spea2,moead",
                        help="comma-separated algorithm names")
    parser.add_argument("--seeds", default="11,29,47", help="comma-separated integer seeds")
    parser.add_argument("--population-size", type=int, default=100)
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--nsga3-divisions", type=int, default=12,
                        help="NSGA-III reference-direction divisions (default 12)")
    parser.add_argument("--output-dir", default="runs/quality")
    args = parser.parse_args(argv)

    options = {
        "problems": _split_csv(args.problems),
        "algorithms": _split_csv(args.algorithms),
        "seeds": [int(x) for x in _split_csv(args.seeds)],
        "population_size": args.population_size,
        "steps": args.steps,
        "nsga3_divisions": args.nsga3_divisions,
    }
    report = run(options)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "quality_report.json"
    md_path = out / "quality_report.md"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    md_path.write_text(build_markdown(report), encoding="utf-8")
    print(f"[ok] wrote {json_path} and {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
