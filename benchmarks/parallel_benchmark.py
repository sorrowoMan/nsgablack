# -*- coding: utf-8 -*-
"""ParallelEvaluator benchmark script.

Run from the directory *above* the repo (recommended), or after `pip install -e .`:

    python nsgablack/benchmarks/parallel_benchmark.py --backend process --workers 8
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np


def _ensure_importable(start: Path | None = None) -> None:
    start = (start or Path(__file__)).resolve()
    cur = start
    for _ in range(10):
        if (cur / "__init__.py").exists() and (cur / "pyproject.toml").exists():
            parent = cur.parent
            if str(parent) not in sys.path:
                sys.path.insert(0, str(parent))
            return
        cur = cur.parent


_ensure_importable(Path(__file__))

from nsgablack.core.base import BlackBoxProblem  # noqa: E402
from nsgablack.utils.parallel import ParallelEvaluator  # noqa: E402


class SphereProblem(BlackBoxProblem):
    def __init__(self, dim: int = 32, *, sleep_ms: float = 0.0) -> None:
        super().__init__()
        self.dim = int(dim)
        self.sleep_ms = float(sleep_ms)
        self.bounds = [(-5.0, 5.0)] * self.dim

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        if self.sleep_ms > 0:
            time.sleep(self.sleep_ms / 1000.0)
        return [float(np.sum(x * x))]


@dataclass
class BenchmarkResult:
    backend: str
    workers: int
    chunk: int | None
    n: int
    dim: int
    wall_s: float

    @property
    def eval_per_s(self) -> float:
        return float(self.n) / float(self.wall_s) if self.wall_s > 1e-12 else 0.0


def run_once(*, backend: str, workers: int, chunk: int | None, n: int, dim: int, sleep_ms: float) -> BenchmarkResult:
    problem = SphereProblem(dim=dim, sleep_ms=sleep_ms)
    pop = np.random.uniform(-5, 5, size=(int(n), int(dim))).astype(float)

    evaluator = ParallelEvaluator(
        backend=str(backend),
        max_workers=int(workers),
        chunk_size=chunk,
        verbose=False,
    )

    t0 = time.time()
    evaluator.evaluate_population(pop, problem)
    t1 = time.time()
    return BenchmarkResult(
        backend=str(backend),
        workers=int(workers),
        chunk=chunk,
        n=int(n),
        dim=int(dim),
        wall_s=float(t1 - t0),
    )


def main() -> None:
    p = argparse.ArgumentParser(description="ParallelEvaluator micro-benchmark")
    p.add_argument("--backend", choices=["thread", "process", "joblib", "ray"], default="process")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--chunk", type=int, default=None)
    p.add_argument("--n", type=int, default=256, help="population size")
    p.add_argument("--dim", type=int, default=32)
    p.add_argument("--repeat", type=int, default=3)
    p.add_argument("--sleep-ms", type=float, default=0.0, help="simulate expensive evaluation (ms)")
    args = p.parse_args()

    print(
        f"[bench] backend={args.backend} workers={args.workers} chunk={args.chunk} "
        f"n={args.n} dim={args.dim} sleep_ms={args.sleep_ms}"
    )
    results = []
    for i in range(int(args.repeat)):
        r = run_once(
            backend=args.backend,
            workers=args.workers,
            chunk=args.chunk,
            n=args.n,
            dim=args.dim,
            sleep_ms=args.sleep_ms,
        )
        results.append(r)
        print(f"[run {i}] wall_s={r.wall_s:.4f} eval/s={r.eval_per_s:.2f}")

    walls = [r.wall_s for r in results]
    walls.sort()
    p50 = walls[len(walls) // 2]
    print(f"[summary] repeats={len(results)} wall_s_p50={p50:.4f}")


if __name__ == "__main__":
    main()

