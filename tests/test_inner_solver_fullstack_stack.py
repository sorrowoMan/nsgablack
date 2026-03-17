from __future__ import annotations

import numpy as np


def test_inner_solver_can_run_inner_adapter_pipeline_bias_and_plugin():
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import AlgorithmAdapter
    from nsgablack.plugins import BridgeRule, ContractBridgePlugin, Plugin
    from nsgablack.core.nested_solver import InnerRuntimeConfig, TaskInnerRuntimeEvaluator

    class InnerProblem(BlackBoxProblem):
        def __init__(self):
            super().__init__(name="inner_problem", dimension=1, bounds={"x0": (-1.0, 1.0)})

        def evaluate(self, x):
            arr = np.asarray(x, dtype=float).reshape(-1)
            return np.array([float(arr[0] ** 2)], dtype=float)

    class OuterProblem(BlackBoxProblem):
        def __init__(self):
            super().__init__(name="outer_problem", dimension=1, bounds={"x0": (-3.0, 3.0)})

        def evaluate(self, x):
            _ = x
            return 999.0

        def build_inner_task(self, x, eval_context):
            _ = (x, eval_context)
            from nsgablack.representation import RepresentationPipeline

            class InnerAdapter(AlgorithmAdapter):
                def __init__(self):
                    super().__init__(name="inner_adapter")

                def propose(self, solver, context):
                    _ = (solver, context)
                    # Intentionally out-of-bound to verify inner pipeline repair is active.
                    return [np.array([2.0], dtype=float)]

            class ClipRepair:
                def repair(self, candidate, context=None):
                    _ = context
                    return np.clip(np.asarray(candidate, dtype=float), -1.0, 1.0)

            class AddBiasModule:
                def compute_bias(self, x, objective, individual_id, context=None):
                    _ = (x, individual_id, context)
                    return float(objective + 0.5)

            class FinishFlagPlugin(Plugin):
                def __init__(self):
                    super().__init__(name="finish_flag")
                    self.finished = False

                def on_solver_finish(self, result):
                    _ = result
                    self.finished = True
                    return None

            def _run_inner(_p, _s, _ctx):
                flag = FinishFlagPlugin()
                inner = ComposableSolver(
                    problem=InnerProblem(),
                    adapter=InnerAdapter(),
                    representation_pipeline=RepresentationPipeline(repair=ClipRepair()),
                    bias_module=AddBiasModule(),
                )
                inner.max_steps = 1
                inner.pop_size = 1
                inner.add_plugin(flag)
                inner_result = inner.run()
                return {
                    "status": "ok",
                    "objective": float(inner.best_objective),
                    "inner_finished": bool(flag.finished),
                    "inner_steps": int(inner_result.get("steps", 0)),
                }

            return {"run_inner": _run_inner}

        def evaluate_from_inner_result(self, x, inner_result, eval_context):
            _ = (x, eval_context)
            return float(inner_result["objective"])

    class OuterAdapter(AlgorithmAdapter):
        def __init__(self):
            super().__init__(name="outer_adapter")

        def propose(self, solver, context):
            _ = (solver, context)
            return [np.array([0.0], dtype=float)]

    solver = ComposableSolver(problem=OuterProblem(), adapter=OuterAdapter())
    solver.max_steps = 1
    solver.pop_size = 1
    solver.add_plugin(
        ContractBridgePlugin(
            rules=[
                BridgeRule("inner_finished", "inner_finished", target_layer="L1"),
                BridgeRule("inner_steps", "inner_steps", target_layer="L1"),
            ]
        )
    )
    solver.problem.inner_runtime_evaluator = TaskInnerRuntimeEvaluator(config=InnerRuntimeConfig(source_layer="L2", target_layer="L1"))
    solver.run()

    # inner objective = clipped(2.0)->1.0, evaluate 1.0, then bias +0.5 -> 1.5
    assert solver.best_objective is not None
    assert abs(float(solver.best_objective) - 1.5) < 1e-8
    layers = getattr(solver, "_layer_contexts", {})
    assert layers.get("L1", {}).get("inner_finished") is True
    assert int(layers.get("L1", {}).get("inner_steps", 0)) == 1


def test_inner_solver_can_run_inner_multi_strategy_stack():
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import AlgorithmAdapter
    from nsgablack.adapters.multi_strategy import (
        MultiStrategyConfig,
        StrategyRouterAdapter,
        StrategySpec,
    )
    from nsgablack.plugins import BridgeRule, ContractBridgePlugin, Plugin
    from nsgablack.core.nested_solver import InnerRuntimeConfig, TaskInnerRuntimeEvaluator

    class InnerProblem(BlackBoxProblem):
        def __init__(self):
            super().__init__(name="inner_problem_multi", dimension=1, bounds={"x0": (-1.0, 1.0)})

        def evaluate(self, x):
            arr = np.asarray(x, dtype=float).reshape(-1)
            return np.array([float(arr[0] ** 2)], dtype=float)

    class _Explorer(AlgorithmAdapter):
        def __init__(self):
            super().__init__(name="explorer")

        def propose(self, solver, context):
            _ = (solver, context)
            return [np.array([0.8], dtype=float)]

    class _Exploiter(AlgorithmAdapter):
        def __init__(self):
            super().__init__(name="exploiter")

        def propose(self, solver, context):
            _ = (solver, context)
            return [np.array([-0.8], dtype=float)]

    class _InnerCounterPlugin(Plugin):
        def __init__(self):
            super().__init__(name="inner_counter")
            self.generation_end_count = 0

        def on_generation_end(self, generation):
            _ = generation
            self.generation_end_count += 1
            return None

    class _InnerBias:
        def compute_bias(self, x, objective, individual_id, context=None):
            _ = (x, individual_id, context)
            return float(objective + 0.25)

    class OuterProblem(BlackBoxProblem):
        def __init__(self):
            super().__init__(name="outer_problem_multi", dimension=1, bounds={"x0": (-3.0, 3.0)})

        def evaluate(self, x):
            _ = x
            return 999.0

        def build_inner_task(self, x, eval_context):
            _ = (x, eval_context)

            def _run_inner(_p, _s, _ctx):
                inner_adapter = StrategyRouterAdapter(
                    strategies=[
                        StrategySpec(adapter=_Explorer(), name="explorer", weight=1.0),
                        StrategySpec(adapter=_Exploiter(), name="exploiter", weight=1.0),
                    ],
                    config=MultiStrategyConfig(total_batch_size=2, adapt_weights=False),
                )
                inner = ComposableSolver(
                    problem=InnerProblem(),
                    adapter=inner_adapter,
                    bias_module=_InnerBias(),
                )
                inner.max_steps = 1
                inner.pop_size = 2
                counter = _InnerCounterPlugin()
                inner.add_plugin(counter)
                inner_result = inner.run()
                return {
                    "status": "ok",
                    "objective": float(inner.best_objective),
                    "inner_generations": int(counter.generation_end_count),
                    "inner_steps": int(inner_result.get("steps", 0)),
                }

            return {"run_inner": _run_inner}

        def evaluate_from_inner_result(self, x, inner_result, eval_context):
            _ = (x, eval_context)
            return float(inner_result["objective"])

    class OuterAdapter(AlgorithmAdapter):
        def __init__(self):
            super().__init__(name="outer_adapter_multi")

        def propose(self, solver, context):
            _ = (solver, context)
            return [np.array([0.0], dtype=float)]

    solver = ComposableSolver(problem=OuterProblem(), adapter=OuterAdapter())
    solver.max_steps = 1
    solver.pop_size = 1
    solver.add_plugin(
        ContractBridgePlugin(
            rules=[
                BridgeRule("inner_generations", "inner_generations", target_layer="L1"),
                BridgeRule("inner_steps", "inner_steps", target_layer="L1"),
            ]
        )
    )
    solver.problem.inner_runtime_evaluator = TaskInnerRuntimeEvaluator(config=InnerRuntimeConfig(source_layer="L2", target_layer="L1"))
    solver.run()

    # inner: x=卤0.8 -> objective 0.64, then bias +0.25 => 0.89
    assert solver.best_objective is not None
    assert abs(float(solver.best_objective) - 0.89) < 1e-8
    layers = getattr(solver, "_layer_contexts", {})
    assert int(layers.get("L1", {}).get("inner_generations", 0)) == 1
    assert int(layers.get("L1", {}).get("inner_steps", 0)) == 1


def test_three_layer_inner_with_multi_strategy_pipeline_bias_plugin():
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import AlgorithmAdapter
    from nsgablack.adapters.multi_strategy import (
        MultiStrategyConfig,
        StrategyRouterAdapter,
        StrategySpec,
    )
    from nsgablack.plugins import BridgeRule, ContractBridgePlugin, Plugin
    from nsgablack.core.nested_solver import InnerRuntimeConfig, TaskInnerRuntimeEvaluator
    from nsgablack.representation import RepresentationPipeline

    class _ClipRepair:
        def repair(self, candidate, context=None):
            _ = context
            return np.clip(np.asarray(candidate, dtype=float), -1.0, 1.0)

    class _CounterPlugin(Plugin):
        def __init__(self, name: str):
            super().__init__(name=name)
            self.generation_end_count = 0

        def on_generation_end(self, generation):
            _ = generation
            self.generation_end_count += 1
            return None

    class _Bias:
        def __init__(self, delta: float):
            self.delta = float(delta)

        def compute_bias(self, x, objective, individual_id, context=None):
            _ = (x, individual_id, context)
            return float(objective + self.delta)

    class _L3Problem(BlackBoxProblem):
        def __init__(self):
            super().__init__(name="l3_problem", dimension=1, bounds={"x0": (0.0, 5.0)})

        def evaluate(self, x):
            arr = np.asarray(x, dtype=float).reshape(-1)
            return np.array([float(arr[0])], dtype=float)

    class _L3Adapter(AlgorithmAdapter):
        def __init__(self, target: float):
            super().__init__(name="l3_adapter")
            self.target = float(target)

        def propose(self, solver, context):
            _ = (solver, context)
            # Include one out-of-bound candidate to confirm inner pipeline repair can handle it.
            return [np.array([self.target], dtype=float), np.array([9.0], dtype=float)]

    class _L2Problem(BlackBoxProblem):
        def __init__(self):
            super().__init__(name="l2_problem", dimension=1, bounds={"x0": (-1.0, 1.0)})

        def evaluate(self, x):
            _ = x
            return np.array([999.0], dtype=float)

        def build_inner_task(self, x, eval_context):
            candidate_x = float(np.asarray(x, dtype=float).reshape(-1)[0])

            def _run_l3(_p, _s, _ctx):
                l3 = ComposableSolver(
                    problem=_L3Problem(),
                    adapter=_L3Adapter(target=abs(candidate_x)),
                    representation_pipeline=RepresentationPipeline(repair=_ClipRepair()),
                    bias_module=_Bias(0.1),
                )
                l3.max_steps = 1
                l3.pop_size = 2
                l3_counter = _CounterPlugin("l3_counter")
                l3.add_plugin(l3_counter)
                l3.run()
                return {
                    "status": "ok",
                    "objective": float(l3.best_objective),
                    "l3_generations": int(l3_counter.generation_end_count),
                    "candidate_seen": candidate_x,
                }

            return {
                "run_inner": _run_l3,
            }

        def evaluate_from_inner_result(self, x, inner_result, eval_context):
            _ = (x, eval_context)
            return float(inner_result["objective"])

    class _L2Explorer(AlgorithmAdapter):
        def __init__(self):
            super().__init__(name="l2_explorer")

        def propose(self, solver, context):
            _ = (solver, context)
            return [np.array([2.0], dtype=float)]

    class _L2Exploiter(AlgorithmAdapter):
        def __init__(self):
            super().__init__(name="l2_exploiter")

        def propose(self, solver, context):
            _ = (solver, context)
            return [np.array([-2.0], dtype=float)]

    class _L1Problem(BlackBoxProblem):
        def __init__(self):
            super().__init__(name="l1_problem", dimension=1, bounds={"x0": (-2.0, 2.0)})

        def evaluate(self, x):
            _ = x
            return np.array([99999.0], dtype=float)

        def build_inner_task(self, x, eval_context):
            _ = (x, eval_context)

            def _run_l2(_p, _s, _ctx):
                l2_adapter = StrategyRouterAdapter(
                    strategies=[
                        StrategySpec(adapter=_L2Explorer(), name="explorer", weight=1.0),
                        StrategySpec(adapter=_L2Exploiter(), name="exploiter", weight=1.0),
                    ],
                    config=MultiStrategyConfig(total_batch_size=2, adapt_weights=False),
                )
                l2 = ComposableSolver(
                    problem=_L2Problem(),
                    adapter=l2_adapter,
                    representation_pipeline=RepresentationPipeline(repair=_ClipRepair()),
                    bias_module=_Bias(0.2),
                )
                l2.max_steps = 1
                l2.pop_size = 2
                l2_counter = _CounterPlugin("l2_counter")
                l2.add_plugin(l2_counter)
                l2.problem.inner_runtime_evaluator = TaskInnerRuntimeEvaluator(config=InnerRuntimeConfig(source_layer="L3", target_layer="L2"))
                l2.run()
                return {
                    "status": "ok",
                    "objective": float(l2.best_objective),
                    "l2_generations": int(l2_counter.generation_end_count),
                    "l2_candidate_seen": float(getattr(l2, "best_x")[0]) if getattr(l2, "best_x", None) is not None else None,
                }

            return {"run_inner": _run_l2}

        def evaluate_from_inner_result(self, x, inner_result, eval_context):
            _ = (x, eval_context)
            return float(inner_result["objective"])

    class _L1Adapter(AlgorithmAdapter):
        def __init__(self):
            super().__init__(name="l1_adapter")

        def propose(self, solver, context):
            _ = (solver, context)
            return [np.array([0.0], dtype=float)]

    l1 = ComposableSolver(problem=_L1Problem(), adapter=_L1Adapter())
    l1.max_steps = 1
    l1.pop_size = 1
    l1.add_plugin(
        ContractBridgePlugin(
            rules=[
                BridgeRule("l2_generations", "l2_generations", target_layer="L1"),
                BridgeRule("l2_candidate_seen", "l2_candidate_seen", target_layer="L1"),
            ]
        )
    )
    l1.problem.inner_runtime_evaluator = TaskInnerRuntimeEvaluator(config=InnerRuntimeConfig(source_layer="L2", target_layer="L1"))
    l1.run()

    # L3 objective ~ abs(repaired x) + 0.1 = 1.1 ; L2 bias adds 0.2 => 1.3
    assert l1.best_objective is not None
    assert abs(float(l1.best_objective) - 1.3) < 1e-8
    layers = getattr(l1, "_layer_contexts", {})
    assert int(layers.get("L1", {}).get("l2_generations", 0)) == 1
    # L2 candidate should already be repaired into [-1, 1] before L3 task build.
    assert abs(float(layers.get("L1", {}).get("l2_candidate_seen"))) <= 1.0 + 1e-12

