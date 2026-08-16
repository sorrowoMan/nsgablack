"""Pipeline factory for L0 binary blacklist search."""

from __future__ import annotations

import numpy as np

from nsgablack.representation.base import RepresentationPipeline
from nsgablack.representation.binary import BinaryInitializer, BinaryRepair, BitFlipMutation


def build_l0_binary_pipeline(*, init_prob: float, bitflip_rate: float) -> RepresentationPipeline:
    """Build the L0 binary pipeline used by the blacklist optimizer."""
    return RepresentationPipeline(
        initializer=BinaryInitializer(probability=float(np.clip(init_prob, 0.0, 1.0))),
        mutator=BitFlipMutation(rate=float(np.clip(bitflip_rate, 0.0, 1.0))),
        repair=BinaryRepair(threshold=0.5),
    )
