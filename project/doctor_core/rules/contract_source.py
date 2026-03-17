"""Contract/source static checks used by project doctor."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Callable, List, Sequence, Set

from ..model import DoctorDiagnostic
from nsgablack.core.state.context_keys import (
    CANONICAL_CONTEXT_KEYS,
    KEY_CONSTRAINT_VIOLATIONS,
    KEY_DECISION_TRACE,
    KEY_HISTORY,
    KEY_OBJECTIVES,
    KEY_PARETO_OBJECTIVES,
    KEY_PARETO_SOLUTIONS,
    KEY_POPULATION,
    normalize_context_key,
)
from .runtime_guards import (
    check_forbidden_solver_mirror_writes,
    check_plugin_solver_state_access,
    check_runtime_bypass_writes,
    check_runtime_private_calls,
)

_CONTRACT_KEYS = {
    "context_requires",
    "context_provides",
    "context_mutates",
    "context_cache",
    "context_notes",
    "requires_context_keys",
    "provides_context_keys",
    "mutates_context_keys",
    "cache_context_keys",
    "runtime_requires",
    "runtime_provides",
    "runtime_mutates",
    "runtime_cache",
}
_CONTRACT_KEY_VALUE_ATTR_GROUPS = {
    "requires": {"context_requires", "requires_context_keys", "runtime_requires"},
    "provides": {"context_provides", "provides_context_keys", "runtime_provides"},
    "mutates": {"context_mutates", "mutates_context_keys", "runtime_mutates"},
    "cache": {"context_cache", "cache_context_keys", "runtime_cache"},
}
_CONTRACT_DYNAMIC_FIELDS = {
    "requires": "requires",
    "provides": "provides",
    "mutates": "mutates",
    "cache": "cache",
    "context_requires": "requires",
    "context_provides": "provides",
    "context_mutates": "mutates",
    "context_cache": "cache",
    "requires_context_keys": "requires",
    "provides_context_keys": "provides",
    "mutates_context_keys": "mutates",
    "cache_context_keys": "cache",
    "runtime_requires": "requires",
    "runtime_provides": "provides",
    "runtime_mutates": "mutates",
    "runtime_cache": "cache",
}
_COMPONENT_NAME_SUFFIXES = (
    "Adapter",
    "Plugin",
    "Bias",
    "Mutator",
    "Mutation",
    "Repair",
    "Initializer",
    "Codec",
    "Pipeline",
)
_COMPONENT_BASE_NAMES = {
    "AlgorithmAdapter",
    "Plugin",
    "BaseBias",
    "BiasModule",
    "RepresentationPipeline",
}
_ALLOWED_METRICS_FALLBACK_VALUES = {
    "none",
    "safe_zero",
    "default",
    "problem_data",
    "warn",
    "ignore",
}
_CONTEXT_LARGE_OBJECT_KEYS = {
    KEY_POPULATION,
    KEY_OBJECTIVES,
    KEY_CONSTRAINT_VIOLATIONS,
    KEY_PARETO_SOLUTIONS,
    KEY_PARETO_OBJECTIVES,
    KEY_HISTORY,
    KEY_DECISION_TRACE,
}
_CONTEXT_VAR_NAMES = {"context", "ctx"}


def _class_has_contract(class_node: ast.ClassDef) -> bool:
    for node in class_node.body:
        if isinstance(node, ast.FunctionDef) and node.name == "get_context_contract":
            return True
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in _CONTRACT_KEYS:
                    return True
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id in _CONTRACT_KEYS:
            return True
    return False


def _class_missing_core_contract_fields(class_node: ast.ClassDef, *, core_contract_keys: Set[str]) -> List[str]:
    for node in class_node.body:
        if isinstance(node, ast.FunctionDef) and node.name == "get_context_contract":
            return []

    present: set[str] = set()
    for node in class_node.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in core_contract_keys:
                    present.add(str(target.id))
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id in core_contract_keys:
                present.add(str(node.target.id))
    return sorted(core_contract_keys - present)


def _extract_literal_string_values(node: ast.expr) -> List[str]:
    try:
        value = ast.literal_eval(node)
    except Exception:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple, set)):
        out: List[str] = []
        for item in value:
            if not isinstance(item, str):
                continue
            text = item.strip()
            if text:
                out.append(text)
        return out
    return []


def _literal_str_value(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return str(node.value)
    return None


def _iter_declared_contract_literals(class_node: ast.ClassDef) -> List[tuple[str, str]]:
    rows: List[tuple[str, str]] = []
    value_attrs = {item for values in _CONTRACT_KEY_VALUE_ATTR_GROUPS.values() for item in values}

    for node in class_node.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in value_attrs:
                    for item in _extract_literal_string_values(node.value):
                        rows.append((str(target.id), item))
        elif isinstance(node, ast.AnnAssign):
            if (
                isinstance(node.target, ast.Name)
                and node.target.id in value_attrs
                and node.value is not None
            ):
                for item in _extract_literal_string_values(node.value):
                    rows.append((str(node.target.id), item))
        elif isinstance(node, ast.FunctionDef) and node.name == "get_context_contract":
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Return) or not isinstance(sub.value, ast.Dict):
                    continue
                for key_node, value_node in zip(sub.value.keys, sub.value.values):
                    if key_node is None:
                        continue
                    key_name = _literal_str_value(key_node)
                    if key_name is None:
                        continue
                    group = _CONTRACT_DYNAMIC_FIELDS.get(key_name.strip())
                    if group is None:
                        continue
                    for item in _extract_literal_string_values(value_node):
                        rows.append((key_name.strip(), item))
    return rows


def _collect_declared_contract_keys(class_node: ast.ClassDef) -> dict[str, set[str]]:
    declared = {"requires": set(), "provides": set(), "mutates": set(), "cache": set()}
    for field_name, value in _iter_declared_contract_literals(class_node):
        group = _CONTRACT_DYNAMIC_FIELDS.get(field_name)
        if group is None:
            continue
        key = normalize_context_key(value)
        if key:
            declared[group].add(key)
    return declared


def _is_known_context_key(key: str) -> bool:
    text = str(key).strip().lower()
    if not text:
        return False
    if text in CANONICAL_CONTEXT_KEYS:
        return True
    if text.startswith("metrics."):
        return True
    return False


def _is_declared_key_covered(key: str, declared: set[str]) -> bool:
    text = str(key).strip().lower()
    if not text:
        return False
    if text in declared:
        return True
    if text.startswith("metrics.") and "metrics" in declared:
        return True
    return False


def _collect_context_aliases(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    aliases: set[str] = set()
    for arg in list(func_node.args.args) + list(func_node.args.kwonlyargs):
        if arg.arg in _CONTEXT_VAR_NAMES:
            aliases.add(str(arg.arg))
    if func_node.args.vararg is not None and func_node.args.vararg.arg in _CONTEXT_VAR_NAMES:
        aliases.add(str(func_node.args.vararg.arg))
    if func_node.args.kwarg is not None and func_node.args.kwarg.arg in _CONTEXT_VAR_NAMES:
        aliases.add(str(func_node.args.kwarg.arg))

    changed = True
    while changed:
        changed = False
        for node in ast.walk(func_node):
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name) and isinstance(node.value, ast.Name):
                    if node.value.id in aliases and target.id not in aliases:
                        aliases.add(str(target.id))
                        changed = True
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and isinstance(node.value, ast.Name):
                    if node.value.id in aliases and node.target.id not in aliases:
                        aliases.add(str(node.target.id))
                        changed = True
    return aliases


def _extract_context_subscript_key(node: ast.Subscript, aliases: set[str]) -> str | None:
    if not isinstance(node.value, ast.Name):
        return None
    if node.value.id not in aliases:
        return None
    key_text = _literal_str_value(node.slice)
    if key_text is None:
        return None
    normalized = normalize_context_key(key_text)
    return normalized or None


def _extract_call_key(call_node: ast.Call, arg_index: int = 0) -> str | None:
    if len(call_node.args) <= arg_index:
        return None
    key_text = _literal_str_value(call_node.args[arg_index])
    if key_text is None:
        return None
    normalized = normalize_context_key(key_text)
    return normalized or None


def _collect_target_context_writes(target: ast.expr, aliases: set[str], writes: set[str]) -> None:
    if isinstance(target, ast.Subscript):
        key = _extract_context_subscript_key(target, aliases)
        if key is not None:
            writes.add(key)
        return
    if isinstance(target, (ast.Tuple, ast.List)):
        for elt in target.elts:
            _collect_target_context_writes(elt, aliases, writes)


def _extract_context_reads_writes(class_node: ast.ClassDef) -> tuple[set[str], set[str]]:
    reads: set[str] = set()
    writes: set[str] = set()

    for node in class_node.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name == "get_context_contract":
            continue
        aliases = _collect_context_aliases(node)
        if not aliases:
            continue

        for sub in ast.walk(node):
            if isinstance(sub, ast.Assign):
                for target in sub.targets:
                    _collect_target_context_writes(target, aliases, writes)
            elif isinstance(sub, ast.AnnAssign):
                _collect_target_context_writes(sub.target, aliases, writes)
            elif isinstance(sub, ast.AugAssign):
                _collect_target_context_writes(sub.target, aliases, writes)
            elif isinstance(sub, ast.Delete):
                for target in sub.targets:
                    _collect_target_context_writes(target, aliases, writes)
            elif isinstance(sub, ast.Subscript):
                if isinstance(sub.ctx, ast.Load):
                    key = _extract_context_subscript_key(sub, aliases)
                    if key is not None:
                        reads.add(key)
            elif isinstance(sub, ast.Call):
                func = sub.func
                if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                    if func.value.id not in aliases:
                        continue
                    method = str(func.attr)
                    if method in {"get", "__getitem__"}:
                        key = _extract_call_key(sub, 0)
                        if key is not None:
                            reads.add(key)
                    elif method in {"pop", "setdefault", "__setitem__", "__delitem__"}:
                        key = _extract_call_key(sub, 0)
                        if key is not None:
                            reads.add(key)
                            writes.add(key)
                    elif method == "update":
                        if sub.args:
                            first = sub.args[0]
                            if isinstance(first, ast.Dict):
                                for key_node in first.keys:
                                    if key_node is None:
                                        continue
                                    key_text = _literal_str_value(key_node)
                                    if key_text is None:
                                        continue
                                    key = normalize_context_key(key_text)
                                    if key:
                                        writes.add(key)
                        for kw in sub.keywords:
                            if kw.arg is None:
                                continue
                            key = normalize_context_key(str(kw.arg))
                            if key:
                                writes.add(key)
    return reads, writes


def _iter_class_attr_values(class_node: ast.ClassDef, attr_name: str) -> List[ast.expr]:
    out: List[ast.expr] = []
    for node in class_node.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == attr_name:
                    out.append(node.value)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == attr_name and node.value is not None:
                out.append(node.value)
    return out


def _check_class_metrics_fallback_literal(
    class_node: ast.ClassDef,
    path: Path,
    diags: List[DoctorDiagnostic],
    *,
    strict: bool,
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
) -> None:
    values = _iter_class_attr_values(class_node, "metrics_fallback")
    if not values:
        return

    for value_node in values:
        literal = _literal_str_value(value_node)
        if literal is None:
            add(
                diags,
                "error" if strict else "warn",
                "metrics-fallback-nonliteral",
                f"Class {class_node.name} metrics_fallback must be a string literal enum value",
                path,
            )
            continue

        normalized = literal.strip().lower()
        if normalized not in _ALLOWED_METRICS_FALLBACK_VALUES:
            allowed = ", ".join(sorted(_ALLOWED_METRICS_FALLBACK_VALUES))
            add(
                diags,
                "error" if strict else "warn",
                "metrics-fallback-invalid",
                f"Class {class_node.name} has invalid metrics_fallback='{literal}' (allowed: {allowed})",
                path,
            )


def _base_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return str(node.id)
    if isinstance(node, ast.Attribute):
        return str(node.attr)
    return ""


def _is_component_class(class_node: ast.ClassDef) -> bool:
    if class_node.name.startswith("_"):
        return False
    if class_node.name.endswith(("Config", "Spec")):
        return False
    for base in class_node.bases:
        if _base_name(base) == "Protocol":
            return False
    if class_node.name.endswith(_COMPONENT_NAME_SUFFIXES):
        return True
    for base in class_node.bases:
        base_name = _base_name(base)
        if not base_name:
            continue
        if base_name in _COMPONENT_BASE_NAMES or base_name.endswith(_COMPONENT_NAME_SUFFIXES):
            return True
    return False


def _is_not_implemented_raise(node: ast.AST) -> bool:
    if not isinstance(node, ast.Raise):
        return False
    exc = node.exc
    if isinstance(exc, ast.Name):
        return exc.id == "NotImplementedError"
    if isinstance(exc, ast.Call):
        func = exc.func
        if isinstance(func, ast.Name):
            return func.id == "NotImplementedError"
        if isinstance(func, ast.Attribute):
            return str(func.attr) == "NotImplementedError"
    if isinstance(exc, ast.Attribute):
        return str(exc.attr) == "NotImplementedError"
    return False


def _has_abstractmethod_decorator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for deco in node.decorator_list:
        if isinstance(deco, ast.Name) and deco.id == "abstractmethod":
            return True
        if isinstance(deco, ast.Attribute) and deco.attr == "abstractmethod":
            return True
    return False


def _check_class_template_not_implemented(
    class_node: ast.ClassDef,
    path: Path,
    diags: List[DoctorDiagnostic],
    *,
    strict: bool,
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
) -> None:
    hits: List[str] = []
    for stmt in class_node.body:
        if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _has_abstractmethod_decorator(stmt):
            continue
        for n in ast.walk(stmt):
            if _is_not_implemented_raise(n):
                line = int(getattr(n, "lineno", getattr(stmt, "lineno", 0)) or 0)
                hits.append(f"{stmt.name}@L{line}")
                break
    if not hits:
        return
    add(
        diags,
        "error" if strict else "warn",
        "template-not-implemented",
        f"Class {class_node.name} has NotImplementedError placeholders (template incomplete): "
        + ", ".join(hits[:8])
        + (" ..." if len(hits) > 8 else ""),
        path,
    )


def _check_class_contract_key_known(
    class_node: ast.ClassDef,
    path: Path,
    diags: List[DoctorDiagnostic],
    *,
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
) -> None:
    unknown: List[str] = []
    for _, key_text in _iter_declared_contract_literals(class_node):
        key = normalize_context_key(key_text)
        if not key:
            continue
        if _is_known_context_key(key):
            continue
        unknown.append(key)
    if not unknown:
        return
    uniq = sorted(set(unknown))
    add(
        diags,
        "warn",
        "contract-key-unknown",
        (
            f"Class {class_node.name} declares non-canonical context keys: "
            + ", ".join(uniq[:12])
            + (" ..." if len(uniq) > 12 else "")
            + " (add to context_keys.py or use metrics.* namespace)."
        ),
        path,
    )


def _check_class_contract_impl_alignment(
    class_node: ast.ClassDef,
    path: Path,
    diags: List[DoctorDiagnostic],
    *,
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
) -> None:
    declared = _collect_declared_contract_keys(class_node)
    reads, writes = _extract_context_reads_writes(class_node)
    if not reads and not writes:
        return

    declared_read = set(declared["requires"]) | set(declared["provides"]) | set(declared["mutates"]) | set(
        declared["cache"]
    )
    declared_write = set(declared["provides"]) | set(declared["mutates"])

    undeclared_reads = sorted(k for k in reads if not _is_declared_key_covered(k, declared_read))
    undeclared_writes = sorted(k for k in writes if not _is_declared_key_covered(k, declared_write))

    if undeclared_reads or undeclared_writes:
        parts: List[str] = []
        if undeclared_reads:
            parts.append(
                "reads not declared: "
                + ", ".join(undeclared_reads[:10])
                + (" ..." if len(undeclared_reads) > 10 else "")
            )
        if undeclared_writes:
            parts.append(
                "writes not declared in provides/mutates: "
                + ", ".join(undeclared_writes[:10])
                + (" ..." if len(undeclared_writes) > 10 else "")
            )
        add(
            diags,
            "warn",
            "contract-impl-mismatch",
            f"Class {class_node.name} contract/implementation mismatch: " + " | ".join(parts),
            path,
        )

    large_writes = sorted(k for k in writes if k in _CONTEXT_LARGE_OBJECT_KEYS)
    if large_writes:
        add(
            diags,
            "warn",
            "context-large-object-write",
            (
                f"Class {class_node.name} writes large objects into context directly: "
                + ", ".join(large_writes[:8])
                + (" ..." if len(large_writes) > 8 else "")
                + ". Use SnapshotStore refs instead."
            ),
            path,
        )


def _class_defines_method(class_node: ast.ClassDef, name: str) -> bool:
    for node in class_node.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return True
    return False


def _check_class_state_recovery_declaration(
    class_node: ast.ClassDef,
    path: Path,
    diags: List[DoctorDiagnostic],
    *,
    strict: bool,
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
    state_recovery_levels: Set[str],
) -> None:
    has_get_state = _class_defines_method(class_node, "get_state")
    has_set_state = _class_defines_method(class_node, "set_state")
    if not (has_get_state or has_set_state):
        return

    if has_get_state != has_set_state:
        add(
            diags,
            "error" if strict else "warn",
            "state-roundtrip-asymmetric",
            (
                f"Class {class_node.name} should define symmetric get_state()/set_state() "
                "for checkpoint roundtrip."
            ),
            path,
        )

    values = _iter_class_attr_values(class_node, "state_recovery_level")
    if not values:
        add(
            diags,
            "error" if strict else "warn",
            "state-recovery-level-missing",
            (
                f"Class {class_node.name} defines state roundtrip but does not declare "
                "state_recovery_level (L0/L1/L2)."
            ),
            path,
        )
        return

    for value_node in values:
        literal = _literal_str_value(value_node)
        if literal is None:
            add(
                diags,
                "error" if strict else "warn",
                "state-recovery-level-invalid",
                (
                    f"Class {class_node.name} state_recovery_level must be a string literal "
                    "(L0/L1/L2)."
                ),
                path,
            )
            continue
        level = literal.strip().upper()
        if level not in state_recovery_levels:
            add(
                diags,
                "error" if strict else "warn",
                "state-recovery-level-invalid",
                (
                    f"Class {class_node.name} has invalid state_recovery_level='{literal}' "
                    f"(allowed: {', '.join(sorted(state_recovery_levels))})."
                ),
                path,
            )


def check_contract_source(
    *,
    root: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
    contract_check_dirs: Sequence[str],
    core_contract_keys: Set[str],
    runtime_state_fields: Set[str],
    plugin_state_fields: Set[str],
    forbidden_solver_mirror_attrs: Set[str],
    state_recovery_levels: Set[str],
) -> None:
    for folder_name in contract_check_dirs:
        folder = root / folder_name
        if not folder.is_dir():
            continue
        py_files = [path for path in folder.rglob("*.py") if path.name != "__init__.py"]
        for py_file in py_files:
            try:
                content = py_file.read_text(encoding="utf-8-sig")
                tree = ast.parse(content, filename=str(py_file))
            except Exception as exc:
                add(diags, "warn", "source-parse-failed", f"Cannot parse source file: {exc}", py_file)
                continue

            check_forbidden_solver_mirror_writes(
                tree=tree,
                path=py_file,
                diags=diags,
                strict=bool(strict),
                add=add,
                forbidden_solver_mirror_attrs=forbidden_solver_mirror_attrs,
            )
            check_runtime_private_calls(
                tree=tree,
                path=py_file,
                diags=diags,
                strict=bool(strict),
                add=add,
            )
            check_runtime_bypass_writes(
                tree=tree,
                path=py_file,
                diags=diags,
                strict=bool(strict),
                add=add,
                runtime_state_fields=runtime_state_fields,
            )
            if strict and folder_name == "plugins" and py_file.name != "base.py":
                check_plugin_solver_state_access(
                    tree=tree,
                    path=py_file,
                    diags=diags,
                    add=add,
                    plugin_state_fields=plugin_state_fields,
                )

            class_nodes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
            if not class_nodes:
                continue

            for class_node in class_nodes:
                if not _is_component_class(class_node):
                    continue
                _check_class_metrics_fallback_literal(class_node, py_file, diags, strict=bool(strict), add=add)
                _check_class_template_not_implemented(class_node, py_file, diags, strict=bool(strict), add=add)
                _check_class_contract_key_known(class_node, py_file, diags, add=add)
                _check_class_contract_impl_alignment(class_node, py_file, diags, add=add)
                _check_class_state_recovery_declaration(
                    class_node,
                    py_file,
                    diags,
                    strict=bool(strict),
                    add=add,
                    state_recovery_levels=state_recovery_levels,
                )
                if not _class_has_contract(class_node):
                    add(
                        diags,
                        "error" if strict else "warn",
                        "class-contract-missing",
                        f"Class {class_node.name} has no explicit context contract fields",
                        py_file,
                    )
                else:
                    missing_core = _class_missing_core_contract_fields(class_node, core_contract_keys=core_contract_keys)
                    if missing_core:
                        add(
                            diags,
                            "warn",
                            "class-contract-core-missing",
                            (
                                f"Class {class_node.name} should declare core contract keys: "
                                f"{', '.join(sorted(core_contract_keys))}; missing: {', '.join(missing_core)}"
                            ),
                            py_file,
                        )
