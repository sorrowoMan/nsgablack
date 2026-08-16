"""
Finite-difference Gradient Descent adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from blackbase.contracts import BatchDisposition

from ..algorithm_adapter import AlgorithmAdapter
from ...utils.context.context_keys import KEY_ADAPTER_BEST_SCORE, KEY_MUTATION_SIGMA


@dataclass
class GradientDescentConfig:
    learning_rate: float = 0.15
    epsilon: float = 1e-3
    max_directions: int = 10
    lr_growth: float = 1.05
    lr_decay: float = 0.7
    min_lr: float = 1e-5
    objective_aggregation: str = "sum"


class GradientDescentAdapter(AlgorithmAdapter):
    context_requires = ()
    context_provides = (KEY_MUTATION_SIGMA, KEY_ADAPTER_BEST_SCORE)
    context_mutates = ()
    context_cache = ()
    context_notes = "Finite-difference local search; emits current step size in context."
    state_recovery_level = "L1"
    state_recovery_notes = "Restores current point/score and learning rate; finite-difference probe cache is recomputed."

    def __init__(
        self,
        config: Optional[GradientDescentConfig] = None,
        name: str = "gradient_descent",
        priority: int = 0,
        **config_kwargs,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.config = self.resolve_config(
            config=config,
            config_cls=GradientDescentConfig,
            config_kwargs=config_kwargs,
            adapter_name="GradientDescentAdapter",
        )
        self.cfg = self.config
        self.current_x: Optional[np.ndarray] = None
        self.current_score: Optional[float] = None
        self.learning_rate: float = float(self.cfg.learning_rate)
        self._pending_probes: List[Tuple[int, int]] = []
        self._runtime_projection: Dict[str, Any] = {}
        self._rng = np.random.default_rng()

    def setup(self, control: Any) -> None:
        self._rng = self.create_local_rng(control)
        self.current_x = None
        self.current_score = None
        self.learning_rate = float(self.cfg.learning_rate)
        self._pending_probes = []
        self._runtime_projection = {KEY_MUTATION_SIGMA: float(self.learning_rate)}

    def propose(self, control: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        if self.current_x is None:
            self.current_x = np.asarray(control.init_candidate(context), dtype=float)
        dim = int(self.current_x.shape[0])
        n_dirs = max(1, min(dim, int(self.cfg.max_directions)))
        dims = self._rng.choice(dim, size=n_dirs, replace=False)
        out = []
        eps = float(self.cfg.epsilon)
        for d in dims:
            plus = np.array(self.current_x, copy=True)
            minus = np.array(self.current_x, copy=True)
            plus[d] += eps
            minus[d] -= eps
            out.append(np.asarray(control.repair_candidate(plus, context), dtype=float))
            out.append(np.asarray(control.repair_candidate(minus, context), dtype=float))
        self._pending_probes = [
            (int(dimension), sign)
            for dimension in dims
            for sign in (1, -1)
        ]
        self._runtime_projection = {KEY_MUTATION_SIGMA: float(self.learning_rate)}
        return out

    def on_proposal_disposition(
        self,
        control: Any,
        disposition: BatchDisposition,
        context: Dict[str, Any],
    ) -> None:
        del control, context
        if disposition.proposed_count != len(self._pending_probes):
            raise ValueError(
                "Gradient-descent proposal disposition does not match pending probes: "
                f"proposed_count={disposition.proposed_count}, "
                f"pending_count={len(self._pending_probes)}"
            )
        self._pending_probes = [
            self._pending_probes[index]
            for index in disposition.accepted_indices
        ]

    def update(
        self,
        control: Any,
        candidates: Sequence[np.ndarray],
        feedback: Tuple[np.ndarray, np.ndarray],
        context: Dict[str, Any],
    ) -> None:
        objectives, violations = feedback
        if len(candidates) == 0:
            return
        if self.current_x is None:
            raise RuntimeError("GradientDescentAdapter.update requires a preceding propose call")
        if not self._pending_probes:
            raise RuntimeError("gradient-descent feedback has no pending finite-difference probes")

        scores = self._scores(objectives, violations)
        if len(candidates) != len(self._pending_probes) or scores.size != len(self._pending_probes):
            raise ValueError(
                "Gradient-descent feedback must align with the accepted finite-difference probes"
            )

        # Estimate a gradient only from dimensions whose +/- probes both survived
        # budget admission or another explicit upstream batch disposition.
        paired_scores: Dict[int, Dict[int, float]] = {}
        for (dimension, sign), score in zip(self._pending_probes, scores):
            paired_scores.setdefault(int(dimension), {})[int(sign)] = float(score)
        complete_pairs = {
            dimension: values
            for dimension, values in paired_scores.items()
            if 1 in values and -1 in values
        }
        if not complete_pairs:
            return

        grad = np.zeros_like(self.current_x, dtype=float)
        eps = max(float(self.cfg.epsilon), 1e-12)
        for dimension, values in complete_pairs.items():
            grad[dimension] = (values[1] - values[-1]) / (2.0 * eps)

        candidate = np.asarray(self.current_x - (self.learning_rate * grad), dtype=float)
        candidate = np.asarray(control.repair_candidate(candidate, context), dtype=float)

        # Use best observed directional score as acceptance proxy.
        best_score = float(np.min(scores))
        if self.current_score is None or best_score < self.current_score:
            self.current_x = candidate
            self.current_score = best_score
            self.learning_rate = max(float(self.cfg.min_lr), self.learning_rate * float(self.cfg.lr_growth))
        else:
            self.learning_rate = max(float(self.cfg.min_lr), self.learning_rate * float(self.cfg.lr_decay))

        self._runtime_projection = {
            KEY_MUTATION_SIGMA: float(self.learning_rate),
            KEY_ADAPTER_BEST_SCORE: None if self.current_score is None else float(self.current_score),
        }

    def get_runtime_context_projection(self, solver: Any) -> Dict[str, Any]:
        _ = solver
        return dict(self._runtime_projection)

    def get_runtime_context_projection_sources(self, solver: Any) -> Dict[str, str]:
        _ = solver
        source = f"adapter.{self.__class__.__name__}"
        return {k: source for k in self._runtime_projection.keys()}

    def get_state(self) -> Dict[str, Any]:
        return {
            "current_x": None if self.current_x is None else self.current_x.tolist(),
            "current_score": self.current_score,
            "learning_rate": float(self.learning_rate),
        }

    def set_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        x = state.get("current_x")
        self.current_x = None if x is None else np.asarray(x, dtype=float)
        score = state.get("current_score")
        self.current_score = None if score is None else float(score)
        self.learning_rate = float(state.get("learning_rate", self.cfg.learning_rate))
        self._runtime_projection = {
            KEY_MUTATION_SIGMA: float(self.learning_rate),
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
