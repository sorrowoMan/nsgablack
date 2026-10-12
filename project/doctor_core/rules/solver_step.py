"""Static enforcement for the strict Solver ``step`` result contract."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Callable, List

from ..model import DoctorDiagnostic
from blackbase.project.doctor_scope import discover_doctor_roots, source_files


def _base_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return str(node.id)
    if isinstance(node, ast.Attribute):
        return str(node.attr)
    if isinstance(node, ast.Subscript):
        return _base_name(node.value)
    return ""


def _is_solver_class(node: ast.ClassDef) -> bool:
    return any(
        name in {"SolverBase", "ComposableSolver", "EvolutionSolver"}
        or name.endswith("Solver")
        for name in (_base_name(base) for base in node.bases)
    )


def _returns_none(step: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    class ReturnVisitor(ast.NodeVisitor):
        found = False

        def visit_Return(self, node: ast.Return) -> None:  # noqa: N802
            if node.value is None or (
                isinstance(node.value, ast.Constant) and node.value.value is None
            ):
                self.found = True

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
            if node is step:
                self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
            if node is step:
                self.generic_visit(node)

        def visit_Lambda(self, node: ast.Lambda) -> None:  # noqa: N802
            del node

        def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
            del node

    visitor = ReturnVisitor()
    visitor.visit(step)
    return bool(visitor.found)


def _can_fall_through(body: list[ast.stmt]) -> bool:
    """Conservative structured control flow, without executing user code."""
    for stmt in body:
        if isinstance(stmt, (ast.Return, ast.Raise)):
            return False
        if isinstance(stmt, ast.If):
            if isinstance(stmt.test, ast.Constant):
                branch = stmt.body if stmt.test.value else stmt.orelse
                if not _can_fall_through(branch):
                    return False
                continue
            if not _can_fall_through(stmt.body) and not _can_fall_through(stmt.orelse):
                return False
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            if not _can_fall_through(stmt.body):
                return False
        elif isinstance(stmt, (ast.Try, getattr(ast, "TryStar", ast.Try))):
            if stmt.finalbody and not _can_fall_through(stmt.finalbody):
                return False
            normal = _can_fall_through(stmt.body) and _can_fall_through(stmt.orelse)
            if not normal and all(not _can_fall_through(h.body) for h in stmt.handlers):
                return False
        elif isinstance(stmt, ast.Match):
            exhaustive = any(isinstance(c.pattern, ast.MatchAs) and c.pattern.pattern is None and c.guard is None for c in stmt.cases)
            if exhaustive and all(not _can_fall_through(c.body) for c in stmt.cases):
                return False
        elif isinstance(stmt, ast.While) and isinstance(stmt.test, ast.Constant) and stmt.test.value is True:
            if not any(isinstance(n, ast.Break) for part in stmt.body for n in ast.walk(part)):
                return False
    return True


def _outcome_annotation(node, aliases) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        try:
            node = ast.parse(node.value, mode="eval").body
        except SyntaxError:
            return False
    if isinstance(node, ast.Name):
        return node.id in aliases
    return isinstance(node, ast.Attribute) and node.attr == "StepOutcome"


def _candidate_files(root: Path) -> tuple[Path, ...]:
    files: set[Path] = set()
    if (root / "core" / "blank_solver.py").is_file():
        files.update(source_files(root / "core"))
    # A custom Solver is allowed directly in a canonical build_solver.py or
    # in any package below that Case root.  Discover the scaffold boundary
    # instead of guessing from a directory literally named ``solver``.
    _, cases = discover_doctor_roots(root)
    for case_root in cases:
        files.update(source_files(case_root))
    root_builder = root / "build_solver.py"
    if root_builder.is_file():
        files.add(root_builder)
    solver_dir = root / "solver"
    if solver_dir.is_dir():
        files.update(source_files(solver_dir))
    return tuple(sorted(files))


def check_solver_step_outcomes(
    *,
    root: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
    add: Callable[..., None],
) -> None:
    level = "error" if strict else "warn"
    for path in _candidate_files(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeError):
            continue
        for class_node in (
            node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        ):
            if not _is_solver_class(class_node):
                continue
            step = next(
                (
                    node
                    for node in class_node.body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name == "step"
                ),
                None,
            )
            if step is None:
                continue
            aliases = {"StepOutcome"}
            for imp in tree.body:
                if isinstance(imp, ast.ImportFrom):
                    aliases.update(a.asname or a.name for a in imp.names if a.name == "StepOutcome")
            if not _outcome_annotation(step.returns, aliases):
                add(
                    diags,
                    level,
                    "solver-step-outcome-annotation",
                    f"{class_node.name}.step() must declare -> StepOutcome.",
                    path,
                    line=step.lineno,
                    column=step.col_offset + 1,
                )
            if _returns_none(step) or _can_fall_through(step.body):
                add(
                    diags,
                    level,
                    "solver-step-none-return",
                    (
                        f"{class_node.name}.step() has an explicit None return or a path that falls through; "
                        "return an explicit idle/rejected/cancelled StepOutcome."
                    ),
                    path,
                    line=step.lineno,
                    column=step.col_offset + 1,
                )


__all__ = ["check_solver_step_outcomes"]
