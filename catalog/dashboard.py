from __future__ import annotations

import argparse
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
    from nsgablack.catalog.facade import (
        catalog_facets,
        catalog_neighbors,
        catalog_schema,
        catalog_source_info,
        catalog_summary,
        list_entries,
        search_entries,
        show_entry,
    )
else:
    from . import dashboard_page as _page
    from . import dashboard_shell as _shell
    from . import dashboard_shared as _shared
    from .facade import (
        catalog_facets,
        catalog_neighbors,
        catalog_schema,
        catalog_source_info,
        catalog_summary,
        list_entries,
        search_entries,
        show_entry,
    )

_KIND_ALL = "all"
_NAV_ACTION_LOCATE_SELECTED = "locate_selected"
_PENDING_LOCATE_KEY = "catalog_ui_pending_locate_selected"
_PENDING_SCROLL_TARGET_KEY = "catalog_ui_pending_scroll_target"

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
    _KIND_ALL: "全部 All",
    "adapter": "Adapter 策略",
    "plugin": "Plugin 能力",
    "bias": "Bias 偏置",
    "representation": "Representation 表示",
    "suite": "Suite 套件",
    "tool": "Tool 工具",
    "doc": "Doc 文档",
    "example": "Example 示例",
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
    "tags": "标签",
    "companions": "关联条目",
    "required_companions": "必备搭档",
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
    "config_keys": "关键配置",
    "example_entry": "示例入口",
    "import_path": "导入路径",
    "summary": "摘要",
}

_PRIMARY_FILTER_FIELDS: tuple[str, ...] = (
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
_DETAIL_TABS: tuple[str, ...] = ("overview", "relations", "source")
_DETAIL_TAB_LABELS: dict[str, str] = {
    "overview": "概览",
    "relations": "关系",
    "source": "来源",
}
_COLUMN_MODE_OPTIONS: tuple[str, ...] = ("compact", "standard", "full")
_COLUMN_MODE_LABELS: dict[str, str] = {
    "compact": "紧凑列",
    "standard": "标准列",
    "full": "完整列",
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
            initial_sidebar_state="collapsed",
        )
    except Exception:
        pass


def _inject_style(st: Any) -> None:
    st.markdown(
        (
            """
        <style>
        .block-container {padding-top: 1.02rem; padding-bottom: 1.28rem; max-width: 1560px;}
        [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {display: none !important;}
        .catalog-hero {
            background: linear-gradient(135deg, #efe7db 0%, #dfcdb0 45%, #bf9f74 100%);
            border: 1px solid rgba(92, 63, 28, 0.14);
            border-radius: 24px;
            padding: 1.15rem 1.3rem;
            margin-bottom: 1rem;
            box-shadow: 0 18px 40px rgba(79, 55, 27, 0.08);
        }
        .catalog-hero-head {
            display: flex;
            align-items: center;
            gap: 0.88rem;
            margin-bottom: 0.38rem;
        }
        .catalog-brand {display: flex; align-items: center; gap: 0.88rem;}
        .catalog-icon {
            width: 48px;
            height: 48px;
            border-radius: 14px;
            background: linear-gradient(180deg, rgba(58, 38, 20, 0.96), rgba(96, 68, 36, 0.96));
            color: #f6ede2;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.05rem;
            font-weight: 900;
            letter-spacing: 0.06em;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.08), 0 12px 24px rgba(63, 41, 20, 0.14);
        }
        .catalog-kicker {font-size: 0.78rem; letter-spacing: 0.08em; text-transform: uppercase; color: #6e4a21; font-weight: 800;}
        .catalog-title {font-size: 2.0rem; line-height: 1.05; color: #2d1e12; font-weight: 800; margin: 0.18rem 0 0.34rem 0;}
        .catalog-sub {font-size: 0.96rem; color: #59442d; max-width: 82ch;}
        .catalog-inline-filters {
            border: 1px solid rgba(90, 62, 28, 0.12);
            border-radius: 18px;
            padding: 0.2rem 0.32rem 0.32rem 0.32rem;
            background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(249,245,239,0.96));
            margin-bottom: 0.9rem;
        }
        .catalog-stat {
            background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(248,244,238,0.96));
            border: 1px solid rgba(90, 62, 28, 0.12);
            border-radius: 18px;
            padding: 0.9rem 1rem;
            min-height: 110px;
        }
        .catalog-stat-label {font-size: 0.76rem; text-transform: uppercase; letter-spacing: 0.06em; color: #7b5b38; font-weight: 700;}
        .catalog-stat-value {font-size: 1.45rem; font-weight: 800; color: #2f2115; margin-top: 0.14rem;}
        .catalog-stat-note {font-size: 0.87rem; color: #65513a; margin-top: 0.16rem;}
        .catalog-chip {
            display: inline-block;
            margin: 0.12rem 0.32rem 0.12rem 0;
            padding: 0.18rem 0.48rem;
            border-radius: 999px;
            background: rgba(68, 47, 23, 0.08);
            color: #4e3419;
            font-size: 0.8rem;
            font-weight: 600;
        }
        .catalog-detail {
            background: white;
            border: 1px solid rgba(90, 62, 28, 0.12);
            border-radius: 20px;
            padding: 1rem 1.05rem;
        }
        .catalog-section-title {font-size: 0.92rem; color: #72502d; font-weight: 780; margin-top: 0.88rem; margin-bottom: 0.32rem;}
        .catalog-empty {
            border: 1px dashed rgba(101, 73, 41, 0.26);
            border-radius: 18px;
            padding: 1rem;
            background: rgba(255, 251, 246, 0.9);
            color: #5d4831;
        }
        .catalog-floating {
            position: sticky;
            top: 0.6rem;
            z-index: 30;
            background: linear-gradient(180deg, rgba(255,250,243,0.98), rgba(250,242,230,0.98));
            border: 1px solid rgba(101, 70, 35, 0.18);
            border-radius: 18px;
            padding: 0.82rem 0.9rem;
            margin-bottom: 0.9rem;
            box-shadow: 0 10px 24px rgba(77, 54, 29, 0.08);
        }
        .catalog-floating-label {font-size: 0.76rem; text-transform: uppercase; letter-spacing: 0.06em; color: #8a6439; font-weight: 700;}
        .catalog-floating-title {font-size: 1.02rem; color: #2f2115; font-weight: 800; margin-top: 0.18rem;}
        .catalog-floating-meta {font-size: 0.86rem; color: #6a543c; margin-top: 0.18rem;}
        .catalog-warning {
            border: 1px solid rgba(170, 118, 34, 0.25);
            border-radius: 16px;
            padding: 0.78rem 0.86rem;
            background: rgba(255, 248, 235, 0.96);
            color: #674c22;
            margin-bottom: 0.85rem;
        }
        .catalog-relation-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 0.72rem;
            margin: 0.38rem 0 0.92rem 0;
        }
        .catalog-relation-card {
            border: 1px solid rgba(101, 70, 35, 0.14);
            border-radius: 18px;
            padding: 0.82rem 0.9rem;
            background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(249,244,237,0.98));
            box-shadow: 0 10px 22px rgba(77, 54, 29, 0.06);
        }
        .catalog-relation-chain-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 0.78rem;
            margin: 0.38rem 0 1rem 0;
        }
        .catalog-relation-chain-card {
            border: 1px solid rgba(101, 70, 35, 0.16);
            border-radius: 20px;
            padding: 0.9rem 0.96rem;
            background: linear-gradient(180deg, rgba(255,250,244,0.99), rgba(245,238,229,0.99));
            box-shadow: 0 12px 24px rgba(77, 54, 29, 0.07);
        }
        .catalog-relation-chain-key {
            margin-top: 0.24rem;
            padding: 0.36rem 0.56rem;
            border-radius: 14px;
            background: rgba(90, 62, 28, 0.08);
            color: #2f2115;
            font-size: 0.96rem;
            font-weight: 800;
        }
        .catalog-relation-chain-meta {
            margin-top: 0.22rem;
            font-size: 0.82rem;
            color: #6a543c;
        }
        .catalog-relation-chain-lanes {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.62rem;
            margin-top: 0.7rem;
        }
        .catalog-relation-lane {
            border-radius: 14px;
            padding: 0.56rem 0.6rem;
            background: rgba(255,255,255,0.68);
            border: 1px solid rgba(101, 70, 35, 0.10);
        }
        .catalog-relation-lane-title {
            font-size: 0.76rem;
            color: #8b6640;
            font-weight: 780;
            margin-bottom: 0.34rem;
        }
        .catalog-relation-lane-empty {
            font-size: 0.78rem;
            color: #8c7b67;
        }
        .catalog-relation-lane-item {
            font-size: 0.82rem;
            color: #4c3822;
            padding: 0.22rem 0.34rem;
            border-radius: 10px;
            background: rgba(90, 62, 28, 0.05);
            margin-bottom: 0.26rem;
        }
        .catalog-relation-lane-item:last-child {
            margin-bottom: 0;
        }
        .catalog-relation-lane-key {
            display: block;
            font-size: 0.74rem;
            color: #7f6140;
        }
        .catalog-relation-family {
            font-size: 0.74rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #8b6640;
            font-weight: 800;
        }
        .catalog-relation-title {
            margin-top: 0.2rem;
            font-size: 0.98rem;
            line-height: 1.35;
            color: #2f2115;
            font-weight: 780;
        }
        .catalog-relation-meta {
            margin-top: 0.18rem;
            font-size: 0.83rem;
            color: #6a543c;
        }
        .catalog-relation-preview {
            margin-top: 0.55rem;
            display: flex;
            flex-direction: column;
            gap: 0.26rem;
        }
        .catalog-relation-preview-item {
            font-size: 0.83rem;
            color: #4c3822;
            padding: 0.28rem 0.44rem;
            border-radius: 12px;
            background: rgba(90, 62, 28, 0.06);
        }
        .catalog-relation-preview-key {
            color: #7f6140;
            font-size: 0.76rem;
            margin-left: 0.26rem;
        }
        .catalog-fab-stack {
            position: fixed;
            right: 1.15rem;
            bottom: 1.15rem;
            display: flex;
            flex-direction: column;
            gap: 0.62rem;
            z-index: 9998;
        }
        .catalog-fab {
            width: 48px;
            height: 48px;
            border-radius: 15px;
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
            text-decoration: none !important;
            background: linear-gradient(180deg, rgba(60, 39, 18, 0.96), rgba(103, 72, 37, 0.96));
            color: #f8efe5 !important;
            box-shadow: 0 14px 30px rgba(57, 38, 20, 0.2);
            border: 1px solid rgba(255,255,255,0.08);
            font-size: 1.22rem;
            font-weight: 800;
            transition: transform 120ms ease, box-shadow 120ms ease, opacity 120ms ease;
        }
        .catalog-fab:hover {
            transform: translateY(-2px);
            box-shadow: 0 18px 32px rgba(57, 38, 20, 0.24);
        }
        .catalog-fab-disabled {
            opacity: 0.42;
            pointer-events: none;
        }
        .catalog-fab[data-tooltip]::before,
        .catalog-fab[data-tooltip]::after {
            position: absolute;
            opacity: 0;
            pointer-events: none;
            transition: opacity 120ms ease, transform 120ms ease;
        }
        .catalog-fab[data-tooltip]::before {
            content: "";
            right: calc(100% + 6px);
            top: 50%;
            transform: translateY(-50%) translateX(6px);
            border-width: 6px 0 6px 7px;
            border-style: solid;
            border-color: transparent transparent transparent rgba(45, 31, 18, 0.96);
        }
        .catalog-fab[data-tooltip]::after {
            content: attr(data-tooltip);
            right: calc(100% + 14px);
            top: 50%;
            transform: translateY(-50%) translateX(6px);
            white-space: nowrap;
            padding: 0.42rem 0.58rem;
            border-radius: 10px;
            background: rgba(45, 31, 18, 0.96);
            color: #fff6ea;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.01em;
            box-shadow: 0 12px 24px rgba(31, 20, 10, 0.22);
        }
        .catalog-fab[data-tooltip]:hover::before,
        .catalog-fab[data-tooltip]:hover::after,
        .catalog-fab[data-tooltip]:focus-visible::before,
        .catalog-fab[data-tooltip]:focus-visible::after {
            opacity: 1;
            transform: translateY(-50%) translateX(0);
        }
        """
            + _page.PAGE_PROTOCOL_STYLE
            + """
        </style>
        """
        ),
        unsafe_allow_html=True,
    )


def _scope_label(scope: str) -> str:
    return _SCOPE_LABELS.get(str(scope or "").strip().lower(), str(scope or ""))


def _kind_label(kind: str) -> str:
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
    except Exception:
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
    return "".join(f"<span class='catalog-chip'>{str(value)}</span>" for value in values if str(value).strip())


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
    return _shared.read_query_params(
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
        base_params={
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
        },
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
        base_params={
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
        },
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
        base_params={
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
        },
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
    if raw == _KIND_ALL:
        return _KIND_ALL
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
) -> dict[str, list[Any]]:
    text = str(query or "").strip()
    if not text:
        return {}
    hits = search_entries(
        text,
        profile=profile,
        scope=scope,
        project_path=project_path,
        include_global=include_global,
        kind=None,
        field=field,
        limit=limit,
        db_path=db_path,
        source_mode=source_mode,
    )
    grouped: dict[str, list[Any]] = {}
    for entry in hits:
        entry_kind = str(getattr(entry, "kind", "") or "").strip().lower()
        if not entry_kind or entry_kind == current_kind:
            continue
        grouped.setdefault(entry_kind, []).append(entry)
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
            except Exception:
                pass

    if spec is None or not spec.origin:
        return None
    origin = str(spec.origin).strip()
    if not origin or origin in {"built-in", "frozen"}:
        return None
    path = Path(origin)
    return path.resolve() if path.exists() else None


def _reveal_source_file(path: Path) -> bool:
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
    except Exception:
        return False


def _open_source_file(path: Path) -> bool:
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
    except Exception:
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
    rows: list[dict[str, str]] = []
    normalized_mode = _normalize_column_mode(column_mode)
    for index, item in enumerate(items, start=1):
        row = {
            "序号": str(index),
            "标题": str(item.get("title", "") or item.get("key", "")),
            "Key": str(item.get("key", "")),
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
    except Exception:
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
        raw_kind = str(target_key).split(".", 1)[0].strip().lower()
    return raw_kind if raw_kind in _KIND_ORDER else ""


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
    _select_catalog_entry(st, target_key=target_key, target_kind=target_kind)


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
) -> None:
    _push_navigation_stack(st, current_entry=current_entry)
    _select_catalog_entry(st, target_key=target_key, target_kind=target_kind)
    st.session_state[_PENDING_SCROLL_TARGET_KEY] = "catalog-detail-anchor"


def _callback_switch_kind(st: Any, *, target_kind: str) -> None:
    st.session_state["catalog_ui_kind"] = str(target_kind or "")


def _callback_clear_filters(st: Any, *, scope: str, kind: str) -> None:
    _clear_scope_kind_filters(st, scope=scope, kind=kind)


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
    }


def _entry_detail_payload(entry: Any) -> dict[str, Any]:
    return {
        "key": str(getattr(entry, "key", "") or ""),
        "title": str(getattr(entry, "title", "") or ""),
        "kind": str(getattr(entry, "kind", "") or ""),
        "import_path": str(getattr(entry, "import_path", "") or ""),
        "tags": tuple(getattr(entry, "tags", ()) or ()),
        "summary": str(getattr(entry, "summary", "") or ""),
        "companions": tuple(getattr(entry, "companions", ()) or ()),
        "context_requires": tuple(getattr(entry, "context_requires", ()) or ()),
        "context_provides": tuple(getattr(entry, "context_provides", ()) or ()),
        "context_mutates": tuple(getattr(entry, "context_mutates", ()) or ()),
        "context_cache": tuple(getattr(entry, "context_cache", ()) or ()),
        "context_notes": tuple(getattr(entry, "context_notes", ()) or ()),
        "artifact_requires": tuple(getattr(entry, "artifact_requires", ()) or ()),
        "artifact_provides": tuple(getattr(entry, "artifact_provides", ()) or ()),
        "phase_in": tuple(getattr(entry, "phase_in", ()) or ()),
        "phase_out": tuple(getattr(entry, "phase_out", ()) or ()),
        "use_when": tuple(getattr(entry, "use_when", ()) or ()),
        "minimal_wiring": tuple(getattr(entry, "minimal_wiring", ()) or ()),
        "required_companions": tuple(getattr(entry, "required_companions", ()) or ()),
        "config_keys": tuple(getattr(entry, "config_keys", ()) or ()),
        "example_entry": str(getattr(entry, "example_entry", "") or ""),
    }


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
        scope=scope,
        project_path=project_path or None,
        include_global=include_global,
        db_path=db_path or None,
        source_mode=source_mode or None,
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
        scope=scope,
        project_path=project_path or None,
        include_global=include_global,
        db_path=db_path or None,
        source_mode=source_mode or None,
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
        scope=scope,
        project_path=project_path or None,
        include_global=include_global,
        db_path=db_path or None,
        source_mode=source_mode or None,
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
    return catalog_facets(
        profile=profile,
        scope=scope,
        project_path=project_path or None,
        include_global=include_global,
        kind=_catalog_kind_arg(kind),
        query=query,
        search_field=search_field,
        limit_per_field=24,
        db_path=db_path or None,
        source_mode=source_mode or None,
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
    filters = _shell.thaw_filters(filters_key)
    entries = (
        search_entries(
            query,
            profile=profile,
            scope=scope,
            project_path=project_path or None,
            include_global=include_global,
            kind=_catalog_kind_arg(kind),
            field=search_field,
            limit=250,
            field_filters=filters,
            db_path=db_path or None,
            source_mode=source_mode or None,
        )
        if str(query).strip()
        else list_entries(
            profile=profile,
            scope=scope,
            project_path=project_path or None,
            include_global=include_global,
            kind=_catalog_kind_arg(kind),
            limit=250,
            field_filters=filters,
            db_path=db_path or None,
            source_mode=source_mode or None,
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
        scope=scope,
        project_path=project_path or None,
        include_global=include_global,
        db_path=db_path or None,
        source_mode=source_mode or None,
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
        scope=scope,
        project_path=project_path or None,
        include_global=include_global,
        db_path=db_path or None,
        source_mode=source_mode or None,
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
    safe_title = escape(title)
    safe_key = escape(selected_key)
    row_index = selection.get("row_index")
    if selection.get("visible", False) and isinstance(row_index, int):
        meta = f"当前选中项位于结果表格第 {int(row_index) + 1} 行。"
    elif selection.get("hidden", False):
        meta = "当前选中项被筛选条件暂时隐藏。"
    else:
        meta = "当前选中项不在结果表格里。"

    st.markdown(
        (
            "<div class='catalog-floating'>"
            "<div class='catalog-floating-label'>Current Selection</div>"
            f"<div class='catalog-floating-title'>{safe_title}</div>"
            f"<div class='catalog-floating-meta'><code>{safe_key}</code><br/>{escape(meta)}</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )

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
    if not items:
        st.markdown("<div class='catalog-empty'>当前筛选条件下没有结果。可以清空筛选、切换分类，或直接使用“全部 All”全局搜索。</div>", unsafe_allow_html=True)
        return ""

    try:
        import pandas as pd

        table_event = st.dataframe(
            pd.DataFrame(_result_rows(items, column_mode=column_mode)),
            width="stretch",
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key=f"catalog_ui::results::{scope}::{kind}",
        )
        selected_rows = _selected_table_row_indices(table_event)
        if selected_rows:
            index = int(selected_rows[0])
            if 0 <= index < len(items):
                selected_key = str(items[index].get("key", ""))
    except Exception:
        st.table(_result_rows(items, column_mode=column_mode))

    if not selected_key and not cleared_selection:
        selected_key = str(items[0].get("key", ""))
    return selected_key or (_NO_SELECTION if cleared_selection else "")


def _render_sequence(st: Any, *, title: str, values: Sequence[str]) -> None:
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    st.markdown(f"<div class='catalog-section-title'>{title}</div>", unsafe_allow_html=True)
    if not cleaned:
        st.caption("无")
        return
    for value in cleaned:
        st.markdown(f"- {value}")


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
    entry_kind = str(entry.get("kind", "") or "")
    entry_title = str(entry.get("title", "") or entry_key)
    import_path = str(entry.get("import_path", "") or "")
    source_path = _resolve_source_file(import_path, project_root=str(source_info.get("project_root", "") or "") or None)
    badges = _source_badges(entry, source_info)

    st.markdown("<div id='catalog-detail-anchor'></div>", unsafe_allow_html=True)
    st.markdown("<div class='catalog-detail'>", unsafe_allow_html=True)
    st.markdown(f"## {entry_title}")
    st.code(entry_key, language=None)
    badge_values = tuple(badges) + tuple(str(value) for value in entry.get("tags", ()) if str(value).strip())
    if badge_values:
        st.markdown(_chips(badge_values), unsafe_allow_html=True)

    summary = str(entry.get("summary", "") or "").strip()
    if summary:
        st.markdown(summary)

    _render_navigation_stack(st, current_key=entry_key)

    current_tab = _normalize_detail_tab(detail_tab)
    expanded_groups = {
        str(value).strip()
        for value in expanded_relation_groups
        if str(value).strip()
    }

    if current_tab == "overview":
        _render_sequence(st, title=_field_label("use_when"), values=tuple(entry.get("use_when", ()) or ()))
        _render_sequence(st, title=_field_label("minimal_wiring"), values=tuple(entry.get("minimal_wiring", ()) or ()))
        _render_sequence(st, title=_field_label("config_keys"), values=tuple(entry.get("config_keys", ()) or ()))
        _render_sequence(st, title=_field_label("context_requires"), values=tuple(entry.get("context_requires", ()) or ()))
        _render_sequence(st, title=_field_label("context_provides"), values=tuple(entry.get("context_provides", ()) or ()))
        _render_sequence(st, title=_field_label("context_mutates"), values=tuple(entry.get("context_mutates", ()) or ()))
        _render_sequence(st, title=_field_label("context_cache"), values=tuple(entry.get("context_cache", ()) or ()))
        _render_sequence(st, title=_field_label("context_notes"), values=tuple(entry.get("context_notes", ()) or ()))
        _render_sequence(st, title=_field_label("artifact_requires"), values=tuple(entry.get("artifact_requires", ()) or ()))
        _render_sequence(st, title=_field_label("artifact_provides"), values=tuple(entry.get("artifact_provides", ()) or ()))
        _render_sequence(st, title=_field_label("phase_in"), values=tuple(entry.get("phase_in", ()) or ()))
        _render_sequence(st, title=_field_label("phase_out"), values=tuple(entry.get("phase_out", ()) or ()))

        example_entry = str(entry.get("example_entry", "") or "").strip()
        st.markdown(f"<div class='catalog-section-title'>{_field_label('example_entry')}</div>", unsafe_allow_html=True)
        if example_entry:
            st.code(example_entry, language=None)
        else:
            st.caption("无")

    elif current_tab == "relations":
        neighbor_groups = _relation_neighbor_groups(entry=entry, neighbors=neighbors)
        relation_labels = dict((neighbors or {}).get("relation_labels", {}) or {})
        relation_cards = tuple((neighbors or {}).get("relation_cards", ()) or ())
        relation_chain_cards = tuple((neighbors or {}).get("relation_chain_cards", ()) or ())
        if not neighbor_groups:
            st.info("当前条目还没有可跳转的关系。")
        _render_relation_chain_cards(
            st,
            relation_chain_cards,
            current_entry=entry,
            scope=scope,
            kind=kind,
            expanded_relation_groups=tuple(expanded_groups),
        )
        _render_relation_cards(st, relation_cards)
        for relation_name, rows in neighbor_groups.items():
            if not rows:
                continue
            with st.expander(f"{_relation_group_label(relation_name, relation_labels)} ({len(rows)})", expanded=relation_name in expanded_groups):
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
                            st.caption(relation_note)
                        if summary:
                            st.caption(summary)
                    with cols[1]:
                        st.button(
                            "跳转",
                            key=f"catalog_ui::jump::{entry_key}::{relation_name}::{index}::{key}",
                            width="stretch",
                            on_click=_callback_jump_relation,
                            kwargs={
                                "st": st,
                                "current_entry": entry,
                                "target_key": key,
                                "target_kind": str(item.get("kind", "") or ""),
                            },
                        )

    else:
        st.markdown("<div class='catalog-section-title'>来源与链接</div>", unsafe_allow_html=True)
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
        st.markdown("<div class='catalog-section-title'>Source File</div>", unsafe_allow_html=True)
        if source_path is not None:
            st.code(str(source_path), language=None)
        else:
            st.caption("当前条目暂时无法解析到本地 source file。")

    st.caption(f"kind={entry_kind or 'unknown'} | scope={scope} | active-view={kind}")
    st.markdown("</div>", unsafe_allow_html=True)


def run_dashboard(argv: Sequence[str] | None = None) -> None:
    args = _parse_args(argv)
    st = _require_streamlit()
    _set_page_config(st)
    _inject_style(st)

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
        query_filters=query_filters,
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

    _page.render_top_anchor(st)
    _page.render_hero(
        st,
        _page.HeroSpec(
            icon_text="NC",
            kicker="nsgablack catalog",
            title="框架 / 项目双视图查询页",
            subtitle=(
                "顶部集中控制查询与字段筛选，中间是可点击选中的结果表格，右侧展示详情、来源、跳转栈与 source file 动作。"
                "同一套页面既能看 framework-core，也能切到项目本地 catalog。"
            ),
        ),
    )
    root_note = str(source_info.get("project_root", "") or "")
    _page.render_stat_cards(
        st,
        (
            _page.StatCardSpec(
                label="Scope",
                value=_scope_label(current_scope),
                note=f"effective={str(source_info.get('effective_source', 'framework'))}",
            ),
            _page.StatCardSpec(
                label="Entries",
                value=str(int(summary.get("total", 0))),
                note="当前视图下的条目总数",
            ),
            _page.StatCardSpec(
                label="Kinds",
                value=str(len(summary.get("by_kind", {}))),
                note=" / ".join(sorted(summary.get("by_kind", {}).keys())[:5]),
            ),
            _page.StatCardSpec(
                label="Project Root",
                value="已连接" if bool(root_note) else "未连接",
                note=root_note or "当前不是 project scaffold 目录",
            ),
        ),
    )

    _page.render_section_header(
        st,
        _page.SectionHeaderSpec(
            section_id=_page.FILTER_SECTION_ID,
            label="Filter",
            title="查询与筛选",
            subtitle="先确定视图、profile、分类与数据源，再用字段筛选把结果收窄到可点选范围。",
        ),
    )

    primary_controls = _page.render_control_row(st, _primary_controls_spec())
    scope = primary_controls["scope"].column.radio(
        primary_controls["scope"].label,
        options=("framework", "project"),
        index=0 if current_scope == "framework" else 1,
        horizontal=True,
        format_func=_scope_label,
    )
    profile = primary_controls["profile"].column.selectbox(
        primary_controls["profile"].label,
        options=("framework-core", "default"),
        index=0 if current_profile == "framework-core" else 1,
    )
    kind = primary_controls["kind"].column.selectbox(
        primary_controls["kind"].label,
        options=list(kinds),
        index=max(0, list(kinds).index(current_kind)) if current_kind in kinds else 0,
        format_func=_kind_label,
    )
    query = primary_controls["query"].column.text_input(
        primary_controls["query"].label,
        value=str(st.session_state["catalog_ui_query"] or ""),
        placeholder=primary_controls["query"].placeholder,
    )

    secondary_controls = _page.render_control_row(st, _secondary_controls_spec())
    field = secondary_controls["field"].column.selectbox(
        secondary_controls["field"].label,
        options=list(_SEARCH_FIELD_LABELS.keys()),
        index=list(_SEARCH_FIELD_LABELS.keys()).index(str(st.session_state["catalog_ui_field"] or "all"))
        if str(st.session_state["catalog_ui_field"] or "all") in _SEARCH_FIELD_LABELS
        else 0,
        format_func=_search_field_label,
    )
    project_path = secondary_controls["project_path"].column.text_input(
        secondary_controls["project_path"].label,
        value=str(st.session_state["catalog_ui_project_path"] or ""),
        disabled=scope != "project",
        help=secondary_controls["project_path"].help,
    )
    include_global = secondary_controls["include_global"].column.checkbox(
        secondary_controls["include_global"].label,
        value=bool(st.session_state["catalog_ui_include_global"]),
        disabled=scope != "project",
    )
    db_controls_disabled = scope == "project" and not include_global
    db_path = secondary_controls["db_path"].column.text_input(
        secondary_controls["db_path"].label,
        value=str(st.session_state["catalog_ui_db_path"] or ""),
        disabled=db_controls_disabled,
        placeholder=secondary_controls["db_path"].placeholder,
        help=secondary_controls["db_path"].help,
    )
    source_mode = secondary_controls["source_mode"].column.selectbox(
        secondary_controls["source_mode"].label,
        options=list(_SOURCE_MODE_OPTIONS),
        index=list(_SOURCE_MODE_OPTIONS).index(current_source_mode) if current_source_mode in _SOURCE_MODE_OPTIONS else 0,
        format_func=_source_mode_label,
        disabled=db_controls_disabled,
        help=secondary_controls["source_mode"].help,
    )
    if kind == _KIND_ALL:
        secondary_controls["field"].caption("当前是全局搜索：会跨 Adapter / Bias / Plugin / Representation 等分类一起查。")
    else:
        secondary_controls["field"].caption(f"当前关键词只在“{_kind_label(kind)}”内搜索。找不到时可切到“全部 All”。")
    if db_controls_disabled:
        secondary_controls["db_path"].caption("当前项目视图只看本地 catalog，未并入框架条目时不读取数据库。")
    else:
        configured_backend = str(source_info.get("db_backend", "") or "").strip()
        if not db_path and configured_backend:
            secondary_controls["db_path"].caption(f"未填写 DB URL 时，会默认使用本地已配置的 {configured_backend} catalog。")
        else:
            secondary_controls["db_path"].caption("框架视图可直接切到 DB-backed catalog；项目视图仅在并入框架条目时读取 DB。")

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
    else:
        active_backend = str(source_info.get("effective_source", "registry") or "registry")
        active_mode = _source_mode_label(str(source_info.get("source_mode", "") or ""))
        db_target = "显式 DB URL" if bool(source_info.get("explicit_db_path", False)) else "catalog DB 配置"
        st.caption(f"当前读取后端：`{active_backend}` · Source Mode：`{active_mode}` · DB 来源：{db_target} · 不带 --db-path 时也会优先吃本地 catalog DB 配置。")

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
    with st.container():
        st.markdown("<div class='catalog-inline-filters'>", unsafe_allow_html=True)
        expander_title = "字段筛选"
        if current_kind != _KIND_ALL:
            expander_title += f" · {_kind_label(current_kind)}"
        with st.expander(expander_title, expanded=False):
            if not filter_fields_with_options:
                st.caption("当前分类下没有可用的字段筛选项。")
            else:
                filter_cols = st.columns(min(3, len(filter_fields_with_options)))
                for index, (field_name, options) in enumerate(filter_fields_with_options):
                    state_key = f"catalog_ui::facet::{current_scope}::{current_kind}::{field_name}"
                    existing = tuple(value for value in st.session_state.get(state_key, ()) if value in options)
                    if state_key not in st.session_state:
                        st.session_state[state_key] = list(existing)
                    with filter_cols[index % len(filter_cols)]:
                        st.multiselect(_field_label(field_name), options=options, key=state_key)
                st.button(
                    "清空字段筛选",
                    width="content",
                    on_click=_callback_clear_filters,
                    kwargs={"st": st, "scope": current_scope, "kind": current_kind},
                )
        st.markdown("</div>", unsafe_allow_html=True)
    field_filters = _shared.collect_session_filters(
        st,
        scope=current_scope,
        kind=current_kind,
        facet_fields=_PRIMARY_FILTER_FIELDS,
        multi_value=True,
    )

    sort_cols = st.columns((0.9, 0.78, 1.52))
    current_sort_by = _normalize_sort_by(st.session_state.get(sort_by_key, _shared.DEFAULT_SORT_BY))
    current_sort_dir = _normalize_sort_dir(st.session_state.get(sort_dir_key, _shared.DEFAULT_SORT_DIR))
    sort_by = sort_cols[0].selectbox(
        "结果排序",
        options=list(_SORT_OPTIONS),
        index=list(_SORT_OPTIONS).index(current_sort_by),
        format_func=_sort_label,
    )
    sort_dir = sort_cols[1].radio(
        "方向",
        options=("asc", "desc"),
        index=0 if current_sort_dir == "asc" else 1,
        horizontal=True,
        format_func=lambda value: "升序" if value == "asc" else "降序",
    )
    sort_cols[2].caption("Deep-link 会记住当前排序方式。")
    st.session_state[sort_by_key] = sort_by
    st.session_state[sort_dir_key] = sort_dir

    display_cols = st.columns((0.9, 0.8, 0.95, 1.45))
    current_column_mode = _normalize_column_mode(st.session_state.get(column_mode_key, _shared.DEFAULT_COLUMN_MODE))
    current_page_size = _normalize_page_size(st.session_state.get(page_size_key, _shared.DEFAULT_PAGE_SIZE))
    current_results_collapse = _normalize_results_collapse(st.session_state.get(results_collapse_key, _shared.DEFAULT_RESULTS_COLLAPSE))
    column_mode = display_cols[0].selectbox(
        "列显示方案",
        options=list(_COLUMN_MODE_OPTIONS),
        index=list(_COLUMN_MODE_OPTIONS).index(current_column_mode),
        format_func=_column_mode_label,
    )
    page_size_options = sorted({* _PAGE_SIZE_OPTIONS, current_page_size})
    page_size = int(
        display_cols[1].selectbox(
            "Page Size",
            options=page_size_options,
            index=page_size_options.index(current_page_size),
            format_func=lambda value: f"{int(value)} 条",
        )
    )
    results_collapse = display_cols[2].radio(
        "结果折叠",
        options=list(_RESULTS_COLLAPSE_OPTIONS),
        index=list(_RESULTS_COLLAPSE_OPTIONS).index(current_results_collapse),
        horizontal=True,
        format_func=_results_collapse_label,
    )
    display_cols[3].caption("Deep-link 会记住当前列方案、结果分页窗口和折叠状态。")
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
            if current_kind not in {_KIND_ALL, selected_kind} and selected_kind:
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

    left, right = st.columns((1.28, 0.92), gap="large")
    with left:
        _render_selection_float(
            st,
            selection=selection,
            selected_entry=selected_entry,
            visible_items=visible_item_payloads,
            scope=current_scope,
            kind=current_kind,
        )
        if selection.get("hidden", False):
            st.markdown(
                "<div class='catalog-warning'>当前选中项仍保留在右侧详情里，但它已经不在中间结果表格中。你可以点“显示它”清空搜索与字段筛选，让它重新出现。</div>",
                unsafe_allow_html=True,
            )
        _page.render_section_header(
            st,
            _page.SectionHeaderSpec(
                section_id=_page.RESULT_SECTION_ID,
                label="Results",
                title=f"结果表格 · {_kind_label(current_kind)}",
                subtitle="当前结果支持单击切换选中项，deep-link 会记住排序、分页窗口与折叠状态。",
                note=f"{len(visible_item_payloads)} / {len(item_payloads)}",
            ),
        )
        st.markdown("<div id='catalog-results-anchor'></div>", unsafe_allow_html=True)
        results_title = f"结果表格 · {_kind_label(current_kind)}"
        results_label = f"{results_title}（显示 {len(visible_item_payloads)} / {len(item_payloads)}）"
        with st.expander(results_label, expanded=results_collapse == "expanded"):
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
            if len(item_payloads) > len(visible_item_payloads):
                st.caption(f"当前命中 {len(item_payloads)} 条，当前展示前 {len(visible_item_payloads)} 条。")
            else:
                st.caption(f"当前命中 {len(item_payloads)} 条。")
            selected_key = _render_results_table(
                st,
                items=visible_item_payloads,
                scope=current_scope,
                kind=current_kind,
                column_mode=column_mode,
            )
        if selected_key and selected_key != _NO_SELECTION:
            st.caption(f"当前选中：{selected_key}")
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
    floating_locate_target = "catalog-results-anchor" if selected_key and selected_key != _NO_SELECTION else None
    floating_locate_tooltip = (
        "定位当前选中项"
        if selected_key and selected_key != _NO_SELECTION
        else "当前没有选中项"
    )
    _render_floating_nav(
        st,
        locate_target=floating_locate_target,
        locate_tooltip=floating_locate_tooltip,
    )

    with right:
        _page.render_section_header(
            st,
            _page.SectionHeaderSpec(
                section_id=_page.DETAIL_SECTION_ID,
                label="Detail",
                title="详情与跳转",
                subtitle="右侧统一承接条目详情、关系跳转、来源信息与 deep-link 回位。",
            ),
        )
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
        detail_cols = st.columns((1.0, 1.3))
        detail_tab = detail_cols[0].radio(
            "详情 Tab",
            options=list(_DETAIL_TABS),
            index=list(_DETAIL_TABS).index(current_detail_tab),
            horizontal=True,
            format_func=_detail_tab_label,
        )
        st.session_state[detail_tab_key] = detail_tab
        expanded_relation_groups = tuple(
            value
            for value in _shared.normalize_csv_values(st.session_state.get(open_relations_key, ()))
            if value in relation_options
        )
        if detail_tab == "relations" and relation_options:
            chosen_groups = detail_cols[1].multiselect(
                "展开关系组",
                options=list(relation_options),
                default=list(expanded_relation_groups),
                format_func=lambda value: _relation_group_label(str(value), relation_labels),
            )
            expanded_relation_groups = tuple(str(value).strip() for value in chosen_groups if str(value).strip())
        elif detail_tab == "relations":
            detail_cols[1].caption("当前条目没有可展开的关系分组。")
            expanded_relation_groups = ()
        else:
            detail_cols[1].caption("Deep-link 会记住当前详情页签与展开状态。")
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




