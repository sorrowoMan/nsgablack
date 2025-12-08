"""
最简单的偏置优化示例
直接使用NSGA2求解器，避免可视化问题
"""

import numpy as np
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.base import BlackBoxProblem
from solvers.nsga2 import BlackBoxSolverNSGAII
from bias import (
    AlgorithmicBiasManager,
    DiversityBias,
    ConvergenceBias,
    GradientDescentBias,
    OptimizationContext
)


class SimpleRosenbrock(BlackBoxProblem):
    """简化的Rosenbrock函数"""

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


def demo_basic_bias():
    """演示基本的偏置使用"""
    print("=" * 60)
    print("基础偏置优化示例：Rosenbrock函数")
    print("=" * 60)

    # 创建问题
    problem = SimpleRosenbrock(dimension=2)

    # 无偏置优化
    print("\n1. 无偏置优化：")
    solver1 = BlackBoxSolverNSGAII(problem)
    solver1.pop_size = 50
    solver1.max_generations = 100
    # 禁用日志以减少输出
    solver1.enable_progress_log = False

    result1 = solver1.run()
    best1 = result1['pareto_solutions']['individuals'][0]
    obj1 = result1['pareto_solutions']['objectives'][0][0]

    print(f"   最优解: [{best1[0]:.4f}, {best1[1]:.4f}]")
    print(f"   最优值: {obj1:.6f}")
    print(f"   理论最优: [1.0, 1.0], 0.0")

    # 有偏置优化
    print("\n2. 有偏置优化：")

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

        # 创建优化上下文
        context = OptimizationContext(
            generation=getattr(solver2, 'generation', 0),
            individual=x,
            population=getattr(solver2, 'population', []),
        )

        # 应用偏置
        total_bias = 0
        for bias in bias_manager.biases:
            total_bias += bias.apply(x, original_evaluate, context)

        return base_value + total_bias

    problem.evaluate = biased_evaluate

    solver2 = BlackBoxSolverNSGAII(problem)
    solver2.pop_size = 50
    solver2.max_generations = 100
    solver2.enable_progress_log = False

    result2 = solver2.run()
    best2 = result2['pareto_solutions']['individuals'][0]
    obj2 = result2['pareto_solutions']['objectives'][0][0]

    print(f"   最优解: [{best2[0]:.4f}, {best2[1]:.4f}]")
    print(f"   最优值: {obj2:.6f}")

    # 比较
    improvement1 = abs(1.0 - best1[0])
    improvement2 = abs(1.0 - best2[0])

    print("\n3. 结果比较：")
    print(f"   无偏置误差: {improvement1:.6f}")
    print(f"   有偏置误差: {improvement2:.6f}")

    if improvement2 < improvement1:
        print("   ✓ 偏置系统改善了结果！")
    else:
        print("   - 需要调整偏置参数")

    # 恢复原始评估函数
    problem.evaluate = original_evaluate

    return result1, result2


def demo_higher_dimension():
    """演示高维优化"""
    print("\n" + "=" * 60)
    print("高维优化示例：10维Rosenbrock函数")
    print("=" * 60)

    # 创建高维问题
    problem = SimpleRosenbrock(dimension=10)

    # 创建偏置管理器
    bias_manager = AlgorithmicBiasManager()

    # 多种偏置组合
    bias_manager.add_bias(
        DiversityBias(
            weight=0.2,
            metric='euclidean'
        )
    )

    bias_manager.add_bias(
        ConvergenceBias(
            weight=0.1,
            early_gen=30,
            late_gen=70
        )
    )

    # 包装评估函数
    original_evaluate = problem.evaluate

    def biased_evaluate(x):
        base_value = original_evaluate(x)

        context = OptimizationContext(
            generation=getattr(solver, 'generation', 0),
            individual=x,
            population=getattr(solver, 'population', []),
        )

        total_bias = 0
        for bias in bias_manager.biases:
            total_bias += bias.apply(x, original_evaluate, context)

        return base_value + total_bias

    problem.evaluate = biased_evaluate

    # 创建求解器
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 100
    solver.max_generations = 200
    solver.enable_progress_log = False
    solver.report_interval = 50

    # 运行优化
    print("\n开始优化...")
    result = solver.run()

    # 分析结果
    best_solution = result['pareto_solutions']['individuals'][0]
    best_value = result['pareto_solutions']['objectives'][0][0]

    # 计算误差
    error = np.linalg.norm(best_solution - np.ones(10))

    print(f"\n优化结果：")
    print(f"  最优值: {best_value:.6f}")
    print(f"  最优解前5维: {best_solution[:5]}")
    print(f"  与理论最优的欧氏距离: {error:.6f}")

    # 恢复原始评估函数
    problem.evaluate = original_evaluate

    return result


def demo_constrained_optimization():
    """演示约束优化"""
    print("\n" + "=" * 60)
    print("约束优化示例")
    print("=" * 60)

    class ConstrainedProblem(BlackBoxProblem):
        """带约束的优化问题"""

        def __init__(self):
            super().__init__(
                name="ConstrainedProblem",
                dimension=2,
                bounds=[(-5, 5), (-5, 5)]
            )

        def evaluate(self, x):
            """目标函数"""
            return x[0]**2 + x[1]**2  # 最小化x² + y²

        def evaluate_constraints(self, x):
            """约束: x + y >= 1"""
            return np.array([1 - x[0] - x[1]])

    # 创建问题
    problem = ConstrainedProblem()

    # 创建偏置管理器
    bias_manager = AlgorithmicBiasManager()

    # 添加偏置引导向可行域
    bias_manager.add_bias(
        DiversityBias(
            weight=0.15,
            metric='euclidean'
        )
    )

    # 包装评估函数
    original_evaluate = problem.evaluate
    original_constraints = problem.evaluate_constraints

    def biased_evaluate(x):
        base_value = original_evaluate(x)

        # 添加惩罚项处理约束
        constraints = original_constraints(x)
        penalty = 1000 * np.sum(np.maximum(0, constraints)**2)

        context = OptimizationContext(
            generation=getattr(solver, 'generation', 0),
            individual=x,
            is_violating_constraints=np.any(constraints > 0)
        )

        total_bias = 0
        for bias in bias_manager.biases:
            total_bias += bias.apply(x, original_evaluate, context)

        return base_value + penalty + total_bias

    problem.evaluate = biased_evaluate

    # 创建求解器
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 50
    solver.max_generations = 100
    solver.enable_progress_log = False

    # 运行优化
    print("\n开始优化...")
    result = solver.run()

    # 分析结果
    best_solution = result['pareto_solutions']['individuals'][0]
    best_value = result['pareto_solutions']['objectives'][0][0]
    constraints = original_constraints(best_solution)

    print(f"\n优化结果：")
    print(f"  最优解: [{best_solution[0]:.4f}, {best_solution[1]:.4f}]")
    print(f"  目标值: {best_value:.6f}")
    print(f"  约束值: {constraints[0]:.6f}")
    print(f"  约束满足: {'✓' if constraints[0] <= 0 else '✗'}")

    # 恢复原始评估函数
    problem.evaluate = original_evaluate

    return result


if __name__ == "__main__":
    print("偏置优化系统演示（简化版）")

    # 运行演示
    demo_basic_bias()
    demo_higher_dimension()
    demo_constrained_optimization()

    print("\n" + "=" * 60)
    print("演示完成！")
    print("\n偏置系统总结：")
    print("✓ 可以引导搜索方向")
    print("✓ 提高解的质量")
    print("✓ 适应不同问题特性")
    print("✓ 易于组合和配置")
    print("=" * 60)