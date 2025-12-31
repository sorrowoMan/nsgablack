"""
差分进化偏置实现模块

该模块实现差分进化（Differential Evolution, DE）算法思想的偏置化，将 DE 概念注入到任何优化算法中：
- 差分变异向量转换为偏置值
- DE 的全局探索能力注入
- 算法无关性的 DE 特性注入
- 与其他偏置的无缝组合

通过偏置系统，任何算法（GA、PSO、NSGA-II等）都可以获得 DE 的强大全局搜索能力。

DE 核心思想：v = x_r1 + F * (x_r2 - x_r3)
转换为偏置：鼓励个体沿差分方向探索
"""

import numpy as np
from typing import List, Dict, Any, Optional
from ..core.base import AlgorithmicBias, OptimizationContext


class DifferentialEvolutionBias(AlgorithmicBias):
    """
    差分进化偏置 - 将 DE 的差分变异思想注入到任何算法

    核心思想是将 DE 的差分变异向量转换为可计算的偏置值：
    - 差分向量 (x_r2 - x_r3) 表示种群中的差异信息
    - 沿着差分方向探索可以获得新的有希望区域
    - 大的差分向量表示高多样性，给予奖励

    通过这种转换，任何优化算法都能获得 DE 的全局探索能力。
    """

    def __init__(
        self,
        initial_weight: float = 0.1,
        F: float = 0.8,                    # 差分权重 [0, 2]
        strategy: str = "rand",            # 变体策略: rand/best
        use_adaptive_F: bool = False
    ):
        """
        初始化差分进化偏置

        Args:
            initial_weight: 初始偏置权重
            F: 差分权重因子，控制差分向量的大小
                - F=0.5: 保守探索
                - F=0.8: 标准DE推荐值
                - F=1.2: 激进探索
            strategy: 变体策略
                - 'rand': 随机选择基向量（更多探索）
                - 'best': 使用最优个体作为基向量（更快收敛）
            use_adaptive_F: 是否自适应调整 F
        """
        super().__init__("differential_evolution", initial_weight, adaptive=True)

        # DE 核心参数
        self.F = F                                    # 差分权重
        self.strategy = strategy                      # 变体策略
        self.use_adaptive_F = use_adaptive_F          # 自适应 F
        self.initial_F = F                            # 记录初始 F

        # 历史记录
        self.diff_magnitude_history = []              # 差分向量大小历史
        self.exploration_direction_history = []       # 探索方向历史

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算差分进化偏置值

        核心算法：
        1. 从种群中随机选择3个不同个体
        2. 计算差分向量：diff = x_r2 - x_r3
        3. 应用 DE 公式：v = x_r1 + F * diff
        4. 转换为偏置值（鼓励沿差分方向探索）

        Args:
            x: 被评估的个体
            context: 优化上下文，需要包含种群信息

        Returns:
            DE 偏置值（负值表示奖励，正值表示惩罚）

        Note:
            上下文需要提供：
            - context.population: 当前种群
            - context.fitness: 适应度值（可选，用于 best 策略）
        """
        population = context.population

        # 种群太小，无法计算差分
        if len(population) < 4:
            return 0.0

        # 自适应调整 F
        if self.use_adaptive_F:
            self._adapt_F(context)

        # 选择基向量
        if self.strategy == "best" and context.fitness is not None:
            # 使用最优个体作为基向量
            best_idx = np.argmin(context.fitness)
            x_r1 = population[best_idx]
        else:
            # 随机选择基向量（不包括当前个体 x）
            indices = [i for i in range(len(population)) if not np.array_equal(population[i], x)]
            if not indices:
                return 0.0
            r1_idx = np.random.choice(indices)
            x_r1 = population[r1_idx]

        # 选择另外两个不同的个体（不包括 x_r1 和 x）
        remaining_indices = [
            i for i in range(len(population))
            if not np.array_equal(population[i], x_r1) and not np.array_equal(population[i], x)
        ]

        if len(remaining_indices) < 2:
            return 0.0

        r2_idx, r3_idx = np.random.choice(remaining_indices, 2, replace=False)
        x_r2 = population[r2_idx]
        x_r3 = population[r3_idx]

        # ========== 计算差分向量 ==========
        diff_vector = x_r2 - x_r3
        diff_magnitude = np.linalg.norm(diff_vector)

        # 记录历史
        self.diff_magnitude_history.append(diff_magnitude)

        # ========== 转换为偏置值 ==========
        # DE 的核心思想：沿差分方向探索
        # 差分向量越大，表示种群多样性越高，应该给予奖励

        # 计算当前个体到差分向量的距离
        # 如果个体沿差分方向移动，应该给予奖励
        direction_to_explore = self.F * diff_vector

        # 计算当前个体沿探索方向的投影
        if np.linalg.norm(direction_to_explore) > 0:
            # 标准化方向
            normalized_direction = direction_to_explore / np.linalg.norm(direction_to_explore)

            # 计算投影（简化：使用距离中心的偏移）
            population_center = np.mean(population, axis=0)
            offset_from_center = x - population_center
            projection = np.dot(offset_from_center, normalized_direction)

            # 偏置值：鼓励沿差分方向探索
            # 正投影 → 负偏置（奖励）
            # 负投影 → 正偏置（惩罚）
            bias_value = -projection * 0.1
        else:
            bias_value = 0.0

        # 额外的多样性奖励
        # 差分向量大小表示种群多样性
        diversity_bonus = diff_magnitude * 0.05
        bias_value -= diversity_bonus

        return bias_value

    def _adapt_F(self, context: OptimizationContext):
        """
        自适应调整 F 值

        策略：
        - 优化早期：F 较大（强调探索）
        - 优化后期：F 较小（强调开发）
        """
        generation = context.generation
        max_generations = context.metrics.get('max_generations', 100)
        progress = generation / max_generations if max_generations > 0 else 0

        # F 从 initial_F 逐渐降低到 0.5
        target_F = self.initial_F * (1 - 0.5 * progress)
        self.F = max(0.5, target_F)

    def generate_trial_vector(
        self,
        x: np.ndarray,
        population: List[np.ndarray],
        CR: float = 0.9
    ) -> np.ndarray:
        """
        生成 DE 试验向量（辅助方法）

        这个方法可以直接用于生成新的候选解，完全模拟 DE 的行为。

        Args:
            x: 目标向量
            population: 当前种群
            CR: 交叉概率

        Returns:
            试验向量（新的候选解）
        """
        if len(population) < 4:
            return x.copy()

        # 选择基向量
        if self.strategy == "best":
            # 需要适应度信息
            indices = list(range(len(population)))
            r1_idx = np.random.choice(indices)
        else:
            indices = [i for i in range(len(population)) if not np.array_equal(population[i], x)]
            if not indices:
                return x.copy()
            r1_idx = np.random.choice(indices)

        # 选择另外两个个体
        remaining_indices = [
            i for i in range(len(population))
            if i != r1_idx and not np.array_equal(population[i], x)
        ]

        if len(remaining_indices) < 2:
            return x.copy()

        r2_idx, r3_idx = np.random.choice(remaining_indices, 2, replace=False)

        # 差分变异
        donor = population[r1_idx] + self.F * (population[r2_idx] - population[r3_idx])

        # 交叉
        cross_points = np.random.rand(len(x)) < CR
        if not np.any(cross_points):
            cross_points[np.random.randint(len(x))] = True

        trial = np.where(cross_points, donor, x)

        return trial

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取 DE 偏置统计信息

        Returns:
            包含各种统计指标的字典
        """
        if not self.diff_magnitude_history:
            return {
                'current_F': self.F,
                'initial_F': self.initial_F,
                'avg_diff_magnitude': 0,
                'strategy': self.strategy
            }

        return {
            'current_F': self.F,                                    # 当前 F 值
            'initial_F': self.initial_F,                           # 初始 F 值
            'avg_diff_magnitude': np.mean(self.diff_magnitude_history),  # 平均差分向量大小
            'last_diff_magnitude': self.diff_magnitude_history[-1],      # 最近差分向量大小
            'strategy': self.strategy,                             # 变体策略
            'diff_history': self.diff_magnitude_history[-10:]      # 最近10次差分记录
        }


class AdaptiveDEBias(DifferentialEvolutionBias):
    """
    自适应差分进化偏置

    在标准 DE 偏置基础上增加自适应能力：
    - 根据种群多样性自动调整 F
    - 在优化停滞时重新随机化探索方向
    - 基于成功率动态选择策略
    """

    def __init__(
        self,
        initial_weight: float = 0.1,
        F: float = 0.8,
        strategy: str = "rand",
        adaptation_window: int = 50
    ):
        """
        初始化自适应 DE 偏置

        Args:
            initial_weight: 初始权重
            F: 差分权重
            strategy: 变体策略
            adaptation_window: 自适应调整窗口
        """
        super().__init__(initial_weight, F, strategy, use_adaptive_F=True)

        self.adaptation_window = adaptation_window       # 自适应窗口
        self.success_history = []                        # 成功历史

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算自适应 DE 偏置值

        在标准 DE 计算基础上增加自适应调整逻辑。
        """
        # 执行标准 DE 计算
        bias_value = super().compute(x, context)

        # 更新自适应统计
        if bias_value < 0:  # 负偏置表示奖励
            self.success_history.append(1)
        else:
            self.success_history.append(0)

        # 保持窗口大小
        if len(self.success_history) > self.adaptation_window:
            self.success_history.pop(0)

        # 自适应调整策略
        if len(self.success_history) >= self.adaptation_window:
            self._adapt_strategy()

        return bias_value

    def _adapt_strategy(self):
        """
        自适应调整策略

        根据成功率在 rand 和 best 策略之间切换
        """
        success_rate = sum(self.success_history) / len(self.success_history)

        if success_rate < 0.3:
            # 成功率低，切换到更多探索
            self.strategy = "rand"
            self.F = min(2.0, self.F * 1.1)
        elif success_rate > 0.7:
            # 成功率高，可以更快收敛
            self.strategy = "best"
            self.F = max(0.5, self.F * 0.9)


class MultiObjectiveDEBias(DifferentialEvolutionBias):
    """
    多目标差分进化偏置

    专门针对多目标优化问题的 DE 偏置：
    - 处理多目标差分变异
    - Pareto 支配关系考虑
    - 拥挤度信息集成
    """

    def __init__(
        self,
        initial_weight: float = 0.1,
        F: float = 0.8,
        crowding_weight: float = 0.5
    ):
        """
        初始化多目标 DE 偏置

        Args:
            initial_weight: 初始权重
            F: 差分权重
            crowding_weight: 拥挤度权重
        """
        super().__init__(initial_weight, F, strategy="rand")
        self.crowding_weight = crowding_weight

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算多目标 DE 偏置值

        Args:
            x: 被评估的个体
            context: 优化上下文

        Returns:
            多目标 DE 偏置值
        """
        # 执行标准 DE 计算
        bias_value = super().compute(x, context)

        # 添加拥挤度奖励
        crowding_distance = context.metrics.get('crowding_distance', 0.0)
        if crowding_distance > 0:
            # 拥挤度大的区域，给予额外奖励
            crowding_bonus = -crowding_distance * self.crowding_weight * 0.1
            bias_value += crowding_bonus

        return bias_value


# ========== 工具函数 ==========

def generate_de_trial(
    x: np.ndarray,
    population: List[np.ndarray],
    F: float = 0.8,
    CR: float = 0.9,
    strategy: str = "rand"
) -> np.ndarray:
    """
    生成 DE 试验向量的便捷函数

    Args:
        x: 目标向量
        population: 当前种群
        F: 差分权重
        CR: 交叉概率
        strategy: 变体策略

    Returns:
        试验向量
    """
    if len(population) < 4:
        return x.copy()

    # 选择基向量
    if strategy == "best":
        r1_idx = np.random.choice(len(population))
    else:
        indices = [i for i in range(len(population)) if not np.array_equal(population[i], x)]
        if not indices:
            return x.copy()
        r1_idx = np.random.choice(indices)

    # 选择另外两个个体
    remaining_indices = [
        i for i in range(len(population))
        if i != r1_idx and not np.array_equal(population[i], x)
    ]

    if len(remaining_indices) < 2:
        return x.copy()

    r2_idx, r3_idx = np.random.choice(remaining_indices, 2, replace=False)

    # 差分变异
    donor = population[r1_idx] + F * (population[r2_idx] - population[r3_idx])

    # 交叉
    cross_points = np.random.rand(len(x)) < CR
    if not np.any(cross_points):
        cross_points[np.random.randint(len(x))] = True

    trial = np.where(cross_points, donor, x)

    return trial
