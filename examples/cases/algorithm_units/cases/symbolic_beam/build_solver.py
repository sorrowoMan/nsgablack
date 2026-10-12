"""符号 Beam Case 正式装配入口。"""
from nsgablack.core.evolution_solver import EvolutionSolver
from nsgablack.project import apply_solver_component_overrides
from .config import build_parser
from .problem.pool import build_problem
from .pipeline import build_pipeline, build_unit_binding
from .adapter.beam import build_adapter


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    config = dict(config or {}) if not hasattr(config, "__dict__") else vars(config)
    config = {**config, **overrides.pop("config", {})}
    args = build_parser().parse_args([])
    for key, value in config.items():
        if not hasattr(args, key):
            raise ValueError(f"未知配置: {key}")
        setattr(args, key, value)
    problem = overrides.pop("problem", None) or build_problem(args)
    binding = build_unit_binding(overrides.pop("unit_builder", None))
    solver = EvolutionSolver(problem, adapter=build_adapter(args, unit_binding=binding),
        pop_size=max(16, int(args.beam_width) * 4), max_generations=int(args.generations),
        enable_progress_log=bool(args.progress), report_interval=max(1, int(args.report_interval)))
    solver.set_representation_pipeline(build_pipeline(args, resource_context=resource_context))
    apply_solver_component_overrides(solver, overrides)
    solver.set_resource_context(resource_context)
    return solver
