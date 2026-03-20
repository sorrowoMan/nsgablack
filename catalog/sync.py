from __future__ import annotations

import ast
import importlib.util
import inspect
import os
from dataclasses import fields, is_dataclass
from dataclasses import MISSING as _DC_MISSING
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .contracts import (
    CatalogBundle,
    CatalogComponentContract,
    ContextContract,
    HealthContract,
    MethodContract,
    ParamContract,
    UsageContract,
)
from .registry import CatalogEntry, get_catalog
from .usage import build_usage_profile
from ..utils.context.context_keys import CANONICAL_CONTEXT_KEYS


_ADAPTER_REQUIRED = ("propose", "update")
_ADAPTER_OPTIONAL = ("get_state", "set_state", "get_population", "set_population")
_PLUGIN_METHODS = (
    "on_solver_init",
    "on_population_init",
    "on_generation_start",
    "on_step",
    "on_generation_end",
    "on_solver_finish",
)
_REPRESENTATION_METHODS = ("init", "mutate", "repair", "encode", "decode")


def _coerce_tuple(values: object) -> Tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        text = values.strip()
        return (text,) if text else ()
    if isinstance(values, (list, tuple, set)):
        out = []
        for item in values:
            text = str(item).strip()
            if text:
                out.append(text)
        return tuple(out)
    text = str(values).strip()
    return (text,) if text else ()


def _safe_unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node).strip()
    except Exception:
        return ""


def _format_type(tp: object) -> str:
    if tp is None:
        return ""
    if tp is inspect._empty:
        return ""
    try:
        origin = getattr(tp, "__origin__", None)
        args = getattr(tp, "__args__", None)
        if origin is None:
            return str(tp)
        if not args:
            return str(origin)
        return f"{origin}[{', '.join(str(a) for a in args)}]"
    except Exception:
        return str(tp)


def _parse_field_call(node: ast.Call) -> tuple[str, bool, str]:
    default = ""
    required = True
    desc = ""
    for kw in node.keywords:
        if kw.arg == "default":
            default = _safe_unparse(kw.value)
            required = False
        if kw.arg == "default_factory":
            default = "<factory>"
            required = False
        if kw.arg == "metadata" and isinstance(kw.value, ast.Dict):
            for k, v in zip(kw.value.keys, kw.value.values):
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    key = k.value.strip().lower()
                    if key in {"desc", "description", "help"}:
                        if isinstance(v, ast.Constant) and isinstance(v.value, str):
                            desc = v.value.strip()
                        else:
                            desc = _safe_unparse(v)
    return default, required, desc


def _find_module_source(import_path: str) -> tuple[Optional[Path], str]:
    mod_path, _, symbol = str(import_path).partition(":")
    if not mod_path or not symbol:
        return None, ""
    try:
        spec = importlib.util.find_spec(mod_path)
    except Exception:
        spec = None
    if spec is None or not spec.origin:
        return None, symbol
    path = Path(spec.origin)
    if not path.exists() or path.suffix.lower() != ".py":
        return None, symbol
    return path, symbol.split(".")[-1]


def _load_module_ast(path: Path) -> ast.Module:
    src = path.read_text(encoding="utf-8", errors="replace")
    return ast.parse(src, filename=str(path))


def _collect_dataclass_fields(tree: ast.Module) -> Dict[str, List[ParamContract]]:
    out: Dict[str, List[ParamContract]] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if not any(_decorator_name(d).endswith("dataclass") for d in node.decorator_list):
            continue
        fields_list: List[ParamContract] = []
        order_index = 0
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                name = stmt.target.id
                annotation = _safe_unparse(stmt.annotation)
                default = ""
                required = True
                desc = ""
                if stmt.value is not None:
                    if isinstance(stmt.value, ast.Call) and _safe_unparse(stmt.value.func) in {"field", "dataclasses.field"}:
                        default, required, desc = _parse_field_call(stmt.value)
                    else:
                        default = _safe_unparse(stmt.value)
                        required = False
                fields_list.append(
                    ParamContract(
                        component_key="",
                        name=name,
                        type=annotation,
                        default=default,
                        required=required,
                        desc=desc,
                        source="config_class",
                        order_index=order_index,
                    )
                )
                order_index += 1
            elif isinstance(stmt, ast.Assign):
                if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
                    continue
                name = stmt.targets[0].id
                default = _safe_unparse(stmt.value)
                fields_list.append(
                    ParamContract(
                        component_key="",
                        name=name,
                        type="",
                        default=default,
                        required=False,
                        desc="",
                        source="config_class",
                        order_index=order_index,
                    )
                )
                order_index += 1
        if fields_list:
            out[node.name] = fields_list
    return out


def _decorator_name(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _find_class_node(tree: ast.Module, name: str) -> Optional[ast.ClassDef]:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    return None


def _find_init_node(class_node: ast.ClassDef) -> Optional[ast.FunctionDef]:
    for node in class_node.body:
        if isinstance(node, ast.FunctionDef) and node.name == "__init__":
            return node
    return None


def _extract_config_class_name(init_node: ast.FunctionDef) -> Optional[str]:
    for arg in init_node.args.args:
        if arg.arg in {"config", "cfg"}:
            if arg.annotation and isinstance(arg.annotation, ast.Name):
                if arg.annotation.id.endswith("Config"):
                    return arg.annotation.id
    for default in init_node.args.defaults:
        if isinstance(default, ast.Call) and isinstance(default.func, ast.Name):
            if default.func.id.endswith("Config"):
                return default.func.id
    return None


def _extract_params_from_ast(entry: CatalogEntry) -> list[ParamContract]:
    path, symbol = _find_module_source(entry.import_path)
    if path is None or not symbol:
        return []
    try:
        tree = _load_module_ast(path)
    except Exception:
        return []

    dataclass_fields = _collect_dataclass_fields(tree)
    class_node = _find_class_node(tree, symbol)
    if class_node is None:
        return []

    init_node = _find_init_node(class_node)
    if init_node is None:
        return []

    config_name = _extract_config_class_name(init_node)
    if config_name and config_name in dataclass_fields:
        return dataclass_fields[config_name]

    params: List[ParamContract] = []
    order_index = 0
    defaults = list(init_node.args.defaults or [])
    arg_names = [a.arg for a in init_node.args.args]
    if arg_names and arg_names[0] == "self":
        arg_names = arg_names[1:]
    default_offset = len(arg_names) - len(defaults)
    for idx, name in enumerate(arg_names):
        if name in {"solver", "problem", "bias_module"}:
            continue
        annotation = ""
        for arg in init_node.args.args:
            if arg.arg == name and arg.annotation is not None:
                annotation = _safe_unparse(arg.annotation)
                break
        default = ""
        has_default = idx >= default_offset
        if has_default:
            default = _safe_unparse(defaults[idx - default_offset])
        params.append(
            ParamContract(
                component_key="",
                name=name,
                type=annotation,
                default=default,
                required=not has_default,
                desc="",
                source="signature",
                order_index=order_index,
            )
        )
        order_index += 1
    return params


def _extract_params_runtime(entry: CatalogEntry) -> list[ParamContract]:
    try:
        symbol = entry.load()
    except Exception:
        return []

    if inspect.isclass(symbol):
        init_fn = getattr(symbol, "__init__", None)
        if init_fn is None:
            return []
        sig = inspect.signature(init_fn)
        config_cls = None
        for name, param in sig.parameters.items():
            if name in {"self"}:
                continue
            if name in {"config", "cfg"}:
                ann = param.annotation
                if ann is not inspect._empty and is_dataclass(ann):
                    config_cls = ann
                elif param.default is not inspect._empty and is_dataclass(param.default):
                    config_cls = param.default.__class__
        if config_cls is not None:
            params: List[ParamContract] = []
            for idx, field in enumerate(fields(config_cls)):
                default = ""
                required = True
                if field.default is not _DC_MISSING:
                    default = repr(field.default)
                    required = False
                elif field.default_factory is not _DC_MISSING:  # type: ignore
                    default = "<factory>"
                    required = False
                desc = ""
                if field.metadata:
                    for key in ("desc", "description", "help"):
                        if key in field.metadata:
                            desc = str(field.metadata[key])
                            break
                params.append(
                    ParamContract(
                        component_key="",
                        name=field.name,
                        type=_format_type(field.type),
                        default=default,
                        required=required,
                        desc=desc,
                        source="config_class",
                        order_index=idx,
                    )
                )
            return params

        params = []
        idx = 0
        for name, param in sig.parameters.items():
            if name in {"self", "solver", "problem", "bias_module"}:
                continue
            if param.kind in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}:
                continue
            default = "" if param.default is inspect._empty else repr(param.default)
            params.append(
                ParamContract(
                    component_key="",
                    name=name,
                    type=_format_type(param.annotation),
                    default=default,
                    required=param.default is inspect._empty,
                    desc="",
                    source="signature",
                    order_index=idx,
                )
            )
            idx += 1
        return params

    if callable(symbol):
        sig = inspect.signature(symbol)
        params = []
        idx = 0
        for name, param in sig.parameters.items():
            if name in {"self", "solver", "problem", "bias_module"}:
                continue
            if param.kind in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}:
                continue
            default = "" if param.default is inspect._empty else repr(param.default)
            params.append(
                ParamContract(
                    component_key="",
                    name=name,
                    type=_format_type(param.annotation),
                    default=default,
                    required=param.default is inspect._empty,
                    desc="",
                    source="signature",
                    order_index=idx,
                )
            )
            idx += 1
        return params
    return []


def _extract_methods_ast(
    entry: CatalogEntry,
    method_names: Sequence[str],
    required_set: Sequence[str],
) -> List[MethodContract]:
    path, symbol = _find_module_source(entry.import_path)
    if path is None or not symbol:
        return []
    try:
        tree = _load_module_ast(path)
    except Exception:
        return []
    class_node = _find_class_node(tree, symbol)
    if class_node is None:
        return []
    methods: Dict[str, ast.FunctionDef] = {}
    for node in class_node.body:
        if isinstance(node, ast.FunctionDef):
            methods[node.name] = node
    out: List[MethodContract] = []
    required_names = set(required_set)
    for name in method_names:
        node = methods.get(name)
        implemented = node is not None
        signature = ""
        if node is not None:
            args = node.args
            arg_names = [a.arg for a in args.args]
            if arg_names and arg_names[0] == "self":
                arg_names = arg_names[1:]
            signature = f"{name}({', '.join(arg_names)})"
        out.append(
            MethodContract(
                component_key="",
                name=name,
                required=name in required_names,
                implemented=implemented,
                signature=signature,
                origin="local" if implemented else "missing",
            )
        )
    return out


def _extract_methods_runtime(
    entry: CatalogEntry,
    method_names: Sequence[str],
    required_set: Sequence[str],
) -> List[MethodContract]:
    try:
        symbol = entry.load()
    except Exception:
        return []
    if not inspect.isclass(symbol):
        return []
    out: List[MethodContract] = []
    required_names = set(required_set)
    for name in method_names:
        fn = getattr(symbol, name, None)
        implemented = callable(fn)
        origin = "missing"
        signature = ""
        if implemented:
            try:
                signature = str(inspect.signature(fn))
            except Exception:
                signature = ""
            qual = getattr(fn, "__qualname__", "")
            origin = "override" if qual.startswith(symbol.__name__ + ".") else "inherited"
        out.append(
            MethodContract(
                component_key="",
                name=name,
                required=name in required_names,
                implemented=implemented,
                signature=signature,
                origin=origin,
            )
        )
    return out


def _validate_context_keys(values: Iterable[str]) -> Tuple[bool, List[str]]:
    unknown = [k for k in values if k and k not in CANONICAL_CONTEXT_KEYS]
    return (len(unknown) == 0, unknown)


def _build_component(entry: CatalogEntry) -> CatalogComponentContract:
    return CatalogComponentContract(
        key=entry.key,
        kind=entry.kind,
        title=entry.title,
        import_path=entry.import_path,
        summary=entry.summary or "",
        tags=tuple(entry.tags or ()),
        companions=tuple(entry.companions or ()),
        source_scope="framework",
        source_hash=os.environ.get("NSGABLACK_CATALOG_SOURCE_HASH", "").strip(),
    )


def _build_context_contract(entry: CatalogEntry) -> ContextContract:
    return ContextContract(
        component_key=entry.key,
        requires=_coerce_tuple(getattr(entry, "context_requires", ())),
        provides=_coerce_tuple(getattr(entry, "context_provides", ())),
        mutates=_coerce_tuple(getattr(entry, "context_mutates", ())),
        cache=_coerce_tuple(getattr(entry, "context_cache", ())),
        notes=_coerce_tuple(getattr(entry, "context_notes", ())),
    )


def _build_usage_contract(entry: CatalogEntry) -> UsageContract:
    usage = build_usage_profile(entry)
    return UsageContract(
        component_key=entry.key,
        use_when=tuple(usage.use_when),
        minimal_wiring=tuple(usage.minimal_wiring),
        required_companions=tuple(usage.required_companions),
        config_keys=tuple(usage.config_keys),
        example_entry=str(usage.example_entry),
    )


def _extract_params(entry: CatalogEntry, *, runtime: bool) -> List[ParamContract]:
    if runtime:
        return _extract_params_runtime(entry)
    return _extract_params_from_ast(entry)


def _extract_methods(entry: CatalogEntry, *, runtime: bool) -> List[MethodContract]:
    method_names: Sequence[str] = ()
    required: Sequence[str] = ()
    if entry.kind == "adapter":
        method_names = _ADAPTER_REQUIRED + _ADAPTER_OPTIONAL
        required = _ADAPTER_REQUIRED
    elif entry.kind == "plugin":
        method_names = _PLUGIN_METHODS
    elif entry.kind == "representation":
        method_names = _REPRESENTATION_METHODS
    if not method_names:
        return []
    if runtime:
        return _extract_methods_runtime(entry, method_names, required)
    return _extract_methods_ast(entry, method_names, required)


def _build_health(
    entry: CatalogEntry,
    params: Sequence[ParamContract],
    methods: Sequence[MethodContract],
    context: ContextContract,
    *,
    runtime: bool,
) -> HealthContract:
    issues: List[str] = []
    import_ok = True
    if runtime:
        try:
            entry.load()
        except Exception as exc:
            import_ok = False
            issues.append(f"import_error: {exc}")

    context_values = list(context.requires + context.provides + context.mutates + context.cache)
    context_ok, unknown = _validate_context_keys(context_values)
    if not context_ok:
        issues.append(f"context_unknown_keys: {', '.join(unknown)}")

    methods_ok = True
    if entry.kind == "adapter":
        missing = [m.name for m in methods if m.name in _ADAPTER_REQUIRED and not m.implemented]
        if missing:
            methods_ok = False
            issues.append(f"missing_methods: {', '.join(missing)}")

    params_ok = True
    if not params and entry.kind in {"adapter", "plugin", "representation"}:
        params_ok = True

    return HealthContract(
        component_key=entry.key,
        import_ok=import_ok,
        context_ok=context_ok,
        methods_ok=methods_ok,
        params_ok=params_ok,
        issues=tuple(issues),
    )


def build_catalog_bundle(*, profile: str, runtime: bool = False) -> CatalogBundle:
    c = get_catalog(profile=profile)
    entries = c.list()
    components: List[CatalogComponentContract] = []
    contexts: List[ContextContract] = []
    usages: List[UsageContract] = []
    params: List[ParamContract] = []
    methods: List[MethodContract] = []
    health: List[HealthContract] = []

    for entry in entries:
        components.append(_build_component(entry))
        context = _build_context_contract(entry)
        contexts.append(context)
        usages.append(_build_usage_contract(entry))

        entry_params = _extract_params(entry, runtime=runtime)
        entry_methods = _extract_methods(entry, runtime=runtime)

        for p in entry_params:
            params.append(
                ParamContract(
                    component_key=entry.key,
                    name=p.name,
                    type=p.type,
                    default=p.default,
                    required=p.required,
                    desc=p.desc,
                    source=p.source,
                    order_index=p.order_index,
                )
            )
        for m in entry_methods:
            methods.append(
                MethodContract(
                    component_key=entry.key,
                    name=m.name,
                    required=m.required,
                    implemented=m.implemented,
                    signature=m.signature,
                    origin=m.origin,
                )
            )

        health.append(_build_health(entry, entry_params, entry_methods, context, runtime=runtime))

    return CatalogBundle(
        components=components,
        contexts=contexts,
        usages=usages,
        params=params,
        methods=methods,
        health=health,
    )
