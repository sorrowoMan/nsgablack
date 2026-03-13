from __future__ import annotations

import numpy as np
import pytest

from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.blank_solver import SolverBase
from nsgablack.plugins.base import Plugin


class _Problem(BlackBoxProblem):
    def __init__(self) -> None:
        super().__init__(dimension=2, bounds=[(-1.0, 1.0), (-1.0, 1.0)])

    def evaluate(self, x):
        arr = np.asarray(x, dtype=float)
        return np.asarray([float(np.sum(arr * arr))], dtype=float)


class _OrderPlugin(Plugin):
    def __init__(self, name: str, priority: int = 0) -> None:
        super().__init__(name=name, priority=priority)


class _RequestOrderPlugin(Plugin):
    def __init__(self, name: str = "request", priority: int = 100) -> None:
        super().__init__(name=name, priority=priority)

    def on_generation_end(self, generation: int):
        if int(generation) == 0 and self.solver is not None:
            self.solver.request_plugin_order("a", after=("b",))


def _names(solver: SolverBase):
    return [str(p.name) for p in solver.plugin_manager.plugins]


def test_plugin_order_default_priority_and_stability() -> None:
    solver = SolverBase(problem=_Problem())
    solver.add_plugin(_OrderPlugin("p0", priority=0))
    solver.add_plugin(_OrderPlugin("p1", priority=10))
    solver.add_plugin(_OrderPlugin("p2", priority=0))

    assert _names(solver) == ["p0", "p2", "p1"]


def test_plugin_order_priority_conflict_is_rejected() -> None:
    solver = SolverBase(problem=_Problem())
    solver.add_plugin(_OrderPlugin("high", priority=0))
    solver.add_plugin(_OrderPlugin("low", priority=10))
    assert _names(solver) == ["high", "low"]

    with pytest.raises(Exception):
        solver.set_plugin_order("high", after=("low",))
    assert _names(solver) == ["high", "low"]


def test_plugin_order_unknown_reference_is_rejected_immediately() -> None:
    solver = SolverBase(problem=_Problem())
    solver.add_plugin(_OrderPlugin("a", priority=0))
    with pytest.raises(Exception):
        solver.set_plugin_order("a", after=("missing_component",))
    assert _names(solver) == ["a"]


def test_add_plugin_rejects_unknown_order_reference() -> None:
    solver = SolverBase(problem=_Problem())
    with pytest.raises(Exception):
        solver.add_plugin(_OrderPlugin("a", priority=0), after=("missing_component",))
    assert _names(solver) == []


def test_plugin_order_cycle_detection_and_rollback() -> None:
    solver = SolverBase(problem=_Problem())
    solver.add_plugin(_OrderPlugin("a", priority=0))
    solver.add_plugin(_OrderPlugin("b", priority=0))

    solver.set_plugin_order("a", after=("b",))
    assert _names(solver) == ["b", "a"]

    with pytest.raises(Exception):
        solver.set_plugin_order("b", after=("a",))

    # previous valid ordering should be kept after rollback
    assert _names(solver) == ["b", "a"]


def test_run_precheck_blocks_invalid_order() -> None:
    solver = SolverBase(problem=_Problem())
    solver.add_plugin(_OrderPlugin("a", priority=0))
    solver.add_plugin(_OrderPlugin("b", priority=0))
    # Inject invalid rules directly to simulate stale/legacy bad state.
    solver._plugin_scheduler._rules["a"]["after"] = {"missing_component"}  # type: ignore[attr-defined]
    with pytest.raises(RuntimeError, match="Plugin order validation failed"):
        solver.run(max_steps=1)


def test_set_plugin_order_rejected_while_running() -> None:
    solver = SolverBase(problem=_Problem())
    solver.add_plugin(_OrderPlugin("a", priority=0))
    solver.add_plugin(_OrderPlugin("b", priority=0))

    solver.running = True
    with pytest.raises(RuntimeError, match="Cannot mutate plugin topology while solver is running"):
        solver.set_plugin_order("a", after=("b",))
    solver.running = False


def test_request_plugin_order_applies_at_next_generation_boundary() -> None:
    solver = SolverBase(problem=_Problem())
    solver.add_plugin(_OrderPlugin("a", priority=0))
    solver.add_plugin(_OrderPlugin("b", priority=0))
    solver.add_plugin(_RequestOrderPlugin())

    assert _names(solver) == ["a", "b", "request"]
    solver.run(max_steps=2)
    assert _names(solver) == ["b", "a", "request"]
