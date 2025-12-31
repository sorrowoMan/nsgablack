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
    AdaptiveSurrogateStrategy,
    MultiSurrogateStrategy
)
from .evaluators import SurrogateEvaluator

__all__ = [
    'BaseSurrogateModel',
    'SurrogateManager',
    'FeatureExtractor',
    'SurrogateStrategy',
    'AdaptiveSurrogateStrategy',
    'MultiSurrogateStrategy',
    'SurrogateEvaluator'
]