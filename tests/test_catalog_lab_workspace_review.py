"""Draft review never executes code and offers only an exact, fresh edit."""
import ast
from copy import deepcopy
import hashlib

import pytest

from nsgablack.catalog.lab_workspace_project import MAX_OUTLINE_SOURCE_CHARS
from nsgablack.catalog.lab_workspace_review import apply_source_fix, review_source


@pytest.mark.parametrize(("before", "after", "line"), [
    ("def choose(pool)\n    return pool\n", "def choose(pool):\n    return pool\n", 1),
    ("if ready  # keep this comment\n    pass\n", "if ready:  # keep this comment\n    pass\n", 1),
    ('if label == "# still a string" # actual comment\n    pass\n',
     'if label == "# still a string": # actual comment\n    pass\n', 1),
    ("if ready\t # trailing spaces  \n    pass\n", "if ready:\t # trailing spaces  \n    pass\n", 1),
    ("\ufeffdef 选择(pool) # 中文注释\r\n    return pool\r\n",
     "\ufeffdef 选择(pool): # 中文注释\r\n    return pool\r\n", 1),
    ("if ready\r    pass\r", "if ready:\r    pass\r", 1),
    ("if (\n    ready\n) # final line\n    pass\n", "if (\n    ready\n): # final line\n    pass\n", 3),
    ("if ready\n\f    pass\n", "if ready:\n\f    pass\n", 1),
    ("class Search\n    pass", "class Search:\n    pass", 1),
])
def test_missing_colon_is_a_single_exact_edit(before, after, line):
    reviewed = review_source("cases/search/adapter/change.py", before)
    assert reviewed["syntax_ok"] is False
    assert len(reviewed["fixes"]) == 1
    fix = reviewed["fixes"][0]
    assert fix["line"] == line and fix["after_text"] == after
    assert fix["before_digest"] == hashlib.sha256(before.encode("utf-8")).hexdigest()
    assert fix["before_digest"] == reviewed["before_digest"]
    assert "--- 草稿（修复前）" in fix["diff"]
    assert "+++ 草稿（补冒号后）" in fix["diff"]
    assert len(after) == len(before) + 1
    ast.parse(after.removeprefix("\ufeff"))
    assert apply_source_fix(before, fix) == after
    assert reviewed["syntax_ok"] is False  # proposal does not rewrite review state


def test_diagnostic_preserves_the_actual_python_line_column_and_message():
    source = "# 当前草稿\ndef choose(pool) # 缺冒号\n    return pool\n"
    with pytest.raises(SyntaxError) as caught:
        ast.parse(source)
    diagnostic = review_source("change.py", source)["diagnostics"][0]
    assert diagnostic == {"code": "python-syntax-error", "line": caught.value.lineno,
                          "column": caught.value.offset, "message": caught.value.msg}


@pytest.mark.parametrize("source", [
    "def choose(:\n    pass\n",
    'label = "unterminated\n',
    "if ready\npass\n",  # adding a colon does not invent indentation
    "if ready\n    pass\nif other\n    pass\n",  # another missing colon remains
    "if ready\n    broken(\n",  # complete candidate still does not parse
    "    pass\n",
])
def test_other_or_multiple_syntax_failures_have_no_automatic_fix(source):
    reviewed = review_source("change.py", source)
    assert reviewed["syntax_ok"] is False
    assert reviewed["fixes"] == []


def test_valid_source_preserves_static_assembly_clues_without_false_execution_claim():
    source = ("from nsgablack.adapters.search_plan import serial as sequence\n"
              "# adapter.set_change(fake)\n"
              "message = \"expected ':' and adapter.set_selector(fake)\"\n"
              "def build_solver():\n"
              "    adapter.set_change(change)\n"
              "    return sequence(stage('ga'), stage('vns'))\n")
    reviewed = review_source("build_solver.py", source)
    assert reviewed["syntax_ok"] is True and reviewed["fixes"] == []
    assert reviewed["diagnostics"] == []
    assert reviewed["scope"] == "static_source"
    assert "不证明" in reviewed["scope_note"]
    calls = reviewed["calls"]
    assert next(row for row in calls if row["name"] == "adapter.set_change")["line"] == 5
    assert next(row for row in calls if row["name"] == "sequence")["canonical_name"].endswith(".serial")
    assert all(row["line"] not in {2, 3} for row in calls)


def test_review_and_apply_never_import_or_execute_the_reviewed_source(tmp_path, monkeypatch):
    marker = tmp_path / "must-not-exist"
    source = ("import module_that_does_not_exist_for_this_draft\n"
              f"__import__('pathlib').Path({str(marker)!r}).write_text('executed')\n"
              "if ready # only text is repaired\n    pass\n")
    import builtins
    original_import = builtins.__import__
    def reject_component_import(name, *args, **kwargs):
        if name.startswith(("nsgablack.adapters", "nsgablack.units", "nsgablack.core")):
            raise AssertionError("review must not import a component")
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", reject_component_import)
    reviewed = review_source("change.py", source)
    assert len(reviewed["fixes"]) == 1
    repaired = apply_source_fix(source, reviewed["fixes"][0])
    assert "if ready:" in repaired
    assert not marker.exists()


def test_current_draft_digest_must_match_exactly():
    source = "if ready\n    pass\n"
    fix = review_source("change.py", source)["fixes"][0]
    with pytest.raises(ValueError, match="草稿已改变"):
        apply_source_fix(source + "# new edit\n", fix)
    with pytest.raises(ValueError, match="草稿已改变"):
        apply_source_fix(source.replace("\n", "\r\n"), fix)


@pytest.mark.parametrize("field,value", [
    ("after_text", "import os\n"), ("line", 2), ("kind", "replace"), ("diff", "fake preview"),
])
def test_changed_suggestion_cannot_become_an_arbitrary_text_replacement(field, value):
    source = "if ready\n    pass\n"
    fix = deepcopy(review_source("change.py", source)["fixes"][0])
    fix[field] = value
    with pytest.raises(ValueError, match="确定性修复不一致"):
        apply_source_fix(source, fix)


def test_non_python_and_oversized_text_have_no_fixes():
    reviewed = review_source("README.md", "def choose(pool)\n    return pool\n")
    assert reviewed["kind"] == "text" and reviewed["syntax_ok"] is None
    assert reviewed["fixes"] == [] and reviewed["calls"] == []
    reviewed = review_source("large.py", "#" * (MAX_OUTLINE_SOURCE_CHARS + 1))
    assert reviewed["syntax_ok"] is None and reviewed["fixes"] == []
    assert reviewed["diagnostics"][0]["code"] == "source-outline-too-large"


def test_invalid_fix_inputs_are_rejected_without_running_anything():
    with pytest.raises(ValueError):
        apply_source_fix(None, {})
    with pytest.raises(ValueError):
        apply_source_fix("pass\n", None)
    with pytest.raises(ValueError):
        apply_source_fix("pass\n", {"before_digest": hashlib.sha256(b"pass\n").hexdigest()})
