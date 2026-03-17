"""Case-local search adapters for production_scheduling."""

from __future__ import annotations

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from nsgablack.adapters import AlgorithmAdapter


@dataclass
class _GreedyConfig:
    max_active_machines_per_day: int
    min_machines_per_day: int
    min_production_per_machine: int
    max_production_per_machine: int


def _build_greedy_schedule(problem, *, rng: np.random.Generator, pheromone: Optional[np.ndarray] = None,
                           alpha: float = 1.0, beta: float = 1.0) -> np.ndarray:
    data = getattr(problem, "data", None)
    constraints = getattr(problem, "constraints", None)
    if data is None or constraints is None:
        raise RuntimeError("Greedy/ACO adapter requires problem.data and problem.constraints")

    machines = int(getattr(problem, "machines", data.machines))
    days = int(getattr(problem, "days", data.days))
    bom = np.asarray(data.bom_matrix, dtype=float)
    supply = np.asarray(data.supply_matrix, dtype=float)
    weights = np.asarray(getattr(problem, "machine_weights", np.ones(machines)), dtype=float)
    weights = np.clip(weights, 1e-6, None)

    cfg = _GreedyConfig(
        max_active_machines_per_day=int(constraints.max_machines_per_day),
        min_machines_per_day=int(constraints.min_machines_per_day),
        min_production_per_machine=int(constraints.min_production_per_machine),
        max_production_per_machine=int(constraints.max_production_per_machine),
    )

    schedule = np.zeros((machines, days), dtype=float)
    stock = np.zeros(supply.shape[0], dtype=float)
    req_indices = [np.where(bom[m] > 0.0)[0] for m in range(machines)]
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
            if len(active) >= cfg.max_active_machines_per_day:
                break
            req = req_indices[m]
            if req.size == 0:
                active.append(m)
                continue
            avail = float(np.min(stock[req]))
            if avail >= cfg.min_production_per_machine:
                active.append(m)
        if len(active) < cfg.min_machines_per_day:
            needed = cfg.min_machines_per_day - len(active)
            for m in order:
                if m in active:
                    continue
                active.append(m)
                if len(active) >= cfg.min_machines_per_day:
                    break
        for m in active:
            req = req_indices[m]
            if req.size == 0:
                upper = cfg.max_production_per_machine
            else:
                upper = min(cfg.max_production_per_machine, int(np.min(stock[req])))
            if upper <= 0:
                continue
            low = min(cfg.min_production_per_machine, upper)
            prod = float(upper) if upper >= low else 0.0
            schedule[m, day] = prod
            if req.size > 0 and prod > 0:
                stock[req] = np.maximum(0.0, stock[req] - prod)
    return schedule.reshape(-1)


class ProductionRandomSearchAdapter(AlgorithmAdapter):
    """Explorer: generate diverse feasible candidates via init+repair."""

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

    def propose(self, solver, context):
        out = []
        for _ in range(max(1, self.batch_size)):
            x = solver.init_candidate(context)
            x = solver.repair_candidate(x, context)
            out.append(x)
        return out


class ProductionLocalSearchAdapter(AlgorithmAdapter):
    """Exploiter: refine best solution via mutate+repair."""

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

    def propose(self, solver, context):
        base = solver.best_x
        out = []
        for _ in range(max(1, self.batch_size)):
            if base is None:
                x = solver.init_candidate(context)
            else:
                x = solver.mutate_candidate(base, context)
            x = solver.repair_candidate(x, context)
            out.append(x)
        return out


class ProductionGreedyBaselineAdapter(AlgorithmAdapter):
    """Baseline: greedy schedule construction (single candidate per step)."""

    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Builds a single greedy candidate; no context mutation.",)

    def __init__(self):
        super().__init__(name="production_greedy_baseline")
        self._rng = np.random.default_rng(42)

    def propose(self, solver, context):
        _ = context
        x = _build_greedy_schedule(solver.problem, rng=self._rng)
        x = solver.repair_candidate(x, context)
        return [x]


class ProductionACOBaselineAdapter(AlgorithmAdapter):
    """Baseline: light ACO-style scheduling over machine/day activation."""

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

    def _ensure_pheromone(self, solver):
        if self._pheromone is not None:
            return
        machines = int(getattr(solver.problem, "machines", 1))
        days = int(getattr(solver.problem, "days", 1))
        self._pheromone = np.ones((machines, days), dtype=float)

    def propose(self, solver, context):
        _ = context
        self._ensure_pheromone(solver)
        out = []
        for _ in range(max(1, self.ants)):
            x = _build_greedy_schedule(
                solver.problem,
                rng=self._rng,
                pheromone=self._pheromone,
                alpha=self.alpha,
                beta=self.beta,
            )
            x = solver.repair_candidate(x, context)
            out.append(x)
        return out

    def update(self, solver, candidates, objectives, violations, context):
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
        machines = int(getattr(solver.problem, "machines", 1))
        days = int(getattr(solver.problem, "days", 1))
        mat = best.reshape(machines, days)
        self._pheromone *= max(0.0, 1.0 - float(self.evaporation))
        deposit = float(self.q) / (1.0 + float(scores[best_idx]))
        self._pheromone += (mat > 0.0).astype(float) * deposit
