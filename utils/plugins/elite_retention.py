"""
精英保留插件

提供两种精英保留策略：
1. BasicElitePlugin: 基础精英保留（适用于所有问题）
2. HistoricalElitePlugin: 历史替换精英保留（仅适用于连续问题）
"""

import numpy as np
from typing import Dict, Any
from .base import Plugin


class BasicElitePlugin(Plugin):
    is_algorithmic = True
    """
    基础精英保留插件

    功能：确保最优解不会在进化过程中丢失
    特点：
    - 不使用历史解
    - 适用于所有问题类型（连续、离散、混合）
    - 性能开销小

    推荐用于：
    - VRP、TSP等离散优化
    - 组合优化
    - 调度问题
    """

    def __init__(self, retention_prob: float = 0.9, retention_ratio: float = 0.1):
        """
        初始化基础精英保留插件

        Args:
            retention_prob: 精英保留概率（默认0.9）
            retention_ratio: 精英保留比例（默认0.1，即10%的最优解）
        """
        super().__init__("basic_elite")
        self.retention_prob = retention_prob
        self.retention_ratio = retention_ratio

        # 全局最优解
        self.best_solution = None
        self.best_objectives = None
        self.best_fitness = float('inf')

        # 历史记录
        self.fitness_history = []

    def on_solver_init(self, solver):
        """求解器初始化"""
        self.best_solution = None
        self.best_objectives = None
        self.best_fitness = float('inf')
        self.fitness_history = []

    def on_population_init(self, population, objectives, violations):
        """种群初始化后记录最优解"""
        self._update_best_solution(population, objectives)

    def on_generation_start(self, generation: int):
        """代开始：什么都不做"""
        pass

    def on_generation_end(self, generation: int):
        """
        代结束：确保最优解被保留

        策略：
        1. 记录当前最优解
        2. 如果需要，替换最差个体为全局最优解
        """
        if self.solver is None:
            return

        # 更新全局最优
        self._update_best_solution(self.solver.population, self.solver.objectives)
        self.fitness_history.append(self.best_fitness)

        # 精英保留：以一定概率替换最差个体
        if np.random.random() < self.retention_prob:
            if self.best_solution is not None:
                self._retain_elites()

    def on_solver_finish(self, result: Dict[str, Any]):
        """求解器结束"""
        result['best_solution'] = self.best_solution
        result['best_fitness'] = self.best_fitness
        result['fitness_history'] = self.fitness_history

    def _update_best_solution(self, population, objectives):
        """更新全局最优解"""
        if len(objectives) == 0:
            return

        # 单目标或多目标（用加权和）
        if objectives.shape[1] == 1:
            fitness_values = objectives[:, 0]
        else:
            # 简单加权和（多目标）
            fitness_values = np.sum(objectives, axis=1)

        best_idx = np.argmin(fitness_values)
        current_best_fitness = float(fitness_values[best_idx])

        # 更新全局最优
        if current_best_fitness < self.best_fitness:
            self.best_fitness = current_best_fitness
            self.best_solution = population[best_idx].copy()
            self.best_objectives = objectives[best_idx].copy()

    def _retain_elites(self):
        """保留精英个体"""
        if self.solver is None or self.best_solution is None:
            return

        pop_size = len(self.solver.population)
        n_retain = max(1, int(pop_size * self.retention_ratio))

        # 找到最差的n_retain个个体
        if self.solver.objectives.shape[1] == 1:
            fitness_values = self.solver.objectives[:, 0]
        else:
            fitness_values = np.sum(self.solver.objectives, axis=1)

        worst_indices = np.argsort(fitness_values)[-n_retain:]

        # 替换为全局最优解（带小扰动以保持多样性）
        for idx in worst_indices:
            # 添加小扰动
            perturbation = np.random.normal(0, 0.01, self.best_solution.shape)
            perturbed_solution = self.best_solution + perturbation

            # 如果使用Pipeline，让Pipeline修复边界
            if self.solver.representation_pipeline is not None:
                context = {'generation': self.solver.generation, 'bounds': self.solver.var_bounds}
                # 使用变异操作来修复
                perturbed_solution = self.solver.representation_pipeline.mutate(
                    self.best_solution, context
                )
            else:
                # 简单裁剪到边界
                for j in range(self.solver.dimension):
                    min_val, max_val = self.solver.var_bounds[j]
                    perturbed_solution[j] = np.clip(perturbed_solution[j], min_val, max_val)

            self.solver.population[idx] = perturbed_solution
            # 重新评估
            obj, vio = self.solver._evaluate_individual(perturbed_solution)
            self.solver.objectives[idx] = obj
            self.solver.constraint_violations[idx] = vio
            # 对齐求解器评估计数（与 evaluate_population 行为一致）
            self.solver.evaluation_count += 1


class HistoricalElitePlugin(Plugin):
    is_algorithmic = True
    """
    历史替换精英保留插件

    警告：仅适用于连续优化问题！

    功能：使用历史最优解替换当前精英
    特点：
    - 维护历史精英档案
    - 从历史档案中采样替换
    - 可能帮助跳出局部最优

    仅推荐用于：
    - 连续函数优化
    - 参数优化
    - 神经网络超参数优化

    不适用于：
    - VRP、TSP等离散问题 ❌
    - 图论问题 ❌
    - 组合优化 ❌
    """

    def __init__(self, history_size: int = 50, replacement_prob: float = 0.1,
                 replacement_ratio: float = 0.1):
        """
        初始化历史替换精英保留插件

        Args:
            history_size: 历史档案大小
            replacement_prob: 历史替换概率
            replacement_ratio: 历史替换比例
        """
        super().__init__("historical_elite")
        self.history_size = history_size
        self.replacement_prob = replacement_prob
        self.replacement_ratio = replacement_ratio

        # 历史精英档案
        self.elite_archive = []

        # 全局最优
        self.best_solution = None
        self.best_fitness = float('inf')

    def on_solver_init(self, solver):
        """求解器初始化"""
        self.elite_archive = []
        self.best_solution = None
        self.best_fitness = float('inf')

    def on_population_init(self, population, objectives, violations):
        """种群初始化"""
        self._update_best_and_archive(population, objectives, 0)

    def on_generation_start(self, generation: int):
        """代开始"""
        pass

    def on_generation_end(self, generation: int):
        """
        代结束：历史替换

        策略：
        1. 更新历史精英档案
        2. 以一定概率从历史档案中采样替换当前精英
        """
        if self.solver is None or not self.enabled:
            return

        # 更新历史
        self._update_best_and_archive(
            self.solver.population,
            self.solver.objectives,
            generation
        )

        # 历史替换
        if np.random.random() < self.replacement_prob:
            if len(self.elite_archive) > 0:
                self._historical_replacement()

    def on_solver_finish(self, result: Dict[str, Any]):
        """求解器结束"""
        result['elite_archive_size'] = len(self.elite_archive)
        result['historical_replacement_used'] = True

    def _update_best_and_archive(self, population, objectives, generation: int):
        """更新全局最优和历史档案"""
        if len(objectives) == 0:
            return

        # 计算适应度
        if objectives.shape[1] == 1:
            fitness_values = objectives[:, 0]
        else:
            fitness_values = np.sum(objectives, axis=1)

        best_idx = np.argmin(fitness_values)
        current_best_fitness = float(fitness_values[best_idx])

        # 更新全局最优
        if current_best_fitness < self.best_fitness:
            self.best_fitness = current_best_fitness
            self.best_solution = population[best_idx].copy()

        # 添加到精英档案
        candidate = {
            'individual': population[best_idx].copy(),
            'objectives': objectives[best_idx].copy(),
            'fitness': current_best_fitness,
            'generation': generation
        }

        # 检查是否重复
        is_duplicate = False
        for elite in self.elite_archive:
            if np.linalg.norm(candidate['individual'] - elite['individual']) < 1e-6:
                is_duplicate = True
                # 如果新解更好，更新
                if candidate['fitness'] < elite['fitness']:
                    elite.update(candidate)
                break

        # 添加新精英
        if not is_duplicate:
            self.elite_archive.append(candidate)
            # 限制档案大小
            if len(self.elite_archive) > self.history_size:
                # 移除最差的
                worst_idx = np.argmax([e['fitness'] for e in self.elite_archive])
                self.elite_archive.pop(worst_idx)

    def _historical_replacement(self):
        """从历史档案中采样并替换"""
        if self.solver is None or len(self.elite_archive) == 0:
            return

        pop_size = len(self.solver.population)
        n_replace = max(1, int(pop_size * self.replacement_ratio))

        # 从历史档案中随机采样（最近的更好）
        recent_elites = self.elite_archive[-min(self.history_size // 2, len(self.elite_archive)):]
        if len(recent_elites) == 0:
            return

        n_sample = min(n_replace, len(recent_elites))
        selected_indices = np.random.choice(len(recent_elites), n_sample, replace=False)

        # 找到当前种群中最差的个体
        if self.solver.objectives.shape[1] == 1:
            fitness_values = self.solver.objectives[:, 0]
        else:
            fitness_values = np.sum(self.solver.objectives, axis=1)

        worst_indices = np.argsort(fitness_values)[-n_sample:]

        # 替换
        for i, elite_idx in enumerate(selected_indices):
            pop_idx = worst_indices[i]
            historical_elite = recent_elites[elite_idx]

            # 添加小扰动
            perturbation = np.random.normal(0, 0.02, historical_elite['individual'].shape)
            new_individual = historical_elite['individual'] + perturbation

            # 边界修复
            if self.solver.representation_pipeline is not None:
                context = {'generation': self.solver.generation, 'bounds': self.solver.var_bounds}
                new_individual = self.solver.representation_pipeline.mutate(
                    historical_elite['individual'], context
                )
            else:
                for j in range(self.solver.dimension):
                    min_val, max_val = self.solver.var_bounds[j]
                    new_individual[j] = np.clip(new_individual[j], min_val, max_val)

            # 替换
            self.solver.population[pop_idx] = new_individual
            obj, vio = self.solver._evaluate_individual(new_individual)
            self.solver.objectives[pop_idx] = obj
            self.solver.constraint_violations[pop_idx] = vio
