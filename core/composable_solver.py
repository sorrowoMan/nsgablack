"""
Composable solver built on SolverBase.

This solver delegates the optimization logic to AlgorithmAdapter instances.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np

from ..adapters import AlgorithmAdapter, CompositeAdapter
from .blank_solver import SolverBase
from ..utils.context.context_keys import KEY_STEP
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
    ) -> None:
        super().__init__(
            problem=problem,
            bias_module=bias_module,
            representation_pipeline=representation_pipeline,
            ignore_constraint_violation_when_bias=ignore_constraint_violation_when_bias,
            plugin_strict=bool(plugin_strict),
            snapshot_strict=bool(snapshot_strict),
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
        )
        self.adapter: Optional[AlgorithmAdapter] = adapter
        self.best_x: Optional[np.ndarray] = None
        self.best_objective: Optional[float] = None
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

    def step(self) -> None:
        if self.adapter is None:
            return

        context = self.build_context()
        context[KEY_STEP] = self.generation

        proposed = self.adapter.coerce_candidates(self.adapter.propose(self, context))
        candidates = normalize_candidates(
            proposed,
            dimension=self.dimension,
            owner=getattr(self.adapter, "name", "adapter"),
        )
        # If a representation pipeline is attached, enforce a repair pass so
        # all adapter-produced candidates go through the main pipeline.
        if len(candidates) > 0 and self.representation_pipeline is not None:
            repair = getattr(self.representation_pipeline, "repair", None)
            if repair is not None:
                if hasattr(self.representation_pipeline, "repair_batch"):
                    contexts = [context] * len(candidates)
                    candidates = self.representation_pipeline.repair_batch(candidates, contexts=contexts)
                else:
                    candidates = [self.repair_candidate(cand, context) for cand in candidates]
        if candidates is None:
            return
        try:
            candidate_count = len(candidates)
        except Exception:
            candidates = [candidates]  # type: ignore[list-item]
            candidate_count = 1
        if candidate_count <= 0:
            return

        self.population = stack_population(candidates, name="ComposableSolver.population")
        self.objectives, self.constraint_violations = self.evaluate_population(self.population)
        self.last_step_summary = self._summarize_step(self.objectives, self.constraint_violations)

        self._update_best(self.population, self.objectives, self.constraint_violations)
        self.adapter.update(
            self,
            self.population,
            self.objectives,
            self.constraint_violations,
            context,
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

    def _summarize_step(self, objectives: np.ndarray, violations: np.ndarray) -> Dict[str, Any]:
        if objectives is None or len(objectives) == 0:
            return {}
        best_idx = self.select_best(objectives, violations)
        return {
            "best_objective": float(np.sum(objectives[best_idx])),
            "best_index": int(best_idx),
            "num_candidates": int(len(objectives)),
        }
