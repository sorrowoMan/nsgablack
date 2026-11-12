"""Static, bounded examples for Catalog discovery, separate from component facts.

The builder reads declarations and focused example manifests. It does not import
components or execute their commands. Execution labels require a matching receipt
from an independently run command against the same published source identity.
"""
from __future__ import annotations

import argparse
import ast
from collections.abc import Mapping
from datetime import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shlex
from typing import Any

try:
    import tomllib
except ImportError:  # Python 3.10
    import tomli as tomllib


SCHEMA = "nsgablack.catalog.examples/v1"
RECEIPTS_SCHEMA = "nsgablack.catalog.example_receipts/v1"
MAX_SOURCE_BYTES = 2 * 1024 * 1024
MAX_INDEX_BYTES = 16 * 1024 * 1024
MAX_SECTION_LINES = 480
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9_.-]{1,200}\Z")
_PRIVATE = frozenset({".git", ".venv", "venv", "__pycache__", "node_modules", "data", "datasets",
                      "artifacts", "results", "runs", "outputs", "checkpoints", "private", "secrets",
                      "attachments", "deployment", ".blackbase", "tests"})
_CREDENTIAL = re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----|\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{24,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,})\b")
_LIST_FIELDS = ("inputs", "steps", "dependencies", "expected_outputs")


class ExampleValidationError(ValueError):
    """An example or receipt does not match its declared source evidence."""


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _safe_file(roots: Mapping[str, Path], qualified: str) -> tuple[str, Path]:
    if not isinstance(qualified, str) or "\\" in qualified or ":" in qualified:
        raise ExampleValidationError("example_source_path_invalid")
    relative = PurePosixPath(qualified)
    parts = relative.parts
    if relative.is_absolute() or len(parts) < 2 or ".." in parts or parts[0] not in roots:
        raise ExampleValidationError("example_source_path_invalid")
    for part in parts[1:]:
        lower = part.lower()
        if lower in _PRIVATE or lower.startswith(".") or lower.startswith(("db.toml", "id_rsa", "id_ed25519")):
            raise ExampleValidationError("example_source_path_private")
    if relative.suffix.lower() not in {".py", ".md", ".rst", ".toml"}:
        raise ExampleValidationError("example_source_type_invalid")
    root = roots[parts[0]]
    target = root
    for part in parts[1:]:
        target = target / part
        if target.is_symlink() or bool(getattr(target, "is_junction", lambda: False)()):
            raise ExampleValidationError("example_source_link_refused")
    if not target.resolve().is_relative_to(root) or not target.is_file():
        raise ExampleValidationError("example_source_missing")
    if target.stat().st_size > MAX_SOURCE_BYTES:
        raise ExampleValidationError("example_source_oversized")
    return parts[0], target


def _read(roots: Mapping[str, Path], qualified: str) -> tuple[str, str]:
    _, path = _safe_file(roots, qualified)
    with path.open("rb") as handle:
        data = handle.read(MAX_SOURCE_BYTES + 1)
    if len(data) > MAX_SOURCE_BYTES:
        raise ExampleValidationError("example_source_oversized")
    text = data.decode("utf-8-sig")
    if _CREDENTIAL.search(text):
        raise ExampleValidationError("example_source_contains_credential")
    return text, hashlib.sha256(data).hexdigest()


def _closed_markdown_fences(lines) -> bool:
    fence = None
    for line in lines:
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not marker[2].strip():
                fence = None
        elif marker:
            fence = (marker[1][0], len(marker[1]))
    return fence is None


def _snippet(roots: Mapping[str, Path], source: Mapping[str, Any]) -> dict:
    qualified = str(source.get("path", ""))
    text, file_digest = _read(roots, qualified)
    lines = text.splitlines()
    start, end = source.get("start_line", 1), source.get("end_line", min(len(lines), 40))
    symbol = source.get("symbol")
    section = source.get("section")
    if section is not None:
        if (not isinstance(section, str) or not _ID.fullmatch(section)
                or not qualified.endswith(".md")
                or any(key in source for key in ("symbol", "start_line", "end_line"))):
            raise ExampleValidationError("example_source_section_invalid")
        # Bind a usage card to its component heading, not a moving line range.
        # Markdown-looking text inside a fenced code block is never a heading.
        headings, fence = [], None
        for number, line in enumerate(lines, 1):
            marker = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", line)
            if fence:
                if marker and marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not marker[2].strip():
                    fence = None
                continue
            if marker:
                fence = (marker[1][0], len(marker[1]))
                continue
            heading = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
            if heading:
                title = heading[2].strip()
                headings.append((number, len(heading[1]), title.split()[0].strip("`")))
        matches = [item for item in headings if item[2] == section]
        if len(matches) != 1:
            raise ExampleValidationError("example_source_section_missing_or_ambiguous")
        start, level, _ = matches[0]
        end = next((number - 1 for number, depth, _ in headings if number > start and depth <= level), len(lines))
    if symbol:
        if not isinstance(symbol, str) or not _ID.fullmatch(symbol) or not qualified.endswith(".py"):
            raise ExampleValidationError("example_source_symbol_invalid")
        nodes = [node for node in ast.walk(ast.parse(text))
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == symbol]
        if len(nodes) != 1:
            raise ExampleValidationError("example_source_symbol_missing_or_ambiguous")
        start, end = nodes[0].lineno, nodes[0].end_lineno
    if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
        raise ExampleValidationError("example_source_lines_invalid")
    if section is not None:
        selected = "\n".join(lines[start - 1:end])
        if end - start >= MAX_SECTION_LINES or len(selected) > 8000:
            raise ExampleValidationError("example_source_section_oversized")
        if not _closed_markdown_fences(lines[start - 1:end]):
            raise ExampleValidationError("example_source_section_fence_unclosed")
        complete = True
    else:
        complete = end - start < 120
        end = min(end, start + 119)
        selected = "\n".join(lines[start - 1:end])
        while len(selected) > 8000 and end > start:
            end -= 1
            selected = "\n".join(lines[start - 1:end])
            complete = False
    if len(selected) > 8000 or not selected:
        raise ExampleValidationError("example_source_excerpt_invalid")
    return {"path": qualified, "start_line": start, "end_line": end, "text": selected,
            "sha256": hashlib.sha256(selected.encode()).hexdigest(), "file_sha256": file_digest,
            "complete": complete}


def _command_source(roots: Mapping[str, Path], framework: str, command: str) -> str | None:
    if not isinstance(command, str) or any(token in command for token in ("\n", "\r", ";", "|", "&", "`", "$", ">", "<")):
        return None
    try:
        args = shlex.split(command.replace("\\", "/"))
    except ValueError:
        return None
    if len(args) < 2 or args[0] not in {"python", "python3"} or "-c" in args:
        return None
    for item in args[1:]:
        if item.endswith(".py"):
            qualified = framework + "/" + item
            _safe_file(roots, qualified)
            return qualified
    return None


def _closure(roots: Mapping[str, Path], qualified: str | None) -> dict[str, str]:
    if not qualified:
        return {}
    framework, target = _safe_file(roots, qualified)
    folder = target.parent
    # A formal Project closes over its Cases; an independent Case closes over
    # its own scaffold. Publication identity additionally binds framework code.
    if target.name not in {"run_project.py", "run_solver.py", "run_trainer.py", "run_and_report.py"}:
        _, digest = _read(roots, qualified)
        return {qualified: digest}
    values = {}
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".py", ".md", ".rst", ".toml"}:
            continue
        name = framework + "/" + path.relative_to(roots[framework]).as_posix()
        try:
            _, digest = _read(roots, name)
        except ExampleValidationError as exc:
            if str(exc) == "example_source_path_private":
                continue
            raise
        values[name] = digest
        if len(values) > 1024:
            raise ExampleValidationError("example_source_closure_oversized")
    return values


def _validate_usage_status(record: Mapping[str, Any]) -> None:
    status = record.get("usage_status")
    if "usage_status" in record and (status != "migration_reference"
            or record.get("kind") != "documentation" or record.get("run_command")):
        raise ExampleValidationError("example_usage_status_invalid")


def _base_record(spec: dict, roots: Mapping[str, Path], publication_digest: str | None) -> dict:
    identifier = spec["id"]
    framework = spec.get("working_directory", "nsgablack")
    if not _ID.fullmatch(identifier) or framework not in roots:
        raise ExampleValidationError("example_identity_invalid")
    keys = list(dict.fromkeys(spec.get("component_keys", ())))
    if not keys or any(not isinstance(key, str) or not _ID.fullmatch(key) for key in keys):
        raise ExampleValidationError("example_components_invalid")
    command = spec.get("run_command", "")
    command_source = _command_source(roots, framework, command) if command else None
    if command and not command_source:
        raise ExampleValidationError("example_run_command_not_source_bound")
    sources = spec.get("sources", ())
    if not isinstance(sources, (list, tuple)) or len(sources) > 8:
        raise ExampleValidationError("example_sources_invalid")
    snippets = [_snippet(roots, item) for item in sources]
    files = _closure(roots, command_source)
    files.update({item["path"]: item["file_sha256"] for item in snippets})
    for package in roots:
        qualified = package + "/pyproject.toml"
        if (roots[package] / "pyproject.toml").is_file():
            _, files[qualified] = _read(roots, qualified)
    record = {"id": identifier, "title": spec.get("title", identifier), "component_keys": keys,
              "summary": spec.get("summary", ""), "kind": spec.get("kind", "case" if command else "documentation"),
              "binding": spec.get("binding", "focused"), "working_directory": framework,
              "origin": "manifest" if spec.get("binding", "focused") == "focused" else "declared",
              "run_command": command, "reference": spec.get("reference", ""),
              "parameters": spec.get("parameters", []), "snippets": snippets, "source_files": files,
              "publication_digest": publication_digest, "issues": spec.get("issues", [])}
    if "usage_status" in spec:
        record["usage_status"] = spec["usage_status"]
    _validate_usage_status(record)
    for field in _LIST_FIELDS:
        record[field] = spec.get(field, [])
    if record["kind"] == "documentation":
        from .usage_learning import documentation_fields
        declared = documentation_fields(snippets)
        aliases = {
            "inputs": ("先准备什么", "输入与前提", "输入与位置", "输入"),
            "steps": ("接入步骤",),
            "dependencies": ("依赖", "依赖与边界"),
            "expected_outputs": ("怎样判断接对", "预期输出", "预期结果", "输出与消费"),
        }
        for field, names in aliases.items():
            values = next((declared[name] for name in names if declared.get(name)), ())
            if values:
                record[field] = list(values)
    record["source_digest"] = _hash(record)
    record["verification"] = {"status": "source_checked" if snippets or command_source else "unverified"}
    return record


def _source_digest(record: Mapping[str, Any]) -> str:
    return _hash({key: value for key, value in record.items() if key not in {"source_digest", "verification"}})


def _receipt(record: dict, receipts: list[dict]) -> dict:
    for value in receipts:
        if (not isinstance(value, dict) or value.get("example_id") != record["id"]
                or value.get("status") != "executed" or value.get("source_digest") != record["source_digest"]
                or not record["publication_digest"] or value.get("publication_digest") != record["publication_digest"]
                or value.get("command") != record["run_command"] or not record["run_command"]
                or any(arg.split("=", 1)[0] in {"--check", "--build-check", "--report-only"}
                       for arg in shlex.split(record["run_command"])) or type(value.get("exit_code")) is not int
                or value["exit_code"] != 0 or not isinstance(value.get("executed_at"), str)
                or not isinstance(value.get("observed_outputs"), list) or not value["observed_outputs"]
                or any(not isinstance(item, str) or len(item) > 2000 or _CREDENTIAL.search(item) for item in value["observed_outputs"])
                or not isinstance(value.get("output_sha256"), str) or not _HEX.fullmatch(value["output_sha256"])):
            continue
        try:
            executed_at = datetime.fromisoformat(value["executed_at"].replace("Z", "+00:00"))
        except ValueError:
            continue
        if executed_at.tzinfo is None:
            continue
        return {key: value[key] for key in ("status", "source_digest", "publication_digest", "command", "exit_code",
                                           "executed_at", "observed_outputs", "output_sha256")}
    return {"status": "source_checked" if record["snippets"] or record["run_command"] else "unverified"}


def _declarations(roots: Mapping[str, Path], catalog_entries=None) -> dict[str, dict]:
    result = {}
    for framework, root in roots.items():
        folder = root / "catalog/entries"
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.toml")):
            qualified = framework + "/" + path.relative_to(root).as_posix()
            text, _ = _read(roots, qualified)
            for entry in tomllib.loads(text).get("entry", []):
                key = entry.get("key", "")
                if not isinstance(key, str) or not _ID.fullmatch(key):
                    raise ExampleValidationError("example_catalog_key_invalid")
                canonical = "mlblack." + key if framework == "mlblack" else key
                if canonical in result:
                    raise ExampleValidationError("example_catalog_key_duplicate")
                result[canonical] = {**entry, "framework": framework}
    # Dynamic/federated entries belong to their public Catalog provider. The
    # caller supplies its snapshot; this static reader never imports arbitrary
    # component factories just to discover their examples.
    supplied = set()
    for item in catalog_entries or ():
        entry = item.as_dict() if hasattr(item, "as_dict") else dict(item)
        key = entry.get("key")
        if not isinstance(key, str) or not _ID.fullmatch(key) or key in supplied:
            raise ExampleValidationError("example_catalog_key_invalid")
        supplied.add(key)
        owner = dict(entry.get("metadata") or {}).get("catalog_framework", "nsgablack")
        owner = entry.get("framework", owner)
        if owner not in roots:
            raise ExampleValidationError("example_catalog_owner_invalid")
        result[key] = {**entry, "framework": owner}
    return result


def _read_json(path: Path, error: str) -> Any:
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_INDEX_BYTES:
        raise ExampleValidationError(error)
    with path.open("rb") as handle:
        raw = handle.read(MAX_INDEX_BYTES + 1)
    if len(raw) > MAX_INDEX_BYTES:
        raise ExampleValidationError(error)
    return json.loads(raw.decode("utf-8"))


def build_example_index(source_roots: Mapping[str, Path], index_path: Path, receipts_path: Path | None = None,
                        *, publication_digest: str | None = None, catalog_entries=None) -> dict:
    if publication_digest is not None and (not isinstance(publication_digest, str) or not _HEX.fullmatch(publication_digest)):
        raise ExampleValidationError("example_publication_digest_invalid")
    roots = {name: Path(path).resolve(strict=True) for name, path in source_roots.items()}
    if not roots or any(not _ID.fullmatch(name) for name in roots):
        raise ExampleValidationError("example_source_roots_invalid")
    declarations = _declarations(roots, catalog_entries)
    entries, examples, issues = {key: [] for key in declarations}, {}, []
    receipts = []
    if receipts_path is not None:
        data = _read_json(receipts_path, "example_receipts_missing_or_oversized")
        if not isinstance(data, dict) or data.get("schema") != RECEIPTS_SCHEMA or not isinstance(data.get("receipts"), list):
            raise ExampleValidationError("example_receipts_invalid")
        receipts = data["receipts"]
    manifest_root = roots.get("nsgablack")
    folder = manifest_root / "catalog/example_manifests" if manifest_root else None
    if folder is not None and folder.is_dir():
        for path in sorted(folder.glob("*.toml")):
            text, _ = _read(roots, "nsgablack/" + path.relative_to(manifest_root).as_posix())
            for spec in tomllib.loads(text).get("example", []):
                record = _base_record({**spec, "binding": "focused"}, roots, publication_digest)
                if record["id"] in examples or any(key not in declarations for key in record["component_keys"]):
                    raise ExampleValidationError("example_manifest_identity_invalid")
                record["verification"] = _receipt(record, receipts)
                examples[record["id"]] = record
                for key in record["component_keys"]:
                    entries[key].append(record["id"])
    grouped = {}
    for key, entry in declarations.items():
        reference = str(entry.get("example_entry", "") or "").strip()
        if reference:
            grouped.setdefault((entry["framework"], reference.replace("\\", "/")), []).append(key)
    for (framework, reference), keys in grouped.items():
        identifier = "declared." + framework + "." + _hash(reference)[:16]
        spec = {"id": identifier, "title": "目录声明的示例引用", "component_keys": keys,
                "working_directory": framework, "reference": reference, "binding": "declared",
                "summary": "由组件目录声明关联；源码可读不代表已运行或已核对每个组件的实际装配。", "sources": []}
        try:
            command_source = _command_source(roots, framework, reference)
            if command_source:
                spec.update(run_command=reference, kind="project" if command_source.endswith("run_project.py") else "case")
                spec["title"] = PurePosixPath(command_source).parent.name + " · 目录声明示例"
                spec["sources"] = [{"path": command_source}]
            elif reference.lower().endswith((".md", ".rst")):
                qualified = framework + "/" + reference
                spec.update(kind="documentation", sources=[{"path": qualified}], title="示例说明文档")
            elif reference.lower().endswith(".py"):
                qualified = framework + "/" + reference
                spec.update(kind="reference", sources=[{"path": qualified}], title="组件源码入口")
            else:
                spec["kind"] = "reference"
            record = _base_record(spec, roots, publication_digest)
        except (ExampleValidationError, OSError, UnicodeError, SyntaxError) as exc:
            issues.append({"example_id": identifier, "error": str(exc) if isinstance(exc, ExampleValidationError) else type(exc).__name__})
            spec.update(run_command="", kind="reference", sources=[], issues=[issues[-1]["error"]])
            record = _base_record(spec, roots, publication_digest)
        examples[identifier] = record
        for key in keys:
            entries[key].append(identifier)
    index = {"schema": SCHEMA, "publication_digest": publication_digest, "entries": entries, "examples": examples,
             "issues": issues}
    validate_example_index(index)
    encoded = _json(index).encode()
    if len(encoded) > MAX_INDEX_BYTES:
        raise ExampleValidationError("example_index_oversized")
    index_path = Path(index_path)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_bytes(encoded)
    counts = {status: sum(e["verification"]["status"] == status for e in examples.values())
              for status in ("source_checked", "executed", "unverified")}
    return {"ok": True, "components": len(entries), "with_examples": sum(bool(ids) for ids in entries.values()),
            "examples": len(examples), "verification": counts, "issues": len(issues), "bytes": len(encoded)}


def validate_example_index(index: Any) -> dict:
    if (not isinstance(index, dict) or index.get("schema") != SCHEMA or not isinstance(index.get("entries"), dict)
            or not isinstance(index.get("examples"), dict) or len(index["entries"]) > 10000 or len(index["examples"]) > 2000):
        raise ExampleValidationError("example_index_invalid")
    publication = index.get("publication_digest")
    if publication is not None and (not isinstance(publication, str) or not _HEX.fullmatch(publication)):
        raise ExampleValidationError("example_publication_digest_invalid")
    issues = index.get("issues", [])
    if not isinstance(issues, list) or len(issues) > 2000 or any(
        not isinstance(item, dict) or set(item) != {"example_id", "error"}
        or not isinstance(item.get("example_id"), str) or item["example_id"] not in index["examples"]
        or not isinstance(item.get("error"), str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", item["error"])
        for item in issues
    ):
        raise ExampleValidationError("example_issues_invalid")
    for identifier, record in index["examples"].items():
        if not isinstance(record, dict) or record.get("id") != identifier or not _ID.fullmatch(identifier):
            raise ExampleValidationError("example_identity_invalid")
        for field in ("title", "summary", "run_command", "reference", "working_directory"):
            if not isinstance(record.get(field), str) or len(record[field]) > 8000 or _CREDENTIAL.search(record[field]):
                raise ExampleValidationError("example_text_invalid")
        for field in (*_LIST_FIELDS, "component_keys", "issues"):
            values = record.get(field)
            if not isinstance(values, list) or len(values) > 2000 or any(not isinstance(v, str) or len(v) > 4000 or _CREDENTIAL.search(v) for v in values):
                raise ExampleValidationError("example_list_invalid")
        if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", issue) for issue in record["issues"]):
            raise ExampleValidationError("example_issues_invalid")
        if record.get("binding") not in {"focused", "declared"} or record.get("kind") not in {"project", "case", "documentation", "reference"}:
            raise ExampleValidationError("example_kind_invalid")
        _validate_usage_status(record)
        if record.get("origin") != ("manifest" if record["binding"] == "focused" else "declared"):
            raise ExampleValidationError("example_origin_invalid")
        if not isinstance(record.get("parameters"), list) or len(record["parameters"]) > 100 or any(not isinstance(p, dict) or
                set(p) != {"name", "value", "meaning"} or any(not isinstance(v, str) or len(v) > 2000 or _CREDENTIAL.search(v) for v in p.values()) for p in record["parameters"]):
            raise ExampleValidationError("example_parameters_invalid")
        files, snippets = record.get("source_files"), record.get("snippets")
        if not isinstance(files, dict) or len(files) > 2048 or not isinstance(snippets, list) or len(snippets) > 8:
            raise ExampleValidationError("example_sources_invalid")
        for path, digest in files.items():
            if not isinstance(path, str):
                raise ExampleValidationError("example_source_identity_invalid")
            parts = PurePosixPath(path)
            if (parts.is_absolute() or len(parts.parts) < 2 or ".." in parts.parts or "\\" in path or ":" in path
                    or any(part.lower() in _PRIVATE or part.startswith(".")
                           or part.lower().startswith(("db.toml", "id_rsa", "id_ed25519")) for part in parts.parts)
                    or parts.suffix.lower() not in {".py", ".md", ".rst", ".toml"}
                    or not isinstance(digest, str) or not _HEX.fullmatch(digest)):
                raise ExampleValidationError("example_source_identity_invalid")
        for source in snippets:
            if not isinstance(source, dict) or source.get("path") not in files:
                raise ExampleValidationError("example_source_excerpt_invalid")
            text, start, end = source.get("text"), source.get("start_line"), source.get("end_line")
            section_excerpt = (record["binding"] == "focused" and record["kind"] == "documentation"
                               and str(source.get("path", "")).endswith(".md") and source.get("complete") is True
                               and isinstance(text, str) and re.match(r"^#{1,6}\s+", text) is not None)
            max_lines = MAX_SECTION_LINES if section_excerpt else 120
            if (not isinstance(text, str) or not text or len(text) > 8000 or _CREDENTIAL.search(text)
                    or type(start) is not int or type(end) is not int or not 1 <= start <= end or end - start >= max_lines
                    or type(source.get("complete")) is not bool
                    or len(text.split("\n")) != end - start + 1 or source.get("file_sha256") != files[source["path"]]
                    or (section_excerpt and end - start >= 120 and not _closed_markdown_fences(text.split("\n")))
                    or source.get("sha256") != hashlib.sha256(text.encode()).hexdigest()):
                raise ExampleValidationError("example_source_excerpt_invalid")
        if record.get("publication_digest") != publication or record.get("source_digest") != _source_digest(record):
            raise ExampleValidationError("example_source_digest_invalid")
        verification = record.get("verification")
        if not isinstance(verification, dict) or verification.get("status") not in {"source_checked", "executed", "unverified"}:
            raise ExampleValidationError("example_verification_invalid")
        if verification["status"] == "executed":
            if _receipt(record, [{**verification, "example_id": identifier}]) != verification:
                raise ExampleValidationError("example_receipt_invalid")
        elif verification != {"status": "source_checked" if snippets or record["run_command"] else "unverified"}:
            raise ExampleValidationError("example_verification_invalid")
    for key, identifiers in index["entries"].items():
        if (not isinstance(key, str) or not _ID.fullmatch(key) or not isinstance(identifiers, list)
                or any(not isinstance(identifier, str) for identifier in identifiers)
                or len(set(identifiers)) != len(identifiers) or any(not isinstance(identifier, str)
                    or identifier not in index["examples"] or key not in index["examples"][identifier]["component_keys"] for identifier in identifiers)):
            raise ExampleValidationError("example_component_index_invalid")
    for identifier, record in index["examples"].items():
        if any(identifier not in index["entries"].get(key, ()) for key in record["component_keys"]):
            raise ExampleValidationError("example_component_index_invalid")
    return json.loads(_json(index))


def load_example_index(path: Path) -> dict:
    return validate_example_index(_read_json(path, "example_index_missing_or_oversized"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=("build",), default="build")
    parser.add_argument("--root", action="append", required=True, help="trusted framework=repository path")
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--receipts", type=Path)
    parser.add_argument("--publication-digest")
    parser.add_argument("--catalog-json", type=Path,
                        help="Public Catalog snapshot including provider-generated entries; no component imports")
    args = parser.parse_args(argv)
    try:
        roots = dict(item.split("=", 1) for item in args.root)
        entries = _read_json(args.catalog_json, "example_catalog_snapshot_invalid") if args.catalog_json else None
        if entries is not None and not isinstance(entries, list):
            raise ExampleValidationError("example_catalog_snapshot_invalid")
        result = build_example_index(roots, args.index, args.receipts,
                                     publication_digest=args.publication_digest, catalog_entries=entries)
        print(_json(result))
        return 0
    except Exception as exc:
        print(_json({"ok": False, "error_type": type(exc).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
