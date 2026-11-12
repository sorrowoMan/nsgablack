#!/usr/bin/env python3
"""Explicit, resumable completion of one frozen Catalog (not the timer quota).

Only a fresh exact-store probe can finish this job.  Provider calls stay in the
adjacent completion_worker; this host owns reservations and private diagnostics.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from functools import partial
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import signal
import time
import uuid


SCHEMA = "nsgablack.catalog.completion_job/v1"
REPORT_SCHEMA = "nsgablack.catalog.completion_report/v1"
TOTAL, MAX_ATTEMPTS, BATCH_LIMIT = 557, 3, 20
MAX_JSON_BYTES = 8 * 1024 * 1024
AUTH_ERRORS = {"ai_http_401", "ai_http_402", "ai_http_403"}
_SECRET = re.compile(
    r"-----BEGIN .*PRIVATE KEY-----|\bsk-[A-Za-z0-9_-]{8,}|\bAKIA[A-Z0-9]{16}|"
    r"\bghp_[A-Za-z0-9]{20,}|\bxox[baprs]-[A-Za-z0-9-]{16,}|"
    r"(?:authorization|api[_ -]?key|password|passwd|access_token)\s*[:=]|"
    r"(?:mysql|postgres(?:ql)?)://", re.I)
_DIAGNOSTIC_NUMBERS = (
    "prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens",
    "content_chars", "content_non_whitespace_chars", "reasoning_chars")
_FINISH_REASONS = {"stop", "length", "content_filter", "tool_calls", "unknown",
                   "insufficient_system_resource", "aborted"}


def sibling(name):
    path = Path(__file__).resolve().with_name(name + ".py")
    spec = importlib.util.spec_from_file_location("catalog_completion_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CompletionError(RuntimeError):
    """Fixed categories only; never print a subprocess or provider exception."""


def write_json(path, value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(encoded) > MAX_JSON_BYTES:
        raise CompletionError("job_json_oversized")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex)
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path):
    if path.stat().st_size > MAX_JSON_BYTES:
        raise CompletionError("job_json_oversized")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError):
        raise CompletionError("job_json_invalid") from None


def safe_text(value, limit=2000):
    return value.strip() if (isinstance(value, str) and value.strip()
                            and len(value) <= limit and not _SECRET.search(value)) else None


def safe_failure(row):
    """Keep actual, bounded correction findings; never arbitrary worker fields."""
    category = row.get("error")
    known = {"note_evidence_validation_failed", "batch_cancelled", "ai_config_invalid",
             "ai_redirect_refused", "ai_packet_too_large", "ai_transport_failed",
             "ai_response_incomplete", "ai_response_invalid", "worker_interrupted",
             "ai_review_format_invalid", "ai_review_format_discarded_findings",
             "worker_failed", "batch_report_invalid", "outcome_unknown",
             "store_not_visible", "docker_timeout", "KnowledgeStoreError", "KnowledgeConflictError",
             "KnowledgeReadOnlyError", "KnowledgeUnavailableError", "ValueError",
             "TypeError", "RuntimeError", "TimeoutError",
             "completion_image_invalid", "completion_identity_invalid", "completion_directory_invalid",
             "completion_job_image_mismatch", "completion_keys_invalid", "completion_release_changed",
             "completion_frozen_identity_mismatch", "completion_worker_create_failed",
             "completion_worker_output_oversized", "completion_worker_report_invalid",
             "completion_worker_exit_failed", "completion_request_invalid"}
    category = category if (isinstance(category, str) and
                           (category in known or re.fullmatch(r"ai_http_[1-5][0-9]{2}", category))) else "worker_failed"
    value = {"error": category}
    if row.get("provider_phase") in {"generate", "review"}:
        value["provider_phase"] = row["provider_phase"]
    issue = safe_text(row.get("validation_issue"), 4000)
    if issue:
        value["validation_issue"] = issue
    raw = row.get("provider_diagnostics")
    if isinstance(raw, dict):
        diagnostics = {key: raw[key] for key in _DIAGNOSTIC_NUMBERS
                       if type(raw.get(key)) is int and 0 <= raw[key] <= 1_000_000}
        if raw.get("finish_reason") in _FINISH_REASONS:
            diagnostics["finish_reason"] = raw["finish_reason"]
        if diagnostics:
            value["provider_diagnostics"] = diagnostics
    review = row.get("source_review")
    if isinstance(review, dict) and review.get("decision") in {"publish", "revise", "insufficient_evidence"}:
        def ids(values):
            return [item for item in values if isinstance(item, str) and re.fullmatch(r"e[0-9]{1,5}", item)][:32] if isinstance(values, list) else []
        issues = []
        for item in review.get("issues", [])[:12] if isinstance(review.get("issues"), list) else []:
            if not isinstance(item, dict):
                continue
            texts = {key: safe_text(item.get(key)) for key in ("location", "problem", "required_change")}
            if all(texts.values()):
                issues.append({**texts, "evidence_ids": ids(item.get("evidence_ids"))})
        checks = [text for item in review.get("checks", [])[:12] if (text := safe_text(item))] if isinstance(review.get("checks"), list) else []
        value["source_review"] = {"decision": review["decision"], "issues": issues,
                                  "checks": checks, "evidence_ids": ids(review.get("evidence_ids"))}
        version = review.get("version")
        if isinstance(version, str) and re.fullmatch(r"[A-Za-z0-9._/-]{1,128}", version):
            value["source_review"]["version"] = version
    return value


def identity_snapshot(probe, image):
    return {"image_id": image, "model": probe["model"], "prompt": probe["prompt"],
            "source_index_sha256": probe["source_index_sha256"],
            "entries": {entry["key"]: entry["digest"] for entry in probe["entries"]}}


def check_identity(job, probe, image):
    if identity_snapshot(probe, image) != job["identity"]:
        raise CompletionError("identity_changed")


def load_job(path, *, job_id, max_items, expected_total):
    value = read_json(path)
    if (not isinstance(value, dict) or value.get("schema") != SCHEMA or value.get("job_id") != job_id
            or value.get("max_items") != max_items or value.get("expected_total") != expected_total
            or value.get("max_attempts") != MAX_ATTEMPTS or not isinstance(value.get("targets"), dict)
            or len(value["targets"]) > max_items or type(value.get("reserved")) is not int
            or not 0 <= value["reserved"] <= max_items * MAX_ATTEMPTS):
        raise CompletionError("job_state_invalid")
    attempts = 0
    for key, item in value["targets"].items():
        if (not re.fullmatch(r"[A-Za-z0-9_.-]{1,200}", key) or not isinstance(item, dict)
                or type(item.get("attempts")) is not int or not 0 <= item["attempts"] <= MAX_ATTEMPTS
                or not isinstance(item.get("next"), (int, float)) or not math.isfinite(item["next"])
                or not re.fullmatch(r"[0-9a-f]{64}", str(item.get("digest")))):
            raise CompletionError("job_state_invalid")
        attempts += item["attempts"]
    if attempts != value["reserved"] or not isinstance(value.get("round_plan"), list):
        raise CompletionError("job_state_invalid")
    if len(set(value["round_plan"])) != len(value["round_plan"]) or set(value["round_plan"]) - set(value["targets"]):
        raise CompletionError("job_state_invalid")
    frozen_entries = value.get("identity", {}).get("entries", {})
    if any(frozen_entries.get(key) != item["digest"] for key, item in value["targets"].items()):
        raise CompletionError("job_state_invalid")
    return value


def job_status(job, probe, status, now, *, next_at=None):
    current = sum(entry["cached"] for entry in probe["entries"])
    return {"job_id": job["job_id"], "status": status, "complete": status == "complete",
            "total": len(probe["entries"]), "current": current,
            "remaining": len(probe["entries"]) - current, "reserved": job["reserved"],
            "max_attempts": MAX_ATTEMPTS, "checked_at": now, "next_eligible_at": next_at,
            "ordinary_reserved_at_start": job["ordinary_at_start"]["reserved"]}


def publish_progress(root, auto, job, probe, result):
    """Publish only the original reader allowlist, never the ordinary ledger."""
    if identity_snapshot(probe, job["identity"]["image_id"]) != job["identity"]:
        return  # A new release cannot borrow this job's source identity.
    status = result["status"]
    exact = (len(probe["entries"]) == job["expected_total"]
             and all(entry["cached"] for entry in probe["entries"]))
    if status == "complete" and not exact:
        status = "partial"
    elif status != "complete" and exact:
        # The reader also uses current==total for its completion message. Wait
        # for the job's independent confirming probe before exposing that state.
        return
    status = {"running": "catching_up", "auth_blocked": "circuit_open",
              "attempt_limit": "partial", "item_limit": "partial"}.get(status, status)
    if status not in {"complete", "catching_up", "circuit_open", "backoff", "awaiting_evidence", "partial"}:
        status = "partial"
    value = {"release": job["release"], "image_id": job["identity"]["image_id"],
             "source_index_sha256": job["identity"]["source_index_sha256"],
             "prompt_version": job["identity"]["prompt"],
             "checked_at": datetime.fromtimestamp(result["checked_at"], timezone.utc).isoformat(),
             "total": result["total"], "current": result["current"], "remaining": result["remaining"],
             "selected": job["reserved"],
             "generated": sum(item["status"] == "reported_saved" for item in job["targets"].values()),
             "failed": sum(item["status"] in {"failed", "outcome_unknown"} for item in job["targets"].values()),
             "daily_limit": auto.DAILY_LIMIT,
             "reserved_today": job["ordinary_at_start"]["reserved"] + job["reserved"],
             "status": status, "next_eligible_at": result["next_eligible_at"],
             "circuit_until": job["circuit_until"]}
    directory = root / "automation/progress"
    directory.mkdir(mode=0o755, parents=True, exist_ok=True)
    os.chmod(directory, 0o755)
    auto.atomic_json(directory / "progress.json", auto.public_progress(value), mode=0o644)


def report_identity(job):
    return {name: value for name, value in job["identity"].items() if name != "entries"}


def retry_feedback(directory, key, item, job):
    fallback = item.get("last_failure")
    reference = item.get("last_report_ref", "")
    if fallback and re.fullmatch(r"reports/batch-[0-9]{5}\.driver\.json", reference):
        report = read_json(directory / reference)
        if (report.get("identity") != report_identity(job) or report.get("job_id") != job["job_id"]
                or report.get("batch_id") != item.get("last_batch")):
            raise CompletionError("feedback_identity_mismatch")
        for row in report.get("results", []):
            if row.get("entry_key") == key and row.get("error") == fallback["error"]:
                return safe_failure(row)
    return fallback


def recover_reserved(job, directory, now):
    """A killed worker never refunds a reservation or invents a successful row."""
    for batch in job["batches"]:
        if batch["report_ref"] is not None:
            continue
        report_path = directory / "reports" / (batch["id"] + ".driver.json")
        report = {"schema": REPORT_SCHEMA, "job_id": job["job_id"], "batch_id": batch["id"],
                  "identity": report_identity(job), "finished_at": now,
                  "results": [{"entry_key": key, "error": "worker_interrupted"} for key in batch["keys"]]}
        if report_path.exists():
            existing = read_json(report_path)
            if (existing.get("identity") != report_identity(job) or existing.get("job_id") != job["job_id"]
                    or existing.get("batch_id") != batch["id"]):
                raise CompletionError("feedback_identity_mismatch")
            report = existing
        else:
            private_path = directory / "reports" / (batch["id"] + ".worker.json")
            if private_path.is_file():
                private = read_json(private_path)
                expected = {"job_id": job["job_id"], "batch_id": batch["id"], "identity": job["identity"]}
                if private.get("completion") == expected and isinstance(private.get("results"), list):
                    rows, seen = {}, set()
                    for row in private["results"]:
                        key = row.get("entry_key") if isinstance(row, dict) else None
                        if (key not in batch["keys"] or key in seen
                                or row.get("source_digest", job["identity"]["entries"][key]) != job["identity"]["entries"][key]):
                            raise CompletionError("batch_report_invalid")
                        seen.add(key)
                        rows[key] = row
                    report["results"] = [
                        {"entry_key": key, **safe_failure(rows.get(key, {"error": "outcome_unknown"}))}
                        if key not in rows or "error" in rows[key] else {"entry_key": key, "status": "reported_saved"}
                        for key in batch["keys"]]
                    batch["worker_report_ref"] = "reports/" + private_path.name
            write_json(report_path, report)
        batch["report_ref"] = "reports/" + report_path.name
        for row in report["results"]:
            key = row["entry_key"]
            if key not in batch["keys"]:
                raise CompletionError("batch_report_invalid")
            item = job["targets"][key]
            item["last_report_ref"] = batch["report_ref"]
            if "error" in row:
                item["status"] = "outcome_unknown"
                item["last_failure"] = {"error": safe_failure(row)["error"]}
                if row["error"] in AUTH_ERRORS:
                    job["circuit_until"] = max(job["circuit_until"], now + 86400)
            else:
                item["status"] = "reported_saved"
                item.pop("last_failure", None)


def check_arguments(job_id, max_items, expected_total, batch_limit, max_batches):
    if (not isinstance(job_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", job_id)
            or type(max_items) is not int or not 1 <= max_items <= TOTAL
            or type(batch_limit) is not int or not 1 <= batch_limit <= BATCH_LIMIT
            or type(expected_total) is not int or not 1 <= expected_total <= TOTAL
            or type(max_batches) is not int or not 1 <= max_batches <= TOTAL * MAX_ATTEMPTS):
        raise CompletionError("job_arguments_invalid")


def plan_job(root, *, job_id, max_items=TOTAL, expected_total=TOTAL,
             batch_limit=BATCH_LIMIT, max_batches=1, now=None):
    """Read a local ledger only: no probe, credentials, reservation or writer."""
    check_arguments(job_id, max_items, expected_total, batch_limit, max_batches)
    path = root / "automation/state/completions" / job_id / "job.json"
    result = {"job_id": job_id, "status": "plan", "complete": False,
              "execute_required": True, "max_items": max_items,
              "max_attempts": MAX_ATTEMPTS, "batch_limit": batch_limit,
              "max_batches": max_batches, "batches_executed": 0,
              "reservation_upper_bound": min(max_items * MAX_ATTEMPTS, batch_limit * max_batches),
              "fresh_probe_required": True, "ledger_exists": path.is_file()}
    if not path.is_file():
        result["reason"] = "execution_will_probe_and_freeze_targets"
        return result
    job = load_job(path, job_id=job_id, max_items=max_items, expected_total=expected_total)
    moment = time.time() if now is None else now
    candidates = {key: item for key, item in job["targets"].items()
                  if item["attempts"] < MAX_ATTEMPTS and item["next"] <= moment}
    order = [key for key in job["round_plan"] if key in candidates]
    if not job["round_plan"]:
        order = sorted(candidates)
    result.update(reserved=job["reserved"], identity=report_identity(job),
                  observed_status=job.get("last_status"),
                  candidate_keys_before_probe=order[:batch_limit])
    return result


def run_job(root, *, job_id, max_items=TOTAL, expected_total=TOTAL, batch_limit=BATCH_LIMIT,
            now=None, docker=None, worker=None, execute=False, max_batches=1):
    """Plan by default; explicit execution submits at most max_batches batches.

    Tests may inject a non-network Docker and worker. An incomplete run returns
    its stopping reason; a later explicit invocation resumes this exact ledger.
    The executing CLI holds worker.lock across this call.
    """
    check_arguments(job_id, max_items, expected_total, batch_limit, max_batches)
    if execute is not True:
        return plan_job(root, job_id=job_id, max_items=max_items, expected_total=expected_total,
                        batch_limit=batch_limit, max_batches=max_batches, now=now)
    clock = time.time if now is None else lambda: now
    batches_executed = 0
    auto = sibling("auto_curate")
    docker = docker or auto.Docker(root)
    directory = root / "automation/state/completions" / job_id
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = directory / "job.json"
    image, release = docker.image()
    probe = auto.validate_probe(docker.run(image, probe=True))
    ordinary_path = root / "automation/state/state.json"
    ordinary = auto.read_state(ordinary_path)
    if path.exists():
        job = load_job(path, job_id=job_id, max_items=max_items, expected_total=expected_total)
        try:
            check_identity(job, probe, image)
        except CompletionError:
            job["last_error"] = "identity_changed"
            job["last_status"] = job_status(job, probe, "identity_changed", clock())
            write_json(path, job)
            raise
    else:
        if len(probe["entries"]) != expected_total:
            raise CompletionError("catalog_total_mismatch")
        pending = sorted((item for item in probe["entries"] if not item["cached"]), key=lambda item: item["key"])[:max_items]
        job = {"schema": SCHEMA, "job_id": job_id, "max_items": max_items,
               "max_attempts": MAX_ATTEMPTS, "expected_total": expected_total,
               "identity": identity_snapshot(probe, image), "release": release,
               "created_at": clock(), "reserved": 0, "round": 0, "round_plan": [], "batches": [],
               "ordinary_at_start": {"reserved": ordinary["reserved"],
                   "catchup_reserved": ordinary.get("catchup_reserved", 0), "budget_day": ordinary["budget_day"],
                   "state_sha256": hashlib.sha256(ordinary_path.read_bytes()).hexdigest() if ordinary_path.exists() else None},
               "circuit_until": ordinary["circuit_until"],
               "targets": {item["key"]: {"digest": item["digest"], "attempts": 0, "status": "pending",
                   "next": ordinary["failures"].get(auto.identity(item, probe), {}).get("next", 0)} for item in pending}}
        write_json(path, job)

    def save(status, next_at=None):
        result = job_status(job, probe, status, clock(), next_at=next_at)
        result.update(batches_executed=batches_executed, max_batches=max_batches)
        job["last_status"] = result
        write_json(path, job)
        publish_progress(root, auto, job, probe, result)
        return result

    def fresh_probe():
        active, _ = docker.image()
        if active != image:
            raise CompletionError("identity_changed")
        updated = auto.validate_probe(docker.run(image, probe=True))
        check_identity(job, updated, active)
        if docker.image()[0] != image:
            raise CompletionError("identity_changed")
        return updated

    try:
        # Never give a crash its reservation back. Absence of a report is not
        # evidence that a remote, potentially billed request did not run.
        recover_reserved(job, directory, clock())
        save("running")
        while True:
            if all(item["cached"] for item in probe["entries"]):
                probe = fresh_probe()  # Reported writes and earlier reads never substitute for this.
                if all(item["cached"] for item in probe["entries"]) and len(probe["entries"]) == expected_total:
                    return save("complete")
            missing = {item["key"]: item for item in probe["entries"] if not item["cached"]}
            if max(job["circuit_until"], ordinary["circuit_until"]) > clock():
                return save("auth_blocked", max(job["circuit_until"], ordinary["circuit_until"]))
            candidates = {key: item for key, item in job["targets"].items()
                          if key in missing and missing[key]["evidence"] and item["attempts"] < MAX_ATTEMPTS}
            # Finish this frozen round before any identity can be attempted again.
            job["round_plan"] = [key for key in job["round_plan"] if key in candidates]
            if not job["round_plan"]:
                eligible = sorted(key for key, item in candidates.items() if item["next"] <= clock())
                if eligible:
                    job["round"] += 1
                    job["round_plan"] = eligible
            selected = [key for key in job["round_plan"] if candidates[key]["next"] <= clock()][:batch_limit]
            if not selected:
                if candidates:
                    return save("backoff", min(item["next"] for item in candidates.values()))
                if any(not item["evidence"] for item in missing.values()):
                    return save("awaiting_evidence")
                if any(key not in job["targets"] for key in missing):
                    return save("item_limit")
                return save("attempt_limit")
            if batches_executed >= max_batches:
                return save("batch_limit")
            probe = fresh_probe()  # Guard immediately before every paid batch.
            visibility = {item["key"]: item["cached"] for item in probe["entries"]}
            if any(visibility[key] for key in selected):
                continue  # An independently published current row must not be regenerated.
            batch_id = f"batch-{len(job['batches']) + 1:05d}"
            feedback = {key: retry_feedback(directory, key, job["targets"][key], job) for key in selected
                        if job["targets"][key].get("last_failure")}
            for key in selected:
                item = job["targets"][key]
                item["attempts"] += 1
                item.update(status="reserved", last_batch=batch_id, last_attempt_at=clock(),
                            next=clock() + 900 * 2 ** (item["attempts"] - 1))
                job["round_plan"].remove(key)
            job["reserved"] += len(selected)
            batch = {"id": batch_id, "round": job["round"], "keys": selected,
                     "reserved_at": clock(), "report_ref": None}
            job["batches"].append(batch)
            save("running")  # Durable before invoking the worker, including its failures.
            batches_executed += 1
            try:
                execute_batch = worker if worker is not None else partial(sibling("completion_worker").run, execute=True)
                report_dir = directory / "reports"
                report_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
                raw = execute_batch(image, keys=selected, feedback=feedback, report_dir=report_dir,
                                    job_id=job_id, batch_id=batch_id)
                rows = raw.get("results") if isinstance(raw, dict) else None
                if not isinstance(rows, list):
                    raise CompletionError("batch_report_invalid")
                seen = set()
                for row in rows:
                    key = row.get("entry_key") if isinstance(row, dict) else None
                    if key not in selected or key in seen:
                        raise CompletionError("batch_report_invalid")
                    seen.add(key)
                by_key = {row["entry_key"]: row for row in rows}
                safe_rows = [{"entry_key": key, **safe_failure(by_key.get(key, {"error": "outcome_unknown"}))}
                             if key not in by_key or "error" in by_key[key]
                             else {"entry_key": key, "status": "reported_saved"} for key in selected]
            except Exception as exc:
                category = str(exc) if isinstance(exc, CompletionError) or type(exc).__name__ in {"SchedulerError", "CompletionWorkerError"} else "worker_failed"
                safe_rows = [{"entry_key": key, **safe_failure({"error": category})} for key in selected]
            report = {"schema": REPORT_SCHEMA, "job_id": job_id, "batch_id": batch_id,
                      "identity": report_identity(job),
                      "finished_at": clock(), "results": safe_rows}
            report_path = directory / "reports" / (batch_id + ".driver.json")
            write_json(report_path, report)
            batch["report_ref"] = "reports/" + report_path.name
            if (directory / "reports" / (batch_id + ".worker.json")).is_file():
                batch["worker_report_ref"] = "reports/" + batch_id + ".worker.json"
            for row in safe_rows:
                item = job["targets"][row["entry_key"]]
                item["last_report_ref"] = batch["report_ref"]
                if "error" in row:
                    item["status"] = "failed"
                    # Keep only a small index in the job; full feedback is read
                    # from its immutable batch report before the next attempt.
                    item["last_failure"] = {"error": row["error"]}
                    if row["error"] in AUTH_ERRORS:
                        job["circuit_until"] = clock() + 86400
                else:
                    item["status"] = "reported_saved"
                    item.pop("last_failure", None)
            save("running")
            if any(row.get("error") in {"completion_frozen_identity_mismatch", "completion_release_changed",
                                         "completion_job_image_mismatch"} for row in safe_rows):
                raise CompletionError("identity_changed")
            probe = fresh_probe()
            for row in safe_rows:
                key = row["entry_key"]
                if "error" not in row and not next(item for item in probe["entries"] if item["key"] == key)["cached"]:
                    job["targets"][key]["last_failure"] = {"error": "store_not_visible"}
                    job["targets"][key]["status"] = "failed"
            save("running")
    except BaseException as exc:
        category = str(exc) if isinstance(exc, CompletionError) else "interrupted" if isinstance(exc, KeyboardInterrupt) else "driver_failed"
        job["last_error"] = category
        recover_reserved(job, directory, clock())
        save(category)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/opt/framework-catalog"))
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--max-items", type=int, default=TOTAL)
    parser.add_argument("--execute", action="store_true", help="explicitly authorize paid batches for this invocation")
    parser.add_argument("--max-batches", type=int, default=1, help="maximum batches this invocation may submit (default: 1)")
    parser.add_argument("--wait-seconds", type=int, default=0)
    args = parser.parse_args(argv)
    if not 0 <= args.wait_seconds <= 86400:
        parser.error("--wait-seconds must be 0..86400")
    lock = None
    try:
        check_arguments(args.job_id, args.max_items, TOTAL, BATCH_LIMIT, args.max_batches)
        if not args.execute:
            print(json.dumps(plan_job(args.root, job_id=args.job_id, max_items=args.max_items,
                                      max_batches=args.max_batches), ensure_ascii=False), flush=True)
            return 0
        if not hasattr(os, "geteuid") or os.geteuid() != 0:
            raise CompletionError("root_required")
        import fcntl
        os.umask(0o077)
        directory = args.root / "automation/state"
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        lock = (directory / "worker.lock").open("a")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise CompletionError("already_running") from None
        def interrupted(signum, frame):
            raise KeyboardInterrupt()
        signal.signal(signal.SIGTERM, interrupted)
        signal.signal(signal.SIGINT, interrupted)
        deadline = time.monotonic() + args.wait_seconds
        batches_left = args.max_batches
        while True:
            result = run_job(args.root, job_id=args.job_id, max_items=args.max_items,
                             execute=True, max_batches=batches_left)
            batches_left -= result.get("batches_executed", 0)
            print(json.dumps(result, ensure_ascii=False), flush=True)
            if result["complete"]:
                return 0
            if batches_left <= 0 or result["status"] != "backoff" or time.monotonic() >= deadline:
                return 2
            delay = max(1, result["next_eligible_at"] - time.time())
            time.sleep(min(60, delay, max(0, deadline - time.monotonic())))
    except BaseException as exc:
        category = str(exc) if isinstance(exc, CompletionError) else "interrupted" if isinstance(exc, KeyboardInterrupt) else "driver_failed"
        print(json.dumps({"complete": False, "status": category}), flush=True)
        return 2
    finally:
        if lock is not None:
            lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
