from __future__ import annotations

import hashlib
import json

import pytest

from nsgablack.catalog.examples import (
    ExampleValidationError,
    RECEIPTS_SCHEMA,
    build_example_index,
    load_example_index,
    validate_example_index,
)


PUBLICATION = "a" * 64


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "nsgablack"
    declarations = root / "catalog/entries"
    declarations.mkdir(parents=True)
    (declarations / "toy.toml").write_text(
        '[[entry]]\nkey="adapter.toy"\nexample_entry="python examples/project/run_project.py"\n'
        '[[entry]]\nkey="tool.documentation"\nexample_entry="docs/guide.md"\n'
        '[[entry]]\nkey="tool.query"\nexample_entry="python -m nsgablack catalog search toy"\n'
        '[[entry]]\nkey="tool.broken"\nexample_entry="python examples/missing.py"\n', encoding="utf-8")
    project = root / "examples/project"
    project.mkdir(parents=True)
    (project / "run_project.py").write_text('raise RuntimeError("source must never execute")\n', encoding="utf-8")
    (project / "project_config.py").write_text('MODE = "first"\n', encoding="utf-8")
    (project / "workflow.py").write_text(
        'raise RuntimeError("source must never import")\n\n'
        'def assemble(size=4):\n    return {"size": size}\n', encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs/guide.md").write_text("# 使用说明\n仅是文档，不是执行记录。\n", encoding="utf-8")
    manifest = root / "catalog/example_manifests"
    manifest.mkdir()
    (manifest / "toy.toml").write_text(
        '[[example]]\nid="toy"\ntitle="实际装配示例"\ncomponent_keys=["adapter.toy"]\n'
        'kind="project"\nworking_directory="nsgablack"\n'
        'run_command="python examples/project/run_project.py"\n'
        'inputs=["4个种子"]\nexpected_outputs=["结果由实际运行确认"]\n'
        'sources=[{path="nsgablack/examples/project/workflow.py", symbol="assemble"}]\n', encoding="utf-8")
    return {"nsgablack": root}, tmp_path / "index.json", manifest / "toy.toml"


def build(source, receipts=None, publication=PUBLICATION):
    roots, index_path, _ = source
    report = build_example_index(roots, index_path, receipts, publication_digest=publication)
    return report, load_example_index(index_path)


def write_receipt(source, record, **updates):
    value = {"example_id": record["id"], "status": "executed", "source_digest": record["source_digest"],
             "publication_digest": record["publication_digest"], "command": record["run_command"],
             "exit_code": 0, "executed_at": "2026-10-22T12:00:00+08:00",
             "observed_outputs": ["Case toy完成；步数=3；求值数=4。"], "output_sha256": "b" * 64}
    value.update(updates)
    path = source[1].parent / "receipts.json"
    path.write_text(json.dumps({"schema": RECEIPTS_SCHEMA, "receipts": [value]}), encoding="utf-8")
    return path


def test_migration_declaration_is_source_bound_and_survives_index_validation(source):
    manifest = source[2]
    with manifest.open("a", encoding="utf-8") as output:
        output.write('\n[[example]]\nid="legacy-guide"\ncomponent_keys=["tool.documentation"]\n'
                     'kind="documentation"\nusage_status="migration_reference"\n'
                     'sources=[{path="nsgablack/docs/guide.md", start_line=1, end_line=2}]\n')
    _, index = build(source)
    record = index["examples"]["legacy-guide"]
    assert record["usage_status"] == "migration_reference"
    assert record["verification"] == {"status": "source_checked"}
    assert validate_example_index(index) == index


@pytest.mark.parametrize("status", ["ready", "migration", None, [], 1])
def test_invalid_usage_status_fails_before_publication(source, status):
    from nsgablack.catalog.examples import _base_record

    spec = {"id": "invalid-guide", "component_keys": ["tool.documentation"],
            "kind": "documentation", "usage_status": status}
    with pytest.raises(ExampleValidationError, match="usage_status_invalid"):
        _base_record(spec, source[0], None)


def test_migration_cannot_declare_the_original_component_executed(source):
    from nsgablack.catalog.examples import _base_record

    spec = {"id": "invalid-guide", "component_keys": ["tool.documentation"],
            "kind": "documentation", "usage_status": "migration_reference",
            "run_command": "python examples/project/run_project.py"}
    with pytest.raises(ExampleValidationError, match="usage_status_invalid"):
        _base_record(spec, source[0], None)


def test_static_builder_finds_real_excerpt_without_import_or_execution(source):
    report, index = build(source)
    example = index["examples"]["toy"]
    assert report["ok"] and report["components"] == 4
    assert example["origin"] == "manifest"
    assert example["verification"] == {"status": "source_checked"}
    snippet = example["snippets"][0]
    assert (snippet["start_line"], snippet["end_line"]) == (3, 4)
    assert snippet["text"] == 'def assemble(size=4):\n    return {"size": size}'
    assert snippet["sha256"] == hashlib.sha256(snippet["text"].encode()).hexdigest()
    assert str(source[0]["nsgablack"]) not in json.dumps(index)
    assert index["entries"]["adapter.toy"][0] == "toy"
    assert "nsgablack/examples/project/project_config.py" in example["source_files"]


def test_excerpt_preserves_real_trailing_blank_source_line(source):
    doc = source[0]["nsgablack"] / "docs/guide.md"
    doc.write_text("# 使用说明\n正文\n\n", encoding="utf-8")
    _, index = build(source)
    record = index["examples"][index["entries"]["tool.documentation"][0]]
    assert record["snippets"][0]["text"] == "# 使用说明\n正文\n"
    assert record["snippets"][0]["end_line"] == 3


def _section_manifest(source, text):
    (source[0]["nsgablack"] / "docs/guide.md").write_text(text, encoding="utf-8")
    with source[2].open("a", encoding="utf-8") as stream:
        stream.write('[[example]]\nid="complete.section"\ncomponent_keys=["tool.documentation"]\n'
                     'kind="documentation"\n'
                     'sources=[{path="nsgablack/docs/guide.md", section="tool.documentation"}]\n')


def test_explicit_component_section_keeps_multifile_baseline_and_late_variations_past_120_lines(source):
    from nsgablack.catalog.usage_learning import documentation_baseline_code, documentation_variations, snippet_parts

    section = ("## tool.documentation\n\n**先准备什么：** 保留已有宿主。\n\n**放在哪：** Case工厂。\n"
               "\n**接入步骤：** 先装配再观察。\n\n```python\ndef build_solver():\n    return 'builder'\n```\n"
               + "\n" * 125
               + "### 第二个文件\n```python\ndef build_model():\n    return 'model'\n```\n"
                 "\n**怎样判断接对：** 读取正式结果。\n\n### 变体一\n替换模型工厂。\n"
                 "```python\ndef other_model():\n    return 'variant one'\n```\n"
                 "\n### 变体二\n替换输入工厂。\n```python\ndef other_input():\n    return 'variant two'\n```\n\n")
    text = "# 使用说明\n" + section + "## other.component\n不能混入下一个组件。\n"
    _section_manifest(source, text)
    _, index = build(source)
    snippet = index["examples"]["complete.section"]["snippets"][0]
    assert snippet["complete"] is True and snippet["end_line"] - snippet["start_line"] > 120
    assert snippet["text"] == "\n".join(text.splitlines()[snippet["start_line"] - 1:snippet["end_line"]])
    assert "other.component" not in snippet["text"]
    assert len(documentation_baseline_code(snippet)) == 2
    assert len(documentation_variations([snippet])) == 2
    assert [part[1] for part in snippet_parts(snippet) if part[0] == "code"][-1].endswith("return 'variant two'")
    assert validate_example_index(index) == index


@pytest.mark.parametrize("problem", ["lines", "characters", "unclosed_fence"])
def test_explicit_section_refuses_overbound_or_unclosed_code_instead_of_publishing_half_a_block(source, problem):
    from nsgablack.catalog.examples import MAX_SECTION_LINES

    body = {"lines": "\n" * MAX_SECTION_LINES, "characters": "x" * 8001,
            "unclosed_fence": "```python\nvalue = 'not a complete code block'\n"}[problem]
    _section_manifest(source, "## tool.documentation\n" + body)
    with pytest.raises(ExampleValidationError, match="section_oversized|section_fence_unclosed"):
        build(source)


def test_ordinary_python_symbol_retains_the_existing_120_line_excerpt_limit(source):
    workflow = source[0]["nsgablack"] / "examples/project/workflow.py"
    workflow.write_text("def assemble():\n" + "    # ordinary source remains a key excerpt\n" * 150
                        + "    return 'after the ordinary excerpt limit'\n", encoding="utf-8")
    _, index = build(source)
    snippet = index["examples"]["toy"]["snippets"][0]
    assert snippet["complete"] is False and snippet["end_line"] - snippet["start_line"] == 119
    assert "after the ordinary excerpt limit" not in snippet["text"]


def test_declared_docs_references_and_missing_sources_remain_transparent(source):
    _, index = build(source)
    doc = index["examples"][index["entries"]["tool.documentation"][0]]
    assert doc["origin"] == "declared" and doc["kind"] == "documentation"
    assert doc["verification"] == {"status": "source_checked"}
    query = index["examples"][index["entries"]["tool.query"][0]]
    assert query["run_command"] == "" and query["kind"] == "reference"
    assert query["verification"] == {"status": "unverified"}
    missing = index["examples"][index["entries"]["tool.broken"][0]]
    assert missing["verification"] == {"status": "unverified"}
    assert missing["issues"] == ["example_source_missing"]
    assert index["issues"] == [{"example_id": missing["id"], "error": "example_source_missing"}]


def test_bare_python_source_is_read_without_inventing_a_run_command(source):
    path = source[0]["nsgablack"] / "catalog/entries/toy.toml"
    with path.open("a", encoding="utf-8") as stream:
        stream.write('[[entry]]\nkey="tool.source"\nexample_entry="examples/project/workflow.py"\n')
    _, index = build(source)
    record = index["examples"][index["entries"]["tool.source"][0]]
    assert record["verification"]["status"] == "source_checked"
    assert record["run_command"] == "" and record["kind"] == "reference"
    assert record["snippets"][0]["path"].endswith("workflow.py")


def test_ml_declarations_use_canonical_cross_framework_keys(source):
    root = source[1].parent / "mlblack"
    (root / "catalog/entries").mkdir(parents=True)
    (root / "catalog/entries/codec.toml").write_text('[[entry]]\nkey="codec.linear"\n', encoding="utf-8")
    source[0]["mlblack"] = root
    _, index = build(source)
    assert index["entries"]["mlblack.codec.linear"] == []
    assert "codec.linear" not in index["entries"]


def test_explicit_public_catalog_snapshot_includes_dynamic_entries_without_importing(source):
    mlroot = source[1].parent / "mlblack"
    mlroot.mkdir()
    source[0]["mlblack"] = mlroot
    entries = [{"key": "mlblack.backend.cpu", "kind": "backend",
                "import_path": "module_that_must_not_be_imported:factory",
                "metadata": {"catalog_framework": "mlblack"}}]
    build_example_index(source[0], source[1], publication_digest=PUBLICATION, catalog_entries=entries)
    index = load_example_index(source[1])
    assert "mlblack.backend.cpu" in index["entries"]
    assert index["entries"]["mlblack.backend.cpu"] == []
    assert len(index["entries"]) == 5


def test_dynamic_entry_ownership_and_duplicate_snapshots_are_checked(source):
    entry = {"key": "dynamic.entry", "metadata": {"catalog_framework": "missing_root"}}
    with pytest.raises(ExampleValidationError, match="owner_invalid"):
        build_example_index(source[0], source[1], catalog_entries=[entry])
    entry["metadata"] = {}
    with pytest.raises(ExampleValidationError, match="key_invalid"):
        build_example_index(source[0], source[1], catalog_entries=[entry, entry])


def test_usage_audit_does_not_confuse_navigation_with_complete_recipe(source):
    from nsgablack.catalog.example_audit import audit_usage
    text = source[2].read_text(encoding="utf-8")
    source[2].write_text(text + 'steps=["调用实际装配函数"]\ndependencies=["公开Python示例"]\n', encoding="utf-8")
    _, index = build(source)
    entries = [{"key": key} for key in index["entries"]] + [{"key": "dynamic.missing"}]
    report = audit_usage(index, entries)
    by_key = {row["key"]: row for row in report["rows"]}
    assert by_key["adapter.toy"]["quality"] == "usage_recipe"
    assert by_key["tool.query"]["quality"] == "reference_only"
    assert by_key["dynamic.missing"]["quality"] == "absent_from_index"
    assert not report["complete_usage"]
    assert not any(row["execution_receipt"] for row in report["rows"])


def test_usage_audit_rejects_broken_python_documentation_even_if_source_exists(source):
    from nsgablack.catalog.example_audit import audit_usage
    guide = source[0]["nsgablack"] / "docs/guide.md"
    guide.write_text("```python\nbroken(\n```\n", encoding="utf-8")
    text = source[2].read_text(encoding="utf-8")
    text = text.replace('path="nsgablack/examples/project/workflow.py", symbol="assemble"',
                        'path="nsgablack/docs/guide.md"')
    source[2].write_text(text + 'steps=["构建组件"]\ndependencies=["Python"]\n', encoding="utf-8")
    _, index = build(source)
    row = audit_usage(index, [{"key": "adapter.toy"}])["rows"][0]
    assert row["quality"] == "reference_only"
    assert row["syntax_errors"][0]["reason"] == "python_syntax_invalid"


def test_exact_success_receipt_is_required_for_executed_label(source):
    _, index = build(source)
    receipt = write_receipt(source, index["examples"]["toy"])
    report, second = build(source, receipt)
    result = second["examples"]["toy"]["verification"]
    assert result["status"] == "executed" and result["exit_code"] == 0
    assert result["observed_outputs"][0].startswith("Case toy")
    assert report["verification"]["executed"] == 1
    # A separate, broad directory association cannot inherit focused proof.
    declared_id = second["entries"]["adapter.toy"][1]
    assert second["examples"][declared_id]["verification"]["status"] == "source_checked"


@pytest.mark.parametrize("changes", [
    {"source_digest": "c" * 64}, {"publication_digest": "c" * 64},
    {"command": "python other.py"}, {"exit_code": 1}, {"exit_code": False},
    {"executed_at": "2026-10-22T12:00:00"}, {"observed_outputs": []},
    {"output_sha256": "missing"}, {"status": "source_checked"},
])
def test_incomplete_stale_or_unsuccessful_receipts_do_not_claim_execution(source, changes):
    _, index = build(source)
    path = write_receipt(source, index["examples"]["toy"], **changes)
    _, rebuilt = build(source, path)
    assert rebuilt["examples"]["toy"]["verification"] == {"status": "source_checked"}


def test_project_configuration_change_invalidates_execution_proof(source):
    _, index = build(source)
    receipt = write_receipt(source, index["examples"]["toy"])
    config = source[0]["nsgablack"] / "examples/project/project_config.py"
    config.write_text('MODE = "second"\n', encoding="utf-8")
    _, changed = build(source, receipt)
    assert changed["examples"]["toy"]["source_digest"] != index["examples"]["toy"]["source_digest"]
    assert changed["examples"]["toy"]["verification"]["status"] == "source_checked"


@pytest.mark.parametrize("flag", ["--check", "--build-check", "--report-only=true"])
def test_check_only_command_cannot_be_execution_proof(source, flag):
    path = source[2]
    path.write_text(path.read_text(encoding="utf-8").replace('run_project.py"', f'run_project.py {flag}"'), encoding="utf-8")
    _, index = build(source)
    receipt = write_receipt(source, index["examples"]["toy"])
    _, rebuilt = build(source, receipt)
    assert rebuilt["examples"]["toy"]["verification"]["status"] == "source_checked"


@pytest.mark.parametrize("change", ["snippet", "digest", "membership", "issues", "receipt"])
def test_index_tampering_fails_validation(source, change):
    _, index = build(source)
    record = index["examples"]["toy"]
    if change == "snippet":
        record["snippets"][0]["text"] = "fabricated example"
    elif change == "digest":
        record["summary"] += "modified"
    elif change == "membership":
        index["entries"]["adapter.toy"] = []
    elif change == "issues":
        index["issues"][0]["error"] = "external text with private details"
    elif change == "receipt":
        record["verification"] = {"status": "executed"}
    with pytest.raises(ExampleValidationError):
        validate_example_index(index)


@pytest.mark.parametrize("relative", ["../outside.py", "private/secret.py", "tests/fixture.py", "db.toml", "/absolute.py"])
def test_focused_manifest_cannot_read_outside_public_source(source, relative):
    manifest = source[2]
    manifest.write_text(manifest.read_text(encoding="utf-8").replace("examples/project/workflow.py", relative), encoding="utf-8")
    with pytest.raises(ExampleValidationError):
        build(source)


def test_source_credentials_are_never_included(source):
    path = source[0]["nsgablack"] / "examples/project/workflow.py"
    path.write_text('TOKEN = "sk-' + "x" * 32 + '"\ndef assemble():\n    return 4\n', encoding="utf-8")
    with pytest.raises(ExampleValidationError, match="contains_credential"):
        build(source)


def test_loaded_index_is_detached_and_size_bounded(source, monkeypatch):
    _, index = build(source)
    detached = validate_example_index(index)
    detached["examples"]["toy"]["inputs"].append("changed")
    assert index["examples"]["toy"]["inputs"] == ["4个种子"]
    import nsgablack.catalog.examples as module
    monkeypatch.setattr(module, "MAX_INDEX_BYTES", 10)
    with pytest.raises(ExampleValidationError, match="oversized"):
        load_example_index(source[1])
