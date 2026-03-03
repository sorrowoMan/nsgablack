from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

_CONTRACT_FIELDS: Tuple[str, ...] = (
    "context_requires",
    "context_provides",
    "context_mutates",
    "context_cache",
    "context_notes",
)


@dataclass(frozen=True)
class SourceSymbol:
    name: str
    kind: str
    lineno: int
    marked: bool = False


@dataclass(frozen=True)
class ExpansionScope:
    root: Path
    scope: str  # "project" | "framework"


def _infer_kind(class_node: ast.ClassDef) -> str:
    name = str(class_node.name)
    base_names: List[str] = []
    for base in class_node.bases:
        if isinstance(base, ast.Name):
            base_names.append(str(base.id))
        elif isinstance(base, ast.Attribute):
            base_names.append(str(base.attr))
    hint = " ".join([name] + base_names).lower()
    if "plugin" in hint:
        return "plugin"
    if "bias" in hint:
        return "bias"
    if "adapter" in hint:
        return "adapter"
    if any(tok in hint for tok in ("initializer", "mutation", "mutator", "repair", "pipeline")):
        return "representation"
    return "tool"


def _decorator_name(deco: ast.expr) -> str:
    if isinstance(deco, ast.Call):
        return _decorator_name(deco.func)
    if isinstance(deco, ast.Name):
        return str(deco.id)
    if isinstance(deco, ast.Attribute):
        return str(deco.attr)
    return ""


def _decorator_kw_str(deco: ast.expr, key: str) -> str | None:
    if not isinstance(deco, ast.Call):
        return None
    for kw in deco.keywords:
        if kw.arg == key and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return str(kw.value.value).strip()
    return None


def _marker_meta(class_node: ast.ClassDef) -> tuple[bool, str | None]:
    for deco in class_node.decorator_list:
        name = _decorator_name(deco)
        if name in {"component", "catalog_component", "nsgablack_component"}:
            return True, (_decorator_kw_str(deco, "kind") or None)
    return False, None


def _is_scaffold_project_root(root: Path) -> bool:
    req_files = ("project_registry.py", "build_solver.py")
    req_dirs = ("problem", "pipeline", "bias", "adapter", "plugins")
    return all((root / f).is_file() for f in req_files) and all((root / d).is_dir() for d in req_dirs)


def _is_framework_root(root: Path) -> bool:
    return (
        (root / "pyproject.toml").is_file()
        and (root / "catalog" / "entries.toml").is_file()
        and (root / "core").is_dir()
        and (root / "bias").is_dir()
    )


def detect_expansion_scope(path: Path | str) -> Optional[ExpansionScope]:
    src = Path(path).resolve()
    start = src if src.is_dir() else src.parent
    for cand in [start] + list(start.parents):
        if (cand / ".nsgablack-project").is_file() and _is_scaffold_project_root(cand):
            return ExpansionScope(root=cand, scope="project")
        if _is_scaffold_project_root(cand):
            return ExpansionScope(root=cand, scope="project")
        if _is_framework_root(cand):
            return ExpansionScope(root=cand, scope="framework")
    return None


def list_source_symbols(path: Path | str, *, marked_only: bool = False) -> List[SourceSymbol]:
    file_path = Path(path)
    source = file_path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source, filename=str(file_path))
    out: List[SourceSymbol] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            marked, marked_kind = _marker_meta(node)
            if marked_only and not marked:
                continue
            out.append(
                SourceSymbol(
                    name=str(node.name),
                    kind=marked_kind or _infer_kind(node),
                    lineno=int(node.lineno),
                    marked=marked,
                )
            )
    return out


def _literal_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return str(node.value)
    return None


def _read_values(node: ast.AST) -> Tuple[str, ...]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        text = str(node.value).strip()
        return (text,) if text else ()
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        vals: List[str] = []
        for elt in node.elts:
            s = _literal_str(elt)
            if s is not None and s.strip():
                vals.append(s.strip())
        return tuple(vals)
    return ()


def read_symbol_contract(path: Path | str, symbol: str) -> Dict[str, Tuple[str, ...]]:
    file_path = Path(path)
    source = file_path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source, filename=str(file_path))
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != symbol:
            continue
        out: Dict[str, Tuple[str, ...]] = {k: () for k in _CONTRACT_FIELDS}
        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                for t in stmt.targets:
                    if isinstance(t, ast.Name) and t.id in out:
                        out[t.id] = _read_values(stmt.value)
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.target.id in out:
                if stmt.value is not None:
                    out[stmt.target.id] = _read_values(stmt.value)
        return out
    raise ValueError(f"symbol not found: {symbol}")


def _is_placeholder_name(kind: str, class_name: str) -> bool:
    n = class_name.strip().lower()
    if n in {"newbias", "bias", "newplugin", "plugin", "newadapter", "adapter", "newcomponent", "component"}:
        return True
    if kind == "bias" and n.endswith("bias") and n.startswith("new"):
        return True
    if kind == "plugin" and n.endswith("plugin") and n.startswith("new"):
        return True
    if kind == "adapter" and n.endswith("adapter") and n.startswith("new"):
        return True
    return False


def _pick_unique_class_name(raw: str, *, kind: str, current_name: str) -> str:
    tree = ast.parse(raw)
    existing = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
    existing.discard(current_name)
    kind_base = {"bias": "Bias", "plugin": "Plugin", "adapter": "Adapter"}.get(kind, "Component")
    if current_name and not _is_placeholder_name(kind, current_name) and current_name not in existing:
        return current_name
    idx = 1
    while f"{kind_base}{idx}" in existing:
        idx += 1
    return f"{kind_base}{idx}"


def _is_empty_shell_class(node: ast.ClassDef) -> bool:
    body = list(node.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    if not body:
        return True
    return all(isinstance(stmt, ast.Pass) for stmt in body)


def _import_insert_line(tree: ast.Module) -> int:
    insert = 1
    if (
        tree.body
        and isinstance(tree.body[0], ast.Expr)
        and isinstance(tree.body[0].value, ast.Constant)
        and isinstance(tree.body[0].value.value, str)
    ):
        first = tree.body[0]
        insert = int(getattr(first, "end_lineno", first.lineno)) + 1
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and str(node.module or "") == "__future__":
            insert = int(getattr(node, "end_lineno", node.lineno)) + 1
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            insert = int(getattr(node, "end_lineno", node.lineno)) + 1
            continue
        break
    return insert


def _ensure_imports(raw: str, import_lines: Sequence[str]) -> str:
    missing = [line for line in import_lines if line and line not in raw]
    if not missing:
        return raw
    lines = raw.splitlines(keepends=True)
    tree = ast.parse(raw)
    at = _import_insert_line(tree)
    block = "".join(f"{line}\n" for line in missing) + "\n"
    lines.insert(max(0, at - 1), block)
    return "".join(lines)


def _build_template_block(kind: str, class_name: str) -> tuple[list[str], str]:
    k = kind.strip().lower()
    if k == "bias":
        imports = [
            "from nsgablack.catalog.markers import component",
            "from nsgablack.bias.core.base import BiasBase, OptimizationContext",
        ]
        block = (
            '@component(kind="bias")\n'
            f"class {class_name}(BiasBase):\n"
            "    # TODO(中/EN): 仅声明真实读写字段 / declare only real read-write fields.\n"
            "    context_requires = ()\n"
            "    context_provides = ()\n"
            "    context_mutates = ()\n"
            "    context_cache = ()\n"
            '    context_notes = ("TODO(中/EN): 一句话说明 context 契约 / one-line context contract.",)\n'
            "    requires_metrics = ()\n"
            '    metrics_fallback = "none"\n'
            '    missing_metrics_policy = "warn"\n'
            "\n"
            "    def __init__(self, weight: float = 1.0) -> None:\n"
            "        # TODO(中/EN): 设置稳定组件名与说明 / set stable name and description.\n"
            f'        super().__init__(name="{class_name.lower()}", weight=float(weight), description="TODO")\n'
            "\n"
            "    def compute(self, x, context: OptimizationContext) -> float:\n"
            "        # TODO(中/EN): 返回标量偏好分 / return a scalar preference score.\n"
            "        _ = x\n"
            "        _ = context\n"
            "        raise NotImplementedError\n"
        )
        return imports, block
    if k == "plugin":
        imports = [
            "from nsgablack.catalog.markers import component",
            "from nsgablack.plugins.base import Plugin",
        ]
        block = (
            '@component(kind="plugin")\n'
            f"class {class_name}(Plugin):\n"
            "    # TODO(中/EN): 仅声明真实读写字段 / declare only real read-write fields.\n"
            "    context_requires = ()\n"
            "    context_provides = ()\n"
            "    context_mutates = ()\n"
            "    context_cache = ()\n"
            '    context_notes = ("TODO(中/EN): 一句话说明 context 契约 / one-line context contract.",)\n'
            "\n"
            "    def __init__(self) -> None:\n"
            "        # TODO(中/EN): 设置稳定插件名 / set a stable plugin name.\n"
            f'        super().__init__(name="{class_name.lower()}")\n'
        )
        return imports, block
    if k == "adapter":
        imports = [
            "from nsgablack.catalog.markers import component",
            "from nsgablack.adapters.algorithm_adapter import AlgorithmAdapter",
        ]
        block = (
            '@component(kind="adapter")\n'
            f"class {class_name}(AlgorithmAdapter):\n"
            "    # TODO(中/EN): 仅声明真实读写字段 / declare only real read-write fields.\n"
            "    context_requires = ()\n"
            "    context_provides = ()\n"
            "    context_mutates = ()\n"
            "    context_cache = ()\n"
            '    context_notes = ("TODO(中/EN): 一句话说明 context 契约 / one-line context contract.",)\n'
            "\n"
            "    def __init__(self) -> None:\n"
            "        # TODO(中/EN): 设置稳定适配器名 / set a stable adapter name.\n"
            f'        super().__init__(name="{class_name.lower()}")\n'
            "\n"
            "    def propose(self, solver, context):\n"
            "        # TODO(中/EN): 生成候选解 / generate candidate solutions.\n"
            "        _ = solver\n"
            "        _ = context\n"
            "        raise NotImplementedError\n"
            "\n"
            "    def update(self, solver, candidates, objectives, violations, context):\n"
            "        # TODO(中/EN): 用评估反馈更新状态 / update state with evaluation feedback.\n"
            "        _ = solver\n"
            "        _ = candidates\n"
            "        _ = objectives\n"
            "        _ = violations\n"
            "        _ = context\n"
            "        raise NotImplementedError\n"
        )
        return imports, block
    raise ValueError(f"unsupported kind for template expansion: {kind}")


def expand_marked_component_template(
    path: Path | str,
    symbol: str,
    *,
    kind: str | None = None,
    force: bool = False,
) -> str:
    """
    Expand a marked shell class to a component template in-place.

    Boundary rule: only allowed under scaffold project roots or framework roots.
    Returns the final class name.
    """
    file_path = Path(path).resolve()
    scope = detect_expansion_scope(file_path)
    if scope is None:
        raise ValueError("template expansion is only enabled inside NSGABlack framework or scaffold projects")

    raw = file_path.read_text(encoding="utf-8-sig")
    raw = _ensure_imports(raw, ["from nsgablack.catalog.markers import component"])
    tree = ast.parse(raw, filename=str(file_path))

    class_node: ast.ClassDef | None = None
    marker_kind: str | None = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == symbol:
            class_node = node
            marked, mk = _marker_meta(node)
            if not marked:
                raise ValueError(f"class '{symbol}' is not marked with @component(...)")
            marker_kind = mk
            break
    if class_node is None:
        raise ValueError(f"symbol not found: {symbol}")
    if not force and not _is_empty_shell_class(class_node):
        raise ValueError(f"class '{symbol}' is not an empty shell; use force=True to overwrite")

    final_kind = (kind or marker_kind or _infer_kind(class_node)).strip().lower()
    final_class_name = _pick_unique_class_name(raw, kind=final_kind, current_name=symbol)
    imports, class_block = _build_template_block(final_kind, final_class_name)
    raw = _ensure_imports(raw, imports)
    lines = raw.splitlines(keepends=True)
    tree = ast.parse(raw, filename=str(file_path))

    class_node = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == symbol:
            class_node = node
            break
    if class_node is None:
        raise ValueError(f"symbol not found after import refresh: {symbol}")

    start = min([class_node.lineno] + [int(d.lineno) for d in class_node.decorator_list])
    end = int(getattr(class_node, "end_lineno", class_node.lineno))
    block = class_block if class_block.endswith("\n") else class_block + "\n"
    lines[start - 1 : end] = [block, "\n"]
    file_path.write_text("".join(lines), encoding="utf-8")

    return final_class_name


def _format_tuple_assignment(indent: str, name: str, values: Sequence[str]) -> str:
    clean = [str(v).strip() for v in values if str(v).strip()]
    if not clean:
        return f"{indent}{name} = ()\n"
    lines = [f"{indent}{name} = (\n"]
    for value in clean:
        lines.append(f"{indent}    {value!r},\n")
    lines.append(f"{indent})\n")
    return "".join(lines)


def _class_indent(source_line: str) -> str:
    return source_line[: len(source_line) - len(source_line.lstrip())]


def apply_symbol_contract(
    path: Path | str,
    symbol: str,
    contract: Dict[str, Sequence[str]],
) -> None:
    file_path = Path(path)
    raw = file_path.read_text(encoding="utf-8-sig")
    lines = raw.splitlines(keepends=True)
    tree = ast.parse(raw, filename=str(file_path))

    class_node: ast.ClassDef | None = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == symbol:
            class_node = node
            break
    if class_node is None:
        raise ValueError(f"symbol not found: {symbol}")

    class_indent = _class_indent(lines[class_node.lineno - 1] if class_node.lineno - 1 < len(lines) else "")
    member_indent = class_indent + "    "

    ranges: List[Tuple[int, int]] = []
    for stmt in class_node.body:
        if isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                if isinstance(t, ast.Name) and t.id in _CONTRACT_FIELDS:
                    ranges.append((int(stmt.lineno), int(getattr(stmt, "end_lineno", stmt.lineno))))
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.target.id in _CONTRACT_FIELDS:
            ranges.append((int(stmt.lineno), int(getattr(stmt, "end_lineno", stmt.lineno))))

    insert_line = class_node.lineno + 1
    if class_node.body:
        first = class_node.body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            insert_line = int(getattr(first, "end_lineno", first.lineno)) + 1
        else:
            insert_line = int(first.lineno)

    remove_before_insert = 0
    for start, end in ranges:
        if end < insert_line:
            remove_before_insert += end - start + 1
    effective_insert = insert_line - remove_before_insert

    for start, end in sorted(ranges, key=lambda x: x[0], reverse=True):
        del lines[start - 1 : end]

    block = []
    for field in _CONTRACT_FIELDS:
        block.append(_format_tuple_assignment(member_indent, field, contract.get(field, ())))
    block.append("\n")

    lines.insert(max(0, effective_insert - 1), "".join(block))
    file_path.write_text("".join(lines), encoding="utf-8")
