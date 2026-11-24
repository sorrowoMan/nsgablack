"""Supervise the standard diagnostic Project; never implement a search loop."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def paths(run_id):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", run_id):
        raise ValueError("run_id must be one identifier of at most 64 characters")
    return (ROOT / ".blackbase" / "runs" / run_id).resolve()


def child(run_id):
    from blackbase.project import execute_project
    result = execute_project(ROOT, run_id=run_id, framework="nsgablack")
    write_json(paths(run_id) / "result.json", result.as_dict())
    return result.exit_code


def verified_summary(folder):
    """Resolve the original sealed outputs, never an unverified schedule copy."""
    from blackbase.resources import ArtifactBinding, ArtifactPublisher
    result = json.loads((folder / "result.json").read_text(encoding="utf-8"))
    parent = result["cases"][0]
    identity = parent["identity"]
    reader = ArtifactPublisher.from_resource_context(parent["request"]["resource_context"],
        project_run_id=identity["project_run_id"], case_run_id=identity["case_run_id"])
    try:
        binding = ArtifactBinding.from_dict({"ref": parent["artifact_refs"]["joint_summary"],
            "publication": parent["artifact_publications"]["joint_summary"]})
        joint = json.loads(reader.read_verified(binding))
        production = json.loads(reader.read_verified(ArtifactBinding.from_dict(joint["production_summary_binding"])))
    finally:
        reader.close()
    write_json(folder / "verified_production_summary.json", production)
    return {"production_pid": production["pid"], "parent_case_pid": production["parent_pid"],
            "algorithm_steps": production["algorithm_steps"],
            "algorithm_evaluations": production["algorithm_evaluations"],
            "audit_evaluations": production["audit_evaluations"],
            "day0_max_abs_delta": production["day0_max_abs_delta"],
            "raw_objectives": production["raw_objectives"], "raw_constraints": production["raw_constraints"],
            "model_sha256": production["model_sha256"], "parent_budget_usage": parent["budget_usage"],
            "inner_budget_usage": joint.get("inner_budget_usage")}


def supervise(args):
    import psutil
    folder = paths(args.run_id)
    if folder.exists():
        raise FileExistsError("Use a new run_id; diagnostic evidence is never overwritten")
    available = psutil.virtual_memory().available
    folder.mkdir(parents=True)
    instrumented = args.mode in {"profile", "timing"}
    wall_limit = (200 if args.workload == "iteration" else 100) if instrumented else (110 if args.workload == "iteration" else 60)
    summary = {"schema": "runtime_cost_probe.supervision/v1", "run_id": args.run_id,
               "mode": args.mode, "workload": args.workload, "unit_mode": args.unit_mode,
               "memory_mode": args.memory_mode,
               "repair_mode": args.repair_mode,
               "io_mode": args.io_mode,
               "timing_detail": args.timing_detail,
               "hotpath_mode": args.hotpath_mode,
               "status": "not_started", "initial_available_bytes": available,
               "wall_limit_seconds": wall_limit, "rss_stop_bytes": 512 * 1024**2,
               "free_memory_stop_bytes": 128 * 1024**2, "os_cpu_memory_hard_limits": False,
               "note": "RSS/free-memory are sampled stop conditions; L0 is an authorization grant"}
    if available < 512 * 1024**2:
        summary["reason"] = "available memory below 512 MiB preflight threshold"
        write_json(folder / "supervision.json", summary)
        print(json.dumps(summary, ensure_ascii=False))
        return 3
    env = dict(os.environ)
    env.update(NSGABLACK_RUNTIME_COST_RUN_ID=args.run_id,
               NSGABLACK_RUNTIME_COST_RUN_ROOT=str(folder), CUDA_VISIBLE_DEVICES="",
               NSGABLACK_RUNTIME_COST_WORKLOAD=args.workload,
               NSGABLACK_RUNTIME_UNIT_REFERENCE=args.unit_mode,
               NSGABLACK_RUNTIME_MEMORY_REFERENCE=args.memory_mode,
               NSGABLACK_RUNTIME_REPAIR_REFERENCE=args.repair_mode,
               NSGABLACK_RUNTIME_IO_REFERENCE=args.io_mode,
               NSGABLACK_RUNTIME_TIMING_DETAIL=args.timing_detail,
               NSGABLACK_RUNTIME_HOTPATH_REFERENCE=args.hotpath_mode,
               OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
               TMPDIR=str(folder / "temp"), TEMP=str(folder / "temp"), TMP=str(folder / "temp"))
    (folder / "temp").mkdir()
    env.pop("NSGABLACK_RUNTIME_PROFILE_DIR", None)
    env.pop("NSGABLACK_RUNTIME_TIMING_ONLY", None)
    if instrumented:
        env["NSGABLACK_RUNTIME_PROFILE_DIR"] = str(folder / "profiles")
        env["PYTHONPATH"] = str(ROOT / "profiling") + os.pathsep + env.get("PYTHONPATH", "")
        if args.mode == "timing":
            env["NSGABLACK_RUNTIME_TIMING_ONLY"] = "1"
    started = time.perf_counter()
    samples, known, reason = [], {}, None
    with (folder / "stdout.log").open("wb") as out, (folder / "stderr.log").open("wb") as err:
        process = subprocess.Popen([sys.executable, "-u", str(Path(__file__).resolve()),
            "--child", "--run-id", args.run_id], cwd=str(ROOT), env=env, stdout=out, stderr=err,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        parent = psutil.Process(process.pid)
        while process.poll() is None:
            elapsed = time.perf_counter() - started
            family = [parent]
            try:
                family += parent.children(recursive=True)
            except psutil.NoSuchProcess:
                pass
            rss = 0
            for member in family:
                try:
                    known[(member.pid, member.create_time())] = member
                    rss += member.memory_info().rss
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            free = psutil.virtual_memory().available
            samples.append({"wall_seconds": elapsed, "family_rss_bytes": rss, "available_bytes": free})
            if elapsed > wall_limit:
                reason = "wall deadline"
            elif rss > 512 * 1024**2:
                reason = "process family RSS stop threshold"
            elif free < 128 * 1024**2:
                reason = "system free memory stop threshold"
            if reason:
                # Only these owned processes, checked against creation identity.
                for identity, member in reversed(tuple(known.items())):
                    try:
                        if member.is_running() and member.create_time() == identity[1]:
                            member.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                break
            time.sleep(.25)
        process.wait(timeout=5)
    summary.update(status="stopped" if reason else ("succeeded" if process.returncode == 0 else "failed"),
                   reason=reason, exit_code=process.returncode, wall_seconds=time.perf_counter() - started,
                   peak_sampled_family_rss_bytes=max((row["family_rss_bytes"] for row in samples), default=0),
                   owned_processes=[{"pid": pid, "created_at": stamp} for pid, stamp in known],
                   samples=samples)
    summary["profile_complete"] = False
    summary["timing_complete"] = False
    if summary["status"] == "succeeded":
        try:
            summary["verified_result"] = verified_summary(folder)
            if args.mode == "profile":
                pid = summary["verified_result"]["production_pid"]
                summary["profile_complete"] = (folder / "profiles" / f"process-{pid}.prof").is_file()
                if not summary["profile_complete"]:
                    summary.update(status="failed", reason="production process profile is missing")
            elif args.mode == "timing":
                pid = summary["verified_result"]["production_pid"]
                meta = json.loads((folder / "profiles" / f"process-{pid}.json").read_text(encoding="utf-8"))
                summary["timing_complete"] = meta.get("timer") == "timing_scopes" and bool(meta.get("scopes"))
                if not summary["timing_complete"]:
                    summary.update(status="failed", reason="production timing scopes are missing")
        except Exception as exc:
            summary.update(status="failed", reason=f"sealed result verification failed: {type(exc).__name__}: {exc}")
    write_json(folder / "supervision.json", summary)
    print(json.dumps({key: value for key, value in summary.items() if key != "samples"}, ensure_ascii=False))
    return 0 if summary["status"] == "succeeded" else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--mode", choices=("baseline", "profile", "timing"), default="baseline")
    parser.add_argument("--workload", choices=("bootstrap", "iteration"), default="bootstrap")
    parser.add_argument("--unit-mode", choices=("native", "legacy"), default="native",
                        help="Diagnostic only: legacy restores the pre-optimization Unit paths in profiled processes")
    parser.add_argument("--memory-mode", choices=("native", "legacy"), default="native",
                        help="Diagnostic only: legacy uses transport preparation for Memory snapshots")
    parser.add_argument("--repair-mode", choices=("native", "legacy"), default="native",
                        help="Diagnostic only: legacy rereads unchanged stock for every threshold retry")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--io-mode", choices=("native", "legacy"), default="native",
                        help="diagnostic reference for budget connections and canonical-byte export")
    parser.add_argument("--timing-detail", choices=("fine", "coarse"), default="fine",
                        help="coarse avoids recursive per-node timing wrappers")
    parser.add_argument("--hotpath-mode", choices=("native", "legacy"), default="native",
                        help="diagnostic reference for pre-fusion Memory tree preparation")
    args = parser.parse_args(argv)
    if not args.child and args.hotpath_mode == "legacy" and args.mode not in {"profile", "timing"}:
        parser.error("legacy hotpath reference requires profile or timing mode")
    if not args.child and args.io_mode == "legacy" and args.mode not in {"profile", "timing"}:
        parser.error("legacy IO reference requires profile or timing mode")
    if not args.child and args.unit_mode == "legacy" and not args.mode in {"profile", "timing"}:
        parser.error("legacy Unit reference requires --mode profile/timing")
    if not args.child and args.memory_mode == "legacy" and not args.mode in {"profile", "timing"}:
        parser.error("legacy Memory reference requires --mode profile/timing")
    if not args.child and args.repair_mode == "legacy" and args.mode not in {"profile", "timing"}:
        parser.error("legacy repair reference requires --mode profile/timing")
    return child(args.run_id) if args.child else supervise(args)


if __name__ == "__main__":
    raise SystemExit(main())
