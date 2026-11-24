import numpy as np

from nsgablack.bias import BiasModule, DomainBias


class BalancedMixBias(DomainBias):
    """偏好原料比例较均衡；只改变选择评分，不改变 Problem 原始成本。"""
    objective_independent = True
    context_notes = "Soft imbalance penalty in the selection view; no context I/O."

    def __init__(self, weight=0.15):
        super().__init__(name="balanced_mix", weight=weight, mandatory=False)

    def compute(self, x, context):
        values = np.asarray(x, dtype=float)
        return float((values[0] - values[1]) ** 2)


def build_bias(weight):
    result = BiasModule()
    result.add(BalancedMixBias(weight))
    return result
