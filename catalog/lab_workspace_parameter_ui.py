"""One explicit Case parameter draft, edited as a form or as JSON.

The draft belongs to a workspace/Case. Reading another source revision obtains
a fresh schema and revalidates the same overrides; it never silently supplies
defaults, drops unknown fields, or writes source files. Invalid JSON remains a
separate, visibly unapplied text draft. The runner still validates on submit.
"""
from __future__ import annotations

from copy import deepcopy
import json

from nsgablack.catalog.lab_workspace_parameters import (
    parameter_form_plan, parse_parameter_json, validate_parameter_overrides,
)


_PREFIX = "project_workspace::"
_MODES = ("按参数填写", "JSON")


def reopen_parameter_panel(st, workspace_id, case):
    """Mount fresh controls over the same canonical Case parameter draft."""
    state = st.session_state.get(_PREFIX + f"parameter_draft::{workspace_id}::{case}")
    if state is not None:
        state["epoch"] += 1


def _json(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)


def _button_action(st, trigger_key, action, *args):
    # A discarded control can be remounted with False instead of its previous
    # absent trigger. Only a real button press may change the canonical draft.
    if st.session_state.get(trigger_key) is True:
        action(st, *args)


def _reset(st, state_key):
    state = st.session_state[state_key]
    state.update(overrides={}, last_valid={}, json_text="{}", json_pending=False,
                 json_error=None, epoch=state["epoch"] + 1)


def _drop(st, state_key, name):
    state = st.session_state[state_key]
    state["overrides"].pop(name, None)
    state["epoch"] += 1


def _load_json(st, state_key):
    state = st.session_state[state_key]
    state.update(json_text=_json(state["overrides"]), json_pending=False,
                 json_error=None, epoch=state["epoch"] + 1)


def _toggle(st, state_key, name, key, field):
    state = st.session_state[state_key]
    if st.session_state[key]:
        if name not in state["overrides"]:
            default = field.get("default")
            state["overrides"][name] = (deepcopy(default) if field["default_valid"] else
                False if field["type"] == "bool" else "" if field["type"] == "str" and
                field.get("choices") is None else None)
    else:
        state["overrides"].pop(name, None)


def _capture(st, state_key, name, key):
    st.session_state[state_key]["overrides"][name] = st.session_state[key]


def _apply_json(state, schema, raw):
    state["json_text"] = raw
    try:
        value = validate_parameter_overrides(schema, parse_parameter_json(raw))
        state.update(overrides=deepcopy(value), last_valid=deepcopy(value),
                     json_pending=False, json_error=None)
        return value
    except (ValueError, TypeError) as exc:
        state.update(json_pending=True, json_error=str(exc))
        return None


def _capture_json(st, state_key, key, schema):
    # Capture a blurred textarea before another control switches editing mode.
    _apply_json(st.session_state[state_key], schema, st.session_state[key])


def _valid_field(schema, name, value):
    try:
        validate_parameter_overrides({"properties": {name: schema["properties"][name]}}, {name: value})
        return True
    except (ValueError, TypeError):
        return False


def _render_field(st, state, state_key, schema, field, scope):
    name, kind = field["name"], field["type"]
    base = _PREFIX + f"parameter::{scope}::{state['epoch']}::{name}"
    default = field.get("default")
    hint = str(field.get("description") or "")
    if field["has_default"]:
        hint += f" 原默认值：{default}。"
    if field.get("bounds_source") == "trial_resource_policy":
        hint += " 此范围属于快速试跑预算。"
    enabled = name in state["overrides"]
    override = st.checkbox(f"调整 {name}", value=enabled, key=base + "::override", help=hint,
        on_change=_toggle, args=(st, state_key, name, base + "::override", field))
    if not override:
        if field["has_default"]:
            st.caption(f"原值 {default}" + (f" · {field['description']}" if field.get("description") else ""))
        if field["requires_override"]:
            st.warning(f"{name} 的原默认值超出快速试跑范围；保留原模型，显式填写本次预算后才能试跑。")
        return
    value = state["overrides"].get(name)
    valid = _valid_field(schema, name, value)
    if not valid and value is not None:
        st.warning(f"{name} 的原覆盖值与当前声明不符：{_json(value)}。请重新填写或取消调整。")
    callback = {"on_change": _capture, "args": (st, state_key, name, base)}
    if field.get("choices") is not None:
        choices = field["choices"]
        index = next((index for index, choice in enumerate(choices)
                      if type(choice) is type(value) and choice == value), None)
        st.selectbox(name, choices, index=index, key=base, placeholder="选择本次取值", help=hint, **callback)
    elif kind == "bool":
        # Invalid prior values remain in the canonical draft until the user
        # explicitly changes the control; rendering False does not overwrite.
        st.checkbox(name, value=value if type(value) is bool else False,
                    key=base, help=hint, **callback)
    elif kind in {"int", "float"}:
        convert = int if kind == "int" else float
        minimum, maximum = field.get("minimum"), field.get("maximum")
        st.number_input(name, min_value=convert(minimum) if minimum is not None else None,
            max_value=convert(maximum) if maximum is not None else None,
            value=convert(value) if valid else None, step=1 if kind == "int" else .01,
            key=base, placeholder="填写本次取值", help=hint, **callback)
    else:
        st.text_input(name, value=value if isinstance(value, str) else "", key=base, help=hint, **callback)


def render_parameter_options(st, runtime, workspace, revision, case):
    """Return validated explicit overrides, or None while the chosen edit is invalid."""
    wid, rid = workspace["workspace_id"], revision["revision_id"]
    scope = f"{wid}::{case}"
    state_key = _PREFIX + f"parameter_draft::{scope}"
    state = st.session_state.setdefault(state_key, {
        "overrides": {}, "last_valid": {}, "json_text": "{}", "json_pending": False,
        "json_error": None, "mode": _MODES[0], "revision": rid, "epoch": 0,
    })
    schema_key = _PREFIX + f"schema_result::{wid}::{rid}::{case}"
    if schema_key not in st.session_state:
        try:
            st.session_state[schema_key] = runtime.runner.parameter_schema(wid, rid, case)
        except (ValueError, OSError) as exc:
            code = getattr(exc, "code", None)
            st.error(str(exc) + (f"（{code}）" if code else ""))
            if st.button("重新读取参数", key=_PREFIX + f"schema_retry::{wid}::{rid}::{case}"):
                st.rerun()
            return None
    schema = st.session_state[schema_key]
    plan = parameter_form_plan(schema)
    if state["revision"] != rid:
        state.update(revision=rid, epoch=state["epoch"] + 1)
    mode = st.radio("参数填写方式", _MODES, index=_MODES.index(state["mode"]), horizontal=True,
                    key=_PREFIX + f"parameter_mode::{scope}")
    if mode != state["mode"]:
        state.update(mode=mode, epoch=state["epoch"] + 1)
        if mode == "JSON" and not state["json_pending"]:
            state["json_text"] = _json(state["overrides"])
        elif mode == _MODES[0] and state["json_pending"]:
            try:
                state["overrides"] = validate_parameter_overrides(schema, state["last_valid"])
            except (ValueError, TypeError):
                # A new revision can invalidate even the old valid draft. Keep
                # it visible for repair instead of dropping fields or defaults.
                pass
    value = None
    if mode == "JSON":
        if state["json_pending"]:
            st.caption("保留了上次未应用的 JSON 草稿；当前参数不会被它覆盖。")
            load_key = _PREFIX + f"load_parameter_json::{scope}"
            st.button("载入当前参数到 JSON", key=load_key,
                      on_click=_button_action, args=(st, load_key, _load_json, state_key))
        json_key = _PREFIX + f"parameters::{scope}::{state['epoch']}"
        raw = st.text_area("Case 参数 JSON", value=state["json_text"], height=140,
            key=json_key, max_chars=65536,
            help="与表单共用显式覆盖；{} 沿用 Case 原值。无效输入会保留，但不会成为运行参数。",
            on_change=_capture_json, args=(st, state_key, json_key, schema))
        value = _apply_json(state, schema, raw)
        if state["json_pending"]:
            st.error(f"参数尚未有效：{state['json_error']}")
    else:
        if state["json_pending"]:
            st.warning("JSON 草稿尚未应用；当前表单继续使用上一次有效覆盖，未通过的原文仍保留。")
            with st.expander("未应用的 JSON 草稿", expanded=False):
                st.code(state["json_text"], language="json")
                discard_key = _PREFIX + f"discard_parameter_json::{scope}"
                st.button("放弃未应用的 JSON", key=discard_key,
                          on_click=_button_action, args=(st, discard_key, _load_json, state_key))
        if plan["empty"]:
            st.info("这个 Case 没有可调整的额外参数；直接使用当前代码。")
        field_names = {field["name"] for field in plan["fields"]}
        stale = [name for name in state["overrides"] if name not in field_names]
        for name in stale:
            st.warning(f"保留的覆盖 {name} 已不受当前声明支持；未自动删除。")
            st.code(_json({name: state["overrides"][name]}), language="json")
            drop_key = _PREFIX + f"drop_parameter::{scope}::{name}"
            st.button(f"撤销 {name} 覆盖", key=drop_key,
                      on_click=_button_action, args=(st, drop_key, _drop, state_key, name))
        for field in plan["fields"]:
            _render_field(st, state, state_key, schema, field, scope)
        if plan["unsupported"]:
            st.info("部分声明尚不支持网页试跑；可编辑正式 Project 代码，按原项目入口运行。")
        try:
            value = validate_parameter_overrides(schema, state["overrides"])
            state["last_valid"] = deepcopy(value)
        except (ValueError, TypeError) as exc:
            st.error(f"参数尚未有效：{exc}")
    reset_key = _PREFIX + f"reset_parameters::{scope}"
    st.button("恢复 Case 默认参数", key=reset_key,
              disabled=not state["overrides"] and not state["json_pending"],
              on_click=_button_action, args=(st, reset_key, _reset, state_key),
              help="撤销这个 Case 的显式覆盖，不改动工程源码。")
    with st.expander("参数声明与试跑范围", expanded=False):
        st.caption("只有勾选的参数才覆盖工程原值。切换表单、JSON 或代码版本会保留本 Case 的覆盖，按当前声明重新校验。")
        st.json(schema)
    return deepcopy(value)
