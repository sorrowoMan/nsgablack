"""
Single-trajectory adaptive search adapter.

This adapter keeps one active trajectory (current solution) and adapts
neighborhood scale online from observed improvement rate.
"""

from __future__ import annotations

import copy
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Optional, Sequence, Tuple

import numpy as np

from ..unit_backed import UnitBackedAdapter, UnitField, UnitFeedbackField
from ..pool_results import PoolRefinementState
from ...representation.structure_builders import TrajectoryUnitBuilder
from ..algorithm_adapter import AlgorithmAdapter
from nsgablack.context_keys import (
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


class SingleTrajectoryAdaptiveAdapter(UnitBackedAdapter):
    """
    Adaptive single-trajectory local/global search.

    Workflow:
    - propose(): sample neighbors around current_x
    - update(): accept best/improving candidate, adapt sigma, optional restart
    """
    uses_pipeline_mutation = True
    pool_input_modes = ("initialize",)
    supports_pool_restart = True
    supports_objective_projection = True
    accepts_proposal_replacement = True
    unit_builder_type = TrajectoryUnitBuilder
    unit_schema = TrajectoryUnitBuilder.unit_type.schema
    current_x = UnitField("current")
    best_x = UnitField("best")
    current_score = UnitFeedbackField("current")
    best_score = UnitFeedbackField("best")


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
        **config_kwargs,
    ) -> None:
        super().__init__(name=name, priority=priority, unit_binding=config_kwargs.pop("unit_binding", None))
        self.config = self.resolve_config(
            config=config,
            config_cls=SingleTrajectoryAdaptiveConfig,
            config_kwargs=config_kwargs,
            adapter_name="SingleTrajectoryAdaptiveAdapter",
        )
        self.cfg = self.config

        self.current_x: Optional[np.ndarray] = None
        self.current_score: Optional[float] = None
        self.best_x: Optional[np.ndarray] = None
        self.best_score: Optional[float] = None
        self.sigma: float = float(self.cfg.initial_sigma)
        self.no_improve_steps: int = 0
        self.success_history: Deque[int] = deque(maxlen=max(1, int(self.cfg.success_window)))
        self.step_count: int = 0
        self._rng = np.random.default_rng()
        self._pool_results = PoolRefinementState()

    def default_pool_input_count(self):
        return 1

    def restart_search(self, control, context):
        """Reset one task's trajectory and best result without resetting its RNG."""
        self.reset_unit()
        self.current_x = self.best_x = None
        self.current_score = self.best_score = None
        self.sigma = float(self.cfg.initial_sigma)
        self.no_improve_steps = 0
        self.success_history = deque(maxlen=max(1, int(self.cfg.success_window)))
        self.step_count = 0
        self._pool_results = PoolRefinementState()

    def get_solution_pool_roots(self, control):
        return self._pool_results.roots(control)

    def get_pool_refinement_results(self, control):
        """Return task-best, including when the current trajectory moved away."""
        return self._pool_results.results(control)

    def setup(self, control: Any) -> None:
        self._rng = self.create_local_rng(control)
        self.restart_search(control, {})

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

    def propose(self, control: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        if self.current_x is None:
            seed = control.init_candidate(context)
            self.current_x = np.asarray(seed, dtype=float)
            self._pool_results.remember_seed(control, seed)
        if self.current_score is None:
            return [self._pool_results.project_current(control, self.current_x, semantic=True)]

        ctx = self._build_context(context)
        out = []
        k = int(max(1, int(self.cfg.batch_size)))
        for _ in range(k):
            parent = self._pool_results.project_current(control, self.current_x)
            cand = self.mutate_candidate(control, parent, ctx)
            out.append(cand)
        return out

    def _proposal_contexts(self, proposed_count, context):
        return tuple(self._build_context(context) for _ in range(proposed_count))

    def update(
        self,
        control: Any,
        candidates: Sequence[np.ndarray],
        feedback: Any,
        context: Dict[str, Any],
    ) -> None:
        objectives, violations = feedback
        self.step_count += 1
        if candidates is None or len(candidates) == 0:
            return
        if objectives is None or len(objectives) == 0:
            return

        scores, violations = self._pool_results.scores(feedback, lambda f, v:
            [self._score(row, float(v[i])) for i, row in enumerate(f)])
        idx = min(range(len(candidates)), key=lambda i: self._pool_results.key(scores[i], violations[i]))
        cand = np.asarray(candidates[idx], dtype=float)
        cand_score = float(scores[idx])
        if self._pool_results.observe_best(control, candidates, feedback, idx, cand_score, violations[idx]):
            self.best_x = np.array(cand, copy=True)
            self.best_score = cand_score

        if self.current_score is None:
            if len(candidates) != 1:
                raise ValueError("Single-trajectory baseline feedback requires one candidate")
            self.current_x = np.array(cand, copy=True)
            self.current_score = cand_score
            self._pool_results.current = self._pool_results.capture(
                control, candidates, feedback, idx, cand_score, violations[idx])
            return

        improved = False
        if self._pool_results.improves_current(cand_score, violations[idx], self.current_score):
            improved = True
            self.current_x = cand
            self.current_score = cand_score
            self._pool_results.current = self._pool_results.capture(
                control, candidates, feedback, idx, cand_score, violations[idx])
        else:
            accept_prob = float(max(0.0, min(1.0, self.cfg.accept_worse_prob)))
            if self._pool_results.permits_exploration(violations[idx]) and self._rng.random() < accept_prob:
                self.current_x = cand
                self.current_score = cand_score
                self._pool_results.current = self._pool_results.capture(
                    control, candidates, feedback, idx, cand_score, violations[idx])

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
            seed = control.init_candidate(context)
            self.current_x = np.asarray(seed, dtype=float)
            self.current_score = None
            self._pool_results.current = None
            self._pool_results.remember_seed(control, seed)
            self.no_improve_steps = 0

    def _get_algorithm_state(self) -> Dict[str, Any]:
        return {
            "current_x": None if self.current_x is None else self.current_x.tolist(),
            "current_score": self.current_score,
            "best_x": None if self.best_x is None else self.best_x.tolist(),
            "best_score": self.best_score,
            "sigma": float(self.sigma),
            "no_improve_steps": int(self.no_improve_steps),
            "success_history": list(self.success_history),
            "step_count": int(self.step_count),
            "rng_state": copy.deepcopy(self._rng.bit_generator.state),
            "pool_refinement": self._pool_results.as_dict(),
        }

    def _set_algorithm_state(self, state: Dict[str, Any]) -> None:
        cx = state.get("current_x")
        bx = state.get("best_x")
        self.current_x = None if cx is None else np.asarray(cx, dtype=float)
        self.current_score = state.get("current_score")
        self.best_x = None if bx is None else np.asarray(bx, dtype=float)
        self.best_score = state.get("best_score")
        self._pool_results = PoolRefinementState.from_dict(state.get("pool_refinement"))
        self.sigma = float(state.get("sigma", self.cfg.initial_sigma))
        self.no_improve_steps = int(state.get("no_improve_steps", 0))
        self.success_history = deque(
            [int(x) for x in state.get("success_history", [])],
            maxlen=max(1, int(self.cfg.success_window)),
        )
        self.step_count = int(state.get("step_count", 0))
        rng_state = state.get("rng_state")
        if isinstance(rng_state, dict):
            self._rng.bit_generator.state = copy.deepcopy(rng_state)

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
