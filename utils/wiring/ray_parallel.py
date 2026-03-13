"""Suite: attach Ray distributed evaluation backend.

This suite wires Ray as the evaluation backend via the parallel wrapper
(`with_parallel_evaluation`). It does not change algorithm behavior beyond
how population evaluation is executed.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import warnings


def attach_ray_parallel(
    solver: Any,
    *,
    problem_factory=None,
    address: Optional[str] = None,
    init_ray: bool = True,
    init_kwargs: Optional[Dict[str, Any]] = None,
    max_workers: Optional[int] = None,
    chunk_size: Optional[int] = None,
    strict: bool = False,
) -> Any:
    """Attach Ray backend configuration to a parallel-enabled solver.

    Requirements
    - The solver instance should come from `with_parallel_evaluation(...)`
      (or otherwise support `_parallel_cfg` + `enable_parallel_evaluation`).
    - For Ray, strongly prefer `problem_factory` so workers construct the problem
      locally (serialization is faster and more reliable).
    """

    if init_ray:
        try:
            import ray  # type: ignore

            if not ray.is_initialized():
                kw = dict(init_kwargs or {})
                kw.setdefault("ignore_reinit_error", True)
                kw.setdefault("include_dashboard", False)
                kw.setdefault("log_to_driver", False)
                if address is not None:
                    kw["address"] = address
                ray.init(**kw)
        except Exception as exc:
            warnings.warn(f"Ray init failed ({exc!r}); backend may fall back at runtime.")

    # Parallel wrapper config (preferred)
    if hasattr(solver, "enable_parallel_evaluation"):
        setattr(solver, "enable_parallel_evaluation", True)
    if hasattr(solver, "_parallel_cfg") and isinstance(getattr(solver, "_parallel_cfg"), dict):
        cfg = getattr(solver, "_parallel_cfg")
        cfg["backend"] = "ray"
        if max_workers is not None:
            cfg["max_workers"] = int(max_workers)
        if chunk_size is not None:
            cfg["chunk_size"] = int(chunk_size)
        cfg["strict"] = bool(strict)
        if problem_factory is not None:
            cfg["problem_factory"] = problem_factory

    # Shadow fields for reporting (ModuleReportPlugin reads these if present)
    try:
        setattr(solver, "enable_parallel", True)
        setattr(solver, "parallel_backend", "ray")
        if max_workers is not None:
            setattr(solver, "parallel_max_workers", int(max_workers))
        if chunk_size is not None:
            setattr(solver, "parallel_chunk_size", int(chunk_size))
        if problem_factory is not None:
            setattr(solver, "parallel_problem_factory", problem_factory)
    except Exception:
        pass

    return solver

