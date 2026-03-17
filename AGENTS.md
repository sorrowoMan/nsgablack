# AGENTS.md

## 0) 这份文档怎么用（给协作 Agent）

这是一份“面向改动执行”的协作说明，不是概念介绍。
阅读顺序建议：

1. 先看 `1/2/4`（定位 + 架构 + 生命周期）
2. 再看 `5/6/7`（数据协议 + API 契约 + catalog 口径）
3. 最后按 `9/12` 跑命令与提交检查

---

## 1) 项目定位（第一原则）

`nsgablack` 是**多目标优化工程框架**，不是单一算法库。
核心是四层正交架构：

- `Solver`：控制平面（生命周期、评估入口、状态管理）
- `Adapter`：算法策略平面（`propose/update`）
- `Representation`：表示平面（init/mutate/repair/encode/decode）
- `Plugin`：能力平面（checkpoint/trace/eval/backend/log）

协作规则：

- 不把算法策略硬塞进 `SolverBase`
- 不把运行时能力（日志、恢复、审计）硬塞进 `Adapter`
- 不把业务策略硬塞进 `repair`

---

## 2) 架构总览（必须先理解）

### 2.1 Solver 继承链

- `core/blank_solver.py::SolverBase`
  - 生命周期调度、插件调度、context/snapshot 访问、评估入口、RNG
- `core/composable_solver.py::ComposableSolver`
  - 引入 `AlgorithmAdapter`，把候选生成与反馈更新委托给 adapter
- `core/evolution_solver.py::EvolutionSolver`
  - 进化范式默认实现（默认 NSGA2 adapter、Pareto 管理、并行评估）

### 2.2 关键依赖关系

- `Solver` 通过 `PluginManager` 扩展，不直接依赖具体插件实现
- `Adapter` 支持 `get_state/set_state` 与 checkpoint 对接
- `RepresentationPipeline` 是候选解流转唯一入口/出口
- 大对象统一进 `SnapshotStore`，`ContextStore` 保持轻量引用

### 2.3 目录职责（高频入口）

- `core/`：求解器主干与运行语义
- `adapters/`：算法策略（NSGA2/3、SPEA2、MOEAD、VNS、SA、DE、TR、A*、MAS 等）
- `plugins/`：能力层（runtime/evaluation/system/ops/storage/backends/models）
- `representation/`：表示组件与 pipeline
- `bias/`：偏置系统（algorithmic/domain/surrogate + facade/manager）
- `core/state/`：context key/schema/contracts/store/snapshot/events（对外主入口）
- `catalog/`：可发现性索引与 profile/filter 规则
- `project/doctor*`：项目规则检查与健康诊断

---

## 3) 运行数据流（改逻辑前必读）

标准一代流程：

1. `adapter.propose(...)` 产出候选
2. 候选经 `representation` 处理（必要时 encode/decode/repair）
3. `evaluate_population()` 或 `evaluate_individual()` 执行评估
4. `adapter.update(...)` 接收目标/约束反馈
5. `plugin` 在代级钩子做观测、持久化、调控
6. 状态按协议写入 snapshot/context

关键点：

- 插件可短路评估链，但返回 shape 必须合法
- 运行态大对象通过 snapshot 引用传递，不直塞 context

---

## 4) 生命周期语义（插件与求解器）

### 4.1 Plugin 生命周期钩子

1. `on_solver_init`
2. `on_population_init`
3. 每代：`on_generation_start` -> `on_step` -> `on_generation_end`
4. `on_solver_finish`

### 4.2 评估路径

- 单点评估：`evaluate_individual()`
- 批量评估：`evaluate_population()`
- 两者均可被插件短路：
  - `evaluate_individual`
  - `evaluate_population`

要求：

- 短路逻辑必须显式、可审计
- 批量路径返回数量必须与候选数量对齐

---

## 5) Context / Snapshot 协议（高风险区）

### 5.1 强制规则

- **禁止**长期把 `population/objectives/violations/history/trace` 直接塞进 context
- 大对象使用 `SnapshotStore.write()`，context 只保留 `_ref/snapshot_key`
- context key 必须来自 `core/state/context_keys.py`

### 5.2 推荐读写优先级

- 读取优先：snapshot -> adapter 内部状态 -> solver 字段
- 写回优先：adapter `set_population*` -> solver `write_population_snapshot()`
- 契约声明：通过 `context_contracts` 标注 `requires/provides/mutates/cache`

---

## 6) 核心 API 契约（新增/改造必须满足）

### 6.1 Adapter API（必备）

- `propose(self, solver, context) -> Sequence[np.ndarray]`
- `update(self, solver, candidates, objectives, violations, context) -> None`

建议实现：

- `get_state()/set_state()`：checkpoint 恢复
- `get_population()/set_population()`：运行态读写对齐
- `get_runtime_context_projection()`：可视化/日志运行切片

### 6.2 Plugin API（生命周期增强）

常见入口：

- `on_solver_init/on_population_init/on_generation_start/on_step/on_generation_end/on_solver_finish`

能力边界：

- 插件增强“能力”，不重写算法语义
- 接管评估时必须保证返回 shape 与类型合法
- 外部资源失败默认 soft-error，必要时给 strict 模式

### 6.3 Representation API（候选解管线）

- `init`
- `mutate`
- `repair`
- `encode`
- `decode`

约束：

- 输入输出可序列化
- shape 稳定
- `repair` 只做约束兜底，不承担业务策略搜索

### 6.4 Bias API（软引导）

- 偏置负责“软引导”而非“硬约束替代”
- 若启用 `ignore_constraint_violation_when_bias`，必须在文档写明风险

### 6.5 Solver/Control Plane 关键 API 速查

- `set_adapter(...)`：挂载/替换算法策略
- `evaluate_individual(...)`：单点评估入口
- `evaluate_population(...)`：批量评估入口
- `write_population_snapshot(...)` / `read_snapshot(...)`：大对象持久化读写
- `set_context_store(...)` / `set_snapshot_store(...)`：后端注入
- `register_controller(...)`：控制器挂载（budget/stop/switch）

---

## 7) Catalog 口径约定（必须遵守）

为避免“框架主干”和“示例/文档索引”混用，采用双口径：

- `default`：完整口径（包含 `example/doc`）
- `framework-core`：纯主干口径（排除 `example/doc`，且不返回 `examples_registry` 导向条目）

### 7.1 使用场景

- 架构重塑/契约审计/主干盘点：**用 `framework-core`**
- 教学演示/模板查找：用 `default`

### 7.2 Agent 执行规范

- 涉及“是否属于框架主干”的结论，命令必须显式带 `--profile framework-core`
- 文档统计必须标注口径（`default` 或 `framework-core`）
- 可设置 `NSGABLACK_CATALOG_PROFILE=framework-core`，但关键命令仍建议显式传参

### 7.3 Catalog 变更验收

- 必须同时验证 `default` 与 `framework-core`
- `framework-core` 下不得出现 `example/doc/examples_registry` 导向结果
- 若改 CLI 行为，`catalog search/list/show` 三子命令行为须一致
- 若影响统计或索引口径，同步更新 `docs/development/COMPONENT_API_INDEX_*`

---

## 8) Agent 改动策略（必须执行）

- 优先修根因，不做表面补丁
- 小步提交：一次只改一层主职责
- 保持 `context_keys`、`extension_contracts`、`doctor` 规则一致
- 改 `catalog` 时优先改 `catalog/registry.py` 的 profile/filter，不在调用侧散落 if/else

涉及评估链改动后，至少验证：

- 单点评估
- 批量评估
- 插件短路评估
- snapshot 读写

---

## 9) 常用开发命令（Windows PowerShell）

```powershell
# 在项目根目录
Set-Location "C:\Users\hp\Desktop\代码逻辑 - 副本\nsgablack"

# 测试（全量）
pytest -q

# 核心测试子集（建议先跑）
pytest tests\test_solver.py tests\test_parallel_integration.py tests\test_snapshot_store.py -q

# 项目体检（严格）
python -m nsgablack project doctor --path . --strict --format problem

# Catalog（主干口径）
python -m nsgablack catalog list --profile framework-core --kind adapter
python -m nsgablack catalog search nsga2 --profile framework-core --limit 20

# Catalog（完整口径对照）
python -m nsgablack catalog list --profile default --kind example
python -m nsgablack catalog list --profile framework-core --kind example
```

---

## 10) 快速接入模板（新增项目）

优先参考：

- `my_project/build_solver.py`
- `my_project/problem/example_problem.py`
- `my_project/pipeline/example_pipeline.py`
- `my_project/plugins/example_plugin.py`

建议路径：先跑通 `problem + pipeline + solver + observability suite`，再引入 bias 与复杂 adapter。

---

## 11) 结语（给自动化协作 Agent）

- 先读 `core/` 与 `core/state/`，再动 `adapters/plugins`
- 改动前确认不破坏 snapshot 引用策略与 context 契约
- 保持系统可回放（decision trace / checkpoint / module report）

---

## 12) 提交前最小检查清单（建议复制到 PR）

- [ ] 是否保持四层边界（Solver / Adapter / Representation / Plugin）
- [ ] 是否避免大对象直写 context（改为 snapshot + ref）
- [ ] 若改评估链，是否验证单点/批量/插件短路三路径
- [ ] 若改 catalog，是否验证 `default` 与 `framework-core` 双口径
- [ ] 是否运行 `project doctor --strict --format problem` 并确认无新增错误
