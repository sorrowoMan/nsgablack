"""标准 Case 装配入口；全局资源由 Project 授权。"""
from nsgablack.core import PoolRetentionPolicy
from nsgablack.project.starter import build_starter_solver
from .problem import build_problem
from .pipeline import build_pipeline
from .adapter.refinement import build_refinement_adapter, build_nested_refinement_adapter


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    options = dict(config or {})
    directions = int(options.get("directions", 100))
    view_count = options.get("view_count", 20)
    local_steps = int(options.get("local_steps", 3))
    nested = bool(options.get("nested_refinement", False))
    if nested:
        fine_steps = int(options.get("fine_steps", 3))
        adapter = build_nested_refinement_adapter(
            directions=directions, view_count=view_count, local_steps=local_steps,
            fine_steps=fine_steps,
        )
        selected_count = directions if view_count is None else int(view_count)
        # Each fine task accepts one baseline and at most two proposals for
        # every later update. Return competition consumes the aggregate output
        # in router batches of sixteen, so it needs its own explicit budget.
        return_candidates = selected_count * (1 + 2 * (fine_steps - 1))
        return_steps = (return_candidates + 15) // 16
        default_steps = (directions + 15) // 16 + 1 + selected_count * (local_steps + fine_steps) + return_steps + 2
    else:
        adapter = build_refinement_adapter(
            directions=directions, view_count=view_count,
            workers=int(options.get("workers", 4)), local_steps=local_steps,
            local_algorithm=str(options.get("local_algorithm", "vns")),
        )
        selected_count = directions if view_count is None else int(view_count)
        workers = int(options.get("workers", 4))
        local_algorithm = options.get("local_algorithm")
        local_batch = 2 * int(build_problem().dimension) if local_algorithm in {"pattern", "finite_difference"} else 2
        return_candidates = selected_count * (1 + local_batch * (local_steps - 1))
        default_steps = ((directions + 15) // 16 + 1
            + ((selected_count + workers - 1) // workers) * local_steps
            + (return_candidates + 15) // 16 + 2)
    solver = build_starter_solver(
        problem=build_problem(), pipeline=build_pipeline(),
        max_steps=int(options.get("max_steps", default_steps)), resource_context=resource_context,
        component_overrides={"adapter": adapter, **dict(component_overrides or {})},
    )
    solver.set_random_seed(int(options.get("seed", 37)))
    solver.set_solution_pool_retention(PoolRetentionPolicy(idle_steps=2))
    return solver
