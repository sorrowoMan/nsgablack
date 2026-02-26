"""
自适应算法偏置系统
只对算法偏置进行自适应调整，业务偏置保持固定
"""

import numpy as np
import re
from typing import List, Dict, Any, Optional, Tuple
from collections import deque
from dataclasses import dataclass
import logging

from ..core.base import AlgorithmicBias, OptimizationContext


@dataclass
class OptimizationState:
    """优化状态信息"""
    generation: int
    diversity: float
    convergence_rate: float
    improvement_rate: float
    population_density: float
    exploration_ratio: float
    exploitation_ratio: float


class AdaptiveAlgorithmicManager:
    """自适应算法偏置管理器"""

    def __init__(self, window_size: int = 50, adaptation_interval: int = 10):
        """
        Args:
            window_size: 历史状态窗口大小
            adaptation_interval: 自适应调整间隔（代数）
        """
        self.biases: Dict[str, AlgorithmicBias] = {}
        self.state_history = deque(maxlen=window_size)
        self._best_fitness_history = deque(maxlen=window_size)
        self.adaptation_interval = adaptation_interval
        self.last_adaptation = 0
        self.weight_cap = 1.0
        self.max_diversity_pairs = 20000

        # 自适应策略配置
        self.adaptation_strategies = {
            'stuck_detection': self._adapt_when_stuck,
            'premature_convergence': self._adapt_for_diversity,
            'slow_progress': self._adapt_for_acceleration,
            'exploration_exploitation': self._balance_exploration_exploitation
        }

        # 状态监测阈值
        self.thresholds = {
            'stuck_improvement': 0.001,  # 改进率低于此值认为陷入停滞
            'low_diversity': 0.1,        # 多样性低于此值需要增加探索
            'high_diversity': 0.8,       # 多样性高于此值可以增加开发
            'slow_improvement': 0.01     # 改进率低于此值认为进展缓慢
        }

        self.logger = logging.getLogger(__name__)

    def add_bias(self, bias: AlgorithmicBias, initial_weight: float = 0.1):
        """添加算法偏置"""
        bias.weight = initial_weight
        bias.is_adaptive = True
        self.biases[bias.name] = bias
        self.logger.info(f"Added adaptive bias: {bias.name} with weight {initial_weight}")

    def update_state(self, context: OptimizationContext,
                    current_population: List, fitness_values: List):
        """更新优化状态"""
        state = self._compute_optimization_state(context, current_population, fitness_values)
        self.state_history.append(state)

        # 检查是否需要自适应调整
        if (context.generation - self.last_adaptation) >= self.adaptation_interval:
            self._adapt_biases(state)
            self.last_adaptation = context.generation

    def _compute_optimization_state(self, context: OptimizationContext,
                                  population: List, fitness_values: List) -> OptimizationState:
        """计算当前优化状态"""
        # 计算多样性指标
        diversity = self._compute_diversity(population)

        # 计算收敛率
        convergence_rate = self._compute_convergence_rate(fitness_values)

        # 计算改进率
        improvement_rate = self._compute_improvement_rate(fitness_values)

        # 计算种群密度
        population_density = self._compute_population_density(population)

        # 计算探索/开发比例
        exploration_ratio, exploitation_ratio = self._compute_exploration_exploitation_ratio(
            population, fitness_values)

        return OptimizationState(
            generation=context.generation,
            diversity=diversity,
            convergence_rate=convergence_rate,
            improvement_rate=improvement_rate,
            population_density=population_density,
            exploration_ratio=exploration_ratio,
            exploitation_ratio=exploitation_ratio
        )

    def _adapt_biases(self, current_state: OptimizationState):
        """根据当前状态调整偏置权重"""
        adaptation_log = []

        # 检测停滞状态
        if current_state.improvement_rate < self.thresholds['stuck_improvement']:
            changes = self.adaptation_strategies['stuck_detection'](current_state)
            adaptation_log.extend(changes)

        # 检测过早收敛
        if current_state.diversity < self.thresholds['low_diversity']:
            changes = self.adaptation_strategies['premature_convergence'](current_state)
            adaptation_log.extend(changes)

        # 检测进展缓慢
        if current_state.improvement_rate < self.thresholds['slow_improvement']:
            changes = self.adaptation_strategies['slow_progress'](current_state)
            adaptation_log.extend(changes)

        # 平衡探索与开发
        self.adaptation_strategies['exploration_exploitation'](current_state)

        # 记录调整信息
        if adaptation_log:
            self.logger.info(f"Adaptation at generation {current_state.generation}: {adaptation_log}")

    def _adapt_when_stuck(self, state: OptimizationState) -> List[str]:
        """当优化陷入停滞时的自适应策略"""
        changes = []

        # 增加探索类偏置
        exploration_biases = self._resolve_biases(('diversity', 'exploration', 'density'))
        for bias_name in exploration_biases:
            if bias_name in self.biases:
                old_weight = self.biases[bias_name].weight
                self.biases[bias_name].weight = min(old_weight * 1.5, 0.5)
                changes.append(f"{bias_name}: {old_weight:.3f} -> {self.biases[bias_name].weight:.3f}")

        # 减少开发类偏置
        exploitation_biases = self._resolve_biases(('convergence', 'precision', 'exploit'))
        for bias_name in exploitation_biases:
            if bias_name in self.biases:
                old_weight = self.biases[bias_name].weight
                self.biases[bias_name].weight = max(old_weight * 0.7, 0.01)
                changes.append(f"{bias_name}: {old_weight:.3f} -> {self.biases[bias_name].weight:.3f}")

        return changes

    def _adapt_for_diversity(self, state: OptimizationState) -> List[str]:
        """为增加多样性而调整偏置"""
        changes = []

        # 大幅增加多样性相关偏置
        diversity_biases = self._resolve_biases(('diversity', 'exploration'))
        for bias_name in diversity_biases:
            if bias_name in self.biases:
                old_weight = self.biases[bias_name].weight
                self.biases[bias_name].weight = min(old_weight * 2.0, 0.8)
                changes.append(f"{bias_name}: {old_weight:.3f} -> {self.biases[bias_name].weight:.3f}")

        return changes

    def _adapt_for_acceleration(self, state: OptimizationState) -> List[str]:
        """为加速收敛而调整偏置"""
        changes = []

        # 增加收敛类偏置
        convergence_biases = self._resolve_biases(('convergence', 'precision', 'memory'))
        for bias_name in convergence_biases:
            if bias_name in self.biases:
                old_weight = self.biases[bias_name].weight
                self.biases[bias_name].weight = min(old_weight * 1.3, 0.4)
                changes.append(f"{bias_name}: {old_weight:.3f} -> {self.biases[bias_name].weight:.3f}")

        return changes

    def _balance_exploration_exploitation(self, state: OptimizationState):
        """平衡探索与开发"""
        # 根据探索/开发比例动态调整
        if state.exploration_ratio < 0.3:  # 探索不足
            exploration_biases = self._resolve_biases(('diversity', 'exploration'))
            for bias_name in exploration_biases:
                if bias_name in self.biases:
                    self.biases[bias_name].weight = min(
                        float(self.weight_cap),
                        float(self.biases[bias_name].weight) * 1.1,
                    )

        elif state.exploitation_ratio < 0.3:  # 开发不足
            exploitation_biases = self._resolve_biases(('convergence', 'precision', 'exploit'))
            for bias_name in exploitation_biases:
                if bias_name in self.biases:
                    self.biases[bias_name].weight = min(
                        float(self.weight_cap),
                        float(self.biases[bias_name].weight) * 1.1,
                    )


    def _resolve_biases(self, aliases: Tuple[str, ...]) -> List[str]:
        """Map alias tokens to currently attached bias keys (name/class fuzzy match)."""
        tokens = tuple(str(x).strip().lower() for x in aliases if str(x).strip())
        if not tokens:
            return []
        matched: List[str] = []
        for key, bias in self.biases.items():
            joined = " ".join(
                [
                    str(key),
                    str(getattr(bias, "name", "")),
                    str(getattr(bias, "__class__", type(bias)).__name__),
                ]
            ).lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", joined)
            if any(tok in normalized for tok in tokens):
                matched.append(str(key))
        return matched

    def _compute_diversity(self, population: List) -> float:
        """计算种群多样性"""
        n = len(population)
        if n < 2:
            return 0.0

        pop_array = np.asarray(population, dtype=float)
        total_pairs = (n * (n - 1)) // 2
        if total_pairs <= 0:
            return 0.0

        if total_pairs <= int(self.max_diversity_pairs):
            distances = []
            for i in range(n):
                for j in range(i + 1, n):
                    distances.append(np.linalg.norm(pop_array[i] - pop_array[j]))
            return float(np.mean(distances)) if len(distances) > 0 else 0.0

        sample_size = int(self.max_diversity_pairs)
        rng = np.random.default_rng()
        sampled = []
        for _ in range(sample_size):
            i = int(rng.integers(0, n))
            j = int(rng.integers(0, n - 1))
            if j >= i:
                j += 1
            sampled.append(np.linalg.norm(pop_array[i] - pop_array[j]))
        return float(np.mean(sampled)) if sampled else 0.0

    def _compute_convergence_rate(self, fitness_values: List) -> float:
        """计算收敛率"""
        if len(fitness_values) < 2:
            return 0.0

        # 计算适应值的标准差变化
        current_std = np.std(fitness_values)
        if len(self.state_history) > 0:
            previous_std = self.state_history[-1].convergence_rate * np.std(fitness_values)
            return abs(current_std - previous_std) / (previous_std + 1e-6)
        return 0.0

    def _compute_improvement_rate(self, fitness_values: List) -> float:
        """计算相对历史最佳的正向改进率。"""
        if not fitness_values:
            return 0.0

        current_best = float(np.min(np.asarray(fitness_values, dtype=float)))
        historical_best = None
        if len(self._best_fitness_history) > 0:
            historical_best = float(np.min(np.asarray(self._best_fitness_history, dtype=float)))
        self._best_fitness_history.append(current_best)

        if historical_best is None or not np.isfinite(historical_best):
            return 0.0

        improvement = (historical_best - current_best) / (abs(historical_best) + 1e-6)
        return float(max(0.0, improvement))

    def _compute_population_density(self, population: List) -> float:
        """计算种群密度"""
        if len(population) < 2:
            return 0.0

        # 计算搜索空间的利用率
        pop_array = np.array(population)
        min_vals = np.min(pop_array, axis=0)
        max_vals = np.max(pop_array, axis=0)
        ranges = max_vals - min_vals

        # 避免除零
        ranges = np.where(ranges == 0, 1, ranges)

        # 计算每个维度的密度
        densities = []
        for dim in range(pop_array.shape[1]):
            dim_values = pop_array[:, dim]
            hist, _ = np.histogram(dim_values, bins=10)
            density = np.sum(hist > 0) / 10.0  # 被占据的bin比例
            densities.append(density)

        return np.mean(densities)

    def _compute_exploration_exploitation_ratio(self, population: List,
                                              fitness_values: List) -> tuple:
        """计算探索与开发比例"""
        # 简化实现：基于适应值分布判断
        if not fitness_values:
            return 0.5, 0.5

        # 将适应值排序，前25%认为是开发区域，后25%认为是探索区域
        sorted_indices = np.argsort(fitness_values)
        n = len(fitness_values)

        exploitation_count = n // 4  # 最佳区域
        exploration_count = n // 4   # 最差区域

        exploitation_ratio = exploitation_count / n
        exploration_ratio = exploration_count / n

        return exploration_ratio, exploitation_ratio

    def get_adaptation_history(self) -> Dict[str, List[float]]:
        """获取自适应历史记录"""
        history = {
            'generation': [],
            'diversity': [],
            'improvement_rate': [],
            'bias_weights': {bias_name: [] for bias_name in self.biases.keys()}
        }

        for state in self.state_history:
            history['generation'].append(state.generation)
            history['diversity'].append(state.diversity)
            history['improvement_rate'].append(state.improvement_rate)

            for bias_name in self.biases.keys():
                history['bias_weights'][bias_name].append(self.biases[bias_name].weight)

        return history
