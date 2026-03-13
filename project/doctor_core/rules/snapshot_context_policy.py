"""Context/snapshot store policy checks used by project doctor."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

from ..model import DoctorDiagnostic

# ---------------------------------------------------------------------------
# Large-object keys that MUST NOT be stored directly in context
# ---------------------------------------------------------------------------
_LARGE_OBJECT_BARE_KEYS = {
    "population",
    "objectives",
    "constraint_violations",
    "history",
    "pareto_solutions",
    "pareto_objectives",
    "decision_trace",
}

_CONTEXT_VAR_NAMES = {
    "context",
    "ctx",
    "context_store",
    "ctx_store",
}


def _normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def check_context_store_policy(
    *,
    root: Path,
    solver: object,
    build_file: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
    min_redis_key_prefix_len: int,
    min_redis_ttl_seconds: float,
) -> None:
    backend = str(getattr(solver, "context_store_backend", "") or "").strip().lower()
    if not backend:
        runtime = getattr(solver, "runtime", None)
        store = getattr(runtime, "context_store", None)
        if store is not None:
            cls_name = store.__class__.__name__.lower()
            backend = "redis" if "redis" in cls_name else "memory"
    if backend != "redis":
        return

    level = "error" if strict else "warn"

    key_prefix = str(getattr(solver, "context_store_key_prefix", "") or "").strip()
    if not key_prefix:
        add(
            diags,
            level,
            "redis-key-prefix-missing",
            "Redis context backend requires non-empty context_store_key_prefix.",
            build_file,
        )
    else:
        if len(key_prefix) < min_redis_key_prefix_len:
            add(
                diags,
                level,
                "redis-key-prefix-too-short",
                (
                    f"context_store_key_prefix is too short ({len(key_prefix)}); "
                    f"recommended >= {min_redis_key_prefix_len} chars."
                ),
                build_file,
            )
        root_token = _normalize_token(root.name)
        prefix_token = _normalize_token(key_prefix)
        if root_token and root_token not in prefix_token:
            add(
                diags,
                level,
                "redis-key-prefix-missing-project-name",
                (
                    "context_store_key_prefix should contain project name token "
                    f"('{root.name}') to avoid cross-project key pollution."
                ),
                build_file,
            )

    ttl = getattr(solver, "context_store_ttl_seconds", None)
    if ttl is None:
        add(
            diags,
            "warn",
            "redis-ttl-policy-implicit",
            (
                "Redis TTL policy is implicit (context_store_ttl_seconds=None). "
                "Set an explicit value (seconds) or 0 for no-expire strategy."
            ),
            build_file,
        )
        return
    try:
        ttl_value = float(ttl)
    except Exception:
        add(
            diags,
            level,
            "redis-ttl-invalid",
            f"context_store_ttl_seconds must be numeric or None; got: {ttl!r}",
            build_file,
        )
        return
    if 0.0 < ttl_value < min_redis_ttl_seconds:
        add(
            diags,
            "warn",
            "redis-ttl-too-small",
            (
                f"context_store_ttl_seconds={ttl_value:g}s may expire keys too early; "
                f"recommended >= {min_redis_ttl_seconds:g}s."
            ),
            build_file,
        )


def check_snapshot_store_policy(
    *,
    solver: object,
    build_file: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
    min_redis_key_prefix_len: int,
    min_redis_ttl_seconds: float,
    safe_snapshot_serializer: str,
) -> None:
    backend = str(getattr(solver, "snapshot_store_backend", "") or "").strip().lower()
    if not backend:
        runtime = getattr(solver, "runtime", None)
        store = getattr(runtime, "snapshot_store", None)
        if store is not None:
            cls_name = store.__class__.__name__.lower()
            if "redis" in cls_name:
                backend = "redis"
            elif "file" in cls_name:
                backend = "file"
            else:
                backend = "memory"
    if backend != "redis":
        return

    level = "error" if strict else "warn"
    key_prefix = str(getattr(solver, "snapshot_store_key_prefix", "") or "").strip()
    if not key_prefix:
        add(
            diags,
            level,
            "snapshot-redis-key-prefix-missing",
            "Redis snapshot backend requires non-empty snapshot_store_key_prefix.",
            build_file,
        )
    elif len(key_prefix) < min_redis_key_prefix_len:
        add(
            diags,
            level,
            "snapshot-redis-key-prefix-too-short",
            (
                f"snapshot_store_key_prefix is too short ({len(key_prefix)}); "
                f"recommended >= {min_redis_key_prefix_len} chars."
            ),
            build_file,
        )

    serializer = str(getattr(solver, "snapshot_store_serializer", safe_snapshot_serializer) or "").strip().lower()
    if serializer not in {"safe", "pickle_signed", "pickle_unsafe"}:
        add(
            diags,
            level,
            "snapshot-redis-serializer-unknown",
            f"Unknown snapshot_store_serializer: {serializer!r}.",
            build_file,
        )
    elif serializer == "pickle_unsafe":
        add(
            diags,
            level,
            "snapshot-redis-pickle-unsafe",
            (
                "snapshot_store_serializer=pickle_unsafe allows unsafe deserialization. "
                "Use serializer='safe' (recommended) or 'pickle_signed' with HMAC."
            ),
            build_file,
        )
    elif serializer == "pickle_signed":
        env_var = str(getattr(solver, "snapshot_store_hmac_env_var", "NSGABLACK_SNAPSHOT_HMAC_KEY") or "").strip()
        if not env_var:
            add(
                diags,
                level,
                "snapshot-redis-pickle-signed-missing-key",
                "snapshot_store_hmac_env_var is empty while serializer=pickle_signed.",
                build_file,
            )

    ttl = getattr(solver, "snapshot_store_ttl_seconds", None)
    if ttl is None:
        add(
            diags,
            "warn",
            "snapshot-redis-ttl-policy-implicit",
            (
                "Redis snapshot TTL policy is implicit (snapshot_store_ttl_seconds=None). "
                "Set explicit TTL or 0 for no-expire strategy."
            ),
            build_file,
        )
        return
    try:
        ttl_value = float(ttl)
    except Exception:
        add(
            diags,
            level,
            "snapshot-redis-ttl-invalid",
            f"snapshot_store_ttl_seconds must be numeric or None; got: {ttl!r}",
            build_file,
        )
        return
    if 0.0 < ttl_value < min_redis_ttl_seconds:
        add(
            diags,
            "warn",
            "snapshot-redis-ttl-too-small",
            (
                f"snapshot_store_ttl_seconds={ttl_value:g}s may expire snapshots too early; "
                f"recommended >= {min_redis_ttl_seconds:g}s."
            ),
            build_file,
        )


def _safe_first_dim(value: object) -> int | None:
    if value is None:
        return None
    shape = getattr(value, "shape", None)
    if shape is not None:
        try:
            if len(shape) >= 1:
                return int(shape[0])
        except Exception:
            pass
    try:
        return int(len(value))  # type: ignore[arg-type]
    except Exception:
        return None


def check_snapshot_refs(
    *,
    solver: object,
    build_file: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
    add: Callable[[List[DoctorDiagnostic], str, str, str, Path | None], None],
    key_snapshot_key: str,
    snapshot_ref_keys: Sequence[str],
    snapshot_payload_ref_map: Sequence[tuple[str, str]],
    key_population: str,
    key_objectives: str,
    key_constraint_violations: str,
) -> None:
    getter = getattr(solver, "get_context", None)
    if not callable(getter):
        return
    try:
        ctx = getter()
    except Exception as exc:
        add(
            diags,
            "warn",
            "context-read-failed",
            f"Failed to read runtime context for snapshot checks: {exc}",
            build_file,
        )
        return
    if not isinstance(ctx, dict):
        return

    level = "error" if strict else "warn"
    snap_key_raw = ctx.get(key_snapshot_key)
    snap_key = str(snap_key_raw).strip() if snap_key_raw is not None else ""

    ref_values: dict[str, str] = {}
    for key in snapshot_ref_keys:
        if key not in ctx:
            continue
        try:
            val = ctx.get(key)
        except Exception:
            val = None
        if val is None or str(val).strip() == "":
            add(
                diags,
                level,
                "snapshot-ref-empty",
                f"Context key '{key}' is empty; snapshot refs must be non-empty.",
                build_file,
            )
            continue
        ref_values[key] = str(val).strip()

    if ref_values and not snap_key:
        add(
            diags,
            level,
            "snapshot-ref-consistency",
            "Context has snapshot refs but snapshot_key is missing/empty.",
            build_file,
        )

    has_state = any(
        getattr(solver, attr, None) is not None
        for attr in ("population", "objectives", "constraint_violations")
    )
    if has_state and not snap_key:
        add(
            diags,
            level,
            "snapshot-ref-missing",
            "Solver has population/objectives/violations but context has no snapshot_key. "
            "Ensure SnapshotStore writes are enabled.",
            build_file,
        )

    reader = getattr(solver, "read_snapshot", None)
    read_cache: dict[str, object] = {}
    read_errors: dict[str, str] = {}

    def _read_snapshot_cached(key: str) -> tuple[object | None, str | None]:
        if key in read_cache:
            return read_cache[key], None
        if key in read_errors:
            return None, read_errors[key]
        if not callable(reader):
            return None, None
        try:
            payload = reader(key)
        except Exception as exc:  # pragma: no cover - defensive
            read_errors[key] = str(exc)
            return None, read_errors[key]
        read_cache[key] = payload
        return payload, None

    if snap_key and ref_values:
        mismatched = [f"{k}={v}" for k, v in sorted(ref_values.items()) if v != snap_key]
        if mismatched:
            add(
                diags,
                "warn",
                "snapshot-ref-consistency",
                "Snapshot refs differ from snapshot_key (verify intentional split refs): "
                + ", ".join(mismatched[:8])
                + (" ..." if len(mismatched) > 8 else ""),
                build_file,
            )

    if callable(reader):
        for ref_key, ref_value in sorted(ref_values.items()):
            payload, read_err = _read_snapshot_cached(ref_value)
            if read_err is not None:
                add(
                    diags,
                    level,
                    "snapshot-ref-consistency",
                    f"read_snapshot failed for context ref {ref_key}='{ref_value}': {read_err}",
                    build_file,
                )
                continue
            if payload is None:
                add(
                    diags,
                    level,
                    "snapshot-ref-consistency",
                    f"Context ref {ref_key}='{ref_value}' has no readable snapshot payload.",
                    build_file,
                )

    if not snap_key:
        return

    payload, read_err = _read_snapshot_cached(snap_key)
    if read_err is not None:
        add(
            diags,
            level,
            "snapshot-read-failed",
            f"snapshot_key present but read_snapshot failed: {read_err}",
            build_file,
        )
        return
    if payload is None:
        add(
            diags,
            level,
            "snapshot-missing",
            "snapshot_key present but snapshot_store returned None.",
            build_file,
        )
        return
    if not isinstance(payload, dict):
        add(
            diags,
            level,
            "snapshot-payload-integrity",
            f"snapshot_key payload should be dict-like; got {type(payload).__name__}.",
            build_file,
        )
        return

    expected_keys: set[str] = set()
    if has_state:
        expected_keys.update((key_population, key_objectives, key_constraint_violations))
    for payload_key, ref_key in snapshot_payload_ref_map:
        if ref_key in ref_values:
            expected_keys.add(payload_key)

    missing_payload = sorted(k for k in expected_keys if k not in payload)
    if missing_payload:
        add(
            diags,
            level,
            "snapshot-payload-integrity",
            "snapshot payload missing required keys: "
            + ", ".join(missing_payload[:10])
            + (" ..." if len(missing_payload) > 10 else ""),
            build_file,
        )

    pop_rows = _safe_first_dim(payload.get(key_population))
    obj_rows = _safe_first_dim(payload.get(key_objectives))
    vio_rows = _safe_first_dim(payload.get(key_constraint_violations))

    shape_issues: List[str] = []
    if pop_rows is not None and obj_rows is not None and pop_rows != obj_rows:
        shape_issues.append(f"population({pop_rows}) != objectives({obj_rows})")
    if pop_rows is not None and vio_rows is not None and pop_rows != vio_rows:
        shape_issues.append(f"population({pop_rows}) != constraint_violations({vio_rows})")
    if pop_rows is None and obj_rows is not None and vio_rows is not None and obj_rows != vio_rows:
        shape_issues.append(f"objectives({obj_rows}) != constraint_violations({vio_rows})")
    if shape_issues:
        add(
            diags,
            level,
            "snapshot-payload-integrity",
            "snapshot payload shape mismatch: " + "; ".join(shape_issues[:6]),
            build_file,
        )


# ---------------------------------------------------------------------------
# New rule: scan source files for raw large-object keys written to context
# ---------------------------------------------------------------------------

def _extract_key_str(node: ast.expr) -> Optional[str]:
    """Extract a key string from a subscript slice node."""
    if isinstance(node, ast.Constant) and isinstance(node.s, str):
        return node.s
    if isinstance(node, ast.Name) and node.id.startswith("KEY_"):
        return node.id[4:].lower()
    return None


def _scan_py_file_for_large_context_writes(
    path: Path,
) -> List[Tuple[int, str, str]]:
    """Return list of (lineno, key, snippet) for direct large-object context writes."""
    hits: List[Tuple[int, str, str]] = []
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
        lines = src.splitlines()
        tree = ast.parse(src, filename=str(path))
    except (OSError, SyntaxError):
        return hits

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Subscript):
                continue
            if not isinstance(target.value, ast.Name):
                continue
            if target.value.id not in _CONTEXT_VAR_NAMES:
                continue
            key = _extract_key_str(target.slice)
            if key and key in _LARGE_OBJECT_BARE_KEYS:
                ln = node.lineno
                snippet = lines[ln - 1].strip() if 0 < ln <= len(lines) else ""
                hits.append((ln, key, snippet))
    return hits


def check_large_objects_in_context(
    *,
    root: Path,
    diags: List[DoctorDiagnostic],
    strict: bool,
    add: Callable[[List[DoctorDiagnostic], str, str, str, Optional[Path]], None],
    skip_dirs: Optional[set] = None,
) -> None:
    """Detect large objects written directly to context dict.

    Any write like ``context['population'] = arr`` is a protocol violation.
    Large objects must go through SnapshotStore; context may only hold the
    ``*_ref`` key pointing to the snapshot.
    """
    _skip = skip_dirs or {
        "__pycache__", ".git", ".mypy_cache", ".pytest_cache",
        ".venv", "venv", "node_modules", "site-packages",
    }
    level = "error" if strict else "warn"
    total = 0

    for py_file in sorted(root.rglob("*.py")):
        if any(part in _skip for part in py_file.parts):
            continue
        hits = _scan_py_file_for_large_context_writes(py_file)
        for lineno, key, snippet in hits:
            total += 1
            try:
                rel = py_file.relative_to(root)
            except ValueError:
                rel = py_file
            ref_key = f"{key}_ref"
            add(
                diags,
                level,
                "large-object-in-context",
                (
                    f"{rel}:{lineno}: key '{key}' is a large object and must not be "
                    f"stored directly in context. Use SnapshotStore.write() and store "
                    f"context['{ref_key}'] = snapshot_key instead.  "
                    f"Snippet: {snippet!r}"
                ),
                py_file,
            )

    if total == 0:
        add(
            diags,
            "info",
            "large-object-context-scan-ok",
            f"Scanned {root}: no direct large-object context writes detected.",
            None,
        )
