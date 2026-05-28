from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.error import URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
from uuid import uuid4

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
_AI_SESSION_KEY = "nsgablack_ui_ai_session_id"
_AI_HISTORY_PREFIX = "nsgablack_ui_ai_history"
_AI_SERVICE_URL_ENV = "NSGABLACK_AI_ASSISTANT_URL"
_ASSISTANT_AUTOSTARTED: set[str] = set()
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
/* AI 悬浮对话框容器 */
.ai-chat-container {{
    position: fixed;
    right: 1.5rem;
    bottom: 2rem;
    z-index: 9999;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", sans-serif;
}}

/* 浮窗主体 */
.ai-chat-box {{
    width: 360px;
    max-height: 520px;
    background: #ffffff;
    border-radius: 12px;
    box-shadow: 0 8px 32px rgba(30, 64, 175, 0.20), 0 2px 8px rgba(0, 0, 0, 0.08);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    border: 1px solid rgba(200, 210, 240, 0.4);
}}

/* 消息历史区域 */
.ai-chat-messages {{
    flex: 1;
    overflow-y: auto;
    padding: 1rem;
    background: #fafbff;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
}}

.ai-chat-messages::-webkit-scrollbar {{
    width: 6px;
}}

.ai-chat-messages::-webkit-scrollbar-track {{
    background: transparent;
}}

.ai-chat-messages::-webkit-scrollbar-thumb {{
    background: rgba(100, 120, 180, 0.3);
    border-radius: 3px;
}}

.ai-chat-messages::-webkit-scrollbar-thumb:hover {{
    background: rgba(100, 120, 180, 0.5);
}}

/* 消息气泡 */
.ai-msg-user {{
    display: flex;
    justify-content: flex-end;
    margin-bottom: 0.3rem;
}}

.ai-msg-user-bubble {{
    background: linear-gradient(135deg, #1f3c88, #3454b0);
    color: #ffffff;
    padding: 0.65rem 0.95rem;
    border-radius: 12px 4px 12px 12px;
    max-width: 75%;
    word-wrap: break-word;
    font-size: 0.9rem;
    line-height: 1.4;
}}

.ai-msg-assistant {{
    display: flex;
    justify-content: flex-start;
    margin-bottom: 0.3rem;
}}

.ai-msg-assistant-bubble {{
    background: #e8eef8;
    color: #1f3c88;
    padding: 0.65rem 0.95rem;
    border-radius: 4px 12px 12px 12px;
    max-width: 75%;
    word-wrap: break-word;
    font-size: 0.9rem;
    line-height: 1.4;
}}

/* 输入框区域 */
.ai-chat-input-area {{
    padding: 0.8rem;
    background: #ffffff;
    border-top: 1px solid rgba(200, 210, 240, 0.3);
    display: flex;
    gap: 0.5rem;
}}

.ai-chat-input {{
    flex: 1;
    border: 1px solid rgba(100, 140, 200, 0.3);
    border-radius: 6px;
    padding: 0.55rem 0.75rem;
    font-size: 0.9rem;
    font-family: inherit;
    resize: none;
    max-height: 80px;
    outline: none;
}}

.ai-chat-input:focus {{
    border-color: rgba(31, 60, 136, 0.5);
    box-shadow: 0 0 0 2px rgba(31, 60, 136, 0.08);
}}

.ai-chat-btn {{
    background: linear-gradient(135deg, #1f3c88, #3454b0);
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 0.55rem 1rem;
    font-weight: 600;
    font-size: 0.85rem;
    cursor: pointer;
    transition: all 0.2s ease;
    white-space: nowrap;
}}

.ai-chat-btn:hover {{
    background: linear-gradient(135deg, #263d80, #3d5ac0);
    box-shadow: 0 4px 12px rgba(31, 60, 136, 0.20);
}}

.ai-chat-btn:active {{
    transform: scale(0.98);
}}

.ai-chat-btn.clear {{
    background: rgba(200, 100, 100, 0.6);
    padding: 0.55rem 0.7rem;
}}

.ai-chat-btn.clear:hover {{
    background: rgba(200, 100, 100, 0.8);
}}

/* 浮窗触发按钮 */
.ai-chat-toggle-btn {{
    width: 3.5rem;
    height: 3.5rem;
    border-radius: 50%;
    border: none;
    background: linear-gradient(135deg, rgba(31, 60, 136, 0.96), rgba(52, 84, 176, 0.98));
    color: #ffffff;
    box-shadow: 0 4px 16px rgba(30, 64, 175, 0.32);
    font-size: 1.3rem;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
}}

.ai-chat-toggle-btn:hover {{
    transform: scale(1.08);
    box-shadow: 0 6px 20px rgba(30, 64, 175, 0.40);
}}

.ai-chat-toggle-btn:active {{
    transform: scale(0.95);
}}

/* 对话框头部 */
.ai-chat-header {{
    background: linear-gradient(135deg, #1f3c88, #3454b0);
    color: #ffffff;
    padding: 1rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}}

.ai-chat-header-title {{
    font-weight: 800;
    font-size: 0.95rem;
}}

.ai-chat-close-btn {{
    background: rgba(255, 255, 255, 0.2);
    border: none;
    color: #ffffff;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.1rem;
    transition: background 0.2s;
}}

.ai-chat-close-btn:hover {{
    background: rgba(255, 255, 255, 0.3);
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


def _assistant_service_base_url() -> str:
    import os

    return str(os.getenv(_AI_SERVICE_URL_ENV, "http://127.0.0.1:5001") or "http://127.0.0.1:5001").rstrip("/")


def _assistant_service_health_url(service_base_url: str) -> str:
    return f"{service_base_url.rstrip('/')}/health"


def _assistant_service_script_path() -> Path:
    return Path(__file__).resolve().parents[2] / "mlblack" / "examples" / "catalog_assistant" / "server.py"


def _assistant_service_is_local(service_base_url: str) -> bool:
    parsed = urlsplit(service_base_url)
    return parsed.scheme in {"http", "https"} and parsed.hostname in {"127.0.0.1", "localhost"} and parsed.port == 5001


def _assistant_service_is_ready(service_base_url: str) -> bool:
    request = Request(_assistant_service_health_url(service_base_url), method="GET")
    try:
        with urlopen(request, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return isinstance(payload, dict) and payload.get("status") == "ok"
    except Exception:
        return False


def _assistant_try_autostart(service_base_url: str) -> bool:
    if not _assistant_service_is_local(service_base_url):
        return False
    if service_base_url in _ASSISTANT_AUTOSTARTED and not _assistant_service_is_ready(service_base_url):
        return False

    script_path = _assistant_service_script_path()
    if not script_path.is_file():
        return False

    if _assistant_service_is_ready(service_base_url):
        return True

    _ASSISTANT_AUTOSTARTED.add(service_base_url)
    try:
        subprocess.Popen(
            [sys.executable, str(script_path)],
            cwd=str(script_path.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return False

    for _ in range(20):
        if _assistant_service_is_ready(service_base_url):
            return True
        time.sleep(0.5)
    return False


def _assistant_session_id() -> str:
    session_id = str(st.session_state.get(_AI_SESSION_KEY) or "").strip()
    if not session_id:
        session_id = uuid4().hex
        st.session_state[_AI_SESSION_KEY] = session_id
    return session_id


def _assistant_history_key(surface: str) -> str:
    return f"{_AI_HISTORY_PREFIX}::{surface}"


def _assistant_history(surface: str) -> list[dict[str, str]]:
    raw = st.session_state.get(_assistant_history_key(surface), [])
    if not isinstance(raw, list):
        return []
    history: list[dict[str, str]] = []
    for item in raw:
        if isinstance(item, Mapping):
            role = str(item.get("role", "") or "").strip()
            content = str(item.get("content", "") or "").strip()
            if role and content:
                history.append({"role": role, "content": content})
    return history


def _assistant_set_history(surface: str, history: list[dict[str, str]]) -> None:
    st.session_state[_assistant_history_key(surface)] = history[-12:]


def _assistant_is_transient_transport_error(exc: Exception) -> bool:
    if isinstance(exc, URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, (ConnectionResetError, BrokenPipeError, TimeoutError)):
            return True
        if isinstance(reason, OSError) and getattr(reason, "winerror", None) == 10054:
            return True
        message = str(reason or exc)
    else:
        message = str(exc)
        if isinstance(exc, (ConnectionResetError, BrokenPipeError, TimeoutError)):
            return True
        if isinstance(exc, OSError) and getattr(exc, "winerror", None) == 10054:
            return True
    lowered = message.lower()
    return "10054" in lowered or "connection reset" in lowered or "远程主机强迫关闭" in message


def _assistant_call_api(query: str, history: list[dict[str, str]]) -> dict[str, Any]:
    payload = json.dumps({"query": query, "session_id": _assistant_session_id()}).encode("utf-8")
    service_base_url = _assistant_service_base_url()
    if not _assistant_service_is_ready(service_base_url):
        _assistant_try_autostart(service_base_url)

    def _post_once() -> dict[str, Any] | None:
        request = Request(
            f"{service_base_url}/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=30) as response:
            text = response.read().decode("utf-8")
            result = json.loads(text)
            if isinstance(result, dict):
                return result
        return None

    try:
        result = _post_once()
        if result is not None:
            return result
    except Exception as exc:
        if _assistant_is_transient_transport_error(exc):
            _assistant_try_autostart(service_base_url)
            try:
                result = _post_once()
                if result is not None:
                    return result
            except Exception as retry_exc:
                exc = retry_exc

        return {
            "reply": f"AI 服务响应异常：{exc}\n\n已尝试自动启动 `catalog_assistant`，如果仍失败，请手动运行：`python c:\\Users\\hp\\Desktop\\mlblack\\examples\\catalog_assistant\\server.py`",
            "entries": [],
            "service_url": service_base_url,
        }
    return {"reply": "AI 服务返回空结果。", "entries": [], "service_url": service_base_url}


def _render_history_message(role: str, content: str) -> None:
    if hasattr(st, "chat_message"):
        with st.chat_message(role if role in {"user", "assistant"} else "assistant"):
            st.markdown(content)
        return
    prefix = "用户" if role == "user" else "助手"
    st.markdown(f"**{prefix}**：{content}")


def _render_ai_panel(surface: str) -> None:
    """渲染紧凑型 AI 对话面板。"""
    history = _assistant_history(surface)
    st.caption(f"Catalog Assistant · {_assistant_service_base_url()}/chat")
    draft_key = f"{_assistant_history_key(surface)}::draft"
    clear_draft_key = f"{_assistant_history_key(surface)}::clear_draft"

    if bool(st.session_state.pop(clear_draft_key, False)):
        st.session_state[draft_key] = ""
    
    # 消息显示区域
    st.markdown('<div class="ai-chat-messages">', unsafe_allow_html=True)
    if not history:
        st.markdown(
            '<div style="text-align: center; color: #999; padding: 0.9rem 0.4rem; font-size: 0.82rem;">'
            '👋 欢迎使用AI助手，请输入你的问题'
            '</div>',
            unsafe_allow_html=True
        )
    else:
        for item in history:
            role = item.get("role", "assistant")
            content = item.get("content", "")
            if role == "user":
                st.markdown(
                    f'<div class="ai-msg-user"><div class="ai-msg-user-bubble">{content}</div></div>',
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f'<div class="ai-msg-assistant"><div class="ai-msg-assistant-bubble">{content}</div></div>',
                    unsafe_allow_html=True
                )
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 输入和操作区域
    st.markdown('<div class="ai-chat-input-area">', unsafe_allow_html=True)
    col1, col2 = st.columns([4, 1])
    
    prompt = col1.text_area(
        "输入问题",
        key=draft_key,
        height=72,
        label_visibility="collapsed",
        placeholder="输入问题..."
    )
    
    send_clicked = col2.button(
        "发送",
        key=f"{_assistant_history_key(surface)}::send",
        use_container_width=True,
        help="发送问题给AI"
    )
    
    if send_clicked:
        if not str(prompt or "").strip():
            st.warning("请输入内容后再发送。")
        else:
            history.append({"role": "user", "content": str(prompt).strip()})
            result = _assistant_call_api(str(prompt).strip(), history)
            reply = str(result.get("reply", "")).strip() or "AI 没有返回内容。"
            history.append({"role": "assistant", "content": reply})
            _assistant_set_history(surface, history)
            st.session_state[clear_draft_key] = True
            _shared.rerun(st)
    
    st.markdown('</div>', unsafe_allow_html=True)


def _render_ai_floating_window(surface: str) -> None:
    """渲染右侧固定的小图标浮窗，并在展开时显示紧凑对话框。"""
    st.markdown(
        """
<style>
.ai-float-shell {
    position: fixed;
    right: 0.9rem;
    top: 52%;
    transform: translateY(-50%);
    z-index: 9999;
}
.ai-float-shell [data-testid="stPopover"] > button {
    width: 3.15rem;
    height: 3.15rem;
    min-width: 3.15rem !important;
    padding: 0 !important;
    border: 0 !important;
    border-radius: 999px !important;
    font-size: 1rem !important;
    font-weight: 800 !important;
    background: linear-gradient(135deg, rgba(31, 60, 136, 0.98), rgba(52, 84, 176, 0.98)) !important;
    color: #fff !important;
    box-shadow: 0 10px 20px rgba(30, 64, 175, 0.28) !important;
}
.ai-float-shell [data-testid="stPopover"] > button:hover {
    transform: scale(1.06);
}
.ai-float-shell [data-testid="stPopover"] {
    min-width: 0 !important;
}
.ai-float-popover {
    width: min(22rem, 82vw) !important;
}
.ai-chat-box {
    width: 100%;
    max-width: 22rem;
    border-radius: 14px;
    overflow: hidden;
    border: 1px solid rgba(140, 160, 220, 0.16);
    box-shadow: 0 16px 36px rgba(30, 64, 175, 0.16);
}
.ai-chat-header {
    display: flex;
    justify-content: space-between;
    gap: 0.5rem;
    align-items: center;
    padding: 0.72rem 0.82rem;
    background: linear-gradient(135deg, rgba(31, 60, 136, 0.98), rgba(52, 84, 176, 0.98));
    color: #fff;
}
.ai-chat-header-title {
    font-size: 0.92rem;
    font-weight: 800;
}
.ai-chat-status {
    font-size: 0.71rem;
    opacity: 0.84;
    margin-top: 0.05rem;
}
.ai-chat-messages {
    max-height: 16rem;
    overflow: auto;
    padding: 0.68rem;
    background: #f8fbff;
}
.ai-chat-input-area {
    padding: 0.68rem;
    border-top: 1px solid rgba(140, 160, 220, 0.12);
    background: #fff;
}
.ai-msg-user, .ai-msg-assistant {
    display: flex;
    margin-bottom: 0.4rem;
}
.ai-msg-user { justify-content: flex-end; }
.ai-msg-assistant { justify-content: flex-start; }
.ai-msg-user-bubble, .ai-msg-assistant-bubble {
    max-width: 90%;
    padding: 0.45rem 0.68rem;
    border-radius: 12px;
    font-size: 0.84rem;
    line-height: 1.45;
    white-space: pre-wrap;
    word-break: break-word;
}
.ai-msg-user-bubble {
    background: linear-gradient(135deg, #1f3c88, #3454b0);
    color: #fff;
    border-bottom-right-radius: 4px;
}
.ai-msg-assistant-bubble {
    background: #e8eef8;
    color: #203562;
    border-bottom-left-radius: 4px;
}
</style>
    """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="ai-float-shell">', unsafe_allow_html=True)
    if hasattr(st, "popover"):
        with st.popover("💬", use_container_width=False):
            st.markdown('<div class="ai-float-popover">', unsafe_allow_html=True)
            st.markdown('<div class="ai-chat-box">', unsafe_allow_html=True)
            st.markdown(
                f'<div class="ai-chat-header"><div><div class="ai-chat-header-title">🤖 AI 助手</div><div class="ai-chat-status">Catalog Assistant · {_assistant_service_base_url()}</div></div></div>',
                unsafe_allow_html=True,
            )
            _render_ai_panel(surface)
            st.markdown('</div></div>', unsafe_allow_html=True)
    else:
        with st.expander("💬", expanded=False):
            st.markdown('<div class="ai-float-popover">', unsafe_allow_html=True)
            st.markdown('<div class="ai-chat-box">', unsafe_allow_html=True)
            st.markdown(
                f'<div class="ai-chat-header"><div><div class="ai-chat-header-title">🤖 AI 助手</div><div class="ai-chat-status">Catalog Assistant · {_assistant_service_base_url()}</div></div></div>',
                unsafe_allow_html=True,
            )
            _render_ai_panel(surface)
            st.markdown('</div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


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
        horizontal=True,
    )
    action_cols = st.columns((0.9, 1.1, 2.0))
    if action_cols[0].button("回到首页 / Home", key="nsgablack_ui_home", use_container_width=True):
        _set_shell_surface("home", clear_query=True)
        _shared.rerun(st)
    action_cols[2].caption("提示：切换工作面会同步到 URL；子页面自己的 deep-link 仍然可用，统一壳也会根据 query 参数自动推断当前应该回到 catalog 还是 experiment。")
    
    # 在页面底部渲染AI浮窗
    _render_ai_floating_window(surface)
    
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
    if action_cols[0].button("打开 Catalog", key="nsgablack_ui_open_catalog", use_container_width=True):
        _set_shell_surface("catalog", clear_query=False)
        _shared.rerun(st)
    if action_cols[1].button("打开 Experiment", key="nsgablack_ui_open_experiment", use_container_width=True):
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
