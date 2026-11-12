"""Case-local search adapters for production_scheduling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from nsgablack.adapters.candidate_proposer import CandidateProposerAdapter
from nsgablack.adapters.unit_backed import UnitBackedAdapter, UnitField
if "." in __package__:
    from ..pipeline.schedule_units import ScheduleUnitBuilder, schedule_parameters
else:  # Compatibility with the Case's existing flat CLI imports.
    from pipeline.schedule_units import ScheduleUnitBuilder, schedule_parameters
import copy


def _build_greedy_schedule(unit, *, rng: np.random.Generator, pheromone: Optional[np.ndarray] = None,
                           alpha: float = 1.0, beta: float = 1.0) -> np.ndarray:
    machines, days = unit.machines, unit.days
    bom, supply, weights = unit.bom, unit.supply, unit.weights
    cfg = unit.constraints
    schedule = np.zeros((machines, days), dtype=float)
    stock = np.zeros(supply.shape[0], dtype=float)
    req_indices = unit.required_materials
    for day in range(days):
        stock += supply[:, day]
        heuristic = weights.copy()
        if pheromone is not None:
            pher_day = np.asarray(pheromone[:, day], dtype=float)
            pher_day = np.clip(pher_day, 1e-6, None)
            heuristic = (pher_day ** float(alpha)) * (weights ** float(beta))
        order = np.argsort(heuristic)[::-1]
        active = []
        for m in order:
            if len(active) >= cfg["max_machines_per_day"]:
                break
            req = req_indices[m]
            if req.size == 0:
                active.append(m)
                continue
            avail = float(np.min(stock[req]))
            if avail >= cfg["min_production_per_machine"]:
                active.append(m)
        if len(active) < cfg["min_machines_per_day"]:
            needed = cfg["min_machines_per_day"] - len(active)
            for m in order:
                if m in active:
                    continue
                active.append(m)
                if len(active) >= cfg["min_machines_per_day"]:
                    break
        for m in active:
            req = req_indices[m]
            if req.size == 0:
                upper = cfg["max_production_per_machine"]
            else:
                upper = min(cfg["max_production_per_machine"], int(np.min(stock[req])))
            if upper <= 0:
                continue
            low = min(cfg["min_production_per_machine"], upper)
            prod = float(upper) if upper >= low else 0.0
            schedule[m, day] = prod
            if req.size > 0 and prod > 0:
                stock[req] = np.maximum(0.0, stock[req] - prod)
    return schedule.reshape(-1)


class ProductionRandomSearchAdapter(CandidateProposerAdapter):
    """Explorer: initialize drafts; the control plane owns proposal repair."""

    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Generates candidates via solver init/repair hooks; no direct context mutation.",
    )

    def __init__(self, *, batch_size: int = 32):
        super().__init__(name="production_random_search")
        self.batch_size = int(batch_size)

    def propose(self, control, context):
        out = []
        for _ in range(max(1, self.batch_size)):
            x = control.init_candidate(context)
            out.append(x)
        return self.build_candidate_units(out, context)

    def update(self, control, candidates, feedback, context):
        _ = (control, candidates, feedback, context)


class ProductionLocalSearchAdapter(CandidateProposerAdapter):
    """Exploiter: mutate drafts; the control plane owns proposal repair."""

    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Refines candidates via solver mutate/repair hooks; no direct context mutation.",
    )

    def __init__(self, *, batch_size: int = 16):
        super().__init__(name="production_local_search")
        self.batch_size = int(batch_size)

    def propose(self, control, context):
        base = control.best_x
        out = []
        for _ in range(max(1, self.batch_size)):
            if base is None:
                x = control.init_candidate(context)
            else:
                x = control.mutate_candidate(np.array(base, copy=True), context)
            out.append(x)
        return self.build_candidate_units(out, context)

    def update(self, control, candidates, feedback, context):
        _ = (control, candidates, feedback, context)


class ProductionGreedyBaselineAdapter(UnitBackedAdapter):
    """Baseline: greedy schedule construction (single candidate per step)."""
    accepts_proposal_replacement = True  # Schedule repair preserves the fixed geometry.
    unit_build_operations = ("initialize", "layout")

    unit_builder_type = ScheduleUnitBuilder
    unit_schema = ScheduleUnitBuilder.unit_type.schema
    state_recovery_level = "L1"
    state_recovery_notes = "Restores schedule geometry, pheromone and RNG through the Unit codec."

    def _ensure_schedule(self, control):
        unit = self.algorithm_unit
        if unit is None or not unit.machines:
            return self.rebuild_unit("layout", **schedule_parameters(control.problem))
        return unit

    def _get_algorithm_state(self):
        return {"rng_state": copy.deepcopy(self._rng.bit_generator.state)}

    def _set_algorithm_state(self, state):
        if state.get("rng_state") is not None:
            self._rng.bit_generator.state = copy.deepcopy(state["rng_state"])

    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Builds a single greedy candidate; no context mutation.",)

    def __init__(self):
        super().__init__(name="production_greedy_baseline")
        self._rng = np.random.default_rng(42)

    def propose(self, control, context):
        _ = context
        unit = self._ensure_schedule(control)
        x = _build_greedy_schedule(unit, rng=self._rng)
        return [x]

    def update(self, control, candidates, feedback, context):
        _ = (control, candidates, feedback, context)


class ProductionACOBaselineAdapter(UnitBackedAdapter):
    """Baseline: light ACO-style scheduling over machine/day activation."""
    accepts_proposal_replacement = True  # Pheromone is updated from the accepted schedule.
    unit_build_operations = ("initialize", "layout")

    unit_builder_type = ScheduleUnitBuilder
    unit_schema = ScheduleUnitBuilder.unit_type.schema
    state_recovery_level = "L1"
    state_recovery_notes = "Restores schedule geometry, pheromone and RNG through the Unit codec."

    def _ensure_schedule(self, control):
        unit = self.algorithm_unit
        if unit is None or not unit.machines:
            return self.rebuild_unit("layout", **schedule_parameters(control.problem))
        return unit

    def _get_algorithm_state(self):
        return {"rng_state": copy.deepcopy(self._rng.bit_generator.state)}

    def _set_algorithm_state(self, state):
        if state.get("rng_state") is not None:
            self._rng.bit_generator.state = copy.deepcopy(state["rng_state"])

    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("ACO-style candidate generation using internal pheromone; no context mutation.",)

    def __init__(
        self,
        *,
        ants: int = 48,
        evaporation: float = 0.2,
        alpha: float = 1.0,
        beta: float = 1.0,
        q: float = 1.0,
    ):
        super().__init__(name="production_aco_baseline")
        self.ants = int(ants)
        self.evaporation = float(evaporation)
        self.alpha = float(alpha)
        self.beta = float(beta)
        self.q = float(q)
        self._pheromone: Optional[np.ndarray] = None
        self._rng = np.random.default_rng(42)

    _pheromone = UnitField("pheromone")

    def _ensure_pheromone(self, control):
        return self._ensure_schedule(control)

    def propose(self, control, context):
        _ = context
        unit = self._ensure_pheromone(control)
        out = []
        for _ in range(max(1, self.ants)):
            x = _build_greedy_schedule(
                unit,
                rng=self._rng,
                pheromone=self._pheromone,
                alpha=self.alpha,
                beta=self.beta,
            )
            out.append(x)
        return out

    def update(self, control, candidates, feedback, context):
        objectives, violations = feedback
        _ = (violations, context)
        if self._pheromone is None or candidates is None or objectives is None:
            return
        objs = np.asarray(objectives, dtype=float)
        if objs.ndim == 1:
            scores = objs
        else:
            scores = np.sum(objs, axis=1)
        best_idx = int(np.argmin(scores))
        best = np.asarray(candidates[best_idx], dtype=float).reshape(-1)
        machines = int(getattr(control.problem, "machines", 1))
        days = int(getattr(control.problem, "days", 1))
        mat = best.reshape(machines, days)
        self._pheromone *= max(0.0, 1.0 - float(self.evaporation))
        deposit = float(self.q) / (1.0 + float(scores[best_idx]))
        self._pheromone += (mat > 0.0).astype(float) * deposit
