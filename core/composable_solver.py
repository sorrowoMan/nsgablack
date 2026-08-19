"""
Composable solver built on SolverBase.

This solver delegates the optimization logic to AlgorithmAdapter instances.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from blackbase.resources import ResourceContext
from blackbase.contracts import BatchDisposition

import numpy as np

from ..adapters import AlgorithmAdapter, CompositeAdapter
from .blank_solver import SolverBase
from .evaluation_feedback import OptimizationFeedbackBatch
from blackbase.context.context_keys import KEY_STEP
from .state.incumbent import (
    DEFAULT_INCUMBENT_POLICY_ID,
    IncumbentState,
    ScalarizationError,
)
from .runtime_governance import commit_population_snapshot, resolve_population_snapshot
from ..utils.extension_contracts import normalize_candidate_batch, stack_population


class ComposableSolver(SolverBase):
    """Solver wrapper that executes adapter-driven optimization loops."""

    def __init__(
        self,
        problem,
        adapter: Optional[AlgorithmAdapter] = None,
        bias_module=None,
        representation_pipeline=None,
        ignore_constraint_violation_when_bias: bool = False,
        plugin_strict: bool = False,
        snapshot_strict: bool = False,
        resource_context: Optional[Mapping[str, Any] | ResourceContext] = None,
        context_store_backend: str = "memory",
        context_store_ttl_seconds: Optional[float] = None,
        context_store_redis_url: str = "redis://localhost:6379/0",
        context_store_key_prefix: str = "nsgablack:context",
        snapshot_store_backend: str = "memory",
        snapshot_store_ttl_seconds: Optional[float] = None,
        snapshot_store_redis_url: str = "redis://localhost:6379/0",
        snapshot_store_key_prefix: str = "nsgablack:snapshot",
        snapshot_store_dir: Optional[str] = None,
        snapshot_store_serializer: str = "safe",
        snapshot_store_hmac_env_var: str = "NSGABLACK_SNAPSHOT_HMAC_KEY",
        snapshot_store_unsafe_allow_unsigned: bool = False,
        snapshot_store_max_payload_bytes: int = 8_388_608,
        context_inline_candidate_max_bytes: int = 4_096,
        snapshot_schema: str = "population_snapshot_v1",
        enable_convergence_monitor: bool = False,
        convergence_config: Optional[object] = None,
        enable_adaptive_parameters: bool = False,
        adaptive_config: Optional[object] = None,
        enable_companion_orchestrator: bool = False,
        companion_config: Optional[object] = None,
    ) -> None:
        super().__init__(
            problem=problem,
            bias_module=bias_module,
            representation_pipeline=representation_pipeline,
            ignore_constraint_violation_when_bias=ignore_constraint_violation_when_bias,
            plugin_strict=bool(plugin_strict),
            snapshot_strict=bool(snapshot_strict),
            resource_context=resource_context,
            context_store_backend=context_store_backend,
            context_store_ttl_seconds=context_store_ttl_seconds,
            context_store_redis_url=context_store_redis_url,
            context_store_key_prefix=context_store_key_prefix,
            snapshot_store_backend=snapshot_store_backend,
            snapshot_store_ttl_seconds=snapshot_store_ttl_seconds,
            snapshot_store_redis_url=snapshot_store_redis_url,
            snapshot_store_key_prefix=snapshot_store_key_prefix,
            snapshot_store_dir=snapshot_store_dir,
            snapshot_store_serializer=snapshot_store_serializer,
            snapshot_store_hmac_env_var=snapshot_store_hmac_env_var,
            snapshot_store_unsafe_allow_unsigned=snapshot_store_unsafe_allow_unsigned,
            snapshot_store_max_payload_bytes=snapshot_store_max_payload_bytes,
            context_inline_candidate_max_bytes=context_inline_candidate_max_bytes,
            snapshot_schema=snapshot_schema,
            enable_convergence_monitor=bool(enable_convergence_monitor),
            convergence_config=convergence_config,
            enable_adaptive_parameters=bool(enable_adaptive_parameters),
            adaptive_config=adaptive_config,
            enable_companion_orchestrator=bool(enable_companion_orchestrator),
            companion_config=companion_config,
        )
        self.adapter: Optional[AlgorithmAdapter] = adapter
        self.last_step_summary: Dict[str, Any] = {}
        self._objective_scalarizer = None
        self.incumbent_scalarizer_id = DEFAULT_INCUMBENT_POLICY_ID
        self.incumbent_scalarizer_context: Dict[str, Any] = {}
        self.scalarizer_failure_policy = "raise"
        self.scalarizer_fallback_count = 0
        self.result_quality_degraded = False
        self.scalarizer_audit_complete = True

    @property
    def objective_scalarizer(self):
        """Stable pointwise scalarizer used only for run-wide incumbent ranking."""

        return self._objective_scalarizer

    @objective_scalarizer.setter
    def objective_scalarizer(self, scalarizer) -> None:
        with self._incumbent_lock:
            incumbent = self._incumbent_commit.state
            if incumbent is not None:
                if scalarizer is self._objective_scalarizer:
                    return
                raise ScalarizationError(
                    "cannot replace the incumbent scalarizer during an active run",
                    policy_id=self.incumbent_scalarizer_id,
                )
            self._objective_scalarizer = scalarizer
            if scalarizer is None:
                self.incumbent_scalarizer_id = DEFAULT_INCUMBENT_POLICY_ID
                return
            module = str(getattr(scalarizer, "__module__", "unknown"))
            name = str(
                getattr(
                    scalarizer,
                    "__qualname__",
                    getattr(scalarizer, "__name__", type(scalarizer).__name__),
                )
            )
            self.incumbent_scalarizer_id = f"pointwise:{module}.{name}"

    def set_incumbent_scalarizer(
        self,
        scalarizer,
        *,
        policy_id: str,
        context: Optional[Mapping[str, Any]] = None,
        failure_policy: str = "raise",
    ) -> "ComposableSolver":
        """Configure a stable row-wise scoring policy for run-wide incumbents."""

        normalized_policy = str(failure_policy or "raise").strip().lower()
        if normalized_policy not in {"raise", "fallback_sum"}:
            raise ValueError(
                "scalarizer failure_policy must be 'raise' or 'fallback_sum'"
            )
        normalized_id = str(policy_id or "").strip()
        if not normalized_id:
            raise ValueError("incumbent scalarizer policy_id must not be empty")
        normalized_context = dict(context or {})
        with self._incumbent_lock:
            incumbent = self._incumbent_commit.state
            if incumbent is not None:
                unchanged = (
                    scalarizer is self._objective_scalarizer
                    and normalized_id == self.incumbent_scalarizer_id
                    and self._policy_context_signature(normalized_context)
                    == self._policy_context_signature(
                        self.incumbent_scalarizer_context
                    )
                    and normalized_policy == self.scalarizer_failure_policy
                )
                if unchanged:
                    return self
                raise ScalarizationError(
                    "cannot change incumbent selection policy during an active run",
                    policy_id=normalized_id,
                )
            self.objective_scalarizer = scalarizer
            self.incumbent_scalarizer_id = normalized_id
            self.incumbent_scalarizer_context = normalized_context
            self.scalarizer_failure_policy = normalized_policy
        return self

    @classmethod
    def _policy_context_signature(cls, value: Any) -> Any:
        if isinstance(value, Mapping):
            return tuple(
                (str(key), cls._policy_context_signature(item))
                for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            )
        if isinstance(value, np.ndarray):
            return cls._policy_context_signature(value.tolist())
        if isinstance(value, (list, tuple)):
            return tuple(cls._policy_context_signature(item) for item in value)
        if isinstance(value, np.generic):
            return value.item()
        return value

    def _validate_incumbent_commit(self, state: IncumbentState) -> None:
        super()._validate_incumbent_commit(state)
        expected_policy_id = str(
            getattr(self, "incumbent_scalarizer_id", DEFAULT_INCUMBENT_POLICY_ID)
        )
        if state.policy_id != expected_policy_id:
            raise ScalarizationError(
                "incumbent commit policy does not match the configured scalarizer",
                phase="incumbent_commit",
                policy_id=expected_policy_id,
            )
        expected_context = dict(
            getattr(self, "incumbent_scalarizer_context", {}) or {}
        )
        if self._policy_context_signature(
            state.policy_context
        ) != self._policy_context_signature(expected_context):
            raise ScalarizationError(
                "incumbent commit policy context does not match the configured scalarizer",
                phase="incumbent_commit",
                policy_id=expected_policy_id,
            )

    def set_adapter(self, adapter: AlgorithmAdapter) -> None:
        self.adapter = adapter

    def set_adapters(self, adapters: Sequence[AlgorithmAdapter]) -> None:
        self.adapter = CompositeAdapter(list(adapters))

    def setup(self) -> None:
        if self.adapter is not None:
            self.adapter.setup(self)

    def teardown(self) -> None:
        if self.adapter is not None:
            self.adapter.teardown(self)

    def _notify_proposal_disposition(
        self,
        *,
        proposed_count: int,
        accepted_count: int,
        context: Dict[str, Any],
        reason: str,
    ) -> None:
        proposed = int(proposed_count)
        accepted = int(accepted_count)
        if accepted == proposed:
            return
        disposition = BatchDisposition.prefix(
            proposed_count=proposed,
            accepted_count=accepted,
            reason=reason,
            metadata={"control": type(self).__name__},
        )
        if self.adapter is None:
            raise RuntimeError("proposal disposition requires an attached adapter")
        self.adapter.on_proposal_disposition(
            self,
            disposition,
            context,
        )

    def step(self) -> None:
        if self.adapter is None or bool(getattr(self, "stop_requested", False)):
            return

        propose_context = self.build_context()
        propose_context[KEY_STEP] = self.generation

        proposed = self.adapter.coerce_candidates(self.adapter.propose(self, propose_context))
        candidate_provenance = self.prepare_candidate_provenance(proposed)
        candidate_batch = normalize_candidate_batch(
            proposed,
            dimension=self.dimension,
            owner=getattr(self.adapter, "name", "adapter"),
            candidate_tokens=[item.candidate_token for item in candidate_provenance],
        )
        candidates, candidate_provenance = self.bind_candidate_batch(
            candidate_batch,
            candidate_provenance,
            activate=False,
        )
        requested_count = len(candidates)
        approved_count = self.evaluation_batch_allowance(
            requested_count,
            context=propose_context,
        )
        if approved_count <= 0:
            self._active_candidate_provenance = []
            if requested_count > 0:
                self._notify_proposal_disposition(
                    proposed_count=requested_count,
                    accepted_count=0,
                    context=propose_context,
                    reason="evaluation_budget_exhausted",
                )
                self.last_step_summary = {
                    "num_proposed": int(requested_count),
                    "num_candidates": 0,
                    "budget_truncated": True,
                }
                self.request_stop()
            return
        if approved_count < requested_count:
            candidates = candidates[:approved_count]
            candidate_provenance = candidate_provenance[:approved_count]
        # If a representation pipeline is attached, enforce a repair pass so
        # all adapter-produced candidates go through the main pipeline.
        if len(candidates) > 0 and self.representation_pipeline is not None:
            repair = getattr(self.representation_pipeline, "repair", None)
            if repair is not None:
                if hasattr(self.representation_pipeline, "repair_batch"):
                    repaired = self.representation_pipeline.repair_batch(
                        candidates,
                        context=propose_context,
                    )
                else:
                    repaired = [
                        self.repair_candidate(cand, propose_context)
                        for cand in candidates
                    ]
                candidate_batch = normalize_candidate_batch(
                    repaired,
                    dimension=self.dimension,
                    owner=f"{getattr(self.adapter, 'name', 'adapter')}.repair",
                    candidate_tokens=[
                        item.candidate_token for item in candidate_provenance
                    ],
                )
                candidates, candidate_provenance = self.bind_candidate_batch(
                    candidate_batch,
                    candidate_provenance,
                    activate=False,
                )
        candidate_count = len(candidates)
        if candidate_count != approved_count:
            raise ValueError(
                "Representation repair must preserve candidate count: "
                f"expected={approved_count}, actual={candidate_count}"
            )

        self.bind_candidate_provenance(candidates, candidate_provenance)
        self.population = stack_population(candidates, name="ComposableSolver.population")
        self.activate_candidate_provenance(self.population, candidate_provenance)
        (
            self.population,
            self.objectives,
            self.constraint_violations,
            reservation_truncated,
        ) = self._evaluate_population_with_budget_retry(self.population)
        accepted_count = int(self.population.shape[0])
        self._active_candidate_provenance = candidate_provenance[:accepted_count]
        self.activate_candidate_provenance(
            self.population,
            self._active_candidate_provenance,
        )
        self._notify_proposal_disposition(
            proposed_count=requested_count,
            accepted_count=accepted_count,
            context=propose_context,
            reason=(
                "evaluation_budget_race"
                if reservation_truncated
                else "evaluation_budget_allowance"
            ),
        )
        if accepted_count == 0:
            self.last_step_summary = {
                "num_proposed": int(requested_count),
                "num_candidates": 0,
                "budget_truncated": True,
            }
            self.request_stop()
            return
        incumbent_selection = self.select_best_with_score(
            self.objectives,
            self.constraint_violations,
        )
        self.last_step_summary = self._summarize_step(
            self.objectives,
            self.constraint_violations,
            selection=incumbent_selection,
        )
        self.last_step_summary.update(
            {
                "num_proposed": int(requested_count),
                "budget_truncated": bool(
                    approved_count < requested_count
                    or reservation_truncated
                ),
            }
        )

        self._update_best(
            self.population,
            self.objectives,
            self.constraint_violations,
            selection=incumbent_selection,
        )
        update_context = self.build_context()
        update_context[KEY_STEP] = self.generation
        feedback_batch = self.get_last_feedback_batch()
        if (
            feedback_batch is None
            or feedback_batch.candidate_count != accepted_count
        ):
            feedback_batch = OptimizationFeedbackBatch.from_arrays(
                self.objectives,
                self.constraint_violations,
                metadata={"evaluation_path": "legacy_solver"},
            )
        else:
            feedback_batch = feedback_batch.with_arrays(
                self.objectives,
                self.constraint_violations,
            )
        self.adapter.update(
            self,
            self.population,
            feedback_batch,
            update_context,
        )
        authoritative_population, authoritative_objectives, authoritative_violations = (
            resolve_population_snapshot(self, prefer_adapter=True)
        )
        commit_population_snapshot(
            self,
            authoritative_population,
            authoritative_objectives,
            authoritative_violations,
            strict=True,
        )

    def _normalize_violation_values(
        self,
        violations: Optional[np.ndarray],
        *,
        rows: int,
    ) -> np.ndarray:
        if violations is None:
            return np.zeros((rows,), dtype=float)
        values = np.asarray(violations, dtype=float).reshape(-1)
        if values.shape[0] != rows:
            raise ValueError(
                "constraint violations must align with objective rows: "
                f"expected={rows}, actual={values.shape[0]}"
            )
        return values

    def _candidate_objective_score(
        self,
        objectives: np.ndarray,
        violations: np.ndarray,
        idx: int,
    ) -> float:
        scalarizer = self.objective_scalarizer
        objective_row = np.asarray(objectives[idx], dtype=float).reshape(-1)
        violation = float(violations[idx])
        if callable(scalarizer):
            try:
                score = float(
                    scalarizer(
                        objective_row.copy(),
                        violation,
                        dict(self.incumbent_scalarizer_context),
                    )
                )
                if not np.isfinite(score):
                    raise ValueError("scalarizer returned a non-finite score")
            except Exception as exc:
                policy = str(self.scalarizer_failure_policy or "raise").strip().lower()
                if policy != "fallback_sum":
                    raise ScalarizationError(
                        "incumbent scalarization failed",
                        candidate_index=int(idx),
                        objective_row=objective_row,
                        violation=violation,
                        policy_id=self.incumbent_scalarizer_id,
                    ) from exc
                self.scalarizer_fallback_count += 1
                self.result_quality_degraded = True
                score = float(np.sum(objective_row))
        else:
            score = float(np.sum(objective_row))
        return score if np.isfinite(score) else float("inf")

    @staticmethod
    def _order_key_from_score(violation: float, score: float) -> Tuple[int, float, float]:
        normalized_violation = float(violation)
        if not np.isfinite(normalized_violation):
            normalized_violation = float("inf")
        feasible = normalized_violation <= 0.0
        return (
            0 if feasible else 1,
            0.0 if feasible else normalized_violation,
            float(score),
        )

    def _candidate_order_key(
        self,
        objectives: np.ndarray,
        violations: np.ndarray,
        idx: int,
    ) -> Tuple[int, float, float]:
        return self._order_key_from_score(
            float(violations[idx]),
            self._candidate_objective_score(objectives, violations, idx),
        )

    def select_best_with_score(
        self,
        objectives: np.ndarray,
        violations: np.ndarray,
    ) -> Tuple[int, float]:
        objective_values = np.asarray(objectives, dtype=float)
        if objective_values.ndim == 1:
            objective_values = objective_values.reshape(-1, 1)
        if objective_values.ndim != 2 or objective_values.shape[0] == 0:
            return 0, float("inf")
        violation_values = self._normalize_violation_values(
            violations,
            rows=objective_values.shape[0],
        )
        keys = [
            self._candidate_order_key(
                objective_values,
                violation_values,
                idx,
            )
            for idx in range(objective_values.shape[0])
        ]
        best_idx = min(range(len(keys)), key=keys.__getitem__)
        return int(best_idx), float(keys[best_idx][2])

    def select_best(self, objectives: np.ndarray, violations: np.ndarray) -> int:
        best_idx, _ = self.select_best_with_score(objectives, violations)
        return best_idx

    def _update_best(
        self,
        population: np.ndarray,
        objectives: np.ndarray,
        violations: np.ndarray,
        *,
        selection: Optional[Tuple[int, float]] = None,
    ) -> None:
        if population is None or len(population) == 0:
            return
        population_values = np.asarray(population, dtype=float)
        objective_values = np.asarray(objectives, dtype=float)
        if objective_values.ndim == 1:
            objective_values = objective_values.reshape(-1, 1)
        if population_values.ndim != 2 or objective_values.ndim != 2:
            raise ValueError("incumbent candidates and objectives must be two-dimensional")
        if population_values.shape[0] != objective_values.shape[0]:
            raise ValueError("incumbent candidates and objectives must have matching rows")
        violation_values = self._normalize_violation_values(
            violations,
            rows=objective_values.shape[0],
        )

        best_idx, best_score = (
            self.select_best_with_score(objective_values, violation_values)
            if selection is None
            else (int(selection[0]), float(selection[1]))
        )
        best_violation = float(violation_values[best_idx])
        if not np.isfinite(best_score) or not np.isfinite(best_violation):
            return
        incumbent = self.get_incumbent()
        if incumbent is not None:
            if incumbent.policy_id != self.incumbent_scalarizer_id:
                raise ScalarizationError(
                    "incumbent scalarizer policy changed during an active run",
                    policy_id=self.incumbent_scalarizer_id,
                )
            if self._policy_context_signature(
                incumbent.policy_context
            ) != self._policy_context_signature(self.incumbent_scalarizer_context):
                raise ScalarizationError(
                    "incumbent scalarizer context changed during an active run",
                    policy_id=self.incumbent_scalarizer_id,
                )
            incumbent_key = self._order_key_from_score(
                incumbent.constraint_violation,
                incumbent.score,
            )
            candidate_key = self._order_key_from_score(best_violation, best_score)
            if incumbent_key <= candidate_key:
                return

        candidate = np.asarray(population_values[best_idx], dtype=float).reshape(-1)
        provenance = self.incumbent_source_for(
            candidate,
            candidate_index=best_idx,
            population=population_values,
        )
        evaluation_id = (
            f"{self._active_run_id or 'unscoped'}:generation:{int(self.generation)}:"
            f"evaluation:{int(self.evaluation_count)}:candidate:{int(best_idx)}"
        )
        self.set_incumbent(
            IncumbentState(
                candidate=candidate,
                objectives=objective_values[best_idx],
                constraint_violation=best_violation,
                score=best_score,
                policy_id=self.incumbent_scalarizer_id,
                policy_context=self.incumbent_scalarizer_context,
                evaluation_id=evaluation_id,
                candidate_token=provenance.get("candidate_token"),
                source=provenance["source"],
                source_run_id=provenance.get("source_run_id"),
                warm_start_id=provenance.get("warm_start_id"),
                proposal_id=provenance.get("proposal_id"),
                metadata=provenance.get("metadata", {}),
            )
        )

    def _summarize_step(
        self,
        objectives: np.ndarray,
        violations: np.ndarray,
        *,
        selection: Optional[Tuple[int, float]] = None,
    ) -> Dict[str, Any]:
        if objectives is None or len(objectives) == 0:
            return {}
        objective_values = np.asarray(objectives, dtype=float)
        if objective_values.ndim == 1:
            objective_values = objective_values.reshape(-1, 1)
        violation_values = self._normalize_violation_values(
            violations,
            rows=objective_values.shape[0],
        )
        best_idx, best_score = (
            self.select_best_with_score(objective_values, violation_values)
            if selection is None
            else (int(selection[0]), float(selection[1]))
        )
        return {
            "best_objective": best_score,
            "best_constraint_violation": float(violation_values[best_idx]),
            "best_index": int(best_idx),
            "num_candidates": int(len(objective_values)),
        }
