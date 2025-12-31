"""
TSP图偏置演示 - 直接运行版本
"""

import sys
import os
import numpy as np

# 直接添加bias目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
bias_dir = os.path.join(current_dir, 'bias')
sys.path.insert(0, bias_dir)
sys.path.insert(0, current_dir)

def main():
    print("=" * 60)
    print("TSP 图偏置系统演示")
    print("抽象框架 + 数学逻辑偏置")
    print("=" * 60)

    try:
        # 直接导入核心模块
        from bias_base import BaseBias, OptimizationContext
        print("✓ 成功导入 bias_base")

        # 检查文件是否存在
        abstract_file = os.path.join(bias_dir, 'bias_graph_abstract.py')
        constraints_file = os.path.join(bias_dir, 'bias_graph_constraints.py')

        if os.path.exists(abstract_file):
            print("✓ bias_graph_abstract.py 文件存在")
        else:
            print("✗ bias_graph_abstract.py 文件不存在")

        if os.path.exists(constraints_file):
            print("✓ bias_graph_constraints.py 文件存在")
        else:
            print("✗ bias_graph_constraints.py 文件不存在")

        # 尝试导入
        try:
            from bias_graph_abstract import GraphProblemFactory
            print("✓ 成功导入 GraphProblemFactory")
        except Exception as e:
            print(f"✗ 导入 GraphProblemFactory 失败: {e}")
            # 创建一个简单的替代实现
            GraphProblemFactory = None

        try:
            from bias_graph_constraints import TSPConstraintBias
            print("✓ 成功导入 TSPConstraintBias")
        except Exception as e:
            print(f"✗ 导入 TSPConstraintBias 失败: {e}")
            # 创建一个简单的替代实现
            TSPConstraintBias = None

        # 创建一个简单的TSP偏置类
        class SimpleTSPBias(BaseBias):
            def __init__(self, num_cities, penalty_scale=1e6):
                super().__init__("simple_tsp", 1.0)
                self.num_cities = num_cities
                self.penalty_scale = penalty_scale

            def compute(self, x, context):
                # 验证是否是有效的TSP解
                perm = np.round(x).astype(int)
                perm = np.clip(perm, 0, self.num_cities - 1)

                # 检查是否有重复
                if len(set(perm)) != len(perm):
                    return self.penalty_scale

                # 检查是否访问了所有城市
                if len(set(perm)) != self.num_cities:
                    return self.penalty_scale

                return 0.0

        # 演示TSP约束验证
        print("\n演示TSP约束验证:")
        print("-" * 30)

        num_cities = 4
        distance_matrix = np.array([
            [0, 10, 15, 20],
            [10, 0, 35, 25],
            [15, 35, 0, 30],
            [20, 25, 30, 0]
        ])

        # 创建简单偏置
        tsp_bias = SimpleTSPBias(num_cities)
        print(f"创建TSP偏置成功: {tsp_bias.name}")

        # 测试不同的解
        test_solutions = [
            [0, 1, 2, 3],      # 有效解
            [0, 1, 2, 1],      # 重复城市
            [0, 1, 2, 4],      # 超出范围
            [1, 2, 3, 0],      # 有效解（不同顺序）
        ]

        for i, sol in enumerate(test_solutions):
            x = np.array(sol, dtype=float)
            penalty = tsp_bias.compute(x, OptimizationContext(1, 100, 0.0))
            status = "有效" if penalty == 0 else "无效"
            print(f"解 {i+1}: {sol} -> {status}")

        # 计算TSP距离的函数
        def calculate_tsp_distance(tour, distance_matrix):
            total = 0.0
            for i in range(len(tour)):
                j = (i + 1) % len(tour)
                total += distance_matrix[tour[i], tour[j]]
            return total

        # 演示距离计算
        print("\n演示距离计算:")
        print("-" * 30)

        valid_tours = [
            [0, 1, 2, 3],
            [0, 2, 1, 3],
            [1, 3, 2, 0]
        ]

        for tour in valid_tours:
            distance = calculate_tsp_distance(tour, distance_matrix)
            print(f"路径 {tour} -> 距离: {distance:.2f}")

        # 组合目标函数
        print("\n组合目标函数演示:")
        print("-" * 30)

        def combined_objective(x):
            # 计算距离
            tour = np.round(x).astype(int)
            tour = np.clip(tour, 0, num_cities - 1)
            distance = calculate_tsp_distance(tour, distance_matrix)

            # 应用约束
            penalty = tsp_bias.compute(x, OptimizationContext(1, 100, distance))

            return distance + penalty

        # 测试组合目标函数
        for sol in test_solutions:
            x = np.array(sol, dtype=float)
            objective_value = combined_objective(x)
            print(f"解 {sol} -> 目标值: {objective_value}")

        print("\n" + "=" * 60)
        print("演示完成!")
        print("\n核心思想:")
        print("1. 抽象框架提供标准接口和数据结构")
        print("2. 数学逻辑偏置只做约束验证，不做搜索引导")
        print("3. 两者的结合实现了代码复用与逻辑清晰的完美平衡")
        print("=" * 60)

    except Exception as e:
        print(f"运行错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()