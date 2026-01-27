"""Batch evaluation helper for GPU-friendly workflows.

This evaluator prefers problem.evaluate_batch(population) when available.
It runs in a single process and can chunk large batches to control memory.
"""

from __future__ import annotations

import time
import warnings
from typing import Any, Dict, Optional, Tuple, Union

import numpy as np

from ...core.base import BlackBoxProblem
from ...bias import BiasModule
from ..constraints.constraint_utils import evaluate_constraints_safe, evaluate_constraints_batch_safe


class BatchEvaluator:
    """Single-process batch evaluator with optional bias support."""

    def __init__(
        self,
        batch_size: Optional[int] = 256,
        enable_bias: bool = False,
        bias_module: Optional[BiasModule] = None,
        verbose: bool = False,
    ) -> None:
        self.batch_size = batch_size
        self.enable_bias = enable_bias
        self.bias_module = bias_module
        self.verbose = verbose

        self.stats = {
            "total_evaluations": 0,
            "total_time": 0.0,
            "avg_evaluation_time": 0.0,
            "error_count": 0,
        }

    def evaluate_population(
        self,
        population: Union[np.ndarray, list],
        problem: BlackBoxProblem,
        enable_bias: Optional[bool] = None,
        bias_module: Optional[BiasModule] = None,
        return_detailed: bool = False,
    ) -> Union[Tuple[np.ndarray, np.ndarray], Dict[str, Any]]:
        """Evaluate a population with batch preference and optional bias."""
        start_time = time.time()

        if not isinstance(population, np.ndarray):
            population = np.asarray(population)
        if population.ndim == 1:
            population = population.reshape(1, -1)

        pop_size = population.shape[0]
        num_objectives = problem.get_num_objectives()
        if num_objectives is None:
            num_objectives = 1

        objectives = np.full((pop_size, num_objectives), np.inf, dtype=float)
        constraint_violations = np.full(pop_size, np.inf, dtype=float)

        use_bias = self.enable_bias if enable_bias is None else enable_bias
        bias_module = bias_module or self.bias_module

        has_batch = callable(getattr(problem, "evaluate_batch", None))
        error_count = 0

        if has_batch:
            try:
                batch_size = self.batch_size or pop_size
                for start in range(0, pop_size, batch_size):
                    end = min(start + batch_size, pop_size)
                    chunk = population[start:end]

                    obj_chunk, cons_chunk, vio_chunk = self._evaluate_batch_chunk(
                        chunk, problem, num_objectives
                    )

                    if use_bias and bias_module is not None:
                        obj_chunk, vio_chunk = self._apply_bias_batch(
                            chunk,
                            obj_chunk,
                            cons_chunk,
                            vio_chunk,
                            start,
                            bias_module,
                        )

                    objectives[start:end] = obj_chunk
                    constraint_violations[start:end] = vio_chunk
            except Exception as exc:
                error_count += 1
                if self.verbose:
                    warnings.warn(f"Batch evaluation failed, fallback to serial: {exc}")
                objectives, constraint_violations = self._evaluate_serial(
                    population, problem, num_objectives, use_bias, bias_module
                )
        else:
            objectives, constraint_violations = self._evaluate_serial(
                population, problem, num_objectives, use_bias, bias_module
            )

        total_time = time.time() - start_time
        self.stats.update(
            {
                "total_evaluations": self.stats["total_evaluations"] + pop_size,
                "total_time": self.stats["total_time"] + total_time,
                "avg_evaluation_time": total_time / max(pop_size, 1),
                "error_count": self.stats["error_count"] + error_count,
            }
        )

        if return_detailed:
            success_rate = (pop_size - error_count) / max(pop_size, 1)
            return {
                "objectives": objectives,
                "constraint_violations": constraint_violations,
                "evaluation_time": total_time,
                "stats": self.stats.copy(),
                "error_count": error_count,
                "success_rate": success_rate,
            }

        return objectives, constraint_violations

    def _evaluate_batch_chunk(
        self,
        chunk: np.ndarray,
        problem: BlackBoxProblem,
        num_objectives: int,
    ) -> Tuple[np.ndarray, Optional[np.ndarray], np.ndarray]:
        result = problem.evaluate_batch(chunk)

        objectives, constraints, violations = self._parse_batch_result(
            result, chunk.shape[0], num_objectives
        )

        if constraints is None and violations is None:
            constraints = self._evaluate_constraints_batch(problem, chunk)

        if violations is None:
            violations = self._compute_violations(constraints, chunk.shape[0])

        return objectives, constraints, violations

    def _parse_batch_result(
        self,
        result: Any,
        batch_size: int,
        num_objectives: int,
    ) -> Tuple[np.ndarray, Optional[np.ndarray], Optional[np.ndarray]]:
        objectives = None
        constraints = None
        violations = None

        if isinstance(result, dict):
            objectives = result.get("objectives", result.get("objective"))
            constraints = result.get("constraints", result.get("constraint_values"))
            violations = result.get("constraint_violations", result.get("violations"))
        elif isinstance(result, (tuple, list)):
            if len(result) >= 2:
                objectives, constraints = result[0], result[1]
            elif len(result) == 1:
                objectives = result[0]
        else:
            objectives = result

        objectives = self._normalize_objectives(objectives, batch_size, num_objectives)

        if constraints is not None:
            constraints = self._normalize_constraints(constraints, batch_size)

        if violations is not None:
            violations = np.asarray(violations, dtype=float).reshape(-1)
            if violations.size != batch_size:
                violations = np.resize(violations, batch_size)

        return objectives, constraints, violations

    def _normalize_objectives(
        self,
        objectives: Any,
        batch_size: int,
        num_objectives: int,
    ) -> np.ndarray:
        obj_arr = np.asarray(objectives, dtype=float)
        if obj_arr.ndim == 0:
            obj_arr = obj_arr.reshape(1, 1)
        elif obj_arr.ndim == 1:
            if obj_arr.size == batch_size * num_objectives:
                obj_arr = obj_arr.reshape(batch_size, num_objectives)
            elif obj_arr.size == batch_size:
                obj_arr = obj_arr.reshape(batch_size, 1)
            elif obj_arr.size % batch_size == 0:
                obj_arr = obj_arr.reshape(batch_size, obj_arr.size // batch_size)
            else:
                obj_arr = obj_arr.reshape(1, -1)
        elif obj_arr.ndim > 2:
            obj_arr = obj_arr.reshape(batch_size, -1)

        return obj_arr

    def _normalize_constraints(self, constraints: Any, batch_size: int) -> np.ndarray:
        cons_arr = np.asarray(constraints, dtype=float)
        if cons_arr.ndim == 0:
            cons_arr = cons_arr.reshape(1, 1)
        elif cons_arr.ndim == 1:
            if cons_arr.size == batch_size:
                cons_arr = cons_arr.reshape(batch_size, 1)
            elif cons_arr.size % batch_size == 0:
                cons_arr = cons_arr.reshape(batch_size, cons_arr.size // batch_size)
            else:
                cons_arr = cons_arr.reshape(1, -1)
        elif cons_arr.ndim > 2:
            cons_arr = cons_arr.reshape(batch_size, -1)
        return cons_arr

    def _evaluate_constraints_batch(
        self, problem: BlackBoxProblem, chunk: np.ndarray
    ) -> np.ndarray:
        try:
            constraints = problem.evaluate_constraints(chunk)
            return self._normalize_constraints(constraints, chunk.shape[0])
        except Exception:
            constraints, _ = evaluate_constraints_batch_safe(problem, chunk)
            return constraints

    def _compute_violations(
        self, constraints: Optional[np.ndarray], batch_size: int
    ) -> np.ndarray:
        if constraints is None or constraints.size == 0:
            return np.zeros(batch_size, dtype=float)
        return np.sum(np.maximum(constraints, 0.0), axis=1)

    def _apply_bias_batch(
        self,
        chunk: np.ndarray,
        objectives: np.ndarray,
        constraints: Optional[np.ndarray],
        violations: np.ndarray,
        offset: int,
        bias_module: BiasModule,
    ) -> Tuple[np.ndarray, np.ndarray]:
        obj_out = objectives.copy()
        vio_out = violations.copy()

        for i in range(chunk.shape[0]):
            constraints_list = []
            if constraints is not None and constraints.size > 0:
                constraints_list = list(np.asarray(constraints[i]).flatten())

            context = {
                "constraints": constraints_list,
                "constraint_violation": float(vio_out[i]),
                "individual_id": offset + i,
            }

            if callable(getattr(bias_module, "compute_bias_vector", None)) and obj_out.shape[1] > 1:
                obj_out[i] = bias_module.compute_bias_vector(
                    chunk[i], obj_out[i], offset + i, context=context
                )
            else:
                for j in range(obj_out.shape[1]):
                    obj_out[i, j] = bias_module.compute_bias(
                        chunk[i], float(obj_out[i, j]), offset + i, context=context
                    )

            if not constraints_list and "constraint_violation" in context:
                try:
                    vio_out[i] = float(context["constraint_violation"])
                except Exception:
                    pass

        return obj_out, vio_out

    def _evaluate_serial(
        self,
        population: np.ndarray,
        problem: BlackBoxProblem,
        num_objectives: int,
        enable_bias: bool,
        bias_module: Optional[BiasModule],
    ) -> Tuple[np.ndarray, np.ndarray]:
        pop_size = population.shape[0]
        objectives = np.zeros((pop_size, num_objectives), dtype=float)
        violations = np.zeros(pop_size, dtype=float)

        for i in range(pop_size):
            obj = np.asarray(problem.evaluate(population[i]), dtype=float).flatten()
            if obj.size == 1 and num_objectives > 1:
                obj = np.resize(obj, num_objectives)
            elif obj.size != num_objectives:
                obj = np.resize(obj, num_objectives)

            cons_arr, violation = evaluate_constraints_safe(problem, population[i])

            if enable_bias and bias_module is not None:
                context = {
                    "constraints": list(cons_arr),
                    "constraint_violation": violation,
                    "individual_id": i,
                }
                for j in range(num_objectives):
                    obj[j] = bias_module.compute_bias(
                        population[i], float(obj[j]), i, context=context
                    )
                if cons_arr.size == 0 and "constraint_violation" in context:
                    try:
                        violation = float(context["constraint_violation"])
                    except Exception:
                        pass

            objectives[i] = obj
            violations[i] = violation

        return objectives, violations

    def get_stats(self) -> Dict[str, Any]:
        """Return evaluation statistics."""
        return self.stats.copy()

    def reset_stats(self) -> None:
        """Reset evaluation statistics."""
        self.stats = {
            "total_evaluations": 0,
            "total_time": 0.0,
            "avg_evaluation_time": 0.0,
            "error_count": 0,
        }


def create_batch_evaluator(
    batch_size: Optional[int] = 256,
    **kwargs: Any,
) -> BatchEvaluator:
    """Convenience factory for BatchEvaluator."""
    return BatchEvaluator(batch_size=batch_size, **kwargs)
