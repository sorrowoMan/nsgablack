# AGENTS.md

## 0) 这份文档怎么用（给协作 Agent）

这是一份“面向改动执行”的协作说明，不是概念介绍。
阅读顺序建议：

1. 先看 `1/2/4`（定位 + 架构 + 生命周期）
2. 再看 `5/6/7`（数据协议 + API 契约 + catalog 口径）
3. 最后按 `9/12` 跑命令与提交检查

新增协作硬规则：

- **在任何代码改动、测试执行、benchmark 运行、批量脚本落地之前，必须先得到用户明确允许**
- 在未获允许前，只允许做：代码阅读、结果分析、机制讨论、方案草案、文档整理
- 不得因为“已经判断出根因”或“只差最后一步”而直接落代码
- 若用户只是在讨论机制、诊断病因、比较路线，默认仍视为**未授权改代码**

文档语言规则（新增）：

- 教程与介绍类文档默认以**中文**为主版本（尤其 `docs/standard_scaffold_tutorial`）。
- 英文版本允许保留，但必须另起独立文件（如 `*_EN.md`），不得覆盖中文主文档。
- 若新增章节，先补中文主文档，再按需要补英文版。

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

### 1.1 统一框架栈规则（nsgablack + mlblack）

`nsgablack` 和 `mlblack` 应被视为一个统一框架栈的不同层，而不是两个孤立项目。新增组件、模型族、provider、runtime、示例或跨框架能力前，必须同时判断两边职责边界。

统一分工：

- `nsgablack` 和 `mlblack` 共享统一的 Project / Case / Scaffold / L0 substrate。编排属于 substrate，不属于任一语义层的私有能力。
- 所有标准 Case 都可以作为外层或内层；外层 Case 通过 `evaluate()`、stage runner 或 project runner 短路调用内层标准脚手架。
- 所有标准 Case 都可以声明资源需求；只有 Project-level L0 substrate 发放 `ResourceContext` grant。Case-level `runtime/` 只负责 requirement/profile/audit，不直接拥有全局 lease。

- `nsgablack` 负责优化搜索语义：solver lifecycle、candidate search、multi-objective/Pareto、adapter strategy、objective/constraint optimization。
- `mlblack` 负责 ML 语义组件、DataView、Spec、Codec、Head、Problem、Trainer、Provider、Artifact、backend capability。
- 外部 domain backend（数值求解器、仿真器、数据库、向量索引、对象存储、Ray/K8s/云服务）只能通过正式 bridge/provider/runtime surface 接入，不应污染两边核心职责。

新增能力前必须先分类：

- 属于 `nsgablack orchestration`：阶段、并行、outer search、多 solver、Pareto、嵌套评估、资源授权。
- 属于 `mlblack semantic component`：数据视图、模型语义、head、训练/评估、artifact、capability contract。
- 属于外部 domain backend：数值求解器、仿真器、索引、数据库、对象存储。
- 属于 cross-framework scaffold：通过两边正式脚手架 surface 组合，而不是在 example 里私接胶水。

硬规则：
- 不允许 `nsgablack` 硬编码 `mlblack` trainer/provider 内部细节；只能通过 `component_overrides`、inner task payload、`ResourceContext`、artifact/result payload 通信。
- PINN、Neural ODE、时序、多模态、符号学习、推荐、科学计算等能力必须综合考虑 `nsgablack + mlblack` 的统一分工，不能只在一个仓库里局部堆实现。

## 1.2 Project / Case / Scaffold directory rule

Projects must follow a three-layer structure: Project -> Case -> Standard Scaffold. `Solver` and `Trainer` are the same abstraction level and share the same Case scaffold. The only difference is catalog semantics (`kind=solver` vs `kind=trainer`), not directory shape.

### 1.2.1 Three layers

1. **Project**
   - Coordinates cross-case orchestration, resource allocation, and the top-level run entry.
   - Contains `run_project.py`, `project_config.py`, and `cases/`.

2. **Case**
   - A self-contained runnable unit, usually one Solver or Trainer.
   - Lives under `cases/<case_name>/` and is itself a complete standard scaffold.

3. **Standard Scaffold**
   - Implements one Solver/Trainer: problem, pipeline, adapter, plugins, runtime, and entrypoints.
   - Uses `build_solver.py` as the canonical assembly entry.

### 1.2.2 Unified Case template

```text
case_name/
  __init__.py
  build_solver.py           # canonical assembly entry
  build_trainer.py          # alias only: from .build_solver import build_solver as build_trainer
  run_solver.py             # canonical CLI entry
  run_trainer.py            # alias only: from .run_solver import main
  config.py                 # component registry aggregation
  problem/
  pipeline/                 # all encode/decode/init/mutate/repair + data pipeline components
  adapter/
  bias/
  plugins/                  # unified capability layer; mlblack capabilities are Plugin-compatible
  evaluation/
  runtime/
  solver/
```

Hard rules:

- `build_solver.py` is the only canonical assembly entry; `build_trainer.py` must remain a thin alias.
- `run_solver.py` is the only canonical CLI entry; `run_trainer.py` must remain a thin alias.
- `representation/` is not a Case-level directory; model encoding/decoding belongs inside `pipeline/`.
- `assembly/scaffold.json` is not a formal assembly entry; assembly logic belongs in `build_solver.py`.
- `capabilities/` is not a Case-level capability directory; use `plugins/`.
- One Solver/Trainer lives in one independent Case folder; registration, assembly, and entries must close inside that Case.

### 1.2.3 Unified Plugin / Capability lifecycle

mlblack `Capability` maps into the unified nsgablack `Plugin` lifecycle. `nsgablack.plugins.base.Plugin` is the shared superset and includes:

| Hook | Source | Timing |
|---|---|---|
| `on_solver_init` | nsgablack / mlblack `on_fit_start` | run start |
| `on_population_init` | nsgablack | after initial population |
| `on_step_attempt_start` | unified | every physical attempt start |
| `on_generation_start` | nsgablack / mlblack `on_step_start` | committed logical generation start |
| `on_evaluate_start` | mlblack / unified | before candidate evaluation |
| `on_evaluate_end` | mlblack / unified | after candidate evaluation |
| `on_step` | nsgablack | after generation step |
| `on_generation_committed` | unified | committed logical generation only |
| `on_generation_end` | nsgablack / mlblack `on_step_end` | committed logical generation end |
| `on_step_attempt_end` | unified | every physical attempt end, including failures |
| `on_solver_finish` | nsgablack / mlblack `on_fit_end` | run finish |
| `on_solver_finalization_prepare` | unified | teardown 成功后、事务提交前的严格发布校验 |
| `on_solver_finalized` | unified | 最终结果与 Artifact 已成为权威状态后的通知 |
| `on_error` | mlblack / unified | error handling |
| `on_context_build` | nsgablack | context construction |

### 1.2.4 Project shape

```text
<project_root>/
  project_config.py
  run_project.py
  README.md
  cases/
    __init__.py
    <case_a>/
      __init__.py
      build_solver.py
      run_solver.py
      problem/
      pipeline/
      adapter/
      ...
    <case_b>/
      ...
```

Collaboration rules:

- Each Case must be independently runnable and testable.
- Cross-case order, parallelism, and resource allocation belong in `project_config.py` / `run_project.py`, not inside a Case.
- `cases/` and every `cases/<case_name>/` must include `__init__.py`.
- Case dependencies must pass through Artifact/Snapshot references injected by the top-level orchestrator.
- New multi-Solver or multi-Trainer projects must use this three-layer structure.

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
- `plugins/`：能力层（runtime/evaluation/system/ops/storage/domain_backends）
- `representation/`：表示组件与 pipeline
- `bias/`：偏置系统（algorithmic/domain/surrogate + facade/manager）
- `core/state/`：context key/schema/contracts/store/snapshot/events（公共 API 入口；实现在 utils/context/）
- `core/resources/`：L0 资源层
  - `compute/` — 执行加速（PoolScheduler, ParallelEvaluator 重导出）
  - `storage/` — 状态持久化（ContextStore, SnapshotStore, ArtifactBackend, lease）
  - `transport/` — 消息/队列/传输（TaskQueue, MessageQueue, L0RuntimeBackend）
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
3. 每次物理尝试：`on_step_attempt_start` -> `on_step_attempt_end`（即使 idle/rejected/cancelled/error 也必须成对）
4. 只有提交逻辑代：`on_generation_start` -> `on_step` -> `on_generation_committed` -> `on_generation_end`
5. `on_solver_finish`
6. 事务型结果发布：`on_solver_finalization_prepare` -> atomic commit -> `on_solver_finalized`

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

- `propose(self, solver, context) -> Sequence[np.ndarray | UnknownState]`
- `update(self, solver, candidates, feedback: OptimizationFeedbackBatch, context) -> None`

候选进入控制面后使用 `CandidateBatch` 同时保留 `semantic_states`、`numeric_matrix`
和 candidate token/provenance：数值算法消费矩阵，Representation / Problem / 结果对齐消费
语义状态。Solver 持有跨代权威 CandidateBatch population；拥有内部环境选择的 Adapter
必须返回与选中行对齐的 candidate tokens，不得按数值相等反推语义状态。`feedback` 的正式形态为 `OptimizationFeedbackBatch`；它仍可解包为
`(objectives, violations)` 供纯数值 Adapter 使用，但不得再定义另一套拆分参数签名。

建议实现：

- `get_state()/set_state()`：checkpoint 恢复
- `snapshot_step_state()/restore_step_state()`：步骤事务回滚；默认可复用脱离后的
  `get_state()/set_state()`，禁止通过 `deepcopy(adapter.__dict__)` 复制锁、executor、
  Provider/session 或任意第三方对象图
- `step_transaction_children()`：复合 Adapter 显式声明拥有独立事务状态的子 Adapter；
  父级事务快照只能保存局部状态，禁止再嵌套保存同一子 Adapter 的 checkpoint state
- `commit_step_state()`：只执行 semantic commit 之后的资源清理；所有参与者都必须被
  尝试并生成 `AdapterCommitReport`。Provider-backed Adapter 按稳定 state ID 清理，
  失败引用必须保留为可重试 cleanup queue，禁止把清理失败伪装成整代未提交
- `population_state_mode`：L2 Adapter 必须显式声明 `single`、`delegate` 或 `partitioned`
- `get_population_snapshot()/set_population_snapshot()`：仅用于 `single/delegate` 模式下完整 L2 population `(X, F, V)` 的权威读写
- `get_population_partitions()/set_population_partitions()`：`partitioned` 复合 Adapter 按稳定 unit/role/phase ID 保存多个 `PopulationPartition`，不得把不同子群体无语义拼接
- `get_current_candidates()/set_current_candidates()`：L1/trajectory Adapter 的当前候选访问；不得冒充 population snapshot
- `get_runtime_context_projection()`：可视化/日志运行切片

恢复顺序是 `prepare -> setup -> Plugin.prepare_restore -> apply restore envelope -> ordinary init hooks -> initialize if fresh -> run`。`set_state()`、外部 Case 预加载与 checkpoint 插件必须先排队恢复信封，不能在 `setup()` 之前直接污染 Adapter 运行态，也不能由各 Adapter 私自维护 `_state_loaded` 分支。普通 `on_solver_init` 钩子必须只观察恢复后的状态。

`RuntimeController` 与有状态 Controller 属于正式 checkpoint component；Controller 必须
按稳定 name/type 导出恢复状态。生命周期结束通知必须独立清理并聚合异常，一个严格
参与者失败不能阻止其他已启动 Plugin/Controller 收到对应 end。

运行级完成条件必须消费可恢复的 `RunProgressState`（逻辑步数、物理尝试数、累计耗时、剩余 deadline 与可选 policy state）。`Solver.step()` 必须返回 `StepOutcome`；只有 `status=committed` 才计入 generation/step 并触发 `on_step/on_generation_committed`，空执行、拒绝与取消不得制造幽灵步骤。`max_steps` 是逻辑提交预算，`max_step_attempts` 是独立活性保护。

Population Snapshot 正式 schema 是 `nsgablack.population_snapshot/v2`。`population_state_mode=partitioned` 时，快照顶层不得出现单一 population/objectives/violations；必须保存 partitions，并把最后评估批次放入独立事件字段。单 population 消费者遇到 partitioned authority 必须 fail-closed。

步骤内权威 Snapshot 必须先 staging，只有 `StepOutcome.committed` 才能用新 key 发布；
Evaluation Event 使用独立 key，失败/拒绝尝试不得覆盖上一份权威 Population Snapshot。
Event 写入前必须在 BlackBase `EvaluationEvidenceJournal` 预留索引，落盘后标记 pending，
Disposition 发布前登记 intent，目标 Snapshot 可读后才结算 terminal。恢复只能按 durable
evidence 补结算或归档 abandoned，不得隐式重跑 Problem、AcceptancePolicy 或 Adapter。
`on_solver_finish` 是 teardown 前的 finishing 通知。事务型发布在 teardown 成功后先调用
`on_solver_finalization_prepare`；该严格钩子可在正式引用公开前否决整组暂存产物。原子 commit
成功后才调用 `on_solver_finalized`，此时最终结果、最终 checkpoint 与成功证据已经具有权威语义。

### 6.2 Plugin API（生命周期增强）

常见入口：

- `prepare_restore/on_solver_init/on_population_init/on_step_attempt_start/on_generation_start/on_step/on_generation_committed/on_generation_end/on_step_attempt_end/on_solver_finish/on_solver_finalization_prepare/on_solver_finalized`

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
- `framework-core`：纯主干口径（排除 `example/doc` 与任何 `examples/` 导向条目）

### 7.1 使用场景

- 架构重塑/契约审计/主干盘点：**用 `framework-core`**
- 教学演示/模板查找：用 `default`

### 7.2 Agent 执行规范

- 涉及“是否属于框架主干”的结论，命令必须显式带 `--profile framework-core`
- 文档统计必须标注口径（`default` 或 `framework-core`）
- 可设置 `NSGABLACK_CATALOG_PROFILE=framework-core`，但关键命令仍建议显式传参

### 7.3 Catalog 变更验收

- 必须同时验证 `default` 与 `framework-core`
- `framework-core` 下不得出现 `example/doc/examples/` 导向结果
- 若改 CLI 行为，`catalog search/list/show` 三子命令行为须一致
- 若影响统计或索引口径，同步更新 `docs/development/COMPONENT_API_INDEX_*`

---

## 8) Agent 改动策略（必须执行）

- 优先修根因，不做表面补丁
- 小步提交：一次只改一层主职责
- 保持 `context_keys`、`extension_contracts`、`doctor` 规则一致
- 改 `catalog` 时优先改 `catalog/registry.py` 的 profile/filter，不在调用侧散落 if/else
- 新增或修改 `example/demo/benchmark runner` 时，必须走标准项目脚手架形态，不要在例子里私搭第二套运行入口
- **先获用户许可，再动代码、跑测试、跑 benchmark；未获许可时只做分析与方案整理**

涉及评估链改动后，至少验证：

- 单点评估
- 批量评估
- 插件短路评估
- snapshot 读写

---

## 9) 示例组装规则（必须遵守）

如果要新增或修改示例、演示或 benchmark runner，必须使用标准项目脚手架形态来组装。

这里的“标准脚手架”首先是**正式职责分层**，其次是**正式落点**：

- 对于 `example / demo / benchmark runner / cross-framework case`，完整脚手架必须优先落在 `examples/cases/<case>/` 或同级 `examples/*` 正式示例命名空间
- **禁止**继续把这类完整示例脚手架默认落进仓库根部 `my_project/`
- `my_project/` 只可作为框架级起步模板、参考骨架、兼容层或用户私有项目孵化位，**不是**示例案例的长期堆放区

标准脚手架本身应具备如下正式项目结构与职责分层：

- `problem/`：问题定义、目标、约束、数据/场景契约
- `pipeline/`：候选流转、representation、evaluation chain、数据处理链
- `config/`：可声明、可复现的装配配置
- `build_solver.py` / `run_solver.py`：正式组装入口与运行入口
- `plugins/` / `bias/` / `reporting/`：按能力边界落位
- `registry` / `catalog`：需要被发现的正式组件必须可索引

示例文件本身只能是薄入口、兼容层或教学调用层。真实装配逻辑必须进入上述标准项目结构，而不是堆在 `examples/.../*.py` 里。

允许：

- 优先复用正式 `solver / adapter / representation / plugin` 装配路径
- 优先复用项目内已有的 `examples/cases/*` 标准脚手架、CLI、workflow、标准 capability 装配协议
- 允许把 `my_project/*` 当作模板、参考实现或兼容层来抽取公共装配模式，但不要把新的完整 case 直接落进去
- 让示例反映正式产品面，而不是写成只在示例里成立的私有捷径

禁止：

- 为了省事，在示例里手写一套绕过正式装配协议的运行入口
- 在 example 中直接拼隐式状态，导致主干能力无法复用/审计
- 让示例和正式框架表面长期分叉
- 把新的完整标准脚手架长期种在 `my_project/`，导致 `my_project` 被案例代码污染
- 在 `examples/cases/<case>/build_solver.py` 里长期堆放 problem、pipeline、adapter、bias、plugin、reporting 的全部装配细节
- **挂羊头卖狗肉：** 示例声称演示组件 X，但 `build_solver.py` 实际未装配 X。`--check` 输出中的 adapter/providers/plugins 必须与 README.md 的组件组合表一致

跨框架规则：

- 如果示例用到 `nsgablack`，`nsgablack` 侧必须采用标准 nsgablack 项目脚手架形态组装外层 solver、adapter、representation、plugin、bias 与 runtime surface。
- 如果示例同时用到 `mlblack`，`mlblack` 侧也必须通过 mlblack 的标准项目脚手架形态暴露 evaluation proxy、inner fitter、artifact builder 与 audit/report surface。
- 跨框架示例只能组合两个正式脚手架 surface，不能绕过任一侧的正式装配边界。
- 过渡期保留的旧 example 必须标注为 compatibility/thin wrapper，新增机制不得继续落在旧 example 文件内。

跨框架 L0 资源边界：

- Project L0 is the authority for resource authorization, lease, fanout limits, worker namespace, and effective `ResourceContext`.
- nsgablack/mlblack standard cases may declare requirements and component intents; they do not directly allocate global resources.
- When nested, child cases must obey the parent-derived `ResourceContext`.
- `nsgablack` 只负责优化搜索语义；不得把 mlblack 内部 trainer/proxy 的业务 backend 细节硬编码进 nsgablack 示例。
- 跨框架项目必须通过正式 scaffold surface 传递 `ResourceContext`，不能在 example/case 文件里私下改写逻辑设备 token、线程数或 inner backend。
- 跨框架运行入口必须在命令行与 summary/runtime_state 中打印“生效后的资源上下文、启用组件、后端与命名空间”，避免出现“配置存在但不可审计”的黑盒状态。

---

## 10) 常用开发命令（Windows PowerShell）

```powershell
# 在项目根目录
Set-Location "C:\Users\hp\Desktop\nsgablack"

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

## 11) 快速接入模板（新增项目）

优先参考：

- `my_project/build_solver.py`
- `my_project/problem/example_problem.py`
- `my_project/pipeline/example_pipeline.py`
- `my_project/plugins/example_plugin.py`
- `examples/cases/*/build_solver.py`
- `examples/cases/*/run_solver.py`

建议路径：

- 若做正式 example/case：先在 `examples/cases/<case>/` 下跑通 `problem + pipeline + solver + observability suite`
- 若做框架模板或用户私有工程孵化：再考虑 `my_project/`
- 完整示例不要反向回灌到 `my_project/`

---

## 12) 结语（给自动化协作 Agent）

- 先读 `core/` 与 `core/state/`，再动 `adapters/plugins`
- 改动前确认不破坏 snapshot 引用策略与 context 契约
- 保持系统可回放（decision trace / checkpoint / module report）

---

## 13) 提交前最小检查清单（建议复制到 PR）

- [ ] 是否保持四层边界（Solver / Adapter / Representation / Plugin）
- [ ] 是否避免大对象直写 context（改为 snapshot + ref）
- [ ] 若改评估链，是否验证单点/批量/插件短路三路径
- [ ] 若改 catalog，是否验证 `default` 与 `framework-core` 双口径
- [ ] 若新增/修改 example 或 demo，是否确认仍走标准脚手架/正式组装路径
- [ ] 若示例声称演示组件 X，`--check` 输出是否确实包含 X（禁止挂羊头卖狗肉）
- [ ] 是否运行 `project doctor --strict --format problem` 并确认无新增错误
