"""Linux-only Nginx checks using ephemeral loopback fixtures, never real accounts.

Run beside gateway.conf after the pinned image has already been pulled.
Both regular and trusted listeners are checked; no production port is used.
"""
from __future__ import annotations

import base64
from contextlib import ExitStack
import hashlib
import http.client
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import threading
import time
import uuid


IMAGE = "nginx@sha256:a8b39bd9cf0f83869a2162827a0caf6137ddf759d50a171451b335cecc87d236"
BASE = "/apps/framework-catalog/"
AUTH_PATH = "/api/workspace/app-access?app=framework-catalog&action=read"
WORKSPACE_BASE = "/apps/framework-workspace/"
WORKSPACE_AUTH_PATH = "/api/workspace/app-access?app=framework-workspace&action=read"
APPS = {"catalog": {"base": BASE, "auth_path": AUTH_PATH},
        "workspace": {"base": WORKSPACE_BASE, "auth_path": WORKSPACE_AUTH_PATH}}
AUTH_PATHS = frozenset(app["auth_path"] for app in APPS.values())
WS_KEY = "dGhlIHNhbXBsZSBub25jZQ=="
WS_ACCEPT = base64.b64encode(hashlib.sha1(
    (WS_KEY + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()
).digest()).decode()
TAIL_LOGIN = "bound-simon@fixture.invalid"
UNBOUND_TAIL_LOGIN = "unbound@fixture.invalid"


def fixture_config(config: str, replacements: dict[int, int]) -> str:
    """Rewrite every production endpoint, refusing any unknown live target."""
    expected_ports = {8080, 8086, 8089, 8615, 8619, 8643}
    if (set(replacements) != expected_ports or len(set(replacements.values())) != len(expected_ports)
            or any(type(port) is not int or not 1024 <= port <= 65535 or port in expected_ports
                   for port in replacements.values())):
        raise ValueError("invalid isolated fixture endpoints")
    targets = set(re.findall(r"\b(?:listen|proxy_pass)\s+([^;\s]+)", config))
    if targets != {"127.0.0.1:8080", "127.0.0.1:8615", "http://127.0.0.1:$catalog_auth_port/api/workspace/app-access?app=framework-catalog&action=read",
                   "http://127.0.0.1:$catalog_auth_port/api/workspace/app-access?app=framework-workspace&action=read",
                   "http://127.0.0.1:8619", "http://127.0.0.1:8643", "http://127.0.0.1:8089"}:
        raise ValueError("unexpected gateway.conf listener or upstream")
    pattern = r"\b(?:8080|8086|8089|8615|8619|8643)\b"
    if set(map(int, re.findall(pattern, config))) != expected_ports:
        raise ValueError("unexpected gateway.conf endpoints")
    return re.sub(pattern, lambda match: str(replacements[int(match.group())]), config)


def main() -> dict:
    auth_requests, upstream_requests, fallback_requests = [], [], []
    servers, threads = {}, []
    name = "catalog-gateway-check-" + uuid.uuid4().hex[:12]

    class Fixture(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):
            pass

        def do_GET(self):
            headers = {key.lower(): value for key, value in self.headers.items()}
            remaining = size = int(headers.get("content-length", "0"))
            digest = hashlib.sha256()
            while remaining:
                chunk = self.rfile.read(min(65536, remaining))
                if not chunk:
                    raise OSError("fixture received an incomplete body")
                digest.update(chunk)
                remaining -= len(chunk)
            observed = {"mode": self.server.mode, "path": self.path, "headers": headers,
                        "size": size, "sha256": digest.hexdigest(), "method": self.command}
            if self.path in AUTH_PATHS and self.server.mode not in APPS:
                auth_requests.append(observed)
                cookies = SimpleCookie(headers.get("cookie", ""))
                account = cookies.get("fixture_account")
                if account:
                    status = {"simon": 200, "other": 403, "unavailable": 503}.get(account.value, 401)
                else:
                    login = headers.get("tailscale-user-login")
                    status = (200 if self.server.mode == "trusted" and login == TAIL_LOGIN else
                              403 if self.server.mode == "trusted" and login == UNBOUND_TAIL_LOGIN else 401)
            elif self.server.mode in APPS:
                upstream_requests.append(observed)
                status = 101 if headers.get("upgrade", "").lower() == "websocket" else 200
            else:
                fallback_requests.append(observed)
                status = 303 if self.path == "/workspace/fixture-redirect" else 200
            self.send_response(status)
            if status == 101:
                self.send_header("Upgrade", "websocket")
                self.send_header("Connection", "Upgrade")
                self.send_header("Sec-WebSocket-Accept", WS_ACCEPT)
                self.close_connection = True
            else:
                self.send_header("Content-Length", "2")
                self.send_header("Content-Type", "application/json")
            if observed in fallback_requests:
                self.send_header("Set-Cookie", "workspace_fixture=ok; Path=/; HttpOnly")
            if status == 303:
                self.send_header("Location", "/workspace/account?fixture=1")
            self.end_headers()
            if status != 101:
                self.wfile.write(b"{}")

        do_POST = do_GET

    def call(port, path, headers=None, *, body=None, method="GET"):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
        try:
            connection.request(method, path, headers=headers or {}, body=body)
            response = connection.getresponse()
            result = response.status, dict(response.getheaders())
            response.read()
            return result
        finally:
            connection.close()

    try:
        for mode in ("regular", "trusted", *APPS):
            server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
            server.mode = mode
            servers[mode] = server
            thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
            threads.append(thread)
            thread.start()
        with ExitStack() as reservations:
            ports = {}
            for mode in ("regular", "trusted"):
                reserved = reservations.enter_context(socket.socket())
                reserved.bind(("127.0.0.1", 0))
                ports[mode] = reserved.getsockname()[1]
        replacements = {
            8080: ports["regular"], 8615: ports["trusted"],
            8089: servers["regular"].server_port, 8086: servers["trusted"].server_port,
            8619: servers["catalog"].server_port,
            8643: servers["workspace"].server_port,
        }
        config = Path(__file__).with_name("gateway.conf").read_text(encoding="utf-8")
        config = fixture_config(config, replacements)
        with tempfile.TemporaryDirectory(prefix="catalog-gateway-check-") as directory:
            source = Path(directory) / "nginx.conf"
            source.write_text(config, encoding="utf-8")
            source.chmod(0o644)
            subprocess.run([
                "docker", "run", "-d", "--rm", "--pull=never", "--name", name,
                "--network", "host", "--user", "101:101", "--read-only", "--cap-drop=ALL",
                "--security-opt", "no-new-privileges:true", "--memory", "128m",
                "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=128m,mode=1777",
                "--mount", f"type=bind,src={source.resolve()},dst=/etc/nginx/nginx.conf,readonly",
                "--entrypoint", "nginx", IMAGE, "-g", "daemon off;",
            ], check=True, capture_output=True, text=True, timeout=30)
            deadline = time.monotonic() + 10
            for port in ports.values():
                while True:
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                            break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise RuntimeError("temporary Nginx did not start")
                        time.sleep(0.1)
            checks = 0
            for app, mode, port in ((app, mode, port) for app in APPS for mode, port in ports.items()):
                base, auth_path = APPS[app]["base"], APPS[app]["auth_path"]
                host = f"catalog.fixture.invalid:{port}"
                origin = "http://" + host
                for suffix in ("", "static/js/fixture.js", "_stcore/health", "_stcore/stream"):
                    websocket = suffix == "_stcore/stream"
                    allowed = 101 if websocket else 200
                    cases = (("", 401), ("other", 403), ("unavailable", 500), ("simon", allowed),
                             ("tail-only", allowed if mode == "trusted" else 401))
                    for account, expected in cases:
                        cookie = "workspace_session=fixture-only; _streamlit_xsrf=fixture-xsrf"
                        if account and account != "tail-only":
                            cookie += "; fixture_account=" + account
                        headers = {
                            "Host": host, "Origin": origin, "Cookie": cookie,
                            "Authorization": "Bearer fixture-only", "X-TRS-Workspace-Service-Token": "fixture-only",
                            "X-TRS-Workspace-Trusted": "true", "X-Catalog-Canary": "must-not-forward",
                            "X-Catalog-Listener": "trusted", "Tailscale-User-Name": "Fixture Simon",
                            "Tailscale-User-Login": TAIL_LOGIN if account == "tail-only" else "unlinked@fixture.invalid",
                            "Tailscale-User-Profile-Pic": "must-not-forward", "X-Xsrftoken": "fixture-xsrf",
                        }
                        if websocket:
                            headers.update({"Upgrade": "websocket", "Connection": "Upgrade", "Sec-WebSocket-Key": WS_KEY,
                                            "Sec-WebSocket-Version": "13", "Sec-WebSocket-Protocol": "streamlit"})
                        if not account:
                            # This case is anonymous. The separate unbound-user
                            # check below exercises an actual unlinked identity.
                            headers.pop("Tailscale-User-Login", None)
                            headers.pop("Tailscale-User-Name", None)
                        before_auth, before_upstream = len(auth_requests), len(upstream_requests)
                        status, response_headers = call(port, base + suffix, headers)
                        assert status == expected, f"{app}/{mode}/{suffix or 'HTML'}/{account or 'anonymous'}: {status} != {expected}"
                        if status == 101:
                            assert response_headers.get("Sec-WebSocket-Accept") == WS_ACCEPT, "invalid WS handshake"
                        assert len(auth_requests) == before_auth + 1, "request bypassed auth"
                        auth = auth_requests[-1]
                        observed = auth["headers"]
                        assert auth["mode"] == mode and auth["path"] == auth_path, "wrong auth listener or target"
                        assert set(observed) <= {"host", "connection", "cookie", "tailscale-user-login", "tailscale-user-name"}, "auth header leaked"
                        assert observed.get("host") == host and observed.get("cookie") == cookie, "auth lost session or Host"
                        if mode == "trusted":
                            assert observed.get("tailscale-user-login") == headers.get("Tailscale-User-Login"), "trusted auth lost login"
                            assert observed.get("tailscale-user-name") == headers.get("Tailscale-User-Name"), "trusted auth lost name"
                        else:
                            assert not any(key.startswith("tailscale-") for key in observed), "ordinary auth accepted Tail headers"
                        if status in (200, 101):
                            assert len(upstream_requests) == before_upstream + 1, "authorized request did not reach upstream"
                            record = upstream_requests[-1]
                            observed = record["headers"]
                            assert record["mode"] == app and record["path"] == base + suffix, "upstream app or path changed"
                            assert observed.get("host") == host and observed.get("origin") == origin, "Host/Origin changed"
                            assert observed.get("cookie") == "_streamlit_xsrf=fixture-xsrf", "workspace cookie leaked"
                            assert observed.get("x-xsrftoken") == "fixture-xsrf", "XSRF header lost"
                            assert not any(key.startswith(("x-trs-", "tailscale-", "x-catalog-")) or key in {"authorization", "proxy-authorization"} for key in observed), "identity header leaked"
                            if websocket:
                                assert observed.get("upgrade") == "websocket" and observed.get("sec-websocket-key") == WS_KEY, "WS headers lost"
                                assert observed.get("sec-websocket-protocol") == "streamlit", "WS protocol lost"
                        else:
                            assert len(upstream_requests) == before_upstream, "unauthorized request reached upstream"
                        checks += 1

            # A trusted listener does not grant an unbound machine identity an
            # account. All four application surfaces must reject it before WS.
            for app, settings in APPS.items():
                for suffix in ("", "static/js/fixture.js", "_stcore/health", "_stcore/stream"):
                    headers = {"Host": f"workspace.fixture.invalid:{ports['trusted']}",
                               "Cookie": "workspace_session=fixture-only; _streamlit_xsrf=fixture-xsrf",
                               "Tailscale-User-Login": UNBOUND_TAIL_LOGIN,
                               "Tailscale-User-Name": "Unbound account"}
                    if suffix == "_stcore/stream":
                        headers.update({"Upgrade": "websocket", "Connection": "Upgrade", "Sec-WebSocket-Key": WS_KEY,
                                        "Sec-WebSocket-Version": "13", "Sec-WebSocket-Protocol": "streamlit"})
                    before_auth, before_upstream = len(auth_requests), len(upstream_requests)
                    status, _ = call(ports["trusted"], settings["base"] + suffix, headers)
                    assert status == 403, f"{app}/{suffix}: trusted unbound account was not refused"
                    assert len(auth_requests) == before_auth + 1 and len(upstream_requests) == before_upstream
                    assert auth_requests[-1]["mode"] == "trusted" and auth_requests[-1]["path"] == settings["auth_path"]
                    checks += 1

            # The regular front door preserves existing business routes and bodies.
            port = ports["regular"]
            host = f"workspace.fixture.invalid:{port}"
            ordinary = {
                "Host": host, "Origin": "http://" + host, "Cookie": "workspace_session=fixture-only",
                "Authorization": "Bearer fixture-only", "X-TRS-Workspace-Service-Token": "fixture-only",
                "X-TRS-Workspace-Helper-Token": "fixture-helper", "Idempotency-Key": "fixture-once",
                "X-T0-Action": "fixture-action", "Content-Type": "application/octet-stream",
            }
            uploads = (("/workspace?fixture=1", b"", "GET"),
                       ("/apps/worklog/api/v1/service-requests/req-fixture/attachments", b"x" * (20 * 1024 * 1024), "POST"),
                       ("/api/workspace/scans", b"s" * (15 * 1024 * 1024), "POST"),
                       ("/api/business-fixture", b"b" * (3 * 1024 * 1024), "POST"),
                       ("/workspace/fixture-redirect", b"", "GET"))
            for path, body, method in uploads:
                before = len(fallback_requests), len(auth_requests), len(upstream_requests)
                forged = {**ordinary, "Tailscale-User-Login": TAIL_LOGIN, "Tailscale-User-Name": "Spoofed",
                          "Tailscale-User-Profile-Pic": "spoofed"}
                status, response_headers = call(port, path, forged, body=body, method=method)
                assert status == (303 if path.endswith("fixture-redirect") else 200), "business fallback failed"
                assert (len(fallback_requests), len(auth_requests), len(upstream_requests)) == (before[0] + 1, before[1], before[2]), "business fallback rerouted"
                record = fallback_requests[-1]
                assert record["mode"] == "regular" and record["path"] == path and record["method"] == method, "business request changed"
                assert record["size"] == len(body) and record["sha256"] == hashlib.sha256(body).hexdigest(), "upload body changed"
                assert all(record["headers"].get(key.lower()) == value for key, value in ordinary.items()), "business header changed"
                assert not any(key.startswith("tailscale-") for key in record["headers"]), "business fallback forwarded Tail identity"
                assert response_headers.get("Set-Cookie") == "workspace_fixture=ok; Path=/; HttpOnly", "business Set-Cookie changed"
                if status == 303:
                    assert response_headers.get("Location") == "/workspace/account?fixture=1", "business redirect changed"
                checks += 1

            before = len(fallback_requests), len(auth_requests), len(upstream_requests)
            for path in ("/", "/workspace", "/apps/worklog/"):
                assert call(ports["trusted"], path)[0] == 404, "trusted Catalog listener exposed fallback"
                checks += 1
            for port in ports.values():
                for path in ("/__catalog_access", "/__workspace_access"):
                    assert call(port, path)[0] == 404, "internal auth endpoint became public"
                    checks += 1
            assert (len(fallback_requests), len(auth_requests), len(upstream_requests)) == before, "denied fallback reached fixtures"
        return {"status": "ok", "checks": checks, "listeners": 2, "catalog_paths": 4,
                "workspace_paths": 4, "applications": list(APPS), "headers_isolated": True,
                "trusted_unbound_denied": True,
                "regular_tail_spoof_denied": True, "trusted_fallback": 404, "upload_mib": [20, 15, 3], "fixtures_only": True}
    finally:
        try:
            cleanup = subprocess.run(["docker", "rm", "-f", name], capture_output=True, text=True, timeout=15)
            if cleanup.returncode and "No such container" not in cleanup.stderr:
                raise RuntimeError("temporary container cleanup failed: " + name)
        finally:
            for server in servers.values():
                server.shutdown()
                server.server_close()
            for thread in threads:
                thread.join(2)


if __name__ == "__main__":
    try:
        print(json.dumps(main(), separators=(",", ":")))
    except Exception as error:
        print(json.dumps({"status": "failed", "error": f"{type(error).__name__}: {error}"}, separators=(",", ":")))
        raise SystemExit(1)
