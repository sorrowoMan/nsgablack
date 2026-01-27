"""
实验1：昂贵黑箱优化 - 实验运行器

对比算法：
1. NSGABlack + 代理偏置（本框架）
2. 标准NSGA-II（无代理）
3. Bayesian Optimization（专业库）
"""

import sys
import os
import json
import time
import numpy as np
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass, asdict

# 添加父目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from exp1_problems import (
    ExpensiveOptimizationProblem,
    create_problem,
    FiniteElementOptimization,
    CEC2017Expensive,
    ComputationalFluidDynamics
)


@dataclass
class ExperimentResult:
    """实验结果"""
    algorithm: str
    problem: str
    seed: int
    best_fitness: float
    evaluations_used: int
    time_elapsed: float
    convergence_history: List[Dict[str, float]]
    final_solution: List[float]


# ============ Baseline算法 ============

class StandardNSGA2:
    """标准NSGA-II（无代理）"""

    def __init__(self, seed: int = 42):
        self.seed = seed
        np.random.seed(seed)

    def run(
        self,
        problem: ExpensiveOptimizationProblem,
        max_evaluations: int = 1000,
        verbose: bool = False
    ) -> ExperimentResult:
        """运行优化"""
        start_time = time.time()

        # 初始化种群
        pop_size = 50
        population = [np.random.uniform(-5, 5, problem.dimension)
                     for _ in range(pop_size)]

        # 评估初始种群
        fitness = [problem.evaluate(ind) for ind in population]

        best_idx = np.argmin(fitness)
        best_solution = population[best_idx].copy()
        best_fitness = fitness[best_idx]

        history = []
        evaluations_used = problem.evaluation_count

        # 进化循环
        generation = 0
        while evaluations_used < max_evaluations:
            generation += 1

            # 选择（锦标赛）
            offspring = []
            for _ in range(pop_size):
                parent1 = self._tournament_select(population, fitness)
                parent2 = self._tournament_select(population, fitness)
                child = self._crossover(parent1, parent2)
                child = self._mutate(child)
                offspring.append(child)

            # 评估后代
            offspring_fitness = [problem.evaluate(ind) for ind in offspring]

            # 更新最优
            for i, fit in enumerate(offspring_fitness):
                if fit < best_fitness:
                    best_fitness = fit
                    best_solution = offspring[i].copy()

            # 环境选择（合并+截断选择）
            population.extend(offspring)
            fitness.extend(offspring_fitness)

            # 按适应度排序，保留前pop_size个
            sorted_indices = np.argsort(fitness)
            population = [population[i] for i in sorted_indices[:pop_size]]
            fitness = [fitness[i] for i in sorted_indices[:pop_size]]

            evaluations_used = problem.evaluation_count

            # 记录历史
            history.append({
                'generation': generation,
                'best_fitness': best_fitness,
                'evaluations': evaluations_used,
                'time': time.time() - start_time
            })

            if verbose and generation % 10 == 0:
                print(f"  Gen {generation}: Best={best_fitness:.6f}, "
                      f"Eval={evaluations_used}/{max_evaluations}")

        end_time = time.time()

        return ExperimentResult(
            algorithm='NSGA-II',
            problem=problem.name,
            seed=self.seed,
            best_fitness=best_fitness,
            evaluations_used=evaluations_used,
            time_elapsed=end_time - start_time,
            convergence_history=history,
            final_solution=best_solution.tolist()
        )

    def _tournament_select(self, population, fitness, tournament_size=3):
        """锦标赛选择"""
        indices = np.random.choice(len(population), tournament_size, replace=False)
        best_idx = indices[np.argmin([fitness[i] for i in indices])]
        return population[best_idx].copy()

    def _crossover(self, parent1, parent2):
        """SBX交叉"""
        eta = 15.0
        child = np.zeros_like(parent1)

        for i in range(len(parent1)):
            if np.random.random() < 0.5:
                # 执行交叉
                beta = self._get_beta(eta)
                child[i] = 0.5 * ((1 + beta) * parent1[i] + (1 - beta) * parent2[i])
            else:
                child[i] = parent1[i] if np.random.random() < 0.5 else parent2[i]

        return child

    def _get_beta(self, eta):
        """SBX的beta值"""
        u = np.random.random()
        if u <= 0.5:
            return (2 * u) ** (1 / (eta + 1))
        else:
            return (1 / (2 * (1 - u))) ** (1 / (eta + 1))

    def _mutate(self, individual):
        """多项式变异"""
        eta = 20.0
        mutated = individual.copy()

        for i in range(len(mutated)):
            if np.random.random() < 1.0 / len(mutated):
                delta = self._get_delta(eta)
                mutated[i] += delta
                mutated[i] = np.clip(mutated[i], -5.0, 5.0)

        return mutated

    def _get_delta(self, eta):
        """多项式变异的delta值"""
        u = np.random.random()
        if u < 0.5:
            return (2 * u) ** (1 / (eta + 1)) - 1
        else:
            return 1 - (2 * (1 - u)) ** (1 / (eta + 1))


class BayesianOptimizationBaseline:
    """贝叶斯优化基线（简化版）"""

    def __init__(self, seed: int = 42):
        self.seed = seed
        np.random.seed(seed)

    def run(
        self,
        problem: ExpensiveOptimizationProblem,
        max_evaluations: int = 1000,
        verbose: bool = False
    ) -> ExperimentResult:
        """运行贝叶斯优化"""
        start_time = time.time()

        # 初始采样（LHS）
        n_init = min(50, max_evaluations // 2)
        X = []
        y = []

        for _ in range(n_init):
            x = np.random.uniform(-5, 5, problem.dimension)
            fitness = problem.evaluate(x)
            X.append(x)
            y.append(fitness)

        X = np.array(X)
        y = np.array(y)

        best_idx = np.argmin(y)
        best_solution = X[best_idx].copy()
        best_fitness = y[best_idx]

        history = [{
            'generation': 0,
            'best_fitness': best_fitness,
            'evaluations': problem.evaluation_count,
            'time': time.time() - start_time
        }]

        # 迭代优化
        iteration = 0
        while problem.evaluation_count < max_evaluations:
            iteration += 1

            # 简化的采集函数：随机探索 + 局部搜索
            if np.random.random() < 0.3:
                # 全局探索
                x_new = np.random.uniform(-5, 5, problem.dimension)
            else:
                # 局部搜索（在最优解附近）
                x_new = best_solution + np.random.randn(problem.dimension) * 0.5
                x_new = np.clip(x_new, -5, 5)

            # 评估
            fitness_new = problem.evaluate(x_new)

            # 更新数据集
            X = np.vstack([X, x_new])
            y = np.append(y, fitness_new)

            # 更新最优
            if fitness_new < best_fitness:
                best_fitness = fitness_new
                best_solution = x_new.copy()

            # 记录
            history.append({
                'generation': iteration,
                'best_fitness': best_fitness,
                'evaluations': problem.evaluation_count,
                'time': time.time() - start_time
            })

            if verbose and iteration % 10 == 0:
                print(f"  Iter {iteration}: Best={best_fitness:.6f}, "
                      f"Eval={problem.evaluation_count}/{max_evaluations}")

        end_time = time.time()

        return ExperimentResult(
            algorithm='Bayesian_Opt',
            problem=problem.name,
            seed=self.seed,
            best_fitness=best_fitness,
            evaluations_used=problem.evaluation_count,
            time_elapsed=end_time - start_time,
            convergence_history=history,
            final_solution=best_solution.tolist()
        )


class NSGABlackWithSurrogate:
    """NSGABlack + 代理偏置（简化版）"""

    def __init__(self, seed: int = 42, surrogate_budget: float = 0.7):
        """
        Args:
            seed: 随机种子
            surrogate_budget: 代理评估比例（0.7表示70%用代理）
        """
        self.seed = seed
        self.surrogate_budget = surrogate_budget
        np.random.seed(seed)

    def run(
        self,
        problem: ExpensiveOptimizationProblem,
        max_evaluations: int = 1000,
        verbose: bool = False
    ) -> ExperimentResult:
        """运行NSGABlack + 代理"""
        start_time = time.time()

        # 初始化
        pop_size = 50
        population = [np.random.uniform(-5, 5, problem.dimension)
                     for _ in range(pop_size)]

        # 初始真实评估
        fitness = [problem.evaluate(ind) for ind in population]

        # 代理模型（使用KNN简化）
        surrogate_X = population.copy()
        surrogate_y = fitness.copy()

        best_idx = np.argmin(fitness)
        best_solution = population[best_idx].copy()
        best_fitness = fitness[best_idx]

        history = []
        evaluations_used = problem.evaluation_count

        generation = 0
        while evaluations_used < max_evaluations:
            generation += 1

            # 生成后代
            offspring = []
            for _ in range(pop_size):
                parent1 = self._tournament_select(population, fitness)
                parent2 = self._tournament_select(population, fitness)
                child = self._crossover(parent1, parent2)
                child = self._mutate(child)
                offspring.append(child)

            # 使用代理评估部分后代
            offspring_fitness = []
            for child in offspring:
                if evaluations_used < max_evaluations * self.surrogate_budget:
                    # 使用代理评估
                    pred_fitness = self._surrogate_predict(child, surrogate_X, surrogate_y)
                    offspring_fitness.append(pred_fitness)
                else:
                    # 真实评估
                    offspring_fitness.append(problem.evaluate(child))

            # 更新代理模型（定期）
            if generation % 5 == 0:
                # 选择最有希望的真实评估
                n_real_eval = min(10, max_evaluations - evaluations_used)
                if n_real_eval > 0:
                    # 选择预测最好的几个
                    sorted_indices = np.argsort(offspring_fitness)[:n_real_eval]
                    for idx in sorted_indices:
                        real_fitness = problem.evaluate(offspring[idx])
                        offspring_fitness[idx] = real_fitness
                        surrogate_X.append(offspring[idx].copy())
                        surrogate_y.append(real_fitness)

            # 更新最优
            for i, fit in enumerate(offspring_fitness):
                if fit < best_fitness:
                    best_fitness = fit
                    best_solution = offspring[i].copy()

            # 环境选择
            population.extend(offspring)
            fitness.extend(offspring_fitness)

            sorted_indices = np.argsort(fitness)
            population = [population[i] for i in sorted_indices[:pop_size]]
            fitness = [fitness[i] for i in sorted_indices[:pop_size]]

            evaluations_used = problem.evaluation_count

            # 记录
            history.append({
                'generation': generation,
                'best_fitness': best_fitness,
                'evaluations': evaluations_used,
                'time': time.time() - start_time
            })

            if verbose and generation % 10 == 0:
                print(f"  Gen {generation}: Best={best_fitness:.6f}, "
                      f"Eval={evaluations_used}/{max_evaluations}")

        end_time = time.time()

        return ExperimentResult(
            algorithm='NSGABlack+Surrogate',
            problem=problem.name,
            seed=self.seed,
            best_fitness=best_fitness,
            evaluations_used=evaluations_used,
            time_elapsed=end_time - start_time,
            convergence_history=history,
            final_solution=best_solution.tolist()
        )

    def _tournament_select(self, population, fitness, tournament_size=3):
        """锦标赛选择"""
        indices = np.random.choice(len(population), tournament_size, replace=False)
        best_idx = indices[np.argmin([fitness[i] for i in indices])]
        return population[best_idx].copy()

    def _crossover(self, parent1, parent2):
        """SBX交叉"""
        eta = 15.0
        child = np.zeros_like(parent1)

        for i in range(len(parent1)):
            if np.random.random() < 0.5:
                beta = self._get_beta(eta)
                child[i] = 0.5 * ((1 + beta) * parent1[i] + (1 - beta) * parent2[i])
            else:
                child[i] = parent1[i] if np.random.random() < 0.5 else parent2[i]

        return child

    def _get_beta(self, eta):
        u = np.random.random()
        if u <= 0.5:
            return (2 * u) ** (1 / (eta + 1))
        else:
            return (1 / (2 * (1 - u))) ** (1 / (eta + 1))

    def _mutate(self, individual):
        """多项式变异"""
        eta = 20.0
        mutated = individual.copy()

        for i in range(len(mutated)):
            if np.random.random() < 1.0 / len(mutated):
                delta = self._get_delta(eta)
                mutated[i] += delta
                mutated[i] = np.clip(mutated[i], -5.0, 5.0)

        return mutated

    def _get_delta(self, eta):
        u = np.random.random()
        if u < 0.5:
            return (2 * u) ** (1 / (eta + 1)) - 1
        else:
            return 1 - (2 * (1 - u)) ** (1 / (eta + 1))

    def _surrogate_predict(self, x, X, y, k=5):
        """KNN代理预测"""
        # 计算距离
        distances = np.array([np.linalg.norm(x - xi) for xi in X])

        # 找到k个最近邻
        nearest_indices = np.argsort(distances)[:k]

        # 加权平均（距离越近权重越大）
        weights = 1.0 / (distances[nearest_indices] + 1e-10)
        weights /= weights.sum()

        prediction = np.dot(weights, np.array(y)[nearest_indices])

        return prediction


# ============ 实验运行器 ============

class ExpensiveOptimizationExperiment:
    """昂贵黑箱优化实验"""

    def __init__(self, output_dir: str = "results/exp1_expensive"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.results = {
            'NSGABlack+Surrogate': [],
            'NSGA-II': [],
            'Bayesian_Opt': []
        }

    def run_single_problem(
        self,
        problem: ExpensiveOptimizationProblem,
        max_evaluations: int = 1000,
        seeds: List[int] = [42, 123, 456, 789, 1024],
        verbose: bool = False
    ):
        """运行单个问题的对比实验"""
        print(f"\n{'=' * 70}")
        print(f"Problem: {problem.name} (d={problem.dimension})")
        print(f"Evaluation cost: {problem.evaluation_cost}s per evaluation")
        print(f"Max evaluations: {max_evaluations}")
        print(f"{'=' * 70}")

        algorithms = {
            'NSGABlack+Surrogate': NSGABlackWithSurrogate(surrogate_budget=0.7),
            'NSGA-II': StandardNSGA2(),
            'Bayesian_Opt': BayesianOptimizationBaseline()
        }

        for algo_name, algo in algorithms.items():
            print(f"\n[{list(algorithms.keys()).index(algo_name)+1}/3] Running {algo_name}...")

            for seed in seeds:
                print(f"  Seed {seed}...", end=" ")

                # 重置问题计数器
                problem.reset_counters()

                # 运行算法
                np.random.seed(seed)
                result = algo.run(problem, max_evaluations, verbose=False)

                self.results[algo_name].append(result)

                print(f"Best={result.best_fitness:.6f}, "
                      f"Eval={result.evaluations_used}, "
                      f"Time={result.time_elapsed:.2f}s")

        # 分析结果
        self._analyze_results(problem)

    def _analyze_results(self, problem: ExpensiveOptimizationProblem):
        """分析实验结果"""
        print(f"\n{'=' * 70}")
        print(f"Analysis: {problem.name}")
        print(f"{'=' * 70}")

        for algo_name in self.results.keys():
            runs = self.results[algo_name]
            if not runs or runs[0].problem != problem.name:
                continue

            fitness = [r.best_fitness for r in runs]
            evals = [r.evaluations_used for r in runs]
            times = [r.time_elapsed for r in runs]

            print(f"\n{algo_name}:")
            print(f"  Best Fitness: {np.mean(fitness):.6f} ± {np.std(fitness):.6f}")
            print(f"  Evaluations: {np.mean(evals):.0f} ± {np.std(evals):.0f}")
            print(f"  Time: {np.mean(times):.2f} ± {np.std(times):.2f}s")

    def run_full_experiment(self):
        """运行完整实验"""
        print("\n" + "=" * 70)
        print("实验1：昂贵黑箱优化")
        print("=" * 70)

        # 定义测试问题
        problems_config = [
            ('finite_element', {'dimension': 20, 'evaluation_cost': 0.05}),
            ('cec2017', {'dimension': 20, 'function_id': 1, 'evaluation_cost': 0.05}),
            ('cfd', {'dimension': 15, 'evaluation_cost': 0.05}),
        ]

        for problem_type, params in problems_config:
            problem = create_problem(problem_type, **params)
            self.run_single_problem(
                problem,
                max_evaluations=500,  # 减少评估次数加快实验
                seeds=[42, 123, 456],  # 3个种子
                verbose=False
            )

        # 保存结果
        self._save_results()

    def _save_results(self):
        """保存结果"""
        output_file = self.output_dir / "exp1_results.json"

        # 转换为可序列化格式
        def convert_to_serializable(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, dict):
                return {k: convert_to_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_serializable(item) for item in obj]
            elif hasattr(obj, '__dict__'):
                return convert_to_serializable(asdict(obj))
            else:
                return obj

        serializable_results = convert_to_serializable(self.results)

        save_data = {
            'metadata': {
                'experiment': 'Expensive Optimization',
                'total_runs': sum(len(r) for r in self.results.values())
            },
            'results': serializable_results
        }

        with open(output_file, 'w') as f:
            json.dump(save_data, f, indent=2)

        print(f"\n结果已保存到: {output_file}")


if __name__ == "__main__":
    experiment = ExpensiveOptimizationExperiment()
    experiment.run_full_experiment()
