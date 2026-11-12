"""
Simulated Annealing (SA) as an AlgorithmAdapter.

This is the "algorithm-core" decomposition of SA:
- propose(): generate neighbor candidates through its bound mutation role
- update(): accept/reject via Metropolis rule + temperature schedule

Notes:
- SA is naturally sequential; this adapter proposes a small batch and processes
  it in order. Batch > 1 is mainly for better throughput when evaluation is
  expensive / parallelized.
- Multi-objective fallback scoring uses sum(objectives) + violation*1e6, aligned
  with ComposableSolver.select_best().
"""

from __future__ import annotations
import copy
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple
import math
import warnings

import numpy as np

from ..unit_backed import UnitBackedAdapter, UnitField, UnitFeedbackField
from ...representation.structure_builders import TrajectoryUnitBuilder
from ..algorithm_adapter import AlgorithmAdapter
from ..pool_results import PoolRefinementState
from ..selection import SelectionRequest
from nsgablack.context_keys import KEY_MUTATION_SIGMA, KEY_TEMPERATURE


@dataclass
class SAConfig:
    # number of candidates per step (processed sequentially)
    batch_size: int = 1

    # temperature schedule: T <- max(min_temperature, T * cooling_rate)
    initial_temperature: float = 10.0
    cooling_rate: float = 0.98
    min_temperature: float = 1e-6

    # optional coupling to representation mutator:
    # - if your mutator consumes "mutation_sigma", SA will write it based on T
    base_sigma: float = 0.2
    sigma_temperature_scale: float = 1.0  # sigma = base_sigma * (T/T0)**scale

    # objective aggregation for multi-objective fallback scoring
    objective_aggregation: str = "sum"  # "sum" or "first"

    # Optional RNG seed for reproducible Metropolis acceptance.
    random_seed: Optional[int] = None


class SimulatedAnnealingAdapter(UnitBackedAdapter):
    """Simulated annealing adapter for ComposableSolver."""
    pool_input_modes = ("initialize",)
    supports_pool_restart = True
    supports_objective_projection = True
    operation_methods = {"initializer": "initialize", "mutator": "mutate",
                         "selector": "select", "repair": "repair"}

    def default_pool_input_count(self):
        return 1

    def restart_search(self, control, context):
        """Reheat and choose a new pool seed; retain the local RNG stream."""
        self.reset_unit()
        self.t0 = float(self.cfg.initial_temperature)
        self.temperature = self.t0
        self.current_x = None
        self.current_score = None
        self._pool_results = PoolRefinementState()
        self._last_runtime_projection = {}

    def get_solution_pool_roots(self, control):
        return self._pool_results.roots(control)

    def get_pool_refinement_results(self, control):
        """Return the task's best evaluated point, even after an uphill move."""
        return self._pool_results.results(control)

    def _project_current(self, control, *, semantic=False):
        return self._pool_results.project_current(control, self.current_x, semantic=semantic)

    uses_pipeline_mutation = True
    accepts_proposal_replacement = True
    unit_builder_type = TrajectoryUnitBuilder
    unit_schema = TrajectoryUnitBuilder.unit_type.schema
    current_x = UnitField("current")
    current_score = UnitFeedbackField("current")

    context_requires = ("generation",)
    context_provides = (KEY_TEMPERATURE, KEY_MUTATION_SIGMA)
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "SA writes temperature and optional sigma into context for mutator scheduling.",
    )
    state_recovery_level = "L1"
    state_recovery_notes = "Restores trajectory Unit, annealing temperature and local RNG state."

    # Soft partner contracts: SA communicates temperature and (optionally)
    # mutation scale via context. Representation mutator may consume these keys.
    recommended_mutators = ["ContextGaussianMutation", "ContextSelectMutator"]

    def __init__(
        self,
        config: Optional[SAConfig] = None,
        name: str = "sa",
        priority: int = 0,
        initializer=None,
        mutator=None,
        selector=None,
        repair=None,
        **config_kwargs,
    ) -> None:
        super().__init__(name=name, priority=priority, unit_binding=config_kwargs.pop("unit_binding", None))
        self.config = self.resolve_config(
            config=config,
            config_cls=SAConfig,
            config_kwargs=config_kwargs,
            adapter_name="SimulatedAnnealingAdapter",
        )
        self.cfg = self.config
        self.t0 = float(self.cfg.initial_temperature)
        self.temperature = float(self.cfg.initial_temperature)
        self.current_x: Optional[np.ndarray] = None
        self.current_score: Optional[float] = None
        self._warned_missing_operator = False
        self._last_runtime_projection: Dict[str, Any] = {}
        self._rng = self._build_rng()
        self._pool_results = PoolRefinementState()
        for role, component in (("initializer", initializer), ("mutator", mutator),
                                ("selector", selector), ("repair", repair)):
            if component is not None:
                self.set_operation(role, component)

    def _build_rng(self) -> np.random.Generator:
        if self.cfg.random_seed is not None:
            return np.random.default_rng(int(self.cfg.random_seed))
        # Derive seed from numpy global RNG state so np.random.seed(...) controls SA reproducibility.
        return np.random.default_rng(int(np.random.randint(0, 2**31 - 1)))

    def setup(self, control: Any) -> None:
        self.reset_unit()
        self.t0 = float(self.cfg.initial_temperature)
        self.temperature = float(self.cfg.initial_temperature)
        self.current_x = None
        self.current_score = None
        self._pool_results = PoolRefinementState()
        self._rng = self.create_local_rng(control, seed=self.cfg.random_seed)
        self.seed_operator_bindings(self._rng)
        self._warn_if_pipeline_has_no_mutator(control)
        self._last_runtime_projection = {}

    def _warn_if_pipeline_has_no_mutator(self, control: Any) -> None:
        if self._warned_missing_operator:
            return

        if self.get_mutation_operator(control) is None:
            warnings.warn(
                "SimulatedAnnealingAdapter 未装配可用的 mutate 算子；"
                "SA 将无法产生邻域候选（会退化为几乎不移动）。"
                "建议：连续变量用 GaussianMutation/ContextGaussianMutation；"
                "离散/多邻域用 ContextSelectMutator 或自定义 mutator。",
                RuntimeWarning,
                stacklevel=3,
            )
            self._warned_missing_operator = True

    def _score(self, objectives_row: np.ndarray, violation: float) -> float:
        if self.cfg.objective_aggregation == "first":
            obj = float(objectives_row[0])
        else:
            obj = float(np.sum(objectives_row))
        return float(violation) * 1e6 + obj

    def _build_sa_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        ctx = dict(context)
        ctx[KEY_TEMPERATURE] = float(self.temperature)

        # Optional: couple temperature to neighborhood scale.
        # If the representation mutator consumes mutation_sigma, SA can "cool"
        # its step size naturally.
        if self.t0 > 0 and self.cfg.sigma_temperature_scale != 0.0:
            ratio = max(0.0, float(self.temperature) / float(self.t0))
            sigma = float(self.cfg.base_sigma) * (ratio ** float(self.cfg.sigma_temperature_scale))
            ctx[KEY_MUTATION_SIGMA] = float(sigma)
        return ctx

    def propose(self, control: Any, context: Dict[str, Any]) -> Sequence[np.ndarray]:
        if self.current_x is None:
            seed = self.init_candidate(control, context)
            self.current_x = np.asarray(seed)
            self._pool_results.remember_seed(control, seed)

        # Establish the initial/current baseline through the ordinary proposal,
        # repair, budget and admission path. No hidden evaluation in propose.
        if self.current_score is None:
            return [self._project_current(control, semantic=True)]

        ctx = self._build_sa_context(context)

        out = []
        for _ in range(max(1, int(self.cfg.batch_size))):
            cand = self.mutate_candidate(control, self._project_current(control), ctx)
            if self.get_bound_mutator() is not None:
                cand = self.semantic_proposal(control, cand)
            out.append(cand)
        return out

    def _proposal_contexts(self, proposed_count, context):
        return tuple(self._build_sa_context(context) for _ in range(proposed_count))

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
        if objectives is None or len(objectives) == 0:
            return
        scores, violations = self._pool_results.scores(feedback, lambda f, v:
            [self._score(row, float(v[i])) for i, row in enumerate(f)])
        best_index = min(range(len(candidates)), key=lambda i: self._pool_results.key(scores[i], violations[i]))
        self._pool_results.observe_best(control, candidates, feedback, best_index,
                                        scores[best_index], violations[best_index])

        # The baseline proposal may have been repaired. Install the evaluated
        # candidate and its own score together; this is not an annealing move.
        if self.current_score is None:
            if len(candidates) != 1:
                raise ValueError("SA baseline feedback requires exactly one candidate")
            self.current_x = np.array(candidates[0], copy=True)
            v0 = float(violations[0]) if violations is not None else 0.0
            self.current_score = float(scores[0])
            self._pool_results.current = self._pool_results.capture(
                control, candidates, feedback, 0, self.current_score, v0)
            self._refresh_runtime_projection(accepted=False)
            return

        # process batch sequentially; accept the first accepted move
        accepted_any = False
        order = range(len(candidates))
        if self.get_bound_operator("selector") is not None:
            request = SelectionRequest("proposal_order", candidates, objectives, violations,
                len(candidates), scores=scores, parameters={"temperature": float(self.temperature)},
                context=context)
            order = self.select_indices(request, rng=self._rng)
        for idx in order:
            cand = candidates[idx]
            vio = float(violations[idx]) if violations is not None else 0.0
            cand_score = float(scores[idx])

            delta = float(cand_score) - float(self.current_score)
            accept = False
            if self._pool_results.improves_current(cand_score, vio, self.current_score) or (
                    delta == 0 and self._pool_results.permits_exploration(vio)):
                accept = True
            elif self._pool_results.permits_exploration(vio):
                T = max(float(self.temperature), float(self.cfg.min_temperature))
                if T > 0:
                    p = math.exp(-max(0.0, delta) / T)
                    accept = (self._rng.random() < p)

            if accept:
                self.current_x = np.asarray(cand)
                self.current_score = float(cand_score)
                self._pool_results.current = self._pool_results.capture(
                    control, candidates, feedback, idx, cand_score, vio)
                accepted_any = True
                break

        # cool down once per step (not per candidate)
        self.temperature = max(float(self.cfg.min_temperature), float(self.temperature) * float(self.cfg.cooling_rate))

        self._refresh_runtime_projection(accepted=accepted_any)

    def _refresh_runtime_projection(self, *, accepted: bool) -> None:
        # Keep runtime state in adapter projection (non-invasive to solver object).
        projection: Dict[str, Any] = {
            KEY_TEMPERATURE: float(self.temperature),
            "sa_accepted": bool(accepted),
        }
        if self.current_x is not None:
            projection["sa_current_x"] = np.asarray(self.current_x, dtype=float)
        if self.current_score is not None:
            projection["sa_current_score"] = float(self.current_score)
        self._last_runtime_projection = projection

    def _get_algorithm_state(self) -> Dict[str, Any]:
        return {
            "temperature": float(self.temperature),
            "t0": float(self.t0),
            "current_x": None if self.current_x is None else np.asarray(self.current_x, dtype=float).tolist(),
            "current_score": None if self.current_score is None else float(self.current_score),
            "rng_state": copy.deepcopy(self._rng.bit_generator.state),
            "pool_refinement": self._pool_results.as_dict(),
        }

    def _set_algorithm_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        if "temperature" in state:
            self.temperature = float(state["temperature"])
        if "t0" in state:
            self.t0 = float(state["t0"])
        cx = state.get("current_x")
        self.current_x = None if cx is None else np.asarray(cx, dtype=float)
        self.current_score = state.get("current_score")
        self._pool_results = PoolRefinementState.from_dict(state.get("pool_refinement"))
        rng_state = state.get("rng_state")
        if isinstance(rng_state, dict):
            self._rng.bit_generator.state = copy.deepcopy(rng_state)
        self._last_runtime_projection = {
            KEY_TEMPERATURE: float(self.temperature),
            **(
                {}
                if self.current_x is None
                else {"sa_current_x": np.asarray(self.current_x, dtype=float)}
            ),
            **(
                {}
                if self.current_score is None
                else {"sa_current_score": float(self.current_score)}
            ),
        }

    def get_runtime_context_projection(self, solver: Any) -> Dict[str, Any]:
        _ = solver
        projection = dict(self._last_runtime_projection)
        projection.pop("sa_current_score", None)
        projection.pop("sa_current_x", None)
        if self.current_x is not None:
            projection["sa_current_x"] = np.array(self.current_x, copy=True)
        if self.current_score is not None:
            projection["sa_current_score"] = self.current_score
        return projection

    def get_runtime_context_projection_sources(self, solver: Any) -> Dict[str, str]:
        _ = solver
        source = f"adapter.{self.__class__.__name__}"
        return {str(key): source for key in self._last_runtime_projection.keys()}
