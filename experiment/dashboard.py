from __future__ import annotations

import argparse
from html import escape
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

if __package__ in {None, ""}:
    _ROOT = Path(__file__).resolve().parents[1]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    from nsgablack.catalog import dashboard_page as _page
    from nsgablack.catalog import dashboard_shared as _shared
    from nsgablack.catalog import dashboard_shell as _shell
    from nsgablack.plugins import (
        list_runtime_artifact_surfaces,
        list_runtime_run_surfaces,
        runtime_surface_filter_values,
        runtime_surface_summary,
        show_runtime_artifact_surface,
        show_runtime_run_surface,
    )
    from nsgablack.experiment.db import (
        experiment_db_candidate_targets,
        experiment_db_config_info,
        normalize_experiment_db_target,
        resolve_experiment_db_target,
        summarize_experiment_db_error,
    )
    from nsgablack.experiment.filesystem_surface import default_artifact_root, discover_filesystem_run_surfaces
else:
    from ..catalog import dashboard_page as _page
    from ..catalog import dashboard_shared as _shared
    from ..catalog import dashboard_shell as _shell
    from ..plugins import (
        list_runtime_artifact_surfaces,
        list_runtime_run_surfaces,
        runtime_surface_filter_values,
        runtime_surface_summary,
        show_runtime_artifact_surface,
        show_runtime_run_surface,
    )
    from .db import (
        experiment_db_candidate_targets,
        experiment_db_config_info,
        normalize_experiment_db_target,
        resolve_experiment_db_target,
        summarize_experiment_db_error,
    )
    from .filesystem_surface import default_artifact_root, discover_filesystem_run_surfaces

try:
    import streamlit as st
except Exception as exc:  # pragma: no cover
    raise SystemExit(
        "streamlit is required for the nsgablack experiment dashboard. Install with: python -m pip install streamlit"
    ) from exc


_VIEW_OPTIONS: tuple[str, ...] = ("run_catalog", "artifact_catalog")
_VIEW_LABELS: dict[str, str] = {
    "run_catalog": "杩愯琛ㄩ潰 / Run Surface",
    "artifact_catalog": "浜х墿琛ㄩ潰 / Artifact Surface",
}
_DETAIL_TABS: tuple[str, ...] = ("overview", "contracts", "payload")
_DETAIL_TAB_LABELS: dict[str, str] = {
    "overview": "姒傝 / Overview",
    "contracts": "鍚堝悓灞?/ Contracts",
    "payload": "鍘熷杞借嵎 / Payload",
}
_COLUMN_MODE_OPTIONS: tuple[str, ...] = ("compact", "standard", "full")
_COLUMN_MODE_LABELS: dict[str, str] = {
    "compact": "绱у噾鍒?/ Compact",
    "standard": "鏍囧噯鍒?/ Standard",
    "full": "瀹屾暣鍒?/ Full",
}
_RESULTS_COLLAPSE_OPTIONS: tuple[str, ...] = ("expanded", "collapsed")
_RESULTS_COLLAPSE_LABELS: dict[str, str] = {
    "expanded": "灞曞紑 / Expanded",
    "collapsed": "鎶樺彔 / Collapsed",
}
_PAGE_SIZE_OPTIONS: tuple[int, ...] = (20, 50, 100, 250)
_ANY_OPTION_LABEL = "涓嶉檺 / Any"
_NO_SELECTION = _shared.NO_SELECTION
_QUERY_BASE_KEYS: tuple[str, ...] = (
    "db",
    "limit",
    "view",
    "selected",
    "detail_tab",
    "column_mode",
    "page_size",
    "results_collapse",
    "query",
)
_FILTER_FIELDS_BY_VIEW: dict[str, tuple[str, ...]] = {
    "run_catalog": (
        "run_status",
        "run_surface_key",
        "run_driver_ref",
        "run_family_ref",
        "run_assembly_signature",
        "run_screening_protocol",
        "run_outer_search_protocol",
        "run_structure_head",
        "run_search_input_space",
        "run_pool_expansion_unit",
        "run_gradient_guidance_mode",
        "run_basis_binding_mode",
        "run_escape_policy",
        "run_equivalence_expression_protocol",
        "run_equivalence_expression_mode",
        "run_interference_feature_protocol",
        "run_interference_feature_mode",
        "run_cross_explanatory_rejection_mode",
        "run_trivial_nonlinearity_penalty_mode",
        "run_environment_invariance_audit_mode",
        "run_lane_id",
        "run_lane_family",
        "run_challenger_objective_protocol",
        "run_pool_expansion_bias_protocol",
        "run_joint_core_score_min",
        "run_cross_lane_stability_min",
    ),
    "artifact_catalog": (
        "artifact_role",
        "artifact_producer_ref",
        "artifact_surface_key",
        "artifact_assembly_signature",
    ),
}

_SELECTION_HOOK_LABEL = "结果内快速切换 / Quick Selection"
_SELECTION_JUMP_LABEL = "按 selection_key 跳转 / Jump by selection_key"
_DEEPLINK_LABEL = "Deep-Link / 直达链接"
_CURRENT_SELECTION_LABEL = "当前选中项 / Current Selection"
_PREV_LINK_LABEL = "上一项链接 / Previous Link"
_NEXT_LINK_LABEL = "下一项链接 / Next Link"


def dashboard_script_path() -> Path:
    return Path(__file__).resolve()


def build_streamlit_command(
    *,
    db_path: str,
    limit: int = 500,
    column_mode: str = _shared.DEFAULT_COLUMN_MODE,
    page_size: int = _shared.DEFAULT_PAGE_SIZE,
    results_collapse: str = _shared.DEFAULT_RESULTS_COLLAPSE,
    host: str | None = None,
    port: int | None = None,
    headless: bool = False,
) -> list[str]:
    command = [sys.executable, "-m", "streamlit", "run", str(dashboard_script_path())]
    if host:
        command.extend(["--server.address", str(host)])
    if port is not None:
        command.extend(["--server.port", str(int(port))])
    if headless:
        command.extend(["--server.headless", "true"])
    command.extend(
        [
            "--",
            "--db",
            str(db_path),
            "--limit",
            str(int(limit)),
            "--column-mode",
            str(column_mode),
            "--page-size",
            str(int(page_size)),
            "--results-collapse",
            str(results_collapse),
        ]
    )
    return command


def _set_page_config() -> None:
    try:
        st.set_page_config(page_title="nsgablack experiment", page_icon="NS", layout="wide")
    except Exception:
        return


def _inject_style() -> None:
    st.markdown(
        f"""
<style>
{_page.PAGE_PROTOCOL_STYLE}
.runtime-chip {{
  display: inline-flex;
  align-items: center;
  margin: 0 0.35rem 0.35rem 0;
  padding: 0.3rem 0.65rem;
  border-radius: 999px;
  border: 1px solid rgba(101, 70, 35, 0.16);
  background: rgba(255, 249, 240, 0.95);
  color: #4a3420;
  font-size: 0.82rem;
}}
.selection-float {{
  margin: 0.3rem 0 0.9rem 0;
  padding: 0.8rem 0.95rem;
  border-radius: 18px;
  border: 1px solid rgba(101, 70, 35, 0.16);
  background: linear-gradient(180deg, rgba(255,250,243,0.98), rgba(250,242,230,0.98));
}}
.selection-float-label {{
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 800;
  color: #8b6840;
}}
.selection-float-title {{
  font-size: 1rem;
  font-weight: 800;
  color: #2f2115;
  margin-top: 0.1rem;
}}
.selection-float-meta {{
  color: #65513a;
  margin-top: 0.15rem;
  font-size: 0.86rem;
}}
.selection-link-row {{
  display: flex;
  gap: 0.55rem;
  flex-wrap: wrap;
  margin: 0.45rem 0 0.75rem 0;
}}
.selection-link-chip {{
  display: inline-flex;
  align-items: center;
  padding: 0.42rem 0.82rem;
  border-radius: 999px;
  border: 1px solid rgba(101, 70, 35, 0.18);
  background: #fffaf3;
  color: #4a3420;
  text-decoration: none;
  font-size: 0.84rem;
  font-weight: 700;
}}
.selection-link-chip.is-disabled {{
  opacity: 0.5;
  pointer-events: none;
}}
.catalog-warning {{
  margin: 0.5rem 0 0.75rem 0;
  padding: 0.7rem 0.85rem;
  border-radius: 14px;
  border: 1px solid rgba(164, 97, 45, 0.18);
  background: #fff5eb;
  color: #6e4a2a;
}}
</style>
""",
        unsafe_allow_html=True,
    )


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _metric_text(value: Any) -> str:
    try:
        return f"{float(value):.6g}"
    except Exception:
        return str(value or "-")


def _optional_float(value: Any) -> float | None:
    text = _text(value)
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def _optional_choice_label(value: Any) -> str:
    return _ANY_OPTION_LABEL if not _text(value) else str(value)


def _normalize_view_mode(value: Any) -> str:
    key = _text(value)
    return key if key in _VIEW_OPTIONS else _VIEW_OPTIONS[0]


def _normalize_detail_tab(value: Any) -> str:
    key = _text(value)
    return key if key in _DETAIL_TABS else _shared.DEFAULT_DETAIL_TAB


def _normalize_column_mode(value: Any) -> str:
    key = _text(value)
    return key if key in _COLUMN_MODE_OPTIONS else _shared.DEFAULT_COLUMN_MODE


def _normalize_page_size(value: Any) -> int:
    try:
        page_size = int(str(value or "").strip())
    except Exception:
        return _shared.DEFAULT_PAGE_SIZE
    return page_size if page_size > 0 else _shared.DEFAULT_PAGE_SIZE


def _normalize_results_collapse(value: Any) -> str:
    key = _text(value)
    return key if key in _RESULTS_COLLAPSE_OPTIONS else _shared.DEFAULT_RESULTS_COLLAPSE


def _view_state_key(view_mode: str, name: str) -> str:
    return _shared.view_state_key("experiment", view_mode, name)


def _facet_state_key(view_mode: str, field_name: str) -> str:
    return _shared.facet_state_key("experiment", view_mode, field_name)


def _read_query_params(st_mod: Any) -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
    return _shared.read_query_params(st_mod, base_keys=_QUERY_BASE_KEYS)


def _build_deep_link_query(
    *,
    base_params: Mapping[str, object],
    field_filters: Mapping[str, object] | None = None,
) -> str:
    return _shared.build_deep_link_query(base_params=base_params, field_filters=field_filters)


def _write_query_params(*, base_params: Mapping[str, object], field_filters: Mapping[str, object] | None = None) -> None:
    _shared.write_query_params(st, base_params=base_params, field_filters=field_filters)


def _query_sync_signature(
    *,
    view_mode: str,
    base_params: Mapping[str, object],
    field_filters: Mapping[str, object],
) -> tuple[tuple[str, str], ...]:
    items: list[tuple[str, str]] = [("view_mode", str(view_mode))]
    for key in _QUERY_BASE_KEYS:
        items.append((key, _text(base_params.get(key))))
    for field_name in _FILTER_FIELDS_BY_VIEW.get(view_mode, ()):
        items.append((f"f_{field_name}", _text(field_filters.get(field_name))))
    return tuple(items)


def _sync_session_state_from_query(args: argparse.Namespace, query_params: Mapping[str, str], query_filters: Mapping[str, tuple[str, ...]]) -> str:
    view_mode = _normalize_view_mode(query_params.get("view") or _VIEW_OPTIONS[0])
    detail_tab_key = _view_state_key(view_mode, "detail_tab")
    column_mode_key = _view_state_key(view_mode, "column_mode")
    page_size_key = _view_state_key(view_mode, "page_size")
    results_collapse_key = _view_state_key(view_mode, "results_collapse")
    field_filters = {
        field_name: (query_filters.get(field_name, ("",))[0] if query_filters.get(field_name) else "")
        for field_name in _FILTER_FIELDS_BY_VIEW.get(view_mode, ())
    }
    base_params = {
        "db": _text(query_params.get("db")) or str(args.db),
        "limit": str(int(query_params.get("limit") or args.limit)),
        "view": view_mode,
        "selected": _text(query_params.get("selected")),
        "detail_tab": _normalize_detail_tab(query_params.get("detail_tab")),
        "column_mode": _normalize_column_mode(query_params.get("column_mode") or args.column_mode),
        "page_size": str(_normalize_page_size(query_params.get("page_size") or args.page_size)),
        "results_collapse": _normalize_results_collapse(query_params.get("results_collapse") or args.results_collapse),
        "query": _text(query_params.get("query")),
    }
    signature = _query_sync_signature(view_mode=view_mode, base_params=base_params, field_filters=field_filters)
    last_signature = st.session_state.get("experiment_ui_last_query_signature")
    if last_signature != signature:
        st.session_state["experiment_ui_db"] = str(base_params["db"])
        st.session_state["experiment_ui_limit"] = int(base_params["limit"])
        st.session_state["experiment_ui_query"] = str(base_params["query"])
        st.session_state["experiment_ui_view"] = view_mode
        st.session_state["experiment_ui_selected"] = str(base_params["selected"])
        st.session_state[detail_tab_key] = str(base_params["detail_tab"])
        st.session_state[column_mode_key] = str(base_params["column_mode"])
        st.session_state[page_size_key] = int(base_params["page_size"])
        st.session_state[results_collapse_key] = str(base_params["results_collapse"])
        for field_name, value in field_filters.items():
            st.session_state[_facet_state_key(view_mode, field_name)] = str(value)
        st.session_state["experiment_ui_last_query_signature"] = signature
    return view_mode


def _selection_run_key(run_id: str) -> str:
    return f"run:{run_id}"


def _selection_artifact_key(run_id: str, artifact_id: str) -> str:
    return f"artifact:{run_id}:{artifact_id}"


def _decode_selection_key(value: str) -> dict[str, str] | None:
    text = _text(value)
    if not text:
        return None
    if text.startswith("artifact:"):
        parts = text.split(":", 2)
        if len(parts) == 3:
            return {"kind": "artifact", "run_id": parts[1], "artifact_id": parts[2]}
    if text.startswith("run:"):
        return {"kind": "run", "run_id": text.split(":", 1)[1]}
    return None


def _runtime_payload_section(result_payload: Mapping[str, Any], key: str) -> Any:
    if key in result_payload:
        return result_payload.get(key)
    nested = result_payload.get("payload")
    if isinstance(nested, Mapping) and key in nested:
        return nested.get(key)
    return None


def _run_like_payload(result_payload: Mapping[str, Any]) -> dict[str, Any]:
    result = _mapping(result_payload)
    for key in ("run_summary", "best_run", "locked_best_run", "unlocked_best_run"):
        payload = _mapping(result.get(key))
        if payload:
            return payload
    payload = _mapping(result.get("payload"))
    if payload:
        nested = _mapping(payload.get("run_summary"))
        if nested:
            return nested
    return {}


def _render_json_block(title: str, payload: Any, *, empty_message: str) -> None:
    st.markdown(f"**{title}**")
    if payload in (None, "", {}, [], ()):
        st.caption(empty_message)
        return
    st.code(_json_text(payload), language="json")


def _render_contract_chips(label: str, refs: Sequence[Any] | None) -> None:
    values = [str(item).strip() for item in tuple(refs or ()) if str(item).strip()]
    st.markdown(f"**{label}**")
    if not values:
        st.caption("褰撳墠涓虹┖ / No values.")
        return
    st.markdown("".join(f"<span class='runtime-chip'>{escape(item)}</span>" for item in values), unsafe_allow_html=True)


def _selected_table_row_indices(event: Any) -> tuple[int, ...]:
    if event is None:
        return ()
    selection = getattr(event, "selection", None)
    if selection is None and isinstance(event, Mapping):
        selection = event.get("selection")
    if selection is None:
        return ()
    rows = getattr(selection, "rows", None)
    if rows is None and isinstance(selection, Mapping):
        rows = selection.get("rows")
    if not isinstance(rows, Sequence):
        return ()
    out: list[int] = []
    for raw in rows:
        try:
            out.append(int(raw))
        except Exception:
            continue
    return tuple(out)


def _query_match(row: Mapping[str, Any], query: str, *, kind: str) -> bool:
    needle = _text(query).lower()
    if not needle:
        return True
    if kind == "run":
        keys = (
            "run_id",
            "status",
            "surface_key",
            "driver_ref",
            "family_ref",
            "assembly_signature",
            "screening_protocol",
            "outer_search_protocol",
            "structure_head",
            "search_input_space",
            "pool_expansion_unit",
            "gradient_guidance_mode",
            "basis_binding_mode",
            "escape_policy",
            "equivalence_expression_protocol",
            "equivalence_expression_mode",
            "interference_feature_protocol",
            "interference_feature_mode",
            "cross_explanatory_rejection_mode",
            "trivial_nonlinearity_penalty_mode",
            "environment_invariance_audit_mode",
            "lane_id",
            "lane_family",
            "challenger_objective_protocol",
            "pool_expansion_bias_protocol",
            "cross_lane_stability",
            "subject_key",
        )
    else:
        keys = (
            "artifact_id",
            "artifact_role",
            "producer_ref",
            "surface_key",
            "assembly_signature",
            "run_id",
        )
    text_blob = "\n".join(_text(row.get(key)) for key in keys).lower()
    return needle in text_blob


def _run_table_records(rows: Sequence[Mapping[str, Any]], *, column_mode: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in rows:
        payload = {
            "run_id": row.get("run_id"),
            "status": row.get("status"),
            "surface_key": row.get("surface_key"),
            "driver_ref": row.get("driver_ref"),
            "primary_metric": _metric_text(row.get("primary_metric_value")),
            "finished_at_utc": row.get("finished_at_utc"),
        }
        if column_mode in {"standard", "full"}:
            payload["family_ref"] = row.get("family_ref")
            payload["screening_protocol"] = row.get("screening_protocol")
            payload["outer_search_protocol"] = row.get("outer_search_protocol")
            payload["lane_id"] = row.get("lane_id")
            payload["structure_head"] = row.get("structure_head")
            payload["basis_binding_mode"] = row.get("basis_binding_mode")
            payload["joint_core_score"] = row.get("joint_core_score")
        if column_mode == "full":
            payload["lane_family"] = row.get("lane_family")
            payload["challenger_objective_protocol"] = row.get("challenger_objective_protocol")
            payload["pool_expansion_bias_protocol"] = row.get("pool_expansion_bias_protocol")
            payload["equivalence_expression_protocol"] = row.get("equivalence_expression_protocol")
            payload["interference_feature_protocol"] = row.get("interference_feature_protocol")
            payload["cross_lane_stability"] = row.get("cross_lane_stability")
            payload["search_input_space"] = row.get("search_input_space")
            payload["pool_expansion_unit"] = row.get("pool_expansion_unit")
            payload["gradient_guidance_mode"] = row.get("gradient_guidance_mode")
            payload["escape_policy"] = row.get("escape_policy")
            payload["selection_key"] = row.get("selection_key")
        records.append(payload)
    return records


def _artifact_table_records(rows: Sequence[Mapping[str, Any]], *, column_mode: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in rows:
        artifact_record = _mapping(row.get("artifact_record_json"))
        payload = {
            "artifact_id": row.get("artifact_id"),
            "artifact_role": row.get("artifact_role"),
            "producer_ref": row.get("producer_ref"),
            "surface_key": row.get("surface_key"),
            "run_id": row.get("run_id"),
            "created_at_utc": row.get("created_at_utc"),
        }
        if column_mode in {"standard", "full"}:
            payload["assembly_signature"] = row.get("assembly_signature")
            payload["format"] = artifact_record.get("format")
        if column_mode == "full":
            payload["selection_key"] = row.get("selection_key")
            payload["path"] = artifact_record.get("path")
        records.append(payload)
    return records


def _run_option_label(row: Mapping[str, Any]) -> str:
    run_id = _text(row.get("run_id")) or "-"
    status = _text(row.get("status")) or "-"
    family = _text(row.get("family_ref")) or _text(row.get("surface_key")) or "-"
    return f"{run_id} 路 {status} 路 {family}"


def _artifact_option_label(row: Mapping[str, Any]) -> str:
    artifact_id = _text(row.get("artifact_id")) or "-"
    role = _text(row.get("artifact_role")) or "-"
    run_id = _text(row.get("run_id")) or "-"
    return f"{artifact_id} 路 {role} 路 {run_id}"


def _selection_state(selected_key: str, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    key = _text(selected_key)
    visible_keys = [str(row.get("selection_key", "")) for row in rows]
    if not key or key == _NO_SELECTION:
        return {"selected_key": "", "visible": False, "hidden": False, "row_index": None}
    if key in visible_keys:
        return {
            "selected_key": key,
            "visible": True,
            "hidden": False,
            "row_index": visible_keys.index(key),
        }
    return {"selected_key": key, "visible": False, "hidden": True, "row_index": None}


def _selection_title(row: Mapping[str, Any], *, view_mode: str) -> str:
    return _run_option_label(row) if view_mode == "run_catalog" else _artifact_option_label(row)


def _render_selection_float(*, selection: Mapping[str, Any], rows: Sequence[Mapping[str, Any]], view_mode: str) -> None:
    selected_key = _text(selection.get("selected_key"))
    if not selected_key:
        return
    row_by_key = {str(row.get("selection_key")): row for row in rows}
    row = row_by_key.get(selected_key, {})
    title = _selection_title(row, view_mode=view_mode) if row else selected_key
    row_index = selection.get("row_index")
    if selection.get("visible") and isinstance(row_index, int):
        meta = f"当前选中项位于结果表格第 {int(row_index) + 1} 行。/ The current selection is visible in result row {int(row_index) + 1}."
    elif selection.get("hidden"):
        meta = "当前选中项仍保留在右侧详情里，但它已经不在中间结果表格中。/ The current selection is still shown in the detail pane, but it is no longer in the visible result table."
    else:
        meta = "当前选中项不在结果表格里。/ The current selection is not present in the result table."
    st.markdown(
        (
            "<div class='selection-float'>"
            f"<div class='selection-float-label'>{escape(_CURRENT_SELECTION_LABEL)}</div>"
            f"<div class='selection-float-title'>{escape(title)}</div>"
            f"<div class='selection-float-meta'><code>{escape(selected_key)}</code><br/>{escape(meta)}</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def _render_selection_hook(*, rows: Sequence[Mapping[str, Any]], view_mode: str, selected_key: str) -> str:
    if not rows:
        return _text(selected_key)
    row_by_key = {str(row.get("selection_key")): row for row in rows}
    option_keys = [str(row.get("selection_key")) for row in rows if _text(row.get("selection_key"))]
    active_key = _text(selected_key) if _text(selected_key) in row_by_key else option_keys[0]
    st.markdown(f"**{_SELECTION_HOOK_LABEL}**")
    hook_cols = st.columns((1.2, 1.0))
    chosen_key = hook_cols[0].selectbox(
        _CURRENT_SELECTION_LABEL,
        options=option_keys,
        index=option_keys.index(active_key),
        format_func=lambda key: _selection_title(row_by_key.get(str(key), {}), view_mode=view_mode),
        key=f"experiment_ui_selection_hook::{view_mode}",
    )
    jump_default = _text(st.session_state.get(f"experiment_ui_selection_jump::{view_mode}")) or chosen_key
    jump_key = hook_cols[1].text_input(
        _SELECTION_JUMP_LABEL,
        value=jump_default,
        key=f"experiment_ui_selection_jump::{view_mode}",
        help="Paste a selection_key to jump directly to a run or artifact row.",
    )
    jump_candidate = _text(jump_key)
    if jump_candidate in row_by_key:
        return jump_candidate
    return _text(chosen_key)


def _render_selection_nav_links(
    *,
    rows: Sequence[Mapping[str, Any]],
    selection: Mapping[str, Any],
    base_params: Mapping[str, object],
    field_filters: Mapping[str, object],
) -> None:
    selected_key = _text(selection.get("selected_key"))
    if not selected_key:
        return
    row_index = selection.get("row_index")
    visible = bool(selection.get("visible")) and isinstance(row_index, int)
    prev_html = f"<span class='selection-link-chip is-disabled'>{escape(_PREV_LINK_LABEL)}</span>"
    next_html = f"<span class='selection-link-chip is-disabled'>{escape(_NEXT_LINK_LABEL)}</span>"
    if visible and len(rows) > 1:
        if int(row_index) > 0:
            prev_key = str(rows[int(row_index) - 1].get("selection_key") or "")
            prev_query = _build_deep_link_query(base_params={**dict(base_params), "selected": prev_key}, field_filters=field_filters)
            prev_html = f"<a class='selection-link-chip' href='{escape(prev_query)}'>{escape(_PREV_LINK_LABEL)}</a>"
        if int(row_index) < len(rows) - 1:
            next_key = str(rows[int(row_index) + 1].get("selection_key") or "")
            next_query = _build_deep_link_query(base_params={**dict(base_params), "selected": next_key}, field_filters=field_filters)
            next_html = f"<a class='selection-link-chip' href='{escape(next_query)}'>{escape(_NEXT_LINK_LABEL)}</a>"
    st.markdown(f"<div class='selection-link-row'>{prev_html}{next_html}</div>", unsafe_allow_html=True)


def _result_rows_frame(rows: Sequence[Mapping[str, Any]], *, view_mode: str, column_mode: str) -> pd.DataFrame:
    if view_mode == "run_catalog":
        return pd.DataFrame(_run_table_records(rows, column_mode=column_mode))
    return pd.DataFrame(_artifact_table_records(rows, column_mode=column_mode))


def _render_results_table(
    *,
    rows: Sequence[Mapping[str, Any]],
    view_mode: str,
    column_mode: str,
    page_size: int,
    selected_key: str,
) -> str:
    if not rows:
        st.info("褰撳墠绛涢€夋潯浠朵笅娌℃湁缁撴灉 / No rows match the current filters.")
        return ""
    visible_rows = list(rows[: max(1, int(page_size))])
    visible_keys = {str(row.get("selection_key")) for row in visible_rows if _text(row.get("selection_key"))}
    table_event = st.dataframe(
        _result_rows_frame(visible_rows, view_mode=view_mode, column_mode=column_mode),
        width="stretch",
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key=f"experiment_ui::results::{view_mode}",
    )
    selected_rows = _selected_table_row_indices(table_event)
    if selected_rows:
        index = int(selected_rows[0])
        if 0 <= index < len(visible_rows):
            return _text(visible_rows[index].get("selection_key"))
    current_selected = _text(selected_key)
    if current_selected in visible_keys:
        return current_selected
    return _text(visible_rows[0].get("selection_key"))


def _artifact_rows_frame(rows: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    items: list[dict[str, Any]] = []
    for row in rows:
        artifact_record = _mapping(row.get("artifact_record_json"))
        items.append(
            {
                "artifact_id": row.get("artifact_id"),
                "artifact_role": row.get("artifact_role"),
                "producer_ref": row.get("producer_ref"),
                "format": artifact_record.get("format"),
                "path": artifact_record.get("path"),
            }
        )
    return pd.DataFrame(items)


def _cycle_reports_frame(rows: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    items: list[dict[str, Any]] = []
    for row in rows:
        comparison = row.get("comparison") if isinstance(row.get("comparison"), Mapping) else {}
        best_unlocked_rmse = _optional_float((comparison or {}).get("vanilla_best_test_rmse"))
        best_locked_rmse = _optional_float((comparison or {}).get("locked_best_test_rmse"))
        best_unlocked_exact = _optional_float((comparison or {}).get("vanilla_best_exact_term_recovery_score"))
        best_locked_exact = _optional_float((comparison or {}).get("locked_best_exact_term_recovery_score"))
        best_unlocked_family = _optional_float((comparison or {}).get("vanilla_best_family_term_recovery_score"))
        best_locked_family = _optional_float((comparison or {}).get("locked_best_family_term_recovery_score"))
        items.append(
            {
                "cycle": row.get("cycle_key") or f"cycle_{int(row.get('cycle_index', 0) or 0):02d}",
                "unlocked_runs": row.get("unlocked_run_count"),
                "locked_runs": row.get("locked_run_count"),
                "core_basis_count": row.get("core_basis_count"),
                "locked_seed_terms": row.get("locked_seed_terms"),
                "best_unlocked_rmse": best_unlocked_rmse,
                "best_locked_rmse": best_locked_rmse,
                "rmse_gain": None if best_unlocked_rmse is None or best_locked_rmse is None else float(best_unlocked_rmse) - float(best_locked_rmse),
                "best_unlocked_exact": best_unlocked_exact,
                "best_locked_exact": best_locked_exact,
                "exact_gain": None if best_unlocked_exact is None or best_locked_exact is None else float(best_locked_exact) - float(best_unlocked_exact),
                "best_unlocked_family": best_unlocked_family,
                "best_locked_family": best_locked_family,
                "family_gain": None if best_unlocked_family is None or best_locked_family is None else float(best_locked_family) - float(best_unlocked_family),
            }
        )
    return pd.DataFrame(items)


def _stage_reports_frame(rows: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    items: list[dict[str, Any]] = []
    for row in rows:
        metrics = row.get("metrics") if isinstance(row.get("metrics"), Mapping) else {}
        items.append(
            {
                "cycle": row.get("cycle_key") or f"cycle_{int(row.get('cycle_index', 0) or 0):02d}",
                "level": row.get("level"),
                "stage": row.get("stage_key"),
                "status": row.get("status"),
                "run_count": row.get("run_count"),
                "best_run_id": row.get("best_run_id"),
                "primary_metric": f"{_text(row.get('primary_metric_name')) or '-'}={_metric_text(row.get('primary_metric_value'))}",
                "notes": ", ".join(
                    filter(
                        None,
                        (
                            f"backfill={metrics.get('selection_backfill_mode')}" if metrics.get("selection_backfill_mode") else "",
                            f"backfill_rows={metrics.get('selected_backfill_rows')}" if metrics.get("selected_backfill_rows") is not None else "",
                            f"weight_field={metrics.get('selection_run_weight_field')}" if metrics.get("selection_run_weight_field") else "",
                        ),
                    )
                ),
            }
        )
    return pd.DataFrame(items)


def _core_basis_evolution_frame(rows: Sequence[Mapping[str, Any]], *, limit: int = 40) -> pd.DataFrame:
    items: list[dict[str, Any]] = []
    for row in list(rows[: max(1, int(limit))]):
        items.append(
            {
                "cycle": row.get("cycle_key") or f"cycle_{int(row.get('cycle_index', 0) or 0):02d}",
                "mode": row.get("equivalence_mode"),
                "rank": row.get("rank"),
                "basis_key": row.get("basis_key") or row.get("basis_class_id"),
                "expression": row.get("representative_expression"),
                "support_rate": row.get("support_rate"),
                "support_weight_rate": row.get("support_weight_rate"),
                "exact_stability": row.get("exact_stability"),
                "cross_lane_stability": row.get("cross_lane_stability"),
                "joint_core_score": row.get("joint_core_score"),
                "selected_as_core": row.get("selected_as_core"),
                "selection_source": row.get("selection_source"),
            }
        )
    return pd.DataFrame(items)


def _leaderboards_frame(leaderboards: Mapping[str, Any]) -> pd.DataFrame:
    items: list[dict[str, Any]] = []
    for key in ("best_rmse", "best_exact", "best_balanced"):
        row = leaderboards.get(key) if isinstance(leaderboards.get(key), Mapping) else {}
        if not row:
            continue
        items.append(
            {
                "board": key,
                "phase": row.get("phase"),
                "cycle": row.get("cycle_key") or f"cycle_{int(row.get('cycle_index', 0) or 0):02d}",
                "run_id": row.get("run_id"),
                "rmse": row.get("test_rmse"),
                "exact": row.get("exact_term_recovery_score"),
                "phase_equiv": row.get("phase_equivalent_term_recovery_score"),
                "family": row.get("family_level_term_recovery_score"),
                "balanced_score": row.get("balanced_score"),
            }
        )
    return pd.DataFrame(items)


def _selected_core_rows_frame(rows: Sequence[Mapping[str, Any]], *, limit: int = 20) -> pd.DataFrame:
    items: list[dict[str, Any]] = []
    for row in list(rows[: max(1, int(limit))]):
        items.append(
            {
                "mode": row.get("equivalence_mode"),
                "basis_key": row.get("basis_class_id") or row.get("representative_family_class_id"),
                "seed_name": row.get("representative_seed_name"),
                "expression": row.get("representative_expression"),
                "features": ", ".join(str(v) for v in tuple(row.get("feature_names", ())) if str(v).strip()),
                "support_rate": row.get("support_rate"),
                "support_weight_rate": row.get("support_weight_rate"),
                "exact_stability": row.get("exact_stability"),
                "cross_lane_stability": row.get("cross_lane_stability"),
                "joint_core_score": row.get("joint_core_score"),
                "selection_source": row.get("selection_source"),
            }
        )
    return pd.DataFrame(items)


def _selection_strategy_frame(selection_strategy: Mapping[str, Any]) -> pd.DataFrame:
    weights = selection_strategy.get("joint_core_score_weights")
    return pd.DataFrame(
        [
            {
                "backfill_mode": selection_strategy.get("backfill_mode"),
                "min_seed_terms": selection_strategy.get("min_seed_terms"),
                "run_weight_field": selection_strategy.get("run_weight_field"),
                "joint_core_score_weights": _json_text(weights) if isinstance(weights, Mapping) else weights,
            }
        ]
    )


def _core_table_summary_frame(core_tables: Mapping[str, Any]) -> pd.DataFrame:
    items: list[dict[str, Any]] = []
    for mode, rows in core_tables.items():
        table_rows = [dict(item) for item in tuple(rows or ()) if isinstance(item, Mapping)]
        top = table_rows[0] if table_rows else {}
        items.append(
            {
                "mode": mode,
                "rows": len(table_rows),
                "selected_rows": sum(1 for row in table_rows if bool(row.get("selected_as_core"))),
                "top_basis": top.get("basis_class_id") or top.get("representative_expression"),
                "top_expression": top.get("representative_expression"),
                "top_support_rate": top.get("support_rate"),
                "top_joint_core_score": top.get("joint_core_score"),
            }
        )
    return pd.DataFrame(items)


def _basis_object_gradient_signals_frame(rows: Sequence[Mapping[str, Any]], *, limit: int = 12) -> pd.DataFrame:
    items: list[dict[str, Any]] = []
    for row in list(rows[: max(1, int(limit))]):
        items.append(
            {
                "object_key": row.get("object_key"),
                "gradient_score": row.get("gradient_score"),
                "abs_gradient_score": row.get("abs_gradient_score"),
                "residual_gain": row.get("residual_gain"),
                "stability": row.get("stability"),
            }
        )
    return pd.DataFrame(items)


def _basis_object_expansion_candidates_frame(rows: Sequence[Mapping[str, Any]], *, limit: int = 12) -> pd.DataFrame:
    items: list[dict[str, Any]] = []
    for row in list(rows[: max(1, int(limit))]):
        items.append(
            {
                "candidate_key": row.get("candidate_key"),
                "expression": row.get("expression"),
                "priority": row.get("priority"),
                "source_object_keys": ", ".join(str(v) for v in tuple(row.get("source_object_keys", ())) if str(v).strip()),
                "family": _mapping(row.get("metadata")).get("family"),
            }
        )
    return pd.DataFrame(items)


def _render_basis_object_gradient_pool_card(*, row: Mapping[str, Any], result_payload: Mapping[str, Any]) -> None:
    run_payload = _run_like_payload(result_payload)
    pool_payload = _mapping(
        _runtime_payload_section(result_payload, "basis_object_gradient_pool")
        or run_payload.get("basis_object_gradient_pool")
    )
    if not pool_payload:
        inner_symbolic_search = _mapping(run_payload.get("inner_symbolic_search"))
        pool_payload = _mapping(inner_symbolic_search.get("object_gradient_pool"))
    basis_context = _mapping(
        _runtime_payload_section(result_payload, "basis_context")
        or run_payload.get("basis_context")
        or pool_payload.get("basis_context")
    )
    if not pool_payload:
        st.caption("褰撳墠鏈褰?basis_object_gradient_pool / No recorded basis_object_gradient_pool.")
        return

    top_signals = [dict(item) for item in tuple(pool_payload.get("top_object_signals", ())) if isinstance(item, Mapping)]
    expansion_candidates = [
        dict(item) for item in tuple(pool_payload.get("expansion_candidates", ())) if isinstance(item, Mapping)
    ]
    selected_basis = [dict(item) for item in tuple(basis_context.get("selected_basis", ())) if isinstance(item, Mapping)]
    locked_basis_keys = [str(v) for v in tuple(basis_context.get("locked_basis_keys", ())) if str(v).strip()]

    st.markdown("**Basis-Object 姊害鎷撴睜 / Basis-Object Gradient Pool**")
    meta_cols = st.columns(4)
    meta_cols[0].metric("鍗忚 / Protocol", _text(pool_payload.get("protocol")) or "-")
    meta_cols[1].metric("缁戝畾 / Binding", _text(row.get("basis_binding_mode")) or _text(basis_context.get("binding_mode")) or "-")
    meta_cols[2].metric("閫冮€?/ Escape", _text(row.get("escape_policy")) or "-")
    meta_cols[3].metric("杩唬 / Iterations", str(pool_payload.get("iteration_count") or "-"))

    stat_cols = st.columns(4)
    stat_cols[0].metric("瀵硅薄淇″彿 / Signals", str(len(top_signals)))
    stat_cols[1].metric("鎵╂睜鍊欓€?/ Candidates", str(len(expansion_candidates)))
    stat_cols[2].metric("Selected Basis", str(len(selected_basis)))
    stat_cols[3].metric("Locked Basis", str(len(locked_basis_keys)))

    if locked_basis_keys:
        _render_contract_chips("閿佸畾 Basis / Locked Basis Keys", locked_basis_keys)

    left, right = st.columns(2)
    with left:
        if top_signals:
            st.dataframe(_basis_object_gradient_signals_frame(top_signals), width="stretch", hide_index=True)
        else:
            st.caption("褰撳墠鏈褰曞璞＄骇姊害淇″彿 / No object-level gradient signals recorded.")
    with right:
        if expansion_candidates:
            st.dataframe(_basis_object_expansion_candidates_frame(expansion_candidates), width="stretch", hide_index=True)
        else:
            st.caption("褰撳墠鏈褰曟墿姹犲€欓€?/ No expansion candidates recorded.")


def _render_run_detail(detail_tab: str, row: Mapping[str, Any], artifact_rows: Sequence[Mapping[str, Any]]) -> None:
    surface_record = row.get("surface_record_json") if isinstance(row.get("surface_record_json"), Mapping) else {}
    assembly_record = row.get("assembly_record_json") if isinstance(row.get("assembly_record_json"), Mapping) else {}
    run_record = row.get("run_record_json") if isinstance(row.get("run_record_json"), Mapping) else {}
    result_payload = row.get("result_json") if isinstance(row.get("result_json"), Mapping) else {}
    run_payload = _run_like_payload(result_payload)
    artifact_records = row.get("artifact_records_json") if isinstance(row.get("artifact_records_json"), Sequence) else []
    orchestration_report = _runtime_payload_section(result_payload, "orchestration_report")
    leaderboards = _runtime_payload_section(result_payload, "leaderboards")
    cycle_rows = [dict(item) for item in tuple(_runtime_payload_section(result_payload, "cycle_reports") or ()) if isinstance(item, Mapping)]
    stage_rows = [dict(item) for item in tuple(_runtime_payload_section(result_payload, "stage_reports") or ()) if isinstance(item, Mapping)]
    evolution_rows = [dict(item) for item in tuple(_runtime_payload_section(result_payload, "core_basis_evolution") or ()) if isinstance(item, Mapping)]
    best_cycle = _mapping(
        _runtime_payload_section(result_payload, "best_cycle")
        or run_payload.get("best_cycle")
        or _mapping(orchestration_report).get("best_cycle")
    )
    core_selection = _mapping(
        _runtime_payload_section(result_payload, "core_selection")
        or run_payload.get("core_selection")
        or best_cycle.get("core_selection")
    )
    core_tables = _mapping(
        _runtime_payload_section(result_payload, "core_tables")
        or run_payload.get("core_tables")
        or core_selection.get("core_tables")
        or best_cycle.get("core_tables")
    )
    selected_core_rows = [dict(item) for item in tuple(core_selection.get("selected_core_rows", ())) if isinstance(item, Mapping)]
    seed_genome = [dict(item) for item in tuple(core_selection.get("seed_genome", ())) if isinstance(item, Mapping)]
    selection_strategy = _mapping(core_selection.get("selection_strategy"))
    derived_protocols = {
        "search_driver": row.get("search_driver"),
        "screening_protocol": row.get("screening_protocol"),
        "outer_search_protocol": row.get("outer_search_protocol"),
        "heterogeneous_multi_lane_protocol": row.get("heterogeneous_multi_lane_protocol"),
        "lane_id": row.get("lane_id"),
        "lane_family": row.get("lane_family"),
        "challenger_objective_protocol": row.get("challenger_objective_protocol"),
        "pool_expansion_bias_protocol": row.get("pool_expansion_bias_protocol"),
        "structure_head": row.get("structure_head"),
        "search_input_space": row.get("search_input_space"),
        "pool_expansion_unit": row.get("pool_expansion_unit"),
        "gradient_guidance_mode": row.get("gradient_guidance_mode"),
        "basis_binding_mode": row.get("basis_binding_mode"),
        "escape_policy": row.get("escape_policy"),
        "equivalence_expression_protocol": row.get("equivalence_expression_protocol"),
        "equivalence_expression_mode": row.get("equivalence_expression_mode"),
        "equivalence_class_scope": row.get("equivalence_class_scope"),
        "interference_feature_protocol": row.get("interference_feature_protocol"),
        "interference_feature_mode": row.get("interference_feature_mode"),
        "cross_explanatory_rejection_mode": row.get("cross_explanatory_rejection_mode"),
        "trivial_nonlinearity_penalty_mode": row.get("trivial_nonlinearity_penalty_mode"),
        "environment_invariance_audit_mode": row.get("environment_invariance_audit_mode"),
        "proxy_group_policy": row.get("proxy_group_policy"),
        "source_overlap_penalty_mode": row.get("source_overlap_penalty_mode"),
        "joint_core_score": row.get("joint_core_score"),
        "cross_lane_stability": row.get("cross_lane_stability"),
        "consensus_prior_row_count": row.get("consensus_prior_row_count"),
    }

    metrics = st.columns(4)
    metrics[0].metric("鐘舵€?/ Status", _text(row.get("status")) or "-")
    metrics[1].metric("椹卞姩 / Driver", _text(row.get("driver_ref")) or "-")
    metrics[2].metric("涓绘寚鏍?/ Primary Metric", _metric_text(row.get("primary_metric_value")))
    metrics[3].metric("浜х墿鏁?/ Artifacts", str(len(list(artifact_rows))))
    st.caption(
        f"run_id={_text(row.get('run_id')) or '-'} | surface_key={_text(row.get('surface_key')) or '-'} | assembly_signature={_text(row.get('assembly_signature')) or '-'}"
    )

    if detail_tab == "overview":
        left, right = st.columns(2)
        with left:
            _render_json_block("琛ㄩ潰璁板綍 / Surface Record", surface_record, empty_message="褰撳墠 run 娌℃湁 SurfaceRecord / No SurfaceRecord for the current run.")
            _render_json_block("杩愯鎸囨爣姹囨€?/ Run Metric Summary", run_record.get("metric_summary_json"), empty_message="褰撳墠 run 娌℃湁 metric_summary / No metric_summary for the current run.")
            _render_json_block("鎼滅储鍗忚 / Search Protocols", derived_protocols, empty_message="褰撳墠 run 娌℃湁鍙睍绀虹殑鎼滅储鍗忚鎽樿 / No derived search protocol summary for the current run.")
        with right:
            _render_contract_chips("瑁呴厤鎸傝浇椤哄簭 / Assembly Mount Order", assembly_record.get("mount_order"))
            _render_contract_chips("鍏宠仈浜х墿 / Artifacts", run_record.get("artifact_ids"))
            _render_basis_object_gradient_pool_card(row=row, result_payload=result_payload)
        if _text(row.get("equivalence_expression_protocol")) or _text(row.get("interference_feature_protocol")):
            st.markdown("**Mechanism Guards / 机制护栏**")
            guard_cols = st.columns(4)
            guard_cols[0].metric("Equivalence", _text(row.get("equivalence_expression_protocol")) or "-")
            guard_cols[1].metric("Interference", _text(row.get("interference_feature_protocol")) or "-")
            guard_cols[2].metric("Cross-Explain", _text(row.get("cross_explanatory_rejection_mode")) or "-")
            guard_cols[3].metric("Invariance", _text(row.get("environment_invariance_audit_mode")) or "-")
            _render_json_block(
                "Mechanism Guard Summary / 机制护栏摘要",
                {
                    "equivalence_expression_handling": _runtime_payload_section(
                        result_payload,
                        "equivalence_expression_handling",
                    )
                    or run_payload.get("equivalence_expression_handling"),
                    "interference_feature_handling": _runtime_payload_section(
                        result_payload,
                        "interference_feature_handling",
                    )
                    or run_payload.get("interference_feature_handling"),
                },
                empty_message="No mechanism-guard metadata recorded.",
            )
        if _text(row.get("lane_id")) or _text(row.get("lane_family")) or _text(row.get("challenger_objective_protocol")):
            st.markdown("**Heterogeneous Multi-Lane / 寮傛瀯澶?Lane**")
            lane_cols = st.columns(5)
            lane_cols[0].metric("Lane ID", _text(row.get("lane_id")) or "-")
            lane_cols[1].metric("Lane Family", _text(row.get("lane_family")) or "-")
            lane_cols[2].metric("Joint Core", _metric_text(row.get("joint_core_score")))
            lane_cols[3].metric("Cross-Lane", _metric_text(row.get("cross_lane_stability")))
            lane_cols[4].metric("Prior Rows", str(row.get("consensus_prior_row_count") or "-"))
            _render_json_block(
                "Lane Protocol Summary / Lane 鍗忚鎽樿",
                {
                    "heterogeneous_multi_lane_protocol": row.get("heterogeneous_multi_lane_protocol"),
                    "challenger_objective_protocol": row.get("challenger_objective_protocol"),
                    "pool_expansion_bias_protocol": row.get("pool_expansion_bias_protocol"),
                    "heterogeneous_multi_lane_context": _runtime_payload_section(
                        result_payload,
                        "heterogeneous_multi_lane_context",
                    )
                    or run_payload.get("heterogeneous_multi_lane_context"),
                    "lane_summary": _runtime_payload_section(result_payload, "lane_summary"),
                },
                empty_message="No multi-lane metadata recorded.",
            )
        if isinstance(leaderboards, Mapping):
            st.markdown("**Best RMSE / Best Exact / Best Balanced**")
            st.dataframe(_leaderboards_frame(leaderboards), width="stretch", hide_index=True)
        if core_selection or cycle_rows or evolution_rows:
            st.markdown("**閿佹牳瀹¤ / Core Lock Audit**")
            audit_cols = st.columns(4)
            audit_cols[0].metric("Best Cycle", _text(best_cycle.get("cycle_key")) or "-")
            audit_cols[1].metric("Selected Core Rows", str(len(selected_core_rows) or row.get("selected_core_row_count") or "-"))
            audit_cols[2].metric("Seed Terms", str(len(seed_genome) or row.get("locked_seed_terms") or "-"))
            audit_cols[3].metric("Equivalence", _text(core_selection.get("equivalence_mode")) or "-")
            if selected_core_rows:
                selected_labels = [
                    _text(item.get("representative_seed_name")) or _text(item.get("basis_class_id")) or _text(item.get("representative_expression"))
                    for item in selected_core_rows
                    if _text(item.get("representative_seed_name")) or _text(item.get("basis_class_id")) or _text(item.get("representative_expression"))
                ]
                _render_contract_chips("閿佸畾 Core Basis / Locked Core Basis", selected_labels[:12])
            audit_left, audit_right = st.columns(2)
            with audit_left:
                if selected_core_rows:
                    st.dataframe(_selected_core_rows_frame(selected_core_rows), width="stretch", hide_index=True)
                else:
                    st.caption("褰撳墠 run 杩樻病鏈?selected_core_rows / No selected_core_rows for the current run.")
            with audit_right:
                if core_tables:
                    st.dataframe(_core_table_summary_frame(core_tables), width="stretch", hide_index=True)
                else:
                    st.caption("褰撳墠 run 杩樻病鏈?core_tables / No core_tables for the current run.")
                if selection_strategy:
                    st.dataframe(_selection_strategy_frame(selection_strategy), width="stretch", hide_index=True)
                else:
                    st.caption("褰撳墠 run 杩樻病鏈?selection_strategy / No selection_strategy for the current run.")
        st.markdown("**鍏宠仈浜х墿琛ㄩ潰琛?/ Linked Artifact Surface Rows**")
        if artifact_rows:
            st.dataframe(_artifact_rows_frame(artifact_rows), width="stretch", hide_index=True)
        else:
            st.info("褰撳墠 run 杩樻病鏈夊凡璁板綍鐨?artifact surface / No recorded artifact surface rows for the current run.")
        if cycle_rows:
            st.markdown("**Consensus 鍛ㄦ湡 / Consensus Cycles**")
            st.dataframe(_cycle_reports_frame(cycle_rows), width="stretch", hide_index=True)
        if stage_rows:
            st.markdown("**L2/L3 闃舵 / L2/L3 Stages**")
            st.dataframe(_stage_reports_frame(stage_rows), width="stretch", hide_index=True)
        if evolution_rows:
            st.markdown("**鏍稿績 Basis 婕斿寲 / Core Basis Evolution**")
            st.dataframe(_core_basis_evolution_frame(evolution_rows), width="stretch", hide_index=True)
        return

    if detail_tab == "contracts":
        left, right = st.columns(2)
        with left:
            _render_json_block("琛ㄩ潰璁板綍 / Surface Record", surface_record, empty_message="褰撳墠 run 娌℃湁 SurfaceRecord / No SurfaceRecord for the current run.")
            _render_json_block("瑁呴厤璁板綍 / Assembly Record", assembly_record, empty_message="褰撳墠 run 娌℃湁 AssemblyRecord / No AssemblyRecord for the current run.")
        with right:
            _render_json_block("杩愯璁板綍 / Run Record", run_record, empty_message="褰撳墠 run 娌℃湁 RunRecord / No RunRecord for the current run.")
            _render_json_block("杩愯鎽樿 / Run Summary", run_payload, empty_message="褰撳墠 run 娌℃湁 run summary / No run summary for the current run.")
            _render_json_block("浜х墿璁板綍鍒楄〃 / Artifact Records", artifact_records, empty_message="褰撳墠 run 娌℃湁 ArtifactRecord 鍒楄〃 / No ArtifactRecord list for the current run.")
        return

    if orchestration_report:
        _render_json_block("缂栨帓姹囨€?/ Orchestration Report", orchestration_report, empty_message="褰撳墠 run 娌℃湁 orchestration report / No orchestration report for the current run.")
    if isinstance(leaderboards, Mapping):
        _render_json_block("Leaderboards / 涓夋骞跺垪", leaderboards, empty_message="褰撳墠 run 娌℃湁 leaderboard payload / No leaderboard payload for the current run.")
    if cycle_rows:
        _render_json_block("鍛ㄦ湡鎶ュ憡 / Cycle Reports", cycle_rows, empty_message="褰撳墠 run 娌℃湁 cycle reports / No cycle reports for the current run.")
    if evolution_rows:
        _render_json_block("鏍稿績 Basis 婕斿寲 / Core Basis Evolution", evolution_rows, empty_message="褰撳墠 run 娌℃湁 core basis evolution / No core basis evolution for the current run.")
    _render_json_block("缁撴灉杞借嵎 / Result Payload", result_payload, empty_message="褰撳墠 run 娌℃湁 result payload / No result payload for the current run.")


def _render_artifact_detail(detail_tab: str, row: Mapping[str, Any], linked_run: Mapping[str, Any] | None) -> None:
    artifact_record = row.get("artifact_record_json") if isinstance(row.get("artifact_record_json"), Mapping) else {}
    surface_record = linked_run.get("surface_record_json") if isinstance(linked_run, Mapping) and isinstance(linked_run.get("surface_record_json"), Mapping) else {}
    assembly_record = linked_run.get("assembly_record_json") if isinstance(linked_run, Mapping) and isinstance(linked_run.get("assembly_record_json"), Mapping) else {}
    run_record = linked_run.get("run_record_json") if isinstance(linked_run, Mapping) and isinstance(linked_run.get("run_record_json"), Mapping) else {}

    metrics = st.columns(4)
    metrics[0].metric("Artifact", _text(row.get("artifact_id")) or "-")
    metrics[1].metric("瑙掕壊 / Role", _text(row.get("artifact_role")) or "-")
    metrics[2].metric("鐢熶骇鑰?/ Producer", _text(row.get("producer_ref")) or "-")
    metrics[3].metric("Run", _text(row.get("run_id")) or "-")
    st.caption(f"artifact_id={_text(row.get('artifact_id')) or '-'} | run_id={_text(row.get('run_id')) or '-'} | surface_key={_text(row.get('surface_key')) or '-'}")

    if detail_tab == "overview":
        left, right = st.columns(2)
        with left:
            _render_json_block("浜х墿璁板綍 / Artifact Record", artifact_record, empty_message="褰撳墠 artifact 娌℃湁 ArtifactRecord / No ArtifactRecord for the current artifact.")
        with right:
            _render_json_block("鍏宠仈杩愯鎸囨爣姹囨€?/ Linked Run Metric Summary", (run_record or {}).get("metric_summary_json"), empty_message="鍏宠仈 run 娌℃湁 metric_summary / No metric_summary for the linked run.")
        return

    if detail_tab == "contracts":
        left, right = st.columns(2)
        with left:
            _render_json_block("琛ㄩ潰璁板綍 / Surface Record", surface_record, empty_message="鍏宠仈 run 娌℃湁 SurfaceRecord / No SurfaceRecord for the linked run.")
            _render_json_block("瑁呴厤璁板綍 / Assembly Record", assembly_record, empty_message="鍏宠仈 run 娌℃湁 AssemblyRecord / No AssemblyRecord for the linked run.")
        with right:
            _render_json_block("杩愯璁板綍 / Run Record", run_record, empty_message="鍏宠仈 run 娌℃湁 RunRecord / No RunRecord for the linked run.")
            _render_json_block("浜х墿璁板綍 / Artifact Record", artifact_record, empty_message="褰撳墠 artifact 娌℃湁 ArtifactRecord / No ArtifactRecord for the current artifact.")
        return

    _render_json_block("浜х墿璁板綍 / Artifact Record", artifact_record, empty_message="褰撳墠 artifact 娌℃湁 ArtifactRecord / No ArtifactRecord for the current artifact.")
    _render_json_block("鍏宠仈杩愯杞借嵎 / Linked Run Payload", (linked_run or {}).get("result_json"), empty_message="鍏宠仈 run 娌℃湁 result payload / No result payload for the linked run.")


def _filesystem_rows_frame(rows: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    items: list[dict[str, Any]] = []
    for row in rows:
        items.append(
            {
                "run_id": _text(row.get("run_id")) or "-",
                "solver": _text(row.get("solver_class")) or "-",
                "adapter": _text(row.get("adapter_class")) or "-",
                "plugins": ", ".join(str(item) for item in tuple(row.get("plugin_names") or ())) or "-",
                "last_step": _text(row.get("last_step")) or "-",
                "last_best_score": _text(row.get("last_best_score")) or "-",
                "files": int(row.get("artifact_file_count", 0) or 0),
                "output_dir": _text(row.get("output_dir")) or "-",
            }
        )
    return pd.DataFrame(items)


def _render_filesystem_fallback(*, raw_db_target: str, query_text: str, run_limit: int, attempts: Sequence[Mapping[str, Any]]) -> None:
    rows = discover_filesystem_run_surfaces(query=query_text, limit=max(20, int(run_limit)))
    artifact_root = default_artifact_root()
    primary_attempt = dict(attempts[0]) if attempts else {}
    primary_diag = dict(primary_attempt.get("diagnostic") or {})
    title = str(primary_diag.get("title") or "瀹為獙搴撲笉鍙繛鎺?/ Experiment DB is unavailable")
    detail = str(primary_diag.get("detail") or "褰撳墠瀹為獙搴撲笉鍙敤 / The configured experiment DB is currently unavailable.")
    hint = str(primary_diag.get("hint") or "宸插垏鎹㈠埌鏍囧噯杩愯浜х墿鐨勫彧璇绘壂鎻忚鍥?/ Switched to a read-only scan of standard run artifacts.")

    st.warning(title)
    st.caption(detail)
    st.caption(hint)
    if attempts:
        with st.expander("鏁版嵁搴撳皾璇曡褰?/ DB Attempt Log", expanded=False):
            for index, item in enumerate(attempts, start=1):
                diag = dict(item.get("diagnostic") or {})
                st.markdown(f"**{index}. {diag.get('safe_target') or item.get('target') or '-'}**")
                st.caption(str(diag.get("detail") or "-"))
                raw_message = str(diag.get("raw_message") or "").strip()
                if raw_message:
                    st.code(raw_message)

    _page.render_stat_cards(
        st,
        (
            _page.StatCardSpec("褰撳墠鏉ユ簮 / Source", "filesystem fallback", "read-only standard artifact scan"),
            _page.StatCardSpec("鍙戠幇杩愯 / Runs", str(len(rows)), "grouped from standard files"),
            _page.StatCardSpec("浜х墿鏍圭洰褰?/ Artifact Root", str(artifact_root), "runs/ standard outputs"),
            _page.StatCardSpec("璇锋眰鐩爣 / Requested DB", _text(raw_db_target) or "-", "database unavailable"),
        ),
    )
    _page.render_section_header(
        st,
        _page.SectionHeaderSpec(
            section_id=_page.RESULT_SECTION_ID,
            label="RESULTS",
            title="鏈湴鏍囧噯浜х墿鍥為€€瑙嗗浘 / Local Standard Artifact Fallback",
            subtitle="褰?PostgreSQL / SQLite runtime surface 鏆傛椂涓嶅彲鐢ㄦ椂锛岄〉闈細鍙鎵弿 runs/ 涓嬬殑鏍囧噯浜х墿鏂囦欢锛屽敖閲忔仮澶?run 绾ф祻瑙堣兘鍔涖€?/ When the runtime surface DB is unavailable, the page falls back to a read-only scan of standard run artifact files under runs/.",
            note=f"鍛戒腑 {len(rows)} 鏉?/ {len(rows)} rows",
        ),
    )
    if not rows:
        st.info("褰撳墠娌℃湁鍙壂鎻忕殑鏍囧噯杩愯浜х墿鏂囦欢 / No standard run artifact files were found under runs/.")
        return

    row_by_key = {str(row.get("selection_key")): dict(row) for row in rows}
    option_keys = [str(row.get("selection_key")) for row in rows if _text(row.get("selection_key"))]
    current_key = _text(st.session_state.get("experiment_ui_selected"))
    if current_key not in row_by_key:
        current_key = option_keys[0]
        st.session_state["experiment_ui_selected"] = current_key
    selected_key = st.selectbox(
        "鏈湴杩愯 / Local Run",
        options=option_keys,
        index=option_keys.index(current_key),
        format_func=lambda key: _text(row_by_key.get(str(key), {}).get("run_id")) or str(key),
        key="experiment_ui_filesystem_selected",
    )
    st.session_state["experiment_ui_selected"] = str(selected_key)
    st.dataframe(_filesystem_rows_frame(rows), width="stretch", hide_index=True)
    selected_row = row_by_key.get(str(selected_key), row_by_key[option_keys[0]])

    _page.render_section_header(
        st,
        _page.SectionHeaderSpec(
            section_id=_page.DETAIL_SECTION_ID,
            label="DETAIL",
            title="鏈湴浜х墿璇︽儏 / Local Artifact Detail",
            subtitle="杩欓噷灞曠ず浠?modules.json / bias.json / repro_bundle.json / progress.csv 绛夋爣鍑嗘枃浠舵仮澶嶅嚭鐨勮繍琛屼笂涓嬫枃銆?/ This panel reconstructs run context from standard files such as modules.json, bias.json, repro_bundle.json, and progress.csv.",
            note="filesystem fallback",
        ),
    )
    metrics = st.columns(4)
    metrics[0].metric("Run", _text(selected_row.get("run_id")) or "-")
    metrics[1].metric("Solver", _text(selected_row.get("solver_class")) or "-")
    metrics[2].metric("Adapter", _text(selected_row.get("adapter_class")) or "-")
    metrics[3].metric("浜х墿鏂囦欢鏁?/ Files", str(int(selected_row.get("artifact_file_count", 0) or 0)))
    _render_contract_chips("缁勪欢鎽樿 / Component Summary", selected_row.get("component_summary"))
    _render_contract_chips("鎻掍欢娓呭崟 / Plugins", selected_row.get("plugin_names"))
    left, right = st.columns(2)
    with left:
        _render_json_block("妯″潡鎶ュ憡 / Module Report", selected_row.get("modules_payload"), empty_message="褰撳墠 run 娌℃湁 modules.json / No modules.json was found for the current run.")
        _render_json_block("鍋忕疆鎶ュ憡 / Bias Report", selected_row.get("bias_payload"), empty_message="褰撳墠 run 娌℃湁 bias.json / No bias.json was found for the current run.")
    with right:
        _render_json_block("杩愯鎽樿 / Summary", selected_row.get("summary_payload"), empty_message="褰撳墠 run 娌℃湁 summary.json / No summary.json was found for the current run.")
        _render_json_block("Repro Bundle", selected_row.get("repro_bundle_payload"), empty_message="褰撳墠 run 娌℃湁 repro_bundle.json / No repro_bundle.json was found for the current run.")
    _render_json_block(
        "Progress Tail / 进度尾部记录",
        selected_row.get("progress_tail"),
        empty_message="当前 run 没有可解析的 progress.csv 尾部记录 / No readable progress tail was found in progress.csv for the current run.",
    )


def _summary_loader(db_path: str) -> dict[str, Any]:
    return runtime_surface_summary(db_path)


def _filter_values_loader(db_path: str) -> dict[str, list[str]]:
    return runtime_surface_filter_values(db_path)


def _run_rows_loader(
    db_path: str,
    query: str,
    status: str | None,
    surface_key: str | None,
    driver_ref: str | None,
    family_ref: str | None,
    assembly_signature: str | None,
    screening_protocol: str | None,
    outer_search_protocol: str | None,
    structure_head: str | None,
    search_input_space: str | None,
    pool_expansion_unit: str | None,
    gradient_guidance_mode: str | None,
    basis_binding_mode: str | None,
    escape_policy: str | None,
    equivalence_expression_protocol: str | None,
    equivalence_expression_mode: str | None,
    interference_feature_protocol: str | None,
    interference_feature_mode: str | None,
    cross_explanatory_rejection_mode: str | None,
    trivial_nonlinearity_penalty_mode: str | None,
    environment_invariance_audit_mode: str | None,
    lane_id: str | None,
    lane_family: str | None,
    challenger_objective_protocol: str | None,
    pool_expansion_bias_protocol: str | None,
    joint_core_score_min: float | None,
    cross_lane_stability_min: float | None,
    limit: int,
) -> list[dict[str, Any]]:
    rows = list_runtime_run_surfaces(
        db_path,
        status=status,
        surface_key=surface_key,
        driver_ref=driver_ref,
        family_ref=family_ref,
        assembly_signature=assembly_signature,
        screening_protocol=screening_protocol,
        outer_search_protocol=outer_search_protocol,
        structure_head=structure_head,
        search_input_space=search_input_space,
        pool_expansion_unit=pool_expansion_unit,
        gradient_guidance_mode=gradient_guidance_mode,
        basis_binding_mode=basis_binding_mode,
        escape_policy=escape_policy,
        equivalence_expression_protocol=equivalence_expression_protocol,
        equivalence_expression_mode=equivalence_expression_mode,
        interference_feature_protocol=interference_feature_protocol,
        interference_feature_mode=interference_feature_mode,
        cross_explanatory_rejection_mode=cross_explanatory_rejection_mode,
        trivial_nonlinearity_penalty_mode=trivial_nonlinearity_penalty_mode,
        environment_invariance_audit_mode=environment_invariance_audit_mode,
        lane_id=lane_id,
        lane_family=lane_family,
        challenger_objective_protocol=challenger_objective_protocol,
        pool_expansion_bias_protocol=pool_expansion_bias_protocol,
        joint_core_score_min=joint_core_score_min,
        cross_lane_stability_min=cross_lane_stability_min,
        limit=limit,
    )
    return [dict(row) for row in rows if _query_match(row, query, kind="run")]


def _artifact_rows_loader(
    db_path: str,
    query: str,
    artifact_role: str | None,
    producer_ref: str | None,
    surface_key: str | None,
    assembly_signature: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    rows = list_runtime_artifact_surfaces(
        db_path,
        artifact_role=artifact_role,
        producer_ref=producer_ref,
        surface_key=surface_key,
        assembly_signature=assembly_signature,
        limit=limit,
    )
    return [dict(row) for row in rows if _query_match(row, query, kind="artifact")]


def _show_run_loader(db_path: str, run_id: str) -> dict[str, Any] | None:
    return show_runtime_run_surface(db_path, run_id=run_id)


def _show_artifact_loader(db_path: str, run_id: str, artifact_id: str) -> dict[str, Any] | None:
    return show_runtime_artifact_surface(db_path, run_id=run_id, artifact_id=artifact_id)


_load_summary_cached = _shell.memoize_loader(_summary_loader, maxsize=16)
_load_filter_values_cached = _shell.memoize_loader(_filter_values_loader, maxsize=16)
_load_run_rows_cached = _shell.memoize_loader(_run_rows_loader, maxsize=64)
_load_artifact_rows_cached = _shell.memoize_loader(_artifact_rows_loader, maxsize=64)
_show_run_cached = _shell.memoize_loader(_show_run_loader, maxsize=128)
_show_artifact_cached = _shell.memoize_loader(_show_artifact_loader, maxsize=128)


def _resolve_runtime_source(raw_db_target: str) -> tuple[str | None, Any, Any, list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    for candidate in experiment_db_candidate_targets(raw_db_target):
        try:
            summary = _load_summary_cached(str(candidate))
            filter_values = _load_filter_values_cached(str(candidate))
            return str(candidate), summary, filter_values, attempts
        except Exception as exc:
            attempts.append(
                {
                    "target": str(candidate),
                    "target_info": normalize_experiment_db_target(candidate),
                    "diagnostic": summarize_experiment_db_error(exc, target=candidate),
                }
            )
    return None, None, None, attempts


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="nsgablack experiment dashboard")
    default_info = experiment_db_config_info()
    parser.add_argument(
        "--db",
        type=str,
        default=str(default_info.get("db_target") or resolve_experiment_db_target()),
        help="Experiment DB target. Accepts a sqlite path or postgresql://... URL. Defaults to experiment/db.toml, env, catalog fallback, then local sqlite.",
    )
    parser.add_argument("--limit", type=int, default=500, help="Max rows to query per view")
    parser.add_argument("--column-mode", type=str, default=_shared.DEFAULT_COLUMN_MODE, help="Initial result table column mode")
    parser.add_argument("--page-size", type=int, default=_shared.DEFAULT_PAGE_SIZE, help="Initial visible result window")
    parser.add_argument("--results-collapse", type=str, default=_shared.DEFAULT_RESULTS_COLLAPSE, help="Initial results expander state")
    return parser.parse_known_args(argv)[0]


def run_dashboard(argv: Sequence[str] | None = None) -> None:
    args = _parse_args(argv)
    _set_page_config()
    _inject_style()
    _page.render_top_anchor(st)

    query_params, query_filters = _read_query_params(st)
    view_mode = _sync_session_state_from_query(args, query_params, query_filters)

    _page.render_hero(
        st,
        _page.HeroSpec(
            icon_text="NS",
            kicker="nsgablack experiment",
            title="杩愯琛ㄩ潰涓庝骇鐗╄〃闈?/ Run & Artifact Surface",
            subtitle="浼樺厛璇诲彇 runtime_run_surface / runtime_artifact_surface锛涙暟鎹簱涓嶅彲鐢ㄦ椂鑷姩鍥為€€鍒版湰鍦版爣鍑嗕骇鐗╂枃浠躲€?/ The dashboard prefers runtime_run_surface / runtime_artifact_surface and can fall back to local standard artifact files when the database is unavailable.",
        ),
    )

    _page.render_section_header(
        st,
        _page.SectionHeaderSpec(
            section_id=_page.FILTER_SECTION_ID,
            label="FILTER",
            title="鏁版嵁婧愩€佹煡璇笌瑙嗗浘鐘舵€?/ Source, Query & View State",
            subtitle="椤堕儴缁熶竴鎵挎帴鏁版嵁搴撶洰鏍囥€佹悳绱€佸竷灞€鍜岃鎯呴〉绛撅紱褰撲富鏁版嵁搴撲笉鍙敤鏃讹紝椤甸潰浼氱户缁皾璇?SQLite 鎴栨湰鍦版爣鍑嗕骇鐗╁洖閫€銆?/ The top controls own the database target, query, layout, and detail-tab state; when the primary DB is unavailable, the page continues with SQLite or local standard-artifact fallback when possible.",
        ),
    )

    top_cols = st.columns((1.7, 1.0, 0.8, 0.6))
    raw_db_target = top_cols[0].text_input("Experiment Source / 实验数据源", key="experiment_ui_db")
    query_text = top_cols[1].text_input("Query / 关键词", key="experiment_ui_query")
    view_mode = top_cols[2].selectbox(
        "View / 瑙嗗浘",
        options=_VIEW_OPTIONS,
        index=_VIEW_OPTIONS.index(_normalize_view_mode(st.session_state.get("experiment_ui_view"))),
        format_func=lambda value: _VIEW_LABELS.get(str(value), str(value)),
        key="experiment_ui_view",
    )
    run_limit = int(top_cols[3].number_input("Limit / 鏌ヨ涓婇檺", min_value=10, max_value=5000, step=10, key="experiment_ui_limit"))

    detail_tab_key = _view_state_key(view_mode, "detail_tab")
    column_mode_key = _view_state_key(view_mode, "column_mode")
    page_size_key = _view_state_key(view_mode, "page_size")
    results_collapse_key = _view_state_key(view_mode, "results_collapse")
    st.session_state.setdefault(detail_tab_key, _normalize_detail_tab(query_params.get("detail_tab")))
    st.session_state.setdefault(column_mode_key, _normalize_column_mode(query_params.get("column_mode") or args.column_mode))
    st.session_state.setdefault(page_size_key, _normalize_page_size(query_params.get("page_size") or args.page_size))
    st.session_state.setdefault(results_collapse_key, _normalize_results_collapse(query_params.get("results_collapse") or args.results_collapse))

    secondary_cols = st.columns((0.8, 0.7, 0.7, 0.8))
    column_mode = secondary_cols[0].selectbox("Column Mode / 列显示方式", options=_COLUMN_MODE_OPTIONS, index=_COLUMN_MODE_OPTIONS.index(_normalize_column_mode(st.session_state.get(column_mode_key))), format_func=lambda value: _COLUMN_MODE_LABELS.get(str(value), str(value)), key=column_mode_key)
    page_size = secondary_cols[1].selectbox("Page Size / 姣忛〉鏉℃暟", options=_PAGE_SIZE_OPTIONS, index=_PAGE_SIZE_OPTIONS.index(_normalize_page_size(st.session_state.get(page_size_key))), format_func=lambda value: f"{int(value)} rows", key=page_size_key)
    results_collapse = secondary_cols[2].selectbox("Results / 缁撴灉鎶樺彔", options=_RESULTS_COLLAPSE_OPTIONS, index=_RESULTS_COLLAPSE_OPTIONS.index(_normalize_results_collapse(st.session_state.get(results_collapse_key))), format_func=lambda value: _RESULTS_COLLAPSE_LABELS.get(str(value), str(value)), key=results_collapse_key)
    detail_tab = secondary_cols[3].selectbox("Detail Tab / 璇︽儏椤电", options=_DETAIL_TABS, index=_DETAIL_TABS.index(_normalize_detail_tab(st.session_state.get(detail_tab_key))), format_func=lambda value: _DETAIL_TAB_LABELS.get(str(value), str(value)), key=detail_tab_key)

    db_path, summary, filter_values, failed_attempts = _resolve_runtime_source(raw_db_target)
    if db_path is None:
        _render_filesystem_fallback(raw_db_target=raw_db_target, query_text=_text(query_text), run_limit=int(run_limit), attempts=failed_attempts)
        return

    db_target_info = normalize_experiment_db_target(db_path)
    if failed_attempts:
        primary_diag = dict(failed_attempts[0].get("diagnostic") or {})
        st.warning("鏁版嵁搴撲富鐩爣涓嶅彲鐢紝宸茶嚜鍔ㄥ洖閫€鍒板彲璇诲彇鐨勬暟鎹簮 / The primary experiment DB target is unavailable; the dashboard fell back to a readable source.")
        st.caption(str(primary_diag.get("detail") or ""))
        st.caption(f"褰撳墠浣跨敤 / Active source: {db_target_info.safe_label}")

    _page.render_stat_cards(
        st,
        (
            _page.StatCardSpec("褰撳墠瑙嗗浘 / View", _VIEW_LABELS.get(view_mode, view_mode), "run / artifact dual view"),
            _page.StatCardSpec("杩愯鏁?/ Runs", str(summary.get("tables", {}).get("runtime_run_surface", 0)), "runtime_run_surface"),
            _page.StatCardSpec("浜х墿鏁?/ Artifacts", str(summary.get("tables", {}).get("runtime_artifact_surface", 0)), "runtime_artifact_surface"),
            _page.StatCardSpec("DB", db_target_info.safe_label, str(summary.get("backend") or db_target_info.backend)),
        ),
    )

    for field_name in _FILTER_FIELDS_BY_VIEW.get(view_mode, ()):
        st.session_state.setdefault(_facet_state_key(view_mode, field_name), "")

    if view_mode == "run_catalog":
        filter_cols = st.columns(5)
        status_filter = filter_cols[0].selectbox("鐘舵€?/ Status", options=[""] + list(filter_values.get("run_status", [])), index=0, format_func=_optional_choice_label, key=_facet_state_key(view_mode, "run_status"))
        surface_key_filter = filter_cols[1].selectbox("surface_key", options=[""] + list(filter_values.get("run_surface_key", [])), index=0, format_func=_optional_choice_label, key=_facet_state_key(view_mode, "run_surface_key"))
        driver_ref_filter = filter_cols[2].selectbox("driver_ref", options=[""] + list(filter_values.get("run_driver_ref", [])), index=0, format_func=_optional_choice_label, key=_facet_state_key(view_mode, "run_driver_ref"))
        family_ref_filter = filter_cols[3].selectbox("family_ref", options=[""] + list(filter_values.get("run_family_ref", [])), index=0, format_func=_optional_choice_label, key=_facet_state_key(view_mode, "run_family_ref"))
        assembly_signature_filter = filter_cols[4].selectbox("assembly_signature", options=[""] + list(filter_values.get("run_assembly_signature", [])), index=0, format_func=_optional_choice_label, key=_facet_state_key(view_mode, "run_assembly_signature"))
        protocol_cols = st.columns(4)
        screening_protocol_filter = protocol_cols[0].selectbox("screening_protocol", options=[""] + list(filter_values.get("run_screening_protocol", [])), index=0, format_func=_optional_choice_label, key=_facet_state_key(view_mode, "run_screening_protocol"))
        outer_search_protocol_filter = protocol_cols[1].selectbox("outer_search_protocol", options=[""] + list(filter_values.get("run_outer_search_protocol", [])), index=0, format_func=_optional_choice_label, key=_facet_state_key(view_mode, "run_outer_search_protocol"))
        structure_head_filter = protocol_cols[2].selectbox("structure_head", options=[""] + list(filter_values.get("run_structure_head", [])), index=0, format_func=_optional_choice_label, key=_facet_state_key(view_mode, "run_structure_head"))
        search_input_space_filter = protocol_cols[3].selectbox("search_input_space", options=[""] + list(filter_values.get("run_search_input_space", [])), index=0, format_func=_optional_choice_label, key=_facet_state_key(view_mode, "run_search_input_space"))
        protocol_cols_2 = st.columns(4)
        pool_expansion_unit_filter = protocol_cols_2[0].selectbox("pool_expansion_unit", options=[""] + list(filter_values.get("run_pool_expansion_unit", [])), index=0, format_func=_optional_choice_label, key=_facet_state_key(view_mode, "run_pool_expansion_unit"))
        gradient_guidance_mode_filter = protocol_cols_2[1].selectbox("gradient_guidance_mode", options=[""] + list(filter_values.get("run_gradient_guidance_mode", [])), index=0, format_func=_optional_choice_label, key=_facet_state_key(view_mode, "run_gradient_guidance_mode"))
        basis_binding_mode_filter = protocol_cols_2[2].selectbox("basis_binding_mode", options=[""] + list(filter_values.get("run_basis_binding_mode", [])), index=0, format_func=_optional_choice_label, key=_facet_state_key(view_mode, "run_basis_binding_mode"))
        escape_policy_filter = protocol_cols_2[3].selectbox("escape_policy", options=[""] + list(filter_values.get("run_escape_policy", [])), index=0, format_func=_optional_choice_label, key=_facet_state_key(view_mode, "run_escape_policy"))
        mechanism_cols = st.columns(4)
        equivalence_expression_protocol_filter = mechanism_cols[0].selectbox("equivalence_expression_protocol", options=[""] + list(filter_values.get("run_equivalence_expression_protocol", [])), index=0, format_func=_optional_choice_label, key=_facet_state_key(view_mode, "run_equivalence_expression_protocol"))
        equivalence_expression_mode_filter = mechanism_cols[1].selectbox("equivalence_expression_mode", options=[""] + list(filter_values.get("run_equivalence_expression_mode", [])), index=0, format_func=_optional_choice_label, key=_facet_state_key(view_mode, "run_equivalence_expression_mode"))
        interference_feature_protocol_filter = mechanism_cols[2].selectbox("interference_feature_protocol", options=[""] + list(filter_values.get("run_interference_feature_protocol", [])), index=0, format_func=_optional_choice_label, key=_facet_state_key(view_mode, "run_interference_feature_protocol"))
        interference_feature_mode_filter = mechanism_cols[3].selectbox("interference_feature_mode", options=[""] + list(filter_values.get("run_interference_feature_mode", [])), index=0, format_func=_optional_choice_label, key=_facet_state_key(view_mode, "run_interference_feature_mode"))
        mechanism_cols_2 = st.columns(3)
        cross_explanatory_rejection_mode_filter = mechanism_cols_2[0].selectbox("cross_explanatory_rejection_mode", options=[""] + list(filter_values.get("run_cross_explanatory_rejection_mode", [])), index=0, format_func=_optional_choice_label, key=_facet_state_key(view_mode, "run_cross_explanatory_rejection_mode"))
        trivial_nonlinearity_penalty_mode_filter = mechanism_cols_2[1].selectbox("trivial_nonlinearity_penalty_mode", options=[""] + list(filter_values.get("run_trivial_nonlinearity_penalty_mode", [])), index=0, format_func=_optional_choice_label, key=_facet_state_key(view_mode, "run_trivial_nonlinearity_penalty_mode"))
        environment_invariance_audit_mode_filter = mechanism_cols_2[2].selectbox("environment_invariance_audit_mode", options=[""] + list(filter_values.get("run_environment_invariance_audit_mode", [])), index=0, format_func=_optional_choice_label, key=_facet_state_key(view_mode, "run_environment_invariance_audit_mode"))
        lane_cols = st.columns(4)
        lane_id_filter = lane_cols[0].selectbox("lane_id", options=[""] + list(filter_values.get("run_lane_id", [])), index=0, format_func=_optional_choice_label, key=_facet_state_key(view_mode, "run_lane_id"))
        lane_family_filter = lane_cols[1].selectbox("lane_family", options=[""] + list(filter_values.get("run_lane_family", [])), index=0, format_func=_optional_choice_label, key=_facet_state_key(view_mode, "run_lane_family"))
        challenger_objective_protocol_filter = lane_cols[2].selectbox("challenger_objective_protocol", options=[""] + list(filter_values.get("run_challenger_objective_protocol", [])), index=0, format_func=_optional_choice_label, key=_facet_state_key(view_mode, "run_challenger_objective_protocol"))
        pool_expansion_bias_protocol_filter = lane_cols[3].selectbox("pool_expansion_bias_protocol", options=[""] + list(filter_values.get("run_pool_expansion_bias_protocol", [])), index=0, format_func=_optional_choice_label, key=_facet_state_key(view_mode, "run_pool_expansion_bias_protocol"))
        numeric_cols = st.columns(2)
        joint_core_score_filter = numeric_cols[0].text_input("joint_core_score_min", key=_facet_state_key(view_mode, "run_joint_core_score_min"), help="按选定 core rows 的最小 joint_core_score 做下限筛选 / Filter by the minimum selected-core joint_core_score.")
        cross_lane_stability_filter = numeric_cols[1].text_input("cross_lane_stability_min", key=_facet_state_key(view_mode, "run_cross_lane_stability_min"), help="按 cross-lane stability 下限筛选 / Filter by the minimum cross-lane stability.")
        rows = _load_run_rows_cached(str(db_path), _text(query_text), _text(status_filter) or None, _text(surface_key_filter) or None, _text(driver_ref_filter) or None, _text(family_ref_filter) or None, _text(assembly_signature_filter) or None, _text(screening_protocol_filter) or None, _text(outer_search_protocol_filter) or None, _text(structure_head_filter) or None, _text(search_input_space_filter) or None, _text(pool_expansion_unit_filter) or None, _text(gradient_guidance_mode_filter) or None, _text(basis_binding_mode_filter) or None, _text(escape_policy_filter) or None, _text(equivalence_expression_protocol_filter) or None, _text(equivalence_expression_mode_filter) or None, _text(interference_feature_protocol_filter) or None, _text(interference_feature_mode_filter) or None, _text(cross_explanatory_rejection_mode_filter) or None, _text(trivial_nonlinearity_penalty_mode_filter) or None, _text(environment_invariance_audit_mode_filter) or None, _text(lane_id_filter) or None, _text(lane_family_filter) or None, _text(challenger_objective_protocol_filter) or None, _text(pool_expansion_bias_protocol_filter) or None, _optional_float(joint_core_score_filter), _optional_float(cross_lane_stability_filter), int(run_limit))
        rows = [{**dict(row), "selection_key": _selection_run_key(_text(row.get("run_id")))} for row in rows if _text(row.get("run_id"))]
    else:
        filter_cols = st.columns(4)
        artifact_role_filter = filter_cols[0].selectbox("artifact_role", options=[""] + list(filter_values.get("artifact_role", [])), index=0, format_func=_optional_choice_label, key=_facet_state_key(view_mode, "artifact_role"))
        producer_ref_filter = filter_cols[1].selectbox("producer_ref", options=[""] + list(filter_values.get("artifact_producer_ref", [])), index=0, format_func=_optional_choice_label, key=_facet_state_key(view_mode, "artifact_producer_ref"))
        surface_key_filter = filter_cols[2].selectbox("surface_key", options=[""] + list(filter_values.get("artifact_surface_key", [])), index=0, format_func=_optional_choice_label, key=_facet_state_key(view_mode, "artifact_surface_key"))
        assembly_signature_filter = filter_cols[3].selectbox("assembly_signature", options=[""] + list(filter_values.get("artifact_assembly_signature", [])), index=0, format_func=_optional_choice_label, key=_facet_state_key(view_mode, "artifact_assembly_signature"))
        rows = _load_artifact_rows_cached(str(db_path), _text(query_text), _text(artifact_role_filter) or None, _text(producer_ref_filter) or None, _text(surface_key_filter) or None, _text(assembly_signature_filter) or None, int(run_limit))
        rows = [{**dict(row), "selection_key": _selection_artifact_key(_text(row.get("run_id")), _text(row.get("artifact_id")))} for row in rows if _text(row.get("run_id")) and _text(row.get("artifact_id"))]

    selected_key = _text(st.session_state.get("experiment_ui_selected"))
    row_by_key = {str(row.get("selection_key")): row for row in rows}
    if rows and selected_key not in row_by_key:
        selected_key = _text(rows[0].get("selection_key"))
        st.session_state["experiment_ui_selected"] = selected_key

    _page.render_section_header(
        st,
        _page.SectionHeaderSpec(
            section_id=_page.RESULT_SECTION_ID,
            label="RESULTS",
            title=f"鍙偣鍑荤粨鏋滆〃 / Clickable Result Table 路 {_VIEW_LABELS.get(view_mode, view_mode)}",
            subtitle="涓棿缁撴灉鍖烘敮鎸佸崟鍑昏鍒囨崲閫変腑椤癸紱Deep-link 浼氳浣忓綋鍓嶇瓫閫夈€侀€変腑椤瑰拰缁撴灉琛ㄦ牸鐘舵€併€?/ Click a row in the middle result table to switch selection; the deep-link restores filters, selection, and result-table state.",
            note=f"鍛戒腑 {len(rows)} 鏉?/ {len(rows)} rows",
        ),
    )

    if rows:
        selected_key = _render_selection_hook(rows=rows, view_mode=view_mode, selected_key=selected_key)
        st.session_state["experiment_ui_selected"] = selected_key
    selection = _selection_state(_text(st.session_state.get("experiment_ui_selected")), rows)
    _render_selection_float(selection=selection, rows=rows, view_mode=view_mode)
    if selection.get("hidden"):
        st.markdown("<div class='catalog-warning'>褰撳墠閫変腑椤逛粛淇濈暀鍦ㄥ彸渚ц鎯呴噷锛屼絾瀹冨凡缁忎笉鍦ㄤ腑闂寸粨鏋滆〃鏍间腑銆備綘鍙互娓呯┖鎼滅储鎴栫瓫閫夛紝璁╁畠閲嶆柊鍑虹幇銆?/div>", unsafe_allow_html=True)

    with st.expander(f"缁撴灉琛ㄦ牸 / Result Table ({min(len(rows), int(page_size))} / {len(rows)})", expanded=bool(results_collapse == "expanded")):
        table_selected = _render_results_table(
            rows=rows,
            view_mode=view_mode,
            column_mode=column_mode,
            page_size=int(page_size),
            selected_key=_text(st.session_state.get("experiment_ui_selected")),
        ) if rows else ""
    if table_selected:
        selected_key = table_selected
        st.session_state["experiment_ui_selected"] = selected_key
    selection = _selection_state(_text(st.session_state.get("experiment_ui_selected")), rows)

    field_filters = {
        field_name: _text(st.session_state.get(_facet_state_key(view_mode, field_name)))
        for field_name in _FILTER_FIELDS_BY_VIEW.get(view_mode, ())
        if _text(st.session_state.get(_facet_state_key(view_mode, field_name)))
    }
    base_params = {
        "db": str(db_path),
        "limit": str(int(run_limit)),
        "view": view_mode,
        "selected": _text(st.session_state.get("experiment_ui_selected")),
        "detail_tab": detail_tab,
        "column_mode": column_mode,
        "page_size": str(int(page_size)),
        "results_collapse": results_collapse,
        "query": _text(query_text),
    }
    _write_query_params(base_params=base_params, field_filters=field_filters)
    _render_selection_nav_links(rows=rows, selection=selection, base_params=base_params, field_filters=field_filters)
    st.text_input(_DEEPLINK_LABEL, value=_build_deep_link_query(base_params=base_params, field_filters=field_filters), key=f"experiment_ui_deeplink::{view_mode}")

    _page.render_section_header(
        st,
        _page.SectionHeaderSpec(
            section_id=_page.DETAIL_SECTION_ID,
            label="DETAIL",
            title="璇︽儏銆佸悎鍚屼笌杞借嵎 / Detail, Contracts & Payload",
            subtitle="鍙充晶缁熶竴鎵挎帴杩愯璇︽儏銆佸悎鍚屽眰涓庡師濮嬭浇鑽凤紝渚夸簬澶嶇幇銆佹瘮瀵瑰拰鍥炴斁銆?/ The right side consolidates runtime detail, contract layers, and payloads for replay, comparison, and audit.",
            note=_DETAIL_TAB_LABELS.get(detail_tab, detail_tab),
        ),
    )

    selected_payload = _decode_selection_key(_text(st.session_state.get("experiment_ui_selected")))
    if view_mode == "run_catalog":
        selected_run_id = ""
        if selected_payload and selected_payload.get("kind") == "run":
            selected_run_id = str(selected_payload.get("run_id") or "")
        selected_run_detail = _show_run_cached(str(db_path), selected_run_id) if selected_run_id else None
        artifact_rows = list_runtime_artifact_surfaces(str(db_path), run_id=selected_run_id, limit=200) if selected_run_id else []
        if not selected_run_detail:
            st.info("褰撳墠杩樻病鏈夊彲灞曠ず鐨?run 璇︽儏 / No run detail is available for the current selection.")
        else:
            _render_run_detail(detail_tab, selected_run_detail, artifact_rows)
    else:
        selected_run_id = ""
        selected_artifact_id = ""
        if selected_payload and selected_payload.get("kind") == "artifact":
            selected_run_id = str(selected_payload.get("run_id") or "")
            selected_artifact_id = str(selected_payload.get("artifact_id") or "")
        selected_artifact_detail = _show_artifact_cached(str(db_path), selected_run_id, selected_artifact_id) if selected_run_id and selected_artifact_id else None
        linked_run = _show_run_cached(str(db_path), selected_run_id) if selected_run_id else None
        if not selected_artifact_detail:
            st.info("褰撳墠杩樻病鏈夊彲灞曠ず鐨?artifact 璇︽儏 / No artifact detail is available for the current selection.")
        else:
            _render_artifact_detail(detail_tab, selected_artifact_detail, linked_run)


def main(argv: Sequence[str] | None = None) -> None:
    run_dashboard(argv)


if __name__ == "__main__":
    main(sys.argv[1:])
