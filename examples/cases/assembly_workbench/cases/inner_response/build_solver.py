"""唯一装配入口；接受父 Project 派生的资源授权。"""
from pathlib import Path
from nsgablack.core import ComposableSolver
from nsgablack.project import apply_solver_component_overrides
from .config import DemoConfig
from .problem import ResponseProblem
from .pipeline import build_pipeline
from .adapter import build_adapter
from .plugins import ResponseTracePlugin
from .solver import ResponseCase

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    settings = DemoConfig(**{**dict(config or {}), **dict(overrides.pop("config", {}))})
    payload = overrides.pop("inner_task_payload", None)
    output_dir = Path(overrides.pop("output_dir",
        Path(__file__).resolve().parents[2] / "results" / "inner_response"))
    solver = ComposableSolver(ResponseProblem(), adapter=build_adapter(),
        representation_pipeline=build_pipeline(), resource_context=resource_context,
        plugin_strict=True, snapshot_strict=True)
    solver.set_random_seed(settings.seed)
    solver.set_max_steps(settings.steps)
    solver.add_plugin(ResponseTracePlugin(output_dir))
    apply_solver_component_overrides(solver, overrides)
    return ResponseCase(solver, settings, output_dir, payload=payload)
