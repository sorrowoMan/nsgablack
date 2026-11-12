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
from ..pool_results import PoolRefinementState
from ...core.evaluation_feedback import OptimizationFeedbackBatch
from ...units.contracts import candidate_array
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
    operation_methods = {"initializer": "initialize", "repair": "repair"}
    pool_input_modes = ("initialize",)
    supports_pool_restart = True
    supports_objective_projection = True
    unit_build_operations = ("initialize", "poll")
    unit_builder_type = PollUnitBuilder
    unit_schema = PollUnitBuilder.unit_type.schema
    current_x = UnitField("current")
    # Only the center's own evaluated feedback is associated with this value.
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
        *,
        initializer=None,
        repair=None,
        **config_kwargs,
    ) -> None:
        super().__init__(name=name, priority=priority, unit_binding=config_kwargs.pop("unit_binding", None))
        self.set_initializer(initializer)
        self.set_repair(repair)
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
        self._pool_results = PoolRefinementState()
        self._pending_stage = None
        self._trial_values = None

    def setup(self, control: Any) -> None:
        self.reset_unit()
        self._rng = self.create_local_rng(control)
        self.seed_operator_bindings(self._rng)
        self.current_x = None
        self.current_score = None
        self.learning_rate = float(self.cfg.learning_rate)
        self._pending_probes = []
        self._runtime_projection = {KEY_MUTATION_SIGMA: float(self.learning_rate)}
        self._pool_results = PoolRefinementState()
        self._pending_stage = None
        self._trial_values = None

    def propose(self, control: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        from nsgablack.context_keys import KEY_SOLUTION_INPUT_REF
        self._validate_pool_candidate(control)
        if self.current_x is None or (self.current_score is None and context.get(KEY_SOLUTION_INPUT_REF) is not None):
            seed = self.init_candidate(control, context)
            self.current_x = candidate_array(seed).copy()
            self._pool_results.remember_seed(control, seed)
        if self.current_score is None:
            self._pending_stage = "baseline"
            return (self._pool_results.project_current(control, self.current_x, semantic=True),)
        if self._trial_values is not None:
            self._pending_stage = "trial"
            return (self._pool_results.derive_candidate(control, self._trial_values, stage="gradient_trial"),)
        self._pending_stage = "probe"
        dim = int(self.current_x.shape[0])
        n_dirs = max(1, min(dim, int(self.cfg.max_directions)))
        dims = self._rng.choice(dim, size=n_dirs, replace=False)
        self.rebuild_unit("poll", dimensions=dims, context=context)
        out = []
        eps = float(self.cfg.epsilon)
        for direction in self.ensure_unit().directions:
            point = self.current_x + eps * direction
            out.append(self._pool_results.derive_candidate(control, point, stage="gradient_probe"))
        self.ensure_unit().displacements = np.asarray([candidate_array(row) for row in out]) - self.current_x
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
        if self._pending_stage in {"baseline", "trial"}:
            if repair.proposed_count != 1:
                raise ValueError("Gradient-descent center/trial repair requires one proposal")
            if repair.proposal_indices and repair.after.numeric_matrix.shape[1:] != self.current_x.shape:
                raise ValueError("Gradient-descent repair must preserve dimension")
            return
        if repair.proposed_count != len(self._pending_probes):
            raise ValueError("Gradient-descent repair must align with pending probes")
        for row, index in enumerate(repair.proposal_indices):
            displacement = repair.after.numeric_matrix[row] - self.current_x
            self._validate_probe_displacement(*self._pending_probes[index], displacement)
            self.ensure_unit().displacements[index] = displacement

    def on_proposal_disposition(
        self,
        control: Any,
        disposition: BatchDisposition,
        context: Dict[str, Any],
    ) -> None:
        del control, context
        if self._pending_stage in {"baseline", "trial"}:
            if disposition.proposed_count != 1:
                raise ValueError("Gradient-descent center/trial disposition requires one proposal")
            return
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
        unit = self.algorithm_unit
        if unit is not None:
            if unit.directions is not None:
                unit.directions = unit.directions[rows]
            if unit.displacements is not None:
                unit.displacements = unit.displacements[rows]

    def update(
        self,
        control: Any,
        candidates: Sequence[np.ndarray],
        feedback: Any,
        context: Dict[str, Any],
    ) -> None:
        feedback = OptimizationFeedbackBatch.coerce(feedback)
        objectives, violations = feedback
        if feedback.candidate_count != len(candidates):
            raise ValueError("Gradient-descent feedback must align with candidates")
        if len(candidates) == 0:
            return
        if self.current_x is None:
            raise RuntimeError("GradientDescentAdapter.update requires a preceding propose call")
        scores, violations = self._pool_results.scores(feedback, self._scores)
        for index in range(len(candidates)):
            self._pool_results.observe_best(control, candidates, feedback, index, scores[index], violations[index])
        if self._pending_stage in {"baseline", "trial"}:
            if len(candidates) != 1:
                raise ValueError("Gradient-descent center/trial feedback requires one candidate")
            improved = self._pool_results.improves_current(scores[0], violations[0], self.current_score)
            if self._pending_stage == "baseline" or improved:
                self.current_x = candidate_array(candidates[0]).copy()
                self.current_score = float(scores[0])
                self._pool_results.current = self._pool_results.capture(control, candidates, feedback, 0, scores[0], violations[0])
            if self._pending_stage == "trial":
                factor = self.cfg.lr_growth if improved else self.cfg.lr_decay
                self.learning_rate = max(float(self.cfg.min_lr), self.learning_rate * float(factor))
            self._trial_values, self._pending_stage = None, None
            self._refresh_runtime_projection()
            return
        if not self._pending_probes:
            raise RuntimeError("gradient-descent feedback has no pending finite-difference probes")
        if len(candidates) != len(self._pending_probes) or scores.size != len(self._pending_probes):
            raise ValueError(
                "Gradient-descent feedback must align with the accepted finite-difference probes"
            )

        # Estimate a gradient only from dimensions whose +/- probes both survived
        # budget admission or another explicit upstream batch disposition.
        paired_scores: Dict[int, Dict[int, float]] = {}
        paired_steps: Dict[int, Dict[int, float]] = {}
        actual = np.asarray([candidate_array(row) for row in candidates]) - self.current_x
        self.ensure_unit().displacements = actual.copy()
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
            self._pending_stage = None
            return

        grad = np.zeros_like(self.current_x, dtype=float)
        for dimension, values in complete_pairs.items():
            width = paired_steps[dimension][1] - paired_steps[dimension][-1]
            if abs(width) > 1e-12:
                grad[dimension] = (values[1] - values[-1]) / width

        # This is an unassessed proposal. Repair and evaluation happen on the
        # next dispatch, before it can replace the evaluated center.
        self._trial_values = np.asarray(self.current_x - (self.learning_rate * grad), dtype=float)
        self._pending_stage = None
        self._refresh_runtime_projection()

    def _refresh_runtime_projection(self):
        self._runtime_projection = {
            KEY_MUTATION_SIGMA: float(self.learning_rate),
            KEY_ADAPTER_BEST_SCORE: None if self.current_score is None else float(self.current_score),
        }

    def default_pool_input_count(self):
        return 1

    def restart_search(self, control, context=None):
        self.reset_unit()
        self.current_x = self.current_score = None
        self.learning_rate = float(self.cfg.learning_rate)
        self._pending_probes = []
        self._pool_results = PoolRefinementState()
        self._pending_stage = self._trial_values = None
        self._refresh_runtime_projection()

    def get_solution_pool_roots(self, control):
        if self.current_score is not None and self._pool_results.current is None:
            raise ValueError("Gradient center requires exact evaluated pool evidence")
        self._validate_pool_candidate(control)
        return self._pool_results.roots(control)

    def get_pool_refinement_results(self, control):
        self._validate_pool_candidate(control)
        return self._pool_results.results(control)

    def _validate_pool_candidate(self, control):
        selected = self._pool_results.current
        if selected is not None and selected.ref is not None:
            if self.current_x is None:
                raise ValueError("Gradient evaluated pool selection requires its center")
            # _trial_values is a separate unevaluated successor; current_x is
            # always the evaluated center, including during a pending trial.
            PoolRefinementState.validate(control, selected, candidate=self.current_x)
            if self.current_score is None or float(self.current_score) != selected.score:
                raise ValueError("Gradient center score differs from its pool selection")

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
            "pool_results": self._pool_results.as_dict(),
            "pending_stage": self._pending_stage,
            "trial_values": None if self._trial_values is None else self._trial_values.tolist(),
        }

    def _set_algorithm_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        self._pool_results = PoolRefinementState.from_dict(state.get("pool_results"))
        self._pending_stage = state.get("pending_stage")
        if self._pending_stage not in {None, "baseline", "probe", "trial"}:
            raise ValueError("Invalid gradient-descent pending stage")
        self._trial_values = None if state.get("trial_values") is None else np.asarray(state["trial_values"], dtype=float)
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
