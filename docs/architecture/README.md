# docs/architecture

用途：架构设计与结构说明。
边界：偏设计文档，不包含教程。
示例：模块结构与管线设计文档。

Purpose: architecture notes and design docs.
Boundary: design, not tutorials.
Example: module structure docs.

## 当前架构（v2）

NSGABlack 当前是“控制面 + 数据面”分层架构：

- 控制面：`SolverRuntime` 统一生命周期与调度，`ContextStore` 存放小字段与运行信号
- 数据面：`SnapshotStore` 专职存放大对象（population/objectives/violations/pareto/history/trace）
- 接口层：Adapter/Plugin/Bias/Pipeline 通过 Context 交互，小字段走 Context，大对象走 Snapshot
- 读写规则：统一使用 `solver.read_snapshot()` / `Plugin.resolve_population_snapshot()` / `Plugin.commit_population_snapshot()`

这层分离让 Context 可审计/可重放，而大对象可高频读写并支持落盘/Redis。

## Solver 命名与边界（Naming & Boundary）

- `SolverBase`：纯底座，不绑定算法流程。
- `ComposableSolver`：Adapter 驱动的通用 step 底座。
- `EvolutionSolver`：进化种群过程求解器的推荐名称（行为兼容 `EvolutionSolver`）。
- `EvolutionSolver`：历史兼容入口，保留但不作为新能力首选落点。
