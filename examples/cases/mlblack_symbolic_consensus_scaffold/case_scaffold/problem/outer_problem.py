from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from nsgablack.core.base import BlackBoxProblem
from nsgablack.plugins.solver_backends.mlblack_symbolic_consensus_backend import (
    MlblackSymbolicConsensusBackendConfig,
)


def _clip_int(value: float, *, low: int, high: int) -> int:
    return int(np.clip(np.round(float(value)), int(low), int(high)))


def _clip_float(value: float, *, low: float, high: float) -> float:
    return float(np.clip(float(value), float(low), float(high)))


@dataclass(frozen=True)
class MlblackConsensusSearchSpace:
    candidate_limit: tuple[int, int] = (24, 140)
    group_count: tuple[int, int] = (4, 24)
    seed_candidate_count: tuple[int, int] = (4, 24)
    max_basis_count: tuple[int, int] = (2, 8)
    greedy_choice_topk: tuple[int, int] = (2, 8)
    random_group_trials: tuple[int, int] = (1, 16)
    core_min_support_rate: tuple[float, float] = (0.35, 0.9)
    core_max_terms: tuple[int, int] = (1, 6)


class MlblackSymbolicConsensusOuterProblem(BlackBoxProblem):
    """Outer problem: nsgablack tunes mlblack symbolic consensus orchestration."""

    context_requires = ()
    context_provides = ("mlblack_symbolic_consensus_metrics",)
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "L1 candidate controls symbolic basis-search and consensus budget knobs; "
        "L2 delegates full symbolic execution to mlblack.",
    )

    def __init__(
        self,
        *,
        benchmark_key: str,
        backend_config: MlblackSymbolicConsensusBackendConfig,
        search_space: MlblackConsensusSearchSpace | None = None,
    ) -> None:
        self.benchmark_key = str(benchmark_key)
        self.backend_config = backend_config
        self.search_space = search_space or MlblackConsensusSearchSpace()
        self.last_inner_result: dict[str, Any] | None = None
        self.best_inner_result: dict[str, Any] | None = None
        self.best_objective_vector: np.ndarray | None = None
        bounds = {
            "x0": list(self.search_space.candidate_limit),
            "x1": list(self.search_space.group_count),
            "x2": list(self.search_space.seed_candidate_count),
            "x3": list(self.search_space.max_basis_count),
            "x4": list(self.search_space.greedy_choice_topk),
            "x5": list(self.search_space.random_group_trials),
            "x6": list(self.search_space.core_min_support_rate),
            "x7": list(self.search_space.core_max_terms),
        }
        super().__init__(
            name=f"MlblackSymbolicConsensusOuterProblem[{self.benchmark_key}]",
            dimension=8,
            bounds=bounds,
            objectives=["exact_term_gap", "family_term_gap", "test_rmse", "outer_complexity"],
        )

    def _decode_plan(self, x: np.ndarray) -> dict[str, Any]:
        arr = np.asarray(x, dtype=float).reshape(self.dimension)
        candidate_limit = _clip_int(
            arr[0],
            low=self.search_space.candidate_limit[0],
            high=self.search_space.candidate_limit[1],
        )
        seed_candidate_count = _clip_int(
            arr[2],
            low=self.search_space.seed_candidate_count[0],
            high=min(self.search_space.seed_candidate_count[1], candidate_limit),
        )
        max_basis_count = _clip_int(
            arr[3],
            low=self.search_space.max_basis_count[0],
            high=self.search_space.max_basis_count[1],
        )
        trainer_overrides = {
            "orth_candidate_limit": candidate_limit,
            "orth_group_count": _clip_int(
                arr[1],
                low=self.search_space.group_count[0],
                high=self.search_space.group_count[1],
            ),
            "orth_seed_candidate_count": seed_candidate_count,
            "orth_min_basis_count": min(2, max_basis_count),
            "orth_max_basis_count": max_basis_count,
            "greedy_choice_topk": _clip_int(
                arr[4],
                low=self.search_space.greedy_choice_topk[0],
                high=self.search_space.greedy_choice_topk[1],
            ),
            "random_group_trials": _clip_int(
                arr[5],
                low=self.search_space.random_group_trials[0],
                high=self.search_space.random_group_trials[1],
            ),
        }
        return {
            "benchmark_key": self.benchmark_key,
            "consensus_cycles": int(self.backend_config.consensus_cycles),
            "unlocked_runs_per_cycle": int(self.backend_config.unlocked_runs_per_cycle),
            "locked_runs_per_cycle": int(self.backend_config.locked_runs_per_cycle),
            "vanilla_runs": int(self.backend_config.vanilla_runs),
            "locked_runs": int(self.backend_config.locked_runs),
            "core_equivalence_mode": str(self.backend_config.core_equivalence_mode),
            "core_min_support_rate": _clip_float(
                arr[6],
                low=self.search_space.core_min_support_rate[0],
                high=self.search_space.core_min_support_rate[1],
            ),
            "core_max_terms": _clip_int(
                arr[7],
                low=self.search_space.core_max_terms[0],
                high=self.search_space.core_max_terms[1],
            ),
            "trainer_params_overrides": trainer_overrides,
        }

    def evaluate(self, x: np.ndarray) -> np.ndarray:
        _ = x
        return np.array(
            [1.0, 1.0, float(self.backend_config.fallback_objective), self._complexity_score(x)],
            dtype=float,
        )

    def evaluate_constraints(self, x: np.ndarray) -> np.ndarray:
        decoded = self._decode_plan(x)
        overrides = dict(decoded.get("trainer_params_overrides", {}) or {})
        candidate_limit = int(overrides.get("orth_candidate_limit", 0) or 0)
        group_count = int(overrides.get("orth_group_count", 0) or 0)
        seed_candidate_count = int(overrides.get("orth_seed_candidate_count", 0) or 0)
        max_basis_count = int(overrides.get("orth_max_basis_count", 0) or 0)
        core_max_terms = int(decoded.get("core_max_terms", 0) or 0)
        return np.asarray(
            [
                max(0.0, float(seed_candidate_count - candidate_limit)),
                max(0.0, float(group_count - candidate_limit)),
                max(0.0, float(core_max_terms - max_basis_count)),
            ],
            dtype=float,
        )

    def _complexity_score(self, x: np.ndarray) -> float:
        decoded = self._decode_plan(x)
        overrides = dict(decoded.get("trainer_params_overrides", {}) or {})
        space = self.search_space

        def norm(value: float, bounds: tuple[float, float]) -> float:
            low, high = float(bounds[0]), float(bounds[1])
            if high <= low:
                return 0.0
            return float(np.clip((float(value) - low) / (high - low), 0.0, 1.0))

        parts = [
            norm(float(overrides.get("orth_candidate_limit", space.candidate_limit[0])), space.candidate_limit),
            norm(float(overrides.get("orth_group_count", space.group_count[0])), space.group_count),
            norm(float(overrides.get("orth_seed_candidate_count", space.seed_candidate_count[0])), space.seed_candidate_count),
            norm(float(overrides.get("orth_max_basis_count", space.max_basis_count[0])), space.max_basis_count),
            norm(float(overrides.get("greedy_choice_topk", space.greedy_choice_topk[0])), space.greedy_choice_topk),
            norm(float(overrides.get("random_group_trials", space.random_group_trials[0])), space.random_group_trials),
            norm(float(decoded.get("core_max_terms", space.core_max_terms[0])), space.core_max_terms),
        ]
        return float(np.mean(parts))

    def build_inner_problem(self, x: np.ndarray, eval_context: dict[str, Any]) -> dict[str, Any]:
        decoded = self._decode_plan(x)
        generation = int(eval_context.get("generation", 0))
        individual_id = int(eval_context.get("individual_id", 0))
        decoded["run_label"] = f"g{generation:03d}_i{individual_id:03d}"
        return decoded

    def evaluate_from_inner_result(
        self,
        x: np.ndarray,
        inner_result: dict[str, Any],
        eval_context: dict[str, Any],
    ) -> np.ndarray:
        _ = (x, eval_context)
        self.last_inner_result = dict(inner_result)
        exact = _clip_float(
            float(inner_result.get("best_exact_term_recovery_score", 0.0) or 0.0),
            low=0.0,
            high=1.0,
        )
        family = _clip_float(
            float(inner_result.get("best_family_level_term_recovery_score", 0.0) or 0.0),
            low=0.0,
            high=1.0,
        )
        rmse = float(inner_result.get("best_test_rmse", self.backend_config.fallback_objective))
        if not np.isfinite(rmse):
            rmse = float(self.backend_config.fallback_objective)
        objective = np.array([1.0 - exact, 1.0 - family, rmse, self._complexity_score(x)], dtype=float)
        if self.best_objective_vector is None or float(np.sum(objective)) < float(np.sum(self.best_objective_vector)):
            self.best_objective_vector = np.asarray(objective, dtype=float)
            self.best_inner_result = dict(inner_result)
        return objective
