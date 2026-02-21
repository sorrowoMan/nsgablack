"""
Monte Carlo + Dynamic Programming demo (robust path planning).

This example shows a simple grid path problem with stochastic weather costs.
- DP computes a path on expected cost.
- MonteCarloEvaluationPlugin estimates robust cost (CVaR) for candidates.

Run:
  python examples/monte_carlo_dp_robust_demo.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable, Tuple

import numpy as np


def _ensure_importable() -> None:
    try:
        import nsgablack  # noqa: F401
        return
    except Exception:
        pass
    here = Path(__file__).resolve()
    repo_parent = str(here.parent.parent.parent)
    if repo_parent not in sys.path:
        sys.path.insert(0, repo_parent)


_ensure_importable()

from nsgablack.core.base import BlackBoxProblem  # noqa: E402
from nsgablack.core.composable_solver import ComposableSolver  # noqa: E402
from nsgablack.core.adapters.algorithm_adapter import AlgorithmAdapter  # noqa: E402
from nsgablack.plugins import (  # noqa: E402
    MonteCarloEvaluationPlugin,
    MonteCarloEvaluationConfig,
)


class StochasticGridPath(BlackBoxProblem):
    def __init__(
        self,
        *,
        rows: int = 5,
        cols: int = 5,
        base_cost: float = 1.0,
        storm_prob: np.ndarray,
        storm_penalty: np.ndarray,
    ) -> None:
        self.rows = int(rows)
        self.cols = int(cols)
        self.base_cost = float(base_cost)
        self.storm_prob = np.asarray(storm_prob, dtype=float)
        self.storm_penalty = np.asarray(storm_penalty, dtype=float)
        steps = (self.rows - 1) + (self.cols - 1)
        bounds = {f"x{i}": [0.0, 1.0] for i in range(steps)}
        super().__init__(name="stochastic_grid_path", dimension=steps, bounds=bounds, objectives=["min"])

    def evaluate(self, x):
        x = np.asarray(x, dtype=float).ravel()
        if x.size != self.dimension:
            return 1e9
        actions = (x >= 0.5).astype(int)  # 0=right, 1=down

        r, c = 0, 0
        total = 0.0
        for a in actions:
            if a == 0:
                c += 1
            else:
                r += 1
            if r >= self.rows or c >= self.cols:
                return 1e9
            total += self.base_cost
            if np.random.rand() < float(self.storm_prob[r, c]):
                total += float(self.storm_penalty[r, c])
        if r != self.rows - 1 or c != self.cols - 1:
            return 1e9
        return float(total)


class FixedPathAdapter(AlgorithmAdapter):
    def __init__(self, path: np.ndarray, name: str) -> None:
        super().__init__(name=name)
        self.path = np.asarray(path, dtype=float)

    def propose(self, solver, context):
        return [self.path]


def build_storm_grid(rows: int, cols: int) -> Tuple[np.ndarray, np.ndarray]:
    storm_prob = np.zeros((rows, cols), dtype=float)
    storm_penalty = np.zeros((rows, cols), dtype=float)
    # stormy band in the middle
    for r in range(1, rows - 1):
        for c in range(1, cols - 1):
            storm_prob[r, c] = 0.4
            storm_penalty[r, c] = 6.0
    return storm_prob, storm_penalty


def dp_path(cost_grid: np.ndarray) -> np.ndarray:
    rows, cols = cost_grid.shape
    dp = np.full((rows, cols), np.inf, dtype=float)
    move = np.zeros((rows, cols), dtype=int)  # 0=from left, 1=from up
    dp[0, 0] = 0.0
    for r in range(rows):
        for c in range(cols):
            if r == 0 and c == 0:
                continue
            best = np.inf
            if r > 0:
                cand = dp[r - 1, c] + cost_grid[r, c]
                if cand < best:
                    best = cand
                    move[r, c] = 1
            if c > 0:
                cand = dp[r, c - 1] + cost_grid[r, c]
                if cand < best:
                    best = cand
                    move[r, c] = 0
            dp[r, c] = best

    actions = []
    r, c = rows - 1, cols - 1
    while r > 0 or c > 0:
        if move[r, c] == 1:
            actions.append(1)  # came from up -> move down
            r -= 1
        else:
            actions.append(0)  # came from left -> move right
            c -= 1
    actions.reverse()
    return np.asarray(actions, dtype=float)


def baseline_path(rows: int, cols: int) -> np.ndarray:
    rights = [0.0] * (cols - 1)
    downs = [1.0] * (rows - 1)
    return np.asarray(rights + downs, dtype=float)


def mc_stats(problem: StochasticGridPath, path: np.ndarray, samples: int = 200) -> Tuple[float, float, float]:
    vals = []
    for _ in range(int(samples)):
        vals.append(problem.evaluate(path))
    arr = np.asarray(vals, dtype=float)
    mean = float(np.mean(arr))
    std = float(np.std(arr))
    alpha = 0.2
    k = max(1, int(np.ceil(alpha * arr.size)))
    cvar = float(np.mean(np.sort(arr)[:k]))
    return mean, std, cvar


def run_solver(problem: StochasticGridPath, adapter: AlgorithmAdapter, label: str) -> float:
    solver = ComposableSolver(problem=problem, adapter=adapter)
    solver.set_max_steps(1)
    solver.add_plugin(
        MonteCarloEvaluationPlugin(
            config=MonteCarloEvaluationConfig(mc_samples=64, reduce="cvar", cvar_alpha=0.2, random_seed=7)
        )
    )
    solver.run()
    obj = float(solver.objectives[0][0])
    print(f"[{label}] solver objective (CVaR) = {obj:.4f}")
    return obj


def main() -> None:
    rows, cols = 5, 5
    storm_prob, storm_penalty = build_storm_grid(rows, cols)
    problem = StochasticGridPath(
        rows=rows,
        cols=cols,
        base_cost=1.0,
        storm_prob=storm_prob,
        storm_penalty=storm_penalty,
    )

    expected_cost_grid = 1.0 + storm_prob * storm_penalty
    dp = dp_path(expected_cost_grid)
    base = baseline_path(rows, cols)

    print("MC stats (mean/std/CVaR) for baseline vs DP path:")
    m1, s1, c1 = mc_stats(problem, base, samples=200)
    m2, s2, c2 = mc_stats(problem, dp, samples=200)
    print(f"  baseline: mean={m1:.3f} std={s1:.3f} cvar={c1:.3f}")
    print(f"  dp-path : mean={m2:.3f} std={s2:.3f} cvar={c2:.3f}")

    run_solver(problem, FixedPathAdapter(base, name="baseline"), label="baseline")
    run_solver(problem, FixedPathAdapter(dp, name="dp_path"), label="dp_path")


if __name__ == "__main__":
    main()

