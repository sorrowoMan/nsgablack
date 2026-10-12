# Unit、算法管线与 Adapter：逐项源码审查及改造方案

2026-10-09 定义澄清：Unit 保留候选本体或集合，扩展算法特征、关系和必要状态；不是把候选编码为另一种表示。派生特征按依赖维护，状态仍由已有 codec 恢复。当前实现和适用边界见 [Unit 特征维护](UNIT_FEATURES_CN.md)。本文旧审查语境中的“结构构建”应按这一含义理解。

日期：2026-10-08。状态：原始源码审查与逐项设计保留；用户授权“全额改”后的实现对照见第十一节。

原清单中的 31 个主干 Adapter 类、19 个非模板示例策略、70 份模板已完成对应的结构或委托迁移。
当前接口和行为以 [中文使用说明](../guides/ALGORITHM_UNITS_CN.md) 及源码为准；
以下“现状/建议/实施顺序”描述的是迁移前基线与设计理由，不能作为当前实现状态。
本次未修改 mlblack 或 blackbase，也未执行消融或性能 benchmark。

本文采用的定义是：**算法管线构建 Unit，Adapter 操作 Unit。问题管线负责候选的约束处理与可行性检查。**

原始审查依据是当时的工作区源码；nsgablack 的 HEAD 为 `ec1ae755d9693bb1996dd472e8e116d9f99b9314`，工作区已有其他未提交修改，因此本报告不等同于该提交的纯净快照。原始审查阶段仅阅读代码、整理文档；后续用户授权“开始完善”及“全额改”后，已完成第十一节所列实现与验证。

覆盖范围：

- 正文逐项覆盖 `adapters/` 中的 **31 个 Adapter 类**：27 个具体实现或包装器、2 个基类、2 个兼容子类。
- 附录另行覆盖当前仓库示例中的 19 个非模板 Adapter 类定义，以及 70 份 Adapter 模板文件。重复模板按实际内容归组，不能把这些副本算成 70 种算法。
- 上述数量来自源码定义盘点，**不是 Catalog 的统计结果**。主干与示例分开陈述；以后验证 Catalog 必须使用 `framework-core`，并按变更范围对照 `default`。
- 不把事务报告类型、Representation 的 `_InitializerAdapter` 等接口包装器、测试替身计为搜索 Adapter。

## 一、从代码得到的判断

你的判断有源码支持：许多 Adapter 已经在维护自己的算法操作结构，只是这些结构有的藏在私有类中，有的散落为数组、字典、列表和多个成员变量。例如 A* 的 `_Node`、MOA* 的 `_Label`、MOEA/D 的权重和邻接矩阵、子空间信赖域的基矩阵、Adam 的参数与动量槽。

因此最有价值的工作，是把这些**已经存在的结构及其构建契约显式化**，让结构可以独立替换，而搜索流程继续由 Adapter 负责。

但不同 Adapter 的改造量差别很大：

- A*、MOA*、MOEA/D、子空间信赖域、梯度优化器，有明确的专用结构，值得提取正式 Unit。
- VNS、SA、普通轨迹搜索，可以先复用轻量候选结构，再按需要声明邻域结构，无须各造一套相同的数据类。
- NSGA-II、NSGA-III、SPEA2、DE，可以共享种群结构，再增加各自需要的几何或提案关联结构。
- Role、Composite、StrategyChain、StrategyRouter 等，主要需要传递和隔离子 Adapter 的 Unit 构建绑定，无须强行包装出新的搜索实体。

**缺口不只是一个 `Unit` 类名，还包括构建入口、兼容声明、候选投影、反馈关联和状态恢复。**这些是同一个抽象落地时必须补齐的接口，不需要因此再造一套 Solver、执行器或调度框架。

## 二、先固定边界

### 2.1 四种职责

1. **Problem：评价求解目标。**这是本次讨论采用的目标职责。当前 `BlackBoxProblem` 仍提供 `evaluate_constraints()`，不能描述为已经完成了“目标与约束彻底分离”。本轮 Unit 设计保留现有评价契约，约束声明迁移应单独设计。
2. **问题管线：处理问题可行性。**包括表示转换、约束修复、合法性检查。repair 未必能修复所有候选，仍需保留不可行反馈与拒绝路径，不能把“调用过 repair”视为可行性证明。
3. **算法管线：构建算法所需的 Unit。**包括结构装配、维度和模式验证、几何构建、初始存储分配、显式转换。构建可发生在初始化，也可发生在新增节点、生成探针或重建子空间时。
4. **Adapter：操作 Unit 并推进算法。**包括选择、扩展、接受、淘汰、排序、更新、切换、停止，以及决定什么时候请求构建新结构。

源码依据：[BlackBoxProblem](C:/Users/hp/Desktop/nsgablack/core/base.py:17)、[RepresentationPipeline](C:/Users/hp/Desktop/nsgablack/representation/base.py:30)、[Adapter 契约](C:/Users/hp/Desktop/nsgablack/adapters/algorithm_adapter.py:191)。

两类管线可以共用同一个 pipeline kernel，按语义划分 slot；不必强制成为两个互不关联的执行系统。

### 2.2 构建结构和执行算法的分界

判断一个函数应不应该搬进算法管线，要看它是否在决定搜索过程：

- 按给定维度、参考方向规则构建权重矩阵：可以进入 builder。
- 根据本轮反馈选择保留哪些个体：留在 Adapter。
- 按 Adapter 指定的坐标、符号和步长装配有限差分探针：可以进入 builder。
- 由反馈计算梯度，再决定接受哪个点：留在 Adapter。
- 为参数分配同形状的零动量槽：可以进入 builder。
- 计算 Adam 动量更新、偏差修正和参数步进：留在 Adapter，或由其调用正式计算后端。
- 构建节点的字段、父引用和候选投影：可以进入 builder。
- 决定扩展哪个节点、如何累计路径代价、如何计算队列优先级：留在 Adapter；领域代价、启发式等工具可由管线装配注入。

因此，“把 Adapter 的全部逻辑搬进 pipeline，再留下一个循环”会破坏这次拆分的意义。管线可以装配算法使用的工具，但**工具被装配，不等于工具拥有搜索流程**。

### 2.3 Unit 不等于整个 Adapter 状态

Unit 还为偏好提供明确的结构语义：单候选、候选相对 Unit、整体 Unit、结构变化是不同评价范围。已实现的视图、作用域与装配契约见 [以 Unit 为中心理解搜索与偏好](UNIT_PREFERENCE_CONTRACT_CN.md)。结构自身提供数据与操作；可选偏好表达倾向；Adapter 决定是否执行结构变化。

建议区分三种数据：

- **操作结构**：节点、标签、种群、方向集合、参数及优化器槽等，是 Unit 的主要内容。
- **策略控制状态**：温度、失败计数、当前阶段、采样策略、接受规则等，由 Adapter 管理。个别标量可以存于 Unit 中，但其更新权仍属于 Adapter。
- **运行资源**：executor、锁、Provider 会话、全局 lease 等，保持现有运行时归属，不能塞进 Unit 然后整体 deepcopy。

Unit 可以是组合结构，也可以只是已有 `UnknownState` 的受约束视图。是否需要独立类，应由结构差异决定，不能以“每个算法必须有一个新类”为目标。

### 2.4 Candidate 和 Unit 要保留各自含义

[UnknownState](C:/Users/hp/Desktop/blackbase/src/blackbase/types.py:354) 和 [CandidateBatch](C:/Users/hp/Desktop/blackbase/src/blackbase/types.py:427) 已承担候选语义、数值矩阵、token 和行对齐。它们可以成为 Unit 的组成部分，但不能直接替代所有 Unit。

例如一个路径节点含父节点和累计代价；送给 Problem 的可能只是该节点的状态编码。两个节点的状态编码相同，也可能代表不同路径。

建议保持以下关系：

```text
算法管线 --构建--> Unit
Adapter  --操作--> Unit --投影--> 候选
候选 --问题管线检查/修复--> CandidateBatch --Solver 评估--> feedback
Adapter <--按提案记录与身份关联-- feedback
```

这里的投影是显式的结构到候选转换。候选变更后，需要重新核对关联结构，而不是按数值相等猜回原 Unit。

## 三、复用现有基础，只补必要接口

### 3.1 已有基础

- [BlackBase PipelineSlotSpec](C:/Users/hp/Desktop/blackbase/src/blackbase/kernel/spec.py:38) 已支持自定义 slot 和调用方法；底层 kernel 可以承载 Unit 构建步骤。
- [nsgablack 的 pipeline kernel 适配层](C:/Users/hp/Desktop/nsgablack/representation/pipeline_kernel.py:56) 目前把标准 init/mutate/repair/encode/decode 槽映射为 RepresentationPipeline，其他 runner 并不因此变成正式 Adapter 构建入口。
- [Solver 候选入口](C:/Users/hp/Desktop/nsgablack/core/blank_solver.py:2701) 会处理候选维度与表示；不宜直接用它装载任意图节点或子空间对象。
- [ComposableSolver](C:/Users/hp/Desktop/nsgablack/core/composable_solver.py:761) 已有 propose、候选规整、repair、评估、disposition 和 update 链路，应保留。
- Adapter 已有步骤事务、checkpoint、子组件声明和种群权威协议，Unit 状态接入这些协议即可。

### 3.2 建议新增的最小契约

以下是最小契约设计；后续第一批已经实现 UnitSchema、UnitBuildRequest、UnitBinding。具体签名以使用说明及源码为准；这里的 UnitBuilder 是构建器角色称谓，并非已导出的公共基类。

1. `UnitSchema`：结构族、版本、维度约束、必要字段与候选投影形式。不要求全部 Unit 继承一个庞大基类。
2. `UnitBuildRequest`：构建目的、输入状态或引用、Adapter 指定的结构参数、构建 RNG/种子、构建器版本。区分 fresh、spawn、refresh、restore，避免恢复时重新初始化。
3. `UnitBuilder.build(request)`：构建新 Unit 或新的结构版本；不得偷偷评估 Problem、提交 Snapshot、推进 generation 或更新已有搜索群体。
4. `UnitBinding`：在装配时绑定 Adapter、builder、schema、候选投影和状态编码方式。可以直接注入 Adapter，不必新增全局可变注册状态。
5. 提案关联记录：记录 proposal/Unit/parent/target 等身份，配合已有 `BatchDisposition`、candidate token 和 feedback 完成对齐。

`build_unit` 可作为正式 slot 名；schema 校验、投影和持久化编码首先做成普通可组合组件，只有确有独立装配需求时才增加 slot，避免一次引入大量生命周期钩子。

建议每个 Adapter 声明**结构需求**，而非绑定某个 pipeline 类名。例如 A* 声明需要可投影状态、父关联和路径代价字段；不同路径领域都可提供满足该契约的 builder。

### 3.3 保持现有 Adapter 外部接口

第一阶段保留：

```text
propose(control, context) -> 候选序列
update(control, candidates, OptimizationFeedbackBatch, context) -> None
```

Adapter 内部使用 Unit；对外通过现有候选协议送评。不要直接把任意 Unit 返回给当前 `propose()`，让 Solver 猜测如何转矩阵。

对于简单向量算法，候选本身即可满足轻量 Unit 契约，builder 可以是验证并保留语义的恒等构建器。复杂算法使用独立结构，并保留 Unit 到候选的显式映射。

### 3.4 构建与反馈的生命周期

1. Case 装配时校验 Adapter 所需结构与 builder 输出是否兼容。
2. `setup` 准备绑定、工具和必要资源，不抢先覆盖待恢复的算法状态。
3. 恢复时按现有 restore envelope 顺序恢复 Unit 与 Adapter 控制状态；fresh 路径才构建初始 Unit。
4. Adapter 决定扩展或采样，向 builder 发出结构构建请求。
5. 投影候选，经过问题管线；若候选发生变化，执行明确的结构重绑定、重建或拒绝规则。
6. 预算裁剪、取消或重排时，用 disposition 同步裁剪关联记录。
7. Adapter 消费 feedback，执行选择与更新；按现有步骤事务提交或回滚。

Builder 不保证算法收敛、完备或最优；它保证声明的操作结构可用。问题可行性、结构适配性、算法性质应分别验证。

### 3.5 身份、恢复和资源

- `unit_id` 标识结构实例；candidate token 标识送评候选关联，二者不可默认等价。多个 Unit 可以投影为相同数值。
- 大结构进入 Snapshot 或正式引用，context 只放轻量字段和引用；不可把完整 frontier、历史、种群重新塞入 context。
- 可重建缓存必须声明来源和失效条件；权威状态不能仅以“可重算”为由丢失。
- 首轮迁移应保持原 RNG 调用顺序；以后拆分 builder RNG 与 Adapter RNG 时，要明确这是可复现序列的版本变更。
- 父 Adapter 的步骤事务只保存本地状态，子 Adapter 通过 `step_transaction_children()` 独立参与，避免重复保存与回滚。
- [StateRef](C:/Users/hp/Desktop/blackbase/src/blackbase/state_ref.py:21) 是 Provider 活状态引用，不是任意可离线恢复的文件引用。Unit 可以持有它，但仍须遵守 Provider 的物化、恢复与清理协议。

## 四、31 个主干 Adapter 的逐项方案

本节的 Unit 名称是可讨论的设计名，不代表必须建立 31 个互不相关的类。各项验收列的是目标要求；第一批实际执行范围另见使用说明中的验证记录。

### 01. AlgorithmAdapter

源码：[algorithm_adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/algorithm_adapter.py:191)。类别：公共基类。

- **现状**：定义 propose/update、候选处理、状态与事务、population/partition 等公共接口；没有统一的算法结构构建绑定。
- **Unit**：基类只认识结构需求和绑定协议，不知道 A* 节点、Adam 动量或 MOEA/D 邻接表的具体字段。
- **怎么构建**：Case 注入匹配的 UnitBinding；简单算法允许默认轻量候选构建器，复杂算法缺少匹配绑定时在装配阶段报错。
- **怎么改**：补结构需求声明、绑定验证和统一构建调用入口；将 Unit 编码接入已有 get/set state 与步骤事务。不要在基类中根据算法名写分支。
- **Adapter 保留**：各具体算法的 propose/update 策略和状态所有权。
- **验收**：旧简单 Adapter 可渐进迁移；复杂结构不匹配能提前定位；不新增一套独立于现有事务的 Unit 提交机制。

### 02. AStarAdapter

源码：[adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/astar/adapter.py:75)，已有私有 `_Node` 位于同文件第 64 行。

- **现状**：`_Node(state, g, h, parent_key)` 保存节点，open 使用堆，closed 记录状态代价；`_pending` 另存父键和 base_g。节点构造埋在 `_push_open()` 中，neighbors、heuristic、edge_cost、state_key 等已可注入。
- **Unit**：`SearchNodeUnit`，包含稳定节点身份、语义状态/候选投影、父节点身份、g/h 等路径注记。open/closed 是 Adapter 操作该结构的搜索状态，不必全部合成一个巨型节点。
- **怎么构建**：初始状态或邻接状态 + Adapter 给定的父关联和已计算代价 → 节点 builder → SearchNodeUnit。算法管线可装配邻接、编码、启发式和边代价工具；Adapter 决定调用次序、扩展和优先级。
- **怎么改**：提取 `_Node` 及其构造；拆开 `_push_open()` 的“建节点”和“计算优先级/入堆”；`_pending` 改为有身份的提案关联。`f=g+h` 的策略不能因原来写在构造函数中，就被误认为任意 builder 都可更改的结构规则。
- **Adapter 保留**：弹出顺序、closed/reopen、g 累计模式、目标检测、剪枝、open 限制与搜索终止。
- **验收**：相同状态、不同父路径仍能区分；repair 改变 child 后，原边代价必须重算、验证兼容或拒绝。当前代码先记 base_g 再进入公共 repair，不能仅按行数对齐就宣称路径语义正确。
- **恢复边界**：当前声明 L0，get_state 不保存完整 frontier。引入节点类不会自动获得精确续跑；完整恢复需要另行保存节点、堆、closed、关联记录及顺序状态。

### 03. MOAStarAdapter

源码：[adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/moa_star/adapter.py:83)，已有 `_Label` 位于第 71 行。

- **现状**：一个状态可有多个标签；`_labels`、`_state_labels`、open、Pareto 集分别维护标签、索引和搜索结果。`_try_add_label()` 同时完成支配检查、旧标签失效、构造和入堆。
- **Unit**：`MultiObjectiveLabelUnit`，保留 label_id、状态、g/h 向量、父标签关联及有效性信息。不能用“状态键唯一”替代“标签唯一”。
- **怎么构建**：状态 + 目标维度 + Adapter 计算的代价向量 + 父标签 ID → 标签 builder；校验向量维度，装配标签。算法管线可与 A* 共享状态编码和邻接工具，但标签 schema 必须区分标量与向量代价。
- **怎么改**：从 `_try_add_label()` 中仅提取实例化和结构校验；保留支配关系处理。将 parent_key 逐步补充为可定位具体标签的关联，不声称现有父状态键已经支持完整路径恢复。
- **Adapter 保留**：标签支配淘汰、Pareto 更新、向量到队列优先级的策略、路径成本模式和开放集裁剪。
- **验收**：同一状态的互不支配标签不被合并；维度变化拒绝；剪裁后的反馈关联正确。当前同样为 L0，不把 Unit 提取当作恢复能力升级。

### 04. VNSAdapter

源码：[adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/vns/adapter.py:45)。

- **现状**：当前候选、当前分数、邻域索引 k 和 sigma 调度由 Adapter 持有；通过 context 把邻域参数传给 mutate/repair，已有对管线配置的提醒。
- **Unit**：基础采用 `CandidateUnit`；若要把不同邻域真正独立建模，再增加 `NeighborhoodStructure`，描述邻域身份、可用操作和结构参数。不要把“k 的循环”包装成 builder。
- **怎么构建**：问题候选 + 邻域声明 → 候选及邻域结构；Adapter 选择 k 后，按该结构调用相应邻域工具，并为新候选请求构建。
- **怎么改**：抽出当前候选的构建/重启输入；把隐含依赖的 `k/sigma` 语义变成明确的邻域构建契约。现有 ContextGaussianMutation/ContextSelect 类工具可复用。
- **Adapter 保留**：改善判定、k 重置/递增、sigma 使用方式、重启条件和预算分配。
- **验收**：同一 VNS 可替换高斯、交换、插入等合法邻域结构；不支持多个邻域的绑定不能仅凭一个通用 mutate 方法被当作完整 VNS 管线。

### 05. SimulatedAnnealingAdapter

源码：[adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/simulated_annealing/adapter.py:52)。

- **现状**：current_x/current_score、温度和 RNG 由 Adapter 维护；管线生成扰动，Adapter 逐项判断接受并降温。
- **Unit**：复用轻量 CandidateUnit；可绑定领域邻域结构。温度属于接受策略的控制状态，无须为了抽象而移入候选。
- **怎么构建**：初始候选或扰动结果 + 语义编码 → 候选 Unit；领域邻域工具由算法管线装配，问题约束由问题管线处理。
- **怎么改**：统一初始/后继候选构建和邻域绑定，保留温度相关 context 的明确输入契约。
- **Adapter 保留**：Metropolis 接受、候选检查顺序、降温时机、当前状态转移。
- **验收**：接受随机数流和每步降温次数保持；换 Unit builder 不得暗改接受规则。

### 06. SingleTrajectoryAdaptiveAdapter

源码：[adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/single_trajectory_adaptive/adapter.py:47)。

- **现状**：持有 current/best 候选和分数、sigma、无改善计数、成功历史 deque、步数及 RNG；根据成功率调整扰动尺度并触发重启。
- **Unit**：共享 CandidateUnit；可用小型轨迹结构显式保存 current/best 引用，但不必把成功窗口也包装为结构构建工作。
- **怎么构建**：初始点、扰动结果或重启种子 → 候选 Unit；重启请求中显式说明初始化来源。
- **怎么改**：抽取候选初始化、复制和语义保留；让邻域定义可换。控制状态继续通过 Adapter checkpoint 管理。
- **Adapter 保留**：较差解接受概率、成功窗口更新、sigma 调整、best 更新和重启决策。
- **验收**：恢复后 deque、RNG 和尺度一致；重启构建器不能自行根据历史评分决定重启。

### 07. PatternSearchAdapter

源码：[adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/pattern_search/adapter.py:27)。

- **现状**：选取坐标方向，构造正负步长候选，repair 后送评；通过最好候选的改善情况扩张或缩小 step_size。
- **Unit**：`PollGeometryUnit` 描述方向集合，配合轻量候选；必要时增加 poll batch 记录方向和来源中心。
- **怎么构建**：维度/方向规则 → 方向结构；Adapter 指定中心、选中方向和步长 → 轮询候选批。非坐标方向可以替换构建器。
- **怎么改**：提取 `propose()` 中的方向几何与候选装配；接入候选修复后的几何一致性说明。
- **Adapter 保留**：选择哪些方向、argmin 接受、步长扩张/收缩和停止条件。
- **验收**：更换方向结构无需修改接受逻辑；该实现是方向轮询，不要把它的候选硬解释成有限差分梯度探针。

### 08. GradientDescentAdapter

源码：[adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/gradient_descent/adapter.py:30)。这是有限差分实现，与后文消费显式梯度的 GradientOptimizerAdapter 分开。

- **现状**：`_pending_probes` 记录维度与正负号，propose 生成 ±eps 探针，disposition 裁剪关联，update 用成对反馈估计梯度。
- **Unit**：`FiniteDifferenceProbeBatchUnit`，包含中心、pair_id、维度/方向、符号、名义与实际位移、候选身份。
- **怎么构建**：Adapter 指定中心、选中维度和 eps → builder 构建探针对与映射；问题管线处理候选后，显式核对实际位移。
- **怎么改**：将探针列表和 `_pending_probes` 合为有结构的提案对象；propose 投影为普通候选，update 按 pair_id 恢复有效配对。
- **Adapter 保留**：维度选择、梯度估计、学习率与步进、接受逻辑。
- **验收**：预算只保留半对时不得错配；repair 改变位移时，不能默认分母仍代表原始 `2*eps`。
- **保留的现状边界**：当前实现使用探针分数作为新点接受的代理，没有对每个梯度步新点再做独立评价。Unit 迁移应记录并保持这一语义；若改成重新评估，必须作为独立算法行为变更。

### 09. GradientOptimizerAdapter

源码：[adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/gradient_optimizer/adapter.py:90)。

- **现状**：实现 SGD/Adam/AdamW 路径，持有参数、动量、平方动量、步数、候选语义模板；还支持 Provider StateRef、slot 引用、事务恢复和延迟清理。
- **Unit**：`ParameterUnit` 加 `OptimizerSlots`。参数可本地存储或引用 Provider；Adam 槽和 SGD 槽按方法声明，不能强制所有优化器都分配两个动量数组。
- **怎么构建**：参数 schema、初始 UnknownState/StateRef、优化器所需槽布局 → 参数与槽结构。算法管线负责维度、dtype、语义编码和槽的初始装配；实际资源仍通过已有 Provider/Gateway 获得。
- **怎么改**：抽取 `_capture_candidate_template()`、`_wrap_candidate()` 的结构职责和 `_optimizer_delta()` 内首次分配槽的部分；Provider 绑定只保存正式引用，不复制后端对象图。
- **Adapter 保留**：梯度裁剪、动量公式、bias correction、weight decay、步数递增，以及何时发起 Provider transition。
- **验收**：本地与 Provider 两条路径语义一致；参数/槽引用随回滚正确恢复；commit 后清理失败仍进入可重试队列，不能因 Unit 引入丢失现有 commit report。
- **特别约束**：恢复槽是按保存状态恢复，不是把零初始化 builder 再运行一遍。

### 10. GaussianSearchAdapter

源码：[adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/gaussian_search/adapter.py:44)。

- **现状**：保存最好候选及分数/违反度，围绕中心高斯采样，支持保留中心；`_wrap_candidate()` 保留 UnknownState 的 kind/metadata。
- **Unit**：复用 CandidateUnit；额外结构最多是中心候选及编码 schema。当前没有完整高斯协方差学习结构，不应虚构成分布估计算法。
- **怎么构建**：初始候选或 Adapter 采样得到的数值 + 语义模板 → 候选 Unit。
- **怎么改**：把候选包装和结构校验独立到 builder；采样工具可复用，但搜索中心选择与采样策略仍在 Adapter。
- **Adapter 保留**：围绕谁采样、是否包含中心、可行性优先比较和 best 更新。
- **验收**：数值相同而 metadata 不同的候选不丢语义；替换 builder 不改变可行性比较顺序。

### 11. FixedCandidateAdapter

源码：[adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/fixed_candidate/adapter.py:12)。

- **现状**：从控制面初始化一个候选，update 校验候选数量为 1；不承担搜索更新。
- **Unit**：已有 UnknownState/候选即可，采用恒等或轻量构建器。
- **怎么构建**：Case 提供的固定语义状态或 initializer 结果 → 验证后直接作为候选 Unit。
- **怎么改**：显式声明所需候选结构和构建绑定即可；无须新增 FixedCandidate 专属数据类。
- **Adapter 保留**：单候选提案和数量契约。
- **验收**：固定候选的语义 metadata 保留；单次评价由 Case 的运行预算控制，不把训练器、模型拟合或 backend 会话塞进这个 Unit。

### 12. DifferentialEvolutionAdapter

源码：[adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/differential_evolution/adapter.py:43)。

- **现状**：种群 X/F/V、candidate tokens 与 `_last_target_indices` 等提案映射分开维护；实现差分变异、交叉、修复和逐目标替换。
- **Unit**：共享 `PopulationUnit`，加 `DETrialBatchUnit`，显式记录 trial 对应的目标槽、目标身份和比较基线。
- **怎么构建**：初始候选批 → 种群结构；Adapter 选定 target 和生成 trial 后 → builder 装配 trial 与 target 关联。
- **怎么改**：抽取初始种群及提案记录装配；让 population 与 tokens、反馈、目标映射一起做结构校验。
- **Adapter 保留**：rand/1、best/1 等变异策略、binomial crossover、目标选择和贪心替换。
- **验收**：同一个 target 在一批中多次出现时，明确保持当前顺序语义；裁剪和重排后不替换错行；新建未评分群体必须显式表示“未评估”，不能构造假反馈。

### 13. NSGA2Adapter

源码：[adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/nsga2/adapter.py:36)。

- **现状**：X/F/V/tokens、rank、crowding 分别持有；父代选择、交叉、变异、合并和环境选择在 Adapter 中完成。
- **Unit**：共享 PopulationUnit，成员保持候选语义与 token；rank/crowding 可以是带失效规则的附属缓存，而非新的权威候选集合。
- **怎么构建**：已初始化候选及可选反馈 → 对齐的种群结构；Adapter 选定保留索引后，由结构工具按同一索引装配新种群。
- **怎么改**：抽取 `_ensure_population()` 的数据构建部分以及多数组对齐/子集构建；保留已有 Snapshot 的唯一权威关系，不能再增一份互相漂移的完整 population。
- **Adapter 保留**：非支配排序、拥挤度计算、锦标赛、交叉策略和环境选择。pipeline 中已有 crossover/mutate 工具仍由 Adapter 调用。
- **验收**：环境选择后所有成员 token 与语义状态一致；不能通过 X 数值相等反查候选；rank/crowding 在种群改变后失效或更新。

### 14. NSGA3Adapter

源码：[adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/nsga3/adapter.py:21)。

- **现状**：继承 NSGA2，另建参考点；环境选择使用归一化、参考方向关联和 niching。
- **Unit**：复用 PopulationUnit，加 `ReferenceDirectionUnit`，保存参考方向矩阵、目标维度、生成规则与版本。
- **怎么构建**：目标数 + divisions 或用户给定方向 → builder 构建并校验参考方向；当前 `_generate_reference_points()` 的 simplex 几何构造适合移出。
- **怎么改**：setup 使用注入的参考方向构建器；自定义参考方向进入状态/配置审计。避免迁移后恢复时又悄悄生成默认方向。
- **Adapter 保留**：归一化策略、个体与方向的关联、niche 占用计数、边界前沿选择。
- **验收**：同一 niching 流程可消费规则格点与定制方向；目标维度不符在运行前报错；继承的种群 token 契约保持。

### 15. SPEA2Adapter

源码：[adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/spea2/adapter.py:21)。

- **现状**：继承 NSGA2，主要替换环境选择，计算 strength/raw fitness、密度和距离截断。配置中有 archive_size，但当前实现没有独立持有一个完整 SPEA2 archive 容器。
- **Unit**：当前先复用 PopulationUnit；如需复用距离存储，可声明 selection workspace，不应为了符合算法教科书名字凭空补一个 archive。
- **怎么构建**：对齐种群/合并候选 + 所需缓冲维度 → 种群结构与可选工作区。
- **怎么改**：共享父类种群构建绑定；把纯存储分配与数据子集装配独立出来即可。
- **Adapter 保留**：strength、density、fitness 排序与截断规则。
- **验收**：结果与当前实现对齐；若未来真正增加外部档案，作为额外算法行为变更引入 ArchiveUnit 和相应权威状态契约。

### 16. MOEADAdapter

源码：[adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/moead/adapter.py:60)，权重与邻域构造位于第 639 行之后。

- **现状**：持有种群、weights、neighbors、ideal、pending 子问题索引及模式；权重生成、邻域计算和种群初始化都在 Adapter。setup 还会通过控制面评价初始种群。
- **Unit**：`DecompositionUnit`，组合 PopulationUnit、稳定子问题 ID、权重、邻域索引和 ideal 存储。ideal 的数值更新权仍属于 Adapter。
- **怎么构建**：有效种群规模、目标维度、权重生成配置、邻域大小、初始候选 → 分解结构。提取 `_generate_weights()`、simplex helpers、`_compute_neighbors()` 及结构装配。
- **怎么改**：构建器消费已经解析的预算/规模，不能自行向 L0 申请资源；初始评价继续走控制面，不能随 setup 代码整体搬进 builder。
- **Adapter 保留**：子问题采样、邻域/全局交配选择、变异、标量化、ideal 更新与最多 nr 个替换。
- **验收**：改变权重或邻接构建器不需要修改更新策略；恢复后的权重/邻域保持原值；子问题关联随 disposition 裁剪；当前 L2/single population 契约保持。
- **忠于当前实现**：`random_dirichlet` 分支实际使用正随机数再行归一化；纯结构迁移先保留现有采样过程，不顺手替换分布。

### 17. TrustRegionBaseAdapter

源码：[adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/trust_region_base/adapter.py:17)。类别：信赖域家族基类。

- **现状**：持有 center、radius、best_score、RNG；采样 center + radius*delta，按改善扩大或缩小半径。
- **Unit**：`LocalRegionUnit`，包含中心候选和局部几何定义；半径可作为结构参数保存，但扩大/缩小规则由 Adapter 控制。
- **怎么构建**：初始中心来源、维度、局部几何和初始尺度 → 区域结构；子类注入几何构建器。
- **怎么改**：抽出 `_init_center()` 中的来源选择接口和结构装配，统一子类对中心/几何的访问。不要把 `_before_propose/_after_update` 的所有策略逻辑一起搬走。
- **Adapter 保留**：中心接受、改善判定、radius 更新与子类控制钩子。
- **验收**：家族共用结构协议；当前私有 `_clip_to_bounds()` 应明确归入问题可行性路径，迁移时核对已有公共 repair 是否再次执行，避免改变候选两次而不自知。

### 18. TrustRegionDFOAdapter

源码：[adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/trust_region_dfo/adapter.py:28)。

- **现状**：基于父类局部搜索，方向采样为逐坐标的 uniform(-1, 1)，再乘半径。
- **Unit**：复用 LocalRegionUnit，默认几何是坐标盒。当前没有构建二次代理模型，不需要虚构 QuadraticModelUnit。
- **怎么构建**：维度 + 默认盒几何或可替换方向几何 → 区域结构。
- **怎么改**：仅将硬编码几何描述和候选结构装配绑定到构建器，复用基类迁移。
- **Adapter 保留**：采样请求、评分、中心/半径更新。
- **验收**：默认构建器复现当前盒采样；替换球形等几何应记录为配置选择，不能声称默认一直是球形信赖域。

### 19. TrustRegionMODFOAdapter

源码：[adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/trust_region_mo_dfo/adapter.py:31)。

- **现状**：在局部区域搜索上增加目标权重，支持 context、固定权重及随机权重等来源，使用加权评分。
- **Unit**：LocalRegionUnit + 小型 `ObjectiveWeightStructure`；不需要复用 MOEA/D 的完整邻域分解结构。
- **怎么构建**：目标维度和明确的权重来源 → 校验后的权重向量；由 Adapter 决定本轮使用既有权重还是请求构建新权重。
- **怎么改**：提取 `_get_weights()` 中纯生成/验证职责，保留来源优先级和刷新时机的显式策略。
- **Adapter 保留**：标量化决策、罚项、改善接受与半径变化。
- **验收**：context 权重覆盖、固定权重与随机权重的优先级保持；恢复时不意外消耗一次新的随机权重。

### 20. TrustRegionNonSmoothAdapter

源码：[adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/trust_region_nonsmooth/adapter.py:29)。

- **现状**：沿用基类采样和局部更新，非光滑部分体现在 sum_abs/max_abs 等评分模式；没有维护次梯度束或切平面集合。
- **Unit**：复用 LocalRegionUnit，无须单独引入“非光滑模型”结构。
- **怎么构建**：按父类构建中心和几何，明确目标反馈维度。
- **怎么改**：迁移父类结构绑定，评分配置留在本类；不为抽象统一捏造当前不存在的 bundle。
- **Adapter 保留**：非光滑评分聚合及中心/尺度更新。
- **验收**：不同评分模式结果保持；若未来实现 bundle method，届时再增加切平面 Unit 和新的搜索策略。

### 21. TrustRegionSubspaceAdapter

源码：[adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/trust_region_subspace/adapter.py:32)。

- **现状**：除中心和半径，还持有 basis 和刷新步数；支持随机正交基、从种群构建 PCA/SVD、稀疏 PCA、KMeans 等基方向，并使用 B@z 生成增量。
- **Unit**：`SubspaceUnit`，记录原维度、子空间维度、basis、构建方法和来源 Snapshot/版本，可组合进 LocalRegionUnit。
- **怎么构建**：种群快照或随机源 + 方法配置 + d/k → 基矩阵及来源信息。`_sample_subspace()`、`_build_or_sample_basis()`、`_build_basis_from_population()` 的结构构建职责适合抽取。
- **怎么改**：算法管线构建并验证基矩阵；记录 fallback 原因；Adapter 通过 binding 获取当前 SubspaceUnit。
- **Adapter 保留**：`_before_propose()` 的刷新时机、低维采样选择、中心和半径演化。
- **验收**：更换 PCA/随机/稀疏基无需改搜索方法；维度、数值有效性和所声明的基性质可检查；checkpoint 保留实际基矩阵或足以确定性恢复的证据，不能随意重采样。

### 22. MASAdapter

源码：[adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/mas/adapter.py:30)。这里是 **Model-and-Search**，不是多智能体 Adapter。

- **现状**：持有 center、VectorSurrogate、X/Y 历史和 RNG；探索时随机提案，利用阶段根据模型预测筛选，并按反馈扩充历史和拟合代理模型。
- **Unit**：`ModelSearchUnit`，包含中心候选、对齐的历史数据/引用，以及可明确恢复的 surrogate 引用或模型描述。
- **怎么构建**：中心、历史 schema、surrogate factory/provider binding → 工作结构和未拟合模型容器；builder 可以构造模型，不能在背后训练、选择候选或修改搜索历史。
- **怎么改**：提取 `_init_center()` 的结构职责、历史容器和 `_ensure_surrogate()` 的模型实例化；把何时拟合与拟合调用分开。大历史走 Snapshot，模型后端走正式 Provider/bridge。
- **Adapter 保留**：探索/利用分配、预测候选排序、中心接受、历史采样范围、拟合触发规则；拟合计算可调用专门工具。
- **验收**：模型可替换而搜索调度保持；恢复明确区分“加载模型引用”和“按历史重新拟合”。当前恢复存在从历史重建 surrogate 的路径，不能把重训副作用隐藏在通用 Unit 解码中。
- **边界**：若改用 mlblack 模型，通过正式 ML surface；不因引入 Unit 强制把每次代理拟合都变成一个新 Case。

### 23. EliteRetentionAdapter

源码：[adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/elite_retention/adapter.py:34)。

- **现状**：包装 inner Adapter，保存精英档案；propose 可用精英扰动结果替换 inner 提案的尾部，update 再更新档案。
- **Unit**：自己的 `EliteArchiveUnit` 保存评估过的候选及身份；inner 的 Unit 仍由 inner 自己持有和构建。
- **怎么构建**：档案容量、候选 schema、可选恢复条目 → 档案结构；精英扰动结果需通过 inner 明确接受的构建/提案注入协议。
- **怎么改**：把无结构的 archive 字典条目改为保留语义与 token 的记录；补 inner 的“候选能否被替换”能力声明及重绑定机制。
- **Adapter 保留**：精英挑选、保留比例、档案排序/截断和扰动调用。
- **验收**：对 A* 父边关联、有限差分探针对、DE target 映射等有结构提案，不能只保持候选数量就任意替换。未声明兼容的 inner 应拒绝这种组合或使用正式重构协议。
- **事务**：本地档案与 inner 分别保存/回滚，复用已有 child transaction；不重复复制 inner 状态。

### 24. RoleAdapter

源码：[adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/role_adapters/adapter.py:44)。

- **现状**：包装 inner，注入角色 context、限制候选数、转发 feedback/disposition 与状态。
- **Unit**：直接委托 inner 的结构；角色名属于角色/来源注记，不需要把所有候选再包成 RoleUnit。
- **怎么构建**：装配时把 role 对应的 UnitBinding 传给 inner；role 需要额外领域结构时，在其子管线中声明。
- **怎么改**：补结构需求和构建绑定的透明转发；限额裁剪同时转发候选到 Unit 的关联处置。
- **Adapter 保留**：角色隔离、候选上限和报告职责。
- **验收**：包装前后 inner 的 Unit 身份不变；角色限制不会让 pending 映射保留被丢弃候选。

### 25. RoleRouterAdapter

源码：[adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/role_adapters/adapter.py:480)。

- **现状**：组合多个角色，维护提案区间和 candidateRoles，分发反馈，使用分区 population authority。
- **Unit**：各角色自己的 Unit，加可选轻量 `RoleDispatchRecord`；不存在必须统一所有角色内部结构的要求。
- **怎么构建**：按稳定 role ID 装配子 Adapter 与其独立算法管线；路由记录按本轮实际提案构建。
- **怎么改**：扩充角色装配信息以携带 builder binding；合并候选时保留角色、子 Unit 与 token 来源。
- **Adapter 保留**：角色路由、区间计算、预算裁剪和反馈分发。
- **验收**：不同角色可使用不同 Unit schema；分区快照不能无语义地拼成一个种群；恢复后 role 到构建器的绑定稳定。

### 26. StrategyChainAdapter

源码：[adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/serial_strategy/adapter.py:51)。

- **现状**：按 phase 串行切换子 Adapter，预先 materialize/setup 子实例；保存 active phase 与 population owner，它们并非始终相同。
- **Unit**：每个 phase 的子 Unit 独立存在；可选 `PhaseTransferRecord` 表示跨阶段传递的候选/Artifact 引用。
- **怎么构建**：为每个 phase 绑定自己的 builder；阶段切换时若要 warm start，显式从上阶段导出候选，再由下阶段 builder 构建目标结构。
- **怎么改**：phase spec 可声明构建绑定和 transfer 规则；保留已准备好的子组件身份，不通过临时修改 Solver 全局 pipeline 来切换算法。
- **Adapter 保留**：切换条件、各阶段步数、反馈交付及 population owner 管理。
- **验收**：DE 种群进入 VNS 时明确选取种子；不能把整个 PopulationUnit 强转成轨迹候选。checkpoint 恢复 active phase 和权威群体所有者均正确。

### 27. StrategyRouterAdapter

源码：[adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/multi_strategy/adapter.py:181)，已有 `UnitSpec` 在第 90 行。

- **现状**：roles/strategies、多个执行实例、预算分配、区域、任务种子、权重适应、pending context 和分区群体一起工作。
- **命名冲突**：当前 `UnitSpec` 表示带 role/id/adapter 的策略执行实例，**不是本次定义的算法操作结构**。建议改名为 `StrategyInstanceSpec` 或 `WorkerSpec`；如需保持外部兼容，先保留明确标注的别名。
- **Unit**：每个子实例持有自己的算法 Unit；可选区域结构独立描述区域边界。执行实例本身仍是组合配置，不作为 SearchUnit。
- **怎么构建**：按稳定实例 ID 调用 Adapter/builder 工厂，构建各自 Unit；允许共享不可变几何，禁止共享可变搜索状态。
- **怎么改**：扩展 StrategySpec/RoleSpec 的实例装配路径以传递 UnitBinding；区域结构构造可提取，区域分配和刷新决策留在 router。
- **Adapter 保留**：预算分配、阶段策略、EMA 权重调整、任务/种子选择和路由。
- **验收**：一个 router 可同时装配 A* 节点管线与 VNS 邻域管线；子实例彼此隔离；disposition、命名空间、partition 和 checkpoint 都能追到同一稳定实例。

### 28. AsyncEventDrivenAdapter

源码：[adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/async_event_driven/adapter.py:101)。

- **现状**：事件队列、inflight、case 触发条件、按 strategy 聚合提案、反馈分发、档案与统计；源码当前声明 L2/partitioned。这里的 EventCaseSpec 是事件触发配置，不能与 Project/Case 目录中的 Case 混同。
- **Unit**：子策略继续使用自己的 Unit；路由器可使用类型化 `EventRecord`、`DispatchRecord` 表达 event_id/strategy/来源/关联 Unit。
- **怎么构建**：装配时绑定每个子策略的 builder；按 Adapter 已决定的派发内容构建事件记录与候选关联。
- **怎么改**：将 `_enqueue_propose()` 与 `_inflight` 的字典结构显式化，并补子构建绑定；`update()` 分组回传时保留 proposal context 和 Unit 身份。
- **Adapter 保留**：when/cooldown/优先级、队列补充、溢出策略、完成事件生成和统计策略。
- **验收**：事件被丢弃、裁剪、重复完成或恢复后，不会更新错误子 Unit；物理异步执行仍由正式 runtime/L0 负责，Unit builder 不新建线程池。

### 29. CompositeAdapter

源码：[algorithm_adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/algorithm_adapter.py:567)。

- **现状**：顺序调用多个子 Adapter 的 propose 并合并候选；保存区间，按 feedback 子集分发；使用 partitioned population authority。
- **Unit**：无须新的算法 Unit。需要一个子组件到 UnitBinding 的组合关系及每批提案来源记录。
- **怎么构建**：各子组件独立构建；Composite 只组合投影后的候选与来源信息，不扁平化子结构。
- **怎么改**：把构建绑定纳入子组件装配，保持 `_last_ranges` 和 disposition 与子 Unit 映射一致。
- **Adapter 保留**：组合、分发、生命周期转发和分区状态协议。
- **验收**：不同结构族可组合且独立恢复；同值候选也能回传到正确孩子；不重复执行子 Unit 的构建或事务快照。

### 30. MultiStrategyControllerAdapter

源码：[adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/multi_strategy/adapter.py:1774)。类别：StrategyRouterAdapter 的兼容子类。

- **现状**：主要保留旧名称及契约属性，没有另一套独立搜索实现。
- **Unit 与构建**：完全复用 StrategyRouterAdapter 的子实例绑定方案。
- **怎么改**：仅转发新增契约，补迁移说明；不要复制 builder、创建另一个 Unit 家族或维护分叉状态 schema。
- **验收**：旧名称与正式名称装配相同结构，恢复兼容策略明确。

### 31. MultiRoleControllerAdapter

源码：[adapter.py](C:/Users/hp/Desktop/nsgablack/adapters/role_adapters/adapter.py:785)。类别：RoleRouterAdapter 的兼容子类。

- **现状**：兼容旧入口，不是额外的角色搜索算法。
- **Unit 与构建**：完全复用 RoleRouterAdapter 的 role 到子 UnitBinding 方案。
- **怎么改**：转发契约和文档说明，不增加专属结构。
- **验收**：角色身份、分区恢复和反馈映射与正式名称一致。

## 五、算法管线具体怎么组装

### 5.1 可复用的结构族

第一批结构可以收敛到以下几族，而不是为每个类新建一套体系：

1. **候选/评估成员结构**：服务 FixedCandidate、Gaussian、VNS、SA、SingleTrajectory，以及各类简单提案器；允许直接复用 UnknownState。
2. **种群结构**：服务 NSGA2、NSGA3、SPEA2、DE、MOEA/D；不同算法附加自己的参考方向、子问题或 trial 关联。
3. **图搜索节点/标签结构**：服务 A*、MOA*；共享状态投影工具，但保留标量路径与多目标标签的差异。
4. **局部几何/探针结构**：服务 PatternSearch、有限差分、信赖域、子空间信赖域；方向集合可以共享，反馈解释协议必须各自明确。
5. **参数及计算状态结构**：服务梯度优化器；区分本地数组与 Provider 引用。
6. **模型搜索工作结构**：服务 MAS，组合候选、历史和模型句柄。
7. **档案/提案关联记录**：服务 EliteRetention 和组合器；记录结构来源，不替代被组合算法的 Unit。

共享结构不等于共享策略。例如 NSGA2 与 DE 都能使用 PopulationUnit，但环境选择与一对一 trial 替换仍是不同操作。

### 5.2 A* Case 的建议装配

```text
Case.problem
  评价目标

Case.pipeline.problem
  状态编码/解码、合法状态检查、约束处理

Case.pipeline.algorithm
  图/邻接数据与工具绑定
  节点 builder：状态、父引用、代价注记 -> SearchNodeUnit
  节点 -> 候选的投影

Case.adapter
  AStarAdapter：扩展、队列、路径代价演化、关闭集、终止

Case.build_solver
  将 Problem、两类管线组件、Adapter、Plugin 正式装配
```

这个分法允许同一个 AStarAdapter 使用不同的状态编码、邻接生成方式和节点附加信息。它不意味着随意替换启发式、代价或 pruning 后仍自动保有相同算法性质。

### 5.3 VNS Case 的建议装配

```text
问题管线：排列编码、时间窗/容量等可行性处理
算法管线：CandidateUnit + 邻域描述（例如 swap、insert、2-opt）
Adapter：选择邻域 k、调用邻域工具、消费反馈、改善后重置 k
```

邻域描述决定“可以做哪种结构操作”；邻域循环和接受策略决定“什么时候做、结果怎么用”。这正是结构与方法能够分别替换的地方。

### 5.4 梯度优化 Case 的建议装配

```text
问题/ML 语义管线：参数编码、模型结构与评价数据绑定
算法管线：参数布局、优化器槽布局、StateRef/本地存储绑定
Adapter：读取反馈中的梯度，执行 SGD/Adam/AdamW 状态转移
Provider：在既有 Gateway 与资源授权下执行计算
```

当前 [mlblack ModelRepresentation](C:/Users/hp/Desktop/mlblack/core/representation.py:23) 及 [nsgablack 控制面桥接](C:/Users/hp/Desktop/mlblack/integrations/nsgablack_control.py:104) 已存在语义候选初始化、修复、模型解码和评价路径。

不能因为 decode 得到一个模型，就自动把那个模型叫作 Adapter 的 Unit：若 Adapter 实际只操作参数向量，模型仍属于评价侧语义对象。只有搜索方法确实直接操作模型拓扑、参数布局或结构时，相应模型结构才进入算法操作契约。

## 六、代码落点与跨仓库归属

以下目录是建议，尚未创建；实施时优先复用已有公共入口，只有确有职责需要才增加模块。

### 6.1 blackbase

若 UnitBuildRequest/UnitSchema/UnitBinding 要同时供 nsgablack 与 mlblack 使用，其最小共享协议放在 blackbase。pipeline slot 的调用、通用引用与状态信封仍由 substrate 提供。

blackbase 不定义 A*、Pareto、Adam、邻域搜索等算法字段，也不因 Unit 增加新的资源授权者。

### 6.2 nsgablack

建议可选落点：

```text
units/
  candidate.py           # 轻量结构/视图，优先复用 UnknownState
  population.py          # 对齐成员、反馈、token 的结构契约
  graph.py               # 节点、标签、父关联
  local_geometry.py      # 方向、探针、局部区域、子空间
  optimizer.py           # 参数与优化器槽的搜索侧契约

representation/unit_builders/
  ...                    # 上述结构的可组合构建器

adapters/<algorithm>/
  adapter.py             # 操作结构的算法逻辑
```

这些文件可以按实施规模合并，不要求先铺满目录。尤其 CandidateUnit 和 PopulationUnit 不应平行复制现有 CandidateBatch 的全部权威数据；可采用明确的结构视图或组合封装。

需要同步的现有 surface：Adapter 契约、pipeline kernel 适配层、状态 schema、catalog 描述、doctor 校验与脚手架模板。Catalog 应能解释“Adapter 需要什么结构、构建器提供什么结构”，不只发现一个名称。

### 6.3 mlblack

数据视图、模型编码、参数/模型语义布局、Head、模型 Artifact 等继续归 mlblack。通用搜索策略留在 nsgablack，底层张量计算继续通过 Provider。

UnitBuilder 不能直接导入某个 mlblack Trainer 的私有实现来拼对象。跨框架仍通过正式组件覆盖、payload、ResourceContext 与 Artifact/result 引用组合。

### 6.4 Case 目录

建议在现有标准脚手架中表达两类管线：

```text
cases/<case_name>/
  build_solver.py
  run_solver.py
  config.py
  problem/
  pipeline/
    main.py               # 汇总装配
    problem.py            # 可行性/表示组件
    algorithm.py          # Unit builder 与算法工具绑定
  adapter/
  plugins/
  evaluation/
  runtime/
```

文件名只是建议，沿用 Case 当前风格即可。无需新增 Case 级 representation/ 或 capabilities/；跨 Case 编排与资源授权仍在 Project 层。正式新示例应放 `examples/cases/`，已有 `_misc_examples` 迁移为薄入口时再接正式 Case。

### 6.5 装配时应检查什么

- Adapter 所需 schema/version 与 builder 输出精确一致，或由 builder 显式声明对应完整 schema 的兼容关系。
- builder/runner 提供 Adapter 所需的构建操作；特殊工厂方法也必须在装配时检查。
- 维度、目标数、方向数、参数布局与 Problem/候选投影匹配。
- 每个子 Adapter 都有自己的有效绑定；共享的是不可变组件还是可变实例可审计。
- 需要后继映射的算法声明 repair/replacement 的处理方式。
- checkpoint 能识别 builder/schema 版本，拒绝不可解释的旧结构。
- Case check 输出实际装配的 Adapter、Unit schema、builder、Provider 和资源上下文，避免只在 README 中声称启用。

## 七、附录：主干之外的 Adapter 逐项处置

这部分单列示例与模板，避免“只看了 adapters/”漏掉真实自定义逻辑。它们的目录存在不等于被当前 Case 实际装配；正式接入应另查 build_solver/config 的有效绑定。

### A1. WarmStartVNSAdapter

源码：[GMM Case build_solver.py](C:/Users/hp/Desktop/nsgablack/examples/cases/gmm_em_vs_de/cases/gmm_em_vs_de/build_solver.py:19)。

- 当前只在 setup 时读取 control.best_x，设置 VNS 当前点，current_score 置空。
- 复用 VNS 的候选/邻域结构。建议用“前一阶段导出种子 → VNS builder 构建初始 Unit”的正式 transfer 规则替代业务子类。
- 必须注意 StrategyChain 会提前 setup 子 Adapter：setup 时的 best_x 不保证就是 DE 结束后的 best。迁移时把 warm start 绑定到实际阶段进入时，而不是仅把现有 setup 代码换个文件。
- 如果保留该类，类定义应落 Case 的 adapter/，构建逻辑落 pipeline/；build_solver 只保留装配。

### A2. ProductionRandomSearchAdapter

源码：[search_adapters.py](C:/Users/hp/Desktop/nsgablack/examples/cases/production_scheduling/cases/production_scheduling/adapter/search_adapters.py:88)。

- 当前通过 init + repair 批量产生排程候选，update 不做策略更新。
- 采用共享 CandidateUnit，必要时由排程语义视图说明 machines/days 布局；构建器接收问题管线产生的候选并保留布局信息。
- Adapter 只保留批量随机探索请求；不把机器约束或库存计算搬进通用候选 builder。
- 验收重点是扁平候选与排程矩阵投影一致，且每条候选保留独立身份。

### A3. ProductionLocalSearchAdapter

源码：[search_adapters.py](C:/Users/hp/Desktop/nsgablack/examples/cases/production_scheduling/cases/production_scheduling/adapter/search_adapters.py:115)。

- 当前读取 best_x，再 mutate + repair。
- 共享排程候选结构，算法管线声明可用的排程邻域工具；问题管线负责约束。
- Adapter 保留围绕 best 的搜索选择；构建器负责扰动结果的排程布局及候选投影。
- 同步核对 best 的正式读取来源，优先使用既有权威快照/候选接口，避免复制出第二个 best 状态所有者。

### A4. ProductionGreedyBaselineAdapter

源码：[search_adapters.py](C:/Users/hp/Desktop/nsgablack/examples/cases/production_scheduling/cases/production_scheduling/adapter/search_adapters.py:146)，同文件 `_build_greedy_schedule()` 提供主要逻辑。

- 当前 helper 同时读取 BOM、供应、机器权重和约束，逐日决定机器顺序与产量。这已经包含贪心求解策略，不能把整个 helper 简单改名 UnitBuilder。
- 建议算法管线构建 `ScheduleConstructionUnit`：机器/日期布局、BOM/供应只读引用、可用动作结构与初始库存工作区。
- Adapter 保留机器排序、选机、产量选择和库存推进；问题管线负责可行性检查/兜底。领域操作可注入，但调用顺序仍由贪心策略决定。
- 验收重点是换排程数据结构时贪心流程可复用，以及约束处理没有把业务偏好藏入 repair。

### A5. ProductionACOBaselineAdapter

源码：[search_adapters.py](C:/Users/hp/Desktop/nsgablack/examples/cases/production_scheduling/cases/production_scheduling/adapter/search_adapters.py:169)。

- 当前 `_ensure_pheromone()` 分配 machines×days 信息素，提案借用上述 greedy helper；update 对最好候选执行蒸发和沉积。
- 建议 `PheromoneScheduleUnit`：排程结构 + 信息素矩阵 + 动作/机器日期索引；算法管线构建布局及初始信息素。
- Adapter 保留 alpha/beta 使用、候选构造中的选择策略、蒸发和沉积公式；不要把更新矩阵视为 builder 职责。
- 当前是轻量 ACO-style baseline，不能仅改结构就称为已实现通用 ACO。后续应补信息素、RNG 和候选身份的恢复验证。

### A6. JointBeamAdapter

源码：[symbolic_joint_bundle_beam_demo.py](C:/Users/hp/Desktop/nsgablack/examples/_misc_examples/symbolic_joint_bundle_beam_demo.py:369)。

- 当前维护 `_beam_masks`，直接调用 Problem 的 residual、候选排名、OMP bundle、mask encode/decode；bootstrap 和 propose 都包含领域结构与搜索逻辑。
- 建议 `SymbolicBeamUnit`：mask/特征池索引、候选编码、父 bundle 关联、残差所需数据引用。算法管线构建特征池布局、mask/编码结构及可调用领域工具。
- Adapter 保留 beam 宽度、扩展顺序、anchor/bundle 选择、去重与按反馈截断。OMP 与残差工具可以独立，但不能把 beam 选择一起塞入 builder。
- 从 `_bootstrap()` 分离“建立空 mask/结构”和“选择初始 bundle”；后者仍是策略。符号学习语义后端按 mlblack/正式 bridge 边界接入。
- 若实施，先迁入正式 Case；不能继续把完整新装配扩大在 `_misc_examples` 单文件内。

### A7. RandomSearchAdapter（GPU/Ray/MySQL 示例）

源码：[gpu_ray_mysql_stack_demo.py](C:/Users/hp/Desktop/nsgablack/examples/_misc_examples/gpu_ray_mysql_stack_demo.py:60)。

- 当前按 var_bounds 均匀采样，持有 RNG。
- 复用 CandidateUnit；算法管线构建维度/边界布局并装配采样工具，Adapter 决定批量独立采样。
- GPU、Ray、MySQL 仍属 evaluation/runtime/storage 能力，不属于 Unit 的结构字段；不因这个示例名字增加专用 GPU Unit。

### A8. RandomSearchAdapter（嵌套三层示例）

源码：[nested_three_layer_demo.py](C:/Users/hp/Desktop/nsgablack/examples/_misc_examples/nested_three_layer_demo.py:112)。

- 当前在固定区间生成一维候选。
- 同样使用轻量候选构建器，把区间与编码放入可声明装配，Adapter 保留采样。
- 内层 Solver/Case 调用属于评价与编排，不装进候选 Unit；正式迁移仍经 Project/Case surface。

### A9. FixedAdapter

源码：[ngspice_inner_demo.py](C:/Users/hp/Desktop/nsgablack/examples/_misc_examples/ngspice_inner_demo.py:31)。

- 当前只提出常量 `[2.0]`。
- 可由正式 FixedCandidateAdapter + 固定候选 initializer/builder 替代；Ngspice backend 留在评价侧。
- 没有必要为这个示例新建 CircuitSolverUnit，除非后续 Adapter 确实操作电路结构。

### A10. FixedPathAdapter

源码：[monte_carlo_dp_robust_demo.py](C:/Users/hp/Desktop/nsgablack/examples/_misc_examples/monte_carlo_dp_robust_demo.py:87)。

- 当前仅返回外部传入 path；同文件 dp_path 的求解不发生在该 Adapter 中。
- 固定路径编码经 builder 构成 CandidateUnit，可用 FixedCandidateAdapter 统一。
- 若未来要把 DP 纳入 Adapter，需要另外定义 DP 表/前驱结构与递推策略；不能因为同文件有 DP 就把现有 FixedPathAdapter 描述成动态规划算法。

### A11. RandomProbeAdapter

源码：[composable_solver_fusion_demo.py](C:/Users/hp/Desktop/nsgablack/examples/_misc_examples/composable_solver_fusion_demo.py:46)。

- 当前重复调用 init_candidate。
- 采用共享候选构建器；Adapter 保留 samples 次探索请求，Composite 记录来源即可。
- 不引入单独 ProbeUnit：此处 probe 是随机候选，不能与有限差分成对探针混淆。

### A12. LocalStepAdapter

源码：[composable_solver_fusion_demo.py](C:/Users/hp/Desktop/nsgablack/examples/_misc_examples/composable_solver_fusion_demo.py:58)。

- 当前有 best_x 才执行 mutate，否则返回空。
- 复用 CandidateUnit 与邻域工具；Adapter 保留“无 best 时空提案”的当前行为。
- 构建器不能自行初始化来填补空提案，否则会改变组合器的策略分工与空步骤语义。

### A13. GreedyAdapter

源码：[blank_vs_composable_demo.py](C:/Users/hp/Desktop/nsgablack/examples/_misc_examples/blank_vs_composable_demo.py:124)。

- 当前根据有无 best 选择 init 或 mutate，依赖正式控制面的 incumbent 更新。
- 复用轻量候选结构；不要给 Unit 增加另一份权威 best，也不要让 builder 执行优劣比较。
- 若要发展为具有私有接受规则的轨迹算法，再显式引入当前轨迹结构与 Adapter 更新逻辑。

### A14. Explorer

源码：[role_adapters_demo.py](C:/Users/hp/Desktop/nsgablack/examples/_misc_examples/role_adapters_demo.py:36)。

- 当前重复 init 后 mutate，产生 12 个候选。
- 采用角色下独立的 CandidateUnit binding；构建候选保留角色来源，探索流程仍由 Explorer 执行。
- 角色 wrapper 限额裁剪必须继续通知子提案映射。

### A15. Exploiter

源码：[role_adapters_demo.py](C:/Users/hp/Desktop/nsgablack/examples/_misc_examples/role_adapters_demo.py:47)。

- 当前有 best 时局部扰动，无 best 时初始化，生成 8 个候选。
- 与 Explorer 共享候选 schema，允许绑定不同邻域工具；不共享可变候选容器。
- “有 best 才利用”的决策保留在 Adapter。

### A16. _L3Adapter

源码：[inner_three_layer_multi_strategy_ui_demo.py](C:/Users/hp/Desktop/nsgablack/examples/_misc_examples/inner_three_layer_multi_strategy_ui_demo.py:56)。

- 当前提出 target 与固定压力测试值 9.0 两个候选。
- 使用固定候选批构建器；不能直接换成要求单候选的 FixedCandidateAdapter 而丢掉第二个测试候选。
- 内层评价关联仍由既有层间结果协议负责，Unit 只表示这两个实际操作/送评状态。

### A17. _L2Explorer

源码：[同一示例](C:/Users/hp/Desktop/nsgablack/examples/_misc_examples/inner_three_layer_multi_strategy_ui_demo.py:105)。

- 当前固定返回 `[2.0]`，没有真实探索更新。
- 可使用固定候选 builder 和正式 FixedCandidateAdapter，仍保留其在 router 中的独立实例身份与角色。
- 不应仅依据 Explorer 名字设计复杂探索 Unit。

### A18. _L2Exploiter

源码：[同一示例](C:/Users/hp/Desktop/nsgablack/examples/_misc_examples/inner_three_layer_multi_strategy_ui_demo.py:123)。

- 当前固定返回 `[-2.0]`。
- 方案与 _L2Explorer 相同，固定候选数据不同；角色语义由组合配置表示。
- 两者数值修复后的候选仍通过各自来源关联，不能按值推断所属角色。

### A19. _L1Adapter

源码：[同一示例](C:/Users/hp/Desktop/nsgablack/examples/_misc_examples/inner_three_layer_multi_strategy_ui_demo.py:181)。

- 当前固定返回 `[0.0]`。
- 可复用 FixedCandidateAdapter 与恒等构建器；层级嵌套留在标准 Case 的评价/编排，不在 Unit 中持有 inner solver 实例。

### A20. ExampleAdapter 与 AdapterTemplate：70 份模板文件

实际内容经文件哈希归为 5 组，再读取各组代表。这里合并相同实现，不逐份重复同一改造说明。

1. **my_project ExampleAdapter：1 份。**[源码](C:/Users/hp/Desktop/nsgablack/my_project/adapter/example_adapter.py:13)。alpha 决定提案数量，随机生成向量；采用 CandidateUnit builder，示范语义保留和正式 feedback 类型。
2. **my_project AdapterTemplate：1 份。**[源码](C:/Users/hp/Desktop/nsgablack/my_project/adapter/template_adapter.py:13)。随机提案并存 `_last_population`；模板应明确它是最近评价批次还是权威种群，不能仅因变量名叫 population 就宣称 L2。
3. **Case ExampleAdapter 常规版：32 份。**[代表源码](C:/Users/hp/Desktop/nsgablack/examples/cases/async_event/cases/async_event/adapter/example_adapter.py:13)。私有 RNG 随机提案；接入轻量构建绑定并明确 RNG 恢复能力，不能把“update 无操作”误写成完全无状态。
4. **Case ExampleAdapter 显式 context 契约版：2 份。**[代表源码](C:/Users/hp/Desktop/nsgablack/examples/cases/classification_threshold_calibration/cases/classification_threshold_calibration/adapter/example_adapter.py:13)。位于 classification_threshold_calibration、residual_boosting，搜索行为与常规版相同，额外声明 context 契约；沿用同一构建方案。
5. **Case AdapterTemplate：34 份。**[代表源码](C:/Users/hp/Desktop/nsgablack/examples/cases/async_event/cases/async_event/adapter/template_adapter.py:13)。统一补“结构需求—builder 注入—propose 投影—update 关联”的最小中文示例，不在模板中硬编码特定 Unit 类型。

上述 34 个 Case 各有 example_adapter.py 和 template_adapter.py，路径形式为 `examples/cases/<name>/cases/<name>/adapter/`：

```text
anomaly_detection                 arima_order_search
async_event                       automl
bias_gallery                      causal_discovery
changepoint_detection              classification_threshold_calibration
dynamic_repair                    dynamic_strategy
gmm_em_vs_de                       graph_coloring
l0_distributed_worker             mas_search
multi_strategy                    nsga2_basic
parallel_repair                   pooled_backend_handoff
ransac                            residual_boosting
risk_bias                         robust_dfo
shap                              single_trajectory
structure_prior                   surrogate_ea
surrogate_lab                     tr_subspace_frontier
trust_region_dfo                  trust_region_mo
trust_region_nonsmooth            trust_region_subspace
tsp_vrp                           wrapper_fs
```

实施时应优先修改正式模板来源和真正被装配的 Adapter；同步复制文件前先确认用途，避免把目录中未使用的模板当作该 Case 的算法实现。生产排程与 GMM 等有实际自定义类的部分，按 A1–A5 独立处理。

## 八、建议实施顺序

### 阶段 1：公共契约与一条完整链路

完成最小 UnitSchema/UnitBinding/build 请求、候选投影与提案身份协议。选 **A* + VNS** 做两个差异明显的试点：一个复杂节点结构，一个轻量候选/邻域结构。

同时给 Composite 或 RoleRouter 接最小子绑定转发，证明两种结构可以放进同一组合器。不要等单算法全迁完后才发现全局单 pipeline 无法支持异构子算法。

完成标准是：从 Case 装配、构建、propose、repair、评价、update 到回滚/恢复形成一条闭合路径；没有新增旁路评价入口。

### 阶段 2：候选与群体复用

迁移 FixedCandidate、Gaussian、SA、SingleTrajectory、PatternSearch，验证轻量结构无需层层包装。

再迁移 NSGA2/NSGA3/SPEA2/DE/MOEA/D：先共享种群对齐结构，再提取参考方向、分解邻域与 trial 映射。以实际权威 CandidateBatch 和 candidate token 为约束，不另造平行 population 真相。

### 阶段 3：专用几何和计算状态

迁移 MOA*、有限差分、信赖域家族、GradientOptimizer、MAS。重点验证多标签、探针配对、repair 后几何、Provider 引用与模型恢复。

这些组件不能仅凭“结果还能下降”判定成功；需要结构语义与恢复语义的针对性证据。

### 阶段 4：完整组合与正式示例

完成 Role/StrategyChain/StrategyRouter/Async/EliteRetention 的完整绑定、跨阶段转换、候选替换和分区状态契约，再处理两个兼容类。

以生产排程 ACO、符号 Beam、DE→VNS 为结构定制示例，落在正式 Case。清理旧 UnitSpec 命名歧义，同步模板、Catalog、Doctor 与中文指南。

以上保留迁移前的依赖顺序；实际完成情况见第十一节，当前接口见中文使用说明。

## 九、验收设计：分别证明结构可用和方法未被偷换

### 9.1 构建与替换

- 固定 Adapter，更换两个符合契约的 builder，能够完成正式运行链路；例如同一 VNS 使用两种邻域、同一子空间搜索使用两种基构建方式。
- 固定候选/种群 schema，替换不同 Adapter，验证共享部分确实可复用。
- 不兼容 schema、目标维度、投影或 Provider 能力，在装配或首次构建时给出明确错误。
- builder 不调用 Problem.evaluate、不推进搜索步、不直接发布权威 Snapshot。

### 9.2 身份与可行性

- 相同数值、不同语义的候选；相同状态、不同父路径/标签；同一 DE target 的多个 trial，都能正确区分。
- 预算裁剪、重排、取消、空提案经过 disposition 后，pending 记录与 feedback 精确对齐。
- A* 的 repair 后边代价、有限差分实际位移、EliteRetention 对结构性提案的替换有明确兼容规则。
- 问题管线输出不可行时，仍通过正式反馈/拒绝路径处理，不以 Unit 校验替代约束评价。

### 9.3 恢复、事务和权威状态

- 失败步骤回滚 Unit、Adapter 控制状态、RNG 和子组件状态，不产生幽灵 generation。
- 只把已提交步骤的新结构发布为权威 Snapshot；失败评价事件保持独立证据。
- partitioned 组合器恢复每个子结构及其 builder 身份，不用一次拼接矩阵掩盖结构差异。
- Provider 状态恢复与清理延续已有事务协议，失败引用可重试。
- A*/MOA* 若仍为 L0，文档如实标注；要提升恢复等级，必须验证完整 frontier 等结构，而非只保存最好结果。

### 9.4 现有测试的承接位置

以下是本轮迁移承接的既有测试文件；实际命令与结果见使用说明中的最终验证记录：

- 公共状态与事务：[test_adapter_step_transactions.py](C:/Users/hp/Desktop/nsgablack/tests/test_adapter_step_transactions.py)、[test_adapter_state_recovery_contract.py](C:/Users/hp/Desktop/nsgablack/tests/test_adapter_state_recovery_contract.py)、[test_candidate_population_semantics.py](C:/Users/hp/Desktop/nsgablack/tests/test_candidate_population_semantics.py)。
- 图搜索：[test_astar_moa_contracts.py](C:/Users/hp/Desktop/nsgablack/tests/test_astar_moa_contracts.py)。
- 轨迹与局部搜索：[test_vns_adapter.py](C:/Users/hp/Desktop/nsgablack/tests/test_vns_adapter.py)、[test_sa_adapter.py](C:/Users/hp/Desktop/nsgablack/tests/test_sa_adapter.py)、[test_single_trajectory_adaptive_adapter.py](C:/Users/hp/Desktop/nsgablack/tests/test_single_trajectory_adaptive_adapter.py)、[test_search_method_adapters.py](C:/Users/hp/Desktop/nsgablack/tests/test_search_method_adapters.py)。
- 专用结构：[test_moead_adapter.py](C:/Users/hp/Desktop/nsgablack/tests/test_moead_adapter.py)、[test_trust_region_adapters.py](C:/Users/hp/Desktop/nsgablack/tests/test_trust_region_adapters.py)。
- 包装与组合：[test_elite_retention_adapter.py](C:/Users/hp/Desktop/nsgablack/tests/test_elite_retention_adapter.py)、[test_role_adapters.py](C:/Users/hp/Desktop/nsgablack/tests/test_role_adapters.py)、[test_multi_strategy_controller_adapter.py](C:/Users/hp/Desktop/nsgablack/tests/test_multi_strategy_controller_adapter.py)、[test_async_event_driven_adapter.py](C:/Users/hp/Desktop/nsgablack/tests/test_async_event_driven_adapter.py)。
- 装配：[test_adapter_config_construction.py](C:/Users/hp/Desktop/nsgablack/tests/test_adapter_config_construction.py)、[test_formal_case_adapter_contract.py](C:/Users/hp/Desktop/nsgablack/tests/test_formal_case_adapter_contract.py)。

涉及公共评价链改动时，需按 AGENTS 要求验证单点评价、批量评价、Plugin 短路评价和 Snapshot 读写。Catalog 改动需要 default/framework-core 双口径验证，正式组件/模板变动需对应 Doctor 校验。本轮对应检查及执行结果记录在中文使用说明末尾。

### 9.5 如何进行消融

这次拆分支持更清楚的实验，但结构与方法可能交互，不能只用一个结果把责任完全归给其中一方：

1. 固定 Adapter、评价预算、问题管线与配对种子，比较不同 Unit 构建方式。
2. 固定结构 schema 与构建器，比较兼容 Adapter 的搜索方法。
3. 对少量关键组合做“结构 × 方法”的交叉实验，观察交互，而不是只比较默认整体组合。
4. 分开记录可行率、结构构建耗时、评价开销、搜索效果和失败类型。结构更好但构建更贵，也应体现在结论中。

只有目标、约束、预算和评价条件可比时，才能将差异归因于这些替换。当前已实现结构替换接口与功能回归；尚未执行上述性能或效果消融实验。

## 十、最终设计立场

当前框架已经具备算法、表示、评价、能力与运行状态的拆分基础。Unit 应把现有 Adapter 隐含依赖的**操作结构及其构建方式**显式化，而不是重命名现有全部对象。

最小而完整的改造目标是：**算法管线能独立构建结构，Adapter 能明确声明并操作该结构；结构投影成候选后，现有评价、身份、事务和恢复协议仍然成立。**

对复杂结构提取专用 Unit，对简单算法复用候选/种群结构，对组合器传递子绑定；这样才能让“结构定制”和“方法定制”真正分别成立。


## 十一、全量实施对照（2026-10-08）

### 主干 31 类

- AlgorithmAdapter：schema、binding、附加结构、组合审计及兼容性校验。
- AStarAdapter / MOAStarAdapter：SearchNodeUnit / ParetoLabelUnit，父身份、repair 策略和完整前沿恢复。
- VNSAdapter：CandidateUnit + 独立 NeighborhoodUnit；构建、接受关联、恢复均闭合。
- SimulatedAnnealingAdapter / SingleTrajectoryAdaptiveAdapter / GaussianSearchAdapter：TrajectoryUnit。
- FixedCandidateAdapter：候选 Unit 构建与 codec。
- PatternSearchAdapter / GradientDescentAdapter：PollUnit，后者包含探针对与实际位移检查。
- GradientOptimizerAdapter：ParameterUnit、可替换槽位构建，保留 Provider 显式资源事务。
- DifferentialEvolutionAdapter：DifferentialPopulationUnit，target 与基线分数行关联。
- NSGA2Adapter / SPEA2Adapter：PopulationUnit；NSGA3Adapter：ReferencePopulationUnit。
- MOEADAdapter：DecompositionUnit，权重/邻接/ideal/子问题提案记录。
- TrustRegionBaseAdapter / TrustRegionDFOAdapter / TrustRegionMODFOAdapter /
  TrustRegionNonSmoothAdapter / TrustRegionSubspaceAdapter：RegionUnit；基构建移入管线。
- MASAdapter：ModelSearchUnit 与模型构建工厂；拟合和候选选择保留在 Adapter。
- EliteRetentionAdapter：ArchiveUnit 与结构性提案替换护栏。
- CompositeAdapter / RoleAdapter / RoleRouterAdapter / StrategyChainAdapter /
  StrategyRouterAdapter / AsyncEventDrivenAdapter：逐子实例委托 Unit binding，不发明通用搜索结构。
- MultiStrategyControllerAdapter / MultiRoleControllerAdapter：继承正式 router 的委托契约。

新增 UnitBackedAdapter / UnitField 与 CandidateProposerAdapter 是公共迁移/扩展基础，
不计为新增搜索算法。StrategyInstanceSpec 保留 UnitSpec 兼容别名。

### 非模板示例与模板

- A1 WarmStartVNS：提案时构建阶段种子，实现从 assembly 移入 adapter 模块。
- A2/A3 生产排程随机/局部：公共候选构建器。
- A4/A5 生产排程 greedy/ACO：ScheduleUnitBuilder 构建领域布局和信息素，算法循环保持原位。
- A6 JointBeam：迁入 algorithm_units/symbolic_beam 完整 Case，BeamUnitBuilder 构建掩码布局。
- A7—A19：13 个轻量候选策略迁入 algorithm_units/candidate_search/adapter，旧 demo 保留兼容导入。
- A20：70 份模板副本同步公共候选 Unit 入口；正式生成模板增加 unit_example.py。

### 实现边界

本轮没有把 SPEA2 扩写为另一个 archive 算法，没有向 DFO 添加不存在的二次模型，
没有将固定路径示例宣称为 DP Adapter，也没有把模型语义或资源授权搬进 Unit。
公共构建器按实际结构拆分，搜索策略继续由 Adapter 操作；互不兼容的结构依赖会明确失败。

装配对齐进一步区分实际结构身份和使用要求：`compatible_schemas` 声明有方向的可替换关系，
`supported_operations` 与 Adapter 的 `unit_build_operations` 对齐；MAS 另要求 `create_model()`。
ReferencePopulationBuilder 可显式服务 NSGA2、SPEA2、NSGA3，三者仍独立持有运行结构。
Doctor 的 `alignment` 输出所需契约、匹配方式和可用能力；checkpoint 继续严格核对实际 schema/codec，
不因装配兼容而隐式转换持久状态。

接口及最终验证结果统一维护在使用说明末尾，避免把重复批次测试数相加。
