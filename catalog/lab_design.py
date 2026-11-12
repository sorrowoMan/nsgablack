"""Portable user-confirmed design notes; data only, never execution authority."""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json

from .lab_jobs import LabJobError

WORKSPACE_SCHEMA = "nsgablack.lab.workspace/v1"
MAX_NOTES = 6000
MAX_WORKSPACE_BYTES = 128 * 1024


def normalize_notes(notes: str) -> str:
    if not isinstance(notes, str) or len(notes) > MAX_NOTES or "\x00" in notes:
        raise ValueError("design_notes_invalid")
    return notes


def notes_digest(notes: str) -> str:
    return hashlib.sha256(normalize_notes(notes).encode("utf-8")).hexdigest()


def apply_design_notes(current_notes: str, result: Mapping) -> str:
    """Explicit confirmation; later manual edits cannot be overwritten."""
    if not isinstance(result, Mapping) or result.get("design_base_digest") != notes_digest(current_notes):
        raise LabJobError("stale_design", "设计笔记已修改，请基于当前笔记重新整理。")
    proposed = result.get("design_notes")
    try:
        proposed = normalize_notes(proposed)
        if not proposed.strip():
            raise ValueError()
    except (TypeError, ValueError):
        raise LabJobError("invalid_design", "没有可确认的设计笔记。") from None
    return proposed


def export_workspace(spec: Mapping, *, design_notes="", history=None) -> bytes:
    from .lab_assembly import normalize_assembly
    from .lab_guide import normalize_guide_context
    context = normalize_guide_context({"design_notes": design_notes, "history": list(history or [])})
    value = {"schema": WORKSPACE_SCHEMA, "assembly": normalize_assembly(spec),
             "design_notes": context["design_notes"], "history": context["history"]}
    data = json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2).encode("utf-8")
    if len(data) > MAX_WORKSPACE_BYTES:
        raise ValueError("workspace_too_large")
    return data


def import_workspace(data) -> dict:
    """Restore a portable design without accepting jobs, evidence or commands."""
    if not isinstance(data, (str, bytes, bytearray)):
        raise ValueError("workspace_invalid")
    raw = data.encode("utf-8") if isinstance(data, str) else bytes(data)
    if len(raw) > MAX_WORKSPACE_BYTES:
        raise ValueError("workspace_too_large")

    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("workspace_duplicate_key")
            value[key] = item
        return value

    value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("workspace_nonfinite")))
    if (not isinstance(value, dict) or set(value) != {"schema", "assembly", "design_notes", "history"}
            or value["schema"] != WORKSPACE_SCHEMA):
        raise ValueError("workspace_invalid")
    from .lab_assembly import normalize_assembly
    from .lab_guide import normalize_guide_context
    context = normalize_guide_context({"design_notes": value["design_notes"], "history": value["history"]})
    return {"assembly": normalize_assembly(value["assembly"]),
            "design_notes": context["design_notes"], "history": context["history"]}


def export_design_markdown(notes: str) -> str:
    return ("# 算法设计笔记\n\n"
            "以下为用户确认或编辑的设计记录。待开发内容不等于已经实现；此文档不授予执行权限，"
            "也不构成运行、数学正确性或性能证据。实际运行装配以 lab_spec.json 为准。\n\n"
            + normalize_notes(notes) + "\n")


__all__ = ["normalize_notes", "notes_digest", "apply_design_notes", "export_workspace",
           "import_workspace", "export_design_markdown"]
