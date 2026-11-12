"""Parameters keep one Case draft while users change their way of editing."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from nsgablack.catalog import lab_workspace_parameter_ui as parameters


AppTest = pytest.importorskip("streamlit.testing.v1").AppTest


BASE = {
    "weight": {"type": "float", "default": .5, "minimum": 0., "maximum": 1.},
    "use_bias": {"type": "bool", "default": True},
    "count": {"type": "int", "default": 12, "minimum": 1, "maximum": 128},
    "method": {"type": "str", "default": "ga", "choices": ["ga", "vns"]},
}


class Runner:
    def __init__(self):
        self.schemas, self.calls = {}, []

    def parameter_schema(self, wid, rid, case):
        self.calls.append((wid, rid, case))
        return deepcopy(self.schemas.get((rid, case), {"properties": BASE, "parameter_mode": "declared"}))


@pytest.fixture
def harness(monkeypatch):
    runtime = SimpleNamespace(runner=Runner())
    monkeypatch.setattr(parameters, "_test_runtime", runtime, raising=False)
    app = AppTest.from_string("""import streamlit as st
from nsgablack.catalog import lab_workspace_parameter_ui as parameters
wid = st.selectbox('Workspace', ['a', 'b'])
rid = st.selectbox('Revision', ['r1', 'r2'])
case = st.selectbox('Case', ['first', 'second'])
value = parameters.render_parameter_options(st, parameters._test_runtime,
    {'workspace_id': wid}, {'revision_id': rid}, case)
st.session_state['effective'] = value
""", default_timeout=15).run()
    assert not app.exception
    return app, runtime


def widget(elements, label):
    return next(item for item in elements if item.label == label)


def ok(app):
    assert not app.exception, [item.message for item in app.exception]


def mode(app, value):
    widget(app.radio, "参数填写方式").set_value(value).run()
    ok(app)


def override(app, name, value):
    widget(app.checkbox, "调整 " + name).check().run()
    widget(app.number_input, name).set_value(value).run()
    ok(app)


def test_empty_form_does_not_inject_declared_defaults(harness):
    app, runtime = harness
    assert app.session_state["effective"] == {}
    assert runtime.runner.calls == [("a", "r1", "first")]
    assert not any(row.label == "Case 参数 JSON" for row in app.text_area)


def test_form_json_form_round_trip_keeps_overrides_and_false(harness):
    app, _ = harness
    override(app, "weight", .8)
    mode(app, "JSON")
    assert json.loads(widget(app.text_area, "Case 参数 JSON").value) == {"weight": .8}
    widget(app.text_area, "Case 参数 JSON").set_value('{"weight": 0.2, "use_bias": false, "method": "vns"}').run()
    ok(app)
    mode(app, "按参数填写")
    assert widget(app.checkbox, "调整 weight").value
    assert widget(app.number_input, "weight").value == .2
    assert widget(app.checkbox, "调整 use_bias").value
    assert not widget(app.checkbox, "use_bias").value
    assert widget(app.selectbox, "method").value == "vns"
    assert app.session_state["effective"] == {"weight": .2, "use_bias": False, "method": "vns"}


def test_code_revision_reloads_schema_but_retains_case_overrides(harness):
    app, runtime = harness
    override(app, "count", 30)
    widget(app.selectbox, "Revision").select("r2").run()
    ok(app)
    assert widget(app.checkbox, "调整 count").value
    assert widget(app.number_input, "count").value == 30
    assert app.session_state["effective"] == {"count": 30}
    assert runtime.runner.calls == [("a", "r1", "first"), ("a", "r2", "first")]
    widget(app.selectbox, "Revision").select("r1").run()
    assert len(runtime.runner.calls) == 2


def test_case_and_workspace_drafts_are_independent(harness):
    app, _ = harness
    override(app, "weight", .8)
    widget(app.selectbox, "Case").select("second").run()
    ok(app)
    assert app.session_state["effective"] == {}
    override(app, "weight", .3)
    widget(app.selectbox, "Workspace").select("b").run()
    assert app.session_state["effective"] == {}
    widget(app.selectbox, "Workspace").select("a").run()
    assert app.session_state["effective"] == {"weight": .3}
    widget(app.selectbox, "Case").select("first").run()
    assert app.session_state["effective"] == {"weight": .8}


def test_invalid_json_is_kept_when_user_returns_to_form(harness):
    app, _ = harness
    override(app, "weight", .8)
    mode(app, "JSON")
    widget(app.text_area, "Case 参数 JSON").set_value('{"weight":').run()
    ok(app)
    assert app.session_state["effective"] is None
    mode(app, "按参数填写")
    assert app.session_state["effective"] == {"weight": .8}
    assert any("JSON 草稿尚未应用" in row.value for row in app.warning)
    widget(app.number_input, "weight").set_value(.9).run()
    mode(app, "JSON")
    assert widget(app.text_area, "Case 参数 JSON").value == '{"weight":'
    assert app.session_state["effective"] is None
    widget(app.button, "载入当前参数到 JSON").click().run()
    ok(app)
    assert json.loads(widget(app.text_area, "Case 参数 JSON").value) == {"weight": .9}
    assert app.session_state["effective"] == {"weight": .9}


def test_removed_parameter_survives_revision_until_explicitly_revoked(harness):
    app, runtime = harness
    override(app, "weight", .8)
    runtime.runner.schemas["r2", "first"] = {"properties": {"count": BASE["count"]}}
    widget(app.selectbox, "Revision").select("r2").run()
    ok(app)
    assert app.session_state["effective"] is None
    assert app.session_state[parameters._PREFIX + "parameter_draft::a::first"]["overrides"] == {"weight": .8}
    assert any("未自动删除" in row.value for row in app.warning)
    widget(app.button, "撤销 weight 覆盖").click().run()
    ok(app)
    assert app.session_state["effective"] == {}


def test_changed_parameter_type_never_coerces_old_value(harness):
    app, runtime = harness
    override(app, "weight", .8)
    runtime.runner.schemas["r2", "first"] = {"properties": {"weight": {"type": "str", "default": "balanced"}}}
    widget(app.selectbox, "Revision").select("r2").run()
    ok(app)
    assert app.session_state["effective"] is None
    assert app.session_state[parameters._PREFIX + "parameter_draft::a::first"]["overrides"]["weight"] == .8
    widget(app.text_input, "weight").set_value("conservative").run()
    ok(app)
    assert app.session_state["effective"] == {"weight": "conservative"}


def test_reset_is_an_explicit_return_to_defaults_not_an_automatic_override(harness):
    app, _ = harness
    override(app, "count", 25)
    mode(app, "JSON")
    widget(app.text_area, "Case 参数 JSON").set_value('{"invented": 1}').run()
    assert app.session_state["effective"] is None
    widget(app.button, "恢复 Case 默认参数").click().run()
    ok(app)
    assert app.session_state["effective"] == {}
    assert widget(app.text_area, "Case 参数 JSON").value == "{}"
    mode(app, "按参数填写")
    assert not widget(app.checkbox, "调整 count").value


def test_json_edit_and_mode_switch_in_one_event_keeps_unapplied_text(harness):
    app, _ = harness
    override(app, "weight", .8)
    mode(app, "JSON")
    # Model the textarea losing focus immediately before changing mode.
    widget(app.text_area, "Case 参数 JSON").set_value('{"weight":')
    widget(app.radio, "参数填写方式").set_value("按参数填写").run()
    ok(app)
    assert app.session_state["effective"] == {"weight": .8}
    assert any("JSON 草稿尚未应用" in row.value for row in app.warning)
    mode(app, "JSON")
    assert widget(app.text_area, "Case 参数 JSON").value == '{"weight":'


def test_tighter_new_schema_does_not_clamp_the_existing_override(harness):
    app, runtime = harness
    override(app, "count", 100)
    runtime.runner.schemas["r2", "first"] = {"properties": {
        "count": {"type": "int", "default": 12, "minimum": 1, "maximum": 64}}}
    widget(app.selectbox, "Revision").select("r2").run()
    ok(app)
    assert app.session_state["effective"] is None
    assert app.session_state[parameters._PREFIX + "parameter_draft::a::first"]["overrides"]["count"] == 100
    assert widget(app.number_input, "count").value is None
    widget(app.checkbox, "调整 count").uncheck().run()
    assert app.session_state["effective"] == {}


def test_reset_current_case_preserves_another_case_draft(harness):
    app, _ = harness
    override(app, "weight", .8)
    widget(app.selectbox, "Case").select("second").run()
    override(app, "count", 32)
    widget(app.button, "恢复 Case 默认参数").click().run()
    assert app.session_state["effective"] == {}
    widget(app.selectbox, "Case").select("first").run()
    assert app.session_state["effective"] == {"weight": .8}


@pytest.mark.parametrize("text", ['{"weight": NaN}', '{"weight": 1e999}',
                                  '{"weight": 0.2, "weight": 0.3}', '[]'])
def test_invalid_advanced_input_does_not_replace_the_effective_form_draft(harness, text):
    app, _ = harness
    override(app, "weight", .7)
    mode(app, "JSON")
    widget(app.text_area, "Case 参数 JSON").set_value(text).run()
    ok(app)
    assert app.session_state["effective"] is None
    mode(app, "按参数填写")
    assert app.session_state["effective"] == {"weight": .7}
    mode(app, "JSON")
    assert widget(app.text_area, "Case 参数 JSON").value == text
