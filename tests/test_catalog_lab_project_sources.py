"""Projects are read as bounded evidence without imports or host-path access."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from nsgablack.catalog import lab_project_sources as sources


def make_project(root: Path, name="planning"):
    project = root / name
    case = project / "cases" / "main"
    case.mkdir(parents=True)
    (project / "project_config.py").write_text(
        'PROJECT_NAME = "生产计划"\nraise RuntimeError("must never execute")\n', encoding="utf-8")
    (project / "run_project.py").write_text('raise RuntimeError("must never execute")\n', encoding="utf-8")
    (project / "README.md").write_text("共享物料的生产排程 planning example", encoding="utf-8")
    (project / "cases" / "__init__.py").write_text("", encoding="utf-8")
    for filename in ("__init__.py", "build_solver.py", "run_solver.py"):
        (case / filename).write_text('raise RuntimeError("must never execute")\n', encoding="utf-8")
    (case / ".case").write_text('{"kind":"solver"}', encoding="utf-8")
    return project, case


@pytest.fixture
def project(tmp_path):
    path, case = make_project(tmp_path)
    return sources.ProjectSourceRegistry({"test": tmp_path}), path, case


def write_workbook(path: Path, *, malicious_xml=False):
    namespace = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    with ZipFile(path, "w") as archive:
        archive.writestr("xl/workbook.xml", f'<workbook {namespace} '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="生产计划" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels", '<Relationships '
            'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="worksheet" Target="worksheets/sheet1.xml"/>'
            '</Relationships>')
        archive.writestr("xl/sharedStrings.xml", f'<sst {namespace}><si><t>day</t></si>'
                        '<si><t>机种0</t></si></sst>')
        xml = f'<worksheet {namespace}><dimension ref="A1:B3"/><sheetData>' \
              '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>' \
              '<row r="2"><c r="A2"><v>0</v></c><c r="B2"><v>100</v></c></row>' \
              '<row r="3"><c r="A3"><v>1</v></c><c r="B3"><f>50+50</f><v>100</v></c></row>' \
              '</sheetData></worksheet>'
        if malicious_xml:
            xml = '<!DOCTYPE worksheet [<!ENTITY bad "payload">]>' + xml
        archive.writestr("xl/worksheets/sheet1.xml", xml)


def test_discovery_and_reads_do_not_execute_project_code(project):
    registry, path, case = project
    result = registry.search_projects("排程")
    assert result["total"] == 1
    record = result["projects"][0]
    assert record["project_id"] == "test:planning"
    assert record["title"] == "生产计划" and record["case_ids"] == ["main"]
    assert str(path) not in json.dumps(result, ensure_ascii=False)
    assert registry.resolve_project(record["project_id"]) == path
    assert registry.resolve_case(record["project_id"], "main") == case
    source = registry.read_project_source(record["project_id"], "project_config.py", max_lines=1)
    assert source["excerpt"] == 'PROJECT_NAME = "生产计划"'
    assert source["start_line"] == source["end_line"] == 1
    assert source["truncated"]
    assert source["source"]["sha256"] == hashlib.sha256((path / "project_config.py").read_bytes()).hexdigest()


def test_manifest_is_relocatable_and_changes_with_actual_source(tmp_path):
    first, _ = make_project(tmp_path / "first")
    second, _ = make_project(tmp_path / "second")
    one = sources.ProjectSourceRegistry({"root": first.parent})
    two = sources.ProjectSourceRegistry({"root": second.parent})
    before = one.snapshot_manifest("root:planning")
    assert before == two.snapshot_manifest("root:planning")
    assert "cases/main/.case" in {row["path"] for row in before["files"]}
    (first / "README.md").write_text("updated", encoding="utf-8")
    assert one.snapshot_manifest("root:planning")["revision"] != before["revision"]


def test_logs_hidden_files_and_credential_sources_are_not_in_manifest(project):
    registry, path, _ = project
    for name in ("runs", ".blackbase", "__pycache__", "exports", "outputs"):
        directory = path / name
        directory.mkdir()
        (directory / "log.json").write_text('{"private":"history"}', encoding="utf-8")
    (path / "credentials.json").write_text('{"api_key":"never-expose"}', encoding="utf-8")
    (path / "innocent.py").write_text('API_KEY = "never-expose"', encoding="utf-8")
    files = registry.snapshot_manifest("test:planning")["files"]
    assert not any(row["path"].startswith(("runs/", ".blackbase/", "exports/", "outputs/")) for row in files)
    assert not {"credentials.json", "innocent.py"} & {row["path"] for row in files}
    with pytest.raises(sources.ProjectSourceError, match="Credential-shaped"):
        registry.read_project_source("test:planning", "innocent.py")


@pytest.mark.parametrize("path", [
    "../outside.py", "/etc/passwd", "C:/private/key.pem", "cases\\main\\build_solver.py",
    "README.md:stream", ".git/config", "runs/output.json", "credentials.json", "key.pem", "x.pkl",
])
def test_model_paths_cannot_expand_the_selected_root(project, path):
    registry, _, _ = project
    with pytest.raises(sources.ProjectSourceError):
        registry.read_project_source("test:planning", path)


def test_project_and_case_identifiers_are_server_handles(project):
    registry, _, _ = project
    for identifier in ("../planning", "C:/planning", "test:missing", "test:planning/", "test:planning/.", None):
        with pytest.raises(sources.ProjectSourceError):
            registry.resolve_project(identifier)
    for case in ("../main", "main/../main", "missing", None):
        with pytest.raises(sources.ProjectSourceError):
            registry.resolve_case("test:planning", case)


def test_symlinks_do_not_grant_file_or_project_access(project, tmp_path):
    registry, path, _ = project
    outside = tmp_path / "outside.py"
    outside.write_text("secret payload", encoding="utf-8")
    try:
        (path / "linked.py").symlink_to(outside)
    except OSError:
        pytest.skip("This Windows session cannot create symlinks")
    with pytest.raises(sources.ProjectSourceError):
        registry.read_project_source("test:planning", "linked.py")
    assert "linked.py" not in {row["path"] for row in registry.snapshot_manifest("test:planning")["files"]}


def test_windows_reparse_attribute_is_refused_without_path_is_junction(project, monkeypatch):
    registry, path, _ = project
    original = Path.lstat

    class ReparseStat:
        st_file_attributes = 0x400

    def substituted(candidate):
        return ReparseStat() if candidate == path / "README.md" else original(candidate)

    monkeypatch.setattr(Path, "lstat", substituted)
    with pytest.raises(sources.ProjectSourceError, match="Linked"):
        registry.read_project_source("test:planning", "README.md")


def test_missing_or_changed_data_changes_revision_without_claiming_it_exists(project):
    registry, _, case = project
    before = registry.snapshot_manifest("test:planning")
    name = "cases/main/input.csv"
    assert name not in {row["path"] for row in before["files"]}
    with pytest.raises(sources.ProjectSourceError):
        registry.inspect_project_data("test:planning", name)
    (case / "input.csv").write_text("id,value\n1,100\n", encoding="utf-8")
    present = registry.snapshot_manifest("test:planning")
    assert present["revision"] != before["revision"]
    first_sha = registry.inspect_project_data("test:planning", name)["source"]["sha256"]
    (case / "input.csv").write_text("id,value\n1,200\n", encoding="utf-8")
    changed = registry.snapshot_manifest("test:planning")
    assert changed["revision"] != present["revision"]
    assert registry.inspect_project_data("test:planning", name)["source"]["sha256"] != first_sha
    (case / "input.csv").unlink()
    assert registry.snapshot_manifest("test:planning")["revision"] == before["revision"]


def test_file_listing_pages_are_complete_and_bound_to_one_revision(project):
    registry, _, case = project
    for number in range(180):
        (case / f"operation_{number:03d}.py").write_text(f"VALUE = {number}\n", encoding="utf-8")
    seen, offset, revision = [], 0, None
    while True:
        page = registry.list_project_files("test:planning", limit=60, offset=offset)
        assert page["offset"] == offset and len(page["files"]) <= 60
        assert revision is None or revision == page["revision"]
        revision = page["revision"]
        seen.extend(row["path"] for row in page["files"])
        if page["next_offset"] is None:
            assert page["truncated"] is False
            break
        assert page["truncated"]
        offset = page["next_offset"]
    assert len(seen) == page["total"] == len(set(seen))
    assert seen == [row["path"] for row in registry.snapshot_manifest("test:planning")["files"]]
    with pytest.raises(sources.ProjectSourceError):
        registry.list_project_files("test:planning", offset=-1)
    with pytest.raises(sources.ProjectSourceError):
        registry.list_project_files("test:planning", limit=201)


def test_csv_inspection_preserves_header_semantics_and_encoding(project):
    registry, _, case = project
    data = "机种编号,物料编号,第0日\n0,135,1000\n1,135,2000\n".encode("gb18030")
    (case / "mapping.csv").write_bytes(data)
    result = registry.inspect_project_data("test:planning", "cases/main/mapping.csv", max_rows=1)
    assert result["encoding"] == "gb18030"
    assert result["columns"] == ["机种编号", "物料编号", "第0日"]
    assert result["data_row_count"] == 2 and result["column_count"] == 3
    assert result["sample_rows"] == [["0", "135", "1000"]]
    assert result["inspection_only"] and result["executed"] is False
    assert result["source"]["sha256"] == hashlib.sha256(data).hexdigest()


def test_xlsx_inspection_reads_cached_values_without_evaluating_formulas(project):
    registry, _, case = project
    write_workbook(case / "plan.xlsx")
    result = registry.inspect_project_data("test:planning", "cases/main/plan.xlsx", max_rows=1)
    sheet = result["sheets"][0]
    assert result["sheet_count"] == 1 and sheet["name"] == "生产计划"
    assert sheet["columns"] == ["day", "机种0"]
    assert sheet["row_count"] == 3 and sheet["data_row_count"] == 2 and sheet["column_count"] == 2
    assert sheet["sample_rows"] == [[0, 100]]
    assert sheet["formulas_present"] and sheet["formula_values"] == "cached_only"
    with pytest.raises(sources.ProjectSourceError, match="does not exist"):
        registry.inspect_project_data("test:planning", "cases/main/plan.xlsx", sheet_name="missing")


def test_workbook_entities_and_zip_expansion_are_refused(project, monkeypatch):
    registry, _, case = project
    write_workbook(case / "bad.xlsx", malicious_xml=True)
    with pytest.raises(sources.ProjectSourceError, match="entity"):
        registry.inspect_project_data("test:planning", "cases/main/bad.xlsx")
    write_workbook(case / "valid.xlsx")
    monkeypatch.setattr(sources, "MAX_ZIP_XML_BYTES", 10)
    with pytest.raises(sources.ProjectSourceError, match="budget"):
        registry.inspect_project_data("test:planning", "cases/main/valid.xlsx")


def test_credentials_in_csv_columns_and_json_are_refused(project):
    registry, _, case = project
    (case / "data.csv").write_text("username,password\nuser,never-expose\n", encoding="utf-8")
    (case / "data.json").write_text('{"nested":{"api_key":"never-expose"}}', encoding="utf-8")
    for name in ("data.csv", "data.json"):
        with pytest.raises(sources.ProjectSourceError):
            registry.inspect_project_data("test:planning", f"cases/main/{name}")


def test_exact_credential_tokens_are_not_confused_with_candidate_identity(project):
    registry, _, case = project
    (case / "binding.py").write_text('token = "never-expose"', encoding="utf-8")
    (case / "candidate.py").write_text('candidate_token = "semantic-example"', encoding="utf-8")
    with pytest.raises(sources.ProjectSourceError):
        registry.read_project_source("test:planning", "cases/main/binding.py")
    assert "candidate_token" in registry.read_project_source("test:planning", "cases/main/candidate.py")["excerpt"]


def test_read_and_project_budgets_are_checked(project, monkeypatch):
    registry, path, _ = project
    with pytest.raises(sources.ProjectSourceError):
        registry.read_project_source("test:planning", "README.md", start_line=0)
    with pytest.raises(sources.ProjectSourceError):
        registry.read_project_source("test:planning", "README.md", max_lines=201)
    with pytest.raises(sources.ProjectSourceError):
        registry.inspect_project_data("test:planning", "README.md", max_rows=21)
    (path / "wide.py").write_text("x" * 30, encoding="utf-8")
    monkeypatch.setattr(sources, "MAX_EXCERPT_CHARS", 10)
    with pytest.raises(sources.ProjectSourceError, match="excerpt budget"):
        registry.read_project_source("test:planning", "wide.py")
    monkeypatch.setattr(sources, "MAX_PROJECT_BYTES", 10)
    with pytest.raises(sources.ProjectSourceError, match="snapshot budget"):
        registry.snapshot_manifest("test:planning")


def test_data_preview_output_is_bounded_without_changing_measured_shape(project):
    registry, _, case = project
    (case / "large.csv").write_text(
        ",".join(f"column{i}" for i in range(100)) + "\n" +
        (",".join("text" * 200 for _ in range(100)) + "\n") * 20, encoding="utf-8")
    result = registry.inspect_project_data("test:planning", "cases/main/large.csv", max_rows=20)
    assert result["data_row_count"] == 20 and result["column_count"] == 100
    assert result["sample_rows_truncated"]
    assert len(json.dumps(result, ensure_ascii=False).encode()) <= sources.MAX_INSPECTION_BYTES


def test_json_structure_has_a_shared_node_budget(project):
    registry, _, case = project
    value = {str(i): {str(j): {str(k): k for k in range(60)} for j in range(60)} for i in range(60)}
    (case / "nested.json").write_text(json.dumps(value), encoding="utf-8")
    result = registry.inspect_project_data("test:planning", "cases/main/nested.json")
    assert result["structure"]["property_count"] == 60
    assert result["structure"]["properties_truncated"]
    assert len(json.dumps(result, ensure_ascii=False).encode()) <= sources.MAX_INSPECTION_BYTES


def test_real_production_case_is_discovered_and_data_is_read_without_building():
    registry = sources.ProjectSourceRegistry()
    result = registry.search_projects("production_scheduling", limit=10)
    record = next(row for row in result["projects"] if row["project_id"] == "examples:production_scheduling")
    assert record["case_ids"] == ["production_scheduling"]
    listed = registry.list_project_files(record["project_id"], limit=200)
    assert "project_config.py" in {row["path"] for row in listed["files"]}
    assert not any("/runs/" in row["path"] for row in listed["files"])
    prefix = "cases/production_scheduling/"
    csv_data = registry.inspect_project_data(record["project_id"], prefix + "machine_material_mapping.csv")
    assert csv_data["columns"][:2] == ["机种编号", "物料编号"]
    assert csv_data["data_row_count"] == 225
    workbook = registry.inspect_project_data(record["project_id"], prefix + "SUPPLY.xlsx", max_rows=2)
    assert workbook["sheet_count"] >= 1 and workbook["sheets"][0]["column_count"] >= 32


def test_literal_source_find_preserves_identity_and_context_lines(project):
    registry, path, _ = project
    content = "first\ndef repair(x):\n    return x\n# REPAIR is literal\nlast\n"
    (path / "operations.py").write_text(content, encoding="utf-8")
    found = registry.find_project_source("test:planning", "operations.py", "repair", context_lines=1)
    assert found["source"]["sha256"] == hashlib.sha256((path / "operations.py").read_bytes()).hexdigest()
    assert found["total_matches"] == 2 and not found["truncated"]
    assert found["match_unit"] == "line" and found["case_sensitive"] is False
    assert [row["line"] for row in found["matches"]] == [2, 4]
    assert found["matches"][0] == {"line": 2, "start_line": 1, "end_line": 3,
                                     "excerpt": "first\ndef repair(x):\n    return x", "excerpt_truncated": False}
    assert registry.find_project_source("test:planning", "operations.py", "missing")["matches"] == []


def test_source_find_uses_literal_unicode_casefold_not_regex(project):
    registry, path, _ = project
    (path / "operations.py").write_text("# Straße\n# a.*b\n# aZZb\n# repair repair repair\n", encoding="utf-8")
    assert registry.find_project_source("test:planning", "operations.py", "STRASSE")["matches"][0]["line"] == 1
    assert [row["line"] for row in registry.find_project_source(
        "test:planning", "operations.py", "a.*b")["matches"]] == [2]
    assert registry.find_project_source("test:planning", "operations.py", "repair")["total_matches"] == 1


@pytest.mark.parametrize("options", [
    {"query": ""}, {"query": "  \n"}, {"query": "a" * 201}, {"query": None},
    {"max_matches": 0}, {"max_matches": 21}, {"max_matches": True},
    {"context_lines": -1}, {"context_lines": 6}, {"context_lines": True},
])
def test_source_find_rejects_invalid_query_and_limits(project, options):
    registry, _, _ = project
    arguments = {"query": "PROJECT_NAME", **options}
    with pytest.raises(sources.ProjectSourceError):
        registry.find_project_source("test:planning", "project_config.py", **arguments)


def test_source_find_obeys_same_path_sensitive_content_and_link_guards(project, monkeypatch):
    registry, path, _ = project
    (path / "private.py").write_text('api_key="synthetic-private"', encoding="utf-8")
    for name in ("private.py", "../outside.py", "runs/old.py", "key.pem"):
        with pytest.raises(sources.ProjectSourceError):
            registry.find_project_source("test:planning", name, "private")
    original = sources._linked
    monkeypatch.setattr(sources, "_linked", lambda candidate: candidate == path / "README.md" or original(candidate))
    with pytest.raises(sources.ProjectSourceError, match="Linked"):
        registry.find_project_source("test:planning", "README.md", "planning")


def test_source_find_bounds_many_large_matches_and_preserves_total(project):
    registry, path, _ = project
    content = ("# target " + "x" * 2900 + "\n") * 100
    (path / "large.py").write_text(content, encoding="utf-8")
    found = registry.find_project_source("test:planning", "large.py", "target", max_matches=20, context_lines=5)
    assert found["total_matches"] == 100 and found["truncated"]
    assert 0 < len(found["matches"]) < 20
    assert all("target" in row["excerpt"] for row in found["matches"])
    assert len(json.dumps(found, ensure_ascii=False, allow_nan=False).encode()) <= sources.MAX_INSPECTION_BYTES


def test_source_find_long_matching_line_keeps_the_actual_literal_in_preview(project):
    registry, path, _ = project
    (path / "long.py").write_text("x" * 30000 + "# STRASSE target\n", encoding="utf-8")
    found = registry.find_project_source("test:planning", "long.py", "strasse target")
    match = found["matches"][0]
    assert match["line"] == match["start_line"] == match["end_line"] == 1
    assert match["excerpt_truncated"] and "STRASSE target" in match["excerpt"]
    assert match["excerpt_start_column"] > 1
    assert len(json.dumps(found, ensure_ascii=False).encode()) <= sources.MAX_INSPECTION_BYTES


def test_source_find_rejects_oversized_input_even_for_short_query(project, monkeypatch):
    registry, path, _ = project
    (path / "long.py").write_text("target" * 20, encoding="utf-8")
    monkeypatch.setattr(sources, "MAX_TEXT_BYTES", 50)
    with pytest.raises(sources.ProjectSourceError, match="read budget"):
        registry.find_project_source("test:planning", "long.py", "target")
