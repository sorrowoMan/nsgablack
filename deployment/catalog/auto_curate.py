#!/usr/bin/env python3
"""Root-only host scheduler for bounded, incremental Catalog explanations.

This launcher follows the verified current image. It never rebuilds or publishes
framework source, and never passes its private grants to the web container.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import uuid


SCHEMA = "nsgablack.catalog.auto_curate/v1"
CONTAINER = "nsgablack-catalog-curation-worker"
LABEL = "org.nsgablack.catalog-curation"
RUN_LABEL = LABEL + ".run"
BATCH_LIMIT, DAILY_LIMIT = 20, 100
MAX_DRAIN_ITEMS = 557
PROGRESS_SCHEMA = "nsgablack.catalog.curation_progress/v1"
PROBE = r'''
import hashlib, json, os
from pathlib import Path
from runtime import configure_reader
os.environ['NSGABLACK_CATALOG_HOSTED_SOURCE']='database'
os.environ['NSGABLACK_CATALOG_READER_CONFIG']='/run/secrets/catalog-reader.json'
configure_reader(os.environ)
from nsgablack.catalog.curate import load_packets
from nsgablack.catalog.curation_provider import PROMPT_VERSION
from nsgablack.catalog.curation_store import resolve_knowledge_store
model=os.environ['NSGABLACK_CATALOG_AI_MODEL']
packets=load_packets(Path('/opt/catalog/knowledge-packets.json'),index_path=Path('/opt/catalog/knowledge-sources.json'))
store=resolve_knowledge_store(readonly=True)
entries=[{'key':key,'digest':p['source_digest'],'evidence':bool(p.get('evidence')),
          'cached':store.get(key,p['source_digest'],model=model,prompt_version=PROMPT_VERSION) is not None}
         for key,p in sorted(packets.items())]
source_index_sha256=hashlib.sha256(json.dumps({e['key']:e['digest'] for e in entries},sort_keys=True,separators=(',',':')).encode()).hexdigest()
print(json.dumps({'model':model,'prompt':PROMPT_VERSION,'entries':entries,'source_index_sha256':source_index_sha256}))
'''


class SchedulerError(RuntimeError):
    """Only fixed diagnostic categories may leave the launcher."""


class Interrupted(SchedulerError):
    pass


def atomic_json(path: Path, value: dict, *, mode: int = 0o600) -> None:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(data.encode()) > 2 * 1024 * 1024:
        raise SchedulerError("state_too_large")
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex)
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_state(path: Path) -> dict:
    if not path.exists():
        return {"schema": SCHEMA, "budget_day": "", "reserved": 0, "catchup_reserved": 0,
                "cursor": "", "failures": {}, "circuit_until": 0}
    if path.stat().st_size > 2 * 1024 * 1024:
        raise SchedulerError("state_too_large")
    value = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(value, dict) or value.get("schema") != SCHEMA
            or type(value.get("reserved")) is not int or not 0 <= value["reserved"] <= DAILY_LIMIT + MAX_DRAIN_ITEMS
            or type(value.get("catchup_reserved", 0)) is not int
            or not 0 <= value.get("catchup_reserved", 0) <= min(value["reserved"], MAX_DRAIN_ITEMS)
            or value["reserved"] - value.get("catchup_reserved", 0) > DAILY_LIMIT
            or not isinstance(value.get("failures"), dict) or len(value["failures"]) > 10000
            or not isinstance(value.get("cursor"), str) or not isinstance(value.get("budget_day"), str)
            or not isinstance(value.get("circuit_until"), (int, float))):
        raise SchedulerError("state_invalid")
    for item in value["failures"].values():
        if (not isinstance(item, dict) or type(item.get("count")) is not int
                or not 1 <= item["count"] <= 100000 or not isinstance(item.get("next"), (int, float))):
            raise SchedulerError("state_invalid")
    value.setdefault("catchup_reserved", 0)
    return value


def identity(entry: dict, probe: dict) -> str:
    return hashlib.sha256(json.dumps([entry["key"], entry["digest"], probe["model"], probe["prompt"]]).encode()).hexdigest()


def validate_probe(probe: object) -> dict:
    if not isinstance(probe, dict) or not isinstance(probe.get("entries"), list) or len(probe["entries"]) > 10000:
        raise SchedulerError("probe_invalid")
    for field in ("model", "prompt"):
        if not isinstance(probe.get(field), str) or not re.fullmatch(r"[A-Za-z0-9._/-]{1,128}", probe[field]):
            raise SchedulerError("probe_invalid")
    keys = set()
    for entry in probe["entries"]:
        if (not isinstance(entry, dict) or not isinstance(entry.get("key"), str)
                or not re.fullmatch(r"[A-Za-z0-9_.-]{1,200}", entry["key"])
                or entry["key"] in keys or not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("digest")))
                or type(entry.get("cached")) is not bool or type(entry.get("evidence")) is not bool):
            raise SchedulerError("probe_invalid")
        keys.add(entry["key"])
    expected = hashlib.sha256(json.dumps({e["key"]: e["digest"] for e in probe["entries"]},
                                        sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if probe.get("source_index_sha256") != expected:
        raise SchedulerError("probe_source_index_invalid")
    return probe


def refresh_state(state: dict, probe: dict, now: float) -> None:
    day = datetime.fromtimestamp(now, timezone.utc).date().isoformat()
    if day > state["budget_day"]:
        state.update(budget_day=day, reserved=0, catchup_reserved=0)
    active = {identity(entry, probe) for entry in probe["entries"] if not entry["cached"]}
    state["failures"] = {key: value for key, value in state["failures"].items() if key in active}


def select_batch(state: dict, probe: dict, now: float, *, drain: bool = False,
                 allowed: set[str] | None = None) -> list[dict]:
    refresh_state(state, probe, now)
    if now < state["circuit_until"]:
        return []
    eligible = [entry for entry in probe["entries"] if not entry["cached"] and entry["evidence"]
                and (allowed is None or identity(entry, probe) in allowed)
                and state["failures"].get(identity(entry, probe), {}).get("next", 0) <= now]
    eligible.sort(key=lambda entry: (entry["key"] <= state["cursor"], entry["key"]))
    capacity = (min(BATCH_LIMIT, MAX_DRAIN_ITEMS - state.get("catchup_reserved", 0),
                    DAILY_LIMIT + MAX_DRAIN_ITEMS - state["reserved"]) if drain
                else min(BATCH_LIMIT, max(0, DAILY_LIMIT - state["reserved"])))
    return eligible[:capacity]


def reserve(state: dict, probe: dict, selected: list[dict], now: float, *, drain: bool = False) -> None:
    state["reserved"] += len(selected)
    if drain:
        state["catchup_reserved"] = state.get("catchup_reserved", 0) + len(selected)
    if selected:
        state["cursor"] = selected[-1]["key"]
    for entry in selected:
        key = identity(entry, probe)
        count = min(state["failures"].get(key, {}).get("count", 0) + 1, 100000)
        state["failures"][key] = {"count": count, "next": now + min(86400, 900 * 2 ** min(count - 1, 7))}


def settle(state: dict, probe: dict, selected: list[dict], report: object, now: float) -> dict:
    if not isinstance(report, dict) or not isinstance(report.get("results"), list):
        raise SchedulerError("batch_report_invalid")
    entries = {entry["key"]: entry for entry in selected}
    seen, generated, failed = set(), 0, 0
    for result in report["results"]:
        key = result.get("entry_key") if isinstance(result, dict) else None
        if key not in entries or key in seen:
            raise SchedulerError("batch_report_invalid")
        seen.add(key)
        if "error" in result:
            failed += 1
            if result["error"] in {"ai_http_401", "ai_http_402", "ai_http_403"}:
                state["circuit_until"] = now + 86400
        else:
            generated += 1
            state["failures"].pop(identity(entries[key], probe), None)
    # Missing rows remain reserved and backed off: an ambiguous exit is not free.
    failed += len(entries) - len(seen)
    return {"generated": generated, "failed": failed}


def progress_status(state: dict, probe: dict, *, image: str, release: str, now: float,
                    selected: int = 0, generated: int = 0, failed: int = 0,
                    running: bool = False, drain: bool = False) -> dict:
    """Explain the next eligible ordinary run without disclosing private state."""
    current = sum(entry["cached"] for entry in probe["entries"])
    total = len(probe["entries"])
    pending = [entry for entry in probe["entries"] if not entry["cached"] and entry["evidence"]]
    next_at = None
    if running:
        reason = "catching_up" if drain else "running"
    elif current == total:
        reason = "complete"
    elif pending:
        earliest = min(state["failures"].get(identity(entry, probe), {}).get("next", now) for entry in pending)
        if state["circuit_until"] > now:
            reason = "circuit_open"
        elif state["reserved"] >= DAILY_LIMIT:
            reason = "daily_limit"
        elif earliest > now:
            reason = "backoff"
        else:
            reason = "partial" if failed else "updated"
        next_at = max(now + 900, earliest, state["circuit_until"])
        if state["reserved"] >= DAILY_LIMIT:
            # A backwards clock cannot mint another ordinary daily allowance.
            day = datetime.fromisoformat(state["budget_day"]).replace(tzinfo=timezone.utc)
            next_at = max(next_at, (day + timedelta(days=1)).timestamp())
    else:
        reason = "awaiting_evidence"
    return {"ok": not failed, "release": release, "image_id": image,
            "checked_at": datetime.fromtimestamp(now, timezone.utc).isoformat(),
            "source_index_sha256": probe["source_index_sha256"],
            "prompt_version": probe["prompt"],
            "total": total, "current": current, "remaining": total - current,
            "without_evidence": sum(not e["evidence"] and not e["cached"] for e in probe["entries"]),
            "selected": selected, "generated": generated, "failed": failed,
            "daily_limit": DAILY_LIMIT, "reserved_today": state["reserved"],
            "status": reason, "next_eligible_at": next_at, "circuit_until": state["circuit_until"]}


def public_progress(status: dict) -> dict:
    """Allowlist the host-to-web document; never copy grants, keys or errors."""
    value = {"schema": PROGRESS_SCHEMA}
    for name in ("total", "current", "remaining", "selected", "generated", "failed", "daily_limit", "reserved_today"):
        item = status.get(name, 0)
        value[name] = item if type(item) is int and 0 <= item <= 10000 else 0
    for name in ("next_eligible_at", "circuit_until"):
        item = status.get(name)
        value[name] = item if type(item) in (int, float) and 0 <= item < 10 ** 12 else None
    for name, pattern in (("release", r"[A-Za-z0-9_.-]{1,200}"),
                          ("image_id", r"sha256:[0-9a-f]{64}"),
                          ("source_index_sha256", r"[0-9a-f]{64}"),
                          ("prompt_version", r"[A-Za-z0-9._/-]{1,128}"),
                          ("checked_at", r"[0-9T:.+Z-]{1,64}")):
        item = status.get(name, "")
        value[name] = item if isinstance(item, str) and re.fullmatch(pattern, item) else ""
    known = {"complete", "daily_limit", "backoff", "circuit_open", "running", "catching_up",
             "updated", "partial", "awaiting_evidence", "failed"}
    value["status"] = status.get("status") if status.get("status") in known else "failed"
    return value


def save_status(root: Path, state: dict, status: dict) -> None:
    state["last_status"] = status
    atomic_json(root / "automation/state/state.json", state)
    directory = root / "automation/progress"
    directory.mkdir(mode=0o755, parents=True, exist_ok=True)
    os.chmod(directory, 0o755)
    # Mount the directory, not this replaceable inode, read-only in the web.
    atomic_json(directory / "progress.json", public_progress(status), mode=0o644)


class Docker:
    def __init__(self, root: Path):
        self.root = root
        self.cidfile = root / "automation/state/worker.cid"
        self.ownerfile = root / "automation/state/worker-owner.json"
        self.cid = None

    def call(self, arguments: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(["docker", *arguments], capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise SchedulerError("docker_timeout") from None

    def model(self) -> str:
        """Read only the public identity from the root-private provider grant."""
        path = self.root / "secrets/deepseek.json"
        if not path.is_file() or path.stat().st_size > 16384:
            raise SchedulerError("ai_config_invalid")
        value = json.loads(path.read_text(encoding="utf-8"))
        model = value.get("model", "deepseek-flash") if isinstance(value, dict) else None
        if (not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9._/-]{1,128}", model)
                or model.startswith("sk-")):
            raise SchedulerError("ai_config_invalid")
        return model

    def image(self) -> tuple[str, str]:
        release = (self.root / "current").resolve(strict=True)
        if not release.is_relative_to((self.root / "releases").resolve()):
            raise SchedulerError("release_path_invalid")
        active = self.call(["inspect", "--format", "{{.Image}}", "nsgablack-catalog"])
        image = active.stdout.strip()
        if active.returncode or not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
            raise SchedulerError("release_not_active")
        service_path = release / "service.json"
        if service_path.is_file():
            service = json.loads(service_path.read_text())
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", str(service.get("image_id", ""))):
                raise SchedulerError("release_image_invalid")
            if service["image_id"] != image:
                raise SchedulerError("release_not_active")
        else:
            # Reader-only rollouts have a source manifest but no three-service
            # manifest. Bind the active image to that exact published source.
            source = json.loads((release / "release-manifest.json").read_text()).get("content_sha256", "")
            if not re.fullmatch(r"[0-9a-f]{64}", str(source)):
                raise SchedulerError("release_source_invalid")
            checked = self.call(["exec", "nsgablack-catalog", "python", "-c",
                "import json;from pathlib import Path;print(json.loads(Path('/opt/catalog/release-manifest.json').read_text())['content_sha256'])"])
            if checked.returncode or checked.stdout.strip() != source:
                raise SchedulerError("release_not_active")
        return image, release.name

    def cleanup(self) -> None:
        cid = self.cid
        if not cid and self.cidfile.exists():
            cid = self.cidfile.read_text().strip()
        if not cid and not self.ownerfile.exists():
            return
        if cid and not re.fullmatch(r"[0-9a-f]{64}", cid):
            raise SchedulerError("worker_identity_invalid")
        owner = json.loads(self.ownerfile.read_text())
        nonce = owner.get("nonce", "")
        if not re.fullmatch(r"[0-9a-f]{32}", nonce):
            raise SchedulerError("worker_identity_invalid")
        # A timed-out create can reach the daemon before --cidfile is written.
        # Name lookup is permitted only to resolve our persisted nonce; removal
        # still uses the exact returned ID, never the shared name.
        checked = self.call(["inspect", "--format", '{{.Id}} {{.Name}} {{index .Config.Labels "' + LABEL
                             + '"}} {{index .Config.Labels "' + RUN_LABEL + '"}}', cid or CONTAINER])
        fields = checked.stdout.strip().split()
        if checked.returncode == 0 and (len(fields) != 4 or not re.fullmatch(r"[0-9a-f]{64}", fields[0])
                or fields[1:] != ["/" + CONTAINER, "managed", nonce] or (cid and fields[0] != cid)):
            raise SchedulerError("worker_identity_conflict")
        if checked.returncode == 0:
            removed = self.call(["rm", "--force", fields[0]])
            if removed.returncode:
                raise SchedulerError("worker_cleanup_failed")
        else:
            # An inspect error can mean an unavailable daemon. Only a successful
            # exact lookup proving absence permits forgetting the creation intent.
            query = "id=" + cid if cid else "name=^/" + CONTAINER + "$"
            absent = self.call(["ps", "-a", "--no-trunc", "--quiet", "--filter", query])
            if absent.returncode or absent.stdout.strip():
                raise SchedulerError("worker_inspect_failed")
        self.cidfile.unlink(missing_ok=True)
        self.ownerfile.unlink(missing_ok=True)
        self.cid = None

    def run(self, image: str, *, probe: bool, keys: list[str] | None = None, execute=False) -> object:
        if not probe and execute is not True:
            raise SchedulerError("ai_paid_execution_required")
        self.cleanup()
        nonce = uuid.uuid4().hex
        atomic_json(self.ownerfile, {"nonce": nonce})
        args = ["create", "--name", CONTAINER, "--cidfile", str(self.cidfile), "--label", LABEL + "=managed",
                "--label", RUN_LABEL + "=" + nonce,
                "--user", "10001:10001" if probe else "0:0", "--network", "trs_capture_demo_default", "--read-only", "--tmpfs",
                "/tmp:rw,nosuid,nodev,size=256m", "--memory", "1g", "--cpus", "1", "--pids-limit", "128",
                "--security-opt", "no-new-privileges:true", "--cap-drop", "ALL", "--log-driver", "none"]
        grants = ("catalog-reader.json",) if probe else ("catalog-writer.json", "deepseek.json")
        for name in grants:
            args += ["--mount", f"type=bind,src={self.root}/secrets/{name},dst=/run/secrets/{name},readonly"]
        if probe:
            args += ["--env", "NSGABLACK_CATALOG_AI_MODEL=" + self.model(), "--entrypoint", "python", image,
                     "-c", "import sys;sys.path.insert(0,'/opt/catalog');" + PROBE]
        else:
            args += ["--env", "NSGABLACK_CATALOG_WRITER_CONFIG=/run/secrets/catalog-writer.json", image,
                     "python", "/opt/catalog/runtime.py", "curate", "--execute", "--limit", str(len(keys)), "--workers", "3",
                     "--keys", ",".join(keys)]
        try:
            created = self.call(args)
            if created.returncode or not re.fullmatch(r"[0-9a-f]{64}", created.stdout.strip()):
                raise SchedulerError("worker_create_failed")
            self.cid = created.stdout.strip()
            result = self.call(["start", "--attach", self.cid], timeout=1800 if not probe else 180)
            if len(result.stdout.encode()) > 4 * 1024 * 1024:
                raise SchedulerError("worker_output_oversized")
            try:
                value = json.loads(result.stdout)
            except ValueError:
                raise SchedulerError("worker_failed") from None
            if probe and result.returncode:
                raise SchedulerError("probe_failed")
            return value
        finally:
            self.cleanup()


def once(root: Path, *, now: float | None = None, docker=None, execute=False) -> dict:
    if execute is not True:
        raise SchedulerError("ai_paid_execution_required")
    clock = time.time if now is None else lambda: now
    now = clock()
    path = root / "automation/state/state.json"
    state = read_state(path)
    docker = docker or Docker(root)
    image, release = docker.image()
    probe = validate_probe(docker.run(image, probe=True))
    selected = select_batch(state, probe, now)
    reserve(state, probe, selected, now)
    save_status(root, state, progress_status(state, probe, image=image, release=release, now=now,
                                           selected=len(selected), running=bool(selected)))
    counts = {"generated": 0, "failed": 0}
    if selected:
        if docker.image()[0] != image:
            raise SchedulerError("release_changed")
        report = docker.run(image, probe=False, keys=[e["key"] for e in selected], execute=True)
        counts = settle(state, probe, selected, report, clock())
        # Persist settlement before the independent read: a failed read must not
        # erase used allowance or pretend the writer's report is DB visibility.
        atomic_json(path, state)
        updated = validate_probe(docker.run(image, probe=True))
        if (docker.image()[0] != image or updated["source_index_sha256"] != probe["source_index_sha256"]
                or (updated["model"], updated["prompt"]) != (probe["model"], probe["prompt"])):
            raise SchedulerError("release_changed")
        probe = updated
    status = progress_status(state, probe, image=image, release=release, now=clock(),
                             selected=len(selected), **counts)
    save_status(root, state, status)
    return status


def drain(root: Path, *, max_items: int, now: float | None = None, docker=None, execute=False) -> dict:
    if execute is not True:
        raise SchedulerError("ai_paid_execution_required")
    """One explicit bounded catch-up of this image's frozen pending identities.

    The CLI still holds the shared host lock. Each frozen identity is attempted
    at most once; backoff and authentication circuits remain in force. Paid
    calls are reserved durably, including crashes, and never refill the timer's
    ordinary daily allowance.
    """
    if type(max_items) is not int or not 1 <= max_items <= MAX_DRAIN_ITEMS:
        raise SchedulerError("drain_limit_invalid")
    clock = time.time if now is None else lambda: now
    path = root / "automation/state/state.json"
    state, docker = read_state(path), docker or Docker(root)
    image, release = docker.image()
    probe = validate_probe(docker.run(image, probe=True))
    refresh_state(state, probe, clock())
    pending = [entry for entry in probe["entries"] if not entry["cached"] and entry["evidence"]]
    pending.sort(key=lambda entry: (entry["key"] <= state["cursor"], entry["key"]))
    plan = {identity(entry, probe) for entry in pending[:max_items]}
    frozen_index, frozen_model, frozen_prompt = probe["source_index_sha256"], probe["model"], probe["prompt"]
    state["last_drain"] = {"id": uuid.uuid4().hex, "image_id": image, "source_index_sha256": frozen_index,
                           "max_items": max_items, "plan_count": len(plan), "reserved": 0}
    counts, selected_total = {"generated": 0, "failed": 0}, 0
    save_status(root, state, progress_status(state, probe, image=image, release=release, now=clock(),
                                           running=bool(plan), drain=True))
    while plan:
        selected = select_batch(state, probe, clock(), drain=True, allowed=plan)
        if not selected:
            break
        if docker.image()[0] != image:
            raise SchedulerError("release_changed")
        reserve(state, probe, selected, clock(), drain=True)
        selected_total += len(selected)
        state["last_drain"]["reserved"] += len(selected)
        for entry in selected:
            plan.remove(identity(entry, probe))
        save_status(root, state, progress_status(state, probe, image=image, release=release, now=clock(),
                                               selected=selected_total, running=True, drain=True, **counts))
        report = docker.run(image, probe=False, keys=[entry["key"] for entry in selected], execute=True)
        result = settle(state, probe, selected, report, clock())
        for name in counts:
            counts[name] += result[name]
        atomic_json(path, state)
        updated = validate_probe(docker.run(image, probe=True))
        if (docker.image()[0] != image or updated["source_index_sha256"] != frozen_index
                or updated["model"] != frozen_model or updated["prompt"] != frozen_prompt):
            raise SchedulerError("release_changed")
        probe = updated
        save_status(root, state, progress_status(state, probe, image=image, release=release, now=clock(),
                                               selected=selected_total, running=bool(plan), drain=True, **counts))
    # Completion is derived from the store probe, never from model response counts.
    status = progress_status(state, probe, image=image, release=release, now=clock(),
                             selected=selected_total, **counts)
    save_status(root, state, status)
    return status


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/opt/framework-catalog"))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--status", action="store_true")
    mode.add_argument("--drain", action="store_true", help="Explicit bounded catch-up; requires --max-items")
    parser.add_argument("--max-items", type=int)
    parser.add_argument("--execute", action="store_true", help="Explicitly allow paid model requests for this invocation")
    args = parser.parse_args(argv)
    if not args.status and not args.execute:
        parser.error("--execute is required for paid model requests; --status is read-only")
    if (args.drain and (args.max_items is None or not 1 <= args.max_items <= MAX_DRAIN_ITEMS)) or (not args.drain and args.max_items is not None):
        parser.error(f"--drain requires --max-items 1..{MAX_DRAIN_ITEMS}; other modes do not accept it")
    lock = None
    try:
        if not hasattr(os, "geteuid") or os.geteuid() != 0:
            raise SchedulerError("root_required")
        import fcntl
        os.umask(0o077)
        directory = args.root / "automation/state"
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if args.status:
            print(json.dumps(read_state(directory / "state.json").get("last_status", {"status": "not_run"})))
            return 0
        lock = (directory / "worker.lock").open("a")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({"ok": True, "status": "already_running"}))
            return 0

        def interrupted(signum, frame):
            raise Interrupted("interrupted")

        signal.signal(signal.SIGTERM, interrupted)
        signal.signal(signal.SIGINT, interrupted)
        result = drain(args.root, max_items=args.max_items, execute=True) if args.drain else once(args.root, execute=True)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["ok"] else 1
    except Exception as exc:
        error = str(exc) if isinstance(exc, SchedulerError) else type(exc).__name__
        persistence_error = None
        if lock is not None:
            try:
                path = args.root / "automation/state/state.json"
                state = read_state(path)
                state["last_status"] = {**state.get("last_status", {}), "ok": False, "status": "failed", "error": error}
                save_status(args.root, state, state["last_status"])
            except (OSError, ValueError, TypeError, SchedulerError) as state_error:
                # Preserve a damaged budget and explicitly report the failure.
                persistence_error = type(state_error).__name__
        print(json.dumps({"ok": False, "status": "failed", "error": error,
                          "status_persistence_error": persistence_error}))
        return 1
    finally:
        if lock is not None:
            lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
