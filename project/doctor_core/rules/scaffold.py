"""Scaffold structure checks used by project doctor."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Sequence

from ..model import DoctorDiagnostic


def looks_like_scaffold_project(root: Path) -> bool:
    return (root / "project_registry.py").is_file() or (root / "build_solver.py").is_file()


def check_structure(
    *,
    root: Path,
    diags: List[DoctorDiagnostic],
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
    required_dirs: Sequence[str],
    required_files: Sequence[str],
) -> None:
    if not looks_like_scaffold_project(root):
        add(
            diags,
            "info",
            "structure-skip",
            "Skip scaffold hard-checks (no project_registry.py/build_solver.py detected).",
            root,
        )
        return

    for name in required_dirs:
        folder = root / name
        if not folder.is_dir():
            add(diags, "error", "missing-dir", f"Missing required directory: {name}", folder)
        elif not (folder / "README.md").is_file():
            add(diags, "warn", "missing-folder-readme", f"Recommended: add {name}/README.md", folder / "README.md")

    for name in required_files:
        file_path = root / name
        if not file_path.is_file():
            add(diags, "error", "missing-file", f"Missing required file: {name}", file_path)

    if not (root / "START_HERE.md").is_file():
        add(diags, "warn", "missing-start-here", "Recommended: add START_HERE.md onboarding file", root / "START_HERE.md")
    if not (root / "COMPONENT_REGISTRATION.md").is_file():
        add(
            diags,
            "warn",
            "missing-component-registration-guide",
            "Recommended: add COMPONENT_REGISTRATION.md to explain what/why/how of local Catalog registration",
            root / "COMPONENT_REGISTRATION.md",
        )

    if not (root / ".nsgablack-project").is_file():
        return

    contract_card_template = root / "docs" / "contracts" / "COMPONENT_CONTRACT_TEMPLATE.md"
    if not contract_card_template.is_file():
        add(
            diags,
            "warn",
            "missing-contract-card-template",
            "Recommended: add docs/contracts/COMPONENT_CONTRACT_TEMPLATE.md for component contract cards.",
            contract_card_template,
        )

    test_matrix_template = root / "tests" / "templates" / "README.md"
    if not test_matrix_template.is_file():
        add(
            diags,
            "warn",
            "missing-component-test-matrix-template",
            "Recommended: add tests/templates/README.md for smoke/contract/roundtrip/strict-fault matrix.",
            test_matrix_template,
        )
