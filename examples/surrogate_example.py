"""代理模型辅助优化示例

演示如何使用代理模型减少昂贵函数的评估次数
"""
import numpy as np
import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.base import BlackBoxProblem
from solvers.surrogate import SurrogateAssistedNSGAII, run_surrogate_assisted
from core.solver import BlackBoxSolverNSGAII


class ExpensiveBlackBox(BlackBoxProblem):
    """模拟昂贵的黑箱函数（每次评估耗时 0.1 秒）"""

    def __init__(self, dimension=5):
        super().__init__(name="昂贵仿真", dimension=dimension)
        self.eval_count = 0

    def evaluate(self, x):
        # 模拟昂贵计算
        time.sleep(0.1)
        self.eval_count += 1

        # Rosenbrock 函数
        x = np.asarray(x)
        result = np.sum(100 * (x[1:] - x[:-1]**2)**2 + (1 - x[:-1])**2)
        return result

    def get_num_objectives(self):
        return 1


class ExpensiveMultiObjective(BlackBoxProblem):
    """昂贵的多目标问题（ZDT1 变体）"""

    def __init__(self, dimension=10):
        super().__init__(name="昂贵多目标", dimension=dimension)
        bounds = {f'x{i}': [0, 1] for i in range(dimension)}
        self.bounds = bounds
        self.eval_count = 0

    def evaluate(self, x):
        time.sleep(0.1)
        self.eval_count += 1

        x = np.asarray(x)
        f1 = x[0]
        g = 1 + 9 * np.sum(x[1:]) / (self.dimension - 1)
        f2 = g * (1 - np.sqrt(f1 / g))
        return np.array([f1, f2])

    def get_num_objectives(self):
        return 2


def example_single_objective():
    """示例1：单目标昂贵优化"""
    print("=" * 60)
    print("示例1：单目标昂贵优化（Rosenbrock 函数）")
    print("=" * 60)

    problem = ExpensiveBlackBox(dimension=5)

    # 方法1：标准 NSGA-II（作为对比）
    print("\n[标准 NSGA-II]")
    problem.eval_count = 0
    start = time.time()

    solver_standard = BlackBoxSolverNSGAII(problem)
    solver_standard.pop_size = 40
    solver_standard.max_generations = 50
    solver_standard.enable_progress_log = True
    solver_standard.report_interval = 5
    print(f"开始运行标准 NSGA-II (预计耗时约 {solver_standard.pop_size * solver_standard.max_generations * 0.1:.1f} 秒)...")
    solver_standard.run()

    time_standard = time.time() - start
    evals_standard = problem.eval_count

    print(f"评估次数: {evals_standard}")
    print(f"耗时: {time_standard:.1f} 秒")
    print(f"最优解: {float(solver_standard.pareto_objectives[0]):.6f}")

    # 方法2：代理模型辅助
    print("\n[代理模型辅助 NSGA-II (GP)]")
    problem = ExpensiveBlackBox(dimension=5)  # 重新创建
    start = time.time()

    result = run_surrogate_assisted(
        problem,
        surrogate_type='gp',
        real_eval_budget=200,  # 限制真实评估次数
        initial_samples=30,
        pop_size=40,
        max_generations=50
    )

    time_surrogate = time.time() - start

    print(f"真实评估次数: {result['real_eval_count']}")
    print(f"耗时: {time_surrogate:.1f} 秒")
    print(f"最优解: {float(result['pareto_objectives'][0]):.6f}")

    # 对比
    print("\n[对比]")
    print(f"评估次数减少: {(1 - result['real_eval_count']/evals_standard)*100:.1f}%")
    print(f"时间节省: {(1 - time_surrogate/time_standard)*100:.1f}%")


def example_multi_objective():
    """示例2：多目标昂贵优化"""
    print("\n" + "=" * 60)
    print("示例2：多目标昂贵优化（ZDT1 变体）")
    print("=" * 60)

    problem = ExpensiveMultiObjective(dimension=10)

    print("\n[代理模型辅助 NSGA-II (RF)]")
    start = time.time()

    solver = SurrogateAssistedNSGAII(problem, surrogate_type='rf')
    solver.real_eval_budget = 300
    solver.initial_samples = 50
    solver.pop_size = 60
    solver.max_generations = 100
    solver.update_interval = 5
    solver.real_evals_per_gen = 3

    result = solver.run()

    elapsed = time.time() - start

    print(f"\n真实评估次数: {result['real_eval_count']}")
    print(f"耗时: {elapsed:.1f} 秒")
    print(f"找到 Pareto 解数量: {len(result['pareto_solutions'])}")
    print(f"Pareto 前沿示例（前5个）:")
    for i, obj in enumerate(result['pareto_objectives'][:5]):
        print(f"  解 {i+1}: f1={obj[0]:.4f}, f2={obj[1]:.4f}")


def example_compare_surrogates():
    """示例3：对比不同代理模型"""
    print("\n" + "=" * 60)
    print("示例3：对比不同代理模型类型")
    print("=" * 60)

    for surrogate_type in ['gp', 'rbf', 'rf']:
        print(f"\n[{surrogate_type.upper()}]")
        problem = ExpensiveBlackBox(dimension=5)

        start = time.time()
        result = run_surrogate_assisted(
            problem,
            surrogate_type=surrogate_type,
            real_eval_budget=150,
            initial_samples=30,
            pop_size=40,
            max_generations=50
        )
        elapsed = time.time() - start

        print(f"  真实评估: {result['real_eval_count']}")
        print(f"  耗时: {elapsed:.1f} 秒")
        print(f"  最优解: {float(result['pareto_objectives'][0]):.6f}")


if __name__ == '__main__':
    # 运行示例
    example_single_objective()
    example_multi_objective()
    example_compare_surrogates()
