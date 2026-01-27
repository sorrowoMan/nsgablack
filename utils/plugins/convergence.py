"""
收敛检测插件

提供收敛状态监控和提前停止功能
"""

import numpy as np
from typing import Dict, Any
from .base import Plugin


class ConvergencePlugin(Plugin):
    is_algorithmic = True
    """
    收敛检测插件

    功能：监控收敛状态，支持提前停止
    特点：
    - 检测停滞期
    - 计算种群多样性
    - 支持提前停止

    推用于：
    - 需要监控收敛过程的问题
    - 计算资源有限的情况
    """

    def __init__(self, stagnation_window: int = 20, improvement_epsilon: float = 1e-4,
                 diversity_threshold: float = 0.05, min_generations: int = 30,
                 enable_early_stop: bool = False):
        """
        初始化收敛检测插件

        Args:
            stagnation_window: 停滞检测窗口大小
            improvement_epsilon: 改进阈值（小于此值认为停滞）
            diversity_threshold: 多样性阈值（小于此值认为收敛）
            min_generations: 最小代数（之前不停止）
            enable_early_stop: 是否启用提前停止
        """
        super().__init__("convergence")
        self.stagnation_window = stagnation_window
        self.improvement_epsilon = improvement_epsilon
        self.diversity_threshold = diversity_threshold
        self.min_generations = min_generations
        self.enable_early_stop = enable_early_stop

        # 历史数据
        self.best_fitness_history = []
        self.diversity_history = []
        self.stagnation_count = 0

        # 收敛状态
        self.is_converged = False
        self.convergence_generation = None

    def on_solver_init(self, solver):
        """求解器初始化"""
        self.best_fitness_history = []
        self.diversity_history = []
        self.stagnation_count = 0
        self.is_converged = False
        self.convergence_generation = None

    def on_population_init(self, population, objectives, violations):
        """种群初始化"""
        if len(objectives) > 0:
            best_fitness = float(np.min(objectives[:, 0] if objectives.shape[1] == 1 else np.sum(objectives, axis=1)))
            self.best_fitness_history.append(best_fitness)
            self._update_diversity(population)

    def on_generation_start(self, generation: int):
        """代开始"""
        pass

    def on_generation_end(self, generation: int):
        """代结束：检测收敛"""
        if self.solver is None:
            return

        # 记录最优适应度
        if self.solver.objectives.shape[1] == 1:
            best_fitness = float(np.min(self.solver.objectives[:, 0]))
        else:
            best_fitness = float(np.min(np.sum(self.solver.objectives, axis=1)))

        self.best_fitness_history.append(best_fitness)

        # 更新多样性
        self._update_diversity(self.solver.population)

        # 检测停滞
        if len(self.best_fitness_history) >= self.stagnation_window:
            recent_best = self.best_fitness_history[-self.stagnation_window:]
            improvement = recent_best[0] - recent_best[-1]

            if abs(improvement) < self.improvement_epsilon * abs(recent_best[0]):
                self.stagnation_count += self.stagnation_window
            else:
                self.stagnation_count = 0

        # 检测收敛
        current_diversity = self.diversity_history[-1] if self.diversity_history else 1.0

        if (generation >= self.min_generations and
            self.stagnation_count >= self.stagnation_window and
            current_diversity < self.diversity_threshold):
            self.is_converged = True
            self.convergence_generation = generation
            print(f"[Convergence] 检测到收敛于第 {generation} 代")
            print(f"[Convergence] 最终适应度: {best_fitness:.6f}")
            print(f"[Convergence] 种群多样性: {current_diversity:.6f}")

            # 提前停止
            if self.enable_early_stop:
                print(f"[Convergence] 启用提前停止")
                self.solver.running = False

    def on_solver_finish(self, result: Dict[str, Any]):
        """求解器结束"""
        result['convergence_detected'] = self.is_converged
        result['convergence_generation'] = self.convergence_generation
        result['final_diversity'] = self.diversity_history[-1] if self.diversity_history else None
        result['stagnation_count'] = self.stagnation_count

        if self.is_converged:
            print(f"\n[Convergence Summary]")
            print(f"  收敛代数: {self.convergence_generation}")
            print(f"  最终适应度: {self.best_fitness_history[-1]:.6f}")
            print(f"  最终多样性: {self.diversity_history[-1]:.6f}")

    def _update_diversity(self, population: np.ndarray):
        """更新种群多样性"""
        if len(population) < 2:
            self.diversity_history.append(0.0)
            return

        # 归一化
        pop_min = population.min(axis=0)
        pop_max = population.max(axis=0)
        pop_range = pop_max - pop_min + 1e-10
        pop_norm = (population - pop_min) / pop_range

        # 计算多样性（采样以减少开销）
        n_samples = min(30, len(pop_norm))
        indices = np.random.choice(len(pop_norm), n_samples, replace=False)
        samples = pop_norm[indices]

        distances = []
        for i in range(n_samples):
            for j in range(i + 1, n_samples):
                dist = np.linalg.norm(samples[i] - samples[j])
                distances.append(dist)

        diversity = float(np.mean(distances)) if distances else 0.0
        self.diversity_history.append(diversity)

    def get_convergence_info(self) -> Dict[str, Any]:
        """获取收敛信息"""
        return {
            'is_converged': self.is_converged,
            'convergence_generation': self.convergence_generation,
            'stagnation_count': self.stagnation_count,
            'current_diversity': self.diversity_history[-1] if self.diversity_history else None,
            'best_fitness_history': self.best_fitness_history.copy(),
            'diversity_history': self.diversity_history.copy()
        }
