"""Offline planning counts material and gaps; it does not verify execution."""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from catalog.material_plan import build_material_plan, main


MAIN = '''## adapter.demo · 来源用法

**什么时候用**：需要检查组件的输入与返回值时。

**先准备什么**：准备整数值，保留现有宿主入口。

**放在哪**：保存到 Case 的 component.py，再由宿主调用。

**接入步骤**：定义工厂，明确传入整数值。

```python
def factory(value):
    return value ** 2
```

**怎样判断接对**：对照返回值与输入平方，不声称已经运行。

**运行入口**：通过原 Case 的正式 Project 入口运行。
'''
VARIANT = '''
### 变体一：只改变本组件的返回规则

替换同一个 component.py 中的工厂，原调用位置与输入保持一致。

```python
def factory(value):
    return value ** 3
```

返回值变为立方，应同步修改结果检查；这不是已经执行的结果。
'''


def example(identifier, text=MAIN, *, kind="documentation", complete=True, command=""):
    return {"id": identifier, "kind": kind, "binding": "focused",
            "verification": {"status": "source_checked"}, "source_digest": "source-" + identifier,
            "run_command": command, "working_directory": "nsgablack",
            "snippets": [{"path": "nsgablack/docs/" + identifier + ".md", "text": text,
                "start_line": 1, "end_line": len(text.splitlines()), "complete": complete,
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "file_sha256": "file-" + identifier}]}


def index_for(items):
    return {"entries": {key: [item["id"]] for key, item in items.items()},
            "examples": {item["id"]: item for item in items.values()}, "issues": []}


def test_categories_follow_real_material_without_hardcoded_catalog_size():
    fragment = "## adapter.fragment\n\n输入与前提：先准备整数。\n\n```python\nvalue = 3\n```\n"
    index = index_for({"adapter.detailed": example("detailed", MAIN + VARIANT),
                       "adapter.main": example("main"), "adapter.fragment": example("fragment", fragment),
                       "doc.guide": example("guide", "# 正式文档\n按原文阅读。\n"),
                       "example.project": example("project", "# 正式Project入口\n", kind="project", command="python run_project.py")})
    original = copy.deepcopy(index)
    plan = build_material_plan(index)
    assert index == original
    assert plan["record_count"] == 5
    assert plan["categories"] == {"detailed_with_variants": 1, "complete_main": 1,
        "migration_reference": 0, "source_fragment": 1, "documentation_navigation": 1, "project_case_navigation": 1, "missing_source": 0}
    assert plan["entries"][0]["complete_variant_count"] == 1
    assert plan["totals"]["entries_with_declared_execution_receipt"] == 0
    assert all(not entry["proof"]["component_execution"] and not entry["proof"]["ai_review_performed"] for entry in plan["entries"])


def test_explicit_complete_migration_stays_separate_from_working_usage():
    old = example("old", MAIN + VARIANT + VARIANT.replace("变体一", "变体二"))
    migration = {**example("migration", MAIN + VARIANT), "usage_status": "migration_reference"}
    index = {"entries": {"bias.legacy": ["old", "migration"]},
             "examples": {"old": old, "migration": migration}, "issues": []}
    plan = build_material_plan(index)
    entry = plan["entries"][0]
    assert entry["primary_example_id"] == "migration"
    assert entry["category"] == "migration_reference"
    assert plan["categories"]["detailed_with_variants"] == 0
    assert plan["categories"]["migration_reference"] == 1
    assert entry["complete_variant_count"] == 0
    assert not entry["proof"]["component_execution"]


def test_migration_declaration_does_not_complete_an_unusable_fragment():
    item = {**example("migration", "## bias.legacy\nOnly a title.\n"),
            "usage_status": "migration_reference"}
    assert build_material_plan(index_for({"bias.legacy": item}))["entries"][0]["category"] == "source_fragment"


def test_multiple_sources_use_one_selected_guide_for_completeness_fields_and_refs():
    first = example("first", MAIN + VARIANT)
    second_variant = VARIANT.replace("变体一", "变体二").replace("value ** 3", "value ** 4")
    chosen = example("chosen", MAIN.replace("准备整数值，保留现有宿主入口。", "准备选中指南要求的整数，保持该来源的宿主入口。")
                     + VARIANT + second_variant)
    index = {"entries": {"adapter.multiple": ["first", "chosen"]},
             "examples": {"first": first, "chosen": chosen}, "issues": []}
    entry = build_material_plan(index)["entries"][0]
    assert entry["category"] == "detailed_with_variants"
    assert entry["primary_example_id"] == "chosen"
    assert entry["complete_variant_count"] == 2
    assert entry["source_refs"][0]["path"] == chosen["snippets"][0]["path"]
    assert entry["fields"]["preparation"]["values"] == ["准备选中指南要求的整数，保持该来源的宿主入口。"]


def test_placeholder_fields_are_gaps_and_not_complete_main():
    text = MAIN.replace("准备整数值，保留现有宿主入口。", "同一正式Case已构造的solver与问题候选管线。")
    text = text.replace("对照返回值与输入平方，不声称已经运行。", "得到已装配组件或回调返回值。")
    plan = build_material_plan(index_for({"adapter.test": example("placeholder", text)}))
    entry = plan["entries"][0]
    assert entry["category"] == "source_fragment"
    assert {gap["code"] for gap in entry["gaps"]} >= {"placeholder_preparation", "placeholder_result_checks"}
    assert entry["fields"]["preparation"]["values"] == []
    assert plan["totals"]["entries_with_placeholder_fields"] == 1


@pytest.mark.parametrize("text,complete,gap", [
    (MAIN, False, "incomplete_or_undeclared_excerpt"),
    (MAIN.replace("return value ** 2", "return ("), True, "python_syntax_invalid"),
    (MAIN.replace("return value ** 2", "return ..."), True, "python_placeholder_ellipsis"),
])
def test_incomplete_or_placeholder_python_remains_a_fragment(text, complete, gap):
    plan = build_material_plan(index_for({"adapter.test": example("invalid", text, complete=complete)}))
    assert plan["entries"][0]["category"] == "source_fragment"
    assert gap in {item["code"] for item in plan["entries"][0]["gaps"]}


def test_navigation_is_not_forced_into_component_fields_or_fake_commands():
    index = index_for({"doc.manual": example("doc", "# 阅读入口\n"),
        "example.case": example("case", "# 精修Case\n```bash\nREADME.md\n```\n", kind="case")})
    plan = build_material_plan(index)
    assert not plan["entries"][0]["gaps"]
    assert not plan["entries"][1]["gaps"]
    assert plan["entries"][1]["declared_run_commands"] == []


def test_measurements_are_literal_unicode_sizes_and_source_proof_is_scoped():
    item = example("中文", MAIN)
    plan = build_material_plan(index_for({"adapter.unicode": item}))
    source = item["snippets"][0]
    assert plan["totals"]["selected_source_chars"] == len(MAIN)
    assert plan["totals"]["selected_source_utf8_bytes"] == len(MAIN.encode("utf-8"))
    ref = plan["entries"][0]["source_refs"][0]
    assert ref["sha256"] == source["sha256"] and ref["declared_excerpt_digest_matches"] is True
    assert ref["start_line"] == 1 and ref["file_sha256"] == "file-中文"
    assert "not reopened" in ref["proof_scope"]
    assert "token" not in plan["totals"]


def test_ai_metadata_does_not_make_source_complete_or_prove_currency():
    item = example("source", "## adapter.test\n```python\nvalue = 3\n```\n")
    index = index_for({"adapter.test": item})
    record = {"entry_key": "adapter.test", "source_digest": "packet-digest", "model": "declared-model",
              "usage": {"review_actual_model": "declared-reviewer"},
              "evidence": [{"path": item["snippets"][0]["path"], "file_sha256": "different"}],
              "note": {"tutorial_review": {"decision": "publish"}, "tutorial": {"code": "raise RuntimeError('do not run')"}}}
    plan = build_material_plan(index, [{"key": "adapter.test", "record": record}])
    entry = plan["entries"][0]
    assert entry["category"] == "source_fragment"
    assert entry["ai_record"]["declared_review_decision"] == "publish"
    assert entry["ai_record"]["currency"] == "source_hash_conflict"
    assert entry["ai_record"]["completed_by_this_tool"] is False
    assert entry["proof"]["execution_status"] == "not_recorded"


def test_duplicate_ai_notes_and_missing_bindings_are_visible():
    index = {"entries": {"adapter.missing": ["absent"]}, "examples": {}, "issues": []}
    note = {"entry_key": "adapter.missing", "note": {}}
    plan = build_material_plan(index, [note, note, {"entry_key": "outside", "note": {}}])
    entry = plan["entries"][0]
    assert entry["category"] == "missing_source"
    assert "missing_example_binding" in {item["code"] for item in entry["gaps"]}
    assert entry["ai_record"]["status"] == "ambiguous_multiple_records"
    assert plan["ai_keys_outside_index"] == ["outside"]


def test_missing_ai_evidence_digest_remains_unknown_not_conflicting_or_current():
    item = example("source")
    record = {"entry_key": "adapter.test", "usage": None, "note": {},
              "evidence": [{"path": item["snippets"][0]["path"]}]}
    plan = build_material_plan(index_for({"adapter.test": item}), [record])
    ai = plan["entries"][0]["ai_record"]
    assert ai["currency"] == "not_established"
    assert ai["shared_source_hash_conflicts"] == []
    assert ai["shared_source_hash_unknown"] == [item["snippets"][0]["path"]]


def test_tutorial_code_is_never_executed(tmp_path):
    target = tmp_path / "never-written"
    text = MAIN.replace("return value ** 2", f"raise RuntimeError({str(target)!r})")
    plan = build_material_plan(index_for({"adapter.noexec": example("noexec", text)}))
    assert plan["entries"][0]["category"] == "complete_main"
    assert not target.exists()


def test_cli_defaults_to_stdout_and_explicit_output_keeps_input_digest(tmp_path, capsys):
    source = tmp_path / "examples.json"
    raw = json.dumps(index_for({"adapter.main": example("main")}), ensure_ascii=False).encode("utf-8")
    source.write_bytes(raw)
    assert main(["--input", str(source)]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["input_files"]["examples_index"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert list(tmp_path.iterdir()) == [source]
    output = tmp_path / "plan.json"
    assert main(["--input", str(source), "--output", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["record_count"] == 1


def test_empty_index_has_zero_actual_counts_and_bad_shapes_are_rejected():
    plan = build_material_plan({"entries": {}, "examples": {}})
    assert plan["record_count"] == 0 and sum(plan["categories"].values()) == 0
    assert plan["totals"]["selected_source_chars"] == 0
    with pytest.raises(ValueError):
        build_material_plan({"entries": [], "examples": {}})
    with pytest.raises(ValueError):
        build_material_plan({"entries": {}, "examples": {}}, "not-json-records")


def test_shared_guide_keeps_key_specific_navigation_classification():
    shared = example("shared", MAIN + VARIANT)
    index = {"entries": {"doc.shared": ["shared"], "adapter.shared": ["shared"]},
             "examples": {"shared": shared}, "issues": []}
    rows = build_material_plan(index)["entries"]
    assert rows[0]["category"] == "documentation_navigation"
    assert rows[0]["complete_variant_count"] == 0
    assert rows[1]["category"] == "detailed_with_variants"
    assert rows[1]["complete_variant_count"] == 1


def test_same_candidates_keep_project_vs_component_primary_preference():
    project = example("project", "# Project入口\n阅读配置。", kind="project")
    manual = example("manual", "# 说明入口\n阅读正文。")
    index = {"entries": {"example.demo": ["project", "manual"],
                         "tool.demo": ["project", "manual"]},
             "examples": {"project": project, "manual": manual}, "issues": []}
    rows = build_material_plan(index)["entries"]
    assert rows[0]["primary_example_id"] == "project"
    assert rows[1]["primary_example_id"] == "manual"


def test_equal_declared_ids_and_digests_do_not_share_different_source_content():
    first, second = example("same", MAIN), example("same", MAIN + VARIANT)
    assert first["source_digest"] == second["source_digest"]
    index = {"entries": {"adapter.first": ["left"], "adapter.second": ["right"]},
             "examples": {"left": first, "right": second}, "issues": []}
    rows = build_material_plan(index)["entries"]
    assert rows[0]["category"] == "complete_main"
    assert rows[1]["category"] == "detailed_with_variants"


def test_shared_guide_analysis_is_reused_without_sharing_entry_issues_or_output(monkeypatch):
    from catalog import material_plan as planner

    shared = example("shared", MAIN + VARIANT)
    receipt = {**example("receipt", "# 运行入口\n", kind="project"),
               "verification": {"status": "executed", "exit_code": 0}}
    index = {"entries": {"adapter.first": ["shared"], "adapter.second": ["shared", "receipt"]},
             "examples": {"shared": shared, "receipt": receipt},
             "issues": [{"example_id": "receipt", "error": "fixture_source_issue"}]}
    notes = [{"entry_key": "adapter.second", "note": {}}]
    calls = []
    original = planner.extract_source_guide_seed

    def extract(examples):
        calls.append(tuple(id(item) for item in examples))
        return original(examples)

    monkeypatch.setattr(planner, "extract_source_guide_seed", extract)
    rows = planner.build_material_plan(index, notes)["entries"]
    assert len(calls) == 1
    assert rows[0]["proof"]["declared_execution_receipts"] == []
    assert len(rows[1]["proof"]["declared_execution_receipts"]) == 1
    assert rows[0]["ai_record"]["status"] == "not_supplied"
    assert rows[1]["ai_record"]["status"] == "record_supplied"
    assert not rows[0]["gaps"]
    assert rows[1]["gaps"] == [{"code": "index_source_issue", "example_id": "receipt", "error": "fixture_source_issue"}]
    rows[0]["baseline_python"]["code_size"]["chars"] = -1
    rows[0]["fields"]["preparation"]["values"].clear()
    rows[0]["source_refs"][0]["path"] = "changed"
    assert rows[1]["baseline_python"]["code_size"]["chars"] > 0
    assert rows[1]["fields"]["preparation"]["values"]
    assert rows[1]["source_refs"][0]["path"] == shared["snippets"][0]["path"]


def test_shared_invalid_python_diagnostics_are_independent_between_rows():
    invalid = example("invalid", MAIN.replace("return value ** 2", "return ("))
    index = {"entries": {"adapter.first": ["invalid"], "adapter.second": ["invalid"]},
             "examples": {"invalid": invalid}}
    first, second = build_material_plan(index)["entries"]
    first["baseline_python"]["issues"][0]["code"] = "changed"
    assert second["baseline_python"]["issues"][0]["code"] == "python_syntax_invalid"
    assert second["gaps"][-1]["code"] == "python_syntax_invalid"


def test_later_call_reparses_an_edited_object_even_if_its_declared_identity_is_unchanged():
    shared = example("shared", MAIN + VARIANT)
    index = index_for({"adapter.shared": shared})
    before = build_material_plan(index)
    snippet = shared["snippets"][0]
    snippet.update(text=MAIN, sha256=hashlib.sha256(MAIN.encode()).hexdigest(), end_line=len(MAIN.splitlines()))
    after = build_material_plan(index)
    assert before["entries"][0]["category"] == "detailed_with_variants"
    assert after["entries"][0]["category"] == "complete_main"
    assert before["index_value_sha256"] != after["index_value_sha256"]
