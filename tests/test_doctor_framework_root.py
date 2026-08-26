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


def test_ml_framework_root_catalog_is_not_treated_as_case_local_registry(tmp_path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='ml-demo'\n", encoding="utf-8")
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "problem.py").write_text("", encoding="utf-8")
    (tmp_path / "integrations").mkdir()
    (tmp_path / "integrations" / "nsgablack_control.py").write_text("", encoding="utf-8")
    (tmp_path / "catalog" / "entries").mkdir(parents=True)
    (tmp_path / "catalog" / "entries" / "assembly.toml").write_text(
        "[[entry]]\nkey='assembly.demo'\n",
        encoding="utf-8",
    )

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=True)

    assert any(d.code == "framework-registry-scope" for d in report.diagnostics)
    assert not any(d.code == "registry-load-failed" for d in report.diagnostics)


def test_empty_generated_component_shell_is_not_a_case_scaffold(tmp_path) -> None:
    shell = tmp_path / "examples" / "cases" / "ghost" / "cases" / "ghost"
    for name in ("problem", "pipeline", "adapter", "plugins", "runtime"):
        (shell / name).mkdir(parents=True, exist_ok=True)
    (shell / "__pycache__").mkdir()
    (shell / "__pycache__" / "generated.pyc").write_bytes(b"cache")

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=True)

    assert not any(
        diagnostic.code in {"case-missing-build-solver", "case-missing-run-solver"}
        for diagnostic in report.diagnostics
    )


def test_contract_keys_preserve_canonical_case_and_strict_is_valid(tmp_path) -> None:
    pipeline = tmp_path / "pipeline"
    pipeline.mkdir()
    (pipeline / "demo.py").write_text(
        "class DemoPipeline:\n"
        "    context_requires = ('data.X_train',)\n"
        "    context_optional = ()\n"
        "    context_provides = ()\n"
        "    context_mutates = ()\n"
        "    context_cache = ()\n"
        "    requires_metrics = ()\n"
        "    metrics_fallback = 'strict'\n"
        "    context_notes = 'test'\n",
        encoding="utf-8",
    )

    report = run_project_doctor(tmp_path, instantiate_solver=False, strict=True)

    assert not any(d.code == "contract-key-unknown" for d in report.diagnostics)
    assert not any(d.code == "metrics-fallback-invalid" for d in report.diagnostics)
