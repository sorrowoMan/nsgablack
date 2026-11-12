"""离线汇总已经完成的 Project Artifact；不启动 Solver，不重算算法结果。"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import sys


def read_report(case):
    from blackbase.resources.artifacts import ArtifactPublicationReceipt

    receipt = ArtifactPublicationReceipt.from_dict(case["artifact_publications"]["report"])
    reference = case["artifact_refs"]["report"]
    if receipt.ref.as_dict() != reference or receipt.metadata.get("case_finalization_sealed") is not True:
        raise ValueError("report reference differs from its sealed publication receipt")
    data = Path(reference["uri"]).read_bytes()
    if len(data) != reference["size_bytes"] or "sha256:" + hashlib.sha256(data).hexdigest() != reference["checksum"]:
        raise ValueError("report Artifact bytes differ from the published checksum")
    return json.loads(data)


def _compact(row):
    overhead = row.get("overhead", {})
    normal = overhead.get("normal_iterations", {})
    normal_left, normal_right = normal.get("reference", {}), normal.get("framework", {})
    evaluations = row.get("semantics", {}).get("framework_evaluations")
    left, right = overhead.get("reference", {}), overhead.get("framework", {})
    quality = row.get("quality", {})
    cpu_ratio = (right.get("cpu_s", 0) / left["cpu_s"] if left.get("cpu_s") else None)
    return {"name": row["name"], "seed": row["seed"], "steps": row["steps"],
            "evaluations": evaluations, "metadata": row.get("metadata", {}),
            "statuses": {key: row.get(key, {}).get("status") for key in ("semantics", "quality", "overhead", "recovery")},
            "quality": quality,
            "cost": {"reference_wall_s": left.get("wall_s"), "framework_wall_s": right.get("wall_s"),
                     "reference_cpu_s": left.get("cpu_s"), "framework_cpu_s": right.get("cpu_s"),
                     "wall_ratio": overhead.get("wall_ratio"), "cpu_ratio": cpu_ratio,
                     "extra_wall_ms_per_evaluation": (1000 * overhead["wall_difference_s"] / evaluations
                                                        if evaluations and "wall_difference_s" in overhead else None),
                     "normal_reference_wall_s": normal_left.get("wall_s_sum"),
                     "normal_framework_wall_s": normal_right.get("wall_s_sum"),
                     "normal_reference_cpu_s": normal_left.get("cpu_s_sum"),
                     "normal_framework_cpu_s": normal_right.get("cpu_s_sum"),
                     "normal_commits": normal_right.get("count"),
                     "reference_io": left.get("io"), "framework_io": right.get("io"),
                     "scope": overhead.get("interpretation")}}


def _validate_report(report):
    for section in ("validation", "comparison"):
        if section in report and report[section].get("status") != "passed":
            raise ValueError(f"Artifact internal {section} did not pass")
    if report.get("mode") == "matrix":
        if not report.get("rows"):
            raise ValueError("empty matrix is not successful benchmark evidence")
        for row in report["rows"]:
            for section in ("semantics", "quality"):
                if row.get(section, {}).get("status") != "passed":
                    raise ValueError(f"Artifact row {row['name']} {section} did not pass")
            recovery = row.get("recovery", {})
            if not (recovery.get("status") == "passed" or
                    (recovery.get("status") == "unsupported" and recovery.get("reason") == "not requested")):
                raise ValueError(f"Artifact row {row['name']} recovery did not pass")
            if row.get("overhead", {}).get("status") != "measured":
                raise ValueError(f"Artifact row {row['name']} overhead was not measured")


def collect(manifests, *, faults_path=None):
    """Verify bytes and receipt integrity; authority ledger checks stay in BlackBase."""
    from benchmarks.transparency_registry import coverage_report

    runs, all_rows = [], []
    for location in manifests:
        path = Path(location).resolve()
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest["status"] != "ok" or manifest["exit_code"] != 0:
            raise ValueError(f"Project is not completed successfully: {path}")
        cases = []
        for case in manifest["cases"]:
            if case["status"] != "succeeded":
                raise ValueError("non-successful Case cannot enter a success summary")
            report = read_report(case)
            _validate_report(report)
            rows = report.get("rows", [])
            all_rows.extend(rows)
            cases.append({"case": case["case_name"], "stage": case["stage_name"], "mode": report["mode"],
                          "identity": report["identity"], "pid": report["pid"],
                          "started_at": report["started_at"], "finished_at": report["finished_at"],
                          "resource_binding_current": report["resource_binding"].get("current"),
                          "artifact_ref": case["artifact_refs"]["report"],
                          "publication": case["artifact_publications"]["report"],
                          "comparison": report.get("comparison"),
                          "child_identity": report.get("child_identity"),
                          "child_publications": report.get("child_publications"),
                          "rows": [_compact(row) for row in rows]})
        runs.append({"run_id": manifest["run_id"], "group": manifest["group"], "manifest": str(path), "cases": cases})
    # Recovery-disabled quality profiles must not override actual full recovery
    # evidence or be counted as having passed recovery themselves.
    complete = [r for r in all_rows if r.get("recovery", {}).get("status") != "unsupported"]
    faults = None if faults_path is None else json.loads(Path(faults_path).read_text(encoding="utf-8"))
    return {"schema": "nsgablack.transparency_summary/v1", "runs": runs,
            "summary": {"rows": len(all_rows),
                        "sections": {key: dict(Counter(r[key]["status"] for r in all_rows))
                                     for key in ("semantics", "quality", "overhead", "recovery")}},
            "coverage": coverage_report(complete),
            "faults": faults,
            "limits": ["small deterministic fixtures, not every parameter/problem/provider branch",
                       "trace-instrumented diagnostic cost, not production throughput",
                       "reference traces remain resident during framework run; RSS is not an isolated memory comparison",
                       "summary checks receipt integrity and Artifact bytes; runtime verifies authority ledger"]}


def source_fingerprints(root=None):
    root = Path(root or Path(__file__).resolve().parents[1])
    files = [*sorted((root / "benchmarks").glob("transparency_*.py")),
             root / "benchmarks" / "classical_quality.py",
             *sorted((root / "adapters" / "nsga3").glob("*.py")),
             root / "adapters" / "nsga2" / "adapter.py", root / "adapters" / "moead" / "adapter.py",
             root / "units" / "collections.py",
             root / "adapters" / "mas" / "adapter.py",
             root / "adapters" / "async_event_driven" / "adapter.py",
             root / "adapters" / "unit_backed.py",
             root / "core" / "blank_solver.py", root / "core" / "composable_solver.py",
             root / "core" / "state" / "solution_pool.py", root / "units" / "contracts.py",
             root / "examples" / "cases" / "algorithm_transparency" / "project_config.py",
             root / "examples" / "cases" / "algorithm_transparency" / "case_cli.py",
             root / "benchmarks" / "reference_sets" / "manifest.json"]
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def write_summary(destination, manifests, *, faults_path=None):
    from importlib.metadata import PackageNotFoundError, version

    result = collect(manifests, faults_path=faults_path)
    result["source_fingerprints_at_collection"] = source_fingerprints()
    packages = {}
    for name in ("nsgablack", "blackbase", "numpy", "scipy", "scikit-learn", "pymoo", "moocore", "psutil"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = "not_installed_as_distribution"
    result["environment"] = {"python": sys.version, "platform": platform.platform(), "packages": packages}
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return result
