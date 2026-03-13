"""Strict feasible solver for production_scheduling case."""

from __future__ import annotations

import numpy as np

from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.utils.context.context_keys import KEY_STEP
from nsgablack.utils.extension_contracts import normalize_candidates, stack_population


def project_schedule_material_feasible(problem, schedule: np.ndarray) -> np.ndarray:
    """Hard projection: enforce day-by-day material feasibility (shortage == 0)."""
    sched = np.asarray(schedule, dtype=float).copy()
    sched = np.clip(sched, 0.0, float(problem.constraints.max_production_per_machine))
    machines, days = sched.shape
    if machines != int(problem.machines) or days != int(problem.days):
        return sched
    bom = np.asarray(problem.data.bom_matrix, dtype=float)
    supply = np.asarray(problem.data.supply_matrix, dtype=float)
    current_stock = np.zeros(int(problem.materials), dtype=float)
    for day in range(days):
        current_stock += supply[:, day]
        day_prod = sched[:, day].copy()
        order = np.argsort(-day_prod)  # Keep larger planned outputs first.
        for m in order:
            prod = float(day_prod[m])
            if prod <= 0.0:
                continue
            req = bom[m, :]
            idx = req > 0
            if not np.any(idx):
                continue
            feasible = float(np.min(current_stock[idx] / np.maximum(req[idx], 1e-12)))
            if feasible < prod:
                day_prod[m] = max(0.0, feasible)
            consume = req * float(day_prod[m])
            current_stock = np.maximum(0.0, current_stock - consume)
        sched[:, day] = day_prod
    return sched


def project_candidate_material_feasible(problem, x: np.ndarray) -> np.ndarray:
    schedule = problem.decode_schedule(np.asarray(x, dtype=float))
    projected = project_schedule_material_feasible(problem, schedule)
    return projected.reshape(-1)


class StrictFeasibleProductionSolver(ComposableSolver):
    """Composable solver with hard material-feasible filtering before adapter update."""

    def __init__(self, *args, strict_constraint_tol: float = 1e-9, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.strict_constraint_tol = float(strict_constraint_tol)

    def step(self) -> None:
        if self.adapter is None:
            return
        context = self.build_context()
        context[KEY_STEP] = self.generation
        proposed = self.adapter.coerce_candidates(self.adapter.propose(self, context))
        candidates = normalize_candidates(
            proposed,
            dimension=self.dimension,
            owner=getattr(self.adapter, "name", "adapter"),
        )
        if len(candidates) > 0 and self.representation_pipeline is not None:
            repair = getattr(self.representation_pipeline, "repair", None)
            if repair is not None:
                if hasattr(self.representation_pipeline, "repair_batch"):
                    contexts = [context] * len(candidates)
                    candidates = self.representation_pipeline.repair_batch(candidates, contexts=contexts)
                else:
                    candidates = [self.repair_candidate(cand, context) for cand in candidates]
        if candidates is None:
            return
        try:
            candidate_count = len(candidates)
        except TypeError:
            candidates = [candidates]  # type: ignore[list-item]
            candidate_count = 1
        if candidate_count <= 0:
            return

        # Step-2: strict projection after repair to ensure material feasibility.
        candidates = [
            project_candidate_material_feasible(self.problem, np.asarray(c, dtype=float))
            for c in candidates
        ]

        population_all = stack_population(candidates, name="StrictFeasibleProductionSolver.population")
        objectives_all, violations_all = self.evaluate_population(population_all)

        # Step-1: hard filter infeasible candidates (all constraints).
        selected_mask = np.ones(len(population_all), dtype=bool)
        if violations_all is not None and len(violations_all) == len(population_all):
            try:
                vio = np.asarray(violations_all, dtype=float).reshape(len(population_all), -1)
                finite_mask = np.all(np.isfinite(vio), axis=1)
                feasible_mask = np.all(vio <= float(self.strict_constraint_tol), axis=1)
                selected_mask = finite_mask & feasible_mask
            except (TypeError, ValueError):
                selected_mask = np.ones(len(population_all), dtype=bool)
        if np.any(selected_mask):
            self.population = np.asarray(population_all[selected_mask], dtype=float)
            self.objectives = np.asarray(objectives_all[selected_mask], dtype=float)
            self.constraint_violations = np.asarray(violations_all[selected_mask], dtype=float)
            strict_fallback = False
        else:
            self.population = population_all
            self.objectives = objectives_all
            self.constraint_violations = violations_all
            strict_fallback = True

        self.last_step_summary = self._summarize_step(self.objectives, self.constraint_violations)
        self.last_step_summary["num_candidates_raw"] = int(len(population_all))
        self.last_step_summary["num_candidates_feasible"] = int(len(self.population))
        self.last_step_summary["strict_feasible_fallback"] = bool(strict_fallback)
        self._update_best(self.population, self.objectives, self.constraint_violations)
        self.adapter.update(
            self,
            self.population,
            self.objectives,
            self.constraint_violations,
            context,
        )
