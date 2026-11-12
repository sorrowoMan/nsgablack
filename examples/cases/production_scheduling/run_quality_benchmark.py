"""依次运行正式 Project 质量组，并用同一原始四目标复核整数排程。

默认是 4 种算法 × 3 个随机种子。每组通过 run_project.py / Project / L0
执行；本文件只监督进程、核验收据和汇总已有导出，不另写求解循环。
使用 --plan 先查看规模；失败保留记录且不重试。--report-only 只重读结果。
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys
import time
from uuid import uuid4


ROOT = Path(__file__).resolve().parent
CASE_ROOT = ROOT / "cases" / "production_scheduling"
ALGORITHMS = ("greedy", "aco", "phased", "directional")
SEEDS = (42, 43, 44)
SESSION_ENV = "NSGABLACK_PRODUCTION_QUALITY_RUN_ID"
RESUME_ENV = "NSGABLACK_PRODUCTION_RESUME_CHECKPOINT"
MAX_LOG_BYTES = 4 * 1024 * 1024
EXPECTED_DATA = {
    "machine_material_mapping.csv": "2aef063f7085b71f08ffb4c9544b83f76e4b392ad3215fa5a751d7c4b3eadd7f",
    "SUPPLY.xlsx": "d2d2cb65649b29125e4002295c67f9ee110b956b7fa7607acd7f5d1fffadd192",
}


def _write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


@contextmanager
def _session(run_id, *, resume=None):
    old = {key: os.environ.get(key) for key in (SESSION_ENV, RESUME_ENV)}
    os.environ[SESSION_ENV] = run_id
    if resume:
        os.environ[RESUME_ENV] = str(resume)
    else:
        os.environ.pop(RESUME_ENV, None)
    try:
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def quality_groups(requested, seeds):
    """Expand only the statically declared quality groups, preserving order."""
    groups = []
    for seed in dict.fromkeys(seeds):
        if seed not in SEEDS:
            raise ValueError("quality seeds are explicitly declared as 42, 43 and 44")
        for name in requested:
            if name in ALGORITHMS:
                group = f"quality_{name}_s{seed}"
            elif name == "pilot":
                if seed != 42:
                    continue
                group = "quality_pilot_s42"
            elif re.fullmatch(r"quality_(greedy|aco|phased|directional)_s(42|43|44)", name):
                if not name.endswith(f"_s{seed}"):
                    continue
                group = name
            elif name == "quality_pilot_s42":
                if seed != 42:
                    continue
                group = name
            else:
                raise ValueError(f"unknown quality group: {name}")
            if group not in groups:
                groups.append(group)
    if not groups:
        raise ValueError("the group/seed selection is empty")
    return groups


def quality_plan(run_id, groups, *, resume=None):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", run_id):
        raise ValueError("run_id must be a single identifier of at most 80 characters")
    if resume:
        if len(groups) != 1 or not (groups[0].startswith("quality_directional_") or groups[0] == "quality_pilot_s42"):
            raise ValueError("--resume requires exactly one directional/pilot group and one seed")
        resume = str(Path(resume).expanduser().resolve())
    with _session(run_id, resume=resume):
        config = runpy.run_path(str(ROOT / "project_config.py"))
    by_name = {stage["name"]: stage for stage in config["STAGES"]}
    result = []
    for name in groups:
        if name not in config["GROUPS"] or name not in by_name:
            raise ValueError(f"Project has not declared {name}")
        stage = by_name[name]
        result.append({"group": name, "project_run_id": f"{run_id}-{name}",
            "stage": stage, "command": [sys.executable, "-u", str(ROOT / "run_project.py"),
                "--group", name, "--run-id", f"{run_id}-{name}"],
            "hard_timeout_seconds": float(stage["timeout_seconds"]) + 30})
    return result


def _input_hashes():
    files = list(CASE_ROOT.rglob("*.py")) + [ROOT / "project_config.py", ROOT / "run_project.py", Path(__file__)]
    files += [CASE_ROOT / name for name in EXPECTED_DATA]
    records = {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in sorted(set(files))}
    # Comparison semantics also depend on the shared installed implementation,
    # not just the Case that imports it.
    import inspect
    from blackbase.plugin import PluginManager
    from blackbase.context.snapshot_store import SnapshotStore
    from blackbase.context.redis_codec import canonical_safe_value_bytes
    from nsgablack.adapters import MOEADAdapter, VNSAdapter
    from nsgablack.plugins import CheckpointResumePlugin
    from nsgablack.representation import RepresentationPipeline
    from nsgablack.representation.state import PipelineStateMixin
    from nsgablack.core.state.representation_state import RepresentationStateParticipant
    from nsgablack.core.blank_solver import SolverBase
    from nsgablack.core.state.solution_pool import SolutionPool
    from nsgablack.core.state.candidate_batch_payload import candidate_batch_snapshot_payload
    for component in (PluginManager, SnapshotStore, canonical_safe_value_bytes,
                      MOEADAdapter, VNSAdapter, SolverBase, SolutionPool,
                      candidate_batch_snapshot_payload, CheckpointResumePlugin,
                      RepresentationPipeline, PipelineStateMixin, RepresentationStateParticipant):
        path = Path(inspect.getfile(component))
        records[f"framework/{component.__module__}"] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name, expected in EXPECTED_DATA.items():
        if records[(CASE_ROOT / name).relative_to(ROOT).as_posix()] != expected:
            raise ValueError(f"canonical input data changed: {name}")
    return records


def _verify_existing_export_hashes(folder):
    """Report-only must not attribute edited CSV bytes to an older experiment."""
    previous = json.loads((folder / "comparison.json").read_text(encoding="utf-8"))
    for row in previous["reports"]:
        path = (ROOT / row["csv_file"]).resolve()
        if (not path.is_relative_to(folder.resolve()) or not path.is_file()
                or hashlib.sha256(path.read_bytes()).hexdigest() != row["csv_sha256"]):
            raise ValueError("delivered CSV differs from the recorded experiment bytes")


def _stop_owned_tree(process):
    import psutil
    try:
        owner = psutil.Process(process.pid)
        owned = owner.children(recursive=True) + [owner]
    except psutil.NoSuchProcess:
        return
    for child in reversed(owned):
        try:
            child.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(owned, timeout=5)
    for child in alive:
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    process.wait(timeout=10)


def supervise_project(command, log_path, environment, *, timeout_seconds):
    """Bound only this owned formal Project process; do not retry or resume."""
    started, failure = time.monotonic(), None
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with log_path.open("xb") as output:
        process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=output,
            stderr=subprocess.STDOUT, creationflags=creationflags)
        while process.poll() is None:
            if time.monotonic() - started > timeout_seconds:
                failure = "project_hard_timeout"
            elif log_path.stat().st_size > MAX_LOG_BYTES:
                failure = "project_log_limit"
            if failure:
                _stop_owned_tree(process)
                break
            time.sleep(0.25)
    return {"exit_code": process.returncode, "elapsed_seconds": time.monotonic() - started,
            "failure": failure, "log_file": str(log_path.relative_to(ROOT))}


def _formal_result(item):
    from blackbase.project.execution import CaseRunResult
    from blackbase.project.run_manifest import ProjectRunManifest
    from blackbase.wire import thaw_wire_mapping
    path = ROOT / ".blackbase" / "runs" / item["project_run_id"] / "manifest.json"
    manifest = ProjectRunManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))
    if manifest.run_id != item["project_run_id"] or manifest.status != "ok" or manifest.exit_code != 0 or len(manifest.cases) != 1:
        raise ValueError("formal Project did not complete the selected single Case")
    case = CaseRunResult.from_dict(manifest.cases[0]["result"])
    if not case.ok or case.status != "succeeded" or case.identity.project_run_id != item["project_run_id"]:
        raise ValueError("formal Case success receipt does not match this experiment")
    binding = dict(case.resource_usage.get("binding", {}))
    resources = binding.get("effective", {}).get("resources", {})
    if binding.get("current") is not True or resources.get("threads") != 1 or resources.get("gpus") != 0:
        raise ValueError("effective Project L0 grant differs from one CPU / no GPU")
    report = thaw_wire_mapping(case.output.get("report", {}))
    count = report.get("evaluation_count")
    limit = 300 if item["group"] == "quality_pilot_s42" else 2500
    if type(count) is not int or not 0 < count <= limit:
        raise ValueError("formal evaluation count is missing or exceeds the declared budget")
    return {"manifest": str(path.relative_to(ROOT)), "case_identity": case.identity.as_dict(),
            "evaluations": count, "steps": report.get("steps", report.get("steps_executed", report.get("generation"))),
            "case_elapsed_seconds": case.elapsed_seconds,
            "resource_binding_current": True, "threads": 1, "gpus": 0,
            "termination_reason": case.output.get("termination_reason")}


def _audit_problem():
    from examples.cases.production_scheduling.cases.production_scheduling.refactor_data import load_production_data
    from examples.cases.production_scheduling.cases.production_scheduling.problem.production_problem import ProductionConstraints, ProductionSchedulingProblem
    data = load_production_data(base_dir=CASE_ROOT, machines=22, materials=157, days=31, fallback=False)
    return ProductionSchedulingProblem(data, ProductionConstraints(max_machines_per_day=8,
        min_machines_per_day=5, min_production_per_machine=50,
        max_production_per_machine=10000, include_penalty_objective=False))


def aggregate_results(folder, state):
    import numpy as np
    import pandas as pd
    from examples.cases.production_scheduling.cases.production_scheduling.reporting.quality_selection import evaluate_schedule_quality, select_schedule_quality
    problem, reports = _audit_problem(), []
    group_positions = {}
    for run in state["runs"]:
        if run["status"] != "succeeded":
            continue
        positions = group_positions.setdefault(run["group"], [])
        for path in sorted((folder / run["group"] / "exports").rglob("*.csv")):
            table = pd.read_csv(path)
            if "Machine0" not in table:
                continue
            if table["Day_Index"].tolist() != list(range(31)):
                raise ValueError("delivered schedule dates do not cover exactly 31 days")
            values = table[[f"Machine{i}" for i in range(22)]].to_numpy(dtype=float).T
            if not np.array_equal(values, np.floor(values)):
                raise ValueError("delivered CSV contains fractional production quantities")
            audited = evaluate_schedule_quality(problem, values, label=path.stem)
            audited.update(group=run["group"], csv_file=str(path.relative_to(ROOT)),
                csv_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                project_run_id=run["project_run_id"])
            positions.append(len(reports))
            reports.append(audited)
        if not positions:
            raise ValueError(f"successful group has no delivered schedule CSV: {run['group']}")
    # Include every feasible arm when freezing shared report scales. A global
    # frontier may be a single dominating plan; its zero-width bounds cannot
    # describe an inferior algorithm's nonconstant objective values.
    feasible_vectors = [report["raw_objectives"] for report in reports if report["hard_feasible"]]
    bounds = None
    if feasible_vectors:
        matrix = np.asarray(feasible_vectors, dtype=float)
        bounds = np.stack((np.min(matrix, axis=0), np.max(matrix, axis=0)), axis=1).tolist()
    global_policies = {policy: select_schedule_quality(reports, policy=policy,
                           **({"normalization_bounds": bounds} if policy == "balanced" and bounds is not None else {}))
                       for policy in ("pareto", "production", "stability", "balanced")}
    by_group, rows = {}, []
    for run in state["runs"]:
        if run["group"] not in group_positions:
            continue
        positions = group_positions[run["group"]]
        local = [reports[i] for i in positions]
        policies = {policy: select_schedule_quality(local, policy=policy,
                       **({"normalization_bounds": bounds} if policy == "balanced" and bounds is not None else {}))
                    for policy in ("pareto", "production", "stability", "balanced")}
        by_group[run["group"]] = {"report_positions": positions, "policies": policies}
        for policy in ("production", "stability", "balanced"):
            chosen = policies[policy]["selected_indices"]
            if not chosen:
                continue
            selected = local[chosen[0]]
            metrics = selected["audit"]
            rows.append({"group": run["group"], "policy": policy,
                "evaluations": run["formal"]["evaluations"], "elapsed_seconds": run["elapsed_seconds"],
                "production": metrics["production"]["total"], "daily_cv": metrics["production"]["daily_cv"],
                "switches": metrics["machine_usage"]["switches_total"],
                "soft_active_shortfall": selected["soft_deviations"]["active_count_shortfall"],
                "raw_objectives": json.dumps(selected["raw_objectives"]), "csv_file": selected["csv_file"]})
    summary = {"schema": "production_scheduling.quality_benchmark/v1", "run_id": state["run_id"],
        "inputs": state["inputs"], "runs": state["runs"], "reports": reports,
        "global_policies": global_policies, "by_group": by_group,
        "comparison_scope": "same full 22/157-slots/31 data (156 material IDs, maximum 157) and original four-objective audit Problem",
        "normalization_scope": "one shared minimum/maximum over all supplied hard-feasible original objective vectors; reference anchors, not a mathematical global ideal/nadir proof",
        "audit_scope": "post-run CSV re-evaluation is separate from algorithm evaluation counts",
        "interpretation": "Production/stability/balanced are declared display policies; no unique user preference or global optimality is inferred."}
    _write(folder / "comparison.json", summary)
    if rows:
        with (folder / "comparison.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    recommended = folder / "recommendations"
    recommended.mkdir(exist_ok=True)
    for policy in ("production", "stability", "balanced"):
        indices = global_policies[policy]["selected_indices"]
        if indices:
            selected = reports[indices[0]]
            shutil.copyfile(ROOT / selected["csv_file"], recommended / f"{policy}.csv")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--groups", nargs="+", default=list(ALGORITHMS), help="算法名称或已声明的完整quality组名；可选pilot")
    parser.add_argument("--seeds", nargs="+", type=int, default=list(SEEDS), choices=SEEDS)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--resume", metavar="CHECKPOINT", default=None,
                        help="从指定checkpoint继续一个方向精修组；需要同配置/种子及原签名密钥文件")
    parser.add_argument("--plan", action="store_true", help="只显示正式Project执行计划，不运行")
    parser.add_argument("--report-only", action="store_true", help="只核对和汇总指定run-id的既有结果")
    args = parser.parse_args(argv)
    if args.report_only and not args.run_id:
        parser.error("--report-only requires --run-id")
    if args.report_only and args.resume:
        parser.error("--report-only cannot be combined with --resume")
    run_id = args.run_id or f"quality-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}"
    plan = quality_plan(run_id, quality_groups(args.groups, args.seeds), resume=args.resume)
    if args.plan:
        print(json.dumps({"run_id": run_id, "runs": plan}, ensure_ascii=False, indent=2))
        return 0
    # Use the installed framework or this checkout; the formal child entry
    # retains its own standard Project bootstrap and resource authorization.
    if str(ROOT.parents[2]) not in sys.path:
        sys.path.insert(0, str(ROOT.parents[2]))
    folder = ROOT / "results" / "quality" / run_id
    if args.report_only:
        state = json.loads((folder / "benchmark.json").read_text(encoding="utf-8"))
        if _input_hashes() != state["inputs"]:
            raise ValueError("original model, source or data changed since this benchmark")
        _verify_existing_export_hashes(folder)
        aggregate_results(folder, state)
        return 0
    folder.mkdir(parents=True, exist_ok=False)
    state = {"schema": "production_scheduling.quality_run/v1", "run_id": run_id,
             "inputs": _input_hashes(), "plan": plan, "runs": [],
             "resume_checkpoint": str(Path(args.resume).resolve()) if args.resume else None}
    _write(folder / "benchmark.json", state)
    environment = dict(os.environ, **{SESSION_ENV: run_id, "PYTHONIOENCODING": "utf-8",
        "CUDA_VISIBLE_DEVICES": "", "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
    if args.resume:
        environment[RESUME_ENV] = str(Path(args.resume).expanduser().resolve())
    else:
        environment.pop(RESUME_ENV, None)
    failed = False
    for index, item in enumerate(plan, 1):
        if _input_hashes() != state["inputs"]:
            raise ValueError("original model, source or data changed during the benchmark")
        group_folder = folder / item["group"]
        group_folder.mkdir(exist_ok=False)
        print(f"[{index}/{len(plan)}] {item['group']}：启动正式Project，单CPU/noGPU，最大900秒。", flush=True)
        result = supervise_project(item["command"], group_folder / "project.log", environment,
                                   timeout_seconds=item["hard_timeout_seconds"])
        row = {"group": item["group"], "project_run_id": item["project_run_id"], **result,
               "status": "failed"}
        if result["exit_code"] == 0 and result["failure"] is None:
            try:
                row["formal"] = _formal_result(item)
                if _input_hashes() != state["inputs"]:
                    raise ValueError("original inputs changed during Project execution")
                row["status"] = "succeeded"
            except (ValueError, KeyError, OSError) as exc:
                row["failure"] = str(exc)
        state["runs"].append(row)
        _write(folder / "benchmark.json", state)
        print(f"[{index}/{len(plan)}] {item['group']}：{row['status']}，{row['elapsed_seconds']:.2f}秒。", flush=True)
        if row["status"] != "succeeded":
            failed = True
            break
    summary = aggregate_results(folder, state)
    print(json.dumps({"run_id": run_id, "completed_groups": len(summary["by_group"]),
                      "comparison": str(folder / "comparison.json"), "failed": failed}, ensure_ascii=False), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
