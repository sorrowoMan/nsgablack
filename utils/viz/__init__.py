"""
Visualization helpers (optional).

Canonical import:

    from nsgablack.utils.viz import SolverVisualizationMixin
"""

from .matplotlib import SolverVisualizationMixin
from .visualizer_tk import launch_from_builder, launch_from_entry, maybe_launch_ui

__all__ = [
    "SolverVisualizationMixin",
    "launch_from_builder",
    "launch_from_entry",
    "maybe_launch_ui",
]
