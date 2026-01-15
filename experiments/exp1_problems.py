"""
实验1：昂贵黑箱优化 - 测试问题定义

包含多个昂贵评估的优化问题：
1. 有限元仿真优化
2. CEC基准测试（昂贵版本）
3. 计算密集型函数
"""

import time
import numpy as np
from typing import Tuple, List
from abc import ABC, abstractmethod


class ExpensiveOptimizationProblem(ABC):
    """昂贵优化问题基类"""

    def __init__(self, dimension: int, evaluation_cost: float = 0.1):
        """
        Args:
            dimension: 问题维度
            evaluation_cost: 每次评估的时间成本（秒）
        """
        self.dimension = dimension
        self.evaluation_cost = evaluation_cost
        self.evaluation_count = 0
        self.total_time = 0.0

    @abstractmethod
    def _evaluate_core(self, x: np.ndarray) -> float:
        """核心评估逻辑（子类实现）"""
        pass

    def evaluate(self, x: np.ndarray) -> float:
        """
        评估解（包含时间成本）

        Args:
            x: 解向量

        Returns:
            目标函数值
        """
        start_time = time.time()
        self.evaluation_count += 1

        # 模拟昂贵评估
        time.sleep(self.evaluation_cost)

        # 核心评估
        fitness = self._evaluate_core(x)

        elapsed = time.time() - start_time
        self.total_time += elapsed

        return fitness

    def get_bounds(self) -> List[Tuple[float, float]]:
        """获取变量边界"""
        return [(-5.0, 5.0) for _ in range(self.dimension)]

    def reset_counters(self):
        """重置计数器"""
        self.evaluation_count = 0
        self.total_time = 0.0


class FiniteElementOptimization(ExpensiveOptimizationProblem):
    """
    有限元仿真优化问题

    模拟结构优化，单次评估需要调用FEA软件（这里用计算密集型函数模拟）
    """

    def __init__(self, dimension: int = 30, evaluation_cost: float = 0.1):
        super().__init__(dimension, evaluation_cost)
        self.name = "Finite_Element"

    def _evaluate_core(self, x: np.ndarray) -> float:
        """
        模拟有限元分析的目标函数

        特点：
        - 多峰
        - 复杂的相互作用
        - 计算密集
        """
        result = 0.0

        # 主目标：类似Rastrigin但更复杂
        n = len(x)
        result += 10 * n
        result += np.sum(x**2 - 10 * np.cos(2 * np.pi * x))

        # 添加复杂的交叉项（模拟结构耦合）
        for i in range(n - 1):
            result += 0.5 * (x[i]**2 * x[i+1]**2)

        # 添加非线性项
        result += np.sum(np.sin(x**3))

        # 约束惩罚（模拟应力约束）
        penalty = 0.0
        for i in range(n):
            if abs(x[i]) > 4.0:
                penalty += (abs(x[i]) - 4.0)**2 * 100

        return result + penalty


class CEC2017Expensive(ExpensiveOptimizationProblem):
    """
    CEC 2017基准测试函数（昂贵版本）

    使用Shifted and Rotated Benchmark Functions
    """

    def __init__(self, function_id: int = 1, dimension: int = 30, evaluation_cost: float = 0.05):
        super().__init__(dimension, evaluation_cost)
        self.function_id = function_id
        self.name = f"CEC2017_F{function_id}"

        # 预定义的偏移和旋转矩阵（简化版）
        self.shift = np.random.randn(dimension) * 2
        self.rotation_matrix = self._generate_rotation_matrix(dimension)

    def _generate_rotation_matrix(self, n: int) -> np.ndarray:
        """生成旋转矩阵（简化版）"""
        # 使用正交矩阵
        Q, _ = np.linalg.qr(np.random.randn(n, n))
        return Q

    def _evaluate_core(self, x: np.ndarray) -> float:
        """CEC 2017函数实现"""
        # 应用偏移和旋转
        x_shifted = x - self.shift
        x_rotated = np.dot(self.rotation_matrix, x_shifted)

        if self.function_id == 1:
            # Shifted Sphere Function
            return np.sum(x_rotated**2)

        elif self.function_id == 2:
            # Shifted Rosenbrock
            return sum(100 * (x_rotated[i]**2 - x_rotated[i+1])**2 +
                      (x_rotated[i] - 1)**2
                      for i in range(len(x) - 1))

        elif self.function_id == 3:
            # Shifted Rastrigin
            n = len(x_rotated)
            return 10 * n + np.sum(x_rotated**2 -
                                   10 * np.cos(2 * np.pi * x_rotated))

        else:
            # 默认：混合函数
            sphere_part = np.sum(x_rotated[:self.dimension//2]**2)
            rastrigin_part = 10 * self.dimension//2 + np.sum(
                x_rotated[self.dimension//2:]**2 -
                10 * np.cos(2 * np.pi * x_rotated[self.dimension//2:])
            )
            return sphere_part + rastrigin_part


class ComputationalFluidDynamics(ExpensiveOptimizationProblem):
    """
    计算流体力学优化问题

    模拟CFD仿真优化（如翼型优化）
    """

    def __init__(self, dimension: int = 20, evaluation_cost: float = 0.15):
        super().__init__(dimension, evaluation_cost)
        self.name = "CFD_Simulation"

    def _evaluate_core(self, x: np.ndarray) -> float:
        """
        模拟CFD优化目标

        目标：最小化阻力 + 保持升力
        """
        # 阻力系数（主要目标）
        drag = 0.0
        for i in range(len(x)):
            drag += x[i]**2 * (1 + 0.1 * np.sin(x[i] * 10))

        # 升力系数（约束）
        lift = np.sum(x) * 0.5
        target_lift = 10.0

        # 阻力-升力权衡
        if lift < target_lift * 0.9:
            # 升力不足，重惩罚
            penalty = (target_lift * 0.9 - lift)**2 * 100
        else:
            penalty = 0.0

        # 添加复杂的非线性项（模拟流体动力学）
        for i in range(len(x) - 1):
            drag += 0.1 * x[i] * x[i+1] * np.cos(x[i] + x[i+1])

        return drag + penalty


class CircuitDesignOptimization(ExpensiveOptimizationProblem):
    """
    电路设计优化问题

    模拟电路仿真优化（SPICE-like）
    """

    def __init__(self, dimension: int = 15, evaluation_cost: float = 0.08):
        super().__init__(dimension, evaluation_cost)
        self.name = "Circuit_Design"

    def _evaluate_core(self, x: np.ndarray) -> float:
        """
        模拟电路设计优化

        目标：最小化功耗 + 满足性能要求
        """
        # 功耗
        power = np.sum(x**2)

        # 性能指标（增益、带宽等）
        gain = np.prod(1 + 0.1 * x[:5])
        bandwidth = np.sum(x[5:10])

        # 目标性能
        target_gain = 2.0
        target_bandwidth = 10.0

        # 性能惩罚
        gain_penalty = max(0, target_gain - gain) ** 2 * 50
        bandwidth_penalty = max(0, target_bandwidth - bandwidth) ** 2 * 50

        # 交叉项（模拟电路耦合）
        coupling = 0.0
        for i in range(min(10, len(x) - 1)):
            coupling += 0.05 * x[i] * x[i+1]

        return power + gain_penalty + bandwidth_penalty + coupling


class MixedExpensiveBenchmark(ExpensiveOptimizationProblem):
    """
    混合昂贵基准测试

    组合多个复杂特性
    """

    def __init__(self, dimension: int = 25, evaluation_cost: float = 0.12):
        super().__init__(dimension, evaluation_cost)
        self.name = "Mixed_Expensive"

    def _evaluate_core(self, x: np.ndarray) -> float:
        """混合复杂特性"""
        n = len(x)

        # 1. 全局结构（Sphere-like）
        global_term = np.sum(x**2)

        # 2. 局部震荡（Rastrigin-like）
        local_term = 10 * n + np.sum(x**2 - 10 * np.cos(2 * np.pi * x))

        # 3. 非凸地形（Rosenbrock-like）
        nonconvex_term = sum(100 * (x[i]**2 - x[i+1])**2 +
                            (1 - x[i])**2
                            for i in range(n - 1) if i < n - 1)

        # 4. 约束
        penalty = 0.0
        for val in x:
            if abs(val) > 4.5:
                penalty += (abs(val) - 4.5)**2 * 100

        # 加权组合
        return 0.3 * global_term + 0.3 * local_term + 0.3 * nonconvex_term + penalty


# 便捷函数
def create_problem(problem_type: str, **kwargs) -> ExpensiveOptimizationProblem:
    """
    创建昂贵优化问题

    Args:
        problem_type: 问题类型
        **kwargs: 问题参数

    Returns:
        问题实例
    """
    problem_map = {
        'finite_element': FiniteElementOptimization,
        'cec2017': CEC2017Expensive,
        'cfd': ComputationalFluidDynamics,
        'circuit': CircuitDesignOptimization,
        'mixed': MixedExpensiveBenchmark
    }

    if problem_type not in problem_map:
        raise ValueError(f"Unknown problem type: {problem_type}")

    return problem_map[problem_type](**kwargs)


if __name__ == "__main__":
    # 测试各个问题
    print("=" * 60)
    print("昂贵优化问题测试")
    print("=" * 60)

    problems = [
        ('finite_element', {}),
        ('cec2017', {'function_id': 1}),
        ('cfd', {}),
        ('circuit', {}),
        ('mixed', {})
    ]

    for problem_type, params in problems:
        print(f"\n测试: {problem_type}")
        problem = create_problem(problem_type, dimension=10, evaluation_cost=0.01, **params)

        # 测试评估
        x = np.random.randn(10)
        fitness = problem.evaluate(x)

        print(f"  维度: {problem.dimension}")
        print(f"  评估成本: {problem.evaluation_cost}s")
        print(f"  测试解适应度: {fitness:.6f}")
        print(f"  评估次数: {problem.evaluation_count}")
        print(f"  总时间: {problem.total_time:.3f}s")

    print("\n" + "=" * 60)
    print("所有问题测试完成！")
    print("=" * 60)
