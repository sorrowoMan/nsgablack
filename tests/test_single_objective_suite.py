"""Unit tests for the self-contained single-objective CMA-ES benchmark."""
import numpy as np
import pytest

from benchmarks.single_objective_suite import (
    PROBLEMS,
    _ackley,
    _rastrigin,
    _rosenbrock,
    _sphere,
    run,
    run_cma,
)


def test_objective_functions_known_values():
    assert _sphere(np.array([3.0, 4.0])) == pytest.approx(25.0)
    assert _rosenbrock(np.array([1.0, 1.0])) == pytest.approx(0.0)
    assert _rastrigin(np.zeros(5)) == pytest.approx(0.0)
    assert _ackley(np.zeros(5)) == pytest.approx(0.0, abs=1e-12)


def test_run_cma_smoke_converges_on_sphere():
    result = run_cma("sphere", seed=11, n_var=5, steps=30)
    assert result["evaluations"] > 0
    assert np.isfinite(result["best"])
    # Sphere optimum is 0; a few CMA generations from mean=3 should improve a lot.
    assert result["best"] < 45.0


def test_run_cma_rejects_unknown_problem():
    with pytest.raises(ValueError, match="unknown single-objective problem"):
        run_cma("nope", seed=11, n_var=5, steps=10)


def test_run_aggregates():
    report = run({"problems": ["sphere"], "seeds": [11, 29], "n_var": 5, "steps": 20,
                  "sigma": 0.35, "cma_lambda": None})
    assert report["results"][0]["problem"] == "sphere"
    assert set(report["results"][0]["best"]) >= {"median", "q1", "q3"}


def test_all_problems_have_zero_optimum():
    for name in PROBLEMS:
        assert name in {"sphere", "rosenbrock", "rastrigin", "ackley"}
