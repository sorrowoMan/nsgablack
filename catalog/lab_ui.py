"""A small assembly workbench backed by standard Project sources and trial jobs.

Rendering and exporting never construct a Solver or Unit. One editable assembly
is shared by manual controls, AI proposals, exports and bounded trial jobs.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from html import escape
import json
import time
from typing import Any
from urllib.parse import urlencode
from uuid import uuid4

from .ui_theme import WORKSPACE_CSS, WORKSPACE_FOOTER


_PREFIX = "catalog_lab::"
_JOB_KEY = _PREFIX + "job"
_INTENT_KEY = _PREFIX + "submission"
_DRAFT_KEY = _PREFIX + "draft"
_REVISION_KEY = _PREFIX + "draft_revision"
_AI_JOB_KEY = _PREFIX + "assistant_job"
_AI_INTENT_KEY = _PREFIX + "assistant_submission"
_PROBLEM_BUFFER_KEY = _PREFIX + "problem_buffer"
_AI_CAPS_KEY = _PREFIX + "assistant_capabilities"
_NOTES_KEY = _PREFIX + "design_notes"
_HISTORY_KEY = _PREFIX + "assistant_history"
_AI_CAPS_TTL = 15.
_ACTIVE = frozenset({"queued", "running"})
_STYLES = """
<style>
.lab-heading {display:flex;justify-content:space-between;gap:1rem;}
.lab-note {border-left:3px solid;border-radius:0 7px 7px 0;padding:.7rem .9rem;line-height:1.7;margin:.75rem 0;}
.lab-problem-line {overflow-wrap:anywhere;}
.lab-steps {color:var(--catalog-muted);font-size:.84rem;margin:.3rem 0 1.1rem;}
.st-key-catalog_lab_workspace {min-width:0;}
.lab-heading {margin:0 0 1.4rem;align-items:flex-start;}
.lab-badge {color:#5d6476;background:#fff;border:1px solid #e1e5ed;font-size:.75rem;border-radius:8px;padding:.45rem .7rem;}
.lab-section {font-size:.92rem;letter-spacing:0;color:#26334b;font-weight:650;margin:.2rem 0 .6rem;}
.lab-description {color:var(--catalog-muted);font-size:.86rem;}
.st-key-catalog_lab_workspace {max-width:none;}
.st-key-catalog_lab_workspace [data-testid="stVerticalBlock"] {gap:.8rem;}
.st-key-catalog_lab_topbar [data-testid="stHorizontalBlock"] {align-items:flex-start;}
.st-key-catalog_lab_tools {display:flex;justify-content:flex-end;padding-top:.45rem;}
.st-key-catalog_lab_workspace [data-testid="stTabs"] > [data-baseweb="tab-list"] {gap:1.6rem;border-bottom:1px solid #dde2ec;background:transparent;padding:0;margin-bottom:1.4rem;}
.st-key-catalog_lab_workspace [data-baseweb="tab"] {min-height:50px;padding:0 .2rem;background:transparent;border-radius:0;}
.st-key-catalog_lab_workspace [data-baseweb="tab"] p {font-size:.88rem;font-weight:550;color:#65718a!important;}
.st-key-catalog_lab_workspace [data-baseweb="tab"][aria-selected="true"] p {color:#4338ca!important;font-weight:700;}
.st-key-catalog_lab_workspace [data-baseweb="tab-highlight"] {background:var(--catalog-accent);height:3px;}
.st-key-catalog_lab_workspace [data-baseweb="tab-border"] {background:transparent;}
.st-key-catalog_lab_conversation,.st-key-catalog_lab_definition,.st-key-catalog_lab_instances,.st-key-catalog_lab_plan {background:#fff;border:1px solid var(--catalog-line);border-radius:16px;padding:1.4rem;box-shadow:var(--workspace-shadow);min-width:0;}
.lab-panel-heading {display:flex;align-items:center;gap:.75rem;margin:0 0 .45rem;}
.lab-panel-icon {display:flex;align-items:center;justify-content:center;width:38px;height:38px;background:#efedff;color:#5b45d9;border-radius:11px;font-size:1.1rem;font-weight:650;flex-shrink:0;}
.lab-panel-heading h2 {color:#202c43!important;font-size:1.08rem!important;letter-spacing:-.02em!important;padding:0!important;margin:0!important;line-height:1.5;}
.lab-panel-copy {color:var(--catalog-muted);font-size:.85rem;line-height:1.8;margin:.3rem 0 1.1rem;}
.lab-status {display:flex;gap:.45rem;align-items:center;flex-wrap:wrap;margin:0 0 .6rem;color:var(--catalog-muted);font-size:.76rem;}
.lab-status-dot {width:6px;height:6px;background:#30a47b;border-radius:50%;display:inline-block;}
.lab-status-dot.offline {background:#94a3b8;}
.lab-status-divider {color:#cbd1dd;margin:0 .25rem;}
.lab-helper {font-size:.78rem;color:var(--catalog-muted);line-height:1.8;margin:.3rem 0;}
.lab-hint-label {color:#7b8497;font-size:.73rem;margin:.8rem 0 .1rem;}
.lab-problem {border:0;background:#f7f8fc;border-radius:11px;padding:1rem 1.1rem;margin:.15rem 0 .8rem;}
.lab-problem-title {font-size:.87rem;color:#36445f;font-weight:650;margin:0 0 .7rem;}
.lab-problem-line {color:#495971;font-size:.83rem;line-height:1.95;}
.lab-problem-type {display:inline-block;font-size:.7rem;color:#6b7390;background:#fff;border:1px solid #e3e7f0;border-radius:5px;padding:.1rem .4rem;margin:0 0 .7rem;}
.lab-note {color:#56617a;background:#f0f1fc;border-color:#a69bea;font-size:.81rem;}
.lab-run-empty {border:1px dashed #d3d9e7;background:#fff;border-radius:14px;padding:2rem;color:var(--catalog-muted);font-size:.88rem;}
.st-key-catalog_lab_workspace [data-testid="stAlert"] [data-baseweb="notification"] {border-radius:10px;background:#f4f5fc!important;border-color:#e2e5f1;}
.st-key-catalog_lab_workspace [data-testid="stAlert"] [data-testid="stMarkdownContainer"] * {color:#465575!important;}
.st-key-catalog_lab_prompts [data-testid="stButton"] button {min-height:32px!important;padding:.25rem .6rem;background:#f9faff!important;border-color:#e5e7f0!important;}
.st-key-catalog_lab_prompts [data-testid="stButton"] button p {font-size:.73rem;}
.st-key-catalog_lab_connection [data-testid="stButton"] button {font-size:.74rem;min-height:30px;}
.st-key-catalog_lab_tools [data-testid="stPopover"] {width:100%;}
.st-key-catalog_lab_tools [data-testid="stPopover"] button {background:#fff;color:#475569;border:1px solid #dde2ec;border-radius:8px;min-height:38px;}
@media(max-width:1050px){.st-key-catalog_lab_conversation,.st-key-catalog_lab_definition{padding:1.1rem}}
@media(max-width:760px){.st-key-catalog_lab_problem_columns>[data-testid="stHorizontalBlock"]{flex-wrap:wrap}.st-key-catalog_lab_problem_columns>[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{width:100%!important;flex:1 1 100%!important;min-width:0!important}.lab-heading{margin-bottom:.75rem}.st-key-catalog_lab_workspace [data-testid="stTabs"]>[data-baseweb="tab-list"]{gap:.9rem}}
</style>
""" + WORKSPACE_CSS


def catalog_component_url(query_params: Mapping[str, Any], entry_key: str) -> str:
    """Build a Catalog link without dropping the user's existing URL state."""
    pairs: list[tuple[str, str]] = []
    for name in query_params:
        if name in {"view", "kind", "selected", "nav_action"}:
            continue
        values = (query_params.get_all(name) if hasattr(query_params, "get_all")
                  else query_params[name])
        if not isinstance(values, (tuple, list)):
            values = [values]
        pairs.extend((str(name), str(value)) for value in values)
    pairs.extend((("view", "catalog"), ("kind", "all"),
                  ("selected", entry_key), ("nav_action", "locate_selected")))
    return "?" + urlencode(pairs)


def _section(st: Any, title: str) -> None:
    st.markdown(f"<div class='lab-section'>{escape(title)}</div>", unsafe_allow_html=True)


def _replace_draft(st: Any, value: Mapping[str, Any]) -> None:
    """Only explicit load/apply actions replace the editable document."""
    from .lab_assembly import normalize_assembly

    st.session_state[_DRAFT_KEY] = normalize_assembly(value)
    st.session_state[_REVISION_KEY] = int(st.session_state.get(_REVISION_KEY, 0)) + 1


def _key(st: Any, name: str) -> str:
    return _PREFIX + f"edit::{st.session_state.get(_REVISION_KEY, 0)}::{name}"


def _parameter(st: Any, rule: Mapping[str, Any], value: Any, *, name: str, label: str | None = None) -> Any:
    label = str(label or rule.get("label") or name)
    key = _key(st, name)
    kind = str(rule.get("type", "float"))
    choices = rule.get("choices")
    if choices:
        options = list(choices)
        if value not in options:
            value = rule.get("default", options[0])
        return st.selectbox(label, options, index=options.index(value), key=key)
    if kind in {"bool", "boolean"}:
        return st.checkbox(label, value=bool(value), key=key)
    if kind in {"str", "string"}:
        return st.text_input(label, value=str(value), key=key)
    numeric = int if kind in {"int", "integer"} else float
    kwargs = {"value": numeric(value), "step": 1 if numeric is int else .01, "key": key}
    if rule.get("min") is not None:
        kwargs["min_value"] = numeric(rule["min"])
    if rule.get("max") is not None:
        kwargs["max_value"] = numeric(rule["max"])
    return st.number_input(label, **kwargs)


def _parameters(st: Any, component: Mapping[str, Any], values: Mapping[str, Any], *, prefix: str) -> dict:
    defaults = component.get("defaults", {})
    result = {}
    for name, rule in component.get("parameters", {}).items():
        value = values.get(name, defaults.get(name, rule.get("default")))
        result[name] = _parameter(st, rule, value, name=f"{prefix}::{name}")
    return result


def _component_link(st: Any, component: Mapping[str, Any]) -> None:
    key = component.get("catalog_key")
    if key:
        st.link_button("查看 Catalog · " + str(key), catalog_component_url(st.query_params, str(key)))
    elif component.get("source") == "framework":
        st.caption("框架组件 · " + str(component.get("constructor", component["key"]))
                   + "；当前没有独立 Catalog 条目，完整装配见项目源码。")
    else:
        st.caption("实验台演示实现；源码包含在导出的 Project 中。")


def _component_picker(st: Any, label: str, available: list, current: Mapping[str, Any] | None,
                      *, name: str, optional: bool = False, compact: bool = False) -> dict | None:
    by_key = {item["key"]: item for item in available}
    options = ([None] if optional else []) + list(by_key)
    if not options:
        st.caption(label + "：当前没有可装配组件。")
        return None
    selected = current.get("component") if current else options[0]
    if selected not in options:
        selected = options[0]
    chosen = st.selectbox(label, options, index=options.index(selected), key=_key(st, name + "::component"),
                          format_func=lambda key: "不启用" if key is None else str(by_key[key]["label"]))
    if chosen is None:
        return None
    metadata = by_key[chosen]
    values = current.get("parameters", {}) if current and current.get("component") == chosen else {}
    # Include component identity: replacing an algorithm must not reuse widgets
    # carrying parameters from the previous component.
    if compact:
        with st.expander("参数与组件说明", expanded=False):
            parameters = _parameters(st, metadata, values, prefix=f"{name}::{chosen}")
            _component_link(st, metadata)
    else:
        parameters = _parameters(st, metadata, values, prefix=f"{name}::{chosen}")
        _component_link(st, metadata)
    return {"component": chosen, "parameters": parameters}


def _prune_plan(plan: Mapping[str, Any], node_id: str) -> dict | None:
    kind = plan.get("kind")
    if kind == "stage":
        return None if plan.get("node") == node_id else deepcopy(dict(plan))
    if kind == "repeat":
        body = _prune_plan(plan["body"], node_id)
        return {**plan, "body": body} if body else None
    children = [value for child in plan.get("children", []) if (value := _prune_plan(child, node_id))]
    if not children:
        return None
    return {**plan, "children": children} if len(children) > 1 else children[0]


def _stage_for(node: Mapping[str, Any]) -> dict:
    refine = (node.get("input") or {}).get("mode") == "refine"
    return {"kind": "stage", "node": node["id"], "label": "step_" + uuid4().hex[:8],
            "action": "search", "steps": None if refine else 2}


def _edit_pool_input(st: Any, node: dict, all_nodes: list[dict], metadata: Mapping[str, Any]) -> None:
    node_id = node["id"]
    value = deepcopy(node.get("input") or {})
    modes = [mode for mode in metadata.get("pool_modes", ["initialize"]) if mode in {"initialize", "refine"}]
    default = value.get("mode", modes[0])
    if default not in modes:
        default = modes[0]
    mode = st.selectbox("如何使用池中的解", modes, index=modes.index(default),
                        key=_key(st, f"node::{node_id}::pool_mode"),
                        format_func=lambda v: {"initialize": "初始化 Unit，然后继续搜索", "refine": "逐个精修本次选中的起点"}.get(v, v))
    value["mode"] = mode
    source = value.get("source", "main")
    creators = [item["id"] for item in all_nodes if item["id"] != node_id]
    sources = ["main", *creators] if mode == "refine" else ["main"]
    selected = source.get("adapter") if isinstance(source, Mapping) else "main"
    if selected not in sources:
        # Keep the unresolved reference visible rather than silently rebinding it.
        sources.append(selected)
    selected = st.selectbox("输入来自哪个池", sources, index=sources.index(selected),
                           key=_key(st, f"node::{node_id}::pool_source"),
                           format_func=lambda v: "母池 main" if v == "main" else f"{v} 创建的已提交视图")
    if selected == "main":
        value["source"] = "main"
    else:
        old = source if isinstance(source, Mapping) else {}
        views = st.selectbox("选择这些来源的哪些视图", ["all", "random"],
                             index=1 if old.get("views") == "random" else 0,
                             key=_key(st, f"node::{node_id}::views"),
                             format_func=lambda v: "全部视图" if v == "all" else "随机选若干视图")
        value["source"] = {"adapter": selected, "views": views}
        if views == "random":
            value["source"]["view_count"] = st.number_input("随机选择的视图数", 1, 24,
                value=int(old.get("view_count", 2)), step=1, key=_key(st, f"node::{node_id}::view_count"))
        st.caption("来源按 Adapter 实例区分；视图会在任务开始时冻结。方向投影保留自己的比较规则。")
    if mode == "initialize":
        value["count"] = node.get("parameters", {}).get("population_size", 1)
        st.caption(f"初始化时从母池取 {value['count']} 个精确成员，匹配此 Unit 的容量。")
    else:
        count = value.get("count", "all")
        count_mode = st.selectbox("每个输入区域取多少解", ["number", "all"], index=1 if count == "all" else 0,
                                 key=_key(st, f"node::{node_id}::count_mode"),
                                 format_func=lambda v: "指定数量" if v == "number" else "全部成员（显式 count=all）")
        value["count"] = ("all" if count_mode == "all" else st.number_input("每个输入区域的解数", 1, 64,
            value=int(count if count != "all" else 1), step=1, key=_key(st, f"node::{node_id}::count")))
    if mode == "refine":
        value["steps"] = st.number_input("每个起点的精修步数（含起点评估）", 1, 8,
            value=int(value.get("steps", 2)), step=1, key=_key(st, f"node::{node_id}::local_steps"))
    value["shuffle"] = st.checkbox("在任务开始时打乱输入", value=bool(value.get("shuffle", False)),
                                   key=_key(st, f"node::{node_id}::shuffle"))
    node["input"] = value
    outputs = [None, *creators]
    output = node.get("return_from")
    if output not in outputs:
        outputs.append(output)
    node["return_from"] = st.selectbox("返回竞争的结果来自", outputs, index=outputs.index(output),
                                      key=_key(st, f"node::{node_id}::return_from"),
                                      format_func=lambda v: "不接收其它实例的返回" if v is None else f"{v} 的本轮最终选择")
    if node["return_from"]:
        st.caption("在计划中为此实例增加“返回竞争”步骤。接收算法重评并决定是否留下结果。")


def _edit_nodes(st: Any, draft: dict, metadata: Mapping[str, Any]) -> None:
    _section(st, "算法实例 · 点击实例调整")
    available = list(metadata["components"]["adapters"])
    by_key = {item["key"]: item for item in available}
    nodes = draft["nodes"]
    for node in nodes:
        node_id = node["id"]
        with st.expander(f"{node_id} · {by_key.get(node['component'], {}).get('label', node['component'])}", expanded=len(nodes) == 1):
            selected = _component_picker(st, "算法组件", available,
                {"component": node["component"], "parameters": node.get("parameters", {})}, name=f"node::{node_id}", compact=True)
            old_component = node["component"]
            node.update(selected or {})
            component = by_key[node["component"]]
            if old_component != node["component"]:
                node["change"] = "native"
                previous_input = deepcopy(node.get("input") or {})
                previous_mode = previous_input.get("mode", "initialize")
                if previous_mode in component.get("pool_modes", ()):
                    # Pool wiring belongs to the instance's task, not to its
                    # algorithm type. VNS -> SA retains the exact selected
                    # views, per-view count, local budget and frozen-input rule.
                    node["input"] = previous_input
                    if previous_mode == "initialize":
                        node["input"]["count"] = node.get("parameters", {}).get("population_size", 1)
                else:
                    node["input"] = {"mode": "initialize", "source": "main",
                        "count": node.get("parameters", {}).get("population_size", 1),
                        "steps": previous_input.get("steps", 2),
                        "shuffle": previous_input.get("shuffle", False)}
                    st.session_state[_PREFIX + "edit_notice"] = (
                        f"{node_id} 的新算法不支持 {previous_mode} 池任务，已改为从母池初始化。"
                        "请检查依赖此实例的视图来源与返回竞争步骤。")
                if node.get("return_from") and "compete" not in component.get("pool_modes", ()):
                    node["return_from"] = None
                    st.session_state[_PREFIX + "edit_notice"] = (
                        f"{node_id} 的新算法不支持接收返回竞争，已解除它的返回来源绑定。"
                        "请在计划中调整原有的返回竞争步骤。")
                st.session_state[_DRAFT_KEY] = draft
                st.session_state[_REVISION_KEY] = int(st.session_state.get(_REVISION_KEY, 0)) + 1
                st.rerun()
            changes = list(component.get("changes") or ["native"])
            current = node.get("change", "native")
            if current not in changes:
                current = changes[0]
            labels = {"native": "算法原生变化", "ga_mask": "掩码交叉 → 高斯变异", "ga_blend": "混合交叉 → 高斯变异",
                      "gaussian": "高斯邻域变化", "moead_blend": "方向父代重组 → 高斯变异"}
            node["change"] = st.selectbox("变化方法", changes, index=changes.index(current),
                key=_key(st, f"node::{node_id}::{node['component']}::change"), format_func=lambda v: labels.get(v, v))
            if node["change"] != "native":
                st.caption("此变化函数直接生成提案，不再追加 Pipeline 的变异；统一问题修复和真实评估仍由控制面执行。")
            with st.expander("池输入与结果交还", expanded=False):
                st.caption(f"实例 {node_id} · Unit：" + str(component.get("unit", "由算法按需建立")))
                _edit_pool_input(st, node, nodes, component)
            if st.button("删除实例 " + node_id, key=_key(st, f"remove::{node_id}"), disabled=len(nodes) <= 1):
                draft["nodes"] = [item for item in nodes if item["id"] != node_id]
                draft["plan"] = _prune_plan(draft["plan"], node_id) or _stage_for(draft["nodes"][0])
                # Dependent references are intentionally retained and diagnosed.
                st.session_state[_DRAFT_KEY] = draft
                st.session_state[_REVISION_KEY] = int(st.session_state.get(_REVISION_KEY, 0)) + 1
                st.rerun()
    with st.container(border=True):
        new_component = st.selectbox("添加一种算法", list(by_key), format_func=lambda v: str(by_key[v]["label"]),
                                     key=_key(st, "add_component"))
        if st.button("添加算法实例", key=_key(st, "add_node")):
            component = by_key[new_component]
            base = new_component.rsplit(".", 1)[-1]
            used = {item["id"] for item in nodes}
            node_id, i = base, 2
            while node_id in used:
                node_id, i = f"{base}_{i}", i + 1
            parameters = deepcopy(component.get("defaults", {}))
            node = {"id": node_id, "component": new_component, "parameters": parameters,
                    "change": "native", "input": {"mode": "initialize", "source": "main",
                        "count": parameters.get("population_size", 1), "shuffle": False}, "return_from": None}
            nodes.append(node)
            plan = draft["plan"]
            if plan.get("kind") == "serial":
                plan["children"].append(_stage_for(node))
            else:
                draft["plan"] = {"kind": "serial", "children": [plan, _stage_for(node)]}
            st.session_state[_DRAFT_KEY] = draft
            st.session_state[_REVISION_KEY] = int(st.session_state.get(_REVISION_KEY, 0)) + 1
            st.rerun()


def _basic_plan(plan: Mapping[str, Any]) -> tuple[str, int, list] | None:
    times = 1
    if plan.get("kind") == "repeat":
        times, plan = plan["times"], plan["body"]
    if plan.get("kind") == "stage":
        return "serial", times, [deepcopy(dict(plan))]
    if plan.get("kind") in {"serial", "multi"} and all(child.get("kind") == "stage" for child in plan["children"]):
        return str(plan["kind"]), times, deepcopy(plan["children"])
    return None


def _render_plan(st: Any, draft: dict) -> None:
    _section(st, "运行顺序 · 可复用同一个算法实例")
    simple = _basic_plan(draft["plan"])
    if simple is None:
        st.info("当前是多层嵌套计划。它会完整保留；可在下方高级编辑中调整 serial / multi / repeat。")
        return
    mode, times, stages = simple
    columns = st.columns(2)
    with columns[0]:
        mode = st.selectbox("阶段如何执行", ["serial", "multi"], index=0 if mode == "serial" else 1,
                            key=_key(st, "plan_mode"), format_func=lambda v: "串行 serial" if v == "serial" else "协同提案 multi")
    with columns[1]:
        times = st.number_input("整个计划重复次数", 1, 10, value=int(times), step=1, key=_key(st, "plan_repeat"))
    st.caption("multi 使用共享控制面路由多个算法的提案，不表示多个独立 Case 或 CPU 并行；逻辑步预算仍限制实际运行。")
    ids = [item["id"] for item in draft["nodes"]]
    by_id = {item["id"]: item for item in draft["nodes"]}
    for index, item in enumerate(stages):
        with st.container(border=True):
            columns = st.columns(2)
            with columns[0]:
                options = ids + ([item["node"]] if item["node"] not in ids else [])
                item["node"] = st.selectbox(f"第 {index + 1} 阶段的实例", options, index=options.index(item["node"]),
                                            key=_key(st, f"stage::{index}::node"))
            with columns[1]:
                item["action"] = st.selectbox(f"第 {index + 1} 阶段的动作", ["search", "compete"],
                    index=1 if item.get("action") == "compete" else 0, key=_key(st, f"stage::{index}::action"),
                    format_func=lambda v: "运行搜索 / 池精修" if v == "search" else "接收返回并竞争")
            task = by_id.get(item["node"], {}).get("input") or {}
            completes_task = item["action"] == "compete" or task.get("mode") == "refine"
            controls = st.columns([2, 1], vertical_alignment="bottom")
            with controls[0]:
                if completes_task:
                    item["steps"] = None
                    st.caption("等待本次任务完成")
                else:
                    item["steps"] = st.number_input(f"第 {index + 1} 阶段的步数", 1, 20,
                        value=int(item.get("steps") or 2), step=1, key=_key(st, f"stage::{index}::steps"))
            with controls[1]:
                if st.button("移除", key=_key(st, f"stage::{index}::remove"), disabled=len(stages) <= 1):
                    del stages[index]
                    body = {"kind": mode, "children": stages}
                    draft["plan"] = {"kind": "repeat", "times": times, "body": body} if times > 1 else body
                    st.session_state[_DRAFT_KEY] = draft
                    st.session_state[_REVISION_KEY] = int(st.session_state.get(_REVISION_KEY, 0)) + 1
                    st.rerun()
    if st.button("增加一个阶段", key=_key(st, "add_stage")):
        stages.append(_stage_for(draft["nodes"][0]))
        body = {"kind": mode, "children": stages}
        draft["plan"] = {"kind": "repeat", "times": times, "body": body} if times > 1 else body
        st.session_state[_DRAFT_KEY] = draft
        st.session_state[_REVISION_KEY] = int(st.session_state.get(_REVISION_KEY, 0)) + 1
        st.rerun()
    body = stages[0] if len(stages) == 1 else {"kind": mode, "children": stages}
    draft["plan"] = {"kind": "repeat", "times": times, "body": body} if times > 1 else body


def _problem_as_expression(problem: Mapping[str, Any], dimension: int) -> dict:
    """An editable equivalent of an existing demo; no evaluation takes place."""
    if problem.get("component") == "problem.expression":
        return deepcopy(dict(problem))
    names = [f"x{i + 1}" for i in range(dimension)]
    variables = [{"name": name, "low": -2., "high": 2., "type": "continuous"} for name in names]
    if problem.get("component") == "problem.sphere":
        objectives = [{"name": "平方和", "expression": "+".join(name + "**2" for name in names), "direction": "min"}]
    else:
        tail = "+" + "+".join(name + "**2" for name in names[1:]) if len(names) > 1 else ""
        objectives = [{"name": "距中心 -1", "expression": f"({names[0]}+1)**2" + tail, "direction": "min"},
                      {"name": "距中心 +1", "expression": f"({names[0]}-1)**2" + tail, "direction": "min"}]
    return {"component": "problem.expression", "parameters": {
        "variables": variables, "objectives": objectives, "constraints": []}}


def _problem_summary(st: Any, problem: Mapping[str, Any], *, dimension: int, title: str = "当前问题") -> None:
    custom = problem.get("component") == "problem.expression"
    value = _problem_as_expression(problem, dimension)["parameters"]
    lines = ["变量 · " + "，".join(f"{row['name']} ∈ [{row['low']:g}, {row['high']:g}]" for row in value["variables"])]
    for row in value["objectives"]:
        lines.append(("最大化" if row["direction"] == "max" else "最小化") + f" {row['name']}：{row['expression']}")
    for row in value.get("constraints", []):
        lines.append(f"约束 {row['name']}：{row['expression']} {row['relation']} {row['rhs']:g}"
                     + (f"（容差 {row['tolerance']:g}）" if row.get("tolerance") else ""))
    if not value.get("constraints"):
        lines.append("约束 · 只有变量边界")
    badge = "可编辑数学问题" if custom else "内置演示 · 可替换成你的问题"
    st.markdown("<div class='lab-problem'><div class='lab-problem-title'>" + escape(title) + "</div>"
                + "<div class='lab-problem-type'>" + escape(badge) + "</div>"
                + "".join("<div class='lab-problem-line'>" + escape(line) + "</div>" for line in lines) + "</div>",
                unsafe_allow_html=True)


def _render_problem_editor(st: Any, draft: dict) -> bool:
    """Keep unfinished formula edits separate from the executable assembly."""
    _problem_summary(st, draft["problem"], dimension=int(draft["dimension"]), title="用于下一次运行的定义")
    revision = int(st.session_state.get(_REVISION_KEY, 0))
    saved = st.session_state.get(_PROBLEM_BUFFER_KEY)
    base_binding = _problem_as_expression(draft["problem"], draft["dimension"])
    if not saved or saved.get("revision") != revision:
        saved = {"revision": revision, "binding": deepcopy(base_binding), "base_binding": deepcopy(base_binding)}
    elif saved.get("base_binding") != base_binding and saved["binding"] == saved.get("base_binding"):
        # Changing a demo's dimension updates its untouched edit buffer too.
        saved = {"revision": revision, "binding": deepcopy(base_binding), "base_binding": deepcopy(base_binding)}
    value = deepcopy(saved["binding"]["parameters"])
    with st.expander("手动编辑变量、目标与约束", expanded=False):
        st.caption("连续变量用名称写公式。修改先保留在编辑区，点击“应用问题定义”后才用于装配与运行。")
        variables_tab, objectives_tab, constraints_tab = st.tabs(["变量与范围", "优化目标", "约束条件"])
        with variables_tab:
            count = st.number_input("变量数量", 1, 8, value=len(value["variables"]), step=1,
                                    key=_key(st, "problem_edit::variable_count"))
            rows = value["variables"][:count]
            while len(rows) < count:
                used = {row["name"] for row in rows}
                number = len(rows) + 1
                while f"x{number}" in used:
                    number += 1
                rows.append({"name": f"x{number}", "low": -2., "high": 2., "type": "continuous"})
            for index, row in enumerate(rows):
                columns = st.columns([2, 1.5, 1.5])
                row["name"] = columns[0].text_input(f"变量 {index + 1} 名称", row["name"],
                    key=_key(st, f"problem_edit::variable::{index}::name"))
                row["low"] = columns[1].number_input(f"变量 {index + 1} 下界", value=float(row["low"]),
                    key=_key(st, f"problem_edit::variable::{index}::low"))
                row["high"] = columns[2].number_input(f"变量 {index + 1} 上界", value=float(row["high"]),
                    key=_key(st, f"problem_edit::variable::{index}::high"))
                row["type"] = "continuous"
            value["variables"] = rows
            st.caption("在线编辑器支持 1–8 个连续变量；整数、类别或外部数据问题可导出 Project 扩展。")
        with objectives_tab:
            count = st.number_input("目标数量", 1, 2, value=len(value["objectives"]), step=1,
                                    key=_key(st, "problem_edit::objective_count"))
            rows = value["objectives"][:count]
            while len(rows) < count:
                rows.append({"name": f"目标 {len(rows) + 1}", "expression": value["variables"][0]["name"] + "**2", "direction": "min"})
            for index, row in enumerate(rows):
                columns = st.columns([2, 1.3, 4])
                row["name"] = columns[0].text_input(f"目标 {index + 1} 名称", row["name"],
                    key=_key(st, f"problem_edit::objective::{index}::name"))
                directions = ["min", "max"]
                row["direction"] = columns[1].selectbox(f"目标 {index + 1} 方向", directions,
                    index=directions.index(row["direction"]), format_func=lambda item: "最小化" if item == "min" else "最大化",
                    key=_key(st, f"problem_edit::objective::{index}::direction"))
                row["expression"] = columns[2].text_input(f"目标 {index + 1} 公式", row["expression"],
                    key=_key(st, f"problem_edit::objective::{index}::expression"))
            value["objectives"] = rows
            st.caption("公式示例：8*x - x**2；支持 abs/min/max/sqrt/log/exp/sin/cos，以及 pi/e。")
        with constraints_tab:
            count = st.number_input("约束数量", 0, 8, value=len(value.get("constraints", [])), step=1,
                                    key=_key(st, "problem_edit::constraint_count"))
            rows = value.get("constraints", [])[:count]
            while len(rows) < count:
                rows.append({"name": f"约束 {len(rows) + 1}", "expression": value["variables"][0]["name"],
                             "relation": "<=", "rhs": 0., "tolerance": 0.})
            for index, row in enumerate(rows):
                columns = st.columns([1.7, 3, 1, 1.2, 1.2])
                row["name"] = columns[0].text_input(f"约束 {index + 1} 名称", row["name"],
                    key=_key(st, f"problem_edit::constraint::{index}::name"))
                row["expression"] = columns[1].text_input(f"约束 {index + 1} 左侧公式", row["expression"],
                    key=_key(st, f"problem_edit::constraint::{index}::expression"))
                relations = ["<=", ">=", "=="]
                row["relation"] = columns[2].selectbox(f"约束 {index + 1} 关系", relations,
                    index=relations.index(row["relation"]), key=_key(st, f"problem_edit::constraint::{index}::relation"))
                row["rhs"] = columns[3].number_input(f"约束 {index + 1} 右侧值", value=float(row["rhs"]),
                    key=_key(st, f"problem_edit::constraint::{index}::rhs"))
                row["tolerance"] = columns[4].number_input(f"约束 {index + 1} 容差", min_value=0.,
                    value=float(row.get("tolerance", 0.)), key=_key(st, f"problem_edit::constraint::{index}::tolerance"))
            value["constraints"] = rows
            if not rows:
                st.caption("没有额外约束。变量上下界始终生效。")
        binding = {"component": "problem.expression", "parameters": value}
        saved["binding"] = deepcopy(binding)
        st.session_state[_PROBLEM_BUFFER_KEY] = saved
        pending = binding != _problem_as_expression(draft["problem"], draft["dimension"])
        if pending:
            st.warning("问题编辑尚未应用。下一次运行与 AI 请求会等待你应用或放弃这些修改。")
        if st.button("应用问题定义", key=_key(st, "problem_edit::apply"), type="primary"):
            from .lab_problem import normalize_problem
            try:
                problem = normalize_problem(binding)
            except (ValueError, TypeError) as exc:
                st.session_state[_PREFIX + "problem_error"] = f"问题未应用：{exc}"
            else:
                draft["problem"] = problem
                draft["dimension"] = len(problem["parameters"]["variables"])
                draft["pipeline"]["initializer"] = {"component": "repr.problem_uniform", "parameters": {}}
                st.session_state[_DRAFT_KEY] = deepcopy(draft)
                st.session_state[_REVISION_KEY] = revision + 1
                st.session_state.pop(_PREFIX + "problem_error", None)
                st.rerun()
        if st.button("放弃尚未应用的问题修改", key=_key(st, "problem_edit::discard"), disabled=not pending):
            st.session_state.pop(_PROBLEM_BUFFER_KEY, None)
            st.session_state[_REVISION_KEY] = revision + 1
            st.rerun()
        if st.session_state.get(_PREFIX + "problem_error"):
            st.error(st.session_state[_PREFIX + "problem_error"])
    return pending


def _render_assembly(st: Any, draft: dict, metadata: Mapping[str, Any]) -> None:
    components = metadata["components"]
    notice = st.session_state.pop(_PREFIX + "edit_notice", None)
    if notice:
        st.warning(notice)
    instances, plan = st.columns([1, 1.05], gap="large")
    with instances, st.container(key="catalog_lab_instances"):
        _edit_nodes(st, draft, metadata)
    with plan, st.container(key="catalog_lab_plan"):
        _render_plan(st, draft)
    with st.expander("候选管线、Bias 与 Plugin（可选）", expanded=False):
        st.caption("这里只展示已经接入装配和试跑的组件。Catalog 中其它组件仍可查阅；需要额外数据或领域代码的组件，请导出 Project 后接入。")
        pipeline = draft["pipeline"]
        pipeline["initializer"] = _component_picker(st, "母池初始解来源", list(components["initializers"]),
            pipeline["initializer"], name="initializer")
        pipeline["mutator"] = _component_picker(st, "问题管线的可选变异", list(components["mutators"]),
            pipeline.get("mutator"), name="mutator", optional=True)
        pipeline["repair"] = _component_picker(st, "问题修复", list(components["repairs"]),
            pipeline["repair"], name="repair")
        st.caption("Pipeline 提供候选处理能力；变异是否被调用，取决于 Adapter 的原生路径或选定的变化函数。")
        draft["bias"] = _component_picker(st, "可选软评分 Bias", list(components["biases"]),
            draft.get("bias"), name="bias", optional=True)
        st.caption("Bias 只影响算法的选择评分，保留 Problem 的原始目标与约束；它不代替算法或硬准入。")
        plugin_rows = list(components["plugins"])
        plugin_keys = [item["key"] for item in plugin_rows]
        selected = [item["component"] for item in draft.get("plugins", [])]
        chosen = st.multiselect("生命周期 Plugin", plugin_keys, default=selected,
            key=_key(st, "plugins"), format_func=lambda key: next(item["label"] for item in plugin_rows if item["key"] == key))
        current_plugins = {item["component"]: item for item in draft.get("plugins", [])}
        draft["plugins"] = []
        for key in chosen:
            row = next(item for item in plugin_rows if item["key"] == key)
            st.markdown("**" + row["label"] + "**")
            values = current_plugins.get(key, {}).get("parameters", {})
            draft["plugins"].append({"component": key, "parameters": _parameters(st, row, values, prefix="plugin::" + key)})
            _component_link(st, row)
    with st.expander("高级 · 嵌套计划 / 完整装配 JSON 导入", expanded=False):
        st.caption("这是同一份装配文档。可以修改嵌套 serial / multi / repeat；点击应用后才替换工作区。不会接收 Python 或动态 import。")
        generated = json.dumps(draft, ensure_ascii=False, indent=2)
        editor_key, previous_key = _key(st, "document_json"), _key(st, "document_json_generated")
        previous = st.session_state.get(previous_key)
        existing = st.session_state.get(editor_key)
        # Follow visual edits while the JSON buffer is untouched. Once the user
        # starts editing JSON, preserve that buffer until its explicit Apply.
        if existing is not None and previous is not None and existing == previous:
            st.session_state[editor_key] = generated
        st.session_state[previous_key] = generated if existing is None or existing == previous else previous
        initial = {} if editor_key in st.session_state else {"value": generated}
        value = st.text_area("完整装配 JSON", height=300, key=editor_key, **initial)
        if existing is not None and previous is not None and existing != previous:
            st.caption("JSON 缓冲区有尚未应用的编辑；可视装配继续保留，点击应用才会替换它。")
        upload_key = _key(st, "import_json")
        st.file_uploader("也可导入先前导出的装配 JSON", type=["json"], key=upload_key)

        def apply_json() -> None:
            try:
                upload = st.session_state.get(upload_key)
                source = upload.getvalue().decode("utf-8-sig") if upload is not None else st.session_state[editor_key]
                if len(source.encode("utf-8")) > 65536:
                    raise ValueError("装配 JSON 不能超过 64 KiB")
                _replace_draft(st, json.loads(source))
            except (ValueError, TypeError, UnicodeError) as exc:
                st.session_state[_PREFIX + "document_error"] = f"未应用：{exc}"
            else:
                st.session_state.pop(_PREFIX + "document_error", None)

        st.button("校验并应用 JSON", key=_key(st, "apply_json"), on_click=apply_json)
        if st.session_state.get(_PREFIX + "document_error"):
            st.error(st.session_state[_PREFIX + "document_error"])


def _render_sources(st: Any, spec: Mapping[str, Any]) -> None:
    from . import lab_project

    notes = st.session_state.get(_NOTES_KEY, "")
    files = lab_project.preview_files(spec, design_notes=notes)
    names = sorted(files)
    default = next((index for index, name in enumerate(names) if name.endswith("/build_solver.py")), 0)
    st.caption("这里展示的文件与下载、试跑使用同一份生成逻辑。查看源码不会构造 Solver 或 Unit。")
    left, right = st.columns([1, 1])
    with left:
        st.download_button("下载完整 Project", lab_project.project_archive(spec, design_notes=notes),
                           file_name="assembly_project.zip", mime="application/zip",
                           key=_PREFIX + "download_project", width="stretch", on_click="ignore")
    with right:
        st.download_button("下载装配参数 JSON", json.dumps(spec, ensure_ascii=False, indent=2),
                           file_name="assembly_spec.json", mime="application/json",
                           key=_PREFIX + "download_spec", width="stretch", on_click="ignore")
    with st.expander(f"标准项目结构 · {len(files)} 个文件", expanded=False):
        st.code("\n".join(names), language="text")
    selected = st.selectbox("项目文件", names, index=default, key=_PREFIX + f"file::{spec['recipe']}")
    if selected:
        extension = selected.rsplit(".", 1)[-1]
        language = {"py": "python", "json": "json", "md": "markdown", "toml": "toml"}.get(extension, "text")
        st.code(files[selected], language=language, line_numbers=True)
    st.caption("导出后从 run_project.py 启动，仍走正式 Case 与 Project L0。"
               "本版源码预览只读；不会把在网页中编辑的任意 Python 发送到服务器执行。")


def _render_observations(st: Any, result: Mapping[str, Any], *, problem: Mapping[str, Any] | None = None) -> None:
    """Show only the runner's checked observations; never infer new authority."""
    records = result.get("records") or []
    if records:
        import altair as alt
        import pandas as pd

        custom = bool(problem and problem.get("component") == "problem.expression")
        single = custom and len(problem["parameters"]["objectives"]) == 1
        if single:
            from .lab_problem import display_objectives
            objective = problem["parameters"]["objectives"][0]
            y_title = objective["name"] + (" · 最大化" if objective["direction"] == "max" else " · 最小化")
            trend = [{"逻辑步": item["steps"], y_title: display_objectives(problem, [item["best_feasible_raw_sum"]])[0]}
                     for item in records if item.get("best_feasible_raw_sum") is not None]
            if not trend:
                st.info("本次记录中暂无可行结果。下方仍保留已接纳候选及其原始约束违反量。")
        else:
            # Unlike business objectives cannot be summed into a claimed best.
            y_title = "累计评估次数" if custom else "最小原始目标和"
            trend = ([{"逻辑步": item["steps"], y_title: item["evaluations"]} for item in records]
                     if custom else [{"逻辑步": item["steps"], y_title: item["best_raw_sum"]}
                     for item in records if item.get("best_raw_sum") is not None])
        if trend:
            st.markdown("**搜索进展**")
            chart = (alt.Chart(pd.DataFrame(trend)).mark_line(color="#087f6b", point=True)
                     .encode(x=alt.X("逻辑步:Q", axis=alt.Axis(tickMinStep=1)),
                             y=alt.Y(y_title + ":Q"))
                     .properties(height=190, background="#ffffff")
                     .configure_axis(labelColor="#52666d", titleColor="#172b32",
                                     gridColor="#e5eceb", domainColor="#becdca", tickColor="#becdca")
                     .configure_view(stroke="#e3e9e9"))
            st.altair_chart(chart, width="stretch", theme=None)
            st.caption("曲线只统计原始约束违反量为 0 的历史候选，目标值按你定义的方向显示。" if single else
                       "显示各次提交的累计评估次数；下表按你定义的名称与方向显示目标值，不代表 Pareto 前沿。" if custom else
                       "显示各次提交时，已接纳历史候选中的最小原始目标和。它用于观察搜索进展，不替代种群的多目标选择规则。")
        with st.expander("逐步运行记录", expanded=False):
            st.dataframe([{"逻辑步": item.get("steps"), "累计评估": item.get("evaluations"),
                           "已接纳候选": item.get("accepted_count"), "池记录数": item.get("pool_records"),
                           "阶段": " / ".join(item.get("phases") or [])} for item in records],
                         hide_index=True, width="stretch")
    values = result.get("results") or {}
    candidates = values.get("candidates") or []
    objectives = values.get("raw_objectives") or []
    violations = values.get("raw_violations") or []
    refs = values.get("refs") or []
    if candidates and len(candidates) == len(objectives) == len(violations) == len(refs):
        st.markdown("**已接纳候选与原始评估**")
        st.caption("展示最近至多 128 个已接纳版本。这是池中的历史候选，不代表最终种群或 Pareto 前沿。")
        rows = []
        custom = bool(problem and problem.get("component") == "problem.expression")
        if custom:
            from .lab_problem import display_objectives, objective_definitions
            definitions = objective_definitions(problem)
            variable_names = [row["name"] for row in problem["parameters"]["variables"]]
        for index, (candidate, feedback, violation, ref) in enumerate(zip(candidates, objectives, violations, refs)):
            shown = display_objectives(problem, feedback) if custom else feedback
            scores = ({f"{item['name']}（{'最大化' if item['direction'] == 'max' else '最小化'}）": shown[i]
                       for i, item in enumerate(definitions)} if custom else
                      {f"原始目标 {i + 1}": value for i, value in enumerate(shown)})
            row = {"序号": index + 1, **{variable_names[i] if custom else f"x{i + 1}": value for i, value in enumerate(candidate)},
                   **scores, "约束违反量": violation,
                   "候选 token": str(ref.get("candidate_token", "")),
                   "版本记录": str(ref.get("record_id", "")), "原记录行": ref.get("row")}
            rows.append(row)
        st.dataframe(rows, hide_index=True, width="stretch", height=min(340, 75 + len(rows) * 35))
        if custom:
            st.caption("最大化目标已恢复原方向正负号；是否可行仍由原始约束违反量判断。算法内部的最小化值保留在完整求解报告中。")
    pool = result.get("pool") or {}
    if pool:
        st.markdown("**Pool · 已提交的候选区域**")
        columns = st.columns(3)
        columns[0].metric("初始候选", pool.get("initial_count", "—"))
        columns[1].metric("已接纳候选版本", pool.get("accepted_count", "—"))
        columns[2].metric("池记录批次数", pool.get("records", "—"))
        views = pool.get("views") or []
        if views:
            st.dataframe([{
                "子池 / 视图": view["descriptor"]["name"],
                "类型": {"objective_projection": "方向投影", "candidate_view": "成员视图"}.get(
                    view["metadata"].get("kind"), view["metadata"].get("kind", "普通集合")),
                "创建者路径": "/".join(view["metadata"].get("created_by") or []),
                "修订": view["descriptor"]["revision"], "成员引用数": view["members"],
                "投影权重": (view["metadata"].get("projection") or {}).get("weights", []),
            } for view in views], hide_index=True, width="stretch")
            st.caption("子池保存候选引用；方向视图的权重只影响该视图的比较。")
    units = (result.get("unit") or {}).get("instances", [])
    if units:
        st.markdown("**Unit · 算法工作结构**")
        st.dataframe([{"实例路径": unit.get("path", ""), "Adapter": unit.get("type", ""),
                       "Unit 已建立": unit.get("unit_exists", False),
                       "当前点已建立": unit.get("current_exists", False),
                       "种群成员": unit.get("population_members", 0),
                       "已发布视图": len(unit.get("published_views") or [])} for unit in units],
                     hide_index=True, width="stretch")


def _render_result(st: Any, job: Mapping[str, Any], *, current_digest: str) -> None:
    status = str(job.get("status", "unknown"))
    if job.get("spec_digest") != current_digest:
        st.warning("参数已改变：下方是上一次提交的结果，与当前装配参数不同。再次试跑才会生成新结果。")
    if status in _ACTIVE:
        st.info("作业已排队，等待运行。" if status == "queued" else "正在试跑，结果会自动刷新。")
        st.caption("试跑使用提交时冻结的参数。调整上方参数不会改变正在运行的作业。")
        return
    result = job.get("result") or {}
    if status == "succeeded":
        st.success("试跑完成 · 已通过正式 Project / Case 执行")
    elif status == "failed":
        error = result.get("error") or job.get("error") or {}
        message = error.get("message", "试跑未完成，请查看运行日志。") if isinstance(error, Mapping) else str(error)
        st.error(message)
    else:
        st.warning("作业状态暂不可读，请刷新运行状态。")

    if result:
        columns = st.columns(3)
        columns[0].metric("已提交逻辑步", result.get("steps", "—"))
        columns[1].metric("实际评估次数", result.get("evaluations", "—"))
        duration = result.get("duration_seconds")
        columns[2].metric("运行耗时", f"{duration:.2f} s" if isinstance(duration, (int, float)) else "—")
        if result.get("plan_completed") is False:
            st.warning("本次逻辑步预算已用完，整个编排计划尚未完成；当前结果仅包含已提交部分。")
        _render_observations(st, result, problem=(job.get("spec") or {}).get("problem"))
        with st.expander("完整求解报告与状态", expanded=False):
            st.json({"report": result.get("report"), "pool": result.get("pool"),
                     "unit": result.get("unit"), "results": result.get("results"),
                     "plan_completed": result.get("plan_completed")})
        with st.expander("Project 执行与 L0 资源审计", expanded=False):
            st.json({"resource_binding": result.get("resource_binding"),
                     "project_result": result.get("project_result"),
                     "exit_code": result.get("exit_code")})
        with st.expander("运行日志", expanded=status == "failed"):
            st.code(str(result.get("logs") or "没有可显示的运行日志。"), language="text")
    with st.expander("本次提交的装配参数", expanded=False):
        st.json(job.get("spec") or {})
        st.caption(f"作业 {job.get('job_id', '—')} · 参数指纹 {str(job.get('spec_digest', '—'))[:12]}")
    if status in {"succeeded", "failed"}:
        st.download_button("下载本次运行记录", json.dumps(dict(job), ensure_ascii=False, indent=2),
                           file_name=f"trial_{str(job.get('job_id', 'result'))[:12]}.json",
                           mime="application/json", key=_PREFIX + "download_result", on_click="ignore")


def _render_trial(st: Any, spec: Mapping[str, Any] | None, capabilities: Mapping[str, Any]) -> None:
    from . import lab_client
    from .lab_jobs import spec_digest

    current_digest = spec_digest(spec) if spec is not None else "invalid"
    job = st.session_state.get(_JOB_KEY)
    active = bool(job and job.get("status") in _ACTIVE)
    supported = {str(item.get("id")) if isinstance(item, Mapping) else str(item)
                 for item in capabilities.get("recipes", ())}
    enabled = bool(spec is not None and capabilities.get("enabled")
                   and (spec.get("recipe") == "assembly" or not supported or spec["recipe"] in supported))
    intent = st.session_state.get(_INTENT_KEY)
    if intent:
        if intent["spec_digest"] == current_digest:
            st.warning("上次提交状态尚未确认。再次点击试跑会沿用同一请求重试确认，避免把本次提交当作新运行。")
        else:
            st.warning("上一组参数的提交状态尚未确认；修改参数不会取消可能已启动的作业。"
                       "恢复原参数后试跑可重试确认；使用新参数点击试跑将提交一组新实验。")
    if spec is None:
        st.info("修正装配参数后即可试跑；已提交作业继续按原参数运行。")
    elif not enabled:
        st.info(str(capabilities.get("reason") or "当前装配未启用在线试跑，仍可查看源码并导出项目。"))
    st.caption("试跑执行当前已校验的组件装配；预算、超时与并发由运行服务限制。界面刷新不会重复提交。")
    if st.button("开始小预算试跑", type="primary", width="stretch", key=_PREFIX + "run",
                 disabled=not enabled or active):
        if not intent or intent["spec_digest"] != current_digest:
            intent = {"request_id": uuid4().hex, "spec_digest": current_digest, "spec": dict(spec)}
            st.session_state[_INTENT_KEY] = intent
        try:
            submitted = lab_client.submit(spec, request_id=intent["request_id"])
        except lab_client.LabClientError as exc:
            st.error(f"无法提交试跑：{exc}")
        else:
            st.session_state[_JOB_KEY] = dict(submitted)
            del st.session_state[_INTENT_KEY]
            # Disable Run immediately; another UI event must not submit a second
            # request while this one is still in progress.
            st.rerun()

    @st.fragment(run_every="2s" if active else None)
    def trial_status() -> None:
        saved = st.session_state.get(_JOB_KEY)
        if not saved:
            st.markdown("<div class='lab-run-empty'>还没有运行记录。<br>先确认装配与源码，再点击“开始小预算试跑”。"
                        "运行完成后，这里会显示真实评估次数、Pool、Unit 和 Project 执行记录。</div>",
                        unsafe_allow_html=True)
            return
        refresh = st.button("刷新运行状态", key=_PREFIX + "refresh")
        if refresh or saved.get("status") in _ACTIVE:
            try:
                updated = lab_client.poll(saved["job_id"])
            except lab_client.LabClientError as exc:
                st.warning(f"暂时无法读取作业：{exc}")
                if st.button("移除本页运行记录", key=_PREFIX + "forget",
                             help="只清除本页绑定，不取消仍在服务中运行的作业。可在记录过期或服务重启后重新试跑。"):
                    del st.session_state[_JOB_KEY]
                    st.rerun()
            else:
                was_active = saved.get("status") in _ACTIVE
                saved = dict(updated)
                st.session_state[_JOB_KEY] = saved
                if was_active and saved.get("status") not in _ACTIVE:
                    # Re-render the app once to re-enable Run and stop the timer.
                    st.rerun()
        _render_result(st, saved, current_digest=current_digest)

    trial_status()


def _render_workspace_transfer(st: Any, spec: Mapping[str, Any] | None) -> None:
    """Save confirmed data only; an import never restores execution authority."""
    from .lab_design import export_workspace, import_workspace

    if spec is not None:
        st.download_button("下载工作区（含设计笔记与近期对话）",
            export_workspace(spec, design_notes=st.session_state.get(_NOTES_KEY, ""),
                             history=st.session_state.get(_HISTORY_KEY, [])),
            file_name="lab_workspace.json", mime="application/json", key=_PREFIX + "download_workspace",
            width="stretch", on_click="ignore")
    else:
        st.caption("当前装配通过校验后可下载工作区；设计笔记仍保留在本页。")
    st.text_area("粘贴工作区 JSON", key=_PREFIX + "workspace_import", height=100, max_chars=128 * 1024,
                 placeholder="粘贴此前下载的 lab_workspace.json；不会执行其中任何内容。")
    st.caption("导入会替换本页装配、设计笔记与近期对话，清除本页旧草案和运行显示；不会取消服务器上的任务。")

    def restore_workspace() -> None:
        try:
            restored = import_workspace(st.session_state.get(_PREFIX + "workspace_import", ""))
        except (ValueError, TypeError, UnicodeError) as exc:
            st.session_state[_PREFIX + "workspace_error"] = f"工作区未导入：{exc}"
            return
        _replace_draft(st, restored["assembly"])
        st.session_state[_NOTES_KEY] = restored["design_notes"]
        st.session_state[_HISTORY_KEY] = restored["history"]
        for key in list(st.session_state):
            if (key in {_JOB_KEY, _INTENT_KEY, _PROBLEM_BUFFER_KEY,
                        _PREFIX + "assistant_seen", _PREFIX + "assistant_apply_error",
                        _PREFIX + "problem_error", _PREFIX + "workspace_error"}
                    or key.startswith(_AI_JOB_KEY) or key.startswith(_AI_INTENT_KEY)):
                st.session_state.pop(key, None)
        st.session_state[_PREFIX + "workspace_restored"] = True

    st.button("校验并恢复工作区", key=_PREFIX + "workspace_restore", on_click=restore_workspace)
    if st.session_state.get(_PREFIX + "workspace_error"):
        st.error(st.session_state[_PREFIX + "workspace_error"])
    if st.session_state.pop(_PREFIX + "workspace_restored", False):
        st.success("已恢复装配、设计笔记与近期对话。导入内容尚未运行。")


def _render_framework_evidence(st: Any, result: Mapping[str, Any]) -> None:
    """Evidence remains a quoted source, never a model-selected URL or a proof."""
    evidence = result.get("framework_evidence")
    if isinstance(evidence, Mapping):
        evidence = list(evidence.get("contracts") or []) + list(evidence.get("components") or [])
    if not isinstance(evidence, list) or not evidence:
        return
    with st.expander("AI 引用的框架依据", expanded=False):
        st.caption("以下是检索到的源码或契约原文，只说明接口与职责，不构成实际运行、算法正确性或性能证明。")
        options = result.get("online_options", [])
        if isinstance(options, list):
            for option in options[:6]:
                if isinstance(option, Mapping) and isinstance(option.get("available_changes"), list):
                    st.write(f"实例 {option.get('instance', '')} · {option.get('component', '')}")
                    st.caption("当前变化：" + str(option.get("current_change", "")) +
                        "；在线可选：" + " / ".join(str(v) for v in option["available_changes"][:12]))
        for row in evidence[:12]:
            if not isinstance(row, Mapping) or not isinstance(row.get("source"), Mapping):
                continue
            source = row["source"]
            path, line, end_line = source.get("path"), source.get("line"), source.get("end_line")
            # Render locations as text only. Even a malformed service response
            # must not introduce an arbitrary external or local file link.
            if (not isinstance(path, str) or not path or len(path) > 320
                    or path.startswith(("/", "\\")) or ":" in path or "\\" in path
                    or ".." in path.split("/") or type(line) is not int or line < 1
                    or type(end_line) is not int or end_line < line):
                continue
            title = str(row.get("title") or row.get("key") or row.get("id") or "框架原文")[:160]
            st.write(title)
            st.caption(f"{path}:{line}–{end_line} · sha256 {str(source.get('sha256', ''))[:12]}")
            if row.get("online_bound") is False:
                st.caption("框架中可查；尚未绑定为本实验台的可运行选项。")
            excerpt = row.get("excerpt")
            if isinstance(excerpt, str) and excerpt:
                st.code(excerpt[:8000], language="text")


def _render_design_suggestion(st: Any, result: Mapping[str, Any], *, current_digest: str,
                              job: Mapping[str, Any], widget_prefix: str) -> None:
    from .lab_design import apply_design_notes, notes_digest
    from .lab_jobs import LabJobError, spec_digest
    from .lab_project import normalize_spec

    proposed = result.get("design_notes")
    if not isinstance(proposed, str) or not proposed.strip():
        return
    current_notes = st.session_state.get(_NOTES_KEY, "")
    original_digest = result.get("design_base_digest")
    stale = (result.get("base_digest", job.get("base_digest")) != current_digest
             or original_digest != notes_digest(current_notes)
             or job.get("ui_design_base_digest", original_digest) != original_digest)
    with st.expander("AI 建议的设计笔记 · 尚未确认", expanded=True):
        st.code(proposed[:6000], language="markdown")
        st.caption("确认笔记只保存设计决定，不会应用装配或运行算法。待开发内容仍是待开发。")
        if proposed == current_notes:
            st.caption("这份建议与当前已保存的设计笔记相同，无需再次覆盖。")
            return
        if stale:
            st.warning("当前设计笔记或装配已经改变。这份旧笔记建议不能覆盖新改动，请基于当前工作区重新整理。")

        def confirm_notes() -> None:
            try:
                current = normalize_spec(st.session_state[_DRAFT_KEY])
                if spec_digest(current) != result.get("base_digest", job.get("base_digest")):
                    raise LabJobError("stale_design", "装配已修改，请基于当前装配重新整理。")
                st.session_state[_NOTES_KEY] = apply_design_notes(st.session_state.get(_NOTES_KEY, ""), result)
            except (ValueError, TypeError, LabJobError) as exc:
                st.session_state[widget_prefix + "notes_error"] = f"设计笔记未确认：{exc}"
            else:
                st.session_state.pop(widget_prefix + "notes_error", None)

        st.button("确认并保存这份设计笔记", key=widget_prefix + "confirm_notes", disabled=stale,
                  width="stretch", on_click=confirm_notes)
        if st.session_state.get(widget_prefix + "notes_error"):
            st.error(st.session_state[widget_prefix + "notes_error"])


def _render_assistant(st: Any, spec: Mapping[str, Any] | None, *, stage: str = "problem", capabilities=None) -> None:
    from . import lab_client
    from .lab_assembly import normalize_assembly
    from .lab_jobs import spec_digest

    job_key = _AI_JOB_KEY if stage == "problem" else _AI_JOB_KEY + "::" + stage
    intent_key = _AI_INTENT_KEY if stage == "problem" else _AI_INTENT_KEY + "::" + stage
    widget_prefix = _PREFIX + "assistant_" + stage + "::"
    if capabilities is None:
        try:
            capabilities = lab_client.assistant_capabilities()
        except lab_client.LabClientError as exc:
            capabilities = {"enabled": False, "reason": f"AI 暂不可用：{exc}"}
    if not capabilities.get("enabled"):
        st.caption(str(capabilities.get("reason") or "AI 服务未配置；手动装配、源码导出和试跑仍可使用。"))
    quota = capabilities.get("quota") or {}
    daily_limit = (capabilities.get("limits") or {}).get("requests_per_utc_day")
    # Remaining is advisory legacy state unless this service explicitly declares
    # a finite daily limit. An unlimited service may still have old quota records.
    daily_limit_reached = (type(daily_limit) is int and daily_limit > 0
                           and quota.get("remaining") == 0)
    online = bool(capabilities.get("enabled"))
    status = "AI 已连接" if online else "AI 暂不可用"
    st.markdown("<div class='lab-status'><span class='lab-status-dot" + ("" if online else " offline")
                + "'></span>" + status + "</div>", unsafe_allow_html=True)
    if daily_limit_reached:
        st.caption("当前服务已达到管理员配置的每日请求上限，请调整服务配置后继续。")
    labels = {"problem": ("描述要解决的问题", "可以从问题或算法想法开始。例如：给 GA 的每个成员保存独立步长，怎样维护 Unit、变化和选择？也可以直接描述变量、目标与约束。", "生成可编辑草案"),
              "assembly": ("描述想怎么调整算法", "例如：我想实现新的交叉方法，需要扩展 Unit 吗？哪些已有组件能复用，哪些逻辑需要开发？", "请 AI 调整装配"),
              "results": ("针对运行结果，你想了解什么", "例如：本次计划完成了吗？评估预算够不够？下一次该调整哪里？", "请 AI 解读结果")}
    label, placeholder, action = labels[stage]
    if stage == "problem":
        with st.container(key="catalog_lab_prompts"):
            prompt_columns = st.columns(2)
            for column, (title, text) in zip(prompt_columns, [
                ("定义一个生产优化问题", "我想优化生产量 amount，范围 0 到 10。最大化利润 8*amount-amount**2，同时要求 amount<=6。请先帮我整理问题定义。"),
                ("设计 GA → VNS 流程", "我想先用 GA 全局搜索，再用 VNS 精修选中的解，最后交还 GA 比较替换。请先和我讨论如何装配，暂时不要改动定义。"),
            ]):
                column.button(title, key=widget_prefix + "prompt::" + title, width="stretch",
                              on_click=lambda value=text: st.session_state.update({widget_prefix + "instruction": value}))
    instruction = st.text_area(label, height=170, max_chars=4000, key=widget_prefix + "instruction", placeholder=placeholder)
    submitted_instruction = instruction
    job = st.session_state.get(job_key)
    active = bool(job and job.get("status") in _ACTIVE)
    current_digest = spec_digest(spec) if spec is not None else "invalid"
    intent = st.session_state.get(intent_key)
    if intent:
        st.warning("上次 AI 请求状态尚未确认。描述、装配、设计笔记与对话上下文相同时再次提交将沿用原请求；改变内容不会取消旧请求。")
    if st.button(action, type="primary", key=widget_prefix + "generate", width="stretch",
                 disabled=not capabilities.get("enabled") or spec is None or not instruction.strip() or active or daily_limit_reached):
        from .lab_guide import build_guide_context
        from .lab_design import notes_digest
        context = build_guide_context(spec, stage=stage,
            history=st.session_state.get(_HISTORY_KEY, []), job=st.session_state.get(_JOB_KEY),
            design_notes=st.session_state.get(_NOTES_KEY, ""))
        same = bool(intent and intent.get("base_digest") == current_digest
                    and intent.get("instruction") == submitted_instruction and intent.get("guide_context") == context)
        if not same:
            intent = {"request_id": uuid4().hex, "base_digest": current_digest,
                      "spec": deepcopy(dict(spec)), "instruction": submitted_instruction, "guide_context": context}
            st.session_state[intent_key] = intent
        try:
            result = lab_client.assistant_submit(intent["spec"], intent["instruction"], request_id=intent["request_id"],
                                                 guide_context=intent.get("guide_context"))
        except lab_client.LabClientError as exc:
            st.error(f"未能确认 AI 请求：{exc}")
        else:
            st.session_state[job_key] = {**dict(result), "ui_instruction": submitted_instruction,
                "ui_design_base_digest": notes_digest(intent["guide_context"].get("design_notes", ""))}
            del st.session_state[intent_key]
            st.session_state.pop(_AI_CAPS_KEY, None)
            st.rerun()
    job = st.session_state.get(job_key)
    if not job:
        st.markdown("<div class='lab-helper'>从业务问题或算法想法开始都可以。AI 依据框架契约给出建议，确认后才应用到右侧定义。</div>", unsafe_allow_html=True)
        return
    refresh = st.button("刷新 AI 草案", key=widget_prefix + "refresh")
    if refresh or job.get("status") in _ACTIVE:
        try:
            job = {**dict(lab_client.assistant_poll(job["job_id"])), "ui_instruction": job.get("ui_instruction", ""),
                   "ui_design_base_digest": job.get("ui_design_base_digest")}
        except lab_client.LabClientError as exc:
            st.warning(f"暂时无法读取 AI 草案：{exc}")
        else:
            st.session_state[job_key] = job
    if job.get("status") in _ACTIVE:
        st.info("AI 正在整理定义与草案。可以继续手动编辑；草案不会覆盖新改动。")
        return
    if job.get("status") == "failed":
        error = job.get("error") or (job.get("result") or {}).get("error") or {}
        st.error(str(error.get("message", "AI 未生成可用草案。") if isinstance(error, Mapping) else error))
        return
    result = job.get("result") or {}
    seen = list(st.session_state.get(_PREFIX + "assistant_seen", []))
    if job.get("job_id") not in seen:
        history = list(st.session_state.get(_HISTORY_KEY, []))
        history.extend([{"role": "user", "content": str(job.get("ui_instruction", ""))[:600]},
                        {"role": "assistant", "content": (str(result.get("explanation", "")) + "\n" +
                         "\n".join(str(row) for row in result.get("questions", [])))[:600]}])
        st.session_state[_HISTORY_KEY] = [row for row in history if row["content"].strip()][-6:]
        st.session_state[_PREFIX + "assistant_seen"] = [*seen, job.get("job_id")][-12:]
    if result.get("explanation"):
        st.markdown(str(result["explanation"]))
    changes = result.get("changes") or []
    if changes:
        st.markdown("**建议改动**")
        for change in changes:
            st.write("• " + (change if isinstance(change, str) else json.dumps(change, ensure_ascii=False)))
    for question in result.get("questions") or []:
        st.info(str(question))
    _render_framework_evidence(st, result)
    _render_design_suggestion(st, result, current_digest=current_digest, job=job, widget_prefix=widget_prefix)
    proposal = result.get("draft")
    if proposal is None:
        st.caption("当前只有建议或待补信息，尚没有可应用的装配。可以补充描述后再生成。")
        return
    try:
        proposal = normalize_assembly(proposal)
    except (ValueError, TypeError) as exc:
        st.error(f"AI 草案未通过装配校验，不能应用：{exc}")
        return
    _problem_summary(st, proposal["problem"], dimension=proposal["dimension"], title="AI 建议 · 尚未应用")
    base_digest = result.get("base_digest", job.get("base_digest"))
    stale = base_digest != current_digest
    if stale:
        st.warning("草案生成后，当前装配已经改变。为避免覆盖手动修改，这份旧草案不能应用；请基于当前装配重新生成。")
    with st.expander("查看 AI 草案及变更", expanded=False):
        import difflib
        original = json.dumps(spec or {}, ensure_ascii=False, indent=2, sort_keys=True).splitlines()
        modified = json.dumps(proposal, ensure_ascii=False, indent=2, sort_keys=True).splitlines()
        st.code("\n".join(difflib.unified_diff(original, modified, fromfile="当前装配", tofile="AI 草案", lineterm="")), language="diff")
        st.json(proposal)
    st.caption("草案已做结构校验，尚未执行。应用后仍由你决定是否试跑。")
    if isinstance(result.get("design_notes"), str) and result["design_notes"].strip():
        st.caption("需要同时采纳设计笔记和装配时，请先确认上方笔记，再应用装配。应用装配不会自动确认笔记。")
    def apply_ai() -> None:
        from .lab_assistant import apply_draft
        from .lab_jobs import LabJobError
        from .lab_project import normalize_spec
        try:
            checked = apply_draft(normalize_spec(st.session_state[_DRAFT_KEY]), result)
            _replace_draft(st, checked)
        except (ValueError, TypeError, LabJobError) as exc:
            st.session_state[_PREFIX + "assistant_apply_error"] = f"未应用 AI 草案：{exc}"
        else:
            st.session_state.pop(job_key, None)
            st.session_state.pop(_PREFIX + "assistant_apply_error", None)

    st.button("应用这份 AI 草案", key=widget_prefix + "apply", disabled=stale or spec is None,
              width="stretch", on_click=apply_ai)
    if st.session_state.get(_PREFIX + "assistant_apply_error"):
        st.error(st.session_state[_PREFIX + "assistant_apply_error"])


def _assistant_capabilities(st: Any) -> dict:
    """Cache reachability failures too, so editing never multiplies timeouts."""
    from . import lab_client

    now = time.monotonic()
    saved = st.session_state.get(_AI_CAPS_KEY)
    if saved and 0 <= now - saved["at"] < _AI_CAPS_TTL:
        return deepcopy(saved["value"])
    try:
        value = dict(lab_client.assistant_capabilities())
    except lab_client.LabClientError as exc:
        value = {"enabled": False, "reason": f"AI 暂不可用：{exc}"}
    st.session_state[_AI_CAPS_KEY] = {"at": now, "value": deepcopy(value)}
    return value


def render_workbench(st: Any, *, hosted: bool = False) -> None:
    """One editable assembly document drives manual, AI, export and execution."""
    from . import lab_assembly, lab_client, lab_project

    st.markdown(_STYLES, unsafe_allow_html=True)
    st.sidebar.markdown(WORKSPACE_FOOTER, unsafe_allow_html=True)
    from .lab_workspace import workspace_enabled
    workspace_modes = ["自由装配", "已有 Project 协作"]
    if workspace_enabled(hosted=hosted):
        workspace_modes.append("Project 代码工作区")
    workspace_mode = st.radio("工作方式", workspace_modes,
                              horizontal=True, key="catalog_lab_workspace_mode")
    if workspace_mode == "Project 代码工作区":
        from .lab_workspace_ui import render_workspace
        render_workspace(st, hosted=hosted)
        return
    if workspace_mode == "已有 Project 协作":
        from .lab_project_ui import render_project_workbench
        render_project_workbench(st)
        return
    try:
        capabilities = lab_client.get_capabilities()
    except lab_client.LabClientError as exc:
        capabilities = {"enabled": False, "mode": "unavailable", "reason": f"试跑服务暂不可用：{exc}", "recipes": []}
    metadata = lab_assembly.assembly_catalog()
    if hosted and capabilities.get("mode") == "local":
        capabilities = {"enabled": False, "mode": "unavailable", "reason": "托管页面需要配置隔离试跑服务，不能使用本机执行。"}
    if capabilities.get("enabled") and capabilities.get("assembly_catalog") != metadata:
        capabilities = {"enabled": False, "mode": "unavailable", "reason": "运行服务的组件声明与当前页面不同，请更新服务后再试跑；手动装配和导出仍可使用。"}
    if _DRAFT_KEY not in st.session_state:
        st.session_state[_DRAFT_KEY] = lab_assembly.assembly_from_recipe("ga")
        st.session_state[_REVISION_KEY] = 0
    draft = deepcopy(st.session_state[_DRAFT_KEY])
    with st.container(key="catalog_lab_workspace"):
        with st.container(key="catalog_lab_topbar"):
            heading, tools = st.columns([5, 1.2])
            with heading:
                st.markdown("<div class='lab-heading'><div><div class='lab-kicker'>EXPERIMENT LAB / 实验工作区</div>"
                    "<h1>让算法想法，有一个起点。</h1>"
                    "<div class='lab-subtitle'>和 AI 梳理问题，自由装配组件，再用真实运行验证。</div></div></div>", unsafe_allow_html=True)
            with tools, st.container(key="catalog_lab_tools"):
                with st.popover("笔记与存档", icon=":material/folder_open:", width="stretch"):
                    st.markdown("**设计笔记与工作区**")
                    st.caption("三个步骤共用。记下已确认的设计，再下载工作区以便下次继续。")
                    st.text_area("已确认的设计笔记", key=_NOTES_KEY, height=160, max_chars=6000,
                                 placeholder="已确定的目标、算法行为、结构归属，以及待开发内容。")
                    workspace_tools = st.container()
        problem, assembly, trial = st.tabs(["1 · 定义问题", "2 · 装配算法", "3 · 运行结果"])
        with problem:
            with st.container(key="catalog_lab_problem_columns"):
                discussion, definition = st.columns([1.15, 1], gap="large")
                with discussion, st.container(key="catalog_lab_conversation"):
                    st.markdown("<div class='lab-panel-heading'><span class='lab-panel-icon'>✦</span><h2>一起想清楚</h2></div>"
                        "<div class='lab-panel-copy'>告诉 AI 你想解决什么，或者想怎样改造算法。</div>", unsafe_allow_html=True)
                    assistant_container = st.container()
                    connection_tools = st.container(key="catalog_lab_connection")
                with definition, st.container(key="catalog_lab_definition"):
                    st.markdown("<div class='lab-panel-heading'><span class='lab-panel-icon'>≡</span><h2>当前问题</h2></div>"
                        "<div class='lab-panel-copy'>这是下一次运行使用的定义，可以随时手动修改。</div>", unsafe_allow_html=True)
                    pending_problem = _render_problem_editor(st, draft)
                    with st.expander("使用内置演示问题", expanded=False):
                        st.caption("选择后会替换当前问题定义，请先保留需要的内容。")
                        presets = [row for row in metadata["components"]["problems"] if row["key"] != "problem.expression"]
                        by_key = {row["key"]: row for row in presets}
                        selected = draft["problem"]["component"]
                        chosen = st.selectbox("原始评估问题", list(by_key),
                            index=list(by_key).index(selected) if selected in by_key else 0,
                            format_func=lambda key: by_key[key]["label"], key=_key(st, "preset_problem"))
                        # Presets are explicit too: browsing choices cannot replace a user's formula.
                        if st.button("使用这个演示问题", key=_key(st, "load_preset_problem")):
                            draft["problem"] = {"component": chosen, "parameters": {}}
                            draft["dimension"] = max(2, int(draft["dimension"]))
                            draft["pipeline"]["initializer"] = {"component": "repr.uniform", "parameters": {"low": -2., "high": 2.}}
                            st.session_state[_DRAFT_KEY] = draft
                            st.session_state[_REVISION_KEY] = int(st.session_state.get(_REVISION_KEY, 0)) + 1
                            st.rerun()
                    st.markdown("<div class='lab-helper'>准备好后，进入「装配算法」选择搜索方式与执行顺序。</div>", unsafe_allow_html=True)
        with assembly:
            assembly_tools = st.columns(2)
            with assembly_tools[0]:
                with st.expander("AI 引导 · 选择算法与连接流程", expanded=False):
                    assembly_assistant = st.container()
            with assembly_tools[1]:
                with st.expander("从演示装配开始（会替换当前问题与算法）", expanded=False):
                    recipes = list(lab_project.list_recipes())
                    by_id = {row["id"]: row for row in recipes}
                    recipe = st.selectbox("载入一个配方作为起点", list(by_id),
                        format_func=lambda value: str(by_id[value]["title"]), key=_PREFIX + "recipe")
                    st.caption("切换下拉框不会覆盖当前装配。点击载入后才替换工作区；也会替换问题定义。")
                    if st.button("载入配方", key=_PREFIX + "load_recipe", width="stretch"):
                        _replace_draft(st, lab_assembly.assembly_from_recipe(recipe))
                        st.rerun()
            with st.expander("候选源与运行预算", expanded=False):
                fields = [(name, rule) for name, rule in metadata["common_parameters"].items() if name != "dimension"]
                columns = st.columns(3)
                for index, (name, rule) in enumerate(fields):
                    with columns[index % 3]:
                        draft[name] = _parameter(st, rule, draft.get(name, rule.get("default")), name=name)
                if draft["problem"]["component"] == "problem.expression":
                    st.caption(f"候选维度 {draft['dimension']}，由问题变量数量决定。初始解按每个变量范围采样。")
                else:
                    draft["dimension"] = _parameter(st, metadata["common_parameters"]["dimension"], draft["dimension"], name="dimension")
                st.caption("母池初始解数、Unit 成员数与运行预算分别配置。")
            _render_assembly(st, draft, metadata)
        # Persist every manual edit before computing digests or allowing an AI
        # apply action, including edits in the right-hand workspace.
        try:
            spec = lab_project.normalize_spec(draft)
        except (TypeError, ValueError) as exc:
            spec = None
            st.session_state[_DRAFT_KEY] = deepcopy(draft)
            st.error(f"请先调整装配参数：{exc}")
        else:
            st.session_state[_DRAFT_KEY] = deepcopy(spec)
        with trial:
            if spec is not None:
                _problem_summary(st, spec["problem"], dimension=spec["dimension"], title="本次准备运行")
            if st.session_state.get(_NOTES_KEY, "").strip():
                st.caption("本次运行以已装配组件和参数为准。设计笔记中的新算子、Unit 或插件需要完成实现与装配后才会生效。")
            if pending_problem:
                st.warning("请先在定义问题页应用或放弃尚未应用的问题修改。")
            _render_trial(st, None if pending_problem else spec, capabilities)
            with st.expander("AI 引导 · 解读运行、规划下一次实验", expanded=False):
                results_assistant = st.container()
            with st.expander("项目源码与导出", expanded=False):
                if spec is None:
                    st.info("装配通过校验后，这里会显示对应的标准 Project 与下载。")
                else:
                    _render_sources(st, spec)
    # Render after all editors: the base digest always includes this rerun's
    # latest manual changes, even though its containers appear earlier in tabs.
    with assistant_container:
        assistant_capabilities = _assistant_capabilities(st)
        _render_assistant(st, None if pending_problem else spec, stage="problem", capabilities=assistant_capabilities)
    with connection_tools:
        with st.popover("AI 连接", icon=":material/tune:"):
            st.caption("AI 依据当前框架契约与可用组件提供建议。设计笔记与近期对话在三个步骤之间共享。")
            if st.button("刷新 AI 连接", key=_PREFIX + "assistant_capabilities_refresh"):
                st.session_state.pop(_AI_CAPS_KEY, None)
                st.rerun()
    with assembly_assistant:
        _render_assistant(st, None if pending_problem else spec, stage="assembly", capabilities=assistant_capabilities)
    with results_assistant:
        _render_assistant(st, None if pending_problem else spec, stage="results", capabilities=assistant_capabilities)
    with workspace_tools:
        _render_workspace_transfer(st, spec)
        history = st.session_state.get(_HISTORY_KEY, [])
        if history:
            with st.expander("近期讨论（最多六条）", expanded=False):
                st.caption("近期讨论供 AI 理解上下文；需要长期保留的决定请写入设计笔记，并下载工作区。")
                for turn in history:
                    st.write("你" if turn["role"] == "user" else "AI")
                    st.code(turn["content"], language="text")


__all__ = ["render_workbench", "catalog_component_url"]
