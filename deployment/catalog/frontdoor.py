#!/usr/bin/env python3
"""Controlled, reversible relocation of the two existing workspace containers."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import signal
import socket
import stat
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import ProxyHandler, Request, build_opener

DASHBOARD_NAME = "trs-dashboard"
GATEWAY_NAME = "nsgablack-catalog-gateway"
BACKUP_ROOT = Path("/opt/framework-catalog/frontdoor/backups")
_ID = re.compile(r"[0-9a-f]{64}")
_ENDPOINT_KEYS = ("IPAMConfig", "Links", "Aliases", "DriverOpts", "GwPriority", "MacAddress")


class FrontdoorError(RuntimeError):
    pass


class DockerAPIError(FrontdoorError):
    def __init__(self, method: str, path: str, status: int):
        self.status = status
        super().__init__(f"Docker {method} failed with HTTP {status}")


class _UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path, **kwargs):
        super().__init__("localhost", **kwargs)
        self.socket_path = socket_path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)


class Docker:
    def __init__(self, socket_path="/var/run/docker.sock"):
        self.socket_path = socket_path
        self.version = ""
        version = self.request("GET", "/version").get("ApiVersion", "")
        if not re.fullmatch(r"\d+\.\d+", version):
            raise FrontdoorError("Docker API version unavailable")
        self.version = "/v" + version

    def request(self, method, path, body=None):
        connection = _UnixHTTPConnection(self.socket_path, timeout=45)
        try:
            encoded = None if body is None else json.dumps(body).encode("utf-8")
            connection.request(method, self.version + path, body=encoded,
                               headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            content = response.read()
            if not 200 <= response.status < 300:
                # Docker error bodies can contain configuration; discard them.
                raise DockerAPIError(method, path, response.status)
            return json.loads(content) if content else None
        except (OSError, http.client.HTTPException, ValueError):
            raise FrontdoorError("Docker API transport failed") from None
        finally:
            connection.close()


def _inspect(client, identifier):
    return client.request("GET", f"/containers/{quote(identifier, safe='')}/json")


def _optional_inspect(client, identifier):
    try:
        return _inspect(client, identifier)
    except DockerAPIError as exc:
        if exc.status == 404:
            return None
        raise


def _cas(client, name, expected_id, *, running=None):
    current = _optional_inspect(client, name)
    if not current or current["Id"] != expected_id:
        raise FrontdoorError("Container identity changed; refusing mutation")
    if running is not None and bool(current.get("State", {}).get("Running")) != running:
        raise FrontdoorError("Container running state changed; refusing mutation")
    return current


def _config_bytes(path):
    path = Path(path)
    if not path.is_absolute() or not path.is_file() or path.stat().st_size > 1024 * 1024:
        raise FrontdoorError("Gateway config must be an existing absolute regular file")
    return path.read_bytes()


def _assert_free_port():
    try:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 8089))
    except OSError:
        raise FrontdoorError("Destination loopback port 8089 is already occupied") from None


def build_create_payload(inspected, *, role, gateway_config=None):
    """Clone declarative settings; never copy runtime IPs or endpoint IDs."""
    payload = deepcopy(inspected["Config"])
    payload["Image"] = inspected["Image"]
    host = deepcopy(inspected["HostConfig"])
    if host.get("AutoRemove"):
        raise FrontdoorError("Auto-removing containers cannot serve as rollback points")
    if role == "dashboard":
        bindings = host.get("PortBindings", {}).get("8080/tcp")
        if bindings != [{"HostIp": "127.0.0.1", "HostPort": "8080"}]:
            raise FrontdoorError("Dashboard 8080 binding differs from the reviewed topology")
        if not host.get("PortBindings", {}).get("8086/tcp"):
            raise FrontdoorError("Dashboard trusted 8086 binding is missing")
        bindings[0]["HostPort"] = "8089"
    elif role == "gateway":
        if host.get("NetworkMode") != "host":
            raise FrontdoorError("Gateway must retain its existing host network")
        target = "/etc/nginx/nginx.conf"
        found = 0
        binds = list(host.get("Binds") or [])
        for index, binding in enumerate(binds):
            parts = binding.split(":")
            if len(parts) >= 2 and parts[1] == target:
                flags = [value for value in (parts[2].split(",") if len(parts) > 2 else []) if value != "rw"]
                if "ro" not in flags:
                    flags.append("ro")
                binds[index] = f"{gateway_config}:{target}:{','.join(flags)}"
                found += 1
        if host.get("Binds") is not None:
            host["Binds"] = binds
        for mount in host.get("Mounts") or []:
            if mount.get("Target") == target:
                mount.update(Source=str(gateway_config), ReadOnly=True)
                found += 1
        if found != 1 or gateway_config is None:
            raise FrontdoorError("Gateway must have exactly one explicit config mount")
        host["Memory"] = 128 * 1024 * 1024
        host["MemorySwap"] = host["Memory"]
        host["NanoCpus"] = 250_000_000
        host["CpuPeriod"] = 0
        host["CpuQuota"] = 0
        host.setdefault("Tmpfs", {})["/tmp"] = "rw,noexec,nosuid,size=128m"
    else:
        raise FrontdoorError("Unknown controlled container role")
    # An implicit anonymous volume would otherwise become a new empty volume.
    explicit = set((host.get("Tmpfs") or {}).keys())
    explicit.update(mount.get("Target") for mount in host.get("Mounts") or [])
    explicit.update(binding.split(":")[1] for binding in host.get("Binds") or [] if ":" in binding)
    if any(mount.get("Destination") not in explicit for mount in inspected.get("Mounts", [])):
        raise FrontdoorError("Implicit mounts require explicit preservation before cloning")
    payload["HostConfig"] = host
    networks = inspected.get("NetworkSettings", {}).get("Networks") or {}
    payload["NetworkingConfig"] = {"EndpointsConfig": {
        name: {key: deepcopy(endpoint[key]) for key in _ENDPOINT_KEYS if key in endpoint}
        for name, endpoint in networks.items()
    }}
    return payload


def _prepare(client, *, expected_dashboard_id, expected_gateway_id, gateway_config):
    if not _ID.fullmatch(expected_dashboard_id) or not _ID.fullmatch(expected_gateway_id):
        raise FrontdoorError("Full exact Docker container IDs are required")
    dashboard = _cas(client, DASHBOARD_NAME, expected_dashboard_id, running=True)
    gateway = _cas(client, GATEWAY_NAME, expected_gateway_id, running=True)
    config = _config_bytes(gateway_config)
    _assert_free_port()
    return {"dashboard": dashboard, "gateway": gateway,
            "dashboard_payload": build_create_payload(dashboard, role="dashboard"),
            "gateway_payload": build_create_payload(gateway, role="gateway", gateway_config=Path(gateway_config)),
            "config_bytes": config, "config_sha256": hashlib.sha256(config).hexdigest()}


def _summary(state, status):
    report = {"status": status, "config_sha256": state["config_sha256"],
              "gateway_config": state["gateway_config"],
              "ports": {"ordinary": 8080, "dashboard_backend": 8089, "trusted": 8086, "catalog": 8615}}
    for role in ("dashboard", "gateway"):
        report[role] = {key: value for key, value in state[role].items()
                        if key in {"old_id", "new_id", "image_id"}}
    if "backup" in state:
        report["backup_path"] = state["backup"]
        report["rollback_command"] = ["python3", str(Path(__file__).resolve()), "rollback", "--backup", state["backup"]]
    return report


def plan(client, *, expected_dashboard_id, expected_gateway_id, gateway_config):
    prepared = _prepare(client, expected_dashboard_id=expected_dashboard_id,
                        expected_gateway_id=expected_gateway_id, gateway_config=gateway_config)
    state = {"gateway_config": str(Path(gateway_config)), "config_sha256": prepared["config_sha256"]}
    for role in ("dashboard", "gateway"):
        state[role] = {"old_id": prepared[role]["Id"], "image_id": prepared[role]["Image"]}
    return _summary(state, "planned")


def _write_private(path, content):
    descriptor, temporary = tempfile.mkstemp(prefix=".pending-", dir=str(path.parent))
    try:
        os.chmod(temporary, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _save(state):
    _write_private(Path(state["backup"]) / "state.json", json.dumps(state).encode("utf-8"))


def _rename(client, identifier, name):
    client.request("POST", f"/containers/{identifier}/rename?name={quote(name, safe='')}")


def _stop(client, identifier):
    client.request("POST", f"/containers/{identifier}/stop?t=20")


def _start(client, identifier):
    client.request("POST", f"/containers/{identifier}/start")


def _http(path, port):
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(Request(f"http://127.0.0.1:{port}{path}"), timeout=5) as response:
            return response.status, response.read(256 * 1024)
    except HTTPError as exc:
        return exc.code, b""


def verify_phase(phase):
    deadline = time.monotonic() + 35
    while True:
        try:
            if phase == "dashboard":
                valid = all(_http("/workspace", port)[0] == 200 for port in (8089, 8086))
            else:
                status, body = _http("/api/workspace/session", 8080)
                session = json.loads(body) if status == 200 else {}
                valid = (status == 200 and session.get("enabled") is True
                         and session.get("access_mode") == "account"
                         and session.get("authenticated") is False
                         and _http("/apps/framework-catalog/", 8080)[0] == 401
                         and _http("/apps/framework-catalog/", 8615)[0] == 403)
            if valid:
                return
        except (OSError, URLError, ValueError):
            pass
        if time.monotonic() >= deadline:
            raise FrontdoorError("Replacement readiness or access boundary check failed")
        time.sleep(0.5)


def _restore(client, state):
    """Touch only the exact original IDs and this operation's created IDs."""
    errors = []
    # Release both replacement listeners before restarting either original.
    for role in ("gateway", "dashboard"):
        item = state[role]
        identifier = item.get("new_id")
        if not identifier:
            continue
        try:
            candidate = _optional_inspect(client, identifier)
            if candidate:
                if candidate["Name"].lstrip("/") not in {item["name"], item["candidate_name"]}:
                    raise FrontdoorError("Replacement moved to another deployment")
                if candidate.get("State", {}).get("Running"):
                    _stop(client, identifier)
                if candidate["Name"].lstrip("/") == item["name"]:
                    _cas(client, item["name"], identifier, running=False)
                    _rename(client, identifier, item["candidate_name"])
        except Exception:
            errors.append(role + "_candidate_stop_failed")
    for role in ("dashboard", "gateway"):
        item = state[role]
        if not item.get("old_stop_intent"):
            continue
        try:
            original = _inspect(client, item["old_id"])
            occupying = _optional_inspect(client, item["name"])
            if occupying and occupying["Id"] != item["old_id"]:
                raise FrontdoorError("Original name is owned by a different deployment")
            if original["Name"].lstrip("/") != item["name"]:
                _rename(client, item["old_id"], item["name"])
            if not original.get("State", {}).get("Running"):
                _start(client, item["old_id"])
            _cas(client, item["name"], item["old_id"], running=True)
        except Exception:
            errors.append(role + "_restore_failed")
    state["status"] = "rollback_incomplete" if errors else "rolled_back"
    state["recovery_errors"] = errors
    try:
        _save(state)
    except Exception:
        errors.append("rollback_state_write_failed")
        state["status"] = "rollback_incomplete"
    return errors


def apply(client, *, expected_dashboard_id, expected_gateway_id, gateway_config,
          backup_root=BACKUP_ROOT, probe=verify_phase):
    prepared = _prepare(client, expected_dashboard_id=expected_dashboard_id,
                        expected_gateway_id=expected_gateway_id, gateway_config=gateway_config)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    backup_root = Path(backup_root).resolve()
    backup_root.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(backup_root, 0o700)
    backup = backup_root / stamp
    backup.mkdir(parents=True, mode=0o700, exist_ok=False)
    os.chmod(backup, 0o700)
    state = {"status": "prepared", "backup": str(backup), "gateway_config": str(Path(gateway_config)),
             "config_sha256": prepared["config_sha256"]}
    for role, name in (("dashboard", DASHBOARD_NAME), ("gateway", GATEWAY_NAME)):
        inspected = prepared[role]
        _write_private(backup / f"{role}-inspect.json", json.dumps(inspected).encode("utf-8"))
        state[role] = {"old_id": inspected["Id"], "image_id": inspected["Image"], "name": name,
                       "backup_name": name + ".frontdoor-backup-" + stamp,
                       "candidate_name": name + ".frontdoor-candidate-" + stamp}
    _write_private(backup / "gateway.conf", prepared["config_bytes"])
    _save(state)
    try:
        for role in ("dashboard", "gateway"):
            _cas(client, DASHBOARD_NAME, expected_dashboard_id, running=True)
            _cas(client, GATEWAY_NAME, expected_gateway_id, running=True)
            item = state[role]
            if _optional_inspect(client, item["candidate_name"]) is not None:
                raise FrontdoorError("Candidate name already exists")
            result = client.request("POST", "/containers/create?name=" + quote(item["candidate_name"], safe=""),
                                    prepared[role + "_payload"])
            item["new_id"] = result["Id"]
            _save(state)
        _assert_free_port()
        _cas(client, DASHBOARD_NAME, expected_dashboard_id, running=True)
        _cas(client, GATEWAY_NAME, expected_gateway_id, running=True)
        state["dashboard"]["old_stop_intent"] = True
        _save(state)
        _stop(client, expected_dashboard_id)
        _cas(client, DASHBOARD_NAME, expected_dashboard_id, running=False)
        _rename(client, expected_dashboard_id, state["dashboard"]["backup_name"])
        _start(client, state["dashboard"]["new_id"])
        probe("dashboard")
        _rename(client, state["dashboard"]["new_id"], DASHBOARD_NAME)
        state["status"] = "dashboard_ready"
        _save(state)
        _cas(client, DASHBOARD_NAME, state["dashboard"]["new_id"], running=True)
        _cas(client, GATEWAY_NAME, expected_gateway_id, running=True)
        if hashlib.sha256(_config_bytes(gateway_config)).hexdigest() != state["config_sha256"]:
            raise FrontdoorError("Gateway config changed after preparation")
        state["gateway"]["old_stop_intent"] = True
        _save(state)
        _stop(client, expected_gateway_id)
        _cas(client, GATEWAY_NAME, expected_gateway_id, running=False)
        _rename(client, expected_gateway_id, state["gateway"]["backup_name"])
        _start(client, state["gateway"]["new_id"])
        probe("gateway")
        _rename(client, state["gateway"]["new_id"], GATEWAY_NAME)
        _cas(client, DASHBOARD_NAME, state["dashboard"]["new_id"], running=True)
        _cas(client, GATEWAY_NAME, state["gateway"]["new_id"], running=True)
        state["status"] = "applied"
        _save(state)
        return _summary(state, "applied")
    except BaseException as exc:
        errors = _restore(client, state)
        report = _summary(state, "rollback_incomplete" if errors else "failed_rolled_back")
        report.update(error_type=type(exc).__name__, docker_status=getattr(exc, "status", None),
                      recovery_errors=errors)
        return report


def rollback(client, *, backup, probe=None):
    backup = Path(backup).resolve()
    state_path = backup / "state.json"
    metadata = state_path.stat()
    if os.name != "nt" and (metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) & 0o077):
        raise FrontdoorError("Rollback state must be root-owned and private")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if Path(state["backup"]).resolve() != backup:
        raise FrontdoorError("Rollback state path does not match")
    # Do not stop this operation's containers if another deployment now owns a name.
    for role in ("dashboard", "gateway"):
        item = state[role]
        expected_name = DASHBOARD_NAME if role == "dashboard" else GATEWAY_NAME
        if (item.get("name") != expected_name or not _ID.fullmatch(item.get("old_id", ""))
                or (item.get("new_id") and not _ID.fullmatch(item["new_id"]))):
            raise FrontdoorError("Rollback state is not a controlled two-container deployment")
        original = _inspect(client, item["old_id"])
        if original["Name"].lstrip("/") not in {item["name"], item["backup_name"]}:
            raise FrontdoorError("Original container moved to another deployment")
        if item.get("new_id"):
            candidate = _optional_inspect(client, item["new_id"])
            if candidate and candidate["Name"].lstrip("/") not in {item["name"], item["candidate_name"]}:
                raise FrontdoorError("Replacement container moved to another deployment")
        current = _optional_inspect(client, item["name"])
        if current and current["Id"] not in {item["old_id"], item.get("new_id")}:
            raise FrontdoorError("Another deployment replaced the front door")
    errors = _restore(client, state)
    report = _summary(state, "rollback_incomplete" if errors else "rolled_back")
    report["recovery_errors"] = errors
    return report


@contextmanager
def _deployment_lock():
    import fcntl
    directory = BACKUP_ROOT.parent
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(directory, 0o700)
    with open(directory / ".lock", "a", encoding="utf-8") as lock:
        os.chmod(directory / ".lock", 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("plan", "apply"):
        operation = commands.add_parser(command)
        operation.add_argument("--expected-dashboard-id", required=True)
        operation.add_argument("--expected-gateway-id", required=True)
        operation.add_argument("--gateway-config", required=True, type=Path)
    operation = commands.add_parser("rollback")
    operation.add_argument("--backup", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if not hasattr(os, "geteuid") or os.geteuid() != 0:
            raise FrontdoorError("Run this controlled deployment tool as server root")
        signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
        client = Docker()
        kwargs = vars(args).copy()
        command = kwargs.pop("command")
        if command == "rollback" and not kwargs["backup"].resolve().is_relative_to(BACKUP_ROOT.resolve()):
            raise FrontdoorError("Rollback directory must be below the controlled backup root")
        if command == "plan":
            report = plan(client, **kwargs)
        else:
            with _deployment_lock():
                report = apply(client, **kwargs) if command == "apply" else rollback(client, **kwargs)
        print(json.dumps(report, separators=(",", ":")))
        return 0 if report["status"] in {"planned", "applied", "rolled_back"} else 1
    except BaseException as exc:
        # Neither inspect data, Docker error bodies nor configuration are logged.
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
