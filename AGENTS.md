# AGENTS.md

## 1) 项目定位（给协作 Agent 的第一原则）

`nsgablack` 是一个**多目标优化工程框架**，不是单一算法库。
核心设计是四轴正交：
- `Solver`（控制平面 / 生命周期）
- `Adapter`（算法策略 propose/update）
- `Representation`（编码、初始化、变异、修复）
- `Plugin`（能力层：追踪、断点续传、代理评估、日志、后端桥接）

协作时应优先保持这四层边界，不把跨层逻辑硬塞进 `SolverBase`。

---

## 2) 架构速览（必须先理解）

### Solver 继承链

- `core/blank_solver.py::SolverBase`
  - 通用控制平面：context/snapshot 存储、插件生命周期、评估入口、RNG、运行循环
- `core/composable_solver.py::ComposableSolver`
  - 引入 `AlgorithmAdapter`，将优化逻辑委托给 `adapter.propose()/update()`
- `core/evolution_solver.py::EvolutionSolver`
  - 进化范式默认实现（NSGA2 默认 adapter、Pareto 管理、并行评估、history）

### 关键依赖关系

- `Solver` 通过 `PluginManager` 扩展能力，不直接依赖具体插件实现。
- `Adapter` 可以有内部状态（可恢复级别 L0/L1/L2），通过 `get_state()/set_state()` 与 checkpoint 对接。
- `RepresentationPipeline` 是候选解的唯一入口/出口（init/mutate/repair/encode/decode）。
- 大对象统一走 `SnapshotStore`，`ContextStore` 只保留引用 key 与小字段。

---

## 3) 目录职责（高频开发入口）

- `core/`：求解器主干、运行语义、helper 拆分
- `adapters/`：算法策略（NSGA2/3、SPEA2、MOEAD、VNS、SA、DE、TrustRegion、A*、MAS、异步事件驱动、多策略）
- `plugins/`：能力层（runtime/evaluation/system/ops/storage/solver_backends/models）
- `bias/`：偏置体系（algorithmic/domain/surrogate + manager/facade）
- `representation/`：表示层组件与 pipeline
- `utils/context/`：context keys/schema/contracts/store/snapshot/events
- `utils/parallel/`：并行评估与后端选择
- `utils/suites/`：默认插件组合与案例配方
- `catalog/` + `project/doctor*`：组件发现、规则检查、项目健康诊断
- `examples/`：真实组装案例（含生产调度、嵌套供给调整）

---

## 4) 生命周期与运行语义（改动前必看）

### Plugin 生命周期

1. `on_solver_init`
2. `on_population_init`
3. 每代：`on_generation_start` -> `on_step` -> `on_generation_end`
4. `on_solver_finish`

### 评估路径

- 单点评估：`evaluate_individual()`
- 批量评估：`evaluate_population()`
- 两者都支持插件短路：
  - `evaluate_population`
  - `evaluate_individual`

若插件短路返回非空，默认评估路径会被替换。

---

## 5) Context / Snapshot 协议（协作中最容易踩坑）

### 必遵守规则

- **大对象不要长期塞进 context**（population/objectives/history/trace 等）。
- 用 `SnapshotStore.write()` 写大对象，再在 context 放 `_ref` 与 `snapshot_key`。
- 统一 key 定义来自 `utils/context/context_keys.py`，禁止拼写新字符串常量绕过。

### 推荐实践

- 读取优先级：snapshot -> adapter 内部状态 -> solver 字段。
- 写回优先级：adapter `set_population*` -> solver `write_population_snapshot()`。
- 通过 `context_contracts` 声明组件的 `requires/provides/mutates/cache`。

---

## 6) 扩展点契约（新增组件必须满足）

### Adapter

最小契约：
- `propose(self, solver, context) -> Sequence[np.ndarray]`
- `update(self, solver, candidates, objectives, violations, context)`

建议同时实现：
- `get_state()/set_state()`（支持 checkpoint）
- `set_population()/get_population()`（支持 runtime 插件写回）
- `get_runtime_context_projection()`（把关键运行态暴露给可视化/日志）

### Plugin

- 只能在能力层增强，不应重写算法本体语义。
- 若涉及接管评估，必须明确短路事件，并保证返回 shape 合法。
- 对外部资源（DB/OTel/文件）失败应走 soft error，必要时提供 strict 模式。

### Representation

- `init/mutate/repair/encode/decode` 保持输入输出可序列化、shape 稳定。
- `repair` 应是“硬约束最后防线”，不要把业务策略逻辑混入 repair。

### Bias

- 偏置是“软引导”，不应替代约束修复。
- 如果启用 `ignore_constraint_violation_when_bias`，必须在工程文档中明确风险。

---

## 7) 已知问题与风险（当前代码状态）

1. `SolverBase.decode_candidate()` 的能力检查使用 `encoder` 字段，语义上应检查解码能力（实现可工作但表达不严谨）。
2. `SolverBase` 构造参数过多（多层 pass-through），维护成本高，后续可考虑抽 `StorageConfig`。
3. `bias_module` 的 property getter 带懒加载副作用（动态注入 `_bias_module_cached`）。
4. `add_plugin()` 中 `plugin.attach()` 异常默认软处理，可能导致“注册成功但未附着”的隐性状态。
5. `EvolutionSolver.run()` 与 `SolverBase.run()` 存在两套循环语义，改运行逻辑时要同步审视。

---

## 8) 对 Agent 的改动策略（必须遵守）

- 先改“根因”，不要在插件层打补丁掩盖核心缺陷。
- 小步提交：一次只改一层主职责（例如只改 adapter，不同时改 solver lifecycle）。
- 保持 `context_keys`、`extension_contracts`、`doctor` 规则一致。
- 涉及评估 shape 的改动后，至少验证：
  - 单点评估
  - 批量评估
  - 插件短路评估
  - snapshot 读写
- 新增组件必须有最小示例或测试覆盖（建议放 `tests/` 或 `examples/`）。

---

## 9) 常用开发命令（Windows PowerShell）

```powershell
# 在项目根目录
Set-Location "C:\Users\hp\Desktop\代码逻辑 - 副本\nsgablack"

# 运行测试（全量）
pytest -q

# 运行核心子集（建议先跑）
pytest tests\test_solver.py tests\test_parallel_integration.py tests\test_snapshot_store.py -q

# 运行项目体检
python -m nsgablack.project.doctor
```

---

## 10) 快速接入模板（新增项目推荐）

优先参考：
- `my_project/build_solver.py`
- `my_project/problem/example_problem.py`
- `my_project/pipeline/example_pipeline.py`
- `my_project/plugins/example_plugin.py`

目标是先跑通“problem + pipeline + solver + observability suite”，再逐步引入 bias 与复杂 adapter。

---

## 11) 结语

如果你是自动化协作 Agent：
- 先读 `core/` 和 `utils/context/`，再动 `adapters/plugins`。
- 改动前先确认是否破坏 snapshot 引用策略与 context 契约。
- 优先保持系统可回放（decision trace / checkpoint / module report）。
