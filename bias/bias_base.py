"""
偏置基类 - 向后兼容层
DEPRECATED: 此文件仅为向后兼容保留，新代码请使用:
from nsgablack.bias.core.base import BiasBase, AlgorithmicBias, DomainBias, OptimizationContext

此文件重新导出核心基类以确保现有代码不会中断。
"""

# 重新导出核心基类以保持向后兼容
from .core.base import (
    BiasBase as BaseBias,  # 为了向后兼容，保留BaseBias名称
    AlgorithmicBias,
    DomainBias,
    OptimizationContext
)

# 为了向后兼容，保留旧的BaseBias名称
# 新代码应使用BiasBase，但现有代码可能仍在使用BaseBias
__all__ = ['BaseBias', 'AlgorithmicBias', 'DomainBias', 'OptimizationContext']