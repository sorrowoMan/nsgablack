"""
实验3：复杂约束优化 - 完整实现

测试问题：
1. 压力容器设计
2. 焊接梁设计
3. 多约束工程设计
"""

import numpy as np
from typing import List, Tuple
from dataclasses import dataclass


@dataclass
class ConstraintInfo:
    """约束信息"""
    name: str
    value: float
    violation: float
    is_satisfied: bool


class ConstrainedProblem:
    """约束优化问题基类"""

    def __init__(self, name: str, dimension: int):
        self.name = name
        self.dimension = dimension
        self.n_constraints = 0
        self.bounds = self._get_bounds()

    def _get_bounds(self) -> List[Tuple[float, float]]:
        """获取变量边界"""
        return [(0.0, 10.0) for _ in range(self.dimension)]

    def evaluate(self, x: np.ndarray) -> float:
        """评估解（目标+惩罚）"""
        objective = self._evaluate_objective(x)
        constraints = self._evaluate_constraints(x)
        penalty = self._compute_penalty(constraints)
        return objective + penalty

    def _evaluate_objective(self, x: np.ndarray) -> float:
        """目标函数"""
        raise NotImplementedError

    def _evaluate_constraints(self, x: np.ndarray) -> List[float]:
        """约束函数（返回约束值，<=0表示满足）"""
        raise NotImplementedError

    def _compute_penalty(self, constraints: List[float]) -> float:
        """计算惩罚"""
        penalty = 0.0
        for c in constraints:
            if c > 0:  # 约束违反
                penalty += c ** 2 * 1000
        return penalty

    def get_constraint_info(self, x: np.ndarray) -> List[ConstraintInfo]:
        """获取详细约束信息"""
        constraints = self._evaluate_constraints(x)
        info = []

        for i, c in enumerate(constraints):
            info.append(ConstraintInfo(
                name=f"Constraint_{i+1}",
                value=c,
                violation=max(0, c),
                is_satisfied=(c <= 0)
            ))

        return info


class PressureVesselDesign(ConstrainedProblem):
    """
    压力容器设计问题（经典约束优化）

    变量（4个）：
    x1: Ts - 壳体厚度
    x2: Th - 封头厚度
    x3: R - 内径
    x4: L - 长度

    约束（7个）：
    g1: 应力约束
    g2: 应力约束
    g3: 体积约束
    g4: 几何约束
    g5: 几何约束
    g6: 尺寸约束
    g7: 尺寸约束
    """

    def __init__(self):
        super().__init__("Pressure_Vessel", dimension=4)
        self.n_constraints = 7

        # 设计参数
        self.P = 3000  # 内压 (psi)
        self.S = 15000  # 允许应力 (psi)
        self.min_volume = 7500  # 最小体积 (in³)

    def _get_bounds(self) -> List[Tuple[float, float]]:
        return [
            (1.0, 10.0),   # Ts
            (1.0, 10.0),   # Th
            (10.0, 200.0), # R
            (10.0, 200.0)  # L
        ]

    def _evaluate_objective(self, x: np.ndarray) -> float:
        """目标函数：总成本"""
        Ts, Th, R, L = x

        # 材料成本
        cost_shell = 0.6224 * Ts * R * L
        cost_head = 3.1661 * Th * R**2
        cost_weld = 19.84 * Ts**2 * L + 12.84 * Th * R

        return cost_shell + cost_head + cost_weld

    def _evaluate_constraints(self, x: np.ndarray) -> List[float]:
        """约束函数"""
        Ts, Th, R, L = x

        constraints = []

        # g1: 壳体应力约束
        g1 = (self.P * R) / (2 * Ts) - self.S
        constraints.append(g1)

        # g2: 封头应力约束
        g2 = (self.P * R) / (2 * Th) - self.S
        constraints.append(g2)

        # g3: 体积约束（最小）
        volume = np.pi * R**2 * L
        g3 = self.min_volume - volume
        constraints.append(g3)

        # g4: 几何约束（R < L）
        g4 = -R + L
        constraints.append(g4)

        # g5: 几何约束（Th < Ts）
        g5 = Th - Ts
        constraints.append(g5)

        # g6: 尺寸约束（Ts >= 1.125）
        g6 = 1.125 - Ts
        constraints.append(g6)

        # g7: 尺寸约束（Th >= 0.625）
        g7 = 0.625 - Th
        constraints.append(g7)

        return constraints


class WeldedBeamDesign(ConstrainedProblem):
    """
    焊接梁设计问题

    变量（4个）：
    h: 焊缝高度
    l: 焊缝长度
    t: 梁高度
    b: 梁宽度

    约束：
    - 剪切应力
    - 弯曲应力
    - 端部挠度
    - 几何约束
    """

    def __init__(self):
        super().__init__("Welded_Beam", dimension=4)
        self.n_constraints = 4

        # 常数
        self.P = 6000  # 载荷 (lb)
        self.L = 14  # 长度 (in)
        self.E = 30e6  # 弹性模量 (psi)
        self.G = 12e6  # 剪切模量 (psi)
        self.tau_max = 13600  # 最大剪切应力
        self.sigma_max = 30000  # 最大弯曲应力

    def _get_bounds(self) -> List[Tuple[float, float]]:
        return [
            (0.125, 5.0),   # h
            (0.1, 10.0),    # l
            (0.1, 10.0),    # t
            (0.125, 5.0)    # b
        ]

    def _evaluate_objective(self, x: np.ndarray) -> float:
        """目标函数：成本"""
        h, l, t, b = x
        return 1.10471 * h**2 * l + 0.04811 * t * b * (14.0 + l)

    def _evaluate_constraints(self, x: np.ndarray) -> List[float]:
        """约束函数"""
        h, l, t, b = x

        constraints = []

        # 中间计算
        A = b * t
        delta = np.sqrt(l**2 / 4 + ((h + t) / 2)**2)
        J = 2 * (0.707 * h * l * (l**2 / 12 + ((h + t) / 2)**2))
        P = self.P
        L = self.L
        E = self.E
        G = self.G

        # g1: 剪切应力约束
        tau_prime = P / (np.sqrt(2) * h * l)
        tau_double_prime = P * L * delta / J
        tau = np.sqrt(tau_prime**2 + 2 * tau_prime * tau_double_prime * l / (2 * delta) +
                      tau_double_prime**2)
        g1 = tau - self.tau_max
        constraints.append(g1)

        # g2: 弯曲应力约束
        sigma = 6 * P * L / (b * t**2)
        g2 = sigma - self.sigma_max
        constraints.append(g2)

        # g3: 端部挠度约束
        delta_deflection = 4 * P * L**3 / (E * b * t**3)
        g3 = delta_deflection - 0.25
        constraints.append(g3)

        # g4: 几何约束（h <= b）
        g4 = h - b
        constraints.append(g4)

        return constraints


class MultiConstraintDesign(ConstrainedProblem):
    """
    多约束工程设计问题

    综合测试约束处理能力
    """

    def __init__(self, dimension=10):
        super().__init__("Multi_Constraint", dimension)
        self.n_constraints = dimension + 3

    def _get_bounds(self) -> List[Tuple[float, float]]:
        return [(-5.0, 5.0) for _ in range(self.dimension)]

    def _evaluate_objective(self, x: np.ndarray) -> float:
        """目标函数：非线性函数"""
        n = len(x)
        return np.sum(x[:n//2]**2) + np.sum(np.sin(x[n//2:]))

    def _evaluate_constraints(self, x: np.ndarray) -> List[float]:
        """多约束"""
        constraints = []

        n = len(x)

        # 1. 不等式约束（n个）
        for i in range(n):
            # 不同类型的约束
            if i % 3 == 0:
                # 球约束
                c = np.sum(x**2) - 25.0
            elif i % 3 == 1:
                # 线性约束
                c = np.sum(x) - 5.0
            else:
                # 非线性约束
                c = x[i]**2 + x[(i+1) % n]**2 - 4.0

            constraints.append(c)

        # 2. 等式约束（2个，转换为不等式）
        # 等式约束1: sum(x) = 2.0
        c_eq1 = abs(np.sum(x) - 2.0) - 0.01
        constraints.append(c_eq1)

        # 等式约束2: prod(1+x) = 1.5
        c_eq2 = abs(np.prod(1 + x * 0.1) - 1.5) - 0.01
        constraints.append(c_eq2)

        return constraints


class DomainBiasExample:
    """
    领域偏置示例：将工程约束转换为偏置
    """

    @staticmethod
    def stress_constraint_bias(x: np.ndarray, problem: ConstrainedProblem) -> float:
        """
        应力约束偏置

        将应力约束转换为软偏置
        """
        if isinstance(problem, PressureVesselDesign):
            Ts, Th, R, L = x
            P, S = problem.P, problem.S

            # 计算应力
            stress_shell = (P * R) / (2 * Ts)
            stress_head = (P * R) / (2 * Th)

            # 偏置值（约束违反为正，满足为负）
            max_stress = max(stress_shell, stress_head)

            if max_stress > S:
                # 违反约束：大惩罚
                violation = max_stress - S
                return violation ** 2 * 1000
            else:
                # 满足约束：小奖励（接近极限时奖励更大）
                margin = S - max_stress
                return -margin * 10

        return 0.0

    @staticmethod
    def volume_constraint_bias(x: np.ndarray, problem: ConstrainedProblem) -> float:
        """体积约束偏置"""
        if isinstance(problem, PressureVesselDesign):
            _, _, R, L = x
            volume = np.pi * R**2 * L
            min_volume = problem.min_volume

            if volume < min_volume:
                violation = min_volume - volume
                return violation ** 2 * 100
            else:
                # 体积稍大于最小值时奖励
                margin = volume - min_volume
                if margin < 1000:
                    return -margin * 0.1

        return 0.0


# 实验运行器
class ComplexConstraintExperiment:
    """复杂约束优化实验"""

    def __init__(self):
        self.problems = [
            PressureVesselDesign(),
            WeldedBeamDesign(),
            MultiConstraintDesign(dimension=10)
        ]

    def run_quick_test(self):
        """快速测试"""
        print("=" * 70)
        print("实验3：复杂约束优化 - 快速测试")
        print("=" * 70)

        for problem in self.problems:
            print(f"\n问题: {problem.name}")
            print(f"  维度: {problem.dimension}")
            print(f"  约束数: {problem.n_constraints}")

            # 测试随机解
            x = np.array([np.random.uniform(low, high)
                         for low, high in problem.bounds])

            # 评估
            fitness = problem.evaluate(x)
            constraints_info = problem.get_constraint_info(x)

            print(f"  目标值: {problem._evaluate_objective(x):.6f}")
            print(f"  总适应度: {fitness:.6f}")
            print(f"  约束满足:")
            for info in constraints_info[:5]:  # 只显示前5个
                status = "[OK]" if info.is_satisfied else "[X]"
                print(f"    {status} {info.name}: {info.value:+.4f} "
                      f"(violation: {info.violation:.4f})")

            # 测试领域偏置
            if isinstance(problem, PressureVesselDesign):
                print(f"\n  领域偏置测试:")
                bias1 = DomainBiasExample.stress_constraint_bias(x, problem)
                bias2 = DomainBiasExample.volume_constraint_bias(x, problem)
                print(f"    应力约束偏置: {bias1:+.6f}")
                print(f"    体积约束偏置: {bias2:+.6f}")

        print("\n" + "=" * 70)
        print("测试完成！")
        print("=" * 70)


if __name__ == "__main__":
    experiment = ComplexConstraintExperiment()
    experiment.run_quick_test()
