"""
SPEA2 强度偏置实现模块

该模块实现 SPEA2 (Strength Pareto Evolutionary Algorithm 2)
算法思想的偏置化，将强度和最近邻概念注入到任何优化算法中：
- Pareto强度计算
- k-最近邻距离估算
- 精英保留策略
- 适应度赋值策略
- 算法无关性的SPEA2特性注入
- 与其他偏置的无缝组合

通过偏置系统，任何算法（GA、PSO、SA、DE等）都可以获得 SPEA2 的
精细Pareto前沿维护能力。

参考论文：
    E. Zitzler, M. Laumanns, and L. Thiele, "SPEA2: Improving the Strength
    Pareto Evolutionary Algorithm for Multiobjective Optimization,"
    Evolutionary Methods for Design, Optimisation and Control, 2002.
"""

import numpy as np
from typing import List, Dict, Any, Optional, Literal
from ..core.base import AlgorithmicBias, OptimizationContext


class SPEA2StrengthBias(AlgorithmicBias):
    """
    SPEA2 强度偏置 - 将强度和最近邻思想注入到任何算法

    核心思想是通过Pareto强度和最近邻距离来评估个体质量：
    - Pareto强度：个体支配的其他个体数量
    - k-最近邻距离：个体在目标空间中的局部密度
    - 强度越高（支配更多个体）→ 偏置值越小（奖励）
    - 最近邻距离越大（稀疏区域）→ 偏置值越小（奖励）
    - 结合强度和密度进行精细的适应度赋值

    通过这种转换，任何优化算法都能获得SPEA2的精细选择特性。

    使用示例：
        >>> # 标准SPEA2偏置
        >>> spea2_bias = SPEA2StrengthBias(
        ...     k_nearest=5,
        ...     strength_weight=0.6,
        ...     density_weight=0.4
        ... )
        >>> solver.bias_manager.algorithmic_manager.add_bias(spea2_bias)

        >>> # 强调密度的SPEA2偏置
        >>> spea2_bias = SPEA2StrengthBias(
        ...     k_nearest=10,
        ...     strength_weight=0.3,
        ...     density_weight=0.7
        ... )
    """

    def __init__(
        self,
        initial_weight: float = 0.5,
        k_nearest: int = 5,
        strength_weight: float = 0.6,
        density_weight: float = 0.4,
        distance_metric: Literal['euclidean', 'manhattan'] = 'euclidean',
        adaptive: bool = True
    ):
        """
        初始化 SPEA2 强度偏置

        Args:
            initial_weight: 偏置权重，控制SPEA2强度偏置的影响强度
            k_nearest: k-最近邻的k值（用于计算局部密度）
            strength_weight: Pareto强度权重（控制支配关系的重要性）
            density_weight: 密度权重（控制局部稀疏性的重要性）
            distance_metric: 距离度量方式
                            - 'euclidean': 欧几里得距离
                            - 'manhattan': 曼哈顿距离
            adaptive: 是否自适应调整权重
        """
        super().__init__("spea2_strength", initial_weight, adaptive)

        # SPEA2核心参数
        self.k_nearest = k_nearest                               # k-最近邻的k值
        self.strength_weight = strength_weight                    # 强度权重
        self.density_weight = density_weight                      # 密度权重
        self.distance_metric = distance_metric                    # 距离度量

        # 历史记录（用于分析和调试）
        self.strength_history = []                                # 强度历史
        self.density_history = []                                 # 密度历史
        self.fitness_history = []                                 # 适应度历史

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算 SPEA2 强度偏置值

        核心算法：
        1. 计算Pareto强度（个体支配的其他个体数量）
        2. 计算k-最近邻距离（局部密度）
        3. 结合强度和密度计算适应度
        4. 转换为偏置值

        Args:
            x: 被评估的个体（决策变量向量）
            context: 优化上下文，需要包含种群和目标信息

        Returns:
            SPEA2 强度偏置值（负值表示奖励，正值表示惩罚）

        Note:
            上下文需要提供：
            - context.population: 当前种群
            - context.metrics['objectives']: 当前个体的多目标值
            - context.metrics['population_objectives']: 种群的多目标值
        """
        # 获取必要信息
        population = context.population
        objectives = context.metrics.get('objectives', None)
        population_objectives = context.metrics.get('population_objectives', None)

        if not population or objectives is None or population_objectives is None:
            return 0.0

        objectives = np.asarray(objectives)
        population_objectives = np.asarray(population_objectives)

        # 1. 计算Pareto强度
        strength = self._compute_strength(objectives, population_objectives)

        # 2. 计算k-最近邻距离
        density = self._compute_density(objectives, population_objectives)

        # 记录历史
        self.strength_history.append(strength)
        self.density_history.append(density)

        # 3. 计算适应度（SPEA2方式）
        # 适应度 = 强度分量 + 密度分量
        fitness = self.strength_weight * strength + self.density_weight * density
        self.fitness_history.append(fitness)

        # 4. 转换为偏置
        # 在SPEA2中，适应度越小越好
        # 负偏置 = 奖励（适应度低）
        bias_value = fitness * self.weight

        return bias_value

    def _compute_strength(self, objectives: np.ndarray, population_objectives: np.ndarray) -> float:
        """
        计算Pareto强度

        强度 = 个体支配的其他个体数量 / (种群大小 + 1)

        Args:
            objectives: 当前个体的目标值
            population_objectives: 种群中所有个体的目标值

        Returns:
            Pareto强度值（越小越好，0表示非支配解）
        """
        # 计算当前个体支配了多少其他个体
        dominated_count = 0

        for other_objectives in population_objectives:
            if self._dominates(objectives, other_objectives):
                dominated_count += 1

        # 强度 = 支配的个体数 / (种群大小 + 1)
        population_size = len(population_objectives)
        strength = dominated_count / (population_size + 1)

        # 取负值，因为支配越多越好（应该给予负偏置奖励）
        return -strength

    def _dominates(self, obj1: np.ndarray, obj2: np.ndarray) -> bool:
        """
        判断obj1是否支配obj2

        Pareto支配定义：
        - obj1在所有目标上都不劣于obj2
        - obj1至少在一个目标上优于obj2

        Args:
            obj1: 个体1的目标值
            obj2: 个体2的目标值

        Returns:
            True if obj1 dominates obj2
        """
        # 至少有一个目标更好
        better_in_any = np.any(obj1 < obj2)

        # 所有目标都不更差
        not_worse_in_all = np.all(obj1 <= obj2)

        return better_in_any and not_worse_in_all

    def _compute_density(self, objectives: np.ndarray, population_objectives: np.ndarray) -> float:
        """
        计算k-最近邻距离（局部密度）

        密度 = 1 / (到第k个最近邻居的距离 + 2)

        Args:
            objectives: 当前个体的目标值
            population_objectives: 种群中所有个体的目标值

        Returns:
            密度值（越小越好，表示在稀疏区域）
        """
        # 计算到所有其他个体的距离
        distances = []

        for other_objectives in population_objectives:
            if self.distance_metric == 'euclidean':
                dist = np.linalg.norm(objectives - other_objectives)
            else:  # manhattan
                dist = np.sum(np.abs(objectives - other_objectives))

            distances.append(dist)

        # 排序并找到第k个最近距离
        distances.sort()
        kth_distance = distances[min(self.k_nearest, len(distances) - 1)]

        # 密度 = 1 / (kth_distance + 2)
        # 取负值，因为距离越大越好（应该给予负偏置奖励）
        density = -1.0 / (kth_distance + 2.0)

        return density

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取 SPEA2 强度偏置统计信息

        Returns:
            包含各种统计指标的字典
        """
        if not self.fitness_history:
            return {
                'k_nearest': self.k_nearest,
                'strength_weight': self.strength_weight,
                'density_weight': self.density_weight,
                'avg_fitness': 0.0,
                'best_fitness': 0.0
            }

        return {
            'k_nearest': self.k_nearest,                                # k值
            'strength_weight': self.strength_weight,                     # 强度权重
            'density_weight': self.density_weight,                       # 密度权重
            'avg_strength': float(np.mean(self.strength_history)),       # 平均强度
            'avg_density': float(np.mean(self.density_history)),         # 平均密度
            'avg_fitness': float(np.mean(self.fitness_history)),         # 平均适应度
            'best_fitness': float(np.min(self.fitness_history)),         # 最好适应度
            'worst_fitness': float(np.max(self.fitness_history)),        # 最差适应度
            'recent_fitness': self.fitness_history[-10:]                 # 最近10次适应度
        }


class AdaptiveSPEA2Bias(SPEA2StrengthBias):
    """
    自适应 SPEA2 强度偏置

    在标准SPEA2偏置基础上增加自适应能力：
    - 根据收敛状态动态调整k值
    - 自动平衡强度和密度权重
    - 基于Pareto前沿分布调整策略
    """

    def __init__(
        self,
        initial_weight: float = 0.5,
        k_nearest: int = 5,
        strength_weight: float = 0.6,
        density_weight: float = 0.4,
        adaptation_window: int = 50,
        distance_metric: Literal['euclidean', 'manhattan'] = 'euclidean'
    ):
        """
        初始化自适应 SPEA2 偏置

        Args:
            initial_weight: 偏置权重
            k_nearest: 初始k值
            strength_weight: 初始强度权重
            density_weight: 初始密度权重
            adaptation_window: 自适应调整窗口大小
            distance_metric: 距离度量方式
        """
        super().__init__(initial_weight, k_nearest, strength_weight, density_weight, distance_metric, adaptive=True)

        self.adaptation_window = adaptation_window                    # 自适应窗口
        self.initial_k_nearest = k_nearest                           # 初始k值
        self.initial_strength_weight = strength_weight                # 初始强度权重
        self.initial_density_weight = density_weight                  # 初始密度权重

        # 自适应统计
        self.convergence_indicator = []                               # 收敛指标

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算自适应 SPEA2 强度偏置值

        在标准SPEA2计算基础上增加自适应调整逻辑。

        Args:
            x: 被评估的个体
            context: 优化上下文

        Returns:
            自适应调整后的SPEA2偏置值
        """
        # 执行标准SPEA2计算
        bias_value = super().compute(x, context)

        # 记录收敛指标
        if self.fitness_history:
            self.convergence_indicator.append(self.fitness_history[-1])

        # 自适应调整参数
        if len(self.convergence_indicator) >= self.adaptation_window:
            self._adapt_parameters()

        return bias_value

    def _adapt_parameters(self):
        """
        自适应调整参数

        根据收敛历史调整k值和权重分配。
        """
        if len(self.convergence_indicator) < self.adaptation_window:
            return

        # 计算近期适应度的标准差
        recent_fitness = np.array(self.convergence_indicator[-self.adaptation_window:])
        fitness_std = np.std(recent_fitness)
        fitness_mean = np.mean(recent_fitness)

        # 根据收敛情况调整参数
        if fitness_std < 0.1 * fitness_mean:
            # 收敛良好，增加k值（更关注全局分布）
            self.k_nearest = min(self.k_nearest + 1, 20)
            # 降低强度权重，增加密度权重（更关注多样性）
            self.strength_weight = max(0.3, self.strength_weight - 0.05)
            self.density_weight = min(0.7, self.density_weight + 0.05)
        elif fitness_std > 0.5 * fitness_mean:
            # 多样性过大，减少k值（更关注局部）
            self.k_nearest = max(self.k_nearest - 1, 3)
            # 增加强度权重，降低密度权重（更关注收敛）
            self.strength_weight = min(0.8, self.strength_weight + 0.05)
            self.density_weight = max(0.2, self.density_weight - 0.05)

        # 重置收敛历史
        self.convergence_indicator = []

    def reset_to_initial_parameters(self):
        """重置参数到初始值"""
        self.k_nearest = self.initial_k_nearest
        self.strength_weight = self.initial_strength_weight
        self.density_weight = self.initial_density_weight
        self.convergence_indicator = []
        self.strength_history = []
        self.density_history = []
        self.fitness_history = []


class HybridSPEA2NSGA2Bias(SPEA2StrengthBias):
    """
    混合 SPEA2-NSGA2 偏置

    结合SPEA2的强度/密度概念和NSGA2的拥挤距离概念：
    - 使用SPEA2的强度计算支配关系
    - 结合SPEA2的k-最近邻密度和NSGA2的拥挤距离
    - 提供更精细的分布性评估
    - 适用于复杂Pareto前沿问题
    """

    def __init__(
        self,
        initial_weight: float = 0.5,
        k_nearest: int = 5,
        strength_weight: float = 0.4,
        spea2_density_weight: float = 0.3,
        nsga2_crowding_weight: float = 0.3,
        distance_metric: Literal['euclidean', 'manhattan'] = 'euclidean'
    ):
        """
        初始化混合 SPEA2-NSGA2 偏置

        Args:
            initial_weight: 偏置权重
            k_nearest: k-最近邻的k值
            strength_weight: SPEA2强度权重
            spea2_density_weight: SPEA2密度权重
            nsga2_crowding_weight: NSGA2拥挤距离权重
            distance_metric: 距离度量方式
        """
        super().__init__(initial_weight, k_nearest, strength_weight,
                        spea2_density_weight, distance_metric, adaptive=True)

        self.nsga2_crowding_weight = nsga2_crowding_weight          # NSGA2拥挤距离权重
        self.spea2_density_weight = spea2_density_weight            # SPEA2密度权重

        # 重新归一化权重
        total_weight = strength_weight + spea2_density_weight + nsga2_crowding_weight
        self.strength_weight = strength_weight / total_weight
        self.spea2_density_weight = spea2_density_weight / total_weight
        self.nsga2_crowding_weight = nsga2_crowding_weight / total_weight

        # 拥挤距离历史
        self.crowding_history = []

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算混合 SPEA2-NSGA2 偏置值

        结合SPEA2强度、SPEA2密度和NSGA2拥挤距离。

        Args:
            x: 被评估的个体
            context: 优化上下文

        Returns:
            混合偏置值
        """
        # 计算SPEA2强度
        objectives = context.metrics.get('objectives', None)
        population_objectives = context.metrics.get('population_objectives', None)

        if objectives is None or population_objectives is None:
            return 0.0

        objectives = np.asarray(objectives)
        population_objectives = np.asarray(population_objectives)

        strength = self._compute_strength(objectives, population_objectives)

        # 计算SPEA2密度
        spea2_density = self._compute_density(objectives, population_objectives)

        # 计算NSGA2拥挤距离
        crowding_distance = context.metrics.get('crowding_distance', 0.0)
        self.crowding_history.append(crowding_distance)
        # 负值，因为拥挤距离越大越好
        nsga2_crowding = -crowding_distance

        # 组合三个分量
        fitness = (self.strength_weight * strength +
                  self.spea2_density_weight * spea2_density +
                  self.nsga2_crowding_weight * nsga2_crowding)

        self.fitness_history.append(fitness)

        # 转换为偏置
        bias_value = fitness * self.weight

        return bias_value

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取混合偏置统计信息

        Returns:
            统计信息字典
        """
        base_stats = super().get_statistics()
        base_stats['nsga2_crowding_weight'] = self.nsga2_crowding_weight
        base_stats['avg_crowding_distance'] = float(np.mean(self.crowding_history)) if self.crowding_history else 0.0
        return base_stats
