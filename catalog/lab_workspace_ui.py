"""Local Project editing over immutable workspace revisions and formal trials.

Opening a workspace never builds a Solver, starts a trial or calls a model.
The local operator configures source roots; browser inputs are project handles.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import difflib
import hashlib
import html
import json
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath
from typing import Any
from uuid import uuid4


_PREFIX = "project_workspace::"
_DRAFTS = _PREFIX + "drafts"
_ACTIVE = frozenset({"queued", "running"})
_TEXT = frozenset({".py", ".md", ".json", ".toml"})
_SECTIONS = {"all": "全部代码", "algorithm": "搜索与编排", "problem": "问题与数据",
             "pipeline": "候选处理", "capability": "偏好与能力"}
_SECTION_HELP = {
    "algorithm": "查看实际装配、算法操作和 Project 编排。选择、变化与池交接都从对应实现进入。",
    "problem": "保留已有业务模型，查看目标、约束和数据。修改算法无需重新定义问题。",
    "pipeline": "查看候选初始化、变化与问题修复；Unit 由所属 Adapter 按需构建。",
    "capability": "查看软评分偏好、评估能力、日志与检查点的实际装配。",
    "all": "直接浏览这份工程的全部已登记文件，数据保持只读。",
}


def _version_label(revision: Mapping) -> str:
    return str(revision.get("message") or ("初始版本" if not revision.get("parent_revision") else "未命名修改"))


def _job_label(job: Mapping, revisions: Mapping) -> str:
    try:
        stamp = datetime.fromtimestamp(float(job["created_at"]), timezone(timedelta(hours=8))).strftime("%m-%d %H:%M:%S")
    except (ValueError, TypeError, OverflowError, KeyError):
        stamp = "实验"
    revision = revisions.get(job.get("revision_id"), {})
    return f"{stamp} · {job.get('case_name', '')} · {_version_label(revision)}"


def _read_file(st, store, wid, rid, path):
    # Immutable revisions can be cached by exact identity. Never cache drafts.
    scope = str(getattr(store, "root", "")) or f"store:{id(store)}"
    cache = st.session_state.setdefault(_PREFIX + "file_cache", {})
    identity = (scope, wid, rid, path)
    if identity not in cache:
        value = store.read_file(wid, rid, path)
        if len(cache) >= 24:
            cache.pop(next(iter(cache)))
        cache[identity] = value
    return cache[identity]


def _short(value: Any) -> str:
    return str(value or "")[:10]


def _draft(st, workspace: Mapping) -> dict:
    drafts = st.session_state.setdefault(_DRAFTS, {})
    wid, head = workspace["workspace_id"], workspace["head_revision"]
    current = drafts.get(wid)
    if current is None or (current["base_revision"] != head and not current["changes"]):
        current = {"base_revision": head, "changes": {}, "originals": {}}
        drafts[wid] = current
    return current


def _capture_edit(st, wid: str, path: str, widget_key: str) -> None:
    draft = st.session_state[_DRAFTS][wid]
    value = st.session_state[widget_key]
    if value == draft["originals"][path]:
        draft["changes"].pop(path, None)
    else:
        draft["changes"][path] = value


def _stage_editor_event(st, binding, payload):
    from nsgablack.catalog.lab_workspace_editor import (validate_editor_event, acknowledge_editor_event,
                                                       EditorEventError)
    try:
        event = validate_editor_event(payload, binding["identity"])
    except EditorEventError:
        return
    drafts = st.session_state.get(_DRAFTS, {})
    draft = drafts.get(binding["wid"])
    if (draft is None or draft["base_revision"] != binding["rid"] or
            st.session_state.get(_PREFIX + f"editor_epoch::{binding['wid']}", "initial") != binding["epoch"]):
        return
    seen = st.session_state.setdefault(_PREFIX + "editor_events", {})
    acknowledge_editor_event(st, key=binding["key"], identity=binding["identity"],
                             sequence=max(event["sequence"], seen.get(binding["identity"], 0)))
    if event["sequence"] <= seen.get(binding["identity"], 0):
        return
    path = binding["path"]
    if path not in draft["originals"]:
        return
    seen[binding["identity"]] = event["sequence"]
    if event["text"] == draft["originals"][path]:
        draft["changes"].pop(path, None)
    else:
        draft["changes"][path] = event["text"]
    if event["command"] == "save":
        st.session_state[_PREFIX + "keyboard_save"] = dict(binding)


def _capture_pending_editor(st):
    # The last blur message can arrive in the same request as a file switch or
    # Save. Capture its bound old file before mounting the next editor.
    binding = st.session_state.get(_PREFIX + "active_editor")
    if binding:
        payload = st.session_state.get(binding["key"])
        if payload is not None:
            _stage_editor_event(st, binding, payload)


def _open_file(st, wid, path, case_names, trigger_key=None):
    if trigger_key and st.session_state.get(trigger_key) is not True:
        return
    st.session_state[_PREFIX + f"open_file::{wid}"] = path
    st.session_state[_PREFIX + f"file::{wid}"] = path
    if path not in st.session_state.get(_PREFIX + f"file_scope_paths::{wid}", ()):
        st.session_state[_PREFIX + f"section::{wid}"] = "all"


def _focus_line(st, wid, path, line):
    st.session_state[_PREFIX + f"focus_line::{wid}"] = {"path": path, "line": line}
    st.session_state[_PREFIX + f"goto_line::{wid}"] = line


def _diff(path: str, before: str, after: str) -> str:
    return "".join(difflib.unified_diff(before.splitlines(keepends=True),
        after.splitlines(keepends=True), fromfile=f"已保存/{path}", tofile=f"草稿/{path}"))


def _error(st, exc: Exception) -> None:
    code = getattr(exc, "code", None)
    st.error(f"{str(exc)}" + (f"（{code}）" if code else ""))


def _jump_to_file(st, wid, path, case_names, line=None):
    st.session_state[_PREFIX + f"section::{wid}"] = "all"
    st.session_state[_PREFIX + f"panel::{wid}"] = None
    st.session_state[_PREFIX + f"file_filter::{wid}"] = ""
    st.session_state[_PREFIX + f"open_file::{wid}"] = path
    focus_key = _PREFIX + f"focus_line::{wid}"
    if type(line) is int and line > 0:
        st.session_state[focus_key] = {"path": path, "line": line}
        st.session_state[_PREFIX + f"goto_line::{wid}"] = line
    else:
        st.session_state.pop(focus_key, None)


def _selected_file_changed(st, wid, case_names):
    # File browsing is independent from the explicit execution target.
    # Keep a callback for queued editor events before the new file is mounted.
    _capture_pending_editor(st)


def _file_case(path, case_names):
    if not isinstance(path, str):
        return None
    parts = PurePosixPath(path).parts
    return parts[1] if len(parts) >= 3 and parts[0] == "cases" and parts[1] in case_names else None


def _set_run_target(st, wid, case, trigger):
    if st.session_state.get(trigger) is not True:
        return
    # Adopting this explicit target keeps the file/cursor being inspected.
    _capture_pending_editor(st)
    st.session_state[_PREFIX + f"case::{wid}"] = case


def _open_component_popup(st, path, trigger):
    if st.session_state.get(trigger) is not True:
        return
    _capture_pending_editor(st)
    from nsgablack.catalog.lab_workspace_reference_ui import request_reference_dialog
    request_reference_dialog(st, context=path)


def _show_run_result(st, wid, trigger):
    if st.session_state.get(trigger) is not True:
        return
    _capture_pending_editor(st)
    st.session_state[_PREFIX + f"panel::{wid}"] = "results"


def _browsing_scope(st, wid, path, case, case_names):
    viewed_case = _file_case(path, case_names)
    if viewed_case is None or viewed_case == case:
        return
    with st.container(key="workbench_scope_notice"):
        notice, action = st.columns([4, 1.4], gap="small")
        notice.caption(f"正在查看 {viewed_case} · 运行目标仍为 {case or '未选择'}")
        trigger = _PREFIX + f"use_file_case::{wid}"
        action.button("设为运行目标", key=trigger, use_container_width=True,
            help=f"将运行目标明确设为 {viewed_case}，不启动运行。",
            on_click=_set_run_target, args=(st, wid, viewed_case, trigger))


def _selected_case_changed(st, wid, case_names):
    case = st.session_state.get(_PREFIX + f"case::{wid}")
    if case in case_names:
        _jump_to_file(st, wid, f"cases/{case}/build_solver.py", case_names)
        st.session_state[_PREFIX + f"section::{wid}"] = "algorithm"


def _clear_file_filter(st, key):
    st.session_state[key] = ""


def _dismiss_position(st, key):
    st.session_state.pop(key, None)


def _toggle_panel(st, wid, panel):
    key = _PREFIX + f"panel::{wid}"
    target = None if st.session_state.get(key) == panel else panel
    if target == "run":
        from nsgablack.catalog.lab_workspace_parameter_ui import reopen_parameter_panel
        reopen_parameter_panel(st, wid, st.session_state.get(_PREFIX + f"case::{wid}"))
    st.session_state[key] = target


def _close_source_dialog(st):
    st.session_state[_PREFIX + "source_dialog"] = False


def _preserve_source_inputs(st):
    for key in (_PREFIX + "source", _PREFIX + "new_title"):
        if key in st.session_state:
            st.session_state[key] = st.session_state[key]


def _preserve_run_inputs(st, wid):
    exact = {_PREFIX + f"{name}::{wid}" for name in ("steps", "timeout", "seed")}
    for key in list(st.session_state):
        if key in exact:
            st.session_state[key] = st.session_state[key]


def _show_dialogs(st, store):
    from nsgablack.catalog.lab_workspace_reference_ui import reference_dialog_requested, open_reference_dialog
    if st.session_state.get(_PREFIX + "source_dialog"):
        @st.dialog("打开工程", width="large", on_dismiss=lambda: _close_source_dialog(st))
        def source_window():
            _new_workspace(st, store, expanded=True)
            if st.button("返回编辑", key=_PREFIX + "source_close"):
                _close_source_dialog(st)
                st.rerun()
        source_window()
    elif reference_dialog_requested(st):
        open_reference_dialog(st)


def _save_action(st, store, workspace, revision, draft, *, online=True):
    wid, rid = workspace["workspace_id"], revision["revision_id"]
    stale = draft["base_revision"] != workspace["head_revision"]
    clicked = st.button("保存", type="primary" if draft["changes"] else "secondary", icon=":material/save:",
                 key=_PREFIX + f"save::{wid}", use_container_width=True,
                 disabled=not online or not draft["changes"] or stale or rid != workspace["head_revision"])
    requested = st.session_state.pop(_PREFIX + "keyboard_save", None)
    shortcut = bool(requested and requested["wid"] == wid and requested["rid"] == rid
                    and requested["epoch"] == st.session_state.get(_PREFIX + f"editor_epoch::{wid}", "initial"))
    if (clicked or shortcut) and online and draft["changes"] and not stale and rid == workspace["head_revision"]:
        try:
            saved = store.save_files(wid, deepcopy(draft["changes"]), expected_revision=draft["base_revision"],
                message=st.session_state.get(_PREFIX + f"message::{wid}", ""))
        except (ValueError, OSError) as exc:
            _error(st, exc)
        else:
            st.session_state[_DRAFTS][wid] = {"base_revision": saved["revision_id"], "changes": {}, "originals": {}}
            st.session_state[_PREFIX + f"saved::{wid}"] = saved["revision_id"]
            st.rerun()


def _editor_tools(st, workspace, revision, draft, path):
    wid = workspace["workspace_id"]
    with st.container(key="workbench_editor_tools"):
        breadcrumb, locator, diff, more = st.columns([5, .85, .9, .85], gap="small")
    with breadcrumb:
        st.markdown("<div class='workbench-path'>" + html.escape(path or "选择文件") + "</div>",
                    unsafe_allow_html=True)
    with diff:
        with st.popover(f"差异 · {len(draft['changes'])}", use_container_width=True):
            if not draft["changes"]:
                st.caption("没有未保存修改。")
            for relative, content in sorted(draft["changes"].items()):
                st.code(_diff(relative, draft["originals"][relative], content), language="diff")
    with more:
        with st.popover("文件", use_container_width=True, help="编辑选项、修订说明和草稿管理"):
            st.checkbox("使用纯文本编辑", key=_PREFIX + f"plain_editor::{wid}",
                        help="只在需要兼容输入方式时切换；正常编辑使用带行号的代码编辑器。")
            st.text_input("修订说明", key=_PREFIX + f"message::{wid}", max_chars=300,
                          placeholder="保存时的说明（可选）")
            st.caption(_version_label(revision))
            st.json({"path": path, "revision_id": revision["revision_id"], "source_digest": revision["source_digest"]})
            stale = draft["base_revision"] != workspace["head_revision"]
            if st.button("放弃草稿并载入最新修订", key=_PREFIX + f"discard::{wid}", disabled=not draft["changes"] and not stale):
                st.session_state[_DRAFTS][wid] = {"base_revision": workspace["head_revision"], "changes": {}, "originals": {}}
                st.session_state[_PREFIX + f"editor_epoch::{wid}"] = uuid4().hex
                st.rerun()
    if draft["base_revision"] != workspace["head_revision"]:
        st.warning("另一个编辑已保存新版本。草稿保留，请先核对差异。")
    return locator


def _remember_run_input(st, wid, key, field):
    st.session_state[_PREFIX + f"run_preferences::{wid}"][field] = st.session_state[key]


def _new_workspace(st, store, *, expanded=False) -> None:
    with st.expander("从已有 Project 创建工作副本", expanded=expanded):
        st.caption("只读取登记的工程。修改保存到工作区，原 Project 和数据不会被覆盖。")
        # Browse directory metadata only, and only inside the requested dialog.
        # Creating a copy still verifies a fresh complete source snapshot.
        root = getattr(store, "root", None)
        scope = str(root.resolve()) if root is not None else f"store:{id(store)}"
        cache = st.session_state.setdefault(_PREFIX + "source_lists", {})
        refresh = st.button("刷新来源 Project", key=_PREFIX + f"refresh_sources::{scope}")
        if refresh or scope not in cache:
            try:
                cache[scope] = list(store.list_sources())
            except (ValueError, OSError) as exc:
                _error(st, exc)
                return
        sources = cache[scope]
        if not sources:
            st.info("尚未登记可打开的标准 Project，请在本机启动配置中指定项目来源。")
            return
        by_id = {row["project_id"]: row for row in sources}
        selected = st.selectbox("来源 Project", list(by_id),
            format_func=lambda key: f"{by_id[key].get('title', key)} · {key}", key=_PREFIX + "source")
        title = st.text_input("工作副本名称（可选）", max_chars=120, key=_PREFIX + "new_title")
        if st.button("创建工作副本", key=_PREFIX + "create", type="primary"):
            try:
                workspace = store.create_workspace(selected, title=title.strip() or None)
            except (ValueError, OSError) as exc:
                _error(st, exc)
            else:
                st.session_state[_PREFIX + "open_after_create"] = workspace["workspace_id"]
                st.session_state[_PREFIX + "source_dialog"] = False
                st.rerun()


def _file_navigation(st, store, workspace: Mapping, revision: Mapping, draft: dict,
                 *, paths=None, default_path=None) -> None:
    wid, rid = workspace["workspace_id"], revision["revision_id"]
    rows = {item["path"]: item for item in revision["files"]}
    case_names = _case_names(revision)
    names = sorted(rows) if paths is None else [path for path in paths if path in rows]
    filter_key = _PREFIX + f"file_filter::{wid}"
    query = st.text_input("查找工程文件", key=filter_key,
        placeholder="按文件名或路径找，如 composition、problem、config", max_chars=200).strip()
    if query:
        matches = [path for path in sorted(rows) if query.casefold() in path.casefold()]
        if matches:
            previous = st.session_state.get(_PREFIX + f"file::{wid}")
            names = ([previous] if previous in rows and previous not in matches else []) + matches
            st.caption(f"整个工程匹配 {len(matches)} 个文件；保留当前文件，选择匹配项后打开。")
        else:
            st.info("没有匹配文件，当前编辑位置保留。")
            st.button("清空文件搜索", key=_PREFIX + f"clear_filter::{wid}",
                      on_click=_clear_file_filter, args=(st, filter_key))
            previous = st.session_state.get(_PREFIX + f"file::{wid}")
            if previous in rows:
                names = [previous]
    # Responsibility tabs narrow navigation; they do not close the live file.
    wanted = st.session_state.pop(_PREFIX + f"open_file::{wid}", None)
    preserved = wanted if wanted in rows else st.session_state.get(_PREFIX + f"file::{wid}")
    if preserved in rows and preserved not in names:
        names = [preserved, *names]
    if not names:
        st.info("这个区域没有登记文件；可以从顶部切到“全部代码”。")
        return None
    file_key = _PREFIX + f"file::{wid}"
    if wanted in names:
        st.session_state[file_key] = wanted
    if st.session_state.get(file_key) not in names:
        st.session_state[file_key] = default_path if default_path in names else names[0]
    st.session_state[_PREFIX + f"file_scope_paths::{wid}"] = names
    with st.popover("快速打开文件", use_container_width=True, icon=":material/search:"):
        path = st.selectbox("工程文件", names, index=None, key=_PREFIX + f"file::{wid}",
                           on_change=_selected_file_changed, args=(st, wid, case_names))
    from nsgablack.catalog.lab_workspace_navigation import render_file_tree
    if draft["changes"]:
        with st.expander(f"未保存 · {len(draft['changes'])}", expanded=True):
            for target in draft["changes"]:
                st.button(str(PurePosixPath(target)), key=_PREFIX + f"dirty_file::{wid}::{target}",
                          use_container_width=True, type="tertiary", on_click=_jump_to_file,
                          args=(st, wid, target, case_names))
    render_file_tree(st, names, workspace_id=wid, current_path=path,
                     changed_paths=set(draft["changes"]), on_open=_open_file, case_names=case_names)
    recent_key = _PREFIX + f"recent_files::{wid}"
    recent = [value for value in st.session_state.get(recent_key, []) if value in rows and value != path]
    st.session_state[recent_key] = [path, *recent][:8]
    return path


def _render_code(st, store, workspace, revision, draft, *, path=None, height=560, location_slot=None):
    if path is None:
        st.info("从左侧选择文件开始编辑。")
        return
    wid, rid = workspace["workspace_id"], revision["revision_id"]
    row = next(item for item in revision["files"] if item["path"] == path)
    is_text = PurePosixPath(path).suffix.lower() in _TEXT or PurePosixPath(path).name == ".case"
    if not is_text:
        st.info("数据文件保持只读，沿用已保存的准确内容与摘要。")
        st.json({"path": path, "size_bytes": row["size_bytes"], "sha256": row["sha256"]})
    else:
        try:
            source = _read_file(st, store, wid, rid, path)
        except (ValueError, OSError) as exc:
            _error(st, exc)
            return
        current = rid == workspace["head_revision"]
        editable = bool(source.get("editable")) and current and draft["base_revision"] == rid
        from nsgablack.catalog.lab_workspace_review import review_source
        shown_source = draft["changes"].get(path, source["content"]) if editable else source["content"]
        outline = review_source(path, shown_source)
        import os
        plaintext = (os.environ.get("NSGABLACK_WORKSPACE_PLAINTEXT_EDITOR") == "1" or
                     st.session_state.get(_PREFIX + f"plain_editor::{wid}", False))
        focus_key = _PREFIX + f"focus_line::{wid}"
        focus = st.session_state.get(focus_key)
        if focus and focus["path"] == path:
            lines = shown_source.splitlines()
            line = focus["line"]
            st.caption(f"报错位置：{path} · L{line}")
            if plaintext and line <= len(lines):
                start, end = max(line - 3, 0), min(line + 3, len(lines))
                st.code("\n".join(f"{index + 1:>4}  {lines[index]}" for index in range(start, end)),
                        language="text", height=140)
            st.button("收起报错位置", key=_PREFIX + f"dismiss_position::{wid}",
                      on_click=_dismiss_position, args=(st, focus_key))
        if outline["calls"] or outline["symbols"]:
            with (location_slot if location_slot is not None else st.container()), st.popover(
                    "定位", help="查看函数与装配调用的位置", use_container_width=True):
                st.caption("下面是当前源码中的定义与调用位置；是否实际执行仍由装配和运行决定。")
                for call in outline["calls"][:16]:
                    st.write(f"L{call['line']} · {call['name']} · {call['role']}")
                for symbol in outline["symbols"][:16]:
                    st.write(f"L{symbol['line']} · {symbol['name']}")
                locations = sorted([*outline["calls"], *outline["symbols"]], key=lambda item: item["line"])
                if locations:
                    selected = st.selectbox("查看附近代码", list(range(len(locations))),
                        format_func=lambda index: f"L{locations[index]['line']} · {locations[index]['name']}",
                        key=_PREFIX + f"location::{wid}::{rid}::{path}::{hashlib.sha256(shown_source.encode()).hexdigest()[:10]}")
                    position = locations[selected]
                    lines = shown_source.splitlines()
                    start = max(position["line"] - 3, 0)
                    end = min(position.get("end_line", position["line"]) + 2, start + 45, len(lines))
                    st.caption(f"当前文件 L{start + 1}–L{end}")
                    st.code("\n".join(lines[start:end]), language="python")
        if plaintext and outline.get("syntax_ok") is False:
            for diagnostic in outline["diagnostics"]:
                st.warning(f"草稿语法 L{diagnostic.get('line', '?')}：{diagnostic['message']}")
        if editable:
            draft["originals"].setdefault(path, source["content"])
            epoch = st.session_state.get(_PREFIX + f"editor_epoch::{wid}", "initial")
            widget_key = _PREFIX + f"editor::{wid}::{rid}::{epoch}::{path}"
            if plaintext:
                st.session_state.pop(_PREFIX + "active_editor", None)
                st.text_area("文件内容", value=draft["changes"].get(path, source["content"]),
                    height=height, key=widget_key, on_change=_capture_edit, args=(st, wid, path, widget_key))
            else:
                from nsgablack.catalog.lab_workspace_editor import render_code_editor
                binding = {"wid": wid, "rid": rid, "path": path, "epoch": epoch,
                           "identity": widget_key, "key": widget_key}
                st.session_state[_PREFIX + "active_editor"] = binding
                markers = [{"line": item["line"], "column": item.get("column") or 1,
                            "severity": "error", "message": item["message"]}
                           for item in outline["diagnostics"] if type(item.get("line")) is int]
                language = {".py": "python", ".json": "json", ".md": "markdown", ".toml": "toml"}.get(PurePosixPath(path).suffix, "text")
                event = render_code_editor(st, value=shown_source, identity=widget_key, key=widget_key,
                    height=height, language=language, diagnostics=markers,
                    theme=st.session_state.get(_PREFIX + "appearance", "dark"),
                    goto_line=st.session_state.pop(_PREFIX + f"goto_line::{wid}", None))
                if event:
                    _stage_editor_event(st, binding, event)
        else:
            if not current:
                st.caption("历史版本 · 只读，切回最新版本可继续编辑。")
            language = {".py": "python", ".json": "json", ".toml": "toml", ".md": "markdown"}.get(
                PurePosixPath(path).suffix, "text")
            st.code(source["content"], language=language, line_numbers=True, height=height)
        return outline

def _case_names(revision: Mapping) -> list[str]:
    files = {item["path"] for item in revision["files"]}
    return sorted({PurePosixPath(path).parts[1] for path in files
        if len(PurePosixPath(path).parts) == 3 and path.startswith("cases/")
        and path.endswith("/build_solver.py")
        and str(PurePosixPath(path).parent / "run_solver.py") in files})


def _parameter_options(st, runtime, workspace, revision, case):
    from nsgablack.catalog.lab_workspace_parameter_ui import render_parameter_options
    return render_parameter_options(st, runtime, workspace, revision, case)


def _options(st, runtime, workspace: Mapping, revision: Mapping, *, case=None) -> tuple[str | None, dict | None]:
    wid = workspace["workspace_id"]
    cases = _case_names(revision)
    if not cases:
        st.warning("本修订没有可运行的标准 Case；需要 build_solver.py 和 run_solver.py。")
        return None, None
    if case is None:
        case = st.selectbox("运行 Case", cases, key=_PREFIX + f"case::{wid}")
    parameters = _parameter_options(st, runtime, workspace, revision, case)
    preferences = st.session_state.setdefault(_PREFIX + f"run_preferences::{wid}",
        {"max_steps": 2, "timeout_seconds": 60, "seed": 42})
    step_key = _PREFIX + f"steps::{wid}"
    steps = st.number_input("逻辑步预算", min_value=1, max_value=32, value=preferences["max_steps"], step=1,
        key=step_key, on_change=_remember_run_input, args=(st, wid, step_key, "max_steps"))
    with st.expander("时间与随机种子", expanded=False):
        timeout_key, seed_key = _PREFIX + f"timeout::{wid}", _PREFIX + f"seed::{wid}"
        timeout = st.number_input("超时（秒）", min_value=5, max_value=180, value=preferences["timeout_seconds"], step=5,
            key=timeout_key, on_change=_remember_run_input, args=(st, wid, timeout_key, "timeout_seconds"))
        seed = st.number_input("随机种子", min_value=0, max_value=2147483647, value=preferences["seed"], step=1,
            key=seed_key, on_change=_remember_run_input, args=(st, wid, seed_key, "seed"))
    return case, (None if parameters is None else {"parameters": parameters, "max_steps": int(steps),
                  "timeout_seconds": int(timeout), "seed": int(seed)})


def _render_run(st, runtime, workspace: Mapping, revision: Mapping, draft: Mapping, *, case=None) -> None:
    wid, rid = workspace["workspace_id"], revision["revision_id"]
    st.markdown("**运行当前 Case**")
    st.caption(f"{_version_label(revision)} · 单 CPU 线程 / 无 GPU")
    with st.container(key="workbench_run_actions"):
        check, run = st.columns([1, 1.3])
    case, options = _options(st, runtime, workspace, revision, case=case)
    if not case:
        return
    dirty = bool(draft["changes"])
    signature = (hashlib.sha256(json.dumps({"revision_id": rid, "case": case, **options},
        sort_keys=True, allow_nan=False).encode()).hexdigest() if options is not None else None)
    if dirty:
        st.warning("仍有未保存修改，请先保存或放弃草稿，再校验和运行。")
    st.caption("当前入口运行选定 Case，最多 32 个提交步、180 秒。跨 Case 依赖仍需完整 Project 编排。")
    with check:
        if st.button("静态校验", key=_PREFIX + f"check::{wid}", disabled=dirty or options is None):
            try:
                checked = runtime.runner.check(wid, rid, case, **options)
            except (ValueError, OSError) as exc:
                _error(st, exc)
            else:
                st.session_state[_PREFIX + f"check_result::{wid}"] = {
                    "revision_id": rid, "signature": signature, "result": checked}
    with run:
        if st.button("开始试跑", type="primary", key=_PREFIX + f"run::{wid}",
                     disabled=dirty or options is None):
            intent_key = _PREFIX + f"run_intent::{wid}"
            intent = st.session_state.get(intent_key)
            if not intent or intent["signature"] != signature:
                intent = {"signature": signature, "request_id": uuid4().hex}
                st.session_state[intent_key] = intent
            try:
                job = runtime.runner.submit(wid, rid, case, request_id=intent["request_id"], **options)
            except (ValueError, OSError) as exc:
                _error(st, exc)
            else:
                st.session_state[_PREFIX + f"job::{wid}"] = job["job_id"]
                st.session_state[_PREFIX + f"history::{wid}::{job['job_id']}"] = job["job_id"]
                st.session_state[_PREFIX + f"last_submission::{wid}"] = _run_status_record(job)
                st.session_state[_PREFIX + f"submitted_notice::{wid}"] = case
                st.session_state.pop(intent_key, None)
                st.rerun()
    previous = st.session_state.get(_PREFIX + f"check_result::{wid}")
    if previous:
        checked = previous["result"]
        if dirty or previous.get("signature") != signature:
            st.warning("下方校验只覆盖已保存版本，不覆盖当前未保存草稿。" if dirty
                else "下方校验属于另一个修订或运行配置，不代表当前选择已经通过。")
            st.caption(f"旧配置 · 修订 {_short(previous['revision_id'])}：" +
                       ("静态校验通过" if checked.get("ok") else "静态校验未通过"))
        else:
            (st.success if checked.get("ok") else st.error)(
                f"修订 {_short(previous['revision_id'])}：静态校验通过" if checked.get("ok")
                else f"修订 {_short(previous['revision_id'])}：静态校验未通过")
        for diagnostic in checked.get("diagnostics", []):
            if isinstance(diagnostic, Mapping):
                prefix = str(diagnostic.get("path") or "")
                if diagnostic.get("line"):
                    prefix += f":{diagnostic['line']}"
                st.write(f"{prefix} {diagnostic.get('message', diagnostic.get('code', ''))}".strip())
                target = str(diagnostic.get("path") or "")
                if target in {row["path"] for row in revision["files"]}:
                    st.button(f"打开 {PurePosixPath(target).name}",
                        key=_PREFIX + f"diagnostic::{wid}::{hashlib.sha256((target + str(diagnostic)).encode()).hexdigest()[:12]}",
                        help=f"{target}" + (f" · L{diagnostic['line']}" if diagnostic.get("line") else ""),
                        disabled=dirty or previous.get("signature") != signature,
                        on_click=_jump_to_file, args=(st, wid, target, _case_names(revision), diagnostic.get("line")))


def _run_status_record(job):
    # The compact strip holds identity/status only. Results and logs load when
    # explicitly opened; no large output is copied into the editor's state.
    return {key: job[key] for key in ("job_id", "workspace_id", "revision_id", "case_name", "status")}


def _render_recent_run(st, runtime, workspace, *, case=None, online=True, draft=None):
    wid = workspace["workspace_id"]
    slot = _PREFIX + f"last_submission::{wid}"
    record = st.session_state.get(slot)
    if not record or (case is not None and record["case_name"] != case):
        return

    @st.fragment(run_every="2s" if online and record["status"] in _ACTIVE else None)
    def status_strip():
        current = st.session_state[slot]
        was_active = current["status"] in _ACTIVE
        if online and was_active:
            try:
                updated = runtime.runner.get_job(wid, current["job_id"])
                if any(updated.get(key) != current[key] for key in
                       ("job_id", "workspace_id", "revision_id", "case_name")):
                    raise ValueError("运行记录身份不一致，未更新本次状态。")
                current = _run_status_record(updated)
                st.session_state[slot] = current
            except (ValueError, OSError) as exc:
                _error(st, exc)
        with st.container(key="workbench_run_status"):
            message, action = st.columns([4, 1.2], gap="small")
            with message:
                status = current["status"]
                if status == "succeeded":
                    st.success(f"Case 试跑完成 · {current['case_name']}")
                elif status in _ACTIVE:
                    st.info(f"{current['case_name']} · " + ("排队中" if status == "queued" else "运行中 · 可以继续编辑"))
                else:
                    st.warning(f"{current['case_name']} · 本次运行未成功，打开记录查看原因。")
                label = ("当前保存版本" if current["revision_id"] == workspace["head_revision"]
                         else "旧版本，未验证新草稿")
                if draft and draft["changes"]:
                    label += " · 未覆盖未保存草稿"
                st.caption(f"运行修订 {_short(current['revision_id'])} · " + label)
            trigger = _PREFIX + f"latest_result::{wid}"
            action.button("查看本次结果", key=trigger, use_container_width=True, disabled=not online,
                on_click=_show_run_result, args=(st, wid, trigger))
        if was_active and current["status"] not in _ACTIVE:
            # Rebuild the fragment once to stop the active-job polling clock.
            st.rerun()
    status_strip()


def _render_job(st, runtime, workspace: Mapping, job: Mapping, *, baseline=None, revisions=None) -> None:
    from nsgablack.catalog.lab_workspace_results import describe_result, compare_experiments
    wid, job_id = workspace["workspace_id"], job["job_id"]
    try:
        current = runtime.runner.get_job(wid, job_id)
    except (ValueError, OSError) as exc:
        _error(st, exc)
        return
    rid = current["revision_id"]
    st.caption(_job_label(current, revisions or {}))
    if rid != workspace["head_revision"]:
        st.warning("这是旧修订的实验记录，保留原始结果；不代表最新代码的运行结果。")
    status = current["status"]
    described = describe_result(current)
    if status in _ACTIVE:
        st.info("本机 Case 试跑正在排队。" if status == "queued" else "本机 Case 正在运行，可以继续编辑下一份修订。")
    elif described["succeeded"]:
        st.success("Case 试跑完成；查看原始目标、约束与本次运行记录。")
    else:
        error = current.get("error") or (current.get("result") or {}).get("error") or {}
        st.error(str(error.get("message", "本次运行未成功；记录保留，不自动重跑。")))
    result = current.get("result") or {}
    columns = st.columns(3)
    for column, measure in zip(columns, described["measures"]):
        value = measure["value"]
        shown = f"{value:.2f} s" if measure["unit"] in {"s", "秒"} and isinstance(value, (int, float)) else (value if value is not None else "—")
        column.metric(measure["label"], shown)
    if described["metric_rows"]:
        st.markdown("**业务指标**")
        st.dataframe([{"指标": row["label"], "本次结果": row["value"]} for row in described["metric_rows"]],
                     hide_index=True, width="stretch")
    if described["raw_rows"]:
        st.markdown("**候选与原始评估**")
        st.caption(described["scope_label"])
        rows = []
        for row in described["raw_rows"]:
            candidate = json.dumps(row["candidate"], ensure_ascii=False)
            rows.append({"候选": candidate if len(candidate) <= 160 else candidate[:157] + "…",
                         "原始目标": row["raw_objectives"], "原始违反量": row["raw_violation"]})
        if rows:
            st.dataframe(rows, hide_index=True, width="stretch")
    for warning in described["warnings"]:
        st.warning(warning)
    if described["missing_evidence"]:
        st.caption("结果解读范围：" + "；".join(described["missing_evidence"]))
    if baseline is not None:
        comparison = compare_experiments(current, baseline)
        st.markdown("**与对照实验相比**")
        if not comparison["can_compare"]:
            for reason in comparison["reasons"]:
                st.info(reason)
        else:
            st.caption(comparison["data_label"])
            changed = [row for row in comparison["configuration_rows"] if row["changed"]]
            if changed:
                st.dataframe([{"配置": row["label"], "对照": json.dumps(row["baseline"], ensure_ascii=False),
                    "本次": json.dumps(row["current"], ensure_ascii=False)} for row in changed],
                    hide_index=True, width="stretch")
            values = comparison["measure_rows"] + comparison["metric_rows"]
            if values:
                st.dataframe([{"指标": row["label"], "对照": row["baseline"], "本次": row["current"],
                               "变化": row["delta"]} for row in values], hide_index=True, width="stretch")
            for notice in comparison["notices"]:
                st.caption(notice)
    if result.get("metrics"):
        with st.expander("业务指标与约束报告", expanded=False):
            st.json(result["metrics"])
    if result.get("logs"):
        with st.expander("运行日志", expanded=False):
            st.code(str(result["logs"])[-24000:], language="text")
    with st.expander("修订、配置与正式运行依据", expanded=False):
        displayed = deepcopy(current)
        archive = (displayed.get("result") or {}).get("artifact_archive")
        if isinstance(archive, dict):
            archive.pop("base64", None)
        st.json(displayed)
    st.download_button("下载本次实验记录", json.dumps(current, ensure_ascii=False, indent=2),
        file_name=f"workspace-{_short(wid)}-{job_id}.json", mime="application/json",
        key=_PREFIX + f"download::{job_id}", on_click="ignore")
    if job.get("status") in _ACTIVE and status not in _ACTIVE:
        st.rerun()


def _render_history(st, runtime, workspace: Mapping, *, revisions=None, case=None) -> None:
    wid = workspace["workspace_id"]
    revisions = revisions or {}
    st.markdown("<div class='project-panel-heading'>实验结果</div>", unsafe_allow_html=True)
    st.markdown("<div id='project-workspace-results'></div>", unsafe_allow_html=True)
    st.button("刷新实验记录", key=_PREFIX + f"refresh::{wid}")
    try:
        jobs = [job for job in runtime.runner.list_jobs(wid)
                if case is None or job.get("case_name") == case]
    except (ValueError, OSError) as exc:
        _error(st, exc)
        return
    if not jobs:
        st.info("这个 Case 还没有实验记录。保存改动后，打开顶部“试跑设置”，结果会保存在这里。")
        return
    labels = {"queued": "排队", "running": "运行中", "succeeded": "成功", "failed": "失败", "interrupted": "已中断"}
    by_id = {row["job_id"]: row for row in jobs}
    preferred = st.session_state.get(_PREFIX + f"job::{wid}")
    ids = list(by_id)
    default = ids.index(preferred) if preferred in by_id else 0
    history_key = _PREFIX + f"history::{wid}::{preferred or 'browse'}"
    if st.session_state.get(history_key) not in by_id:
        st.session_state[history_key] = ids[default]
    selected = st.selectbox("查看实验记录", ids, index=None,
        # Widget option labels stay stable while a job progresses. Dynamic
        # status belongs to the live table/detail, not a cached selection label.
        format_func=lambda identity: _job_label(by_id[identity], revisions),
        key=history_key)
    job = by_id[selected]
    others = [identity for identity in ids if identity != selected]
    base_id = st.selectbox("对照实验", [None, *others],
        format_func=lambda identity: "暂不对照" if identity is None else _job_label(by_id[identity], revisions),
        key=_PREFIX + f"baseline::{wid}::{selected}")
    baseline = None
    if base_id is not None:
        try:
            baseline = runtime.runner.get_job(wid, base_id)
        except (ValueError, OSError) as exc:
            _error(st, exc)
    with st.expander("全部实验记录", expanded=False):
        st.dataframe([{"实验": _job_label(row, revisions), "状态": labels.get(row["status"], row["status"]),
            "逻辑步": (row.get("result") or {}).get("steps"),
            "评估次数": (row.get("result") or {}).get("evaluations")} for row in jobs],
            hide_index=True, width="stretch")
    @st.fragment(run_every="2s" if job["status"] in _ACTIVE else None)
    def current_job():
        _render_job(st, runtime, workspace, job, baseline=baseline, revisions=revisions)
    current_job()


def _file_tabs(st, wid, path, draft, cases):
    from nsgablack.catalog.lab_workspace_navigation import file_tab_label
    values = st.session_state.get(_PREFIX + f"recent_files::{wid}", [])[:5]
    if not values:
        return
    with st.container(key="workbench_file_tabs"):
        for column, target in zip(st.columns(len(values), gap="small"), values):
            trigger = _PREFIX + f"tab::{wid}::{target}"
            column.button(file_tab_label(target, target in draft["changes"]), key=trigger,
                help=target, use_container_width=True, type="primary" if target == path else "tertiary",
                on_click=_open_file, args=(st, wid, target, cases, trigger))


def _open_reference_for(st, wid, query):
    prefix = _PREFIX + "reference::"
    st.session_state[prefix + "query"] = query
    st.session_state[prefix + "last_query"] = query
    st.session_state.pop(prefix + "selected", None)
    st.session_state[_PREFIX + f"panel::{wid}"] = "reference"


def _replace_draft(st, wid, path, content):
    draft = st.session_state[_DRAFTS][wid]
    if content == draft["originals"][path]:
        draft["changes"].pop(path, None)
    else:
        draft["changes"][path] = content
    st.session_state[_PREFIX + f"editor_epoch::{wid}"] = uuid4().hex
    st.session_state.pop(_PREFIX + "active_editor", None)
    st.session_state.pop(_PREFIX + "keyboard_save", None)


def _apply_review_fix(st, wid, path, fix, trigger):
    if st.session_state.get(trigger) is not True:
        return
    from nsgablack.catalog.lab_workspace_review import apply_source_fix
    _capture_pending_editor(st)
    draft = st.session_state[_DRAFTS][wid]
    content = draft["changes"].get(path, draft["originals"].get(path, ""))
    try:
        changed = apply_source_fix(content, fix)
    except ValueError as exc:
        st.session_state[_PREFIX + f"review_error::{wid}"] = str(exc)
        return
    st.session_state[_PREFIX + f"last_fix::{wid}"] = {"path": path, "before": content, "after": changed}
    _replace_draft(st, wid, path, changed)


def _undo_review_fix(st, wid, trigger):
    if st.session_state.get(trigger) is not True:
        return
    _capture_pending_editor(st)
    draft = st.session_state[_DRAFTS][wid]
    last = st.session_state.get(_PREFIX + f"last_fix::{wid}")
    if last is None:
        return
    content = draft["changes"].get(last["path"], draft["originals"].get(last["path"]))
    if content != last["after"]:
        st.session_state[_PREFIX + f"review_error::{wid}"] = "草稿已改变，未覆盖新的编辑。"
        return
    _replace_draft(st, wid, last["path"], last["before"])
    st.session_state.pop(_PREFIX + f"last_fix::{wid}", None)


def _render_review(st, workspace, revision, draft, path):
    from nsgablack.catalog.lab_workspace_review import review_source
    wid = workspace["workspace_id"]
    error = st.session_state.pop(_PREFIX + f"review_error::{wid}", None)
    if error:
        st.error(error)
    if path not in draft["originals"]:
        st.info("选择一个当前版本的可编辑源码文件，再检查草稿。")
        return
    content = draft["changes"].get(path, draft["originals"][path])
    review = review_source(path, content)
    if review["syntax_ok"] is True:
        st.success("Python 语法检查通过")
    elif review["syntax_ok"] is None:
        st.info("此文件没有进行 Python 语法检查。")
    for number, item in enumerate(review["diagnostics"]):
        st.error(f"L{item.get('line') or '?'} · {item['message']}")
        if type(item.get("line")) is int:
            st.button("定位到这一行", key=_PREFIX + f"review_line::{wid}::{number}",
                on_click=_focus_line, args=(st, wid, path, item["line"]), icon=":material/my_location:")
    for number, fix in enumerate(review["fixes"]):
        st.markdown("**建议修复 · " + fix["title"] + "**")
        st.code(fix["diff"], language="diff")
        trigger = _PREFIX + f"apply_fix::{wid}::{number}"
        st.button("应用到草稿", key=trigger, type="primary",
                  on_click=_apply_review_fix, args=(st, wid, path, fix, trigger))
    last = st.session_state.get(_PREFIX + f"last_fix::{wid}")
    if last and last["path"] == path and content == last["after"]:
        st.caption("修复已放入草稿，尚未保存或运行。")
        trigger = _PREFIX + f"undo_fix::{wid}"
        st.button("撤销这次修复", key=trigger, on_click=_undo_review_fix, args=(st, wid, trigger))
    st.caption(review["scope_note"])
    if review["calls"]:
        st.markdown("**组件与装配线索**")
        for index, call in enumerate(review["calls"][:16]):
            left, right = st.columns([3, 1])
            with left:
                st.caption(f"L{call['line']} · {call['role']}")
                st.write(call["name"])
            with right:
                st.button("用法", key=_PREFIX + f"review_reference::{wid}::{index}",
                    on_click=_open_reference_for, args=(st, wid, call["name"].rsplit(".", 1)[-1]))
    else:
        st.caption("本文件未发现已登记的装配调用线索；组件也可能在其他工厂文件中。")
    st.divider()
    st.caption("正式校验针对已保存修订；实际装配与算法结果仍由 Case 运行确认。")
    st.button("打开正式校验", key=_PREFIX + f"review_formal::{wid}", use_container_width=True,
              on_click=_toggle_panel, args=(st, wid, "run"))


def render_workspace(st: Any, runtime=None, *, hosted: bool = False) -> None:
    """Editor first. Source browsing, parameters and results load on demand."""
    _capture_pending_editor(st)
    from nsgablack.catalog.lab_workspace_reference_ui import keep_reference_inputs
    keep_reference_inputs(st)
    # Preserve absent controls before any widgets are instantiated.
    previous_wid = st.session_state.get(_PREFIX + "workspace")
    if previous_wid and st.session_state.get(_PREFIX + f"panel::{previous_wid}") != "run":
        _preserve_run_inputs(st, previous_wid)
    if not st.session_state.get(_PREFIX + "source_dialog"):
        _preserve_source_inputs(st)
    from nsgablack.catalog.lab_workspace_style import THEMES, workspace_styles
    from nsgablack.catalog.lab_workspace_project import project_outline
    from nsgablack.catalog.lab_workspace import REMOTE_ENV
    import os
    appearance_key = _PREFIX + "appearance"
    if st.session_state.get(appearance_key) not in THEMES:
        st.session_state[appearance_key] = "dark"
    st.markdown(workspace_styles(st.session_state[appearance_key]), unsafe_allow_html=True)
    remote_configured = bool(os.environ.get(REMOTE_ENV, "").strip())
    if hosted and not remote_configured and getattr(runtime, "mode", None) != "remote":
        st.info("工程工作区尚未配置本机连接。")
        return
    if runtime is None:
        try:
            from nsgablack.catalog.lab_workspace import get_workspace_runtime
            runtime = get_workspace_runtime()
        except (ValueError, OSError) as exc:
            _error(st, exc)
            return
    if hosted and getattr(runtime, "mode", None) != "remote":
        st.error("托管界面不能在网页服务内执行工程。")
        return
    if runtime is None:
        st.info("请先配置工程来源与本机运行器。")
        return
    store = runtime.store
    scope = str(getattr(store, "root", "")) or str(id(store))
    cache = st.session_state.setdefault(_PREFIX + "metadata", {})
    snapshot = cache.setdefault(scope, {"workspaces": [], "workspace": {}, "revisions": {}})
    online = True
    try:
        workspaces = list(store.list_workspaces())
        snapshot["workspaces"] = workspaces
    except (ValueError, OSError):
        workspaces, online = snapshot["workspaces"], False

    with st.sidebar:
        brand, appearance = st.columns([2, 1.4], gap="small")
        with brand:
            st.markdown("<div class='workbench-brand'><span>N</span> PROJECT LAB</div>", unsafe_allow_html=True)
        with appearance, st.popover("界面", icon=":material/contrast:", help="调整整个工作区与代码编辑器的主题"):
            st.selectbox("界面主题", THEMES, key=appearance_key,
                format_func={"dark": "深色", "light": "浅色", "system": "跟随系统"}.get)
            st.caption("切换主题保留代码、光标、草稿与当前工具。")
        if st.button("打开工程", key=_PREFIX + "open_source", use_container_width=True, icon=":material/create_new_folder:", disabled=not online):
            st.session_state[_PREFIX + "source_dialog"] = True
        if not workspaces:
            st.caption("还没有工作副本" if online else "本机未连接")
        else:
            by_id = {row["workspace_id"]: row for row in workspaces}
            preferred = st.session_state.pop(_PREFIX + "open_after_create", None)
            if preferred in by_id:
                st.session_state[_PREFIX + "workspace"] = preferred
            if st.session_state.get(_PREFIX + "workspace") not in by_id:
                st.session_state[_PREFIX + "workspace"] = next(iter(by_id))
            wid = st.selectbox("工作副本", list(by_id),
                format_func=lambda identity: by_id[identity]["title"], index=None, key=_PREFIX + "workspace")
    if not workspaces:
        st.markdown("<div class='workbench-empty'><h2>从你的 Project 开始</h2>"
                    "<p>打开已有工程，在工作副本中编辑、检查和验证算法。</p></div>", unsafe_allow_html=True)
        if st.button("选择一个工程", type="primary", key=_PREFIX + "welcome_open", disabled=not online):
            st.session_state[_PREFIX + "source_dialog"] = True
        if not online:
            st.warning("本机暂不可连接，恢复连接后重试。")
        _show_dialogs(st, store)
        return
    try:
        workspace = store.get_workspace(wid)
        snapshot["workspace"][wid] = workspace
    except (ValueError, OSError):
        workspace = snapshot["workspace"].get(wid)
        online = False
    if workspace is None:
        st.warning("本机连接中断，尚无这个工程的缓存。")
        return
    head = workspace["head_revision"]
    revision_key = (wid, head)
    if revision_key not in snapshot["revisions"]:
        try:
            snapshot["revisions"][revision_key] = list(store.list_revisions(wid))
            if len(snapshot["revisions"]) > 12:
                snapshot["revisions"].pop(next(iter(snapshot["revisions"])))
        except (ValueError, OSError):
            st.warning("当前版本暂不可读取，已有草稿仍保留。")
            return
    revisions = snapshot["revisions"][revision_key]
    revision_by_id = {item["revision_id"]: item for item in revisions}
    draft = _draft(st, workspace)
    nav = st.sidebar.container()
    with nav:
        st.caption("● 本机已连接" if online else "○ 本机离线 · 草稿保留")
        ids = [head, *[identity for identity in revision_by_id if identity != head]]
        with st.popover("版本历史", use_container_width=True, icon=":material/history:"):
            rid = st.selectbox("工程修订", ids,
                format_func=lambda identity: ("最新 · " if identity == head else "历史 · ") +
                    _version_label(revision_by_id[identity]), key=_PREFIX + f"revision::{wid}::{head}")
            st.caption(workspace["source_project_id"])
        revision = revision_by_id[rid]
        outline = project_outline(revision)
        cases = outline["case_names"]
        case_key = _PREFIX + f"case::{wid}"
        if cases and st.session_state.get(case_key) not in cases:
            st.session_state[case_key] = cases[0]
        case = st.selectbox("运行 Case", cases, index=None, key=case_key,
            on_change=_selected_case_changed, args=(st, wid, cases)) if cases else None

    panel_key = _PREFIX + f"panel::{wid}"
    panel = st.session_state.get(panel_key)
    with st.container(key="workbench_toolbar"):
        title, save, review, lookup, run, history = st.columns([3, .85, .85, 1, 1.15, 1.1], gap="small")
    section_key = _PREFIX + f"section::{wid}"
    if st.session_state.get(section_key) not in _SECTIONS:
        st.session_state[section_key] = "all"
    with st.container(key="workbench_categories"):
        section = st.radio("文件范围", list(_SECTIONS), format_func=_SECTIONS.get, horizontal=True,
                           key=section_key, index=None, label_visibility="collapsed") or "all"
    case_info = next((item for item in outline["cases"] if item["name"] == case), None)
    paths = (next((group["paths"] for group in case_info["groups"] if group["id"] == section), [])
             if case_info and section != "all" else outline["all_paths"])
    if section == "algorithm":
        paths = list(dict.fromkeys([*(paths or []), *outline["project_paths"]]))
    with nav:
        st.markdown("<div class='explorer-heading'>工程文件</div>", unsafe_allow_html=True)
        path = _file_navigation(st, store, workspace, revision, draft, paths=paths,
            default_path=case_info["build_path"] if case_info else None)
        if hosted:
            with st.popover("帮助与资料", use_container_width=True):
                st.link_button("完整组件目录", "/apps/framework-catalog/", use_container_width=True)
                st.caption("代码和数据在本机，工程访问仅限 simon。")
    saved = st.session_state.pop(_PREFIX + f"saved::{wid}", None)
    if saved == head:
        st.toast("已保存")
    submitted_case = st.session_state.pop(_PREFIX + f"submitted_notice::{wid}", None)
    if submitted_case:
        st.toast(f"已提交 {submitted_case} · 可以继续编辑，下方可查看本次运行。")
    if not online:
        st.warning("本机暂时离线。可以继续编辑已载入文件；保存和试跑在重连后恢复。")
    _browsing_scope(st, wid, path, case, cases)
    _file_tabs(st, wid, path, draft, cases)
    if panel == "results":
        with st.container(key="workbench_results"):
            if st.button("返回代码", key=_PREFIX + f"back_to_code::{wid}", icon=":material/arrow_back:"):
                st.session_state[panel_key] = None
                st.rerun()
            if online:
                _render_history(st, runtime, workspace, revisions=revision_by_id, case=case)
            else:
                st.info("连接恢复后可读取实验记录，草稿仍然保留。")
    else:
        panes = st.columns([3.6, 1.7], gap="medium") if panel in {"run", "review", "reference"} else [st.container()]
        with panes[0], st.container(key="project_workspace_editor"):
            location_slot = _editor_tools(st, workspace, revision, draft, path)
            _render_code(st, store, workspace, revision, draft, path=path, height=620, location_slot=location_slot)
        if len(panes) > 1:
            with panes[1], st.container(key="workbench_inspector"):
                heading, close = st.columns([4, 1])
                with heading:
                    st.markdown("### " + {"run": "运行配置", "review": "代码审查", "reference": "组件速查"}[panel])
                with close, st.container(key="workbench_inspector_close"):
                    if st.button("关闭", key=_PREFIX + f"close_panel::{wid}", icon=":material/close:", help="收起右侧工具"):
                        st.session_state[panel_key] = None
                        st.rerun()
                if panel == "run":
                    if online:
                        _render_run(st, runtime, workspace, revision, draft, case=case)
                    else:
                        st.info("本机恢复连接后可读取与提交实验。")
                elif panel == "review":
                    if rid == head and draft["base_revision"] == rid:
                        _render_review(st, workspace, revision, draft, path)
                    else:
                        st.info("先切回最新修订，才能审查或修改当前草稿。")
                else:
                    from nsgablack.catalog.lab_workspace_reference_ui import (render_reference_browser,
                        reference_dialog_requested, request_reference_dialog)
                    if st.button("弹出小窗", key=_PREFIX + f"reference_window::{wid}", icon=":material/open_in_new:"):
                        request_reference_dialog(st, context=path)
                    if not reference_dialog_requested(st):
                        render_reference_browser(st, context=path, compact=True)
                    if st.button("返回编辑", key=_PREFIX + f"reference_back::{wid}"):
                        st.session_state[panel_key] = None
                        st.rerun()
        _render_recent_run(st, runtime, workspace, case=case, online=online, draft=draft)
    # Render action widgets after capturing this editor's newest value. Their
    # containers remain at the top, so Save never commits an older blur buffer.
    with title:
        st.markdown("<div class='workspace-title'>" + html.escape(workspace["title"]) + "</div>"
            "<div class='workspace-subtitle'>运行：" + html.escape(str(case or "未选择 Case")) + " · " +
            (f"{len(draft['changes'])} 个文件未保存" if draft["changes"] else "所有更改已保存") + "</div>", unsafe_allow_html=True)
    with save:
        _save_action(st, store, workspace, revision, draft, online=online)
    with review:
        st.button("审查", key=_PREFIX + f"show_review::{wid}", use_container_width=True, icon=":material/rule:",
                  on_click=_toggle_panel, args=(st, wid, "review"))
    with lookup:
        st.button("查组件", key=_PREFIX + f"lookup::{wid}", use_container_width=True, icon=":material/widgets:",
                  on_click=_open_component_popup, args=(st, path, _PREFIX + f"lookup::{wid}"))
    with run:
        st.button("试跑设置", key=_PREFIX + f"show_run::{wid}", use_container_width=True, icon=":material/play_arrow:",
                  on_click=_toggle_panel, args=(st, wid, "run"))
    with history:
        st.button("实验结果", key=_PREFIX + f"show_results::{wid}", use_container_width=True, icon=":material/assessment:",
                  on_click=_toggle_panel, args=(st, wid, "results"))
    _show_dialogs(st, store)

if __name__ == "__main__":
    import os
    import streamlit as st
    st.set_page_config(page_title="工程实验", layout="wide", initial_sidebar_state="auto")
    render_workspace(st, hosted=os.environ.get("NSGABLACK_CATALOG_HOSTED") == "1")
