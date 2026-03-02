"""Lightweight parallel evaluation integration for solver classes.

This keeps solver bases (SolverBase / ComposableSolver) unchanged.
Users can opt-in by wrapping a solver class:

    from nsgablack.utils.parallel import with_parallel_evaluation
    ParallelBlank = with_parallel_evaluation(SolverBase)
    solver = ParallelBlank(problem, enable_parallel=True, parallel_backend="thread")
"""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional, Type, TypeVar, Union

import numpy as np

from .evaluator import ParallelEvaluator, Backend, ProblemFactory, ContextBuilder

BackendLike = Union[Backend, Literal["auto"]]

T = TypeVar("T")


def with_parallel_evaluation(
    solver_class: Type[T],
    *,
    min_population_for_parallel: int = 5,
) -> Type[T]:
    """Return a subclass that overrides evaluate_population() using ParallelEvaluator."""

    class ParallelizedSolver(solver_class):  # type: ignore[misc]
        def __init__(
            self,
            *args: Any,
            enable_parallel: Optional[bool] = None,
            parallel: Optional[bool] = None,
            enable_parallel_evaluation: Optional[bool] = None,
            parallel_backend: BackendLike = "process",
            parallel_max_workers: Optional[int] = None,
            parallel_chunk_size: Optional[int] = None,
            parallel_load_balancing: bool = True,
            parallel_retry_errors: bool = True,
            parallel_max_retries: int = 3,
            parallel_verbose: bool = False,
            parallel_precheck: bool = True,
            parallel_strict: bool = False,
            parallel_fallback_backend: Backend = "thread",
            parallel_thread_bias_isolation: Literal["deepcopy", "disable_cache", "off"] = "deepcopy",
            parallel_problem_factory: Optional[ProblemFactory] = None,
            parallel_context_builder: Optional[ContextBuilder] = None,
            parallel_extra_context: Optional[Dict[str, Any]] = None,
            **kwargs: Any,
        ) -> None:
            super().__init__(*args, **kwargs)
            enabled = enable_parallel
            if enabled is None:
                enabled = parallel
            if enabled is None:
                enabled = enable_parallel_evaluation
            self.enable_parallel_evaluation = bool(enabled)
            self.parallel_evaluator: Optional[ParallelEvaluator] = None
            self._parallel_cfg = {
                "backend": parallel_backend,
                "max_workers": parallel_max_workers,
                "chunk_size": parallel_chunk_size,
                "enable_load_balancing": parallel_load_balancing,
                "retry_errors": parallel_retry_errors,
                "max_retries": parallel_max_retries,
                "verbose": parallel_verbose,
                "precheck": parallel_precheck,
                "strict": parallel_strict,
                "fallback_backend": parallel_fallback_backend,
                "thread_bias_isolation": parallel_thread_bias_isolation,
                "problem_factory": parallel_problem_factory,
                "context_builder": parallel_context_builder,
                "extra_context": parallel_extra_context,
            }

        def _ensure_parallel_evaluator(self) -> Optional[ParallelEvaluator]:
            if not self.enable_parallel_evaluation:
                return None
            if self.parallel_evaluator is not None:
                return self.parallel_evaluator
            cfg = self._parallel_cfg
            backend = cfg["backend"]
            if backend == "auto":
                from .evaluator import SmartEvaluatorSelector
                self.parallel_evaluator = SmartEvaluatorSelector.select_evaluator(
                    getattr(self, "problem", None), getattr(self, "pop_size", 0) or 0
                )
                # Apply engineering safeguards when available.
                for key, attr in (
                    ("precheck", "precheck"),
                    ("strict", "strict"),
                    ("fallback_backend", "fallback_backend"),
                    ("thread_bias_isolation", "thread_bias_isolation"),
                    ("problem_factory", "problem_factory"),
                    ("context_builder", "context_builder"),
                    ("extra_context", "extra_context"),
                ):
                    if hasattr(self.parallel_evaluator, attr):
                        try:
                            setattr(self.parallel_evaluator, attr, cfg[key])
                        except Exception:
                            pass
                return self.parallel_evaluator

            self.parallel_evaluator = ParallelEvaluator(
                backend=backend,
                max_workers=cfg["max_workers"],
                chunk_size=cfg["chunk_size"],
                enable_load_balancing=cfg["enable_load_balancing"],
                retry_errors=cfg["retry_errors"],
                max_retries=cfg["max_retries"],
                verbose=cfg["verbose"],
                precheck=cfg["precheck"],
                strict=cfg["strict"],
                fallback_backend=cfg["fallback_backend"],
                thread_bias_isolation=cfg["thread_bias_isolation"],
                problem_factory=cfg["problem_factory"],
                context_builder=cfg["context_builder"],
                extra_context=cfg["extra_context"],
            )
            return self.parallel_evaluator

        def evaluate_population(self, population: np.ndarray, *args: Any, **kwargs: Any):
            evaluator = self._ensure_parallel_evaluator()
            if evaluator is None:
                return super().evaluate_population(population, *args, **kwargs)

            pop = np.asarray(population)
            if pop.ndim == 1:
                pop = pop.reshape(1, -1)
            if pop.shape[0] < int(min_population_for_parallel):
                return super().evaluate_population(pop, *args, **kwargs)

            # Match solver contracts as much as possible.
            problem = getattr(self, "problem", None)
            if problem is None:
                return super().evaluate_population(pop, *args, **kwargs)

            enable_bias = bool(getattr(self, "enable_bias", False))
            bias_module = getattr(self, "bias_module", None)
            return evaluator.evaluate_population(
                population=pop,
                problem=problem,
                enable_bias=enable_bias,
                bias_module=bias_module,
                return_detailed=False,
            )

    ParallelizedSolver.__name__ = f"Parallel{solver_class.__name__}"
    ParallelizedSolver.__qualname__ = ParallelizedSolver.__name__
    return ParallelizedSolver
