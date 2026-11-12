"""Component lookup reads publication facts, not component implementations."""
from copy import deepcopy
import hashlib
import json

import pytest

from nsgablack.catalog import lab_workspace_reference as reference


@pytest.fixture
def source():
    entries = [
        {"key": "adapter.vns", "title": "VNSAdapter", "kind": "adapter",
         "summary": "从精英池进行邻域精修", "import_path": "never_import.vns:VNSAdapter",
         "config_keys": ["k_max"], "required_companions": ["tool.pool"],
         "companions": ["tool.pool", "tool.missing"],
         "contract": {"catalog": {"operations": ["set_change"], "boundaries": ["不改原始目标"]}}},
        {"key": "tool.pool", "title": "Pool", "kind": "tool", "summary": "候选集合",
         "minimal_wiring": ["from never_import.pool import Pool", "elite = Pool(parent=members)"]},
        {"key": "mlblack.codec.demo", "title": "DemoCodec", "kind": "codec", "summary": "模型布局"},
        {"key": "doc.demo", "title": "指南", "kind": "doc", "summary": "VNS 参考"},
    ]
    text = ("## adapter.vns\n\n先准备什么：已评估的精英池。\n\n放在哪：Case adapter 工厂。\n\n"
            "```python\nfrom never_import.vns import VNSAdapter\nadapter = VNSAdapter(k_max=3)\n```\n\n"
            "### 变体一：替换邻域\n\n```python\nadapter.set_change(change)\n```\n")
    example = {"id": "focused.vns", "title": "VNS 用法", "binding": "focused", "kind": "documentation",
               "component_keys": ["adapter.vns"], "verification": {"status": "source_checked"},
               "snippets": [{"path": "nsgablack/docs/VNS.md", "start_line": 10, "text": text}],
               "parameters": [{"name": "k_max", "value": "3", "meaning": "本片段的邻域上限"}]}
    return reference.ReferenceSource(entries,
        {"entries": {"adapter.vns": ["focused.vns"]}, "examples": {"focused.vns": example}},
        profiles={"default": [row["key"] for row in entries],
                  "framework-core": [row["key"] for row in entries if row["kind"] != "doc"]})


def test_search_has_exact_names_chinese_usage_and_kind_filter(source, monkeypatch):
    import importlib
    monkeypatch.setattr(importlib, "import_module", lambda *a, **k: pytest.fail("component imported"))
    result = reference.reference_search("VNSAdapter", source=source)
    assert result["available"] and result["items"][0]["key"] == "adapter.vns"
    assert reference.reference_search("精英池", source=source)["total"] == 1
    assert reference.reference_search("VNS", kind="tool", source=source)["items"] == []
    assert reference.reference_search("模型", source=source)["items"][0]["key"] == "mlblack.codec.demo"


def test_empty_search_is_bounded_and_does_not_hide_other_frameworks(source):
    result = reference.reference_search(source=source, limit=2)
    assert result["total"] == 4 and len(result["items"]) == 2
    assert result["items"][0]["key"] == "adapter.vns"
    assert reference.reference_search("Codec", source=source)["total"] == 1


def test_search_can_find_a_use_case_or_operation_inside_published_guide(source):
    assert reference.reference_search("替换邻域", source=source)["items"][0]["key"] == "adapter.vns"
    assert reference.reference_search("adapter.set_change(change)", source=source)["total"] == 1


def test_nonmapping_optional_guidance_does_not_invent_a_role():
    source = reference.ReferenceSource([{"key": "tool.demo", "kind": "tool", "contract": {"catalog": None}}])
    detail = reference.reference_detail("tool.demo", source=source)
    assert detail["operations"] == detail["boundaries"] == []


def test_published_profiles_drive_scope_without_reinferring_membership(source):
    assert reference.reference_search("", source=source)["catalog_total"] == 4
    core = reference.reference_search("", profile="framework-core", source=source)
    assert core["catalog_total"] == 3 and all(row["kind"] != "doc" for row in core["items"])
    assert reference.reference_detail("doc.demo", source=source, profile="framework-core") is None


@pytest.mark.parametrize("options", [{"query": None}, {"query": "x" * 301}, {"kind": []},
    {"limit": True}, {"limit": 0}, {"limit": 51}, {"profile": "unknown"}])
def test_invalid_search_inputs_are_explicit(source, options):
    with pytest.raises(ValueError):
        reference.reference_search(source=source, **options)


def test_detail_preserves_full_guide_variants_code_and_source_lines(source):
    detail = reference.reference_detail("adapter.vns", source=source)
    assert "变体一" in detail["usage_markdown"]
    assert [block["code"] for block in detail["code_blocks"]] == [
        "from never_import.vns import VNSAdapter\nadapter = VNSAdapter(k_max=3)",
        "adapter.set_change(change)"]
    assert detail["code_blocks"][0]["language"] == "python"
    assert detail["code_blocks"][0]["start_line"] == 17
    assert detail["parameters"] == [{"name": "k_max", "value": "3", "meaning": "本片段的邻域上限"}]
    assert detail["config_keys"] == ["k_max"]
    assert detail["operations"] == ["set_change"]
    assert "未声明当前版本运行成功" in detail["evidence_note"]


def test_only_declared_relations_are_used_and_missing_targets_stay_visible(source):
    detail = reference.reference_detail("adapter.vns", source=source)
    assert [row["key"] for row in detail["relations"]] == ["tool.pool", "tool.missing"]
    assert detail["relations"][0]["reason"] == "必需配套（目录声明）"
    assert detail["relations"][1]["available"] is False
    assert all(row["key"] != "doc.demo" for row in detail["relations"])


def test_minimal_wiring_is_verbatim_and_never_instantiates_component(source):
    detail = reference.reference_detail("tool.pool", source=source)
    assert detail["code_blocks"][0]["code"] == "from never_import.pool import Pool\nelite = Pool(parent=members)"
    assert detail["parameters"] == []
    assert "未验证" in detail["evidence_note"]


def test_unknown_component_returns_none_without_fabrication(source):
    assert reference.reference_detail("adapter.missing", source=source) is None
    with pytest.raises(ValueError):
        reference.reference_detail("../../private", source=source)


def test_detail_outputs_are_detached_from_following_lookups(source):
    first = reference.reference_detail("adapter.vns", source=source)
    first["parameters"][0]["meaning"] = "changed"
    first["relations"].clear()
    again = reference.reference_detail("adapter.vns", source=source)
    assert again["parameters"][0]["meaning"] == "本片段的邻域上限"
    assert len(again["relations"]) == 2


def write_publication(tmp_path):
    packet = {"schema": "nsgablack.catalog.knowledge_packets/v1", "packets": {
        "tool.pool": {"entry": {"key": "tool.pool", "title": "Pool", "kind": "tool"},
                      "source_digest": "a" * 64}}}
    raw = json.dumps(packet).encode()
    index = {"schema": "nsgablack.catalog.knowledge_sources/v1",
             "packets_sha256": hashlib.sha256(raw).hexdigest(), "entries": {"tool.pool": "a" * 64},
             "profiles": {"default": ["tool.pool"], "framework-core": ["tool.pool"]}}
    examples = {"schema": "nsgablack.catalog.examples/v1", "publication_digest": "b" * 64,
                "entries": {"tool.pool": []}, "examples": {}, "issues": []}
    for name, content in (("knowledge-packets.json", raw), ("knowledge-sources.json", json.dumps(index).encode()),
                          ("examples.json", json.dumps(examples).encode())):
        (tmp_path / name).write_bytes(content)
    return [tmp_path / name for name in ("knowledge-packets.json", "knowledge-sources.json", "examples.json")]


def test_publication_loader_verifies_bound_entry_and_example_identity(tmp_path):
    paths = write_publication(tmp_path)
    source = reference.load_reference_source(*paths)
    assert source.available and source.publication_digest == "b" * 64
    assert reference.reference_search(source=source)["catalog_total"] == 1


@pytest.mark.parametrize("mutation", ["packet_digest", "entry_scope", "profile", "example_scope"])
def test_mismatched_publication_never_publishes_partial_directory(tmp_path, mutation):
    paths = write_publication(tmp_path)
    if mutation == "packet_digest":
        paths[0].write_bytes(paths[0].read_bytes() + b" ")
    elif mutation in {"entry_scope", "profile"}:
        index = json.loads(paths[1].read_bytes())
        if mutation == "entry_scope":
            index["entries"] = {}
        else:
            index["profiles"]["default"] = []
        paths[1].write_text(json.dumps(index))
    else:
        examples = json.loads(paths[2].read_bytes())
        examples["entries"] = {}
        paths[2].write_text(json.dumps(examples))
    with pytest.raises(ValueError):
        reference.load_reference_source(*paths)


def test_missing_publication_is_unavailable_and_can_refresh_when_files_appear(tmp_path, monkeypatch):
    monkeypatch.setenv("NSGABLACK_WORKSPACE_REFERENCE_ROOT", str(tmp_path))
    result = reference.reference_search()
    assert not result["available"] and not result["items"]
    assert reference.reference_detail("tool.pool") is None
    write_publication(tmp_path)
    assert reference.reference_search()["available"]


def test_reference_source_never_accepts_a_live_component_object():
    class Dangerous:
        def load(self):
            pytest.fail("load called")
    with pytest.raises(ValueError):
        reference.ReferenceSource([Dangerous()])


def test_duplicate_json_fields_are_not_silently_accepted(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text('{"schema":"a","schema":"b"}')
    with pytest.raises(ValueError, match="重复"):
        reference._read_json(path, 1000)


def _reference_ui_app(monkeypatch, source, *, compact=True, context=None):
    from nsgablack.catalog import lab_workspace_reference_ui as ui
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    monkeypatch.setattr(ui, "_test_reference_source", source, raising=False)
    return AppTest.from_string(f'''
import streamlit as st
from nsgablack.catalog import lab_workspace_reference_ui as ui
ui.render_reference_browser(st, source=ui._test_reference_source, compact={compact!r}, context={context!r})
''', default_timeout=15).run()


def test_compact_reference_puts_original_baseline_fields_then_code_and_preserves_full_guide(source, monkeypatch):
    source.entries["adapter.vns"]["use_when"] = ["已有精英解，需要邻域精修。"]
    snippet = source.examples["examples"]["focused.vns"]["snippets"][0]
    snippet["text"] = snippet["text"].replace("放在哪：Case adapter 工厂。",
        "放在哪：Case adapter 工厂。\n\n接入步骤：创建 VNSAdapter，再交给本 Case 的 solver。")
    before = deepcopy((source.entries, source.examples))
    app = _reference_ui_app(monkeypatch, source, context="cases/search/build_solver.py")
    assert not app.exception
    assert not app.get("column")
    assert not any("正在编辑：" in item.value for item in app.caption)
    assert [item.label for item in app.tabs] == ["接入", "完整用法", "参数与接口", "相关组件"]
    assert any(item.value == "已有精英解，需要邻域精修。" for item in app.markdown)
    first_tab = app.tabs[0]
    fields = [item.value for item in first_tab.get("markdown")]
    assert fields == ["**先准备什么** · 已评估的精英池。", "**放在哪** · Case adapter 工厂。",
                      "**接入步骤** · 创建 VNSAdapter，再交给本 Case 的 solver。"]
    full = app.tabs[1].get("markdown")
    assert any(item.value == reference.reference_detail("adapter.vns", source=source)["usage_markdown"].strip()
               for item in full)
    assert any("变体一：替换邻域" in item.value for item in full)
    assert any("adapter = VNSAdapter(k_max=3)" in item.value for item in first_tab.get("code"))
    ordered = [item.value if item.type in {"markdown", "code"} else item.label
               for item in first_tab if item.type in {"markdown", "code", "selectbox"}]
    assert ordered.index(fields[-1]) < next(i for i, text in enumerate(ordered)
                                          if "adapter = VNSAdapter(k_max=3)" in text)
    code_and_captions = [item.value for item in first_tab if item.type in {"code", "caption"}]
    assert next(i for i, text in enumerate(code_and_captions) if "adapter = VNSAdapter(k_max=3)" in text) < next(
        i for i, text in enumerate(code_and_captions) if "代码右上角可复制" in text)
    filters = next(item for item in app.expander if item.label == "筛选与收藏")
    hits = next(item for item in app.expander if item.label.startswith("搜索结果"))
    assert not filters.proto.expanded and not hits.proto.expanded
    assert any(item.label == "组件范围" for item in filters.get("selectbox"))
    tools = [item for item in app.get("popover")
             if any(button.label == "返回上一组件" for button in item.get("button"))]
    assert len(tools) == 1
    assert any(button.label == "收藏组件" for button in tools[0].get("button"))
    assert not any(item.label == "本次会话收藏" for item in app.expander)
    assert (source.entries, source.examples) == before


def test_compact_search_is_limited_to_six_and_can_select_correct_match(source, monkeypatch):
    calls = []
    search = reference.reference_search
    def read_search(*args, **kwargs):
        calls.append(kwargs["limit"])
        return search(*args, **kwargs)
    monkeypatch.setattr(reference, "reference_search", read_search)
    app = _reference_ui_app(monkeypatch, source)
    assert not app.exception and calls == [6]
    assert app.subheader[0].value == "VNSAdapter"
    app.text_input[0].set_value("Pool").run()
    assert not app.exception
    assert next(item for item in app.expander if item.label.startswith("搜索结果")).proto.expanded
    # Retaining the previous detail during a search is explicit; choosing a hit
    # must still open that hit rather than an old positional selection.
    next(item for item in app.button if item.label == "Pool").click().run()
    assert not app.exception
    assert app.subheader[0].value == "Pool"
    assert not next(item for item in app.expander if item.label.startswith("搜索结果")).proto.expanded
    assert any("elite = Pool(parent=members)" in item.value for item in app.code)
    assert all(limit == 6 for limit in calls)
    next(item for item in app.button if item.label == "返回上一组件").click().run()
    assert app.subheader[0].value == "VNSAdapter"
    next(item for item in app.button if item.label == "收藏组件").click().run()
    assert any(item.label == "取消收藏" for item in app.button)


def test_compact_many_matches_keep_only_six_result_buttons(monkeypatch):
    source = reference.ReferenceSource([
        {"key": f"tool.match_{i}", "title": f"MatchTool {i}", "kind": "tool"}
        for i in range(10)])
    app = _reference_ui_app(monkeypatch, source)
    app.text_input[0].set_value("MatchTool").run()
    assert not app.exception
    hits = [item for item in app.button if item.label.startswith("MatchTool ")]
    assert len(hits) == 6
    assert any("显示前 6 项" in item.label for item in app.expander)


def test_compact_unstructured_guide_has_full_usage_entry_and_never_truncates_code(source, monkeypatch):
    code = "from never_import.vns import VNSAdapter\n" + "# literal source line\n" * 40 + "adapter = VNSAdapter()"
    guide = "本指南没有已登记的准备或装配位置字段。\n\n```python\n" + code + "\n```\n\n完整尾注。"
    source.examples["examples"]["focused.vns"]["snippets"][0]["text"] = guide
    app = _reference_ui_app(monkeypatch, source)
    assert not app.exception
    assert any("完整用法" in item.value for item in app.tabs[0].get("caption"))
    assert app.tabs[0].get("code")[0].value == code
    assert app.tabs[1].get("markdown")[0].value == guide


def test_compact_fields_take_baseline_originals_without_variation_or_code_leaks():
    from nsgablack.catalog.lab_workspace_reference_ui import _compact_usage_fields
    guide = ("先准备什么：原始输入。\n\n放在哪：原始工厂。\n\n"
             "```python\nprint('接入步骤：不是说明')\n```\n\n"
             "### 变体一：另一种接法\n\n放在哪：另一处工厂。\n\n接入步骤：变体步骤。")
    assert _compact_usage_fields(guide) == [("先准备什么", "原始输入。"), ("放在哪", "原始工厂。")]


def test_default_reference_dialog_layout_preserves_parameters_relations_and_full_guide(source, monkeypatch):
    app = _reference_ui_app(monkeypatch, source, compact=False)
    assert not app.exception and app.get("column")
    assert any("先准备什么" in item.value for item in app.markdown)
    assert any(item.label == "可复制的用法片段" for item in app.selectbox)
    assert any(item.label == "Pool" for item in app.button)
    assert any(item.label == "tool.missing" and item.disabled for item in app.button)
    assert any("never_import.vns:VNSAdapter" in item.value for item in app.code)
    assert len(app.dataframe) == 1
def test_pin_component_reference_preserves_current_draft_and_query():
    from types import SimpleNamespace
    from nsgablack.catalog import lab_workspace_reference_ui as ui
    draft = {"changes": {"cases/search/change.py": "user draft"}}
    state = {"project_workspace::workspace": "workspace-a",
             "project_workspace::reference::open": True,
             "project_workspace::reference::query": "VNS",
             "project_workspace::drafts": {"workspace-a": draft}}
    ui._pin_to_workspace(SimpleNamespace(session_state=state))
    assert state["project_workspace::panel::workspace-a"] == "reference"
    assert state["project_workspace::reference::open"] is False
    assert state["project_workspace::reference::query"] == "VNS"
    assert state["project_workspace::drafts"]["workspace-a"] is draft


def test_pin_without_open_workspace_does_not_invent_a_target():
    from types import SimpleNamespace
    from nsgablack.catalog import lab_workspace_reference_ui as ui
    state = {"project_workspace::reference::open": True}
    ui._pin_to_workspace(SimpleNamespace(session_state=state))
    assert state == {"project_workspace::reference::open": True}
