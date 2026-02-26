"""Initialization diversity helper plugin."""

from __future__ import annotations

from typing import Any

import numpy as np

from ..base import Plugin


class DiversityInitPlugin(Plugin):
    """Compute/encourage diversity signal for initial population."""

    is_algorithmic = True
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Uses solver/population state to improve initialization diversity; "
        "does not persist context fields."
    )

    def __init__(self, similarity_threshold: float = 0.1, rejection_prob: float = 0.5) -> None:
        super().__init__("diversity_init")
        self.similarity_threshold = float(similarity_threshold)
        self.rejection_prob = float(rejection_prob)
        self._rng = np.random.default_rng()

    def on_solver_init(self, solver) -> None:
        self._rng = self.create_local_rng(solver=solver)
        if hasattr(solver, "use_diverse_init"):
            solver.use_diverse_init = True
        return None

    def on_population_init(self, population, objectives, violations) -> None:
        diversity_score = self._compute_diversity(population)
        print(f"[DiversityInit] initial_diversity={diversity_score:.4f}")
        return None

    def on_generation_start(self, generation: int) -> None:
        return None

    def on_generation_end(self, generation: int) -> None:
        return None

    def on_solver_finish(self, result: Any) -> None:
        return None

    def _compute_diversity(self, population: np.ndarray) -> float:
        if len(population) < 2:
            return 0.0

        pop_norm = (population - population.min(axis=0)) / (
            population.max(axis=0) - population.min(axis=0) + 1e-10
        )

        n_samples = min(30, len(pop_norm))
        indices = self._rng.choice(len(pop_norm), n_samples, replace=False)
        samples = pop_norm[indices]

        distances = []
        for i in range(n_samples):
            for j in range(i + 1, n_samples):
                distances.append(float(np.linalg.norm(samples[i] - samples[j])))

        return float(np.mean(distances)) if len(distances) > 0 else 0.0

    def is_similar(self, individual: np.ndarray, existing_population: np.ndarray) -> bool:
        if len(existing_population) == 0:
            return False

        min_distance = float("inf")
        for existing in existing_population:
            dist = float(np.linalg.norm(individual - existing))
            if dist < min_distance:
                min_distance = dist
        return min_distance < self.similarity_threshold

    def should_accept(self, individual: np.ndarray, existing_population: np.ndarray) -> bool:
        if not self.is_similar(individual, existing_population):
            return True
        return bool(self._rng.random() > self.rejection_prob)
