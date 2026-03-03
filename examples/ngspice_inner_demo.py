from __future__ import annotations

import numpy as np

from nsgablack.adapters import AlgorithmAdapter
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.plugins import InnerSolverConfig, InnerSolverPlugin
from nsgablack.plugins.solver_backends.ngspice_backend import NgspiceBackend, NgspiceBackendConfig


class NgspiceOuterProblem(BlackBoxProblem):
    def __init__(self) -> None:
        super().__init__(name="ngspice_outer_demo", dimension=1, bounds={"x0": (-5.0, 5.0)})

    def evaluate(self, x):
        # Outer direct evaluate is bypassed by InnerSolverPlugin.
        _ = x
        return 1e9

    def build_inner_problem(self, x, eval_context):
        _ = (x, eval_context)
        # InnerSolverPlugin requires a non-empty inner task context.
        return {"kind": "ngspice_case"}

    def evaluate_from_inner_result(self, x, inner_result, eval_context):
        _ = (x, eval_context)
        return float(inner_result.get("objective", 1e6))


class FixedAdapter(AlgorithmAdapter):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Proposes fixed candidate for ngspice inner demo.",)

    def __init__(self) -> None:
        super().__init__(name="fixed_adapter")

    def propose(self, solver, context):
        _ = (solver, context)
        return [np.array([2.0], dtype=float)]


def build_solver() -> ComposableSolver:
    solver = ComposableSolver(problem=NgspiceOuterProblem(), adapter=FixedAdapter())
    solver.set_max_steps(1)
    solver.set_solver_hyperparams(pop_size=1)
    solver.add_plugin(
        InnerSolverPlugin(
            config=InnerSolverConfig(
                source_layer="L2",
                target_layer="L1",
                max_retries=1,
                per_call_timeout_ms=30000,
                retry_backoff_ms=100.0,
            ),
            inner_backend_factory=lambda _inner_problem, _ctx: NgspiceBackend(
                config=NgspiceBackendConfig(
                    command="ngspice",
                    timeout_ms=30000,
                    # If ngspice binary is unavailable, demo still runs in mock mode.
                    mock_when_unavailable=True,
                )
            ),
        )
    )
    return solver


def main() -> None:
    solver = build_solver()
    result = solver.run()
    print("done:", result)
    print("best objective:", solver.best_objective)


if __name__ == "__main__":
    main()
