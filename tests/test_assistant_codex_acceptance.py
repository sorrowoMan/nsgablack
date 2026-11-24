from pathlib import Path
import hashlib
import json
from types import SimpleNamespace
import pytest

from nsgablack.catalog import assistant_codex_acceptance as acceptance


def test_codex_process_does_not_inherit_unrelated_credentials(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "private-canary")
    monkeypatch.setenv("OTHER_SERVICE_TOKEN", "other-private-canary")
    env = acceptance._environment(False)
    assert "OPENAI_API_KEY" not in env and "OTHER_SERVICE_TOKEN" not in env
    assert "private-canary" not in str(env)


def test_subscription_acceptance_refuses_api_login_before_starting_model(tmp_path, monkeypatch):
    monkeypatch.setattr(acceptance.subprocess, "run", lambda *a, **k: SimpleNamespace(
        returncode=0, stdout="Logged in using an API key", stderr=""))
    output = tmp_path / "not-created"
    with pytest.raises(ValueError, match="no_api_fallback"):
        acceptance.run_acceptance(idea_id="age_population_unit", codex="unused",
                                  output=output, model="unused")
    assert not output.exists()


def test_native_prompt_has_shared_foundations_before_model_starts(tmp_path, monkeypatch):
    from nsgablack.catalog.lab_knowledge import read_framework_basics
    monkeypatch.setattr(acceptance.subprocess, "run", lambda *a, **k: SimpleNamespace(
        returncode=0, stdout="Logged in using ChatGPT", stderr=""))
    monkeypatch.setattr(acceptance, "_user_config", lambda: {})
    monkeypatch.setattr(acceptance, "_share_with_invoking_user", lambda path: {"changed": False})
    monkeypatch.setattr(acceptance, "_disable_other_servers", lambda: [])
    monkeypatch.setattr(acceptance.tempfile, "mkdtemp", lambda **kw: str(tmp_path / "workspace"))
    def stop(*args, **kwargs):
        raise RuntimeError("model_start_intercepted")
    monkeypatch.setattr(acceptance.subprocess, "Popen", stop)
    output = tmp_path / "report"
    with pytest.raises(RuntimeError, match="model_start_intercepted"):
        acceptance.run_acceptance(idea_id="archive_maximin_survivor", codex="not-executed",
            output=output, model="test-only")
    basics = read_framework_basics()
    assert (output / "prompt.txt").read_text(encoding="utf-8").startswith(basics["content"])
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["framework_basics"] == basics["metadata"]
    assert report["foundations_loaded_before_model_start"] is True
    assert report["validation_profile"] == "archive-distance-v2"


def test_preserve_user_trust_but_disable_unrelated_mcp_servers(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    (tmp_path / "config.toml").write_text(
        '[projects."C:/my-project"]\ntrust_level="trusted"\n'
        '[mcp_servers.other]\ncommand="private-backend"\n'
        '[mcp_servers.black-framework]\ncommand="python"\n'
        '[plugins."other@team"]\nenabled=true\n', encoding="utf-8")
    before = (tmp_path / "config.toml").read_bytes()
    assert acceptance._disable_other_servers() == ["-c", "mcp_servers.other.enabled=false",
                                                  "-c", 'plugins."other@team".enabled=false']
    assert (tmp_path / "config.toml").read_bytes() == before


def test_host_validator_factories_have_fixed_identities_and_parameter_contracts():
    from nsgablack.catalog.assistant_novel_acceptance import spec_identity, TARGET
    for idea, name in acceptance.FACTORIES.items():
        binding = getattr(acceptance, name)()
        assert callable(binding["edit_validator"])
        if idea == "deadband_blend_change":
            from nsgablack.catalog.assistant_startup_acceptance import spec_identity as startup_identity
            assert binding["validation_identity"] == startup_identity()
        else:
            assert binding["validation_identity"] == spec_identity()
        assert TARGET in binding["edit_call_contracts"]


def _delivery_fixture(tmp_path):
    from nsgablack.catalog.assistant_novel_acceptance import TARGET
    project = tmp_path / "project"
    target = project / TARGET
    target.parent.mkdir(parents=True)
    target.write_text("def component(x):\n    return x\n", encoding="utf-8")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (tmp_path / "report.json").write_text(json.dumps({"idea": "fixture", "project": str(project), "project_id": "fixture:project",
        "exit_code": 0, "stop_reason": None, "validation_identity": "fixed/v1"}))
    check = {"path": TARGET, "code_sha256": digest, "edit_digest": "edit-1", "check": {"status": "needs_runtime_validation"},
        "validation": {"status": "passed", "executed": True, "code_sha256": digest,
                       "executed_source_sha256": digest, "validation_identity": "fixed/v1"}}
    (tmp_path / "post-write-mcp.json").write_text(json.dumps({"native_stdio_MCP": True,
        "project_read_succeeded": True, "read_receipt": {"source": {"path": TARGET,
            "project_id": "fixture:project", "sha256": digest}}}))
    def tool(name, data):
        return {"type": "item.completed", "item": {"type": "mcp_tool_call", "server": "black-framework",
            "tool": name, "result": {"structured_content": data}}}
    events = [{"type": "thread.started", "thread_id": "same-thread"},
        tool("check_project_edit", check), tool("edit_result", {"verification_status": "passed", "result": check}),
        {"type": "item.completed", "item": {"type": "file_change", "status": "completed"}}]
    def save():
        (tmp_path / "events.jsonl").write_text("\n".join(json.dumps(v) for v in events), encoding="utf-8")
    save()
    return target, events, tool, save


def test_delivery_review_rejects_changed_file_and_old_pass_after_later_failure(tmp_path):
    target, events, tool, save = _delivery_fixture(tmp_path)
    assert acceptance.review_acceptance(tmp_path)["status"] == "passed"
    original = target.read_bytes()
    target.write_bytes(original + b"# changed\n")
    assert acceptance.review_acceptance(tmp_path)["status"] == "not_delivered"
    target.write_bytes(original)
    failed = dict(events[1]["item"]["result"]["structured_content"])
    failed["validation"] = {"status": "failed", "executed": True}
    events.append(tool("check_project_edit", failed))
    save()
    assert acceptance.review_acceptance(tmp_path)["status"] == "not_delivered"


def test_delivery_review_records_unreadable_file_without_false_pass(tmp_path, monkeypatch):
    target, _, _, _ = _delivery_fixture(tmp_path)
    original = Path.read_bytes
    def read(path):
        if path == target:
            raise PermissionError("unreadable handoff")
        return original(path)
    monkeypatch.setattr(Path, "read_bytes", read)
    result = acceptance.review_acceptance(tmp_path)
    assert result["status"] == "not_delivered" and result["file_error"] == "PermissionError"
