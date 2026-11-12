from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest

from nsgablack.catalog import examples_ui
from nsgablack.catalog.examples import RECEIPTS_SCHEMA, build_example_index


PUBLICATION = "a" * 64
ENTRY = {"key": "adapter.vns", "minimal_wiring": ["adapter = VNSAdapter()"]}


@pytest.fixture(autouse=True)
def clear_example_cache(monkeypatch):
    from nsgablack.catalog.curation_provider import DeepSeekGenerator

    def forbidden(*args, **kwargs):
        raise AssertionError("Source example presentation must not call an AI model")

    for name in ("generate", "review", "_complete"):
        monkeypatch.setattr(DeepSeekGenerator, name, forbidden)
    examples_ui._load_snapshot.cache_clear()
    monkeypatch.delenv(examples_ui.INDEX_ENV, raising=False)
    yield
    examples_ui._load_snapshot.cache_clear()


def test_source_coverage_distinguishes_migration_navigation_and_incomplete_material():
    view = View()
    examples_ui.render_material_status(view, snapshot={"available": True, "material_categories": {
        "active_a": "detailed_with_variants", "active_b": "complete_main",
        "legacy": "migration_reference", "doc": "documentation_navigation",
        "project": "project_case_navigation", "fragment": "source_fragment",
        "missing": "missing_source"}})
    assert len(view.captions) == 2
    assert "全部索引 7 项" in view.captions[0]
    assert "详细用法 2" in view.captions[0] and "迁移说明 1" in view.captions[0]
    assert "导航 2 · 待补资料 2" in view.captions[0]
    assert "分别统计" in view.captions[1]
    assert "仍缺完整说明" not in "\n".join(view.captions)


def test_completed_material_inventory_keeps_navigation_and_migration_out_of_pending():
    view = View()
    examples_ui.render_material_status(view, snapshot={"available": True, "material_categories": {
        "guide": "detailed_with_variants", "legacy": "migration_reference",
        "doc": "documentation_navigation", "project": "project_case_navigation"}})
    assert view.captions[0] == ("用法资料 · 全部索引 4 项：详细用法 1 · 迁移说明 1 · "
                                "导航 2 · 待补资料 0")
    assert not any("仍缺" in text or "4 项都有详细用法" in text for text in view.captions)


def test_empty_source_inventory_does_not_claim_complete_material():
    view = View()
    examples_ui.render_material_status(view, snapshot={"available": True, "material_categories": {}})
    assert view.captions == []


def test_unrecognized_material_category_is_pending_instead_of_claiming_completion():
    view = View()
    examples_ui.render_material_status(view, snapshot={"available": True,
        "material_categories": {"unknown": "future_category"}})
    assert view.captions[0] == ("用法资料 · 全部索引 1 项：详细用法 0 · 迁移说明 0 · "
                                "导航 0 · 待补资料 1")


def test_real_material_summary_labels_the_full_index_separately_from_search_results(monkeypatch):
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    def forbidden(*args, **kwargs):
        raise AssertionError("A supplied material snapshot must not trigger another source scan")
    monkeypatch.setattr(examples_ui, "_read_index", forbidden)
    snapshot = {"available": True, "material_categories": {
        "a": "detailed_with_variants", "b": "complete_main", "c": "migration_reference",
        "d": "documentation_navigation", "e": "project_case_navigation",
        "f": "source_fragment", "g": "missing_source"}}
    app = AppTest.from_string(
        "import streamlit as st\nfrom nsgablack.catalog.examples_ui import render_material_status\n"
        f"render_material_status(st, snapshot={snapshot!r})\n", default_timeout=20).run()
    assert not app.exception
    assert app.caption[0].value == ("用法资料 · 全部索引 7 项：详细用法 2 · 迁移说明 1 · "
                                     "导航 2 · 待补资料 2")
    assert not app.get("progress") and not app.expander
    assert all("当前搜索" not in item.value and "仍缺完整说明" not in item.value for item in app.caption)


def test_unavailable_source_index_does_not_claim_coverage():
    view = View()
    examples_ui.render_material_status(view, snapshot={"available": False})
    assert view.captions == []


def test_variant_attachment_identity_does_not_become_a_dangling_main_heading():
    snippet = {"path": "nsgablack/docs/usage/EXTENSIONS.md", "text": (
        "## extension.adapter.demo\n\n### 变体一：从明确来源取候选\n\n"
        "替换同一个Case工厂并检查返回值。\n\n```python\nvalue = 2\n```\n")}
    assert list(examples_ui._documentation_body_parts(snippet)) == []
    from nsgablack.catalog.usage_learning import documentation_variations
    variation, = documentation_variations((snippet,))
    assert variation["title"] == "变体一：从明确来源取候选"
    assert any(kind == "code" and value == "value = 2" for kind, value, _ in variation["parts"])


def test_shared_attachment_keeps_its_human_instructions_and_copyable_code():
    snippet = {"path": "nsgablack/docs/usage/EXTENSIONS.md", "text": (
        "## extension.feedback_observation\n\n保存到Case观察器文件。\n\n"
        "```python\nclass Observer:\n    pass\n```\n")}
    parts = list(examples_ui._documentation_body_parts(snippet))
    assert any(kind == "text" and "保存到Case观察器文件" in value for kind, value, _ in parts)
    assert any(kind == "code" and "class Observer" in value for kind, value, _ in parts)
    assert not any("extension.feedback_observation" in value for kind, value, _ in parts if kind == "text")


@pytest.fixture
def published_examples(tmp_path, monkeypatch):
    """Build a real static index; execution receipts below are test fixtures."""
    root = tmp_path / "nsgablack"
    (root / "catalog/entries").mkdir(parents=True)
    (root / "catalog/example_manifests").mkdir()
    project = root / "examples/demo"
    project.mkdir(parents=True)
    (project / "run_project.py").write_text(
        "from build_solver import build_solver\nprint(build_solver())\n", encoding="utf-8")
    (project / "build_solver.py").write_text(
        "def build_solver():\n    # A renderer must never execute this code.\n    return 'demo-result'\n",
        encoding="utf-8")
    (root / "pyproject.toml").write_text('[project]\nname="example-test"\n', encoding="utf-8")
    (root / "catalog/entries/components.toml").write_text('''
[[entry]]
key = "adapter.vns"
example_entry = "python examples/demo/run_project.py"
[[entry]]
key = "adapter.missing"
example_entry = "python examples/deleted/run_project.py"
[[entry]]
key = "adapter.reference"
example_entry = "legacy-reference"
[[entry]]
key = "adapter.empty"
''', encoding="utf-8")
    (root / "catalog/example_manifests/demo.toml").write_text('''
[[example]]
id = "focused.demo"
title = "VNS 精修最小 Project"
component_keys = ["adapter.vns"]
summary = "<script>never_execute()</script>从候选开始精修。"
kind = "project"
working_directory = "nsgablack"
run_command = "python examples/demo/run_project.py"
inputs = ["提供一个已评估候选。"]
steps = ["装配 Problem 与 VNS。", "执行标准 Project 入口。"]
dependencies = ["Python 3.10+；安装本地框架依赖。"]
expected_outputs = ["返回已评估候选与原始目标。"]
sources = [
  {path="nsgablack/examples/demo/build_solver.py", start_line=1, end_line=3},
  {path="nsgablack/examples/demo/run_project.py", start_line=1, end_line=2}
]
[[example.parameters]]
name = "seed"
value = "7"
meaning = "固定随机种子。"
''', encoding="utf-8")
    path = tmp_path / "examples-index.json"
    build_example_index({"nsgablack": root}, path, publication_digest=PUBLICATION)
    monkeypatch.setenv(examples_ui.INDEX_ENV, str(path))
    return root, path


def add_success_receipt(root: Path, path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    record = data["examples"]["focused.demo"]
    output = "fixture: committed=2, evaluations=6, candidate=demo-result"
    receipt = {
        "example_id": record["id"], "status": "executed", "source_digest": record["source_digest"],
        "publication_digest": PUBLICATION, "command": record["run_command"], "exit_code": 0,
        "executed_at": "2026-10-22T06:15:00Z", "observed_outputs": [output],
        "output_sha256": hashlib.sha256(output.encode()).hexdigest(),
    }
    receipt_path = path.with_name("test-receipts.json")
    receipt_path.write_text(json.dumps({"schema": RECEIPTS_SCHEMA, "receipts": [receipt]}), encoding="utf-8")
    build_example_index({"nsgablack": root}, path, receipt_path, publication_digest=PUBLICATION)
    return receipt


class View:
    def __init__(self):
        self.markdowns = []
        self.captions = []
        self.codes = []
        self.infos = []
        self.expanders = []
        self.events = []
        self.depth = 0

    def markdown(self, text, **kwargs):
        self.markdowns.append((text, kwargs, self.depth))
        self.events.append(("markdown", text, self.depth))

    def caption(self, text):
        self.captions.append(text)
        self.events.append(("caption", text, self.depth))

    def code(self, text, **kwargs):
        self.codes.append((text, kwargs, self.depth))
        self.events.append(("code", text, self.depth))

    def info(self, text):
        self.infos.append(text)
        self.events.append(("info", text, self.depth))

    def expander(self, title, **kwargs):
        self.expanders.append((title, kwargs))
        return self

    def __enter__(self):
        self.depth += 1
        return self

    def __exit__(self, *args):
        self.depth -= 1
        return False


@pytest.mark.parametrize("numbered", [False, True])
def test_display_lists_omit_empty_marker_items_and_their_heading(numbered):
    view = View()
    examples_ui._list(view, "不应出现空标题", ["", "  ", "1.", "2)", "-", "*", "- 1.", "1.\n2)\n-\n*"], numbered=numbered)
    assert view.events == []


@pytest.mark.parametrize("numbered", [False, True])
def test_display_lists_keep_existing_markdown_and_do_not_wrap_numbering(numbered):
    view = View()
    ordered = "1. 准备 Problem\n2) 挂载 Adapter"
    unordered = "- 保留反馈\n* 核对结果"
    examples_ui._list(view, "步骤", ["1.", ordered, unordered, "运行正式 Project"], numbered=numbered)
    text = [value for value, _, _ in view.markdowns]
    assert text == ["**步骤**", ordered, unordered,
                    "3. 运行正式 Project" if numbered else "- 运行正式 Project"]


def test_display_list_cleanup_preserves_literal_markers_and_indentation_in_fenced_code():
    view = View()
    fenced = "````python\n1.\n2)\n-\n*\ndef example():\n    return '```'\n````"
    examples_ui._list(view, "原样代码", ["-", fenced])
    assert [value for value, _, _ in view.markdowns] == ["**原样代码**", fenced]
    snippet_view = View()
    examples_ui._snippet(snippet_view, {"path": "nsgablack/docs/usage.md", "start_line": 1, "end_line": 9,
                                      "text": fenced, "complete": True})
    assert snippet_view.codes[0][0] == "1.\n2)\n-\n*\ndef example():\n    return '```'"


def test_marker_only_details_do_not_create_empty_headings_or_expanders():
    view = View()
    examples_ui._render_one(view, {
        "id": "empty-details", "title": "仅有标题", "summary": "仅有摘要",
        "inputs": ["1."], "steps": ["2)"], "dependencies": ["-"], "expected_outputs": ["*"],
        "parameters": [{"name": "", "value": "", "meaning": ""}], "snippets": [],
    })
    assert view.expanders == []
    assert not any(text.startswith("**") for text, _, _ in view.markdowns)


def test_source_remains_visible_when_assembly_details_have_no_content(documentation_example):
    documentation_example.update(inputs=["1."], steps=["2)"], dependencies=["-"], expected_outputs=["*"])
    code = "def actual_call():\n    return 2"
    documentation_example["snippets"][0]["text"] = "```python\n" + code + "\n```"
    view = View()
    examples_ui._render_one(view, documentation_example)
    assert [title for title, _ in view.expanders] == ["源码与验证记录"]
    assert any(value == code and depth == 0 for value, _, depth in view.codes)
    assert any(value == code and depth > 0 for value, _, depth in view.codes)


def test_additional_title_only_reference_does_not_create_an_empty_expander(monkeypatch):
    monkeypatch.setattr(examples_ui, "examples_snapshot", lambda: {
        "available": True, "index": {"entries": {"entry": ["reference"]}, "examples": {
            "reference": {"id": "reference", "title": "没有用法内容", "summary": "只有摘要",
                          "binding": "declared", "verification": {"status": "unverified"}}
        }},
    })
    view = View()
    examples_ui.render_examples(view, {"key": "entry", "minimal_wiring": ["component = ProvidedComponent()"]})
    assert not any(title.startswith("更多用法") for title, _ in view.expanders)
    assert any("ProvidedComponent()" in code for code, _, _ in view.codes)


def test_no_index_has_honest_fallback_and_performs_no_source_reads(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No configured index must not read or scan any source")

    monkeypatch.setattr(examples_ui, "_read_index", forbidden)
    assert examples_ui.example_status(ENTRY) == "装配片段"
    assert examples_ui.example_status({"key": "other", "example_entry": "python old.py"}) == "示例待验证"
    assert examples_ui.example_status({"key": "other"}) == "待补示例"
    view = View()
    examples_ui.render_examples(view, {**ENTRY, "example_entry": "python old.py"})
    assert any("不能视为独立可运行" in caption for caption in view.captions)
    assert any("没有实际运行记录" in caption for caption in view.captions)
    assert not any("实际运行结果" in text for text, _, _ in view.markdowns)


def test_index_disambiguates_broken_reference_from_unverified_and_missing(published_examples):
    assert examples_ui.example_status(ENTRY) == "示例待验证"
    assert examples_ui.example_status({"key": "adapter.missing"}) == "入口失效"
    assert examples_ui.example_status({"key": "adapter.reference"}) == "示例待验证"
    assert examples_ui.example_status({"key": "adapter.empty"}) == "待补示例"
    view = View()
    examples_ui.render_examples(view, {"key": "adapter.missing"})
    assert any("无法与当前发布源码对应" in item for item in view.infos)
    assert not any("已记录此示例" in item for item in view.captions)


def test_focused_usage_has_visible_code_expected_results_and_safe_text(published_examples):
    view = View()
    examples_ui.render_examples(view, ENTRY)
    text = "\n".join(item[0] for item in view.markdowns)
    assert "输入与准备" in text and "使用步骤" in text and "可以修改什么" in text
    assert "预期得到什么" in text and "实际运行结果" not in text
    assert "seed" in text and "固定随机种子" in text
    assert any("尚无当前版本的成功运行记录" in item for item in view.captions)
    assert any("实际运行结果待补充" in item for item in view.captions)
    assert all(options.get("unsafe_allow_html") is False for _, options, _ in view.markdowns)
    assert any("<script>" in text for text, _, _ in view.markdowns)
    assert any("def build_solver" in code and depth == 0 for code, _, depth in view.codes)
    assert any("from build_solver" in code and depth > 0 for code, _, depth in view.codes)
    assert all(options["expanded"] is False for _, options in view.expanders)
    assert any("组件声明" in item for item in view.captions)
    assert any("nsgablack 仓库根目录" in item for item in view.captions)
    main = [(kind, text) for kind, text, depth in view.events if depth == 0]
    first_code = next(index for index, (kind, _) in enumerate(main) if kind == "code")
    first_input = next(index for index, (_, text) in enumerate(main) if "输入与准备" in text)
    assert first_input < first_code
    assert main[0] == ("caption", "**用法** · 源码已核对，未记录运行结果。")
    assert not any("VNS 精修最小 Project" in text or "<script>" in text for _, text in main)
    assert not any(text.startswith("###") for _, text in main)


def test_generic_reference_cannot_hide_component_specific_wiring(published_examples):
    view = View()
    examples_ui.render_examples(view, {"key": "adapter.reference",
        "minimal_wiring": ["component = SpecificComponent(value=3)"]})
    assert any("SpecificComponent(value=3)" == code.strip() or "component = SpecificComponent(value=3)" == code
               for code, _, _ in view.codes)


def test_documentation_fences_become_native_copyable_code_with_safe_prose():
    view = View()
    examples_ui._snippet(view, {"path": "nsgablack/docs/example.md", "start_line": 4, "end_line": 8,
        "text": "输入：2个变量。\n```python\nresult = component(value=2)\n```\n<script>x()</script>", "complete": True})
    assert any("输入：2个变量。" in text for text, _, _ in view.markdowns)
    assert any("<script>x()</script>" in text for text, _, _ in view.markdowns)
    assert all("```" not in text and options.get("unsafe_allow_html") is False
               for text, options, _ in view.markdowns)
    assert view.codes == [("result = component(value=2)", {"language": "python", "wrap_lines": True}, 0)]


@pytest.fixture
def documentation_example():
    return {
        "id": "usage.control", "title": "ControlPolicy · 最小使用片段",
        "summary": "控制建议，不能自动改变算法。", "kind": "documentation", "binding": "focused",
        "inputs": ["已定义的控制上下文。"],
        "expected_outputs": ["控制建议 Mapping。"],
        "steps": ["由明确的控制消费者处理建议。"],
        "dependencies": ["统一框架环境。"],
        "verification": {"status": "source_checked"},
        "source_digest": "a" * 64,
        "snippets": [{
            "path": "nsgablack/docs/control.md", "start_line": 2, "end_line": 18,
            "complete": False,
            "text": "## ControlPolicy\n\n控制建议，不能自动改变算法。\n\n"
                    "**输入与前提：** 已定义的控制上下文。\n\n"
                    "```python\ndef control(context):\n    return {}\n\n"
                    "updates = control(context)\n```\n\n"
                    "**预期输出：** 控制建议 Mapping。\n\n"
                    "边界：当前没有正式自动消费者，不能加入标量 BiasModule。\n",
        }],
    }


def test_documentation_main_view_has_one_recipe_and_keeps_real_limitations_visible(documentation_example):
    view = View()
    examples_ui._render_one(view, documentation_example)
    main_text = "\n".join(text for kind, text, depth in view.events if depth == 0 and kind != "code")
    main_codes = [(code, options) for code, options, depth in view.codes if depth == 0]
    assert len(main_codes) == 1
    assert main_codes[0][0] == "def control(context):\n    return {}\n\nupdates = control(context)"
    assert main_codes[0][1]["language"] == "python"
    assert "输入与准备" in main_text and "预期得到什么" in main_text
    assert "没有正式自动消费者" in main_text and "不能加入标量 BiasModule" in main_text
    assert "ControlPolicy" not in main_text
    assert "控制建议，不能自动改变算法。" not in main_text
    assert "nsgablack/docs/control.md" not in main_text
    assert "源码已核对" in main_text and "未记录运行结果" in main_text
    assert not any("实际运行结果" in text for text, _, _ in view.markdowns)
    assert {title for title, _ in view.expanders} == {"装配说明与参数", "源码与验证记录"}
    assert all(options["expanded"] is False for _, options in view.expanders)
    # Hiding layout noise must not discard the source, description or steps.
    assert any("ControlPolicy" in text and depth > 0 for text, _, depth in view.markdowns)
    assert any("不能自动改变算法" in text and depth > 0 for text, _, depth in view.markdowns)
    assert any("由明确的控制消费者处理建议" in text and depth > 0 for text, _, depth in view.markdowns)


def test_documentation_source_fields_supply_input_output_without_reinterpreting_code(documentation_example):
    documentation_example.pop("inputs")
    documentation_example.pop("expected_outputs")
    view = View()
    examples_ui._render_one(view, documentation_example)
    main = "\n".join(text for text, _, depth in view.markdowns if depth == 0)
    assert "已定义的控制上下文。" in main and "控制建议 Mapping。" in main


def test_generic_output_and_following_boundary_are_not_presented_as_a_result(documentation_example):
    documentation_example["expected_outputs"] = ["得到已装配组件或回调返回值；稍后确认。", "只能在已有Case中使用。"]
    documentation_example["snippets"][0]["text"] = documentation_example["snippets"][0]["text"].replace(
        "**预期输出：** 控制建议 Mapping。", "**预期输出：** 得到已装配组件或回调返回值；稍后确认。")
    view = View()
    examples_ui._render_one(view, documentation_example)
    main = "\n".join(text for kind, text, depth in view.events if depth == 0 and kind != "code")
    assert "结果检查说明待补充" in main
    assert "**预期得到什么**" not in main
    assert "得到已装配组件或回调返回值" not in main
    assert "不能加入标量 BiasModule" in main


def test_fenced_source_preserves_nested_fences_indentation_and_plain_text():
    parts = examples_ui._markdown_parts(
        "输入与位置：标准 Case。\n\n````python\n"
        "def example():\n    return '```'\n\nexample()\n````\n\n"
        "~~~sh\npython run_project.py\n~~~\n"
    )
    assert [part for part in parts if part[0] == "code"] == [
        ("code", "def example():\n    return '```'\n\nexample()", "python"),
        ("code", "python run_project.py", "bash"),
    ]


def test_focused_recipe_wins_over_equally_checked_generic_reference():
    state = {"available": True, "index": {
        "entries": {"component": ["generic", "focused"]},
        "examples": {
            "generic": {"id": "generic", "binding": "declared", "verification": {"status": "source_checked"}},
            "focused": {"id": "focused", "binding": "focused", "verification": {"status": "source_checked"}},
        },
    }}
    assert examples_ui._examples({"key": "component"}, state)[0]["id"] == "focused"


def test_pseudocode_is_not_highlighted_as_copyable_python():
    view = View()
    examples_ui.render_examples(view, {"key": "unindexed", "minimal_wiring": ["Problem -> Pipeline -> Adapter"]})
    main_codes = [(code, options) for code, options, depth in view.codes if depth == 0]
    assert main_codes == [("Problem -> Pipeline -> Adapter", {"language": "text", "wrap_lines": True})]


def test_local_fallback_keeps_copyable_function_indentation():
    import ast
    lines = ["def neighbors(state, context):", "", "    return [state]", "neighbors(1, {})"]
    view = View()
    examples_ui.render_examples(view, {"key": "local", "minimal_wiring": lines})
    code, options, _ = next(item for item in view.codes if item[2] == 0)
    assert code == "\n".join(lines)
    assert options["language"] == "python"
    ast.parse(code)


def test_explicit_learning_fields_precede_code_and_override_generic_input_output(documentation_example):
    documentation_example["inputs"] = ["索引中的旧输入。"]
    documentation_example["expected_outputs"] = ["索引中的旧输出。"]
    documentation_example["snippets"][0]["text"] = (
        "## adapter.toy · Toy\n\n"
        "什么时候用：需要在同一Case替换搜索策略。\n\n"
        "装配位置：旧装配位置。\n\n"
        "输入与前提：旧输入说明。\n\n"
        "**放在哪：** Case的adapter/toy.py工厂。\n\n"
        "**先准备什么：** Problem.dimension=2；候选shape=(2,)。\n\n"
        "```python\nsolver.set_adapter(Component(problem))\n```\n\n"
        "**接入步骤：**\n\n1. 由build_solver挂载工厂返回值。\n\n"
        "预期输出：旧输出说明。\n\n"
        "**怎样判断接对：** 提交后检查两列候选与同序引用。\n\n"
        "边界：构造不代表已完成求值。\n"
    )
    view = View()
    examples_ui._render_one(view, documentation_example, entry={"kind": "adapter"})
    main = [(kind, text) for kind, text, depth in view.events if depth == 0]
    main_text = "\n".join(text for kind, text in main if kind != "code")
    assert "Case的adapter/toy.py工厂" in main_text
    assert "Problem.dimension=2" in main_text and "候选shape=(2,)" in main_text
    assert "由build_solver挂载工厂返回值" in main_text
    assert "提交后检查两列候选与同序引用" in main_text
    assert not any(value in main_text for value in ("旧输入", "旧输出", "旧装配位置", "片段里的对象从哪里来"))
    code_position = next(i for i, (kind, _) in enumerate(main) if kind == "code")
    assert next(i for i, (_, text) in enumerate(main) if "**放在哪**" in text) < code_position
    assert next(i for i, (_, text) in enumerate(main) if "Problem.dimension=2" in text) < code_position
    assert next(i for i, (_, text) in enumerate(main) if "接下来怎么接" in text) > code_position


def test_learning_prose_and_file_instructions_stay_between_their_code_blocks(documentation_example):
    documentation_example["snippets"][0]["text"] = (
        "## adapter.toy · Toy\n\n"
        "**先准备什么：** 目标 `x**2`，构造 `build(**kwargs)`。\n\n"
        "**放在哪：** Case 工厂。\n\n"
        "**接入步骤：** 先定义第一份文件。\n\n"
        "首段代码保存为 `adapter/first.py`，这是独立的文件说明。\n\n"
        "```python\nfirst_file = 1\n```\n\n"
        "第一份结果由实际调用者交给第二份工厂。\n\n"
        "`pipeline/main.py` 必须使用下面的独立文件。\n\n"
        "```python\nsecond_file = 2\n```\n\n"
        "第二份文件之后还要保留这条接线说明。\n\n"
        "**怎样判断接对：** 检查两份文件的结果。\n\n"
        "主用法在变体标题前的收尾说明不能丢。\n\n"
        "### 变体一：另一种方法\n\n只在展开后说明。\n\n"
        "```python\nvariant_file = 3\n```\n"
    )
    view = View()
    examples_ui._render_one(view, documentation_example, entry={"kind": "adapter"})
    main = [(kind, value) for kind, value, depth in view.events if depth == 0]
    content = "\n".join(value for _, value in main)
    assert "`x**2`" in content and "`build(**kwargs)`" in content
    position = lambda needle: next(i for i, (_, value) in enumerate(main) if needle in value)
    assert position("adapter/first.py") < position("first_file = 1")
    assert position("first_file = 1") < position("第一份结果") < position("pipeline/main.py") < position("second_file = 2")
    assert position("second_file = 2") < position("第二份文件之后") < position("主用法在变体标题前")
    assert not any(value == "variant_file = 3" for _, value in main)
    assert any(code == "variant_file = 3" and depth > 0 for code, _, depth in view.codes)


def test_continuing_sources_keep_all_wiring_in_main_and_resolve_their_own_links(documentation_example):
    first = (
        "## first.section\n\n**先准备什么：** 第一份[输入](./input.md)。\n\n"
        "**放在哪：** 同一个Case目录。\n\n**接入步骤：** 先保存第一份文件。\n\n"
        "第一章的[调用说明](./call.md)。\n\n```python\nfirst_file = 1\n```\n\n"
        "第一章的结果交给后续工厂。\n\n### 变体一：替换第一文件\n\n"
        "只在第一变体里读[变体说明](./variant.md)。\n\n```python\nvariant_first = 3\n```\n"
    )
    second = (
        "## second.wiring\n\n第二章保存[完整接线](../reference.md#builder)，不能藏在源码中。\n\n"
        "**先准备什么：** 第二份[输入](./input.md)。\n\n"
        "```python\ndef build_solver():\n    return first_file\n```\n\n"
        "第二工厂之后检查[最终结果](./results.md)。\n\n"
        "**怎样判断接对：** 查看[核对方法](./check.md)。\n\n"
        "**运行入口：** 正式Project入口。\n\n### 变体二：替换第二文件\n\n"
        "只在第二变体里读[变体说明](./variant.md)。\n\n```python\nvariant_second = 4\n```\n"
    )
    documentation_example["snippets"] = [
        {"path": "nsgablack/docs/first/start.md", "text": first, "complete": True,
         "start_line": 1, "end_line": len(first.splitlines())},
        {"path": "nsgablack/docs/second/assemble.md", "text": second, "complete": True,
         "start_line": 1, "end_line": len(second.splitlines())},
    ]
    view = View()
    examples_ui._render_one(view, documentation_example)
    main = [(kind, text) for kind, text, depth in view.events if depth == 0]
    main_code = [text for kind, text in main if kind == "code"]
    assert main_code == ["first_file = 1", "def build_solver():\n    return first_file"]
    prose = "\n".join(text for kind, text in main if kind == "markdown")
    for path in ("nsgablack/docs/first/input.md", "nsgablack/docs/first/call.md",
                 "nsgablack/docs/second/input.md", "nsgablack/docs/reference.md#builder",
                 "nsgablack/docs/second/results.md", "nsgablack/docs/second/check.md"):
        assert path in prose
    assert "只在第一变体" not in prose and "只在第二变体" not in prose
    position = lambda needle: next(i for i, (_, value) in enumerate(main) if needle in value)
    assert position("第一章的调用说明") < position("first_file = 1")
    assert position("first_file = 1") < position("第一章的结果") < position("第二章保存") < position("def build_solver")
    assert position("def build_solver") < position("第二工厂之后")
    assert sum(text == "**输入与准备**" for kind, text in main if kind == "markdown") == 1
    nested_prose = "\n".join(text for text, _, depth in view.markdowns if depth > 0)
    assert "nsgablack/docs/first/variant.md" in nested_prose
    assert "nsgablack/docs/second/variant.md" in nested_prose
    assert all("variant_" not in code for code in main_code)


def test_prose_only_migration_keeps_explanations_visible_and_does_not_promote_variant_code(documentation_example):
    text = (
        "## migration.main\n\n**什么时候用：** 检查旧实现。\n\n"
        "**先准备什么：** 原Case。\n\n**放在哪：** 原工厂。\n\n"
        "**接入步骤：** 改用正式替代入口。\n\n"
        "真正的限制是旧方法返回固定零，不能按类名猜成有效评分。\n\n"
        "**怎样判断接对：** 检查替代反馈。\n\n**运行入口：** 正式Case。\n\n"
        "### 变体：后续替代配置\n\n只在展开后给出。\n\n```python\nvariant_only = 1\n```\n"
    )
    continuation = "## migration.details\n\n详细因果链：[调用者](./caller.md)从未消费原返回值。\n"
    documentation_example.update(usage_status="migration_reference", snippets=[
        {"path": "nsgablack/docs/migration.md", "text": text, "complete": True,
         "start_line": 1, "end_line": len(text.splitlines())},
        {"path": "nsgablack/docs/nested/details.md", "text": continuation, "complete": True,
         "start_line": 1, "end_line": len(continuation.splitlines())},
    ])
    view = View()
    examples_ui._render_one(view, documentation_example)
    main = "\n".join(text for kind, text, depth in view.events if depth == 0 and kind == "markdown")
    assert "旧方法返回固定零" in main and "从未消费原返回值" in main
    assert "nsgablack/docs/nested/caller.md" in main
    assert not [code for code, _, depth in view.codes if depth == 0]
    assert any(code == "variant_only = 1" and depth > 0 for code, _, depth in view.codes)
    assert "完整内容见下方源码" not in "\n".join(view.infos)


@pytest.mark.parametrize("manifest", ["core_unit_member_applications.toml", "core_control_state_applications.toml"])
def test_real_multisection_case_has_its_complete_builder_in_main(manifest):
    import tomllib
    from nsgablack.catalog.examples import _base_record

    root = Path(__file__).resolve().parents[1]
    spec = tomllib.loads((root/"catalog/example_manifests"/manifest).read_text(encoding="utf-8"))["example"][0]
    roots = {name: root.parent/name for name in ("nsgablack", "blackbase", "mlblack")}
    record = _base_record(spec, roots, None)
    expected = [part[1] for snippet in record["snippets"]
                for part in examples_ui._documentation_baseline_parts(snippet) if part[0] == "code"]
    assert len(record["snippets"]) == 2 and any("def build_solver" in code for code in expected)
    view = View()
    examples_ui._render_one(view, record)
    assert [code for code, _, depth in view.codes if depth == 0] == expected
    variant_code = [part[1] for snippet in record["snippets"]
                    for variation in examples_ui._documentation_variations((snippet,))
                    for part in variation["parts"] if part[0] == "code" and part[1] not in expected]
    assert variant_code
    assert all(code not in [value for value, _, depth in view.codes if depth == 0] for code in variant_code)


def test_generic_manifest_sentences_do_not_become_actual_preparation_or_output(documentation_example):
    documentation_example["snippets"][0]["text"] = (
        "```python\nsolver.set_adapter(Component())\n```"
    )
    documentation_example["inputs"] = ["同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。"]
    documentation_example["expected_outputs"] = ["得到已装配组件或回调返回值；结果需运行确认。"]
    view = View()
    examples_ui._render_one(view, documentation_example, entry={"kind": "adapter"})
    main_text = "\n".join(text for kind, text, depth in view.events if depth == 0 and kind != "code")
    assert "同一正式Case已构造" not in main_text
    assert "得到已装配组件或回调返回值" not in main_text
    assert "片段里的对象从哪里来" in main_text and "build_solver()" in main_text
    assert "**放在哪**" in main_text and "adapter/" in main_text


def test_render_does_not_import_or_execute_component_or_html(documentation_example, monkeypatch, tmp_path):
    import builtins
    marker = tmp_path / "must-not-execute.txt"
    code = ("from catalog_component_never_imported import Component\n"
            f"open({str(marker)!r}, 'w').write('executed')\n"
            "solver.set_adapter(Component())")
    documentation_example["snippets"][0]["text"] = (
        "先准备什么：二维候选。\n\n"
        "<script>arbitrary_html()</script>\n\n"
        "```python\n" + code + "\n```\n\n"
        "怎样判断接对：检查提交后的精确引用。\n\n"
        "<img src=x onerror=arbitrary_html()>\n"
    )
    original_import = builtins.__import__

    def forbid_component(name, *args, **kwargs):
        if name == "catalog_component_never_imported":
            raise AssertionError("Rendering attempted to import its component")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", forbid_component)
    view = View()
    examples_ui._render_one(view, documentation_example)
    assert not marker.exists()
    assert any(text == code and depth == 0 for text, _, depth in view.codes)
    assert all(options.get("unsafe_allow_html") is False for _, options, _ in view.markdowns)
    main_text = "\n".join(text for text, _, depth in view.markdowns if depth == 0)
    assert "arbitrary_html" not in main_text
    assert any("arbitrary_html" in text and depth > 0 for text, _, depth in view.markdowns)


def test_detailed_guide_is_primary_while_project_receipt_remains_collapsed(published_examples):
    root, path = published_examples
    (root / "docs").mkdir()
    (root / "docs/usage.md").write_text(
        "## adapter.vns · VNS\n\n放在哪：Case的adapter/工厂。\n\n"
        "先准备什么：准备二维候选与Problem边界。\n\n"
        "```python\nguide_adapter = VNSAdapter()\n```\n\n"
        "怎样判断接对：检查任务最终的已评估引用。\n", encoding="utf-8")
    (root / "catalog/example_manifests/guide.toml").write_text('''
[[example]]
id = "focused.guide"
title = "VNS具体接线说明"
component_keys = ["adapter.vns"]
kind = "documentation"
working_directory = "nsgablack"
sources = [{path="nsgablack/docs/usage.md", section="adapter.vns"}]
''', encoding="utf-8")
    build_example_index({"nsgablack": root}, path, publication_digest=PUBLICATION)
    add_success_receipt(root, path)
    assert examples_ui.example_status(ENTRY) == "已运行示例"
    view = View()
    examples_ui.render_examples(view, {**ENTRY, "kind": "adapter"})
    main_codes = [code for code, _, depth in view.codes if depth == 0]
    assert main_codes == ["guide_adapter = VNSAdapter()"]
    assert any(title.startswith("完整 Project 与运行记录") for title, _ in view.expanders)
    assert any("fixture: committed=2" in code and depth > 0 for code, _, depth in view.codes)
    assert all(not options["expanded"] for _, options in view.expanders)


@pytest.mark.parametrize("executed", [False, True])
def test_component_section_hides_same_book_preface_but_retains_other_project(published_examples, executed):
    root, path = published_examples
    (root / "docs").mkdir()
    book = ("# Component usage book\n\n```python\nunrelated_book_header()\n```\n\n"
            + "Other component introduction.\n" * 40
            + "\n## adapter.vns · VNS\n\n放在哪：Case的adapter/工厂。\n\n"
            "先准备什么：准备二维Problem。\n\n```python\nspecific_vns_usage()\n```\n\n"
            "怎样判断接对：检查已评估引用。\n")
    (root / "docs/usage.md").write_text(book, encoding="utf-8")
    declarations = root / "catalog/entries/components.toml"
    declarations.write_text(declarations.read_text(encoding="utf-8").replace(
        'example_entry = "python examples/demo/run_project.py"', 'example_entry = "docs/usage.md"'), encoding="utf-8")
    (root / "catalog/example_manifests/guide.toml").write_text('''
[[example]]
id = "focused.section"
title = "VNS专属章节"
component_keys = ["adapter.vns"]
kind = "documentation"
sources = [{path="nsgablack/docs/usage.md", section="adapter.vns"}]
''', encoding="utf-8")
    build_example_index({"nsgablack": root}, path, publication_digest=PUBLICATION)
    if executed:
        add_success_receipt(root, path)
    before = path.read_bytes()
    data = json.loads(before)
    assert any(record["binding"] == "declared" and record["kind"] == "documentation"
               for record in data["examples"].values())
    view = View()
    examples_ui.render_examples(view, ENTRY)
    codes = [code for code, _, _ in view.codes]
    assert "specific_vns_usage()" in codes
    assert not any("unrelated_book_header" in code for code in codes)
    assert any(title.endswith("VNS 精修最小 Project") for title, _ in view.expanders)
    assert "python examples/demo/run_project.py" in codes
    assert any("def build_solver" in code for code in codes)
    assert any("fixture: committed=2" in code for code in codes) is executed
    assert path.read_bytes() == before  # Presentation never deletes index evidence.


@pytest.mark.parametrize("focused_problem", ["broken", "wrong-section", "incomplete", "different-revision", "heading-only"])
def test_unusable_or_unbound_focused_section_cannot_hide_valid_declared_book(monkeypatch, focused_problem):
    digest = "a" * 64
    focus_snippet = {"path": "nsgablack/docs/usage.md", "start_line": 50, "end_line": 56,
                     "file_sha256": digest, "complete": True,
                     "text": "## entry · Component\n\n```python\nspecific_usage()\n```"}
    focused = {"id": "focused", "title": "专属用法", "component_keys": ["entry"],
               "binding": "focused", "kind": "documentation", "verification": {"status": "source_checked"},
               "snippets": [focus_snippet]}
    if focused_problem == "broken":
        focused.update(snippets=[], issues=["section_unavailable"], verification={"status": "unverified"})
    elif focused_problem == "wrong-section":
        focus_snippet["text"] = focus_snippet["text"].replace("## entry", "## other")
    elif focused_problem == "incomplete":
        focus_snippet["complete"] = False
    elif focused_problem == "different-revision":
        focus_snippet["file_sha256"] = "b" * 64
    else:
        focus_snippet["text"] = "## entry · Component"
    declared = {"id": "book", "title": "有效文档引用", "binding": "declared", "kind": "documentation",
                "verification": {"status": "source_checked"}, "snippets": [{
                    "path": "nsgablack/docs/usage.md", "start_line": 1, "end_line": 40,
                    "file_sha256": digest, "complete": True,
                    "text": "# Usage book\n\n```python\nvalid_declared_usage()\n```"}]}
    state = {"available": True, "index": {"entries": {"entry": ["focused", "book"]},
                                          "examples": {"focused": focused, "book": declared}}}
    monkeypatch.setattr(examples_ui, "examples_snapshot", lambda: state)
    view = View()
    examples_ui.render_examples(view, {"key": "entry"})
    assert any("valid_declared_usage()" in code for code, _, _ in view.codes)
    assert state["index"]["examples"]["book"] is declared


@pytest.mark.parametrize("framework,expected", [("nsgablack", "--type solver --framework nsgablack"),
                                               ("mlblack", "--type trainer --framework mlblack")])
def test_project_onboarding_is_collapsed_and_owned_by_component_framework(framework, expected):
    view = View()
    examples_ui.render_examples(view, {"key": "component", "metadata": {"catalog_framework": framework}})
    guides = [(code, depth) for code, _, depth in view.codes if "project new first_project" in code]
    assert len(guides) == 1 and guides[0][1] > 0
    assert expected in guides[0][0]
    assert "--check --build-check" in guides[0][0]
    assert any("第一次装配" in title and options["expanded"] is False for title, options in view.expanders)


def test_migration_page_does_not_offer_an_ai_tutorial_as_current_usage(monkeypatch):
    prose = "\n\n".join(f"**{label}**：{text}" for label, text in (
        ("什么时候用", "迁移旧配置时。"), ("先准备什么", "保留正式 Project。"),
        ("放在哪", "替代组件的工厂文件。"), ("接入步骤", "将替代工厂传入原 builder。"),
        ("怎样判断接对", "检查替代组件输出，不声称原组件已实现。"), ("运行入口", "正式 Project 入口。")))
    text = prose + "\n\n```python\ndef alternative(x):\n    return x * 2\n```"
    item = {"id": "migration", "title": "当前边界与替代", "kind": "documentation",
            "binding": "focused", "usage_status": "migration_reference", "component_keys": ["bias.legacy"],
            "verification": {"status": "source_checked"}, "source_digest": "a" * 64,
            "snippets": [{"path": "guide.md", "text": text, "complete": True,
                          "start_line": 1, "end_line": len(text.splitlines())}]}
    state = {"available": True, "index": {"entries": {"bias.legacy": ["migration"]},
             "examples": {"migration": item}}}
    monkeypatch.setattr(examples_ui, "examples_snapshot", lambda: state)
    def forbid(*args, **kwargs):
        raise AssertionError("a migration page cannot present a current AI tutorial")
    monkeypatch.setattr("nsgablack.catalog.curation_ui.render_tutorial", forbid)
    view = View()
    examples_ui.render_examples(view, {"key": "bias.legacy"})
    assert examples_ui.example_status({"key": "bias.legacy"}, state) == "迁移说明"
    assert any("替代示例不表示原组件" in text for text, _, depth in view.markdowns if depth == 0)


def test_focused_documentation_usage_has_its_own_honest_status():
    record = {"id": "usage", "binding": "focused", "kind": "documentation",
              "verification": {"status": "source_checked"},
              "snippets": [{"path": "fragment.md", "text": "```python\nvalue = 1\n```", "complete": True}]}
    state = {"available": True, "index": {"entries": {"component": ["usage"]},
             "examples": {"usage": record}}}
    assert examples_ui.example_status({"key": "component"}, state) == "用法片段"


@pytest.mark.parametrize("damage,expected", [(None, "详细用法"), ("placeholder", "用法片段"),
                                           ("syntax", "用法片段"), ("truncated", "用法片段")])
def test_complete_teaching_labels_require_usable_source_fields_and_code(damage, expected):
    prose = "\n\n".join("**" + label + "：** " + value for label, value in (
        ("什么时候用", "需要读取候选时。"), ("先准备什么", "准备整数输入。"),
        ("放在哪", "Case 的 helpers.py，由原工厂调用。"), ("接入步骤", "定义函数后传入整数。"),
        ("怎样判断接对", "返回输入的平方，未记录实际执行。"), ("运行入口", "现有 Project 的 run_project.py。")))
    code = "def square(x):\n    return x ** 2"
    if damage == "placeholder":
        prose = prose.replace("准备整数输入。", "同一正式Case已构造的solver与问题候选管线。")
    if damage == "syntax":
        code = "def square(:"
    item = {"id": "guide", "binding": "focused", "kind": "documentation",
            "verification": {"status": "source_checked"}, "snippets": [{
                "path": "guide.md", "text": prose + "\n\n```python\n" + code + "\n```",
                "complete": damage != "truncated"}]}
    state = {"available": True, "index": {"entries": {"component": ["guide"]}, "examples": {"guide": item}}}
    assert examples_ui.example_status({"key": "component"}, state) == expected
    # A teaching-completeness label is never an execution receipt.
    assert examples_ui.example_status({"key": "component"}, state) != "已运行示例"


def test_snapshot_caches_readiness_without_executing_the_documented_code(monkeypatch, tmp_path):
    target = tmp_path / "must-not-exist"
    record = {"id": "fragment", "binding": "focused", "kind": "documentation",
              "verification": {"status": "source_checked"}, "snippets": [{"path": "fragment.md",
                  "text": f"```python\nopen({str(target)!r}, 'w').write('never')\n```", "complete": True}]}
    index = {"entries": {"component": ["fragment"]}, "examples": {"fragment": record}}
    before = deepcopy(index)
    calls = []
    monkeypatch.setattr(examples_ui, "_read_index", lambda path: calls.append(path) or index)
    state = examples_ui._load_snapshot("fixed-index.json", (1, 2))
    again = examples_ui._load_snapshot("fixed-index.json", (1, 2))
    assert again is state and calls == ["fixed-index.json"]
    assert state["material_categories"] == {"component": "source_fragment"}
    assert examples_ui.example_status({"key": "component"}, state) == "用法片段"
    assert index == before and not target.exists()


def test_valid_receipt_renders_observed_result_separately_and_local_time(published_examples):
    root, path = published_examples
    receipt = add_success_receipt(root, path)
    assert examples_ui.example_status(ENTRY) == "已运行示例"
    view = View()
    examples_ui.render_examples(view, ENTRY)
    text = "\n".join(item[0] for item in view.markdowns)
    assert "预期得到什么" in text and "实际运行结果" in text
    assert any(receipt["observed_outputs"][0] == code for code, _, _ in view.codes)
    assert any("2026-10-22 14:15:00 UTC+08:00" in item for item in view.captions)
    assert any("退出码：0" in item for item in view.captions)
    assert not any("实际运行结果待补充" in item for item in view.captions)


@pytest.mark.parametrize("damage", ["schema", "snippet", "receipt", "publication"])
def test_corrupt_index_never_claims_execution_and_falls_back(published_examples, damage):
    root, path = published_examples
    add_success_receipt(root, path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if damage == "schema":
        data["schema"] = "old-version"
    elif damage == "snippet":
        data["examples"]["focused.demo"]["snippets"][0]["text"] += "\nforged()"
    elif damage == "receipt":
        data["examples"]["focused.demo"]["verification"]["source_digest"] = "b" * 64
    else:
        data["publication_digest"] = "b" * 64
    path.write_text(json.dumps(data), encoding="utf-8")
    assert examples_ui.example_status(ENTRY) == "装配片段"
    view = View()
    examples_ui.render_examples(view, ENTRY)
    assert any("示例索引暂不可用" in item for item in view.captions)
    assert not any("已记录此示例" in item for item in view.captions)
    assert not any("fixture:" in code for code, _, _ in view.codes)


def test_fixed_path_reader_caches_and_changes_with_published_file(published_examples, monkeypatch):
    root, path = published_examples
    original = examples_ui._read_index
    reads = []

    def read_once(path):
        reads.append(path)
        return original(path)

    monkeypatch.setattr(examples_ui, "_read_index", read_once)
    assert examples_ui.example_status(ENTRY) == "示例待验证"
    assert examples_ui.example_status({"key": "adapter.empty"}) == "待补示例"
    assert len(reads) == 1
    old = path.stat().st_mtime_ns
    add_success_receipt(root, path)
    os.utime(path, ns=(old + 1_000_000_000, old + 1_000_000_000))
    assert examples_ui.example_status(ENTRY) == "已运行示例"
    assert len(reads) == 2


def test_missing_oversized_or_failed_index_discloses_no_deployment_path(monkeypatch, tmp_path):
    path = tmp_path / "private" / "index.json"
    monkeypatch.setenv(examples_ui.INDEX_ENV, str(path))
    assert examples_ui.examples_snapshot() == {
        "configured": True, "available": False, "error_type": "FileNotFoundError"}
    path.parent.mkdir()
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(examples_ui, "_MAX_INDEX_BYTES", 1)
    assert examples_ui.examples_snapshot()["error_type"] == "ValueError"
    monkeypatch.setattr(examples_ui, "_MAX_INDEX_BYTES", 100)

    def fail(_path):
        raise RuntimeError("mysql://private:do-not-show@host/example")

    monkeypatch.setattr(examples_ui, "_read_index", fail)
    snapshot = examples_ui.examples_snapshot()
    assert snapshot == {"configured": True, "available": False, "error_type": "RuntimeError"}
    assert "do-not-show" not in repr(snapshot)


@pytest.mark.parametrize("profile", ["default", "framework-core"])
@pytest.mark.parametrize("executed", [False, True])
def test_real_streamlit_render_keeps_source_and_execution_evidence_distinct(published_examples, profile, executed):
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    root, path = published_examples
    if executed:
        add_success_receipt(root, path)
    app = AppTest.from_string(
        "import streamlit as st\n"
        "from nsgablack.catalog.examples_ui import render_examples\n"
        f"render_examples(st, {{'key': 'adapter.vns'}}, profile={profile!r})\n",
        default_timeout=20,
    ).run()
    assert not app.exception, [item.message for item in app.exception]
    text = "\n".join(item.value for item in app.markdown)
    captions = "\n".join(item.value for item in app.caption)
    codes = "\n".join(item.value for item in app.code)
    assert "**用法** · " in captions and "VNS 精修最小 Project" in text
    assert "python examples/demo/run_project.py" in codes and "def build_solver" in codes
    assert "预期得到什么" in text
    assert ("实际运行结果" in text) is executed
    assert ("fixture: committed=2" in codes) is executed
    assert ("2026-10-22 14:15:00 UTC+08:00" in captions) is executed
    assert app.expander and all(not item.proto.expanded for item in app.expander)


def test_real_streamlit_documentation_shows_copyable_call_before_collapsed_details(documentation_example):
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    app = AppTest.from_string(
        "import streamlit as st\n"
        "from nsgablack.catalog.examples_ui import _render_one\n"
        f"_render_one(st, {documentation_example!r})\n",
        default_timeout=20,
    ).run()
    assert not app.exception, [item.message for item in app.exception]
    assert app.code[0].value == "def control(context):\n    return {}\n\nupdates = control(context)"
    assert app.code[0].proto.language == "python"
    text = "\n".join(item.value for item in app.markdown)
    assert "```python" not in text
    assert "没有正式自动消费者" in text
    assert all(not item.proto.expanded for item in app.expander)


@pytest.fixture
def deployment_verifier(monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / "deployment/catalog"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("verify_catalog_examples_fixture", scripts / "verify_examples.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_deployment_source_check_reads_every_referenced_file(published_examples, deployment_verifier):
    root, path = published_examples
    data = json.loads(path.read_text(encoding="utf-8"))
    whitelist = {"nsgablack/" + source.relative_to(root).as_posix(): {
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "resolved": source.resolve(),
    } for source in root.rglob("*") if source.is_file()}
    report = deployment_verifier._verify_source_files(data, whitelist, {"nsgablack": root})
    assert report["unique_files"] == len({name for example in data["examples"].values()
                                          for name in example["source_files"]})
    assert report["source_references"] == sum(len(example["source_files"]) for example in data["examples"].values())
    source = root / "examples/demo/build_solver.py"
    source.write_text("def build_solver():\n    return 'changed-after-publication'\n", encoding="utf-8")
    with pytest.raises(deployment_verifier.VerificationError, match="file checksum"):
        deployment_verifier._verify_source_files(data, whitelist, {"nsgablack": root})


def test_deployment_source_check_verifies_excerpt_content_and_scope(published_examples, deployment_verifier):
    root, path = published_examples
    data = json.loads(path.read_text(encoding="utf-8"))
    whitelist = {"nsgablack/" + source.relative_to(root).as_posix(): {
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "resolved": source.resolve(),
    } for source in root.rglob("*") if source.is_file()}
    forged = deepcopy(data)
    forged["examples"]["focused.demo"]["snippets"][0]["text"] = "fake_excerpt()"
    with pytest.raises(deployment_verifier.VerificationError, match="source lines"):
        deployment_verifier._verify_source_files(forged, whitelist, {"nsgablack": root})
    escaped = deepcopy(data)
    escaped["examples"]["focused.demo"]["source_files"] = {"nsgablack/../private.py": "b" * 64}
    with pytest.raises(deployment_verifier.VerificationError, match="unsafe framework-relative"):
        deployment_verifier._verify_source_files(escaped, whitelist, {"nsgablack": root})
