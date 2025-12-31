"""
多智能体黑盒求解器

基于NSGA-II框架实现的多智能体协同进化求解器
通过不同角色的智能体实现探索、开发、学习和协调

智能体角色：
- Explorer: 探索者，专注于发现新区域
- Exploiter: 开发者，专注于局部优化
- Waiter: 等待者，学习其他智能体的成功模式
- Coordinator: 协调者，动态调整策略
"""

import time
import math
import random
import numpy as np
from scipy.spatial.distance import cdist
import json
import os
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from collections import Counter

try:
    # 当作为包导入时使用相对导入
    from ..core.base import BlackBoxProblem
    from ..core.diversity import DiversityAwareInitializerBlackBox
    from ..core.elite import AdvancedEliteRetention
    from ..core.solver import BaseSolver
    from ..multi_agent.core.role import AgentRole, RoleCharacteristics, get_role_description, suggest_role_config
    # 可选导入
    try:
        from ..utils.visualization import SolverVisualizationMixin
    except ImportError:
        class SolverVisualizationMixin:
            pass
    try:
        from ..bias import BiasModule
    except ImportError:
        BiasModule = None
    try:
        from ..utils.experiment import ExperimentResult
    except ImportError:
        ExperimentResult = None
    try:
        from ..utils.numba_helpers import fast_is_dominated, NUMBA_AVAILABLE
    except Exception:
        fast_is_dominated = None
        NUMBA_AVAILABLE = False
    try:
        from ..utils.representation import RepresentationPipeline
    except ImportError:
        RepresentationPipeline = None
except ImportError:
    # 当作为脚本运行时使用绝对导入
    try:
        from nsgablack.core.base import BlackBoxProblem
        from nsgablack.core.diversity import DiversityAwareInitializerBlackBox
        from nsgablack.core.elite import AdvancedEliteRetention
        from nsgablack.core.solver import BaseSolver
        from nsgablack.multi_agent.core.role import AgentRole, RoleCharacteristics, get_role_description, suggest_role_config
    except ImportError:
        import sys
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        core_dir = os.path.join(parent_dir, 'core')
        utils_dir = os.path.join(parent_dir, 'utils')
        multi_agent_dir = os.path.join(parent_dir, 'multi_agent')
        if core_dir not in sys.path:
            sys.path.insert(0, core_dir)
        if utils_dir not in sys.path:
            sys.path.insert(0, utils_dir)
        if multi_agent_dir not in sys.path:
            sys.path.insert(0, multi_agent_dir)
        from base import BlackBoxProblem
        from diversity import DiversityAwareInitializerBlackBox
        from elite import AdvancedEliteRetention
        from base_solver import BaseSolver
        from multi_agent.core.role import AgentRole, RoleCharacteristics, get_role_description, suggest_role_config

    # 可选导入
    try:
        from nsgablack.utils.visualization import SolverVisualizationMixin
    except ImportError:
        class SolverVisualizationMixin:
            pass
    try:
        from nsgablack.bias import BiasModule
    except ImportError:
        BiasModule = None
    try:
        from nsgablack.utils.experiment import ExperimentResult
    except ImportError:
        ExperimentResult = None
    try:
        from nsgablack.utils.numba_helpers import fast_is_dominated, NUMBA_AVAILABLE
    except Exception:
        fast_is_dominated = None
        NUMBA_AVAILABLE = False
    try:
        from nsgablack.utils.representation import RepresentationPipeline
    except ImportError:
        RepresentationPipeline = None


@dataclass
class AgentPopulation:
    """智能体种群数据结构"""
    role: AgentRole
    population: List[np.ndarray]
    objectives: List[List[float]]
    constraints: List[List[float]]  # 约束违背度
    fitness: List[float]
    bias_profile: Dict
    generation: int = 0
    best_individual: Optional[np.ndarray] = None
    best_objectives: Optional[List[float]] = None
    best_constraints: Optional[List[float]] = None
    representation_pipeline: Optional['RepresentationPipeline'] = None


class MultiAgentBlackBoxSolver(BaseSolver, SolverVisualizationMixin):
    """
    多智能体黑盒求解器

    基于NSGA-II框架，通过多智能体协同进化进行优化。
    每个智能体角色有不同的搜索策略和偏置设置。
    """

    def __init__(self, problem: BlackBoxProblem, config: Dict = None):
        """初始化多智能体求解器"""
        # 调用父类初始化
        super().__init__(problem)

        # 基础属性
        self.problem = problem
        self.variables = problem.variables
        self.num_objectives = problem.get_num_objectives()
        self.dimension = problem.dimension
        self.constraints = []
        self.constraint_violations = None
        self.var_bounds = problem.bounds

        # 默认配置
        self.config = {
            'total_population': 200,
            'agent_ratios': {
                AgentRole.EXPLORER: 0.25,    # 25% 探索者
                AgentRole.EXPLOITER: 0.35,   # 35% 开发者
                AgentRole.WAITER: 0.15,      # 15% 等待者
                AgentRole.ADVISOR: 0.15,      # 15% 建议者 🌟
                AgentRole.COORDINATOR: 0.10  # 10% 协调者
            },
            'max_generations': 100,
            'elite_ratio': 0.1,
            'communication_interval': 5,     # 种群间通信间隔
            'adaptation_interval': 20,       # 策略调整间隔
            'dynamic_ratios': True,          # 是否动态调整比例
            'use_bias_system': True,         # 是否使用偏置系统
            'region_partition': False,       # 是否启用区域分区（生产调度特有）
            'advisory_method': 'bayesian',   # 建议者使用的方法: 'bayesian', 'ml', 'ensemble'
            'advisory_update_interval': 5,   # 建议更新间隔
            'representation_pipeline': None,
            'representation_pipelines': {}
        }

        # 更新配置
        if config:
            self.config.update(config)

        # 初始化智能体种群
        self.agent_populations = {}
        self._initialize_agents()

        # 历史记录
        self.history = {
            'best_objectives': [],
            'diversity': [],
            'convergence_rate': [],
            'agent_contributions': {role: [] for role in AgentRole},
            'generation': 0
        }

        # 全局最优
        self.global_best = None
        self.global_best_objectives = None
        self.global_best_constraints = None

        # 统计信息
        self.stats = {
            'evaluations': 0,
            'communications': 0,
            'adaptations': 0
        }

        print(f"[MultiAgent] 初始化多智能体求解器")
        print(f"[MultiAgent] 种群配置: {[f'{role.value}: {len(pop.population)}' for role, pop in self.agent_populations.items()]}")

    def _initialize_agents(self):
        """初始化智能体种群"""
        total_pop = self.config['total_population']

        for role, ratio in self.config['agent_ratios'].items():
            pop_size = int(total_pop * ratio)

            # 根据角色设置偏置配置
            bias_profile = self._get_bias_profile(role)

            # 初始化种群
            pipeline = self._get_representation_pipeline(role)
            population = self._initialize_agent_population(pop_size, bias_profile, role, pipeline)

            self.agent_populations[role] = AgentPopulation(
                role=role,
                population=population,
                objectives=[],
                constraints=[],
                fitness=[],
                bias_profile=bias_profile,
                representation_pipeline=pipeline
            )

    def _get_bias_profile(self, role: AgentRole) -> Dict:
        """获取不同角色的偏置配置"""
        if role == AgentRole.EXPLORER:
            return {
                'diversity_weight': 2.0,        # 强调多样性
                'exploration_rate': 0.8,        # 高探索率
                'mutation_rate': 0.3,           # 高变异率
                'crossover_rate': 0.6,          # 较低交叉率
                'selection_pressure': 0.3,      # 低选择压力
                'constraint_tolerance': 0.5     # 高约束容忍度
            }
        elif role == AgentRole.EXPLOITER:
            return {
                'diversity_weight': 0.5,        # 弱化多样性
                'exploration_rate': 0.2,        # 低探索率
                'mutation_rate': 0.1,           # 低变异率
                'crossover_rate': 0.9,          # 高交叉率
                'selection_pressure': 0.8,      # 高选择压力
                'constraint_tolerance': 0.1     # 低约束容忍度
            }
        elif role == AgentRole.WAITER:
            return {
                'diversity_weight': 1.0,        # 中等多样性
                'exploration_rate': 0.1,        # 极低探索率
                'mutation_rate': 0.05,          # 极低变异率
                'crossover_rate': 0.7,          # 中等交叉率
                'selection_pressure': 0.5,      # 中等选择压力
                'constraint_tolerance': 0.3     # 中等约束容忍度
            }
        elif role == AgentRole.ADVISOR:
            # 建议者：智能分析与建议
            return {
                'diversity_weight': 1.2,        # 平衡多样性
                'exploration_rate': 0.5,        # 平衡探索
                'mutation_rate': 0.15,          # 低变异率（主要依靠建议）
                'crossover_rate': 0.7,          # 中等交叉率
                'selection_pressure': 0.5,      # 中等选择压力
                'constraint_tolerance': 0.3,    # 中等约束容忍度
                'analytical_weight': 0.8,       # 分析权重
                'advisory_influence': 0.7       # 建议影响权重
            }
        else:  # COORDINATOR
            return {
                'diversity_weight': 1.5,        # 较高多样性
                'exploration_rate': 0.4,        # 中等探索率
                'mutation_rate': 0.2,           # 中等变异率
                'crossover_rate': 0.8,          # 较高交叉率
                'selection_pressure': 0.6,      # 中等选择压力
                'constraint_tolerance': 0.4     # 中等约束容忍度
            }

    def _get_representation_pipeline(self, role: AgentRole):
        """Pick a role-specific representation pipeline if provided."""
        role_pipelines = self.config.get('representation_pipelines') or {}
        if isinstance(role_pipelines, dict):
            pipeline = role_pipelines.get(role)
            if pipeline is not None:
                return pipeline
        return self.config.get('representation_pipeline')

    def _initialize_agent_population(self, size: int, bias_profile: Dict, role: AgentRole, pipeline=None) -> List[np.ndarray]:
        """初始化智能体种群"""
        population = []

        for i in range(size):
            if pipeline is not None and getattr(pipeline, 'initializer', None) is not None:
                context = {
                    'generation': 0,
                    'bounds': self.var_bounds,
                    'role': role.value
                }
                individual = pipeline.init(self.problem, context)
            else:
                if bias_profile['exploration_rate'] > 0.5:
                    # high exploration: uniform
                    individual = np.random.uniform(
                        low=self.var_bounds[:, 0],
                        high=self.var_bounds[:, 1],
                        size=self.dimension
                    )
                else:
                    # low exploration: center-focused
                    center = np.mean(self.var_bounds, axis=1)
                    radius = np.max(self.var_bounds[:, 1] - self.var_bounds[:, 0]) * 0.2
                    individual = center + np.random.randn(self.dimension) * radius
                    individual = np.clip(individual, self.var_bounds[:, 0], self.var_bounds[:, 1])

            population.append(individual)

        return population

    def evaluate_population(self, agent_pop: AgentPopulation):
        """评估种群（考虑角色偏置）"""
        agent_pop.objectives = []
        agent_pop.constraints = []
        agent_pop.fitness = []

        for individual in agent_pop.population:
            # 基础评估
            objectives = self.problem.evaluate(individual)
            constraints = self.problem.evaluate_constraints(individual) if hasattr(self.problem, 'evaluate_constraints') else []

            # 计算约束违背度总和
            total_violation = sum(abs(c) for c in constraints) if constraints else 0

            # 应用角色偏置
            biased_objectives = self._apply_role_bias(objectives, agent_pop.role)

            # 计算适应度（考虑约束）
            if total_violation > 0:
                fitness = -np.mean(biased_objectives) + total_violation * 1000  # 惩罚不可行解
            else:
                fitness = -np.mean(biased_objectives)

            agent_pop.objectives.append(objectives)
            agent_pop.constraints.append(constraints)
            agent_pop.fitness.append(fitness)

            # 更新最优个体
            if agent_pop.best_individual is None or \
               (total_violation == 0 and self._dominates(objectives, agent_pop.best_objectives)) or \
               (total_violation < sum(abs(c) for c in (agent_pop.best_constraints or []))):
                agent_pop.best_individual = individual.copy()
                agent_pop.best_objectives = objectives.copy()
                agent_pop.best_constraints = constraints.copy() if constraints else []

        self.stats['evaluations'] += len(agent_pop.population)

    def _apply_role_bias(self, objectives: List[float], role: AgentRole) -> List[float]:
        """应用角色偏置到目标值"""
        if role == AgentRole.EXPLORER:
            # 探索者：奖励新颖解，增加多样性
            diversity_bonus = np.random.randn() * 0.1 * np.std(objectives) if len(objectives) > 1 else 0
            return [obj + diversity_bonus for obj in objectives]
        elif role == AgentRole.EXPLOITER:
            # 开发者：优先考虑主要目标
            return [objectives[0]] + [obj * 0.7 for obj in objectives[1:]]
        elif role == AgentRole.WAITER:
            # 等待者：平衡所有目标
            return objectives
        elif role == AgentRole.ADVISOR:
            # 建议者：综合分析，考虑所有目标的平衡
            # 计算目标的加权平均值，更关注次要目标的改善
            if len(objectives) > 1:
                primary_weight = 0.6
                secondary_weight = 0.4 / (len(objectives) - 1)
                weighted_obj = objectives[0] * primary_weight + sum(objectives[1:]) * secondary_weight
                return [weighted_obj] + [obj * 0.9 for obj in objectives[1:]]
            return objectives
        else:  # COORDINATOR
            # 协调者：综合考虑
            return objectives

    def evolve_population(self, agent_pop: AgentPopulation):
        """
        进化种群 - 统一的 NSGA-II 框架 + 偏置系统

        核心理念：
        1. 所有角色使用统一的 NSGA-II 算法
        2. 通过偏置系统实现角色差异化
        3. 保持项目特色：NSGA-II + 偏置系统
        """
        pop_size = len(agent_pop.population)

        # ========== 第一步：应用角色偏置到适应度 ==========
        # 所有角色都用同样的评估，但应用不同的偏置
        biased_objectives = []
        for i, individual in enumerate(agent_pop.population):
            if i < len(agent_pop.objectives):
                # 应用角色偏置
                biased_obj = self._apply_role_bias(
                    agent_pop.objectives[i],
                    agent_pop.role
                )
                biased_objectives.append(biased_obj)

        # ========== 第二步：NSGA-II 选择（所有角色统一） ==========
        # 2.1 快速非支配排序
        fronts = self._fast_non_dominated_sort(
            agent_pop.population,
            biased_objectives
        )

        # 2.2 计算拥挤距离
        for front in fronts:
            self._calculate_crowding_distance(front, biased_objectives)

        # 2.3 选择精英（基于 front rank 和 crowding distance）
        selected_indices = self._nsga2_select(
            fronts,
            pop_size
        )

        # 精英个体直接进入下一代
        new_population = [
            agent_pop.population[i].copy()
            for i in selected_indices
        ]

        # ========== 第三步：遗传操作生成新个体 ==========
        # 生成剩余个体
        while len(new_population) < pop_size:
            # NSGA-II 锦标赛选择（基于偏置后的适应度）
            parent1_idx = self._nsga2_tournament_select(selected_indices, biased_objectives)
            parent2_idx = self._nsga2_tournament_select(selected_indices, biased_objectives)

            parent1 = agent_pop.population[parent1_idx]
            parent2 = agent_pop.population[parent2_idx]

            # 模拟二进制交叉（SBX）- NSGA-II 标准交叉算子
            child1, child2 = self._sbx_crossover(
                parent1,
                parent2,
                agent_pop.bias_profile
            )

            # 多项式变异 - NSGA-II 标准变异算子
            child1 = self._polynomial_mutation(child1, agent_pop.bias_profile)
            child2 = self._polynomial_mutation(child2, agent_pop.bias_profile)

            if agent_pop.representation_pipeline is not None and getattr(agent_pop.representation_pipeline, 'mutator', None) is not None:
                context = {
                    'generation': agent_pop.generation,
                    'bounds': self.var_bounds,
                    'role': agent_pop.role.value
                }
                child1 = agent_pop.representation_pipeline.mutate(child1, context)
                child2 = agent_pop.representation_pipeline.mutate(child2, context)

            new_population.append(child1)
            if len(new_population) < pop_size:
                new_population.append(child2)

        # 更新种群
        agent_pop.population = new_population[:pop_size]
        agent_pop.generation += 1

    def _fast_non_dominated_sort(self, population: List[np.ndarray], objectives: List[List[float]]):
        """
        NSGA-II: 快速非支配排序

        将种群分成多个前沿面（fronts）
        Front 0 是非支配解集，Front 1 被 Front 0 支配，以此类推
        """
        if not population or not objectives:
            return [[]]

        n = len(population)
        # 每个个体被多少其他个体支配
        domination_count = [0] * n
        # 每个个体支配哪些其他个体
        dominated_solutions = [[] for _ in range(n)]
        # 前沿面
        fronts = [[]]

        # 计算支配关系
        for i in range(n):
            for j in range(i + 1, n):
                if self._dominates(objectives[i], objectives[j]):
                    domination_count[j] += 1
                    dominated_solutions[i].append(j)
                elif self._dominates(objectives[j], objectives[i]):
                    domination_count[i] += 1
                    dominated_solutions[j].append(i)

            # 如果不被任何个体支配，加入第一前沿面
            if domination_count[i] == 0:
                fronts[0].append(i)

        # 构建后续前沿面
        i = 0
        while fronts[i]:
            next_front = []
            for individual_idx in fronts[i]:
                for dominated_idx in dominated_solutions[individual_idx]:
                    domination_count[dominated_idx] -= 1
                    if domination_count[dominated_idx] == 0:
                        next_front.append(dominated_idx)
            i += 1
            if next_front:
                fronts.append(next_front)
            else:
                break

        return fronts

    def _calculate_crowding_distance(self, front: List[int], objectives: List[List[float]]):
        """
        NSGA-II: 计算拥挤距离

        拥挤距离衡量个体在目标空间中的稀疏程度
        距离越大，表示周围个体越少，多样性越好
        """
        if len(front) == 0:
            return

        n = len(front)
        # 初始化拥挤距离
        distance = [0.0] * n

        if n <= 2:
            # 边界个体赋给无穷大
            for i in range(n):
                distance[i] = float('inf')
            return

        # 对每个目标计算拥挤距离
        num_objectives = len(objectives[front[0]])
        for m in range(num_objectives):
            # 按第 m 个目标排序
            sorted_indices = sorted(front, key=lambda i: objectives[i][m])
            distance[front.index(sorted_indices[0])] = float('inf')
            distance[front.index(sorted_indices[-1])] = float('inf')

            # 计算目标范围
            obj_min = objectives[sorted_indices[0]][m]
            obj_max = objectives[sorted_indices[-1]][m]
            obj_range = obj_max - obj_min

            if obj_range == 0:
                continue

            # 计算中间个体的拥挤距离
            for i in range(1, n - 1):
                idx = front.index(sorted_indices[i])
                distance[idx] += (objectives[sorted_indices[i + 1]][m] -
                                 objectives[sorted_indices[i - 1]][m]) / obj_range

        # 存储拥挤距离到个体属性中
        for i, individual_idx in enumerate(front):
            if hasattr(self, '_crowding_distances'):
                self._crowding_distances[individual_idx] = distance[i]

    def _nsga2_select(self, fronts: List[List[int]], pop_size: int) -> List[int]:
        """
        NSGA-II: 环境选择

        根据 front rank 和 crowding distance 选择下一代
        优先选择 rank 低的，同 rank 内选择 crowding distance 大的
        """
        selected = []
        current_size = 0

        for front in fronts:
            if current_size + len(front) <= pop_size:
                # 整个 front 都可以加入
                selected.extend(front)
                current_size += len(front)
            else:
                # 只能加入 front 的一部分
                remaining = pop_size - current_size
                # 按 crowding distance 排序，选择最大的
                if hasattr(self, '_crowding_distances'):
                    sorted_front = sorted(
                        front,
                        key=lambda i: self._crowding_distances.get(i, 0),
                        reverse=True
                    )
                else:
                    # 如果没有计算拥挤距离，随机选择
                    sorted_front = front
                selected.extend(sorted_front[:remaining])
                break

        return selected

    def _nsga2_tournament_select(self, candidate_indices: List[int], objectives: List[List[float]]) -> int:
        """
        NSGA-II: 二元锦标赛选择

        随机选择两个个体，选择：
        1. rank 更低的
        2. 如果 rank 相同，选择 crowding distance 更大的
        """
        # 随机选择两个候选
        idx1, idx2 = np.random.choice(candidate_indices, 2, replace=False)

        # 简化版：比较目标值（实际应该比较 rank 和 crowding distance）
        # 这里使用随机选择（在实现完整版时应该比较 rank）
        return idx1 if np.random.rand() < 0.5 else idx2

    def _sbx_crossover(self, parent1: np.ndarray, parent2: np.ndarray, bias_profile: Dict) -> Tuple[np.ndarray, np.ndarray]:
        """
        NSGA-II: 模拟二进制交叉（Simulated Binary Crossover, SBX）

        根据偏置配置调整分布指数，实现角色差异化
        """
        eta_c = 15.0  # 分布指数
        # 根据角色调整：探索者用小的 eta_c（更接近均匀），开发者用大的 eta_c（更接近父母）
        if bias_profile['exploration_rate'] > 0.5:
            eta_c = 5.0  # 探索者：更分散
        else:
            eta_c = 20.0  # 开发者：更集中

        child1 = np.zeros_like(parent1)
        child2 = np.zeros_like(parent2)

        for i in range(len(parent1)):
            if np.random.rand() <= 0.5:
                if abs(parent1[i] - parent2[i]) > 1e-14:
                    # 计算 Beta 值
                    u = np.random.rand()
                    beta = 1.0 + (2.0 * min(parent1[i], parent2[i]) /
                                  abs(parent1[i] - parent2[i]))
                    alpha = 2.0 - beta ** -(eta_c + 1.0)

                    if u <= 1.0 / alpha:
                        beta_q = (u * alpha) ** (1.0 / (eta_c + 1.0))
                    else:
                        beta_q = (1.0 / (2.0 - u * alpha)) ** (1.0 / (eta_c + 1.0))

                    child1[i] = 0.5 * ((parent1[i] + parent2[i]) - beta_q * abs(parent2[i] - parent1[i]))
                    child2[i] = 0.5 * ((parent1[i] + parent2[i]) + beta_q * abs(parent2[i] - parent1[i]))
                else:
                    child1[i] = parent1[i]
                    child2[i] = parent2[i]
            else:
                child1[i] = parent1[i]
                child2[i] = parent2[i]

        # 边界处理
        child1 = np.clip(child1, self.var_bounds[:, 0], self.var_bounds[:, 1])
        child2 = np.clip(child2, self.var_bounds[:, 0], self.var_bounds[:, 1])

        return child1, child2

    def _polynomial_mutation(self, individual: np.ndarray, bias_profile: Dict) -> np.ndarray:
        """
        NSGA-II: 多项式变异（Polynomial Mutation）

        根据偏置配置调整变异强度，实现角色差异化
        """
        eta_m = 20.0  # 分布指数
        mutation_prob = 1.0 / len(individual)  # 变异概率

        # 根据角色调整：探索者用高的变异率，开发者用低的变异率
        if bias_profile['exploration_rate'] > 0.5:
            mutation_prob *= 1.5  # 探索者：增加变异
            eta_m = 10.0  # 更均匀的变异
        else:
            mutation_prob *= 0.8  # 开发者：减少变异
            eta_m = 30.0  # 更小的变异

        mutated = individual.copy()

        for i in range(len(individual)):
            if np.random.rand() < mutation_prob:
                delta_low = (individual[i] - self.var_bounds[i, 0]) / (self.var_bounds[i, 1] - self.var_bounds[i, 0])
                delta_high = (self.var_bounds[i, 1] - individual[i]) / (self.var_bounds[i, 1] - self.var_bounds[i, 0])

                u = np.random.rand()
                delta_q = 0.0

                if u <= 0.5:
                    delta_q = (2.0 * u + (1.0 - 2.0 * u) * (1.0 - delta_low) ** (eta_m + 1.0)) ** (1.0 / (eta_m + 1.0)) - 1.0
                else:
                    delta_q = 1.0 - (2.0 * (1.0 - u) + 2.0 * (u - 0.5) * (1.0 - delta_high) ** (eta_m + 1.0)) ** (1.0 / (eta_m + 1.0))

                mutated[i] = individual[i] + delta_q * (self.var_bounds[i, 1] - self.var_bounds[i, 0])

        # 边界处理
        mutated = np.clip(mutated, self.var_bounds[:, 0], self.var_bounds[:, 1])

        return mutated

    def _select_elites(self, agent_pop: AgentPopulation, elite_size: int) -> List[np.ndarray]:
        """选择精英个体（已废弃，保留向后兼容）"""
        if not agent_pop.fitness:
            return []

        fitness = np.array(agent_pop.fitness)
        elite_indices = np.argsort(fitness)[-elite_size:]
        return [agent_pop.population[i].copy() for i in elite_indices]

    def _select_parents_random(self, agent_pop: AgentPopulation) -> Tuple[np.ndarray, np.ndarray]:
        """随机选择父母（已废弃，保留向后兼容）"""
        if len(agent_pop.population) < 2:
            return agent_pop.population[0], agent_pop.population[0]

        idx1, idx2 = np.random.choice(len(agent_pop.population), 2, replace=False)
        return agent_pop.population[idx1], agent_pop.population[idx2]

    def _select_parents_best(self, agent_pop: AgentPopulation) -> Tuple[np.ndarray, np.ndarray]:
        """基于适应度选择父母（已废弃，保留向后兼容）"""
        if len(agent_pop.population) < 2:
            return agent_pop.population[0], agent_pop.population[0]

        fitness = np.array(agent_pop.fitness)
        # 避免负值
        fitness = fitness - fitness.min() + 1e-8
        probabilities = fitness / fitness.sum()

        idx1, idx2 = np.random.choice(
            len(agent_pop.population),
            2,
            replace=False,
            p=probabilities
        )
        return agent_pop.population[idx1], agent_pop.population[idx2]

    def _crossover_with_bias(self, parent1: np.ndarray, parent2: np.ndarray,
                           bias_profile: Dict) -> np.ndarray:
        """带偏置的交叉操作（已废弃，保留向后兼容）"""
        if np.random.rand() < bias_profile['crossover_rate']:
            # 根据角色选择交叉策略
            if bias_profile['exploration_rate'] > 0.5:
                # 探索者：均匀交叉
                mask = np.random.rand(len(parent1)) < 0.5
                child = np.where(mask, parent1, parent2)
            else:
                # 开发者：算术交叉
                alpha = np.random.rand()
                child = alpha * parent1 + (1 - alpha) * parent2
        else:
            child = parent1.copy()

        # 确保在边界内
        child = np.clip(child, self.var_bounds[:, 0], self.var_bounds[:, 1])
        return child

    def _mutate_with_bias(self, individual: np.ndarray, bias_profile: Dict) -> np.ndarray:
        """带偏置的变异操作（已废弃，保留向后兼容）"""
        if np.random.rand() < bias_profile['mutation_rate']:
            mutation_strength = bias_profile['exploration_rate'] * 0.5
            mutation = np.random.randn(len(individual)) * mutation_strength

            # 限制变异幅度
            max_mutation = (self.var_bounds[:, 1] - self.var_bounds[:, 0]) * 0.2
            mutation = np.clip(mutation, -max_mutation, max_mutation)

            individual = individual + mutation

        # 确保在边界内
        individual = np.clip(individual, self.var_bounds[:, 0], self.var_bounds[:, 1])
        return individual

    def _learn_from_other_agents(self, waiter_pop: AgentPopulation) -> np.ndarray:
        """等待者学习其他种群的成功模式"""
        # 收集其他种群的精英
        elites = []
        for role, pop in self.agent_populations.items():
            if role != AgentRole.WAITER and pop.best_individual is not None:
                elites.append(pop.best_individual)

        if elites:
            # 基于精英生成新解
            elite = elites[np.random.randint(len(elites))]
            # 较小的扰动
            child = elite + np.random.randn(len(elite)) * 0.05
        else:
            # 随机生成
            child = self._initialize_agent_population(1, waiter_pop.bias_profile, waiter_pop.role)[0]

        return np.clip(child, self.var_bounds[:, 0], self.var_bounds[:, 1])

    def _exploratory_evolution(self, coordinator_pop: AgentPopulation) -> np.ndarray:
        """协调者的探索性进化"""
        # 结合不同种群的特性
        if np.random.rand() < 0.5:
            # 学习探索者
            return self._mutate_with_bias(
                coordinator_pop.population[np.random.randint(len(coordinator_pop.population))],
                self.agent_populations[AgentRole.EXPLORER].bias_profile
            )
        else:
            # 学习开发者
            return self._crossover_with_bias(
                coordinator_pop.population[np.random.randint(len(coordinator_pop.population))],
                coordinator_pop.population[np.random.randint(len(coordinator_pop.population))],
                self.agent_populations[AgentRole.EXPLOITER].bias_profile
            )

    def _exploitative_evolution(self, coordinator_pop: AgentPopulation) -> np.ndarray:
        """协调者的开发性进化"""
        # 基于当前最优解进行局部搜索
        if coordinator_pop.best_individual is not None:
            best = coordinator_pop.best_individual
            # 小步长搜索
            child = best + np.random.randn(len(best)) * 0.01
        else:
            child = self._initialize_agent_population(1, coordinator_pop.bias_profile, coordinator_pop.role)[0]

        return np.clip(child, self.var_bounds[:, 0], self.var_bounds[:, 1])

    def _generate_advisory_solution(self, advisor_pop: AgentPopulation) -> np.ndarray:
        """
        建议者：基于分析和建议生成新解

        实现三种建议方法：
        1. 基于种群统计分析（基础版）
        2. 基于贝叶斯优化（高级版，需要安装gpy）
        3. 基于机器学习（高级版，需要安装sklearn）
        """
        advisory_method = self.config.get('advisory_method', 'statistical')

        if advisory_method == 'bayesian':
            return self._generate_bayesian_advisory_solution(advisor_pop)
        elif advisory_method == 'ml':
            return self._generate_ml_advisory_solution(advisor_pop)
        else:
            return self._generate_statistical_advisory_solution(advisor_pop)

    def _generate_statistical_advisory_solution(self, advisor_pop: AgentPopulation) -> np.ndarray:
        """基于统计分析的建议（无需额外依赖）"""
        # 收集所有种群的非支配解
        all_solutions = []
        all_objectives = []

        for role, pop in self.agent_populations.items():
            for i, individual in enumerate(pop.population):
                if i < len(pop.objectives):
                    all_solutions.append(individual)
                    all_objectives.append(pop.objectives[i])

        if not all_solutions:
            return self._initialize_agent_population(1, advisor_pop.bias_profile, advisor_pop.role)[0]

        all_solutions = np.array(all_solutions)
        all_objectives = np.array(all_objectives)

        # 分析解的分布特征
        mean_solution = np.mean(all_solutions, axis=0)
        std_solution = np.std(all_solutions, axis=0)

        # 识别有希望的区域（目标值较好的解）
        if len(all_objectives) > 0:
            # 使用加权和来确定"好"的解
            if all_objectives[0] is not None and len(all_objectives[0]) > 0:
                objective_means = np.mean(all_objectives, axis=0)
                # 找到综合目标较好的解
                weighted_scores = []
                for obj in all_objectives:
                    if obj is not None:
                        score = -np.mean(obj)  # 负号因为我们要最小化
                        weighted_scores.append(score)
                    else:
                        weighted_scores.append(0)

                weighted_scores = np.array(weighted_scores)

                # 选择前20%的解
                top_indices = np.argsort(weighted_scores)[-max(1, len(all_solutions) // 5):]
                promising_solutions = all_solutions[top_indices]

                if len(promising_solutions) > 0:
                    # 在有希望的区域生成新解
                    center = np.mean(promising_solutions, axis=0)
                    # 小幅扰动，保持在该区域
                    child = center + np.random.randn(len(center)) * std_solution * 0.3
                else:
                    child = mean_solution + np.random.randn(len(mean_solution)) * std_solution * 0.5
            else:
                child = mean_solution + np.random.randn(len(mean_solution)) * std_solution * 0.5
        else:
            child = mean_solution + np.random.randn(len(mean_solution)) * std_solution * 0.5

        return np.clip(child, self.var_bounds[:, 0], self.var_bounds[:, 1])

    def _generate_bayesian_advisory_solution(self, advisor_pop: AgentPopulation) -> np.ndarray:
        """基于贝叶斯优化的建议（需要gpy库）"""
        try:
            from scipy.optimize import minimize
            from scipy.stats import norm

            # 收集训练数据
            X_train = []
            y_train = []

            for role, pop in self.agent_populations.items():
                for i, individual in enumerate(pop.population):
                    if i < len(pop.objectives) and pop.objectives[i] is not None:
                        X_train.append(individual)
                        # 使用目标值的加权和
                        y_train.append(-np.mean(pop.objectives[i]))  # 负号因为我们要最小化

            if len(X_train) < 5:  # 数据不足，回退到统计方法
                return self._generate_statistical_advisory_solution(advisor_pop)

            X_train = np.array(X_train)
            y_train = np.array(y_train)

            # 简化的采集函数：使用距离加权的方法
            def acquisition_function(x):
                # 计算与已知解的距离
                distances = np.linalg.norm(X_train - x, axis=1)
                # 加权：距离近的解权重高
                weights = np.exp(-distances / distances.mean())
                # 预测值（加权平均）
                predicted = np.sum(weights * y_train) / np.sum(weights)
                # 探索项（鼓励探索未知区域）
                exploration = distances.min() * 0.1
                return predicted + exploration

            # 找到最优解附近的有希望区域
            best_idx = np.argmin(y_train)
            best_solution = X_train[best_idx]

            # 在最优解附近搜索
            result = minimize(
                lambda x: -acquisition_function(x),
                x0=best_solution,
                bounds=[(self.var_bounds[i, 0], self.var_bounds[i, 1]) for i in range(len(best_solution))],
                method='L-BFGS-B'
            )

            if result.success:
                child = result.x
            else:
                child = best_solution + np.random.randn(len(best_solution)) * 0.1

        except ImportError:
            # 没有scipy，回退到统计方法
            return self._generate_statistical_advisory_solution(advisor_pop)
        except Exception as e:
            # 出错，回退到统计方法
            print(f"[Advisor] 贝叶斯建议出错: {e}，使用统计方法")
            return self._generate_statistical_advisory_solution(advisor_pop)

        return np.clip(child, self.var_bounds[:, 0], self.var_bounds[:, 1])

    def _generate_ml_advisory_solution(self, advisor_pop: AgentPopulation) -> np.ndarray:
        """基于机器学习的建议（需要sklearn库）"""
        try:
            from sklearn.ensemble import RandomForestRegressor
            from scipy.stats import norm

            # 收集训练数据
            X_train = []
            y_train = []

            for role, pop in self.agent_populations.items():
                for i, individual in enumerate(pop.population):
                    if i < len(pop.objectives) and pop.objectives[i] is not None:
                        X_train.append(individual)
                        y_train.append(-np.mean(pop.objectives[i]))  # 负号因为我们要最小化

            if len(X_train) < 10:  # 数据不足，回退到统计方法
                return self._generate_statistical_advisory_solution(advisor_pop)

            X_train = np.array(X_train)
            y_train = np.array(y_train)

            # 训练随机森林模型
            model = RandomForestRegressor(n_estimators=50, max_depth=10, random_state=42)
            model.fit(X_train, y_train)

            # 预测当前所有解的目标值
            predictions = model.predict(X_train)

            # 找到预测最好的解
            best_idx = np.argmin(predictions)
            best_solution = X_train[best_idx]

            # 在最优解附近生成新解，结合模型的不确定性
            # 使用随机森林的树方差作为不确定性估计
            tree_predictions = []
            for tree in model.estimators_:
                tree_predictions.append(tree.predict([best_solution])[0])

            uncertainty = np.std(tree_predictions)

            # 在最优解附近探索，步长与不确定性相关
            child = best_solution + np.random.randn(len(best_solution)) * uncertainty * 0.5

        except ImportError:
            # 没有sklearn，回退到统计方法
            return self._generate_statistical_advisory_solution(advisor_pop)
        except Exception as e:
            # 出错，回退到统计方法
            print(f"[Advisor] ML建议出错: {e}，使用统计方法")
            return self._generate_statistical_advisory_solution(advisor_pop)

        return np.clip(child, self.var_bounds[:, 0], self.var_bounds[:, 1])

    def communicate_between_agents(self):
        """智能体间的信息交流"""
        # 收集所有种群的最优解
        global_best = None
        global_best_obj = None
        global_best_constraints = None

        for role, pop in self.agent_populations.items():
            if pop.best_individual is not None:
                # 计算约束违背度
                total_violation = sum(abs(c) for c in (pop.best_constraints or []))

                if global_best is None or \
                   (total_violation == 0 and self._dominates(pop.best_objectives, global_best_obj)) or \
                   (total_violation < sum(abs(c) for c in (global_best_constraints or []))):
                    global_best = pop.best_individual.copy()
                    global_best_obj = pop.best_objectives.copy()
                    global_best_constraints = pop.best_constraints.copy() if pop.best_constraints else []

        # 更新全局最优
        if global_best is not None:
            self.global_best = global_best
            self.global_best_objectives = global_best_obj
            self.global_best_constraints = global_best_constraints

            # 将全局最优解传播到其他种群
            for role, pop in self.agent_populations.items():
                if role != AgentRole.EXPLOITER:  # 开发者保持独立性
                    # 用全局最优替换最差个体
                    if len(pop.population) > 0 and pop.fitness:
                        worst_idx = np.argmin(pop.fitness)
                        pop.population[worst_idx] = global_best + np.random.randn(len(global_best)) * 0.01

        self.stats['communications'] += 1

    def adapt_agent_strategies(self, generation: int):
        """动态调整智能体策略"""
        if not self.config['dynamic_ratios']:
            return

        # 计算各角色的贡献度
        contributions = {}
        for role, pop in self.agent_populations.items():
            if pop.best_objectives is not None:
                total_violation = sum(abs(c) for c in (pop.best_constraints or []))
                if total_violation == 0:
                    contributions[role] = np.mean(pop.best_objectives)
                else:
                    contributions[role] = float('inf')
            else:
                contributions[role] = float('inf')

        # 根据进化阶段调整策略
        progress = generation / self.config['max_generations']

        if progress < 0.3:
            # 早期：增加探索
            self._adjust_bias_parameters(explorer_boost=1.2, exploiter_boost=0.8)
        elif progress < 0.7:
            # 中期：平衡
            self._adjust_bias_parameters(explorer_boost=1.0, exploiter_boost=1.0)
        else:
            # 后期：增加开发
            self._adjust_bias_parameters(explorer_boost=0.7, exploiter_boost=1.3)

        self.stats['adaptations'] += 1

    def _adjust_bias_parameters(self, explorer_boost: float, exploiter_boost: float):
        """调整偏置参数"""
        for role, pop in self.agent_populations.items():
            if role == AgentRole.EXPLORER:
                pop.bias_profile['exploration_rate'] *= explorer_boost
                pop.bias_profile['exploration_rate'] = np.clip(pop.bias_profile['exploration_rate'], 0.1, 1.0)
            elif role == AgentRole.EXPLOITER:
                pop.bias_profile['selection_pressure'] *= exploiter_boost
                pop.bias_profile['selection_pressure'] = np.clip(pop.bias_profile['selection_pressure'], 0.1, 1.0)

    def _dominates(self, obj1: List[float], obj2: List[float]) -> bool:
        """判断obj1是否支配obj2"""
        if obj2 is None:
            return True
        return all(o1 <= o2 for o1, o2 in zip(obj1, obj2)) and any(o1 < o2 for o1, o2 in zip(obj1, obj2))

    def calculate_diversity(self) -> float:
        """计算种群多样性"""
        all_individuals = []
        for pop in self.agent_populations.values():
            all_individuals.extend(pop.population)

        if len(all_individuals) < 2:
            return 0

        # 计算平均距离
        distances = []
        for i in range(len(all_individuals)):
            for j in range(i + 1, len(all_individuals)):
                dist = np.linalg.norm(all_individuals[i] - all_individuals[j])
                distances.append(dist)

        return np.mean(distances)

    def run(self):
        """运行多智能体优化"""
        print(f"[MultiAgent] 开始优化，最大代数: {self.config['max_generations']}")
        start_time = time.time()

        # 初始化偏置系统
        if self.config['use_bias_system'] and hasattr(self.problem, 'bias_manager'):
            self.problem.bias_manager.set_solver_instance(self)

        for generation in range(self.config['max_generations']):
            self.history['generation'] = generation

            # 评估所有种群
            for role, pop in self.agent_populations.items():
                self.evaluate_population(pop)

            # 进化所有种群
            for role, pop in self.agent_populations.items():
                self.evolve_population(pop)

            # 种群间交流
            if generation % self.config['communication_interval'] == 0:
                self.communicate_between_agents()
                print(f"[MultiAgent] Generation {generation}: 信息交流完成")

            # 动态调整策略
            if generation % self.config['adaptation_interval'] == 0:
                self.adapt_agent_strategies(generation)
                print(f"[MultiAgent] Generation {generation}: 策略调整完成")

            # 记录历史
            diversity = self.calculate_diversity()
            self.history['diversity'].append(diversity)

            # 记录全局最优
            if self.global_best_objectives is not None:
                self.history['best_objectives'].append(self.global_best_objectives.copy())

            # 记录各角色贡献
            for role, pop in self.agent_populations.items():
                if pop.best_objectives is not None:
                    self.history['agent_contributions'][role].append(np.mean(pop.best_objectives))

            # 进度报告
            if generation % 10 == 0:
                print(f"[MultiAgent] Generation {generation}:")
                print(f"  多样性: {diversity:.4f}")
                print(f"  评估次数: {self.stats['evaluations']}")
                if self.global_best_objectives:
                    print(f"  全局最优: {self.global_best_objectives}")
                for role, pop in self.agent_populations.items():
                    if pop.best_objectives:
                        total_violation = sum(abs(c) for c in (pop.best_constraints or []))
                        print(f"  {role.value}: {pop.best_objectives} (违规: {total_violation:.2f})")

        # 最终评估
        for role, pop in self.agent_populations.items():
            self.evaluate_population(pop)

        # 收集Pareto前沿
        pareto_front = self._extract_pareto_front()

        end_time = time.time()
        print(f"[MultiAgent] 优化完成！耗时: {end_time - start_time:.2f}秒")
        print(f"[MultiAgent] 总评估次数: {self.stats['evaluations']}")
        print(f"[MultiAgent] 找到 {len(pareto_front)} 个Pareto最优解")

        return pareto_front

    def _extract_pareto_front(self) -> List[Dict]:
        """提取Pareto前沿"""
        all_individuals = []
        all_objectives = []
        all_constraints = []

        # 收集所有种群的个体
        for pop in self.agent_populations.values():
            for i, individual in enumerate(pop.population):
                if i < len(pop.objectives):
                    # 只保留可行解
                    total_violation = sum(abs(c) for c in (pop.constraints[i] if pop.constraints else []))
                    if total_violation == 0:
                        all_individuals.append(individual)
                        all_objectives.append(pop.objectives[i])
                        all_constraints.append(pop.constraints[i] if pop.constraints else [])

        # 提取非支配解
        pareto_front = []
        for i, obj in enumerate(all_objectives):
            dominated = False
            for j, other_obj in enumerate(all_objectives):
                if i != j and self._dominates(other_obj, obj):
                    dominated = True
                    break
            if not dominated:
                pareto_front.append({
                    'solution': all_individuals[i],
                    'objectives': all_objectives[i],
                    'constraints': all_constraints[i]
                })

        return pareto_front

    def get_population(self):
        """获取种群（兼容原始接口）"""
        all_pop = []
        for pop in self.agent_populations.values():
            all_pop.extend(pop.population)
        return all_pop

    def get_objectives(self):
        """获取目标值（兼容原始接口）"""
        all_objs = []
        for pop in self.agent_populations.values():
            all_objs.extend(pop.objectives)
        return all_objs

    def get_constraint_violations(self):
        """获取约束违背度（兼容原始接口）"""
        all_violations = []
        for pop in self.agent_populations.values():
            for constraints in pop.constraints:
                total_violation = sum(abs(c) for c in constraints) if constraints else 0
                all_violations.append(total_violation)
        return all_violations

    def environmental_selection(self, population, objectives, constraint_violations):
        """环境选择（兼容原始接口）"""
        # 在多智能体框架中，这个方法由各角色自行处理
        pass

    # 继承自BaseSolver的其他方法
    def solve(self, max_generations=None, **kwargs):
        """求解接口"""
        if max_generations:
            self.config['max_generations'] = max_generations

        return self.run()

    def get_results(self):
        """获取结果"""
        pareto_front = self._extract_pareto_front()
        return {
            'pareto_front': pareto_front,
            'history': self.history,
            'statistics': self.stats,
            'global_best': {
                'solution': self.global_best,
                'objectives': self.global_best_objectives,
                'constraints': self.global_best_constraints
            } if self.global_best is not None else None
        }
