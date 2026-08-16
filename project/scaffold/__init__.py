"""nsgablack semantic templates over the shared blackbase scaffold substrate."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

from blackbase.project.scaffold import add_component
from blackbase.project.scaffold import add_case as _add_case
from blackbase.project.scaffold import create_project as _create_project

from .check_output import build_solver_check_payload, format_solver_check, print_solver_check

_SCAFFOLD_ROOT = Path(__file__).resolve().parent
_PROJECT_TEMPLATE = _SCAFFOLD_ROOT / "project_template"
_NSGA_TEMPLATE_BY_KIND = {
    "solver": _SCAFFOLD_ROOT / "case_template_solver",
    "trainer": _SCAFFOLD_ROOT / "case_template_trainer",
}


def create_project(project_name: str | Path, *, force: bool = False):
    return _create_project(
        project_name,
        force=bool(force),
        framework="nsgablack",
        project_template=_PROJECT_TEMPLATE,
    )


def add_case(
    case_name: str,
    case_type: str,
    *,
    framework: str = "nsgablack",
    project_root: str | Path | None = None,
):
    return _add_case(
        case_name,
        case_type,
        framework=str(framework or "nsgablack"),
        project_root=project_root,
        template_by_kind=_template_by_kind(str(framework or "nsgablack")),
    )


def _template_by_kind(framework: str) -> dict[str, Path]:
    if str(framework).strip().lower() == "mlblack":
        ml_templates = _mlblack_templates()
        if ml_templates:
            return ml_templates
    return dict(_NSGA_TEMPLATE_BY_KIND)


def _mlblack_templates() -> dict[str, Path]:
    spec = importlib.util.find_spec("mlblack.project.scaffold")
    if spec is None or spec.origin is None:
        return {}
    root = Path(spec.origin).resolve().parent
    return {
        "solver": root / "solver_case_template",
        "trainer": root / "trainer_case_template",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage nsgablack projects and cases.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    parser_new = subparsers.add_parser("new", help="Create a new project.")
    parser_new.add_argument("project_name", type=str)
    parser_new.add_argument("--force", action="store_true")
    parser_add = subparsers.add_parser("add-case", help="Add a new case to the current project.")
    parser_add.add_argument("case_name", type=str)
    parser_add.add_argument("--type", choices=("solver", "trainer"), required=True)
    parser_add.add_argument("--framework", choices=("nsgablack", "mlblack"), default="nsgablack")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "new":
        create_project(args.project_name, force=bool(args.force))
        return 0
    if args.command == "add-case":
        add_case(args.case_name, args.type, framework=args.framework)
        return 0
    return 2


init_project = create_project

__all__ = [
    "add_case",
    "add_component",
    "build_solver_check_payload",
    "create_project",
    "format_solver_check",
    "init_project",
    "main",
    "print_solver_check",
]


if __name__ == "__main__":
    raise SystemExit(main())
