"""The new executable workspace is a deliberate local operator entry."""
import json
from pathlib import Path

import pytest

from nsgablack.catalog import lab_workspace as workspace


def test_workspace_is_opt_in_and_hosted_reader_cannot_enable_it(monkeypatch, tmp_path):
    monkeypatch.delenv(workspace.REMOTE_ENV, raising=False)
    monkeypatch.delenv(workspace.ROOT_ENV, raising=False)
    monkeypatch.delenv("NSGABLACK_CATALOG_HOSTED", raising=False)
    assert not workspace.workspace_enabled()
    monkeypatch.setenv(workspace.ROOT_ENV, str(tmp_path))
    assert workspace.workspace_enabled()
    assert not workspace.workspace_enabled(hosted=True)
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED", "1")
    assert not workspace.workspace_enabled()
    with pytest.raises(ValueError, match="托管只读"):
        workspace.get_workspace_runtime()


def test_launch_environment_uses_trusted_roots_and_no_catalog_service_credentials(tmp_path):
    source = tmp_path / "sources"
    source.mkdir()
    previous = {name: "not-a-real-config" for name in workspace._CLIENT_CONFIGS}
    previous["NSGABLACK_CATALOG_HOSTED"] = "1"
    env = workspace.launch_environment(tmp_path / "data", {"projects": str(source)}, environ=previous)
    assert not set(workspace._CLIENT_CONFIGS).intersection(env)
    assert env["NSGABLACK_CATALOG_HOSTED"] == "0"
    assert Path(env[workspace.ROOT_ENV]) == tmp_path / "data"
    assert json.loads(env[workspace.SOURCES_ENV]) == {"projects": str(source.resolve())}
    assert previous["NSGABLACK_CATALOG_HOSTED"] == "1"
    assert not (tmp_path / "data").exists(), "Launcher validation should not create a workspace"


@pytest.mark.parametrize("storage", ["sources", "sources/subdir", "."])
def test_storage_cannot_overlap_original_source_roots(tmp_path, storage):
    source = tmp_path / "sources"
    source.mkdir()
    with pytest.raises(ValueError, match="必须分开"):
        workspace.launch_environment(tmp_path / storage, {"projects": str(source)}, environ={})


@pytest.mark.parametrize("port", [True, 80, 0, 65536, "8633"])
def test_workspace_port_validation(port):
    with pytest.raises(ValueError):
        workspace.build_workspace_command(port=port)


def test_command_binds_only_loopback_and_disables_telemetry():
    command = workspace.build_workspace_command(port=8633)
    assert command[command.index("--server.address") + 1] == "127.0.0.1"
    assert command[command.index("--server.headless") + 1] == "true"
    assert command[command.index("--browser.gatherUsageStats") + 1] == "false"
    assert command[command.index("--server.port") + 1] == "8633"
    assert Path(command[4]).name == "lab_workspace_ui.py"
    assert command[command.index("--theme.base") + 1] == "dark"


def test_launcher_preserves_sources_as_arguments_without_a_shell(tmp_path, monkeypatch):
    source = tmp_path / "registered sources"
    source.mkdir()
    calls = []
    monkeypatch.setattr(workspace.subprocess, "call", lambda argv, *, env: calls.append((argv, env)) or 0)
    assert workspace.main(["--storage", str(tmp_path / "work"), "--project-root", f"mine={source}", "--port", "8634"]) == 0
    assert len(calls) == 1 and calls[0][0][0]
    assert json.loads(calls[0][1][workspace.SOURCES_ENV]) == {"mine": str(source)}


def test_duplicate_root_alias_does_not_launch(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace.subprocess, "call", lambda *a, **k: pytest.fail("invalid launch"))
    with pytest.raises(SystemExit):
        workspace.main(["--project-root", f"mine={tmp_path}", "--project-root", f"mine={tmp_path}"])


def test_explicit_remote_config_selects_client_without_local_runtime(monkeypatch, tmp_path):
    from types import SimpleNamespace
    config = tmp_path / "client.json"
    config.write_text("{}", encoding="utf-8")
    remote = SimpleNamespace(mode="remote", store=object(), runner=object())
    calls = []
    monkeypatch.setenv(workspace.REMOTE_ENV, str(config))
    monkeypatch.setenv("NSGABLACK_CATALOG_HOSTED", "1")
    monkeypatch.setattr(workspace, "_runtime", lambda *args: pytest.fail("server must not create local execution"))
    monkeypatch.setattr(workspace, "_remote_runtime", lambda *args: calls.append(args) or remote)
    assert workspace.workspace_enabled(hosted=True)
    assert workspace.get_workspace_runtime() is remote
    assert calls[0][0] == str(config)


def test_missing_remote_config_never_falls_back_to_local_execution(monkeypatch, tmp_path):
    monkeypatch.setenv(workspace.REMOTE_ENV, str(tmp_path / "missing.json"))
    monkeypatch.setenv(workspace.ROOT_ENV, str(tmp_path / "local"))
    monkeypatch.setattr(workspace, "_runtime", lambda *args: pytest.fail("silent local fallback"))
    with pytest.raises(ValueError, match="连接配置不可用"):
        workspace.get_workspace_runtime()


def test_remote_configuration_cache_identity_changes_when_config_changes(monkeypatch, tmp_path):
    config = tmp_path / "client.json"
    config.write_text("{}", encoding="utf-8")
    calls = []
    monkeypatch.setenv(workspace.REMOTE_ENV, str(config))
    monkeypatch.setattr(workspace, "_remote_runtime", lambda *args: calls.append(args) or object())
    workspace.get_workspace_runtime()
    config.write_text('{"changed":true}', encoding="utf-8")
    workspace.get_workspace_runtime()
    assert calls[0] != calls[1]
