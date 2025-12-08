"""
简单偏置优化示例（无可视化版本）
演示如何使用偏置系统解决实际的优化问题
"""

import numpy as np
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.base import BlackBoxProblem
from core.solver import BlackBoxSolverNSGAII
from bias import (
    AlgorithmicBiasManager,
    DiversityBias,
    ConvergenceBias,
    GradientDescentBias,
    OptimizationContext
)


class EngineeringDesignProblem(BlackBoxProblem):
    """
    工程设计问题示例：设计一个简单的悬臂梁

    目标：最小化材料成本
    约束：最大挠度不能超过限制
    变量：
        - 长度 x[0] (0.5-2.0 m)
        - 宽度 x[1] (0.05-0.3 m)
        - 高度 x[2] (0.05-0.5 m)
    """

    def __init__(self):
        super().__init__(
            name="CantileverBeam",
            dimension=3,
            bounds=[(0.5, 2.0), (0.05, 0.3), (0.05, 0.5)]  # 使用列表形式
        )
        # 材料属性
        self.E = 200e9  # 弹性模量 (Pa)
        self.rho = 7850  # 密度 (kg/m³)
        self.max_deflection = 0.01  # 最大允许挠度 (m)
        self.force = 1000  # 末端载荷 (N)

    def evaluate(self, x):
        """计算目标函数：材料成本"""
        L, W, H = x[0], x[1], x[2]

        # 体积 = 长度 × 宽度 × 高度
        volume = L * W * H
        # 成本与体积成正比
        cost = volume * self.rho * 0.001  # 假设每kg材料0.001元

        return cost

    def evaluate_constraints(self, x):
        """计算约束：挠度限制"""
        L, W, H = x[0], x[1], x[2]

        # 悬臂梁末端挠度公式
        I = (W * H**3) / 12  # 惯性矩
        deflection = (self.force * L**3) / (3 * self.E * I)

        # 约束：挠度 - 最大允许挠度 <= 0
        constraint = deflection - self.max_deflection

        return np.array([constraint])


class PortfolioOptimizationProblem(BlackBoxProblem):
    """
    投资组合优化问题

    目标：最大化收益 - 风险
    变量：5个资产的投资比例
    约束：总权重 = 1，每个资产权重 >= 0
    """

    def __init__(self):
        # 资产预期收益
        self.expected_returns = np.array([0.08, 0.12, 0.15, 0.06, 0.10])
        # 协方差矩阵
        self.covariance = np.array([
            [0.01, 0.002, 0.003, 0.001, 0.002],
            [0.002, 0.04, 0.008, 0.002, 0.004],
            [0.003, 0.008, 0.09, 0.003, 0.006],
            [0.001, 0.002, 0.003, 0.0025, 0.001],
            [0.002, 0.004, 0.006, 0.001, 0.0225]
        ])

        super().__init__(
            name="Portfolio",
            dimension=5,
            bounds=[(0, 1) for _ in range(5)]  # 使用列表形式
        )

    def evaluate(self, x):
        """计算目标函数：负的夏普比率（要最小化）"""
        # 确保权重和为1
        w = x / np.sum(x)

        # 计算组合收益
        portfolio_return = np.dot(w, self.expected_returns)

        # 计算组合风险（方差）
        portfolio_variance = np.dot(w, np.dot(self.covariance, w))
        portfolio_risk = np.sqrt(portfolio_variance)

        # 夏普比率 (假设无风险利率为0.02)
        sharpe_ratio = (portfolio_return - 0.02) / (portfolio_risk + 1e-6)

        # 最小化负的夏普比率
        return -sharpe_ratio

    def evaluate_constraints(self, x):
        """计算约束：权重和应为1"""
        w = x / np.sum(x)
        # 权重和约束：sum(w) - 1 = 0
        return np.array([np.sum(w) - 1])


def demo_engineering_design():
    """演示工程设计优化"""
    print("=" * 60)
    print("工程设计优化示例：悬臂梁设计")
    print("=" * 60)

    # 创建问题
    problem = EngineeringDesignProblem()

    # 创建偏置管理器
    bias_manager = AlgorithmicBiasManager()

    # 添加多样性偏置：鼓励探索不同的设计方案
    bias_manager.add_bias(
        DiversityBias(
            weight=0.2,
            metric='euclidean'
        )
    )

    # 添加收敛偏置：在后期加速收敛
    bias_manager.add_bias(
        ConvergenceBias(
            weight=0.15,
            early_gen=10,
            late_gen=30
        )
    )

    # 创建求解器（禁用可视化）
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 50
    solver.max_generations = 50
    solver.enable_progress_log = True
    solver.report_interval = 10

    # 禁用可视化以避免错误
    if hasattr(solver, 'disable_visualization'):
        solver.disable_visualization()

    # 包装评估函数以集成偏置
    original_evaluate = problem.evaluate

    def biased_evaluate(x):
        base_value = original_evaluate(x)

        # 创建优化上下文
        context = OptimizationContext(
            generation=getattr(solver, 'generation', 0),
            individual=x,
            population=getattr(solver, 'population', []),
        )

        # 应用所有偏置
        total_bias = 0
        for bias in bias_manager.biases:
            total_bias += bias.apply(x, original_evaluate, context)

        return base_value + total_bias

    # 替换评估函数
    problem.evaluate = biased_evaluate

    # 运行优化
    print("\n开始优化...")
    result = solver.run()

    # 分析结果
    best_solution = result['pareto_solutions']['individuals'][0]
    best_objective = result['pareto_solutions']['objectives'][0][0]
    constraints = problem.evaluate_constraints(best_solution)

    L, W, H = best_solution[0], best_solution[1], best_solution[2]
    volume = L * W * H

    print("\n最优设计方案：")
    print(f"  长度: {L:.3f} m")
    print(f"  宽度: {W:.3f} m")
    print(f"  高度: {H:.3f} m")
    print(f"  体积: {volume:.6f} m³")
    print(f"  材料成本: {best_objective:.2f} 元")
    print(f"  挠度约束: {constraints[0]:.6f} m")
    print(f"  约束满足: {'✓' if constraints[0] <= 0 else '✗'}")

    return result


def demo_portfolio_optimization():
    """演示投资组合优化"""
    print("\n" + "=" * 60)
    print("投资组合优化示例")
    print("=" * 60)

    # 创建问题
    problem = PortfolioOptimizationProblem()

    # 创建偏置管理器
    bias_manager = AlgorithmicBiasManager()

    # 添加梯度下降偏置：引导向最优投资组合方向
    bias_manager.add_bias(
        GradientDescentBias(
            weight=0.1,
            learning_rate=0.005,
            momentum=0.9,
            adaptive_lr=True
        )
    )

    # 添加多样性偏置：避免过度集中投资
    bias_manager.add_bias(
        DiversityBias(
            weight=0.15,
            metric='euclidean'
        )
    )

    # 创建求解器（禁用可视化）
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 100
    solver.max_generations = 100
    solver.enable_progress_log = True
    solver.report_interval = 20

    # 禁用可视化
    if hasattr(solver, 'disable_visualization'):
        solver.disable_visualization()

    # 包装评估函数
    original_evaluate = problem.evaluate

    def biased_evaluate(x):
        base_value = original_evaluate(x)

        # 创建优化上下文
        context = OptimizationContext(
            generation=getattr(solver, 'generation', 0),
            individual=x,
            population=getattr(solver, 'population', []),
        )

        # 应用偏置
        total_bias = 0
        for bias in bias_manager.biases:
            total_bias += bias.apply(x, original_evaluate, context)

        return base_value + total_bias

    problem.evaluate = biased_evaluate

    # 运行优化
    print("\n开始优化...")
    result = solver.run()

    # 分析结果
    best_solution = result['pareto_solutions']['individuals'][0]
    best_objective = result['pareto_solutions']['objectives'][0][0]

    # 归一化权重
    weights = best_solution / np.sum(best_solution)

    # 计算组合指标
    portfolio_return = np.dot(weights, problem.expected_returns)
    portfolio_risk = np.sqrt(np.dot(weights, np.dot(problem.covariance, weights)))
    sharpe_ratio = (portfolio_return - 0.02) / portfolio_risk

    print("\n最优投资组合：")
    print(f"  夏普比率: {-best_objective:.4f}")
    print(f"  预期收益: {portfolio_return:.2%}")
    print(f"  风险(标准差): {portfolio_risk:.2%}")
    print("\n资产权重分配：")
    for i, w in enumerate(weights):
        print(f"  资产{i+1}: {w:.2%} (收益: {problem.expected_returns[i]:.1%})")

    return result


def compare_with_without_bias():
    """比较有偏置和无偏置的优化效果"""
    print("\n" + "=" * 60)
    print("有偏置 vs 无偏置 对比")
    print("=" * 60)

    # 使用简单测试问题
    problem = EngineeringDesignProblem()

    # 无偏置优化
    print("\n1. 无偏置优化：")
    solver1 = BlackBoxSolverNSGAII(problem)
    solver1.pop_size = 30
    solver1.max_generations = 30

    # 禁用可视化
    if hasattr(solver1, 'disable_visualization'):
        solver1.disable_visualization()

    result1 = solver1.run()
    best1 = result1['pareto_solutions']['individuals'][0]
    obj1 = result1['pareto_solutions']['objectives'][0][0]

    print(f"   最优成本: {obj1:.2f} 元")
    print(f"   设计方案: {best1}")

    # 有偏置优化
    print("\n2. 有偏置优化：")

    # 创建偏置
    bias_manager = AlgorithmicBiasManager()
    bias_manager.add_bias(DiversityBias(weight=0.2))
    bias_manager.add_bias(ConvergenceBias(weight=0.1, late_gen=20))

    # 包装评估函数
    original_evaluate = problem.evaluate

    def biased_evaluate(x):
        base_value = original_evaluate(x)
        context = OptimizationContext(
            generation=getattr(solver2, 'generation', 0),
            individual=x
        )

        total_bias = 0
        for bias in bias_manager.biases:
            total_bias += bias.apply(x, original_evaluate, context)

        return base_value + total_bias

    problem.evaluate = biased_evaluate

    solver2 = BlackBoxSolverNSGAII(problem)
    solver2.pop_size = 30
    solver2.max_generations = 30

    # 禁用可视化
    if hasattr(solver2, 'disable_visualization'):
        solver2.disable_visualization()

    result2 = solver2.run()
    best2 = result2['pareto_solutions']['individuals'][0]
    obj2 = result2['pareto_solutions']['objectives'][0][0]

    print(f"   最优成本: {obj2:.2f} 元")
    print(f"   设计方案: {best2}")

    # 比较
    improvement = ((obj1 - obj2) / obj1) * 100
    print(f"\n改进效果: {improvement:.2f}%")

    # 恢复原始评估函数
    problem.evaluate = original_evaluate


if __name__ == "__main__":
    print("偏置优化系统演示（无可视化版本）")

    # 运行示例
    demo_engineering_design()
    demo_portfolio_optimization()
    compare_with_without_bias()

    print("\n" + "=" * 60)
    print("演示完成！")
    print("\n偏置系统的优势：")
    print("✓ 引导搜索方向，加速收敛")
    print("✓ 维持种群多样性，避免早熟")
    print("✓ 灵活组合多种策略")
    print("✓ 适应不同问题的特性")
    print("=" * 60)