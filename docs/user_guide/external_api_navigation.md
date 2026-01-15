# 对外展示版入口清单与统一 API 导航

本页给“对外展示/对外发布”用，目标是**入口少、路径统一、场景清晰**。

---

## 1) 精简入口清单（建议对外只展示这些）

| 入口（推荐导入） | 用途 | 什么时候用 |
| --- | --- | --- |
| `BlackBoxProblem` | 定义问题 | 任何优化任务的起点 |
| `BlackBoxSolverNSGAII` | 通用多目标求解器 | 常规多目标优化 |
| `BiasModule` | 快速加奖励/惩罚 | 业务规则或启发式快速落地 |
| `ParallelEvaluator` | 并行评估 | 评估成本高、CPU可并行 |
| `SurrogateAssistedNSGAII` | 代理辅助NSGA-II | 黑箱评估昂贵时 |
| `SurrogateUnifiedNSGAII` | 代理统一接口 | 需要“预筛选/评分偏置/替代评估”精细控制时 |
| `MultiAgentBlackBoxSolver` | 多智能体优化 | 需要角色分工、资源分配时 |
| `MonteCarloOptimizer` | MC鲁棒优化 | 目标/约束含随机性时 |

**对外展示推荐导入方式**（统一从根包）：

```
from nsgablack import (
    BlackBoxProblem,
    BlackBoxSolverNSGAII,
    BiasModule,
    ParallelEvaluator,
    SurrogateAssistedNSGAII,
    SurrogateUnifiedNSGAII,
    MonteCarloOptimizer,
)
from nsgablack.solvers import MultiAgentBlackBoxSolver
```

---

## 2) 统一 API 导航（按场景选入口）

### 常规多目标
- 入口：`BlackBoxSolverNSGAII`
- 配合：自定义 `BlackBoxProblem.evaluate()` / `evaluate_constraints()`

### 有约束 / 业务规则
- 入口：`BiasModule`
- 方式：在 `evaluate_constraints()` 写硬约束，在 `BiasModule` 写软约束/偏好

### 黑箱评估很贵
- 入口：`SurrogateAssistedNSGAII`
- 高级控制：`SurrogateUnifiedNSGAII`

### 需要“分阶段/不确定性预算”的代理策略
- 入口：`SurrogateUnifiedNSGAII` + `bias/surrogate`
- 偏置：`PhaseScheduleBias`、`UncertaintyBudgetBias`

### 多智能体 / 角色协作
- 入口：`MultiAgentBlackBoxSolver`
- 配合：角色配置 + 偏置系统

### 随机不确定性优化
- 入口：`MonteCarloOptimizer` / `SurrogateMonteCarloOptimizer`

### 并行评估
- 入口：`ParallelEvaluator`

---

## 3) 统一导入规范（对外稳定路径）

**第一层：根包入口（对外主入口）**

```
from nsgablack import BlackBoxSolverNSGAII, BiasModule, SurrogateAssistedNSGAII
```

**第二层：算法与高级模块**

```
from nsgablack.solvers import MultiAgentBlackBoxSolver
from nsgablack.surrogate import SurrogateManager, SurrogateTrainer
from nsgablack.bias.surrogate import PhaseScheduleBias
```

**建议**：避免直接依赖 `core/` 或 `solvers/nsga2.py` 的内部路径，优先走统一入口。

---

## 4) 对外展示建议（选 3 条主线即可）

- 经典 NSGA-II + 偏置（核心创新）
- 代理辅助 + 预算控制（昂贵黑箱）
- 多智能体角色协作（资源分配与分工）
