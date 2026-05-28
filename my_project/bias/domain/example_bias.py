# -*- coding: utf-8 -*-
"""Example bias assembly."""

from __future__ import annotations

from nsgablack.bias import BiasModule
from nsgablack.bias.algorithmic.diversity import DiversityBias

from .config import BiasConfig


def build_bias_module(enable_bias: bool | None = None, *, cfg: BiasConfig | None = None) -> BiasModule:
    if cfg is None:
        cfg = BiasConfig()
    if enable_bias is None:
        enable_bias = bool(cfg.enable_bias)
    module = BiasModule()
    if bool(enable_bias):
        module.add(
            DiversityBias(
                weight=float(cfg.diversity_weight),
                metric=str(cfg.diversity_metric),
            )
        )
    module.context_requires = ()
    module.context_provides = ()
    module.context_mutates = ()
    module.context_cache = ()
    module.context_notes = "Starter template bias surface; optional diversity bias when enable_bias=True."
    return module
