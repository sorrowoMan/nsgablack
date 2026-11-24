"""外层唯一装配入口；不把内层求解器变成 Adapter 叶算子。"""
from pathlib import Path
from nsgablack.core import ComposableSolver
from nsgablack.project import apply_solver_component_overrides
from .config import DemoConfig
from .problem import NestedResponseProblem
from .pipeline import build_pipeline
from .adapter import build_adapter
from .plugins import NestedTracePlugin
from .solver import NestedCase

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    settings = DemoConfig(**{**dict(config or {}), **dict(overrides.pop("config", {}))})
    output_dir = Path(overrides.pop("output_dir",
        Path(__file__).resolve().parents[2] / "results" / "outer_nested"))
    solver = ComposableSolver(NestedResponseProblem(inner_steps=settings.inner_steps, output_dir=output_dir),
        adapter=build_adapter(), representation_pipeline=build_pipeline(),
        resource_context=resource_context, plugin_strict=True, snapshot_strict=True)
    solver.set_random_seed(settings.seed)
    solver.set_max_steps(settings.steps)
    solver.add_plugin(NestedTracePlugin(output_dir))
    apply_solver_component_overrides(solver, overrides)
    return NestedCase(solver, settings, output_dir)
