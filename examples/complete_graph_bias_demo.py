"""
完整的图偏置示例

演示抽象框架与数学逻辑偏置的完美结合，
从问题定义到求解的完整流程。

Complete Graph Bias Demo

Demonstrates the perfect combination of abstract framework and mathematical logic bias,
from problem definition to solving the complete workflow.
"""

import sys
import os
# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import matplotlib.pyplot as plt
try:
    import networkx as nx
except ImportError:
    nx = None
    print("警告: networkx 未安装，将跳过网络可视化功能")

from typing import List, Tuple, Dict

# 导入完整的图偏置系统
from bias.bias_graph_abstract import (
    GraphProblemFactory, TSPProblem, SpanningTreeProblem,
    GraphColoringProblem, SolutionEncoding
)
from bias.bias_graph_constraints import (
    TSPConstraintBias, TreeConstraintBias, GraphColoringConstraintBias
)
from bias.bias_base import OptimizationContext

# 导入优化器
from core import BlackBoxSolverNSGAII
from core.problems import BlackBoxProblem


class CompleteGraphDemo:
    """完整的图偏置演示类"""

    def __init__(self):
        self.demos = {
            'tsp': self.demo_tsp_complete,
            'spanning_tree': self.demo_spanning_tree_complete,
            'graph_coloring': self.demo_graph_coloring_complete
        }

    def run_demo(self, demo_name: str):
        """运行指定的演示"""
        if demo_name in self.demos:
            print(f"\n{'='*80}")
            print(f"运行演示: {demo_name.upper()}")
            print(f"{'='*80}")
            self.demos[demo_name]()
        else:
            print(f"未找到演示: {demo_name}")
            print(f"可用演示: {list(self.demos.keys())}")

    def demo_tsp_complete(self):
        """完整的TSP演示"""

        print("\n📍 第一步：定义TSP问题")
        print("-" * 40)

        # 1. 生成城市数据
        np.random.seed(42)
        num_cities = 12
        cities = np.random.rand(num_cities, 2) * 100

        # 2. 计算距离矩阵
        distance_matrix = self._compute_distance_matrix(cities)
        print(f"创建了 {num_cities} 个城市的TSP问题")
        print(f"城市坐标范围: x:[{cities[:, 0].min():.1f}, {cities[:, 0].max():.1f}], "
              f"y:[{cities[:, 1].min():.1f}, {cities[:, 1].max():.1f}]")

        # 3. 使用抽象框架创建TSP问题
        tsp_problem = GraphProblemFactory.create_tsp(distance_matrix)
        print(f"\n✅ 抽象框架创建成功:")
        print(f"   - 问题名称: {tsp_problem.get_name()}")
        print(f"   - 编码方式: {tsp_problem.get_encoding().value}")
        print(f"   - 节点数: {tsp_problem.num_nodes}")

        print("\n📐 第二步：创建数学逻辑偏置")
        print("-" * 40)

        # 4. 创建数学约束偏置
        math_constraint = TSPConstraintBias(num_cities, penalty_scale=1e6)
        print(f"✅ 数学约束偏置创建成功:")
        print(f"   - 约束类型: TSP约束")
        print(f"   - 惩罚尺度: {math_constraint.penalty_scale}")

        print("\n🧮 第三步：验证数学逻辑")
        print("-" * 40)

        # 5. 演示数学约束的验证逻辑
        test_solutions = [
            {
                "name": "有效解",
                "solution": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
            },
            {
                "name": "重复城市",
                "solution": [0, 1, 2, 1, 3, 4, 5, 6, 7, 8, 9, 10]
            },
            {
                "name": "缺失城市",
                "solution": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 10]
            },
            {
                "name": "超出范围",
                "solution": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20]
            }
        ]

        for test in test_solutions:
            x = np.array(test["solution"], dtype=float)
            result = math_constraint.validate_constraints(
                x, OptimizationContext(generation=1, population_size=100, current_objective=0.0)
            )
            status = "✅ 有效" if result.is_valid else "❌ 无效"
            print(f"   {test['name']:8}: {status}")
            if not result.is_valid:
                print(f"            原因: {result.violation_type}")

        print("\n⚡ 第四步：创建优化问题")
        print("-" * 40)

        # 6. 结合抽象框架和数学约束创建优化目标函数
        def tsp_objective(x: np.ndarray) -> float:
            # 使用抽象框架计算目标值
            objective_value = tsp_problem.evaluate_solution(x)

            # 使用数学约束应用惩罚
            constraint_penalty = math_constraint.compute(
                x, OptimizationContext(generation=1, population_size=100, current_objective=objective_value)
            )

            return objective_value + constraint_penalty

        # 7. 创建BlackBoxProblem
        problem = BlackBoxProblem(
            name="tsp_with_mathematical_constraint",
            n_var=num_cities,
            n_obj=1,
            n_constr=0,
            xl=0.0,
            xu=float(num_cities - 1),
            function=tsp_objective
        )
        print(f"✅ 优化问题创建成功:")
        print(f"   - 变量数: {problem.n_var}")
        print(f"   - 变量范围: [{problem.xl}, {problem.xu}]")

        print("\n🚀 第五步：执行优化")
        print("-" * 40)

        # 8. 设置求解器并优化
        solver = BlackBoxSolverNSGAII(problem)
        solver.population_size = 50

        print("开始优化...")
        print("代数 | 当前最优 | 改进幅度 | 约束状态")
        print("-" * 50)

        best_distance = float('inf')
        history = []

        for gen in range(60):
            solver.run(max_gen=1)

            # 获取当前最优解
            current_solution = solver.population[0]
            current_distance = tsp_problem.evaluate_solution(current_solution)

            # 验证约束
            is_valid = tsp_problem.validate_solution(current_solution).is_valid

            # 记录历史
            if is_valid and current_distance < best_distance:
                improvement = best_distance - current_distance
                best_distance = current_distance
                history.append((gen, current_distance))
                status = "✅"
            elif is_valid:
                improvement = 0
                status = "✅"
            else:
                improvement = 0
                status = "❌"

            if gen % 10 == 0 or improvement > 0:
                print(f"{gen:4d} | {current_distance:9.2f} | {improvement:9.2f} | {status}")

        print("-" * 50)
        print(f"优化完成! 最优距离: {best_distance:.2f}")

        print("\n📊 第六步：结果可视化")
        print("-" * 40)

        # 9. 可视化结果
        if best_distance < float('inf'):
            # 找到最优解
            for solution in solver.population:
                if tsp_problem.validate_solution(solution).is_valid:
                    if tsp_problem.evaluate_solution(solution) <= best_distance + 0.1:
                        best_solution = solution
                        break

            # 解码路径
            tour = tsp_problem.decode_solution(best_solution)
            print(f"最优路径: {' → '.join(map(str, tour))} → {tour[0]}")

            # 绘制城市和路径
            plt.figure(figsize=(12, 8))

            # 绘制城市
            plt.scatter(cities[:, 0], cities[:, 1], c='red', s=200, zorder=5, alpha=0.8)
            for i, (x, y) in enumerate(cities):
                plt.annotate(f'{i}', (x, y), xytext=(5, 5),
                            textcoords='offset points', fontsize=12, fontweight='bold')

            # 绘制路径
            tour_cities = [cities[i] for i in tour] + [cities[tour[0]]]
            path_x = [c[0] for c in tour_cities]
            path_y = [c[1] for c in tour_cities]

            plt.plot(path_x, path_y, 'b-', alpha=0.6, linewidth=2, marker='o', markersize=8)

            # 添加起点和终点标记
            plt.scatter(cities[tour[0], 0], cities[tour[0], 1],
                       c='green', s=300, marker='*', zorder=10, label='起点/终点')

            plt.title(f'TSP最优解 (抽象框架 + 数学逻辑偏置)\n'
                     f'总距离: {best_distance:.2f}', fontsize=14, fontweight='bold')
            plt.xlabel('X坐标', fontsize=12)
            plt.ylabel('Y坐标', fontsize=12)
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.axis('equal')
            plt.show()

        print("\n🎯 总结：抽象框架与数学逻辑的完美结合")
        print("-" * 40)
        print("✅ 抽象框架提供标准接口和数据结构")
        print("✅ 数学逻辑提供严谨的约束验证")
        print("✅ 两者的结合实现了代码复用与逻辑清晰的完美平衡")

    def demo_spanning_tree_complete(self):
        """完整的生成树演示"""

        print("\n📍 第一步：定义生成树问题")
        print("-" * 40)

        # 1. 创建图数据
        np.random.seed(123)
        num_nodes = 8

        # 生成随机边权重
        edge_weights = {}
        for i in range(num_nodes):
            for j in range(i + 1, num_nodes):
                edge_weights[(i, j)] = np.random.uniform(1, 20)

        print(f"创建了 {num_nodes} 个节点的生成树问题")
        print(f"可能的边数: {num_nodes * (num_nodes - 1) // 2}")

        # 2. 使用抽象框架创建问题
        tree_problem = GraphProblemFactory.create_spanning_tree(num_nodes, edge_weights)
        print(f"\n✅ 抽象框架创建成功:")
        print(f"   - 问题名称: {tree_problem.get_name()}")
        print(f"   - 编码方式: {tree_problem.get_encoding().value}")
        print(f"   - 期望边数: {tree_problem.expected_edges}")
        print(f"   - 必须连通: {tree_problem.must_be_connected}")
        print(f"   - 必须无环: {tree_problem.must_be_acyclic}")

        print("\n📐 第二步：创建数学逻辑偏置")
        print("-" * 40)

        # 3. 创建数学约束偏置
        math_constraint = TreeConstraintBias(num_nodes, penalty_scale=1e6)

        print("\n🧮 第三步：验证数学逻辑")
        print("-" * 40)

        # 4. 演示边数检查的数学逻辑
        num_possible_edges = num_nodes * (num_nodes - 1) // 2

        test_cases = [
            {
                "name": "正确边数 (7条)",
                "edges": [1] * 7 + [0] * (num_possible_edges - 7)
            },
            {
                "name": "边数不足 (6条)",
                "edges": [1] * 6 + [0] * (num_possible_edges - 6)
            },
            {
                "name": "边数过多 (8条)",
                "edges": [1] * 8 + [0] * (num_possible_edges - 8)
            },
            {
                "name": "形成环路",
                "edges": [1, 1, 1, 0] + [0] * (num_possible_edges - 4)  # 边0-1, 0-2, 1-2形成环
            }
        ]

        for test in test_cases:
            x = np.array(test["edges"])
            result = math_constraint.validate_constraints(
                x, OptimizationContext(generation=1, population_size=100, current_objective=0.0)
            )
            status = "✅ 有效" if result.is_valid else "❌ 无效"
            print(f"   {test['name']:15}: {status}")
            if not result.is_valid:
                print(f"                      原因: {result.violation_type}")

        print("\n⚡ 第四步：执行优化")
        print("-" * 40)

        # 5. 优化求解
        def tree_objective(x: np.ndarray) -> float:
            objective_value = tree_problem.evaluate_solution(x)
            constraint_penalty = math_constraint.compute(
                x, OptimizationContext(generation=1, population_size=100, current_objective=objective_value)
            )
            return objective_value + constraint_penalty

        problem = BlackBoxProblem(
            name="spanning_tree_with_mathematical_constraint",
            n_var=num_possible_edges,
            n_obj=1,
            n_constr=0,
            xl=0.0,
            xu=1.0,
            function=tree_objective
        )

        solver = BlackBoxSolverNSGAII(problem)
        solver.population_size = 30

        print("开始优化...")
        solver.run(max_gen=50)

        # 获取最优解
        best_solution = None
        best_weight = float('inf')

        for solution in solver.population:
            if tree_problem.validate_solution(solution).is_valid:
                weight = tree_problem.evaluate_solution(solution)
                if weight < best_weight:
                    best_weight = weight
                    best_solution = solution

        print(f"优化完成! 最优权重: {best_weight:.2f}")

        print("\n📊 第五步：结果展示")
        print("-" * 40)

        if best_solution is not None:
            edges = tree_problem.decode_solution(best_solution)
            print(f"找到的生成树边:")
            total_weight = 0.0
            for edge in edges:
                weight = edge_weights.get((min(edge), max(edge)), 1.0)
                total_weight += weight
                print(f"   边 {edge}: 权重 {weight:.2f}")
            print(f"总权重: {total_weight:.2f}")

            # 验证数学约束
            result = tree_problem.validate_solution(best_solution)
            print(f"\n数学约束验证: {'✅ 满足' if result.is_valid else '❌ 违反'}")

    def demo_graph_coloring_complete(self):
        """完整的图着色演示"""

        print("\n📍 第一步：定义图着色问题")
        print("-" * 40)

        # 1. 创建图数据
        adjacency_matrix = np.array([
            [0, 1, 1, 0, 1, 0],
            [1, 0, 1, 1, 0, 0],
            [1, 1, 0, 1, 1, 0],
            [0, 1, 1, 0, 1, 1],
            [1, 0, 1, 1, 0, 1],
            [0, 0, 0, 1, 1, 0]
        ])

        max_colors = 3
        print(f"创建了 6 节点图着色问题")
        print(f"最大颜色数: {max_colors}")

        # 2. 使用抽象框架创建问题
        coloring_problem = GraphProblemFactory.create_graph_coloring(adjacency_matrix, max_colors)
        print(f"\n✅ 抽象框架创建成功:")
        print(f"   - 问题名称: {coloring_problem.get_name()}")
        print(f"   - 编码方式: {coloring_problem.get_encoding().value}")
        print(f"   - 节点数: {coloring_problem.num_nodes}")
        print(f"   - 最大颜色数: {coloring_problem.max_colors}")

        print("\n📐 第二步：创建数学逻辑偏置")
        print("-" * 40)

        # 3. 创建数学约束偏置
        math_constraint = GraphColoringConstraintBias(adjacency_matrix, max_colors)

        print("\n🧮 第三步：验证数学逻辑")
        print("-" * 40)

        # 4. 演示颜色冲突检查的数学逻辑
        test_cases = [
            {
                "name": "有效着色",
                "colors": [0, 1, 2, 0, 1, 2]
            },
            {
                "name": "颜色冲突",
                "colors": [0, 0, 1, 2, 1, 2]  # 节点0和1相邻且同色
            },
            {
                "name": "颜色过多",
                "colors": [0, 1, 2, 3, 4, 5]  # 使用6种颜色，超过限制
            }
        ]

        for test in test_cases:
            x = np.array(test["colors"], dtype=float)
            result = math_constraint.validate_constraints(
                x, OptimizationContext(generation=1, population_size=100, current_objective=0.0)
            )
            status = "✅ 有效" if result.is_valid else "❌ 无效"
            print(f"   {test['name']:10}: {status}")
            if not result.is_valid:
                print(f"               原因: {result.violation_type}")

        print("\n⚡ 第四步：执行优化")
        print("-" * 40)

        # 5. 优化求解
        def coloring_objective(x: np.ndarray) -> float:
            objective_value = coloring_problem.evaluate_solution(x)
            constraint_penalty = math_constraint.compute(
                x, OptimizationContext(generation=1, population_size=100, current_objective=objective_value)
            )
            return objective_value + constraint_penalty

        problem = BlackBoxProblem(
            name="graph_coloring_with_mathematical_constraint",
            n_var=6,
            n_obj=1,
            n_constr=0,
            xl=0.0,
            xu=float(max_colors - 1),
            function=coloring_objective
        )

        solver = BlackBoxSolverNSGAII(problem)
        solver.population_size = 40

        print("开始优化...")
        solver.run(max_gen=40)

        # 获取最优解
        best_solution = None
        best_num_colors = float('inf')

        for solution in solver.population:
            if coloring_problem.validate_solution(solution).is_valid:
                colors = coloring_problem.decode_solution(solution)
                num_colors = len(set(colors))
                if num_colors < best_num_colors:
                    best_num_colors = num_colors
                    best_solution = solution

        print(f"优化完成! 最少颜色数: {best_num_colors}")

        print("\n📊 第五步：结果展示")
        print("-" * 40)

        if best_solution is not None:
            colors = coloring_problem.decode_solution(best_solution)
            print(f"找到的着色方案:")
            for i, color in enumerate(colors):
                print(f"   节点 {i}: 颜色 {color}")

            # 验证颜色冲突
            conflicts = []
            for i in range(6):
                for j in range(i + 1, 6):
                    if adjacency_matrix[i, j] > 0 and colors[i] == colors[j]:
                        conflicts.append((i, j, colors[i]))

            if conflicts:
                print(f"\n❌ 发现 {len(conflicts)} 个颜色冲突:")
                for i, j, color in conflicts:
                    print(f"   节点 {i} 和 {j} 都是颜色 {color}")
            else:
                print(f"\n✅ 没有颜色冲突！")

    def _compute_distance_matrix(self, cities: np.ndarray) -> np.ndarray:
        """计算城市间的距离矩阵"""
        n = len(cities)
        matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                if i != j:
                    matrix[i, j] = np.linalg.norm(cities[i] - cities[j])
        return matrix


def main():
    """主函数"""
    print("🎯 完整的图偏置系统演示")
    print("抽象框架 + 数学逻辑偏置的完美结合")
    print("=" * 80)

    demo = CompleteGraphDemo()

    # 选择要运行的演示
    print("\n可用的演示:")
    print("1. tsp - 旅行商问题")
    print("2. spanning_tree - 生成树问题")
    print("3. graph_coloring - 图着色问题")
    print("4. all - 运行所有演示")

    choice = input("\n请选择演示 (输入数字或名称): ").strip().lower()

    if choice in ['1', 'tsp']:
        demo.run_demo('tsp')
    elif choice in ['2', 'spanning_tree']:
        demo.run_demo('spanning_tree')
    elif choice in ['3', 'graph_coloring']:
        demo.run_demo('graph_coloring')
    elif choice in ['4', 'all']:
        for demo_name in ['tsp', 'spanning_tree', 'graph_coloring']:
            demo.run_demo(demo_name)
    else:
        print("无效选择，运行TSP演示...")
        demo.run_demo('tsp')

    print("\n" + "=" * 80)
    print("🎉 演示完成！")
    print("\n总结:")
    print("✅ 抽象框架提供了标准的接口和数据结构")
    print("✅ 数学逻辑偏置提供了严谨的约束验证")
    print("✅ 两者的结合实现了完美的代码复用和逻辑清晰")
    print("\n这确实是图论优化问题的优雅解决方案！")
    print("=" * 80)


if __name__ == "__main__":
    main()