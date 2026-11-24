from examples.cases.production_scheduling.run_budget_study import plan
from examples.cases.production_scheduling.report_budget_study import summarize, load_verified
import hashlib
import json
import numpy as np
import pytest


def test_budget_ladder_changes_only_budget_policy_and_output_not_search_plan():
    jobs=plan("test-budget-only")
    assert len(jobs)==18
    for seed in (42,43,44):
        normalized=[]
        for job in [j for j in jobs if j["seed"]==seed]:
            argv=job["stage"]["component_overrides"]["production_scheduling"]["argv"]
            assert argv[argv.index("--max-evaluations")+1]==str(job["budget"])
            assert argv[argv.index("--quality-cycles")+1]=="64"
            assert argv[argv.index("--generations")+1]=="1024"
            assert job["stage"]["resource_requests"]["production_scheduling"]=={"threads":1,"gpus":0,"backend":"local"}
            keep=[];i=0
            while i<len(argv):
                if argv[i] in {"--max-evaluations","--mutation-policy","--export"}:i+=2
                else:keep.append(argv[i]);i+=1
            normalized.append(keep)
        assert all(a==normalized[0] for a in normalized)


def samples():
    result=[]
    for seed in (42,43,44):
        for policy in ("legacy","window"):
            for budget in (240,1104,2400):
                f=np.tile([-10.,1.,1.,1.],(budget,1))
                for level,limit in enumerate((240,1104,2400),1):
                    if limit<=budget:f[limit-1:]=[-10.-level,1.-level*.1,1.-level*.1,1.-level*.1]
                a={"raw_objectives":f,"raw_violations":np.zeros(budget),
                   "numeric_hashes":np.arange(budget).astype(str),"delivered_raw_objectives":f[-1:]}
                r={"group":f"{seed}-{policy}-{budget}","seed":seed,"policy":policy,"budget":budget,
                   "formal":{"case_elapsed_seconds":1.},"verified_arrays_sha256":"test"}
                result.append({"record":r,"arrays":a})
    return result


def test_budget_metrics_use_one_reference_and_preserve_true_prefixes():
    r=summarize(samples())
    assert all(c["same_numeric_and_raw_prefix"] for c in r["prefix_checks"])
    for policy in ("legacy","window"):
        means=[m for m in r["means"] if m["policy"]==policy]
        assert means[0]["delivered_hv"]<means[1]["delivered_hv"]<means[2]["delivered_hv"]
        assert means[-1]["delivered_igd"]==0


def test_budget_report_rejects_changed_initial_feedback():
    data=samples();data[-1]["arrays"]["raw_objectives"][0,0]=-11
    with pytest.raises(ValueError,match="initial"):
        summarize(data)


def test_downloaded_evidence_must_match_cloud_receipt(tmp_path):
    e=samples()[0];r=e["record"];a=e["arrays"]
    a.update(batch_counts=np.array([240]),cumulative_evaluations=np.array([240]))
    r.update(status="succeeded",metadata={"initial_count":48},
             formal={"evaluations":240,"resource_binding_current":True,"threads":1,"gpus":0})
    folder=tmp_path/r["group"];folder.mkdir();p=folder/"verified_observations.npz"
    np.savez_compressed(p,**a);r["verified_arrays_sha256"]=hashlib.sha256(p.read_bytes()).hexdigest()
    (tmp_path/"run.json").write_text(json.dumps({"status":"succeeded","jobs":[{"group":r["group"]}],"runs":[r]}))
    assert len(load_verified(tmp_path)[1])==1
    a["raw_objectives"][0,0]=-500
    np.savez_compressed(p,**a)
    with pytest.raises(ValueError,match="cloud verification receipt"):
        load_verified(tmp_path)
