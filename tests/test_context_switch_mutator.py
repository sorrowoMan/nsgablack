import numpy as np


def test_context_switch_mutator_selects_by_vns_k():
    from nsgablack.representation import ContextSwitchMutator

    class AddOne:
        def mutate(self, x, context=None):
            return np.asarray(x, dtype=float) + 1.0

    class AddTwo:
        def mutate(self, x, context=None):
            return np.asarray(x, dtype=float) + 2.0

    op = ContextSwitchMutator(mutators=[AddOne(), AddTwo()], k_key="vns_k")
    x = np.array([0.0, 0.0])

    y0 = op.mutate(x, {"vns_k": 0})
    y1 = op.mutate(x, {"vns_k": 1})
    y_big = op.mutate(x, {"vns_k": 999})  # clamp to last

    assert np.allclose(y0, [1.0, 1.0])
    assert np.allclose(y1, [2.0, 2.0])
    assert np.allclose(y_big, [2.0, 2.0])

