"""ComposableSolver + 表示管线 + 偏置 + Plugin 的最小可运行示例。

算法推进属于 Adapter，Plugin 只观察已经提交的逻辑代。这样示例与正式
StepOutcome 生命周期一致，不会让 generation hook 反过来承担算法执行。
"""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np

try:
    from nsgablack.adapters import (
        SingleTrajectoryAdaptiveAdapter,
        SingleTrajectoryAdaptiveConfig,
    )
    from nsgablack.bias import BiasModule, ConvergenceBias
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.plugins import Plugin
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import (
        ClipRepair,
        GaussianMutation,
        UniformInitializer,
    )
except ModuleNotFoundError:  # pragma: no cover - convenience for direct script runs
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.adapters import (
        SingleTrajectoryAdaptiveAdapter,
        SingleTrajectoryAdaptiveConfig,
    )
    from nsgablack.bias import BiasModule, ConvergenceBias
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.plugins import Plugin
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import (
        ClipRepair,
        GaussianMutation,
        UniformInitializer,
    )


class SimpleSphereProblem(BlackBoxProblem):
    """简单 Sphere 测试问题。"""

    def __init__(self, dimension: int = 5, low: float = -5.0, high: float = 5.0):
        super().__init__(
            name="SimpleSphere",
            dimension=dimension,
            bounds={f"x{i}": (low, high) for i in range(dimension)},
        )
        self.low = float(low)
        self.high = float(high)

    def evaluate(self, candidate: Any) -> float:
        values = np.asarray(candidate, dtype=float)
        return float(np.sum(values**2))


class CommitAuditPlugin(Plugin):
    """只审计正式提交，不持有或修改算法权威状态。"""

    def __init__(self, name: str = "commit_audit") -> None:
        super().__init__(name=name)
        self.committed_steps = 0
        self.last_outcome: dict[str, Any] = {}

    def on_generation_committed(
        self,
        generation: int,
        outcome: Mapping[str, Any],
    ) -> None:
        _ = generation
        self.committed_steps += 1
        self.last_outcome = dict(outcome)


def build_solver() -> ComposableSolver:
    problem = SimpleSphereProblem(dimension=6, low=-5.0, high=5.0)
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=problem.low, high=problem.high),
        mutator=GaussianMutation(sigma=0.5, low=problem.low, high=problem.high),
        repair=ClipRepair(low=problem.low, high=problem.high),
    )
    adapter = SingleTrajectoryAdaptiveAdapter(
        SingleTrajectoryAdaptiveConfig(
            batch_size=4,
            initial_sigma=0.5,
            min_sigma=0.05,
            max_sigma=1.5,
        )
    )
    bias = BiasModule()
    bias.add(ConvergenceBias(weight=0.2, early_gen=5, late_gen=25))

    solver = ComposableSolver(
        problem,
        adapter=adapter,
        bias_module=bias,
        representation_pipeline=pipeline,
    )
    solver.set_max_steps(40)
    solver.add_plugin(CommitAuditPlugin())
    return solver


if __name__ == "__main__":
    solver = build_solver()
    result = solver.run()

    audit = solver.get_plugin("commit_audit")
    adapter = solver.adapter
    print("运行状态:", result["status"], "steps:", result["steps"])
    if audit is not None:
        print("Plugin 已审计提交:", audit.committed_steps)
    if adapter is not None and adapter.best_x is not None:
        print("最优目标值:", f"{adapter.best_score:.6f}")
        print("最优解:", adapter.best_x)
