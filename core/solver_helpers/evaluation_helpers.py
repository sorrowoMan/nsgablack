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


def evaluate_individual_with_plugins_and_bias(
    solver: Any,
    x: np.ndarray,
    individual_id: Optional[int] = None,
) -> Tuple[np.ndarray, float]:
    overridden = solver.plugin_manager.trigger("evaluate_individual", solver, x, individual_id)
    if overridden is not None:
        try:
            obj, vio = overridden
        except Exception as exc:  # pragma: no cover
            raise ContractError("evaluate_individual plugin return must be (objectives, violation)") from exc
        obj = normalize_objectives(obj, num_objectives=solver.num_objectives, name="plugin.evaluate_individual.objectives")
        vio = normalize_violation(vio, name="plugin.evaluate_individual.violation")
        solver.evaluation_count += 1
        return obj, vio

    x = normalize_candidate(x, dimension=solver.dimension, name="evaluate_individual.x")
    val = solver.problem.evaluate(x)
    obj = normalize_objectives(val, num_objectives=solver.num_objectives, name="problem.evaluate")
    cons_arr, violation = evaluate_constraints_safe(solver.problem, x)
    try:
        violation = normalize_violation(violation, name="constraint_violation")
    except ContractError:
        if not np.isinf(float(violation)):
            raise
        violation = float(violation)

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
        try:
            objectives, violations = overridden
        except Exception as exc:  # pragma: no cover
            raise ContractError("evaluate_population plugin return must be (objectives, violations)") from exc
        objectives = np.asarray(objectives, dtype=float)
        violations = np.asarray(violations, dtype=float).ravel()
        if objectives.ndim != 2 or objectives.shape[1] != solver.num_objectives:
            raise ContractError(
                f"plugin.evaluate_population.objectives shape mismatch: got {tuple(objectives.shape)} expected (N, {solver.num_objectives})"
            )
        if violations.shape[0] != objectives.shape[0]:
            raise ContractError(
                f"plugin.evaluate_population.violations length mismatch: got {int(violations.shape[0])} expected {int(objectives.shape[0])}"
            )
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
