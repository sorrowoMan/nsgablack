"""唯一装配入口；各组件实现保留在所属目录。"""
from pathlib import Path
from nsgablack.core import ComposableSolver
from nsgablack.project import apply_solver_component_overrides
from .adapter import build_adapter
from .config import ArchiveConfig
from .pipeline import build_pipeline
from .problem import build_problem
from .plugins import ArchiveSummary


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    settings = ArchiveConfig(**{**dict(config or {}), **dict(overrides.pop("config", {}))})
    solver = ComposableSolver(problem=build_problem(), representation_pipeline=build_pipeline(),
        adapter=build_adapter(settings), resource_context=resource_context, plugin_strict=True, snapshot_strict=True)
    solver.set_random_seed(settings.seed)
    solver.set_max_steps(settings.max_steps)
    output = (Path(settings.output_dir) if settings.output_dir is not None
              else Path(__file__).resolve().parents[2] / "results" / "map_elites_archive")
    solver.add_plugin(ArchiveSummary(output))
    apply_solver_component_overrides(solver, overrides)
    return solver
