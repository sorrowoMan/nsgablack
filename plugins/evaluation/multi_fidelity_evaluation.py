from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

import numpy as np

from ..base import Plugin
from ...utils.constraints.constraint_utils import evaluate_constraints_safe
from ...utils.extension_contracts import ContractError, normalize_candidate, normalize_objectives


@dataclass
class MultiFidelityEvaluationConfig:
    min_train_samples: int = 10
    min_high_fidelity: int = 6
    topk_exploit: int = 6
    topk_explore: int = 6
    objective_aggregation: str = "sum"
    random_seed: Optional[int] = 0


class MultiFidelityEvaluationPlugin(Plugin):
    """
    Two-level evaluation plugin (low-fidelity + high-fidelity).

    - Uses low-fidelity scores to pre-rank candidates.
    - Evaluates a subset with high-fidelity (true) evaluation.
    - Returns mixed objectives (high-fidelity for selected, low-fidelity for others).
    """

    is_algorithmic = True
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Runs low/high-fidelity mixed evaluation and returns objectives/violations; "
        "does not write context fields by default."
    )

    def __init__(
        self,
        name: str = "multi_fidelity_evaluation",
        *,
        config: Optional[MultiFidelityEvaluationConfig] = None,
        low_fidelity: Optional[Callable[[Any], Any]] = None,
    ) -> None:
        super().__init__(name=name)
        self.cfg = config or MultiFidelityEvaluationConfig()
        self.low_fidelity = low_fidelity
        self._rng = np.random.default_rng(self.cfg.random_seed)
        self.stats = {"low_calls": 0, "high_calls": 0}

    def on_solver_init(self, solver):
        if self.low_fidelity is None:
            lf = getattr(getattr(solver, "problem", None), "evaluate_low_fidelity", None)
            if callable(lf):
                self.low_fidelity = lf

    def evaluate_population(self, solver, population: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        if self.low_fidelity is None:
            raise RuntimeError("MultiFidelityEvaluationPlugin requires low_fidelity evaluator.")

        pop = np.asarray(population)
        if pop.ndim == 1:
            pop = pop.reshape(1, -1)
        if pop.ndim != 2:
            raise ContractError("multi_fidelity expects population as 2D array")

        n = int(pop.shape[0])
        m = int(getattr(solver, "num_objectives", 1) or 1)
        if n == 0:
            return np.zeros((0, m), dtype=float), np.zeros((0,), dtype=float)

        xs = [normalize_candidate(pop[i], dimension=int(solver.dimension), name=f"population[{i}]") for i in range(n)]
        X = np.stack(xs, axis=0)

        cons_list = []
        violations = np.zeros((n,), dtype=float)
        for i in range(n):
            cons, vio = evaluate_constraints_safe(solver.problem, X[i])
            cons_list.append(cons)
            violations[i] = float(vio)

        # low-fidelity evaluations
        low_obj = np.zeros((n, m), dtype=float)
        for i in range(n):
            val = self.low_fidelity(X[i])
            low_obj[i] = normalize_objectives(val, num_objectives=m, name="low_fidelity.objectives")
        self.stats["low_calls"] += n

        # select high-fidelity subset
        selected = self._select_indices_for_high_fidelity(low_obj)
        if not selected and int(self.cfg.min_high_fidelity) > 0:
            selected = [int(self._rng.integers(0, n))]

        out_obj = np.array(low_obj, dtype=float, copy=True)
        if selected:
            for idx in selected:
                val = solver.problem.evaluate(X[idx])
                out_obj[idx] = normalize_objectives(val, num_objectives=m, name="high_fidelity.objectives")
            self.stats["high_calls"] += len(selected)
            solver.evaluation_count += len(selected)

        # apply bias with proper context (shared for both fidelity levels)
        for i in range(n):
            ctx = solver.build_context(individual_id=i, constraints=cons_list[i], violation=float(violations[i]))
            if getattr(solver, "enable_bias", False) and getattr(solver, "bias_module", None) is not None:
                out_obj[i] = solver._apply_bias(out_obj[i], X[i], i, ctx)

        return out_obj, violations

    def _select_indices_for_high_fidelity(self, objectives: np.ndarray) -> list[int]:
        n = int(objectives.shape[0])
        scores = self._aggregate_objectives(objectives)
        exploit_k = min(int(self.cfg.topk_exploit), n)
        exploit = list(np.argsort(scores)[:exploit_k])

        explore_k = min(int(self.cfg.topk_explore), n)
        explore = list(self._rng.choice(n, size=explore_k, replace=False)) if n > 0 else []

        selected = set(int(i) for i in exploit + explore)

        min_high = min(max(0, int(self.cfg.min_high_fidelity)), n)
        if min_high > 0:
            while len(selected) < min_high:
                selected.add(int(self._rng.integers(0, n)))

        return sorted(selected)

    def _aggregate_objectives(self, objectives: np.ndarray) -> np.ndarray:
        arr = np.asarray(objectives, dtype=float)
        if arr.ndim == 1:
            return arr
        mode = str(self.cfg.objective_aggregation).lower().strip()
        if mode == "first":
            return arr[:, 0]
        return np.sum(arr, axis=1)

