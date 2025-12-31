"""
NSGA-II 偏置实现模块

该模块实现 NSGA-II 算法思想的偏置化，将 NSGA-II 概念注入到任何优化算法中：
- Pareto 支配关系转换为偏置值
- 非支配排序 rank 转换为偏置值
- 拥挤距离转换为偏置值
- 算法无关性的 NSGA-II 特性注入
- 与其他偏置的无缝组合

通过偏置系统，任何算法（GA、PSO、SA、DE等）都可以获得 NSGA-II 的多目标优化能力。
"""

import numpy as np
from typing import List, Dict, Any, Optional
from ..core.base import AlgorithmicBias, OptimizationContext


class NSGA2Bias(AlgorithmicBias):
    """
    NSGA-II 偏置 - 将 NSGA-II 概念注入到任何算法

    核心思想是将 NSGA-II 的核心概念转换为可计算的偏置值：
    - Pareto rank：rank越低（越好）给予负偏置（奖励）
    - Crowding distance：拥挤距离越大（越稀疏）给予负偏置（奖励）
    - Pareto dominance：被支配个体给予正偏置（惩罚）

    通过这种转换，任何单目标优化算法都能获得 NSGA-II 的多目标特性。
    """

    def __init__(
        self,
        initial_weight: float = 0.1,
        rank_weight: float = 0.5,
        crowding_weight: float = 0.3,
        dominance_weight: float = 0.2
    ):
        """
        初始化 NSGA-II 偏置

        Args:
            initial_weight: 初始偏置权重
            rank_weight: Pareto rank 的权重（越低越好）
            crowding_weight: 拥挤距离的权重（越大越好，保持多样性）
            dominance_weight: Pareto 支配关系的权重
        """
        super().__init__("nsga2", initial_weight, adaptive=True)

        # NSGA-II 核心参数
        self.rank_weight = rank_weight              # Rank 权重
        self.crowding_weight = crowding_weight      # 拥挤距离权重
        self.dominance_weight = dominance_weight    # 支配关系权重

        # 历史记录（用于分析和调试）
        self.rank_history = []                      # Rank 历史
        self.crowding_history = []                  # 拥挤距离历史
        self.dominance_history = []                # 支配关系历史

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算 NSGA-II 偏置值

        核心算法：
        1. 获取 Pareto rank（非支配排序层级）
        2. 获取拥挤距离（在目标空间中的稀疏程度）
        3. 计算 Pareto 支配关系
        4. 转换为偏置值

        Args:
            x: 被评估的个体
            context: 优化上下文，需要包含多目标信息

        Returns:
            NSGA-II 偏置值（负值表示奖励，正值表示惩罚）

        Note:
            上下文需要提供：
            - context.metrics['pareto_rank']: Pareto rank（0是最好的）
            - context.metrics['crowding_distance']: 拥挤距离
            - context.metrics['is_dominated']: 是否被其他解支配
        """
        # 获取 NSGA-II 相关信息
        pareto_rank = context.metrics.get('pareto_rank', 0)
        crowding_distance = context.metrics.get('crowding_distance', 0.0)
        is_dominated = context.metrics.get('is_dominated', False)

        # 记录历史
        self.rank_history.append(pareto_rank)
        self.crowding_history.append(crowding_distance)
        self.dominance_history.append(is_dominated)

        # ========== 转换为偏置值 ==========
        bias_value = 0.0

        # 1. Pareto rank 偏置：rank 越低越好
        # rank=0（非支配）→ 负偏置（奖励）
        # rank=1,2,...（被支配）→ 正偏置（惩罚）
        rank_bias = pareto_rank * self.rank_weight
        bias_value += rank_bias

        # 2. 拥挤距离偏置：距离越大越好（保持多样性）
        # 大拥挤距离 → 负偏置（奖励，鼓励多样性）
        # 小拥挤距离 → 正偏置（惩罚，避免聚集）
        if crowding_distance > 0:
            # 归一化拥挤距离（假设最大值约为1）
            crowding_bias = -crowding_distance * self.crowding_weight
        else:
            # 边界个体或无法计算，给予奖励
            crowding_bias = -self.crowding_weight
        bias_value += crowding_bias

        # 3. Pareto 支配关系偏置
        # 被支配 → 正偏置（惩罚）
        # 非支配 → 负偏置（奖励）
        if is_dominated:
            dominance_bias = self.dominance_weight
        else:
            dominance_bias = -self.dominance_weight * 0.5
        bias_value += dominance_bias

        return bias_value

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取 NSGA-II 偏置统计信息

        Returns:
            包含各种统计指标的字典
        """
        if not self.rank_history:
            return {
                'avg_rank': 0,
                'best_rank': 0,
                'avg_crowding': 0,
                'domination_rate': 0
            }

        return {
            'avg_rank': np.mean(self.rank_history),           # 平均 rank
            'best_rank': min(self.rank_history),              # 最好 rank
            'worst_rank': max(self.rank_history),             # 最差 rank
            'avg_crowding': np.mean(self.crowding_history),  # 平均拥挤距离
            'domination_rate': sum(self.dominance_history) / len(self.dominance_history),  # 被支配率
            'rank_history': self.rank_history[-10:],          # 最近10次 rank 记录
            'crowding_history': self.crowding_history[-10:]   # 最近10次拥挤距离记录
        }


class AdaptiveNSGA2Bias(NSGA2Bias):
    """
    自适应 NSGA-II 偏置

    在标准 NSGA-II 偏置基础上增加自适应能力：
    - 根据优化进展动态调整 rank/crowding 权重
    - 早期强调 rank（收敛），后期强调 crowding（多样性）
    - 基于 Pareto 前沿质量自适应调整
    """

    def __init__(
        self,
        initial_weight: float = 0.1,
        rank_weight: float = 0.5,
        crowding_weight: float = 0.3,
        dominance_weight: float = 0.2,
        adaptation_rate: float = 0.01
    ):
        """
        初始化自适应 NSGA-II 偏置

        Args:
            initial_weight: 初始权重
            rank_weight: 初始 rank 权重
            crowding_weight: 初始拥挤距离权重
            dominance_weight: 支配关系权重
            adaptation_rate: 自适应调整率
        """
        super().__init__(initial_weight, rank_weight, crowding_weight, dominance_weight)

        self.adaptation_rate = adaptation_rate              # 自适应率
        self.initial_rank_weight = rank_weight              # 初始 rank 权重
        self.initial_crowding_weight = crowding_weight      # 初始拥挤权重

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算自适应 NSGA-II 偏置值

        在标准 NSGA-II 计算基础上增加自适应调整逻辑。

        Args:
            x: 被评估的个体
            context: 优化上下文

        Returns:
            自适应调整后的 NSGA-II 偏置值
        """
        # 自适应调整权重
        self._adapt_weights(context)

        # 执行标准 NSGA-II 计算
        bias_value = super().compute(x, context)

        return bias_value

    def _adapt_weights(self, context: OptimizationContext):
        """
        自适应调整 rank 和 crowding 权重

        策略：
        - 优化早期（generation < 30%）：强调 rank（快速收敛）
        - 优化中期（30% < generation < 70%）：平衡
        - 优化后期（generation > 70%）：强调 crowding（保持多样性）
        """
        generation = context.generation
        max_generations = context.metrics.get('max_generations', 100)
        progress = generation / max_generations if max_generations > 0 else 0

        if progress < 0.3:
            # 早期：强调 rank
            target_rank_weight = 0.7
            target_crowding_weight = 0.2
        elif progress < 0.7:
            # 中期：平衡
            target_rank_weight = 0.5
            target_crowding_weight = 0.4
        else:
            # 后期：强调 crowding
            target_rank_weight = 0.3
            target_crowding_weight = 0.6

        # 平滑调整权重
        self.rank_weight += (target_rank_weight - self.rank_weight) * self.adaptation_rate
        self.crowding_weight += (target_crowding_weight - self.crowding_weight) * self.adaptation_rate


class DiversityPreservingNSGA2Bias(NSGA2Bias):
    """
    多样性保持的 NSGA-II 偏置

    专门针对强维持多样性的 NSGA-II 变体：
    - 增强的拥挤距离计算
    - 惩罚聚集的个体
    - 奖励稀疏区域的个体
    - 动态调整多样性压力
    """

    def __init__(
        self,
        initial_weight: float = 0.1,
        rank_weight: float = 0.3,
        crowding_weight: float = 0.5,  # 更高的拥挤权重
        diversity_threshold: float = 0.1
    ):
        """
        初始化多样性保持 NSGA-II 偏置

        Args:
            initial_weight: 初始权重
            rank_weight: Rank 权重（降低）
            crowding_weight: 拥挤距离权重（提高）
            diversity_threshold: 多样性阈值
        """
        super().__init__(initial_weight, rank_weight, crowding_weight)
        self.diversity_threshold = diversity_threshold

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算多样性保持的 NSGA-II 偏置值

        Args:
            x: 被评估的个体
            context: 优化上下文

        Returns:
            强调多样性的 NSGA-II 偏置值
        """
        # 获取基础信息
        pareto_rank = context.metrics.get('pareto_rank', 0)
        crowding_distance = context.metrics.get('crowding_distance', 0.0)
        is_dominated = context.metrics.get('is_dominated', False)

        # 计算多样性奖励
        diversity_bonus = 0.0

        # 如果拥挤距离很小（聚集），给予额外惩罚
        if crowding_distance < self.diversity_threshold:
            diversity_bonus = self.crowding_weight  # 惩罚聚集
        # 如果拥挤距离很大（稀疏），给予额外奖励
        elif crowding_distance > self.diversity_threshold * 2:
            diversity_bonus = -self.crowding_weight * 0.5  # 奖励稀疏

        # 基础偏置
        bias_value = super().compute(x, context)

        # 应用多样性奖励
        bias_value += diversity_bonus

        return bias_value


# ========== 工具函数 ==========

def compute_pareto_rank(
    individual_objectives: List[float],
    all_objectives: List[List[float]]
) -> int:
    """
    计算个体的 Pareto rank

    Args:
        individual_objectives: 个体的目标值
        all_objectives: 所有个体的目标值

    Returns:
        Pareto rank（0是最好的非支配解）
    """
    rank = 0
    current_front = [individual_objectives]

    while True:
        # 找到当前 front 的支配集
        dominated = []
        for obj in all_objectives:
            if obj in current_front:
                continue
            # 检查是否被 front 中的任何个体支配
            is_dominated = any(
                _dominates(front_obj, obj)
                for front_obj in current_front
            )
            if is_dominated:
                dominated.append(obj)

        if not dominated:
            # 没有更多被支配的个体，返回当前 rank
            return rank

        # 下一层 front
        current_front = dominated
        rank += 1


def compute_crowding_distance(
    individual_objectives: List[float],
    front_objectives: List[List[float]]
) -> float:
    """
    计算个体在 Pareto front 中的拥挤距离

    Args:
        individual_objectives: 个体的目标值
        front_objectives: 同一 front 中所有个体的目标值

    Returns:
        拥挤距离（越大表示周围个体越少）
    """
    if len(front_objectives) <= 2:
        # 边界个体或 front 太小
        return float('inf')

    num_objectives = len(individual_objectives)
    crowding_distance = 0.0

    for m in range(num_objectives):
        # 按第 m 个目标排序
        sorted_indices = sorted(
            range(len(front_objectives)),
            key=lambda i: front_objectives[i][m]
        )

        # 计算目标范围
        obj_min = front_objectives[sorted_indices[0]][m]
        obj_max = front_objectives[sorted_indices[-1]][m]
        obj_range = obj_max - obj_min

        if obj_range == 0:
            continue

        # 找到当前个体的位置
        for idx, sorted_idx in enumerate(sorted_indices):
            if front_objectives[sorted_idx] == individual_objectives:
                if idx == 0 or idx == len(sorted_indices) - 1:
                    # 边界个体
                    return float('inf')
                else:
                    # 中间个体
                    distance = (front_objectives[sorted_indices[idx + 1]][m] -
                              front_objectives[sorted_indices[idx - 1]][m]) / obj_range
                    crowding_distance += distance
                break

    return crowding_distance


def _dominates(obj1: List[float], obj2: List[float]) -> bool:
    """
    判断 obj1 是否支配 obj2

    Args:
        obj1: 目标值1
        obj2: 目标值2

    Returns:
        True 如果 obj1 支配 obj2
    """
    at_least_one_better = False
    for o1, o2 in zip(obj1, obj2):
        if o1 > o2:  # 假设最小化
            return False
        elif o1 < o2:
            at_least_one_better = True
    return at_least_one_better
