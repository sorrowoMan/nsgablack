"""Doctor report models and shared formatting helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from blackbase.project.doctor import DoctorDiagnostic, DoctorReport


def add_diagnostic(
    diagnostics: List[DoctorDiagnostic],
    level: str,
    code: str,
    message: str,
    path: Path | None = None,
) -> None:
    diagnostics.append(
        DoctorDiagnostic(
            level=level,
            code=code,
            message=message,
            path=str(path) if path is not None else None,
        )
    )


def format_doctor_report_text(report: DoctorReport) -> str:
    lines: List[str] = []
    lines.append(f"Project doctor: {report.project_root}")
    lines.append(
        f"summary: errors={report.error_count} warnings={report.warn_count} infos={report.info_count}"
    )
    for diag in report.diagnostics:
        prefix = {"error": "[ERROR]", "warn": "[WARN]", "info": "[INFO]"}.get(diag.level, "[INFO]")
        location = f" ({diag.path})" if diag.path else ""
        lines.append(f"{prefix} {diag.code}: {diag.message}{location}")
    return "\n".join(lines)


def iter_diagnostics_by_level(
    diagnostics: Iterable[DoctorDiagnostic],
    level: str,
) -> List[DoctorDiagnostic]:
    return [diag for diag in diagnostics if diag.level == level]

