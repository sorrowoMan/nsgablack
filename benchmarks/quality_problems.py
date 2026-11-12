"""Analytical test problems and reference fronts for the quality benchmark.

These implement the published ZDT / DTLZ definitions directly (no pymoo), so the
quality benchmark has no runtime dependency beyond numpy/scipy. Reference fronts
are analytical (published Pareto-front equations), so the framework is not
grading itself with a front it produced.
"""
from __future__ import annotations

import numpy as np

from nsgablack.core import BlackBoxProblem
from nsgablack.utils.analysis.metrics import reference_front_zdt3


class ZDTProblem(BlackBoxProblem):
    """ZDT1/2/3/6 test problems (two objectives, x in [0, 1]^n).

    ZDT4 is intentionally omitted for now: its decision variables are not
    uniformly bounded ([0,1] for x1, [-5,5] for the rest), which needs
    variable-wise bounds in the mutation/repair operators.
    """

    def __init__(self, variant, n_var=30):
        if int(variant) not in (1, 2, 3, 6):
            raise ValueError(f"unsupported ZDT variant: {variant}")
        self.variant = int(variant)
        super().__init__(
            name=f"ZDT{self.variant}",
            dimension=int(n_var),
            bounds=[(0.0, 1.0)] * int(n_var),
            objectives=["min", "min"],
        )

    def evaluate(self, candidate):
        x = np.asarray(candidate, dtype=float)
        if self.variant == 6:
            f1 = 1.0 - np.exp(-4.0 * x[0]) * np.sin(6.0 * np.pi * x[0]) ** 6
            g = 1.0 + 9.0 * (np.sum(x[1:]) / (len(x) - 1)) ** 0.25
            f2 = g * (1.0 - (f1 / g) ** 2)
        else:
            f1 = x[0]
            g = 1.0 + 9.0 * np.sum(x[1:]) / (len(x) - 1)
            if self.variant == 1:
                h = 1.0 - np.sqrt(f1 / g)
            elif self.variant == 2:
                h = 1.0 - (f1 / g) ** 2
            else:  # ZDT3
                h = 1.0 - np.sqrt(f1 / g) - (f1 / g) * np.sin(10.0 * np.pi * f1)
            f2 = g * h
        return np.array([f1, f2], dtype=float)


class DTLZProblem(BlackBoxProblem):
    """DTLZ1 (linear) / DTLZ2 / DTLZ4 test problems (m objectives, x in [0,1]^n)."""

    def __init__(self, variant, n_obj=3, n_var=None):
        if int(variant) not in (1, 2, 4):
            raise ValueError(f"unsupported DTLZ variant: {variant}")
        self.variant = int(variant)
        self.n_obj = int(n_obj)
        if n_var is None:
            n_var = self.n_obj + 10 - 1  # k = 10 position variables
        super().__init__(
            name=f"DTLZ{self.variant}-{self.n_obj}",
            dimension=int(n_var),
            bounds=[(0.0, 1.0)] * int(n_var),
            objectives=["min"] * self.n_obj,
        )

    def evaluate(self, candidate):
        x = np.asarray(candidate, dtype=float)
        m = self.n_obj

        if self.variant == 1:  # linear DTLZ1; Pareto front is the simplex sum(f)=0.5
            k = len(x) - m + 1
            g = 100.0 * (k + np.sum((x[m - 1:] - 0.5) ** 2
                                    - np.cos(20.0 * np.pi * (x[m - 1:] - 0.5))))
            f = np.empty(m, dtype=float)
            for i in range(m):
                val = 1.0
                for j in range(m - 1 - i):
                    val *= x[j]
                if i >= 1:
                    val *= (1.0 - x[m - 1 - i])
                f[i] = 0.5 * (1.0 + g) * val
            return f

        # DTLZ2 / DTLZ4 share the cos/sin shape; DTLZ4 raises x_j to alpha=100.
        g = float(np.sum((x[m - 1:] - 0.5) ** 2))
        f = np.empty(m, dtype=float)
        for i in range(m):
            val = 1.0 + g
            for j in range(m - 1 - i):
                xj = x[j] if self.variant == 2 else x[j] ** 100.0
                val *= np.cos(xj * np.pi / 2.0)
            if i >= 1:
                idx = m - 1 - i
                xj = x[idx] if self.variant == 2 else x[idx] ** 100.0
                val *= np.sin(xj * np.pi / 2.0)
            f[i] = val
        return f


class DTLZ2Problem(DTLZProblem):
    """Backward-compatible alias for the DTLZ2 variant."""

    def __init__(self, n_obj=3, n_var=None):
        super().__init__(2, n_obj=n_obj, n_var=n_var)


def zdt_reference_front(variant, n_points=1000):
    """Analytical Pareto front for ZDT1/2/3/6."""
    variant = int(variant)
    if variant == 3:
        return reference_front_zdt3(n_points)
    if variant == 6:
        # ZDT6's first objective is bounded away from zero.
        f1 = np.linspace(0.2807753191, 1.0, n_points)
        return np.column_stack([f1, 1.0 - f1 ** 2])
    f1 = np.linspace(0.0, 1.0, n_points)
    if variant == 2:
        return np.column_stack([f1, 1.0 - f1 ** 2])
    return np.column_stack([f1, 1.0 - np.sqrt(f1)])


def dtlz_reference_front(variant, n_obj, n_points=1000):
    """Analytical Pareto front for DTLZ1 (simplex sum=0.5) / DTLZ2,4 (unit sphere)."""
    variant = int(variant)
    n_obj = int(n_obj)
    partitions = _partitions_for(n_obj, n_points)
    weights = _simplex_grid(n_obj, partitions)
    if variant == 1:
        return 0.5 * weights
    return np.sqrt(weights)


def dtlz1_reference_front(n_obj, n_points=1000):
    return dtlz_reference_front(1, n_obj, n_points)


def dtlz2_reference_front(n_obj, n_points=1000):
    return dtlz_reference_front(2, n_obj, n_points)


def _partitions_for(n_obj, target):
    from math import comb

    p = 1
    while comb(p + n_obj - 1, n_obj - 1) < target:
        p += 1
    return p


def _simplex_grid(n_obj, partitions):
    weights = list(_compositions(int(partitions), n_obj))
    return np.asarray(weights, dtype=float) / float(partitions)


def _compositions(total, parts):
    if parts == 1:
        yield (total,)
        return
    for first in range(total + 1):
        for rest in _compositions(total - first, parts - 1):
            yield (first,) + rest
