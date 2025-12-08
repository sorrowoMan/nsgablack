#!/usr/bin/env python3
"""
偏置系统 v2.0 简单示例
演示如何使用新的偏置系统进行优化

这个示例展示了：
1. 如何创建偏置管理器
2. 如何添加算法偏置和业务偏置
3. 如何在求解器中使用偏置
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from core.base import BlackBoxProblem
from core.solver import BlackBoxSolverNSGAII
from bias_v2 import (
    UniversalBiasManager,
    OptimizationContext,
    create_bias_manager_from_template
)
from bias_library_algorithmic import DiversityBias, ConvergenceBias
from bias_library_domain import ConstraintBias, PreferenceBias


class ConstrainedRosenbrockProblem(BlackBoxProblem):
    """带约束的 Rosenbrock 问题"""

    def __init__(self):
        super().__init__(
            name="Constrained Rosenbrock",
            dimension=2,
            bounds={'x0': (-2.0, 2.0), 'x1': (-2.0, 2.0)}
        )

    def evaluate(self, x):
        # Rosenbrock 函数
        return 100 * (x[1] - x[0]**2)**2 + (1 - x[0])**2

    def evaluate_constraints(self, x):
        return np.array([
            x[0] + x[1] - 2.5,     # g1(x) <= 0
            1.5 - x[0]            # g2(x) <= 0
        ])


def demonstrate_basic_bias_usage():
    """演示基础偏置使用"""
    print("=" * 60)
    print("偏置系统 v2.0 基础使用示例")
    print("=" * 60)

    # 创建问题
    problem = ConstrainedRosenbrockProblem()
    print(f"问题: {problem.name}")
    print(f"维度: {problem.dimension}")
    print(f"目标: 最小化 Rosenbrock 函数 (全局最优在 [1, 1])")
    print(f"约束: x0 + x1 <= 2.5, x0 >= 1.5")

    # 创建偏置管理器
    print("\n1. 创建偏置管理器...")
    bias_manager = UniversalBiasManager()
    print(f"   [OK] 偏置权重: 算法={bias_manager.bias_weights['algorithmic']:.1f}, 业务={bias_manager.bias_weights['domain']:.1f}")

    # 添加算法偏置
    print("\n2. 添加算法偏置...")
    diversity_bias = DiversityBias(weight=0.2, metric='euclidean')
    convergence_bias = ConvergenceBias(weight=0.1, early_gen=10, late_gen=50)

    bias_manager.algorithmic_manager.add_bias(diversity_bias)
    bias_manager.algorithmic_manager.add_bias(convergence_bias)
    print("   [OK] 已添加: 多样性偏置, 收敛性偏置")

    # 添加业务偏置
    print("\n3. 添加业务偏置...")
    constraint_bias = ConstraintBias(weight=2.0)

    # 添加硬约束
    constraint_bias.add_hard_constraint(lambda x: max(0, x[0] + x[1] - 2.5))
    constraint_bias.add_hard_constraint(lambda x: max(0, 1.5 - x[0]))

    bias_manager.domain_manager.add_bias(constraint_bias)
    print("   [OK] 已添加: 约束偏置 (2个硬约束)")

    # 创建求解器
    print("\n4. 创建求解器...")
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 50
    solver.max_generations = 100
    solver.enable_bias = True
    solver.bias_manager = bias_manager
    print("   [OK] 求解器配置完成")

    # 运行优化
    print("\n5. 开始优化...")
    print("   迭代进度 (每10代显示一次):")

    result = solver.run()

    # 显示结果
    print("\n" + "=" * 60)
    print("优化结果")
    print("=" * 60)

    if len(result['pareto_solutions']['individuals']) > 0:
        best_solution = result['pareto_solutions']['individuals'][0]
        best_objective = result['pareto_solutions']['objectives'][0][0]

        print(f"最优解: [{best_solution[0]:.6f}, {best_solution[1]:.6f}]")
        print(f"最优值: {best_objective:.6f}")

        # 检查约束满足情况
        constraints = problem.evaluate_constraints(best_solution)
        print(f"约束值: g1={constraints[0]:.6f}, g2={constraints[1]:.6f}")

        if np.all(constraints <= 1e-6):
            print("[OK] 所有约束都满足")
        else:
            print("[WARNING] 存在约束违反")
    else:
        print("未找到可行解")


def demonstrate_template_usage():
    """演示模板使用"""
    print("\n" + "=" * 60)
    print("偏置系统模板使用示例")
    print("=" * 60)

    # 创建问题
    problem = ConstrainedRosenbrockProblem()

    # 使用工程设计模板
    print("\n1. 使用工程设计模板...")
    eng_bias_manager = create_bias_manager_from_template('basic_engineering')
    print("   [OK] 创建工程设计偏置管理器")

    # 添加问题的约束
    constraint_bias = eng_bias_manager.domain_manager.get_bias('engineering_design')
    if constraint_bias:
        constraint_bias.add_hard_constraint(lambda x: max(0, x[0] + x[1] - 2.5))
        constraint_bias.add_hard_constraint(lambda x: max(0, 1.5 - x[0]))
        print("   [OK] 已添加约束到工程设计偏置")

    # 创建求解器
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 40
    solver.max_generations = 80
    solver.enable_bias = True
    solver.bias_manager = eng_bias_manager

    # 运行优化
    print("\n2. 运行优化...")
    result = solver.run()

    # 显示结果
    if len(result['pareto_solutions']['individuals']) > 0:
        best_solution = result['pareto_solutions']['individuals'][0]
        best_objective = result['pareto_solutions']['objectives'][0][0]

        print(f"最优解: [{best_solution[0]:.6f}, {best_solution[1]:.6f}]")
        print(f"最优值: {best_objective:.6f}")

        constraints = problem.evaluate_constraints(best_solution)
        print(f"约束值: g1={constraints[0]:.6f}, g2={constraints[1]:.6f}")
        print("[OK] 工程设计模板优化完成")


def demonstrate_bias_weights():
    """演示偏置权重调整"""
    print("\n" + "=" * 60)
    print("偏置权重调整示例")
    print("=" * 60)

    # 创建问题
    problem = ConstrainedRosenbrockProblem()

    # 创建偏置管理器
    bias_manager = UniversalBiasManager()

    # 添加一些偏置
    bias_manager.algorithmic_manager.add_bias(DiversityBias(weight=0.3))
    bias_manager.domain_manager.add_bias(ConstraintBias(weight=1.0))

    # 测试不同的权重配置
    test_x = np.array([1.2, 1.0])
    context = OptimizationContext(generation=25, individual=test_x)

    configs = [
        ("默认权重", 0.3, 0.7),
        ("算法导向", 0.7, 0.3),
        ("业务导向", 0.1, 0.9),
        ("平衡权重", 0.5, 0.5)
    ]

    print("\n不同权重配置下的偏置值:")
    print("-" * 50)

    for name, alg_weight, domain_weight in configs:
        bias_manager.set_bias_weights(alg_weight, domain_weight)
        total_bias = bias_manager.compute_total_bias(test_x, context)

        alg_bias = bias_manager.algorithmic_manager.compute_algorithmic_bias(test_x, context)
        domain_bias = bias_manager.domain_manager.compute_domain_bias(test_x, context)

        print(f"{name:12s}: 算法={alg_bias:8.4f} + 业务={domain_bias:8.4f} = 总={total_bias:8.4f}")


def main():
    """主函数"""
    print("偏置系统 v2.0 示例程序")
    print("演示新的双重架构偏置系统")

    try:
        # 基础使用
        demonstrate_basic_bias_usage()

        # 模板使用
        demonstrate_template_usage()

        # 权重调整
        demonstrate_bias_weights()

        print("\n" + "=" * 60)
        print("[SUCCESS] 所有示例运行成功!")
        print("[SUCCESS] 偏置系统 v2.0 功能正常!")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] 运行出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()