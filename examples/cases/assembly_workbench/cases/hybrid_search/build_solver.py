"""唯一装配入口：组件先组合，实际运行由正式 Case/Project 托管。"""
from pathlib import Path

from nsgablack.core import ComposableSolver
from nsgablack.core.control_plane import BudgetController
from nsgablack.core.evaluation_acceptance import FeasibleEvaluationAcceptance
from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin
from nsgablack.project import apply_solver_component_overrides

from .adapter import build_adapter
from .bias import build_bias
from .config import HybridConfig
from .evaluation import RecipeProvider
from .pipeline import build_pipeline
from .plugins import WorkbenchTrace
from .problem import RecipeProblem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    settings = HybridConfig(**{**dict(config or {}), **dict(overrides.pop("config", {}))})
    output = (Path(settings.output_dir) if settings.output_dir is not None
              else Path(__file__).resolve().parents[2] / "results" / "hybrid_search")
    pipeline, _repair = build_pipeline(settings.vns_sigma)
    solver = ComposableSolver(RecipeProblem(), representation_pipeline=pipeline,
        adapter=build_adapter(settings), bias_module=build_bias(settings.bias_weight),
        resource_context=resource_context, snapshot_strict=True, plugin_strict=True)
    solver.set_random_seed(settings.seed)
    solver.set_max_steps(settings.max_steps)
    solver.set_evaluation_acceptance_policy(FeasibleEvaluationAcceptance())
    solver.register_controller(BudgetController(max_evaluations=settings.evaluation_budget))
    if settings.evaluation_mode == "provider":
        solver.register_evaluation_provider(RecipeProvider())
    solver.add_plugin(CheckpointResumePlugin(config=CheckpointResumeConfig(
        checkpoint_dir=str(output / "checkpoints"), save_every=settings.checkpoint_every,
        save_on_finish=True, keep_last=3, trusted_roots=(str((output / "checkpoints").resolve()),))))
    solver.add_plugin(WorkbenchTrace(output, settings.max_steps))
    apply_solver_component_overrides(solver, overrides)
    return solver
