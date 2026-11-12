"""Ablation fairness and raw evidence, independent of search quality."""
import copy
import importlib
import io
from types import SimpleNamespace

import numpy as np
import pytest

from blackbase import CandidateBatch, Feedback
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch

runner = importlib.import_module("examples.cases.production_scheduling.run_ablation")
metrics = importlib.import_module("examples.cases.production_scheduling.report_ablation")
audit_module = importlib.import_module("examples.cases.production_scheduling.cases.production_scheduling.plugins.ablation")


def options(argv):
    return {k: argv[i+1] for i,k in enumerate(argv[:-1]) if k.startswith("--") and not argv[i+1].startswith("--")}


@pytest.mark.parametrize("profile,budget", [("pilot", 240), ("formal", 1104)])
def test_three_arms_use_one_initial_size_budget_problem_and_single_cpu(profile, budget):
    jobs = runner.plan("test", profile, [42])
    assert len(jobs) == 3
    for job in jobs:
        stage = job["stage"]
        argv = stage["component_overrides"]["production_scheduling"]["argv"]
        opts = options(argv)
        assert [opts[k] for k in ["--machines","--materials","--days"]] == ["22","157","31"]
        assert opts["--moead-pop-size"] == "48" and opts["--max-evaluations"] == str(budget)
        assert "--ablation-audit" in argv and "--checkpoint-dir" not in argv
        assert stage["resource_requests"]["production_scheduling"] == {"threads":1,"gpus":0,"backend":"local"}


def rows():
    initial = np.tile([-10., .5, .5, .5], (48,1))
    out=[]
    for arm,last in zip(runner.ARMS,[[-11.,.5,.5,.5],[-12.,.4,.4,.4],[-13.,.3,.3,.3]]):
        out.append({"metadata":{"seed":42,"arm":arm,"initial_count":48,"initial_values_sha256":"same",
                                "observer_seconds":.01,"packing_seconds":.01},
            "arrays":{"raw_objectives":np.vstack([initial,last]),"raw_violations":np.zeros(49),
                      "numeric_hashes":np.asarray([str(i) for i in range(49)])},
            "elapsed_seconds":1.,"termination_reason":"evaluation_budget_exhausted","binding":{}})
    return out


def test_metrics_use_one_shared_scale_and_a_disclosed_empirical_reference():
    pytest.importorskip("pymoo")
    summary=metrics.summarize(rows())
    assert "not a true" in summary["reference_scope"]
    results=summary["results"]
    assert len({r["initial_hv"] for r in results})==1
    assert results[-1]["observed_hv"] > results[0]["observed_hv"]
    assert results[-1]["empirical_igd"] == 0


@pytest.mark.parametrize("change",["values_hash","raw_feedback"])
def test_mismatched_initialization_is_rejected_instead_of_called_fair(change):
    pytest.importorskip("pymoo")
    data=rows()
    if change=="values_hash": data[1]["metadata"]["initial_values_sha256"]="different"
    else: data[1]["arrays"]["raw_objectives"][0,0]-=1
    with pytest.raises(ValueError,match="initial"):
        metrics.summarize(data)


def test_observer_records_raw_feedback_without_evaluating_or_projecting_again():
    f=np.asarray([[-10.,.5,.5,.5],[-12.,.4,.4,.4]])
    batch=CandidateBatch((np.zeros(2),np.ones(2)),np.asarray([[0.,0.],[1.,1.]]),("a","b"))
    items=tuple(Feedback(objectives=row-3,info={"raw_evaluation":{"objectives":row.tolist(),"constraint_violation":0.}}) for row in f)
    fb=OptimizationFeedbackBatch.from_feedback(items,violations=np.zeros(2))
    event=SimpleNamespace(event_id="one",candidate_payload=batch.as_dict(),feedback_payload=fb.as_dict(),evaluation_count=2)
    solver=SimpleNamespace(get_last_evaluation_event=lambda:event,evaluation_count=2)
    observer=audit_module.ProductionAblationAudit(arm="test",seed=42)
    observer.attach(solver)
    observer.on_generation_committed(0,{})
    observer.on_solver_finish({})
    with np.load(io.BytesIO(observer._encoded),allow_pickle=False) as data:
        np.testing.assert_array_equal(data["raw_objectives"],f)
        assert data["candidate_tokens"].tolist()==["a","b"]
    with pytest.raises(ValueError,match="distinct"):
        observer.on_generation_committed(1,{})


@pytest.mark.parametrize("fault", ["missing", "duplicate", "budget", "violations", "infeasible"])
def test_incomplete_or_incomparable_experiments_are_rejected(fault):
    pytest.importorskip("pymoo")
    data = rows()
    if fault == "missing":
        data.pop()
    elif fault == "duplicate":
        data[1]["metadata"]["arm"] = "constructive"
    elif fault == "budget":
        data[1]["arrays"]["raw_violations"] = np.zeros(48)
    elif fault == "violations":
        data[1]["arrays"]["raw_violations"][0] = 1.
    else:
        for row in data:
            row["arrays"]["raw_violations"][:] = 1.
    with pytest.raises(ValueError):
        metrics.summarize(data)
