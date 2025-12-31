"""
TSP约束偏置示例 - 旅行商问题的终极解法

这个示例展示如何使用约束型偏置来解决TSP问题。
关键思想：只做约束验证，不做搜索引导，让算法在合法解空间中自由探索。

TSP Constraint Bias Example - The Ultimate Solution for Traveling Salesman Problem

This example demonstrates how to use constraint-only bias to solve TSP.
Key philosophy: Only validate constraints, don't guide search, let algorithm explore freely in valid solution space.
"""

import numpy as np
import matplotlib.pyplot as plt
from typing import List, Tuple
import random

# 导入核心组件
from core import BlackBoxSolverNSGAII
from core.problems import BlackBoxProblem
from bias.bias_base import OptimizationContext

# 导入图约束偏置
from bias.bias_graph_constraints import (
    TSPConstraintBias, GraphConstraintFactory, CompositeGraphConstraintBias
)


class TSPProblem:
    """TSP问题定义"""

    def __init__(self, num_cities: int = 20, seed: int = 42):
        self.num_cities = num_cities
        self.seed = seed
        np.random.seed(seed)
        random.seed(seed)

        # 生成随机城市坐标
        self.cities = np.random.rand(num_cities, 2) * 100

        # 计算距离矩阵
        self.distance_matrix = self._compute_distance_matrix()

    def _compute_distance_matrix(self) -> np.ndarray:
        """计算城市间的欧氏距离矩阵"""
        matrix = np.zeros((self.num_cities, self.num_cities))
        for i in range(self.num_cities):
            for j in range(self.num_cities):
                if i != j:
                    matrix[i, j] = np.linalg.norm(self.cities[i] - self.cities[j])
        return matrix

    def calculate_tour_distance(self, tour: List[int]) -> float:
        """计算路径的总距离"""
        total_distance = 0.0
        for i in range(len(tour) - 1):
            total_distance += self.distance_matrix[tour[i], tour[i + 1]]
        # 添加返回起点的距离
        total_distance += self.distance_matrix[tour[-1], tour[0]]
        return total_distance

    def visualize_solution(self, tour: List[int], title: str = "TSP Solution"):
        """可视化TSP解"""
        plt.figure(figsize=(10, 8))

        # 绘制城市
        plt.scatter(self.cities[:, 0], self.cities[:, 1],
                   c='red', s=100, zorder=5, label='Cities')

        # 标注城市编号
        for i, (x, y) in enumerate(self.cities):
            plt.annotate(str(i), (x, y), xytext=(5, 5),
                        textcoords='offset points', fontsize=10)

        # 绘制路径
        tour_cities = [self.cities[i] for i in tour]
        tour_cities.append(self.cities[tour[0]])  # 回到起点

        path_x = [city[0] for city in tour_cities]
        path_y = [city[1] for city in tour_cities]

        plt.plot(path_x, path_y, 'b-', alpha=0.6, linewidth=2, label='Tour')

        plt.title(f"{title}\nDistance: {self.calculate_tour_distance(tour):.2f}")
        plt.xlabel('X Coordinate')
        plt.ylabel('Y Coordinate')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.show()


class TSPConstraintOptimizer:
    """基于约束偏置的TSP优化器"""

    def __init__(self, tsp_problem: TSPProblem):
        self.tsp = tsp_problem
        self.constraint_bias = TSPConstraintBias(tsp_problem.num_cities, penalty_scale=1e6)
        self.best_solution = None
        self.best_distance = float('inf')
        self.optimization_history = []

    def create_tsp_objective_function(self):
        """创建TSP目标函数（只计算距离，约束由偏置处理）"""

        def objective(x: np.ndarray) -> float:
            # 1. 将解向量转换为城市序列
            tour = self._decode_solution(x)

            # 2. 计算路径距离
            distance = self.tsp.calculate_tour_distance(tour)

            # 3. 应用约束偏置（如果违反约束，返回大惩罚值）
            context = OptimizationContext(
                generation=1,
                population_size=100,
                current_objective=distance
            )
            constraint_penalty = self.constraint_bias.compute(x, context)

            # 4. 返回总目标值
            return distance + constraint_penalty

        return objective

    def _decode_solution(self, x: np.ndarray) -> List[int]:
        """将解向量解码为城市序列"""
        if len(x) == self.tsp.num_cities:
            # 顺序编码：直接是城市序列
            tour = np.round(x).astype(int)
            # 确保所有城市都在0到n-1范围内
            tour = np.clip(tour, 0, self.tsp.num_cities - 1)
            return tour.tolist()
        else:
            # 需要从其他编码转换
            return self._convert_to_tour(x)

    def _convert_to_tour(self, x: np.ndarray) -> List[int]:
        """从其他编码转换为城市序列"""
        # 简化实现：使用随机排列
        tour = list(range(self.tsp.num_cities))
        random.shuffle(tour)
        return tour

    def optimize(self, max_generations: int = 200, population_size: int = 100):
        """执行优化"""
        print("=" * 60)
        print("TSP约束偏置优化 - Constraint-Only TSP Optimization")
        print("=" * 60)
        print(f"城市数量: {self.tsp.num_cities}")
        print(f"优化代数: {max_generations}")
        print(f"种群大小: {population_size}")
        print("-" * 60)

        # 创建优化问题
        objective_func = self.create_tsp_objective_function()
        problem = BlackBoxProblem(
            name="tsp_constraint",
            n_var=self.tsp.num_cities,  # 每个变量代表一个城市的位置
            n_obj=1,
            n_constr=0,
            xl=0.0,
            xu=float(self.tsp.num_cities - 1),
            function=objective_func
        )

        # 创建求解器
        solver = BlackBoxSolverNSGAII(problem)
        solver.population_size = population_size

        # 记录初始最优解
        print("生成初始随机解...")
        initial_tour = list(range(self.tsp.num_cities))
        random.shuffle(initial_tour)
        initial_distance = self.tsp.calculate_tour_distance(initial_tour)
        print(f"初始随机路径距离: {initial_distance:.2f}")

        # 可视化初始解
        self.tsp.visualize_solution(initial_tour, "Initial Random Solution")

        # 开始优化
        print("\n开始优化...")
        best_generation = 0
        stagnation_count = 0
        last_best_distance = float('inf')

        for gen in range(max_generations):
            # 运行一代
            solver.run(max_gen=1)

            # 获取当前最优解
            current_best = solver.population[0]
            current_tour = self._decode_solution(current_best)

            # 验证约束
            context = OptimizationContext(
                generation=gen,
                population_size=population_size,
                current_objective=0.0
            )
            validation_result = self.constraint_bias.validate_constraints(current_best, context)

            if validation_result.is_valid:
                current_distance = self.tsp.calculate_tour_distance(current_tour)
                self.optimization_history.append((gen, current_distance))

                # 更新全局最优
                if current_distance < self.best_distance:
                    self.best_solution = current_tour.copy()
                    self.best_distance = current_distance
                    best_generation = gen
                    print(f"代数 {gen:3d}: 新的最优解! 距离 = {current_distance:.2f}")
                    stagnation_count = 0
                else:
                    stagnation_count += 1
                    if gen % 20 == 0:
                        print(f"代数 {gen:3d}: 当前最优 = {self.best_distance:.2f}")
            else:
                # 当前解违反约束
                print(f"代数 {gen:3d}: 违反约束 - {validation_result.violation_type}")
                stagnation_count += 1

            # 早停条件
            if stagnation_count > 50:
                print(f"\n连续{stagnation_count}代没有改进，提前停止")
                break

        print("-" * 60)
        print("优化完成!")
        print(f"找到最优解的代数: {best_generation}")
        print(f"最优距离: {self.best_distance:.2f}")
        print(f"改进幅度: {((initial_distance - self.best_distance) / initial_distance * 100):.1f}%")

        # 可视化最终结果
        if self.best_solution:
            self.tsp.visualize_solution(self.best_solution, "Optimized Solution (Constraint Bias)")

        # 绘制优化历史
        self._plot_optimization_history()

    def _plot_optimization_history(self):
        """绘制优化历史曲线"""
        if not self.optimization_history:
            return

        generations, distances = zip(*self.optimization_history)

        plt.figure(figsize=(10, 6))
        plt.plot(generations, distances, 'b-', linewidth=2, label='Best Distance')
        plt.scatter([generations[-1]], [distances[-1]], c='red', s=100, zorder=5,
                   label=f'Final: {distances[-1]:.2f}')

        plt.xlabel('Generation')
        plt.ylabel('Tour Distance')
        plt.title('TSP Optimization History (Constraint-Only Bias)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.show()

    def analyze_solution(self):
        """分析最优解的性质"""
        if not self.best_solution:
            print("没有找到有效解")
            return

        print("\n" + "=" * 60)
        print("最优解分析")
        print("=" * 60)

        # 路径信息
        print(f"最优路径: {' -> '.join(map(str, self.best_solution))}")
        print(f"总距离: {self.best_distance:.2f}")

        # 统计信息
        edges = [(self.best_solution[i], self.best_solution[(i + 1) % len(self.best_solution)])
                for i in range(len(self.best_solution))]
        edge_lengths = [self.tsp.distance_matrix[u, v] for u, v in edges]

        print(f"\n边统计:")
        print(f"  最短边: {min(edge_lengths):.2f}")
        print(f"  最长边: {max(edge_lengths):.2f}")
        print(f"  平均边长: {np.mean(edge_lengths):.2f}")
        print(f"  边长标准差: {np.std(edge_lengths):.2f}")

        # 验证约束
        x = np.array(self.best_solution, dtype=float)
        context = OptimizationContext(generation=1, population_size=100, current_objective=self.best_distance)
        validation_result = self.constraint_bias.validate_constraints(x, context)

        print(f"\n约束验证:")
        print(f"  是否满足所有约束: {'✓ 是' if validation_result.is_valid else '✗ 否'}")
        if not validation_result.is_valid:
            print(f"  违反类型: {validation_result.violation_type}")


def demonstrate_constraint_only_philosophy():
    """演示纯约束偏置的哲学思想"""
    print("\n" + "=" * 60)
    print("约束偏置哲学演示")
    print("=" * 60)

    # 创建一个小的TSP实例
    tsp = TSPProblem(num_cities=8, seed=123)
    constraint_bias = TSPConstraintBias(tsp.num_cities)

    # 测试几个不同的解
    test_cases = [
        {
            "name": "有效解",
            "solution": [0, 2, 4, 1, 3, 5, 6, 7]  # 有效的城市序列
        },
        {
            "name": "重复城市",
            "solution": [0, 2, 4, 2, 3, 5, 6, 7]  # 城市2重复
        },
        {
            "name": "缺失城市",
            "solution": [0, 2, 4, 1, 3, 5, 6, 6]  # 缺少城市7
        },
        {
            "name": "超出范围",
            "solution": [0, 2, 4, 8, 3, 5, 6, 7]  # 城市8不存在
        }
    ]

    for test in test_cases:
        print(f"\n测试: {test['name']}")
        print(f"解: {test['solution']}")

        x = np.array(test['solution'], dtype=float)
        context = OptimizationContext(generation=1, population_size=100, current_objective=0.0)

        # 验证约束
        result = constraint_bias.validate_constraints(x, context)
        print(f"约束满足: {'✓' if result.is_valid else '✗'}")

        if not result.is_valid:
            print(f"违反类型: {result.violation_type}")
            if result.violation_details:
                print(f"详细信息: {result.violation_details}")

        # 计算惩罚值
        penalty = constraint_bias.compute(x, context)
        print(f"惩罚值: {penalty}")

        # 计算实际距离
        if result.is_valid:
            distance = tsp.calculate_tour_distance(test['solution'])
            print(f"路径距离: {distance:.2f}")
        else:
            print("路径距离: 无效解，不计算")


def main():
    """主函数"""
    print("TSP约束偏置优化示例")
    print("=" * 60)

    # 演示约束偏置哲学
    demonstrate_constraint_only_philosophy()

    # 运行完整的TSP优化
    print("\n\n" + "=" * 60)
    print("开始TSP约束偏置优化")
    print("=" * 60)

    # 创建TSP问题
    tsp = TSPProblem(num_cities=15, seed=42)

    # 创建优化器
    optimizer = TSPConstraintOptimizer(tsp)

    # 执行优化
    optimizer.optimize(max_generations=150, population_size=50)

    # 分析结果
    optimizer.analyze_solution()


if __name__ == "__main__":
    main()