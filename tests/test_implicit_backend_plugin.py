import numpy as np


def test_newton_implicit_backend_plugin_short_circuits_evaluate_individual():
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import AlgorithmAdapter
    from nsgablack.plugins import NumericalSolverConfig, NewtonSolverPlugin

    class ImplicitProblem(BlackBoxProblem):
        def __init__(self):
            super().__init__(
                name="implicit_problem",
                dimension=1,
                bounds={"x0": (-3.0, 3.0)},
            )

        def evaluate(self, x):
            # Should be bypassed by plugin in this test.
            return 999.0

        def build_implicit_system(self, x, eval_context):
            _ = eval_context
            target = float(x[0] * x[0] + 1.0)

            def residual(y):
                y_arr = np.asarray(y, dtype=float)
                return np.array([y_arr[0] * y_arr[0] - target], dtype=float)

            def jacobian(y):
                y_arr = np.asarray(y, dtype=float)
                return np.array([[2.0 * y_arr[0]]], dtype=float)

            return {"residual": residual, "x0": np.array([1.2], dtype=float), "jacobian": jacobian}

        def evaluate_from_implicit_solution(self, x, y, eval_context):
            _ = (x, eval_context)
            return float((float(y[0]) - 2.0) ** 2)

    class FixedAdapter(AlgorithmAdapter):
        def __init__(self):
            super().__init__(name="fixed")

        def propose(self, solver, context):
            _ = (solver, context)
            # x^2 + 1 = 4 -> x = sqrt(3), expected root y ~= 2
            return [np.array([np.sqrt(3.0)], dtype=float) for _ in range(4)]

    solver = ComposableSolver(problem=ImplicitProblem(), adapter=FixedAdapter())
    solver.max_steps = 1
    solver.pop_size = 4
    plugin = NewtonSolverPlugin(config=NumericalSolverConfig(tol=1e-10, max_iter=100))
    solver.add_plugin(plugin)
    solver.run()

    assert solver.best_objective is not None
    assert float(solver.best_objective) < 1e-6
    assert plugin.stats["calls"] > 0
    assert plugin.stats["success"] > 0


def test_implicit_backend_plugin_returns_none_when_problem_hooks_missing():
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.plugins import NewtonSolverPlugin

    class PlainProblem(BlackBoxProblem):
        def __init__(self):
            super().__init__(name="plain", dimension=1, bounds={"x0": (-1.0, 1.0)})

        def evaluate(self, x):
            return float(np.sum(np.asarray(x, dtype=float) ** 2))

    class DummySolver:
        problem = PlainProblem()
        dimension = 1
        num_objectives = 1
        generation = 0
        enable_bias = False
        bias_module = None
        ignore_constraint_violation_when_bias = False

    plugin = NewtonSolverPlugin()
    out = plugin.evaluate_individual(DummySolver(), np.array([0.1], dtype=float), individual_id=0)
    assert out is None
