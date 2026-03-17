from __future__ import annotations

import ast
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_MD = REPO_ROOT / "docs" / "development" / "API_GLOBAL_RENAME_AUDIT_CN.md"
REPORT_CSV = REPO_ROOT / "artifacts" / "naming_audit" / "api_rename_audit.csv"
INCLUDED_SUFFIXES = {".py"}
SKIP_DIR_NAMES = {
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
}

EXACT_CLASS_RENAMES = {
    "ContextSwitchMutator": "ContextSelectMutator",
    "ContextRouterMutator": "ContextDispatchMutator",
    "SerialStrategyControllerAdapter": "StrategyChainAdapter",
    "MultiStrategyControllerAdapter": "StrategyRouterAdapter",
    "MultiRoleControllerAdapter": "RoleRouterAdapter",
}

PARAM_ALIASES = {
    "switch_key": "selector",
    "route_key": "selector",
    "route_map": "routes",
    "router": "routes",
    "default_strategy": "fallback",
    "gen": "generation",
    "iter": "generation",
}

GETTERISH_TOKENS = {
    "population_snapshot",
    "best_snapshot",
    "checkpoint_path",
    "hmac_key",
    "context_best",
    "context_value",
    "run_id",
    "entry_file",
    "summary_path",
    "export_path",
    "pareto_export_root",
    "best_snapshot_fields",
}
GETTERISH_CONTAINS = (
    "snapshot",
    "path",
    "value",
    "run_id",
    "section",
    "entry",
    "file",
    "summary",
    "export",
)
COMPUTEISH_TOKENS = {
    "config",
    "order",
    "order_strict",
    "order_internal",
    "start_state",
    "phase",
    "biases",
    "max_generations",
    "backend",
    "switch_mode",
    "mapping",
    "callable",
    "template_name",
    "machine_weights",
    "existing",
    "default_baseline_plan",
    "import_path",
    "bounds",
    "observability_preset",
}

OUT_OF_SCOPE_BUCKETS = {"tests"}
KEEP_SWITCH_PATH_PARTS = {
    "utils/dynamic/switch.py",
    "plugins/runtime/dynamic_switch.py",
    "utils/wiring/dynamic_switch.py",
}


@dataclass
class SymbolRecord:
    path: str
    bucket: str
    line: int
    kind: str
    qualified_name: str
    name: str
    parent: str
    params: list[str]


@dataclass
class Advice:
    action: str
    suggested_name: str
    confidence: str
    reason: str
    param_suggestions: list[str]


def iter_python_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        yield path


def classify_bucket(path: Path) -> str:
    rel = path.relative_to(REPO_ROOT).as_posix()
    first = rel.split("/", 1)[0]
    if first in {
        "core",
        "adapters",
        "representation",
        "plugins",
        "bias",
        "utils",
        "project",
        "examples",
        "tests",
        "tools",
        "scripts",
        "catalog",
        "benchmarks",
        "my_project",
        "nsgablack",
        "docs",
    }:
        return first
    return "root"


class SymbolCollector(ast.NodeVisitor):
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.bucket = classify_bucket(file_path)
        self.class_stack: list[str] = []
        self.function_stack: list[str] = []
        self.records: list[SymbolRecord] = []

    def _qualified_name(self, name: str) -> str:
        parts = [*self.class_stack, *self.function_stack, name]
        return ".".join(part for part in parts if part)

    def _params(self, node: ast.AST) -> list[str]:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return []
        items: list[str] = []
        args = node.args
        for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
            items.append(arg.arg)
        if args.vararg is not None:
            items.append("*" + args.vararg.arg)
        if args.kwarg is not None:
            items.append("**" + args.kwarg.arg)
        return items

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        parent = self.class_stack[-1] if self.class_stack else ""
        self.records.append(
            SymbolRecord(
                path=self.file_path.relative_to(REPO_ROOT).as_posix(),
                bucket=self.bucket,
                line=node.lineno,
                kind="class",
                qualified_name=self._qualified_name(node.name),
                name=node.name,
                parent=parent,
                params=[],
            )
        )
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        parent = self.class_stack[-1] if self.class_stack else ""
        kind = "method" if self.class_stack else "function"
        self.records.append(
            SymbolRecord(
                path=self.file_path.relative_to(REPO_ROOT).as_posix(),
                bucket=self.bucket,
                line=node.lineno,
                kind=kind,
                qualified_name=self._qualified_name(node.name),
                name=node.name,
                parent=parent,
                params=self._params(node),
            )
        )
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        parent = self.class_stack[-1] if self.class_stack else ""
        kind = "async-method" if self.class_stack else "async-function"
        self.records.append(
            SymbolRecord(
                path=self.file_path.relative_to(REPO_ROOT).as_posix(),
                bucket=self.bucket,
                line=node.lineno,
                kind=kind,
                qualified_name=self._qualified_name(node.name),
                name=node.name,
                parent=parent,
                params=self._params(node),
            )
        )
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()


def read_symbols(path: Path) -> list[SymbolRecord]:
    source = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []
    collector = SymbolCollector(path)
    collector.visit(tree)
    return collector.records


def is_dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__") and len(name) > 4


def param_suggestions(record: SymbolRecord) -> list[str]:
    suggestions: list[str] = []
    for param in record.params:
        plain = param.lstrip("*")
        if plain in {"self", "cls"}:
            continue
        target = PARAM_ALIASES.get(plain)
        if target and target != plain:
            suggestions.append(f"{plain}->{target}")
    return suggestions


def suggest_resolve_name(record: SymbolRecord, stem: str, private: bool) -> Advice:
    prefix = "_" if private else ""
    parameter_notes = param_suggestions(record)
    if stem in GETTERISH_TOKENS:
        return Advice(
            action="rename",
            suggested_name=f"{prefix}get_{stem}",
            confidence="high",
            reason="读取/取值语义优先统一到 get_*，避免 resolve_* 同时承载读取和推断。",
            param_suggestions=parameter_notes,
        )
    if stem in COMPUTEISH_TOKENS:
        return Advice(
            action="keep",
            suggested_name=record.name,
            confidence="high",
            reason="该 resolve_* 属于推断/合并/派生语义，符合规范保留。",
            param_suggestions=parameter_notes,
        )
    if any(token in stem for token in GETTERISH_CONTAINS):
        return Advice(
            action="rename",
            suggested_name=f"{prefix}get_{stem}",
            confidence="high",
            reason="读取/取值语义优先统一到 get_*，避免 resolve_* 同时承载读取和推断。",
            param_suggestions=parameter_notes,
        )
    return Advice(
        action="review",
        suggested_name=record.name,
        confidence="low",
        reason="无法仅靠静态命名确定 resolve_* 属于读取还是推断，建议人工确认后再改。",
        param_suggestions=parameter_notes,
    )


def advise(record: SymbolRecord) -> Advice:
    parameter_notes = param_suggestions(record)
    rel_path = record.path
    name = record.name

    if record.bucket in OUT_OF_SCOPE_BUCKETS:
        return Advice(
            action="out-of-scope",
            suggested_name=name,
            confidence="high",
            reason="测试文件不作为框架 Canonical API 命名源头，仅在目标 API 改名后跟随调整。",
            param_suggestions=parameter_notes,
        )

    if is_dunder(name):
        return Advice(
            action="keep",
            suggested_name=name,
            confidence="high",
            reason="Python 特殊方法，按语言协议保留。",
            param_suggestions=parameter_notes,
        )

    if record.kind == "class":
        exact = EXACT_CLASS_RENAMES.get(name)
        if exact:
            return Advice(
                action="rename",
                suggested_name=exact,
                confidence="high",
                reason="该类命中已确认的高优先级命名收敛映射。",
                param_suggestions=parameter_notes,
            )
        if name.endswith("ControllerAdapter"):
            return Advice(
                action="review",
                suggested_name=name.replace("ControllerAdapter", "Adapter"),
                confidence="medium",
                reason="ControllerAdapter 为复合角色后缀，原则上应拆解为更单一的 Adapter/Router/Chain 语义。",
                param_suggestions=parameter_notes,
            )
        return Advice(
            action="keep",
            suggested_name=name,
            confidence="high",
            reason="类名未命中当前归一化冲突规则。",
            param_suggestions=parameter_notes,
        )

    if name == "build_provider":
        return Advice(
            action="rename",
            suggested_name="create_provider",
            confidence="high",
            reason="对外 provider 构造动作统一使用 create_*。",
            param_suggestions=parameter_notes,
        )

    if name.startswith("set_enable_"):
        tail = name.removeprefix("set_enable_")
        return Advice(
            action="rename",
            suggested_name=f"set_{tail}_enabled",
            confidence="high",
            reason="禁止双动词 set_enable_*；布尔 setter 统一为 set_*_enabled。",
            param_suggestions=parameter_notes,
        )

    if name.startswith("set_disable_"):
        tail = name.removeprefix("set_disable_")
        return Advice(
            action="rename",
            suggested_name=f"set_{tail}_disabled",
            confidence="high",
            reason="禁止双动词 set_disable_*；布尔 setter 统一为 set_*_disabled。",
            param_suggestions=parameter_notes,
        )

    if name.startswith("resolve_"):
        return suggest_resolve_name(record, name.removeprefix("resolve_"), private=False)

    if name.startswith("_resolve_"):
        return suggest_resolve_name(record, name.removeprefix("_resolve_"), private=True)

    if name.startswith("router_"):
        return Advice(
            action="rename",
            suggested_name="dispatch_" + name.removeprefix("router_"),
            confidence="medium",
            reason="方法级路由动作统一使用 dispatch_*；Router 更适合作为类型名。",
            param_suggestions=parameter_notes,
        )

    if name.startswith("serial_") and rel_path not in KEEP_SWITCH_PATH_PARTS:
        return Advice(
            action="review",
            suggested_name="chain_" + name.removeprefix("serial_"),
            confidence="medium",
            reason="若该名称表达公开串行编排语义，建议改为 chain_*；若是性能/数学术语则保留。",
            param_suggestions=parameter_notes,
        )

    if name.startswith("switch_") and rel_path not in KEEP_SWITCH_PATH_PARTS:
        return Advice(
            action="review",
            suggested_name="select_" + name.removeprefix("switch_"),
            confidence="medium",
            reason="非状态机场景下 switch_* 容易与真正切换语义冲突，建议审查是否应收敛为 select_*。",
            param_suggestions=parameter_notes,
        )

    if name.startswith("_switch_") and rel_path not in KEEP_SWITCH_PATH_PARTS:
        return Advice(
            action="review",
            suggested_name="_select_" + name.removeprefix("_switch_"),
            confidence="low",
            reason="私有 helper 命中 switch_* 模式，若并非真实状态机切换，建议审查是否改为 select_*。",
            param_suggestions=parameter_notes,
        )

    if name.startswith("_router_"):
        return Advice(
            action="review",
            suggested_name="_dispatch_" + name.removeprefix("_router_"),
            confidence="medium",
            reason="私有 helper 若表达分发动作，建议统一为 dispatch_*。",
            param_suggestions=parameter_notes,
        )

    if name in {"get", "set", "delete", "put"}:
        return Advice(
            action="keep",
            suggested_name=name,
            confidence="high",
            reason="通用存取方法，参数别名规则不适用。",
            param_suggestions=parameter_notes,
        )

    if name.startswith("_") and parameter_notes:
        return Advice(
            action="keep",
            suggested_name=name,
            confidence="high",
            reason="私有方法参数别名不纳入公开 API 命名审计。",
            param_suggestions=parameter_notes,
        )

    if parameter_notes:
        return Advice(
            action="review",
            suggested_name=name,
            confidence="medium",
            reason="名称本身可暂留，但参数命名存在历史别名，建议同步收敛。",
            param_suggestions=parameter_notes,
        )

    return Advice(
        action="keep",
        suggested_name=name,
        confidence="high",
        reason="未命中当前批量改名规则，可暂时保留。",
        param_suggestions=parameter_notes,
    )


def build_markdown(rows: list[tuple[SymbolRecord, Advice]]) -> str:
    summary: dict[tuple[str, str], int] = {}
    exact_renames = 0
    rename_rows: list[tuple[SymbolRecord, Advice]] = []
    for record, advice in rows:
        summary[(record.bucket, advice.action)] = summary.get((record.bucket, advice.action), 0) + 1
        if advice.action == "rename":
            exact_renames += 1
            rename_rows.append((record, advice))

    bucket_names = sorted({record.bucket for record, _ in rows})
    lines: list[str] = []
    lines.append("# 全局 API 改名审计（全文件 / 全方法）")
    lines.append("")
    lines.append("> 本文由 `tools/generate_api_rename_audit.py` 自动生成，覆盖仓库内所有可解析 Python 文件中的类、函数、方法与异步方法。")
    lines.append("")
    lines.append("## 1. 审计范围")
    lines.append("")
    lines.append(f"- Python 文件数：`{len({record.path for record, _ in rows})}`")
    lines.append(f"- 符号总数：`{len(rows)}`")
    lines.append(f"- 明确建议改名：`{exact_renames}`")
    lines.append("")
    lines.append("## 2. 动作说明")
    lines.append("")
    lines.append("- `rename`：高置信度，建议直接进入首批改名计划。")
    lines.append("- `review`：需要结合语义人工复核，不能机械替换。")
    lines.append("- `keep`：当前规则下建议保留。")
    lines.append("- `out-of-scope`：不作为 Canonical API 命名源头，但会受后续改名波及。")
    lines.append("")
    lines.append("## 3. 目录级计数")
    lines.append("")
    lines.append("| 目录 | rename | review | keep | out-of-scope |")
    lines.append("|---|---:|---:|---:|---:|")
    for bucket in bucket_names:
        rename_count = summary.get((bucket, "rename"), 0)
        review_count = summary.get((bucket, "review"), 0)
        keep_count = summary.get((bucket, "keep"), 0)
        out_count = summary.get((bucket, "out-of-scope"), 0)
        lines.append(f"| `{bucket}` | {rename_count} | {review_count} | {keep_count} | {out_count} |")
    lines.append("")
    lines.append("## 4. 首批高置信度改名清单")
    lines.append("")
    lines.append("| 文件 | 行号 | 类型 | 当前名称 | 建议新名 | 原因 |")
    lines.append("|---|---:|---|---|---|---|")
    for record, advice in sorted(rename_rows, key=lambda item: (item[0].path, item[0].line, item[0].qualified_name)):
        lines.append(
            f"| `{record.path}` | {record.line} | {record.kind} | `{record.qualified_name}` | `{advice.suggested_name}` | {advice.reason} |"
        )
    lines.append("")
    lines.append("## 5. 全量逐项建议")
    lines.append("")

    grouped: dict[str, list[tuple[SymbolRecord, Advice]]] = {}
    for record, advice in rows:
        grouped.setdefault(record.path, []).append((record, advice))

    for path in sorted(grouped):
        lines.append(f"### `{path}`")
        lines.append("")
        lines.append("| 行号 | 类型 | 当前名称 | 建议动作 | 建议新名 | 置信度 | 参数建议 | 原因 |")
        lines.append("|---:|---|---|---|---|---|---|---|")
        for record, advice in sorted(grouped[path], key=lambda item: (item[0].line, item[0].qualified_name)):
            params = ", ".join(advice.param_suggestions) if advice.param_suggestions else "-"
            lines.append(
                f"| {record.line} | {record.kind} | `{record.qualified_name}` | `{advice.action}` | `{advice.suggested_name}` | `{advice.confidence}` | `{params}` | {advice.reason} |"
            )
        lines.append("")

    return "\n".join(lines) + "\n"


def write_csv(rows: list[tuple[SymbolRecord, Advice]]) -> None:
    REPORT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "path",
            "bucket",
            "line",
            "kind",
            "qualified_name",
            "current_name",
            "action",
            "suggested_name",
            "confidence",
            "param_suggestions",
            "reason",
        ])
        for record, advice in rows:
            writer.writerow([
                record.path,
                record.bucket,
                record.line,
                record.kind,
                record.qualified_name,
                record.name,
                advice.action,
                advice.suggested_name,
                advice.confidence,
                "; ".join(advice.param_suggestions),
                advice.reason,
            ])


def main() -> None:
    rows: list[tuple[SymbolRecord, Advice]] = []
    for path in sorted(iter_python_files(REPO_ROOT)):
        for record in read_symbols(path):
            rows.append((record, advise(record)))

    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(build_markdown(rows), encoding="utf-8")
    write_csv(rows)
    print(f"Generated {REPORT_MD}")
    print(f"Generated {REPORT_CSV}")
    print(f"Symbols: {len(rows)}")


if __name__ == "__main__":
    main()
