"""
约束偏置实现模块

该模块提供各种约束处理偏置，用于：
- 处理硬约束和软约束
- 可行性检查和惩罚
- 业务规则集成
- 约束违反度计算

约束偏置是领域偏置的核心组成部分，确保优化结果满足实际问题的约束条件。
"""

import numpy as np
from typing import List, Callable, Dict, Any, Optional
from ..core.base import DomainBias, OptimizationContext


class ConstraintBias(DomainBias):
    """
    通用约束偏置 - 处理多种约束类型

    支持硬约束和软约束的统一处理框架：
    - 硬约束：必须满足的约束，违反时给予重惩罚
    - 软约束：尽量满足的约束，违反时给予轻惩罚
    - 支持动态添加和移除约束函数
    - 详细的约束违反统计和分析

    适用于各种带约束的优化问题。
    """
    context_requires = ("generation",)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads context fields: generation; outputs scalar bias only."



    def __init__(self, weight: float = 1.0, penalty_factor: float = 10.0):
        """
        初始化约束偏置

        Args:
            weight: 基础惩罚权重
            penalty_factor: 惩罚因子（硬约束的额外惩罚倍数）
        """
        super().__init__("constraint", weight, mandatory=True)
        self.penalty_factor = penalty_factor                   # 惩罚因子
        self.constraints = []                                # 约束函数列表
        self.constraint_weights = []                          # 约束权重列表
        self.constraint_types = []                            # 约束类型列表
        self.violation_history = []                          # 违反历史记录

    def add_constraint(
        self,
        constraint_func: Callable[[np.ndarray], float],
        weight: float = 1.0,
        constraint_type: str = 'hard'
    ):
        """
        添加约束函数

        Args:
            constraint_func: 约束函数，输入个体，返回违反程度（>= 0）
            weight: 约束权重，控制该约束的重要性
            constraint_type: 约束类型
                           'hard' - 硬约束，必须满足
                           'soft' - 软约束，尽量满足

        Example:
            def max_value_constraint(x):
                return max(0, x[0] - 1.0)  # x[0] <= 1.0

            bias.add_constraint(max_value_constraint, weight=2.0, constraint_type='hard')
        """
        self.constraints.append(constraint_func)
        self.constraint_weights.append(weight)
        self.constraint_types.append(constraint_type)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算约束偏置值

        Args:
            x: 被评估的个体
            context: 优化上下文

        Returns:
            总约束违反惩罚值
        """
        total_violation = 0.0

        for i, (constraint, weight, c_type) in enumerate(
            zip(self.constraints, self.constraint_weights, self.constraint_types)
        ):
            violation = constraint(x)
            if violation > 0:  # 有违反
                if c_type == 'hard':
                    # 硬约束：高惩罚
                    penalty = violation * weight * self.penalty_factor
                else:
                    # 软约束：标准惩罚
                    penalty = violation * weight
                total_violation += penalty

        # 记录违反历史
        if total_violation > 0:
            self.violation_history.append({
                'generation': context.generation,
                'violation': total_violation,
                'constraint_count': len([c for c in self.constraints if c(x) > 0])
            })

        return total_violation * self.weight

    def get_violation_statistics(self) -> Dict[str, Any]:
        """
        获取约束违反统计信息

        Returns:
            包含各种统计指标的字典
        """
        if not self.violation_history:
            return {
                'total_violations': 0,
                'max_violation': 0.0,
                'avg_violation': 0.0,
                'violation_rate': 0.0
            }

        violations = [v['violation'] for v in self.violation_history]
        total_evaluations = self.usage_count + len(self.violation_history)

        return {
            'total_violations': len(self.violation_history),
            'max_violation': max(violations),
            'avg_violation': np.mean(violations),
            'violation_rate': len(self.violation_history) / max(1, total_evaluations)
        }


class FeasibilityBias(DomainBias):
    """
    可行性偏置 - 确保解的可行性

    基于与可行区域的距离计算偏置：
    - 计算个体到可行区域的距离
    - 根据距离大小施加相应惩罚
    - 支持可行性阈值配置
    - 与其他约束偏置协同工作

    适用于需要严格可行性保证的问题。
    """
    context_requires = ("problem_data",)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads context fields: problem_data; outputs scalar bias only."



    def __init__(
        self,
        weight: float = 1.0,
        feasibility_threshold: float = 1e-6,
        penalty_scale: float = 100.0
    ):
        """
        初始化可行性偏置

        Args:
            weight: 偏置权重
            feasibility_threshold: 可行性阈值（小于此值认为可行）
            penalty_scale: 惩罚缩放因子
        """
        super().__init__("feasibility", weight, mandatory=True)
        self.feasibility_threshold = feasibility_threshold    # 可行性阈值
        self.penalty_scale = penalty_scale                  # 惩罚缩放

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算可行性偏置值

        Args:
            x: 被评估的个体
            context: 优化上下文

        Returns:
            可行性偏置值
        """
        # 从上下文获取约束违反信息
        constraint_violations = context.problem_data.get('constraint_violations', [])

        if not constraint_violations:
            return 0.0  # 无约束时自动可行

        total_violation = sum(max(0, v) for v in constraint_violations)

        if total_violation < self.feasibility_threshold:
            return 0.0  # 可行

        # 根据违反程度施加惩罚
        return self.weight * self.penalty_scale * total_violation


class PreferenceBias(DomainBias):
    """
    偏好偏置 - 融入决策者偏好

    支持多种偏好表达方式：
    - 愿望水平（目标期望值）
    - 目标函数偏好
    - 偏好函数集成
    - 区域偏好（满意区间）

    适用于需要考虑决策者偏好的多目标优化问题。
    """
    context_requires = ()
    requires_metrics = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads context fields: metrics; outputs scalar bias only."



    def __init__(
        self,
        weight: float = 0.5,
        aspiration_levels: Optional[Dict[str, float]] = None,
        preference_functions: Optional[List[Callable]] = None
    ):
        """
        初始化偏好偏置

        Args:
            weight: 偏置权重
            aspiration_levels: 愿望水平字典 {目标名: 期望值或区间}
            preference_functions: 偏好函数列表
        """
        super().__init__("preference", weight, mandatory=False)
        self.aspiration_levels = aspiration_levels or {}    # 愿望水平
        self.preference_functions = preference_functions or []  # 偏好函数

    def add_preference_function(self, pref_func: Callable[[np.ndarray], float]):
        """
        添加偏好函数

        Args:
            pref_func: 偏好函数，输入个体，返回偏好值
        """
        self.preference_functions.append(pref_func)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算偏好偏置值

        Args:
            x: 被评估的个体
            context: 优化上下文

        Returns:
            偏好偏置值
        """
        preference_score = 0.0

        # 应用愿望水平偏好
        for obj_name, aspiration in self.aspiration_levels.items():
            current_value = context.metrics.get(f'obj_{obj_name}', 0.0)
            if isinstance(aspiration, tuple):  # 区间愿望 (min, max)
                min_val, max_val = aspiration
                if min_val <= current_value <= max_val:
                    preference_score += 1.0  # 在满意区间内
                else:
                    distance = min(abs(current_value - min_val),
                                  abs(current_value - max_val))
                    preference_score -= distance  # 距离满意区间的惩罚
            else:  # 单一目标值
                distance = abs(current_value - aspiration)
                preference_score -= distance

        # 应用自定义偏好函数
        for pref_func in self.preference_functions:
            try:
                pref_score = pref_func(x)
                preference_score += pref_score
            except Exception:
                pass  # 忽略无效偏好函数

        return self.weight * preference_score


class RuleBasedBias(DomainBias):
    """
    基于规则的偏置 - 支持复杂业务规则

    允许定义复杂的条件-动作规则：
    - 条件检查：基于个体和上下文
    - 动作执行：返回相应的偏置值
    - 规则优先级管理
    - 规则触发历史记录

    适用于复杂的业务逻辑和专家规则集成。
    """
    context_requires = ("generation",)
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Reads context fields: generation; outputs scalar bias only."



    def __init__(self, weight: float = 1.0, rules: Optional[List[Dict]] = None):
        """
        初始化基于规则的偏置

        Args:
            weight: 默认偏置权重
            rules: 规则列表
        """
        super().__init__("rule_based", weight, mandatory=False)
        self.rules = rules or []                               # 规则列表
        self.rule_firings = []                               # 规则触发记录

    def add_rule(
        self,
        condition: Callable[[np.ndarray, OptimizationContext], bool],
        action: Callable[[np.ndarray], float],
        priority: int = 1,
        description: str = ""
    ):
        """
        添加规则

        Args:
            condition: 条件函数，返回True时规则触发
            action: 动作函数，返回偏置值
            priority: 规则优先级（数值越大优先级越高）
            description: 规则描述

        Example:
            def max_capacity_rule(x, context):
                return x[0] > 100.0  # 容量约束

            def capacity_penalty(x):
                return (x[0] - 100.0) * 10.0

            bias.add_rule(max_capacity_rule, capacity_penalty, priority=2)
        """
        self.rules.append({
            'condition': condition,
            'action': action,
            'priority': priority,
            'description': description,
            'fires': 0  # 触发次数统计
        })

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算规则偏置值

        Args:
            x: 被评估的个体
            context: 优化上下文

        Returns:
            规则偏置值
        """
        total_bias = 0.0
        fired_rules = []

        # 按优先级排序规则（高优先级先执行）
        sorted_rules = sorted(self.rules, key=lambda r: r['priority'], reverse=True)

        for rule in sorted_rules:
            try:
                if rule['condition'](x, context):
                    bias_value = rule['action'](x)
                    total_bias += bias_value
                    rule['fires'] += 1
                    fired_rules.append(rule['description'])
            except Exception:
                pass  # 忽略无效规则

        # 记录规则触发历史
        if fired_rules:
            self.rule_firings.append({
                'generation': context.generation,
                'fired_rules': fired_rules,
                'total_bias': total_bias
            })

        return self.weight * total_bias

    def get_rule_statistics(self) -> Dict[str, Any]:
        """
        获取规则统计信息

        Returns:
            规则执行统计
        """
        return {
            'rule_counts': {r['description']: r['fires'] for r in self.rules},
            'total_firings': sum(r['fires'] for r in self.rules),
            'most_fired_rule': max(self.rules, key=lambda r: r['fires'])['description'] if self.rules else None
        }
