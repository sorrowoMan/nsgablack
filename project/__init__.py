# -*- coding: utf-8 -*-
"""Project scaffolding and local catalog support."""

from __future__ import annotations

from .catalog import find_project_root, load_project_catalog, load_project_entries
from .doctor import format_doctor_report, run_project_doctor
from .scaffold import add_case, create_project, init_project

__all__ = [
    "find_project_root",
    "load_project_catalog",
    "load_project_entries",
    "run_project_doctor",
    "format_doctor_report",
    "create_project",
    "add_case",
    "init_project",
]
