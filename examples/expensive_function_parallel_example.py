"""
昂贵函数并行评估示例
演示如何使用并行评估加速昂贵的优化过程
"""

import time
import numpy as np
import matplotlib.pyplot as plt
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.base import BlackBoxProblem
from core.solver import BlackBoxSolverNSGAII
from utils.headless import run_headless_single_objective
from utils.parallel_evaluator import ParallelEvaluator, SmartEvaluatorSelector


# ==================== 昂贵测试函数 ====================
class ExpensiveEngineeringProblem(BlackBoxProblem):
    """
    模拟昂贵的工程仿真问题
    例如：CFD流场计算、结构力学分析、电磁场仿真等
    """

    def __init__(self, dimension=5, simulation_time=0.1):
        super().__init__(
            name="昂贵工程仿真",
            dimension=dimension,
            bounds={f'x{i}': (0, 10) for i in range(dimension)}
        )
        self.simulation_time = simulation_time  # 模拟仿真时间

    def evaluate(self, x):
        """模拟昂贵的仿真计算"""
        # 模拟计算时间
        time.sleep(self.simulation_time)

        # 复杂的目标函数（模拟真实的工程优化目标）
        # 组合多个非线性项，增加计算复杂度
        term1 = np.sum(x**2)  # 基础二次项
        term2 = 10 * np.sum(np.sin(2 * np.pi * x))  # 多模态项
        term3 = np.prod(1 + 0.1 * x)  # 交互项

        # 添加一些随机性（模拟数值误差）
        noise = np.random.normal(0, 0.01)

        return term1 + term2 + term3 + noise


class CADOptimizationProblem(BlackBoxProblem):
    """
    模拟CAD参数优化问题
    例如：机械零件形状优化、天线设计等
    """

    def __init__(self, dimension=8, cad_time=0.05):
        super().__init__(
            name="CAD参数优化",
            dimension=dimension,
            bounds={f'param{i}': (-5, 5) for i in range(dimension)}
        )
        self.cad_time = cad_time

    def evaluate(self, x):
        """模拟CAD模型重建和分析"""
        time.sleep(self.cad_time)

        # 模拟CAD分析的目标函数
        # 最小化某种性能指标（如应力、重量、成本等）
        volume = np.prod(np.abs(x) + 1)  # 体积
        stress = np.sum(x**2 * np.sin(x))  # 应力分析
        manufacturing_cost = np.sum(np.abs(x)) * 0.5  # 制造成本

        return volume + stress + manufacturing_cost


class MachineLearningModelOptimization(BlackBoxProblem):
    """
    模拟机器学习模型超参数优化
    例如：神经网络架构搜索、超参数调优等
    """

    def __init__(self, dimension=6, training_time=0.2):
        super().__init__(
            name="ML模型优化",
            dimension=dimension,
            bounds={f'hyperparam{i}': (0.001, 1.0) for i in range(dimension)}
        )
        self.training_time = training_time
        self.best_known_score = 0.95  # 模拟已知的最佳性能

    def evaluate(self, x):
        """模拟模型训练和验证"""
        time.sleep(self.training_time)

        # 模拟模型性能评估
        # 超参数通常有复杂的交互效应
        learning_rate = x[0]
        batch_size = int(x[1] * 100) + 10
        dropout = x[2]
        regularization = x[3]
        hidden_units = int(x[4] * 200) + 50
        momentum = x[5]

        # 模拟验证损失（越小越好）
        # 简化的模型性能函数
        base_loss = 1.0

        # 学习率影响
        if 0.001 <= learning_rate <= 0.01:
            base_loss *= 0.8
        elif 0.01 < learning_rate <= 0.1:
            base_loss *= 0.9
        else:
            base_loss *= 1.2

        # dropout和正则化影响
        if 0.2 <= dropout <= 0.5 and 0.0001 <= regularization <= 0.01:
            base_loss *= 0.85
        else:
            base_loss *= 1.1

        # 添加一些随机性
        noise = np.random.normal(0, 0.02)

        return base_loss + noise


# ==================== 性能测试函数 ====================
def benchmark_serial_vs_parallel(problem, pop_size=50, max_workers=4):
    """对比串行和并行评估的性能"""

    print(f"\n{'='*60}")
    print(f"性能测试: {problem.name}")
    print(f"种群规模: {pop_size}, 工作线程数: {max_workers}")
    print(f"{'='*60}")

    # 生成测试种群
    population = np.random.uniform(
        low=[problem.bounds[f'x{i}'][0] for i in range(problem.dimension)],
        high=[problem.bounds[f'x{i}'][1] for i in range(problem.dimension)],
        size=(pop_size, problem.dimension)
    )

    # 串行评估
    print("\n1. 串行评估...")
    serial_evaluator = ParallelEvaluator(backend="thread", max_workers=1)

    start_time = time.time()
    objectives_serial, violations_serial = serial_evaluator.evaluate_population(
        population, problem
    )
    serial_time = time.time() - start_time

    print(f"   串行评估时间: {serial_time:.3f}秒")
    print(f"   平均每个个体: {serial_time/pop_size*1000:.2f}毫秒")

    # 并行评估
    print(f"\n2. 并行评估（{max_workers}线程）...")
    parallel_evaluator = ParallelEvaluator(
        backend="thread",
        max_workers=max_workers,
        verbose=True
    )

    start_time = time.time()
    objectives_parallel, violations_parallel = parallel_evaluator.evaluate_population(
        population, problem
    )
    parallel_time = time.time() - start_time

    print(f"   并行评估时间: {parallel_time:.3f}秒")
    print(f"   平均每个个体: {parallel_time/pop_size*1000:.2f}毫秒")

    # 计算加速比
    speedup = serial_time / parallel_time if parallel_time > 0 else 0
    efficiency = speedup / max_workers * 100

    print(f"\n3. 性能分析:")
    print(f"   加速比: {speedup:.2f}x")
    print(f"   并行效率: {efficiency:.1f}%")

    # 验证结果一致性
    max_diff = np.max(np.abs(objectives_serial - objectives_parallel))
    print(f"   结果差异: {max_diff:.6f} (应接近0)")

    # 获取详细统计
    stats = parallel_evaluator.get_stats()
    print(f"\n4. 详细统计:")
    print(f"   总评估次数: {stats['total_evaluations']}")
    print(f"   错误次数: {stats['error_count']}")
    print(f"   平均评估时间: {stats['avg_evaluation_time']*1000:.2f}ms")

    return {
        'serial_time': serial_time,
        'parallel_time': parallel_time,
        'speedup': speedup,
        'efficiency': efficiency,
        'stats': stats
    }


def test_different_backends(problem, pop_size=30):
    """测试不同后端的性能"""

    print(f"\n{'='*60}")
    print(f"后端性能对比: {problem.name}")
    print(f"{'='*60}")

    population = np.random.uniform(
        low=[problem.bounds[f'x{i}'][0] for i in range(problem.dimension)],
        high=[problem.bounds[f'x{i}'][1] for i in range(problem.dimension)],
        size=(pop_size, problem.dimension)
    )

    backends = ["thread"]

    # 检查可用后端
    try:
        import joblib
        backends.append("joblib")
        print("   joblib 后端可用")
    except ImportError:
        print("   joblib 后端不可用（需要安装 joblib）")

    results = {}

    for backend in backends:
        print(f"\n测试 {backend} 后端...")

        try:
            evaluator = ParallelEvaluator(
                backend=backend,
                max_workers=4,
                verbose=False
            )

            # 预热
            evaluator.evaluate_population(population[:5], problem)

            # 正式测试
            start_time = time.time()
            objectives, violations = evaluator.evaluate_population(population, problem)
            end_time = time.time()

            results[backend] = {
                'time': end_time - start_time,
                'stats': evaluator.get_stats()
            }

            print(f"   时间: {results[backend]['time']:.3f}秒")
            print(f"   成功率: {results[backend]['stats']['total_evaluations']/pop_size*100:.1f}%")

        except Exception as e:
            print(f"   错误: {e}")
            continue

    # 性能对比
    if len(results) > 1:
        print(f"\n性能对比:")
        fastest = min(results.keys(), key=lambda k: results[k]['time'])
        fastest_time = results[fastest]['time']

        for backend, result in results.items():
            speedup = fastest_time / result['time'] if result['time'] > 0 else 0
            status = " (最快)" if backend == fastest else ""
            print(f"   {backend}: {result['time']:.3f}秒, 相对性能: {speedup:.2f}x{status}")

    return results


# ==================== 优化示例 ====================
def optimize_expensive_function_example():
    """优化昂贵函数的完整示例"""

    print("\n" + "="*60)
    print("昂贵函数优化示例")
    print("="*60)

    # 创建昂贵问题
    problem = ExpensiveEngineeringProblem(dimension=5, simulation_time=0.05)

    print(f"\n问题: {problem.name}")
    print(f"维度: {problem.dimension}")
    print(f"预计单次评估时间: {problem.simulation_time*1000:.0f}ms")

    # 串行优化
    print("\n1. 串行优化...")
    solver_serial = BlackBoxSolverNSGAII(problem)
    solver_serial.pop_size = 30
    solver_serial.max_generations = 20
    solver_serial.enable_progress_log = True

    start_time = time.time()
    result_serial = solver_serial.run()
    serial_time = time.time() - start_time

    print(f"\n串行优化完成:")
    print(f"   总时间: {serial_time:.2f}秒")
    print(f"   找到 {len(result_serial['pareto_solutions']['objectives'])} 个解")

    # 并行优化
    print("\n2. 并行优化...")
    solver_parallel = BlackBoxSolverNSGAII(problem)
    solver_parallel.pop_size = 30
    solver_parallel.max_generations = 20
    solver_parallel.enable_progress_log = True

    # 启用并行评估
    solver_parallel.enable_parallel(
        backend="thread",
        max_workers=4,
        auto_configure=True
    )

    start_time = time.time()
    result_parallel = solver_parallel.run()
    parallel_time = time.time() - start_time

    print(f"\n并行优化完成:")
    print(f"   总时间: {parallel_time:.2f}秒")
    print(f"   找到 {len(result_parallel['pareto_solutions']['objectives'])} 个解")

    # 性能对比
    speedup = serial_time / parallel_time if parallel_time > 0 else 0
    print(f"\n性能提升:")
    print(f"   加速比: {speedup:.2f}x")
    print(f"   时间节省: {serial_time - parallel_time:.2f}秒 ({(1-parallel_time/serial_time)*100:.1f}%)")

    # 并行统计
    parallel_stats = solver_parallel.get_parallel_stats()
    if parallel_stats:
        print(f"\n并行评估统计:")
        print(f"   总评估次数: {parallel_stats.get('total_evaluations', 'N/A')}")
        print(f"   平均评估时间: {parallel_stats.get('avg_evaluation_time', 0)*1000:.2f}ms")


def single_objective_expensive_example():
    """单目标昂贵函数优化示例"""

    print("\n" + "="*60)
    print("单目标昂贵函数优化")
    print("="*60)

    # 定义昂贵函数
    def expensive_objective(x):
        """模拟需要2秒计算的昂贵函数"""
        time.sleep(0.02)  # 模拟计算时间

        # Rastrigin函数（多模态优化基准）
        n = len(x)
        A = 10
        return A * n + np.sum(x**2 - A * np.cos(2 * np.pi * x))

    # 变量边界
    bounds = [(-5.12, 5.12) for _ in range(6)]

    print(f"\n优化问题: 6维Rastrigin函数")
    print(f"全局最优: f(0,0,0,0,0,0) = 0")
    print(f"预计单次评估时间: 20ms")

    # 串行优化
    print("\n1. 串行优化...")
    start_time = time.time()
    result_serial = run_headless_single_objective(
        expensive_objective,
        bounds,
        pop_size=40,
        max_generations=30,
        enable_parallel=False,
        show_progress=True
    )
    serial_time = time.time() - start_time

    print(f"\n串行结果:")
    print(f"   最优解: {result_serial['best_x']}")
    print(f"   最优值: {result_serial['best_f']:.6f}")
    print(f"   总时间: {serial_time:.2f}秒")

    # 并行优化
    print("\n2. 并行优化...")
    start_time = time.time()
    result_parallel = run_headless_single_objective(
        expensive_objective,
        bounds,
        pop_size=40,
        max_generations=30,
        enable_parallel=True,
        parallel_backend="thread",
        max_workers=4,
        show_progress=True
    )
    parallel_time = time.time() - start_time

    print(f"\n并行结果:")
    print(f"   最优解: {result_parallel['best_x']}")
    print(f"   最优值: {result_parallel['best_f']:.6f}")
    print(f"   总时间: {parallel_time:.2f}秒")

    # 性能对比
    speedup = serial_time / parallel_time if parallel_time > 0 else 0
    print(f"\n性能对比:")
    print(f"   加速比: {speedup:.2f}x")
    print(f"   时间节省: {(serial_time - parallel_time):.2f}秒")


# ==================== 主程序 ====================
def main():
    """主程序"""
    print("昂贵函数并行评估示例")
    print("演示如何使用并行评估加速昂贵的优化过程")
    print("="*60)

    # 示例1: 性能基准测试
    print("\n\n示例1: 性能基准测试")
    print("-"*40)

    # 测试不同类型的问题
    problems = [
        ExpensiveEngineeringProblem(dimension=5, simulation_time=0.01),
        CADOptimizationProblem(dimension=6, cad_time=0.01),
        MachineLearningModelOptimization(dimension=5, training_time=0.01)
    ]

    for problem in problems:
        benchmark_serial_vs_parallel(problem, pop_size=40, max_workers=4)

        # 测试不同后端
        test_different_backends(problem, pop_size=20)

    # 示例2: 完整优化示例
    print("\n\n示例2: 完整优化示例")
    print("-"*40)
    optimize_expensive_function_example()

    # 示例3: 单目标优化
    print("\n\n示例3: 单目标昂贵函数优化")
    print("-"*40)
    single_objective_expensive_example()

    # 总结
    print("\n" + "="*60)
    print("总结")
    print("="*60)
    print("\n使用建议:")
    print("1. 对于评估时间 > 10ms 的函数，建议使用并行评估")
    print("2. Windows平台优先使用 'thread' 后端")
    print("3. Linux/macOS可以使用 'process' 后端获得更好性能")
    print("4. 种群规模 > 30 时，并行效果更明显")
    print("5. 使用 SmartEvaluatorSelector 自动选择最佳配置")

    print("\n性能提升预期:")
    print("- 种群规模 50: 2-3倍加速")
    print("- 种群规模 100: 3-4倍加速")
    print("- 种群规模 200: 4-5倍加速")

    print("\n示例程序运行完成！")


if __name__ == "__main__":
    main()