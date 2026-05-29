"""Unified scaffold system for nsgablack and mlblack.

Solver and Trainer cases use the identical unified template.
The --type flag affects only catalog registration semantics.
"""

import argparse
import shutil
from pathlib import Path

# Path to the unified case template (identical for solver and trainer).
_CASE_TEMPLATE = Path(__file__).parent / "case_template"


def create_project(project_name: str, *, force: bool = False):
    """Creates a new project scaffold.

    Args:
        project_name: Name or path for the new project directory.
        force: If True, overwrite existing directory.
    """
    project_path = Path(project_name).resolve()
    if project_path.exists():
        if force:
            shutil.rmtree(project_path)
        else:
            print(f"Error: Directory '{project_name}' already exists. Use --force to overwrite.")
            return

    template_path = Path(__file__).parent / "project_template"
    shutil.copytree(template_path, project_path)

    # Rename template files
    for f in project_path.glob("**/*.template"):
        f.rename(f.with_suffix(""))

    print(f"Successfully created project '{project_name}'")
    return project_path


def add_case(case_name: str, case_type: str):
    """Adds a new case to an existing project.

    Solver and Trainer cases use the identical unified template.
    The --type flag affects only catalog registration semantics,
    not the directory structure.
    """
    project_root = Path.cwd()
    if not (project_root / "project_config.py").exists():
        print("Error: Not inside a project root. Please `cd` into your project directory.")
        return

    case_path = project_root / "cases" / case_name
    if case_path.exists():
        print(f"Error: Case '{case_name}' already exists.")
        return

    if case_type not in ("solver", "trainer"):
        print(f"Error: Unknown case type '{case_type}'. Use 'solver' or 'trainer'.")
        return

    # Unified template -- identical for solver and trainer.
    shutil.copytree(_CASE_TEMPLATE, case_path)

    # Rename template files
    for f in case_path.glob("**/*.template"):
        f.rename(f.with_suffix(""))

    # --type affects catalog registration kind only.
    kind = "solver" if case_type == "solver" else "trainer"
    _write_case_marker(case_path, case_name=case_name, kind=kind)

    print(f"Successfully added {case_type} case '{case_name}' (kind={kind})")


def _write_case_marker(case_path, *, case_name, kind):
    """Write a lightweight case marker for catalog discovery."""
    marker = case_path / ".case"
    marker.write_text(
        f"name = {case_name}\nkind = {kind}\n",
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description="Manage nsgablack projects and cases.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # New project command
    parser_new = subparsers.add_parser("new", help="Create a new project.")
    parser_new.add_argument("project_name", type=str, help="The name of the new project.")

    # Add case command
    parser_add = subparsers.add_parser("add-case", help="Add a new case to the current project.")
    parser_add.add_argument("case_name", type=str, help="The name of the new case.")
    parser_add.add_argument("--type", type=str, choices=["solver", "trainer"], required=True, help="The type of the case.")

    args = parser.parse_args()

    if args.command == "new":
        create_project(args.project_name)
    elif args.command == "add-case":
        add_case(args.case_name, args.type)


# Backward-compat alias (legacy name)
init_project = create_project

if __name__ == "__main__":
    main()
