"""
Parallel execution helpers.

Canonical imports:

    from nsgablack.utils.parallel import ParallelEvaluator, with_parallel_evaluation
"""

from .evaluator import ParallelEvaluator, SmartEvaluatorSelector, create_parallel_evaluator
from .integration import with_parallel_evaluation
from .batch import BatchEvaluator, create_batch_evaluator

__all__ = [
    "ParallelEvaluator",
    "SmartEvaluatorSelector",
    "create_parallel_evaluator",
    "with_parallel_evaluation",
    "BatchEvaluator",
    "create_batch_evaluator",
    "run_headless_in_parallel",
    "run_vns_in_parallel",
]


def __getattr__(name):  # pragma: no cover
    if name in {"run_headless_in_parallel", "run_vns_in_parallel"}:
        from .runs import run_headless_in_parallel, run_vns_in_parallel

        return {
            "run_headless_in_parallel": run_headless_in_parallel,
            "run_vns_in_parallel": run_vns_in_parallel,
        }[name]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
