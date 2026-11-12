# 解池、视图与 Adapter 接入契约

最后按代码核对：2026-10-14。本文记录当前支持范围与后续算法接入要求，不把候选登记等同于任意算法融合。运行细节见 [解池契约](SOLUTION_POOL_CN.md)。

## 1. 三个明确的数据职责

母池 SolutionPool 拥有一次运行的不可变候选版本。SolutionRef 指定 pool、record、row 与 token；同值不同身份和同身份不同版本分别保存。候选语义、原始反馈与来源通过共享 SnapshotStore 存放。

子池是具名引用视图，使用同一索引、事务、检查点与保留机制。全部视图具有稳定 view_id、revision、created_by、parent 和发布状态。candidate_collection 表达普通集合或工作队列；candidate_view 表达算法明确交付的选择；objective_projection 另保存比较参数。视图不复制候选本体。

Unit 保存算法自己的成员关系、顺序、路径、槽位、区域和派生特征。数值工作数组可以留在 Unit；其来源版本必须能准确说明。不能把池成员关系当成算法的环境选择。

父视图引用 x，精修子视图引用新候选 y，二者都在母池内。parent 表达派生来源，不要求 child 集合包含于 parent 集合；删父视图不删除后代或其他使用者的候选。

## 2. 创建、绑定和运行

Adapter 的配置实例可以在装配期间构造。Solver 建立母池后才进入 Adapter.setup。setup 应准备 RNG、codec 和资源；普通池任务在绑定后的首次 propose 初始化候选。EvolutionSolver 的生命周期初始化是另一条显式入口：控制面先完成 repair、求值和准入，再向支持完整交付的 Adapter 安装已评估成员，不提前让 Adapter 自行求值。

MOEA/D 已采用此流程：初始化提案通过问题 repair、评估、预算和准入；部分接纳分批建立种群。完整种群形成后才生成方向和发布视图，pool_views_ready 是后续任务的启动条件。外部 initialize 不随机补齐不足的显式输入；compete 仍按当前方向规则、随机顺序和 nr 上限竞争。

NSGA 家族与 DE 不再从另一个算法的共享 snapshot/control.population 隐式借初始成员。跨算法输入使用显式池任务；已有自身 Unit 与 checkpoint 仍按自己的路径恢复。EvolutionSolver 的初始化已通过完整批次、原始反馈、来源和精确收据交付；不能把 X/F/V 自动解释为池版本收据。

Evolution 显式池输入的初始化先按当前预算取种子，派生提案身份后执行一次问题 repair，再进入求值与准入。池游标按原始消费数量和最终接纳的原始索引结算，预算进一步裁剪或非前缀接纳都不能丢掉未接纳种子；失败和零接纳由事务恢复输入。并发预算竞争可能在 repair 后再次减少送评数量，此时不重跑 repair，仍按原消费数量结算。

子池选择声明可以先写，实际读取时要求视图已经存在且可读。普通具名输入不存在就报错；已存在但候选不足可以显式 wait/available。按创建者的 all/random 在请求开始时冻结已发布视图；完整的上游阶段屏障由 Router 决定。

## 3. 选择方式不能改变视图含义

PoolTaskSpec 可以指定母池、具名视图、引用选择函数或 subpools.all/random(adapter)。名称与创建者选择器都以解析后的视图类型检查消费者能力。投影视图的反馈在任务层应用一次，原始目标和约束证据仍保存在母池。

普通具名集合的 count 表示每实例输入配额；按创建者选择多个视图时 count 表示每视图起点数。不同方向即使引用同一解，仍是不同任务。队列保存冻结 source_descriptor、projection、slot、ref 和 uses_view_jobs；恢复禁止丢掉解释后继续按默认评分运行。

## 4. 输出、最终选择和接收

显式 output 聚合集合保存任务接纳的提案。get_pool_refinement_results 明确交付最终选择的精确引用；这不是 retention roots 的别名。refine 消费者都须实现结果交付；output=None 也发布最终视图，且不创建累计提案历史。

普通精修也发布 candidate_view，下一层可以使用 subpools.all(refiner)。投影精修发布继承当前有效比较参数的 objective_projection。下一层从新反馈应用有效投影一次，不把已标量化分数再次投影。

透明 Role 的 pool_result_owner 指向真实算法实例。all(Role(VNS)) 与 all(vns_leaf) 使用同一个具体实例身份，不依类型名或候选生产者猜所有权。

VNS 和 PatternSearch 交付最终选中已评估解。SA、SingleTrajectory 可以为探索走向较差 current，但交付 task-best；二者的存活引用分别保护。接收方重新经过正常评估和选择，结果发布不自动修改来源算法的槽位。

## 5. 当前覆盖

| 组件 | 指定池输入 | 任务精修／投影 | 精确结果与保留 | 说明 |
|---|---|---|---|---|
| NSGA-II／III／SPEA2 | initialize、compete | 发布普通 population 视图；不消费标量精修 | 成员精确版本，随选择对齐 | 保持各自多目标排序 |
| MOEA/D | initialize、compete | 发布方向视图 | 精确槽位引用 | 延迟 bootstrap，返回可竞争多个方向 |
| DifferentialEvolution | initialize | 发布普通 population 视图；不消费 refine／投影 | 精确成员版本与保留 | 先评估种子，再产生 target trial；不猜外部竞争配对 |
| VNS | initialize | refine、投影 | 明确最终解 | 保持原搜索机制 |
| SA／PatternSearch／SingleTrajectoryAdaptive | initialize | refine、投影 | 精确 current/best 或最终解 | 起点先送评，任务解释冻结 |
| RoleAdapter | 透传叶能力 | 透传叶支持面 | 真实结果所有者，局部空根 | intake 不按普通提案上限截断 |
| StrategyRouter／PoolTask | 正式装配与分发 | 普通及投影视图 | 队列、结果、来源共同恢复 | 多实例与嵌套复用同一机制 |
| RoleRouter／StrategyChain | 由嵌套池 Router 承担 | 不推断阶段交接 | 局部空根，子组件单独声明 | 保留原调度策略 |
| AsyncEventDriven／EliteRetention | 受其明确封装边界约束 | 不自动变成任意精修器 | 档案保护交付的精确版本 | 未带收据的旧非空档案不能开启回收 |
| FixedCandidate | 公共起点接入 | 不声明任意投影精修 | 当前候选引用 | 保留来源身份 |
| CandidateProposer | 子类声明 | 子类声明 | 显式绑定接口；默认未知 | 不猜测子类保留了哪些提案 |
| GaussianSearch／MAS | initialize | refine、投影 | 已评估任务最佳、当前点与训练样本准确引用 | 投影使用相同可行性顺序；MAS 不隐式借全局最优点 |
| DFO／MO-DFO／NonSmooth／Subspace 信赖域 | initialize | refine、投影 | 精确中心、任务最佳与参考样本 | 起点先送评；repair 守区域；子空间只用本任务样本 |
| A*／MOA* | 显式 new_root initialize | 不声明通用 refine／restart／投影 | 节点／标签／父路径及明确结果准确引用 | 新根不继承其他路径 g；图终止与路径代价保持原语义 |
| GradientDescent | initialize | refine、投影 | 已评估中心／探针／下降点的任务最佳 | 起点→探针→下降提案分别评估；不使用探针代理分数给新点评分 |
| GradientOptimizer | initialize | 普通 refine；拒绝目标单独投影 | 已评估任务最佳与前驱；待评估参数单列 | SGD／Adam／AdamW 仍消费 Provider 梯度；保留 slot 事务与清理债务 |

NSGA 家族和 DE 每实例发布一个普通 population 视图，MOEA/D 每方向发布一个投影视图。`PoolTaskSpec(subpools.all(ga), count="all", steps=3, output="refined")` 明确逐成员精修；使用默认 count 时仍按每视图一个起点分发。普通视图可能保存已提交的部分初始化成员，不代表种群已填满；启动屏障仍由 Router 定义。仅在全部成员都有精确引用时发布视图，旧数值 setter 或不完整引用不能伪装成可交接的完整种群。

NSGA 家族／DE／MOEA/D 一旦持有精确成员引用，数值 set_population_snapshot 只能对同一批成员刷新反馈，不能换成员或清空；新成员须走显式池输入、完整身份交付或完整恢复。未建立精确身份前的数值初始化仍支持。NSGA 家族／DE 的手工 update 若让成员缺少准确引用，会撤回该实例自己的旧 population 视图；撤回与 Unit 一起回滚，不误删同名自定义集合。

Evolution 初始化与环境选择使用 `set_population_state(control, batch, feedback, solution_refs=..., provenance=...)` 完整交付。`get_population_solution_refs(control)` 是与成员行对齐、允许重复槽位的有序引用；`get_solution_pool_roots` 只声明保留根，不能代替它。L1／none Adapter 的初始化批次仍由 Solver 权威持有，不伪造 Adapter 种群。老三数组环境选择须显式 `external_evaluation=True`：这是外部原始求值断言与新身份导入，不是追认旧引用，也不虚增 Problem 调用计数。

`supports_population_state_delivery()` 是只读能力查询**方法**，不是布尔属性。它声明能否接收完整状态并导出有序成员引用；真正交付时仍须校验池作用域、精确版本、候选数值与 metadata、原始反馈、来源。`get_population_solution_refs(control)` 返回 `None` 表示不支持；返回引用时保留行顺序及重复槽位，不能对引用去重。回收根还可能包括档案、队列和当前点，且透明包装可以没有本地根，因此不能从回收根树反推成员序列。

完整交付的转发边界如下：

- NSGA-II／III／SPEA2、DE、MOEA/D 实现接收与有序引用导出。MOEA/D 在完整交付后建立方向；至少需要两个成员和两个目标，已有分解不能由此静默改变槽位数或目标维度。
- RoleAdapter 和 EliteRetentionAdapter 将能力查询、完整交付及有序引用导出交给内层实例；局部回收根仍按各自职责声明。
- StrategyChainAdapter 转发给最后确认的种群所有者；阶段推进后，该所有者可能与下一次要运行的阶段不同。不会向所有阶段广播成员。
- 只有一个子 Adapter 的 CompositeAdapter 透明转发；多个子 Adapter 保持 partitioned 权威，不隐式拼接或广播同一批成员。
- PoolTaskAdapter 拥有自己的输入策略，不因为继承 RoleAdapter 就允许生命周期直接灌入种群。它拒绝完整状态交付，防止绕过 PoolTaskSpec 的种子选择、冻结解释和进度。

EvolutionSolver 在 setup 阶段、初始化求值前检查完整交付能力和可能的分区权威；直接调用已评分初始化或环境选择也会先检查。不支持的 L2 配置与多子分区配置明确拒绝，使用 ComposableSolver 或正式聚合策略；L1／none 无需伪装种群接收能力。当前 setup 检查位于 `super().setup()` 之后，不能据此承诺尚未调用 Adapter.setup，第三方 setup 仍须遵守“不隐含候选求值”的契约。数据相关的大小、维度和收据合法性在交付时检查，失败回滚不会撤销已经消耗的求值成本。

DE 的外部竞争必须定义 target 配对，不能借用 NSGA 环境选择。支持 Unit 或正常搜索不能自动推导池任务能力。

## 6. 后续接入的验收条件

新增算法首先明确：输入是建立新根、初始化成员、替换目标、还是参与竞争；需要几个起点及哪些参考样本。已评估基准与后继提案不能混为一个分数。

输出明确 current、best、population、路径或其他已选择结果，记录精确引用。待评估点可以作为新提案，但不能附上之前候选的反馈冒充已评估结果。

成员版本校验包括语义 metadata：相同 token、相同数值也可能是不同版本。捕获时读取准确回执并验证值与 metadata；检查点把引用和语义摘要一起保存，恢复/读取时再次验证，不允许用后来同值但不同 metadata 的记录替换原来选中的版本。

Gaussian／MAS／有限差分／GradientOptimizer 在 propose、保留根和结果读取前，交叉验证已评估 Unit 候选与对应精确池版本；候选缺失或数值不同须拒绝，不能用旧收据继续求值。Gaussian／有限差分也核对同义评分；GradientOptimizer 的未评估后继不绑定前驱的候选值或损失。MAS 恢复时，兼容载荷与 codec Unit 的 X/Y 历史若不同，在重建模型前拒绝；历史 X 另与保护的精确版本比对。此处不重跑 Problem 或 Bias，也不把不同含义的分数强行相等。

投影能力要求评分和附加反馈语义完整。梯度消费者需要同步变换梯度或 Jacobian；路径消费者要维护父边代价与标签；信赖域要明确中心、半径、参考样本与任务来源。无法满足时明确拒绝，不只补布尔声明。

行为验证覆盖起点、预算截断、部分／零接纳、失败回滚、任务重启、正式 checkpoint、同 token 后续版本、包装和多实例。回收声明必须完整；没有本地活引用可以返回空集合，未知存活状态必须拒绝，不能用空根隐藏。

本次没有重造 Project/L0 调度器或共享存储；池任务仍通过既有 Router、步骤事务和 SnapshotStore 执行。

## 7. 精修器与路径搜索的具体边界

有限差分 GradientDescent 首次评估起点，下一次评估成对探针，再提出并评估下降点。预算或接纳只保留单侧探针时，不构造该维度梯度。未送评 trial 不修改中心或其分数；结果策略明确选择任务内最好已评估候选，可以是探针。探针数与步骤数是不同预算，steps=3 才能完成一次完整的起点／探针／下降尝试。

GradientOptimizer 每次评估当前参数、消费梯度并计算尚未评估的后继。结果交付前驱中的最好已评估版本，不将后继关联到旧损失。仅对目标标量化不足以变换梯度或不可见 gradient_ref，所以此 Adapter 拒绝 objective_projection；需要投影梯度时应由 Provider 正式交付与该损失一致的梯度。新任务清空算法 moments，旧 Provider slots 在事务成功后退休；失败恢复旧 slots，未确认释放的引用保留为可重试债务。没有新 transition 时仍存活的 slots 不释放。

信赖域精修在起点接纳后建立中心与半径。MO 原生池任务冻结一套权重；普通运行仍可换方向，但必须在同一新方向重评分已保存的目标向量。Subspace 的 sample_limit 默认 256，样本是本任务实际接纳的版本，数量不足可用随机基底；不读取别人的全局 population。边界裁剪保持采样射线与子空间，不因逐坐标 clip 破坏结构。

A*／MOA* 使用 `pool_start_policy="new_root"` 明确读取单个种子，先 repair／evaluate／admit 再建立根。edge 模式 g=0，objective 模式依据本次反馈建立根；新根不等于接续旧父路径。默认旧图搜索入口仍保留，但未有准确收据的旧节点不能开启严格池回收。A* 结果名为 best_evaluated（原目标聚合与罚分），MOA* 为 nondominated_path_labels；路径 g、标签支配、原始目标不是同一件事。二者不接受通用有界 refine 或 MOEA/D 目标投影视图，不能为满足步骤配额重评终止节点来伪造融合。
