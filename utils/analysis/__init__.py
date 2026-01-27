"""
Analysis utilities (Pareto filtering, hypervolume, IGD, reference fronts).
"""

from __future__ import annotations

from .metrics import (
    pareto_filter,
    hypervolume_2d,
    igd,
    reference_front_zdt1,
    reference_front_zdt3,
    reference_front_dtlz2,
)

__all__ = [
    "pareto_filter",
    "hypervolume_2d",
    "igd",
    "reference_front_zdt1",
    "reference_front_zdt3",
    "reference_front_dtlz2",
]
