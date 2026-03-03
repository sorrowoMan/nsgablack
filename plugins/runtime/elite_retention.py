"""Elite retention plugins."""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np

from ..base import Plugin
from ...utils.context.context_keys import (
    KEY_CONSTRAINT_VIOLATIONS,
    KEY_EVALUATION_COUNT,
    KEY_OBJECTIVES,
    KEY_POPULATION,
)


def _evaluate_candidate_with_solver(solver, x: np.ndarray, individual_id: int) -> tuple[np.ndarray, float]:
    evaluator = getattr(solver, "evaluate_individual", None)
    if callable(evaluator):
        obj, vio = evaluator(x, individual_id=individual_id)
        return np.asarray(obj, dtype=float).reshape(-1), float(vio)

    legacy = getattr(solver, "_evaluate_individual", None)
    if callable(legacy):
        obj, vio = legacy(x, individual_id=individual_id)
        counter = getattr(solver, "increment_evaluation_count", None)
        if callable(counter):
            try:
                counter(1)
            except Exception:
                pass
        return np.asarray(obj, dtype=float).reshape(-1), float(vio)

    raise AttributeError("solver has neither evaluate_individual() nor _evaluate_individual()")


class BasicElitePlugin(Plugin):
    """Keep global best solution from being lost during evolution."""

    is_algorithmic = True
    context_requires = ()
    context_provides = ()
    context_mutates = (KEY_POPULATION, KEY_OBJECTIVES, KEY_CONSTRAINT_VIOLATIONS, KEY_EVALUATION_COUNT)
    context_cache = ()
    context_notes = (
        "Mutates population snapshot via adapter/context write-back by elite injection; "
        "uses representation pipeline when available."
    )

    def __init__(self, retention_prob: float = 0.9, retention_ratio: float = 0.1) -> None:
        super().__init__("basic_elite")
        self.retention_prob = float(retention_prob)
        self.retention_ratio = float(retention_ratio)
        self.best_solution: np.ndarray | None = None
        self.best_objectives: np.ndarray | None = None
        self.best_fitness = float("inf")
        self.fitness_history: List[float] = []
        self._rng = np.random.default_rng()

    def on_solver_init(self, solver) -> None:
        self._rng = self.create_local_rng(solver=solver)
        self.best_solution = None
        self.best_objectives = None
        self.best_fitness = float("inf")
        self.fitness_history = []

    def on_population_init(self, population, objectives, violations) -> None:
        self._update_best_solution(population, objectives)

    def on_generation_start(self, generation: int) -> None:
        return None

    def on_context_build(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if self.solver is None:
            return context
        context[KEY_EVALUATION_COUNT] = int(getattr(self.solver, "evaluation_count", 0))
        return context

    def on_generation_end(self, generation: int) -> None:
        if self.solver is None:
            return None
        population, objectives, violations = self.resolve_population_snapshot(self.solver)
        if objectives.size == 0:
            return None
        self._update_best_solution(population, objectives)
        self.fitness_history.append(float(self.best_fitness))
        if self._rng.random() < self.retention_prob and self.best_solution is not None:
            self._retain_elites(population, objectives, violations)
        return None

    def on_solver_finish(self, result: Dict[str, Any]) -> None:
        result["best_solution"] = self.best_solution
        result["best_fitness"] = self.best_fitness
        result["fitness_history"] = self.fitness_history

    def _update_best_solution(self, population: np.ndarray, objectives: np.ndarray) -> None:
        if len(objectives) == 0:
            return None
        if objectives.shape[1] == 1:
            fitness_values = objectives[:, 0]
        else:
            fitness_values = np.sum(objectives, axis=1)

        best_idx = int(np.argmin(fitness_values))
        current_best_fitness = float(fitness_values[best_idx])
        if current_best_fitness < self.best_fitness:
            self.best_fitness = current_best_fitness
            self.best_solution = population[best_idx].copy()
            self.best_objectives = objectives[best_idx].copy()
        return None

    def _retain_elites(self, population: np.ndarray, objectives: np.ndarray, violations: np.ndarray) -> None:
        if self.solver is None or self.best_solution is None:
            return None

        pop_size = len(population)
        n_retain = max(1, int(pop_size * self.retention_ratio))

        if objectives.shape[1] == 1:
            fitness_values = objectives[:, 0]
        else:
            fitness_values = np.sum(objectives, axis=1)
        worst_indices = np.argsort(fitness_values)[-n_retain:]

        for idx in worst_indices:
            perturbation = self._rng.normal(0, 0.01, self.best_solution.shape)
            perturbed_solution = self.best_solution + perturbation

            if self.solver.representation_pipeline is not None:
                context = {"generation": self.solver.generation, "bounds": self.solver.var_bounds}
                perturbed_solution = self.solver.representation_pipeline.mutate(self.best_solution, context)
            else:
                for j in range(self.solver.dimension):
                    min_val, max_val = self.solver.var_bounds[j]
                    perturbed_solution[j] = np.clip(perturbed_solution[j], min_val, max_val)

            population[idx] = perturbed_solution
            obj, vio = _evaluate_candidate_with_solver(self.solver, perturbed_solution, int(idx))
            objectives[idx] = obj
            violations[idx] = float(vio)
        self.commit_population_snapshot(population, objectives, violations, self.solver)
        return None


class HistoricalElitePlugin(Plugin):
    """Use historical elite archive to replace weak individuals."""

    is_algorithmic = True
    context_requires = ()
    context_provides = ()
    context_mutates = (KEY_POPULATION, KEY_OBJECTIVES, KEY_CONSTRAINT_VIOLATIONS, KEY_EVALUATION_COUNT)
    context_cache = ()
    context_notes = (
        "Maintains historical elite archive and replaces weak individuals; "
        "mutates population snapshot via adapter/context write-back."
    )

    def __init__(
        self,
        history_size: int = 50,
        replacement_prob: float = 0.1,
        replacement_ratio: float = 0.1,
    ) -> None:
        super().__init__("historical_elite")
        self.history_size = int(history_size)
        self.replacement_prob = float(replacement_prob)
        self.replacement_ratio = float(replacement_ratio)
        self.elite_archive: List[Dict[str, Any]] = []
        self.best_solution: np.ndarray | None = None
        self.best_fitness = float("inf")
        self._rng = np.random.default_rng()

    def on_solver_init(self, solver) -> None:
        self._rng = self.create_local_rng(solver=solver)
        self.elite_archive = []
        self.best_solution = None
        self.best_fitness = float("inf")

    def on_population_init(self, population, objectives, violations) -> None:
        self._update_best_and_archive(population, objectives, 0)

    def on_generation_start(self, generation: int) -> None:
        return None

    def on_context_build(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if self.solver is None:
            return context
        context[KEY_EVALUATION_COUNT] = int(getattr(self.solver, "evaluation_count", 0))
        return context

    def on_generation_end(self, generation: int) -> None:
        if self.solver is None or not self.enabled:
            return None

        population, objectives, violations = self.resolve_population_snapshot(self.solver)
        if objectives.size == 0:
            return None
        self._update_best_and_archive(population, objectives, generation)
        if self._rng.random() < self.replacement_prob and len(self.elite_archive) > 0:
            self._historical_replacement(population, objectives, violations)
        return None

    def on_solver_finish(self, result: Dict[str, Any]) -> None:
        result["elite_archive_size"] = len(self.elite_archive)
        result["historical_replacement_used"] = True

    def _update_best_and_archive(self, population: np.ndarray, objectives: np.ndarray, generation: int) -> None:
        if len(objectives) == 0:
            return None

        if objectives.shape[1] == 1:
            fitness_values = objectives[:, 0]
        else:
            fitness_values = np.sum(objectives, axis=1)

        best_idx = int(np.argmin(fitness_values))
        current_best_fitness = float(fitness_values[best_idx])

        if current_best_fitness < self.best_fitness:
            self.best_fitness = current_best_fitness
            self.best_solution = population[best_idx].copy()

        candidate = {
            "individual": population[best_idx].copy(),
            "objectives": objectives[best_idx].copy(),
            "fitness": current_best_fitness,
            "generation": int(generation),
        }

        is_duplicate = False
        for elite in self.elite_archive:
            if np.linalg.norm(candidate["individual"] - elite["individual"]) < 1e-6:
                is_duplicate = True
                if candidate["fitness"] < elite["fitness"]:
                    elite.update(candidate)
                break

        if not is_duplicate:
            self.elite_archive.append(candidate)
            if len(self.elite_archive) > self.history_size:
                worst_idx = int(np.argmax([e["fitness"] for e in self.elite_archive]))
                self.elite_archive.pop(worst_idx)
        return None

    def _historical_replacement(
        self,
        population: np.ndarray,
        objectives: np.ndarray,
        violations: np.ndarray,
    ) -> None:
        if self.solver is None or len(self.elite_archive) == 0:
            return None

        pop_size = len(population)
        n_replace = max(1, int(pop_size * self.replacement_ratio))

        recent = self.elite_archive[-min(self.history_size // 2, len(self.elite_archive)) :]
        if len(recent) == 0:
            return None

        n_sample = min(n_replace, len(recent))
        selected_indices = self._rng.choice(len(recent), n_sample, replace=False)

        if objectives.shape[1] == 1:
            fitness_values = objectives[:, 0]
        else:
            fitness_values = np.sum(objectives, axis=1)
        worst_indices = np.argsort(fitness_values)[-n_sample:]

        for i, elite_idx in enumerate(selected_indices):
            pop_idx = worst_indices[i]
            historical = recent[int(elite_idx)]

            perturbation = self._rng.normal(0, 0.02, historical["individual"].shape)
            new_individual = historical["individual"] + perturbation

            if self.solver.representation_pipeline is not None:
                context = {"generation": self.solver.generation, "bounds": self.solver.var_bounds}
                new_individual = self.solver.representation_pipeline.mutate(historical["individual"], context)
            else:
                for j in range(self.solver.dimension):
                    min_val, max_val = self.solver.var_bounds[j]
                    new_individual[j] = np.clip(new_individual[j], min_val, max_val)

            population[pop_idx] = new_individual
            obj, vio = _evaluate_candidate_with_solver(self.solver, new_individual, int(pop_idx))
            objectives[pop_idx] = obj
            violations[pop_idx] = float(vio)
        self.commit_population_snapshot(population, objectives, violations, self.solver)
        return None
