"""Scaffold structure checks used by project doctor."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, List, Sequence

from ..model import DoctorDiagnostic


def looks_like_scaffold_project(root: Path) -> bool:
    """Detect a formal Project or Case scaffold."""
    if (root / "build_solver.py").is_file() and (
        (root / ".case").is_file() or root.parent.name == "cases"
    ):
        return True
    if (root / "project_config.py").is_file() and (root / "cases").is_dir():
        return True
    return False


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
            "Skip scaffold hard-checks (no formal Project/Case scaffold detected).",
            root,
        )
        return

    for name in required_dirs:
        folder = root / name
        if not folder.is_dir():
            add(diags, "error", "missing-dir", f"Missing required directory: {name}", folder)

    for name in required_files:
        file_path = root / name
        if not file_path.is_file():
            add(diags, "error", "missing-file", f"Missing required file: {name}", file_path)

    if not (root / "README.md").is_file():
        add(
            diags,
            "warn",
            "missing-case-readme",
            "Case must keep its component, resource and I/O guidance in one README.md.",
            root / "README.md",
        )


_CASE_MARKER_FILES = {
    "build_solver.py",
    "build_trainer.py",
    "run_solver.py",
    "run_trainer.py",
}
_CASE_MARKER_DIRS = {
    "problem",
    "pipeline",
    "adapter",
    "plugins",
    "solver",
    "runtime",
    "evaluation",
    "bias",
}
_NON_CASE_DIR_NAMES = {
    "problem",
    "pipeline",
    "adapter",
    "plugins",
    "solver",
    "runtime",
    "evaluation",
    "bias",
    "assembly",
    "catalog",
    "case_scaffold",
    "config",
    "original",
    "assets",
    "docs",
}
_PROJECT_MARKER_FILES = {"project_config.py", "run_project.py"}


def check_standard_case_scaffolds(
    *,
    root: Path,
    diags: List[DoctorDiagnostic],
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
) -> None:
    """Validate unified Solver=Trainer case scaffold structure under examples/cases and cases."""

    container_roots = tuple(path for path in (root / "examples" / "cases", root / "cases") if path.is_dir())
    total = 0
    for container in container_roots:
        case_roots = tuple(_iter_case_roots(container))
        total += len(case_roots)
        for case_root in case_roots:
            _check_case_root_scaffold(case_root, diags=diags, add=add)
    if container_roots:
        add(
            diags,
            "info",
            "case-scaffold-scope",
            f"Validated {total} unified case scaffold roots.",
            root,
        )


def _iter_case_roots(container: Path) -> Iterable[Path]:
    candidates = [container]
    candidates.extend(path for path in container.rglob("*") if path.is_dir())
    for directory in sorted(candidates):
        if directory == container:
            continue
        rel_parts = directory.relative_to(container).parts
        if any(part in _NON_CASE_DIR_NAMES or part == "__pycache__" for part in rel_parts):
            continue
        child_files = {path.name for path in directory.iterdir() if path.is_file()}
        child_dirs = {path.name for path in directory.iterdir() if path.is_dir()}
        if _PROJECT_MARKER_FILES.issubset(child_files) and "cases" in child_dirs:
            continue
        # Ignore untracked/generated directory shells that contain only empty
        # component folders, caches, run output, or artifacts.  A real Case
        # candidate must contain at least one declarative/source file; otherwise
        # a local cache tree can manufacture Doctor errors for a Case that does
        # not exist in the repository.
        if not _contains_case_source(directory):
            continue
        if child_files & _CASE_MARKER_FILES or child_dirs & _CASE_MARKER_DIRS:
            yield directory


def _contains_case_source(directory: Path) -> bool:
    ignored = {"__pycache__", "runs", "artifacts", ".blackbase"}
    source_suffixes = {".py", ".toml", ".json", ".yaml", ".yml"}
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(directory)
        if any(part in ignored for part in relative.parts[:-1]):
            continue
        if path.suffix.lower() in source_suffixes:
            return True
    return False


def _check_case_root_scaffold(
    case_root: Path,
    *,
    diags: List[DoctorDiagnostic],
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
) -> None:
    build_solver = case_root / "build_solver.py"
    build_trainer = case_root / "build_trainer.py"
    run_solver = case_root / "run_solver.py"
    run_trainer = case_root / "run_trainer.py"

    if not build_solver.is_file():
        add(diags, "error", "case-missing-build-solver", "Case must use build_solver.py as canonical assembly entry.", build_solver)
    elif "def build_solver" not in _read_text(build_solver):
        add(diags, "error", "case-build-solver-missing-function", "build_solver.py must define build_solver().", build_solver)

    if build_trainer.is_file():
        if not build_solver.is_file():
            add(
                diags,
                "error",
                "case-build-trainer-without-build-solver",
                "build_trainer.py is only an alias and requires build_solver.py.",
                build_trainer,
            )
        _check_alias_file(
            build_trainer,
            diags=diags,
            add=add,
            required_tokens=("build_solver", "build_trainer"),
            forbidden_tokens=("def build_trainer", "def build_project_trainer"),
            code="case-build-trainer-not-alias",
            message="build_trainer.py must be a thin alias to build_solver.build_solver.",
        )

    if not run_solver.is_file():
        add(diags, "error", "case-missing-run-solver", "Case must use run_solver.py as canonical CLI entry.", run_solver)

    if run_trainer.is_file():
        if not run_solver.is_file():
            add(
                diags,
                "error",
                "case-run-trainer-without-run-solver",
                "run_trainer.py is only an alias and requires run_solver.py.",
                run_trainer,
            )
        _check_alias_file(
            run_trainer,
            diags=diags,
            add=add,
            required_tokens=("run_solver", "main"),
            forbidden_tokens=("build_trainer", "def main("),
            code="case-run-trainer-not-alias",
            message="run_trainer.py must be a thin alias to run_solver.main.",
        )

    legacy_capabilities = case_root / "capabilities"
    if legacy_capabilities.is_dir():
        add(diags, "error", "case-legacy-capabilities-dir", "Case-level capabilities/ is forbidden; use plugins/.", legacy_capabilities)

    legacy_representation = case_root / "representation"
    if legacy_representation.is_dir():
        add(
            diags,
            "error",
            "case-legacy-representation-dir",
            "Case-level representation/ is forbidden; use pipeline/representation/.",
            legacy_representation,
        )

    legacy_scaffold_json = case_root / "assembly" / "scaffold.json"
    if legacy_scaffold_json.is_file():
        add(
            diags,
            "error",
            "case-legacy-assembly-scaffold-json",
            "assembly/scaffold.json is forbidden; assembly logic belongs in build_solver.py.",
            legacy_scaffold_json,
        )

    pipeline_main = case_root / "pipeline" / "main.py"
    pipeline_module = case_root / "pipeline.py"
    if not pipeline_main.is_file() and not pipeline_module.is_file():
        add(
            diags,
            "warn",
            "case-pipeline-entry-recommended",
            "Recommended: add one canonical pipeline entry (pipeline/main.py or pipeline.py) and compose operators inside it.",
            case_root / "pipeline",
        )


def _check_alias_file(
    path: Path,
    *,
    diags: List[DoctorDiagnostic],
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
    required_tokens: tuple[str, ...],
    forbidden_tokens: tuple[str, ...],
    code: str,
    message: str,
) -> None:
    text = _read_text(path)
    if not all(token in text for token in required_tokens):
        add(diags, "error", code, message, path)
        return
    for token in forbidden_tokens:
        if token in text:
            add(diags, "error", code, message, path)
            return


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8-sig", errors="replace")
