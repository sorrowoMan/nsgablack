# -*- coding: utf-8 -*-
"""Project scaffolding and local catalog support."""

from __future__ import annotations

from .catalog import find_project_root, load_project_catalog, load_project_entries
from .case_components import apply_solver_component_overrides
from .doctor import format_doctor_report, run_project_doctor
from .project_runner import execute_project, run_project
from .scaffold import add_case, add_component, create_project

__all__ = [
    "find_project_root",
    "load_project_catalog",
    "load_project_entries",
    "run_project_doctor",
    "format_doctor_report",
    "run_project",
    "execute_project",
    "create_project",
    "add_case",
    "add_component",
    "apply_solver_component_overrides",
]
