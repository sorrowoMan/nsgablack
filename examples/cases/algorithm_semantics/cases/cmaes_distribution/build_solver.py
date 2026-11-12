"""标准唯一装配入口；公式组件在公共包，Case 只负责组合。"""
from pathlib import Path

from nsgablack.core import ComposableSolver
from nsgablack.core.control_plane import BudgetController
from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin
from nsgablack.project import apply_solver_component_overrides

from .adapter import build_adapter
from .config import CMASettings
from .pipeline import build_pipeline
from .plugins import DistributionReport
from .problem import QuadraticProblem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    settings = CMASettings(**{**dict(config or {}), **dict(overrides.pop("config", {}))})
    output = Path(settings.output_dir) if settings.output_dir else Path(__file__).resolve().parents[2] / "results" / "cmaes_distribution"
    solver = ComposableSolver(QuadraticProblem(1 if settings.fixture == "scalar" else 2),
        adapter=build_adapter(settings), representation_pipeline=build_pipeline(),
        resource_context=resource_context, snapshot_strict=True, plugin_strict=True)
    solver.set_random_seed(settings.seed)
    solver.set_max_steps(settings.max_steps)
    if settings.evaluation_budget is not None:
        solver.register_controller(BudgetController(max_evaluations=settings.evaluation_budget))
    checkpoints = output / "checkpoints"
    solver.add_plugin(CheckpointResumePlugin(config=CheckpointResumeConfig(
        checkpoint_dir=str(checkpoints), save_every=1, keep_last=10, save_on_finish=True,
        trusted_roots=(str(checkpoints.resolve()),))))
    solver.add_plugin(DistributionReport(output))
    apply_solver_component_overrides(solver, overrides)
    return solver
