# -*- coding: utf-8 -*-
"""L0 distributed worker — standard scaffold assembly entry.

Verifies the shared blackbase task runtime across multiple workers:
  - Worker registration and heartbeat
  - fenced task claims
  - durable result publication through the selected transport

Usage:
  python build_solver.py --id worker-1 --cycles 100
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

import numpy as np

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from blackbase.resources import TaskResult, build_local_worker_descriptor
from nsgablack.project.scaffold import print_solver_check
from runtime.config import build_l0_worker_backend


@dataclass
class L0DistributedWorker:
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Consumes the Project-authorized L0 ResourceContext and does not write Solver Context fields.",
    )

    worker_id: str
    run_id: str
    max_cycles: int = 0
    namespace: str = "nsgablack_dist"
    resource_context: Mapping[str, Any] = field(default_factory=dict)
    backend_factory: Callable[..., Any] = build_l0_worker_backend
    problem: str = "l0_task_queue"
    adapter: str = "shared_task_runtime_worker_loop"
    representation_pipeline: Any = None

    def run(self) -> Dict[str, Any]:
        backend = self.backend_factory(namespace=self.namespace)
        wid = self.worker_id

        desc = build_local_worker_descriptor(worker_id=wid)
        backend.heartbeat(desc)

        print(f"[{wid}] registered on shared task runtime")
        cycle = 0
        running = True

        def _shutdown(signum, frame):
            nonlocal running
            print(f"[{wid}] signal {signum}, draining...")
            running = False

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        while running and (self.max_cycles <= 0 or cycle < int(self.max_cycles)):
            backend.heartbeat(wid)

            claim = backend.claim_task(desc, run_id=self.run_id, timeout_seconds=2)
            if claim is None:
                time.sleep(0.1)
                continue
            task = claim.task

            cycle += 1
            payload = dict(task.payload or {})
            x = float(payload.get("x", 0.0))
            time.sleep(0.02)
            result = TaskResult.success(
                task_id=str(getattr(task, "task_id", "")),
                objectives=(float(np.sin(x)),),
                worker_id=wid,
                metadata={"run_id": self.run_id, "worker_id": wid, "cycle": cycle},
            )
            backend.complete_claim(claim, result)

            if cycle % 50 == 0:
                print(f"[{wid}] completed {cycle} tasks")

        print(f"[{wid}] exiting after {cycle} cycles")
        return {"worker_id": wid, "namespace": self.namespace, "cycles": cycle}


def build_solver(
    run_id: str | None = None,
    *,
    worker_id: str | None = None,
    max_cycles: int = 0,
    resource_context=None,
    component_overrides=None,
) -> L0DistributedWorker:
    overrides = dict(component_overrides or {})
    wid = worker_id or f"{os.environ.get('HOSTNAME', 'local')}_{os.getpid()}"
    return L0DistributedWorker(
        worker_id=str(wid),
        run_id=str(run_id or "default"),
        max_cycles=int(max_cycles),
        namespace=str(overrides.get("namespace", "nsgablack_dist")),
        resource_context=dict(resource_context or {}),
        backend_factory=overrides.get("backend_factory", build_l0_worker_backend),
    )


# --- CLI ----------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="L0 distributed worker (scaffold entry)")
    p.add_argument("--id", default=None, help="worker identifier")
    p.add_argument("--cycles", type=int, default=0, help="max cycles (0=forever)")
    p.add_argument("--namespace", default="nsgablack_dist")
    p.add_argument("--check", action="store_true")
    return p


def main(argv: Optional[list[str]] = None) -> None:
    args = _build_parser().parse_args(argv)
    worker = build_solver(
        run_id=args.id,
        worker_id=args.id,
        max_cycles=int(args.cycles),
        component_overrides={"namespace": args.namespace},
    )
    if args.check:
        print_solver_check(worker, resource_context=worker.resource_context)
        print(f"[check] runtime=RedisTaskRuntimeBackend(lazy) namespace={worker.namespace}")
        return
    worker.run()


if __name__ == "__main__":
    main()
