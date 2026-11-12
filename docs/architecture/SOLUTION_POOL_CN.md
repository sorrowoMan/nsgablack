# 解池、运行时间与算法结构

核心规则的压缩试写见 [Pool 的 9 条候选不变量](POOL_INVARIANTS_CN.md)。该稿区分可推导语义、算法前提与当前执行政策；它是讨论稿，不替代本文的正式支持范围。

最后按代码核对：2026-10-20（本次补充变化函数的只读访问、输入范围与接纳后交付）。实现：`core/state/solution_pool.py`、`adapters/pool_tasks.py`。本文是当前运行契约；全 Adapter 覆盖与接入要求见 [池与 Adapter 接入契约](SOLUTION_POOL_ADAPTER_READINESS_CN.md)。更广的编排讨论见 [增量 Unit 编排讨论](ORCHESTRATION_WITH_INCREMENTAL_UNITS_DISCUSSION_CN.md)。

VNS/MOEA-D 完整 change 现在可使用调用内只读 `request.pool` 选择、抽样、合并候选引用，
通过 `ChangeResult`/`PoolOutput` 声明接纳后普通集合输出。任务内额外来源须声明
`change_sources`（精确公开子池名）或 `change_allow_main`；默认保留原任务输入边界。
输出与原始反馈、池 manifest、步骤事务统一提交，不能绕过算法最终比较或直接改其结果视图。
冻结时点、目标 revision、身份与旧 checkpoint 迁移见[池驱动变化编排](POOL_CHANGE_ORCHESTRATION_CN.md)。

只读集合查询与精确成员替换/移除/裁剪已补齐，普通函数通过 PoolEdit 返回计划，不直接改写共享池。
保持 view_id，成员实际改变才推进 revision，复用输入声明、步骤事务与 checkpoint；详细 API 与一轮精英池例子见
[Pool 集合操作](POOL_COLLECTION_OPERATIONS_CN.md)。

## 1. 解先有存放位置，再由算法使用

母池先于 Adapter 的运行初始化与候选操作建立，Adapter 配置对象可以先构造。MOEA/D 的 setup 不再创建或求值候选，首次派发后才通过正式提案流程建立起始种群；下游须等待 pool_views_ready，不依赖固定第一步或 setup 已有方向。

解池是一次运行中存放候选的具名区域。它记录候选语义、数值视图、身份、来源和运行时间。Adapter 从中取得候选，用自己的 Unit 组织成员、当前点、路径、邻域、区域等关系，再提出新候选。Unit 构建不等于编码；池读取不等于解码。

最小分工是：

- Problem 定义原始求值和问题约束；问题 Pipeline 处理候选。
- SolutionPool 通过共享 SnapshotStore 保存候选版本，不负责排名、温度、支配关系或调度。
- Unit 保存本算法的工作投影、成员关系、派生特征和必要状态。
- Adapter 决定从池中使用哪些解、如何搜索、何时接纳到自己的结构。
- Bias 形成当前算法的选择偏好；Plugin 提供评估、恢复、观察等运行能力。

框架不需要 NSGA-II→SA、SA→MOEA/D 等逐对转换器。接收算法取得候选后按自己已有的规则建立或更新结构。两个种群可以引用同一候选来源而拥有不同成员顺序、排名和参考方向。

池是共享候选版本的所有者；PopulationAuthority 仍拥有**当前算法投影与发布游标**。二者不争夺同一个可写矩阵：池版本不可原位改写，Unit 的工作数组按已有成员操作和步骤事务更新。当前内置 Unit 保留数值数组以便高效运算，还没有全部迁移成只存 SolutionRef 的结构。

### 1.1 私有阶段合批与读取边界（2026-10-30）

同步提案、步骤内批量初始化和问题修复，先使用 CandidateBatch 已脱离且不可原位改写的调用内值，
在本调用的数量、形状验收完成后、正式评估之前，按阶段合批写入原 SolutionPool。
例如 200 个候选各经历 mutation_parent、mutation、repair_input、repair，仍保留四个阶段及各行 token/来源，
但可写成四个批次，而非 800 个单行快照。repair 保持提案 token，阶段版本与来源不按数值相等合并。
sequence 仍按实际池记录写入递增，不要求每个候选各占一个逻辑序号。

这不是公开值缓存，也不延迟正式接纳或 Event/Authority 的持久核验。调用内值不能充当持久读取收据；
跨调用读取仍实读并核验完整 SnapshotIdentity。队列只在所属 Solver 的同步线程内有效，
即使 copy_context 传到另一线程也不共享；退出后清空，嵌套失败只丢弃内层新增项。
算子/形状验收失败不刷新该作用域队列，写入失败由原步骤事务回滚，评估不启动。
步骤外的初始化和直接候选调用保持即时登记，避免改变后续初始化器可见的已发布输入。

完整成员交付在一次读取中联合核对候选、raw feedback 与 provenance；每个 backing record 只加载一次，
后续调用仍重新核验。MOEA/D 的全部方向在同一私有索引操作中验证一次完整视图图，失败不留下已发布前缀。
NSGA 家族和 MOEA/D 的步骤局部状态不再重复保存 Unit 已持有的成员矩阵；自定义显式状态协议保留保守路径。
完整 manifest 生成、发布前恢复校验和 Unit codec 仍存在，尚未改为增量持久格式。

验证：`tests/test_candidate_stage_write_batches.py`、`tests/test_pool_unit_work_reuse.py`，
并结合 repair/disposition、成员字段、部分接纳、失败回滚及 checkpoint 恢复测试。

## 2. 时间属于运行，不用墙钟决定可见性

`SolutionStamp` 包含 `run_id / sequence / generation / attempt`。sequence 是池写入的逻辑序号；generation、attempt 是控制面提供的进度注记。直接调用 `step()` 与运行循环的进度计数不同，不能把这些注记解释成额外的运行计数器。

`pool.timestamp` 给出当前运行的逻辑截止点。`pool.select(at=stamp, ...)` 只返回该时点之前**已发布**的记录。旧运行的 stamp、未来时点和越界引用直接失败。不用 `time.time()` 排序，也不以数值相等合并身份。

失败步骤删除其未发布索引与输入消费；sequence 保留高水位，下一次写入不会复用失败尝试的时间。时间有空洞是正常的，不能用 sequence 差值代替候选数或代数。

## 3. 三种不同的身份动作

`SolutionRef(pool_id, record_id, row, candidate_token)` 同时指出候选身份和池内的具体内容版本。池索引还保存 SnapshotIdentity，读取验证 store scope、schema、revision 和内容摘要。

1. **读取已有解**：`solver.read_solutions(refs)` 保留 token、语义 metadata 和 provenance；返回脱离值，修改读出的数组不会改变池记录。
2. **由已有解产生新提案**：`solver.propose_solutions(refs)` 建立新 token，provenance 的 parent_token 指向原 token，`solution_source_ref` 保存完整原池引用。新调用可获得自己的 StrategyOrigin，并独立 repair、评估和接纳。它是提案身份，不是为种群槽位编造身份。
3. **修复同一提案**：repair 保留提案 token、产生新的 record_id；旧版本仍不能被原位覆盖。ProposalRepair 对账依然先于评估，BatchDisposition 仍负责评估后筛选。

因此，同值不同身份、同身份不同修复版本、同来源不同提案可以分别表达。重复种群槽位依旧允许使用同一 token，不靠池替换槽位语义。

## 4. 池公开的是已提交接纳提案

普通候选帮助函数 `init_candidate / init_population / mutate_candidate / repair_candidate` 接入池；控制面绑定 CandidateBatch 时也登记自定义 Adapter 直接产生的候选。

一次步骤中，新候选先是私有记录。`select()` 和普通 `read()` 不能读到这些记录；控制面按明确引用使用 `allow_pending=True`。评估接纳后，只有被接纳的 CandidateBatch 才写入 `stage="accepted"`。

提交顺序为：准备池 manifest → 将它的 SnapshotIdentity 放入目标 Authority Snapshot → 提交既有权威围栏 → 发布池内存索引。失败恢复池、Adapter、Unit 和输入游标；已经执行的评估、预算和 Evaluation Event 保留。恢复持久提交时，按已经验证的目标 Snapshot 中的 manifest 恢复池，不重跑任何算法。

manifest 准备后禁止新增记录或移动输入游标，防止内存索引与目标 Snapshot 分叉。普通零接纳可以保留 Adapter 调度/RNG 状态，因此新建的公开输入选择 ID 仍有效，游标退回未消费位置；异常路径则随 Adapter 整组恢复，删除该次新建选择。

零接纳不新增公开解。部分接纳只发布被接纳的行。`stage="accepted"` 表示步骤中的准入通过，**不表示每个接收算法最终将它保留为种群成员，也不自动证明问题可行**；是否必须可行取决于正式 AcceptancePolicy。可行门始终读 raw_violations。

提交结束时，池索引丢弃本尝试的私有中间记录；最终候选、修复和处置证据仍由既有 Event/Authority Snapshot 留存。启用第 9 节的保留策略后，已知私有草稿与失败尝试产生的池 Snapshot 进入可重试清理队列，实际删除仍使用共享 SnapshotStore 的正式接口。

步骤外显式写入的初始化记录可按 `stage="initial"` 查询。默认 `select()` 查询 accepted，以免后续算法误把未经评估的初始化值当成可交接结果。池不是自动 Pareto 档案，默认不去重、不选最优；历史回收须显式启用保留策略。

## 5. 评估与偏好不从上一个算法照搬

池可以保存对齐的原始目标和违规量，用于审计。它不把上一算法的 selection feedback 当成接收算法的反馈，也不据 token 或数值相等自动复用评估。

PoolSearchAdapter 的初始化和返回竞争都走正常 Problem/Provider、repair、Bias、预算与接纳路径。NSGA-II 和 NSGA-III 分别重新建立自己的选择视图与结构。需要复用原始评估时，应另行声明求值语义、问题版本、上下文和 Provider scope 的等价性；这一轮没有新增自动求值缓存。

Unit 偏好继续通过 UnitView/UnitInputSpec 明确绑定实例路径和数据依赖；池里的解不会携带一份可写排名供所有算法共同修改。

## 6. 用户装配：取解配额和算法容量独立

三种数量分别属于不同职责：

- 解池保存运行中的候选历史，没有统一的 `population_size` 上限。
- `PoolSearchSpec.initial_count` 是这个编排计划为某个算法选择的初始取解数量，不是 Unit 容量。
- NSGA-II/III 的 `population_size` 是各自算法保留成员的容量；其他算法不必拥有这个参数。

`build_solver()` 不要求传入 `config={"population_size": 100}`。各 Adapter 在装配时配置自身参数，编排独立指定取解配额；两个 Unit 可以容量不同。200→100×2 只是此前讨论的一种计划，也可以准备 200 个候选，A 取 120 个并选留 100 个，B 取 80 个并保留 80 个：

在标准 Case 的 `adapter/` 工厂中装配：

```python
from nsgablack.adapters import (
    NSGA2Adapter, NSGA3Adapter, SimulatedAnnealingAdapter,
    PoolSearchAdapter, PoolSearchSpec,
)

adapter = PoolSearchAdapter(
    producer=SimulatedAnnealingAdapter(name="seed_sa", batch_size=199),
    searches=[
        PoolSearchSpec(NSGA2Adapter(name="population_a", population_size=100), initial_count=120),
        PoolSearchSpec(NSGA3Adapter(name="population_b", population_size=80), initial_count=80),
    ],
    stagnation_steps=20,
    recovery_steps=5,
)
```

`build_solver.py` 把这个 Adapter 与问题和 Pipeline 装到 ComposableSolver 中即可；池由 Solver 先创建，用户无需装第二套存储。脚手架提供可选 `adapter/pool_example.py` 工厂，默认起步算法不会被自动替换。

上述示例流程：

1. `preparing`：只启动 producer 搜索；已接纳提案进入池，累计数量达到 200 后切换阶段。SA 先评估 1 个基准点，下一次可提出 199 个邻居；“200 个”是已接纳提案数，不是 200 个不同数值，也不承诺固定两步完成。
2. `search`：锁定 ready_stamp，按池记录顺序分配前 120 和后 80 个引用。分配不重叠；两个算法分别送评，A 按自己的环境选择保留 100 个成员，B 保留 80 个。之后 producer 保持等待、温度不下降，两种群各自搜索。
3. `recovery`：观测到停滞后显式重启 producer，从池中选择一个种子、重置搜索温度，保留本地 RNG 流；不重放 setup/Plugin 生命周期。仅 producer 搜索指定的已提交步骤数。
4. `return`：锁定本次恢复后发布的候选，分别提交给两个种群参与正常环境选择；不直接覆盖整个种群。随后回到 search。

默认停滞指标是 `min(sum(raw_objectives) + 1e6 * raw_violation)`；这是一项明确的标量策略，**不是局部最优证明**。多目标、目标量纲不同或追求多样性时，用具名 `metric(feedback)` 显式替换。默认恢复种子是该组合最近发布的一个候选；需要精英、多样性或区域选择时提供 `recovery_selector(pool, stamp)`，当前单解恢复要求恰好一个引用。

`recovery_steps` 包括重启后的基准评估提交。未接纳或预算未覆盖的初始化种子保留在输入选择中，下次继续送评；即使种群已满，剩余输入仍可参与成员选择。初始取解超过容量时，NSGA-II/III 在首次安装成员前选择一次，并保持反馈、token、metadata、provenance 对齐；取解少于容量时先建立较小种群，之后由普通后代搜索逐步扩充，不偷偷补充池输入。其他算法按自身结构与输入契约处理，不能据此推断都能从较少种子启动。若准入条件长期无法满足，依旧需要 max_step_attempts/deadline 保护。

这个 PoolSearchAdapter 的准备触发阈值是各 `initial_count` 之和，它是一项具体编排策略，不是池的存储上限。producer 的批次可以超过阈值，多出来的公开候选仍留在池中。后来搜索和恢复还会继续向池发布候选；后代批次大小也由各算法自己决定。

同一组合中可变 Adapter 实例和 name 均不可重复。嵌套调用按正式 StrategyTask 路径识别本组合的池候选；父级不能用全局 context 重新绑定子提案。

正式示例：`examples/cases/solution_pool/cases/pool_search/`。默认准备 8 个候选，A 取 6 个并保留 4 个，B 取 2 个并在后续搜索中扩充到 3 个。脚手架工厂支持显式传入 `producer` 和 `searches`，不使用一个全局大小控制全部算法；完整 200/100/100 流程仍由行为测试覆盖。

## 7. 输入游标与接纳

`pool.bind_input(refs)` 生成轻量 selection ID；context 只携带 `solution_input_ref` 和 `solution_input_mode`。Adapter 通过 `init_candidate / init_population` 消费选择，不把整个候选矩阵放入 context。

PoolSearchAdapter 在提出候选前后记录消费数量，最终 BatchDisposition 按原提案索引结算输入。未接纳的种子保留在该选择的剩余区；一个子提案批次不混合“池输入”和“新生成候选”，避免无法确定游标对账含义。消费失败不随机补种子。

输入被允许进入搜索与候选是否成为最终成员是两件事：initialize/compete 模式都按正式准入消费输入，由 Adapter 自己决定最终成员。已经通过准入但在环境选择中落选的候选不作为未消费种子重试，仍保留在池的已接纳历史中。池不修改成员决策。

## 8. 恢复、存储和可检查范围

池提供 Mapping 步骤快照和显式可传输 checkpoint codec；快照只有索引、refs、游标和发布身份，不复制 SnapshotStore、锁或 Provider。

checkpoint 中的候选值按显式 CandidateBatch codec 搬运到目标 SnapshotStore，新物理 key/scope 不冒充旧物理引用。logical SolutionRef 保留，恢复每条值时核对原内容摘要。PoolSearchAdapter 要求 checkpoint 中必须有 solution_pool component，不能在宽松恢复模式下丢失其输入状态。

正式恢复先应用池组件并在目标存储创建 manifest，再恢复发布算法 Authority Snapshot，然后应用其余组件；同一池只恢复一次。读取必需池状态失败时，即便 checkpoint 配置非 strict 也不得遗漏它。

共享 context 只增加四个正式轻量键：`solution_pool_ref / solution_pool_time / solution_input_ref / solution_input_mode`。Doctor 检查池存储是否与 Solver 相同、是否登记步骤参与者、候选事实 owner 是否一致，以及 Adapter 的输入/重启声明。启用保留策略时还检查显式活引用声明，缺失报告 `solution-pool-retention-contract-invalid`；不执行搜索或扫描任意对象图证明算法正确性。

支持范围：公共候选控制面池化；NSGA-II/III 声明初始化和竞争输入，SA 声明单解初始化与显式重启。其他 Adapter 自行声明并实现所需模式后才能进入这个特定组合，不能因有 Unit 就推断已支持。种群算法的“两边推进”是同一 Solver 步骤中的组合调度，不承诺 CPU 同时运行；实际并行与多 Case L0 仍由 BlackBase 管理。

## 9. 长期无人使用的解如何释放空间

### 9.1 用户只需显式选择保留策略

在标准 `build_solver.py` 完成装配后、首次池发布前配置：

```python
from nsgablack.core import PoolRetentionPolicy

solver.set_solution_pool_retention(PoolRetentionPolicy(
    idle_steps=20,              # 连续多少个提交步骤没有消费者持有
    retained_publications=2,   # 自动保留最近多少次完整池发布
))
```

框架默认不启用回收，保持已有历史读取行为。两个参数必须是正整数。它们不限制池容量、不限制初始化解数，也不替算法选择成员。初始生成多少解、以后何时随机注入、串行哪些解继续流转、并行分支如何汇合，仍由初始化与编排策略决定。可以通过已有初始化帮助函数和局部调用 context 表达后续注入，不需要给池增加统一大小。

正式示例显式设置 `idle_steps=2 / retained_publications=2`，便于小规模演示回收；实际项目按历史使用需求选择窗口。存储后端必须提供 SnapshotStore 的正式 read_verified/pin/unpin/delete 行为，失败不得伪装为已经释放空间。

### 9.2 算法淘汰成员与池回收是两件事

Adapter 在 `get_solution_pool_roots(control)` 中返回自己仍会使用的全部 SolutionRef；子 Adapter 由 `step_transaction_children()` 显式遍历。控制面按实例路径同步这些引用。相同类型、多实例、同一 token 的重复成员都不会据数值相等合并；仅持 token 的 Unit 可使用 `pool.refs_for_tokens(tokens)` 保守保留该 token 的所有已接纳版本。

NSGA-II/III 声明当前成员 token，SA 在自身 Unit metadata/codec 保存当前解 token，PoolSearchAdapter 声明待分配或待返回的来源候选。未消费输入引用自动受保护。未知 Adapter 的默认返回 None，启用策略立即失败；明确没有本地引用才返回空序列。继承组件新增历史、精英或待提交候选时，也必须扩展本地声明，框架不会猜未知字段。

其他消费者使用自己的名字显式持有和释放：

```python
pool.retain("orchestration:future_stage", refs)
# 更新需要的引用时，再次 retain 会替换该消费者的引用集合。
pool.release("orchestration:future_stage")
```

`adapter/` 是控制面专用命名空间。若 A、B 同时引用 x，A 淘汰 x 仅解除 A 的关系，B 的持有仍保留 x。释放全部持有后，x 进入闲置宽限期；新消费者在到期前重新持有即可延续寿命。保存在任意 Python 变量中的 refs 不自动成为强引用；未来确实需要重读必须 retain。来源 provenance 是身份审计信息，不默认要求旧候选值永久可读。

### 9.3 闲置时间按提交步数计算

每个提交步骤在 Adapter.update 后、登记持久提交意图前，同步活引用并暂存一次保留更新。仍被消费者持有的行刷新最后使用步数；连续闲置达到 idle_steps 的行退出当前查询索引。只读日志、select/read 不刷新寿命。失败、拒绝、取消不推进闲置时钟；行、消费者引用、输入游标与时钟一起回滚，已经消耗的评估和预算照旧保留。

未消费输入保护其候选；已消费前缀从输入保留集合移除，exhausted selection ID 仍可查询。这样不会因为一个旧 selection ID 存在而永远保留其全部历史值。

同一批次中仅部分候选闲置时，池写入新的压缩 Snapshot，只保存存活候选和对齐的 metadata、provenance、原始反馈。存活引用的 record_id、原始 row 与 token 均不变；原始 row=50 可以对应压缩值矩阵的第 0 行，调用者不需要重新编号。过期行读取明确失败，不返回另一行或偷偷生成新解。

### 9.4 历史恢复窗口与长期固定引用

退出当前索引与删除物理 Snapshot 分开进行。最近 retained_publications 次发布保留 manifest 及其候选值闭包。若某历史发布需要保留更久，显式固定整组引用：

```python
saved = pool.pin_publication("analysis_checkpoint")
# pool.restore_publication(saved) 可重读固定版本。
pool.unpin_publication("analysis_checkpoint", saved)
```

不同发布即使使用相同 owner，也拥有独立 lease，解除一个不会解除另一个共享候选的保护。pin/unpin 在步骤外使用，且必须与池身份相符。它们是本地后端 lease，不随跨存储 checkpoint 搬运；pin 的 I/O 失败须传播，使用相同 owner/identity 重试。

**启用回收后，窗口之外且未固定的旧池 manifest 可失效。** 旧 Authority Snapshot 即使还存在，也不保证其指向的池历史永久可读。需要长期保留该恢复根，应固定池发布，或使用携带完整候选值的正式可传输 checkpoint。checkpoint 包含它所捕获的全部当前池值，即使源存储随后清理，仍能恢复到目标存储；checkpoint 捕获时已经退出当前索引的候选不会被补回。

未决持久提交使用内部临时 lease 保护已准备 manifest 和候选值闭包。围栏确认丢失或 destination 暂时不可读时，回滚后的清理不能删掉恢复所需值；只按持久证据恢复并确认进入已提交索引后，才释放该 lease。保留更新或 manifest 准备失败发生在登记提交意图之前，可以正常回滚并清理孤儿快照。

### 9.5 实际删除在提交之后

RuntimeParticipant 的 commit cleanup 使用共享 SnapshotStore.delete 删除已失去所有保护的池快照；不删除其他组件的 Evaluation Event、Authority Snapshot 或 Artifact。删除前验证 scope/schema/摘要和 pool_id，仍 pinned 的快照继续等待。

清理异常留下队列，在后续提交或显式 `pool.collect_garbage()` 时重试；函数报告 deleted/deferred/errors，步骤结果中的 runtime_commit_report 保存清理证据。清理失败不能把已经提交的算法步骤改判为未提交。读取抛错时保守保留；read 返回 None 按正式后端契约表示不存在。失败步骤的已知新快照也进入队列，但回滚过程不执行物理删除。

这是明确引用与窗口下的存储回收，不是任意 Python 引用追踪或内存泄漏证明；底层存储释放不保证进程 RSS 立刻下降。算法私有历史、Context/Snapshot 的其他数据和外部 Provider 活状态仍由其所属组件负责。当前行为测试覆盖 memory/file 后端；Redis 等后端及长期规模性能另需验收。

## 10. 子池与现有多角色调度

### 10.1 子池是引用集合

子池给已有候选划出一个具名区域，不创建另一份候选数组或另一套存储。一个精确 SolutionRef 可同时属于多个子池，各算法通过该引用建立自己的 Unit。子池成员关系复用池的 retention owner，因此随既有索引、步骤事务和可传输 checkpoint 保存；不增加新的权威对象。

```python
pool = solver.solution_pool
refs = pool.select(at=pool.timestamp, stage="accepted", limit=20)
pool.create_subpool("local_inputs", refs)
same_refs = pool.select(subpool="local_inputs")
pool.add_to_subpool("local_inputs", more_refs)
pool.drop_subpool("local_inputs")
```

`select(subpool=...)` 可继续按 at/stage/source/limit 过滤，保留成员顺序；它直接读取逻辑集合，不再以物理 region 限定。`drop_subpool` 只释放该集合的引用，其他 Unit、子池、历史发布仍然可以持有同一候选。输出子池需由使用方在不再需要时显式释放，否则它仍是回收保护根。

`create_subpool` 只接收已发布来源；`add_to_subpool` 允许将本步骤已通过准入的输出暂存进集合，`subpool_refs` 在同一 Authority 提交前看不到这些输出。失败步骤恢复集合和任务进度；普通零接纳保留新建的来源选择，供下次尝试继续。缺失子池或失效引用不会自动退化成随机初始化。

### 10.2 给角色声明一个取解任务

组合器的 `working_pool` 使用上述普通引用集合，名字必须已存在且已提交。
StrategyRouterAdapter/StrategyChainAdapter 可显式绑定，子组合 None 继承最近上层区域；
池任务省略 select 时从该区域冻结输入，没有绑定时保持根池行为。
本批接纳候选自动归入最近工作区，不自动归入所有祖先，不改变孩子 Unit 的成员关系。
记录进入已有成员计划收集器，和显式输出一起预检后随同一 Authority 提交；同名 replace/append 冲突拒绝。
绑定和原提案描述符由 Adapter 恢复，作用域不改变持久视图的 parent/ancestors，也不复制候选。
具体输入、结果与权限边界见 [接口手册 0.5](POOL_API_REFERENCE_CN.md)。

已有 StrategyRouterAdapter 负责阶段、激活角色、候选预算和反馈路由。新增的任务绑定只描述该角色如何从池取解、何时完成、向哪交付：

```python
from nsgablack.adapters import PoolTaskSpec, RoleSpec, VNSAdapter

def choose_seeds(control, context):
    # 这里可以按已提交结果、区域或自己的指标选择。
    return control.solution_pool.select(stage="accepted", limit=20)

def make_vns(unit_id):
    return VNSAdapter(name=f"vns_{unit_id}", batch_size=4,
                      restart_on_stagnation=False)

local_role = RoleSpec(
    "local", make_vns, n_units=2,
    pool_task=PoolTaskSpec(choose_seeds, count="all", steps=5, output="refined"),
)
```

Router 自动用 PoolTaskAdapter 包装子实例。每个角色的一次 request 只选择和分配一次；每个实例依次处理自己的起点队列。两个角色可以选择同一批 refs，用不同 VNS 参数建立不同 Unit。实例数量表示逻辑搜索状态的数量，不自动等于线程数。

`select` 省略时读取母池 main 区域的全部已发布引用，包括未求值的初始化种子；不读取本次尝试的私有草稿。它也可以是 `select(control, context) -> Sequence[SolutionRef]` 的具名函数，或 Router 作用域内的子池名。子池须在实际取解时已存在，不要求早于其上游生产阶段；不存在立即报错。输出子池仍由任务按声明创建。具名函数的 module/qualname 进入 checkpoint 配置身份；函数行为或外部配置的等价性仍由装配者保证，不支持用匿名 callable 对象冒充稳定身份。

三种模式：

- `refine`：每个起点显式重启接收算法的搜索状态，先消费该来源，再执行普通 propose/update。要求 initialize 能力与 supports_pool_restart。
- `initialize`：选出的引用按既有输入游标交给算法初始化；数量与其 Unit 容量独立。
- `compete`：送入现有种群的正常成员竞争，不直接覆盖成员。

取多少由 `count` 控制，正整数表示每实例数量，`"all"` 表示完整来源集合。省略时 initialize 使用 Adapter 的 `default_pool_input_count()` 声明，NSGA-II/III 返回自身 population_size，SA/VNS 返回 1；refine 默认一个起点，compete 默认全部。初始化取解数量仍可独立覆盖，比如容量 100 的算法可以 count=120，经环境选择保留 100 个。第三方 Adapter 不声明默认量时须显式 count，不能靠扫描 cfg 字段或类名猜测。

分配由 `distribution` 控制：

- `independent`：每实例分别无放回抽样，允许不同实例使用同一来源；initialize 默认采用此规则。
- `partition`：整组选出最多 count × 实例数条不同引用，再均分；count="all" 时分摊整个集合。refine/compete 默认采用此规则。
- `shared`：选出同一组引用，交给每个实例。适合不同 VNS 配置从同一起点比较。

`shuffle=True` 默认随机取解和分配；`shuffle=False` 保留母池/子池/selector 的返回顺序，需要先精修排名靠前的起点时可用。去重仅针对完全相同的 SolutionRef；同值但不同 token，或同 token 的不同版本，不按数值合并。每个算法仍按原提案身份规则产生新提案，不能为槽位编造来源身份。分配 RNG 为包装实例私有，随步骤回滚和 checkpoint 保存。

例如，30 个 GA 群体各需 100 个来源，只需默认初始化装配：

```python
RoleSpec("ga", ga_factory, n_units=30,
         pool_task=PoolTaskSpec(mode="initialize"))
```

若 ga_factory 返回 population_size=100 的 NSGA-II，母池只有 300 个不同候选也能分配：每群内部取得 100 个不同来源，群间允许重叠。3000 个成员位置不要求 3000 个不同源候选。各群拥有独立 Unit，淘汰与变异不修改别群或池中的旧版本。若要求群间互不重叠，设置 distribution="partition"，此时需要 3000 条不同来源引用。

VNS 的默认 PoolTaskSpec() 则为每个实例分配一个起点；显式 count="all" 可将 20 个起点排成队列，交给 4 个实例各处理 5 个，仍然是各自一个当前点。设置 distribution="shared", count=1，可让 4 个实例从同一个来源出发。优质起点排序仍由明确的 selector/比较规则决定，默认取解不暗含“全局最优”或“局部最优已证明”。

候选不足时 `on_insufficient="error"` 默认报出所需数量和实际数量；`"wait"` 在现有调度/尝试预算内等待，不消费分配 RNG；`"available"` 使用现有不同来源，空池则等待。后者需接收算法能处理较小初始批次，NSGA-II/III 已支持。缺失命名子池无论哪种策略都报错。框架不重复引用凑数，也不暗中调用 initializer 补解；补解由已有初始化或生产阶段决定。同一角色各实例的默认取解数量必须一致；不同容量需显式统一 count 或拆成不同角色。

`steps` 只用于 refine，是每个起点的接纳更新数，包含起点基准求值；`steps=2` 即基准加一批邻域。零接纳不推进任务，失败回滚进度，已经发生的评估成本仍计入全局预算。它不是时间上限、总求值次数，也不会绕开 Solver deadline/预算。VNS 的基准通过正常 repair/评估/Bias/准入之后，才允许用它与后续邻域比较。

VNS 的起点拒绝与停滞重启遵守以下边界（2026-10-29）：

- 普通内部 initializer 生成的未评分起点，只有在本次 Evaluation Event 与该提案的准确 token 对齐、确认已经送评却零接纳后，才允许在下一次提案重新初始化。预算未覆盖、兄弟提案取消和旧事件不触发重抽，不制造已提交步骤或虚构分数；同一任务先前已评估的 selector 结果仍须保留。
- 显式池输入、手工给定点、warm start，以及未声明起点来源的旧 checkpoint，保留其原起点重试；不能用随机候选代替调用方冻结的输入。长期不满足接纳条件时，由尝试次数、求值预算或 deadline 终止。
- 停滞触发的重启推迟到下一次 `propose`。触发当步仍保留已评估的当前点与准确引用，任务若恰在此步完成，交回这个结果；不能交回尚未评分的重启点。待重启标记随步骤事务和 checkpoint 保存，下一次提案只初始化一次。

推迟重启会改变 initializer 相对于步骤间共享 RNG 钩子的执行时点，因此不承诺与旧版本在这类交错下逐位一致；同一新版本的恢复和回滚必须保持自己的随机流与待重启状态一致。该调整不改变问题求值、硬接纳或原始反馈。

`output` 收集任务期间送评且被准入的候选，包括起点和没有胜过当前点的试探解。需要精英集合时，由后续选择函数明确筛选，不能把整个结果子池叫作“全部精修最优解”。结果保留自身 token、来源引用与真实原始反馈，不改变源 x 的分数来冒充 y 的结果。

SA/VNS 的当前点持久保存来源记录；Unit 投影和变异草稿复制通过控制面重新绑定该记录，复制本身不生成新身份。真正变异才派生新 token，parent_token 指向当前点，solution_source_ref 保留原始池来源。多实例反馈先按候选的实际绑定取记录，不能把子批次第 0 行当作根批次第 0 行。池任务要求根 Adapter 与池组件均成功恢复；配置不匹配或子状态恢复失败必须传播，即使 checkpoint 插件没有开启全局 strict。

### 10.3 阶段与返回竞争

```python
ga_role = RoleSpec(
    "ga", ga_adapter,
    pool_task=PoolTaskSpec("refined", mode="compete", phases=("return",)),
)
```

`phase_roles` 决定何时调度角色，`phase_policy` 决定当前阶段。任务的 phases 为空时对该角色所有已调度阶段生效；指定阶段之外，未开始/已完成任务的角色正常执行原算法，未完成任务暂停，避免把它当作不相关搜索继续改写。

phase_policy 的局部输入新增 `pool_tasks`，按 `role:unit_id` 提供 request/status/next/count/steps/output 小摘要。它不把候选数组存入共享 context。可以在所有精修实例 done 后进入 return，在种群输入消费完后回到 search。停滞触发仍由既有策略根据指标决定，并不证明局部最优。

默认请求 key 为阶段名，同一 key 完成后不重复启动。需要周期性精修时，`request_key(control, context)` 返回每次触发的新稳定字符串，例如策略维护的触发序号；任务未完成时不被新 key 替换。回调在恢复后应对同一请求产生相同 key，不使用墙钟生成每次不同的 key。

initialize/compete 输入消费完成后，后续调度继续原算法的 propose/update，不每步重抽成员。initialize 未声明 request_key 时只初始化一次，阶段切换也不重新取解；需要再次输入时显式声明新的 request_key。refine 队列完成后等待后续请求或调度到其他角色。

子池名自动位于 Router 路径/名称作用域下，例如 `refinement/refined`；嵌套 Router 加入父 StrategyTask 路径。输入选择、当前结果、尚未消费来源均受保留策略保护。角色原有数值 seeds 对 pool_task 关闭，正式引用是唯一任务输入来源；没有 pool_task 的历史角色仍保留原有调用方式。

返回候选依旧经过接收方正常求值与 Bias 投影；源算法的选择分数不自动复用。原始反馈查询 `pool.read_raw_feedback(refs)` 可供选择函数使用，但本身不代表已满足接收方的评估等价条件。

`pool.read_raw_feedback_info(refs, allow_pending=False)` 按输入的精确引用顺序返回逐行原始反馈信息，包含重复引用；没有保存信息的历史记录返回空 Mapping。`put(..., feedback=...)` 将每项 `Feedback.info` 的脱离、可序列化值保存在同一候选 Snapshot 的 `raw_feedback.info` 中，不建立第二份索引或可写权威。步骤回滚、checkpoint、保留与行压缩沿用原 Snapshot 机制，读取返回脱离值，不能反向改写池内记录。

该入口适合保存子 Case 的 ArtifactBinding、运行身份、预算结算等轻量证据。排程矩阵、模型和数据集应发布为 Artifact，不能因有 info 字段就复制进每项反馈。反馈信息不能替代发布收据验证，也不能按数值相等、局部行号或同 token 的最新版本反推最终结果。实际用法见供应调整 Project 的 `JointSupplyCase` 与 `test_solution_pool_feedback_info.py`。

### 10.4 支持范围与可运行入口

SA/VNS 支持普通逐起点 refine；NSGA-II/III 支持 initialize/compete；MOEA/D 支持返回 compete，并自动发布方向投影子池，由 VNS 消费（见下一节）。其他算法必须先声明并实现对应池输入及投影能力；声明本身不能代替实现。

同一个 Case 内的这种精修使用已有 Router、PoolTaskSpec 和子 Adapter，不要求额外写一套子 Case。跨 Case 生命周期、并行和 L0 授权仍使用 BlackBase 的标准入口。

正式例子：`examples/cases/solution_pool/cases/pool_refinement/`。它先建立 20 成员种群，再以两类四实例 VNS 分别精修 20 个起点，返回 NSGA-II 竞争并恢复普通搜索。装配策略在 `adapter/refinement.py`，Problem/Pipeline/运行入口仍按标准脚手架组织。

### 10.5 MOEA/D 自动方向投影与来源选择

MOEA/D 初始化完成后，每个实际方向自动创建一个子池。100 个方向就是 100 个子池，与外部 VNS 实例数无关。每个子池引用当前槽位候选，并保存 `created_by`、`slot`、`projection`：

- `created_by`：当前 Solver 中 Adapter 的稳定所有权路径。装配时传入具体实例；同类型、同名的两个实例仍有不同路径。它标识谁创建这个视图，与候选最早由 GA 还是 VNS 生成无关。
- `slot`：创建者的方向索引。不同槽位可以引用同一候选，仍然是不同任务，不按 token 或数值跨方向去重。
- `projection`：分解方法、权重、参考点。当前支持与内置 MOEA/D 一致的 weighted_sum 和 tchebycheff；后者使用创建者当时的 ideal point。

用户只需选择方向并绑定现有池任务，以下是装配片段：

```python
from nsgablack.adapters import MOEADAdapter, PoolTaskSpec, RoleSpec, subpools

adapter1 = MOEADAdapter(name="adapter1", population_size=100)
selection = subpools.all(adapter1)          # 该实例创建的全部已发布方向
selection = subpools.random(20, adapter1)   # 或无放回选择其中 20 个方向

producer = RoleSpec("moead", adapter1,
    pool_task=PoolTaskSpec("refined", mode="compete", phases=("return",)))
local = RoleSpec("local", vns_factory, n_units=4,
    pool_task=PoolTaskSpec(selection, steps=3, output="refined"))
```

把这两个角色装进同一个 Router；`vns_factory(index)` 返回一个独立 VNSAdapter。阶段触发由原有 phase_policy/phase_roles 决定。选择器传入未装配的实例、非投影生产者或不支持投影的消费者，装配检查会报错，不会按名字寻找替代者。嵌套组合仍按实际实例路径查找。

`random(20, adapter1)` 的 20 是整个角色请求选中的方向数。默认 partition 将这 20 个任务分给四个 VNS，每个处理五个方向；不会四个实例各抽 20 个。`count` 另外表示每个选中方向取几个起点，默认 1。shared 表示每个实例显式重复所有选中任务；independent 在这种选择中拒绝，避免与角色级抽样混淆。方向不足默认报错，可使用已有 on_insufficient=wait/available；不会有放回补足。没有已发布方向时同样遵循不足策略。

一次请求在开始时冻结所选方向、候选版本和投影参数。起点通过正常 Problem 求值建立基准；随后所有邻域候选仍经过正常 repair、Problem/Provider、Bias 和准入，再由任务投影反馈交给 VNS。VNS 以同一标量坐标比较起点与邻域，不能中途因 MOEA/D ideal point 改变而混用两套分数。新请求才获取新的方向视图；同阶段重复触发需改变 request_key。

投影处理的是接收链当前的 selection objectives，使它与 MOEA/D 的分解比较一致；约束选择值保持原样，采用 MOEA/D 的可行性优先规则。硬准入仍在此前消费 raw constraints。无 Bias 时投影也显式保留 raw_evaluation；有 Bias 时沿用原始证据。母池与 Evaluation Event 始终保存原目标向量，不把方向标量冒充 Problem 的结果。

精修输出仍是候选引用集合。返回时 MOEA/D 正常重评、更新 ideal，并按当前权重和 `nr` 替换上限竞争槽位，可能改善多个方向；创建来源不承诺只替换原槽位。框架不把“精修 x 得到 y”解释成 x 的分数等于 y，也不把精修承诺成一定改善。具名 output 聚合子池收集已接纳提案；投影任务另外发布每个起点的最终选择视图，供下一层精修，见 §10.6。

绕过 Solver 手工调用 MOEA/D.update 的调用者，同样须先建立候选对应的已发布或已接纳池记录；未知 token 不能用于发布方向。旧控制面曾为重复槽位派生 population_slot_alias，这不再是合法的新身份来源；包含这类别名但缺少对应池记录的历史 checkpoint 需要显式迁移，不能在恢复时按数值猜原身份。旧版要求全局唯一 token 的快照消费者也需同步升级。

方向成员和元数据与池 manifest 一起 staging/提交；更新中的方向不会进入已发布选择列表，失败恢复旧视图。已选任务持有自己的冻结副本与输入引用，不受后续方向替换或回收影响。任务队列、投影、RNG、VNS 基准与所有权路径共同 checkpoint；恢复不重抽、不重跑评估。普通子池保持原来的无投影视图行为。

100 个子池是 100 份轻量引用及比较参数，不是 100 份候选数组，也不意味着同时创建 100 个 VNS 或取得 100 份资源。VNS 数量由 n_units 决定，Case/Project 资源规则保持原职责。

完整标准 Case：`examples/cases/solution_pool/cases/moead_refinement/`，演示 MOEA/D 与 GA 搜索、四个 VNS 消费 MOEA/D 的 20 个方向、返回竞争。`view_count=None` 切换为全部方向。

### 10.6 递归派生视图：MOEA/D → VNS → VNS

投影精修任务每个起点完成时会发布一个派生视图，output=None 也可交付最终选择；显式 output 额外聚合接纳历史。下一层仍用相同选择器。以下角色装入同一个 Router，并依次调度 coarse、fine、return 阶段：

```python
coarse = VNSAdapter(name="coarse", base_sigma=0.2, restart_on_stagnation=False)
fine = VNSAdapter(name="fine", base_sigma=0.02, restart_on_stagnation=False)

coarse_role = RoleSpec("coarse", coarse,
    pool_task=PoolTaskSpec(subpools.random(20, adapter1), steps=3, output="coarse"))
fine_role = RoleSpec("fine", fine,
    pool_task=PoolTaskSpec(subpools.all(coarse), steps=3, output="fine"))
# 还可以让下一层选择 subpools.random(5, fine)。
# 最后由 MOEA/D 的 PoolTaskSpec("fine", mode="compete", ...) 接收结果。
```

每层沿用现有步骤、预算、repair、准入和事务。`all(coarse)` 只选择该具体实例在请求开始时已经发布的视图，不自动等待将来生成的视图。阶段策略须等待上一层所有任务完成；周期性重启须给出新的 request_key。尚未释放的往次结果也属于 all/random 的可选范围，并不隐含“仅最新请求”；只需要本轮结果时，调度者应在下一次生产前释放不再消费的旧结果视图。工厂创建的多个 VNS 是不同创建者，不能把工厂函数或类型名当作其中一个实例。

两种输出各有明确含义：

- `"coarse"` 聚合子池保留所有接纳过的提案，供种群竞争或显式筛选。
- `subpools.all(coarse)` 选择 coarse 创建的派生视图。每个视图只装入 `get_pool_refinement_results(control)` 明确交付的最终结果；VNS 返回当前 incumbent 当时选中的精确候选引用，不按 token 追读未来版本。因此下一层从上一层选中的解继续，不从聚合集合的第一条旧基线重新开始。这不表示数学上的局部最优已被证明。

投影消费者须实现这个结果接口，不能拿保留用的 get_solution_pool_roots 当作选择策略。裸 VNS 支持投影计算，但没有声明投影池精修任务时不成为视图生产者；output 不再是发布最终视图的前提。Doctor/装配检查拒绝缺失声明、未挂载创建者和循环生产依赖；运行时验证实际结果引用和原发布身份。

视图身份与来源：

- 每个投影视图有稳定 view_id，成员或投影变化时增加 revision。删除后重用相同名字得到新身份。
- parent 保存请求选中时的 `{pool_id, name, view_id, revision, ancestors}`。ancestors 是从根到父级之前的身份列表，不存候选值或整个 Unit。
- 派生视图的 created_by 是本层 VNS 实例，parent 指向选中的上层视图，两者不可混用。父级更新或释放之后，冻结来源仍成立。
- 子搜索产生的新候选不必属于父视图旧成员。父子关系表达来源，不是永久集合包含关系。

可以按结构检查一个方向的子树：

```python
source = pool.subpool_descriptor(direction_name)
direct_children = pool.children_subpools(source)
all_descendants = pool.children_subpools(source, recursive=True)
```

名字参数查询当前存活视图；冻结 descriptor 可在父视图释放后查询历史来源的后代。同名新视图不会接管旧子树。children_subpools 是查询接口，不启动任务。正式父子关系由身份元数据决定，不能用名字中的斜杠或字符串前缀推断。

每层任务直接继承一个有效 ObjectiveProjection，对本层新求值的 selection feedback 应用一次。母池仍保存原始多目标反馈；不是先把父池标量再乘一次权重。已带 subpool_projection 的反馈再次投影会报错，包括一维目标时也不会静默重复计算。显式 publish_projection_subpool 可以为新视图提供另一套有效投影，仍须面向正常反馈维度；它不是任意函数复合语言。

可见性与恢复沿用池事务：派生结果只在接纳更新完成后暂存，提交前不能枚举或按名字读成员，即使它引用的候选以前已发布。异常回滚整组视图/成员/进度；零接纳保留输入选择但不产生成功结果；部分接纳只推进对应工作实例。任务恢复源 descriptor、候选引用、投影、进度与 RNG，不追读父视图当前参数、不重新抽签或补跑求值。旧投影 checkpoint 缺少视图身份或任务源 descriptor 时须显式迁移，不能根据当前名字猜造历史身份。

父子关系只提供值式来源，不隐含保留权。drop_subpool 释放自己的成员，子视图仍保留自身引用。聚合 output 与派生视图是不同保留根，不再使用时都须明确释放。删除父级不会递归删除候选。subpool/ 是专用成员命名空间，通用 retain/replace_roots 不得绕过 create/add/publish/drop 改写它。校验拒绝跨池、循环、重复身份及与存活身份矛盾的来源；已删除历史的任意伪造不能仅靠轻量元数据证明，持久完整性仍依赖 Snapshot/签名 checkpoint。

控制面在接纳记录写入池后，把对应 accepted_solution_ref 放入每项 Feedback.info，再交给 Adapter。它与该反馈共同经过子集/路由/投影，不放在会丢失行对齐的批次级 metadata。VNS 在选择当前点时同时保存这个引用，步骤/checkpoint 和保留声明一起维护它；另一个算法后来产生同 token 新版本，不会改变这份交付。独立直接调用 VNS.update 的旧用法可以没有池引用，但不能据此发布一个猜出的精修结果视图。

存储增量主要是引用、投影参数、任务进度和祖先身份。创建视图不会新增候选 Snapshot，搜索产生的新候选和评估仍占真实空间。当前每个派生视图保存展平的祖先列表，开销随总成员引用数、视图数和深度增长；一条不断加深且全部保留的链，祖先条目累计可达深度的平方量级。应及时释放已消费的结果集合，结合 PoolRetentionPolicy 回收无人持有的候选。各算法自己的 Unit 工作副本、评估记录和 checkpoint 存储仍须另计。

可运行装配在 examples/cases/solution_pool/cases/moead_refinement/，启用 `nested_refinement=True`。

## 11. 验收依据

当前池与 manifest schema 为 v2。普通 candidate_collection、明确结果 candidate_view 与 objective_projection 都有稳定身份、版本、来源和发布状态；父子仍表达派生，不要求集合包含。旧缺失视图身份的检查点要求显式迁移。

按名称选择投影视图与按创建者选择执行相同能力检查和投影；不能用字符串绕开比较语义。普通具名集合保持每实例配额，按创建者选择以每视图配额分发。VNS、SA、PatternSearch、SingleTrajectoryAdaptive、GaussianSearch、MAS、有限差分 GradientDescent 和四种信赖域使用相同 PoolTask 装配；普通精修也发布最终选择视图，下一层可以 subpools.all(refiner)。all/random 不选择聚合 output，不隐含阶段屏障。

Role 的 pool_result_owner 指向真实结果算法。SA/Single 的 current 可以为探索变差，get_pool_refinement_results 交付 task-best；原始求值与硬准入不改变。NSGA 系列和 MOEA/D 的成员引用与 PopulationChange 一起更新，不能用回收工具 refs_for_tokens 推断最新版本。

NSGA-II／III、SPEA2 和 DE 每实例自动发布一个普通 population 视图，保存全部已选择成员的精确引用；MOEA/D 每方向发布一个投影视图。`PoolTaskSpec(subpools.all(ga), count="all", steps=3, output="refined")` 逐成员精修，默认 count 仍取每视图一个起点。视图更新复用 view_id 并推进 revision，不复制候选记录。仅在全部成员都有精确版本时发布；普通视图可包含部分初始化后已提交的成员，不能替代种群完成屏障。

EvolutionSolver 初始化、恢复和环境选择已完整交付 CandidateBatch、原始反馈、provenance 及 SolutionRef。`get_population_solution_refs` 保留成员顺序与重复槽位；`get_solution_pool_roots` 只声明回收保护，不充当成员表。Role／EliteRetention／StrategyChain／单子 Composite 转发实际所有者，多子 Composite 保持分区；不支持交付的 L2 配置在求值前拒绝。显式池初始化按最终接纳索引结算游标，拒绝和预算外种子不丢失。旧三数组环境选择需要 `external_evaluation=True`，表示外部原始求值与新身份导入，不能按数值追认旧版本。

GradientOptimizer 可普通精修，但缺少同步梯度变换时拒绝 objective_projection；结果只交付已评估点，Provider slots 按原事务保留与清理。A*／MOA* 可用 `pool_start_policy="new_root"` 从单个池种子建立新搜索根，不声明通用精修或投影。有限差分起点／探针／下降 trial 分别求值；信赖域 repair 继续守区域与子空间不变量。更细的支持矩阵、结果语义和迁移边界见 [Adapter 接入契约](SOLUTION_POOL_ADAPTER_READINESS_CN.md)。

- `test_solution_pool.py`：时间截止、身份与版本、私有可见性、失败高水位、游标回滚、可传输恢复和摘要篡改拒绝。
- `test_pool_search_adapter.py`：200→两个 100 成员种群→停滞唤醒→返回竞争；不同取解配额/种群容量与超额准备；满种群后的部分接纳重试；第二个子更新失败的整组回滚；正式 checkpoint 恢复。
- `test_solution_pool_retention.py`：多消费者保护、闲置时钟、部分行压缩、输入消费、历史固定、可传输 checkpoint、删除失败重试、步骤回滚、未决围栏与不支持组件拒绝。
- `test_subpool_tasks.py`：20 起点与两类 VNS、子池提交可见性、任务回滚/零接纳重试、返回种群竞争及正式 checkpoint。
- `test_pool_task_allocation.py`：母池默认输入、300→30×100、分区/共享、缺失与空子池、不足策略、单解起点与随机分配恢复。
- `test_projection_subpools.py`：100 方向与实例来源、all/random、两种标量投影、同候选多方向、原始证据、零/部分接纳、冻结比较、回滚与正式 checkpoint、返回 MOEA/D 竞争。
- 既有 repair、SA、语义候选、评估接纳、步骤事务与 checkpoint 测试确认旧边界仍成立。
- `test_nested_pool_views.py`：父子身份、来源冻结、同名重建、子树查询、共享引用、发布/回滚和恢复校验。
- `test_nested_refinement.py` / `test_nested_refinement_contracts.py`：多层 VNS 的最终候选交接、一次投影、原始反馈、异常/零/部分接纳与处理中途恢复。
- `test_evolution_population_identity.py`：完整初始化与恢复交付、同值不同身份、重复槽位、透明包装、部分种子结算和外部求值导入。
- `test_pool_numeric_refiners.py` / `test_trust_region_pool_tasks.py`：统一任务输入、精确结果、基准先求值、投影与 repair、零接纳、回滚和正式 checkpoint。
- `test_graph_pool_contracts.py` / `test_gradient_pool_provider_lifecycle.py`：新根与路径含义、Provider 活 slot 保留、重启与回滚、清理债务重试。

实际运行命令与结果统一记录在本轮验收文档；存在测试源码不能单独解释成验证通过。
