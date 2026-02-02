"""
Tkinter UI entrypoint (thin wrapper).
"""

try:
    from .app import VisualizerApp, launch_from_builder, launch_from_entry, maybe_launch_ui, main
except ImportError:  # allow running as a script
    import sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from utils.viz.app import VisualizerApp, launch_from_builder, launch_from_entry, maybe_launch_ui, main

__all__ = [
    "VisualizerApp",
    "launch_from_builder",
    "launch_from_entry",
    "maybe_launch_ui",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
