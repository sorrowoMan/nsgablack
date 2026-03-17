# `nsgablack` Plugins 面试复习文档

> 面向面试复习 / 插件治理 / 运行能力扩展。
>
> 本文基于仓库源码整理，重点参考：
>
> - `plugins/base.py`
> - `plugins/__init__.py`
> - `core/blank_solver.py`
> - `core/solver_helpers/context_helpers.py`

---

## 1. 先记住：Plugin 在这个框架里是什么

Plugin 是能力层，不是算法层。

它用于：

1. 观测（trace/report/profiler）
2. 恢复（checkpoint）
3. 评估接管（surrogate/multi-fidelity/solver backend）
4. 运行治理（timeout/boundary/event hub）

一句话：**Plugin 让系统“能工程化”，但不应重写算法本体语义。**

---

## 2. 生命周期（必须背）

标准顺序：

1. `on_solver_init`
2. `on_population_init`
3. 每代：`on_generation_start -> on_step -> on_generation_end`
4. `on_solver_finish`

对应实现：`plugins/base.py::Plugin` + `PluginManager` 触发。

---

## 3. `PluginManager` 核心能力

### 3.1 注册与执行

- `register/unregister/get`
- 按 `priority` 稳定排序
- 支持 enable/disable

### 3.2 触发模型

- `trigger(event, ...)`：逐个插件执行
- `dispatch(event, ...)`：支持返回最后非空结果

### 3.3 短路机制（高频追问）

- `short_circuit=True`
- `short_circuit_events={...}`
- 在允许事件上返回非空即可接管默认路径

典型：评估插件接管 `evaluate_population` / `evaluate_individual`。

---

## 4. 插件与快照协议（非常关键）

`Plugin` 基类提供：

- `get_population_snapshot(...)`
- `commit_population_snapshot(...)`

### 读取优先级

1. `solver.read_snapshot()`
2. `adapter.get_population()`
3. `solver.population/objectives/violations`

### 写回优先级

1. `adapter.set_population*`
2. `solver.write_population_snapshot(...)`

意义：

- 插件不直接硬改 solver 大对象
- 统一通过 snapshot 协议读写，避免状态分叉

---

## 5. 插件上下文合同与可追溯性

每个插件支持合同字段：

- `context_requires`
- `context_provides`
- `context_mutates`
- `context_cache`
- `context_notes`

`PluginManager.dispatch('on_context_build', ctx)` 还能记录 key 写入来源（writer attribution）。

---

## 6. 插件分类速记（按职责）

### 运行时

- `ParetoArchivePlugin`
- `DynamicSwitchPlugin`

### 评估层

- `SurrogateEvaluationProviderPlugin`
- `MultiFidelityEvaluationProviderPlugin`
- `MonteCarloEvaluationProviderPlugin`
- `EvaluationModelProviderPlugin`

### 运维/系统层

- `CheckpointResumePlugin`
- `TimeoutBudgetPlugin`
- `AsyncEventHubPlugin`
- `BoundaryGuardPlugin`

### 可观测层

- `DecisionTracePlugin`
- `ModuleReportPlugin`
- `BenchmarkHarnessPlugin`
- `ProfilerPlugin`

---

## 7. Plugin 逐项介绍（按导出清单一项项过）

以下名称来自 `plugins/__init__.py::__all__`，重点讲插件类（`*Plugin`）。

### 7.1 Runtime 运行时插件

| Plugin | 作用一句话 | 适用场景 | 注意点 |
| --- | --- | --- | --- |
| `BasicElitePlugin` | 基础精英保留 | 稳态提升 | 保留比例过高会降多样性 |
| `HistoricalElitePlugin` | 历史精英回注 | 防退化 | 要防过期精英干扰 |
| `DiversityInitPlugin` | 多样性初始化增强 | 初始覆盖不足 | 与 problem 边界一致 |
| `ParetoArchivePlugin` | 外部前沿归档 | 多目标输出 | archive 尺寸与更新策略要明确 |
| `DynamicSwitchPlugin` | 动态切换策略 | 阶段搜索 | 切换条件需可解释 |

### 7.2 Evaluation 评估插件

| Plugin | 作用一句话 | 适用场景 | 注意点 |
| --- | --- | --- | --- |
| `SurrogateEvaluationProviderPlugin` | 代理模型评估接管 | 昂贵评估 | 必留真值回注 |
| `MultiFidelityEvaluationProviderPlugin` | 多保真评估调度 | 分级仿真 | 保真切换条件要稳定 |
| `MonteCarloEvaluationProviderPlugin` | MC 采样评估 | 随机不确定问题 | 采样预算需受控 |
| `NumericalSolverProviderPlugin` | 数值求解器评估桥接 | 方程/物理模型 | 收敛失败要软处理 |
| `NewtonSolverProviderPlugin` | Newton 迭代评估接入 | 可导局部求解 | 初值敏感 |
| `BroydenSolverProviderPlugin` | Broyden 近似求解 | 无显式 Jacobian | 收敛性需监控 |
| `GpuEvaluationTemplateProviderPlugin` | GPU 评估模板接入 | 批量并行评估 | 资源管理和回退策略 |
| `EvaluationModelProviderPlugin` | 模型生命周期管理 | surrogate 全流程 | 版本与漂移治理 |

### 7.3 Ops 可观测与分析插件

| Plugin | 作用一句话 | 适用场景 | 注意点 |
| --- | --- | --- | --- |
| `BenchmarkHarnessPlugin` | 对比实验与指标采集 | A/B 与回归 | 指标口径统一 |
| `ModuleReportPlugin` | 模块级报告输出 | 可解释汇报 | 报告字段需稳定 |
| `ProfilerPlugin` | 运行性能剖析 | 性能优化 | 采样开销需评估 |
| `SensitivityAnalysisPlugin` | 敏感性分析 | 鲁棒性评估 | 参数扫描预算 |
| `OpenTelemetryTracingPlugin` | 分布式追踪 | 生产可观测 | 采样率与隐私治理 |
| `DecisionTracePlugin` | 决策轨迹记录 | 可解释与复盘 | 粒度过细会膨胀 |
| `SequenceGraphPlugin` | 序列图化追踪 | 复杂流程分析 | 需控制图规模 |

### 7.4 Models 模型支持插件

| Plugin | 作用一句话 | 适用场景 | 注意点 |
| --- | --- | --- | --- |

### 7.5 Storage 与 System 插件

| Plugin | 作用一句话 | 适用场景 | 注意点 |
| --- | --- | --- | --- |
| `MySQLRunLoggerPlugin` | 运行日志入库 | 持久化审计 | 连接失败要软降级 |
| `AsyncEventHubPlugin` | 异步事件总线 | 事件驱动优化 | schema/重试/回压 |
| `BoundaryGuardPlugin` | 运行边界保护 | 风险控制 | 规则误杀需可调 |
| `CheckpointResumePlugin` | 断点续传恢复 | 长跑/容错 | snapshot 一致性必测 |
| `TimeoutBudgetPlugin` | 超时与预算治理 | 外部评估/内层任务 | 超时后回退策略 |

### 7.6 与插件协同的后端桥接组件（非 Plugin 但常被追问）

| 组件 | 作用 |
| --- | --- |
| `ContractBridgePlugin` + `BridgeRule` | 合同桥接与字段映射 |
| `BackendSolver` / `BackendSolveRequest` | 求解后端统一契约 |
| `NgspiceBackend` | 领域后端示例实现 |

---

## 8. 高风险点（面试能加分）

1. 插件 attach 失败但未严格阻断，可能“注册成功但未附着”
2. 非短路事件返回值会被忽略（并警告）
3. 插件过度侵入算法状态会破坏层次边界

---

## 9. 什么时候该用 Plugin，而不是改 Solver

用 Plugin 的场景：

- 能力是横切关注点（观测、恢复、预算、桥接）
- 需要按项目开关/组合
- 希望不影响算法核心语义

改 Solver 的场景：

- 生命周期主语义需要重构
- 控制平面协议本身要变

---

## 10. 面试追问模板（Plugin）

### Q1：为什么不用继承 Solver 来做所有扩展？

A：继承会把能力耦合进主干，插件化能做到按需组合、低侵入和可治理。

### Q2：插件如何保证不污染状态？

A：通过 snapshot 协议读写、context contract 显式声明、以及 manager 统一调度与可观测追踪。

### Q3：评估插件接管会不会失控？

A：通过短路事件白名单和 strict 策略控制，同时可配 trace/report 验证行为。

---

## 11. 30 秒口述模板（Plugin）

> `nsgablack` 把恢复、评估代理、观测、系统治理做成插件层，由 `PluginManager` 统一生命周期调度，并通过短路事件实现可控接管。插件读写群体状态优先走 snapshot 协议，避免直接改 solver 大对象。这样我们可以在不破坏算法和控制平面的前提下，持续叠加工程能力。

---

## 12. 一页速记（只背这些）

- Plugin 是能力层，不是算法层
- 生命周期 5 段必须熟
- 导出插件可按 Runtime/Evaluation/Ops/Models/System 五组记忆
- `short_circuit + short_circuit_events` 控制接管
- 快照读写走 `resolve/commit_population_snapshot`
- 合同字段让依赖与副作用可治理
- 插件优先低侵入，不改主语义
