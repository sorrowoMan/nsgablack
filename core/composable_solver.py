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
from ..core.state.context_keys import KEY_STEP
from .runtime_governance import commit_population_snapshot, resolve_population_snapshot
from ..utils.extension_contracts import normalize_candidates, stack_population


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
            snapshot_schema=snapshot_schema,
            enable_convergence_monitor=bool(enable_convergence_monitor),
            convergence_config=convergence_config,
            enable_adaptive_parameters=bool(enable_adaptive_parameters),
            adaptive_config=adaptive_config,
            enable_companion_orchestrator=bool(enable_companion_orchestrator),
            companion_config=companion_config,
        )
        self.adapter: Optional[AlgorithmAdapter] = adapter
        self.best_x: Optional[np.ndarray] = None
        self.best_objective: Optional[float] = None
        self.best_objectives: Optional[np.ndarray] = None
        self.best_constraint_violation: Optional[float] = None
        self.last_step_summary: Dict[str, Any] = {}
        # Optional scalarizer for multi-objective summaries (best_x/summary only).
        # Signature: fn(objectives: np.ndarray, violations: np.ndarray, idx: int) -> float
        self.objective_scalarizer = None

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
        candidates = normalize_candidates(
            proposed,
            dimension=self.dimension,
            owner=getattr(self.adapter, "name", "adapter"),
        )
        requested_count = len(candidates)
        approved_count = self.evaluation_batch_allowance(
            requested_count,
            context=propose_context,
        )
        if approved_count <= 0:
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
        # If a representation pipeline is attached, enforce a repair pass so
        # all adapter-produced candidates go through the main pipeline.
        if len(candidates) > 0 and self.representation_pipeline is not None:
            repair = getattr(self.representation_pipeline, "repair", None)
            if repair is not None:
                if hasattr(self.representation_pipeline, "repair_batch"):
                    candidates = self.representation_pipeline.repair_batch(candidates, context=propose_context)
                else:
                    candidates = [self.repair_candidate(cand, propose_context) for cand in candidates]
        candidate_count = len(candidates)
        if candidate_count != approved_count:
            raise ValueError(
                "Representation repair must preserve candidate count: "
                f"expected={approved_count}, actual={candidate_count}"
            )

        self.population = stack_population(candidates, name="ComposableSolver.population")
        (
            self.population,
            self.objectives,
            self.constraint_violations,
            reservation_truncated,
        ) = self._evaluate_population_with_budget_retry(self.population)
        accepted_count = int(self.population.shape[0])
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
        self.last_step_summary = self._summarize_step(self.objectives, self.constraint_violations)
        self.last_step_summary.update(
            {
                "num_proposed": int(requested_count),
                "budget_truncated": bool(
                    approved_count < requested_count
                    or reservation_truncated
                ),
            }
        )

        self._update_best(self.population, self.objectives, self.constraint_violations)
        update_context = self.build_context()
        update_context[KEY_STEP] = self.generation
        self.adapter.update(
            self,
            self.population,
            (self.objectives, self.constraint_violations),
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

    def select_best(self, objectives: np.ndarray, violations: np.ndarray) -> int:
        scores = []
        scalarizer = self.objective_scalarizer
        for idx, obj in enumerate(objectives):
            vio = violations[idx] if violations is not None else 0.0
            if callable(scalarizer):
                try:
                    score = float(scalarizer(objectives, violations, idx))
                except Exception:
                    score = float(vio) * 1e6 + float(np.sum(obj))
            else:
                score = float(vio) * 1e6 + float(np.sum(obj))
            scores.append(score)
        return int(np.argmin(scores)) if scores else 0

    def _update_best(
        self,
        population: np.ndarray,
        objectives: np.ndarray,
        violations: np.ndarray,
    ) -> None:
        if population is None or len(population) == 0:
            return
        best_idx = self.select_best(objectives, violations)
        best_obj = float(np.sum(objectives[best_idx]))
        if self.best_objective is None or best_obj < self.best_objective:
            self.best_objective = best_obj
            self.best_x = np.asarray(population[best_idx])
            self.best_objectives = np.asarray(objectives[best_idx], dtype=float).reshape(-1)
            violation_values = (
                np.asarray(violations, dtype=float).reshape(-1)
                if violations is not None
                else np.zeros((len(objectives),), dtype=float)
            )
            self.best_constraint_violation = (
                float(violation_values[best_idx])
                if violation_values.shape[0] > best_idx
                else None
            )

    def _summarize_step(self, objectives: np.ndarray, violations: np.ndarray) -> Dict[str, Any]:
        if objectives is None or len(objectives) == 0:
            return {}
        best_idx = self.select_best(objectives, violations)
        return {
            "best_objective": float(np.sum(objectives[best_idx])),
            "best_index": int(best_idx),
            "num_candidates": int(len(objectives)),
        }
