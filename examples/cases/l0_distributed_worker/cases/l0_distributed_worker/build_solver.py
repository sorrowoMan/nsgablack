# -*- coding: utf-8 -*-
"""L0 distributed worker — standard scaffold assembly entry.

Verifies the shared blackbase task runtime across multiple workers:
  - Worker registration and heartbeat
  - fenced task claims
  - durable result publication through the selected transport

Usage:
  python run_solver.py --id worker-1 --cycles 100
"""

from __future__ import annotations

import os
import signal
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

import numpy as np

from blackbase.call_binding import CallCandidate, invoke_bound_once
from blackbase.resources import TaskEnvelope, TaskResult, build_local_worker_descriptor
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
    max_idle_cycles: int = 0
    seed_demo_task: bool = False
    namespace: str = "nsgablack_dist"
    transport_backend: str = "sqlite"
    sqlite_path: str = "runs/l0_distributed_worker/tasks.sqlite"
    resource_context: Mapping[str, Any] = field(default_factory=dict)
    backend_factory: Callable[..., Any] = build_l0_worker_backend
    problem: str = "l0_task_queue"
    adapter: str = "shared_task_runtime_worker_loop"
    representation_pipeline: Any = None

    def run(self) -> Dict[str, Any]:
        backend = invoke_bound_once(
            self.backend_factory,
            (
                CallCandidate(
                    kwargs={
                        "namespace": self.namespace,
                        "transport_backend": self.transport_backend,
                        "sqlite_path": self.sqlite_path,
                    },
                    label="backend_factory(namespace, transport_backend, sqlite_path)",
                ),
                CallCandidate(
                    kwargs={"namespace": self.namespace},
                    label="backend_factory(namespace)",
                ),
            ),
        )
        wid = self.worker_id

        desc = build_local_worker_descriptor(worker_id=wid)
        backend.heartbeat(desc)

        if self.seed_demo_task:
            backend.submit(
                TaskEnvelope(
                    task_id=f"{self.run_id}:demo:{wid}",
                    task_type="objective",
                    payload={"x": 0.5},
                    namespace=self.run_id,
                    metadata={"source": "l0_distributed_worker.demo"},
                )
            )

        print(f"[{wid}] registered on shared task runtime")
        cycle = 0
        idle_cycles = 0
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
                idle_cycles += 1
                if self.max_idle_cycles > 0 and idle_cycles >= int(self.max_idle_cycles):
                    break
                time.sleep(0.1)
                continue
            idle_cycles = 0
            task = claim.task

            cycle += 1
            payload = dict(task.payload or {})
            x = float(payload.get("x", 0.0))
            time.sleep(0.02)
            result = TaskResult.success(
                task_id=str(getattr(task, "task_id", "")),
                objectives=(float(np.sin(x)),),
                worker_id=wid,
                metrics={"cycle": cycle},
                output={"run_id": self.run_id, "worker_id": wid},
            )
            backend.complete_claim(claim, result)

            if cycle % 50 == 0:
                print(f"[{wid}] completed {cycle} tasks")

        print(f"[{wid}] exiting after {cycle} cycles")
        return {
            "worker_id": wid,
            "namespace": self.namespace,
            "cycles": cycle,
            "idle_cycles": idle_cycles,
            "transport_backend": self.transport_backend,
        }


def build_solver(
    run_id: str | None = None,
    *,
    worker_id: str | None = None,
    max_cycles: int = 1,
    resource_context=None,
    component_overrides=None,
) -> L0DistributedWorker:
    overrides = dict(component_overrides or {})
    wid = worker_id or f"{os.environ.get('HOSTNAME', 'local')}_{os.getpid()}"
    return L0DistributedWorker(
        worker_id=str(wid),
        run_id=str(run_id or "default"),
        max_cycles=int(overrides.pop("max_cycles", max_cycles)),
        max_idle_cycles=int(overrides.pop("max_idle_cycles", 2)),
        seed_demo_task=bool(overrides.pop("seed_demo_task", True)),
        namespace=str(overrides.pop("namespace", "nsgablack_dist")),
        transport_backend=str(overrides.pop("transport_backend", "sqlite")),
        sqlite_path=str(overrides.pop("sqlite_path", "runs/l0_distributed_worker/tasks.sqlite")),
        resource_context=dict(resource_context or {}),
        backend_factory=overrides.pop("backend_factory", build_l0_worker_backend),
    )


# --- CLI ----------------------------------------------------------------
