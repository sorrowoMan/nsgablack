# -*- coding: utf-8 -*-
"""L0 distributed worker — standard scaffold assembly entry.

Verifies the L0 runtime layer across multiple workers:
  - Worker registration + heartbeat (PostgresWorkerRegistryBackend)
  - Task queue with SKIP LOCKED concurrent dequeue
  - Result persistence (PostgresTaskResultBackend)

Usage:
  python build_solver.py --id worker-1 --cycles 100
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from nsgablack.core.resources import TaskResult, build_local_worker_descriptor
from runtime.config import build_l0_worker_backend


def build_solver(
    run_id: str | None = None,
    *,
    worker_id: str | None = None,
    max_cycles: int = 0,
) -> Dict[str, Any]:
    wid = worker_id or f"{os.environ.get('HOSTNAME', 'local')}_{os.getpid()}"
    backend = build_l0_worker_backend()

    desc = build_local_worker_descriptor(worker_id=wid)
    backend.worker_registry.register(desc, ttl_seconds=60)

    print(f"[{wid}] registered on {backend.namespace}")
    cycle = 0
    running = True

    def _shutdown(signum, frame):
        nonlocal running
        print(f"[{wid}] signal {signum}, draining...")
        running = False

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    while running and (max_cycles <= 0 or cycle < int(max_cycles)):
        backend.worker_registry.heartbeat(wid, ttl_seconds=60)

        task = backend.task_queue.claim(timeout_seconds=2)
        if task is None:
            time.sleep(0.1)
            continue

        cycle += 1
        payload = dict(task.payload or {})
        x = float(payload.get("x", 0.0))
        time.sleep(0.02)
        result = TaskResult(
            task_id=str(getattr(task, "task_id", "")),
            status="completed",
            objectives=(float(np.sin(x)),),
            worker_id=wid,
            metadata={"run_id": "default", "worker_id": wid, "cycle": cycle},
        )
        backend.result_backend.complete(result)

        if cycle % 50 == 0:
            print(f"[{wid}] completed {cycle} tasks")

    print(f"[{wid}] exiting after {cycle} cycles")
    return {"worker_id": wid, "namespace": backend.namespace, "cycles": cycle}


# --- CLI ----------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="L0 distributed worker (scaffold entry)")
    p.add_argument("--id", default=None, help="worker identifier")
    p.add_argument("--cycles", type=int, default=0, help="max cycles (0=forever)")
    return p


def main(argv: Optional[list[str]] = None) -> None:
    args = _build_parser().parse_args(argv)
    build_solver(run_id=args.id, worker_id=args.id, max_cycles=int(args.cycles))


if __name__ == "__main__":
    main()
