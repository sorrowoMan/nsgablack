"""
NSGA-III 参考点偏置实现模块

该模块实现 NSGA-III (Non-dominated Sorting Genetic Algorithm III)
算法思想的偏置化，将参考点引导概念注入到任何优化算法中：
- 参考点生成与引导
- Pareto前沿均匀分布
- 多维目标空间的分解
- 参考点关联策略
- 算法无关性的NSGA-III特性注入
- 与其他偏置的无缝组合

通过偏置系统，任何算法（GA、PSO、SA、DE等）都可以获得 NSGA-III 的
高维多目标优化能力。

参考论文：
    K. Deb and H. Jain, "An Evolutionary Many-Objective Optimization Algorithm
    Using Reference-Point-Based Non-dominated Sorting, Part I: Solving Problems
    with Box Constraints," IEEE Transactions on Evolutionary Computation, 2014.
"""

import numpy as np
from typing import List, Dict, Any, Optional, Literal
from ..core.base import AlgorithmicBias, OptimizationContext


class NSGA3ReferencePointBias(AlgorithmicBias):
    """
    NSGA-III 参考点偏置 - 将参考点引导思想注入到任何算法

    核心思想是通过预设的参考点来引导搜索过程：
    - 在目标空间中定义一组参考点
    - 计算个体到参考点的距离
    - 距离参考点越近 → 偏置值越小（奖励）
    - 促进Pareto前沿的均匀分布
    - 特别适用于高维多目标优化（3个以上目标）

    通过这种转换，任何优化算法都能获得NSGA-III的参考点引导特性。

    使用示例：
        >>> # 2目标问题，使用Das-Dennis方法生成参考点
        >>> nsga3_bias = NSGA3ReferencePointBias(
        ...     num_objectives=2,
        ...     divisions=12,
        ...     generation_method='das_dennis'
        ... )
        >>> solver.bias_manager.algorithmic_manager.add_bias(nsga3_bias)

        >>> # 3目标问题，使用随机参考点
        >>> reference_points = np.random.rand(10, 3)
        >>> nsga3_bias = NSGA3ReferencePointBias(
        ...     reference_points=reference_points,
        ...     distance_metric='euclidean'
        ... )
    """

    def __init__(
        self,
        num_objectives: int = 2,
        divisions: int = 12,
        reference_points: Optional[np.ndarray] = None,
        initial_weight: float = 0.6,
        distance_metric: Literal['euclidean', 'manhattan', 'chebyshev'] = 'euclidean',
        generation_method: Literal['das_dennis', 'random', 'custom'] = 'das_dennis',
        adaptive: bool = True
    ):
        """
        初始化 NSGA-III 参考点偏置

        Args:
            num_objectives: 目标数量
            divisions: Das-Dennis方法的分割数（控制参考点密度）
            reference_points: 自定义参考点集（如果提供，则忽略generation_method）
            initial_weight: 偏置权重，控制参考点引导的影响强度
            distance_metric: 距离度量方式
                            - 'euclidean': 欧几里得距离
                            - 'manhattan': 曼哈顿距离
                            - 'chebyshev': 切比雪夫距离
            generation_method: 参考点生成方法
                              - 'das_dennis': Das-Dennis方法（推荐，均匀分布）
                              - 'random': 随机生成
                              - 'custom': 使用自定义参考点
            adaptive: 是否自适应调整参考点
        """
        super().__init__("nsga3_reference", initial_weight, adaptive)

        self.num_objectives = num_objectives
        self.divisions = divisions
        self.distance_metric = distance_metric
        self.generation_method = generation_method

        # 生成或使用自定义参考点
        if reference_points is not None:
            self.reference_points = np.asarray(reference_points)
        else:
            self.reference_points = self._generate_reference_points()

        # 归一化参考点到[0, 1]区间
        self._normalize_reference_points()

        # 历史记录（用于分析和调试）
        self.distance_history = []                            # 到最近参考点的距离历史
        self.associated_reference_history = []                # 关联的参考点历史
        self.reference_point_usage = np.zeros(len(self.reference_points))  # 参考点使用统计

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算 NSGA-III 参考点偏置值

        核心算法：
        1. 获取当前个体的多目标值
        2. 归一化目标值
        3. 计算到各个参考点的距离
        4. 找到最近的参考点
        5. 转换为偏置值

        Args:
            x: 被评估的个体（决策变量向量）
            context: 优化上下文，需要包含多目标信息

        Returns:
            NSGA-III 参考点偏置值（负值表示奖励，正值表示惩罚）

        Note:
            上下文需要提供：
            - context.metrics['objectives']: 当前个体的多目标值数组
            - context.metrics['population_objectives']: 种群的多目标值（用于归一化）
        """
        # 获取多目标值
        objectives = context.metrics.get('objectives', None)
        if objectives is None:
            return 0.0

        objectives = np.asarray(objectives)

        # 归一化目标值
        normalized_objectives = self._normalize_objectives(objectives, context)

        # 计算到所有参考点的距离
        distances = self._compute_distances_to_references(normalized_objectives)

        # 找到最近的参考点
        min_distance_idx = np.argmin(distances)
        min_distance = distances[min_distance_idx]

        # 更新参考点使用统计
        self.reference_point_usage[min_distance_idx] += 1

        # 记录历史
        self.distance_history.append(min_distance)
        self.associated_reference_history.append(min_distance_idx)

        # 转换为偏置（距离越小越好）
        # 负偏置 = 奖励（鼓励靠近参考点）
        bias_value = min_distance * self.weight

        return bias_value

    def _generate_reference_points(self) -> np.ndarray:
        """
        生成参考点

        根据选择的方法生成参考点集。

        Returns:
            参考点数组，形状为(num_points, num_objectives)
        """
        if self.generation_method == 'das_dennis':
            return self._das_dennis_generation()
        elif self.generation_method == 'random':
            return self._random_generation()
        else:
            # 默认使用Das-Dennis
            return self._das_dennis_generation()

    def _das_dennis_generation(self) -> np.ndarray:
        """
        Das-Dennis 参考点生成方法

        在单纯形上生成均匀分布的参考点。
        对于d维目标空间和h个分割，生成的参考点数量为 C(h+d-1, d-1)。

        Returns:
            参考点数组
        """
        def recursive_generate(d, h, sum_val, current_point):
            """递归生成Das-Dennis参考点"""
            if d == 1:
                current_point.append(sum_val)
                reference_points.append(current_point.copy())
                current_point.pop()
            else:
                for i in range(h + 1):
                    current_point.append(i / h)
                    recursive_generate(d - 1, h, sum_val - i / h, current_point)
                    current_point.pop()

        reference_points = []
        recursive_generate(self.num_objectives, self.divisions, 1.0, [])

        return np.array(reference_points)

    def _random_generation(self) -> np.ndarray:
        """
        随机参考点生成方法

        在单纯形上随机生成参考点。

        Returns:
            参考点数组
        """
        num_points = self.divisions * 10  # 随机方法生成更多点
        reference_points = []

        for _ in range(num_points):
            # 生成随机点
            point = np.random.rand(self.num_objectives)

            # 归一化到单纯形上（sum = 1）
            point = point / np.sum(point)

            reference_points.append(point)

        return np.array(reference_points)

    def _normalize_reference_points(self):
        """
        归一化参考点到[0, 1]区间
        """
        # 确保所有参考点在[0, 1]区间且和为1
        for i in range(len(self.reference_points)):
            point = self.reference_points[i]
            point = np.maximum(point, 0)
            point = point / np.sum(point)
            self.reference_points[i] = point

    def _normalize_objectives(self, objectives: np.ndarray, context: OptimizationContext) -> np.ndarray:
        """
        归一化目标值

        根据种群的范围将目标值归一化到[0, 1]区间。

        Args:
            objectives: 原始目标值
            context: 优化上下文

        Returns:
            归一化后的目标值
        """
        # 获取种群的目标值用于归一化
        population_objectives = context.metrics.get('population_objectives', None)

        if population_objectives is not None:
            pop_obj = np.asarray(population_objectives)
            min_obj = np.min(pop_obj, axis=0)
            max_obj = np.max(pop_obj, axis=0)
            range_obj = max_obj - min_obj

            # 避免除零
            range_obj = np.maximum(range_obj, 1e-10)

            # 归一化
            normalized = (objectives - min_obj) / range_obj
        else:
            # 如果没有种群信息，使用简单缩放
            # 假设目标值在合理范围内（可以根据实际问题调整）
            normalized = objectives / (np.abs(objectives).max() + 1e-10)

        # 确保在[0, 1]区间
        normalized = np.clip(normalized, 0, 1)

        return normalized

    def _compute_distances_to_references(self, normalized_objectives: np.ndarray) -> np.ndarray:
        """
        计算归一化目标到所有参考点的距离

        Args:
            normalized_objectives: 归一化后的目标值

        Returns:
            距离数组
        """
        if self.distance_metric == 'euclidean':
            # 欧几里得距离
            distances = np.linalg.norm(self.reference_points - normalized_objectives, axis=1)

        elif self.distance_metric == 'manhattan':
            # 曼哈顿距离
            distances = np.sum(np.abs(self.reference_points - normalized_objectives), axis=1)

        elif self.distance_metric == 'chebyshev':
            # 切比雪夫距离
            distances = np.max(np.abs(self.reference_points - normalized_objectives), axis=1)

        else:
            # 默认使用欧几里得距离
            distances = np.linalg.norm(self.reference_points - normalized_objectives, axis=1)

        return distances

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取 NSGA-III 参考点偏置统计信息

        Returns:
            包含各种统计指标的字典
        """
        if not self.distance_history:
            return {
                'num_reference_points': len(self.reference_points),
                'distance_metric': self.distance_metric,
                'generation_method': self.generation_method,
                'avg_distance': 0.0,
                'best_distance': 0.0,
                'reference_point_usage': self.reference_point_usage.tolist()
            }

        return {
            'num_reference_points': len(self.reference_points),         # 参考点数量
            'distance_metric': self.distance_metric,                    # 距离度量方式
            'generation_method': self.generation_method,                # 生成方法
            'avg_distance': float(np.mean(self.distance_history)),     # 平均距离
            'best_distance': float(np.min(self.distance_history)),     # 最好距离
            'worst_distance': float(np.max(self.distance_history)),    # 最差距离
            'reference_point_usage': self.reference_point_usage.tolist(),  # 参考点使用统计
            'most_used_reference': int(np.argmax(self.reference_point_usage)),  # 最常用参考点
            'least_used_reference': int(np.argmin(self.reference_point_usage)), # 最少用参考点
            'recent_distances': self.distance_history[-10:]            # 最近10次距离
        }

    def get_reference_points(self) -> np.ndarray:
        """
        获取当前参考点集

        Returns:
            参考点数组
        """
        return self.reference_points.copy()

    def set_reference_points(self, reference_points: np.ndarray):
        """
        设置新的参考点集

        Args:
            reference_points: 新的参考点数组
        """
        self.reference_points = np.asarray(reference_points)
        self._normalize_reference_points()
        self.reference_point_usage = np.zeros(len(self.reference_points))


class AdaptiveNSGA3Bias(NSGA3ReferencePointBias):
    """
    自适应 NSGA-III 参考点偏置

    在标准NSGA-III偏置基础上增加自适应能力：
    - 根据Pareto前沿分布动态调整参考点
    - 自动增减参考点密度
    - 基于收敛状态调整参考点范围
    """

    def __init__(
        self,
        num_objectives: int = 2,
        divisions: int = 12,
        initial_weight: float = 0.6,
        adaptation_window: int = 100,
        density_threshold: float = 0.1
    ):
        """
        初始化自适应 NSGA-III 偏置

        Args:
            num_objectives: 目标数量
            divisions: 初始分割数
            initial_weight: 偏置权重
            adaptation_window: 自适应调整窗口大小
            density_threshold: 密度阈值（用于判断是否需要增加参考点）
        """
        super().__init__(
            num_objectives=num_objectives,
            divisions=divisions,
            initial_weight=initial_weight,
            adaptive=True
        )

        self.adaptation_window = adaptation_window                  # 自适应窗口
        self.density_threshold = density_threshold                  # 密度阈值
        self.initial_divisions = divisions                          # 初始分割数

        # 自适应统计
        self.convergence_history = []                               # 收敛历史
        self.adaptation_count = 0                                   # 调整次数

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算自适应 NSGA-III 参考点偏置值

        在标准NSGA-III计算基础上增加自适应调整逻辑。

        Args:
            x: 被评估的个体
            context: 优化上下文

        Returns:
            自适应调整后的NSGA-III偏置值
        """
        # 执行标准NSGA-III计算
        bias_value = super().compute(x, context)

        # 记录收敛信息
        if self.distance_history:
            self.convergence_history.append(self.distance_history[-1])

        # 自适应调整参考点
        if len(self.convergence_history) >= self.adaptation_window:
            self._adapt_reference_points()

        return bias_value

    def _adapt_reference_points(self):
        """
        自适应调整参考点

        根据收敛历史和参考点使用情况调整参考点集。
        """
        # 检查是否需要增加参考点密度
        avg_distance = np.mean(self.convergence_history[-self.adaptation_window:])

        if avg_distance < self.density_threshold and self.divisions < 20:
            # 收敛良好，增加参考点密度
            self.divisions += 2
            self.reference_points = self._das_dennis_generation()
            self._normalize_reference_points()
            self.reference_point_usage = np.zeros(len(self.reference_points))
            self.adaptation_count += 1

        # 重置收敛历史
        self.convergence_history = []

    def reset_to_initial_state(self):
        """重置到初始状态"""
        self.divisions = self.initial_divisions
        self.reference_points = self._das_dennis_generation()
        self._normalize_reference_points()
        self.reference_point_usage = np.zeros(len(self.reference_points))
        self.convergence_history = []
        self.distance_history = []
        self.associated_reference_history = []
        self.adaptation_count = 0
