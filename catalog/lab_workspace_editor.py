"""Offline, identity-bound code editor for a workspace draft.

The component only edits text. It never imports, evaluates or saves a Project.
The caller applies an accepted event to its draft before handling ``save`` with
the existing revision/CAS operation. Change ``identity`` for an external source
replacement (including discard); ordinary rerenders preserve the live cursor.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import lru_cache
import hashlib
from pathlib import Path
from typing import Any

MAX_TEXT_BYTES = 512 * 1024
MAX_SEQUENCE = (1 << 53) - 1  # Exact integer range shared with JavaScript.
_ASSETS = Path(__file__).with_name("workspace_editor_frontend")


class EditorEventError(ValueError):
    """An untrusted component message did not satisfy the editor contract."""


def _text(value: Any, *, limit: int, label: str) -> str:
    if not isinstance(value, str) or "\0" in value:
        raise EditorEventError(f"editor_{label}_invalid")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError:
        raise EditorEventError(f"editor_{label}_invalid") from None
    if size > limit:
        raise EditorEventError(f"editor_{label}_too_large")
    return value


def validate_editor_event(payload: Any, identity: str, *,
                          max_text_bytes: int = MAX_TEXT_BYTES) -> dict[str, Any]:
    """Validate/detach one message; no draft or session state is mutated.

    Only text, a monotonic sequence and an optional save *request* cross the
    iframe boundary. Neither paths, execution requests nor arbitrary commands
    are accepted. The caller's identity is authoritative.
    """
    expected = _text(identity, limit=4096, label="identity")
    if not expected:
        raise EditorEventError("editor_identity_invalid")
    if not isinstance(payload, Mapping) or set(payload) != {
            "identity", "text", "sequence", "command"}:
        raise EditorEventError("editor_payload_invalid")
    if payload["identity"] != expected:
        raise EditorEventError("editor_identity_mismatch")
    value = _text(payload["text"], limit=max_text_bytes, label="text")
    sequence = payload["sequence"]
    if type(sequence) is not int or not 1 <= sequence <= MAX_SEQUENCE:
        raise EditorEventError("editor_sequence_invalid")
    command = payload["command"]
    if command is not None and command != "save":
        raise EditorEventError("editor_command_invalid")
    return {"identity": expected, "text": value, "sequence": sequence, "command": command}


def validate_editor_diagnostics(diagnostics: Any) -> list[dict[str, Any]]:
    """Detach bounded, display-only source diagnostics; messages remain text."""
    if diagnostics is None:
        return []
    if (not isinstance(diagnostics, Sequence) or isinstance(diagnostics, (str, bytes))
            or len(diagnostics) > 200):
        raise EditorEventError("editor_diagnostics_invalid")
    result = []
    for item in diagnostics:
        if (not isinstance(item, Mapping) or not {"line", "severity", "message"} <= set(item)
                or set(item) - {"line", "column", "severity", "message"}):
            raise EditorEventError("editor_diagnostics_invalid")
        line, column = item["line"], item.get("column", 1)
        if (type(line) is not int or not 1 <= line <= MAX_TEXT_BYTES
                or type(column) is not int or not 1 <= column <= MAX_TEXT_BYTES
                or item["severity"] not in ("error", "warning")):
            raise EditorEventError("editor_diagnostics_invalid")
        message = _text(item["message"], limit=4000, label="diagnostic")
        result.append({"line": line, "column": column, "severity": item["severity"],
                       "message": message})
    return result


@lru_cache(maxsize=1)
def _declare_editor_component():
    # Lazy import: reading contracts does not require Streamlit or start a UI.
    import streamlit.components.v1 as components
    return components.declare_component("nsgablack_workspace_editor", path=str(_ASSETS))


def _state_key(key: str, identity: str) -> str:
    encoded = (str(key) + "\0" + identity).encode("utf-8")
    return "_workspace_editor_sequence::" + hashlib.sha256(encoded).hexdigest()


def acknowledge_editor_event(st, *, key: str, identity: str, sequence: int) -> int:
    """Advance the remount seed after the caller accepts a queued event.

    File navigation may consume an old iframe's pending event without rendering
    that editor again. After validating its workspace/revision/epoch/path, the
    caller acknowledges its sequence here so a later iframe cannot reuse it.
    This updates only the editor watermark, never text or a saved revision.
    """
    _text(key, limit=4096, label="key")
    _text(identity, limit=4096, label="identity")
    if not key or not identity:
        raise EditorEventError("editor_identity_invalid")
    if type(sequence) is not int or not 1 <= sequence <= MAX_SEQUENCE:
        raise EditorEventError("editor_sequence_invalid")
    slot = _state_key(key, identity)
    current = st.session_state.get(slot, 0)
    if type(current) is not int or not 0 <= current <= MAX_SEQUENCE:
        raise EditorEventError("editor_sequence_invalid")
    watermark = max(current, sequence)
    st.session_state[slot] = watermark
    return watermark


def render_code_editor(st, *, value: str, identity: str, height: int = 520,
                       language: str = "python", read_only: bool = False,
                       goto_line: int | None = None, diagnostics=None, key: str,
                       plaintext_fallback: bool = False, theme: str = "dark") -> dict[str, Any] | None:
    """Render the production editor; return a fresh validated event or ``None``.

    ``identity`` binds workspace/revision/editor epoch/path in the caller.
    The sequence seed survives iframe remounts and switching away/back. A save
    event includes the newest buffer, so callers must accept its text first.
    ``plaintext_fallback`` is explicit for backend/AppTest fixtures; it is never
    selected automatically on a production failure.
    """
    _text(value, limit=MAX_TEXT_BYTES, label="text")
    _text(identity, limit=4096, label="identity")
    if not identity or type(height) is not int or not 200 <= height <= 1200:
        raise EditorEventError("editor_arguments_invalid")
    if language not in ("python", "json", "markdown", "toml", "text"):
        raise EditorEventError("editor_language_invalid")
    if theme not in ("dark", "light", "system"):
        raise EditorEventError("editor_theme_invalid")
    if goto_line is not None and (type(goto_line) is not int or goto_line < 1):
        raise EditorEventError("editor_goto_invalid")
    markers = validate_editor_diagnostics(diagnostics)
    slot = _state_key(key, identity)
    last_sequence = st.session_state.get(slot, 0)
    if type(last_sequence) is not int or not 0 <= last_sequence < MAX_SEQUENCE:
        raise EditorEventError("editor_sequence_exhausted")
    if plaintext_fallback:
        current = st.text_area("文件内容", value=value, height=height, disabled=read_only,
                               key=str(key) + "::plain::" + slot.rsplit("::", 1)[-1])
        payload = (None if read_only or current == value else {
            "identity": identity, "text": current, "sequence": last_sequence + 1,
            "command": None})
    else:
        payload = _declare_editor_component()(
            value=value, identity=identity, height=height, language=language,
            read_only=bool(read_only), goto_line=goto_line, diagnostics=markers,
            sequence_base=last_sequence, max_text_bytes=MAX_TEXT_BYTES,
            theme=theme,
            key=key, default=None)
    if payload is None or read_only:
        return None
    try:
        event = validate_editor_event(payload, identity)
    except EditorEventError as exc:
        # Switching files can leave one old iframe event in Streamlit's queue.
        if str(exc) != "editor_identity_mismatch":
            st.warning("编辑器消息未通过校验，草稿未被修改。")
        return None
    if event["sequence"] <= last_sequence:
        return None
    acknowledge_editor_event(st, key=key, identity=identity, sequence=event["sequence"])
    return event
