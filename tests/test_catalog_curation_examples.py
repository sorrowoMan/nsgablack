"""Focused demonstrations enrich static AI evidence, never certify execution."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

from blackbase.catalog import CatalogEntry

from nsgablack.catalog.curation import prepare_packet, validate_note


def _source(tmp_path):
    (tmp_path / "__init__.py").write_text("class Toy:\n    pass\n", encoding="utf-8")
    code = b"raise RuntimeError('must never import example')\nmodel = Toy()\n"
    (tmp_path / "demo.py").write_bytes(code)
    entry = CatalogEntry(key="tool.toy", title="Toy", kind="tool", import_path="demo:Toy")
    example = {"origin": "manifest", "title": "实际装配", "run_command": "python demo.py",
               "inputs": ["固定数据"], "expected_outputs": ["候选反馈"],
               "publication_digest": "a" * 64, "verification": {"status": "executed"},
               "snippets": [{"path": "demo/demo.py", "file_sha256": hashlib.sha256(code).hexdigest(),
                             "start_line": 1, "end_line": 2}]}
    return entry, example


def test_focused_code_is_real_evidence_and_receipts_do_not_enter_ai_packet(tmp_path):
    entry, example = _source(tmp_path)
    packet = prepare_packet(entry, [entry], {"demo": tmp_path}, usage_examples=[example])
    guide = packet["usage_examples"][0]
    assert guide["run_command"] == "python demo.py"
    assert all(any(e["id"] == identity and e["path"] == "demo/demo.py" for e in packet["evidence"])
               for identity in guide["evidence_ids"])
    serialized = json.dumps(packet)
    assert "publication_digest" not in serialized and "executed" not in serialized
    changed = deepcopy(example)
    changed.update(publication_digest="b" * 64, verification={"status": "source_checked"})
    assert packet == prepare_packet(entry, [entry], {"demo": tmp_path}, usage_examples=[changed])
    note = {"summary": "演示组件", "use_when": [], "inputs_outputs": "候选反馈", "assembly_steps": [],
            "pitfalls": [], "related_keys": [], "missing_information": [], "evidence_ids": guide["evidence_ids"]}
    assert validate_note(note, packet)["summary"] == "演示组件"


def test_missing_wrong_hash_unsafe_or_declared_snippets_cannot_invent_evidence(tmp_path):
    entry, example = _source(tmp_path)
    baseline = prepare_packet(entry, [entry], {"demo": tmp_path})
    assert baseline == prepare_packet(entry, [entry], {"demo": tmp_path}, usage_examples=[])
    variants = []
    for field, value in (("path", "demo/../secret.py"), ("path", "demo/missing.py"),
                         ("file_sha256", "0" * 64), ("start_line", True)):
        changed = deepcopy(example)
        changed["snippets"][0][field] = value
        variants.append(changed)
    changed = deepcopy(example)
    changed["origin"] = "declared"
    variants.append(changed)
    for variant in variants:
        assert baseline == prepare_packet(entry, [entry], {"demo": tmp_path}, usage_examples=[variant])
