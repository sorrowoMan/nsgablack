"""Declared mathematical fault injection; the original oracle stays immutable.

The host creates a seed, never a corrected implementation. A fresh Codex must
first test that exact seed and then repair it within the same conversation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


FAULTS = {
    "center_reflection_expansion": {
        "source": "reflection/generated.py",
        "reference_sha256": "00efd26dc2b9c72c53107b9e7f55c64db8c57a57e01b4b40fbfcf8bb88806ec8",
        "old": "np.mean(parents[:-1], axis=0)", "new": "np.mean(parents, axis=0)",
        "fault": "Centroid incorrectly includes the parent being reflected.",
    },
    "archive_maximin_survivor": {
        "source": "archive/generated.py",
        "reference_sha256": "ed28e9a185ea6502242df45ed3b0a1ab7e4cd286bd1846d811ba6da343d7903b",
        "old": "distance if previous is None else min(previous, distance)",
        "new": "distance if previous is None else max(previous, distance)",
        "fault": "Greedy coverage updates with maximum rather than minimum distance after a survivor is chosen.",
    },
}
ORACLE_FILES = ("assistant_novel_acceptance.py", "assistant_closed_loop_acceptance.py", "assistant_edit_acceptance.py")


def freeze_oracle(validation_profile="baseline"):
    from .assistant_novel_acceptance import oracle_math_sha256, spec_identity
    root = Path(__file__).parent
    result = {"oracle_math_sha256": oracle_math_sha256(), "validation_identity": spec_identity(),
              "files": {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in ORACLE_FILES}}
    if validation_profile == "archive-distance-v2":
        from . import assistant_archive_distance_acceptance as extra
        result["baseline_math_sha256"] = result["oracle_math_sha256"]
        result["baseline_validation_identity"] = result["validation_identity"]
        result.update(oracle_math_sha256=extra.oracle_math_sha256(), validation_identity=extra.spec_identity())
        name = "assistant_archive_distance_acceptance.py"
        result["files"][name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    elif validation_profile != "baseline":
        raise ValueError("unknown_validation_profile")
    return result


def prepare_distance_seed(destination, *, expected_thread_id=None):
    """Replay the exact retained, previously undetected seed; no new solution."""
    root = Path(__file__).resolve().parents[1]
    old = root / "docs/user_guide/evidence/codex-math-repair-20261124/coverage-gap"
    manifest = json.loads((old / "seed-manifest.json").read_text(encoding="utf-8"))
    raw = (old / "seed.py").read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["seed_sha256"]:
        raise ValueError("retained_coverage_gap_seed_changed")
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "seed.py").write_bytes(raw)
    manifest = {**manifest, "validation_profile": "archive-distance-v2",
                "oracle_before": freeze_oracle("archive-distance-v2"),
                "expected_thread_id": expected_thread_id,
                "prior_record_not_modified": str(old)}
    (destination / "seed-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def prepare_seed(idea_id, destination):
    fault = FAULTS[idea_id]
    source = Path(__file__).resolve().parents[1] / "docs/user_guide/evidence/codex-mcp-20261124" / fault["source"]
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != fault["reference_sha256"]:
        raise ValueError("fault_reference_source_changed")
    text = raw.decode("utf-8")
    if text.count(fault["old"]) != 1:
        raise ValueError("fault_injection_location_ambiguous")
    seed = text.replace(fault["old"], fault["new"], 1)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "seed.py").write_bytes(seed.encode("utf-8"))
    manifest = {"schema": "nsgablack.math_fault_seed/v1", "idea": idea_id, "kind": "declared_seeded_fault",
        "reference_source_sha256": fault["reference_sha256"], "seed_sha256": hashlib.sha256(seed.encode()).hexdigest(),
        "fault": fault["fault"], "single_expression_mutation": {"old": fault["old"], "new": fault["new"]},
        "oracle_before": freeze_oracle(), "host_writes_corrected_source": False,
        "seed_is_not_model_spontaneous_error": True}
    (destination / "seed-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def preflight_seed(idea_id, seed_directory):
    import tempfile
    from .assistant_codex_acceptance import _binding
    from .assistant_novel_acceptance import TARGET
    from .assistant_session_acceptance import create_teaching_project
    from .mcp_server import FrameworkWorkspace
    directory = Path(seed_directory)
    manifest = json.loads((directory / "seed-manifest.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="math-fault-preflight-") as temporary:
        sources, project_id = create_teaching_project(Path(temporary))
        workspace = FrameworkWorkspace(sources, **_binding(idea_id, manifest.get("validation_profile", "baseline")))
        opened = workspace.call("open_project", {"project_id": project_id})
        result = workspace.call("check_project_edit", {"session_id": opened["session_id"], "path": TARGET,
            "source": (directory / "seed.py").read_text(encoding="utf-8")})
    validation = result.get("validation", {})
    # Keep even an undetected seed: it is evidence about test coverage, not a
    # reason to silently strengthen or replace the frozen mathematical oracle.
    (directory / "preflight.json").write_text(json.dumps({"model_calls": 0, "not_a_model_observed_failure": True,
        "actual_result": result}, ensure_ascii=False, indent=2), encoding="utf-8")
    if not (result["code_sha256"] == manifest["seed_sha256"]
            and result["check"]["status"] != "rejected" and validation.get("status") == "failed"
            and validation.get("executed") is True and validation.get("failed_stage") == "behavior"
            and validation.get("error_type") == "AssertionError"):
        raise ValueError("seed_did_not_fail_actual_mathematical_assertion")
    if freeze_oracle(manifest.get("validation_profile", "baseline")) != manifest["oracle_before"]:
        raise ValueError("oracle_changed_during_seed_preflight")
    return result


def review_repair(output, seed_directory):
    from .assistant_codex_acceptance import review_acceptance
    from .assistant_novel_acceptance import TARGET
    output, seed_directory = Path(output), Path(seed_directory)
    manifest = json.loads((seed_directory / "seed-manifest.json").read_text(encoding="utf-8"))
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    delivery = review_acceptance(output)
    attempts = []
    forbidden = []
    for line in (output / "events.jsonl").read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        item = event.get("item", {})
        if event.get("type") != "item.completed":
            continue
        if item.get("type") == "command_execution":
            command = item.get("command", "")
            if any(token in command for token in ("assistant_novel_acceptance", "assistant_closed_loop_acceptance",
                "assistant_edit_acceptance", "assistant_archive_distance_acceptance", "codex-mcp-20261124/",
                "codex-mcp-20261124\\", "codex-math-repair-20261124", "test_assistant_novel",
                "test_assistant_archive_distance")):
                forbidden.append(command[:240])
        if (item.get("type") != "mcp_tool_call" or item.get("server") != "black-framework"
                or item.get("tool") != "check_project_edit"):
            continue
        result = (item.get("result") or {}).get("structured_content", {})
        if result.get("path") != TARGET:
            continue
        attempts.append({"source_sha256": result.get("code_sha256"),
            "static_status": result.get("check", {}).get("status"), "validation": result.get("validation", {})})
    first = attempts[0] if attempts else {}
    failed = first.get("validation", {})
    seen_failure = (first.get("source_sha256") == manifest["seed_sha256"]
        and first.get("static_status") != "rejected" and failed.get("status") == "failed"
        and failed.get("executed") is True and failed.get("failed_stage") == "behavior"
        and failed.get("error_type") == "AssertionError")
    profile = manifest.get("validation_profile", "baseline")
    frozen = freeze_oracle(profile) == manifest["oracle_before"]
    expected_thread = manifest.get("expected_thread_id")
    same_thread = (len(delivery["thread_ids"]) == 1 and
                   ((report.get("resume_thread") is None and expected_thread is None) or
                    (expected_thread is not None and report.get("resume_thread") == expected_thread
                     and delivery["thread_ids"] == [expected_thread])))
    passed = (delivery["status"] == "passed" and seen_failure and len(attempts) >= 2
        and delivery["actual_file_sha256"] != manifest["seed_sha256"] and frozen and not forbidden
        and same_thread)
    result = {"schema": "nsgablack.codex_mathematical_repair/v1", "status": "passed" if passed else "not_verified",
        "kind": "declared_seeded_fault_repair", "idea": report["idea"], "thread_ids": delivery["thread_ids"],
        "initial_model_observed_mathematical_failure": seen_failure, "oracle_unchanged": frozen,
        "validation_profile": profile, "expected_thread_id": expected_thread, "same_thread_verified": same_thread,
        "seed_sha256": manifest["seed_sha256"], "repaired_sha256": delivery["actual_file_sha256"],
        "attempts": attempts, "delivery_review": delivery, "forbidden_reference_commands": forbidden,
        "host_source_actions": "initial_fault_seed_only", "corrected_source_by_same_Codex": passed,
        "not_a_spontaneous_model_error": True}
    (output / "math-repair-review.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
