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


def test_doctor_build_reports_invalid_runtime_snapshot(tmp_path: Path) -> None:
    project_root = create_project(tmp_path / "snapshot_project")
    case_root = add_case("invalid_snapshot", "solver", project_root=project_root)
    (case_root / "build_solver.py").write_text(
        "from threading import RLock\n"
        "from nsgablack.core import BlackBoxProblem\n"
        "from nsgablack.core.blank_solver import SolverBase\n"
        "from nsgablack.core.state.population_authority import PopulationAuthority\n"
        "class Problem(BlackBoxProblem):\n"
        "    def evaluate(self, candidate): return 0.0\n"
        "class InvalidSnapshot(PopulationAuthority):\n"
        "    name = 'invalid-snapshot'\n"
        "    def snapshot_step_state(self): return RLock()\n"
        "def build_solver(*, resource_context=None, component_overrides=None):\n"
        "    solver = SolverBase(Problem(dimension=1, bounds=[(-1, 1)]))\n"
        "    solver.register_state_participant(InvalidSnapshot())\n"
        "    return solver\n",
        encoding="utf-8",
    )

    report = run_project_doctor(case_root, strict=True, instantiate_solver=True)

    errors = [item for item in report.diagnostics if item.code == "runtime-participant-snapshot-invalid"]
    assert len(errors) == 1
    assert errors[0].level == "error"
    assert "invalid-snapshot" in errors[0].message
    assert "Mapping" in errors[0].message
    assert not any(item.code == "build-entry-instantiate-failed" for item in report.diagnostics)
