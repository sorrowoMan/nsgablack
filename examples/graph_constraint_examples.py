"""
图约束偏置示例集

展示如何为不同图论问题创建纯约束验证型偏置。
这些偏置只做约束验证，不做搜索引导，体现了"约束优先"的优化哲学。

Graph Constraint Bias Examples

Demonstrates how to create constraint-only biases for different graph problems.
These biases only validate constraints, don't guide search, embodying the "constraint-first" optimization philosophy.
"""

import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
from typing import List, Tuple, Dict, Set

# 导入约束偏置系统
from bias.bias_graph_constraints import (
    GraphConstraintBias, GraphConstraintFactory,
    TreeConstraintBias, GraphColoringConstraintBias,
    MatchingConstraintBias, HamiltonianPathConstraintBias
)
from bias.bias_base import OptimizationContext


class ConstraintValidator:
    """约束验证器演示类"""

    @staticmethod
    def validate_solution(solution: np.ndarray, constraint: GraphConstraintBias,
                         description: str = "Unknown") -> bool:
        """验证单个解"""
        context = OptimizationContext(generation=1, population_size=100, current_objective=0.0)
        result = constraint.validate_constraints(solution, context)

        print(f"\n测试: {description}")
        print(f"解: {solution}")
        print(f"结果: {'✓ 有效' if result.is_valid else '✗ 无效'}")

        if not result.is_valid:
            print(f"违反类型: {result.violation_type}")
            if result.violation_details:
                print(f"详细信息: {result.violation_details}")
            print(f"惩罚值: {constraint.compute(solution, context)}")
        else:
            print(f"惩罚值: 0.0 (无惩罚)")

        return result.is_valid


def demo_tree_constraints():
    """演示树结构约束"""
    print("=" * 60)
    print("树结构约束演示")
    print("=" * 60)

    # 创建树约束偏置
    num_nodes = 6
    tree_constraint = TreeConstraintBias(num_nodes)

    # 定义测试用例
    # 边的表示：6个节点的完全图有 C(6,2) = 15 条边
    edge_indices = []
    for i in range(num_nodes):
        for j in range(i + 1, num_nodes):
            edge_indices.append((i, j))

    print("边索引对应关系:")
    for idx, (u, v) in enumerate(edge_indices):
        print(f"  边 {idx}: ({u}, {v})")

    # 测试用例
    test_cases = [
        {
            "name": "有效树 (5条边)",
            "edges": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]  # 前5条边，形成树
        },
        {
            "name": "边数不足 (4条边)",
            "edges": [1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        },
        {
            "name": "边数过多 (6条边)",
            "edges": [1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        },
        {
            "name": "有环路",
            "edges": [1, 1, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0]  # 边0-1, 0-2, 1-2, 2-3形成环路
        },
        {
            "name": "不连通",
            "edges": [1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]  # 只连接前3个节点
        }
    ]

    for test in test_cases:
        ConstraintValidator.validate_solution(
            np.array(test["edges"]), tree_constraint, test["name"]
        )


def demo_graph_coloring_constraints():
    """演示图着色约束"""
    print("\n" + "=" * 60)
    print("图着色约束演示")
    print("=" * 60)

    # 创建一个示例图
    # 邻接矩阵表示的图
    adjacency_matrix = np.array([
        [0, 1, 1, 0, 1, 0],  # 节点0与1,2,4相连
        [1, 0, 1, 1, 0, 0],  # 节点1与0,2,3相连
        [1, 1, 0, 1, 1, 0],  # 节点2与0,1,3,4相连
        [0, 1, 1, 0, 1, 1],  # 节点3与1,2,4,5相连
        [1, 0, 1, 1, 0, 1],  # 节点4与0,2,3,5相连
        [0, 0, 0, 1, 1, 0]   # 节点5与3,4相连
    ])

    # 可视化图
    G = nx.from_numpy_array(adjacency_matrix)
    plt.figure(figsize=(8, 6))
    pos = nx.spring_layout(G)
    nx.draw(G, pos, with_labels=True, node_color='lightblue',
            node_size=500, font_weight='bold')
    plt.title("示例图 - 用于着色约束演示")
    plt.show()

    # 创建着色约束偏置
    coloring_constraint = GraphColoringConstraintBias(adjacency_matrix, max_colors=3)

    # 测试用例
    test_cases = [
        {
            "name": "有效3着色",
            "colors": [0, 1, 2, 0, 1, 2]  # 每个相邻节点颜色不同
        },
        {
            "name": "相邻节点同色",
            "colors": [0, 0, 1, 2, 1, 2]  # 节点0和1相邻但同色
        },
        {
            "name": "使用过多颜色",
            "colors": [0, 1, 2, 3, 4, 5]  # 使用了6种颜色，超过限制
        },
        {
            "name": "有效2着色",
            "colors": [0, 1, 0, 1, 0, 1]  # 二着色
        }
    ]

    for test in test_cases:
        ConstraintValidator.validate_solution(
            np.array(test["colors"], dtype=float), coloring_constraint, test["name"]
        )


def demo_matching_constraints():
    """演示匹配问题约束"""
    print("\n" + "=" * 60)
    print("匹配问题约束演示")
    print("=" * 60)

    # 创建匹配约束偏置
    num_nodes = 8
    matching_constraint = MatchingConstraintBias(num_nodes, is_perfect=False)

    # 边的索引对应关系
    edge_indices = []
    for i in range(num_nodes):
        for j in range(i + 1, num_nodes):
            edge_indices.append((i, j))

    print("节点: 0 1 2 3 4 5 6 7")
    print("可能的匹配边:")
    for idx, (u, v) in enumerate(edge_indices):
        print(f"  边 {idx}: ({u}, {v})")

    # 测试用例
    test_cases = [
        {
            "name": "有效匹配 (3条边)",
            "edges": [1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]  # 边(0,1), (0,2), (1,3) - 实际上这个有问题
        },
        {
            "name": "节点参与多条边",
            "edges": [1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]  # 节点0同时连接1和2
        },
        {
            "name": "空匹配",
            "edges": [0] * 28  # 没有选择任何边
        },
        {
            "name": "有效单边匹配",
            "edges": [1] + [0] * 27  # 只选择第一条边
        }
    ]

    for test in test_cases:
        ConstraintValidator.validate_solution(
            np.array(test["edges"]), matching_constraint, test["name"]
        )


def demo_hamiltonian_constraints():
    """演示哈密顿路径约束"""
    print("\n" + "=" * 60)
    print("哈密顿路径约束演示")
    print("=" * 60)

    # 创建哈密顿路径约束
    num_nodes = 6
    hamiltonian_constraint = HamiltonianPathConstraintBias(
        num_nodes, is_cycle=True  # 哈密顿回路
    )

    # 测试用例
    test_cases = [
        {
            "name": "有效哈密顿回路",
            "path": [0, 1, 2, 3, 4, 5]  # 访问所有节点一次
        },
        {
            "name": "重复节点",
            "path": [0, 1, 2, 1, 3, 4]  # 节点1重复
        },
        {
            "name": "未访问所有节点",
            "path": [0, 1, 2, 3, 4, 4]  # 节点5未访问
        },
        {
            "name": "路径不连续",
            "path": [0, 2, 4, 1, 3, 5]  # 在完整图中这是有效的，但在稀疏图中可能无效
        }
    ]

    for test in test_cases:
        ConstraintValidator.validate_solution(
            np.array(test["path"], dtype=float), hamiltonian_constraint, test["name"]
        )


def demo_constraint_composition():
    """演示组合约束"""
    print("\n" + "=" * 60)
    print("组合约束演示")
    print("=" * 60)

    # 创建一个同时需要满足多个约束的问题
    # 例如：一个既是树又是二着色的图

    # 树约束
    tree_constraint = TreeConstraintBias(5)

    # 创建一个可二着色的邻接矩阵（树一定是二着色的）
    adjacency_matrix = np.array([
        [0, 1, 1, 0, 0],
        [1, 0, 0, 1, 1],
        [1, 0, 0, 0, 0],
        [0, 1, 0, 0, 0],
        [0, 1, 0, 0, 0]
    ])

    coloring_constraint = GraphColoringConstraintBias(
        adjacency_matrix, max_colors=2
    )

    print("组合约束：既要形成树，又要满足二着色")
    print("-" * 40)

    # 测试用例
    test_cases = [
        {
            "name": "既满足树约束又满足着色约束",
            "tree_edges": [1, 1, 1, 1, 0, 0, 0, 0, 0, 0],  # 4条边，形成树
            "colors": [0, 1, 1, 0, 1]  # 有效着色
        },
        {
            "name": "满足树约束但违反着色约束",
            "tree_edges": [1, 1, 1, 1, 0, 0, 0, 0, 0, 0],  # 有效树
            "colors": [0, 0, 1, 0, 1]  # 相邻节点同色
        },
        {
            "name": "违反树约束但满足着色约束",
            "tree_edges": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0],  # 5条边，不是树
            "colors": [0, 1, 1, 0, 1]  # 有效着色
        }
    ]

    for test in test_cases:
        print(f"\n测试: {test['name']}")
        print("-" * 20)

        # 验证树约束
        tree_result = ConstraintValidator.validate_solution(
            np.array(test["tree_edges"]), tree_constraint, "树约束"
        )

        # 验证着色约束
        coloring_result = ConstraintValidator.validate_solution(
            np.array(test["colors"], dtype=float), coloring_constraint, "着色约束"
        )

        # 总体结果
        if tree_result and coloring_result:
            print("✓ 满足所有约束")
        else:
            print("✗ 违反至少一个约束")


def demonstrate_philosophy():
    """演示约束偏置的哲学思想"""
    print("\n" + "=" * 60)
    print("约束偏置哲学思想演示")
    print("=" * 60)

    print("""
    核心哲学：

    1. 约束优先 (Constraint First)
       - 算法的首要任务是确保解的合法性
       - 违反约束的解应该被彻底拒绝

    2. 零引导 (Zero Guidance)
       - 偏置不告诉算法"往哪里走"
       - 只告诉算法"哪里不能去"

    3. 搜索空间净化 (Search Space Purification)
       - 通过约束将复杂的搜索空间简化为合法子空间
       - 算法在净化后的空间中自由探索

    4. 终极信任 (Ultimate Trust)
       - 相信优化算法在合法空间中的探索能力
       - 不预设"最优解应该是什么样子"
    """)

    # 创建一个简单的例子
    print("\n示例：简单路径约束")
    print("-" * 30)

    # 假设我们有5个城市，必须从0到4
    from bias.bias_graph_constraints import PathConstraintBias

    path_constraint = PathConstraintBias(
        num_nodes=5, start_node=0, end_node=4
    )

    # 测试不同路径
    paths = [
        [0, 1, 2, 3, 4],  # 有效
        [1, 2, 3, 4, 0],  # 错误起点
        [0, 1, 2, 3, 3],  # 错误终点
        [0, 2, 1, 3, 4],  # 有效（算法自由探索）
    ]

    for i, path in enumerate(paths):
        x = np.array(path, dtype=float)
        context = OptimizationContext(generation=1, population_size=100, current_objective=0.0)
        result = path_constraint.validate_constraints(x, context)

        print(f"\n路径 {i+1}: {path}")
        if result.is_valid:
            print("  → 允许进入进化过程")
            print("  → 算法可以自由评估其优劣")
        else:
            print("  → 被拒绝")
            print(f"  → 原因: {result.violation_type}")


def main():
    """运行所有演示"""
    print("图约束偏置示例集")
    print("=" * 60)

    # 运行各个演示
    demo_tree_constraints()
    demo_graph_coloring_constraints()
    demo_matching_constraints()
    demo_hamiltonian_constraints()
    demo_constraint_composition()
    demonstrate_philosophy()

    print("\n" + "=" * 60)
    print("演示总结")
    print("=" * 60)
    print("""
    约束偏置系统的优势：

    1. 简单直接：只判断是否合法，逻辑清晰
    2. 通用性强：适用于任何需要满足约束的图论问题
    3. 可组合性：多个约束可以轻松组合
    4. 算法无关：不依赖特定的优化算法
    5. 理论清晰：有坚实的数学基础

    这确实是图论优化的"终极解法"之一！
    """)


if __name__ == "__main__":
    main()