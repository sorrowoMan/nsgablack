"""唯一规范装配入口；不在这里另写评估或搜索循环。"""
from nsgablack.core import ComposableSolver
from nsgablack.project import apply_solver_component_overrides
from .adapter import build_adapter
from .pipeline import build_pipeline
from .problem import build_problem
from .plugins import FixedCandidateTrace


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    options = dict(config or {})
    solver = ComposableSolver(
        problem=build_problem(),
        representation_pipeline=build_pipeline(),
        adapter=build_adapter(
            candidate=options.get("candidate", (0.25, 0.75)),
            use_pipeline_initializer=bool(options.get("use_pipeline_initializer", False)),
        ),
        resource_context=resource_context,
    )
    solver.set_random_seed(17)
    solver.set_max_steps(1)
    solver.add_plugin(FixedCandidateTrace())
    apply_solver_component_overrides(solver, component_overrides)
    return solver
