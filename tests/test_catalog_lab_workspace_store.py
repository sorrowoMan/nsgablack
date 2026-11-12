"""Project revisions remain detached, immutable and scoped under concurrent edits."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import sqlite3
import threading

import pytest

from nsgablack.catalog.lab_project_sources import ProjectSourceRegistry
from nsgablack.catalog.lab_workspace_store import WorkspaceError, WorkspaceStore
from nsgablack.catalog import lab_workspace_store as workspace_module


@pytest.fixture
def source(tmp_path):
    project = tmp_path / "sources" / "small"
    files = {
        "project_config.py": "PROJECT_NAME = '可编辑实验'\n",
        "run_project.py": "raise RuntimeError('source browsing must not execute')\n",
        "cases/__init__.py": "",
        "cases/search/__init__.py": "",
        "cases/search/build_solver.py": "def build_solver():\n    return None\n",
        "cases/search/run_solver.py": "def main():\n    return 0\n",
        "cases/search/.case": '{"kind":"solver"}\n',
        "cases/search/problem/problem.py": "scale = 1.0\n",
        "cases/search/adapter/operators.py": "def change(x):\n    return x + 1\n",
        "README.md": "# 示例工程\n",
        "results/old.json": '{"old":true}',
        ".hidden/note.md": "hidden note",
        "credentials.py": "password = 'private-marker'\n",
        "normal.py": "token = 'also-private-marker'\n",
    }
    for name, text in files.items():
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
    (project / "input.csv").write_bytes(b"name,value\na,3\n")
    (project / "supply.xlsx").write_bytes(b"binary-workbook-fixture")
    registry = ProjectSourceRegistry({"examples": project.parent})
    return project, registry


@pytest.fixture
def imported(tmp_path, source):
    project, registry = source
    store = WorkspaceStore(tmp_path / "workspace", registry)
    workspace = store.create_workspace("examples:small")
    return store, workspace, project


def _changed(store, workspace, text="scale = 2.0\n"):
    return store.save_files(workspace["workspace_id"], {"cases/search/problem/problem.py": text},
                            expected_revision=workspace["head_revision"], message="Adjust scale")


def test_import_uses_exact_safe_source_closure_without_execution(imported, source):
    store, workspace, project = imported
    _, registry = source
    revision = store.get_revision(workspace["workspace_id"])
    original = registry.snapshot_manifest("examples:small")
    assert revision["source_digest"] == original["source_digest"]
    assert revision["files"] == original["files"]
    assert workspace["title"] == "可编辑实验"
    assert {r["path"] for r in revision["files"]}.isdisjoint(
        {"results/old.json", ".hidden/note.md", "credentials.py", "normal.py"})
    assert not (project / ".blackbase").exists()
    assert store.list_sources()[0]["project_id"] == "examples:small"


def test_edit_preserves_old_revision_source_and_survives_restart(imported, source):
    store, workspace, project = imported
    identity, old_id = workspace["workspace_id"], workspace["head_revision"]
    new = _changed(store, workspace)
    restored = WorkspaceStore(store.root, source[1])
    assert restored.get_workspace(identity)["head_revision"] == new["revision_id"]
    assert new["parent_revision"] == old_id
    assert restored.read_file(identity, old_id, "cases/search/problem/problem.py")["content"] == "scale = 1.0\n"
    assert restored.read_file(identity, new["revision_id"], "cases/search/problem/problem.py")["content"] == "scale = 2.0\n"
    assert (project / "cases/search/problem/problem.py").read_text() == "scale = 1.0\n"
    assert [r["revision_id"] for r in restored.list_revisions(identity)] == [new["revision_id"], old_id]
    assert restored.list_workspaces()[0]["workspace_id"] == identity


def test_two_store_instances_reject_stale_revision(imported, source):
    store, workspace, _ = imported
    other = WorkspaceStore(store.root, source[1])
    new = _changed(store, workspace)
    with pytest.raises(WorkspaceError, match="changed") as error:
        _changed(other, workspace, "scale = 3.0\n")
    assert error.value.code == "workspace_revision_conflict"
    assert store.get_workspace(workspace["workspace_id"])["head_revision"] == new["revision_id"]
    assert len(other.list_revisions(workspace["workspace_id"])) == 2


def test_simultaneous_writers_have_exactly_one_cas_winner(imported, source):
    store, workspace, _ = imported
    other = WorkspaceStore(store.root, source[1])
    barrier = threading.Barrier(2)
    def save(selected, value):
        barrier.wait()
        try:
            return _changed(selected, workspace, f"scale = {value}\n")["revision_id"]
        except WorkspaceError as exc:
            return exc.code
    with ThreadPoolExecutor(max_workers=2) as workers:
        outcomes = list(workers.map(lambda row: save(*row), [(store, 2), (other, 3)]))
    assert outcomes.count("workspace_revision_conflict") == 1
    assert len(store.list_revisions(workspace["workspace_id"])) == 2


def test_noop_and_content_revert_preserve_history(imported):
    store, workspace, _ = imported
    original = store.get_revision(workspace["workspace_id"])
    same = _changed(store, workspace, "scale = 1.0\n")
    assert same == original
    changed = _changed(store, workspace)
    reverted = store.save_files(workspace["workspace_id"], {"cases/search/problem/problem.py": "scale = 1.0\n"},
                               expected_revision=changed["revision_id"])
    assert reverted["source_digest"] == original["source_digest"]
    assert reverted["revision_id"] != original["revision_id"]
    assert reverted["parent_revision"] == changed["revision_id"]


def test_shared_inputs_are_single_blobs_and_materializations_are_copies(imported, tmp_path, source):
    store, workspace, project = imported
    new = _changed(store, workspace)
    inputs = [row for row in new["files"] if row["path"] == "supply.xlsx"]
    assert len(inputs) == 1
    digest = inputs[0]["sha256"]
    assert len(list((store.root / "blobs").rglob(digest))) == 1
    first = store.materialize(workspace["workspace_id"], workspace["head_revision"], tmp_path / "first")
    second = store.materialize(workspace["workspace_id"], new["revision_id"], tmp_path / "second")
    second_registry = ProjectSourceRegistry({"copy": second})
    assert second_registry.snapshot_manifest("copy:.")["source_digest"] == new["source_digest"]
    (second / "supply.xlsx").write_bytes(b"changed output")
    assert (first / "supply.xlsx").read_bytes() == b"binary-workbook-fixture"
    assert (project / "supply.xlsx").read_bytes() == b"binary-workbook-fixture"
    assert (store.root / "blobs" / digest[:2] / digest).read_bytes() == b"binary-workbook-fixture"
    with pytest.raises(WorkspaceError) as error:
        store.materialize(workspace["workspace_id"], new["revision_id"], second)
    assert error.value.code == "workspace_target_exists"


def test_source_deletion_does_not_remove_saved_project(imported, tmp_path):
    store, workspace, project = imported
    shutil.rmtree(project)
    restored = store.materialize(workspace["workspace_id"], workspace["head_revision"], tmp_path / "recovered")
    assert (restored / "cases/search/problem/problem.py").read_text() == "scale = 1.0\n"
    assert store.read_file(workspace["workspace_id"], workspace["head_revision"], "README.md")["content"] == "# 示例工程\n"


def test_binary_data_is_readonly(imported):
    store, workspace, _ = imported
    result = store.read_file(workspace["workspace_id"], workspace["head_revision"], "supply.xlsx")
    assert not result["editable"] and result["encoding"] is None and result["content"] == ""
    with pytest.raises(WorkspaceError) as error:
        store.save_files(workspace["workspace_id"], {"supply.xlsx": "x"}, expected_revision=workspace["head_revision"])
    assert error.value.code == "workspace_file_readonly"


def test_gb18030_import_can_be_edited_and_normalized_to_utf8(imported):
    store, workspace, project = imported
    path = project / "README.md"
    path.write_bytes("# 中文旧文件\n".encode("gb18030"))
    again = store.create_workspace("examples:small")
    read = store.read_file(again["workspace_id"], again["head_revision"], "README.md")
    assert read["encoding"] == "gb18030"
    new = store.save_files(again["workspace_id"], {"README.md": read["content"] + "新增\n"}, expected_revision=again["head_revision"])
    updated = store.read_file(again["workspace_id"], new["revision_id"], "README.md")
    assert updated["encoding"] == "utf-8-sig" and updated["content"].endswith("新增\n")


@pytest.mark.parametrize("prefix", ["# coding: gb18030\n", "#!/usr/bin/env python\n# -*- coding: gbk -*-\n"])
def test_python_encoding_cookie_matches_saved_utf8_bytes(imported, prefix, tmp_path):
    store, workspace, project = imported
    relative = "cases/search/problem/problem.py"
    text = prefix + "label = '中文文本'\n"
    (project / relative).write_bytes(text.encode("gb18030"))
    workspace = store.create_workspace("examples:small")
    observed = store.read_file(workspace["workspace_id"], workspace["head_revision"], relative)
    assert observed["encoding"] == "gb18030"
    revision = store.save_files(workspace["workspace_id"], {relative: observed["content"] + "scale = 3\n"},
                                expected_revision=workspace["head_revision"])
    saved = store.read_file(workspace["workspace_id"], revision["revision_id"], relative)
    assert "coding: utf-8" in saved["content"]
    restored = store.materialize(workspace["workspace_id"], revision["revision_id"], tmp_path / "utf8-project")
    namespace = {}
    exec(compile((restored / relative).read_bytes(), relative, "exec"), namespace)
    assert namespace["label"] == "中文文本" and namespace["scale"] == 3


def test_read_and_noop_save_preserve_original_crlf_bytes(imported):
    store, _, project = imported
    relative = "cases/search/problem/problem.py"
    (project / relative).write_bytes(b"scale = 1.0\r\n")
    workspace = store.create_workspace("examples:small")
    original = store.get_revision(workspace["workspace_id"])
    read = store.read_file(workspace["workspace_id"], workspace["head_revision"], relative)
    assert read["content"] == "scale = 1.0\r\n"
    assert store.save_files(workspace["workspace_id"], {relative: read["content"]},
                            expected_revision=workspace["head_revision"]) == original


@pytest.mark.parametrize("path", ["../outside.py", "/root.py", "a/../README.md", "a\\b.py", "C:/host.py", "README.md\x00", ".hidden/a.py", "secrets.py", "README.md/", "a//b.py"])
def test_path_escape_and_noncanonical_paths_rejected(imported, path):
    store, workspace, _ = imported
    with pytest.raises(WorkspaceError) as error:
        store.save_files(workspace["workspace_id"], {path: "x"}, expected_revision=workspace["head_revision"])
    assert error.value.code == "workspace_path_refused"


@pytest.mark.parametrize("identity", ["..", "/etc/passwd", "A" * 32, "a" * 31, "a" * 33, None, 1])
def test_invalid_ids_are_not_filesystem_paths(imported, identity):
    store, _, _ = imported
    with pytest.raises(WorkspaceError) as error:
        store.get_workspace(identity)
    assert error.value.code == "workspace_identity_invalid"


def test_revision_from_another_workspace_is_not_accessible(imported):
    store, workspace, _ = imported
    other = store.create_workspace("examples:small")
    with pytest.raises(WorkspaceError) as error:
        store.get_revision(workspace["workspace_id"], other["head_revision"])
    assert error.value.code == "workspace_revision_missing"


def test_explicit_empty_revision_does_not_silently_select_head(imported):
    store, workspace, _ = imported
    with pytest.raises(WorkspaceError) as error:
        store.get_revision(workspace["workspace_id"], "")
    assert error.value.code == "workspace_identity_invalid"


def test_new_files_and_secrets_are_rejected_atomically_but_syntax_drafts_can_save(imported):
    store, workspace, _ = imported
    for changes, code in [({"new.py": "x"}, "workspace_file_missing"),
                          ({"README.md": "token = 'secret-marker'"}, "workspace_sensitive"),
                          ({"README.md": "x\x00y"}, "workspace_file_readonly"),
                          ({"README.md": "x" * (512 * 1024 + 1)}, "workspace_file_too_large")]:
        with pytest.raises(WorkspaceError) as error:
            store.save_files(workspace["workspace_id"], changes, expected_revision=workspace["head_revision"])
        assert error.value.code == code
        assert len(store.list_revisions(workspace["workspace_id"])) == 1
    saved = _changed(store, workspace, "def broken(:\n")
    assert store.read_file(workspace["workspace_id"], saved["revision_id"], "cases/search/problem/problem.py")["content"] == "def broken(:\n"


def test_tampered_blob_fails_before_materialization_or_text_read(imported, tmp_path):
    store, workspace, _ = imported
    revision = store.get_revision(workspace["workspace_id"])
    row = next(r for r in revision["files"] if r["path"] == "README.md")
    blob = store.root / "blobs" / row["sha256"][:2] / row["sha256"]
    blob.write_bytes(b"tampered")
    with pytest.raises(WorkspaceError) as error:
        store.materialize(workspace["workspace_id"], revision["revision_id"], tmp_path / "copy")
    assert error.value.code == "workspace_blob_invalid" and not (tmp_path / "copy").exists()
    with pytest.raises(WorkspaceError) as error:
        store.read_file(workspace["workspace_id"], revision["revision_id"], "README.md")
    assert error.value.code == "workspace_blob_invalid"


def test_failed_materialization_cleans_only_its_unpublished_staging(imported, tmp_path, monkeypatch):
    store, workspace, _ = imported
    outside = tmp_path / "keep.txt"
    outside.write_bytes(b"keep")
    original = Path.write_bytes
    def fail_one(path, data):
        if path.name == "project_config.py" and any(".incoming-" in part for part in path.parts):
            raise OSError("simulated write failure")
        return original(path, data)
    monkeypatch.setattr(Path, "write_bytes", fail_one)
    with pytest.raises(OSError, match="simulated"):
        store.materialize(workspace["workspace_id"], workspace["head_revision"], tmp_path / "copy")
    assert not (tmp_path / "copy").exists()
    assert not list(tmp_path.glob("copy.incoming-*"))
    assert outside.read_bytes() == b"keep"


def test_tampered_manifest_cannot_introduce_an_escaped_file(imported, tmp_path):
    store, workspace, _ = imported
    revision = store.get_revision(workspace["workspace_id"])
    revision["files"][0]["path"] = "../escaped.py"
    with sqlite3.connect(store.root / "workspace.sqlite3") as connection:
        connection.execute("UPDATE revisions SET data=? WHERE revision_id=?", (json.dumps(revision), revision["revision_id"]))
    with pytest.raises(WorkspaceError) as error:
        store.materialize(workspace["workspace_id"], revision["revision_id"], tmp_path / "copy")
    assert error.value.code == "workspace_path_refused"
    assert not (tmp_path / "escaped.py").exists()


def test_revision_metadata_cannot_claim_another_identity(imported):
    store, workspace, _ = imported
    revision = store.get_revision(workspace["workspace_id"])
    revision["workspace_id"] = "a" * 32
    with sqlite3.connect(store.root / "workspace.sqlite3") as connection:
        connection.execute("UPDATE revisions SET data=? WHERE revision_id=?", (json.dumps(revision), revision["revision_id"]))
    with pytest.raises(WorkspaceError) as error:
        store.get_revision(workspace["workspace_id"], revision["revision_id"])
    assert error.value.code == "workspace_manifest_invalid"


@pytest.mark.parametrize("linked_part", ["root", "database", "blob"])
def test_reparse_detection_is_enforced_without_os_link_creation(imported, monkeypatch, linked_part):
    store, workspace, _ = imported
    revision = store.get_revision(workspace["workspace_id"])
    row = next(r for r in revision["files"] if r["path"] == "README.md")
    selected = {"root": store.root, "database": store.root / "workspace.sqlite3",
                "blob": store.root / "blobs" / row["sha256"][:2] / row["sha256"]}[linked_part]
    original = workspace_module._linked
    monkeypatch.setattr(workspace_module, "_linked", lambda path: path == selected or original(path))
    with pytest.raises(WorkspaceError) as error:
        store.read_file(workspace["workspace_id"], revision["revision_id"], "README.md")
    assert error.value.code == "workspace_path_refused"


def _symlink(target: Path, link: Path, directory=False):
    try:
        link.symlink_to(target, target_is_directory=directory)
    except OSError:
        pytest.skip("Symlink creation is not available to this account")


def test_source_symlinks_are_not_imported(imported, tmp_path):
    store, _, project = imported
    outside = tmp_path / "outside.py"
    outside.write_text("secret outside source", encoding="utf-8")
    _symlink(outside, project / "linked.py")
    fresh = store.create_workspace("examples:small")
    assert "linked.py" not in {r["path"] for r in store.get_revision(fresh["workspace_id"])["files"]}


def test_linked_storage_and_materialize_destinations_are_refused(imported, tmp_path, source):
    store, workspace, _ = imported
    linked = tmp_path / "linked"
    _symlink(store.root, linked, directory=True)
    with pytest.raises(WorkspaceError) as error:
        WorkspaceStore(linked, source[1])
    assert error.value.code == "workspace_path_refused"
    with pytest.raises(WorkspaceError) as error:
        store.materialize(workspace["workspace_id"], workspace["head_revision"], linked / "copy")
    assert error.value.code == "workspace_path_refused"


def test_linked_blob_is_refused_even_when_contents_match(imported, tmp_path):
    store, workspace, _ = imported
    revision = store.get_revision(workspace["workspace_id"])
    row = next(r for r in revision["files"] if r["path"] == "README.md")
    blob = store.root / "blobs" / row["sha256"][:2] / row["sha256"]
    external = tmp_path / "external.md"
    external.write_bytes(blob.read_bytes())
    blob.unlink()
    _symlink(external, blob)
    with pytest.raises(WorkspaceError) as error:
        store.read_file(workspace["workspace_id"], revision["revision_id"], "README.md")
    assert error.value.code == "workspace_path_refused"
