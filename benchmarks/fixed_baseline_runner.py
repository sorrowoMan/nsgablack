from __future__ import annotations

import argparse
import csv
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import numpy as np

from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.solver import BlackBoxSolverNSGAII
from nsgablack.utils.engineering.file_io import atomic_write_json
from nsgablack.utils.engineering.schema_version import stamp_schema


@dataclass(frozen=True)
class BaselineScenario:
    name: str
    dimension: int
    pop_size: int
    generations: int


DEFAULT_SCENARIOS: tuple[BaselineScenario, ...] = (
    BaselineScenario(name="small", dimension=8, pop_size=40, generations=20),
    BaselineScenario(name="medium", dimension=24, pop_size=80, generations=30),
    BaselineScenario(name="large", dimension=60, pop_size=140, generations=40),
)


class SphereProblem(BlackBoxProblem):
    def __init__(self, dimension: int) -> None:
        bounds = [(-5.0, 5.0)] * int(dimension)
        super().__init__(
            name=f"Sphere-{dimension}",
            dimension=int(dimension),
            objectives=["minimize"],
            bounds=bounds,
        )

    def evaluate(self, x):
        arr = np.asarray(x, dtype=float)
        return np.array([float(np.sum(arr ** 2))], dtype=float)

    def evaluate_constraints(self, x):
        return np.zeros(0, dtype=float)


def _resolve_best_score(result: Dict[str, object]) -> float:
    objs = result.get("pareto_objectives")
    if objs is None:
        return float("nan")
    arr = np.asarray(objs, dtype=float)
    if arr.size == 0:
        return float("nan")
    if arr.ndim == 1:
        return float(np.min(arr))
    return float(np.min(arr[:, 0]))


def run_scenario(scenario: BaselineScenario, *, seed: int) -> Dict[str, float]:
    np.random.seed(int(seed))

    solver = BlackBoxSolverNSGAII(SphereProblem(scenario.dimension))
    solver.pop_size = int(scenario.pop_size)
    solver.max_generations = int(scenario.generations)
    solver.crossover_rate = 0.85
    solver.mutation_rate = 0.15
    solver.enable_progress_log = False
    solver.random_seed = int(seed)

    t0 = time.perf_counter()
    result = solver.run(return_dict=True)
    wall_s = max(0.0, float(time.perf_counter() - t0))

    return {
        "scenario": scenario.name,
        "seed": int(seed),
        "dimension": int(scenario.dimension),
        "pop_size": int(scenario.pop_size),
        "generations": int(scenario.generations),
        "wall_s": float(wall_s),
        "eval_count": int(getattr(solver, "evaluation_count", 0) or 0),
        "best_score": float(_resolve_best_score(result)),
    }


def aggregate(records: List[Dict[str, float]]) -> List[Dict[str, float]]:
    grouped: Dict[str, List[Dict[str, float]]] = {}
    for row in records:
        grouped.setdefault(str(row["scenario"]), []).append(row)

    out: List[Dict[str, float]] = []
    for scenario in sorted(grouped.keys()):
        rows = grouped[scenario]
        wall = [float(r["wall_s"]) for r in rows]
        score = [float(r["best_score"]) for r in rows]
        evals = [int(r["eval_count"]) for r in rows]
        proto = rows[0]
        out.append(
            {
                "scenario": scenario,
                "runs": len(rows),
                "dimension": int(proto["dimension"]),
                "pop_size": int(proto["pop_size"]),
                "generations": int(proto["generations"]),
                "wall_s_median": float(statistics.median(wall)),
                "wall_s_min": float(min(wall)),
                "wall_s_max": float(max(wall)),
                "best_score_median": float(statistics.median(score)),
                "best_score_min": float(min(score)),
                "best_score_max": float(max(score)),
                "eval_count_median": int(statistics.median(evals)),
            }
        )
    return out


def _write_csv(path: Path, rows: List[Dict[str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run_baseline(
    *,
    scenarios: tuple[BaselineScenario, ...] = DEFAULT_SCENARIOS,
    repeats: int = 3,
    base_seed: int = 20260217,
    output_dir: Path = Path("runs/evidence/baseline"),
) -> Dict[str, object]:
    rows: List[Dict[str, float]] = []
    for idx, scenario in enumerate(scenarios):
        for r in range(int(repeats)):
            seed = int(base_seed + idx * 100 + r)
            rows.append(run_scenario(scenario, seed=seed))

    summary_rows = aggregate(rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")

    csv_path = output_dir / f"baseline_raw_{ts}.csv"
    summary_path = output_dir / f"baseline_summary_{ts}.json"
    summary_csv_path = output_dir / f"baseline_summary_{ts}.csv"

    _write_csv(csv_path, rows)
    _write_csv(summary_csv_path, summary_rows)

    payload = {
        "generated_at": ts,
        "base_seed": int(base_seed),
        "repeats": int(repeats),
        "scenarios": [
            {
                "name": s.name,
                "dimension": int(s.dimension),
                "pop_size": int(s.pop_size),
                "generations": int(s.generations),
            }
            for s in scenarios
        ],
        "summary": summary_rows,
        "artifacts": {
            "raw_csv": str(csv_path),
            "summary_csv": str(summary_csv_path),
        },
    }
    payload = stamp_schema(payload, "benchmark_summary")
    atomic_write_json(summary_path, payload, ensure_ascii=False, indent=2, encoding="utf-8")
    return {
        "raw_csv": str(csv_path),
        "summary_csv": str(summary_csv_path),
        "summary_json": str(summary_path),
        "summary": summary_rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run fixed baseline benchmark scenarios.")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20260217)
    parser.add_argument("--output-dir", type=str, default="runs/evidence/baseline")
    args = parser.parse_args(argv)

    report = run_baseline(
        repeats=max(1, int(args.repeats)),
        base_seed=int(args.seed),
        output_dir=Path(args.output_dir).resolve(),
    )
    print(f"raw_csv={report['raw_csv']}")
    print(f"summary_csv={report['summary_csv']}")
    print(f"summary_json={report['summary_json']}")
    for row in report["summary"]:
        print(
            "[baseline] "
            f"{row['scenario']} wall_median={row['wall_s_median']:.3f}s "
            f"best_median={row['best_score_median']:.6f} eval_median={row['eval_count_median']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
