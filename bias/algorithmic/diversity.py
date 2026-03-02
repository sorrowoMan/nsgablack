"""
多样性偏置实现模块

该模块提供多种多样性维护偏置，用于：
- 防止种群早熟收敛
- 保持搜索空间探索能力
- 维护种群多样性水平
- 避免陷入局部最优

多样性是进化算法性能的关键因素，合理的多样性偏置能够显著改善优化效果。
"""

import numpy as np
from typing import List, Optional
from ..core.base import AlgorithmicBias, OptimizationContext


class DiversityBias(AlgorithmicBias):
    """
    标准多样性偏置 - 基于最小距离的多样性维护

    通过计算个体与种群中其他个体的最小距离来维护多样性：
    - 距离越大，多样性越好，给予正向偏置
    - 距离越小，多样性越差，给予负向偏置或无偏置
    - 支持多种距离度量方法

    适用场景：多模态优化、需要全局搜索的问题
    """
    context_requires = ("population_ref",)
    requires_metrics = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Algorithmic bias: reads metrics and outputs scalar guidance."


    def __init__(self, weight: float = 0.1, metric: str = 'euclidean'):
        """
        初始化多样性偏置

        Args:
            weight: 偏置权重，控制多样性引导强度
            metric: 距离度量方法
                  'euclidean' - 欧几里得距离
                  'manhattan' - 曼哈顿距离
                  'chebyshev' - 切比雪夫距离
        """
        super().__init__("diversity", weight, adaptive=True)
        self.metric = metric                                  # 距离度量方法
        self.diversity_history = []                           # 多样性历史记录

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算多样性偏置值

        Args:
            x: 被评估的个体
            context: 优化上下文

        Returns:
            多样性偏置值（距离越大值越大）
        """
        if len(context.population) == 0:
            return 0.0                                        # 无种群时返回0

        # 计算与种群中其他个体的最小距离
        distances = self._calculate_distances(x, context.population)

        if len(distances) > 0:
            min_dist = min(distances)
            # 距离越大，多样性越好
            diversity_value = min_dist

            # 记录多样性历史
            self.diversity_history.append(diversity_value)

            return diversity_value
        return 0.0

    def _calculate_distances(self, x: np.ndarray, population: List[np.ndarray]) -> List[float]:
        """
        计算个体x与种群中所有个体的距离

        Args:
            x: 目标个体
            population: 种群个体列表

        Returns:
            距离列表
        """
        distances = []
        for other in population:
            if not np.array_equal(x, other):                # 跳过自身
                if self.metric == 'euclidean':
                    dist = np.linalg.norm(x - other)      # 欧几里得距离
                elif self.metric == 'manhattan':
                    dist = np.sum(np.abs(x - other))       # 曼哈顿距离
                elif self.metric == 'chebyshev':
                    dist = np.max(np.abs(x - other))       # 切比雪夫距离
                else:
                    dist = np.linalg.norm(x - other)      # 默认欧几里得距离
                distances.append(dist)
        return distances

    def get_average_diversity(self) -> float:
        """
        获取历史平均多样性水平

        Returns:
            平均多样性值
        """
        if not self.diversity_history:
            return 0.0
        return np.mean(self.diversity_history)


class AdaptiveDiversityBias(AlgorithmicBias):
    """
    自适应多样性偏置 - 基于种群多样性水平动态调整

    根据当前种群多样性水平自适应调整偏置强度：
    - 多样性低时：增强多样性偏置
    - 多样性高时：减弱多样性偏置
    - 维持多样性在目标水平附近

    适用于动态变化的优化问题和需要平衡多样性的场景。
    """
    context_requires = ("population_ref",)
    requires_metrics = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Algorithmic bias: reads metrics and outputs scalar guidance."


    def __init__(
        self,
        weight: float = 0.15,
        target_diversity: float = 0.8,
        adaptation_rate: float = 0.1
    ):
        """
        初始化自适应多样性偏置

        Args:
            weight: 基础偏置权重
            target_diversity: 目标多样性水平
            adaptation_rate: 自适应调整速率
        """
        super().__init__("adaptive_diversity", weight, adaptive=True)
        self.target_diversity = target_diversity              # 目标多样性
        self.adaptation_rate = adaptation_rate                # 自适应速率
        self.current_diversity = 0.0                         # 当前多样性

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算自适应多样性偏置值

        Args:
            x: 被评估的个体
            context: 优化上下文

        Returns:
            自适应调整后的多样性偏置值
        """
        if len(context.population) < 2:
            return 0.0

        # 计算当前种群多样性
        self.current_diversity = self._calculate_population_diversity(context.population)

        # 根据多样性水平自适应调整权重
        if self.current_diversity < self.target_diversity:
            # 多样性不足 - 增强偏置权重
            adapted_weight = self.weight * (1 + self.adaptation_rate)
        else:
            # 多样性充足 - 减弱偏置权重
            adapted_weight = self.weight * (1 - self.adaptation_rate * 0.5)

        # 计算个体多样性贡献
        min_dist = self._calculate_individual_distance(x, context.population)
        return adapted_weight * min_dist

    def _calculate_population_diversity(self, population: List[np.ndarray]) -> float:
        """
        计算种群整体多样性

        使用平均成对距离作为多样性度量。

        Args:
            population: 种群

        Returns:
            种群多样性值
        """
        if len(population) < 2:
            return 0.0

        total_distance = 0.0
        count = 0

        for i, ind1 in enumerate(population):
            for ind2 in population[i+1:]:
                distance = np.linalg.norm(ind1 - ind2)
                total_distance += distance
                count += 1

        return total_distance / count if count > 0 else 0.0

    def _calculate_individual_distance(self, x: np.ndarray, population: List[np.ndarray]) -> float:
        """
        计算个体与种群的最小距离

        Args:
            x: 目标个体
            population: 种群

        Returns:
            最小距离
        """
        distances = [np.linalg.norm(x - other) for other in population if not np.array_equal(x, other)]
        return min(distances) if len(distances) > 0 else 0.0


class NicheDiversityBias(AlgorithmicBias):
    """
    生态位多样性偏置 - 基于生态位概念维护多样性

    将解空间划分为多个生态位，限制每个生态位中的个体数量：
    - 每个生态位最多容纳指定数量个体
    - 生态位满时施加惩罚
    - 生态位有空位时给予奖励

    适用于需要覆盖多个解空间区域的问题。
    """
    context_requires = ()
    requires_metrics = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Algorithmic bias: reads metrics and outputs scalar guidance."


    def __init__(
        self,
        weight: float = 0.2,
        niche_radius: float = 0.1,
        max_niche_size: int = 3
    ):
        """
        初始化生态位多样性偏置

        Args:
            weight: 偏置权重
            niche_radius: 生态位半径（确定生态位划分）
            max_niche_size: 每个生态位最大个体数
        """
        super().__init__("niche_diversity", weight, adaptive=True)
        self.niche_radius = niche_radius                       # 生态位半径
        self.max_niche_size = max_niche_size                   # 最大生态位大小
        self.niches = {}                                      # 生态位字典

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算生态位多样性偏置值

        Args:
            x: 被评估的个体
            context: 优化上下文

        Returns:
            生态位偏置值
        """
        # 查找或创建个体所属的生态位
        niche_id = self._find_niche(x)

        # 计算生态位中的个体数量
        niche_count = len(self.niches.get(niche_id, []))

        if niche_count >= self.max_niche_size:
            # 生态位已满 - 施加负向偏置
            return -self.weight * (niche_count - self.max_niche_size + 1)
        else:
            # 生态位有空位 - 施加正向偏置
            return self.weight * (1.0 - niche_count / self.max_niche_size)

    def _find_niche(self, x: np.ndarray) -> str:
        """
        根据个体位置确定其所属生态位

        通过将空间离散化来创建生态位。

        Args:
            x: 个体向量

        Returns:
            生态位标识符
        """
        # 将空间划分为网格，每个网格单元为一个生态位
        niche_coords = tuple(np.floor(x / self.niche_radius).astype(int))
        return str(niche_coords)

    def update_niches(self, population: List[np.ndarray]):
        """
        更新生态位分配

        Args:
            population: 当前种群
        """
        self.niches = {}
        for individual in population:
            niche_id = self._find_niche(individual)
            if niche_id not in self.niches:
                self.niches[niche_id] = []
            self.niches[niche_id].append(individual)


class CrowdingDistanceBias(AlgorithmicBias):
    """
    拥挤距离多样性偏置 - 基于拥挤距离概念的多样性维护

    使用拥挤距离概念来鼓励在拥挤程度低的区域探索：
    - 拥挤距离大：种群稀疏区域，给予正向偏置
    - 拥挤距离小：种群密集区域，给予负向偏置
    - 使用k最近邻距离计算拥挤程度

    适用于多目标优化和需要均匀分布解的问题。
    """
    context_requires = ("population_ref",)
    requires_metrics = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Algorithmic bias: reads metrics and outputs scalar guidance."


    def __init__(self, weight: float = 0.15):
        """
        初始化拥挤距离偏置

        Args:
            weight: 偏置权重
        """
        super().__init__("crowding_distance", weight, adaptive=True)

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算拥挤距离偏置值

        Args:
            x: 被评估的个体
            context: 优化上下文

        Returns:
            拥挤距离偏置值
        """
        if len(context.population) < 3:
            return 0.0

        # 计算个体的拥挤距离
        crowding_dist = self._calculate_crowding_distance(x, context.population)
        return self.weight * crowding_dist

    def _calculate_crowding_distance(self, x: np.ndarray, population: List[np.ndarray]) -> float:
        """
        计算个体的拥挤距离

        使用基于距离的拥挤距离计算方法。

        Args:
            x: 目标个体
            population: 种群

        Returns:
            拥挤距离值
        """
        # 计算到所有其他个体的距离
        distances = sorted([np.linalg.norm(x - other) for other in population if not np.array_equal(x, other)])

        if len(distances) < 2:
            return float('inf')                               # 个体唯一时距离无限大

        # 使用到k个最近邻居的距离之和作为拥挤距离
        k = min(3, len(distances))
        return sum(distances[:k]) / k


class SharingFunctionBias(AlgorithmicBias):
    """
    共享函数多样性偏置 - 基于共享函数的多样性控制

    使用共享函数来降低相似个体的适应度：
    - 相似个体：共享函数值高，降低偏置值
    - 不同个体：共享函数值低，保持原偏置值
    - 通过控制相似个体的繁殖机会维护多样性

    适用于需要精确控制相似度的问题。
    """
    context_requires = ("population_ref",)
    requires_metrics = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = "Algorithmic bias: reads metrics and outputs scalar guidance."


    def __init__(self, weight: float = 0.1, sigma_share: float = 0.2, alpha: float = 1.0):
        """
        初始化共享函数偏置

        Args:
            weight: 偏置权重
            sigma_share: 共享距离阈值
            alpha: 共享函数形状参数
        """
        super().__init__("sharing_function", weight, adaptive=True)
        self.sigma_share = sigma_share                        # 共享距离阈值
        self.alpha = alpha                                    # 形状参数

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算共享函数偏置值

        Args:
            x: 被评估的个体
            context: 优化上下文

        Returns:
            共享函数调整后的偏置值
        """
        if len(context.population) == 0:
            return 0.0

        # 计算共享函数值
        sharing_sum = 0.0
        for other in context.population:
            distance = np.linalg.norm(x - other)
            if distance < self.sigma_share:
                sharing_sum += 1.0 - (distance / self.sigma_share) ** self.alpha

        # 共享函数降低相似个体的偏置值
        if sharing_sum > 0:
            return self.weight / sharing_sum
        return self.weight
