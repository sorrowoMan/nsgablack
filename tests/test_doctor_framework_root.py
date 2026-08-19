from __future__ import annotations

from nsgablack.project import run_project_doctor


def test_framework_root_catalog_is_not_treated_as_case_local_registry(tmp_path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "blank_solver.py").write_text("", encoding="utf-8")
    (tmp_path / "catalog" / "entries").mkdir(parents=True)
    (tmp_path / "catalog" / "entries" / "adapter.toml").write_text(
        "[[entry]]\nkey='adapter.demo'\n",
        encoding="utf-8",
    )
    (tmp_path / "project").mkdir()
    (tmp_path / "project" / "doctor.py").write_text("", encoding="utf-8")

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=True)

    assert any(d.code == "framework-registry-scope" for d in report.diagnostics)
    assert not any(d.code == "registry-load-failed" for d in report.diagnostics)
