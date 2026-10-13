# AGENTS.md

最后按代码核对：2026-10-13。实现契约见 `docs/architecture/RUNTIME_CONTRACTS_CN.md`；源码与文档冲突必须明确报告。

## 术语与必须保护的语义

- `Problem` 定义评估含义；问题管线处理候选；算法管线构建 `Unit`；Adapter 操作 Unit 作搜索决策。
- `SolutionPool` 先于 Adapter 创建，通过共享 SnapshotStore 保存具名区域中的不可原位改写候选版本；SolutionStamp 使用运行身份与逻辑时钟，SolutionRef 同时标识 token 和版本。读取保留身份，新算法提案显式派生身份并保留父 token/源引用，repair 保留提案 token。Unit 保留算法工作投影和关系，不共享一份可写排名。详见 `docs/architecture/SOLUTION_POOL_CN.md`。
- `Unit` 保留候选本体或候选集合，扩展算法特征、关系与必要状态；构建 Unit 不等于候选编码，取出候选不等于解码。`UnitBinding` 绑定 builder、持久状态 codec 和可选构建 runner；Unit 不拥有 Solver 生命周期或全局授权。
- 种群 Adapter 决定成员选择或槽位替换，PopulationUnit 统一维护 X/F/V/token 与扩展成员字段。新增行字段声明 member_fields，通过只读 on_members_changed(PopulationChange) 返回更新；change 携带对齐的只读 incoming 候选/反馈/token/metadata/provenance。禁止让 Adapter 猜未知字段的维护语义。详见 `docs/architecture/UNIT_MEMBER_OPERATIONS_CN.md`。
- `CandidateBatch` 保留语义值、数值矩阵和 token；数值相等不能替代身份。`ProposalRepair` 表达评估前同一提案被修改；`BatchDisposition` 表达预算/接纳筛选。二者不可互相替代。
- `UnknownState` 是可传输候选；`StateRef` 是 Provider 管理的活状态引用，可寻址范围由 Provider 声明；`DataRef` 是 Artifact 引用，权威交付还须发布收据；Snapshot key 须结合 store scope、版本/摘要和 AuthorityIdentity 验证。
- `PopulationAuthority` 拥有内存种群投影与发布游标；`AuthorityStore` 拥有持久围栏边。Solver 的旧字段是同一对象的视图，不得建立第二份可写副本。
- `RunSession` 拥有运行身份、进度、恢复门闸与结果引用；`RunProgressState` 是可传输的进度值。
- context 参数是一次调用的轻量上下文；ContextStore 是共享存储；context contract 是键与读写声明。进入共享命名空间的键必须注册，局部变量名不自动构成契约。
- `individual_id/individual` 只属于当前调用；build_context 不从旧共享值继承，也不自动回写这两个键，避免新提案绑定到上一代语义身份。
- ML Capability 使用共享 Plugin 生命周期；观察、建议、决定、否决按 ParticipationContract 的作用域区分。
- Doctor 检查声明和受支持的结构/运行面，不能证明任意 Python 副作用、算法正确性或数学性质，必须结合行为测试。

## 0) 这份文档怎么用（给协作 Agent）

这是一份“面向改动执行”的协作说明，不是概念介绍。
阅读顺序建议：

1. 先看 `1/2/4`（定位 + 架构 + 生命周期）
2. 再看 `5/6/7`（数据协议 + API 契约 + catalog 口径）
3. 最后按 `10/13` 跑命令与提交检查

新增协作硬规则：

- **在任何代码改动、测试执行、benchmark 运行、批量脚本落地之前，必须先得到用户明确允许**
- 在未获允许前，只允许做：代码阅读、结果分析、机制讨论、方案草案、文档整理
- 不得因为“已经判断出根因”或“只差最后一步”而直接落代码
- 若用户只是在讨论机制、诊断病因、比较路线，默认仍视为**未授权改代码**
- 同一任务中用户已明确授权完善或修复的工作，许可持续有效；无需对必要的小步修改和验证重复索取许可。

文档语言规则（新增）：

- 教程与介绍类文档默认以**中文**为主版本（尤其 `docs/standard_scaffold_tutorial`）。
- 英文版本允许保留，但必须另起独立文件（如 `*_EN.md`），不得覆盖中文主文档。
- 若新增章节，先补中文主文档，再按需要补英文版。

---

## 1) 项目定位（第一原则）

`nsgablack` 是**多目标优化工程框架**，不是单一算法库。
理解与装配的主线是 **Problem → Pipeline → Unit → Adapter → Bias → Plugin**。这是职责关系，不是六个组件依次执行的线性流程：

- `Problem`：定义求值含义、原始目标和约束。
- `Pipeline`：问题管线处理候选及编解码；算法管线通过 `UnitBinding` 构造算法结构。
- `Unit`：保存节点、标签、种群、区域等算法结构及其操作；不持有全局资源授权或运行循环。
- `Adapter`：拥有搜索决策与 Unit，提出候选、对账修复、消费反馈；组合须路由到原提案所有者。
- `Bias`：产生可审计的选择偏好，保留原始求值；软化选择视图不能修改硬可行性接纳。
- `Plugin`：按声明角色参与评估、检查点、观察和发布等生命周期能力。

`Solver` 是上述组件的控制与装配门面。状态由 PopulationAuthority / RunSession 等所属对象管理；共享事务、证据状态机、Plugin 生命周期、Project 编排和 L0 授权由 BlackBase 提供。旧“四层”称呼仅概括扩展面，不能作为遗漏 Problem、Unit、Bias 或共享底座的理由。

协作规则：

- 不把算法策略硬塞进 `SolverBase`
- 不把运行时能力（日志、恢复、审计）硬塞进 `Adapter`
- 不把业务策略硬塞进 `repair`

### 1.1 统一框架栈规则（blackbase + nsgablack + mlblack）

`blackbase`、`nsgablack` 和 `mlblack` 构成统一框架栈。新增组件、模型族、provider、runtime、示例或跨框架能力前，必须判断三者职责边界。

统一分工：

- `nsgablack` 和 `mlblack` 共享统一的 Project / Case / Scaffold / L0 substrate。编排属于 substrate，不属于任一语义层的私有能力。
- 所有标准 Case 都可以作为外层或内层；外层 Case 通过 `evaluate()`、stage runner 或 project runner 短路调用内层标准脚手架。
- 所有标准 Case 都可以声明资源需求；只有 Project-level L0 substrate 发放 `ResourceContext` grant。Case-level `runtime/` 只负责 requirement/profile/audit，不直接拥有全局 lease。

- `nsgablack` 负责优化搜索语义：solver lifecycle、candidate search、multi-objective/Pareto、adapter strategy、objective/constraint optimization。
- `mlblack` 负责 ML 语义组件、DataView、Spec、Codec、Head、Problem、Trainer、Provider、Artifact、backend capability。
- 外部 domain backend（数值求解器、仿真器、数据库、向量索引、对象存储、Ray/K8s/云服务）只能通过正式 bridge/provider/runtime surface 接入，不应污染两边核心职责。

新增能力前必须先分类：

- 属于共享 `blackbase orchestration`：阶段、并行、多 Case、嵌套调用与资源授权；outer search、Pareto 和优化接纳属于 `nsgablack`。
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

共享生命周期由 `blackbase.plugin.PluginBase/PluginManager` 拥有。`nsgablack.plugins.base.Plugin` 添加优化辅助接口，mlblack Capability 参与同一生命周期；不要在任一语义仓重造调度器。正式 hooks 包括：

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
- `RepresentationPipeline` 是问题候选处理门面；算法结构构建通过独立 `UnitBinding`。不能在 Unit builder 内偷偷 repair 候选。
- 大对象统一进 `SnapshotStore`，`ContextStore` 保持轻量引用

### 2.3 目录职责（高频入口）

- `core/`：求解器主干与运行语义
- `adapters/`：算法策略（NSGA2/3、SPEA2、MOEAD、VNS、SA、DE、TR、A*、MAS 等）
- `plugins/`：能力层（runtime/evaluation/system/ops/storage/domain_backends）
- `representation/`：表示组件与 pipeline
- `bias/`：偏置系统（algorithmic/domain/surrogate + facade/manager）
- `core/state/`：优化状态、PopulationAuthority、RunSession、incumbent 与共享协议入口；通用存储实现在 `blackbase.context`。
- `core/state/solution_pool.py`：运行内候选区域、逻辑时间、输入游标与 manifest；`adapters/pool_search.py`：优化准备/停滞恢复/返回竞争策略，不重造 Project 并行执行或 L0 授权。
- `blackbase.resources`：共享 L0、Artifact、lease、transport；`blackbase.runtime`：参与者、事务、权威登记与结果发布契约。
- `core/evidence_semantics.py`：优化证据只读检查；通用状态机由 BlackBase EvaluationEvidenceCoordinator 拥有。
- `core/semantic_extension.py`：显式步骤扩展；提交后投影失败必须保留提交结果与计数。
- `units/`：算法结构、构建请求、绑定与显式恢复 codec。
- `adapters/proposal_repair.py`：评估前修复证据与复合提案索引映射；`core/evaluation_acceptance.py`：评估后的准入策略。
- `catalog/`：可发现性索引与 profile/filter 规则
- `project/doctor*`：项目规则检查与健康诊断

---

## 3) 运行数据流（改逻辑前必读）

标准步骤尝试：

初始化、变异、修复和控制面候选绑定接入 Solver 自带 SolutionPool。池按引用交换候选，Adapter 按自己的 Unit 建立结构；不把其他 Adapter 的 Unit 当候选解码。

1. Adapter 操作 Unit，通过 `propose(...)` 投影候选；控制面建立 CandidateBatch/token/provenance。
2. 预算限制评估行数。问题管线 repair 后，控制面生成 `ProposalRepair`，调用 `adapter.on_proposal_repair(...)`，成功后才能开始评估。
3. Problem 或声明的 Evaluation Provider 求值；Bias 生成选择视图，同时保留 raw feedback。
4. 持久化 Evaluation Event；接纳策略输出 BatchDisposition，与预算截断组合为一次最终处置，通知 Adapter 对齐待更新结构。
5. `adapter.update(...)` 只接收被接纳的候选和对应反馈；按权威模式暂存 population/partitions。
6. 只有 committed 才发布新 Authority Snapshot、推进逻辑步数并通知提交钩子；失败路径恢复事务参与者，已发生的评估和预算消耗保留。

池 accepted 记录与同一 Authority Snapshot 的 manifest 引用一起提交；失败/零接纳不发布新解。部分接纳按原提案索引结算池输入游标，未接纳的初始化种子保留。池内 raw feedback 不自动替代接收算法的重新评估与 Bias 投影。私有草稿在尝试结束后退出池索引，物理 Snapshot 回收由共享存储负责。

关键点：

- mutate/mutate_batch 只生成提案，不隐含 repair；默认提案阶段的问题 repair 在预算裁剪后执行一次。显式 JointRepairPolicy 可按 max_rounds 协调多轮 ProblemRepair/UnitRepair，每轮验证最终版本。propose 不重复手工 repair；初始化与 update 内新状态是独立阶段。repair 错误必须传播。
- get_proposal_contexts 按原始提案行返回局部上下文，复合层须沿 ranges/局部处置/StrategyTask 路由，不得把所有子提案改用顶层 context。
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
- 通用 context key 由 `blackbase.context` 定义，优化 key 由 `nsgablack.context_keys` 定义（`core/state/context_keys.py` 为语义入口），ML key 由 `mlblack.context_keys` 定义。Project/Case 自定义键在本地 `context_keys.json` 注册；`metrics.*` 也须声明。Doctor 与标准运行入口使用同一作用域注册表，禁止让 Case 私有声明泄漏到其他 Case。

### 5.2 推荐读写优先级

- 读取服从声明的 authority mode；权威读取失败时禁止静默改读其他副本。持久数据验证 Snapshot identity，内存投影访问所属 Authority。
- 写回优先：adapter `set_population*` -> solver `write_population_snapshot()`
- 契约声明：通过 `context_contracts` 标注 `requires/provides/mutates/cache`

---

## 6) 核心 API 契约（新增/改造必须满足）

### 6.1 Adapter API（必备）

- `propose(self, solver, context) -> Sequence[np.ndarray | UnknownState]`
- `update(self, solver, candidates, feedback: OptimizationFeedbackBatch, context) -> None`
- `on_proposal_repair(self, solver, repair: ProposalRepair, context) -> None`：评估前验证/重建；证据包含 before/after CandidateBatch、稳定 token、原提案索引及完整 proposed_count。无改变也可能收到通知，预算未评估行不在证据内。
- `on_proposal_disposition(self, solver, disposition: BatchDisposition, context) -> None`：评估与接纳后按最终索引筛选 pending 状态；不能拿这一步代替 repair 对账。

repair 不改变行数、维度或 token。Adapter 必须处理数值变化和语义 metadata 变化；复合 Adapter 根据原 proposal ranges 及本地选择映射转发，不能广播，也不能提前压缩 pending。hook 返回即表示允许评估；不能恢复不变量时抛错，整个步骤回滚，不调用 Problem/Provider。默认允许无结构约束的普通提案替换；结构所有者不允许替换而又未实现对账时直接拒绝。

A*/MOA* 默认 `repair_policy="reject"`，显式 `recompute` 重算父边代价，update 对修复后候选重建 h 和支配关系；领域仍须保证边可重新解释。CandidateProposerAdapter 保留 Unit ID 重建候选 Unit。TrustRegion 的 repair 须留在当前采样区域：DFO/MO/nonsmooth 使用 box 的无穷范数，subspace 同时检查子空间与坐标半径。不得把候选变化当作只需要重新绑定 token。

候选进入控制面后使用 `CandidateBatch` 同时保留 `semantic_states`、`numeric_matrix`
和 candidate token/provenance：数值算法消费矩阵，Representation / Problem / 结果对齐消费
语义状态。Solver 持有跨代权威 CandidateBatch population；拥有内部环境选择的 Adapter
必须返回与选中行对齐的 candidate tokens，不得按数值相等反推语义状态。`feedback` 的正式形态为 `OptimizationFeedbackBatch`；它仍可解包为
`(objectives, violations)` 供纯数值 Adapter 使用，但不得再定义另一套拆分参数签名。

建议实现：

- `get_state()/set_state()`：checkpoint 恢复
- `snapshot_step_state()/restore_step_state()`：步骤事务回滚；快照必须返回 `Mapping[str, Any]`，捕获过程只读。默认可复用脱离后的
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

多策略组合的正式调用输入是 `StrategyTask.from_context(context)`。角色、实例路径、阶段、区域、种子和原始提案预算由该任务统一生成；repair/disposition/update 必须绑定原任务，不得用全局观测覆盖。接纳结果由 BatchDisposition 表达，不能改写 task.budget。`StrategyOrigin.from_candidate(state)` 读取随 CandidateBatch/token 保存的嵌套来源路径。`unit_tasks` 是按路径组织的轻量摘要，`strategy_instances` 是各子实例观测；二者不得反向成为调度依据。重复角色名和同一可变 Adapter 对象占用多个实例必须在装配时拒绝。

`AuthorityRegistry.register()` 登记每个事实时，所有者必须实现 `RuntimeParticipant`，或显式提供非空 `rollback_exempt_reason`。RunSession 的尝试次数、耗时和已消耗预算不随步骤回滚，结果走独立发布事务，因此显式豁免且禁止注册为步骤参与者。Mapping 校验只保证快照外层结构；内部可变值的脱离与 codec 安全由组件负责。

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

评估决定须声明 `ParticipationContract(decides=("evaluation",))`；严格发布校验须声明 `vetoes=("finalization",)`。Controller 的决定须属于其 `owns_domains`。角色检查不是任意 Python 代码的沙箱。

常见入口：

- `prepare_restore/on_solver_init/on_population_init/on_step_attempt_start/on_generation_start/on_step/on_generation_committed/on_generation_end/on_step_attempt_end/on_solver_finish/on_solver_finalization_prepare/on_solver_finalized`

能力边界：

- 插件增强“能力”，不重写算法语义
- 接管评估时必须保证返回 shape 与类型合法
- 可选观察/日志后端可按声明记录 soft-error；求值、原始约束、权威快照和严格发布失败必须传播，不能以“外部资源”为由降级成成功。

### 6.3 Representation API（候选解管线）

组件必须通过 `blackbase.representation.RepresentationCapabilities` **只声明实际支持的操作**；不存在全部组件必须实现的统一五方法接口。角色与方法族对应如下：

- 编码角色 `CandidateCodec`：`encode` / `decode`。
- 搜索角色 `SearchOperator`：`init` / `mutate`。
- 约束修复角色 `ConstraintRepair`：`repair`；可声明批量扩展 `repair_batch`，但同时必须支持 `repair`。

上述 Protocol 描述完整角色接口；仅提供角色中的部分操作时，按实际操作声明能力，不得声称满足整个 Protocol。`RepresentationPipeline` 是装配门面。框架不再根据 initializer/_initializer/decoder 标记猜测能力，ML bridge 也无需伪装未支持的方法。确定性、幂等性须显式声明并验证，不统一强加。

需要 Unit 数据的叶变异组件声明 `unit_inputs=UnitInputSpec(...)` 并实现 `mutate(candidate, context, *, unit)`。Adapter 经自身 `mutate_candidate(control, candidate, context)` 提供候选副本与只读 UnitInputs，不从共享 context 猜所有者。消费者声明 uses_pipeline_mutation；Doctor 用 unit-operator-contract-invalid 检查签名和可检查的字段依赖，不执行特征计算。普通算子仍只接收候选/context；通用 kernel wrapper 不会自动转发 Unit 输入。完整执行与迁移约定见 `docs/architecture/UNIT_OPERATOR_INPUTS_CN.md`。

多个 Adapter 可以共享一份问题 Pipeline。不同搜索需求使用 `RepresentationPipeline(mutation_operators={...})` 注册具名算子，实际消费者通过 `set_mutation_operator(name)` 选择；未指定使用默认 mutator。选择不修改共享默认项，不按 Adapter 类型猜测，不自动广播到子 Adapter。UnitBinding 仍独立负责结构构建；禁止为了算子差异复制完整问题管线。共享算子对象也共享其状态，需隔离时显式创建不同实例。

ProblemRepair 修问题约束；UnitRepair 修算法结构，也可改候选。JointRepairPolicy 显式开启严格共同验收，要求问题组件提供只读 validate；UnitRepair 绑定有 algorithm_unit/UnitBinding 的实际叶所有者，只改 codec 草稿。最终版本须共同通过，对账后再次验证 Unit；不能由最后执行的 repair 宣布成功。循环/次数耗尽回滚后由根 Adapter.on_joint_repair_rejected 决策。组合通过 proposal_repair_children 共享索引/任务映射，不可广播或静默丢行。详见 `docs/architecture/JOINT_REPAIR_CN.md`。

共同验收仅允许送评。默认 ProblemRepair 与共同修复均在修复前捕获活跃所有者及组合祖先的局部参与者快照；零接纳恢复该子树，再通知普通 disposition。部分接纳先由 Adapter disposition 整理坐标，再调用 UnitRepair.project_admission 并重验；baseline 保留原始 Unit，draft 已整理，evidence/disposition 仍是原始索引，不得重复裁剪。投影必须保留 admission_unit_fields 声明的字段。评估成本不回滚，不重跑 repair，也不猜测任意结构的裁剪。

失败证据包含稳定 owner 路径、局部/根索引和 token。on_rejection 默认 stop，retry/advance 必须显式选择。advance 先规划所有失败路径，再在独立决策事务中整组推进；异常/取消整组恢复，不能计为逻辑提交。串行退出阶段的 teardown 延后到决定生效后，失败进入可恢复清理队列，成功后不得在最终 teardown 重复清理。多轮修复与拒绝决策复用 Case cancellation/deadline，不新增资源授权者。

约束：

- 输入输出可序列化
- shape 稳定
- `repair` 只做约束兜底，不承担业务策略搜索

### 6.4 Bias API（软引导）

- Bias 通常在求值反馈边界形成选择偏好；可只依赖候选，也可显式读取参考 Unit。candidate/unit/transition 等比较范围是可选工具，不要求每个 Bias 都实现。正式说明见 `docs/architecture/UNIT_PREFERENCE_CONTRACT_CN.md`。
- UnitFeature 明确声明数据字段依赖及 none/raw/selection 反馈视图；派生缓存按 Unit 实例隔离，不进入 checkpoint，读取时按依赖内容校验。历史/路径/动量等算法状态仍须显式保存，不能当缓存丢弃。特征函数只消费声明数据，不递归调用特征，也不能隐藏决策或求值。
- 轨迹/区域候选关联分数通过 Unit.candidate_feedback 保存值、依赖和内容版本；候选改变后旧分数不再参与比较。历史度量不能冒充当前候选反馈。trajectory/poll/parameters/local_region 的 Unit schema 为 v2，旧 v1 不自动恢复或重新求值；详见 UNIT_FEATURES_CN.md。
- 候选改动后须先完成问题管线处理，再消费相关特征；NSGA-II 与 MOEA/D 的 pipeline 变异给搜索算子传独立父代副本。PopulationUnit 分别追踪 objectives/violations 的候选版本，只更新一个字段不能使另一个旧字段生效，部分更新状态须保留到 codec。完整求值使用 attach_feedback；成员替换使用 replace_evaluated_rows 同步候选、反馈和 token。DE/MOEA/D 已接入；选择与比较入口拒绝过期反馈。这不是对任意 Python 写入或反馈真实性的证明。
- UnitView/PopulationView 是带 owner_path、unit_id、schema、revision 的脱离只读依赖；同类型多实例按路径绑定。准备态成员可无 token，只按已知相同 token 排除自身，不能按数值相等猜身份。
- PopulationView 允许同一候选 token 占据多个槽位，不能为区分槽位编造候选身份。UnitPreferenceBias 的 owner_path 指定参考 Unit，apply_to_paths 可按正式 StrategyOrigin 路径限定候选范围；默认全局，限定时无来源不适用、损坏来源传播。整体/变化偏好由 Adapter 显式消费。Unit、Bias 均不能自行获得全局调度或搜索决定权。
- TabuSearchBias 评分只读，记忆定义为已提交步骤中接纳的提案；BiasModule 在 Adapter.update 后暂存更新，并参与步骤回滚和 checkpoint。单独 evaluate 不更新该记忆。其他历史语义必须显式声明。
- stateful_preference 组件必须提供显式状态 codec 并禁用旧标量缓存；Unit 偏好依赖错误必须传播。不要假定新契约已经迁移所有旧 Bias 的隐式状态。

- 偏置负责“软引导”而非“硬约束替代”
- 新 Bias 可实现 PreferenceProvider，返回声明键的 PreferenceDelta(key, delta, reason)。硬约束键不能通过偏好接口改写。
- 必须保留原始评估。OptimizationFeedbackBatch.raw_objectives/raw_violations 是原始视图；objectives/violations 是选择视图。
- ignore_constraint_violation_when_bias 只改变选择视图，禁止擦除 raw_evaluation；Case 文档必须说明这种约束软化。
- `FeasibleEvaluationAcceptance` 只读取 `raw_violations`：有限且不超过容差才接纳，处置声明 `constraint_view="raw_evaluation"`。需要按选择偏好准入时另写显式命名策略，不得偷换“可行”的含义。

### 6.5 Solver/Control Plane 关键 API 速查

- `store_solutions / read_solutions / propose_solutions`：登记版本、按引用读取、显式生成带源身份的新提案；`solution_pool.select(at=stamp, region=..., stage=...)` 锁定候选来源时点。context 仅传 pool manifest/time/input ID/mode。
- `pool_input_modes` / `supports_pool_restart` / `restart_search`：Adapter 显式声明池初始化、竞争、搜索重启。不得因实现 Unit 就推断已支持任意交接；PoolSearchAdapter 的接收方须支持 initialize/compete，producer 的重启不重放生命周期。

- `register_state_participant(...)`：接入共享 RuntimeParticipant 事务，不遍历任意对象图。
- `register_semantic_extension(...)`：提交前扩展和提交后投影；后者失败不得伪装成未提交。
- `finalization_hooks = FinalizationHooks(...)`：注册结果准备、暂存、冻结、中止；事务型三钩子必须完整。
- `run_session.submit_restore(...)`：统一恢复入口；扩展层不得私自维护恢复顺序标志。

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
- `config.py` 与各组件的 `config.py`：可声明、可复现的装配配置；不强制额外 config/ 目录
- `build_solver.py` / `run_solver.py`：正式组装入口与运行入口
- `plugins/` / `bias/` / `reporting/`：按能力边界落位
- `registry` / `catalog`：需要被发现的正式组件必须可索引

示例文件本身只能是薄入口、兼容层或教学调用层。真实装配逻辑必须进入上述标准项目结构，而不是堆在 `examples/.../*.py` 里。

公共装配实现由 `nsgablack.project.case_support` 提供；通用图导出由 `blackbase.project.graph_export` 提供。Case 保留显式薄导出、本地工厂与参数。可变 builder 注册表必须每 Case 独立，不能用共享模块级字典替代本地注册。生成模板默认可运行；`add-component` 生成自定义骨架，不按名称自动选择内置组件。

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
- 在 `examples/cases/<project>/cases/<case>/build_solver.py` 里长期堆放 problem、pipeline、adapter、bias、plugin、reporting 的全部实现
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

# Unit/repair/Bias/接纳边界改动
pytest tests\test_proposal_repair.py tests\test_bias_acceptance_boundary.py tests\test_evaluation_acceptance.py tests\test_adapter_step_transactions.py -q

# Unit 成员、联合修复、部分接纳、Provider 清理与恢复组合
pytest tests\test_unit_member_composition.py tests\test_population_member_operations.py tests\test_checkpoint_resume_plugin.py -q

# Unit 成员只读输入、Bias 候选范围、MOEA/D 重复槽位与 SA 基准
pytest tests\test_unit_scope_and_member_inputs.py tests\test_unit_preferences.py tests\test_sa_adapter.py -q

# 解池时间、候选身份、200→100×2、部分接纳与正式 checkpoint
pytest tests\test_solution_pool.py tests\test_pool_search_adapter.py -q

# 仓库体检（严格，包含所发现 Case；显式开启主干 Catalog 审计）
python -m nsgablack project doctor --path . --strict --catalog-audit --profile framework-core --format json

# 对实际改动的 Project/Case 单独执行装配检查（会执行 builder，不执行 run/fit）
python -m nsgablack project doctor --path examples/cases/algorithm_units --strict --build --format json

# Catalog（主干口径）
python -m nsgablack catalog list --profile framework-core --kind adapter
python -m nsgablack catalog search nsga2 --profile framework-core --limit 20

# Catalog（完整口径对照）
python -m nsgablack catalog list --profile default --kind example
python -m nsgablack catalog list --profile framework-core --kind example
```

---

Doctor 的 `--format problem` 仅改变呈现，不筛选级别；未知位置不填 `1:1`。
提交检查必须审阅 coverage 中的 scope/skipped；根目录检查未开启 `--build` 不代表装配检查通过。
非 strict 默认仅 error 阻断，`--fail-on warn` 可单独提高失败阈值。详见 `docs/project/DOCTOR_CN.md`。

## 11) 快速接入模板（新增项目）

优先参考实际产品面：

- `docs/standard_scaffold_tutorial/01_create_and_run.md`：生成并运行 Project/Case。
- `project/scaffold/case_template_solver/`、`project/starter.py`：可运行起步模板；ML 起步由 mlblack.project.starter 提供。
- `project/case_support/`：公共装配实现；Case 绑定自己的工厂与参数，不复制完整框架工具。
- `examples/cases/algorithm_units/cases/`：Unit 构建与搜索示例。
- `examples/cases/catalog_recipes/cases/`：正式 Adapter 装配示例。
- 示例入口形状为 `examples/cases/<project>/cases/<case>/build_solver.py` 和同目录 run_solver.py。

建议路径：

- 若做正式 example/case：先在 `examples/cases/<project>/cases/<case>/` 下跑通问题定义、管线、Unit/Adapter、控制面与必要能力
- 若做框架模板或用户私有工程孵化：再考虑 `my_project/`
- 完整示例不要反向回灌到 `my_project/`

---

## 12) 结语（给自动化协作 Agent）

- 先读 `core/` 与 `core/state/`，再动 `adapters/plugins`
- 改动前确认不破坏 snapshot 引用策略与 context 契约
- 保持系统可回放（decision trace / checkpoint / module report）

---

## 13) 提交前最小检查清单（建议复制到 PR）

- [ ] 是否保持 Problem / Pipeline / Unit / Adapter / Bias / Plugin 职责与共享底座边界
- [ ] 若改候选管线，是否验证 repair 通知、原提案索引/metadata、Unit 重建或拒绝、复合路由及失败回滚
- [ ] 若改解池/交接，是否验证时点截止、私有可见性、源 token/版本、部分接纳游标、manifest 与 Authority 同步发布，以及正式 checkpoint 恢复
- [ ] 若改 Bias/接纳，是否验证选择软化不能绕过 raw 可行性门，以及证据 Snapshot 与准入结果一致
- [ ] 是否避免大对象直写 context（改为 snapshot + ref）
- [ ] 若改评估链，是否验证单点/批量/插件短路三路径
- [ ] 若改 catalog，是否验证 `default` 与 `framework-core` 双口径
- [ ] 若新增/修改 example 或 demo，是否确认仍走标准脚手架/正式组装路径
- [ ] 若示例声称演示组件 X，`--check` 输出是否确实包含 X（禁止挂羊头卖狗肉）
- [ ] 是否运行 Doctor 严格检查，记录 scope/coverage/skipped，并区分既有发现与新增回归
- [ ] 是否对受影响的 Project/Case 执行必要的 `--build`，以及显式选择 Catalog 审计口径
