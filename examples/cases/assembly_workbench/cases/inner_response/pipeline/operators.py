"""确定性条件初始化与向 target 靠近；问题边界仍由统一 repair 处理。"""
import numpy as np
from blackbase.representation import RepresentationCapabilities
from nsgablack.representation.base import RepresentationComponentContract
from nsgablack.context_keys import KEY_VNS_K

class ResponseOperators(RepresentationComponentContract):
    representation_capabilities = RepresentationCapabilities(frozenset({"init", "mutate"}))
    context_requires = (KEY_VNS_K,)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Uses an explicitly bound scalar condition; never writes context."

    def __init__(self, target=.5):
        self.target = float(target)

    def set_target(self, target):
        self.target = float(target)

    def initialize(self, problem, context=None):
        return np.array([self.target + .5])

    def mutate(self, candidate, context=None):
        scale = 1. / (2. + int(context[KEY_VNS_K]))
        return self.target + scale * (np.asarray(candidate, dtype=float) - self.target)
