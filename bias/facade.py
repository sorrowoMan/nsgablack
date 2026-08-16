"""Convenience re-exports for bias facade.

Provides the commonly-expected import path ``nsgablack.bias.facade``.
"""

from .bias_module import BiasModule, create_bias_module, from_universal_manager, proximity_reward, improvement_reward

# Alias: BiasFacade is the historical name for BiasModule
BiasFacade = BiasModule

__all__ = [
    "BiasFacade",
    "BiasModule",
    "create_bias_module",
    "from_universal_manager",
    "proximity_reward",
    "improvement_reward",
]
