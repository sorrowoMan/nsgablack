from __future__ import annotations

import numpy as np


def test_inner_solver_backend_retry_and_timeout_strategy():
    from nsgablack.adapters import AlgorithmAdapter
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.plugins import InnerSolverConfig, InnerSolverPlugin
    from nsgablack.plugins.solver_backends.backend_contract import BackendSolveRequest

    class _RetryBackend:
        def __init__(self) -> None:
            self.calls = 0

        def solve(self, request: BackendSolveRequest):
            _ = request
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("transient backend error")
            return {"status": "ok", "objective": 0.25, "violation": 0.0}

    class _Problem(BlackBoxProblem):
        def __init__(self):
            super().__init__(name="p", dimension=1, bounds={"x0": (-1.0, 1.0)})

        def evaluate(self, x):
            _ = x
            return 9999.0

        def build_inner_problem(self, x, eval_context):
            _ = (x, eval_context)
            return object()

    class _Adapter(AlgorithmAdapter):
        def __init__(self):
            super().__init__(name="a")

        def propose(self, solver, context):
            _ = (solver, context)
            return [np.array([0.0], dtype=float)]

    backend = _RetryBackend()
    solver = ComposableSolver(problem=_Problem(), adapter=_Adapter())
    solver.max_steps = 1
    solver.pop_size = 1
    solver.add_plugin(
        InnerSolverPlugin(
            config=InnerSolverConfig(max_retries=1, retry_backoff_ms=0.0),
            inner_backend_factory=lambda _p, _ctx: backend,
        )
    )
    solver.run()
    assert solver.best_objective is not None
    assert abs(float(solver.best_objective) - 0.25) < 1e-12
    assert backend.calls == 2

