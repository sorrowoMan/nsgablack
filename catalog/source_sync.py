from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

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
