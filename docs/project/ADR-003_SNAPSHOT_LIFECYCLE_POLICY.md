# ADR-003: Snapshot 生命周期治理策略（TTL / GC / 归档）

状态：Proposed  
日期：2026-03-01  
范围：SnapshotStore 数据生命周期

## 1. 背景

Snapshot 承载大对象，是运行正确性与复盘能力的关键资产。  
如果没有生命周期治理，会出现两类问题：

- 不治理：存储无限增长，成本失控。
- 乱治理：误删关键快照，复盘失效。

因此必须先定义策略，再做实现。

## 2. 决策

建立统一生命周期状态机与策略接口，默认保守策略，先可观察再自动清理。

### 2.1 生命周期状态

- `active`：当前可读写。
- `pinned`：保护态，不允许自动删除。
- `expired`：过期候选，待回收。
- `archived`：已转冷存储。
- `deleted`：已删除，仅留元数据记录。

### 2.2 策略分层

- 保留策略：`keep_last_n`, `ttl_seconds`, `pin_tags`
- 清理策略：`dry_run`, `mark_sweep`, `batch_delete`
- 归档策略：`archive_before_delete`, `archive_ttl`, `archive_target`

### 2.3 默认安全原则

1. 默认 `dry_run=true`（先报告，后执行）。
2. `pinned` 永不自动删除。
3. 删除前必须有 `manifest` 记录与 hash。
4. 删除动作必须写审计日志。

## 3. 最小策略配置（建议）

```toml
[snapshot_lifecycle]
enabled = true
ttl_seconds = 604800
keep_last_n = 20
dry_run = true
archive_before_delete = false
```

## 4. GC 执行模型（v1）

采用标记-清扫（Mark-Sweep）：

1. 标记阶段：
   - 仍被 run/manifest 引用的 snapshot 标记为 `active/pinned`。
   - 过期且未引用的标记为 `expired`。
2. 清扫阶段：
   - 按批次处理 `expired`。
   - 若开启归档，先归档再删除。
3. 审计阶段：
   - 输出本次 GC 报告（命中数/跳过数/删除数/错误数）。

## 5. 与后端无关的统一接口

无论 memory/redis/file 后端，都应遵守统一语义：

- `pin(snapshot_key)`
- `unpin(snapshot_key)`
- `mark_expired(...)`
- `gc(dry_run=...)`
- `archive(snapshot_key, target=...)`

后端仅实现存取细节，不改变生命周期契约。

## 6. 非目标（明确不做）

- 不在 v1 做跨集群分布式 GC 一致性协议。
- 不在 v1 做复杂冷热分层自动调度。
- 不在 v1 绑定特定云厂商归档服务。

## 7. 风险与缓解

- 风险：TTL 过短导致“key 在但数据没了”。  
  缓解：默认长 TTL + Doctor 增加策略检查。
- 风险：GC 与读取并发冲突。  
  缓解：分代/批次执行，删除前做二次可达性检查。
- 风险：归档失败导致数据丢失。  
  缓解：`archive_before_delete` 模式下，归档成功才允许删除。

## 8. 推进节奏（建议）

1. 先做观测模式（只报告，不删）。
2. 再做手动执行 GC。
3. 最后才考虑定时自动 GC。

