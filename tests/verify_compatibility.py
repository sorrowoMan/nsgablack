"""
偏置系统兼容性验证脚本

验证 BiasModule 和 UniversalBiasManager 的正确集成。
运行此脚本以确保所有组件正常工作。
"""

import sys
import os

import numpy as np
from typing import List


class SimpleProblem:
    """简单的测试问题"""

    def __init__(self):
        self.dimension = 2
        self.bounds = [(0, 1), (0, 1)]

    def evaluate(self, x):
        """目标函数：x[0]^2 + x[1]^2"""
        return x[0]**2 + x[1]**2

    def evaluate_constraints(self, x):
        """约束：x[0] + x[1] <= 1"""
        return np.array([x[0] + x[1] - 1])


def test_bias_module_import():
    """测试 1：BiasModule 导入"""
    print("=" * 60)
    print("测试 1：BiasModule 导入")
    print("=" * 60)

    try:
        from nsgablack.bias import BiasModule
        print("✓ BiasModule 导入成功")
        return True
    except ImportError as e:
        print(f"✗ BiasModule 导入失败: {e}")
        return False


def test_universal_manager_import():
    """测试 2：UniversalBiasManager 导入"""
    print("\n" + "=" * 60)
    print("测试 2：UniversalBiasManager 导入")
    print("=" * 60)

    try:
        from nsgablack.bias import UniversalBiasManager, DiversityBias, ConstraintBias
        print("✓ UniversalBiasManager 导入成功")
        print("✓ DiversityBias 导入成功")
        print("✓ ConstraintBias 导入成功")
        return True
    except ImportError as e:
        print(f"✗ 导入失败: {e}")
        return False


def test_bias_module_creation():
    """测试 3：BiasModule 创建和添加偏置"""
    print("\n" + "=" * 60)
    print("测试 3：BiasModule 创建和添加偏置")
    print("=" * 60)

    try:
        from nsgablack.bias import BiasModule, DiversityBias, ConstraintBias

        bias = BiasModule()
        bias.add(DiversityBias(weight=0.2))
        bias.add(ConstraintBias(weight=2.0))

        print(f"✓ BiasModule 创建成功")
        print(f"✓ 添加了 {len(bias.list_biases())} 个偏置")
        print(f"  偏置列表: {bias.list_biases()}")
        return True
    except Exception as e:
        print(f"✗ 创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_universal_manager_creation():
    """测试 4：UniversalBiasManager 创建和添加偏置"""
    print("\n" + "=" * 60)
    print("测试 4：UniversalBiasManager 创建和添加偏置")
    print("=" * 60)

    try:
        from nsgablack.bias import UniversalBiasManager, DiversityBias, ConstraintBias

        manager = UniversalBiasManager()
        manager.add_algorithmic_bias(DiversityBias(weight=0.2))
        manager.add_domain_bias(ConstraintBias(weight=2.0))

        print(f"✓ UniversalBiasManager 创建成功")
        print(f"✓ 添加了 {len(manager.list_biases())} 个偏置")
        print(f"  偏置列表: {manager.list_biases()}")
        return True
    except Exception as e:
        print(f"✗ 创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_from_universal_manager():
    """测试 5：从 UniversalBiasManager 转换为 BiasModule"""
    print("\n" + "=" * 60)
    print("测试 5：从 UniversalBiasManager 转换为 BiasModule")
    print("=" * 60)

    try:
        from nsgablack.bias import UniversalBiasManager, DiversityBias, from_universal_manager

        manager = UniversalBiasManager()
        manager.add_algorithmic_bias(DiversityBias(weight=0.2))

        bias_module = from_universal_manager(manager)

        print(f"✓ 转换成功")
        print(f"✓ BiasModule 有 {len(bias_module.list_biases())} 个偏置")
        print(f"  偏置列表: {bias_module.list_biases()}")

        # 验证内部管理器一致
        assert bias_module.to_universal_manager() is manager
        print("✓ 内部管理器引用一致")

        return True
    except Exception as e:
        print(f"✗ 转换失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_bias_computation():
    """测试 6：偏置计算功能"""
    print("\n" + "=" * 60)
    print("测试 6：偏置计算功能")
    print("=" * 60)

    try:
        from nsgablack.bias import BiasModule, DiversityBias
        from nsgablack.bias.core.base import OptimizationContext

        # 创建问题
        problem = SimpleProblem()

        # 创建偏置模块
        bias = BiasModule()
        bias.add(DiversityBias(weight=0.2))

        # 测试计算
        x = np.array([0.5, 0.5])
        objective_value = problem.evaluate(x)

        # 创建上下文
        context = {
            "problem": problem,
            "constraints": [0.0],
            "constraint_violation": 0.0,
            "individual_id": 0,
            "generation": 10,
            "population": [x]
        }

        # 计算偏置
        biased_value = bias.compute_bias(x, objective_value, 0, context)

        print(f"✓ 原始目标值: {objective_value:.4f}")
        print(f"✓ 偏置后值: {biased_value:.4f}")
        print(f"✓ 偏置影响: {biased_value - objective_value:.4f}")

        return True
    except Exception as e:
        print(f"✗ 计算失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_solver_integration():
    """测试 7：与求解器的集成"""
    print("\n" + "=" * 60)
    print("测试 7：与求解器的集成")
    print("=" * 60)

    try:
        from nsgablack.core.solver import BlackBoxSolverNSGAII
        from nsgablack.core.base import BlackBoxProblem
        from nsgablack.bias import BiasModule, DiversityBias

        class TestProblem(BlackBoxProblem):
            def __init__(self):
                super().__init__(name="test", dimension=2, bounds=[(0, 1), (0, 1)])

            def evaluate(self, x):
                return x[0]**2 + x[1]**2

        # 创建问题和求解器
        problem = TestProblem()
        solver = BlackBoxSolverNSGAII(problem)
        solver.pop_size = 20
        solver.max_generations = 10

        # 配置偏置
        bias = BiasModule()
        bias.add(DiversityBias(weight=0.2))
        solver.bias_module = bias
        solver.enable_bias = True

        print("✓ 求解器配置成功")
        print(f"  种群大小: {solver.pop_size}")
        print(f"  最大迭代: {solver.max_generations}")
        print(f"  偏置模块: {solver.bias_module}")
        print(f"  启用偏置: {solver.enable_bias}")

        # 注意：不运行完整优化，只验证配置
        print("✓ 配置验证通过（未运行完整优化）")

        return True
    except Exception as e:
        print(f"✗ 集成失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_enable_disable():
    """测试 8：启用/禁用功能"""
    print("\n" + "=" * 60)
    print("测试 8：启用/禁用功能")
    print("=" * 60)

    try:
        from nsgablack.bias import BiasModule, DiversityBias, ConstraintBias

        bias = BiasModule()
        bias.add(DiversityBias(weight=0.2))
        bias.add(ConstraintBias(weight=2.0))

        # 禁用所有
        bias.disable_all()
        print("✓ 禁用所有偏置")

        # 启用所有
        bias.enable_all()
        print("✓ 启用所有偏置")

        return True
    except Exception as e:
        print(f"✗ 操作失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("=" * 60)
    print("NSGABlack 偏置系统兼容性验证")
    print("=" * 60)

    tests = [
        ("BiasModule 导入", test_bias_module_import),
        ("UniversalBiasManager 导入", test_universal_manager_import),
        ("BiasModule 创建", test_bias_module_creation),
        ("UniversalBiasManager 创建", test_universal_manager_creation),
        ("Manager 转换", test_from_universal_manager),
        ("偏置计算", test_bias_computation),
        ("求解器集成", test_solver_integration),
        ("启用/禁用", test_enable_disable),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ 测试 '{name}' 抛出异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{status}: {name}")

    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n🎉 所有测试通过！偏置系统工作正常。")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查配置。")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
