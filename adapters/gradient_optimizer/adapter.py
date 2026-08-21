"""Provider-neutral first-order optimization adapter.

The adapter consumes gradients carried by ``OptimizationFeedbackBatch``.  It
does not import an autodiff framework, inspect training data, or own a device;
those responsibilities remain with the evaluation provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence

import numpy as np
from blackbase.contracts import BatchDisposition, ComponentContract
from blackbase.context.context_keys import (
    KEY_ADAPTER_BEST_SCORE,
    KEY_MUTATION_SIGMA,
    KEY_RESOURCE_CONTEXT,
    KEY_RESOURCE_CONTEXT_SHORT,
)
from blackbase.context import detach_context_value
from blackbase.evaluation import (
    EvaluationGateway,
    StateMaterializationRequest,
    StateTransitionRequest,
)
from blackbase.resources import ResourceContext
from blackbase.state_ref import StateRef
from blackbase.types import UnknownState

from ..algorithm_adapter import AlgorithmAdapter
from ...core.evaluation_feedback import OptimizationFeedbackBatch


@dataclass(frozen=True)
class GradientOptimizerConfig:
    optimizer: str = "adam"  # sgd | adam | adamw
    learning_rate: float = 1e-3
    min_learning_rate: float = 1e-12
    weight_decay: float = 0.0
    max_gradient_norm: float | None = None
    beta1: float = 0.9
    beta2: float = 0.999
    epsilon: float = 1e-8
    objective_aggregation: str = "sum"  # sum | first
    skip_infeasible: bool = True

    @classmethod
    def from_method(cls, method: str, **overrides: Any) -> "GradientOptimizerConfig":
        method_id = str(method or "").strip().lower()
        mapping = {
            "gradient.sgd": "sgd",
            "gradient.adam": "adam",
            "gradient.adamw": "adamw",
        }
        if method_id not in mapping:
            raise ValueError(
                "unknown gradient method; expected gradient.sgd, "
                "gradient.adam, or gradient.adamw"
            )
        return cls(optimizer=mapping[method_id], **overrides)

    def __post_init__(self) -> None:
        optimizer = str(self.optimizer or "adam").strip().lower()
        if optimizer not in {"sgd", "adam", "adamw"}:
            raise ValueError("optimizer must be one of: sgd, adam, adamw")
        if float(self.learning_rate) <= 0.0:
            raise ValueError("learning_rate must be positive")
        if float(self.min_learning_rate) <= 0.0:
            raise ValueError("min_learning_rate must be positive")
        if float(self.weight_decay) < 0.0:
            raise ValueError("weight_decay must be non-negative")
        if self.max_gradient_norm is not None and float(self.max_gradient_norm) <= 0.0:
            raise ValueError("max_gradient_norm must be positive when provided")
        if not 0.0 <= float(self.beta1) < 1.0:
            raise ValueError("beta1 must be in [0, 1)")
        if not 0.0 <= float(self.beta2) < 1.0:
            raise ValueError("beta2 must be in [0, 1)")
        if float(self.epsilon) <= 0.0:
            raise ValueError("epsilon must be positive")
        aggregation = str(self.objective_aggregation or "sum").strip().lower()
        if aggregation not in {"sum", "first"}:
            raise ValueError("objective_aggregation must be 'sum' or 'first'")
        object.__setattr__(self, "optimizer", optimizer)
        object.__setattr__(self, "objective_aggregation", aggregation)


class GradientOptimizerAdapter(AlgorithmAdapter):
    """SGD/Adam/AdamW over gradients supplied by an evaluation provider."""

    context_requires = ()
    # Keep literals here so Doctor can prove the source-level read contract.
    context_optional = (KEY_RESOURCE_CONTEXT, KEY_RESOURCE_CONTEXT_SHORT)
    context_provides = (KEY_MUTATION_SIGMA, KEY_ADAPTER_BEST_SCORE)
    context_mutates = ()
    context_cache = ()
    feedback_requires = ("gradients",)
    method_ids = ("gradient.sgd", "gradient.adam", "gradient.adamw")
    context_notes = (
        "Consumes Feedback.gradients; autodiff, data batching, and device state belong to the provider.",
        "Supports SGD, Adam, and AdamW without importing an ML backend.",
    )
    state_recovery_level = "L1"
    state_recovery_notes = "Restores current parameters, optimizer moments, and step index."
    contract = ComponentContract(
        name="gradient_optimizer",
        optional=context_optional,
        supports_gradient=True,
        supports_batch=False,
        supports_resume=True,
        metadata={
            "family": "first_order",
            "feedback_requires": ("gradients",),
            "provider_neutral": True,
            "method_ids": method_ids,
        },
    )

    def __init__(
        self,
        config: Optional[GradientOptimizerConfig] = None,
        name: str = "gradient_optimizer",
        priority: int = 0,
        state_gateway: EvaluationGateway | None = None,
        prefer_provider_transition: bool = False,
        **config_kwargs: Any,
    ) -> None:
        super().__init__(name=name, priority=priority)
        self.config = self.resolve_config(
            config=config,
            config_cls=GradientOptimizerConfig,
            config_kwargs=config_kwargs,
            adapter_name="GradientOptimizerAdapter",
        )
        self.cfg = self.config
        self.state_gateway = state_gateway
        self.prefer_provider_transition = bool(prefer_provider_transition)
        self.current_x: np.ndarray | None = None
        self.current_score: float | None = None
        self.best_score: float | None = None
        self.last_gradient_norm: float | None = None
        self.step_index = 0
        self._first_moment: np.ndarray | None = None
        self._second_moment: np.ndarray | None = None
        self._candidate_kind = "array"
        self._candidate_metadata: Dict[str, Any] = {}
        self._proposal_pending = False
        self._runtime_projection: Dict[str, Any] = {}
        self._provider_state_ref: StateRef | None = None
        self._provider_slot_refs: Dict[str, StateRef] = {}
        self._provider_transition_count = 0
        self._provider_transition_needs_slot_seed = False
        self._provider_resource_context: ResourceContext | None = None
        self._state_loaded = False

    def setup(self, control: Any) -> None:
        resume_loaded = bool(getattr(control, "_resume_loaded", False)) or bool(
            self._state_loaded
        )
        if not resume_loaded:
            self.current_x = None
            self.current_score = None
            self.best_score = None
            self.last_gradient_norm = None
            self.step_index = 0
            self._first_moment = None
            self._second_moment = None
            self._candidate_kind = "array"
            self._candidate_metadata = {}
            self._provider_state_ref = None
            self._provider_slot_refs = {}
            self._provider_transition_count = 0
            self._provider_transition_needs_slot_seed = False
            self._provider_resource_context = None
        self._state_loaded = False
        self._proposal_pending = False
        self._refresh_runtime_projection()

    def propose(self, control: Any, context: Dict[str, Any]) -> Sequence[Any]:
        if self._proposal_pending:
            raise RuntimeError("gradient optimizer has an unresolved proposal")
        if self.current_x is None:
            initial = control.init_candidate(context)
            self._capture_candidate_template(initial)
            self.current_x = self._candidate_array(initial)
        candidate = self._repair_values(control, self.current_x.copy(), context)
        self._proposal_pending = True
        return (self._wrap_candidate(candidate),)

    def teardown(self, control: Any) -> None:
        del control
        had_live_slots = bool(self._provider_slot_refs)
        self._refresh_provider_slot_shadow()
        self._provider_slot_refs = {}
        self._provider_resource_context = None
        if had_live_slots and self.cfg.optimizer in {"adam", "adamw"}:
            self._provider_transition_needs_slot_seed = True

    def on_proposal_disposition(
        self,
        control: Any,
        disposition: BatchDisposition,
        context: Dict[str, Any],
    ) -> None:
        _ = (control, context)
        if disposition.proposed_count != 1:
            raise ValueError(
                "GradientOptimizerAdapter expects one pending proposal, "
                f"got proposed_count={disposition.proposed_count}"
            )
        self._proposal_pending = disposition.accepted_count == 1

    def update(
        self,
        control: Any,
        candidates: Sequence[Any],
        feedback: Any,
        context: Dict[str, Any],
    ) -> None:
        rich_feedback = OptimizationFeedbackBatch.coerce(feedback)
        objectives, violations = rich_feedback
        if len(candidates) != 1:
            raise ValueError("GradientOptimizerAdapter requires exactly one evaluated candidate")
        if not self._proposal_pending:
            raise RuntimeError("gradient feedback has no pending proposal")

        items = tuple(rich_feedback.items)
        if len(items) != 1:
            raise ValueError(
                "GradientOptimizerAdapter requires exactly one Feedback item"
            )
        item = items[0]
        use_provider_transition = self._should_use_provider_transition(item)
        if item.gradients is None and not use_provider_transition:
            raise ValueError(
                "GradientOptimizerAdapter requires inline gradients or a Provider "
                "gradient_ref/state_ref transition; attach an autograd/analytic "
                "Provider or use the finite-difference GradientDescentAdapter"
            )

        semantic_resolver = getattr(control, "semantic_candidate_state", None)
        candidate_view = (
            semantic_resolver(candidates[0], candidate_index=0)
            if callable(semantic_resolver)
            else candidates[0]
        )
        self._capture_candidate_template(candidate_view)
        candidate = self._candidate_array(candidate_view)
        gradient = (
            None
            if item.gradients is None
            else np.asarray(item.gradients, dtype=float).reshape(-1)
        )
        if gradient is not None:
            if gradient.shape != candidate.shape:
                raise ValueError(
                    "feedback gradient shape must match the candidate: "
                    f"gradient={gradient.shape}, candidate={candidate.shape}"
                )
            if not np.all(np.isfinite(gradient)):
                raise ValueError("feedback gradient must contain only finite values")

        objective_rows = np.asarray(objectives, dtype=float)
        if objective_rows.ndim == 1:
            objective_rows = objective_rows.reshape(1, -1)
        violation_values = np.asarray(violations, dtype=float).reshape(-1)
        if objective_rows.shape[0] != 1 or violation_values.shape[0] != 1:
            raise ValueError("gradient feedback must contain exactly one result row")

        score = self._score(objective_rows[0])
        self.current_score = float(score)
        if self.best_score is None or float(score) < self.best_score:
            self.best_score = float(score)
        self._proposal_pending = False
        if bool(self.cfg.skip_infeasible) and float(violation_values[0]) > 0.0:
            self.current_x = candidate.copy()
            self._refresh_runtime_projection()
            return

        if gradient is not None:
            gradient = self._clip_gradient(gradient)
            self.last_gradient_norm = float(np.linalg.norm(gradient))
        if use_provider_transition:
            # Maintain a materialized optimizer shadow for checkpoint fallback;
            # the authoritative parameter update still executes exactly once
            # inside the Provider.
            slot_seed = None
            if self._provider_transition_needs_slot_seed:
                slot_seed = {
                    "first_moment": (
                        None if self._first_moment is None else self._first_moment.copy()
                    ),
                    "second_moment": (
                        None if self._second_moment is None else self._second_moment.copy()
                    ),
                }
            if gradient is not None:
                self._optimizer_delta(candidate, gradient)
            self._apply_provider_transition(
                feedback=item,
                context=context,
                slot_seed=slot_seed,
            )
            if self.current_x is None:  # defensive contract guard
                raise RuntimeError("provider transition did not materialize a candidate")
            self.current_x = self._repair_values(
                control,
                self.current_x.copy(),
                context,
            )
            self.step_index += 1
            self._refresh_runtime_projection()
            return
        assert gradient is not None
        next_x = candidate - self._optimizer_delta(candidate, gradient)
        self.current_x = self._repair_values(control, next_x, context)
        self.step_index += 1
        self._refresh_runtime_projection()

    def _should_use_provider_transition(self, feedback: Any) -> bool:
        if not self.prefer_provider_transition:
            return False
        if self.state_gateway is None:
            raise RuntimeError(
                "provider transition is enabled but no BlackBase EvaluationGateway was injected"
            )
        state_ref = dict(getattr(feedback, "info", {}) or {}).get(
            "evaluation_state_ref"
        )
        return isinstance(state_ref, StateRef) and isinstance(
            getattr(feedback, "gradient_ref", None),
            StateRef,
        )

    def _apply_provider_transition(
        self,
        *,
        feedback: Any,
        context: Mapping[str, Any],
        slot_seed: Mapping[str, Any] | None = None,
    ) -> None:
        gateway = self.state_gateway
        if gateway is None:
            raise RuntimeError("provider transition gateway is unavailable")
        state_ref = dict(feedback.info or {}).get("evaluation_state_ref")
        gradient_ref = feedback.gradient_ref
        if not isinstance(state_ref, StateRef) or not isinstance(gradient_ref, StateRef):
            raise TypeError("provider transition requires StateRef parameters and gradient")
        parameters: dict[str, Any] = {
            "learning_rate": float(self.cfg.learning_rate),
            "min_learning_rate": float(self.cfg.min_learning_rate),
            "weight_decay": float(self.cfg.weight_decay),
            "beta1": float(self.cfg.beta1),
            "beta2": float(self.cfg.beta2),
            "epsilon": float(self.cfg.epsilon),
        }
        if self.cfg.max_gradient_norm is not None:
            parameters["max_gradient_norm"] = float(self.cfg.max_gradient_norm)
        if self.cfg.optimizer == "sgd":
            parameters = {
                key: value
                for key, value in parameters.items()
                if key
                in {
                    "learning_rate",
                    "min_learning_rate",
                    "weight_decay",
                    "max_gradient_norm",
                }
            }
        resource = ResourceContext.from_mapping(
            context.get(
                KEY_RESOURCE_CONTEXT,
                context.get(KEY_RESOURCE_CONTEXT_SHORT, {}),
            )
        )
        self._provider_resource_context = resource
        operands: dict[str, Any] = {"gradient": gradient_ref}
        for name, value in dict(slot_seed or {}).items():
            if value is not None:
                operands[str(name)] = np.asarray(value, dtype=float).reshape(-1)
        transition = gateway.transition(
            StateTransitionRequest(
                state_ref=state_ref,
                method_id=f"gradient.{self.cfg.optimizer}",
                operands=operands,
                slot_refs=dict(self._provider_slot_refs),
                parameters=parameters,
                step_index=int(self.step_index),
                metadata={"adapter": self.name},
            ),
            resource,
        )
        materialized = gateway.materialize(
            StateMaterializationRequest(
                state_ref=transition.state_ref,
                release_after=True,
                metadata={"adapter": self.name, "reason": "trainer_candidate"},
            ),
            resource,
        )
        if not isinstance(materialized.value, UnknownState):
            raise TypeError("gradient transition materialization must return UnknownState")
        self._capture_candidate_template(materialized.value)
        self.current_x = self._candidate_array(materialized.value)
        gradient_norm = transition.metrics.get("gradient_norm")
        if gradient_norm is not None:
            self.last_gradient_norm = float(gradient_norm)
        # materialize(release_after=True) intentionally releases this parameter
        # state.  Keeping its StateRef would make checkpoint evidence look live.
        self._provider_state_ref = None
        self._provider_slot_refs = dict(transition.slot_refs)
        self._provider_transition_count += 1
        self._provider_transition_needs_slot_seed = False

    def get_current_candidates(self) -> tuple[Any, ...] | None:
        if self.current_x is None:
            return None
        return (self._wrap_candidate(self.current_x.copy()),)

    def set_current_candidates(
        self,
        population: Any,
        objectives: Any | None = None,
        violations: Any | None = None,
    ) -> bool:
        if objectives is not None or violations is not None:
            if objectives is None or violations is None:
                raise ValueError(
                    "population snapshot restore requires both objectives and violations"
                )
            self.validate_population_snapshot(
                population,
                objectives,
                violations,
            )
            # NSGABlack runtime population publication describes the evaluated
            # batch, not the Adapter's already-computed successor.  Accepting it
            # would roll the gradient step back to the stale proposal.
            return False
        else:
            if isinstance(population, UnknownState):
                values = (population,)
            elif isinstance(population, np.ndarray) and population.ndim <= 1:
                values = (population,)
            else:
                values = tuple(population) if population is not None else tuple()
            if not values:
                self.current_x = None
                self._state_loaded = True
                return True
            candidate: Any = values[0]
        self._capture_candidate_template(candidate)
        self.current_x = self._candidate_array(candidate)
        self._state_loaded = True
        self._proposal_pending = False
        self._refresh_runtime_projection()
        return True

    def _score(self, objectives: np.ndarray) -> float:
        row = np.asarray(objectives, dtype=float).reshape(-1)
        if self.cfg.objective_aggregation == "first":
            return float(row[0])
        return float(np.sum(row))

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
                path="gradient_optimizer.candidate_metadata",
            )

    def _wrap_candidate(self, values: np.ndarray) -> Any:
        array = np.asarray(values, dtype=float).reshape(-1)
        if self._candidate_kind == "unknown_state":
            return UnknownState(
                values=array.copy(),
                metadata={
                    **detach_context_value(
                        self._candidate_metadata,
                        path="gradient_optimizer.candidate_metadata",
                    ),
                    "optimizer_method": f"gradient.{self.cfg.optimizer}",
                    "optimizer_step": int(self.step_index),
                },
            )
        return array.copy()

    def _repair_values(
        self,
        control: Any,
        values: np.ndarray,
        context: Dict[str, Any],
    ) -> np.ndarray:
        repaired = control.repair_candidate(self._wrap_candidate(values), context)
        self._capture_candidate_template(repaired)
        return self._candidate_array(repaired)

    def _clip_gradient(self, gradient: np.ndarray) -> np.ndarray:
        out = np.asarray(gradient, dtype=float).reshape(-1)
        limit = self.cfg.max_gradient_norm
        norm = float(np.linalg.norm(out))
        if limit is not None and norm > float(limit) and norm > 0.0:
            out = out * (float(limit) / norm)
        return out

    def _optimizer_delta(self, candidate: np.ndarray, gradient: np.ndarray) -> np.ndarray:
        learning_rate = max(
            float(self.cfg.min_learning_rate),
            float(self.cfg.learning_rate),
        )
        optimizer = self.cfg.optimizer
        weight_decay = float(self.cfg.weight_decay)

        effective_gradient = gradient
        if optimizer in {"sgd", "adam"} and weight_decay > 0.0:
            effective_gradient = gradient + (weight_decay * candidate)
        if optimizer == "sgd":
            return learning_rate * effective_gradient

        if self._first_moment is None or self._first_moment.shape != gradient.shape:
            self._first_moment = np.zeros_like(gradient)
            self._second_moment = np.zeros_like(gradient)
        beta1 = float(self.cfg.beta1)
        beta2 = float(self.cfg.beta2)
        self._first_moment = (beta1 * self._first_moment) + (
            (1.0 - beta1) * effective_gradient
        )
        self._second_moment = (beta2 * self._second_moment) + (
            (1.0 - beta2) * (effective_gradient ** 2)
        )
        time_index = int(self.step_index) + 1
        first_hat = self._first_moment / (1.0 - (beta1 ** time_index))
        second_hat = self._second_moment / (1.0 - (beta2 ** time_index))
        delta = learning_rate * first_hat / (
            np.sqrt(second_hat) + float(self.cfg.epsilon)
        )
        if optimizer == "adamw" and weight_decay > 0.0:
            delta = delta + (learning_rate * weight_decay * candidate)
        return np.asarray(delta, dtype=float)

    def _refresh_runtime_projection(self) -> None:
        self._runtime_projection = {
            KEY_MUTATION_SIGMA: float(self.cfg.learning_rate),
            KEY_ADAPTER_BEST_SCORE: self.best_score,
        }

    def get_runtime_context_projection(self, solver: Any) -> Dict[str, Any]:
        _ = solver
        return dict(self._runtime_projection)

    def get_runtime_context_projection_sources(self, solver: Any) -> Dict[str, str]:
        _ = solver
        source = f"adapter.{self.__class__.__name__}"
        return {key: source for key in self._runtime_projection}

    def _refresh_provider_slot_shadow(self) -> None:
        """Materialize optimizer slots only when persistent state is requested."""

        if not self._provider_slot_refs:
            return
        gateway = self.state_gateway
        resource = self._provider_resource_context
        if gateway is None or resource is None:
            raise RuntimeError(
                "provider optimizer slots are live but their materialization "
                "gateway/resource context is unavailable"
            )
        materialized: dict[str, np.ndarray] = {}
        for name, ref in self._provider_slot_refs.items():
            result = gateway.materialize(
                StateMaterializationRequest(
                    state_ref=ref,
                    release_after=False,
                    metadata={
                        "adapter": self.name,
                        "reason": "checkpoint_optimizer_slot",
                    },
                ),
                resource,
            )
            if not isinstance(result.value, UnknownState):
                raise TypeError(
                    "provider optimizer slot materialization must return UnknownState"
                )
            materialized[str(name)] = np.asarray(
                result.value.as_array(),
                dtype=float,
            ).reshape(-1).copy()
        if self.cfg.optimizer in {"adam", "adamw"}:
            if set(materialized) != {"m", "v"}:
                raise RuntimeError("Adam Provider checkpoint requires m/v slot states")
            self._first_moment = materialized["m"]
            self._second_moment = materialized["v"]

    def get_state(self) -> Mapping[str, Any]:
        self._refresh_provider_slot_shadow()
        return {
            "current_x": None if self.current_x is None else self.current_x.tolist(),
            "current_score": self.current_score,
            "best_score": self.best_score,
            "last_gradient_norm": self.last_gradient_norm,
            "step_index": int(self.step_index),
            "first_moment": (
                None if self._first_moment is None else self._first_moment.tolist()
            ),
            "second_moment": (
                None if self._second_moment is None else self._second_moment.tolist()
            ),
            "optimizer": self.cfg.optimizer,
            "candidate_kind": self._candidate_kind,
            "candidate_metadata": detach_context_value(
                self._candidate_metadata,
                path="gradient_optimizer.candidate_metadata",
            ),
            "provider_transition": {
                "enabled": bool(self.prefer_provider_transition),
                "count": int(self._provider_transition_count),
                "state_ref": (
                    None
                    if self._provider_state_ref is None
                    else self._provider_state_ref.as_dict()
                ),
                "slot_refs": {
                    name: ref.as_dict()
                    for name, ref in self._provider_slot_refs.items()
                },
                "checkpoint_mode": "on_demand_materialized_slot_shadow",
                "needs_slot_seed": bool(self._provider_transition_needs_slot_seed),
            },
        }

    def set_state(self, state: Mapping[str, Any]) -> None:
        saved_optimizer = str(state.get("optimizer", self.cfg.optimizer) or "").strip().lower()
        if saved_optimizer != self.cfg.optimizer:
            raise ValueError(
                "gradient optimizer checkpoint method does not match current config: "
                f"checkpoint={saved_optimizer}, current={self.cfg.optimizer}"
            )
        current_x = state.get("current_x")
        self.current_x = (
            None
            if current_x is None
            else np.asarray(current_x, dtype=float).reshape(-1)
        )
        score = state.get("current_score")
        self.current_score = None if score is None else float(score)
        best_score = state.get("best_score")
        self.best_score = None if best_score is None else float(best_score)
        norm = state.get("last_gradient_norm")
        self.last_gradient_norm = None if norm is None else float(norm)
        self.step_index = int(state.get("step_index", 0) or 0)
        candidate_kind = str(state.get("candidate_kind", "array") or "array")
        if candidate_kind not in {"array", "unknown_state"}:
            raise ValueError("unsupported gradient optimizer candidate kind")
        self._candidate_kind = candidate_kind
        self._candidate_metadata = detach_context_value(
            dict(state.get("candidate_metadata", {}) or {}),
            path="gradient_optimizer.candidate_metadata",
        )
        provider_transition = dict(state.get("provider_transition", {}) or {})
        self._provider_transition_count = int(
            provider_transition.get("count", 0) or 0
        )
        # StateRef is process-local and cannot be resurrected.  The next
        # Provider transition seeds fresh live slots from the exact materialized
        # optimizer shadow, so restore does not permanently change execution mode.
        self._provider_state_ref = None
        self._provider_slot_refs = {}
        self._provider_transition_needs_slot_seed = bool(
            provider_transition.get("needs_slot_seed")
            or provider_transition.get("state_ref")
            or provider_transition.get("slot_refs")
        )
        self._provider_resource_context = None
        first = state.get("first_moment")
        second = state.get("second_moment")
        self._first_moment = (
            None if first is None else np.asarray(first, dtype=float).reshape(-1)
        )
        self._second_moment = (
            None if second is None else np.asarray(second, dtype=float).reshape(-1)
        )
        if (self._first_moment is None) != (self._second_moment is None):
            raise ValueError("gradient optimizer checkpoint must contain both Adam moments")
        if self._first_moment is not None:
            if self.current_x is None:
                raise ValueError("gradient optimizer moments require a current candidate")
            if (
                self._first_moment.shape != self.current_x.shape
                or self._second_moment is None
                or self._second_moment.shape != self.current_x.shape
            ):
                raise ValueError(
                    "gradient optimizer checkpoint moments must match current candidate shape"
                )
        if self.step_index < 0:
            raise ValueError("gradient optimizer checkpoint step_index must be non-negative")
        self._state_loaded = True
        self._proposal_pending = False
        self._refresh_runtime_projection()


__all__ = ["GradientOptimizerAdapter", "GradientOptimizerConfig"]
