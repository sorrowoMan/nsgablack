import numpy as np
import matplotlib.pyplot as plt

from .solver import BlackBoxSolverNSGAII
from .vns import BlackBoxSolverVNS
from .problems import (
    NeuralNetworkHyperparameterOptimization,
    EngineeringDesignOptimization,
    BusinessPortfolioOptimization,
)


def optimize_neural_network():
    problem = NeuralNetworkHyperparameterOptimization(dimension=4)
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 50
    solver.max_generations = 100
    solver.mutation_rate = 0.1
    solver.crossover_rate = 0.9
    solver.enable_diversity_init = True
    solver.use_history = True
    solver.enable_elite_retention = True
    solver.diversity_params['candidate_size'] = 200
    solver.diversity_params['similarity_threshold'] = 0.1
    solver.diversity_params['rejection_prob'] = 0.7
    solver.elite_retention_prob = 0.85
    print("开始优化神经网络超参数...")
    plt.tight_layout()
    plt.show()
    return solver


def optimize_engineering_design():
    problem = EngineeringDesignOptimization(dimension=3)
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 40
    solver.max_generations = 80
    solver.enable_diversity_init = True
    solver.enable_elite_retention = True
    print("开始优化工程设计...")
    plt.tight_layout()
    plt.show()
    return solver


def optimize_business_portfolio():
    problem = BusinessPortfolioOptimization(dimension=5)
    solver = BlackBoxSolverNSGAII(problem)
    solver.pop_size = 60
    solver.max_generations = 120
    solver.enable_diversity_init = True
    solver.enable_elite_retention = True
    print("开始优化投资组合...")
    plt.tight_layout()
    plt.show()
    return solver


def analyze_results(solver, problem_name):
    if solver.pareto_solutions is None or len(solver.pareto_solutions['individuals']) == 0:
        print("没有找到Pareto最优解")
        return
    pareto_front = solver.pareto_solutions
    print(f"\n=== {problem_name} 优化结果 ===")
    print(f"找到 {len(pareto_front['individuals'])} 个Pareto最优解")
    print(f"总函数评估次数: {solver.evaluation_count}")
    for i, (ind, obj) in enumerate(zip(pareto_front['individuals'][:5], pareto_front['objectives'][:5])):
        print(f"\n解 {i+1}:")
        for var_idx, var_name in enumerate(solver.variables):
            print(f"  {var_name}: {ind[var_idx]:.4f}")
        if problem_name == "神经网络超参数优化":
            hidden1 = int(ind[0]); hidden2 = int(ind[1]); lr = ind[2]; alpha = ind[3]
            accuracy = 1 - obj[0]
            complexity = obj[1] * 10000
            print(f"  隐藏层1: {hidden1} 神经元")
            print(f"  隐藏层2: {hidden2} 神经元")
            print(f"  学习率: {lr:.6f}")
            print(f"  正则化: {alpha:.6f}")
            print(f"  准确率: {accuracy:.4f}")
            print(f"  参数数量: {complexity:.0f}")
        elif problem_name == "工程梁设计优化":
            width, height, length = ind
            weight = obj[0]; deformation = obj[1]
            print(f"  宽度: {width:.3f} m")
            print(f"  高度: {height:.3f} m")
            print(f"  长度: {length:.3f} m")
            print(f"  重量: {weight:.2f} kg")
            print(f"  变形: {deformation:.6f} m")
        elif problem_name == "投资组合优化":
            weights = ind
            expected_return = -obj[0]
            risk = obj[1]
            print(f"  预期收益: {expected_return:.4f}")
            print(f"  风险: {risk:.6f}")
            print(f"  资产配置: {[f'{w:.3f}' for w in weights]}")


def optimize_with_vns():
    """示例：使用简单 VNS 求解 Sphere 函数（单目标）"""
    from .problems import SphereBlackBox

    problem = SphereBlackBox(dimension=2)
    solver = BlackBoxSolverVNS(problem)
    solver.max_iterations = 100
    solver.k_max = 4
    solver.shake_scale = 0.5
    print("使用 VNS 优化 Sphere 函数（示例）...")
    result = solver.run()
    print(f"VNS 结束，最优目标: {result['best_f']:.6f}，评估次数: {result['evaluations']}")
    return solver, result


if __name__ == "__main__":
    # 默认运行工程设计示例
    solver = optimize_engineering_design()
    # analyze_results(solver, "工程梁设计优化")
