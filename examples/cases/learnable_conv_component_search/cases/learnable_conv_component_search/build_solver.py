from __future__ import annotations

from pathlib import Path

try:
    from .case_scaffold.config import LearnableConvComponentSearchConfig
    from .case_scaffold.problem import LearnableConvComponentSearchProblem
    from .pipeline.main import build_pipeline
except ImportError:  # direct Case CLI execution
    from case_scaffold.config import LearnableConvComponentSearchConfig
    from case_scaffold.problem import LearnableConvComponentSearchProblem
    from pipeline.main import build_pipeline

from nsgablack.adapters import NSGA2Adapter, NSGA2Config
from nsgablack.core.evolution_solver import EvolutionSolver


class LearnableConvOuterSolver(EvolutionSolver):
    """Forward the shared Case runtime to the nested-evaluation Problem."""

    def set_case_runtime(self, runtime):
        self.case_runtime = runtime
        self.problem.set_case_runtime(runtime)
        return self


def build_learnable_conv_component_search_solver(
    cfg: LearnableConvComponentSearchConfig | None = None,
    *,
    suite_id: str,
) -> EvolutionSolver:
    config = cfg or LearnableConvComponentSearchConfig()
    output_dir = Path(config.output_dir).expanduser().resolve() / str(suite_id)
    problem = LearnableConvComponentSearchProblem(config, output_dir=output_dir)
    pipeline = build_pipeline(problem, mutation_sigma=float(config.mutation_sigma))
    adapter = NSGA2Adapter(
        NSGA2Config(
            population_size=max(4, int(config.pop_size)),
            offspring_size=max(2, int(config.offspring_size)),
            crossover_rate=float(config.crossover_rate),
            objective_aggregation="sum",
        ),
        name="learnable_conv_component_outer_nsga2",
    )
    solver = LearnableConvOuterSolver(
        problem=problem,
        adapter=adapter,
        representation_pipeline=pipeline,
        pop_size=max(4, int(config.pop_size)),
        max_generations=max(1, int(config.generations)),
        mutation_rate=0.2,
        crossover_rate=float(config.crossover_rate),
        random_seed=int(config.seed),
        enable_progress_log=False,
    )
    solver.learnable_conv_output_dir = output_dir
    return solver




def build_solver(cfg=None, *, suite_id: str = "doctor_smoke", resource_context=None, component_overrides=None):
    """Canonical scaffold entry; delegates to build_learnable_conv_component_search_solver()."""

    solver = build_learnable_conv_component_search_solver(cfg, suite_id=suite_id)
    from nsgablack.project import apply_solver_component_overrides
    apply_solver_component_overrides(solver, component_overrides)
    solver.set_resource_context(resource_context)
    return solver

__all__ = ["LearnableConvComponentSearchConfig", "build_solver", "build_learnable_conv_component_search_solver"]
