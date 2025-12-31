"""
抽象图论框架与数学逻辑偏置结合示例

展示如何优雅地结合抽象框架和数学逻辑偏置：
1. 抽象类提供标准结构和接口
2. 数学逻辑专注于约束验证
3. 完美的职责分离和代码复用

Abstract Graph Framework with Mathematical Logic Bias Example

Demonstrates the elegant combination of abstract framework and mathematical logic bias:
1. Abstract classes provide standard structure and interfaces
2. Mathematical logic focuses on constraint validation
3. Perfect separation of concerns and code reuse
"""

import numpy as np
import matplotlib.pyplot as plt
from typing import List, Dict, Tuple, Optional

# 导入抽象框架
from bias.bias_graph_abstract import (
    GraphProblemFactory, TSPProblem, SpanningTreeProblem,
    GraphColoringProblem, CompositeGraphProblem
)

# 导入数学逻辑偏置
from bias.bias_graph_constraints import (
    GraphConstraintBias, TSPConstraintBias,
    TreeConstraintBias, GraphColoringConstraintBias,
    CompositeGraphConstraintBias
)

# 导入优化组件
from core import BlackBoxSolverNSGAII
from core.problems import BlackBoxProblem
from bias.bias_base import OptimizationContext


class MathematicalConstraintWrapper(GraphConstraintBias):
    """
    数学约束包装器

    将抽象问题的数学逻辑包装为标准的约束偏置
    """

    def __init__(self, graph_problem, penalty_scale: float = 1e6):
        super().__init__(f"mathematical_{graph_problem.get_name().lower().replace(' ', '_')}", penalty_scale)
        self.graph_problem = graph_problem

    def validate_constraints(self, x: np.ndarray, context: OptimizationContext):
        """使用抽象问题的验证逻辑"""
        result = self.graph_problem.validate_solution(x)
        return result


class AbstractGraphOptimizer:
    """
    基于抽象框架的图论优化器

    展示如何优雅地结合抽象问题和数学约束
    """

    def __init__(self, graph_problem, use_mathematical_bias: bool = True):
        self.graph_problem = graph_problem
        self.use_mathematical_bias = use_mathematical_bias

        # 创建数学约束偏置（如果启用）
        if use_mathematical_bias:
            self.constraint_bias = MathematicalConstraintWrapper(graph_problem)
        else:
            self.constraint_bias = None

        self.best_solution = None
        self.best_objective = float('inf')
        self.history = []

    def create_objective_function(self):
        """创建目标函数"""
        def objective(x: np.ndarray) -> float:
            # 1. 评估解的质量
            objective_value = self.graph_problem.evaluate_solution(x)

            # 2. 应用数学约束（如果启用）
            if self.use_mathematical_bias and self.constraint_bias:
                context = OptimizationContext(
                    generation=1,
                    population_size=100,
                    current_objective=objective_value
                )
                constraint_penalty = self.constraint_bias.compute(x, context)
                return objective_value + constraint_penalty

            return objective_value

        return objective

    def optimize(self, max_generations: int = 100, population_size: int = 50):
        """执行优化"""
        print(f"优化问题: {self.graph_problem.get_name()}")
        print(f"使用数学约束偏置: {'是' if self.use_mathematical_bias else '否'}")
        print("-" * 60)

        # 创建优化问题
        objective_func = self.create_objective_function()

        # 根据编码方式确定变量范围
        encoding = self.graph_problem.get_encoding()
        if encoding.value == "permutation":
            xl = 0.0
            xu = float(self.graph_problem.num_nodes - 1)
        elif encoding.value == "binary_edges":
            # 计算可能的边数
            num_edges = self.graph_problem.num_nodes * (self.graph_problem.num_nodes - 1) // 2
            xl = 0.0
            xu = 1.0
        else:
            xl = 0.0
            xu = 10.0

        problem = BlackBoxProblem(
            name=self.graph_problem.get_name(),
            n_var=self.graph_problem.num_nodes if encoding.value == "permutation" else self.graph_problem.num_nodes * (self.graph_problem.num_nodes - 1) // 2,
            n_obj=1,
            n_constr=0,
            xl=xl,
            xu=xu,
            function=objective_func
        )

        # 创建求解器
        solver = BlackBoxSolverNSGAII(problem)
        solver.population_size = population_size

        # 优化循环
        for gen in range(max_generations):
            solver.run(max_gen=1)

            # 获取当前最优解
            current_best = solver.population[0]
            current_objective = solver.objectives[0][0]

            # 验证解的有效性
            validation_result = self.graph_problem.validate_solution(current_best)

            if validation_result.is_valid:
                # 记录有效解
                self.history.append((gen, current_objective))
                if current_objective < self.best_objective:
                    self.best_solution = current_best.copy()
                    self.best_objective = current_objective
                    print(f"代数 {gen:3d}: 新的最优解 = {current_objective:.4f}")
            else:
                print(f"代数 {gen:3d}: 违反约束 - {validation_result.violation_type}")

        print("-" * 60)
        print(f"优化完成! 最优值: {self.best_objective:.4f}")

        return self.best_solution

    def analyze_solution(self):
        """分析最优解"""
        if self.best_solution is None:
            print("没有找到有效解")
            return

        print("\n" + "=" * 60)
        print("解分析")
        print("=" * 60)

        # 解码解
        decoded_solution = self.graph_problem.decode_solution(self.best_solution)
        print(f"解码后的解: {decoded_solution}")

        # 验证约束
        validation_result = self.graph_problem.validate_solution(self.best_solution)
        print(f"约束满足: {'✓ 是' if validation_result.is_valid else '✗ 否'}")

        # 评估目标
        objective_value = self.graph_problem.evaluate_solution(self.best_solution)
        print(f"目标函数值: {objective_value:.4f}")


def demo_tsp_with_mathematical_logic():
    """演示TSP的抽象框架与数学逻辑结合"""
    print("=" * 80)
    print("TSP：抽象框架 + 数学逻辑偏置")
    print("=" * 80)

    # 创建距离矩阵
    np.random.seed(42)
    num_cities = 10
    cities = np.random.rand(num_cities, 2) * 100

    distance_matrix = np.zeros((num_cities, num_cities))
    for i in range(num_cities):
        for j in range(num_cities):
            if i != j:
                distance_matrix[i, j] = np.linalg.norm(cities[i] - cities[j])

    # 使用工厂创建TSP问题
    tsp_problem = GraphProblemFactory.create_tsp(distance_matrix)

    print("TSP问题信息:")
    print(f"  城市数量: {num_cities}")
    print(f"  编码方式: {tsp_problem.get_encoding().value}")
    print(f"  图类型: {[t.value for t in tsp_problem.metadata.graph_type]}")

    # 创建优化器（使用数学约束）
    optimizer = AbstractGraphOptimizer(tsp_problem, use_mathematical_bias=True)

    # 执行优化
    best_solution = optimizer.optimize(max_generations=50, population_size=30)

    # 分析结果
    optimizer.analyze_solution()

    # 可视化结果
    if best_solution is not None:
        decoded = tsp_problem.decode_solution(best_solution)
        plt.figure(figsize=(10, 8))
        plt.scatter(cities[:, 0], cities[:, 1], c='red', s=100, zorder=5)
        for i, (x, y) in enumerate(cities):
            plt.annotate(str(i), (x, y), xytext=(5, 5), textcoords='offset points')

        # 绘制路径
        path_cities = [cities[i] for i in decoded] + [cities[decoded[0]]]
        path_x = [c[0] for c in path_cities]
        path_y = [c[1] for c in path_cities]
        plt.plot(path_x, path_y, 'b-', alpha=0.6, linewidth=2)

        total_distance = tsp_problem.evaluate_solution(best_solution)
        plt.title(f"TSP最优解\n总距离: {total_distance:.2f}")
        plt.show()


def demo_spanning_tree_with_mathematical_logic():
    """演示生成树的抽象框架与数学逻辑结合"""
    print("\n" + "=" * 80)
    print("生成树：抽象框架 + 数学逻辑偏置")
    print("=" * 80)

    # 创建生成树问题
    num_nodes = 8
    np.random.seed(123)

    # 生成随机边权重
    edge_weights = {}
    for i in range(num_nodes):
        for j in range(i + 1, num_nodes):
            edge_weights[(i, j)] = np.random.uniform(1, 10)

    # 使用工厂创建生成树问题
    tree_problem = GraphProblemFactory.create_spanning_tree(num_nodes, edge_weights)

    print("生成树问题信息:")
    print(f"  节点数量: {num_nodes}")
    print(f"  编码方式: {tree_problem.get_encoding().value}")
    print(f"  期望边数: {tree_problem.expected_edges}")
    print(f"  必须连通: {tree_problem.must_be_connected}")
    print(f"  必须无环: {tree_problem.must_be_acyclic}")

    # 创建优化器
    optimizer = AbstractGraphOptimizer(tree_problem, use_mathematical_bias=True)

    # 执行优化
    num_edges = num_nodes * (num_nodes - 1) // 2
    best_solution = optimizer.optimize(max_generations=30, population_size=20)

    # 分析结果
    optimizer.analyze_solution()

    # 展示找到的树
    if best_solution is not None:
        decoded_edges = tree_problem.decode_solution(best_solution)
        print(f"\n找到的生成树:")
        total_weight = 0.0
        for edge in decoded_edges:
            weight = edge_weights.get((min(edge), max(edge)), 1.0)
            total_weight += weight
            print(f"  边 {edge}: 权重 {weight:.2f}")
        print(f"总权重: {total_weight:.2f}")


def demo_graph_coloring_with_mathematical_logic():
    """演示图着色的抽象框架与数学逻辑结合"""
    print("\n" + "=" * 80)
    print("图着色：抽象框架 + 数学逻辑偏置")
    print("=" * 80)

    # 创建示例图的邻接矩阵
    adjacency_matrix = np.array([
        [0, 1, 1, 0, 1, 0],
        [1, 0, 1, 1, 0, 0],
        [1, 1, 0, 1, 1, 0],
        [0, 1, 1, 0, 1, 1],
        [1, 0, 1, 1, 0, 1],
        [0, 0, 0, 1, 1, 0]
    ])

    max_colors = 3

    # 使用工厂创建图着色问题
    coloring_problem = GraphProblemFactory.create_graph_coloring(
        adjacency_matrix, max_colors
    )

    print("图着色问题信息:")
    print(f"  节点数量: {coloring_problem.num_nodes}")
    print(f"  最大颜色数: {max_colors}")
    print(f"  编码方式: {coloring_problem.get_encoding().value}")

    # 创建优化器
    optimizer = AbstractGraphOptimizer(coloring_problem, use_mathematical_bias=True)

    # 执行优化
    best_solution = optimizer.optimize(max_generations=40, population_size=25)

    # 分析结果
    optimizer.analyze_solution()

    # 展示着色方案
    if best_solution is not None:
        colors = coloring_problem.decode_solution(best_solution)
        print(f"\n着色方案:")
        for i, color in enumerate(colors):
            print(f"  节点 {i}: 颜色 {color}")
        print(f"使用的颜色数: {len(set(colors))}")

        # 验证相邻节点颜色不同
        conflicts = 0
        for i in range(coloring_problem.num_nodes):
            for j in range(i + 1, coloring_problem.num_nodes):
                if adjacency_matrix[i, j] > 0 and colors[i] == colors[j]:
                    conflicts += 1
                    print(f"  冲突: 节点 {i} 和 {j} 都是颜色 {colors[i]}")

        if conflicts == 0:
            print("✓ 没有颜色冲突！")


def demo_composite_problem():
    """演示组合问题的抽象框架"""
    print("\n" + "=" * 80)
    print("组合问题：抽象框架 + 数学逻辑偏置")
    print("=" * 80)

    # 创建一个需要同时满足多个约束的组合问题
    num_nodes = 6

    # 子问题1：生成树约束
    tree_problem = GraphProblemFactory.create_spanning_tree(num_nodes)

    # 子问题2：二着色约束（树是二着色的）
    adjacency_matrix = np.array([
        [0, 1, 1, 0, 0, 0],
        [1, 0, 0, 1, 1, 0],
        [1, 0, 0, 0, 0, 0],
        [0, 1, 0, 0, 0, 1],
        [0, 1, 0, 0, 0, 1],
        [0, 0, 0, 1, 1, 0]
    ])
    coloring_problem = GraphProblemFactory.create_graph_coloring(adjacency_matrix, max_colors=2)

    # 创建组合问题
    composite_problem = CompositeGraphProblem([tree_problem, coloring_problem])

    print("组合问题信息:")
    print(f"  子问题数量: {len(composite_problem.subproblems)}")
    for i, problem in enumerate(composite_problem.subproblems):
        print(f"  子问题 {i + 1}: {problem.get_name()}")

    # 创建优化器
    optimizer = AbstractGraphOptimizer(composite_problem, use_mathematical_bias=True)

    # 执行优化
    best_solution = optimizer.optimize(max_generations=30, population_size=20)

    # 分析结果
    optimizer.analyze_solution()

    # 展示组合结果
    if best_solution is not None:
        print(f"\n组合解分析:")
        edges = tree_problem.decode_solution(best_solution)
        colors = coloring_problem.decode_solution(best_solution)

        print(f"选择的边: {edges}")
        print(f"着色方案: {colors}")

        # 验证每个子问题
        for i, problem in enumerate(composite_problem.subproblems):
            result = problem.validate_solution(best_solution)
            print(f"子问题 {i + 1}: {'✓ 满足' if result.is_valid else '✗ 违反'}")


def demonstrate_elegance():
    """演示抽象框架的优雅性"""
    print("\n" + "=" * 80)
    print("抽象框架的优雅性演示")
    print("=" * 80)

    print("""
    抽象框架 + 数学逻辑偏置的优势：

    1. 职责分离清晰
       - 抽象类：提供标准接口和数据结构
       - 数学逻辑：专注于约束验证和优化目标

    2. 代码复用性强
       - 相同的编码方式可以用于多个问题
       - 相同的约束逻辑可以用于不同编码

    3. 扩展性好
       - 新增问题类型只需继承抽象类
       - 组合多个问题成为可能

    4. 维护性高
       - 修改问题逻辑不影响框架
       - 修改框架不影响具体问题

    5. 可测试性强
       - 每个组件可以独立测试
       - 约束逻辑和优化逻辑分离
    """)

    # 演示快速创建不同问题
    print("\n快速创建不同图论问题示例:")

    # TSP
    distance_matrix = np.random.rand(5, 5)
    tsp = GraphProblemFactory.create_tsp(distance_matrix)

    # 生成树
    tree = GraphProblemFactory.create_spanning_tree(5)

    # 图着色
    adj_matrix = np.random.randint(0, 2, (5, 5))
    coloring = GraphProblemFactory.create_graph_coloring(adj_matrix, 3)

    problems = [tsp, tree, coloring]

    print(f"  TSP: {tsp.get_name()}")
    print(f"  生成树: {tree.get_name()}")
    print(f"  图着色: {coloring.get_name()}")

    print("\n所有问题都有统一的接口:")
    print("  - validate_solution(): 验证解的合法性")
    print("  - evaluate_solution(): 评估解的质量")
    print("  - decode_solution(): 解码解向量")
    print("  - get_encoding(): 获取编码方式")


def main():
    """主函数"""
    print("抽象图论框架与数学逻辑偏置结合示例")
    print("=" * 80)

    # 运行各种演示
    demo_tsp_with_mathematical_logic()
    demo_spanning_tree_with_mathematical_logic()
    demo_graph_coloring_with_mathematical_logic()
    demo_composite_problem()
    demonstrate_elegance()

    print("\n" + "=" * 80)
    print("总结")
    print("=" * 80)
    print("""
    抽象框架与数学逻辑偏置的结合体现了软件工程的最高原则：

    • 抽象提供结构，数学提供逻辑
    • 框架提供接口，逻辑提供实现
    • 复用提供效率，专精提供质量

    这确实是图论优化问题的优雅解决方案！
    """)


if __name__ == "__main__":
    main()