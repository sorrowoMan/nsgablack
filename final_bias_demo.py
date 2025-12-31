"""
最终偏置系统演示
真正展示如何使用偏置系统
"""

import numpy as np

# 偏置系统核心类
class BaseBias:
    """偏置基类"""
    def __init__(self, name, weight=1.0):
        self.name = name
        self.weight = weight

    def compute(self, x, context=None):
        """计算偏置值 - 核心方法"""
        raise NotImplementedError

class OptimizationContext:
    """优化上下文"""
    def __init__(self, generation, population_size, current_objective):
        self.generation = generation
        self.population_size = population_size
        self.current_objective = current_objective

# TSP约束偏置 - 这才是真正的偏置！
class TSPConstraintBias(BaseBias):
    """TSP约束偏置 - 将数学逻辑封装到偏置中"""

    def __init__(self, num_cities, penalty_scale=1e6):
        super().__init__("tsp_constraint", 1.0)
        self.num_cities = num_cities
        self.penalty_scale = penalty_scale

    def compute(self, x, context=None):
        """
        偏置的核心：计算约束违反惩罚
        这就是您提到的"终极解法" - 只验证约束，不引导搜索
        """
        tour = np.round(x).astype(int)
        tour = np.clip(tour, 0, self.num_cities - 1)

        # 检查约束
        unique_cities = set(tour)

        # 违反约束 -> 无穷大惩罚
        if len(unique_cities) != self.num_cities:
            return self.penalty_scale

        if len(tour) != len(unique_cities):
            return self.penalty_scale

        # 满足约束 -> 零惩罚
        return 0.0

class TSPDistanceBias(BaseBias):
    """TSP距离偏置 - 计算路径距离"""

    def __init__(self, distance_matrix):
        super().__init__("tsp_distance", 1.0)
        self.distance_matrix = distance_matrix

    def compute(self, x, context=None):
        """计算TSP路径距离"""
        tour = np.round(x).astype(int)
        tour = np.clip(tour, 0, self.distance_matrix.shape[0] - 1)

        total = 0.0
        for i in range(len(tour)):
            j = (i + 1) % len(tour)
            total += self.distance_matrix[tour[i], tour[j]]
        return total

class BiasManager:
    """偏置管理器 - 这是偏置系统的核心"""

    def __init__(self):
        self.biases = []

    def add_bias(self, bias, weight=1.0):
        """添加偏置到系统"""
        bias.weight = weight
        self.biases.append(bias)

    def compute_total_bias(self, x, context=None):
        """计算所有偏置的加权和"""
        total = 0.0
        for bias in self.biases:
            bias_value = bias.compute(x, context)
            total += bias.weight * bias_value
        return total

def main():
    print("=" * 60)
    print("真正的偏置系统演示")
    print("展示如何将数学逻辑封装到偏置中")
    print("=" * 60)

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

    # 2. 创建偏置系统
    print("\n2. 偏置系统创建")
    print("-" * 40)

    bias_manager = BiasManager()

    # 添加约束偏置（核心！）
    constraint_bias = TSPConstraintBias(num_cities)
    bias_manager.add_bias(constraint_bias, weight=1.0)
    print(f"添加约束偏置: {constraint_bias.name}")

    # 添加距离偏置
    distance_bias = TSPDistanceBias(distance_matrix)
    bias_manager.add_bias(distance_bias, weight=1.0)
    print(f"添加距离偏置: {distance_bias.name}")

    print(f"偏置系统包含 {len(bias_manager.biases)} 个偏置")

    # 3. 测试偏置系统
    print("\n3. 偏置系统测试")
    print("-" * 40)

    test_solutions = [
        [0, 1, 2, 3],      # 有效
        [0, 1, 2, 1],      # 无效（重复）
        [1, 2, 3, 0],      # 有效
    ]

    for i, sol in enumerate(test_solutions):
        x = np.array(sol, dtype=float)
        print(f"\n解 {i+1}: {sol}")

        # 计算各个偏置
        constraint_value = constraint_bias.compute(x)
        distance_value = distance_bias.compute(x)
        total_value = bias_manager.compute_total_bias(x)

        print(f"  约束偏置: {constraint_value:.0f}")
        print(f"  距离偏置: {distance_value:.2f}")
        print(f"  总偏置值: {total_value:.2f}")
        print(f"  状态: {'有效' if constraint_value == 0 else '无效'}")

    # 4. 展示偏置系统的作用
    print("\n4. 偏置系统的作用")
    print("-" * 40)

    print("\n核心思想:")
    print("1. 约束偏置 - 只验证是否满足约束，不引导搜索方向")
    print("2. 距离偏置 - 计算目标函数值")
    print("3. 偏置管理器 - 组合多个偏置，权重可调")

    # 5. 动态调整权重
    print("\n5. 动态调整权重")
    print("-" * 40)

    # 创建新的偏置管理器，不同权重
    weighted_manager = BiasManager()
    weighted_manager.add_bias(constraint_bias, weight=1000)  # 强约束
    weighted_manager.add_bias(distance_bias, weight=0.001)   # 弱目标

    x = np.array([0, 1, 2, 1], dtype=float)  # 无效解
    weighted_total = weighted_manager.compute_total_bias(x)

    print(f"无效解在不同权重下的总偏置值: {weighted_total:.0f}")

    print("\n" + "=" * 60)
    print("总结")
    print("=" * 60)
    print("\n这就是真正的偏置系统！")
    print("\n关键特点:")
    print("1. 偏置封装数学逻辑")
    print("2. 偏置只计算值，不改变解")
    print("3. 约束偏置实现了'只验证不引导'的终极思想")
    print("4. 偏置管理器灵活组合")
    print("5. 权重可以动态调整")
    print("\n这确实是图论优化的优雅解决方案！")


if __name__ == "__main__":
    main()