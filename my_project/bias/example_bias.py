# -*- coding: utf-8 -*-
"""Example bias assembly."""

from __future__ import annotations

from nsgablack.bias import BiasModule


def build_bias_module(enable_bias: bool = False) -> BiasModule:
    module = BiasModule()
    if enable_bias:
        # Add domain/algorithmic bias here when needed.
        # Keep default empty so project is runnable from day one.
        pass
    module.context_requires = ()
    module.context_provides = ()
    module.context_mutates = ()
    module.context_cache = ()
    module.context_notes = "No default bias I/O in starter template."
    return module
