"""Tkinter UI entrypoints with lazy optional-dependency loading."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Optional


_TK_IMPORT_NAMES = {"tkinter", "_tkinter"}
_TK_UNAVAILABLE_MESSAGE = (
    "NSGABlack's Tk UI is unavailable because this Python runtime does not "
    "provide tkinter/Tcl-Tk. Install Tk support before calling a visualization launcher."
)


def _load_app_module() -> ModuleType:
    """Load the Tk application only when a UI entrypoint is actually used."""
    try:
        importlib.import_module("tkinter")
    except ImportError as exc:
        if str(getattr(exc, "name", "")) not in _TK_IMPORT_NAMES:
            raise
        raise RuntimeError(_TK_UNAVAILABLE_MESSAGE) from exc

    if __package__:
        return importlib.import_module(f"{__package__}.app")

    # Preserve direct-script execution without broad ImportError fallback.
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return importlib.import_module("utils.viz.app")


def launch_from_builder(builder: Callable[[], Any], *, entry_label: str = "<in-code>") -> int:
    return int(_load_app_module().launch_from_builder(builder, entry_label=entry_label))


def launch_from_entry(entry: str) -> int:
    return int(_load_app_module().launch_from_entry(entry))


def launch_empty(*, workspace: Optional[str] = None) -> int:
    return int(_load_app_module().launch_empty(workspace=workspace))


def maybe_launch_ui(
    builder: Callable[[], Any],
    *,
    entry_label: str = "<in-code>",
    env_var: str = "NSGABLACK_UI",
) -> bool:
    """Load Tk only when the environment flag actually requests the UI."""
    if os.environ.get(env_var, "0").strip().lower() not in {"1", "true", "yes", "on"}:
        return False
    return bool(
        _load_app_module().maybe_launch_ui(
            builder,
            entry_label=entry_label,
            env_var=env_var,
        )
    )


def main() -> int:
    return int(_load_app_module().main())


def __getattr__(name: str) -> Any:
    if name == "VisualizerApp":
        return getattr(_load_app_module(), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "VisualizerApp",
    "launch_empty",
    "launch_from_builder",
    "launch_from_entry",
    "maybe_launch_ui",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
