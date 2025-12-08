"""
偏置模块 v2.0 - 双重架构实现
算法偏置 (Algorithmic Bias) + 业务偏置 (Domain Bias)

这个版本实现了可复用、可组合的偏置系统，将算法层面的优化引导与业务层面的约束和偏好分离。
"""

import numpy as np
from typing import Dict, List, Any, Optional
import json
from pathlib import Path

# 导入基类
from .bias_base import BaseBias, AlgorithmicBias, DomainBias, OptimizationContext

# 导入算法偏置
from .bias_library_algorithmic import (
    DiversityBias, ConvergenceBias, ExplorationBias, PrecisionBias,
    AdaptiveDiversityBias, MemoryGuidedBias, GradientApproximationBias,
    AdaptiveConvergenceBias, PopulationDensityBias, PatternBasedBias, TemperatureControlBias,
    AlgorithmicBiasFactory, create_exploration_focused_bias, create_convergence_focused_bias,
    create_balanced_bias, create_high_precision_bias, create_adaptive_bias,
    ALGORITHMIC_BIAS_LIBRARY
)

# 导入业务偏置
from .bias_library_domain import (
    ConstraintBias, PreferenceBias, ObjectiveBias,
    EngineeringDesignBias, FinancialBias, MLHyperparameterBias, SupplyChainBias,
    SchedulingBias, PortfolioBias, EnergyOptimizationBias, HealthcareBias, RoboticsBias,
    DomainBiasFactory, ConstraintBasedBias,
    DOMAIN_BIAS_LIBRARY,
    create_engineering_bias, create_ml_bias, create_financial_bias, create_supply_chain_bias,
    create_healthcare_bias
)


# ==================== 偏置管理器 ====================

class AlgorithmicBiasManager:
    """算法偏置管理器"""

    def __init__(self):
        self.biases = {}

    def add_bias(self, bias: AlgorithmicBias):
        """添加算法偏置"""
        self.biases[bias.name] = bias

    def remove_bias(self, name: str):
        """移除算法偏置"""
        if name in self.biases:
            del self.biases[name]

    def get_bias(self, name: str) -> Optional[AlgorithmicBias]:
        """获取偏置"""
        return self.biases.get(name)

    def compute_algorithmic_bias(self, x: np.ndarray, context: OptimizationContext) -> float:
        """计算总的算法偏置"""
        total_bias = 0.0
        for bias in self.biases.values():
            if bias.enabled:
                total_bias += bias.compute(x, context)
        return total_bias

    def enable_all(self):
        """启用所有偏置"""
        for bias in self.biases.values():
            bias.enable()

    def disable_all(self):
        """禁用所有偏置"""
        for bias in self.biases.values():
            bias.disable()


class DomainBiasManager:
    """业务偏置管理器"""

    def __init__(self):
        self.biases = {}

    def add_bias(self, bias: DomainBias):
        """添加业务偏置"""
        self.biases[bias.name] = bias

    def remove_bias(self, name: str):
        """移除业务偏置"""
        if name in self.biases:
            del self.biases[name]

    def get_bias(self, name: str) -> Optional[DomainBias]:
        """获取偏置"""
        return self.biases.get(name)

    def compute_domain_bias(self, x: np.ndarray, context: OptimizationContext) -> float:
        """计算总的业务偏置"""
        total_bias = 0.0
        for bias in self.biases.values():
            if bias.enabled:
                total_bias += bias.compute(x, context)
        return total_bias


class UniversalBiasManager:
    """通用偏置管理器：协调算法偏置和业务偏置"""

    def __init__(self, algorithm_config: Dict = None, domain_config: Dict = None):
        self.algorithmic_manager = AlgorithmicBiasManager()
        self.domain_manager = DomainBiasManager()

        # 偏置权重配置
        self.bias_weights = {
            'algorithmic': 0.3,  # 算法偏置权重
            'domain': 0.7       # 业务偏置权重（业务更重要）
        }

        # 初始化算法偏置
        if algorithm_config:
            self._initialize_algorithmic_biases(algorithm_config)
        else:
            # 默认算法偏置
            self._initialize_default_algorithmic_biases()

        # 初始化业务偏置
        if domain_config:
            self._initialize_domain_biases(domain_config)

    def _initialize_default_algorithmic_biases(self):
        """初始化默认算法偏置"""
        self.algorithmic_manager.add_bias(DiversityBias(weight=0.1))
        self.algorithmic_manager.add_bias(ConvergenceBias(weight=0.1))

    def _initialize_algorithmic_biases(self, config):
        """根据配置初始化算法偏置"""
        bias_configs = config.get('biases', [])

        for bias_config in bias_configs:
            bias_type = bias_config['type']
            params = bias_config.get('parameters', {})

            from .bias_library_algorithmic import AlgorithmicBiasFactory
            bias = AlgorithmicBiasFactory.create_bias(bias_type, **params)
            self.algorithmic_manager.add_bias(bias)

    def _initialize_domain_biases(self, config):
        """根据配置初始化业务偏置"""
        bias_configs = config.get('biases', [])

        for bias_config in bias_configs:
            bias_type = bias_config['type']
            params = bias_config.get('parameters', {})

            from .bias_library_domain import DomainBiasFactory
            bias = DomainBiasFactory.create_bias(bias_type, **params)
            self.domain_manager.add_bias(bias)

    def compute_total_bias(self, x: np.ndarray, context: OptimizationContext) -> float:
        """计算总偏置"""

        # 算法层面偏置
        alg_bias = self.algorithmic_manager.compute_algorithmic_bias(x, context)

        # 业务层面偏置
        domain_bias = self.domain_manager.compute_domain_bias(x, context)

        # 加权组合
        total_bias = (self.bias_weights['algorithmic'] * alg_bias +
                     self.bias_weights['domain'] * domain_bias)

        return total_bias

    def adjust_weights(self, optimization_state: Dict[str, Any]):
        """根据优化状态动态调整权重"""

        if optimization_state.get('is_stuck', False):
            # 陷入局部最优，增加算法偏置
            self.bias_weights['algorithmic'] = min(0.7, self.bias_weights['algorithmic'] + 0.1)
            self.bias_weights['domain'] = 1.0 - self.bias_weights['algorithmic']

        elif optimization_state.get('is_violating_constraints', False):
            # 违反约束，增加业务偏置
            self.bias_weights['domain'] = min(0.9, self.bias_weights['domain'] + 0.1)
            self.bias_weights['algorithmic'] = 1.0 - self.bias_weights['domain']

    def set_bias_weights(self, algorithmic_weight: float, domain_weight: float):
        """设置偏置权重"""
        total = algorithmic_weight + domain_weight
        if total > 0:
            self.bias_weights['algorithmic'] = algorithmic_weight / total
            self.bias_weights['domain'] = domain_weight / total

    def get_algorithmic_bias(self, name: str) -> Optional[AlgorithmicBias]:
        """获取算法偏置"""
        return self.algorithmic_manager.get_bias(name)

    def get_domain_bias(self, name: str) -> Optional[DomainBias]:
        """获取业务偏置"""
        return self.domain_manager.get_bias(name)

    def save_config(self, filepath: str):
        """保存配置到文件"""
        config = {
            'bias_weights': self.bias_weights,
            'algorithmic_biases': {},
            'domain_biases': {}
        }

        # 保存算法偏置配置
        for name, bias in self.algorithmic_manager.biases.items():
            config['algorithmic_biases'][name] = {
                'type': bias.__class__.__name__,
                'weight': bias.weight,
                'enabled': bias.enabled
            }

        # 保存业务偏置配置
        for name, bias in self.domain_manager.biases.items():
            config['domain_biases'][name] = {
                'type': bias.__class__.__name__,
                'weight': bias.weight,
                'enabled': bias.enabled
            }

        with open(filepath, 'w') as f:
            json.dump(config, f, indent=2)

    def load_config(self, filepath: str):
        """从文件加载配置"""
        with open(filepath, 'r') as f:
            config = json.load(f)

        self.bias_weights = config.get('bias_weights', self.bias_weights)

        # 这里可以进一步加载具体的偏置配置
        # 但需要根据实际的偏置类型来创建实例


# ==================== 偏置模板系统 ====================

BASIC_ENGINEERING_TEMPLATE = {
    'algorithmic': {
        'type': 'diversity_convergence_mix',
        'parameters': {
            'diversity_weight': 0.15,
            'convergence_weight': 0.1
        }
    },
    'domain': {
        'type': 'engineering_design',
        'parameters': {
            'hard_constraints': ['stress_limits', 'material_properties'],
            'soft_constraints': ['weight_limit', 'cost_limit'],
            'preferences': [
                {'metric': 'reliability', 'direction': 'maximize', 'weight': 2.0},
                {'metric': 'manufacturability', 'direction': 'maximize', 'weight': 1.0}
            ]
        }
    }
}

FINANCIAL_OPTIMIZATION_TEMPLATE = {
    'algorithmic': {
        'type': 'fast_convergence',
        'parameters': {
            'early_gen': 5,
            'late_gen': 30
        }
    },
    'domain': {
        'type': 'financial_optimization',
        'parameters': {
            'hard_constraints': ['budget_limits', 'risk_limits'],
            'preferences': [
                {'metric': 'return', 'direction': 'maximize', 'weight': 3.0},
                {'metric': 'risk', 'direction': 'minimize', 'weight': 2.0}
            ]
        }
    }
}

MACHINE_LEARNING_TEMPLATE = {
    'algorithmic': {
        'type': 'precision_search',
        'parameters': {
            'precision_radius': 0.05
        }
    },
    'domain': {
        'type': 'machine_learning',
        'parameters': {
            'hard_constraints': ['training_time_limit', 'memory_limit'],
            'preferences': [
                {'metric': 'accuracy', 'direction': 'maximize', 'weight': 4.0},
                {'metric': 'model_complexity', 'direction': 'minimize', 'weight': 1.0}
            ]
        }
    }
}


def create_bias_manager_from_template(template_name: str, customizations: Dict = None) -> UniversalBiasManager:
    """从模板创建偏置管理器"""

    templates = {
        'basic_engineering': BASIC_ENGINEERING_TEMPLATE,
        'financial_optimization': FINANCIAL_OPTIMIZATION_TEMPLATE,
        'machine_learning': MACHINE_LEARNING_TEMPLATE
    }

    if template_name not in templates:
        raise ValueError(f"Unknown template: {template_name}")

    config = templates[template_name].copy()

    # 应用自定义配置
    if customizations:
        if 'algorithmic' in customizations:
            config['algorithmic'].update(customizations['algorithmic'])
        if 'domain' in customizations:
            config['domain'].update(customizations['domain'])

    return UniversalBiasManager(
        algorithm_config=config.get('algorithmic'),
        domain_config=config.get('domain')
    )


# ==================== 便捷创建函数 ====================

def create_engineering_bias(constraints: List = None, preferences: List = None,
                           safety_factors: Dict[str, float] = None) -> UniversalBiasManager:
    """快速创建工程设计偏置管理器"""
    manager = UniversalBiasManager()

    # 添加默认的算法偏置
    manager.algorithmic_manager.add_bias(DiversityBias(weight=0.15))
    manager.algorithmic_manager.add_bias(ConvergenceBias(weight=0.1))

    # 创建工程设计偏置
    eng_bias = create_engineering_bias(
        constraints=constraints,
        preferences=preferences,
        safety_factors=safety_factors
    )
    manager.domain_manager.add_bias(eng_bias)

    return manager


def create_ml_bias(accuracy_weight: float = 5.0, time_limit: float = 3600,
                   memory_limit: float = 8.0) -> UniversalBiasManager:
    """快速创建机器学习偏置管理器"""
    manager = UniversalBiasManager()

    # 添加适合ML的算法偏置
    manager.algorithmic_manager.add_bias(PrecisionBias(weight=0.2))
    manager.algorithmic_manager.add_bias(ExplorationBias(weight=0.1))

    # 创建ML偏置
    ml_bias = create_ml_bias(
        accuracy_weight=accuracy_weight,
        time_limit=time_limit,
        memory_limit=memory_limit
    )
    manager.domain_manager.add_bias(ml_bias)

    return manager


def create_financial_bias(max_risk: float = 0.15, max_sector_exposure: float = 0.3,
                         target_return: float = 0.12) -> UniversalBiasManager:
    """快速创建金融优化偏置管理器"""
    manager = UniversalBiasManager()

    # 添加适合金融的算法偏置
    manager.algorithmic_manager.add_bias(ConvergenceBias(weight=0.2, early_gen=5, late_gen=30))

    # 创建金融偏置
    finance_bias = create_financial_bias(
        max_risk=max_risk,
        max_sector_exposure=max_sector_exposure,
        target_return=target_return
    )
    manager.domain_manager.add_bias(finance_bias)

    return manager


# ==================== 便捷函数 ====================

def print_bias_library_info():
    """打印偏置库信息"""
    print("算法偏置库:")
    for name, info in ALGORITHMIC_BIAS_LIBRARY.items():
        print(f"  {name}: {info['description']}")

    print("\n业务偏置库:")
    for name, info in DOMAIN_BIAS_LIBRARY.items():
        print(f"  {name}: {info['description']}")


# ==================== 导出接口 ====================

__all__ = [
    # 核心类
    'UniversalBiasManager',
    'OptimizationContext',

    # 管理器
    'AlgorithmicBiasManager',
    'DomainBiasManager',

    # 工厂
    'AlgorithmicBiasFactory',
    'DomainBiasFactory',

    # 偏置库
    'ALGORITHMIC_BIAS_LIBRARY',
    'DOMAIN_BIAS_LIBRARY',

    # 模板
    'BASIC_ENGINEERING_TEMPLATE',
    'FINANCIAL_OPTIMIZATION_TEMPLATE',
    'MACHINE_LEARNING_TEMPLATE',

    # 便捷函数
    'create_bias_manager_from_template',
    'create_engineering_bias',
    'create_ml_bias',
    'create_financial_bias',
    'print_bias_library_info',

    # 导入的偏置类
    'AlgorithmicBias', 'DomainBias', 'ConstraintBias', 'PreferenceBias',
    'DiversityBias', 'ConvergenceBias', 'ExplorationBias', 'PrecisionBias',
    'EngineeringDesignBias', 'FinancialBias', 'MLHyperparameterBias',
    'SupplyChainBias', 'SchedulingBias', 'PortfolioBias'
]