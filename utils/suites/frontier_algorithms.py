"""
Suites for frontier algorithms (combined wiring).
"""

from __future__ import annotations

from typing import Optional

from ...plugins import (
    BenchmarkHarnessPlugin,
    ModuleReportPlugin,
    ParetoArchivePlugin,
    MonteCarloEvaluationPlugin,
    MonteCarloEvaluationConfig,
    SurrogateEvaluationPlugin,
    SurrogateEvaluationConfig,
    SubspaceBasisPlugin,
    SubspaceBasisConfig,
    MultiFidelityEvaluationPlugin,
    MultiFidelityEvaluationConfig,
)
from ...core.adapters import (
    TrustRegionMODFOAdapter,
    TrustRegionMODFOConfig,
    TrustRegionDFOAdapter,
    TrustRegionSubspaceAdapter,
)
from ...core.adapters import MOEADAdapter
from ...bias import BiasModule, DynamicPenaltyBias, StructurePriorBias, UncertaintyExplorationBias, RiskBias
from ...bias.algorithmic.signal_driven import RobustnessBias


def _require_set_adapter(solver) -> None:
    if not hasattr(solver, "set_adapter"):
        raise ValueError("suite wiring requires solver.set_adapter()")


def _require_set_bias_module(solver) -> None:
    if not hasattr(solver, "set_bias_module"):
        raise ValueError("suite wiring requires solver.set_bias_module()")


def attach_trust_region_mo_dfo(solver) -> None:
    """Attach multi-objective trust-region DFO + Pareto archive + reports."""
    _require_set_adapter(solver)
    solver.set_adapter(TrustRegionMODFOAdapter(TrustRegionMODFOConfig()))
    solver.add_plugin(ParetoArchivePlugin())
    solver.add_plugin(BenchmarkHarnessPlugin())
    solver.add_plugin(ModuleReportPlugin())


def attach_trust_region_subspace_frontier(solver) -> None:
    """Attach subspace trust-region with learned basis + reports."""
    _require_set_adapter(solver)
    solver.set_adapter(TrustRegionSubspaceAdapter())
    solver.add_plugin(SubspaceBasisPlugin(SubspaceBasisConfig(method="pca")))
    solver.add_plugin(BenchmarkHarnessPlugin())
    solver.add_plugin(ModuleReportPlugin())


def attach_active_learning_surrogate(solver) -> None:
    """Attach surrogate evaluation with active-learning style exploration."""
    cfg = SurrogateEvaluationConfig(topk_explore=12, topk_exploit=6, min_true_evals=6)
    solver.add_plugin(SurrogateEvaluationPlugin(config=cfg))
    solver.add_plugin(BenchmarkHarnessPlugin())
    solver.add_plugin(ModuleReportPlugin())


def attach_robust_dfo(solver) -> None:
    """Attach DFO + Monte Carlo evaluation + robustness + dynamic penalty."""
    _require_set_adapter(solver)
    _require_set_bias_module(solver)
    solver.set_adapter(TrustRegionDFOAdapter())
    solver.add_plugin(MonteCarloEvaluationPlugin(MonteCarloEvaluationConfig(mc_samples=12)))
    # Bias module
    bias = BiasModule()
    bias.add(RobustnessBias(weight=0.2))
    bias.add(DynamicPenaltyBias(penalty_func=lambda x, c, ctx: {"penalty": float(ctx.get("constraint_violation", 0.0))}))
    solver.set_bias_module(bias, enable=True)
    solver.add_plugin(BenchmarkHarnessPlugin())
    solver.add_plugin(ModuleReportPlugin())


def attach_surrogate_assisted_ea(solver) -> None:
    """Attach surrogate evaluation to any EA adapter/solver."""
    cfg = SurrogateEvaluationConfig(min_train_samples=24, topk_exploit=8, topk_explore=8)
    solver.add_plugin(SurrogateEvaluationPlugin(config=cfg))
    solver.add_plugin(BenchmarkHarnessPlugin())
    solver.add_plugin(ModuleReportPlugin())


def attach_surrogate_model_lab(solver, *, model_type: str = "rf") -> None:
    """Attach surrogate evaluation with a specific model family (taxonomy demo)."""
    cfg = SurrogateEvaluationConfig(min_train_samples=24, topk_exploit=6, topk_explore=10)
    solver.add_plugin(SurrogateEvaluationPlugin(config=cfg, model_type=str(model_type)))
    solver.add_plugin(BenchmarkHarnessPlugin())
    solver.add_plugin(ModuleReportPlugin())


def attach_structure_prior_mo(solver) -> None:
    """Attach MOEA/D + structure prior bias for multi-objective structural priors."""
    _require_set_adapter(solver)
    _require_set_bias_module(solver)
    solver.set_adapter(MOEADAdapter())
    bias = BiasModule()
    bias.add(StructurePriorBias(pairs=[(0, 1), (2, 3)], weight=0.2))
    bias.add(UncertaintyExplorationBias(weight=0.05))
    solver.set_bias_module(bias, enable=True)
    solver.add_plugin(ParetoArchivePlugin())
    solver.add_plugin(BenchmarkHarnessPlugin())
    solver.add_plugin(ModuleReportPlugin())


def attach_multi_fidelity_eval(solver) -> None:
    """Attach multi-fidelity evaluation plugin + reporting."""
    cfg = MultiFidelityEvaluationConfig(min_high_fidelity=6, topk_exploit=6, topk_explore=6)
    solver.add_plugin(MultiFidelityEvaluationPlugin(config=cfg))
    solver.add_plugin(BenchmarkHarnessPlugin())
    solver.add_plugin(ModuleReportPlugin())


def attach_risk_cvar(solver) -> None:
    """Attach MC evaluation + risk bias (CVaR-like)."""
    _require_set_bias_module(solver)
    solver.add_plugin(MonteCarloEvaluationPlugin(MonteCarloEvaluationConfig(mc_samples=12, reduce="mean")))
    bias = BiasModule()
    bias.add(RiskBias(mode="cvar", alpha=0.2, weight=0.2))
    solver.set_bias_module(bias, enable=True)
    solver.add_plugin(BenchmarkHarnessPlugin())
    solver.add_plugin(ModuleReportPlugin())

