"""标准 Case 装配入口；全局资源由 Project 授权。"""
from nsgablack.core import PoolRetentionPolicy
from nsgablack.project.starter import build_starter_solver
from .problem import build_problem
from .pipeline import build_pipeline
from .adapter.refinement import build_refinement_adapter


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    options = dict(config or {})
    adapter = build_refinement_adapter(
        directions=int(options.get("directions", 100)),
        view_count=options.get("view_count", 20),
        workers=int(options.get("workers", 4)),
        local_steps=int(options.get("local_steps", 3)),
    )
    solver = build_starter_solver(
        problem=build_problem(), pipeline=build_pipeline(),
        max_steps=int(options.get("max_steps", 25)), resource_context=resource_context,
        component_overrides={"adapter": adapter, **dict(component_overrides or {})},
    )
    solver.set_random_seed(int(options.get("seed", 37)))
    solver.set_solution_pool_retention(PoolRetentionPolicy(idle_steps=2))
    return solver
