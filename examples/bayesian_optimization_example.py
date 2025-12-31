"""
贝叶斯优化示例
演示贝叶斯优化器的三种使用方式：
1. 作为独立的全局优化器
2. 作为偏置策略引导NSGA-II
3. 与NSGA-II混合优化
"""

import numpy as np
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.base import BlackBoxProblem
from solvers.bayesian_optimizer import BayesianOptimizer, bayesian_optimize
from solvers.hybrid_bo import HybridBO_NSGA, AdaptiveBOOptimizer
from bias import (
    AlgorithmicBiasManager,
    BayesianGuidanceBias,
    BayesianExplorationBias,
    OptimizationContext
)
try:
    from examples.simple_bias_minimal import SimpleNSGAII
except ImportError:
    # Fallback if running as script
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from simple_bias_minimal import SimpleNSGAII


class ExpensiveFunction(BlackBoxProblem):
    """昂贵函数示例 - 模拟需要长时间运行的仿真"""

    def __init__(self, dimension=2):
        bounds = [( -5, 5) for _ in range(dimension)]
        super().__init__(
            name="ExpensiveFunction",
            dimension=dimension,
            bounds=bounds
        )

    def evaluate(self, x):
        """复杂的非凸函数"""
        # 模拟计算延迟
        import time
        time.sleep(0.01)  # 模拟昂贵计算

        # 复合函数：多个局部最优
        term1 = np.sum(x**2)  # 二次项
        term2 = 10 * np.sin(x[0] * x[1])  # 非线性项
        term3 = 5 * np.cos(x[0]) * np.cos(x[1])  # 周期项
        term4 = 0.1 * (x[0]**4 + x[1]**4)  # 高阶项

        return term1 + term2 + term3 + term4


class EngineeringDesignProblem(BlackBoxProblem):
    """工程设计优化问题"""

    def __init__(self):
        super().__init__(
            name="EngineeringDesign",
            dimension=3,
            bounds=[(0.1, 10.0), (0.1, 10.0), (0.1, 10.0)]
        )

    def evaluate(self, x):
        """工程目标函数：最小化成本"""
        a, b, c = x

        # 材料成本
        material_cost = 2 * a + 3 * b + 1.5 * c

        # 制造成本（非线性）
        manufacturing_cost = 10 * (a**0.5 + b**0.5 + c**0.5)

        # 性能惩罚（如果性能不达标）
        performance = a * b * c  # 性能指标
        penalty = 0
        if performance < 5:
            penalty = 100 * (5 - performance)**2

        return material_cost + manufacturing_cost + penalty


def demo_standalone_bayesian():
    """演示独立的贝叶斯优化"""
    print("=" * 60)
    print("独立贝叶斯优化示例")
    print("=" * 60)

    # 创建问题
    problem = ExpensiveFunction(dimension=2)

    # 设置边界
    bounds = [(-5, 5), (-5, 5)]

    # 创建优化器
    bo = BayesianOptimizer(
        acquisition='ei',
        kernel='matern',
        alpha=1e-6
    )

    # 运行优化
    print("\n开始贝叶斯优化...")
    result = bo.optimize(
        objective_func=problem.evaluate,
        bounds=bounds,
        budget=50,
        callback=lambda i, x, y, best: print(f"  迭代 {i+1:2d}: 当前={y:8.4f}, 最优={best:8.4f}")
    )

    print(f"\n优化结果：")
    print(f"  最优解: [{result['best_x'][0]:.4f}, {result['best_x'][1]:.4f}]")
    print(f"  最优值: {result['best_y']:.6f}")

    # 绘制结果
    try:
        bo.plot_optimization()
    except:
        print("  (绘图功能不可用)")

    return result


def demo_bayesian_as_bias():
    """演示贝叶斯偏置引导的优化"""
    print("\n" + "=" * 60)
    print("贝叶斯偏置示例：BO引导NSGA-II")
    print("=" * 60)

    # 创建问题
    problem = ExpensiveFunction(dimension=2)

    # 创建偏置管理器
    bias_manager = AlgorithmicBiasManager()

    # 添加贝叶斯引导偏置
    bias_manager.add_bias(
        BayesianGuidanceBias(
            weight=0.3,
            buffer_size=30,
            acquisition='ei',
            adaptive_weight=True
        )
    )

    # 添加多样性偏置
    bias_manager.add_bias(
        BayesianExplorationBias(
            weight=0.2,
            uncertainty_threshold=0.1
        )
    )

    # 包装评估函数
    original_evaluate = problem.evaluate
    eval_count = [0]  # 使用列表以便在闭包中修改

    def biased_evaluate(x):
        eval_count[0] += 1
        base_value = original_evaluate(x)

        # 创建优化上下文
        context = OptimizationContext(
            generation=getattr(solver, 'generation', 0),
            individual=x,
            population=getattr(solver, 'population', []),
            individual_value=base_value
        )

        # 应用偏置
        total_bias = 0
        for bias in bias_manager.biases.values():
            total_bias += bias.compute(x, context)

        return base_value + total_bias

    problem.evaluate = biased_evaluate

    # 运行优化
    solver = SimpleNSGAII(problem, pop_size=30, max_generations=50)
    print("\n开始贝叶斯偏置引导的NSGA-II优化...")
    result = solver.run()

    # 计算真实值
    best_x = result['pareto_solutions']['individuals'][0]
    true_value = original_evaluate(best_x)

    print(f"\n优化结果：")
    print(f"  最优解: [{best_x[0]:.4f}, {best_x[1]:.4f}]")
    print(f"  偏置值: {result['pareto_solutions']['objectives'][0][0]:.6f}")
    print(f"  真实值: {true_value:.6f}")
    print(f"  评估次数: {eval_count[0]}")

    # 恢复原始评估
    problem.evaluate = original_evaluate

    return result


def demo_hybrid_optimization():
    """演示混合优化"""
    print("\n" + "=" * 60)
    print("混合优化示例：BO + NSGA-II")
    print("=" * 60)

    # 创建问题
    problem = EngineeringDesignProblem()

    # 创建混合求解器
    hybrid = HybridBO_NSGA(
        problem=problem,
        bo_ratio=0.4,  # 40% 预算给BO
        adapt_strategy=True
    )

    # 运行混合优化
    print("\n开始混合优化...")
    result = hybrid.run(total_budget=200, verbose=True)

    print(f"\n混合优化结果：")
    print(f"  最优解: {result['best_x']}")
    print(f"  最优值: {result['best_y']:.6f}")
    print(f"  最优来源: {result['best_source']}")
    print(f"  总用时: {result['total_time']:.2f}秒")

    # 分析性能
    if 'performance_history' in result:
        bo_contribution = result['bo_result']['best_y'] if 'bo_result' in result else float('inf')
        print(f"\n阶段贡献：")
        print(f"  BO阶段最优: {bo_contribution:.6f}")
        print(f"  最终最优: {result['best_y']:.6f}")

    return result


def demo_adaptive_bayesian():
    """演示自适应贝叶斯优化"""
    print("\n" + "=" * 60)
    print("自适应贝叶斯优化示例")
    print("=" * 60)

    # 创建问题
    problem = ExpensiveFunction(dimension=2)

    # 创建自适应优化器
    adaptive_bo = AdaptiveBOOptimizer(
        problem=problem,
        initial_strategy='ei',
        adaptation_frequency=25
    )

    # 运行自适应优化
    print("\n开始自适应贝叶斯优化...")
    result = adaptive_bo.run(budget=100, verbose=True)

    print(f"\n自适应优化结果：")
    print(f"  最优解: {result['best_x']}")
    print(f"  最优值: {result['best_y']:.6f}")

    # 策略使用历史
    if 'strategy_history' in result:
        from collections import Counter
        strategy_counts = Counter(result['strategy_history'])
        print(f"\n策略使用统计：")
        for strategy, count in strategy_counts.items():
            print(f"  {strategy}: {count} 次")

    return result


def compare_methods():
    """比较不同方法"""
    print("\n" + "=" * 60)
    print("方法比较")
    print("=" * 60)

    problem = ExpensiveFunction(dimension=2)
    bounds = [(-5, 5), (-5, 5)]
    budget = 50

    # 方法1：独立BO
    print("\n1. 独立贝叶斯优化...")
    bo_result = bayesian_optimize(
        objective_func=problem.evaluate,
        bounds=bounds,
        budget=budget,
        acquisition='ei'
    )

    # 方法2：BO偏置引导的NSGA-II（简化版）
    print("\n2. 标准NSGA-II...")
    try:
        from examples.simple_bias_minimal import SimpleNSGAII
    except ImportError:
        # Fallback if running as script
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from simple_bias_minimal import SimpleNSGAII
    solver_nsga = SimpleNSGAII(problem, pop_size=25, max_generations=30)
    nsga_result = solver_nsga.run()

    # 方法3：混合优化（小规模）
    print("\n3. 混合优化（小规模）...")
    hybrid_small = HybridBO_NSGA(problem, bo_ratio=0.3)
    hybrid_result = hybrid_small.run(total_budget=budget, verbose=False)

    # 比较
    print("\n" + "=" * 60)
    print("比较结果：")
    print(f"{'方法':<20} {'最优值':<15} {'评估次数':<10}")
    print("-" * 50)
    print(f"{'独立BO':<20} {bo_result['best_y']:<15.6f} {bo_result['n_evaluations']:<10}")

    nsga_best = nsga_result['pareto_solutions']['objectives'][0][0]
    print(f"{'NSGA-II':<20} {nsga_best:<15.6f} {solver_nsga.pop_size * solver_nsga.max_generations:<10}")
    print(f"{'混合优化':<20} {hybrid_result['best_y']:<15.6f} {budget:<10}")

    # 找出最佳方法
    best_value = min(bo_result['best_y'], nsga_best, hybrid_result['best_y'])
    if best_value == bo_result['best_y']:
        print(f"\n★ 最佳方法: 独立贝叶斯优化")
    elif best_value == nsga_best:
        print(f"\n★ 最佳方法: NSGA-II")
    else:
        print(f"\n★ 最佳方法: 混合优化")


if __name__ == "__main__":
    print("贝叶斯优化系统演示")
    print("=" * 60)

    # 运行所有演示
    print("\n选择演示模式：")
    print("1. 独立贝叶斯优化")
    print("2. 贝叶斯偏置引导")
    print("3. 混合优化")
    print("4. 自适应贝叶斯优化")
    print("5. 方法比较")
    print("6. 运行所有演示")

    try:
        choice = input("\n请输入选择 (1-6): ").strip()

        if choice == "1":
            demo_standalone_bayesian()
        elif choice == "2":
            demo_bayesian_as_bias()
        elif choice == "3":
            demo_hybrid_optimization()
        elif choice == "4":
            demo_adaptive_bayesian()
        elif choice == "5":
            compare_methods()
        elif choice == "6":
            print("\n运行所有演示...\n")
            demo_standalone_bayesian()
            demo_bayesian_as_bias()
            demo_hybrid_optimization()
            demo_adaptive_bayesian()
            compare_methods()
        else:
            print("无效选择，运行默认演示...")
            demo_standalone_bayesian()

    except KeyboardInterrupt:
        print("\n\n演示被用户中断")
    except Exception as e:
        print(f"\n运行出错: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("演示完成！")
    print("\n贝叶斯优化系统的优势：")
    print("✓ 高样本效率，适合昂贵函数")
    print("✓ 不确定性量化，平衡探索与利用")
    print("✓ 灵活的获取函数选择")
    print("✓ 支持多场景应用（独立、偏置、混合）")
    print("✓ 理论保证，性能可靠")
    print("=" * 60)