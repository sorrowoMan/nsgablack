"""完整最小装配配方；使用标准 Project/Case 资源和结果入口。"""
from nsgablack.project.starter import build_starter_solver
from nsgablack.project import apply_solver_component_overrides
from .pipeline import build_pipeline
from .problem import build_problem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    solver = build_starter_solver(problem=build_problem(), pipeline=build_pipeline(),
                                  resource_context=resource_context, max_steps=2)
    from nsgablack.adapters import RoleAdapter, NSGA2Adapter
    solver.set_adapter(RoleAdapter(role='explorer', inner=NSGA2Adapter(population_size=4, offspring_size=4)))
    apply_solver_component_overrides(solver, component_overrides)
    return solver
