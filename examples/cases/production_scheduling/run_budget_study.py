"""Supervise budget-only experiments through formal Project/Case/L0 entries."""
from contextlib import contextmanager
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import runpy
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import numpy as np
from blackbase.resources import ArtifactBinding, ArtifactPublisher
from blackbase.types import PopulationSnapshot
from examples.cases.production_scheduling import run_quality_benchmark as quality
from examples.cases.production_scheduling.report_ablation import read_observations
from examples.cases.production_scheduling.report_operator_comparison import delivered_raw

STUDY_ENV = "NSGABLACK_PRODUCTION_BUDGET_STUDY_RUN_ID"
BUDGETS = (240, 1104, 2400)


@contextmanager
def study_environment(run_id):
    old = os.environ.get(STUDY_ENV)
    os.environ[STUDY_ENV] = run_id
    try:
        yield
    finally:
        if old is None:
            os.environ.pop(STUDY_ENV, None)
        else:
            os.environ[STUDY_ENV] = old


def plan(run_id, budgets=BUDGETS, seeds=(42,43,44)):
    if not quality.re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,59}", run_id):
        raise ValueError("invalid study identifier")
    with study_environment(run_id):
        config = runpy.run_path(str(ROOT / "project_config.py"))
    stages = {s["name"]: s for s in config["STAGES"]}
    jobs = []
    for budget in budgets:
        for seed in seeds:
            for policy in (("window", "legacy") if seed == 43 else ("legacy", "window")):
                group = f"budget_{budget}_{policy}_s{seed}"
                run = f"{run_id}-{group}"
                jobs.append({"budget":budget, "seed":seed, "policy":policy, "group":group,
                    "project_run_id":run, "stage":stages[group],
                    "command":[sys.executable, "-u", str(ROOT/"run_project.py"), "--group",group,"--run-id",run],
                    "hard_timeout_seconds":stages[group]["timeout_seconds"] + 30})
    return jobs


def source_hashes():
    result = quality._input_hashes()
    for name in ("run_budget_study.py", "report_operator_comparison.py"):
        result[name] = hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
    for prefix, root in (("nsgablack",REPO), ("blackbase",REPO.parent/"blackbase/src/blackbase")):
        selected = [root/name for name in ("core","adapters","bias","plugins","units","representation","utils","project","catalog","nsgablack")] if prefix == "nsgablack" else [root]
        for directory in selected:
            for path in sorted(directory.rglob("*.py")):
                result[prefix+"/"+path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def collect(job):
    formal = quality._formal_result(job)
    if formal["evaluations"] != job["budget"] or formal["termination_reason"] != "evaluation_budget_exhausted":
        raise ValueError("Project did not consume exactly the selected search budget")
    observation = read_observations(ROOT,job["project_run_id"],job["budget"])
    manifest = json.loads((ROOT/".blackbase/runs"/job["project_run_id"]/"manifest.json").read_text())
    case = manifest["cases"][0]["result"]
    argv = case["request"]["component_overrides"]["argv"]
    if argv != job["stage"]["component_overrides"]["production_scheduling"]["argv"]:
        raise ValueError("actual Case arguments differ from the study plan")
    binding = ArtifactBinding.from_dict({"ref":case["artifact_refs"]["pareto_front"],
        "publication":case["artifact_publications"]["pareto_front"]})
    reader = ArtifactPublisher.from_resource_context(case["request"]["resource_context"],
        project_run_id=case["identity"]["project_run_id"],case_run_id=case["identity"]["case_run_id"])
    snapshot = PopulationSnapshot.from_dict(json.loads(reader.read_verified(binding)))
    final_raw = delivered_raw(snapshot,observation)
    return observation, final_raw, {"formal":formal,"metadata":observation["metadata"],
        "observations_binding":observation["binding"],"delivered_binding":binding.as_dict()}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id",required=True)
    parser.add_argument("--budgets",nargs="+",type=int,choices=BUDGETS,default=list(BUDGETS))
    parser.add_argument("--seeds",nargs="+",type=int,choices=(42,43,44),default=[42,43,44])
    parser.add_argument("--plan",action="store_true")
    args=parser.parse_args(argv)
    jobs=plan(args.run_id,tuple(dict.fromkeys(args.budgets)),tuple(dict.fromkeys(args.seeds)))
    if args.plan:
        print(json.dumps(jobs,ensure_ascii=False,indent=2));return 0
    folder=ROOT/"results/budget_study"/args.run_id
    folder.mkdir(parents=True,exist_ok=False)
    state={"schema":"production.budget_study/v1","run_id":args.run_id,"jobs":jobs,"runs":[],
        "inputs":source_hashes(),"environment":{"python":platform.python_version(),"numpy":np.__version__,
        "executable":sys.executable,"source_root":str(REPO)},
        "budget_scope":"search evaluations; existing post-search exports/audits excluded"}
    quality._write(folder/"run.json",state)
    environment=dict(os.environ,**{STUDY_ENV:args.run_id,"PYTHONIOENCODING":"utf-8","CUDA_VISIBLE_DEVICES":"",
        "OMP_NUM_THREADS":"1","OPENBLAS_NUM_THREADS":"1","MKL_NUM_THREADS":"1"})
    environment.pop(quality.RESUME_ENV,None)
    for index,job in enumerate(jobs,1):
        if source_hashes()!=state["inputs"]:
            raise ValueError("code/model/data changed during study")
        subfolder=folder/job["group"];subfolder.mkdir()
        print(f"[{index}/{len(jobs)}] {job['group']}",flush=True)
        record=quality.supervise_project(job["command"],subfolder/"project.log",environment,timeout_seconds=job["hard_timeout_seconds"])
        row={"group":job["group"],"policy":job["policy"],"seed":job["seed"],"budget":job["budget"],**record,"status":"failed"}
        state["runs"].append(row);quality._write(folder/"run.json",state)
        if record["exit_code"]!=0 or record["failure"] is not None:
            raise RuntimeError(f"Project failed; preserved evidence: {record}")
        observation,final_raw,receipt=collect(job)
        if source_hashes()!=state["inputs"]:
            raise ValueError("source changed during Project run")
        arrays={**observation["arrays"],"delivered_raw_objectives":final_raw}
        evidence=subfolder/"verified_observations.npz"
        with evidence.open("xb") as target:np.savez_compressed(target,**arrays)
        row.update(status="succeeded",**receipt,verified_arrays_sha256=hashlib.sha256(evidence.read_bytes()).hexdigest())
        quality._write(folder/"run.json",state)
        print(f"  succeeded budget={job['budget']} seconds={record['elapsed_seconds']:.1f}",flush=True)
    state["status"]="succeeded";quality._write(folder/"run.json",state)
    print(json.dumps({"status":"succeeded","folder":str(folder),"runs":len(jobs)},ensure_ascii=False),flush=True)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
