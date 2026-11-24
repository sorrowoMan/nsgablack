import numpy as np
from nsgablack.core import BlackBoxProblem


class RiskCostProblem(BlackBoxProblem):
    """Increasing exposure reduces mean cost but increases scenario variance."""
    def __init__(self):
        super().__init__(name="risk_cost", dimension=2, bounds=[(-2, 2)] * 2,
                         objectives=["scenario_cost"])

    def evaluate(self, x):
        x = np.asarray(x)
        return float(np.sum((x - 1) ** 2) + (0.1 + abs(x[0])) * np.random.normal())
