"""
简单图偏置示例

快速展示抽象框架与数学逻辑偏置的核心思想。

Simple Graph Bias Example

Quick demonstration of the core idea of abstract framework + mathematical logic bias.
"""

import sys
import os
# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

# 导入核心组件
from bias.bias_graph_abstract import GraphProblemFactory
from bias.bias_graph_constraints import TSPConstraintBias
from bias.bias_base import OptimizationContext

# 导入优化器
from core import BlackBoxSolverNSGAII
from core.problems import BlackBoxProblem


def quick_tsp_demo():
    """快速TSP演示 - 展示抽象+数学的完美结合"""

    print("🎯 快速TSP演示：抽象框架 + 数学逻辑偏置")
    print("=" * 60)

    # 第一步：使用抽象框架定义问题
    print("\n1️⃣ 抽象框架定义问题")
    print("-" * 30)

    # 创建简单的4城市TSP
    distance_matrix = np.array([
        [0, 10, 15, 20],
        [10, 0, 35, 25],
        [15, 35, 0, 30],
        [20, 25, 30, 0]
    ])

    # 一行代码创建TSP问题
    tsp = GraphProblemFactory.create_tsp(distance_matrix)
    print(f"✅ 创建了TSP问题: {tsp.get_name()}")
    print(f"   城市数: {tsp.num_nodes}")
    print(f"   编码: {tsp.get_encoding().value}")

    # 第二步：使用数学逻辑创建约束
    print("\n2️⃣ 数学逻辑创建约束")
    print("-" * 30)

    # 一行代码创建数学约束
    constraint = TSPConstraintBias(tsp.num_nodes)
    print(f"✅ 创建了数学约束: {constraint.name}")

    # 演示数学约束的验证逻辑
    print("\n📐 数学约束验证演示:")
    test_solutions = [
        [0, 1, 2, 3],      # ✅ 有效
        [0, 1, 2, 1],      # ❌ 重复城市1
        [0, 1, 2, 4],      # ❌ 超出范围
    ]

    for i, sol in enumerate(test_solutions):
        x = np.array(sol, dtype=float)
        result = constraint.validate_constraints(
            x, OptimizationContext(generation=1, population_size=100, current_objective=0.0)
        )
        status = "✅ 有效" if result.is_valid else "❌ 无效"
        print(f"   解 {i+1}: {sol} -> {status}")
        if not result.is_valid:
            print(f"          原因: {result.violation_type}")

    # 第三步：抽象+数学的结合
    print("\n3️⃣ 抽象框架 + 数学逻辑 结合")
    print("-" * 30)

    def combined_objective(x: np.ndarray) -> float:
        """完美的结合：抽象评估目标，数学验证约束"""
        # 🎯 抽象框架：计算目标值
        objective_value = tsp.evaluate_solution(x)

        # 📐 数学逻辑：验证约束并应用惩罚
        constraint_penalty = constraint.compute(
            x, OptimizationContext(generation=1, population_size=100, current_objective=objective_value)
        )

        return objective_value + constraint_penalty

    print("✅ 创建了结合的目标函数")
    print("   - 抽象框架计算路径长度")
    print("   - 数学逻辑验证TSP约束")
    print("   - 违反约束获得无穷大惩罚")

    # 第四步：优化求解
    print("\n4️⃣ 执行优化")
    print("-" * 30)

    # 创建优化问题
    problem = BlackBoxProblem(
        name="tsp_abstract_plus_math",
        n_var=4,
        n_obj=1,
        n_constr=0,
        xl=0.0,
        xu=3.0,
        function=combined_objective
    )

    # 求解
    solver = BlackBoxSolverNSGAII(problem)
    solver.population_size = 20

    print("开始优化...")
    solver.run(max_gen=20)

    # 分析结果
    print("\n5️⃣ 结果分析")
    print("-" * 30)

    best_valid_solution = None
    best_distance = float('inf')

    for solution in solver.population:
        # 使用抽象框架验证
        if tsp.validate_solution(solution).is_valid:
            distance = tsp.evaluate_solution(solution)
            if distance < best_distance:
                best_distance = distance
                best_valid_solution = solution

    if best_valid_solution is not None:
        tour = tsp.decode_solution(best_valid_solution)
        print(f"✅ 找到有效解!")
        print(f"   最优路径: {' → '.join(map(str, tour))} → {tour[0]}")
        print(f"   路径长度: {best_distance:.2f}")
    else:
        print("❌ 未找到有效解")

    # 第六步：展示优雅性
    print("\n6️⃣ 抽象框架的优雅性")
    print("-" * 30)

    print("🏗️  抽象框架的优势:")
    print("   • 统一的接口（validate_solution, evaluate_solution, decode_solution）")
    print("   • 标准的数据结构（元数据、编码方式）")
    print("   • 工厂模式快速创建问题")

    print("\n📐 数学逻辑的优势:")
    print("   • 纯粹的约束验证逻辑")
    print("   • 严谨的数学公式驱动")
    print("   • 零搜索引导，只做合法性判断")

    print("\n🎯 结合的优势:")
    print("   • 职责分离清晰")
    print("   • 代码复用性高")
    print("   • 易于维护和扩展")


def demonstrate_reusability():
    """演示复用性"""

    print("\n\n🔄 复用性演示")
    print("=" * 60)

    print("\n同一段数学逻辑可以用于不同编码的TSP问题:")

    # 不同的TSP实例
    distance_matrices = [
        np.array([[0, 1, 2], [1, 0, 3], [2, 3, 0]]),    # 3城市
        np.array([[0, 1, 2, 3], [1, 0, 4, 5], [2, 4, 0, 6], [3, 5, 6, 0]]),  # 4城市
    ]

    for i, dist_matrix in enumerate(distance_matrices):
        # 使用相同的抽象框架
        tsp = GraphProblemFactory.create_tsp(dist_matrix)
        print(f"\nTSP实例 {i+1}: {tsp.num_nodes} 个城市")

        # 使用相同的数学逻辑（调整城市数）
        constraint = TSPConstraintBias(tsp.num_nodes)

        # 测试相同的验证逻辑
        test_solution = np.array([0, 1, 2, 3][:tsp.num_nodes], dtype=float)
        result = constraint.validate_constraints(
            test_solution, OptimizationContext(generation=1, population_size=100, current_objective=0.0)
        )
        print(f"   解验证: {'✅ 有效' if result.is_valid else '❌ 无效'}")

    print("\n✅ 数学逻辑完全复用，抽象框架自动适应不同问题规模！")


def show_elegance():
    """展示设计的优雅性"""

    print("\n\n💎 设计优雅性展示")
    print("=" * 60)

    print("""
    这个设计的优雅之处：

    1. 🎯 抽象层提供标准接口
       - 所有图论问题都有相同的方法签名
       - 统一的数据结构和元数据管理

    2. 📐 数学层专注于约束
       - 纯粹的数学逻辑，不受框架束缚
       - 可以独立测试和验证

    3. 🔄 完美的结合
       - 抽象框架计算目标值
       - 数学逻辑验证约束
       - 两者的职责边界清晰

    4. 🚀 极高的复用性
       - 相同的约束逻辑可用于不同问题
       - 相同的框架可用于不同约束

    5. 🛠️ 易于扩展
       - 新问题只需继承抽象类
       - 新约束只需实现验证逻辑

    这确实是抽象框架与数学逻辑的完美结合！
    """)


def main():
    """主函数"""
    quick_tsp_demo()
    demonstrate_reusability()
    show_elegance()

    print("\n" + "=" * 60)
    print("🎉 简单示例完成！")
    print("\n您已经看到了抽象框架与数学逻辑偏置的完美结合！")
    print("=" * 60)


if __name__ == "__main__":
    main()