"""The paired study cannot improve its score by changing inputs or budgets."""
import copy

import numpy as np
import pytest

from examples.cases.production_scheduling.run_operator_comparison import summarize
from examples.cases.production_scheduling.report_operator_comparison import delivered_raw, numeric_digest
from blackbase.types import PopulationSnapshot, UnknownState


def observations():
    rows = []
    for seed in (42, 43, 44):
        for policy in ("legacy", "window"):
            f = np.tile([-100., 1., 1., 1.], (240, 1))
            if policy == "window":
                f[48:] = [-110., 0.5, 0.5, 0.5]
            rows.append({"policy": policy, "metadata": {"seed": seed, "initial_count": 48},
                "arrays": {"raw_objectives": f, "raw_violations": np.zeros(240),
                           "numeric_hashes": np.arange(240).astype(str)},
                "elapsed_seconds": 1., "identity": {}, "binding": {},
                "termination_reason": "evaluation_limit"})
    return rows


def test_comparison_uses_shared_axes_and_rewards_real_raw_dominance():
    report = summarize(observations())
    assert report["initial_candidates_and_raw_feedback_equal"]
    for seed in (42, 43, 44):
        pair = {r["policy"]: r for r in report["results"] if r["seed"] == seed}
        assert pair["legacy"]["initial_hv"] == pair["window"]["initial_hv"]
        assert pair["window"]["observed_hv"] > pair["legacy"]["observed_hv"]
        assert pair["window"]["empirical_igd"] < pair["legacy"]["empirical_igd"]


@pytest.mark.parametrize("field", ["raw_objectives", "raw_violations", "numeric_hashes"])
def test_comparison_refuses_different_initial_conditions(field):
    rows = observations()
    rows[1]["arrays"][field][0] = 7
    with pytest.raises(ValueError, match="initial candidate/feedback mismatch"):
        summarize(rows)


def test_comparison_requires_every_seed_and_exact_equal_budget():
    rows = observations()
    with pytest.raises(ValueError, match="both policies"):
        summarize(rows[:-1])
    rows = copy.deepcopy(rows)
    rows[1]["arrays"]["raw_violations"] = np.zeros(239)
    with pytest.raises(ValueError, match="budget"):
        summarize(rows)


def test_delivered_report_uses_raw_evidence_and_refuses_numeric_identity_guessing():
    candidate = UnknownState(values=[10., 20.])
    snapshot = PopulationSnapshot([candidate], [[-999., 0., 0., 0.]], candidate_tokens=["token-a"])
    raw = np.array([[-30., 1., 2., 3.]])
    evidence = {"arrays": {"candidate_tokens": np.array(["token-a"]), "raw_objectives": raw,
        "raw_violations": np.zeros(1), "numeric_hashes": np.array([numeric_digest(candidate.as_array())])}}
    np.testing.assert_array_equal(delivered_raw(snapshot, evidence), raw)
    evidence["arrays"]["candidate_tokens"][0] = "token-b"
    with pytest.raises(ValueError, match="identity"):
        delivered_raw(snapshot, evidence)


def test_delivered_report_rejects_changed_candidate_under_same_token():
    snapshot = PopulationSnapshot([UnknownState(values=[11., 20.])], [[-31., 0., 0., 0.]],
                                  candidate_tokens=["token-a"])
    evidence = {"arrays": {"candidate_tokens": np.array(["token-a"]),
        "raw_objectives": np.array([[-30., 1., 2., 3.]]), "raw_violations": np.zeros(1),
        "numeric_hashes": np.array([numeric_digest([10., 20.])])}}
    with pytest.raises(ValueError, match="numeric version"):
        delivered_raw(snapshot, evidence)
