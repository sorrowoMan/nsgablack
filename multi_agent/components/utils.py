"""Auto-extracted mixin module."""
from __future__ import annotations


from typing import List, Dict, Optional
import numpy as np

from multi_agent.core.role import AgentRole

class UtilsMixin:
    """Mixin for multi-agent solver."""

    def _normalize_bounds(self, bounds) -> np.ndarray:
        if isinstance(bounds, dict):
            keys = self.variables if isinstance(self.variables, list) else list(bounds.keys())
            return np.asarray([bounds[k] for k in keys], dtype=float)
        return np.asarray(bounds, dtype=float)

    def _get_effective_bounds(self, bias_profile: Optional[Dict]) -> np.ndarray:
        bounds = self._normalize_bounds(self.var_bounds)
        if isinstance(bias_profile, dict):
            region_bounds = bias_profile.get('region_bounds')
            if region_bounds is not None:
                region_bounds = np.asarray(region_bounds, dtype=float)
                if region_bounds.shape == bounds.shape:
                    bounds = region_bounds.copy()
        # ensure bounds stay inside global bounds
        bounds[:, 0] = np.maximum(bounds[:, 0], self.var_bounds[:, 0])
        bounds[:, 1] = np.minimum(bounds[:, 1], self.var_bounds[:, 1])
        return bounds

    def _clip_to_bounds(self, x: np.ndarray, bounds: np.ndarray) -> np.ndarray:
        return np.clip(x, bounds[:, 0], bounds[:, 1])

    def _dominates(self, obj1: List[float], obj2: List[float]) -> bool:
        """判断obj1是否支配obj2"""
        if obj2 is None:
            return True
        return all(o1 <= o2 for o1, o2 in zip(obj1, obj2)) and any(o1 < o2 for o1, o2 in zip(obj1, obj2))

    def _total_violation(self, constraints: List[float]) -> float:
        """sum of constraint violations"""
        if not constraints:
            return 0.0
        try:
            arr = np.asarray(constraints, dtype=float).flatten()
            if arr.size == 0:
                return 0.0
            return float(np.sum(np.maximum(arr, 0.0)))
        except Exception:
            return float(sum(max(0.0, float(c)) for c in constraints))

    def _normalize_metric(self, values: Dict[AgentRole, float]) -> Dict[AgentRole, float]:
        """min-max normalize per role"""
        if not values:
            return {}
        vals = list(values.values())
        v_min = min(vals)
        v_max = max(vals)
        if abs(v_max - v_min) < 1e-12:
            return {role: 0.0 for role in values}
        return {role: (val - v_min) / (v_max - v_min) for role, val in values.items()}

