"""Quality selection must preserve raw semantics and reject misleading plans."""
from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from examples.cases.production_scheduling.cases.production_scheduling.problem.production_problem import (
    ProductionConstraints,
    ProductionSchedulingProblem,
    ProductionSchedulingSingleObjectiveProblem,
)
from examples.cases.production_scheduling.cases.production_scheduling.refactor_data import ProductionData
from examples.cases.production_scheduling.cases.production_scheduling.reporting.quality_selection import (
    evaluate_schedule_quality,
    select_schedule_quality,
)


def make_problem(cls=ProductionSchedulingProblem):
    data = ProductionData(
        machines=2, materials=1, days=3, bom_matrix=np.ones((2, 1), dtype=bool),
        supply_matrix=np.array([[20.0, 20.0, 20.0]]), machine_weights=np.ones(2))
    return cls(data, ProductionConstraints(max_machines_per_day=2,
        min_machines_per_day=1, min_production_per_machine=2,
        max_production_per_machine=100, include_penalty_objective=False))


def report(vector, *, feasible=True):
    return {"raw_objectives": list(vector), "hard_feasible": feasible,
            "audit": {"production": {"total": -float(vector[0]),
                                     "daily_cv": float(np.sqrt(vector[1])) if len(vector) > 1 else 0.0}}}


def test_integer_export_recalculates_actual_delivered_quantity_without_mutation():
    problem = make_problem()
    schedule = np.array([[2.9, 2.1, 0.0], [0.0, 0.0, 3.8]])
    original = schedule.copy()
    supply, bom = problem.data.supply_matrix.copy(), problem.data.bom_matrix.copy()
    result = evaluate_schedule_quality(problem, schedule, integer_export=True)
    assert result["raw_objectives"][0] == -7.0
    assert result["audit"]["production"]["total"] == 7.0
    assert result["input_total"] == pytest.approx(8.8)
    assert result["floor_output_delta"] == pytest.approx(1.8)
    assert result["integer_schedule"] and result["hard_feasible"]
    np.testing.assert_array_equal(schedule, original)
    np.testing.assert_array_equal(problem.data.supply_matrix, supply)
    np.testing.assert_array_equal(problem.data.bom_matrix, bom)


def test_future_supply_cannot_cover_an_earlier_shortage_even_if_raw_guard_is_wrong():
    class IncompleteGuard(ProductionSchedulingProblem):
        def evaluate_constraints(self, candidate):
            return np.zeros(5)

    problem = make_problem(IncompleteGuard)
    result = evaluate_schedule_quality(problem, np.array([[25, 0, 0], [0, 0, 0]]))
    assert result["raw_hard_feasible"] is True
    assert result["min_cumulative_stock"] == -5
    assert result["independent_stock_feasible"] is False
    assert result["hard_feasible"] is False


def test_soft_deviations_are_exposed_without_becoming_hard_rules():
    result = evaluate_schedule_quality(make_problem(), np.array([[1, 0, 3], [0, 0, 0]]))
    assert result["hard_feasible"]
    assert result["soft_deviations"]["days_below_minimum_active"] == 1
    assert result["soft_deviations"]["positive_cells_below_minimum_production"] == 1
    assert result["soft_deviations"]["minimum_production_shortfall"] == 1.0
    assert result["soft_deviations"]["minimum_production_is_soft"]


def test_pareto_default_keeps_tradeoffs_and_never_selects_infeasible_high_output():
    reports = [report([-100, 1.0, 0.2, 0.2]), report([-90, 0.1, 0.2, 0.2]),
               report([-80, 0.9, 0.3, 0.3]), report([-1000, 0.0, 0, 0], feasible=False)]
    result = select_schedule_quality(reports)
    assert result["selected_indices"] == result["non_dominated_indices"] == [0, 1]
    assert result["scores"] == []
    assert select_schedule_quality(reports, policy="production")["selected_indices"] == [0]
    assert select_schedule_quality(reports, policy="stability")["selected_indices"] == [1]
    assert select_schedule_quality(reports, policy="stability", minimum_output_fraction=0.95)["selected_indices"] == [0]


def test_balanced_regret_is_invariant_to_production_units_and_preserves_raw_scores():
    reports = [report([-100000, 1, 0.2, 0.2]), report([-80000, 0.1, 0.2, 0.2]),
               report([-92000, 0.3, 0.2, 0.2])]
    before = deepcopy(reports)
    result = select_schedule_quality(reports, policy="balanced")
    assert result["selected_indices"] == [2]
    assert result["ideal_point"] == [-100000, 0.1, 0.2, 0.2]
    assert result["nadir_point"] == [-80000, 1.0, 0.2, 0.2]
    assert result["objective_scales"] == [20000, 0.9, 0.0, 0.0]
    assert result["weights"] == [0.25, 0.25, 0.25, 0.25]
    assert reports == before
    rescaled = deepcopy(reports)
    for item in rescaled:
        item["raw_objectives"][0] *= 0.001
    assert select_schedule_quality(rescaled, policy="balanced")["selected_indices"] == [2]


def test_single_objective_baseline_supports_production_but_not_fake_balanced_comparison():
    evaluated = evaluate_schedule_quality(make_problem(ProductionSchedulingSingleObjectiveProblem),
                                          np.array([[3, 3, 3], [0, 0, 0]]))
    assert evaluated["raw_objective_count"] == 1
    assert select_schedule_quality([evaluated], policy="production")["selected_indices"] == [0]
    with pytest.raises(ValueError, match="same original four/five-objective"):
        select_schedule_quality([evaluated], policy="balanced")


@pytest.mark.parametrize("schedule", [np.ones((3, 2)), np.array([[np.nan, 0, 0], [0, 0, 0]]),
                                     np.array([[-1, 0, 0], [0, 0, 0]])])
def test_invalid_candidate_cannot_be_cleaned_silently(schedule):
    with pytest.raises(ValueError):
        evaluate_schedule_quality(make_problem(), schedule, integer_export=True)


def test_empty_or_all_infeasible_results_never_produce_a_recommendation():
    assert select_schedule_quality([])["selected_indices"] == []
    assert select_schedule_quality([report([-100, 1, 1, 1], feasible=False)], policy="balanced")["selected_indices"] == []


def test_bad_reference_or_weights_cannot_silently_erase_a_varying_objective():
    reports = [report([-100, 1, 0, 0]), report([-90, 0.1, 0, 0])]
    with pytest.raises(ValueError, match="constant reference"):
        select_schedule_quality(reports, policy="balanced", normalization_bounds=[[-100, -100], [0, 1], [0, 0], [0, 0]])
    with pytest.raises(ValueError, match="weights"):
        select_schedule_quality(reports, policy="balanced", weights=[0, 0, 0, 0])
    with pytest.raises(ValueError, match="same original objective axes"):
        select_schedule_quality([reports[0], report([-100])])
