"""
偏置模块库 - 可复用的算法偏置和业务偏置集合
"""

from .bias_v2 import *
from typing import Dict, Any, Callable
import importlib.util


# ==================== 算法偏置库 ====================

ALGORITHMIC_BIAS_LIBRARY = {
    'diversity_promotion': {
        'class': 'DiversityBias',
        'description': '促进种群多样性，避免早熟收敛',
        'use_case': '多模态问题，需要探索多个解',
        'default_params': {
            'weight': 0.2,
            'metric': 'euclidean'
        }
    },

    'fast_convergence': {
        'class': 'ConvergenceBias',
        'description': '加速收敛到已知好区域',
        'use_case': '时间敏感的优化问题',
        'default_params': {
            'weight': 0.15,
            'early_gen': 5,
            'late_gen': 30
        }
    },

    'precision_search': {
        'class': 'PrecisionBias',
        'description': '在好解周围进行精细搜索',
        'use_case': '需要高精度解的问题',
        'default_params': {
            'weight': 0.1,
            'precision_radius': 0.05
        }
    },

    'balanced_exploration': {
        'class': 'ExplorationBias',
        'description': '平衡探索和利用，防止早熟收敛',
        'use_case': '通用优化问题',
        'default_params': {
            'weight': 0.1,
            'stagnation_threshold': 20
        }
    },

    'late_precision': {
        'class': 'ConvergenceBias',
        'description': '后期精度偏置',
        'use_case': '需要精确最终解的问题',
        'default_params': {
            'weight': 0.2,
            'early_gen': 50,
            'late_gen': 100
        }
    }
}


# ==================== 业务偏置库 ====================

DOMAIN_BIAS_LIBRARY = {
    'engineering_design': {
        'class': 'EngineeringDesignBias',
        'description': '工程设计专用偏置，考虑安全系数、制造约束等',
        'constraints': ['stress_limits', 'material_properties', 'manufacturing_constraints'],
        'preferences': ['minimize_weight', 'maximize_reliability'],
        'default_params': {
            'weight': 1.0
        }
    },

    'financial_optimization': {
        'class': 'FinancialBias',
        'description': '金融优化专用偏置，考虑风险、收益、法规等',
        'constraints': ['risk_limits', 'regulatory_requirements', 'sector_exposure'],
        'preferences': ['maximize_return', 'minimize_risk', 'diversification'],
        'default_params': {
            'weight': 1.5
        }
    },

    'supply_chain': {
        'class': 'SupplyChainBias',
        'description': '供应链优化专用偏置',
        'constraints': ['capacity_limits', 'lead_times', 'inventory_constraints'],
        'preferences': ['minimize_cost', 'maximize_service_level', 'minimize_delivery_time'],
        'default_params': {
            'weight': 1.0
        }
    },

    'machine_learning': {
        'class': 'MLHyperparameterBias',
        'description': '机器学习超参数优化偏置',
        'constraints': ['memory_limits', 'training_time', 'computational_budget'],
        'preferences': ['maximize_accuracy', 'minimize_complexity', 'minimize_overfitting'],
        'default_params': {
            'weight': 1.2
        }
    },

    'scheduling': {
        'class': 'SchedulingBias',
        'description': '调度优化专用偏置',
        'constraints': ['resource_constraints', 'precedence_constraints', 'time_windows'],
        'preferences': ['minimize_makespan', 'minimize_tardiness', 'balance_workload'],
        'default_params': {
            'weight': 1.0
        }
    },

    'portfolio_optimization': {
        'class': 'PortfolioBias',
        'description': '投资组合优化偏置',
        'constraints': ['budget_constraint', 'risk_tolerance', 'sector_limits'],
        'preferences': ['maximize_return', 'minimize_volatility', 'sharpe_ratio'],
        'default_params': {
            'weight': 1.3
        }
    }
}


# ==================== 业务偏置具体实现 ====================

class EngineeringDesignBias(DomainBias):
    """工程设计偏置"""

    def __init__(self, weight: float = 1.0):
        super().__init__("engineering_design", weight)
        self.constraint_bias = ConstraintBias(weight=weight)
        self.preference_bias = PreferenceBias(weight=weight * 0.5)

    def add_safety_constraint(self, safety_function, margin: float = 1.5):
        """添加安全约束"""
        def safety_constraint(x):
            return max(0, safety_function(x) * safety_function(x) - margin)
        self.constraint_bias.add_hard_constraint(safety_constraint)

    def add_manufacturing_constraint(self, manufacturability_function):
        """添加制造约束"""
        self.constraint_bias.add_soft_constraint(manufacturability_function)

    def set_reliability_preference(self, reliability_metric):
        """设置可靠性偏好"""
        self.preference_bias.set_preference(reliability_metric, 'maximize', weight=2.0)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        constraint_bias = self.constraint_bias.compute(x, context)
        preference_bias = self.preference_bias.compute(x, context)
        return constraint_bias + preference_bias


class FinancialBias(DomainBias):
    """金融优化偏置"""

    def __init__(self, weight: float = 1.5):
        super().__init__("financial", weight)
        self.constraint_bias = ConstraintBias(weight=weight)
        self.objective_bias = ObjectiveBias(weight=weight)

    def add_risk_constraint(self, risk_function, max_risk: float):
        """添加风险约束"""
        def risk_constraint(x):
            return max(0, risk_function(x) - max_risk)
        self.constraint_bias.add_hard_constraint(risk_constraint)

    def add_sector_constraint(self, sector_exposure_function, max_exposure: float = 0.3):
        """添加行业敞口约束"""
        def sector_constraint(x):
            return max(0, sector_exposure_function(x) - max_exposure)
        self.constraint_bias.add_hard_constraint(sector_constraint)

    def set_return_target(self, return_function, target_return: float):
        """设置收益目标"""
        self.objective_bias.set_target('return', target_return, 'maximize')

    def set_volatility_preference(self, volatility_metric):
        """设置波动率偏好"""
        self.objective_bias.set_target('volatility', 0.0, 'minimize')  # 目标是最小波动率

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        constraint_bias = self.constraint_bias.compute(x, context)

        # 计算夏普比率偏好
        if 'return' in context.metrics and 'volatility' in context.metrics:
            sharpe = context.metrics['return'] / (context.metrics['volatility'] + 1e-6)
            sharpe_preference = -sharpe * 0.1  # 负值表示奖励高夏普比率
        else:
            sharpe_preference = 0.0

        return constraint_bias + sharpe_preference


class MLHyperparameterBias(DomainBias):
    """机器学习超参数偏置"""

    def __init__(self, weight: float = 1.2):
        super().__init__("ml_hyperparameter", weight)
        self.constraint_bias = ConstraintBias(weight=weight)
        self.preference_bias = PreferenceBias(weight=weight * 0.8)

    def add_time_constraint(self, time_limit: float):
        """添加时间约束"""
        def time_constraint(x):
            # 这里应该有实际的时间预测函数
            return 0.0  # 简化实现
        self.constraint_bias.add_hard_constraint(time_constraint)

    def add_memory_constraint(self, memory_limit: float):
        """添加内存约束"""
        def memory_constraint(x):
            # 这里应该有实际的内存预测函数
            return 0.0  # 简化实现
        self.constraint_bias.add_hard_constraint(memory_constraint)

    def set_accuracy_preference(self, accuracy_metric):
        """设置准确率偏好"""
        self.preference_bias.set_preference(accuracy_metric, 'maximize', weight=5.0)

    def set_complexity_penalty(self, complexity_metric):
        """设置复杂度惩罚"""
        self.preference_bias.set_preference(complexity_metric, 'minimize', weight=2.0)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        constraint_bias = self.constraint_bias.compute(x, context)
        preference_bias = self.preference_bias.compute(x, context)

        # 添加过拟合惩罚
        if 'train_accuracy' in context.metrics and 'val_accuracy' in context.metrics:
            overfitting = context.metrics['train_accuracy'] - context.metrics['val_accuracy']
            overfitting_penalty = max(0, overfitting) * 2.0
        else:
            overfitting_penalty = 0.0

        return constraint_bias + preference_bias + overfitting_penalty


class SupplyChainBias(DomainBias):
    """供应链优化偏置"""

    def __init__(self, weight: float = 1.0):
        super().__init__("supply_chain", weight)
        self.constraint_bias = ConstraintBias(weight=weight)
        self.preference_bias = PreferenceBias(weight=weight * 0.6)

    def add_capacity_constraint(self, capacity_function):
        """添加产能约束"""
        self.constraint_bias.add_hard_constraint(capacity_function)

    def add_inventory_constraint(self, inventory_function):
        """添加库存约束"""
        self.constraint_bias.add_soft_constraint(inventory_function)

    def set_service_level_preference(self, service_level_metric):
        """设置服务水平偏好"""
        self.preference_bias.set_preference(service_level_metric, 'maximize', weight=3.0)

    def set_cost_preference(self, cost_metric):
        """设置成本偏好"""
        self.preference_bias.set_preference(cost_metric, 'minimize', weight=2.0)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        constraint_bias = self.constraint_bias.compute(x, context)
        preference_bias = self.preference_bias.compute(x, context)
        return constraint_bias + preference_bias


class SchedulingBias(DomainBias):
    """调度优化偏置"""

    def __init__(self, weight: float = 1.0):
        super().__init__("scheduling", weight)
        self.constraint_bias = ConstraintBias(weight=weight)
        self.preference_bias = PreferenceBias(weight=weight * 0.5)

    def add_resource_constraint(self, resource_function):
        """添加资源约束"""
        self.constraint_bias.add_hard_constraint(resource_function)

    def add_precedence_constraint(self, precedence_function):
        """添加优先级约束"""
        self.constraint_bias.add_hard_constraint(precedence_function)

    def set_makespan_preference(self, makespan_metric):
        """设置完工时间偏好"""
        self.preference_bias.set_preference(makespan_metric, 'minimize', weight=3.0)

    def set_tardiness_preference(self, tardiness_metric):
        """设置延迟时间偏好"""
        self.preference_bias.set_preference(tardiness_metric, 'minimize', weight=2.0)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        constraint_bias = self.constraint_bias.compute(x, context)
        preference_bias = self.preference_bias.compute(x, context)
        return constraint_bias + preference_bias


class PortfolioBias(DomainBias):
    """投资组合偏置"""

    def __init__(self, weight: float = 1.3):
        super().__init__("portfolio", weight)
        self.constraint_bias = ConstraintBias(weight=weight)
        self.objective_bias = ObjectiveBias(weight=weight)

    def add_budget_constraint(self, budget_limit: float = 1.0):
        """添加预算约束"""
        def budget_constraint(x):
            return max(0, np.sum(x) - budget_limit)
        self.constraint_bias.add_hard_constraint(budget_constraint)

    def add_risk_constraint(self, risk_function, max_risk: float):
        """添加风险约束"""
        def risk_constraint(x):
            return max(0, risk_function(x) - max_risk)
        self.constraint_bias.add_soft_constraint(risk_constraint)

    def set_return_target(self, return_function):
        """设置收益目标"""
        self.objective_bias.set_target('expected_return', 0.15, 'maximize')

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        constraint_bias = self.constraint_bias.compute(x, context)

        # 多样性偏好
        diversification_penalty = 0.0
        if len(x) > 1:
            concentration = np.max(x) / (np.sum(x) + 1e-6)
            if concentration > 0.4:  # 任何单一资产占比超过40%
                diversification_penalty = (concentration - 0.4) * 10.0

        return constraint_bias + diversification_penalty


# ==================== 偏置工厂 ====================

class BiasFactory:
    """偏置工厂：根据配置创建偏置实例"""

    @staticmethod
    def create_algorithmic_bias(bias_type: str, **params) -> AlgorithmicBias:
        """创建算法偏置"""
        if bias_type not in ALGORITHMIC_BIAS_LIBRARY:
            raise ValueError(f"Unknown algorithmic bias type: {bias_type}")

        bias_info = ALGORITHMIC_BIAS_LIBRARY[bias_type]
        class_name = bias_info['class']

        # 合并默认参数和用户参数
        default_params = bias_info['default_params'].copy()
        default_params.update(params)

        # 创建偏置实例
        return globals()[class_name](**default_params)

    @staticmethod
    def create_domain_bias(bias_type: str, **params) -> DomainBias:
        """创建业务偏置"""
        if bias_type not in DOMAIN_BIAS_LIBRARY:
            raise ValueError(f"Unknown domain bias type: {bias_type}")

        bias_info = DOMAIN_BIAS_LIBRARY[bias_type]
        class_name = bias_info['class']

        # 合并默认参数和用户参数
        default_params = bias_info['default_params'].copy()
        default_params.update(params)

        # 创建偏置实例
        return globals()[class_name](**default_params)

    @staticmethod
    def list_available_algorithmic_biases() -> Dict[str, Dict]:
        """列出可用的算法偏置"""
        return ALGORITHMIC_BIAS_LIBRARY

    @staticmethod
    def list_available_domain_biases() -> Dict[str, Dict]:
        """列出可用的业务偏置"""
        return DOMAIN_BIAS_LIBRARY


# ==================== 偏置组合器 ====================

class BiasComposer:
    """偏置组合器：组合多个偏置模块"""

    def __init__(self):
        self.algorithmic_biases = []
        self.domain_biases = []

    def add_algorithmic_bias(self, bias: AlgorithmicBias):
        """添加算法偏置"""
        self.algorithmic_biases.append(bias)

    def add_domain_bias(self, bias: DomainBias):
        """添加业务偏置"""
        self.domain_biases.append(bias)

    def add_algorithmic_bias_from_config(self, bias_type: str, **params):
        """从配置添加算法偏置"""
        bias = BiasFactory.create_algorithmic_bias(bias_type, **params)
        self.add_algorithmic_bias(bias)

    def add_domain_bias_from_config(self, bias_type: str, **params):
        """从配置添加业务偏置"""
        bias = BiasFactory.create_domain_bias(bias_type, **params)
        self.add_domain_bias(bias)

    def compose(self, x: np.ndarray, context: OptimizationContext,
                alg_weight: float = 0.3, domain_weight: float = 0.7) -> float:
        """组合所有偏置"""

        # 组合所有算法偏置
        alg_bias = sum(bias.compute(x, context) for bias in self.algorithmic_biases)

        # 组合所有业务偏置
        domain_bias = sum(bias.compute(x, context) for bias in self.domain_biases)

        # 加权组合
        total_weight = alg_weight + domain_weight
        if total_weight > 0:
            return (alg_weight / total_weight) * alg_bias + (domain_weight / total_weight) * domain_bias
        else:
            return 0.0

    def get_bias_summary(self) -> Dict[str, Any]:
        """获取偏置摘要"""
        return {
            'algorithmic_biases': [
                {'name': bias.name, 'weight': bias.weight, 'enabled': bias.enabled}
                for bias in self.algorithmic_biases
            ],
            'domain_biases': [
                {'name': bias.name, 'weight': bias.weight, 'enabled': bias.enabled}
                for bias in self.domain_biases
            ]
        }


# ==================== 便捷函数 ====================

def quick_engineering_bias(safety_constraints: List = None,
                           manufacturing_constraints: List = None,
                           reliability_weight: float = 2.0) -> UniversalBiasManager:
    """快速创建工程设计偏置"""
    manager = UniversalBiasManager()

    # 添加默认的算法偏置
    manager.algorithmic_manager.add_bias(DiversityBias(weight=0.15))
    manager.algorithmic_manager.add_bias(ConvergenceBias(weight=0.1))

    # 创建工程设计偏置
    eng_bias = EngineeringDesignBias()

    # 添加安全约束
    if safety_constraints:
        for constraint in safety_constraints:
            eng_bias.add_safety_constraint(constraint)

    # 添加制造约束
    if manufacturing_constraints:
        for constraint in manufacturing_constraints:
            eng_bias.add_manufacturing_constraint(constraint)

    # 设置可靠性偏好
    eng_bias.set_reliability_preference('reliability')

    manager.domain_manager.add_bias(eng_bias)
    return manager


def quick_ml_bias(accuracy_weight: float = 5.0,
                 time_limit: float = 3600.0,
                 memory_limit: float = 8.0) -> UniversalBiasManager:
    """快速创建机器学习偏置"""
    manager = UniversalBiasManager()

    # 添加适合ML的算法偏置
    manager.algorithmic_manager.add_bias(PrecisionBias(weight=0.2))
    manager.algorithmic_manager.add_bias(ExplorationBias(weight=0.1))

    # 创建ML偏置
    ml_bias = MLHyperparameterBias()

    # 添加约束
    ml_bias.add_time_constraint(time_limit)
    ml_bias.add_memory_constraint(memory_limit)

    # 设置偏好
    ml_bias.set_accuracy_preference('accuracy')
    ml_bias.set_complexity_penalty('model_size')

    manager.domain_manager.add_bias(ml_bias)
    return manager


def quick_financial_bias(max_risk: float = 0.15,
                        max_sector_exposure: float = 0.3,
                        target_return: float = 0.12) -> UniversalBiasManager:
    """快速创建金融优化偏置"""
    manager = UniversalBiasManager()

    # 添加适合金融的算法偏置
    manager.algorithmic_manager.add_bias(ConvergenceBias(weight=0.2, early_gen=5, late_gen=30))

    # 创建金融偏置
    finance_bias = FinancialBias()

    # 添加约束（这里使用占位函数）
    # 实际使用时需要提供真实的约束函数
    # finance_bias.add_risk_constraint(risk_function, max_risk)
    # finance_bias.add_sector_constraint(sector_function, max_sector_exposure)

    # 设置目标
    finance_bias.set_return_target(lambda x: 0.0)  # 占位函数
    finance_bias.set_volatility_preference('volatility')

    manager.domain_manager.add_bias(finance_bias)
    return manager