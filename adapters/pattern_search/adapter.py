"""
Pattern Search adapter.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np

from ..unit_backed import UnitBackedAdapter, UnitField, UnitFeedbackField
from ...representation.structure_builders import PollUnitBuilder
from ..algorithm_adapter import AlgorithmAdapter
from nsgablack.context_keys import KEY_ADAPTER_BEST_SCORE, KEY_MUTATION_SIGMA


@dataclass
class PatternSearchConfig:
    max_directions: int = 12
    step_size: float = 0.2
    expansion: float = 1.2
    contraction: float = 0.6
    min_step: float = 1e-4
    objective_aggregation: str = "sum"


class PatternSearchAdapter(UnitBackedAdapter):
    unit_build_operations = ("initialize", "poll")
    accepts_proposal_replacement = True
    unit_builder_type = PollUnitBuilder
    unit_schema = PollUnitBuilder.unit_type.schema
    current_x = UnitField("current")
    current_score = UnitFeedbackField("current")

    context_requires = ()
    context_provides = (KEY_MUTATION_SIGMA, KEY_ADAPTER_BEST_SCORE)
    context_mutates = ()
    context_cache = ()
    context_notes = "Coordinate pattern search with adaptive step-size."
    state_recovery_level = "L1"
    state_recovery_notes = "Restores incumbent, step size and pipeline-built poll geometry."

    def __init__(
        self,
        config: Optional[PatternSearchConfig] = None,
        name: str = "pattern_search",
        priority: int = 0,
        **config_kwargs,
    ) -> None:
        super().__init__(name=name, priority=priority, unit_binding=config_kwargs.pop("unit_binding", None))
        self.config = self.resolve_config(
            config=config,
            config_cls=PatternSearchConfig,
            config_kwargs=config_kwargs,
            adapter_name="PatternSearchAdapter",
        )
        self.cfg = self.config
        self.current_x: Optional[np.ndarray] = None
        self.current_score: Optional[float] = None
        self.step_size: float = float(self.cfg.step_size)
        self._runtime_projection: Dict[str, Any] = {}
        self._rng = np.random.default_rng()

    def setup(self, control: Any) -> None:
        self._rng = self.create_local_rng(control)
        self.current_x = None
        self.current_score = None
        self.step_size = float(self.cfg.step_size)
        self._runtime_projection = {KEY_MUTATION_SIGMA: float(self.step_size)}

    def propose(self, control: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        if self.current_x is None:
            self.current_x = np.asarray(control.init_candidate(context), dtype=float)
        dim = int(self.current_x.shape[0])
        n_dirs = max(1, min(dim, int(self.cfg.max_directions)))
        dims = self._rng.choice(dim, size=n_dirs, replace=False)
        self.rebuild_unit("poll", dimensions=dims, context=context)
        out = []
        for direction in self.algorithm_unit.directions:
            point = self.current_x + float(self.step_size) * direction
            out.append(np.asarray(point, dtype=float))
        self.algorithm_unit.displacements = np.asarray(out) - self.current_x
        self._runtime_projection = {KEY_MUTATION_SIGMA: float(self.step_size)}
        return out

    def on_proposal_repair(self, control, repair, context):
        if repair.proposed_count != len(self.algorithm_unit.probes):
            raise ValueError("Pattern-search repair must align with pending probes")
        for row, index in enumerate(repair.proposal_indices):
            self.algorithm_unit.displacements[index] = repair.after.numeric_matrix[row] - self.current_x

    def update(
        self,
        control: Any,
        candidates: Sequence[np.ndarray],
        feedback: Any,
        context: Dict[str, Any],
    ) -> None:
        objectives, violations = feedback
        _ = control
        _ = context
        if candidates is None or len(candidates) == 0:
            return
        scores = self._scores(objectives, violations)
        best_idx = int(np.argmin(scores))
        best_score = float(scores[best_idx])
        if self.current_score is None or best_score < self.current_score:
            self.current_x = np.asarray(candidates[best_idx], dtype=float)
            self.current_score = best_score
            self.step_size = max(float(self.cfg.min_step), self.step_size * float(self.cfg.expansion))
        else:
            self.step_size = max(float(self.cfg.min_step), self.step_size * float(self.cfg.contraction))
        self._runtime_projection = {
            KEY_MUTATION_SIGMA: float(self.step_size),
            KEY_ADAPTER_BEST_SCORE: None if self.current_score is None else float(self.current_score),
        }

    def get_runtime_context_projection(self, solver: Any) -> Dict[str, Any]:
        _ = solver
        return {**self._runtime_projection, KEY_ADAPTER_BEST_SCORE: self.current_score}

    def get_runtime_context_projection_sources(self, solver: Any) -> Dict[str, str]:
        _ = solver
        source = f"adapter.{self.__class__.__name__}"
        return {k: source for k in self._runtime_projection.keys()}

    def _get_algorithm_state(self) -> Dict[str, Any]:
        return {
            "current_x": None if self.current_x is None else self.current_x.tolist(),
            "current_score": self.current_score,
            "step_size": float(self.step_size),
            "rng_state": copy.deepcopy(self._rng.bit_generator.state),
        }

    def _set_algorithm_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        x = state.get("current_x")
        self.current_x = None if x is None else np.asarray(x, dtype=float)
        score = state.get("current_score")
        self.current_score = None if score is None else float(score)
        self.step_size = float(state.get("step_size", self.cfg.step_size))
        rng_state = state.get("rng_state")
        if isinstance(rng_state, dict):
            self._rng.bit_generator.state = copy.deepcopy(rng_state)
        self._runtime_projection = {
            KEY_MUTATION_SIGMA: float(self.step_size),
            KEY_ADAPTER_BEST_SCORE: None if self.current_score is None else float(self.current_score),
        }

    def _scores(self, objectives: np.ndarray, violations: np.ndarray) -> np.ndarray:
        obj = np.asarray(objectives, dtype=float)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        vio = np.asarray(violations, dtype=float).reshape(-1)
        if str(self.cfg.objective_aggregation).lower() == "first":
            agg = obj[:, 0]
        else:
            agg = np.sum(obj, axis=1)
        return agg + (1e6 * vio)
