from __future__ import annotations

import numpy as np

from nsgablack.core.base import BlackBoxProblem

from evaluation.supply_evaluation_model import SupplyPlanEvaluationModel


class SupplyAdjustmentOuterProblem(BlackBoxProblem):
    """Outer problem: optimize supply scaling factors.

    Inner layer is an evaluation model that simulates production and returns
    metrics/constraints.
    """

    context_requires = ()
    context_provides = ("inner_metrics",)
    context_mutates = ()
    context_cache = ()
    context_notes = (
        "Outer evaluate(x) delegates to inner evaluation model.",
    )

    def __init__(self, inner_model: SupplyPlanEvaluationModel) -> None:
        self.inner_model = inner_model
        days = int(inner_model.cfg.days)
        bounds = {f"x{i}": [0.5, 1.8] for i in range(days)}
        objectives = ["maximize_output", "smooth_supply", "min_total_supply"]
        super().__init__(
            name="SupplyAdjustmentOuterProblem",
            dimension=days,
            bounds=bounds,
            objectives=objectives,
        )

    def evaluate(self, x: np.ndarray) -> np.ndarray:
        scales = np.asarray(x, dtype=float).reshape(self.dimension)
        m = self.inner_model.evaluate_supply(scales)

        smooth_penalty = float(np.mean(np.abs(np.diff(scales)))) if self.dimension > 1 else 0.0
        output_obj = -float(m["total_output"])
        supply_obj = float(m["total_supply_used"]) / max(1.0, float(self.inner_model.total_supply_budget))
        return np.array([output_obj, smooth_penalty, supply_obj], dtype=float)

    def evaluate_constraints(self, x: np.ndarray) -> np.ndarray:
        scales = np.asarray(x, dtype=float).reshape(self.dimension)
        m = self.inner_model.evaluate_supply(scales)
        return np.array(
            [
                float(m["shortage"]),
                float(m["machine_excess"]),
                float(m["budget_violation"]),
            ],
            dtype=float,
        )
