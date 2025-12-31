# -*- coding: utf-8 -*-
"""
增强的搜索策略系统

为不同角色提供专门的搜索方法，提高优化效率
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from enum import Enum


class SearchMethod(Enum):
    """搜索方法枚举"""
    # 基础方法
    RANDOM = "random"                      # 纯随机
    GENETIC_UNIFORM = "genetic_uniform"    # 遗传算法-均匀交叉
    GENETIC_ARITHMETIC = "genetic_arithmetic"  # 遗传算法-算术交叉

    # 进化方法
    DIFFERENTIAL_EVOLUTION = "de"          # 差分进化
    EVOLUTIONARY_STRATEGY = "es"           # 进化策略

    # 模式和梯度方法
    PATTERN_SEARCH = "pattern"             # 模式搜索
    GRADIENT_APPROXIMATION = "gradient_approx"  # 近似梯度

    # 局部搜索
    HILL_CLIMBING = "hill_climb"           # 爬山算法
    SIMULATED_ANNEALING = "sa"             # 模拟退火
    LOCAL_SEARCH_HJ = "local_hj"           # Hooke-Jeeves
    LOCAL_SEARCH_RS = "local_rs"           # Rosenbrock

    # 混合方法
    MEMETIC = "memetic"                    # 文化基因（GA+局部搜索）
    HYBRID = "hybrid"                      # 混合策略


class SearchStrategy:
    """搜索策略基类"""

    def __init__(self, name: str, config: Dict = None):
        self.name = name
        self.config = config or {}
        self.history = []  # 搜索历史

    def search(self, population: List[np.ndarray], bounds: np.ndarray,
               n_solutions: int, **kwargs) -> List[np.ndarray]:
        """
        执行搜索

        Args:
            population: 当前种群
            bounds: 变量边界 [n_vars, 2]
            n_solutions: 需要生成的新解数量
            **kwargs: 额外参数（如适应度、目标值等）

        Returns:
            List[np.ndarray]: 新生成的解
        """
        raise NotImplementedError("子类必须实现此方法")


class DifferentialEvolutionStrategy(SearchStrategy):
    """
    差分进化策略

    适合探索者：利用种群个体的差异信息进行搜索
    优点：搜索能力强，适合全局探索
    """

    def __init__(self, config: Dict = None):
        default_config = {
            'F': 0.8,           # 差分权重 [0, 2]
            'CR': 0.9,          # 交叉概率 [0, 1]
            'variant': 'rand',  # 变体类型: rand/best
            'strategy': 'DE/rand/1/bin'  # 经典DE
        }
        if config:
            default_config.update(config)
        super().__init__("DifferentialEvolution", default_config)

    def search(self, population: List[np.ndarray], bounds: np.ndarray,
               n_solutions: int, **kwargs) -> List[np.ndarray]:
        """
        差分进化搜索

        公式：v = x_r1 + F * (x_r2 - x_r3)
        交叉：u = v if rand() < CR else x_target
        """
        if len(population) < 4:
            # 种群太小，回退到随机搜索
            return RandomSearchStrategy().search(population, bounds, n_solutions)

        F = self.config['F']
        CR = self.config['CR']
        variant = self.config['variant']

        new_solutions = []
        pop_array = np.array(population)

        for _ in range(n_solutions):
            # 选择目标个体
            if variant == 'best' and 'fitness' in kwargs:
                # 选择适应度最好的作为基向量
                target_idx = np.argmax(kwargs['fitness'])
            else:
                # 随机选择
                target_idx = np.random.randint(len(population))

            target = pop_array[target_idx]

            # 选择3个不同的个体（不包括target）
            candidates = list(range(len(population)))
            candidates.remove(target_idx)
            idx_r1, idx_r2, idx_r3 = np.random.choice(candidates, 3, replace=False)

            # 差分变异
            donor = pop_array[idx_r1] + F * (pop_array[idx_r2] - pop_array[idx_r3])

            # 交叉
            cross_points = np.random.rand(len(target)) < CR
            # 确保至少有一个维度交叉
            if not np.any(cross_points):
                cross_points[np.random.randint(len(target))] = True

            trial = np.where(cross_points, donor, target)

            # 边界处理
            trial = np.clip(trial, bounds[:, 0], bounds[:, 1])
            new_solutions.append(trial)

        return new_solutions


class EvolutionaryStrategy(SearchStrategy):
    """
    进化策略（ES）

    适合探索者：自适应变异，利用协方差矩阵
    优点：自适应性，能够探索复杂的搜索空间
    """

    def __init__(self, config: Dict = None):
        default_config = {
            'sigma': 0.5,         # 初始标准差
            'learning_rate': 0.1,  # 学习率
            'offspring_ratio': 7   # 子代数量倍数
        }
        if config:
            default_config.update(config)
        super().__init__("EvolutionaryStrategy", default_config)

    def search(self, population: List[np.ndarray], bounds: np.ndarray,
               n_solutions: int, **kwargs) -> List[np.ndarray]:
        """
        进化策略搜索

        使用自适应高斯变异
        """
        sigma = self.config['sigma']

        # 计算种群的均值和协方差
        pop_array = np.array(population)
        mean = np.mean(pop_array, axis=0)

        # 估计协方差矩阵（如果种群足够大）
        if len(population) > 2:
            cov = np.cov(pop_array.T)
            # 确保正定
            cov = cov + np.eye(cov.shape[0]) * 1e-6
        else:
            # 种群太小，使用对角协方差
            std = np.std(pop_array, axis=0) + 1e-6
            cov = np.diag(std ** 2)

        new_solutions = []
        for _ in range(n_solutions):
            # 从多元正态分布采样
            trial = np.random.multivariate_normal(mean, sigma * cov)
            trial = np.clip(trial, bounds[:, 0], bounds[:, 1])
            new_solutions.append(trial)

        return new_solutions


class PatternSearchStrategy(SearchStrategy):
    """
    模式搜索策略

    适合开发者：系统性探索邻域
    优点：能够找到局部最优，收敛可靠
    """

    def __init__(self, config: Dict = None):
        default_config = {
            'pattern_size': 2,    # 模式大小
            'step_size': 0.1,     # 初始步长
            'reduction': 0.5,     # 步长缩减因子
            'min_step': 1e-6      # 最小步长
        }
        if config:
            default_config.update(config)
        super().__init__("PatternSearch", default_config)

    def search(self, population: List[np.ndarray], bounds: np.ndarray,
               n_solutions: int, **kwargs) -> List[np.ndarray]:
        """
        模式搜索

        从当前最优解出发，沿着坐标方向搜索
        """
        step_size = self.config['step_size']
        pattern_size = self.config['pattern_size']

        # 如果有适应度信息，选择最好的个体作为起点
        if 'fitness' in kwargs and kwargs['fitness']:
            best_idx = np.argmax(kwargs['fitness'])
            base_point = population[best_idx]
        else:
            base_point = population[0]

        dimension = len(base_point)
        new_solutions = []

        for _ in range(n_solutions):
            # 生成模式搜索点
            # 沿着每个正负坐标方向探索
            direction = np.random.randint(-pattern_size, pattern_size + 1, size=dimension)
            trial = base_point + direction * step_size
            trial = np.clip(trial, bounds[:, 0], bounds[:, 1])
            new_solutions.append(trial)

        return new_solutions


class ApproximateGradientStrategy(SearchStrategy):
    """
    近似梯度策略

    适合开发者：利用函数的局部梯度信息
    优点：收敛快，适合连续可微问题
    """

    def __init__(self, config: Dict = None):
        default_config = {
            'epsilon': 1e-5,      # 有限差分步长
            'learning_rate': 0.1, # 学习率
            'method': 'forward'   # forward/central_difference
        }
        if config:
            default_config.update(config)
        super().__init__("ApproximateGradient", default_config)

    def search(self, population: List[np.ndarray], bounds: np.ndarray,
               n_solutions: int, **kwargs) -> List[np.ndarray]:
        """
        近似梯度搜索

        使用有限差分近似梯度，然后沿负梯度方向搜索
        """
        if 'evaluate' not in kwargs:
            # 没有评估函数，回退到模式搜索
            return PatternSearchStrategy().search(population, bounds, n_solutions)

        evaluate_func = kwargs['evaluate']
        epsilon = self.config['epsilon']
        learning_rate = self.config['learning_rate']

        # 选择当前最好的点
        if 'fitness' in kwargs and kwargs['fitness']:
            best_idx = np.argmax(kwargs['fitness'])
            x = population[best_idx].copy()
        else:
            x = population[0].copy()

        # 计算近似梯度（前向差分）
        f_x = evaluate_func(x)
        gradient = np.zeros_like(x)

        for i in range(len(x)):
            x_plus = x.copy()
            x_plus[i] += epsilon
            f_x_plus = evaluate_func(x_plus)
            gradient[i] = (f_x_plus - f_x) / epsilon

        # 沿负梯度方向生成多个点
        new_solutions = []
        for _ in range(n_solutions):
            # 添加随机扰动到梯度方向
            perturbed_gradient = gradient + np.random.randn(len(gradient)) * 0.1
            trial = x - learning_rate * perturbed_gradient
            trial = np.clip(trial, bounds[:, 0], bounds[:, 1])
            new_solutions.append(trial)

        return new_solutions


class HillClimbingStrategy(SearchStrategy):
    """
    爬山策略

    适合开发者：简单的局部搜索
    优点：实现简单，局部优化能力强
    """

    def __init__(self, config: Dict = None):
        default_config = {
            'step_size': 0.1,     # 初始步长
            'max_iterations': 10,  # 最大迭代次数
            'directions': 2       # 每个维度的搜索方向数
        }
        if config:
            default_config.update(config)
        super().__init__("HillClimbing", default_config)

    def search(self, population: List[np.ndarray], bounds: np.ndarray,
               n_solutions: int, **kwargs) -> List[np.ndarray]:
        """
        爬山搜索

        从当前点出发，向各个小方向探索
        """
        step_size = self.config['step_size']

        # 选择多个起点
        if len(population) >= n_solutions:
            start_points = population[:n_solutions]
        else:
            # 重复使用种群
            start_points = (population * (n_solutions // len(population) + 1))[:n_solutions]

        new_solutions = []
        for point in start_points:
            # 向随机方向小步移动
            direction = np.random.randn(len(point))
            direction = direction / np.linalg.norm(direction)
            trial = point + step_size * direction
            trial = np.clip(trial, bounds[:, 0], bounds[:, 1])
            new_solutions.append(trial)

        return new_solutions


class SimulatedAnnealingStrategy(SearchStrategy):
    """
    模拟退火策略

    适合探索/开发平衡：概率接受劣解
    优点：能够跳出局部最优
    """

    def __init__(self, config: Dict = None):
        default_config = {
            'initial_temp': 1.0,    # 初始温度
            'cooling_rate': 0.95,   # 降温速率
            'min_temp': 1e-4        # 最小温度
        }
        if config:
            default_config.update(config)
        super().__init__("SimulatedAnnealing", default_config)
        self.temperature = default_config['initial_temp']

    def search(self, population: List[np.ndarray], bounds: np.ndarray,
               n_solutions: int, **kwargs) -> List[np.ndarray]:
        """
        模拟退火搜索

        生成邻域解，根据Metropolis准则决定是否接受
        """
        current_temp = kwargs.get('temperature', self.temperature)

        # 选择起点
        if 'fitness' in kwargs and kwargs['fitness']:
            best_idx = np.argmax(kwargs['fitness'])
            base_point = population[best_idx]
        else:
            base_point = population[0]

        new_solutions = []
        for _ in range(n_solutions):
            # 生成邻域解
            trial = base_point + np.random.randn(len(base_point)) * current_temp * 0.5
            trial = np.clip(trial, bounds[:, 0], bounds[:, 1])
            new_solutions.append(trial)

        # 降温
        self.temperature *= self.config['cooling_rate']
        self.temperature = max(self.temperature, self.config['min_temp'])

        return new_solutions


class MemeticStrategy(SearchStrategy):
    """
    文化基因策略（Memeitic Algorithm）

    适合开发者：全局搜索 + 局部精炼
    优点：结合遗传算法的全局搜索和局部搜索的精确性
    """

    def __init__(self, config: Dict = None):
        default_config = {
            'global_method': 'genetic',  # 全局搜索方法
            'local_method': 'pattern',    # 局部搜索方法
            'local_search_prob': 0.3      # 局部搜索概率
        }
        if config:
            default_config.update(config)
        super().__init__("Memetic", default_config)

    def search(self, population: List[np.ndarray], bounds: np.ndarray,
               n_solutions: int, **kwargs) -> List[np.ndarray]:
        """
        文化基因搜索

        大部分解用全局搜索，小部分解用局部搜索精炼
        """
        local_search_prob = self.config['local_search_prob']
        n_local = int(n_solutions * local_search_prob)
        n_global = n_solutions - n_local

        # 全局搜索
        global_strategy = DifferentialEvolutionStrategy()
        global_solutions = global_strategy.search(population, bounds, n_global, **kwargs)

        # 局部搜索
        local_strategy = PatternSearchStrategy()
        local_solutions = local_strategy.search(population, bounds, n_local, **kwargs)

        return global_solutions + local_solutions


class RandomSearchStrategy(SearchStrategy):
    """
    随机搜索策略（基准策略）
    """

    def search(self, population: List[np.ndarray], bounds: np.ndarray,
               n_solutions: int, **kwargs) -> List[np.ndarray]:
        """纯随机搜索"""
        new_solutions = []
        for _ in range(n_solutions):
            trial = np.random.uniform(bounds[:, 0], bounds[:, 1])
            new_solutions.append(trial)
        return new_solutions


# 策略工厂
class SearchStrategyFactory:
    """搜索策略工厂"""

    _strategies = {
        SearchMethod.RANDOM: RandomSearchStrategy,
        SearchMethod.DIFFERENTIAL_EVOLUTION: DifferentialEvolutionStrategy,
        SearchMethod.EVOLUTIONARY_STRATEGY: EvolutionaryStrategy,
        SearchMethod.PATTERN_SEARCH: PatternSearchStrategy,
        SearchMethod.GRADIENT_APPROXIMATION: ApproximateGradientStrategy,
        SearchMethod.HILL_CLIMBING: HillClimbingStrategy,
        SearchMethod.SIMULATED_ANNEALING: SimulatedAnnealingStrategy,
        SearchMethod.MEMETIC: MemeticStrategy,
    }

    @classmethod
    def create_strategy(cls, method: SearchMethod, config: Dict = None) -> SearchStrategy:
        """
        创建搜索策略实例

        Args:
            method: 搜索方法
            config: 配置参数

        Returns:
            SearchStrategy: 策略实例
        """
        strategy_class = cls._strategies.get(method)
        if strategy_class is None:
            raise ValueError(f"未知的搜索方法: {method}")
        return strategy_class(config)

    @classmethod
    def get_available_methods(cls) -> List[SearchMethod]:
        """获取所有可用的搜索方法"""
        return list(cls._strategies.keys())

    @classmethod
    def recommend_for_explorer(cls) -> List[SearchMethod]:
        """为探索者推荐的方法"""
        return [
            SearchMethod.DIFFERENTIAL_EVOLUTION,    # 最佳选择
            SearchMethod.EVOLUTIONARY_STRATEGY,      # 次优
            SearchMethod.SIMULATED_ANNEALING,        # 平衡探索
        ]

    @classmethod
    def recommend_for_exploiter(cls) -> List[SearchMethod]:
        """为开发者推荐的方法"""
        return [
            SearchMethod.PATTERN_SEARCH,            # 最佳选择
            SearchMethod.GRADIENT_APPROXIMATION,     # 如果可微
            SearchMethod.HILL_CLIMBING,              # 简单快速
            SearchMethod.MEMETIC,                    # 全局+局部
        ]
