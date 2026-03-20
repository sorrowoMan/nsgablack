from __future__ import annotations

import json
import ast
from pathlib import Path
from typing import List, Optional, Tuple

from .contracts import ApiDocEntry, ApiDocGap
from .store.mysql import MySQLCatalogStore, mysql_config_enabled


def _profile_label(profile: str) -> str:
    return str(profile or "default").strip().lower() or "default"


def get_api_doc_entry_from_mysql(
    *,
    profile: str,
    module: str,
    class_name: str,
    method_name: str,
) -> Optional[ApiDocEntry]:
    if not mysql_config_enabled():
        raise RuntimeError("MySQL catalog is not configured for API doc lookup.")
    store = MySQLCatalogStore(readonly=True)
    return store.get_api_doc_entry(
        profile=_profile_label(profile),
        module=module,
        class_name=class_name,
        method_name=method_name,
    )


def list_api_doc_gaps_from_mysql(*, profile: str, limit: int = 200) -> List[ApiDocGap]:
    if not mysql_config_enabled():
        raise RuntimeError("MySQL catalog is not configured for API doc gap scan.")
    store = MySQLCatalogStore(readonly=True)
    return store.list_api_doc_gaps(profile=_profile_label(profile), limit=limit)


def _coerce_params_json(payload: dict) -> str:
    if "params_json" in payload:
        return str(payload.get("params_json") or "").strip()
    params = payload.get("params")
    if params is None:
        return ""
    try:
        return json.dumps(params, ensure_ascii=False)
    except Exception:
        return ""


def import_api_doc_jsonl(*, profile: str, path: Path) -> int:
    if not mysql_config_enabled():
        raise RuntimeError("MySQL catalog is not configured for API doc import.")
    prof = _profile_label(profile)
    entries: List[ApiDocEntry] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        module = str(payload.get("module", "")).strip()
        class_name = str(payload.get("class_name", payload.get("class", "")) or "").strip()
        method_name = str(payload.get("method_name", payload.get("method", "")) or "").strip()
        if not module or not method_name:
            continue
        if not class_name:
            class_name = "(module)"
        auto_fields = payload.get("auto_fields")
        if isinstance(auto_fields, (list, tuple)):
            auto_fields_tuple: Tuple[str, ...] = tuple(str(x) for x in auto_fields if str(x).strip())
        else:
            auto_fields_tuple = ()
        entries.append(
            ApiDocEntry(
                profile=prof,
                module=module,
                class_name=class_name,
                method_name=method_name,
                params_json=_coerce_params_json(payload),
                boundaries=str(payload.get("boundaries", "") or "").strip(),
                side_effects=str(payload.get("side_effects", "") or "").strip(),
                lifecycle=str(payload.get("lifecycle", "") or "").strip(),
                notes=str(payload.get("notes", "") or "").strip(),
                auto_fields=auto_fields_tuple,
            )
        )

    if not entries:
        return 0
    store = MySQLCatalogStore()
    store.upsert_api_docs(entries, profile=prof)
    return len(entries)


def export_api_doc_template(*, profile: str, path: Path, limit: int = 200) -> int:
    if not mysql_config_enabled():
        raise RuntimeError("MySQL catalog is not configured for API doc export.")
    prof = _profile_label(profile)
    store = MySQLCatalogStore(readonly=True)
    gaps = store.list_api_doc_gaps(profile=prof, limit=limit)
    if not gaps:
        path.write_text("", encoding="utf-8")
        return 0

    lines: List[str] = []
    for gap in gaps:
        payload = {
            "profile": gap.profile,
            "module": gap.module,
            "class_name": gap.class_name,
            "method_name": gap.method_name,
            "missing_fields": list(gap.missing_fields),
            "auto_fields": [],
            "params": [],
            "boundaries": "",
            "side_effects": "",
            "lifecycle": "",
            "notes": "",
        }
        lines.append(json.dumps(payload, ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


def _safe_unparse(node: Optional[ast.AST]) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node).strip()
    except Exception:
        return ""


def _load_ast(path: Path) -> Optional[ast.Module]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
    try:
        return ast.parse(text, filename=str(path))
    except SyntaxError:
        return None


def _find_method_node(tree: ast.Module, class_name: str, method_name: str) -> Optional[ast.FunctionDef]:
    if class_name == "(module)":
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == method_name:
                return node  # type: ignore[return-value]
        return None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for stmt in node.body:
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name == method_name:
                    return stmt  # type: ignore[return-value]
    return None


def _extract_params(fn: ast.FunctionDef, *, drop_self: bool) -> List[dict]:
    args = fn.args
    params: List[dict] = []

    posonly = list(args.posonlyargs or [])
    normal = list(args.args or [])
    if drop_self and normal and normal[0].arg in {"self", "cls"}:
        normal = normal[1:]
    all_pos = posonly + normal
    defaults = list(args.defaults or [])
    defaults_map: dict[int, ast.AST] = {}
    if defaults:
        start = len(all_pos) - len(defaults)
        for idx, node in enumerate(defaults):
            defaults_map[start + idx] = node

    for idx, node in enumerate(posonly):
        params.append(
            {
                "name": node.arg,
                "kind": "positional_only",
                "default": _safe_unparse(defaults_map.get(idx)),
                "annotation": _safe_unparse(node.annotation),
            }
        )
    for offset, node in enumerate(normal):
        idx = len(posonly) + offset
        params.append(
            {
                "name": node.arg,
                "kind": "positional_or_keyword",
                "default": _safe_unparse(defaults_map.get(idx)),
                "annotation": _safe_unparse(node.annotation),
            }
        )

    if args.vararg is not None:
        params.append(
            {
                "name": args.vararg.arg,
                "kind": "var_positional",
                "default": "",
                "annotation": _safe_unparse(args.vararg.annotation),
            }
        )

    kwonly_defaults = list(args.kw_defaults or [])
    for idx, node in enumerate(args.kwonlyargs or []):
        default_node = kwonly_defaults[idx] if idx < len(kwonly_defaults) else None
        params.append(
            {
                "name": node.arg,
                "kind": "keyword_only",
                "default": _safe_unparse(default_node),
                "annotation": _safe_unparse(node.annotation),
            }
        )

    if args.kwarg is not None:
        params.append(
            {
                "name": args.kwarg.arg,
                "kind": "var_keyword",
                "default": "",
                "annotation": _safe_unparse(args.kwarg.annotation),
            }
        )

    return params


def _auto_lifecycle(method_name: str) -> str:
    if method_name.startswith("on_"):
        return "插件生命周期钩子（自动推断）"
    if method_name in {"setup", "teardown"}:
        return "生命周期阶段：初始化/收尾（自动推断）"
    if method_name in {"run", "step"}:
        return "生命周期阶段：运行主循环（自动推断）"
    if method_name in {"propose", "update"}:
        return "算法策略阶段：候选生成/反馈更新（自动推断）"
    if method_name.startswith("evaluate_"):
        return "评估阶段（自动推断）"
    return ""


def _auto_side_effects(method_name: str) -> str:
    if method_name.startswith(("get_", "list_", "read_")):
        return "读取状态/配置，不应产生写入副作用（自动推断）"
    if method_name.startswith(("set_", "update_")):
        return "更新配置或运行态（自动推断）"
    if method_name.startswith(("add_", "remove_", "register_")):
        return "修改注册表或容器内容（自动推断）"
    if method_name.startswith(("write_", "save_")):
        return "写入持久化或快照（自动推断）"
    if method_name.startswith(("build_", "create_", "init_")):
        return "构造或初始化对象/状态（自动推断）"
    if method_name.startswith("on_"):
        return "通常以观察/记录为主，避免重写主流程（自动推断）"
    return ""


def _auto_boundaries(method_name: str) -> str:
    if method_name.startswith("evaluate_"):
        return "需返回合法 shape；异常时由上层 fallback 处理（自动推断）"
    if method_name in {"propose", "update"}:
        return "不负责目标评估，仅生成候选/吸收反馈（自动推断）"
    if method_name.startswith("on_"):
        return "应保持轻量，不阻断主流程（自动推断）"
    if method_name.startswith("get_"):
        return "仅负责读取，不保证线程安全（自动推断）"
    if method_name.startswith("set_"):
        return "仅负责写入配置/状态，不保证业务约束（自动推断）"
    return ""


def seed_api_doc_params_from_ast(*, profile: str, limit: int = 200, auto_fill: bool = True) -> int:
    if not mysql_config_enabled():
        raise RuntimeError("MySQL catalog is not configured for API doc seed.")
    prof = _profile_label(profile)
    store = MySQLCatalogStore(readonly=True)
    gaps = store.list_api_doc_gaps(profile=prof, limit=limit)
    if not gaps:
        return 0

    existing_map = {
        (e.module, e.class_name, e.method_name): e for e in store.load_api_doc_entries(profile=prof)
    }

    root = Path(__file__).resolve().parents[1]
    ast_cache: dict[Path, Optional[ast.Module]] = {}
    updates: List[ApiDocEntry] = []

    for gap in gaps:
        existing = existing_map.get((gap.module, gap.class_name, gap.method_name))
        params_json = existing.params_json if existing else ""
        boundaries = existing.boundaries if existing else ""
        side_effects = existing.side_effects if existing else ""
        lifecycle = existing.lifecycle if existing else ""
        notes = existing.notes if existing else ""
        auto_fields = set(existing.auto_fields if existing else ())

        module_path = root / gap.module
        if module_path not in ast_cache:
            ast_cache[module_path] = _load_ast(module_path)
        tree = ast_cache[module_path]
        if tree is not None and not params_json:
            fn = _find_method_node(tree, gap.class_name, gap.method_name)
            if fn is not None:
                params = _extract_params(fn, drop_self=gap.class_name != "(module)")
                params_json = json.dumps(params, ensure_ascii=False)
                auto_fields.add("params")

        if auto_fill:
            if not lifecycle:
                lifecycle = _auto_lifecycle(gap.method_name)
                if lifecycle:
                    auto_fields.add("lifecycle")
            if not side_effects:
                side_effects = _auto_side_effects(gap.method_name)
                if side_effects:
                    auto_fields.add("side_effects")
            if not boundaries:
                boundaries = _auto_boundaries(gap.method_name)
                if boundaries:
                    auto_fields.add("boundaries")

        if not (params_json or boundaries or side_effects or lifecycle or notes):
            continue

        updates.append(
            ApiDocEntry(
                profile=prof,
                module=gap.module,
                class_name=gap.class_name,
                method_name=gap.method_name,
                params_json=params_json,
                boundaries=boundaries,
                side_effects=side_effects,
                lifecycle=lifecycle,
                notes=notes,
                auto_fields=tuple(sorted(auto_fields)),
            )
        )

    if not updates:
        return 0
    writer = MySQLCatalogStore()
    writer.upsert_api_docs(updates, profile=prof)
    return len(updates)
