"""Local Project revisions; source access never imports or runs a Project.

SQLite atomically advances each workspace head. Immutable file blobs are shared
between revisions, including read-only CSV/XLSX inputs. A materialized Project is
always a detached copy, never a hard link to those blobs or the original source.
"""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
from uuid import uuid4

from .lab_project_sources import (
    MAX_PROJECT_BYTES, MAX_PROJECT_FILES, MAX_TEXT_BYTES, ProjectSourceError,
    ProjectSourceRegistry, _allowed_name, _decode_text, _linked, _SENSITIVE_CONTENT,
    _TEXT_SUFFIXES,
)


SCHEMA = "nsgablack.project_workspace/v1"
REVISION_SCHEMA = "nsgablack.project_workspace_revision/v1"
_ID = re.compile(r"[0-9a-f]{32}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_PY_ENCODING = re.compile(r"^([ \t\f]*#.*?coding[:=][ \t]*)([-_.a-zA-Z0-9]+)")


class WorkspaceError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _fail(code: str, message: str):
    raise WorkspaceError(code, message)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _identity(value, name="identity") -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        _fail("workspace_identity_invalid", f"Invalid {name}.")
    return value


def _no_links(path: Path) -> None:
    for item in (path, *path.parents):
        if _linked(item):
            _fail("workspace_path_refused", "Linked workspace paths are not allowed.")


def _relative(value: str) -> str:
    if (not isinstance(value, str) or not value or len(value) > 400
            or any(c in value for c in ("\\", ":", "\x00"))):
        _fail("workspace_path_refused", "The workspace file path is not allowed.")
    path = PurePosixPath(value)
    if (path.is_absolute() or ".." in path.parts or value != path.as_posix()
            or not _allowed_name(path)):
        _fail("workspace_path_refused", "The workspace file path is not allowed.")
    return value


def _source_digest(files: list[dict]) -> str:
    # Exactly the digest used by ProjectSourceRegistry.snapshot_manifest.
    return hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _editable(path: str) -> bool:
    item = PurePosixPath(path)
    return item.suffix.lower() in _TEXT_SUFFIXES or item.name == ".case"


def _utf8_python_header(path: str, content: str) -> str:
    """The saved bytes are UTF-8, so any Python coding cookie must agree."""
    if PurePosixPath(path).suffix.lower() != ".py":
        return content
    lines = content.splitlines(keepends=True)
    for index in range(min(2, len(lines))):
        match = _PY_ENCODING.match(lines[index])
        if match:
            lines[index] = lines[index][:match.start(2)] + "utf-8" + lines[index][match.end(2):]
    return "".join(lines)


class WorkspaceStore:
    """Persist local editing history under an operator-selected directory.

    IDs and relative paths may come from the UI. The root and source registry
    must be selected by trusted local configuration, never by a browser field.
    """

    def __init__(self, root: Path, sources: ProjectSourceRegistry):
        if not isinstance(sources, ProjectSourceRegistry):
            _fail("workspace_sources_invalid", "A trusted Project source registry is required.")
        root = Path(root).absolute()
        _no_links(root)
        root.mkdir(parents=True, exist_ok=True)
        self.root, self.sources = root.resolve(), sources
        self._db = self.root / "workspace.sqlite3"
        self._blobs = self.root / "blobs"
        self._blobs.mkdir(exist_ok=True)
        with self._connection() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS workspaces (
                    workspace_id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS revisions (
                    revision_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL,
                    data TEXT NOT NULL,
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id));
                CREATE INDEX IF NOT EXISTS workspace_revisions ON revisions(workspace_id);
            """)

    @contextmanager
    def _connection(self):
        _no_links(self._db)
        connection = sqlite3.connect(self._db, timeout=20)
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _blob_path(self, digest: str) -> Path:
        if not isinstance(digest, str) or not _SHA.fullmatch(digest):
            _fail("workspace_manifest_invalid", "A workspace file digest is invalid.")
        result = self._blobs / digest[:2] / digest
        _no_links(result)
        return result

    def _read_blob(self, row: dict) -> bytes:
        path = self._blob_path(row["sha256"])
        try:
            if path.stat().st_size != row["size_bytes"]:
                raise ValueError()
            data = path.read_bytes()
        except (OSError, ValueError):
            _fail("workspace_blob_invalid", "A saved workspace file is missing or damaged.")
        if hashlib.sha256(data).hexdigest() != row["sha256"]:
            _fail("workspace_blob_invalid", "A saved workspace file failed its digest check.")
        return data

    def _write_blob(self, data: bytes) -> str:
        digest = hashlib.sha256(data).hexdigest()
        target = self._blob_path(digest)
        if target.exists():
            self._read_blob({"sha256": digest, "size_bytes": len(data)})
            return digest
        target.parent.mkdir(exist_ok=True)
        _no_links(target)
        temporary = target.with_name(digest + "." + uuid4().hex + ".tmp")
        try:
            with temporary.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()
        return digest

    def list_sources(self) -> list[dict]:
        return self.sources.browse_projects(limit=100)["projects"]

    def list_workspaces(self) -> list[dict]:
        with self._connection() as connection:
            identities = [row[0] for row in connection.execute(
                "SELECT workspace_id FROM workspaces ORDER BY rowid DESC")]
            return [self._workspace(connection, identity) for identity in identities]

    @staticmethod
    def _workspace(connection, workspace_id: str) -> dict:
        _identity(workspace_id, "workspace_id")
        row = connection.execute("SELECT data FROM workspaces WHERE workspace_id=?", (workspace_id,)).fetchone()
        if row is None:
            _fail("workspace_missing", "The selected workspace does not exist.")
        try:
            workspace = json.loads(row[0])
        except (ValueError, TypeError):
            _fail("workspace_metadata_invalid", "The saved workspace metadata is invalid.")
        if (not isinstance(workspace, dict) or workspace.get("schema") != SCHEMA
                or workspace.get("workspace_id") != workspace_id
                or not isinstance(workspace.get("head_revision"), str)
                or not _ID.fullmatch(workspace["head_revision"])):
            _fail("workspace_metadata_invalid", "The saved workspace identity is inconsistent.")
        return workspace

    def get_workspace(self, workspace_id: str) -> dict:
        with self._connection() as connection:
            return self._workspace(connection, workspace_id)

    @staticmethod
    def _revision(connection, workspace_id: str, revision_id: str) -> dict:
        _identity(revision_id, "revision_id")
        row = connection.execute("SELECT data FROM revisions WHERE workspace_id=? AND revision_id=?",
                                 (workspace_id, revision_id)).fetchone()
        if row is None:
            _fail("workspace_revision_missing", "The selected workspace revision does not exist.")
        try:
            revision = json.loads(row[0])
        except (ValueError, TypeError):
            _fail("workspace_manifest_invalid", "The saved revision manifest is invalid.")
        if (not isinstance(revision, dict) or revision.get("schema") != REVISION_SCHEMA
                or revision.get("workspace_id") != workspace_id or revision.get("revision_id") != revision_id):
            _fail("workspace_manifest_invalid", "The saved revision identity is inconsistent.")
        files = revision.get("files")
        if not isinstance(files, list) or not 1 <= len(files) <= MAX_PROJECT_FILES:
            _fail("workspace_manifest_invalid", "The saved revision manifest is invalid.")
        previous = None
        total = 0
        for row in files:
            if not isinstance(row, dict) or set(row) != {"path", "size_bytes", "sha256", "kind"}:
                _fail("workspace_manifest_invalid", "A saved file manifest is invalid.")
            path = _relative(row["path"])
            if previous is not None and previous >= path:
                _fail("workspace_manifest_invalid", "Saved workspace paths must be unique and ordered.")
            if (type(row["size_bytes"]) is not int or row["size_bytes"] < 0
                    or not isinstance(row["sha256"], str) or not _SHA.fullmatch(row["sha256"])
                    or row["kind"] != ("data" if PurePosixPath(path).suffix.lower() in {".csv", ".xlsx"} else "source")):
                _fail("workspace_manifest_invalid", "A saved file manifest is invalid.")
            previous, total = path, total + row["size_bytes"]
        if total > MAX_PROJECT_BYTES or _source_digest(files) != revision.get("source_digest"):
            _fail("workspace_manifest_invalid", "The saved revision failed its source digest check.")
        return revision

    def get_revision(self, workspace_id: str, revision_id: str | None = None) -> dict:
        with self._connection() as connection:
            workspace = self._workspace(connection, workspace_id)
            selected = workspace["head_revision"] if revision_id is None else revision_id
            return self._revision(connection, workspace_id, selected)

    def list_revisions(self, workspace_id: str) -> list[dict]:
        with self._connection() as connection:
            self._workspace(connection, workspace_id)
            ids = [row[0] for row in connection.execute(
                "SELECT revision_id FROM revisions WHERE workspace_id=? ORDER BY rowid DESC", (workspace_id,))]
            return [self._revision(connection, workspace_id, identity) for identity in ids]

    def create_workspace(self, project_id: str, *, title: str | None = None) -> dict:
        if title is not None and (not isinstance(title, str) or not title.strip() or len(title) > 200):
            _fail("workspace_title_invalid", "Use a workspace title of 1 to 200 characters.")
        try:
            description = self.sources.describe_project(project_id)
            files = description["files"]
            for row in files:
                data, observed = self.sources._read(project_id, row["path"])
                if any(observed[key] != row[key] for key in ("size_bytes", "sha256")):
                    _fail("workspace_source_changed", "The source changed while the workspace was created.")
                self._write_blob(data)
            if self.sources.snapshot_manifest(project_id)["source_digest"] != description["source_digest"]:
                _fail("workspace_source_changed", "The source changed while the workspace was created.")
        except ProjectSourceError as exc:
            raise WorkspaceError(exc.code, str(exc)) from None
        identity, revision_id, created = uuid4().hex, uuid4().hex, _now()
        workspace = {"schema": SCHEMA, "workspace_id": identity,
                     "title": title.strip() if title is not None else description["title"],
                     "source_project_id": project_id, "source_revision": description["source_digest"],
                     "head_revision": revision_id, "created_at": created}
        revision = {"schema": REVISION_SCHEMA, "workspace_id": identity, "revision_id": revision_id,
                    "parent_revision": None, "source_digest": description["source_digest"],
                    "files": files, "created_at": created, "message": "Imported Project snapshot"}
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("INSERT INTO workspaces(workspace_id,data) VALUES (?,?)", (identity, _json(workspace)))
            connection.execute("INSERT INTO revisions(revision_id,workspace_id,data) VALUES (?,?,?)",
                               (revision_id, identity, _json(revision)))
        return workspace

    def read_file(self, workspace_id: str, revision_id: str, path: str) -> dict:
        path = _relative(path)
        revision = self.get_revision(workspace_id, revision_id)
        row = next((row for row in revision["files"] if row["path"] == path), None)
        if row is None:
            _fail("workspace_file_missing", "The selected file is not part of this revision.")
        editable = _editable(path) and row["size_bytes"] <= MAX_TEXT_BYTES
        if not editable:
            return {**row, "content": "", "encoding": None, "editable": False}
        data = self._read_blob(row)
        try:
            content, encoding = _decode_text(data)
        except ProjectSourceError as exc:
            raise WorkspaceError(exc.code, str(exc)) from None
        if _SENSITIVE_CONTENT.search(content):
            _fail("workspace_sensitive", "Credential-shaped file content is not exposed.")
        return {**row, "content": content, "encoding": encoding, "editable": True}

    def save_files(self, workspace_id: str, changes: Mapping[str, str], *,
                   expected_revision: str, message: str = "") -> dict:
        _identity(workspace_id, "workspace_id")
        _identity(expected_revision, "expected_revision")
        if not isinstance(changes, Mapping) or not changes or len(changes) > MAX_PROJECT_FILES:
            _fail("workspace_changes_invalid", "Provide at least one existing text file to save.")
        if not isinstance(message, str) or len(message) > 1000:
            _fail("workspace_message_invalid", "The revision note exceeds 1000 characters.")
        encoded = {}
        for path, content in changes.items():
            path = _relative(path)
            if not _editable(path) or not isinstance(content, str) or "\x00" in content:
                _fail("workspace_file_readonly", "Only existing supported text files can be edited.")
            if _SENSITIVE_CONTENT.search(content):
                _fail("workspace_sensitive", "Credential-shaped text must not be saved in a workspace.")
            content = _utf8_python_header(path, content)
            try:
                raw = content.encode("utf-8")
            except UnicodeEncodeError:
                _fail("workspace_encoding_invalid", "The edited text is not valid UTF-8.")
            if len(raw) > MAX_TEXT_BYTES:
                _fail("workspace_file_too_large", "The edited text exceeds the file size limit.")
            encoded[path] = raw
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            workspace = self._workspace(connection, workspace_id)
            if workspace["head_revision"] != expected_revision:
                _fail("workspace_revision_conflict", "The workspace has changed. Reload its current revision before saving.")
            old = self._revision(connection, workspace_id, expected_revision)
            existing = {row["path"]: row for row in old["files"]}
            if set(encoded) - existing.keys():
                _fail("workspace_file_missing", "New or deleted files are not supported by this editor.")
            updated = []
            for row in old["files"]:
                if row["path"] in encoded:
                    raw = encoded[row["path"]]
                    updated.append({**row, "sha256": self._write_blob(raw), "size_bytes": len(raw)})
                else:
                    updated.append(row)
            if sum(row["size_bytes"] for row in updated) > MAX_PROJECT_BYTES:
                _fail("workspace_project_too_large", "The saved Project exceeds the workspace size limit.")
            if updated == old["files"]:
                return old
            revision = {"schema": REVISION_SCHEMA, "workspace_id": workspace_id, "revision_id": uuid4().hex,
                        "parent_revision": expected_revision, "source_digest": _source_digest(updated),
                        "files": updated, "created_at": _now(), "message": message}
            connection.execute("INSERT INTO revisions(revision_id,workspace_id,data) VALUES (?,?,?)",
                               (revision["revision_id"], workspace_id, _json(revision)))
            workspace["head_revision"] = revision["revision_id"]
            connection.execute("UPDATE workspaces SET data=? WHERE workspace_id=?", (_json(workspace), workspace_id))
            return revision

    def materialize(self, workspace_id: str, revision_id: str, target: Path) -> Path:
        revision = self.get_revision(workspace_id, revision_id)
        target = Path(target).absolute()
        _no_links(target)
        if target.exists():
            _fail("workspace_target_exists", "Choose a new directory for the detached Project.")
        # Validate every blob before publishing any copy, so damage cannot look
        # like a usable partial materialization.
        payloads = [(row["path"], self._read_blob(row)) for row in revision["files"]]
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = target.with_name(target.name + ".incoming-" + uuid4().hex)
        staging.mkdir()
        try:
            for relative, data in payloads:
                destination = staging.joinpath(*PurePosixPath(relative).parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
            # os.rename refuses an existing destination on Windows; checking
            # again also avoids intentionally replacing a caller's directory.
            if target.exists():
                _fail("workspace_target_exists", "The detached Project destination already exists.")
            staging.rename(target)
        finally:
            if staging.exists():
                import shutil
                _no_links(staging)
                if (staging.resolve().parent != target.parent.resolve()
                        or not staging.name.startswith(target.name + ".incoming-")):
                    _fail("workspace_path_refused", "The temporary Project directory changed unexpectedly.")
                shutil.rmtree(staging)
        return target


__all__ = ["SCHEMA", "REVISION_SCHEMA", "WorkspaceError", "WorkspaceStore"]
