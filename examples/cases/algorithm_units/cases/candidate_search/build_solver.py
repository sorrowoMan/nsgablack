"""标准候选 Case：正式控制面 + 问题管线 + 独立算法构建管线。"""
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.project import apply_solver_component_overrides
from .problem.sphere import Sphere
from .pipeline import build_pipeline, build_unit_binding
from .adapter.composable_solver_fusion_demo import RandomProbeAdapter


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    config = dict(config or {})
    overrides = dict(component_overrides or {})
    config.update(overrides.pop("config", {}))
    adapter = RandomProbeAdapter(samples=int(config.get("samples", 4)))
    adapter.set_unit_binding(build_unit_binding(overrides.pop("unit_builder", None)))
    solver = ComposableSolver(problem=Sphere(), adapter=adapter,
        representation_pipeline=build_pipeline(resource_context=resource_context))
    solver.set_max_steps(int(config.get("max_steps", 3)))
    apply_solver_component_overrides(solver, overrides)
    solver.set_resource_context(resource_context)
    return solver
