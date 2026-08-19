import numpy as np
import pytest

from blackbase.types import UnknownState


def test_candidate_boundary_consumes_shared_unknown_state_protocol():
    from nsgablack.utils.extension_contracts import normalize_candidate

    candidate = UnknownState(
        values=np.asarray([1.0, -2.0], dtype=float),
        metadata={"provider": "test"},
    )

    normalized = normalize_candidate(candidate, dimension=2)

    assert isinstance(normalized, np.ndarray)
    assert normalized.dtype != object
    assert np.array_equal(normalized, [1.0, -2.0])


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

