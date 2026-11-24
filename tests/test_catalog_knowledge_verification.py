"""Published-note QA honors the body/review split without calls or execution."""
from copy import deepcopy
import importlib.util
from pathlib import Path

from blackbase.catalog import CatalogEntry
from nsgablack.catalog.curation import CurationValidationError, prepare_packet, validate_note
from nsgablack.catalog.tutorial_review import REVIEW_VERSION
import pytest


@pytest.fixture
def verification(monkeypatch):
    directory = Path(__file__).resolve().parents[1] / "deployment/catalog"
    monkeypatch.syspath_prepend(str(directory))
    spec = importlib.util.spec_from_file_location("verify_knowledge_contract_test", directory / "verify_knowledge.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def published(tmp_path):
    (tmp_path / "__init__.py").write_text(
        "raise RuntimeError('QA must not execute the source')\nclass Toy:\n    pass\n", encoding="utf-8")
    entry = CatalogEntry(key="tool.fixture", title="Fixture", kind="tool", import_path="fixture:Toy")
    packet = prepare_packet(entry, [entry], {"fixture": tmp_path})
    ids = [packet["evidence"][0]["id"]]
    note = {"summary": "候选值的使用示例。", "use_when": ["检查明确的候选输入。"],
            "inputs_outputs": "候选向量到候选向量。", "assembly_steps": ["由调用方消费返回值。"],
            "pitfalls": ["需要调用方提供输入。"], "related_keys": [], "missing_information": [],
            "evidence_ids": ids,
            "tutorial": {"scenario": "读取一个候选值。", "preparation": ["调用方传入 x。"],
                "placement": "独立函数调用。", "code": "def use(x):\n    return x\n", "language": "python",
                "execution_flow": ["调用方调用 use(x)。"], "result_checks": ["返回输入值。"],
                "extensions": [{"title": "复制输入列表", "purpose": "使返回值独立。", "placement": "替换同一函数。",
                    "code": "def use(x):\n    return list(x)\n", "language": "python", "effect": "返回新列表。",
                    "limits": ["输入必须可迭代。"], "evidence_ids": ids}], "evidence_ids": ids},
            "tutorial_review": {"decision": "publish", "issues": [],
                "checks": ["输入来源已核对。", "调用位置已核对。", "返回值与变体已核对。"],
                "evidence_ids": ids, "version": REVIEW_VERSION}}
    # Match curate_packets: normalize the generated body first, then append
    # the independent approval. Raw model code may still have trailing newlines.
    review = note.pop("tutorial_review")
    note = validate_note(note, packet)
    note["tutorial_review"] = review
    return note, packet


def test_current_reviewed_note_validates_without_dropping_or_mutating_values(verification, published):
    note, packet = published
    before = deepcopy((note, packet))
    assert verification.validate_published_note(note, packet) == note
    assert (note, packet) == before


@pytest.mark.parametrize("damage", ["extra", "unknown_source", "noncanonical", "missing_field",
                                   "tutorial_newline", "extension_newline"])
def test_body_contract_and_source_checks_stay_strict(verification, published, damage):
    note, packet = deepcopy(published)
    if damage == "extra":
        note["automatic_approval"] = True
    elif damage == "unknown_source":
        note["evidence_ids"] = ["e99999"]
    elif damage == "noncanonical":
        note["summary"] = " " + note["summary"]
    elif damage == "tutorial_newline":
        note["tutorial"]["code"] += "\n"
    elif damage == "extension_newline":
        note["tutorial"]["extensions"][0]["code"] += "\n"
    else:
        note.pop("inputs_outputs")
    before = deepcopy((note, packet))
    with pytest.raises(CurationValidationError):
        verification.validate_published_note(note, packet)
    assert (note, packet) == before


@pytest.mark.parametrize("damage", ["extra", "old_version", "unknown_source", "revise", "missing", "noncanonical"])
def test_review_shape_version_sources_and_publish_decision_are_all_required(verification, published, damage):
    note, packet = deepcopy(published)
    review = note["tutorial_review"]
    if damage == "extra":
        review["trusted_override"] = True
    elif damage == "old_version":
        review["version"] = "older-review-policy"
    elif damage == "unknown_source":
        review["evidence_ids"] = ["e99999"]
    elif damage == "revise":
        review.update(decision="revise", issues=[{"location": "code", "problem": "实际调用不匹配。",
            "required_change": "使用现有签名。", "evidence_ids": review["evidence_ids"]}])
    elif damage == "missing":
        note.pop("tutorial_review")
    else:
        review["checks"][0] = " " + review["checks"][0]
    before = deepcopy((note, packet))
    with pytest.raises(CurationValidationError):
        verification.validate_published_note(note, packet)
    assert (note, packet) == before
