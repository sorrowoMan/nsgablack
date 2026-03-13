"""Evaluation-path helper functions used by SolverBase."""

from __future__ import annotations

from typing import Any, Optional, Tuple

import numpy as np

from ...utils.constraints.constraint_utils import evaluate_constraints_safe
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
    validate_plugin_short_circuit_return,
)


def evaluate_individual_with_plugins_and_bias(
    solver: Any,
    x: np.ndarray,
    individual_id: Optional[int] = None,
) -> Tuple[np.ndarray, float]:
    overridden = solver.plugin_manager.trigger("evaluate_individual", solver, x, individual_id)
    if overridden is not None:
        result = validate_plugin_short_circuit_return(
            overridden,
            expected_mode="individual",
            population_size=None,
            num_objectives=solver.num_objectives,
            context="plugin.evaluate_individual",
            strict=bool(getattr(solver, "plugin_strict", False)),
        )
        if result is not None:
            obj, vio = result
            obj = normalize_objectives(
                obj,
                num_objectives=solver.num_objectives,
                name="plugin.evaluate_individual.objectives",
            )
            vio = normalize_violation(vio, name="plugin.evaluate_individual.violation")
            solver.evaluation_count += 1
            return obj, vio

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
    # If validation produced a violation (non-strict coercion), respect it.
    if not np.isfinite(float(violation)) and np.isfinite(float(vio_val)):
        violation = float(vio_val)

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
    overridden = solver.plugin_manager.trigger("evaluate_population", solver, population)
    if overridden is not None:
        result = validate_plugin_short_circuit_return(
            overridden,
            expected_mode="population",
            population_size=int(population.shape[0]) if population is not None else None,
            num_objectives=solver.num_objectives,
            context="plugin.evaluate_population",
            strict=bool(getattr(solver, "plugin_strict", False)),
        )
        if result is not None:
            objectives, violations = result
            return objectives, violations

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
