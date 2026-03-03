"""多算法并行协同（多策略协作）示例。

目标：演示如何用 ComposableSolver + MultiStrategyControllerAdapter
让多个策略（例如 VNS + SA）并行协同搜索，并共享最佳信息/档案。

注意：
- 这里的“并行”指策略并行（同一步生成来自多个策略的候选并统一评估）。
- 若评估本身昂贵，可结合 ParallelEvaluator / 并行 wrapper / 评估短路插件进一步加速。
"""

import numpy as np

try:
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import (
        StrategySpec,
        VNSAdapter,
        VNSConfig,
        SimulatedAnnealingAdapter,
        SAConfig,
    )
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, GaussianMutation, ClipRepair
    from nsgablack.utils.suites import attach_multi_strategy_coop, attach_vns
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import (
        StrategySpec,
        VNSAdapter,
        VNSConfig,
        SimulatedAnnealingAdapter,
        SAConfig,
    )
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, GaussianMutation, ClipRepair
    from nsgablack.utils.suites import attach_multi_strategy_coop, attach_vns


class SphereProblem(BlackBoxProblem):
    def __init__(self, dim=6, low=-5.0, high=5.0):
        super().__init__(name="Sphere", dimension=dim, bounds={f"x{i}": (low, high) for i in range(dim)})
        self.low = low
        self.high = high

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        return float(np.sum(x**2))


def main():
    np.random.seed(123)
    problem = SphereProblem()

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=problem.low, high=problem.high),
        mutator=GaussianMutation(sigma=0.6, low=problem.low, high=problem.high),
        repair=ClipRepair(low=problem.low, high=problem.high),
    )

    solver = ComposableSolver(problem=problem, representation_pipeline=pipeline)
    solver.set_max_steps(40)

    # 子策略 1：VNS（suite 可自动把 GaussianMutation 升级为 ContextGaussianMutation）
    vns = VNSAdapter(VNSConfig(batch_size=16, k_max=4, base_sigma=0.15))
    # 子策略 2：SA（顺序接受准则；这里 batch>1 主要是为了吞吐/可并行评估）
    sa = SimulatedAnnealingAdapter(SAConfig(batch_size=8, initial_temperature=8.0, cooling_rate=0.95, base_sigma=0.6))

    # 可选：先用 attach_vns() 升级 mutator（这样 VNS 的 neighborhood schedule 不会退化）
    attach_vns(solver, ensure_context_mutator=True, batch_size=16, k_max=4, base_sigma=0.15)
    # attach_vns 已设置了 solver.adapter（VNS），我们用 multi_strategy 会覆盖它，所以重新构造 spec 即可

    strategies = [
        StrategySpec(adapter=vns, name="vns", weight=0.6),
        StrategySpec(adapter=sa, name="sa", weight=0.4),
    ]
    attach_multi_strategy_coop(solver, strategies=strategies, attach_pareto_archive=True)

    result = solver.run()
    print("status:", result["status"], "steps:", result["steps"])
    print("best_score:", solver.best_objective)
    print("shared_best_score:", getattr(solver, "shared_best_score", None))
    print("strategy_stats:", getattr(solver, "shared_strategy_stats", None))


if __name__ == "__main__":
    main()
