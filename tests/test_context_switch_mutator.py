import numpy as np


def test_context_switch_mutator_selects_by_vns_k():
    from nsgablack.representation import ContextSelectMutator

    class AddOne:
        def mutate(self, x, context=None):
            return np.asarray(x, dtype=float) + 1.0

    class AddTwo:
        def mutate(self, x, context=None):
            return np.asarray(x, dtype=float) + 2.0

    op = ContextSelectMutator(mutators=[AddOne(), AddTwo()], k_key="vns_k")
    x = np.array([0.0, 0.0])

    y0 = op.mutate(x, {"vns_k": 0})
    y1 = op.mutate(x, {"vns_k": 1})
    y_big = op.mutate(x, {"vns_k": 999})  # clamp to last

    assert np.allclose(y0, [1.0, 1.0])
    assert np.allclose(y1, [2.0, 2.0])
    assert np.allclose(y_big, [2.0, 2.0])


def test_serial_mutator_applies_in_order():
    from nsgablack.representation import SerialMutator

    class AddOne:
        def mutate(self, x, context=None):
            return np.asarray(x, dtype=float) + 1.0

    class TimesTwo:
        def mutate(self, x, context=None):
            return np.asarray(x, dtype=float) * 2.0

    op = SerialMutator(mutators=[AddOne(), TimesTwo()])
    x = np.array([1.0, 3.0])
    y = op.mutate(x, {})
    assert np.allclose(y, [4.0, 8.0])


def test_context_router_mutator_routes_by_selector_key():
    from nsgablack.representation import ContextDispatchMutator

    class AddOne:
        def mutate(self, x, context=None):
            return np.asarray(x, dtype=float) + 1.0

    class AddTen:
        def mutate(self, x, context=None):
            return np.asarray(x, dtype=float) + 10.0

    op = ContextDispatchMutator(
        routes={"explore": AddOne(), "exploit": AddTen()},
        selector_key="phase",
        strict=True,
    )
    x = np.array([0.0, 0.0])

    y_explore = op.mutate(x, {"phase": "explore"})
    y_exploit = op.mutate(x, {"phase": "exploit"})

    assert np.allclose(y_explore, [1.0, 1.0])
    assert np.allclose(y_exploit, [10.0, 10.0])


def test_context_router_mutator_falls_back_when_not_strict():
    from nsgablack.representation import ContextDispatchMutator

    class AddFive:
        def mutate(self, x, context=None):
            return np.asarray(x, dtype=float) + 5.0

    op = ContextDispatchMutator(
        routes={"a": AddFive()},
        selector_key="strategy_id",
        strict=False,
    )
    x = np.array([2.0, 2.0])
    y = op.mutate(x, {"strategy_id": "unknown"})
    assert np.allclose(y, [2.0, 2.0])


