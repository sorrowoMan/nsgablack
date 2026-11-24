"""Stable Markdown section selectors are source readers, never code runners."""
import builtins
import hashlib

import pytest

from nsgablack.catalog.examples import ExampleValidationError, _snippet, build_example_index, load_example_index


@pytest.fixture
def section_source(tmp_path):
    root = tmp_path / "nsgablack"
    (root / "docs").mkdir(parents=True)
    path = root / "docs/usage.md"
    path.write_text(
        "# 组件使用书\n\n## adapter.before · 前一组件\n前一组件正文。\n\n"
        "## `adapter.target` · 目标组件\n目标输入。\n\n"
        "### 更细的接线\n目标内部说明。\n\n"
        "```python\nimport must_never_import\n## adapter.target · 围栏中的假标题\n```\n\n"
        "~~~text\n## adapter.next · 另一种围栏的假标题\n~~~\n\n"
        "目标输出。\n\n## adapter.next · 下一组件\n下一组件正文。\n",
        encoding="utf-8")
    return {"nsgablack": root}, path


def test_selector_covers_nested_content_ignores_fenced_headings_and_stops_at_next_card(section_source):
    roots, path = section_source
    source = {"path": "nsgablack/docs/usage.md", "section": "adapter.target"}
    selected = _snippet(roots, source)
    assert selected["text"].startswith("## `adapter.target` · 目标组件")
    assert "目标输入" in selected["text"] and "目标输出" in selected["text"]
    assert "### 更细的接线" in selected["text"]
    assert "围栏中的假标题" in selected["text"] and "另一种围栏的假标题" in selected["text"]
    assert "前一组件正文" not in selected["text"] and "下一组件正文" not in selected["text"]
    assert selected["sha256"] == hashlib.sha256(selected["text"].encode()).hexdigest()
    assert selected["complete"] is True
    lines = path.read_text(encoding="utf-8").splitlines()
    assert "\n".join(lines[selected["start_line"] - 1:selected["end_line"]]) == selected["text"]


def test_inserting_earlier_sections_moves_line_numbers_without_switching_component(section_source):
    roots, path = section_source
    source = {"path": "nsgablack/docs/usage.md", "section": "adapter.target"}
    before = _snippet(roots, source)
    prefix = "## adapter.inserted · 新组件\n新组件的长说明。\n\n### 内部步骤\n不要串到目标卡。\n\n"
    path.write_text(prefix + path.read_text(encoding="utf-8"), encoding="utf-8")
    after = _snippet(roots, source)
    assert after["text"] == before["text"] and after["sha256"] == before["sha256"]
    assert after["file_sha256"] != before["file_sha256"]
    assert after["start_line"] == before["start_line"] + len(prefix.splitlines())
    assert after["end_line"] == before["end_line"] + len(prefix.splitlines())


@pytest.mark.parametrize("selector", ["adapter.missing", "adapter.targ"])
def test_missing_selector_or_partial_key_is_rejected(section_source, selector):
    roots, _ = section_source
    with pytest.raises(ExampleValidationError, match="example_source_section_missing_or_ambiguous"):
        _snippet(roots, {"path": "nsgablack/docs/usage.md", "section": selector})


def test_duplicate_actual_heading_is_rejected_even_at_different_depth(section_source):
    roots, path = section_source
    path.write_text(path.read_text(encoding="utf-8") + "\n### `adapter.target` · 重复组件\n正文。\n", encoding="utf-8")
    with pytest.raises(ExampleValidationError, match="example_source_section_missing_or_ambiguous"):
        _snippet(roots, {"path": "nsgablack/docs/usage.md", "section": "adapter.target"})


@pytest.mark.parametrize("extra", [{"symbol": "build"}, {"symbol": None}, {"start_line": 1}, {"end_line": 3},
                                   {"start_line": 1, "end_line": 2}])
def test_section_cannot_be_combined_with_symbol_or_line_coordinates(section_source, extra):
    roots, _ = section_source
    with pytest.raises(ExampleValidationError, match="example_source_section_invalid"):
        _snippet(roots, {"path": "nsgablack/docs/usage.md", "section": "adapter.target", **extra})


@pytest.mark.parametrize("selector", ["", 4, False, "adapter.target extra"])
def test_section_requires_a_valid_component_identifier(section_source, selector):
    roots, _ = section_source
    with pytest.raises(ExampleValidationError, match="example_source_section_invalid"):
        _snippet(roots, {"path": "nsgablack/docs/usage.md", "section": selector})


def test_source_index_uses_the_section_and_never_imports_its_code(section_source, monkeypatch, tmp_path):
    roots, _ = section_source
    root = roots["nsgablack"]
    (root / "catalog/entries").mkdir(parents=True)
    (root / "catalog/entries/component.toml").write_text('[[entry]]\nkey="adapter.target"\n', encoding="utf-8")
    (root / "catalog/example_manifests").mkdir()
    (root / "catalog/example_manifests/usage.toml").write_text('''
[[example]]
id="target.usage"
component_keys=["adapter.target"]
kind="documentation"
sources=[{path="nsgablack/docs/usage.md",section="adapter.target"}]
''', encoding="utf-8")
    original = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "must_never_import":
            raise AssertionError("Indexing imported documentation code")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    destination = tmp_path / "index.json"
    report = build_example_index(roots, destination)
    record = load_example_index(destination)["examples"]["target.usage"]
    assert report["with_examples"] == 1
    assert record["verification"]["status"] == "source_checked"
    assert "目标输入" in record["snippets"][0]["text"]
    assert "下一组件正文" not in record["snippets"][0]["text"]
