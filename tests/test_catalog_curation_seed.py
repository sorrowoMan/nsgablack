"""Source-only extraction: fixtures are never imported or executed."""

from __future__ import annotations

import copy

import pytest

from catalog.curation_seed import bounded_source_guide_reference, extract_source_guide_seed


MAIN = '''## tool.example · 保留文件与调用位置

**什么时候用**：需要把正式宿主与叶组件一起接起来时。

**先准备什么**：保留现有 Project，先准备输入与资源授权。

**放在哪**：分别保存下面两个文件，不要合成一个模块。

**接入步骤**：先创建工厂，再在原 builder 中调用它。

```python
# cases/demo/component.py
def factory(value):
    return value ** 2
```

第二段保存在 `cases/demo/build_solver.py`；这里的 factory 从前一文件导入。

```python
# cases/demo/build_solver.py
from .component import factory

def build_solver(*, resource_context=None, component_overrides=None):
    return factory(3)
```

**怎样判断接对**：检查工厂输出与输入平方相同；这是源码说明，没有运行证明。

**运行入口**：使用已有 Project 的正式入口，先确认 Case 已被启用。

```bash
python run_project.py
```
'''

VARIANT = '''### 变体一：显式改变工厂规则

只替换 `cases/demo/component.py`，保留正式 builder 与运行入口。

```python
def factory(value):
    return value ** 3
```

输出改为立方；这不改变运行资源的所有者，也没有声称已验证算法效果。
'''


def example(text=MAIN + "\n" + VARIANT, **snippet_updates):
    snippet = {"path": "nsgablack/docs/catalog_usage/EXAMPLE_CN.md",
               "start_line": 11, "end_line": 80, "text": text,
               "complete": True, "sha256": "excerpt-digest", "file_sha256": "file-digest"}
    snippet.update(snippet_updates)
    return {"id": "example.guide", "binding": "focused", "kind": "documentation",
            "verification": {"status": "source_checked"}, "source_digest": "guide-digest",
            "snippets": [snippet]}


def test_migration_reference_cannot_be_used_as_an_active_tutorial_seed():
    item = {**example(), "usage_status": "migration_reference"}
    assert extract_source_guide_seed([item]) is None


def test_extract_preserves_exact_order_code_file_instructions_and_fields():
    item = example()
    original = copy.deepcopy(item)
    seed = extract_source_guide_seed([item])
    assert seed is not None
    assert item == original
    assert seed["reference_only"] is True
    assert seed["requires_generation_or_independent_review"] is True
    assert "verified" not in seed and "ok" not in seed
    assert seed["source_digest"] == "guide-digest"
    assert seed["main"]["markdown"] == MAIN + "\n"
    assert seed["variants"][0]["markdown"] == VARIANT
    assert list(seed["main"]["fields"]) == [
        "什么时候用", "先准备什么", "放在哪", "接入步骤", "怎样判断接对", "运行入口"]
    fragments = seed["main"]["code_fragments"]
    assert len(fragments) == 2
    assert fragments[0]["text"] == (
        "# cases/demo/component.py\ndef factory(value):\n    return value ** 2\n")
    assert fragments[0]["start_line"] == 22
    assert "前一文件导入" in seed["main"]["parts"][2]["text"]
    assert [part for part in seed["main"]["parts"] if part["kind"] == "code"][-1]["language"] == "bash"
    assert "Source guide:" in seed["main"]["code"]
    assert seed["main"]["code"].index("# cases/demo/component.py") < seed["main"]["code"].index("# cases/demo/build_solver.py")
    assert "resource_context=None" in seed["main"]["code"]
    assert seed["main"]["code_is_multi_fragment"] is True
    assert seed["sources"][0]["sha256"] == "excerpt-digest"


def test_fake_variation_heading_inside_code_does_not_split_source():
    text = MAIN.replace("return value ** 2", 'return """\n### 变体假：只是字符串\n"""') + "\n" + VARIANT
    seed = extract_source_guide_seed([example(text)])
    assert seed is not None
    assert len(seed["variants"]) == 1
    assert "变体假" in seed["main"]["code_fragments"][0]["text"]


@pytest.mark.parametrize("label", [
    "什么时候用", "先准备什么", "放在哪", "接入步骤", "怎样判断接对", "运行入口"])
def test_missing_any_explicit_teaching_field_is_not_completed(label):
    text = (MAIN + VARIANT).replace(f"**{label}**：", "说明：")
    assert extract_source_guide_seed([example(text)]) is None


@pytest.mark.parametrize("complete", [False, None, "true"])
def test_incomplete_or_unproven_excerpt_is_not_completed(complete):
    assert extract_source_guide_seed([example(complete=complete)]) is None


def test_missing_complete_marker_is_not_completed():
    guide = example()
    del guide["snippets"][0]["complete"]
    assert extract_source_guide_seed([guide]) is None


@pytest.mark.parametrize("marker", ["[...truncated...]", "source truncated", "内容已截断"])
def test_closed_fences_do_not_make_truncated_source_complete(marker):
    assert extract_source_guide_seed([example(MAIN + marker + "\n" + VARIANT)]) is None


@pytest.mark.parametrize("placeholder", [
    "结果检查说明待补充", "结果待补", "TODO", "得到已装配组件或回调返回值"])
def test_generic_placeholders_are_not_full_seed(placeholder):
    text = (MAIN + VARIANT).replace("检查工厂输出与输入平方相同", placeholder)
    assert extract_source_guide_seed([example(text)]) is None


@pytest.mark.parametrize("broken", [
    "return ...", "return (", "pass", "import framework_that_does_not_exist"])
def test_main_must_have_substantive_complete_python(broken):
    simple = MAIN[:MAIN.index("```python")] + "```python\n" + broken + "\n```\n"
    simple += "\n**怎样判断接对**：检查明确返回值。\n\n**运行入口**：从现有正式入口调用。\n"
    assert extract_source_guide_seed([example(simple + VARIANT)]) is None


def test_unclosed_fence_cannot_use_heading_to_fake_variant():
    assert extract_source_guide_seed([example(MAIN + VARIANT.replace("```\n\n输出", "\n\n输出"))]) is None


@pytest.mark.parametrize("variant", [
    "", "### 变体一：空标题\n", "### 变体一：只有代码\n```python\nvalue = 9\n```\n",
    "### 变体一：只有文字\n这里讲了完整改动位置和用途，但没有给出实际代码。\n"])
def test_at_least_one_code_and_prose_variant_is_required(variant):
    assert extract_source_guide_seed([example(MAIN + variant)]) is None


def test_renamed_identical_code_is_not_a_substantive_variant():
    same = VARIANT.replace("def factory(value):\n    return value ** 3",
                           "# cases/demo/component.py\ndef factory(value):\n    return value ** 2")
    assert extract_source_guide_seed([example(MAIN + same)]) is None


def test_code_is_only_parsed_not_run(tmp_path):
    target = tmp_path / "must-not-exist.txt"
    text = MAIN.replace("return value ** 2", f"raise RuntimeError({str(target)!r})") + VARIANT
    seed = extract_source_guide_seed([example(text)])
    assert seed is not None
    assert not target.exists()


def test_selected_guide_is_not_replaced_by_a_weaker_fallback():
    bad = example(complete=False)
    weak = example()
    weak["id"] = "weaker"
    weak["verification"]["status"] = "unverified"
    assert extract_source_guide_seed([weak, bad]) is None


def test_referenced_or_non_documentation_examples_do_not_seed():
    guide = example()
    guide["binding"] = "related"
    assert extract_source_guide_seed([guide]) is None
    guide = example()
    guide["kind"] = "code"
    assert extract_source_guide_seed([guide]) is None


def packet_for(guide):
    snippet = guide["snippets"][0]
    return {"source_digest": "original-packet-digest", "evidence": [{
        "id": "e2", "path": snippet["path"], "file_sha256": snippet["file_sha256"],
        "start_line": snippet["start_line"],
        "end_line": snippet["start_line"] + len(snippet["text"].splitlines()) - 1,
        "text": snippet["text"],
    }]}


def test_bounded_reference_preserves_only_main_and_one_variant_without_mutation():
    second = VARIANT.replace("变体一", "变体二").replace("value ** 3", "value ** 4")
    guide = example(MAIN + VARIANT + "\n" + second)
    packet = packet_for(guide)
    original = copy.deepcopy((guide, packet))
    reference = bounded_source_guide_reference(packet, [guide])
    assert reference is not None
    assert (guide, packet) == original
    assert reference["reference_only"] is True
    assert reference["evidence_ids"] == ["e2"]
    assert len(reference["variants"]) == 1
    assert reference["variants"][0]["title"] == "变体一：显式改变工厂规则"
    assert "markdown" not in reference["main"] and "code" not in reference["main"]
    for section in (reference["main"], reference["variants"][0]):
        for part in section["parts"]:
            assert part["file_sha256"] == "file-digest"
            assert part["start_line"] <= part["end_line"]
            assert part["evidence_ids"] == ["e2"]
    assert reference["main"]["fields"]["接入步骤"] == ["先创建工厂，再在原 builder 中调用它。"]


@pytest.mark.parametrize("field,value", [
    ("path", "nsgablack/docs/OTHER.md"), ("file_sha256", "different-version"),
    ("start_line", 12), ("end_line", 20), ("id", ""),
])
def test_bounded_reference_requires_path_digest_full_ranges_and_existing_id(field, value):
    guide = example()
    packet = packet_for(guide)
    packet["evidence"][0][field] = value
    assert bounded_source_guide_reference(packet, [guide]) is None


def test_same_file_digest_does_not_allow_unquoted_variant_tail():
    guide = example()
    packet = packet_for(guide)
    # A real bounded excerpt has a corrected end_line; same full-file digest
    # cannot authorize the complete original variant below this boundary.
    evidence = packet["evidence"][0]
    evidence["text"] = MAIN + VARIANT[:VARIANT.index("```python")]
    evidence["end_line"] = evidence["start_line"] + len(evidence["text"].splitlines()) - 1
    assert bounded_source_guide_reference(packet, [guide]) is None


def test_bounded_reference_checks_literal_text_even_when_claimed_lines_match():
    guide = example()
    packet = packet_for(guide)
    packet["evidence"][0]["text"] = packet["evidence"][0]["text"].replace("value ** 3", "value ** 9")
    assert bounded_source_guide_reference(packet, [guide]) is None


def test_bounded_reference_checks_missing_text_even_when_end_line_is_overstated():
    guide = example()
    packet = packet_for(guide)
    evidence = packet["evidence"][0]
    evidence["text"] = evidence["text"][:evidence["text"].index("### 变体")]
    assert bounded_source_guide_reference(packet, [guide]) is None


def test_bounded_reference_requires_main_prose_not_only_covered_code():
    guide = example()
    packet = packet_for(guide)
    evidence = packet["evidence"][0]
    lines = evidence["text"].splitlines(keepends=True)
    cut = next(index for index, line in enumerate(lines) if line.startswith("```python"))
    evidence["text"] = "".join(lines[cut:])
    evidence["start_line"] += cut
    assert bounded_source_guide_reference(packet, [guide]) is None


def test_first_complete_variant_can_be_covered_by_a_different_existing_excerpt():
    second = VARIANT.replace("变体一", "变体二").replace("value ** 3", "value ** 4")
    guide = example(MAIN + VARIANT + "\n" + second)
    packet = packet_for(guide)
    all_lines = guide["snippets"][0]["text"].splitlines(keepends=True)
    first = packet["evidence"][0]
    first["text"] = MAIN
    first["end_line"] = first["start_line"] + len(MAIN.splitlines()) - 1
    second_index = next(index for index, line in enumerate(all_lines) if line.startswith("### 变体二"))
    packet["evidence"].append({**first, "id": "e9", "start_line": 11 + second_index,
                               "end_line": 10 + len(all_lines), "text": "".join(all_lines[second_index:])})
    reference = bounded_source_guide_reference(packet, [guide])
    assert reference is not None
    assert reference["variants"][0]["title"].startswith("变体二")
    assert reference["evidence_ids"] == ["e2", "e9"]


def test_each_whole_part_must_be_contained_in_one_excerpt():
    guide = example()
    packet = packet_for(guide)
    full = packet["evidence"][0]
    lines = full["text"].splitlines(keepends=True)
    cut = 3  # splits the first prose part, even though the union has all lines
    packet["evidence"] = [
        {**full, "text": "".join(lines[:cut]), "end_line": full["start_line"] + cut - 1},
        {**full, "id": "e3", "text": "".join(lines[cut:]), "start_line": full["start_line"] + cut},
    ]
    assert bounded_source_guide_reference(packet, [guide]) is None


def test_only_line_endings_align_and_returned_parts_are_literal_packet_text():
    guide = example((MAIN + VARIANT).rstrip("\n"))
    packet = packet_for(guide)
    evidence = packet["evidence"][0]
    evidence["text"] = (evidence["text"] + "\n").replace("\n", "\r\n")
    reference = bounded_source_guide_reference(packet, [guide])
    assert reference is not None
    lines = evidence["text"].splitlines(keepends=True)
    for section in (reference["main"], reference["variants"][0]):
        for part in section["parts"]:
            original = "".join(lines[part["start_line"] - evidence["start_line"]:
                                     part["end_line"] - evidence["start_line"] + 1])
            assert part["text"] == original
            assert "\r\n" in part["text"]


@pytest.mark.parametrize("replacement", ["value ** 9", "value  ** 3", "value\r ** 3"])
def test_line_ending_alignment_does_not_tolerate_content_or_space_changes(replacement):
    guide = example()
    packet = packet_for(guide)
    evidence = packet["evidence"][0]
    evidence["text"] = evidence["text"].replace("value ** 3", replacement).replace("\n", "\r\n")
    assert bounded_source_guide_reference(packet, [guide]) is None


def test_line_ending_alignment_does_not_extend_declared_excerpt_range():
    guide = example((MAIN + VARIANT).rstrip("\n"))
    packet = packet_for(guide)
    evidence = packet["evidence"][0]
    evidence["text"] = (evidence["text"] + "\n").replace("\n", "\r\n")
    evidence["end_line"] -= 1
    assert bounded_source_guide_reference(packet, [guide]) is None
