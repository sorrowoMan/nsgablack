"""
Finite-difference Gradient Descent adapter.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from blackbase.contracts import BatchDisposition

from ..unit_backed import UnitBackedAdapter, UnitField, UnitFeedbackField
from ...representation.structure_builders import PollUnitBuilder
from ..algorithm_adapter import AlgorithmAdapter
from nsgablack.context_keys import KEY_ADAPTER_BEST_SCORE, KEY_MUTATION_SIGMA


@dataclass
class GradientDescentConfig:
    learning_rate: float = 0.15
    epsilon: float = 1e-3
    max_directions: int = 10
    lr_growth: float = 1.05
    lr_decay: float = 0.7
    min_lr: float = 1e-5
    objective_aggregation: str = "sum"
    repair_policy: str = "coordinate"  # coordinate displacement | reject changes

    def __post_init__(self):
        if self.repair_policy not in {"coordinate", "reject"}:
            raise ValueError("Finite-difference repair_policy must be coordinate or reject")


class GradientDescentAdapter(UnitBackedAdapter):
    unit_build_operations = ("initialize", "poll")
    unit_builder_type = PollUnitBuilder
    unit_schema = PollUnitBuilder.unit_type.schema
    current_x = UnitField("current")
    # A directional-score proxy, invalidated when its associated center changes.
    current_score = UnitFeedbackField("current")
    _pending_probes = UnitField("probes")
    admission_unit_fields = ("probes", "directions", "displacements")

    context_requires = ()
    context_provides = (KEY_MUTATION_SIGMA, KEY_ADAPTER_BEST_SCORE)
    context_mutates = ()
    context_cache = ()
    context_notes = "Finite-difference local search; emits current step size in context."
    state_recovery_level = "L1"
    state_recovery_notes = "Restores point, learning rate, probe identities and actual displacement structure."

    def __init__(
        self,
        config: Optional[GradientDescentConfig] = None,
        name: str = "gradient_descent",
        priority: int = 0,
        **config_kwargs,
    ) -> None:
        super().__init__(name=name, priority=priority, unit_binding=config_kwargs.pop("unit_binding", None))
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
        self.rebuild_unit("poll", dimensions=dims, context=context)
        out = []
        eps = float(self.cfg.epsilon)
        for direction in self.algorithm_unit.directions:
            point = self.current_x + eps * direction
            out.append(np.asarray(point, dtype=float))
        self.algorithm_unit.displacements = np.asarray(out) - self.current_x
        self._runtime_projection = {KEY_MUTATION_SIGMA: float(self.learning_rate)}
        return out

    def _validate_probe_displacement(self, dimension, sign, displacement):
        others = np.delete(displacement, dimension)
        if not np.allclose(others, 0.0, atol=1e-12, rtol=0):
            raise ValueError("Repair changed the finite-difference coordinate geometry")
        if self.cfg.repair_policy == "reject" and not np.isclose(
                displacement[dimension], sign * float(self.cfg.epsilon), atol=1e-12, rtol=1e-8):
            raise ValueError("Repair changed the finite-difference step")

    def on_proposal_repair(self, control, repair, context):
        if repair.proposed_count != len(self._pending_probes):
            raise ValueError("Gradient-descent repair must align with pending probes")
        for row, index in enumerate(repair.proposal_indices):
            displacement = repair.after.numeric_matrix[row] - self.current_x
            self._validate_probe_displacement(*self._pending_probes[index], displacement)
            self.algorithm_unit.displacements[index] = displacement

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
        rows = list(disposition.accepted_indices)
        if self.algorithm_unit.directions is not None:
            self.algorithm_unit.directions = self.algorithm_unit.directions[rows]
        if self.algorithm_unit.displacements is not None:
            self.algorithm_unit.displacements = self.algorithm_unit.displacements[rows]

    def update(
        self,
        control: Any,
        candidates: Sequence[np.ndarray],
        feedback: Any,
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
        paired_steps: Dict[int, Dict[int, float]] = {}
        actual = np.asarray(candidates, dtype=float) - self.current_x
        self.algorithm_unit.displacements = actual.copy()
        for (dimension, sign), score, displacement in zip(self._pending_probes, scores, actual):
            self._validate_probe_displacement(dimension, sign, displacement)
            paired_scores.setdefault(int(dimension), {})[int(sign)] = float(score)
            paired_steps.setdefault(int(dimension), {})[int(sign)] = float(displacement[dimension])
        complete_pairs = {
            dimension: values
            for dimension, values in paired_scores.items()
            if 1 in values and -1 in values
        }
        if not complete_pairs:
            return

        grad = np.zeros_like(self.current_x, dtype=float)
        for dimension, values in complete_pairs.items():
            width = paired_steps[dimension][1] - paired_steps[dimension][-1]
            if abs(width) > 1e-12:
                grad[dimension] = (values[1] - values[-1]) / width

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
        return {**self._runtime_projection, KEY_ADAPTER_BEST_SCORE: self.current_score}

    def get_runtime_context_projection_sources(self, solver: Any) -> Dict[str, str]:
        _ = solver
        source = f"adapter.{self.__class__.__name__}"
        return {k: source for k in self._runtime_projection.keys()}

    def _get_algorithm_state(self) -> Dict[str, Any]:
        return {
            "current_x": None if self.current_x is None else self.current_x.tolist(),
            "current_score": self.current_score,
            "learning_rate": float(self.learning_rate),
            "pending_probes": [list(item) for item in self._pending_probes],
            "rng_state": copy.deepcopy(self._rng.bit_generator.state),
        }

    def _set_algorithm_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        x = state.get("current_x")
        self.current_x = None if x is None else np.asarray(x, dtype=float)
        score = state.get("current_score")
        self.current_score = None if score is None else float(score)
        self.learning_rate = float(state.get("learning_rate", self.cfg.learning_rate))
        self._pending_probes = [
            (int(item[0]), int(item[1]))
            for item in tuple(state.get("pending_probes", ()) or ())
        ]
        rng_state = state.get("rng_state")
        if isinstance(rng_state, dict):
            self._rng.bit_generator.state = copy.deepcopy(rng_state)
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
