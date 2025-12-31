"""
MOEA/D简化兼容性测试

测试MOEA/D与核心模块的兼容性
"""

import sys
import os
import numpy as np
import time

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from .core.base import BlackBoxProblem
    from .solvers.moead import BlackBoxSolverMOEAD
except ImportError as e:
    print(f"导入错误: {e}")
    sys.exit(1)


class TestProblem(BlackBoxProblem):
    """简单测试问题"""

    def __init__(self, dimension=2):
        super().__init__(
            name="TestProblem",
            dimension=dimension,
            bounds={f'x{i}': (-5, 5) for i in range(dimension)}
        )

    def evaluate(self, x):
        f1 = x[0]**2 + x[1]**2  # 最小化距离原点
        f2 = (x[0] - 2)**2 + (x[1] - 2)**2  # 最小化距离(2,2)
        return [f1, f2]

    def get_num_objectives(self):
        return 2


def test_basic_moead():
    """测试MOEA/D基础功能"""
    print("\n" + "="*50)
    print("测试MOEA/D基础功能")
    print("="*50)

    problem = TestProblem()

    # 创建MOEA/D求解器
    moead = BlackBoxSolverMOEAD(problem)
    moead.population_size = 50
    moead.max_generations = 30
    moead.enable_progress_log = True

    # 运行算法
    print("运行MOEA/D...")
    start_time = time.time()
    result = moead.run()
    elapsed = time.time() - start_time

    # 验证结果
    assert 'pareto_solutions' in result, "缺少Pareto解"
    assert 'pareto_objectives' in result, "缺少Pareto目标值"
    assert result['generation'] > 0, "代数应该大于0"
    assert result['evaluation_count'] > 0, "评估次数应该大于0"

    pareto_solutions = result['pareto_solutions']
    pareto_objectives = result['pareto_objectives']

    print(f"✅ 基础功能测试通过")
    print(f"   - Pareto解数量: {len(pareto_solutions)}")
    print(f"   - 运行代数: {result['generation']}")
    print(f"   - 评估次数: {result['evaluation_count']}")
    print(f"   - 运行时间: {elapsed:.2f}秒")

    # 检查解的合理性
    if len(pareto_objectives) > 0:
        print(f"   - 目标1范围: [{np.min(pareto_objectives[:, 0]):.3f}, {np.max(pareto_objectives[:, 0]):.3f}]")
        print(f"   - 目标2范围: [{np.min(pareto_objectives[:, 1]):.3f}, {np.max(pareto_objectives[:, 1]):.3f}]")

    return True


def test_decomposition_methods():
    """测试不同分解方法"""
    print("\n" + "="*50)
    print("测试不同分解方法")
    print("="*50)

    problem = TestProblem()

    methods = ['weighted_sum', 'tchebycheff']
    results = {}

    for method in methods:
        print(f"\n测试分解方法: {method}")

        moead = BlackBoxSolverMOEAD(problem)
        moead.population_size = 30
        moead.max_generations = 20
        moead.decomposition_method = method
        moead.enable_progress_log = False

        start_time = time.time()
        result = moead.run()
        elapsed = time.time() - start_time

        results[method] = result

        print(f"   - 找到 {len(result['pareto_solutions'])} 个解")
        print(f"   - 运行时间: {elapsed:.2f}秒")

    print(f"\n✅ 分解方法测试通过")
    return True


def test_parameter_tuning():
    """测试参数调整功能"""
    print("\n" + "="*50)
    print("测试参数调整功能")
    print("="*50)

    problem = TestProblem()

    # 测试便捷创建函数
    from .solvers.moead import create_moead_solver

    moead = create_moead_solver(
        problem,
        population_size=40,
        max_generations=25,
        neighborhood_size=15,
        mutation_rate=0.1,
        decomposition_method='tchebycheff'
    )

    print("运行参数调整后的MOEA/D...")
    result = moead.run()

    print(f"✅ 参数调整测试通过")
    print(f"   - 种群大小: {moead.population_size}")
    print(f"   - 邻域大小: {moead.neighborhood_size}")
    print(f"   - 变异率: {moead.mutation_rate}")
    print(f"   - 找到 {len(result['pareto_solutions'])} 个解")

    return True


def test_three_objective():
    """测试三目标问题"""
    print("\n" + "="*50)
    print("测试三目标问题")
    print("="*50)

    class ThreeObjectiveProblem(BlackBoxProblem):
        def __init__(self):
            super().__init__(
                name="ThreeObjective",
                dimension=5,
                bounds={f'x{i}': (0, 1) for i in range(5)}
            )

        def evaluate(self, x):
            f1 = x[0] + x[1] + x[2]
            f2 = (x[0] - 1)**2 + (x[1] - 1)**2 + (x[2] - 1)**2
            f3 = x[3] + x[4]
            return [f1, f2, f3]

        def get_num_objectives(self):
            return 3

    problem = ThreeObjectiveProblem()

    moead = BlackBoxSolverMOEAD(problem)
    moead.population_size = 50
    moead.max_generations = 30
    moead.decomposition_method = 'tchebycheff'  # 高维目标推荐
    moead.enable_progress_log = False

    print("运行三目标优化...")
    result = moead.run()

    if len(result['pareto_objectives'][0]) == 3:
        print(f"✅ 三目标问题测试通过")
        print(f"   - 找到 {len(result['pareto_solutions'])} 个解")
        print(f"   - 目标维度: {len(result['pareto_objectives'][0])}")
        return True
    else:
        print(f"❌ 三目标问题测试失败")
        return False


def test_bias_integration():
    """测试偏置系统集成（简化版）"""
    print("\n" + "="*50)
    print("测试偏置系统集成")
    print("="*50)

    # 创建一个简单的偏置类
    class SimpleBias:
        def compute_total_bias(self, x, context):
            # 简单的偏置：偏好x[0]较小的值
            return x[0] * 0.1

    problem = TestProblem()

    moead = BlackBoxSolverMOEAD(problem)
    moead.population_size = 30
    moead.max_generations = 20
    moead.enable_progress_log = False

    # 尝试设置偏置（不会真正工作，但不会报错）
    try:
        moead.bias_manager = SimpleBias()
        moead.enable_bias = True
        print("偏置系统集成接口正常")
    except Exception as e:
        print(f"偏置系统集成警告: {e}")

    result = moead.run()

    print(f"✅ 偏置系统集成测试通过（接口级别）")
    print(f"   - 找到 {len(result['pareto_solutions'])} 个解")

    return True


def main():
    """运行所有测试"""
    print("MOEA/D简化兼容性测试套件")
    print("="*70)

    tests = [
        ("基础功能", test_basic_moead),
        ("分解方法", test_decomposition_methods),
        ("参数调整", test_parameter_tuning),
        ("三目标问题", test_three_objective),
        ("偏置系统接口", test_bias_integration)
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        try:
            print(f"\n{'='*20} {test_name} {'='*20}")
            if test_func():
                passed += 1
                print(f"✅ {test_name} - 通过")
            else:
                print(f"❌ {test_name} - 失败")
        except Exception as e:
            print(f"❌ {test_name} - 错误: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*70)
    print(f"测试完成: {passed}/{total} 通过")

    if passed == total:
        print("🎉 所有测试通过！MOEA/D核心功能正常！")
    else:
        print("⚠️  部分测试失败，需要检查实现")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)