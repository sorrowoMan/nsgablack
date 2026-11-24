"""Unit tests for the pymoo baseline comparison."""
import numpy as np
import pytest

pytest.importorskip("pymoo")

from pymoo.problems import get_problem

from benchmarks.pymoo_baseline import pymoo_run, run
from benchmarks.quality_problems import DTLZProblem, ZDTProblem


@pytest.mark.parametrize("variant", [1, 2, 3, 6])
def test_zdt_matches_pymoo(variant):
    rng = np.random.default_rng(0)
    mine = ZDTProblem(variant, n_var=30)
    theirs = get_problem(f"zdt{variant}", n_var=30)
    for _ in range(5):
        x = rng.uniform(0.0, 1.0, 30)
        np.testing.assert_allclose(mine.evaluate(x),
                                   theirs.evaluate(x, return_values_of=["F"]), atol=1e-9)


@pytest.mark.parametrize("n_obj,n_var", [(2, 11), (3, 12)])
def test_dtlz2_matches_pymoo(n_obj, n_var):
    rng = np.random.default_rng(1)
    mine = DTLZProblem(2, n_obj=n_obj, n_var=n_var)
    theirs = get_problem("dtlz2", n_var=n_var, n_obj=n_obj)
    for _ in range(5):
        x = rng.uniform(0.0, 1.0, n_var)
        np.testing.assert_allclose(mine.evaluate(x),
                                   theirs.evaluate(x, return_values_of=["F"]), atol=1e-9)


def test_pymoo_run_smoke():
    F, n_eval = pymoo_run("nsga2", "zdt1", 20, 8, seed=11)
    assert F.shape[1] == 2
    assert n_eval == 20 * 8
    assert np.isfinite(F).all()


def test_run_compares_both_sides():
    report = run({"problems": ["zdt1"], "algorithms": ["nsga2"], "seeds": [11],
                  "population_size": 20, "steps": 8})
    row = report["results"][0]
    assert row["algorithm"] == "nsga2"
    assert np.isfinite(row["framework_igd"]["median"])
    assert np.isfinite(row["pymoo_igd"]["median"])
    assert row["per_seed"][0]["evaluations"] == 20 * 8


def test_rejects_unsupported():
    with pytest.raises(ValueError, match="supports"):
        run({"problems": ["zdt1"], "algorithms": ["spea2"], "seeds": [11],
             "population_size": 20, "steps": 8})
    with pytest.raises(ValueError, match="no clean pymoo baseline problem"):
        run({"problems": ["dtlz1_3"], "algorithms": ["nsga2"], "seeds": [11],
             "population_size": 20, "steps": 8})
