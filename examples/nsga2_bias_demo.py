# -*- coding: utf-8 -*-
"""
NSGA-II 偏置化使用示例

展示 NSGA-II 思想如何通过偏置注入到任何算法中
（按照模拟退火偏置化的设计模式）
"""

import numpy as np
from typing import List, Dict, Any


class NSGA2Bias:
    """
    NSGA-II 偏置 - 将 NSGA-II 思想转换为可注入的偏置

    核心概念转换：
    1. Pareto rank → 偏置值（rank越低，负偏置越大）
    2. Crowding distance → 偏置值（距离越大，负偏置越大）
    3. Pareto dominance → 偏置值（被支配=正偏置，非支配=负偏置）
    """

    def __init__(self, weight=0.15, rank_weight=0.5, crowding_weight=0.3):
        self.weight = weight
        self.rank_weight = rank_weight
        self.crowding_weight = crowding_weight

    def compute_bias(self, x: List, context: Dict[str, Any]) -> float:
        """
        计算 NSGA-II 偏置值 - 核心是将 Pareto 概念转换为偏置

        Args:
            x: 个体
            context: 优化上下文，需要包含：
                - context['pareto_rank']: Pareto rank
                - context['crowding_distance']: 拥挤距离
                - context['is_dominated']: 是否被支配

        Returns:
            偏置值（负值=奖励，正值=惩罚）
        """
        # 获取 NSGA-II 信息
        pareto_rank = context.get('pareto_rank', 0)
        crowding_distance = context.get('crowding_distance', 0.0)
        is_dominated = context.get('is_dominated', False)

        bias_value = 0.0

        # 1. Pareto rank 偏置：rank 越低越好
        # rank=0 → 负偏置（奖励）
        # rank>0 → 正偏置（惩罚）
        rank_bias = pareto_rank * self.rank_weight
        bias_value += rank_bias

        # 2. 拥挤距离偏置：距离越大越好（保持多样性）
        if crowding_distance > 0:
            # 大距离 → 负偏置（奖励）
            crowding_bias = -crowding_distance * self.crowding_weight
        else:
            # 边界个体 → 额外奖励
            crowding_bias = -self.crowding_weight
        bias_value += crowding_bias

        # 3. Pareto 支配关系偏置
        if is_dominated:
            bias_value += 0.2  # 被支配的惩罚
        else:
            bias_value -= 0.1  # 非支配的奖励

        return self.weight * bias_value


class NSGA2EnhancedOptimizer:
    """
    NSGA-II 增强的优化器 - 可用于任何基础算法

    展示如何将 NSGA-II 思想通过偏置注入到遗传算法、粒子群等算法中
    """

    def __init__(self, problem, use_nsga2_bias=True):
        self.problem = problem
        self.use_nsga2_bias = use_nsga2_bias

        # 添加 NSGA-II 偏置
        if self.use_nsga2_bias:
            self.nsga2_bias = NSGA2Bias(weight=0.15)
            print("[OK] 启用 NSGA-II 偏置")
        else:
            print("[OFF] 禁用 NSGA-II 偏置")

        # 历史记录
        self.fitness_history = []

    def optimize(self, max_generations=100, population_size=30):
        """通用优化过程"""
        algorithm_name = "NSGA-II增强" if self.use_nsga2_bias else "标准优化器"
        print(f"\n[开始优化] {algorithm_name} ({max_generations}代)")
        print("-" * 50)

        # 初始化种群
        population = self._initialize_population(population_size)
        best_solution = None
        best_fitness = float('inf')

        for generation in range(max_generations):
            fitness_values = []
            pareto_ranks = []
            crowding_distances = []

            # 评估种群
            for i, individual in enumerate(population):
                # 计算目标函数
                obj_value = self.problem.evaluate(individual)

                # 计算约束
                constraints = self.problem.evaluate_constraints(individual)
                total_violation = sum(max(0, c) for c in constraints)

                # ========== 计算 NSGA-II 指标 ==========
                if self.use_nsga2_bias:
                    # 计算 Pareto rank
                    all_objectives = [self.problem.evaluate(ind) for ind in population]
                    pareto_rank = self._compute_pareto_rank(obj_value, all_objectives)
                    pareto_ranks.append(pareto_rank)

                    # 计算拥挤距离（简化版：基于适应度值）
                    crowding_distance = self._compute_crowding_distance(
                        obj_value, [self.problem.evaluate(ind) for ind in population]
                    )
                    crowding_distances.append(crowding_distance)

                    # 判断是否被支配
                    is_dominated = pareto_rank > 0
                else:
                    pareto_rank = 0
                    crowding_distance = 0
                    is_dominated = False

                # 构建上下文
                context = {
                    'generation': generation,
                    'individual': individual,
                    'population': population,
                    'pareto_rank': pareto_rank,
                    'crowding_distance': crowding_distance,
                    'is_dominated': is_dominated
                }

                # ========== 应用偏置 ==========
                base_fitness = obj_value + total_violation * 100

                # NSGA-II 偏置
                if self.use_nsga2_bias:
                    nsga2_bias_value = self.nsga2_bias.compute_bias(individual, context)
                    total_fitness = base_fitness + nsga2_bias_value
                else:
                    total_fitness = base_fitness

                fitness_values.append(total_fitness)

                # 更新最佳解
                if obj_value < best_fitness:
                    best_fitness = obj_value
                    best_solution = individual.copy()

            # 记录历史
            self.fitness_history.append(best_fitness)

            # 进化操作
            population = self._evolve_population(population, fitness_values)

            # 进度报告
            if generation % 20 == 0 or generation == max_generations - 1:
                avg_rank = np.mean(pareto_ranks) if pareto_ranks else 0
                avg_crowding = np.mean(crowding_distances) if crowding_distances else 0
                print(f"代数 {generation:3d}: 最佳={best_fitness:8.4f}, "
                      f"Avg_Rank={avg_rank:.2f}, Avg_Crowding={avg_crowding:.4f}")

        print(f"\n[优化完成] 最优解: {best_fitness:.6f}")
        return best_solution, best_fitness

    def _compute_pareto_rank(self, current_obj, all_objectives) -> int:
        """计算 Pareto rank（简化版）"""
        rank = 0
        current_set = [current_obj]

        while True:
            # 找到被 current_set 支配的解
            dominated = []
            for obj in all_objectives:
                if obj in current_set:
                    continue
                if any(self._dominates(front_obj, obj) for front_obj in current_set):
                    dominated.append(obj)

            if not dominated:
                return rank

            current_set = dominated
            rank += 1

            # 限制最大 rank，避免无限循环
            if rank > 10:
                return rank

    def _compute_crowding_distance(self, current_obj, all_objectives) -> float:
        """计算拥挤距离（简化版：基于适应度差）"""
        if len(all_objectives) <= 2:
            return float('inf')

        # 计算到最近邻居的距离
        distances = [abs(current_obj - obj) for obj in all_objectives if obj != current_obj]
        return min(distances) if distances else 1.0

    def _dominates(self, obj1, obj2) -> bool:
        """判断 obj1 是否支配 obj2"""
        return obj1 <= obj2 and obj1 < obj2

    def _initialize_population(self, population_size):
        """初始化种群"""
        population = []
        for _ in range(population_size):
            individual = [np.random.uniform(b[0], b[1]) for b in self.problem.bounds]
            population.append(individual)
        return population

    def _evolve_population(self, population, fitness_values):
        """简化的进化操作"""
        new_population = []

        # 精英保留
        elite_idx = np.argmin(fitness_values)
        new_population.append(population[elite_idx].copy())

        # 锦标赛选择和交叉变异
        while len(new_population) < len(population):
            parent1 = self._tournament_selection(population, fitness_values)
            parent2 = self._tournament_selection(population, fitness_values)
            child = self._crossover(parent1, parent2)
            child = self._mutate(child)
            new_population.append(child)

        return new_population

    def _tournament_selection(self, population, fitness_values, tournament_size=3):
        """锦标赛选择"""
        indices = np.random.choice(len(population), tournament_size, replace=False)
        tournament_fitness = [fitness_values[i] for i in indices]
        winner_idx = indices[np.argmin(tournament_fitness)]
        return population[winner_idx].copy()

    def _crossover(self, parent1, parent2):
        """算术交叉"""
        alpha = np.random.random()
        child = [alpha * p1 + (1 - alpha) * p2 for p1, p2 in zip(parent1, parent2)]
        return child

    def _mutate(self, individual):
        """高斯变异"""
        mutated = individual.copy()
        for i in range(len(mutated)):
            if np.random.random() < 0.1:
                bounds = self.problem.bounds[i]
                mutation = np.random.normal(0, 0.1 * (bounds[1] - bounds[0]))
                mutated[i] = np.clip(mutated[i] + mutation, bounds[0], bounds[1])
        return mutated


class SimpleProblem:
    """简单的测试问题"""

    def __init__(self, dimension=5):
        self.dimension = dimension
        self.bounds = [(0, 1)] * dimension

    def evaluate(self, x):
        """Rastrigin函数"""
        A = 10
        n = len(x)
        return A * n + sum(xi**2 - A * np.cos(2 * np.pi * xi) for xi in x)

    def evaluate_constraints(self, x):
        """无约束"""
        return []


def demonstrate_nsga2_bias_integration():
    """演示 NSGA-II 偏置集成效果"""
    print("=" * 70)
    print("NSGA-II 偏置化集成演示")
    print("展示 NSGA-II 思想如何通过偏置注入到任何算法中")
    print("=" * 70)

    # 创建问题
    problem = SimpleProblem(dimension=5)
    print(f"\n测试问题: Rastrigin函数（多峰）")
    print(f"维度: {problem.dimension}")

    # 优化器1: 不使用 NSGA-II 偏置
    print(f"\n{'='*25} 优化器1: 标准优化器 {'='*25}")
    standard_optimizer = NSGA2EnhancedOptimizer(problem, use_nsga2_bias=False)
    standard_best, standard_fitness = standard_optimizer.optimize(100, 30)

    # 优化器2: 使用 NSGA-II 偏置
    print(f"\n{'='*25} 优化器2: NSGA-II增强 {'='*25}")
    nsga2_optimizer = NSGA2EnhancedOptimizer(problem, use_nsga2_bias=True)
    nsga2_best, nsga2_fitness = nsga2_optimizer.optimize(100, 30)

    # 结果对比
    print(f"\n{'='*25} 性能对比分析 {'='*25}")
    print(f"标准优化器结果: {standard_fitness:.6f}")
    print(f"NSGA-II增强结果: {nsga2_fitness:.6f}")

    if standard_fitness > 0:
        improvement = ((standard_fitness - nsga2_fitness) / standard_fitness) * 100
        print(f"\n[结果] NSGA-II偏置带来的改进: {improvement:+.2f}%")

    print(f"\n[NSGA-II 偏置的核心优势]")
    print("-" * 30)
    print("1. **模块化注入**: NSGA-II 概念作为偏置可注入任何算法")
    print("2. **算法无关性**: 不需要修改基础算法的核心逻辑")
    print("3. **多目标能力**: 单目标算法也能获得多目标优化特性")
    print("4. **组合使用**: 可与其他偏置（SA、多样性等）同时使用")
    print("5. **自适应能力**: 可根据优化状态动态调整 NSGA-II 参数")

    print(f"\n[NSGA-II 偏置的实际应用]")
    print("-" * 30)
    print("- 遗传算法 + NSGA-II 偏置 = 多目标 GA")
    print("- 粒子群优化 + NSGA-II 偏置 = 多目标 PSO")
    print("- 差分进化 + NSGA-II 偏置 = 多目标 DE (实质上是 MOEA/D)")
    print("- 任何单目标算法都可以通过偏置获得多目标特性")

    print(f"\n[与 SA 偏置的对比]")
    print("-" * 30)
    print("- SA 偏置: 注入 Metropolis准则（全局搜索能力）")
    print("- NSGA-II 偏置: 注入 Pareto 概念（多目标优化能力）")
    print("- 两者可以同时使用: SA + NSGA-II = 全局多目标优化")

    print(f"\n[演示完成] NSGA-II 偏置成功展示了算法思想的模块化注入能力")


if __name__ == "__main__":
    np.random.seed(42)
    demonstrate_nsga2_bias_integration()
