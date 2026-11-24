"""Trusted workbench guidance and bounded, read-only conversation context."""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
import math
from pathlib import Path
import re

GUIDE_ID = "framework-experiment-guide"
GUIDE_VERSION = "4"
STAGES = ("problem", "assembly", "results")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_PATH = Path(__file__).with_name("skills") / GUIDE_ID / "SKILL.md"


def read_guide() -> dict:
    """Only this packaged source is loaded; no user-selected file is read."""
    data = _PATH.read_bytes()
    if not 100 < len(data) <= 24000:
        raise ValueError("guide_source_invalid")
    source = data.decode("utf-8-sig")
    if not source.startswith("---\n") or "\n---\n" not in source[4:]:
        # Windows checkouts may use CRLF, but the digest retains exact bytes.
        source = source.replace("\r\n", "\n")
    header, separator, content = source[4:].partition("\n---\n")
    if not separator or f"name: {GUIDE_ID}" not in header or not content.strip():
        raise ValueError("guide_source_invalid")
    return {"content": content.strip(), "metadata": {
        "id": GUIDE_ID, "version": GUIDE_VERSION,
        "sha256": hashlib.sha256(data).hexdigest(), "stages": list(STAGES)}}


def normalize_guide_context(value=None, *, base_digest=None) -> dict:
    """Reject unknown context surfaces; chat never carries commands or raw logs."""
    if value is None:
        value = {}
    if not isinstance(value, Mapping) or set(value) - {"stage", "history", "trial", "design_notes"}:
        raise ValueError("guide_context_invalid")
    from .lab_design import normalize_notes
    notes = normalize_notes(value.get("design_notes", ""))
    stage = value.get("stage", "problem")
    if stage not in STAGES:
        raise ValueError("guide_stage_invalid")
    history = value.get("history", [])
    if not isinstance(history, list) or len(history) > 6:
        raise ValueError("guide_history_invalid")
    turns = []
    for row in history:
        if (not isinstance(row, Mapping) or set(row) != {"role", "content"}
                or row["role"] not in {"user", "assistant"}
                or not isinstance(row["content"], str) or not 1 <= len(row["content"]) <= 600):
            raise ValueError("guide_history_invalid")
        turns.append({"role": row["role"], "content": row["content"]})
    trial = value.get("trial")
    if trial is not None:
        allowed = {"status", "spec_digest", "matches_current", "steps", "evaluations",
                   "plan_completed", "error", "best_raw_sum", "feasible_count", "best_feasible_objective"}
        required = {"status", "spec_digest", "matches_current", "steps", "evaluations", "plan_completed"}
        if (not isinstance(trial, Mapping) or set(trial) - allowed or required - set(trial)
                or trial["status"] not in {"queued", "running", "succeeded", "failed"}
                or not isinstance(trial["spec_digest"], str) or not _DIGEST.fullmatch(trial["spec_digest"])
                or type(trial["matches_current"]) is not bool
                or trial["plan_completed"] is not None and type(trial["plan_completed"]) is not bool):
            raise ValueError("guide_trial_invalid")
        if base_digest is not None and trial["matches_current"] != (trial["spec_digest"] == base_digest):
            raise ValueError("guide_trial_identity_mismatch")
        for name in ("steps", "evaluations"):
            count = trial[name]
            if count is not None and (type(count) is not int or not 0 <= count <= 10**12):
                raise ValueError("guide_trial_invalid")
        trial = {key: trial[key] for key in required}
        extra = value["trial"]
        if "error" in extra and extra["error"] is not None:
            error = extra["error"]
            if (not isinstance(error, Mapping) or set(error) != {"code", "message"}
                    or any(not isinstance(error[k], str) or len(error[k]) > n
                           for k, n in (("code", 80), ("message", 320)))):
                raise ValueError("guide_trial_invalid")
            trial["error"] = dict(error)
        if "best_raw_sum" in extra and extra["best_raw_sum"] is not None:
            best = extra["best_raw_sum"]
            if type(best) not in (int, float) or not math.isfinite(best):
                raise ValueError("guide_trial_invalid")
            trial["best_raw_sum"] = float(best)
        if "feasible_count" in extra:
            count = extra["feasible_count"]
            if type(count) is not int or not 0 <= count <= 10**12:
                raise ValueError("guide_trial_invalid")
            trial["feasible_count"] = count
        if "best_feasible_objective" in extra:
            best = extra["best_feasible_objective"]
            if (not isinstance(best, Mapping) or set(best) != {"name", "direction", "value"}
                    or not isinstance(best["name"], str) or not 1 <= len(best["name"]) <= 80
                    or best["direction"] not in {"min", "max"}
                    or type(best["value"]) not in (int, float) or not math.isfinite(best["value"])):
                raise ValueError("guide_trial_invalid")
            trial["best_feasible_objective"] = dict(best)
    return {"stage": stage, "history": turns, "trial": trial, "design_notes": notes}


def build_guide_context(spec, *, stage="problem", history=None, job=None, design_notes="") -> dict:
    """Project a real UI job to bounded evidence; exclude logs, paths and refs."""
    from .lab_jobs import spec_digest
    from .lab_project import normalize_spec
    current = normalize_spec(spec)
    digest = spec_digest(current)
    context = {"stage": stage, "history": list(history or [])[-6:], "trial": None, "design_notes": design_notes}
    if isinstance(job, Mapping) and isinstance(job.get("spec_digest"), str):
        result = job.get("result") or {}
        trial = {"status": job.get("status"), "spec_digest": job["spec_digest"],
                 "matches_current": job["spec_digest"] == digest,
                 "steps": result.get("steps"), "evaluations": result.get("evaluations"),
                 "plan_completed": result.get("plan_completed")}
        error = result.get("error") or job.get("error")
        if isinstance(error, Mapping):
            trial["error"] = {"code": str(error.get("code", ""))[:80],
                              "message": str(error.get("message", ""))[:320]}
        records = result.get("records") or []
        if records and isinstance(records[-1], Mapping):
            record = records[-1]
            source_spec = current if trial["matches_current"] else job.get("spec", result.get("spec"))
            source_problem = source_spec.get("problem", {}) if isinstance(source_spec, Mapping) else {}
            if source_problem.get("component") == "problem.expression":
                from .lab_problem import objective_definitions, display_objectives
                definitions = objective_definitions(source_problem)
                count = record.get("feasible_count")
                if type(count) is int and count >= 0:
                    trial["feasible_count"] = count
                best = record.get("best_feasible_raw_sum")
                if len(definitions) == 1 and type(best) in (int, float) and math.isfinite(best):
                    trial["best_feasible_objective"] = {
                        "name": definitions[0]["name"], "direction": definitions[0]["direction"],
                        "value": display_objectives(source_problem, [best])[0]}
            elif source_spec is not None:
                best = record.get("best_raw_sum")
                if type(best) in (int, float) and math.isfinite(best):
                    trial["best_raw_sum"] = best
        context["trial"] = trial
    return normalize_guide_context(context, base_digest=digest)


__all__ = ["read_guide", "normalize_guide_context", "build_guide_context"]
