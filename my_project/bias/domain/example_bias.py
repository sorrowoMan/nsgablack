# -*- coding: utf-8 -*-
"""Example bias assembly."""

from __future__ import annotations

from nsgablack.bias import BiasModule

from .config import BiasConfig


def build_bias_module(enable_bias: bool | None = None, *, cfg: BiasConfig | None = None) -> BiasModule:
    if cfg is None:
        cfg = BiasConfig()
    if enable_bias is None:
        enable_bias = bool(cfg.enable_bias)
    module = BiasModule()
    if bool(enable_bias):
        # Add domain/algorithmic bias here when needed.
        # Keep default empty so project is runnable from day one.
        pass
    module.context_requires = ()
    module.context_provides = ()
    module.context_mutates = ()
    module.context_cache = ()
    module.context_notes = "No default bias I/O in starter template."
    return module
