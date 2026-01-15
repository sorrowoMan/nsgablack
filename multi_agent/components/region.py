"""Auto-extracted mixin module."""
from __future__ import annotations


from typing import Any, Dict, List
import numpy as np
from ..core.role import AgentRole

class RegionMixin:
    """Mixin for multi-agent solver."""

    def _update_region_partition(self, generation: int) -> None:
        """Update per-role region bounds based on current quality."""
        interval = self.config.get('region_update_interval')
        if interval is None:
            interval = self.config.get('adaptation_interval', 1)
        try:
            interval = int(interval)
        except (TypeError, ValueError):
            interval = 1
        if interval <= 0 or generation % interval != 0:
            return

        candidates = self._collect_region_candidates()
        if not candidates:
            return

        top_ratio = float(self.config.get('region_top_ratio', 0.2))
        top_k = max(5, int(len(candidates) * top_ratio))
        top_k = min(top_k, len(candidates))
        top_candidates = candidates[:top_k]
        xs = np.asarray([c['x'] for c in top_candidates], dtype=float)
        if xs.size == 0:
            return

        base_bounds = self._compute_region_bounds(xs, generation)
        role_factors = self._get_region_role_factors()

        for role, pop in self.agent_populations.items():
            factor = role_factors.get(role, role_factors.get(role.value, 1.0))
            bounds = self._scale_bounds(base_bounds, factor)
            pop.bias_profile['region_bounds'] = bounds

    def _collect_region_candidates(self) -> List[Dict[str, Any]]:
        candidates = []
        if self.archives.get('feasible'):
            for item in self.archives['feasible']:
                candidates.append({
                    'x': item.get('x'),
                    'objectives': item.get('objectives'),
                    'violation': float(item.get('violation', 0.0)),
                })
        elif self.archives.get('boundary'):
            for item in self.archives['boundary']:
                candidates.append({
                    'x': item.get('x'),
                    'objectives': item.get('objectives'),
                    'violation': float(item.get('violation', 0.0)),
                })
        else:
            for pop in self.agent_populations.values():
                for i, individual in enumerate(pop.population):
                    if i >= len(pop.objectives):
                        continue
                    cons = pop.constraints[i] if pop.constraints else []
                    candidates.append({
                        'x': individual,
                        'objectives': pop.objectives[i],
                        'violation': self._total_violation(cons),
                    })

        if not candidates:
            return []

        feasible = [c for c in candidates if c['violation'] == 0.0]
        ranked = feasible if feasible else candidates
        penalty = float(self.config.get('region_violation_weight', 1000.0))
        ranked = sorted(
            ranked,
            key=lambda c: float(np.mean(c['objectives'])) + penalty * float(c['violation'])
        )
        return ranked

    def _compute_region_bounds(self, xs: np.ndarray, generation: int) -> np.ndarray:
        xs = np.asarray(xs, dtype=float)
        if xs.ndim == 1:
            xs = xs.reshape(1, -1)

        min_vals = np.min(xs, axis=0)
        max_vals = np.max(xs, axis=0)
        span = max_vals - min_vals

        global_span = self.var_bounds[:, 1] - self.var_bounds[:, 0]
        span = np.where(span > 0, span, global_span * 0.1)

        progress = generation / max(1, int(self.config.get('max_generations', 1)))
        base_expansion = float(self.config.get('region_expansion', 0.2))
        min_expansion = float(self.config.get('region_min_expansion', 0.05))
        expansion = min_expansion + (base_expansion - min_expansion) * (1.0 - progress)

        low = min_vals - span * expansion
        high = max_vals + span * expansion

        bounds = np.stack([low, high], axis=1)
        bounds[:, 0] = np.maximum(bounds[:, 0], self.var_bounds[:, 0])
        bounds[:, 1] = np.minimum(bounds[:, 1], self.var_bounds[:, 1])
        return bounds

    def _scale_bounds(self, bounds: np.ndarray, factor: float) -> np.ndarray:
        if factor is None:
            return bounds
        factor = max(0.1, float(factor))
        centers = (bounds[:, 0] + bounds[:, 1]) * 0.5
        half = (bounds[:, 1] - bounds[:, 0]) * 0.5 * factor
        scaled = np.stack([centers - half, centers + half], axis=1)
        scaled[:, 0] = np.maximum(scaled[:, 0], self.var_bounds[:, 0])
        scaled[:, 1] = np.minimum(scaled[:, 1], self.var_bounds[:, 1])
        return scaled

    def _get_region_role_factors(self) -> Dict:
        factors = self.config.get('region_role_factors')
        if isinstance(factors, dict):
            return factors
        return {
            AgentRole.EXPLORER: 1.4,
            AgentRole.EXPLOITER: 0.8,
            AgentRole.ADVISOR: 1.0,
            AgentRole.COORDINATOR: 1.1,
            AgentRole.WAITER: 1.2,
        }

