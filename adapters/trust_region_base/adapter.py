"""
Shared base for trust-region adapters.
"""

from __future__ import annotations

import copy
from abc import abstractmethod
from typing import Any, Dict, Optional, Sequence, Tuple, List

import numpy as np

from ..unit_backed import UnitBackedAdapter, UnitField, UnitFeedbackField
from ...representation.structure_builders import RegionUnitBuilder
from ..pool_results import PoolRefinementState
from nsgablack.context_keys import KEY_SOLUTION_INPUT_REF


class TrustRegionBaseAdapter(UnitBackedAdapter):
    """
    Common trust-region behavior:
    - center initialization
    - trust-radius expand/shrink
    - candidate propose loop
    - state roundtrip
    """
    accepts_proposal_replacement = True
    pool_input_modes = ("initialize",)
    supports_pool_restart = True
    supports_objective_projection = True
    unit_builder_type = RegionUnitBuilder
    unit_schema = RegionUnitBuilder.unit_type.schema
    _center = UnitField("center")
    _best_score = UnitFeedbackField("center")
    _basis = UnitField("basis")
    _weights = UnitField("weights")

    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Shared trust-region base class; concrete adapters define sampling and scoring."
    state_recovery_level = "L1"
    state_recovery_notes = "Restores center/radius/best score and subclass extra state."

    def __init__(
        self,
        config: Any,
        *,
        name: str,
        priority: int = 0,
        random_seed: Optional[int] = None,
        unit_binding=None,
    ) -> None:
        super().__init__(name=name, priority=priority, unit_binding=unit_binding)
        self.cfg = config
        self._rng = np.random.default_rng(random_seed)
        self._center: Optional[np.ndarray] = None
        self._radius: float = float(getattr(self.cfg, "initial_radius", 0.5))
        self._best_score: Optional[float] = None
        self._pool_results = PoolRefinementState()
        self._selection_objectives = {"current": None, "best": None}
        self._pool_input_task = False
        self._seed_baseline = False

    def setup(self, control: Any) -> None:
        self._rng = self.create_local_rng(control, seed=getattr(self.cfg, "random_seed", None))
        self.restart_search(control, {})

    def default_pool_input_count(self):
        return 1

    def restart_search(self, control, context):
        self.reset_unit()
        self._radius = float(getattr(self.cfg, "initial_radius", 0.5))
        self._center = None
        self._best_score = None
        self._pool_results = PoolRefinementState()
        self._selection_objectives = {"current": None, "best": None}
        self._pool_input_task = False
        self._seed_baseline = False
        self._reset_internal_state(control)

    def get_solution_pool_roots(self, control):
        self._validate_current(control)
        return self._pool_results.roots(control)

    def get_pool_refinement_results(self, control):
        self._validate_current(control)
        return self._pool_results.results(control)

    def _validate_current(self, control):
        selected = self._pool_results.current
        if selected is not None:
            if self._best_score != selected.score:
                raise ValueError("trust-region center differs from its selected feedback")
            self._pool_results.validate(control, selected, candidate=self._center)

    def propose(self, control: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        if self._center is None or (self._pool_results.current is None
                                    and context.get(KEY_SOLUTION_INPUT_REF) is not None):
            seed = self._init_center(control, context)
            self._center = np.asarray(seed, dtype=float).copy()
            self._best_score = None
            self._pool_results.remember_seed(control, seed)
            self._pool_input_task = bool(context.get(KEY_SOLUTION_INPUT_REF))
            self._seed_baseline = True
        self._validate_current(control)
        # A task input is an unevaluated starting point under this comparison
        # frame. It must consume its own accepted step before any neighbors.
        if self._best_score is None:
            return [self._pool_results.project_current(control, self._center, semantic=True)]

        self._before_propose(control, context)
        center = np.asarray(self._center, dtype=float)
        n = max(1, int(getattr(self.cfg, "batch_size", 1)))
        candidates: List[np.ndarray] = []
        if bool(getattr(self.cfg, "include_center", True)):
            candidates.append(self._pool_results.project_current(control, center, semantic=True))
        while len(candidates) < n:
            delta = np.asarray(self._sample_delta(control, context), dtype=float)
            cand = center + (delta * float(self._radius))
            cand = self._clip_to_bounds(cand, control)
            candidates.append(self._pool_results.derive_candidate(control, cand, stage="trust_region"))
        self._after_propose(control, context)
        return candidates

    def _repair_within_region(self, candidate: np.ndarray) -> bool:
        # DFO/MO/nonsmooth sample a box, so radius uses the infinity norm.
        delta = np.asarray(candidate, dtype=float) - np.asarray(self._center, dtype=float)
        return bool(np.all(np.isfinite(delta)) and np.max(np.abs(delta), initial=0.0)
                    <= self._radius + 1e-12 * max(1.0, abs(self._radius)))

    def on_proposal_repair(self, control, repair, context):
        if self._seed_baseline:
            if repair.proposed_count != 1:
                raise ValueError("Trust-region baseline requires one candidate")
            # No region has been accepted yet. The repaired, accepted seed
            # establishes the center; neighbors will be constrained to it.
            return
        for row in repair.changed_rows:
            if self._center is None or not self._repair_within_region(repair.after.numeric_matrix[row]):
                raise ValueError(f"{self.name}: repair moved candidate outside the trust region")

    def update(
        self,
        control: Any,
        candidates: Sequence[np.ndarray],
        feedback: Any,
        context: Dict[str, Any],
    ) -> None:
        objectives, violations = feedback
        if candidates is None or len(candidates) == 0:
            return
        scores, violations = self._pool_results.scores(
            feedback, lambda f, v: self._score(control, f, v, context))
        if scores.size == 0:
            return
        best_idx = min(range(len(candidates)), key=lambda i: self._pool_results.key(scores[i], violations[i]))
        best_score = float(scores[best_idx])
        baseline = self._best_score is None
        if baseline and len(candidates) != 1:
            raise ValueError("Trust-region baseline feedback requires one candidate")
        improved = baseline or self._pool_results.improves_current(best_score, violations[best_idx], self._best_score)
        # Native trust-region tolerance controls radius/center movement. A
        # projected task must preserve its owner's exact feasibility ordering.
        if improved and not baseline and self._pool_results.projection is None:
            improved = float(self._best_score) - best_score > float(getattr(self.cfg, "success_tolerance", 1e-8))
        if self._pool_results.observe_best(control, candidates, feedback, best_idx, best_score, violations[best_idx]):
            self._selection_objectives["best"] = np.asarray(objectives[best_idx], dtype=float).reshape(-1).tolist()
        if improved:
            self._center = np.asarray(candidates[best_idx], dtype=float).copy()
            self._best_score = best_score
            self._pool_results.current = self._pool_results.capture(
                control, candidates, feedback, best_idx, best_score, violations[best_idx])
            self._selection_objectives["current"] = np.asarray(objectives[best_idx], dtype=float).reshape(-1).tolist()
            if not baseline:
                self._radius = min(
                    float(self._radius) * float(getattr(self.cfg, "radius_expand", 1.5)),
                    float(getattr(self.cfg, "max_radius", 2.0)),
                )
        else:
            self._radius = max(
                float(self._radius) * float(getattr(self.cfg, "radius_shrink", 0.7)),
                float(getattr(self.cfg, "min_radius", 1e-6)),
            )
        self._seed_baseline = False
        self._record_reference_samples(control, candidates, feedback, scores, violations)
        self._after_update(control, candidates, objectives, violations, context, improved=improved)

    def _get_algorithm_state(self) -> Dict[str, Any]:
        state: Dict[str, Any] = {
            "center": None if self._center is None else self._center.tolist(),
            "radius": float(self._radius),
            "best_score": None if self._best_score is None else float(self._best_score),
            "rng_state": copy.deepcopy(self._rng.bit_generator.state),
            "pool_refinement": self._pool_results.as_dict(),
            "selection_objectives": copy.deepcopy(self._selection_objectives),
            "pool_input_task": self._pool_input_task,
            "seed_baseline": self._seed_baseline,
        }
        extra = self._extra_state()
        if extra:
            state.update(extra)
        return state

    def _set_algorithm_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        center = state.get("center")
        self._center = None if center is None else np.asarray(center, dtype=float)
        if state.get("radius") is not None:
            self._radius = float(state["radius"])
        self._best_score = state.get("best_score")
        self._pool_results = PoolRefinementState.from_dict(state.get("pool_refinement"))
        self._selection_objectives = copy.deepcopy(state.get("selection_objectives", {"current": None, "best": None}))
        self._pool_input_task = bool(state.get("pool_input_task", False))
        self._seed_baseline = bool(state.get("seed_baseline", False))
        rng_state = state.get("rng_state")
        if isinstance(rng_state, dict):
            self._rng.bit_generator.state = copy.deepcopy(rng_state)
        self._load_extra_state(state)

    def _init_center(self, control: Any, context: Optional[Dict[str, Any]] = None) -> np.ndarray:
        return control.init_candidate(context)

    def _extract_bounds(self, control: Any) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        bounds = getattr(getattr(control, "problem", None), "bounds", None)
        if bounds is None:
            return None, None
        if isinstance(bounds, dict):
            vals = list(bounds.values())
        else:
            vals = list(bounds)
        low = np.asarray([float(v[0]) for v in vals], dtype=float)
        high = np.asarray([float(v[1]) for v in vals], dtype=float)
        return low, high

    def _clip_to_bounds(self, x: np.ndarray, control: Any) -> np.ndarray:
        low, high = self._extract_bounds(control)
        if low is None or high is None:
            return x
        return np.minimum(np.maximum(x, low), high)

    # Hooks
    def _record_reference_samples(self, control, candidates, feedback, scores, violations):
        """A subclass may retain evaluated samples from this accepted batch."""

    def _reset_internal_state(self, control: Any) -> None:
        _ = control

    def _before_propose(self, control: Any, context: Dict[str, Any]) -> None:
        _ = control, context

    def _after_propose(self, control: Any, context: Dict[str, Any]) -> None:
        _ = control, context

    def _after_update(
        self,
        control: Any,
        candidates: Sequence[np.ndarray],
        objectives: np.ndarray,
        violations: np.ndarray,
        context: Dict[str, Any],
        *,
        improved: bool,
    ) -> None:
        _ = control, candidates, objectives, violations, context, improved

    def _extra_state(self) -> Dict[str, Any]:
        return {}

    def _load_extra_state(self, state: Dict[str, Any]) -> None:
        _ = state

    # Required in subclasses
    @abstractmethod
    def _sample_delta(self, control: Any, context: Dict[str, Any]) -> np.ndarray:
        raise NotImplementedError

    @abstractmethod
    def _score(
        self,
        control: Any,
        objectives: np.ndarray,
        violations: np.ndarray,
        context: Dict[str, Any],
    ) -> np.ndarray:
        raise NotImplementedError
