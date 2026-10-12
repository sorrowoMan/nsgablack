# -*- coding: utf-8 -*-
# Example bias assembly.

from __future__ import annotations

from nsgablack.bias import (BiasModule, PopulationDiversityPreference,
                           UnitPreferenceBias, TabuSearchBias)

from .config import BiasConfig


def build_unit_preferences(adapter) -> BiasModule:
    """Bind preferences to this Case's search instance, after Adapter assembly."""
    module = BiasModule()
    module.add(UnitPreferenceBias.from_adapter(
        PopulationDiversityPreference(), adapter, owner_path=("bias_gallery", "search"),
        name="population_novelty", weight=0.1,
    ))
    module.add(TabuSearchBias(weight=0.15))
    return module


def build_bias_module(enable_bias: bool | None = None, *, cfg: BiasConfig | None = None) -> BiasModule:
    if cfg is None:
        cfg = BiasConfig()
    if enable_bias is None:
        enable_bias = bool(cfg.enable_bias)
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
