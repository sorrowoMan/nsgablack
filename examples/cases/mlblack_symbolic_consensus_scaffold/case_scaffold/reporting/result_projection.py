# -*- coding: utf-8 -*-
"""Result projection for the mlblack symbolic consensus outer solver."""

from __future__ import annotations

import numpy as np

from nsgablack.core.composable_solver import ComposableSolver


class MlblackConsensusOuterSolver(ComposableSolver):
    """Promote the best inner orchestration surface into the outer run result."""

    def _build_run_result(self, base_result):
        out = dict(base_result)
        out["generation"] = int(getattr(self, "generation", 0))
        out["evaluation_count"] = int(getattr(self, "evaluation_count", 0))
        if getattr(self, "best_objective", None) is not None:
            out["best_objective"] = float(self.best_objective)
        if getattr(self, "best_x", None) is not None:
            out["best_x"] = np.asarray(self.best_x, dtype=float).tolist()

        problem = getattr(self, "problem", None)
        inner_result = None
        if problem is not None:
            best_inner = getattr(problem, "best_inner_result", None)
            last_inner = getattr(problem, "last_inner_result", None)
            inner_result = best_inner if isinstance(best_inner, dict) else last_inner
        if not isinstance(inner_result, dict):
            return out

        for key in (
            "benchmark_key",
            "signature",
            "best_phase",
            "best_cycle_index",
            "best_cycle_key",
            "best_run_id",
            "best_artifact_id",
            "best_expression",
            "best_test_rmse",
            "best_test_r2",
            "best_rmse_run_id",
            "best_rmse_artifact_id",
            "best_rmse_phase",
            "best_rmse_cycle_index",
            "best_rmse_cycle_key",
            "best_rmse_expression",
            "best_rmse_test_rmse",
            "best_rmse_test_r2",
            "best_rmse_exact_term_recovery_score",
            "best_rmse_phase_equivalent_term_recovery_score",
            "best_rmse_family_level_term_recovery_score",
            "best_exact_run_id",
            "best_exact_artifact_id",
            "best_exact_phase",
            "best_exact_cycle_index",
            "best_exact_cycle_key",
            "best_exact_expression",
            "best_exact_test_rmse",
            "best_exact_test_r2",
            "best_exact_term_recovery_score",
            "best_phase_equivalent_term_recovery_score",
            "best_family_level_term_recovery_score",
            "best_balanced_run_id",
            "best_balanced_artifact_id",
            "best_balanced_phase",
            "best_balanced_cycle_index",
            "best_balanced_cycle_key",
            "best_balanced_expression",
            "best_balanced_score",
            "best_balanced_test_rmse",
            "best_balanced_test_r2",
            "best_balanced_exact_term_recovery_score",
            "best_balanced_phase_equivalent_term_recovery_score",
            "best_balanced_family_level_term_recovery_score",
            "best_outer_objective_score",
            "best_inner_fit_score",
            "search_driver",
            "screening_protocol",
            "outer_search_protocol",
            "consensus_prior_row_count",
            "joint_core_score",
            "core_basis_count",
            "locked_seed_terms",
            "global_core_basis_count",
            "global_locked_seed_terms",
            "core_equivalence_mode",
            "consensus_cycles",
            "unlocked_runs_per_cycle",
            "locked_runs_per_cycle",
            "total_cycle_rows",
            "total_stage_rows",
            "total_inner_runs",
            "leaderboards",
            "summary_path",
            "orchestration_summary_path",
            "cycle_reports_path",
            "stage_reports_path",
            "core_basis_evolution_path",
            "comparison_path",
            "core_selection_path",
            "orchestration_report",
            "cycle_reports",
            "stage_reports",
            "core_basis_evolution",
            "payload",
        ):
            if key in inner_result:
                out[key] = inner_result[key]
        for key, value in inner_result.items():
            if isinstance(key, str) and key.startswith(("best_rmse_", "best_exact_", "best_balanced_")):
                out[key] = value

        metrics = dict(out.get("metrics") or {})
        metrics.update(dict(inner_result.get("metrics") or {}))
        out["metrics"] = metrics

        artifacts = dict(out.get("artifacts") or {})
        artifacts.update(dict(inner_result.get("artifacts") or {}))
        out["artifacts"] = artifacts
        return out
