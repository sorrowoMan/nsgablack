"""Core building blocks for project doctor."""

from .model import (
    DoctorDiagnostic,
    DoctorReport,
    add_diagnostic,
    format_doctor_report_text,
    iter_diagnostics_by_level,
)

__all__ = [
    "DoctorDiagnostic",
    "DoctorReport",
    "add_diagnostic",
    "format_doctor_report_text",
    "iter_diagnostics_by_level",
]

