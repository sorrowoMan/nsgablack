"""Scenario demo for strict plugin order semantics."""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nsgablack.core.base import BlackBoxProblem
from nsgablack.core.blank_solver import SolverBase
from nsgablack.plugins.base import Plugin


class DemoProblem(BlackBoxProblem):
    def __init__(self) -> None:
        super().__init__(dimension=2, bounds=[(-1.0, 1.0), (-1.0, 1.0)])

    def evaluate(self, x):
        arr = np.asarray(x, dtype=float)
        return np.asarray([float(np.sum(arr * arr))], dtype=float)


class NamedPlugin(Plugin):
    def __init__(self, name: str, priority: int = 0) -> None:
        super().__init__(name=name, priority=priority)


class RequestOrderPlugin(Plugin):
    def __init__(self) -> None:
        super().__init__(name="request", priority=100)

    def on_generation_end(self, generation: int):
        if generation == 0 and self.solver is not None:
            self.solver.request_plugin_order("a", after=("b",))


def plugin_names(solver: SolverBase):
    return [str(p.name) for p in solver.plugin_manager.plugins]


def print_case(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def case_1_priority_smaller_first() -> None:
    print_case("Scenario 1: priority (smaller value runs earlier)")
    s = SolverBase(problem=DemoProblem())
    s.add_plugin(NamedPlugin("p10", priority=10))
    s.add_plugin(NamedPlugin("p0", priority=0))
    s.add_plugin(NamedPlugin("p5", priority=5))
    print(plugin_names(s))


def case_2_unknown_reference_fails() -> None:
    print_case("Scenario 2: unknown component reference")
    s = SolverBase(problem=DemoProblem())
    s.add_plugin(NamedPlugin("a", priority=0))
    try:
        s.set_plugin_order("a", after=("missing_component",))
    except Exception as exc:
        print(type(exc).__name__)
        print(exc)


def case_3_priority_conflict_fails() -> None:
    print_case("Scenario 3: priority direction conflict")
    s = SolverBase(problem=DemoProblem())
    s.add_plugin(NamedPlugin("high", priority=0))
    s.add_plugin(NamedPlugin("low", priority=10))
    try:
        s.set_plugin_order("high", after=("low",))
    except Exception as exc:
        print(type(exc).__name__)
        print(exc)


def case_4_runtime_freeze() -> None:
    print_case("Scenario 4: topology mutation while running is rejected")
    s = SolverBase(problem=DemoProblem())
    s.add_plugin(NamedPlugin("a", priority=0))
    s.add_plugin(NamedPlugin("b", priority=0))
    s.running = True
    try:
        s.set_plugin_order("a", after=("b",))
    except Exception as exc:
        print(type(exc).__name__)
        print(exc)
    finally:
        s.running = False


def case_5_request_order_boundary_apply() -> None:
    print_case("Scenario 5: request_plugin_order applies on next generation boundary")
    s = SolverBase(problem=DemoProblem())
    s.add_plugin(NamedPlugin("a", priority=0))
    s.add_plugin(NamedPlugin("b", priority=0))
    s.add_plugin(RequestOrderPlugin())
    print("before run:", plugin_names(s))
    s.run(max_steps=2)
    print("after run: ", plugin_names(s))


def case_6_nested_solver_scope_isolation() -> None:
    print_case("Scenario 6: nested solver scope isolation")
    parent = SolverBase(problem=DemoProblem())
    child = SolverBase(problem=DemoProblem())

    parent.add_plugin(NamedPlugin("parent_archive", priority=0))
    parent.add_plugin(NamedPlugin("parent_report", priority=1), after=("parent_archive",))

    child.add_plugin(NamedPlugin("child_eval", priority=0))
    child.add_plugin(NamedPlugin("child_export", priority=1), after=("child_eval",))

    print("parent order:", plugin_names(parent))
    print("child order: ", plugin_names(child))

    print("cross-scope order constraint on parent -> child name (expected fail)")
    try:
        parent.set_plugin_order("parent_report", after=("child_eval",))
    except Exception as exc:
        print(type(exc).__name__)
        print(exc)


def run_demo() -> None:
    case_1_priority_smaller_first()
    case_2_unknown_reference_fails()
    case_3_priority_conflict_fails()
    case_4_runtime_freeze()
    case_5_request_order_boundary_apply()
    case_6_nested_solver_scope_isolation()


if __name__ == "__main__":
    run_demo()
