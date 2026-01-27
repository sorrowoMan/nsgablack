"""
MOEA/D 分解偏置实现模块

该模块实现 MOEA/D (Multi-Objective Evolutionary Algorithm based on Decomposition)
算法思想的偏置化，将分解优化概念注入到任何优化算法中：
- 多目标分解为单目标子问题
- Tchebycheff聚合函数转换
- Weighted Sum聚合函数转换
- 邻域协作优化思想
- 算法无关性的MOEA/D特性注入
- 与其他偏置的无缝组合

通过偏置系统，任何算法（GA、PSO、SA、DE等）都可以获得 MOEA/D 的分解优化能力。

参考论文：
    Q. Zhang and H. Li, "MOEA/D: A Multiobjective Evolutionary Algorithm Based on
    Decomposition," IEEE Transactions on Evolutionary Computation, 2007.
"""

import numpy as np
from typing import List, Dict, Any, Optional, Literal
from ..core.base import AlgorithmicBias, OptimizationContext


class MOEADDecompositionBias(AlgorithmicBias):
    """
    MOEA/D 分解偏置 - 将多目标分解思想注入到任何算法

    核心思想是将多目标优化问题分解为多个单目标优化子问题：
    - 使用聚合函数（Tchebycheff、Weighted Sum等）将多目标转换为单目标
    - 每个子问题关注目标空间的特定方向
    - 权重向量定义了子问题的偏好方向
    - 聚合函数值越小 → 偏置值越小（奖励）

    通过这种转换，任何优化算法都能获得MOEA/D的分解优化特性。

    使用示例：
        >>> # 2目标问题，均衡偏好
        >>> moead_bias = MOEADDecompositionBias(
        ...     weight_vector=np.array([0.5, 0.5]),
        ...     method='tchebycheff'
        ... )
        >>> solver.bias_manager.algorithmic_manager.add_bias(moead_bias)

        >>> # 3目标问题，偏向第一个目标
        >>> moead_bias = MOEADDecompositionBias(
        ...     weight_vector=np.array([0.7, 0.2, 0.1]),
        ...     method='weighted_sum'
        ... )
    """

    def __init__(
        self,
        weight_vector: np.ndarray,
        initial_weight: float = 0.5,
        method: Literal['tchebycheff', 'weighted_sum', 'boundary_intersection'] = 'tchebycheff',
        adaptive: bool = True
    ):
        """
        初始化 MOEA/D 分解偏置

        Args:
            weight_vector: 权重向量，定义子问题的偏好方向
                          例如：[0.5, 0.5] 表示均衡优化两个目标
                                [0.7, 0.3] 表示更关注第一个目标
            initial_weight: 偏置权重，控制分解偏置的影响强度
            method: 聚合函数方法
                   - 'tchebycheff': Tchebycheff方法（推荐，处理非凸Pareto前沿）
                   - 'weighted_sum': 加权和方法（仅适用于凸问题）
                   - 'boundary_intersection': 边界交叉方法
            adaptive: 是否自适应调整权重
        """
        super().__init__("moead_decomposition", initial_weight, adaptive)

        # 归一化权重向量
        self.weight_vector = np.asarray(weight_vector, dtype=float)
        self.weight_vector = self.weight_vector / np.sum(self.weight_vector)

        self.method = method                                    # 聚合函数方法
        self.ideal_point = None                                 # 理想点（用于Tchebycheff）

        # 历史记录（用于分析和调试）
        self.aggregation_history = []                           # 聚合函数值历史
        self.objective_history = []                             # 原始目标值历史
        self.weight_adjustments = []                            # 权重调整历史

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算 MOEA/D 分解偏置值

        核心算法：
        1. 获取当前个体的多目标值
        2. 更新理想点（如果使用Tchebycheff）
        3. 使用聚合函数将多目标转换为单目标
        4. 转换为偏置值

        Args:
            x: 被评估的个体（决策变量向量）
            context: 优化上下文，需要包含多目标信息

        Returns:
            MOEA/D 分解偏置值（负值表示奖励，正值表示惩罚）

        Note:
            上下文需要提供：
            - context.metrics['objectives']: 当前个体的多目标值数组
            - context.metrics['ideal_point']: 当前理想点（可选，自动更新）
        """
        # 获取多目标值
        objectives = context.metrics.get('objectives', None)
        if objectives is None:
            return 0.0

        objectives = np.asarray(objectives)
        self.objective_history.append(objectives.copy())

        # 更新理想点
        if self.ideal_point is None:
            self.ideal_point = objectives.copy()
        else:
            self.ideal_point = np.minimum(self.ideal_point, objectives)

        # 计算聚合函数值
        aggregation_value = self._compute_aggregation(objectives)

        # 记录历史
        self.aggregation_history.append(aggregation_value)

        # 转换为偏置（聚合值越小越好）
        # 负偏置 = 奖励（因为是最小化问题）
        bias_value = aggregation_value * self.weight

        return bias_value

    def _compute_aggregation(self, objectives: np.ndarray) -> float:
        """
        计算聚合函数值

        根据选择的方法计算多目标到单目标的聚合值。

        Args:
            objectives: 多目标值数组

        Returns:
            聚合函数值（越小越好）
        """
        if self.method == 'tchebycheff':
            return self._tchebycheff_aggregation(objectives)
        elif self.method == 'weighted_sum':
            return self._weighted_sum_aggregation(objectives)
        elif self.method == 'boundary_intersection':
            return self._boundary_intersection_aggregation(objectives)
        else:
            # 默认使用Tchebycheff
            return self._tchebycheff_aggregation(objectives)

    def _tchebycheff_aggregation(self, objectives: np.ndarray) -> float:
        """
        Tchebycheff 聚合函数

        g^te(x|λ, z*) = max{λ_i * |f_i(x) - z*_i|}

        其中：
        - λ 是权重向量
        - z* 是理想点
        - f_i(x) 是第i个目标值

        优势：可以处理非凸Pareto前沿

        Args:
            objectives: 多目标值数组

        Returns:
            Tchebycheff聚合值
        """
        # 计算加权距离
        distances = self.weight_vector * np.abs(objectives - self.ideal_point)
        return float(np.max(distances))

    def _weighted_sum_aggregation(self, objectives: np.ndarray) -> float:
        """
        加权聚合函数

        g^ws(x|λ) = Σ λ_i * f_i(x)

        其中：
        - λ 是权重向量
        - f_i(x) 是第i个目标值

        注意：仅适用于凸Pareto前沿问题

        Args:
            objectives: 多目标值数组

        Returns:
            加权和聚合值
        """
        return float(np.dot(self.weight_vector, objectives))

    def _boundary_intersection_aggregation(self, objectives: np.ndarray) -> float:
        """
        边界交叉聚合函数（Penalty-based Boundary Intersection, PBI）

        g^pbi(x|λ, z*) = d1 + θ * d2

        其中：
        - d1 是到权重向量方向的距离
        - d2 是垂直于权重向量方向的距离
        - θ 是惩罚参数

        优势：在处理复杂Pareto前沿形状时表现更好

        Args:
            objectives: 多目标值数组

        Returns:
            PBI聚合值
        """
        theta = 5.0  # 惩罚参数

        # 归一化目标向量（相对于理想点）
        normalized_obj = objectives - self.ideal_point

        # 计算d1：沿权重向量方向的距离
        d1 = np.dot(normalized_obj, self.weight_vector) / np.linalg.norm(self.weight_vector)

        # 计算d2：垂直于权重向量方向的距离
        d2 = np.linalg.norm(normalized_obj - d1 * self.weight_vector / np.linalg.norm(self.weight_vector))

        # PBI聚合值
        return float(d1 + theta * d2)

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取 MOEA/D 分解偏置统计信息

        Returns:
            包含各种统计指标的字典
        """
        if not self.aggregation_history:
            return {
                'method': self.method,
                'weight_vector': self.weight_vector.tolist(),
                'avg_aggregation': 0.0,
                'best_aggregation': 0.0,
                'ideal_point': None
            }

        return {
            'method': self.method,                                    # 聚合方法
            'weight_vector': self.weight_vector.tolist(),             # 权重向量
            'avg_aggregation': float(np.mean(self.aggregation_history)),  # 平均聚合值
            'best_aggregation': float(np.min(self.aggregation_history)),  # 最好聚合值
            'worst_aggregation': float(np.max(self.aggregation_history)), # 最差聚合值
            'ideal_point': self.ideal_point.tolist() if self.ideal_point is not None else None,  # 理想点
            'recent_aggregations': [float(v) for v in self.aggregation_history[-10:]]      # 最近10次聚合值
        }


class AdaptiveMOEADBias(MOEADDecompositionBias):
    """
    自适应 MOEA/D 偏置

    在标准MOEA/D偏置基础上增加自适应能力：
    - 根据优化进展动态调整权重向量
    - 自动切换聚合函数方法
    - 基于性能反馈调整偏好方向
    """

    def __init__(
        self,
        weight_vector: np.ndarray,
        initial_weight: float = 0.5,
        method: Literal['tchebycheff', 'weighted_sum', 'boundary_intersection'] = 'tchebycheff',
        adaptation_window: int = 50,
        weight_adjustment_rate: float = 0.1
    ):
        """
        初始化自适应 MOEA/D 偏置

        Args:
            weight_vector: 初始权重向量
            initial_weight: 偏置权重
            method: 聚合函数方法
            adaptation_window: 自适应调整窗口大小
            weight_adjustment_rate: 权重调整率
        """
        super().__init__(weight_vector, initial_weight, method, adaptive=True)

        self.adaptation_window = adaptation_window                    # 自适应窗口
        self.weight_adjustment_rate = weight_adjustment_rate          # 权重调整率
        self.initial_weight_vector = weight_vector.copy()             # 初始权重向量

        # 自适应统计
        self.performance_history = []                                 # 性能历史

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算自适应 MOEA/D 偏置值

        在标准MOEA/D计算基础上增加自适应调整逻辑。

        Args:
            x: 被评估的个体
            context: 优化上下文

        Returns:
            自适应调整后的MOEA/D偏置值
        """
        # 执行标准MOEA/D计算
        bias_value = super().compute(x, context)

        # 记录性能
        if hasattr(context, 'metrics') and 'objectives' in context.metrics:
            self.performance_history.append(context.metrics['objectives'])

        # 自适应调整权重向量
        if len(self.performance_history) >= self.adaptation_window:
            self._adapt_weight_vector()

        return bias_value

    def _adapt_weight_vector(self):
        """
        自适应调整权重向量

        根据近期优化表现调整权重向量的方向。
        """
        if len(self.performance_history) < self.adaptation_window:
            return

        # 获取最近的目标值
        recent_objectives = np.array(self.performance_history[-self.adaptation_window:])

        # 计算每个目标的标准差（作为改进空间的指标）
        std_per_objective = np.std(recent_objectives, axis=0)

        # 标准差小的目标可能已经收敛，应该降低其权重
        # 标准差大的目标还有改进空间，应该增加其权重
        adjustment = std_per_objective / (np.sum(std_per_objective) + 1e-10)

        # 平滑调整权重向量
        self.weight_vector = (1 - self.weight_adjustment_rate) * self.weight_vector + \
                            self.weight_adjustment_rate * adjustment

        # 重新归一化
        self.weight_vector = self.weight_vector / np.sum(self.weight_vector)

        # 记录调整历史
        self.weight_adjustments.append(self.weight_vector.copy())

    def reset_to_initial_weights(self):
        """重置权重向量到初始值"""
        self.weight_vector = self.initial_weight_vector.copy()
        self.performance_history = []
        self.weight_adjustments = []
