"""
Advanced bias management modules.

This package contains sophisticated bias management systems including
adaptive management, meta-learning, and performance analytics.
"""

try:
    from .adaptive_manager import AdaptiveAlgorithmicManager
except Exception:
    AdaptiveAlgorithmicManager = None

try:
    from .meta_learning_selector import MetaLearningBiasSelector
except Exception:
    MetaLearningBiasSelector = None

try:
    from .analytics import BiasEffectivenessAnalyzer
except Exception:
    BiasEffectivenessAnalyzer = None

__all__ = [
    'AdaptiveAlgorithmicManager',
    'MetaLearningBiasSelector',
    'BiasEffectivenessAnalyzer'
]
