from __future__ import annotations

import numpy as np


def test_evaluation_model_plugin_outer_and_inner():
    from nsgablack.adapters import AlgorithmAdapter
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.plugins import (
        EvaluationModelConfig,
        EvaluationModelProviderPlugin,
    )
    from nsgablack.core.nested_solver import InnerRuntimeConfig, TaskInnerRuntimeEvaluator

    class _Backend:
        def solve(self, request):
            cand = np.asarray(request.candidate, dtype=float).reshape(-1)
            scope = str((request.eval_context or {}).get("scope", "outer"))
            base = float(np.sum(cand * cand))
            if scope == "inner":
                return {"status": "ok", "objective": base + 0.5, "violation": 0.0}
            return {"status": "ok", "objective": base + 1.0, "violation": 0.0}

    class _OuterProblem(BlackBoxProblem):
        def __init__(self):
            super().__init__(name="outer_eval_model", dimension=1, bounds={"x0": (-3.0, 3.0)})

        def evaluate(self, x):
            _ = x
            return 9999.0

        def build_inner_problem(self, x, eval_context):
            _ = (x, eval_context)
            return {"kind": "inner_case"}

        def evaluate_from_inner_result(self, x, inner_result, eval_context):
            _ = (x, eval_context)
            return float(inner_result.get("objective", 1e6))

    class _Adapter(AlgorithmAdapter):
        def __init__(self):
            super().__init__(name="a")

        def propose(self, solver, context):
            _ = (solver, context)
            return [np.array([2.0], dtype=float)]

    backend = _Backend()
    solver = ComposableSolver(problem=_OuterProblem(), adapter=_Adapter())
    solver.max_steps = 1
    solver.pop_size = 1
    solver.register_evaluation_provider(
        EvaluationModelProviderPlugin(
            config=EvaluationModelConfig(scope="both", warn_on_failure=False),
            backend_factory=lambda _problem, _ctx: backend,
        ).create_provider()
    )
    solver.run()
    # outer objective path: 2^2 + 1.0 = 5.0
    assert solver.best_objective is not None
    assert abs(float(solver.best_objective) - 5.0) < 1e-12

    # inner delegation path should use same evaluation model plugin.
    solver2 = ComposableSolver(problem=_OuterProblem(), adapter=_Adapter())
    solver2.max_steps = 1
    solver2.pop_size = 1
    solver2.register_evaluation_provider(
        EvaluationModelProviderPlugin(
            config=EvaluationModelConfig(scope="inner", warn_on_failure=False),
            backend_factory=lambda _problem, _ctx: backend,
        ).create_provider()
    )
    solver2.problem.inner_runtime_evaluator = TaskInnerRuntimeEvaluator(
        config=InnerRuntimeConfig(source_layer="L2", target_layer="L1")
    )
    solver2.run()
    # inner objective path: 2^2 + 0.5 = 4.5
    assert solver2.best_objective is not None
    assert abs(float(solver2.best_objective) - 4.5) < 1e-12

