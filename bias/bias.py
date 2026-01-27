"""
Compatibility wrapper for BiasModule imports.
"""

from .bias_module import (
    BiasModule,
    create_bias_module,
    from_universal_manager,
    proximity_reward,
    improvement_reward,
)

__all__ = [
    "BiasModule",
    "create_bias_module",
    "from_universal_manager",
    "proximity_reward",
    "improvement_reward",
]
