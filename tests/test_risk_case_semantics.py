from pathlib import Path
import numpy as np
import pytest
from blackbase.project import build_case, load_case_builder, run_case
from nsgablack.bias import RiskBias
from nsgablack.plugins.evaluation.monte_carlo_evaluation import MonteCarloEvaluationProviderPlugin, MonteCarloEvaluationConfig


@pytest.mark.parametrize("name,mode,has_bias", [("risk_bias", "mean", True), ("robust_dfo", "cvar", False)])
def test_risk_cases_assemble_the_feature_they_advertise(name, mode, has_bias):
    root = Path(__file__).resolve().parents[1] / "examples/cases" / name
    solver = build_case(load_case_builder(root, name), resource_context={"threads": 1})
    plugins = solver.plugin_manager.list_plugins(enabled_only=False)
    mc = next(p for p in plugins if isinstance(p, MonteCarloEvaluationProviderPlugin))
    assert mc.cfg.reduce == mode
    risk = None if solver.bias_module is None else solver.bias_module.get_bias("risk_bias")
    assert isinstance(risk, RiskBias) is has_bias
    solver.set_max_steps(1)
    assert run_case(solver) is not None
    assert solver.evaluation_count > 0


def test_minimization_cvar_uses_worst_loss_tail():
    provider = MonteCarloEvaluationProviderPlugin(config=MonteCarloEvaluationConfig(reduce="cvar", cvar_alpha=0.5))
    np.testing.assert_allclose(provider._reduce(np.array([[1.0], [2.0], [8.0], [10.0]])), [9.0])
