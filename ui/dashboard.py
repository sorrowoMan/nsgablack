from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    _ROOT = Path(__file__).resolve().parents[1]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    from nsgablack.catalog import dashboard as catalog_dashboard
    from nsgablack.catalog import dashboard_page as _page
    from nsgablack.catalog import dashboard_shared as _shared
    from nsgablack.experiment import dashboard as experiment_dashboard
    from nsgablack.experiment.db import experiment_db_config_info
else:
    from ..catalog import dashboard as catalog_dashboard
    from ..catalog import dashboard_page as _page
    from ..catalog import dashboard_shared as _shared
    from ..experiment import dashboard as experiment_dashboard
    from ..experiment.db import experiment_db_config_info

try:
    import streamlit as st
except Exception as exc:  # pragma: no cover
    raise SystemExit(
        "streamlit is required for the nsgablack unified UI. Install with: python -m pip install streamlit"
    ) from exc


_SURFACE_OPTIONS: tuple[str, ...] = ("home", "catalog", "experiment")
_SURFACE_LABELS: dict[str, str] = {
    "home": "首页 / Home",
    "catalog": "框架目录 / Catalog",
    "experiment": "运行实验 / Experiment",
}
_SURFACE_STATE_KEY = "nsgablack_ui_surface"
_SURFACE_WIDGET_KEY = "nsgablack_ui_surface_widget"
_SHELL_QUERY_KEYS: tuple[str, ...] = ("surface",)
_CATALOG_MARKER_KEYS: tuple[str, ...] = (
    "profile",
    "scope",
    "kind",
    "field",
    "project_path",
    "include_global",
    "db_path",
    "source_mode",
    "sort_by",
    "sort_dir",
    "nav_action",
)
_EXPERIMENT_MARKER_KEYS: tuple[str, ...] = (
    "db",
    "view",
)


def dashboard_script_path() -> Path:
    return Path(__file__).resolve()


def build_streamlit_command(
    *,
    surface: str = "home",
    profile: str = "framework-core",
    scope: str = "framework",
    kind: str = "all",
    query: str = "",
    field: str = "all",
    project_path: str | None = None,
    include_global: bool = False,
    db_path: str | None = None,
    source_mode: str | None = None,
    experiment_db: str | None = None,
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
            "--surface",
            str(surface),
            "--profile",
            str(profile),
            "--scope",
            str(scope),
            "--kind",
            str(kind),
            "--field",
            str(field),
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
    if query:
        command.extend(["--query", str(query)])
    if project_path:
        command.extend(["--project-path", str(project_path)])
    if include_global:
        command.append("--include-global")
    if db_path:
        command.extend(["--db-path", str(db_path)])
    if source_mode:
        command.extend(["--source-mode", str(source_mode)])
    if experiment_db:
        command.extend(["--experiment-db", str(experiment_db)])
    return command


def launch_ui_dashboard(
    *,
    surface: str = "home",
    profile: str = "framework-core",
    scope: str = "framework",
    kind: str = "all",
    query: str = "",
    field: str = "all",
    project_path: str | None = None,
    include_global: bool = False,
    db_path: str | None = None,
    source_mode: str | None = None,
    experiment_db: str | None = None,
    limit: int = 500,
    column_mode: str = _shared.DEFAULT_COLUMN_MODE,
    page_size: int = _shared.DEFAULT_PAGE_SIZE,
    results_collapse: str = _shared.DEFAULT_RESULTS_COLLAPSE,
    host: str | None = None,
    port: int | None = None,
    headless: bool = False,
) -> int:
    return int(
        subprocess.call(
            build_streamlit_command(
                surface=surface,
                profile=profile,
                scope=scope,
                kind=kind,
                query=query,
                field=field,
                project_path=project_path,
                include_global=include_global,
                db_path=db_path,
                source_mode=source_mode,
                experiment_db=experiment_db,
                limit=limit,
                column_mode=column_mode,
                page_size=page_size,
                results_collapse=results_collapse,
                host=host,
                port=port,
                headless=headless,
            )
        )
    )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="nsgablack unified ui shell")
    parser.add_argument("--surface", choices=_SURFACE_OPTIONS, default="home")
    parser.add_argument("--profile", default="framework-core")
    parser.add_argument("--scope", choices=("framework", "project"), default="framework")
    parser.add_argument("--kind", default="all")
    parser.add_argument("--query", default="")
    parser.add_argument("--field", choices=("all", "name", "tag", "context", "usage"), default="all")
    parser.add_argument("--project-path", default=None)
    parser.add_argument("--include-global", action="store_true")
    parser.add_argument("--db-path", default=None)
    parser.add_argument("--source-mode", choices=("prefer", "only", "off"), default=None)
    parser.add_argument("--experiment-db", default=None)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--column-mode", choices=("compact", "standard", "full"), default=_shared.DEFAULT_COLUMN_MODE)
    parser.add_argument("--page-size", type=int, default=_shared.DEFAULT_PAGE_SIZE)
    parser.add_argument("--results-collapse", choices=("expanded", "collapsed"), default=_shared.DEFAULT_RESULTS_COLLAPSE)
    return parser.parse_known_args(argv)[0]


def _set_page_config() -> None:
    try:
        st.set_page_config(page_title="nsgablack ui", page_icon="NS", layout="wide")
    except Exception:
        return


def _inject_style() -> None:
    st.markdown(
        f"""
<style>
{_page.PAGE_PROTOCOL_STYLE}
.workspace-shell {{
  margin-bottom: 1rem;
  padding: 0.9rem 1rem;
  border-radius: 20px;
  border: 1px solid rgba(101, 70, 35, 0.16);
  background: linear-gradient(180deg, rgba(255,250,243,0.98), rgba(250,242,230,0.98));
  box-shadow: 0 12px 30px rgba(77, 54, 29, 0.08);
}}
.workspace-shell-head {{
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 0.45rem;
}}
.workspace-shell-kicker {{
  font-size: 0.74rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 800;
  color: #8b6840;
}}
.workspace-shell-title {{
  font-size: 1.18rem;
  font-weight: 800;
  color: #2f2115;
}}
.workspace-shell-subtitle {{
  color: #65513a;
  font-size: 0.9rem;
}}
.workspace-shell-note {{
  color: #816847;
  font-size: 0.84rem;
  text-align: right;
}}
.workspace-card-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 0.9rem;
  margin-top: 0.8rem;
}}
.workspace-card {{
  border-radius: 20px;
  border: 1px solid rgba(101, 70, 35, 0.14);
  background: rgba(255, 255, 255, 0.82);
  padding: 1rem 1.05rem;
}}
.workspace-card-title {{
  font-size: 1rem;
  font-weight: 800;
  color: #2f2115;
  margin-bottom: 0.22rem;
}}
.workspace-card-copy {{
  color: #65513a;
  font-size: 0.89rem;
  line-height: 1.55;
}}
.workspace-card-meta {{
  color: #816847;
  font-size: 0.81rem;
  margin-top: 0.55rem;
}}
</style>
""",
        unsafe_allow_html=True,
    )


def _coerce_query_value(value: Any) -> str:
    if isinstance(value, list):
        value = value[-1] if value else ""
    return str(value or "").strip()


def _raw_query_params() -> dict[str, str]:
    try:
        params = st.query_params
        return {str(key): _coerce_query_value(params.get(key)) for key in list(params.keys())}
    except Exception:
        try:
            raw = st.experimental_get_query_params()
        except Exception:
            return {}
        return {str(key): _coerce_query_value(value) for key, value in dict(raw).items()}


def _infer_surface(query_params: Mapping[str, str], default_surface: str) -> str:
    explicit = str(query_params.get("surface", "") or "").strip().lower()
    if explicit in _SURFACE_OPTIONS:
        return explicit
    if any(str(query_params.get(key, "") or "").strip() for key in _CATALOG_MARKER_KEYS):
        return "catalog"
    if any(str(query_params.get(key, "") or "").strip() for key in _EXPERIMENT_MARKER_KEYS):
        return "experiment"
    if any(key.startswith("f_run_") or key.startswith("f_artifact_") for key in query_params):
        return "experiment"
    if str(query_params.get("selected", "") or "").startswith(("run:", "artifact:")):
        return "experiment"
    return default_surface if default_surface in _SURFACE_OPTIONS else "home"


def _set_shell_surface(surface: str, *, clear_query: bool = False) -> None:
    base_params: dict[str, object] = {}
    if not clear_query:
        base_params["surface"] = str(surface)
    else:
        base_params["surface"] = "home"
    _shared.write_query_params(st, base_params=base_params, field_filters={})
    st.session_state[_SURFACE_STATE_KEY] = str(surface)


def _catalog_argv(args: argparse.Namespace) -> list[str]:
    out = [
        "--profile",
        str(args.profile),
        "--scope",
        str(args.scope),
        "--kind",
        str(args.kind),
        "--field",
        str(args.field),
        "--column-mode",
        str(args.column_mode),
        "--page-size",
        str(int(args.page_size)),
        "--results-collapse",
        str(args.results_collapse),
    ]
    if str(args.query or "").strip():
        out.extend(["--query", str(args.query)])
    if args.project_path:
        out.extend(["--project-path", str(args.project_path)])
    if bool(args.include_global):
        out.append("--include-global")
    if args.db_path:
        out.extend(["--db-path", str(args.db_path)])
    if args.source_mode:
        out.extend(["--source-mode", str(args.source_mode)])
    return out


def _experiment_argv(args: argparse.Namespace) -> list[str]:
    out = [
        "--limit",
        str(int(args.limit)),
        "--column-mode",
        str(args.column_mode),
        "--page-size",
        str(int(args.page_size)),
        "--results-collapse",
        str(args.results_collapse),
    ]
    experiment_db = str(args.experiment_db or experiment_db_config_info().get("db_target") or "").strip()
    if experiment_db:
        out[0:0] = ["--db", experiment_db]
    return out


def _render_shell_bar(surface: str) -> str:
    st.markdown(
        (
            "<div class='workspace-shell'>"
            "<div class='workspace-shell-head'>"
            "<div>"
            "<div class='workspace-shell-kicker'>nsgablack workspace</div>"
            "<div class='workspace-shell-title'>统一首页入口 / Unified Workspace</div>"
            "<div class='workspace-shell-subtitle'>"
            "在同一套 Streamlit 壳里切 catalog 与 experiment；如果 deep-link 里已经带了子页面参数，页面会自动回到对应工作面。"
            "</div>"
            "</div>"
            "<div class='workspace-shell-note'>"
            f"当前工作面: {_SURFACE_LABELS.get(surface, surface)}"
            "</div>"
            "</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )
    selected_surface = st.radio(
        "工作面 / Workspace",
        options=_SURFACE_OPTIONS,
        index=_SURFACE_OPTIONS.index(surface if surface in _SURFACE_OPTIONS else "home"),
        format_func=lambda value: _SURFACE_LABELS.get(str(value), str(value)),
        key=_SURFACE_WIDGET_KEY,
        horizontal=True,
    )
    action_cols = st.columns((0.9, 3.1))
    if action_cols[0].button("回到首页 / Home", key="nsgablack_ui_home", width="stretch"):
        _set_shell_surface("home", clear_query=True)
        _shared.rerun(st)
    action_cols[1].caption("提示：切换工作面会同步到 URL；子页面自己的 deep-link 仍然可用，统一壳也会根据 query 参数自动推断当前应该回到 catalog 还是 experiment。")
    return str(selected_surface)


def _render_home(args: argparse.Namespace) -> None:
    experiment_info = experiment_db_config_info()
    experiment_target = str(args.experiment_db or experiment_info.get("db_target") or "(auto)")
    _page.render_top_anchor(st)
    _page.render_hero(
        st,
        _page.HeroSpec(
            icon_text="NS",
            kicker="nsgablack ui",
            title="框架目录 + 运行实验统一入口 / Unified Catalog & Experiment Workspace",
            subtitle="左手看组件结构，右手看运行表面；从这里统一进入，不用再记两套独立命令。",
        ),
    )
    _page.render_stat_cards(
        st,
        (
            _page.StatCardSpec("Catalog 默认 Profile", str(args.profile), "framework / project 双视图"),
            _page.StatCardSpec("Catalog Source", str(args.source_mode or "auto"), str(args.db_path or "registry + auto DB config")),
            _page.StatCardSpec("Experiment DB", experiment_target, str(experiment_info.get("source") or "auto")),
        ),
    )
    _page.render_section_header(
        st,
        _page.SectionHeaderSpec(
            section_id=_page.FILTER_SECTION_ID,
            label="WORKSPACES",
            title="选择一个工作面 / Choose a Workspace",
            subtitle="首页负责统一入口；进入子页面后，catalog 与 experiment 仍保留各自的正式产品面和 deep-link 行为。",
        ),
    )
    st.markdown(
        (
            "<div class='workspace-card-grid'>"
            "<div class='workspace-card'>"
            "<div class='workspace-card-title'>框架目录 / Catalog</div>"
            "<div class='workspace-card-copy'>"
            "查 adapter、plugin、representation、bias 的合同、关系、来源、依赖链与 SQL materialize 结果。"
            "</div>"
            f"<div class='workspace-card-meta'>默认 profile: {args.profile} | source: {args.source_mode or 'auto'}</div>"
            "</div>"
            "<div class='workspace-card'>"
            "<div class='workspace-card-title'>运行实验 / Experiment</div>"
            "<div class='workspace-card-copy'>"
            "查 runtime run / artifact surface、组件装配、参数、结果、合同层与复现实验入口。"
            "</div>"
            f"<div class='workspace-card-meta'>默认 runtime DB: {experiment_target}</div>"
            "</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )
    action_cols = st.columns((1.0, 1.0, 2.0))
    if action_cols[0].button("打开 Catalog", key="nsgablack_ui_open_catalog", width="stretch"):
        _set_shell_surface("catalog", clear_query=False)
        _shared.rerun(st)
    if action_cols[1].button("打开 Experiment", key="nsgablack_ui_open_experiment", width="stretch"):
        _set_shell_surface("experiment", clear_query=False)
        _shared.rerun(st)
    action_cols[2].caption(
        "命令入口：`python -m nsgablack ui`。如果你已经有子页面 deep-link，也可以直接贴到浏览器里，统一壳会自动回到对应工作面。"
    )


def run_dashboard(argv: Sequence[str] | None = None) -> None:
    args = _parse_args(argv)
    _set_page_config()
    _inject_style()
    query_params = _raw_query_params()
    inferred_surface = _infer_surface(query_params, str(args.surface))
    current_surface = str(st.session_state.get(_SURFACE_STATE_KEY) or "").strip()
    if current_surface not in _SURFACE_OPTIONS or (query_params and inferred_surface != current_surface):
        st.session_state[_SURFACE_STATE_KEY] = inferred_surface
    current_surface = str(st.session_state.get(_SURFACE_STATE_KEY) or inferred_surface)
    widget_surface = str(st.session_state.get(_SURFACE_WIDGET_KEY) or "").strip()
    if widget_surface not in _SURFACE_OPTIONS or widget_surface != current_surface:
        st.session_state[_SURFACE_WIDGET_KEY] = current_surface
    surface = _render_shell_bar(current_surface)
    if surface != current_surface:
        _set_shell_surface(surface, clear_query=bool(surface == "home"))
        _shared.rerun(st)
    if surface == "home":
        _render_home(args)
        return
    if surface == "catalog":
        catalog_dashboard.run_dashboard(_catalog_argv(args))
        return
    experiment_dashboard.run_dashboard(_experiment_argv(args))


def main(argv: Sequence[str] | None = None) -> None:
    run_dashboard(argv)


if __name__ == "__main__":
    main(sys.argv[1:])
