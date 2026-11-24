"""Auditable Catalog links derived from declared usage, without loading components.

Coordinates refer to the exact ``minimal_wiring`` text (joined with newlines),
not to a guessed line in a TOML file. Static public re-exports may establish
identity; matching class names, imports alone and runtime execution may not.
"""
from __future__ import annotations

import ast
from collections import defaultdict
from functools import lru_cache
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace
from typing import Any, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from .registry import CatalogEntry


ASSEMBLY_NOTE = (
    "关系来自用法片段中的显式导入与调用；仅导入未调用不建立关系。"
    "片段同现不表示必须依赖、兼容性承诺或已经执行；行列指向原始用法片段。"
)
_LABELS = {"assembly_uses": "用法片段使用了", "assembly_used_by": "被哪些用法使用"}
_PACKAGES = ("nsgablack", "blackbase", "mlblack")


def _package_roots() -> dict[str, Path]:
    """Use loaded package locations or known sibling sources, never import targets."""
    repository = Path(__file__).resolve().parent.parent
    roots = {"nsgablack": repository}
    for package in _PACKAGES[1:]:
        loaded = sys.modules.get(package)
        filename = vars(loaded).get("__file__") if loaded is not None else None
        if filename:
            roots[package] = Path(filename).resolve().parent
            continue
        for candidate in (repository.parent / package / "src" / package,
                          repository.parent / package / package,
                          repository.parent / package):
            if (candidate / "__init__.py").is_file():
                roots[package] = candidate
                break
    return roots


@lru_cache(maxsize=512)
def _parse_file(path: str, modified: int, size: int) -> ast.Module | None:
    try:
        return ast.parse(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, SyntaxError, UnicodeError):
        return None


@lru_cache(maxsize=2048)
def _parse_wiring(source: str):
    return ast.parse(source)


def _bound_names(node: ast.AST) -> set[str]:
    """Names local to this scope; nested scopes cannot lend an import to it."""
    names: set[str] = set()

    class Bindings(ast.NodeVisitor):
        def visit_Name(self, item):
            if isinstance(item.ctx, (ast.Store, ast.Del)):
                names.add(item.id)

        def visit_Import(self, item):
            names.update(alias.asname or alias.name.split(".")[0] for alias in item.names)

        def visit_ImportFrom(self, item):
            names.update(alias.asname or alias.name for alias in item.names)

        def visit_FunctionDef(self, item):
            names.add(item.name)

        visit_AsyncFunctionDef = visit_FunctionDef
        visit_ClassDef = visit_FunctionDef

        def visit_Lambda(self, item):
            pass

    visitor = Bindings()
    for child in getattr(node, "body", ()):
        visitor.visit(child)
    return names


class _Exports:
    def __init__(self):
        self.roots = _package_roots()
        self.cache: dict[str, tuple[str, tuple[dict[str, Any], ...]]] = {}

    def module_file(self, module):
        parts = module.split(".")
        if not all(part.isidentifier() for part in parts):
            return None
        root = self.roots.get(parts[0])
        if root is None:
            return None
        base = root.joinpath(*parts[1:])
        path = base / "__init__.py" if base.is_dir() else base.with_suffix(".py")
        return path if path.is_file() else None

    def resolve(self, import_path: str, seen: frozenset[str] = frozenset()):
        if import_path in self.cache:
            return self.cache[import_path]
        if import_path in seen or len(seen) >= 16:
            return "", ()
        module, separator, symbol = import_path.partition(":")
        if not separator or not module or not symbol or "." in symbol:
            return import_path, ()
        parts = module.split(".")
        path = self.module_file(module)
        if path is None:
            return import_path, ()
        try:
            stat = path.stat()
        except OSError:
            return import_path, ()
        tree = _parse_file(str(path), stat.st_mtime_ns, stat.st_size)
        if tree is None:
            return import_path, ()
        # Only one unconditional, unshadowed import establishes a re-export.
        matches = []
        shadowed = False
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if (alias.asname or alias.name) != symbol:
                        continue
                    if node.level:
                        package = parts if path.name == "__init__.py" else parts[:-1]
                        if node.level > len(package):
                            return "", ()
                        prefix = package[:len(package) - node.level + 1]
                        target_module = ".".join(prefix + ([node.module] if node.module else []))
                    else:
                        target_module = node.module or ""
                    matches.append((f"{target_module}:{alias.name}", node))
            elif symbol in _bound_names(ast.Module(body=[node], type_ignores=[])):
                shadowed = True
        if not matches:
            # Dynamic __getattr__ and wildcard exports deliberately yield no equivalence.
            result = (import_path, ())
        elif len(matches) != 1 or shadowed:
            result = ("", ())
        else:
            target, node = matches[0]
            canonical, chain = self.resolve(target, seen | {import_path})
            evidence = {"path": str(path), "line": node.lineno,
                        "import_path": import_path, "target_import_path": target}
            result = (canonical, (evidence, *chain))
        self.cache[import_path] = result
        return result


class _Index:
    def __init__(self, entries):
        self.exports = _Exports()
        self.direct = defaultdict(list)
        self.canonical = defaultdict(list)
        self.symbols = set()
        for entry in entries:
            self.direct[entry.import_path].append(entry)
            self.symbols.add(entry.import_path.partition(":")[2])
            canonical, _ = self.exports.resolve(entry.import_path)
            if canonical:
                self.canonical[canonical].append(entry)

    def match(self, import_path):
        module, _, symbol = import_path.partition(":")
        if "." in symbol and import_path not in self.direct:
            prefix, _, attribute = symbol.rpartition(".")
            submodule = module + "." + prefix
            if self.exports.module_file(submodule) is not None:
                import_path = submodule + ":" + attribute
        canonical, chain = self.exports.resolve(import_path)
        matches = self.direct.get(import_path, ()) or self.canonical.get(canonical, ())
        return list(matches), chain


def _analyze(entry, index):
    lines = getattr(entry, "minimal_wiring", ())
    if not lines:
        return {}, ({"code": "missing-wiring", "note": "尚未声明用法片段，无法提取装配关系。"},), "missing"
    if not isinstance(lines, (tuple, list)) or any(not isinstance(line, str) for line in lines):
        return {}, ({"code": "invalid-wiring", "note": "用法片段必须为字符串列表。"},), "invalid"
    source = "\n".join(lines)
    try:
        tree = _parse_wiring(source)
    except SyntaxError as exc:
        return {}, ({"code": "invalid-wiring", "line": exc.lineno, "column": exc.offset,
                     "note": f"用法片段无法解析：{exc.msg}"},), "invalid"
    links = defaultdict(list)
    diagnostics = []
    source_lines = source.splitlines()

    def column(line, byte_offset):
        return len(source_lines[line - 1].encode("utf-8")[:byte_offset].decode("utf-8")) + 1

    class Calls(ast.NodeVisitor):
        def __init__(self):
            self.bindings = {}
            self.class_globals = None

        def visit_Import(self, node):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                self.bindings[local] = (alias.name if alias.asname else local, node.lineno)

        def visit_ImportFrom(self, node):
            if node.level or any(alias.name == "*" for alias in node.names):
                diagnostics.append({"code": "unsupported-import", "line": node.lineno,
                                    "note": "相对导入或星号导入无法在独立片段中确定身份。"})
                return
            for alias in node.names:
                self.bindings[alias.asname or alias.name] = (f"{node.module}:{alias.name}", node.lineno)

        def visit_Name(self, node):
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                self.bindings[node.id] = None

        def visit_Assign(self, node):
            self.visit(node.value)
            for target in node.targets:
                self.visit(target)

        def visit_AnnAssign(self, node):
            if node.value is not None:
                self.visit(node.value)
            self.visit(node.target)

        def visit_NamedExpr(self, node):
            self.visit(node.value)
            self.visit(node.target)

        def visit_FunctionDef(self, node):
            for decorator in node.decorator_list:
                self.visit(decorator)
            for default in (*node.args.defaults, *node.args.kw_defaults):
                if default is not None:
                    self.visit(default)
            self.bindings[node.name] = None
            outer = self.bindings
            class_globals = self.class_globals
            self.bindings = dict(class_globals if class_globals is not None else outer)
            self.class_globals = None
            for local in _bound_names(node):
                self.bindings[local] = None
            for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs,
                        *([node.args.vararg] if node.args.vararg else []),
                        *([node.args.kwarg] if node.args.kwarg else [])):
                self.bindings[arg.arg] = None
            for statement in node.body:
                self.visit(statement)
            self.bindings = outer
            self.class_globals = class_globals

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, node):
            for item in (*node.bases, *node.decorator_list):
                self.visit(item)
            self.bindings[node.name] = None
            outer = self.bindings
            previous = self.class_globals
            self.class_globals = outer
            self.bindings = dict(outer)
            for statement in node.body:
                self.visit(statement)
            self.bindings = outer
            self.class_globals = previous

        def visit_Lambda(self, node):
            outer = self.bindings
            class_globals = self.class_globals
            self.bindings = dict(class_globals if class_globals is not None else outer)
            self.class_globals = None
            for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs,
                        *([node.args.vararg] if node.args.vararg else []),
                        *([node.args.kwarg] if node.args.kwarg else [])):
                self.bindings[arg.arg] = None
            self.visit(node.body)
            self.bindings = outer
            self.class_globals = class_globals

        def visit_ListComp(self, node):
            outer = self.bindings
            self.visit(node.generators[0].iter)
            self.bindings = dict(outer)
            for number, generator in enumerate(node.generators):
                if number:
                    self.visit(generator.iter)
                self.visit(generator.target)
                for condition in generator.ifs:
                    self.visit(condition)
            if isinstance(node, ast.DictComp):
                self.visit(node.key)
                self.visit(node.value)
            else:
                self.visit(node.elt)
            self.bindings = outer

        visit_SetComp = visit_ListComp
        visit_DictComp = visit_ListComp
        visit_GeneratorExp = visit_ListComp

        def visit_ExceptHandler(self, node):
            if node.type:
                self.visit(node.type)
            if node.name:
                self.bindings[node.name] = None
            for statement in node.body:
                self.visit(statement)

        def visit_If(self, node):
            self.visit(node.test)
            outer = dict(self.bindings)
            branches = []
            for branch in (node.body, node.orelse):
                self.bindings = dict(outer)
                for statement in branch:
                    self.visit(statement)
                branches.append(self.bindings)
            self.bindings = {name: branches[0].get(name) if branches[0].get(name) == branches[1].get(name) else None
                             for name in branches[0].keys() | branches[1].keys()}

        def visit_Try(self, node):
            outer = dict(self.bindings)
            for statement in (*node.body, *node.orelse):
                self.visit(statement)
            branches = [self.bindings]
            for handler in node.handlers:
                self.bindings = dict(outer)
                self.visit(handler)
                branches.append(self.bindings)
            names = set().union(*(branch.keys() for branch in branches))
            self.bindings = {name: branches[0].get(name) if all(branch.get(name) == branches[0].get(name) for branch in branches) else None
                             for name in names}
            for statement in node.finalbody:
                self.visit(statement)

        visit_TryStar = visit_Try

        def visit_For(self, node):
            self.visit(node.iter)
            outer = dict(self.bindings)
            self.visit(node.target)
            for statement in node.body:
                self.visit(statement)
            after = self.bindings
            self.bindings = {name: after.get(name) if after.get(name) == outer.get(name) else None
                             for name in after.keys() | outer.keys()}
            for statement in node.orelse:
                self.visit(statement)

        visit_AsyncFor = visit_For

        def visit_Call(self, node):
            parts = []
            value = node.func
            while isinstance(value, ast.Attribute):
                parts.insert(0, value.attr)
                value = value.value
            if isinstance(value, ast.Name):
                parts.insert(0, value.id)
                binding = self.bindings.get(value.id)
                if binding:
                    path, import_line = binding
                    if len(parts) > 1:
                        if ":" in path:
                            path += "." + ".".join(parts[1:])
                        else:
                            path = ".".join([path, *parts[1:-1]]) + ":" + parts[-1]
                    matches, chain = index.match(path)
                    if len(matches) == 1:
                        target = matches[0]
                        if target.key != entry.key:
                            links[target.key].append({
                                "source_key": entry.key, "source_field": "minimal_wiring",
                                "line": node.lineno, "column": column(node.lineno, node.col_offset),
                                "end_line": node.end_lineno, "end_column": column(node.end_lineno, node.end_col_offset),
                                "call": ast.get_source_segment(source, node.func),
                                "source_line": source_lines[node.lineno - 1],
                                "import_path": path, "import_line": import_line,
                                "target_import_path": target.import_path,
                                "resolution": "static-reexport" if chain or target.import_path != path else "exact-import",
                                "reexports": chain,
                                "target_reexports": index.exports.resolve(target.import_path)[1],
                            })
                    elif len(matches) > 1:
                        diagnostics.append({"code": "ambiguous-target", "line": node.lineno,
                                            "call": ".".join(parts), "import_path": path,
                                            "candidate_keys": tuple(sorted(item.key for item in matches)),
                                            "note": "该导入对应多个 Catalog 条目，未猜测目标。"})
                    elif path.split(".", 1)[0].split(":", 1)[0] in _PACKAGES:
                        diagnostics.append({"code": "unresolved-target", "line": node.lineno,
                                            "call": ".".join(parts), "import_path": path,
                                            "note": "当前 Catalog 范围内没有可唯一确认的调用目标。"})
                elif parts[-1] in index.symbols:
                    diagnostics.append({"code": "missing-import", "line": node.lineno,
                                        "call": ".".join(parts),
                                        "note": "调用缺少可确定身份的显式导入，或名称已被局部绑定覆盖。"})
            self.generic_visit(node)

    Calls().visit(tree)
    return dict(links), tuple(diagnostics), "partial" if diagnostics else "analyzed"


def _declared_analysis(entry, index):
    links, diagnostics, status = _analyze(entry, index)
    diagnostics = tuple({"source_field": "minimal_wiring", **item} for item in diagnostics)
    module, separator, symbol = entry.import_path.partition(":")
    if not separator or not all(part.isidentifier() for part in (*module.split("."), *symbol.split("."))):
        diagnostics += ({"code": "invalid-import-path", "note": "条目的 import_path 声明无效，未据此猜测组件身份。"},)
        status = "partial" if links else "invalid"
    return links, diagnostics, status


def _source_roots():
    roots = {}
    for package, root in _package_roots().items():
        for candidate in (root, *tuple(root.parents)[:3]):
            if (candidate / "pyproject.toml").is_file():
                roots[package] = candidate
                break
    return roots


@lru_cache(maxsize=512)
def _python_blocks(text):
    """Yield only closed Python fences, with offsets in the exact excerpt."""
    opening = None
    lines = []
    blocks = []
    for number, line in enumerate(text.splitlines(), 1):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if opening:
            fence, start, language = opening
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                if language in {"python", "py"} and lines:
                    blocks.append((start, tuple(lines)))
                opening, lines = None, []
            else:
                lines.append(line)
        elif marker:
            info = marker[2].strip().split()
            opening = (marker[1], number + 1, info[0].lower() if info else "")
    return tuple(blocks)


@lru_cache(maxsize=4)
def _published_index(path, modified, size):
    from .examples import load_example_index

    return load_example_index(Path(path))


@lru_cache(maxsize=128)
def _published_source(roots, qualified, modified, size):
    from .examples import _read

    return _read(dict(roots), qualified)


def _usage_examples(universe, index):
    """Accept only source-verified, explicitly bound focused documentation."""
    configured = os.environ.get("NSGABLACK_CATALOG_EXAMPLES_INDEX", "").strip()
    if not configured:
        return {}, {}
    from .examples import ExampleValidationError, _safe_file

    try:
        index_stat = Path(configured).stat()
        published = _published_index(configured, index_stat.st_mtime_ns, index_stat.st_size)
    except (OSError, ValueError, UnicodeError, TypeError, KeyError):
        return {}, {key: [{"code": "usage-index-invalid", "note": "用法示例索引不可用，未据此建立关系。"}]
                    for key in universe}
    roots = _source_roots()
    links_by_key = defaultdict(lambda: defaultdict(list))
    issues_by_key = defaultdict(list)
    file_cache = {}
    for identifier, example in published["examples"].items():
        owners = set(example["component_keys"]) & universe.keys()
        if (not owners or example["binding"] != "focused" or example["kind"] != "documentation"
                or example["verification"]["status"] not in {"source_checked", "executed"}):
            continue
        for snippet in example["snippets"]:
            path = snippet["path"]
            if not path.endswith(".md"):
                continue
            if not snippet["complete"]:
                for owner in owners:
                    issues_by_key[owner].append({"code": "usage-source-incomplete", "example_id": identifier,
                                                "note": "专属用法摘录不完整，未提取装配关系。"})
                continue
            try:
                if path not in file_cache:
                    _, source_path = _safe_file(roots, path)
                    stat = source_path.stat()
                    text, digest = _published_source(tuple(sorted(roots.items())), path, stat.st_mtime_ns, stat.st_size)
                    file_cache[path] = (text.splitlines(), digest)
                source_lines, digest = file_cache[path]
                selected = "\n".join(source_lines[snippet["start_line"] - 1:snippet["end_line"]])
                if digest != snippet["file_sha256"] or selected != snippet["text"]:
                    raise ExampleValidationError("usage_source_stale")
            except (OSError, ValueError, UnicodeError):
                for owner in owners:
                    issues_by_key[owner].append({"code": "usage-source-unavailable", "example_id": identifier,
                                                "note": "专属用法的源文件或哈希不匹配，未提取该片段。"})
                continue
            for start, lines in _python_blocks(selected):
                # Analyze once per bound owner so self-exclusion stays exact.
                for owner in owners:
                    links_by_key.setdefault(owner, defaultdict(list))
                    synthetic = SimpleNamespace(key=owner, minimal_wiring=lines)
                    links, diagnostics, _ = _analyze(synthetic, index)
                    offset = snippet["start_line"] + start - 2
                    identity = {"source_field": "usage_example", "example_id": identifier,
                                "source_path": path, "file_sha256": digest, "source_sha256": snippet["sha256"]}
                    for target, evidence in links.items():
                        for item in evidence:
                            links_by_key[owner][target].append({**item, **identity,
                                "line": item["line"] + offset, "end_line": item["end_line"] + offset,
                                "import_line": item["import_line"] + offset})
                    for diagnostic in diagnostics:
                        issue = {**diagnostic, **identity}
                        if "line" in issue and issue["line"] is not None:
                            issue["line"] += offset
                        issues_by_key[owner].append(issue)
    return dict(links_by_key), dict(issues_by_key)


def _deduplicate(evidence):
    unique = {}
    for item in evidence:
        identity = tuple(item.get(field) for field in ("source_key", "source_field", "source_path", "file_sha256",
                                                       "line", "column", "import_path", "target_import_path"))
        if identity not in unique:
            unique[identity] = dict(item)
        if item.get("example_id"):
            current = unique[identity]
            current["example_ids"] = tuple(sorted(set(current.get("example_ids", ())) | {item["example_id"]}))
    return tuple(unique.values())


def build_assembly_neighbor_sections(entry: CatalogEntry, *, candidates: Sequence[CatalogEntry] = ()) -> dict[str, Any]:
    """Compute both directions within the supplied profile/scope only.

    Read raw declarations, including whitespace. Do not infer recipes, inspect
    constructor signatures, import target modules, or construct Adapter/Unit.
    """
    universe = {candidate.key: candidate for candidate in candidates if candidate.key != entry.key}
    universe[entry.key] = entry
    index = _Index(tuple(universe.values()))
    analyses = {key: _declared_analysis(candidate, index) for key, candidate in universe.items()}
    examples, example_issues = _usage_examples(universe, index)
    for key in examples.keys() | example_issues.keys():
        links, diagnostics, status = analyses[key]
        for target, evidence in examples.get(key, {}).items():
            links.setdefault(target, []).extend(evidence)
        additional = tuple(example_issues.get(key, ()))
        if key in examples and status in {"missing", "invalid"}:
            status = "analyzed" if status == "missing" else "partial"
        analyses[key] = (links, (*diagnostics, *additional), "partial" if additional else status)
    outgoing, diagnostics, status = analyses[entry.key]

    def row(candidate, evidence, role):
        return {"key": candidate.key, "title": candidate.title, "kind": candidate.kind,
                "summary": candidate.summary, "relation_family": "assembly",
                "relation_role": role, "relation_note": ASSEMBLY_NOTE,
                "evidence": _deduplicate(evidence)}

    uses = [row(universe[key], evidence, "used") for key, evidence in outgoing.items()]
    used_by = [row(universe[key], links[entry.key], "usage") for key, (links, _, _) in analyses.items()
               if key != entry.key and entry.key in links]
    groups = {name: sorted(rows, key=lambda item: (item["kind"], item["key"]))
              for name, rows in (("assembly_uses", uses), ("assembly_used_by", used_by)) if rows}
    cards = tuple({"group_id": name, "family": "assembly", "family_label": "用法装配",
                   "direction": "out" if name == "assembly_uses" else "in", "value": name,
                   "title": _LABELS[name], "count": len(rows), "preview_items": tuple(rows[:3])}
                  for name, rows in groups.items())
    return {"relation_groups": groups, "relation_labels": dict(_LABELS), "relation_cards": cards,
            "assembly_status": status, "assembly_diagnostics": diagnostics, "assembly_note": ASSEMBLY_NOTE}


__all__ = ["ASSEMBLY_NOTE", "build_assembly_neighbor_sections"]
