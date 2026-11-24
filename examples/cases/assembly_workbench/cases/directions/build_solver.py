"""本 Case 唯一装配入口：Problem/Pipeline/Adapter/Plugin 都是显式组件。"""
from pathlib import Path

from nsgablack.core import ComposableSolver
from nsgablack.plugins import ParetoArchivePlugin
from nsgablack.project import apply_solver_component_overrides

from .adapter import build_adapter
from .config import DirectionsConfig
from .pipeline import build_pipeline
from .plugins import DirectionTrace
from .problem import build_problem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    settings = DirectionsConfig(**{**dict(config or {}), **dict(overrides.pop("config", {}))})
    output_dir = (Path(settings.output_dir) if settings.output_dir is not None
                  else Path(__file__).resolve().parents[2] / "results" / "directions")
    solver = ComposableSolver(problem=build_problem(), representation_pipeline=build_pipeline(),
        adapter=build_adapter(settings), resource_context=resource_context,
        plugin_strict=True, snapshot_strict=True)
    solver.set_random_seed(settings.seed)
    solver.set_max_steps(settings.max_steps)
    solver.add_plugin(ParetoArchivePlugin())
    solver.add_plugin(DirectionTrace(output_dir=output_dir, settings=settings))
    apply_solver_component_overrides(solver, overrides)
    return solver
