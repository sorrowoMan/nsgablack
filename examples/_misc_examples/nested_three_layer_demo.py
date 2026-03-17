"""
Three-layer nested workflow demo (L1 -> L2 -> L3).

What this demonstrates:
1) L1 outer solver only sees evaluate_individual result.
2) L2 inner workflow is executed by problem.inner_runtime_evaluator.
3) L2 calls L3 numerical solve (Newton/Broyden style residual solve).
4) ContractBridgePlugin writes L3 fields directly back to L1 layer context.

Run:
  python examples/nested_three_layer_demo.py
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path
from typing import Dict, Mapping

import numpy as np
from scipy import optimize


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
from nsgablack.adapters import AlgorithmAdapter  # noqa: E402
from nsgablack.core.nested_solver import InnerRuntimeConfig, TaskInnerRuntimeEvaluator  # noqa: E402
from nsgablack.plugins import (  # noqa: E402
    BridgeRule,
    ContractBridgePlugin,
    TimeoutBudgetConfig,
    TimeoutBudgetPlugin,
)


def _solve_level3_newton(target: float) -> Dict[str, float]:
    """L3: pure numerical solver (residual = 0)."""

    def residual(y: np.ndarray) -> np.ndarray:
        val = float(y[0])
        return np.array([val * val - target], dtype=float)

    out = optimize.root(residual, x0=np.array([1.0], dtype=float), method="hybr")
    y = float(out.x[0])
    r = float(residual(np.array([y], dtype=float))[0])
    return {
        "l3_status": "ok" if bool(out.success) else "failed",
        "l3_root": y,
        "l3_residual": abs(r),
        "l3_iters": float(getattr(out, "nfev", 0)),
    }


def _run_level2(candidate: np.ndarray, generation: int) -> Mapping[str, object]:
    """L2: workflow that calls L3 and assembles an inner result packet."""
    x0 = float(candidate[0])
    l2_target = x0 * x0 + 0.5
    l3 = _solve_level3_newton(l2_target)

    # L2 objective combines local target and L3 solve quality.
    objective = (float(l3["l3_root"]) - 1.2) ** 2 + abs(x0 - 0.3) + 5.0 * float(l3["l3_residual"])
    return {
        "status": "ok" if l3["l3_status"] == "ok" else "failed",
        "objective": float(objective),
        "violation": 0.0,
        "generation": int(generation),
        "l2_target": float(l2_target),
        # L3 fields that will be bridged directly to L1.
        "l3_root": float(l3["l3_root"]),
        "l3_residual": float(l3["l3_residual"]),
        "l3_iters": float(l3["l3_iters"]),
    }


class NestedOuterProblem(BlackBoxProblem):
    """L1 outer problem. The real evaluation is delegated to inner workflow."""

    def __init__(self) -> None:
        super().__init__(name="nested_three_layer", dimension=1, bounds={"x0": (-2.0, 2.0)})

    def evaluate(self, x):
        # Fallback only. Problem inner runtime evaluator should bypass this path.
        x0 = float(np.asarray(x, dtype=float)[0])
        return float((x0 - 0.3) ** 2 + 100.0)

    def build_inner_task(self, x, eval_context):
        candidate = np.asarray(x, dtype=float).reshape(-1)
        generation = int(eval_context.get("generation", 0))
        return {"run_inner": lambda _p, _s, _ctx: _run_level2(candidate, generation)}

    def evaluate_from_inner_result(self, x, inner_result, eval_context):
        _ = (x, eval_context)
        return float(inner_result.get("objective", 1e6))


class RandomSearchAdapter(AlgorithmAdapter):
    def __init__(self) -> None:
        super().__init__(name="random_search")
        self.rng = np.random.default_rng(7)

    def propose(self, solver, context):
        _ = context
        low, high = -2.0, 2.0
        out = []
        for _ in range(int(getattr(solver, "pop_size", 8))):
            out.append(np.array([float(self.rng.uniform(low, high))], dtype=float))
        return out


def build_solver() -> ComposableSolver:
    solver = ComposableSolver(problem=NestedOuterProblem(), adapter=RandomSearchAdapter())
    solver.set_solver_hyperparams(pop_size=10)
    solver.set_max_steps(20)

    # Guard inner execution budget (L2 layer).
    solver.add_plugin(
        TimeoutBudgetPlugin(
            config=TimeoutBudgetConfig(layer="L2", max_calls=400, time_budget_ms=30_000, fail_closed=True)
        )
    )

    # Map L2/L3 output fields directly into L1 layer context.
    solver.add_plugin(
        ContractBridgePlugin(
            rules=[
                BridgeRule("l2_target", "l2_target", target_layer="L1"),
                BridgeRule("l3_root", "l3_root", target_layer="L1"),
                BridgeRule("l3_residual", "l3_residual", target_layer="L1"),
                BridgeRule("l3_iters", "l3_iters", target_layer="L1"),
                BridgeRule("status", "inner_status", target_layer="L1"),
            ]
        )
    )

    # Execute nested inner workflow from L1 evaluation.
    solver.problem.inner_runtime_evaluator = TaskInnerRuntimeEvaluator(
        config=InnerRuntimeConfig(source_layer="L2", target_layer="L1")
    )
    return solver


def main() -> None:
    solver = build_solver()
    result = solver.run()

    best = float(solver.best_objective) if solver.best_objective is not None else math.inf
    layer_ctx = getattr(solver, "_layer_contexts", {})
    l1 = layer_ctx.get("L1", {})
    bridge_log = getattr(solver, "_bridge_log", [])

    print("Nested demo completed.")
    print(f"status={result.get('status')} steps={result.get('steps')} best_objective={best:.6f}")
    print("L1 bridged fields:", {k: l1.get(k) for k in ("inner_status", "l2_target", "l3_root", "l3_residual", "l3_iters")})
    print(f"bridge_records={len(bridge_log)}")
    print(f"logs_dir={os.path.abspath('runs')}")


if __name__ == "__main__":
    main()
