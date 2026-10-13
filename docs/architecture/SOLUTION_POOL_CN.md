# 解池、运行时间与算法结构

最后按代码核对：2026-10-13。实现：`core/state/solution_pool.py`、`adapters/pool_search.py`。本文是当前运行契约；更广的编排讨论见 [增量 Unit 编排讨论](ORCHESTRATION_WITH_INCREMENTAL_UNITS_DISCUSSION_CN.md)。

## 1. 解先有存放位置，再由算法使用

解池是一次运行中存放候选的具名区域。它记录候选语义、数值视图、身份、来源和运行时间。Adapter 从中取得候选，用自己的 Unit 组织成员、当前点、路径、邻域、区域等关系，再提出新候选。Unit 构建不等于编码；池读取不等于解码。

最小分工是：

- Problem 定义原始求值和问题约束；问题 Pipeline 处理候选。
- SolutionPool 通过共享 SnapshotStore 保存候选版本，不负责排名、温度、支配关系或调度。
- Unit 保存本算法的工作投影、成员关系、派生特征和必要状态。
- Adapter 决定从池中使用哪些解、如何搜索、何时接纳到自己的结构。
- Bias 形成当前算法的选择偏好；Plugin 提供评估、恢复、观察等运行能力。

框架不需要 NSGA-II→SA、SA→MOEA/D 等逐对转换器。接收算法取得候选后按自己已有的规则建立或更新结构。两个种群可以引用同一候选来源而拥有不同成员顺序、排名和参考方向。

池是共享候选版本的所有者；PopulationAuthority 仍拥有**当前算法投影与发布游标**。二者不争夺同一个可写矩阵：池版本不可原位改写，Unit 的工作数组按已有成员操作和步骤事务更新。当前内置 Unit 保留数值数组以便高效运算，还没有全部迁移成只存 SolutionRef 的结构。

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

## 10. 验收依据

- `test_solution_pool.py`：时间截止、身份与版本、私有可见性、失败高水位、游标回滚、可传输恢复和摘要篡改拒绝。
- `test_pool_search_adapter.py`：200→两个 100 成员种群→停滞唤醒→返回竞争；不同取解配额/种群容量与超额准备；满种群后的部分接纳重试；第二个子更新失败的整组回滚；正式 checkpoint 恢复。
- `test_solution_pool_retention.py`：多消费者保护、闲置时钟、部分行压缩、输入消费、历史固定、可传输 checkpoint、删除失败重试、步骤回滚、未决围栏与不支持组件拒绝。
- 既有 repair、SA、语义候选、评估接纳、步骤事务与 checkpoint 测试确认旧边界仍成立。

实际运行命令与结果统一记录在本轮验收文档；存在测试源码不能单独解释成验证通过。
