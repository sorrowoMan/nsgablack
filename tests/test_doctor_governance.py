from pathlib import Path
from types import SimpleNamespace

import pytest

from blackbase.project.doctor import DoctorDiagnostic, DoctorReport, run_common_project_doctor
from importlib import import_module
from nsgablack.__main__ import main
from nsgablack.project.doctor import run_project_doctor

cli = import_module(main.__module__)
_doctor_exit_code = cli._doctor_exit_code
_doctor_report_payload = cli._doctor_report_payload


def make_case(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / ".case").write_text("kind = solver\n", encoding="utf-8")
    (root / "build_solver.py").write_text(
        "def build_solver(*, resource_context=None, component_overrides=None):\n"
        "    return object()\n", encoding="utf-8")
    return root


@pytest.mark.parametrize("strict,threshold,errors,warnings,expected", [
    (False, "error", 0, 1, 0), (False, "warn", 0, 1, 1),
    (True, "error", 0, 1, 1), (False, "error", 1, 0, 2),
    (True, "warn", 1, 1, 2), (False, "warn", 0, 0, 0),
])
def test_failure_threshold(strict, threshold, errors, warnings, expected):
    report = SimpleNamespace(error_count=errors, warn_count=warnings)
    assert _doctor_exit_code(report, strict=strict, fail_on=threshold) == expected


def test_message_numbers_never_become_source_positions(tmp_path):
    report = DoctorReport(tmp_path, (DoctorDiagnostic("warn", "example", "nested.py line 900 @L32", str(tmp_path)),))
    row = _doctor_report_payload(report)["diagnostics"][0]
    assert row["line"] is None and row["column"] is None


def test_cli_exposes_catalog_profile_and_failure_threshold(monkeypatch, tmp_path, capsys):
    project_api = import_module(cli.__package__ + ".project")
    captured = {}

    def doctor(**kwargs):
        captured.update(kwargs)
        return DoctorReport(tmp_path, (DoctorDiagnostic("warn", "demo", "warning"),))

    monkeypatch.setattr(project_api, "run_project_doctor", doctor)
    assert main(["project", "doctor", "--catalog-audit", "--profile", "default", "--fail-on", "warn", "--format", "json"]) == 1
    assert captured["catalog_audit"] and captured["catalog_profile"] == "default"
    assert '"failure_threshold": "warn"' in capsys.readouterr().out


def test_root_checks_cases_and_build_cleans_up_without_running(tmp_path):
    project = tmp_path / "examples" / "cases" / "demo"
    case = make_case(project / "cases" / "search")
    (case.parent / "__init__.py").write_text("", encoding="utf-8")
    (case / "__init__.py").write_text("", encoding="utf-8")
    (project / "project_config.py").write_text("STAGES = []\n", encoding="utf-8")
    (project / "run_project.py").write_text("", encoding="utf-8")
    (case / "build_solver.py").write_text(
        "from pathlib import Path\n"
        "class Case:\n"
        "    def run(self): raise AssertionError('Doctor must not run')\n"
        "    def close(self): Path(__file__).with_name('closed').write_text('yes')\n"
        "def build_solver(*, resource_context=None, component_overrides=None):\n"
        "    Path(__file__).with_name('built').write_text(str(resource_context['grant']['threads']))\n"
        "    return Case()\n", encoding="utf-8")
    report = run_project_doctor(tmp_path, strict=True)
    assert not (case / "built").exists()
    assert any(c.check == "case-build" and c.status == "skipped" and c.scope == str(case) for c in report.coverage)
    report = run_project_doctor(tmp_path, strict=True, instantiate_solver=True)
    failures = [(d.code, d.message) for d in report.diagnostics if d.code in {"build-entry-import-failed", "build-entry-instantiate-failed"}]
    assert failures == []
    assert (case / "built").read_text() == "1"
    assert (case / "closed").read_text() == "yes"
    assert not any(d.code in {"build-entry-resource-binding-stale", "build-entry-instantiate-failed", "build-entry-cleanup-failed"} for d in report.diagnostics)
    assert any(c.check == "case-build" and c.status == "completed" for c in report.coverage)


def test_shared_rules_are_the_only_structural_authority(tmp_path):
    case = make_case(tmp_path / "cases" / "demo")
    (case / "capabilities").mkdir()
    (case / "build_solver.py").write_text("# def build_solver is not a function\n", encoding="utf-8")
    rows = run_project_doctor(tmp_path).diagnostics
    assert sum(d.code == "case-capabilities-dir" for d in rows) == 1
    assert not any(d.code == "case-legacy-capabilities-dir" for d in rows)
    assert sum(d.code == "case-build-missing-function" for d in rows) == 1
    direct = run_common_project_doctor(case)
    assert {d.code for d in direct.diagnostics if d.level == "error"} <= {d.code for d in rows}


def test_shared_ast_accepts_spacing_and_ignores_comment_tokens(tmp_path):
    case = make_case(tmp_path)
    (case / "build_solver.py").write_text(
        '# backward compatible documentation\ndef  build_solver(*, resource_context=None, component_overrides=None):\n    return object()\n', encoding="utf-8")
    (case / "build_trainer.py").write_text(
        '# def build_trainer\nfrom .build_solver import build_solver as build_trainer\n', encoding="utf-8")
    (case / "run_trainer.py").write_text(
        '# def main(\nfrom .run_solver import main\n', encoding="utf-8")
    codes = {d.code for d in run_common_project_doctor(case, strict=True).diagnostics}
    assert not codes & {"case-build-missing-function", "case-build-trainer-not-thin-alias", "case-run-trainer-not-thin-alias", "case-compatibility-source-forbidden"}


def test_large_context_rule_is_connected_with_aliases_and_locations(tmp_path):
    (tmp_path / "demo.py").write_text(
        "def f(context):\n    c = context\n    c['population']: object = [1]\n"
        "    c.update(history=[2])\n    c = {}\n    c['population'] = [3]\n", encoding="utf-8")
    rows = [d for d in run_project_doctor(tmp_path, strict=True).diagnostics if d.code == "large-object-in-context"]
    assert {d.line for d in rows} == {3, 4}
    assert all(d.level == "error" for d in rows)


def test_framework_broad_exception_is_checked(tmp_path):
    (tmp_path / "demo.py").write_text("try:\n    f()\nexcept Exception:\n    pass\n", encoding="utf-8")
    rows = run_project_doctor(tmp_path, strict=True).diagnostics
    assert any(d.code == "broad-except-swallow" and d.line == 3 for d in rows)


def test_solver_alias_rebinding_and_scope(tmp_path):
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    (plugins / "demo.py").write_text(
        "def bad(solver):\n    s = solver\n    s.population = [1]\n"
        "    s = object()\n    s.population = [2]\n"
        "def unrelated(s):\n    s.population = [3]\n", encoding="utf-8")
    rows = run_project_doctor(tmp_path, strict=True).diagnostics
    hits = [d for d in rows if d.code == "runtime-bypass-write"]
    assert len(hits) == 1 and hits[0].line == 3
    assert "@L5" not in hits[0].message and "@L7" not in hits[0].message


@pytest.mark.parametrize("body,expected", [
    ("        pass\n", True),
    ("        if self.ready:\n            return SO(status='idle')\n", True),
    ("        if self.ready:\n            return SO(status='idle')\n        else:\n            raise RuntimeError()\n", False),
])
def test_step_alias_annotation_and_fallthrough(tmp_path, body, expected):
    case = make_case(tmp_path)
    (case / "solver").mkdir()
    (case / "solver" / "demo.py").write_text(
        "from nsgablack.core import StepOutcome as SO, ComposableSolver\n"
        "class Demo(ComposableSolver):\n    def step(self) -> SO:\n" + body, encoding="utf-8")
    codes = {d.code for d in run_project_doctor(case, strict=True).diagnostics}
    assert "solver-step-outcome-annotation" not in codes
    assert ("solver-step-none-return" in codes) is expected


def test_order_category_does_not_depend_on_message():
    from nsgablack.core.solver_helpers import ComponentOrderError
    from nsgablack.project.doctor_core.rules.component_order import _classify_component_order_error
    assert _classify_component_order_error(ComponentOrderError("arbitrary wording", code="cycle")) == "component-order-cycle"


def test_default_case_check_really_imports_lazy_builder(tmp_path):
    case = make_case(tmp_path / "cases" / "broken")
    (case.parent / "__init__.py").write_text("", encoding="utf-8")
    (case / "__init__.py").write_text("", encoding="utf-8")
    (case / "build_solver.py").write_text("raise RuntimeError('broken import')\n", encoding="utf-8")
    report = run_project_doctor(tmp_path)
    assert any(d.code == "build-entry-import-failed" for d in report.diagnostics)


def test_source_scope_does_not_leak_into_sys_path(tmp_path):
    import sys
    before = list(sys.path)
    run_project_doctor(tmp_path)
    assert sys.path == before


def test_cleanup_failure_is_reported(tmp_path):
    case = make_case(tmp_path)
    (case / "build_solver.py").write_text(
        "class Case:\n    def close(self): raise RuntimeError('close failed')\n"
        "def build_solver(*, resource_context=None, component_overrides=None):\n    return Case()\n", encoding="utf-8")
    rows = run_project_doctor(case, instantiate_solver=True).diagnostics
    assert any(d.code == "build-entry-cleanup-failed" and d.level == "error" for d in rows)


def test_catalog_parameter_only_failure_is_reported(monkeypatch):
    from nsgablack.project import doctor
    from nsgablack.catalog.audit import CatalogAuditReport
    seen = {}

    def audit(**kwargs):
        seen.update(kwargs)
        return CatalogAuditReport(total=1, import_failures=0, context_failures=0,
                                  method_failures=0, param_failures=1, issues=[], import_unchecked=1)

    monkeypatch.setattr(doctor, "audit_catalog", audit)
    rows = []
    doctor._check_catalog_audit(rows, profile="default")
    assert seen == {"profile": "default", "runtime": False}
    assert [d.code for d in rows] == ["catalog-audit-scope", "catalog-audit-issues"]


def test_unparseable_source_cannot_report_clean_context_scan(tmp_path):
    (tmp_path / "broken.py").write_text("def incomplete(:\n", encoding="utf-8")
    report = run_project_doctor(tmp_path, strict=True)
    assert sum(d.code == "source-parse-failed" and d.line == 1 for d in report.diagnostics) == 1
    assert not any(d.code == "large-object-context-scan-ok" for d in report.diagnostics)


def test_generated_build_output_does_not_duplicate_source_findings(tmp_path):
    source = "try:\n    f()\nexcept Exception:\n    pass\n"
    (tmp_path / "demo.py").write_text(source, encoding="utf-8")
    build = tmp_path / "build" / "lib"
    build.mkdir(parents=True)
    (build / "demo.py").write_text(source, encoding="utf-8")
    (build / "broken.py").write_bytes(b"\xff\xff")
    rows = run_project_doctor(tmp_path, strict=True).diagnostics
    assert sum(d.code == "broad-except-swallow" for d in rows) == 1
    assert not any(d.code == "source-parse-failed" for d in rows)
