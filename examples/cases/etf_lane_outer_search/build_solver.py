from __future__ import annotations

from pathlib import Path

from nsgablack.adapters import NSGA2Adapter, NSGA2Config
from nsgablack.core.evolution_solver import EvolutionSolver

try:
    from .config import EtfLaneOuterSearchConfig
    from .pipeline import build_representation_pipeline
    from .problem import EtfLaneOuterSearchProblem
except ImportError:
    from config import EtfLaneOuterSearchConfig
    from pipeline import build_representation_pipeline
    from problem import EtfLaneOuterSearchProblem


def build_etf_lane_outer_search_solver(
    cfg: EtfLaneOuterSearchConfig | None = None,
    *,
    suite_id: str,
) -> EvolutionSolver:
    config = cfg or EtfLaneOuterSearchConfig()
    output_dir = Path(config.output_dir).expanduser().resolve() / str(suite_id)
    problem = EtfLaneOuterSearchProblem(config, output_dir=output_dir)
    pipeline = build_representation_pipeline(problem, mutation_sigma=float(config.mutation_sigma))
    adapter = NSGA2Adapter(
        NSGA2Config(
            population_size=max(4, int(config.pop_size)),
            offspring_size=max(2, int(config.offspring_size)),
            crossover_rate=float(config.crossover_rate),
            objective_aggregation="sum",
        ),
        name="etf_lane_outer_nsga2",
    )
    solver = EvolutionSolver(
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
    solver.etf_outer_output_dir = output_dir
    return solver


__all__ = ["EtfLaneOuterSearchConfig", "build_etf_lane_outer_search_solver"]

