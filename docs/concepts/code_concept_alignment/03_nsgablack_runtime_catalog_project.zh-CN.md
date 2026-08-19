# 03. nsgablack 运行治理、Catalog 与项目面向对齐

覆盖路径：

- `plugins/base.py`
- `plugins/runtime/*`, `plugins/evaluation/*`, `plugins/ops/*`, `plugins/storage/*`, `plugins/solver_backends/*`
- `core/state/*`（优化状态）与 `blackbase.context`（共享 Context/Snapshot）
- `catalog/*`
- `project/doctor*`, `project/scaffold.py`
- `utils/runtime/*`, `utils/engineering/*`

## 1. Plugin 基类与生命周期

| 代码叫法 | 社区常用叫法 | 机制含义 | 你的差异点 |
| --- | --- | --- | --- |
| `Plugin` | callback / middleware / lifecycle extension | 插件能力基类。 | 插件不应重写算法语义，只增强运行能力。 |
| `on_solver_init` | initialization callback | solver 初始化后触发。 | 能力挂载在生命周期上，而不是散落在主循环。 |
| `on_population_init` | population initialization hook | 初始种群后触发。 | runtime 插件可观测初始状态。 |
| `on_generation_start/end` | generation lifecycle hook | 每代开始/结束事件。 | 日志、trace、archive、switch 可统一接入。 |
| `on_step` | per-step callback | 每步运行观察或干预。 | 控制类插件有正式入口。 |
| `on_solver_finish` | finish callback | 运行结束后报告/持久化。 | 统一收尾和 artifact/report 输出。 |
| `get_report` | plugin report / audit payload | 插件输出小报告。 | algorithmic plugin 才应该产出算法报告。 |
| `get_population_snapshot` | snapshot-first runtime read | 优先从 snapshot 读 population。 | 插件读取状态遵循 snapshot -> adapter -> solver 字段。 |
| `PluginManager` | callback dispatcher | 插件调度器。 | 支持 priority、strict/soft-error、短路事件。 |

## 2. Runtime 插件

| 代码路径 | 社区常用叫法 | 机制含义 |
| --- | --- | --- |
| `plugins/runtime/pareto_archive.py` | Pareto archive / elite set | 保存非支配前沿或精英解。 |
| `plugins/runtime/elite_retention.py` | elitism / survivor preservation | 精英保留。 |
| `plugins/runtime/diversity_init.py` | diversity-aware initialization | 多样性初始化。 |
| `plugins/runtime/dynamic_switch.py` | dynamic strategy switching / adaptive control | 运行中切换策略或参数。 |

对齐说明：这些不是 solver 主逻辑，而是运行期能力。它们类似 callback/controller，但在你的框架里有更强的 context/snapshot 契约。

## 3. Evaluation 插件

| 代码路径 | 社区常用叫法 | 机制含义 | 你的差异点 |
| --- | --- | --- | --- |
| `surrogate_evaluation.py` | surrogate evaluator / response surface evaluator | 用代理模型接管或辅助评估。 | 插件短路评估必须守 shape。 |
| `multi_fidelity_evaluation.py` | multi-fidelity evaluation | 高低保真评估切换。 | 作为能力层接入，不污染 adapter。 |
| `monte_carlo_evaluation.py` | Monte Carlo evaluator | 随机模拟评估。 | 可与黑箱 problem 统一。 |
| `gpu_evaluation_template.py` | GPU evaluator provider | GPU 加速评估模板。 | 作为 provider 能力而不是 solver 内部分支。 |
| `numerical_solver_base.py`, `newton_solver_plugin.py`, `broyden_solver_plugin.py` | numerical solver provider | 数值求解器作为评估/内层能力。 | 说明 evaluation provider 可是学习模型，也可是数值求解器。 |

## 4. Solver backend 插件

| 代码路径 | 社区常用叫法 | 机制含义 |
| --- | --- | --- |
| `backend_contract.py` | backend request/response contract | 后端求解请求协议。 |
| `copt_backend.py` / `copt_templates/*` | mathematical programming backend | COPT/锥优化/线性/二次/半定等后端模板。 |
| `ngspice_backend.py` | simulator backend | 电路仿真后端。 |
| `mlblack.integrations.nsgablack_symbolic_backend` | inner ML/symbolic workflow backend | nsgablack 通过 mlblack 正式集成面调用符号共识流。 |
| `timeout_budget.py` | timeout/budget guard | 后端预算与超时控制。 |
| `contract_bridge.py` | backend contract adapter | 后端契约转换。 |

对外表达：

> Solver backends let the outer optimizer treat simulators, mathematical programming solvers, and ML workflows as governed inner evaluators.

## 5. Ops / Storage 插件

| 代码路径 | 社区常用叫法 | 机制含义 |
| --- | --- | --- |
| `plugins/ops/decision_trace.py` | decision trace / audit log | 记录决策过程。 |
| `plugins/ops/module_report.py` | module report / component inventory | 输出模块装配报告。 |
| `plugins/ops/sequence_graph.py` | execution sequence graph | 运行序列图。 |
| `plugins/ops/profiler.py` | profiler | 性能分析。 |
| `plugins/ops/sensitivity_analysis.py` | sensitivity analysis | 敏感性分析。 |
| `plugins/storage/mysql_run_logger.py` | run logger / experiment DB sink | 运行记录落库。 |
| `plugins/storage/runtime_surface_tracker.py` | lineage tracker / run surface registry | surface/assembly/run/artifact 持久化。 |

## 6. Context / Snapshot 状态面

| 代码叫法 | 社区常用叫法 | 机制含义 | 你的差异点 |
| --- | --- | --- | --- |
| `ContextStore` | runtime context store | 轻量上下文状态。 | 不长期存大对象。 |
| `SnapshotStore` | snapshot/object store | 大对象持久化。 | population/objectives/history/trace 通过 ref 进入 context。 |
| `context_keys.py` | state key registry / schema keys | 集中定义上下文字段。 | 避免隐式字符串字段漂移。 |
| `context_contracts.py` | data contract registry | 声明组件读写字段。 | 用于 doctor/catalog/报告。 |
| `context_events.py` | state event log | 状态事件。 | 有利于回放和审计。 |
| `context_field_governance.py` | state governance rules | 上下文字段治理。 | 防止大对象直写和字段污染。 |

## 7. Catalog

| 代码叫法 | 社区常用叫法 | 机制含义 | 你的差异点 |
| --- | --- | --- | --- |
| `catalog/registry.py` | component registry / metadata catalog | 组件索引。 | 以 profile/filter 管理主干与示例口径。 |
| `framework-core` profile | core-only catalog view | 主干口径。 | 避免 example/doc 混入框架主干结论。 |
| `default` profile | full catalog view | 完整口径。 | 教学、模板和案例可发现。 |
| `catalog search/list/show` | discoverability CLI | 查组件。 | 组件可被人和自动化工具共同发现。 |
| `catalog/store/*` | catalog persistence backend | Catalog 落库。 | 支持 sqlite/mysql/postgres 类持久化查询。 |
| `contract_relations.py` | component relation graph | 组件契约关系。 | 连接 requires/provides/mutates 等信息。 |
| `dashboard_*` | catalog UI | 可视化检索面。 | 让框架能力可浏览，不只靠 README。 |

## 8. Project scaffold / Doctor

| 代码叫法 | 社区常用叫法 | 机制含义 | 你的差异点 |
| --- | --- | --- | --- |
| `project/scaffold.py` | project generator / app scaffold | 生成标准项目结构。 | problem/pipeline/config/build_solver/plugins/reporting 分层。 |
| `project doctor` | structural linter / health checker | 检查项目规则。 | 面向框架契约，不只是 Python lint。 |
| `snapshot_context_policy` rule | state hygiene rule | 检查大对象是否直写 context。 | 强制 snapshot/ref 协议。 |
| `adapter_purity` rule | architecture boundary rule | 检查 adapter 纯度。 | 防止算法策略层越权。 |
| `runtime_surface` rule | experiment surface rule | 检查运行入口和 surface。 | 确保运行可审计。 |
| `component_catalog` rule | discoverability rule | 检查组件是否可索引。 | 防止正式组件不可发现。 |

## 9. Run surface 四记录

| 代码叫法 | 社区常用叫法 | 机制含义 |
| --- | --- | --- |
| `SurfaceRecord` | workflow entry record | 跑的是哪个标准入口。 |
| `AssemblyRecord` | component composition manifest | 实际挂载了哪些组件。 |
| `RunRecord` | experiment run record | 一次具体运行。 |
| `ArtifactRecord` | artifact lineage record | 产物及其来源。 |
| `assembly_signature` | configuration fingerprint | 装配指纹。 |
| `artifact_signature` | artifact fingerprint | 产物指纹。 |

## 10. 这一层的核心价值

| 传统写法 | 你的写法 |
| --- | --- |
| 日志、checkpoint、trace 都手写在算法循环里。 | 插件生命周期统一管理。 |
| 运行结果只是一堆文件。 | surface/assembly/run/artifact 四层记录。 |
| 组件靠 README 找。 | catalog + profile + UI + DB。 |
| 项目结构靠约定俗成。 | scaffold + doctor 约束结构。 |
| 大对象和小状态混在 dict。 | context/snapshot 分层。 |
