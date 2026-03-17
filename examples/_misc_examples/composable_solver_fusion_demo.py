"""ComposableSolver 组合式适配器示例。

演示 AlgorithmAdapter + CompositeAdapter 的组合方式，
并结合表示管线、偏置与插件进行端到端运行。
"""

import numpy as np

try:
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import AlgorithmAdapter, CompositeAdapter
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, GaussianMutation, ClipRepair
    from nsgablack.bias import BiasModule, ConvergenceBias
    from nsgablack.plugins import Plugin
except ModuleNotFoundError:  # pragma: no cover - convenience for direct script runs
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import AlgorithmAdapter, CompositeAdapter
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, GaussianMutation, ClipRepair
    from nsgablack.bias import BiasModule, ConvergenceBias
    from nsgablack.plugins import Plugin


class SimpleSphereProblem(BlackBoxProblem):
    def __init__(self, dimension=6, low=-5.0, high=5.0):
        super().__init__(
            name="FusionSphere",
            dimension=dimension,
            bounds={f"x{i}": (low, high) for i in range(dimension)},
        )
        self.low = low
        self.high = high

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        return float(np.sum(x ** 2))


class RandomProbeAdapter(AlgorithmAdapter):
    def __init__(self, samples=4):
        super().__init__(name="random_probe")
        self.samples = samples

    def propose(self, solver, context):
        return [solver.init_candidate(context) for _ in range(self.samples)]


class LocalStepAdapter(AlgorithmAdapter):
    def __init__(self, samples=2):
        super().__init__(name="local_step")
        self.samples = samples

    def propose(self, solver, context):
        if solver.best_x is None:
            return []
        return [solver.mutate_candidate(solver.best_x, context) for _ in range(self.samples)]


class StepLoggerPlugin(Plugin):
    def __init__(self, name="step_logger", interval=5):
        super().__init__(name=name)
        self.interval = interval

    def on_step(self, solver, generation):
        if generation % self.interval != 0:
            return
        summary = getattr(solver, "last_step_summary", {})
        if summary:
            print(f"[step {generation}] best={summary.get('best_objective'):.4f}")


def build_solver():
    problem = SimpleSphereProblem()

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=problem.low, high=problem.high),
        mutator=GaussianMutation(sigma=0.4, low=problem.low, high=problem.high),
        repair=ClipRepair(low=problem.low, high=problem.high),
    )

    bias = BiasModule()
    bias.add(ConvergenceBias(weight=0.15, early_gen=5, late_gen=20))

    adapter = CompositeAdapter([
        RandomProbeAdapter(samples=4),
        LocalStepAdapter(samples=2),
    ])

    solver = ComposableSolver(
        problem=problem,
        adapter=adapter,
        bias_module=bias,
        representation_pipeline=pipeline,
    )
    solver.set_max_steps(30)
    solver.add_plugin(StepLoggerPlugin(interval=5))
    return solver


if __name__ == "__main__":
    solver = build_solver()
    result = solver.run()
    print("运行状态:", result["status"], "steps:", result["steps"])
    if solver.best_x is not None:
        print("最优目标值:", f"{solver.best_objective:.6f}")
        print("最优解:", solver.best_x)

