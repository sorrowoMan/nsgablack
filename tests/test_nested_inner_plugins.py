import numpy as np


def test_inner_solver_and_bridge_plugins_write_layer_context():
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import AlgorithmAdapter
    from nsgablack.plugins import BridgeRule, ContractBridgePlugin, InnerSolverConfig, InnerSolverPlugin

    class OuterProblem(BlackBoxProblem):
        def __init__(self):
            super().__init__(name="outer", dimension=1, bounds={"x0": (-3.0, 3.0)})

        def evaluate(self, x):
            # Should be bypassed by inner solver plugin.
            return 999.0

        def build_inner_task(self, x, eval_context):
            _ = eval_context
            score = float((x[0] - 1.0) ** 2)
            return {"run_inner": lambda _p, _s, _c: {"status": "ok", "objective": score, "score": score}}

    class FixedAdapter(AlgorithmAdapter):
        def __init__(self):
            super().__init__(name="fixed")

        def propose(self, solver, context):
            _ = (solver, context)
            return [np.array([1.0], dtype=float)]

    solver = ComposableSolver(problem=OuterProblem(), adapter=FixedAdapter())
    solver.max_steps = 1
    solver.pop_size = 1
    solver.add_plugin(
        ContractBridgePlugin(
            rules=[
                BridgeRule("score", "inner_score", target_layer="L1"),
                BridgeRule("status", "inner_state", target_layer="L1"),
            ]
        )
    )
    solver.add_plugin(InnerSolverPlugin(config=InnerSolverConfig(source_layer="L2", target_layer="L1")))
    solver.run()

    assert solver.best_objective is not None
    assert float(solver.best_objective) <= 1e-10
    layers = getattr(solver, "_layer_contexts", {})
    assert "L1" in layers
    assert float(layers["L1"]["inner_score"]) <= 1e-10
    assert layers["L1"]["inner_state"] == "ok"


def test_inner_timeout_budget_blocks_calls():
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import AlgorithmAdapter
    from nsgablack.plugins import (
        InnerSolverConfig,
        InnerSolverPlugin,
        TimeoutBudgetConfig,
        TimeoutBudgetPlugin,
    )

    class OuterProblem(BlackBoxProblem):
        def __init__(self):
            super().__init__(name="outer_timeout", dimension=1, bounds={"x0": (-3.0, 3.0)})

        def evaluate(self, x):
            return 999.0

        def build_inner_task(self, x, eval_context):
            _ = (x, eval_context)
            return {"run_inner": lambda _p, _s, _c: {"status": "ok", "objective": 0.0}}

    class FixedAdapter(AlgorithmAdapter):
        def __init__(self):
            super().__init__(name="fixed")

        def propose(self, solver, context):
            _ = (solver, context)
            return [np.array([1.0], dtype=float)]

    solver = ComposableSolver(problem=OuterProblem(), adapter=FixedAdapter())
    solver.max_steps = 1
    solver.pop_size = 1
    solver.add_plugin(TimeoutBudgetPlugin(config=TimeoutBudgetConfig(layer="L2", max_calls=0, time_budget_ms=10_000)))
    solver.add_plugin(InnerSolverPlugin(config=InnerSolverConfig(source_layer="L2", target_layer="L1", fallback_penalty=12345.0)))
    solver.run()

    assert solver.best_objective is not None
    assert float(solver.best_objective) >= 12345.0
