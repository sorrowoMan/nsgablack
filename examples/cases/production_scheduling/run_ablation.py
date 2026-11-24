"""Supervise declared Project ablations; never implement an algorithm loop here."""
from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from examples.cases.production_scheduling import run_quality_benchmark as quality
from examples.cases.production_scheduling.report_ablation import read_observations, summarize

SESSION_ENV = "NSGABLACK_PRODUCTION_ABLATION_RUN_ID"
ARMS = ("constructive", "moead", "directional")
BUDGETS = {"pilot": 240, "formal": 1104}


@contextmanager
def session(run_id):
    old = os.environ.get(SESSION_ENV)
    os.environ[SESSION_ENV] = run_id
    try:
        yield
    finally:
        if old is None:
            os.environ.pop(SESSION_ENV, None)
        else:
            os.environ[SESSION_ENV] = old


def plan(run_id, profile, seeds):
    with session(run_id):
        cfg = runpy.run_path(str(ROOT / "project_config.py"))
    stages = {s["name"]: s for s in cfg["STAGES"]}
    return [{"group": (name := f"ablation_{profile}_{arm}_s{seed}"),
             "project_run_id": f"{run_id}-{name}", "stage": stages[name],
             "command": [sys.executable, "-u", str(ROOT / "run_project.py"),
                         "--group", name, "--run-id", f"{run_id}-{name}"],
             "hard_timeout_seconds": stages[name]["timeout_seconds"] + 30}
            for seed in dict.fromkeys(seeds) for arm in ARMS]


def source_hashes():
    result = quality._input_hashes()
    for name in ("run_ablation.py", "report_ablation.py"):
        result[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    return result


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=BUDGETS, default="pilot")
    parser.add_argument("--seeds", nargs="+", type=int, choices=(42, 43, 44), default=[42])
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--plan", action="store_true")
    args = parser.parse_args(argv)
    run_id = args.run_id or f"ablation-{datetime.now():%Y%m%d-%H%M%S}"
    if not quality.re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", run_id):
        parser.error("run-id must be a single identifier")
    jobs = plan(run_id, args.profile, args.seeds)
    if args.plan:
        print(json.dumps({"run_id": run_id, "budget_per_arm": BUDGETS[args.profile], "jobs": jobs}, ensure_ascii=False, indent=2))
        return 0
    import pymoo
    import numpy as np
    import platform
    if pymoo.__version__ != "0.6.2":
        raise ValueError("ablation metric protocol requires pymoo==0.6.2")
    folder = ROOT / "results/ablation" / run_id
    folder.mkdir(parents=True, exist_ok=False)
    state = {"schema": "production.ablation_run/v1", "run_id": run_id,
             "profile": args.profile, "inputs": source_hashes(), "plan": jobs, "runs": [],
             "environment": {"python": platform.python_version(), "executable": sys.executable,
                             "numpy": np.__version__, "pymoo": pymoo.__version__}}
    quality._write(folder / "run.json", state)
    environment = dict(os.environ, **{SESSION_ENV: run_id, "PYTHONIOENCODING": "utf-8",
        "CUDA_VISIBLE_DEVICES": "", "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
    environment.pop(quality.RESUME_ENV, None)
    observed = []
    for index, job in enumerate(jobs, 1):
        if source_hashes() != state["inputs"]:
            raise ValueError("model/code/data changed during the experiment")
        subfolder = folder / job["group"]
        subfolder.mkdir()
        print(f"[{index}/{len(jobs)}] {job['group']} budget={BUDGETS[args.profile]}", flush=True)
        record = quality.supervise_project(job["command"], subfolder / "project.log", environment,
                                           timeout_seconds=job["hard_timeout_seconds"])
        row = {"group": job["group"], "project_run_id": job["project_run_id"], **record, "status": "failed"}
        if record["exit_code"] == 0 and record["failure"] is None:
            try:
                observation = read_observations(ROOT, job["project_run_id"], BUDGETS[args.profile])
                observed.append(observation)
                row["status"] = "succeeded"
                row["observation_metadata"] = observation["metadata"]
            except (ValueError, KeyError, OSError) as exc:
                row["failure"] = str(exc)
        state["runs"].append(row)
        quality._write(folder / "run.json", state)
        print(f"  {row['status']} elapsed={row['elapsed_seconds']:.2f}s", flush=True)
        if row["status"] != "succeeded":
            return 1
    if source_hashes() != state["inputs"]:
        raise ValueError("model/code/data changed during the experiment")
    comparison = summarize(observed)
    comparison["run_id"] = run_id
    comparison["inputs"] = state["inputs"]
    quality._write(folder / "comparison.json", comparison)
    print(json.dumps({"run_id": run_id, "status": "succeeded", "comparison": str(folder / "comparison.json"),
                      "results": [{k:v for k,v in r.items() if k != "artifact"} for r in comparison["results"]]}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
