"""Read-only, bounded evidence from explicitly trusted standard Projects.

This module never imports a Project, executes its configuration or constructs a
Solver. Project identifiers are handles in configured roots, not host paths.
"""
from __future__ import annotations

import ast
from collections.abc import Mapping
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import stat
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile


SCHEMA = "nsgablack.project_sources/v1"
_REPO_ROOT = Path(__file__).resolve().parent.parent
_TEXT_SUFFIXES = {".py", ".md", ".json", ".toml"}
_DATA_SUFFIXES = {".csv", ".xlsx", ".json"}
_ALLOWED_SUFFIXES = _TEXT_SUFFIXES | _DATA_SUFFIXES
_EXCLUDED_DIRS = {
    "runs", "run_logs", "exports", "artifacts", "outputs", "output", "results",
    "node_modules", "__pycache__", "venv", "env", "build", "dist",
}
_SENSITIVE_NAME = re.compile(
    r"secret|credential|password|api[_-]?key|private[_-]?key|access[_-]?token|id_rsa|id_ed25519", re.I)
_SENSITIVE_CONTENT = re.compile(
    r"(?<![A-Za-z0-9_])[\"']?(?:api[_-]?key|password|client[_-]?secret|access[_-]?token|private[_-]?key|authorization|token)[\"']?"
    r"\s*[:=]\s*[\"'][^\"'\r\n]+", re.I)
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_PROJECT_BYTES = 64 * 1024 * 1024
MAX_PROJECT_FILES = 1024
MAX_TEXT_BYTES = 512 * 1024
MAX_EXCERPT_CHARS = 14000
MAX_INSPECTION_BYTES = 24 * 1024
MAX_FIND_EXCERPT_BYTES = 6000
MAX_XML_BYTES = 8 * 1024 * 1024
MAX_ZIP_XML_BYTES = 32 * 1024 * 1024
_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


class ProjectSourceError(ValueError):
    """A fixed error category; no secret content or absolute host path escapes."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _fail(code, message):
    raise ProjectSourceError(code, message)


def _bounded_integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        _fail("invalid_source_request", f"Invalid {name}.")
    return value


def _linked(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(getattr(info, "st_file_attributes", 0) & reparse) or stat.S_ISLNK(info.st_mode)


def _allowed_name(relative: PurePosixPath) -> bool:
    for part in relative.parts:
        if part.startswith(".") and part != ".case":
            return False
        if part.lower() in _EXCLUDED_DIRS or _SENSITIVE_NAME.search(part):
            return False
    return relative.name == ".case" or relative.suffix.lower() in _ALLOWED_SUFFIXES


def _decode_text(data: bytes) -> tuple[str, str]:
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            pass
    _fail("source_encoding_unsupported", "The file has no supported text encoding.")


def _safe_value(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, str):
        return value[:1000]
    return value


def _json_shape(value, depth=0, budget=None):
    budget = [100] if budget is None else budget
    budget[0] -= 1
    if isinstance(value, dict):
        if depth >= 3:
            return {"type": "object", "property_count": len(value)}
        properties = {}
        for key, item in list(value.items())[:30]:
            if budget[0] <= 0:
                break
            properties[str(key)[:80]] = _json_shape(item, depth + 1, budget)
        return {"type": "object", "property_count": len(value), "properties": properties,
                "properties_truncated": len(properties) < len(value)}
    if isinstance(value, list):
        return {"type": "array", "length": len(value),
                "item": _json_shape(value[0], depth + 1, budget) if value and depth < 4 and budget[0] > 0 else None}
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, (int, float)):
        return {"type": "number"}
    return {"type": "string"}


def _bound_inspection(result):
    """Shrink previews, never the measured row/column counts or source digest."""
    def oversized():
        return len(json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")) > MAX_INSPECTION_BYTES

    tables = result.get("sheets", []) if result.get("format") == "xlsx" else [result]
    while oversized():
        available = [table for table in tables if table.get("sample_rows")]
        if available:
            table = max(available, key=lambda item: len(json.dumps(item["sample_rows"], ensure_ascii=False)))
            table["sample_rows"].pop()
            table["sample_rows_truncated"] = True
            continue
        available = [table for table in tables if table.get("columns")]
        if available:
            table = max(available, key=lambda item: len(json.dumps(item["columns"], ensure_ascii=False)))
            table["columns"].pop()
            table["sample_columns_truncated"] = True
            continue
        _fail("data_budget_exceeded", "The data structure exceeds the inspection response budget.")
    return result


def _read_xml(archive, name):
    try:
        info = archive.getinfo(name)
        if info.file_size > MAX_XML_BYTES:
            _fail("data_budget_exceeded", "An XML member exceeds the inspection budget.")
        data = archive.read(info)
    except KeyError:
        _fail("data_format_invalid", "The workbook is missing a required XML member.")
    except (BadZipFile, RuntimeError, NotImplementedError):
        _fail("data_format_invalid", "The workbook has an unreadable XML member.")
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        _fail("data_format_invalid", "XML entity declarations are not supported.")
    try:
        return ET.fromstring(data)
    except ET.ParseError:
        _fail("data_format_invalid", "The workbook XML is invalid.")


def _column_index(reference):
    match = re.fullmatch(r"([A-Z]{1,3})[1-9][0-9]{0,6}", reference or "")
    if not match:
        _fail("data_format_invalid", "The workbook has an invalid cell address.")
    result = 0
    for character in match.group(1):
        result = result * 26 + ord(character) - 64
    if result > 16384:
        _fail("data_budget_exceeded", "The workbook exceeds the supported column count.")
    return result - 1


def _xlsx_structure(data, max_rows, sheet_name):
    try:
        archive = ZipFile(io.BytesIO(data))
    except BadZipFile:
        _fail("data_format_invalid", "The file is not an XLSX workbook.")
    with archive:
        members = archive.infolist()
        if len(members) > 256 or sum(item.file_size for item in members) > MAX_ZIP_XML_BYTES:
            _fail("data_budget_exceeded", "The workbook exceeds the inspection budget.")
        if any(item.flag_bits & 1 for item in members):
            _fail("data_format_invalid", "Encrypted workbook members are not supported.")
        names = [item.filename for item in members]
        if (len(names) != len(set(names)) or any(
                "\\" in name or PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts
                for name in names)):
            _fail("data_format_invalid", "The workbook has unsafe or duplicate member names.")
        workbook = _read_xml(archive, "xl/workbook.xml")
        relationships = _read_xml(archive, "xl/_rels/workbook.xml.rels")
        targets = {}
        for row in relationships:
            if row.attrib.get("TargetMode") == "External":
                continue
            target = row.attrib.get("Target", "")
            target = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
            if not target.startswith("xl/") or ".." in PurePosixPath(target).parts:
                _fail("data_format_invalid", "The workbook has an unsafe worksheet target.")
            targets[row.attrib.get("Id")] = target
        shared = []
        if "xl/sharedStrings.xml" in names:
            shared = ["".join(row.itertext()) for row in _read_xml(archive, "xl/sharedStrings.xml")]
        sheets = workbook.findall(f"{_MAIN}sheets/{_MAIN}sheet")
        if len(sheets) > 32:
            _fail("data_budget_exceeded", "The workbook has too many sheets.")
        selected = [row for row in sheets if sheet_name is None or row.attrib.get("name") == sheet_name]
        if not selected:
            _fail("data_sheet_missing", "The requested worksheet does not exist.")
        results = []
        for sheet in selected[:8]:
            target = targets.get(sheet.attrib.get(f"{_REL}id"))
            if not target:
                _fail("data_format_invalid", "The worksheet has no local XML target.")
            root = _read_xml(archive, target)
            dimension = root.find(f"{_MAIN}dimension")
            sampled, nonempty_rows, columns, formulas = [], 0, 0, False
            for row in root.findall(f"{_MAIN}sheetData/{_MAIN}row"):
                cells = {}
                row_cells = row.findall(f"{_MAIN}c")
                for cell in row_cells:
                    index = _column_index(cell.attrib.get("r"))
                    columns = max(columns, index + 1)
                    raw = cell.findtext(f"{_MAIN}v")
                    cell_type = cell.attrib.get("t")
                    formulas = formulas or cell.find(f"{_MAIN}f") is not None
                    if cell_type == "s" and raw is not None:
                        try:
                            shared_index = int(raw)
                            if not 0 <= shared_index < len(shared):
                                raise IndexError()
                            value = shared[shared_index]
                        except (ValueError, IndexError):
                            _fail("data_format_invalid", "The workbook has an invalid shared string reference.")
                    elif cell_type == "inlineStr":
                        inline = cell.find(f"{_MAIN}is")
                        value = "".join(inline.itertext()) if inline is not None else ""
                    elif cell_type == "b" and raw is not None:
                        value = raw == "1"
                    elif raw is not None and cell_type not in {"str", "e"}:
                        try:
                            value = float(raw)
                            if math.isfinite(value) and value.is_integer():
                                value = int(value)
                        except ValueError:
                            value = raw
                    else:
                        value = raw
                    if index < 100:
                        cells[index] = _safe_value(value)
                if row_cells:
                    nonempty_rows += 1
                    if len(sampled) <= max_rows:
                        sampled.append(cells)
            width = min(columns, 100)
            values = [[row.get(index) for index in range(width)] for row in sampled]
            headers = values[0] if values else []
            if any(_SENSITIVE_NAME.search(str(item)) for item in headers if item is not None):
                _fail("source_sensitive", "Credential-shaped data columns are not exposed.")
            results.append({"name": sheet.attrib.get("name", ""), "row_count": nonempty_rows,
                            "data_row_count": max(0, nonempty_rows - 1), "column_count": columns,
                            "declared_range": dimension.attrib.get("ref") if dimension is not None else None,
                            "columns": headers, "sample_rows": values[1:],
                            "sample_columns_truncated": columns > 100,
                            "formulas_present": formulas, "formula_values": "cached_only"})
        return {"format": "xlsx", "sheet_count": len(sheets), "sheets": results,
                "sheets_truncated": len(selected) > 8}


class ProjectSourceRegistry:
    """Discover and inspect configured trusted standard Project directories."""

    def __init__(self, roots: Mapping[str, str | Path] | None = None):
        selected = {"examples": _REPO_ROOT / "examples" / "cases"} if roots is None else roots
        if not isinstance(selected, Mapping) or not selected:
            _fail("invalid_source_roots", "At least one trusted source root is required.")
        self.roots = {}
        for name, directory in selected.items():
            if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", name):
                _fail("invalid_source_roots", "A source root identifier is invalid.")
            path = Path(directory).resolve()
            if not path.is_dir():
                _fail("invalid_source_roots", "A configured source root does not exist.")
            self.roots[name] = path

    @staticmethod
    def _formal_project(path):
        return (path.is_dir() and not _linked(path)
                and (path / "cases").is_dir() and not _linked(path / "cases")
                and all((path / name).is_file() and not _linked(path / name)
                        for name in ("project_config.py", "run_project.py", "cases/__init__.py")))

    def _projects(self, *, roots=None):
        projects = {}
        for name, root in (self.roots if roots is None else roots).items():
            candidates = [root] if self._formal_project(root) else sorted(root.iterdir(), key=lambda p: p.name)
            for candidate in candidates:
                if candidate.name.startswith(".") or not self._formal_project(candidate):
                    continue
                relative = candidate.relative_to(root).as_posix()
                projects[f"{name}:{relative}"] = candidate
        return projects

    def resolve_project(self, project_id: str) -> Path:
        """Internal host-side resolver; do not serialize its absolute path to a model."""
        if not isinstance(project_id, str) or len(project_id) > 240:
            _fail("project_missing", "The selected Project is not available.")
        root_name, separator, relative = project_id.partition(":")
        root = self.roots.get(root_name)
        item = PurePosixPath(relative)
        if (not separator or root is None or not relative or "\\" in relative or ":" in relative
                or "\x00" in relative or item.is_absolute() or ".." in item.parts
                or len(item.parts) > 1 or relative != item.as_posix()
                or relative.startswith(".") and relative != "."):
            _fail("project_missing", "The selected Project is not available.")
        path = root if relative == "." else root / relative
        if (relative != "." and self._formal_project(root)) or not self._formal_project(path):
            _fail("project_missing", "The selected Project is not available.")
        try:
            path.resolve().relative_to(root)
        except (OSError, ValueError):
            _fail("project_missing", "The selected Project is outside its trusted root.")
        return path

    def _resolve_file(self, project_id, relative_path):
        project = self.resolve_project(project_id)
        if (not isinstance(relative_path, str) or not relative_path or len(relative_path) > 400
                or "\\" in relative_path or ":" in relative_path or "\x00" in relative_path):
            _fail("source_path_refused", "The source path is not allowed.")
        relative = PurePosixPath(relative_path)
        if (relative.is_absolute() or ".." in relative.parts or relative_path != relative.as_posix()
                or not _allowed_name(relative)):
            _fail("source_path_refused", "The source path is not allowed.")
        candidate = project.joinpath(*relative.parts)
        for parent in (candidate, *candidate.parents):
            if _linked(parent):
                _fail("source_path_refused", "Linked source paths are not allowed.")
            if parent == project:
                break
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(project.resolve())
        except (OSError, ValueError):
            _fail("source_missing", "The requested source file is unavailable.")
        if not resolved.is_file():
            _fail("source_missing", "The requested source file is unavailable.")
        return resolved, relative.as_posix()

    def _read(self, project_id, relative_path, *, maximum=MAX_FILE_BYTES):
        path, relative = self._resolve_file(project_id, relative_path)
        before = path.stat()
        if before.st_size > maximum:
            _fail("source_budget_exceeded", "The source file exceeds the read budget.")
        with path.open("rb") as stream:
            data = stream.read(maximum + 1)
        after = path.stat()
        if len(data) > maximum or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            _fail("source_changed", "The source changed while it was being read.")
        checked, _ = self._resolve_file(project_id, relative)
        if checked != path:
            _fail("source_changed", "The source path changed while it was being read.")
        return data, {"project_id": project_id, "path": relative,
                      "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

    def _files(self, project_id):
        project = self.resolve_project(project_id)
        files = []
        for directory, children, names in os.walk(project, followlinks=False):
            base = Path(directory)
            children[:] = sorted(name for name in children if not name.startswith(".")
                                 and name.lower() not in _EXCLUDED_DIRS
                                 and not _SENSITIVE_NAME.search(name) and not _linked(base / name))
            for name in sorted(names):
                relative = (base / name).relative_to(project).as_posix()
                if _allowed_name(PurePosixPath(relative)) and not _linked(base / name):
                    files.append(relative)
                    if len(files) > MAX_PROJECT_FILES:
                        _fail("project_budget_exceeded", "The Project has too many readable files.")
        return sorted(files)

    def snapshot_manifest(self, project_id):
        """Return the exact allowed source/data closure for a versioned copy."""
        files, total = [], 0
        for relative in self._files(project_id):
            data, source = self._read(project_id, relative)
            if Path(relative).suffix.lower() in _TEXT_SUFFIXES or Path(relative).name == ".case":
                text, _ = _decode_text(data)
                if _SENSITIVE_CONTENT.search(text):
                    continue
            total += len(data)
            if total > MAX_PROJECT_BYTES:
                _fail("project_budget_exceeded", "The Project exceeds the source snapshot budget.")
            files.append({key: value for key, value in source.items() if key != "project_id"} |
                         {"kind": "data" if Path(relative).suffix.lower() in {".csv", ".xlsx"} else "source"})
        digest = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return {"schema": SCHEMA, "project_id": project_id, "revision": digest,
                "source_digest": digest, "total_bytes": total, "files": files}

    def resolve_case(self, project_id, case_id):
        if not isinstance(case_id, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", case_id):
            _fail("case_missing", "The selected Case is not available.")
        project = self.resolve_project(project_id)
        path = project / "cases" / case_id
        if (_linked(project / "cases") or _linked(path) or not path.is_dir()
                or any(not (path / name).is_file() or _linked(path / name)
                       for name in ("__init__.py", "build_solver.py", "run_solver.py"))):
            _fail("case_missing", "The selected Case is not a standard runnable Case.")
        try:
            path.resolve().relative_to(project.resolve())
        except (OSError, ValueError):
            _fail("case_missing", "The selected Case is outside its Project.")
        return path

    def describe_project(self, project_id):
        project = self.resolve_project(project_id)
        manifest = self.snapshot_manifest(project_id)
        cases = []
        for candidate in sorted((project / "cases").iterdir(), key=lambda p: p.name):
            if candidate.is_dir() and not candidate.name.startswith("_"):
                try:
                    self.resolve_case(project_id, candidate.name)
                except ProjectSourceError:
                    continue
                cases.append(candidate.name)
        title = project.name
        try:
            data, _ = self._read(project_id, "project_config.py", maximum=MAX_TEXT_BYTES)
            tree = ast.parse(_decode_text(data)[0])
            for node in tree.body:
                if (isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
                        and target.id == "PROJECT_NAME" for target in node.targets)
                        and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
                    title = node.value.value[:200]
        except (SyntaxError, ProjectSourceError):
            pass
        return manifest | {"title": title, "case_ids": cases, "case_names": cases,
                           "relative_path": project_id.split(":", 1)[1]}

    def browse_projects(self, query="", *, limit=100):
        """List directory metadata without reading or hashing Project contents.

        This is an unversioned chooser, not source evidence. Creating a workspace
        must still obtain a complete checked snapshot; ``search_projects`` keeps
        its existing evidence-producing behavior for project collaboration.
        """
        _bounded_integer(limit, 1, 100, "limit")
        if not isinstance(query, str) or len(query) > 300:
            _fail("invalid_source_request", "The project query is invalid.")
        terms = [term for term in re.split(r"[\s_/-]+", query.casefold()) if term]
        # A configured directory may have been replaced since registration.
        # Do not enumerate a newly linked root or linked ancestor.
        roots = {name: root for name, root in self.roots.items()
                 if root.is_dir() and not any(_linked(item) for item in (root, *root.parents))}
        matches, unavailable = [], 0
        for project_id, directory in self._projects(roots=roots).items():
            if directory.name.lower() in _EXCLUDED_DIRS or _SENSITIVE_NAME.search(directory.name):
                continue
            try:
                project = self.resolve_project(project_id)
                cases = []
                for candidate in sorted((project / "cases").iterdir(), key=lambda item: item.name):
                    if (candidate.name.startswith("_") or candidate.name.startswith(".")
                            or _SENSITIVE_NAME.search(candidate.name)
                            or candidate.name.lower() in _EXCLUDED_DIRS):
                        continue
                    try:
                        self.resolve_case(project_id, candidate.name)
                    except ProjectSourceError:
                        continue
                    cases.append(candidate.name)
                haystack = " ".join((project_id, project.name, *cases)).casefold()
                score = sum(term in haystack for term in terms)
                if terms and not score:
                    continue
                matches.append((score, {"project_id": project_id, "title": project.name,
                    "relative_path": project_id.split(":", 1)[1],
                    "case_ids": cases, "case_names": cases.copy()}))
            except (OSError, ProjectSourceError):
                # Directory metadata can become stale while it is displayed;
                # never replace an unavailable source with a different path.
                unavailable += 1
        matches.sort(key=lambda item: (-item[0], item[1]["project_id"]))
        return {"schema": SCHEMA, "scope": "directory_metadata_only",
                "projects": [record for _, record in matches[:limit]],
                "total": len(matches), "truncated": len(matches) > limit,
                "unavailable_projects": unavailable}

    def search_projects(self, query="", *, limit=20):
        _bounded_integer(limit, 1, 100, "limit")
        if not isinstance(query, str) or len(query) > 300:
            _fail("invalid_source_request", "The project query is invalid.")
        terms = [term for term in re.split(r"[\s_/-]+", query.lower()) if term]
        candidates = []
        unavailable = 0
        for project_id, directory in self._projects().items():
            case_names = [item.name for item in sorted((directory / "cases").iterdir())
                          if item.is_dir() and not item.name.startswith("_") and not _linked(item)]
            snippets = []
            for relative in (["README.md", *(f"cases/{case}/README.md" for case in case_names[:8])]
                             if terms else []):
                try:
                    raw, _ = self._read(project_id, relative, maximum=MAX_TEXT_BYTES)
                    body, _ = _decode_text(raw)
                    if not _SENSITIVE_CONTENT.search(body):
                        snippets.append(body[:2500])
                except ProjectSourceError:
                    pass
            haystack = " ".join([project_id, directory.name, *case_names, *snippets]).lower()
            score = sum(term in haystack for term in terms)
            if terms and not score:
                continue
            candidates.append((score, project_id))
        candidates.sort(key=lambda row: (-row[0], row[1]))
        matches = []
        for _, project_id in candidates:
            if len(matches) >= limit:
                break
            try:
                project = self.describe_project(project_id)
            except ProjectSourceError:
                unavailable += 1
                continue
            matches.append({key: project[key] for key in (
                "project_id", "title", "case_ids", "case_names", "revision", "source_digest", "relative_path")})
        return {"schema": SCHEMA, "projects": matches,
                "total": len(candidates), "truncated": len(candidates) > len(matches),
                "unavailable_projects": unavailable}

    def list_project_files(self, project_id, *, case_id=None, limit=80, offset=0):
        _bounded_integer(limit, 1, 200, "limit")
        _bounded_integer(offset, 0, MAX_PROJECT_FILES, "offset")
        manifest = self.snapshot_manifest(project_id)
        files = manifest["files"]
        if case_id is not None:
            self.resolve_case(project_id, case_id)
            prefix = f"cases/{case_id}/"
            files = [row for row in files if row["path"].startswith(prefix)]
        return {"schema": SCHEMA, "project_id": project_id, "revision": manifest["revision"],
                "source_digest": manifest["revision"], "files": files[offset:offset + limit],
                "offset": offset, "next_offset": offset + limit if offset + limit < len(files) else None,
                "total": len(files), "truncated": offset + limit < len(files)}

    def read_project_source(self, project_id, path, *, start_line=1, max_lines=120):
        _bounded_integer(start_line, 1, 1000000, "start_line")
        _bounded_integer(max_lines, 1, 200, "max_lines")
        if PurePosixPath(str(path)).suffix.lower() not in _TEXT_SUFFIXES and PurePosixPath(str(path)).name != ".case":
            _fail("source_type_refused", "Use the data inspection tool for data files.")
        data, source = self._read(project_id, path, maximum=MAX_TEXT_BYTES)
        text, encoding = _decode_text(data)
        if _SENSITIVE_CONTENT.search(text):
            _fail("source_sensitive", "Credential-shaped source content is not exposed.")
        lines = text.splitlines()
        if start_line > max(1, len(lines)):
            _fail("source_range_invalid", "The requested line is beyond this source file.")
        selected = lines[start_line - 1:start_line - 1 + max_lines]
        while selected and len("\n".join(selected)) > MAX_EXCERPT_CHARS:
            selected.pop()
        if not selected and start_line <= len(lines):
            _fail("source_budget_exceeded", "A source line exceeds the excerpt budget.")
        excerpt = "\n".join(selected)
        return {"schema": SCHEMA, "source": source, "encoding": encoding,
                "start_line": start_line, "end_line": start_line + len(selected) - 1,
                "total_lines": len(lines), "excerpt": excerpt,
                "truncated": start_line - 1 + len(selected) < len(lines)}

    def find_project_source(self, project_id, path, query, *, max_matches=12, context_lines=2):
        """Find literal, Unicode-casefolded text in one allowed source file.

        A match is one source line, even when the literal occurs more than once.
        Query length is 1..200 characters, max_matches is 1..20 and context_lines
        is 0..5. The complete JSON result is at most MAX_INSPECTION_BYTES.
        """
        _bounded_integer(max_matches, 1, 20, "max_matches")
        _bounded_integer(context_lines, 0, 5, "context_lines")
        if not isinstance(query, str) or not 1 <= len(query) <= 200 or not query.strip():
            _fail("invalid_source_request", "A nonempty literal query of at most 200 characters is required.")
        if PurePosixPath(str(path)).suffix.lower() not in _TEXT_SUFFIXES and PurePosixPath(str(path)).name != ".case":
            _fail("source_type_refused", "Only allowed text sources can be searched.")
        data, source = self._read(project_id, path, maximum=MAX_TEXT_BYTES)
        text, encoding = _decode_text(data)
        if _SENSITIVE_CONTENT.search(text):
            _fail("source_sensitive", "Credential-shaped source content is not exposed.")
        lines = text.splitlines()
        folded = query.casefold()
        positions = [index for index, line in enumerate(lines) if folded in line.casefold()]
        output = {"schema": SCHEMA, "source": source, "encoding": encoding, "query": query,
                  "case_sensitive": False, "match_unit": "line", "matches": [],
                  "total_matches": len(positions), "total_lines": len(lines), "truncated": False}
        for index in positions[:max_matches]:
            start, stop = max(0, index - context_lines), min(len(lines), index + context_lines + 1)
            excerpt = "\n".join(lines[start:stop])
            record = {"line": index + 1, "start_line": start + 1, "end_line": stop,
                      "excerpt": excerpt, "excerpt_truncated": False}
            if len(excerpt.encode("utf-8")) > MAX_FIND_EXCERPT_BYTES:
                start, stop, excerpt = index, index + 1, lines[index]
                record.update(start_line=index + 1, end_line=index + 1, excerpt_truncated=True)
                if len(excerpt.encode("utf-8")) > MAX_FIND_EXCERPT_BYTES:
                    # Locate the original character even when casefold expands
                    # characters (for example, German sharp s becomes "ss").
                    folded_position = excerpt.casefold().find(folded)
                    consumed, original_position = 0, 0
                    for original_position, character in enumerate(excerpt):
                        if consumed + len(character.casefold()) > folded_position:
                            break
                        consumed += len(character.casefold())
                    first = max(0, original_position - 500)
                    last = min(len(excerpt), original_position + len(query) + 500)
                    excerpt = excerpt[first:last]
                    record.update(excerpt_start_column=first + 1, excerpt_end_column=last)
                record["excerpt"] = excerpt
            output["matches"].append(record)
            output["truncated"] = (len(output["matches"]) < len(positions)
                                   or any(row["excerpt_truncated"] for row in output["matches"]))
            if len(json.dumps(output, ensure_ascii=False, allow_nan=False).encode("utf-8")) > MAX_INSPECTION_BYTES:
                output["matches"].pop()
                output["truncated"] = True
                break
        output["truncated"] = (output["truncated"] or len(output["matches"]) < len(positions))
        return output

    def inspect_project_data(self, project_id, path, *, max_rows=5, sheet_name=None):
        _bounded_integer(max_rows, 0, 20, "max_rows")
        if sheet_name is not None and (not isinstance(sheet_name, str) or len(sheet_name) > 100):
            _fail("invalid_source_request", "The worksheet name is invalid.")
        suffix = PurePosixPath(str(path)).suffix.lower()
        if suffix not in _DATA_SUFFIXES:
            _fail("source_type_refused", "Only CSV, XLSX and JSON data can be inspected.")
        data, source = self._read(project_id, path)
        if suffix == ".xlsx":
            result = _xlsx_structure(data, max_rows, sheet_name)
        else:
            text, encoding = _decode_text(data)
            if _SENSITIVE_CONTENT.search(text):
                _fail("source_sensitive", "Credential-shaped data content is not exposed.")
            if suffix == ".json":
                try:
                    value = json.loads(text, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
                except (ValueError, RecursionError):
                    _fail("data_format_invalid", "The JSON data is invalid.")
                result = {"format": "json", "encoding": encoding, "structure": _json_shape(value)}
            else:
                try:
                    rows = csv.reader(io.StringIO(text), strict=True)
                    header = next(rows, [])
                    if len(header) > 1000:
                        _fail("data_budget_exceeded", "The CSV has too many columns.")
                    if any(_SENSITIVE_NAME.search(name) for name in header):
                        _fail("source_sensitive", "Credential-shaped data columns are not exposed.")
                    count, samples, minimum, maximum = 0, [], len(header), len(header)
                    for row in rows:
                        count += 1
                        minimum, maximum = min(minimum, len(row)), max(maximum, len(row))
                        if len(row) > 1000:
                            _fail("data_budget_exceeded", "The CSV has too many columns.")
                        if len(samples) < max_rows:
                            samples.append([_safe_value(value) for value in row[:100]])
                except csv.Error:
                    _fail("data_format_invalid", "The CSV data is invalid.")
                result = {"format": "csv", "encoding": encoding, "columns": [_safe_value(name) for name in header[:100]],
                          "column_count": len(header), "data_row_count": count,
                          "row_count": count + bool(header), "row_width_min": minimum,
                          "row_width_max": maximum, "sample_rows": samples,
                          "sample_columns_truncated": max(len(header), maximum) > 100}
        return _bound_inspection({"schema": SCHEMA, "source": source, "inspection_only": True,
                                 "executed": False, **result})


__all__ = ["ProjectSourceError", "ProjectSourceRegistry", "SCHEMA"]
