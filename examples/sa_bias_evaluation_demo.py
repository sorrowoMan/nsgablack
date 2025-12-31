"""
使用元学习系统评估模拟退火偏置
科学分析SA偏置的真实效果和使用价值
"""

import numpy as np
import matplotlib.pyplot as plt
from typing import List, Dict, Any
import time
import json

# 导入基础类
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bias_system_demo import EngineeringDesignProblem, DomainBias, AlgorithmicBias, AdaptiveBiasManager
from meta_learning_bias_demo import BiasEffectivenessTracker, MetaLearningBiasSelector


# 模拟退火偏置实现
class SimulatedAnnealingBias:
    """模拟退火偏置"""

    def __init__(self, initial_weight=0.15, initial_temperature=100.0, cooling_rate=0.995):
        self.name = "SimulatedAnnealing"
        self.weight = initial_weight
        self.initial_temperature = initial_temperature
        self.cooling_rate = cooling_rate
        self.current_temperature = initial_temperature
        self.acceptance_history = []

    def compute_bias(self, x, context):
        generation = context.get('generation', 0)
        self.current_temperature = self.initial_temperature * (self.cooling_rate ** generation)

        current_energy = context.get('current_energy', 0)
        previous_energy = context.get('previous_energy', 0)

        if previous_energy is None:
            return 0.0

        delta_energy = current_energy - previous_energy

        if delta_energy <= 0:
            return -self.weight * abs(delta_energy) * 0.1
        else:
            if self.current_temperature > 0:
                acceptance_prob = np.exp(-delta_energy / self.current_temperature)
                return self.weight * acceptance_prob * delta_energy * 0.1
            return 0.0


class SABiasEvaluationSystem:
    """SA偏置评估系统"""

    def __init__(self):
        self.effectiveness_tracker = BiasEffectivenessTracker()
        self.meta_learner = MetaLearningBiasSelector()
        self.evaluation_results = []

    def evaluate_sa_bias_on_multiple_problems(self):
        """在多个问题上评估SA偏置"""
        print("=" * 70)
        print("模拟退火偏置科学评估")
        print("使用元学习系统分析SA偏置的真实效果")
        print("=" * 70)

        # 创建不同复杂度的测试问题
        test_problems = self._create_test_problems()

        print(f"创建了 {len(test_problems)} 个不同特征的测试问题")

        # 对每个问题进行对比测试
        all_results = []

        for i, problem in enumerate(test_problems):
            print(f"\n{'='*20} 测试问题 {i+1}/{len(test_problems)} {'='*20}")
            print(f"问题特征:")
            print(f"  多峰性: {problem.multimodality:.2f}")
            print(f"  可分离性: {problem.separability:.2f}")
            print(f"  维度: {problem.dimension}")

            # 无SA偏置的优化
            baseline_result = self._optimize_without_sa(problem, max_generations=60)

            # 有SA偏置的优化
            sa_result = self._optimize_with_sa(problem, max_generations=60)

            # 记录结果
            problem_result = {
                'problem_id': i,
                'multimodality': problem.multimodality,
                'separability': problem.separability,
                'dimension': problem.dimension,
                'baseline_fitness': baseline_result['final_fitness'],
                'sa_fitness': sa_result['final_fitness'],
                'baseline_convergence': baseline_result['convergence_generation'],
                'sa_convergence': sa_result['convergence_generation'],
                'improvement': (baseline_result['final_fitness'] - sa_result['final_fitness']) / baseline_result['final_fitness'] * 100 if baseline_result['final_fitness'] > 0 else 0,
                'bias_usage': sa_result['bias_usage']
            }

            all_results.append(problem_result)

            # 分析本次优化的偏置效果
            self._analyze_sa_bias_performance(problem_result)

            print(f"结果对比:")
            print(f"  基线优化: {baseline_result['final_fitness']:.6f} (第{baseline_result['convergence_generation']}代收敛)")
            print(f"  SA增强: {sa_result['final_fitness']:.6f} (第{sa_result['convergence_generation']}代收敛)")
            improvement = problem_result['improvement']
            print(f"  性能改进: {improvement:+.2f}%")

        # 综合分析
        self._comprehensive_analysis(all_results)

        # 生成详细报告
        report = self._generate_evaluation_report(all_results)

        # 可视化结果
        self._visualize_evaluation_results(all_results)

        return report

    def _create_test_problems(self):
        """创建不同复杂度的测试问题"""
        problems = []

        # 问题1: 简单问题（低多峰性，高可分离性）
        problem1 = EngineeringDesignProblem()
        problem1.multimodality = 0.2
        problem1.separability = 0.9
        problem1.dimension = 5
        problems.append(problem1)

        # 问题2: 中等复杂度（中等多峰性，中等可分离性）
        problem2 = EngineeringDesignProblem()
        problem2.multimodality = 0.5
        problem2.separability = 0.5
        problem2.dimension = 8
        problems.append(problem2)

        # 问题3: 复杂问题（高多峰性，低可分离性）
        problem3 = EngineeringDesignProblem()
        problem3.multimodality = 0.8
        problem3.separability = 0.3
        problem3.dimension = 10
        problems.append(problem3)

        # 问题4: 超高多峰性（极难优化）
        problem4 = EngineeringDesignProblem()
        problem4.multimodality = 0.95
        problem4.separability = 0.2
        problem4.dimension = 12
        problems.append(problem4)

        # 问题5: 高维问题
        problem5 = EngineeringDesignProblem()
        problem5.multimodality = 0.6
        problem5.separability = 0.4
        problem5.dimension = 20
        # 扩展边界
        problem5.bounds = [(0.1, 5.0)] * problem5.dimension
        problems.append(problem5)

        return problems

    def _optimize_without_sa(self, problem, max_generations=60):
        """不使用SA偏置的基准优化"""
        bias_manager = AdaptiveBiasManager()
        domain_bias = DomainBias()

        # 只添加传统偏置，不添加SA偏置
        diversity_bias = AlgorithmicBias("DiversityBias", 0.15)
        convergence_bias = AlgorithmicBias("ConvergenceBias", 0.1)
        bias_manager.add_bias(diversity_bias)
        bias_manager.add_bias(convergence_bias)

        # 运行优化
        population = self._initialize_population(problem, 30)
        fitness_history = []

        for generation in range(max_generations):
            fitness_values = []
            for individual in population:
                obj_value = problem.evaluate(individual)
                constraints = problem.evaluate_constraints(individual)
                total_violation = sum(max(0, c) for c in constraints)

                # 只使用业务偏置和传统算法偏置
                domain_bias_value = domain_bias.compute_bias(individual, total_violation)

                context = {'generation': generation, 'population': population}
                algorithmic_bias_value = bias_manager.compute_total_bias(individual, context)

                total_fitness = obj_value + domain_bias_value + algorithmic_bias_value
                fitness_values.append(total_fitness)

            fitness_history.append(min(fitness_values))
            population = self._evolve_population(population, fitness_values, problem)

        return {
            'final_fitness': min([problem.evaluate(ind) for ind in population]),
            'convergence_generation': self._find_convergence_point(fitness_history),
            'fitness_history': fitness_history
        }

    def _optimize_with_sa(self, problem, max_generations=60):
        """使用SA偏置的优化"""
        bias_manager = AdaptiveBiasManager()
        domain_bias = DomainBias()
        sa_bias = SimulatedAnnealingBias(initial_weight=0.15, initial_temperature=50.0, cooling_rate=0.98)

        # 添加所有偏置，包括SA偏置
        diversity_bias = AlgorithmicBias("DiversityBias", 0.1)
        convergence_bias = AlgorithmicBias("ConvergenceBias", 0.1)
        sa_algo_bias = AlgorithmicBias("SimulatedAnnealing", sa_bias.weight)

        bias_manager.add_bias(diversity_bias)
        bias_manager.add_bias(convergence_bias)
        bias_manager.add_bias(sa_algo_bias)

        # 运行优化并追踪SA偏置使用
        population = self._initialize_population(problem, 30)
        fitness_history = []
        bias_usage = {'SimulatedAnnealing': []}
        previous_energies = []

        for generation in range(max_generations):
            fitness_values = []
            generation_sa_contributions = []

            for i, individual in enumerate(population):
                obj_value = problem.evaluate(individual)
                constraints = problem.evaluate_constraints(individual)
                total_violation = sum(max(0, c) for c in constraints)

                # 记录能量
                if i < len(previous_energies):
                    previous_energy = previous_energies[i]
                else:
                    previous_energy = obj_value

                # 应用所有偏置
                domain_bias_value = domain_bias.compute_bias(individual, total_violation)

                context = {
                    'generation': generation,
                    'individual': individual,
                    'population': population,
                    'current_energy': obj_value,
                    'previous_energy': previous_energy
                }
                algorithmic_bias_value = bias_manager.compute_total_bias(individual, context)
                sa_bias_value = sa_bias.compute_bias(individual, context)

                generation_sa_contributions.append(sa_bias_value)
                previous_energies.append(obj_value)

                total_fitness = obj_value + domain_bias_value + algorithmic_bias_value + sa_bias_value
                fitness_values.append(total_fitness)

            # 记录SA偏置使用情况
            if generation_sa_contributions:
                bias_usage['SimulatedAnnealing'].append({
                    'generation': generation,
                    'weight': sa_bias.weight,
                    'temperature': sa_bias.current_temperature,
                    'avg_contribution': np.mean(generation_sa_contributions),
                    'contribution_std': np.std(generation_sa_contributions)
                })

            fitness_history.append(min(fitness_values))
            population = self._evolve_population(population, fitness_values, problem)

        return {
            'final_fitness': min([problem.evaluate(ind) for ind in population]),
            'convergence_generation': self._find_convergence_point(fitness_history),
            'fitness_history': fitness_history,
            'bias_usage': bias_usage
        }

    def _analyze_sa_bias_performance(self, problem_result):
        """分析SA偏置在特定问题上的表现"""
        bias_usage = problem_result['bias_usage']

        if 'SimulatedAnnealing' in bias_usage and bias_usage['SimulatedAnnealing']:
            sa_data = bias_usage['SimulatedAnnealing']

            # 计算统计指标
            contributions = [d['avg_contribution'] for d in sa_data]
            temperatures = [d['temperature'] for d in sa_data]
            weights = [d['weight'] for d in sa_data]

            analysis = {
                'avg_contribution': np.mean(contributions),
                'contribution_stability': 1.0 - (np.std(contributions) / (np.abs(np.mean(contributions)) + 1e-6)),
                'temperature_range': (max(temperatures), min(temperatures)),
                'total_usage': len(sa_data)
            }

            # 判断效果
            if analysis['avg_contribution'] < -0.01:
                effect_status = "有效"
            elif analysis['avg_contribution'] > 0.01:
                effect_status = "有害"
            else:
                effect_status = "中性"

            print(f"\nSA偏置效果分析:")
            print(f"  状态: {effect_status}")
            print(f"  平均贡献: {analysis['avg_contribution']:+.4f}")
            print(f"  稳定性: {analysis['contribution_stability']:.2f}")
            print(f"  温度范围: {analysis['temperature_range'][1]:.2f} → {analysis['temperature_range'][0]:.2f}")
            print(f"  使用次数: {analysis['total_usage']}")

            return analysis

        return None

    def _comprehensive_analysis(self, all_results):
        """综合分析所有问题的SA偏置效果"""
        print(f"\n{'='*20} 综合分析 {'='*20}")

        improvements = [r['improvement'] for r in all_results]
        multimodalities = [r['multimodality'] for r in all_results]
        separabilities = [r['separability'] for r in all_results]

        avg_improvement = np.mean(improvements)
        positive_improvements = sum(1 for imp in improvements if imp > 0)
        negative_improvements = sum(1 for imp in improvements if imp < 0)

        print(f"总体统计:")
        print(f"  平均改进: {avg_improvement:+.2f}%")
        print(f"  有效问题数: {positive_improvements}/{len(all_results)}")
        print(f"  无效问题数: {negative_improvements}/{len(all_results)}")

        # 按问题复杂度分析
        low_complexity = [(r, imp) for r, imp in zip(all_results, improvements) if r['multimodality'] < 0.4]
        medium_complexity = [(r, imp) for r, imp in zip(all_results, improvements) if 0.4 <= r['multimodality'] < 0.7]
        high_complexity = [(r, imp) for r, imp in zip(all_results, improvements) if r['multimodality'] >= 0.7]

        print(f"\n按复杂度分析:")
        print(f"  低复杂度 (多峰性 < 0.4): 平均改进 {np.mean([imp for r, imp in low_complexity]):+.2f}% ({len(low_complexity)}个问题)")
        print(f"  中等复杂度 (0.4 ≤ 多峰性 < 0.7): 平均改进 {np.mean([imp for r, imp in medium_complexity]):+.2f}% ({len(medium_complexity)}个问题)")
        print(f"  高复杂度 (多峰性 ≥ 0.7): 平均改进 {np.mean([imp for r, imp in high_complexity]):+.2f}% ({len(high_complexity)}个问题)")

        # 相关性分析
        correlation = np.corrcoef(multimodalities, improvements)[0, 1] if len(multimodalities) > 1 else 0
        print(f"\n相关性分析:")
        print(f"  多峰性与改进效果的相关性: {correlation:.3f}")

    def _generate_evaluation_report(self, all_results):
        """生成详细评估报告"""
        report = {
            'evaluation_summary': {
                'total_problems': len(all_results),
                'avg_improvement': np.mean([r['improvement'] for r in all_results]),
                'positive_results': sum(1 for r in all_results if r['improvement'] > 0),
                'negative_results': sum(1 for r in all_results if r['improvement'] < 0)
            },
            'detailed_results': all_results,
            'recommendations': [],
            'conclusions': []
        }

        # 生成建议
        avg_improvement = report['evaluation_summary']['avg_improvement']
        if avg_improvement > 5:
            report['recommendations'].append("SA偏置总体有效，建议在大多数情况下使用")
        elif avg_improvement < -5:
            report['recommendations'].append("SA偏置总体有害，建议谨慎使用或禁用")
        else:
            report['recommendations'].append("SA偏置效果有限，建议根据问题特征选择性使用")

        # 按问题复杂度给出建议
        high_complexity_results = [r for r in all_results if r['multimodality'] >= 0.7]
        if high_complexity_results:
            high_complexity_improvement = np.mean([r['improvement'] for r in high_complexity_results])
            if high_complexity_improvement > 3:
                report['recommendations'].append("SA偏置在高复杂度问题上效果显著，推荐用于多峰性问题")
            else:
                report['recommendations'].append("SA偏置在高复杂度问题上效果有限，可能需要参数调整")

        # 生成结论
        report['conclusions'] = [
            f"SA偏置在{len(all_results)}个测试问题上的平均改进为{avg_improvement:+.2f}%",
            f"有效性问题占比: {report['evaluation_summary']['positive_results']}/{len(all_results)} ({report['evaluation_summary']['positive_results']/len(all_results)*100:.1f}%)",
            "SA偏置的效果与问题复杂度相关，需要根据具体问题特征决定是否使用"
        ]

        return report

    def _visualize_evaluation_results(self, all_results):
        """可视化评估结果"""
        fig, axes = plt.subplots(2, 3, figsize=(18, 12))

        # 数据提取
        multimodalities = [r['multimodality'] for r in all_results]
        improvements = [r['improvement'] for r in all_results]
        separabilities = [r['separability'] for r in all_results]
        baseline_fitness = [r['baseline_fitness'] for r in all_results]
        sa_fitness = [r['sa_fitness'] for r in all_results]

        # 1. 改进效果分布
        axes[0, 0].hist(improvements, bins=10, alpha=0.7, color='skyblue', edgecolor='black')
        axes[0, 0].axvline(x=0, color='red', linestyle='--', label='零改进线')
        axes[0, 0].set_xlabel('改进率 (%)')
        axes[0, 0].set_ylabel('频次')
        axes[0, 0].set_title('SA偏置改进效果分布')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)

        # 2. 多峰性 vs 改进效果
        axes[0, 1].scatter(multimodalities, improvements, alpha=0.7, s=100, c=separabilities, cmap='viridis')
        axes[0, 1].set_xlabel('多峰性')
        axes[0, 1].set_ylabel('改进率 (%)')
        axes[0, 1].set_title('多峰性 vs SA偏置效果')
        plt.colorbar(axes[0, 1].collections[0], ax=axes[0, 1], label='可分离性')
        axes[0, 1].grid(True, alpha=0.3)

        # 3. 性能对比（基线 vs SA）
        x_pos = np.arange(len(all_results))
        width = 0.35
        axes[0, 2].bar(x_pos - width/2, baseline_fitness, width, label='基线优化', alpha=0.7)
        axes[0, 2].bar(x_pos + width/2, sa_fitness, width, label='SA增强', alpha=0.7)
        axes[0, 2].set_xlabel('问题编号')
        axes[0, 2].set_ylabel('最终适应度')
        axes[0, 2].set_title('基线 vs SA增强性能对比')
        axes[0, 2].set_xticks(x_pos)
        axes[0, 2].set_xticklabels([f'P{i+1}' for i in range(len(all_results))])
        axes[0, 2].legend()
        axes[0, 2].grid(True, alpha=0.3)

        # 4. 收敛速度对比
        baseline_conv = [r['baseline_convergence'] for r in all_results]
        sa_conv = [r['sa_convergence'] for r in all_results]
        axes[1, 0].plot(x_pos, baseline_conv, 'o-', label='基线收敛', linewidth=2, markersize=8)
        axes[1, 0].plot(x_pos, sa_conv, 's-', label='SA收敛', linewidth=2, markersize=8)
        axes[1, 0].set_xlabel('问题编号')
        axes[1, 0].set_ylabel('收敛代数')
        axes[1, 0].set_title('收敛速度对比')
        axes[1, 0].set_xticks(x_pos)
        axes[1, 0].set_xticklabels([f'P{i+1}' for i in range(len(all_results))])
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)

        # 5. 问题特征散点图
        axes[1, 1].scatter(multimodalities, separabilities, c=improvements, s=200, cmap='RdYlBu', alpha=0.7)
        axes[1, 1].set_xlabel('多峰性')
        axes[1, 1].set_ylabel('可分离性')
        axes[1, 1].set_title('问题特征分布 (颜色=改进效果)')
        plt.colorbar(axes[1, 1].collections[0], ax=axes[1, 1], label='改进率 (%)')
        axes[1, 1].grid(True, alpha=0.3)

        # 6. SA偏置效果热力图
        if len(all_results) >= 3:
            # 创建热力图数据
            effect_matrix = np.zeros((3, 3))
            category_labels = ['低多峰性', '中多峰性', '高多峰性']

            for i, result in enumerate(all_results):
                multi_cat = min(int(result['multimodality'] * 3), 2)
                sep_cat = min(int(result['separability'] * 3), 2)
                effect_matrix[multi_cat, sep_cat] += result['improvement']

            im = axes[1, 2].imshow(effect_matrix, cmap='RdYlGn', aspect='auto')
            axes[1, 2].set_xticks(range(3))
            axes[1, 2].set_yticks(range(3))
            axes[1, 2].set_xticklabels(['低可分离', '中可分离', '高可分离'])
            axes[1, 2].set_yticklabels(category_labels)
            axes[1, 2].set_title('SA偏置效果热力图')

            # 添加数值标注
            for i in range(3):
                for j in range(3):
                    text = axes[1, 2].text(j, i, f'{effect_matrix[i, j]:+.1f}%',
                                           ha="center", va="center", color="black")

            plt.colorbar(im, ax=axes[1, 2], label='平均改进率 (%)')

        plt.tight_layout()
        plt.savefig('sa_bias_evaluation_results.png', dpi=300, bbox_inches='tight')
        plt.show()

        print(f"\n[评估结果图表已保存为 sa_bias_evaluation_results.png]")

    def _initialize_population(self, problem, population_size):
        """初始化种群"""
        population = []
        for _ in range(population_size):
            individual = [np.random.uniform(b[0], b[1]) for b in problem.bounds]
            population.append(individual)
        return population

    def _evolve_population(self, population, fitness_values, problem):
        """进化操作"""
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

    def _mutate(self, individual, problem):
        """高斯变异"""
        mutated = individual.copy()
        for i in range(len(mutated)):
            if np.random.random() < 0.1:
                bounds = problem.bounds[i]
                mutation = np.random.normal(0, 0.1 * (bounds[1] - bounds[0]))
                mutated[i] = np.clip(mutated[i] + mutation, bounds[0], bounds[1])
        return mutated

    def _find_convergence_point(self, fitness_history, threshold=1e-4):
        """找到收敛点"""
        if len(fitness_history) < 10:
            return len(fitness_history)
        for i in range(10, len(fitness_history)):
            window = fitness_history[i-10:i]
            if max(window) - min(window) < threshold:
                return i
        return len(fitness_history)


def main():
    """主函数"""
    print("模拟退火偏置科学评估系统")
    print("使用元学习框架客观分析SA偏置的真实价值")

    # 创建评估系统
    evaluator = SABiasEvaluationSystem()

    # 执行评估
    report = evaluator.evaluate_sa_bias_on_multiple_problems()

    # 显示最终结论
    print(f"\n{'='*20} 最终结论 {'='*20}")

    summary = report['evaluation_summary']
    print(f"评估总结:")
    print(f"  测试问题数: {summary['total_problems']}")
    print(f"  平均改进: {summary['avg_improvement']:+.2f}%")
    print(f"  有效问题: {summary['positive_results']}")
    print(f"  无效问题: {summary['negative_results']}")

    print(f"\n建议:")
    for i, recommendation in enumerate(report['recommendations'], 1):
        print(f"  {i}. {recommendation}")

    print(f"\n核心发现:")
    for i, conclusion in enumerate(report['conclusions'], 1):
        print(f"  {i}. {conclusion}")

    # 保存详细报告
    with open('sa_bias_evaluation_report.json', 'w') as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n[详细报告已保存为 sa_bias_evaluation_report.json]")

    # 判断SA偏置的价值
    if summary['avg_improvement'] > 2:
        print(f"\n[OK] SA偏置具有实际价值，值得在合适的问题中使用")
    elif summary['avg_improvement'] < -2:
        print(f"\n[BAD] SA偏置在当前配置下效果不佳，需要调整或谨慎使用")
    else:
        print(f"\n[NEUTRAL] SA偏置效果有限，需要根据问题特征选择性使用")


if __name__ == "__main__":
    # 设置随机种子
    np.random.seed(42)

    main()