"""
实验2：混合变量优化 - 完整实现

测试问题：
1. 供应链网络设计（连续+整数+分类）
2. 车辆路径问题（连续+整数+排列）
"""

import numpy as np
from typing import List, Tuple, Dict, Any
from dataclasses import dataclass


class MixedVariableProblem:
    """混合变量问题基类"""

    def __init__(self, name: str):
        self.name = name

    def evaluate(self, x: np.ndarray) -> float:
        """评估混合变量解"""
        raise NotImplementedError


class SupplyChainDesign(MixedVariableProblem):
    """
    供应链网络设计问题

    变量：
    - 连续：仓库容量、运输量
    - 整数：仓库数量、车辆数量
    - 分类：供应商选择
    """

    def __init__(self):
        super().__init__("Supply_Chain_Design")
        self.n_continuous = 10  # 仓库容量
        self.n_integer = 5      # 设施数量
        self.n_categorical = 3  # 供应商选择

        self.dimension = self.n_continuous + self.n_integer + self.n_categorical

        # 需求数据
        self.demands = np.random.rand(10) * 100

        # 成本系数
        self.fixed_cost = 1000
        self.variable_cost = 10
        self.transport_cost = 5

    def evaluate(self, x: np.ndarray) -> float:
        """
        解码并评估供应链设计

        x = [连续变量, 整数变量, 分类变量]
        """
        # 解码
        continuous = x[:self.n_continuous]
        integer = np.round(x[self.n_continuous:self.n_continuous+self.n_integer]).astype(int)
        categorical = x[self.n_continuous+self.n_integer:]

        # 目标函数：总成本
        # 1. 设施固定成本
        n_facilities = integer[0]
        fixed_cost = n_facilities * self.fixed_cost

        # 2. 运营成本（基于容量）
        capacity_cost = np.sum(continuous * self.variable_cost)

        # 3. 运输成本
        transport_cost = np.sum(continuous * self.transport_cost)

        # 4. 供应商选择成本
        supplier_cost = np.sum(categorical) * 500

        total_cost = fixed_cost + capacity_cost + transport_cost + supplier_cost

        # 约束惩罚
        penalty = 0.0

        # 容量约束
        if np.sum(continuous) < np.sum(self.demands):
            penalty += (np.sum(self.demands) - np.sum(continuous))**2 * 10

        # 设施数量约束
        if n_facilities < 2 or n_facilities > 10:
            penalty += abs(n_facilities - 5) * 1000

        # 供应商约束
        if np.any(categorical < 0) or np.any(categorical > 4):
            penalty += 10000

        return total_cost + penalty

    def decode(self, x: np.ndarray) -> Dict[str, Any]:
        """解码混合变量"""
        continuous = x[:self.n_continuous]
        integer = np.round(x[self.n_continuous:self.n_continuous+self.n_integer]).astype(int)
        categorical = x[self.n_continuous+self.n_integer:]

        return {
            'continuous': continuous,
            'integer': integer,
            'categorical': categorical
        }


class VehicleRoutingProblem(MixedVariableProblem):
    """
    车辆路径问题（VRP）

    变量：
    - 连续：出发时间
    - 整数：车辆数量
    - 排列：客户访问顺序
    """

    def __init__(self, n_customers=20):
        super().__init__("Vehicle_Routing")
        self.n_customers = n_customers

        # 生成客户位置
        self.coordinates = np.random.rand(n_customers, 2) * 100

        # 需求量
        self.demands = np.random.rand(n_customers) * 50 + 10

        # 时间窗
        self.time_windows = [(0, 100) for _ in range(n_customers)]

        self.dimension = 1 + 1 + n_customers  # 出发时间 + 车辆数 + 排列

    def evaluate(self, x: np.ndarray) -> float:
        """
        评估VRP解

        x = [出发时间, 车辆数, 客户排列]
        """
        # 解码
        departure_time = x[0]
        n_vehicles = int(round(x[1]))
        route_order = x[2:]

        # 确保排列索引有效
        route_order = np.argsort(route_order)  # 转换为排列索引

        # 计算总距离
        total_distance = 0.0

        # 分配客户到车辆
        customers_per_vehicle = len(route_order) // max(1, n_vehicles)

        current_location = np.array([50.0, 50.0])  # 仓库位置

        for v in range(n_vehicles):
            start_idx = v * customers_per_vehicle
            end_idx = start_idx + customers_per_vehicle if v < n_vehicles - 1 else len(route_order)

            for i in range(start_idx, end_idx):
                customer_idx = int(route_order[i]) % self.n_customers
                customer_loc = self.coordinates[customer_idx]

                # 计算距离
                distance = np.linalg.norm(current_location - customer_loc)
                total_distance += distance

                current_location = customer_loc

            # 返回仓库
            total_distance += np.linalg.norm(current_location - np.array([50.0, 50.0]))
            current_location = np.array([50.0, 50.0])

        # 约束惩罚
        penalty = 0.0

        # 时间窗约束
        current_time = departure_time
        for customer_idx in route_order[:5]:  # 只检查前5个
            customer_idx = int(customer_idx) % self.n_customers
            tw_start, tw_end = self.time_windows[customer_idx]

            if current_time < tw_start or current_time > tw_end:
                penalty += abs(current_time - tw_end) * 10

            current_time += 10  # 服务时间

        # 车辆容量约束
        if n_vehicles < 2 or n_vehicles > 10:
            penalty += abs(n_vehicles - 5) * 100

        return total_distance + penalty


class EngineeringDesign(MixedVariableProblem):
    """
    工程设计问题（压力容器+梁设计）

    混合变量：连续尺寸 + 离散材料选择
    """

    def __init__(self):
        super().__init__("Engineering_Design")
        self.n_continuous = 4  # 尺寸参数
        self.n_discrete = 2    # 材料选择

        self.dimension = self.n_continuous + self.n_discrete

        # 材料属性
        self.materials = {
            0: {'density': 7.85, 'strength': 250, 'cost': 1.0},
            1: {'density': 2.70, 'strength': 150, 'cost': 1.5},
            2: {'density': 8.0, 'strength': 300, 'cost': 2.0},
        }

    def evaluate(self, x: np.ndarray) -> float:
        """
        评估工程设计

        x = [尺寸参数, 材料选择]
        """
        # 解码
        dimensions = x[:self.n_continuous]
        material_indices = np.round(x[self.n_continuous:]).astype(int) % 3

        # 目标函数：总成本
        # 1. 材料成本
        material_cost = sum(self.materials[int(mi)]['cost']
                           for mi in material_indices)

        # 2. 重量成本
        volume = np.prod(dimensions)
        avg_density = np.mean([self.materials[int(mi)]['density']
                              for mi in material_indices])
        weight = volume * avg_density

        # 3. 性能惩罚
        penalty = 0.0

        # 强度约束
        avg_strength = np.mean([self.materials[int(mi)]['strength']
                               for mi in material_indices])
        required_strength = 200

        if avg_strength < required_strength:
            penalty += (required_strength - avg_strength) ** 2 * 10

        # 尺寸约束
        for dim in dimensions:
            if dim < 0.1 or dim > 10.0:
                penalty += 1000

        return material_cost + weight * 0.01 + penalty


# 实验运行器
class MixedVariableExperiment:
    """混合变量优化实验"""

    def __init__(self):
        self.problems = [
            SupplyChainDesign(),
            VehicleRoutingProblem(n_customers=15),
            EngineeringDesign()
        ]

    def run_quick_test(self):
        """快速测试"""
        print("=" * 70)
        print("实验2：混合变量优化 - 快速测试")
        print("=" * 70)

        for problem in self.problems:
            print(f"\n问题: {problem.name}")
            print(f"  维度: {problem.dimension}")

            # 测试评估
            x = np.random.randn(problem.dimension)
            fitness = problem.evaluate(x)

            print(f"  测试适应度: {fitness:.6f}")

            if hasattr(problem, 'decode'):
                decoded = problem.decode(x)
                print(f"  解码:")
                for key, val in decoded.items():
                    print(f"    {key}: {type(val).__name__} {val[:5] if hasattr(val, '__len__') else val}")

        print("\n" + "=" * 70)
        print("测试完成！")
        print("=" * 70)


if __name__ == "__main__":
    experiment = MixedVariableExperiment()
    experiment.run_quick_test()
