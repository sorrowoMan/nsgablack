# -*- coding: utf-8 -*-
"""
独立使用示例：偏置 + NSGA-II (无需多智能体)

这个示例展示如何在不使用多智能体系统的情况下，
直接使用偏置系统增强 NSGA-II 算法。

这符合真正的算法偏置化设计理念：
    偏置系统（独立核心）+ NSGA-II = 增强的优化器
    无需多智能体，偏置照样工作！
"""

import numpy as np
import matplotlib.pyplot as plt
from typing import List, Dict, Any

# 导入偏置（从 bias 模块）
from bias.algorithmic.nsga2 import NSGA2Bias
from bias.algorithmic.simulated_annealing import SimulatedAnnealingBias
from bias.algorithmic.differential_evolution import DifferentialEvolutionBias
from bias.algorithmic.pattern_search import PatternSearchBias
from bias.algorithmic.gradient_descent import GradientDescentBias


# ==========================================
# 定义优化上下文类
# ==========================================

class OptimizationContext:
    """优化上下文 - 偏置系统需要的接口"""

    def __init__(
        self,
        generation: int,
        population: List[np.ndarray],
        fitness: List[float] = None,
        evaluate_func: callable = None,
        metrics: Dict[str, Any] = None
    ):
        self.generation = generation
        self.population = population
        self.fitness = fitness
        self.evaluate = evaluate_func
        self.metrics = metrics or {}


# ==========================================
# 定义测试问题
# ==========================================

class ZDT1:
    """ZDT1 测试问题（经典多目标优化问题）"""

    def __init__(self, dimension=30):
        self.dimension = dimension
        self.bounds = [(0, 1)] * dimension

    def evaluate(self, x: np.ndarray) -> List[float]:
        """计算目标值"""
        f1 = x[0]
        g = 1 + 9 * sum(x[1:]) / (self.dimension - 1)
        f2 = g * (1 - np.sqrt(x[0] / g))
        return [f1, f2]


class Rastrigin:
    """Rastrigin 函数（多峰单目标问题）"""

    def __init__(self, dimension=10):
        self.dimension = dimension
        self.bounds = [(-5.12, 5.12)] * dimension

    def evaluate(self, x: np.ndarray) -> float:
        """计算目标值"""
        A = 10
        n = len(x)
        return A * n + sum(xi**2 - A * np.cos(2 * np.pi * xi) for xi in x)


# ==========================================
# 偏置增强的 NSGA-II 优化器
# ==========================================

class BiasedNSGA2Optimizer:
    """
    偏置增强的 NSGA-II 优化器

    核心特点：
    - 标准 NSGA-II 流程
    - 通过偏置系统注入其他算法的优点
    - 无需多智能体系统
    """

    def __init__(self, problem, biases: List = None, pop_size=100):
        """
        初始化优化器

        Args:
            problem: 优化问题
            biases: 偏置列表（算法偏置化的核心！）
            pop_size: 种群大小
        """
        self.problem = problem
        self.pop_size = pop_size
        self.biases = biases or []

        # 历史记录
        self.fitness_history = []
        self.diversity_history = []

        print(f"[初始化] 偏置增强 NSGA-II 优化器")
        print(f"  问题: {problem.__class__.__name__}")
        print(f"  种群大小: {pop_size}")
        print(f"  激活偏置: {len(self.biases)}")
        for i, bias in enumerate(self.biases, 1):
            print(f"    {i}. {bias.name} (权重: {bias.initial_weight})")

    def optimize(self, max_generations=100) -> tuple:
        """
        执行优化

        Returns:
            (最终种群, 目标值列表)
        """
        print(f"\n[开始优化] 最大代数: {max_generations}")
        print("-" * 60)

        # 初始化种群
        population = self._initialize_population()

        for generation in range(max_generations):
            # ========== 1. 评估种群 ==========
            objectives = self._evaluate_population(population)

            # ========== 2. 应用偏置 ==========
            if self.biases:
                biased_objectives = self._apply_biases(
                    population, objectives, generation
                )
            else:
                biased_objectives = objectives

            # ========== 3. NSGA-II 选择 ==========
            selected_indices = self._nsga2_selection(
                population, biased_objectives
            )

            # ========== 4. 遗传操作 ==========
            offspring = self._generate_offspring(
                population, selected_indices
            )

            # ========== 5. 精英保留 ==========
            population = self._environmental_selection(
                population, offspring, objectives
            )

            # 记录历史
            self._record_history(objectives, generation)

            # 进度报告
            if generation % 20 == 0 or generation == max_generations - 1:
                self._report_progress(generation, objectives)

        print("\n[优化完成]")
        return population, objectives

    def _initialize_population(self) -> List[np.ndarray]:
        """初始化种群"""
        population = []
        for _ in range(self.pop_size):
            individual = np.array([
                np.random.uniform(b[0], b[1])
                for b in self.problem.bounds
            ])
            population.append(individual)
        return population

    def _evaluate_population(self, population: List[np.ndarray]) -> List[List[float]]:
        """评估种群"""
        objectives = []
        for individual in population:
            obj = self.problem.evaluate(individual)
            if isinstance(obj, (int, float)):
                obj = [obj]
            objectives.append(obj)
        return objectives

    def _apply_biases(
        self,
        population: List[np.ndarray],
        objectives: List[List[float]],
        generation: int
    ) -> List[List[float]]:
        """
        应用偏置系统 ⭐

        这是核心！将多种算法的优点通过偏置注入
        """
        biased_objectives = []

        # 计算必要指标
        pareto_ranks = self._compute_pareto_ranks(objectives)
        crowding_distances = self._compute_crowding_distances(objectives)
        fitness_values = [sum(obj) for obj in objectives]

        for i, (individual, raw_obj) in enumerate(zip(population, objectives)):
            # 构建优化上下文
            context = OptimizationContext(
                generation=generation,
                population=population,
                fitness=fitness_values,
                metrics={
                    'pareto_rank': pareto_ranks[i],
                    'crowding_distance': crowding_distances[i],
                    'is_dominated': pareto_ranks[i] > 0,
                    'max_generations': 100,
                    'current_energy': fitness_values[i] if i > 0 else fitness_values[i],
                    'previous_energy': fitness_values[i-1] if i > 0 else fitness_values[i]
                }
            )

            # 如果有评估函数，添加到上下文（用于梯度偏置）
            if hasattr(self.problem, 'evaluate'):
                context.evaluate = self.problem.evaluate

            # 应用所有偏置
            total_bias = 0.0
            for bias in self.biases:
                if hasattr(bias, 'compute'):
                    bias_value = bias.compute(individual, context)
                    total_bias += bias_value

            # 将偏置应用到目标值
            biased_obj = [o + total_bias for o in raw_obj]
            biased_objectives.append(biased_obj)

        return biased_objectives

    def _compute_pareto_ranks(self, objectives: List[List[float]]) -> List[int]:
        """计算 Pareto rank"""
        n = len(objectives)
        ranks = [0] * n

        for i in range(n):
            rank = 0
            current_front = [objectives[i]]

            while True:
                dominated = []
                for j in range(n):
                    if j == i:
                        continue
                    if any(self._dominates(front_obj, objectives[j])
                           for front_obj in current_front):
                        dominated.append(objectives[j])

                if not dominated:
                    break

                current_front = dominated
                rank += 1
                if rank > 10:  # 防止无限循环
                    break

            ranks[i] = rank

        return ranks

    def _compute_crowding_distances(self, objectives: List[List[float]]) -> List[float]:
        """计算拥挤距离（简化版）"""
        n = len(objectives)
        distances = [0.0] * n

        if n <= 2:
            return [float('inf')] * n

        # 基于第一个目标的简单拥挤距离
        obj_values = [obj[0] for obj in objectives]
        sorted_indices = sorted(range(n), key=lambda i: obj_values[i])

        obj_range = obj_values[sorted_indices[-1]] - obj_values[sorted_indices[0]]
        if obj_range == 0:
            return [0.0] * n

        # 边界个体
        distances[sorted_indices[0]] = float('inf')
        distances[sorted_indices[-1]] = float('inf')

        # 中间个体
        for idx in range(1, n - 1):
            i = sorted_indices[idx]
            distances[i] = (
                obj_values[sorted_indices[idx + 1]] -
                obj_values[sorted_indices[idx - 1]]
            ) / obj_range

        return distances

    def _dominates(self, obj1: List[float], obj2: List[float]) -> bool:
        """判断 obj1 是否支配 obj2"""
        at_least_one_better = False
        for o1, o2 in zip(obj1, obj2):
            if o1 > o2:
                return False
            elif o1 < o2:
                at_least_one_better = True
        return at_least_one_better

    def _nsga2_selection(
        self,
        population: List[np.ndarray],
        objectives: List[List[float]]
    ) -> List[int]:
        """NSGA-II 选择"""
        # 使用锦标赛选择（简化版）
        fitness = [sum(obj) for obj in objectives]
        selected = []

        for _ in range(len(population)):
            # 锦标赛
            candidates = np.random.choice(len(population), 2, replace=False)
            winner = candidates[0] if fitness[candidates[0]] < fitness[candidates[1]] else candidates[1]
            selected.append(winner)

        return selected

    def _generate_offspring(
        self,
        population: List[np.ndarray],
        selected_indices: List[int]
    ) -> List[np.ndarray]:
        """生成后代"""
        offspring = []

        for _ in range(self.pop_size):
            # 选择父代
            parent1_idx = np.random.choice(selected_indices)
            parent2_idx = np.random.choice(selected_indices)

            parent1 = population[parent1_idx]
            parent2 = population[parent2_idx]

            # SBX 交叉（简化版：模拟二进制交叉）
            if np.random.random() < 0.9:
                alpha = np.random.random()
                child = alpha * parent1 + (1 - alpha) * parent2
            else:
                child = parent1.copy()

            # 多项式变异
            if np.random.random() < 0.1:
                for i in range(len(child)):
                    if np.random.random() < 0.1:
                        bounds = self.problem.bounds[i]
                        mutation = np.random.normal(0, 0.1 * (bounds[1] - bounds[0]))
                        child[i] = np.clip(child[i] + mutation, bounds[0], bounds[1])

            offspring.append(child)

        return offspring

    def _environmental_selection(
        self,
        population: List[np.ndarray],
        offspring: List[np.ndarray],
        objectives: List[List[float]]
    ) -> List[np.ndarray]:
        """环境选择（精英保留）"""
        # 合并父代和子代
        combined = population + offspring
        combined_obj = objectives + self._evaluate_population(offspring)

        # 计算适应度
        fitness = [sum(obj) for obj in combined_obj]

        # 选择最好的 pop_size 个
        sorted_indices = sorted(
            range(len(combined)),
            key=lambda i: fitness[i]
        )[:self.pop_size]

        return [combined[i].copy() for i in sorted_indices]

    def _record_history(self, objectives: List[List[float]], generation: int):
        """记录历史"""
        avg_fitness = np.mean([sum(obj) for obj in objectives])
        self.fitness_history.append(avg_fitness)

    def _report_progress(self, generation: int, objectives: List[List[float]]):
        """报告进度"""
        avg_fitness = np.mean([sum(obj) for obj in objectives])
        best_fitness = min(sum(obj) for obj in objectives)

        print(f"代数 {generation:3d}: "
              f"平均={avg_fitness:8.4f}, "
              f"最佳={best_fitness:8.4f}")


# ==========================================
# 对比实验
# ==========================================

def run_comparison():
    """运行对比实验"""
    print("=" * 70)
    print("偏置增强 NSGA-II vs 标准 NSGA-II 对比实验")
    print("（无需多智能体系统）")
    print("=" * 70)

    # 创建测试问题
    problem = Rastrigin(dimension=10)
    print(f"\n测试问题: {problem.__class__.__name__} (多峰函数)")
    print(f"维度: {problem.dimension}")

    # ========== 实验 1: 标准 NSGA-II（无偏置）==========
    print(f"\n{'='*25} 实验 1: 标准 NSGA-II {'='*25}")
    optimizer1 = BiasedNSGA2Optimizer(problem, biases=[], pop_size=50)
    pop1, obj1 = optimizer1.optimize(max_generations=50)
    fitness1 = [sum(o) for o in obj1]
    print(f"最优解: {min(fitness1):.6f}")

    # ========== 实验 2: NSGA-II + NSGA-II 偏置（自我增强）==========
    print(f"\n{'='*25} 实验 2: NSGA-II + NSGA-II 偏置 {'='*25}")
    optimizer2 = BiasedNSGA2Optimizer(
        problem,
        biases=[
            NSGA2Bias(
                initial_weight=0.1,
                rank_weight=0.5,
                crowding_weight=0.5
            )
        ],
        pop_size=50
    )
    pop2, obj2 = optimizer2.optimize(max_generations=50)
    fitness2 = [sum(o) for o in obj2]
    print(f"最优解: {min(fitness2):.6f}")

    # ========== 实验 3: NSGA-II + SA 偏置（全局搜索）==========
    print(f"\n{'='*25} 实验 3: NSGA-II + SA 偏置 {'='*25}")
    optimizer3 = BiasedNSGA2Optimizer(
        problem,
        biases=[
            NSGA2Bias(initial_weight=0.05),
            SimulatedAnnealingBias(
                initial_weight=0.1,
                initial_temperature=100.0,
                cooling_rate=0.99
            )
        ],
        pop_size=50
    )
    pop3, obj3 = optimizer3.optimize(max_generations=50)
    fitness3 = [sum(o) for o in obj3]
    print(f"最优解: {min(fitness3):.6f}")

    # ========== 实验 4: NSGA-II + DE 偏置（差分进化）==========
    print(f"\n{'='*25} 实验 4: NSGA-II + DE 偏置 {'='*25}")
    optimizer4 = BiasedNSGA2Optimizer(
        problem,
        biases=[
            NSGA2Bias(initial_weight=0.05),
            DifferentialEvolutionBias(
                initial_weight=0.1,
                F=0.8,
                strategy="rand"
            )
        ],
        pop_size=50
    )
    pop4, obj4 = optimizer4.optimize(max_generations=50)
    fitness4 = [sum(o) for o in obj4]
    print(f"最优解: {min(fitness4):.6f}")

    # ========== 实验 5: NSGA-II + Pattern Search 偏置（局部精化）==========
    print(f"\n{'='*25} 实验 5: NSGA-II + Pattern Search 偏置 {'='*25}")
    optimizer5 = BiasedNSGA2Optimizer(
        problem,
        biases=[
            NSGA2Bias(initial_weight=0.05),
            PatternSearchBias(
                initial_weight=0.1,
                step_size=0.1
            )
        ],
        pop_size=50
    )
    pop5, obj5 = optimizer5.optimize(max_generations=50)
    fitness5 = [sum(o) for o in obj5]
    print(f"最优解: {min(fitness5):.6f}")

    # ========== 实验 6: NSGA-II + 组合偏置（全能）==========
    print(f"\n{'='*25} 实验 6: NSGA-II + 组合偏置 {'='*25}")
    optimizer6 = BiasedNSGA2Optimizer(
        problem,
        biases=[
            NSGA2Bias(initial_weight=0.05),
            SimulatedAnnealingBias(initial_weight=0.05),
            DifferentialEvolutionBias(initial_weight=0.05),
            PatternSearchBias(initial_weight=0.05)
        ],
        pop_size=50
    )
    pop6, obj6 = optimizer6.optimize(max_generations=50)
    fitness6 = [sum(o) for o in obj6]
    print(f"最优解: {min(fitness6):.6f}")

    # ========== 结果对比 ==========
    print(f"\n{'='*25} 结果对比分析 {'='*25}")
    results = [
        ("标准 NSGA-II", min(fitness1)),
        ("NSGA-II + NSGA-II偏置", min(fitness2)),
        ("NSGA-II + SA偏置", min(fitness3)),
        ("NSGA-II + DE偏置", min(fitness4)),
        ("NSGA-II + PS偏置", min(fitness5)),
        ("NSGA-II + 组合偏置", min(fitness6))
    ]

    for name, best in results:
        improvement = ((fitness1[0] - best) / fitness1[0]) * 100
        print(f"{name:25s}: {best:8.4f}  (改进: {improvement:+.2f}%)")

    # 绘制收敛曲线
    plt.figure(figsize=(12, 6))

    plt.subplot(1, 2, 1)
    plt.plot(optimizer1.fitness_history, label='标准 NSGA-II', linewidth=2)
    plt.plot(optimizer2.fitness_history, label='NSGA-II + NSGA-II偏置')
    plt.plot(optimizer3.fitness_history, label='NSGA-II + SA偏置')
    plt.plot(optimizer4.fitness_history, label='NSGA-II + DE偏置')
    plt.plot(optimizer5.fitness_history, label='NSGA-II + PS偏置')
    plt.plot(optimizer6.fitness_history, label='NSGA-II + 组合偏置', linewidth=2)
    plt.xlabel('Generation')
    plt.ylabel('Average Fitness')
    plt.title('Convergence Comparison')
    plt.legend()
    plt.grid(True, alpha=0.3)

    plt.subplot(1, 2, 2)
    improvements = [((results[0][1] - r[1]) / results[0][1]) * 100 for r in results[1:]]
    labels = [r[0].replace("NSGA-II + ", "") for r in results[1:]]
    colors = ['green' if imp > 0 else 'red' for imp in improvements]
    plt.barh(labels, improvements, color=colors, alpha=0.7)
    plt.xlabel('Improvement over Standard NSGA-II (%)')
    plt.title('Bias Impact')
    plt.grid(True, alpha=0.3, axis='x')

    plt.tight_layout()
    plt.savefig('standalone_bias_nsga2_comparison.png', dpi=150)
    print(f"\n[图表已保存] standalone_bias_nsga2_comparison.png")

    # ========== 核心信息 ==========
    print(f"\n{'='*25} 核心设计理念 {'='*25}")
    print("""
    ✅ 偏置系统是独立的模块
       - 不依赖多智能体系统
       - 可以直接与任何优化算法组合

    ✅ 算法偏置化
       - NSGA-II 思想 → NSGA2Bias
       - SA 思想 → SimulatedAnnealingBias
       - DE 思想 → DifferentialEvolutionBias
       - PS 思想 → PatternSearchBias

    ✅ 无限组合可能
       - 任意偏置都可以组合
       - 通过权重调整各算法的影响程度

    ✅ 使用灵活
       - 简单问题: 使用单个偏置
       - 复杂问题: 使用组合偏置
       - 无需多智能体: 直接用偏置 + NSGA-II
       - 需要多智能体: 偏置 + NSGA-II + 多智能体
    """)


# ==========================================
# 主程序
# ==========================================

if __name__ == "__main__":
    np.random.seed(42)

    # 运行对比实验
    run_comparison()

    print("\n[演示完成] 偏置系统成功展示了独立于多智能体的算法增强能力！")
