"""Today's supply stays fixed through decoding, direct moves and file exports."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest


CASE_DIR = (
    Path(__file__).resolve().parents[1]
    / "examples/cases/supply_adjustment_nested/cases/supply_adjustment_nested"
)


@pytest.fixture
def problem_type(monkeypatch):
    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        return module

    load("inner_solver", CASE_DIR / "inner_solver.py")
    module = load("supply_day_zero_problem", CASE_DIR / "problem/supply_event_shift_problem.py")
    return module.SupplyEventShiftProblem


@pytest.fixture
def problem(problem_type):
    return problem_type(
        base_supply=np.array([[71, 11, 23, 0, 47], [103, 13, 0, 31, 0]], dtype=float),
        bom_matrix=np.ones((1, 2)),
        production_case_dir=CASE_DIR,
    )


def test_today_rule_keeps_event_identity_and_day_one_zero_width(problem):
    assert [(event.material_idx, event.day) for event in problem.events] == [
        (0, 1), (0, 2), (0, 4), (1, 1), (1, 3)
    ]
    assert problem.dimension == 5
    assert list(problem.bounds.values()) == [[0, 0], [0, 1], [0, 3], [0, 0], [0, 2]]


def test_legacy_day_zero_moves_are_redecoded_without_changing_today(problem):
    candidate = np.array([1, 2, 4, 1, 3], dtype=float)
    original = problem.base_supply.copy()

    shifts = problem.decode_shifts(candidate)
    adjusted = problem.apply_shifts(shifts)

    np.testing.assert_array_equal(shifts, [0, 1, 3, 0, 2])
    np.testing.assert_array_equal(candidate, [1, 2, 4, 1, 3])
    np.testing.assert_array_equal(problem.base_supply, original)
    np.testing.assert_array_equal(adjusted[:, 0], original[:, 0])
    np.testing.assert_array_equal(adjusted.sum(axis=1), original.sum(axis=1))
    np.testing.assert_array_equal(adjusted[:, 1], [81, 44])
    assert np.min(adjusted) >= 0


@pytest.mark.parametrize(
    "shifts",
    [
        [1, 0, 0, 0, 0],       # Day 1 cannot move into today.
        [0, 2, 0, 0, 0],       # A later whole event cannot move into today.
        [0, -1, 0, 0, 0],      # No delay disguised as a negative shift.
        [0, 0.5, 0, 0, 0],     # Direct decoded operations must be integral.
        [0, np.nan, 0, 0, 0],
        [0, np.inf, 0, 0, 0],
        [0, 0],
    ],
)
def test_direct_apply_and_move_export_reject_invalid_decoded_moves(problem, shifts, tmp_path):
    original = problem.base_supply.copy()
    path = tmp_path / "invalid_moves.csv"

    with pytest.raises(ValueError):
        problem.apply_shifts(np.asarray(shifts))
    with pytest.raises(ValueError):
        problem.export_move_log(np.asarray(shifts), path)

    assert not path.exists()
    np.testing.assert_array_equal(problem.base_supply, original)


def test_supply_export_and_move_log_describe_the_same_today_safe_plan(problem, tmp_path):
    supply_path = tmp_path / "adjusted.csv"
    move_path = tmp_path / "moves.csv"
    shifts, _ = problem.export_adjusted_supply(np.array([1, 2, 4, 1, 3]), supply_path)
    problem.export_move_log(shifts, move_path)
    exported = pd.read_csv(supply_path)
    moves = pd.read_csv(move_path)
    reconstructed = problem.base_supply.copy()

    assert (moves["from_day"] >= 2).all()
    assert (moves["to_day"] >= 1).all()
    assert (moves["to_day"] < moves["from_day"]).all()
    for row in moves.itertuples(index=False):
        material_index = int(row.material) - 1
        reconstructed[material_index, int(row.from_day)] -= row.quantity
        reconstructed[material_index, int(row.to_day)] += row.quantity

    np.testing.assert_array_equal(exported["0"], problem.base_supply[:, 0])
    np.testing.assert_array_equal(exported.iloc[:, 1:].to_numpy(), reconstructed)
    np.testing.assert_array_equal(reconstructed.sum(axis=1), problem.base_supply.sum(axis=1))


def test_movement_cap_ignores_immovable_day_one_event(problem_type):
    problem = problem_type(
        base_supply=np.array([[71, 11, 23, 0, 47]], dtype=float),
        bom_matrix=np.ones((1, 1)),
        production_case_dir=CASE_DIR,
        max_moved_events=1,
    )

    shifts = problem.decode_shifts(np.array([1, 2, 4], dtype=float))

    assert shifts[0] == 0
    assert np.count_nonzero(shifts) == 1
    assert np.all((shifts == 0) | (shifts == [0, 1, 3]))
    np.testing.assert_array_equal(problem.apply_shifts(shifts)[:, 0], [71])


def test_today_only_problem_allows_empty_moves_and_exports(problem_type, tmp_path):
    problem = problem_type(
        base_supply=np.array([[71], [103]], dtype=float),
        bom_matrix=np.ones((1, 2)),
        production_case_dir=CASE_DIR,
    )
    shifts, exported = problem.export_adjusted_supply(np.empty(0), tmp_path / "today.csv")

    assert problem.dimension == 0
    assert shifts.size == 0
    np.testing.assert_array_equal(exported["0"], [71, 103])
    np.testing.assert_array_equal(problem.apply_shifts(shifts), problem.base_supply)
