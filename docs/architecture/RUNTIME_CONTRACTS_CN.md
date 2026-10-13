# 运行所有权与显式扩展契约

最后按代码核对：2026-10-13。本文描述当前实现；解池本轮验证见 [解池验收](SOLUTION_POOL_VALIDATION_CN.md)，其余边界验证见 [验收记录](../development/RUNTIME_REFINEMENT_VALIDATION_CN.md)。

## 保留的主线

Problem 定义问题；问题管线处理候选；算法管线构建 Unit；Adapter 操作 Unit 并作搜索决策；Bias 表达偏好；Plugin 提供声明的能力。Solver 保留公开装配门面，运行状态、事务、证据检查和结果发布分别有明确的所属对象或协议。

必须保护候选值与身份分离、活状态与持久数据引用分离、部分接纳显式成值、Unit 按绑定 codec 恢复。Unit 可以提供结构操作，不能拥有第二套求解生命周期。关于“唯一”“最原创”等研究主张需要比较研究，不能由实现核对推导。

## 权威与事务

SolutionPool 在 Solver 构造时先创建，登记 candidates 事实并参与共享步骤事务；大值仍由 BlackBase SnapshotStore 保存。池保存不可原位改写的候选版本、运行时点和输入游标；Unit 保存本算法关系与工作投影。新算法提案使用显式派生 token 并保留源 SolutionRef；读取不换身份，repair 同一提案保持 token。不是为每个成员槽位编造身份。

提交先暂存池 manifest，将引用写入同一目标 Authority Snapshot，权威围栏成功后才公布池索引；恢复只读已验证的 destination manifest。失败/零接纳不让另一阶段读到草稿；部分接纳结算原输入索引，未接纳初始化种子保留。池不自动借用其他算法的选择反馈或重放评估。详细接口、算法支持范围与存储回收限制见 [解池契约](SOLUTION_POOL_CN.md)。

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

verification receipt 可由 Journal 持久化用于审计，但 verified_at 是观测时间，必须排除在语义 content digest、幂等键和证据身份计算之外。重复检查允许时间不同；Event/Destination 的 identity 与 disposition_digest 必须相同，检查本身不得改写 Snapshot、围栏或 Journal。若归档文件包含审计时间，其字节校验和只是该归档载荷的完整性证明，不能替代上述语义身份。

内存与发布快照的一致性通过真实 step 回归断言：step_batch、single、partitioned 均比对数值、CandidateBatch/token/provenance 或每个分区，关联 AuthorityStore 的 destination 与 event cause；下一次 staging 后失败必须恢复为同一已提交投影。这是覆盖指定故障窗口的行为验证，不是对任意直接 Python 写入的证明。

## 显式扩展与失败

SolverSemanticExtension.before_step 属于提交前尝试；after_step_committed 属于提交后投影。后者失败通过 CommittedStepError 保留真实 StepOutcome；循环先记录提交计数和通知，再结束失败运行。ML 投影使用该接口，LearningSolver 不再覆盖 step。

FinalizationHooks 显式绑定结果准备与发布。事务型 prepare/freeze/abort 必须一起声明；freeze 只冻结暂存结果，CaseExecutor 在全部清理与验证完成后原子 seal。可选方法名称本身不再隐式注册发布行为。

SolverSemanticExtension 同时声明 prepare_run、setup、project_context、checkpoint_components、should_execute_step 和 cleanup_components。共享控制器按 reset → semantic setup → Adapter setup → queued restore 执行；停止扩展不能绕过共享 deadline。checkpoint 组件名称冲突直接失败，不能抢占已有状态所有者。cleanup_components 返回独立命名回调：即使 Adapter 清理或另一扩展的清理发现失败，其余回调仍会被尝试；首个异常保留，全部失败通过 BlackBase failure evidence 的 solver_teardown 字段跨 Case 传输。清理必须容忍 setup 只完成一部分。

MOEA/D setup 检查共享 RunSession 的待恢复信封；存在时只准备运行面，跳过新种群的初始化、求值和权威发布，等待共享恢复槽安装实际 Unit 与 Authority。它不维护私有 loaded 标记。无待恢复信封的 fresh setup 保留正式初始化行为。

LearningSolver 已移除 build_context/setup/prepare_fresh_run/teardown/checkpoint_components/should_execute_step/init_population 的覆盖，ML 组件通过上述端口参与。init_candidate/evaluate_individual/run/export_case_result 仍提供领域输入或返回值门面，不能引入第二次评估或第二套循环。ML 的 get_state/set_state 保留领域信封，恢复顺序由 RunSession 控制。LearningSolver 仍是语义门面子类；新增控制行为必须使用已声明端口。

RepresentationCapabilities 是候选管线能力入口。CandidateCodec、SearchOperator、ConstraintRepair 区分编码、搜索、约束修复；组件可仅实现需要的部分。缺少声明或声明的方法不可调用时拒绝执行。codec 确定性和 repair 幂等性需要组件声明及行为测试，不能由方法名保证。

ParticipationContract 按域声明 observe/advise/decide/veto。Plugin 默认具有 context 建议面；评估接管和严格发布否决须显式声明。Controller 的输出限于 owns_domains。正式入口执行检查，任意直接 Python 写入仍需静态规则与行为测试补充。

## 偏好与原始反馈

PreferenceProvider 声明 preference_keys，返回 PreferenceDelta(key, delta, reason)。当前优化选择投影支持 objectives.<index>，硬约束键不可通过偏好接口改写。已有 compute/apply 组件保留正式装配入口，并形成可审计的选择投影。

Feedback.info.raw_evaluation 保留首次原始目标和违规量；preference_deltas 记录偏好及显式选择策略。批量 raw_objectives/raw_violations 提供只读原值；子集选择及 wire/checkpoint 往返保留证据。旧 ignore_constraint_violation_when_bias 可令选择违规量为零，不能据此声称硬约束满足。

FeasibleEvaluationAcceptance 使用 `feedback.raw_violations`，有限且不超过 constraint_tolerance 才接纳；处置 metadata 显式标注 `constraint_view="raw_evaluation"`。Bias 可以改变算法排序，不能打开硬可行性准入门。按选择视图准入须另写具有明确含义的 EvaluationAcceptancePolicy。未配置可行性策略时框架仍允许算法搜索不可行区域，不自动安装这个门。

ML Bias 原本还支持 project_context；adjust_feedback 链同样保留原始评估。将 Bias 概括为只有目标改写一种能力并不准确。

## Unit 与比较范围

种群 Adapter 保留搜索决策，`PopulationUnit.apply_selection` 按明确的旧成员/新提案索引同步 X/F/V/token；`initialize_population`、`replace_evaluated_rows`、`clear_population` 共享成员维护入口。自定义行字段声明 member_fields，on_members_changed(PopulationChange) 只读原数据并返回扩展字段更新，全部 codec 脱离与草稿 validate 成功后才发布。恢复不重放钩子；参考方向和子问题槽位不按数值猜成员身份。实际覆盖与限制见 [Unit 成员维护](UNIT_MEMBER_OPERATIONS_CN.md)。

Unit 保留候选或集合并扩展算法特征与必要状态；构建与取出候选不隐含 encode/decode。`FeatureUnit.feature(UnitFeature)` 按实例维护声明依赖的派生结果，区分 none/raw/selection，检测依赖变化；缓存不进入 codec。NSGA-II 排序和种群距离已接入。历史、路径和动量仍是持久算法状态。完整职责、执行顺序和限制见 [Unit 特征维护](UNIT_FEATURES_CN.md)。

PopulationUnit 的 objectives/violations 分别保存候选版本，部分反馈更新经过 codec 后仍不能被视为完整求值。`attach_feedback` 成对附加完整反馈；`replace_evaluated_rows` 在校验后的副本上维护候选、反馈和 token，供 DE/MOEA/D 接纳替换使用。该局部操作不接管搜索决定或整步事务；非法输入不能留下半更新的行，原有过期反馈不能被一次局部替换重新认证。

mutate/mutate_batch 不隐含 repair。默认提案的 repair 在预算裁剪后执行一次，随后通知 Unit 所有者；初始化与 update 内新状态另计阶段。显式 JointRepairPolicy 可开启有限轮 ProblemRepair/UnitRepair，使用 codec 草稿，在同版本上共同验收；循环或次数耗尽回滚后由 Adapter 决策。默认与共同修复路径均在修复前捕获局部参与者状态，零接纳恢复相应子树，保留已消耗评估成本。部分接纳先经 Adapter disposition 整理坐标，再由显式 project_admission 投影修复效果并重验；draft 已是接纳坐标，不得使用原始索引二次裁剪，admission_unit_fields 声明字段须保持。之后才进入 update。

on_rejection 默认停止，重试与推进串行阶段须显式选择。advance 先规划所有受影响分支，再在独立决策事务中整组执行；执行异常或取消整组恢复，不制造逻辑代。退出阶段的资源清理延后到决定生效后，失败进入 checkpoint 队列重试。修复轮间与决策边界复用 Case cancellation/deadline；失败证据保留 owner/索引/token。详见 [共同修复契约](JOINT_REPAIR_CN.md)。

轨迹/区域候选关联反馈保存于 Unit.candidate_feedback，候选依赖变化使旧分数失效；trajectory/poll/parameters/local_region schema 为 v2，旧 v1 不自动恢复或重新求值。具体归属与历史指标区别见 [Unit 特征维护](UNIT_FEATURES_CN.md)。`get_proposal_contexts` 在复合层保留每行原任务。需要 Unit 的叶变异组件声明 UnitInputSpec，由实际 Adapter 传只读 UnitInputs，不借共享 context 隐式绑定。使用方法见 [算子 Unit 输入](UNIT_OPERATOR_INPUTS_CN.md)。

Pipeline 可注册 mutation_operators；叶 Adapter 通过 set_mutation_operator(name) 选择，省略名称使用默认 mutator。多个异质 Adapter 共享问题修复/编解码而按需选择搜索算子；选择不修改共享默认项。名称及 Unit 依赖须显式匹配，不能失败后换用默认算子。共享注册表不克隆有状态算子，恢复时要求一致装配；本契约不保证任意算子的状态隔离、线程安全或恢复等价。

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

恢复 schema 为 `nsgablack.strategy_router_state/v3`，步骤事务为 `nsgablack.strategy_router_step_transaction/v2`。恢复核对实例集合、类和任务所有者；旧版未分作用域的任务不自动解释为新契约。Doctor 的 `strategy-task-contract-invalid` 检查已物化的实例和任务；任意 Python 工厂副作用不属于该检查的证明范围。

Catalog source/MySQL/PostgreSQL 共用 registry.apply_catalog_profile_entry。SQL 条件只是查询优化；过滤保留 artifact、phase、contract、metadata 等完整字段。default 与 framework-core 必须同时验证。

异常处理区分三类：策略、初始化、RNG 和权威状态采集失败直接传播；已知输入/格式/IO 失败只捕获预期类型；可选后端、界面和观测降级使用 report_soft_error 形成限频记录。checkpoint 无法脱离活对象或无法取得组件状态时，不得返回原对象或遗漏组件。Doctor 支持局部返回的失败信封，以及源码可解析的继承契约（C3 顺序、命名导入、静态重导出）；动态基类或动态 __all__ 不推断为已满足契约。静态通过不等于所有业务异常已被证明可观测。
