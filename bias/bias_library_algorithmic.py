"""
算法偏置库 - Algorithmic Bias Library
专注于优化算法本身的效率、多样性、收敛性等算法层面的偏置

这个库提供了可复用的算法偏置实现，可以在不同问题间共享使用。
"""

from .bias_base import AlgorithmicBias, BaseBias, OptimizationContext
import numpy as np
from typing import Dict, Any, List, Callable
from abc import ABC, abstractmethod


# ==================== 算法偏置库 ====================

ALGORITHMIC_BIAS_LIBRARY = {
    'diversity_promotion': {
        'class': 'DiversityBias',
        'description': '促进种群多样性，避免早熟收敛',
        'use_case': '多模态问题，需要探索多个解',
        'default_params': {
            'weight': 0.2,
            'metric': 'euclidean'
        },
        'complexity': 'low'
    },

    'fast_convergence': {
        'class': 'ConvergenceBias',
        'description': '加速收敛到已知好区域',
        'use_case': '时间敏感的优化问题',
        'default_params': {
            'weight': 0.15,
            'early_gen': 5,
            'late_gen': 30
        },
        'complexity': 'low'
    },

    'precision_search': {
        'class': 'PrecisionBias',
        'description': '在好解周围进行精细搜索',
        'use_case': '需要高精度解的问题',
        'default_params': {
            'weight': 0.1,
            'precision_radius': 0.05
        },
        'complexity': 'medium'
    },

    'balanced_exploration': {
        'class': 'ExplorationBias',
        'description': '平衡探索和利用，防止早熟收敛',
        'use_case': '通用优化问题',
        'default_params': {
            'weight': 0.1,
            'stagnation_threshold': 20
        },
        'complexity': 'low'
    },

    'late_precision': {
        'class': 'ConvergenceBias',
        'description': '后期精度偏置',
        'use_case': '需要精确最终解的问题',
        'default_params': {
            'weight': 0.2,
            'early_gen': 50,
            'late_gen': 100
        },
        'complexity': 'low'
    },

    'adaptive_diversity': {
        'class': 'AdaptiveDiversityBias',
        'description': '自适应多样性偏置，根据种群状态调整',
        'use_case': '动态变化的问题',
        'default_params': {
            'weight': 0.15,
            'target_diversity': 0.8
        },
        'complexity': 'high'
    },

    'memory_guided_search': {
        'class': 'MemoryGuidedBias',
        'description': '基于搜索历史的引导偏置',
        'use_case': '有模式可循的优化问题',
        'default_params': {
            'weight': 0.2,
            'memory_size': 100
        },
        'complexity': 'high'
    },

    'gradient_approximation': {
        'class': 'GradientApproximationBias',
        'description': '基于数值梯度的近似引导',
        'use_case': '可微但梯度昂贵的函数',
        'default_params': {
            'weight': 0.1,
            'epsilon': 1e-6
        },
        'complexity': 'high'
    }
}


# ==================== 具体算法偏置实现 ====================

class DiversityBias(AlgorithmicBias):
    """多样性偏置：促进种群多样性"""

    def __init__(self, weight: float = 0.1, metric: str = 'euclidean'):
        super().__init__("diversity", weight)
        self.metric = metric

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        if not context.population:
            return 0.0

        # 计算与种群中其他个体的最小距离
        distances = []
        for other in context.population:
            if not np.array_equal(x, other):
                if self.metric == 'euclidean':
                    dist = np.linalg.norm(x - other)
                elif self.metric == 'manhattan':
                    dist = np.sum(np.abs(x - other))
                else:
                    dist = np.linalg.norm(x - other)
                distances.append(dist)

        if distances:
            min_dist = min(distances)
            # 距离越大，多样性越好，给予正向偏置
            return self.weight * min_dist
        return 0.0


class ConvergenceBias(AlgorithmicBias):
    """收敛性偏置：根据迭代阶段调整收敛倾向"""

    def __init__(self, weight: float = 0.1, early_gen: int = 10, late_gen: int = 50):
        super().__init__("convergence", weight)
        self.early_gen = early_gen
        self.late_gen = late_gen

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        gen = context.generation

        if gen < self.early_gen:
            # 早期：不鼓励收敛，保持探索
            return 0.0
        elif gen > self.late_gen:
            # 后期：鼓励收敛
            return self.weight
        else:
            # 中期：逐渐增加收敛倾向
            progress = (gen - self.early_gen) / (self.late_gen - self.early_gen)
            return self.weight * progress


class ExplorationBias(AlgorithmicBias):
    """探索性偏置：检测停滞并增加探索倾向"""

    def __init__(self, weight: float = 0.1, stagnation_threshold: int = 20):
        super().__init__("exploration", weight)
        self.stagnation_threshold = stagnation_threshold
        self.best_fitness_history = []

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        # 需要从外部获取适应度信息
        if not context.metrics or 'best_fitness' not in context.metrics:
            return 0.0

        current_best = context.metrics['best_fitness']
        self.best_fitness_history.append(current_best)

        # 保持历史记录长度
        if len(self.best_fitness_history) > self.stagnation_threshold:
            self.best_fitness_history.pop(0)

        # 检测停滞
        if len(self.best_fitness_history) >= self.stagnation_threshold:
            recent_best = max(self.best_fitness_history[-self.stagnation_threshold:])
            older_best = max(self.best_fitness_history[:-self.stagnation_threshold]) if len(self.best_fitness_history) > self.stagnation_threshold else recent_best

            if recent_best == older_best:
                # 发生停滞，增加探索偏置
                return self.weight

        return 0.0


class PrecisionBias(AlgorithmicBias):
    """精度偏置：在好解周围进行精细搜索"""

    def __init__(self, weight: float = 0.1, precision_radius: float = 0.1):
        super().__init__("precision", weight)
        self.precision_radius = precision_radius
        self.good_solutions = []

    def add_good_solution(self, x: np.ndarray):
        """添加已知的好解"""
        self.good_solutions.append(x.copy())

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        if not self.good_solutions:
            return 0.0

        # 计算与最近好解的距离
        min_distance = min(np.linalg.norm(x - good_sol) for good_sol in self.good_solutions)

        if min_distance < self.precision_radius:
            # 在好解附近，给予精细搜索的偏置
            return self.weight * (1.0 - min_distance / self.precision_radius)

        return 0.0


class AdaptiveDiversityBias(AlgorithmicBias):
    """自适应多样性偏置"""

    def __init__(self, weight: float = 0.15, target_diversity: float = 0.8):
        super().__init__("adaptive_diversity", weight)
        self.target_diversity = target_diversity
        self.diversity_history = []

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        if not context.population:
            return 0.0

        # 计算当前多样性
        current_diversity = self._calculate_diversity(context.population)
        self.diversity_history.append(current_diversity)

        # 自适应调整
        diversity_deficit = self.target_diversity - current_diversity
        bias_strength = np.clip(diversity_deficit, -1.0, 1.0)

        # 计算个体在多样性中的贡献
        individual_contribution = self._calculate_individual_contribution(x, context.population)

        return self.weight * bias_strength * individual_contribution

    def _calculate_diversity(self, population: List[np.ndarray]) -> float:
        """计算种群多样性"""
        if len(population) < 2:
            return 0.0

        distances = []
        for i in range(len(population)):
            for j in range(i + 1, len(population)):
                dist = np.linalg.norm(population[i] - population[j])
                distances.append(dist)

        return np.mean(distances)

    def _calculate_individual_contribution(self, x: np.ndarray, population: List[np.ndarray]) -> float:
        """计算个体对多样性的贡献"""
        distances = []
        for other in population:
            if not np.array_equal(x, other):
                dist = np.linalg.norm(x - other)
                distances.append(dist)

        return np.mean(distances) if distances else 1.0


class MemoryGuidedBias(AlgorithmicBias):
    """基于搜索历史的引导偏置"""

    def __init__(self, weight: float = 0.2, memory_size: int = 100):
        super().__init__("memory_guided", weight)
        self.memory_size = memory_size
        self.success_history = []  # 成功的历史
        self.failure_history = []  # 失败的历史
        self.pattern_learner = PatternLearner()

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        # 学习成功模式
        pattern_bias = self.pattern_learner.predict_success_probability(x, self.success_history)

        # 距离好解的距离
        proximity_bias = self._calculate_proximity_bias(x)

        # 避免已知坏区域
        avoidance_bias = self._calculate_avoidance_bias(x)

        return self.weight * (pattern_bias + proximity_bias - avoidance_bias)

    def record_success(self, x: np.ndarray, fitness: float):
        """记录成功的历史"""
        self.success_history.append({
            'x': x.copy(),
            'fitness': fitness,
            'generation': len(self.success_history) + len(self.failure_history)
        })

        # 限制内存大小
        if len(self.success_history) > self.memory_size:
            self.success_history.pop(0)

    def record_failure(self, x: np.ndarray):
        """记录失败的历史"""
        self.failure_history.append({
            'x': x.copy(),
            'generation': len(self.success_history) + len(self.failure_history)
        })

        # 限制内存大小
        if len(self.failure_history) > self.memory_size:
            self.failure_history.pop(0)

    def _calculate_proximity_bias(self, x: np.ndarray) -> float:
        """计算接近好解的偏置"""
        if not self.success_history:
            return 0.0

        # 找到最近的成功解
        min_distance = float('inf')
        for record in self.success_history:
            dist = np.linalg.norm(x - record['x'])
            min_distance = min(min_distance, dist)

        return np.exp(-min_distance) * 0.1

    def _calculate_avoidance_bias(self, x: np.ndarray) -> float:
        """计算避免坏区域的偏置"""
        if not self.failure_history:
            return 0.0

        # 找到最近的失败解
        min_distance = float('inf')
        for record in self.failure_history:
            dist = np.linalg.norm(x - record['x'])
            min_distance = min(min_distance, dist)

        if min_distance < 0.1:  # 太近失败区域，增加惩罚
            return (0.1 - min_distance) * 10.0
        else:
            return 0.0


class GradientApproximationBias(AlgorithmicBias):
    """基于数值梯度的近似引导偏置"""

    def __init__(self, weight: float = 0.1, epsilon: float = 1e-6, direction: str = 'descent'):
        super().__init__("gradient_approximation", weight)
        self.epsilon = epsilon
        self.direction = direction  # 'descent' or 'ascent'

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        # 这里需要一个可评估的函数，但在这个层我们无法获取
        # 实际使用时需要在更高层提供评估函数
        return 0.0  # 占位实现

    def compute_with_function(self, x: np.ndarray, eval_func: Callable[[np.ndarray], float]) -> float:
        """使用提供的函数计算梯度偏置"""
        gradient = self._numerical_gradient(x, eval_func)

        if self.direction == 'descent':
            return -self.weight * np.linalg.norm(gradient)  # 沿负梯度方向
        else:
            return self.weight * np.linalg.norm(gradient)  # 沿正梯度方向

    def _numerical_gradient(self, x: np.ndarray, eval_func: Callable[[np.ndarray], float]) -> np.ndarray:
        """计算数值梯度"""
        gradient = np.zeros_like(x)
        base_value = eval_func(x)

        for i in range(len(x)):
            x_plus = x.copy()
            x_plus[i] += self.epsilon
            f_plus = eval_func(x_plus)

            # 前向差分
            gradient[i] = (f_plus - base_value) / self.epsilon

        return gradient


class AdaptiveConvergenceBias(AlgorithmicBias):
    """自适应收敛偏置"""

    def __init__(self, weight: float = 0.1,
                 convergence_sensitivity: float = 0.01,
                 stagnation_threshold: int = 30):
        super().__init__("adaptive_convergence", weight)
        self.convergence_sensitivity = convergence_sensitivity
        self.stagnation_threshold = stagnation_threshold
        self.best_fitness_history = []

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        # 需要传入当前个体的适应度
        # 这里简化实现，实际使用时需要更多信息
        return self.weight * self._calculate_convergence_pressure(context.generation)

    def update_best_fitness(self, best_fitness: float):
        """更新最佳适应度历史"""
        self.best_fitness_history.append(best_fitness)
        if len(self.best_fitness_history) > 100:
            self.best_fitness_history.pop(0)

    def _calculate_convergence_pressure(self, generation: int) -> float:
        """计算收敛压力"""
        if len(self.best_fitness_history) < 10:
            return 0.0

        # 计算最近的改进
        recent_improvements = []
        for i in range(-10, 0):
            if abs(i) <= len(self.best_fitness_history):
                if i == -1:  # 最新的
                    continue
                if i < len(self.best_fitness_history):
                    improvement = abs(self.best_fitness_history[i] - self.best_fitness_history[i + 1])
                    recent_improvements.append(improvement)

        if not recent_improvements:
            return 0.0

        avg_improvement = np.mean(recent_improvements)

        # 如果改进很小，增加收敛压力
        if avg_improvement < self.convergence_sensitivity:
            # 但要避免过早收敛
            if generation < self.stagnation_threshold:
                return 0.0
            else:
                return 0.2  # 后期允许更大收敛压力
        else:
            return 0.0


class PopulationDensityBias(AlgorithmicBias):
    """种群密度偏置"""

    def __init__(self, weight: float = 0.1, ideal_density: float = 0.5):
        super().__init__("population_density", weight)
        self.ideal_density = ideal_density
        self.density_history = []

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        if not context.population:
            return 0.0

        # 计算个体周围的密度
        local_density = self._calculate_local_density(x, context.population)
        self.density_history.append(local_density)

        # 偏离理想密度的程度
        density_deviation = abs(local_density - self.ideal_density)

        # 密度过低时鼓励探索，密度过高时鼓励离开
        if local_density < self.ideal_density:
            return self.weight * density_deviation * 2  # 鼓励探索稀疏区域
        else:
            return -self.weight * density_deviation * 0.5  # 鼓励离开密集区域

    def _calculate_local_density(self, x: np.ndarray, population: List[np.ndarray],
                           radius: float = 0.1) -> float:
        """计算局部密度"""
        count = 0
        for other in population:
            if np.linalg.norm(x - other) < radius:
                count += 1

        return count / len(population)


class PatternBasedBias(AlgorithmicBias):
    """基于模式的偏置"""

    def __init__(self, weight: float = 0.1, pattern_length: int = 10):
        super().__init__("pattern_based", weight)
        self.pattern_length = pattern_length
        self.patterns = []
        self.pattern_weights = []

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        if not self.patterns:
            return 0.0

        # 检查是否匹配已知模式
        pattern_scores = []
        for i, pattern in enumerate(self.patterns):
            match_score = self._pattern_match_score(x, pattern)
            pattern_scores.append(match_score * self.pattern_weights[i])

        # 使用最佳匹配的分数
        return self.weight * max(pattern_scores)

    def learn_pattern(self, successful_solutions: List[np.ndarray],
                      weights: List[float] = None):
        """从成功解中学习模式"""
        if len(successful_solutions) < self.pattern_length:
            return

        # 简单的模式学习：计算平均向量和方差
        solutions_array = np.array(successful_solutions)
        pattern_mean = np.mean(solutions_array, axis=0)
        pattern_var = np.var(solutions_array, axis=0)

        pattern = {
            'mean': pattern_mean,
            'variance': pattern_var,
            'count': len(successful_solutions)
        }

        self.patterns.append(pattern)
        self.pattern_weights.append(weights[0] if weights else 1.0)

        # 限制模式数量
        if len(self.patterns) > 10:
            self.patterns.pop(0)
            self.pattern_weights.pop(0)

    def _pattern_match_score(self, x: np.ndarray, pattern: Dict) -> float:
        """计算与模式的匹配分数"""
        # 使用马氏距离计算匹配度
        diff = x - pattern['mean']
        variance_inv = 1.0 / (pattern['variance'] + 1e-6)
        squared_distance = np.sum(diff * diff * variance_inv)

        # 转换为匹配分数（距离越小，分数越高）
        match_score = np.exp(-squared_distance / 2.0)
        return match_score


class TemperatureControlBias(AlgorithmicBias):
    """温度控制偏置：模拟退火中的温度概念"""

    def __init__(self, weight: float = 0.1, initial_temp: float = 1.0,
                 cooling_rate: float = 0.95):
        super().__init__("temperature_control", weight)
        self.initial_temp = initial_temp
        self.cooling_rate = cooling_rate
        self.current_temp = initial_temp
        self.temperature_history = []

    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        # 更新温度
        self.current_temp = self.initial_temp * (self.cooling_rate ** context.generation)
        self.temperature_history.append(self.current_temp)

        # 温度影响探索倾向
        exploration_pressure = self.current_temp * 0.1

        # 高温时鼓励探索，低温时鼓励利用
        return self.weight * exploration_pressure

    def reset_temperature(self):
        """重置温度"""
        self.current_temp = self.initial_temp
        self.temperature_history = []


# ==================== 模式学习器 ====================

class PatternLearner:
    """模式学习器"""

    def __init__(self, learning_rate: float = 0.1):
        self.learning_rate = learning_rate
        self.patterns = []

    def predict_success_probability(self, x: np.ndarray, success_history: List[Dict]) -> float:
        """预测成功概率"""
        if not success_history:
            return 0.5

        # 简单的基于距离的预测
        similar_successes = []
        for record in success_history:
            distance = np.linalg.norm(x - record['x'])
            if distance < 0.1:  # 相似阈值
                similar_successes.append(1.0 if record['fitness'] > 0 else 0.0)

        if similar_successes:
            return np.mean(similar_successes)
        else:
            return 0.5

    def learn_pattern(self, x: np.ndarray, success: bool):
        """学习新模式"""
        self.patterns.append({
            'x': x.copy(),
            'success': success,
            'timestamp': len(self.patterns)
        })

        # 限制模式数量
        if len(self.patterns) > 1000:
            self.patterns.pop(0)


# ==================== 算法偏置工厂 ====================

class AlgorithmicBiasFactory:
    """算法偏置工厂"""

    @staticmethod
    def create_bias(bias_type: str, **params) -> AlgorithmicBias:
        """创建算法偏置实例"""
        if bias_type not in ALGORITHMIC_BIAS_LIBRARY:
            raise ValueError(f"Unknown algorithmic bias type: {bias_type}")

        bias_info = ALGORITHMIC_BIAS_LIBRARY[bias_type]
        class_name = bias_info['class']

        # 合并默认参数和用户参数
        default_params = bias_info['default_params'].copy()
        default_params.update(params)

        # 创建偏置实例
        return globals()[class_name](**default_params)

    @staticmethod
    def list_available_biases() -> Dict[str, Dict]:
        """列出所有可用的算法偏置"""
        return ALGORITHMIC_BIAS_LIBRARY

    @staticmethod
    def get_bias_complexity(bias_type: str) -> str:
        """获取偏置的复杂度"""
        if bias_type in ALGORITHMIC_BIAS_LIBRARY:
            return ALGORITHMIC_BIAS_LIBRARY[bias_type]['complexity']
        return 'unknown'

    @staticmethod
    def create_bias_suite(bias_configs: List[Dict]) -> List[AlgorithmicBias]:
        """创建偏置套件"""
        biases = []
        for config in bias_configs:
            bias = AlgorithmicBiasFactory.create_bias(
                config['type'],
                **config.get('parameters', {})
            )
            biases.append(bias)
        return biases

    @staticmethod
    def create_recommended_suite(problem_characteristics: Dict) -> List[AlgorithmicBias]:
        """根据问题特征推荐偏置套件"""
        biases = []

        # 基于问题特征推荐
        if problem_characteristics.get('is_multimodal', False):
            biases.append(AlgorithmicBiasFactory.create_bias(
                'diversity_promotion', weight=0.2
            ))

        if problem_characteristics.get('is_expensive', False):
            biases.append(AlgorithmicBiasFactory.create_bias(
                'fast_convergence', weight=0.15
            ))

        if problem_characteristics.get('dimension', 1) > 10:
            biases.append(AlgorithmicBiasFactory.create_bias(
                'adaptive_diversity', weight=0.15
            ))

        if problem_characteristics.get('needs_precision', False):
            biases.append(AlgorithmicBiasFactory.create_bias(
                'precision_search', weight=0.1
            ))

        return biases


# ==================== 便捷创建函数 ====================

def create_exploration_focused_bias() -> List[AlgorithmicBias]:
    """创建探索导向的偏置套件"""
    return AlgorithmicBiasFactory.create_bias_suite([
        {'type': 'diversity_promotion', 'parameters': {'weight': 0.25}},
        {'type': 'balanced_exploration', 'parameters': {'weight': 0.15}},
        {'type': 'adaptive_diversity', 'parameters': {'weight': 0.1}}
    ])


def create_convergence_focused_bias() -> List[AlgorithmicBias]:
    """创建收敛导向的偏置套件"""
    return AlgorithmicBiasFactory.create_bias_suite([
        {'type': 'fast_convergence', 'parameters': {'weight': 0.2}},
        {'type': 'precision_search', 'parameters': {'weight': 0.15}},
        {'type': 'temperature_control', 'parameters': {'weight': 0.1}}
    ])


def create_balanced_bias() -> List[AlgorithmicBias]:
    """创建平衡的偏置套件"""
    return AlgorithmicBiasFactory.create_bias_suite([
        {'type': 'diversity_promotion', 'parameters': {'weight': 0.1}},
        {'type': 'fast_convergence', 'parameters': {'weight': 0.1}},
        {'type': 'balanced_exploration', 'parameters': {'weight': 0.1}}
    ])


def create_high_precision_bias() -> List[AlgorithmicBias]:
    """创建高精度偏置套件"""
    return AlgorithmicBiasFactory.create_bias_suite([
        {'type': 'precision_search', 'parameters': {'weight': 0.2}},
        {'type': 'gradient_approximation', 'parameters': {'weight': 0.15}},
        {'type': 'memory_guided_search', 'parameters': {'weight': 0.1}}
    ])


def create_adaptive_bias() -> List[AlgorithmicBias]:
    """创建自适应偏置套件"""
    return AlgorithmicBiasFactory.create_bias_suite([
        {'type': 'adaptive_diversity', 'parameters': {'weight': 0.2}},
        {'type': 'memory_guided_search', 'parameters': {'weight': 0.15}},
        {'type': 'pattern_based', 'parameters': {'weight': 0.1}}
    ])


# ==================== 导出接口 ====================

__all__ = [
    # 算法偏置基类
    'AlgorithmicBias',

    # 具体偏置实现
    'DiversityBias',
    'ConvergenceBias',
    'ExplorationBias',
    'PrecisionBias',
    'AdaptiveDiversityBias',
    'MemoryGuidedBias',
    'GradientApproximationBias',
    'AdaptiveConvergenceBias',
    'PopulationDensityBias',
    'PatternBasedBias',
    'TemperatureControlBias',

    # 工具类
    'PatternLearner',
    'AlgorithmicBiasFactory',

    # 偏置库
    'ALGORITHMIC_BIAS_LIBRARY',

    # 便捷函数
    'create_exploration_focused_bias',
    'create_convergence_focused_bias',
    'create_balanced_bias',
    'create_high_precision_bias',
    'create_adaptive_bias'
]