"""Doctor report models and shared formatting helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence


@dataclass(frozen=True)
class DoctorDiagnostic:
    """Single doctor diagnostic entry."""

    level: str  # info / warn / error
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class DoctorReport:
    """Doctor report for one project root."""

    project_root: Path
    diagnostics: Sequence[DoctorDiagnostic]

    @property
    def error_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.level == "error")

    @property
    def warn_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.level == "warn")

    @property
    def info_count(self) -> int:
        return sum(1 for d in self.diagnostics if d.level == "info")


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

