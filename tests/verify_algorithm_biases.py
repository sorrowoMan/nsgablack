"""
快速验证脚本 - 验证新增的算法偏置能否正确使用

运行方式：
    python tests/verify_algorithm_biases.py
"""

import sys
from pathlib import Path

# 添加项目根目录到路径

import numpy as np


def test_imports():
    """测试所有偏置能否正确导入"""
    print("=" * 60)
    print("测试1: 导入测试")
    print("=" * 60)

    try:
        from nsgablack.bias.algorithmic import (
            MOEADDecompositionBias,
            AdaptiveMOEADBias,
            NSGA3ReferencePointBias,
            AdaptiveNSGA3Bias,
            SPEA2StrengthBias,
            AdaptiveSPEA2Bias,
            HybridSPEA2NSGA2Bias
        )
        print("✓ 所有偏置类导入成功")
        return True
    except ImportError as e:
        print(f"✗ 导入失败: {e}")
        return False


def test_moad_bias():
    """测试MOEAD偏置"""
    print("\n" + "=" * 60)
    print("测试2: MOEAD分解偏置")
    print("=" * 60)

    try:
        from nsgablack.bias.algorithmic import MOEADDecompositionBias, AdaptiveMOEADBias

        # 测试标准MOEAD
        print("  创建标准MOEAD偏置...")
        moead = MOEADDecompositionBias(
            weight_vector=np.array([0.5, 0.5]),
            method='tchebycheff',
            initial_weight=0.5
        )
        print(f"  ✓ 名称: {moead.name}")
        print(f"  ✓ 方法: {moead.method}")
        print(f"  ✓ 权重向量: {moead.weight_vector}")

        # 测试权重归一化
        print("  测试权重归一化...")
        moead2 = MOEADDecompositionBias(
            weight_vector=np.array([2.0, 2.0]),  # 未归一化
            method='tchebycheff'
        )
        assert np.allclose(moead2.weight_vector, [0.5, 0.5])
        print("  ✓ 权重自动归一化正确")

        # 测试Tchebycheff聚合
        print("  测试Tchebycheff聚合函数...")
        moead.ideal_point = np.array([0.0, 0.0])
        agg_value = moead._tchebycheff_aggregation(np.array([2.0, 4.0]))
        expected = 2.0  # max(0.5*2, 0.5*4)
        assert agg_value == expected
        print(f"  ✓ Tchebycheff聚合值: {agg_value} (期望: {expected})")

        # 测试加权和聚合
        print("  测试加权和聚合函数...")
        moead_ws = MOEADDecompositionBias(
            weight_vector=np.array([0.3, 0.7]),
            method='weighted_sum'
        )
        agg_value = moead_ws._weighted_sum_aggregation(np.array([2.0, 4.0]))
        expected = 3.4  # 0.3*2 + 0.7*4
        assert np.isclose(agg_value, expected)
        print(f"  ✓ 加权和聚合值: {agg_value} (期望: {expected})")

        # 测试自适应MOEAD
        print("  创建自适应MOEAD偏置...")
        adaptive_moead = AdaptiveMOEADBias(
            weight_vector=np.array([0.5, 0.5]),
            adaptation_window=50
        )
        assert adaptive_moead.adaptive == True
        print("  ✓ 自适应MOEAD偏置创建成功")

        print("✓ MOEAD偏置所有测试通过")
        return True

    except Exception as e:
        print(f"✗ MOEAD偏置测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_nsga3_bias():
    """测试NSGA3偏置"""
    print("\n" + "=" * 60)
    print("测试3: NSGA3参考点偏置")
    print("=" * 60)

    try:
        from nsgablack.bias.algorithmic import NSGA3ReferencePointBias, AdaptiveNSGA3Bias

        # 测试Das-Dennis生成
        print("  测试Das-Dennis参考点生成...")
        nsga3_2obj = NSGA3ReferencePointBias(
            num_objectives=2,
            divisions=12
        )
        expected_points = 13  # C(12+2-1, 2-1) = C(13, 1) = 13
        assert len(nsga3_2obj.reference_points) == expected_points
        print(f"  ✓ 2目标12分割生成{len(nsga3_2obj.reference_points)}个参考点 (期望: {expected_points})")

        # 测试3目标
        print("  测试3目标参考点生成...")
        nsga3_3obj = NSGA3ReferencePointBias(
            num_objectives=3,
            divisions=2
        )
        expected_points = 6  # C(2+3-1, 3-1) = C(4, 2) = 6
        assert len(nsga3_3obj.reference_points) == expected_points
        print(f"  ✓ 3目标2分割生成{len(nsga3_3obj.reference_points)}个参考点 (期望: {expected_points})")

        # 测试参考点归一化
        print("  测试参考点归一化...")
        for point in nsga3_2obj.reference_points:
            assert np.all(point >= 0) and np.all(point <= 1)
            assert np.isclose(np.sum(point), 1.0)
        print("  ✓ 所有参考点都在[0,1]区间且和为1")

        # 测试自定义参考点
        print("  测试自定义参考点...")
        custom_refs = np.array([
            [0.0, 1.0],
            [0.5, 0.5],
            [1.0, 0.0]
        ])
        nsga3_custom = NSGA3ReferencePointBias(
            reference_points=custom_refs
        )
        assert len(nsga3_custom.reference_points) == 3
        print(f"  ✓ 自定义参考点设置成功，共{len(nsga3_custom.reference_points)}个")

        # 测试距离计算
        print("  测试距离计算...")
        objectives = np.array([0.5, 0.5])
        distances = nsga3_2obj._compute_distances_to_references(objectives)
        assert len(distances) == len(nsga3_2obj.reference_points)
        assert np.all(distances >= 0)
        print(f"  ✓ 距离计算成功，最小距离: {np.min(distances):.4f}")

        # 测试自适应NSGA3
        print("  创建自适应NSGA3偏置...")
        adaptive_nsga3 = AdaptiveNSGA3Bias(
            num_objectives=2,
            divisions=4,
            adaptation_window=100
        )
        assert adaptive_nsga3.adaptive == True
        print("  ✓ 自适应NSGA3偏置创建成功")

        print("✓ NSGA3偏置所有测试通过")
        return True

    except Exception as e:
        print(f"✗ NSGA3偏置测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_spea2_bias():
    """测试SPEA2偏置"""
    print("\n" + "=" * 60)
    print("测试4: SPEA2强度偏置")
    print("=" * 60)

    try:
        from nsgablack.bias.algorithmic import (
            SPEA2StrengthBias,
            AdaptiveSPEA2Bias,
            HybridSPEA2NSGA2Bias
        )

        # 测试标准SPEA2
        print("  创建标准SPEA2偏置...")
        spea2 = SPEA2StrengthBias(
            k_nearest=5,
            strength_weight=0.6,
            density_weight=0.4
        )
        print(f"  ✓ 名称: {spea2.name}")
        print(f"  ✓ k值: {spea2.k_nearest}")
        print(f"  ✓ 强度权重: {spea2.strength_weight}")
        print(f"  ✓ 密度权重: {spea2.density_weight}")

        # 测试支配关系判断
        print("  测试Pareto支配关系判断...")
        obj1 = np.array([1.0, 1.0])
        obj2 = np.array([2.0, 2.0])
        assert spea2._dominates(obj1, obj2) == True
        assert spea2._dominates(obj2, obj1) == False
        print("  ✓ 支配关系判断正确")

        # 测试强度计算
        print("  测试强度计算...")
        objectives = np.array([1.0, 1.0])
        pop_objectives = np.array([
            [2.0, 2.0],  # 被支配
            [3.0, 3.0],  # 被支配
            [0.5, 0.5],  # 支配当前个体
            [1.5, 1.5],  # 被支配
        ])
        strength = spea2._compute_strength(objectives, pop_objectives)
        expected_strength = -0.6  # -3/(4+1)
        assert np.isclose(strength, expected_strength)
        print(f"  ✓ 强度值: {strength} (期望: {expected_strength})")

        # 测试密度计算
        print("  测试密度计算...")
        density = spea2._compute_density(objectives, pop_objectives)
        assert density < 0  # 应该是负值
        assert density >= -1.0  # 应该在[-1, 0]区间
        print(f"  ✓ 密度值: {density:.4f}")

        # 测试自适应SPEA2
        print("  创建自适应SPEA2偏置...")
        adaptive_spea2 = AdaptiveSPEA2Bias(
            k_nearest=5,
            adaptation_window=50
        )
        assert adaptive_spea2.adaptive == True
        print("  ✓ 自适应SPEA2偏置创建成功")

        # 测试混合SPEA2-NSGA2
        print("  创建混合SPEA2-NSGA2偏置...")
        hybrid = HybridSPEA2NSGA2Bias(
            k_nearest=5,
            strength_weight=0.4,
            spea2_density_weight=0.3,
            nsga2_crowding_weight=0.3
        )
        assert hybrid.nsga2_crowding_weight == 0.3
        print("  ✓ 混合偏置创建成功")

        print("✓ SPEA2偏置所有测试通过")
        return True

    except Exception as e:
        print(f"✗ SPEA2偏置测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_bias_combination():
    """测试偏置组合"""
    print("\n" + "=" * 60)
    print("测试5: 偏置组合")
    print("=" * 60)

    try:
        from nsgablack.bias.algorithmic import (
            MOEADDecompositionBias,
            NSGA3ReferencePointBias,
            SPEA2StrengthBias
        )
        from nsgablack.bias import UniversalBiasManager

        print("  创建偏置管理器...")
        manager = UniversalBiasManager()
        print("  ✓ 偏置管理器创建成功")

        # 添加三个偏置
        print("  添加多种算法偏置...")
        moead_bias = MOEADDecompositionBias(
            weight_vector=np.array([0.5, 0.5]),
            initial_weight=0.3
        )
        nsga3_bias = NSGA3ReferencePointBias(
            num_objectives=2,
            divisions=4,
            initial_weight=0.3
        )
        spea2_bias = SPEA2StrengthBias(
            k_nearest=5,
            initial_weight=0.2
        )

        manager.algorithmic_manager.add_bias(moead_bias)
        manager.algorithmic_manager.add_bias(nsga3_bias)
        manager.algorithmic_manager.add_bias(spea2_bias)

        print(f"  ✓ 成功添加{len(manager.algorithmic_manager.biases)}个偏置")

        # 测试偏置列表
        biases = manager.algorithmic_manager.get_all_biases()
        assert len(biases) == 3
        print("  ✓ 偏置列表获取成功")

        print("✓ 偏置组合测试通过")
        return True

    except Exception as e:
        print(f"✗ 偏置组合测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_bias_compute():
    """测试偏置计算"""
    print("\n" + "=" * 60)
    print("测试6: 偏置计算功能")
    print("=" * 60)

    try:
        from nsgablack.bias.algorithmic import MOEADDecompositionBias
        from nsgablack.bias.core.base import OptimizationContext

        print("  创建MOEAD偏置...")
        moead = MOEADDecompositionBias(
            weight_vector=np.array([0.5, 0.5]),
            method='tchebycheff',
            initial_weight=0.5
        )

        print("  创建优化上下文...")
        context = OptimizationContext(
            generation=0,
            individual=np.array([1.0, 2.0]),
            metrics={'objectives': np.array([2.0, 4.0])}
        )
        print("  ✓ 上下文创建成功")

        print("  计算偏置值...")
        bias_value = moead.compute(np.array([1.0, 2.0]), context)
        assert isinstance(bias_value, (int, float))
        print(f"  ✓ 偏置值: {bias_value:.4f}")

        print("  测试理想点更新...")
        context2 = OptimizationContext(
            generation=1,
            individual=np.array([0.5, 0.5]),
            metrics={'objectives': np.array([1.0, 2.0])}
        )
        moead.compute(np.array([0.5, 0.5]), context2)
        print(f"  ✓ 理想点更新为: {moead.ideal_point}")

        print("  获取统计信息...")
        stats = moead.get_statistics()
        assert 'method' in stats
        assert 'weight_vector' in stats
        assert 'ideal_point' in stats
        print("  ✓ 统计信息获取成功")
        print(f"    - 方法: {stats['method']}")
        print(f"    - 权重向量: {stats['weight_vector']}")
        print(f"    - 理想点: {stats['ideal_point']}")

        print("✓ 偏置计算功能测试通过")
        return True

    except Exception as e:
        print(f"✗ 偏置计算测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_high_dimensional():
    """测试高维目标问题"""
    print("\n" + "=" * 60)
    print("测试7: 高维目标问题")
    print("=" * 60)

    try:
        from nsgablack.bias.algorithmic import MOEADDecompositionBias, NSGA3ReferencePointBias

        # 测试5目标MOEAD
        print("  测试5目标MOEAD偏置...")
        moead_5obj = MOEADDecompositionBias(
            weight_vector=np.array([0.2, 0.2, 0.2, 0.2, 0.2]),
            method='tchebycheff'
        )
        assert len(moead_5obj.weight_vector) == 5
        print("  ✓ 5目标MOEAD偏置创建成功")

        # 测试5目标NSGA3
        print("  测试5目标NSGA3偏置...")
        nsga3_5obj = NSGA3ReferencePointBias(
            num_objectives=5,
            divisions=1
        )
        assert nsga3_5obj.reference_points.shape[1] == 5
        print(f"  ✓ 5目标NSGA3偏置创建成功，生成{len(nsga3_5obj.reference_points)}个参考点")

        print("✓ 高维目标问题测试通过")
        return True

    except Exception as e:
        print(f"✗ 高维目标问题测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("算法偏置快速验证测试")
    print("=" * 60)

    tests = [
        ("导入测试", test_imports),
        ("MOEAD偏置", test_moad_bias),
        ("NSGA3偏置", test_nsga3_bias),
        ("SPEA2偏置", test_spea2_bias),
        ("偏置组合", test_bias_combination),
        ("偏置计算", test_bias_compute),
        ("高维目标", test_high_dimensional),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n[X] 测试 '{test_name}' 发生异常: {e}")
            results.append((test_name, False))

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "[OK] 通过" if result else "[FAIL] 失败"
        print(f"  {test_name}: {status}")

    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n🎉 所有测试通过！新增的算法偏置可以正确使用。")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查问题。")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
