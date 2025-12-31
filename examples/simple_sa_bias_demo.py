"""
简化的SA偏置集成演示
展示模拟退火思想如何通过偏置注入到任何算法中
"""

import numpy as np
import matplotlib.pyplot as plt
from typing import List, Dict, Any

# 导入基础类
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bias_system_demo import EngineeringDesignProblem, DomainBias, AlgorithmicBias, AdaptiveBiasManager


class SimulatedAnnealingBias:
    """模拟退火偏置 - 将SA思想转换为可注入的偏置"""

    def __init__(self, initial_weight=0.15, initial_temperature=100.0, cooling_rate=0.995):
        self.weight = initial_weight
        self.initial_temperature = initial_temperature
        self.cooling_rate = cooling_rate
        self.current_temperature = initial_temperature

    def compute_bias(self, x: List, context: Dict[str, Any]) -> float:
        """
        计算SA偏置值 - 核心是将Metropolis准则转换为偏置
        """
        generation = context.get('generation', 0)
        current_energy = context.get('current_energy', 0)
        previous_energy = context.get('previous_energy', 0)

        # 更新温度
        self.current_temperature = self.initial_temperature * (self.cooling_rate ** generation)

        # 如果没有历史能量，返回0
        if previous_energy is None:
            return 0.0

        # 计算能量差
        delta_energy = current_energy - previous_energy

        # 应用Metropolis准则
        if delta_energy <= 0:
            # 好的解 - 给予奖励（负偏置表示接受）
            return -self.weight * abs(delta_energy) * 0.1
        else:
            # 差的解 - 根据温度给予概率性接受
            if self.current_temperature > 0:
                acceptance_prob = np.exp(-delta_energy / self.current_temperature)
                return self.weight * acceptance_prob * delta_energy * 0.1
            return 0.0


class SAEnhancedOptimizer:
    """SA增强的优化器 - 可用于任何基础算法"""

    def __init__(self, problem, use_sa=True):
        self.problem = problem
        self.use_sa = use_sa

        # 偏置系统
        self.domain_bias = DomainBias()
        self.adaptive_manager = AdaptiveBiasManager()

        # 添加传统偏置
        diversity_bias = AlgorithmicBias("DiversityBias", 0.1)
        self.adaptive_manager.add_bias(diversity_bias)

        # 添加SA偏置
        if self.use_sa:
            self.sa_bias = SimulatedAnnealingBias(initial_weight=0.15)
            sa_algo_bias = AlgorithmicBias("SimulatedAnnealing", self.sa_bias.weight)
            self.adaptive_manager.add_bias(sa_algo_bias)
            print("[OK] 启用模拟退火偏置")
        else:
            print("[OFF] 禁用模拟退火偏置")

        # 历史记录
        self.fitness_history = []
        self.temperature_history = []

    def optimize(self, max_generations=100, population_size=30):
        """通用优化过程"""
        algorithm_name = "SA增强优化器" if self.use_sa else "标准优化器"
        print(f"\n[开始优化] {algorithm_name} ({max_generations}代)")
        print("-" * 50)

        # 初始化种群
        population = self._initialize_population(population_size)
        best_solution = None
        best_fitness = float('inf')

        for generation in range(max_generations):
            fitness_values = []

            # 评估种群
            for i, individual in enumerate(population):
                # 计算目标函数
                obj_value = self.problem.evaluate(individual)
                previous_obj = fitness_values[i-1] if i > 0 else obj_value

                # 计算约束
                constraints = self.problem.evaluate_constraints(individual)
                total_violation = sum(max(0, c) for c in constraints)

                # 构建上下文
                context = {
                    'generation': generation,
                    'individual': individual,
                    'population': population,
                    'individual_index': i,
                    'current_energy': obj_value,
                    'previous_energy': previous_obj
                }

                # 应用偏置
                # 1. 业务偏置（固定）
                domain_bias_value = self.domain_bias.compute_bias(individual, total_violation)

                # 2. 算法偏置（自适应）
                algorithmic_bias_value = self.adaptive_manager.compute_total_bias(individual, context)

                # 3. SA偏置（如果启用）
                sa_bias_value = 0.0
                if self.use_sa:
                    sa_bias_value = self.sa_bias.compute_bias(individual, context)

                # 总适应度
                total_fitness = obj_value + domain_bias_value + algorithmic_bias_value + sa_bias_value
                fitness_values.append(total_fitness)

                # 更新最佳解（基于原始目标值）
                if obj_value < best_fitness:
                    best_fitness = obj_value
                    best_solution = individual.copy()

            # 记录历史
            self.fitness_history.append(best_fitness)
            if self.use_sa:
                self.temperature_history.append(self.sa_bias.current_temperature)

            # 更新自适应管理器
            adaptation_context = {
                'generation': generation,
                'individual': population[0],
                'population': population
            }
            self.adaptive_manager.update_state(adaptation_context, population, fitness_values)

            # 进化操作（简化版）
            population = self._evolve_population(population, fitness_values)

            # 进度报告
            if generation % 20 == 0 or generation == max_generations - 1:
                temp_str = f", T={self.sa_bias.current_temperature:.2f}" if self.use_sa else ""
                print(f"代数 {generation:3d}: 最佳={best_fitness:8.4f}{temp_str}")

        # 检查约束满足
        final_violation = sum(max(0, c) for c in self.problem.evaluate_constraints(best_solution))

        print(f"\n[优化完成]")
        print(f"最优解: {best_fitness:.6f}")
        print(f"约束违反: {final_violation:.6f}")
        print(f"解可行性: {'[OK]' if final_violation < 1e-6 else '[WARN]'}")

        return best_solution, best_fitness

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

    def visualize_results(self, title=""):
        """可视化结果"""
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))

        # 适应度演化
        axes[0, 0].plot(self.fitness_history, 'b-', linewidth=2, label=title)
        axes[0, 0].set_xlabel('Generation')
        axes[0, 0].set_ylabel('Best Fitness')
        axes[0, 0].set_title(f'{title} Optimization Progress')
        axes[0, 0].grid(True, alpha=0.3)
        axes[0, 0].legend()

        # 收敛速度分析
        if len(self.fitness_history) > 10:
            convergence_rate = []
            for i in range(10, len(self.fitness_history)):
                recent_improvement = (self.fitness_history[i-10] - self.fitness_history[i]) / self.fitness_history[i-10]
                convergence_rate.append(recent_improvement)

            axes[0, 1].plot(range(10, len(self.fitness_history)), convergence_rate, 'r-', linewidth=2)
            axes[0, 1].set_xlabel('Generation')
            axes[0, 1].set_ylabel('Improvement Rate')
            axes[0, 1].set_title('Convergence Speed Analysis')
            axes[0, 1].grid(True, alpha=0.3)

        # 温度演化（仅SA）
        if self.use_sa and self.temperature_history:
            axes[1, 0].plot(self.temperature_history, 'g-', linewidth=2)
            axes[1, 0].set_xlabel('Generation')
            axes[1, 0].set_ylabel('Temperature')
            axes[1, 0].set_title('Simulated Annealing Temperature Schedule')
            axes[1, 0].grid(True, alpha=0.3)
        else:
            axes[1, 0].text(0.5, 0.5, 'No SA Temperature Data',
                           ha='center', va='center', transform=axes[1, 0].transAxes)
            axes[1, 0].set_title('Simulated Annealing Temperature Schedule')

        # 最终解分布
        axes[1, 1].hist(self.fitness_history[-20:], bins=10, alpha=0.7, color='purple')
        axes[1, 1].set_xlabel('Fitness Value')
        axes[1, 1].set_ylabel('Frequency')
        axes[1, 1].set_title('Final Solution Distribution')
        axes[1, 1].grid(True, alpha=0.3)

        plt.tight_layout()
        filename = f'sa_bias_results_{title.lower().replace(" ", "_")}.png'
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.show()
        print(f"[图表已保存为 {filename}]")


def demonstrate_sa_bias_integration():
    """演示SA偏置集成效果"""
    print("=" * 70)
    print("模拟退火偏置集成演示")
    print("展示SA思想如何通过偏置注入到任何算法中")
    print("=" * 70)

    # 创建问题
    problem = EngineeringDesignProblem()
    print(f"测试问题: {problem.name}")
    print(f"维度: {problem.dimension}, 约束数: {problem.constraint_count}")
    print(f"多峰性: {problem.multimodality}, 可分离性: {problem.separability}")

    # 优化器1: 不使用SA偏置
    print(f"\n{'='*25} 优化器1: 标准优化器 {'='*25}")
    standard_optimizer = SAEnhancedOptimizer(problem, use_sa=False)
    standard_best, standard_fitness = standard_optimizer.optimize(100, 30)

    # 优化器2: 使用SA偏置
    print(f"\n{'='*25} 优化器2: SA增强优化器 {'='*25}")
    sa_optimizer = SAEnhancedOptimizer(problem, use_sa=True)
    sa_best, sa_fitness = sa_optimizer.optimize(100, 30)

    # 结果对比
    print(f"\n{'='*25} 性能对比分析 {'='*25}")
    print(f"标准优化器结果: {standard_fitness:.6f}")
    print(f"SA增强优化器结果: {sa_fitness:.6f}")

    if standard_fitness > 0:
        improvement = ((standard_fitness - sa_fitness) / standard_fitness) * 100
        print(f"\n[结果] SA偏置带来的改进: {improvement:+.2f}%")

        if improvement > 0:
            print("[OK] SA偏置显著改善了优化性能")
        elif improvement > -5:
            print("[INFO] SA偏置对性能影响较小")
        else:
            print("[WARN] SA偏置降低了性能（可能需要调整参数）")
    else:
        print("📊 无法计算改进率（目标值接近零）")

    # 可视化对比
    print(f"\n[生成可视化对比]")
    standard_optimizer.visualize_results("Standard Optimizer")
    sa_optimizer.visualize_results("SA Enhanced Optimizer")

    # SA偏置的核心优势总结
    print(f"\n[SA偏置的核心优势]")
    print("-" * 30)
    print("1. **模块化注入**: SA思想作为偏置可注入任何算法")
    print("2. **算法无关性**: 不需要修改基础算法的核心逻辑")
    print("3. **参数可调**: 温度调度、权重等都可灵活配置")
    print("4. **组合使用**: 可与其他偏置（多样性、收敛等）同时使用")
    print("5. **自适应能力**: 可根据优化状态动态调整SA参数")

    print(f"\n[SA偏置的实际应用]")
    print("-" * 30)
    print("- 遗传算法 + SA偏置 = SA-GA")
    print("- 粒子群优化 + SA偏置 = SA-PSO")
    print("- 差分进化 + SA偏置 = SA-DE")
    print("- 蚁群算法 + SA偏置 = SA-ACO")
    print("- 任何基于种群的算法都可以通过偏置获得SA特性")

    print(f"\n[演示完成] SA偏置成功展示了算法思想的模块化注入能力")


if __name__ == "__main__":
    # 设置随机种子
    np.random.seed(42)

    demonstrate_sa_bias_integration()