"""Convergence detection plugin."""

from __future__ import annotations

from typing import Any, Dict

import numpy as np

from ..base import Plugin
from ...utils.context.context_keys import KEY_RUNNING


class ConvergencePlugin(Plugin):
    """Detect convergence and optionally stop early."""

    is_algorithmic = True
    context_requires = ()
    context_provides = ()
    context_mutates = (KEY_RUNNING,)
    context_cache = ()
    context_notes = (
        "Reads adapter/context population snapshot to detect convergence; "
        "may set solver.running=False when early-stop is enabled."
    )

    def __init__(
        self,
        stagnation_window: int = 20,
        improvement_epsilon: float = 1e-4,
        diversity_threshold: float = 0.05,
        min_generations: int = 30,
        enable_early_stop: bool = False,
    ) -> None:
        super().__init__("convergence")
        self.stagnation_window = int(stagnation_window)
        self.improvement_epsilon = float(improvement_epsilon)
        self.diversity_threshold = float(diversity_threshold)
        self.min_generations = int(min_generations)
        self.enable_early_stop = bool(enable_early_stop)

        self.best_fitness_history: list[float] = []
        self.diversity_history: list[float] = []
        self.stagnation_count = 0
        self.is_converged = False
        self.convergence_generation: int | None = None
        self._rng = np.random.default_rng()

    def on_solver_init(self, solver) -> None:
        self._rng = self.create_local_rng(solver=solver)
        self.best_fitness_history = []
        self.diversity_history = []
        self.stagnation_count = 0
        self.is_converged = False
        self.convergence_generation = None

    def on_population_init(self, population, objectives, violations) -> None:
        if len(objectives) == 0:
            return None
        if objectives.shape[1] == 1:
            best_fitness = float(np.min(objectives[:, 0]))
        else:
            best_fitness = float(np.min(np.sum(objectives, axis=1)))
        self.best_fitness_history.append(best_fitness)
        self._update_diversity(population)
        return None

    def on_generation_start(self, generation: int) -> None:
        return None

    def on_context_build(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if self.solver is None:
            return context
        context[KEY_RUNNING] = bool(getattr(self.solver, "running", False))
        return context

    def on_generation_end(self, generation: int) -> None:
        if self.solver is None:
            return None

        population, objectives, _ = self.resolve_population_snapshot(self.solver)
        if objectives.size == 0:
            return None

        if objectives.shape[1] == 1:
            best_fitness = float(np.min(objectives[:, 0]))
        else:
            best_fitness = float(np.min(np.sum(objectives, axis=1)))
        self.best_fitness_history.append(best_fitness)
        self._update_diversity(population)

        if len(self.best_fitness_history) >= self.stagnation_window:
            recent = self.best_fitness_history[-self.stagnation_window :]
            improvement = recent[0] - recent[-1]
            if abs(improvement) < self.improvement_epsilon * abs(recent[0]):
                # Count consecutive stagnant checks instead of jumping by window size.
                self.stagnation_count += 1
            else:
                self.stagnation_count = 0

        current_diversity = self.diversity_history[-1] if self.diversity_history else 1.0
        if (
            generation >= self.min_generations
            and self.stagnation_count >= self.stagnation_window
            and current_diversity < self.diversity_threshold
        ):
            self.is_converged = True
            self.convergence_generation = int(generation)
            if self.enable_early_stop:
                self.solver.running = False
        return None

    def on_solver_finish(self, result: Dict[str, Any]) -> None:
        result["convergence_detected"] = bool(self.is_converged)
        result["convergence_generation"] = self.convergence_generation
        result["final_diversity"] = self.diversity_history[-1] if self.diversity_history else None
        result["stagnation_count"] = int(self.stagnation_count)
        return None

    def _update_diversity(self, population: np.ndarray) -> None:
        if len(population) < 2:
            self.diversity_history.append(0.0)
            return None

        pop_min = population.min(axis=0)
        pop_max = population.max(axis=0)
        pop_range = pop_max - pop_min + 1e-10
        pop_norm = (population - pop_min) / pop_range

        n_samples = min(30, len(pop_norm))
        indices = self._rng.choice(len(pop_norm), n_samples, replace=False)
        samples = pop_norm[indices]

        distances = []
        for i in range(n_samples):
            for j in range(i + 1, n_samples):
                distances.append(float(np.linalg.norm(samples[i] - samples[j])))

        diversity = float(np.mean(distances)) if distances else 0.0
        self.diversity_history.append(diversity)
        return None

    def get_convergence_info(self) -> Dict[str, Any]:
        return {
            "is_converged": self.is_converged,
            "convergence_generation": self.convergence_generation,
            "stagnation_count": self.stagnation_count,
            "current_diversity": self.diversity_history[-1] if self.diversity_history else None,
            "best_fitness_history": list(self.best_fitness_history),
            "diversity_history": list(self.diversity_history),
        }
