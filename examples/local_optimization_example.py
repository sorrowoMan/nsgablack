"""
局部优化偏置示例
演示如何使用偏置系统实现各种局部优化技术
"""

import numpy as np
import matplotlib.pyplot as plt
from bias.bias_local_optimization import create_derivative_free_suite
from core.base import BlackBoxProblem
from core.solver import BlackBoxSolverNSGAII
from bias import (
    AlgorithmicBiasManager,
    GradientDescentBias,
    NewtonMethodBias,
    LineSearchBias,
    TrustRegionBias,
    NelderMeadBias,
    QuasiNewtonBias,
    create_gradient_descent_suite,
    create_newton_suite,
    create_hybrid_local_suite,
    OptimizationContext
)


class RosenbrockFunction(BlackBoxProblem):
    """Rosenbrock函数 - 经典的测试函数（非凸，有全局最优）"""

    def __init__(self, dimension=2):
        super().__init__(
            name="Rosenbrock",
            dimension=dimension,
            bounds={f'x{i}': (-5, 5) for i in range(dimension)}
        )

    def evaluate(self, x):
        """Rosenbrock函数: f(x) = sum(100*(x[i+1] - x[i]^2)^2 + (1 - x[i])^2)"""
        total = 0
        for i in range(len(x) - 1):
            total += 100 * (x[i+1] - x[i]**2)**2 + (1 - x[i])**2
        return total

    def get_global_optimum(self):
        """全局最优解"""
        return np.ones(self.dimension)


class RastriginFunction(BlackBoxProblem):
    """Rastrigin函数 - 多模态函数"""

    def __init__(self, dimension=2):
        super().__init__(
            name="Rastrigin",
            dimension=dimension,
            bounds={f'x{i}': (-5.12, 5.12) for i in range(dimension)}
        )

    def evaluate(self, x):
        """Rastrigin函数: f(x) = 10*n + sum(x[i]^2 - 10*cos(2*pi*x[i]))"""
        n = len(x)
        return 10 * n + np.sum(x**2 - 10 * np.cos(2 * np.pi * x))


def demo_gradient_descent_bias():
    """演示梯度下降偏置"""
    print("\n=== 梯度下降偏置演示 ===")

    # 创建问题
    problem = RosenbrockFunction(dimension=2)

    # 创建偏置管理器
    bias_manager = AlgorithmicBiasManager()

    # 添加梯度下降偏置
    bias_manager.add_bias(
        GradientDescentBias(
            weight=0.3,
            learning_rate=0.01,
            momentum=0.9,
            adaptive_lr=True,
            nesterov=True
        )
    )

    # 添加线搜索偏置
    bias_manager.add_bias(
        LineSearchBias(
            weight=0.2,
            method='armijo',
            alpha=0.5,
            beta=0.8
        )
    )

    # 创建求解器
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 20
    solver.max_generations = 50
    solver.enable_progress_log = True

    # 集成偏置（通过修改适应度评估）
    original_evaluate = problem.evaluate

    def biased_evaluate(x):
        base_value = original_evaluate(x)

        # 创建优化上下文
        context = OptimizationContext(
            generation=solver.generation if hasattr(solver, 'generation') else 0,
            individual=x
        )

        # 应用偏置
        total_bias = 0
        for bias in bias_manager.biases:
            total_bias += bias.apply(x, original_evaluate, context)

        return base_value + total_bias

    problem.evaluate = biased_evaluate

    # 运行优化
    result = solver.run()

    # 显示结果
    best_solution = result['pareto_solutions']['individuals'][0]
    best_value = result['pareto_solutions']['objectives'][0][0]

    print(f"最优解: {best_solution}")
    print(f"最优值: {best_value:.6f}")
    print(f"理论最优值: 0.0")
    print(f"误差: {best_value:.6f}")

    return result


def demo_newton_method_bias():
    """演示牛顿法偏置"""
    print("\n=== 牛顿法偏置演示 ===")

    # 创建问题
    problem = RosenbrockFunction(dimension=2)

    # 创建偏置管理器
    bias_manager = AlgorithmicBiasManager()

    # 添加牛顿法偏置
    bias_manager.add_bias(
        NewtonMethodBias(
            weight=0.4,
            regularization=1e-6,
            use_damped_newton=True,
            use_bfgs_approx=True
        )
    )

    # 创建求解器
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 20
    solver.max_generations = 30
    solver.enable_progress_log = True

    # 集成偏置
    original_evaluate = problem.evaluate

    def biased_evaluate(x):
        base_value = original_evaluate(x)

        context = OptimizationContext(
            generation=solver.generation if hasattr(solver, 'generation') else 0,
            individual=x
        )

        total_bias = 0
        for bias in bias_manager.biases:
            total_bias += bias.apply(x, original_evaluate, context)

        return base_value + total_bias

    problem.evaluate = biased_evaluate

    # 运行优化
    result = solver.run()

    # 显示结果
    best_solution = result['pareto_solutions']['individuals'][0]
    best_value = result['pareto_solutions']['objectives'][0][0]

    print(f"最优解: {best_solution}")
    print(f"最优值: {best_value:.6f}")
    print(f"理论最优值: 0.0")
    print(f"误差: {best_value:.6f}")

    return result


def demo_trust_region_bias():
    """演示信赖域偏置"""
    print("\n=== 信赖域偏置演示 ===")

    # 创建问题
    problem = RastriginFunction(dimension=2)

    # 创建偏置管理器
    bias_manager = AlgorithmicBiasManager()

    # 添加信赖域偏置
    bias_manager.add_bias(
        TrustRegionBias(
            weight=0.3,
            initial_radius=0.5,
            eta1=0.25,
            eta2=0.75
        )
    )

    # 添加梯度下降辅助
    bias_manager.add_bias(
        GradientDescentBias(
            weight=0.1,
            learning_rate=0.005
        )
    )

    # 创建求解器
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 30
    solver.max_generations = 100
    solver.enable_progress_log = True

    # 集成偏置
    original_evaluate = problem.evaluate

    def biased_evaluate(x):
        base_value = original_evaluate(x)

        context = OptimizationContext(
            generation=solver.generation if hasattr(solver, 'generation') else 0,
            individual=x
        )

        total_bias = 0
        for bias in bias_manager.biases:
            total_bias += bias.apply(x, original_evaluate, context)

        return base_value + total_bias

    problem.evaluate = biased_evaluate

    # 运行优化
    result = solver.run()

    # 显示结果
    best_solution = result['pareto_solutions']['individuals'][0]
    best_value = result['pareto_solutions']['objectives'][0][0]

    print(f"最优解: {best_solution}")
    print(f"最优值: {best_value:.6f}")
    print(f"理论最优值: 0.0")
    print(f"误差: {best_value:.6f}")

    return result


def demo_nelder_mead_bias():
    """演示Nelder-Mead单纯形法偏置"""
    print("\n=== Nelder-Mead单纯形法偏置演示 ===")

    # 创建问题
    problem = RosenbrockFunction(dimension=2)

    # 创建偏置管理器
    bias_manager = AlgorithmicBiasManager()

    # 添加Nelder-Mead偏置
    bias_manager.add_bias(
        NelderMeadBias(
            weight=0.3,
            simplex_size=0.1
        )
    )

    # 创建求解器
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 20
    solver.max_generations = 40
    solver.enable_progress_log = True

    # 集成偏置
    original_evaluate = problem.evaluate

    def biased_evaluate(x):
        base_value = original_evaluate(x)

        context = OptimizationContext(
            generation=solver.generation if hasattr(solver, 'generation') else 0,
            individual=x
        )

        total_bias = 0
        for bias in bias_manager.biases:
            total_bias += bias.apply(x, original_evaluate, context)

        return base_value + total_bias

    problem.evaluate = biased_evaluate

    # 运行优化
    result = solver.run()

    # 显示结果
    best_solution = result['pareto_solutions']['individuals'][0]
    best_value = result['pareto_solutions']['objectives'][0][0]

    print(f"最优解: {best_solution}")
    print(f"最优值: {best_value:.6f}")
    print(f"理论最优值: 0.0")
    print(f"误差: {best_value:.6f}")

    return result


def demo_hybrid_local_optimization():
    """演示混合局部优化"""
    print("\n=== 混合局部优化演示 ===")

    # 创建问题
    problem = RosenbrockFunction(dimension=5)  # 高维版本

    # 使用预定义的混合套件
    hybrid_biases = create_hybrid_local_suite(
        learning_rate=0.01,
        momentum=0.9,
        method='bfgs'
    )

    # 创建偏置管理器
    bias_manager = AlgorithmicBiasManager()
    for bias in hybrid_biases:
        bias_manager.add_bias(bias)

    # 创建求解器
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 40
    solver.max_generations = 80
    solver.enable_progress_log = True

    # 集成偏置
    original_evaluate = problem.evaluate

    def biased_evaluate(x):
        base_value = original_evaluate(x)

        context = OptimizationContext(
            generation=solver.generation if hasattr(solver, 'generation') else 0,
            individual=x
        )

        total_bias = 0
        for bias in bias_manager.biases:
            total_bias += bias.apply(x, original_evaluate, context)

        return base_value + total_bias

    problem.evaluate = biased_evaluate

    # 运行优化
    result = solver.run()

    # 显示结果
    best_solution = result['pareto_solutions']['individuals'][0]
    best_value = result['pareto_solutions']['objectives'][0][0]

    print(f"最优解: {best_solution}")
    print(f"最优值: {best_value:.6f}")
    print(f"理论最优值: 0.0")
    print(f"误差: {best_value:.6f}")

    return result


def demo_adaptive_local_optimization():
    """演示自适应局部优化"""
    print("\n=== 自适应局部优化演示 ===")

    # 创建问题
    problem = RosenbrockFunction(dimension=3)

    # 创建偏置管理器
    bias_manager = AlgorithmicBiasManager()

    # 阶段1：早期使用梯度下降
    bias_manager.add_bias(
        GradientDescentBias(
            weight=0.2,
            learning_rate=0.02,
            adaptive_lr=True
        )
    )

    # 阶段2：中期加入牛顿法
    bias_manager.add_bias(
        NewtonMethodBias(
            weight=0.15,
            use_bfgs_approx=True
        )
    )

    # 阶段3：后期使用信赖域精细调整
    bias_manager.add_bias(
        TrustRegionBias(
            weight=0.1,
            initial_radius=0.2
        )
    )

    # 创建求解器
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 30
    solver.max_generations = 60
    solver.enable_progress_log = True

    # 记录优化历史
    history = []

    def biased_evaluate(x):
        base_value = original_evaluate(x)

        # 自适应调整偏置权重
        if hasattr(solver, 'generation'):
            gen = solver.generation
            total_gen = solver.max_generations

            # 早期：侧重梯度下降
            if gen < total_gen * 0.3:
                bias_manager.biases[0].weight = 0.25  # 梯度下降
                bias_manager.biases[1].weight = 0.05  # 牛顿法
                bias_manager.biases[2].weight = 0.05  # 信赖域
            # 中期：平衡使用
            elif gen < total_gen * 0.7:
                bias_manager.biases[0].weight = 0.15
                bias_manager.biases[1].weight = 0.15
                bias_manager.biases[2].weight = 0.1
            # 后期：侧重精细优化
            else:
                bias_manager.biases[0].weight = 0.1
                bias_manager.biases[1].weight = 0.1
                bias_manager.biases[2].weight = 0.2

        context = OptimizationContext(
            generation=solver.generation if hasattr(solver, 'generation') else 0,
            individual=x
        )

        total_bias = 0
        for bias in bias_manager.biases:
            total_bias += bias.apply(x, original_evaluate, context)

        # 记录历史
        history.append({
            'generation': solver.generation if hasattr(solver, 'generation') else 0,
            'base_value': base_value,
            'bias_value': total_bias,
            'total_value': base_value + total_bias
        })

        return base_value + total_bias

    original_evaluate = problem.evaluate
    problem.evaluate = biased_evaluate

    # 运行优化
    result = solver.run()

    # 显示结果
    best_solution = result['pareto_solutions']['individuals'][0]
    best_value = result['pareto_solutions']['objectives'][0][0]

    print(f"最优解: {best_solution}")
    print(f"最优值: {best_value:.6f}")
    print(f"理论最优值: 0.0")
    print(f"误差: {best_value:.6f}")

    # 绘制优化历史
    if history:
        generations = [h['generation'] for h in history]
        base_values = [h['base_value'] for h in history]
        total_values = [h['total_value'] for h in history]

        plt.figure(figsize=(10, 6))
        plt.plot(generations, base_values, 'b-', label='原始函数值', alpha=0.7)
        plt.plot(generations, total_values, 'r-', label='偏置调整后值', linewidth=2)
        plt.xlabel('进化代数')
        plt.ylabel('函数值')
        plt.title('自适应局部优化过程')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.yscale('log')
        plt.show()

    return result


def compare_local_optimization_methods():
    """比较不同局部优化方法"""
    print("\n=== 局部优化方法比较 ===")

    problem = RosenbrockFunction(dimension=2)

    methods = {
        "梯度下降": create_gradient_descent_suite(),
        "牛顿法": create_newton_suite(),
        "混合方法": create_hybrid_local_suite(),
        "无导数方法": create_derivative_free_suite()
    }

    results = {}

    for method_name, biases in methods.items():
        print(f"\n测试方法: {method_name}")

        # 创建偏置管理器
        bias_manager = AlgorithmicBiasManager()
        for bias in biases:
            bias_manager.add_bias(bias)

        # 创建求解器
        solver = BlackBoxSolverNSGAII(problem)
        solver.pop_size = 20
        solver.max_generations = 50

        # 集成偏置
        original_evaluate = problem.evaluate

        def biased_evaluate(x):
            base_value = original_evaluate(x)
            context = OptimizationContext(
                generation=solver.generation if hasattr(solver, 'generation') else 0,
                individual=x
            )

            total_bias = 0
            for bias in bias_manager.biases:
                total_bias += bias.apply(x, original_evaluate, context)

            return base_value + total_bias

        problem.evaluate = biased_evaluate

        # 运行优化
        import time
        start_time = time.time()
        result = solver.run()
        end_time = time.time()

        # 记录结果
        best_value = result['pareto_solutions']['objectives'][0][0]
        results[method_name] = {
            'best_value': best_value,
            'time': end_time - start_time,
            'evaluations': solver.pop_size * solver.max_generations
        }

        print(f"  最优值: {best_value:.6f}")
        print(f"  用时: {end_time - start_time:.2f}秒")

    # 打印比较结果
    print("\n=== 比较结果汇总 ===")
    print(f"{'方法':<12} {'最优值':<12} {'用时(秒)':<10} {'评估次数':<10}")
    print("-" * 50)

    for method, data in results.items():
        print(f"{method:<12} {data['best_value']:<12.6f} {data['time']:<10.2f} {data['evaluations']:<10}")

    return results


if __name__ == "__main__":
    print("局部优化偏置演示")
    print("=" * 50)

    # 运行各种演示
    print("\n选择演示模式:")
    print("1. 梯度下降偏置")
    print("2. 牛顿法偏置")
    print("3. 信赖域偏置")
    print("4. Nelder-Mead偏置")
    print("5. 混合局部优化")
    print("6. 自适应局部优化")
    print("7. 方法比较")
    print("8. 运行所有演示")

    try:
        choice = input("\n请输入选择 (1-8): ").strip()

        if choice == "1":
            demo_gradient_descent_bias()
        elif choice == "2":
            demo_newton_method_bias()
        elif choice == "3":
            demo_trust_region_bias()
        elif choice == "4":
            demo_nelder_mead_bias()
        elif choice == "5":
            demo_hybrid_local_optimization()
        elif choice == "6":
            demo_adaptive_local_optimization()
        elif choice == "7":
            compare_local_optimization_methods()
        elif choice == "8":
            print("\n运行所有演示...")
            demo_gradient_descent_bias()
            demo_newton_method_bias()
            demo_trust_region_bias()
            demo_nelder_mead_bias()
            demo_hybrid_local_optimization()
            demo_adaptive_local_optimization()
            compare_local_optimization_methods()
        else:
            print("无效选择，运行默认演示...")
            demo_hybrid_local_optimization()

    except KeyboardInterrupt:
        print("\n\n演示被用户中断")
    except Exception as e:
        print(f"\n运行出错: {e}")
        # 运行默认演示
        print("\n运行默认演示...")
        demo_hybrid_local_optimization()

    print("\n演示完成！")