"""L4 evaluation provider wrapping nsgablack's CoptBackend.

Demonstrates the pooled-thread handoff pattern with a real COPT backend:
  Outer solver writes candidate to store -> releases threads.
  This provider picks up threads -> builds linear spec -> solves via CoptBackend.

If coptpy is unavailable, CoptBackend falls back to mock (configurable).
"""

from __future__ import annotations

import time
from typing import Any, Dict, Mapping, Optional, Tuple

import numpy as np

from nsgablack.plugins.solver_backends.backend_contract import BackendSolveRequest
from nsgablack.plugins.solver_backends.copt_backend import CoptBackend, CoptBackendConfig


class CoptHandoffProvider:
    """L4 EvaluationProvider wrapping CoptBackend for COPT-based evaluation."""

    name: str = "copt_handoff"
    semantic_mode: str = "exact"

    def __init__(
        self,
        *,
        copt_config: CoptBackendConfig | None = None,
        pool_threads: int = 4,
    ) -> None:
        self._backend = CoptBackend(config=copt_config or CoptBackendConfig())
        self._pool_threads = max(1, int(pool_threads))
        self._thread_owner: Optional[str] = None
        self._store: Dict[str, Any] = {}

    # -- pool thread management (simulated) --------------------------------

    def _acquire(self, owner: str) -> None:
        if self._thread_owner == owner:
            return
        if self._thread_owner is not None:
            print(f"  [pool]     release    {self._pool_threads} threads from {self._thread_owner}")
        self._thread_owner = owner
        print(f"  [pool]     acquire    {self._pool_threads} threads for {owner}")

    def _release(self, owner: str) -> None:
        if self._thread_owner == owner:
            print(f"  [pool]     release    {self._pool_threads} threads from {self._thread_owner}")
            self._thread_owner = None

    # -- EvaluationProvider contract ---------------------------------------

    def can_handle_individual(
        self, solver: Any, x: np.ndarray, context: Mapping[str, Any]
    ) -> bool:
        return True

    def evaluate_individual(
        self,
        solver: Any,
        x: np.ndarray,
        context: Mapping[str, Any],
        individual_id: Optional[int] = None,
    ) -> Optional[Tuple[np.ndarray, float]]:
        cid = individual_id if individual_id is not None else 0

        # Outer: propose candidate
        self._acquire("outer_search")
        self._store[f"candidate_{cid}"] = np.asarray(x, dtype=float).tolist()
        print(f"  [outer]    propose    candidate[{cid}]: x={np.asarray(x).round(3).tolist()}")
        print(f"  [outer]    store      candidate[{cid}] to L0 store")

        # Handoff: outer releases, copt acquires
        self._release("outer_search")
        self._acquire("copt_backend")

        # CoptBackend: read candidate, build linear spec, solve
        cand = np.asarray(self._store[f"candidate_{cid}"], dtype=float)
        n = int(cand.size)

        print(f"  [copt]     read       candidate[{cid}] from L0 store")

        request = BackendSolveRequest(
            candidate=cand,
            eval_context=dict(context or {}),
            payload={
                "copt_linear_spec_builder": lambda req: {
                    "c": cand.tolist(),
                    "A": np.eye(n).tolist(),
                    "rhs": [1.0] * n,
                    "sense": "<=",
                    "lb": [-5.0] * n,
                    "ub": [5.0] * n,
                    "objective_sense": "min",
                }
            },
        )

        result = self._backend.solve(request)
        status = str(result.get("status", "ok"))
        objective = float(result.get("objective", 0.0))
        copt_mode = (
            result.get("metrics", {}).get("copt.mode", "unknown")
            if isinstance(result.get("metrics"), Mapping)
            else "unknown"
        )

        self._store[f"result_{cid}"] = {"objective": objective, "status": status}
        print(f"  [copt]     solve      LP dim={n} | status={status} | obj={objective:.4f} | mode={copt_mode}")

        self._release("copt_backend")
        self._acquire("outer_search")

        stored = self._store.get(f"result_{cid}", {})
        obj = float(stored.get("objective", 0.0))
        print(f"  [outer]    read       result[{cid}] obj={obj:.4f} from L0 store")

        return np.array([obj], dtype=float), 0.0

    def can_handle_population(
        self, solver: Any, population: np.ndarray, context: Mapping[str, Any]
    ) -> bool:
        return False

    def evaluate_population(
        self,
        solver: Any,
        population: np.ndarray,
        context: Mapping[str, Any],
    ) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        return None
