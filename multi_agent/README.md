# NSGABlack多智能体优化系统

## 概述

NSGABlack多智能体优化系统是一个基于偏置驱动的协同进化框架，通过多个专业化智能体的协作来解决复杂的黑盒优化问题。

## 核心理念

### 定位说明

本系统定位为**多角色协同优化底座**：信用分配、显式通信协议、去中心化策略学习等能力都可以通过偏置与角色策略扩展实现，按需启用，而非强制内置。

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
├── core/                       # 核心数据结构
│   ├── __init__.py
│   ├── role.py                # 角色系统
│   └── population.py          # 种群数据结构
├── components/                 # 组件化能力（可组合 mixin）
│   ├── __init__.py
│   ├── advisor.py             # 建议生成与注入
│   ├── archive.py             # 档案库管理
│   ├── communication.py       # 通信与协作
│   ├── evolution.py           # 进化与选择
│   ├── region.py              # 区域划分
│   ├── role_logic.py          # 角色行为与切换
│   ├── scoring.py             # 评分与比例更新
│   └── utils.py               # 通用工具
├── bias/                       # 偏置驱动系统
│   ├── __init__.py
│   ├── profiles.py            # 偏置配置文件
│   ├── adapters.py            # 偏置适配器
│   ├── dynamics.py            # 动态偏置调整
│   └── learning.py            # 偏置学习机制
├── strategies/                 # 搜索策略与配置
│   ├── __init__.py
│   ├── role_bias_combinations.py # 角色偏置组合
│   ├── search_strategies.py      # 搜索策略
│   └── advisory.py              # 建议策略
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
from solvers.multi_agent import MultiAgentBlackBoxSolver
from multi_agent.core import AgentRole

# 创建优化器
solver = MultiAgentBlackBoxSolver(
    problem=your_problem,
    config={
        'total_population': 300,
        'max_generations': 100,
        'agent_ratios': {
            AgentRole.EXPLORER: 0.3,
            AgentRole.EXPLOITER: 0.4,
            AgentRole.WAITER: 0.2,
            AgentRole.COORDINATOR: 0.1,
        }
    }
)

# 运行优化
pareto_front = solver.run()
```

## 新增角色（Enum 方式）

当前角色体系基于 `AgentRole(Enum)`，新增角色需要改源码并按以下步骤补齐：

1. `multi_agent/core/role.py`：新增枚举值 + 默认特性 + 角色描述  
2. `solvers/multi_agent.py`：补充 `_get_bias_profile`（必要时加 `_apply_role_bias`）  
3. `multi_agent/strategies/role_bias_combinations.py`：如使用角色偏置组合，补充配置  
4. `multi_agent/bias/profiles.py`：如使用 `BiasLibrary`，注册默认 profile  
5. `multi_agent/components/archive.py`：需要差异化档案采样时补充策略  
6. 运行 `examples/validation_smoke_suite.py` 做回归验证  

最小示例（新增 `ANALYST` 角色）：

```python
# multi_agent/core/role.py
class AgentRole(Enum):
    ANALYST = "analyst"
```

```python
# solvers/multi_agent.py
elif role == AgentRole.ANALYST:
    return {
        'diversity_weight': 1.0,
        'exploration_rate': 0.4,
        'mutation_rate': 0.1,
        'crossover_rate': 0.7,
        'selection_pressure': 0.6,
        'constraint_tolerance': 0.3
    }
```

```python
config = {
    "agent_ratios": {
        AgentRole.EXPLORER: 0.3,
        AgentRole.EXPLOITER: 0.4,
        AgentRole.ANALYST: 0.1,
        AgentRole.WAITER: 0.1,
        AgentRole.COORDINATOR: 0.1,
    }
}
```

## 研究方向

1. **偏置函数优化**：设计更有效的偏置函数
2. **自适应机制**：基于搜索状态的自适应策略
3. **新角色定义**：探索更多专业化角色
4. **大规模协作**：支持更多智能体的协同
5. **领域自适应**：针对特定问题的偏置设计

## 贡献

欢迎贡献新的偏置策略、智能体角色和分析工具！
