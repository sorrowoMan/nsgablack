from nsgablack.core import EvolutionSolver, SolverBase
from nsgablack.utils.runtime.imports import import_core


def test_evolution_solver_is_solver_base_subclass():
    assert issubclass(EvolutionSolver, SolverBase)


def test_runtime_import_core_exposes_new_solver_symbols():
    core_items = import_core()
    assert core_items["EvolutionSolver"] is EvolutionSolver
    assert core_items["SolverBase"] is SolverBase
    assert "ComposableSolver" in core_items

