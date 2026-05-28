"""Redis worker for supply_adjustment_nested outer nested evaluation.

This is an L0 worker surface: it claims candidate tasks from Redis, runs the
case-local inner production evaluation, and writes objective results back.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import numpy as np

_THIS_DIR = Path(__file__).resolve().parent
_CASE_DIR = _THIS_DIR.parent
if str(_CASE_DIR) not in sys.path:
    sys.path.insert(0, str(_CASE_DIR))

from _bootstrap import ensure_nsgablack_importable  # noqa: E402

ensure_nsgablack_importable(Path(__file__))

from nsgablack.utils.parallel import run_nested_redis_worker  # noqa: E402
from nsgablack.core.resources import RedisL0RuntimeBackend, TaskEnvelope, TaskResult  # noqa: E402

from assembly import _build_solver_from_args, build_parser  # noqa: E402


def build_worker_parser():
    p = build_parser()
    p.description = "Redis worker for supply_adjustment_nested nested evaluation"
    p.add_argument("--worker-id", type=str, default=None)
    p.add_argument("--worker-max-tasks", type=int, default=0, help="Stop after N tasks (<=0 means unlimited).")
    p.add_argument("--worker-idle-timeout-seconds", type=float, default=60.0)
    p.add_argument("--worker-claim-timeout-seconds", type=int, default=2)
    p.add_argument("--redis-run-id", type=str, default=None, help="Only needed with --redis-queue-scope run.")
    return p


def _build_task_runner(solver):
    problem = getattr(solver, "problem", None)
    evaluator = getattr(problem, "inner_runtime_evaluator", None) if problem is not None else None
    if not callable(getattr(evaluator, "evaluate", None)):
        raise RuntimeError("solver.problem.inner_runtime_evaluator.evaluate is required")

    def _run(task: TaskEnvelope) -> TaskResult:
        payload = dict(task.payload)
        candidate = np.asarray(payload.get("candidate", []), dtype=float).reshape(-1)
        individual_id = int(payload.get("index", 0))
        nested = evaluator.evaluate(
            solver=solver,
            x=candidate,
            individual_id=individual_id,
            context={
                "distributed": True,
                "task_id": task.task_id,
                "run_id": payload.get("run_id", task.namespace),
                "l0_task": task.as_dict(),
                "metadata": dict(task.metadata or {}),
            },
        )
        if nested is None:
            raise RuntimeError("inner runtime evaluator returned None")
        objectives, violation = nested
        return TaskResult.success(
            task_id=task.task_id,
            objectives=tuple(float(x) for x in np.asarray(objectives, dtype=float).reshape(-1)),
            violations=(float(violation),),
            worker_id="supply_adjustment_nested",
            metadata={
                "worker": "supply_adjustment_nested",
                "index": individual_id,
                "run_id": str(payload.get("run_id", task.namespace)),
            },
        )

    return _run


def main(argv: Optional[list[str]] = None) -> None:
    args = build_worker_parser().parse_args(argv)
    solver = _build_solver_from_args(args)
    queue = RedisL0RuntimeBackend(
        redis_url=str(args.redis_url),
        namespace=str(args.redis_namespace),
        queue_scope=str(args.redis_queue_scope),
        result_ttl_seconds=int(args.redis_result_ttl_seconds),
    )
    worker_id = args.worker_id
    max_tasks = int(args.worker_max_tasks)
    print(
        "[redis-worker] "
        f"namespace={args.redis_namespace} scope={args.redis_queue_scope} "
        f"worker_id={worker_id or 'auto'} max_tasks={max_tasks if max_tasks > 0 else 'unlimited'}"
    )
    summary = run_nested_redis_worker(
        queue=queue,
        task_runner=_build_task_runner(solver),
        worker_id=worker_id,
        run_id=args.redis_run_id,
        max_tasks=(max_tasks if max_tasks > 0 else None),
        idle_timeout_seconds=float(args.worker_idle_timeout_seconds),
        claim_timeout_seconds=int(args.worker_claim_timeout_seconds),
    )
    print(f"[redis-worker] stopped processed={summary['processed']} worker_id={summary['worker_id']}")


if __name__ == "__main__":
    main()
