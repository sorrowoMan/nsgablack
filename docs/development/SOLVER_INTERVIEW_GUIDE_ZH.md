# `nsgablack` Solver 面试复习文档

> 面向面试复习 / 框架理解 / 二次开发。
>
> 本文基于仓库当前源码整理，重点参考：
>
> - `core/blank_solver.py`
> - `core/composable_solver.py`
> - `core/evolution_solver.py`
> - `core/solver_helpers/*.py`
> - `core/state/context_store.py`
> - `core/state/snapshot_store.py`

---

## 1. 先记住：Solver 在这个框架里是什么

`Solver` 是控制平面，不是算法本体。

它主要负责：

1. 运行生命周期（init/loop/finish）
2. 评估入口与插件协同
3. context/snapshot 的一致性
4. 恢复、可观测、扩展能力挂接

一句话：**`Solver` 管“怎么跑”，`Adapter` 管“怎么搜”。**

---

## 2. 三层 Solver 继承关系（面试高频）

### `SolverBase`（`core/blank_solver.py`）

- 控制平面与基础协议
- context/snapshot 写读
- 插件生命周期入口
- 评估路径包装

### `ComposableSolver`（`core/composable_solver.py`）

- 引入 `AlgorithmAdapter`
- 一轮核心链路：`propose -> evaluate -> update`

### `EvolutionSolver`（`core/evolution_solver.py`）

- 进化范式默认实现
- 多目标常用流程、并行评估、历史管理

---

## 3. Solver 的一轮运行链路（你要能口述）

典型一轮可以概括为：

**统一约定**：唯一循环入口是 `run_solver_loop`；各 Solver 的 `run()` 只做结果视图转换（dict / tuple / ExperimentResult）。

1. `build_context()` 组织上下文
2. `plugin_manager.on_generation_start(...)`
3. `adapter.propose(...)` 产出候选
4. `representation_pipeline.repair(...)` 修复候选
5. `evaluate_population(...)`（可被插件短路）
6. `_update_best(...)` 与快照同步
7. `adapter.update(...)`
8. `plugin_manager.on_generation_end(...)`

面试一句话：

> Solver 负责流程与一致性，算法更新点严格收敛在 adapter。  

---

## 4. Context 与 Snapshot：Solver 为什么要双存储

### 4.1 设计原则

- `ContextStore`：放小字段与引用 key
- `SnapshotStore`：放大对象（population/objectives/history/trace）

### 4.2 Solver 关键方法

- `write_population_snapshot(...)`
- `_persist_snapshot(...)`
- `read_snapshot(...)`
- `_strip_large_context(...)`
- `_attach_snapshot_refs(...)`

### 4.3 你可直接说的实现要点

- 快照写入后在 context 中挂 `snapshot_key` 与 `*_ref`
- 严格模式可用 `ensure_snapshot_readable(...)` 做读回校验
- 默认建议内存后端，跨进程/持久化时切 `redis/file`

---

## 5. Solver 与插件的关系边界

### Solver 做什么

- 管生命周期回调顺序
- 管 short-circuit 接口接入点
- 管 snapshot/context 一致性

### 插件做什么

- 提供评估代理、观测、恢复、后端桥接等能力
- 不应篡改算法核心语义

面试防守句：

> 插件负责能力增强，Solver 保持运行语义稳定，Adapter 保持算法语义稳定。  

---

## 6. Solver 与 Bias / Representation 的边界

### Bias

- 通过 `apply_bias_module(...)` 作为软引导
- 不替代硬约束修复

### Representation

- `init/mutate/repair/encode/decode` 统一入口
- `repair` 是硬约束最后防线

---

## 7. 高风险点（可反向体现你熟悉代码）

1. `SolverBase` 构造参数较多（历史兼容 + 配置透传）
2. 运行逻辑在 `SolverBase.run()` 与 `EvolutionSolver.run()` 有差异
3. 快照/上下文如果混放大对象，会造成性能与恢复问题

---

## 8. 面试追问：为什么 Solver 这么“重控制、轻算法”

建议回答：

- 这样算法可替换性更高（adapter 可热插）
- 运维能力更强（checkpoint/trace/report 可统一复用）
- 团队协作更稳（职责边界清晰，排错面更小）

---

## 9. 30 秒口述模板（Solver）

> 在 `nsgablack` 里，Solver 是控制平面，主要负责生命周期、评估中介、context/snapshot 一致性和插件编排，不直接承载算法核心。算法策略在 adapter 的 `propose/update`，候选操作在 representation，能力增强在插件层。这样做的好处是算法可替换、运行可恢复、过程可观测，适合工程化迭代。

---

## 10. 内层求解器（Nested / Inner Runtime）关键点（你这次面试必须能讲）

对应源码：`core/nested_solver.py`。

### 10.1 这个能力解决什么问题

- 外层优化每评估一个候选解时，可能需要再启动一个“内层求解任务”（例如子仿真、子优化、工艺校核）。
- 框架把它做成**问题级评估契约**，而不是把复杂内层逻辑硬编码进 `SolverBase`。

### 10.2 核心对象

- `InnerSolveRequest`：内层输入（candidate、outer_generation、budget、metadata）。
- `InnerSolveResult`：内层输出（objectives、violation、status、cost_units、payload）。
- `InnerRuntimeEvaluator`：通用内层运行器，负责构建、校验、运行、映射结果。
- `TaskInnerRuntimeEvaluator`：面向任务型流程，带 guard、timeout、retry、fallback。

### 10.3 调用链（可口述）

1. 外层在评估阶段触发内层 evaluator；
2. 组装 `InnerSolveRequest`（包含预算和外层代信息）；
3. 通过 `solver_factory` 或 `problem.build_inner_solver(...)` 创建内层 solver；
4. 校验 `accepted_parent_contracts`，防止契约不匹配；
5. 执行 `inner_solver.run()`，归一化为 `InnerSolveResult`；
6. 通过 `result_projector` 或 `problem.evaluate_from_inner_result(...)` 回投到外层目标/约束。

### 10.4 工程护栏（面试加分）

- 预算护栏：`default_budget_units`、`max_total_budget_units`。
- 契约护栏：`parent_contract` + `accepted_parent_contracts`。
- 鲁棒护栏（Task 版）：`per_call_timeout_ms`、`max_retries`、`retry_backoff_ms`、`fallback_penalty`。
- 可观测护栏：`on_inner_guard`、`on_inner_result` 事件可被插件接管记录。

### 10.5 边界怎么讲

- 内层求解器是**问题层语义**，不是 L4 评估 provider 的替代品。
- 评估 provider 解决“如何评估”，内层求解器解决“评估本身还要再求解一次”的嵌套结构。

### 10.6 高频追问模板

Q：为什么不直接在 `problem.evaluate()` 里塞所有内层逻辑？  
A：可行但不可治理。`InnerRuntimeEvaluator` 把预算、契约、超时、重试、回退和统计统一抽象，避免业务脚本化膨胀。

Q：内层失败怎么办？  
A：`TaskInnerRuntimeEvaluator` 支持重试与回退惩罚，并通过状态统计（success/failure/fallback/timeouts）可观测。

Q：为什么说它是 Solver 关键点？  
A：它决定了“外层候选评估是否可工程化复现”，直接影响吞吐、稳定性和可追溯性。

---

## 11. 一页速记（只背这些）

- `SolverBase`：协议与存储
- `ComposableSolver`：`propose/evaluate/update`
- `EvolutionSolver`：进化默认范式
- `InnerRuntimeEvaluator`：外层评估中的内层求解契约
- 小字段进 `ContextStore`，大对象进 `SnapshotStore`
- 插件增强能力，不改算法本体
- `Solver` 稳定语义，`Adapter` 快速迭代
