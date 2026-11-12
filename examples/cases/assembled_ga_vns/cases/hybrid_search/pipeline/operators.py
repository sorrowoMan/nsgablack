"""只处理问题可行性；不创建 Unit、不求值、不决定成员去留。"""
from dataclasses import dataclass
from typing import ClassVar

import numpy as np

from blackbase.representation import RepresentationCapabilities
from nsgablack.representation.base import RepresentationComponentContract
from nsgablack.units.contracts import candidate_array


@dataclass(frozen=True)
class BoxRepair(RepresentationComponentContract):
    low: float = -4.0
    high: float = 4.0
    representation_capabilities: ClassVar = RepresentationCapabilities(
        frozenset({"repair"}), repair_idempotent=True,
    )
    context_notes = "Clips each coordinate to the problem bounds; no context writes."

    def repair(self, candidate, context=None):
        return np.clip(candidate_array(candidate), self.low, self.high)

    def validate(self, candidate, context=None):
        # 只读检查；共同修复需要时可复用，不偷偷调用 Problem.evaluate。
        x = candidate_array(candidate)
        return bool(x.shape == (2,) and np.all(np.isfinite(x))
                    and np.all(x >= self.low) and np.all(x <= self.high))
