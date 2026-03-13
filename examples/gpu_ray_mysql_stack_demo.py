"""Integrated demo: GPU evaluation template + Ray distributed + MySQL run logger.

This is a minimal wiring example. It demonstrates one stack, not a production recipe:
- GPU evaluation plugin (short-circuit evaluate_population when GPU path is available)
- Ray distributed backend (solver parallel evaluator path)
- MySQL run logger (run metadata persistence)
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime
from typing import Any, Dict, Sequence

import numpy as np

from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.adapters import AlgorithmAdapter
from nsgablack.plugins import (
    BenchmarkHarnessConfig,
    BenchmarkHarnessPlugin,
    GpuEvaluationTemplateConfig,
    GpuEvaluationTemplatePlugin,
    MySQLRunLoggerConfig,
    MySQLRunLoggerPlugin,
)
from nsgablack.utils.parallel import with_parallel_evaluation
from nsgablack.utils.wiring import attach_ray_parallel


class DemoGpuProblem(BlackBoxProblem):
    def __init__(self, dimension: int = 16) -> None:
        bounds = {f"x{i}": (-5.0, 5.0) for i in range(int(dimension))}
        super().__init__(name="gpu_ray_mysql_demo_problem", dimension=int(dimension), bounds=bounds)

    def evaluate(self, x):
        arr = np.asarray(x, dtype=float).reshape(-1)
        return np.array([float(np.sum(arr * arr))], dtype=float)

    def evaluate_gpu_batch(self, population: np.ndarray, *, backend: str, device: str = "cuda:0"):
        pop = np.asarray(population, dtype=float)
        if str(backend) == "torch":
            import torch  # type: ignore

            t = torch.as_tensor(pop, dtype=torch.float32, device=device)
            out = torch.sum(t * t, dim=1, keepdim=True)
            return out.detach().cpu().numpy()
        if str(backend) == "cupy":
            import cupy as cp  # type: ignore

            c = cp.asarray(pop, dtype=cp.float32)
            out = cp.sum(c * c, axis=1, keepdims=True)
            return cp.asnumpy(out)
        # fallback path for unexpected backend value
        return np.sum(pop * pop, axis=1, keepdims=True)


class RandomSearchAdapter(AlgorithmAdapter):
    def __init__(self, name: str = "random_search_adapter", seed: int = 7) -> None:
        super().__init__(name=name)
        self.rng = np.random.default_rng(int(seed))

    def propose(self, solver: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        _ = context
        out = []
        lows = np.array([solver.var_bounds[f"x{i}"][0] for i in range(solver.dimension)], dtype=float)
        highs = np.array([solver.var_bounds[f"x{i}"][1] for i in range(solver.dimension)], dtype=float)
        for _ in range(int(getattr(solver, "pop_size", 32))):
            out.append(self.rng.uniform(lows, highs).astype(float))
        return out

    def update(self, solver: Any, candidates, objectives, violations, context: Dict[str, Any]) -> None:
        _ = (solver, candidates, objectives, violations, context)
        return None


def build_solver(args: argparse.Namespace):
    ParallelComposable = with_parallel_evaluation(ComposableSolver)
    use_ray = bool(args.enable_ray)
    parallel_backend = "ray" if use_ray else "thread"
    problem_factory = (lambda: DemoGpuProblem(dimension=int(args.dimension))) if use_ray else None
    solver = ParallelComposable(
        problem=DemoGpuProblem(dimension=int(args.dimension)),
        adapter=RandomSearchAdapter(seed=int(args.seed)),
        enable_parallel=True,
        parallel_backend=parallel_backend,
        parallel_max_workers=int(args.max_workers),
        parallel_chunk_size=8,
        parallel_precheck=True,
        parallel_strict=False,
        parallel_thread_bias_isolation=str(args.parallel_thread_bias_isolation),
        parallel_problem_factory=problem_factory,
    )
    solver.set_max_steps(int(args.steps))
    solver.set_solver_hyperparams(pop_size=int(args.pop_size))

    run_id = f"gpu_ray_mysql_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    solver.add_plugin(BenchmarkHarnessPlugin(config=BenchmarkHarnessConfig(output_dir="runs", run_id=run_id)))

    # GPU short-circuit template plugin. If GPU path is unavailable, it returns None and solver keeps default path.
    solver.add_plugin(
        GpuEvaluationTemplatePlugin(
            config=GpuEvaluationTemplateConfig(
                preferred_backend=str(args.gpu_backend),
                device=str(args.gpu_device),
                fallback_to_solver_eval=True,
                warn_on_fallback=True,
            )
        )
    )

    if use_ray:
        attach_ray_parallel(
            solver,
            problem_factory=problem_factory,
            max_workers=int(args.max_workers),
            strict=False,
        )

    if bool(args.enable_mysql):
        solver.add_plugin(
            MySQLRunLoggerPlugin(
                config=MySQLRunLoggerConfig(
                    host=os.getenv("NSGABLACK_MYSQL_HOST", "127.0.0.1"),
                    port=int(os.getenv("NSGABLACK_MYSQL_PORT", "3306")),
                    user=os.getenv("NSGABLACK_MYSQL_USER", "root"),
                    password=os.getenv("NSGABLACK_MYSQL_PASSWORD", "20041123"),
                    database=os.getenv("NSGABLACK_MYSQL_DB", "nsgablack"),
                    table=os.getenv("NSGABLACK_MYSQL_TABLE", "nsgablack_runs"),
                )
            )
        )
    return solver


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Integrated GPU + Ray + MySQL stack demo")
    p.add_argument("--steps", type=int, default=40)
    p.add_argument("--pop-size", type=int, default=64)
    p.add_argument("--dimension", type=int, default=16)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--gpu-backend", choices=["auto", "torch", "cupy"], default="auto")
    p.add_argument("--gpu-device", default="cuda:0")
    p.add_argument("--max-workers", type=int, default=4)
    p.add_argument(
        "--parallel-thread-bias-isolation",
        choices=["deepcopy", "disable_cache", "off"],
        default="deepcopy",
        help="Thread backend bias isolation strategy.",
    )
    p.add_argument("--enable-ray", action="store_true", default=False)
    p.add_argument("--enable-mysql", action="store_true", default=False)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    solver = build_solver(args)
    result = solver.run()
    print("done:", result.get("status"), "steps=", result.get("steps"), "best=", getattr(solver, "best_objective", None))


if __name__ == "__main__":
    main()
