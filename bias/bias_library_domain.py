"""
业务偏置库 - Domain Bias Library
专注于特定业务领域的约束、偏好和目标

这个库提供了各个领域的专业偏置实现，体现了业务知识和行业最佳实践。
"""

from .bias_base import DomainBias, BaseBias, OptimizationContext
import numpy as np
from typing import Dict, Any, List, Callable
from abc import ABC, abstractmethod


# ==================== 业务偏置库 ====================

DOMAIN_BIAS_LIBRARY = {
    'engineering_design': {
        'class': 'EngineeringDesignBias',
        'description': '工程设计专用偏置，考虑安全系数、制造约束等',
        'constraints': ['stress_limits', 'material_properties', 'manufacturing_constraints'],
        'preferences': ['minimize_weight', 'maximize_reliability', 'minimize_cost'],
        'typical_applications': ['mechanical_design', 'structural_optimization', 'CAE_simulation'],
        'complexity': 'medium'
    },

    'financial_optimization': {
        'class': 'FinancialBias',
        'description': '金融优化专用偏置，考虑风险、收益、法规等',
        'constraints': ['risk_limits', 'regulatory_requirements', 'sector_exposure'],
        'preferences': ['maximize_return', 'minimize_risk', 'diversification'],
        'typical_applications': ['portfolio_optimization', 'risk_management', 'trading_strategy'],
        'complexity': 'high'
    },

    'supply_chain': {
        'class': 'SupplyChainBias',
        'description': '供应链优化专用偏置',
        'constraints': ['capacity_limits', 'lead_times', 'inventory_constraints'],
        'preferences': ['minimize_cost', 'maximize_service_level', 'minimize_delivery_time'],
        'typical_applications': ['inventory_management', 'logistics_optimization', 'production_planning'],
        'complexity': 'medium'
    },

    'machine_learning': {
        'class': 'MLHyperparameterBias',
        'description': '机器学习超参数优化偏置',
        'constraints': ['memory_limits', 'training_time', 'computational_budget'],
        'preferences': ['maximize_accuracy', 'minimize_complexity', 'minimize_overfitting'],
        'typical_applications': ['hyperparameter_tuning', 'model_selection', 'neural_architecture_search'],
        'complexity': 'high'
    },

    'scheduling': {
        'class': 'SchedulingBias',
        'description': '调度优化专用偏置',
        'constraints': ['resource_constraints', 'precedence_constraints', 'time_windows'],
        'preferences': ['minimize_makespan', 'minimize_tardiness', 'balance_workload'],
        'typical_applications': ['job_shop_scheduling', 'project_management', 'resource_allocation'],
        'complexity': 'high'
    },

    'portfolio_optimization': {
        'class': 'PortfolioBias',
        'description': '投资组合优化偏置',
        'constraints': ['budget_constraint', 'risk_tolerance', 'sector_limits'],
        'preferences': ['sharpe_ratio', 'expected_return', 'downside_protection'],
        'typical_applications': ['asset_allocation', 'risk_parity', 'factor_investing'],
        'complexity': 'medium'
    },

    'energy_optimization': {
        'class': 'EnergyOptimizationBias',
        'description': '能源系统优化偏置',
        'constraints': ['power_balance', 'emission_limits', 'grid_constraints'],
        'preferences': ['minimize_cost', 'maximize_efficiency', 'minimize_emissions'],
        'typical_applications': ['power_systems', 'renewable_energy', 'smart_grid'],
        'complexity': 'high'
    },

    'healthcare_optimization': {
        'class': 'HealthcareBias',
        'description': '医疗保健优化偏置',
        'constraints': ['patient_safety', 'resource_allocation', 'regulatory_compliance'],
        'preferences': ['maximize_outcomes', 'minimize_costs', 'improve_equity'],
        'typical_applications': ['hospital_management', 'treatment_planning', 'drug_discovery'],
        'complexity': 'very_high'
    },

    'robotics_optimization': {
        'class': 'RoboticsBias',
        'description': '机器人系统优化偏置',
        'constraints': ['kinematics_limits', 'dynamics_constraints', 'safety_zones'],
        'preferences': ['minimize_energy', 'maximize_precision', 'improve_stability'],
        'typical_applications': ['path_planning', 'motion_planning', 'control_optimization'],
        'complexity': 'high'
    }
}


# ==================== 具体业务偏置实现 ====================

class ConstraintBias(DomainBias):
    """约束偏置：处理各种约束条件"""

    def __init__(self, weight: float = 1.0):
        super().__init__("constraint", weight)
        self.hard_constraints = []
        self.soft_constraints = []
        self.preferred_constraints = []

    def add_hard_constraint(self, constraint_func):
        """添加硬约束"""
        self.hard_constraints.append(constraint_func)

    def add_soft_constraint(self, constraint_func):
        """添加软约束"""
        self.soft_constraints.append(constraint_func)

    def add_preferred_constraint(self, constraint_func):
        """添加偏好约束"""
        self.preferred_constraints.append(constraint_func)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        total_penalty = 0.0

        # 硬约束：违反则严重惩罚
        for constraint in self.hard_constraints:
            violation = constraint(x)
            if violation > 0:
                total_penalty += violation * 10.0  # 大惩罚

        # 软约束：违反则适度惩罚
        for constraint in self.soft_constraints:
            violation = constraint(x)
            if violation > 0:
                total_penalty += violation * 2.0  # 适度惩罚

        # 偏好约束：满足则奖励
        for constraint in self.preferred_constraints:
            satisfaction = constraint(x)
            if satisfaction > 0:
                total_penalty -= satisfaction * 0.5  # 奖励

        return self.weight * total_penalty


class PreferenceBias(DomainBias):
    """偏好偏置：体现业务偏好"""

    def __init__(self, weight: float = 0.5):
        super().__init__("preference", weight)
        self.preferences = {}

    def set_preference(self, name: str, direction: str, weight: float = 1.0):
        """设置偏好"""
        self.preferences[name] = {'direction': direction, 'weight': weight}

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        if not context.metrics:
            return 0.0

        total_preference = 0.0

        for name, pref in self.preferences.items():
            if name in context.metrics:
                value = context.metrics[name]
                if pref['direction'] == 'minimize':
                    # 值越小越好
                    total_preference += pref['weight'] * (1.0 / (1.0 + value))
                elif pref['direction'] == 'maximize':
                    # 值越大越好
                    total_preference += pref['weight'] * value

        return self.weight * total_preference


class ObjectiveBias(DomainBias):
    """目标偏置：引导向理想目标"""

    def __init__(self, weight: float = 1.0):
        super().__init__("objective", weight)
        self.targets = {}

    def set_target(self, name: str, target_value: float, direction: str = 'minimize'):
        """设置目标值"""
        self.targets[name] = {'target': target_value, 'direction': direction}

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        if not context.metrics:
            return 0.0

        total_bias = 0.0

        for name, target in self.targets.items():
            if name in context.metrics:
                value = context.metrics[name]
                distance = abs(value - target['target'])

                if target['direction'] == 'minimize':
                    # 越小越好，距离越小偏置越大
                    total_bias += target['target'] / (distance + 1e-6)
                elif target['direction'] == 'maximize':
                    # 越大越好，距离越小偏置越大
                    total_bias += value / (distance + 1e-6)

        return self.weight * total_bias


class EngineeringDesignBias(DomainBias):
    """工程设计偏置"""

    def __init__(self, weight: float = 1.0):
        super().__init__("engineering_design", weight)
        self.constraint_bias = ConstraintBias(weight=weight)
        self.preference_bias = PreferenceBias(weight=weight * 0.5)
        self.safety_factors = {}
        self.manufacturability_rules = []

    def add_safety_factor(self, constraint_name: str, factor: float):
        """添加安全系数"""
        self.safety_factors[constraint_name] = factor

    def add_safety_constraint(self, constraint_func: Callable[[np.ndarray], float],
                             constraint_name: str, safety_factor: float = None):
        """添加带安全系数的约束"""
        if safety_factor is None:
            safety_factor = self.safety_factors.get(constraint_name, 1.5)

        def safe_constraint(x):
            base_violation = max(0, constraint_func(x))
            return max(0, base_violation * safety_factor - 1.0)  # 超过安全值才违反

        self.constraint_bias.add_hard_constraint(safe_constraint)

    def add_manufacturability_rule(self, rule_func: Callable[[np.ndarray], float]):
        """添加可制造性规则"""
        self.manufacturability_rules.append(rule_func)
        self.preference_bias.add_preference('manufacturability', 'maximize', weight=1.0)

    def add_tolerance_constraint(self, dimension: int, tolerance: float):
        """添加公差约束"""
        def tolerance_constraint(x):
            if dimension < len(x):
                return max(0, abs(x[dimension] - round(x[dimension], 2)) - tolerance)
            return 0

        self.constraint_bias.add_soft_constraint(tolerance_constraint)

    def add_material_constraint(self, available_materials: List[str],
                             cost_per_kg: Dict[str, float]):
        """添加材料约束"""
        def material_cost(x):
            # 简化的材料成本计算
            volume = np.prod(x)  # 假设x是尺寸参数
            # 默认使用最便宜的材料
            base_cost = volume * cost_per_kg.get('steel', 5.0)
            return base_cost

        self.preference_bias.set_preference('material_cost', 'minimize', weight=2.0)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        # 计算基础约束偏置
        constraint_bias = self.constraint_bias.compute(x, context)

        # 计算偏好偏置
        preference_bias = self.preference_bias.compute(x, context)

        # 添加可制造性评估
        manufacturability_score = self._evaluate_manufacturability(x)

        return constraint_bias + preference_bias + manufacturability_score

    def _evaluate_manufacturability(self, x: np.ndarray) -> float:
        """评估可制造性"""
        score = 0.0
        for rule in self.manufacturability_rules:
            try:
                rule_score = rule(x)
                score += rule_score
            except:
                continue
        return score


class FinancialBias(DomainBias):
    """金融优化偏置"""

    def __init__(self, weight: float = 1.5):
        super().__init__("financial", weight)
        self.constraint_bias = ConstraintBias(weight=weight)
        self.risk_model = None
        self.market_conditions = {}

    def set_risk_model(self, model_func: Callable[[np.ndarray], float]):
        """设置风险模型"""
        self.risk_model = model_func

    def add_risk_constraint(self, risk_limit: float):
        """添加风险约束"""
        def risk_constraint(x):
            if self.risk_model:
                return max(0, self.risk_model(x) - risk_limit)
            return 0

        self.constraint_bias.add_hard_constraint(risk_constraint)

    def add_sector_constraint(self, sector_allocation_func: Callable[[np.ndarray], np.ndarray],
                             max_exposure: float = 0.3):
        """添加行业敞口约束"""
        def sector_constraint(x):
            allocations = sector_allocation_func(x)
            return np.maximum(0, allocations - max_exposure)

        self.constraint_bias.add_hard_constraint(sector_constraint)

    def add_liquidity_constraint(self, liquidity_function: Callable[[np.ndarray], float],
                                min_liquidity: float = 0.05):
        """添加流动性约束"""
        self.constraint_bias.add_soft_constraint(
            lambda x: max(0, min_liquidity - liquidity_function(x))
        )

    def set_return_target(self, target_return: float, minimum_return: float = None):
        """设置收益目标"""
        self.preference_bias.set_preference('expected_return', 'maximize', weight=3.0)
        if minimum_return:
            self.constraint_bias.add_soft_constraint(
                lambda x: max(0, minimum_return - x[0] if len(x) > 0 else 0)
            )

    def add_volatility_preference(self, max_volatility: float = None):
        """设置波动率偏好"""
        if max_volatility:
            self.constraint_bias.add_soft_constraint(
                lambda x: max(0, x[1] - max_volatility) if len(x) > 1 else 0
            )

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        constraint_bias = self.constraint_bias.compute(x, context)
        preference_bias = self.preference_bias.compute(x, context)

        # 计算夏普比率偏好
        sharpe_preference = 0.0
        if 'expected_return' in context.metrics and 'volatility' in context.metrics:
            sharpe = context.metrics['expected_return'] / (context.metrics['volatility'] + 1e-6)
            sharpe_preference = -sharpe * 0.2  # 负值表示奖励高夏普比率

        return constraint_bias + preference_bias + sharpe_preference
        

class MLHyperparameterBias(DomainBias):
    """机器学习超参数偏置"""

    def __init__(self, weight: float = 1.2):
        super().__init__("ml_hyperparameter", weight)
        self.constraint_bias = ConstraintBias(weight=weight)
        self.preference_bias = PreferenceBias(weight=weight * 0.8)
        self.performance_history = []

    def add_time_constraint(self, time_limit: float):
        """添加时间约束"""
        def time_constraint(x):
            # 简化的时间预测
            lr, batch_size, hidden_units, dropout = x
            estimated_time = hidden_units * 100 / batch_size * 0.01
            return max(0, estimated_time - time_limit)

        self.constraint_bias.add_hard_constraint(time_constraint)

    def add_memory_constraint(self, memory_limit: float):
        """添加内存约束"""
        def memory_constraint(x):
            lr, batch_size, hidden_units, dropout = x
            estimated_memory = hidden_units * 4 / 1024  # 简化的内存估算(MB)
            return max(0, estimated_memory - memory_limit)

        self.constraint_bias.add_hard_constraint(memory_constraint)

    def add_flops_constraint(self, max_flops: float):
        """添加计算量约束"""
        def flops_constraint(x):
            lr, batch_size, hidden_units, dropout = x
            # 简化的FLOP计算
            flops = hidden_units * hidden_units * 100
            return max(0, flops - max_flops)

        self.constraint_bias.add_soft_constraint(flops_constraint)

    def add_validation_split_constraint(self, min_val_size: float = 0.2):
        """添加验证集大小约束"""
        self.preference_bias.set_preference('val_size', 'minimize', weight=2.0)

    def set_accuracy_preference(self, accuracy_metric: str = 'accuracy'):
        """设置准确率偏好"""
        self.preference_bias.set_preference(accuracy_metric, 'maximize', weight=5.0)

    def add_complexity_penalty(self, complexity_metric: str = 'model_size'):
        """添加复杂度惩罚"""
        self.preference_bias.set_preference(complexity_metric, 'minimize', weight=2.0)

    def add_overfitting_penalty(self, train_accuracy_metric: str = 'train_accuracy',
                              val_accuracy_metric: str = 'val_accuracy'):
        """添加过拟合惩罚"""
        def overfitting_penalty(x, context):
            if train_accuracy_metric in context.metrics and val_accuracy_metric in context.metrics:
                train_acc = context.metrics[train_accuracy_metric]
                val_acc = context.metrics[val_accuracy_metric]
                overfitting = train_acc - val_acc
                return max(0, overfitting) * 10.0  # 过拟合惩罚
            return 0

        # 将这个逻辑添加到compute方法中
        self.overfitting_penalty_func = overfitting_penalty

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        constraint_bias = self.constraint_bias.compute(x, context)
        preference_bias = self.preference_bias.compute(x, context)

        # 添加过拟合惩罚
        overfitting_penalty = 0.0
        if hasattr(self, 'overfitting_penalty_func'):
            overfitting_penalty = self.overfitting_penalty_func(x, context)

        # 添加正则化偏好
        regularization_bias = self._compute_regularization_bias(x)

        return constraint_bias + preference_bias + overfitting_penalty + regularization_bias

    def _compute_regularization_bias(self, x: np.ndarray) -> float:
        """计算正则化偏好"""
        lr, batch_size, hidden_units, dropout = x

        # L2正则化偏好（避免过大的权重）
        regularization_bias = 0.0
        if hidden_units > 512:
            regularization_bias += (hidden_units - 512) * 0.01

        if dropout > 0.5:
            regularization_bias += (dropout - 0.5) * 2.0

        if lr > 0.1:
            regularization_bias += (lr - 0.1) * 5.0

        return regularization_bias


class SupplyChainBias(DomainBias):
    """供应链优化偏置"""

    def __init__(self, weight: float = 1.0):
        super().__init__("supply_chain", weight)
        self.constraint_bias = ConstraintBias(weight=weight)
        self.preference_bias = PreferenceBias(weight=weight * 0.6)
        self.demand_history = []

    def add_capacity_constraint(self, capacity_function: Callable[[np.ndarray], float]):
        """添加产能约束"""
        self.constraint_bias.add_hard_constraint(capacity_function)

    def add_inventory_constraint(self, inventory_function: Callable[[np.ndarray], float],
                                safety_stock: float = 0.2):
        """添加库存约束"""
        def inventory_constraint(x):
            current_inventory = inventory_function(x)
            target_inventory = safety_stock * np.mean(x)
            return max(0, target_inventory - current_inventory)

        self.constraint_bias.add_soft_constraint(inventory_constraint)

    def add_lead_time_constraint(self, lead_time_function: Callable[[np.ndarray], float],
                                 max_lead_time: float):
        """添加交货时间约束"""
        self.constraint_bias.add_soft_constraint(
            lambda x: max(0, lead_time_function(x) - max_lead_time)
        )

    def set_service_level_preference(self, service_level_metric: str):
        """设置服务水平偏好"""
        self.preference_bias.set_preference(service_level_metric, 'maximize', weight=3.0)

    def set_cost_preference(self, cost_metric: str):
        """设置成本偏好"""
        self.preference_bias.set_preference(cost_metric, 'minimize', weight=2.0)

    def add_demand_forecast_bias(self, demand_forecast: np.ndarray):
        """添加需求预测偏置"""
        self.demand_history.append(demand_forecast)
        if len(self.demand_history) > 100:
            self.demand_history.pop(0)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        constraint_bias = self.constraint_bias.compute(x, context)
        preference_bias = self.preference_bias.compute(x, context)

        # 添加需求匹配偏好
        demand_bias = self._compute_demand_match_bias(x)

        return constraint_bias + preference_bias + demand_bias

    def _compute_demand_match_bias(self, x: np.ndarray) -> float:
        """计算需求匹配偏置"""
        if not self.demand_history:
            return 0.0

        # 简化的需求匹配计算
        recent_demand = self.demand_history[-1]
        production = x  # 简化：假设x是生产计划
        match_error = np.abs(production - recent_demand)
        return -np.exp(-match_error / np.std(recent_demand)) * 0.1  # 负值表示奖励


class SchedulingBias(DomainBias):
    """调度优化偏置"""

    def __init__(self, weight: float = 1.0):
        super().__init__("scheduling", weight)
        self.constraint_bias = ConstraintBias(weight=weight)
        self.preference_bias = PreferenceBias(weight=weight * 0.5)
        self.resource_utilization = {}

    def add_resource_constraint(self, resource_function: Callable[[np.ndarray], np.ndarray]):
        """添加资源约束"""
        def constraint_func(x):
            usage = resource_function(x)
            capacity = self.resource_utilization.get('capacity', 1.0)
            return np.maximum(0, usage - capacity)

        self.constraint_bias.add_hard_constraint(constraint_func)

    def add_precedence_constraint(self, precedence_matrix: np.ndarray):
        """添加优先级约束"""
        def precedence_constraint(x):
            # 简化的优先级检查
            return 0.0  # 实际实现会检查依赖关系

        self.constraint_bias.add_hard_constraint(precedence_constraint)

    def add_time_window_constraint(self, time_windows: List[tuple]):
        """添加时间窗口约束"""
        def window_constraint(x):
            # 简化实现
            return 0.0

        self.constraint_bias.add_hard_constraint(window_constraint)

    def set_makespan_preference(self, makespan_metric: str):
        """设置完工时间偏好"""
        self.preference_bias.set_preference(makespan_metric, 'minimize', weight=3.0)

    def set_tardiness_preference(self, tardiness_metric: str):
        """设置延迟时间偏好"""
        self.preference_bias.set_preference(tardiness_metric, 'minimize', weight=2.0)

    def set_workload_balance_preference(self, balance_metric: str):
        """设置负载均衡偏好"""
        self.preference_bias.set_preference(balance_metric, 'minimize', weight=1.0)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        constraint_bias = self.constraint_bias.compute(x, context)
        preference_bias = self.preference_bias.compute(x, context)

        # 添加资源利用率偏好
        utilization_bias = self._compute_utilization_bias(x)

        return constraint_bias + preference_bias + utilization_bias

    def _compute_utilization_bias(self, x: np.ndarray) -> float:
        """计算资源利用率偏置"""
        # 简化的利用率计算
        target_utilization = 0.8
        current_utilization = 0.5  # 简化实现

        if current_utilization < target_utilization:
            return (target_utilization - current_utilization) * 0.1
        else:
            return -(current_utilization - target_utilization) * 0.05


class PortfolioBias(DomainBias):
    """投资组合优化偏置"""

    def __init__(self, weight: float = 1.3):
        super().__init__("portfolio", weight)
        self.constraint_bias = ConstraintBias(weight=weight)
        self.objective_bias = ObjectiveBias(weight=weight)
        self.correlation_matrix = None
        self.expected_returns = None

    def add_budget_constraint(self, budget_limit: float = 1.0):
        """添加预算约束"""
        def budget_constraint(x):
            return max(0, np.sum(x) - budget_limit)

        self.constraint_bias.add_hard_constraint(budget_constraint)

    def add_risk_constraint(self, risk_function: Callable[[np.ndarray], float],
                             max_risk: float):
        """添加风险约束"""
        def constraint_func(x):
            return max(0, risk_function(x) - max_risk)

        self.constraint_bias.add_soft_constraint(constraint_func)

    def add_sector_limit_constraint(self, sector_limits: Dict[str, float]):
        """添加行业限制约束"""
        def sector_constraint(x):
            # 简化实现：假设x按资产类别排序
            total = np.sum(x)
            for i, (sector, limit) in enumerate(sector_limits.items()):
                if i < len(x):
                    sector_allocation = x[i] / total
                    return max(0, sector_allocation - limit)
            return 0

        self.constraint_bias.add_hard_constraint(sector_constraint)

    def add_correlation_avoidance(self, correlation_matrix: np.ndarray, max_correlation: float = 0.7):
        """添加相关性避免约束"""
        self.correlation_matrix = correlation_matrix

        def correlation_constraint(x):
            if len(x) < 2 or correlation_matrix is None:
                return 0

            # 计算协方差矩阵的近似
            cov_approx = np.outer(x, x)
            if np.sum(cov_approx) == 0:
                return 0

            corr_approx = cov_approx / np.sqrt(np.outer(np.diag(cov_approx), np.diag(cov_approx)))

            # 检查高相关性
            high_corr_count = np.sum(np.abs(corr_approx) > max_correlation) - len(x)
            return max(0, high_corr_count)

        self.constraint_bias.add_soft_constraint(correlation_constraint)

    def set_return_target(self, return_function: Callable[[np.ndarray], float],
                           target_return: float):
        """设置收益目标"""
        self.objective_bias.set_target('expected_return', target_return, 'maximize')

    def set_volatility_preference(self, volatility_function: Callable[[np.ndarray], float]):
        """设置波动率偏好"""
        self.objective_bias.set_target('volatility', 0.0, 'minimize')

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        constraint_bias = self.constraint_bias.compute(x, context)
        object_bias = self.objective_bias.compute(x, context)

        # 多样性偏好
        diversification_penalty = self._calculate_diversification_penalty(x)

        return constraint_bias + object_bias + diversification_penalty

    def _calculate_diversification_penalty(self, x: np.ndarray) -> float:
        """计算多样性惩罚"""
        if len(x) <= 1:
            return 0.0

        # 归一化权重
        weights = x / (np.sum(x) + 1e-6)

        # 集中度指标
        concentration = np.sum(weights ** 2)

        # 任何单一资产占比过高时增加惩罚
        max_concentration = np.max(weights)
        if max_concentration > 0.4:
            return (max_concentration - 0.4) * 10.0

        return 0.0


class EnergyOptimizationBias(DomainBias):
    """能源系统优化偏置"""

    def __init__(self, weight: float = 1.5):
        super().__init__("energy_optimization", weight)
        self.constraint_bias = ConstraintBias(weight=weight)
        self.preference_bias = PreferenceBias(weight=weight * 0.7)

    def add_power_balance_constraint(self, balance_function: Callable[[np.ndarray], float]):
        """添加功率平衡约束"""
        self.constraint_bias.add_hard_constraint(
            lambda x: max(0, abs(balance_function(x)))
        )

    def add_emission_constraint(self, emission_function: Callable[[np.ndarray], float],
                             max_emission: float):
        """添加排放约束"""
        self.constraint_bias.add_hard_constraint(
            lambda x: max(0, emission_function(x) - max_emission)
        )

    def add_grid_capacity_constraint(self, grid_function: Callable[[np.ndarray], float]):
        """添加电网容量约束"""
        self.constraint_bias.add_hard_constraint(
            lambda x: max(0, grid_function(x) - 1.0)
        )

    def set_efficiency_preference(self, efficiency_metric: str):
        """设置效率偏好"""
        self.preference_bias.set_preference(efficiency_metric, 'maximize', weight=3.0)

    def set_cost_preference(self, cost_metric: str):
        """设置成本偏好"""
        self.preference_bias.set_preference(cost_metric, 'minimize', weight=2.0)

    def add_renewable_preference(self, renewable_ratio_metric: str, target_ratio: float = 0.3):
        """添加可再生能源偏好"""
        self.preference_bias.set_preference(renewable_ratio_metric, 'maximize', weight=1.5)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        constraint_bias = self.constraint_bias.compute(x, context)
        preference_bias = self.preference_bias.compute(x, context)

        # 添加可靠性偏好
        reliability_bias = self._compute_reliability_bias(x)

        return constraint_bias + preference_bias + reliability_bias

    def _compute_reliability_bias(self, x: np.ndarray) -> float:
        """计算可靠性偏置"""
        # 简化的可靠性计算
        redundancy = np.sum(x > 0.5) / len(x)  # 假设>0.5表示有冗余
        return redundancy * 0.1


# ==================== 业务偏置工厂 ====================

class DomainBiasFactory:
    """业务偏置工厂"""

    @staticmethod
    def create_bias(bias_type: str, **params) -> DomainBias:
        """创建业务偏置实例"""
        if bias_type not in DOMAIN_BIAS_LIBRARY:
            raise ValueError(f"Unknown domain bias type: {bias_type}")

        bias_info = DOMAIN_BIAS_LIBRARY[bias_type]
        class_name = bias_info['class']

        # 合并默认参数和用户参数
        default_params = bias_info.get('default_params', {}).copy()
        default_params.update(params)

        # 创建偏置实例
        return globals()[class_name](**default_params)

    @staticmethod
    def list_available_biases() -> Dict[str, Dict]:
        """列出所有可用的业务偏置"""
        return DOMAIN_BIAS_LIBRARY

    @staticmethod
    def get_applications(bias_type: str) -> List[str]:
        """获取偏置的典型应用"""
        if bias_type in DOMAIN_BIAS_LIBRARY:
            return DOMAIN_BIAS_LIBRARY[bias_type]['typical_applications']
        return []

    @staticmethod
    def get_complexity(bias_type: str) -> str:
        """获取偏置的复杂度"""
        if bias_type in DOMAIN_BIAS_LIBRARY:
            return DOMAIN_BIAS_LIBRARY[bias_type]['complexity']
        return 'unknown'

    @staticmethod
    def create_bias_suite(domain_config: Dict) -> List[DomainBias]:
        """创建业务偏置套件"""
        biases = []

        # 创建主要偏置
        if 'main_bias' in domain_config:
            bias_config = domain_config['main_bias']
            bias = DomainBiasFactory.create_bias(
                bias_config['type'],
                **bias_config.get('parameters', {})
            )
            biases.append(bias)

        # 添加约束偏置
        if 'constraints' in domain_config:
            constraint_bias = DomainBiasFactory.create_bias('constraint_based', **domain_config['constraints'])
            biases.append(constraint_bias)

        return biases


# ==================== 约束偏置基类 ====================

class ConstraintBasedBias(DomainBias):
    """基于约束的偏置基类"""

    def __init__(self, weight: float = 1.0):
        super().__init__("constraint_based", weight)
        self.constraint_bias = ConstraintBias(weight=weight)

    def add_hard_constraint(self, constraint_func: Callable[[np.ndarray], float]):
        """添加硬约束"""
        self.constraint_bias.add_hard_constraint(constraint_func)

    def add_soft_constraint(self, constraint_func: Callable[[np.ndarray], float]):
        """添加软约束"""
        self.constraint_bias.add_soft_constraint(constraint_func)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        return self.constraint_bias.compute(x, context)


# ==================== 便捷创建函数 ====================

def create_engineering_bias(constraints: List[Callable] = None,
                           preferences: List[Dict] = None,
                           safety_factors: Dict[str, float] = None) -> DomainBias:
    """快速创建工程设计偏置"""
    bias = EngineeringDesignBias()

    if constraints:
        for constraint in constraints or []:
            bias.add_safety_constraint(constraint)

    if preferences:
        for pref in preferences or []:
            bias.preference_bias.set_preference(**pref)

    if safety_factors:
        for name, factor in (safety_factors or {}).items():
            bias.add_safety_factor(name, factor)

    return bias


def create_ml_bias(accuracy_weight: float = 5.0,
                   time_limit: float = 3600,
                   memory_limit: float = 8.0,
                   complexity_weight: float = 2.0) -> DomainBias:
    """快速创建机器学习偏置"""
    bias = MLHyperparameterBias()

    # 添加约束
    bias.add_time_constraint(time_limit)
    bias.add_memory_constraint(memory_limit)

    # 设置偏好
    bias.set_accuracy_preference()
    bias.add_complexity_penalty()

    # 调整权重
    bias.preference_bias.set_preference('accuracy', 'maximize', accuracy_weight)
    bias.preference_bias.set_preference('model_complexity', 'minimize', complexity_weight)

    return bias


def create_financial_bias(max_risk: float = 0.15,
                         max_sector_exposure: float = 0.3,
                         target_return: float = 0.12,
                         sharpe_preference_weight: float = 0.2) -> DomainBias:
    """快速创建金融优化偏置"""
    bias = FinancialBias()

    # 添加约束（简化实现，实际需要具体函数）
    # bias.add_risk_constraint(lambda x: max(0, x[1] - max_risk))
    # bias.add_sector_constraint(lambda x: np.array([0.2, 0.3, 0.1, 0.4]), max_sector_exposure)

    # 设置目标
    bias.set_return_target(target_return)

    return bias


def create_supply_chain_bias(capacity_limit: float = 1.0,
                           safety_stock_ratio: float = 0.2,
                           service_level_weight: float = 3.0) -> DomainBias:
    """快速创建供应链偏置"""
    bias = SupplyChainBias()

    # 约束（简化实现）
    # bias.add_capacity_constraint(lambda x: max(0, x[0] - capacity_limit))
    # bias.add_inventory_constraint(lambda x: max(0, safety_stock_ratio * x[0] - x[1]))

    # 偏好
    bias.set_service_level_preference('service_level')
    bias.preference_bias.set_preference('service_level', 'maximize', service_level_weight)

    return bias


def create_healthcare_bias(patient_safety_weight: float = 10.0,
                           cost_minimize_weight: float = 2.0,
                           equity_weight: float = 1.0) -> DomainBias:
    """快速创建医疗保健偏置"""
    bias = HealthcareBias(patient_safety_weight, cost_minimize_weight, equity_weight)
    return bias


# ==================== 特定领域偏置 ====================

class HealthcareBias(DomainBias):
    """医疗保健偏置"""

    def __init__(self, safety_weight: float = 10.0, cost_weight: float = 2.0, equity_weight: float = 1.0):
        super().__init__("healthcare", safety_weight)
        self.safety_weight = safety_weight
        self.cost_weight = cost_weight
        self.equity_weight = equity_weight
        self.constraint_bias = ConstraintBias(weight=safety_weight)
        self.preference_bias = PreferenceBias(weight=1.0)

        self.preference_bias.set_preference('patient_outcomes', 'maximize', weight=3.0)
        self.preference_bias.set_preference('treatment_cost', 'minimize', weight=cost_weight)
        self.preference_bias.set_preference('health_equity', 'maximize', weight=equity_weight)

    def add_safety_constraint(self, safety_function: Callable[[np.ndarray], float]):
        """添加患者安全约束"""
        self.constraint_bias.add_hard_constraint(safety_function)

    def add_resource_constraint(self, resource_function: Callable[[np.ndarray], float]):
        """添加医疗资源约束"""
        self.constraint_bias.add_hard_constraint(resource_function)

    def add_regulation_constraint(self, regulation_function: Callable[[np.ndarray], float]):
        """添加法规合规约束"""
        self.constraint_bias.add_hard_constraint(regulation_function)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        constraint_bias = self.constraint_bias.compute(x, context)
        preference_bias = self.preference_bias.compute(x, context)
        return constraint_bias + preference_bias


class RoboticsBias(DomainBias):
    """机器人优化偏置"""

    def __init__(self, weight: float = 1.2):
        super().__init__("robotics", weight)
        self.constraint_bias = ConstraintBias(weight=weight)
        self.preference_bias = PreferenceBias(weight=weight * 0.8)

    def add_kinematics_constraint(self, kinematics_function: Callable[[np.ndarray], np.ndarray]):
        """添加运动学约束"""
        def constraint_func(x):
            joint_positions = kinematics_function(x)
            # 简化的关节限制检查
            return np.max(np.abs(joint_positions)) - np.pi  # 限制在±180度

        self.constraint_bias.add_hard_constraint(constraint_func)

    def add_dynamics_constraint(self, dynamics_function: Callable[[np.ndarray], float]):
        """添加动力学约束"""
        self.constraint_bias.add_hard_constraint(dynamics_function)

    def add_safety_zone_constraint(self, safety_function: Callable[[np.ndarray], float]):
        """添加安全区域约束"""
        self.constraint_bias.add_hard_constraint(safety_function)

    def set_energy_preference(self, energy_metric: str):
        """设置能耗偏好"""
        self.preference_bias.set_preference(energy_metric, 'minimize', weight=2.0)

    def set_precision_preference(self, precision_metric: str):
        """设置精度偏好"""
        self.preference_bias.set_preference(precision_metric, 'maximize', weight=1.5)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        constraint_bias = self.constraint_bias.compute(x, context)
        preference_bias = self.preference_bias.compute(x, context)
        return constraint_bias + preference_bias


# ==================== 导出接口 ====================

__all__ = [
    # 业务偏置基类
    'DomainBias',

    # 具体领域偏置
    'EngineeringDesignBias',
    'FinancialBias',
    'MLHyperparameterBias',
    'SupplyChainBias',
    'SchedulingBias',
    'PortfolioBias',
    'EnergyOptimizationBias',
    'HealthcareBias',
    'RoboticsBias',

    # 约束偏置
    'ConstraintBasedBias',

    # 工厂类
    'DomainBiasFactory',

    # 偏置库
    'DOMAIN_BIAS_LIBRARY',

    # 便捷函数
    'create_engineering_bias',
    'create_ml_bias',
    'create_financial_bias',
    'create_supply_chain_bias',
    'create_healthcare_bias'
]