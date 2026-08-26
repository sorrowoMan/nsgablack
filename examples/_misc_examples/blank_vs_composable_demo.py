"""显式 SolverBase 子类与 ComposableSolver 的对比示例。

两条路径都遵守 StepOutcome 与原子 incumbent 协议：
- SolverBase：在专用 Solver 子类中显式实现完整控制步骤；
- ComposableSolver：把搜索策略放进可复用 Adapter。

实际项目优先选择第二条路径。Plugin 不承担算法推进，只扩展观测与运行能力。
"""

from __future__ import annotations

from typing import Any

import numpy as np

try:
    from nsgablack.adapters import AlgorithmAdapter
    from nsgablack.bias import BiasModule, ConvergenceBias
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.blank_solver import SolverBase
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.state import IncumbentState, StepOutcome
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
    from nsgablack.adapters import AlgorithmAdapter
    from nsgablack.bias import BiasModule, ConvergenceBias
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.blank_solver import SolverBase
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.state import IncumbentState, StepOutcome
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import (
        ClipRepair,
        GaussianMutation,
        UniformInitializer,
    )


class SimpleSphereProblem(BlackBoxProblem):
    def __init__(self, dimension: int = 6, low: float = -5.0, high: float = 5.0):
        super().__init__(
            name="CompareSphere",
            dimension=dimension,
            bounds={f"x{i}": (low, high) for i in range(dimension)},
        )
        self.low = float(low)
        self.high = float(high)

    def evaluate(self, candidate: Any) -> float:
        values = np.asarray(candidate, dtype=float)
        return float(np.sum(values**2))


class ExplicitGreedySolver(SolverBase):
    """展示直接继承 SolverBase 时必须自行闭合的正式步骤。"""

    def step(self) -> StepOutcome:
        context = {"generation": self.generation, "bounds": self.var_bounds}
        incumbent = self.get_incumbent()
        if incumbent is None:
            candidate = self.init_candidate(context)
        else:
            candidate = self.mutate_candidate(incumbent.candidate, context)
        candidate = self.repair_candidate(candidate, context)

        population = np.asarray(candidate, dtype=float).reshape(1, -1)
        objectives, violations = self.evaluate_population(population)
        score = float(np.sum(objectives[0]))
        violation = float(violations[0])
        candidate_batch = self.commit_candidate_population(population, None)
        self.population = population
        self.objectives = np.asarray(objectives, dtype=float)
        self.constraint_violations = np.asarray(violations, dtype=float)

        incumbent = self.get_incumbent()
        candidate_feasible = violation <= 0.0
        incumbent_feasible = bool(
            incumbent is not None and incumbent.constraint_violation <= 0.0
        )
        better = (
            incumbent is None
            or (candidate_feasible and not incumbent_feasible)
            or (
                candidate_feasible == incumbent_feasible
                and (
                    (
                        not candidate_feasible
                        and violation < incumbent.constraint_violation
                    )
                    or (candidate_feasible and score < incumbent.score)
                )
            )
        )
        if better:
            self.set_incumbent(
                IncumbentState(
                    candidate=population[0],
                    objectives=objectives[0],
                    constraint_violation=violation,
                    score=score,
                    candidate_token=candidate_batch.candidate_tokens[0],
                    source="explicit_solver_step",
                    source_run_id=self._active_run_id,
                )
            )
        self.write_population_snapshot(population, objectives, violations)
        return StepOutcome(
            status="committed",
            proposals=1,
            evaluations=1,
            metadata={"implementation": "explicit_solver_subclass"},
        )


class GreedyAdapter(AlgorithmAdapter):
    """同一策略通过 Adapter 复用 ComposableSolver 的完整提交逻辑。"""

    def __init__(self) -> None:
        super().__init__(name="greedy_adapter")

    def propose(self, control: Any, context: dict[str, Any]):
        if control.best_x is None:
            return [control.init_candidate(context)]
        return [control.mutate_candidate(control.best_x, context)]

    def update(self, control: Any, candidates: Any, feedback: Any, context: Any) -> None:
        # ComposableSolver 在调用 update() 前已经原子提交权威 incumbent。
        _ = (control, candidates, feedback, context)


def build_pipeline(problem: SimpleSphereProblem) -> RepresentationPipeline:
    return RepresentationPipeline(
        initializer=UniformInitializer(low=problem.low, high=problem.high),
        mutator=GaussianMutation(sigma=0.4, low=problem.low, high=problem.high),
        repair=ClipRepair(low=problem.low, high=problem.high),
    )


def build_bias() -> BiasModule:
    bias = BiasModule()
    bias.add(ConvergenceBias(weight=0.15, early_gen=5, late_gen=20))
    return bias


def run_blank():
    problem = SimpleSphereProblem()
    solver = ExplicitGreedySolver(
        problem,
        representation_pipeline=build_pipeline(problem),
        bias_module=build_bias(),
    )
    solver.set_max_steps(30)
    solver.run()
    return solver.best_objective, solver.best_x


def run_composable():
    problem = SimpleSphereProblem()
    solver = ComposableSolver(
        problem=problem,
        adapter=GreedyAdapter(),
        representation_pipeline=build_pipeline(problem),
        bias_module=build_bias(),
    )
    solver.set_max_steps(30)
    solver.run()
    return solver.best_objective, solver.best_x


if __name__ == "__main__":
    best_f_blank, best_x_blank = run_blank()
    print("[SolverBase] best_f:", f"{best_f_blank:.6f}", "best_x:", best_x_blank)

    best_f_comp, best_x_comp = run_composable()
    print("[ComposableSolver] best_f:", f"{best_f_comp:.6f}", "best_x:", best_x_comp)
