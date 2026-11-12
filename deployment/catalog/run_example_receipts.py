"""Run a fixed CPU showcase allowlist through genuine Project CLIs.

Catalog prose, AI output and index commands never become executable code. Every
command below is fixed here and matched against the preliminary index. Projects
run in fresh source-only copies; generated results never contaminate source.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Mapping


SCHEMA = "nsgablack.catalog.example_receipts/v1"
ALLOWLIST = {
    "pool-workflow": {
        "framework": "nsgablack", "project": "examples/cases/pool_workflow_pilot",
        "command": "python examples/cases/pool_workflow_pilot/run_project.py",
        "cases": {"ga_search": "pool-workflow-ga", "vns_search": "pool-workflow-vns",
                  "moead_search": "pool-workflow-moead"},
    },
    "ml-linear-point": {
        "framework": "mlblack", "project": "examples/cases/catalog_codec_demo",
        "command": "python examples/cases/catalog_codec_demo/run_project.py",
        "cases": {"linear_point": "ml-linear-point"},
    },
    "risk-bias": {
        "framework": "nsgablack", "project": "examples/cases/risk_bias",
        "command": "python examples/cases/risk_bias/run_project.py",
        "cases": {"risk_bias": "risk-bias"},
    },
    "fixed-candidate": {
        "framework": "nsgablack", "project": "examples/cases/catalog_fixed_candidate",
        "command": "python examples/cases/catalog_fixed_candidate/run_project.py",
        "cases": {"fixed": "fixed-candidate-project"},
    },
}
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_SKIP = {".git", ".blackbase", ".pytest_cache", "__pycache__", "results", "outputs",
         "runs", "artifacts", "checkpoints", ".venv", "venv", "node_modules"}
_SOURCE_EXTENSIONS = {".py", ".md", ".toml", ".json", ".rst"}
MAX_FILE_BYTES = 2 * 1024 * 1024


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _read_json(path: Path, *, limit: int = 16 * 1024 * 1024) -> dict:
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError("missing_or_oversized_json")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("json_object_required")
    return value


def _source_path(roots: Mapping[str, Path], qualified: str) -> Path:
    parts = qualified.split("/")
    if len(parts) < 2 or parts[0] not in roots or any(p in {"", ".", ".."} for p in parts):
        raise ValueError("source_path_invalid")
    if "\\" in qualified or ":" in qualified:
        raise ValueError("source_path_invalid")
    root = roots[parts[0]]
    target = root
    for part in parts[1:]:
        target = target / part
        if target.is_symlink() or bool(getattr(target, "is_junction", lambda: False)()):
            raise ValueError("source_link_refused")
    if not target.resolve().is_relative_to(root) or not target.is_file():
        raise ValueError("source_missing")
    return target


def validate_sources(record: Mapping[str, Any], roots: Mapping[str, Path]) -> None:
    files = record.get("source_files")
    if not isinstance(files, dict) or not files:
        raise ValueError("source_closure_required")
    for qualified, digest in files.items():
        path = _source_path(roots, qualified)
        if not isinstance(digest, str) or not _HEX.fullmatch(digest) or path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("source_digest_invalid")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("source_changed_since_index")


def _copy_project(source: Path, destination: Path) -> None:
    count = 0
    for folder, dirs, files in os.walk(source, followlinks=False):
        current = Path(folder)
        for name in tuple(dirs):
            child = current / name
            if child.is_symlink() or bool(getattr(child, "is_junction", lambda: False)()):
                raise ValueError("project_link_refused")
        dirs[:] = [name for name in dirs if name not in _SKIP and not name.startswith(".")]
        for name in files:
            path = current / name
            if path.is_symlink():
                raise ValueError("project_link_refused")
            if name != ".case" and (name.startswith(".") or path.suffix not in _SOURCE_EXTENSIONS):
                continue
            if path.stat().st_size > MAX_FILE_BYTES:
                raise ValueError("project_source_oversized")
            count += 1
            if count > 1200:
                raise ValueError("project_source_count_exceeded")
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)


def _case_observations(case: dict, *, project: Path, case_name: str, preset: str,
                       fixed_report: Mapping[str, Any] | None = None) -> list[str]:
    if case.get("status") != "succeeded" or case.get("exit_code") != 0:
        raise ValueError("case_did_not_succeed")
    usage = case.get("resource_usage", {})
    if usage.get("binding", {}).get("current") is not True:
        raise ValueError("case_resource_binding_not_current")
    runtime = case.get("metadata", {}).get("runtime_state", {})
    output = case.get("output", {})
    report = output.get("report", {})
    observed = [f"Case {case_name}: succeeded; Project L0 resource binding current=true; CPU.",
                f"Assembled {runtime.get('case_class', 'unknown')} / {runtime.get('adapter', 'unknown')}."]
    if preset == "pool-workflow":
        trace = _read_json(project / "results" / f"{case_name}.json")
        final, result, initial = trace["final"], trace["result"], trace["initial"]
        if final["steps"] != 10 or report.get("evaluation_count") != final["evaluations"]:
            raise ValueError("trace_progress_or_evaluation_count_disagrees")
        if any(initial[key] for key in ("unit_exists", "current_exists", "neighborhood_exists")):
            raise ValueError("source_eagerly_created_unit")
        expected_count = 1 if case_name == "vns_search" else 6
        if len(result["refs"]) != expected_count:
            raise ValueError("final_membership_wrong")
        rows = zip(result["candidates"], result["raw_objectives"], result["raw_violations"], strict=True)
        for x, objectives, violation in rows:
            centers = ((0.5, -0.5),) if case_name == "vns_search" else ((-1.0, 0.0), (1.0, 0.0))
            expected = [sum((a - b) ** 2 for a, b in zip(x, center, strict=True)) for center in centers]
            if violation != 0 or len(expected) != len(objectives) or any(abs(t) > 2 for t in x):
                raise ValueError("raw_feedback_or_bounds_invalid")
            if any(not math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-14)
                   for a, b in zip(objectives, expected, strict=True)):
                raise ValueError("raw_objectives_disagree_with_problem")
        observed += [f"Committed steps={final['steps']}; actual evaluations={final['evaluations']}; seed={'31' if case_name == 'vns_search' else '37'}.",
                     f"Initial pool references={len(initial['initial_refs'])}; final exact members={len(result['refs'])}.",
                     "Raw objectives=" + _json(result["raw_objectives"]),
                     "Stored raw objectives and violations checked against the analytic Problem; bounds passed.",
                     f"Elite collection members={len(final['elite']['refs'])}; accepted change output members={len(trace['change_output']['refs'])}."]
        if case_name == "moead_search":
            if len(trace["views"]) != 6:
                raise ValueError("direction_views_missing")
            observed.append("MOEA/D published 6 direction views; raw feedback retains two objective columns.")
    elif preset == "ml-linear-point":
        representation = report.get("representation", {})
        codec, head = representation.get("codec", {}), representation.get("head", {})
        if (representation.get("name") != "linear_point" or codec.get("codec") != "linear_point"
                or head.get("name") != "point" or report.get("steps") != 3):
            raise ValueError("ml_representation_or_progress_mismatch")
        score = report.get("best_score")
        if not isinstance(score, (float, int)) or not math.isfinite(score):
            raise ValueError("ml_best_score_not_finite")
        publications = case.get("artifact_publications", {})
        if "best_model" not in publications:
            raise ValueError("ml_best_model_publication_missing")
        observed += ["Synthetic data: seed=17; 24 rows; 2 features; max_steps=3; SGD learning_rate=0.05.",
                     "Actual representation=" + _json({key: representation[key] for key in ("name", "dimension", "base_dimension")}),
                     "Actual codec=" + _json(codec) + "; head=" + _json({key: head[key] for key in ("name", "output_kind", "parameter_size")}),
                     f"Committed ML steps={report['steps']}; best_score={score:.12g}.",
                     "Best metrics=" + _json(report.get("best_metrics", {})),
                     "Finalized best_model Artifact checksum=" + str(publications["best_model"]["ref"]["checksum"]),
                     "Pure NumPy CPU route; this run does not validate NeuralGraphCodec or a neural backend."]
    elif preset == "fixed-candidate":
        if (report.get("steps") != 1 or report.get("evaluation_count") != 1
                or runtime.get("adapter") != "FixedCandidateAdapter"
                or output.get("best_objectives") != [0.625]
                or fixed_report != {"steps": 1, "evaluations": 1, "accepted_refs": 1,
                                    "candidates": [[0.25, 0.75]], "raw_objectives": [[0.625]],
                                    "raw_violations": [0.0]}):
            raise ValueError("fixed_candidate_result_mismatch")
        observed += ["FixedCandidateAdapter + two-dimensional Sphere + ClipRepair; one committed step and one evaluation.",
                     "Accepted candidate=[0.25,0.75]; independently checked raw objective=0.625; raw violation=0.",
                     "The Project prints fixed-candidate-result with the actual accepted SolutionRef feedback."]
    else:
        progress = {key: report[key] for key in ("steps", "steps_executed", "generation", "evaluation_count") if key in report}
        if not progress or not report.get("evaluation_count", 0):
            raise ValueError("no_real_evaluation_reported")
        observed += ["Observed progress=" + _json(progress),
                     "Best raw objectives=" + _json(output.get("best_objectives")),
                     "RiskCostProblem + RiskBias + TrustRegionDFO, with scenario evaluation Plugin; see assembly source."]
    return observed


def run_preset(name: str, roots: Mapping[str, Path], index: dict, *, timeout: int) -> list[dict]:
    if name not in ALLOWLIST:
        raise ValueError("example_not_allowlisted")
    preset = ALLOWLIST[name]
    framework = preset["framework"]
    publication = index.get("publication_digest")
    if not isinstance(publication, str) or not _HEX.fullmatch(publication):
        raise ValueError("publication_digest_required")
    records = {}
    for case_name, identifier in preset["cases"].items():
        record = index.get("examples", {}).get(identifier)
        if not isinstance(record, dict) or record.get("run_command") != preset["command"]:
            raise ValueError("allowlisted_command_missing_or_changed")
        if record.get("working_directory") != framework or record.get("publication_digest") != publication:
            raise ValueError("example_scope_mismatch")
        validate_sources(record, roots)
        records[case_name] = record
    source = roots[framework] / preset["project"]
    if not source.is_dir() or not (source / "project_config.py").is_file():
        raise ValueError("allowlisted_project_unavailable")
    with tempfile.TemporaryDirectory(prefix="catalog-example-") as temporary:
        work = Path(temporary) / framework
        project = work / preset["project"]
        _copy_project(source, project)
        command = shlex.split(preset["command"])
        # Executable spelling is descriptive; execute this interpreter without a shell.
        argv = [sys.executable, *command[1:]]
        env = os.environ.copy()
        parents = [str(root.parent) for root in roots.values()]
        env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys([*parents, env.get("PYTHONPATH", "")]))
        env.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", PYTHONUTF8="1")
        started = time.monotonic()
        with (Path(temporary) / "run.log").open("wb") as log:
            result = subprocess.run(argv, cwd=work, env=env, stdout=log, stderr=subprocess.STDOUT,
                                    timeout=timeout, check=False)
        if result.returncode:
            raise ValueError(f"project_exit_{result.returncode}")
        manifests = list((project / ".blackbase" / "runs").glob("*/manifest.json"))
        if len(manifests) != 1:
            raise ValueError("one_fresh_project_manifest_required")
        manifest = _read_json(manifests[0])
        if manifest.get("exit_code") != 0 or manifest.get("status") != "ok":
            raise ValueError("project_manifest_not_successful")
        cases = {row.get("case_name"): row.get("result") for row in manifest.get("cases", [])}
        if set(cases) != set(records):
            raise ValueError("project_case_set_changed")
        fixed_report = None
        if name == "fixed-candidate":
            log_path = Path(temporary) / "run.log"
            if log_path.stat().st_size > 1024 * 1024:
                raise ValueError("fixed_candidate_log_oversized")
            reports = [line.partition("fixed-candidate-result ")[2]
                       for line in log_path.read_text(encoding="utf-8").splitlines()
                       if line.startswith("fixed-candidate-result ")]
            if len(reports) != 1:
                raise ValueError("fixed_candidate_report_missing_or_ambiguous")
            fixed_report = json.loads(reports[0])
        receipts = []
        for case_name, record in records.items():
            validate_sources(record, roots)
            observed = _case_observations(cases[case_name], project=project, case_name=case_name,
                                          preset=name, fixed_report=fixed_report)
            receipts.append({
                "example_id": record["id"], "source_digest": record["source_digest"],
                "publication_digest": publication, "status": "executed", "command": preset["command"],
                "exit_code": result.returncode, "executed_at": datetime.now(timezone.utc).isoformat(),
                "observed_outputs": observed,
                "output_sha256": hashlib.sha256(_json(cases[case_name]).encode("utf-8")).hexdigest(),
                "project_runtime_seconds": round(time.monotonic() - started, 6),
            })
        return receipts


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", action="append", required=True, help="trusted framework=source path")
    parser.add_argument("--index", type=Path, required=True, help="preliminary examples index")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--example", action="append", choices=tuple(ALLOWLIST), help="allowlisted showcase; repeatable")
    parser.add_argument("--timeout", type=int, default=120, help="per Project timeout, 1..300 seconds")
    args = parser.parse_args(argv)
    if not 1 <= args.timeout <= 300:
        parser.error("timeout must be between 1 and 300")
    roots = {}
    for value in args.root:
        key, separator, raw = value.partition("=")
        if not separator or key not in {"nsgablack", "mlblack", "blackbase"} or key in roots:
            parser.error("root must be a unique trusted framework=path")
        roots[key] = Path(raw).resolve()
    from nsgablack.catalog.examples import load_example_index
    index = load_example_index(args.index)
    receipts, failures = [], []
    for name in args.example or tuple(ALLOWLIST):
        try:
            receipts.extend(run_preset(name, roots, index, timeout=args.timeout))
        except (ValueError, KeyError, OSError, subprocess.TimeoutExpired) as exc:
            # Do not publish logs, arbitrary exception text or environment values.
            reason = str(exc) if type(exc) is ValueError and re.fullmatch(r"[a-z0-9_]+", str(exc)) else type(exc).__name__
            failures.append({"example": name, "error": reason})
    payload = {"schema": SCHEMA, "receipts": receipts, "failures": failures}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(_json({"executed": [row["example_id"] for row in receipts], "failures": failures}))
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
