"""Bias 模块使用示例

演示如何使用 BiasModule 来引导优化过程
"""
import numpy as np
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.base import BlackBoxProblem
from core.solver import BlackBoxSolverNSGAII
from bias import BiasModule, create_standard_bias


# ==================== 示例 1: 基础使用 ====================
def example_basic():
    """基础示例：使用标准 bias 配置"""
    print("=" * 60)
    print("示例 1: 基础使用 - 标准 bias 配置")
    print("=" * 60)

    # 定义问题
    class SphereProblem(BlackBoxProblem):
        def __init__(self):
            super().__init__(name="Sphere", dimension=2, bounds={'x0': (-5, 5), 'x1': (-5, 5)})

        def evaluate(self, x):
            return np.sum(x**2)

    problem = SphereProblem()

    # 创建求解器
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 40
    solver.max_generations = 50
    solver.enable_progress_log = True
    solver.report_interval = 10

    # 启用 bias 模块（使用标准配置）
    solver.enable_bias = True
    solver.bias_module = create_standard_bias(problem, reward_weight=0.05, penalty_weight=1.0)

    # 运行优化
    result = solver.run()

    print(f"\n最优解: {result['pareto_solutions']['individuals'][0]}")
    print(f"最优值: {result['pareto_solutions']['objectives'][0]}")


# ==================== 示例 2: 自定义奖励函数 ====================
def example_custom_reward():
    """自定义奖励函数示例"""
    print("\n" + "=" * 60)
    print("示例 2: 自定义奖励函数")
    print("=" * 60)

    # 定义问题（Rosenbrock 函数）
    class RosenbrockProblem(BlackBoxProblem):
        def __init__(self):
            super().__init__(name="Rosenbrock", dimension=2, bounds={'x0': (-2, 2), 'x1': (-2, 2)})

        def evaluate(self, x):
            return np.sum(100 * (x[1:] - x[:-1]**2)**2 + (1 - x[:-1])**2)

    problem = RosenbrockProblem()

    # 创建 bias 模块
    bias = BiasModule()

    # 添加自定义奖励：奖励接近 (1, 1) 的解
    def proximity_to_optimum(x):
        target = np.array([1.0, 1.0])
        distance = np.linalg.norm(x - target)
        return np.exp(-distance)  # 距离越近奖励越大

    bias.add_reward(proximity_to_optimum, weight=0.1, name="proximity_to_optimum")

    # 创建求解器
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 40
    solver.max_generations = 50
    solver.enable_bias = True
    solver.bias_module = bias
    solver.enable_progress_log = True
    solver.report_interval = 10

    # 运行优化
    result = solver.run()

    print(f"\n最优解: {result['pareto_solutions']['individuals'][0]}")
    print(f"最优值: {result['pareto_solutions']['objectives'][0]}")
    print(f"理论最优: [1.0, 1.0], 值: 0.0")


# ==================== 示例 3: 约束优化 ====================
def example_constrained():
    """约束优化示例"""
    print("\n" + "=" * 60)
    print("示例 3: 约束优化")
    print("=" * 60)

    # 定义问题：最小化 x^2 + y^2，约束 x + y >= 1
    class ConstrainedProblem(BlackBoxProblem):
        def __init__(self):
            super().__init__(name="Constrained", dimension=2, bounds={'x0': (-2, 2), 'x1': (-2, 2)})

        def evaluate(self, x):
            return x[0]**2 + x[1]**2

        def evaluate_constraints(self, x):
            # g(x) <= 0 为可行
            return np.array([1 - x[0] - x[1]])  # x + y >= 1 => 1 - x - y <= 0

    problem = ConstrainedProblem()

    # 使用标准 bias（包含约束罚函数）
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 40
    solver.max_generations = 50
    solver.enable_bias = True
    solver.bias_module = create_standard_bias(problem, reward_weight=0.05, penalty_weight=5.0)
    solver.enable_progress_log = True
    solver.report_interval = 10

    # 运行优化
    result = solver.run()

    best_x = result['pareto_solutions']['individuals'][0]
    best_f = result['pareto_solutions']['objectives'][0]

    print(f"\n最优解: {best_x}")
    print(f"最优值: {best_f}")
    print(f"约束检查: x + y = {best_x[0] + best_x[1]:.4f} (应 >= 1)")
    print(f"理论最优: [0.5, 0.5], 值: 0.5")


# ==================== 示例 4: 多目标优化 ====================
def example_multiobjective():
    """多目标优化示例"""
    print("\n" + "=" * 60)
    print("示例 4: 多目标优化")
    print("=" * 60)

    # ZDT1 问题
    class ZDT1Problem(BlackBoxProblem):
        def __init__(self):
            super().__init__(name="ZDT1", dimension=5, bounds={f'x{i}': (0, 1) for i in range(5)})

        def evaluate(self, x):
            f1 = x[0]
            g = 1 + 9 * np.sum(x[1:]) / (len(x) - 1)
            f2 = g * (1 - np.sqrt(f1 / g))
            return np.array([f1, f2])

        def get_num_objectives(self):
            return 2

    problem = ZDT1Problem()

    # 创建求解器
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 60
    solver.max_generations = 100
    solver.enable_bias = True
    solver.bias_module = create_standard_bias(problem, reward_weight=0.03, penalty_weight=1.0)
    solver.enable_progress_log = True
    solver.report_interval = 20

    # 运行优化
    result = solver.run()

    print(f"\n找到 {len(result['pareto_solutions']['individuals'])} 个 Pareto 解")
    print("前 3 个解:")
    for i in range(min(3, len(result['pareto_solutions']['individuals']))):
        print(f"  解 {i+1}: 目标 = {result['pareto_solutions']['objectives'][i]}")


# ==================== 示例 5: 与 VNS 结合 ====================
def example_vns_with_bias():
    """VNS + Bias 示例"""
    print("\n" + "=" * 60)
    print("示例 5: VNS + Bias")
    print("=" * 60)

    from .solvers.vns import BlackBoxSolverVNS

    # 定义问题
    class RastriginProblem(BlackBoxProblem):
        def __init__(self):
            super().__init__(name="Rastrigin", dimension=2, bounds={'x0': (-5, 5), 'x1': (-5, 5)})

        def evaluate(self, x):
            return 20 + np.sum(x**2 - 10 * np.cos(2 * np.pi * x))

    problem = RastriginProblem()

    # 创建 bias 模块
    bias = BiasModule()

    # 添加奖励：接近原点
    def proximity_to_origin(x):
        distance = np.linalg.norm(x)
        return np.exp(-distance)

    bias.add_reward(proximity_to_origin, weight=0.1, name="proximity_to_origin")

    # 创建 VNS 求解器
    solver = BlackBoxSolverVNS(problem)
    solver.max_iterations = 100
    solver.enable_bias = True
    solver.bias_module = bias

    # 运行优化
    result = solver.run()

    print(f"\n最优解: {result['best_x']}")
    print(f"最优值: {result['best_f']}")
    print(f"评估次数: {result['evaluations']}")
    print(f"理论最优: [0.0, 0.0], 值: 0.0")


# ==================== 主函数 ====================
if __name__ == "__main__":
    # 运行所有示例
    example_basic()
    example_custom_reward()
    example_constrained()
    example_multiobjective()
    example_vns_with_bias()

    print("\n" + "=" * 60)
    print("所有示例运行完成！")
    print("=" * 60)
