"""并行批量运行工具：headless 与可选 VNS。"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple

import numpy as np

from ...core.base import BlackBoxProblem
from ..headless import run_headless_single_objective

BlackBoxSolverVNS = None  # type: ignore
Backend = Literal["thread", "process"]


def _get_executor(backend: Backend, max_workers: Optional[int]):
    if backend == "thread":
        return ThreadPoolExecutor(max_workers=max_workers)
    return ProcessPoolExecutor(max_workers=max_workers)


def _run_single_headless(args: Tuple[Callable, List[Tuple[float, float]], int, Dict[str, Any]]):
    objective, bounds, run_index, solver_kwargs = args
    res = run_headless_single_objective(objective, bounds, **solver_kwargs)
    fun_val = res.get("fun", None)
    fun = float(fun_val) if fun_val is not None else float("inf")
    return {"index": run_index, "x": res.get("x", None), "fun": fun, "raw": res}


def run_headless_in_parallel(
    objective: Callable,
    bounds,
    n_runs: int = 4,
    backend: Backend = "process",
    max_workers: Optional[int] = None,
    **solver_kwargs: Any,
) -> Dict[str, Any]:
    tasks: List[Tuple[Callable, Any, int, Dict[str, Any]]] = [
        (objective, bounds, i, solver_kwargs) for i in range(n_runs)
    ]

    results: List[Dict[str, Any]] = []
    with _get_executor(backend, max_workers) as executor:
        futures = {executor.submit(_run_single_headless, task): task[2] for task in tasks}
        iterator = as_completed(futures)
        try:
            from tqdm import tqdm  # type: ignore

            iterator = tqdm(iterator, total=len(futures), desc="Parallel headless runs")
        except Exception:
            pass
        for future in iterator:
            results.append(future.result())

    if not results:
        return {"results": [], "best_index": None, "best_x": None, "best_fun": None}

    best_idx = int(np.argmin([item["fun"] for item in results]))
    best = results[best_idx]
    return {
        "results": sorted(results, key=lambda item: item["index"]),
        "best_index": best["index"],
        "best_x": best["x"],
        "best_fun": best["fun"],
    }


def _run_single_vns(args: Tuple[Callable[[], BlackBoxProblem], int, Dict[str, Any]]):
    problem_factory, run_index, solver_kwargs = args
    problem: BlackBoxProblem = problem_factory()
    solver = BlackBoxSolverVNS(problem)
    for key, value in solver_kwargs.items():
        setattr(solver, key, value)
    res = solver.run()
    best_f_val = res.get("best_f", None)
    best_f = float(best_f_val) if best_f_val is not None else float("inf")
    return {"index": run_index, "x": res.get("best_x", None), "fun": best_f, "raw": res}


def run_vns_in_parallel(
    problem_factory: Callable[[], BlackBoxProblem],
    n_runs: int = 4,
    backend: Backend = "process",
    max_workers: Optional[int] = None,
    **solver_kwargs: Any,
) -> Dict[str, Any]:
    if BlackBoxSolverVNS is None:
        raise ImportError(
            "BlackBoxSolverVNS 已从主包归档。"
            "如需 VNS，请使用 adapters 的 VNSAdapter（ComposableSolver + ContextGaussianMutation/ContextSelectMutator）。"
        )

    tasks: List[Tuple[Callable[[], BlackBoxProblem], int, Dict[str, Any]]] = [
        (problem_factory, i, solver_kwargs) for i in range(n_runs)
    ]

    results: List[Dict[str, Any]] = []
    with _get_executor(backend, max_workers) as executor:
        futures = {executor.submit(_run_single_vns, task): task[1] for task in tasks}
        iterator = as_completed(futures)
        try:
            from tqdm import tqdm  # type: ignore

            iterator = tqdm(iterator, total=len(futures), desc="Parallel VNS runs")
        except Exception:
            pass
        for future in iterator:
            results.append(future.result())

    if not results:
        return {"results": [], "best_index": None, "best_x": None, "best_fun": None}

    best_idx = int(np.argmin([item["fun"] for item in results]))
    best = results[best_idx]
    return {
        "results": sorted(results, key=lambda item: item["index"]),
        "best_index": best["index"],
        "best_x": best["x"],
        "best_fun": best["fun"],
    }


__all__ = ["run_headless_in_parallel", "run_vns_in_parallel"]

