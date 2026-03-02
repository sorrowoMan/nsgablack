# NSGABlack Overview

一句话：`NSGABlack` 不是“再来一个算法库”，而是把优化系统拆成可组合、可诊断、可复现的工程框架。

## 你会遇到的问题
- 结果看起来不错，但很难复现和解释“为什么有效”。
- 新策略接入后牵一发而动全身，对比口径不一致。
- 约束、偏好、算法逻辑混在一起，维护成本越来越高。

## 核心结构
- `Problem`：目标与约束定义。
- `SolverBase`：求解器控制面（生命周期、stop/step、plugin hook、context/snapshot）。
- `ComposableSolver`：通用执行器（由 `Adapter.propose/update` 驱动）。
- `EvolutionSolver`：官方进化求解器预置（基于 adapter 体系）。
- `RepresentationPipeline`：初始化/变异/修复（硬约束优先放这里）。
- `BiasModule`：软偏好与策略偏置。
- `Plugin`：观测、回放、导出、并行、checkpoint 等运行能力。
- `Catalog + Suite`：组件可发现与权威装配。

## Context + Snapshot 分层
- `ContextStore`：小字段、契约字段、组件协作字段。
- `SnapshotStore`：大对象载体（population/objectives/violations/pareto/history/trace）。
- `Context` 只放引用（`*_ref` / `snapshot_key`），大对象通过快照读写。

## 快速入口
```powershell
python -m pip install -e .
python examples/end_to_end_workflow_demo.py
```

建议阅读顺序：
- `START_HERE.md`
- `WORKFLOW_END_TO_END.md`
- `docs/FEATURES_OVERVIEW.md`

