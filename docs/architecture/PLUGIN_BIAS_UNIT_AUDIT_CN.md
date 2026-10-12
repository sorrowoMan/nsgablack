# Plugin / Bias / Unit / Adapter 边界审计

> 2026-10-09 后续实现：已新增 [Unit 与偏好正式契约](UNIT_PREFERENCE_CONTRACT_CN.md)，四种评价范围、实例化只读 Unit 视图、候选相对 Unit 的装配桥已落地；修正标准 DiversityBias 的方向/数值身份问题，Tabu 改为纯评分，并把接纳记忆接入步骤回滚和 checkpoint。旧 Bias 对缺失/分区种群依赖会拒绝，不再静默当作空群体。**以下正文保留审计当时的基线证据，不是当前修复状态清单。** A4/A5 的迁移覆盖本次明确声明的偏好，不代表所有旧自适应 Bias 已迁移；A6–A8 的 Plugin 拆分和 A9 的公共 Plugin 读取 helper 仍未在本次改造。A10 已修运行插件 README，其他局部说明仍需逐项同步。

审计日期：2026-10-09  
审计方式：本地源码、装配路径、运行契约和测试源码的静态核对。  
基线：nsgablack HEAD 为 `ec1ae755d9693bb1996dd472e8e116d9f99b9314`；结论针对**含既有未提交修改的当前工作区**，不等同于该提交本身。

## 1. 结论

**需要完善，而且已经存在会改变选择结果的具体问题；但不需要推翻 Problem → Pipeline → Unit → Adapter → Bias → Plugin 这条主线。**

当前主要断点是：Unit 已经成为正式算法结构，而旧 Bias 主路径仍假设“对一个数值候选算一个标量，再加到目标上”。它没有完整表达这个偏好属于哪个 Unit 实例、读取哪一版结构、作用于哪个比较过程，以及偏好记忆在何时更新。少数 Plugin 又绕过这些边界直接改变搜索配置。

本次列出 **10 项发现：5 项 P1、5 项 P2**。其中既有确定的实现问题，也有条件性风险和职责缺口，逐项标明。优先处理评分方向、身份、分区读取、状态更新及恢复；之后再收口组合接口和文档。单纯把文件从 `plugins/` 移到 `bias/`，这些问题仍会存在。

同时确认几项不能再沿用旧批评：

- 精英保留 Plugin 已成为 `EliteRetentionAdapter` 的弃用装配桥，不是原来的独立种群修改器。
- [硬可行性接纳][acceptance-source]现在读取 `raw_violations`，原先被 Bias 软化视图放行的问题在当前实现中已改正；相关行为测试源码也已存在，本次未执行。
- ParetoArchive 已有 token 对齐、目标分段和状态恢复，不能说它没有身份或 checkpoint 契约。
- 评估 Provider 内部使用数值算法，不构成“搜索算法放错到 Plugin”的证据。

### 审计范围与限制

主干口径为 **framework-core 的职责范围**：重点阅读 `bias/`、`plugins/runtime/`、相关 Solver helper、Unit、Adapter 消费端及 BlackBase 共享接口。没有执行 Catalog 命令，也没有把下面的抽样清单说成 Catalog 全量统计。旧示例仅用于说明 API 曾怎样被使用，不计作主干能力。

本次未运行测试、Doctor、builder、benchmark 或示例；没有导入执行框架，没有改动实现。文中的小例子均为源码演算，不是运行日志。测试章节只说明读到了哪些断言，不能据此宣称测试通过。

这是一份针对最近讨论的 **Plugin/Bias/Unit 边界专项审计**，不是对历史全部问题的重新验收；没有重新全面审计 Doctor、Catalog 服务化、脚手架副本、MLBlack 或证据运行时。

## 2. 先把要表达的语义分开

“单解比较、Unit 比较、单解在 Unit 中比较”可以明确表达。关键是同时说明**评价对象**和**依赖对象**。

| 场景 | 被评价的对象 | 依赖的结构 | 偏好或比较输出 | 最终决定者 |
| --- | --- | --- | --- | --- |
| 候选之间比较 | `x`、`y` | 原始反馈、已声明的选择视图 | 次序、偏好分或不可比关系 | Adapter 的选择策略 |
| 候选相对种群的新颖性 | 候选 `x` | 指定 PopulationUnit 的只读视图 | 距离、密度或边际贡献偏好 | Adapter |
| 候选相对历史的禁忌偏好 | 候选 `x` | 明确含义的历史/记忆 | 重访惩罚或建议 | Adapter；硬禁行另属显式接纳规则 |
| 两个种群方案比较 | `P1`、`P2` | 兼容的目标与结构语义 | 整体覆盖度或多样性比较 | 拥有这次选择的 Adapter |
| Unit 的替换/扩展方案比较 | `(U, operation)` | 当前 Unit 与待执行操作 | 操作的边际收益或优先关系 | Adapter；Unit 执行结构操作 |

这里有四个边界需要保留：

1. **依赖种群，不等于评价对象必然是整个种群。** `novelty(x | P)` 评价一个候选，读取一个种群；`diversity(P)` 才评价整个种群。
2. **依赖某种结构，不等于必须硬绑具体 Python 类。** 新颖性也可以读取归档或邻域，只要明确要求的能力、实例身份和版本。不能因都叫 PopulationUnit 就共享一份隐式全局数据。
3. **比较不全是 Bias。** 必须遵守的支配关系、算法生存选择和结构不变量，仍由显式算法策略负责。可选的探索倾向、业务偏好才适合 Bias。
4. **Plugin 是生命周期接入方式，不能自动获得搜索决定权。** 信号采集、指标记录和发布可以是 Plugin；改变 Unit、策略权重、提案顺序的决定必须有明确语义所有者。

当前 `PopulationUnit` 已保存 `unit_id`、population、反馈和 token，并有行对齐校验，见 [PopulationUnit][unit-population]。问题不是缺少 Unit 数据结构，而是这些身份和依赖尚未进入 Bias 主路径。

## 3. 发现总览

P1 表示在相应受支持配置下可能直接改变选择、恢复或权威读取结果，应先修。P2 表示职责、条件性行为或产品说明需要收口。不把尚未运行的案例标作“实测复现”。

| 编号 | 等级 | 发现 | 证据性质 |
| --- | --- | --- | --- |
| A1 | P1 | DiversityBias 的正距离被当作最小化惩罚 | 完整静态调用链 |
| A2 | P2 | 多样性计算把数值相等当作同一个候选 | 明确代码条件 |
| A3 | P1 | 分区种群和读取失败均可在旧 Bias 路径中变成空种群 | schema 与消费端直接不匹配 |
| A4 | P1 | 有状态 Bias 的评分次数被目标维数与缓存命中控制 | 完整静态调用链及可演算例子 |
| A5 | P1 | Tabu 等偏好记忆未接入默认步骤事务和 checkpoint | 默认注册/收集路径核对 |
| A6 | P2 | DynamicSwitch 在步骤事务前直接执行搜索修改回调 | 调用顺序明确，具体影响取决于回调 |
| A7 | P2 | ParetoArchive 同时作为结果归档和隐式搜索输入 | 生产者与消费者已连通 |
| A8 | P2 | DiversityInitPlugin 的拒绝采样方法未接入标准初始化路径 | 定向搜索未发现消费点 |
| A9 | P1 | Plugin 的公共种群读取在权威读取失败后仍会换读其他来源 | 明确异常与 fallback 路径 |
| A10 | P2 | 部分局部文档仍授权旧式隐式修改 | 文档与当前契约直接冲突 |

## 4. 逐项证据与整改建议

### A1 · P1：多样性奖励在默认最小化路径中方向相反

**证据。** [DiversityBias.compute][diversity-compute] 返回正的最近邻距离；[compute_with_tracking][bias-weight] 乘正权重；[BiasModule][bias-add] 执行 `objective_value + total_bias`。NSGA 使用的[支配比较][minimization] 按最小化处理。中间没有把“新颖性奖励”转为负向目标增量的步骤。

**源码演算。** 只启用默认正权重 `DiversityBias(weight=0.1)`，原始目标均为 10，参照种群为 `[0]`。候选 `[1]` 的选择目标为 10.1，候选 `[3]` 为 10.3；最小化选择偏向更近的候选。与类说明“距离越大，多样性越好”的意图相反。该结论针对这个具体组件及加法投影路径，不外推所有 Diversity 变体。

**整改。** 明确偏好输出是“越大越好的分数”还是“直接加到最小化目标的 delta”；转换只能由一个位置负责。保留 raw objective，不靠用户传负权重补救。以后 Unit 级比较也必须声明排序方向。

**验收。** 相同原始目标下，远点相对近点获得预期偏好；单点、向量、批量路径一致；权重为零恢复原选择视图。

### A2 · P2：数值相等被当成身份相同，重复候选被排除出密度计算

**证据。** [DiversityBias._calculate_distances][diversity-identity] 用 `not np.array_equal(x, other)` 过滤“自身”，没有 token 或成员身份。

若新候选 `x=[0]` 与种群中的另一个候选数值相等、token 不同，种群另有 `[10]`，当前计算排除距离为零的那个成员，得到最近距离 10。候选实际上重复，却被计算成很新颖。是否属于同一候选、是否恰好数值相同，是两个不同问题。

**整改。** 读取带 token 的结构视图；只有调用明确声明“排除本成员”时才按身份排除。全新候选与已有成员数值相等应产生零距离。A1 的符号修正不能替代这一项。

**验收。** 覆盖相同值不同 token、同 token 自身、候选尚未进入 Unit、重复值占满种群等情况。

### A3 · P1：旧 Bias 读取不了分区语义，还把读取失败当作空集合

**证据链。**

- [Population Snapshot 契约][snapshot-partition] 禁止 partitioned 权威快照携带顶层 population/objectives/violations。
- [BiasModule._resolve_snapshot_payload][bias-read] 直接 `store.read(key)`；缺 store、缺 key、读取异常或无 record 都返回 `{}`，没有在此验证 AuthorityIdentity。
- [BiasModule._get_or_update_context][bias-context] 只从顶层 `population` 取值，缺省 `[]`；没有 partition、owner path 或 Unit capability 路由。
- [DiversityBias.compute][diversity-compute] 遇空种群返回 0。因此一个合法 partitioned snapshot 进入该消费路径，也会被当作没有种群。

**后果。** 组合 Adapter 中的种群偏好可能静默失效。单种群场景下，真实的 Snapshot 读取故障也可能被消化为“本轮无偏好”。声明 `context_requires=("population_ref",)` 只能说明键依赖，不能证明读到了正确结构。这里不能靠把多个分区拼成一个矩阵补救。

**整改。** 让装配为偏好绑定一个明确的只读结构依赖：实例路径、所需能力、数据版本与身份。区分“合法空 Unit”“依赖未装配”“读取失败”“数据类型不兼容”。声明必需依赖的偏好遇到后三种情况应报错；可选缺省必须在契约中明示。

**验收。** 两个同类型 PopulationUnit 各读自己的成员；嵌套组合不串分区；缺失/损坏快照不能返回正常零偏好；合法空群体遵循明示规则。

### A4 · P1：Tabu 的记忆更新混进评分，多目标和缓存改变算法语义

**证据链。**

- [TabuSearchBias.compute][tabu-compute] 每次计算都会 `_remember(x)`，第一次也会立即写入。
- [compute_bias_vector][bias-vector] 对同一候选逐目标调用 `_compute_bias_value`。
- [缓存命中分支][bias-cache-hit] 在调用 Bias 前直接返回；[缓存 key][bias-cache-key] 包含 objective_value；默认 context fingerprint 为空，未自动包含依赖 Unit 或记忆的 revision。

**源码演算。** 只装默认 `TabuSearchBias(weight=0.15, penalty_scale=0.5)`，初始 tabu list 为空，首次对一个候选计算目标向量 `[10, 20]`：第一个目标记住候选并返回零偏置；第二个目标因 objective_value 不同而不命中第一次的缓存，对刚记住的自己计算零距离，产生 0.075 惩罚，结果为 `[10, 20.075]`。若两个目标相同，第二次反而可能命中缓存，行为又不同。

这不是目标的领域含义造成的差异，而是调用次数泄漏进了偏好语义。同理，清缓存、批内次序、同代依赖状态变化都可能影响有状态偏好。仅加锁可以串行化访问，不能定义正确的语义顺序。

**整改。** 把“基于某版记忆评分”和“把事件写入记忆”拆开。优先每候选/每决策计算一次偏好结果，再显式投影到目标。缓存仅适用于已声明的纯评分，key 纳入所依赖的实例身份和 revision；有状态且未声明可缓存的组件默认不缓存。

**验收。** 目标排列不改变候选是否被记住；相同目标值不改变更新次数；缓存开关不改变选择结果；需要顺序语义时以显式事件顺序定义，而非 Python 调用顺序。

### A5 · P1：偏好记忆没有随默认事务与恢复闭环交付

**证据。** 默认[步骤参与者][solver-participants] 包含 PopulationAuthority 和 incumbent；Adapter 有独立事务。默认 [checkpoint_components][checkpoint-components] 包含 Adapter、Representation、RuntimeController 及显式扩展。`BiasModule`、`TabuSearchBias` 与它们的基类未提供/注册对应的偏好记忆恢复面。Checkpoint 插件的[组件收集][checkpoint-collection]只读取声明组件的 `get_state/set_state`，不会自动发现 `_tabu_list`。

**后果。** 默认装配下，在评分后步骤失败，Tabu 内部记忆仍可能保留；新进程重建 Bias 后再恢复 checkpoint，Solver/Adapter 继续运行，但 Tabu 从空列表开始。A4 解决“记几次”，本项解决“谁拥有记忆、失败和恢复后记忆是什么”，两者需要分别处理。

**边界说明。** 本次没有认定所有记忆都必须回滚。如果定义的是“已经真实评估过的候选”，失败步骤中的已完成评估也可能应保留；如果定义的是“已接纳/已访问状态”，则必须跟对应提交事件一致。当前缺的是这项显式选择，不能直接把“recently visited”解释为“调用过 compute”。

线程评估另有按任务 deepcopy Bias 的[隔离路径][parallel-bias]；已有[测试][parallel-bias-test]明确期望原 Bias 不被修改。这可保护并发访问，但不能自动提供全局、连续的禁忌历史。不同执行模式的记忆归属需要一并规定。

**整改。** 为真正影响后续决策的偏好状态提供明确 owner、codec、更新时间与失败语义；复用现有 RuntimeParticipant/checkpoint 扩展，不另建恢复框架。无状态偏好无需强行实现空快照。已发生事件的不可回滚记忆需能按稳定事件身份去重恢复。

**验收。** 连续运行与中断恢复后下一次偏好一致；失败重试符合声明的记忆策略；串行/并行符合声明的历史共享范围；禁止复制锁或整个第三方对象图充当 codec。

### A6 · P2：DynamicSwitch 的搜索决定发生在步骤事务之前

**证据链。** [DynamicSwitchBase][switch-attempt] 在 `on_step_attempt_start` 中决定并应用切换；[run loop][attempt-before-step] 先分发该 hook，之后才执行 `solver.step()`；[步骤事务][step-transaction]在 step 内捕获。`soft/hard/both` [回调执行][switch-apply]可以直接修改权重、替换策略或重置算法状态，之后才更新 phase。

此组件继承的默认 ParticipationContract 是 context 建议；[运行时校验][participation-check]针对正式评估接管和 finalization veto，没有为这些搜索修改回调建立专门决定入口。DynamicSwitchBase 自身也没有 `get_state/set_state`。旧[演示代码][switch-example]确实通过回调改策略权重，说明这不是纯日志接口。

**风险与限定。** 如果 soft 成功、hard 失败，已发生的修改没有这次切换自身的原子边界。若后续 step 失败，step 捕获的是切换后的状态，无法回到切换前。这里不能简单断言“切换必须随 step 回滚”：运行级控制可能有意独立提交，但需要单独的提交、幂等与恢复声明。当前接口未区分两种语义。

**整改。** 信号采集留在 Plugin；策略调度由组合 Adapter 的显式策略入口消费，运行级开关由 Controller 的声明域负责。具体改变策略权重的命令仍需 Adapter 验证。明确切换是步骤事务一部分，还是独立可恢复控制事件。

**验收。** 覆盖两段切换的第二段失败、同一逻辑步重复尝试、checkpoint 后 phase 恢复、信号读取失败、决定域不匹配。

### A7 · P2：ParetoArchive 的“结果归档”和“搜索状态”用途未显式分开

**已经正确的部分。** 该 Plugin 在已提交代更新，维护目标标签分段，保存对齐 CandidateBatch，并提供 [get_state/set_state][archive-state]；不能当作“没有恢复的随意数组拼接”。

**仍有的边界。** 它执行可行过滤、非支配筛选和拥挤截断，见[更新策略][archive-policy]，随后[发布 Pareto 结果][archive-publish]。同时 MultiStrategy 的 `seeds_source="pareto"` 会从 `control.pareto_solutions` 取[下一轮种子][archive-seeds]。这证明 Pareto 视图可以进入搜索反馈闭环。`pareto_solutions` 也可能由其他来源产生，因此不能声称所有多策略搜索都依赖这个 Plugin。

当归档用于搜索种子时，归档配置、更新频率、发布失败策略及恢复时点都会成为算法输入的一部分。仅称其为“可随时关掉的观察能力”不充分；当前种子端也没有显式绑定归档 owner/revision。

**整改。** 区分可重算的报告归档和搜索会消费的归档。后者应通过明确的 archive view/provider 交给 Adapter，包含身份、目标语义和版本；归档结构可由 Unit 承载，筛选策略由明确所有者执行，Plugin 保留观察、发布或装配职责。不能把现有 `ArchiveUnit` 名字相同当作足以直接替换分段 Pareto 归档的依据。

**验收。** 纯报告模式开关不改变搜索；搜索归档模式缺失依赖时不偷偷换成另一种种子来源，除非声明了该策略；恢复后首轮种子来源和目标分段一致。

### A8 · P2：DiversityInitPlugin 的标准入口没有接上其拒绝采样逻辑

**证据。** [初始化 hook][diversity-init] 只在 Solver 已存在 `use_diverse_init` 属性时设置它；`on_population_init` 计算指标并打印。文件另有 `is_similar/should_accept`，但对 `core/adapters/representation/plugins/utils/project/tests` 的定向检索未发现标准初始化流程调用这些方法，也未发现主干读取 `use_diverse_init`。

**结论限定。** 标准生命周期能确认的行为是初始多样性观测；不能因此承诺已执行基于 `similarity_threshold/rejection_prob` 的初始化筛选。用户手动调用这些方法、外部自定义 Solver 使用该属性不在此否定范围内。

**整改。** 将只读指标观察与初始化策略分开。前者留 Plugin；后者由明确的初始化 operator/算法构建过程生成候选，或由 Adapter 消费候选相对已构建 Unit 的偏好来选择。是否使用软偏好、拒绝采样及预算限制由算法入口明确装配。

**验收。** 正式脚手架装配后可观测到所选初始化策略被实际调用；只装指标观察器不改变候选；重采样有预算与确定的终止条件。

### A9 · P1：Plugin 的公共读取 helper 仍可能掩盖权威读取失败

**证据。** [Plugin.get_population_snapshot][plugin-read] 已对 partitioned mode 拒绝单种群访问，这是正确改进。但 single/delegate 路径仍会捕获 `read_snapshot` 失败后尝试别的 key，再读 Adapter，最后读 Solver 数组字段。读取异常和部分转换异常按 soft error 记录后继续。失败与“某个兼容客户端没有正式读取面”未充分区分。

**影响。** 对指定权威 Snapshot 的读取失败，本应保留故障事实；helper 却可能返回看起来正常的另一来源。对于基于此结果维护归档或计算偏好的 Plugin，即使备用数组数值恰好一致，也没有证明它对应同一发布版本和身份。这与当前“按 authority mode 读取、权威失败不换副本”的约束冲突。

**整改。** 复用唯一的权威读取入口：根据声明的 mode 选择读法，校验引用与身份。若为兼容轻量协议客户端保留备用读取，必须以显式客户端能力/模式区分；不能在正式权威读取报错后把它当作恢复方式。

**验收。** 指定权威读取故障时，即使 Adapter/Solver 内存字段非空也不得成功返回；合法的轻量兼容客户端走自己的声明路径；partitioned 拒绝行为继续保留。

### A10 · P2：局部文档仍在鼓励已经不允许的写法

**明确冲突。**

- [plugins/runtime/README.md][runtime-readme] 的 Side Effects 仍写 `May directly mutate solver state or population content.`，Failure Policy 泛称默认安全降级。当前 [AGENTS 主线][agents-boundary] 和[运行契约][runtime-contract]已经要求明确所有者与参与角色。
- [MemoryPlugin.context_notes][memory-notes] 仍称会原地修改 population arrays；当前清理实现做 GC、清理 `temp_data` 和统计，没有对应的种群修改。这里是说明错误，不能据此把 MemoryPlugin 列为已确认的算法越界实现。
- [BlackBase Bias 基类说明][shared-bias-doc] 用 `Plugin/Event = control logic (enable/disable, switch strategies)` 概括控制职责。作为共享层描述过于宽泛，未交代 nsgablack 的 Adapter/Controller 决定权，需要补充边界，而非由读者自行推断。

**整改。** 统一说明“组件做什么、读谁的状态、输出交给谁决定、何时提交、失败能否继续”。优先更新实际开发入口和组件 docstring，再同步教程、Catalog 描述及装配示例。当前磁盘 AGENTS 已是 2026-10-09 版本，不能继续把全部问题归因于用户此前贴出的旧版 AGENTS。

## 5. 已核对组件的处置清单

这是本次抽样审阅结果，不是全部 Plugin/Bias 的逐类认证。

| 组件/组件组 | 当前实质 | 建议 |
| --- | --- | --- |
| DiversityBias | 候选相对集合的距离偏好 | 留在偏好层；修方向、身份和显式结构依赖 |
| TabuSearchBias | 候选评分与可变记忆混合 | 拆评分与记忆事件；明确历史含义、恢复和并行范围 |
| ParticleSwarmBias / CMAES 风格 Bias / LevyFlightBias | 借用算法直觉的标量偏好 | 可保留；文档继续说明 inspired，不宣称实现完整算法 |
| DiversityInitPlugin | 指标观察，加未连通的接受辅助方法 | 分离观察与初始化策略 |
| DynamicSwitchPlugin | 信号与任意搜索修改回调 | 分离信号输入、控制决定、策略执行 |
| ParetoArchivePlugin | 分段归档、筛选、结果发布，可间接供搜索使用 | 显式区分报告用途与搜索依赖 |
| BasicElitePlugin / HistoricalElitePlugin | 弃用装配桥 | 保持迁移到 EliteRetentionAdapter 的方向，按既定版本退场 |
| NumericalSolverProviderPlugin | 评估 Provider 工厂 | 保留能力层，不因 `is_algorithmic=True` 搬到 Adapter |
| MemoryPlugin | 内存观测与清理 | 保留 Plugin，修正过时说明 |
| checkpoint / trace / logger / backend 装配 | 运行与交付能力 | 按实际参与角色保留；本次未逐一审核全部实现 |

归类依据是“是否拥有搜索状态转移和决定”，不是类名带不带算法名。例：[PSO 风格 Bias][pso-bias]计算到 best 的距离偏好，没有速度/粒子转移；[数值求解 Provider][numerical-provider]通过正式[注册入口][provider-registration]参与评估；[精英兼容入口][elite-compat]明确安装 Adapter wrapper。

## 6. 需要补足的最小正式接口

现在的两条 Bias 路径各解决了一部分问题：

- 旧 `compute(x, OptimizationContext) -> float` 可表达简单候选评分，context 只有全局式 population/metrics/history。
- 新 [PreferenceProvider][preference-contract]可声明输出键，当前[优化投影入口][preference-projection]只接受 `objectives.<index>`，能保护 raw evidence，却还没有完整表达 Unit 对比或结构操作偏好。

可以在现有装配面上逐步补齐以下信息，不必一次建立复杂的泛型偏好引擎。下列是**建议契约信息，不是当前已存在 API**：

1. **评价对象**：candidate、unit 或 unit operation；候选携带稳定 token，Unit 携带实例身份。
2. **依赖视图**：所属 Adapter/组合路径、Unit ID、所需 capability、revision/快照身份，以及依赖是必需还是可选。
3. **输出语义**：目标 delta、可比较分数、排序建议或部分次序；声明方向和量纲，禁止把所有比较强塞成一个可相加实数。
4. **消费位置**：候选选择、proposal 分配、Unit 操作选择等明确决策点。Adapter 拥有最终裁决，偏好不能直接写权威种群。
5. **状态语义**：评分是否只读、何时更新记忆、checkpoint codec、失败/重复事件行为、缓存和并行范围。

同种 Unit 并存时，应绑定实例路径和身份，不按类名、角色类型或矩阵数值猜测。“这一份群体的多样性”与“另一份同类型群体的多样性”必须可以独立配置与恢复。

对普通用户，标准脚手架应仍只要求知道：**选哪个 Adapter、把哪个偏好绑到它的哪个结构/决策点、设置参数**。默认绑定、依赖校验和恢复接线由框架完成；跨多个同类型实例时才要求用户明确选择。不能为修内部边界而要求每个使用者手写事务和 Snapshot 解析。

## 7. 整改顺序与归属

### 第一阶段：先修已存在的结果语义问题

处理 A1–A5、A9：统一偏好方向；修候选身份；禁止错误依赖静默归零；拆评分与记忆更新；补状态恢复；权威读取失败不自动改读。主要改动属于 nsgablack，复用 BlackBase 已有事务和引用协议。

先为简单候选偏好与候选相对种群偏好提供正式路径，不要求所有旧 Bias 同时迁移。兼容层应显式标明“只支持无状态候选标量偏好”等限制，不能把不支持的组合伪装为正常运行。

### 第二阶段：让结构依赖和消费位置成为显式装配

为已实际需要的 Population/History/Archive 只读能力提供绑定；解决同类型多实例、嵌套路径、revision 与缓存键。Unit 保持结构职责，Adapter 保持选择职责，偏好结果保留可审计原因。

优化特有的支配、多样性和 Unit 选择协议放 nsgablack。只有确实跨框架共用的中性协议才进入 BlackBase；不能为了跨框架一致，要求 MLBlack 假装自己拥有种群。

### 第三阶段：收口 Plugin 的双重职责

处理 A6–A8：DynamicSwitch 拆采集和决定；ParetoArchive 分清结果归档和搜索依赖；DiversityInit 分清观察和初始化。使用精英兼容桥已有的迁移经验，保留清晰弃用期，避免直接搬文件破坏公开装配入口。

### 第四阶段：同步文档与治理

处理 A10，并同步 scaffold、组件说明、Catalog default/framework-core 描述和 Doctor 的可检查声明。Doctor 可以检查缺失依赖、缺失状态声明或不支持的绑定；不能靠名字判断某个算法数学上是否正确，也不能证明任意回调无副作用。

## 8. 测试源码观察与后续验收

当前已有的正面证据：

- [test_bias_acceptance_boundary.py][acceptance-test]包含 raw violation 与软化选择视图分离、真实 step 接纳与事件证据一致的断言。
- [test_pareto_archive_identity.py][archive-test]包含相同数值不同身份、checkpoint 对齐和损坏状态拒绝的断言。
- [test_bias_vector.py][bias-vector-test]检查无状态 CallableBias 的向量/标量一致性，不能覆盖 Tabu 的记忆副作用。
- [verify_biases.py][bias-verify]主要检查导入、标量返回和算法迁移目录口径；其中多样性测试没有装入参照种群。并且当前 [pytest 配置][pytest-discovery]默认只收集 `test_*.py`，`verify_biases.py` 需要显式执行或另外纳入检查，不能仅凭它存在声称普通 pytest 已覆盖。

建议后续行为验收至少包含：

| 维度 | 必须区分的场景 |
| --- | --- |
| 偏好方向 | 相同 raw objective 的近点/远点、零权重、各输出方向 |
| 身份 | 同值不同 token、同 token 自身、新提案与已存在成员 |
| 结构绑定 | 单群体、两个同类型 Unit、嵌套组合、不兼容结构 |
| 读取 | 合法空结构、缺依赖、不可读引用、身份/版本不匹配 |
| 评分 | 单目标、多目标、目标重排、相同目标值、批内次序 |
| 缓存 | 开关、命中、依赖 revision 改变、不同实例 |
| 状态 | 失败重试、接纳/拒绝、checkpoint、连续运行对照 |
| 并行 | 本地只读共享、局部隔离、需要全局记忆的明示策略 |
| 切换 | 回调部分成功、步骤失败、重复尝试、恢复 phase |
| 归档 | 报告开关、搜索依赖缺失、恢复后首轮种子来源 |

实施时按改动范围运行测试；涉及评估链须覆盖单点、批量、Provider 短路与 Snapshot 读写；涉及 Catalog 再验证 default/framework-core；最后分别检查仓库 Doctor coverage 和受影响正式 Case 的 build。**本次仅写出验收要求，没有执行这些命令。**

## 9. 交付边界

本报告建议保留既有主线，并把“比较对象、结构依赖、决定权、状态时间”接起来。最值得先修的不是分类名称，而是 A1/A3/A4 等已经能沿源码推导出错误结果的路径。

此次交付只有本 Markdown。上述发现均尚待实现修复和行为验证；不能把报告落盘算作完成整改。

<!-- 链接指向本次审计的本地工作区；行号随后续代码修改可能移动。 -->
[unit-population]: C:/Users/hp/Desktop/nsgablack/units/collections.py:75
[diversity-compute]: C:/Users/hp/Desktop/nsgablack/bias/algorithmic/diversity.py:52
[diversity-identity]: C:/Users/hp/Desktop/nsgablack/bias/algorithmic/diversity.py:91
[bias-weight]: C:/Users/hp/Desktop/nsgablack/bias/core/base.py:136
[bias-add]: C:/Users/hp/Desktop/nsgablack/bias/bias_module.py:357
[minimization]: C:/Users/hp/Desktop/nsgablack/utils/performance/fast_non_dominated_sort.py:161
[snapshot-partition]: C:/Users/hp/Desktop/nsgablack/core/solver_helpers/snapshot_helpers.py:370
[bias-read]: C:/Users/hp/Desktop/nsgablack/bias/bias_module.py:506
[bias-context]: C:/Users/hp/Desktop/nsgablack/bias/bias_module.py:561
[tabu-compute]: C:/Users/hp/Desktop/nsgablack/bias/algorithmic/tabu_search.py:44
[bias-vector]: C:/Users/hp/Desktop/nsgablack/bias/bias_module.py:275
[bias-cache-hit]: C:/Users/hp/Desktop/nsgablack/bias/bias_module.py:331
[bias-cache-key]: C:/Users/hp/Desktop/nsgablack/bias/bias_module.py:395
[solver-participants]: C:/Users/hp/Desktop/nsgablack/core/blank_solver.py:282
[checkpoint-components]: C:/Users/hp/Desktop/nsgablack/core/blank_solver.py:4909
[checkpoint-collection]: C:/Users/hp/Desktop/nsgablack/plugins/system/checkpoint_resume.py:616
[parallel-bias]: C:/Users/hp/Desktop/nsgablack/utils/parallel/evaluator.py:305
[parallel-bias-test]: C:/Users/hp/Desktop/nsgablack/tests/test_parallel_engineering_safeguards.py:78
[switch-attempt]: C:/Users/hp/Desktop/nsgablack/utils/dynamic/switch.py:90
[attempt-before-step]: C:/Users/hp/Desktop/nsgablack/core/solver_helpers/run_helpers.py:340
[step-transaction]: C:/Users/hp/Desktop/nsgablack/core/composable_solver.py:383
[switch-apply]: C:/Users/hp/Desktop/nsgablack/utils/dynamic/switch.py:161
[participation-check]: C:/Users/hp/Desktop/blackbase/src/blackbase/plugin/base.py:275
[switch-example]: C:/Users/hp/Desktop/nsgablack/examples/_misc_examples/dynamic_multi_strategy_demo.py:202
[archive-state]: C:/Users/hp/Desktop/nsgablack/plugins/runtime/pareto_archive.py:263
[archive-policy]: C:/Users/hp/Desktop/nsgablack/plugins/runtime/pareto_archive.py:201
[archive-publish]: C:/Users/hp/Desktop/nsgablack/plugins/runtime/pareto_archive.py:486
[archive-seeds]: C:/Users/hp/Desktop/nsgablack/adapters/multi_strategy/adapter.py:840
[diversity-init]: C:/Users/hp/Desktop/nsgablack/plugins/runtime/diversity_init.py:31
[plugin-read]: C:/Users/hp/Desktop/nsgablack/plugins/base.py:80
[runtime-readme]: C:/Users/hp/Desktop/nsgablack/plugins/runtime/README.md:15
[agents-boundary]: C:/Users/hp/Desktop/nsgablack/AGENTS.md:43
[runtime-contract]: C:/Users/hp/Desktop/nsgablack/docs/architecture/RUNTIME_CONTRACTS_CN.md:7
[memory-notes]: C:/Users/hp/Desktop/nsgablack/plugins/system/memory_optimize.py:20
[shared-bias-doc]: C:/Users/hp/Desktop/blackbase/src/blackbase/abc/_bias.py:10
[pso-bias]: C:/Users/hp/Desktop/nsgablack/bias/algorithmic/pso.py:47
[numerical-provider]: C:/Users/hp/Desktop/nsgablack/plugins/evaluation/numerical_solver_base.py:48
[provider-registration]: C:/Users/hp/Desktop/nsgablack/plugins/evaluation/provider_plugin_base.py:23
[elite-compat]: C:/Users/hp/Desktop/nsgablack/utils/compat/elite_retention.py:18
[preference-contract]: C:/Users/hp/Desktop/blackbase/src/blackbase/preferences.py:25
[preference-projection]: C:/Users/hp/Desktop/nsgablack/core/solver_helpers/bias_helpers.py:12
[acceptance-test]: C:/Users/hp/Desktop/nsgablack/tests/test_bias_acceptance_boundary.py:58
[acceptance-source]: C:/Users/hp/Desktop/nsgablack/core/evaluation_acceptance.py:67
[archive-test]: C:/Users/hp/Desktop/nsgablack/tests/test_pareto_archive_identity.py:29
[bias-vector-test]: C:/Users/hp/Desktop/nsgablack/tests/test_bias_vector.py:7
[bias-verify]: C:/Users/hp/Desktop/nsgablack/tests/verify_biases.py:22
[pytest-discovery]: C:/Users/hp/Desktop/nsgablack/pyproject.toml:285
