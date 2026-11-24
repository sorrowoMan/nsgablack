"""In-place Catalog reference. Looking up a component never edits a Project."""
from __future__ import annotations

_PREFIX = "project_workspace::reference::"
_KINDS = {"all": "全部组件", "adapter": "搜索算法", "representation": "候选与结构",
          "bias": "评分偏好", "plugin": "运行能力", "tool": "工具与操作"}


def request_reference_dialog(st, *, context=None):
    st.session_state[_PREFIX + "open"] = True
    st.session_state[_PREFIX + "context"] = context


def reference_dialog_requested(st):
    return bool(st.session_state.get(_PREFIX + "open"))


def keep_reference_inputs(st):
    # Detach these widget values before a full rerun closes the dialog. The
    # next lookup should retain the search and chosen snippet, not reset them.
    for key in list(st.session_state):
        if key in {_PREFIX + "query", _PREFIX + "kind"} or key.startswith(_PREFIX + "code::"):
            st.session_state[key] = st.session_state[key]


def _close(st):
    st.session_state[_PREFIX + "open"] = False


def _pin_to_workspace(st):
    """Keep the current reference beside code, using the existing tool rail."""
    workspace = st.session_state.get("project_workspace::workspace")
    if workspace:
        st.session_state[f"project_workspace::panel::{workspace}"] = "reference"
        _close(st)


def _select(st, key):
    previous = st.session_state.get(_PREFIX + "selected")
    if previous and previous != key:
        history = st.session_state.setdefault(_PREFIX + "history", [])
        history.append(previous)
        del history[:-12]
    st.session_state[_PREFIX + "selected"] = key
    st.session_state[_PREFIX + "results_open"] = False


def _back(st):
    history = st.session_state.get(_PREFIX + "history", [])
    if history:
        st.session_state[_PREFIX + "selected"] = history.pop()
        st.session_state[_PREFIX + "results_open"] = False


def _favorite(st, key, enabled):
    values = st.session_state.setdefault(_PREFIX + "favorites", [])
    if not enabled and key in values:
        values.remove(key)
    elif enabled and key not in values:
        values.append(key)
        del values[:-24]


def _compact_usage_fields(markdown):
    """Use explicit baseline labels, never guess or truncate source code."""
    from nsgablack.catalog.usage_learning import documentation_fields
    fields = documentation_fields(({"path": "catalog-usage.md", "text": markdown},))
    return [(label, fields[label][0]) for label in ("先准备什么", "放在哪", "接入步骤")
            if fields.get(label)]


def render_reference_browser(st, *, context=None, source=None, compact=False):
    """Read published reference in a dialog or a single-column editor rail.

    The caller invokes this only while lookup is open. ``compact`` changes the
    layout and result bound, not the underlying read-only publication contract.
    """
    from nsgablack.catalog.lab_workspace_reference import reference_search, reference_detail
    if context and not compact:
        st.caption(f"正在编辑：{context} · 查阅不会改变文件或运行实验")
    left, right = ((st.container(), st.container()) if compact else
                   st.columns([1, 2.1], gap="large"))
    with left:
        previous_query = st.session_state.get(_PREFIX + "last_query", "")
        query = st.text_input("查组件", placeholder="名称或用途，如 VNS、精英池、并行评估",
                              value=previous_query,
                              key=_PREFIX + "query", max_chars=200)
        st.session_state[_PREFIX + "last_query"] = query
        previous_kind = st.session_state.get(_PREFIX + "last_kind", "all")
        filters = st.expander("筛选与收藏", expanded=False) if compact else st.container()
        with filters:
            kind = st.selectbox("组件范围", list(_KINDS), format_func=_KINDS.get,
                               index=list(_KINDS).index(previous_kind), key=_PREFIX + "kind")
        st.session_state[_PREFIX + "last_kind"] = kind
        if compact and (query != previous_query or kind != previous_kind):
            st.session_state[_PREFIX + "results_open"] = True
        try:
            limit = 6 if compact else 12
            found = reference_search(query, kind=kind, limit=limit, source=source)
        except (ValueError, OSError) as exc:
            st.error(f"组件资料暂不可读：{exc}")
            return
        with filters:
            st.caption(found.get("source_note", ""))
            favorites = st.session_state.get(_PREFIX + "favorites", [])
            if favorites:
                if compact:
                    st.caption("本次会话收藏")
                    favorite_container = st.container()
                else:
                    favorite_container = st.expander("本次会话收藏", expanded=True)
                with favorite_container:
                    for key in favorites:
                        st.button(key, key=_PREFIX + "favorite_hit::" + key,
                                  on_click=_select, args=(st, key), use_container_width=True)
        if not found.get("available"):
            st.info("当前环境没有发布的组件资料。工程草稿仍保留，可以继续编辑。")
            return
        items = found["items"]
        result_note = f"找到 {found['total']} 项" + (
            f" · 显示前 {limit} 项" if found["total"] > limit else "")
        def render_hits():
            for item in items:
                st.button(item["title"], key=_PREFIX + "hit::" + item["key"],
                          help=item.get("summary", ""), use_container_width=True,
                          on_click=_select, args=(st, item["key"]))
        if compact:
            with st.expander("搜索结果 · " + result_note,
                             expanded=st.session_state.get(_PREFIX + "results_open", False)):
                render_hits()
        else:
            st.caption(result_note)
            render_hits()
        if not items:
            st.info("没有匹配项。试试组件名称、英文类名或更短的用途词。")
        selected = st.session_state.get(_PREFIX + "selected")
        if not selected and items:
            selected = items[0]["key"]
            st.session_state[_PREFIX + "selected"] = selected
        elif selected and selected not in {item["key"] for item in items}:
            st.caption(("下方" if compact else "右侧") + "保留正在查阅的组件；点击搜索结果后切换。")
    with right:
        if not selected:
            st.info("按用途搜索组件，在这里查看具体装配方法。")
            return
        try:
            entry = reference_detail(selected, source=source)
        except (ValueError, OSError) as exc:
            st.error(f"组件详情暂不可读：{exc}")
            return
        if not entry:
            st.info("此组件已不在当前发布资料中；可重新搜索。")
            return
        if compact:
            with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
                heading = st.container()
                tools = st.popover("组件操作")
        else:
            heading, tools = st.columns([3, 1])
        with heading:
            st.subheader(entry["title"])
            st.caption(entry["key"])
        with tools:
            st.button("返回上一组件", key=_PREFIX + "back", disabled=not st.session_state.get(_PREFIX + "history"),
                      on_click=_back, args=(st,))
            is_favorite = selected in st.session_state.get(_PREFIX + "favorites", [])
            if st.button("取消收藏" if is_favorite else "收藏组件",
                         key=_PREFIX + ("favorite_remove::" if is_favorite else "favorite_add::") + selected):
                _favorite(st, selected, not is_favorite)
                st.rerun()
        if compact:
            uses = entry.get("use_when", [])
            st.write(uses[0] if uses else entry.get("summary", ""))
            usage, full_usage, interface, relations = st.tabs(["接入", "完整用法", "参数与接口", "相关组件"])
        else:
            st.write(entry.get("summary", ""))
            usage, interface, relations = st.tabs(["怎么用", "参数与接口", "相关组件"])
        with usage:
            if compact:
                fields = _compact_usage_fields(entry.get("usage_markdown", ""))
                for label, value in fields:
                    st.markdown(f"**{label}** · {value}")
                if not fields:
                    st.caption("详细装配说明见「完整用法」标签；这里不补写资料未声明的步骤。")
            elif entry.get("use_when"):
                st.markdown("**适合什么时候用**")
                for value in entry["use_when"]:
                    st.write(value)
            # Assembly prose is the primary content, not an optional section
            # below an unexplained code block. Keep all published variants.
            if not compact and entry.get("usage_markdown"):
                st.markdown(entry["usage_markdown"])
            blocks = entry.get("code_blocks", [])
            if blocks:
                symbol = str(entry.get("import_path", "")).partition(":")[2].split(".")[-1]
                preferred = next((i for i, block in enumerate(blocks)
                                  if symbol and symbol + "(" in block["code"]), 0)
                saved_index = st.session_state.get(_PREFIX + "last_code::" + selected, preferred)
                if not isinstance(saved_index, int) or not 0 <= saved_index < len(blocks):
                    saved_index = preferred
                def block_label(i):
                    lines = [line.strip() for line in blocks[i]["code"].splitlines() if line.strip()]
                    first = next((line for line in lines if not line.startswith(("#", "from ", "import "))),
                                 lines[0] if lines else blocks[i].get("title", ""))
                    return f"片段 {i + 1} · {first[:64]}"
                selector = st.popover("切换用法片段") if compact and len(blocks) > 1 else st.container()
                with selector:
                    if compact and len(blocks) == 1:
                        index = 0
                    else:
                        index = st.selectbox("可复制的用法片段", list(range(len(blocks))),
                            format_func=block_label,
                            index=saved_index, key=_PREFIX + "code::" + selected)
                st.session_state[_PREFIX + "last_code::" + selected] = index
                block = blocks[index]
                if not compact:
                    st.caption("代码右上角可复制。按说明放进对应文件，查阅不会自动插入。")
                code_height = min(240 if compact else 320,
                                  max(92, 36 + 20 * len(block["code"].splitlines())))
                st.code(block["code"], language=block.get("language") or "python",
                        height=code_height)
                if compact:
                    st.caption("代码右上角可复制。按说明放进对应文件，查阅不会自动插入。")
                if block.get("source_path"):
                    st.caption(str(block["source_path"]) +
                               (f" · L{block['start_line']}" if block.get("start_line") else ""))
            if not entry.get("usage_markdown") and not blocks:
                st.info("当前发布资料未提供可复制片段；这里不生成未经核对的装配代码。")
            st.caption(entry.get("evidence_note", ""))
        if compact:
            with full_usage:
                if entry.get("use_when"):
                    st.markdown("**适合什么时候用**")
                    for value in entry["use_when"]:
                        st.write(value)
                if entry.get("usage_markdown"):
                    st.markdown(entry["usage_markdown"])
                else:
                    st.info("发布资料没有完整说明；可查看「接入」中的已登记片段与「参数与接口」。")
                st.caption(entry.get("evidence_note", ""))
        with interface:
            if entry.get("import_path"):
                st.markdown("**正式导入位置**")
                st.code(entry["import_path"], language="text")
            if entry.get("parameters"):
                st.dataframe(entry["parameters"], hide_index=True, width="stretch")
            elif entry.get("config_keys"):
                st.write("资料中声明的配置项：" + "、".join(entry["config_keys"]))
            else:
                st.info("当前资料未单独登记参数表，请查看完整用法与来源。")
            for label, field in (("支持的操作", "operations"), ("使用边界", "boundaries")):
                values = entry.get(field, [])
                if values:
                    st.markdown(f"**{label}**")
                    for value in values:
                        st.write(value)
        with relations:
            for item in entry.get("relations", []):
                st.button(item.get("title") or item["key"], key=_PREFIX + f"relation::{selected}::{item['key']}",
                          on_click=_select, args=(st, item["key"]), help=item.get("reason", ""),
                          disabled=item.get("available") is False)
                if item.get("reason"):
                    st.caption(item["reason"])
            if not entry.get("relations"):
                st.info("当前资料没有显式登记配套关系，可继续按用途搜索。")


def open_reference_dialog(st, *, context=None, source=None):
    context = context or st.session_state.get(_PREFIX + "context")
    @st.dialog("组件速查", width="large", on_dismiss=lambda: _close(st))
    def window():
        render_reference_browser(st, context=context, source=source)
        back, pin = st.columns([1, 1])
        with back:
            if st.button("返回编辑", key=_PREFIX + "close", type="primary", use_container_width=True):
                _close(st)
                st.rerun()
        with pin:
            if st.button("固定到右侧", key=_PREFIX + "pin", use_container_width=True,
                         disabled=not st.session_state.get("project_workspace::workspace"),
                         icon=":material/keep:"):
                _pin_to_workspace(st)
                st.rerun()
    window()
