from __future__ import annotations

import inspect
from dataclasses import dataclass, replace
from typing import Iterable, Sequence, Tuple

from .contract_relations import _entry_field_values
from blackbase.context import get_component_contract
from .recipes import ADAPTER_RECIPES, constructor_check, required_arguments


@dataclass(frozen=True)
class CatalogUsage:
    use_when: Tuple[str, ...] = ()
    minimal_wiring: Tuple[str, ...] = ()
    required_companions: Tuple[str, ...] = ()
    config_keys: Tuple[str, ...] = ()
    example_entry: str = ""
    wiring_status: str = "unverified"
    wiring_notes: Tuple[str, ...] = ()


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
        "plugin": ("需要记录/审计/并行/评估增强等工程能力时",),
        "suite": ("想一键接入权威组合，避免漏配时",),
        "adapter": ("需要替换或新增搜索策略时",),
        "bias": ("需要表达软偏好或搜索倾向时",),
        "representation": ("需要控制初始化/变异/修复等表示逻辑时",),
        "tool": ("需要调用独立工具能力时",),
        "example": ("需要可运行参考实现时",),
    }
    return mapping.get(str(kind).strip().lower(), ())


def _infer_minimal_wiring(kind: str, import_path: str, entry=None) -> Tuple[str, ...]:
    symbol = _symbol_from_import(import_path)
    required = required_arguments(entry) if entry is not None else ()
    arguments = ", ".join(p.name if p.kind is inspect.Parameter.POSITIONAL_ONLY else f"{p.name}={p.name}" for p in required)
    constructor = f"{symbol}({arguments})"
    header = ("# template: 请先定义必填依赖 " + ", ".join(p.name for p in required),) if required else ()
    k = str(kind).strip().lower()
    if k == "plugin":
        return header + (
            f"from {import_path.split(':', 1)[0]} import {symbol}",
            f"solver.add_plugin({constructor})",
        )
    if k == "suite":
        return header + (
            f"from {import_path.split(':', 1)[0]} import {symbol}",
            f"{symbol}(solver)",
        )
    if k == "adapter":
        return header + (
            f"from {import_path.split(':', 1)[0]} import {symbol}",
            f"solver.set_adapter({constructor})",
        )
    if k == "bias":
        return header + (
            f"from {import_path.split(':', 1)[0]} import {symbol}",
            f"bias_module.add({constructor})",
        )
    if k == "representation":
        prefix = header + (f"from {import_path.split(':', 1)[0]} import {symbol}",)
        component = entry.load() if entry is not None else None
        if component is not None and hasattr(component, "schema") and hasattr(component, "restore"):
            return prefix + ("from nsgablack.units import UnitBinding", f"binding = UnitBinding({constructor})", "# 将 binding 传给支持该 Unit schema 的 Adapter")
        for method, slot in (("init", "initializer"), ("mutate", "mutator"), ("repair", "repair"), ("encode", "encoder"), ("decode", "decoder")):
            if callable(getattr(component, method, None)):
                return prefix + ("from nsgablack.representation import RepresentationPipeline", f"solver.set_representation_pipeline(RepresentationPipeline({slot}={constructor}))")
        return prefix + (f"component = {constructor}", "# 按组件角色接入 Case pipeline，不把原始组件当作完整管线")
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
        except (ValueError, TypeError):
            pass
    return tuple(params) if params else ("(none)",)


def _infer_example_entry(entry) -> str:
    explicit = str(getattr(entry, "example_entry", "") or "").strip()
    if explicit and "catalog search" not in explicit:
        return explicit
    if entry.key in ADAPTER_RECIPES:
        case = entry.key.split(".")[-1]
        return f"examples/cases/catalog_recipes/cases/{case}/build_solver.py"
    return "尚无已验证的专用 Case；通用装配见 docs/standard_scaffold_tutorial/01_create_and_run.md"


def build_usage_profile(entry) -> CatalogUsage:
    use_when = _normalize_values(getattr(entry, "use_when", ()))
    minimal_wiring = _normalize_values(getattr(entry, "minimal_wiring", ()))
    required_companions = _normalize_values(getattr(entry, "required_companions", ()))
    config_keys = _infer_config_keys(entry)
    example_entry = _infer_example_entry(entry)

    if not use_when:
        use_when = _infer_use_when(getattr(entry, "kind", ""))
    if entry.key in ADAPTER_RECIPES:
        minimal_wiring = ADAPTER_RECIPES[entry.key]
    if not minimal_wiring:
        minimal_wiring = _infer_minimal_wiring(getattr(entry, "kind", ""), getattr(entry, "import_path", ""), entry)
    status, notes = constructor_check(entry, minimal_wiring)
    if status == "invalid":
        minimal_wiring = _infer_minimal_wiring(entry.kind, entry.import_path, entry)
        status, notes = constructor_check(entry, minimal_wiring)
    if any("# template:" in line for line in minimal_wiring):
        status = "template"
        notes = ("必填依赖须由 Case 定义；片段尚未执行验收",)
    minimal_wiring = tuple(line for line in minimal_wiring if not line.startswith("# recipe-status:"))
    minimal_wiring = (f"# recipe-status: {status}; {'; '.join(notes)}", *minimal_wiring)
    if not required_companions:
        required_companions = _infer_required_companions(getattr(entry, "companions", ()))

    return CatalogUsage(
        use_when=use_when,
        minimal_wiring=minimal_wiring,
        required_companions=required_companions,
        config_keys=config_keys,
        example_entry=example_entry,
        wiring_status=status,
        wiring_notes=notes,
    )


def _callable_has_no_required_args(obj: object) -> bool:
    try:
        sig = inspect.signature(obj)
    except (ValueError, TypeError):
        return False
    for param in sig.parameters.values():
        if param.kind in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}:
            continue
        if param.default is inspect._empty:
            return False
    return True


def _load_runtime_context_contract(symbol: object):
    contract = get_component_contract(symbol)
    if contract is not None:
        return contract

    instance = None
    try:
        if inspect.isclass(symbol) and _callable_has_no_required_args(symbol):
            instance = symbol()
        elif callable(symbol) and _callable_has_no_required_args(symbol):
            instance = symbol()
    except Exception:
        instance = None

    if instance is None:
        return None
    return get_component_contract(instance)


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
        artifact_requires = _normalize_values(getattr(entry, "artifact_requires", ()))
        artifact_provides = _normalize_values(getattr(entry, "artifact_provides", ()))
        phase_in = _normalize_values(getattr(entry, "phase_in", ()))
        phase_out = _normalize_values(getattr(entry, "phase_out", ()))

        if req and prov and mut and cache and notes and artifact_requires and artifact_provides and phase_in and phase_out:
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
            if not artifact_requires:
                artifact_requires = _normalize_values(getattr(symbol, "artifact_requires", ()))
            if not artifact_provides:
                artifact_provides = _normalize_values(getattr(symbol, "artifact_provides", ()))
            if not phase_in:
                phase_in = _normalize_values(getattr(symbol, "phase_in", ()))
            if not phase_out:
                phase_out = _normalize_values(getattr(symbol, "phase_out", ()))
            if not (req and prov and mut and cache and notes):
                runtime_contract = _load_runtime_context_contract(symbol)
                if runtime_contract is not None:
                    if not req:
                        req = _normalize_values(runtime_contract.requires)
                    if not prov:
                        prov = _normalize_values(runtime_contract.provides)
                    if not mut:
                        mut = _normalize_values(runtime_contract.mutates)
                    if not cache:
                        cache = _normalize_values(runtime_contract.cache)
                    if not artifact_requires:
                        artifact_requires = _normalize_values(getattr(runtime_contract, "artifact_requires", ()))
                    if not artifact_provides:
                        artifact_provides = _normalize_values(getattr(runtime_contract, "artifact_provides", ()))
                    if not phase_in:
                        phase_in = _normalize_values(getattr(runtime_contract, "phase_in", ()))
                    if not phase_out:
                        phase_out = _normalize_values(getattr(runtime_contract, "phase_out", ()))
                    if not notes:
                        notes = _normalize_context_notes(runtime_contract.notes)

        base_entry = replace(
            entry,
            context_requires=tuple(req),
            context_provides=tuple(prov),
            context_mutates=tuple(mut),
            context_cache=tuple(cache),
            context_notes=tuple(notes),
        )
        out.append(
            replace(
                base_entry,
                artifact_requires=artifact_requires or _entry_field_values(base_entry, "artifact_requires"),
                artifact_provides=artifact_provides or _entry_field_values(base_entry, "artifact_provides"),
                phase_in=phase_in or _entry_field_values(base_entry, "phase_in"),
                phase_out=phase_out or _entry_field_values(base_entry, "phase_out"),
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
