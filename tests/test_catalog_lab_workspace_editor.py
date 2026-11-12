"""Editor boundary tests use text fixtures; no Project or model is executed."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from nsgablack.catalog import lab_workspace_editor as editor


def event(*, identity="workspace/revision/epoch/file.py", text="x = 1\n", sequence=1,
          command=None):
    return {"identity": identity, "text": text, "sequence": sequence, "command": command}


class FakeStreamlit:
    def __init__(self):
        self.session_state = {}
        self.warnings = []
        self.plain_value = None
        self.plain_args = None

    def warning(self, message):
        self.warnings.append(message)

    def text_area(self, label, **kwargs):
        self.plain_args = (label, kwargs)
        return kwargs["value"] if self.plain_value is None else self.plain_value


def mount(monkeypatch, payload):
    calls = []

    def component(**kwargs):
        calls.append(kwargs)
        return payload[0]

    monkeypatch.setattr(editor, "_declare_editor_component", lambda: component)
    return calls


def render(st, **kwargs):
    return editor.render_code_editor(st, value=kwargs.pop("value", "x = 1\n"),
        identity=kwargs.pop("identity", "workspace/revision/epoch/file.py"),
        key=kwargs.pop("key", "editor"), **kwargs)


def test_valid_event_is_detached_and_save_carries_latest_text():
    payload = event(text="latest = 2\n", command="save", sequence=8)
    result = editor.validate_editor_event(payload, payload["identity"])
    assert result == payload and result is not payload
    payload["text"] = "changed after validation"
    assert result["text"] == "latest = 2\n"


@pytest.mark.parametrize("patch", [
    {"identity": "other/file.py"}, {"identity": None}, {"text": None}, {"text": b"bytes"},
    {"text": "bad\0text"}, {"text": "\ud800"}, {"sequence": 0}, {"sequence": -1},
    {"sequence": True}, {"sequence": 1.0}, {"sequence": 2**53}, {"command": "run"},
    {"command": {"save": True}}, {"unknown": "field"},
])
def test_rejects_malformed_or_wrong_identity_event(patch):
    payload = event()
    payload.update(patch)
    with pytest.raises(editor.EditorEventError):
        editor.validate_editor_event(payload, event()["identity"])


@pytest.mark.parametrize("payload", [None, [], "text", {}, {"text": "x"}])
def test_rejects_non_event_payloads(payload):
    with pytest.raises(editor.EditorEventError):
        editor.validate_editor_event(payload, event()["identity"])


def test_text_limit_is_utf8_bytes_and_includes_boundary():
    payload = event(text="界" * 4)
    assert editor.validate_editor_event(payload, payload["identity"], max_text_bytes=12)
    with pytest.raises(editor.EditorEventError, match="editor_text_too_large"):
        editor.validate_editor_event(payload, payload["identity"], max_text_bytes=11)


def test_duplicate_and_stale_saves_are_consumed_once_and_seed_remount(monkeypatch):
    st, payload = FakeStreamlit(), [event(sequence=5, command="save", text="newest")]
    calls = mount(monkeypatch, payload)
    assert render(st)["text"] == "newest"
    assert calls[-1]["sequence_base"] == 0
    assert render(st) is None
    assert calls[-1]["sequence_base"] == 5
    payload[0] = event(sequence=4, text="stale", command="save")
    assert render(st) is None
    # A new iframe receives this seed and emits a sequence above it.
    payload[0] = event(sequence=calls[-1]["sequence_base"] + 1, text="remounted")
    assert render(st)["text"] == "remounted"
    assert calls[-1]["sequence_base"] == 5


def test_sequence_scope_keeps_file_identity_and_component_key_separate(monkeypatch):
    st, payload = FakeStreamlit(), [event(sequence=4)]
    calls = mount(monkeypatch, payload)
    render(st)
    other = "workspace/revision/epoch/other.py"
    payload[0] = event(identity=other)
    assert render(st, identity=other)["sequence"] == 1
    assert calls[-1]["sequence_base"] == 0
    payload[0] = event(sequence=5)
    assert render(st)["sequence"] == 5
    assert calls[-1]["sequence_base"] == 4
    payload[0] = event()
    assert render(st, key="another-editor")["sequence"] == 1
    assert calls[-1]["sequence_base"] == 0


def test_acknowledged_pending_event_seeds_remounted_editor(monkeypatch):
    st, payload = FakeStreamlit(), [None]
    calls = mount(monkeypatch, payload)
    identity = event()["identity"]
    assert editor.acknowledge_editor_event(st, key="editor", identity=identity, sequence=7) == 7
    assert render(st) is None
    assert calls[-1]["sequence_base"] == 7
    payload[0] = event(sequence=8, text="new edit after file switch")
    assert render(st)["text"] == "new edit after file switch"
    assert editor.acknowledge_editor_event(st, key="editor", identity=identity, sequence=8) == 8


def test_acknowledgement_never_regresses_and_rejects_invalid_parameters(monkeypatch):
    st = FakeStreamlit()
    calls = mount(monkeypatch, [None])
    options = {"key": "editor", "identity": event()["identity"], "sequence": 9}
    assert editor.acknowledge_editor_event(st, **options) == 9
    assert editor.acknowledge_editor_event(st, **{**options, "sequence": 3}) == 9
    assert editor.acknowledge_editor_event(st, **options) == 9
    render(st)
    assert calls[-1]["sequence_base"] == 9
    before = st.session_state.copy()
    for patch in ({"key": ""}, {"key": None}, {"identity": ""}, {"identity": "bad\0id"},
                  {"sequence": True}, {"sequence": 0}, {"sequence": -1}, {"sequence": 2**53}):
        with pytest.raises(editor.EditorEventError):
            editor.acknowledge_editor_event(st, **{**options, **patch})
        assert st.session_state == before


def test_wrong_file_and_read_only_events_cannot_mutate_draft_or_sequence(monkeypatch):
    st, payload = FakeStreamlit(), [event(identity="old/file.py", command="save")]
    mount(monkeypatch, payload)
    assert render(st) is None
    assert not st.session_state and not st.warnings
    payload[0] = event(text="untrusted", command="save")
    assert render(st, read_only=True) is None
    assert not st.session_state
    payload[0]["command"] = "execute"
    assert render(st) is None
    assert not st.session_state and len(st.warnings) == 1
    assert "untrusted" not in st.warnings[0]


def test_none_is_normal_before_component_mount(monkeypatch):
    st = FakeStreamlit()
    mount(monkeypatch, [None])
    assert render(st) is None and not st.warnings


def test_goto_clear_and_diagnostics_are_forwarded_as_bounded_data(monkeypatch):
    st = FakeStreamlit()
    calls = mount(monkeypatch, [None])
    markers = [{"line": 2, "column": 3, "severity": "error", "message": "missing ':'"}]
    render(st, goto_line=2, diagnostics=markers)
    assert calls[-1]["goto_line"] == 2
    assert calls[-1]["diagnostics"] == markers
    assert calls[-1]["diagnostics"] is not markers
    render(st, goto_line=None)
    assert calls[-1]["goto_line"] is None
    render(st, goto_line=2)
    assert calls[-1]["goto_line"] == 2


@pytest.mark.parametrize("markers", [
    "bad", {}, [{"line": 0, "severity": "error", "message": "x"}],
    [{"line": True, "severity": "error", "message": "x"}],
    [{"line": 1, "column": 0, "severity": "error", "message": "x"}],
    [{"line": 1, "severity": "fatal", "message": "x"}],
    [{"line": 1, "severity": "error", "message": "x", "action": "run"}],
    [{"line": 1, "severity": "error", "message": "x" * 4001}],
    [{"line": 1, "severity": "error", "message": "x"}] * 201,
])
def test_rejects_unbounded_or_actionable_diagnostics(markers):
    with pytest.raises(editor.EditorEventError):
        editor.validate_editor_diagnostics(markers)


def test_plaintext_fallback_is_explicit_and_uses_same_event_contract(monkeypatch):
    st = FakeStreamlit()
    monkeypatch.setattr(editor, "_declare_editor_component",
                        lambda: pytest.fail("fallback must not instantiate JS component"))
    assert render(st, plaintext_fallback=True) is None
    st.plain_value = "changed = 1\n"
    result = render(st, plaintext_fallback=True)
    assert result == event(text="changed = 1\n")
    assert st.plain_args[0] == "文件内容"
    assert render(st, plaintext_fallback=True, value=result["text"]) is None


@pytest.mark.parametrize("theme", ["dark", "light", "system"])
def test_theme_is_presentation_only_and_keeps_sequence_scope(monkeypatch, theme):
    st, payload = FakeStreamlit(), [event(sequence=5, text="latest text")]
    calls = mount(monkeypatch, payload)
    assert render(st)["sequence"] == 5
    before = st.session_state.copy()
    payload[0] = None
    assert render(st, theme=theme) is None
    assert calls[-1]["theme"] == theme
    assert calls[-1]["sequence_base"] == 5
    assert calls[-1]["identity"] == event()["identity"]
    assert st.session_state == before


@pytest.mark.parametrize("kwargs", [
    {"identity": ""}, {"identity": "x" * 4097}, {"height": 100}, {"height": True},
    {"height": 1201}, {"goto_line": False}, {"goto_line": 0}, {"language": "javascript"},
    {"theme": "no-such-theme"}, {"theme": None}, {"theme": []},
])
def test_invalid_host_arguments_fail_before_component(monkeypatch, kwargs):
    monkeypatch.setattr(editor, "_declare_editor_component",
                        lambda: pytest.fail("invalid props must not mount component"))
    with pytest.raises(editor.EditorEventError):
        render(FakeStreamlit(), **kwargs)


def test_vendored_runtime_is_small_offline_and_matches_pinned_manifest():
    assets = Path(editor.__file__).with_name("workspace_editor_frontend")
    html = (assets / "index.html").read_text(encoding="utf-8")
    js = (assets / "editor.js").read_text(encoding="utf-8")
    bundle = (assets / "editor.bundle.js").read_bytes()
    manifest = json.loads((assets / "build-manifest.json").read_text(encoding="utf-8"))
    assert manifest["sha256"] == hashlib.sha256(bundle).hexdigest()
    assert manifest["bytes"] == len(bundle) < 500 * 1024
    assert manifest["presentation"] == {"themes": ["dark", "light", "system"], "default": "dark"}
    for name, expected in manifest["assets"].items():
        content = (assets / name).read_bytes()
        assert expected == {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
    assert 'src="editor.bundle.js"' in html and 'href="editor.css"' in html
    assert "connect-src 'none'" in html and "script-src 'self'" in html
    assert "https://" not in html and "http://" not in html
    assert "event.source !== window.parent" in js
    assert "sequence = args.sequence_base" in js
    assert "lastGoto = null" in js
    assert "fetch(" not in js and "eval(" not in js and "localStorage" not in js
    licenses = (assets / "THIRD_PARTY_LICENSES.txt").read_text(encoding="utf-8")
    for package, version in manifest["packages"].items():
        assert f"{package}@{version}" in licenses
    package = json.loads((assets / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((assets / "package-lock.json").read_text(encoding="utf-8"))
    assert package["dependencies"] == lock["packages"][""]["dependencies"]
    assert all(version[0].isdigit() for version in package["dependencies"].values())


def test_plaintext_fixture_runs_with_streamlit_without_a_custom_component():
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    app = AppTest.from_string('''
import streamlit as st
from nsgablack.catalog.lab_workspace_editor import render_code_editor
value = st.session_state.get("draft", "x = 1\\n")
event = render_code_editor(st, value=value, identity="fixture/revision/epoch/file.py",
    key="fixture", plaintext_fallback=True)
if event:
    st.session_state["draft"] = event["text"]
    st.session_state["last_sequence"] = event["sequence"]
''', default_timeout=15).run()
    assert not app.exception
    app.text_area[0].set_value("x = 2\n").run()
    assert not app.exception
    assert app.session_state["draft"] == "x = 2\n"
    assert app.session_state["last_sequence"] == 1
    app.run()
    assert app.session_state["last_sequence"] == 1
