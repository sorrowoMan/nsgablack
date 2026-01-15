"""
实验4：动态优化 - 完整实现

测试问题：
1. 动态函数优化
2. 动态约束优化
3. 跟踪动态最优解
"""

import numpy as np
from typing import List, Tuple, Dict, Any
from dataclasses import dataclass


@dataclass
class DynamicState:
    """动态环境状态"""
    generation: int
    phase: int
    objective_type: str
    severity: float
    changed: bool


class DynamicOptimizationProblem:
    """动态优化问题基类"""

    def __init__(self, name: str, dimension: int, change_frequency: int = 50):
        self.name = name
        self.dimension = dimension
        self.change_frequency = change_frequency  # 环境变化频率
        self.generation = 0

    def evaluate(self, x: np.ndarray, generation: int = None) -> float:
        """
        评估解（考虑环境动态）

        Args:
            x: 解向量
            generation: 当前代数
        """
        if generation is not None:
            self.generation = generation

        # 更新环境状态
        state = self._get_dynamic_state()

        # 根据状态评估
        fitness = self._evaluate_dynamic(x, state)

        return fitness

    def _get_dynamic_state(self) -> DynamicState:
        """获取当前动态状态"""
        phase = self.generation // self.change_frequency
        changed = (self.generation % self.change_frequency == 0) and (self.generation > 0)

        return DynamicState(
            generation=self.generation,
            phase=phase,
            objective_type=self._get_objective_type(phase),
            severity=self._get_severity(phase),
            changed=changed
        )

    def _get_objective_type(self, phase: int) -> str:
        """获取当前目标函数类型"""
        raise NotImplementedError

    def _get_severity(self, phase: int) -> float:
        """获取变化严重程度"""
        return 1.0

    def _evaluate_dynamic(self, x: np.ndarray, state: DynamicState) -> float:
        """动态评估"""
        raise NotImplementedError


class RotatingOptimization(DynamicOptimizationProblem):
    """
    旋转优化问题

    目标函数在多个基准函数之间切换
    """

    def __init__(self, dimension=30, change_frequency=50):
        super().__init__("Rotating_Functions", dimension, change_frequency)

    def _get_objective_type(self, phase: int) -> str:
        types = ['sphere', 'rastrigin', 'rosenbrock', 'ackley']
        return types[phase % len(types)]

    def _get_severity(self, phase: int) -> float:
        # 变化程度逐渐增加
        return 1.0 + phase * 0.1

    def _evaluate_dynamic(self, x: np.ndarray, state: DynamicState) -> float:
        """根据当前阶段评估"""

        if state.objective_type == 'sphere':
            return np.sum(x**2)

        elif state.objective_type == 'rastrigin':
            n = len(x)
            return 10 * n + np.sum(x**2 - 10 * np.cos(2 * np.pi * x))

        elif state.objective_type == 'rosenbrock':
            return sum(100 * (x[i]**2 - x[i+1])**2 + (1 - x[i])**2
                      for i in range(len(x) - 1))

        elif state.objective_type == 'ackley':
            n = len(x)
            sum_sq = np.sum(x**2)
            sum_cos = np.sum(np.cos(2 * np.pi * x))
            return -20 * np.exp(-0.2 * np.sqrt(sum_sq / n)) - \
                   np.exp(sum_cos / n) + 20 + np.exp(1)

        return np.sum(x**2)


class MovingOptima(DynamicOptimizationProblem):
    """
    移动峰问题

    最优解位置随时间移动
    """

    def __init__(self, dimension=30, change_frequency=30):
        super().__init__("Moving_Optima", dimension, change_frequency)
        self.optimum_history = []

    def _get_objective_type(self, phase: int) -> str:
        return 'moving_peaks'

    def _get_severity(self, phase: int) -> float:
        return 1.0

    def _get_current_optimum(self) -> np.ndarray:
        """获取当前最优解位置"""
        phase = self.generation // self.change_frequency

        # 最优解按螺旋移动
        t = phase * 0.5
        center = np.zeros(self.dimension)

        for i in range(self.dimension):
            if i % 2 == 0:
                center[i] = 3 * np.cos(t + i * 0.5)
            else:
                center[i] = 3 * np.sin(t + i * 0.5)

        return center

    def _evaluate_dynamic(self, x: np.ndarray, state: DynamicState) -> float:
        """评估到移动峰的距离"""
        current_optimum = self._get_current_optimum()

        # 记录历史
        if state.changed or len(self.optimum_history) == 0:
            self.optimum_history.append(current_optimum.copy())

        # 距离当前峰的距离
        distance = np.linalg.norm(x - current_optimum)

        # 多峰结构
        landscape = np.sum(x**2) * 0.1  # 背景

        # 主峰（移动的）
        main_peak = distance ** 2

        # 次峰（静态的，干扰项）
        secondary_peaks = 0.0
        for i in range(0, len(x), 5):
            secondary_peak = np.linalg.norm(x - np.roll(current_optimum, i))
            secondary_peaks += 50 * np.exp(-secondary_peak**2 / 10)

        return landscape + main_peak - secondary_peaks


class DynamicConstraints(DynamicOptimizationProblem):
    """
    动态约束优化

    约束条件随时间变化
    """

    def __init__(self, dimension=20, change_frequency=40):
        super().__init__("Dynamic_Constraints", dimension, change_frequency)

    def _get_objective_type(self, phase: int) -> str:
        return 'dynamic_constraints'

    def _get_severity(self, phase: int) -> float:
        return 1.0 + phase * 0.05

    def _evaluate_dynamic(self, x: np.ndarray, state: DynamicState) -> float:
        """动态约束优化"""
        # 目标函数（固定）
        objective = np.sum(x**2)

        # 动态约束
        constraints = []

        # 约束1：可行域随时间旋转
        angle = state.phase * np.pi / 4
        x_rotated = np.zeros_like(x)

        # 只旋转前两维
        if len(x) >= 2:
            x_rotated[0] = x[0] * np.cos(angle) - x[1] * np.sin(angle)
            x_rotated[1] = x[0] * np.sin(angle) + x[1] * np.cos(angle)

        for i in range(len(x)):
            if i == 0 or i == 1:
                val = x_rotated[i]
            else:
                val = x[i]

            # 约束：球约束，半径随时间变化
            radius = 4.0 - state.phase * 0.2
            c = val**2 - radius**2
            constraints.append(max(0, c))

        # 约束2：线性约束，斜率变化
        sum_constraint = np.sum(x[:5]) - (5.0 + state.phase * 0.3)
        constraints.append(max(0, sum_constraint))

        # 惩罚
        penalty = sum(c**2 * 100 for c in constraints)

        return objective + penalty


class AdaptiveBias:
    """
    自适应偏置

    根据环境变化动态调整策略
    """

    def __init__(self):
        self.performance_history = []
        self.phase_history = []
        self.current_strategy = 'exploration'

    def update_strategy(self, state: DynamicState, recent_improvement: float):
        """根据环境状态更新策略"""
        self.phase_history.append(state.phase)

        # 检测环境变化
        if state.changed:
            # 环境变化，重置策略
            self._detect_and_adapt()

        # 根据性能调整
        self.performance_history.append(recent_improvement)
        if len(self.performance_history) > 10:
            self.performance_history.pop(0)

    def _detect_and_adapt(self):
        """检测变化并适应"""
        if len(self.phase_history) < 2:
            return

        # 检测性能突变
        if len(self.performance_history) >= 5:
            recent_avg = np.mean(self.performance_history[-3:])
            older_avg = np.mean(self.performance_history[-6:-3])

            # 性能下降 → 环境变了，增加探索
            if recent_avg < older_avg * 0.8:
                self.current_strategy = 'exploration'
            # 性能稳定 → 增加开发
            elif recent_avg > older_avg * 1.1:
                self.current_strategy = 'exploitation'

    def compute_bias(self, x: np.ndarray, state: DynamicState) -> float:
        """计算自适应偏置"""
        if self.current_strategy == 'exploration':
            # 探索：鼓励多样性
            diversity_bonus = np.sum(np.abs(x)) * 0.01
            return -diversity_bonus
        else:
            # 开发：鼓励向中心收敛
            convergence_bonus = -np.sum(x**2) * 0.1
            return convergence_bias

    def get_strategy(self) -> str:
        """获取当前策略"""
        return self.current_strategy


class DynamicOptimizationTracker:
    """
    动态优化跟踪器

    记录算法对动态环境的适应能力
    """

    def __init__(self):
        self.best_fitness_history = []
        self.phase_changes = []
        self.recovery_times = []
        self.current_phase_start = 0

    def update(self, generation: int, best_fitness: float, phase: int):
        """更新跟踪信息"""
        self.best_fitness_history.append({
            'generation': generation,
            'fitness': best_fitness,
            'phase': phase
        })

        # 检测相位变化
        if len(self.best_fitness_history) > 1:
            last_phase = self.best_fitness_history[-2]['phase']
            if phase != last_phase:
                # 记录相位变化
                self.phase_changes.append(generation)

                # 记录恢复时间（从前一变化到找到更好解）
                if len(self.phase_changes) > 1:
                    recovery_time = generation - self.phase_changes[-2]
                    self.recovery_times.append(recovery_time)

    def compute_metrics(self) -> Dict[str, Any]:
        """计算性能指标"""
        if len(self.best_fitness_history) < 2:
            return {}

        fitnesses = [h['fitness'] for h in self.best_fitness_history]

        return {
            'best_fitness': min(fitnesses),
            'avg_fitness': np.mean(fitnesses),
            'worst_fitness': max(fitnesses),
            'n_phase_changes': len(self.phase_changes),
            'avg_recovery_time': np.mean(self.recovery_times) if self.recovery_times else 0,
            'tracking_accuracy': self._compute_tracking_accuracy()
        }

    def _compute_tracking_accuracy(self) -> float:
        """计算追踪准确度（在变化后多快找到新最优）"""
        if len(self.recovery_times) == 0:
            return 0.0

        # 恢复时间越短，准确度越高
        max_acceptable = 50  # 最多50代
        accuracies = [1.0 - min(rt / max_acceptable, 1.0)
                     for rt in self.recovery_times]

        return np.mean(accuracies)


# 实验运行器
class DynamicOptimizationExperiment:
    """动态优化实验"""

    def __init__(self):
        self.problems = [
            RotatingOptimization(dimension=20, change_frequency=30),
            MovingOptima(dimension=20, change_frequency=30),
            DynamicConstraints(dimension=15, change_frequency=30)
        ]

    def run_quick_test(self):
        """快速测试"""
        print("=" * 70)
        print("实验4：动态优化 - 快速测试")
        print("=" * 70)

        for problem in self.problems:
            print(f"\n问题: {problem.name}")
            print(f"  维度: {problem.dimension}")
            print(f"  变化频率: 每{problem.change_frequency}代")

            # 测试多个时间步
            tracker = DynamicOptimizationTracker()

            print(f"\n  模拟动态环境:")

            for gen in [0, 30, 60, 90]:
                state = problem._get_dynamic_state()
                if gen > 0:
                    problem.generation = gen

                # 生成测试解
                x = np.random.randn(problem.dimension) * 2

                # 评估
                fitness = problem.evaluate(x, generation=gen)

                print(f"    Gen {gen}: Phase={state.phase}, "
                      f"Type={state.objective_type}, "
                      f"Fitness={fitness:.6f}, "
                      f"Changed={state.changed}")

                tracker.update(gen, fitness, state.phase)

            # 计算指标
            metrics = tracker.compute_metrics()
            if metrics:
                print(f"\n  跟踪指标:")
                print(f"    相位变化次数: {metrics['n_phase_changes']}")
                print(f"    平均恢复时间: {metrics['avg_recovery_time']:.1f}代")

        print("\n" + "=" * 70)
        print("测试完成！")
        print("=" * 70)


if __name__ == "__main__":
    experiment = DynamicOptimizationExperiment()
    experiment.run_quick_test()
