"""正式 Case 装配；生命周期和运行循环复用框架。"""
from nsgablack.core import ComposableSolver
from nsgablack.plugins import ParetoArchivePlugin
from nsgablack.project import apply_solver_component_overrides
from .adapter.workflow import build_adapter
from .config import CaseConfig
from .pipeline import build_pipeline
from .plugins import PipelineSource, WorkflowTrace
from .problem import build_problem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    settings = CaseConfig(**dict(config or {}))
    solver = ComposableSolver(problem=build_problem(), representation_pipeline=build_pipeline(),
        adapter=build_adapter(settings), resource_context=resource_context,
        plugin_strict=True, snapshot_strict=True)
    solver.set_random_seed(settings.seed)
    solver.set_max_steps(settings.max_steps)
    solver.add_plugin(PipelineSource(settings.source_count))
    solver.add_plugin(ParetoArchivePlugin())
    solver.add_plugin(WorkflowTrace(case_name="moead_search", max_steps=settings.max_steps))
    apply_solver_component_overrides(solver, component_overrides)
    return solver
