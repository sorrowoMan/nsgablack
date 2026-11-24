"""SA 的独立 Solver；不与 DE 共享运行状态或母池。"""
from nsgablack.core import ComposableSolver
from nsgablack.project import apply_solver_component_overrides
from .adapter import build_adapter
from .config import SEED, MAX_STEPS
from .pipeline import build_pipeline
from .problem import build_problem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    options = dict(config or {})
    solver = ComposableSolver(problem=build_problem(), adapter=build_adapter(),
                             representation_pipeline=build_pipeline(), resource_context=resource_context,
                             plugin_strict=True, snapshot_strict=True)
    solver.set_random_seed(int(options.get("seed", SEED)))
    solver.set_max_steps(int(options.get("max_steps", MAX_STEPS)))
    apply_solver_component_overrides(solver, component_overrides)
    return solver
