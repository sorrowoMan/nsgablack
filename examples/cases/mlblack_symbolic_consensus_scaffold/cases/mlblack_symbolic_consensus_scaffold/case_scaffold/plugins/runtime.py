# -*- coding: utf-8 -*-
"""Runtime plugin/provider assembly for the cross-framework scaffold."""

from __future__ import annotations

import argparse
from pathlib import Path

from nsgablack.core.nested_solver import InnerRuntimeConfig, TaskInnerRuntimeEvaluator
from nsgablack.plugins import (
    BridgeRule,
    ContractBridgePlugin,
    EvaluationModelConfig,
    EvaluationModelProviderPlugin,
    RuntimeSurfaceTrackerConfig,
    RuntimeSurfaceTrackerPlugin,
    TimeoutBudgetConfig,
    TimeoutBudgetPlugin,
)
from mlblack.integrations.nsgablack_symbolic_backend import (
    MlblackSymbolicConsensusBackend,
    MlblackSymbolicConsensusBackendConfig,
)
from nsgablack.utils.wiring import attach_default_observability_plugins


def build_backend_config(
    args: argparse.Namespace,
    *,
    run_root: Path,
    inner_root: Path,
    db_path: str,
) -> MlblackSymbolicConsensusBackendConfig:
    return MlblackSymbolicConsensusBackendConfig(
        benchmark_key=str(args.benchmark_key),
        n_total=int(args.n_total),
        train_ratio=float(args.train_ratio),
        noise_std=float(args.noise_std),
        dataset_seed=int(args.seed),
        output_root=str(inner_root),
        db_path=str(db_path),
        namespace=str(args.namespace),
        tag_prefix=str(args.tag_prefix),
        consensus_cycles=max(1, int(args.consensus_cycles)),
        unlocked_runs_per_cycle=max(1, int(args.unlocked_runs_per_cycle)),
        locked_runs_per_cycle=max(0, int(args.locked_runs_per_cycle)),
        vanilla_runs=int(args.vanilla_runs),
        locked_runs=int(args.locked_runs),
        search_seed_base=int(args.search_seed_base),
        locked_search_seed_base=int(args.locked_search_seed_base),
        core_equivalence_mode=str(args.core_equivalence_mode),
        inner_steps=max(1, int(args.inner_fit_steps)),
        inner_population_size=max(2, int(args.inner_fit_population)),
        stage2_inner_steps=max(1, int(args.task_fit_steps)),
        stage2_inner_population_size=max(2, int(args.task_fit_population)),
    )


def build_contract_bridge_plugin() -> ContractBridgePlugin:
    return ContractBridgePlugin(
        rules=[
            BridgeRule("benchmark_key", "mlblack_benchmark_key", target_layer="L1"),
            BridgeRule("best_phase", "mlblack_best_phase", target_layer="L1"),
            BridgeRule("best_test_rmse", "mlblack_best_test_rmse", target_layer="L1"),
            BridgeRule(
                "best_exact_term_recovery_score",
                "mlblack_best_exact_term_recovery_score",
                target_layer="L1",
            ),
            BridgeRule(
                "best_family_level_term_recovery_score",
                "mlblack_best_family_level_term_recovery_score",
                target_layer="L1",
            ),
            BridgeRule("best_outer_objective_score", "mlblack_best_outer_objective_score", target_layer="L1"),
            BridgeRule("locked_seed_terms", "mlblack_locked_seed_terms", target_layer="L1"),
            BridgeRule("core_basis_count", "mlblack_core_basis_count", target_layer="L1"),
            BridgeRule("total_inner_runs", "mlblack_total_inner_runs", target_layer="L1"),
            BridgeRule("summary_path", "mlblack_summary_path", target_layer="L1"),
        ]
    )


def attach_runtime_plugins(
    solver,
    *,
    backend: MlblackSymbolicConsensusBackend,
    backend_config: MlblackSymbolicConsensusBackendConfig,
    args: argparse.Namespace,
    db_path: str,
) -> None:
    solver.add_plugin(
        TimeoutBudgetPlugin(
            config=TimeoutBudgetConfig(
                layer="L2",
                max_calls=max(1, int(args.max_inner_calls)),
                time_budget_ms=float(args.inner_time_budget_ms),
                fail_closed=True,
            )
        )
    )
    solver.add_plugin(build_contract_bridge_plugin())
    solver.register_evaluation_provider(
        EvaluationModelProviderPlugin(
            config=EvaluationModelConfig(scope="inner", warn_on_failure=False),
            backend_factory=lambda _problem, _ctx: backend,
        ).create_provider()
    )
    solver.problem.inner_runtime_evaluator = TaskInnerRuntimeEvaluator(
        config=InnerRuntimeConfig(
            source_layer="L2",
            target_layer="L1",
            fallback_penalty=float(backend_config.fallback_objective),
            per_call_timeout_ms=int(args.inner_time_budget_ms),
            max_retries=0,
        )
    )
    solver.add_plugin(
        RuntimeSurfaceTrackerPlugin(
            config=RuntimeSurfaceTrackerConfig(
                db_path=str(db_path),
                namespace=str(args.namespace),
                tag=f"{args.tag_prefix}:{args.benchmark_key}:outer",
                surface_key="solver:mlblack_symbolic_consensus_scaffold.build_solver",
                surface_label="mlblack symbolic consensus scaffold",
            )
        )
    )


def attach_observability(
    solver,
    *,
    args: argparse.Namespace,
    run_root: Path,
    run_id: str,
) -> None:
    if bool(args.no_logs):
        return
    run_root.mkdir(parents=True, exist_ok=True)
    attach_default_observability_plugins(
        solver,
        output_dir=str(run_root),
        run_id=str(run_id),
        overwrite=True,
        enable_pareto_archive=False,
        enable_benchmark=True,
        benchmark_log_every=1,
        benchmark_flush_every=10,
        enable_module_report=True,
        write_bias_markdown=False,
        enable_profiler=False,
        enable_decision_trace=True,
        decision_trace_flush_every=1,
        enable_sequence_graph=False,
    )
