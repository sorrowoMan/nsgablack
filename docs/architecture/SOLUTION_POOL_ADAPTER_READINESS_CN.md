# 解池、视图与 Adapter 接入契约

最后按代码核对：2026-10-14。本文记录当前支持范围与后续算法接入要求，不把候选登记等同于任意算法融合。运行细节见 [解池契约](SOLUTION_POOL_CN.md)。

## 1. 三个明确的数据职责

母池 SolutionPool 拥有一次运行的不可变候选版本。SolutionRef 指定 pool、record、row 与 token；同值不同身份和同身份不同版本分别保存。候选语义、原始反馈与来源通过共享 SnapshotStore 存放。

子池是具名引用视图，使用同一索引、事务、检查点与保留机制。全部视图具有稳定 view_id、revision、created_by、parent 和发布状态。candidate_collection 表达普通集合或工作队列；candidate_view 表达算法明确交付的选择；objective_projection 另保存比较参数。视图不复制候选本体。

Unit 保存算法自己的成员关系、顺序、路径、槽位、区域和派生特征。数值工作数组可以留在 Unit；其来源版本必须能准确说明。不能把池成员关系当成算法的环境选择。

父视图引用 x，精修子视图引用新候选 y，二者都在母池内。parent 表达派生来源，不要求 child 集合包含于 parent 集合；删父视图不删除后代或其他使用者的候选。

## 2. 创建、绑定和运行

Adapter 的配置实例可以在装配期间构造。Solver 建立母池后才进入 Adapter.setup。setup 应准备 RNG、codec 和资源；依赖池输入的候选初始化发生在任务绑定后的首次 propose。

MOEA/D 已采用此流程：初始化提案通过问题 repair、评估、预算和准入；部分接纳分批建立种群。完整种群形成后才生成方向和发布视图，pool_views_ready 是后续任务的启动条件。外部 initialize 不随机补齐不足的显式输入；compete 仍按当前方向规则、随机顺序和 nr 上限竞争。

NSGA 家族与 DE 不再从另一个算法的共享 snapshot/control.population 隐式借初始成员。跨算法输入使用显式池任务；已有自身 Unit 与 checkpoint 仍按自己的路径恢复。EvolutionSolver 的旧显式初始化同步仍需另行补完整身份交付，不能把 X/F/V 自动解释为池版本收据。

子池选择声明可以先写，实际读取时要求视图已经存在且可读。普通具名输入不存在就报错；已存在但候选不足可以显式 wait/available。按创建者的 all/random 在请求开始时冻结已发布视图；完整的上游阶段屏障由 Router 决定。

## 3. 选择方式不能改变视图含义

PoolTaskSpec 可以指定母池、具名视图、引用选择函数或 subpools.all/random(adapter)。名称与创建者选择器都以解析后的视图类型检查消费者能力。投影视图的反馈在任务层应用一次，原始目标和约束证据仍保存在母池。

普通具名集合的 count 表示每实例输入配额；按创建者选择多个视图时 count 表示每视图起点数。不同方向即使引用同一解，仍是不同任务。队列保存冻结 source_descriptor、projection、slot、ref 和 uses_view_jobs；恢复禁止丢掉解释后继续按默认评分运行。

## 4. 输出、最终选择和接收

output 聚合集合保存任务接纳的提案。get_pool_refinement_results 明确交付最终选择的精确引用；这不是 retention roots 的别名。声明 output 的 refine 消费者必须实现结果交付。

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
| GaussianSearch／MAS／信赖域各类 | 尚未迁移正式池任务 | 未声明 | 未完成统一保留 | 自取起点／参考样本仍需审查 |
| A*／MOA* | 尚未迁移正式池任务 | 未声明 | 路径与标签需要专属接入 | 必须定义新根或继续路径 |
| GradientDescent／GradientOptimizer | 尚未迁移正式池任务 | 未声明 | 待评估点与已评估结果须区分 | 梯度、Provider 活状态不能由目标投影替代 |

NSGA 家族和 DE 每实例发布一个普通 population 视图，MOEA/D 每方向发布一个投影视图。`PoolTaskSpec(subpools.all(ga), count="all", steps=3, output="refined")` 明确逐成员精修；使用默认 count 时仍按每视图一个起点分发。普通视图可能保存已提交的部分初始化成员，不代表种群已填满；启动屏障仍由 Router 定义。仅在全部成员都有精确引用时发布视图，旧数值 setter 或不完整引用不能伪装成可交接的完整种群。

NSGA 家族／DE 一旦持有精确成员引用，数值 set_population_snapshot 只能对同一批成员刷新反馈，不能换成员或清空；新成员须走显式池输入或完整恢复。未建立精确身份前的数值初始化仍支持。手工 update 若让成员缺少准确引用，会撤回该实例自己的旧 population 视图；撤回与 Unit 一起回滚，不误删同名自定义集合。Evolution 正常初始化与运行已验证，旧跨成员数值替换仍需迁移为完整身份交付。

DE 的外部竞争必须定义 target 配对，不能借用 NSGA 环境选择。支持 Unit 或正常搜索不能自动推导池任务能力。

## 6. 后续接入的验收条件

新增算法首先明确：输入是建立新根、初始化成员、替换目标、还是参与竞争；需要几个起点及哪些参考样本。已评估基准与后继提案不能混为一个分数。

输出明确 current、best、population、路径或其他已选择结果，记录精确引用。待评估点可以作为新提案，但不能附上之前候选的反馈冒充已评估结果。

成员版本校验包括语义 metadata：相同 token、相同数值也可能是不同版本。捕获时读取准确回执并验证值与 metadata；检查点把引用和语义摘要一起保存，恢复/读取时再次验证，不允许用后来同值但不同 metadata 的记录替换原来选中的版本。

投影能力要求评分和附加反馈语义完整。梯度消费者需要同步变换梯度或 Jacobian；路径消费者要维护父边代价与标签；信赖域要明确中心、半径、参考样本与任务来源。无法满足时明确拒绝，不只补布尔声明。

行为验证覆盖起点、预算截断、部分／零接纳、失败回滚、任务重启、正式 checkpoint、同 token 后续版本、包装和多实例。回收声明必须完整；没有本地活引用可以返回空集合，未知存活状态必须拒绝，不能用空根隐藏。

本次没有重造 Project/L0 调度器或共享存储；池任务仍通过既有 Router、步骤事务和 SnapshotStore 执行。
