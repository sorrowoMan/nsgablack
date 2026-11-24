"""Authored reading links stay distinct from inferred assembly dependencies."""
from copy import deepcopy

import pytest

from nsgablack.catalog.usage_navigation import documentation_reference_groups, render_documentation_navigation


def _record(key, path, text, **extra):
    return {"component_keys": [key], "binding": "focused", "kind": "documentation",
            "verification": {"status": "source_checked"},
            "snippets": [{"path": path, "text": text, "complete": True}], **extra}


def _index(link="[固定符号](FIXED.md)"):
    intro = "**先准备什么：** 有效输入。\n\n**放在哪：** Case工厂。\n\n"
    examples = {
        "old": _record("old", "mlblack/docs/usage/LEGACY.md", intro + link,
                       usage_status="migration_reference"),
        "a": _record("model.a", "mlblack/docs/usage/FIXED.md", "## model.a · 固定表达式\n正文"),
        "b": _record("problem.b", "mlblack/docs/usage/FIXED.md", "## problem.b · 固定评估\n正文"),
        "other": _record("other", "nsgablack/docs/usage/FIXED.md", "## other\n不同框架"),
    }
    return {"entries": {value["component_keys"][0]: [identifier] for identifier, value in examples.items()},
            "examples": examples, "issues": []}


def test_exact_document_link_has_all_bound_chapters_and_preserves_framework():
    result = documentation_reference_groups(_index(), "old")
    assert result == ({"label": "固定符号", "path": "mlblack/docs/usage/FIXED.md", "anchor": "",
                       "keys": ("model.a", "problem.b")},)


@pytest.mark.parametrize("anchor", ["model.a", "modela--固定表达式", "modela--%E5%9B%BA%E5%AE%9A%E8%A1%A8%E8%BE%BE%E5%BC%8F"])
def test_explicit_anchor_resolves_only_the_containing_chapter(anchor):
    result = documentation_reference_groups(_index(f"[表达式](FIXED.md#{anchor})"), "old")
    assert result[0]["keys"] == ("model.a",)


@pytest.mark.parametrize("link", [
    "model.a 是一个提到的词，不是链接。", "`[固定](FIXED.md)`",
    "```python\nx = '[固定](FIXED.md)'\n```", "![图片](FIXED.md)",
    "[外部](https://example.com/FIXED.md)", "[外部](//example.com/FIXED.md)",
    "[源码](factory.py)", "[不存在](ABSENT.md)", "[未知章节](FIXED.md#unknown)",
    "[非法](../../../../private/FIXED.md)", "[不猜参数](FIXED.md?chapter=a)",
])
def test_prose_code_external_and_unresolvable_links_do_not_invent_relationships(link):
    assert documentation_reference_groups(_index(link), "old") == ()


@pytest.mark.parametrize("change", ["unverified", "incomplete", "declared", "issue", "unbound"])
def test_destination_requires_verified_focused_bound_source(change):
    index = _index("[表达式](FIXED.md#model.a)")
    target = index["examples"]["a"]
    if change == "unverified":
        target["verification"]["status"] = "unverified"
    elif change == "incomplete":
        target["snippets"][0]["complete"] = False
    elif change == "declared":
        target["binding"] = "declared"
    elif change == "issue":
        index["issues"] = [{"example_id": "a", "error": "source mismatch"}]
    else:
        index["entries"]["model.a"] = []
    assert documentation_reference_groups(index, "old") == ()


def test_bad_selected_guide_cannot_lend_links_from_another_unselected_example():
    index = _index()
    index["issues"] = [{"example_id": "old", "error": "source mismatch"}]
    assert documentation_reference_groups(index, "old") == ()


def test_same_document_fragment_and_parent_paths_resolve_without_reading_disk():
    index = _index("[其它章节](#model.a) [跨框架](../../../nsgablack/docs/usage/FIXED.md)")
    index["examples"]["a"]["snippets"][0]["path"] = "mlblack/docs/usage/LEGACY.md"
    assert [group["keys"] for group in documentation_reference_groups(index, "old")] == [("model.a",), ("other",)]


def test_shared_host_continuation_does_not_turn_its_book_into_another_tutorial_entry():
    index = _index("[固定](FIXED.md) [函数池](POOL.md)")
    record = _record("pool", "mlblack/docs/usage/POOL.md", "## pool\n主章节")
    record["snippets"].append({"path": "mlblack/docs/usage/FIXED.md", "text": "## shared.host\n共享builder", "complete": True})
    index["examples"]["pool"] = record
    index["entries"]["pool"] = ["pool"]
    groups = documentation_reference_groups(index, "old")
    assert [group["keys"] for group in groups] == [("model.a", "problem.b"), ("pool",)]


class View:
    def __init__(self):
        self.buttons, self.captions, self.markdowns = [], [], []

    def markdown(self, value, **kwargs):
        assert kwargs.get("unsafe_allow_html") is False
        self.markdowns.append(value)

    def caption(self, value):
        self.captions.append(value)

    def expander(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def button(self, label, **kwargs):
        self.buttons.append((label, kwargs))


def test_current_scope_limits_destinations_and_callback_preserves_navigation():
    index = _index("[固定](FIXED.md) [重复](FIXED.md#model.a)")
    original = deepcopy(index)
    view, clicked = View(), []
    entry = {"key": "old"}
    def navigate(**kwargs):
        clicked.append(kwargs)
    render_documentation_navigation(view, entry=entry, index=index,
                                    available_entries=[{"key": "model.a", "kind": "model", "title": "表达式"}],
                                    on_navigate=navigate, navigation_kwargs={"current_entry": entry})
    assert len(view.buttons) == 1 and "model.a" in view.buttons[0][0]
    options = view.buttons[0][1]
    assert options["key"].endswith("::old::model.a")
    options["on_click"](**options["kwargs"])
    assert clicked == [{"current_entry": entry, "target_key": "model.a", "target_kind": "model", "detail_tab": "overview"}]
    assert "不表示组件等价" in view.captions[0]
    assert index == original


def test_no_visible_destination_adds_no_empty_navigation_block():
    view = View()
    render_documentation_navigation(view, entry={"key": "old"}, index=_index(),
                                    available_entries=[], on_navigate=None, navigation_kwargs={})
    assert not view.buttons and not view.markdowns and not view.captions
