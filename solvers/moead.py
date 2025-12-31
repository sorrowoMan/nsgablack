"""
MOEA/D - Multi-Objective Evolutionary Algorithm based on Decomposition
基于分解的多目标进化算法实现

MOEA/D将多目标优化问题分解为多个单目标子问题，同时优化这些子问题。
特别适合高维多目标优化问题（目标数 > 3）。

参考文献：
Q. Zhang and H. Li, "MOEA/D: A Multiobjective Evolutionary Algorithm Based on Decomposition,"
IEEE Transactions on Evolutionary Computation, vol. 11, no. 6, pp. 712-731, Dec. 2007.
"""

import numpy as np
import random
import time
import math
from typing import List, Tuple, Dict, Any, Optional
from scipy.spatial.distance import cdist
import json
import os

# 尝试导入模块，失败时使用占位符
try:
    from ..core.base import BlackBoxProblem
    from ..utils.visualization import SolverVisualizationMixin
    from ..bias import UniversalBiasManager, OptimizationContext
    from ..utils.parallel_evaluator import ParallelEvaluator
    from ..utils.experiment import ExperimentResult
    from ..bias.bias_base import DomainBias
    from ..core.diversity import DiversityAwareInitializerBlackBox
except ImportError:
    # 作为脚本运行时
    try:
        from core.base import BlackBoxProblem
        from bias import UniversalBiasManager, OptimizationContext
        from utils.parallel_evaluator import ParallelEvaluator
        from utils.experiment import ExperimentResult
        from bias.bias_base import DomainBias
        from core.diversity import DiversityAwareInitializerBlackBox
        # 可视化模块可能不存在
        try:
            from utils.visualization import SolverVisualizationMixin
        except ImportError:
            class SolverVisualizationMixin:
                pass
    except ImportError:
        # 最小化导入
        class BlackBoxProblem:
            def __init__(self, *args, **kwargs):
                pass
            def get_num_objectives(self):
                return 1
            def evaluate(self, x):
                return [0.0]
        class SolverVisualizationMixin:
            pass
        class UniversalBiasManager:
            def compute_total_bias(self, *args):
                return 0.0
        class OptimizationContext:
            pass
        class ParallelEvaluator:
            def evaluate_population(self, *args):
                return None, None
        class ExperimentResult:
            pass
        class DomainBias:
            pass
        class DiversityAwareInitializerBlackBox:
            def __init__(self, *args, **kwargs):
                pass
            def initialize_diverse_population(self, *args, **kwargs):
                return None, None


class BlackBoxSolverMOEAD(SolverVisualizationMixin):
    """MOEA/D求解器实现"""

    def __init__(self, problem: BlackBoxProblem):
        # 基础设置
        self.problem = problem
        self.variables = problem.variables
        self.num_objectives = problem.get_num_objectives()
        self.dimension = problem.dimension
        self.var_bounds = problem.bounds

        # MOEA/D核心参数
        self.population_size = 100  # 必须等于权重向量数量
        self.neighborhood_size = 20
        self.max_generations = 200
        self.distribution_index = 20  # SBX交叉参数
        self.mutation_rate = 1.0 / self.dimension
        self.crossover_rate = 0.9

        # 分解方法
        self.decomposition_method = 'tchebycheff'  # 'tchebycheff' 或 'weighted_sum'
        self.weight_vectors = None
        self.ideal_point = None
        self.neighborhood = None

        # 种群和适应度
        self.population = None
        self.objectives = None
        self.constraint_violations = None
        self.fitness = None  # 分解后的单目标适应度

        # 运行状态
        self.generation = 0
        self.running = False
        self.start_time = 0
        self.evaluation_count = 0
        self.history = []

        # 可选组件（与NSGA-II保持兼容）
        self.enable_diversity_init = False
        self.diversity_initializer = None
        self.bias_manager = None
        self.enable_bias = False
        self.enable_parallel = False
        self.parallel_evaluator = None
        self.enable_progress_log = True
        self.report_interval = 20

        # 结果
        self.pareto_solutions = None
        self.pareto_objectives = None

        # 初始化
        self._initialize()

    def _initialize(self):
        """初始化权重向量和邻域"""
        # 生成权重向量
        self.weight_vectors = self._generate_weight_vectors()
        self.population_size = len(self.weight_vectors)

        # 初始化邻域
        self.neighborhood = self._initialize_neighborhood()

        # 初始化理想点
        self.ideal_point = np.full(self.num_objectives, float('inf'))

        # 初始化多样性初始化器
        if self.enable_diversity_init:
            self.diversity_initializer = DiversityAwareInitializerBlackBox(
                self.problem,
                similarity_threshold=0.05,
                rejection_prob=0.6
            )

        # 初始化并行评估器
        if self.enable_parallel:
            self.parallel_evaluator = ParallelEvaluator(
                backend="thread",
                max_workers=4
            )

    def _generate_weight_vectors(self) -> np.ndarray:
        """生成均匀分布的权重向量"""
        H = self._get_divisor(self.population_size, self.num_objectives) - 1
        weights = []

        # 生成所有权重向量
        def generate_recursive(current_h, current_dim, current_weights):
            if current_dim == self.num_objectives - 1:
                weights.append(current_weights + [1.0 - sum(current_weights)])
            else:
                for h in range(current_h + 1):
                    generate_recursive(h, current_dim + 1,
                                     current_weights + [h / H])

        generate_recursive(H, 0, [])

        # 确保权重向量数量正确
        if len(weights) > self.population_size:
            weights = weights[:self.population_size]
        elif len(weights) < self.population_size:
            # 生成额外的随机权重
            while len(weights) < self.population_size:
                w = np.random.dirichlet(np.ones(self.num_objectives))
                weights.append(w.tolist())

        return np.array(weights)

    def _get_divisor(self, n: int, m: int) -> int:
        """计算用于生成权重向量的最大值"""
        max_h = 1
        while math.comb(max_h + m - 1, m - 1) <= n:
            max_h += 1
        return max_h

    def _initialize_neighborhood(self) -> np.ndarray:
        """初始化权重向量的邻域"""
        # 计算权重向量间的距离
        distances = cdist(self.weight_vectors, self.weight_vectors)

        # 为每个权重向量选择最近的邻居
        neighborhood = np.zeros((self.population_size, self.neighborhood_size), dtype=int)
        for i in range(self.population_size):
            neighbors = np.argsort(distances[i])[1:self.neighborhood_size + 1]
            neighborhood[i] = neighbors

        return neighborhood

    def initialize_population(self):
        """初始化种群"""
        if self.enable_diversity_init:
            print("使用多样性感知初始化MOEA/D种群...")
            self.population, self.objectives = self.diversity_initializer.initialize_diverse_population(
                pop_size=self.population_size,
                candidate_size=self.population_size * 5,
                sampling_method='lhs'
            )
        else:
            # 标准初始化
            self.population = np.zeros((self.population_size, self.dimension))
            for i, var in enumerate(self.variables):
                min_val, max_val = self.var_bounds[var]
                self.population[:, i] = np.random.uniform(min_val, max_val, self.population_size)

            # 评估初始种群
            if self.enable_parallel and self.parallel_evaluator:
                self.objectives, self.constraint_violations = self.parallel_evaluator.evaluate_population(
                    self.population, self.problem
                )
            else:
                self.objectives = np.zeros((self.population_size, self.num_objectives))
                self.constraint_violations = np.zeros(self.population_size)
                for i in range(self.population_size):
                    obj = self._evaluate_individual(self.population[i])
                    if len(obj) == self.num_objectives:
                        self.objectives[i] = obj

        # 更新理想点
        self._update_ideal_point(self.objectives)

        # 计算分解适应度
        self.fitness = self._calculate_decomposed_fitness(self.objectives)

    def _evaluate_individual(self, x: np.ndarray) -> np.ndarray:
        """评估单个个体"""
        try:
            obj = self.problem.evaluate(x)
            obj = np.asarray(obj, dtype=float).flatten()

            # 应用偏置
            if self.enable_bias and self.bias_manager:
                context = OptimizationContext(
                    generation=self.generation,
                    individual=x,
                    population=self.population.tolist() if self.population is not None else None
                )
                bias_value = self.bias_manager.compute_total_bias(x, context)
                # 应用偏置到所有目标（简化处理）
                obj = obj + bias_value * 0.1

            self.evaluation_count += 1
            return obj
        except Exception as e:
            print(f"评估个体时出错: {e}")
            return np.full(self.num_objectives, float('inf'))

    def _update_ideal_point(self, objectives: np.ndarray):
        """更新理想点"""
        self.ideal_point = np.minimum(self.ideal_point, np.min(objectives, axis=0))

    def _calculate_decomposed_fitness(self, objectives: np.ndarray) -> np.ndarray:
        """计算分解后的适应度"""
        fitness = np.zeros(self.population_size)

        if self.decomposition_method == 'weighted_sum':
            # 加权和分解
            for i in range(self.population_size):
                if i < len(self.weight_vectors) and i < len(objectives):
                    fitness[i] = np.sum(self.weight_vectors[i] * objectives[i])

        elif self.decomposition_method == 'tchebycheff':
            # Tchebycheff分解
            for i in range(self.population_size):
                if i < len(self.weight_vectors) and i < len(objectives):
                    diff = objectives[i] - self.ideal_point
                    fitness[i] = np.max(self.weight_vectors[i] * np.abs(diff))

        return fitness

    def selection(self, i: int) -> int:
        """从第i个子问题的邻域中选择父代"""
        # 随机选择邻域中的两个个体进行锦标赛选择
        neighbors = self.neighborhood[i]
        # 确保邻居索引在有效范围内
        valid_neighbors = neighbors[neighbors < len(self.fitness)]
        if len(valid_neighbors) < 2:
            # 如果有效邻居不足2个，返回当前索引或随机有效索引
            if i < len(self.fitness):
                return i
            elif len(valid_neighbors) > 0:
                return valid_neighbors[0]
            else:
                return np.random.randint(0, len(self.fitness))

        idx1, idx2 = np.random.choice(valid_neighbors, size=2, replace=False)

        return idx1 if self.fitness[idx1] < self.fitness[idx2] else idx2

    def genetic_operator(self, parent1: np.ndarray, parent2: np.ndarray) -> np.ndarray:
        """遗传操作：SBX交叉 + 多项式变异"""
        child1 = parent1.copy()
        child2 = parent2.copy()

        # SBX交叉
        if np.random.rand() < self.crossover_rate:
            for j in range(self.dimension):
                u = np.random.rand()
                if u <= 0.5:
                    beta = (2 * u) ** (1.0 / (self.distribution_index + 1))
                else:
                    beta = (1.0 / (2 * (1 - u))) ** (1.0 / (self.distribution_index + 1))

                child1[j] = 0.5 * ((1 + beta) * parent1[j] + (1 - beta) * parent2[j])
                child2[j] = 0.5 * ((1 - beta) * parent1[j] + (1 + beta) * parent2[j])

        # 选择一个子代
        child = child1 if np.random.rand() < 0.5 else child2

        # 多项式变异
        if np.random.rand() < self.mutation_rate:
            for j in range(self.dimension):
                if np.random.rand() < self.mutation_rate:
                    y = child[j]
                    low = self.var_bounds[f"x{j}"][0]
                    high = self.var_bounds[f"x{j}"][1]

                    delta_low = (y - low) / (high - low)
                    delta_high = (high - y) / (high - low)

                    u = np.random.rand()
                    if u <= 0.5:
                        delta = 2 * u + (1 - 2 * u) * (1 - delta_low) ** (self.distribution_index + 1)
                        delta = delta ** (1.0 / (self.distribution_index + 1)) - 1
                    else:
                        delta = 2 * (1 - u) + 2 * (u - 0.5) * (1 - delta_high) ** (self.distribution_index + 1)
                        delta = 1 - (2 - delta) ** (1.0 / (self.distribution_index + 1))

                    child[j] = y + delta * (high - low)
                    child[j] = np.clip(child[j], low, high)

        return child

    def update_solution(self, i: int, child: np.ndarray, child_objectives: np.ndarray,
                       child_fitness: float):
        """更新第i个子问题的解"""
        # 找到邻域中最差的个体
        neighbors = self.neighborhood[i]
        # 确保邻居索引在有效范围内
        valid_neighbors = neighbors[neighbors < len(self.fitness)]
        if len(valid_neighbors) == 0:
            return

        worst_idx = valid_neighbors[np.argmax(self.fitness[valid_neighbors])]

        # 如果子代更好，则替换
        if child_fitness < self.fitness[worst_idx]:
            self.population[worst_idx] = child
            self.objectives[worst_idx] = child_objectives
            self.fitness[worst_idx] = child_fitness

    def evolve_one_generation(self):
        """进化一代"""
        # 保存当前种群
        old_population = self.population.copy()
        old_objectives = self.objectives.copy()

        # 确保不超过权重向量和邻域的大小
        actual_pop_size = min(self.population_size, len(self.weight_vectors), len(self.neighborhood))

        # 对每个子问题进行进化
        for i in range(actual_pop_size):
            # 选择父代
            parent_idx = self.selection(i)
            parent = self.population[parent_idx]

            # 生成子代
            child = self.genetic_operator(parent, parent)

            # 评估子代
            child_objectives = self._evaluate_individual(child)
            child_fitness = self._calculate_single_fitness(i, child_objectives)

            # 更新解
            self.update_solution(i, child, child_objectives, child_fitness)

        # 更新理想点
        self._update_ideal_point(self.objectives)

        # 重新计算所有适应度（因为理想点可能改变）
        if self.decomposition_method == 'tchebycheff':
            self.fitness = self._calculate_decomposed_fitness(self.objectives)

        self.generation += 1

    def _calculate_single_fitness(self, weight_idx: int, objectives: np.ndarray) -> float:
        """计算单个分解适应度"""
        if self.decomposition_method == 'weighted_sum':
            return np.sum(self.weight_vectors[weight_idx] * objectives)
        else:  # tchebycheff
            diff = objectives - self.ideal_point
            return np.max(self.weight_vectors[weight_idx] * np.abs(diff))

    def run(self, return_experiment=False):
        """运行MOEA/D算法"""
        self.running = True
        self.start_time = time.time()
        self.evaluation_count = 0

        # 初始化
        self.initialize_population()

        # 进化循环
        while self.running and self.generation < self.max_generations:
            self.evolve_one_generation()

            # 进度日志
            if self.enable_progress_log and (self.generation % self.report_interval == 0):
                self._log_progress()

        self.running = False
        elapsed = time.time() - self.start_time

        # 提取Pareto最优解
        self._extract_pareto_solutions()

        # 构建结果
        if return_experiment:
            result = ExperimentResult(
                problem_name=getattr(self.problem, 'name', 'unknown'),
                config={
                    'algorithm': 'MOEA/D',
                    'decomposition_method': self.decomposition_method,
                    'population_size': self.population_size,
                    'max_generations': self.max_generations
                }
            )
            result.set_results(
                self.pareto_solutions,
                self.pareto_objectives,
                self.generation,
                self.evaluation_count,
                elapsed,
                self.history
            )
            return result

        return {
            'pareto_solutions': self.pareto_solutions,
            'pareto_objectives': self.pareto_objectives,
            'generation': self.generation,
            'evaluation_count': self.evaluation_count
        }

    def _extract_pareto_solutions(self):
        """提取Pareto最优解"""
        # 简单实现：选择所有非支配解
        n_dominated = np.zeros(self.population_size, dtype=bool)

        for i in range(self.population_size):
            for j in range(self.population_size):
                if i != j and self._dominates(self.objectives[j], self.objectives[i]):
                    n_dominated[i] = True
                    break

        pareto_indices = ~n_dominated

        if np.any(pareto_indices):
            self.pareto_solutions = self.population[pareto_indices]
            self.pareto_objectives = self.objectives[pareto_indices]
        else:
            # 如果没有非支配解，选择最好的几个
            best_indices = np.argsort(self.fitness)[:min(10, self.population_size)]
            self.pareto_solutions = self.population[best_indices]
            self.pareto_objectives = self.objectives[best_indices]

    def _dominates(self, obj1: np.ndarray, obj2: np.ndarray) -> bool:
        """检查obj1是否支配obj2"""
        return np.all(obj1 <= obj2) and np.any(obj1 < obj2)

    def _log_progress(self):
        """打印进度日志"""
        try:
            if self.num_objectives == 1:
                best_idx = int(np.argmin(self.objectives[:, 0]))
                best_value = float(self.objectives[best_idx, 0])
                print(f"[MOEA/D] 第{self.generation}代 | 最佳适应度: {best_value:.6f}")
            else:
                # 多目标：显示种群统计
                avg_fitness = np.mean(self.fitness)
                min_fitness = np.min(self.fitness)
                print(f"[MOEA/D] 第{self.generation}代 | 平均适应度: {avg_fitness:.6f} | 最佳: {min_fitness:.6f}")
        except Exception:
            pass

    def stop(self):
        """停止算法"""
        self.running = False

    def reset(self):
        """重置算法状态"""
        self.generation = 0
        self.population = None
        self.objectives = None
        self.constraint_violations = None
        self.fitness = None
        self.evaluation_count = 0
        self.history = []
        self.ideal_point = np.full(self.num_objectives, float('inf'))
        self._initialize()

    # 兼容性方法（与NSGA-II保持一致）
    def set_neighborhood_size(self, value):
        try:
            self.neighborhood_size = int(value)
            if self.weight_vectors is not None:
                self.neighborhood = self._initialize_neighborhood()
        except Exception:
            pass

    def set_population_size(self, value):
        try:
            new_size = int(value)
            if new_size != self.population_size:
                self.population_size = new_size
                self._initialize()  # 重新初始化权重向量
        except Exception:
            pass

    def set_max_generations(self, value):
        try:
            self.max_generations = int(value)
        except Exception:
            pass

    def set_mutation_rate(self, value):
        self.mutation_rate = float(value)

    def set_decomposition_method(self, method):
        if method in ['tchebycheff', 'weighted_sum']:
            self.decomposition_method = method
            if self.objectives is not None:
                self.fitness = self._calculate_decomposed_fitness(self.objectives)


# 便捷函数
def create_moead_solver(problem: BlackBoxProblem, **kwargs) -> BlackBoxSolverMOEAD:
    """创建MOEA/D求解器的便捷函数"""
    solver = BlackBoxSolverMOEAD(problem)

    # 应用配置
    for key, value in kwargs.items():
        if hasattr(solver, f'set_{key}'):
            getattr(solver, f'set_{key}')(value)
        elif hasattr(solver, key):
            setattr(solver, key, value)

    return solver