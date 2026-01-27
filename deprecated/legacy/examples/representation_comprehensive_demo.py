"""
Representation Pipeline 综合示例

展示如何使用 Representation Pipeline 处理不同类型的优化问题：
1. 整数优化 - 直接在整数空间初始化和搜索
2. 矩阵优化 - 带行列和约束的整数矩阵
3. 二进制优化 - 背包问题
4. 排列优化 - TSP 问题（随机键编码）
5. 连续优化 - 带边界的连续优化
"""

import os
import sys
import numpy as np

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.base import BlackBoxProblem
from core.solver import BlackBoxSolverNSGAII
from utils.representation import RepresentationPipeline
from utils.representation.integer import IntegerInitializer, IntegerMutation
from utils.representation.matrix import IntegerMatrixInitializer, MatrixRowColSumRepair
from utils.representation.binary import BinaryInitializer, BitFlipMutation, BinaryCapacityRepair
from utils.representation.permutation import (
    RandomKeyInitializer,
    RandomKeyMutation,
    RandomKeyPermutationDecoder,
    PermutationInitializer,
    PermutationSwapMutation,
)
from utils.representation.continuous import UniformInitializer, GaussianMutation, ClipRepair


# ============================================================================
# 示例 1: 整数优化
# ============================================================================
class IntegerAllocationProblem(BlackBoxProblem):
    """
    整数分配问题：将资源分配给不同项目

    目标：最小化成本，最大化收益
    约束：每个项目的资源量为整数
    """

    def __init__(self, n_projects=5, max_per_project=10):
        self.n_projects = n_projects
        self.costs = np.random.uniform(1, 5, n_projects)
        self.revenues = np.random.uniform(10, 20, n_projects)

        bounds = {f"project_{i}": [0, max_per_project] for i in range(n_projects)}
        super().__init__(
            name="IntegerAllocation",
            dimension=n_projects,
            bounds=bounds
        )

    def evaluate(self, x):
        x = np.asarray(x, dtype=int)

        # 目标 1: 最小化成本
        total_cost = np.sum(x * self.costs)

        # 目标 2: 最大化收益（取负值以最小化）
        total_revenue = np.sum(x * self.revenues)

        return [total_cost, -total_revenue]


def demo_integer_optimization():
    """演示整数优化"""
    print("\n" + "=" * 60)
    print("示例 1: 整数优化 - 资源分配问题")
    print("=" * 60)

    problem = IntegerAllocationProblem(n_projects=5, max_per_project=10)

    # 使用整数表示管道 - 直接在整数空间初始化
    pipeline = RepresentationPipeline(
        initializer=IntegerInitializer(low=0, high=3),  # 从小范围开始，效率高
        mutator=IntegerMutation(sigma=1.0, low=0, high=10),
    )

    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 50
    solver.max_generations = 80
    solver.set_representation_pipeline(pipeline)

    result = solver.run()

    pareto = result.get("pareto_solutions") or {}
    objectives = pareto.get("objectives")

    if objectives is not None and len(objectives) > 0:
        print(f"\n找到 {len(objectives)} 个解")

        # 根据目标数量处理结果
        if objectives.shape[1] >= 2:
            # 多目标情况
            best_cost_idx = np.argmin(objectives[:, 0])
            best_revenue_idx = np.argmin(objectives[:, 1])

            print(f"\n最低成本方案:")
            print(f"  成本: {objectives[best_cost_idx, 0]:.2f}")
            print(f"  收益: {-objectives[best_cost_idx, 1]:.2f}")

            print(f"\n最高收益方案:")
            print(f"  成本: {objectives[best_revenue_idx, 0]:.2f}")
            print(f"  收益: {-objectives[best_revenue_idx, 1]:.2f}")
        else:
            # 单目标情况
            best_idx = np.argmin(objectives[:, 0])
            print(f"\n最优解 (目标值): {objectives[best_idx, 0]:.2f}")


# ============================================================================
# 示例 2: 矩阵优化（带行列和约束）
# ============================================================================
class MatrixBalancingProblem(BlackBoxProblem):
    """
    矩阵平衡问题：构造满足行列和约束的矩阵

    目标：最小化与目标矩阵的差异
    约束：每行每列的和必须满足指定值
    """

    def __init__(self, n=5, row_sum_target=20, col_sum_target=20):
        self.n = n
        self.row_sum_target = row_sum_target
        self.col_sum_target = col_sum_target
        self.target_matrix = np.random.uniform(0, 10, (n, n))

        # 矩阵展平为向量
        bounds = {f"cell_{i}_{j}": [0, 10] for i in range(n) for j in range(n)}
        super().__init__(
            name="MatrixBalancing",
            dimension=n * n,
            bounds=bounds
        )

    def evaluate(self, x):
        mat = np.asarray(x).reshape(self.n, self.n)

        # 目标：最小化与目标矩阵的差异
        diff = np.sum((mat - self.target_matrix) ** 2)

        return [diff]


def demo_matrix_optimization():
    """演示矩阵优化"""
    print("\n" + "=" * 60)
    print("示例 2: 矩阵优化 - 带行列和约束")
    print("=" * 60)

    n = 5
    problem = MatrixBalancingProblem(n=n, row_sum_target=20, col_sum_target=20)

    # 使用矩阵表示管道 - 直接初始化整数矩阵
    pipeline = RepresentationPipeline(
        initializer=IntegerMatrixInitializer(
            rows=n, cols=n, low=0, high=5
        ),
        repair=MatrixRowColSumRepair(
            row_sums=np.full(n, 20),
            col_sums=np.full(n, 20),
            max_passes=5
        ),
        mutator=IntegerMatrixMutation(sigma=0.5, low=0, high=10),
    )

    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 60
    solver.max_generations = 100
    solver.set_representation_pipeline(pipeline)

    result = solver.run()

    pareto = result.get("pareto_solutions") or {}
    objectives = pareto.get("objectives")
    individuals = pareto.get("individuals")

    if objectives is not None and len(objectives) > 0:
        best_idx = np.argmin(objectives[:, 0])
        best_x = individuals[best_idx]
        best_mat = best_x.reshape(n, n)

        print(f"\n最优解 (差异 = {objectives[best_idx, 0]:.2f}):")
        print(best_mat)
        print(f"\n行和: {best_mat.sum(axis=0)}")
        print(f"列和: {best_mat.sum(axis=1)}")


# ============================================================================
# 示例 3: 二进制优化（背包问题）
# ============================================================================
class KnapsackProblem(BlackBoxProblem):
    """
    0/1 背包问题

    目标：最大化价值
    约束：重量不超过容量
    """

    def __init__(self, n_items=15, capacity=50):
        self.n_items = n_items
        self.capacity = capacity

        # 随机生成物品
        np.random.seed(42)
        self.weights = np.random.uniform(1, 10, n_items)
        self.values = np.random.uniform(10, 100, n_items)

        bounds = {f"item_{i}": [0, 1] for i in range(n_items)}
        super().__init__(
            name="Knapsack",
            dimension=n_items,
            bounds=bounds
        )

    def evaluate(self, x):
        x = np.asarray(x, dtype=int)

        total_weight = np.sum(x * self.weights)
        total_value = np.sum(x * self.values)

        # 惩罚超重
        penalty = max(0, total_weight - self.capacity) * 100

        # 最大化价值（取负值）
        return [-(total_value - penalty)]


def demo_binary_optimization():
    """演示二进制优化"""
    print("\n" + "=" * 60)
    print("示例 3: 二进制优化 - 背包问题")
    print("=" * 60)

    capacity = 50
    problem = KnapsackProblem(n_items=15, capacity=capacity)

    # 使用二进制表示管道 + 容量约束修复
    pipeline = RepresentationPipeline(
        initializer=BinaryInitializer(probability=0.3),
        mutator=BitFlipMutation(rate=0.05),
        repair=BinaryCapacityRepair(capacity=capacity, exact=False),
    )

    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 80
    solver.max_generations = 100
    solver.set_representation_pipeline(pipeline)

    result = solver.run()

    pareto = result.get("pareto_solutions") or {}
    objectives = pareto.get("objectives")
    individuals = pareto.get("individuals")

    if objectives is not None and len(objectives) > 0:
        best_idx = np.argmin(objectives[:, 0])
        best_x = individuals[best_idx].astype(int)

        total_weight = np.sum(best_x * problem.weights)
        total_value = np.sum(best_x * problem.values)

        print(f"\n最优解:")
        print(f"  价值: {-objectives[best_idx, 0]:.2f}")
        print(f"  重量: {total_weight:.2f} / {capacity}")
        print(f"  选中物品: {np.where(best_x == 1)[0].tolist()}")


# ============================================================================
# 示例 4: 排列优化（TSP - 随机键编码）
# ============================================================================
class TSPRandomKeysProblem(BlackBoxProblem):
    """使用随机键编码的 TSP 问题"""

    def __init__(self, cities: np.ndarray):
        self.cities = np.array(cities, dtype=float)
        self.decoder = RandomKeyPermutationDecoder()
        n = self.cities.shape[0]
        bounds = {f"x{i}": [0.0, 1.0] for i in range(n)}
        super().__init__(name="TSPRandomKeys", dimension=n, bounds=bounds)

    def evaluate(self, x):
        tour = self.decoder.decode(np.asarray(x, dtype=float))
        total = 0.0
        for i in range(len(tour)):
            j = (i + 1) % len(tour)
            total += np.linalg.norm(self.cities[tour[i]] - self.cities[tour[j]])
        return [total]


def demo_tsp_optimization():
    """演示 TSP 优化（随机键编码）"""
    print("\n" + "=" * 60)
    print("示例 4: 排列优化 - TSP (随机键编码)")
    print("=" * 60)

    rng = np.random.default_rng(42)
    n_cities = 10
    cities = rng.uniform(0, 100, size=(n_cities, 2))

    problem = TSPRandomKeysProblem(cities)

    # 使用随机键编码管道
    pipeline = RepresentationPipeline(
        initializer=RandomKeyInitializer(0.0, 1.0),
        mutator=RandomKeyMutation(sigma=0.1, low=0.0, high=1.0),
        encoder=problem.decoder,
    )

    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 80
    solver.max_generations = 120
    solver.set_representation_pipeline(pipeline)

    result = solver.run()

    pareto = result.get("pareto_solutions") or {}
    objectives = pareto.get("objectives")
    individuals = pareto.get("individuals")

    if objectives is not None and len(objectives) > 0:
        best_idx = np.argmin(objectives[:, 0])
        best_x = individuals[best_idx]
        best_tour = problem.decoder.decode(best_x)
        best_distance = float(objectives[best_idx, 0])

        print(f"\n最优解:")
        print(f"  距离: {best_distance:.2f}")
        print(f"  路径: {best_tour.tolist()}")


# ============================================================================
# 示例 5: 连续优化
# ============================================================================
class ContinuousOptimizationProblem(BlackBoxProblem):
    """
    连续优化问题：经典的测试函数

    目标：最小化 Rastrigin 函数（多峰函数）
    """

    def __init__(self, dimension=5):
        bounds = {f"x{i}": [-5.12, 5.12] for i in range(dimension)}
        super().__init__(
            name="Rastrigin",
            dimension=dimension,
            bounds=bounds
        )

    def evaluate(self, x):
        """Rastrigin 函数"""
        x = np.asarray(x)
        A = 10
        n = len(x)
        return [A * n + np.sum(x ** 2 - A * np.cos(2 * np.pi * x))]


def demo_continuous_optimization():
    """演示连续优化"""
    print("\n" + "=" * 60)
    print("示例 5: 连续优化 - Rastrigin 函数")
    print("=" * 60)

    problem = ContinuousOptimizationProblem(dimension=5)

    # 使用连续表示管道
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(low=-5.12, high=5.12),
        mutator=GaussianMutation(sigma=0.5, low=-5.12, high=5.12),
        repair=ClipRepair(low=-5.12, high=5.12),
    )

    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 100
    solver.max_generations = 150
    solver.set_representation_pipeline(pipeline)

    result = solver.run()

    pareto = result.get("pareto_solutions") or {}
    objectives = pareto.get("objectives")

    if objectives is not None and len(objectives) > 0:
        best_idx = np.argmin(objectives[:, 0])
        best_value = float(objectives[best_idx, 0])

        print(f"\n最优解:")
        print(f"  Rastrigin 函数值: {best_value:.4f}")
        print(f"  (全局最优值 = 0)")


# ============================================================================
# 主函数
# ============================================================================
def main():
    """运行所有示例"""
    print("\n" + "=" * 60)
    print("Representation Pipeline 综合示例")
    print("=" * 60)
    print("\n本示例展示如何使用 Representation Pipeline 处理不同类型的优化问题")
    print("每种类型都使用专门的初始化、变异和修复策略")

    # 运行各个示例
    demo_integer_optimization()
    demo_matrix_optimization()
    demo_binary_optimization()
    demo_tsp_optimization()
    demo_continuous_optimization()

    print("\n" + "=" * 60)
    print("所有示例运行完成！")
    print("=" * 60)
    print("\n关键优势:")
    print("  1. 直接在正确的表示空间初始化（效率高）")
    print("  2. 自然的变异操作（保持解的合法性）")
    print("  3. 可选的修复机制（处理复杂约束）")
    print("  4. 与求解器解耦（可复用）")
    print("=" * 60)


if __name__ == "__main__":
    main()
