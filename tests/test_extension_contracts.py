import numpy as np
import pytest


def test_composable_solver_rejects_wrong_candidate_shape():
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.adapters import AlgorithmAdapter
    from nsgablack.utils.extension_contracts import ContractError

    class P(BlackBoxProblem):
        def __init__(self):
            super().__init__(name="p", dimension=3, bounds={f"x{i}": (-1.0, 1.0) for i in range(3)})

        def evaluate(self, candidate):
            candidate = np.asarray(candidate, dtype=float)
            return float(np.sum(candidate * candidate))

    class BadAdapter(AlgorithmAdapter):
        def __init__(self):
            super().__init__(name="bad")

        def propose(self, control, context):
            return [np.zeros(2)]  # wrong length

        def update(self, control, candidates, feedback, context):
            _ = (control, candidates, feedback, context)

    control = ComposableSolver(problem=P(), adapter=BadAdapter())
    control.max_steps = 1
    with pytest.raises(ContractError):
        control.run()


def test_plugin_return_value_warns_by_default():
    from nsgablack.plugins import Plugin, PluginManager

    class BadPlugin(Plugin):
        def __init__(self):
            super().__init__(name="bad")

        def on_generation_start(self, generation: int):
            return True

    mgr = PluginManager()
    mgr.register(BadPlugin())

    with pytest.warns(RuntimeWarning):
        mgr.on_generation_start(0)

