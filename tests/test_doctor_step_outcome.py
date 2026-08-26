from pathlib import Path

from nsgablack.project.doctor import run_project_doctor


def _case_root(tmp_path: Path, source: str) -> Path:
    (tmp_path / "build_solver.py").write_text(
        "def build_solver(*, resource_context=None, component_overrides=None):\n"
        "    return object()\n",
        encoding="utf-8",
    )
    solver_dir = tmp_path / "solver"
    solver_dir.mkdir()
    (solver_dir / "custom.py").write_text(source, encoding="utf-8")
    return tmp_path


def test_doctor_rejects_legacy_none_step(tmp_path: Path) -> None:
    root = _case_root(
        tmp_path,
        "from nsgablack.core import ComposableSolver\n"
        "class CustomSolver(ComposableSolver):\n"
        "    def step(self):\n"
        "        return None\n",
    )
    report = run_project_doctor(root, strict=True)
    codes = {item.code for item in report.diagnostics}
    assert "solver-step-outcome-annotation" in codes
    assert "solver-step-none-return" in codes


def test_doctor_accepts_explicit_step_outcome(tmp_path: Path) -> None:
    root = _case_root(
        tmp_path,
        "from nsgablack.core import ComposableSolver, StepOutcome\n"
        "class CustomSolver(ComposableSolver):\n"
        "    def step(self) -> StepOutcome:\n"
        "        return StepOutcome(status='idle', reason='no_work')\n",
    )
    report = run_project_doctor(root, strict=True)
    codes = {item.code for item in report.diagnostics}
    assert "solver-step-outcome-annotation" not in codes
    assert "solver-step-none-return" not in codes


def test_doctor_scans_custom_solver_defined_in_root_build_solver(tmp_path: Path) -> None:
    (tmp_path / "build_solver.py").write_text(
        "from nsgablack.core import ComposableSolver\n"
        "class InlineSolver(ComposableSolver):\n"
        "    def step(self):\n"
        "        return None\n"
        "def build_solver(*, resource_context=None, component_overrides=None):\n"
        "    return object()\n",
        encoding="utf-8",
    )

    report = run_project_doctor(tmp_path, strict=True)
    codes = {item.code for item in report.diagnostics}

    assert "solver-step-outcome-annotation" in codes
    assert "solver-step-none-return" in codes
