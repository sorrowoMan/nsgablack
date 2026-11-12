"""Inventory-aware construction and neighborhoods for the existing Problem.

The constructor and mutator make search decisions.  The repair only truncates
inadmissible quantities; a valid integer plan is a fixed point.  None of these
components evaluates a candidate or assigns a candidate identity.
"""
from __future__ import annotations

from collections.abc import Mapping
import copy
from dataclasses import dataclass
import hashlib

import numpy as np

from blackbase.representation import RepresentationCapabilities
from nsgablack.context_keys import KEY_MUTATION_SIGMA, KEY_PROBLEM, KEY_VNS_K
from nsgablack.representation import RepresentationPipeline


@dataclass(frozen=True)
class ScheduleGeometry:
    """Immutable business inputs used by the operators, independent of a Unit."""

    bom: np.ndarray
    supply: np.ndarray
    max_active: int
    min_active: int
    max_quantity: int
    min_quantity: int
    hard_min_active: bool = False
    hard_min_quantity: bool = False

    def __post_init__(self):
        bom = np.array(self.bom, dtype=bool, copy=True)
        supply = np.array(self.supply, dtype=float, copy=True)
        if (bom.ndim != 2 or supply.ndim != 2 or bom.shape[1] != supply.shape[0]
                or not np.all(np.isfinite(supply)) or np.any(supply < 0)):
            raise ValueError("schedule geometry requires finite nonnegative aligned BOM/supply")
        if self.max_active < 1 or self.max_quantity < 1:
            raise ValueError("schedule geometry requires positive active/quantity limits")
        bom.flags.writeable = supply.flags.writeable = False
        object.__setattr__(self, "bom", bom)
        object.__setattr__(self, "supply", supply)

    @classmethod
    def from_problem(cls, problem):
        constraints = problem.constraints
        return cls(problem.data.bom_matrix, problem.data.supply_matrix,
                   int(constraints.max_machines_per_day), int(constraints.min_machines_per_day),
                   int(constraints.max_production_per_machine), int(constraints.min_production_per_machine),
                   not bool(constraints.soft_min_machines), not bool(constraints.soft_min_production))

    @property
    def machines(self):
        return self.bom.shape[0]

    @property
    def days(self):
        return self.supply.shape[1]

    def identity(self):
        return {"bom_sha256": hashlib.sha256(self.bom.tobytes()).hexdigest(),
                "supply_sha256": hashlib.sha256(self.supply.tobytes()).hexdigest(),
                "shape": [self.machines, self.days], "max_active": self.max_active,
                "min_active": self.min_active, "max_quantity": self.max_quantity,
                "min_quantity": self.min_quantity, "hard_min_active": self.hard_min_active,
                "hard_min_quantity": self.hard_min_quantity}

    def array(self, candidate):
        value = np.array(candidate, dtype=float, copy=True)
        if value.size != self.machines * self.days or not np.all(np.isfinite(value)):
            raise ValueError("schedule candidate must have finite quantities and the existing Problem dimension")
        return value.reshape(self.machines, self.days)

    def balances(self, schedule):
        return np.cumsum(self.supply - self.bom.T @ schedule, axis=1)

    def capacity(self, balances, machine, day):
        required = self.bom[machine]
        if not np.any(required):
            return float(self.max_quantity)
        return max(0.0, float(np.min(balances[required, day:])))


class _Component:
    context_requires = ()
    context_optional = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    artifact_requires = ()
    artifact_provides = ()
    phase_in = ()
    phase_out = ()

    def __init__(self, geometry):
        self.geometry = geometry

    @classmethod
    def from_problem(cls, problem, **kwargs):
        return cls(ScheduleGeometry.from_problem(problem), **kwargs)

    def checkpoint_identity(self):
        return {"schema": "production_schedule.operator/v1", "component": type(self).__name__,
                "geometry": self.geometry.identity()}


class _RandomComponent(_Component):
    stateless = False
    state_recovery_level = "L1"
    state_recovery_notes = "Explicit operator-local PCG64 RNG; business input hashes are constructor identity."

    def __init__(self, geometry, *, seed=None):
        super().__init__(geometry)
        self.set_random_seed(seed)

    def set_random_seed(self, seed):
        self._rng = np.random.default_rng(seed)

    def get_state(self):
        return {"identity": self.checkpoint_identity(), "rng": copy.deepcopy(self._rng.bit_generator.state)}

    def set_state(self, state):
        if not isinstance(state, Mapping) or state.get("identity") != self.checkpoint_identity():
            raise ValueError("schedule operator state belongs to different business inputs")
        restored = np.random.default_rng()
        restored.bit_generator.state = copy.deepcopy(state["rng"])
        self._rng = restored


class MinimalScheduleRepair(_Component):
    """Only enforce candidate shape, integer quantities, daily slots and stock.

    Soft minimum activation/quantity preferences remain soft.  A repaired plan
    is returned as a new array and is unchanged by a second repair.
    """

    stateless = True
    representation_capabilities = RepresentationCapabilities(frozenset({"repair"}), repair_idempotent=True)
    context_notes = ("Read-only constructor inventory; no search, smoothing or soft-preference enforcement.",)

    def repair(self, candidate, context=None):
        del context
        g = self.geometry
        schedule = np.clip(np.floor(g.array(candidate)), 0, g.max_quantity)
        stock = np.zeros(g.supply.shape[0], dtype=float)
        for day in range(g.days):
            active = np.flatnonzero(schedule[:, day] > 0)
            if len(active) > g.max_active:
                drop = active[np.argsort(schedule[active, day], kind="stable")[:len(active) - g.max_active]]
                schedule[drop, day] = 0
            stock += g.supply[:, day]
            for machine in np.argsort(-schedule[:, day], kind="stable"):
                required = g.bom[machine]
                available = float(np.min(stock[required])) if np.any(required) else float(g.max_quantity)
                schedule[machine, day] = min(schedule[machine, day], max(0, int(np.floor(available + 1e-9))))
                if g.hard_min_quantity and schedule[machine, day] < g.min_quantity:
                    schedule[machine, day] = 0
                stock[required] -= schedule[machine, day]
        return schedule.reshape(-1)

    def validate(self, candidate, context=None):
        del context
        try:
            g = self.geometry
            schedule = g.array(candidate)
        except (TypeError, ValueError):
            return False
        if (np.any(schedule < 0) or np.any(schedule > g.max_quantity)
                or not np.array_equal(schedule, np.floor(schedule))
                or np.any(np.sum(schedule > 0, axis=0) > g.max_active)
                or np.min(g.balances(schedule)) < -1e-9):
            return False
        if g.hard_min_active and np.any(np.sum(schedule > 0, axis=0) < g.min_active):
            return False
        return not (g.hard_min_quantity and np.any((schedule > 0) & (schedule < g.min_quantity)))


class ScheduleNeighborhoodMutation(_RandomComponent):
    """Bounded inventory-aware moves over quantities, not independent genes."""

    representation_capabilities = RepresentationCapabilities(frozenset({"mutate"}))
    context_optional = (KEY_MUTATION_SIGMA, KEY_VNS_K)
    context_notes = ("Optionally reads VNS neighborhood depth and sigma; all writes are private proposal quantities.",)

    def __init__(self, geometry, *, seed=None, attempts=1):
        if type(attempts) is not int or not 1 <= attempts <= 8:
            raise ValueError("mutation attempts must be an integer in [1, 8]")
        self.attempts = attempts
        super().__init__(geometry, seed=seed)

    def checkpoint_identity(self):
        identity = super().checkpoint_identity()
        # Preserve existing checkpoint identity for the unchanged default.
        if self.attempts != 1:
            identity["mutation_attempts"] = self.attempts
        return identity

    def mutate(self, candidate, context=None):
        g = self.geometry
        schedule = g.array(candidate)
        # Incoming drafts can be infeasible after crossover; the control plane
        # will repair them.  Do not perform a second hidden repair here.
        if (np.any(schedule < 0) or np.any(np.sum(schedule > 0, axis=0) > g.max_active)
                or np.min(g.balances(schedule)) < -1e-9):
            return schedule.reshape(-1)
        context = context or {}
        depth = int(context.get(KEY_VNS_K, 0))
        sigma = float(context.get(KEY_MUTATION_SIGMA, 0.4))
        if depth < 0 or not np.isfinite(sigma) or sigma < 0:
            raise ValueError("schedule neighborhood requires nonnegative finite depth/sigma")
        count = min(8, 1 + depth)
        fraction = min(1.0, max(0.1, sigma))
        baseline = schedule.copy() if self.attempts > 1 else None
        for _attempt in range(self.attempts):
            for _ in range(count):
                mode = int(self._rng.choice(3, p=(0.55, 0.30, 0.15)))
                if mode == 0:
                    self._balance(schedule, fraction)
                elif mode == 1:
                    self._fill(schedule, fraction)
                else:
                    self._substitute(schedule, fraction)
            if baseline is None or not np.array_equal(schedule, baseline):
                break
        return schedule.reshape(-1)

    def _balance(self, schedule, fraction):
        g = self.geometry
        totals = schedule.sum(axis=0)
        low = np.argsort(totals, kind="stable")[:max(1, g.days // 3)]
        balance = g.balances(schedule)
        for target in self._rng.permutation(low):
            target = int(target)
            # Nearby earlier batches can be postponed even when all the largest
            # late-month batches depend on materials that have not arrived.
            distance = np.abs(np.arange(g.days) - target)
            priority = np.maximum(0.0, totals - totals[target]) / (1.0 + 0.05 * distance)
            priority *= self._rng.uniform(0.9, 1.1, g.days)
            for donor in np.argsort(-priority, kind="stable"):
                if totals[donor] <= totals[target] + 1:
                    continue
                active = np.flatnonzero(schedule[:, donor] > 0)
                self._rng.shuffle(active)
                if np.sum(schedule[:, target] > 0) < g.min_active:
                    active = active[np.argsort(schedule[active, target] > 0, kind="stable")]
                for machine in active:
                    if schedule[machine, target] <= 0 and np.sum(schedule[:, target] > 0) >= g.max_active:
                        continue
                    limit = min(schedule[machine, donor], g.max_quantity - schedule[machine, target],
                                (totals[donor] - totals[target]) * 0.5)
                    if target < donor and np.any(g.bom[machine]):
                        limit = min(limit, float(np.min(balance[g.bom[machine], target:donor])))
                    move = int(np.floor(max(0, limit) * fraction))
                    if move < 1 or (schedule[machine, target] == 0 and move < g.min_quantity):
                        continue
                    remainder = schedule[machine, donor] - move
                    if 0 < remainder < g.min_quantity:
                        move = int(max(0, schedule[machine, donor] - g.min_quantity))
                    if move < 1 or (schedule[machine, target] == 0 and move < g.min_quantity):
                        continue
                    schedule[machine, donor] -= move
                    schedule[machine, target] += move
                    return

    def _fill(self, schedule, fraction):
        g = self.geometry
        balance = g.balances(schedule)
        order = np.argsort(schedule.sum(axis=0), kind="stable")
        # A random low-production day keeps a batch from duplicating one move.
        day = int(self._rng.choice(order[:max(1, g.days // 2)]))
        machines = self._rng.permutation(g.machines)
        capacity = np.array([g.capacity(balance, machine, day) for machine in machines])
        machines = machines[np.argsort(-capacity, kind="stable")]
        if np.sum(schedule[:, day] > 0) < g.min_active:
            machines = machines[np.argsort(schedule[machines, day] > 0, kind="stable")]
        for machine in machines:
            if schedule[machine, day] == 0 and np.sum(schedule[:, day] > 0) >= g.max_active:
                continue
            limit = min(g.capacity(balance, int(machine), day), g.max_quantity - schedule[machine, day])
            amount = int(np.floor(limit * fraction))
            if amount < 1 or (schedule[machine, day] == 0 and amount < g.min_quantity):
                continue
            schedule[machine, day] += amount
            return

    def _coverage(self, schedule):
        """Construct a missing small lot if inventory or a safe transfer allows.

        This is an optional search move, not a minimum-activation repair rule.
        All transfer donors keep their own positive minimum lot.
        """
        g = self.geometry
        balance = g.balances(schedule)
        for target in self._rng.permutation(g.days):
            while np.sum(schedule[:, target] > 0) < min(g.min_active, g.max_active):
                changed = False
                for machine in self._rng.permutation(g.machines):
                    if schedule[machine, target] > 0:
                        continue
                    lot = max(1, g.min_quantity)
                    if g.capacity(balance, int(machine), int(target)) >= lot:
                        schedule[machine, target] = lot
                        balance[g.bom[machine], target:] -= lot
                        changed = True
                        break
                    donors = np.flatnonzero(schedule[machine] >= 2 * lot)
                    donors = donors[np.argsort(np.abs(donors - target), kind="stable")]
                    for donor in donors:
                        if donor == target:
                            continue
                        if target < donor and np.any(g.bom[machine]):
                            if np.min(balance[g.bom[machine], target:donor]) < lot:
                                continue
                        schedule[machine, target] = lot
                        schedule[machine, donor] -= lot
                        balance = g.balances(schedule)
                        changed = True
                        break
                    if changed:
                        break
                if not changed:
                    break

    def _substitute(self, schedule, fraction):
        g = self.geometry
        day = int(self._rng.integers(g.days))
        active = np.flatnonzero(schedule[:, day] > 0)
        if not len(active):
            return
        donor = int(self._rng.choice(active))
        old = schedule[donor, day]
        amount = int(max(g.min_quantity, old * fraction))
        amount = min(amount, int(old))
        remainder = old - amount
        if 0 < remainder < g.min_quantity:
            amount = int(old)
        schedule[donor, day] -= amount
        balance = g.balances(schedule)
        for machine in self._rng.permutation(g.machines):
            if machine == donor:
                continue
            if schedule[machine, day] == 0 and np.sum(schedule[:, day] > 0) >= g.max_active:
                continue
            capacity = min(g.capacity(balance, int(machine), day), g.max_quantity - schedule[machine, day])
            extra = int(min(capacity, max(amount, g.min_quantity)))
            if extra < amount or extra < g.min_quantity:
                continue
            schedule[machine, day] += extra
            return
        schedule[donor, day] = old


class ConstructiveScheduleInitializer(_RandomComponent):
    """Finite rolling-stock construction with varied throughput/level profiles."""

    representation_capabilities = RepresentationCapabilities(frozenset({"init"}))
    context_notes = ("Constructor-only inventory; candidates vary scarcity/continuity and daily target profiles.",)

    def init(self, context):
        return self.initialize(context[KEY_PROBLEM], context)

    def _monthly_target(self, costs):
        g = self.geometry
        stock = g.supply.sum(axis=1).copy()
        total = 0.0
        for _ in range(g.machines * 10):
            feasible = [(machine, float(np.min(stock[g.bom[machine]])) if np.any(g.bom[machine])
                         else float(g.max_quantity)) for machine in range(g.machines)]
            feasible = [(machine, capacity) for machine, capacity in feasible if capacity >= 1]
            if not feasible:
                break
            machine, capacity = min(feasible, key=lambda item: costs[item[0]] *
                                     float(self._rng.uniform(0.85, 1.15)))
            quantity = min(capacity, float(g.max_quantity), max(50.0, capacity * 0.5))
            total += quantity
            stock[g.bom[machine]] -= quantity
        return max(1.0, total / float(g.days))

    def initialize(self, problem, context=None):
        del problem, context
        g = self.geometry
        schedule = np.zeros((g.machines, g.days), dtype=float)
        stock = np.zeros(g.supply.shape[0], dtype=float)
        totals = g.supply.sum(axis=1)
        scarcity_cost = g.bom @ (1.0 / np.maximum(1.0, totals))
        scarcity_cost = np.maximum(scarcity_cost, 1e-12)
        target = self._monthly_target(scarcity_cost)
        profile = int(self._rng.integers(3))
        target *= (0.80, 1.0, 1.35)[profile]
        continuity = float(self._rng.uniform(0.1, 0.7))
        diversity = self._rng.uniform(0.75, 1.25, g.machines)
        seen = np.zeros(g.machines, dtype=bool)
        for day in range(g.days):
            stock += g.supply[:, day]
            available = np.array([float(np.min(stock[g.bom[machine]])) if np.any(g.bom[machine])
                                  else float(g.max_quantity) for machine in range(g.machines)])
            previous = schedule[:, day - 1] > 0 if day else np.zeros(g.machines, dtype=bool)
            preference = diversity / scarcity_cost * (1.0 + continuity * previous + 0.05 * ~seen)
            order = np.argsort(-preference, kind="stable")
            active = []
            # First allocate non-fragmentary lots to several feasible types.
            for machine in order:
                if len(active) >= g.max_active:
                    break
                required = g.bom[machine]
                cap = float(np.min(stock[required])) if np.any(required) else float(g.max_quantity)
                if cap < g.min_quantity:
                    continue
                quantity = min(float(g.min_quantity), float(g.max_quantity), cap)
                schedule[machine, day] = quantity
                stock[required] -= quantity
                active.append(int(machine))
            desired = target
            if profile == 2:
                desired = max(desired, min(2.0 * target, float(available.max())))
            # Last-day stock use is still bounded; avoids a giant cleanup spike.
            for machine in active:
                gap = max(0.0, desired - schedule[:, day].sum())
                if gap < 1:
                    break
                required = g.bom[machine]
                cap = float(np.min(stock[required])) if np.any(required) else float(g.max_quantity)
                extra = int(np.floor(min(cap, g.max_quantity - schedule[machine, day], gap)))
                schedule[machine, day] += extra
                stock[required] -= extra
            seen |= schedule[:, day] > 0
        # Search-side smoothing conserves total output and respects arrival
        # times. It is part of constructing this proposal, never repair.
        mover = ScheduleNeighborhoodMutation(g, seed=int(self._rng.integers(2**31)))
        for _ in range(g.days * 2):
            mover._balance(schedule, 1.0)
        mover._coverage(schedule)
        return schedule.reshape(-1)


def build_quality_pipeline(problem, args=None):
    """Assemble candidate operators without changing the Problem or its data."""
    geometry = ScheduleGeometry.from_problem(problem)
    return RepresentationPipeline(initializer=ConstructiveScheduleInitializer(geometry),
                                  mutator=ScheduleNeighborhoodMutation(geometry, attempts=getattr(args, "mutation_attempts", 1)),
                                  repair=MinimalScheduleRepair(geometry),
                                  random_seed=getattr(args, "seed", None))


__all__ = ["ScheduleGeometry", "MinimalScheduleRepair", "ScheduleNeighborhoodMutation",
           "ConstructiveScheduleInitializer", "build_quality_pipeline"]
