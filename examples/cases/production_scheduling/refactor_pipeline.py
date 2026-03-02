# -*- coding: utf-8 -*-
"""Representation pipeline pieces for production scheduling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import sys
from pathlib import Path

import numpy as np

def _ensure_importable() -> None:
    try:
        import nsgablack  # noqa: F401
        return
    except ImportError:
        pass
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


_ensure_importable()

from nsgablack.representation import RepresentationPipeline

try:
    from nsgablack.utils.context.context_keys import KEY_MUTATION_SIGMA, KEY_VNS_K
except (ImportError, AttributeError):
    KEY_MUTATION_SIGMA = "mutation_sigma"
    KEY_VNS_K = "vns_k"


@dataclass
class ProductionScheduleInitializer:
    machines: int
    days: int
    min_machines_per_day: int
    max_machines_per_day: int
    min_production_per_machine: int
    max_production_per_machine: int
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Uses constructor constraints/data only; no context I/O.",)

    def initialize(self, problem, context=None) -> np.ndarray:
        schedule = np.zeros((self.machines, self.days), dtype=float)
        for day in range(self.days):
            if self.max_machines_per_day <= 0:
                continue
            lower = max(0, self.min_machines_per_day)
            upper = max(lower, self.max_machines_per_day)
            active_count = int(np.random.randint(lower, upper + 1))
            if active_count == 0:
                continue
            active_idx = np.random.choice(self.machines, size=active_count, replace=False)
            production = np.random.randint(
                self.min_production_per_machine,
                self.max_production_per_machine + 1,
                size=active_count,
            )
            schedule[active_idx, day] = production
        return schedule.reshape(-1)


@dataclass
class SupplyAwareInitializer:
    machines: int
    days: int
    min_machines_per_day: int
    max_machines_per_day: int
    min_production_per_machine: int
    max_production_per_machine: int
    bom_matrix: np.ndarray
    supply_matrix: np.ndarray
    machine_weights: Optional[np.ndarray] = None
    soft_min_ratio: float = 0.2
    min_prod_ratio: float = 0.02
    min_prod_abs: int = 100
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Supply-aware initializer reads constructor matrices; no context I/O.",)

    def initialize(self, problem, context=None) -> np.ndarray:
        schedule = np.zeros((self.machines, self.days), dtype=float)
        current_stock = np.zeros(self.supply_matrix.shape[0], dtype=float)
        req_indices = [np.where(self.bom_matrix[m])[0] for m in range(self.machines)]
        base_soft_min = max(1, int(self.min_production_per_machine * self.soft_min_ratio))
        weight_vec = (
            np.asarray(self.machine_weights, dtype=float)
            if self.machine_weights is not None and len(self.machine_weights) == self.machines
            else np.ones(self.machines, dtype=float)
        )
        weight_vec = np.clip(weight_vec, 0.05, None)
        weight_norm = weight_vec / max(np.max(weight_vec), 1e-6)
        prev_active = np.zeros(self.machines, dtype=bool)

        for day in range(self.days):
            current_stock += self.supply_matrix[:, day]

            probs = weight_vec / np.sum(weight_vec)
            machine_order = np.random.choice(self.machines, size=self.machines, replace=False, p=probs)
            soft_min = base_soft_min
            chosen = []
            availability = {}

            while True:
                feasible = []
                availability.clear()
                for m in machine_order:
                    req = req_indices[m]
                    if req.size == 0:
                        feasible.append(m)
                        availability[m] = float(self.max_production_per_machine)
                        continue
                    avail = float(np.min(current_stock[req]))
                    if avail >= soft_min:
                        feasible.append(m)
                        availability[m] = avail

                lower = max(0, self.min_machines_per_day)
                upper = max(lower, min(self.max_machines_per_day, len(feasible)))
                target = upper

                feasible.sort(
                    key=lambda idx: availability.get(idx, 0.0) * (0.5 + weight_norm[idx]),
                    reverse=True,
                )
                chosen = []
                for m in feasible:
                    if m in chosen:
                        continue
                    if prev_active[m]:
                        chosen.append(m)
                    if len(chosen) >= target:
                        break
                if len(chosen) < target:
                    for m in feasible:
                        if m in chosen:
                            continue
                        chosen.append(m)
                        if len(chosen) >= target:
                            break

                if len(chosen) >= lower or soft_min <= 1:
                    break
                soft_min = max(1, soft_min // 2)

            if not chosen:
                continue

            for m in chosen:
                req = req_indices[m]
                if req.size == 0:
                    avail = float(self.max_production_per_machine)
                else:
                    avail = float(np.min(current_stock[req]))
                if avail < soft_min:
                    continue
                upper_prod = min(self.max_production_per_machine, int(avail))
                if upper_prod <= 0:
                    continue
                low = min(self.min_production_per_machine, upper_prod)
                low = max(1, low)
                production = int(np.random.randint(low, upper_prod + 1))
                schedule[m, day] = production
                if req.size > 0:
                    current_stock[req] = np.maximum(0.0, current_stock[req] - production)

            # dynamic minimum production threshold
            day_total = float(np.sum(schedule[:, day]))
            threshold = max(self.min_prod_abs, self.min_prod_ratio * day_total)
            if threshold > 0:
                for m in list(chosen):
                    if schedule[m, day] < threshold:
                        prod = schedule[m, day]
                        schedule[m, day] = 0.0
                        req = req_indices[m]
                        if req.size > 0 and prod > 0:
                            current_stock[req] = current_stock[req] + prod

            prev_active = schedule[:, day] > 0

        return schedule.reshape(-1)


@dataclass
class ProductionScheduleMutation:
    sigma: float = 0.5
    per_gene_rate: float = 0.05
    toggle_rate: float = 0.02
    max_production_per_machine: int = 3000

    # VNS compatibility contract: VNSAdapter writes these keys into context.
    sigma_key: str = KEY_MUTATION_SIGMA
    k_key: str = KEY_VNS_K

    # Neighborhood-depth scaling (k -> stronger perturbation).
    k_sigma_scale: float = 0.18
    k_rate_scale: float = 0.12
    min_per_gene_rate: float = 0.01
    max_per_gene_rate: float = 0.35
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Optionally reads mutation_sigma/vns_k from context when provided.",
    )

    def _runtime_params(self, context=None) -> tuple[float, float]:
        sigma = float(self.sigma)
        per_gene_rate = float(self.per_gene_rate)
        if isinstance(context, dict):
            raw_sigma = context.get(self.sigma_key)
            if raw_sigma is not None:
                try:
                    sigma = max(1e-9, float(raw_sigma))
                except (TypeError, ValueError):
                    pass

            raw_k = context.get(self.k_key)
            if raw_k is not None:
                try:
                    k = max(0, int(raw_k))
                    sigma *= 1.0 + float(self.k_sigma_scale) * float(k)
                    per_gene_rate *= 1.0 + float(self.k_rate_scale) * float(k)
                except (TypeError, ValueError):
                    pass

        per_gene_rate = float(np.clip(per_gene_rate, self.min_per_gene_rate, self.max_per_gene_rate))
        return sigma, per_gene_rate

    def mutate(self, x: np.ndarray, context=None) -> np.ndarray:
        vec = np.array(x, dtype=float, copy=True)
        if vec.size == 0:
            return vec

        sigma, per_gene_rate = self._runtime_params(context)

        mask = np.random.rand(vec.size) < per_gene_rate
        if np.any(mask):
            vec[mask] += np.random.normal(0.0, sigma, size=int(np.sum(mask)))

        if self.toggle_rate > 0:
            toggle_mask = np.random.rand(vec.size) < self.toggle_rate
            if np.any(toggle_mask):
                toggles = np.random.randint(0, self.max_production_per_machine + 1, size=int(np.sum(toggle_mask)))
                vec[toggle_mask] = toggles

        vec = np.clip(np.floor(vec), 0, self.max_production_per_machine).astype(float)
        return vec


@dataclass
class ProductionScheduleRepair:
    machines: int
    days: int
    min_machines_per_day: int
    max_machines_per_day: int
    min_production_per_machine: int
    max_production_per_machine: int
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Hard-constraint repair over machine/day production matrix; no context I/O.",)

    def repair(self, x: np.ndarray, context=None) -> np.ndarray:
        schedule = np.array(x, dtype=float, copy=True).reshape(self.machines, self.days)
        schedule = np.clip(schedule, 0, self.max_production_per_machine)

        for day in range(self.days):
            day_values = schedule[:, day]
            active_mask = day_values > 0
            active_count = int(np.sum(active_mask))

            if active_count > self.max_machines_per_day:
                active_idx = np.where(active_mask)[0]
                order = active_idx[np.argsort(day_values[active_idx])]
                drop = order[: active_count - self.max_machines_per_day]
                schedule[drop, day] = 0.0

            if self.min_machines_per_day > 0:
                active_mask = schedule[:, day] > 0
                active_count = int(np.sum(active_mask))
                if active_count < self.min_machines_per_day:
                    inactive_idx = np.where(~active_mask)[0]
                    need = min(len(inactive_idx), self.min_machines_per_day - active_count)
                    if need > 0:
                        chosen = np.random.choice(inactive_idx, size=need, replace=False)
                        schedule[chosen, day] = float(self.min_production_per_machine)

            low_mask = (schedule[:, day] > 0) & (schedule[:, day] < self.min_production_per_machine)
            schedule[low_mask, day] = 0.0

        schedule = np.clip(schedule, 0, self.max_production_per_machine)
        return schedule.reshape(-1)


@dataclass
class SupplyAwareScheduleRepair:
    machines: int
    days: int
    min_production_per_machine: int
    bom_matrix: np.ndarray
    supply_matrix: np.ndarray
    base_repair: ProductionScheduleRepair
    machine_weights: Optional[np.ndarray] = None
    soft_min_ratio: float = 0.2
    continuity_bonus: float = 600.0
    weight_bonus: float = 200.0
    coverage_bonus: float = 300.0
    weight_mix: float = 0.6
    min_prod_ratio: float = 0.02
    min_prod_abs: int = 100
    material_cap_ratio: float = 1.2
    daily_floor_ratio: float = 0.6
    donor_keep_ratio: float = 0.7
    daily_cap_ratio: float = 1.3
    reserve_ratio: float = 0.6
    budget_mode: str = "today"
    backfill_window: int = 0
    smooth_strength: float = 0.6
    smooth_passes: int = 2
    coverage_passes: int = 2
    fragment_passes: int = 2
    continuity_swap: bool = True
    enforce_material_feasible: bool = True
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Supply/BOM-aware hard repair uses constructor matrices; no context I/O.",)

    def _prune_fragments(self, schedule: np.ndarray) -> np.ndarray:
        passes = max(1, int(self.fragment_passes))
        for _ in range(passes):
            changed = False
            for day in range(self.days):
                before = schedule[:, day].copy()
                active_before = before > 0
                active_count_before = int(np.sum(active_before))
                if active_count_before <= 1:
                    continue

                day_total = float(np.sum(before))
                if day_total <= 1e-9:
                    continue
                threshold = max(float(self.min_prod_abs), self.min_prod_ratio * day_total)
                if day_total < float(self.min_prod_abs):
                    threshold = max(1.0, self.min_prod_ratio * day_total)
                if threshold <= 0:
                    continue
                mask = (schedule[:, day] > 0) & (schedule[:, day] < threshold)
                if np.any(mask):
                    schedule[mask, day] = 0.0
                    active_after = int(np.sum(schedule[:, day] > 0))
                    min_keep = max(1, min(int(self.base_repair.min_machines_per_day), active_count_before))
                    if active_after < min_keep:
                        # Keep the largest productions to avoid empty/too-sparse days.
                        keep_idx = np.argsort(before)[-min_keep:]
                        schedule[:, day] = 0.0
                        schedule[keep_idx, day] = before[keep_idx]
                    changed = True
            if not changed:
                break
        return schedule

    def _balance_forward(self, schedule: np.ndarray, weight_norm: np.ndarray) -> np.ndarray:
        max_machines = int(self.base_repair.max_machines_per_day)
        if max_machines <= 0:
            return schedule
        min_shift = max(1.0, float(max(self.min_prod_abs, self.min_production_per_machine)))
        donor_floor = max(1, int(self.base_repair.min_machines_per_day))
        passes = max(1, int(self.smooth_passes))
        for _ in range(passes):
            daily_totals = np.sum(schedule, axis=0).astype(float)
            target_total = float(np.mean(daily_totals))
            if target_total < min_shift:
                target_total = min_shift
            baseline_totals = daily_totals.copy()
            for day in range(1, self.days):
                active = schedule[:, day] > 0
                active_count = int(np.sum(active))
                if active_count >= max_machines and daily_totals[day] >= target_total:
                    continue
                lookback = self.backfill_window
                if lookback <= 0:
                    start_day = 0
                else:
                    start_day = max(0, day - lookback)
                needed_total = max(0.0, target_total - daily_totals[day])
                if self.smooth_strength > 0 and day > 0:
                    adj_gap = daily_totals[day - 1] - daily_totals[day]
                    if adj_gap > 0:
                        needed_total = max(needed_total, adj_gap * float(self.smooth_strength))
                missing = max(0, max_machines - active_count)
                if missing > 0:
                    needed_total = max(needed_total, min_shift * float(missing))
                per_new_target = max(min_shift, needed_total / max(1, missing)) if missing > 0 else min_shift
                for donor_day in range(day - 1, start_day - 1, -1):
                    if active_count >= max_machines and needed_total <= 1e-6:
                        break
                    donor_active = schedule[:, donor_day] > 0
                    donor_count = int(np.sum(donor_active))
                    if donor_count <= 0:
                        continue
                    can_expand = schedule[:, day] < (self.base_repair.max_production_per_machine - 1e-6)
                    candidates = np.where(donor_active & can_expand)[0]
                    if candidates.size == 0:
                        continue
                    if active_count < max_machines:
                        inactive_first = []
                        active_first = []
                        for m in candidates:
                            if schedule[m, day] <= 1e-12:
                                inactive_first.append(m)
                            else:
                                active_first.append(m)
                        inactive_first = sorted(
                            inactive_first,
                            key=lambda m: (schedule[m, donor_day], weight_norm[m]),
                            reverse=True,
                        )
                        active_first = sorted(
                            active_first,
                            key=lambda m: (schedule[m, donor_day], weight_norm[m]),
                            reverse=True,
                        )
                        candidates = inactive_first + active_first
                    else:
                        candidates = sorted(
                            candidates,
                            key=lambda m: (schedule[m, donor_day], weight_norm[m]),
                            reverse=True,
                        )
                    donor_floor_total = max(
                        float(self.min_prod_abs),
                        float(target_total) * max(0.1, float(self.daily_floor_ratio)),
                        float(baseline_totals[donor_day]) * float(self.donor_keep_ratio),
                    )
                    donor_surplus = max(0.0, daily_totals[donor_day] - donor_floor_total)
                    for m in candidates:
                        if active_count >= max_machines and needed_total <= 1e-6:
                            break
                        if schedule[m, day] <= 1e-12 and active_count >= max_machines:
                            continue
                        donor_prod = schedule[m, donor_day]
                        if donor_prod <= 0:
                            continue
                        extra_cap = float(self.base_repair.max_production_per_machine) - schedule[m, day]
                        if extra_cap <= 0:
                            continue
                        if donor_surplus > 1e-6:
                            target_move = max(needed_total, min_shift)
                            if schedule[m, day] <= 1e-12 and active_count < max_machines:
                                target_move = max(per_new_target, min_shift)
                            move = min(donor_prod, extra_cap, donor_surplus, target_move)
                        else:
                            if active_count >= max_machines:
                                continue
                            move = min(donor_prod, extra_cap, per_new_target)
                        if move <= 1e-6:
                            continue
                        if donor_count <= donor_floor and donor_prod - move <= 1e-6:
                            continue
                        schedule[m, donor_day] -= move
                        schedule[m, day] += move
                        if schedule[m, donor_day] <= 1e-6:
                            schedule[m, donor_day] = 0.0
                            donor_count -= 1
                        if schedule[m, day] > 0 and not active[m]:
                            active[m] = True
                            active_count += 1
                            missing = max(0, max_machines - active_count)
                            per_new_target = max(min_shift, needed_total / max(1, missing)) if missing > 0 else min_shift
                        daily_totals[donor_day] -= move
                        daily_totals[day] += move
                        donor_surplus = max(0.0, donor_surplus - move)
                        if needed_total > 0:
                            needed_total = max(0.0, needed_total - move)
        return schedule

    def _backfill_coverage(self, schedule: np.ndarray, weight_norm: np.ndarray) -> np.ndarray:
        max_machines = int(self.base_repair.max_machines_per_day)
        if max_machines <= 0 or self.days <= 1:
            return schedule

        day_totals = np.sum(schedule, axis=0).astype(float)
        target_total = max(float(self.min_prod_abs), float(np.mean(day_totals)))
        baseline_totals = day_totals.copy()

        def _threshold_from_total(total: float) -> float:
            threshold = max(float(self.min_prod_abs), self.min_prod_ratio * total)
            if total < float(self.min_prod_abs):
                threshold = max(1.0, self.min_prod_ratio * total)
            return float(threshold)

        for day in range(1, self.days):
            active_mask = schedule[:, day] > 0
            active_count = int(np.sum(active_mask))
            if active_count >= max_machines:
                continue
            missing = max_machines - active_count
            base_threshold = _threshold_from_total(float(day_totals[day]))
            needed_total = max(0.0, target_total - float(day_totals[day]))
            base_target_min = max(1.0, base_threshold)
            if missing > 0 and needed_total > 0:
                base_target_min = max(base_target_min, needed_total / float(missing))
            prev_active = schedule[:, day - 1] > 0
            candidates = [int(m) for m in np.where(prev_active & ~active_mask)[0]]
            for m in np.where(~active_mask)[0]:
                if int(m) not in candidates:
                    candidates.append(int(m))
            candidates = sorted(candidates, key=lambda m: weight_norm[m], reverse=True)
            if self.backfill_window > 0:
                start_day = max(0, day - int(self.backfill_window))
            else:
                start_day = 0
            for m in candidates:
                if missing <= 0:
                    break
                donor_days = list(range(day - 1, start_day - 1, -1))
                donor_days.sort(key=lambda d: schedule[m, d], reverse=True)
                for donor_day in donor_days:
                    donor_prod = float(schedule[m, donor_day])
                    if donor_prod <= 0:
                        continue
                    donor_threshold = _threshold_from_total(float(day_totals[donor_day]))
                    movable = donor_prod - donor_threshold
                    if movable <= 1e-6:
                        continue
                    donor_active = int(np.sum(schedule[:, donor_day] > 0))
                    donor_avg = float(day_totals[donor_day]) / float(max(1, donor_active))
                    global_avg = float(target_total) / float(max(1, max_machines))
                    needed_per_machine = needed_total / float(max(1, missing))
                    dynamic_target = max(
                        base_target_min,
                        needed_per_machine,
                        global_avg,
                        donor_avg * 0.6,
                        donor_prod * 0.4,
                    )
                    move = min(movable, dynamic_target)
                    donor_floor_total = max(
                        float(self.min_prod_abs),
                        float(target_total) * max(0.1, float(self.daily_floor_ratio)),
                        float(baseline_totals[donor_day]) * float(self.donor_keep_ratio),
                    )
                    max_by_day = max(0.0, float(day_totals[donor_day]) - donor_floor_total)
                    if max_by_day <= 1e-6:
                        continue
                    if move > max_by_day:
                        move = max_by_day
                    if move <= 1e-6:
                        continue
                    schedule[m, donor_day] -= move
                    schedule[m, day] += move
                    day_totals[donor_day] = max(0.0, float(day_totals[donor_day]) - move)
                    day_totals[day] = float(day_totals[day]) + move
                    active_mask[m] = True
                    missing -= 1
                    base_threshold = _threshold_from_total(float(day_totals[day]))
                    needed_total = max(0.0, target_total - float(day_totals[day]))
                    base_target_min = max(1.0, base_threshold)
                    if missing > 0 and needed_total > 0:
                        base_target_min = max(base_target_min, needed_total / float(missing))
                    break

            # Top-up low-production machines even if already active.
            needed_total = max(0.0, target_total - float(day_totals[day]))
            base_threshold = _threshold_from_total(float(day_totals[day]))
            target_min = max(1.0, base_threshold)
            if needed_total > 0:
                target_min = max(target_min, needed_total / float(max_machines))
            low_machines = np.where((schedule[:, day] > 0) & (schedule[:, day] < target_min))[0]
            low_machines = sorted(low_machines, key=lambda m: schedule[m, day])
            for m in low_machines:
                need = target_min - float(schedule[m, day])
                if need <= 1e-6:
                    continue
                donor_days = list(range(day - 1, start_day - 1, -1))
                donor_days.sort(key=lambda d: (schedule[m, d], d), reverse=True)
                for donor_day in donor_days:
                    donor_prod = float(schedule[m, donor_day])
                    if donor_prod <= 0:
                        continue
                    donor_threshold = _threshold_from_total(float(day_totals[donor_day]))
                    movable = donor_prod - donor_threshold
                    if movable <= 1e-6:
                        continue
                    move = min(movable, need)
                    donor_floor_total = max(
                        float(self.min_prod_abs),
                        float(target_total) * max(0.1, float(self.daily_floor_ratio)),
                        float(baseline_totals[donor_day]) * float(self.donor_keep_ratio),
                    )
                    max_by_day = max(0.0, float(day_totals[donor_day]) - donor_floor_total)
                    if max_by_day <= 1e-6:
                        continue
                    if move > max_by_day:
                        move = max_by_day
                    if move <= 1e-6:
                        continue
                    schedule[m, donor_day] -= move
                    schedule[m, day] += move
                    day_totals[donor_day] = max(0.0, float(day_totals[donor_day]) - move)
                    day_totals[day] = float(day_totals[day]) + move
                    need -= move
                    if need <= 1e-6:
                        break
        return schedule

    def _continuity_swap(self, schedule: np.ndarray, weight_norm: np.ndarray) -> np.ndarray:
        if not self.continuity_swap or self.days <= 1:
            return schedule
        min_shift = max(1.0, float(max(self.min_prod_abs, self.min_production_per_machine)))
        req_indices = [np.where(self.bom_matrix[m])[0] for m in range(self.machines)]
        current_stock = np.zeros(self.supply_matrix.shape[0], dtype=float)
        deferred = []
        max_machines = int(self.base_repair.max_machines_per_day)
        max_per_machine = float(self.base_repair.max_production_per_machine)

        for day in range(self.days):
            current_stock += self.supply_matrix[:, day]
            day_prod = schedule[:, day].copy()
            day_usage = day_prod @ self.bom_matrix.astype(float)
            available = np.maximum(0.0, current_stock - day_usage)

            if day > 0:
                prev_active = schedule[:, day - 1] > 0
                new_idx = np.where((day_prod > 0) & (~prev_active))[0]
                missing_idx = np.where(prev_active & (day_prod <= 0))[0]
                if new_idx.size > 0 and missing_idx.size > 0:
                    missing_order = sorted(
                        missing_idx,
                        key=lambda m: (schedule[m, day - 1], weight_norm[m]),
                        reverse=True,
                    )
                    new_order = sorted(
                        new_idx,
                        key=lambda m: (weight_norm[m], day_prod[m]),
                    )
                    for i in missing_order:
                        if not new_order:
                            break
                        req_i = req_indices[i]
                        for j in list(new_order):
                            prod_j = day_prod[j]
                            if prod_j < min_shift:
                                continue
                            req_j = req_indices[j]
                            if req_i.size > 0:
                                avail_after = available.copy()
                                if req_j.size > 0:
                                    avail_after[req_j] += prod_j
                                if np.any(avail_after[req_i] < prod_j - 1e-6):
                                    continue
                            day_prod[j] = 0.0
                            day_prod[i] = prod_j
                            if req_j.size > 0:
                                available[req_j] += prod_j
                            if req_i.size > 0:
                                available[req_i] -= prod_j
                            deferred.append([int(j), float(prod_j), day + 1])
                            new_order.remove(j)
                            break

            if deferred:
                active_mask = day_prod > 0
                active_count = int(np.sum(active_mask))
                deferred.sort(key=lambda item: (item[2], -weight_norm[item[0]]))
                remaining = []
                for m, qty, earliest in deferred:
                    if day < earliest:
                        remaining.append([m, qty, earliest])
                        continue
                    cap = max_per_machine - day_prod[m]
                    if cap <= 1e-6:
                        remaining.append([m, qty, earliest])
                        continue
                    if day_prod[m] <= 0 and active_count >= max_machines:
                        remaining.append([m, qty, earliest])
                        continue
                    req = req_indices[m]
                    max_feasible = cap if req.size == 0 else float(np.min(available[req]))
                    add = min(cap, max_feasible, qty)
                    if add < min_shift:
                        remaining.append([m, qty, earliest])
                        continue
                    day_prod[m] += add
                    if req.size > 0:
                        available[req] -= add
                    if day_prod[m] > 0 and not active_mask[m]:
                        active_mask[m] = True
                        active_count += 1
                    leftover = qty - add
                    if leftover > 1e-6:
                        remaining.append([m, leftover, day + 1])
                deferred = remaining

            schedule[:, day] = day_prod
            day_usage = day_prod @ self.bom_matrix.astype(float)
            current_stock = np.maximum(0.0, current_stock - day_usage)

        return schedule

    def _enforce_material_feasibility(self, schedule: np.ndarray, weight_norm: np.ndarray) -> np.ndarray:
        if not self.enforce_material_feasible:
            return schedule
        current_stock = np.zeros(self.supply_matrix.shape[0], dtype=float)
        req_indices = [np.where(self.bom_matrix[m])[0] for m in range(self.machines)]
        prev_active = np.zeros(self.machines, dtype=bool)
        max_per_machine = float(self.base_repair.max_production_per_machine)

        for day in range(self.days):
            current_stock += self.supply_matrix[:, day]
            day_prod = schedule[:, day].copy()
            if np.sum(day_prod) <= 1e-6:
                prev_active = day_prod > 0
                continue

            priority = day_prod.copy()
            priority += self.weight_bonus * weight_norm
            priority[prev_active] += self.continuity_bonus
            order = np.argsort(priority)[::-1]

            reserve = np.zeros_like(current_stock)
            if self.reserve_ratio > 0 and day < self.days - 1:
                future_total = np.sum(schedule[:, day + 1 :], axis=1)
                future_requirements = future_total @ self.bom_matrix.astype(float)
                reserve_target = future_requirements * float(self.reserve_ratio)
                reserve_cap = current_stock * float(self.reserve_ratio)
                reserve = np.minimum(reserve_target, reserve_cap)
            # Lock part of the stock for future scheduled production.
            remaining = np.maximum(0.0, current_stock - reserve)
            for m in order:
                prod = day_prod[m]
                if prod <= 1e-12:
                    continue
                req = req_indices[m]
                if req.size == 0:
                    feasible = max_per_machine
                else:
                    feasible = float(np.min(remaining[req]))
                if feasible <= 1e-12:
                    day_prod[m] = 0.0
                    continue
                new_prod = min(prod, feasible, max_per_machine)
                if new_prod <= 1e-12:
                    day_prod[m] = 0.0
                    continue
                day_prod[m] = new_prod
                if req.size > 0:
                    remaining[req] = np.maximum(0.0, remaining[req] - new_prod)

            schedule[:, day] = day_prod
            consumption = day_prod @ self.bom_matrix.astype(float)
            current_stock = np.maximum(0.0, current_stock - consumption)
            prev_active = day_prod > 0

        return schedule

    def repair(self, x: np.ndarray, context=None) -> np.ndarray:
        schedule_pref = np.array(x, dtype=float, copy=True).reshape(self.machines, self.days)
        schedule_pref = np.clip(schedule_pref, 0, self.base_repair.max_production_per_machine)
        schedule = np.zeros_like(schedule_pref)

        current_stock = np.zeros(self.supply_matrix.shape[0], dtype=float)
        req_indices = [np.where(self.bom_matrix[m])[0] for m in range(self.machines)]
        base_soft_min = max(1, int(self.min_production_per_machine * self.soft_min_ratio))
        weight_vec = (
            np.asarray(self.machine_weights, dtype=float)
            if self.machine_weights is not None and len(self.machine_weights) == self.machines
            else np.ones(self.machines, dtype=float)
        )
        weight_vec = np.clip(weight_vec, 0.05, None)
        weight_norm = weight_vec / max(np.max(weight_vec), 1e-6)
        avg_materials = float(np.sum(self.bom_matrix)) / float(max(1, self.machines))
        avg_materials = max(1e-6, avg_materials)
        prev_active = np.zeros(self.machines, dtype=bool)
        produced_any = np.zeros(self.machines, dtype=bool)
        for day in range(self.days):
            prev_day_active = prev_active.copy()
            current_stock += self.supply_matrix[:, day]
            remaining_days = max(1, self.days - day)
            if day < self.days - 1:
                future_supply = np.sum(self.supply_matrix[:, day + 1 :], axis=1)
            else:
                future_supply = np.zeros_like(current_stock)
            remaining_stock = current_stock + future_supply
            target_total = float(np.sum(remaining_stock)) / avg_materials / float(remaining_days)
            min_day_total = max(float(self.min_prod_abs), target_total * self.daily_floor_ratio)
            if self.budget_mode == "today":
                material_budget = np.maximum(0.0, current_stock.copy())
                max_day_total = max(min_day_total, float(np.sum(material_budget)) / avg_materials)
            else:
                max_day_total = max(min_day_total, target_total * self.daily_cap_ratio)
                material_budget = remaining_stock / float(remaining_days)
                material_budget *= self.material_cap_ratio
                material_budget = np.minimum(material_budget, current_stock)
                material_budget = np.maximum(0.0, material_budget)
            budget_stock = material_budget.copy()
            if np.sum(budget_stock) <= 1e-6 and np.sum(current_stock) > 1e-6:
                budget_stock = current_stock.copy()

            priority = schedule_pref[:, day].copy()
            priority += self.weight_bonus * weight_norm
            priority[prev_active] += self.continuity_bonus
            priority[~produced_any] += self.coverage_bonus
            order = np.argsort(priority)[::-1]

            soft_min = base_soft_min
            active = []

            while True:
                active.clear()
                # force continuity when feasible
                for m in order:
                    if not prev_active[m]:
                        continue
                    if len(active) >= self.base_repair.max_machines_per_day:
                        break
                    req = req_indices[m]
                    avail = float(self.base_repair.max_production_per_machine) if req.size == 0 else float(np.min(budget_stock[req]))
                    if avail >= soft_min:
                        active.append(m)

                for m in order:
                    if len(active) >= self.base_repair.max_machines_per_day:
                        break
                    if m in active:
                        continue
                    req = req_indices[m]
                    if req.size == 0:
                        avail = float(self.base_repair.max_production_per_machine)
                    else:
                        avail = float(np.min(budget_stock[req]))
                    if avail < soft_min:
                        continue
                    active.append(m)

                if len(active) >= self.base_repair.min_machines_per_day or soft_min <= 1:
                    break
                soft_min = max(1, soft_min // 2)

            if not active:
                if np.any(current_stock > 0):
                    m = int(order[0])
                    req = req_indices[m]
                    avail = float(np.min(budget_stock[req])) if req.size > 0 else float(self.base_repair.max_production_per_machine)
                    prod = min(avail, float(self.base_repair.max_production_per_machine))
                    if prod > 0:
                        schedule[m, day] = prod
                        if req.size > 0:
                            current_stock[req] = np.maximum(0.0, current_stock[req] - prod)
                            budget_stock[req] = np.maximum(0.0, budget_stock[req] - prod)
                        prev_active = schedule[:, day] > 0
                        continue
                prev_active = np.zeros(self.machines, dtype=bool)
                continue

            # continuity reserve for next day
            if day < self.days - 1:
                supply_next = self.supply_matrix[:, day + 1]
            else:
                supply_next = np.zeros_like(current_stock)

            target_next = min(self.base_repair.max_machines_per_day, self.machines)
            if target_next <= 0:
                reserve = np.zeros_like(current_stock)
            else:
                active_set = set(active)
                next_candidates = []
                for m in order:
                    if m in active_set:
                        next_candidates.append(m)
                for m in order:
                    if m not in active_set:
                        next_candidates.append(m)
                selected_next = list(next_candidates[:target_next])

                required_counts = np.zeros_like(current_stock)
                for m in selected_next:
                    req = req_indices[m]
                    if req.size > 0:
                        required_counts[req] += 1
                reserve = np.maximum(0.0, required_counts * soft_min - supply_next)
                reserve = np.maximum(0.0, reserve * self.reserve_ratio)

                # drop low-priority machines from next-day target if reserve is impossible
                total_available = current_stock + supply_next
                if np.any(reserve > total_available):
                    for m in next_candidates[::-1]:
                        if m not in selected_next:
                            continue
                        req = req_indices[m]
                        if req.size > 0:
                            required_counts[req] = np.maximum(0, required_counts[req] - 1)
                        selected_next.remove(m)
                        reserve = np.maximum(0.0, required_counts * soft_min - supply_next)
                        reserve = np.maximum(0.0, reserve * self.reserve_ratio)
                        if not np.any(reserve > total_available):
                            break

            available_today = np.maximum(0.0, budget_stock - reserve)

            # base allocation + weighted allocation
            base_floor = max(1.0, float(soft_min))
            if active and base_floor > 0:
                while True:
                    required_counts = np.zeros_like(current_stock)
                    for m in active:
                        req = req_indices[m]
                        if req.size > 0:
                            required_counts[req] += 1
                    base_required = required_counts * base_floor
                    over_mask = base_required > (available_today + 1e-6)
                    if not np.any(over_mask):
                        break
                    candidates = []
                    for m in active:
                        req = req_indices[m]
                        if req.size == 0:
                            continue
                        if np.any(over_mask[req]):
                            candidates.append(m)
                    if len(candidates) == 0:
                        candidates = list(active)
                    drop = min(candidates, key=lambda m: priority[m])
                    active.remove(drop)
                    if not active:
                        break

            if not active:
                if np.any(available_today > 0):
                    for m in order:
                        req = req_indices[m]
                        avail = (
                            float(np.min(available_today[req]))
                            if req.size > 0
                            else float(self.base_repair.max_production_per_machine)
                        )
                        if avail <= 0:
                            continue
                        prod = min(avail, float(self.base_repair.max_production_per_machine))
                        if prod <= 0:
                            continue
                        schedule[m, day] = prod
                        if req.size > 0:
                            current_stock[req] = np.maximum(0.0, current_stock[req] - prod)
                            budget_stock[req] = np.maximum(0.0, budget_stock[req] - prod)
                        break
                prev_active = schedule[:, day] > 0
                produced_any |= prev_active
                continue

            for m in active:
                req = req_indices[m]
                prod = min(base_floor, float(self.base_repair.max_production_per_machine))
                if prod <= 0:
                    continue
                schedule[m, day] = prod
                if req.size > 0:
                    current_stock[req] = np.maximum(0.0, current_stock[req] - prod)
                    budget_stock[req] = np.maximum(0.0, budget_stock[req] - prod)

            available_today = np.maximum(0.0, budget_stock - reserve)
            mix = float(np.clip(self.weight_mix, 0.0, 1.0))
            weights = (1.0 - mix) + mix * weight_norm
            total_weight = np.zeros_like(current_stock)
            for m in active:
                req = req_indices[m]
                if req.size > 0:
                    total_weight[req] += weights[m]

            day_total = float(np.sum(schedule[:, day]))
            remaining_cap = max(0.0, max_day_total - day_total)
            alloc_order = sorted(active, key=lambda m: weights[m], reverse=True)
            for m in alloc_order:
                if remaining_cap <= 0:
                    break
                req = req_indices[m]
                extra_cap = float(self.base_repair.max_production_per_machine) - schedule[m, day]
                if extra_cap <= 0:
                    continue
                if req.size == 0:
                    extra = min(extra_cap, remaining_cap)
                else:
                    shares = []
                    for mat in req:
                        denom = total_weight[mat]
                        if denom <= 1e-9:
                            continue
                        shares.append(available_today[mat] * weights[m] / denom)
                    if not shares:
                        continue
                    extra = min(min(shares), extra_cap, remaining_cap)
                if extra <= 0:
                    continue
                schedule[m, day] += extra
                remaining_cap -= extra
                if req.size > 0:
                    current_stock[req] = np.maximum(0.0, current_stock[req] - extra)
                    budget_stock[req] = np.maximum(0.0, budget_stock[req] - extra)
                    available_today[req] = np.maximum(0.0, available_today[req] - extra)

            # expand production for active machines with remaining stock
            day_total = float(np.sum(schedule[:, day]))
            remaining_cap = max(0.0, max_day_total - day_total)
            for m in active:
                if remaining_cap <= 0:
                    break
                req = req_indices[m]
                if req.size == 0:
                    avail = float(self.base_repair.max_production_per_machine)
                else:
                    avail = float(np.min(np.maximum(0.0, budget_stock[req] - reserve[req])))
                if avail <= 0:
                    continue
                extra_cap = float(self.base_repair.max_production_per_machine) - schedule[m, day]
                if extra_cap <= 0:
                    continue
                extra = min(avail, extra_cap, remaining_cap)
                if extra <= 0:
                    continue
                schedule[m, day] += extra
                if req.size > 0:
                    current_stock[req] = np.maximum(0.0, current_stock[req] - extra)
                    budget_stock[req] = np.maximum(0.0, budget_stock[req] - extra)
                remaining_cap -= extra

            # dynamic minimum production threshold per day
            day_total = float(np.sum(schedule[:, day]))
            threshold = max(self.min_prod_abs, self.min_prod_ratio * day_total)
            if day_total < min_day_total and threshold > 1.0:
                ratio = day_total / max(min_day_total, 1e-6)
                threshold = max(1.0, threshold * max(0.25, ratio))
            if threshold > 0:
                pruned = True
                attempts = 0
                while pruned and attempts < 3:
                    pruned = False
                    attempts += 1
                    for m in list(active):
                        if schedule[m, day] >= threshold:
                            continue
                        prod = schedule[m, day]
                        schedule[m, day] = 0.0
                        active.remove(m)
                        req = req_indices[m]
                        if req.size > 0 and prod > 0:
                            current_stock[req] = current_stock[req] + prod
                            budget_stock[req] = budget_stock[req] + prod
                        pruned = True

                    if len(active) < self.base_repair.min_machines_per_day:
                        threshold = max(1.0, threshold * 0.5)
                        # try to refill with machines that can meet threshold
                        for m in order:
                            if len(active) >= self.base_repair.min_machines_per_day:
                                break
                            if m in active:
                                continue
                            req = req_indices[m]
                            avail = float(self.base_repair.max_production_per_machine) if req.size == 0 else float(np.min(budget_stock[req]))
                            if avail >= threshold:
                                schedule[m, day] = min(avail, float(self.base_repair.max_production_per_machine))
                                active.append(m)
                                if req.size > 0:
                                    current_stock[req] = np.maximum(0.0, current_stock[req] - schedule[m, day])
                                    budget_stock[req] = np.maximum(0.0, budget_stock[req] - schedule[m, day])
                                pruned = True

            if np.sum(schedule[:, day]) <= 1e-6 and np.any(current_stock > 0):
                for m in order:
                    req = req_indices[m]
                    avail = float(np.min(current_stock[req])) if req.size > 0 else float(self.base_repair.max_production_per_machine)
                    if avail <= 0:
                        continue
                    prod = min(avail, float(self.base_repair.max_production_per_machine))
                    if prod <= 0:
                        continue
                    schedule[m, day] = prod
                    if req.size > 0:
                        current_stock[req] = np.maximum(0.0, current_stock[req] - prod)
                    break

            # fill to max machines when possible, prefer previous-day machines
            active_mask = schedule[:, day] > 0
            active_count = int(np.sum(active_mask))
            if active_count < self.base_repair.max_machines_per_day and np.any(current_stock > 0):
                day_total = float(np.sum(schedule[:, day]))
                remaining_cap = max(0.0, max_day_total - day_total)
                if remaining_cap > 0:
                    missing = max(1, self.base_repair.max_machines_per_day - active_count)
                    target_per_new = max(float(self.min_production_per_machine), remaining_cap / float(missing))
                    candidate_order = []
                    for m in order:
                        if prev_day_active[m] and not active_mask[m]:
                            candidate_order.append(m)
                    for m in order:
                        if not active_mask[m] and m not in candidate_order:
                            candidate_order.append(m)

                    for m in candidate_order:
                        if active_count >= self.base_repair.max_machines_per_day or remaining_cap <= 1e-6:
                            break
                        req = req_indices[m]
                        avail = (
                            float(np.min(current_stock[req]))
                            if req.size > 0
                            else float(self.base_repair.max_production_per_machine)
                        )
                        if avail <= 0:
                            continue
                        extra_cap = float(self.base_repair.max_production_per_machine) - schedule[m, day]
                        if extra_cap <= 0:
                            continue
                        extra = min(avail, extra_cap, target_per_new, remaining_cap)
                        if extra <= 0:
                            continue
                        schedule[m, day] += extra
                        remaining_cap -= extra
                        active_mask[m] = True
                        active_count += 1
                        if req.size > 0:
                            current_stock[req] = np.maximum(0.0, current_stock[req] - extra)

            # force daily minimum production (sacrifice smoothness if needed)
            day_total = float(np.sum(schedule[:, day]))
            if day_total < min_day_total and np.any(current_stock > 0):
                gap = min_day_total - day_total

                def _lift_with_stock(stock: np.ndarray, allow_new: bool) -> float:
                    nonlocal gap
                    active_mask = schedule[:, day] > 0
                    active_count = int(np.sum(active_mask))
                    lift_order = []
                    for m in order:
                        if active_mask[m]:
                            lift_order.append(m)
                    if allow_new:
                        for m in order:
                            if not active_mask[m]:
                                lift_order.append(m)
                    for m in lift_order:
                        if gap <= 1e-6:
                            break
                        req = req_indices[m]
                        is_new = schedule[m, day] <= 1e-12
                        if is_new and active_count >= self.base_repair.max_machines_per_day:
                            continue
                        extra_cap = float(self.base_repair.max_production_per_machine) - schedule[m, day]
                        if extra_cap <= 0:
                            continue
                        if req.size == 0:
                            avail = extra_cap
                        else:
                            avail = float(np.min(stock[req]))
                            avail = min(avail, extra_cap)
                        if avail <= 0:
                            continue
                        if is_new:
                            min_new = max(float(self.min_production_per_machine), threshold)
                        else:
                            min_new = 0.0
                        extra = min(avail, gap)
                        if extra < min_new:
                            extra = min(avail, min_new)
                            if extra <= 0:
                                continue
                        schedule[m, day] += extra
                        gap -= extra
                        if req.size > 0:
                            stock[req] = np.maximum(0.0, stock[req] - extra)
                            current_stock[req] = np.maximum(0.0, current_stock[req] - extra)
                            if stock is not budget_stock:
                                budget_stock[req] = np.maximum(0.0, budget_stock[req] - extra)
                        if is_new and schedule[m, day] > 0:
                            active_count += 1
                    return gap

                allow_new = len(active) < self.base_repair.max_machines_per_day
                _lift_with_stock(budget_stock, allow_new=allow_new)
                if gap > 1e-6:
                    _lift_with_stock(current_stock, allow_new=allow_new)

            prev_active = schedule[:, day] > 0
            produced_any |= prev_active

        schedule = self._balance_forward(schedule, weight_norm)
        schedule = np.floor(schedule)
        schedule = np.clip(schedule, 0, self.base_repair.max_production_per_machine)
        schedule = self._prune_fragments(schedule)

        coverage_rounds = max(1, int(self.coverage_passes))
        for _ in range(coverage_rounds):
            schedule = self._enforce_material_feasibility(schedule, weight_norm)
            schedule = self._backfill_coverage(schedule, weight_norm)
            schedule = np.floor(schedule)
            schedule = np.clip(schedule, 0, self.base_repair.max_production_per_machine)
            schedule = self._prune_fragments(schedule)

        schedule = self._continuity_swap(schedule, weight_norm)
        schedule = self._enforce_material_feasibility(schedule, weight_norm)
        schedule = self._prune_fragments(schedule)
        return schedule.reshape(-1)


def build_schedule_pipeline(
    problem,
    constraints,
    *,
    material_cap_ratio: float = 2.0,
    daily_floor_ratio: float = 0.55,
    donor_keep_ratio: float = 0.7,
    daily_cap_ratio: float = 2.2,
    reserve_ratio: float = 0.6,
    coverage_bonus: float = 300.0,
    budget_mode: str = "today",
    smooth_strength: float = 0.6,
    smooth_passes: int = 2,
) -> RepresentationPipeline:
    if getattr(problem, "data", None) is not None:
        initializer = SupplyAwareInitializer(
            machines=problem.machines,
            days=problem.days,
            min_machines_per_day=constraints.min_machines_per_day,
            max_machines_per_day=constraints.max_machines_per_day,
            min_production_per_machine=constraints.min_production_per_machine,
            max_production_per_machine=constraints.max_production_per_machine,
            bom_matrix=problem.data.bom_matrix,
            supply_matrix=problem.data.supply_matrix,
            machine_weights=getattr(problem.data, "machine_weights", None),
        )
    else:
        initializer = ProductionScheduleInitializer(
            machines=problem.machines,
            days=problem.days,
            min_machines_per_day=constraints.min_machines_per_day,
            max_machines_per_day=constraints.max_machines_per_day,
            min_production_per_machine=constraints.min_production_per_machine,
            max_production_per_machine=constraints.max_production_per_machine,
        )
    mutator = ProductionScheduleMutation(
        sigma=0.5,
        per_gene_rate=0.05,
        toggle_rate=0.02,
        max_production_per_machine=constraints.max_production_per_machine,
    )
    base_repair = ProductionScheduleRepair(
        machines=problem.machines,
        days=problem.days,
        min_machines_per_day=constraints.min_machines_per_day,
        max_machines_per_day=constraints.max_machines_per_day,
        min_production_per_machine=constraints.min_production_per_machine,
        max_production_per_machine=constraints.max_production_per_machine,
    )
    if getattr(problem, "data", None) is not None:
        repair = SupplyAwareScheduleRepair(
            machines=problem.machines,
            days=problem.days,
            min_production_per_machine=constraints.min_production_per_machine,
            bom_matrix=problem.data.bom_matrix,
            supply_matrix=problem.data.supply_matrix,
            base_repair=base_repair,
            machine_weights=getattr(problem.data, "machine_weights", None),
            soft_min_ratio=0.2,
            continuity_bonus=600.0,
            weight_bonus=200.0,
            coverage_bonus=coverage_bonus,
            min_prod_ratio=0.02,
            min_prod_abs=100,
            material_cap_ratio=material_cap_ratio,
            daily_floor_ratio=daily_floor_ratio,
            donor_keep_ratio=donor_keep_ratio,
            daily_cap_ratio=daily_cap_ratio,
            reserve_ratio=reserve_ratio,
            budget_mode=budget_mode,
            smooth_strength=smooth_strength,
            smooth_passes=smooth_passes,
            coverage_passes=smooth_passes,
            fragment_passes=2,
        )
    else:
        repair = base_repair
    return RepresentationPipeline(
        initializer=initializer,
        mutator=mutator,
        repair=repair,
        encoder=None,
    )
