from nsgablack.project.doctor import run_project_doctor


def test_doctor_accepts_only_the_current_project_declarations(tmp_path):
    source = tmp_path / "pipeline"
    source.mkdir()
    (source / "score.py").write_text('class ScorePipeline:\n    context_requires = ()\n    context_provides = ("project.score",)\n    context_mutates = ()\n    context_cache = ()\n', encoding="utf-8")
    assert any(d.code == "contract-key-unknown" for d in run_project_doctor(tmp_path).diagnostics)
    manifest = tmp_path / "context_keys.json"
    manifest.write_text('["project.score"]', encoding="utf-8")
    assert not any(d.code == "contract-key-unknown" for d in run_project_doctor(tmp_path).diagnostics)
    manifest.unlink()
    assert any(d.code == "contract-key-unknown" for d in run_project_doctor(tmp_path).diagnostics)


def test_invalid_registry_is_a_doctor_diagnostic(tmp_path):
    (tmp_path / "context_keys.json").write_text('{', encoding="utf-8")
    report = run_project_doctor(tmp_path)
    assert report.error_count == 1
    assert report.diagnostics[0].code == "context-registry-invalid"
