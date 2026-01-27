# -*- coding: utf-8 -*-
"""
测试多智能体系统与ADVISOR角色的集成
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("测试 1: 检查 AgentRole 定义")
print("=" * 60)

from multi_agent.core.role import AgentRole

print("[OK] 成功导入 AgentRole")
print("可用的角色:")
for role in AgentRole:
    print(f"  - {role.name}: {role.value}")

print("\n" + "=" * 60)
print("测试 2: 检查 MultiAgentBlackBoxSolver 导入")
print("=" * 60)

from solvers.multi_agent import MultiAgentBlackBoxSolver
print("[OK] 成功导入 MultiAgentBlackBoxSolver")

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
print("[OK] 创建了 ZDT1 测试问题 (维度: {0})".format(problem.dimension))

print("\n" + "=" * 60)
print("测试 4: 创建多智能体求解器（包含 ADVISOR）")
print("=" * 60)

config = {
    'total_population': 100,
    'agent_ratios': {
        AgentRole.EXPLORER: 0.25,
        AgentRole.EXPLOITER: 0.35,
        AgentRole.WAITER: 0.15,
        AgentRole.ADVISOR: 0.15,  # 包含建议者
        AgentRole.COORDINATOR: 0.10
    },
    'max_generations': 5,  # 只运行几代测试
    'advisory_method': 'statistical'  # 使用统计方法（无需额外依赖）
}

solver = MultiAgentBlackBoxSolver(problem, config=config)

print("[OK] 创建了多智能体求解器")
print("种群配置:")
for role, ratio in solver.config['agent_ratios'].items():
    print("  - {0}: {1:.0%}".format(role.value, ratio))
print("建议者方法: {0}".format(solver.config.get('advisory_method', 'statistical')))
print("\n各种群数量:")
for role, pop in solver.agent_populations.items():
    print("  - {0}: {1} 个个体".format(role.value, len(pop.population)))

print("\n" + "=" * 60)
print("测试 5: 运行几代优化测试")
print("=" * 60)

result = solver.run()

print("\n[OK] 优化完成！")
print("找到 {0} 个 Pareto 最优解".format(len(result)))
print("总评估次数: {0}".format(solver.stats['evaluations']))
print("信息交流次数: {0}".format(solver.stats['communications']))
print("策略调整次数: {0}".format(solver.stats['adaptations']))

print("\n" + "=" * 60)
print("测试完成！多智能体系统（包含 ADVISOR）集成成功！")
print("=" * 60)
print("\n角色配置:")
print("  - Explorer (探索者): {0:.0%}".format(config['agent_ratios'][AgentRole.EXPLORER]))
print("  - Exploiter (开发者): {0:.0%}".format(config['agent_ratios'][AgentRole.EXPLOITER]))
print("  - Waiter (等待者): {0:.0%}".format(config['agent_ratios'][AgentRole.WAITER]))
print("  - Advisor (建议者): {0:.0%}".format(config['agent_ratios'][AgentRole.ADVISOR]))
print("  - Coordinator (协调者): {0:.0%}".format(config['agent_ratios'][AgentRole.COORDINATOR]))
