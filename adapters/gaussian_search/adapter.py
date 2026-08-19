"""Provider-neutral Gaussian random-search strategy."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence

import numpy as np
from blackbase.contracts import ComponentContract
from blackbase.context.context_keys import KEY_ADAPTER_BEST_SCORE, KEY_MUTATION_SIGMA
from blackbase.context import detach_context_value
from blackbase.types import UnknownState

from ..algorithm_adapter import AlgorithmAdapter
from ...core.evaluation_feedback import OptimizationFeedbackBatch


@dataclass(frozen=True)
class GaussianSearchConfig:
    population_size: int = 16
    mutation_scale: float = 0.25
    random_seed: int = 42
    exploit_best: bool = True
    initialization: str = "population"  # population | center
    include_center_candidate: bool = True
    objective_aggregation: str = "sum"  # sum | first

    def __post_init__(self) -> None:
        if int(self.population_size) <= 0:
            raise ValueError("population_size must be positive")
        if float(self.mutation_scale) < 0.0:
            raise ValueError("mutation_scale must be non-negative")
        initialization = str(self.initialization or "population").strip().lower()
        if initialization not in {"population", "center"}:
            raise ValueError("initialization must be 'population' or 'center'")
        aggregation = str(self.objective_aggregation or "sum").strip().lower()
        if aggregation not in {"sum", "first"}:
            raise ValueError("objective_aggregation must be 'sum' or 'first'")
        object.__setattr__(self, "initialization", initialization)
        object.__setattr__(self, "objective_aggregation", aggregation)


class GaussianSearchAdapter(AlgorithmAdapter):
    """Search numeric candidate state without owning model or data semantics."""

    context_requires = ()
    context_optional = ()
    context_provides = (KEY_MUTATION_SIGMA, KEY_ADAPTER_BEST_SCORE)
    context_mutates = ()
    context_cache = ()
    method_ids = ("search.random_gaussian",)
    context_notes = (
        "Mutates numeric candidate state; decoding, fitting, and metrics belong to the Problem/Provider.",
        "Selects an incumbent feasibility-first, then by the configured objective aggregation.",
    )
    state_recovery_level = "L1"
    state_recovery_notes = "Restores incumbent, feasibility evidence, and exact RNG state."
    contract = ComponentContract(
        name="gaussian_search",
        supports_gradient=False,
        supports_batch=True,
        supports_resume=True,
        metadata={
            "family": "stochastic_search",
            "provider_neutral": True,
            "method_ids": method_ids,
        },
    )

    def __init__(
        self,
        config: Optional[GaussianSearchConfig] = None,
        name: str = "gaussian_search",
        priority: int = 0,
        **config_kwargs: Any,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.config = self.resolve_config(
            config=config,
            config_cls=GaussianSearchConfig,
            config_kwargs=config_kwargs,
            adapter_name="GaussianSearchAdapter",
        )
        self.cfg = self.config
        self.best_x: np.ndarray | None = None
        self.best_score: float | None = None
        self.best_violation: float | None = None
        self.step_index = 0
        self._candidate_kind = "array"
        self._candidate_metadata: Dict[str, Any] = {}
        self._rng = np.random.default_rng(int(self.cfg.random_seed))
        self._state_loaded = False
        self._runtime_projection: Dict[str, Any] = {}
        self._refresh_runtime_projection()

    def setup(self, control: Any) -> None:
        _ = control
        if not self._state_loaded:
            self.best_x = None
            self.best_score = None
            self.best_violation = None
            self.step_index = 0
            self._candidate_kind = "array"
            self._candidate_metadata = {}
            self._rng = np.random.default_rng(int(self.cfg.random_seed))
        self._state_loaded = False
        self._refresh_runtime_projection()

    def propose(self, control: Any, context: Mapping[str, Any]) -> Sequence[Any]:
        n = int(self.cfg.population_size)
        if self.best_x is None:
            if self.cfg.initialization == "population":
                return tuple(control.init_population(n, context))
            center = control.init_candidate(context)
            self._capture_candidate_template(center)
            return self._around_center(center, n)

        if not self.cfg.exploit_best and self.cfg.initialization == "population":
            return tuple(control.init_population(n, context))
        return self._around_center(self._wrap_candidate(self.best_x), n)

    def update(
        self,
        control: Any,
        candidates: Sequence[Any],
        feedback: Any,
        context: Mapping[str, Any],
    ) -> None:
        _ = (control, context)
        rich_feedback = OptimizationFeedbackBatch.coerce(feedback)
        values = tuple(candidates)
        if len(values) != rich_feedback.candidate_count:
            raise ValueError(
                "GaussianSearchAdapter feedback must align with candidates: "
                f"candidates={len(values)}, feedback={rich_feedback.candidate_count}"
            )
        objectives, violations = rich_feedback
        for index, candidate in enumerate(values):
            row = np.asarray(objectives[index], dtype=float).reshape(-1)
            score = self._score(row)
            violation = float(violations[index])
            if not np.isfinite(score):
                continue
            if not np.isfinite(violation):
                violation = float("inf")
            violation = max(0.0, violation)
            if self._is_better(violation, score):
                self._capture_candidate_template(candidate)
                self.best_x = self._candidate_array(candidate).copy()
                self.best_score = float(score)
                self.best_violation = float(violation)
        self.step_index += 1
        self._refresh_runtime_projection()

    def _around_center(self, center: Any, count: int) -> tuple[Any, ...]:
        self._capture_candidate_template(center)
        base = self._candidate_array(center)
        out: list[Any] = []
        if self.cfg.include_center_candidate:
            out.append(self._wrap_candidate(base))
        while len(out) < int(count):
            noise = self._rng.normal(
                0.0,
                float(self.cfg.mutation_scale),
                size=base.shape,
            )
            out.append(self._wrap_candidate(base + noise, source="gaussian_mutation"))
        return tuple(out[: int(count)])

    def _is_better(self, violation: float, score: float) -> bool:
        if self.best_x is None or self.best_violation is None or self.best_score is None:
            return True
        candidate_feasible = violation <= 0.0
        incumbent_feasible = self.best_violation <= 0.0
        if candidate_feasible != incumbent_feasible:
            return candidate_feasible
        if not candidate_feasible and violation != self.best_violation:
            return violation < self.best_violation
        return score < self.best_score

    def _score(self, objectives: np.ndarray) -> float:
        if objectives.size == 0:
            raise ValueError("GaussianSearchAdapter requires at least one objective")
        if self.cfg.objective_aggregation == "first":
            return float(objectives[0])
        return float(np.sum(objectives))

    @staticmethod
    def _candidate_array(candidate: Any) -> np.ndarray:
        if isinstance(candidate, UnknownState):
            return np.asarray(candidate.as_array(), dtype=float).reshape(-1)
        return np.asarray(candidate, dtype=float).reshape(-1)

    def _capture_candidate_template(self, candidate: Any) -> None:
        if isinstance(candidate, UnknownState):
            self._candidate_kind = "unknown_state"
            self._candidate_metadata = detach_context_value(
                dict(candidate.metadata or {}),
                path="gaussian_search.candidate_metadata",
            )
        else:
            self._candidate_kind = "array"
            self._candidate_metadata = {}

    def _wrap_candidate(self, values: np.ndarray, **metadata: Any) -> Any:
        array = np.asarray(values, dtype=float).reshape(-1).copy()
        if self._candidate_kind == "unknown_state":
            return UnknownState(
                values=array,
                metadata={
                    **detach_context_value(
                        self._candidate_metadata,
                        path="gaussian_search.candidate_metadata",
                    ),
                    **metadata,
                    "search_method": "search.random_gaussian",
                    "search_step": int(self.step_index),
                },
            )
        return array

    def get_population(self) -> tuple[Any, ...] | None:
        if self.best_x is None:
            return None
        return (self._wrap_candidate(self.best_x),)

    def set_population(
        self,
        population: Any,
        objectives: Any | None = None,
        violations: Any | None = None,
    ) -> bool:
        if isinstance(population, UnknownState):
            values = (population,)
        elif isinstance(population, np.ndarray) and population.ndim <= 1:
            values = (population,)
        elif population is None:
            values = ()
        else:
            values = tuple(population)
        if not values:
            self.best_x = None
            self.best_score = None
            self.best_violation = None
            self._state_loaded = True
            self._refresh_runtime_projection()
            return True
        candidate = values[0]
        self._capture_candidate_template(candidate)
        self.best_x = self._candidate_array(candidate).copy()
        if objectives is not None:
            objective_rows = np.asarray(objectives, dtype=float)
            row = objective_rows if objective_rows.ndim == 1 else objective_rows[0]
            self.best_score = self._score(np.asarray(row, dtype=float).reshape(-1))
        if violations is not None:
            self.best_violation = max(
                0.0,
                float(np.asarray(violations, dtype=float).reshape(-1)[0]),
            )
        self._state_loaded = True
        self._refresh_runtime_projection()
        return True

    def get_runtime_context_projection(self, solver: Any) -> Dict[str, Any]:
        _ = solver
        return dict(self._runtime_projection)

    def get_runtime_context_projection_sources(self, solver: Any) -> Dict[str, str]:
        _ = solver
        source = f"adapter.{self.__class__.__name__}"
        return {key: source for key in self._runtime_projection}

    def _refresh_runtime_projection(self) -> None:
        self._runtime_projection = {
            KEY_MUTATION_SIGMA: float(self.cfg.mutation_scale),
            KEY_ADAPTER_BEST_SCORE: self.best_score,
        }

    def get_state(self) -> Mapping[str, Any]:
        return {
            "best_x": None if self.best_x is None else self.best_x.tolist(),
            "best_score": self.best_score,
            "best_violation": self.best_violation,
            "step_index": int(self.step_index),
            "candidate_kind": self._candidate_kind,
            "candidate_metadata": detach_context_value(
                self._candidate_metadata,
                path="gaussian_search.candidate_metadata",
            ),
            "rng_state": deepcopy(self._rng.bit_generator.state),
            "method_id": "search.random_gaussian",
        }

    def set_state(self, state: Mapping[str, Any]) -> None:
        method_id = str(state.get("method_id", "search.random_gaussian") or "")
        if method_id != "search.random_gaussian":
            raise ValueError("GaussianSearchAdapter checkpoint method does not match")
        best_x = state.get("best_x")
        self.best_x = (
            None if best_x is None else np.asarray(best_x, dtype=float).reshape(-1)
        )
        score = state.get("best_score")
        self.best_score = None if score is None else float(score)
        violation = state.get("best_violation")
        self.best_violation = None if violation is None else float(violation)
        self.step_index = int(state.get("step_index", 0) or 0)
        if self.step_index < 0:
            raise ValueError("GaussianSearchAdapter step_index must be non-negative")
        candidate_kind = str(state.get("candidate_kind", "array") or "array")
        if candidate_kind not in {"array", "unknown_state"}:
            raise ValueError("unsupported GaussianSearchAdapter candidate kind")
        self._candidate_kind = candidate_kind
        self._candidate_metadata = detach_context_value(
            dict(state.get("candidate_metadata", {}) or {}),
            path="gaussian_search.candidate_metadata",
        )
        self._rng = np.random.default_rng(int(self.cfg.random_seed))
        rng_state = state.get("rng_state")
        if isinstance(rng_state, Mapping):
            self._rng.bit_generator.state = deepcopy(dict(rng_state))
        self._state_loaded = True
        self._refresh_runtime_projection()


__all__ = ["GaussianSearchAdapter", "GaussianSearchConfig"]
