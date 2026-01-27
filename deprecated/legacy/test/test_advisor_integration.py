"""
测试多智能体系统与ADVISOR角色的集成
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    # 测试1: 检查 AgentRole 导入
    print("=" * 60)
    print("测试 1: 检查 AgentRole 定义")
    print("=" * 60)

    from multi_agent.core.role import AgentRole

    print(f"✅ 成功导入 AgentRole")
    print(f"可用的角色: {[role.value for role in AgentRole]}")

    # 检查是否包含 ADVISOR
    if AgentRole.ADVISOR:
        print(f"✅ ADVISOR 角色已定义: {AgentRole.ADVISOR.value}")
    else:
        print("❌ ADVISOR 角色未找到")

    # 测试2: 检查求解器导入
    print("\n" + "=" * 60)
    print("测试 2: 检查 MultiAgentBlackBoxSolver 导入")
    print("=" * 60)

    from solvers.multi_agent import MultiAgentBlackBoxSolver
    print(f"✅ 成功导入 MultiAgentBlackBoxSolver")

    # 测试3: 创建简单问题
    print("\n" + "=" * 60)
    print("测试 3: 创建简单测试问题")
    print("=" * 60)

    import numpy as np
    from core.base import BlackBoxProblem

    class SimpleZDT1(BlackBoxProblem):
        def __init__(self, dimension=10):
            super().__init__(dimension)
            self.bounds = np.array([[0, 1]] * dimension)

        def evaluate(self, x):
            f1 = x[0]
            g = 1 + 9 * np.sum(x[1:]) / (self.dimension - 1)
            f2 = g * (1 - np.sqrt(x[0] / g))
            return [f1, f2]

        def evaluate_constraints(self, x):
            return []  # 无约束

    problem = SimpleZDT1(dimension=10)
    print(f"✅ 创建了 ZDT1 测试问题 (维度: {problem.dimension})")

    # 测试4: 创建多智能体求解器（包含 ADVISOR）
    print("\n" + "=" * 60)
    print("测试 4: 创建多智能体求解器（包含 ADVISOR）")
    print("=" * 60)

    config = {
        'total_population': 100,
        'agent_ratios': {
            AgentRole.EXPLORER: 0.25,
            AgentRole.EXPLOITER: 0.35,
            AgentRole.WAITER: 0.15,
            AgentRole.ADVISOR: 0.15,  # 🌟 包含建议者
            AgentRole.COORDINATOR: 0.10
        },
        'max_generations': 5,  # 只运行几代测试
        'advisory_method': 'statistical'  # 使用统计方法（无需额外依赖）
    }

    solver = MultiAgentBlackBoxSolver(problem, config=config)

    print(f"✅ 创建了多智能体求解器")
    print(f"种群配置: {solver.config['agent_ratios']}")
    print(f"建议者方法: {solver.config.get('advisory_method', 'statistical')}")
    print(f"各种群数量:")
    for role, pop in solver.agent_populations.items():
        print(f"  - {role.value}: {len(pop.population)} 个个体")

    # 测试5: 运行优化
    print("\n" + "=" * 60)
    print("测试 5: 运行几代优化测试")
    print("=" * 60)

    result = solver.run()

    print(f"\n✅ 优化完成！")
    print(f"找到 {len(result)} 个 Pareto 最优解")
    print(f"总评估次数: {solver.stats['evaluations']}")
    print(f"信息交流次数: {solver.stats['communications']}")
    print(f"策略调整次数: {solver.stats['adaptations']}")

    # 测试6: 测试不同的建议方法
    print("\n" + "=" * 60)
    print("测试 6: 测试不同的建议方法")
    print("=" * 60)

    methods_to_test = ['statistical']  # 默认只测试统计方法

    # 尝试测试贝叶斯方法（如果有 scipy）
    try:
        import scipy
        methods_to_test.append('bayesian')
        print("✅ 检测到 scipy，可以测试贝叶斯方法")
    except ImportError:
        print("⚠️  未安装 scipy，跳过贝叶斯方法测试")

    # 尝试测试 ML 方法（如果有 sklearn）
    try:
        import sklearn
        methods_to_test.append('ml')
        print("✅ 检测到 sklearn，可以测试 ML 方法")
    except ImportError:
        print("⚠️  未安装 sklearn，跳过 ML 方法测试")

    for method in methods_to_test:
        print(f"\n测试建议方法: {method}")
        solver_test = MultiAgentBlackBoxSolver(problem, config={
            'total_population': 50,
            'agent_ratios': config['agent_ratios'],
            'max_generations': 2,
            'advisory_method': method
        })

        result_test = solver_test.run()
        print(f"✅ {method} 方法测试完成，找到 {len(result_test)} 个解")

    # 最终总结
    print("\n" + "=" * 60)
    print("🎉 所有测试完成！")
    print("=" * 60)
    print("\n多智能体系统（包含 ADVISOR）集成成功！")
    print("\n角色配置:")
    print(f"  - Explorer (探索者): {config['agent_ratios'][AgentRole.EXPLORER]:.0%}")
    print(f"  - Exploiter (开发者): {config['agent_ratios'][AgentRole.EXPLOITER]:.0%}")
    print(f"  - Waiter (等待者): {config['agent_ratios'][AgentRole.WAITER]:.0%}")
    print(f"  - Advisor (建议者) 🌟: {config['agent_ratios'][AgentRole.ADVISOR]:.0%}")
    print(f"  - Coordinator (协调者): {config['agent_ratios'][AgentRole.COORDINATOR]:.0%}")

except Exception as e:
    print(f"\n❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
