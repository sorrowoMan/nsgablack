"""
自适应参数调整插件

根据种群的收敛状态动态调整交叉率和变异率
"""

import numpy as np
from typing import Dict, Any
from .base import Plugin


class AdaptiveParametersPlugin(Plugin):
    is_algorithmic = True
    """
    自适应参数调整插件

    功能：根据种群的改进情况动态调整交叉率和变异率
    特点：
    - 监控种群的改进趋势
    - 停滞时增加探索（提高变异率）
    - 快速改进时加强开发（提高交叉率）
    - 适用于所有优化问题

    推荐用于：
    - 连续优化问题
    - 需要平衡探索和开发的问题
    - 复杂的多模态优化问题
    """

    def __init__(self,
                 stagnation_window: int = 10,
                 improvement_threshold: float = 0.001,
                 min_mutation_rate: float = 0.05,
                 max_mutation_rate: float = 0.4,
                 min_crossover_rate: float = 0.5,
                 max_crossover_rate: float = 0.95):
        """
        初始化自适应参数插件

        Args:
            stagnation_window: 停滞检测窗口（多少代没有显著改进）
            improvement_threshold: 改进阈值（小于此值视为停滞）
            min_mutation_rate: 最小变异率
            max_mutation_rate: 最大变异率
            min_crossover_rate: 最小交叉率
            max_crossover_rate: 最大交叉率
        """
        super().__init__("adaptive_parameters")

        # 参数
        self.stagnation_window = stagnation_window
        self.improvement_threshold = improvement_threshold
        self.min_mutation_rate = min_mutation_rate
        self.max_mutation_rate = max_mutation_rate
        self.min_crossover_rate = min_crossover_rate
        self.max_crossover_rate = max_crossover_rate

        # 状态跟踪
        self.best_fitness_history = []
        self.stagnation_count = 0

        # 记录初始参数
        self.initial_crossover_rate = None
        self.initial_mutation_rate = None

        # 统计信息
        self.adaptation_history = []  # 记录参数调整历史

    def on_solver_init(self, solver):
        """求解器初始化"""
        self.best_fitness_history = []
        self.stagnation_count = 0
        self.adaptation_history = []

        # 保存初始参数
        self.initial_crossover_rate = solver.crossover_rate
        self.initial_mutation_rate = solver.mutation_rate

        print(f"[INFO] AdaptiveParametersPlugin: 初始参数")
        print(f"      crossover_rate={solver.crossover_rate:.3f}")
        print(f"      mutation_rate={solver.mutation_rate:.3f}")

    def on_population_init(self, population, objectives, violations):
        """种群初始化后记录初始适应度"""
        best_fitness = self._get_best_fitness(objectives)
        self.best_fitness_history.append(best_fitness)

    def on_generation_start(self, generation: int):
        """代开始：什么都不做"""
        pass

    def on_generation_end(self, generation: int):
        """
        代结束：评估改进情况并调整参数

        策略：
        1. 计算当前代的最优适应度
        2. 与历史最优比较
        3. 如果连续N代没有显著改进，增加变异率
        4. 如果改进显著，适当降低变异率，提高交叉率
        """
        if self.solver is None or not self.enabled:
            return

        # 获取当前最优
        current_best = self._get_best_fitness(self.solver.objectives)
        self.best_fitness_history.append(current_best)

        # 检查改进
        if len(self.best_fitness_history) >= 2:
            improvement = self.best_fitness_history[-2] - current_best

            if improvement > self.improvement_threshold:
                # 有显著改进
                self.stagnation_count = 0
                self._adjust_parameters("improving", generation)
            else:
                # 没有显著改进
                self.stagnation_count += 1

                if self.stagnation_count >= self.stagnation_window:
                    # 检测到停滞
                    self._adjust_parameters("stagnant", generation)
                    self.stagnation_count = 0  # 重置计数

    def on_solver_finish(self, result: Dict[str, Any]):
        """求解器结束"""
        result['adaptation_history'] = self.adaptation_history
        result['final_crossover_rate'] = self.solver.crossover_rate
        result['final_mutation_rate'] = self.solver.mutation_rate

        print(f"[INFO] AdaptiveParametersPlugin: 最终参数")
        print(f"      crossover_rate={self.solver.crossover_rate:.3f}")
        print(f"      mutation_rate={self.solver.mutation_rate:.3f}")
        print(f"      参数调整次数={len(self.adaptation_history)}")

    def _get_best_fitness(self, objectives):
        """获取最优适应度"""
        if objectives.shape[1] == 1:
            # 单目标
            return float(np.min(objectives[:, 0]))
        else:
            # 多目标：使用加权和
            fitness_values = np.sum(objectives, axis=1)
            return float(np.min(fitness_values))

    def _adjust_parameters(self, state: str, generation: int):
        """
        调整参数

        Args:
            state: "improving" 或 "stagnant"
            generation: 当前代数
        """
        if state == "stagnant":
            # 停滞：增加探索，提高变异率
            old_mutation = self.solver.mutation_rate
            old_crossover = self.solver.crossover_rate

            # 增加变异率（步长0.05）
            self.solver.mutation_rate = min(
                self.max_mutation_rate,
                self.solver.mutation_rate + 0.05
            )

            # 略微降低交叉率（平衡探索和开发）
            self.solver.crossover_rate = max(
                self.min_crossover_rate,
                self.solver.crossover_rate - 0.03
            )

            action = "stagnant"

        elif state == "improving":
            # 正在改进：加强开发，提高交叉率，降低变异率
            old_mutation = self.solver.mutation_rate
            old_crossover = self.solver.crossover_rate

            # 降低变异率
            self.solver.mutation_rate = max(
                self.min_mutation_rate,
                self.solver.mutation_rate - 0.02
            )

            # 提高交叉率
            self.solver.crossover_rate = min(
                self.max_crossover_rate,
                self.solver.crossover_rate + 0.03
            )

            action = "improving"

        else:
            return

        # 记录调整历史
        record = {
            'generation': generation,
            'action': action,
            'old_mutation_rate': old_mutation,
            'new_mutation_rate': self.solver.mutation_rate,
            'old_crossover_rate': old_crossover,
            'new_crossover_rate': self.solver.crossover_rate
        }
        self.adaptation_history.append(record)

        # 每5代打印一次
        if generation % 5 == 0:
            print(f"  [Gen {generation}] AdaptiveParameters: {action}")
            print(f"    mutation_rate: {old_mutation:.3f} -> {self.solver.mutation_rate:.3f}")
            print(f"    crossover_rate: {old_crossover:.3f} -> {self.solver.crossover_rate:.3f}")
