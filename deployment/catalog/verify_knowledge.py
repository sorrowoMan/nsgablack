#!/usr/bin/env python3
"""Read-only acceptance of published AI notes and their actual dashboard view."""
from contextlib import redirect_stdout, redirect_stderr
from collections import Counter
import io
import json
import os
from pathlib import Path
from unittest.mock import patch

from runtime import configure_reader


def validate_published_note(note, packet):
    """Verify the immutable body and its independent review separately."""
    from collections.abc import Mapping
    from nsgablack.catalog.curation import CurationValidationError, validate_note
    from nsgablack.catalog.tutorial_review import validate_review

    if not isinstance(note, Mapping):
        raise CurationValidationError("Published knowledge note must be a mapping")
    body = {key: value for key, value in note.items() if key != "tutorial_review"}
    checked = validate_note(body, packet)
    if checked != body:
        raise CurationValidationError("Published knowledge body is not canonical")
    review = note.get("tutorial_review")
    fields = {"decision", "issues", "checks", "evidence_ids"}
    if not isinstance(review, Mapping) or set(review) != fields | {"version"}:
        raise CurationValidationError("Published knowledge review has unsupported fields")
    checked_review = validate_review(
        {key: review[key] for key in fields},
        evidence_ids={item["id"] for item in packet["evidence"]},
    )
    if checked_review["decision"] != "publish" or checked_review != review:
        raise CurationValidationError("Published knowledge review is not a canonical current approval")
    return {**checked, "tutorial_review": checked_review}


def current_published_notes(records, packets, *, prompt_version):
    """An empty current cache is valid; matching notes must still pass review."""
    current = []
    for record in records:
        packet = packets.get(record["entry_key"])
        if (packet is None or record["source_digest"] != packet["source_digest"]
                or record["prompt_version"] != prompt_version):
            continue
        assert validate_published_note(record["note"], packet) == record["note"]
        current.append(record)
    return current


def verify_reader_write_denied(store):
    """The readonly guard must reject before validating or writing a record."""
    from nsgablack.catalog.curation_store import KnowledgeReadOnlyError

    try:
        store.put({})
    except KnowledgeReadOnlyError:
        return
    raise AssertionError("Reader did not reject a knowledge write before record validation")


def verify_maintenance_panel(app, counts, total):
    """Cache freshness is an optional detail, independent of usage coverage."""
    assert not app.get("progress"), "AI cache status must not appear as a completion progress bar"
    panels = [item for item in app.expander if item.label == "资料维护详情"]
    assert len(panels) == 1 and not panels[0].proto.expanded, "AI maintenance detail must start collapsed"
    assert sum(counts.values()) == total and set(counts) <= {"current", "stale", "missing", "invalid"}, \
        "AI cache summary contains unmatched or duplicated identities"
    expected = (f"AI 缓存 · 当前目录范围 {total} 项：可复用 {counts.get('current', 0)} · "
                f"已过期 {counts.get('stale', 0)} · 未生成 {counts.get('missing', 0)} · "
                f"校验未通过 {counts.get('invalid', 0)}")
    assert any(item.value == expected for item in panels[0].caption), "AI cache summary lost its scoped freshness counts"


def verify():
    assert configure_reader(os.environ) == "only"
    assert not Path("/run/secrets/deepseek.json").exists(), "Web reader must not hold the AI credential"
    from nsgablack.catalog.curate import load_packets
    from nsgablack.catalog.curation_provider import DeepSeekGenerator, PROMPT_VERSION
    from nsgablack.catalog.curation_store import resolve_knowledge_store
    from nsgablack.catalog import curation_ui, dashboard
    from nsgablack.units import UnitBinding
    from streamlit.testing.v1 import AppTest
    packets = load_packets(Path("/opt/catalog/knowledge-packets.json"),
                           index_path=Path("/opt/catalog/knowledge-sources.json"))
    store = resolve_knowledge_store(readonly=True)
    records = store.list_latest()
    current = current_published_notes(records, packets, prompt_version=PROMPT_VERSION)
    current_keys = {r["entry_key"] for r in current}
    # New source guides legitimately invalidate old notes. Cache population is
    # independent of source-guide completeness and never authorizes generation.
    verify_reader_write_denied(store)

    def forbidden(*args, **kwargs):
        raise AssertionError("UI attempted model inference or Unit construction")

    curation_ui._load_snapshot.cache_clear()
    runs = []
    with (patch.object(DeepSeekGenerator, "generate", forbidden),
          patch.object(DeepSeekGenerator, "review", forbidden),
          patch.object(DeepSeekGenerator, "_complete", forbidden),
          patch.object(UnitBinding, "build", forbidden)):
        for profile in ("default", "framework-core"):
            for key in ("tool.solution_pool", "adapter.moead", "mlblack.codec.neural_graph", "mlblack.trainer.learning_solver"):
                app = AppTest.from_file(dashboard.__file__, default_timeout=90)
                app.query_params.update({"profile": profile, "kind": "all", "query": key,
                                         "selected": key, "detail_tab": "interface"})
                app.run()
                assert not app.exception, "Dashboard raised while displaying generated notes"
                snapshot = curation_ui.knowledge_snapshot()
                assert snapshot.get("available"), "Published knowledge summary is unavailable"
                keys = snapshot["index"].get("profiles", {}).get(profile)
                assert keys is not None, "Requested profile is not registered in the knowledge source index"
                counts = Counter(curation_ui.entry_knowledge(item, snapshot)["status"] for item in keys)
                verify_maintenance_panel(app, counts, len(keys))
                status = curation_ui.entry_knowledge(key)["status"]
                assert any(item.value == "### AI 使用说明" for item in app.markdown)
                if key in current_keys:
                    assert status == "current"
                    assert any(item.label == "依据与整理版本" for item in app.expander)
                    assert any("未进行运行验收" in item.value for item in app.caption)
                else:
                    assert status in {"stale", "missing"}
                    assert any("缓存" in item.value for item in app.info)
                    assert not any(item.label == "依据与整理版本" for item in app.expander)
                runs.append({"profile": profile, "entry_key": key, "status": status})
    return {"ok": True, "stored_notes": len(records), "current_notes": len(current), "web_has_ai_key": False,
            "web_model_calls": 0, "reader_write_denied": True, "app_runs": runs,
            "cache_unmatched": len(packets) - len(current_keys)}


def main():
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = verify()
        code = 0
    except Exception as exc:
        result, code = {"ok": False, "error_type": type(exc).__name__}, 1
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
