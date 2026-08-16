# -*- coding: utf-8 -*-
# Example bias assembly.

from __future__ import annotations

from typing import Any

from nsgablack.bias import BiasModule


def build_bias_module(enable_bias: bool | None = None, *, cfg: Any | None = None) -> BiasModule:
    if enable_bias is None:
        enable_bias = bool(getattr(cfg, "enable_bias", False))
    module = BiasModule()
    if bool(enable_bias):
        # Add domain/algorithmic bias here when needed.
        pass
    module.context_requires = ()
    module.context_provides = ()
    module.context_mutates = ()
    module.context_cache = ()
    module.context_notes = "No default bias I/O in starter template."
    return module
