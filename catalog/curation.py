"""Build bounded, static evidence packets for optional Catalog explanations.

The returned records are detached JSON values. They do not alter CatalogEntry,
its contract, or its source fingerprint. No component is imported or executed.
Paths in evidence are relative to explicit, deployment-owned source roots.
"""
from __future__ import annotations

import ast
from collections.abc import Iterable, Mapping
from functools import lru_cache
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

from blackbase.catalog import CatalogEntry


PACKET_SCHEMA = "nsgablack.catalog.curation_packet/v1"
PROMPT_VERSION = "catalog-explanation-v1"
MAX_PACKET_CHARS = 48000
MAX_SOURCE_BYTES = 2 * 1024 * 1024
MAX_EXCERPT_CHARS = 4200
MAX_TUTORIAL_CHARS = 40000
_CASE_SIGNATURE_EVIDENCE_KEYS = frozenset({
    "doc.user_guide.catalog", "doc.user_guide.run_inspector",
    "mlblack.core.diagnostic_representation",
    "mlblack.preset.baseline_forecast_search",
    "mlblack.preset.linear_autoregressive_forecast",
    "mlblack.preset.mlp_regression",
    "mlblack.preset.orthogonal_logistic_classification",
    "mlblack.preset.tabular_tabnet_classification",
    "mlblack.preset.tabular_tabnet_regression",
    "mlblack.preset.temporal_deepar_forecast",
    "mlblack.preset.temporal_tft_forecast",
    "mlblack.integration.learning_solver",
    "tool.semantic_extension",
})
_MAX_EVIDENCE_IDS = 32
NOTE_FIELDS = frozenset({"summary", "use_when", "inputs_outputs", "assembly_steps", "pitfalls",
                         "related_keys", "missing_information", "evidence_ids"})
_TUTORIAL_FIELDS = frozenset({"scenario", "preparation", "placement", "code", "language",
                              "execution_flow", "result_checks", "extensions", "evidence_ids"})
_EXTENSION_FIELDS = frozenset({"title", "purpose", "placement", "code", "language", "effect", "limits", "evidence_ids"})
_DENIED = frozenset({".git", ".venv", "venv", "env", "__pycache__", "node_modules", "data", "datasets",
                    "artifacts", "checkpoints", "results", "runs", "outputs", "private", "secrets", "attachments",
                    "tests", "test-results", "deployment", ".blackbase"})
_SENSITIVE_FIELD = re.compile(r"(?:^|_)(?:api_key|password|passwd|secret|credential|access_token|private_key)(?:$|_)", re.I)
_CREDENTIAL = re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----|\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{24,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|xox[baprs]-[A-Za-z0-9-]{20,})\b")
_SUCCESS_CLAIM = re.compile(r"已(?:验证|测试|跑通|通过验收|完成验收)|测试(?:全部)?通过|\b(?:verified|validated|tested|tests? pass(?:ed)?)\b", re.I)
_NEGATED = re.compile(r"(?:not|never|without|un|未|尚未|未经|没有|不代表|不能声称|不能宣称|不能证明|不得声称)\s*(?:been\s+)?$", re.I)
_CLAUSES = re.compile(r"[，,。；;！？!?\n]+|\.(?:\s+|$)|\b(?:but|however|nevertheless|yet)\b|但是|然而|不过|但(?=已|测试|本|该|它)", re.I)
_NEGATIVE_FRAME = re.compile(
    r"(?:不构成|不代表|不意味着|不等于|不能证明|不足以证明|无法证明|不能说明|不能视为|不能当作|不保证|"
    r"(?:不得|不能|不可|不应)(?:宣称|声称|标记为)|"
    r"\bnot\s+(?:an?\s+)?(?:evidence|proof|guarantee)|"
    r"\b(?:no|without|lacks?)\s+(?:any\s+)?(?:evidence|proof|confirmation)|"
    r"\b(?:cannot|must not|should not|do not)\s+(?:be\s+)?(?:claim|assert|declare|mark|consider|treat|assume))[^，,。；;！？!?\n]{0,100}$", re.I)
_MISSING_FRAME = re.compile(r"(?:缺少|缺乏|尚无|没有|未提供|尚未提供|未见|未发现|\bmissing|\black(?:s|ing)?)[^，,。；;！？!?\n]{0,60}$", re.I)
_EVIDENCE_WORD = re.compile(r"证据|记录|报告|依据|证明|\b(?:evidence|proof|reports?|records?)\b", re.I)
_MANUAL_NAMES = r"(?:begin_attempt|prepare_publication|commit_attempt|abort_attempt)"
_MANUAL_CONTROL = re.compile(r"(?<![A-Za-z0-9_])" + _MANUAL_NAMES + r"(?![A-Za-z0-9_])")
_MANUAL_REFERENCE = re.compile(r"(?:[A-Za-z_]\w*\.)*" + _MANUAL_NAMES + r"(?:\([^)]{0,40}\))?")
_MANUAL_CLAUSES = re.compile(r"[。；;！？!?]+|\.(?:\s+|$)|\b(?:but|however|nevertheless|yet)\b|但是|然而|不过", re.I)
_MANUAL_SEPARATORS = re.compile(r"[`'\"/、,，:：\s*+-]+|\b(?:and|or)\b|以及|和|或|及|与", re.I)
_NO_MANUAL_PREFIX = re.compile(
    r"(?<!不是)(?<!并非)(?<!没有)(?<!不再)(?<!不)"
    r"(?:(?:无需|不需|不需要|禁止|严禁|不得|不要|不可|不应|不能)\s*(?:(?:手动|手工|自行|直接|显式)\s*){0,2}"
    r"(?:调用|执行|操作|使用)?(?:\s*(?:以下|如下|这些|任何|内部|控制面|事务|方法|接口|API|函数))*|"
    r"\b(?:do not|must not|should not|never|no need to)\s+(?:(?:manually|directly)\s+)?(?:call|invoke|run|use))"
    r"\s*(?:[A-Za-z_]\w*\.)*$", re.I)
_NO_MANUAL_SUFFIX = re.compile(
    r"\s*(?:\([^)]{0,40}\))?\s*(?:方法|接口)?\s*(?:均|都)?(?:无需|不需|不需要|禁止|严禁|不得|不要|不可|不应|不能)"
    r"(?:由[^，,。；;！？!?\n]{1,15})?(?:手动|手工|自行|直接|显式)?(?:调用|执行|操作|使用)", re.I)
_POSITIVE_MANUAL_SUFFIX = re.compile(
    r"\s*(?:\([^)]{0,40}\))?\s*[`'\"]?\s*(?:方法|接口)?\s*(?:必须|需要|应该|应当|请|可以|建议)"
    r"(?:手动|手工|自行|直接|显式)?(?:调用|执行|操作|使用)", re.I)
_GENERIC_TAGS = frozenset({"core", "tool", "component", "mlblack", "nsgablack", "catalog", "runtime"})


class CurationValidationError(ValueError):
    """A source packet or explanation cannot satisfy the evidence contract."""


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: object) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _negates_verification(clause: str, match: re.Match) -> bool:
    """Recognize bounded disclaimers, without carrying negation into new clauses."""
    before, after = clause[:match.start()], clause[match.end():]
    if _NEGATED.search(before) or _NEGATIVE_FRAME.search(before):
        return True
    # "没有问题，已验证" must not be accepted as missing verification evidence.
    return bool(_MISSING_FRAME.search(before) and _EVIDENCE_WORD.search(after))


def _negates_manual_control(clause: str, match: re.Match) -> bool:
    if _POSITIVE_MANUAL_SUFFIX.match(clause[match.end():]):
        return False
    # Only method references and list punctuation can extend a prohibition.
    # Verbs such as "随后调用" remain and terminate that negative scope.
    before = _MANUAL_SEPARATORS.sub(" ", _MANUAL_REFERENCE.sub("", clause[:match.start()]))
    after = _MANUAL_SEPARATORS.sub(" ", _MANUAL_REFERENCE.sub("", clause[match.end():]))
    return bool(_NO_MANUAL_PREFIX.search(before) or _NO_MANUAL_SUFFIX.match(after))


def _detached(value: Any, *, depth: int = 0) -> Any:
    if depth > 16:
        raise CurationValidationError("Catalog source declaration is too deeply nested")
    if value is None or type(value) in (bool, int, float):
        return value
    if isinstance(value, str):
        return _CREDENTIAL.sub("[credential omitted]", value)
    if isinstance(value, Mapping):
        return {str(key): ("[private field omitted]" if _SENSITIVE_FIELD.search(str(key)) else _detached(item, depth=depth + 1))
                for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_detached(item, depth=depth + 1) for item in value]
    raise CurationValidationError("Catalog source declarations must contain JSON values")


def _linked(path: Path) -> bool:
    return path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)())


def _safe_path(root: Path, relative: str) -> Path | None:
    if not relative or "\\" in relative or ":" in relative:
        return None
    parts = PurePosixPath(relative).parts
    if PurePosixPath(relative).is_absolute() or ".." in parts or not parts:
        return None
    for part in parts:
        lower = part.lower()
        if (lower in _DENIED or lower.startswith(".") or lower.endswith((".egg-info", ".dist-info"))
                or any(token in lower for token in ("credential", "private_key", ".secret", ".local."))):
            return None
    if Path(parts[-1]).suffix.lower() not in {".py", ".md", ".rst", ".toml"}:
        return None
    if parts[-1].lower().startswith(("db.toml", "id_rsa", "id_ed25519")):
        return None
    path = root
    for part in parts:
        path = path / part
        if _linked(path):
            return None
    try:
        path.resolve().relative_to(root)
        if path.is_file() and path.stat().st_size <= MAX_SOURCE_BYTES:
            return path
    except (OSError, ValueError):
        pass
    return None


@lru_cache(maxsize=192)
def _read_cached(path: str, modified_ns: int, size: int) -> tuple[str, str]:
    data = Path(path).read_bytes()
    if len(data) > MAX_SOURCE_BYTES:
        raise CurationValidationError("Source file exceeds the curation size limit")
    text = data.decode("utf-8-sig")
    if _CREDENTIAL.search(text):
        raise CurationValidationError("Source file contains credential-shaped material")
    return text, hashlib.sha256(data).hexdigest()


def _read(path: Path) -> tuple[str, str] | None:
    try:
        stat = path.stat()
        return _read_cached(str(path), stat.st_mtime_ns, stat.st_size)
    except (OSError, UnicodeError, CurationValidationError):
        return None


@lru_cache(maxsize=128)
def _tree(text: str) -> ast.Module | None:
    try:
        return ast.parse(text)
    except (SyntaxError, ValueError):
        return None


def _module_file(module: str, roots: Mapping[str, Path]) -> tuple[str, Path] | None:
    if not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", module):
        return None
    package, _, rest = module.partition(".")
    root = roots.get(package)
    if root is None:
        return None
    suffix = rest.replace(".", "/")
    for prefix in ("", package + "/", "src/" + package + "/"):
        for relative in ((prefix + suffix + ".py") if suffix else "", prefix + (suffix + "/" if suffix else "") + "__init__.py"):
            path = _safe_path(root, relative)
            if path is not None:
                return package, path
    return None


def _find_symbol(body: list[ast.stmt], parts: list[str]) -> ast.AST | None:
    for item in body:
        if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == parts[0]:
            return _find_symbol(item.body, parts[1:]) if len(parts) > 1 else item
    return None


def _declaration(module: str, symbol: str, roots: Mapping[str, Path], seen: frozenset = frozenset()):
    marker = (module, symbol)
    if marker in seen or len(seen) >= 8:
        return None
    located = _module_file(module, roots)
    if located is None:
        return None
    name, path = located
    content = _read(path)
    if content is None:
        return None
    text, file_hash = content
    tree = _tree(text)
    if tree is None:
        return name, path, text, file_hash, None
    parts = symbol.split(".") if symbol else []
    found = _find_symbol(tree.body, parts) if parts else None
    if found is not None:
        return name, path, text, file_hash, found
    # A single explicit local alias (for example Pool = ChangeSelection) is
    # declaration evidence; computed assignments remain unresolved.
    aliases = [statement for statement in tree.body if parts
               and ((isinstance(statement, ast.Assign) and any(isinstance(target, ast.Name)
                      and target.id == parts[0] for target in statement.targets))
                    or (isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name)
                        and statement.target.id == parts[0]))]
    if len(aliases) == 1 and isinstance(aliases[0].value, ast.Name):
        result = _declaration(module, ".".join([aliases[0].value.id, *parts[1:]]), roots, seen | {marker})
        if result is not None and result[-1] is not None:
            return result
    # Follow only static from-import re-exports; never call find_spec/importlib.
    if parts:
        for statement in tree.body:
            if not isinstance(statement, ast.ImportFrom):
                continue
            for alias in statement.names:
                star = alias.name == "*"
                if not star and (alias.asname or alias.name) != parts[0]:
                    continue
                if statement.level:
                    package = module if path.name == "__init__.py" else module.rpartition(".")[0]
                    base = package.split(".")
                    if statement.level > len(base):
                        continue
                    imported = ".".join(base[:len(base) - statement.level + 1] + ([statement.module] if statement.module else []))
                else:
                    imported = statement.module or ""
                result = _declaration(imported, symbol if star else ".".join([alias.name, *parts[1:]]), roots, seen | {marker})
                if result is not None and (not star or result[-1] is not None):
                    return result
    return name, path, text, file_hash, None


def _fallback_declaration(module, symbol, roots, *, owner, seen=frozenset()):
    """Recover explicit source declarations only after the legacy lookup failed.

    Keeping this separate leaves successful packets and their related-source
    traversal byte-for-byte unchanged. No imports or constructors are executed.
    """
    marker = (module, symbol)
    if marker in seen or len(seen) >= 8:
        return None, []
    previous = _declaration(module, symbol, roots)
    if previous is not None and previous[-1] is not None:
        return previous, []
    if previous is None:
        # Examples live inside their explicitly declared framework repository,
        # rather than being an independently trusted Python package root.
        if owner not in roots or not re.fullmatch(r"examples(?:\.[A-Za-z_]\w*)+", module):
            return None, []
        relative = module.replace(".", "/")
        path = next((path for suffix in (".py", "/__init__.py")
                     if (path := _safe_path(roots[owner], relative + suffix)) is not None), None)
        content = _read(path) if path is not None else None
        if content is None:
            return None, []
        name, (text, file_hash) = owner, content
    else:
        name, path, text, file_hash, _ = previous
    tree = _tree(text)
    parts = symbol.split(".")
    if tree is None or not parts or not all(part.isidentifier() for part in parts):
        return None, []
    found = _find_symbol(tree.body, parts)
    if found is not None:
        return (name, path, text, file_hash, found), []
    implementation = _source_module(name, path, roots[name])
    assignments = [node for node in tree.body if isinstance(node, (ast.Assign, ast.AnnAssign))
                   and any(isinstance(target, ast.Name) and target.id == parts[0]
                           for target in (node.targets if isinstance(node, ast.Assign) else [node.target]))]
    if len(assignments) == 1 and len(parts) == 1:
        value = assignments[0].value
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and not value.args and not value.keywords:
            cls = _find_symbol(tree.body, [value.func.id])
            if isinstance(cls, ast.ClassDef):
                proof = (name, path, text, file_hash, assignments[0].lineno, assignments[0].end_lineno)
                return (name, path, text, file_hash, cls), [proof]
    imports = []
    for statement in tree.body:
        if isinstance(statement, ast.ImportFrom):
            imports.append((statement, statement))
        elif isinstance(statement, ast.Try):
            branches = [statement.body, statement.orelse, statement.finalbody,
                        *[handler.body for handler in statement.handlers]]
            imports.extend((child, statement) for branch in branches for child in branch
                           if isinstance(child, ast.ImportFrom))
    targets, namespace = {}, []
    for statement, proof in imports:
        if statement.level:
            package = implementation if path.name == "__init__.py" else implementation.rpartition(".")[0]
            base = package.split(".")
            if statement.level > len(base):
                continue
            imported = ".".join(base[:len(base) - statement.level + 1] + ([statement.module] if statement.module else []))
        else:
            imported = statement.module or ""
        if len(parts) == 1 and imported == implementation + "." + symbol:
            namespace.append(proof)
        for alias in statement.names:
            if (alias.asname or alias.name) == parts[0] and alias.name != "*":
                targets.setdefault((imported, ".".join([alias.name, *parts[1:]])), []).append(proof)
    if len(targets) == 1:
        (target_module, target_symbol), proofs = next(iter(targets.items()))
        result, nested = _fallback_declaration(target_module, target_symbol, roots,
                                              owner=name, seen=seen | {marker})
        if result is not None:
            return result, [(name, path, text, file_hash, proof.lineno, proof.end_lineno)
                            for proof in proofs] + nested
    if not targets and namespace and len(parts) == 1:
        child = _module_file(implementation + "." + symbol, roots)
        content = _read(child[1]) if child is not None else None
        if content is not None and (node := _tree(content[0])) is not None:
            return (*child, *content, node), [(name, path, text, file_hash,
                                             proof.lineno, proof.end_lineno) for proof in namespace]
    return None, []


def _excerpt(text: str, start: int, end: int, max_chars: int) -> tuple[int, int, str] | None:
    lines = text.splitlines(keepends=True)
    if not lines:
        return None
    start, end = max(1, start), min(len(lines), end)
    selected, size = [], 0
    for line in lines[start - 1:end]:
        if size + len(line) > max_chars:
            break
        selected.append(line)
        size += len(line)
    if not selected:
        return None
    return start, start + len(selected) - 1, "".join(selected)


def _bounded_entry(entry: CatalogEntry) -> tuple[dict, str]:
    record = _detached(entry.as_dict())
    full_digest = _digest(record)
    # Large model layouts remain source facts, but do not exhaust a model request.
    if len(_json(record)) > 6500:
        for field in ("metadata", "contract", "minimal_wiring", "context_notes"):
            if len(_json(record.get(field))) > 1800:
                record[field] = {} if field in {"metadata", "contract"} else []
                record.setdefault("curation_omitted_fields", []).append(field)
    if len(_json(record)) > 7500:
        raise CurationValidationError("Catalog entry exceeds the bounded evidence packet")
    return record, full_digest


def _source_module(package: str, path: Path, root: Path) -> str:
    parts = list(path.relative_to(root).with_suffix("").parts)
    if parts[:2] == ["src", package]:
        parts = parts[2:]
    elif parts[:1] == [package]:
        parts = parts[1:]
    if parts[-1:] == ["__init__"]:
        parts.pop()
    return ".".join([package, *parts])


def _usage_imports(path: str, text: str) -> list[tuple[str, str]]:
    """Return explicit imported names actually referenced by displayed Python."""
    if path.endswith(".py"):
        blocks = [text]
    else:
        blocks, current, fence = [], [], ""
        for line in text.splitlines():
            stripped = line.strip()
            if fence:
                if stripped == fence:
                    blocks.append("\n".join(current))
                    current, fence = [], ""
                else:
                    current.append(line)
            elif re.fullmatch(r"(`{3,}|~{3,})(?:python|py)\s*", stripped, re.I):
                fence = re.match(r"[`~]+", stripped).group()
    imported = []
    for block in blocks:
        tree = _tree(block)
        if tree is None:
            continue
        used = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}
        rebound = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)}
        rebound.update(node.arg for node in ast.walk(tree) if isinstance(node, ast.arg))
        rebound.update(node.name for node in ast.walk(tree)
                       if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)))
        bindings = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and not node.level and node.module:
                for alias in node.names:
                    if alias.name != "*":
                        bindings.setdefault(alias.asname or alias.name, set()).add((node.module, alias.name))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    local = alias.asname or alias.name.split(".")[0]
                    bindings.setdefault(local, set()).add((alias.name if alias.asname else local, ""))
        for local, targets in bindings.items():
            if local in rebound or local not in used or len(targets) != 1:
                continue
            module, symbol = next(iter(targets))
            if symbol:
                imported.append((module, symbol))
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Attribute) or not isinstance(node.ctx, ast.Load):
                    continue
                parts, base = [], node
                while isinstance(base, ast.Attribute):
                    parts.insert(0, base.attr)
                    base = base.value
                if isinstance(base, ast.Name) and base.id == local and parts:
                    imported.append((".".join([module, *parts[:-1]]), parts[-1]))
    return list(dict.fromkeys(imported))


def _usage_classes(sources, entries, roots, primary):
    """Match used imports to actual Catalog declarations, never common tags."""
    candidates = {}
    for entry in entries:
        module, separator, symbol = entry.import_path.partition(":")
        if separator and symbol:
            candidates.setdefault(symbol.rsplit(".", 1)[-1], []).append(entry)
    selected = {}
    for path, text in sources:
        for module, symbol in _usage_imports(path, text):
            declaration = _declaration(module, symbol, roots)
            if declaration is None or not isinstance(declaration[-1], ast.ClassDef):
                continue
            owner, source, _, _, node = declaration
            identity = (owner, source, node.lineno)
            if identity == primary or identity in selected:
                continue
            possible = {entry.key: entry for name in {symbol, node.name}
                        for entry in candidates.get(name, ())}
            matches = []
            for entry in possible.values():
                target_module, _, target_symbol = entry.import_path.partition(":")
                target = _declaration(target_module, target_symbol, roots)
                if target is not None and isinstance(target[-1], ast.ClassDef) and (
                        target[0], target[1], target[-1].lineno) == identity:
                    matches.append(entry)
            if matches:
                rank = min({"adapter": 0, "problem": 1, "solver": 2, "trainer": 2}.get(entry.kind, 3)
                           for entry in matches)
                selected[identity] = (rank, declaration)
    return [value[1] for value in sorted(selected.values(), key=lambda value: value[0])[:3]]


def _signature_type_names(method) -> list[str]:
    arguments = [*method.args.posonlyargs, *method.args.args, *method.args.kwonlyargs]
    arguments.extend(item for item in (method.args.vararg, method.args.kwarg) if item is not None)
    annotations = [argument.annotation for argument in arguments if argument.annotation is not None]
    if method.returns is not None:
        annotations.append(method.returns)
    names = []
    for annotation in annotations:
        if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
            annotation = _tree(annotation.value)
        if annotation is None or any(isinstance(node, ast.Call) for node in ast.walk(annotation)):
            continue
        for node in ast.walk(annotation):
            if isinstance(node, ast.Name) and node.id.endswith(("Context", "Request", "Batch", "Result", "View", "Spec")):
                names.append(node.id)
    return list(dict.fromkeys(names))


def _related(entry: CatalogEntry, entries: Iterable[CatalogEntry]) -> list[CatalogEntry]:
    values = {item.key: item for item in entries if isinstance(item, CatalogEntry)}
    explicit = list(dict.fromkeys((*entry.required_companions, *entry.companions)))
    tags = set(entry.tags) - _GENERIC_TAGS
    candidates = []
    for item in values.values():
        if item.key == entry.key or item.key in explicit:
            continue
        score = 8 * (item.import_path == entry.import_path) + len(tags.intersection(item.tags))
        if score:
            candidates.append((-score, item.key))
    ordered = explicit + [key for _, key in sorted(candidates)]
    return [values[key] for key in ordered if key in values and key != entry.key][:12]


@lru_cache(maxsize=12)
def _catalog_blocks(root_name: str, root_string: str, signature: tuple) -> dict[str, tuple]:
    blocks = {}
    for relative, _, _ in signature:
        path = _safe_path(Path(root_string), relative)
        if path is None:
            continue
        content = _read(path)
        if content is None:
            continue
        text, file_hash = content
        lines = text.splitlines(keepends=True)
        starts = [index for index, line in enumerate(lines) if re.fullmatch(r"\s*\[\[entry\]\]\s*", line)]
        for start, end in zip(starts, starts[1:] + [len(lines)]):
            for line in lines[start:end]:
                match = re.fullmatch(r"\s*key\s*=\s*([\"'])([^\"']+)\1\s*", line)
                if match:
                    blocks[match.group(2)] = (path, text, file_hash, start + 1, end)
                    break
    return blocks


def _catalog_block(root_name: str, root: Path, key: str):
    signature = []
    for directory in ("catalog/entries", root_name + "/catalog/entries", "src/" + root_name + "/catalog/entries"):
        folder = root / directory
        current = root
        safe = True
        for part in PurePosixPath(directory).parts:
            current = current / part
            if part.lower() in _DENIED or _linked(current):
                safe = False
                break
        if not safe or not folder.is_dir():
            continue
        for item in sorted(folder.glob("*.toml")):
            relative = item.relative_to(root).as_posix()
            if _safe_path(root, relative) is not None:
                stat = item.stat()
                signature.append((relative, stat.st_mtime_ns, stat.st_size))
    return _catalog_blocks(root_name, str(root), tuple(signature)).get(key)


def prepare_packet(entry: CatalogEntry, catalog_entries: Iterable[CatalogEntry], source_roots: Mapping[str, Path],
                   *, usage_examples: Iterable[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Capture source declarations and exact excerpts without running components.

    Roots map package names to trusted repository roots (including src layouts).
    A source digest covers complete selected source files as well as excerpts,
    so editing a class below an excerpt still invalidates the derived note.
    """
    if not isinstance(entry, CatalogEntry):
        raise TypeError("entry must be a shared CatalogEntry")
    roots = {}
    for name, value in source_roots.items():
        root = Path(value)
        if not re.fullmatch(r"[A-Za-z_]\w*", name) or name.lower() in _DENIED or _linked(root):
            raise CurationValidationError("Invalid curation source root")
        if not root.is_dir():
            raise CurationValidationError("Curation source root is missing")
        roots[name] = root.resolve()
    entries = tuple(item for item in catalog_entries if isinstance(item, CatalogEntry))
    record, entry_digest = _bounded_entry(entry)
    related = _related(entry, entries)
    related_records = [{"key": item.key, "title": item.title, "kind": item.kind, "summary": item.summary[:240],
                        "import_path": item.import_path, "source_digest": _digest(_detached(item.as_dict()))} for item in related]
    from .tutorial_review import REVIEW_VERSION
    packet = {"schema": PACKET_SCHEMA, "prompt_version": PROMPT_VERSION, "review_protocol": REVIEW_VERSION, "entry_key": entry.key,
              "entry_digest": entry_digest, "entry": record, "related_entries": related_records,
              "known_entry_keys": [entry.key, *[item.key for item in related]], "evidence": [],
              "gaps": [], "verification": "explanation-only; no behavioral execution evidence"}

    def add(name: str, path: Path, text: str, file_hash: str, start: int, end: int, *, max_chars=MAX_EXCERPT_CHARS):
        excerpt = _excerpt(text, start, end, max_chars)
        if excerpt is None:
            return
        start, end, selected = excerpt
        display = name + "/" + path.relative_to(roots[name]).as_posix()
        if any(item["path"] == display and item["start_line"] == start and item["end_line"] == end for item in packet["evidence"]):
            return True
        evidence = {"id": "e" + str(len(packet["evidence"]) + 1), "path": display,
                    "start_line": start, "end_line": end, "text": selected,
                    "sha256": hashlib.sha256(selected.encode("utf-8")).hexdigest(), "file_sha256": file_hash}
        packet["evidence"].append(evidence)
        if len(_json(packet)) > MAX_PACKET_CHARS - 100:
            packet["evidence"].pop()
            return False
        return True

    class_contexts, usage_sources = [], []
    primary = None
    module, _, symbol = entry.import_path.partition(":")
    owner = str(entry.metadata.get("catalog_framework") or module.split(".")[0])
    if owner not in roots:
        owner = module.split(".")[0] if module.split(".")[0] in roots else ""
    original_key = str(entry.metadata.get("catalog_original_key") or entry.key)
    if owner in roots:
        block = _catalog_block(owner, roots[owner], original_key)
        if block:
            add(owner, *block[:3], block[3], block[4], max_chars=2400)
    # Preserve the first explicit Case wiring before implementation methods can
    # exhaust the packet. These are source facts, never runtime certificates.
    first_usage_source = True
    for example in list(usage_examples or ())[:2]:
        if example.get("origin") != "manifest":
            continue
        evidence_ids = []
        for snippet in list(example.get("snippets", ()))[:2]:
            display = str(snippet.get("path", ""))
            name, separator, relative = display.partition("/")
            if not separator or name not in roots:
                continue
            path = _safe_path(roots[name], relative)
            content = _read(path) if path is not None else None
            if content is None or content[1] != snippet.get("file_sha256"):
                continue
            start, end = snippet.get("start_line"), snippet.get("end_line")
            if type(start) is not int or type(end) is not int or not 0 < start <= end:
                continue
            if add(name, path, content[0], content[1], start, end, max_chars=12000 if first_usage_source else 6000):
                first_usage_source = False
            shown = [item for item in packet["evidence"]
                     if item["path"] == display and start <= item["start_line"] <= end]
            evidence_ids.extend(item["id"] for item in shown)
            usage_sources.extend((item["path"], item["text"]) for item in shown)
        if evidence_ids:
            guide = {"title": str(example.get("title", ""))[:160],
                     "run_command": str(example.get("run_command", ""))[:500],
                     "inputs": [str(value)[:400] for value in example.get("inputs", ())][:3],
                     "expected_outputs": [str(value)[:400] for value in example.get("expected_outputs", ())][:3],
                     "evidence_ids": list(dict.fromkeys(evidence_ids))}
            guides = packet.setdefault("usage_examples", [])
            guides.append(guide)
            if len(_json(packet)) > MAX_PACKET_CHARS - 100:
                guides.pop()
            if not guides:
                packet.pop("usage_examples", None)
    located = _declaration(module, symbol, roots)
    resolution_proofs = []
    if (located is None or located[-1] is None) and entry.kind not in {"doc"}:
        recovered, resolution_proofs = _fallback_declaration(module, symbol, roots, owner=owner)
        if recovered is not None:
            located = recovered
    if located:
        name, path, text, file_hash, node = located
        if node is None:
            add(name, path, text, file_hash, 1, 100)
            packet["gaps"].append("符号未能静态定位；模块摘录不证明该符号的运行语义。")
        elif isinstance(node, ast.Module):
            add(name, path, text, file_hash, 1, 110)
        else:
            start = min([node.lineno, *[item.lineno for item in getattr(node, "decorator_list", [])]])
            add(name, path, text, file_hash, start, min(node.end_lineno, start + 45), max_chars=2800)
            if isinstance(node, ast.ClassDef):
                primary = (name, path, node.lineno)
                implementation_module = _source_module(name, path, roots[name])
                config_names = sorted({item.id for item in ast.walk(node)
                                       if isinstance(item, ast.Name) and item.id.endswith("Config")})[:3]
                for config_name in config_names:
                    configuration = _declaration(implementation_module, config_name, roots)
                    if configuration is None or not isinstance(configuration[-1], ast.ClassDef):
                        continue
                    config_owner, config_path, config_text, config_hash, config = configuration
                    config_start = min([config.lineno, *[decorator.lineno for decorator in config.decorator_list]])
                    add(config_owner, config_path, config_text, config_hash, config_start, config.end_lineno, max_chars=4200)
                methods = {item.name: item for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))}
                semantic_methods = {
                    "plugin": ("prepare_restore", "on_solver_init", "on_generation_committed", "on_generation_end", "on_solver_finish", "on_solver_finalization_prepare", "on_solver_finalized", "get_report", "get_runtime_context_projection"),
                    "capability": ("on_solver_init", "evaluate_individual", "evaluate_population", "on_solver_finish", "get_runtime_context_projection"),
                    "bias": ("compute_bias", "__call__", "apply", "compute", "score"),
                    "head": ("__call__", "forward", "predict", "predict_proba", "transform", "apply", "loss"),
                    "provider": ("evaluate", "evaluate_individual", "evaluate_population", "create_provider", "close"),
                }.get(entry.kind, ())
                priority = tuple(dict.fromkeys(("__init__", *semantic_methods,
                            "get_population_snapshot", "get_population_solution_refs", "read", "read_raw_feedback",
                            "chosen", "inject", "propose", "update", "selector", "select", "choose", "mutate", "repair",
                            "change", "maintain", "get_population", "get_pool_task_results", "get_pool_refinement_results",
                            "feature", "build", "initialize", "init", "encode", "decode", "apply", "__call__",
                            "apply_selection", "set_selector", "set_mutator")))
                initial_size = len(_json(packet))
                selected_methods = []
                for method_name in priority:
                    remaining = 18000 - (len(_json(packet)) - initial_size)
                    if remaining < 700:
                        break
                    method = methods.get(method_name)
                    if method is not None:
                        method_start = min([method.lineno, *[decorator.lineno for decorator in method.decorator_list]])
                        if add(name, path, text, file_hash, method_start, min(method.end_lineno, method.lineno + 180),
                               max_chars=min(5200, remaining - 400)):
                            selected_methods.append(method)
                class_contexts.append((name, path, text, file_hash, methods, selected_methods))
                # Capture only direct, explicitly named bases. Resolving their
                # declarations may follow imports, but never follows another
                # inheritance level or imports a running component.
                bases = list(dict.fromkeys(base.id for base in node.bases
                                           if isinstance(base, ast.Name) and base.id not in {"object", "Protocol"}))[:2]
                parent_priority = ("__init__", "propose", "update", *[name for name in priority
                                    if name not in {"__init__", "propose", "update"}])
                parent_start_size = len(_json(packet))
                for base_name in bases:
                    parent = _declaration(implementation_module, base_name, roots)
                    if parent is None or not isinstance(parent[-1], ast.ClassDef):
                        packet["gaps"].append(f"显式父类 {base_name} 未能静态定位；不得推断其参数或运行流程。")
                        continue
                    parent_owner, parent_path, parent_text, parent_hash, parent_node = parent
                    parent_start = min([parent_node.lineno, *[decorator.lineno for decorator in parent_node.decorator_list]])
                    add(parent_owner, parent_path, parent_text, parent_hash, parent_start,
                        min(parent_node.end_lineno, parent_start + 30), max_chars=1800)
                    parent_methods = {item.name: item for item in parent_node.body
                                      if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))}
                    selected_parent_methods = []
                    for method_name in parent_priority:
                        remaining = 12000 - (len(_json(packet)) - parent_start_size)
                        if remaining < 700:
                            break
                        method = parent_methods.get(method_name)
                        if method is not None:
                            method_start = min([method.lineno, *[decorator.lineno for decorator in method.decorator_list]])
                            if add(parent_owner, parent_path, parent_text, parent_hash, method_start,
                                   min(method.end_lineno, method.lineno + 120), max_chars=min(3200, remaining - 400)):
                                selected_parent_methods.append(method)
                    class_contexts.append((parent_owner, parent_path, parent_text, parent_hash,
                                           parent_methods, selected_parent_methods))
                if bases:
                    packet["gaps"].append("父类实现证据只展开一层；未据此确认更上层或动态基类的完整语义。")
    else:
        packet["gaps"].append("未定位到该导入声明的受支持静态源码；不得猜测实现。")
    for proof_owner, proof_path, proof_text, proof_hash, start, end in resolution_proofs:
        add(proof_owner, proof_path, proof_text, proof_hash, start, end, max_chars=2400)
    # Case wiring is stronger evidence of a useful combination than common tags.
    # Follow only displayed, hash-checked code imports to known Catalog classes.
    usage_start_size = len(_json(packet))
    for name, path, text, file_hash, node in _usage_classes(usage_sources, entries, roots, primary):
        remaining = 12000 - (len(_json(packet)) - usage_start_size)
        if remaining < 700:
            break
        start = min([node.lineno, *[decorator.lineno for decorator in node.decorator_list]])
        add(name, path, text, file_hash, start, min(node.end_lineno, start + 65), max_chars=min(3000, remaining - 400))
        methods = {item.name: item for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for method_name in ("__init__", "feature", "validate_for", "validate_member_contract",
                            "on_members_changed", "validate_feature_inputs"):
            remaining = 12000 - (len(_json(packet)) - usage_start_size)
            if remaining < 700:
                break
            method = methods.get(method_name)
            if method is not None:
                start = min([method.lineno, *[decorator.lineno for decorator in method.decorator_list]])
                add(name, path, text, file_hash, start, min(method.end_lineno, start + 120),
                    max_chars=min(2400, remaining - 400))
    # Signature input/feedback types supply real fields; no traversal of their
    # field annotations, methods, inheritance, or runtime type expressions.
    type_start_size, signature_types = len(_json(packet)), set()
    for name, path, _text, _file_hash, _methods, selected_methods in class_contexts:
        implementation_module = _source_module(name, path, roots[name])
        for method in selected_methods:
            for type_name in _signature_type_names(method):
                if len(signature_types) >= 3:
                    break
                declaration = _declaration(implementation_module, type_name, roots)
                if declaration is None or not isinstance(declaration[-1], ast.ClassDef):
                    continue
                type_owner, type_path, type_text, type_hash, type_node = declaration
                identity = (type_owner, type_path, type_node.lineno)
                if identity == primary or identity in signature_types:
                    continue
                remaining = 6000 - (len(_json(packet)) - type_start_size)
                if remaining < 700:
                    break
                start = min([type_node.lineno, *[decorator.lineno for decorator in type_node.decorator_list]])
                if add(type_owner, type_path, type_text, type_hash, start, min(type_node.end_lineno, start + 100),
                       max_chars=min(3000, remaining - 400)):
                    signature_types.add(identity)
    # Only one direct self.method() hop from already selected methods; helper
    # bodies never become new traversal roots. Prefer actual guard/restore facts.
    helper_candidates = {}
    for name, path, text, file_hash, methods, selected_methods in class_contexts:
        selected_names = {method.name for method in selected_methods}
        for method in selected_methods:
            for call in ast.walk(method):
                if (not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute)
                        or not isinstance(call.func.value, ast.Name) or call.func.value.id != "self"):
                    continue
                helper = methods.get(call.func.attr)
                if helper is not None and helper.name not in selected_names:
                    guard = helper.name.lstrip("_").startswith(("validate", "assert", "check", "restore", "resume", "save", "report"))
                    helper_candidates[(path, helper.lineno)] = (not guard, name, path, text, file_hash, helper)
    helper_start_size = len(_json(packet))
    for _, name, path, text, file_hash, helper in sorted(helper_candidates.values(), key=lambda value: value[0])[:6]:
        remaining = 8000 - (len(_json(packet)) - helper_start_size)
        if remaining < 700:
            break
        start = min([helper.lineno, *[decorator.lineno for decorator in helper.decorator_list]])
        add(name, path, text, file_hash, start, min(helper.end_lineno, start + 120), max_chars=min(2400, remaining - 400))
    # Formal example/detail references are read only under the entry's owner.
    for reference in (entry.example_entry, entry.detail_ref):
        if not reference or owner not in roots:
            continue
        relative = reference.split("#", 1)[0]
        if relative.startswith(owner + "/"):
            relative = relative[len(owner) + 1:]
        path = _safe_path(roots[owner], relative)
        if path is not None:
            content = _read(path)
            if content:
                add(owner, path, content[0], content[1], 1, 110, max_chars=3400)

    # Targeted repairs for explicitly reviewed failures, never a global graph
    # expansion. Existing successful primary packets take their original path.
    if entry.key == "mlblack.head.softmax":
        classification = _declaration("mlblack.problems.classification", "SupervisedClassificationProblem", roots)
        if classification is not None and isinstance(classification[-1], ast.ClassDef):
            source_owner, source_path, source_text, source_hash, cls = classification
            evaluate = next((node for node in cls.body if isinstance(node, ast.FunctionDef)
                             and node.name == "evaluate"), None)
            if evaluate is not None:
                add(source_owner, source_path, source_text, source_hash,
                    evaluate.lineno, evaluate.end_lineno, max_chars=5000)
                called = {node.func.id for node in ast.walk(evaluate)
                          if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
                for helper_name in ("_classification_metrics", "_build_objectives"):
                    helper = _declaration("mlblack.problems.classification", helper_name, roots)
                    if helper_name in called and helper is not None and isinstance(helper[-1], ast.FunctionDef):
                        add(*helper[:4], helper[-1].lineno, helper[-1].end_lineno, max_chars=5000)
        if located is not None and isinstance(located[-1], ast.ClassDef):
            decode = next((node for node in located[-1].body if isinstance(node, ast.FunctionDef)
                           and node.name == "decode"), None)
            if decode is not None and any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                                         and node.func.id == "SoftmaxProbabilityModel" for node in ast.walk(decode)):
                model = _declaration(module, "SoftmaxProbabilityModel", roots)
                if model is not None and isinstance(model[-1], ast.ClassDef):
                    start = min([model[-1].lineno, *[node.lineno for node in model[-1].decorator_list]])
                    add(*model[:4], start, model[-1].end_lineno, max_chars=5000)
    if entry.key == "mlblack.preset.temporal_patchtst_forecast" and "mlblack" in roots:
        for relative in ("examples/cases/temporal_neural_compare/cases/temporal_patchtst/build_solver.py",
                         "examples/cases/temporal_neural_compare/cases/temporal_patchtst/pipeline/__init__.py",
                         "examples/cases/temporal_neural_compare/cases/temporal_patchtst/pipeline/main.py",
                         "examples/cases/temporal_neural_compare/project_config.py"):
            source_path = _safe_path(roots["mlblack"], relative)
            content = _read(source_path) if source_path is not None else None
            if content is not None:
                add("mlblack", source_path, *content, 1, len(content[0].splitlines()), max_chars=5000)
    if entry.key in _CASE_SIGNATURE_EVIDENCE_KEYS:
        case_builder = _declaration("blackbase.project.runtime", "build_case", roots)
        if case_builder is not None and isinstance(case_builder[-1], ast.FunctionDef):
            # The signature check, rejection and actual injected call are one
            # source fact; adding it does not certify a tutorial's own builder.
            add(*case_builder[:4], case_builder[-1].lineno, case_builder[-1].end_lineno, max_chars=5000)
    if entry.key == "mlblack.schema.scaffold_config":
        for source_module, source_symbol in (
                ("mlblack.pipeline.numericizer.default", "DefaultNumericizer"),
                ("mlblack.pipeline.numericizer.plan", "NumericizationPlan")):
            declaration = _declaration(source_module, source_symbol, roots)
            if declaration is not None and isinstance(declaration[-1], ast.ClassDef):
                node = declaration[-1]
                start = min([node.lineno, *[decorator.lineno for decorator in node.decorator_list]])
                add(*declaration[:4], start, node.end_lineno, max_chars=5000)
    if entry.key in {"mlblack.problem.training_proxy", "mlblack.problem_bridge.ml_black_training"}:
        proxy = _declaration("mlblack.problems.proxy", "MLBlackTrainingProxy", roots)
        if proxy is not None and isinstance(proxy[-1], ast.ClassDef):
            for method in proxy[-1].body:
                if isinstance(method, ast.FunctionDef) and method.name in {
                        "make_task", "run_task", "evaluate_individual", "evaluate_population"}:
                    add(*proxy[:4], method.lineno, method.end_lineno, max_chars=4000)
    if entry.key == "mlblack.integration.learning_solver":
        helper = _declaration("mlblack.integrations.nsgablack_control", "build_learning_solver", roots)
        if helper is not None and isinstance(helper[-1], ast.FunctionDef):
            add(*helper[:4], helper[-1].lineno, helper[-1].end_lineno, max_chars=1800)
        builder = _declaration("mlblack.examples.cases.catalog_codec_demo.cases.linear_point.build_solver",
                               "build_solver", roots)
        if builder is not None and isinstance(builder[-1], ast.FunctionDef):
            add(*builder[:4], 1, builder[-1].lineno - 1, max_chars=1800)
            add(*builder[:4], builder[-1].lineno, builder[-1].end_lineno, max_chars=2500)
        if "mlblack" in roots:
            for relative in ("examples/cases/catalog_codec_demo/project_config.py",
                             "examples/cases/catalog_codec_demo/cases/linear_point/config.py",
                             "examples/cases/catalog_codec_demo/cases/linear_point/pipeline/__init__.py",
                             "examples/cases/catalog_codec_demo/cases/linear_point/pipeline/main.py"):
                source_path = _safe_path(roots["mlblack"], relative)
                content = _read(source_path) if source_path is not None else None
                if content is not None:
                    add("mlblack", source_path, *content, 1, len(content[0].splitlines()), max_chars=2000)
    if entry.key == "mlblack.head.interval":
        problem = _declaration("mlblack.problems.supervised", "SupervisedIntervalRegressionProblem", roots)
        if problem is not None and isinstance(problem[-1], ast.ClassDef):
            for method in problem[-1].body:
                if isinstance(method, ast.FunctionDef) and method.name == "evaluate":
                    add(*problem[:4], method.lineno, method.end_lineno, max_chars=5000)
        violation = _declaration("nsgablack.core.evaluation_feedback", "feedback_constraint_violation", roots)
        if violation is not None and isinstance(violation[-1], ast.FunctionDef):
            add(*violation[:4], violation[-1].lineno, violation[-1].end_lineno, max_chars=2000)
    if entry.key == "tool.semantic_extension":
        declaration = _declaration("nsgablack.core.semantic_extension", "SolverSemanticExtension", roots)
        if declaration is not None and isinstance(declaration[-1], ast.ClassDef):
            add(*declaration[:4], declaration[-1].lineno, declaration[-1].end_lineno, max_chars=5000)
        constructor = _declaration("nsgablack.core.composable_solver", "ComposableSolver.__init__", roots)
        if constructor is not None and isinstance(constructor[-1], ast.FunctionDef):
            # Preserve the complete actual signature, not a guessed **kwargs
            # path or an invented semantic_extensions constructor parameter.
            end = constructor[-1].body[0].lineno - 1
            add(*constructor[:4], constructor[-1].lineno, end, max_chars=5000)
        register = _declaration("nsgablack.core.blank_solver", "SolverBase.register_semantic_extension", roots)
        if register is not None and isinstance(register[-1], ast.FunctionDef):
            add(*register[:4], register[-1].lineno, register[-1].end_lineno, max_chars=2000)
    if entry.key == "tool.objective_projection":
        for source_module, symbol in (
                ("nsgablack.core.state.pool_views", "ObjectiveProjection.apply"),
                ("nsgablack.core.evaluation_acceptance", "FeasibleEvaluationAcceptance.select"),
                ("nsgablack.utils.performance.fast_non_dominated_sort", "FastNonDominatedSort.sort")):
            declaration = _declaration(source_module, symbol, roots)
            if declaration is not None and isinstance(declaration[-1], ast.FunctionDef):
                node = declaration[-1]
                start = min([node.lineno, *[decorator.lineno for decorator in node.decorator_list]])
                add(*declaration[:4], start, node.end_lineno, max_chars=5000)
    if entry.key == "mlblack.core.model":
        representation = _declaration("mlblack.core.representation", "ModelRepresentation", roots)
        if representation is not None and isinstance(representation[-1], ast.ClassDef):
            add(*representation[:4], representation[-1].lineno, representation[-1].end_lineno, max_chars=5000)
        state = _declaration("blackbase.types", "UnknownState", roots)
        if state is not None and isinstance(state[-1], ast.ClassDef):
            node = state[-1]
            start = min([node.lineno, *[decorator.lineno for decorator in node.decorator_list]])
            add(*state[:4], start, min(node.end_lineno, node.lineno + 26), max_chars=2400)
            for method in node.body:
                if isinstance(method, ast.FunctionDef) and method.name in {"as_array", "with_values"}:
                    add(*state[:4], method.lineno, method.end_lineno, max_chars=2000)
        initialize = _declaration("mlblack.integrations.nsgablack_control", "_initialize_representation", roots)
        if initialize is not None and isinstance(initialize[-1], ast.FunctionDef):
            add(*initialize[:4], initialize[-1].lineno, initialize[-1].end_lineno, max_chars=2400)
    if entry.key == "mlblack.model.orthogonal_linear_point":
        for method_name in ("fit", "output_dim", "transform"):
            declaration = _declaration("mlblack.models.linear", "OrthogonalFeatureMap." + method_name, roots)
            if declaration is not None and isinstance(declaration[-1], ast.FunctionDef):
                node = declaration[-1]
                start = min([node.lineno, *[decorator.lineno for decorator in node.decorator_list]])
                add(*declaration[:4], start, node.end_lineno, max_chars=5000)
    if not packet["evidence"]:
        packet["gaps"].append("没有可引用源码片段，暂不生成可发布的整理说明。")
    packet["source_digest"] = _digest(packet)
    if len(_json(packet)) > MAX_PACKET_CHARS:
        raise CurationValidationError("Curation packet exceeds the character limit")
    return packet


def _safety_texts(texts: Iterable[str], *, manual_control: bool = False) -> None:
    for value in texts:
        if _CREDENTIAL.search(value):
            raise CurationValidationError("Curation note contains credential-shaped material")
        for clause in _CLAUSES.split(value):
            for match in _SUCCESS_CLAIM.finditer(clause):
                if not _negates_verification(clause, match):
                    raise CurationValidationError("Curation note cannot claim behavioral verification")
        if manual_control:
            for clause in _MANUAL_CLAUSES.split(value):
                for match in _MANUAL_CONTROL.finditer(clause):
                    if not _negates_manual_control(clause, match):
                        raise CurationValidationError("Case assembly must not instruct manual control-plane transactions")


def _tutorial_text(value: object, field: str, maximum: int, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (not allow_empty and not value.strip()):
        raise CurationValidationError("Tutorial text field is invalid: " + field)
    return value.strip()


def _tutorial_strings(value: object, field: str, *, minimum: int = 1, maximum: int = 12) -> list[str]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise CurationValidationError("Tutorial list field is invalid: " + field)
    result = [_tutorial_text(item, field, 1600) for item in value]
    from .usage_learning import display_items

    if len(display_items(result)) != len(result):
        raise CurationValidationError("Tutorial list contains empty marker items: " + field)
    return list(dict.fromkeys(result))


def _tutorial_evidence(value: object, known: set[str], field: str) -> list[str]:
    values = _tutorial_strings(value, field, maximum=_MAX_EVIDENCE_IDS)
    if not set(values) <= known:
        raise CurationValidationError("Tutorial requires genuine source evidence IDs: " + field)
    return values


def _tutorial_code(value: object, language: object, field: str, *, maximum: int, allow_empty: bool) -> tuple[str, str]:
    if not isinstance(language, str) or language not in {"python", "bash", "text"}:
        raise CurationValidationError("Tutorial language is invalid: " + field)
    if not isinstance(value, str) or len(value) > maximum or (not allow_empty and not value.strip()):
        raise CurationValidationError("Tutorial code is missing or oversized: " + field)
    code = value.strip("\r\n")
    if not code.strip():
        return "", language
    if all(line.strip() in {"...", "pass"} for line in code.splitlines() if line.strip()):
        raise CurationValidationError("Tutorial code must not be a placeholder: " + field)
    if language == "python":
        try:
            tree = ast.parse(code)
        except (SyntaxError, ValueError, TypeError, RecursionError):
            raise CurationValidationError("Tutorial Python code is invalid: " + field) from None
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value is Ellipsis:
                raise CurationValidationError("Tutorial code must not contain Ellipsis placeholders: " + field)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                body = [item for item in node.body if not (isinstance(item, ast.Expr)
                        and isinstance(item.value, ast.Constant) and isinstance(item.value.value, str))]
                if not body or all(isinstance(item, ast.Pass) for item in body):
                    raise CurationValidationError("Tutorial code must not contain pass-only placeholders: " + field)
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
                if _MANUAL_CONTROL.fullmatch(name):
                    raise CurationValidationError("Case assembly must not instruct manual control-plane transactions")
        if not any(not isinstance(item, (ast.Import, ast.ImportFrom, ast.Pass))
                   and not (isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant)) for item in tree.body):
            raise CurationValidationError("Tutorial code must include actual usage: " + field)
    return code, language


def validate_tutorial(payload: object, *, evidence_ids: set[str], allow_reference: bool = False) -> dict[str, Any]:
    """Validate display-only detailed usage without importing or executing code.

    The caller supplies verified evidence identities. Static syntax and genuine
    citations cannot prove the code's behavior or its business interpretation.
    External host names remain governed by the explicit preparation text; they
    are not guessed from imports or rejected as if every Case were standalone.
    """
    if not isinstance(payload, Mapping) or set(payload) != _TUTORIAL_FIELDS:
        raise CurationValidationError("Tutorial must contain exactly the supported fields")
    result = {
        "scenario": _tutorial_text(payload["scenario"], "scenario", 2000),
        "preparation": _tutorial_strings(payload["preparation"], "preparation"),
        "placement": _tutorial_text(payload["placement"], "placement", 2000),
        "execution_flow": _tutorial_strings(payload["execution_flow"], "execution_flow"),
        "result_checks": _tutorial_strings(payload["result_checks"], "result_checks"),
        "evidence_ids": _tutorial_evidence(payload["evidence_ids"], evidence_ids, "evidence_ids"),
    }
    result["code"], result["language"] = _tutorial_code(payload["code"], payload["language"], "code",
                                                       maximum=12000, allow_empty=allow_reference)
    extensions = payload["extensions"]
    if not isinstance(extensions, list) or not (0 if allow_reference else 1) <= len(extensions) <= 4:
        raise CurationValidationError("Tutorial requires one to four code extensions; references may omit them")
    normalized = []
    for extension in extensions:
        if not isinstance(extension, Mapping) or set(extension) != _EXTENSION_FIELDS:
            raise CurationValidationError("Tutorial extension must contain exactly the supported fields")
        item = {field: _tutorial_text(extension[field], "extensions." + field, 2000)
                for field in ("title", "purpose", "placement", "effect")}
        item["code"], item["language"] = _tutorial_code(extension["code"], extension["language"], "extensions.code",
                                                        maximum=8000, allow_empty=allow_reference)
        item["limits"] = _tutorial_strings(extension["limits"], "extensions.limits")
        item["evidence_ids"] = _tutorial_evidence(extension["evidence_ids"], evidence_ids, "extensions.evidence_ids")
        normalized.append(item)
    result["extensions"] = normalized
    if len(_json(result)) > MAX_TUTORIAL_CHARS:
        raise CurationValidationError("Tutorial exceeds its 40000 character limit")
    texts = []

    def collect(value):
        if isinstance(value, str):
            texts.append(value)
        elif isinstance(value, Mapping):
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(result)
    _safety_texts(texts, manual_control=True)
    return result


def validate_note(payload: object, packet: Mapping[str, Any]) -> dict[str, Any]:
    """Validate generated explanations; this does not certify their semantics."""
    if packet.get("schema") != PACKET_SCHEMA or packet.get("source_digest") != _digest({key: value for key, value in packet.items() if key != "source_digest"}):
        raise CurationValidationError("Curation evidence packet identity is invalid")
    if not isinstance(payload, Mapping) or set(payload) not in (NOTE_FIELDS, NOTE_FIELDS | {"tutorial"}):
        raise CurationValidationError("Curation note must contain exactly the supported explanation fields")
    result = {}
    for field in ("summary", "inputs_outputs"):
        value = payload[field]
        if not isinstance(value, str) or not value.strip() or len(value) > (1600 if field == "inputs_outputs" else 900):
            raise CurationValidationError("Curation text field is invalid: " + field)
        result[field] = value.strip()
    for field in NOTE_FIELDS - {"summary", "inputs_outputs"}:
        values = payload[field]
        if not isinstance(values, list) or len(values) > (_MAX_EVIDENCE_IDS if field == "evidence_ids" else 12):
            raise CurationValidationError("Curation list field is invalid: " + field)
        if any(not isinstance(value, str) or not value.strip() or len(value) > 1200 for value in values):
            raise CurationValidationError("Curation list item is invalid: " + field)
        result[field] = list(dict.fromkeys(value.strip() for value in values))
    known = set(packet.get("known_entry_keys", ()))
    if not set(result["related_keys"]) <= known:
        raise CurationValidationError("Curation note references unknown related components")
    evidence_ids = {item["id"] for item in packet.get("evidence", ())}
    if not result["evidence_ids"] or not set(result["evidence_ids"]) <= evidence_ids:
        raise CurationValidationError("Curation note requires genuine source evidence IDs")
    texts = [item for value in result.values() for item in ([value] if isinstance(value, str) else value)]
    _safety_texts(texts)
    _safety_texts(result["assembly_steps"], manual_control=True)
    if "tutorial" in payload:
        result["tutorial"] = validate_tutorial(payload["tutorial"], evidence_ids=evidence_ids,
                                                allow_reference=packet.get("entry", {}).get("kind") in {"doc", "example"})
    # Static extraction gaps cannot disappear merely because a model omitted them.
    result["missing_information"] = list(dict.fromkeys([*packet.get("gaps", ()), *result["missing_information"]]))[:12]
    # A note has no fields that can replace a runtime contract or execute code.
    return result


__all__ = ["PACKET_SCHEMA", "PROMPT_VERSION", "MAX_PACKET_CHARS", "MAX_TUTORIAL_CHARS", "NOTE_FIELDS",
           "CurationValidationError", "prepare_packet", "validate_note", "validate_tutorial"]
