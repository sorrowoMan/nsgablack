"""
测试偏置系统（Bias System）

测试BiasModule的核心功能，包括罚函数、奖函数和偏置计算。
"""
import pytest
import numpy as np
from typing import Dict, Any, List
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from bias.bias import BiasModule, proximity_reward, improvement_reward


class TestBiasModule:
    """测试BiasModule类。"""

    def test_init(self):
        """测试BiasModule初始化。"""
        bias = BiasModule()
        assert len(bias.penalties) == 0
        assert len(bias.rewards) == 0
        assert bias.history_best_x is None
        assert bias.history_best_f == float('inf')

    def test_add_penalty(self):
        """测试添加罚函数。"""
        bias = BiasModule()

        def simple_penalty(x):
            return np.sum(np.maximum(x, 0))

        bias.add_penalty(simple_penalty, weight=2.0, name="test_penalty")

        assert len(bias.penalties) == 1
        assert bias.penalties[0]['weight'] == 2.0
        assert bias.penalties[0]['name'] == "test_penalty"

    def test_add_reward(self):
        """测试添加奖函数。"""
        bias = BiasModule()

        def simple_reward(x):
            return -np.sum(x**2)

        bias.add_reward(simple_reward, weight=0.1, name="test_reward")

        assert len(bias.rewards) == 1
        assert bias.rewards[0]['weight'] == 0.1
        assert bias.rewards[0]['name'] == "test_reward"

    def test_compute_bias_with_penalty(self):
        """测试带罚函数的偏置计算。"""
        bias = BiasModule()

        # 添加边界罚函数
        def bounds_penalty(x, constraints, context):
            violation = np.sum(np.maximum(np.abs(x) - 5, 0))
            return {"penalty": violation}

        bias.add_penalty(bounds_penalty, weight=10.0)

        # 测试可行解
        x_feasible = np.array([1.0, 2.0])
        f_original = 5.0
        f_biased = bias.compute_bias(x_feasible, f_original)
        assert f_biased == f_original  # 无惩罚

        # 测试不可行解
        x_infeasible = np.array([10.0, 0.0])
        f_biased = bias.compute_bias(x_infeasible, f_original)
        # 违反度: (10-5) + 0 = 5, 惩罚: 5*10 = 50
        assert f_biased > f_original

    def test_compute_bias_with_reward(self):
        """测试带奖函数的偏置计算。"""
        bias = BiasModule()

        # 添加接近原点的奖励
        def origin_reward(x, constraints, context):
            distance = np.linalg.norm(x)
            return {"reward": max(0, 10 - distance)}

        bias.add_reward(origin_reward, weight=0.5)

        # 测试接近原点
        x_near = np.array([1.0, 1.0])
        f_original = 10.0
        f_biased = bias.compute_bias(x_near, f_original)
        # 距离≈1.41, 奖励≈8.59, 偏置减少≈4.3
        assert f_biased < f_original

    def test_compute_bias_combined(self):
        """测试罚函数和奖函数的组合。"""
        bias = BiasModule()

        def penalty_func(x, constraints, context):
            return 1.0 if np.sum(x**2) > 10 else 0.0

        def reward_func(x, constraints, context):
            return 2.0 if np.sum(x**2) < 5 else 0.0

        bias.add_penalty(penalty_func, weight=5.0)
        bias.add_reward(reward_func, weight=0.1)

        # 情况1: 无惩罚无奖励
        x1 = np.array([2.0, 2.0])  # f=8
        f1 = bias.compute_bias(x1, 8.0)
        assert f1 == 8.0

        # 情况2: 有惩罚
        x2 = np.array([4.0, 4.0])  # f=32
        f2 = bias.compute_bias(x2, 32.0)
        assert f2 > 32.0

        # 情况3: 有奖励
        x3 = np.array([1.0, 1.0])  # f=2
        f3 = bias.compute_bias(x3, 2.0)
        assert f3 < 2.0

    def test_history_tracking(self):
        """测试历史最优跟踪。"""
        bias = BiasModule()

        solutions = [
            (np.array([5.0, 5.0]), 50.0),
            (np.array([3.0, 3.0]), 18.0),
            (np.array([1.0, 1.0]), 2.0),
            (np.array([2.0, 2.0]), 8.0),
        ]

        for x, f in solutions:
            bias.compute_bias(x, f)

        assert bias.history_best_f == 2.0
        assert np.allclose(bias.history_best_x, np.array([1.0, 1.0]))

    def test_clear(self):
        """测试清空偏置。"""
        bias = BiasModule()

        bias.add_penalty(lambda x: 1.0)
        bias.add_reward(lambda x: 1.0)

        assert len(bias.penalties) == 1
        assert len(bias.rewards) == 1

        bias.clear()

        assert len(bias.penalties) == 0
        assert len(bias.rewards) == 0


class TestRewardFunctions:
    """测试内置奖函数。"""

    def test_proximity_reward(self):
        """测试接近奖励函数。"""
        best_x = np.array([0.0, 0.0, 0.0])

        # 接近最优
        x_near = np.array([0.1, 0.1, 0.1])
        reward = proximity_reward(x_near, best_x)
        assert reward > 0

        # 远离最优
        x_far = np.array([10.0, 10.0, 10.0])
        reward = proximity_reward(x_far, best_x)
        # 应该有很小的奖励（因为距离远）
        assert 0 <= reward < 1

    def test_improvement_reward(self):
        """测试改进奖励函数。"""
        previous_f = 100.0
        current_f = 50.0

        reward = improvement_reward(current_f, previous_f)
        assert reward > 0  # 有改进

        # 无改进
        reward = improvement_reward(100.0, 100.0)
        assert reward == 0

        # 变差
        reward = improvement_reward(150.0, 100.0)
        assert reward == 0


class TestBiasIntegration:
    """测试偏置系统的集成场景。"""

    def test_constraint_bias(self):
        """测试约束偏置场景。"""
        bias = BiasModule()

        # 定义约束偏置
        def constraint_penalty(x, constraints, context):
            """简单的边界约束。"""
            lower = -5
            upper = 5
            violations = []

            for i, val in enumerate(x):
                if val < lower:
                    violations.append(lower - val)
                elif val > upper:
                    violations.append(val - upper)

            total_violation = sum(violations) if violations else 0
            context["constraints"].append({"type": "bounds", "violation": total_violation})
            return {"penalty": total_violation}

        bias.add_penalty(constraint_penalty, weight=10.0, name="bounds")

        # 可行解
        x1 = np.array([0.0, 0.0])
        f1 = bias.compute_bias(x1, 10.0, context={"constraints": []})
        assert f1 == 10.0
        assert len(bias.history_best_x) == 2

        # 不可行解
        x2 = np.array([10.0, -10.0])
        f2 = bias.compute_bias(x2, 10.0, context={"constraints": []})
        # 违反: (10-5) + (-5+5) = 5, 惩罚: 5*10 = 50
        assert f2 > 50.0

    @pytest.mark.slow
    def test_complex_bias_scenario(self, sample_bias):
        """测试复杂偏置场景。"""
        bias = sample_bias

        # 生成一些测试解
        test_cases = [
            (np.array([0.0, 0.0]), 0.0),      # 最优
            (np.array([3.0, 3.0]), 18.0),     # 可行
            (np.array([7.0, 0.0]), 49.0),     # 不可行
            (np.array([0.0, 10.0]), 100.0),   # 不可行
        ]

        for x, f in test_cases:
            f_biased = bias.compute_bias(x, f, context={"constraints": []})
            # 偏置后的值应该保留相对顺序
            assert f_biased >= 0


@pytest.mark.parametrize("x,expected", [
    (np.array([0.0, 0.0]), 0.0),  # 原点
    (np.array([1.0, 0.0]), 1.0),  # x轴
    (np.array([0.0, 1.0]), 1.0),  # y轴
    (np.array([3.0, 4.0]), 25.0),  # 3-4-5三角形
])
def test_sphere_objective(x, expected):
    """参数化测试：Sphere目标函数。"""
    result = np.sum(x**2)
    assert np.isclose(result, expected)
