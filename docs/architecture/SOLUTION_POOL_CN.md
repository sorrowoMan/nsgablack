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

提交结束时，池索引丢弃本尝试的私有中间记录；最终候选、修复和处置证据仍由既有 Event/Authority Snapshot 留存。池不把每次算子草稿无限加入可查询历史。已经写出的私有 Snapshot 的物理回收遵循共享存储策略，本轮不增加另一套删除器。

步骤外显式写入的初始化记录可按 `stage="initial"` 查询。默认 `select()` 查询 accepted，以免后续算法误把未经评估的初始化值当成可交接结果。池不是自动 Pareto 档案，默认不去重、不选最优、不自动裁剪历史。

## 5. 评估与偏好不从上一个算法照搬

池可以保存对齐的原始目标和违规量，用于审计。它不把上一算法的 selection feedback 当成接收算法的反馈，也不据 token 或数值相等自动复用评估。

PoolSearchAdapter 的初始化和返回竞争都走正常 Problem/Provider、repair、Bias、预算与接纳路径。NSGA-II 和 NSGA-III 分别重新建立自己的选择视图与结构。需要复用原始评估时，应另行声明求值语义、问题版本、上下文和 Provider scope 的等价性；这一轮没有新增自动求值缓存。

Unit 偏好继续通过 UnitView/UnitInputSpec 明确绑定实例路径和数据依赖；池里的解不会携带一份可写排名供所有算法共同修改。

## 6. 用户装配：准备 200 个解，两个种群各取 100 个

在标准 Case 的 `adapter/` 工厂中装配：

```python
from nsgablack.adapters import (
    NSGA2Adapter, NSGA3Adapter, SimulatedAnnealingAdapter,
    PoolSearchAdapter, PoolSearchSpec,
)

adapter = PoolSearchAdapter(
    producer=SimulatedAnnealingAdapter(name="seed_sa", batch_size=199),
    searches=[
        PoolSearchSpec(NSGA2Adapter(name="population_a", population_size=100), 100),
        PoolSearchSpec(NSGA3Adapter(name="population_b", population_size=100), 100),
    ],
    stagnation_steps=20,
    recovery_steps=5,
)
```

`build_solver.py` 把这个 Adapter 与问题和 Pipeline 装到 ComposableSolver 中即可；池由 Solver 先创建，用户无需装第二套存储。脚手架提供可选 `adapter/pool_example.py` 工厂，默认起步算法不会被自动替换。

具体流程：

1. `preparing`：只启动 producer 搜索；已接纳提案进入池，累计数量达到 200 后切换阶段。SA 先评估 1 个基准点，下一次可提出 199 个邻居；“200 个”是已接纳提案数，不是 200 个不同数值，也不承诺固定两步完成。
2. `search`：锁定 ready_stamp，按池记录顺序分配前 100 和后 100 个引用。分配不重叠；两个种群分别送评并建立自己的 Unit。之后 producer 保持等待、温度不下降，两种群各自搜索。
3. `recovery`：观测到停滞后显式重启 producer，从池中选择一个种子、重置搜索温度，保留本地 RNG 流；不重放 setup/Plugin 生命周期。仅 producer 搜索指定的已提交步骤数。
4. `return`：锁定本次恢复后发布的候选，分别提交给两个种群参与正常环境选择；不直接覆盖整个种群。随后回到 search。

默认停滞指标是 `min(sum(raw_objectives) + 1e6 * raw_violation)`；这是一项明确的标量策略，**不是局部最优证明**。多目标、目标量纲不同或追求多样性时，用具名 `metric(feedback)` 显式替换。默认恢复种子是该组合最近发布的一个候选；需要精英、多样性或区域选择时提供 `recovery_selector(pool, stamp)`，当前单解恢复要求恰好一个引用。

`recovery_steps` 包括重启后的基准评估提交。初始分配数量须匹配接收种群容量；未接纳或预算未覆盖的初始化种子保留在输入选择中，下次继续补齐。若条件长期无法满足，依旧需要 max_step_attempts/deadline 保护。

同一组合中可变 Adapter 实例和 name 均不可重复。嵌套调用按正式 StrategyTask 路径识别本组合的池候选；父级不能用全局 context 重新绑定子提案。

正式示例：`examples/cases/solution_pool/cases/pool_search/`。默认采用较小种群以便快速查看阶段；完整 200/100/100 流程由行为测试覆盖。

## 7. 输入游标与接纳

`pool.bind_input(refs)` 生成轻量 selection ID；context 只携带 `solution_input_ref` 和 `solution_input_mode`。Adapter 通过 `init_candidate / init_population` 消费选择，不把整个候选矩阵放入 context。

PoolSearchAdapter 在提出候选前后记录消费数量，最终 BatchDisposition 按原提案索引结算输入。未接纳的种子保留在该选择的剩余区；一个子提案批次不混合“池输入”和“新生成候选”，避免无法确定游标对账含义。消费失败不随机补种子。

输入被允许进入搜索与候选是否成为最终成员是两件事：compete 模式按正式准入消费输入，由 Adapter 自己决定最终成员。池不修改该决策。

## 8. 恢复、存储和可检查范围

池提供 Mapping 步骤快照和显式可传输 checkpoint codec；快照只有索引、refs、游标和发布身份，不复制 SnapshotStore、锁或 Provider。

checkpoint 中的候选值按显式 CandidateBatch codec 搬运到目标 SnapshotStore，新物理 key/scope 不冒充旧物理引用。logical SolutionRef 保留，恢复每条值时核对原内容摘要。PoolSearchAdapter 要求 checkpoint 中必须有 solution_pool component，不能在宽松恢复模式下丢失其输入状态。

正式恢复先应用池组件并在目标存储创建 manifest，再恢复发布算法 Authority Snapshot，然后应用其余组件；同一池只恢复一次。读取必需池状态失败时，即便 checkpoint 配置非 strict 也不得遗漏它。

共享 context 只增加四个正式轻量键：`solution_pool_ref / solution_pool_time / solution_input_ref / solution_input_mode`。Doctor 检查池存储是否与 Solver 相同、是否登记步骤参与者、候选事实 owner 是否一致，以及 Adapter 的输入/重启声明；不通过执行搜索证明算法正确性。

支持范围：公共候选控制面池化；NSGA-II/III 声明初始化和竞争输入，SA 声明单解初始化与显式重启。其他 Adapter 自行声明并实现所需模式后才能进入这个特定组合，不能因有 Unit 就推断已支持。种群算法的“两边推进”是同一 Solver 步骤中的组合调度，不承诺 CPU 同时运行；实际并行与多 Case L0 仍由 BlackBase 管理。

## 9. 验收依据

- `test_solution_pool.py`：时间截止、身份与版本、私有可见性、失败高水位、游标回滚、可传输恢复和摘要篡改拒绝。
- `test_pool_search_adapter.py`：200→两个 100 成员种群→停滞唤醒→返回竞争；第二个子更新失败的整组回滚；正式 checkpoint 恢复；输入部分接纳。
- 既有 repair、SA、语义候选、评估接纳、步骤事务与 checkpoint 测试确认旧边界仍成立。

实际运行命令与结果统一记录在本轮验收文档；存在测试源码不能单独解释成验证通过。
