"""
Model-and-Search (MAS) adapter: alternates model update and search steps.
"""

from __future__ import annotations
from blackbase.plugin import report_soft_error as _report_optional_failure

import copy
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from ..unit_backed import UnitBackedAdapter, UnitField
from ...representation.structure_builders import ModelSearchUnitBuilder
from ..algorithm_adapter import AlgorithmAdapter
from ..pool_results import PoolRefinementState
from ...core.evaluation_feedback import OptimizationFeedbackBatch
from ...core.state.solution_pool import SolutionRef
from ...units.contracts import candidate_array
from ...utils.surrogate.vector_surrogate import VectorSurrogate


@dataclass
class MASConfig:
    batch_size: int = 16
    exploration_ratio: float = 0.4
    random_seed: Optional[int] = None
    enable_surrogate: bool = True
    surrogate_model_type: str = "rf"
    surrogate_min_train_samples: int = 20
    surrogate_max_train_samples: int = 5000
    surrogate_retrain_every_call: bool = True


class MASAdapter(UnitBackedAdapter):
    """
    MAS adapter (model-and-search).

    This adapter maintains an optional internal surrogate model for exploitation.
    """
    operation_methods = {"initializer": "initialize", "repair": "repair"}
    unit_builder_methods = ("create_model",)
    accepts_proposal_replacement = True
    pool_input_modes = ("initialize",)
    supports_pool_restart = True
    supports_objective_projection = True
    unit_builder_type = ModelSearchUnitBuilder
    unit_schema = ModelSearchUnitBuilder.unit_type.schema
    _center = UnitField("center")
    _X = UnitField("history_x")
    _Y = UnitField("history_y")

    context_requires = ("generation",)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Optional model-assisted search using internal surrogate.",)
    state_recovery_level = "L1"
    state_recovery_notes = "Restores adaptive center; surrogate cache is rebuilt from adapter history."

    def __init__(
        self,
        config: Optional[MASConfig] = None,
        name: str = "mas",
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
            config_cls=MASConfig,
            config_kwargs=config_kwargs,
            adapter_name="MASAdapter",
        )
        self.cfg = self.config
        self._rng = np.random.default_rng(self.cfg.random_seed)
        self._center: Optional[np.ndarray] = None
        self._surrogate: Optional[VectorSurrogate] = None
        self._X: list[np.ndarray] = []
        self._Y: list[np.ndarray] = []
        self.solver: Any = None
        self._pool_results = PoolRefinementState()
        self._history_refs = []

    def setup(self, control: Any) -> None:
        self.reset_unit()
        self.solver = control
        self._center = None
        self._surrogate = None
        self._X = []
        self._Y = []
        self._pool_results = PoolRefinementState()
        self._history_refs = []
        self._rng = self.create_local_rng(control, seed=self.cfg.random_seed)
        self.seed_operator_bindings(self._rng)

    def propose(self, control: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        from nsgablack.context_keys import KEY_SOLUTION_INPUT_REF
        self._validate_pool_candidate(control)
        if self._center is None or (self._pool_results.current is None and context.get(KEY_SOLUTION_INPUT_REF) is not None):
            seed = self.init_candidate(control, context)
            self._center = candidate_array(seed).copy()
            self._pool_results.remember_seed(control, seed)
        if self._pool_results.current is None:
            return (self._pool_results.project_current(control, self._center, semantic=True),)
        center = np.asarray(self._center, dtype=float)
        n = max(1, int(self.cfg.batch_size))
        explore_n = int(round(n * float(self.cfg.exploration_ratio)))
        exploit_n = max(0, n - explore_n)

        candidates: List[np.ndarray] = []
        # exploration: random neighborhood
        for _ in range(explore_n):
            cand = center + self._rng.normal(size=center.shape) * 0.5
            candidates.append(self._pool_results.derive_candidate(control, self._clip_to_bounds(cand, control), stage="mas_explore"))

        # exploitation: use surrogate model if available
        model = self._surrogate
        if model is not None and self._surrogate_is_fitted() and exploit_n > 0:
            pool = [center + self._rng.normal(size=center.shape) * 0.5 for _ in range(exploit_n * 3)]
            pool_arr = np.stack(pool, axis=0)
            try:
                preds = np.asarray(model.predict(pool_arr), dtype=float)
                if preds.ndim == 1:
                    scores = preds.reshape(-1)
                else:
                    scores = np.sum(preds, axis=1)
            except Exception as exc:
                _report_optional_failure(component=__name__, event="mas.predict", exc=exc)
                scores = np.zeros(len(pool_arr), dtype=float)
            best_idx = np.argsort(scores)[:exploit_n]
            for idx in best_idx:
                candidates.append(self._pool_results.derive_candidate(control, self._clip_to_bounds(pool_arr[idx], control), stage="mas_exploit"))
        elif exploit_n > 0:
            for _ in range(exploit_n):
                cand = center + self._rng.normal(size=center.shape) * 0.5
                candidates.append(self._pool_results.derive_candidate(control, self._clip_to_bounds(cand, control), stage="mas_explore"))
        return candidates

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
            raise ValueError("MAS feedback must align with candidates")
        if candidates is None or len(candidates) == 0:
            return None
        scores, violations = self._pool_results.scores(feedback, self._score)
        best_idx = min(range(len(scores)), key=lambda i: self._pool_results.key(scores[i], violations[i]))
        selected = self._pool_results.capture(control, candidates, feedback, best_idx, scores[best_idx], violations[best_idx])
        self._pool_results.current = selected
        self._pool_results.observe_best(control, candidates, feedback, best_idx, scores[best_idx], violations[best_idx])
        self._center = candidate_array(candidates[best_idx]).copy()
        refs = [self._pool_results.capture(control, candidates, feedback, i, scores[i], violations[i]).ref for i in range(len(candidates))]
        self._update_surrogate(candidates, objectives, refs=refs)
        return None

    def default_pool_input_count(self):
        return 1

    def restart_search(self, control, context=None):
        self.reset_unit()
        self._center, self._surrogate = None, None
        self._X = []
        self._Y = []
        self._history_refs = []
        self._pool_results = PoolRefinementState()

    def get_pool_refinement_results(self, control):
        self._validate_pool_candidate(control)
        return self._pool_results.results(control)

    def get_solution_pool_roots(self, control):
        if self._center is not None and self._pool_results.current is None:
            raise ValueError("MAS center requires exact evaluated pool evidence")
        if len(self._history_refs) != len(self._X) or any(ref is None for ref in self._history_refs):
            raise ValueError("MAS training history requires exact pool versions")
        self._validate_pool_candidate(control)
        refs = self._pool_results.roots(control)
        return tuple(dict.fromkeys((*refs, *self._history_refs)))

    def _validate_pool_candidate(self, control):
        selected = self._pool_results.current
        if selected is not None and selected.ref is not None:
            if self._center is None:
                raise ValueError("MAS evaluated pool selection requires its center")
            PoolRefinementState.validate(control, selected, candidate=self._center)
        if self._history_refs and any(ref is not None for ref in self._history_refs):
            if len(self._history_refs) != len(self._X) or any(ref is None for ref in self._history_refs):
                raise ValueError("MAS training history requires aligned exact pool versions")
            batch = control.solution_pool.read(tuple(self._history_refs), allow_pending=True)
            if not np.array_equal(batch.numeric_matrix, np.asarray(self._X), equal_nan=True):
                raise ValueError("MAS training candidates differ from their exact pool versions")

    def _extract_bounds(self, control: Any) -> tuple[Optional[np.ndarray], Optional[np.ndarray]]:
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

    def _get_algorithm_state(self) -> Dict[str, Any]:
        return {
            "center": None if self._center is None else self._center.tolist(),
            "history_x": [np.asarray(row, dtype=float).tolist() for row in self._X],
            "history_y": [np.asarray(row, dtype=float).tolist() for row in self._Y],
            "surrogate_present": self._surrogate is not None,
            "surrogate_fitted": self._surrogate_is_fitted(),
            "rng_state": copy.deepcopy(self._rng.bit_generator.state),
            "pool_results": self._pool_results.as_dict(),
            "history_refs": [None if ref is None else ref.as_dict() for ref in self._history_refs],
        }

    def _set_algorithm_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        self._validate_saved_history(state)
        self._pool_results = PoolRefinementState.from_dict(state.get("pool_results"))
        self._history_refs = [None if ref is None else SolutionRef.from_dict(ref) for ref in state.get("history_refs", ())]
        center = state.get("center")
        self._center = None if center is None else np.asarray(center, dtype=float)
        self._X = [
            np.asarray(row, dtype=float).reshape(-1)
            for row in tuple(state.get("history_x", ()) or ())
        ]
        self._Y = [
            np.asarray(row, dtype=float).reshape(-1)
            for row in tuple(state.get("history_y", ()) or ())
        ]
        if len(self._X) != len(self._Y):
            raise ValueError("MAS checkpoint surrogate history is misaligned")
        rng_state = state.get("rng_state")
        if isinstance(rng_state, Mapping):
            self._rng.bit_generator.state = copy.deepcopy(dict(rng_state))
        self._restore_surrogate_from_history(
            present=bool(state.get("surrogate_present", False)),
            fitted=bool(state.get("surrogate_fitted", False)),
        )

    def _snapshot_algorithm_step_state(self) -> Mapping[str, Any]:
        return {
            "schema": "nsgablack.mas_step_transaction/v1",
            "center": None if self._center is None else np.array(self._center, copy=True),
            "history_x": (
                None
                if not self._X
                else np.asarray(self._X, dtype=float).copy()
            ),
            "history_y": (
                None
                if not self._Y
                else np.asarray(self._Y, dtype=float).copy()
            ),
            "surrogate_present": self._surrogate is not None,
            "surrogate_fitted": self._surrogate_is_fitted(),
            "rng_state": copy.deepcopy(self._rng.bit_generator.state),
            "pool_results": self._pool_results.as_dict(),
            "history_refs": [None if ref is None else ref.as_dict() for ref in self._history_refs],
        }

    def _restore_algorithm_step_state(self, state: Mapping[str, Any]) -> None:
        if str(state.get("schema", "")) != "nsgablack.mas_step_transaction/v1":
            raise ValueError("unsupported MASAdapter step transaction schema")
        self._validate_saved_history(state, step=True)
        self._pool_results = PoolRefinementState.from_dict(state.get("pool_results"))
        self._history_refs = [None if ref is None else SolutionRef.from_dict(ref) for ref in state.get("history_refs", ())]
        center = state.get("center")
        self._center = None if center is None else np.asarray(center, dtype=float).copy()
        history_x = state.get("history_x")
        history_y = state.get("history_y")
        self._X = (
            []
            if history_x is None
            else [np.array(row, copy=True) for row in np.asarray(history_x, dtype=float)]
        )
        self._Y = (
            []
            if history_y is None
            else [np.array(row, copy=True) for row in np.asarray(history_y, dtype=float)]
        )
        if len(self._X) != len(self._Y):
            raise ValueError("MAS transaction surrogate history is misaligned")
        rng_state = state.get("rng_state")
        if not isinstance(rng_state, Mapping):
            raise TypeError("MAS transaction RNG state is invalid")
        self._rng.bit_generator.state = copy.deepcopy(dict(rng_state))
        self._restore_surrogate_from_history(
            present=bool(state.get("surrogate_present", False)),
            fitted=bool(state.get("surrogate_fitted", False)),
        )

    def _validate_saved_history(self, state, *, step=False):
        """Reject contradictory compatibility fields before fitting a model.

        The authoritative codec Unit's history must agree with the payload used for model
        reconstruction; neither copy may silently override the other.
        """
        payload = state.get("algorithm_unit")
        if payload is None:
            return  # Legacy numerical state without a Unit codec remains valid.
        # Runtime snapshots may contain native arrays; portable checkpoints
        # still require the persistent data codec and its original validation.
        restore = self.unit_binding.restore_step if step else self.unit_binding.restore
        unit = restore(payload)
        for field in ("history_x", "history_y"):
            raw = state.get(field)
            rows = [] if raw is None else list(raw)
            expected = getattr(unit, field)
            if len(rows) != len(expected) or any(
                not np.array_equal(np.asarray(row, dtype=float).reshape(-1),
                                   np.asarray(saved, dtype=float).reshape(-1), equal_nan=True)
                for row, saved in zip(rows, expected)
            ):
                raise ValueError("MAS saved training history disagrees with its authoritative Unit")

    def _surrogate_is_fitted(self) -> bool:
        surrogate = self._surrogate
        if surrogate is None or not surrogate.trainers:
            return False
        for trainer in surrogate.trainers:
            model = getattr(trainer, "model", None)
            if model is None or not (
                hasattr(model, "estimators_") or hasattr(model, "_fit_X")
            ):
                return False
        return True

    def _restore_surrogate_from_history(self, *, present: bool, fitted: bool) -> None:
        self._surrogate = None
        if not present:
            return
        objectives = None if not self._Y else np.asarray(self._Y, dtype=float)
        self._ensure_surrogate(self.solver, objectives)
        if not fitted:
            return
        if self._surrogate is None or not self._X or not self._Y:
            raise ValueError("MAS fitted surrogate checkpoint is missing training history")
        self._surrogate.fit(
            np.asarray(self._X, dtype=float),
            np.asarray(self._Y, dtype=float),
        )

    def _score(self, objectives: np.ndarray, violations: np.ndarray) -> np.ndarray:
        obj = np.asarray(objectives, dtype=float)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        vio = np.asarray(violations, dtype=float).reshape(-1)
        return np.sum(obj, axis=1) + vio * 1e6

    def _ensure_surrogate(self, control: Any, objectives: Optional[np.ndarray] = None) -> None:
        if not bool(self.cfg.enable_surrogate):
            return None
        if self._surrogate is not None:
            return None
        n_obj = None
        if objectives is not None:
            obj = np.asarray(objectives, dtype=float)
            if obj.ndim == 1:
                n_obj = 1
            elif obj.ndim >= 2:
                n_obj = int(obj.shape[1])
        if n_obj is None:
            n_obj = int(getattr(control, "num_objectives", 1) or 1)
        self._surrogate = self.unit_binding.builder.create_model(
            num_objectives=int(n_obj), model_type=self.cfg.surrogate_model_type)

    def _update_surrogate(self, candidates: Sequence[np.ndarray], objectives: np.ndarray, *, refs=None) -> None:
        if not bool(self.cfg.enable_surrogate):
            return None
        if candidates is None or len(candidates) == 0:
            return None
        obj = np.asarray(objectives, dtype=float)
        if obj.ndim == 1:
            obj = obj.reshape(-1, 1)
        self._ensure_surrogate(self.solver, obj if obj.size else None)
        if self._surrogate is None:
            return None
        X = [candidate_array(c).reshape(-1) for c in candidates]
        Y = [np.asarray(row, dtype=float).reshape(-1) for row in obj]
        self._X.extend(X)
        self._Y.extend(Y)
        self._history_refs.extend([None] * len(X) if refs is None else refs)

        max_keep = max(0, int(self.cfg.surrogate_max_train_samples))
        if max_keep > 0 and len(self._X) > max_keep:
            overflow = len(self._X) - max_keep
            del self._X[:overflow]
            del self._Y[:overflow]
            del self._history_refs[:overflow]

        if len(self._X) >= int(self.cfg.surrogate_min_train_samples) and bool(
            self.cfg.surrogate_retrain_every_call
        ):
            X_arr = np.asarray(self._X, dtype=float)
            Y_arr = np.asarray(self._Y, dtype=float)
            try:
                self._surrogate.fit(X_arr, Y_arr)
            except Exception as _fallback_error:
                _report_optional_failure(component=__name__, event='MASAdapter._update_surrogate.fallback_10', exc=_fallback_error)
                return None
        return None
