"""Auto-extracted mixin module."""
from __future__ import annotations


import random
from typing import List
import numpy as np
from ..core.role import AgentRole
from ..core.population import AgentPopulation

class RoleLogicMixin:
    """Mixin for multi-agent solver."""

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

        bounds = self._get_effective_bounds(waiter_pop.bias_profile)
        return self._clip_to_bounds(child, bounds)

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

        bounds = self._get_effective_bounds(coordinator_pop.bias_profile)
        return self._clip_to_bounds(child, bounds)

    def _remove_worst(self, pop: AgentPopulation, count: int) -> None:
        if count <= 0 or not pop.population:
            return
        if pop.fitness and len(pop.fitness) == len(pop.population):
            worst_idx = np.argsort(pop.fitness)[:count].tolist()
        else:
            worst_idx = random.sample(range(len(pop.population)), k=min(count, len(pop.population)))
        for idx in sorted(worst_idx, reverse=True):
            del pop.population[idx]
            if pop.objectives and idx < len(pop.objectives):
                del pop.objectives[idx]
            if pop.constraints and idx < len(pop.constraints):
                del pop.constraints[idx]
            if pop.fitness and idx < len(pop.fitness):
                del pop.fitness[idx]
        pop.best_individual = None
        pop.best_objectives = None
        pop.best_constraints = None

    def _add_individuals(self, pop: AgentPopulation, count: int, role: AgentRole) -> None:
        if count <= 0:
            return
        new_individuals = []
        seed_ratio = float(self.config.get('archive_seed_ratio', 0.0))
        seed_k = int(count * seed_ratio)
        if seed_k > 0:
            seeds = self._select_archive_candidates(role, seed_k)
            new_individuals.extend(seeds)
        remaining = count - len(new_individuals)
        if remaining > 0:
            pipeline = self._get_representation_pipeline(role)
            new_individuals.extend(self._initialize_agent_population(remaining, pop.bias_profile, role, pipeline))

        if new_individuals:
            pop.population.extend(new_individuals)
            pop.objectives = []
            pop.constraints = []
            pop.fitness = []
            pop.best_individual = None
            pop.best_objectives = None
            pop.best_constraints = None

