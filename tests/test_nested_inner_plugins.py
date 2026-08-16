import time

import numpy as np


def test_inner_solver_and_bridge_plugins_write_layer_context():
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import AlgorithmAdapter
    from nsgablack.plugins import BridgeRule, ContractBridgePlugin
    from nsgablack.core.nested_solver import InnerRuntimeConfig, TaskInnerRuntimeEvaluator

    class OuterProblem(BlackBoxProblem):
        def __init__(self):
            super().__init__(name="outer", dimension=1, bounds={"x0": (-3.0, 3.0)})

        def evaluate(self, candidate):
            # Should be bypassed by inner solver plugin.
            return 999.0

        def build_inner_task(self, x, eval_context):
            _ = eval_context
            score = float((x[0] - 1.0) ** 2)
            return {"run_inner": lambda _p, _s, _c: {"status": "ok", "objective": score, "score": score}}

    class FixedAdapter(AlgorithmAdapter):
        def __init__(self):
            super().__init__(name="fixed")

        def propose(self, control, context):
            _ = (control, context)
            return [np.array([1.0], dtype=float)]

        def update(self, control, candidates, feedback, context):
            _ = (control, candidates, feedback, context)

    control = ComposableSolver(problem=OuterProblem(), adapter=FixedAdapter())
    control.max_steps = 1
    control.pop_size = 1
    control.add_plugin(
        ContractBridgePlugin(
            rules=[
                BridgeRule("score", "inner_score", target_layer="L1"),
                BridgeRule("status", "inner_state", target_layer="L1"),
            ]
        )
    )
    control.problem.inner_runtime_evaluator = TaskInnerRuntimeEvaluator(config=InnerRuntimeConfig(source_layer="L2", target_layer="L1"))
    control.run()

    assert control.best_objective is not None
    assert float(control.best_objective) <= 1e-10
    layers = getattr(control, "_layer_contexts", {})
    assert "L1" in layers
    assert float(layers["L1"]["inner_score"]) <= 1e-10
    assert layers["L1"]["inner_state"] == "ok"


def test_inner_timeout_budget_blocks_calls():
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import AlgorithmAdapter
    from nsgablack.plugins import (
        TimeoutBudgetConfig,
        TimeoutBudgetPlugin,
    )
    from nsgablack.core.nested_solver import InnerRuntimeConfig, TaskInnerRuntimeEvaluator

    class OuterProblem(BlackBoxProblem):
        def __init__(self):
            super().__init__(name="outer_timeout", dimension=1, bounds={"x0": (-3.0, 3.0)})

        def evaluate(self, candidate):
            return 999.0

        def build_inner_task(self, x, eval_context):
            _ = (x, eval_context)
            return {"run_inner": lambda _p, _s, _c: {"status": "ok", "objective": 0.0}}

    class FixedAdapter(AlgorithmAdapter):
        def __init__(self):
            super().__init__(name="fixed")

        def propose(self, control, context):
            _ = (control, context)
            return [np.array([1.0], dtype=float)]

        def update(self, control, candidates, feedback, context):
            _ = (control, candidates, feedback, context)

    control = ComposableSolver(problem=OuterProblem(), adapter=FixedAdapter())
    control.max_steps = 1
    control.pop_size = 1
    control.add_plugin(TimeoutBudgetPlugin(config=TimeoutBudgetConfig(layer="L2", max_calls=0, time_budget_ms=10_000)))
    control.problem.inner_runtime_evaluator = TaskInnerRuntimeEvaluator(config=InnerRuntimeConfig(source_layer="L2", target_layer="L1", fallback_penalty=12345.0))
    control.run()

    assert control.best_objective is not None
    assert float(control.best_objective) >= 12345.0


def test_task_inner_runtime_preserves_resource_context_and_timeout_is_non_blocking():
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.blank_solver import SolverBase
    from nsgablack.core.nested_solver import InnerRuntimeConfig, TaskInnerRuntimeEvaluator

    seen: dict = {}

    class OuterProblem(BlackBoxProblem):
        def __init__(self):
            super().__init__(name="runtime_contract", dimension=1, bounds={"x0": (-1.0, 1.0)})

        def evaluate(self, candidate):
            return 0.0

        def build_inner_task(self, x, eval_context):
            seen.update(dict(eval_context.get("resource_context", {})))
            return {"run_inner": lambda _p, _s, _c: {"status": "ok", "objective": float(x[0])}}

    solver = SolverBase(problem=OuterProblem())
    evaluator = TaskInnerRuntimeEvaluator(config=InnerRuntimeConfig(warn_on_failure=False))
    result = evaluator.evaluate(
        solver=solver,
        x=np.asarray([0.5]),
        individual_id=0,
        context={"resource_context": {"threads": 3, "namespace": "project.outer"}},
    )

    assert result is not None
    assert seen["threads"] == 3
    assert seen["namespace"] == "project.outer"

    solver.problem.build_inner_task = lambda _x, _ctx: {
        "run_inner": lambda _p, _s, _c: (time.sleep(0.5) or {"status": "ok", "objective": 0.0})
    }
    timed = TaskInnerRuntimeEvaluator(
        config=InnerRuntimeConfig(per_call_timeout_ms=20, fallback_penalty=123.0, warn_on_failure=False)
    )
    started = time.perf_counter()
    objectives, violation = timed.evaluate(
        solver=solver,
        x=np.asarray([0.0]),
        individual_id=1,
        context={"resource_context": {"threads": 1, "namespace": "project.outer"}},
    )

    assert time.perf_counter() - started < 0.25
    assert objectives.tolist() == [123.0]
    assert violation == 123.0
    assert timed.stats["timeouts"] == 1.0
