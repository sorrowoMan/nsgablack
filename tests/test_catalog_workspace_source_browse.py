"""Workspace source choices are cheap metadata; imports remain exact snapshots."""
from pathlib import Path
import json

import pytest

from nsgablack.catalog import lab_project_sources as source_module
from nsgablack.catalog.lab_project_sources import ProjectSourceError, ProjectSourceRegistry
from nsgablack.catalog.lab_workspace_store import WorkspaceError, WorkspaceStore


def project(root, name="planning", case="search"):
    path = root / name
    case_path = path / "cases" / case
    case_path.mkdir(parents=True)
    files = {"project_config.py": 'PROJECT_NAME = "生产计划"\nraise RuntimeError("must not execute")\n',
             "run_project.py": 'raise RuntimeError("must not execute")\n',
             "cases/__init__.py": "",
             f"cases/{case}/__init__.py": "",
             f"cases/{case}/build_solver.py": 'raise RuntimeError("must not execute")\n',
             f"cases/{case}/run_solver.py": 'raise RuntimeError("must not execute")\n',
             "README.md": "this body must not be searched by the chooser\n",
             "input.csv": "name,value\na,3\n"}
    for relative, text in files.items():
        (path / relative).write_text(text, encoding="utf-8")
    return path


def fail_read(*args, **kwargs):
    pytest.fail("Directory browsing read Project contents or built a snapshot")


def test_browse_reads_no_source_or_data_and_returns_no_revision(tmp_path, monkeypatch):
    path = project(tmp_path)
    registry = ProjectSourceRegistry({"mine": tmp_path})
    for name in ("snapshot_manifest", "describe_project", "_read", "_files", "search_projects"):
        monkeypatch.setattr(registry, name, fail_read)
    monkeypatch.setattr(Path, "read_text", fail_read)
    monkeypatch.setattr(Path, "read_bytes", fail_read)
    result = registry.browse_projects()
    assert result["scope"] == "directory_metadata_only"
    assert result["projects"] == [{"project_id": "mine:planning", "title": "planning",
        "relative_path": "planning", "case_ids": ["search"], "case_names": ["search"]}]
    serialized = json.dumps(result)
    assert str(path) not in serialized
    assert "revision" not in serialized and "source_digest" not in serialized
    assert "total_bytes" not in serialized


def test_workspace_chooser_uses_only_the_metadata_api(tmp_path, monkeypatch):
    project(tmp_path / "sources")
    registry = ProjectSourceRegistry({"mine": tmp_path / "sources"})
    store = WorkspaceStore(tmp_path / "workspaces", registry)
    for name in ("snapshot_manifest", "describe_project", "search_projects", "_read"):
        monkeypatch.setattr(registry, name, fail_read)
    rows = store.list_sources()
    assert rows[0]["project_id"] == "mine:planning"
    assert store.list_workspaces() == []


def test_browse_supports_a_root_that_is_itself_a_project(tmp_path):
    path = project(tmp_path)
    registry = ProjectSourceRegistry({"single": path})
    assert registry.browse_projects()["projects"][0] == {
        "project_id": "single:.", "title": "planning", "relative_path": ".",
        "case_ids": ["search"], "case_names": ["search"]}


def test_chooser_query_uses_only_handle_directory_and_standard_case_names(tmp_path):
    path = project(tmp_path, case="精修")
    # This Case is not an allowed identifier; a valid second Case is discoverable.
    case = path / "cases" / "refine"
    case.mkdir()
    for name in ("__init__.py", "build_solver.py", "run_solver.py"):
        (case / name).write_text("", encoding="utf-8")
    registry = ProjectSourceRegistry({"mine": tmp_path})
    assert registry.browse_projects("refine")["projects"][0]["case_names"] == ["refine"]
    assert registry.browse_projects("planning")["total"] == 1
    assert registry.browse_projects("must not be searched")["total"] == 0
    assert registry.browse_projects("生产计划")["total"] == 0


def test_nonstandard_hidden_and_sensitive_names_are_not_choices(tmp_path):
    visible = project(tmp_path)
    project(tmp_path, name=".hidden")
    project(tmp_path, name="credentials_project")
    project(tmp_path, name="outputs")
    for case_name in ("_helper", "password_cases", "invalid-case", "missing_entry"):
        case = visible / "cases" / case_name
        case.mkdir()
        for name in ("__init__.py", "build_solver.py", "run_solver.py"):
            if case_name != "missing_entry" or name != "run_solver.py":
                (case / name).write_text("", encoding="utf-8")
    broken = tmp_path / "broken"
    (broken / "cases").mkdir(parents=True)
    (broken / "project_config.py").write_text("", encoding="utf-8")
    rows = ProjectSourceRegistry({"mine": tmp_path}).browse_projects()["projects"]
    assert [row["project_id"] for row in rows] == ["mine:planning"]
    assert rows[0]["case_names"] == ["search"]


def test_metadata_results_are_sorted_bounded_and_detached(tmp_path):
    for name in ("zeta", "alpha", "beta"):
        project(tmp_path, name=name)
    registry = ProjectSourceRegistry({"mine": tmp_path})
    result = registry.browse_projects(limit=2)
    assert result["total"] == 3 and result["truncated"]
    assert [row["title"] for row in result["projects"]] == ["alpha", "beta"]
    result["projects"][0]["case_names"].clear()
    assert registry.browse_projects(limit=1)["projects"][0]["case_names"] == ["search"]


@pytest.mark.parametrize("kwargs", [{"query": None}, {"query": "x" * 301},
    {"limit": True}, {"limit": 0}, {"limit": 101}])
def test_invalid_browse_request_is_rejected(tmp_path, kwargs):
    registry = ProjectSourceRegistry({"mine": tmp_path})
    with pytest.raises(ProjectSourceError):
        registry.browse_projects(**kwargs)


def test_source_disappearance_during_browse_does_not_leak_or_replace_it(tmp_path, monkeypatch):
    project(tmp_path)
    registry = ProjectSourceRegistry({"mine": tmp_path})
    monkeypatch.setattr(registry, "resolve_project", lambda key: (_ for _ in ()).throw(
        ProjectSourceError("project_missing", "unavailable")))
    result = registry.browse_projects()
    assert result["projects"] == [] and result["unavailable_projects"] == 1


def test_linked_project_and_case_do_not_grant_access_to_outside_roots(tmp_path):
    trusted = tmp_path / "trusted"
    trusted.mkdir()
    path = project(trusted)
    outside = project(tmp_path / "elsewhere", name="outside")
    try:
        (trusted / "escaped").symlink_to(outside, target_is_directory=True)
        (path / "cases" / "escaped").symlink_to(outside / "cases" / "search", target_is_directory=True)
    except OSError:
        pytest.skip("This Windows session cannot create symlinks")
    result = ProjectSourceRegistry({"mine": trusted}).browse_projects()
    assert [row["project_id"] for row in result["projects"]] == ["mine:planning"]
    assert result["projects"][0]["case_names"] == ["search"]


def test_root_replaced_with_reparse_point_is_not_enumerated(tmp_path, monkeypatch):
    project(tmp_path / "trusted")
    root = tmp_path / "trusted"
    registry = ProjectSourceRegistry({"mine": root})
    linked = source_module._linked
    monkeypatch.setattr(source_module, "_linked", lambda path: path == root or linked(path))
    iterdir = Path.iterdir
    def guarded(path):
        if path == root:
            pytest.fail("A replaced trusted root was enumerated")
        return iterdir(path)
    monkeypatch.setattr(Path, "iterdir", guarded)
    assert registry.browse_projects()["projects"] == []


def test_create_after_browse_still_snapshots_latest_content_and_uses_formal_title(tmp_path):
    path = project(tmp_path / "sources")
    registry = ProjectSourceRegistry({"mine": tmp_path / "sources"})
    store = WorkspaceStore(tmp_path / "workspaces", registry)
    choice = store.list_sources()[0]
    (path / "input.csv").write_text("name,value\na,9\n", encoding="utf-8")
    workspace = store.create_workspace(choice["project_id"])
    revision = store.get_revision(workspace["workspace_id"])
    actual = registry.snapshot_manifest(choice["project_id"])
    assert workspace["title"] == "生产计划"
    assert workspace["source_revision"] == revision["source_digest"] == actual["source_digest"]
    assert revision["files"] == actual["files"]


def test_creation_still_rejects_changed_source_instead_of_trusting_a_choice(tmp_path, monkeypatch):
    path = project(tmp_path / "sources")
    registry = ProjectSourceRegistry({"mine": tmp_path / "sources"})
    store = WorkspaceStore(tmp_path / "workspaces", registry)
    choice = store.list_sources()[0]
    read = registry._read
    input_reads = 0
    def changed(project_id, relative, **kwargs):
        nonlocal input_reads
        data, metadata = read(project_id, relative, **kwargs)
        if relative == "input.csv":
            input_reads += 1
            if input_reads > 1:
                metadata = metadata | {"sha256": "0" * 64}
        return data, metadata
    monkeypatch.setattr(registry, "_read", changed)
    with pytest.raises(WorkspaceError, match="changed"):
        store.create_workspace(choice["project_id"])
    assert store.list_workspaces() == []


def test_evidence_search_retains_its_original_snapshot_contract(tmp_path):
    project(tmp_path)
    registry = ProjectSourceRegistry({"mine": tmp_path})
    row = registry.search_projects("planning")["projects"][0]
    assert row["title"] == "生产计划"
    assert row["revision"] == row["source_digest"]
    assert len(row["source_digest"]) == 64
