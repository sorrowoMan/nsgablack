"""L0 Compute — execution backends, shared thread pool, parallel evaluators.

Canonical import surface: ``from nsgablack.core.resources.compute import PoolScheduler``
"""

from .pool import PoolScheduler, PoolTask, PoolResult, PoolTaskResult

__all__ = ["PoolScheduler", "PoolTask", "PoolResult", "PoolTaskResult"]


def __getattr__(name: str):
    if name in {"ParallelEvaluator", "SmartEvaluatorSelector", "create_parallel_evaluator"}:
        from nsgablack.utils.parallel.evaluator import (  # type: ignore[attr-defined]
            ParallelEvaluator, SmartEvaluatorSelector, create_parallel_evaluator,
        )
        _g = globals()
        _g["ParallelEvaluator"] = ParallelEvaluator
        _g["SmartEvaluatorSelector"] = SmartEvaluatorSelector
        _g["create_parallel_evaluator"] = create_parallel_evaluator
        return _g[name]
    if name in {"NestedParallelEvaluator", "RedisNestedDistributedEvaluator"}:
        from nsgablack.utils.parallel.nested import (  # type: ignore[attr-defined]
            NestedParallelEvaluator, RedisNestedDistributedEvaluator,
        )
        _g = globals()
        _g["NestedParallelEvaluator"] = NestedParallelEvaluator
        _g["RedisNestedDistributedEvaluator"] = RedisNestedDistributedEvaluator
        return _g[name]
    raise AttributeError(name)
