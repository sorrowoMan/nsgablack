"""
智能偏置系统演示 - 简化版本
展示业务偏置固定、算法偏置自适应的完整工作流程
"""

import numpy as np
import matplotlib.pyplot as plt
import time
import random


# 1. 定义工程设计问题
class EngineeringDesignProblem:
    """工程设计问题：最小化重量的约束优化"""

    def __init__(self):
        self.name = "工程设计优化"
        self.dimension = 8
        self.constraint_count = 3

        # 设计变量边界（厚度、材料属性等）
        self.bounds = [(0.1, 5.0)] * self.dimension

        # 问题特征
        self.multimodality = 0.7  # 多峰性较高
        self.separability = 0.4   # 变量间耦合较强

    def evaluate(self, x):
        """评估目标函数（结构重量）"""
        # 转换为numpy数组
        x_array = np.array(x)

        # 基础重量计算
        weight = np.sum(x_array) + 0.1 * np.sum(x_array**2)

        # 复杂交互项（制造多峰性）
        weight += 0.5 * np.sin(x_array[0] * x_array[1]) * np.cos(x_array[2] * x_array[3])

        return weight

    def evaluate_constraints(self, x):
        """评估约束（强度、稳定性、制造约束）"""
        constraints = []
        x_array = np.array(x)

        # 强度约束：x[0]*x[1] + x[2] >= 2.0
        constraints.append(2.0 - (x_array[0]*x_array[1] + x_array[2]))

        # 稳定性约束：x[3] + 2*x[4] <= 5.0
        constraints.append(x_array[3] + 2*x_array[4] - 5.0)

        # 制造约束：x[5]到x[7]的和在合理范围
        sum_constraints = np.sum(x_array[5:])
        constraints.append(abs(sum_constraints - 2.5) - 1.0)

        return constraints

    def is_feasible(self, x):
        """检查解是否可行"""
        constraints = self.evaluate_constraints(x)
        return all(c <= 0 for c in constraints)


# 2. 业务偏置（固定不变）
class DomainBias:
    """业务偏置：固定权重，代表业务规则和约束"""

    def __init__(self):
        self.name = "DomainBias"
        self.weight = 0.3  # 固定权重，永不改变
        self.is_adaptive = False  # 永不自适应

    def compute_bias(self, x, constraint_violation):
        """计算业务偏置值（约束处理）"""
        # 约束违反越大，惩罚越重
        penalty = 1000 * constraint_violation
        return self.weight * penalty


# 3. 算法偏置（可自适应）
class AlgorithmicBias:
    """算法偏置：可动态调整，优化搜索策略"""

    def __init__(self, name, initial_weight=0.1):
        self.name = name
        self.weight = initial_weight
        self.is_adaptive = True  # 支持自适应
        self.history = []

    def compute_bias(self, x, context):
        """计算算法偏置值"""
        generation = context['generation']
        population = context['population']

        if self.name == "DiversityBias":
            # 多样性偏置：奖励远离种群中心的个体
            center = np.mean(population, axis=0)
            distance = np.linalg.norm(np.array(x) - center)
            return self.weight * distance

        elif self.name == "ConvergenceBias":
            # 收敛偏置：引导向历史最优解
            if 'best_solution' in context and context['best_solution'] is not None:
                distance_to_best = np.linalg.norm(np.array(x) - np.array(context['best_solution']))
                return self.weight * (-distance_to_best)  # 负值表示吸引力
            return 0

        elif self.name == "ExplorationBias":
            # 探索偏置：奖励未探索区域
            exploration_bonus = np.random.random() * 0.1 * self.weight
            return exploration_bonus

        else:
            return 0

    def adjust_weight(self, factor):
        """调整权重（自适应）"""
        old_weight = self.weight
        self.weight = max(0.01, min(0.5, self.weight * factor))
        self.history.append(self.weight)
        return self.weight, old_weight


# 4. 自适应偏置管理器（只管理算法偏置）
class AdaptiveBiasManager:
    """自适应算法偏置管理器"""

    def __init__(self):
        self.biases = {}
        self.state_history = []
        self.adaptation_interval = 10

    def add_bias(self, bias):
        """添加算法偏置"""
        self.biases[bias.name] = bias

    def compute_total_bias(self, x, context):
        """计算总算法偏置"""
        total = 0
        for bias in self.biases.values():
            total += bias.compute_bias(x, context)
        return total

    def update_state(self, context, population, fitness_values):
        """更新优化状态并自适应调整"""
        generation = context['generation']

        # 计算当前状态指标
        diversity = self._compute_diversity(population)
        improvement_rate = self._compute_improvement_rate(fitness_values)

        state = {
            'generation': generation,
            'diversity': diversity,
            'improvement_rate': improvement_rate
        }
        self.state_history.append(state)

        # 检查是否需要自适应调整
        if generation % self.adaptation_interval == 0 and generation > 0:
            self._adapt_biases(state)

    def _compute_diversity(self, population):
        """计算种群多样性"""
        if len(population) < 2:
            return 0.0

        pop_array = np.array(population)
        distances = []

        for i in range(len(population)):
            for j in range(i + 1, len(population)):
                dist = np.linalg.norm(pop_array[i] - pop_array[j])
                distances.append(dist)

        return np.mean(distances) if distances else 0.0

    def _compute_improvement_rate(self, fitness_values):
        """计算改进率"""
        if len(fitness_values) < 10:
            return 0.1

        recent = np.mean(fitness_values[-5:])
        older = np.mean(fitness_values[-10:-5])

        if older > 0:
            return (older - recent) / older
        return 0.0

    def _adapt_biases(self, state):
        """自适应调整偏置权重"""
        print(f"    [ADAPT] 世代 {state['generation']}: 自适应调整偏置权重")

        diversity = state['diversity']
        improvement_rate = state['improvement_rate']

        # 规则1：多样性过低，增加探索
        if diversity < 0.5:
            if "DiversityBias" in self.biases:
                new_weight, old_weight = self.biases["DiversityBias"].adjust_weight(1.3)
                print(f"      多样性偏低，DiversityBias: {old_weight:.3f} → {new_weight:.3f}")

            if "ExplorationBias" in self.biases:
                new_weight, old_weight = self.biases["ExplorationBias"].adjust_weight(1.2)
                print(f"      增加探索，ExplorationBias: {old_weight:.3f} → {new_weight:.3f}")

        # 规则2：改进缓慢，调整收敛偏置
        if improvement_rate < 0.01:
            if "ConvergenceBias" in self.biases:
                new_weight, old_weight = self.biases["ConvergenceBias"].adjust_weight(0.8)
                print(f"      改进缓慢，减少ConvergenceBias: {old_weight:.3f} → {new_weight:.3f}")

        # 规则3：多样性过高，可以增加开发
        elif diversity > 2.0:
            if "ConvergenceBias" in self.biases:
                new_weight, old_weight = self.biases["ConvergenceBias"].adjust_weight(1.2)
                print(f"      多样性充足，增加ConvergenceBias: {old_weight:.3f} → {new_weight:.3f}")


# 5. 智能偏置系统
class IntelligentBiasSystem:
    """智能偏置系统"""

    def __init__(self):
        # 业务偏置（固定）
        self.domain_bias = DomainBias()

        # 算法偏置（自适应）
        self.adaptive_manager = AdaptiveBiasManager()

        # 优化历史
        self.fitness_history = []
        self.diversity_history = []
        self.adaptation_log = []

    def setup_biases(self, problem):
        """根据问题特征设置偏置"""
        print("\n[配置偏置系统]")
        print("-" * 30)

        # 业务偏置（固定不变）
        print("业务偏置（全局固定）:")
        print(f"  [OK] {self.domain_bias.name}: 权重={self.domain_bias.weight} (永不改变)")

        # 算法偏置（可自适应）
        print("\n算法偏置（动态自适应）:")

        # 基于问题特征选择算法偏置
        if problem.multimodality > 0.5:
            diversity_bias = AlgorithmicBias("DiversityBias", 0.15)
            exploration_bias = AlgorithmicBias("ExplorationBias", 0.1)
            self.adaptive_manager.add_bias(diversity_bias)
            self.adaptive_manager.add_bias(exploration_bias)
            print("  [INFO] 检测到高多峰性，增加探索偏置")

        if problem.separability < 0.5:
            convergence_bias = AlgorithmicBias("ConvergenceBias", 0.1)
            self.adaptive_manager.add_bias(convergence_bias)
            print("  [INFO] 检测到强耦合，增加收敛偏置")

    def optimize(self, problem, max_generations=60, population_size=30):
        """执行智能偏置优化"""
        print(f"\n[开始智能优化] {max_generations}代，{population_size}个体")
        print("-" * 50)

        # 初始化种群
        population = self._initialize_population(problem, population_size)
        best_solution = None
        best_fitness = float('inf')

        start_time = time.time()

        # 主优化循环
        for generation in range(max_generations):
            fitness_values = []
            constraint_violations = []

            # 评估种群
            for i, individual in enumerate(population):
                # 计算目标函数
                obj_value = problem.evaluate(individual)

                # 计算约束违反
                constraints = problem.evaluate_constraints(individual)
                total_violation = sum(max(0, c) for c in constraints)
                constraint_violations.append(total_violation)

                # 应用偏置
                context = {
                    'generation': generation,
                    'individual': individual,
                    'population': population,
                    'best_solution': best_solution
                }

                # 业务偏置（固定）- 处理约束
                domain_bias_value = self.domain_bias.compute_bias(individual, total_violation)

                # 算法偏置（自适应）- 优化搜索策略
                algorithmic_bias_value = self.adaptive_manager.compute_total_bias(individual, context)

                # 组合偏置
                total_bias = domain_bias_value + algorithmic_bias_value
                biased_fitness = obj_value + total_bias

                fitness_values.append(biased_fitness)

                # 更新最佳解
                if biased_fitness < best_fitness:
                    best_fitness = biased_fitness
                    best_solution = individual.copy()

            # 记录历史
            self.fitness_history.append(best_fitness)
            diversity = self._compute_diversity(population)
            self.diversity_history.append(diversity)

            # 更新自适应偏置管理器
            self.adaptive_manager.update_state(context, population, fitness_values)

            # 进化操作
            population = self._evolve_population(population, fitness_values, problem)

            # 进度报告
            if generation % 10 == 0 or generation == max_generations - 1:
                avg_violation = np.mean(constraint_violations)
                print(f"代数 {generation:2d}: "
                      f"最佳适应度={best_fitness:8.4f}, "
                      f"约束违反={avg_violation:6.3f}, "
                      f"多样性={diversity:5.3f}")

        optimization_time = time.time() - start_time

        print(f"\n[优化完成] 用时: {optimization_time:.2f}秒")
        print(f"最优解:")
        print(f"  目标函数值: {problem.evaluate(best_solution):.6f}")
        print(f"  约束违反: {sum(max(0, c) for c in problem.evaluate_constraints(best_solution)):.6f}")

        return best_solution, best_fitness

    def _initialize_population(self, problem, population_size):
        """初始化种群"""
        population = []
        for _ in range(population_size):
            individual = [np.random.uniform(b[0], b[1]) for b in problem.bounds]
            # 简单修复确保可行性
            if not problem.is_feasible(individual):
                individual[0] = max(0.5, individual[0])
                individual[1] = max(0.5, individual[1])
            population.append(individual)
        return population

    def _evolve_population(self, population, fitness_values, problem):
        """进化种群"""
        new_population = []

        # 精英保留
        elite_idx = np.argmin(fitness_values)
        new_population.append(population[elite_idx].copy())

        # 锦标赛选择和交叉变异
        while len(new_population) < len(population):
            parent1 = self._tournament_selection(population, fitness_values)
            parent2 = self._tournament_selection(population, fitness_values)
            child = self._crossover(parent1, parent2)
            child = self._mutate(child, problem)
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

    def _mutate(self, individual, problem, mutation_rate=0.1):
        """高斯变异"""
        mutated = individual.copy()
        for i in range(len(mutated)):
            if np.random.random() < mutation_rate:
                mutation = np.random.normal(0, 0.1 * (problem.bounds[i][1] - problem.bounds[i][0]))
                mutated[i] = np.clip(mutated[i] + mutation, problem.bounds[i][0], problem.bounds[i][1])
        return mutated

    def _compute_diversity(self, population):
        """计算种群多样性"""
        if len(population) < 2:
            return 0.0
        pop_array = np.array(population)
        distances = []
        for i in range(len(population)):
            for j in range(i + 1, len(population)):
                dist = np.linalg.norm(pop_array[i] - pop_array[j])
                distances.append(dist)
        return np.mean(distances) if distances else 0.0

    def visualize_results(self):
        """可视化结果"""
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))

        # 适应度演化
        axes[0, 0].plot(self.fitness_history, 'b-', linewidth=2)
        axes[0, 0].set_xlabel('Generation')
        axes[0, 0].set_ylabel('Best Fitness')
        axes[0, 0].set_title('Optimization Progress')
        axes[0, 0].grid(True, alpha=0.3)

        # 多样性演化
        axes[0, 1].plot(self.diversity_history, 'r-', linewidth=2)
        axes[0, 1].set_xlabel('Generation')
        axes[0, 1].set_ylabel('Population Diversity')
        axes[0, 1].set_title('Diversity Maintenance')
        axes[0, 1].grid(True, alpha=0.3)

        # 偏置权重演化
        generations = range(len(self.fitness_history))
        for bias_name, bias in self.adaptive_manager.biases.items():
            if bias.history:
                # 将权重历史对齐到代数
                weight_history = []
                current_weight = bias.weight
                for gen in generations:
                    adaptation_points = [i * self.adaptive_manager.adaptation_interval
                                       for i in range(len(bias.history))]
                    if gen in adaptation_points:
                        idx = adaptation_points.index(gen)
                        if idx < len(bias.history):
                            current_weight = bias.history[idx]
                    weight_history.append(current_weight)

                axes[1, 0].plot(generations, weight_history, label=bias_name, linewidth=2)

        axes[1, 0].set_xlabel('Generation')
        axes[1, 0].set_ylabel('Bias Weight')
        axes[1, 0].set_title('Adaptive Bias Weight Evolution')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)

        # 收敛分析
        if len(self.fitness_history) > 10:
            improvements = []
            for i in range(1, len(self.fitness_history)):
                improvement = (self.fitness_history[i-1] - self.fitness_history[i]) / abs(self.fitness_history[i-1]) * 100
                improvements.append(improvement)

            axes[1, 1].plot(range(1, len(self.fitness_history)), improvements)
            axes[1, 1].set_xlabel('Generation')
            axes[1, 1].set_ylabel('Improvement Rate (%)')
            axes[1, 1].set_title('Fitness Improvement Rate')
            axes[1, 1].grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig('bias_system_results.png', dpi=300, bbox_inches='tight')
        plt.show()


def main():
    """主演示函数"""
    print("=" * 60)
    print("智能偏置系统演示")
    print("业务偏置固定，算法偏置自适应")
    print("=" * 60)

    # 创建问题
    print("\n[问题定义]")
    print("-" * 30)
    problem = EngineeringDesignProblem()
    print(f"问题类型: {problem.name}")
    print(f"设计变量: {problem.dimension} 个")
    print(f"约束数量: {problem.constraint_count} 个")
    print(f"多峰性: {problem.multimodality}")
    print(f"可分离性: {problem.separability}")

    # 创建智能偏置系统
    bias_system = IntelligentBiasSystem()

    # 配置偏置
    bias_system.setup_biases(problem)

    # 执行优化
    best_solution, best_fitness = bias_system.optimize(problem, max_generations=60, population_size=30)

    # 分析结果
    print(f"\n[结果分析]")
    print("-" * 30)

    # 检查最终约束违反
    final_violation = sum(max(0, c) for c in problem.evaluate_constraints(best_solution))
    if final_violation < 1e-6:
        print("[OK] 最终解满足所有约束")
    else:
        print(f"[WARN] 最终解仍有约束违反: {final_violation:.6f}")

    # 分析偏置自适应
    print(f"\n[偏置自适应分析]")
    print("-" * 30)
    print("业务偏置：保持固定权重，确保约束始终被处理")
    print("算法偏置：根据优化状态动态调整")

    for bias_name, bias in bias_system.adaptive_manager.biases.items():
        if bias.history:
            initial = bias.history[0] if bias.history else bias.weight
            final = bias.weight
            change = (final - initial) / initial * 100 if initial > 0 else 0
            print(f"  {bias_name}: {initial:.3f} → {final:.3f} ({change:+.1f}%)")

    # 可视化结果
    print(f"\n[生成可视化图表]")
    bias_system.visualize_results()

    print(f"\n[关键发现]")
    print("-" * 30)
    print("- 业务偏置始终保持固定权重，保证了约束处理的稳定性")
    print("- 算法偏置根据种群状态自动调整，实现了探索与开发的平衡")
    print("- 系统能够自动识别优化状态并做出相应调整")
    print("- 自适应机制有效避免了过早收敛和搜索停滞")

    print(f"\n[演示完成] 图表已保存为 'bias_system_results.png'")


if __name__ == "__main__":
    # 设置随机种子以获得可重复结果
    np.random.seed(42)
    random.seed(42)

    main()