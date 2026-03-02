# Redis Context + Snapshot Workflow (CN/EN)

This guide explains how to use Redis for both `ContextStore` and `SnapshotStore`, and why their workflows are different.

## 中文

### 1) 核心结论

- `ContextStore` 负责小字段契约与控制信号。
- `SnapshotStore` 负责大对象载体（`population/objectives/violations/pareto/history` 等）。
- 即使两者都用 Redis，也不是同一条业务流程。

### 2) 两条流程的职责边界

- Context 流程：
  - 直接读写小值（字段/状态/信号）。
  - 重点是契约一致性（谁提供、谁消费、谁修改）。
- Snapshot 流程：
  - 先写大对象得到 `snapshot_key`。
  - 再把 `snapshot_key`/`population_ref` 放入 Context。
  - 消费方通过 `solver.read_snapshot()` 或 `resolve_population_snapshot()` 解析大对象。

### 3) Redis 下的典型键流转

写入侧（每代）：

1. Adapter/Solver 把大对象写入 `SnapshotStore`（Redis）并得到 `snapshot_key`。
2. Solver 在 Context 中写入 `snapshot_key`（以及必要的小字段摘要）。
3. Plugin/组件只通过引用读取大对象，不把大对象直接塞回 Context。

读取侧：

1. 先从 Context 取 `snapshot_key`/`population_ref`。
2. 再通过 `SnapshotStore` 读取真实数据。
3. 若 key 存在但数据不存在，按“后端不可达/TTL过期/写入失败”处理。

### 4) 推荐配置与键命名

建议显式区分前缀：

- `context_store_key_prefix = "nsgablack:ctx:<project>"`
- `snapshot_store_key_prefix = "nsgablack:snap:<project>"`

建议区分 TTL：

- Context TTL 可以更短（控制面）。
- Snapshot TTL 应覆盖复盘与插件读取窗口（数据面）。

### 5) 诊断与排障要点

- Context 缺字段：
  - 看契约声明与 `on_context_build()` 写入路径。
- 有 `snapshot_key` 但读不到数据：
  - 看 Redis 连通性、TTL、后端写入异常。
- 数据错位：
  - 检查是否绕过 `read_snapshot()/resolve_population_snapshot()` 直接读旧镜像字段。

### 6) 最小配置示例

```python
solver = EvolutionSolver(
    problem,
    context_store_backend="redis",
    context_store_redis_url="redis://127.0.0.1:6379/0",
    context_store_key_prefix="nsgablack:ctx:demo",
    context_store_ttl_seconds=3600,
    snapshot_store_backend="redis",
    snapshot_store_redis_url="redis://127.0.0.1:6379/0",
    snapshot_store_key_prefix="nsgablack:snap:demo",
    snapshot_store_ttl_seconds=21600,
)
```

---

## English

### 1) Key takeaway

- `ContextStore` carries small contract fields and control signals.
- `SnapshotStore` carries large optimization artifacts.
- Using Redis for both does not mean one identical workflow.

### 2) Responsibility split

- Context path:
  - Read/write small values directly.
  - Governed by explicit contracts (`requires/provides/mutates`).
- Snapshot path:
  - Persist large payload first and get `snapshot_key`.
  - Publish only references (`snapshot_key`, `population_ref`) into context.
  - Resolve payload via `solver.read_snapshot()` or `resolve_population_snapshot()`.

### 3) Typical key flow in Redis

Write side:

1. Adapter/Solver writes large payload to `SnapshotStore` and obtains `snapshot_key`.
2. Solver writes that key (plus small summaries) into context.
3. Consumers read payload by reference, not by embedding large objects into context.

Read side:

1. Read `snapshot_key` from context.
2. Resolve actual payload from `SnapshotStore`.
3. If key exists but payload is missing, treat as backend/TTL/write-path issue.

### 4) Recommended prefix and TTL policy

- Keep prefixes explicit and separate:
  - `nsgablack:ctx:<project>`
  - `nsgablack:snap:<project>`
- Keep TTL policies separate:
  - Context TTL for control-plane freshness.
  - Snapshot TTL for replay/inspection window.

### 5) Troubleshooting checklist

- Missing context fields:
  - Verify contract declaration and context write path.
- `snapshot_key` exists but payload read fails:
  - Verify Redis connectivity, TTL, and snapshot write success.
- Stale/misaligned payload:
  - Ensure consumers use snapshot resolver APIs instead of direct mirror fields.

