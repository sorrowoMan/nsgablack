from nsgablack.project import run_project_doctor


def _runtime_private_call_source() -> str:
    return (
        "def call_runtime_private(solver):\n"
        "    solver.runtime._unsafe_private_hook()\n"
    )


def test_runtime_private_surface_scans_working_files(tmp_path):
    (tmp_path / "working_demo.py").write_text(_runtime_private_call_source(), encoding="utf-8")

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=True)
    rows = [d for d in report.diagnostics if d.code == "runtime-private-call"]

    assert rows
    assert all(d.level == "error" for d in rows)
    assert any("working_demo.py" in (d.path or "") for d in rows)


def test_runtime_private_surface_scans_build_solver_file(tmp_path):
    (tmp_path / "build_solver.py").write_text(
        "def build_solver():\n"
        "    class _Local:\n"
        "        runtime = None\n"
        "    solver = _Local()\n"
        "    solver.runtime._unsafe_private_hook()\n"
        "    return solver\n",
        encoding="utf-8",
    )

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=True)
    rows = [d for d in report.diagnostics if d.code == "runtime-private-call"]

    assert rows
    assert any("build_solver.py" in (d.path or "") for d in rows)


def test_runtime_private_surface_scans_utils_when_present(tmp_path):
    utils_dir = tmp_path / "utils"
    utils_dir.mkdir(parents=True)
    (utils_dir / "runtime_helper.py").write_text(_runtime_private_call_source(), encoding="utf-8")

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=True)
    rows = [d for d in report.diagnostics if d.code == "runtime-private-call"]

    assert rows
    assert any("runtime_helper.py" in (d.path or "") for d in rows)


def test_runtime_private_surface_skips_tests_by_default(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_runtime_private_demo.py").write_text(
        _runtime_private_call_source(),
        encoding="utf-8",
    )

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=True)
    rows = [d for d in report.diagnostics if d.code == "runtime-private-call"]

    assert not rows
