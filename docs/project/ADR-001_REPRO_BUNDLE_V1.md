# ADR-001: Repro Bundle v1（环境锁定 + 配置锁定 + 重跑包）

状态：Proposed  
日期：2026-03-01  
范围：研究/实验框架层（非业务输出口径）

## 1. 背景

框架处于快速迭代期，最容易失真的不是算法本身，而是“同一实验无法稳定重跑”。  
当前缺少统一的可复现封装，导致以下风险：

- 同名 run 语义不同（配置漂移）。
- 依赖版本变化后结果不一致。
- 数据输入变更无法追溯。
- 团队协作时只能靠口头说明“当时怎么跑的”。

## 2. 决策

引入 `Repro Bundle v1`，作为一次运行的最小重跑单元。  
框架只规范“复现元数据”，不规范业务结果列格式。

### 2.1 Bundle 目录结构

推荐路径：`runs/<run_id>/repro_bundle/`

- `manifest.json`：产物索引与血缘入口（run 级）。
- `solver_config.json`：求解器装配配置（canonical JSON）。
- `env.lock.json`：环境锁定信息。
- `input_fingerprint.json`：输入数据指纹。
- `replay.sh` / `replay.ps1`：标准重跑命令。
- `README.md`：重跑说明与已知限制。

### 2.2 强制采集字段

- `run_id`
- `started_at` / `finished_at`
- `framework_version`
- `git_commit`
- `git_dirty`
- `entrypoint`（如 `build_solver.py:build_solver`）
- `seed`（全局与关键子模块）
- `solver_config_sha256`
- `env_lock_sha256`
- `input_fingerprint_sha256`

### 2.3 环境锁定（env.lock.json）

最低要求：

- Python 版本与实现信息。
- OS/平台信息。
- 已安装依赖清单（`pip freeze` 快照）。
- 关键可选依赖状态（如 `redis`, `ray`, `numba`）。

### 2.4 配置锁定（solver_config.json）

要求：

- 使用 canonical JSON（稳定排序与稳定序列化）。
- 仅包含“可影响结果”的配置项。
- 输出 `sha256` 并写回 `manifest.json`。

### 2.5 输入锁定（input_fingerprint.json）

建议字段：

- 输入文件 URI/路径
- 文件大小与修改时间
- 内容哈希（默认 sha256）
- 外部数据版本号（若存在）

## 3. 非目标（明确不做）

- 不强制规定团队业务结果的列格式（CSV/Parquet 由团队决定）。
- 不保证跨硬件绝对 bit-level 一致。
- 不把业务分析逻辑纳入重跑包规范。

## 4. 最小验收标准

满足以下条件即可视为“可复现合格”：

1. 任意同事拿到 bundle 可执行重跑命令。
2. 能定位并验证运行参数、环境、输入是否一致。
3. 可通过 `manifest + hashes` 识别漂移来源。

## 5. 实施顺序（建议）

1. 先生成只读 bundle（不做强校验）。
2. 再加 `--strict-repro` 校验模式（缺关键字段直接失败）。
3. 最后把 bundle 写入 CI 的回归工件。

## 6. 风险与缓解

- 风险：采集过重影响运行性能。  
  缓解：哈希策略可配置（元信息哈希/全量哈希）。
- 风险：锁定字段太多导致维护成本高。  
  缓解：先做最小字段集，按失败案例扩展。

