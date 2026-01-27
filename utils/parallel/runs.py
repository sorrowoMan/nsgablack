"""并行批量运行 GA / VNS 的辅助模块。

python -m pytest tests/test_parallel_runs.py
主要提供两个入口：
- run_headless_in_parallel: 并行多次调用 run_headless_single_objective
- run_vns_in_parallel: 并行多次调用 BlackBoxSolverVNS.run

默认使用多进程 (ProcessPoolExecutor) 以更好地利用 CPU 多核，
也支持 backend="thread" 的线程池模式。
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from typing import Callable, Literal, Optional, Dict, Any, List, Tuple

import numpy as np

from ..headless import run_headless_single_objective
from ...core.base import BlackBoxProblem

# Legacy note: earlier versions shipped a VNS solver implementation.
# The modern architecture uses `core/adapters/vns.py` instead, so we keep
# the parallel-run helper but disable VNS batch runs unless the legacy solver
# is provided by user code.
BlackBoxSolverVNS = None  # type: ignore

Backend = Literal["thread", "process"]


def _get_executor(backend: Backend, max_workers: Optional[int]):
    """根据 backend 返回合适的执行器实例。"""
    if backend == "thread":
        return ThreadPoolExecutor(max_workers=max_workers)
    return ProcessPoolExecutor(max_workers=max_workers)


def _run_single_headless(args: Tuple[Callable, List[Tuple[float, float]], int, Dict[str, Any]]):
    """子进程/线程中运行一次 headless GA。

    注意：
    - objective 必须是可被多进程序列化的函数（顶层定义）。
    - bounds 应该是可序列化的简单列表/元组结构。
    """
    objective, bounds, run_index, solver_kwargs = args
    res = run_headless_single_objective(objective, bounds, **solver_kwargs)
    fun_val = res.get("fun", None)
    fun = float(fun_val) if fun_val is not None else float("inf")
    return {
        "index": run_index,
        "x": res.get("x", None),
        "fun": fun,
        "raw": res,
    }


def run_headless_in_parallel(
    objective: Callable,
    bounds,
    n_runs: int = 4,
    backend: Backend = "process",
    max_workers: Optional[int] = None,
    **solver_kwargs: Any,
) -> Dict[str, Any]:
    """并行多次运行 run_headless_single_objective。

    参数
    ------
    objective : callable
        接受形如 (d,) 或 (n,d) 的数组并返回标量的目标函数。
    bounds : list[tuple]
        每个变量的 (min, max)。
    n_runs : int, default 4
        总共要独立运行多少次。
    backend : {"process", "thread"}, default "process"
        "process" 使用 ProcessPoolExecutor（推荐用于 CPU 密集型优化），
        "thread" 使用 ThreadPoolExecutor（若目标函数 I/O 多可考虑）。
    max_workers : int | None
        并发 worker 数量；None 时由执行器自行决定。
    **solver_kwargs : Any
        传给 run_headless_single_objective 的其余关键字参数，例如
        pop_size, max_generations, mutation_rate 等。

    返回
    ------
    result : dict
        {
          "results": [
             {"index": i, "x": best_x_i, "fun": best_f_i, "raw": 原始返回字典},
             ...
          ],
          "best_index": int | None,
          "best_x": ndarray | None,
          "best_fun": float | None,
        }
    """
    tasks: List[Tuple[Callable, Any, int, Dict[str, Any]]] = [
        (objective, bounds, i, solver_kwargs)
        for i in range(n_runs)
    ]

    results: List[Dict[str, Any]] = []
    with _get_executor(backend, max_workers) as executor:
        futures = {executor.submit(_run_single_headless, t): t[2] for t in tasks}

        iterator = as_completed(futures)
        # 若环境安装了 tqdm，则显示简单进度条
        try:
            from tqdm import tqdm  # type: ignore

            iterator = tqdm(iterator, total=len(futures), desc="Parallel headless runs")
        except Exception:
            pass

        for fut in iterator:
            results.append(fut.result())

    if not results:
        return {"results": [], "best_index": None, "best_x": None, "best_fun": None}

    # 找全局最好的一次（最小化 fun）
    best_idx = int(np.argmin([r["fun"] for r in results]))
    best = results[best_idx]

    return {
        "results": sorted(results, key=lambda r: r["index"]),
        "best_index": best["index"],
        "best_x": best["x"],
        "best_fun": best["fun"],
    }


def _run_single_vns(args: Tuple[Callable[[], BlackBoxProblem], int, Dict[str, Any]]):
    """子进程/线程中运行一次 VNS 优化。"""
    problem_factory, run_index, solver_kwargs = args
    problem: BlackBoxProblem = problem_factory()
    solver = BlackBoxSolverVNS(problem)
    # 将传入的参数设置到 solver 上（如 max_iterations, k_max 等）
    for k, v in solver_kwargs.items():
        setattr(solver, k, v)
    res = solver.run()
    best_f_val = res.get("best_f", None)
    best_f = float(best_f_val) if best_f_val is not None else float("inf")
    return {
        "index": run_index,
        "x": res.get("best_x", None),
        "fun": best_f,
        "raw": res,
    }


def run_vns_in_parallel(
    problem_factory: Callable[[], BlackBoxProblem],
    n_runs: int = 4,
    backend: Backend = "process",
    max_workers: Optional[int] = None,
    **solver_kwargs: Any,
) -> Dict[str, Any]:
    """并行多次运行 BlackBoxSolverVNS。

    参数
    ------
    problem_factory : callable
        无参函数，每次调用返回一个新的 BlackBoxProblem 实例。
        这样可以避免进程/线程之间共享同一个 problem 对象。
    n_runs : int, default 4
        总共要独立运行多少次。
    backend : {"process", "thread"}, default "process"
        并行后端，含义同 run_headless_in_parallel。
    max_workers : int | None
        并发 worker 数量；None 时由执行器自行决定。
    **solver_kwargs : Any
        要设置到 BlackBoxSolverVNS 实例上的其他属性，例如
        max_iterations, k_max, neighborhood_type 等。

    返回
    ------
    result : dict
        结构与 run_headless_in_parallel 相同。
    """
    if BlackBoxSolverVNS is None:
        raise ImportError(
            "BlackBoxSolverVNS 已从主包中归档（solvers/ 已移除）。"
            "如需 VNS，请使用 core/adapters 的 VNSAdapter（ComposableSolver + utils/suites/vns.py）。"
        )
    tasks: List[Tuple[Callable[[], BlackBoxProblem], int, Dict[str, Any]]] = [
        (problem_factory, i, solver_kwargs)
        for i in range(n_runs)
    ]

    results: List[Dict[str, Any]] = []
    with _get_executor(backend, max_workers) as executor:
        futures = {executor.submit(_run_single_vns, t): t[1] for t in tasks}

        iterator = as_completed(futures)
        try:
            from tqdm import tqdm  # type: ignore

            iterator = tqdm(iterator, total=len(futures), desc="Parallel VNS runs")
        except Exception:
            pass

        for fut in iterator:
            results.append(fut.result())

    if not results:
        return {"results": [], "best_index": None, "best_x": None, "best_fun": None}

    best_idx = int(np.argmin([r["fun"] for r in results]))
    best = results[best_idx]

    return {
        "results": sorted(results, key=lambda r: r["index"]),
        "best_index": best["index"],
        "best_x": best["x"],
        "best_fun": best["fun"],
    }


__all__ = [
    "run_headless_in_parallel",
    "run_vns_in_parallel",
]
