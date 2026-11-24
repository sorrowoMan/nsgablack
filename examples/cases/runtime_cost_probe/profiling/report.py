"""Analyze trusted local profiles from this diagnostic Project without loading models.

Run with ``--run-root ABSOLUTE_PATH`` after the profiled processes have exited.
Only exclusive self profile-clock time is added across groups. Inclusive boundaries and caller
edges are explanatory views of the same work and must never be added to it.
"""
from __future__ import annotations

import argparse
import ast
from functools import lru_cache
import json
from pathlib import Path
import pstats
import re
from typing import Any


GROUPS = {
    "unit_codec_runtime_capture": "Unit codec and explicit runtime state capture; self only",
    "pool_index": "SolutionPool index, references, views and transaction bookkeeping; self only",
    "pool_values": "SolutionPool value writes, verified loads and projections; self only",
    "journal_evidence_authority": "Journal, evaluation evidence semantics and Authority fencing; self only",
    "snapshot_io_digest": "Snapshot payload assembly, storage, retention I/O and digest entrypoints; self only",
    "shared_wire_copy_json": "Shared wire/protocol codecs, copying and JSON; caller ownership is not inferred",
    "domain_repair": "Production Case repair methods and repair component helpers; self only",
    "repair_coordination": "Framework repair coordination and evidence reconciliation; self only",
    "raw_problem_evaluate_constraints": "Problem.evaluate/evaluate_constraints entrypoints; shared callees are separate",
    "domain_model_support": "Other functions in domain Problem modules; not asserted to be raw evaluation time",
    "algorithm_preference": "Adapter decisions, operators, initialization, selection and Bias; self only",
    "evidence_archive_publication": "Evidence archive construction, verification, publication and release; self only",
    "cold_import": "Import machinery and module-level self work; not all transitive import time",
    "native_numpy": "NumPy Python/native functions; not assigned to a semantic caller",
    "unclassified": "Other Python/native work; not attributed to audit or model evaluation",
}
PROFILE_CLOCKS = {
    "time.thread_time": "main_thread_cpu",
    "cProfile.default_elapsed": "elapsed",
}

_POOL_VALUES = {
    "put", "_payload", "read", "_read_selection", "read_provenance", "read_raw_feedback",
    "read_raw_feedback_info",
}
_STATE_METHODS = {
    "get_state", "set_state", "snapshot_step_state", "restore_step_state", "begin_step_transaction",
    "_snapshot_algorithm_step_state", "_restore_algorithm_step_state", "capture",
}
_ARCHIVE_METHODS = {
    "iter_evaluation_evidence_archives", "_parse_archive", "archive_and_release",
    "archive_bundle_and_release", "resume_archive_release", "_archive_and_release",
    "_release_bound_event", "_bind_archive_bundle", "_verify_archive", "_release_receipt",
}
_EVENT_METHODS = {
    "record_evaluation_event", "export_evaluation_event_checkpoint_state", "get_last_evaluation_event",
    "write_evaluation_event_snapshot", "prepare_evaluation_disposition", "settle_evaluation_disposition",
    "_finalize_evaluation_disposition", "_settle_evaluation_disposition_best_effort",
    "ensure_evaluation_evidence_ready_for_next_step", "reconcile_evaluation_evidence",
    "_authority_commit_plan", "get_population_authority_identity",
}
_SNAPSHOT_METHODS = {
    "_prepare_snapshot_payload", "_persist_snapshot", "_write_snapshot_record", "write_population_snapshot",
    "write_partitioned_population_snapshot", "commit_snapshot_step_transaction", "read_snapshot",
    "candidate_batch_snapshot_payload",
}


def _normalized(filename: str) -> str:
    return filename.replace("\\", "/").lower()


@lru_cache(maxsize=256)
def _source_functions(filename: str) -> tuple[tuple[int, int, str], ...]:
    """Read source solely to distinguish methods/comprehensions sharing a file.

    No source is imported or executed. Missing/changed source falls back to the
    recorded function identity; every output retains the original profile key.
    """
    path = Path(filename)
    if not path.is_file() or path.suffix != ".py":
        return ()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, SyntaxError):
        return ()
    spans = []

    def visit(node, names=()):
        scope = names
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            scope = (*names, node.name)
            if not isinstance(node, ast.ClassDef):
                start = min([node.lineno, *(item.lineno for item in node.decorator_list)])
                spans.append((start, node.end_lineno or node.lineno, ".".join(scope)))
        for child in ast.iter_child_nodes(node):
            visit(child, scope)

    visit(tree)
    return tuple(spans)


def source_context(key: tuple[str, int, str]) -> str:
    filename, line, name = key
    if name == "<module>" or filename.startswith("<") or filename == "~":
        return name
    matches = [span for span in _source_functions(filename) if span[0] <= line <= span[1]]
    if not matches:
        return name
    return min(matches, key=lambda span: (span[1] - span[0], -span[0]))[2]


def classify_function(key: tuple[str, int, str]) -> str:
    filename, _line, name = key
    path = _normalized(filename)
    context = source_context(key)
    owner = context.rsplit(".", 1)[-1]
    if name == "<module>" or "importlib" in path or "<frozen importlib" in path:
        return "cold_import"
    if "/context/snapshot_store.py" in path:
        return "snapshot_io_digest"
    if "/core/state/solution_pool.py" in path:
        return "pool_values" if owner in _POOL_VALUES else "pool_index"
    if "/evaluation/coordinator.py" in path:
        if owner in _ARCHIVE_METHODS or "Archive" in context or "iter_evaluation_evidence_archives" in context:
            return "evidence_archive_publication"
        return "journal_evidence_authority"
    if any(part in path for part in (
        "/evaluation/journal.py", "/evaluation/event.py", "/context/authority.py", "/core/evidence_semantics.py",
    )):
        return "journal_evidence_authority"
    if "/representation/structure_builders.py" in path and (
        owner in {"encode_unit_value", "decode_unit_value", "dump", "restore"}
        or "encode_unit_value" in context or "decode_unit_value" in context
    ):
        return "unit_codec_runtime_capture"
    if (
        "/units/wire.py" in path
        or "/units/contracts.py" in path and owner in {"dump", "restore", "validate", "describe"}
        or "/blackbase/runtime.py" in path
        or "/adapters/" in path and owner in _STATE_METHODS
        or "/core/state/" in path and owner in _STATE_METHODS
    ):
        return "unit_codec_runtime_capture"
    if any(part in path for part in (
        "/context/redis_codec.py", "/blackbase/wire.py", "/blackbase/types.py", "/core/evaluation_feedback.py",
        "/copy.py", "/json/", "/units/candidate.py",
    )) or filename == "~" and ("_json." in name or "encode_basestring" in name):
        return "shared_wire_copy_json"
    if "/examples/cases/" in path and "/pipeline/" in path:
        return "domain_repair" if "repair" in context.lower() else "algorithm_preference"
    if "/core/joint_repair.py" in path or owner == "repair_candidate" and "/core/blank_solver.py" in path:
        return "repair_coordination"
    if "/examples/cases/" in path and "/problem/" in path:
        return "raw_problem_evaluate_constraints" if owner in {"evaluate", "evaluate_constraints"} else "domain_model_support"
    if owner in {"stage_evaluation_evidence_archives", "release_after_authority_seal"} and "/core/blank_solver.py" in path:
        return "evidence_archive_publication"
    if owner in _EVENT_METHODS and any(part in path for part in ("/core/blank_solver.py", "/core/composable_solver.py")):
        return "journal_evidence_authority"
    if owner in _SNAPSHOT_METHODS and "/core/" in path:
        return "snapshot_io_digest"
    if "/core/solver_helpers/snapshot_helpers.py" in path:
        return "journal_evidence_authority" if owner.startswith("validate") or owner.startswith("_validate") else "snapshot_io_digest"
    if any(part in path for part in ("/adapters/", "/bias/", "/utils/performance/", "/units/collections.py")):
        return "algorithm_preference"
    if "/numpy/" in path or filename == "~" and ("numpy" in name or "ndarray" in name):
        return "native_numpy"
    return "unclassified"


def _key_payload(key: tuple[str, int, str]) -> dict[str, Any]:
    return {"filename": key[0], "line": key[1], "function": key[2], "source_context": source_context(key)}


def _boundary_label(key: tuple[str, int, str]) -> str | None:
    path, name = _normalized(key[0]), key[2]
    if "/representation/structure_builders.py" in path and name in {"encode_unit_value", "decode_unit_value"}:
        return "unit_value_codec"
    if "/units/contracts.py" in path and name in {"dump", "restore", "validate"}:
        return "unit_binding_codec_validation"
    if "/blackbase/runtime.py" in path and name == "capture_runtime_snapshot":
        return "runtime_participant_capture"
    if "/core/state/solution_pool.py" in path and name in {
        "prepare_publication", "_index_state", "_restore_index", "_payload", "_read_selection", "put",
    }:
        return "pool_" + name.lstrip("_")
    if "/evaluation/journal.py" in path and name in {"list_unresolved", "_backfill_unresolved", "_atomic_update"}:
        return "journal_" + name.lstrip("_")
    if "/core/joint_repair.py" in path and name in {"repair_problem_batch", "coordinate_joint_repair"}:
        return "framework_" + name
    if "/examples/cases/" in path and "/pipeline/" in path and name == "repair":
        return "domain_repair"
    if "/examples/cases/" in path and "/problem/" in path and name in {"evaluate", "evaluate_constraints"}:
        return "raw_problem_" + name
    if "/core/blank_solver.py" in path and name in {
        "write_evaluation_event_snapshot", "export_evaluation_event_checkpoint_state", "_prepare_snapshot_payload",
        "_write_snapshot_record", "commit_snapshot_step_transaction", "stage_evaluation_evidence_archives",
        "evaluate_population", "evaluate_individual",
    }:
        return "solver_" + name.lstrip("_")
    if "/core/evidence_semantics.py" in path and name in {"inspect_event", "_inspect_evaluation_disposition_destination"}:
        return "evidence_" + name.lstrip("_")
    if "/evaluation/coordinator.py" in path and name in {
        "confirm_event", "settle_decision", "_pin_identities", "iter_evaluation_evidence_archives",
        "archive_bundle_and_release", "archive_and_release",
    }:
        return "coordinator_" + name.lstrip("_")
    if "/context/snapshot_store.py" in path and name in {
        "read_verified", "snapshot_content_digest", "_prepare_snapshot_payload", "read", "write",
    }:
        return "snapshot_" + name.lstrip("_")
    if "/context/authority.py" in path and name == "commit":
        return "authority_commit"
    if "importlib" in path and name in {"_find_and_load", "_find_and_load_unlocked"}:
        return "cold_import_boundary"
    return None


def analyze_profile(profile_path: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    stats = pstats.Stats(str(profile_path))
    total = sum(entry[2] for entry in stats.stats.values())
    groups = {key: {"self_profile_clock_seconds": 0.0, "function_count": 0, "total_calls": 0} for key in GROUPS}
    functions, boundaries, edges = [], [], []
    for key, (primitive_calls, calls, self_seconds, inclusive_seconds, callers) in stats.stats.items():
        group = classify_function(key)
        bucket = groups[group]
        bucket["self_profile_clock_seconds"] += self_seconds
        bucket["function_count"] += 1
        bucket["total_calls"] += calls
        row = {**_key_payload(key), "group": group, "primitive_calls": primitive_calls,
               "total_calls": calls, "self_profile_clock_seconds": self_seconds,
               "inclusive_profile_clock_seconds_non_additive": inclusive_seconds,
               "fraction_of_profile_self": self_seconds / total if total else 0.0}
        local_edges = []
        for caller, timing in callers.items():
            if not isinstance(timing, tuple) or len(timing) != 4:
                raise ValueError("Expected cProfile four-field caller timing")
            edge = {"caller": _key_payload(caller), "callee": _key_payload(key),
                    "primitive_calls": timing[0], "total_calls": timing[1],
                    "callee_self_profile_clock_seconds": timing[2],
                    "inclusive_profile_clock_seconds_non_additive": timing[3]}
            edges.append(edge)
            local_edges.append(edge)
        row["top_callers_non_additive"] = sorted(
            local_edges, key=lambda edge: edge["inclusive_profile_clock_seconds_non_additive"], reverse=True,
        )[:3]
        functions.append(row)
        label = _boundary_label(key)
        if label is not None:
            boundaries.append({"boundary": label, **row})
    group_rows = []
    for name, values in groups.items():
        fraction = values["self_profile_clock_seconds"] / total if total else 0.0
        group_rows.append({"group": name, "description": GROUPS[name], **values,
                           "fraction_of_profile_self": fraction, "percent_of_profile_self": 100 * fraction})
    return {
        "pid": metadata["pid"], "metadata": metadata, "profile_path": str(profile_path.resolve()),
        "profile_timer": metadata["timer"], "profile_clock_kind": PROFILE_CLOCKS[metadata["timer"]],
        "total_self_profile_clock_seconds": total,
        "grouped_self_profile_clock_seconds": sum(row["self_profile_clock_seconds"] for row in group_rows),
        "self_groups": sorted(group_rows, key=lambda row: row["self_profile_clock_seconds"], reverse=True),
        "top20_self": sorted(functions, key=lambda row: row["self_profile_clock_seconds"], reverse=True)[:20],
        "key_boundaries_non_additive": sorted(
            boundaries, key=lambda row: row["inclusive_profile_clock_seconds_non_additive"], reverse=True,
        ),
        "top20_caller_callee_edges_non_additive": sorted(
            edges, key=lambda edge: edge["inclusive_profile_clock_seconds_non_additive"], reverse=True,
        )[:20],
    }


def analyze_run(run_root: str | Path) -> dict[str, Any]:
    root = Path(run_root)
    if not root.is_absolute():
        raise ValueError("--run-root must be an absolute local directory")
    root = root.resolve(strict=True)
    profiles = root / "profiles"
    paths = sorted(profiles.glob("process-*.prof"))
    if not paths:
        raise ValueError("No process-PID.prof files found under run-root/profiles")
    results = []
    for path in paths:
        match = re.fullmatch(r"process-([0-9]+)\.prof", path.name)
        if match is None:
            raise ValueError(f"Unexpected process profile filename: {path.name}")
        metadata_path = path.with_suffix(".json")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
        if not isinstance(metadata, dict) or metadata.get("pid") != int(match.group(1)):
            raise ValueError(f"Profile PID disagrees with metadata: {path.name}")
        if metadata.get("timer") not in PROFILE_CLOCKS:
            raise ValueError(f"Unsupported profile timer: {path.name}")
        result = analyze_profile(path, metadata)
        result["metadata_path"] = str(metadata_path.resolve())
        results.append(result)
    return {
        "schema": "runtime_cost_probe.profile_analysis/v1", "run_root": str(root),
        "clock": "per-process metadata.timer", "profile_timers": sorted({row["profile_timer"] for row in results}),
        "coverage": "main thread of each listed process only",
        "interpretation": [
            "self_groups partition profile-clock self time exactly; fractions use total_self_profile_clock_seconds, not CPU or wall metadata",
            "inclusive boundaries, caller edges and top-function views overlap and must not be added to self groups",
            "process CPU and wall metadata include work outside profiler coverage; no missing CPU is assigned to audit",
            "default_elapsed self includes elapsed waits; it is not CPU time, and profiled runs are not uninstrumented baselines",
            "shared codecs, copying, JSON and native NumPy are not assigned to their semantic caller by flat self data",
            "raw Problem entrypoint self excludes its callees; inclusive evaluate and constraints can also overlap",
            "Problem.evaluate can include nested Case orchestration or waits; inclusive boundaries are not a separately timed raw-dispatch measurement",
            "cold_import is exclusive import machinery/module self, not the complete transitive cold-start cost",
            "source_context is a best-effort read of local source; original filename/line/function remain authoritative",
            "inputs are trusted local profiles from this run; no models are imported or executed by this analyzer",
        ],
        "processes": sorted(results, key=lambda row: row["pid"]),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True, help="Absolute directory containing profiles/process-PID.prof and .json")
    args = parser.parse_args(argv)
    try:
        report = analyze_run(args.run_root)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    target = Path(report["run_root"]) / "profile_analysis.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    print(json.dumps({"profile_analysis": str(target), "process_count": len(report["processes"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
