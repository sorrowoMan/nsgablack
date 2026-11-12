"""Unit tests for the self-contained quality benchmark (no pymoo)."""
import numpy as np
import pytest

from benchmarks.quality_metrics import hypervolume, igd, pareto_filter
from benchmarks.quality_problems import (
    DTLZ2Problem,
    DTLZProblem,
    ZDTProblem,
    dtlz1_reference_front,
    dtlz2_reference_front,
    zdt_reference_front,
)
from benchmarks.quality_suite import SUITE, run, run_one


# --- Problems ---------------------------------------------------------------

@pytest.mark.parametrize("variant,x,expected", [
    (1, [0.0, 0.0, 0.0], [0.0, 1.0]),
    (1, [1.0, 0.0, 0.0], [1.0, 0.0]),
    (2, [1.0, 0.0, 0.0], [1.0, 0.0]),
    (6, [0.0, 0.0, 0.0], [1.0, 0.0]),
])
def test_zdt_problem_known_values(variant, x, expected):
    problem = ZDTProblem(variant, n_var=len(x))
    result = problem.evaluate(x)
    np.testing.assert_allclose(result, expected, atol=1e-9)


def test_dtlz2_problem_lies_on_unit_sphere_at_g_zero():
    problem = DTLZ2Problem(n_obj=3, n_var=12)
    x = np.full(12, 0.5)
    f = problem.evaluate(x)
    np.testing.assert_allclose(np.sum(f ** 2), 1.0, atol=1e-9)


def test_dtlz2_problem_objective_count():
    assert DTLZ2Problem(n_obj=2).evaluate(np.zeros(11)).shape == (2,)
    assert DTLZ2Problem(n_obj=3).evaluate(np.zeros(12)).shape == (3,)


# --- Reference fronts -------------------------------------------------------

def test_zdt_reference_front_endpoints():
    front = zdt_reference_front(1, 100)
    assert front.shape == (100, 2)
    np.testing.assert_allclose(front[0], [0.0, 1.0], atol=1e-6)
    np.testing.assert_allclose(front[-1], [1.0, 0.0], atol=1e-6)


@pytest.mark.parametrize("n_obj", [2, 3])
def test_dtlz2_reference_front_lies_on_unit_sphere(n_obj):
    front = dtlz2_reference_front(n_obj, 300)
    assert front.shape[1] == n_obj
    np.testing.assert_allclose(np.sum(front ** 2, axis=1), 1.0, atol=1e-9)


def test_suite_front_dimensions_match():
    for name, spec in SUITE.items():
        assert spec["front"]().shape[1] == spec["n_obj"]
        assert len(spec["ref"]) == spec["n_obj"]


# --- Hypervolume (hand-computed) --------------------------------------------

@pytest.mark.parametrize("points,ref,expected", [
    ([[0.5, 0.5]], [1.0, 1.0], 0.25),
    ([[0.2, 0.8], [0.8, 0.2]], [1.0, 1.0], 0.28),
    ([[0.5, 0.5, 0.5]], [1.0, 1.0, 1.0], 0.125),
    ([[2.0, 2.0]], [1.0, 1.0], 0.0),
])
def test_hypervolume_known_values(points, ref, expected):
    assert hypervolume(points, ref) == pytest.approx(expected, abs=1e-12)


def test_hypervolume_empty_and_ignores_dominated():
    assert hypervolume([], [1.0, 1.0]) == 0.0
    # a dominated point adds no volume
    assert hypervolume([[0.5, 0.5], [0.6, 0.6]], [1.0, 1.0]) == pytest.approx(0.25, abs=1e-12)


def test_igd_zero_when_front_matches_reference():
    ref = zdt_reference_front(1, 50)
    assert igd(ref, ref) == pytest.approx(0.0, abs=1e-12)


def test_pareto_filter_removes_dominated():
    points = np.array([[0.0, 0.0], [1.0, 1.0], [0.5, 0.5]])
    front = pareto_filter(points)
    assert len(front) == 1
    np.testing.assert_allclose(front[0], [0.0, 0.0])


# --- End-to-end smoke -------------------------------------------------------

def test_run_one_smoke():
    result = run_one("nsga2", "zdt1", seed=11, population_size=20, steps=10)
    assert result["evaluations"] == 20 * 10
    assert np.isfinite(result["igd"])
    assert np.isfinite(result["hv"])
    assert result["front_size"] >= 1


def test_run_rejects_unknown_problem_and_algorithm():
    with pytest.raises(ValueError, match="unknown problems"):
        run({"problems": ["nope"], "algorithms": ["nsga2"], "seeds": [11],
             "population_size": 20, "steps": 10})
    with pytest.raises(ValueError, match="unknown algorithms"):
        run({"problems": ["zdt1"], "algorithms": ["nope"], "seeds": [11],
             "population_size": 20, "steps": 10})


# --- DTLZ1 / DTLZ4 ----------------------------------------------------------

def test_dtlz1_problem_front_is_simplex_at_g_zero():
    problem = DTLZProblem(1, n_obj=3, n_var=12)
    f = problem.evaluate(np.full(12, 0.5))
    np.testing.assert_allclose(np.sum(f), 0.5, atol=1e-9)


def test_dtlz1_reference_front_is_simplex():
    front = dtlz1_reference_front(3, 300)
    assert front.shape[1] == 3
    np.testing.assert_allclose(np.sum(front, axis=1), 0.5, atol=1e-9)


def test_dtlz4_problem_lies_on_unit_sphere_at_g_zero():
    problem = DTLZProblem(4, n_obj=3, n_var=12)
    f = problem.evaluate(np.full(12, 0.5))
    np.testing.assert_allclose(np.sum(f ** 2), 1.0, atol=1e-9)


# --- NSGA3 / compatibility --------------------------------------------------

def test_run_one_nsga3_smoke():
    result = run_one("nsga3", "dtlz2_3", seed=11, population_size=15, steps=6,
                     nsga3_divisions=4)
    assert result["evaluations"] == 15 * 6
    assert np.isfinite(result["igd"])
    assert np.isfinite(result["hv"])


def test_nsga3_skipped_on_two_objective_problems():
    report = run({"problems": ["zdt1", "dtlz2_3"], "algorithms": ["nsga3"],
                  "seeds": [11], "population_size": 20, "steps": 6,
                  "nsga3_divisions": 4})
    assert [r["problem"] for r in report["results"]] == ["dtlz2_3"]
    assert report["config"]["skipped_combinations"] == ["nsga3xzdt1"]
