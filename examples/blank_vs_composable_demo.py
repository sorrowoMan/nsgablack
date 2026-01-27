"""BlankSolverBase vs ComposableSolver 对比示例。

同一问题、同一“随机游走 + 贪心保留”策略，用两种方式实现：
- BlankSolverBase：流程写在插件里
- ComposableSolver + Adapter：流程写成可复用算法模块
"""

import numpy as np

try:
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.blank_solver import BlankSolverBase
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import AlgorithmAdapter
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, GaussianMutation, ClipRepair
    from nsgablack.bias import BiasModule, ConvergenceBias
    from nsgablack.utils.plugins import Plugin
except ModuleNotFoundError:  # pragma: no cover - convenience for direct script runs
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.blank_solver import BlankSolverBase
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import AlgorithmAdapter
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, GaussianMutation, ClipRepair
    from nsgablack.bias import BiasModule, ConvergenceBias
    from nsgablack.utils.plugins import Plugin


class SimpleSphereProblem(BlackBoxProblem):
    def __init__(self, dimension=6, low=-5.0, high=5.0):
        super().__init__(
            name="CompareSphere",
            dimension=dimension,
            bounds={f"x{i}": (low, high) for i in range(dimension)},
        )
        self.low = low
        self.high = high

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        return float(np.sum(x ** 2))


class GreedyStepPlugin(Plugin):
    """BlankSolverBase：把算法流程写在插件里。"""

    def __init__(self, name="greedy_plugin"):
        super().__init__(name=name)
        self.best_x = None
        self.best_f = None

    def on_solver_init(self, solver):
        self._step_once(solver, generation=0, use_mutation=False)

    def on_step(self, solver, generation):
        self._step_once(solver, generation=generation, use_mutation=True)

    def _step_once(self, solver, generation, use_mutation):
        context = {"generation": generation, "bounds": solver.var_bounds}
        if use_mutation and self.best_x is not None:
            candidate = solver.mutate_candidate(self.best_x, context)
        else:
            candidate = solver.init_candidate(context)
        candidate = solver.repair_candidate(candidate, context)
        obj, _ = solver.evaluate_individual(candidate, individual_id=0)
        score = float(obj[0]) if np.asarray(obj).size > 0 else float(obj)
        if self.best_f is None or score < self.best_f:
            self.best_f = score
            self.best_x = np.asarray(candidate)
        solver.best_x = self.best_x
        solver.best_objective = self.best_f


class GreedyAdapter(AlgorithmAdapter):
    """ComposableSolver：把算法逻辑写成可复用模块。"""

    def __init__(self):
        super().__init__(name="greedy_adapter")

    def propose(self, solver, context):
        if solver.best_x is None:
            return [solver.init_candidate(context)]
        return [solver.mutate_candidate(solver.best_x, context)]

    def update(self, solver, candidates, objectives, violations, context):
        obj = objectives[0]
        score = float(obj[0]) if np.asarray(obj).size > 0 else float(obj)
        if solver.best_objective is None or score < solver.best_objective:
            solver.best_objective = score
            solver.best_x = np.asarray(candidates[0])


def build_pipeline(problem):
    return RepresentationPipeline(
        initializer=UniformInitializer(low=problem.low, high=problem.high),
        mutator=GaussianMutation(sigma=0.4, low=problem.low, high=problem.high),
        repair=ClipRepair(low=problem.low, high=problem.high),
    )


def build_bias():
    bias = BiasModule()
    bias.add(ConvergenceBias(weight=0.15, early_gen=5, late_gen=20))
    return bias


def run_blank():
    problem = SimpleSphereProblem()
    solver = BlankSolverBase(problem, representation_pipeline=build_pipeline(problem), bias_module=build_bias())
    solver.max_steps = 30
    plugin = GreedyStepPlugin()
    solver.add_plugin(plugin)
    solver.run()
    return plugin.best_f, plugin.best_x


def run_composable():
    problem = SimpleSphereProblem()
    adapter = GreedyAdapter()
    solver = ComposableSolver(
        problem=problem,
        adapter=adapter,
        representation_pipeline=build_pipeline(problem),
        bias_module=build_bias(),
    )
    solver.max_steps = 30
    solver.run()
    return solver.best_objective, solver.best_x


if __name__ == "__main__":
    best_f_blank, best_x_blank = run_blank()
    print("[BlankSolverBase] best_f:", f"{best_f_blank:.6f}", "best_x:", best_x_blank)

    best_f_comp, best_x_comp = run_composable()
    print("[ComposableSolver] best_f:", f"{best_f_comp:.6f}", "best_x:", best_x_comp)
