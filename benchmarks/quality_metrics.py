"""Self-contained quality metrics: IGD and exact hypervolume.

These are independent, published-definition implementations used only by the
quality benchmark. Unlike the transparency suite (which delegates HV/IGD to
pymoo), the quality benchmark deliberately has no pymoo dependency so it can run
in any environment with numpy/scipy. Correctness is pinned by unit tests against
hand-computed values.
"""
from __future__ import annotations

import numpy as np

from nsgablack.utils.analysis.metrics import igd, pareto_filter

__all__ = ["igd", "pareto_filter", "hypervolume"]


def hypervolume(objectives, reference_point):
    """Exact hypervolume (minimization) of the union of boxes [f, reference].

    Points not weakly dominated by the reference point (any objective above the
    reference) contribute nothing and are ignored.
    """
    obj = np.asarray(objectives, dtype=float)
    ref = np.asarray(reference_point, dtype=float)
    if obj.size == 0:
        return 0.0
    if obj.ndim == 1:
        obj = obj.reshape(1, -1)
    if obj.shape[1] != ref.shape[0]:
        raise ValueError("objective dimension must match reference point dimension")
    mask = np.all(obj <= ref, axis=1)
    obj = obj[mask]
    if obj.shape[0] == 0:
        return 0.0
    obj = pareto_filter(obj)  # dominated points add no volume
    if obj.shape[0] == 0:
        return 0.0
    return float(_hypervolume_recursive(obj, ref))


def _hypervolume_recursive(points, ref):
    """Dimension-sweep recursion (HSO). ``points`` is non-dominated and <= ref."""
    m = points.shape[1]
    if m == 1:
        return float(ref[0] - np.min(points[:, 0]))
    order = np.argsort(points[:, 0], kind="stable")
    pts = points[order]
    volume = 0.0
    prev = float(ref[0])
    for i in range(pts.shape[0] - 1, -1, -1):
        width = prev - float(pts[i, 0])
        if width > 0.0:
            volume += width * _hypervolume_recursive(pts[: i + 1, 1:], ref[1:])
        prev = float(pts[i, 0])
    return volume
