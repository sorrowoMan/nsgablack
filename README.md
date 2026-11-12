# NSGABlack

`nsgablack` 是统一框架栈中的优化与搜索语义层。它面向的不是“调用一个算法”，而是把候选表示、目标与约束、搜索策略、运行能力和结果证据装配成可组合、可恢复、可审计的求解系统。

第一次了解项目，建议先读[框架整体介绍与毕业设计研究方向](docs/research/FRAMEWORK_OVERVIEW_CN.md)，
再看[可运行 Pool Project](examples/cases/pool_workflow_pilot/README.md)。
整体介绍说明了 Problem、Pipeline、Pool、Unit、Adapter、Bias、Plugin 的分工，
也列出了已有案例、已执行验证和仍需研究的部分。当前为开发快照，验证范围不代表所有组件均已完成验收。

当前开发版本：`0.4.1`，依赖 `blackbase>=0.3.27,<0.4.0`。本轮共享编排接口已进入本机源码，尚未发布包。

VNS / MOEA-D 现在可直接传 `change=普通函数`，在 Project 中编排完整的变化操作，
不用继承或手写状态包装。母池种子、按需 Unit、真实运行与待完善的 Pool 操作见
[普通函数试作](docs/architecture/POOL_WORKFLOW_PILOT_CN.md)及其标准 Project。
同步 BO、CMA-ES 和 MAP-Elites 的组件装配、语义验收与标准 Project 见
[三种算法语义示例](examples/cases/algorithm_semantics/README.md)。三者分别保留观测、完整分布批次和格子档案的语义，明确区分原始求值与模型/偏好分数。

Catalog 现可按“贝叶斯引导”“替换采集函数”“种群扩展字段”等用途查找，分别查看组件职责、运行操作、装配参数和支持边界；本地网页、声明方式与验证记录见 [当前架构的 Catalog](docs/architecture/CATALOG_USAGE_CN.md)。

完整变化现可从母池/具名子池取解，自行组合操作顺序，并声明接纳后输出集合；
装配及事务语义见[池驱动变化编排](docs/architecture/POOL_CHANGE_ORCHESTRATION_CN.md)。
集合进一步支持过滤、显式排序、交差与分组，普通函数可用 PoolEdit 维护精英池成员；
见 [Pool 集合操作](docs/architecture/POOL_COLLECTION_OPERATIONS_CN.md)。

NSGA-II/III、SPEA2 现支持普通 change 一次交回多个独立后代，以及 `choose(Pool) -> Pool` 生存选择。
GA、VNS、MOEA/D 可在本批反馈后用普通函数维护池成员，沿用同一提交事务。
GA 的选择函数还可返回 `members, {"elite": elite, "reserve": remaining}`，将 Unit 主成员和普通副集合一起提交；
副集合不存在时创建，存在时精确替换，可直接从最终生存成员中挑精英。
精英可作为下一代父代或交给 VNS 精修；历史档案维护另有同次 request.members 输入，
与旧档案归并后通过 replace_members(create=True) 发布，无需重复选择或求值。
三个具体用途及边界见 [用途说明](docs/architecture/POOL_DATA_MODEL_AND_OPERATIONS_CN.md#185-已落地的三个用途繁殖精修与历史档案)。
`partition(pool, by=choose)` 按当前输入位置一次拆出选中与未选中部分，保留重复引用和原选择坐标。
完整装配、三个基础 Case 与 100 个成员的种群拆分示例见 [Pool Project](examples/cases/pool_workflow_pilot/README.md)，
具体接口见 [Pool 手册](docs/architecture/POOL_API_REFERENCE_CN.md)。

Pool 手册第 0 节现提供 `source.chosen(rule)`、`Pool(parent=..., name=...)` 与 `target.inject(source, replace=True)` 的真实用法。
可在生存选择和成员档案回调中直接声明精英池，沿用原身份与提交事务；GA→VNS 仍由现有 Router 装配。
multi/serial 现可通过 `working_pool="workspace"` 指定普通工作区域；子任务省略来源时继承最近绑定，
接纳候选进入最近区域，继续共享同一池存储与事务。实际区域需先创建，详见 Pool 手册 0.5。

`SearchPlanAdapter` 现支持 `repeat(times=100, body=serial(stage("ga", steps=100), stage("vns", steps=30)))`，
不必手算全局 step；同一算法跨阶段保留状态，池精修可等待本轮任务完成再返回竞争。
具体输入绑定、停滞条件与恢复边界见[自然搜索编排](docs/architecture/NATURAL_SEARCH_PLANS_CN.md)，
实际 GA→VNS→GA 交接见[标准 Project](examples/cases/assembled_ga_vns/PLAN_CN.md)。

搜索操作现按初始化、变化、选择、结构修复四类由实际 Adapter 装配。NSGA、DE、MOEA/D、SA、VNS 等保留各自的比较与执行语义，图搜索、信赖域和梯度算法保留必要的结构操作；不支持的绑定明确拒绝。具体支持、只读 Unit 输入和恢复约束见 [Adapter 行为装配边界](docs/architecture/ADAPTER_OPERATION_BOUNDARIES_CN.md)，精英池父代范例见 [局部装配说明](docs/architecture/ADAPTER_OPERATOR_BINDINGS_CN.md)。

运行内候选现在由具名、带逻辑时间的 SolutionPool 存放，算法使用候选构建自己的 Unit。正式 PoolSearchAdapter 支持“单解算法准备候选 → 两个独立种群搜索 → 停滞唤醒单解算法 → 返回竞争”；可显式启用 PoolRetentionPolicy 回收长期无人使用的解，同时保护活 Unit、待处理输入和指定历史发布。装配、身份与恢复窗口见 [解池中文契约](docs/architecture/SOLUTION_POOL_CN.md)，可运行入口见 [标准示例](examples/cases/solution_pool/README.md)。

本轮把 population 与运行状态分别归入 PopulationAuthority / RunSession，统一步骤事务并声明表示、插件参与和最终发布接口；偏好投影保留原始评估证据。自定义组件需要按 [迁移说明](docs/project/RUNTIME_CONTRACT_MIGRATION_CN.md) 更新，具体行为与验证范围见 [运行契约](docs/architecture/RUNTIME_CONTRACTS_CN.md)。

0.4.0 将算法型 population 写入收口到 Adapter/Evaluation transaction；旧 Elite Plugin
保留到 1.0.0 的弃用装配桥。升级步骤见
[`docs/project/MIGRATION_0_4.md`](docs/project/MIGRATION_0_4.md)。

本版的正式超级拓扑示例改用 BlackBase Project DAG：基线 Solver/Trainer 是并行就绪
节点，外层 Solver 由权威 Artifact 依赖自动唤醒；外层候选继续动态调用 MLBlack
Trainer，Trainer 再调用内层 Solver。静态 DAG 与动态 Case 调用树因此在同一 L0、预算、
lineage 和 Artifact 协议下组合，而不把编排下沉到 Adapter。

本版将 Pareto 结果改为 token 对齐的语义投影：`UnknownState` metadata、candidate token、
目标与约束反馈从权威 `CandidateBatch` 一起交付，不再按数值近似相等反查身份。
checkpoint 升级为 v9，保存同一份语义 Pareto 证据；最终 checkpoint 则在 teardown 前冻结、
teardown 后与 Case Artifact 进入共享 finalization transaction。

本版要求 Evaluation Evidence 的终态携带经过 Snapshot 实读比对的验证回执；暂时不可读
的 Event 或 authority 不再被恢复器误判为 abandoned。SnapshotStore 与 Evidence Journal
只能在未运行、未发布状态时成对原子切换。每次 Adapter post-commit cleanup report 还会
写入独立 Snapshot 并在 Context 留下正式引用，成功清理证据也不再只存在于进程内字段。

本版修正周期 checkpoint 的逻辑恢复游标，保存频率与 resume cursor 都以已提交的
`RunProgressState.steps_completed` 为准。正常 Evaluation Evidence 结算与恢复路径现已
共用同一组 Snapshot 可读性和处置一致性验证；SnapshotStore 与 Evidence Journal 只能
成对替换，避免证据索引跨后端分裂。Adapter post-commit cleanup report 还会保存 Provider
精确 state ID 回执，缺失或错位的 release evidence 会保留为可重试债务。

本版把运行级 Plugin 也纳入精确 receipt：初始化失败只清理已经启动的参与者，错误
观察器失败不会覆盖主异常，finish/finalized 会独立扇出。Evaluation Event、最终
`BatchDisposition` 与 authority Snapshot 现在通过版本化处置信封形成显式证据边；
拒绝/失败写独立记录，提交处置与新权威 Snapshot 同记录。Gradient Adapter checkpoint
还会保留 host/cluster 可寻址的 Provider 清理债务，并在恢复后的下一次提交或 teardown
使用当前 L0 grant 继续释放。

Event、Disposition 和 Authority 之间还新增了共享证据日志。Solver 在 Event 快照写入前
登记 `preparing`，落盘后进入 `pending`，处置发布前进入 `deciding`；只有目标快照可读时
才结算终态。checkpoint 恢复会按同一 run ID 对账：已落盘的处置幂等补结算，没有确定
裁决的 Event 则归档为 `abandoned`，不会擅自重跑 Problem、接纳策略或 Adapter。

## 三仓边界

- `blackbase`：Project / Stage / Case / Scaffold、L0 资源授权、Context / Snapshot / Artifact 引用、跨 Case 调用与公共协议。
- `nsgablack`：Solver 生命周期、CandidateBatch、Representation、Adapter、Bias、Plugin、目标/约束、Pareto 与求解结果。
- `mlblack`：DataView、Spec、Codec、Head、LearningProblem、Evaluation Provider、模型 Artifact 与 ML 报告。

编排和资源授权只属于共享底座。优化 Adapter 不申请 GPU，也不硬编码 Torch、CUDA 或模型训练逻辑；Problem / Evaluation Provider 根据 L0 发放的 `ResourceContext` 执行求值。

## 核心闭环

```text
Representation 产生语义候选与数值视图，登记到 SolutionPool
    -> Adapter 从池取得候选，Unit 维护算法结构
    -> Adapter.propose()
    -> 问题 repair / Unit 对账
    -> Problem / Evaluation Provider 求值
    -> OptimizationFeedbackBatch
    -> Adapter.update()
    -> Solver 同步发布池 manifest、authority snapshot、incumbent 和审计
```

四个主要扩展面：

- `Solver`：唯一控制平面，管理生命周期、评估入口、状态和插件钩子。
- `Adapter`：组织搜索行为与 Unit，`propose/update` 是控制面调用的门面。
- `RepresentationPipeline`：候选的 init / mutate / repair / encode / decode。
- `Plugin`：checkpoint、trace、报告、评估短路和运行治理等能力。

算法操作结构通过 **Unit** 显式声明：Adapter 持有运行实例，按需调用装配的 UnitBinding／builder 构建；问题管线继续负责候选表示与可行性处理。未启用的 Adapter 不提前创建工作 Unit，已有结构由同一所有者继续维护。
节点、种群、邻域、参考方向、探针和参数槽位可以独立定制，并通过绑定的 codec 恢复。
装配同时校验结构、构建操作和必要工厂方法；builder 可显式声明兼容的基础结构契约，供多个 Adapter 复用。
装配方式、各 Adapter 的结构及兼容性变化见[算法 Unit 中文说明](docs/guides/ALGORITHM_UNITS_CN.md)。

`CandidateBatch` 同时保存 `semantic_states`、`numeric_matrix` 与 candidate token/provenance。数值算法消费矩阵；Representation、Problem、结果绑定和恢复消费语义状态。框架不再通过“数值相等”反推候选身份。

复合 Adapter 不再把多个子群体强行拼成一个虚假的 population。透明包装器委托当前子 Adapter；多策略、角色路由和事件组合器通过稳定 partition ID 发布 `PopulationPartition`。同一真实候选可以进入多个槽位，保留同一候选 token 与对应的精确池版本；分区和槽位表达成员关系，不为区分槽位另造候选身份。checkpoint 保存 partition、反馈和 token，Solver 只在外层确实完成融合选择时接受单一权威 population。

步骤提交采用显式两阶段边界：评估期间的 Evaluation Event 使用独立 Snapshot key；权威 Population Snapshot 只在 `StepOutcome.committed` 后从内存 staging 发布，拒绝或失败不会覆盖上一份权威快照。Adapter 的 semantic state 随 Solver 提交，`commit_step_state()` 只负责 post-commit cleanup；所有参与者都会执行，失败形成 `AdapterCommitReport` 并进入运行证据。事务型最终结果在 teardown 后先经过 `on_solver_finalization_prepare` 严格校验，再原子提交；`on_solver_finalized` 与 `save_on_finish` checkpoint 只观察已经权威化的最终结果。

恢复生命周期固定为 `prepare -> setup -> Plugin.prepare_restore -> apply restore envelope -> ordinary init hooks -> initialize if fresh -> run`。外部预加载、插件自动恢复和 `set_state()` 都进入同一恢复通道，普通初始化钩子只能观察恢复后的状态。每次执行尝试返回 `StepOutcome`：`on_step_attempt_start/end` 对所有物理尝试成对触发；`on_generation_start/end` 及 `on_step/on_generation_committed` 只属于真正提交的逻辑代。`max_steps` 限制已提交逻辑步，`max_step_attempts` 单独防止持续 idle/rejected；累计耗时和逻辑 deadline 由可恢复的 `RunProgressState` 统一记录。

生命周期尾钩子采用独立清理聚合：一个严格 Plugin/Controller 的结束通知失败不会阻止其他已启动参与者收到对应 end。RuntimeController 与各 Controller 进入正式 checkpoint component，StopController 的 patience 状态可恢复。Adapter 的步骤回滚只消费显式 `snapshot_step_state()/restore_step_state()`，不再深拷贝任意 Python 对象内部。复合 Adapter 必须通过 `step_transaction_children()` 声明独立状态参与者，成功时由 `commit_step_state()` 清理尝试期资源；Provider-backed Adapter 依赖 copy-on-write slot，回滚只释放本次尝试创建的 `StateRef` 并恢复旧引用，提交只回收前驱 slot。

Population Snapshot 使用 `nsgablack.population_snapshot/v2`。`single/step_batch` 同时区分权威 `(X, F, V)` 与独立的 `last_evaluation_event`；`partitioned` 只保存稳定分区和独立的 `last_evaluated_batch` 事件证据。checkpoint v10 保存版本化的完整评估事件信封和 population `AuthorityIdentity`，包括 `CandidateBatch` 语义 metadata、`OptimizationFeedbackBatch.items`、candidate token/provenance、Pareto 语义身份与 run/attempt identity；恢复时先收敛未决的 Journal 证据，再复用精确匹配的 durable Authority edge，冲突则失败关闭。旧 checkpoint 迁移时只标记为 `semantic_complete=false`，不会伪造语义 lineage。接纳策略收到评估后的计数、事件 best 摘要与 snapshot ref；零接纳不会清空旧权威状态，部分接纳也不会裁掉完整评估证据。

## 标准项目

```text
project/
  project_config.py
  run_project.py
  README.md
  cases/
    case_a/
      .case
      README.md
      build_solver.py
      run_solver.py
      config.py
      problem/
      pipeline/
      adapter/
      bias/
      plugins/
      evaluation/
      runtime/
      solver/
```

- Project 负责跨 Case 的串行、并行、嵌套和资源授权。
- Case 是独立运行和被父 Case 调用的统一组合单元。
- `build_solver.py` 是唯一规范装配入口。
- `build_trainer.py` 如存在，只能是 `build_solver` 的薄别名。
- 每个 Project 和 Case 只维护一个 `README.md`，不再复制 `START_HERE`、注册指南或契约模板。

## 快速开始

```powershell
python -m pip install -e .[dev]
python -m nsgablack project new demo_project
Set-Location demo_project
python -m nsgablack project add-case demo_case --type solver
python -m nsgablack project doctor --path . --build --strict
python run_project.py
```

查看组件：

```powershell
python -m nsgablack catalog search nsga2 --profile framework-core
python -m nsgablack catalog list --kind adapter --profile framework-core
python -m nsgablack catalog show adapter.nsga2 --profile framework-core
```

`default` Catalog 包含示例和文档；架构审计必须显式使用 `framework-core`。

## 状态与大对象

- ContextStore 只保存轻量状态、版本和引用。
- population、objectives、history、trace 和大型 incumbent 进入 SnapshotStore。
- 可跨 Case、跨进程或长期保存的模型与数据先由 Artifact provider 发布，再传递 `DataRef`。
- `UnknownState` 是可传输语义状态；`StateRef` 是 Provider 持有的进程内活状态，不能伪装成持久 Artifact。

## 文档

- [文档入口](docs/README.md)
- [标准脚手架教程](docs/standard_scaffold_tutorial/README.md)
- [架构边界](docs/architecture/README.md)
- [用户指南](docs/user_guide/README.md)
- [组件导读](docs/guides/README.md)
- [示例项目](examples/cases/README.md)
- [当前白皮书草稿](docs/whitepaper/README.md)

历史设计和已删除接口以 Git 历史为准，不作为现行使用说明。
