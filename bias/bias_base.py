"""
偏置基类 - Base Classes for Bias System
定义所有偏置类型的抽象基类和公共接口
"""

import numpy as np
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod


class OptimizationContext:
    """优化上下文信息"""

    def __init__(self, generation: int, individual: np.ndarray, population: List[np.ndarray] = None,
                 metrics: Dict[str, float] = None, history: List = None):
        self.generation = generation
        self.individual = individual
        self.population = population or []
        self.metrics = metrics or {}
        self.history = history or []
        self.is_stuck = False
        self.is_violating_constraints = False


class BaseBias(ABC):
    """偏置基类"""

    def __init__(self, name: str, weight: float = 1.0):
        self.name = name
        self.weight = weight
        self.enabled = True

    @abstractmethod
    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """计算偏置值"""
        pass

    def enable(self):
        """启用偏置"""
        self.enabled = True

    def disable(self):
        """禁用偏置"""
        self.enabled = False

    def set_weight(self, weight: float):
        """设置权重"""
        self.weight = max(0.0, weight)


class AlgorithmicBias(BaseBias):
    """算法偏置基类"""

    def __init__(self, name: str, weight: float = 1.0):
        super().__init__(name, weight)
        self.bias_type = 'algorithmic'


class DomainBias(BaseBias):
    """业务偏置基类"""

    def __init__(self, name: str, weight: float = 1.0):
        super().__init__(name, weight)
        self.bias_type = 'domain'