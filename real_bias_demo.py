"""
真正使用偏置系统的TSP演示
演示如何将数学逻辑封装到偏置系统中
"""

import sys
import os
import numpy as np

# 首先创建一个简单的偏置基类
class BaseBias:
    """偏置基类"""
    def __init__(self, name, weight=1.0):
        self.name = name
        self.weight = weight

    def compute(self, x, context=None):
        """计算偏置值"""
        raise NotImplementedError

class OptimizationContext:
    """优化上下文"""
    def __init__(self, generation, population_size, current_objective):
        self.generation = generation
        self.population_size = population_size
        self.current_objective = current_objective

# 数学逻辑偏置类
class TSPConstraintBias(BaseBias):
    """
    TSP约束偏置 - 将数学逻辑封装到偏置中
    这是真正的偏置系统使用方式
    """

    def __init__(self, num_cities, penalty_scale=1e6):
        super().__init__("tsp_constraint", 1.0)
        self.num_cities = num_cities
        self.penalty_scale = penalty_scale
        print(f"创建TSP约束偏置: 城市数={num_cities}, 惩罚尺度={penalty_scale}")

    def compute(self, x, context=None):
        """
        这是偏置的核心方法
        返回约束违反的惩罚值
        """
        # 第一步：解码为城市序列
        tour = np.round(x).astype(int)
        tour = np.clip(tour, 0, self.num_cities - 1)

        # 第二步：数学逻辑验证
        penalty = 0.0

        # 检查1：是否访问所有城市
        unique_cities = set(tour)
        if len(unique_cities) != self.num_cities:
            missing = set(range(self.num_cities)) - unique_cities
            penalty += self.penalty_scale
            if context:
                print(f"  [偏置] 检测到未访问城市: {missing}, 应用惩罚 {self.penalty_scale}")
            return penalty

        # 检查2：是否有重复访问
        if len(tour) != len(unique_cities):
            duplicates = [city for city in tour if tour.tolist().count(city) > 1]
            penalty += self.penalty_scale
            if context:
                print(f"  [偏置] 检测到重复访问: {duplicates}, 应用惩罚 {self.penalty_scale}")
            return penalty

        # 检查3：确保在有效范围内
        if any(city < 0 or city >= self.num_cities for city in tour):
            penalty += self.penalty_scale
            if context:
                print(f"  [偏置] 检测到超出范围的访问, 应用惩罚 {self.penalty_scale}")
            return penalty

        # 如果所有约束都满足，返回0（无惩罚）
        if context:
            print(f"  [偏置] 所有约束满足，无惩罚")
        return 0.0

class TSPDistanceBias(BaseBias):
    """
    TSP距离偏置 - 另一种偏置类型
    这个偏置计算路径距离（通常作为目标函数）
    """

    def __init__(self, distance_matrix):
        super().__init__("tsp_distance", 1.0)
        self.distance_matrix = distance_matrix
        print(f"创建TSP距离偏置: 矩阵形状={distance_matrix.shape}")

    def compute(self, x, context=None):
        """计算TSP路径距离"""
        tour = np.round(x).astype(int)
        tour = np.clip(tour, 0, self.distance_matrix.shape[0] - 1)

        total_distance = 0.0
        for i in range(len(tour)):
            j = (i + 1) % len(tour)
            total_distance += self.distance_matrix[tour[i], tour[j]]

        return total_distance

class BiasManager:
    """
    偏置管理器 - 管理多个偏置的组合
    这是偏置系统的核心组件
    """

    def __init__(self):
        self.biases = []

    def add_bias(self, bias, weight=1.0):
        """添加偏置"""
        bias.weight = weight
        self.biases.append(bias)
        print(f"  添加偏置: {bias.name} (权重={weight})")

    def compute_total_bias(self, x, context=None):
        """计算所有偏置的总和"""
        total = 0.0
        print(f"\n[偏置系统] 计算解 {x} 的总偏置值:")

        for bias in self.biases:
            bias_value = bias.compute(x, context)
            weighted_value = bias.weight * bias_value
            total += weighted_value
            print(f"  {bias.name}: {bias_value:.2f} (权重={bias.weight}) -> 贡献: {weighted_value:.2f}")

        print(f"[偏置系统] 总偏置值: {total:.2f}")
        return total

def main():
    print("=" * 70)
    print("真正的偏置系统TSP演示")
    print("演示如何将数学逻辑封装到偏置中")
    print("=" * 70)

    # 第一步：定义TSP问题
    print("\n1. 定义TSP问题")
    print("-" * 40)

    num_cities = 4
    distance_matrix = np.array([
        [0, 10, 15, 20],
        [10, 0, 35, 25],
        [15, 35, 0, 30],
        [20, 25, 30, 0]
    ])

    print(f"城市数量: {num_cities}")

    # 第二步：创建偏置系统
    print("\n2. 创建偏置系统")
    print("-" * 40)

    # 创建偏置管理器
    bias_manager = BiasManager()

    # 添加约束偏置（这是您提到的核心）
    constraint_bias = TSPConstraintBias(num_cities, penalty_scale=1e6)
    bias_manager.add_bias(constraint_bias, weight=1.0)

    # 添加距离偏置（作为目标函数）
    distance_bias = TSPDistanceBias(distance_matrix)
    bias_manager.add_bias(distance_bias, weight=1.0)

    print(f"偏置系统创建完成，包含 {len(bias_manager.biases)} 个偏置")

    # 第三步：测试偏置系统
    print("\n3. 测试偏置系统")
    print("-" * 40)

    test_solutions = [
        [0, 1, 2, 3],      # 有效解
        [0, 1, 2, 1],      # 重复访问
        [0, 1, 2, 4],      # 超出范围（会被裁剪）
        [1, 2, 3, 0],      # 有效解（不同顺序）
    ]

    best_solution = None
    best_value = float('inf')

    for i, sol in enumerate(test_solutions):
        x = np.array(sol, dtype=float)
        context = OptimizationContext(generation=1, population_size=100, current_objective=0.0)

        print(f"\n测试解 {i+1}: {sol}")
        print("=" * 50)

        # 使用偏置系统计算
        total_bias = bias_manager.compute_total_bias(x, context)

        # 判断是否是最优解
        if total_bias < 1e6:  # 小于惩罚尺度说明是有效解
            if total_bias < best_value:
                best_value = total_bias
                best_solution = x
                print(f"  ★ 新的最优解！")
        else:
            print(f"  ✗ 无效解（违反约束）")

    # 第四步：分析最优解
    print("\n4. 分析最优解")
    print("-" * 40)

    if best_solution is not None:
        print(f"找到最优解: {best_solution.tolist()}")
        print(f"最优值: {best_value:.2f}")

        # 验证约束
        context = OptimizationContext(generation=1, population_size=100, current_objective=best_value)
        constraint_penalty = constraint_bias.compute(best_solution, context)
        distance = distance_bias.compute(best_solution)

        print(f"\n最优解分析:")
        print(f"  路径距离: {distance:.2f}")
        print(f"  约束惩罚: {constraint_penalty:.2f}")
        print(f"  总目标值: {distance + constraint_penalty:.2f}")

        # 计算路径
        tour = np.round(best_solution).astype(int)
        print(f"  完整路径: {' -> '.join(map(str, tour))} -> {tour[0]}")
    else:
        print("未找到有效解")

    # 第五步：演示偏置系统的灵活性
    print("\n5. 偏置系统的灵活性")
    print("-" * 40)

    # 创建新的偏置管理器，只使用约束偏置
    print("\n场景1: 只使用约束偏置（纯约束验证）")
    constraint_only_manager = BiasManager()
    constraint_only_manager.add_bias(TSPConstraintBias(num_cities), weight=1.0)

    x = np.array([0, 1, 2, 1], dtype=float)  # 无效解
    context = OptimizationContext(generation=1, population_size=100, current_objective=0.0)

    penalty = constraint_only_manager.compute_total_bias(x, context)
    print(f"无效解的惩罚: {penalty:.0f}")

    # 场景2: 调整惩罚权重
    print("\n场景2: 调整约束权重")
    weighted_manager = BiasManager()
    weighted_manager.add_bias(TSPConstraintBias(num_cities, penalty_scale=5e5), weight=2.0)  # 更高的惩罚
    weighted_manager.add_bias(TSPDistanceBias(distance_matrix), weight=0.1)  # 降低距离权重

    penalty = weighted_manager.compute_total_bias(x, context)
    print(f"调整权重后的惩罚: {penalty:.0f}")

    print("\n" + "=" * 70)
    print("偏置系统演示总结")
    print("=" * 70)
    print("\n关键特点:")
    print("1. 偏置封装了数学逻辑")
    print("2. 偏置管理器组合多个偏置")
    print("3. 权重可以动态调整")
    print("4. 约束偏置实现了您提到的'只验证不引导'思想")
    print("5. 距离偏置计算目标函数值")
    print("\n这就是真正的偏置系统！")
    print("=" * 70)


if __name__ == "__main__":
    main()