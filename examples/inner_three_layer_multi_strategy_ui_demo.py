from __future__ import annotations

import numpy as np

from nsgablack.core.adapters import AlgorithmAdapter
from nsgablack.core.adapters.multi_strategy import (
    MultiStrategyConfig,
    MultiStrategyControllerAdapter,
    StrategySpec,
)
from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.plugins import InnerSolverConfig, InnerSolverPlugin
from nsgablack.representation import RepresentationPipeline


class _ClipRepair:
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Repairs candidates by clipping into [-1, 1].",)

    def repair(self, candidate, context=None):
        _ = context
        return np.clip(np.asarray(candidate, dtype=float), -1.0, 1.0)


class _Bias:
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Adds constant bias delta to objective.",)
    requires_metrics = ()
    metrics_fallback = "none"
    missing_metrics_policy = "warn"

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
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Proposes target and stress-test candidate for L3.",)

    def __init__(self, target: float):
        super().__init__(name="l3_adapter")
        self.target = float(target)

    def propose(self, solver, context):
        _ = (solver, context)
        return [np.array([self.target], dtype=float), np.array([9.0], dtype=float)]


def _build_l3_solver(target: float) -> ComposableSolver:
    l3 = ComposableSolver(
        problem=_L3Problem(),
        adapter=_L3Adapter(target=target),
        representation_pipeline=RepresentationPipeline(repair=_ClipRepair()),
        bias_module=_Bias(0.1),
    )
    l3.max_steps = 1
    l3.pop_size = 2
    return l3


class _L2Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="l2_problem", dimension=1, bounds={"x0": (-1.0, 1.0)})

    def evaluate(self, x):
        _ = x
        return np.array([999.0], dtype=float)

    def build_inner_task(self, x, eval_context):
        candidate_x = float(np.asarray(x, dtype=float).reshape(-1)[0])
        l3 = _build_l3_solver(abs(candidate_x))
        return {"inner_solver": l3}

    def evaluate_from_inner_result(self, x, inner_result, eval_context):
        _ = (x, eval_context)
        return float(inner_result["objective"])


class _L2Explorer(AlgorithmAdapter):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Explorer role in L2 multi-strategy.",)

    def __init__(self):
        super().__init__(name="l2_explorer")

    def propose(self, solver, context):
        _ = (solver, context)
        return [np.array([2.0], dtype=float)]


class _L2Exploiter(AlgorithmAdapter):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Exploiter role in L2 multi-strategy.",)

    def __init__(self):
        super().__init__(name="l2_exploiter")

    def propose(self, solver, context):
        _ = (solver, context)
        return [np.array([-2.0], dtype=float)]


def _build_l2_solver() -> ComposableSolver:
    l2_adapter = MultiStrategyControllerAdapter(
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
    l2_inner = InnerSolverPlugin(config=InnerSolverConfig(source_layer="L3", target_layer="L2"))
    # Preview pointer for Run Inspector tree (before runtime task creation).
    l2_inner.inner_solver = _build_l3_solver(target=1.0)
    l2.add_plugin(l2_inner)
    return l2


class _L1Problem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="l1_problem", dimension=1, bounds={"x0": (-2.0, 2.0)})

    def evaluate(self, x):
        _ = x
        return np.array([99999.0], dtype=float)

    def build_inner_task(self, x, eval_context):
        _ = (x, eval_context)
        l2 = _build_l2_solver()
        return {"inner_solver": l2}

    def evaluate_from_inner_result(self, x, inner_result, eval_context):
        _ = (x, eval_context)
        return float(inner_result["objective"])


class _L1Adapter(AlgorithmAdapter):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Top-level adapter for L1.",)

    def __init__(self):
        super().__init__(name="l1_adapter")

    def propose(self, solver, context):
        _ = (solver, context)
        return [np.array([0.0], dtype=float)]


def build_solver() -> ComposableSolver:
    l1 = ComposableSolver(problem=_L1Problem(), adapter=_L1Adapter())
    l1.max_steps = 1
    l1.pop_size = 1
    l1_inner = InnerSolverPlugin(config=InnerSolverConfig(source_layer="L2", target_layer="L1"))
    # Preview pointer for Run Inspector tree (before runtime task creation).
    l1_inner.inner_solver = _build_l2_solver()
    l1.add_plugin(l1_inner)
    return l1
