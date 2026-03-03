"""
Single-trajectory adaptive search adapter.

This adapter keeps one active trajectory (current solution) and adapts
neighborhood scale online from observed improvement rate.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Optional, Sequence

import numpy as np

from .algorithm_adapter import AlgorithmAdapter
from ..utils.context.context_keys import (
    KEY_MUTATION_SIGMA,
    KEY_SINGLE_TRAJ_SIGMA,
    KEY_SINGLE_TRAJ_STATE,
)


@dataclass
class SingleTrajectoryAdaptiveConfig:
    # Candidates sampled around current state each step.
    batch_size: int = 8

    # Neighborhood scale adaptation (sigma).
    initial_sigma: float = 0.35
    min_sigma: float = 0.02
    max_sigma: float = 2.0
    target_success_rate: float = 0.25
    adapt_gain: float = 1.2
    success_window: int = 25

    # Stagnation handling.
    restart_patience: int = 20
    accept_worse_prob: float = 0.05

    # Scalar score mapping.
    objective_aggregation: str = "sum"  # "sum" | "first"
    violation_penalty: float = 1e6


class SingleTrajectoryAdaptiveAdapter(AlgorithmAdapter):
    """
    Adaptive single-trajectory local/global search.

    Workflow:
    - propose(): sample neighbors around current_x
    - update(): accept best/improving candidate, adapt sigma, optional restart
    """

    context_requires = ("generation",)
    context_provides = (KEY_SINGLE_TRAJ_STATE, KEY_SINGLE_TRAJ_SIGMA)
    context_mutates = (KEY_SINGLE_TRAJ_STATE, KEY_SINGLE_TRAJ_SIGMA)
    context_cache = ()
    context_notes = (
        "Maintains one active trajectory and adaptively updates mutation scale.",
    )
    state_recovery_level = "L1"
    state_recovery_notes = "Restores trajectory incumbent/best state and adaptive sigma history."

    def __init__(
        self,
        config: Optional[SingleTrajectoryAdaptiveConfig] = None,
        name: str = "single_trajectory_adaptive",
        priority: int = 0,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.cfg = config or SingleTrajectoryAdaptiveConfig()

        self.current_x: Optional[np.ndarray] = None
        self.current_score: Optional[float] = None
        self.best_x: Optional[np.ndarray] = None
        self.best_score: Optional[float] = None
        self.sigma: float = float(self.cfg.initial_sigma)
        self.no_improve_steps: int = 0
        self.success_history: Deque[int] = deque(maxlen=max(1, int(self.cfg.success_window)))
        self.step_count: int = 0
        self._rng = np.random.default_rng()

    def setup(self, solver: Any) -> None:
        self.current_x = None
        self.current_score = None
        self.best_x = None
        self.best_score = None
        self.sigma = float(self.cfg.initial_sigma)
        self.no_improve_steps = 0
        self.success_history = deque(maxlen=max(1, int(self.cfg.success_window)))
        self.step_count = 0

    def _score(self, objectives_row: np.ndarray, violation: float) -> float:
        if self.cfg.objective_aggregation == "first":
            obj = float(objectives_row[0])
        else:
            obj = float(np.sum(objectives_row))
        return float(violation) * float(self.cfg.violation_penalty) + obj

    def _build_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        ctx = dict(context)
        ctx[KEY_MUTATION_SIGMA] = float(self.sigma)
        ctx[KEY_SINGLE_TRAJ_SIGMA] = float(self.sigma)
        ctx[KEY_SINGLE_TRAJ_STATE] = {
            "step": int(self.step_count),
            "no_improve_steps": int(self.no_improve_steps),
            "best_score": self.best_score,
        }
        return ctx

    def propose(self, solver: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        if self.current_x is None:
            self.current_x = np.asarray(solver.init_candidate(context), dtype=float)

        ctx = self._build_context(context)
        out = []
        k = int(max(1, int(self.cfg.batch_size)))
        for _ in range(k):
            cand = solver.mutate_candidate(self.current_x, ctx)
            cand = solver.repair_candidate(cand, ctx)
            out.append(np.asarray(cand, dtype=float))
        return out

    def update(
        self,
        solver: Any,
        candidates: Sequence[np.ndarray],
        objectives: np.ndarray,
        violations: np.ndarray,
        context: Dict[str, Any],
    ) -> None:
        self.step_count += 1
        if candidates is None or len(candidates) == 0:
            return
        if objectives is None or len(objectives) == 0:
            return

        scores = np.asarray(
            [self._score(objectives[i], float(violations[i]) if violations is not None else 0.0) for i in range(len(candidates))],
            dtype=float,
        )
        idx = int(np.argmin(scores))
        cand = np.asarray(candidates[idx], dtype=float)
        cand_score = float(scores[idx])

        improved = False
        if self.current_score is None or cand_score < float(self.current_score):
            improved = True
            self.current_x = cand
            self.current_score = cand_score
        else:
            accept_prob = float(max(0.0, min(1.0, self.cfg.accept_worse_prob)))
            if self._rng.random() < accept_prob:
                self.current_x = cand
                self.current_score = cand_score

        if self.best_score is None or cand_score < float(self.best_score):
            self.best_x = cand
            self.best_score = cand_score

        if improved:
            self.no_improve_steps = 0
            self.success_history.append(1)
        else:
            self.no_improve_steps += 1
            self.success_history.append(0)

        success_rate = float(np.mean(self.success_history)) if self.success_history else 0.0
        # Multiplicative adaptation: push sigma to reach target success rate.
        delta = float(self.cfg.target_success_rate) - success_rate
        scale = float(np.exp(float(self.cfg.adapt_gain) * delta))
        self.sigma = float(np.clip(self.sigma * scale, float(self.cfg.min_sigma), float(self.cfg.max_sigma)))

        if self.no_improve_steps >= int(max(1, int(self.cfg.restart_patience))):
            self.current_x = np.asarray(solver.init_candidate(context), dtype=float)
            self.current_score = None
            self.no_improve_steps = 0

    def get_state(self) -> Dict[str, Any]:
        return {
            "current_x": None if self.current_x is None else self.current_x.tolist(),
            "current_score": self.current_score,
            "best_x": None if self.best_x is None else self.best_x.tolist(),
            "best_score": self.best_score,
            "sigma": float(self.sigma),
            "no_improve_steps": int(self.no_improve_steps),
            "success_history": list(self.success_history),
            "step_count": int(self.step_count),
        }

    def set_state(self, state: Dict[str, Any]) -> None:
        cx = state.get("current_x")
        bx = state.get("best_x")
        self.current_x = None if cx is None else np.asarray(cx, dtype=float)
        self.current_score = state.get("current_score")
        self.best_x = None if bx is None else np.asarray(bx, dtype=float)
        self.best_score = state.get("best_score")
        self.sigma = float(state.get("sigma", self.cfg.initial_sigma))
        self.no_improve_steps = int(state.get("no_improve_steps", 0))
        self.success_history = deque(
            [int(x) for x in state.get("success_history", [])],
            maxlen=max(1, int(self.cfg.success_window)),
        )
        self.step_count = int(state.get("step_count", 0))

    def get_runtime_context_projection(self, solver: Any) -> Dict[str, Any]:
        _ = solver
        return {
            KEY_MUTATION_SIGMA: float(self.sigma),
            KEY_SINGLE_TRAJ_SIGMA: float(self.sigma),
            KEY_SINGLE_TRAJ_STATE: {
                "step": int(self.step_count),
                "no_improve_steps": int(self.no_improve_steps),
                "best_score": self.best_score,
            },
        }

    def get_runtime_context_projection_sources(self, solver: Any) -> Dict[str, str]:
        _ = solver
        source = f"adapter.{self.__class__.__name__}"
        return {
            KEY_MUTATION_SIGMA: source,
            KEY_SINGLE_TRAJ_SIGMA: source,
            KEY_SINGLE_TRAJ_STATE: source,
        }
