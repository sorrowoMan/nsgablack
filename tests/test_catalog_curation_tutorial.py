"""Detailed usage remains cited display data; code is never executed."""
from __future__ import annotations

import builtins
from copy import deepcopy
import json

import pytest

from blackbase.catalog import CatalogEntry
from nsgablack.catalog.curation import (
    CurationValidationError, MAX_PACKET_CHARS, MAX_TUTORIAL_CHARS,
    prepare_packet, validate_note, validate_tutorial,
)


@pytest.fixture
def evidence(tmp_path):
    (tmp_path / "__init__.py").write_text(
        "raise RuntimeError('source must never import')\n"
        "class Component:\n    def mutate(self, candidate):\n        return candidate + 1\n", encoding="utf-8")
    entry = CatalogEntry(key="tool.component", title="Component", kind="tool", import_path="demo:Component")
    packet = prepare_packet(entry, [entry], {"demo": tmp_path})
    return tmp_path, entry, packet


def tutorial(ids):
    return {
        "scenario": "在同一候选上比较两种局部变化尺度。",
        "preparation": ["settings 与 factory 由当前 Case 的工厂显式提供。"],
        "placement": "Case 的 adapter/main.py 工厂。",
        "code": "def build_adapter(settings):\n    return factory(settings)\n",
        "language": "python",
        "execution_flow": ["由 build_solver 调用该工厂，随后交回正式 Project 运行。"],
        "result_checks": ["运行后检查成员引用与原始反馈的行数一致；这是预期检查，未提供运行证据。"],
        "extensions": [{
            "title": "保留一个明确子集", "purpose": "改变所选成员而不更改原始目标。",
            "placement": "所属 Adapter 的选择回调。",
            "code": "def choose(pool, *, rng):\n    return pool.take([0])\n", "language": "python",
            "effect": "回调返回当前请求中的一个位置。", "limits": ["调用方仍须提供足够候选并满足成员数量契约。"],
            "evidence_ids": list(ids),
        }],
        "evidence_ids": list(ids),
    }


def old_note(packet):
    return {"summary": "候选变化组件。", "use_when": ["需要一次明确变化。"], "inputs_outputs": "候选向量到候选向量。",
            "assembly_steps": ["在 Case 工厂装配。"], "pitfalls": ["未提供运行证据。"], "related_keys": [],
            "missing_information": [], "evidence_ids": [packet["evidence"][0]["id"]]}


@pytest.fixture
def many_citations(tmp_path):
    names = ("__init__", "prepare_restore", "on_solver_init", "on_generation_committed", "on_generation_end",
             "on_solver_finish", "on_solver_finalization_prepare", "on_solver_finalized", "get_report",
             "get_runtime_context_projection", "get_population_snapshot", "get_population_solution_refs", "read",
             "read_raw_feedback", "chosen", "inject", "propose", "update", "selector", "select", "choose", "mutate",
             "repair", "change", "maintain", "get_population", "get_pool_task_results", "get_pool_refinement_results",
             "feature", "build", "initialize", "init", "encode", "decode", "apply", "__call__", "apply_selection",
             "set_selector", "set_mutator")
    (tmp_path / "__init__.py").write_text("raise RuntimeError('never import citation source')\nclass Engine:\n"
                                           + "".join(f"    def {name}(self, *args):\n        return args\n" for name in names),
                                           encoding="utf-8")
    entry = CatalogEntry(key="plugin.engine", title="Engine", kind="plugin", import_path="demo:Engine")
    packet = prepare_packet(entry, [entry], {"demo": tmp_path})
    assert len(packet["evidence"]) >= 33
    return packet


@pytest.mark.parametrize("count", [18, 20, 32])
def test_legacy_and_detailed_citation_lists_accept_up_to_32_genuine_source_ids(many_citations, count):
    note = old_note(many_citations)
    note["evidence_ids"] = [item["id"] for item in many_citations["evidence"][:count]]
    note["tutorial"] = tutorial(note["evidence_ids"])
    normalized = validate_note(note, many_citations)
    assert normalized["evidence_ids"] == normalized["tutorial"]["evidence_ids"] == note["evidence_ids"]


def test_larger_citation_limit_keeps_unknown_ids_and_other_field_limits_strict(many_citations):
    note = old_note(many_citations)
    note["evidence_ids"] = [item["id"] for item in many_citations["evidence"][:33]]
    with pytest.raises(CurationValidationError, match="list field.*evidence_ids"):
        validate_note(note, many_citations)
    note["evidence_ids"] = [item["id"] for item in many_citations["evidence"][:20]]
    note["evidence_ids"][-1] = "unknown"
    with pytest.raises(CurationValidationError, match="genuine source evidence"):
        validate_note(note, many_citations)
    note["evidence_ids"] = [many_citations["evidence"][0]["id"]]
    note["use_when"] = ["明确场景" + str(index) for index in range(13)]
    with pytest.raises(CurationValidationError, match="list field.*use_when"):
        validate_note(note, many_citations)


def test_optional_tutorial_keeps_legacy_eight_fields_compatible_and_detached(evidence):
    _, _, packet = evidence
    note = old_note(packet)
    assert "tutorial" not in validate_note(note, packet)
    note["tutorial"] = tutorial(note["evidence_ids"])
    normalized = validate_note(note, packet)
    assert normalized["tutorial"]["extensions"][0]["code"].startswith("def choose")
    note["tutorial"]["preparation"].append("changed")
    assert len(normalized["tutorial"]["preparation"]) == 1


@pytest.mark.parametrize("field,value", [
    ("scenario", ""), ("preparation", []), ("preparation", ["1."]), ("placement", " "),
    ("execution_flow", []), ("result_checks", []), ("code", ""), ("language", "javascript"),
    ("extensions", []), ("extensions", [{}] * 5), ("evidence_ids", []), ("evidence_ids", ["unknown"]),
])
def test_tutorial_requires_substantive_bounded_fields_and_real_citations(field, value):
    payload = tutorial({"e1"})
    payload[field] = value
    with pytest.raises(CurationValidationError):
        validate_tutorial(payload, evidence_ids={"e1"})


@pytest.mark.parametrize("field,value", [
    ("title", ""), ("purpose", ""), ("placement", ""), ("code", ""), ("language", "shell"),
    ("effect", ""), ("limits", []), ("evidence_ids", ["invented"]),
])
def test_extensions_require_real_alternative_code_effect_limits_and_citations(field, value):
    payload = tutorial({"e1"})
    payload["extensions"][0][field] = value
    with pytest.raises(CurationValidationError):
        validate_tutorial(payload, evidence_ids={"e1"})


@pytest.mark.parametrize("location", ["tutorial", "extension"])
def test_unknown_fields_are_rejected_in_both_tutorial_levels(location):
    payload = tutorial({"e1"})
    target = payload if location == "tutorial" else payload["extensions"][0]
    target["unsupported"] = "not a new authority"
    with pytest.raises(CurationValidationError, match="supported fields"):
        validate_tutorial(payload, evidence_ids={"e1"})


@pytest.mark.parametrize("code", [
    "def incomplete(", "...", "pass", "def mutate(x):\n    ...", "def mutate(x):\n    pass",
    "class Empty:\n    pass", "# explanation only", "from nowhere import Component", "None", "42", "pass\npass",
])
@pytest.mark.parametrize("location", ["code", "extension"])
def test_bad_python_and_placeholders_are_never_presented_as_complete_code(code, location):
    payload = tutorial({"e1"})
    target = payload if location == "code" else payload["extensions"][0]
    target["code"] = code
    with pytest.raises(CurationValidationError):
        validate_tutorial(payload, evidence_ids={"e1"})


@pytest.mark.parametrize("location", ["scenario", "preparation", "code", "extension_code", "extension_effect", "extension_limits"])
@pytest.mark.parametrize("material", ["已验证正确", "All tests passed", "sk-" + "x" * 32])
def test_claims_and_credentials_are_checked_in_every_new_string(location, material):
    payload = tutorial({"e1"})
    if location == "scenario":
        payload["scenario"] = material
    elif location == "preparation":
        payload["preparation"] = [material]
    elif location == "code":
        payload["code"] = f"print({material!r})"
    elif location == "extension_code":
        payload["extensions"][0]["code"] = f"print({material!r})"
    elif location == "extension_effect":
        payload["extensions"][0]["effect"] = material
    else:
        payload["extensions"][0]["limits"] = [material]
    with pytest.raises(CurationValidationError):
        validate_tutorial(payload, evidence_ids={"e1"})


@pytest.mark.parametrize("operation", ["begin_attempt", "prepare_publication", "commit_attempt", "abort_attempt"])
def test_control_plane_transactions_are_not_generated_usage(operation):
    payload = tutorial({"e1"})
    payload["code"] = f"control.{operation}()"
    with pytest.raises(CurationValidationError, match="control-plane"):
        validate_tutorial(payload, evidence_ids={"e1"})
    payload["code"] = "value = 1"
    payload["extensions"][0]["purpose"] = f"调用 control.{operation}() 完成本轮。"
    with pytest.raises(CurationValidationError, match="control-plane"):
        validate_tutorial(payload, evidence_ids={"e1"})


@pytest.mark.parametrize("warning", [
    "禁止begin_attempt、prepare_publication、commit_attempt、abort_attempt；不得手工调用这些控制面方法。",
    "不要手工调用begin_attempt/prepare_publication/commit_attempt/abort_attempt。",
    "不要手工调用 `control.begin_attempt()`、`control.prepare_publication()`、`control.commit_attempt()`、`control.abort_attempt()`。",
    "禁止调用以下控制面方法：begin_attempt, prepare_publication, commit_attempt, abort_attempt。",
    "禁止调用以下方法：\n- begin_attempt\n- prepare_publication\n- commit_attempt\n- abort_attempt",
    "begin_attempt、prepare_publication、commit_attempt、abort_attempt均不得手工调用。",
    "Do not manually call control.begin_attempt()/control.prepare_publication()/control.commit_attempt()/control.abort_attempt().",
])
def test_explicit_negative_transaction_lists_are_boundaries_not_instructions(warning):
    payload = tutorial({"e1"})
    payload["result_checks"] = [warning]
    assert validate_tutorial(payload, evidence_ids={"e1"})["result_checks"] == [warning]


@pytest.mark.parametrize("instruction", [
    "手工调用begin_attempt/prepare_publication/commit_attempt/abort_attempt。",
    "禁止begin_attempt；随后调用commit_attempt。",
    "不要调用begin_attempt，但是直接调用commit_attempt。",
    "不要调用begin_attempt，随后调用commit_attempt。",
    "不要调用begin_attempt再调用commit_attempt。",
    "禁止begin_attempt、commit_attempt必须手工调用。",
    "Do not call begin_attempt, but manually call commit_attempt.",
    "Do not call begin_attempt and then call commit_attempt.",
    "begin_attempt不得调用；commit_attempt需要手工调用。",
    "不得不调用begin_attempt。",
    "不禁止手工调用begin_attempt。",
    "并非禁止调用begin_attempt。",
    "不是不要手工调用begin_attempt。",
])
def test_negative_transaction_boundary_does_not_license_positive_continuations(instruction):
    payload = tutorial({"e1"})
    payload["result_checks"] = [instruction]
    with pytest.raises(CurationValidationError, match="control-plane"):
        validate_tutorial(payload, evidence_ids={"e1"})


@pytest.mark.parametrize("operation", ["begin_attempt", "prepare_publication", "commit_attempt", "abort_attempt"])
def test_negative_prose_and_comments_never_allow_an_actual_python_transaction_call(operation):
    payload = tutorial({"e1"})
    payload["result_checks"] = ["禁止手工调用begin_attempt/prepare_publication/commit_attempt/abort_attempt。"]
    payload["code"] = f"# 不要手工调用 {operation}\ncontrol.{operation}()"
    with pytest.raises(CurationValidationError, match="control-plane"):
        validate_tutorial(payload, evidence_ids={"e1"})


def test_negative_boundaries_and_real_assertions_are_allowed_without_claiming_execution():
    payload = tutorial({"e1"})
    payload["result_checks"] = ["本片段不代表测试通过的证据。", "不要调用 commit_attempt；由正式 Solver 提交。"]
    payload["code"] = "values = [1, 2]\nassert len(values) == 2"
    assert validate_tutorial(payload, evidence_ids={"e1"})["code"] == payload["code"]


def test_reference_exception_applies_only_to_doc_and_example_generation(evidence):
    root, entry, packet = evidence
    payload = tutorial({packet["evidence"][0]["id"]})
    payload.update(code="", extensions=[])
    assert validate_tutorial(payload, evidence_ids=set(payload["evidence_ids"]), allow_reference=True)["code"] == ""
    for kind in ("tool", "adapter", "doc", "example"):
        reference = CatalogEntry(key=entry.key, title=entry.title, kind=kind, import_path=entry.import_path)
        current = prepare_packet(reference, [reference], {"demo": root})
        note = old_note(current)
        note["tutorial"] = deepcopy(payload)
        note["tutorial"]["evidence_ids"] = note["evidence_ids"]
        if kind in {"doc", "example"}:
            assert validate_note(note, current)["tutorial"]["extensions"] == []
        else:
            with pytest.raises(CurationValidationError):
                validate_note(note, current)


def test_tutorial_size_limit_is_independent_of_storage_capacity():
    payload = tutorial({"e1"})
    payload["extensions"] *= 4
    for extension in payload["extensions"]:
        extension["code"] = "value = '" + "x" * 7900 + "'"
    payload["code"] = "value = '" + "y" * 11900 + "'"
    assert len(json.dumps(payload)) > MAX_TUTORIAL_CHARS
    with pytest.raises(CurationValidationError, match="40000"):
        validate_tutorial(payload, evidence_ids={"e1"})


def test_python_validation_never_imports_executes_or_writes_and_allows_explicit_host_names(tmp_path, monkeypatch):
    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name == "tutorial_must_not_import":
            raise AssertionError("Tutorial code was imported")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    marker = tmp_path / "never-created.txt"
    payload = tutorial({"e1"})
    payload["preparation"] = ["solver 是宿主 Case 实例，Component 使用当前显式导入。"]
    payload["code"] = ("from tutorial_must_not_import import Component\n"
                       f"open({str(marker)!r}, 'w').write('never execute')\n"
                       "solver.set_adapter(Component())")
    assert validate_tutorial(payload, evidence_ids={"e1"})["code"] == payload["code"]
    assert not marker.exists()


def test_packet_identity_changes_even_for_edits_outside_selected_source_and_tampering_is_rejected(evidence):
    root, entry, first = evidence
    assert validate_note(old_note(first), first)
    source = root / "__init__.py"
    source.write_text(source.read_text(encoding="utf-8") + "\n# source revision after the selected method\n", encoding="utf-8")
    second = prepare_packet(entry, [entry], {"demo": root})
    assert first["source_digest"] != second["source_digest"]
    assert {item["file_sha256"] for item in first["evidence"]} != {item["file_sha256"] for item in second["evidence"]}
    damaged = deepcopy(first)
    damaged["evidence"][0]["text"] += "changed"
    with pytest.raises(CurationValidationError, match="identity"):
        validate_note(old_note(first), damaged)


def test_evidence_prioritizes_late_implementation_methods_and_actual_imported_config(tmp_path):
    (tmp_path / "__init__.py").write_text("from .impl import Engine\n", encoding="utf-8")
    settings = tmp_path / "settings.py"
    settings.write_text("raise RuntimeError('never import settings')\nfrom dataclasses import dataclass\n"
                        "@dataclass\nclass EngineConfig:\n    width: int = 4\n", encoding="utf-8")
    implementation = tmp_path / "impl.py"
    implementation.write_text(
        "raise RuntimeError('never import implementation')\nfrom .settings import EngineConfig\n"
        "class Engine:\n    def __init__(self, config: EngineConfig):\n        self.config = config\n"
        + "    # unrelated prefix must not displace real operations\n" * 160
        + "    def propose(self, control, context):\n        return context['seed']\n"
          "    def update(self, control, candidates, feedback, context):\n        self.feedback = feedback\n"
          "    def get_population_snapshot(self):\n        return self.population, self.objectives, self.violations\n"
          "    def read(self, refs):\n        return self.store.read(refs)\n"
          "    def chosen(self, rule):\n        return rule(self)\n"
          "    def inject(self, source):\n        return source\n", encoding="utf-8")
    entry = CatalogEntry(key="adapter.engine", title="Engine", kind="adapter", import_path="demo:Engine")
    first = prepare_packet(entry, [entry], {"demo": tmp_path})
    text = "\n".join(item["text"] for item in first["evidence"])
    for declaration in ("def propose", "def update", "def get_population_snapshot", "def read", "def chosen", "def inject"):
        assert declaration in text
    assert "class EngineConfig" in text and "width: int = 4" in text
    assert any(item["path"] == "demo/settings.py" for item in first["evidence"])
    assert len(json.dumps(first, ensure_ascii=False, separators=(",", ":"))) <= MAX_PACKET_CHARS
    for item in first["evidence"]:
        source = tmp_path / item["path"].partition("/")[2]
        lines = source.read_bytes().decode("utf-8-sig").splitlines(keepends=True)
        assert item["text"] == "".join(lines[item["start_line"] - 1:item["end_line"]])
    settings.write_text(settings.read_text(encoding="utf-8") + "\n# different config source revision\n", encoding="utf-8")
    second = prepare_packet(entry, [entry], {"demo": tmp_path})
    assert second["source_digest"] != first["source_digest"]


def test_explicit_pool_alias_delivers_chosen_and_inject_instead_of_module_preface(tmp_path):
    source = tmp_path / "__init__.py"
    source.write_text("raise RuntimeError('never import alias')\nclass ChangeSelection:\n"
                      + "    # unrelated class heading detail\n" * 130
                      + "    def chosen(self, rule):\n        return rule(self)\n"
                        "    def inject(self, source, *, replace=False):\n        return source\n"
                        "Pool = ChangeSelection\n", encoding="utf-8")
    entry = CatalogEntry(key="tool.pool", title="Pool", kind="tool", import_path="demo:Pool")
    packet = prepare_packet(entry, [entry], {"demo": tmp_path})
    assert not packet["gaps"]
    assert any("def chosen" in item["text"] for item in packet["evidence"])
    assert any("def inject" in item["text"] for item in packet["evidence"])
    source.write_text(source.read_text(encoding="utf-8") + "Pool = dynamic_factory()\n", encoding="utf-8")
    ambiguous = prepare_packet(entry, [entry], {"demo": tmp_path})
    assert any("符号未能静态定位" in gap for gap in ambiguous["gaps"])


def test_explicit_input_example_keeps_its_result_reading_beyond_old_short_excerpt(evidence):
    import hashlib

    root, entry, _ = evidence
    source = root / "usage.py"
    content = ("raise RuntimeError('never execute usage')\n"
               + "# explicit inputs and their interpretation need context\n" * 60
               + "expected_feedback_shape = (4, 1)\n")
    source.write_text(content, encoding="utf-8")
    example = {"origin": "manifest", "title": "完整的显式输入与结果读法", "inputs": ["候选为四行二维向量。"],
               "expected_outputs": ["原始反馈为四行一列。"], "snippets": [{
                   "path": "demo/usage.py", "start_line": 1, "end_line": len(content.splitlines()),
                   "file_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}]}
    packet = prepare_packet(entry, [entry], {"demo": root}, usage_examples=[example])
    assert any("expected_feedback_shape = (4, 1)" in item["text"] for item in packet["evidence"])
    assert packet["usage_examples"][0]["expected_outputs"] == ["原始反馈为四行一列。"]


def test_one_level_parent_evidence_includes_cross_file_constructor_and_late_methods(tmp_path):
    (tmp_path / "__init__.py").write_text("from .child import Child\n", encoding="utf-8")
    (tmp_path / "grand.py").write_text("raise RuntimeError('do not import grand')\nclass Grand:\n    pass\n", encoding="utf-8")
    parent_path = tmp_path / "parent.py"
    parent_path.write_text(
        "raise RuntimeError('do not import parent')\nfrom .grand import Grand\nclass Parent(Grand):\n"
        "    def __init__(self, capacity=4, *, seed=17):\n        self.capacity = capacity\n"
        + "    # implementation continues beyond the class preface\n" * 150
        + "    def propose(self, control, context):\n        return context['parent_seed']\n"
          "    def update(self, control, candidates, feedback, context):\n        self.feedback = feedback\n", encoding="utf-8")
    (tmp_path / "child.py").write_text("raise RuntimeError('do not import child')\nfrom .parent import Parent\n"
                                      "class Child(Parent):\n    name = 'child'\n", encoding="utf-8")
    entry = CatalogEntry(key="adapter.child", title="Child", kind="adapter", import_path="demo:Child")
    first = prepare_packet(entry, [entry], {"demo": tmp_path})
    parent_evidence = [item for item in first["evidence"] if item["path"] == "demo/parent.py"]
    assert any("def __init__(self, capacity=4, *, seed=17)" in item["text"] for item in parent_evidence)
    assert any("def propose" in item["text"] and "parent_seed" in item["text"] for item in parent_evidence)
    assert any("def update" in item["text"] for item in parent_evidence)
    assert not any(item["path"] == "demo/grand.py" for item in first["evidence"])
    assert any("只展开一层" in gap for gap in first["gaps"])
    for item in parent_evidence:
        lines = parent_path.read_bytes().decode("utf-8-sig").splitlines(keepends=True)
        assert item["text"] == "".join(lines[item["start_line"] - 1:item["end_line"]])
    parent_path.write_text(parent_path.read_text(encoding="utf-8").replace("parent_seed", "new_parent_seed"), encoding="utf-8")
    second = prepare_packet(entry, [entry], {"demo": tmp_path})
    assert first["source_digest"] != second["source_digest"]
    assert {item["file_sha256"] for item in parent_evidence} != {
        item["file_sha256"] for item in second["evidence"] if item["path"] == "demo/parent.py"}


def test_parent_evidence_caps_two_explicit_names_and_does_not_expand_attributes(tmp_path):
    for name in ("First", "Second", "Third"):
        (tmp_path / f"{name.lower()}.py").write_text(
            f"raise RuntimeError('never import {name}')\nclass {name}:\n"
            "    def __init__(self, capacity=2):\n        self.capacity = capacity\n", encoding="utf-8")
    (tmp_path / "__init__.py").write_text(
        "from .first import First\nfrom .second import Second\nfrom .third import Third\n"
        "class Child(First, Second, Third):\n    name = 'child'\n", encoding="utf-8")
    entry = CatalogEntry(key="tool.child", title="Child", kind="tool", import_path="demo:Child")
    packet = prepare_packet(entry, [entry], {"demo": tmp_path})
    paths = {item["path"] for item in packet["evidence"]}
    assert "demo/first.py" in paths and "demo/second.py" in paths
    assert "demo/third.py" not in paths
    assert len(json.dumps(packet, ensure_ascii=False, separators=(",", ":"))) <= MAX_PACKET_CHARS


def test_direct_helper_evidence_prioritizes_guards_caps_six_and_stops_after_one_hop(tmp_path):
    source = tmp_path / "__init__.py"
    source.write_text(
        "raise RuntimeError('never import helpers')\nclass Engine:\n"
        "    def on_solver_finish(self, result):\n"
        + "".join(f"        self._normal_{index}()\n" for index in range(8))
        + "        self._assert_security()\n        self._save_state()\n"
        + "    # helpers occur after the ordinary declaration excerpt\n" * 90
        + "    def _assert_security(self):\n        return self._second_hop()\n"
          "    def _save_state(self):\n        return 'saved bytes, not a runtime claim'\n"
        + "".join(f"    def _normal_{index}(self):\n        return {index}\n" for index in range(8))
        + "    def _second_hop(self):\n        return 'not followed'\n"
          "    def get_report(self):\n        return {'status': 'not_attempted'}\n", encoding="utf-8")
    entry = CatalogEntry(key="plugin.engine", title="Engine", kind="plugin", import_path="demo:Engine")
    packet = prepare_packet(entry, [entry], {"demo": tmp_path})
    text = "\n".join(item["text"] for item in packet["evidence"])
    assert "def _assert_security" in text and "def _save_state" in text and "def get_report" in text
    assert "def _second_hop" not in text
    assert sum(f"def _normal_{index}" in text for index in range(8)) <= 4
    assert len(json.dumps(packet, ensure_ascii=False, separators=(",", ":"))) <= MAX_PACKET_CHARS
    source.write_text(source.read_text(encoding="utf-8").replace("not followed", "changed unselected helper"), encoding="utf-8")
    assert prepare_packet(entry, [entry], {"demo": tmp_path})["source_digest"] != packet["source_digest"]


def _usage_snippet(root, code, *, suffix=".py"):
    import hashlib

    path = root / ("usage" + suffix)
    path.write_text(code, encoding="utf-8")
    return {"origin": "manifest", "title": "显式工厂装配", "snippets": [{
        "path": "demo/" + path.name, "start_line": 1, "end_line": len(code.splitlines()),
        "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}]}


def test_usage_imports_match_real_catalog_classes_prioritize_case_wiring_and_cap_three(tmp_path):
    classes = ("Main", "Data", "Head", "FitAdapter", "Problem", "Unused", "Unknown")
    for name in classes:
        (tmp_path / (name.lower() + ".py")).write_text(
            f"raise RuntimeError('never import {name}')\nclass {name}:\n"
            "    def __init__(self, *, source=None):\n        self.source = source\n", encoding="utf-8")
    (tmp_path / "__init__.py").write_text(
        "".join(f"from .{name.lower()} import {name}\n" for name in classes), encoding="utf-8")
    entries = [CatalogEntry(key="tool.main", title="Main", kind="tool", import_path="demo:Main")]
    entries.extend(CatalogEntry(key="tool." + name.lower(), title=name, kind=kind,
                               import_path="demo." + name.lower() + ":" + name)
                   for name, kind in (("Data", "tool"), ("Head", "head"), ("FitAdapter", "adapter"),
                                      ("Problem", "problem"), ("Unused", "tool")))
    code = ("```python\nfrom demo import Data, Head, FitAdapter as Fit, Problem, Unused, Unknown\n"
            "data = Data()\nhead = Head()\nadapter = Fit(source=head)\nproblem = Problem(source=data)\n"
            "other = Unknown()\n```\n")
    example = _usage_snippet(tmp_path, code, suffix=".md")
    packet = prepare_packet(entries[0], iter(entries), {"demo": tmp_path}, usage_examples=[example])
    paths = {item["path"] for item in packet["evidence"]}
    assert {"demo/fitadapter.py", "demo/problem.py", "demo/data.py"} <= paths
    assert not {"demo/head.py", "demo/unused.py", "demo/unknown.py"} & paths
    assert len(json.dumps(packet, ensure_ascii=False, separators=(",", ":"))) <= MAX_PACKET_CHARS
    problem_source = tmp_path / "problem.py"
    problem_source.write_text(problem_source.read_text(encoding="utf-8") + "\n# full related source revision\n", encoding="utf-8")
    refreshed = prepare_packet(entries[0], entries, {"demo": tmp_path}, usage_examples=[example])
    assert refreshed["source_digest"] != packet["source_digest"]
    assert {item["file_sha256"] for item in refreshed["evidence"] if item["path"] == "demo/problem.py"} != {
        item["file_sha256"] for item in packet["evidence"] if item["path"] == "demo/problem.py"}
    stale = deepcopy(example)
    stale["snippets"][0]["file_sha256"] = "0" * 64
    assert prepare_packet(entries[0], entries, {"demo": tmp_path}, usage_examples=[stale]) == prepare_packet(entries[0], entries, {"demo": tmp_path})


def test_usage_rebound_or_ambiguous_imports_and_non_python_fences_are_not_class_evidence(tmp_path):
    for name in ("Main", "First", "Second"):
        (tmp_path / (name.lower() + ".py")).write_text(f"class {name}:\n    enabled = True\n", encoding="utf-8")
    (tmp_path / "__init__.py").write_text("from .main import Main\nfrom .first import First\nfrom .second import Second\n", encoding="utf-8")
    entries = [CatalogEntry(key="tool." + name.lower(), title=name, kind="tool", import_path="demo:" + name)
               for name in ("Main", "First", "Second")]
    for code in ("from demo import First as Selected\nSelected = factory()\nunit = Selected()\n",
                 "from demo import First as Selected\nfrom demo import Second as Selected\nunit = Selected()\n",
                 "```text\nfrom demo import First\nunit = First()\n```\n"):
        example = _usage_snippet(tmp_path, code, suffix=".md" if code.startswith("```") else ".py")
        packet = prepare_packet(entries[0], entries, {"demo": tmp_path}, usage_examples=[example])
        assert not {"demo/first.py", "demo/second.py"} & {item["path"] for item in packet["evidence"]}


def test_actual_checkpoint_guards_report_and_unit_usage_consumers_are_static_evidence(tmp_path, monkeypatch):
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    roots = {"nsgablack": root, "blackbase": root.parent / "blackbase", "demo": tmp_path}
    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name in {"nsgablack.units", "nsgablack.plugins.system.checkpoint_resume"}:
            raise AssertionError("Source component was imported")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    checkpoint = CatalogEntry(key="plugin.checkpoint_resume", title="Checkpoint", kind="plugin",
                              import_path="nsgablack.plugins.system.checkpoint_resume:CheckpointResumePlugin")
    packet = prepare_packet(checkpoint, [checkpoint], roots)
    text = "\n".join(item["text"] for item in packet["evidence"])
    assert "def _assert_strict_security_ready" in text and "strict checkpoint mode requires HMAC key" in text
    assert "def get_report" in text and '"resume_audit"' in text
    assert "def on_solver_finalized" in text and 'str(ref.uri)' in text
    entries = [CatalogEntry(key="tool." + name.lower(), title=name, kind="tool", import_path="nsgablack.units:" + name)
               for name in ("UnitFeature", "FeatureUnit", "PopulationUnit")]
    example = _usage_snippet(tmp_path, "raise RuntimeError('never execute usage')\n"
                            "from nsgablack.units import UnitFeature, FeatureUnit, PopulationUnit\n"
                            "unit = PopulationUnit('example')\nfeature = UnitFeature('size', ('population',), len)\n"
                            "assert isinstance(unit, FeatureUnit)\nvalue = unit.feature(feature)\n")
    packet = prepare_packet(entries[0], entries, roots, usage_examples=[example])
    text = "\n".join(item["text"] for item in packet["evidence"])
    for declaration in ("class FeatureUnit", "def feature(", "class PopulationUnit", "feature_feedback_fields:",
                        "member_fields:", "def on_members_changed", "def validate_feature_inputs"):
        assert declaration in text
    assert len(json.dumps(packet, ensure_ascii=False, separators=(",", ":"))) <= MAX_PACKET_CHARS


def test_signature_types_are_static_bounded_not_recursive_and_invalidate_full_source_digest(tmp_path):
    for name in ("CallContext", "DecisionResult", "FeedbackBatch", "ExtraSpec", "NestedRequest", "BodyRequest"):
        (tmp_path / (name.lower() + ".py")).write_text(
            f"raise RuntimeError('never import {name}')\nclass {name}:\n"
            "    actual_field: str = 'current'\n    nested: 'NestedRequest' = None\n", encoding="utf-8")
    (tmp_path / "__init__.py").write_text(
        "from .callcontext import CallContext\nfrom .decisionresult import DecisionResult\n"
        "from .feedbackbatch import FeedbackBatch\nfrom .extraspec import ExtraSpec\n"
        "from .bodyrequest import BodyRequest\nfrom numpy import NumericContext\n"
        "class Engine:\n"
        "    def propose(self, context: 'CallContext') -> 'DecisionResult':\n        return BodyRequest()\n"
        "    def update(self, feedback: FeedbackBatch, extra: ExtraSpec, numeric: NumericContext):\n        self.feedback = feedback\n",
        encoding="utf-8")
    entry = CatalogEntry(key="adapter.engine", title="Engine", kind="adapter", import_path="demo:Engine")
    first = prepare_packet(entry, [entry], {"demo": tmp_path})
    selected = [item for item in first["evidence"] if item["path"] != "demo/__init__.py"]
    assert {item["path"] for item in selected} == {"demo/callcontext.py", "demo/decisionresult.py", "demo/feedbackbatch.py"}
    assert len(json.dumps(selected, ensure_ascii=False, separators=(",", ":"))) <= 6000
    assert len(json.dumps(first, ensure_ascii=False, separators=(",", ":"))) <= MAX_PACKET_CHARS
    source = tmp_path / "callcontext.py"
    source.write_text(source.read_text(encoding="utf-8").replace("actual_field", "renamed_actual_field"), encoding="utf-8")
    second = prepare_packet(entry, [entry], {"demo": tmp_path})
    assert first["source_digest"] != second["source_digest"]
    assert {item["file_sha256"] for item in selected if item["path"] == "demo/callcontext.py"} != {
        item["file_sha256"] for item in second["evidence"] if item["path"] == "demo/callcontext.py"}


def test_actual_tabu_packet_contains_optimization_context_fields_without_importing_bias(monkeypatch):
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name == "nsgablack.bias.algorithmic.tabu_search":
            raise AssertionError("Bias source was imported")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    entry = CatalogEntry(key="bias.tabu", title="TabuSearchBias", kind="bias",
                         import_path="nsgablack.bias.algorithmic.tabu_search:TabuSearchBias")
    packet = prepare_packet(entry, [entry], {"nsgablack": root, "blackbase": root.parent / "blackbase"})
    contexts = [item for item in packet["evidence"] if "class OptimizationContext:" in item["text"]]
    assert contexts
    text = "\n".join(item["text"] for item in contexts)
    for field in ("generation", "individual", "metrics", "candidate_token", "candidate_state", "is_stuck"):
        assert "self." + field in text
    assert "self.stage" not in text
    assert all(item["path"] == "nsgablack/bias/core/base.py" for item in contexts)
    assert len(json.dumps(packet, ensure_ascii=False, separators=(",", ":"))) <= MAX_PACKET_CHARS


def test_first_complete_usage_builder_keeps_twelve_k_before_large_implementation_evidence(tmp_path):
    source = "raise RuntimeError('never import implementation')\nclass Engine:\n"
    for name in ("__init__", "propose", "update", "read", "chosen", "inject"):
        source += f"    def {name}(self, *args):\n" + "        # substantial implementation detail\n" * 140 + "        return args\n"
    (tmp_path / "__init__.py").write_text(source, encoding="utf-8")
    code = ("raise RuntimeError('never execute complete builder')\nfrom demo import Engine\n"
            + "# Preparation explains the exact input layout and the Case resource handoff.\n" * 110
            + "def build_solver(config=None, *, resource_context=None):\n"
              "    solver = Engine(config, resource_context)\n    return solver\n"
              "expected_result_kind = 'formal Case result'\n")
    assert 6000 < len(code) < 12000
    example = _usage_snippet(tmp_path, code)
    entry = CatalogEntry(key="adapter.engine", title="Engine", kind="adapter", import_path="demo:Engine")
    packet = prepare_packet(entry, [entry], {"demo": tmp_path}, usage_examples=[example])
    paths = [item["path"] for item in packet["evidence"]]
    assert paths.index("demo/usage.py") < paths.index("demo/__init__.py")
    shown = next(item for item in packet["evidence"] if item["path"] == "demo/usage.py")
    assert "def build_solver" in shown["text"] and "expected_result_kind" in shown["text"]
    assert len(shown["text"]) > 6000
    assert packet["usage_examples"][0]["evidence_ids"] == [shown["id"]]
    assert len(json.dumps(packet, ensure_ascii=False, separators=(",", ":"))) <= MAX_PACKET_CHARS
