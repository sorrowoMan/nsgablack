from __future__ import annotations

from typing import Any


def dashboard_main(*args: Any, **kwargs: Any):
    from .dashboard import main

    return main(*args, **kwargs)


def build_streamlit_command(*args: Any, **kwargs: Any):
    from .dashboard import build_streamlit_command as _build_streamlit_command

    return _build_streamlit_command(*args, **kwargs)


def launch_ui_dashboard(*args: Any, **kwargs: Any):
    from .dashboard import launch_ui_dashboard as _launch_ui_dashboard

    return _launch_ui_dashboard(*args, **kwargs)


def dashboard_script_path():
    from .dashboard import dashboard_script_path as _dashboard_script_path

    return _dashboard_script_path()


__all__ = [
    "build_streamlit_command",
    "dashboard_main",
    "dashboard_script_path",
    "launch_ui_dashboard",
]
