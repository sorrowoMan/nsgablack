"""Local connection supervision never executes a Case or calls real SSH."""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from nsgablack.catalog import lab_workspace_connection as link


@pytest.fixture
def configuration(tmp_path):
    source = tmp_path / "registered projects"
    source.mkdir()
    agent = tmp_path / "agent-private.json"
    agent.write_text(json.dumps({"token": "a" * 64}), encoding="utf-8")
    identity = tmp_path / "operator-key.pem"
    identity.write_text("not-a-real-private-key", encoding="utf-8")
    value = {"storage": str(tmp_path / "workspace-data"),
             "project_roots": {"examples": str(source)}, "agent_config": str(agent),
             "local_port": 8640, "ssh": {"host": "8.217.114.28", "user": "root",
                 "identity_file": str(identity), "remote_port": 18640},
             "status_file": str(tmp_path / "connection-status.json")}
    path = tmp_path / "connection.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path, value


def write_config(configuration, value):
    path, _ = configuration
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_commands_use_explicit_arguments_strict_host_checks_and_loopback(configuration):
    config = link.load_config(configuration[0])
    argv = link.build_ssh_command(config)
    assert argv[0:3] == ["ssh", "-N", "-T"]
    assert "StrictHostKeyChecking=yes" in argv
    assert "ExitOnForwardFailure=yes" in argv
    assert "BatchMode=yes" in argv
    assert "ServerAliveInterval=20" in argv and "ServerAliveCountMax=3" in argv
    assert argv[argv.index("-R") + 1] == "127.0.0.1:18640:127.0.0.1:8640"
    assert argv[-1] == "root@8.217.114.28"
    assert "a" * 64 not in " ".join(argv)
    agent = link.build_agent_command(config)
    assert agent[:4] == [sys.executable, "-m", "nsgablack.catalog.lab_workspace_transport", "serve"]
    assert agent[agent.index("--project-root") + 1] == f"examples={config.project_roots['examples']}"
    assert agent[agent.index("--config") + 1] == str(config.agent_config)


@pytest.mark.parametrize("section,name,bad", [
    (None, "local_port", True), (None, "local_port", 80),
    (None, "local_port", "8640"), ("ssh", "remote_port", 65536),
    ("ssh", "host", "-oProxyCommand=anything"), ("ssh", "host", "host name"),
    ("ssh", "host", "host\nname"), ("ssh", "host", "a..b"),
    ("ssh", "user", "root;exit"), ("ssh", "user", "-o"),
    ("ssh", "identity_file", "relative-key.pem"),
    (None, "agent_config", "relative-agent.json"),
    (None, "storage", "relative-storage"),
])
def test_invalid_connection_arguments_are_refused(configuration, section, name, bad):
    value = deepcopy(configuration[1])
    (value[section] if section else value)[name] = bad
    with pytest.raises(link.ConnectionError):
        link.load_config(write_config(configuration, value))


def test_unknown_fields_and_duplicate_fields_are_refused(configuration):
    path, value = configuration
    value["command"] = "never execute"
    with pytest.raises(link.ConnectionError):
        link.load_config(write_config(configuration, value))
    path.write_text('{"storage":1,"storage":2}', encoding="utf-8")
    with pytest.raises(link.ConnectionError):
        link.load_config(path)


def test_status_cannot_overwrite_private_key_or_original_project(configuration):
    path, original = configuration
    for status in (original["ssh"]["identity_file"], original["agent_config"],
                   str(path), str(Path(original["project_roots"]["examples"]) / "status.json")):
        value = deepcopy(original); value["status_file"] = status
        with pytest.raises(link.ConnectionError):
            link.load_config(write_config(configuration, value))


def test_status_cannot_replace_preexisting_unrelated_json(configuration):
    path, value = configuration
    status = Path(value["status_file"])
    status.write_text('{"user_data":"keep"}', encoding="utf-8")
    before = status.read_bytes()
    with pytest.raises(link.ConnectionError):
        link.load_config(path)
    assert status.read_bytes() == before


def test_storage_and_source_overlap_is_refused(configuration):
    value = deepcopy(configuration[1])
    value["storage"] = value["project_roots"]["examples"]
    with pytest.raises(link.ConnectionError):
        link.load_config(write_config(configuration, value))


def test_credential_failure_never_prints_contents(configuration, capsys):
    agent = Path(configuration[1]["agent_config"])
    secret = "do-not-print-this-token"
    agent.write_text(json.dumps({"token": secret}), encoding="utf-8")
    assert link.main(["--config", str(configuration[0])]) == 2
    output = capsys.readouterr()
    assert secret not in output.err + output.out
    assert "connection_config_invalid" in output.err


def test_config_lock_refuses_second_live_owner_and_supports_cooperative_stop(configuration):
    path, _ = configuration
    with link.ConnectorLock(path) as first:
        with pytest.raises(link.ConnectionError) as error:
            with link.ConnectorLock(path):
                pytest.fail("duplicate owner")
        assert error.value.code == "connection_already_running"
        assert not first.stop_requested()
        assert link.ConnectorLock(path).request_stop()
        assert first.stop_requested()
    with link.ConnectorLock(path) as next_owner:
        assert not next_owner.stop_requested()


def test_stale_lock_is_reclaimed_without_killing_pid(configuration, monkeypatch):
    path, _ = configuration
    record = link.ConnectorLock(path)
    db = record._connect()
    db.execute("INSERT INTO connector_owner VALUES (1,?)",
               (json.dumps({"identity": "old", "pid": 123, "created": 0, "stop": False}),))
    db.commit(); db.close()
    monkeypatch.setattr(link, "_alive", lambda owner: False)
    with link.ConnectorLock(path) as current:
        assert current.acquired


class FakeProcess:
    def __init__(self, identity, code=None, terminate_timeout=False):
        self.pid, self.code = identity, code
        self.terminated = self.killed = False
        self.terminate_timeout = terminate_timeout

    def poll(self):
        return self.code

    def terminate(self):
        self.terminated = True
        if not self.terminate_timeout:
            self.code = -15

    def kill(self):
        self.killed = True; self.code = -9

    def wait(self, timeout=None):
        if self.terminate_timeout and not self.killed:
            raise subprocess.TimeoutExpired("owned-test-process", timeout)
        return self.code


def test_reconnection_reuses_one_agent_and_only_cleans_owned_children(configuration):
    config = link.load_config(configuration[0])
    calls = []
    agent, first_ssh, second_ssh = FakeProcess(101), FakeProcess(102, 255), FakeProcess(103)
    processes = iter((agent, first_ssh, second_ssh))
    def spawn(argv, **kwargs):
        calls.append((argv, kwargs))
        return next(processes)
    connection = link.WorkspaceConnection(config, popen=spawn, ready=lambda: True,
                                          port_check=lambda: None)
    def pause(seconds):
        if len(calls) >= 3:
            connection.stop()
            return True
        return False
    connection._pause = pause
    connection.run()
    assert len(calls) == 3
    assert calls[0][0] == link.build_agent_command(config)
    assert calls[1][0] == calls[2][0] == link.build_ssh_command(config)
    assert all(call[1]["shell"] is False for call in calls)
    assert all(call[1]["stdout"] == call[1]["stderr"] == subprocess.DEVNULL for call in calls)
    assert agent.terminated and second_ssh.terminated
    assert not first_ssh.terminated, "Exited SSH was not forcefully killed"
    status = json.loads(config.status_file.read_text(encoding="utf-8"))
    assert status["status"] == "stopped" and status["attempt"] == 2
    assert status["connection_verified"] is False
    encoded = json.dumps(status)
    assert "a" * 64 not in encoded and str(config.identity_file) not in encoded


def test_backoff_is_bounded_at_thirty_seconds(configuration):
    config = link.load_config(configuration[0])
    agent = FakeProcess(101)
    started = []
    def spawn(argv, **kwargs):
        item = agent if not started else FakeProcess(102 + len(started), 255)
        started.append(item)
        return item
    connection = link.WorkspaceConnection(config, popen=spawn, ready=lambda: True, port_check=lambda: None)
    delays = []
    def pause(seconds):
        delays.append(seconds)
        if len(delays) == 9:
            connection.stop()
            return True
        return False
    connection._pause = pause
    connection.run()
    assert delays == [1, 2, 4, 8, 16, 30, 30, 30, 30]
    assert started.count(agent) == 1


def test_agent_failure_stops_connection_without_starting_ssh(configuration):
    config = link.load_config(configuration[0])
    calls = []
    agent = FakeProcess(101, 2)
    connection = link.WorkspaceConnection(config, popen=lambda *a, **k: calls.append(a) or agent,
        ready=lambda: pytest.fail("failed agent cannot be ready"), port_check=lambda: None)
    with pytest.raises(link.ConnectionError) as error:
        connection.run()
    assert error.value.code == "connection_agent_failed"
    assert len(calls) == 1


def test_busy_local_port_does_not_spawn_or_kill_any_process(configuration):
    config = link.load_config(configuration[0])
    def busy():
        raise link.ConnectionError("connection_local_port_busy", "occupied")
    connection = link.WorkspaceConnection(config, popen=lambda *a, **k: pytest.fail("must not spawn"), port_check=busy)
    with pytest.raises(link.ConnectionError):
        connection.run()


def test_owned_process_timeout_only_kills_that_popen_instance():
    owned = FakeProcess(123, terminate_timeout=True)
    unrelated = FakeProcess(456)
    link.WorkspaceConnection._terminate(owned)
    assert owned.terminated and owned.killed
    assert not unrelated.terminated and not unrelated.killed


def test_stop_command_does_not_launch_or_signal_other_processes(configuration, monkeypatch, capsys):
    monkeypatch.setattr(link, "WorkspaceConnection", lambda *a, **k: pytest.fail("stop cannot launch agent"))
    assert link.main(["--config", str(configuration[0]), "--stop"]) == 0
    assert "没有正在运行" in capsys.readouterr().out
    with link.ConnectorLock(configuration[0]) as owner:
        assert link.main(["--config", str(configuration[0]), "--stop"]) == 0
        assert owner.stop_requested()


def test_stop_still_works_after_key_or_agent_configuration_removed(configuration, capsys):
    path, value = configuration
    with link.ConnectorLock(path) as owner:
        Path(value["agent_config"]).unlink()
        Path(value["ssh"]["identity_file"]).unlink()
        assert link.main(["--config", str(path), "--stop"]) == 0
        assert owner.stop_requested()
    assert "已请求" in capsys.readouterr().out


def test_cleanup_attempts_agent_even_when_tunnel_cleanup_fails(configuration):
    config = link.load_config(configuration[0])
    agent, tunnel = FakeProcess(123), FakeProcess(456)
    processes = iter((agent, tunnel))
    connection = link.WorkspaceConnection(config, popen=lambda *a, **k: next(processes),
        ready=lambda: True, port_check=lambda: None)
    def pause(seconds):
        connection.stop()
        return True
    connection._pause = pause
    original = connection._terminate
    attempted = []
    def terminate(process):
        attempted.append(process)
        if process is tunnel:
            raise OSError("private-operating-system-detail")
        original(process)
    connection._terminate = terminate
    with pytest.raises(link.ConnectionError) as error:
        connection.run()
    assert error.value.code == "connection_cleanup_failed"
    assert attempted == [tunnel, agent] and agent.terminated
    assert "private-operating-system-detail" not in str(error.value)


def test_port_probe_targets_only_loopback(configuration, monkeypatch):
    config = link.load_config(configuration[0])
    addresses = []
    class Probe:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def setsockopt(self, *args): pass
        def bind(self, address): addresses.append(address)
    monkeypatch.setattr(link.socket, "socket", Probe)
    link.WorkspaceConnection(config)._port_free()
    assert addresses == [("127.0.0.1", 8640)]


def test_agent_ready_request_is_authenticated_and_never_runs_a_case(configuration, monkeypatch):
    config = link.load_config(configuration[0])
    requests = []
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
    def open_request(request, *, timeout):
        requests.append(request)
        assert timeout <= 1
        return Response()
    monkeypatch.setattr(link, "urlopen", open_request)
    assert link.WorkspaceConnection(config)._agent_ready()
    request = requests[0]
    assert request.full_url == "http://127.0.0.1:8640/rpc"
    assert request.get_header("Authorization") == "Bearer " + "a" * 64
    assert json.loads(request.data) == {"operation": "list_workspaces", "arguments": {}}
