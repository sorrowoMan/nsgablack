from __future__ import annotations

from typing import Tuple
import numpy as np


def get_num_objectives(problem) -> int:
    if hasattr(problem, "get_num_objectives"):
        try:
            return int(problem.get_num_objectives())
        except Exception:
            pass
    for attr in ("n_objectives", "num_objectives"):
        if hasattr(problem, attr):
            try:
                return int(getattr(problem, attr))
            except Exception:
                pass
    return 1


def get_problem_dimension(problem, bounds=None) -> int:
    if hasattr(problem, "dimension"):
        try:
            return int(problem.dimension)
        except Exception:
            pass
    if bounds is None:
        bounds = getattr(problem, "bounds", None)
    if bounds is not None:
        if isinstance(bounds, dict):
            return len(bounds)
        try:
            return int(np.asarray(bounds).shape[0])
        except Exception:
            pass
    lower = getattr(problem, "lower_bounds", None)
    if lower is not None:
        try:
            return int(len(lower))
        except Exception:
            pass
    return 0


def get_problem_bounds(problem) -> Tuple[np.ndarray, np.ndarray]:
    lower = getattr(problem, "lower_bounds", None)
    upper = getattr(problem, "upper_bounds", None)
    if lower is not None and upper is not None:
        return np.asarray(lower, dtype=float), np.asarray(upper, dtype=float)

    bounds = getattr(problem, "bounds", None)
    if bounds is not None:
        if isinstance(bounds, dict):
            if hasattr(problem, "variables"):
                keys = list(problem.variables)
            else:
                keys = sorted(bounds.keys())
            lows = []
            highs = []
            for key in keys:
                value = bounds.get(key)
                if value is None or len(value) < 2:
                    continue
                lows.append(value[0])
                highs.append(value[1])
            if lows and highs:
                return np.asarray(lows, dtype=float), np.asarray(highs, dtype=float)
        else:
            arr = np.asarray(bounds, dtype=float)
            if arr.ndim == 2 and arr.shape[1] == 2:
                return arr[:, 0], arr[:, 1]
            if arr.ndim == 2 and arr.shape[0] == 2:
                return arr[0], arr[1]

    dim = get_problem_dimension(problem, bounds=bounds)
    if dim <= 0:
        dim = 1
    return np.full(dim, -5.0, dtype=float), np.full(dim, 5.0, dtype=float)
