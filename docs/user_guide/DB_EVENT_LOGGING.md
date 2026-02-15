# DB 事件日志接入（MySQL）

本文定义 NSGABlack 的数据库落地分层：

- 资产层（当前可用）：运行记录、报告路径、配置快照。
- 事件层（建议建设）：context 事件流持久化与重放。

目标：让 Run Inspector、实验复现、组件归因使用同一套数据面。

## 1. 分层说明

### 1.1 资产层（现有能力）

框架已有 `MySQLRunLoggerPlugin`（`plugins/storage/mysql_run_logger.py`），用于把运行结果写入 MySQL。

适用：
- run 级别检索（run_id、status、best_objective）
- 报告路径管理（modules/bias report）
- 快速对比实验结果

### 1.2 事件层（建议能力）

新增标准三表（`runs / snapshots / context_events`）：

- `runs`：一次运行的元数据与配置摘要
- `snapshots`：按 step 保存的 context 快照
- `context_events`：按 event 保存的上下文增量

这样可以支持：
- 字段级溯源（谁写了哪个 key）
- 运行时回放（基于 snapshot + events）
- 结构审计与跨实验追踪

## 2. 最小数据模型

### 2.1 runs

建议字段：
- `run_id`（唯一）
- `entry`（`path.py:build_solver`）
- `status`、`seed`、`started_at`、`finished_at`
- `config_json`（运行配置）
- `tags_json`（可选标签）

### 2.2 snapshots

建议字段：
- `run_id`、`step`（联合唯一）
- `schema_version`
- `context_json`
- `context_hash`
- `created_at`

### 2.3 context_events

建议字段：
- `run_id`、`event_id`（联合唯一）
- `step`、`generation`
- `kind`、`ctx_key`、`source`
- `value_json`
- `event_time`

## 3. SQL 模板

可直接执行：

- `docs/attachments/sql/mysql_event_logging_schema.sql`

该脚本包含：
- 三张表 DDL
- 关键索引（`run_id/step/key/source`）

## 4. 接入建议（渐进式）

阶段 A（低风险）：
- 保持现有 `MySQLRunLoggerPlugin`
- 增加 `runs` 表写入（可与现有表并存）

阶段 B（可观测增强）：
- 在 `on_generation_end` 写 `snapshots`
- 从 `context_events`/`async_event_hub` 写 `context_events`

阶段 C（回放闭环）：
- 提供 DB 回放读取器（按 run_id + step）
- Run Inspector 增加 DB 数据源选项

## 5. 性能与边界

- 事件写入建议批量提交（按 step 或按 N 条 flush）
- 大字段（`context_json`）建议压缩或限制频率
- `cache` 字段可写入但默认不参与“可重放”判定
- `schema_version` 必须随结构变更升级

## 6. 与现有插件关系

- `MySQLRunLoggerPlugin`：继续负责 run 级汇总落库
- 事件层写入器：建议新增独立插件（如 `ContextEventDBLoggerPlugin`），避免污染现有实现

推荐做法：
- 先稳定 schema，再做插件实现与 UI 消费
- 保持兼容：未启用 DB 事件层时，现有本地 JSON/报告流程不受影响

