# Solver Helpers 职责说明

本目录用于承载 `SolverBase` 的内部实现细节，目标是让 `core/blank_solver.py` 保持为“控制面编排层”。

## 设计原则

- `SolverBase` 对外 API 不变，helper 只做内部实现下沉。
- 每个 helper 模块只负责一类职责，避免跨模块重复逻辑。
- helper 不直接承载业务流程编排；流程编排仍在 `SolverBase`。

## 模块职责

- `store_helpers.py`
  - 负责 `ContextStore`/`SnapshotStore` 的创建和失败降级策略（降级到 memory）。
  - 统一构建参数，避免构建逻辑散落在 `SolverBase`。

- `snapshot_helpers.py`
  - 负责快照相关纯数据处理：
  - 快照元数据（meta）构建
  - 快照 payload 构建
  - context 中 snapshot refs 构建
  - context 大字段剥离

- `control_plane_helpers.py`
  - 负责 solver 控制面状态字段的读写与推导：
  - `generation` / `evaluation_count`
  - `best` / `pareto` 快照字段
  - runtime context projection 聚合

- `context_helpers.py`
  - 负责 context 构建和刷新流程：
  - 读取 context store 快照并合并运行态
  - 触发 `on_context_build`
  - 写回 context store
  - 严格模式下 snapshot 可读性校验

- `bias_helpers.py`
  - 负责 bias 模块接线和 bias 计算应用：
  - 注入 context/snapshot store
  - 单目标/多目标 bias 结果标准化

- `evaluation_helpers.py`
  - 负责评估流程实现：
  - `evaluate_individual`：插件短路、problem 评估、约束评估、bias 应用、计数递增
  - `evaluate_population`：批量输入校验、前后快照持久化、逐个个体评估、结果整形

- `run_helpers.py`
  - 负责 solver 运行循环：
  - init/resume 状态恢复
  - generation 生命周期 hook 调度
  - 运行结果结构化输出

- `candidate_helpers.py`
  - 负责候选解随机采样（dict/array bounds 两种路径）。

## 变更约束

- 新增控制面逻辑：优先放 `control_plane_helpers.py`。
- 新增 context 读写流程：优先放 `context_helpers.py`。
- 新增评估流程逻辑：优先放 `evaluation_helpers.py`。
- 不要在 helper 之间形成循环依赖。
