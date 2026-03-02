# ADR-002: Artifact Manifest + Lineage v1（run 到产物一致登记）

状态：Proposed  
日期：2026-03-01  
范围：框架运行产物治理（不包含业务分析模型）

## 1. 背景

随着插件、快照、报告增多，单靠目录结构无法稳定回答：

- 这次 run 到底产出了哪些文件？
- 哪个产物由哪个组件生成？
- 新产物是基于哪些上游产物派生出来的？

需要一个统一入口，避免“文件有了，但关系丢了”。

## 2. 决策

引入 `manifest.json` 作为 run 级单一事实来源（Single Source of Truth）。  
Manifest 只做登记与关系追踪，不入侵业务内容。

### 2.1 Manifest 最小结构

```json
{
  "run_id": "20260301_123000",
  "schema_name": "artifact_manifest",
  "schema_version": 1,
  "created_at": "2026-03-01T12:30:00Z",
  "entrypoint": "build_solver.py:build_solver",
  "artifacts": [],
  "lineage_edges": []
}
```

### 2.2 Artifact 记录字段（最小）

- `artifact_id`（唯一）
- `type`（`snapshot/report/trace/decision/sequence/benchmark/...`）
- `uri`（本地路径或对象存储 URI）
- `hash`（sha256）
- `size_bytes`
- `schema_name`
- `schema_version`
- `produced_by`（组件名，如 `plugin.sequence_graph`）
- `created_at`
- `tags`（可选）

### 2.3 血缘边（Lineage Edge）

每条边表达“由谁基于谁生成”：

- `from_artifact_id`
- `to_artifact_id`
- `relation`（`derived_from/aggregated_from/replayed_from`）
- `created_by`
- `created_at`

### 2.4 最小查询能力目标

v1 必须支持：

1. `run_id -> 全部产物`
2. `artifact_id -> 上游/下游`
3. `component -> 其生成产物`

## 3. 非目标（明确不做）

- 不在 v1 做图数据库落地。
- 不在 v1 强制跨 run 全局血缘合并。
- 不在 v1 绑定某种对象存储厂商。

## 4. 与现有机制关系

- `result["artifacts"]`：仍可存在，但最终应同步写入 manifest。
- `Context`：只留轻量引用键，不承担产物索引职责。
- `SnapshotStore`：仍负责大对象读写，manifest 负责登记其产物元数据。

## 5. 实施顺序（建议）

1. v1 先登记核心产物：snapshot/report/decision/sequence/benchmark。
2. 插件逐步接入 `manifest append`。
3. Run Inspector 增加 manifest 路径展示与完整性检查。

## 6. 风险与缓解

- 风险：插件各自写 manifest，格式漂移。  
  缓解：统一 `append_artifact()` API + schema 校验。
- 风险：产物已写成功但 manifest 未更新。  
  缓解：两阶段提交语义（先临时记录，结束时原子落盘）。

