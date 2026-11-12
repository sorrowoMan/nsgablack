# 运行所有权与显式扩展契约

2026-11-02 补充 Unit 步骤回滚：`UnitBinding.snapshot_step/restore_step` 与持久 `dump/restore`
分开。未改写持久 codec 的内建 StructureUnitBuilder 支持 `nsgablack.unit_step/native-v1` 私有数据值，
数组在捕获和每次恢复时独立复制，不转成 JSON 列表、不调用 builder.build；完整 schema/绑定/身份验证保留。
UnitBackedAdapter 已有局部步骤协议的路径使用该接口；其他 Adapter 和自定义持久 codec 仍可沿用原路径。
自定义 dump/restore（含实例替换或修改函数代码）不因继承 native hooks 而被绕过。
运行内步骤值不属于可传输 checkpoint；get_state/set_state 继续使用原持久格式，旧步骤数据仍按原 codec 恢复。
PopulationChange 保留闭合数据 codec 的只读脱离，省去未使用的摘要；特征缓存依赖的签名不变。
详见 `UNIT_STEP_SNAPSHOTS_CN.md` 与 `results/test_runs/unit_runtime_snapshot_20261102/` 的实测记录。

2026-11-02 补充：标准 Case 的取消检查由 BlackBase 运行时管理。普通检查每次验证截止时间，
取消状态最多复用 50 毫秒（短 TTL 进一步收紧）；任务交接、run 前后和最终发布前强制读持久状态。
该窗口还需加上协作检查间距和 I/O，不是硬实时响应保证。SQLite/Redis 同步不续期，
心跳独立续活自己拥有的记录；失败不按“未取消”放行。预算与恢复仍由原持久账本负责，
本轮未降低真实消费或 settlement 的持久化要求，详见 BlackBase 的 `RUNTIME_CONTROL_OWNERSHIP_CN.md`。

最后按代码核对：2026-10-21（本次接入调用期 chosen/inject 语法）；2026-10-26补充Provider原始反馈、单次Bias投影与派发计数。本文描述当前实现；本轮可运行流程见 [Pool Project](../../examples/cases/pool_workflow_pilot/README.md)，其余边界验证见 [验收记录](../development/RUNTIME_REFINEMENT_VALIDATION_CN.md)。

## 保留的主线

VNS / MOEA-D 与 NSGA-II/III、SPEA2 提供 `change=function` 完整变化入口。普通同步函数接收只读 ChangeRequest
和所属 Adapter 的 rng；GA 可返回 ChangeBatchResult，每个 ChangeResult 保存独立候选、来源和目的池。
request.max_outputs 给出本次许可，超额拒绝，空批次不自动补满；标量位置仅接受恰好一个候选。
函数不要求用户手写组件身份或恢复样板。
内部桥接复用 OperatorBinding；主函数及直接同模块 helper 的代码、不可变配置参与身份。
函数不得持有隐藏可变搜索状态，指纹不等于全依赖图签名或副作用沙箱。
完整 change 与直属 mutator/具名变异互斥，输出仍通过正式候选身份、修复、求值与提交路径。
阶段分块见 [普通函数与池输入试作](POOL_WORKFLOW_PILOT_CN.md)。
`request.pool` 现提供调用内冻结、只读的 main/subpool/read，以及局部 take/random/merge；
操作顺序由普通函数编排。任务内额外来源须声明 change_sources/change_allow_main，嵌套不扩大范围。
ChangeResult/PoolOutput 声明接纳后的普通集合输出，使用同一 accepted SolutionRef 和池事务；
目标身份与 revision 冻结，输出指令绑定提案 token，不改写算法结果视图或重放祖先交付。
协议、示例与恢复边界见 [池驱动变化编排](POOL_CHANGE_ORCHESTRATION_CN.md)。
只读集合进一步支持过滤、显式排序、交差与临时分组；普通成员维护通过 ChangeResult.edits/PoolEdit
冻结精确成员和目标身份，以接纳结果为执行边界，并随同一池事务提交。查询不生成候选，成员变更不删除候选。
精确替换与裁剪保留明确顺序和重数，空更新不折叠任务坐标；比较规则与本轮/下一轮分数边界见
[Pool 集合操作](POOL_COLLECTION_OPERATIONS_CN.md)。

GA 原生 survivor 位置接受普通 choose(Pool)->Pool，内部用精确引用与原始位置映射回现有选择索引。
Pool 是 ChangeSelection 的公开别名，all/concat/filter/sample/sort 保留同一接口；concat 保留重数，merge 精确去重。
请求内选择反馈与池 raw 分开；没有精确引用的旧数组路径不允许伪造 Pool 身份。
已有对象 selector 的局部索引协议继续支持，未装配普通选择时保留算法默认规则。

GA 的 survivor 选择还接受 `(members, {name: branch_pool})`，普通函数只调用一次。
主结果保持既有 count/原始位置唯一校验，Unit 仍通过 PopulationChange 维护基础和扩展字段。
命名副结果必须来自同一 offered root/scope；普通集合允许保留显式重数，不要求它一定是主成员子集。
从主成员选 elite 与从淘汰成员选 reserve 均由用户函数明确表达，框架不根据目的池名字猜规则。
每个副结果表示目标普通 candidate_collection 的精确最终成员，不是 append；空副结果可创建空集合。
已存在目标冻结完整 descriptor，不存在目标冻结 pool_id/name/absent。规则返回时全部验证并脱离为 PoolEdit，
进入现有 collecting_pool_edits；在同一 update 后与逐提案输出统一预检，再随 Pool/Authority 原事务发布。
任何名称、输入归属、主结果数量或后续 Unit 更新失败均不发布副结果；同目标不同 replace、append+replace、
目标同名重建及缺失目标中途出现都拒绝并回滚。真实求值消耗保留。
副结果不复制候选或选择分数、不生成新身份、不改算法发布视图，也不将活 Pool 保存进 checkpoint。
发布副集合不扩大下一调用的输入能力，池任务仍通过 change_sources/change_allow_main 声明后续读取。
恢复读取已提交集合与 Unit，普通函数身份仍由既有绑定检查；不重跑选择来重建副结果。
命名副结果只在已有 survivor 更新位置支持；其他 purpose 拒绝。零接纳/空提案仍不独立发布纯成员计划。
partition 的 by 仍是纯 Pool→Pool 规则，副结果交付仅在实际 survivor 应用边界处理。

`partition(pool, by=choose, rng=None)` 将当前输入的每次出现临时编号，非空时调用普通 Pool→Pool 规则一次，
验证其返回属于同一临时请求且局部位置唯一，再将两边映回调用者的原坐标与作用域。
选择反馈按当前输入顺序和重数只读切片；缺失时不改读 raw、不求值或重跑 Bias。
selected 保持规则次序，remaining 保持输入相对次序；同一引用的不同出现可以分在两边。
`difference` 仍按精确引用求差集，不能替代这个位置补集；有放回重复同一局部位置的返回会被拒绝。
空输入不调用规则或消耗 RNG；参数/签名仍检查，未使用的 required rng 可省。
callback 的内部异常不重试；两边有效期沿用外层调用，不新增持久身份、Unit、Snapshot 或事务参与者。
局部重编号不能赋予外层重复生存槽位新的身份；外层仍按原请求坐标校验。
拆分不编辑成员；需要应用时继续通过所属算法或带冻结目标身份/revision 的 PoolEdit 进入原提交点。

调用期 Pool 进一步提供 `source.chosen(rule, rng=None)`：纯同步规则接收并返回本次 Pool，
通过临时出现位置校验后映回原坐标。显式重采样可以重复位置，但不能绕过最终 survivor 的唯一性检查；
空源不调用规则、不消耗 RNG。规则内部不得通过 inject 修改本作用域草稿。
`Pool(parent=source_or_scope, name=None)` 创建空本地草稿；有 name 时是普通集合目标，同 scope 同名共享草稿。
仅构造不读取同名旧成员，也不创建持久集合。`inject(source, replace=False)` 在本地追加，保留旧重数，
新加入的精确版本只追加一次；`replace=True` 精确保留源顺序与重数，空源表示清空。
首次追加到已有具名集合必须通过原 scope 的 subpool 读取授权；精确替换无需读取旧成员，但仍检查目标身份。
`all()` 固定调用时的草稿快照；同反馈 root 保留临时选择分数，跨 root 不拼分数、不改读 raw。
具名草稿仅在实际 survivor 和 pool_maintenance 写回调生效，登记前检查现有 update collector/attempt。
成功回调自动脱离为既有 PoolEdit；同草稿反复注入只提交最终计划，独立回调争用仍拒绝。
maintenance 可在注入后返回 None；没有自动计划时仍须返回旧序列协议。
普通 change/propose 不开放自动 inject，继续使用按提案接纳绑定的 ChangeResult.edits。
parent 只携带调用作用域与局部来源，不创建持久拓扑、继承投影、配置 Adapter 输入或约定返回路由。
此语法不创建新执行器、生命周期或事务；活 Pool 不进 checkpoint，原 Router 的装配与提交可见性不变。

五种上述叶 Adapter 还支持 pool_maintenance 普通函数，每个实际 update 的算法决策后调用一次。
PoolMaintenanceRequest.accepted 仅授权本批实际交付的 accepted 精确版本，普通 main 不放开 pending。
request.members 使用同一实际叶的 get_population_solution_refs 与 get_population_snapshot 交付有序最终种群；
不从保留根或尚未公开的 population 视图反推。NSGA-II/III、SPEA2、MOEA/D 支持，VNS 为 None；
两个入口半支持、维度/引用不齐或值不符均拒绝，不静默降为空。重复槽位保留，MOEA/D 的 F/V 仍是多目标反馈。
只有本叶本批 accepted 可未发布；旧自有成员在同次维护内获准确引用授权，不开放兄弟 pending 或额外 main/subpool。
accepted 与 members 各自附只读选择反馈，request.objectives/violations 仍按 accepted 对齐；parameters 保留已有投影声明。
历史集合与最终成员可以在同作用域合并，跨 root 不自动拼接选择分数，应显式读取 raw 或提供统一比较规则。
replace_members(..., create=True) 可将缺失普通目标冻结为 pool_id/name/absent，提交时仍缺失才创建；
默认 create=False 保留原缺失错误。创建不增加读权限，任务仍须声明准确公共目标名；空结果可创建空集合。
返回 PoolEdit 与逐提案输出在原提交点统一验证，保留目标身份/revision与同目标冲突规则。
不在每个槽位重复维护、不另求值或计代；异常一并回滚，已经发生的求值和预算消耗保留。
PoolTask 在 proposal/update 两端执行相同 donor 范围限制，包括父代来源；子任务不能借维护或父代选择扩大权限。

StrategyRouterAdapter/StrategyChainAdapter 现提供 `working_pool=name|None` 与运行前 setter。
显式名字指向同一 SolutionPool 内已提交的普通 candidate_collection；None 继承最近组合，没有绑定时保持根池行为。
不自动建池，不复制候选，不把算法投影视图当可写工作区；阶段、算法 Unit 和资源授权不转移给区域。
PoolTaskSpec(select=None) 按本次绑定冻结来源，显式 select 保留原任务命名/投影语义；绑定不自动给裸孩子插入池任务。
普通 change/maintenance 的 main 同步限定到工作区域，change_allow_main/change_sources 的嵌套权限仍生效。
本批 accepted receipt 经原成员计划收集器暂存为工作区追加；最近组合先承接，外层不自动重收显式内层区域的结果。
全部追加在现有 publish_change_outputs 中与显式输出统一验证，再随原 Authority/Pool 事务提交。
自动追加与显式同名 replace 冲突；空/零接纳不增加成员，失败丢弃计划并回滚成员和算法状态，真实求值保留。
绑定名字与轻量原提案描述符进入 Adapter 状态；repair/disposition/update 不受后来 ctx 工作区观测覆盖。
同名重建拒绝，正常 revision 推进可继续；旧无字段状态仅在当前无显式绑定时接受。
首次提案后冻结配置是进程内装配锁，不计入算法语义状态；setup 重置，恢复按已运行进度重新锁定。
Doctor 只检查绑定声明，不为了验证存在性运行 Source 或创建 Unit。完整用法见 Pool 手册 0.5。

Problem 定义问题；问题管线处理候选；UnitBinding 提供算法结构构建能力；Adapter 按需创建、持有并操作 Unit 作搜索决策；Bias 表达偏好；Plugin 提供声明的能力。Solver 保留公开装配门面，运行状态、事务、证据检查和结果发布分别有明确的所属对象或协议。

必须保护候选值与身份分离、活状态与持久数据引用分离、部分接纳显式成值、Unit 按绑定 codec 恢复。Unit 可以提供结构操作，不能拥有第二套求解生命周期。关于“唯一”“最原创”等研究主张需要比较研究，不能由实现核对推导。

## 权威与事务

SolutionPool 在 Solver 构造时先创建，登记 candidates 事实并参与共享步骤事务；大值仍由 BlackBase SnapshotStore 保存。池保存不可原位改写的候选版本、运行时点和输入游标；Unit 保存本算法关系与工作投影。新算法提案使用显式派生 token 并保留源 SolutionRef；读取不换身份，repair 同一提案保持 token。不是为每个成员槽位编造身份。

池历史数量、编排取解配额和各算法的成员容量独立；不要求 build_solver 统一传入 population_size。PoolSearchSpec.initial_count 只控制该组合的初始取解，准备阈值不是池上限。NSGA-II/III 的超额初始输入先经过自身环境选择，再一次安装对齐成员；种群已满也不阻止剩余种子送评。较少种子形成较小种群，后续由算法自己的后代搜索扩充。

提交先暂存池 manifest，将引用写入同一目标 Authority Snapshot，权威围栏成功后才公布池索引；恢复只读已验证的 destination manifest。失败/零接纳不让另一阶段读到草稿；部分接纳结算原输入索引，未接纳初始化种子保留。池不自动借用其他算法的选择反馈或重放评估。详细接口、算法支持范围与存储回收限制见 [解池契约](SOLUTION_POOL_CN.md)。

PoolRetentionPolicy 显式启用无人使用候选的回收，默认关闭；闲置按提交步数计时。Adapter 的本地活引用声明、显式消费者 retain 与未消费输入共同保护候选，淘汰一方成员不能解除另一方持有。部分批次压缩保留原始 row/token，年龄与引用参与回滚；物理删除只在提交之后，失败留队列。最近发布窗口和显式 pin 保留值闭包，窗口外未固定的旧池 manifest 可失效；可传输 checkpoint 自带候选值。未决 Authority 提交临时固定 prepared manifest 及其值，恢复按持久证据确认后释放；池暂存操作须先于持久 disposition intent。

新 checkpoint 外层信封为 nsgablack.checkpoint.envelope.v2：候选和组件状态序列化一次，HMAC 对实际保存的 payload_bytes 签名并先验签、再解析该 payload。禁止用“再次 pickle 语义值”的字节近似原始签名，也不保存另一份可写 payload 副本；内部 checkpoint.v10 语义 schema 不变。旧 v1 保留既有严格验签读取，签名不通过不得绕过。

PopulationAuthority 保存内存 population/objectives/violations、CandidateBatch、token、分区及 Snapshot 发布游标；原 Solver 字段通过 OwnedField 访问同一对象。AuthorityStore 继续负责持久 identity、epoch 与围栏；内存投影不能自行宣布持久提交。

RunSession 保存运行身份、进度、时间、deadline、恢复队列/锁和结果引用。它显式声明 rollback_exempt_reason：失败尝试、耗时与已消耗预算必须保留，逻辑步数仅在提交后推进，结果通过独立 finalization 事务发布。它不参与步骤回滚；误注册时在采集状态前拒绝，避免复制 RLock 等过程内对象。RunProgressState 只序列化可恢复值，锁、回调和单调时钟起点不进入 checkpoint。跨框架恢复调用 submit_restore。

AuthorityRegistry 拒绝同一事实登记两个不同所有者；每个事实必须登记 RuntimeParticipant，或显式提供非空 rollback_exempt_reason。Doctor 检查全部登记项，包括扩展事实；同一登记不可静默改变回滚策略。它不证明任意 Python 程序中不存在未登记的副本。结果和进度可共享 RunSession；Artifact 权威仍由 BlackBase publication seal 确认。

RuntimeParticipant 的 snapshot/restore、独立 children、commit cleanup 协议属于 BlackBase。RuntimeTransaction 按身份去重，拒绝环；回滚失败也尝试其他参与者，提交后的清理失败形成报告。Adapter 添加优化报告与搜索语义；L1 轨迹、L2 population 分类留在优化层，不要求 ML 参数更新冒充种群。

Unit 成员字段由所属 Adapter 的 Unit codec 捕获和恢复，成员维护不是额外的 RuntimeParticipant。正常零接纳与异常回滚的范围不同：前者恢复修复前成员与结构效果，再由 disposition 消费本次 pending；后者恢复步骤前的完整参与者状态。原提案索引与成员操作局部索引不得混用；职责与行为证据见 [Unit 契约清单](UNIT_CONTRACT_MAP_CN.md)。

SA 的 current 尚无关联评分时，只提出一个初始/基准候选；该候选通过正常 repair、预算、求值和接纳后整组安装 current/score。初始化提交计入逻辑步骤和求值预算，但不降温；下一次才变异并按 Metropolis 比较。拒绝或失败不生成基准评分，checkpoint 恢复已有评分不重复求值。不能将第一个邻居的评分关联到未评估的初始点。

snapshot_step_state 必须只读地返回 Mapping[str, Any]。事务和 Doctor 共用捕获校验，子参与者同样检查；无效返回产生 runtime-participant-snapshot-invalid。Doctor 不调用 restore/commit，不做清理。Mapping 只是外层结构约束，不证明嵌套对象可安全复制；组件仍负责状态脱离，禁止携带锁、executor、Provider session 等活对象。

ComposableSolver 与 EvolutionSolver 共用步骤事务。PopulationAuthority、incumbent 参与者、EvolutionState 分别管理状态。新增字段应归到正确所有者；可变复合内容须有明确复制/codec 契约，不能复制锁、executor 或第三方活对象图。

已发生的评估、预算消耗和失败证据不回滚。EvaluationEvidenceCoordinator 拥有公共持久证据状态机。PopulationEvidenceSemantics 只接收 SnapshotStore 与 AuthorityStore，验证优化载荷，不持有 Solver、Adapter 或重放评估回调。

PopulationEvidenceSemantics 的 EvidenceReason 把稳定原因码与 verified/deferred/invalid 状态绑定在同一枚举项，直接返回 EvaluationEvidenceInspection。异常类型和详情放在 diagnostics；不从原因文本或错误文案推断恢复分类。未知原因不能默认降为 invalid。

恢复分类由 BlackBase EvaluationEvidenceCoordinator 的 recover_unresolved 实现：已有持久处置的 decision_ready 或尚未核验的 finalized 证据，只有 Event、目标 Snapshot 和 Authority 围栏核验后才补结算；不可读或核验失败时保留 deferred，不推断为没有处置。event_ready 尚无持久处置时以 decision_not_durable 归档 abandoned；reserved 的 Event 证实无效时也可归档。所有分支都不重跑 Problem、AcceptancePolicy、repair 或 Adapter，不制造新 generation 或求值。

verification receipt 可由 Journal 持久化用于审计，但 verified_at 是观测时间，必须排除在语义 content digest、幂等键和证据身份计算之外。重复检查允许时间不同；Event/Destination 的 identity 与 disposition_digest 必须相同，检查本身不得改写 Snapshot、围栏或 Journal。若归档文件包含审计时间，其字节校验和只是该归档载荷的完整性证明，不能替代上述语义身份。

内存与发布快照的一致性通过真实 step 回归断言：step_batch、single、partitioned 均比对数值、CandidateBatch/token/provenance 或每个分区，关联 AuthorityStore 的 destination 与 event cause；下一次 staging 后失败必须恢复为同一已提交投影。这是覆盖指定故障窗口的行为验证，不是对任意直接 Python 写入的证明。

Authority v2 仍完整内嵌最近 Evaluation Event。存在精确已发布身份时，组装通过 BlackBase `read_verified_view(identity)` 读取该版本，复用不可变的 envelope、候选和来源子树；每次调用核对精确身份，内容的不可变证明由共享底座保证，不能用先前普通读取替代本次读面。已知身份丢失、跨 scope、版本或摘要不符时直接失败，不能改用旧内存副本。未发布事件、旧式不完整事件及跨 Store checkpoint 导入继续使用自足值路径；便携 checkpoint 仍导出完整语义事件。

共享仅减少 Memory Snapshot 的重复物化和内存占用：Authority 对冻结子树保持 Python 所有权，源 Event key 删除后仍包含全部内嵌值，不引入外链、依赖图或新 schema。Event v1 的 JSON 数值列表保留原协议，Authority 的 X/F/V 仍须物化为数组；File 等后端按原脱离读取处理。持久化 Authority 和 Event 仍各自保存完整值，不能据此声称落盘字节去重。

BlackBase 的 Memory 写入对无归一化的闭合值使用本地冻结准备，省去传输 JSON 解析与恢复，
仍核对类型、深度、节点数、传输大小及完整 canonical digest。协议对象和自定义输入回退原 codec；
File/Redis 和便携 checkpoint 不改。此实现优化不允许跳过取消、预算消费、证据结算或恢复核验。
闭合值的类型／深度／节点检查、冻结和 safe-wire 构造由 BlackBase 单次递归完成；
输入捕获、传输大小检查及完整根 canonical 编码仍执行。跨 Store、不支持或需归一化的值
继续走原 codec，不以减少遍历为理由省掉候选身份、dtype 保真或摘要边界。
Memory 的 verified-content 导出可在完整身份核验后复用有界的 canonical 字节缓存，
证据归档据此避免再次遍历完整值；缓存淘汰或未命中仍可从同一精确版本重新编码。
标准 Case 的 SQLite 预算连接由 BlackBase 当前调用作用域持有，操作之间不保留事务；
逐候选消费仍持久提交，运行时在 Artifact seal 前关闭连接。取消与步骤回滚不撤销消费。

步骤 Snapshot 事务内，context 构建只投影已经发布的 Snapshot handle；尚无 handle 时不隐式组织完整载荷或创建 pending，也不能把可变 pending 当作已发布引用。当前步骤的最终 population、分区、候选来源与池引用仍由正式 Authority writer 准备，处置登记和提交后才可读；idle、reject、cancel 与失败回滚不因此发布草稿。事务外公开 `build_context()` 保留无 handle 时生成首个可读 Snapshot 的兼容行为。

事务内的批量评估同样不准备中间 population Authority：已评估批次由独立 Event 保存，接纳及环境选择后由正式 writer 准备最终 pending；事务外直接评估的既有快照行为保留。读取 context 和记录评估均不替代选中成员的发布。

证据检查对已有 Journal Event／carrier 身份使用本次精确只读 view；仅 preparing、legacy 或尚未取得精确 carrier 时保留按 key 发现。首次 committed 检查可从当前 Authority 边取得 destination 身份，但该前置查询只作读取位置，读取后仍重新核对当前完整围栏、Event cause、epoch 和 scope，不把先前边缓存为结算证明。已知身份失效禁止退回裸读；destination 版本或内容损坏返回稳定的 invalid 原因 `destination_snapshot_invalid`，缺失仍 deferred。SQLite Authority 后端可能多一次查询，不据此承诺所有后端均提速。

## 可选数值运行库按实际使用加载

导入 core、插件或 performance 命名空间不应启动未使用的 Numba/LLVM 或 COPT。
performance 的公开导出保持原路径，按属性实际访问导入；基础非支配排序类保持纯 NumPy，
optimized 入口只有达到原有加速规模条件才装载独立 JIT backend。显式查询 Numba 状态或
使用 Numba helper 仍可触发探测；首次实际加速的导入/JIT成本没有消失。
COPT 在真实后端装载入口才导入，失败后仍按原 mock/strict 配置处理，不在普通插件导入时探测。
本规则不改变候选、评分、约束、资源授权或取消/预算持久化语义。

## 显式扩展与失败

多角色池任务使用 `RoleSpec/StrategySpec.pool_task`，由现有 Router 与 PoolTaskAdapter 绑定输入、逐起点重启和输出，不创建第二个运行循环。子池是池内具名 SolutionRef 集合，复用 retention owners、池索引事务和 checkpoint；引用按 token+版本保留，候选内容不复制。任务进度与子算法分别回滚；正常零接纳保留输入选择以重试，异常整组恢复。输出引用暂存到同一池 publication，提交前不能通过子池读取。

PoolTaskSpec 省略 select 时读取母池 main 的已发布候选，命名子池不存在必须报错。count/distribution/on_insufficient/shuffle 声明数量、分配与不足规则；默认初始化独立无放回抽样，跨实例允许共享来源；默认精修每实例一个起点，整批队列须显式 count="all"。独立分配 RNG 与首次分配结果可回滚、可恢复。initialize 完成后继续算法自身搜索，不每轮取解，不默认随阶段重置。数量默认由算法声明，未知组件需显式 count。

VNS 首次从池输入后先评估起点，基准未通过准入时重试同一来源，不随机替换起点。每次局部更新仍经过既有修复/预算/接纳；每个任务的 steps 包含基准更新，不等于裸求值次数。结果集合包含所有被接纳提案；返回种群重新求值与选择，不能把新候选的分数归给来源候选。SA/VNS 与 NSGA-II/III 的声明能力已接入此路径，MOEA/D 支持返回竞争。

MOEA/D 显式发布每方向投影子池，created_by 是 Adapter 实例所有权路径，包含槽位及 ObjectiveProjection。subpools.all/random 只按指定实例选择已发布方向；PoolTaskAdapter 在请求开始时冻结引用与权重/参考点，VNS 的起点和邻域共用该比较坐标。selection 标量在 Adapter 消费边界生成，raw 目标/约束和硬准入不变；返回 MOEA/D 时按其当前分解重新竞争。方向元数据随池 manifest 提交，队列/投影/RNG 随任务恢复，不重抽签或重评。详见 SOLUTION_POOL_CN.md §10.5。

投影池精修任务每个完成起点通过 get_pool_refinement_results 显式交付最终选择，另发布本层创建的派生视图，output=None 也可交付最终选择；显式 output 另保存累计接纳提案。下一层可用 subpools.all(vns_instance) 继续精修。控制面将精确接纳引用写入每项 Feedback.info.accepted_solution_ref，随子集/路由保留；VNS 选择时保存该版本，不按 token 追读之后的新版本。每个视图有稳定 view_id/revision，parent 保存冻结来源身份与祖先列表；继承有效投影后对新反馈应用一次，不递归标量化。任务依赖环和未绑定投影输出的生产者在装配时拒绝，阶段完成屏障仍由 Router 决定。视图本身提交前不可读；父级更新/删除不改子级语义，释放父级只解除其引用，不级联删除后代候选。缺失新身份的旧投影 checkpoint 需显式迁移。详见 SOLUTION_POOL_CN.md §10.6。

一个候选可以被多个方向槽位或多个种群分区持有。控制面和 Population Snapshot 保留相同 token，不派生 population_slot_alias；槽位身份由 Unit/partition 与行位置表达。快照对重复 token 校验数值及语义 metadata 一致。初始化成员不在最近评估窗口时，按显式 token 从池读取来源并校验内容，不能重新生成身份。

SolverSemanticExtension.before_step 属于提交前尝试；after_step_committed 属于提交后投影。后者失败通过 CommittedStepError 保留真实 StepOutcome；循环先记录提交计数和通知，再结束失败运行。ML 投影使用该接口，LearningSolver 不再覆盖 step。

FinalizationHooks 显式绑定结果准备与发布。事务型 prepare/freeze/abort 必须一起声明；freeze 只冻结暂存结果，CaseExecutor 在全部清理与验证完成后原子 seal。可选方法名称本身不再隐式注册发布行为。

SolverSemanticExtension 同时声明 prepare_run、setup、project_context、checkpoint_components、should_execute_step 和 cleanup_components。共享控制器按 reset → semantic setup → Adapter setup → queued restore 执行；停止扩展不能绕过共享 deadline。checkpoint 组件名称冲突直接失败，不能抢占已有状态所有者。cleanup_components 返回独立命名回调：即使 Adapter 清理或另一扩展的清理发现失败，其余回调仍会被尝试；首个异常保留，全部失败通过 BlackBase failure evidence 的 solver_teardown 字段跨 Case 传输。清理必须容忍 setup 只完成一部分。

MOEA/D setup 仅准备运行面；新种群在首次实际派发后经正常 repair、求值和接纳建立，完整 bootstrap 后发布方向视图。待恢复信封由共享恢复槽安装 Unit 与 Authority，不维护私有 loaded 标记，也不在 setup 先建立临时种群。

LearningSolver 已移除 build_context/setup/prepare_fresh_run/teardown/checkpoint_components/should_execute_step/init_population 的覆盖，ML 组件通过上述端口参与。init_candidate/evaluate_individual/run/export_case_result 仍提供领域输入或返回值门面，不能引入第二次评估或第二套循环。ML 的 get_state/set_state 保留领域信封，恢复顺序由 RunSession 控制。LearningSolver 仍是语义门面子类；新增控制行为必须使用已声明端口。

RepresentationCapabilities 是候选管线能力入口。CandidateCodec、SearchOperator、ConstraintRepair 区分编码、搜索、约束修复；组件可仅实现需要的部分。缺少声明或声明的方法不可调用时拒绝执行。codec 确定性和 repair 幂等性需要组件声明及行为测试，不能由方法名保证。

RepresentationPipeline 的显式数据 codec 保存自身 RNG 和声明了 get_state/set_state 的算子状态；共享实例只按首次槽位保存一次，同时验证别名布局和配置身份。只复制这些 Mapping 数据，不复制算子对象、锁或 kernel。管线经 solver.representation 参与原步骤事务；含显式状态所有者的管线是 required checkpoint component，缺失状态的旧文件不能猜测恢复。有状态声明却无 codec 时拒绝；这不证明任意未声明第三方内部状态可恢复。

ParticipationContract 按域声明 observe/advise/decide/veto。Plugin 默认具有 context 建议面；评估接管和严格发布否决须显式声明。Controller 的输出限于 owns_domains。正式入口执行检查，任意直接 Python 写入仍需静态规则与行为测试补充。

## 偏好与原始反馈

PreferenceProvider 声明 preference_keys，返回 PreferenceDelta(key, delta, reason)。当前优化选择投影支持 objectives.<index>，硬约束键不可通过偏好接口改写。已有 compute/apply 组件保留正式装配入口，并形成可审计的选择投影。

Feedback.info.raw_evaluation 保留首次原始目标和违规量；preference_deltas 记录偏好及显式选择策略。批量 raw_objectives/raw_violations 提供只读原值；子集选择及 wire/checkpoint 往返保留证据。旧 ignore_constraint_violation_when_bias 可令选择违规量为零，不能据此声称硬约束满足。

FeasibleEvaluationAcceptance 使用 `feedback.raw_violations`，有限且不超过 constraint_tolerance 才接纳；处置 metadata 显式标注 `constraint_view="raw_evaluation"`。Bias 可以改变算法排序，不能打开硬可行性准入门。按选择视图准入须另写具有明确含义的 EvaluationAcceptancePolicy。未配置可行性策略时框架仍允许算法搜索不可行区域，不自动安装这个门。

Evaluation Provider 交付未经 Bias 投影的反馈，不能自行调用 `_apply_bias` 或根据选择软化开关清零原始违反量。候选级指标通过正式 `Feedback.metrics` 交给唯一的控制面投影；不依赖一次私有 `build_context` 的临时写入。代理预测与低/高保真混合属于 `approximate`，调用者须显式允许近似评估；其 raw 值表示该 Provider 的未加偏好输出，不可冒称全部来自高保真 Problem。逐行 `evaluation_fidelity` 区分 surrogate/true 或 low/high。

Solver 的 `evaluation_count` 在正式派发时按候选行计费，Provider 不再次递增。代理的真实调用、低/高保真调用以及隐式求解次数由各自 `stats` 解释；`Problem.evaluation_count` 只统计实际调用该 Problem 的 evaluate，不把未调用它的隐式数值迭代或代理预测伪装成同一个计数。拒绝或步骤回滚不返还已经消耗的求值预算。

ML Bias 原本还支持 project_context；adjust_feedback 链同样保留原始评估。将 Bias 概括为只有目标改写一种能力并不准确。

## Unit 与比较范围

Unit 的运行实例归具体 Adapter，问题 Pipeline 不提前创建所有算法结构。UnitBinding 提供规则而不拥有可变搜索状态。UnitBackedAdapter 配置完成、setup/fresh reset 后可保持 algorithm_unit=None；实际需要时 ensure_unit 创建一次并复用。暂停后继续保留已有结构，显式 reset 只解除结构，首次再用才构建。运行内显式成员维护和结构重建仍按实际算法操作执行。

未创建状态进入步骤快照和 checkpoint，并保存绑定契约；读取状态不调用 builder，恢复已存在 Unit 只用 codec，回滚须恢复创建前的缺席状态。Doctor、运行投影、字段读取、偏好装配和 get_operator_unit 不得制造结构。显式 builder.unit_type 可供声明检查，实际值和特征计算留到运行。UnitPreferenceBias 从所属实例的稳定 Unit ID、schema 与 owner_path 绑定身份；未激活视图为 None，实际消费偏好时明确拒绝，不以提前构建满足依赖。UnitRepair 可在未创建时绑定声明，实际修复仍要求当前真实 Unit。

种群 Adapter 保留搜索决策，`PopulationUnit.apply_selection` 按明确的旧成员/新提案索引同步 X/F/V/token；`initialize_population`、`replace_evaluated_rows`、`clear_population` 共享成员维护入口。自定义行字段声明 member_fields，on_members_changed(PopulationChange) 只读原数据并返回扩展字段更新，全部 codec 脱离与草稿 validate 成功后才发布。恢复不重放钩子；参考方向和子问题槽位不按数值猜成员身份。实际覆盖与限制见 [Unit 成员维护](UNIT_MEMBER_OPERATIONS_CN.md)。

Unit 保留候选或集合并扩展算法特征与必要状态；构建与取出候选不隐含 encode/decode。`FeatureUnit.feature(UnitFeature)` 按实例维护声明依赖的派生结果，区分 none/raw/selection，检测依赖变化；缓存不进入 codec。NSGA-II 排序和种群距离已接入。历史、路径和动量仍是持久算法状态。完整职责、执行顺序和限制见 [Unit 特征维护](UNIT_FEATURES_CN.md)。

PopulationUnit 的 objectives/violations 分别保存候选版本，部分反馈更新经过 codec 后仍不能被视为完整求值。`attach_feedback` 成对附加完整反馈；`replace_evaluated_rows` 在校验后的副本上维护候选、反馈和 token，供 DE/MOEA/D 接纳替换使用。该局部操作不接管搜索决定或整步事务；非法输入不能留下半更新的行，原有过期反馈不能被一次局部替换重新认证。

mutate/mutate_batch 不隐含 repair。默认提案的 repair 在预算裁剪后执行一次，随后通知 Unit 所有者；初始化与 update 内新状态另计阶段。显式 JointRepairPolicy 可开启有限轮 ProblemRepair/UnitRepair，使用 codec 草稿，在同版本上共同验收；循环或次数耗尽回滚后由 Adapter 决策。默认与共同修复路径均在修复前捕获局部参与者状态，零接纳恢复相应子树，保留已消耗评估成本。部分接纳先经 Adapter disposition 整理坐标，再由显式 project_admission 投影修复效果并重验；draft 已是接纳坐标，不得使用原始索引二次裁剪，admission_unit_fields 声明字段须保持。之后才进入 update。

on_rejection 默认停止，重试与推进串行阶段须显式选择。advance 先规划所有受影响分支，再在独立决策事务中整组执行；执行异常或取消整组恢复，不制造逻辑代。退出阶段的资源清理延后到决定生效后，失败进入 checkpoint 队列重试。修复轮间与决策边界复用 Case cancellation/deadline；失败证据保留 owner/索引/token。详见 [共同修复契约](JOINT_REPAIR_CN.md)。

轨迹/区域候选关联反馈保存于 Unit.candidate_feedback，候选依赖变化使旧分数失效；trajectory/poll/parameters/local_region schema 为 v2，旧 v1 不自动恢复或重新求值。具体归属与历史指标区别见 [Unit 特征维护](UNIT_FEATURES_CN.md)。`get_proposal_contexts` 在复合层保留每行原任务。需要 Unit 的叶变异组件声明 UnitInputSpec，由实际 Adapter 传只读 UnitInputs，不借共享 context 隐式绑定。使用方法见 [算子 Unit 输入](UNIT_OPERATOR_INPUTS_CN.md)。

Pipeline 可注册 mutation_operators；叶 Adapter 通过 set_mutation_operator(name) 选择，省略名称使用默认 mutator。多个异质 Adapter 共享问题修复/编解码而按需选择搜索算子；选择不修改共享默认项。名称及 Unit 依赖须显式匹配，不能失败后换用默认算子。共享注册表不克隆有状态算子，恢复时要求一致装配；本契约不保证任意算子的状态隔离、线程安全或恢复等价。

Adapter 通过 operation_methods 声明实际消费的初始化、变化、选择和结构修复角色。绑定声明 checkpoint_identity 与显式 stateless 或 Mapping 状态 codec，由实际叶 Adapter 唯一拥有并纳入步骤快照与 checkpoint。UnitBackedAdapter 共用该 codec，包括专用算法步骤快照；独立状态所有者显式集成。恢复缺失绑定或身份不符直接失败，后续算法恢复拒绝时补偿已恢复的组件状态；不据此宣称任意第三方坏载荷恢复完全原子。Pool 输入与暖启动优先，直属 initializer 只生成新提案；基准求值走正常控制面，不由组件偷偷调用 Problem。

NSGA-II/III、SPEA2 的 parent_selector 返回精确父代 SolutionRef；selector 的 offered-row 请求按 purpose 区分 survivor、replacement、candidate、proposal_order，严格校验局部整数索引的数量、唯一性和范围。它不是任意 frontier/阶段调度的通用选择器。SA 的排列仍经过 Metropolis；VNS/Pattern 的提名仍经过原改善与结构守卫；MOEA/D 使用当前方向的分解分数；DE 使用提案时冻结的目标基准。Request 与可选 UnitInputs 均只读，参考 Unit 初始时可能为空，待选候选与反馈在 Request 中。Doctor 不创建 Unit 或计算特征，使用已有实例或显式数据类型检查可证明的字段要求，实际调用仍严格捕获依赖。

直接 mutator 优先于默认 Pipeline，且与具名 Pipeline 选择互斥；变化派生提案身份，repair 保持提案 token。set_repair 绑定已有 UnitRepair/JointRepair 入口，不能搬走问题可行性权威或增加一次提前修复。每族的实际支持和拒绝边界见 [Adapter 行为装配边界](ADAPTER_OPERATION_BOUNDARIES_CN.md)，首轮用法见 [局部算子绑定](ADAPTER_OPERATOR_BINDINGS_CN.md)。

Unit 也是偏好依赖与比较范围的中心。`PreferenceQuery` 区分候选、候选相对 Unit、整个 Unit 和 Unit 变化；`UnitView/PopulationView` 通过实例路径、结构身份与内容 revision 绑定只读依赖。`UnitPreferenceBias` 接入选择投影，整体结构的选择仍由 Adapter 决定。详见 [Unit 与偏好契约](UNIT_PREFERENCE_CONTRACT_CN.md)。Tabu 评分只读；已提交接纳提案的记忆通过 BiasModule 进入既有步骤事务和 checkpoint，不能按评分调用次数更新。

PopulationView 的行表示槽位，允许多个槽位携带同一 candidate token。UnitPreferenceBias 的 `owner_path` 绑定参考 Unit，`apply_to_paths` 绑定消费候选的 StrategyOrigin 路径；默认全局，限定范围时来源缺失不适用、来源损坏报错。矩阵行的 provenance 只按与当前活动批次的精确内存视图关系恢复，不按数值或独立调用的 individual_id 反查旧身份。

## repair 与 Unit 对账

`nsgablack.adapters.ProposalRepair` 和 `AlgorithmAdapter.on_proposal_repair` 属于优化提案协议。控制面在问题管线 repair 前保存脱离的 CandidateBatch，repair 后生成同 token、同行数/维度的 before/after 证据。变化判定包括 UnknownState metadata，不能只看数值。它在 Problem/Provider 调用、Event 写入和最终 BatchDisposition 之前交给原提案所有者。

`proposal_indices` 指向原 pending 列表，`proposed_count` 是完整提案数；预算只允许前几行求值时，其余行不进入 repair 证据。复合 Adapter 用 `for_range()` 转为子范围，存在本地截断/筛选时用 `through()` 还原子提案索引。这一步不筛除 pending，也不发送提前的 disposition；评估后再发送一次预算与接纳组合的最终处置。

ProposalRepair 是一次调用内的脱离值，不进入共享 ContextStore，也不另立持久权威。它对账成功后的候选由 Evaluation Event 和 Authority Snapshot 保存；对账失败在评估前结束，恢复不重放 repair hook。

`individual_id/individual` 是 build_context 的调用局部参数，不继承旧 ContextStore 值，也不自动写回共享存储。否则批量 repair 可按上一轮 individual_id 解析旧 metadata，造成数值未变、语义倒退的错误；两代同数值不同身份以及 ML 梯度路径必须覆盖这一情况。

hook 返回 None 表示允许继续；不变量无法恢复时抛错，由现有步骤事务回滚，Problem/Provider 不执行且不消耗评估预算。普通无结构约束的提案允许替换；不允许提案替换的结构所有者必须显式实现对账，否则拒绝变化。未实现路由的自定义复合 Adapter 遇到变化也拒绝，不能把父级的“允许替换”当作子级同意。Doctor 仅检查 hook 是否可调用，算法不变量靠行为测试确认。

A*/MOA* 默认在评估前按 `repair_policy="reject"` 拒绝改变的候选；显式 recompute 时重新计算父边 base_g，update 用修复后的状态重建 h、节点/标签及支配关系。直接调用 update 的旧边界仍保留变化检查。recompute 不证明邻接合法，领域 edge_cost 必须能解释该边或抛错。CandidateProposerAdapter 用原 Unit ID 重建变化的候选 Unit。信赖域按实际采样度量校验：DFO/MO/nonsmooth 为 box 无穷范数，subspace 还要检查子空间残差及基坐标半径；不合格不做隐式二次投影。

## 可检查范围

Context key 的通用词汇与注册机制由 BlackBase 拥有；优化词汇位于 nsgablack.context_keys，ML 词汇位于 mlblack.context_keys，已有 wire 名称保持不变。语义包发布不可变 namespace；Project/Case 使用 `context_keys.json` 字符串数组声明扩展键，Doctor 与标准 builder/run_case 读取同一声明。动态扩展在 `context_key_scope()` 内调用 `register_context_keys()`，注册后立即被 ContextContract 校验消费，作用域结束恢复；跨线程须显式传递 `ContextKeyRegistry`。这不是把某个 Case 的配置提升为进程全局注册表。

UnitBinding 的自定义 dump 必须返回 Mapping，内部只能是显式 codec 产生的 JSON 数据值。边界执行脱离复制，拒绝循环、非字符串键、锁/session/executor 等活对象；恢复校验 schema/binding 与 unit_id，并且不调用 build。图节点父 key 的 tuple/bytes 使用显式标签，保存恢复不能改变可哈希身份。

ParetoArchive 与普通种群一样保留 CandidateBatch 的语义状态和 token；每次行筛选与截断同步应用到 X/F/V 和身份。重复 token 替换，数值相等但 token 不同的候选保持独立。最终发布 PopulationSnapshot 后才允许结果导出。只写数值 Pareto 视图会清除旧语义快照，不能复用过期身份。

Case 的公共装配实现位于 `nsgablack.project.case_support`，无优化依赖的图导出位于 `blackbase.project.graph_export`。Case 侧保留显式薄导出及本地依赖绑定；每次 create_bindings 产生独立 builder 字典，不共享可变注册状态。

Catalog 的 recipe-status 区分 guidance/template/signature-checked/unverified；签名通过不是行为证明。专用 Case 的运行由行为测试确认。静态 Catalog 同步的 import_ok/params_ok 为 null（未检查），不得转换为 true 或 false；数据库后端保留该三态。

运行入口与 Doctor --build 共用 inspect_runtime_contracts，检查能力、参与者、权威登记、发布和偏好声明。Snapshot identity、候选 token、部分接纳、恢复和故障窗口由契约测试验证。Doctor 静态扫描仅覆盖支持的语法与局部数据流，不能替代算法或安全证明。

### 多策略调用作用域（2026-10-09）

`StrategyTask` 是 nsgablack 搜索任务值，不是 Project/L0 的 Task。每次提案分配独立 task_id；owner_path 标识组合中的实例，parent_task_id 记录嵌套调用。同一种 Unit/Adapter 可以重复实例化，但角色名必须唯一，多个实例不得共享同一个可变 Adapter 对象。位置编号仍要求恢复时保持同一装配拓扑；改顺序或改角色名须显式迁移，不能依赖类型相同推断身份。

子 Adapter 使用 `StrategyTask.from_context(context)` 读取角色、阶段、区域、种子和原提案预算。局部 role/strategy_id/phase/region_id 等键全部从任务派生，在 repair、disposition、update 重建；task.budget 不随接纳数改变，接纳事实只由 BatchDisposition 表达。全局生命周期字段可以更新，不能覆盖局部任务字段。工厂可以使用实际操作协议，不要求为观测对象额外继承基类。

每个候选在 `UnknownState.metadata` 携带 `nsgablack.strategy_origins`，用 `StrategyOrigin.from_candidate(state)` 取得从外到内的来源。元数据随既有 CandidateBatch/token/provenance、repair、接纳筛选和 Snapshot 保存；不创建第二套候选 ID。来源记录实际 proposal_index，数值相同的行仍可独立追溯。再次提案会得到新的任务来源，不能沿用旧调用身份。

`candidate_roles/candidate_units` 是当前组合层分配区间的派生展示。`unit_tasks` 按 owner_path 输出轻量任务摘要，使用独立 summary schema，仅给 seed_count，不发布种子和区域数组。`strategy_instances` 按子实例收集观测，保留子层投影健康证据；子层的 task/role/strategy_id/phase 等字段不扁平合并到父 context。父层不再发布“最后一个子任务”作为全局任务。

恢复 schema 为 `nsgablack.strategy_router_state/v4`，步骤事务为 `nsgablack.strategy_router_step_transaction/v3`。恢复核对实例集合、类、任务所有者与冻结的调度配置；实际 StrategySpec/RoleSpec.weight 单独保存并回滚。首次 setup／状态捕获前可完成装配，之后变更 cfg 须重建或迁移；fresh setup 恢复初始权重。缺失调度声明／权重的旧状态要求显式迁移。Doctor 的 `strategy-task-contract-invalid` 检查已物化的实例和任务；任意 Python 工厂副作用不属于该检查的证明范围。

Catalog source/MySQL/PostgreSQL 共用 registry.apply_catalog_profile_entry。SQL 条件只是查询优化；过滤保留 artifact、phase、contract、metadata 等完整字段。default 与 framework-core 必须同时验证。

异常处理区分三类：策略、初始化、RNG 和权威状态采集失败直接传播；已知输入/格式/IO 失败只捕获预期类型；可选后端、界面和观测降级使用 report_soft_error 形成限频记录。checkpoint 无法脱离活对象或无法取得组件状态时，不得返回原对象或遗漏组件。Doctor 支持局部返回的失败信封，以及源码可解析的继承契约（C3 顺序、命名导入、静态重导出）；动态基类或动态 __all__ 不推断为已满足契约。静态通过不等于所有业务异常已被证明可观测。

## 解池统一接入补充（2026-10-14）

SolutionPool 在算法运行初始化前建立；配置实例的构造顺序不代表候选执行顺序。MOEA/D 首次派发才建立和评估起始种群，完整 bootstrap 后发布方向。输入绑定、起点基准、搜索反馈和结果交付必须使用同一任务解释。

池与 manifest schema 为 v2；全部子池具有身份和版本，普通集合、选中结果与投影是不同视图类型。名称和创建者选择同一投影视图不得改变语义。refine 的 output 聚合接纳提案，get_pool_refinement_results 明确返回准确选中版本；普通结果也能继续按创建者选择。透明包装通过 pool_result_owner 解析真实实例。

SA、PatternSearch、SingleTrajectoryAdaptive、VNS、GaussianSearch、MAS、有限差分 GradientDescent 和四种信赖域 Adapter 支持普通／投影精修。任务结果是已评估的明确选择；探索 current 与 task-best 可不同，二者分别保护。MAS 的训练历史保护实际反馈的准确版本，所有目标模型完成训练后才参与提案筛选。Subspace 的参考样本来自本任务已接纳版本，默认最多 256 条，不借别人的全局 population。详细覆盖见 [池与 Adapter 接入契约](SOLUTION_POOL_ADAPTER_READINESS_CN.md)。

VNS 只对有本次 Event/token 证据的、内部生成且未评分的拒绝起点安排重新初始化；显式池输入、手工点和未知来源的旧 checkpoint 保持原输入重试。停滞重启在下一次提案执行，完成当步保留准确的已评估选择；待重启标记参与回滚与 checkpoint，不能把未评估后继当作精修结果。具体起点、预算截断、取消与 RNG 时点约束见 [解池任务说明](SOLUTION_POOL_CN.md)。

有限差分的起点、成对探针、下降 trial 分三次派发求值；单侧接纳不能产生该维度梯度，尚未求值的 trial 不能覆盖中心及其评分。GradientOptimizer 支持普通精修，交付已评估前驱中的任务最佳，不给新参数沿用旧损失；仅变换目标而没有同步梯度/Jacobian 的投影视图明确拒绝。Provider slots 仍由原事务维护：没有 transition 不退休活 slots，失败恢复旧 slots，未确认释放的引用保存为清理债务。

数值精修器的已评估 Unit 候选须与所持精确收据交叉验证，不能只检查 ref 自身而放过已变更的内存值；缺失候选同样拒绝。Gaussian／有限差分核对同义当前评分，GradientOptimizer 的未评估后继保留独立状态。MAS 在模型重建前拒绝兼容载荷与 codec Unit 的历史矛盾，历史候选另须对应其保留的池版本；此验证不重跑求值或偏好。

A*／MOA* 仅通过显式 `pool_start_policy="new_root"` 支持单个池种子初始化；修复、求值和接纳成功后才建立新根，不继承来源路径 g。不声明通用 refine／restart／目标投影。节点、标签、父路径及结果保存准确引用；A* 的 best_evaluated 与 MOA* 的 nondominated_path_labels 仍按各自结果含义交付。

NSGA 家族与 DE 发布普通 population 视图，MOEA/D 发布方向投影视图。Evolution 初始化和恢复用 `set_population_state(control, batch, feedback, solution_refs=..., provenance=...)` 交付候选身份、原始反馈和准确收据；`get_population_solution_refs(control)` 是对齐成员行的有序引用，允许重复槽位，不能用无序回收根代替。Role、EliteRetention、StrategyChain 和单子 Composite 可转发完整交付；不支持的 L2 配置在 setup 阶段拒绝，多子 Composite 保持分区语义。旧三数组环境选择须显式 `external_evaluation=True` 断言外部原始求值并导入新身份，不追认旧池版本，也不虚增 Problem 调用。

Evolution 初始化复用步骤事务，保存池、权威状态和证据，但不制造逻辑代或物理尝试；步骤语义扩展仍只用于普通步骤。显式池输入按最终接纳的原提案索引结算，预算外和未接纳种子保持可重试；问题 repair 不因完整身份交付再执行一次。

## 自然搜索编排补充（2026-10-21）

BlackBase ExecutionPlan/ExecutionCursor 只持纯值结构与有限执行进度，不拥有叶执行、资源或新提交权威。
SearchPlanAdapter 复用 StrategyRouterAdapter，按已接纳的非空子更新推进局部额度；serial、multi 全体汇合与有限 repeat 可以嵌套。
同 owner 串行位置复用一个算法实例，潜在并行占用拒绝；循环和暂停不重放 setup，不提前 teardown 后续还会使用的实例。

原 StrategyTask 仍拥有调用作用域。计划的 label/count 在提案之前绑定，repair/disposition/update 沿原任务路由。
父级先解释孩子正常完成；只有根计划完成或全局停止才结束 Solver。等待和纯控制切换不制造 generation。
游标、条件观察、激活身份、预算轮转与池任务共同恢复；实际失败回滚本次状态，真实求值成本保留。

refine/compete 新激活开启稳定新请求，重试/恢复沿用原请求；initialize 默认仍只初始化一次。
实际启用的 refine/compete 叶省略正数 steps 并等待任务完成，不用 until 提前丢弃未完成队列。
get_pool_task_results 只交付当前 done 精修请求已经发布的最终选择；核对原发布的 Pool／视图身份、修订、解释、创建者与有序精确引用，不按同名重建读取新结果。output=None 也交付最终视图，显式 output 才额外保留累计 accepted 历史；最终视图仍是保留根，消费后按原 Pool 方法显式释放。已启动任务缺结果收据的旧状态须迁移。
Pool 写继续归原选择/更新事务，独立无送评 Pool 编辑尚未开放。详细接口见 [自然搜索编排](NATURAL_SEARCH_PLANS_CN.md)。

嵌套组合通过 on_schedule_activation 通知局部调用；只有已完成子编排重开游标，未完成子编排保留执行 scope 和冻结任务，均不重放 setup。旧 Chain 消费正常完成再推进；作为可重复子组合时不提前退休孩子。Router 空分支取消立即向已提案兄弟发送零接纳并上抛，不能等所有分支无候选。running PoolTask 的内层普通 terminal 目前明确拒绝，不能升级为整批 done 或制造空提交；取消／明确 stop 仍传递。

内部组件可在实际类上直接声明 catalog_owner_type，归属一个已在 Catalog 按对象身份解析的真实基类。
Doctor 不继承该豁免，不因任意子类继承了已注册类就视为注册；声明不是算法行为正确性证明。

## 三类算法语义补充（2026-10-22）

BayesianOptimizationAdapter 将真实观测与候选成员分开。完整 Evaluation Event 验证后按运行、事件、原行号幂等消费；便携模型数据集携带原 Snapshot 内容身份和必要值，不向新 Journal 伪造历史事件。首版仅保证无求值接管的直接 Problem 路径；individual_fallback 标签本身不能证明真值。修复不得改变算法观测绑定字段，模型缓存由固定解释和训练证据重建；采集函数/搜索器须声明无状态。

CMAESAdapter 以完整 cohort 更新正权重完整协方差分布。四个已评估样本与两个重组父代是不同集合，预算/接纳裁剪不得静默更改 lambda。首版对 changed repair 在送评前拒绝，对残缺 cohort 拒绝分布更新，真实求值与成本仍保留。均值、协方差、路径、步长、组件及 RNG 一起回滚/恢复；未求值均值不是可交付候选。

MapElitesAdapter 的 Unit 唯一拥有格子冠军；描述符、格子映射、质量竞争与生成器分别装配。公开 Pool 视图只引用真实冠军的准确版本，档案 raw 反馈必须与 Pool 一致。普通 emitter 可逐条消费部分接纳；emit-only 接口不代表支持需要联合反馈的自适应 emitter。仅显式耗尽声明支持正常终止，空提案不自动判完成。

三个算法均不另造 Solver 生命周期、Project 执行器或 L0 授权。公开接口、标准 Case、验收反例及限制见 [三种算法语义验收](ALGORITHM_SEMANTIC_ACCEPTANCE_CN.md) 与 [标准 Project](../../examples/cases/algorithm_semantics/README.md)。


## 完整子 Case 的候选绑定与结果投影（2026-10-29）

`CaseInnerRuntimeEvaluator` 用共享 `ChildCaseCall` / `CaseStageRunner` 调用一个完整标准 Case。每次求值可通过 `component_overrides_factory(solver, candidate, context)` 生成本候选的轻量装配参数；candidate 是脱离的只读数值视图，返回值必须是 Mapping。已经绑定的 CandidateProvenance 随正式 inputs.candidate_provenance 传递，工厂上下文可读取 `_candidate_provenance`；缺失身份时不能按局部行号或相同数值猜测。要求身份的应用应在派发前明确拒绝缺失 token。

`projector` 必须显式解释子结果与外层目标的关系，可以返回 `(objectives, violation)` 或共享 `Feedback`。后者用于携带核验后的发布收据与谱系；不能把输入 x 的目标直接换成内层找到的另一个 y 的分数而丢弃 y 的身份。供排嵌套的外层候选本身是供应方案，内层排程是该供应方案的求值产物，二者应分别保存并通过正式收据关联。

`termination` 独立于超时设置，显式传入子调用的 ExecutionControl。默认不擅自把父级硬隔离策略强加给每个叶任务；需要保护全局随机流、锁或外部运行环境的完整子 Case，应使用正式进程隔离，并在 builder 之前建立边界。超时、取消和子 Case 失败保持结构化错误，不降级为供料总量、零产量或成功占位分数。

BudgetHandle 构造后递归冻结 authority/metadata；as_dict 导出脱离的普通 wire 容器。完整 CaseRunRequest 的公开字典可经 JSON 或进程传输，不传递带 mappingproxy 的活对象图。原始算法求值与发布审计的独立预算分别结算，不能把 charged_to_parent 再算成一轮额外求值。

## 状态减负与完整子 Case 批次（2026-10-30）

共享后端的取消检查在同一 Redis authority 内原子读取谱系并续期；每次检查仍即时读取，不以 TTL 缓存替代取消与完整 lineage 校验。
Case 拥有的 Artifact 连接与 fence pool 在该 Case 内复用，每次验证保留；CaseExecutor 在 seal、观察及最终 audit 后关闭自建 Publisher，构造失败也释放。
短期 Project 收据验证器独立释放连接，清理失败不得覆盖原始验证失败或伪造发布回滚。
外部调度的声明静态校验仍在装配时执行；后端和目标运行实例按实际使用启动。
未初始化的审计明确为 unknown/None，不能被解释为零占用。优化不增加语义层的资源所有者，完整契约见 BlackBase 的 RUNTIME_COST_REFINEMENT_CN.md。

同一外部 Dispatcher 的兄弟调用共享一次在途过期扫描，只有成功扫描才推进本地扫描时间；各调用仍读取自身实时任务，并核对最终身份和围栏。Redis Transport 在原锁内批量读取和恢复，不修改锁期限或重试语义。失败信封的预算观察再次失败时，原错误保留，独立记录 budget_audit_failure；用 usage_status=unknown、数值 None 和 consumption_uncertain 表示未明，不能当零消耗或结算收据，原隔离与持久结算日志继续负责债务。

SnapshotStore 单次 write 内可复用已安全隔离、已证明 wire 稳定的数据准备结果，保持原摘要 codec/schema 和读取校验。
协议对象及规范化容器不猜测摘要等价，不按对象 id 跨调用缓存。Pool 的拒绝处理通过
`RuntimeTransaction.reconcile(pool, pool.reject_attempt)` 复用原捕获基线；仅同 owner 绑定方法可只读消费，事务仍可完整回滚。

`CaseInnerRuntimeEvaluator(artifact_bindings={"child_name": "parent_name"})` 从当前父请求的正式
`input_artifact_bindings` 转交原发布 binding。父名缺失在 dispatch 前拒绝；单点和批次走相同规则。
Solver 的 `set_input_artifacts()` 仅冻结注入的 DataRef 映射；读取和发布权威仍来自 Case runtime，
不能用注入引用代替发布收据。跨操作系统的公共 Artifact root 可由 Project 的
`L0.artifacts.authority` 显式指定，须匹配本进程可信 HTTP profile；不能重解释成主机本地路径。

`CaseInnerRuntimeEvaluator(max_workers>1)` 在标准无 Provider fallback 中以并行 CaseStage 派发一批完整 Case，
`evaluate_batch` 交付按输入顺序的逐项投影；外层约束、Bias、hooks 和状态更新仍串行。
有 Provider 或自定义 mediator 时保留原仲裁。整批 dispatch 计 N 次外层求值，子预算沿原授权链独立结算。

Project 可通过 `L0.nested_execution.case_names` 显式选取外部执行的内层 Case，复用 project_case transport/Worker。
远端 grant 由目标共享持久 L0 ledger 授予，不继承父本机物理容量；未命中的下层调用保留 local。
实际 attempt 身份、预算 handle、grant、fence 与发布收据须一致。执行不确定时不得猜测已终结或返还未用预算。
装配、测试和跨机前提见 [状态减负与内层批量执行](STATE_COST_AND_NESTED_EXECUTION_CN.md)。


### Pool 选择的实际数量与成员属性读取（2026-11-12）

普通生存选择函数显式声明 `count`（例如 choose(pool, *, count, rng)）时，由本次 SelectionRequest
提供数量；不从配置副本推测。旧无 count 函数保持原调用，显式 partial 固定 count 不被覆盖。
自动数量绑定使用 pool_selection/v2 身份；固定数量及无 count 路径保留 v1，不自动迁移 checkpoint。

Pool 成员属性读取基于所属 Unit 的本次槽位坐标，重复 SolutionRef 不合并槽位。
最终成员可省略 default；有新提案必须显式给出初值。默认值不能静默损坏已有整数精度。
结构数据复用 Unit 的封闭数据 codec 和脱离只读入口，不计算 feature digest。
此读取不改变候选、成员维护规则、预算或恢复顺序。跨来源 Pool 不自动拥有统一成员属性。


父代 Pool 交接：NSGA-II/III、SPEA2 在父代选择时冻结真实 Unit 槽位字段，ParentSelectionRequest.members 与返回的 Pool 保留出现位置。有序引用返回必须能唯一对应所属成员槽位；外部引用下标为 None，重复槽位不可猜测。完整 ChangeRequest.parent_pool 在变化结束后失效，parent_member_indices 随来源证据保存，不属于新的运行可写状态；恢复不重放选择或计算字段。字段读取不得构造 Unit。


Router共享档案：StrategyRouterAdapter可拥有pool_maintenance绑定，在本次实际非空子更新完成后执行一次。members_by_owner按实例所有权路径交付自有最终成员，members只聚合引用而不混成权威种群或统一评分；无种群叶不冒充种群。成员计划加入原池事务；子/父同目标冲突继续拒绝。绑定codec参与Router checkpoint与局部步骤快照，不嵌套复制子状态；取消、零接纳和无提案不额外提交。跨独立Case及多机异步归并不由此接口提供。
