"""Paired candidate-operator study through the existing Project/L0 runner."""
from contextlib import contextmanager
import ast
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import numpy as np
from examples.cases.production_scheduling import run_ablation as ablation
from examples.cases.production_scheduling import run_quality_benchmark as quality
from examples.cases.production_scheduling.report_ablation import read_observations, front

POLICY_ENV = "NSGABLACK_PRODUCTION_MUTATION_POLICY"


@contextmanager
def policy_environment(policy):
    old = os.environ.get(POLICY_ENV)
    os.environ[POLICY_ENV] = policy
    try:
        yield
    finally:
        if old is None:
            os.environ.pop(POLICY_ENV, None)
        else:
            os.environ[POLICY_ENV] = old


def source_hashes():
    hashes = ablation.source_hashes()
    hashes[Path(__file__).name] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    # Capture actual shared source closure too, to reject concurrent changes.
    for root in (REPO / "core", REPO / "adapters", REPO / "representation",
                 REPO / "units", REPO / "project", REPO.parent / "blackbase/src/blackbase"):
        for path in sorted(root.rglob("*.py")):
            hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def assert_protected(baseline):
    for relative, digest in baseline["protected_model_data"].items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != digest:
            raise ValueError(f"protected Problem/data changed: {relative}")
    path = ROOT / "cases/production_scheduling/pipeline/neighborhood_search.py"
    source = path.read_text(encoding="utf-8-sig")
    classes = {n.name: hashlib.sha256(ast.get_source_segment(source, n).encode()).hexdigest()
               for n in ast.parse(source).body if isinstance(n, ast.ClassDef)}
    for name, digest in baseline["unchanged_original_classes"].items():
        if classes[name] != digest:
            raise ValueError(f"original operator class changed: {name}")


def summarize(rows):
    from pymoo.indicators.hv import HV
    from pymoo.indicators.igd import IGD
    if len(rows) != 6:
        raise ValueError("requires both policies for all three seeds")
    for seed in (42, 43, 44):
        pair = [r for r in rows if r["metadata"]["seed"] == seed]
        if len(pair) != 2 or {r["policy"] for r in pair} != {"legacy", "window"}:
            raise ValueError("incomplete paired comparison")
        for row in pair:
            if len(row["arrays"]["raw_violations"]) != 240 or row["metadata"]["initial_count"] != 48:
                raise ValueError("budget or initialization differs")
        for key in ("raw_objectives", "raw_violations", "numeric_hashes"):
            if not np.array_equal(pair[0]["arrays"][key][:48], pair[1]["arrays"][key][:48]):
                raise ValueError(f"initial candidate/feedback mismatch: {seed}/{key}")
    feasible = [r["arrays"]["raw_objectives"][r["arrays"]["raw_violations"] <= 1e-9] for r in rows]
    union = np.vstack(feasible)
    low, high = union.min(axis=0), union.max(axis=0)
    scale = np.where(high > low, high - low, 1.)
    reference = front(np.unique((union - low) / scale, axis=0))
    hv, igd = HV(ref_point=np.full(4, 1.1)), IGD(reference)
    result = []
    for row, good in zip(rows, feasible):
        a = row["arrays"]
        initial = a["raw_objectives"][:48][a["raw_violations"][:48] <= 1e-9]
        observed = front((good - low) / scale)
        best = good[np.argmin(good[:, 0])]
        result.append({"policy": row["policy"], "seed": row["metadata"]["seed"],
            "evaluations": len(a["raw_violations"]), "initial_best_output": float(-initial[:, 0].min()),
            "best_output": float(-best[0]), "best_output_raw_objectives": best.tolist(),
            "hard_feasible_fraction": float(np.mean(a["raw_violations"] <= 1e-9)),
            "observed_hv": float(hv.do(observed)), "initial_hv": float(hv.do(front((initial-low)/scale))),
            "empirical_igd": float(igd.do(observed)),
            "unique_numeric_candidates": len(set(a["numeric_hashes"].tolist())),
            "case_elapsed_seconds": row["elapsed_seconds"], "identity": row["identity"],
            "termination_reason": row["termination_reason"], "artifact": row["binding"]})
    return {"schema": "production.operator_comparison/v1", "results": result,
        "initial_candidates_and_raw_feedback_equal": True, "normalization_low": low.tolist(),
        "normalization_high": high.tolist(), "hv_reference_point": [1.1]*4,
        "empirical_reference_front": reference.tolist(),
        "measurement": "all evaluated raw feasible vectors in committed batches; opportunity front, not final population",
        "limitations": "three seeds, 240 evaluations; pooled empirical reference, not true optimum; no dominance or general superiority assumed"}


def main(argv=None):
    import argparse
    import platform
    import pymoo
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    folder = args.run_dir.resolve()
    baseline = json.loads((folder / "baseline.json").read_text(encoding="utf-8"))
    assert_protected(baseline)
    if pymoo.__version__ != "0.6.2":
        raise ValueError("metric protocol requires pymoo==0.6.2")
    if (folder / "run.json").exists():
        raise FileExistsError("study already started; preserve existing evidence and use a new study")
    jobs = []
    # A caller's old retry experiment must not change this study's policy.
    os.environ["NSGABLACK_PRODUCTION_MUTATION_ATTEMPTS"] = "1"
    for seed in (42, 43, 44):
        for policy in (("legacy", "window") if seed != 43 else ("window", "legacy")):
            session = f"{baseline['run_id']}-{policy}"
            with policy_environment(policy):
                job = next(j for j in ablation.plan(session, "pilot", [seed]) if "_directional_" in j["group"])
            jobs.append({**job, "policy": policy, "seed": seed, "session": session})
    state = {"run_id": baseline["run_id"], "inputs": source_hashes(), "jobs": jobs, "runs": [],
        "environment": {"python": platform.python_version(), "executable": sys.executable,
                        "numpy": np.__version__, "pymoo": pymoo.__version__}}
    quality._write(folder / "run.json", state)
    rows = []
    for index, job in enumerate(jobs, 1):
        assert_protected(baseline)
        if source_hashes() != state["inputs"]:
            raise ValueError("source changed during study")
        subfolder = folder / f"{job['seed']}-{job['policy']}"
        subfolder.mkdir()
        environment = dict(os.environ, **{ablation.SESSION_ENV: job["session"], POLICY_ENV: job["policy"],
            "PYTHONIOENCODING": "utf-8", "CUDA_VISIBLE_DEVICES": "", "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
        environment.pop(quality.RESUME_ENV, None)
        print(f"[{index}/6] seed={job['seed']} policy={job['policy']} evaluations=240", flush=True)
        record = quality.supervise_project(job["command"], subfolder / "project.log", environment,
            timeout_seconds=job["hard_timeout_seconds"])
        state["runs"].append({**record, "policy": job["policy"], "seed": job["seed"],
                              "project_run_id": job["project_run_id"]})
        quality._write(folder / "run.json", state)
        if record["exit_code"] != 0 or record["failure"] is not None:
            raise RuntimeError(f"Project run failed: {record}")
        if source_hashes() != state["inputs"]:
            raise ValueError("source changed during Project execution")
        manifest = json.loads((ROOT / ".blackbase/runs" / job["project_run_id"] / "manifest.json").read_text())
        actual = manifest["cases"][0]["result"]["request"]["component_overrides"]["argv"]
        if actual[actual.index("--mutation-policy") + 1] != job["policy"]:
            raise ValueError("actual Case mutation policy differs from declared study")
        observation = read_observations(ROOT, job["project_run_id"], 240)
        rows.append({**observation, "policy": job["policy"]})
        print(f"  succeeded elapsed={record['elapsed_seconds']:.2f}s", flush=True)
    comparison = {**summarize(rows), "run_id": baseline["run_id"], "inputs": state["inputs"]}
    quality._write(folder / "comparison.json", comparison)
    print(json.dumps({"comparison": str(folder / "comparison.json"), "results": [
        {k: v for k, v in r.items() if k not in {"artifact", "identity"}} for r in comparison["results"]]}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
