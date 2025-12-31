"""
MOEA/D算法使用示例（无可视化版本）

展示如何使用MOEA/D求解多目标优化问题，以及与偏置系统的集成。
"""

import sys
import os
import numpy as np
import json

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from .core.base import BlackBoxProblem
    from .core.problems import ZDT1BlackBox, ZDT3BlackBox, DTLZ2BlackBox
    from .solvers.moead import BlackBoxSolverMOEAD, create_moead_solver
    from .solvers.nsga2 import BlackBoxSolverNSGAII
    from .bias.bias_v2 import UniversalBiasManager
    from .bias.bias_library_algorithmic import DiversityBias, ConvergenceBias
    from .bias.bias_library_domain import ConstraintBias
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保在项目根目录运行")
    sys.exit(1)


def save_results_to_file(results, filename):
    """保存结果到JSON文件"""
    try:
        # 转换numpy数组为列表以便JSON序列化
        def convert_for_json(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, dict):
                return {k: convert_for_json(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_for_json(item) for item in obj]
            return obj

        with open(filename, 'w') as f:
            json.dump(results, f, indent=2, default=convert_for_json)
        print(f"结果已保存到: {filename}")
    except Exception as e:
        print(f"保存文件失败: {e}")


def analyze_pareto_front(objectives, problem_name):
    """分析Pareto前沿"""
    if len(objectives) == 0:
        print("没有Pareto解可分析")
        return

    print(f"\n{problem_name} Pareto前沿分析:")
    print(f"  解的数量: {len(objectives)}")

    # 计算每个目标的统计信息
    for i in range(objectives.shape[1]):
        obj_values = objectives[:, i]
        print(f"  目标{i+1}: 最小值={np.min(obj_values):.4f}, 最大值={np.max(obj_values):.4f}, "
              f"平均值={np.mean(obj_values):.4f}")

    # 计算解的分布
    if len(objectives) > 1:
        distances = []
        for i in range(len(objectives)):
            for j in range(i+1, len(objectives)):
                dist = np.linalg.norm(objectives[i] - objectives[j])
                distances.append(dist)
        print(f"  平均解间距离: {np.mean(distances):.4f}")
        print(f"  最小解间距离: {np.min(distances):.4f}")
        print(f"  最大解间距离: {np.max(distances):.4f}")


def example_basic_moead():
    """基础MOEA/D使用示例"""
    print("="*60)
    print("基础MOEA/D使用示例 - ZDT1问题")
    print("="*60)

    # 创建ZDT1测试问题
    problem = ZDT1BlackBox(dimension=30)

    # 创建MOEA/D求解器
    moead = BlackBoxSolverMOEAD(problem)
    moead.population_size = 100
    moead.max_generations = 100
    moead.enable_progress_log = True
    moead.report_interval = 20

    # 运行优化
    result = moead.run()

    # 显示结果
    print(f"\n优化完成！")
    print(f"找到 {len(result['pareto_solutions'])} 个Pareto最优解")
    print(f"运行代数: {result['generation']}")
    print(f"评估次数: {result['evaluation_count']}")

    # 分析Pareto前沿
    analyze_pareto_front(result['pareto_objectives'], "ZDT1")

    # 保存结果
    results_data = {
        'problem': 'ZDT1',
        'algorithm': 'MOEA/D',
        'parameters': {
            'population_size': moead.population_size,
            'max_generations': moead.max_generations,
            'decomposition_method': moead.decomposition_method
        },
        'results': {
            'pareto_count': len(result['pareto_solutions']),
            'generation': result['generation'],
            'evaluation_count': result['evaluation_count']
        },
        'pareto_objectives': result['pareto_objectives'].tolist(),
        'pareto_solutions': result['pareto_solutions'].tolist()
    }
    save_results_to_file(results_data, 'moead_zdt1_results.json')

    return result


def example_moead_with_bias():
    """MOEA/D与偏置系统集成示例"""
    print("="*60)
    print("MOEA/D与偏置系统集成示例")
    print("="*60)

    # 创建带约束的问题
    class ConstrainedZDT1(BlackBoxProblem):
        def __init__(self):
            super().__init__(
                name="ConstrainedZDT1",
                dimension=10,
                bounds={f'x{i}': (0, 1) for i in range(10)}
            )

        def evaluate(self, x):
            # ZDT1目标函数
            f1 = x[0]
            g = 1 + 9 * np.sum(x[1:]) / (len(x) - 1)
            h = 1 - np.sqrt(f1 / g)
            f2 = g * h
            return [f1, f2]

        def evaluate_constraints(self, x):
            # 添加约束：x0 + x1 <= 1.5
            return np.array([max(0, x[0] + x[1] - 1.5)])

        def get_num_objectives(self):
            return 2

    problem = ConstrainedZDT1()

    # 创建偏置管理器
    bias_manager = UniversalBiasManager()

    # 添加多样性偏置
    bias_manager.algorithmic_manager.add_bias(
        DiversityBias(weight=0.2)
    )

    # 添加约束偏置
    constraint_bias = ConstraintBias(weight=3.0)
    constraint_bias.add_hard_constraint(lambda x: max(0, x[0] + x[1] - 1.5))
    bias_manager.domain_manager.add_bias(constraint_bias)

    # 测试1：不使用偏置
    print("\n1. 不使用偏置系统")
    moead_no_bias = BlackBoxSolverMOEAD(problem)
    moead_no_bias.population_size = 50
    moead_no_bias.max_generations = 50
    moead_no_bias.enable_progress_log = False
    result_no_bias = moead_no_bias.run()

    # 测试2：使用偏置
    print("\n2. 使用偏置系统")
    moead_with_bias = BlackBoxSolverMOEAD(problem)
    moead_with_bias.population_size = 50
    moead_with_bias.max_generations = 50
    moead_with_bias.enable_bias = True
    moead_with_bias.bias_manager = bias_manager
    result_with_bias = moead_with_bias.run()

    # 统计可行解
    def count_feasible(solutions):
        count = 0
        for sol in solutions:
            if np.all(problem.evaluate_constraints(sol) <= 1e-6):
                count += 1
        return count

    feasible_no_bias = count_feasible(result_no_bias['pareto_solutions'])
    feasible_with_bias = count_feasible(result_with_bias['pareto_solutions'])

    print(f"\n结果对比:")
    print(f"不使用偏置: {len(result_no_bias['pareto_solutions'])} 个解, {feasible_no_bias} 个可行")
    print(f"使用偏置: {len(result_with_bias['pareto_solutions'])} 个解, {feasible_with_bias} 个可行")

    if feasible_no_bias > 0:
        improvement = (feasible_with_bias - feasible_no_bias) / feasible_no_bias * 100
        print(f"可行解提升: {improvement:.1f}%")

    # 保存对比结果
    comparison_data = {
        'problem': 'ConstrainedZDT1',
        'algorithm': 'MOEA/D',
        'bias_comparison': {
            'without_bias': {
                'pareto_count': len(result_no_bias['pareto_solutions']),
                'feasible_count': feasible_no_bias
            },
            'with_bias': {
                'pareto_count': len(result_with_bias['pareto_solutions']),
                'feasible_count': feasible_with_bias
            }
        }
    }
    save_results_to_file(comparison_data, 'moead_bias_comparison.json')

    return result_no_bias, result_with_bias


def example_three_objective():
    """三目标优化示例"""
    print("="*60)
    print("三目标优化示例 - DTLZ2问题")
    print("="*60)

    # 创建DTL2三目标问题
    problem = DTLZ2BlackBox(dimension=12, n_objectives=3)

    # 配置MOEA/D
    moead = BlackBoxSolverMOEAD(problem)
    moead.population_size = 105  # 105 = C(14,2)，适合3目标
    moead.max_generations = 100
    moead.enable_progress_log = True
    moead.decomposition_method = 'tchebycheff'  # 高维目标推荐使用Tchebycheff

    # 运行优化
    result = moead.run()

    print(f"\n三目标优化完成！")
    print(f"找到 {len(result['pareto_solutions'])} 个Pareto最优解")
    print(f"目标维度: {result['pareto_objectives'].shape[1]}")

    # 分析三目标结果
    print("\n三目标结果分析:")
    for i in range(3):
        obj_values = result['pareto_objectives'][:, i]
        print(f"  目标{i+1}: 范围[{np.min(obj_values):.3f}, {np.max(obj_values):.3f}], 平均值{np.mean(obj_values):.3f}")

    # 保存三目标结果
    three_obj_data = {
        'problem': 'DTL2_3obj',
        'algorithm': 'MOEA/D',
        'objectives': 3,
        'parameters': {
            'population_size': moead.population_size,
            'decomposition_method': moead.decomposition_method
        },
        'results': {
            'pareto_count': len(result['pareto_solutions']),
            'generation': result['generation'],
            'evaluation_count': result['evaluation_count']
        },
        'pareto_objectives': result['pareto_objectives'].tolist()
    }
    save_results_to_file(three_obj_data, 'moead_dtlz2_3obj.json')

    return result


def example_comparison_nsga2():
    """MOEA/D与NSGA-II对比示例"""
    print("="*60)
    print("MOEA/D与NSGA-II性能对比")
    print("="*60)

    # 使用ZDT3问题（有断开的Pareto前沿）
    problem = ZDT3BlackBox(dimension=30)

    # MOEA/D配置
    print("\n运行MOEA/D...")
    moead = create_moead_solver(
        problem,
        population_size=100,
        max_generations=100,
        decomposition_method='tchebycheff'
    )
    moead.enable_progress_log = False
    result_moead = moead.run()

    # NSGA-II配置
    print("\n运行NSGA-II...")
    nsga2 = BlackBoxSolverNSGAII(problem)
    nsga2.pop_size = 100
    nsga2.max_generations = 100
    nsga2.enable_progress_log = False
    result_nsga2 = nsga2.run()

    # 提取结果
    moead_solutions = result_moead['pareto_objectives']
    nsga2_solutions = result_nsga2['pareto_solutions']['objectives']

    # 分析对比结果
    def calculate_hypervolume_indicator(objectives, reference_point=(1.1, 1.1)):
        """简化的超体积指标"""
        if len(objectives) == 0:
            return 0
        # 计算在参考点内的解的比例
        feasible_points = objectives[
            np.all(objectives <= reference_point, axis=1)
        ]
        return len(feasible_points) / len(objectives)

    moead_hv = calculate_hypervolume_indicator(moead_solutions)
    nsga2_hv = calculate_hypervolume_indicator(nsga2_solutions)

    print(f"\n性能对比:")
    print(f"MOEA/D:")
    print(f"  - Pareto解数量: {len(moead_solutions)}")
    print(f"  - 超体积指标: {moead_hv:.4f}")

    print(f"\nNSGA-II:")
    print(f"  - Pareto解数量: {len(nsga2_solutions)}")
    print(f"  - 超体积指标: {nsga2_hv:.4f}")

    if nsga2_hv > 0:
        hv_improvement = ((moead_hv - nsga2_hv) / nsga2_hv * 100)
        print(f"\n超体积相对差异: {hv_improvement:+.1f}%")

    # 详细统计
    print("\n详细统计:")
    print("MOEA/D:")
    analyze_pareto_front(moead_solutions, "MOEA/D")

    print("\nNSGA-II:")
    analyze_pareto_front(nsga2_solutions, "NSGA-II")

    # 保存对比结果
    comparison_data = {
        'problem': 'ZDT3',
        'algorithms': {
            'moead': {
                'pareto_count': len(moead_solutions),
                'hypervolume': moead_hv
            },
            'nsga2': {
                'pareto_count': len(nsga2_solutions),
                'hypervolume': nsga2_hv
            }
        }
    }
    save_results_to_file(comparison_data, 'moead_vs_nsga2_comparison.json')

    return result_moead, result_nsga2


def example_decomposition_methods():
    """不同分解方法对比示例"""
    print("="*60)
    print("不同分解方法对比示例")
    print("="*60)

    problem = ZDT1BlackBox(dimension=10)

    methods = ['weighted_sum', 'tchebycheff']
    results = {}

    for method in methods:
        print(f"\n测试分解方法: {method}")

        moead = BlackBoxSolverMOEAD(problem)
        moead.population_size = 50
        moead.max_generations = 50
        moead.decomposition_method = method
        moead.enable_progress_log = False

        result = moead.run()
        results[method] = result

        print(f"  找到 {len(result['pareto_solutions'])} 个解")
        print(f"  运行代数: {result['generation']}")
        print(f"  评估次数: {result['evaluation_count']}")

        # 分析结果分布
        analyze_pareto_front(result['pareto_objectives'], f"{method}方法")

    # 保存分解方法对比结果
    decomposition_data = {
        'problem': 'ZDT1',
        'decomposition_methods': {}
    }

    for method, result in results.items():
        decomposition_data['decomposition_methods'][method] = {
            'pareto_count': len(result['pareto_solutions']),
            'generation': result['generation'],
            'evaluation_count': result['evaluation_count'],
            'final_fitness_mean': np.mean(result.get('pareto_objectives', [])) if len(result.get('pareto_objectives', [])) > 0 else 0
        }

    save_results_to_file(decomposition_data, 'moead_decomposition_comparison.json')

    return results


def main():
    """主函数 - 运行所有示例"""
    print("MOEA/D算法使用示例（无可视化版本）")
    print("="*80)

    examples = [
        ("基础MOEA/D使用", example_basic_moead),
        ("MOEA/D与偏置系统", example_moead_with_bias),
        ("三目标优化", example_three_objective),
        ("与NSGA-II对比", example_comparison_nsga2),
        ("分解方法对比", example_decomposition_methods)
    ]

    results = {}

    for name, example_func in examples:
        try:
            print(f"\n{'='*20} {name} {'='*20}")
            results[name] = example_func()
            print(f"✅ {name} 完成")
        except Exception as e:
            print(f"❌ {name} 失败: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*80)
    print("所有示例运行完成！")
    print("\n生成的结果文件:")
    print("- moead_zdt1_results.json: ZDT1问题的优化结果")
    print("- moead_bias_comparison.json: 偏置系统对比结果")
    print("- moead_dtlz2_3obj.json: 三目标优化结果")
    print("- moead_vs_nsga2_comparison.json: 算法性能对比")
    print("- moead_decomposition_comparison.json: 分解方法对比")

    print("\n提示: 可以使用这些JSON文件进行进一步的分析和可视化")


if __name__ == "__main__":
    main()