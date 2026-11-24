"""直属初始化只给候选；问题修复和评估仍由控制面执行。"""
import numpy as np
from nsgablack.adapters import FixedCandidateAdapter


class FixedSeed:
    stateless = True

    def __init__(self, candidate=(0.25, 0.75)):
        value = np.asarray(candidate, dtype=float)
        if value.shape != (2,) or not np.all(np.isfinite(value)):
            raise ValueError("candidate must contain two finite numbers")
        self._candidate = tuple(float(item) for item in value)

    def checkpoint_identity(self):
        return {"name": "catalog_fixed_seed", "version": 1,
                "candidate": list(self._candidate)}

    def initialize(self, problem, context):
        return np.array(self._candidate, dtype=float)


def build_adapter(*, candidate=(0.25, 0.75), use_pipeline_initializer=False):
    initializer = None if use_pipeline_initializer else FixedSeed(candidate)
    return FixedCandidateAdapter(initializer=initializer)
