"""Explicit bridge to the production-scheduling domain Case.

The two examples are separate Projects, so their Case directories are not
siblings.  This module owns compatibility discovery and keeps path mutation
out of solver assembly.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Optional
from blackbase.project import case_import_context


def resolve_production_case_dir(explicit: str | Path | None = None) -> Path:
    if explicit is not None:
        candidate = Path(explicit).expanduser().resolve()
        return _validate_case_dir(candidate)

    origin = Path(__file__).resolve()
    for ancestor in origin.parents:
        candidate = ancestor / "production_scheduling" / "cases" / "production_scheduling"
        if (candidate / "refactor_data.py").is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        "Unable to locate examples/cases/production_scheduling/cases/production_scheduling; "
        "inject an explicit production Case path through the bridge."
    )


def ensure_production_case_importable(explicit: str | Path | None = None) -> Path:
    raise RuntimeError("use blackbase.project.case_import_context for scoped Case imports")


def load_production_case_data(
    *,
    bom_path: Optional[str],
    supply_path: Optional[str],
    machines: int,
    materials: int,
    days: int,
    production_case_dir: str | Path | None = None,
):
    case_dir = resolve_production_case_dir(production_case_dir)
    with case_import_context(case_dir.parents[1], case_dir.name):
        load_production_data = importlib.import_module("refactor_data").load_production_data
        return load_production_data(
            base_dir=case_dir,
            bom_path=Path(bom_path) if bom_path else None,
            supply_path=Path(supply_path) if supply_path else None,
            machines=int(machines),
            materials=int(materials),
            days=int(days),
            fallback=False,
        )


def _validate_case_dir(candidate: Path) -> Path:
    if not (candidate / "refactor_data.py").is_file():
        raise FileNotFoundError(f"Not a production_scheduling Case directory: {candidate}")
    return candidate


__all__ = [
    "ensure_production_case_importable",
    "load_production_case_data",
    "resolve_production_case_dir",
]
