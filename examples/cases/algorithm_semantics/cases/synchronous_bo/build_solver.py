"""固定 GP + LCB + 网格是普通可替换组件，生命周期使用公共 Solver。"""
from pathlib import Path
from nsgablack.core import ComposableSolver
from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin
from nsgablack.project import apply_solver_component_overrides
from .adapter import build_adapter
from .bias import build_bias
from .config import BOCaseConfig
from .pipeline import build_pipeline
from .plugins import BOReport
from .problem import QuadraticProblem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    settings = BOCaseConfig(**{**dict(config or {}), **dict(overrides.pop("config", {}))})
    output = (Path(settings.output_dir) if settings.output_dir else
              Path(__file__).resolve().parents[2] / "results" / "synchronous_bo")
    solver = ComposableSolver(QuadraticProblem(), adapter=build_adapter(),
        representation_pipeline=build_pipeline(), bias_module=build_bias(settings.bias_weight),
        resource_context=resource_context, snapshot_strict=True, plugin_strict=True)
    solver.set_random_seed(13)
    solver.set_max_steps(settings.max_steps)
    solver.add_plugin(CheckpointResumePlugin(config=CheckpointResumeConfig(
        checkpoint_dir=str(output / "checkpoints"), save_every=settings.checkpoint_every,
        save_on_finish=True, keep_last=8,
        trusted_roots=(str((output / "checkpoints").resolve()),))))
    solver.add_plugin(BOReport(output))
    apply_solver_component_overrides(solver, overrides)
    return solver
