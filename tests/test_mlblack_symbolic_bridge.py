from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def _mlblack_root() -> Path:
    return Path(__file__).resolve().parents[2] / "mlblack"


def _small_backend_config(tmp_path: Path):
    from mlblack.integrations.nsgablack_symbolic_backend import (
        MlblackSymbolicConsensusBackendConfig,
    )

    return MlblackSymbolicConsensusBackendConfig(
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
        core_max_terms=3,
        orth_candidate_limit=20,
        save_report=False,
    )


def test_mlblack_symbolic_bridge_smoke(tmp_path):
    from nsgablack.plugins.domain_backends.backend_contract import BackendSolveRequest
    from mlblack.integrations.nsgablack_symbolic_backend import (
        MlblackSymbolicConsensusBackend,
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
            "consensus_cycles": 2,
            "unlocked_runs_per_cycle": 1,
            "locked_runs_per_cycle": 1,
        },
    )

    result = dict(backend.solve(request))

    assert result["status"] == "ok"
    assert result["protocol"] == "nsgablack_mlblack_symbolic_bridge_v3"
    assert result["benchmark_key"] == "ohm_like"
    assert float(result["best_test_rmse"]) >= 0.0
    assert float(result["best_exact_term_recovery_score"]) >= 0.0
    assert int(result["total_inner_runs"]) == 4
    assert int(result["consensus_cycles"]) == 2
    assert len(list(result["cycle_reports"])) == 2
    assert len(list(result["stage_reports"])) == 4
    assert {
        str(row["stage"])
        for row in result["stage_reports"]
    } == {"orthogonal_basis", "basis_conditioned_task"}
    assert all(int(row["unlocked_run_count"]) == 1 for row in result["cycle_reports"])
    assert all(int(row["locked_run_count"]) == 1 for row in result["cycle_reports"])
    assert all(dict(row["unlocked_best_run"]).get("metrics") for row in result["cycle_reports"])
    assert all(dict(row["locked_best_run"]).get("metrics") for row in result["cycle_reports"])

    for key in ("summary_path", "comparison_path", "core_selection_path"):
        assert Path(str(result[key])).is_file()
    summary = json.loads(Path(str(result["summary_path"])).read_text(encoding="utf-8"))
    assert summary["protocol"] == result["protocol"]
    assert len(summary["cycle_reports"]) == 2
    assert len(summary["stage_reports"]) == 4
    assert summary["basis_artifact"]["artifact_id"] == result["payload"]["basis_artifact_id"]
    assert summary["task_artifact"]["artifact_id"] == result["payload"]["task_artifact_id"]
    assert set(result["artifact_refs"]) == {"summary", "comparison", "core_selection"}
    assert len(result["objectives"]) == 4
    assert "truth_contract_recovery" in result["payload"]


def test_mlblack_symbolic_consensus_inner_runtime_provider_smoke(tmp_path):
    from nsgablack.adapters import AlgorithmAdapter
    from nsgablack.core.base import BlackBoxProblem
    from nsgablack.core.composable_solver import ComposableSolver
    from nsgablack.core.nested_solver import InnerRuntimeConfig, TaskInnerRuntimeEvaluator
    from nsgablack.plugins import EvaluationModelConfig, EvaluationModelProviderPlugin
    from mlblack.integrations.nsgablack_symbolic_backend import (
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

        def evaluate(self, candidate):
            _ = candidate
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

        def propose(self, control, context):
            _ = (control, context)
            return [np.array([0.0], dtype=float)]

        def update(self, control, candidates, feedback, context):
            _ = (control, candidates, feedback, context)

    control = ComposableSolver(problem=_Problem(), adapter=_Adapter())
    control.set_max_steps(1)
    control.set_solver_hyperparams(pop_size=1)
    control.register_evaluation_provider(
        EvaluationModelProviderPlugin(
            config=EvaluationModelConfig(scope="inner", warn_on_failure=False),
            backend_factory=lambda _problem, _ctx: backend,
        ).create_provider()
    )
    control.problem.inner_runtime_evaluator = TaskInnerRuntimeEvaluator(
        config=InnerRuntimeConfig(source_layer="L2", target_layer="L1", fallback_penalty=1e6)
    )

    control.run()

    assert control.best_objective is not None
    assert np.isfinite(float(control.best_objective))
    assert isinstance(control.problem.last_inner_result, dict)
    assert control.problem.last_inner_result["benchmark_key"] == "ohm_like"
    assert len(list(control.problem.last_inner_result["cycle_reports"])) == 2
    assert Path(str(control.problem.last_inner_result["summary_path"])).exists()


def test_mlblack_symbolic_bridge_arrhenius_contract(tmp_path):
    from nsgablack.plugins.domain_backends.backend_contract import BackendSolveRequest
    from mlblack.integrations.nsgablack_symbolic_backend import (
        MlblackSymbolicConsensusBackend,
    )

    if not _mlblack_root().exists():
        raise AssertionError(f"mlblack repo not found: {_mlblack_root()}")

    backend = MlblackSymbolicConsensusBackend(config=_small_backend_config(tmp_path))
    backend._ensure_mlblack_imports()
    build_data = backend._ml["build_symbolic_benchmark_data"]
    data = build_data(
        "arrhenius_gate_like",
        n_total=32,
        train_ratio=0.75,
        noise_std=0.01,
        seed=7,
    )

    assert tuple(data.effective_feature_names) == (
        "temperature",
        "activation_energy",
        "catalyst_bias",
    )
    assert tuple(data.metadata["truth_contracts"]) == (
        "activation_energy/temperature",
        "catalyst_bias",
    )

    request = BackendSolveRequest(
        candidate=np.array([24.0, 6.0, 4.0, 2.0], dtype=float),
        eval_context={"scope": "inner", "generation": 0, "individual_id": 0},
        inner_problem={
            "benchmark_key": "arrhenius_gate_like",
            "n_total": 32,
            "dataset_seed": 7,
            "consensus_cycles": 1,
            "unlocked_runs_per_cycle": 1,
            "locked_runs_per_cycle": 1,
            "force_recompute": True,
        },
    )
    plan = backend._resolve_plan(request)

    assert plan["benchmark_key"] == "arrhenius_gate_like"
    assert plan["pool_max_terms"] == 24
    assert plan["basis_size"] == 2

    result = dict(backend.solve(request))
    summary = json.loads(Path(str(result["summary_path"])).read_text(encoding="utf-8"))
    stage_metadata = dict(summary["basis_artifact"]["metadata"]["stage_metadata"])

    assert result["status"] == "ok"
    assert result["benchmark_key"] == "arrhenius_gate_like"
    assert result["total_inner_runs"] == 2
    assert tuple(stage_metadata["truth_contracts"]) == (
        "activation_energy/temperature",
        "catalyst_bias",
    )
    assert summary["plan"]["basis_size"] == 2
    assert summary["plan"]["pool_max_terms"] == 24
