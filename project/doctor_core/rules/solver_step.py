"""Static enforcement for the strict Solver ``step`` result contract."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Callable, List

from ..model import DoctorDiagnostic


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


def _candidate_files(root: Path) -> tuple[Path, ...]:
    files: set[Path] = set()
    if (root / "core" / "blank_solver.py").is_file():
        files.update((root / "core").rglob("*.py"))
    # A custom Solver is allowed directly in a canonical build_solver.py or
    # in any package below that Case root.  Discover the scaffold boundary
    # instead of guessing from a directory literally named ``solver``.
    for build_file in root.rglob("build_solver.py"):
        relative_parts = build_file.relative_to(root).parts
        if any(
            part in {".git", ".venv", "venv", "site-packages"}
            for part in relative_parts
        ):
            continue
        case_root = build_file.parent
        files.update(case_root.rglob("*.py"))
    root_builder = root / "build_solver.py"
    if root_builder.is_file():
        files.add(root_builder)
    solver_dir = root / "solver"
    if solver_dir.is_dir():
        files.update(solver_dir.rglob("*.py"))
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
            annotation = "" if step.returns is None else ast.unparse(step.returns)
            if "StepOutcome" not in annotation:
                add(
                    diags,
                    level,
                    "solver-step-outcome-annotation",
                    f"{class_node.name}.step() must declare -> StepOutcome.",
                    path,
                )
            if _returns_none(step):
                add(
                    diags,
                    level,
                    "solver-step-none-return",
                    (
                        f"{class_node.name}.step() has a bare/None return; "
                        "return an explicit idle/rejected/cancelled StepOutcome."
                    ),
                    path,
                )


__all__ = ["check_solver_step_outcomes"]
