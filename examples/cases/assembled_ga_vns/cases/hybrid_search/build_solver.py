"""唯一装配入口；Project 的 L0 授权通过 resource_context 传入。"""
from pathlib import Path
from nsgablack.core import ComposableSolver
from nsgablack.core.control_plane import BudgetController
from nsgablack.project import apply_solver_component_overrides
from .adapter import build_adapter
from .bias import build_bias
from .config import DemoConfig
from .pipeline import build_pipeline
from .plugins import build_plugin
from .problem import build_problem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    options = {**dict(config or {}), **dict(overrides.pop("config", {}))}
    settings = DemoConfig(**options)
    results = Path(__file__).resolve().parents[2] / "results"
    solver = ComposableSolver(
        problem=build_problem(), representation_pipeline=build_pipeline(),
        adapter=build_adapter(settings), bias_module=build_bias(),
        resource_context=resource_context, plugin_strict=True, snapshot_strict=True,
    )
    solver.set_random_seed(settings.seed)
    solver.set_max_steps(settings.max_steps)
    if settings.evaluation_budget is not None:
        solver.register_controller(BudgetController(max_evaluations=settings.evaluation_budget))
    if settings.schedule == "plan":
        results = results / "plan"
    elif settings.refinement_source == "elite":
        results = results / "elite"
    solver.add_plugin(build_plugin(output_dir=results, max_records=settings.max_steps))
    apply_solver_component_overrides(solver, overrides)
    return solver
