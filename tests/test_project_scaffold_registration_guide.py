from nsgablack.project import init_project, run_project_doctor


def test_init_project_creates_component_registration_guide(tmp_path):
    root = init_project(tmp_path / "demo_project")
    guide = root / "COMPONENT_REGISTRATION.md"
    assert guide.is_file()
    text = guide.read_text(encoding="utf-8")
    assert "Why register components" in text
    assert "project_registry.py" in text


def test_project_doctor_warns_when_registration_guide_missing(tmp_path):
    root = init_project(tmp_path / "demo_project")
    guide = root / "COMPONENT_REGISTRATION.md"
    guide.unlink()

    report = run_project_doctor(root, instantiate_solver=False)
    codes = {d.code for d in report.diagnostics}
    assert "missing-component-registration-guide" in codes

