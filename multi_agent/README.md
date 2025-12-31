# NSGABlack多智能体优化系统

## 概述

NSGABlack多智能体优化系统是一个基于偏置驱动的协同进化框架，通过多个专业化智能体的协作来解决复杂的黑盒优化问题。

## 核心理念

### 偏置驱动的智能体行为
- **无需机器学习**：通过精心设计的偏置函数控制智能体行为
- **角色专业化**：每个智能体角色专注于特定的搜索策略
- **自适应调整**：动态调整偏置参数以适应不同优化阶段

### 智能体角色分工
1. **Explorer（探索者）**：发现新的搜索区域
2. **Exploiter（开发者）**：深入优化有前景的区域
3. **Waiter（等待者）**：学习其他智能体的成功模式
4. **Coordinator（协调者）**：平衡全局策略

## 目录结构

```
multi_agent/
├── __init__.py                 # 模块初始化
├── core/                       # 核心框架
│   ├── __init__.py
│   ├── agent.py               # 智能体基类
│   ├── role.py                # 角色系统
│   ├── population.py          # 种群管理
│   ├── solver.py              # 多智能体求解器
│   └── communication.py       # 通信机制
├── bias/                       # 偏置驱动系统
│   ├── __init__.py
│   ├── profiles.py            # 偏置配置文件
│   ├── adapters.py            # 偏置适配器
│   ├── dynamics.py            # 动态偏置调整
│   └── learning.py            # 偏置学习机制
├── strategies/                 # 搜索策略
│   ├── __init__.py
│   ├── exploration.py         # 探索策略
│   ├── exploitation.py        # 开发策略
│   ├── learning.py            # 学习策略
│   └── coordination.py        # 协调策略
├── visualization/              # 可视化工具
│   ├── __init__.py
│   ├── agent_dashboard.py     # 智能体仪表盘
│   ├── evolution_plot.py      # 进化过程可视化
│   └── role_analysis.py       # 角色分析工具
├── analysis/                   # 分析工具
│   ├── __init__.py
│   ├── performance.py         # 性能分析
│   ├── contribution.py        # 贡献度分析
│   └── convergence.py         # 收敛性分析
├── examples/                   # 示例和教程
│   ├── __init__.py
│   ├── basic_usage.py         # 基础使用示例
│   ├── production_scheduling.py # 生产调度示例
│   └── custom_agents.py       # 自定义智能体示例
└── docs/                       # 文档
    ├── user_guide.md          # 用户指南
    ├── api_reference.md       # API参考
    └── research_notes.md      # 研究笔记
```

## 特性

### 🎯 智能体角色系统
- 灵活的角色定义机制
- 可配置的偏置参数
- 动态角色比例调整

### 🧠 偏置驱动决策
- 无需训练数据
- 透明的决策过程
- 自适应偏置调整

### 🔄 协同进化机制
- 种群间信息交流
- 知识共享和学习
- 协调式搜索策略

### 📊 丰富的分析工具
- 实时性能监控
- 角色贡献度分析
- 可视化仪表盘

## 快速开始

```python
from nsgablack.multi_agent import MultiAgentOptimizer
from nsgablack.multi_agent.core import AgentRole

# 创建优化器
optimizer = MultiAgentOptimizer(
    problem=your_problem,
    config={
        'total_population': 300,
        'max_generations': 100,
        'agent_config': {
            AgentRole.EXPLORER: {'ratio': 0.3, 'bias_profile': 'high_exploration'},
            AgentRole.EXPLOITER: {'ratio': 0.4, 'bias_profile': 'high_exploitation'},
            AgentRole.WAITER: {'ratio': 0.2, 'bias_profile': 'learning'},
            AgentRole.COORDINATOR: {'ratio': 0.1, 'bias_profile': 'adaptive'}
        }
    }
)

# 运行优化
results = optimizer.optimize()

# 分析结果
optimizer.visualize_results()
optimizer.analyze_performance()
```

## 研究方向

1. **偏置函数优化**：设计更有效的偏置函数
2. **自适应机制**：基于搜索状态的自适应策略
3. **新角色定义**：探索更多专业化角色
4. **大规模协作**：支持更多智能体的协同
5. **领域自适应**：针对特定问题的偏置设计

## 贡献

欢迎贡献新的偏置策略、智能体角色和分析工具！