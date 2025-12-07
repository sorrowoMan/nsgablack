"""并行评估示例

演示如何使用种群内并行评估功能，包括：
1. 基本并行评估
2. 与现有求解器的集成
3. 性能对比
4. 不同后端的比较
"""

import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import matplotlib.pyplot as plt
from core.base import BlackBoxProblem
from core.solver import BlackBoxSolverNSGAII
from utils.parallel_evaluator import ParallelEvaluator, SmartEvaluatorSelector
from utils.solver_extensions import integrate_parallel_evaluation, create_parallel_solver
from utils.bias import create_standard_bias


# ==================== 测试问题 ====================
class ExpensiveTestProblem(BlackBoxProblem):
    """模拟昂贵的评估函数"""

    def __init__(self, dimension=10, eval_delay=0.01):
        super().__init__(
            name="昂贵测试问题",
            dimension=dimension,
            bounds={f'x{i}': (-5, 5) for i in range(dimension)}
        )
        self.eval_delay = eval_delay  # 模拟评估延迟

    def evaluate(self, x):
        # 模拟昂贵的计算
        time.sleep(self.eval_delay)

        # Rastrigin函数
        n = len(x)
        return 10 * n + np.sum(x**2 - 10 * np.cos(2 * np.pi * x))


class ConstrainedTestProblem(BlackBoxProblem):
    """带约束的测试问题"""

    def __init__(self, dimension=5):
        super().__init__(
            name="约束测试问题",
            dimension=dimension,
            bounds={f'x{i}': (-2, 2) for i in range(dimension)}
        )

    def evaluate(self, x):
        # 目标函数：最小化距离原点的距离
        return np.sum(x**2)

    def evaluate_constraints(self, x):
        # 约束：x[0] + x[1] >= 1
        # 转换为 g(x) <= 0 形式：1 - x[0] - x[1] <= 0
        constraints = []

        # 线性约束
        constraints.append(1 - x[0] - x[1])

        # 非线性约束
        constraints.append(0.25 - x[2]**2 - x[3]**2)  # 在圆内

        return np.array(constraints)


# ==================== 示例 1: 基本并行评估 ====================
def example_basic_parallel_evaluation():
    """示例1: 基本的并行评估功能"""
    print("=" * 60)
    print("示例 1: 基本并行评估")
    print("=" * 60)

    problem = ExpensiveTestProblem(dimension=10, eval_delay=0.001)

    # 生成测试种群
    population = np.random.uniform(-5, 5, (50, 10))

    # 创建并行评估器
    parallel_evaluator = ParallelEvaluator(
        backend="process",
        max_workers=4,
        verbose=True
    )

    # 串行评估
    print("\n串行评估...")
    start_time = time.time()
    with ParallelEvaluator(backend="thread") as serial_evaluator:
        # 使用单线程模拟串行
        objectives_serial, violations_serial = serial_evaluator.evaluate_population(
            population, problem
        )
    serial_time = time.time() - start_time

    # 并行评估
    print("\n并行评估...")
    start_time = time.time()
    objectives_parallel, violations_parallel = parallel_evaluator.evaluate_population(
        population, problem
    )
    parallel_time = time.time() - start_time

    # 比较结果
    speedup = serial_time / parallel_time
    print(f"\n结果比较:")
    print(f"串行时间: {serial_time:.3f}s")
    print(f"并行时间: {parallel_time:.3f}s")
    print(f"加速比: {speedup:.2f}x")

    # 验证结果一致性
    obj_diff = np.max(np.abs(objectives_serial - objectives_parallel))
    vio_diff = np.max(np.abs(violations_serial - violations_parallel))
    print(f"结果差异 (目标值): {obj_diff:.2e}")
    print(f"结果差异 (约束): {vio_diff:.2e}")

    # 获取统计信息
    stats = parallel_evaluator.get_stats()
    print(f"评估统计: {stats}")


# ==================== 示例 2: 智能评估器选择 ====================
def example_smart_evaluator_selection():
    """示例2: 智能评估器选择"""
    print("\n" + "=" * 60)
    print("示例 2: 智能评估器选择")
    print("=" * 60)

    problem = ExpensiveTestProblem(dimension=15)

    # 测试不同种群规模
    population_sizes = [10, 50, 100]

    for pop_size in population_sizes:
        print(f"\n种群规模: {pop_size}")

        # 智能选择评估器
        evaluator = SmartEvaluatorSelector.select_evaluator(
            problem=problem,
            population_size=pop_size
        )

        print(f"推荐后端: {evaluator.backend}")
        print(f"工作进程数: {evaluator.max_workers}")
        print(f"块大小: {evaluator.chunk_size}")
        print(f"负载均衡: {evaluator.enable_load_balancing}")


# ==================== 示例 3: 集成到现有求解器 ====================
def example_solver_integration():
    """示例3: 将并行评估集成到现有求解器"""
    print("\n" + "=" * 60)
    print("示例 3: 求解器集成")
    print("=" * 60)

    problem = ExpensiveTestProblem(dimension=8, eval_delay=0.001)

    # 创建增强的求解器
    EnhancedNSGAII = integrate_parallel_evaluation(BlackBoxSolverNSGAII)

    # 创建求解器实例
    solver = EnhancedNSGAII(problem)
    solver.pop_size = 40
    solver.max_generations = 30
    solver.verbose = True

    # 启用并行评估
    solver.enable_parallel(
        backend="process",
        max_workers=4,
        auto_configure=True
    )

    # 运行优化
    print("\n运行并行优化...")
    result_parallel = solver.run()

    # 禁用并行，运行串行优化
    solver.disable_parallel()

    print("\n运行串行优化...")
    result_serial = solver.run()

    # 比较结果
    print(f"\n性能比较:")
    if 'total_time' in result_parallel and 'total_time' in result_serial:
        speedup = result_serial['total_time'] / result_parallel['total_time']
        print(f"串行时间: {result_serial['total_time']:.2f}s")
        print(f"并行时间: {result_parallel['total_time']:.2f}s")
        print(f"加速比: {speedup:.2f}x")

    # 输出并行统计
    parallel_stats = solver.get_parallel_stats()
    if parallel_stats:
        print(f"\n并行评估统计:")
        print(f"  总评估次数: {parallel_stats['total_evaluations']}")
        print(f"  平均评估时间: {parallel_stats['avg_evaluation_time']*1000:.2f}ms")
        if parallel_stats['error_count'] > 0:
            print(f"  错误次数: {parallel_stats['error_count']}")


# ==================== 示例 4: 不同后端比较 ====================
def example_backend_comparison():
    """示例4: 比较不同并行后端的性能"""
    print("\n" + "=" * 60)
    print("示例 4: 并行后端性能比较")
    print("=" * 60)

    problem = ExpensiveTestProblem(dimension=6, eval_delay=0.002)
    population = np.random.uniform(-5, 5, (30, 6))

    # 测试不同后端
    backends = ["thread", "process"]
    if True:  # 检查是否有joblib
        try:
            import joblib
            backends.append("joblib")
        except ImportError:
            pass

    results = {}

    for backend in backends:
        print(f"\n测试后端: {backend}")

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

            print(f"  时间: {results[backend]['time']:.3f}s")
            print(f"  成功率: {results[backend]['stats']['total_evaluations'] / len(population):.2%}")

        except Exception as e:
            print(f"  错误: {e}")
            continue

    # 性能比较
    if results:
        print(f"\n后端性能比较:")
        fastest_backend = min(results.keys(), key=lambda k: results[k]['time'])
        fastest_time = results[fastest_backend]['time']

        for backend, result in results.items():
            speedup = fastest_time / result['time']
            status = " (最快)" if backend == fastest_backend else ""
            print(f"  {backend}: {result['time']:.3f}s, 加速比: {speedup:.2f}x{status}")


# ==================== 示例 5: 带约束问题的并行评估 ====================
def example_constrained_parallel():
    """示例5: 带约束问题的并行评估"""
    print("\n" + "=" * 60)
    print("示例 5: 带约束问题的并行评估")
    print("=" * 60)

    problem = ConstrainedTestProblem(dimension=5)

    # 创建带偏置的求解器
    solver = create_parallel_solver(
        solver_class=BlackBoxSolverNSGAII,
        problem=problem,
        enable_parallel=True,
        parallel_backend="process",
        max_workers=3,
        pop_size=50,
        max_generations=40,
        verbose=True
    )

    # 启用约束处理偏置
    solver.enable_bias = True
    solver.bias_module = create_standard_bias(
        problem,
        reward_weight=0.02,
        penalty_weight=5.0
    )

    # 运行优化
    print("\n运行带约束的并行优化...")
    result = solver.run()

    # 分析结果
    best_idx = np.argmin(result['pareto_solutions']['objectives'])
    best_solution = result['pareto_solutions']['individuals'][best_idx]
    best_violation = result['pareto_solutions']['constraint_violations'][best_idx]

    print(f"\n最优解: {best_solution}")
    print(f"最优值: {result['pareto_solutions']['objectives'][best_idx]}")
    print(f"约束违反度: {best_violation}")
    print(f"是否可行: {'是' if best_violation < 1e-6 else '否'}")

    # 性能统计
    if 'performance' in result:
        perf = result['performance']
        print(f"\n性能统计:")
        print(f"  总评估次数: {perf['total_evaluations']}")
        print(f"  平均评估时间: {perf.get('avg_evaluation_time', 0)*1000:.2f}ms")


# ==================== 性能可视化 ====================
def visualize_performance_comparison():
    """可视化性能比较"""
    print("\n" + "=" * 60)
    print("性能比较可视化")
    print("=" * 60)

    problem = ExpensiveTestProblem(dimension=10, eval_delay=0.001)

    # 测试不同种群规模
    population_sizes = [10, 20, 40, 80, 160]
    serial_times = []
    parallel_times = []

    for pop_size in population_sizes:
        population = np.random.uniform(-5, 5, (pop_size, 10))

        # 串行评估
        evaluator_serial = ParallelEvaluator(backend="thread", max_workers=1)
        start_time = time.time()
        evaluator_serial.evaluate_population(population, problem)
        serial_times.append(time.time() - start_time)

        # 并行评估
        evaluator_parallel = ParallelEvaluator(backend="process", max_workers=4)
        start_time = time.time()
        evaluator_parallel.evaluate_population(population, problem)
        parallel_times.append(time.time() - start_time)

        print(f"种群规模 {pop_size:3d}: 串行 {serial_times[-1]:.3f}s, 并行 {parallel_times[-1]:.3f}s")

    # 计算加速比
    speedups = [s/p for s, p in zip(serial_times, parallel_times)]

    # 绘制图表
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # 时间比较
    ax1.plot(population_sizes, serial_times, 'o-', label='串行', linewidth=2)
    ax1.plot(population_sizes, parallel_times, 's-', label='并行 (4进程)', linewidth=2)
    ax1.set_xlabel('种群规模')
    ax1.set_ylabel('评估时间 (s)')
    ax1.set_title('评估时间比较')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # 加速比
    ax2.plot(population_sizes, speedups, '^-', label='实际加速比', linewidth=2, color='red')
    ax2.axhline(y=4, color='green', linestyle='--', label='理论最大加速比')
    ax2.set_xlabel('种群规模')
    ax2.set_ylabel('加速比')
    ax2.set_title('并行加速比')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('parallel_performance_comparison.png', dpi=150, bbox_inches='tight')
    plt.show()

    print(f"\n可视化结果已保存为 'parallel_performance_comparison.png'")


# ==================== 主函数 ====================
if __name__ == "__main__":
    # 运行所有示例
    example_basic_parallel_evaluation()
    example_smart_evaluator_selection()
    example_solver_integration()
    example_backend_comparison()
    example_constrained_parallel()

    # 性能可视化
    try:
        visualize_performance_comparison()
    except Exception as e:
        print(f"可视化失败: {e}")

    print("\n" + "=" * 60)
    print("所有示例运行完成！")
    print("=" * 60)

    print("\n使用建议:")
    print("1. 种群规模 > 20 时建议启用并行评估")
    print("2. CPU密集型问题使用 'process' 后端")
    print("3. I/O密集型问题使用 'thread' 后端")
    print("4. 大种群问题使用 'joblib' 后端（更好的内存管理）")
    print("5. 使用 SmartEvaluatorSelector 自动选择最佳配置")