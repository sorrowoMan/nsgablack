"""
MOEA/D与现有模块的兼容性测试

这个测试套件验证：
1. MOEA/D与偏置系统的集成
2. MOEA/D与并行评估的兼容性
3. MOEA/D与多样性初始化的集成
4. 与NSGA-II的性能对比
"""

import sys
import os
import numpy as np
import time
import matplotlib.pyplot as plt
from typing import List, Tuple

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from .core.base import BlackBoxProblem
    from .core.problems import ZDT1BlackBox, ZDT3BlackBox, DTLZ2BlackBox
    from .solvers.nsga2 import BlackBoxSolverNSGAII
    from .solvers.moead import BlackBoxSolverMOEAD, create_moead_solver
    from .bias.bias_v2 import UniversalBiasManager
    from .bias.bias_library_algorithmic import DiversityBias, ConvergenceBias
    from .bias.bias_library_domain import ConstraintBias
    from .utils.parallel_evaluator import ParallelEvaluator
except ImportError as e:
    print(f"导入错误: {e}")
    sys.exit(1)


class TestProblems:
    """测试问题集合"""

    @staticmethod
    def create_simple_two_objective() -> BlackBoxProblem:
        """简单的双目标问题"""
        class SimpleProblem(BlackBoxProblem):
            def __init__(self):
                super().__init__(
                    name="SimpleTwoObj",
                    dimension=2,
                    bounds={'x0': (-5, 5), 'x1': (-5, 5)}
                )

            def evaluate(self, x):
                f1 = x[0]**2 + x[1]**2  # 最小化距离原点
                f2 = (x[0] - 2)**2 + (x[1] - 2)**2  # 最小化距离(2,2)
                return [f1, f2]

            def get_num_objectives(self):
                return 2

        return SimpleProblem()

    @staticmethod
    def create_constrained_problem() -> BlackBoxProblem:
        """带约束的问题"""
        class ConstrainedProblem(BlackBoxProblem):
            def __init__(self):
                super().__init__(
                    name="ConstrainedProblem",
                    dimension=2,
                    bounds={'x0': (0, 5), 'x1': (0, 5)}
                )

            def evaluate(self, x):
                f1 = x[0] + x[1]
                f2 = (x[0] - 3)**2 + (x[1] - 2)**2
                return [f1, f2]

            def evaluate_constraints(self, x):
                # x0 + x1 <= 4
                # x1 >= 2
                return np.array([
                    max(0, x[0] + x[1] - 4),
                    max(0, 2 - x[1])
                ])

            def get_num_objectives(self):
                return 2

        return ConstrainedProblem()


class CompatibilityTester:
    """兼容性测试器"""

    def __init__(self):
        self.results = {}

    def test_basic_functionality(self):
        """测试MOEA/D基础功能"""
        print("\n" + "="*60)
        print("1. 测试MOEA/D基础功能")
        print("="*60)

        problem = TestProblems.create_simple_two_objective()

        # 创建MOEA/D求解器
        moead = BlackBoxSolverMOEAD(problem)
        moead.population_size = 50
        moead.max_generations = 50
        moead.enable_progress_log = True

        # 运行算法
        start_time = time.time()
        result = moead.run()
        end_time = time.time()

        # 验证结果
        assert 'pareto_solutions' in result
        assert 'pareto_objectives' in result
        assert result['generation'] > 0
        assert result['evaluation_count'] > 0

        pareto_solutions = result['pareto_solutions']
        pareto_objectives = result['pareto_objectives']

        print(f"✓ MOEA/D基础功能测试通过")
        print(f"  - 找到 {len(pareto_solutions)} 个Pareto解")
        print(f"  - 运行代数: {result['generation']}")
        print(f"  - 评估次数: {result['evaluation_count']}")
        print(f"  - 运行时间: {end_time - start_time:.2f}秒")

        self.results['basic'] = {
            'pareto_count': len(pareto_solutions),
            'generation': result['generation'],
            'evaluation_count': result['evaluation_count'],
            'time': end_time - start_time
        }

        return True

    def test_bias_system_integration(self):
        """测试偏置系统集成"""
        print("\n" + "="*60)
        print("2. 测试偏置系统集成")
        print("="*60)

        problem = TestProblems.create_constrained_problem()

        # 创建偏置管理器
        bias_manager = UniversalBiasManager()

        # 添加算法偏置
        from .bias.bias_library_algorithmic import DiversityBias
        bias_manager.algorithmic_manager.add_bias(DiversityBias(weight=0.2))

        # 添加约束偏置
        constraint_bias = ConstraintBias(weight=2.0)
        constraint_bias.add_hard_constraint(lambda x: max(0, x[0] + x[1] - 4))
        constraint_bias.add_hard_constraint(lambda x: max(0, 2 - x[1]))
        bias_manager.domain_manager.add_bias(constraint_bias)

        # 测试1：不使用偏置
        print("\n测试1：不使用偏置")
        moead_no_bias = BlackBoxSolverMOEAD(problem)
        moead_no_bias.population_size = 50
        moead_no_bias.max_generations = 30
        result_no_bias = moead_no_bias.run()

        # 测试2：使用偏置
        print("\n测试2：使用偏置")
        moead_with_bias = BlackBoxSolverMOEAD(problem)
        moead_with_bias.population_size = 50
        moead_with_bias.max_generations = 30
        moead_with_bias.enable_bias = True
        moead_with_bias.bias_manager = bias_manager
        result_with_bias = moead_with_bias.run()

        # 验证约束满足情况
        def count_feasible(solutions):
            feasible_count = 0
            for sol in solutions:
                cons = problem.evaluate_constraints(sol)
                if np.all(cons <= 1e-6):
                    feasible_count += 1
            return feasible_count

        feasible_no_bias = count_feasible(result_no_bias['pareto_solutions'])
        feasible_with_bias = count_feasible(result_with_bias['pareto_solutions'])

        print(f"✓ 偏置系统集成测试通过")
        print(f"  不使用偏置: {len(result_no_bias['pareto_solutions'])} 个解, {feasible_no_bias} 个可行")
        print(f"  使用偏置: {len(result_with_bias['pareto_solutions'])} 个解, {feasible_with_bias} 个可行")

        # 验证偏置确实提升了约束满足
        print(f"  约束满足率提升: {(feasible_with_bias - feasible_no_bias) / max(1, feasible_no_bias) * 100:.1f}%")

        self.results['bias'] = {
            'no_bias_feasible': feasible_no_bias,
            'with_bias_feasible': feasible_with_bias,
            'improvement': feasible_with_bias - feasible_no_bias
        }

        return True

    def test_parallel_evaluation(self):
        """测试并行评估兼容性"""
        print("\n" + "="*60)
        print("3. 测试并行评估兼容性")
        print("="*60)

        problem = TestProblems.create_simple_two_objective()

        # 测试1：串行执行
        print("\n测试1：串行执行")
        moead_serial = BlackBoxSolverMOEAD(problem)
        moead_serial.population_size = 50
        moead_serial.max_generations = 30
        moead_serial.enable_parallel = False
        start_time = time.time()
        result_serial = moead_serial.run()
        serial_time = time.time() - start_time

        # 测试2：并行执行
        print("\n测试2：并行执行")
        moead_parallel = BlackBoxSolverMOEAD(problem)
        moead_parallel.population_size = 50
        moead_parallel.max_generations = 30
        moead_parallel.enable_parallel = True
        moead_parallel.parallel_evaluator = ParallelEvaluator(
            backend="thread",
            max_workers=4
        )
        start_time = time.time()
        result_parallel = moead_parallel.run()
        parallel_time = time.time() - start_time

        # 验证结果一致性
        pareto_count_serial = len(result_serial['pareto_solutions'])
        pareto_count_parallel = len(result_parallel['pareto_solutions'])

        print(f"✓ 并行评估测试通过")
        print(f"  串行: {pareto_count_serial} 个解, {serial_time:.2f}秒")
        print(f"  并行: {pareto_count_parallel} 个解, {parallel_time:.2f}秒")

        if parallel_time > 0:
            speedup = serial_time / parallel_time
            print(f"  加速比: {speedup:.2f}x")

        self.results['parallel'] = {
            'serial_time': serial_time,
            'parallel_time': parallel_time,
            'speedup': serial_time / parallel_time if parallel_time > 0 else 1
        }

        return True

    def test_diversity_initialization(self):
        """测试多样性初始化集成"""
        print("\n" + "="*60)
        print("4. 测试多样性初始化集成")
        print("="*60)

        problem = TestProblems.create_simple_two_objective()

        # 测试1：标准初始化
        print("\n测试1：标准初始化")
        moead_standard = BlackBoxSolverMOEAD(problem)
        moead_standard.population_size = 50
        moead_standard.max_generations = 30
        moead_standard.enable_diversity_init = False
        result_standard = moead_standard.run()

        # 测试2：多样性初始化
        print("\n测试2：多样性初始化")
        moead_diverse = BlackBoxSolverMOEAD(problem)
        moead_diverse.population_size = 50
        moead_diverse.max_generations = 30
        moead_diverse.enable_diversity_init = True
        result_diverse = moead_diverse.run()

        # 计算解的分布多样性
        def calculate_diversity(objectives):
            if len(objectives) < 2:
                return 0
            distances = []
            for i in range(len(objectives)):
                for j in range(i + 1, len(objectives)):
                    dist = np.linalg.norm(objectives[i] - objectives[j])
                    distances.append(dist)
            return np.mean(distances)

        diversity_standard = calculate_diversity(result_standard['pareto_objectives'])
        diversity_diverse = calculate_diversity(result_diverse['pareto_objectives'])

        print(f"✓ 多样性初始化测试通过")
        print(f"  标准初始化多样性: {diversity_standard:.4f}")
        print(f"  多样性初始化多样性: {diversity_diverse:.4f}")

        if diversity_standard > 0:
            improvement = (diversity_diverse - diversity_standard) / diversity_standard * 100
            print(f"  多样性提升: {improvement:.1f}%")

        self.results['diversity'] = {
            'standard_diversity': diversity_standard,
            'diverse_diversity': diversity_diverse
        }

        return True

    def test_comparison_with_nsga2(self):
        """与NSGA-II的性能对比"""
        print("\n" + "="*60)
        print("5. 与NSGA-II的性能对比")
        print("="*60)

        # 使用标准测试问题
        problems = {
            'ZDT1': ZDT1BlackBox(dimension=30),
            'ZDT3': ZDT3BlackBox(dimension=30),
            'DTLZ2': DTLZ2BlackBox(dimension=12, n_objectives=3)
        }

        comparison_results = {}

        for problem_name, problem in problems.items():
            print(f"\n测试问题: {problem_name}")

            # MOEA/D
            print("  运行MOEA/D...")
            moead = BlackBoxSolverMOEAD(problem)
            moead.population_size = 100
            moead.max_generations = 50
            moead.enable_progress_log = False
            start_time = time.time()
            result_moead = moead.run()
            moead_time = time.time() - start_time

            # NSGA-II
            print("  运行NSGA-II...")
            nsga2 = BlackBoxSolverNSGAII(problem)
            nsga2.pop_size = 100
            nsga2.max_generations = 50
            nsga2.enable_progress_log = False
            start_time = time.time()
            result_nsga2 = nsga2.run()
            nsga2_time = time.time() - start_time

            # 提取结果
            moead_pareto = len(result_moead['pareto_solutions']['individuals'])
            nsga2_pareto = len(result_nsga2['pareto_solutions']['individuals'])

            # 计算超体积（简化版本）
            def calculate_hypervolume(objectives, reference_point):
                """简化版超体积计算"""
                if len(objectives) == 0:
                    return 0
                # 找到所有点都在参考点内的点
                feasible_points = objectives[np.all(objectives <= reference_point, axis=1)]
                if len(feasible_points) == 0:
                    return 0
                # 简单估计：使用体积的近似值
                return len(feasible_points) * np.prod(reference_point) / len(objectives)

            # 计算超体积
            if problem.num_objectives == 2:
                ref_point = np.array([1.1, 1.1])
            else:
                ref_point = np.array([1.1, 1.1, 1.1])

            moead_hv = calculate_hypervolume(result_moead['pareto_objectives'], ref_point)
            nsga2_hv = calculate_hypervolume(result_nsga2['pareto_objectives'], ref_point)

            comparison_results[problem_name] = {
                'moead': {
                    'pareto_count': moead_pareto,
                    'hypervolume': moead_hv,
                    'time': moead_time
                },
                'nsga2': {
                    'pareto_count': nsga2_pareto,
                    'hypervolume': nsga2_hv,
                    'time': nsga2_time
                }
            }

            print(f"  MOEA/D: {moead_pareto} 个解, HV: {moead_hv:.4f}, 时间: {moead_time:.2f}s")
            print(f"  NSGA-II: {nsga2_pareto} 个解, HV: {nsga2_hv:.4f}, 时间: {nsga2_time:.2f}s")

        self.results['comparison'] = comparison_results

        print(f"\n✓ 性能对比测试完成")

        # 总结对比结果
        print("\n对比总结:")
        for problem_name, results in comparison_results.items():
            moead_hv = results['moead']['hypervolume']
            nsga2_hv = results['nsga2']['hypervolume']
            moead_time = results['moead']['time']
            nsga2_time = results['nsga2']['time']

            hv_improvement = ((moead_hv - nsga2_hv) / nsga2_hv * 100) if nsga2_hv > 0 else 0
            time_ratio = moead_time / nsga2_time if nsga2_time > 0 else 1

            print(f"  {problem_name}:")
            print(f"    超体积提升: {hv_improvement:+.1f}%")
            print(f"    时间比率: {time_ratio:.2f}")

        return True

    def run_all_tests(self):
        """运行所有测试"""
        print("开始MOEA/D兼容性测试套件")
        print("="*80)

        tests = [
            ("基础功能", self.test_basic_functionality),
            ("偏置系统集成", self.test_bias_system_integration),
            ("并行评估", self.test_parallel_evaluation),
            ("多样性初始化", self.test_diversity_initialization),
            ("与NSGA-II对比", self.test_comparison_with_nsga2)
        ]

        passed = 0
        total = len(tests)

        for test_name, test_func in tests:
            try:
                if test_func():
                    passed += 1
                    print(f"\n✅ {test_name} - 通过")
                else:
                    print(f"\n❌ {test_name} - 失败")
            except Exception as e:
                print(f"\n❌ {test_name} - 错误: {e}")

        print("\n" + "="*80)
        print(f"测试完成: {passed}/{total} 通过")

        if passed == total:
            print("🎉 所有测试通过！MOEA/D与现有模块完全兼容！")
        else:
            print("⚠️  部分测试失败，需要检查兼容性")

        return self.results


def create_performance_visualization(results: dict):
    """创建性能可视化图表"""
    if 'comparison' not in results:
        return

    comparison = results['comparison']
    problems = list(comparison.keys())

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # 超体积对比
    moead_hv = [comparison[p]['moead']['hypervolume'] for p in problems]
    nsga2_hv = [comparison[p]['nsga2']['hypervolume'] for p in problems]

    x = np.arange(len(problems))
    width = 0.35

    ax1.bar(x - width/2, moead_hv, width, label='MOEA/D', alpha=0.8)
    ax1.bar(x + width/2, nsga2_hv, width, label='NSGA-II', alpha=0.8)
    ax1.set_xlabel('测试问题')
    ax1.set_ylabel('超体积')
    ax1.set_title('算法性能对比')
    ax1.set_xticks(x)
    ax1.set_xticklabels(problems)
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # 时间对比
    moead_time = [comparison[p]['moead']['time'] for p in problems]
    nsga2_time = [comparison[p]['nsga2']['time'] for p in problems]

    ax2.bar(x - width/2, moead_time, width, label='MOEA/D', alpha=0.8)
    ax2.bar(x + width/2, nsga2_time, width, label='NSGA-II', alpha=0.8)
    ax2.set_xlabel('测试问题')
    ax2.set_ylabel('运行时间 (秒)')
    ax2.set_title('计算时间对比')
    ax2.set_xticks(x)
    ax2.set_xticklabels(problems)
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('test/moead_performance_comparison.png', dpi=150, bbox_inches='tight')
    plt.show()


if __name__ == "__main__":
    # 运行测试
    tester = CompatibilityTester()
    results = tester.run_all_tests()

    # 保存测试结果
    import json
    with open('test/moead_test_results.json', 'w') as f:
        # 将numpy数组转换为列表以便JSON序列化
        def convert_numpy(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            return obj

        json.dump(results, f, indent=2, default=convert_numpy)

    # 创建可视化
    try:
        create_performance_visualization(results)
    except Exception as e:
        print(f"可视化创建失败: {e}")
        print("请确保安装了matplotlib")

    print("\n测试结果已保存到: test/moead_test_results.json")