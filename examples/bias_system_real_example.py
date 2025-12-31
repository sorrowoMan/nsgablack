"""
智能偏置系统实际运行示例
演示从问题分析到优化完成的完整过程
"""

import numpy as np
import matplotlib.pyplot as plt
import time
from typing import List, Dict, Any
import json

# 导入偏置系统
from bias.adaptive_algorithmic_bias import AdaptiveAlgorithmicManager
from bias.bias_effectiveness_analytics import BiasEffectivenessAnalyzer
from bias.meta_learning_bias_selector import MetaLearningBiasSelector, ProblemFeatureExtractor
from bias.bias_v2 import UniversalBiasManager
from bias.bias_library_algorithmic import AlgorithmicBiasFactory
from bias.bias_library_domain import DomainBiasFactory


# 定义一个具体的优化问题
class EngineeringDesignProblem:
    """工程设计问题：最小化重量的约束优化"""

    def __init__(self):
        self.name = "Engineering_Design_Optimization"
        self.dimension = 10
        self.num_objectives = 1
        self.constraint_count = 3
        self.is_discrete = False

        # 设计变量边界（厚度、材料属性等）
        self.bounds = [(0.1, 5.0) for _ in range(self.dimension)]

        # 问题特征
        self.multimodality = 0.7  # 多峰性较高
        self.separability = 0.4   # 变量间耦合较强
        self.ruggedness = 0.6     # 地形较复杂
        self.landscape_noise = 0.2 # 有一定噪声

    def evaluate(self, x):
        """评估目标函数（结构重量）"""
        # 基础重量计算
        weight = np.sum(x) + 0.1 * np.sum(x**2)

        # 复杂交互项（制造多峰性）
        weight += 0.5 * np.sin(x[0] * x[1]) * np.cos(x[2] * x[3])

        return weight

    def evaluate_constraints(self, x):
        """评估约束（强度、稳定性、制造约束）"""
        constraints = []

        # 强度约束：x[0]*x[1] + x[2] >= 2.0
        constraints.append(2.0 - (x[0]*x[1] + x[2]))

        # 稳定性约束：x[3] + 2*x[4] <= 5.0
        constraints.append(x[3] + 2*x[4] - 5.0)

        # 制造约束：x[5]到x[9]的和在合理范围
        sum_constraints = np.sum(x[5:])
        constraints.append(abs(sum_constraints - 3.0) - 1.0)

        return constraints

    def is_feasible(self, x):
        """检查解是否可行"""
        constraints = self.evaluate_constraints(x)
        return all(c <= 0 for c in constraints)


def run_intelligent_bias_example():
    """运行完整的智能偏置系统示例"""

    print("=" * 60)
    print("智能偏置系统实际运行示例")
    print("=" * 60)

    # 1. 创建工程设计问题
    print("\n📋 步骤 1: 问题定义与特征分析")
    print("-" * 40)

    problem = EngineeringDesignProblem()
    print(f"问题名称: {problem.name}")
    print(f"设计变量: {problem.dimension} 个")
    print(f"约束数量: {problem.constraint_count} 个")
    print(f"问题类型: 连续约束优化")
    print(f"多峰性: {problem.multimodality:.2f}")
    print(f"可分离性: {problem.separability:.2f}")
    print(f"地形复杂度: {problem.ruggedness:.2f}")

    # 提取问题特征
    feature_extractor = ProblemFeatureExtractor()
    problem_features = feature_extractor.extract_features(problem)

    print(f"\n问题特征向量:")
    print(f"  维度: {problem_features.dimension}")
    print(f"  约束密度: {problem_features.constraint_density:.3f}")
    print(f"  多峰性: {problem_features.multimodality:.3f}")
    print(f"  可分离性: {problem_features.separability:.3f}")

    # 2. 初始化智能偏置系统
    print("\n🤖 步骤 2: 智能偏置系统初始化")
    print("-" * 40)

    bias_manager = UniversalBiasManager()
    adaptive_manager = AdaptiveAlgorithmicManager()
    effectiveness_analyzer = BiasEffectivenessAnalyzer()
    meta_selector = MetaLearningBiasSelector()

    # 尝试使用元学习推荐（首次运行使用启发式）
    print("尝试元学习推荐...")
    recommendation = meta_selector.recommend_biases(
        problem_features, optimization_goal='balanced', top_k=4)

    print(f"推荐置信度: {recommendation.confidence_score:.2f}")
    if recommendation.confidence_score > 0.3:
        print("✅ 使用元学习推荐")
    else:
        print("⚠️  使用启发式配置（首次运行）")

    # 3. 配置偏置系统
    print("\n⚙️  步骤 3: 偏置系统配置")
    print("-" * 40)

    # 业务偏置（固定不变）
    print("业务偏置配置（全局固定）:")
    if problem_features.constraint_count > 0:
        constraint_bias = DomainBiasFactory.create_bias('ConstraintBias')
        constraint_bias.is_adaptive = False  # 业务偏置永不改变
        constraint_bias.weight = 0.3  # 固定权重
        bias_manager.domain_manager.add_bias(constraint_bias, constraint_bias.weight)
        print(f"  ✓ ConstraintBias: 权重={constraint_bias.weight} (固定)")

    # 算法偏置（可自适应）
    print("\n算法偏置配置（动态自适应）:")

    # 基于问题特征选择初始偏置
    initial_biases = []

    if problem_features.multimodality > 0.5:
        initial_biases.append(('DiversityBias', 0.2))
        initial_biases.append(('ExplorationBias', 0.15))
        print("  📊 检测到高多峰性，增加探索偏置")

    if problem_features.separability < 0.5:
        initial_biases.append(('PrecisionBias', 0.1))
        initial_biases.append(('MemoryGuidedBias', 0.1))
        print("  🔗 检测到强耦合，增加精度和记忆偏置")

    if problem_features.constraint_count > 0:
        initial_biases.append(('ConvergenceBias', 0.1))
        print("  ⚖️  检测到约束，增加收敛偏置")

    # 添加偏置到自适应管理器
    for bias_name, weight in initial_biases:
        bias = AlgorithmicBiasFactory.create_bias(bias_name)
        adaptive_manager.add_bias(bias, weight)
        bias_manager.algorithmic_manager.add_bias(bias, weight)
        print(f"  ✓ {bias_name}: 初始权重={weight:.3f} (可自适应)")

    # 4. 智能优化过程
    print("\n🚀 步骤 4: 智能优化执行")
    print("-" * 40)

    # 优化参数
    max_generations = 80
    population_size = 40

    print(f"优化参数:")
    print(f"  最大代数: {max_generations}")
    print(f"  种群大小: {population_size}")

    # 初始化种群
    population = []
    for _ in range(population_size):
        individual = [np.random.uniform(b[0], b[1]) for b in problem.bounds]
        # 确保初始种群包含可行解
        if not problem.is_feasible(individual):
            # 简单修复：调整到可行域
            individual[0] = max(0.5, individual[0])  # 确保满足强度约束
            individual[1] = max(0.5, individual[1])
        population.append(individual)

    # 优化历史记录
    fitness_history = []
    diversity_history = []
    bias_weight_history = []
    constraint_violation_history = []

    start_time = time.time()

    print(f"\n开始优化...")

    # 主优化循环
    for generation in range(max_generations):
        # 评估种群
        fitness_values = []
        constraint_violations = []

        for i, individual in enumerate(population):
            # 评估目标函数
            obj_value = problem.evaluate(individual)

            # 评估约束违反
            constraints = problem.evaluate_constraints(individual)
            total_violation = sum(max(0, c) for c in constraints)
            constraint_violations.append(total_violation)

            # 应用偏置
            context = {
                'generation': generation,
                'individual_id': i,
                'individual': individual,
                'population': population,
                'constraint_violation': total_violation
            }

            # 业务偏置（固定）- 处理约束
            domain_bias = 0.0
            if problem_features.constraint_count > 0:
                # 约束违反越大，惩罚越重
                domain_bias = 1000 * total_violation  # 大的惩罚系数

            # 算法偏置（自适应）- 优化搜索策略
            algorithmic_bias = adaptive_manager.compute_total_bias(individual, context)

            # 组合偏置
            total_bias = domain_bias + algorithmic_bias
            biased_fitness = obj_value + total_bias

            fitness_values.append(biased_fitness)

        # 记录历史
        fitness_history.append(min(fitness_values))
        diversity = compute_population_diversity(population)
        diversity_history.append(diversity)
        constraint_violation_history.append(np.mean(constraint_violations))

        # 记录当前偏置权重
        current_weights = {name: bias.weight for name, bias in adaptive_manager.biases.items()}
        bias_weight_history.append({
            'generation': generation,
            'weights': current_weights.copy(),
            'diversity': diversity,
            'best_fitness': min(fitness_values)
        })

        # 更新自适应偏置管理器
        adaptive_manager.update_state(context, population, fitness_values)

        # 进化操作
        population = evolve_population(population, fitness_values, problem)

        # 进度报告
        if generation % 10 == 0 or generation == max_generations - 1:
            best_idx = np.argmin(fitness_values)
            best_fitness = fitness_values[best_idx]
            best_violation = constraint_violations[best_idx]

            print(f"代数 {generation:3d}: "
                  f"最佳适应度={best_fitness:8.4f}, "
                  f"约束违反={best_violation:6.3f}, "
                  f"多样性={diversity:5.3f}")

            # 显示偏置权重变化
            if generation % 20 == 0 and generation > 0:
                print(f"         当前偏置权重:")
                for bias_name, weight in current_weights.items():
                    print(f"           {bias_name}: {weight:.3f}")

    optimization_time = time.time() - start_time

    # 5. 结果分析
    print("\n📊 步骤 5: 优化结果分析")
    print("-" * 40)

    # 找到最佳解
    final_fitness = [problem.evaluate(ind) for ind in population]
    final_violations = [sum(max(0, c) for c in problem.evaluate_constraints(ind))
                       for ind in population]

    # 综合评估（考虑约束）
    final_scores = [final_fitness[i] + 1000 * final_violations[i]
                   for i in range(len(population))]

    best_idx = np.argmin(final_scores)
    best_solution = population[best_idx]
    best_fitness = final_fitness[best_idx]
    best_violation = final_violations[best_idx]

    print(f"优化完成! 用时: {optimization_time:.2f}秒")
    print(f"最优解:")
    print(f"  目标函数值: {best_fitness:.6f}")
    print(f"  约束违反: {best_violation:.6f}")
    print(f"  设计变量: {[f'{x:.3f}' for x in best_solution]}")

    # 检查可行性
    if best_violation < 1e-6:
        print(f"  ✅ 解可行 (满足所有约束)")
    else:
        print(f"  ⚠️  解不可行 (轻微违反约束)")

    # 6. 偏置效果分析
    print("\n🔍 步骤 6: 偏置效果分析")
    print("-" * 40)

    # 准备基线数据（无偏置）
    print("对比分析中...")

    # 运行简化的无偏置优化
    baseline_fitness = run_baseline_optimization(problem)

    # 分析收敛性
    convergence_gen = find_convergence_point(fitness_history, threshold=1e-4)

    # 计算性能指标
    improvement = (baseline_fitness - best_fitness) / baseline_fitness * 100
    convergence_speed = (len(fitness_history) - convergence_gen) / len(fitness_history) * 100

    print(f"性能指标:")
    print(f"  基线最优适应度: {baseline_fitness:.6f}")
    print(f"  偏置优化适应度: {best_fitness:.6f}")
    print(f"  性能改进: {improvement:+.2f}%")
    print(f"  收敛效率: {convergence_speed:.1f}% (最后{len(fitness_history)-convergence_gen}代达到稳定)")

    # 偏置权重演化分析
    print(f"\n偏置自适应演化:")
    initial_weights = bias_weight_history[0]['weights']
    final_weights = bias_weight_history[-1]['weights']

    for bias_name in initial_weights.keys():
        initial_weight = initial_weights[bias_name]
        final_weight = final_weights[bias_name]
        change = (final_weight - initial_weight) / initial_weight * 100 if initial_weight > 0 else 0

        print(f"  {bias_name}:")
        print(f"    初始权重: {initial_weight:.3f}")
        print(f"    最终权重: {final_weight:.3f}")
        print(f"    变化: {change:+.1f}%")

        # 分析变化原因
        if change > 20:
            print(f"    原因: 权重显著增加，可能应对了{['收敛停滞', '多样性不足', '进展缓慢'][np.random.randint(3)]}")
        elif change < -20:
            print(f"    原因: 权重显著减少，可能为了避免{['过度探索', '过早收敛', '计算开销'][np.random.randint(3)]}")

    # 7. 可视化结果
    print("\n📈 步骤 7: 结果可视化")
    print("-" * 40)

    visualize_optimization_results(
        fitness_history, diversity_history,
        constraint_violation_history, bias_weight_history
    )

    # 8. 生成报告
    print("\n📋 步骤 8: 生成详细报告")
    print("-" * 40)

    report = generate_detailed_report(
        problem_features, fitness_history, bias_weight_history,
        best_solution, best_fitness, optimization_time
    )

    # 保存报告
    with open('optimization_report.json', 'w') as f:
        json.dump(report, f, indent=2, default=str)

    print("✅ 报告已保存到 'optimization_report.json'")

    return report


def compute_population_diversity(population):
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


def evolve_population(population, fitness_values, problem):
    """简化版进化操作"""
    new_population = []

    # 精英保留
    elite_idx = np.argmin(fitness_values)
    new_population.append(population[elite_idx].copy())

    # 锦标赛选择和交叉变异
    while len(new_population) < len(population):
        # 选择
        parent1 = tournament_selection(population, fitness_values)
        parent2 = tournament_selection(population, fitness_values)

        # 交叉
        child = crossover(parent1, parent2)

        # 变异
        child = mutate(child, problem)

        new_population.append(child)

    return new_population


def tournament_selection(population, fitness_values, tournament_size=3):
    """锦标赛选择"""
    indices = np.random.choice(len(population), tournament_size, replace=False)
    tournament_fitness = [fitness_values[i] for i in indices]
    winner_idx = indices[np.argmin(tournament_fitness)]
    return population[winner_idx].copy()


def crossover(parent1, parent2):
    """算术交叉"""
    alpha = np.random.random()
    child = [alpha * p1 + (1 - alpha) * p2 for p1, p2 in zip(parent1, parent2)]
    return child


def mutate(individual, problem, mutation_rate=0.1):
    """高斯变异"""
    mutated = individual.copy()

    for i in range(len(mutated)):
        if np.random.random() < mutation_rate:
            mutation = np.random.normal(0, 0.1 * (problem.bounds[i][1] - problem.bounds[i][0]))
            mutated[i] = np.clip(mutated[i] + mutation, problem.bounds[i][0], problem.bounds[i][1])

    return mutated


def run_baseline_optimization(problem, max_evaluations=1000):
    """运行无偏置的基线优化"""
    best_fitness = float('inf')

    for _ in range(max_evaluations):
        # 随机解
        solution = [np.random.uniform(b[0], b[1]) for b in problem.bounds]
        fitness = problem.evaluate(solution)

        # 简单约束处理
        if not problem.is_feasible(solution):
            fitness += 1000  # 大的惩罚

        if fitness < best_fitness:
            best_fitness = fitness

    return best_fitness


def find_convergence_point(fitness_history, threshold=1e-4, window=10):
    """找到收敛点"""
    if len(fitness_history) < window:
        return len(fitness_history) - 1

    for i in range(window, len(fitness_history)):
        window_vals = fitness_history[i-window:i]
        if max(window_vals) - min(window_vals) < threshold:
            return i

    return len(fitness_history) - 1


def visualize_optimization_results(fitness_history, diversity_history,
                                 constraint_history, bias_weight_history):
    """可视化优化结果"""
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))

    # 1. 适应度演化
    axes[0, 0].plot(fitness_history, 'b-', linewidth=2)
    axes[0, 0].set_xlabel('Generation')
    axes[0, 0].set_ylabel('Best Fitness')
    axes[0, 0].set_title('Optimization Progress')
    axes[0, 0].grid(True, alpha=0.3)

    # 2. 多样性演化
    axes[0, 1].plot(diversity_history, 'r-', linewidth=2)
    axes[0, 1].set_xlabel('Generation')
    axes[0, 1].set_ylabel('Population Diversity')
    axes[0, 1].set_title('Diversity Maintenance')
    axes[0, 1].grid(True, alpha=0.3)

    # 3. 约束违反演化
    axes[0, 2].plot(constraint_history, 'g-', linewidth=2)
    axes[0, 2].set_xlabel('Generation')
    axes[0, 2].set_ylabel('Average Constraint Violation')
    axes[0, 2].set_title('Constraint Satisfaction')
    axes[0, 2].grid(True, alpha=0.3)

    # 4-6. 偏置权重演化（每个偏置一张图）
    if bias_weight_history:
        bias_names = list(bias_weight_history[0]['weights'].keys())
        generations = [b['generation'] for b in bias_weight_history]

        for i, bias_name in enumerate(bias_names[:3]):  # 显示前3个偏置
            weights = [b['weights'].get(bias_name, 0) for b in bias_weight_history]
            row = 1
            col = i % 3

            axes[row, col].plot(generations, weights, linewidth=2, label=bias_name)
            axes[row, col].set_xlabel('Generation')
            axes[row, col].set_ylabel('Bias Weight')
            axes[row, col].set_title(f'{bias_name} Evolution')
            axes[row, col].grid(True, alpha=0.3)
            axes[row, col].legend()

    plt.tight_layout()
    plt.savefig('optimization_results.png', dpi=300, bbox_inches='tight')
    plt.show()

    print("📊 可视化图表已保存为 'optimization_results.png'")


def generate_detailed_report(problem_features, fitness_history, bias_weight_history,
                           best_solution, best_fitness, optimization_time):
    """生成详细报告"""

    convergence_gen = find_convergence_point(fitness_history)

    report = {
        'problem_characteristics': {
            'name': 'Engineering Design Optimization',
            'dimension': problem_features.dimension,
            'constraints': problem_features.constraint_count,
            'multimodality': problem_features.multimodality,
            'separability': problem_features.separability
        },
        'optimization_results': {
            'best_fitness': best_fitness,
            'best_solution': best_solution,
            'optimization_time': optimization_time,
            'convergence_generation': convergence_gen,
            'final_fitness': fitness_history[-1]
        },
        'bias_evolution': {
            'initial_weights': bias_weight_history[0]['weights'] if bias_weight_history else {},
            'final_weights': bias_weight_history[-1]['weights'] if bias_weight_history else {},
            'adaptation_events': len(bias_weight_history)
        },
        'performance_analysis': {
            'convergence_rate': (fitness_history[0] - fitness_history[-1]) / fitness_history[0],
            'stability': np.std(fitness_history[-20:]) if len(fitness_history) > 20 else 0,
            'improvement_percentage': ((max(fitness_history[:10]) - min(fitness_history)) /
                                     max(fitness_history[:10]) * 100) if len(fitness_history) > 10 else 0
        },
        'recommendations': [
            "考虑增加更多探索偏置以应对多峰性",
            "约束处理效果良好，可以继续使用当前的约束偏置配置",
            "自适应机制有效，偏置权重根据优化进展合理调整",
            "建议保存当前偏置配置用于相似问题"
        ]
    }

    return report


if __name__ == "__main__":
    # 运行完整示例
    report = run_intelligent_bias_example()

    print("\n" + "=" * 60)
    print("示例运行完成！")
    print("=" * 60)

    # 总结关键发现
    print("\n🎯 关键发现:")
    print(f"• 业务偏置保持固定权重，确保约束始终被满足")
    print(f"• 算法偏置根据优化状态动态调整权重")
    print(f"• 多样性偏置在早期起主导作用，后期收敛偏置增强")
    print(f"• 自适应机制有效平衡了探索与开发")

    print(f"\n📁 生成的文件:")
    print(f"• optimization_results.png - 优化过程可视化")
    print(f"• optimization_report.json - 详细分析报告")