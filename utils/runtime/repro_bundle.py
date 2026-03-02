"""Repro bundle helpers for export / compare / replay in Run Inspector."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple
import datetime as _dt
import hashlib
import json
import locale
import os
import platform
import subprocess
import sys
import time

from ..engineering.file_io import atomic_write_json
from ..engineering.schema_version import stamp_schema


def _json_safe(value: Any) -> Any:
    try:
        import numpy as np  # type: ignore

        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, (np.integer, np.floating)):
            return value.item()
    except Exception:
        pass
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return str(value)


def _canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    text = json.dumps(
        _json_safe(dict(payload)),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return text.encode("utf-8")


def _sha256_payload(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _sha256_file(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    try:
        with path.open("rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
    except Exception:
        return None
    return h.hexdigest()


def _now_iso(ts: Optional[float] = None) -> str:
    point = float(ts if ts is not None else time.time())
    return _dt.datetime.fromtimestamp(point, tz=_dt.timezone.utc).isoformat()


def _run_cmd(args: List[str], *, cwd: Path, timeout_s: float = 2.0) -> Optional[str]:
    def _decode(data: Any) -> str:
        raw = data if isinstance(data, (bytes, bytearray)) else b""
        if not raw:
            return ""
        candidates = []
        pref = locale.getpreferredencoding(False)
        if pref:
            candidates.append(str(pref))
        candidates.extend(["utf-8", "gbk", "cp936"])
        seen = set()
        for enc in candidates:
            key = str(enc).lower()
            if key in seen:
                continue
            seen.add(key)
            try:
                return bytes(raw).decode(enc)
            except Exception:
                continue
        return bytes(raw).decode("utf-8", errors="replace")

    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            timeout=float(timeout_s),
            check=False,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    text = _decode(proc.stdout).strip()
    return text or None


def _detect_git(workspace: Path) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "commit": None,
        "branch": None,
        "dirty": None,
        "root": None,
    }
    root_text = _run_cmd(["git", "rev-parse", "--show-toplevel"], cwd=workspace)
    if not root_text:
        return out
    root = Path(root_text).resolve()
    out["root"] = str(root)
    out["commit"] = _run_cmd(["git", "rev-parse", "HEAD"], cwd=root)
    out["branch"] = _run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root)
    dirty_text = _run_cmd(["git", "status", "--porcelain"], cwd=root)
    if dirty_text is None:
        out["dirty"] = None
    else:
        out["dirty"] = bool(dirty_text.strip())
    return out


def _normalize_entry(entrypoint: str, workspace: Path) -> str:
    text = str(entrypoint or "").strip()
    if not text:
        return ""
    if ":" in text:
        path_part, func = text.rsplit(":", 1)
    else:
        path_part, func = text, "build_solver"
    p = Path(path_part)
    if not p.is_absolute():
        p = (workspace / p).resolve()
    else:
        p = p.resolve()
    return f"{p}:{func}"


def _path_ref(path_value: Any, workspace: Path) -> Dict[str, Any]:
    text = str(path_value or "").strip()
    if not text:
        return {"path": "", "exists": False, "sha256": None}
    p = Path(text)
    if not p.is_absolute():
        p = (workspace / p).resolve()
    else:
        p = p.resolve()
    return {
        "path": str(p),
        "exists": bool(p.is_file()),
        "sha256": _sha256_file(p),
    }


def _sanitize_artifacts(artifacts: Optional[Mapping[str, Any]], workspace: Path) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if not isinstance(artifacts, Mapping):
        return out
    for key, value in artifacts.items():
        k = str(key)
        if value is None:
            out[k] = None
            continue
        if isinstance(value, (str, os.PathLike)):
            out[k] = _path_ref(value, workspace)
            continue
        out[k] = _json_safe(value)
    return out


def _load_json_dict(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_jsonl(path: Path, *, max_rows: int = 200000) -> List[Dict[str, Any]]:
    if not path.is_file():
        return []
    rows: List[Dict[str, Any]] = []
    for idx, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines()):
        if idx >= max_rows:
            break
        text = line.strip()
        if not text:
            continue
        try:
            obj = json.loads(text)
        except Exception:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _hash_signature_set(sequence_records: Iterable[Mapping[str, Any]]) -> Optional[str]:
    signatures = sorted(
        {
            str(rec.get("signature", "")).strip()
            for rec in sequence_records
            if str(rec.get("signature", "")).strip()
        }
    )
    if not signatures:
        return None
    return _sha256_payload({"signatures": signatures})


def _hash_trie_fingerprint(sequence_records: Iterable[Mapping[str, Any]]) -> Optional[str]:
    edges: Dict[Tuple[str, str], int] = {}
    has_edge = False
    for rec in sequence_records:
        events = rec.get("events") if isinstance(rec, Mapping) else None
        if not isinstance(events, list) or not events:
            continue
        weight = int(rec.get("count", 1) or 1)
        prefix: List[str] = []
        for evt in events:
            token = str(evt)
            edge_key = ("->".join(prefix), token)
            edges[edge_key] = int(edges.get(edge_key, 0)) + weight
            prefix.append(token)
            has_edge = True
    if not has_edge:
        return None
    payload = [
        {"prefix": key[0], "token": key[1], "count": int(count)}
        for key, count in sorted(edges.items(), key=lambda x: (x[0][0], x[0][1]))
    ]
    return _sha256_payload({"trie_edges": payload})


def _hash_trace_groups(trace_events: Iterable[Mapping[str, Any]]) -> Optional[str]:
    groups: Dict[str, Dict[str, Any]] = {}
    total = 0
    for event in trace_events:
        total += 1
        thread_id = str(event.get("thread_id", "") or "")
        task_id = str(event.get("task_id", "") or "")
        token = str(event.get("token", "") or "")
        status = str(event.get("status", "") or "ok").lower()
        duration_ns = int(event.get("duration_ns", 0) or 0)
        gid = f"{thread_id}|{task_id}"
        grp = groups.get(gid)
        if grp is None:
            grp = {
                "thread_id": thread_id,
                "task_id": task_id,
                "events": 0,
                "errors": 0,
                "duration_ns_sum": 0,
                "duration_ns_max": 0,
                "tokens": {},
            }
            groups[gid] = grp
        grp["events"] = int(grp["events"]) + 1
        if status == "error":
            grp["errors"] = int(grp["errors"]) + 1
        grp["duration_ns_sum"] = int(grp["duration_ns_sum"]) + duration_ns
        if duration_ns > int(grp["duration_ns_max"]):
            grp["duration_ns_max"] = duration_ns
        token_map = grp["tokens"]
        token_map[token] = int(token_map.get(token, 0)) + 1
    if total <= 0:
        return None
    payload = []
    for gid in sorted(groups.keys()):
        g = groups[gid]
        payload.append(
            {
                "thread_id": g["thread_id"],
                "task_id": g["task_id"],
                "events": int(g["events"]),
                "errors": int(g["errors"]),
                "duration_ns_sum": int(g["duration_ns_sum"]),
                "duration_ns_max": int(g["duration_ns_max"]),
                "tokens": [
                    {"token": token, "count": count}
                    for token, count in sorted(g["tokens"].items(), key=lambda x: x[0])
                ],
            }
        )
    return _sha256_payload({"trace_groups": payload})


def _digest_decision_trace(path: Path) -> Dict[str, Any]:
    rows = _load_jsonl(path)
    if not rows:
        return {
            "path": str(path),
            "exists": bool(path.is_file()),
            "count": 0,
            "hash": None,
        }
    by_type: Dict[str, int] = {}
    by_component: Dict[str, int] = {}
    for row in rows:
        t = str(row.get("event_type", "unknown"))
        c = str(row.get("component", "unknown"))
        by_type[t] = int(by_type.get(t, 0)) + 1
        by_component[c] = int(by_component.get(c, 0)) + 1
    summary = {
        "count": int(len(rows)),
        "first_seq": int(rows[0].get("seq", 0) or 0),
        "last_seq": int(rows[-1].get("seq", 0) or 0),
        "event_type_counts": dict(sorted(by_type.items())),
        "component_counts": dict(sorted(by_component.items())),
    }
    return {
        "path": str(path),
        "exists": True,
        "count": int(len(rows)),
        "hash": _sha256_payload(summary),
        "summary": summary,
    }


def _build_structure_proof(
    *,
    workspace: Path,
    artifacts: Mapping[str, Any],
) -> Dict[str, Any]:
    proof: Dict[str, Any] = {
        "sequence_signature_set_hash": None,
        "sequence_trie_fingerprint_hash": None,
        "trace_group_digest_hash": None,
        "decision_trace_digest_hash": None,
    }

    seq_raw = artifacts.get("sequence_graph_json")
    if isinstance(seq_raw, Mapping):
        path = Path(str(seq_raw.get("path", "") or ""))
    else:
        path = Path(str(seq_raw or ""))
        if not path.is_absolute():
            path = (workspace / path).resolve()
    if path and path.is_file():
        payload = _load_json_dict(path)
        records = payload.get("sequence_records", [])
        trace_events = payload.get("trace_events", [])
        if isinstance(records, list):
            proof["sequence_signature_set_hash"] = _hash_signature_set(records)
            proof["sequence_trie_fingerprint_hash"] = _hash_trie_fingerprint(records)
        if isinstance(trace_events, list):
            proof["trace_group_digest_hash"] = _hash_trace_groups(trace_events)

    decision_raw = artifacts.get("decision_trace_jsonl")
    if isinstance(decision_raw, Mapping):
        dt_path = Path(str(decision_raw.get("path", "") or ""))
    else:
        dt_path = Path(str(decision_raw or ""))
        if dt_path and not dt_path.is_absolute():
            dt_path = (workspace / dt_path).resolve()
    if dt_path and dt_path.is_file():
        proof["decision_trace_digest_hash"] = _digest_decision_trace(dt_path).get("hash")

    return proof


def _solver_section(solver: Any, attrs: List[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for attr in attrs:
        if not hasattr(solver, attr):
            continue
        out[str(attr)] = _json_safe(getattr(solver, attr, None))
    return out


def _runtime_view(solver: Any) -> Dict[str, Any]:
    runtime = _solver_section(
        solver,
        [
            "max_generations",
            "max_steps",
            "pop_size",
            "dimension",
            "num_objectives",
            "context_store_backend",
            "context_store_ttl_seconds",
            "context_store_key_prefix",
            "snapshot_store_backend",
            "snapshot_store_ttl_seconds",
            "snapshot_store_key_prefix",
            "snapshot_schema",
            "snapshot_strict",
        ],
    )
    runtime["solver_class"] = solver.__class__.__name__ if solver is not None else None
    return runtime


def _wiring_view(run_snapshot: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    if not isinstance(run_snapshot, Mapping):
        return {}
    return {
        "adapter": run_snapshot.get("adapter"),
        "pipeline": _json_safe(run_snapshot.get("pipeline") or {}),
        "strategies": _json_safe(run_snapshot.get("strategies") or []),
        "biases": _json_safe(run_snapshot.get("biases") or []),
        "plugins": _json_safe(run_snapshot.get("plugins") or []),
        "context_store": _json_safe(run_snapshot.get("context_store") or {}),
        "snapshot_store": _json_safe(run_snapshot.get("snapshot_store") or {}),
        "structure_hash": run_snapshot.get("structure_hash"),
        "structure_hash_short": run_snapshot.get("structure_hash_short"),
    }


def _environment_view(workspace: Path) -> Dict[str, Any]:
    git = _detect_git(workspace)
    return {
        "python_version": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "workspace": str(workspace),
        "cwd": str(Path.cwd().resolve()),
        "git": git,
    }


def build_repro_bundle(
    *,
    run_id: str,
    solver: Any,
    entrypoint: str,
    workspace: str | os.PathLike[str] | None,
    run_snapshot: Optional[Mapping[str, Any]] = None,
    artifacts: Optional[Mapping[str, Any]] = None,
    started_at: Optional[float] = None,
    finished_at: Optional[float] = None,
) -> Dict[str, Any]:
    ws = Path(workspace).resolve() if workspace is not None else Path.cwd().resolve()
    started = float(started_at) if started_at is not None else None
    finished = float(finished_at) if finished_at is not None else time.time()
    duration = None
    if started is not None:
        duration = max(0.0, float(finished) - float(started))

    normalized_entry = _normalize_entry(entrypoint, ws)
    wiring = _wiring_view(run_snapshot)
    runtime = _runtime_view(solver)
    artifacts_view = _sanitize_artifacts(artifacts, ws)
    structure_proof = _build_structure_proof(workspace=ws, artifacts=artifacts_view)
    config_hash = _sha256_payload({"wiring": wiring, "runtime": runtime, "entrypoint": normalized_entry})

    payload = {
        "run_id": str(run_id),
        "created_at": _now_iso(),
        "started_at": _now_iso(started) if started is not None else None,
        "finished_at": _now_iso(finished) if finished is not None else None,
        "duration_sec": duration,
        "recipe": {
            "entrypoint": normalized_entry,
            "workspace": str(ws),
        },
        "random": {
            "seed_policy": "solver.random_seed",
            "effective_seed": getattr(solver, "random_seed", None),
        },
        "wiring": wiring,
        "runtime": runtime,
        "env": _environment_view(ws),
        "inputs": [],
        "artifacts": artifacts_view,
        "structure_proof": structure_proof,
        "config_fingerprint_sha256": config_hash,
    }
    return stamp_schema(payload, "repro_bundle")


def write_repro_bundle(
    bundle: Mapping[str, Any],
    *,
    output_dir: str | os.PathLike[str] = "runs",
    run_id: Optional[str] = None,
) -> Path:
    payload = dict(bundle)
    rid = str(run_id or payload.get("run_id") or "run")
    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{rid}.repro_bundle.json"
    atomic_write_json(path, payload, ensure_ascii=False, indent=2, encoding="utf-8")
    return path


def load_repro_bundle(path: str | os.PathLike[str]) -> Dict[str, Any]:
    p = Path(path).expanduser().resolve()
    payload = _load_json_dict(p)
    if payload:
        payload.setdefault("bundle_path", str(p))
    return payload


def compare_repro_bundle(
    bundle: Mapping[str, Any],
    *,
    current_entrypoint: str,
    current_workspace: str | os.PathLike[str] | None,
    current_snapshot: Optional[Mapping[str, Any]] = None,
    current_solver: Any = None,
) -> Dict[str, Any]:
    ws = Path(current_workspace).resolve() if current_workspace is not None else Path.cwd().resolve()
    current_entry = _normalize_entry(current_entrypoint, ws)
    current_wiring = _wiring_view(current_snapshot)
    current_runtime = _runtime_view(current_solver) if current_solver is not None else {}

    findings: List[Dict[str, Any]] = []

    def _add(
        level: str,
        code: str,
        message: str,
        *,
        expected: Any = None,
        actual: Any = None,
    ) -> None:
        findings.append(
            {
                "level": str(level),
                "code": str(code),
                "message": str(message),
                "expected": _json_safe(expected),
                "actual": _json_safe(actual),
            }
        )

    expected_entry = str((bundle.get("recipe") or {}).get("entrypoint") or "")
    if expected_entry and expected_entry != current_entry:
        _add(
            "BLOCKER",
            "entrypoint_mismatch",
            "entrypoint does not match bundle recipe",
            expected=expected_entry,
            actual=current_entry,
        )

    expected_hash = str((bundle.get("wiring") or {}).get("structure_hash") or "")
    actual_hash = str(current_wiring.get("structure_hash") or "")
    if expected_hash and actual_hash and expected_hash != actual_hash:
        _add(
            "BLOCKER",
            "structure_hash_mismatch",
            "wiring structure hash differs",
            expected=expected_hash,
            actual=actual_hash,
        )

    expected_adapter = str((bundle.get("wiring") or {}).get("adapter") or "")
    actual_adapter = str(current_wiring.get("adapter") or "")
    if expected_adapter and actual_adapter and expected_adapter != actual_adapter:
        _add(
            "BLOCKER",
            "adapter_mismatch",
            "adapter class differs",
            expected=expected_adapter,
            actual=actual_adapter,
        )

    expected_seed = (bundle.get("random") or {}).get("effective_seed")
    if expected_seed is not None and current_solver is not None:
        actual_seed = getattr(current_solver, "random_seed", None)
        if actual_seed != expected_seed:
            _add(
                "WARN",
                "seed_mismatch",
                "effective random seed differs",
                expected=expected_seed,
                actual=actual_seed,
            )

    for key in ("max_generations", "max_steps", "context_store_backend", "snapshot_store_backend"):
        expected = (bundle.get("runtime") or {}).get(key)
        if expected is None:
            continue
        actual = current_runtime.get(key)
        if actual is None:
            continue
        if actual != expected:
            _add(
                "WARN",
                f"runtime_{key}_mismatch",
                f"runtime field `{key}` differs",
                expected=expected,
                actual=actual,
            )

    levels = [str(row.get("level", "INFO")).upper() for row in findings]
    blockers = sum(1 for lv in levels if lv == "BLOCKER")
    warns = sum(1 for lv in levels if lv == "WARN")
    infos = sum(1 for lv in levels if lv == "INFO")

    status = "match" if blockers == 0 and warns == 0 else ("blocked" if blockers > 0 else "drift")
    return {
        "status": status,
        "blockers": blockers,
        "warnings": warns,
        "infos": infos,
        "findings": findings,
    }


def apply_bundle_to_solver(solver: Any, bundle: Mapping[str, Any]) -> List[str]:
    applied: List[str] = []
    random_section = bundle.get("random") if isinstance(bundle.get("random"), Mapping) else {}
    runtime_section = bundle.get("runtime") if isinstance(bundle.get("runtime"), Mapping) else {}

    seed = random_section.get("effective_seed")
    if seed is not None:
        setter = getattr(solver, "set_random_seed", None)
        if callable(setter):
            try:
                setter(int(seed))
                applied.append(f"seed={int(seed)}")
            except Exception:
                pass
        else:
            try:
                setattr(solver, "random_seed", int(seed))
                applied.append(f"seed={int(seed)}")
            except Exception:
                pass

    for key in ("max_generations", "max_steps"):
        if key not in runtime_section:
            continue
        value = runtime_section.get(key)
        if value is None:
            continue
        if not hasattr(solver, key):
            continue
        try:
            setattr(solver, key, int(value))
            applied.append(f"{key}={int(value)}")
        except Exception:
            continue
    return applied


def replay_spec(bundle: Mapping[str, Any]) -> Dict[str, Any]:
    recipe = bundle.get("recipe") if isinstance(bundle.get("recipe"), Mapping) else {}
    random_section = bundle.get("random") if isinstance(bundle.get("random"), Mapping) else {}
    runtime = bundle.get("runtime") if isinstance(bundle.get("runtime"), Mapping) else {}
    return {
        "run_id": str(bundle.get("run_id", "") or ""),
        "entrypoint": str(recipe.get("entrypoint", "") or ""),
        "workspace": str(recipe.get("workspace", "") or ""),
        "seed": random_section.get("effective_seed"),
        "max_generations": runtime.get("max_generations"),
        "max_steps": runtime.get("max_steps"),
    }
