"""
工程优化偏置实现模块

该模块提供专门针对工程优化问题的偏置实现，用于：
- 结构优化和设计参数调优
- 工程约束和安全规范处理
- 多学科设计优化(MDO)支持
- 精度和可靠性要求的满足

工程优化偏置的特点：
- 高精度要求：通常需要数值稳定性好的偏置
- 约束严格：安全性和可靠性约束通常是刚性的
- 多目标：平衡性能、成本、重量、可靠性等
- 计算昂贵：工程仿真计算成本高，需要高效引导

适用场景：
- 机械结构设计优化
- 电子电路设计
- 控制系统参数调优
- 流体动力学优化
- 材料科学设计
"""

import numpy as np
from typing import List, Dict, Any, Callable, Optional

# 导入核心偏置类
from ...core.base import AlgorithmicBias, DomainBias, OptimizationContext
from ...algorithmic.convergence import ConvergenceBias, PrecisionBias
from ...algorithmic.diversity import AdaptiveDiversityBias
from ...domain.constraint import ConstraintBias, FeasibilityBias


class EngineeringPrecisionBias(AlgorithmicBias):
    """
    工程精度偏置 - 专门用于工程设计的精细优化

    该偏置专注于：
    - 数值精度和稳定性保证
    - 局部精细搜索能力增强
    - 收敛到高精度解的引导
    - 避免数值震荡和不稳定

    适用于对解精度要求极高的工程设计问题，
    如结构优化、参数调优等场景。
    """

    def __init__(self, weight: float = 0.15, precision_threshold: float = 1e-6,
                 convergence_window: int = 10, adaptive_precision: bool = True):
        """
        初始化工程精度偏置

        Args:
            weight: 偏置权重
            precision_threshold: 精度阈值（小于此值认为已收敛）
            convergence_window: 收敛检查窗口大小
            adaptive_precision: 是否启用自适应精度控制
        """
        super().__init__("engineering_precision", weight, adaptive=True)
        self.precision_threshold = precision_threshold        # 精度阈值
        self.convergence_window = convergence_window         # 收敛检查窗口
        self.adaptive_precision = adaptive_precision         # 自适应精度控制
        self.convergence_history = []                        # 收敛历史记录
        self.current_precision = 1e-4                       # 当前精度要求

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算工程精度偏置值

        基于当前个体的数值精度和收敛状态计算偏置：
        1. 检查数值稳定性和精度水平
        2. 评估局部收敛性
        3. 动态调整精度要求
        4. 引导向高精度区域搜索

        Args:
            x: 当前设计参数向量
            context: 优化上下文，包含精度相关信息

        Returns:
            工程精度偏置值（正值表示精度改善潜力）
        """
        # 获取当前解的精度信息
        current_precision = self._estimate_numerical_precision(x, context)
        self.convergence_history.append(current_precision)

        # 保持历史窗口大小
        if len(self.convergence_history) > self.convergence_window:
            self.convergence_history.pop(0)

        # 自适应调整精度要求
        if self.adaptive_precision:
            self._adjust_precision_requirement()

        # 计算精度改善潜力
        if current_precision > self.current_precision:
            # 精度不足，给予负偏置（惩罚）
            precision_deficit = current_precision - self.current_precision
            return -self.weight * precision_deficit * 1000  # 放大惩罚
        else:
            # 精度满足要求，给予正偏置（奖励）
            precision_margin = self.current_precision - current_precision
            return self.weight * precision_margin * 100

    def _estimate_numerical_precision(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        估计当前解的数值精度

        Args:
            x: 设计参数向量
            context: 优化上下文

        Returns:
            估计的数值精度（越小越好）
        """
        # 方法1：基于目标函数值的变化率
        if len(self.convergence_history) > 1:
            recent_values = self.convergence_history[-5:]
            if len(recent_values) >= 2:
                value_changes = [abs(recent_values[i] - recent_values[i-1])
                               for i in range(1, len(recent_values))]
                avg_change = np.mean(value_changes)
                return avg_change

        # 方法2：基于设计参数的微小扰动
        perturbation_magnitude = 1e-8
        base_fitness = context.metrics.get('objective', 0.0)

        total_sensitivity = 0.0
        for i in range(min(len(x), 10)):  # 最多检查10个参数
            x_perturbed = x.copy()
            x_perturbed[i] += perturbation_magnitude

            # 简化的敏感性估计
            sensitivity = abs(x_perturbed[i] - x[i]) / (perturbation_magnitude + 1e-12)
            total_sensitivity += sensitivity

        return total_sensitivity / max(1, min(len(x), 10))

    def _adjust_precision_requirement(self):
        """自适应调整精度要求"""
        if len(self.convergence_history) < self.convergence_window:
            return

        # 检查最近的收敛趋势
        recent_improvements = [
            self.convergence_history[i] - self.convergence_history[i-1]
            for i in range(1, min(len(self.convergence_history), self.convergence_window))
        ]

        if len(recent_improvements) > 0:
            avg_improvement = np.mean(recent_improvements)

            if avg_improvement < self.precision_threshold:
                # 改善很慢，提高精度要求
                self.current_precision *= 0.9
            else:
                # 改善良好，保持当前精度要求
                pass

            # 限制精度要求范围
            self.current_precision = np.clip(
                self.current_precision, 1e-8, 1e-3
            )


class EngineeringConstraintBias(DomainBias):
    """
    工程约束偏置 - 处理工程设计中的物理和安全约束

    支持多种工程约束类型：
    - 物理约束：强度、刚度、稳定性等
    - 几何约束：尺寸、间隙、干涉等
    - 性能约束：频率、响应时间、效率等
    - 安全约束：安全系数、失效概率等
    - 制造约束：可制造性、成本限制等
    """

    def __init__(self, weight: float = 1.0, safety_factor: float = 1.5,
                 constraint_types: Optional[List[str]] = None):
        """
        初始化工程约束偏置

        Args:
            weight: 偏置权重
            safety_factor: 安全系数（约束放大的倍数）
            constraint_types: 约束类型列表
        """
        super().__init__("engineering_constraint", weight, mandatory=True)
        self.safety_factor = safety_factor                    # 安全系数
        self.constraint_types = constraint_types or []        # 约束类型列表
        self.constraints = []                                # 具体约束函数列表
        self.constraint_weights = []                          # 约束权重列表
        self.violation_history = []                          # 违反历史记录

    def add_engineering_constraint(
        self,
        constraint_func: Callable[[np.ndarray], float],
        constraint_type: str,
        weight: float = 1.0,
        description: str = ""
    ):
        """
        添加工程约束

        Args:
            constraint_func: 约束函数，输入设计参数，返回违反程度
            constraint_type: 约束类型 ('strength', 'geometry', 'performance', 'safety', 'manufacturing')
            weight: 约束权重
            description: 约束描述

        Example:
            # 添加强度约束：应力 <= 200MPa
            def stress_constraint(x):
                stress = calculate_stress(x)
                return max(0, stress - 200)  # 返回超过量

            bias.add_engineering_constraint(
                stress_constraint,
                'strength',
                weight=2.0,
                description='Maximum allowable stress'
            )
        """
        self.constraints.append(constraint_func)
        self.constraint_weights.append(weight)
        self.constraint_types.append(constraint_type)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算工程约束偏置值

        Args:
            x: 当前设计参数
            context: 优化上下文

        Returns:
            总约束违反惩罚值
        """
        total_violation = 0.0
        constraint_violations = []

        for i, (constraint, weight, c_type) in enumerate(
            zip(self.constraints, self.constraint_weights, self.constraint_types)
        ):
            try:
                violation = constraint(x)

                if violation > 0:
                    # 应用安全系数
                    adjusted_violation = violation * self.safety_factor
                    constraint_penalty = adjusted_violation * weight
                    total_violation += constraint_penalty
                    constraint_violations.append(adjusted_violation)

            except Exception:
                # 约束计算失败时给予惩罚
                total_violation += weight * 1000
                constraint_violations.append(1000)

        # 记录违反历史
        if total_violation > 0:
            self.violation_history.append({
                'generation': context.generation,
                'total_violation': total_violation,
                'constraint_count': len(constraint_violations),
                'max_violation': max(constraint_violations) if constraint_violations else 0
            })

        return total_violation * self.weight

    def get_constraint_status(self) -> Dict[str, Any]:
        """
        获取约束状态信息

        Returns:
            约束状态统计信息
        """
        if not self.violation_history:
            return {
                'total_constraints': len(self.constraints),
                'violation_rate': 0.0,
                'avg_violation': 0.0,
                'max_violation': 0.0
            }

        recent_violations = [v['total_violation'] for v in self.violation_history[-10:]]

        return {
            'total_constraints': len(self.constraints),
            'constraint_types': list(set(self.constraint_types)),
            'violation_rate': len(self.violations) / max(1, self.usage_count),
            'avg_violation': np.mean(recent_violations),
            'max_violation': max(recent_violations),
            'violation_trend': 'improving' if len(recent_violations) > 1 and
                               recent_violations[-1] < recent_violations[-2] else 'stable'
        }


class EngineeringRobustnessBias(AlgorithmicBias):
    """
    工程鲁棒性偏置 - 确保设计解对参数变化的鲁棒性

    该偏置用于：
    - 提高设计对制造公差的容忍度
    - 减少环境变化对性能的影响
    - 增强设计的稳定性和可靠性
    - 优化鲁棒性指标（如信噪比）

    特别适用于需要考虑不确定性的工程设计问题。
    """

    def __init__(self, weight: float = 0.2, perturbation_magnitude: float = 0.01,
                 sample_size: int = 20, robustness_metric: str = 'variance'):
        """
        初始化工程鲁棒性偏置

        Args:
            weight: 偏置权重
            perturbation_magnitude: 扰动幅度（模拟制造公差）
            sample_size: 采样数量
            robustness_metric: 鲁棒性指标 ('variance', 'worst_case', 'signal_noise')
        """
        super().__init__("engineering_robustness", weight, adaptive=True)
        self.perturbation_magnitude = perturbation_magnitude  # 扰动幅度
        self.sample_size = sample_size                        # 采样数量
        self.robustness_metric = robustness_metric            # 鲁棒性指标

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算工程鲁棒性偏置值

        通过在当前解周围进行扰动采样，评估解的鲁棒性。

        Args:
            x: 当前设计参数
            context: 优化上下文

        Returns:
            鲁棒性偏置值（负值表示鲁棒性差，需要惩罚）
        """
        eval_func = context.problem_data.get('eval_func')
        if eval_func is None:
            return 0.0

        # 获取基准性能
        try:
            baseline_performance = eval_func(x)
        except Exception as e:
            # 基准失败，记录后返回0偏置
            import logging
            logging.getLogger(__name__).warning("baseline eval failed in EngineeringRobustness: %s", e, exc_info=True)
            return 0.0

        # 在设计参数周围采样
        perturbed_performances = []

        for _ in range(self.sample_size):
            # 生成扰动
            perturbation = np.random.normal(0, self.perturbation_magnitude, x.shape)
            x_perturbed = x + perturbation

            # 确保扰动在设计空间内
            x_perturbed = np.clip(x_perturbed, 0, 1)

            try:
                perturbed_performance = eval_func(x_perturbed)
                perturbed_performances.append(perturbed_performance)
            except Exception as e:
                # 评估失败时给予惩罚并记录
                import logging
                logging.getLogger(__name__).debug("perturbed eval failed; penalize inf: %s", e, exc_info=True)
                perturbed_performances.append(float('inf'))

        # 计算鲁棒性指标
        robustness_score = self._calculate_robustness_metric(
            baseline_performance, perturbed_performances
        )

        # 转换为偏置值（鲁棒性越好，偏置值越大）
        return self.weight * robustness_score

    def _calculate_robustness_metric(self, baseline: float,
                                   perturbed: List[float]) -> float:
        """
        计算鲁棒性指标

        Args:
            baseline: 基准性能值
            perturbed: 扰动后的性能值列表

        Returns:
            鲁棒性得分（越大越好）
        """
        if self.robustness_metric == 'variance':
            # 方差指标：方差越小越鲁棒
            variance = np.var(perturbed)
            robustness = 1.0 / (1.0 + variance)  # 转换为正向指标

        elif self.robustness_metric == 'worst_case':
            # 最坏情况指标：最坏性能与基准的差异
            worst_performance = max(perturbed)
            worst_case_degradation = abs(worst_performance - baseline)
            robustness = 1.0 / (1.0 + worst_case_degradation)

        elif self.robustness_metric == 'signal_noise':
            # 信噪比指标
            mean_performance = np.mean(perturbed)
            std_performance = np.std(perturbed)
            if std_performance > 0:
                snr = mean_performance / std_performance
                robustness = snr / (1.0 + abs(snr))  # 归一化
            else:
                robustness = 1.0
        else:
            # 默认使用方差
            variance = np.var(perturbed)
            robustness = 1.0 / (1.0 + variance)

        return robustness


# 便捷函数
def create_engineering_bias_suite(problem_type: str = "general") -> List[AlgorithmicBias]:
    """
    创建工程问题专用偏置套件

    Args:
        problem_type: 问题类型 ('structural', 'electrical', 'control', 'general')

    Returns:
        工程偏置列表
    """
    biases = []

    # 基础精度偏置（所有工程问题都需要）
    biases.append(EngineeringPrecisionBias(weight=0.15))

    # 根据问题类型添加专门偏置
    if problem_type == "structural":
        # 结构优化：需要高精度和鲁棒性
        biases.append(EngineeringPrecisionBias(weight=0.2, precision_threshold=1e-8))
        biases.append(EngineeringRobustnessBias(weight=0.25, robustness_metric='variance'))

    elif problem_type == "electrical":
        # 电路设计：需要精度和稳定性
        biases.append(EngineeringPrecisionBias(weight=0.18, precision_threshold=1e-7))
        biases.append(EngineeringRobustnessBias(weight=0.2, perturbation_magnitude=0.005))

    elif problem_type == "control":
        # 控制系统：需要鲁棒性和稳定性
        biases.append(EngineeringRobustnessBias(weight=0.3, robustness_metric='signal_noise'))

    else:  # general
        # 通用工程问题
        biases.append(EngineeringPrecisionBias(weight=0.15))
        biases.append(EngineeringRobustnessBias(weight=0.15))

    return biases


def create_engineering_constraint_bias(safety_factor: float = 1.5) -> EngineeringConstraintBias:
    """
    创建工程约束偏置

    Args:
        safety_factor: 安全系数

    Returns:
        工程约束偏置实例
    """
    return EngineeringConstraintBias(
        weight=1.0,
        safety_factor=safety_factor,
        constraint_types=['strength', 'geometry', 'performance', 'safety']
    )


# 导出接口
__all__ = [
    'EngineeringPrecisionBias',
    'EngineeringConstraintBias',
    'EngineeringRobustnessBias',
    'create_engineering_bias_suite',
    'create_engineering_constraint_bias'
]
