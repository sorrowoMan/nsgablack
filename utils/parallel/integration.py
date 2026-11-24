"""Lightweight parallel evaluation integration for solver classes.

This keeps solver bases (SolverBase / ComposableSolver) unchanged.
Users can opt-in by wrapping a solver class:

    from nsgablack.utils.parallel import with_parallel_evaluation
    ParallelBlank = with_parallel_evaluation(SolverBase)
    solver = ParallelBlank(problem, enable_parallel=True, parallel_backend="thread")
"""

from __future__ import annotations

import warnings
from typing import Any, Dict, Literal, Optional, Type, TypeVar, Union

import numpy as np

from .evaluator import ParallelEvaluator, Backend, ProblemFactory, ContextBuilder

BackendLike = Union[Backend, Literal["auto", "redis"]]

T = TypeVar("T")


def _has_problem_inner_runtime_evaluator(solver: Any) -> bool:
    problem = getattr(solver, "problem", None)
    evaluator = getattr(problem, "inner_runtime_evaluator", None) if problem is not None else None
    return callable(getattr(evaluator, "evaluate", None))


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
            self._parallel_requested_max_workers = parallel_max_workers
            self._parallel_has_custom_context = bool(parallel_extra_context) or parallel_context_builder is not None
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
            apply_resources = getattr(self, "_apply_resource_context_to_runtime", None)
            if callable(apply_resources):
                apply_resources()

        def _ensure_parallel_evaluator(self) -> Optional[ParallelEvaluator]:
            if not self.enable_parallel_evaluation:
                return None
            if self.parallel_evaluator is not None:
                return self.parallel_evaluator
            cfg = self._parallel_cfg
            backend = str(cfg["backend"] or "process").lower()
            if backend == "redis":
                msg = "parallel_backend='redis' is only supported for nested inner-runtime evaluation"
                if bool(cfg.get("strict", False)):
                    raise ValueError(msg)
                warnings.warn(f"{msg}; falling back to {cfg.get('fallback_backend', 'thread')!r}")
                backend = str(cfg.get("fallback_backend", "thread") or "thread").lower()
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
                            raise
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
            if _has_problem_inner_runtime_evaluator(self):
                return super().evaluate_population(population, *args, **kwargs)
            if not self.enable_parallel_evaluation:
                return super().evaluate_population(population, *args, **kwargs)
            if args or kwargs:
                return super().evaluate_population(population, *args, **kwargs)
            from ...core.solver_helpers.evaluation_helpers import (
                evaluate_external_population_with_contract,
                evaluate_population_with_plugins_and_bias,
            )
            try:
                mediator = getattr(self, "evaluation_mediator", None)
                providers = getattr(mediator, "list_providers", lambda: ())()
                if providers:
                    # Provider ownership/decline/priority remain the mediator's
                    # decision; never bypass it with direct Problem workers.
                    return evaluate_population_with_plugins_and_bias(self, population)
                backend = str(self._parallel_cfg["backend"] or "process").lower()
                if backend != "thread":
                    raise ValueError(
                        "with_parallel_evaluation formal Problem dispatch currently supports "
                        "backend='thread' only; process/ray/joblib require a verified "
                        "Feedback and Case-import boundary"
                    )
                if self._parallel_has_custom_context:
                    raise ValueError(
                        "formal parallel Problem contexts come from Solver binding/hooks; "
                        "legacy parallel_context_builder/parallel_extra_context are not supported"
                    )
                evaluator = self._ensure_parallel_evaluator()

                def evaluate_raw(limited, *, contexts):
                    return evaluator.evaluate_raw_population(
                        limited, self.problem, contexts=contexts,
                        parallel=len(limited) >= int(min_population_for_parallel),
                        requested_workers=self._parallel_requested_max_workers,
                    )

                return evaluate_external_population_with_contract(
                    self, population, evaluate_raw,
                    context_name="parallel.problem", bias_already_applied=False,
                    pass_contexts=True,
                )
            except BaseException as exc:
                dispatch = getattr(self, "_dispatch_error_once", None)
                if callable(dispatch):
                    dispatch(exc, phase="evaluate_population")
                raise

    ParallelizedSolver.__name__ = f"Parallel{solver_class.__name__}"
    ParallelizedSolver.__qualname__ = ParallelizedSolver.__name__
    return ParallelizedSolver
