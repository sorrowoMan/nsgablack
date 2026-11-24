"""Unit tests for the self-contained fusion benchmark (no pymoo)."""
import numpy as np
import pytest

from benchmarks.fusion_suite import FUSION_PAIRS, run, run_fusion


def test_run_fusion_smoke_budgets_align():
    result = run_fusion("nsga2", "moead", "zdt1", seed=11,
                        population_size=20, total_steps=8)
    budget = 20 * 8
    assert result["global_alone"]["evaluations"] == budget
    assert result["refine_alone"]["evaluations"] == budget
    assert result["hybrid"]["evaluations"] == budget
    assert sum(result["hybrid"]["phase_evaluations"]) == budget
    for key in ("global_alone", "refine_alone", "hybrid"):
        assert np.isfinite(result[key]["igd"])
        assert np.isfinite(result[key]["hv"])


def test_run_fusion_warm_start_same_algorithm_is_comparable():
    # A nsga2->nsga2 control (continuation) should not collapse quality.
    result = run_fusion("nsga2", "nsga2", "zdt1", seed=11,
                        population_size=20, total_steps=10)
    assert np.isfinite(result["hybrid"]["igd"])
    assert result["hybrid"]["igd"] < 2.0


def test_run_fusion_rejects_unknown_pair_and_problem():
    with pytest.raises(ValueError, match="unknown fusion algorithm pair"):
        run_fusion("nope", "moead", "zdt1", 11, 20, 8)
    with pytest.raises(ValueError, match="unknown problem"):
        run_fusion("nsga2", "moead", "nope", 11, 20, 8)


def test_run_aggregates_and_reports_all_three():
    report = run({"pairs": [("nsga2", "moead")], "problems": ["zdt1"],
                  "seeds": [11], "population_size": 20, "total_steps": 8})
    assert report["results"][0]["pair"] == "nsga2->moead"
    assert set(report["results"][0]) >= {"global_igd", "refine_igd", "hybrid_igd",
                                          "global_hv", "hybrid_hv"}


def test_default_fusion_pairs_are_valid():
    for global_alg, refine_alg in FUSION_PAIRS:
        assert global_alg in {"nsga2", "spea2", "moead"}
        assert refine_alg in {"nsga2", "spea2", "moead"}
