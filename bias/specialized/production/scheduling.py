"""
Production scheduling biases.

This module provides a lightweight, clean implementation of a few production
scheduling-oriented biases, suitable as a specialized example without extra
dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np

from ...core.base import OptimizationContext, DomainBias, AlgorithmicBias
from ...core.manager import UniversalBiasManager

try:
    from ...specialized.bayesian_biases import BayesianGuidanceBias, BayesianExplorationBias
except Exception:
    BayesianGuidanceBias = None
    BayesianExplorationBias = None


class ProductionSchedulingBiasManager:
    """
    Specialized bias manager for production scheduling.

    The manager bundles domain and algorithmic biases and exposes a single
    compute_bias() entry for integration.
    """

    def __init__(
        self,
        machine_bom: Dict[Any, List[Any]],
        inventory_data: Dict[Any, float],
        machine_ids: List[Any],
        days: int,
        max_machines_per_day: int = 8,
    ) -> None:
        self.machine_bom = machine_bom
        self.inventory_data = inventory_data
        self.machine_ids = machine_ids
        self.days = int(days)
        self.max_machines_per_day = int(max_machines_per_day)

        self.bias_manager = UniversalBiasManager()
        self._configure_bias_weights()
        self._setup_constraints()
        self._setup_algorithmic_bias()

    def _configure_bias_weights(self) -> None:
        try:
            self.bias_manager.set_bias_weights({"algorithmic": 0.5, "domain": 0.5})
        except Exception:
            self.bias_manager.bias_weights = {"algorithmic": 0.5, "domain": 0.5}

    def _setup_constraints(self) -> None:
        constraint_bias = ProductionConstraintBias(
            self.machine_bom,
            self.inventory_data,
            self.machine_ids,
            self.days,
            self.max_machines_per_day,
        )
        self.bias_manager.domain_manager.add_bias(constraint_bias)

    def _setup_algorithmic_bias(self) -> None:
        diversity_bias = ProductionDiversityBias(weight=0.15)
        self.bias_manager.algorithmic_manager.add_bias(diversity_bias)

        continuity_bias = ProductionContinuityBias(self.machine_ids, self.days, weight=0.25)
        self.bias_manager.algorithmic_manager.add_bias(continuity_bias)

        if BayesianGuidanceBias is not None:
            try:
                bayesian_guidance = BayesianGuidanceBias(weight=0.4)
                self.bias_manager.algorithmic_manager.add_bias(bayesian_guidance)
            except Exception:
                pass

        if BayesianExplorationBias is not None:
            try:
                bayesian_exploration = BayesianExplorationBias(weight=0.2)
                self.bias_manager.algorithmic_manager.add_bias(bayesian_exploration)
            except Exception:
                pass

    def compute_bias(self, x: np.ndarray, context: OptimizationContext) -> float:
        """Compute total bias for production scheduling."""
        return self.bias_manager.compute_total_bias(x, context)


class ProductionConstraintBias(DomainBias):
    """Hard/soft constraint bias for production scheduling plans."""
    context_requires = ("problem_data",)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads context fields: problem_data; outputs scalar bias only."



    def __init__(
        self,
        machine_bom: Dict[Any, List[Any]],
        inventory_data: Dict[Any, float],
        machine_ids: List[Any],
        days: int,
        max_machines_per_day: int = 8,
        weight: float = 1.0,
    ) -> None:
        super().__init__("production_constraints", weight)
        self.machine_bom = machine_bom
        self.inventory_data = inventory_data
        self.machine_ids = machine_ids
        self.num_machines = len(machine_ids)
        self.days = int(days)
        self.max_machines_per_day = int(max_machines_per_day)
        self._setup_material_info()

    def _setup_material_info(self) -> None:
        self.material_users: Dict[Any, List[int]] = {}
        self.active_materials: List[Any] = []
        active_set = set()
        for m_idx, m_id in enumerate(self.machine_ids):
            for mat in self.machine_bom.get(m_id, []):
                active_set.add(mat)
                self.material_users.setdefault(mat, []).append(m_idx)
        self.active_materials = list(active_set)

    def _decode_plan(self, x: np.ndarray) -> np.ndarray:
        plan = x.reshape((self.num_machines, self.days))
        return np.round(plan).astype(int)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        plan = self._decode_plan(x)

        # hard constraint: per-day active machines
        daily_active = (plan > 0).sum(axis=0)
        if np.any(daily_active > self.max_machines_per_day):
            return float(1e12)

        # hard constraint: material shortage
        if self._material_shortage(plan) > 0:
            return float(1e12)

        # soft constraints
        penalty = 0.0
        penalty += self._integer_penalty(x)
        penalty += 10.0 * self._smoothness_penalty(plan)
        penalty += 5.0 * self._batch_penalty(plan)
        return float(penalty)

    def _material_shortage(self, plan: np.ndarray) -> float:
        if not self.active_materials:
            return 0.0
        shortage = 0.0
        for mat in self.active_materials:
            demand = 0.0
            for m_idx in self.material_users.get(mat, []):
                demand += float(np.sum(plan[m_idx, :] > 0))
            avail = float(self.inventory_data.get(mat, 0.0))
            if demand > avail:
                shortage += demand - avail
        return shortage

    def _integer_penalty(self, x: np.ndarray) -> float:
        frac = np.abs(x - np.round(x))
        return float(np.mean(frac))

    def _smoothness_penalty(self, plan: np.ndarray) -> float:
        diffs = np.abs(np.diff(plan, axis=1))
        return float(np.mean(diffs))

    def _batch_penalty(self, plan: np.ndarray) -> float:
        # penalize single-day bursts per machine
        penalty = 0.0
        for row in plan:
            runs = np.diff(np.r_[0, row > 0, 0])
            starts = np.where(runs == 1)[0]
            ends = np.where(runs == -1)[0]
            lengths = ends - starts
            penalty += float(np.sum(lengths <= 1))
        return penalty / max(1, self.num_machines)


class ProductionDiversityBias(AlgorithmicBias):
    """Encourage diverse plans (avoid early convergence)."""
    context_requires = ()
    requires_metrics = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads context fields: metrics; outputs scalar bias only."



    def __init__(self, weight: float = 0.1) -> None:
        super().__init__("production_diversity", weight)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        # Higher variance -> lower penalty (encourage diversity)
        var = float(np.var(x))
        return -var


class ProductionContinuityBias(AlgorithmicBias):
    """Encourage contiguous production blocks to reduce switching."""
    context_requires = ()
    requires_metrics = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads context fields: metrics; outputs scalar bias only."



    def __init__(self, machine_ids: List[Any], days: int, weight: float = 0.2) -> None:
        super().__init__("production_continuity", weight)
        self.machine_ids = machine_ids
        self.days = int(days)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        num_machines = len(self.machine_ids)
        plan = x.reshape((num_machines, self.days))
        switches = np.sum(np.abs(np.diff(plan > 0, axis=1)))
        return float(switches)


@dataclass
class ProductionOptimizationContext(OptimizationContext):
    """Optional extended context for production scheduling."""

    machine_ids: Optional[List[Any]] = None
    days: Optional[int] = None


class ProductionSchedulingBias:
    """Thin wrapper compatible with older code paths."""
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "No explicit context dependency; outputs scalar bias only."



    def __init__(self, manager: ProductionSchedulingBiasManager) -> None:
        self.manager = manager

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        return self.manager.compute_bias(x, context)
