"""
使用您项目中已有偏置系统的完整演示
"""

import sys
import os
import numpy as np

# 添加路径
bias_dir = os.path.join(os.path.dirname(__file__), 'bias')
sys.path.insert(0, bias_dir)
sys.path.insert(0, os.path.dirname(__file__))

# 导入您的类
try:
    from bias_base import BaseBias, OptimizationContext
    from bias_graph_constraints import (
        GraphConstraintBias, TSPConstraintBias, ValidationResult
    )
    IMPORTS_SUCCESS = True
    print("成功导入您的偏置类！")
except ImportError as e:
    print(f"导入错误: {e}")
    IMPORTS_SUCCESS = False

def main():
    print("=" * 60)
    print("使用您项目的偏置系统")
    print("直接引用 bias_base 和 bias_graph_constraints")
    print("=" * 60)

    if not IMPORTS_SUCCESS:
        print("\n无法导入必要的类，请检查文件路径")
        return

    # 1. 创建TSP问题
    print("\n1. TSP问题定义")
    print("-" * 40)

    num_cities = 4
    distance_matrix = np.array([
        [0, 10, 15, 20],
        [10, 0, 35, 25],
        [15, 35, 0, 30],
        [20, 25, 30, 0]
    ])

    print(f"城市数量: {num_cities}")

    # 2. 使用您的 TSPConstraintBias
    print("\n2. 使用您的 TSPConstraintBias")
    print("-" * 40)

    tsp_constraint = TSPConstraintBias(
        num_cities=num_cities,
        penalty_scale=1e6
    )
    print(f"创建 TSPConstraintBias: {tsp_constraint.name}")
    print(f"  城市数: {tsp_constraint.num_cities}")
    print(f"  惩罚尺度: {tsp_constraint.penalty_scale}")

    # 3. 测试不同的解
    print("\n3. 测试不同的解")
    print("-" * 40)

    test_solutions = [
        [0, 1, 2, 3],      # 有效解
        [0, 1, 2, 1],      # 重复城市
        [0, 1, 2, 4],      # 超出范围
        [1, 2, 3, 0],      # 有效解
    ]

    best_solution = None
    best_distance = float('inf')

    for i, sol in enumerate(test_solutions):
        x = np.array(sol, dtype=float)

        # 使用您的优化上下文
        context = OptimizationContext(
            generation=1,
            individual=x,
            population=[x]
        )

        # 使用您的偏置计算惩罚
        penalty = tsp_constraint.compute(x, context)

        # 使用您的验证方法
        validation = tsp_constraint.validate_constraints(x, context)

        print(f"\n解 {i+1}: {sol}")
        print(f"  有效: {'是' if validation.is_valid else '否'}")
        print(f"  惩罚: {penalty:.0f}")
        print(f"  违反类型: {validation.violation_type or '无'}")

        if validation.is_valid:
            # 计算距离
            tour = np.round(x).astype(int)
            tour = np.clip(tour, 0, num_cities - 1)

            distance = 0.0
            for j in range(len(tour)):
                k = (j + 1) % len(tour)
                distance += distance_matrix[tour[j], tour[k]]

            print(f"  距离: {distance:.2f}")

            if distance < best_distance:
                best_distance = distance
                best_solution = x

    # 4. 创建自定义偏置继承您的基类
    print("\n4. 自定义偏置继承您的 BaseBias")
    print("-" * 40)

    class MyDistanceBias(BaseBias):
        """继承您的BaseBias的距离偏置"""

        def __init__(self, distance_matrix):
            super().__init__("my_distance_bias", 1.0)
            self.distance_matrix = distance_matrix

        def compute(self, x, context):
            """实现您的抽象方法"""
            tour = np.round(x).astype(int)
            tour = np.clip(tour, 0, self.distance_matrix.shape[0] - 1)

            total = 0.0
            for i in range(len(tour)):
                j = (i + 1) % len(tour)
                total += self.distance_matrix[tour[i], tour[j]]

            return total

    # 创建并测试自定义偏置
    distance_bias = MyDistanceBias(distance_matrix)
    print(f"创建自定义偏置: {distance_bias.name}")

    # 测试
    x = np.array([0, 1, 2, 3], dtype=float)
    context = OptimizationContext(generation=1, individual=x)
    distance = distance_bias.compute(x, context)
    print(f"距离偏置计算结果: {distance:.2f}")

    # 5. 展示您设计的优雅性
    print("\n5. 您设计的优雅性")
    print("-" * 40)

    print("\nBaseBias 类特点:")
    print("  - 抽象基类设计")
    print("  - 统一的 compute 接口")
    print("  - 权重管理功能")
    print("  - 启用/禁用功能")

    print("\nGraphConstraintBias 特点:")
    print("  - 专注约束验证")
    print("  - ValidationResult 详细报告")
    print("  - 可配置惩罚尺度")
    print("  - 只验证不引导的哲学")

    print("\nTSPConstraintBias 实现:")
    print("  - 完整的TSP约束")
    print("  - 多编码支持")
    print("  - 详细的违反信息")
    print("  - 可扩展架构")

    # 6. 结果
    print("\n6. 最终结果")
    print("-" * 40)

    if best_solution is not None:
        tour = np.round(best_solution).astype(int)
        print(f"最优解: {best_solution.tolist()}")
        print(f"最优路径: {' -> '.join(map(str, tour))} -> {tour[0]}")
        print(f"最短距离: {best_distance:.2f}")

    print("\n" + "=" * 60)
    print("总结")
    print("=" * 60)
    print("\n您的偏置系统设计出色！")
    print("\n关键点:")
    print("1. 使用了真正的偏置类")
    print("2. 继承了您的基类")
    print("3. 实现了抽象方法")
    print("4. 使用了您的上下文")
    print("5. 完美展示了约束偏置思想")
    print("\n这就是您要的 - 使用您已有的类！")


if __name__ == "__main__":
    main()