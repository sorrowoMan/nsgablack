"""Operator-owned local agent and reconnecting SSH reverse connection.

No browser supplies these paths or SSH arguments. This helper never submits a
Project run; it only keeps the already authenticated workspace agent reachable.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from urllib.error import URLError
from urllib.request import Request, urlopen
from uuid import uuid4

import psutil


SCHEMA = "nsgablack.workspace_connection/v1"
_NAME = re.compile(r"[A-Za-z0-9_-]{1,40}\Z")
_USER = re.compile(r"[A-Za-z_][A-Za-z0-9_-]{0,63}\Z")
_HOST = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?\Z")
_TOKEN = re.compile(r"[0-9a-f]{64}\Z")


class ConnectionError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _fail(code, message):
    raise ConnectionError(code, message)


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            _fail("connection_config_invalid", "连接配置含重复字段。")
        result[key] = value
    return result


def _read_json(path: Path):
    try:
        if path.stat().st_size > 16384:
            raise ValueError()
        return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError()))
    except (OSError, UnicodeError, ValueError):
        _fail("connection_config_invalid", "无法读取有效的本机连接配置。")


def _path(value, *, kind=None):
    if not isinstance(value, str) or not value or any(ord(c) < 32 for c in value):
        _fail("connection_config_invalid", "连接目录或文件配置无效。")
    path = Path(value)
    if not path.is_absolute():
        _fail("connection_config_invalid", "连接目录和文件必须使用绝对路径。")
    try:
        path = path.resolve()
        if kind == "file" and not path.is_file() or kind == "directory" and not path.is_dir():
            _fail("connection_config_invalid", "指定的本机连接文件或来源目录不存在。")
    except (OSError, RuntimeError):
        _fail("connection_config_invalid", "指定的本机连接文件或来源目录不可用。")
    return path


def _port(value):
    if type(value) is not int or not 1024 <= value <= 65535:
        _fail("connection_config_invalid", "连接端口必须为 1024 到 65535 的整数。")
    return value


@dataclass(frozen=True)
class ConnectionConfig:
    path: Path
    storage: Path
    project_roots: dict[str, Path]
    agent_config: Path
    local_port: int
    host: str
    user: str
    identity_file: Path
    remote_port: int
    status_file: Path | None = None


def load_config(path: str | Path) -> ConnectionConfig:
    path = _path(str(path), kind="file")
    value = _read_json(path)
    required = {"storage", "project_roots", "agent_config", "local_port", "ssh"}
    if not isinstance(value, dict) or required - value.keys() or value.keys() - required - {"status_file"}:
        _fail("connection_config_invalid", "连接配置字段不符合约定。")
    ssh = value["ssh"]
    if not isinstance(ssh, dict) or set(ssh) != {"host", "user", "identity_file", "remote_port"}:
        _fail("connection_config_invalid", "SSH 连接配置字段无效。")
    host, user = ssh["host"], ssh["user"]
    if not isinstance(host, str):
        _fail("connection_config_invalid", "SSH 主机无效。")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not _HOST.fullmatch(host) or ".." in host:
            _fail("connection_config_invalid", "SSH 主机必须是字面地址或主机名。")
    if not isinstance(user, str) or not _USER.fullmatch(user):
        _fail("connection_config_invalid", "SSH 用户名无效。")
    roots = value["project_roots"]
    if not isinstance(roots, dict) or not roots or len(roots) > 20:
        _fail("connection_config_invalid", "至少登记一个本机 Project 来源。")
    normalized = {}
    for name, root in roots.items():
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            _fail("connection_config_invalid", "Project 来源名称无效。")
        normalized[name] = _path(root, kind="directory")
    storage = _path(value["storage"])
    for root in normalized.values():
        if storage == root or storage.is_relative_to(root) or root.is_relative_to(storage):
            _fail("connection_config_invalid", "工作区存储与原工程来源必须分开。")
    agent = _path(value["agent_config"], kind="file")
    secret = _read_json(agent)
    if not isinstance(secret, dict) or not isinstance(secret.get("token"), str) or not _TOKEN.fullmatch(secret["token"]):
        _fail("connection_config_invalid", "本机运行器认证配置无效。")
    identity = _path(ssh["identity_file"], kind="file")
    status = _path(value["status_file"]) if value.get("status_file") is not None else None
    if status is not None:
        if (status in {path, agent, identity} or status.suffix.lower() != ".json"
                or any(status.is_relative_to(root) for root in normalized.values())):
            _fail("connection_config_invalid", "状态文件不能覆盖配置、凭据或原工程文件。")
        if status.exists():
            previous = _read_json(status)
            if not isinstance(previous, dict) or previous.get("schema") != SCHEMA:
                _fail("connection_config_invalid", "状态文件位置已有其它内容，未覆盖。")
    return ConnectionConfig(path, storage, normalized, agent, _port(value["local_port"]),
                            host, user, identity,
                            _port(ssh["remote_port"]), status)


def build_agent_command(config: ConnectionConfig) -> list[str]:
    command = [sys.executable, "-m", "nsgablack.catalog.lab_workspace_transport", "serve",
               "--storage", str(config.storage), "--config", str(config.agent_config),
               "--port", str(config.local_port)]
    for name, directory in sorted(config.project_roots.items()):
        command += ["--project-root", f"{name}={directory}"]
    return command


def build_ssh_command(config: ConnectionConfig) -> list[str]:
    return ["ssh", "-N", "-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
            "-o", "ExitOnForwardFailure=yes", "-o", "ConnectTimeout=12",
            "-o", "ServerAliveInterval=20", "-o", "ServerAliveCountMax=3",
            "-i", str(config.identity_file), "-R",
            f"127.0.0.1:{config.remote_port}:127.0.0.1:{config.local_port}",
            f"{config.user}@{config.host}"]


def _alive(owner):
    try:
        process = psutil.Process(owner["pid"])
        return process.is_running() and abs(process.create_time() - owner["created"]) < .01
    except psutil.AccessDenied:
        return True  # Ownership cannot safely be disproved.
    except (psutil.Error, KeyError, TypeError, ValueError):
        return False


class ConnectorLock:
    def __init__(self, config_path: Path):
        self.path = config_path.with_name(config_path.name + ".connection.sqlite3")
        self.identity = uuid4().hex
        self.acquired = False

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.execute("CREATE TABLE IF NOT EXISTS connector_owner (singleton INTEGER PRIMARY KEY CHECK(singleton=1), record TEXT NOT NULL)")
        return db

    def __enter__(self):
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT record FROM connector_owner WHERE singleton=1").fetchone()
            if row and _alive(json.loads(row[0])):
                _fail("connection_already_running", "此连接器已启动，请使用已有连接。")
            owner = {"identity": self.identity, "pid": os.getpid(),
                     "created": psutil.Process().create_time(), "stop": False}
            db.execute("INSERT OR REPLACE INTO connector_owner VALUES (1,?)", (json.dumps(owner),))
            db.commit()
            self.acquired = True
            return self
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def stop_requested(self):
        db = self._connect()
        try:
            row = db.execute("SELECT record FROM connector_owner WHERE singleton=1").fetchone()
            return not row or json.loads(row[0]).get("identity") != self.identity or bool(json.loads(row[0]).get("stop"))
        finally:
            db.close()

    def request_stop(self):
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT record FROM connector_owner WHERE singleton=1").fetchone()
            if row is None or not _alive(json.loads(row[0])):
                return False
            owner = json.loads(row[0]); owner["stop"] = True
            db.execute("UPDATE connector_owner SET record=? WHERE singleton=1", (json.dumps(owner),))
            db.commit()
            return True
        finally:
            db.close()

    def __exit__(self, *_args):
        if not self.acquired:
            return
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT record FROM connector_owner WHERE singleton=1").fetchone()
            if row and json.loads(row[0]).get("identity") == self.identity:
                db.execute("DELETE FROM connector_owner WHERE singleton=1")
            db.commit()
        finally:
            db.close()
            self.acquired = False


class WorkspaceConnection:
    def __init__(self, config: ConnectionConfig, *, popen=None, wait=None, ready=None, port_check=None):
        self.config = config
        self._popen = popen or subprocess.Popen
        self._event = threading.Event()
        self._wait = wait or self._event.wait
        self._ready = ready or self._agent_ready
        self._port_check = port_check or self._port_free
        self.agent = self.tunnel = self.lock = None
        self.attempt = 0

    def stop(self):
        self._event.set()

    def _status(self, state):
        path = self.config.status_file
        if path is None:
            return
        value = {"schema": SCHEMA, "status": state, "connector_pid": os.getpid(),
                 "agent_pid": getattr(self.agent, "pid", None), "tunnel_pid": getattr(self.tunnel, "pid", None),
                 "local_port": self.config.local_port, "remote_port": self.config.remote_port,
                 "attempt": self.attempt, "updated_at": datetime.now(timezone.utc).isoformat(),
                 "connection_verified": False}
        path.parent.mkdir(parents=True, exist_ok=True)
        incoming = path.with_name(path.name + ".incoming-" + uuid4().hex)
        try:
            with incoming.open("x", encoding="utf-8") as stream:
                json.dump(value, stream, ensure_ascii=False)
            incoming.chmod(0o600)
            os.replace(incoming, path)
        finally:
            if incoming.exists():
                incoming.unlink()

    def _port_free(self):
        with socket.socket() as probe:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                probe.bind(("127.0.0.1", self.config.local_port))
            except OSError:
                _fail("connection_local_port_busy", "本机运行器端口已被占用，未启动或终止其他服务。")

    def _agent_ready(self):
        token = _read_json(self.config.agent_config)["token"]
        body = json.dumps({"operation": "list_workspaces", "arguments": {}}).encode()
        request = Request(f"http://127.0.0.1:{self.config.local_port}/rpc", data=body,
                          headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=.8) as response:
                return response.status == 200
        except (OSError, URLError):
            return False

    def _spawn(self, command):
        return self._popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, shell=False,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def _stopping(self):
        return self._event.is_set() or (self.lock is not None and self.lock.stop_requested())

    def _pause(self, seconds):
        deadline = time.monotonic() + seconds
        while not self._stopping():
            if self._wait(min(1., max(0., deadline - time.monotonic()))):
                self.stop()
                return True
            if time.monotonic() >= deadline:
                return False
        return True

    @staticmethod
    def _terminate(process):
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    def run(self):
        with ConnectorLock(self.config.path) as lock:
            self.lock = lock
            try:
                self._port_check()
                self._status("starting_agent")
                self.agent = self._spawn(build_agent_command(self.config))
                deadline = time.monotonic() + 20
                while not self._stopping():
                    if self.agent.poll() is not None:
                        _fail("connection_agent_failed", "本机运行器未能启动，请检查本机配置。")
                    if self._ready():
                        break
                    if time.monotonic() >= deadline:
                        _fail("connection_agent_timeout", "等待本机运行器就绪超时。")
                    self._pause(.2)
                if self._stopping():
                    return
                self._status("agent_ready")
                delay = 1
                while not self._stopping():
                    if self.agent.poll() is not None:
                        _fail("connection_agent_stopped", "本机运行器已退出，连接器停止转发。")
                    self.attempt += 1
                    self._status("connecting")
                    self.tunnel = self._spawn(build_ssh_command(self.config))
                    self._status("tunnel_running")
                    # A live SSH process is not an end-to-end RPC receipt.
                    while not self._stopping() and self.tunnel.poll() is None:
                        if self.agent.poll() is not None:
                            _fail("connection_agent_stopped", "本机运行器已退出，连接器停止转发。")
                        self._pause(1)
                    if self._stopping():
                        break
                    self._status("reconnecting")
                    self.tunnel = None
                    if self._pause(delay):
                        break
                    delay = min(30, delay * 2)
            except KeyboardInterrupt:
                self.stop()
            except Exception:
                self._status("error")
                raise
            finally:
                failed = False
                for process in (self.tunnel, self.agent):
                    try:
                        self._terminate(process)
                    except (OSError, subprocess.TimeoutExpired):
                        failed = True
                if not failed:
                    self.tunnel = self.agent = None
                self._status("cleanup_failed" if failed else "stopped")
                self.lock = None
                if failed:
                    _fail("connection_cleanup_failed", "本次连接器子进程清理未完成，请核对本机状态记录。")


def main(argv=None):
    parser = argparse.ArgumentParser(description="连接云端工程界面与本机运行器")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--stop", action="store_true", help="请求已有连接器退出，不终止其他进程")
    args = parser.parse_args(argv)
    try:
        if args.stop:
            # Stop remains available after an operator rotates a key or removes
            # a source root; it needs only this configuration's ownership file.
            path = _path(str(args.config), kind="file")
            active = ConnectorLock(path).request_stop()
            print("已请求本机连接器退出。" if active else "没有正在运行的本机连接器。")
        else:
            config = load_config(args.config)
            WorkspaceConnection(config).run()
    except ConnectionError as exc:
        print(f"{exc.code}: {exc}", file=sys.stderr)
        return 2
    except (OSError, sqlite3.Error):
        print("connection_runtime_failed: 本机连接器未能完成启动或清理。", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
