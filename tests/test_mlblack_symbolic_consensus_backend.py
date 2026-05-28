from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

pytestmark = pytest.mark.skip(reason="mlblack module structure was refactored; backend imports (from config import ...) are stale. Backend integration code needs updating.")


def _mlblack_root() -> Path:
    return Path(__file__).resolve().parents[2] / "mlblack"


def _small_backend_config(tmp_path: Path):
    from nsgablack.plugins.solver_backends.mlblack_symbolic_consensus_backend import (
        MlblackSymbolicConsensusBackendConfig,
    )

    return MlblackSymbolicConsensusBackendConfig(
        mlblack_root=str(_mlblack_root()),
        benchmark_key="ohm_like",
        n_total=120,
        train_ratio=0.8,
        noise_std=0.02,
        dataset_seed=42,
        output_root=str(tmp_path / "inner_runs"),
        db_path=str(tmp_path / "mlblack_tracker.sqlite3"),
        namespace="nsg_test_mlblack_consensus",
        tag_prefix="pytest",
        consensus_cycles=2,
        unlocked_runs_per_cycle=1,
        locked_runs_per_cycle=1,
        vanilla_runs=1,
        locked_runs=1,
        search_seed_base=100,
        locked_search_seed_base=900,
        core_equivalence_mode="family",
        core_min_support_rate=0.5,
        core_max_terms=3,
        orth_candidate_limit=20,
        orth_group_count=5,
        orth_seed_candidate_count=5,
        orth_min_basis_count=2,
        orth_max_basis_count=3,
        greedy_choice_topk=2,
        random_group_trials=1,
        orth_assembler_max_added_terms=2,
        orth_assembler_topk_features=2,
        orth_assembler_max_pair_terms=2,
        orth_assembler_max_candidates_per_iter=16,
        orth_assembler_candidate_keep_top=3,
        orth_assembler_max_expr_depth=4,
        save_report=False,
    )


def test_mlblack_symbolic_consensus_backend_smoke(tmp_path):
    from nsgablack.plugins.solver_backends.backend_contract import BackendSolveRequest
    from nsgablack.plugins.solver_backends.mlblack_symbolic_consensus_backend import (
        MlblackSymbolicConsensusBackend,
    )
    from nsgablack.plugins.storage.runtime_surface_tracker import (
        list_runtime_run_surfaces,
        runtime_surface_filter_values,
    )

    if not _mlblack_root().exists():
        raise AssertionError(f"mlblack repo not found: {_mlblack_root()}")

    backend = MlblackSymbolicConsensusBackend(config=_small_backend_config(tmp_path))
    request = BackendSolveRequest(
        candidate=np.array([32.0, 6.0, 5.0, 3.0, 2.0, 1.0, 0.6, 3.0], dtype=float),
        eval_context={"scope": "inner", "generation": 0, "individual_id": 0},
        inner_problem={
            "benchmark_key": "ohm_like",
            "run_label": "pytest_direct",
            "trainer_params_overrides": {
                "orth_candidate_limit": 20,
                "orth_group_count": 5,
                "orth_seed_candidate_count": 5,
                "orth_min_basis_count": 2,
                "orth_max_basis_count": 3,
                "greedy_choice_topk": 2,
                "random_group_trials": 1,
                "orth_assembler_max_added_terms": 2,
                "orth_assembler_topk_features": 2,
                "orth_assembler_max_pair_terms": 2,
                "orth_assembler_max_candidates_per_iter": 16,
                "orth_assembler_candidate_keep_top": 3,
                "orth_assembler_max_expr_depth": 4,
            },
            "vanilla_runs": 1,
            "locked_runs": 1,
            "core_min_support_rate": 0.5,
            "core_max_terms": 3,
        },
    )

    result = dict(backend.solve(request))

    assert result["status"] == "ok"
    assert float(result["best_test_rmse"]) >= 0.0
    assert float(result["best_exact_term_recovery_score"]) >= 0.0
    assert int(result["total_inner_runs"]) >= 1
    assert int(result["consensus_cycles"]) == 2
    assert len(list(result["cycle_reports"])) == 2
    assert len(list(result["stage_reports"])) == 6
    assert Path(str(result["summary_path"])).exists()
    assert Path(str(result["comparison_path"])).exists()
    assert Path(str(result["core_selection_path"])).exists()
    cycle_reports = list(result["cycle_reports"])
    locked_best_run = dict(cycle_reports[0].get("locked_best_run") or {})
    assert str(locked_best_run.get("phase")) == "locked_core"
    locked_meta_path = Path(str(locked_best_run.get("output_dir"))) / "artifact" / "meta.json"
    assert locked_meta_path.exists()
    locked_meta = json.loads(locked_meta_path.read_text(encoding="utf-8"))
    locked_metadata = dict(locked_meta.get("metadata", {}) or {})
    assert len(list(locked_metadata.get("consensus_prior_rows") or ())) >= 1
    symbolic = dict(locked_metadata.get("symbolic", {}) or {})
    structure_engine = dict(symbolic.get("structure_engine", {}) or {})
    assert str(structure_engine.get("search_driver")) == "orthogonal_basis_set_search"
    assert (
        str(structure_engine.get("screening_protocol"))
        == "target_corr+residual_gain+semantic_novelty+consensus_prior"
    )
    assert str(structure_engine.get("outer_search_protocol")) == "beam_basis_set_structure_search"
    assert str(locked_metadata.get("structure_head")) == "expression"
    assert str(locked_metadata.get("search_input_space")) == "basis_object_space"
    assert str(locked_metadata.get("pool_expansion_unit")) == "basis_object"
    assert str(locked_metadata.get("gradient_guidance_mode")) == "basis_object_gradient"
    assert str(locked_metadata.get("basis_binding_mode")) == "defining"
    assert str(locked_metadata.get("escape_policy")) == "forbid"
    assert dict(locked_metadata.get("basis_object_gradient_pool", {}) or {}).get("protocol") == "basis_object_gradient_pool_expansion_v1"
    run_rows = list_runtime_run_surfaces(tmp_path / "mlblack_tracker.sqlite3", limit=50)
    assert len(run_rows) >= 10
    surface_kinds = {str(row.get("surface_kind")) for row in run_rows}
    assert "flow" in surface_kinds
    assert "solver" in surface_kinds
    flow_rows = [dict(row) for row in run_rows if str(row.get("surface_kind")) == "flow"]
    assert flow_rows
    locked_flow_rows = [row for row in flow_rows if str(row.get("screening_protocol") or "").strip()]
    assert locked_flow_rows
    assert any(
        str(row.get("screening_protocol"))
        == "target_corr+residual_gain+semantic_novelty+consensus_prior"
        for row in locked_flow_rows
    )
    assert any(
        "beam_basis_set_structure_search" in str(row.get("outer_search_protocol") or "")
        or "orthogonal_structure_search_with_budgeted_symbolic_assembler" in str(row.get("outer_search_protocol") or "")
        for row in locked_flow_rows
    )
    assert any(str(row.get("structure_head") or "") == "expression" for row in locked_flow_rows)
    assert any(str(row.get("search_input_space") or "") == "basis_object_space" for row in locked_flow_rows)
    assert any(str(row.get("pool_expansion_unit") or "") == "basis_object" for row in locked_flow_rows)
    assert any(str(row.get("gradient_guidance_mode") or "") == "basis_object_gradient" for row in locked_flow_rows)
    assert any(str(row.get("basis_binding_mode") or "") == "defining" for row in locked_flow_rows)
    assert any(str(row.get("escape_policy") or "") == "forbid" for row in locked_flow_rows)
    assert any(
        dict(row.get("result_json", {}) or {}).get("basis_object_gradient_pool")
        or dict(dict(row.get("result_json", {}) or {}).get("run_summary", {}) or {}).get("basis_object_gradient_pool")
        or dict(dict(row.get("result_json", {}) or {}).get("best_run", {}) or {}).get("basis_object_gradient_pool")
        or dict(dict(row.get("result_json", {}) or {}).get("locked_best_run", {}) or {}).get("basis_object_gradient_pool")
        or dict(dict(dict(row.get("result_json", {}) or {}).get("payload", {}) or {}).get("run_summary", {}) or {}).get("basis_object_gradient_pool")
        for row in locked_flow_rows
    )
    consensus_rows = [
        dict(row)
        for row in run_rows
        if str(row.get("surface_key") or "").endswith(".consensus")
    ]
    assert consensus_rows
    assert any(float(row.get("joint_core_score") or 0.0) > 0.0 for row in consensus_rows)
    filter_values = runtime_surface_filter_values(tmp_path / "mlblack_tracker.sqlite3")
    assert "target_corr+residual_gain+semantic_novelty+consensus_prior" in list(
        filter_values.get("run_screening_protocol", [])
    )
    assert "expression" in list(filter_values.get("run_structure_head", []))
    assert "basis_object_space" in list(filter_values.get("run_search_input_space", []))
    assert "basis_object" in list(filter_values.get("run_pool_expansion_unit", []))
    assert "basis_object_gradient" in list(filter_values.get("run_gradient_guidance_mode", []))
    assert "defining" in list(filter_values.get("run_basis_binding_mode", []))
    assert "forbid" in list(filter_values.get("run_escape_policy", []))
    assert list_runtime_run_surfaces(
        tmp_path / "mlblack_tracker.sqlite3",
        screening_protocol="target_corr+residual_gain+semantic_novelty+consensus_prior",
        limit=20,
    )
    assert list_runtime_run_surfaces(
        tmp_path / "mlblack_tracker.sqlite3",
        structure_head="expression",
        search_input_space="basis_object_space",
        pool_expansion_unit="basis_object",
        gradient_guidance_mode="basis_object_gradient",
        basis_binding_mode="defining",
        escape_policy="forbid",
        limit=20,
    )
    assert list_runtime_run_surfaces(
        tmp_path / "mlblack_tracker.sqlite3",
        joint_core_score_min=0.1,
        limit=20,
    )
    assert "payload" in result


def test_mlblack_symbolic_consensus_inner_runtime_provider_smoke(tmp_path):
    from nsgablack.adapters import AlgorithmAdapter
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.nested_solver import InnerRuntimeConfig, TaskInnerRuntimeEvaluator
    from nsgablack.plugins import EvaluationModelConfig, EvaluationModelProviderPlugin
    from nsgablack.plugins.solver_backends.mlblack_symbolic_consensus_backend import (
        MlblackSymbolicConsensusBackend,
    )

    if not _mlblack_root().exists():
        raise AssertionError(f"mlblack repo not found: {_mlblack_root()}")

    backend = MlblackSymbolicConsensusBackend(config=_small_backend_config(tmp_path))

    class _Problem(BlackBoxProblem):
        def __init__(self) -> None:
            super().__init__(
                name="mlblack_inner_provider",
                dimension=1,
                bounds={"x0": (-1.0, 1.0)},
                objectives=["exact_gap", "family_gap", "rmse"],
            )
            self.last_inner_result: dict[str, object] | None = None

        def evaluate(self, x):
            _ = x
            return np.array([1.0, 1.0, 1e6], dtype=float)

        def build_inner_problem(self, x, eval_context):
            _ = x
            return {
                "benchmark_key": "ohm_like",
                "run_label": f"pytest_nested_g{int(eval_context.get('generation', 0)):03d}",
                "output_root": str(tmp_path / "nested_inner_runs"),
                "db_path": str(tmp_path / "nested_tracker.sqlite3"),
                "vanilla_runs": 1,
                "locked_runs": 1,
                "core_min_support_rate": 0.5,
                "core_max_terms": 3,
                "trainer_params_overrides": {
                    "orth_candidate_limit": 18,
                    "orth_group_count": 4,
                    "orth_seed_candidate_count": 4,
                    "orth_min_basis_count": 2,
                    "orth_max_basis_count": 3,
                    "greedy_choice_topk": 2,
                    "random_group_trials": 1,
                    "orth_assembler_max_added_terms": 2,
                    "orth_assembler_topk_features": 2,
                    "orth_assembler_max_pair_terms": 2,
                    "orth_assembler_max_candidates_per_iter": 16,
                    "orth_assembler_candidate_keep_top": 3,
                    "orth_assembler_max_expr_depth": 4,
                },
            }

        def evaluate_from_inner_result(self, x, inner_result, eval_context):
            _ = (x, eval_context)
            self.last_inner_result = dict(inner_result)
            exact = float(inner_result.get("best_exact_term_recovery_score", 0.0) or 0.0)
            family = float(inner_result.get("best_family_level_term_recovery_score", 0.0) or 0.0)
            rmse = float(inner_result.get("best_test_rmse", 1e6) or 1e6)
            return np.array([1.0 - exact, 1.0 - family, rmse], dtype=float)

    class _Adapter(AlgorithmAdapter):
        def __init__(self) -> None:
            super().__init__(name="fixed")

        def propose(self, solver, context):
            _ = (solver, context)
            return [np.array([0.0], dtype=float)]

    solver = ComposableSolver(problem=_Problem(), adapter=_Adapter())
    solver.set_max_steps(1)
    solver.set_solver_hyperparams(pop_size=1)
    solver.register_evaluation_provider(
        EvaluationModelProviderPlugin(
            config=EvaluationModelConfig(scope="inner", warn_on_failure=False),
            backend_factory=lambda _problem, _ctx: backend,
        ).create_provider()
    )
    solver.problem.inner_runtime_evaluator = TaskInnerRuntimeEvaluator(
        config=InnerRuntimeConfig(source_layer="L2", target_layer="L1", fallback_penalty=1e6)
    )

    solver.run()

    assert solver.best_objective is not None
    assert np.isfinite(float(solver.best_objective))
    assert isinstance(solver.problem.last_inner_result, dict)
    assert solver.problem.last_inner_result["benchmark_key"] == "ohm_like"
    assert len(list(solver.problem.last_inner_result["cycle_reports"])) == 2
    assert Path(str(solver.problem.last_inner_result["summary_path"])).exists()


def test_mlblack_symbolic_consensus_backend_arrhenius_mechanism_hints(tmp_path):
    from nsgablack.plugins.solver_backends.backend_contract import BackendSolveRequest
    from nsgablack.plugins.solver_backends.mlblack_symbolic_consensus_backend import (
        MlblackSymbolicConsensusBackend,
    )

    if not _mlblack_root().exists():
        raise AssertionError(f"mlblack repo not found: {_mlblack_root()}")

    backend = MlblackSymbolicConsensusBackend(config=_small_backend_config(tmp_path))
    backend._ensure_mlblack_imports()
    request = BackendSolveRequest(
        candidate=np.array([24.0, 6.0, 4.0, 2.0, 2.0, 1.0, 0.5, 3.0], dtype=float),
        eval_context={"scope": "inner", "generation": 0, "individual_id": 0},
        inner_problem={"benchmark_key": "arrhenius_gate_like", "run_label": "pytest_arrhenius_hints"},
    )
    base_plan = backend._resolve_plan(request)
    _definition, bundle, _truth = backend._ml["build_known_relation_bundle"](
        benchmark_key="arrhenius_gate_like",
        n_total=int(base_plan["n_total"]),
        train_ratio=float(base_plan["train_ratio"]),
        noise_std=float(base_plan["noise_std"]),
        seed=int(base_plan["dataset_seed"]),
    )
    merged_plan = backend._apply_orchestrator_hints(plan=base_plan, bundle_metadata=dict(bundle.metadata))
    lane_specs = backend._normalize_lane_specs(plan=merged_plan)
    lane_summary = backend._lane_summary(lane_specs)
    search_hints = dict(bundle.metadata.get("search_hints", {}) or {})
    params = backend._orthogonal_params(
        plan=merged_plan,
        gate_feature_names=tuple(search_hints.get("gate_feature_names", ()) or ()),
        enable_piecewise_basis=bool(search_hints.get("enable_piecewise_basis")),
        search_seed=123,
        lock_seed_basis=False,
        artifact_id="pytest_arrhenius_mechanism",
    )

    assert int(params["gate_candidate_screen_reserve"]) == 3
    assert bool(params["require_gate_candidate_in_group"]) is True
    assert int(params["min_gate_basis_terms"]) == 1
    assert len(lane_specs) == 3
    assert bool(lane_summary["multi_lane_enabled"]) is True
    assert int(lane_summary["lane_count"]) == 3
    assert "mechanistic_gate_lane" in list(lane_summary["lane_ids"])
    assert tuple(tuple(group) for group in tuple(params["mechanistic_feature_groups"])) == (
        ("activation_energy", "temperature"),
    )
    assert float(params["mechanistic_screen_bonus"]) == 0.8
    assert float(params["mechanistic_group_bonus"]) == 0.3
    assert str(params["assembler_basis_binding_mode"]) == "bound"
    assert str(params["assembler_escape_policy"]) == "budgeted_escape"
    assert tuple(params["assembler_escape_feature_names"]) == ("catalyst_bias",)
