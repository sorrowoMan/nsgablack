# Context 字段命名与新增规则

> context_field_schema_name: blackbase.context_field.v1  
> context_field_schema_version: 1.1.0

本规范用于约束 Context 字段治理，避免同义字段漂移、隐式写入和不可审计状态。

## 1. 目标

- 字段可读：看到 key 就能理解语义。
- 字段可追：能定位声明者、写入者、读取者。
- 字段可演进：新增字段不破坏既有组件。

## 2. 命名规则（必须）

- 使用小写蛇形，优先复用 `core/state/context_keys.py` 常量。
- 不允许同义词并存（例如 `obj` 与 `objectives` 同时存在）。
- 不允许随意缩写进入长期代码。
- 新 key 必须先声明常量，再进入组件契约。

## 3. 生命周期规则（必须）

字段需明确生命周期：

- `input`：问题输入或静态配置
- `runtime`：运行时状态
- `cache`：性能缓存，不保证可重放
- `custom`：临时/扩展字段（后续应收敛）

## 3.1 Context vs Snapshot 决策表（必须）

| 数据类型 | 放置位置 | 典型例子 | 说明 |
|---|---|---|---|
| 小字段、控制信号、契约依赖 | Context | `generation`、`phase_id`、`snapshot_key`、`population_ref` | 组件协作与可审计主通道 |
| 大对象、频繁读写数组 | SnapshotStore | `population`、`objectives`、`constraint_violations`、`pareto_*` | 不直接塞入 Context，避免膨胀和后端压力 |
| 需要跨组件共享的大对象 | Context 放引用 + Snapshot 放实体 | `population_ref -> snapshot_key` | Context 只传指针，读取走 `read_snapshot()` |
| 权威最佳候选 | 小对象可内联；大对象使用引用 | `best_x` / `best_candidate_ref` | 按正式序列化尺寸阈值决定，不能无条件写入 Context |
| 组件私有临时变量 | 组件内部 | 局部缓存、单次中间值 | 不写 Context，不写 Snapshot |

## 4. 组件契约规则（必须）

所有涉及字段读写的组件都要显式声明：

- `context_requires`
- `context_provides`
- `context_mutates`
- `context_cache`
- `context_notes`

`doctor --strict` 与 Run Inspector 会据此审计。

最低模板要求（建议直接复制）：

```python
class MyComponent:
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Explain what/why for context interactions.",)
```

其中 `context_requires/context_provides/context_mutates` 是核心三字段，必须明确写出（可以为空元组）。

## 5. 写入来源规则（必须）

- `last_writer` 必须来自可追踪证据（事件流/投影/构建写入记录）。
- `declared_by` 仅表示“声明写入者”，不能替代真实写入来源。

### 5.1 权威 incumbent 单写者规则

- `best_x`、`best_candidate_ref`、`best_objective` 属于 Solver incumbent 发布器。
- 普通 Context 构建可以把这些字段放入返回给调用方的局部视图，但不得把捕获到的旧值回写共享 `ContextStore`。
- Context 发布健康度必须由 `incumbent_revision`、`incumbent_context_projection_revision`、`incumbent_context_projection_current` 和 `incumbent_context_projection_error` 共同表达。
- 直接运行结果、标准 `SolverResult`、checkpoint 和 module report 应复用同一份发布审计，不得各自推断。
- checkpoint 恢复后的旧发布状态只作为历史证据；当前进程必须针对当前 `ContextStore` 重新发布并重新计算健康度。
- Adapter 的代内局部最佳只能使用 `adapter_best_x`、`adapter_best_objectives`、`adapter_best_score`，不得覆盖 Solver 的权威 incumbent 字段。
- `generation` 与 `evaluation_count` 同样属于 Solver 运行控制面，Adapter runtime projection 只能读取，不能重新发布。
- `get_runtime_context_projection(self, solver)` 是唯一正式签名；调用边界不得通过捕获 `TypeError` 猜测旧签名。
- Adapter runtime projection 的每个字段和整体 payload 都受独立遥测预算约束。超限字段从轻量 Context 省略，并在 `runtime_projection_audit` 中记录字段名、原因和估算尺寸；审计不复制被省略的值。
- 普通 Adapter 投影的外层 `runtime_projection_audit.status` 使用 `ok / unavailable / error / invalid_result` 四态；组合投影额外允许 `degraded`，因此完整外层状态机为五态。仅缺少 Adapter/投影器可作为健康的 `unavailable`；`degraded / error / invalid_result` 均不得声明 `current=True`。
- 组合投影信封自身只使用 `ok / degraded / error`，其状态必须与成功、降级、失败、非法、不可用组件计数一致，所有分类计数之和必须等于组件总数。
- 嵌套组合的降级或失败通过固定 64 位 `cause_digest` 传播子信封 `audit_digest`；父级只保留定长因果摘要，不递归复制子级审计样本。
- 所有复合 Adapter 必须通过 blackbase `aggregate_runtime_projections()` 聚合显式声明的当前活动子节点；blackbase 负责机制，nsgablack 负责 Composite/Async/Role/Serial/MultiStrategy 的拓扑选择，不允许组合器只返回自身字段而吞掉子级健康。
- Event Case 模式尚未选出活动 Case 时，运行时投影的子节点集合为空；投影读取不得产生选择 Case 的生命周期副作用。
- 实际字段写入者通过 `RuntimeContextProjection.field_sources` 随嵌套信封递归传播。外层 `runtime_projection_audit` 仅发布有界 `field_source_samples`、完整 `field_source_count` 和独立 `field_source_digest`；健康 `audit_digest` 不得因 writer 变化而改变。
- 审计自身也受硬预算约束：组件问题使用固定字段协议，只保留有限且逐字段有界的样本，同时发布完整计数、原因计数、截断标志和稳定摘要；组件审计与完整外层审计都不得超过正式字节预算。fresh run 必须重置审计和去重 signature，审计隔离失败必须原子发布最小 `error` 信封，不能保留上一轮证据。
- Runtime collector 不会为任意大对象自动伪造 Snapshot/Artifact ref。需要跨边界保留的字段必须由拥有其 codec 与生命周期的 Adapter/Plugin 主动发布真实 `*_ref`。

## 6. 新字段接入流程

1. 在 `context_keys.py` 增加 `KEY_XXX`。
2. 在相关组件补齐 `context_*` 契约。
3. 在 Run Inspector 校验字段可见性与归因。
4. 运行 `project doctor --strict` 与测试。
5. 更新文档/变更记录。

## 7. CI 门禁

CI 需至少包含：

- `tests/test_context_key_alignment.py`
- `tests/test_schema_version.py`
- `python tools/context_field_guard.py --strict`

---

# Context Field Naming and Evolution Rules

This document defines hard governance rules for Context key lifecycle and compatibility.

## Required controls

- Canonical keys must come from `context_keys.py`.
- Every component that touches context must declare explicit contracts.
- Field provenance must be evidence-based (declared vs actual writer separated).
- CI must reject non-canonical key drift.

## Versioning

- `context_field_schema_name = blackbase.context_field.v1`
- `context_field_schema_version = 1.1.0`

When semantics break compatibility, bump schema version and provide migration guidance.
