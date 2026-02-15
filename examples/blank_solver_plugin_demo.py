"""�հ������ + ƫ��/����/��� �����ʾ��

Ŀ�꣺�� BlankSolverBase ����һ���ǽ������̣�������� + ̰�ı������
��ʾ��ΰѱ�ʾ���ߡ�ƫ��ϵͳ����ϵͳƴװ���Զ����㷨��
"""

import numpy as np

try:
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.blank_solver import BlankSolverBase
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, GaussianMutation, ClipRepair
    from nsgablack.bias import BiasModule, ConvergenceBias
    from nsgablack.plugins import Plugin
except ModuleNotFoundError:  # pragma: no cover - convenience for direct script runs
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.blank_solver import BlankSolverBase
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.continuous import UniformInitializer, GaussianMutation, ClipRepair
    from nsgablack.bias import BiasModule, ConvergenceBias
    from nsgablack.plugins import Plugin


class SimpleSphereProblem(BlackBoxProblem):
    """�� Sphere ��Ŀ�����⡣"""

    def __init__(self, dimension=5, low=-5.0, high=5.0):
        super().__init__(
            name="SimpleSphere",
            dimension=dimension,
            bounds={f"x{i}": (low, high) for i in range(dimension)},
        )
        self.low = low
        self.high = high

    def evaluate(self, x):
        x = np.asarray(x, dtype=float)
        return float(np.sum(x ** 2))


class RandomWalkPlugin(Plugin):
    """������� + ̰�ı���Ĳ�������̡�"""

    def __init__(self, name="random_walk", buffer_size=20):
        super().__init__(name=name)
        self.buffer_size = buffer_size
        self.best_x = None
        self.best_f = None
        self._population = []
        self._objectives = []
        self._violations = []

    def on_solver_init(self, solver):
        context = {"generation": 0, "bounds": solver.var_bounds}
        candidate = solver.init_candidate(context)
        candidate = solver.repair_candidate(candidate, context)
        obj, vio = solver.evaluate_individual(candidate, individual_id=0)
        self._update_buffers(solver, candidate, obj, vio)
        self._maybe_update_best(candidate, obj)

    def on_step(self, solver, generation):
        context = {"generation": generation, "bounds": solver.var_bounds}
        if self.best_x is None:
            candidate = solver.init_candidate(context)
        else:
            candidate = solver.mutate_candidate(self.best_x, context)
        candidate = solver.repair_candidate(candidate, context)

        obj, vio = solver.evaluate_individual(candidate, individual_id=0)
        self._update_buffers(solver, candidate, obj, vio)
        self._maybe_update_best(candidate, obj)

    def _update_buffers(self, solver, candidate, obj, vio):
        self._population.append(np.asarray(candidate))
        self._objectives.append(np.asarray(obj))
        self._violations.append(float(vio))

        if len(self._population) > self.buffer_size:
            self._population.pop(0)
            self._objectives.pop(0)
            self._violations.pop(0)

        solver.population = np.asarray(self._population)
        solver.objectives = np.asarray(self._objectives)
        solver.constraint_violations = np.asarray(self._violations)

    def _maybe_update_best(self, candidate, obj):
        value = float(obj[0]) if np.asarray(obj).size > 0 else float(obj)
        if self.best_f is None or value < self.best_f:
            self.best_f = value
            self.best_x = np.asarray(candidate)


def build_solver():
    problem = SimpleSphereProblem(dimension=6, low=-5.0, high=5.0)

    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=problem.low, high=problem.high),
        mutator=GaussianMutation(sigma=0.5, low=problem.low, high=problem.high),
        repair=ClipRepair(low=problem.low, high=problem.high),
    )

    bias = BiasModule()
    bias.add(ConvergenceBias(weight=0.2, early_gen=5, late_gen=25))

    solver = BlankSolverBase(problem, bias_module=bias, representation_pipeline=pipeline)
    solver.max_steps = 40
    solver.add_plugin(RandomWalkPlugin(buffer_size=20))
    return solver


if __name__ == "__main__":
    solver = build_solver()
    result = solver.run()

    plugin = solver.get_plugin("random_walk")
    print("����״̬:", result["status"], "steps:", result["steps"])
    if plugin is not None and plugin.best_x is not None:
        print("����Ŀ��ֵ:", f"{plugin.best_f:.6f}")
        print("���Ž�:", plugin.best_x)

