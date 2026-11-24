"""One canonical Case assembly; resource authorization comes from Project L0."""
from pathlib import Path
from nsgablack.core import ComposableSolver
from nsgablack.project import apply_solver_component_overrides
from .config import DemoConfig
from .problem import build_problem
from .pipeline import build_pipeline
from .adapter import build_adapter
from .plugins import PoolTracePlugin


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    settings = DemoConfig(**{**dict(config or {}), **dict(overrides.pop("config", {}))})
    solver = ComposableSolver(problem=build_problem(), representation_pipeline=build_pipeline(),
                              adapter=build_adapter(settings), resource_context=resource_context,
                              plugin_strict=True, snapshot_strict=True)
    solver.set_random_seed(settings.seed)
    solver.set_max_steps(settings.max_steps)
    solver.add_plugin(PoolTracePlugin(output_dir=Path(__file__).resolve().parents[2] / "results",
                                      max_records=settings.max_steps))
    apply_solver_component_overrides(solver, overrides)
    return solver
