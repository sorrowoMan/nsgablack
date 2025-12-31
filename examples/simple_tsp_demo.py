"""
简化版TSP演示
避免编码问题，专注于核心功能演示
"""

import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import numpy as np

def main():
    print("=" * 50)
    print("TSP 图偏置系统演示")
    print("=" * 50)

    try:
        # 测试导入
        from bias.bias_graph_abstract import GraphProblemFactory
        from bias.bias_graph_constraints import TSPConstraintBias
        from bias.bias_base import OptimizationContext
        from core import BlackBoxSolverNSGAII
        from core.problems import BlackBoxProblem

        print("1. 所有模块导入成功!")

        # 2. 创建TSP问题
        print("\n2. 创建TSP问题...")

        # 创建4城市TSP
        distance_matrix = np.array([
            [0, 10, 15, 20],
            [10, 0, 35, 25],
            [15, 35, 0, 30],
            [20, 25, 30, 0]
        ])

        tsp = GraphProblemFactory.create_tsp(distance_matrix)
        print(f"   TSP问题创建成功: {tsp.get_name()}")
        print(f"   城市数量: {tsp.num_nodes}")
        print(f"   编码方式: {tsp.get_encoding().value}")

        # 3. 创建数学约束
        print("\n3. 创建数学约束...")

        constraint = TSPConstraintBias(tsp.num_nodes)
        print(f"   约束偏置创建成功: {constraint.name}")

        # 4. 测试约束验证
        print("\n4. 测试约束验证...")

        test_solutions = [
            [0, 1, 2, 3],      # 有效
            [0, 1, 2, 1],      # 重复
            [0, 1, 2, 4],      # 超出范围
        ]

        for i, sol in enumerate(test_solutions):
            x = np.array(sol, dtype=float)
            result = constraint.validate_constraints(
                x, OptimizationContext(generation=1, population_size=100, current_objective=0.0)
            )
            status = "有效" if result.is_valid else "无效"
            print(f"   解 {i+1}: {sol} -> {status}")
            if not result.is_valid:
                print(f"          原因: {result.violation_type}")

        # 5. 创建优化目标函数
        print("\n5. 创建优化目标函数...")

        def combined_objective(x: np.ndarray) -> float:
            # 抽象框架计算目标值
            objective_value = tsp.evaluate_solution(x)

            # 数学逻辑验证约束
            constraint_penalty = constraint.compute(
                x, OptimizationContext(generation=1, population_size=100, current_objective=objective_value)
            )

            return objective_value + constraint_penalty

        print("   目标函数创建成功!")

        # 6. 创建优化问题
        print("\n6. 创建优化问题...")

        problem = BlackBoxProblem(
            name="tsp_demo",
            n_var=4,
            n_obj=1,
            n_constr=0,
            xl=0.0,
            xu=3.0,
            function=combined_objective
        )

        print(f"   优化问题创建成功")
        print(f"   变量数: {problem.n_var}")

        # 7. 执行优化
        print("\n7. 执行优化...")

        solver = BlackBoxSolverNSGAII(problem)
        solver.population_size = 20

        print("   开始优化...")
        solver.run(max_gen=10)

        # 8. 分析结果
        print("\n8. 分析结果...")

        best_valid_solution = None
        best_distance = float('inf')

        for solution in solver.population:
            if tsp.validate_solution(solution).is_valid:
                distance = tsp.evaluate_solution(solution)
                if distance < best_distance:
                    best_distance = distance
                    best_valid_solution = solution

        if best_valid_solution is not None:
            tour = tsp.decode_solution(best_valid_solution)
            print(f"   找到有效解!")
            print(f"   最优路径: {' -> '.join(map(str, tour))} -> {tour[0]}")
            print(f"   路径长度: {best_distance:.2f}")
        else:
            print("   未找到有效解")

        print("\n" + "=" * 50)
        print("演示完成!")
        print("抽象框架与数学逻辑偏置完美结合!")
        print("=" * 50)

    except ImportError as e:
        print(f"导入错误: {e}")
        print("请确保所有必要的模块都存在")
    except Exception as e:
        print(f"运行错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()