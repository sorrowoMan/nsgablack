from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .contracts import ApiIndexEntry, ApiIndexMeta
from .store.mysql import MySQLCatalogStore, mysql_config_enabled


_ROOT = Path(__file__).resolve().parents[1]

_FRAMEWORK_CORE_DIRS = (
    "core",
    "adapters",
    "plugins",
    "representation",
    "bias",
    "utils",
    "catalog",
    "project",
    "nsgablack",
)

_DEFAULT_EXCLUDE_DIRS = {
    "examples",
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    "build",
    "dist",
}


_SPECIAL_METHODS = {
    "evaluate_population": ("批量评估入口", "算法主路径与并行评估常用入口"),
    "evaluate_individual": ("单点评估入口", "调试/在线评估场景优先使用"),
    "run": ("执行完整生命周期主流程", "直接调用 `instance.run(...)` 作为入口"),
    "step": ("执行一个离散迭代步", "用于调试或外部细粒度驱动"),
    "setup": ("初始化组件运行态并绑定上下文", "在 `run/setup` 阶段由框架调用，通常不手工频繁触发"),
    "teardown": ("释放资源并收尾持久化", "在 `run` 结束后自动调用，可用于 flush/report"),
    "propose": ("生成待评估候选解", "由 solver 在评估前调用，返回候选序列"),
    "update": ("根据评估反馈更新内部状态", "在目标值/约束值返回后调用"),
    "get_state": ("导出可恢复状态快照", "用于 checkpoint、断点续跑与调试可视化"),
    "set_state": ("恢复内部状态", "在 resume 或迁移运行态时调用"),
    "set_population": ("写入当前种群快照", "用于 runtime 插件回写或恢复后对齐"),
    "get_population": ("读取当前种群快照", "给插件可视化读取运行态"),
    "get_context_contract": ("声明 context 读写契约", "doctor 校验与组件编排时读取"),
    "get_runtime_context_projection": ("输出可观测运行态切片", "供插件/UI 获取关键运行指标"),
    "on_solver_init": ("solver 初始化生命周期钩子", "插件在启动阶段注入逻辑"),
    "on_population_init": ("初代种群完成后的钩子", "插件统计或过滤初始化结果"),
    "on_generation_start": ("每代开始钩子", "插件更新调度参数或预算"),
    "on_step": ("步级别钩子", "需要更细粒度监控时使用"),
    "on_generation_end": ("每代结束钩子", "插件记录指标/归档/动态调控"),
    "on_solver_finish": ("求解结束钩子", "输出报告、落盘、清理资源"),
}


_PREFIX_TEMPLATES = {
    "can_handle_": (
        "判断当前是否可执行 `handle_{suffix}`",
        "在执行前先调用，返回布尔值决定是否继续",
    ),
    "get_": (
        "读取 `{suffix}` 相关运行态或配置值",
        "通过 `obj.{method}(...)` 在日志、诊断或编排阶段查询",
    ),
    "set_": (
        "设置 `{suffix}` 相关运行参数或状态",
        "在构建 solver/adapter/plugin 时调用 `obj.{method}(...)`",
    ),
    "has_": (
        "判断是否具备 `{suffix}` 能力",
        "在装配分支中调用并据此选择能力路径",
    ),
    "resolve_": (
        "解析并确定 `{suffix}` 最终结果",
        "在多来源配置合并时调用 `obj.{method}(...)`",
    ),
    "build_": (
        "构建 `{suffix}` 产物或对象",
        "作为工厂方法在装配阶段调用并接入后续流程",
    ),
    "create_": (
        "创建 `{suffix}` 实例或资源",
        "在初始化阶段调用并返回可复用对象",
    ),
    "validate_": (
        "校验 `{suffix}` 合法性与一致性",
        "在运行前调用，异常时中断并修正配置",
    ),
}


_GENERIC_PURPOSE = "组件公开方法（需结合实现细节）"
_GENERIC_USAGE = "按签名调用 `obj.{method}(...)`，并结合所属类职责使用"


@dataclass(frozen=True)
class ApiIndexBundle:
    entries: Sequence[ApiIndexEntry]
    meta: ApiIndexMeta


def _profile_label(profile: str) -> str:
    return str(profile or "default").strip().lower() or "default"


def _iter_profile_files(profile: str) -> Tuple[List[Path], int]:
    prof = _profile_label(profile)
    files: List[Path] = []
    if prof == "framework-core":
        for rel in _FRAMEWORK_CORE_DIRS:
            base = _ROOT / rel
            if not base.exists():
                continue
            for path in sorted(base.rglob("*.py")):
                if "__pycache__" in path.parts:
                    continue
                files.append(path)
        return files, len(files)

    if prof == "default":
        for path in sorted(_ROOT.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            if any(part in _DEFAULT_EXCLUDE_DIRS for part in path.parts):
                continue
            files.append(path)
        return files, len(files)

    raise ValueError(f"Unsupported profile: {profile}")


def _scan_module(path: Path) -> Tuple[List[Tuple[str, int]], List[Tuple[str, List[Tuple[str, int]]]]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return [], []

    module_funcs: List[Tuple[str, int]] = []
    class_blocks: List[Tuple[str, List[Tuple[str, int]]]] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                module_funcs.append((node.name, node.lineno))
        elif isinstance(node, ast.ClassDef):
            methods: List[Tuple[str, int]] = []
            for stmt in node.body:
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not stmt.name.startswith("_"):
                        methods.append((stmt.name, stmt.lineno))
            if methods:
                class_blocks.append((node.name, methods))
    return module_funcs, class_blocks


def _infer_usage(method_name: str, existing: Dict[Tuple[str, str, str], Tuple[str, str]]) -> Tuple[str, str]:
    existing_val = existing.get(("", "", method_name))
    if method_name in _SPECIAL_METHODS:
        return _SPECIAL_METHODS[method_name]
    if existing_val:
        return existing_val
    for prefix, (purpose_tpl, usage_tpl) in _PREFIX_TEMPLATES.items():
        if method_name.startswith(prefix):
            suffix = method_name[len(prefix) :]
            purpose = purpose_tpl.format(suffix=suffix, method=method_name)
            usage = usage_tpl.format(suffix=suffix, method=method_name)
            return purpose, usage
    return _GENERIC_PURPOSE, _GENERIC_USAGE.format(method=method_name)


def build_api_index_bundle(
    *,
    profile: str,
    existing_map: Optional[Dict[Tuple[str, str, str], Tuple[str, str]]] = None,
) -> ApiIndexBundle:
    existing_map = existing_map or {}
    files, file_count = _iter_profile_files(profile)
    prof = _profile_label(profile)
    entries: List[ApiIndexEntry] = []

    for path in files:
        rel = path.relative_to(_ROOT).as_posix()
        module_funcs, class_blocks = _scan_module(path)
        if module_funcs:
            for name, lineno in module_funcs:
                key = (rel, "(module)", name)
                if key in existing_map:
                    purpose, usage = existing_map[key]
                else:
                    purpose, usage = _infer_usage(name, existing_map)
                entries.append(
                    ApiIndexEntry(
                        profile=prof,
                        module=rel,
                        class_name="(module)",
                        method_name=name,
                        purpose=purpose,
                        usage=usage,
                        lineno=lineno,
                    )
                )
        for class_name, methods in class_blocks:
            for name, lineno in methods:
                key = (rel, class_name, name)
                if key in existing_map:
                    purpose, usage = existing_map[key]
                else:
                    purpose, usage = _infer_usage(name, existing_map)
                entries.append(
                    ApiIndexEntry(
                        profile=prof,
                        module=rel,
                        class_name=class_name,
                        method_name=name,
                        purpose=purpose,
                        usage=usage,
                        lineno=lineno,
                    )
                )

    component_count = len({(e.module, e.class_name) for e in entries})
    meta = ApiIndexMeta(
        profile=prof,
        file_count=file_count,
        component_count=component_count,
        method_count=len(entries),
    )
    return ApiIndexBundle(entries=entries, meta=meta)


def _load_existing_map(profile: str) -> Dict[Tuple[str, str, str], Tuple[str, str]]:
    if not mysql_config_enabled():
        return {}
    try:
        store = MySQLCatalogStore(readonly=True)
        entries = store.load_api_index(profile=_profile_label(profile))
    except Exception:
        return {}
    out: Dict[Tuple[str, str, str], Tuple[str, str]] = {}
    for e in entries:
        key = (e.module, e.class_name, e.method_name)
        out[key] = (e.purpose, e.usage)
    return out


def sync_api_index_to_mysql(*, profile: str, overwrite_usage: bool = False) -> ApiIndexMeta:
    if not mysql_config_enabled():
        raise RuntimeError("MySQL catalog is not configured for API index sync.")
    existing = {} if overwrite_usage else _load_existing_map(profile)
    bundle = build_api_index_bundle(profile=profile, existing_map=existing)
    store = MySQLCatalogStore()
    store.sync_api_index(bundle.entries, bundle.meta, profile=_profile_label(profile), wipe=True)
    return bundle.meta


def load_api_index_from_mysql(*, profile: str) -> Tuple[List[ApiIndexEntry], Optional[ApiIndexMeta]]:
    if not mysql_config_enabled():
        raise RuntimeError("MySQL catalog is not configured for API index load.")
    store = MySQLCatalogStore(readonly=True)
    entries = store.load_api_index(profile=_profile_label(profile))
    meta = store.load_api_index_meta(profile=_profile_label(profile))
    return entries, meta


def search_api_index_from_mysql(
    *, profile: str, query: str, field: str = "all", limit: int = 20
) -> List[ApiIndexEntry]:
    if not mysql_config_enabled():
        raise RuntimeError("MySQL catalog is not configured for API index search.")
    store = MySQLCatalogStore(readonly=True)
    return store.search_api_index(
        profile=_profile_label(profile),
        query=query,
        field=field,
        limit=limit,
    )


def get_api_index_entry_from_mysql(
    *,
    profile: str,
    module: str,
    class_name: str,
    method_name: str,
) -> Optional[ApiIndexEntry]:
    if not mysql_config_enabled():
        raise RuntimeError("MySQL catalog is not configured for API index lookup.")
    store = MySQLCatalogStore(readonly=True)
    return store.get_api_index_entry(
        profile=_profile_label(profile),
        module=module,
        class_name=class_name,
        method_name=method_name,
    )


def render_api_index_markdown(
    *,
    entries: Sequence[ApiIndexEntry],
    meta: Optional[ApiIndexMeta],
    profile: str,
) -> str:
    prof = _profile_label(profile)
    if prof == "framework-core":
        title = "# 纯框架主干 API 索引（逐类逐方法，含用途/用法）"
        quote_lines = [
            "> 来源：MySQL（catalog_api_index）",
            "> 白名单：`core/adapters/plugins/representation/bias/utils/catalog/project/nsgablack`",
        ]
    else:
        title = "# 全组件 API 全量索引（逐类逐方法，含用途/用法）"
        quote_lines = [
            "> 来源：MySQL（catalog_api_index）",
            "> 说明：本文件用于“覆盖全仓”的组件 API 检索与重构治理。",
            "> 特殊规则：已按要求排除 `examples/` 目录内容。",
        ]

    file_count = meta.file_count if meta else len({e.module for e in entries})
    component_count = meta.component_count if meta else len({(e.module, e.class_name) for e in entries})
    method_count = meta.method_count if meta else len(entries)

    coverage: Dict[str, int] = {}
    for e in entries:
        top = str(e.module).split("/")[0]
        coverage[top] = coverage.get(top, 0) + 1

    def _sorted_entries(items: Iterable[ApiIndexEntry]) -> List[ApiIndexEntry]:
        return sorted(items, key=lambda x: (x.module, x.class_name, x.lineno, x.method_name))

    entries_sorted = _sorted_entries(entries)

    lines: List[str] = []
    lines.append(title)
    lines.append("")
    lines.extend(quote_lines)
    lines.append("")
    lines.append(f"- 扫描文件数：`{file_count}`")
    lines.append(f"- 组件（模块+类）数：`{component_count}`")
    lines.append(f"- 方法/函数条目总数：`{method_count}`")
    lines.append("")
    lines.append("## 覆盖统计（按顶层目录）")
    lines.append("")
    lines.append("| 顶层目录 | 条目数 |")
    lines.append("|---|---:|")
    for key in sorted(coverage.keys()):
        lines.append(f"| `{key}` | {coverage[key]} |")
    lines.append("")
    lines.append("## A. 扁平检索总表（模块 / 类 / 方法 / 用途 / 用法）")
    lines.append("")
    lines.append("| 模块 | 类 | 方法 | 用途 | 用法 |")
    lines.append("|---|---|---|---|---|")
    for e in entries_sorted:
        lines.append(
            f"| `{e.module}` | `{e.class_name}` | `{e.method_name}` | {e.purpose} | {e.usage} |"
        )
    lines.append("")
    lines.append("## B. 逐类完整展开（每个 class/模块函数集合）")
    lines.append("")

    by_module: Dict[str, List[ApiIndexEntry]] = {}
    for e in entries_sorted:
        by_module.setdefault(e.module, []).append(e)

    for module in sorted(by_module.keys()):
        lines.append(f"### `{module}`")
        lines.append("")
        block = by_module[module]
        by_class: Dict[str, List[ApiIndexEntry]] = {}
        for e in block:
            by_class.setdefault(e.class_name, []).append(e)

        for class_name in sorted(by_class.keys()):
            methods = by_class[class_name]
            lines.append(f"- `{class_name}`")
            lines.append(f"  - 方法数：`{len(methods)}`")
            lines.append("  - 方法明细：")
            for e in methods:
                lines.append(
                    f"    - `{e.method_name}`（L{e.lineno}）：用途={e.purpose}；用法={e.usage}"
                )
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def export_api_index_docs(*, profile: str, output_path: Path) -> Path:
    entries, meta = load_api_index_from_mysql(profile=profile)
    content = render_api_index_markdown(entries=entries, meta=meta, profile=profile)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path


def export_default_api_index_docs() -> List[Path]:
    mapping = {
        "default": Path("docs/development/COMPONENT_API_INDEX_FULL_CN.md"),
        "framework-core": Path("docs/development/COMPONENT_API_INDEX_FRAMEWORK_CORE_CN.md"),
    }
    out: List[Path] = []
    for profile, path in mapping.items():
        out.append(export_api_index_docs(profile=profile, output_path=path))
    return out
