"""Auto-extracted mixin module."""
from __future__ import annotations


import random
from typing import List, Optional

import numpy as np
from ..core.role import AgentRole
from ..core.population import AgentPopulation

class CommunicationMixin:
    """Mixin for multi-agent solver."""

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
                        candidate = global_best + np.random.randn(len(global_best)) * 0.01
                        bounds = self._get_effective_bounds(pop.bias_profile)
                        pop.population[worst_idx] = self._clip_to_bounds(candidate, bounds)

        # update archives and share candidates
        self._update_archives()
        if self.config.get('archive_enabled', True):
            share_k = int(self.config.get('archive_share_k', 0))
            if share_k > 0:
                for role, pop in self.agent_populations.items():
                    candidates = self._select_archive_candidates(role, share_k)
                    self._inject_archive_candidates(pop, candidates)
            sizes = {name: len(self.archives.get(name, [])) for name in self.archives}
            for name, size in sizes.items():
                self.history['archive_sizes'][name].append(size)

        self.stats['communications'] += 1

    def adapt_agent_strategies(self, generation: int):
        """动态调整智能体策略"""
        if not self.config['dynamic_ratios']:
            return

        scores = self._compute_role_scores()
        if scores:
            self._update_role_ratios(scores)

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

        if self.config.get('region_partition', False):
            self._update_region_partition(generation)

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

    def _reassign_waiter_pool(self, generation: int) -> None:
        """Use waiter pool as a reserve to strengthen target roles."""
        interval = int(self.config.get('waiter_reassign_interval', 1))
        if interval <= 0 or generation % interval != 0:
            return

        waiter_pop = self.agent_populations.get(AgentRole.WAITER)
        if waiter_pop is None or not waiter_pop.population:
            return

        ratio = float(self.config.get('waiter_reassign_ratio', 0.0))
        if ratio <= 0:
            return

        min_ratio = float(self.config.get('min_role_ratio', 0.05))
        total_pop = int(self.config.get('total_population', 0))
        min_reserve = int(total_pop * min_ratio)
        available = max(0, len(waiter_pop.population) - min_reserve)
        if available <= 0:
            return

        move_count = min(available, max(1, int(len(waiter_pop.population) * ratio)))
        targets = self._resolve_role_list(self.config.get('waiter_reassign_targets'))
        if not targets:
            targets = self._pick_top_roles()

        if not targets:
            return

        base = move_count // len(targets)
        remainder = move_count % len(targets)
        for role in targets:
            if role == AgentRole.WAITER:
                continue
            count = base + (1 if remainder > 0 else 0)
            remainder = max(0, remainder - 1)
            moved = self._take_waiter_individuals(waiter_pop, count)
            self._append_individuals(self.agent_populations[role], moved)

    def _pick_top_roles(self) -> List[AgentRole]:
        roles = []
        for role, pop in self.agent_populations.items():
            if role == AgentRole.WAITER:
                continue
            roles.append((role, float(getattr(pop, 'score', 0.0))))
        if not roles:
            return []
        roles.sort(key=lambda r: r[1], reverse=True)
        return [role for role, _ in roles[:2]]

    def _resolve_role_list(self, roles, default: Optional[List[AgentRole]] = None) -> List[AgentRole]:
        if roles is None:
            return default or []
        resolved = []
        for role in roles:
            if isinstance(role, AgentRole):
                resolved.append(role)
            else:
                try:
                    resolved.append(AgentRole(role))
                except Exception:
                    continue
        return resolved or (default or [])

    def _take_waiter_individuals(self, waiter_pop: AgentPopulation, count: int) -> List[np.ndarray]:
        if count <= 0 or not waiter_pop.population:
            return []
        count = min(count, len(waiter_pop.population))
        if waiter_pop.fitness and len(waiter_pop.fitness) == len(waiter_pop.population):
            best_idx = np.argsort(waiter_pop.fitness)[-count:].tolist()
        else:
            best_idx = random.sample(range(len(waiter_pop.population)), k=count)

        individuals = [waiter_pop.population[i].copy() for i in best_idx]
        for idx in sorted(best_idx, reverse=True):
            del waiter_pop.population[idx]
            if waiter_pop.objectives and idx < len(waiter_pop.objectives):
                del waiter_pop.objectives[idx]
            if waiter_pop.constraints and idx < len(waiter_pop.constraints):
                del waiter_pop.constraints[idx]
            if waiter_pop.fitness and idx < len(waiter_pop.fitness):
                del waiter_pop.fitness[idx]

        waiter_pop.best_individual = None
        waiter_pop.best_objectives = None
        waiter_pop.best_constraints = None
        return individuals

    def _append_individuals(self, pop: AgentPopulation, individuals: List[np.ndarray]) -> None:
        if not individuals:
            return
        pop.population.extend(individuals)
        pop.objectives = []
        pop.constraints = []
        pop.fitness = []
        pop.best_individual = None
        pop.best_objectives = None
        pop.best_constraints = None

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

