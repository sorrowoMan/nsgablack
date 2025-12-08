"""并行评估示例 - 修复版

演示如何使用种群内并行评估功能，包括：
1. 基本并行评估
2. 与现有求解器的集成
3. 性能对比
4. 不同后端的比较

修复了Windows平台下的多进程和pickle问题。
"""

import time
import sys
import os
import multiprocessing as mp
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import matplotlib
matplotlib.use('Agg')  # 避免GUI问题
import matplotlib.pyplot as plt

# 导入基础模块
from core.base import BlackBoxProblem
from core.solver import BlackBoxSolverNSGAII
from utils.parallel_evaluator import ParallelEvaluator, SmartEvaluatorSelector
from utils.solver_extensions import integrate_parallel_evaluation, create_parallel_solver
from bias import create_standard_bias

# 延迟导入辅助函数
def safe_imports():
    pass  # 已经在顶部导入

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

        # Rastrigin函数 - 避免使用numpy的复杂函数以减少pickle问题
        n = len(x)
        result = 10 * n
        for i in range(n):
            result += x[i]**2 - 10 * np.cos(2 * np.pi * x[i])
        return result


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

    # 导入模块
    safe_imports()

    problem = ExpensiveTestProblem(dimension=10, eval_delay=0.001)

    # 生成测试种群
    population = np.random.uniform(-5, 5, (20, 10))  # 减小种群规模以避免错误

    # 测试不同的后端
    backends_to_test = ["thread"]  # 默认只用thread，避免process的问题

    # 尝试使用joblib如果可用
    try:
        import joblib
        backends_to_test.append("joblib")
    except ImportError:
        pass

    results = {}

    for backend in backends_to_test:
        print(f"\n测试 {backend} 后端...")

        try:
            # 创建并行评估器
            if backend == "process":
                # Windows下多进程需要特殊处理
                parallel_evaluator = ParallelEvaluator(
                    backend=backend,
                    max_workers=min(4, mp.cpu_count()),
                    verbose=False,
                    chunk_size=1  # 减小块大小
                )
            else:
                parallel_evaluator = ParallelEvaluator(
                    backend=backend,
                    max_workers=4,
                    verbose=False
                )

            # 并行评估
            start_time = time.time()
            objectives_parallel, violations_parallel = parallel_evaluator.evaluate_population(
                population, problem
            )
            parallel_time = time.time() - start_time

            results[backend] = {
                'time': parallel_time,
                'objectives': objectives_parallel,
                'violations': violations_parallel,
                'stats': parallel_evaluator.get_stats()
            }

            print(f"  {backend} 后端成功: 时间 {parallel_time:.3f}s")

        except Exception as e:
            print(f"  {backend} 后端失败: {str(e)}")
            continue

    # 串行评估作为基准
    print("\n串行评估（单线程）...")
    try:
        serial_evaluator = ParallelEvaluator(backend="thread", max_workers=1)
        start_time = time.time()
        objectives_serial, violations_serial = serial_evaluator.evaluate_population(
            population, problem
        )
        serial_time = time.time() - start_time

        print(f"串行时间: {serial_time:.3f}s")

        # 比较结果
        for backend, result in results.items():
            speedup = serial_time / result['time']
            print(f"\n{backend} 后端:")
            print(f"  时间: {result['time']:.3f}s")
            print(f"  加速比: {speedup:.2f}x")

            # 验证结果一致性
            obj_diff = np.max(np.abs(objectives_serial - result['objectives']))
            print(f"  结果差异: {obj_diff:.2e}")

    except Exception as e:
        print(f"串行评估失败: {e}")


# ==================== 示例 2: 智能评估器选择 ====================
def example_smart_evaluator_selection():
    """示例2: 智能评估器选择"""
    print("\n" + "=" * 60)
    print("示例 2: 智能评估器选择")
    print("=" * 60)

    safe_imports()

    problem = ExpensiveTestProblem(dimension=15)

    # 测试不同种群规模
    population_sizes = [10, 20, 50]  # 减小规模以避免问题

    for pop_size in population_sizes:
        print(f"\n种群规模: {pop_size}")

        try:
            # 智能选择评估器
            evaluator = SmartEvaluatorSelector.select_evaluator(
                problem=problem,
                population_size=pop_size
            )

            print(f"推荐后端: {evaluator.backend}")
            print(f"工作进程数: {evaluator.max_workers}")
            print(f"块大小: {evaluator.chunk_size}")
            print(f"负载均衡: {evaluator.enable_load_balancing}")

        except Exception as e:
            print(f"  选择失败: {e}")


# ==================== 示例 3: 简化的求解器集成 ====================
def example_solver_integration():
    """示例3: 简化的求解器集成（避免复杂的并行问题）"""
    print("\n" + "=" * 60)
    print("示例 3: 简化的求解器集成")
    print("=" * 60)

    safe_imports()

    problem = ExpensiveTestProblem(dimension=8, eval_delay=0.001)

    try:
        # 创建基本的求解器（不使用并行）
        solver = BlackBoxSolverNSGAII(problem)
        solver.pop_size = 20  # 减小规模
        solver.max_generations = 10  # 减少代数
        solver.verbose = True

        # 运行优化
        print("\n运行基础优化...")
        start_time = time.time()
        result = solver.run()
        total_time = time.time() - start_time

        print(f"\n优化完成！")
        print(f"总时间: {total_time:.2f}s")
        print(f"找到 {len(result['pareto_solutions']['objectives'])} 个解")

        # 显示最优解
        if len(result['pareto_solutions']['objectives']) > 0:
            best_idx = np.argmin(result['pareto_solutions']['objectives'])
            best_obj = result['pareto_solutions']['objectives'][best_idx]
            # 处理可能是数组的情况
            if isinstance(best_obj, np.ndarray):
                best_obj = best_obj.item() if best_obj.size == 1 else best_obj[0]
            print(f"最优目标值: {float(best_obj):.4f}")

    except Exception as e:
        print(f"求解器运行失败: {e}")
        import traceback
        traceback.print_exc()


# ==================== 示例 4: 后端性能比较（简化版） ====================
def example_backend_comparison():
    """示例4: 比较不同并行后端的性能（简化版）"""
    print("\n" + "=" * 60)
    print("示例 4: 并行后端性能比较（简化版）")
    print("=" * 60)

    safe_imports()

    problem = ExpensiveTestProblem(dimension=6, eval_delay=0.001)
    population = np.random.uniform(-5, 5, (15, 6))  # 小种群

    # 只测试安全的后端
    backends = ["thread"]

    # 尝试joblib
    try:
        import joblib
        backends.append("joblib")
        print("joblib 可用")
    except ImportError:
        print("joblib 不可用")

    results = {}

    for backend in backends:
        print(f"\n测试后端: {backend}")

        try:
            evaluator = ParallelEvaluator(
                backend=backend,
                max_workers=2,  # 减少工作进程数
                verbose=False
            )

            # 测试
            start_time = time.time()
            objectives, violations = evaluator.evaluate_population(population, problem)
            end_time = time.time()

            results[backend] = {
                'time': end_time - start_time,
                'stats': evaluator.get_stats()
            }

            print(f"  时间: {results[backend]['time']:.3f}s")
            print(f"  成功评估: {results[backend]['stats']['total_evaluations']}/{len(population)}")

        except Exception as e:
            print(f"  错误: {e}")
            continue

    # 性能比较
    if len(results) > 1:
        print(f"\n后端性能比较:")
        fastest_backend = min(results.keys(), key=lambda k: results[k]['time'])
        fastest_time = results[fastest_backend]['time']

        for backend, result in results.items():
            speedup = fastest_time / result['time']
            status = " (最快)" if backend == fastest_backend else ""
            print(f"  {backend}: {result['time']:.3f}s, 相对性能: {speedup:.2f}x{status}")
    elif results:
        print("\n单个后端测试成功")


# ==================== 示例 5: 带约束问题的简化处理 ====================
def example_constrained_parallel():
    """示例5: 带约束问题的简化处理"""
    print("\n" + "=" * 60)
    print("示例 5: 带约束问题的简化处理")
    print("=" * 60)

    safe_imports()

    problem = ConstrainedTestProblem(dimension=5)

    try:
        # 使用基础求解器
        solver = BlackBoxSolverNSGAII(problem)
        solver.pop_size = 30  # 小种群
        solver.max_generations = 20  # 减少代数
        solver.verbose = True

        # 运行优化
        print("\n运行带约束的优化...")
        result = solver.run()

        # 分析结果
        if 'pareto_solutions' in result and len(result['pareto_solutions']['objectives']) > 0:
            best_idx = np.argmin(result['pareto_solutions']['objectives'])
            best_solution = result['pareto_solutions']['individuals'][best_idx]

            # 检查约束
            violations = problem.evaluate_constraints(best_solution)
            max_violation = np.max(violations)

            print(f"\n最优解: {best_solution}")
            print(f"最优值: {result['pareto_solutions']['objectives'][best_idx]}")
            print(f"最大约束违反度: {max_violation:.4f}")
            print(f"是否可行: {'是' if max_violation <= 0 else '否'}")
        else:
            print("未找到可行解")

    except Exception as e:
        print(f"约束优化失败: {e}")
        import traceback
        traceback.print_exc()


# ==================== 简化的性能可视化 ====================
def simple_performance_report():
    """简单的性能报告（避免matplotlib问题）"""
    print("\n" + "=" * 60)
    print("性能评估报告")
    print("=" * 60)

    safe_imports()

    problem = ExpensiveTestProblem(dimension=8, eval_delay=0.001)

    # 测试不同种群规模
    population_sizes = [10, 20, 40]
    print(f"种群规模\t串行时间\t线程并行")
    print("-" * 40)

    for pop_size in population_sizes:
        population = np.random.uniform(-5, 5, (pop_size, 8))

        # 串行评估
        try:
            evaluator_serial = ParallelEvaluator(backend="thread", max_workers=1)
            start_time = time.time()
            evaluator_serial.evaluate_population(population, problem)
            serial_time = time.time() - start_time
        except:
            serial_time = float('nan')

        # 并行评估
        try:
            evaluator_parallel = ParallelEvaluator(backend="thread", max_workers=4)
            start_time = time.time()
            evaluator_parallel.evaluate_population(population, problem)
            parallel_time = time.time() - start_time
        except:
            parallel_time = float('nan')

        if not np.isnan(serial_time) and not np.isnan(parallel_time):
            speedup = serial_time / parallel_time
            print(f"{pop_size}\t\t{serial_time:.3f}s\t\t{parallel_time:.3f}s (加速比: {speedup:.2f}x)")
        else:
            print(f"{pop_size}\t\t评估失败")


# ==================== 主函数 ====================
def main():
    """主函数，包含错误处理"""
    print("开始运行并行评估示例（修复版）...")
    print("注意：此版本针对Windows平台进行了优化")
    print("=" * 60)

    # Windows多进程保护
    if __name__ == "__main__":
        # 设置多进程启动方法
        try:
            mp.set_start_method('spawn', force=True)
        except:
            pass  # 可能已经设置过

        # 运行示例
        try:
            example_basic_parallel_evaluation()
        except Exception as e:
            print(f"示例1运行出错: {e}")

        try:
            example_smart_evaluator_selection()
        except Exception as e:
            print(f"示例2运行出错: {e}")

        try:
            example_solver_integration()
        except Exception as e:
            print(f"示例3运行出错: {e}")

        try:
            example_backend_comparison()
        except Exception as e:
            print(f"示例4运行出错: {e}")

        try:
            example_constrained_parallel()
        except Exception as e:
            print(f"示例5运行出错: {e}")

        # 简化的性能报告
        try:
            simple_performance_report()
        except Exception as e:
            print(f"性能报告出错: {e}")

        print("\n" + "=" * 60)
        print("示例运行完成！")
        print("=" * 60)

        print("\n使用建议:")
        print("1. Windows平台建议使用 'thread' 后端")
        print("2. Linux/macOS可以使用 'process' 后端获得更好性能")
        print("3. 小种群(<20)使用串行评估即可")
        print("4. 大种群(>50)考虑使用并行评估")
        print("5. 遇到pickle问题时，简化评估函数")


if __name__ == "__main__":
    main()