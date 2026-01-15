"""
Surrogate module - 代理模型框架

提供通用的代理模型实现，包括：
- 代理模型基类
- 特征提取器
- 状态管理
- 模型管理
"""

from .base import BaseSurrogateModel
from .manager import SurrogateManager
from .features import FeatureExtractor
from .strategies import (
    SurrogateStrategy,
    AdaptiveStrategy,
    MultiSurrogateStrategy,
    RandomStrategy,
    BayesianStrategy,
    SurrogateStrategyFactory,
)
from .evaluators import SurrogateEvaluator
from .trainer import SurrogateTrainer, TrueEvaluator, ProductionEvaluator

AdaptiveSurrogateStrategy = AdaptiveStrategy

__all__ = [
    'BaseSurrogateModel',
    'SurrogateManager',
    'FeatureExtractor',
    'SurrogateStrategy',
    'AdaptiveSurrogateStrategy',
    'AdaptiveStrategy',
    'MultiSurrogateStrategy',
    'RandomStrategy',
    'BayesianStrategy',
    'SurrogateStrategyFactory',
    'SurrogateEvaluator',
    'SurrogateTrainer',
    'TrueEvaluator',
    'ProductionEvaluator',
]
