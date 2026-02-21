"""Adaptive runtime parameter plugin."""

from __future__ import annotations

from typing import Any, Dict

import numpy as np

from ..base import Plugin
from ...utils.context.context_keys import KEY_CROSSOVER_RATE, KEY_MUTATION_RATE


class AdaptiveParametersPlugin(Plugin):
    """Adapt mutation/crossover rates based on recent improvement."""

    is_algorithmic = True
    context_requires = ()
    context_provides = ()
    context_mutates = (KEY_MUTATION_RATE, KEY_CROSSOVER_RATE)
    context_cache = ()
    context_notes = (
        "Reads adapter/context objective snapshot and adaptively mutates solver "
        "mutation_rate/crossover_rate; writes adaptation summary into run result."
    )

    def __init__(
        self,
        stagnation_window: int = 10,
        improvement_threshold: float = 0.001,
        min_mutation_rate: float = 0.05,
        max_mutation_rate: float = 0.4,
        min_crossover_rate: float = 0.5,
        max_crossover_rate: float = 0.95,
    ) -> None:
        super().__init__("adaptive_parameters")
        self.stagnation_window = int(stagnation_window)
        self.improvement_threshold = float(improvement_threshold)
        self.min_mutation_rate = float(min_mutation_rate)
        self.max_mutation_rate = float(max_mutation_rate)
        self.min_crossover_rate = float(min_crossover_rate)
        self.max_crossover_rate = float(max_crossover_rate)

        self.best_fitness_history: list[float] = []
        self.stagnation_count = 0
        self.initial_crossover_rate: float | None = None
        self.initial_mutation_rate: float | None = None
        self.adaptation_history: list[Dict[str, Any]] = []

    def on_solver_init(self, solver) -> None:
        self.best_fitness_history = []
        self.stagnation_count = 0
        self.adaptation_history = []
        self.initial_crossover_rate = float(solver.crossover_rate)
        self.initial_mutation_rate = float(solver.mutation_rate)

    def on_population_init(self, population, objectives, violations) -> None:
        best_fitness = self._get_best_fitness(objectives)
        self.best_fitness_history.append(best_fitness)

    def on_generation_start(self, generation: int) -> None:
        return None

    def on_context_build(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if self.solver is None:
            return context
        context[KEY_MUTATION_RATE] = float(getattr(self.solver, "mutation_rate", 0.0))
        context[KEY_CROSSOVER_RATE] = float(getattr(self.solver, "crossover_rate", 0.0))
        return context

    def on_generation_end(self, generation: int) -> None:
        if self.solver is None or not self.enabled:
            return None

        _, objectives, _ = self.resolve_population_snapshot(self.solver)
        if objectives.size == 0:
            return None
        current_best = self._get_best_fitness(objectives)
        self.best_fitness_history.append(current_best)

        if len(self.best_fitness_history) < 2:
            return None

        improvement = self.best_fitness_history[-2] - current_best
        if improvement > self.improvement_threshold:
            self.stagnation_count = 0
            self._adjust_parameters("improving", generation)
            return None

        self.stagnation_count += 1
        if self.stagnation_count >= self.stagnation_window:
            self._adjust_parameters("stagnant", generation)
            self.stagnation_count = 0
        return None

    def on_solver_finish(self, result: Dict[str, Any]) -> None:
        if self.solver is None:
            return None
        result["adaptation_history"] = self.adaptation_history
        result["final_crossover_rate"] = float(self.solver.crossover_rate)
        result["final_mutation_rate"] = float(self.solver.mutation_rate)
        return None

    def _get_best_fitness(self, objectives: np.ndarray) -> float:
        if objectives.shape[1] == 1:
            return float(np.min(objectives[:, 0]))
        fitness_values = np.sum(objectives, axis=1)
        return float(np.min(fitness_values))

    def _adjust_parameters(self, state: str, generation: int) -> None:
        if self.solver is None:
            return None

        old_mutation = float(self.solver.mutation_rate)
        old_crossover = float(self.solver.crossover_rate)

        if state == "stagnant":
            self.solver.mutation_rate = min(self.max_mutation_rate, old_mutation + 0.05)
            self.solver.crossover_rate = max(self.min_crossover_rate, old_crossover - 0.03)
            action = "stagnant"
        elif state == "improving":
            self.solver.mutation_rate = max(self.min_mutation_rate, old_mutation - 0.02)
            self.solver.crossover_rate = min(self.max_crossover_rate, old_crossover + 0.03)
            action = "improving"
        else:
            return None

        self.adaptation_history.append(
            {
                "generation": int(generation),
                "action": action,
                "old_mutation_rate": old_mutation,
                "new_mutation_rate": float(self.solver.mutation_rate),
                "old_crossover_rate": old_crossover,
                "new_crossover_rate": float(self.solver.crossover_rate),
            }
        )
        return None
