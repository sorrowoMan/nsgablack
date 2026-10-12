"""Optimization scaffold guidance; structural rules belong to BlackBase."""
from pathlib import Path
from blackbase.project.doctor_scope import discover_doctor_roots, is_case_candidate, is_project_candidate


def looks_like_scaffold_project(root: Path) -> bool:
    return is_project_candidate(root) or is_case_candidate(root)


def check_standard_case_scaffolds(*, root, diags, add) -> None:
    _, cases = discover_doctor_roots(root)
    for case_root in cases:
        if not (case_root / "pipeline" / "main.py").is_file() and not (case_root / "pipeline.py").is_file():
            add(diags, "warn", "case-pipeline-entry-recommended",
                "Recommended: add one canonical pipeline entry (pipeline/main.py or pipeline.py) and compose operators inside it.",
                case_root / "pipeline")
