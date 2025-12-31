"""
模拟退火偏置实现模块

该模块实现模拟退火算法思想的偏置化，将SA概念注入到任何优化算法中：
- Metropolis准则转换为偏置值
- 温度调度策略可配置
- 算法无关性的SA特性注入
- 与其他偏置的无缝组合

通过偏置系统，任何算法（GA、PSO、DE等）都可以获得模拟退火的全局搜索能力。
"""

import numpy as np
import math
from typing import List, Dict, Any, Optional
from ..core.base import AlgorithmicBias, OptimizationContext


class SimulatedAnnealingBias(AlgorithmicBias):
    """
    模拟退火偏置 - 将SA概念注入到任何算法

    核心思想是将传统的Metropolis准则转换为可计算的偏置值：
    - 好的解（能量降低）：给予奖励偏置
    - 差的解（能量增加）：根据温度给予概率性偏置
    - 温度随优化进度逐渐降低，搜索越来越确定

    通过这种转换，任何优化算法都能获得模拟退火的特性。
    """

    def __init__(
        self,
        initial_weight: float = 0.1,
        initial_temperature: float = 100.0,
        cooling_rate: float = 0.99,
        acceptance_strategy: str = "metropolis"
    ):
        """
        初始化模拟退火偏置

        Args:
            initial_weight: 初始偏置权重
            initial_temperature: 初始温度（高温度允许更多探索）
            cooling_rate: 冷却率（每次迭代的温度衰减因子）
            acceptance_strategy: 接受策略
                                'metropolis' - 经典Metropolis准则
                                'boltzmann' - Boltzmann分布
                                'threshold' - 阈值策略
        """
        super().__init__("simulated_annealing", initial_weight, adaptive=True)

        # SA核心参数
        self.initial_temperature = initial_temperature      # 初始温度
        self.cooling_rate = cooling_rate                     # 冷却率
        self.current_temperature = initial_temperature      # 当前温度
        self.acceptance_strategy = acceptance_strategy       # 接受策略

        # 历史记录（用于分析和调试）
        self.acceptance_history = []                        # 接受决策历史
        self.temperature_history = []                      # 温度历史
        self.energy_history = []                          # 能量变化历史

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算模拟退火偏置值

        核心算法：
        1. 更新当前温度
        2. 计算能量差（目标函数值变化）
        3. 应用Metropolis准则转换为偏置值

        Args:
            x: 被评估的个体
            context: 优化上下文，需要包含能量信息

        Returns:
            SA偏置值（正值表示惩罚，负值表示奖励）

        Note:
            上下文需要提供：
            - context.generation: 当前代数
            - context.metrics['current_energy']: 当前个体能量
            - context.metrics['previous_energy']: 前一个个体能量
        """
        generation = context.generation
        current_energy = context.metrics.get('current_energy', 0.0)
        previous_energy = context.metrics.get('previous_energy', 0.0)

        # 更新温度（指数冷却）
        self.current_temperature = self.initial_temperature * (self.cooling_rate ** generation)
        self.temperature_history.append(self.current_temperature)

        # 如果没有历史能量信息，无法计算偏置
        if previous_energy == 0.0:
            return 0.0

        # 计算能量差
        delta_energy = current_energy - previous_energy
        self.energy_history.append(delta_energy)

        # 应用Metropolis准则的偏置转换
        if delta_energy <= 0:
            # 好的解（能量降低）- 给予奖励偏置
            # 负偏置值表示该解更可能被接受
            bias_value = -abs(delta_energy) * 0.1
        else:
            # 差的解（能量增加）- 根据温度给予概率性偏置
            if self.current_temperature > 0:
                acceptance_probability = self._calculate_acceptance_probability(delta_energy)
                # 正偏置值，但温度高时偏置较小（更容易接受）
                bias_value = acceptance_probability * delta_energy * 0.1
            else:
                bias_value = 0.0  # 温度为0时不接受差的解

        return bias_value

    def _calculate_acceptance_probability(self, delta_energy: float) -> float:
        """
        计算接受概率

        根据选择的策略计算能量增加时的接受概率。

        Args:
            delta_energy: 能量增加量（正值）

        Returns:
            接受概率（0到1之间）
        """
        if self.current_temperature <= 0:
            return 0.0

        if self.acceptance_strategy == "metropolis":
            # 经典Metropolis准则
            return math.exp(-delta_energy / self.current_temperature)

        elif self.acceptance_strategy == "boltzmann":
            # 更保守的Boltzmann分布
            return 1.0 / (1.0 + math.exp(delta_energy / self.current_temperature))

        elif self.acceptance_strategy == "threshold":
            # 阈值策略：温度高时接受概率高
            threshold = self.current_temperature / self.initial_temperature
            return max(0.0, threshold)

        else:
            # 默认使用Metropolis准则
            return math.exp(-delta_energy / self.current_temperature)

    def get_temperature(self) -> float:
        """
        获取当前温度

        Returns:
            当前温度值
        """
        return self.current_temperature

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取SA统计信息

        Returns:
            包含各种统计指标的字典
        """
        return {
            'current_temperature': self.current_temperature,      # 当前温度
            'initial_temperature': self.initial_temperature,      # 初始温度
            'cooling_rate': self.cooling_rate,                    # 冷却率
            'acceptance_rate': self._calculate_acceptance_rate(),  # 接受率
            'temperature_history': self.temperature_history[-10:],  # 最近10次温度记录
            'energy_history': self.energy_history[-10:]           # 最近10次能量变化记录
        }

    def _calculate_acceptance_rate(self) -> float:
        """
        计算历史接受率

        Returns:
            接受劣解的比率
        """
        if not self.acceptance_history:
            return 0.0
        return sum(self.acceptance_history) / len(self.acceptance_history)


class AdaptiveSABias(SimulatedAnnealingBias):
    """
    自适应模拟退火偏置

    在标准SA偏置基础上增加自适应能力：
    - 根据优化进展动态调整温度衰减
    - 自动重置机制防止过早冷却
    - 基于成功率调整冷却策略
    """

    def __init__(
        self,
        initial_weight: float = 0.1,
        initial_temperature: float = 100.0,
        cooling_rate: float = 0.99,
        adaptation_window: int = 50,
        reset_threshold: float = 0.1
    ):
        """
        初始化自适应SA偏置

        Args:
            initial_weight: 初始权重
            initial_temperature: 初始温度
            cooling_rate: 冷却率
            adaptation_window: 自适应调整窗口大小
            reset_threshold: 重置阈值（接受率低于此值时重置）
        """
        super().__init__(initial_weight, initial_temperature, cooling_rate)

        self.adaptation_window = adaptation_window    # 自适应窗口
        self.reset_threshold = reset_threshold         # 重置阈值
        self.adaptive_cooling_rate = cooling_rate       # 自适应冷却率

        # 自适应统计
        self.recent_successes = []                     # 近期成功记录
        self.recent_failures = []                      # 近期失败记录

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算自适应SA偏置值

        在标准SA计算基础上增加自适应调整逻辑。

        Args:
            x: 被评估的个体
            context: 优化上下文

        Returns:
            自适应调整后的SA偏置值
        """
        # 执行标准SA计算
        bias_value = super().compute(x, context)

        # 更新自适应统计
        self._update_adaptive_stats(bias_value)

        # 自适应调整冷却率
        if len(self.recent_successes) >= self.adaptation_window:
            self._adapt_cooling_rate()

        # 必要时重置温度
        if self._should_reset_temperature():
            self._reset_temperature()

        return bias_value

    def _update_adaptive_stats(self, bias_value: float):
        """
        更新自适应统计信息

        Args:
            bias_value: 当前偏置值
        """
        if bias_value < 0:  # 负偏置表示接受了解
            self.recent_successes.append(1)
            self.recent_failures.append(0)
        else:
            self.recent_successes.append(0)
            self.recent_failures.append(1)

        # 保持窗口大小
        if len(self.recent_successes) > self.adaptation_window:
            self.recent_successes.pop(0)
            self.recent_failures.pop(0)

    def _adapt_cooling_rate(self):
        """
        自适应调整冷却率
        """
        success_rate = sum(self.recent_successes) / len(self.recent_successes)

        if success_rate > 0.6:
            # 成功率高 - 可以加快冷却
            self.adaptive_cooling_rate = min(0.999, self.adaptive_cooling_rate * 1.01)
        elif success_rate < 0.2:
            # 成功率低 - 减慢冷却
            self.adaptive_cooling_rate = max(0.9, self.adaptive_cooling_rate * 0.99)

    def _should_reset_temperature(self) -> bool:
        """
        判断是否应该重置温度

        Returns:
            True if temperature should be reset
        """
        if len(self.recent_successes) < self.adaptation_window:
            return False

        success_rate = sum(self.recent_successes) / len(self.recent_successes)
        return success_rate < self.reset_threshold

    def _reset_temperature(self):
        """重置温度到初始值"""
        self.current_temperature = self.initial_temperature
        self.recent_successes = []
        self.recent_failures = []


class MultiObjectiveSABias(SimulatedAnnealingBias):
    """
    多目标模拟退火偏置

    专门针对多目标优化问题的SA偏置：
    - 处理多目标能量计算
    - Pareto支配关系考虑
    - 拥挤度信息集成
    - 非支配解的特别处理
    """

    def __init__(
        self,
        initial_weight: float = 0.1,
        initial_temperature: float = 100.0,
        cooling_rate: float = 0.99,
        crowding_weight: float = 0.5
    ):
        """
        初始化多目标SA偏置

        Args:
            initial_weight: 初始权重
            initial_temperature: 初始温度
            cooling_rate: 冷却率
            crowding_weight: 拥挤度权重
        """
        super().__init__(initial_weight, initial_temperature, cooling_rate)
        self.crowding_weight = crowding_weight              # 拥挤度权重

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算多目标SA偏置值

        Args:
            x: 被评估的个体（包含多个目标值）
            context: 优化上下文

        Returns:
            多目标SA偏置值
        """
        # 获取多目标信息
        current_objectives = context.metrics.get('current_objectives', [])
        previous_objectives = context.metrics.get('previous_objectives', [])
        pareto_front = context.metrics.get('pareto_front', [])

        if not current_objectives or not previous_objectives:
            return 0.0

        # 计算多目标能量变化
        energy_change = self._calculate_multi_objective_energy_change(
            current_objectives, previous_objectives, pareto_front
        )

        # 应用SA偏置逻辑
        if energy_change <= 0:
            # Pareto改进或非支配解
            bias_value = -abs(energy_change) * 0.1
        else:
            # Pareto退化 - 根据温度和拥挤度决定
            crowding_bonus = self._calculate_crowding_bonus(x, pareto_front)
            acceptance_prob = math.exp(-energy_change / self.current_temperature)
            bias_value = acceptance_prob * energy_change * 0.1 + crowding_bonus

        return bias_value

    def _calculate_multi_objective_energy_change(
        self,
        current_obj: List[float],
        previous_obj: List[float],
        pareto_front: List
    ) -> float:
        """
        计算多目标能量变化

        Args:
            current_obj: 当前目标值
            previous_obj: 前一个目标值
            pareto_front: Pareto前沿

        Returns:
            能量变化值
        """
        # 简化处理：使用目标值之和作为能量
        current_energy = sum(current_obj)
        previous_energy = sum(previous_obj)
        return current_energy - previous_energy

    def _calculate_crowding_bonus(self, x: np.ndarray, pareto_front: List) -> float:
        """
        计算拥挤度奖励

        Args:
            x: 当前个体
            pareto_front: Pareto前沿

        Returns:
            拥挤度奖励偏置
        """
        if not pareto_front:
            return 0.0

        # 计算到Pareto前沿的最小距离
        min_distance = float('inf')
        for front_point in pareto_front:
            distance = np.linalg.norm(x - np.array(front_point))
            min_distance = min(min_distance, distance)

        # 距离越大（稀疏区域）奖励越大
        return self.crowding_weight * min_distance