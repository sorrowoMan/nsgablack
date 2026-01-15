"""Auto-extracted mixin module."""
from __future__ import annotations


import math
import random
from typing import Dict, List, Tuple

import numpy as np

from ..core.population import AgentPopulation

class EvolutionMixin:
    """Mixin for multi-agent solver."""

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
        bounds = self._get_effective_bounds(bias_profile)

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

        # bounds handling
        child1 = self._clip_to_bounds(child1, bounds)
        child2 = self._clip_to_bounds(child2, bounds)

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
        bounds = self._get_effective_bounds(bias_profile)

        for i in range(len(individual)):
            if np.random.rand() < mutation_prob:
                delta_low = (individual[i] - bounds[i, 0]) / (bounds[i, 1] - bounds[i, 0])
                delta_high = (bounds[i, 1] - individual[i]) / (bounds[i, 1] - bounds[i, 0])

                u = np.random.rand()
                delta_q = 0.0

                if u <= 0.5:
                    delta_q = (2.0 * u + (1.0 - 2.0 * u) * (1.0 - delta_low) ** (eta_m + 1.0)) ** (1.0 / (eta_m + 1.0)) - 1.0
                else:
                    delta_q = 1.0 - (2.0 * (1.0 - u) + 2.0 * (u - 0.5) * (1.0 - delta_high) ** (eta_m + 1.0)) ** (1.0 / (eta_m + 1.0))

                mutated[i] = individual[i] + delta_q * (bounds[i, 1] - bounds[i, 0])

        # 边界处理
        mutated = self._clip_to_bounds(mutated, bounds)

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
        bounds = self._get_effective_bounds(bias_profile)
        child = self._clip_to_bounds(child, bounds)
        return child

    def _mutate_with_bias(self, individual: np.ndarray, bias_profile: Dict) -> np.ndarray:
        """带偏置的变异操作（已废弃，保留向后兼容）"""
        if np.random.rand() < bias_profile['mutation_rate']:
            mutation_strength = bias_profile['exploration_rate'] * 0.5
            mutation = np.random.randn(len(individual)) * mutation_strength

            # 限制变异幅度
            bounds = self._get_effective_bounds(bias_profile)
            max_mutation = (bounds[:, 1] - bounds[:, 0]) * 0.2
            mutation = np.clip(mutation, -max_mutation, max_mutation)

            individual = individual + mutation

        # 确保在边界内
        bounds = self._get_effective_bounds(bias_profile)
        individual = self._clip_to_bounds(individual, bounds)
        return individual

