# -*- coding: utf-8 -*-
# Export static execution graph as JSON / Mermaid / HTML.

from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any, Mapping

FINGERPRINT_VERSION = "l0-runtime-graph-v1"
VOLATILE_METADATA_KEYS = {
    "run_id",
    "started_at",
    "finished_at",
    "created_at",
    "updated_at",
    "timestamp",
    "time",
}


def export_execution_graph(
    graph: object,
    output_path: str | Path,
    *,
    format: str | None = None,
    skip_if_unchanged: bool = True,
    fingerprint_scope: str = "structure",
) -> Path:
    path = Path(output_path)
    fmt = _detect_format(path, format)
    payload = graph_to_dict(graph)
    if skip_if_unchanged and _is_same_fingerprint(path, payload, scope=fingerprint_scope):
        return path
    if fmt == "json":
        out = write_execution_graph_json(payload, path)
    elif fmt in {"mmd", "mermaid"}:
        out = write_execution_graph_mermaid(payload, path)
    elif fmt in {"html", "htm"}:
        out = write_execution_graph_html(payload, path)
    else:
        raise ValueError(f"Unsupported execution graph export format: {fmt}")
    _write_fingerprint(path, payload, scope=fingerprint_scope)
    return out


def export_execution_graph_if_changed(
    graph: object,
    output_path: str | Path,
    *,
    format: str | None = None,
    fingerprint_scope: str = "structure",
) -> tuple[Path, bool]:
    path = Path(output_path)
    fmt = _detect_format(path, format)
    payload = graph_to_dict(graph)
    if _is_same_fingerprint(path, payload, scope=fingerprint_scope):
        return path, False
    if fmt == "json":
        out = write_execution_graph_json(payload, path)
    elif fmt in {"mmd", "mermaid"}:
        out = write_execution_graph_mermaid(payload, path)
    elif fmt in {"html", "htm"}:
        out = write_execution_graph_html(payload, path)
    else:
        raise ValueError(f"Unsupported execution graph export format: {fmt}")
    _write_fingerprint(path, payload, scope=fingerprint_scope)
    return out, True


def write_execution_graph_json(graph: object, output_path: str | Path) -> Path:
    path = Path(output_path)
    payload = graph_to_dict(graph)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_execution_graph_mermaid(graph: object, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(graph_to_mermaid(graph), encoding="utf-8")
    return path


def write_execution_graph_html(graph: object, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(graph_to_html(graph), encoding="utf-8")
    return path


def graph_to_dict(graph: object) -> dict[str, Any]:
    return _graph_payload(graph)


def graph_fingerprint(graph: object, *, scope: str = "structure") -> str:
    payload = graph_to_dict(graph)
    if str(scope).lower() == "exact":
        normalized = payload
    else:
        normalized = _normalize_graph_for_structure_fingerprint(payload, depth=0)
    fingerprint_payload = {
        "version": FINGERPRINT_VERSION,
        "scope": str(scope).lower(),
        "graph": normalized,
    }
    raw = json.dumps(fingerprint_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def graph_to_mermaid(graph: object) -> str:
    payload = graph_to_dict(graph)
    lines = ["flowchart TD"]
    _append_mermaid_node(lines, payload, parent_id=None, seen={})
    return "\n".join(lines) + "\n"


def graph_to_html(graph: object) -> str:
    mermaid = graph_to_mermaid(graph)
    payload = graph_to_dict(graph)
    title = str(payload.get("label") or payload.get("id") or "execution graph")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)} - L0 Runtime Graph</title>
  <style>
    body {{
      margin: 0;
      padding: 32px;
      font-family: Georgia, 'Times New Roman', serif;
      color: #1d2a24;
      background:
        radial-gradient(circle at 18% 12%, rgba(66, 148, 110, 0.16), transparent 28rem),
        linear-gradient(135deg, #f6f1e5 0%, #dfe9da 100%);
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 28px;
      background: rgba(255, 252, 244, 0.82);
      border: 1px solid rgba(68, 94, 75, 0.18);
      border-radius: 24px;
      box-shadow: 0 24px 80px rgba(43, 61, 51, 0.16);
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: clamp(28px, 4vw, 48px);
      letter-spacing: -0.04em;
    }}
    p {{
      margin: 0 0 24px;
      color: #526358;
    }}
    .diagram {{
      overflow: auto;
      padding: 18px;
      border-radius: 18px;
      background: #fffaf0;
    }}
    details {{
      margin-top: 22px;
    }}
    pre {{
      overflow: auto;
      padding: 16px;
      border-radius: 14px;
      background: #17211c;
      color: #f4f1e8;
    }}
  </style>
</head>
<body>
  <main>
    <h1>{html.escape(title)}</h1>
    <p>Static execution plan generated from the project L0 runtime graph.</p>
    <div class="diagram">
      <pre class="mermaid">{html.escape(mermaid)}</pre>
    </div>
    <details>
      <summary>Mermaid source</summary>
      <pre>{html.escape(mermaid)}</pre>
    </details>
  </main>
  <script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
    mermaid.initialize({{ startOnLoad: true, theme: 'neutral' }});
  </script>
</body>
</html>
"""


# Backward-compatible aliases for early local experiments.
execution_graph_to_mermaid = graph_to_mermaid
execution_graph_to_html = graph_to_html


def _detect_format(path: Path, explicit: str | None) -> str:
    if explicit:
        return str(explicit).strip().lower().lstrip(".")
    suffix = path.suffix.lower().lstrip(".")
    return suffix or "json"


def _graph_payload(graph: object) -> dict[str, Any]:
    if isinstance(graph, Mapping):
        return dict(graph)
    as_dict = getattr(graph, "as_dict", None)
    if callable(as_dict):
        return dict(as_dict())
    raise TypeError("graph must be a mapping or expose as_dict()")


def _is_same_fingerprint(path: Path, payload: Mapping[str, Any], *, scope: str) -> bool:
    if not path.exists():
        return False
    marker = _fingerprint_marker_path(path)
    if not marker.exists():
        return False
    try:
        stored = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
        return False
    stored_scope = str(stored.get("scope", "")).lower()
    expected_scope = str(scope).lower()
    if stored_scope != expected_scope:
        return False
    expected = graph_fingerprint(payload, scope=scope)
    return str(stored.get("fingerprint", "")) == expected


def _write_fingerprint(path: Path, payload: Mapping[str, Any], *, scope: str) -> None:
    marker = _fingerprint_marker_path(path)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        json.dumps(
            {
                "version": FINGERPRINT_VERSION,
                "scope": str(scope).lower(),
                "fingerprint": graph_fingerprint(payload, scope=scope),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _fingerprint_marker_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".fingerprint.json")


def _normalize_graph_for_structure_fingerprint(node: Mapping[str, Any], *, depth: int) -> dict[str, Any]:
    kind = str(node.get("kind") or "")
    label = str(node.get("label") or "")
    if depth == 0 or kind in {"run", "lifecycle_run"}:
        label = "__root__"
    metadata = _normalize_metadata(node.get("metadata", {}))
    children = [
        _normalize_graph_for_structure_fingerprint(child, depth=depth + 1)
        for child in tuple(node.get("children", ()) or ())
        if isinstance(child, Mapping)
    ]
    payload: dict[str, Any] = {
        "kind": kind,
        "label": label,
        "children": children,
    }
    if metadata:
        payload["metadata"] = metadata
    return payload


def _normalize_metadata(value: Any) -> Any:
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in sorted(value.items(), key=lambda kv: str(kv[0])):
            key_text = str(key)
            if key_text.lower() in VOLATILE_METADATA_KEYS:
                continue
            out[key_text] = _normalize_metadata(item)
        return out
    if isinstance(value, (list, tuple)):
        return [_normalize_metadata(item) for item in value]
    return value


def _append_mermaid_node(
    lines: list[str],
    node: Mapping[str, Any],
    *,
    parent_id: str | None,
    seen: dict[str, int],
) -> None:
    raw_id = str(node.get("id") or node.get("label") or "node")
    node_id = _safe_node_id(raw_id)
    if node_id in seen:
        seen[node_id] += 1
        node_id = f"{node_id}_{seen[node_id]}"
    else:
        seen[node_id] = 0

    label = _node_label(node)
    lines.append(f'  {node_id}["{label}"]')
    if parent_id:
        lines.append(f"  {parent_id} --> {node_id}")

    for child in tuple(node.get("children", ()) or ()):
        if isinstance(child, Mapping):
            _append_mermaid_node(lines, child, parent_id=node_id, seen=seen)


def _node_label(node: Mapping[str, Any]) -> str:
    label = str(node.get("label") or node.get("id") or "node")
    kind = str(node.get("kind") or "")
    if kind:
        label = f"{label}\\n({kind})"
    return label.replace('"', '\\"')


def _safe_node_id(value: str) -> str:
    text = re.sub(r"[^0-9a-zA-Z_]+", "_", value).strip("_")
    if not text:
        text = "node"
    if text[0].isdigit():
        text = f"n_{text}"
    return text
