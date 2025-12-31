"""
模式搜索偏置实现模块

该模块实现模式搜索（Pattern Search）算法思想的偏置化，将 PS 概念注入到任何优化算法中：
- 坐标方向探索转换为偏置值
- 模式搜索的局部精化能力注入
- 算法无关性的 PS 特性注入
- 与其他偏置的无缝组合

通过偏置系统，任何算法（GA、PSO、NSGA-II等）都可以获得 PS 的局部精化能力。

PS 核心思想：沿着坐标方向系统性探索邻域
转换为偏置：鼓励在小范围内系统性搜索
"""

import numpy as np
from typing import List, Dict, Any, Optional
from ..core.base import AlgorithmicBias, OptimizationContext


class PatternSearchBias(AlgorithmicBias):
    """
    模式搜索偏置 - 将 PS 的坐标方向探索思想注入到任何算法

    核心思想是将模式搜索的坐标方向探索转换为可计算的偏置值：
    - 沿着正负坐标方向系统性探索
    - 适合局部精化和快速收敛
    - 在当前最优解附近进行模式化搜索

    通过这种转换，任何优化算法都能获得 PS 的局部精化能力。
    """

    def __init__(
        self,
        initial_weight: float = 0.1,
        pattern_size: int = 2,       # 模式大小
        step_size: float = 0.1,      # 初始步长
        reduction_factor: float = 0.5, # 步长缩减因子
        min_step: float = 1e-6       # 最小步长
    ):
        """
        初始化模式搜索偏置

        Args:
            initial_weight: 初始偏置权重
            pattern_size: 模式大小
                - 2: 沿着 ±坐标方向探索
                - 4: 沿着 ±2倍坐标方向探索
            step_size: 初始步长（相对于变量范围）
            reduction_factor: 步长缩减因子（当搜索失败时）
            min_step: 最小步长（小于此值停止搜索）
        """
        super().__init__("pattern_search", initial_weight, adaptive=True)

        # PS 核心参数
        self.pattern_size = pattern_size                # 模式大小
        self.initial_step_size = step_size              # 初始步长
        self.step_size = step_size                      # 当前步长
        self.reduction_factor = reduction_factor        # 步长缩减因子
        self.min_step = min_step                        # 最小步长

        # 历史记录
        self.step_size_history = []                     # 步长历史
        self.search_direction_history = []              # 搜索方向历史
        self.success_count = 0                          # 成功次数
        self.failure_count = 0                          # 失败次数

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算模式搜索偏置值

        核心算法：
        1. 获取当前最优解（作为模式搜索的基点）
        2. 生成模式搜索方向（沿坐标方向）
        3. 计算当前个体沿模式方向的位置
        4. 转换为偏置值（鼓励沿模式方向探索）

        Args:
            x: 被评估的个体
            context: 优化上下文

        Returns:
            PS 偏置值（负值表示奖励，正值表示惩罚）

        Note:
            上下文需要提供：
            - context.population: 当前种群
            - context.fitness: 适应度值（可选）
        """
        population = context.population

        # 获取模式搜索的基点（通常是当前最优解）
        if context.fitness is not None:
            best_idx = np.argmin(context.fitness)
            base_point = population[best_idx]
        else:
            # 没有适应度信息，使用种群中心
            base_point = np.mean(population, axis=0)

        # 记录当前步长
        self.step_size_history.append(self.step_size)

        # ========== 计算模式搜索偏置 ==========
        bias_value = 0.0

        # 计算当前个体到基点的偏移
        offset = x - base_point

        # 判断个体是否在模式搜索的合理方向上
        for dim in range(len(x)):
            # 模式搜索方向：沿着 ±pattern_size * step_size 的方向
            pattern_directions = [
                self.pattern_size * self.step_size,    # 正方向
                -self.pattern_size * self.step_size    # 负方向
            ]

            # 检查当前维度的偏移是否接近模式方向
            for direction in pattern_directions:
                # 如果个体沿这个模式方向，给予奖励
                if abs(offset[dim] - direction) < self.step_size * 0.5:
                    bias_value -= 0.1  # 负偏置（奖励）

        # 距离基点的偏移量
        distance_to_base = np.linalg.norm(offset)

        # 鼓励在基点附近的小范围探索
        if distance_to_base < self.pattern_size * self.step_size:
            # 在合理搜索范围内，给予奖励
            bias_value -= 0.2
        elif distance_to_base > self.pattern_size * self.step_size * 2:
            # 超出搜索范围，给予惩罚
            bias_value += 0.3

        return bias_value

    def adjust_step_size(self, success: bool):
        """
        调整步长

        Args:
            success: 是否成功找到更好的解
        """
        if success:
            # 成功：可以增大步长
            self.step_size = min(self.step_size * 1.2, 1.0)
            self.success_count += 1
        else:
            # 失败：缩小步长
            self.step_size = max(
                self.step_size * self.reduction_factor,
                self.min_step
            )
            self.failure_count += 1

    def generate_pattern_points(
        self,
        base_point: np.ndarray,
        n_points: int = 5
    ) -> List[np.ndarray]:
        """
        生成模式搜索点（辅助方法）

        这个方法可以直接用于生成新的候选解，完全模拟 PS 的行为。

        Args:
            base_point: 模式搜索的基点
            n_points: 要生成的点数量

        Returns:
            模式搜索点列表
        """
        dimension = len(base_point)
        pattern_points = []

        for _ in range(n_points):
            # 生成模式搜索点
            direction = np.random.randint(
                -self.pattern_size,
                self.pattern_size + 1,
                size=dimension
            )
            point = base_point + direction * self.step_size
            pattern_points.append(point)

        return pattern_points

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取 PS 偏置统计信息

        Returns:
            包含各种统计指标的字典
        """
        if not self.step_size_history:
            return {
                'current_step_size': self.step_size,
                'initial_step_size': self.initial_step_size,
                'success_rate': 0,
                'pattern_size': self.pattern_size
            }

        total_attempts = self.success_count + self.failure_count
        success_rate = self.success_count / total_attempts if total_attempts > 0 else 0

        return {
            'current_step_size': self.step_size,                          # 当前步长
            'initial_step_size': self.initial_step_size,                 # 初始步长
            'min_step_size': self.min_step,                              # 最小步长
            'success_rate': success_rate,                                # 成功率
            'success_count': self.success_count,                         # 成功次数
            'failure_count': self.failure_count,                         # 失败次数
            'pattern_size': self.pattern_size,                           # 模式大小
            'step_size_history': self.step_size_history[-10:]           # 最近10次步长记录
        }


class AdaptivePatternSearchBias(PatternSearchBias):
    """
    自适应模式搜索偏置

    在标准 PS 偏置基础上增加自适应能力：
    - 根据优化进展自动调整步长
    - 在收敛时自动缩小搜索范围
    - 在停滞时自动扩大搜索范围
    """

    def __init__(
        self,
        initial_weight: float = 0.1,
        pattern_size: int = 2,
        step_size: float = 0.1,
        reduction_factor: float = 0.5,
        adaptation_rate: float = 0.1
    ):
        """
        初始化自适应 PS 偏置

        Args:
            initial_weight: 初始权重
            pattern_size: 模式大小
            step_size: 初始步长
            reduction_factor: 步长缩减因子
            adaptation_rate: 自适应调整率
        """
        super().__init__(initial_weight, pattern_size, step_size, reduction_factor)

        self.adaptation_rate = adaptation_rate              # 自适应率
        self.improvement_history = []                       # 改进历史

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算自适应 PS 偏置值

        在标准 PS 计算基础上增加自适应调整逻辑。
        """
        # 执行标准 PS 计算
        bias_value = super().compute(x, context)

        # 更新自适应统计
        self._update_adaptive_stats(bias_value, context)

        # 自适应调整步长
        if len(self.improvement_history) >= 10:
            self._adapt_step_size()

        return bias_value

    def _update_adaptive_stats(self, bias_value: float, context: OptimizationContext):
        """
        更新自适应统计信息

        Args:
            bias_value: 当前偏置值
            context: 优化上下文
        """
        # 负偏置表示成功
        improvement = 1 if bias_value < 0 else 0
        self.improvement_history.append(improvement)

        # 保持历史长度
        if len(self.improvement_history) > 50:
            self.improvement_history.pop(0)

    def _adapt_step_size(self):
        """
        自适应调整步长

        根据最近的改进率调整步长：
        - 改进率高：可以增大步长
        - 改进率低：需要缩小步长
        """
        recent_improvements = self.improvement_history[-10:]
        improvement_rate = sum(recent_improvements) / len(recent_improvements)

        if improvement_rate > 0.6:
            # 改进率高，增大步长
            self.step_size = min(self.step_size * 1.1, 1.0)
        elif improvement_rate < 0.2:
            # 改进率低，缩小步长
            self.step_size = max(self.step_size * 0.9, self.min_step)


class CoordinateDescentBias(PatternSearchBias):
    """
    坐标下降偏置

    专门针对单维优化的模式搜索变体：
    - 每次只沿着一个坐标方向搜索
    - 循环遍历所有维度
    - 适合可分离问题
    """

    def __init__(
        self,
        initial_weight: float = 0.1,
        step_size: float = 0.1,
        cyclic: bool = True
    ):
        """
        初始化坐标下降偏置

        Args:
            initial_weight: 初始权重
            step_size: 步长
            cyclic: 是否循环选择维度
        """
        super().__init__(initial_weight, pattern_size=1, step_size=step_size)
        self.cyclic = cyclic                  # 循环选择
        self.current_dim = 0                  # 当前维度

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算坐标下降偏置值

        只沿着当前选中的维度方向给予奖励。
        """
        population = context.population

        # 获取基点
        if context.fitness is not None:
            best_idx = np.argmin(context.fitness)
            base_point = population[best_idx]
        else:
            base_point = np.mean(population, axis=0)

        # 更新当前维度
        if self.cyclic:
            dimension = len(x)
            self.current_dim = (self.current_dim + 1) % dimension

        # 计算偏置
        offset = x - base_point
        bias_value = 0.0

        # 只在当前维度给予奖励
        dim = self.current_dim
        if abs(offset[dim]) < self.step_size:
            # 在当前维度的搜索范围内
            bias_value -= 0.3

        # 其他维度给予轻微惩罚
        for i in range(len(x)):
            if i != dim and abs(offset[i]) > self.step_size:
                bias_value += 0.1

        return bias_value


# ========== 工具函数 ==========

def generate_pattern_search_point(
    base_point: np.ndarray,
    pattern_size: int = 2,
    step_size: float = 0.1
) -> np.ndarray:
    """
    生成单个模式搜索点的便捷函数

    Args:
        base_point: 基点
        pattern_size: 模式大小
        step_size: 步长

    Returns:
        模式搜索点
    """
    dimension = len(base_point)
    direction = np.random.randint(-pattern_size, pattern_size + 1, size=dimension)
    point = base_point + direction * step_size
    return point


def generate_coordinate_descent_points(
    base_point: np.ndarray,
    step_size: float = 0.1,
    n_dims: int = None
) -> List[np.ndarray]:
    """
    生成坐标下降点的便捷函数

    Args:
        base_point: 基点
        step_size: 步长
        n_dims: 要探索的维度数量（默认所有维度）

    Returns:
        坐标下降点列表
    """
    if n_dims is None:
        n_dims = len(base_point)

    points = []
    for dim in range(min(n_dims, len(base_point))):
        # 正方向
        point_plus = base_point.copy()
        point_plus[dim] += step_size
        points.append(point_plus)

        # 负方向
        point_minus = base_point.copy()
        point_minus[dim] -= step_size
        points.append(point_minus)

    return points
