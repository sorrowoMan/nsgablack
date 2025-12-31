"""
智能偏置系统完整演示
展示自适应算法偏置 + 效果评估 + 元学习的完整工作流程
"""

import numpy as np
import matplotlib.pyplot as plt
import time
from typing import List, Dict, Any
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 导入偏置系统组件
from bias.adaptive_algorithmic_bias import AdaptiveAlgorithmicManager, OptimizationState
from bias.bias_effectiveness_analytics import BiasEffectivenessAnalyzer, BiasEffectivenessMetrics
from bias.meta_learning_bias_selector import MetaLearningBiasSelector, ProblemFeatureExtractor
from bias.bias_v2 import UniversalBiasManager, AlgorithmicBiasManager, DomainBiasManager
from bias.bias_library_algorithmic import AlgorithmicBiasFactory
from bias.bias_library_domain import DomainBiasFactory

# 导入测试问题
from core.problems import SyntheticTestProblem


class IntelligentBiasSystem:
    """智能偏置系统整合类"""

    def __init__(self):
        self.bias_manager = UniversalBiasManager()
        self.adaptive_manager = AdaptiveAlgorithmicManager()
        self.effectiveness_analyzer = BiasEffectivenessAnalyzer()
        self.meta_selector = MetaLearningBiasSelector()
        self.feature_extractor = ProblemFeatureExtractor()

        # 优化历史记录
        self.optimization_history: List[Dict] = []

        logger.info("Intelligent Bias System initialized")

    def setup_initial_biases(self, problem_features):
        """设置初始偏置配置"""
        # 尝试使用元学习推荐
        recommendation = self.meta_selector.recommend_biases(
            problem_features, optimization_goal='balanced')

        if recommendation.confidence_score > 0.3:
            logger.info(f"Using meta-learning recommendation (confidence: {recommendation.confidence_score:.2f})")
            self._apply_recommendation(recommendation)
        else:
            logger.info("Using default bias configuration")
            self._setup_default_biases(problem_features)

    def _apply_recommendation(self, recommendation):
        """应用元学习推荐"""
        # 添加算法偏置（自适应）
        for bias_name, weight in recommendation.algorithmic_biases.items():
            try:
                bias = AlgorithmicBiasFactory.create_bias(bias_name)
                self.adaptive_manager.add_bias(bias, weight)
                self.bias_manager.algorithmic_manager.add_bias(bias, weight)
            except Exception as e:
                logger.warning(f"Failed to add algorithmic bias {bias_name}: {e}")

        # 添加业务偏置（固定）
        for bias_name, weight in recommendation.domain_biases.items():
            try:
                bias = DomainBiasFactory.create_bias(bias_name, **{})
                bias.is_adaptive = False  # 业务偏置固定不变
                self.bias_manager.domain_manager.add_bias(bias, weight)
            except Exception as e:
                logger.warning(f"Failed to add domain bias {bias_name}: {e}")

        logger.info(f"Applied {len(recommendation.algorithmic_biases)} algorithmic and "
                   f"{len(recommendation.domain_biases)} domain biases")

    def _setup_default_biases(self, problem_features):
        """设置默认偏置配置"""
        # 默认算法偏置（自适应）
        default_algorithmic = [
            ('DiversityBias', 0.15),
            ('ExplorationBias', 0.1),
            ('ConvergenceBias', 0.1),
            ('PrecisionBias', 0.05)
        ]

        for bias_name, weight in default_algorithmic:
            try:
                bias = AlgorithmicBiasFactory.create_bias(bias_name)
                self.adaptive_manager.add_bias(bias, weight)
                self.bias_manager.algorithmic_manager.add_bias(bias, weight)
            except Exception as e:
                logger.warning(f"Failed to add default algorithmic bias {bias_name}: {e}")

        # 默认业务偏置（根据问题类型）
        if problem_features.constraint_count > 0:
            try:
                constraint_bias = DomainBiasFactory.create_bias('ConstraintBias')
                constraint_bias.is_adaptive = False
                self.bias_manager.domain_manager.add_bias(constraint_bias, 0.3)
            except Exception as e:
                logger.warning(f"Failed to add constraint bias: {e}")

    def optimize_with_intelligent_bias(self, problem, max_generations=100, population_size=50):
        """使用智能偏置系统进行优化"""
        logger.info(f"Starting optimization with intelligent bias for {max_generations} generations")

        # 提取问题特征
        problem_features = self.feature_extractor.extract_features(problem)
        logger.info(f"Problem features extracted: {problem_features.problem_type}, "
                   f"{problem_features.dimension}D, {problem_features.num_objectives} objectives")

        # 设置初始偏置
        self.setup_initial_biases(problem_features)

        # 初始化种群
        population = self._initialize_population(problem, population_size)
        fitness_history = []
        diversity_history = []
        adaptation_history = []

        start_time = time.time()

        # 主优化循环
        for generation in range(max_generations):
            # 评估种群
            fitness_values = []
            for i, individual in enumerate(population):
                # 计算目标函数值
                obj_value = problem.evaluate(individual)

                # 应用偏置
                context = OptimizationContext(
                    generation=generation,
                    individual_id=i,
                    individual=individual,
                    population=population,
                    generation_data={'generation': generation}
                )

                # 业务偏置（固定）
                domain_bias = self.bias_manager.domain_manager.compute_total_bias(
                    individual, context)

                # 算法偏置（自适应）
                algorithmic_bias = self.adaptive_manager.compute_total_bias(
                    individual, context)

                # 组合偏置
                total_bias = domain_bias + algorithmic_bias
                biased_fitness = obj_value + total_bias

                fitness_values.append(biased_fitness)

            # 记录历史
            fitness_history.append(min(fitness_values))
            diversity = self._compute_diversity(population)
            diversity_history.append(diversity)

            # 更新自适应偏置管理器
            self.adaptive_manager.update_state(context, population, fitness_values)

            # 记录自适应历史
            bias_weights = {name: bias.weight for name, bias in self.adaptive_manager.biases.items()}
            adaptation_history.append({
                'generation': generation,
                'bias_weights': bias_weights.copy(),
                'diversity': diversity,
                'best_fitness': min(fitness_values)
            })

            # 选择和变异（简化版）
            population = self._evolve_population(population, fitness_values, problem)

            # 进度报告
            if generation % 10 == 0:
                logger.info(f"Generation {generation}: Best fitness = {min(fitness_values):.6f}, "
                           f"Diversity = {diversity:.3f}")

        # 记录优化结果
        optimization_time = time.time() - start_time
        self.optimization_history.append({
            'problem_features': problem_features,
            'fitness_history': fitness_history,
            'diversity_history': diversity_history,
            'adaptation_history': adaptation_history,
            'computation_time': optimization_time,
            'final_best_fitness': min(fitness_history),
            'generations_to_convergence': self._find_convergence_generation(fitness_history)
        })

        logger.info(f"Optimization completed in {optimization_time:.2f}s")
        logger.info(f"Final best fitness: {min(fitness_history):.6f}")

        return min(fitness_history), population[np.argmin(fitness_values)]

    def _initialize_population(self, problem, population_size):
        """初始化种群"""
        population = []
        bounds = getattr(problem, 'bounds', [(0, 1)] * problem.dimension)

        for _ in range(population_size):
            individual = [np.random.uniform(b[0], b[1]) for b in bounds]
            population.append(individual)

        return population

    def _evolve_population(self, population, fitness_values, problem):
        """进化种群（简化版遗传算法）"""
        # 锦标赛选择
        new_population = []
        for _ in range(len(population)):
            # 选择两个父代
            parent1 = self._tournament_selection(population, fitness_values, 3)
            parent2 = self._tournament_selection(population, fitness_values, 3)

            # 交叉
            child = self._crossover(parent1, parent2)

            # 变异
            child = self._mutation(child, problem)

            new_population.append(child)

        return new_population

    def _tournament_selection(self, population, fitness_values, tournament_size):
        """锦标赛选择"""
        tournament_indices = np.random.choice(len(population), tournament_size, replace=False)
        tournament_fitness = [fitness_values[i] for i in tournament_indices]
        winner_index = tournament_indices[np.argmin(tournament_fitness)]
        return population[winner_index]

    def _crossover(self, parent1, parent2):
        """算术交叉"""
        alpha = np.random.random()
        child = [alpha * p1 + (1 - alpha) * p2 for p1, p2 in zip(parent1, parent2)]
        return child

    def _mutation(self, individual, problem, mutation_rate=0.1):
        """高斯变异"""
        mutated = individual.copy()
        bounds = getattr(problem, 'bounds', [(0, 1)] * problem.dimension)

        for i in range(len(mutated)):
            if np.random.random() < mutation_rate:
                mutation = np.random.normal(0, 0.1 * (bounds[i][1] - bounds[i][0]))
                mutated[i] = np.clip(mutated[i] + mutation, bounds[i][0], bounds[i][1])

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

    def _find_convergence_generation(self, fitness_history, threshold=1e-6, window=20):
        """找到收敛代数"""
        if len(fitness_history) < window:
            return len(fitness_history) - 1

        for i in range(window, len(fitness_history)):
            window_vals = fitness_history[i-window:i]
            if max(window_vals) - min(window_vals) < threshold:
                return i

        return len(fitness_history) - 1

    def evaluate_bias_effectiveness(self, num_baseline_runs=5):
        """评估偏置效果"""
        logger.info("Evaluating bias effectiveness")

        if len(self.optimization_history) == 0:
            logger.warning("No optimization history available")
            return

        # 获取最后一次优化的特征
        last_run = self.optimization_history[-1]
        problem_features = last_run['problem_features']

        # 运行基线对比（无偏置）
        baseline_runs = []
        for i in range(num_baseline_runs):
            logger.info(f"Running baseline optimization {i+1}/{num_baseline_runs}")
            baseline_fitness = self._run_baseline_optimization(problem_features)
            baseline_runs.append(baseline_fitness)

        # 准备偏置运行数据
        biased_runs = [last_run]

        # 评估每个偏置的效果
        bias_metrics = {}

        # 评估算法偏置
        for bias_name in self.adaptive_manager.biases.keys():
            # 简化处理：为每个偏置创建虚拟评估
            metrics = self.effectiveness_analyzer.evaluate_bias(
                bias_name=bias_name,
                bias_type='algorithmic',
                biased_runs=biased_runs,
                baseline_runs=baseline_runs
            )
            bias_metrics[bias_name] = metrics

        # 评估业务偏置
        for bias_name in self.bias_manager.domain_manager.biases.keys():
            metrics = self.effectiveness_analyzer.evaluate_bias(
                bias_name=bias_name,
                bias_type='domain',
                biased_runs=biased_runs,
                baseline_runs=baseline_runs
            )
            bias_metrics[bias_name] = metrics

        # 生成报告
        report = self.effectiveness_analyzer.generate_report()
        logger.info("Bias effectiveness evaluation completed")

        return report, bias_metrics

    def _run_baseline_optimization(self, problem_features):
        """运行无偏置的基线优化"""
        # 简化的基线优化（随机搜索）
        best_fitness = float('inf')
        best_solution = None

        for _ in range(1000):  # 简化的评估次数
            solution = np.random.uniform(-10, 10, problem_features.dimension)
            fitness = np.sum(solution**2)  # 简化的球函数

            if fitness < best_fitness:
                best_fitness = fitness
                best_solution = solution

        return best_fitness

    def train_meta_learning_model(self):
        """训练元学习模型"""
        if len(self.optimization_history) == 0:
            logger.warning("No optimization data available for training")
            return

        logger.info("Training meta-learning model")

        # 准备训练数据
        for run_data in self.optimization_history:
            problem_features = run_data['problem_features']

            # 为每次运行创建偏置效果指标
            # 这里简化处理，实际应该从详细分析中获取
            bias_metrics = {}

            # 添加到元学习系统
            self.meta_selector.add_historical_data(problem_features, bias_metrics)

        # 训练模型
        training_results = self.meta_selector.train_models()

        if 'error' not in training_results:
            logger.info("Meta-learning model trained successfully")
        else:
            logger.warning(f"Meta-learning training failed: {training_results['error']}")

        return training_results

    def visualize_results(self):
        """可视化结果"""
        if not self.optimization_history:
            logger.warning("No optimization history to visualize")
            return

        # 创建子图
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))

        # 1. 优化过程
        last_run = self.optimization_history[-1]
        fitness_history = last_run['fitness_history']
        diversity_history = last_run['diversity_history']

        axes[0, 0].plot(fitness_history, 'b-', label='Fitness')
        axes[0, 0].set_xlabel('Generation')
        axes[0, 0].set_ylabel('Best Fitness')
        axes[0, 0].set_title('Optimization Progress')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)

        # 2. 多样性变化
        axes[0, 1].plot(diversity_history, 'r-', label='Diversity')
        axes[0, 1].set_xlabel('Generation')
        axes[0, 1].set_ylabel('Population Diversity')
        axes[0, 1].set_title('Diversity Maintenance')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)

        # 3. 偏置权重变化
        adaptation_history = last_run['adaptation_history']
        if adaptation_history:
            generations = [a['generation'] for a in adaptation_history]
            bias_weights_history = {}

            # 收集所有偏置的权重历史
            for bias_name in self.adaptive_manager.biases.keys():
                weights = [a['bias_weights'].get(bias_name, 0) for a in adaptation_history]
                bias_weights_history[bias_name] = weights

            for bias_name, weights in bias_weights_history.items():
                axes[1, 0].plot(generations, weights, label=bias_name)

            axes[1, 0].set_xlabel('Generation')
            axes[1, 0].set_ylabel('Bias Weight')
            axes[1, 0].set_title('Adaptive Bias Weight Evolution')
            axes[1, 0].legend()
            axes[1, 0].grid(True, alpha=0.3)

        # 4. 收敛分析
        if len(self.optimization_history) > 1:
            # 多次运行的对比
            for i, run in enumerate(self.optimization_history):
                fitness = run['fitness_history']
                axes[1, 1].plot(fitness, label=f'Run {i+1}', alpha=0.7)

            axes[1, 1].set_xlabel('Generation')
            axes[1, 1].set_ylabel('Best Fitness')
            axes[1, 1].set_title('Multiple Run Comparison')
            axes[1, 1].legend()
            axes[1, 1].grid(True, alpha=0.3)
        else:
            # 单次运行的详细分析
            improvements = []
            for i in range(1, len(fitness_history)):
                improvement = (fitness_history[i-1] - fitness_history[i]) / abs(fitness_history[i-1]) * 100
                improvements.append(improvement)

            axes[1, 1].plot(improvements)
            axes[1, 1].set_xlabel('Generation')
            axes[1, 1].set_ylabel('Improvement Rate (%)')
            axes[1, 1].set_title('Fitness Improvement Rate')
            axes[1, 1].grid(True, alpha=0.3)

        plt.tight_layout()
        plt.show()

    def generate_comprehensive_report(self):
        """生成综合报告"""
        if not self.optimization_history:
            logger.warning("No optimization data for report generation")
            return {}

        report = {
            'system_summary': {
                'total_optimizations': len(self.optimization_history),
                'available_algorithmic_biases': len(self.adaptive_manager.biases),
                'available_domain_biases': len(self.bias_manager.domain_manager.biases),
                'meta_learning_trained': self.meta_selector._models_trained()
            },
            'optimization_performance': {},
            'bias_effectiveness': {},
            'recommendations': []
        }

        # 优化性能统计
        if self.optimization_history:
            fitnesses = [run['final_best_fitness'] for run in self.optimization_history]
            times = [run['computation_time'] for run in self.optimization_history]
            generations = [run['generations_to_convergence'] for run in self.optimization_history]

            report['optimization_performance'] = {
                'average_final_fitness': np.mean(fitnesses),
                'best_fitness_achieved': min(fitnesses),
                'average_computation_time': np.mean(times),
                'average_generations_to_convergence': np.mean(generations)
            }

        # 生成建议
        report['recommendations'] = [
            "Consider adding more diverse algorithmic biases for complex problems",
            "Implement more sophisticated feature extraction for better meta-learning",
            "Consider parallel evaluation for faster optimization",
            "Add more historical data to improve meta-learning accuracy"
        ]

        return report


def main():
    """主演示函数"""
    print("=== 智能偏置系统演示 ===\n")

    # 创建智能偏置系统
    bias_system = IntelligentBiasSystem()

    # 创建测试问题
    print("1. 创建测试问题")
    problem = SyntheticTestProblem(
        dimension=30,
        num_objectives=1,
        problem_type='continuous'
    )
    print(f"   - 问题维度: {problem.dimension}")
    print(f"   - 目标数量: {problem.num_objectives}")
    print(f"   - 问题类型: 连续优化\n")

    # 进行多次优化以收集数据
    print("2. 进行智能偏置优化")
    for run in range(3):
        print(f"\n--- 运行 {run + 1}/3 ---")
        best_fitness, best_solution = bias_system.optimize_with_intelligent_bias(
            problem, max_generations=100, population_size=30)
        print(f"   最佳适应度: {best_fitness:.6f}")

    # 评估偏置效果
    print("\n3. 评估偏置效果")
    effectiveness_report, bias_metrics = bias_system.evaluate_bias_effectiveness()
    if effectiveness_report:
        print("   偏置效果评估完成")
        print(f"   - 总偏置数: {effectiveness_report['summary']['total_biases']}")
        print(f"   - 显著改进: {effectiveness_report['summary']['significant_improvements']}")

        # 显示建议
        print("\n   改进建议:")
        for rec in effectiveness_report['recommendations'][:3]:
            print(f"   - {rec}")

    # 训练元学习模型
    print("\n4. 训练元学习模型")
    training_results = bias_system.train_meta_learning_model()
    if training_results and 'error' not in training_results:
        print("   元学习模型训练成功")
    else:
        print("   需要更多数据来训练元学习模型")

    # 可视化结果
    print("\n5. 可视化结果")
    bias_system.visualize_results()

    # 生成综合报告
    print("\n6. 生成综合报告")
    comprehensive_report = bias_system.generate_comprehensive_report()

    print("\n=== 系统总结 ===")
    summary = comprehensive_report['system_summary']
    print(f"总优化次数: {summary['total_optimizations']}")
    print(f"可用算法偏置: {summary['available_algorithmic_biases']}")
    print(f"可用业务偏置: {summary['available_domain_biases']}")
    print(f"元学习状态: {'已训练' if summary['meta_learning_trained'] else '未训练'}")

    if 'optimization_performance' in comprehensive_report:
        perf = comprehensive_report['optimization_performance']
        print(f"\n性能统计:")
        print(f"平均最终适应度: {perf['average_final_fitness']:.6f}")
        print(f"最佳适应度: {perf['best_fitness_achieved']:.6f}")
        print(f"平均计算时间: {perf['average_computation_time']:.2f}秒")

    print("\n=== 演示完成 ===")


if __name__ == "__main__":
    main()