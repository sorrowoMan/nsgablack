"""
测试表征系统（Representation System）

测试各种表征管线和变量类型的编码/解码功能。
"""
import pytest
import numpy as np
import sys
from pathlib import Path
from typing import List, Tuple, Any

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.representation.base import (
    RepresentationPipeline,
    ContinuousRepresentation,
    IntegerRepresentation,
    PermutationRepresentation,
    MixedRepresentation,
)


class TestContinuousRepresentation:
    """测试连续变量表征。"""

    def test_init(self):
        """测试初始化。"""
        rep = ContinuousRepresentation(
            dimension=3,
            bounds=[(-10, 10), (-5, 5), (0, 100)]
        )

        assert rep.dimension == 3
        assert len(rep.bounds) == 3

    def test_encode(self):
        """测试编码。"""
        rep = ContinuousRepresentation(
            dimension=2,
            bounds=[(0, 10), (0, 10)]
        )

        # 连续变量：编码就是恒等映射
        solution = np.array([3.5, 7.2])
        encoded = rep.encode(solution)

        assert np.allclose(encoded, solution)

    def test_decode(self):
        """测试解码。"""
        rep = ContinuousRepresentation(
            dimension=2,
            bounds=[(0, 10), (0, 10)]
        )

        # 连续变量：解码就是恒等映射
        encoded = np.array([3.5, 7.2])
        decoded = rep.decode(encoded)

        assert np.allclose(decoded, encoded)

    def test_clip_to_bounds(self):
        """测试边界裁剪。"""
        rep = ContinuousRepresentation(
            dimension=2,
            bounds=[(0, 10), (0, 10)]
        )

        # 测试超出上界的值
        x1 = rep.decode(np.array([15.0, 5.0]))
        assert x1[0] <= 10.0

        # 测试超出下界的值
        x2 = rep.decode(np.array([-5.0, 5.0]))
        assert x2[0] >= 0.0


class TestIntegerRepresentation:
    """测试整数变量表征。"""

    def test_init(self):
        """测试初始化。"""
        rep = IntegerRepresentation(
            dimension=3,
            bounds=[(0, 10), (1, 5), (10, 20)]
        )

        assert rep.dimension == 3

    def test_encode_rounds_to_int(self):
        """测试编码时舍入到整数。"""
        rep = IntegerRepresentation(
            dimension=2,
            bounds=[(0, 10), (0, 10)]
        )

        solution = np.array([3.7, 7.2])
        encoded = rep.encode(solution)

        # 应该舍入到整数
        assert np.allclose(encoded, np.array([4.0, 7.0]))

    def test_decode_returns_integers(self):
        """测试解码返回整数值。"""
        rep = IntegerRepresentation(
            dimension=2,
            bounds=[(0, 10), (0, 10)]
        )

        encoded = np.array([3.7, 7.2])
        decoded = rep.decode(encoded)

        # 解码后应该是整数
        assert np.all(np.mod(decoded, 1) == 0)


class TestPermutationRepresentation:
    """测试排列变量表征。"""

    def test_init(self):
        """测试初始化。"""
        rep = PermutationRepresentation(size=5)

        assert rep.size == 5
        assert rep.dimension == 5

    def test_encode_creates_permutation(self):
        """测试编码创建排列。"""
        rep = PermutationRepresentation(size=5)

        # 任意输入
        solution = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        encoded = rep.encode(solution)

        # 应该是0-4的排列
        assert len(encoded) == 5
        assert set(encoded) == {0, 1, 2, 3, 4}

    def test_decode_preserves_permutation(self):
        """测试解码保持排列。"""
        rep = PermutationRepresentation(size=5)

        encoded = np.array([2, 0, 4, 1, 3])
        decoded = rep.decode(encoded)

        assert len(decoded) == 5
        assert set(decoded) == {0, 1, 2, 3, 4}

    def test_random_permutation_is_valid(self):
        """测试随机排列的有效性。"""
        rep = PermutationRepresentation(size=10)

        for _ in range(5):
            random_perm = rep.generate_random()
            assert len(random_perm) == 10
            assert set(random_perm) == set(range(10))


class TestMixedRepresentation:
    """测试混合变量表征。"""

    def test_init(self):
        """测试初始化。"""
        # 创建混合表征
        representations = [
            ContinuousRepresentation(dimension=2, bounds=[(0, 10)] * 2),
            IntegerRepresentation(dimension=1, bounds=[(0, 5)]),
            PermutationRepresentation(size=3),
        ]

        mixed = MixedRepresentation(representations=representations)

        assert mixed.total_dimension == 6  # 2 + 1 + 3

    def test_encode_combines_all(self):
        """测试编码组合所有表征。"""
        representations = [
            ContinuousRepresentation(dimension=2, bounds=[(0, 10)] * 2),
            IntegerRepresentation(dimension=1, bounds=[(0, 5)]),
        ]

        mixed = MixedRepresentation(representations=representations)

        # 输入应该是字典或列表
        solution = {
            'continuous': np.array([3.5, 7.2]),
            'integer': np.array([4.0])
        }

        encoded = mixed.encode(solution)

        assert len(encoded) == 3

    def test_decode_separates_all(self):
        """测试解码分离所有表征。"""
        representations = [
            ContinuousRepresentation(dimension=2, bounds=[(0, 10)] * 2),
            IntegerRepresentation(dimension=1, bounds=[(0, 5)]),
        ]

        mixed = MixedRepresentation(representations=representations)

        encoded = np.array([3.5, 7.2, 4.0])
        decoded = mixed.decode(encoded)

        # 应该返回字典或列表
        assert decoded is not None
        assert 'continuous' in decoded or 'integer' in decoded


class TestRepresentationConstraints:
    """测试表征的约束处理。"""

    def test_continuous_with_constraint(self):
        """测试带约束的连续变量。"""
        from utils.representation.constraints import BoundConstraint

        rep = ContinuousRepresentation(
            dimension=2,
            bounds=[(0, 10), (0, 10)]
        )

        # 添加边界约束
        constraint = BoundConstraint(bounds=[(0, 10), (0, 10)])
        rep.add_constraint(constraint)

        # 测试约束检查
        valid_x = np.array([5.0, 5.0])
        assert rep.check_constraints(valid_x)

        invalid_x = np.array([15.0, 5.0])
        assert not rep.check_constraints(invalid_x)

    def test_repair_infeasible_solution(self):
        """测试修复不可行解。"""
        from utils.representation.constraints import BoundConstraint

        rep = ContinuousRepresentation(
            dimension=2,
            bounds=[(0, 10), (0, 10)]
        )

        constraint = BoundConstraint(bounds=[(0, 10), (0, 10)])
        rep.add_constraint(constraint)

        # 不可行解
        x_infeasible = np.array([15.0, -5.0])

        # 修复
        x_repaired = rep.repair(x_infeasible)

        # 修复后应该满足约束
        assert rep.check_constraints(x_repaired)
        assert 0 <= x_repaired[0] <= 10
        assert 0 <= x_repaired[1] <= 10


@pytest.mark.slow
class TestRepresentationPerformance:
    """测试表征性能（慢速测试）。"""

    def test_large_permutation_encoding(self):
        """测试大规模排列编码。"""
        size = 100
        rep = PermutationRepresentation(size=size)

        # 编码多次
        for _ in range(10):
            solution = np.random.rand(size)
            encoded = rep.encode(solution)

            assert len(encoded) == size
            assert set(encoded) == set(range(size))

    def test_high_dimensional_continuous(self):
        """测试高维连续变量。"""
        dimension = 100
        rep = ContinuousRepresentation(
            dimension=dimension,
            bounds=[(0, 10)] * dimension
        )

        solution = np.random.rand(dimension) * 10
        encoded = rep.encode(solution)
        decoded = rep.decode(encoded)

        assert len(encoded) == dimension
        assert len(decoded) == dimension


@pytest.mark.parametrize("dimension,bounds", [
    (2, [(0, 10), (0, 10)]),
    (3, [(-5, 5), (-5, 5), (-5, 5)]),
    (5, [(0, 1)] * 5),
])
def test_continuous_various_dimensions(dimension, bounds):
    """参数化测试：不同维度的连续变量。"""
    rep = ContinuousRepresentation(dimension=dimension, bounds=bounds)

    assert rep.dimension == dimension
    assert len(rep.bounds) == dimension

    # 测试编码/解码
    x = np.random.rand(dimension)
    encoded = rep.encode(x)
    decoded = rep.decode(encoded)

    assert len(decoded) == dimension
