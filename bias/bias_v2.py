"""
偏置模块 v2.0 - 兼容层实现
此模块提供对新的 core/manager.py 架构的向后兼容支持
推荐直接使用: from nsgablack.bias.core.manager import UniversalBiasManager
"""

import numpy as np
from typing import Dict, List, Any, Optional, Union
import json

# 导入新的核心实现
from .core.manager import (
    UniversalBiasManager as CoreUniversalBiasManager,
    AlgorithmicBiasManager as CoreAlgorithmicBiasManager,
    DomainBiasManager as CoreDomainBiasManager
)
from .core.base import BiasBase, AlgorithmicBias, DomainBias, OptimizationContext

# 为了向后兼容，重新导出常用偏置类
try:
    from .bias_library_algorithmic import (
        DiversityBias, ConvergenceBias, ExplorationBias, PrecisionBias,
        AdaptiveDiversityBias, MemoryGuidedBias, GradientApproximationBias,
        AdaptiveConvergenceBias, PopulationDensityBias, PatternBasedBias, TemperatureControlBias,
        AlgorithmicBiasFactory, create_exploration_focused_bias, create_convergence_focused_bias,
        create_balanced_bias, create_high_precision_bias, create_adaptive_bias,
        ALGORITHMIC_BIAS_LIBRARY
    )
except ImportError:
    # 如果导入失败，创建占位符
    DiversityBias = None
    ConvergenceBias = None
    ExplorationBias = None
    AlgorithmicBiasFactory = None
    ALGORITHMIC_BIAS_LIBRARY = {}

try:
    from .bias_library_domain import (
        ConstraintBias, PreferenceBias, ObjectiveBias,
        EngineeringDesignBias, FinancialBias, MLHyperparameterBias, SupplyChainBias,
        SchedulingBias, PortfolioBias, EnergyOptimizationBias, HealthcareBias, RoboticsBias,
        DomainBiasFactory, ConstraintBasedBias,
        DOMAIN_BIAS_LIBRARY,
        create_engineering_bias, create_ml_bias, create_financial_bias, create_supply_chain_bias,
        create_healthcare_bias
    )
except ImportError:
    # 如果导入失败，创建占位符
    ConstraintBias = None
    PreferenceBias = None
    DomainBiasFactory = None
    DOMAIN_BIAS_LIBRARY = {}


# ==================== 兼容层：偏置管理器 ====================

class AlgorithmicBiasManager(CoreAlgorithmicBiasManager):
    """
    算法偏置管理器 - 兼容层
    继承自核心实现，提供向后兼容的接口
    """
    pass  # 继承所有功能，无需额外实现


class DomainBiasManager(CoreDomainBiasManager):
    """
    业务偏置管理器 - 兼容层
    继承自核心实现，提供向后兼容的接口
    """
    pass  # 继承所有功能，无需额外实现


class UniversalBiasManager(CoreUniversalBiasManager):
    """
    通用偏置管理器 - 兼容层
    继承自核心实现，提供向后兼容的接口

    此类作为新旧架构之间的桥梁，确保现有代码无需修改即可使用新的实现
    """

    def __init__(self, algorithm_config: Dict = None, domain_config: Dict = None):
        """
        兼容性初始化方法

        Args:
            algorithm_config: 算法偏置配置（向后兼容）
            domain_config: 领域偏置配置（向后兼容）
        """
        # 调用父类初始化
        super().__init__()

        # 为了向后兼容，保存权重配置
        self.bias_weights = {
            'algorithmic': 0.3,
            'domain': 0.7
        }

        # 处理旧的配置格式
        if algorithm_config or domain_config:
            self._initialize_from_legacy_config(algorithm_config, domain_config)

    def _initialize_from_legacy_config(self, algorithm_config, domain_config):
        """从旧配置格式初始化偏置"""
        # 初始化算法偏置
        if algorithm_config and DiversityBias and ConvergenceBias:
            if algorithm_config.get('use_defaults', True):
                self.add_algorithmic_bias(DiversityBias(weight=0.1))
                self.add_algorithmic_bias(ConvergenceBias(weight=0.1))

        # 初始化领域偏置
        if domain_config and ConstraintBias:
            if domain_config.get('use_defaults', True):
                self.add_domain_bias(ConstraintBias(weight=0.5))

    def compute_total_bias(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        兼容性方法：计算总偏置值（返回单个浮点数）

        Args:
            x: 被评估的个体
            context: 优化上下文

        Returns:
            总偏置值（加权组合）
        """
        # 使用核心实现计算，但返回兼容的格式
        result = super().compute_total_bias(x, context)

        # 如果核心实现返回字典，转换为浮点数
        if isinstance(result, dict):
            algorithmic_bias = result.get('algorithmic_bias', 0.0)
            domain_bias = result.get('domain_bias', 0.0)
            total_bias = result.get('total_bias', 0.0)

            # 应用权重（向后兼容）
            if total_bias == 0.0:
                total_bias = (self.bias_weights['algorithmic'] * algorithmic_bias +
                            self.bias_weights['domain'] * domain_bias)

            return total_bias
        else:
            return float(result)

    def adjust_weights(self, optimization_state: Dict[str, Any]):
        """根据优化状态动态调整权重（向后兼容方法）"""
        if optimization_state.get('is_stuck', False):
            # 陷入局部最优，增加算法偏置
            self.bias_weights['algorithmic'] = min(0.7, self.bias_weights['algorithmic'] + 0.1)
            self.bias_weights['domain'] = 1.0 - self.bias_weights['algorithmic']
        elif optimization_state.get('is_violating_constraints', False):
            # 违反约束，增加业务偏置
            self.bias_weights['domain'] = min(0.9, self.bias_weights['domain'] + 0.1)
            self.bias_weights['algorithmic'] = 1.0 - self.bias_weights['domain']

    def set_bias_weights(self, algorithmic_weight, domain_weight=None):
        """
        设置偏置权重（向后兼容方法）

        Args:
            algorithmic_weight: 算法偏置权重，可以是字典或浮点数
            domain_weight: 领域偏置权重（如果第一个参数是字典，此参数忽略）
        """
        if isinstance(algorithmic_weight, dict):
            # 字典格式 {'algorithmic': 0.5, 'domain': 0.5}
            weights = algorithmic_weight
            alg_weight = weights.get('algorithmic', 0.5)
            dom_weight = weights.get('domain', 0.5)
        else:
            # 浮点数格式
            alg_weight = algorithmic_weight
            dom_weight = domain_weight if domain_weight is not None else 0.5

        total = alg_weight + dom_weight
        if total > 0:
            self.bias_weights['algorithmic'] = alg_weight / total
            self.bias_weights['domain'] = dom_weight / total

    def get_algorithmic_bias(self, name: str) -> Optional[AlgorithmicBias]:
        """获取算法偏置（向后兼容方法）"""
        return self.algorithmic_manager.get_bias(name)

    def get_domain_bias(self, name: str) -> Optional[DomainBias]:
        """获取业务偏置（向后兼容方法）"""
        return self.domain_manager.get_bias(name)


# ==================== 向后兼容的工厂函数 ====================

def create_universal_bias_manager(
    algorithm_config: Dict = None,
    domain_config: Dict = None
) -> UniversalBiasManager:
    """
    创建通用偏置管理器的工厂函数（向后兼容）

    Args:
        algorithm_config: 算法偏置配置
        domain_config: 领域偏置配置

    Returns:
        UniversalBiasManager实例
    """
    return UniversalBiasManager(algorithm_config, domain_config)


# ==================== 模块级别的便利函数 ====================

def list_available_algorithmic_biases() -> List[str]:
    """列出可用的算法偏置类型"""
    return list(ALGORITHMIC_BIAS_LIBRARY.keys()) if ALGORITHMIC_BIAS_LIBRARY else []


def list_available_domain_biases() -> List[str]:
    """列出可用的领域偏置类型"""
    return list(DOMAIN_BIAS_LIBRARY.keys()) if DOMAIN_BIAS_LIBRARY else []


# ==================== 兼容性导出 ====================

# 确保这些类在新架构中可用
__all__ = [
    # 核心类
    'UniversalBiasManager',
    'AlgorithmicBiasManager',
    'DomainBiasManager',
    'OptimizationContext',

    # 偏置类型
    'AlgorithmicBias',
    'DomainBias',
    'BiasBase',

    # 算法偏置（如果可用）
    'DiversityBias',
    'ConvergenceBias',
    'ExplorationBias',
    'PrecisionBias',
    'AdaptiveDiversityBias',
    'MemoryGuidedBias',
    'GradientApproximationBias',
    'AdaptiveConvergenceBias',
    'PopulationDensityBias',
    'PatternBasedBias',
    'TemperatureControlBias',
    'AlgorithmicBiasFactory',
    'ALGORITHMIC_BIAS_LIBRARY',

    # 领域偏置（如果可用）
    'ConstraintBias',
    'PreferenceBias',
    'ObjectiveBias',
    'EngineeringDesignBias',
    'FinancialBias',
    'MLHyperparameterBias',
    'SupplyChainBias',
    'SchedulingBias',
    'PortfolioBias',
    'EnergyOptimizationBias',
    'HealthcareBias',
    'RoboticsBias',
    'DomainBiasFactory',
    'DOMAIN_BIAS_LIBRARY',

    # 工厂函数
    'create_universal_bias_manager',
    'create_exploration_focused_bias',
    'create_convergence_focused_bias',
    'create_balanced_bias',
    'create_high_precision_bias',
    'create_adaptive_bias',
    'create_engineering_bias',
    'create_ml_bias',
    'create_financial_bias',
    'create_supply_chain_bias',
    'create_healthcare_bias',

    # 便利函数
    'list_available_algorithmic_biases',
    'list_available_domain_biases'
]