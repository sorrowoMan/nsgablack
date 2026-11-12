"""Read-only file and source navigation for one immutable Project revision.

The outline describes file locations and Python syntax. It neither imports a
Project nor proves which branches, factories or algorithm instances will run.
Every path comes from the supplied manifest; this module performs no file I/O.
"""
from __future__ import annotations

import ast
from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath
from typing import Any


_GROUPS = (
    ("problem", "问题与数据", "目标、约束、评估含义及输入数据。"),
    ("algorithm", "算法与流程", "装配入口、搜索行为、算法结构和运行配置。"),
    ("pipeline", "候选管线", "初始化、候选处理、编解码与问题修复。"),
    ("capability", "偏好与插件", "选择偏好、观察、检查点及其他生命周期能力。"),
    ("all", "全部文件", "当前 Case 的完整文件清单。"),
)
_DATA_SUFFIXES = {".csv", ".xlsx", ".xls", ".parquet", ".npz", ".npy"}
_CALL_ROLES = {
    "set_adapter": "算法挂载",
    "set_initializer": "初始化规则",
    "set_mutator": "变异规则",
    "set_mutation_operator": "管线变异绑定",
    "set_change": "变化规则",
    "set_parent_selector": "父代选择",
    "set_selector": "成员选择",
    "set_repair": "Unit 修复绑定",
    "set_pool_maintenance": "池成员维护",
    "set_solution_pool_retention": "池保留策略",
    "PoolTaskSpec": "池任务声明",
    "SearchPlanAdapter": "搜索编排声明",
    "StrategySpec": "策略声明",
    "RoleSpec": "角色声明",
    "UnitBinding": "算法结构绑定",
    "Pool": "池草稿构造",
    "chosen": "候选选择调用",
    "inject": "候选入池调用",
    "serial": "串行编排调用",
    "multi": "并行编排调用",
    "repeat": "重复编排调用",
    "stage": "阶段声明调用",
}
MAX_OUTLINE_SOURCE_CHARS = 1024 * 1024


def _paths(revision: Mapping[str, Any]) -> list[str]:
    if not isinstance(revision, Mapping):
        raise ValueError("工程修订必须提供文件清单。")
    rows = revision.get("files", ())
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise ValueError("工程文件清单格式无效。")
    paths: set[str] = set()
    for row in rows:
        path = row.get("path") if isinstance(row, Mapping) else None
        if not isinstance(path, str) or not path or "\\" in path or "\x00" in path:
            raise ValueError("工程文件路径格式无效。")
        parts = path.split("/")
        if (PurePosixPath(path).is_absolute() or any(part in {"", ".", ".."} for part in parts)
                or ":" in parts[0]):
            raise ValueError("工程文件路径必须是清单内的相对路径。")
        paths.add(path)
    return sorted(paths, key=lambda path: (path.casefold(), path))


def _group_id(path: str, prefix: str) -> str | None:
    relative = path[len(prefix):]
    parts = PurePosixPath(relative).parts
    folder = parts[0]
    if folder in {"problem", "evaluation", "data", "datasets", "inputs"}:
        return "problem"
    if PurePosixPath(relative).suffix.lower() in _DATA_SUFFIXES:
        return "problem"
    if folder == "pipeline":
        return "pipeline"
    if folder in {"bias", "plugins", "reporting"}:
        return "capability"
    if folder in {"adapter", "solver", "unit", "units", "runtime"}:
        return "algorithm"
    if len(parts) == 1 and parts[0] in {
        "build_solver.py", "run_solver.py", "build_trainer.py", "run_trainer.py", "config.py",
    }:
        return "algorithm"
    return None


def project_outline(revision: Mapping[str, Any]) -> dict[str, Any]:
    """Group existing Case files without reading or evaluating their contents.

    Case discovery follows the workspace's standard build/run entry pair. A
    directory or a matching string in a README cannot create a runnable Case.
    """
    paths = _paths(revision)
    present = set(paths)
    names = sorted({
        PurePosixPath(path).parts[1]
        for path in paths
        if len(PurePosixPath(path).parts) == 3
        and path.startswith("cases/") and path.endswith("/build_solver.py")
        and str(PurePosixPath(path).parent / "run_solver.py") in present
    })
    cases = []
    for name in names:
        prefix = f"cases/{name}/"
        case_paths = [path for path in paths if path.startswith(prefix)]
        readme = next((prefix + filename for filename in ("README.md", "README_CN.md")
                       if prefix + filename in present), None)
        groups = [{"id": identity, "label": label, "description": description,
                   "paths": case_paths.copy() if identity == "all" else [
                       path for path in case_paths if _group_id(path, prefix) == identity]}
                  for identity, label, description in _GROUPS]
        build = prefix + "build_solver.py"
        cases.append({"name": name, "prefix": prefix, "build_path": build,
                      "run_path": prefix + "run_solver.py", "readme_path": readme,
                      "default_path": readme or build, "groups": groups})
    prefixes = tuple(case["prefix"] for case in cases)
    return {"case_names": names, "cases": cases, "all_paths": paths,
            "project_paths": [path for path in paths if not path.startswith(prefixes)],
            "scope": "manifest_only"}


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted_name(node.value)
        return f"{base}.{node.attr}" if base else None
    return None


def _target_names(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, (ast.Tuple, ast.List)):
        return set().union(*(_target_names(item) for item in node.elts)) if node.elts else set()
    return set()


class _SourceOutline(ast.NodeVisitor):
    def __init__(self) -> None:
        self.symbols: list[dict[str, Any]] = []
        self.calls: list[dict[str, Any]] = []
        self.parents: list[str] = []
        self.bindings: dict[str, str] = {}

    def _resolved(self, node: ast.AST) -> str | None:
        dotted = _dotted_name(node)
        if dotted is None:
            return None
        root, *tail = dotted.split(".")
        resolved = self.bindings.get(root)
        return ".".join((resolved, *tail)) if resolved else None

    def visit_Import(self, node: ast.Import) -> None:
        for item in node.names:
            self.bindings[item.asname or item.name.split(".")[0]] = (
                item.name if item.asname else item.name.split(".")[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = "." * node.level + (node.module or "")
        for item in node.names:
            if item.name != "*":
                separator = "" if not module or module.endswith(".") else "."
                self.bindings[item.asname or item.name] = module + separator + item.name

    def _assignment(self, targets: list[ast.AST], value: ast.AST | None) -> None:
        resolved = self._resolved(value) if value is not None else None
        if value is not None:
            self.visit(value)
        for target in targets:
            for name in _target_names(target):
                self.bindings.pop(name, None)
            if isinstance(target, ast.Name) and resolved is not None:
                self.bindings[target.id] = resolved
            # Subscript/property expressions may contain calls of their own.
            if not isinstance(target, ast.Name):
                self.visit(target)

    def visit_Assign(self, node: ast.Assign) -> None:
        self._assignment(node.targets, node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.visit(node.annotation)
        self._assignment([node.target], node.value)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._assignment([node.target], node.value)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self._assignment([node.target], node.value)

    def _definition(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> None:
        name = ".".join((*self.parents, node.name))
        kind = ("class" if isinstance(node, ast.ClassDef)
                else "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function")
        self.symbols.append({"name": name, "kind": kind, "line": node.lineno,
                             "end_line": node.end_lineno or node.lineno})
        for decorator in node.decorator_list:
            self.visit(decorator)
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                self.visit(base)
            for keyword in node.keywords:
                self.visit(keyword.value)
        else:
            for default in (*node.args.defaults, *node.args.kw_defaults):
                if default is not None:
                    self.visit(default)
        self.bindings.pop(node.name, None)
        outer = self.bindings
        self.bindings = dict(outer)
        if not isinstance(node, ast.ClassDef):
            args = (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs,
                    *((node.args.vararg,) if node.args.vararg else ()),
                    *((node.args.kwarg,) if node.args.kwarg else ()))
            for arg in args:
                self.bindings.pop(arg.arg, None)
        self.parents.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self.parents.pop()
        self.bindings = outer

    visit_FunctionDef = _definition
    visit_AsyncFunctionDef = _definition
    visit_ClassDef = _definition

    def visit_Call(self, node: ast.Call) -> None:
        name = _dotted_name(node.func)
        canonical = self._resolved(node.func)
        tail = (canonical or name or "").rsplit(".", 1)[-1]
        if not tail and isinstance(node.func, ast.Attribute):
            tail = node.func.attr
            name = f"<expression>.{tail}"
        role = _CALL_ROLES.get(tail)
        if (canonical or name or "").endswith(("subpools.all", "subpools.random")):
            role = "子池视图选择"
        if role:
            self.calls.append({"name": name or tail, "canonical_name": canonical,
                               "role": role, "line": node.lineno,
                               "end_line": node.end_lineno or node.lineno,
                               "owner": ".".join(self.parents) or None,
                               "evidence": "source_call"})
        self.generic_visit(node)


def source_outline(path: str, source: str) -> dict[str, Any]:
    """Return navigable definitions/call sites, never runtime assembly claims.

    Import aliases are resolved syntactically within the visited scope. Dynamic
    factories, conditional execution and actual object types remain unknown.
    Non-Python text is not parsed as Python; syntax failures remain editable.
    """
    if not isinstance(path, str) or not isinstance(source, str):
        raise ValueError("源码导航需要文件路径与文本内容。")
    python = PurePosixPath(path).suffix.lower() == ".py"
    result: dict[str, Any] = {"kind": "python" if python else "text", "syntax_ok": None,
                              "symbols": [], "calls": [], "diagnostics": [],
                              "scope": "static_source"}
    if not python:
        return result
    if len(source) > MAX_OUTLINE_SOURCE_CHARS:
        result["diagnostics"] = [{"code": "source-outline-too-large", "line": None,
                                   "column": None, "message": "文件较大，请直接查看源码。"}]
        return result
    try:
        # A UTF-8 signature can survive a text transport. Removing this one
        # leading character preserves every source line and column thereafter.
        tree = ast.parse(source.removeprefix("\ufeff"))
        visitor = _SourceOutline()
        visitor.visit(tree)
    except SyntaxError as exc:
        result["syntax_ok"] = False
        result["diagnostics"] = [{"code": "python-syntax-error", "line": exc.lineno,
                                   "column": exc.offset, "message": exc.msg}]
        return result
    except (ValueError, RecursionError, MemoryError):
        result["syntax_ok"] = False
        result["diagnostics"] = [{"code": "source-outline-unavailable", "line": None,
                                   "column": None, "message": "当前文本无法建立源码导航。"}]
        return result
    result["syntax_ok"] = True
    result["symbols"] = sorted(visitor.symbols, key=lambda item: (item["line"], item["name"]))
    result["calls"] = sorted(visitor.calls, key=lambda item: (item["line"], item["name"]))
    return result
