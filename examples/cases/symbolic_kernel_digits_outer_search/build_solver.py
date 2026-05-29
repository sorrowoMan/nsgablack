from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    _THIS_DIR = Path(__file__).resolve().parent
    if str(_THIS_DIR) not in sys.path:
        sys.path.insert(0, str(_THIS_DIR))
    from _bootstrap import ensure_nsgablack_importable  # noqa: E402
    from case_scaffold.config import SymbolicKernelDigitsOuterSearchConfig  # noqa: E402
    from case_scaffold.pipeline import build_representation_pipeline  # noqa: E402
    from case_scaffold.problem import SymbolicKernelDigitsOuterSearchProblem  # noqa: E402
else:
    from ._bootstrap import ensure_nsgablack_importable  # noqa: E402
    from .case_scaffold.config import SymbolicKernelDigitsOuterSearchConfig  # noqa: E402
    from .case_scaffold.pipeline import build_representation_pipeline  # noqa: E402
    from .case_scaffold.problem import SymbolicKernelDigitsOuterSearchProblem  # noqa: E402

ensure_nsgablack_importable(Path(__file__))

from nsgablack.adapters import NSGA2Adapter, NSGA2Config
from nsgablack.core.evolution_solver import EvolutionSolver


def build_symbolic_kernel_digits_outer_search_solver(
    cfg: SymbolicKernelDigitsOuterSearchConfig | None = None,
    *,
    suite_id: str,
) -> EvolutionSolver:
    config = cfg or SymbolicKernelDigitsOuterSearchConfig()
    output_dir = Path(config.output_dir).expanduser().resolve() / str(suite_id)
    problem = SymbolicKernelDigitsOuterSearchProblem(config, output_dir=output_dir)
    pipeline = build_representation_pipeline(problem, mutation_sigma=float(config.mutation_sigma))
    adapter = NSGA2Adapter(
        NSGA2Config(
            population_size=max(4, int(config.pop_size)),
            offspring_size=max(2, int(config.offspring_size)),
            crossover_rate=float(config.crossover_rate),
            objective_aggregation="sum",
        ),
        name="symbolic_kernel_digits_outer_nsga2",
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
    solver.symbolic_kernel_digits_output_dir = output_dir
    return solver




def build_solver(cfg=None, *, suite_id: str = "doctor_smoke"):
    """Canonical scaffold entry; delegates to build_symbolic_kernel_digits_outer_search_solver()."""

    return build_symbolic_kernel_digits_outer_search_solver(cfg, suite_id=suite_id)

__all__ = ["SymbolicKernelDigitsOuterSearchConfig", "build_solver", "build_symbolic_kernel_digits_outer_search_solver"]
