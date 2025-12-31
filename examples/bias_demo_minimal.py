"""
最小化偏置演示 - 完全无可视化
"""

import numpy as np
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 直接导入必要组件，避免可视化
from core.base import BlackBoxProblem
from bias import (
    AlgorithmicBiasManager,
    DiversityBias,
    ConvergenceBias,
    GradientDescentBias,
    OptimizationContext
)


# 简单的NSGA-II实现（无可视化）
class SimpleNSGAII:
    def __init__(self, problem, pop_size=50, max_generations=100):
        self.problem = problem
        self.pop_size = pop_size
        self.max_generations = max_generations
        self.generation = 0
        self.population = None
        self.fitness = None

    def initialize_population(self):
        """初始化种群"""
        population = []
        for _ in range(self.pop_size):
            individual = []
            for i in range(self.problem.dimension):
                low, high = self.problem.bounds[i]
                individual.append(np.random.uniform(low, high))
            population.append(np.array(individual))
        return population

    def evaluate_population(self, population):
        """评估种群"""
        fitness = []
        for ind in population:
            f = self.problem.evaluate(ind)
            fitness.append(f)
        return np.array(fitness)

    def tournament_selection(self, population, fitness, k=2):
        """锦标赛选择"""
        selected = []
        for _ in range(len(population)):
            candidates = np.random.choice(len(population), k, replace=False)
            winner = candidates[np.argmin(fitness[candidates])]
            selected.append(population[winner].copy())
        return selected

    def sbx_crossover(self, parent1, parent2, eta=20):
        """模拟二进制交叉"""
        child1, child2 = parent1.copy(), parent2.copy()
        if np.random.random() < 0.9:  # 交叉概率
            for i in range(len(parent1)):
                if np.random.random() < 0.5:
                    u = np.random.random()
                    if u <= 0.5:
                        beta = (2 * u) ** (1 / (eta + 1))
                    else:
                        beta = (1 / (2 * (1 - u))) ** (1 / (eta + 1))

                    child1[i] = 0.5 * ((1 + beta) * parent1[i] + (1 - beta) * parent2[i])
                    child2[i] = 0.5 * ((1 - beta) * parent1[i] + (1 + beta) * parent2[i])
        return child1, child2

    def polynomial_mutation(self, individual, eta=20):
        """多项式变异"""
        mutated = individual.copy()
        for i in range(len(individual)):
            if np.random.random() < 0.1:  # 变异概率
                u = np.random.random()
                if u < 0.5:
                    delta = (2 * u) ** (1 / (eta + 1)) - 1
                else:
                    delta = 1 - (2 * (1 - u)) ** (1 / (eta + 1))

                low, high = self.problem.bounds[i]
                mutated[i] = np.clip(mutated[i] + delta * (high - low), low, high)
        return mutated

    def run(self):
        """运行优化"""
        # 初始化
        self.population = self.initialize_population()
        self.fitness = self.evaluate_population(self.population)

        # 进化循环
        for gen in range(self.max_generations):
            self.generation = gen

            # 选择
            selected = self.tournament_selection(self.population, self.fitness)

            # 交叉和变异
            offspring = []
            for i in range(0, len(selected), 2):
                if i + 1 < len(selected):
                    child1, child2 = self.sbx_crossover(selected[i], selected[i+1])
                    offspring.append(self.polynomial_mutation(child1))
                    offspring.append(self.polynomial_mutation(child2))

            # 评估后代
            offspring_fitness = self.evaluate_population(offspring)

            # 合并种群
            combined_pop = self.population + offspring
            combined_fit = np.concatenate([self.fitness, offspring_fitness])

            # 选择新一代（精英保留）
            indices = np.argsort(combined_fit)[:self.pop_size]
            self.population = [combined_pop[i] for i in indices]
            self.fitness = combined_fit[indices]

            # 输出进度
            if gen % 20 == 0:
                print(f"  Generation {gen}: Best = {self.fitness[0]:.6f}")

        return {
            'pareto_solutions': {
                'individuals': [self.population[0]],
                'objectives': [[self.fitness[0]]]
            }
        }


# 测试问题
class SimpleRosenbrock(BlackBoxProblem):
    """Rosenbrock函数"""

    def __init__(self, dimension=2):
        bounds = [( -5, 5) for _ in range(dimension)]
        super().__init__(
            name="Rosenbrock",
            dimension=dimension,
            bounds=bounds
        )

    def evaluate(self, x):
        """Rosenbrock函数"""
        total = 0
        for i in range(len(x) - 1):
            total += 100 * (x[i+1] - x[i]**2)**2 + (1 - x[i])**2
        return total


def demo_no_bias():
    """无偏置优化"""
    print("=" * 60)
    print("无偏置优化：纯NSGA-II")
    print("=" * 60)

    problem = SimpleRosenbrock(dimension=2)
    solver = SimpleNSGAII(problem, pop_size=50, max_generations=100)

    result = solver.run()
    best = result['pareto_solutions']['individuals'][0]
    obj = result['pareto_solutions']['objectives'][0][0]

    print(f"\n结果：")
    print(f"  最优解: [{best[0]:.6f}, {best[1]:.6f}]")
    print(f"  最优值: {obj:.6f}")
    print(f"  理论最优: [1.0, 1.0], 0.0")

    return result


def demo_with_bias():
    """有偏置优化"""
    print("\n" + "=" * 60)
    print("有偏置优化：NSGA-II + 偏置系统")
    print("=" * 60)

    problem = SimpleRosenbrock(dimension=2)

    # 创建偏置管理器
    bias_manager = AlgorithmicBiasManager()

    # 添加多样性偏置
    bias_manager.add_bias(
        DiversityBias(
            weight=0.2,
            metric='euclidean'
        )
    )

    # 添加收敛偏置
    bias_manager.add_bias(
        ConvergenceBias(
            weight=0.15,
            early_gen=20,
            late_gen=60
        )
    )

    # 包装评估函数
    original_evaluate = problem.evaluate

    def biased_evaluate(x):
        base_value = original_evaluate(x)

        context = OptimizationContext(
            generation=solver.generation,
            individual=x,
            population=solver.population,
        )

        # 应用偏置
        total_bias = 0
        for bias in bias_manager.biases.values():
            total_bias += bias.compute(x, context)

        return base_value + total_bias

    problem.evaluate = biased_evaluate

    # 运行优化
    solver = SimpleNSGAII(problem, pop_size=50, max_generations=100)
    result = solver.run()

    best = result['pareto_solutions']['individuals'][0]
    obj = result['pareto_solutions']['objectives'][0][0]

    # 计算原始值
    true_obj = original_evaluate(best)

    print(f"\n结果：")
    print(f"  最优解: [{best[0]:.6f}, {best[1]:.6f}]")
    print(f"  偏置值: {obj:.6f}")
    print(f"  真实值: {true_obj:.6f}")

    # 恢复原始评估
    problem.evaluate = original_evaluate

    return result, true_obj


def demo_gradient_descent_bias():
    """演示梯度下降偏置"""
    print("\n" + "=" * 60)
    print("梯度下降偏置示例")
    print("=" * 60)

    problem = SimpleRosenbrock(dimension=2)

    # 创建偏置管理器
    bias_manager = AlgorithmicBiasManager()

    # 添加梯度下降偏置
    bias_manager.add_bias(
        GradientDescentBias(
            weight=0.3,
            learning_rate=0.01,
            momentum=0.9,
            adaptive_lr=True
        )
    )
   
    # 包装评估函数
    original_evaluate = problem.evaluate

    def biased_evaluate(x):
        base_value = original_evaluate(x)

        context = OptimizationContext(
            generation=solver.generation,
            individual=x,
            population=solver.population,
            best_solution=solver.population[0] if solver.population else None
        )

        # 应用偏置
        total_bias = 0
        for bias in bias_manager.biases.values():
            total_bias += bias.compute(x, context)

        return base_value + total_bias

    problem.evaluate = biased_evaluate

    # 运行优化
    solver = SimpleNSGAII(problem, pop_size=50, max_generations=100)
    result = solver.run()

    best = result['pareto_solutions']['individuals'][0]
    obj = result['pareto_solutions']['objectives'][0][0]
    true_obj = original_evaluate(best)

    print(f"\n结果：")
    print(f"  最优解: [{best[0]:.6f}, {best[1]:.6f}]")
    print(f"  真实值: {true_obj:.6f}")

    # 恢复原始评估
    problem.evaluate = original_evaluate

    return result, true_obj


if __name__ == "__main__":
    print("偏置系统最小化演示")
    print("=" * 60)

    # 运行演示
    result1 = demo_no_bias()
    result2, true_obj2 = demo_with_bias()
    result3, true_obj3 = demo_gradient_descent_bias()  # 暂时注释

    # 比较
    print("\n" + "=" * 60)
    print("结果比较")
    print("=" * 60)

    best1 = result1['pareto_solutions']['individuals'][0]
    obj1 = result1['pareto_solutions']['objectives'][0][0]

    error1 = np.linalg.norm(best1 - np.ones(2))
    error2 = np.linalg.norm(result2['pareto_solutions']['individuals'][0] - np.ones(2))
    error3 = np.linalg.norm(result3['pareto_solutions']['individuals'][0] - np.ones(2))

    print(f"\n方法对比：")
    print(f"  无偏置:   误差 = {error1:.6f}")
    print(f"  多样性偏置: 误差 = {error2:.6f}")
    print(f"  梯度偏置:  误差 = {error3:.6f}")

    print("\n* 演示完成！偏置系统成功运行。")