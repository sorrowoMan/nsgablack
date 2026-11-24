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


def test_runtime_surface_prunes_ignored_trees_before_visiting_them(tmp_path, monkeypatch):
    import os
    from pathlib import Path
    from nsgablack.project.doctor_core.rules import runtime_surface
    for folder in (tmp_path/".pytest_cache/deep", tmp_path/"project/utils", tmp_path/"project/case"):
        folder.mkdir(parents=True)
        (folder/"working_example.py").write_text(_runtime_private_call_source(), encoding="utf-8")
    (tmp_path/"project/utils/helper.py").write_text(_runtime_private_call_source(), encoding="utf-8")
    original = os.walk
    visited = []
    def walk(*args, **kwargs):
        for directory, dirs, files in original(*args, **kwargs):
            visited.append(Path(directory))
            yield directory, dirs, files
    monkeypatch.setattr(runtime_surface.os, "walk", walk)
    files=list(runtime_surface._iter_runtime_surface_files(root=tmp_path,
        file_patterns=("working_*.py", "build_solver.py"), include_utils=True,
        skip_dir_names={".pytest_cache"}, skip_tests=True))
    assert all(".pytest_cache" not in path.parts for path in visited)
    assert {str(p.relative_to(tmp_path)).replace('\\','/') for p in files} == {
        "project/utils/helper.py", "project/utils/working_example.py", "project/case/working_example.py"}
