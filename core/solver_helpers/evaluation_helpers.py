"""Evaluation helper utilities for SolverBase."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional, Sequence, Tuple

import numpy as np
from blackbase.resources import BudgetClaim

from ...utils.constraints.constraint_utils import evaluate_constraints_safe
from ...utils.evaluation.shape_validation import (
    EvaluationShapeError,
    validate_individual_evaluation_shape,
    validate_population_evaluation_shape,
)
from ...utils.extension_contracts import ContractError, normalize_candidate


def _strict(solver: Any) -> bool:
    return bool(getattr(solver, "plugin_strict", False))


def _checkpoint_case_runtime(solver: Any) -> None:
    checkpoint = getattr(solver, "checkpoint_case_runtime", None)
    if callable(checkpoint):
        checkpoint()


def _validate_individual_result(
    solver: Any,
    objectives: Any,
    violation: Any,
    *,
    context: str,
) -> tuple[np.ndarray, float]:
    try:
        return validate_individual_evaluation_shape(
            objectives,
            violation,
            int(getattr(solver, "num_objectives", 1) or 1),
            context=context,
            strict=_strict(solver),
        )
    except EvaluationShapeError as exc:
        raise ContractError(str(exc)) from exc


def _validate_population_result(
    solver: Any,
    objectives: Any,
    violations: Any,
    *,
    population_size: int,
    context: str,
) -> tuple[np.ndarray, np.ndarray]:
    try:
        return validate_population_evaluation_shape(
            objectives,
            violations,
            int(population_size),
            int(getattr(solver, "num_objectives", 1) or 1),
            context=context,
            strict=_strict(solver),
        )
    except EvaluationShapeError as exc:
        raise ContractError(str(exc)) from exc


def _constraint_violation(problem: Any, x: np.ndarray) -> Tuple[np.ndarray, float]:
    constraints, violation = evaluate_constraints_safe(problem, x)
    return np.asarray(constraints, dtype=float).reshape(-1), float(violation)


def _reserve_evaluations(solver: Any, requested: int) -> BudgetClaim:
    return solver.reserve_evaluation_batch(int(requested))


def _complete_evaluations(solver: Any, claim: BudgetClaim) -> None:
    solver.complete_evaluation_batch(claim)


def _consume_evaluations(solver: Any, claim: BudgetClaim, amount: int) -> None:
    solver.consume_evaluation_batch(claim, int(amount))


def _cancel_evaluations(solver: Any, claim: BudgetClaim) -> None:
    solver.cancel_evaluation_batch(claim)


def _annotate_evaluation_error(
    exc: Exception,
    *,
    phase: str,
    context: Optional[Mapping[str, Any]] = None,
) -> None:
    """Attach lightweight phase data; the run loop owns on_error dispatch."""
    if not getattr(exc, "_nsgablack_error_phase", None):
        try:
            setattr(exc, "_nsgablack_error_phase", str(phase))
        except Exception:
            pass
    details = dict(getattr(exc, "_nsgablack_error_context", {}) or {})
    for key in ("individual_id", "population_size", "evaluation_path"):
        if context is not None and key in context:
            details[key] = context[key]
    try:
        setattr(exc, "_nsgablack_error_context", details)
    except Exception:
        pass


def _evaluate_individual(
    solver: Any,
    x: Any,
    individual_id: int | None,
    *,
    context: Optional[Mapping[str, Any]] = None,
    emit_hooks: bool = True,
    budget_claim: BudgetClaim | None = None,
    budget_already_consumed: bool = False,
) -> tuple[np.ndarray, float]:
    _checkpoint_case_runtime(solver)
    arr = normalize_candidate(
        x,
        dimension=int(getattr(solver, "dimension", 0) or 0),
        name="evaluate_individual.x",
    )
    owns_claim = budget_claim is None
    claim = budget_claim if budget_claim is not None else _reserve_evaluations(solver, 1)
    claim_pending = bool(owns_claim and claim.active)
    dispatched = bool(budget_already_consumed)
    ctx = dict(context or solver.build_context(individual_id=individual_id, individual=arr))
    plugin_manager = getattr(solver, "plugin_manager", None)

    try:
        if emit_hooks and plugin_manager is not None:
            plugin_manager.on_evaluate_start(arr, ctx)

        def fallback() -> tuple[np.ndarray, float]:
            problem = getattr(solver, "problem", None)
            if problem is None or not callable(getattr(problem, "evaluate", None)):
                raise ContractError("solver.problem.evaluate must be callable")

            inner = getattr(problem, "inner_runtime_evaluator", None)
            if inner is not None and callable(getattr(inner, "evaluate", None)):
                nested = inner.evaluate(
                    solver=solver,
                    x=arr,
                    individual_id=int(individual_id or 0),
                    context=ctx,
                )
                if nested is not None:
                    obj_nested, vio_nested = _validate_individual_result(
                        solver,
                        nested[0],
                        nested[1],
                        context="problem.inner_runtime.evaluate",
                    )
                    constraints, constraint_vio = _constraint_violation(problem, arr)
                    ctx["constraints"] = constraints
                    ctx["constraint_violation"] = constraint_vio
                    if np.isfinite(constraint_vio) and np.isfinite(vio_nested):
                        vio_nested = max(float(vio_nested), float(constraint_vio))
                    return obj_nested, float(vio_nested)

            raw = problem.evaluate(arr)
            obj, shape_violation = _validate_individual_result(
                solver,
                raw,
                0.0,
                context="problem.evaluate",
            )
            constraints, violation = _constraint_violation(problem, arr)
            ctx["constraints"] = constraints
            ctx["constraint_violation"] = violation
            if np.isfinite(violation) and np.isfinite(shape_violation):
                violation = max(float(violation), float(shape_violation))
            return obj, float(violation)

        def on_dispatch(mode: str) -> None:
            nonlocal dispatched
            del mode
            if dispatched:
                return
            _consume_evaluations(solver, claim, 1)
            dispatched = True

        mediator = getattr(solver, "evaluation_mediator", None)
        if mediator is not None and callable(getattr(mediator, "evaluate_individual", None)):
            objectives, violation = mediator.evaluate_individual(
                solver,
                arr,
                individual_id=individual_id,
                context=ctx,
                fallback=fallback,
                on_dispatch=on_dispatch,
            )
        else:
            on_dispatch("fallback")
            objectives, violation = fallback()

        objectives, violation = _validate_individual_result(
            solver,
            objectives,
            violation,
            context="evaluate_individual.result",
        )
        if bool(getattr(solver, "enable_bias", False)):
            objectives = solver._apply_bias(objectives, arr, individual_id, ctx)
            if bool(getattr(solver, "ignore_constraint_violation_when_bias", False)):
                violation = 0.0
            objectives, violation = _validate_individual_result(
                solver,
                objectives,
                violation,
                context="evaluate_individual.bias",
            )

        result = (np.asarray(objectives, dtype=float).reshape(-1), float(violation))
        if emit_hooks and plugin_manager is not None:
            plugin_manager.on_evaluate_end(arr, result, ctx)
        _checkpoint_case_runtime(solver)
        if owns_claim:
            if not dispatched:
                on_dispatch("result")
            if claim_pending:
                _complete_evaluations(solver, claim)
                claim_pending = False
        return result
    except Exception as exc:
        if claim_pending:
            _cancel_evaluations(solver, claim)
        _annotate_evaluation_error(exc, phase="evaluate_individual", context=ctx)
        raise


def evaluate_individual_with_plugins_and_bias(
    solver: Any,
    x: Any,
    individual_id: int | None = None,
) -> tuple[np.ndarray, float]:
    """Evaluate one candidate through L4 mediation, hooks, bias, and validation."""
    return _evaluate_individual(solver, x, individual_id, emit_hooks=True)


def _normalize_population(solver: Any, population: Any) -> np.ndarray:
    if population is None:
        raise ContractError("evaluate_population.population cannot be empty")
    dimension = int(getattr(solver, "dimension", 0) or 0)
    try:
        pop = np.asarray(population, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"evaluate_population.population must be a numeric array: {exc}") from exc
    if pop.ndim == 1:
        pop = pop.reshape(1, -1) if pop.size else np.empty((0, dimension), dtype=float)
    if pop.ndim != 2 or pop.shape[1] != dimension:
        raise ContractError(
            "evaluate_population.population shape mismatch: "
            f"got {tuple(pop.shape)} expected (N, {dimension})"
        )
    return pop


def _persist_evaluation_snapshot(
    solver: Any,
    population: np.ndarray,
    objectives: Any,
    violations: Any,
    *,
    complete: bool,
) -> None:
    persist = getattr(solver, "_persist_snapshot", None)
    if not callable(persist):
        return
    persist(
        population=population,
        objectives=objectives,
        violations=violations,
        include_pareto=True,
        include_history=True,
        include_decision_trace=True,
        complete=bool(complete),
    )


def _evaluate_population_via_individuals(
    solver: Any,
    population: np.ndarray,
    *,
    hook_contexts: Optional[Sequence[Mapping[str, Any]]] = None,
    emit_hooks: bool = True,
    budget_claim: BudgetClaim,
    budget_already_consumed: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    objectives = []
    violations = []
    for idx, individual in enumerate(population):
        item_context = None if hook_contexts is None else hook_contexts[idx]
        obj, vio = _evaluate_individual(
            solver,
            individual,
            idx,
            context=item_context,
            emit_hooks=emit_hooks,
            budget_claim=budget_claim,
            budget_already_consumed=budget_already_consumed,
        )
        objectives.append(obj)
        violations.append(vio)
    if not objectives:
        return (
            np.zeros((0, int(getattr(solver, "num_objectives", 1) or 1)), dtype=float),
            np.zeros((0,), dtype=float),
        )
    return np.vstack(objectives), np.asarray(violations, dtype=float).reshape(-1)


def evaluate_population_with_plugins_and_bias(
    solver: Any,
    population: Any,
) -> tuple[np.ndarray, np.ndarray]:
    """Evaluate a population with cardinality, hook, counter, and snapshot closure."""
    pop = _normalize_population(solver, population)
    pop_size = int(pop.shape[0])
    claim = _reserve_evaluations(solver, pop_size)
    claim_pending = claim.active
    population_context: dict[str, Any] = {}
    try:
        _checkpoint_case_runtime(solver)
        if bool(getattr(solver, "snapshot_pre_evaluate_population", False)):
            _persist_evaluation_snapshot(solver, pop, None, None, complete=False)

        mediator = getattr(solver, "evaluation_mediator", None)
        plugin_manager = getattr(solver, "plugin_manager", None)
        providers = ()
        list_providers = getattr(mediator, "list_providers", None)
        if callable(list_providers):
            providers = tuple(list_providers())
        batch_hook_scope = bool(providers) and plugin_manager is not None
        hook_contexts: list[dict[str, Any]] = []
        if batch_hook_scope:
            for idx, individual in enumerate(pop):
                item_context = dict(
                    solver.build_context(individual_id=idx, individual=individual)
                )
                hook_contexts.append(item_context)
                plugin_manager.on_evaluate_start(individual, item_context)

        used_fallback = False
        population_context = dict(solver.build_context())

        def fallback() -> tuple[np.ndarray, np.ndarray]:
            nonlocal used_fallback
            used_fallback = True
            return _evaluate_population_via_individuals(
                solver,
                pop,
                hook_contexts=hook_contexts if batch_hook_scope else None,
                emit_hooks=not batch_hook_scope,
                budget_claim=claim,
                budget_already_consumed=batch_dispatched,
            )

        batch_dispatched = False

        def on_dispatch(mode: str) -> None:
            nonlocal batch_dispatched
            if mode != "provider" or batch_dispatched:
                return
            _consume_evaluations(solver, claim, pop_size)
            batch_dispatched = True

        if mediator is not None and callable(getattr(mediator, "evaluate_population", None)):
            objectives, violations = mediator.evaluate_population(
                solver,
                pop,
                context={**population_context, "population_size": pop_size},
                fallback=fallback,
                on_dispatch=on_dispatch,
            )
        else:
            objectives, violations = fallback()

        objectives, violations = _validate_population_result(
            solver,
            objectives,
            violations,
            population_size=pop_size,
            context="evaluate_population.result",
        )

        if not used_fallback:
            if bool(getattr(solver, "enable_bias", False)):
                adjusted = []
                for idx, individual in enumerate(pop):
                    item_context = hook_contexts[idx] if batch_hook_scope else dict(
                        solver.build_context(individual_id=idx, individual=individual)
                    )
                    biased = solver._apply_bias(objectives[idx], individual, idx, item_context)
                    row, vio = _validate_individual_result(
                        solver,
                        biased,
                        0.0 if bool(getattr(solver, "ignore_constraint_violation_when_bias", False)) else violations[idx],
                        context=f"evaluate_population.bias[{idx}]",
                    )
                    adjusted.append(row)
                    violations[idx] = vio
                objectives = np.vstack(adjusted) if adjusted else objectives

        if claim.remaining > 0:
            _consume_evaluations(solver, claim, claim.remaining)
        if claim_pending:
            _complete_evaluations(solver, claim)
            claim_pending = False

        if batch_hook_scope:
            for idx, individual in enumerate(pop):
                plugin_manager.on_evaluate_end(
                    individual,
                    (objectives[idx], float(violations[idx])),
                    hook_contexts[idx],
                )

        _checkpoint_case_runtime(solver)
        _persist_evaluation_snapshot(
            solver,
            pop,
            objectives,
            violations,
            complete=True,
        )
        return objectives, violations
    except Exception as exc:
        if claim_pending:
            _cancel_evaluations(solver, claim)
        _annotate_evaluation_error(exc, phase="evaluate_population", context=population_context)
        raise


def evaluate_external_population_with_contract(
    solver: Any,
    population: Any,
    evaluator: Callable[[np.ndarray], tuple[Any, Any]],
    *,
    context_name: str,
    bias_already_applied: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """Close the Solver evaluation contract around an external batch executor.

    Parallel and distributed executors own scheduling only. Candidate and result
    validation, lifecycle hooks, the global evaluation counter, final bias
    semantics, and snapshot persistence remain Solver responsibilities.
    """
    pop = _normalize_population(solver, population)
    _checkpoint_case_runtime(solver)
    pop_size = int(pop.shape[0])
    if pop_size == 0:
        objectives = np.zeros(
            (0, int(getattr(solver, "num_objectives", 1) or 1)),
            dtype=float,
        )
        violations = np.zeros((0,), dtype=float)
        _persist_evaluation_snapshot(
            solver,
            pop,
            objectives,
            violations,
            complete=True,
        )
        return objectives, violations

    claim = _reserve_evaluations(solver, pop_size)
    claim_pending = claim.active
    population_context: dict[str, Any] = {}
    try:
        if bool(getattr(solver, "snapshot_pre_evaluate_population", False)):
            _persist_evaluation_snapshot(solver, pop, None, None, complete=False)
        plugin_manager = getattr(solver, "plugin_manager", None)
        population_context = dict(solver.build_context())
        population_context.update(
            {
                "evaluation_path": str(context_name),
                "population_size": pop_size,
            }
        )
        hook_contexts: list[dict[str, Any]] = []
        for idx, individual in enumerate(pop):
            item_context = dict(solver.build_context(individual_id=idx, individual=individual))
            item_context["evaluation_path"] = str(context_name)
            hook_contexts.append(item_context)
            if plugin_manager is not None:
                plugin_manager.on_evaluate_start(individual, item_context)

        _consume_evaluations(solver, claim, pop_size)
        objectives, violations = evaluator(pop)
        objectives, violations = _validate_population_result(
            solver,
            objectives,
            violations,
            population_size=pop_size,
            context=f"{context_name}.result",
        )

        enable_bias = bool(getattr(solver, "enable_bias", False))
        ignore_bias_violation = bool(
            getattr(solver, "ignore_constraint_violation_when_bias", False)
        )
        if enable_bias and not bool(bias_already_applied):
            adjusted = []
            for idx, individual in enumerate(pop):
                biased = solver._apply_bias(
                    objectives[idx],
                    individual,
                    idx,
                    hook_contexts[idx],
                )
                row, vio = _validate_individual_result(
                    solver,
                    biased,
                    0.0 if ignore_bias_violation else violations[idx],
                    context=f"{context_name}.bias[{idx}]",
                )
                adjusted.append(row)
                violations[idx] = vio
            objectives = np.vstack(adjusted) if adjusted else objectives
        elif enable_bias and ignore_bias_violation:
            violations = np.zeros((pop_size,), dtype=float)

        _complete_evaluations(solver, claim)
        claim_pending = False
        if plugin_manager is not None:
            for idx, individual in enumerate(pop):
                plugin_manager.on_evaluate_end(
                    individual,
                    (objectives[idx], float(violations[idx])),
                    hook_contexts[idx],
                )

        _checkpoint_case_runtime(solver)
        _persist_evaluation_snapshot(
            solver,
            pop,
            objectives,
            violations,
            complete=True,
        )
        return objectives, violations
    except Exception as exc:
        if claim_pending:
            _cancel_evaluations(solver, claim)
        _annotate_evaluation_error(exc, phase=str(context_name), context=population_context)
        raise


__all__ = [
    "evaluate_external_population_with_contract",
    "evaluate_individual_with_plugins_and_bias",
    "evaluate_population_with_plugins_and_bias",
]
