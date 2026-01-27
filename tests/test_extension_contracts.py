import numpy as np
import pytest


def test_composable_solver_rejects_wrong_candidate_shape():
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.adapters import AlgorithmAdapter
    from nsgablack.utils.extension_contracts import ContractError

    class P(BlackBoxProblem):
        def __init__(self):
            super().__init__(name="p", dimension=3, bounds={f"x{i}": (-1.0, 1.0) for i in range(3)})

        def evaluate(self, x):
            x = np.asarray(x, dtype=float)
            return float(np.sum(x * x))

    class BadAdapter(AlgorithmAdapter):
        def __init__(self):
            super().__init__(name="bad")

        def propose(self, solver, context):
            return [np.zeros(2)]  # wrong length

    solver = ComposableSolver(problem=P(), adapter=BadAdapter())
    solver.max_steps = 1
    with pytest.raises(ContractError):
        solver.run()


def test_plugin_return_value_warns_by_default():
    from nsgablack.utils.plugins import Plugin, PluginManager

    class BadPlugin(Plugin):
        def __init__(self):
            super().__init__(name="bad")

        def on_generation_start(self, generation: int):
            return True

    mgr = PluginManager()
    mgr.register(BadPlugin())

    with pytest.warns(RuntimeWarning):
        mgr.on_generation_start(0)
