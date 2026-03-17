# FRAMEWORK_OVERVIEW (Redirect)

这份“框架总览”原本是一篇很长的理念/架构说明，但内容与以下权威入口存在大量重叠，且长期维护会不可避免地产生漂移（同一个概念在不同文档里被解释多次）。

因此本页收敛为指向，避免重复维护：

## 当前架构要点（v2）

- Context 只放小字段与快照引用（`snapshot_key` / `population_ref` 等）
- 大对象统一走 `SnapshotStore`（内存/Redis/文件后端可切）
- 统一入口：`solver.read_snapshot()` / `Plugin.get_population_snapshot()` / `Plugin.commit_population_snapshot()`
- 详细说明见 `docs/architecture/README.md`

## 推荐阅读顺序

1) 手把手落地一个真实问题（入口主线）

- `WORKFLOW_END_TO_END.md`

2) 解耦对象导读（你会越用越依赖）

- `docs/guides/DECOUPLING_PROBLEM.md`
- `docs/guides/DECOUPLING_REPRESENTATION.md`
- `docs/guides/DECOUPLING_BIAS.md`
- `docs/guides/DECOUPLING_CAPABILITIES.md`

   3.核心边界（哪些算核心承诺，哪些可变）

- `docs/CORE_STABILITY.md`
