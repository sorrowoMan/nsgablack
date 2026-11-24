from __future__ import annotations
from blackbase.plugin import report_soft_error as _report_optional_failure

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from html import escape
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode

if __package__ in {None, ""}:
    _ROOT = Path(__file__).resolve().parents[1]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    from nsgablack.catalog import dashboard_page as _page
    from nsgablack.catalog import dashboard_shell as _shell
    from nsgablack.catalog import dashboard_shared as _shared
    from nsgablack.catalog import curation_ui as _curation
    from nsgablack.catalog import examples_ui as _examples
    from nsgablack.catalog import navigation as _navigation
    from nsgablack.catalog.dashboard_style import DASHBOARD_CSS
    from nsgablack.catalog.ui_theme import WORKSPACE_BRAND
    from nsgablack.catalog.facade import (
        _entry_payload,
        catalog_facets,
        catalog_neighbors,
        catalog_schema,
        catalog_source_info,
        catalog_summary,
        list_entries,
        search_entries,
        show_entry,
    )
    from nsgablack.catalog.guidance import WIRING_STATUS_NOTE, wiring_status_label
else:
    from . import dashboard_page as _page
    from . import dashboard_shell as _shell
    from . import dashboard_shared as _shared
    from . import curation_ui as _curation
    from . import examples_ui as _examples
    from . import navigation as _navigation
    from .dashboard_style import DASHBOARD_CSS
    from .ui_theme import WORKSPACE_BRAND
    from .facade import (
        _entry_payload,
        catalog_facets,
        catalog_neighbors,
        catalog_schema,
        catalog_source_info,
        catalog_summary,
        list_entries,
        search_entries,
        show_entry,
    )
    from .guidance import WIRING_STATUS_NOTE, wiring_status_label

_KIND_ALL = "all"
_NAV_ACTION_LOCATE_SELECTED = "locate_selected"
_PENDING_LOCATE_KEY = "catalog_ui_pending_locate_selected"
_PENDING_SCROLL_TARGET_KEY = "catalog_ui_pending_scroll_target"
_HOSTED_SOURCE_VALUES = {
    "scope": "framework",
    "project_path": "",
    "include_global": False,
    "db_path": "",
    "source_mode": "off",
}


def _hosted_mode() -> bool:
    return os.environ.get("NSGABLACK_CATALOG_HOSTED", "").strip() == "1"


def _hosted_source_values() -> dict[str, Any]:
    """Only trusted process configuration can choose the hosted read model."""
    values = dict(_HOSTED_SOURCE_VALUES)
    source = os.environ.get("NSGABLACK_CATALOG_HOSTED_SOURCE", "registry").strip()
    if source not in {"registry", "database"}:
        raise RuntimeError("Invalid hosted Catalog source configuration")
    if source == "database":
        if not os.environ.get("NSGABLACK_CATALOG_DB_URL", "").strip():
            raise RuntimeError("Hosted Catalog database configuration is required")
        values["source_mode"] = "only"
    return values


def _catalog_source_options(
    scope: str,
    project_path: str | None,
    include_global: bool,
    db_path: str | None,
    source_mode: str | None,
) -> dict[str, Any]:
    """One read boundary for local configuration and the fixed hosted source."""
    values = _hosted_source_values() if _hosted_mode() else {
        "scope": scope, "project_path": project_path, "include_global": include_global,
        "db_path": db_path, "source_mode": source_mode,
    }
    for field in ("project_path", "db_path", "source_mode"):
        values[field] = values[field] or None
    return values


def _public_query_params(values: Mapping[str, object]) -> dict[str, object]:
    params = dict(values)
    if _hosted_mode():
        params.update({**_hosted_source_values(), "include_global": ""})
    return params


def _enforce_hosted_session(st: Any) -> None:
    if _hosted_mode():
        for key, value in _hosted_source_values().items():
            st.session_state[f"catalog_ui_{key}"] = value

_KIND_ORDER: tuple[str, ...] = (
    _KIND_ALL,
    "adapter",
    "plugin",
    "bias",
    "representation",
    "suite",
    "tool",
    "doc",
    "example",
)

_KIND_LABELS: dict[str, str] = {
    _KIND_ALL: "全部组件",
    "adapter": "搜索策略 Adapter",
    "plugin": "运行能力 Plugin",
    "bias": "评估偏好 Bias",
    "representation": "管线与结构",
    "suite": "Suite 套件",
    "tool": "操作与工具",
    "doc": "设计文档",
    "example": "项目示例",
    "assembly": "装配入口",
    "backend": "计算后端",
    "backend_capability": "后端能力",
    "capability": "生命周期能力",
    "catalog": "目录工具",
    "codec": "模型参数 Codec",
    "conditional": "条件管线",
    "core": "核心协议",
    "dashboard": "可视化工具",
    "data_view": "数据视图 DataView",
    "experiment": "实验管理",
    "head": "模型输出 Head",
    "integration": "框架连接",
    "model": "模型组件",
    "nsgablack_neural": "神经模型搜索",
    "nsgablack_symbolic": "符号模型搜索",
    "numericizer": "数据数值化",
    "pipeline": "候选与数据管线",
    "preset": "装配预设",
    "problem": "评估问题 Problem",
    "problem_bridge": "问题连接",
    "provider": "模型执行 Provider",
    "schema": "数据结构规范",
    "symbolic_pipeline": "符号表达式管线",
    "trainer": "训练入口 Trainer",
}

_SCOPE_LABELS: dict[str, str] = {
    "framework": "框架视图",
    "project": "项目视图",
}

_SEARCH_FIELD_LABELS: dict[str, str] = {
    "all": "全部",
    "name": "名称",
    "tag": "标签",
    "context": "上下文契约",
    "usage": "使用说明",
}

_SOURCE_MODE_OPTIONS: tuple[str, ...] = ("", "prefer", "only", "off")
_SOURCE_MODE_LABELS: dict[str, str] = {
    "": "自动",
    "prefer": "优先数据库",
    "only": "仅数据库",
    "off": "仅 registry",
}

_FIELD_LABELS: dict[str, str] = {
    "role": "职责",
    "concepts": "相关概念",
    "operations": "运行方法",
    "boundaries": "支持边界",
    "wiring_status": "配方结构状态",
    "wiring_notes": "结构检查说明",
    "tags": "标签",
    "companions": "关联条目",
    "required_companions": "声明的依赖",
    "linked_by": "反向关联",
    "context_requires": "读取上下文",
    "context_provides": "提供上下文",
    "context_mutates": "变更上下文",
    "context_cache": "缓存上下文",
    "context_notes": "上下文说明",
    "artifact_requires": "依赖 Artifact",
    "artifact_provides": "产出 Artifact",
    "phase_in": "进入阶段",
    "phase_out": "输出阶段",
    "use_when": "适用场景",
    "minimal_wiring": "最小接线",
    "config_keys": "装配配置",
    "example_entry": "示例入口",
    "import_path": "导入路径",
    "summary": "摘要",
}

_PRIMARY_FILTER_FIELDS: tuple[str, ...] = (
    "concepts",
    "role",
    "tags",
    "companions",
    "required_companions",
    "context_requires",
    "context_provides",
)

_NO_SELECTION = _shared.NO_SELECTION
_NAV_STACK_KEY = _shared.NAV_STACK_KEY
_SORT_OPTIONS: tuple[str, ...] = ("default", "title", "key", "kind")
_SORT_LABELS: dict[str, str] = {
    "default": "默认排序",
    "title": "标题",
    "key": "Key",
    "kind": "分类",
}
_DETAIL_TABS: tuple[str, ...] = ("overview", "interface", "relations", "source")
_DETAIL_TAB_LABELS: dict[str, str] = {
    "overview": "用法",
    "interface": "接口",
    "relations": "关系",
    "source": "来源",
}
_COLUMN_MODE_OPTIONS: tuple[str, ...] = ("compact", "standard", "full")
_COLUMN_MODE_LABELS: dict[str, str] = {
    "compact": "简洁列表",
    "standard": "组件列表",
    "full": "完整表格",
}
_RESULTS_COLLAPSE_OPTIONS: tuple[str, ...] = ("expanded", "collapsed")
_RESULTS_COLLAPSE_LABELS: dict[str, str] = {
    "expanded": "展开",
    "collapsed": "折叠",
}
_PAGE_SIZE_OPTIONS: tuple[int, ...] = (25, 50, 100, 250)


def dashboard_script_path() -> Path:
    return Path(__file__).resolve()


def build_streamlit_command(
    *,
    profile: str = "framework-core",
    scope: str = "framework",
    kind: str = _KIND_ALL,
    query: str = "",
    field: str = "all",
    project_path: str | None = None,
    include_global: bool = False,
    db_path: str | None = None,
    source_mode: str | None = None,
    column_mode: str = _shared.DEFAULT_COLUMN_MODE,
    page_size: int = _shared.DEFAULT_PAGE_SIZE,
    results_collapse: str = _shared.DEFAULT_RESULTS_COLLAPSE,
    host: str | None = None,
    port: int | None = None,
    headless: bool = False,
) -> list[str]:
    return _shell.build_streamlit_command(
        script_path=dashboard_script_path(),
        profile=profile,
        scope=scope,
        kind=kind,
        query=query,
        field=field,
        project_path=project_path,
        include_global=include_global,
        db_path=db_path,
        source_mode=source_mode,
        column_mode=column_mode,
        page_size=page_size,
        results_collapse=results_collapse,
        host=host,
        port=port,
        headless=headless,
    )


def launch_catalog_dashboard(
    *,
    profile: str = "framework-core",
    scope: str = "framework",
    kind: str = _KIND_ALL,
    query: str = "",
    field: str = "all",
    project_path: str | None = None,
    include_global: bool = False,
    db_path: str | None = None,
    source_mode: str | None = None,
    column_mode: str = _shared.DEFAULT_COLUMN_MODE,
    page_size: int = _shared.DEFAULT_PAGE_SIZE,
    results_collapse: str = _shared.DEFAULT_RESULTS_COLLAPSE,
    host: str | None = None,
    port: int | None = None,
    headless: bool = False,
) -> int:
    return _shell.launch_catalog_dashboard(
        script_path=dashboard_script_path(),
        profile=profile,
        scope=scope,
        kind=kind,
        query=query,
        field=field,
        project_path=project_path,
        include_global=include_global,
        db_path=db_path,
        source_mode=source_mode,
        column_mode=column_mode,
        page_size=page_size,
        results_collapse=results_collapse,
        host=host,
        port=port,
        headless=headless,
    )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="nsgablack catalog dashboard")
    parser.add_argument("--profile", type=str, default="framework-core")
    parser.add_argument("--scope", type=str, default="framework")
    parser.add_argument("--kind", type=str, default=_KIND_ALL)
    parser.add_argument("--query", type=str, default="")
    parser.add_argument("--field", type=str, default="all")
    parser.add_argument("--project-path", type=str, default=None)
    parser.add_argument("--include-global", action="store_true")
    parser.add_argument("--db-path", type=str, default=None)
    parser.add_argument("--source-mode", type=str, default=None)
    parser.add_argument("--column-mode", type=str, default=_shared.DEFAULT_COLUMN_MODE, choices=list(_COLUMN_MODE_OPTIONS))
    parser.add_argument("--page-size", type=int, default=_shared.DEFAULT_PAGE_SIZE)
    parser.add_argument("--results-collapse", type=str, default=_shared.DEFAULT_RESULTS_COLLAPSE, choices=list(_RESULTS_COLLAPSE_OPTIONS))
    return parser.parse_known_args(argv)[0]


def _require_streamlit():
    try:
        import streamlit as st
    except Exception as exc:  # pragma: no cover
        raise SystemExit(
            "streamlit is required for catalog dashboard. Install with: python -m pip install streamlit"
        ) from exc
    return st


def _set_page_config(st: Any) -> None:
    try:
        st.set_page_config(
            page_title="nsgablack Catalog",
            page_icon="NC",
            layout="wide",
            initial_sidebar_state="auto",
        )
    except Exception as _fallback_error:
        _report_optional_failure(component=__name__, event='_set_page_config.fallback_89', exc=_fallback_error)
        pass


def _inject_style(st: Any) -> None:
    st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)


def _scope_label(scope: str) -> str:
    return _SCOPE_LABELS.get(str(scope or "").strip().lower(), str(scope or ""))


def _kind_label(kind: str) -> str:
    if _navigation.is_group(kind):
        return _navigation.group_title(kind)
    return _KIND_LABELS.get(str(kind or "").strip().lower(), str(kind or ""))


def _catalog_kind_arg(kind: str | None) -> str | None:
    raw = str(kind or "").strip().lower()
    if not raw or raw == _KIND_ALL:
        return None
    return raw


def _ordered_kinds(values: Sequence[str]) -> tuple[str, ...]:
    present = {str(value or "").strip().lower() for value in values if str(value or "").strip()}
    ordered = [kind for kind in _KIND_ORDER if kind == _KIND_ALL or kind in present]
    extras = sorted(present.difference(set(_KIND_ORDER)))
    return tuple(ordered + extras)


def _search_field_label(field_name: str) -> str:
    return _SEARCH_FIELD_LABELS.get(str(field_name or "").strip().lower(), str(field_name or ""))


def _source_mode_label(mode: str) -> str:
    key = str(mode or "").strip().lower()
    return _SOURCE_MODE_LABELS.get(key, key or "自动")


def _field_label(field_name: str) -> str:
    key = str(field_name or "").strip()
    return _FIELD_LABELS.get(key, key.replace("_", " ").title())


def _relation_group_label(relation_name: str, relation_labels: Mapping[str, str] | None = None) -> str:
    key = str(relation_name or "").strip()
    custom = str((relation_labels or {}).get(key, "") or "").strip()
    if custom:
        return custom
    if key in {"companions", "linked_by"}:
        return {"companions": "目录声明的配套组件", "linked_by": "哪些组件关联了它"}[key]
    if key.startswith("context_provides::"):
        _, _, context_key = key.partition("::")
        return f"产物 -> {context_key} -> 消费者"
    if key.startswith("context_requires::"):
        _, _, context_key = key.partition("::")
        return f"依赖 <- {context_key} <- 生产者"
    if key.startswith("artifact_provides::"):
        _, _, artifact_key = key.partition("::")
        return f"Artifact -> {artifact_key} -> 消费者"
    if key.startswith("artifact_requires::"):
        _, _, artifact_key = key.partition("::")
        return f"Artifact 依赖 <- {artifact_key} <- 生产者"
    if key.startswith("phase_out::"):
        _, _, phase_key = key.partition("::")
        return f"Phase Out -> {phase_key} -> 下游"
    if key.startswith("phase_in::"):
        _, _, phase_key = key.partition("::")
        return f"Phase In <- {phase_key} <- 上游"
    return _field_label(key)


def _relation_family_label(family_name: str) -> str:
    mapping = {
        "context": "上下文链路",
        "artifact": "Artifact 链路",
        "phase": "Phase 链路",
    }
    key = str(family_name or "").strip().lower()
    return mapping.get(key, key or "关系链路")


def _render_relation_cards(st: Any, relation_cards: Sequence[Mapping[str, Any]]) -> None:
    cards = [dict(item) for item in relation_cards if isinstance(item, Mapping)]
    if not cards:
        return
    family_order = ("context", "artifact", "phase")
    for family in family_order:
        family_cards = [card for card in cards if str(card.get("family", "") or "") == family]
        if not family_cards:
            continue
        st.markdown(f"<div class='catalog-section-title'>{_relation_family_label(family)}</div>", unsafe_allow_html=True)
        fragments: list[str] = ["<div class='catalog-relation-grid'>"]
        for card in family_cards:
            title = escape(str(card.get("title", "") or ""))
            direction = "向外输出" if str(card.get("direction", "") or "") == "out" else "向内依赖"
            count = int(card.get("count", 0) or 0)
            previews = []
            for item in tuple(card.get("preview_items", ()) or ())[:3]:
                label = escape(str(item.get("title", "") or item.get("key", "") or ""))
                key = escape(str(item.get("key", "") or ""))
                previews.append(
                    f"<div class='catalog-relation-preview-item'>{label}<span class='catalog-relation-preview-key'>{key}</span></div>"
                )
            if count > 3:
                previews.append(
                    f"<div class='catalog-relation-preview-item'>还有 {count - 3} 个关联条目</div>"
                )
            fragments.append(
                "<div class='catalog-relation-card'>"
                f"<div class='catalog-relation-family'>{escape(_relation_family_label(family))}</div>"
                f"<div class='catalog-relation-title'>{title}</div>"
                f"<div class='catalog-relation-meta'>{direction} · {count} 个关联条目</div>"
                + ("<div class='catalog-relation-preview'>" + "".join(previews) + "</div>" if previews else "")
                + "</div>"
            )
        fragments.append("</div>")
        st.markdown("".join(fragments), unsafe_allow_html=True)


def _render_relation_chain_cards(
    st: Any,
    relation_chain_cards: Sequence[Mapping[str, Any]],
    *,
    current_entry: Mapping[str, Any] | None,
    scope: str,
    kind: str,
    expanded_relation_groups: Sequence[str] = (),
) -> None:
    cards = [dict(item) for item in relation_chain_cards if isinstance(item, Mapping)]
    if not cards:
        return
    expanded = {str(value).strip() for value in expanded_relation_groups if str(value).strip()}
    st.markdown("<div class='catalog-section-title'>按合同键聚合的链路视图</div>", unsafe_allow_html=True)
    st.caption("当前条目位于链路中间。左侧是上游生产者，右侧是下游消费者；点击条目可直接跳转，点击展开可查看完整关系组。")
    for card_index, card in enumerate(cards):
        family_name = _relation_family_label(str(card.get("family", "") or ""))
        family_key = str(card.get("family", "") or "").strip() or "all"
        relation_value = str(card.get("value", "") or "").strip()
        incoming_group_id = str(card.get("incoming_group_id", "") or "").strip()
        outgoing_group_id = str(card.get("outgoing_group_id", "") or "").strip()
        incoming_label = str(card.get("incoming_label", "") or "上游生产者").strip() or "上游生产者"
        outgoing_label = str(card.get("outgoing_label", "") or "下游消费者").strip() or "下游消费者"
        incoming_count = int(card.get("incoming_count", 0) or 0)
        outgoing_count = int(card.get("outgoing_count", 0) or 0)
        total_count = int(card.get("total_count", 0) or 0)
        incoming_items = [dict(item) for item in tuple(card.get("incoming_preview_items", ()) or ()) if isinstance(item, Mapping)]
        outgoing_items = [dict(item) for item in tuple(card.get("outgoing_preview_items", ()) or ()) if isinstance(item, Mapping)]
        incoming_open = bool(incoming_group_id) and incoming_group_id in expanded
        outgoing_open = bool(outgoing_group_id) and outgoing_group_id in expanded

        with st.container(border=True):
            top_cols = st.columns((1.2, 0.9, 1.2))
            with top_cols[0]:
                st.caption(f"上游生产者 · {incoming_count}")
                if incoming_label:
                    st.caption(incoming_label)
            with top_cols[1]:
                st.caption(family_name)
                st.markdown(f"**{relation_value or '未命名合同键'}**")
                st.caption(f"总链路 {total_count} · {incoming_count} -> 当前合同键 -> {outgoing_count}")
            with top_cols[2]:
                st.caption(f"下游消费者 · {outgoing_count}")
                if outgoing_label:
                    st.caption(outgoing_label)

            lane_cols = st.columns((1.3, 0.9, 1.3))
            lane_specs = (
                ("上游生产者", incoming_items, incoming_count, incoming_group_id, incoming_open),
                ("下游消费者", outgoing_items, outgoing_count, outgoing_group_id, outgoing_open),
            )
            for lane_index, (lane_col, (lane_title, lane_items, lane_count, lane_group_id, lane_open)) in enumerate(
                zip((lane_cols[0], lane_cols[2]), lane_specs)
            ):
                with lane_col:
                    st.button(
                        f"{'已展开' if lane_open else '展开'}{lane_title.replace('生产者', '').replace('消费者', '')} {lane_count}",
                        key=(
                            f"catalog_ui::chain::open::{kind}::{family_key}::{card_index}::"
                            f"{relation_value or 'unnamed'}::{lane_index}::{lane_group_id or lane_title}"
                        ),
                        width="stretch",
                        disabled=not lane_group_id,
                        on_click=_callback_focus_relation_group,
                        kwargs={
                            "st": st,
                            "scope": scope,
                            "kind": kind,
                            "relation_group": lane_group_id,
                        },
                    )
                    if not lane_items:
                        st.caption("当前暂无关联条目")
                    for index, item in enumerate(lane_items):
                        target_key = str(item.get("key", "") or "").strip()
                        target_kind = str(item.get("kind", "") or "").strip()
                        title = str(item.get("title", "") or target_key).strip() or target_key
                        if not target_key:
                            continue
                        st.button(
                            title,
                            key=(
                                f"catalog_ui::chain::jump::{kind}::{family_key}::{card_index}::"
                                f"{relation_value or 'unnamed'}::{lane_index}::{index}::{target_key}"
                            ),
                            width="stretch",
                            on_click=_callback_jump_relation,
                            kwargs={
                                "st": st,
                                "current_entry": current_entry,
                                "target_key": target_key,
                                "target_kind": target_kind,
                            },
                        )
                    if lane_count > len(lane_items):
                        st.caption(f"还有 {lane_count - len(lane_items)} 个关联条目，可先展开这条链路。")

            with lane_cols[1]:
                st.caption("聚合链路")
                st.markdown(f"**{incoming_count} 个上游**")
                st.caption("通过当前合同键流入")
                st.code(relation_value or "unnamed_contract_key", language=None)
                st.caption("再流向下游消费者")
                st.markdown(f"**{outgoing_count} 个下游**")


def _sort_label(sort_name: str) -> str:
    key = str(sort_name or "").strip().lower()
    return _SORT_LABELS.get(key, key)


def _detail_tab_label(tab_name: str) -> str:
    key = str(tab_name or "").strip().lower()
    return _DETAIL_TAB_LABELS.get(key, key)


def _column_mode_label(mode_name: str) -> str:
    key = str(mode_name or "").strip().lower()
    return _COLUMN_MODE_LABELS.get(key, key)


def _results_collapse_label(mode_name: str) -> str:
    key = str(mode_name or "").strip().lower()
    return _RESULTS_COLLAPSE_LABELS.get(key, key)


def _primary_controls_spec() -> _page.ControlRowSpec:
    return _page.ControlRowSpec(
        row_id=_page.PRIMARY_CONTROLS_ROW_ID,
        section_id="primary",
        slots=(
            _page.ControlSlotSpec("scope", 0.78, "视图"),
            _page.ControlSlotSpec("profile", 0.92, "Profile"),
            _page.ControlSlotSpec("kind", 0.95, "分类"),
            _page.ControlSlotSpec("query", 1.2, "关键词", placeholder="按当前分类搜索 key / 标题 / 摘要；想全局找 bias 就切到“全部 All”"),
        ),
    )


def _secondary_controls_spec() -> _page.ControlRowSpec:
    return _page.ControlRowSpec(
        row_id=_page.SECONDARY_CONTROLS_ROW_ID,
        section_id="secondary",
        slots=(
            _page.ControlSlotSpec("field", 0.88, "搜索范围"),
            _page.ControlSlotSpec(
                "project_path",
                1.08,
                "Project Path",
                help="项目视图下用于定位正式 Project/Case 与其 catalog/ 的路径。",
            ),
            _page.ControlSlotSpec("include_global", 1.05, "项目视图并入框架条目"),
            _page.ControlSlotSpec(
                "db_path",
                0.95,
                "DB Path / URL",
                help="留空时按 catalog/db.toml 或环境变量自动连接；填写后优先直连这个数据库。",
                placeholder="postgresql://postgres:password@localhost:5432/nsgablack",
            ),
            _page.ControlSlotSpec(
                "source_mode",
                0.92,
                "Source Mode",
                help="自动 / 优先数据库 / 仅数据库 / 仅 registry。",
            ),
        ),
    )


def _normalize_sort_by(value: object) -> str:
    key = str(value or "").strip().lower()
    return key if key in _SORT_OPTIONS else _shared.DEFAULT_SORT_BY


def _normalize_sort_dir(value: object) -> str:
    key = str(value or "").strip().lower()
    return "desc" if key == "desc" else _shared.DEFAULT_SORT_DIR


def _normalize_detail_tab(value: object) -> str:
    key = str(value or "").strip().lower()
    return key if key in _DETAIL_TABS else _shared.DEFAULT_DETAIL_TAB


def _normalize_column_mode(value: object) -> str:
    key = str(value or "").strip().lower()
    return key if key in _COLUMN_MODE_OPTIONS else _shared.DEFAULT_COLUMN_MODE


def _normalize_page_size(value: object) -> int:
    try:
        page_size = int(str(value or "").strip())
    except (TypeError, ValueError, OverflowError):
        return _shared.DEFAULT_PAGE_SIZE
    return page_size if page_size > 0 else _shared.DEFAULT_PAGE_SIZE


def _normalize_results_collapse(value: object) -> str:
    key = str(value or "").strip().lower()
    return key if key in _RESULTS_COLLAPSE_OPTIONS else _shared.DEFAULT_RESULTS_COLLAPSE


def _view_state_key(scope: str, kind: str, name: str) -> str:
    return _shared.view_state_key(scope, kind, name)


def _render_scalar(value: Any) -> str:
    if value in (None, "", (), [], {}):
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (list, tuple, set, frozenset)):
        return ", ".join(str(item) for item in value if str(item).strip())
    return str(value)


def _chips(values: Sequence[str]) -> str:
    return "".join(f"<span class='catalog-chip'>{escape(str(value))}</span>" for value in values if str(value).strip())


def _item_sort_value(item: Mapping[str, Any], sort_by: str) -> str:
    key = str(sort_by or "").strip().lower()
    if key == "title":
        return str(item.get("title", "") or item.get("key", "")).strip().lower()
    if key == "kind":
        return str(item.get("kind", "") or "").strip().lower()
    if key == "key":
        return str(item.get("key", "") or "").strip().lower()
    return str(item.get("key", "") or "").strip().lower()


def _sorted_items(items: Sequence[Mapping[str, Any]], *, sort_by: str, sort_dir: str) -> list[Mapping[str, Any]]:
    rows = list(items)
    if _normalize_sort_by(sort_by) == _shared.DEFAULT_SORT_BY:
        return rows
    reverse = _normalize_sort_dir(sort_dir) == "desc"
    return sorted(rows, key=lambda item: (_item_sort_value(item, sort_by), str(item.get("key", "") or "").strip().lower()), reverse=reverse)


def _read_query_params(st: Any) -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
    params, filters = _shared.read_query_params(
        st,
        base_keys=(
            "profile",
            "scope",
            "kind",
            "query",
            "field",
            "selected",
            "project_path",
            "include_global",
            "db_path",
            "source_mode",
            "sort_by",
            "sort_dir",
            "detail_tab",
            "open_relations",
            "column_mode",
            "page_size",
            "results_collapse",
            "nav_action",
        ),
    )
    if _hosted_mode():
        safe_params = _public_query_params(params)
        if safe_params != params:
            _shared.write_query_params(st, base_params=safe_params, field_filters=filters)
        params = {key: str(value) for key, value in safe_params.items()}
    return params, filters


def _query_param_payload(
    *,
    profile: str,
    scope: str,
    kind: str,
    query: str,
    field: str,
    selected: str,
    project_path: str,
    include_global: bool,
    db_path: str,
    source_mode: str,
    sort_by: str,
    sort_dir: str,
    detail_tab: str,
    open_relations: str,
    column_mode: str,
    page_size: int,
    results_collapse: str,
    field_filters: Mapping[str, object] | None = None,
) -> dict[str, str]:
    return _shared.build_query_param_payload(
        base_params=_public_query_params({
            "profile": str(profile),
            "scope": str(scope),
            "kind": str(kind),
            "query": str(query),
            "field": str(field),
            "selected": str(selected),
            "project_path": str(project_path),
            "include_global": "1" if include_global else "",
            "db_path": str(db_path),
            "source_mode": str(source_mode),
            "sort_by": str(sort_by),
            "sort_dir": str(sort_dir),
            "detail_tab": str(detail_tab),
            "open_relations": str(open_relations),
            "column_mode": str(column_mode),
            "page_size": str(int(page_size)),
            "results_collapse": str(results_collapse),
        }),
        field_filters=field_filters,
    )


def _build_deep_link_query(
    *,
    profile: str,
    scope: str,
    kind: str,
    query: str,
    field: str,
    selected: str,
    project_path: str,
    include_global: bool,
    db_path: str,
    source_mode: str,
    sort_by: str,
    sort_dir: str,
    detail_tab: str,
    open_relations: str,
    column_mode: str,
    page_size: int,
    results_collapse: str,
    field_filters: Mapping[str, object] | None = None,
) -> str:
    return _shared.build_deep_link_query(
        base_params=_public_query_params({
            "profile": str(profile),
            "scope": str(scope),
            "kind": str(kind),
            "query": str(query),
            "field": str(field),
            "selected": str(selected),
            "project_path": str(project_path),
            "include_global": "1" if include_global else "",
            "db_path": str(db_path),
            "source_mode": str(source_mode),
            "sort_by": str(sort_by),
            "sort_dir": str(sort_dir),
            "detail_tab": str(detail_tab),
            "open_relations": str(open_relations),
            "column_mode": str(column_mode),
            "page_size": str(int(page_size)),
            "results_collapse": str(results_collapse),
        }),
        field_filters=field_filters,
    )


def _write_query_params(
    st: Any,
    *,
    profile: str,
    scope: str,
    kind: str,
    query: str,
    field: str,
    selected: str,
    project_path: str,
    include_global: bool,
    db_path: str,
    source_mode: str,
    sort_by: str,
    sort_dir: str,
    detail_tab: str,
    open_relations: str,
    column_mode: str,
    page_size: int,
    results_collapse: str,
    field_filters: Mapping[str, object] | None = None,
) -> None:
    _shared.write_query_params(
        st,
        base_params=_public_query_params({
            "profile": str(profile),
            "scope": str(scope),
            "kind": str(kind),
            "query": str(query),
            "field": str(field),
            "selected": str(selected),
            "project_path": str(project_path),
            "include_global": "1" if include_global else "",
            "db_path": str(db_path),
            "source_mode": str(source_mode),
            "sort_by": str(sort_by),
            "sort_dir": str(sort_dir),
            "detail_tab": str(detail_tab),
            "open_relations": str(open_relations),
            "column_mode": str(column_mode),
            "page_size": str(int(page_size)),
            "results_collapse": str(results_collapse),
        }),
        field_filters=field_filters,
    )


def _deep_link_with_nav_action(deep_link_query: str, *, action: str) -> str:
    raw = str(deep_link_query or "").strip()
    query_only, _, fragment = raw.partition("#")
    query_text = query_only[1:] if query_only.startswith("?") else query_only
    params = [(key, value) for key, value in parse_qsl(query_text, keep_blank_values=True) if key != "nav_action"]
    params.append(("nav_action", str(action).strip()))
    rebuilt = "?" + urlencode(params)
    if fragment:
        return f"{rebuilt}#{fragment}"
    return rebuilt


def _has_active_field_filters(field_filters: Mapping[str, object] | None) -> bool:
    if not field_filters:
        return False
    for value in field_filters.values():
        if isinstance(value, (list, tuple, set, frozenset)):
            if any(str(item).strip() for item in value):
                return True
            continue
        if str(value or "").strip():
            return True
    return False


def _write_locate_state_and_rerun(
    st: Any,
    *,
    profile: str,
    scope: str,
    kind: str,
    query: str,
    field: str,
    selected: str,
    project_path: str,
    include_global: bool,
    db_path: str,
    source_mode: str,
    sort_by: str,
    sort_dir: str,
    detail_tab: str,
    open_relations: str,
    column_mode: str,
    page_size: int,
    results_collapse: str,
    field_filters: Mapping[str, object] | None,
) -> None:
    _write_query_params(
        st,
        profile=profile,
        scope=scope,
        kind=kind,
        query=query,
        field=field,
        selected=selected,
        project_path=project_path,
        include_global=include_global,
        db_path=db_path,
        source_mode=source_mode,
        sort_by=sort_by,
        sort_dir=sort_dir,
        detail_tab=detail_tab,
        open_relations=open_relations,
        column_mode=column_mode,
        page_size=page_size,
        results_collapse=results_collapse,
        field_filters=field_filters,
    )
    _rerun(st)


def _rerun(st: Any) -> None:
    _shared.rerun(st)


def _selected_table_row_indices(event: Any) -> tuple[int, ...]:
    if event is None:
        return ()
    selection = getattr(event, "selection", None)
    if selection is not None:
        rows = getattr(selection, "rows", None)
        if rows is not None:
            return tuple(int(value) for value in rows)
    if isinstance(event, Mapping):
        payload = event.get("selection")
        if isinstance(payload, Mapping):
            rows = payload.get("rows")
            if isinstance(rows, Sequence):
                return tuple(int(value) for value in rows)
    return ()


def _pick_default_kind(kind: str, kinds: Sequence[str]) -> str:
    raw = str(kind or "").strip().lower()
    if raw == _KIND_ALL or _navigation.is_group(raw):
        return raw
    if raw in kinds:
        return raw
    if kinds:
        return _KIND_ALL if _KIND_ALL in kinds else str(kinds[0])
    return _KIND_ALL


def _other_kind_hits(
    *,
    query: str,
    profile: str,
    scope: str,
    project_path: str | None,
    include_global: bool,
    field: str,
    current_kind: str,
    db_path: str | None = None,
    source_mode: str | None = None,
    limit: int = 24,
    filters_key: tuple[tuple[str, tuple[str, ...]], ...] = (),
) -> dict[str, list[Any]]:
    text = str(query or "").strip()
    if not text:
        return {}
    hits = search_entries(
        text,
        profile=profile,
        **_catalog_source_options(scope, project_path, include_global, db_path, source_mode),
        kind=None,
        field=field,
        limit=limit,
        field_filters=_shell.thaw_filters(filters_key),
    )
    grouped: dict[str, list[Any]] = {}
    for entry in hits:
        entry_kind = str(getattr(entry, "kind", "") or "").strip().lower()
        if not entry_kind or _navigation.contains_kind(current_kind, entry_kind):
            continue
        target = _navigation.group_for_kind(entry_kind) if _navigation.is_group(current_kind) else entry_kind
        grouped.setdefault(target, []).append(entry)
    return grouped


def _normalize_navigation_stack(values: object) -> list[dict[str, str]]:
    return _shared.normalize_navigation_stack(values)


def _navigation_stack(st: Any) -> list[dict[str, str]]:
    return _shared.navigation_stack(st, state_key=_NAV_STACK_KEY)


def _push_navigation_stack(st: Any, *, current_entry: Mapping[str, Any] | None) -> None:
    _shared.push_navigation_stack(st, current_entry=current_entry, state_key=_NAV_STACK_KEY)


def _pop_navigation_stack(st: Any) -> dict[str, str] | None:
    return _shared.pop_navigation_stack(st, state_key=_NAV_STACK_KEY)


def _restore_navigation_index(st: Any, index: int) -> dict[str, str] | None:
    return _shared.restore_navigation_index(st, index, state_key=_NAV_STACK_KEY)


def _entry_source_scope(entry_key: str) -> str:
    return "project" if str(entry_key or "").strip().startswith("project.") else "framework"


def _source_badges(entry: Mapping[str, Any], source_info: Mapping[str, Any]) -> tuple[str, ...]:
    badges = [
        f"entry:{_entry_source_scope(str(entry.get('key', '')))}",
        f"view:{str(source_info.get('effective_source', 'framework'))}",
    ]
    metadata = entry.get("metadata", {}) or {}
    if isinstance(metadata, Mapping) and metadata.get("catalog_framework"):
        badges.insert(0, str(metadata["catalog_framework"]))
    framework_source = str(source_info.get("framework_source", "") or "").strip()
    if framework_source:
        badges.append(f"framework-backend:{framework_source}")
    db_backend = str(source_info.get("route_db_backend", "") or source_info.get("db_backend", "") or "").strip()
    if db_backend:
        badges.append(f"db-backend:{db_backend}")
    db_mode = str(source_info.get("source_mode", "") or source_info.get("db_mode", "") or "").strip()
    if db_mode and db_mode != "off":
        badges.append(f"db-mode:{db_mode}")
    return tuple(badges)


def _resolve_source_file(import_path: str, *, project_root: str | None = None) -> Path | None:
    if _hosted_mode():
        return None
    module_name = str(import_path or "").partition(":")[0].strip()
    if not module_name:
        return None

    root: str | None = None
    added_sys_path = False
    if project_root:
        root = str(Path(project_root).resolve())
        if root not in sys.path:
            sys.path.insert(0, root)
            added_sys_path = True
    try:
        spec = importlib.util.find_spec(module_name)
    except Exception:
        spec = None
    finally:
        if added_sys_path and root:
            try:
                sys.path.remove(root)
            except ValueError:
                pass

    if spec is None or not spec.origin:
        return None
    origin = str(spec.origin).strip()
    if not origin or origin in {"built-in", "frozen"}:
        return None
    path = Path(origin)
    return path.resolve() if path.exists() else None


def _reveal_source_file(path: Path) -> bool:
    if _hosted_mode():
        return False
    target = Path(path).resolve()
    if not target.exists():
        return False
    try:
        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer", "/select,", str(target)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target.parent)])
        return True
    except Exception as _fallback_error:
        _report_optional_failure(component=__name__, event='_reveal_source_file.fallback_91', exc=_fallback_error)
        return False


def _open_source_file(path: Path) -> bool:
    if _hosted_mode():
        return False
    target = Path(path).resolve()
    if not target.exists():
        return False
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(target))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])
        return True
    except Exception as _fallback_error:
        _report_optional_failure(component=__name__, event='_open_source_file.fallback_92', exc=_fallback_error)
        return False


def _copy_current_url(st: Any, *, key: str) -> None:
    if not st.button("复制 Deep-Link", key=key, width="stretch"):
        return
    try:
        from streamlit.components.v1 import html

        html(
            """
            <script>
            const current = window.parent.location.href;
            navigator.clipboard.writeText(current);
            </script>
            """,
            height=0,
            width=0,
        )
        try:
            st.toast("已复制当前页面链接")
        except Exception:
            st.success("已复制当前页面链接")
    except Exception:
        st.info("浏览器未允许自动复制，请手动复制下方 deep-link。")


def _selection_state(
    selected_key: str,
    items: Sequence[Mapping[str, Any]],
    *,
    selected_exists: bool,
) -> dict[str, Any]:
    return _shared.selection_state(selected_key, items, selected_exists=selected_exists, none_sentinel=_NO_SELECTION)


def _result_rows(items: Sequence[Mapping[str, Any]], *, column_mode: str) -> list[dict[str, str]]:
    example_snapshot = _examples.examples_snapshot()
    rows: list[dict[str, str]] = []
    normalized_mode = _normalize_column_mode(column_mode)
    for index, item in enumerate(items, start=1):
        row = {
            "序号": str(index),
            "标题": str(item.get("title", "") or item.get("key", "")),
            "Key": str(item.get("key", "")),
            "示例": _examples.example_status(item, example_snapshot),
        }
        if normalized_mode in {"standard", "full"}:
            row["分类"] = _kind_label(str(item.get("kind", "")))
            row["标签"] = ", ".join(str(value) for value in item.get("tags", ()) if str(value).strip())
        if normalized_mode == "full":
            row["摘要"] = str(item.get("summary", "") or "")
        rows.append(row)
    return rows


def _visible_result_items(items: Sequence[Mapping[str, Any]], *, page_size: int) -> list[Mapping[str, Any]]:
    return list(items[: _normalize_page_size(page_size)])


def _clear_scope_kind_filters(st: Any, *, scope: str, kind: str) -> None:
    _shared.clear_scope_kind_filters(st, scope=scope, kind=kind, facet_fields=_PRIMARY_FILTER_FIELDS)
    params = getattr(st, "query_params", None)
    if params is not None:
        for name in tuple(params):
            if str(name).startswith("f_"):
                del params[name]


def _scroll_to_anchor(st: Any, *, anchor_id: str) -> None:
    try:
        from streamlit.components.v1 import html

        html(
            f"""
            <script>
            const target = window.parent.document.getElementById({anchor_id!r});
            if (target) {{
                target.scrollIntoView({{ behavior: "smooth", block: "start" }});
            }}
            </script>
            """,
            height=0,
            width=0,
        )
    except Exception as _fallback_error:
        _report_optional_failure(component=__name__, event='_scroll_to_anchor.fallback_93', exc=_fallback_error)
        return


def _scroll_action_js(anchor_id: str) -> str:
    safe_anchor = json.dumps(str(anchor_id))
    return (
        "const target = window.parent.document.getElementById("
        f"{safe_anchor}"
        "); if (target) { target.scrollIntoView({ behavior: 'smooth', block: 'start' }); }"
    )


def _floating_nav_markup(
    *,
    locate_target: str | None,
    locate_tooltip: str = "定位当前选中项",
    top_target: str = "catalog-page-top",
) -> str:
    target_svg = (
        "<svg viewBox='0 0 24 24' width='22' height='22' aria-hidden='true' focusable='false'>"
        "<circle cx='12' cy='12' r='7.25' fill='none' stroke='currentColor' stroke-width='1.8'/>"
        "<circle cx='12' cy='12' r='2.5' fill='currentColor'/>"
        "<path d='M12 2.75v3.1M12 18.15v3.1M2.75 12h3.1M18.15 12h3.1' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round'/>"
        "</svg>"
    )
    top_svg = (
        "<svg viewBox='0 0 24 24' width='22' height='22' aria-hidden='true' focusable='false'>"
        "<path d='M12 5l-6 6m6-6l6 6M12 5v14' fill='none' stroke='currentColor' stroke-width='1.9' stroke-linecap='round' stroke-linejoin='round'/>"
        "</svg>"
    )
    if locate_target:
        locate_button = (
            "<button type='button' class='catalog-fab' "
            f"onclick='{escape(_scroll_action_js(str(locate_target)), quote=True)}' "
            f"title='{escape(str(locate_tooltip), quote=True)}' "
            f"aria-label='{escape(str(locate_tooltip), quote=True)}' "
            f"data-tooltip='{escape(str(locate_tooltip), quote=True)}' "
            f"data-scroll-target='{escape(str(locate_target), quote=True)}'>"
            f"{target_svg}"
            "</button>"
        )
    else:
        locate_button = (
            "<span class='catalog-fab catalog-fab-disabled' "
            f"title='{escape(str(locate_tooltip), quote=True)}' "
            f"aria-label='{escape(str(locate_tooltip), quote=True)}' "
            f"data-tooltip='{escape(str(locate_tooltip), quote=True)}'>"
            f"{target_svg}"
            "</span>"
        )
    top_button = (
        "<button type='button' class='catalog-fab' "
        f"onclick='{escape(_scroll_action_js(str(top_target)), quote=True)}' "
        "title='回到页面顶部' aria-label='回到页面顶部' data-tooltip='回到页面顶部' "
        f"data-scroll-target='{escape(str(top_target), quote=True)}'>"
        f"{top_svg}"
        "</button>"
    )
    return f"<div class='catalog-fab-stack'>{locate_button}{top_button}</div>"


def _render_floating_nav(
    st: Any,
    *,
    locate_target: str | None,
    locate_tooltip: str = "定位当前选中项",
    top_target: str = "catalog-page-top",
) -> None:
    st.markdown(
        _floating_nav_markup(
            locate_target=locate_target,
            locate_tooltip=locate_tooltip,
            top_target=top_target,
        ),
        unsafe_allow_html=True,
    )


def _selection_presence(
    selected_key: str,
    *,
    items: Sequence[Mapping[str, Any]],
    visible_items: Sequence[Mapping[str, Any]],
) -> tuple[bool, bool]:
    key = str(selected_key or "").strip()
    if not key:
        return False, False
    all_keys = {str(item.get("key", "") or "").strip() for item in items}
    visible_keys = {str(item.get("key", "") or "").strip() for item in visible_items}
    return key in all_keys, key in visible_keys


def _catalog_kind_from_target(*, target_key: str, target_kind: str = "") -> str:
    raw_kind = str(target_kind or "").strip().lower()
    if not raw_kind and "." in str(target_key):
        segments = str(target_key).split(".")
        raw_kind = segments[1] if segments[0] == "mlblack" and len(segments) > 1 else segments[0]
        raw_kind = raw_kind.strip().lower()
    return raw_kind if raw_kind in _KIND_LABELS else ""


def _select_catalog_entry(
    st: Any,
    *,
    target_key: str,
    target_kind: str = "",
) -> None:
    st.session_state["catalog_ui_selected"] = str(target_key or "")
    resolved_kind = _catalog_kind_from_target(target_key=target_key, target_kind=target_kind)
    if resolved_kind:
        st.session_state["catalog_ui_kind"] = resolved_kind


def _callback_select_entry(st: Any, *, target_key: str, target_kind: str = "") -> None:
    # Previous/next browse the current result set; relations own cross-kind jumps.
    st.session_state["catalog_ui_selected"] = str(target_key or "")


def _callback_reveal_selected(st: Any, *, scope: str, kind: str) -> None:
    st.session_state["catalog_ui_query"] = ""
    _clear_scope_kind_filters(st, scope=scope, kind=kind)


def _callback_locate_selected(st: Any) -> None:
    st.session_state[_PENDING_SCROLL_TARGET_KEY] = "catalog-results-anchor"


def _callback_pop_navigation(st: Any) -> None:
    target = _pop_navigation_stack(st)
    if target is not None:
        _select_catalog_entry(
            st,
            target_key=str(target.get("key", "") or ""),
            target_kind=str(target.get("kind", "") or ""),
        )


def _callback_restore_navigation(st: Any, *, index: int) -> None:
    target = _restore_navigation_index(st, index)
    if target is not None:
        _select_catalog_entry(
            st,
            target_key=str(target.get("key", "") or ""),
            target_kind=str(target.get("kind", "") or ""),
        )


def _callback_clear_selected(st: Any) -> None:
    st.session_state["catalog_ui_selected"] = _NO_SELECTION


def _callback_focus_relation_group(
    st: Any,
    *,
    scope: str,
    kind: str,
    relation_group: str,
) -> None:
    group = str(relation_group or "").strip()
    if not group:
        return
    normalized_scope = str(scope or "framework")
    normalized_kind = str(kind or _KIND_ALL)
    detail_tab_key = _view_state_key(normalized_scope, normalized_kind, "detail_tab")
    open_relations_key = _view_state_key(normalized_scope, normalized_kind, "open_relations")
    existing = tuple(
        str(value).strip()
        for value in _shared.normalize_csv_values(st.session_state.get(open_relations_key, ()))
        if str(value).strip()
    )
    merged: list[str] = list(existing)
    if group not in merged:
        merged.append(group)
    st.session_state[detail_tab_key] = "relations"
    st.session_state[open_relations_key] = tuple(merged)
    st.session_state[_PENDING_SCROLL_TARGET_KEY] = "catalog-detail-anchor"


def _callback_jump_relation(
    st: Any,
    *,
    current_entry: Mapping[str, Any] | None,
    target_key: str,
    target_kind: str = "",
    detail_tab: str | None = None,
) -> None:
    _push_navigation_stack(st, current_entry=current_entry)
    _select_catalog_entry(st, target_key=target_key, target_kind=target_kind)
    if detail_tab is not None:
        tab = _normalize_detail_tab(detail_tab)
        target_view = _view_state_key(str(st.session_state.get("catalog_ui_scope", "framework")),
                                     str(st.session_state.get("catalog_ui_kind", "all")), "detail_tab")
        st.session_state[target_view] = tab
        st.query_params["detail_tab"] = tab
    st.session_state[_PENDING_SCROLL_TARGET_KEY] = "catalog-detail-anchor"


def _callback_switch_kind(st: Any, *, target_kind: str) -> None:
    # Suggestions promise the same query in the target category, without a
    # hidden filter remembered from an earlier visit to that category.
    _clear_scope_kind_filters(st, scope=str(st.session_state.get("catalog_ui_scope", "framework")),
                              kind=str(target_kind or _KIND_ALL))
    st.session_state["catalog_ui_kind"] = str(target_kind or "")


def _callback_browse_kind(st: Any) -> None:
    target = str(st.session_state.get("catalog_ui::browse_kind", _KIND_ALL))
    _clear_scope_kind_filters(st, scope=str(st.session_state.get("catalog_ui_scope", "framework")), kind=target)
    st.session_state.update({"catalog_ui_kind": target, "catalog_ui_query": "",
                             "catalog_ui_field": "all", "catalog_ui_selected": ""})


def _callback_browse_subkind(st: Any) -> None:
    target = str(st.session_state.get("catalog_ui::browse_subkind", _KIND_ALL))
    _clear_scope_kind_filters(st, scope=str(st.session_state.get("catalog_ui_scope", "framework")), kind=target)
    st.session_state.update({"catalog_ui_kind": target, "catalog_ui_query": "",
                             "catalog_ui_field": "all", "catalog_ui_selected": ""})


def _callback_clear_filters(st: Any, *, scope: str, kind: str) -> None:
    _clear_scope_kind_filters(st, scope=scope, kind=kind)


def _callback_reset_search(st: Any) -> None:
    scope = str(st.session_state.get("catalog_ui_scope", "framework"))
    kind = str(st.session_state.get("catalog_ui_kind", _KIND_ALL))
    _clear_scope_kind_filters(st, scope=scope, kind=kind)
    st.session_state["catalog_ui_query"] = ""
    st.session_state["catalog_ui_field"] = "all"


def _raw_relation_neighbor_groups(entry: Mapping[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    source = entry or {}
    groups: dict[str, list[dict[str, Any]]] = {}
    for relation_name in ("companions", "required_companions"):
        rows: list[dict[str, Any]] = []
        for raw_key in tuple(source.get(relation_name, ()) or ()):
            key = str(raw_key or "").strip()
            if not key:
                continue
            rows.append(
                {
                    "key": key,
                    "kind": _catalog_kind_from_target(target_key=key),
                    "title": key,
                    "summary": "",
                    "fallback": True,
                }
            )
        if rows:
            groups[relation_name] = rows
    return groups


def _relation_neighbor_groups(
    *,
    entry: Mapping[str, Any] | None,
    neighbors: Mapping[str, Any] | None,
) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    companions = list((neighbors or {}).get("companions", ()) or ())
    linked_by = list((neighbors or {}).get("linked_by", ()) or ())
    if companions:
        groups["companions"] = companions
    if linked_by:
        groups["linked_by"] = linked_by
    for relation_name, rows in dict((neighbors or {}).get("relation_groups", {}) or {}).items():
        normalized_name = str(relation_name or "").strip()
        normalized_rows = list(rows or ())
        if normalized_name and normalized_rows:
            groups[normalized_name] = normalized_rows
    for relation_name, rows in _raw_relation_neighbor_groups(entry).items():
        groups.setdefault(str(relation_name), rows)
    return groups


def _entry_list_payload(entry: Any) -> dict[str, Any]:
    return {
        "key": str(getattr(entry, "key", "") or ""),
        "title": str(getattr(entry, "title", "") or ""),
        "kind": str(getattr(entry, "kind", "") or ""),
        "tags": tuple(getattr(entry, "tags", ()) or ()),
        "summary": str(getattr(entry, "summary", "") or ""),
        "minimal_wiring": tuple(getattr(entry, "minimal_wiring", ()) or ()),
        "example_entry": str(getattr(entry, "example_entry", "") or ""),
    }


def _entry_detail_payload(entry: Any) -> dict[str, Any]:
    return _entry_payload(entry)


def _load_source_info(
    profile: str,
    scope: str,
    project_path: str,
    include_global: bool,
    db_path: str,
    source_mode: str,
) -> dict[str, Any]:
    return catalog_source_info(
        profile=profile,
        **_catalog_source_options(scope, project_path, include_global, db_path, source_mode),
    )


_cached_source_info = _shell.memoize_loader(_load_source_info, maxsize=64)


def _load_summary(
    profile: str,
    scope: str,
    project_path: str,
    include_global: bool,
    db_path: str,
    source_mode: str,
) -> dict[str, Any]:
    return catalog_summary(
        profile=profile,
        **_catalog_source_options(scope, project_path, include_global, db_path, source_mode),
    )


_cached_summary = _shell.memoize_loader(_load_summary, maxsize=64)


def _load_schema(
    profile: str,
    scope: str,
    project_path: str,
    include_global: bool,
    db_path: str,
    source_mode: str,
) -> dict[str, Any]:
    return catalog_schema(
        profile=profile,
        **_catalog_source_options(scope, project_path, include_global, db_path, source_mode),
    )


_cached_schema = _shell.memoize_loader(_load_schema, maxsize=128)


def _load_facets(
    profile: str,
    scope: str,
    project_path: str,
    include_global: bool,
    kind: str,
    query: str,
    search_field: str,
    db_path: str,
    source_mode: str,
) -> dict[str, Any]:
    scoped_kind, scoped_filters = _navigation.query_scope(
        kind, available_kinds=tuple(_cached_summary(
            profile, scope, project_path, include_global, db_path, source_mode).get("by_kind", {})))
    return catalog_facets(
        profile=profile,
        **_catalog_source_options(scope, project_path, include_global, db_path, source_mode),
        kind=scoped_kind,
        field_filters=scoped_filters,
        query=query,
        search_field=search_field,
        fields=_PRIMARY_FILTER_FIELDS,
        limit_per_field=24,
    )


_cached_facets = _shell.memoize_loader(_load_facets, maxsize=256)


def _load_items(
    profile: str,
    scope: str,
    project_path: str,
    include_global: bool,
    kind: str,
    query: str,
    search_field: str,
    filters_key: tuple[tuple[str, tuple[str, ...]], ...],
    db_path: str,
    source_mode: str,
) -> tuple[dict[str, Any], ...]:
    scoped_kind, filters = _navigation.query_scope(
        kind, _shell.thaw_filters(filters_key), available_kinds=tuple(_cached_summary(
            profile, scope, project_path, include_global, db_path, source_mode).get("by_kind", {})))
    entries = (
        search_entries(
            query,
            profile=profile,
            **_catalog_source_options(scope, project_path, include_global, db_path, source_mode),
            kind=scoped_kind,
            field=search_field,
            limit=max(1, int(_cached_summary(profile, scope, project_path, include_global, db_path, source_mode).get("total", 0))),
            field_filters=filters,
        )
        if str(query).strip()
        else list_entries(
            profile=profile,
            **_catalog_source_options(scope, project_path, include_global, db_path, source_mode),
            kind=scoped_kind,
            limit=None,
            field_filters=filters,
        )
    )
    return tuple(_entry_list_payload(entry) for entry in entries)


_cached_items = _shell.memoize_loader(_load_items, maxsize=256)


def _load_selected_entry(
    profile: str,
    scope: str,
    project_path: str,
    include_global: bool,
    selected_key: str,
    db_path: str,
    source_mode: str,
) -> dict[str, Any] | None:
    key = str(selected_key or "").strip()
    if not key:
        return None
    entry = show_entry(
        key,
        profile=profile,
        **_catalog_source_options(scope, project_path, include_global, db_path, source_mode),
    )
    return None if entry is None else _entry_detail_payload(entry)


_cached_selected = _shell.memoize_loader(_load_selected_entry, maxsize=256)


def _load_neighbors(
    profile: str,
    scope: str,
    project_path: str,
    include_global: bool,
    selected_key: str,
    db_path: str,
    source_mode: str,
) -> dict[str, Any] | None:
    key = str(selected_key or "").strip()
    if not key:
        return None
    return catalog_neighbors(
        key,
        profile=profile,
        **_catalog_source_options(scope, project_path, include_global, db_path, source_mode),
    )


_cached_neighbors = _shell.memoize_loader(_load_neighbors, maxsize=256)


_cached_other_kind_hits = _shell.memoize_loader(_other_kind_hits, maxsize=256)


def _render_selection_float(
    st: Any,
    *,
    selection: Mapping[str, Any],
    selected_entry: Mapping[str, Any] | None,
    visible_items: Sequence[Mapping[str, Any]],
    scope: str,
    kind: str,
) -> None:
    selected_key = str(selection.get("selected_key", "") or "").strip()
    if not selected_key:
        return

    title = str((selected_entry or {}).get("title", "") or selected_key)
    row_index = selection.get("row_index")
    visible_rows = list(visible_items or ())
    if selection.get("visible", False) and isinstance(row_index, int) and len(visible_rows) > 1:
        nav_cols = st.columns((1.0, 1.0))
        prev_disabled = int(row_index) <= 0
        next_disabled = int(row_index) >= len(visible_rows) - 1
        prev_target = visible_rows[max(0, int(row_index) - 1)]
        next_target = visible_rows[min(len(visible_rows) - 1, int(row_index) + 1)]
        nav_cols[0].button(
            "上一项",
            key=f"catalog_ui::prev::{scope}::{kind}",
            width="stretch",
            disabled=prev_disabled,
            on_click=_callback_select_entry,
            kwargs={
                "st": st,
                "target_key": str(prev_target.get("key", "") or ""),
                "target_kind": str(prev_target.get("kind", "") or ""),
            },
        )
        nav_cols[1].button(
            "下一项",
            key=f"catalog_ui::next::{scope}::{kind}",
            width="stretch",
            disabled=next_disabled,
            on_click=_callback_select_entry,
            kwargs={
                "st": st,
                "target_key": str(next_target.get("key", "") or ""),
                "target_kind": str(next_target.get("kind", "") or ""),
            },
        )

    with st.expander("选中项操作", expanded=False):
        st.caption(title)
        stack = _navigation_stack(st)
        action_cols = st.columns((1.0, 1.0, 1.0))
        if selection.get("hidden", False):
            action_cols[0].button(
                "显示它",
                key=f"catalog_ui::reveal::{scope}::{kind}",
                width="stretch",
                on_click=_callback_reveal_selected,
                kwargs={"st": st, "scope": scope, "kind": kind},
            )
        else:
            action_cols[0].button(
                "定位到结果区",
                key=f"catalog_ui::locate_selection::{scope}::{kind}",
                width="stretch",
                on_click=_callback_locate_selected,
                kwargs={"st": st},
            )
        if stack:
            action_cols[1].button(
                "返回上一个",
                key=f"catalog_ui::back::{scope}::{kind}",
                width="stretch",
                on_click=_callback_pop_navigation,
                kwargs={"st": st},
            )
        else:
            action_cols[1].caption("跳转栈为空")
        action_cols[2].button(
            "清除选中",
            key=f"catalog_ui::clear_selected::{scope}::{kind}",
            width="stretch",
            on_click=_callback_clear_selected,
            kwargs={"st": st},
        )



def _callback_results_selection(st: Any, *, table_key: str, item_keys: Sequence[str]) -> None:
    rows = _selected_table_row_indices(st.session_state.get(table_key, {}))
    if rows and 0 <= int(rows[0]) < len(item_keys):
        st.session_state["catalog_ui_selected"] = item_keys[int(rows[0])]
    elif not rows:
        st.session_state["catalog_ui_selected"] = _NO_SELECTION


def _callback_results_choice(st: Any, *, choice_key: str) -> None:
    st.session_state["catalog_ui_selected"] = st.session_state.get(choice_key) or _NO_SELECTION


def _view_control_key(st: Any, *, state_key: str, value: object) -> str:
    key = state_key + "::control"
    if key in st.session_state and st.session_state[key] != value:
        st.session_state[key] = value
    return key


def _callback_view_control(st: Any, *, state_key: str, parameter: str) -> None:
    value = st.session_state[state_key + "::control"]
    st.session_state[state_key] = value
    # Query restoration runs before rendering. Commit the user's choice first
    # so the previous URL cannot overwrite a new widget value on that rerun.
    st.query_params[parameter] = str(value)


def _entry_description(entry: Mapping[str, Any], *, limit: int | None = None) -> str:
    """Use the primary-language summary in browsing; keep the source declaration intact."""
    summary = " ".join(str(entry.get("summary", "") or "").split())
    primary, separator, _ = summary.partition(" / ")
    if separator and any("\u4e00" <= char <= "\u9fff" for char in primary):
        summary = primary.rstrip(" /;")
    if limit and len(summary) > limit:
        summary = summary[:limit].rstrip("，。；、 ") + "…"
    return summary


def _callback_show_more(st: Any, *, page_size_key: str, total: int) -> None:
    count = min(total, _normalize_page_size(st.session_state.get(page_size_key, 50)) + 50)
    st.session_state[page_size_key] = count
    st.query_params["page_size"] = str(count)


def _render_results_table(
    st: Any,
    *,
    items: Sequence[Mapping[str, Any]],
    scope: str,
    kind: str,
    column_mode: str,
) -> str:
    raw_selected_key = str(st.session_state.get("catalog_ui_selected", "") or "")
    cleared_selection = raw_selected_key == _NO_SELECTION
    selected_key = raw_selected_key
    if selected_key == _NO_SELECTION:
        selected_key = ""
    item_keys = tuple(str(item.get("key", "")) for item in items)
    st.session_state["catalog_ui_result_keys"] = item_keys
    if not items:
        st.markdown("<div class='catalog-empty'>没有匹配的组件。试试更短的关键词，或清空筛选。</div>", unsafe_allow_html=True)
        return raw_selected_key

    if not selected_key and not cleared_selection:
        selected_key = item_keys[0]
    rows_digest = hashlib.sha256("\0".join(item_keys).encode()).hexdigest()[:12]
    if column_mode != "full":
        titles = {str(item.get("key", "")): str(item.get("title", "") or item.get("key", "")) for item in items}
        choice_key = f"catalog_ui::component_list::{scope}::{kind}::{rows_digest}"
        selected_choice = selected_key if selected_key in item_keys else None
        if choice_key in st.session_state and st.session_state[choice_key] != selected_choice:
            # External navigation updates the existing widget without replacing
            # it, so successive arrow-key selections keep keyboard focus.
            st.session_state[choice_key] = selected_choice
        with st.container(key="catalog_component_list", height=596, border=False):
            st.radio(
                "组件列表",
                options=item_keys,
                index=item_keys.index(selected_key) if selected_key in item_keys else None,
                format_func=lambda key: titles[key],
                captions=[_entry_description(item, limit=64) for item in items] if column_mode == "standard" else None,
                label_visibility="collapsed",
                key=choice_key,
                width="stretch",
                on_change=_callback_results_choice,
                kwargs={"st": st, "choice_key": choice_key},
            )
        return selected_key or (_NO_SELECTION if cleared_selection else "")

    try:
        import pandas as pd

        table_key = f"catalog_ui::results::{scope}::{kind}::{rows_digest}::{selected_key}"
        selected_rows = [item_keys.index(selected_key)] if selected_key in item_keys else []
        st.dataframe(
            pd.DataFrame(_result_rows(items, column_mode=column_mode)),
            width="stretch",
            height=min(596, max(145, 42 + 38 * len(items))),
            hide_index=True,
            column_config={"序号": None, "标题": st.column_config.TextColumn("组件", width="medium"),
                           "Key": st.column_config.TextColumn("标识", width="medium"),
                           "示例": st.column_config.TextColumn("使用示例", width="small"),
                           "分类": st.column_config.TextColumn("分类", width="small"),
                           "标签": st.column_config.TextColumn("标签", width="medium")},
            on_select=lambda: _callback_results_selection(st, table_key=table_key, item_keys=item_keys),
            selection_mode="single-row",
            selection_default={"selection": {"rows": selected_rows}},
            row_height=38,
            key=table_key,
        )
    except Exception:
        st.table(_result_rows(items, column_mode=column_mode))

    if not selected_key and not cleared_selection:
        selected_key = str(items[0].get("key", ""))
    return selected_key or (_NO_SELECTION if cleared_selection else "")


def _render_sequence(st: Any, *, title: str, values: Sequence[str]) -> None:
    cleaned = [str(value).strip() for value in values if str(value).strip() and str(value).strip().lower() not in {"(none)", "none", "无"}]
    if not cleaned:
        return
    st.markdown(f"<div class='catalog-section-title'>{escape(title)}</div>", unsafe_allow_html=True)
    for value in cleaned:
        st.markdown(f"- {value}")


def _render_usage_overview(st: Any, entry: Mapping[str, Any], *, include_wiring: bool = True) -> None:
    """Present declared guidance and structural checks without running a recipe."""
    _render_sequence(st, title=_field_label("use_when"), values=tuple(entry.get("use_when", ()) or ()))
    wiring = tuple(str(value) for value in entry.get("minimal_wiring", ()) or () if str(value).strip())
    if wiring and include_wiring:
        st.markdown("<div class='catalog-section-title'>最小接线</div>", unsafe_allow_html=True)
        code = "\n".join(wiring)
        if hasattr(st, "code"):
            st.code(code, language="python", wrap_lines=True)
        else:
            st.markdown(code)
    for field in ("operations", "config_keys"):
        values = tuple(str(value) for value in entry.get(field, ()) or ()
                       if str(value).strip() and str(value).strip().lower() not in {"(none)", "none", "无"})
        if values:
            st.markdown(f"<div class='catalog-section-title'>{_field_label(field)}</div>", unsafe_allow_html=True)
            st.markdown(_chips(values), unsafe_allow_html=True)
    _render_sequence(st, title=_field_label("boundaries"), values=tuple(entry.get("boundaries", ()) or ()))
    role = str(entry.get("role", "") or "").strip()
    _render_sequence(st, title=_field_label("role"), values=(role,) if role else ())
    concepts = tuple(entry.get("concepts", ()) or ())
    if concepts:
        st.markdown("<div class='catalog-section-title'>相关概念</div>", unsafe_allow_html=True)
        st.markdown(_chips(concepts), unsafe_allow_html=True)
    st.markdown(f"<div class='catalog-section-title'>{_field_label('wiring_status')}</div>", unsafe_allow_html=True)
    st.markdown(wiring_status_label(str(entry.get("wiring_status", "unverified") or "unverified")))
    for note in entry.get("wiring_notes", ()) or ():
        st.caption(str(note))
    st.caption(WIRING_STATUS_NOTE)


def _render_navigation_stack(st: Any, *, current_key: str) -> None:
    stack = _navigation_stack(st)
    if not stack:
        return
    st.markdown("<div class='catalog-section-title'>跳转栈</div>", unsafe_allow_html=True)
    for index, item in enumerate(reversed(stack[-6:])):
        real_index = len(stack) - 1 - index
        label = str(item.get("title", "") or item.get("key", ""))
        target_key = str(item.get("key", "") or "")
        if not target_key:
            continue
        button_label = f"返回 {label} · {target_key}"
        if target_key == current_key:
            st.caption(f"当前：{button_label}")
            continue
        st.button(
            button_label,
            key=f"catalog_ui::stack::{real_index}::{target_key}",
            width="stretch",
            on_click=_callback_restore_navigation,
            kwargs={"st": st, "index": real_index},
        )


def _render_detail_header(st: Any, entry: Mapping[str, Any] | None) -> None:
    st.markdown(f"<div id='{_page.DETAIL_SECTION_ID}'></div><div id='catalog-detail-anchor'></div>", unsafe_allow_html=True)
    if not entry:
        return
    entry_key = str(entry.get("key", "") or "")
    title = str(entry.get("title", "") or entry_key)
    kind_label = _kind_label(str(entry.get("kind", "") or ""))
    st.markdown(
        "<div class='catalog-entry-header'>"
        f"<div class='catalog-entry-meta'>{escape(kind_label)}</div>"
        f"<h2 class='catalog-entry-title'>{escape(title)}</h2>"
        f"<div class='catalog-entry-key'>{escape(entry_key)}</div>"
        f"<p class='catalog-entry-summary'>{escape(_entry_description(entry))}</p></div>",
        unsafe_allow_html=True,
    )


def _render_detail(
    st: Any,
    *,
    entry: Mapping[str, Any] | None,
    neighbors: Mapping[str, Any] | None,
    source_info: Mapping[str, Any],
    deep_link_query: str,
    scope: str,
    kind: str,
    detail_tab: str,
    expanded_relation_groups: Sequence[str],
) -> None:
    if not entry:
        st.info("当前没有选中条目。")
        return

    entry_key = str(entry.get("key", "") or "")
    import_path = str(entry.get("import_path", "") or "")
    hosted = _hosted_mode()
    source_path = None if hosted else _resolve_source_file(
        import_path, project_root=str(source_info.get("project_root", "") or "") or None,
    )
    badges = _source_badges(entry, source_info)

    current_tab = _normalize_detail_tab(detail_tab)
    expanded_groups = {
        str(value).strip()
        for value in expanded_relation_groups
        if str(value).strip()
    }
    # Usage links land on the overview tab. Keep the same navigation history
    # available there instead of requiring a detour through the relations tab.
    _render_navigation_stack(st, current_key=entry_key)

    if current_tab == "overview":
        _examples.render_examples(st, entry,
                                  profile=str(st.session_state.get("catalog_ui_profile", "default")))
        example_state = _examples.examples_snapshot()
        if example_state.get("available"):
            from nsgablack.catalog.usage_navigation import render_documentation_navigation
            available_entries = _cached_items(
                str(st.session_state.get("catalog_ui_profile", "default")), scope,
                str(st.session_state.get("catalog_ui_project_path", "") or ""),
                bool(st.session_state.get("catalog_ui_include_global", False)),
                "all", "", "all", (),
                str(st.session_state.get("catalog_ui_db_path", "") or ""),
                str(st.session_state.get("catalog_ui_source_mode", "") or ""),
            )
            render_documentation_navigation(
                st, entry=entry, index=example_state["index"], available_entries=available_entries,
                on_navigate=_callback_jump_relation, navigation_kwargs={"st": st, "current_entry": entry},
            )
        related = {}
        for row in (*dict((neighbors or {}).get("relation_groups", {})).get("assembly_uses", ()),
                    *((neighbors or {}).get("companions", ()) or ())):
            if row.get("key"):
                related.setdefault(row["key"], row)
        if related:
            st.markdown("**这段用法关联的组件**")
            st.caption("按需查看配套组件的接入方式；这里的关联不表示必须全部启用。")
            rows = tuple(related.items())

            def render_related(values):
                for key, row in values:
                    st.button(str(row.get("title") or key), key=f"catalog_ui::usage_related::{entry_key}::{key}",
                              on_click=_callback_jump_relation,
                              kwargs={"st": st, "current_entry": entry, "target_key": key,
                                      "target_kind": str(row.get("kind") or ""), "detail_tab": "overview"})

            render_related(rows[:5])
            if len(rows) > 5:
                with st.expander(f"查看其余 {len(rows) - 5} 个关联组件（共 {len(rows)} 个）", expanded=False):
                    render_related(rows[5:])

    elif current_tab == "interface":
        _render_usage_overview(st, entry, include_wiring=True)
        _curation.render_note(st, entry_key=entry_key,
                              profile=str(st.session_state.get("catalog_ui_profile", "default")),
                              on_navigate=_callback_jump_relation,
                              navigation_kwargs={"st": st, "current_entry": entry})
        contract_fields = ("context_requires", "context_provides", "context_mutates", "context_cache",
                           "context_notes", "artifact_requires", "artifact_provides", "phase_in", "phase_out")
        if any(entry.get(field) for field in contract_fields):
            with st.expander("契约与依赖", expanded=False):
                for field in contract_fields:
                    _render_sequence(st, title=_field_label(field), values=tuple(entry.get(field, ()) or ()))
        declared_contract = entry.get("contract", {}) or {}
        declared_metadata = entry.get("metadata", {}) or {}
        if declared_contract or declared_metadata:
            with st.expander("原始组件声明", expanded=False):
                st.json({"contract": declared_contract, "metadata": declared_metadata})

    elif current_tab == "relations":
        neighbor_groups = _relation_neighbor_groups(entry=entry, neighbors=neighbors)
        used_keys = {row.get("key") for row in neighbor_groups.get("assembly_uses", ())}
        declared_keys = {row.get("key") for row in neighbor_groups.get("companions", ())}
        if used_keys and neighbor_groups.get("companions"):
            neighbor_groups["companions"] = [row for row in neighbor_groups["companions"] if row.get("key") not in used_keys]
        relation_labels = dict((neighbors or {}).get("relation_labels", {}) or {})
        relation_cards = tuple((neighbors or {}).get("relation_cards", ()) or ())
        relation_chain_cards = tuple((neighbors or {}).get("relation_chain_cards", ()) or ())
        st.caption("配套组件来自目录声明；“用法片段使用了”来自实际代码调用。"
                   "下方契约关系表示输入输出的键匹配，仍需按各组件的接入条件装配。")
        if not neighbor_groups:
            st.info("当前公开声明和用法代码中尚未找到可跳转的组件关系。可先在“用法”页核对装配位置与输入条件。")
        if (neighbors or {}).get("missing_companions"):
            st.caption("当前目录范围未收录的关联项：" + "、".join((neighbors or {})["missing_companions"]))
        if relation_chain_cards or relation_cards:
            with st.expander("查看上下文、Artifact 与阶段契约概览", expanded=False):
                _render_relation_chain_cards(
                    st, relation_chain_cards, current_entry=entry, scope=scope, kind=kind,
                    expanded_relation_groups=tuple(expanded_groups),
                )
                _render_relation_cards(st, relation_cards)
        priority = {"assembly_uses": 0, "companions": 1, "assembly_used_by": 2, "linked_by": 3}
        ordered_groups = sorted(neighbor_groups.items(), key=lambda item: priority.get(item[0], 4))
        for relation_name, rows in ordered_groups:
            if not rows:
                continue
            with st.expander(f"{_relation_group_label(relation_name, relation_labels)} ({len(rows)})",
                             expanded=relation_name in expanded_groups or relation_name in {"assembly_uses", "companions"}):
                for index, item in enumerate(rows):
                    key = str(item.get("key", "") or "")
                    label = str(item.get("title", "") or key)
                    summary = str(item.get("summary", "") or "").strip()
                    relation_note = str(item.get("relation_note", "") or "").strip()
                    if not key:
                        continue
                    cols = st.columns((0.72, 0.28))
                    with cols[0]:
                        st.markdown(f"**{label or key}**")
                        st.caption(f"{_kind_label(str(item.get('kind', '') or ''))} | {key}")
                        if relation_note:
                            if relation_name == "assembly_uses":
                                st.caption("本组件的用法代码创建或调用了它。" +
                                           ("目录也将它列为配套组件。" if key in declared_keys else ""))
                            elif relation_name == "assembly_used_by":
                                st.caption("它的用法代码使用了当前组件。")
                            else:
                                st.caption(relation_note)
                        if summary:
                            st.caption(_entry_description(item, limit=160))
                        evidence = tuple(item.get("evidence", ()) or ())
                        if evidence:
                            with st.expander("查看这条关系的依据", expanded=False):
                                for proof in evidence:
                                    source = proof.get("source_path") or "组件的 minimal_wiring"
                                    st.caption(f"{source} · 第 {proof.get('line', '?')} 行 · {proof.get('call', '')}")
                    with cols[1]:
                        st.button(
                            "查看用法",
                            key=f"catalog_ui::jump::{entry_key}::{relation_name}::{index}::{key}",
                            width="stretch",
                            on_click=_callback_jump_relation,
                            kwargs={
                                "st": st,
                                "current_entry": entry,
                                "target_key": key,
                                "target_kind": str(item.get("kind", "") or ""),
                                "detail_tab": "overview",
                            },
                        )

    else:
        st.markdown("<div class='catalog-section-title'>来源与链接</div>", unsafe_allow_html=True)
        if badges:
            st.markdown(_chips(badges), unsafe_allow_html=True)
        link_cols = st.columns((1.1, 0.95, 0.95))
        with link_cols[0]:
            _copy_current_url(st, key=f"catalog_ui::copy_link::{scope}::{kind}::{entry_key}")
        with link_cols[1]:
            if source_path and st.button("打开 Source File", key=f"catalog_ui::open::{entry_key}", width="stretch"):
                if _open_source_file(source_path):
                    try:
                        st.toast("已打开 source file")
                    except Exception:
                        st.success("已打开 source file")
                else:
                    st.warning("打开 source file 失败。")
        with link_cols[2]:
            if source_path and st.button("定位到 Source File", key=f"catalog_ui::reveal::{entry_key}", width="stretch"):
                if _reveal_source_file(source_path):
                    try:
                        st.toast("已定位到 source file")
                    except Exception:
                        st.success("已定位到 source file")
                else:
                    st.warning("定位 source file 失败。")

        st.text_input("Deep-Link", value=deep_link_query, key=f"catalog_ui::deeplink::{entry_key}")
        st.markdown(f"<div class='catalog-section-title'>{_field_label('import_path')}</div>", unsafe_allow_html=True)
        st.code(import_path, language=None)
        if hosted:
            st.caption("服务器只读视图不解析或打开本地源码文件。")
        elif source_path is not None:
            st.markdown("<div class='catalog-section-title'>Source File</div>", unsafe_allow_html=True)
            st.code(str(source_path), language=None)
        else:
            st.markdown("<div class='catalog-section-title'>Source File</div>", unsafe_allow_html=True)
            st.caption("当前条目暂时无法解析到本地 source file。")



def _callback_search_intent(st: Any, *, query: str, target_key: str) -> None:
    scope = str(st.session_state.get("catalog_ui_scope", "framework"))
    for kind in (str(st.session_state.get("catalog_ui_kind", _KIND_ALL)), _KIND_ALL):
        _clear_scope_kind_filters(st, scope=scope, kind=kind)
    st.session_state.update({"catalog_ui_query": query, "catalog_ui_field": "all",
                             "catalog_ui_kind": _KIND_ALL, "catalog_ui_selected": target_key})
    for key in tuple(st.query_params):
        if str(key).startswith("f_"):
            del st.query_params[key]
    st.query_params.update({"query": query, "field": "all", "kind": _KIND_ALL,
                            "selected": target_key, "detail_tab": "overview"})
    st.session_state[_view_state_key(scope, _KIND_ALL, "detail_tab")] = "overview"


def _render_workbench_controls(st: Any, *, summary: Mapping[str, Any], kinds: Sequence[str],
                               current_kind: str, hosted: bool) -> dict[str, Any]:
    """Keep discovery on the main surface and configuration in the sidebar."""
    values = {key: st.session_state[f"catalog_ui_{key}"] for key in
              ("scope", "profile", "query", "field", "project_path", "include_global", "db_path", "source_mode")}
    with st.sidebar:
        values["profile"] = st.selectbox("目录范围", options=("default", "framework-core"),
            index=0 if values["profile"] == "default" else 1,
            format_func=lambda value: "全部组件与示例" if value == "default" else "仅框架主干")
        counts = summary.get("by_kind", {})
        _examples.render_material_status(st)
        _curation.render_status(st, profile=str(values["profile"]))
        st.markdown("<div class='catalog-section-title'>浏览分类</div>", unsafe_allow_html=True)
        primary = _navigation.group_for_kind(current_kind)
        grouped_counts = _navigation.group_counts(counts)
        if st.session_state.get("catalog_ui::browse_kind") != primary:
            st.session_state["catalog_ui::browse_kind"] = primary
        selected_group = st.radio("分类", options=list(_navigation.PRIMARY_OPTIONS),
            index=_navigation.PRIMARY_OPTIONS.index(primary),
            format_func=lambda value: f"{_navigation.group_title(value)} · {grouped_counts[value]}",
            key="catalog_ui::browse_kind", on_change=_callback_browse_kind, kwargs={"st": st},
            label_visibility="collapsed")
        values["kind"] = selected_group
        if selected_group != _KIND_ALL:
            subkinds = (selected_group, *_navigation.member_kinds(selected_group, kinds))
            selected_kind = current_kind if current_kind in subkinds else selected_group
            if st.session_state.get("catalog_ui::browse_subkind") != selected_kind:
                st.session_state["catalog_ui::browse_subkind"] = selected_kind
            values["kind"] = st.selectbox("组件类型", options=list(subkinds),
                index=subkinds.index(selected_kind),
                format_func=lambda value: (f"本组全部 · {grouped_counts[selected_group]}" if value == selected_group
                                          else f"{_kind_label(value)} · {counts.get(value, 0)}"),
                key="catalog_ui::browse_subkind", on_change=_callback_browse_subkind, kwargs={"st": st})
        st.caption("点击分类浏览完整列表；切换分类会清除搜索条件。")
        if not hosted:
            with st.expander("数据源与项目", expanded=False):
                values["scope"] = st.radio("视图", options=("framework", "project"),
                    index=0 if values["scope"] == "framework" else 1, format_func=_scope_label, horizontal=True)
                values["project_path"] = st.text_input("Project Path", value=values["project_path"],
                    disabled=values["scope"] != "project")
                values["include_global"] = st.checkbox("项目视图并入框架条目", value=values["include_global"],
                    disabled=values["scope"] != "project")
                db_disabled = values["scope"] == "project" and not values["include_global"]
                values["db_path"] = st.text_input("DB Path / URL", value=values["db_path"], disabled=db_disabled)
                mode = str(values["source_mode"] or "")
                values["source_mode"] = st.selectbox("Source Mode", options=list(_SOURCE_MODE_OPTIONS),
                    index=_SOURCE_MODE_OPTIONS.index(mode) if mode in _SOURCE_MODE_OPTIONS else 0,
                    format_func=_source_mode_label, disabled=db_disabled)
        st.markdown(f"<div id='{_page.SECONDARY_CONTROLS_ROW_ID}' class='catalog-sidebar-note'>"
                    f"{'服务器只读预览' if hosted else '本地组件目录'} · {int(summary.get('total', 0))} 条目</div>",
                    unsafe_allow_html=True)
        if hosted:
            st.caption("服务器只读模式读取已发布 Catalog 数据库；组件定义来自框架源码同步。"
                       if _hosted_source_values()["source_mode"] == "only" else
                       "服务器只读模式固定读取框架 registry，不连接项目或数据库。")

    _page.render_top_anchor(st)
    with st.container(key="catalog_topbar"):
        st.markdown(f"<div id='{_page.HERO_SECTION_ID}' class='catalog-heading'>"
                    "<div><div class='heading-kicker'>WORKSPACE / CATALOG</div>"
                    "<h1 class='heading-title'>组件目录</h1>"
                    "<p class='heading-subtitle'>查找算法与组件，查看接口、装配方式和支持边界。</p></div>"
                    f"<span class='catalog-mode-badge'>{'只读预览' if hosted else _scope_label(str(values['scope']))}</span>"
                    "</div>", unsafe_allow_html=True)
    with st.container(key="catalog_search"):
        st.markdown(f"<div id='{_page.PRIMARY_CONTROLS_ROW_ID}'></div>", unsafe_allow_html=True)
        search_cols = st.columns((4, 1.1, 0.9), gap="small")
        values["query"] = search_cols[0].text_input("搜索组件", value=str(values["query"] or ""),
            placeholder="搜索名称、用途或想法，例如：贝叶斯、精英池、GA + VNS", label_visibility="collapsed")
        field = str(values["field"] or "all")
        values["field"] = search_cols[1].selectbox("搜索范围", options=list(_SEARCH_FIELD_LABELS),
            index=list(_SEARCH_FIELD_LABELS).index(field) if field in _SEARCH_FIELD_LABELS else 0,
            format_func=_search_field_label, label_visibility="collapsed")
        search_cols[2].button("重置搜索", key="catalog_ui::reset_search", width="stretch",
                              on_click=_callback_reset_search, kwargs={"st": st})
        quick = (("贝叶斯优化", "贝叶斯引导", "adapter.bayesian_optimization"),
                 ("GA + VNS 编排", "GA停滞VNS精修", "adapter.search_plan"),
                 ("解池操作", "解池", "tool.solution_pool"),
                 ("扩展 Unit", "种群扩展字段", "tool.population_change"))
        with st.container(key="catalog_intents"):
            quick_cols = st.columns(len(quick), gap="small")
            for col, (label, query, target) in zip(quick_cols, quick):
                col.button(label, key=f"catalog_ui::intent::{target}", width="stretch",
                    on_click=_callback_search_intent, kwargs={"st": st, "query": query, "target_key": target})
    return values


def _render_sidebar_facets(st: Any, *, available: Sequence[tuple[str, list[str]]], scope: str, kind: str) -> None:
    active = _shared.collect_session_filters(st, scope=scope, kind=kind,
                                            facet_fields=_PRIMARY_FILTER_FIELDS, multi_value=True)
    with st.sidebar:
        st.markdown(f"<div id='{_page.FILTER_SECTION_ID}' class='catalog-section-title'>FILTER · 精细筛选</div>",
                    unsafe_allow_html=True)
        with st.expander(f"字段筛选{f' · {len(active)} 项' if active else ''}", expanded=bool(active)):
            if not available:
                st.caption("当前没有可用的筛选项。")
            for field_name, options in available:
                state_key = f"catalog_ui::facet::{scope}::{kind}::{field_name}"
                if state_key not in st.session_state:
                    st.session_state[state_key] = []
                st.multiselect(_field_label(field_name), options=options, key=state_key)
            st.button("清空字段筛选", width="stretch", on_click=_callback_clear_filters,
                      kwargs={"st": st, "scope": scope, "kind": kind})


def run_dashboard(argv: Sequence[str] | None = None) -> None:
    args = _parse_args(argv)
    hosted = _hosted_mode()
    st = _require_streamlit()
    _set_page_config(st)
    _inject_style(st)

    # The assembly workbench is a separate workspace. Browsing Catalog still
    # performs no trial execution and does not construct algorithm Units.
    requested_workspace = "装配实验台" if st.query_params.get("view") == "lab" else "组件目录"
    if "view" in st.query_params:
        st.session_state["catalog_ui::workspace"] = requested_workspace
    st.session_state.setdefault("catalog_ui::workspace", requested_workspace)
    def _workspace_changed():
        if st.session_state["catalog_ui::workspace"] == "装配实验台":
            st.query_params["view"] = "lab"
        elif "view" in st.query_params:
            del st.query_params["view"]
    st.sidebar.markdown(WORKSPACE_BRAND, unsafe_allow_html=True)
    st.sidebar.radio("工作区", ("组件目录", "装配实验台"), key="catalog_ui::workspace",
                     on_change=_workspace_changed)
    if st.session_state["catalog_ui::workspace"] == "装配实验台":
        from nsgablack.catalog.lab_ui import render_workbench
        render_workbench(st, hosted=hosted)
        return

    query_params, query_filters = _read_query_params(st)
    st.session_state.setdefault("catalog_ui_profile", str(query_params.get("profile", args.profile or "framework-core")))
    st.session_state.setdefault("catalog_ui_scope", str(query_params.get("scope", args.scope or "framework")))
    st.session_state.setdefault("catalog_ui_kind", str(query_params.get("kind", args.kind or _KIND_ALL)))
    st.session_state.setdefault("catalog_ui_query", str(query_params.get("query", args.query or "")))
    st.session_state.setdefault("catalog_ui_field", str(query_params.get("field", args.field or "all")))
    st.session_state.setdefault("catalog_ui_selected", str(query_params.get("selected", "")))
    st.session_state.setdefault("catalog_ui_project_path", str(query_params.get("project_path", args.project_path or "")))
    st.session_state.setdefault(
        "catalog_ui_include_global",
        str(query_params.get("include_global", "1" if args.include_global else "")).strip().lower() in {"1", "true", "yes", "on"},
    )
    st.session_state.setdefault("catalog_ui_db_path", str(query_params.get("db_path", args.db_path or "")))
    st.session_state.setdefault("catalog_ui_source_mode", str(query_params.get("source_mode", args.source_mode or "")))
    # Restored Streamlit sessions are untrusted source selection too.
    _enforce_hosted_session(st)
    st.session_state.setdefault(_NAV_STACK_KEY, [])
    if str(query_params.get("nav_action", "") or "").strip().lower() == _NAV_ACTION_LOCATE_SELECTED:
        st.session_state[_PENDING_LOCATE_KEY] = True

    current_profile = str(st.session_state["catalog_ui_profile"] or "framework-core")
    current_scope = str(st.session_state["catalog_ui_scope"] or "framework")
    current_project_path = str(st.session_state["catalog_ui_project_path"] or "")
    current_include_global = bool(st.session_state["catalog_ui_include_global"])
    current_db_path = str(st.session_state["catalog_ui_db_path"] or "")
    current_source_mode = str(st.session_state["catalog_ui_source_mode"] or "")

    summary = _cached_summary(
        current_profile,
        current_scope,
        current_project_path,
        current_include_global,
        current_db_path,
        current_source_mode,
    )
    source_info = _cached_source_info(
        current_profile,
        current_scope,
        current_project_path,
        current_include_global,
        current_db_path,
        current_source_mode,
    )
    schema = _cached_schema(
        current_profile,
        current_scope,
        current_project_path,
        current_include_global,
        current_db_path,
        current_source_mode,
    )
    schema_kinds = tuple(str(kind) for kind in schema.get("kinds", ()) if str(kind).strip())
    kinds = _ordered_kinds(schema_kinds or _KIND_ORDER[1:])
    current_kind = _pick_default_kind(str(st.session_state["catalog_ui_kind"]), kinds)
    st.session_state["catalog_ui_kind"] = current_kind
    _shared.sync_query_filters_to_session(
        st,
        scope=current_scope,
        kind=current_kind,
        facet_fields=_PRIMARY_FILTER_FIELDS,
        # URL filters initialize their own category only. Thereafter widget
        # session state owns edits; an old URL must not overwrite them on rerun.
        query_filters=(query_filters if str(query_params.get("kind", current_kind)) == current_kind
                       and str(query_params.get("scope", current_scope)) == current_scope else {}),
        multi_value=True,
    )
    sort_by_key = _view_state_key(current_scope, current_kind, "sort_by")
    sort_dir_key = _view_state_key(current_scope, current_kind, "sort_dir")
    detail_tab_key = _view_state_key(current_scope, current_kind, "detail_tab")
    open_relations_key = _view_state_key(current_scope, current_kind, "open_relations")
    column_mode_key = _view_state_key(current_scope, current_kind, "column_mode")
    page_size_key = _view_state_key(current_scope, current_kind, "page_size")
    results_collapse_key = _view_state_key(current_scope, current_kind, "results_collapse")
    st.session_state.setdefault(column_mode_key, _normalize_column_mode(args.column_mode))
    st.session_state.setdefault(page_size_key, _normalize_page_size(args.page_size))
    st.session_state.setdefault(results_collapse_key, _normalize_results_collapse(args.results_collapse))
    if bool(st.session_state.get(_PENDING_LOCATE_KEY)):
        st.session_state[results_collapse_key] = "expanded"
    sort_by_value = _normalize_sort_by(query_params.get("sort_by", st.session_state.get(sort_by_key, _shared.DEFAULT_SORT_BY)))
    sort_dir_value = _normalize_sort_dir(query_params.get("sort_dir", st.session_state.get(sort_dir_key, _shared.DEFAULT_SORT_DIR)))
    detail_tab_value = _normalize_detail_tab(query_params.get("detail_tab", st.session_state.get(detail_tab_key, _shared.DEFAULT_DETAIL_TAB)))
    open_relation_values = (
        _shared.normalize_csv_values(query_params.get("open_relations", st.session_state.get(open_relations_key, ())))
        if "open_relations" in query_params or open_relations_key in st.session_state
        else ()
    )
    column_mode_value = _normalize_column_mode(query_params.get("column_mode", st.session_state.get(column_mode_key, _shared.DEFAULT_COLUMN_MODE)))
    page_size_value = _normalize_page_size(query_params.get("page_size", st.session_state.get(page_size_key, _shared.DEFAULT_PAGE_SIZE)))
    results_collapse_value = _normalize_results_collapse(
        query_params.get("results_collapse", st.session_state.get(results_collapse_key, _shared.DEFAULT_RESULTS_COLLAPSE))
    )
    if bool(st.session_state.get(_PENDING_LOCATE_KEY)):
        results_collapse_value = "expanded"
    if st.session_state.get(sort_by_key) != sort_by_value:
        st.session_state[sort_by_key] = sort_by_value
    if st.session_state.get(sort_dir_key) != sort_dir_value:
        st.session_state[sort_dir_key] = sort_dir_value
    if st.session_state.get(detail_tab_key) != detail_tab_value:
        st.session_state[detail_tab_key] = detail_tab_value
    if tuple(st.session_state.get(open_relations_key, ())) != tuple(open_relation_values):
        st.session_state[open_relations_key] = tuple(open_relation_values)
    if st.session_state.get(column_mode_key) != column_mode_value:
        st.session_state[column_mode_key] = column_mode_value
    if _normalize_page_size(st.session_state.get(page_size_key, _shared.DEFAULT_PAGE_SIZE)) != page_size_value:
        st.session_state[page_size_key] = page_size_value
    if st.session_state.get(results_collapse_key) != results_collapse_value:
        st.session_state[results_collapse_key] = results_collapse_value

    controls = _render_workbench_controls(st, summary=summary, kinds=kinds, current_kind=current_kind, hosted=hosted)
    scope, profile, kind, query, field = (controls[key] for key in ("scope", "profile", "kind", "query", "field"))
    project_path, include_global, db_path, source_mode = (controls[key] for key in
        ("project_path", "include_global", "db_path", "source_mode"))

    state_changed = False
    updates = {
        "catalog_ui_scope": scope,
        "catalog_ui_profile": profile,
        "catalog_ui_kind": kind,
        "catalog_ui_query": query,
        "catalog_ui_field": field,
        "catalog_ui_project_path": project_path,
        "catalog_ui_include_global": include_global,
        "catalog_ui_db_path": db_path,
        "catalog_ui_source_mode": source_mode,
    }
    if hosted:
        updates.update({f"catalog_ui_{key}": value for key, value in _hosted_source_values().items()})
    for key, value in updates.items():
        if st.session_state.get(key) != value:
            st.session_state[key] = value
            state_changed = True
    if state_changed:
        _rerun(st)

    if current_scope == "project" and not bool(source_info.get("project_found", False)):
        st.warning("当前没有发现正式 Project/Case catalog。请提供 Project Path，或在项目目录内启动页面。")
    db_error = str(source_info.get("db_error", "") or "").strip()
    db_stale_reason = str(source_info.get("db_stale_reason", "") or "").strip()
    if db_stale_reason:
        st.warning(
            f"DB catalog 快照已过期，已只读回退到 "
            f"{str(source_info.get('effective_source', 'registry'))}：{db_stale_reason}"
        )
    elif db_error:
        st.warning(f"DB catalog 当前不可用，已回退到 {str(source_info.get('effective_source', 'registry'))}：{db_error}")
    elif not hosted:
        st.sidebar.caption(f"Current source: {source_info.get('effective_source', 'registry')}")

    facet_payload = _cached_facets(
        current_profile,
        current_scope,
        current_project_path,
        current_include_global,
        current_kind,
        str(st.session_state["catalog_ui_query"] or ""),
        str(st.session_state["catalog_ui_field"] or "all"),
        current_db_path,
        current_source_mode,
    )
    filter_fields_with_options: list[tuple[str, list[str]]] = []
    for field_name in _PRIMARY_FILTER_FIELDS:
        options = [
            str(item.get("value", ""))
            for item in facet_payload.get("facets", {}).get(field_name, [])
            if str(item.get("value", "")).strip()
        ]
        if options:
            filter_fields_with_options.append((field_name, options))
    _render_sidebar_facets(st, available=filter_fields_with_options, scope=current_scope, kind=current_kind)
    field_filters = _shared.collect_session_filters(
        st,
        scope=current_scope,
        kind=current_kind,
        facet_fields=_PRIMARY_FILTER_FIELDS,
        multi_value=True,
    )

    with st.sidebar.expander("显示设置", expanded=False):
        sort_cols = st.columns((1, 1))
        current_sort_by = _normalize_sort_by(st.session_state.get(sort_by_key, _shared.DEFAULT_SORT_BY))
        current_sort_dir = _normalize_sort_dir(st.session_state.get(sort_dir_key, _shared.DEFAULT_SORT_DIR))
        sort_by = sort_cols[0].selectbox(
            "结果排序",
            options=list(_SORT_OPTIONS),
            index=list(_SORT_OPTIONS).index(current_sort_by),
            format_func=_sort_label,
            key=_view_control_key(st, state_key=sort_by_key, value=current_sort_by),
            on_change=_callback_view_control,
            kwargs={"st": st, "state_key": sort_by_key, "parameter": "sort_by"},
        )
        sort_dir = sort_cols[1].radio(
            "方向",
            options=("asc", "desc"),
            index=0 if current_sort_dir == "asc" else 1,
            horizontal=True,
            format_func=lambda value: "升序" if value == "asc" else "降序",
            key=_view_control_key(st, state_key=sort_dir_key, value=current_sort_dir),
            on_change=_callback_view_control,
            kwargs={"st": st, "state_key": sort_dir_key, "parameter": "sort_dir"},
        )
        st.session_state[sort_by_key] = sort_by
        st.session_state[sort_dir_key] = sort_dir

        display_cols = st.columns((1, 1))
        current_column_mode = _normalize_column_mode(st.session_state.get(column_mode_key, _shared.DEFAULT_COLUMN_MODE))
        current_page_size = _normalize_page_size(st.session_state.get(page_size_key, _shared.DEFAULT_PAGE_SIZE))
        current_results_collapse = _normalize_results_collapse(st.session_state.get(results_collapse_key, _shared.DEFAULT_RESULTS_COLLAPSE))
        column_mode = display_cols[0].selectbox(
            "浏览方式",
            options=list(_COLUMN_MODE_OPTIONS),
            index=list(_COLUMN_MODE_OPTIONS).index(current_column_mode),
            format_func=_column_mode_label,
            key=_view_control_key(st, state_key=column_mode_key, value=current_column_mode),
            on_change=_callback_view_control,
            kwargs={"st": st, "state_key": column_mode_key, "parameter": "column_mode"},
        )
        page_size_options = sorted({* _PAGE_SIZE_OPTIONS, current_page_size})
        page_size = int(
            display_cols[1].selectbox(
                "显示数量",
                options=page_size_options,
                index=page_size_options.index(current_page_size),
                format_func=lambda value: f"{int(value)} 条",
                key=_view_control_key(st, state_key=page_size_key, value=current_page_size),
                on_change=_callback_view_control,
                kwargs={"st": st, "state_key": page_size_key, "parameter": "page_size"},
            )
        )
        results_collapse = st.radio(
            "结果折叠",
            options=list(_RESULTS_COLLAPSE_OPTIONS),
            index=list(_RESULTS_COLLAPSE_OPTIONS).index(current_results_collapse),
            horizontal=True,
            format_func=_results_collapse_label,
            key=_view_control_key(st, state_key=results_collapse_key, value=current_results_collapse),
            on_change=_callback_view_control,
            kwargs={"st": st, "state_key": results_collapse_key, "parameter": "results_collapse"},
        )
        st.session_state[column_mode_key] = column_mode
        st.session_state[page_size_key] = page_size
        st.session_state[results_collapse_key] = results_collapse

    item_payloads = list(
        _cached_items(
            current_profile,
            current_scope,
            current_project_path,
            current_include_global,
            current_kind,
            str(st.session_state["catalog_ui_query"] or ""),
            str(st.session_state["catalog_ui_field"] or "all"),
            _shell.freeze_filters(field_filters),
            current_db_path,
            current_source_mode,
        )
    )
    item_payloads = _sorted_items(item_payloads, sort_by=sort_by, sort_dir=sort_dir)
    visible_item_payloads = _visible_result_items(item_payloads, page_size=page_size)
    other_kind_hits = (
        _cached_other_kind_hits(
            query=str(st.session_state["catalog_ui_query"] or ""),
            profile=current_profile,
            scope=current_scope,
            project_path=current_project_path or None,
            include_global=current_include_global,
            field=str(st.session_state["catalog_ui_field"] or "all"),
            current_kind=current_kind,
            db_path=current_db_path or None,
            source_mode=current_source_mode or None,
            filters_key=_shell.freeze_filters(field_filters),
        )
        if (not item_payloads and str(st.session_state["catalog_ui_query"] or "").strip() and current_kind != _KIND_ALL)
        else {}
    )

    selected_key = str(st.session_state.get("catalog_ui_selected", "") or "").strip()
    selected_entry = (
        _cached_selected(
            current_profile,
            current_scope,
            current_project_path,
            current_include_global,
            selected_key,
            current_db_path,
            current_source_mode,
        )
        if selected_key
        else None
    )
    selection = _selection_state(selected_key, visible_item_payloads, selected_exists=selected_entry is not None)
    if not selection["selected_key"] and visible_item_payloads and selected_key != _NO_SELECTION:
        selected_key = visible_item_payloads[0]["key"]
        selected_entry = _cached_selected(
            current_profile,
            current_scope,
            current_project_path,
            current_include_global,
            selected_key,
            current_db_path,
            current_source_mode,
        )
        selection = _selection_state(selected_key, visible_item_payloads, selected_exists=selected_entry is not None)

    if bool(st.session_state.get(_PENDING_LOCATE_KEY)):
        selected_in_items, selected_in_visible = _selection_presence(
            selected_key,
            items=item_payloads,
            visible_items=visible_item_payloads,
        )
        if not selected_key or selected_key == _NO_SELECTION or selected_entry is None:
            st.session_state[_PENDING_LOCATE_KEY] = False
        else:
            selected_kind = str((selected_entry or {}).get("kind", "") or "").strip().lower()
            if selected_kind and not _navigation.contains_kind(current_kind, selected_kind):
                st.session_state["catalog_ui_kind"] = selected_kind
                _write_locate_state_and_rerun(
                    st,
                    profile=current_profile,
                    scope=current_scope,
                    kind=selected_kind,
                    query=str(st.session_state.get("catalog_ui_query", "") or ""),
                    field=str(st.session_state.get("catalog_ui_field", "all") or "all"),
                    selected=selected_key,
                    project_path=current_project_path,
                    include_global=current_include_global,
                    db_path=current_db_path,
                    source_mode=current_source_mode,
                    sort_by=sort_by,
                    sort_dir=sort_dir,
                    detail_tab=_normalize_detail_tab(st.session_state.get(detail_tab_key, _shared.DEFAULT_DETAIL_TAB)),
                    open_relations=_shared.csv_param_value(st.session_state.get(open_relations_key, ())),
                    column_mode=column_mode,
                    page_size=page_size,
                    results_collapse="expanded",
                    field_filters=field_filters,
                )
            if not selected_in_items:
                next_query = str(st.session_state.get("catalog_ui_query", "") or "")
                next_filters: dict[str, object] = dict(field_filters)
                changed = False
                if next_query.strip():
                    st.session_state["catalog_ui_query"] = ""
                    next_query = ""
                    changed = True
                if _has_active_field_filters(field_filters):
                    _clear_scope_kind_filters(st, scope=current_scope, kind=current_kind)
                    next_filters = {}
                    changed = True
                if changed:
                    _write_locate_state_and_rerun(
                        st,
                        profile=current_profile,
                        scope=current_scope,
                        kind=current_kind,
                        query=next_query,
                        field=str(st.session_state.get("catalog_ui_field", "all") or "all"),
                        selected=selected_key,
                        project_path=current_project_path,
                        include_global=current_include_global,
                        db_path=current_db_path,
                        source_mode=current_source_mode,
                        sort_by=sort_by,
                        sort_dir=sort_dir,
                        detail_tab=_normalize_detail_tab(st.session_state.get(detail_tab_key, _shared.DEFAULT_DETAIL_TAB)),
                        open_relations=_shared.csv_param_value(st.session_state.get(open_relations_key, ())),
                        column_mode=column_mode,
                        page_size=page_size,
                        results_collapse="expanded",
                        field_filters=next_filters,
                    )
            if selected_in_items and not selected_in_visible:
                desired_page_size = max(_normalize_page_size(st.session_state.get(page_size_key, page_size)), len(item_payloads))
                if _normalize_page_size(st.session_state.get(page_size_key, page_size)) < desired_page_size:
                    st.session_state[page_size_key] = desired_page_size
                    _write_locate_state_and_rerun(
                        st,
                        profile=current_profile,
                        scope=current_scope,
                        kind=current_kind,
                        query=str(st.session_state.get("catalog_ui_query", "") or ""),
                        field=str(st.session_state.get("catalog_ui_field", "all") or "all"),
                        selected=selected_key,
                        project_path=current_project_path,
                        include_global=current_include_global,
                        db_path=current_db_path,
                        source_mode=current_source_mode,
                        sort_by=sort_by,
                        sort_dir=sort_dir,
                        detail_tab=_normalize_detail_tab(st.session_state.get(detail_tab_key, _shared.DEFAULT_DETAIL_TAB)),
                        open_relations=_shared.csv_param_value(st.session_state.get(open_relations_key, ())),
                        column_mode=column_mode,
                        page_size=desired_page_size,
                        results_collapse="expanded",
                        field_filters=field_filters,
                    )
            if selected_in_items:
                st.session_state[_PENDING_LOCATE_KEY] = False
                st.session_state[_PENDING_SCROLL_TARGET_KEY] = "catalog-results-anchor"

    workspace = st.container(key="catalog_workspace")
    left, right = workspace.columns((0.36, 1.0), gap="large")
    left = left.container(key="catalog_results")
    right = right.container(key="catalog_detail")
    with left:
        if selection.get("hidden", False):
            st.markdown(
                "<div class='catalog-warning'>筛选隐藏了当前组件；右侧仍保留它的用法。</div>",
                unsafe_allow_html=True,
            )
        st.markdown(
            f"<div id='{_page.RESULT_SECTION_ID}' class='catalog-list-heading'>"
            f"<strong>组件</strong><span>{len(visible_item_payloads)} / {len(item_payloads)}</span></div>",
            unsafe_allow_html=True,
        )
        st.markdown("<div id='catalog-results-anchor'></div>", unsafe_allow_html=True)
        results_label = f"组件列表 · {len(visible_item_payloads)} / {len(item_payloads)}"
        results_container = st.expander(results_label, expanded=False) if results_collapse == "collapsed" else st.container()
        with results_container:
            if other_kind_hits:
                st.info("当前分类没有命中，但其他分类里有结果。可以直接切换过去，或者切到“全部 All”看全局结果。")
                switch_cols = st.columns(min(4, len(other_kind_hits) + 1))
                switch_cols[0].button(
                    "切到全部 All",
                    key=f"catalog_ui::switch_all::{current_scope}::{current_kind}",
                    width="stretch",
                    on_click=_callback_switch_kind,
                    kwargs={"st": st, "target_kind": _KIND_ALL},
                )
                for index, other_kind in enumerate(tuple(other_kind_hits.keys())[:3], start=1):
                    hit_count = len(other_kind_hits.get(other_kind, ()))
                    label = f"{_kind_label(other_kind)} ({hit_count})"
                    switch_cols[index].button(
                        label,
                        key=f"catalog_ui::switch_kind::{current_scope}::{current_kind}::{other_kind}",
                        width="stretch",
                        on_click=_callback_switch_kind,
                        kwargs={"st": st, "target_kind": other_kind},
                    )
            selected_key = _render_results_table(
                st,
                items=visible_item_payloads,
                scope=current_scope,
                kind=current_kind,
                column_mode=column_mode,
            )
            if len(item_payloads) > len(visible_item_payloads):
                st.button("显示更多组件", width="stretch", on_click=_callback_show_more,
                          kwargs={"st": st, "page_size_key": page_size_key, "total": len(item_payloads)})
        _render_selection_float(
            st,
            selection=selection,
            selected_entry=selected_entry,
            visible_items=visible_item_payloads,
            scope=current_scope,
            kind=current_kind,
        )
        pending_scroll_target = str(st.session_state.get(_PENDING_SCROLL_TARGET_KEY, "") or "").strip()
        if pending_scroll_target:
            _scroll_to_anchor(st, anchor_id=pending_scroll_target)
            st.session_state[_PENDING_SCROLL_TARGET_KEY] = ""

    st.session_state["catalog_ui_selected"] = selected_key if selected_key else (_NO_SELECTION if selected_key == _NO_SELECTION else "")
    if selected_key and selected_key != _NO_SELECTION:
        if selected_entry is None or str(selected_entry.get("key", "") or "") != selected_key:
            selected_entry = _cached_selected(
                current_profile,
                current_scope,
                current_project_path,
                current_include_global,
                selected_key,
                current_db_path,
                current_source_mode,
            )
    else:
        selected_entry = None

    with right:
        _render_detail_header(st, selected_entry)
        current_detail_tab = _normalize_detail_tab(st.session_state.get(detail_tab_key, _shared.DEFAULT_DETAIL_TAB))
        neighbors = (
            _cached_neighbors(
                current_profile,
                current_scope,
                current_project_path,
                current_include_global,
                selected_key,
                current_db_path,
                current_source_mode,
            )
            if selected_key
            else None
        )
        relation_labels = dict((neighbors or {}).get("relation_labels", {}) or {})
        relation_options = tuple(_relation_neighbor_groups(entry=selected_entry, neighbors=neighbors).keys())
        detail_cols = st.columns((1.0,))
        detail_tab = detail_cols[0].radio(
            "详情 Tab",
            options=list(_DETAIL_TABS),
            index=list(_DETAIL_TABS).index(current_detail_tab),
            horizontal=True,
            format_func=_detail_tab_label,
            label_visibility="collapsed",
            key=_view_control_key(st, state_key=detail_tab_key, value=current_detail_tab),
            on_change=_callback_view_control,
            kwargs={"st": st, "state_key": detail_tab_key, "parameter": "detail_tab"},
        )
        st.session_state[detail_tab_key] = detail_tab
        expanded_relation_groups = tuple(
            value
            for value in _shared.normalize_csv_values(st.session_state.get(open_relations_key, ()))
            if value in relation_options
        )
        if detail_tab == "relations" and relation_options:
            chosen_groups = st.multiselect(
                "展开关系组",
                options=list(relation_options),
                default=list(expanded_relation_groups),
                format_func=lambda value: _relation_group_label(str(value), relation_labels),
            )
            expanded_relation_groups = tuple(str(value).strip() for value in chosen_groups if str(value).strip())
        elif detail_tab == "relations":
            st.caption("当前条目没有可展开的关系分组。")
            expanded_relation_groups = ()
        st.session_state[open_relations_key] = expanded_relation_groups
        deep_link_query = _build_deep_link_query(
            profile=current_profile,
            scope=current_scope,
            kind=current_kind,
            query=str(st.session_state["catalog_ui_query"] or ""),
            field=str(st.session_state["catalog_ui_field"] or "all"),
            selected="" if selected_key == _NO_SELECTION else selected_key,
            project_path=current_project_path,
            include_global=current_include_global,
            db_path=current_db_path,
            source_mode=current_source_mode,
            sort_by=sort_by,
            sort_dir=sort_dir,
            detail_tab=detail_tab,
            open_relations=_shared.csv_param_value(expanded_relation_groups),
            column_mode=column_mode,
            page_size=page_size,
            results_collapse=results_collapse,
            field_filters=field_filters,
        )
        _write_query_params(
            st,
            profile=current_profile,
            scope=current_scope,
            kind=current_kind,
            query=str(st.session_state["catalog_ui_query"] or ""),
            field=str(st.session_state["catalog_ui_field"] or "all"),
            selected="" if selected_key == _NO_SELECTION else selected_key,
            project_path=current_project_path,
            include_global=current_include_global,
            db_path=current_db_path,
            source_mode=current_source_mode,
            sort_by=sort_by,
            sort_dir=sort_dir,
            detail_tab=detail_tab,
            open_relations=_shared.csv_param_value(expanded_relation_groups),
            column_mode=column_mode,
            page_size=page_size,
            results_collapse=results_collapse,
            field_filters=field_filters,
        )
        _render_detail(
            st,
            entry=selected_entry,
            neighbors=neighbors,
            source_info=source_info,
            deep_link_query=deep_link_query,
            scope=current_scope,
            kind=current_kind,
            detail_tab=detail_tab,
            expanded_relation_groups=expanded_relation_groups,
        )


def main(argv: Sequence[str] | None = None) -> None:
    run_dashboard(argv)


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv[1:])




