"""Example registry helpers for catalog entries."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def _path(name: str) -> str:
    return str(EXAMPLES / name)


def template_continuous_constrained() -> str:
    return _path("template_continuous_constrained.py")


def template_knapsack_binary() -> str:
    return _path("template_knapsack_binary.py")


def template_tsp_permutation() -> str:
    return _path("template_tsp_permutation.py")


def template_multiobjective_pareto() -> str:
    return _path("template_multiobjective_pareto.py")


def template_assignment_matrix() -> str:
    return _path("template_assignment_matrix.py")


def template_graph_path() -> str:
    return _path("template_graph_path.py")


def template_production_schedule_simple() -> str:
    return _path("template_production_schedule_simple.py")


def template_portfolio_pareto() -> str:
    return _path("template_portfolio_pareto.py")


def dynamic_multi_strategy_demo() -> str:
    return _path("dynamic_multi_strategy_demo.py")


def trust_region_dfo_demo() -> str:
    return _path("trust_region_dfo_demo.py")


def trust_region_subspace_demo() -> str:
    return _path("trust_region_subspace_demo.py")


def monte_carlo_dp_robust_demo() -> str:
    return _path("monte_carlo_dp_robust_demo.py")


def surrogate_plugin_demo() -> str:
    return _path("surrogate_plugin_demo.py")


def multi_fidelity_demo() -> str:
    return _path("multi_fidelity_demo.py")


def risk_bias_demo() -> str:
    return _path("risk_bias_demo.py")


def bias_gallery_demo() -> str:
    return _path("bias_gallery_demo.py")


def plugin_gallery_demo() -> str:
    return _path("plugin_gallery_demo.py")


def role_adapters_demo() -> str:
    return _path("role_adapters_demo.py")


def astar_demo() -> str:
    return _path("astar_demo.py")


def moa_star_demo() -> str:
    return _path("moa_star_demo.py")


def parallel_repair_demo() -> str:
    return _path("parallel_repair_demo.py")


def nsga2_solver_demo() -> str:
    return _path("nsga2_solver_demo.py")


def parallel_evaluator_demo() -> str:
    return _path("parallel_evaluator_demo.py")


def context_keys_demo() -> str:
    return _path("context_keys_demo.py")


def context_schema_demo() -> str:
    return _path("context_schema_demo.py")


def logging_demo() -> str:
    return _path("logging_demo.py")


def metrics_demo() -> str:
    return _path("metrics_demo.py")


def dynamic_cli_signal_demo() -> str:
    return _path("dynamic_cli_signal_demo.py")


def async_event_driven_demo() -> str:
    return _path("async_event_driven_demo.py")


def single_trajectory_adaptive_demo() -> str:
    return _path("single_trajectory_adaptive_demo.py")
