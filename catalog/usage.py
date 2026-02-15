from __future__ import annotations

import inspect
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable, Sequence, Tuple


@dataclass(frozen=True)
class CatalogUsage:
    use_when: Tuple[str, ...] = ()
    minimal_wiring: Tuple[str, ...] = ()
    required_companions: Tuple[str, ...] = ()
    config_keys: Tuple[str, ...] = ()
    example_entry: str = ""


def _normalize_values(values: object) -> Tuple[str, ...]:
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


def _symbol_from_import(import_path: str) -> str:
    _, _, sym = str(import_path).partition(":")
    if not sym:
        return "Component"
    return sym.split(".")[-1] or "Component"


def _normalize_context_notes(value: object) -> Tuple[str, ...]:
    vals = _normalize_values(value)
    if vals:
        return vals
    if value is None:
        return ()
    if isinstance(value, (list, tuple, set, dict)) and not value:
        return ()
    text = str(value).strip()
    return (text,) if text else ()


def _infer_use_when(kind: str) -> Tuple[str, ...]:
    mapping = {
        "plugin": ("需要记录/审查/并行/评估增强等工程能力时",),
        "suite": ("想一键接入权威组合，避免漏配时",),
        "adapter": ("需要替换或新增搜索策略时",),
        "bias": ("需要表达软偏好或搜索倾向时",),
        "representation": ("需要控制初始化/变异/修复等表示逻辑时",),
        "tool": ("需要调用独立工具能力时",),
        "example": ("需要可运行参考实现时",),
    }
    return mapping.get(str(kind).strip().lower(), ())


def _infer_minimal_wiring(kind: str, import_path: str) -> Tuple[str, ...]:
    symbol = _symbol_from_import(import_path)
    k = str(kind).strip().lower()
    if k == "plugin":
        return (
            f"from {import_path.split(':', 1)[0]} import {symbol}",
            "solver.add_plugin(" + symbol + "())",
        )
    if k == "suite":
        return (
            f"from {import_path.split(':', 1)[0]} import {symbol}",
            f"{symbol}(solver)",
        )
    if k == "adapter":
        return (
            f"from {import_path.split(':', 1)[0]} import {symbol}",
            f"solver.adapter = {symbol}()",
        )
    if k == "bias":
        return (
            f"from {import_path.split(':', 1)[0]} import {symbol}",
            f"bias_module.add({symbol}())",
        )
    if k == "representation":
        return (
            f"from {import_path.split(':', 1)[0]} import {symbol}",
            "solver.set_representation_pipeline(" + symbol + "())",
        )
    return (f"from {import_path.split(':', 1)[0]} import {symbol}",)


def _infer_required_companions(companions: Iterable[str]) -> Tuple[str, ...]:
    vals = tuple(str(c).strip() for c in companions if str(c).strip())
    return vals if vals else ("(none)",)


def _infer_config_keys(entry) -> Tuple[str, ...]:
    explicit = _normalize_values(getattr(entry, "config_keys", ()))
    if explicit:
        return explicit
    try:
        symbol = entry.load()
    except Exception:
        symbol = None
    params: list[str] = []
    if symbol is not None:
        try:
            if inspect.isclass(symbol):
                sig = inspect.signature(symbol.__init__)
            else:
                sig = inspect.signature(symbol)
            for name, p in sig.parameters.items():
                if name in {"self", "cls", "solver", "problem", "bias_module"}:
                    continue
                if p.kind in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}:
                    continue
                params.append(name)
        except Exception:
            pass
    return tuple(params) if params else ("(none)",)


def _infer_example_entry(entry) -> str:
    explicit = str(getattr(entry, "example_entry", "") or "").strip()
    if explicit:
        return explicit

    import_path = str(getattr(entry, "import_path", "") or "")
    module_path, _, sym = import_path.partition(":")
    if module_path == "nsgablack.examples_registry" and sym:
        try:
            fn = entry.load()
            if callable(fn):
                path = str(fn() or "").strip()
                if path:
                    p = Path(path)
                    if p.suffix == ".py":
                        return f"{path}:build_solver"
                    return path
        except Exception:
            pass

    key = str(getattr(entry, "key", "") or "")
    token = key.split(".")[-1] if "." in key else key
    token = token.strip()
    if token:
        return f"python -m nsgablack catalog search {token} --kind example"
    return "python -m nsgablack catalog search <keyword> --kind example"


def build_usage_profile(entry) -> CatalogUsage:
    use_when = _normalize_values(getattr(entry, "use_when", ()))
    minimal_wiring = _normalize_values(getattr(entry, "minimal_wiring", ()))
    required_companions = _normalize_values(getattr(entry, "required_companions", ()))
    config_keys = _infer_config_keys(entry)
    example_entry = _infer_example_entry(entry)

    if not use_when:
        use_when = _infer_use_when(getattr(entry, "kind", ""))
    if not minimal_wiring:
        minimal_wiring = _infer_minimal_wiring(getattr(entry, "kind", ""), getattr(entry, "import_path", ""))
    if not required_companions:
        required_companions = _infer_required_companions(getattr(entry, "companions", ()))

    return CatalogUsage(
        use_when=use_when,
        minimal_wiring=minimal_wiring,
        required_companions=required_companions,
        config_keys=config_keys,
        example_entry=example_entry,
    )


def enrich_context_contracts(entries: Sequence, *, kinds: Sequence[str] = ("plugin",)) -> list:
    """Fill missing context_* fields from symbol class-level declarations."""
    target_kinds = {str(k).strip().lower() for k in kinds if str(k).strip()}
    out = []
    for entry in entries:
        if target_kinds and str(getattr(entry, "kind", "")).strip().lower() not in target_kinds:
            out.append(entry)
            continue

        req = _normalize_values(getattr(entry, "context_requires", ()))
        prov = _normalize_values(getattr(entry, "context_provides", ()))
        mut = _normalize_values(getattr(entry, "context_mutates", ()))
        cache = _normalize_values(getattr(entry, "context_cache", ()))
        notes = _normalize_context_notes(getattr(entry, "context_notes", ()))

        if req and prov and mut and cache and notes:
            out.append(entry)
            continue

        try:
            symbol = entry.load()
        except Exception:
            symbol = None

        if symbol is not None:
            if not req:
                req = _normalize_values(getattr(symbol, "context_requires", ()))
            if not prov:
                prov = _normalize_values(getattr(symbol, "context_provides", ()))
            if not mut:
                mut = _normalize_values(getattr(symbol, "context_mutates", ()))
            if not cache:
                cache = _normalize_values(getattr(symbol, "context_cache", ()))
            if not notes:
                notes = _normalize_context_notes(getattr(symbol, "context_notes", ()))

        out.append(
            replace(
                entry,
                context_requires=tuple(req),
                context_provides=tuple(prov),
                context_mutates=tuple(mut),
                context_cache=tuple(cache),
                context_notes=tuple(notes),
            )
        )
    return out


def enrich_usage_contracts(entries: Sequence) -> list:
    out = []
    for entry in entries:
        usage = build_usage_profile(entry)
        out.append(
            replace(
                entry,
                use_when=tuple(usage.use_when),
                minimal_wiring=tuple(usage.minimal_wiring),
                required_companions=tuple(usage.required_companions),
                config_keys=tuple(usage.config_keys),
                example_entry=str(usage.example_entry),
            )
        )
    return out
