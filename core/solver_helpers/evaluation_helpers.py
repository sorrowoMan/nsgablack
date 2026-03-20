"""Evaluation-path helper functions used by SolverBase."""

from __future__ import annotations

from typing import Any, Optional, Tuple

import numpy as np

from ...utils.constraints.constraint_utils import evaluate_constraints_safe
from ..nested_solver import InnerRuntimeEvaluator
from ...utils.extension_contracts import (
    ContractError,
    normalize_candidate,
    normalize_objectives,
    normalize_violation,
)
from ...utils.evaluation.shape_validation import (
    EvaluationShapeError,
    validate_individual_evaluation_shape,
    validate_population_evaluation_shape,
)


def evaluate_individual_with_plugins_and_bias(
    solver: Any,
    x: np.ndarray,
    individual_id: Optional[int] = None,
) -> Tuple[np.ndarray, float]:
    mediator = getattr(solver, "evaluation_mediator", None)
    if mediator is not None and hasattr(mediator, "evaluate_individual"):
        providers = getattr(mediator, "list_providers", None)
        has_provider = callable(providers) and len(tuple(providers())) > 0
        if has_provider:
            return mediator.evaluate_individual(
                solver,
                x,
                individual_id=individual_id,
                context={"individual_id": individual_id},
                fallback=lambda: _evaluate_individual_via_problem(solver, x, individual_id),
            )
    return _evaluate_individual_via_problem(solver, x, individual_id)


def _evaluate_individual_via_problem(
    solver: Any,
    x: np.ndarray,
    individual_id: Optional[int],
) -> Tuple[np.ndarray, float]:
    problem = getattr(solver, "problem", None)
    evaluator = getattr(problem, "inner_runtime_evaluator", None) if problem is not None else None
    if isinstance(evaluator, InnerRuntimeEvaluator):
        nested = evaluator.evaluate(
            solver=solver,
            x=x,
            individual_id=0 if individual_id is None else int(individual_id),
            context={"individual_id": individual_id},
        )
        if nested is not None:
            obj_nested, vio_nested = nested
            obj_nested = normalize_objectives(
                obj_nested,
                num_objectives=solver.num_objectives,
                name="problem.inner_runtime.objectives",
            )
            vio_nested = normalize_violation(vio_nested, name="problem.inner_runtime.violation")
            cons_arr, violation_calc = evaluate_constraints_safe(solver.problem, np.asarray(x, dtype=float).reshape(-1))
            if np.isfinite(float(violation_calc)):
                vio_nested = float(max(float(vio_nested), float(violation_calc)))
            if solver.enable_bias and solver.bias_module is not None:
                ctx = solver.build_context(
                    individual_id=individual_id,
                    constraints=cons_arr,
                    violation=float(vio_nested),
                    individual=np.asarray(x, dtype=float).reshape(-1),
                )
                obj_nested = solver._apply_bias(
                    obj_nested,
                    np.asarray(x, dtype=float).reshape(-1),
                    individual_id,
                    ctx,
                )
                if solver.ignore_constraint_violation_when_bias:
                    vio_nested = 0.0
            solver.evaluation_count += 1
            return obj_nested, vio_nested

    x = normalize_candidate(x, dimension=solver.dimension, name="evaluate_individual.x")
    val = solver.problem.evaluate(x)
    try:
        obj_arr, vio_val = validate_individual_evaluation_shape(
            val,
            0.0,
            solver.num_objectives,
            context="problem.evaluate",
            strict=bool(getattr(solver, "plugin_strict", False)),
        )
    except EvaluationShapeError as exc:
        raise ContractError(str(exc)) from exc
    obj = normalize_objectives(obj_arr, num_objectives=solver.num_objectives, name="problem.evaluate")
    cons_arr, violation = evaluate_constraints_safe(solver.problem, x)
    try:
        violation = normalize_violation(violation, name="constraint_violation")
    except ContractError:
        if not np.isinf(float(violation)):
            raise
        violation = float(violation)
    # If validation produced a violation (non-strict coercion), merge it without
    # masking hard constraint failures (e.g., inf from constraint evaluation error).
    if np.isfinite(float(violation)) and np.isfinite(float(vio_val)):
        violation = float(max(float(violation), float(vio_val)))

    context = solver.build_context(
        individual_id=individual_id,
        constraints=cons_arr,
        violation=violation,
        individual=x,
    )
    if solver.enable_bias and solver.bias_module is not None:
        obj = solver._apply_bias(obj, x, individual_id, context)
        if solver.ignore_constraint_violation_when_bias:
            violation = 0.0

    solver.evaluation_count += 1
    return obj, violation


def evaluate_population_with_plugins_and_bias(
    solver: Any,
    population: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    mediator = getattr(solver, "evaluation_mediator", None)
    if mediator is not None and hasattr(mediator, "evaluate_population"):
        providers = getattr(mediator, "list_providers", None)
        has_provider = callable(providers) and len(tuple(providers())) > 0
        if has_provider:
            used_fallback = False
            pre_snapshot = bool(getattr(solver, "snapshot_pre_evaluate_population", False))
            if pre_snapshot:
                solver._persist_snapshot(
                    population=population,
                    objectives=None,
                    violations=None,
                    include_pareto=True,
                    include_history=True,
                    include_decision_trace=True,
                    complete=False,
                )

            def _fallback():
                nonlocal used_fallback
                used_fallback = True
                # Pre-snapshot already handled above when enabled.
                return _evaluate_population_via_problem(solver, population, pre_snapshot=False)

            objectives, violations = mediator.evaluate_population(
                solver,
                population,
                context={"population_size": int(population.shape[0]) if population is not None else None},
                fallback=_fallback,
            )
            if not used_fallback:
                try:
                    objectives, violations = validate_population_evaluation_shape(
                        objectives,
                        violations,
                        int(np.asarray(population).shape[0]),
                        solver.num_objectives,
                        context="evaluate_population.provider",
                        strict=bool(getattr(solver, "plugin_strict", False)),
                    )
                except EvaluationShapeError as exc:
                    raise ContractError(str(exc)) from exc
                solver._persist_snapshot(
                    population=population,
                    objectives=objectives,
                    violations=violations,
                    include_pareto=True,
                    include_history=True,
                    include_decision_trace=True,
                    complete=True,
                )
            return objectives, violations
    return _evaluate_population_via_problem(solver, population)


def _evaluate_population_via_problem(
    solver: Any,
    population: np.ndarray,
    *,
    pre_snapshot: Optional[bool] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    if population is None:
        raise ContractError("evaluate_population.population cannot be empty")
    population = np.asarray(population)
    if population.ndim == 1:
        population = population.reshape(1, -1)
    if population.ndim != 2 or population.shape[1] != solver.dimension:
        raise ContractError(
            f"evaluate_population.population shape mismatch: got {tuple(population.shape)} expected (N, {solver.dimension})"
        )

    pop_size = int(population.shape[0])
    if pre_snapshot is None:
        pre_snapshot = bool(getattr(solver, "snapshot_pre_evaluate_population", False))
    if bool(pre_snapshot):
        solver._persist_snapshot(
            population=population,
            objectives=None,
            violations=None,
            include_pareto=True,
            include_history=True,
            include_decision_trace=True,
            complete=False,
        )

    objectives = np.zeros((pop_size, solver.num_objectives))
    violations = np.zeros(pop_size, dtype=float)
    for idx in range(pop_size):
        obj, vio = solver.evaluate_individual(population[idx], individual_id=idx)
        if obj.size == solver.num_objectives:
            objectives[idx] = obj
        elif obj.size > solver.num_objectives:
            objectives[idx] = obj[: solver.num_objectives]
        else:
            objectives[idx, : obj.size] = obj
        violations[idx] = vio

    try:
        objectives, violations = validate_population_evaluation_shape(
            objectives,
            violations,
            pop_size,
            solver.num_objectives,
            context="evaluate_population",
            strict=bool(getattr(solver, "plugin_strict", False)),
        )
    except EvaluationShapeError as exc:
        raise ContractError(str(exc)) from exc

    solver._persist_snapshot(
        population=population,
        objectives=objectives,
        violations=violations,
        include_pareto=True,
        include_history=True,
        include_decision_trace=True,
        complete=True,
    )
    return objectives, violations
