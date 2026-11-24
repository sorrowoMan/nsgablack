"""在给定外部条件 target 下搜索响应 y；不是外层 x 的替身。"""
import numpy as np
from nsgablack.core import BlackBoxProblem

class ResponseProblem(BlackBoxProblem):
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()

    def __init__(self, target=.5):
        super().__init__(name="conditional_response", dimension=1,
                         objectives=["min"], bounds=[(-3., 3.)])
        self.set_target(target)

    def set_target(self, target):
        target = float(target)
        if not np.isfinite(target) or not -2. <= target <= 2.:
            raise ValueError("response target must be finite and within [-2, 2]")
        self.target = target

    def evaluate(self, candidate):
        y = float(np.asarray(candidate).reshape(-1)[0])
        return [(y - self.target) ** 2]
