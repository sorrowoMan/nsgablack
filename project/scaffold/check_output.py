"""Compatibility names for the shared blackbase Case check reporter."""

from blackbase.project.check_output import (
    build_case_check_payload as build_solver_check_payload,
    format_case_check as format_solver_check,
    print_case_check as print_solver_check,
)


__all__ = ["build_solver_check_payload", "format_solver_check", "print_solver_check"]
