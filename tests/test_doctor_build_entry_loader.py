from pathlib import Path

from nsgablack.project import add_case, create_project, run_project_doctor
from nsgablack.project.doctor_core.rules.build_solver import _load_module_from_file


def test_doctor_build_entry_loader_supports_dataclasses(tmp_path: Path) -> None:
    source = tmp_path / "build_solver.py"
    source.write_text(
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class Demo:\n"
        "    value: int = 1\n"
        "def build_solver():\n"
        "    return Demo()\n",
        encoding="utf-8",
    )

    module = _load_module_from_file("nsgablack_doctor_dataclass_test", source)

    assert module.build_solver().value == 1


def test_trainer_doctor_uses_canonical_build_solver_entry(tmp_path: Path) -> None:
    project_root = create_project(tmp_path / "trainer_project")
    case_root = add_case("trainer_case", "trainer", project_root=project_root)
    (case_root / "build_trainer.py").write_text(
        "raise RuntimeError('Doctor must not import build_trainer')\n",
        encoding="utf-8",
    )

    report = run_project_doctor(project_root, instantiate_solver=False)
    entries = [item for item in report.diagnostics if item.code == "build-entry-found"]

    assert entries
    assert all("build_solver" in item.message for item in entries)
    assert not any(item.code == "build-entry-import-failed" for item in report.diagnostics)
