"""
测试新增的算法偏置：MOEAD、NSGA3、SPEA2

测试内容包括：
1. 导入测试
2. 基本功能测试
3. 与求解器集成测试
4. 边界条件测试
5. 自适应特性测试
"""

import pytest
import numpy as np
import sys
from pathlib import Path

# 添加项目根目录到路径

from nsgablack.bias.algorithmic import (
    MOEADDecompositionBias,
    AdaptiveMOEADBias,
    NSGA3ReferencePointBias,
    AdaptiveNSGA3Bias,
    SPEA2StrengthBias,
    AdaptiveSPEA2Bias,
    HybridSPEA2NSGA2Bias
)
from nsgablack.bias.core.base import OptimizationContext


class TestMOEADBias:
    """测试MOEAD分解偏置"""

    def test_import(self):
        """测试MOEAD偏置能否正确导入"""
        assert MOEADDecompositionBias is not None
        assert AdaptiveMOEADBias is not None

    def test_initialization(self):
        """测试MOEAD偏置初始化"""
        # 标准初始化
        bias = MOEADDecompositionBias(
            weight_vector=np.array([0.5, 0.5]),
            method='tchebycheff'
        )
        assert bias.name == "moead_decomposition"
        assert bias.method == 'tchebycheff'
        assert np.allclose(bias.weight_vector, [0.5, 0.5])

    def test_weight_vector_normalization(self):
        """测试权重向量自动归一化"""
        bias = MOEADDecompositionBias(
            weight_vector=np.array([2.0, 2.0]),  # 未归一化
            method='tchebycheff'
        )
        # 应该自动归一化为[0.5, 0.5]
        assert np.allclose(bias.weight_vector, [0.5, 0.5])

    def test_tchebycheff_aggregation(self):
        """测试Tchebycheff聚合函数"""
        bias = MOEADDecompositionBias(
            weight_vector=np.array([0.5, 0.5]),
            method='tchebycheff'
        )

        # 设置理想点
        bias.ideal_point = np.array([0.0, 0.0])

        # 计算聚合值
        objectives = np.array([2.0, 4.0])
        aggregation = bias._tchebycheff_aggregation(objectives)

        # max(0.5*|2-0|, 0.5*|4-0|) = max(1.0, 2.0) = 2.0
        assert aggregation == 2.0

    def test_weighted_sum_aggregation(self):
        """测试加权和聚合函数"""
        bias = MOEADDecompositionBias(
            weight_vector=np.array([0.3, 0.7]),
            method='weighted_sum'
        )

        objectives = np.array([2.0, 4.0])
        aggregation = bias._weighted_sum_aggregation(objectives)

        # 0.3*2 + 0.7*4 = 0.6 + 2.8 = 3.4
        assert np.isclose(aggregation, 3.4)

    def test_compute_bias(self):
        """测试偏置计算"""
        bias = MOEADDecompositionBias(
            weight_vector=np.array([0.5, 0.5]),
            initial_weight=0.5,
            method='tchebycheff'
        )

        # 创建上下文
        objectives = np.array([2.0, 4.0])
        context = OptimizationContext(
            generation=0,
            individual=np.array([1.0, 2.0]),
            metrics={'objectives': objectives}
        )

        # 计算偏置
        bias_value = bias.compute(np.array([1.0, 2.0]), context)

        # 应该返回一个数值
        assert isinstance(bias_value, (int, float))
        # 偏置值应该是聚合值 * 权重
        assert bias_value >= 0  # Tchebycheff总是非负

    def test_ideal_point_update(self):
        """测试理想点自动更新"""
        bias = MOEADDecompositionBias(
            weight_vector=np.array([0.5, 0.5]),
            method='tchebycheff'
        )

        # 第一个解
        context1 = OptimizationContext(
            generation=0,
            individual=np.array([1.0, 1.0]),
            metrics={'objectives': np.array([5.0, 5.0])}
        )
        bias.compute(np.array([1.0, 1.0]), context1)
        assert np.allclose(bias.ideal_point, [5.0, 5.0])

        # 更好的解（更新理想点）
        context2 = OptimizationContext(
            generation=1,
            individual=np.array([0.5, 0.5]),
            metrics={'objectives': np.array([2.0, 3.0])}
        )
        bias.compute(np.array([0.5, 0.5]), context2)
        assert np.allclose(bias.ideal_point, [2.0, 3.0])

    def test_adaptive_moad_bias(self):
        """测试自适应MOEAD偏置"""
        bias = AdaptiveMOEADBias(
            weight_vector=np.array([0.5, 0.5]),
            adaptation_window=10,
            weight_adjustment_rate=0.1
        )

        assert bias.adaptive is True
        assert bias.adaptation_window == 10

    def test_statistics(self):
        """测试统计信息获取"""
        bias = MOEADDecompositionBias(
            weight_vector=np.array([0.5, 0.5]),
            method='tchebycheff'
        )

        # 计算一次偏置以生成历史记录
        context = OptimizationContext(
            generation=0,
            individual=np.array([1.0, 1.0]),
            metrics={'objectives': np.array([2.0, 4.0])}
        )
        bias.compute(np.array([1.0, 1.0]), context)

        # 获取统计信息
        stats = bias.get_statistics()

        assert 'method' in stats
        assert 'weight_vector' in stats
        assert 'ideal_point' in stats
        assert stats['method'] == 'tchebycheff'


class TestNSGA3Bias:
    """测试NSGA3参考点偏置"""

    def test_import(self):
        """测试NSGA3偏置能否正确导入"""
        assert NSGA3ReferencePointBias is not None
        assert AdaptiveNSGA3Bias is not None

    def test_initialization(self):
        """测试NSGA3偏置初始化"""
        bias = NSGA3ReferencePointBias(
            num_objectives=2,
            divisions=12
        )

        assert bias.name == "nsga3_reference"
        assert bias.num_objectives == 2
        assert bias.divisions == 12
        assert len(bias.reference_points) > 0

    def test_das_dennis_generation(self):
        """测试Das-Dennis参考点生成"""
        # 2目标，12分割
        bias = NSGA3ReferencePointBias(
            num_objectives=2,
            divisions=12,
            generation_method='das_dennis'
        )

        # 2目标h分割应该生成 C(h+2-1, 2-1) = C(13, 1) = 13 个参考点
        expected_points = 13
        assert len(bias.reference_points) == expected_points

    def test_reference_points_normalization(self):
        """测试参考点归一化"""
        bias = NSGA3ReferencePointBias(
            num_objectives=2,
            divisions=4
        )

        # 所有参考点应该在[0, 1]区间且和为1
        for point in bias.reference_points:
            assert np.all(point >= 0)
            assert np.all(point <= 1)
            assert np.isclose(np.sum(point), 1.0)

    def test_custom_reference_points(self):
        """测试自定义参考点"""
        custom_refs = np.array([
            [0.0, 1.0],
            [0.5, 0.5],
            [1.0, 0.0]
        ])

        bias = NSGA3ReferencePointBias(
            reference_points=custom_refs
        )

        assert len(bias.reference_points) == 3
        assert np.allclose(bias.reference_points, custom_refs)

    def test_distance_calculation(self):
        """测试距离计算"""
        bias = NSGA3ReferencePointBias(
            num_objectives=2,
            divisions=4
        )

        # 创建归一化的目标值
        objectives = np.array([0.5, 0.5])
        distances = bias._compute_distances_to_references(objectives)

        assert len(distances) == len(bias.reference_points)
        assert np.all(distances >= 0)

    def test_compute_bias(self):
        """测试偏置计算"""
        bias = NSGA3ReferencePointBias(
            num_objectives=2,
            divisions=4,
            initial_weight=0.6
        )

        # 创建上下文（包含种群信息用于归一化）
        objectives = np.array([0.5, 0.5])
        pop_objectives = np.array([
            [0.0, 1.0],
            [0.5, 0.5],
            [1.0, 0.0]
        ])

        context = OptimizationContext(
            generation=0,
            individual=np.array([1.0, 2.0]),
            metrics={
                'objectives': objectives,
                'population_objectives': pop_objectives
            }
        )

        # 计算偏置
        bias_value = bias.compute(np.array([1.0, 2.0]), context)

        # 应该返回一个数值
        assert isinstance(bias_value, (int, float))
        assert bias_value >= 0  # 距离总是非负

    def test_reference_point_usage_tracking(self):
        """测试参考点使用统计"""
        bias = NSGA3ReferencePointBias(
            num_objectives=2,
            divisions=4
        )

        # 计算几次偏置
        for i in range(5):
            context = OptimizationContext(
                generation=i,
                individual=np.array([1.0, 2.0]),
                metrics={
                    'objectives': np.array([0.5, 0.5]),
                    'population_objectives': np.array([[0.0, 1.0], [0.5, 0.5], [1.0, 0.0]])
                }
            )
            bias.compute(np.array([1.0, 2.0]), context)

        # 检查使用统计
        stats = bias.get_statistics()
        assert 'reference_point_usage' in stats
        assert np.sum(stats['reference_point_usage']) == 5

    def test_adaptive_nsga3_bias(self):
        """测试自适应NSGA3偏置"""
        bias = AdaptiveNSGA3Bias(
            num_objectives=2,
            divisions=4,
            adaptation_window=50
        )

        assert bias.adaptive is True
        assert bias.adaptation_window == 50

    def test_statistics(self):
        """测试统计信息获取"""
        bias = NSGA3ReferencePointBias(
            num_objectives=2,
            divisions=4
        )

        # 计算一次偏置以生成历史记录
        context = OptimizationContext(
            generation=0,
            individual=np.array([1.0, 2.0]),
            metrics={
                'objectives': np.array([0.5, 0.5]),
                'population_objectives': np.array([[0.0, 1.0], [0.5, 0.5], [1.0, 0.0]])
            }
        )
        bias.compute(np.array([1.0, 2.0]), context)

        # 获取统计信息
        stats = bias.get_statistics()

        assert 'num_reference_points' in stats
        assert 'distance_metric' in stats
        assert stats['num_reference_points'] > 0


class TestSPEA2Bias:
    """测试SPEA2强度偏置"""

    def test_import(self):
        """测试SPEA2偏置能否正确导入"""
        assert SPEA2StrengthBias is not None
        assert AdaptiveSPEA2Bias is not None
        assert HybridSPEA2NSGA2Bias is not None

    def test_initialization(self):
        """测试SPEA2偏置初始化"""
        bias = SPEA2StrengthBias(
            k_nearest=5,
            strength_weight=0.6,
            density_weight=0.4
        )

        assert bias.name == "spea2_strength"
        assert bias.k_nearest == 5
        assert bias.strength_weight == 0.6
        assert bias.density_weight == 0.4

    def test_dominance_check(self):
        """测试支配关系判断"""
        bias = SPEA2StrengthBias()

        # obj1支配obj2 (所有目标都不更差，至少一个更好)
        obj1 = np.array([1.0, 1.0])
        obj2 = np.array([2.0, 2.0])
        assert bias._dominates(obj1, obj2) == True
        assert bias._dominates(obj2, obj1) == False

        # 不确定（各自有优势）
        obj3 = np.array([1.0, 3.0])
        obj4 = np.array([3.0, 1.0])
        assert bias._dominates(obj3, obj4) == False
        assert bias._dominates(obj4, obj3) == False

    def test_strength_computation(self):
        """测试强度计算"""
        bias = SPEA2StrengthBias()

        # 当前个体
        objectives = np.array([1.0, 1.0])

        # 种群（当前个体支配2个，被1个支配）
        population_objectives = np.array([
            [2.0, 2.0],  # 被支配
            [3.0, 3.0],  # 被支配
            [0.5, 0.5],  # 支配当前个体
            [1.5, 1.5],  # 被支配
        ])

        strength = bias._compute_strength(objectives, population_objectives)

        # 支配了3个，强度 = -3/(4+1) = -0.6
        assert np.isclose(strength, -0.6)

    def test_density_computation(self):
        """测试密度计算"""
        bias = SPEA2StrengthBias(k_nearest=3)

        # 当前个体
        objectives = np.array([0.5, 0.5])

        # 种群
        population_objectives = np.array([
            [0.0, 0.0],
            [0.2, 0.2],
            [0.4, 0.4],
            [0.6, 0.6],
            [1.0, 1.0],
        ])

        density = bias._compute_density(objectives, population_objectives)

        # 密度应该是负值（距离越大越好）
        assert density < 0
        # 密度在[-1, 0]区间
        assert density >= -1.0

    def test_compute_bias(self):
        """测试偏置计算"""
        bias = SPEA2StrengthBias(
            k_nearest=3,
            strength_weight=0.6,
            density_weight=0.4,
            initial_weight=0.5
        )

        # 创建上下文
        objectives = np.array([1.0, 1.0])
        population_objectives = np.array([
            [0.5, 0.5],
            [1.0, 1.0],
            [1.5, 1.5],
            [2.0, 2.0],
            [2.5, 2.5],
        ])

        context = OptimizationContext(
            generation=0,
            individual=np.array([1.0, 2.0]),
            population=[[1.0, 2.0] for _ in range(5)],
            metrics={
                'objectives': objectives,
                'population_objectives': population_objectives
            }
        )

        # 计算偏置
        bias_value = bias.compute(np.array([1.0, 2.0]), context)

        # 应该返回一个数值
        assert isinstance(bias_value, (int, float))

    def test_adaptive_spea2_bias(self):
        """测试自适应SPEA2偏置"""
        bias = AdaptiveSPEA2Bias(
            k_nearest=5,
            adaptation_window=50
        )

        assert bias.adaptive is True
        assert bias.adaptation_window == 50

    def test_hybrid_bias_initialization(self):
        """测试混合SPEA2-NSGA2偏置初始化"""
        bias = HybridSPEA2NSGA2Bias(
            k_nearest=5,
            strength_weight=0.4,
            spea2_density_weight=0.3,
            nsga2_crowding_weight=0.3
        )

        assert bias.name == "spea2_strength"  # 继承自SPEA2
        assert bias.nsga2_crowding_weight == 0.3

    def test_statistics(self):
        """测试统计信息获取"""
        bias = SPEA2StrengthBias(k_nearest=3)

        # 计算一次偏置以生成历史记录
        context = OptimizationContext(
            generation=0,
            individual=np.array([1.0, 2.0]),
            population=[[1.0, 2.0] for _ in range(5)],
            metrics={
                'objectives': np.array([1.0, 1.0]),
                'population_objectives': np.array([
                    [0.5, 0.5],
                    [1.0, 1.0],
                    [1.5, 1.5],
                    [2.0, 2.0],
                    [2.5, 2.5],
                ])
            }
        )
        bias.compute(np.array([1.0, 2.0]), context)

        # 获取统计信息
        stats = bias.get_statistics()

        assert 'k_nearest' in stats
        assert 'strength_weight' in stats
        assert 'density_weight' in stats


class TestBiasIntegration:
    """测试偏置与求解器的集成"""

    def test_bias_manager_integration(self):
        """测试偏置管理器集成"""
        from nsgablack.bias import UniversalBiasManager

        # 创建偏置管理器
        manager = UniversalBiasManager()

        # 添加各种偏置
        moead_bias = MOEADDecompositionBias(
            weight_vector=np.array([0.5, 0.5]),
            initial_weight=0.5
        )
        nsga3_bias = NSGA3ReferencePointBias(
            num_objectives=2,
            divisions=4,
            initial_weight=0.4
        )
        spea2_bias = SPEA2StrengthBias(
            k_nearest=5,
            initial_weight=0.3
        )

        # 添加到管理器
        manager.algorithmic_manager.add_bias(moead_bias)
        manager.algorithmic_manager.add_bias(nsga3_bias)
        manager.algorithmic_manager.add_bias(spea2_bias)

        # 验证添加成功
        assert len(manager.algorithmic_manager.biases) == 3

    def test_bias_combination(self):
        """测试偏置组合计算"""
        from nsgablack.bias import UniversalBiasManager

        manager = UniversalBiasManager()

        # 添加多个偏置
        moead_bias = MOEADDecompositionBias(
            weight_vector=np.array([0.5, 0.5]),
            initial_weight=0.5
        )
        spea2_bias = SPEA2StrengthBias(
            k_nearest=5,
            initial_weight=0.3
        )

        manager.algorithmic_manager.add_bias(moead_bias)
        manager.algorithmic_manager.add_bias(spea2_bias)

        # 创建上下文
        context = OptimizationContext(
            generation=0,
            individual=np.array([1.0, 2.0]),
            population=[[1.0, 2.0] for _ in range(5)],
            metrics={
                'objectives': np.array([1.0, 1.0]),
                'population_objectives': np.array([
                    [0.5, 0.5],
                    [1.0, 1.0],
                    [1.5, 1.5],
                    [2.0, 2.0],
                    [2.5, 2.5],
                ])
            }
        )

        # 计算总偏置
        total_bias = manager.compute_total_algorithmic_bias(
            np.array([1.0, 2.0]), context
        )

        # 总偏置应该是两个偏置的加权和
        assert isinstance(total_bias, (int, float))


class TestEdgeCases:
    """测试边界条件"""

    def test_moad_with_single_objective(self):
        """测试MOEAD在单目标情况下的行为"""
        bias = MOEADDecompositionBias(
            weight_vector=np.array([1.0]),
            method='weighted_sum'
        )

        objectives = np.array([5.0])
        context = OptimizationContext(
            generation=0,
            individual=np.array([1.0]),
            metrics={'objectives': objectives}
        )

        bias_value = bias.compute(np.array([1.0]), context)
        assert isinstance(bias_value, (int, float))

    def test_nsga3_with_high_dimensional_objectives(self):
        """测试NSGA3在高维目标下的行为"""
        bias = NSGA3ReferencePointBias(
            num_objectives=5,  # 5个目标
            divisions=2
        )

        # 应该生成参考点
        assert len(bias.reference_points) > 0
        assert bias.reference_points.shape[1] == 5

    def test_spea2_with_small_population(self):
        """测试SPEA2在小种群下的行为"""
        bias = SPEA2StrengthBias(k_nearest=5)

        # 种群小于k
        population_objectives = np.array([
            [0.5, 0.5],
            [1.0, 1.0],
        ])

        objectives = np.array([0.7, 0.7])
        density = bias._compute_density(objectives, population_objectives)

        # 应该仍然能计算（使用实际可用的邻居数）
        assert isinstance(density, (int, float))

    def test_missing_metrics(self):
        """测试缺少必要指标时的行为"""
        bias = MOEADDecompositionBias(
            weight_vector=np.array([0.5, 0.5])
        )

        # 不提供objectives
        context = OptimizationContext(
            generation=0,
            individual=np.array([1.0, 2.0]),
            metrics={}
        )

        bias_value = bias.compute(np.array([1.0, 2.0]), context)

        # 应该返回0（无法计算）
        assert bias_value == 0.0


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "--tb=short"])
