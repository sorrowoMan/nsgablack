"""
Visualization helpers (optional).

Canonical import:

    from nsgablack.utils.viz import SolverVisualizationMixin
"""

try:
    from .matplotlib import SolverVisualizationMixin
except Exception:  # optional dependency
    SolverVisualizationMixin = None
from .visualizer_tk import launch_empty, launch_from_builder, launch_from_entry, maybe_launch_ui

__all__ = [
    "SolverVisualizationMixin",
    "launch_empty",
    "launch_from_builder",
    "launch_from_entry",
    "maybe_launch_ui",
]
