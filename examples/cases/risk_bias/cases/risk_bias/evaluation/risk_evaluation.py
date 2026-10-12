from nsgablack.plugins.evaluation.monte_carlo_evaluation import (
    MonteCarloEvaluationProviderPlugin, MonteCarloEvaluationConfig,
)


def attach_scenario_evaluation(solver):
    solver.add_plugin(MonteCarloEvaluationProviderPlugin(config=MonteCarloEvaluationConfig(
        mc_samples=8, reduce="mean", cvar_alpha=0.25, random_seed=7,
    )))
