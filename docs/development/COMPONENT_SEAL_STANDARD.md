# 组件统一封口标准（Contract / Guard / Test / Governance）

这份文档用于把「组件可组合」落到可执行标准，避免只停留在理念层。

## 1. 契约卡（每个组件都要有）

每个组件（Adapter / Plugin / Bias / Representation 组件）至少要明确：

- 角色职责：它负责什么，不负责什么。
- I/O 契约：
  - `propose/update`（Adapter）
  - 对应 hook（Plugin）
  - 输入上下文依赖、输出/改写字段
- Context 契约字段：
  - `context_requires`
  - `context_provides`
  - `context_mutates`
  - `context_cache`
- 语义边界：
  - 可证明模式（严格前提）
  - 工程启发模式（为了可组合性允许的放宽）
- 副作用与停止条件：
  - 是否修改内部状态
  - 是否触发求解停止
  - 是否依赖外部系统（队列/数据库/文件）

## 2. Checkpoint 恢复等级（L0 / L1 / L2）

对所有实现了 `get_state()/set_state()` 的组件，必须声明：

- `state_recovery_level = "L0" | "L1" | "L2"`
- `state_recovery_notes = "..."`

等级定义：

- `L0`：摘要态恢复  
  仅恢复统计/摘要，不保证搜索前沿、队列或分布状态可继续。
- `L1`：业务态恢复  
  恢复核心内部状态，可继续运行，但不承诺严格逐步重放一致。
- `L2`：确定性续跑恢复  
  恢复足够完整的状态（配合 solver RNG / snapshot），目标是稳定续跑。

## 3. Doctor 护栏（静态规则）

Doctor 负责把架构边界变成自动化检查：

- `solver-mirror-write`：禁止业务组件直写 solver 镜像字段。
- `runtime-bypass-write`：禁止绕过控制面直接写 runtime 状态字段。
- `runtime-private-call`：禁止调用 `solver.runtime._*` 私有方法。
- `plugin-direct-solver-state-access`：插件禁止直接读写 solver 的 population/objectives/violations。
- `state-roundtrip-asymmetric`：`get_state()/set_state()` 必须成对。
- `state-recovery-level-missing` / `state-recovery-level-invalid`：状态恢复等级必须显式且合法。

## 4. 测试矩阵（最少四类）

每类核心组件都应覆盖以下维度：

- `smoke`：基础运行可达（至少能跑通一个最小 step/run）。
- `contract`：`propose/update` 或 hook 行为符合契约。
- `checkpoint roundtrip`：`get_state -> set_state` 可恢复到声明等级。
- `strict/fault`：严格模式与异常路径（错误输入、回退路径）行为可验证。

## 5. 治理规则

### 5.1 checkpoint 恢复等级治理

- 新增或改动状态接口时，必须同步更新：
  - 组件类上的 `state_recovery_level/state_recovery_notes`
  - 对应测试（至少 roundtrip + fault）
  - 契约卡文档

### 5.2 schema_tool 噪声治理

- `tools/schema_tool.py` 默认扫描项目根，但**默认排除 `runs/` 历史产物**。
- 需要扫描历史产物时显式开启：`--include-runs`，或直接传入 `runs` 路径。

这样做的目标是：日常 CI 保持低噪声；回溯历史时可显式切换到“历史审计模式”。
