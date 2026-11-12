"""软偏好单独定义；不修改原始目标、约束或候选。"""
import numpy as np

from nsgablack.bias import BiasModule, DomainBias


class NegativeHalfPlaneBias(DomainBias):
    objective_independent = True
    context_notes = "Penalizes negative x0 in the selection view; no context I/O."

    def __init__(self, weight=0.1):
        super().__init__(
            name="prefer_nonnegative_x0",
            weight=weight,
            mandatory=False,
            description="x0 < 0 时增加软惩罚；x0 >= 0 不加分、不扣分。",
        )

    def compute(self, x, context):
        return max(0.0, -float(np.asarray(x)[0]))


def build_bias():
    module = BiasModule()
    module.add(NegativeHalfPlaneBias(weight=0.1))
    return module
