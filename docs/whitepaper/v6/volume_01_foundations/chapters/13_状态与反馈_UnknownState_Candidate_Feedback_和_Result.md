# 第一卷·第十三章　状态与反馈：UnknownState、Candidate、Feedback 和 Result

第十二章把一个组件能否运行写成多类合同的合取，其中 I/O 合同留下了一个尚未解决的问题：即使输入输出都有类型、shape 和 schema，框架怎样知道一份反馈究竟属于谁？如果某个数组先被称为参数，解码后被称为模型，评估后又与目标值放在一起，更新结束后仍沿用原来的变量名，那么每一步单独看都能通过类型检查，整条因果链却可能已经把不同时间、不同身份的对象混成了一个“值”。

这种混淆在短脚本里不易暴露。变量 `x` 从生成到评估只活几行，开发者凭上下文知道它此刻是什么意思。进入框架以后，同一批对象会经过 repair、decode、并行派发、部分接纳、评价、策略更新、环境选择、快照提交和结果投影；它还可能跨线程、跨 Case、跨进程或跨存储后端。此时，“数组内容看起来一样”不再足以证明“还是同一个对象”，而“最后留下来的种群”也不等于“刚才真正接受过评价的种群”。

因此，本章不把 UnknownState、Candidate、Feedback 和 Result 当作四个并列数据类，而把它们放回一条不可逆的语义链：UnknownState 是框架可以操作的未知状态；Candidate 是该状态在某种表示规则和上下文下还原出的领域对象；Feedback 是对一个确定候选、在一次确定评价中的事实陈述；Result 则是一次运行结束后，依据选择规则和证据边界形成的交付结论。四者之间可以转换、引用和组合，却不能互相冒充。

```text
UnknownState
    -- decode / materialize --> Candidate
    -- evaluate -------------> Feedback bound to that candidate
    -- update / select ------> authoritative runtime state
    -- finalize -------------> Result + evidence references
```

本章命题可以先写成一句严格的话：**任何 Feedback 都必须能够回答“评价的是哪个状态，经由哪种表示得到哪个候选，在什么评价条件下产生”；任何 Result 都必须能够回答“从哪一个已提交的权威状态和哪些反馈事实推导而来”。** 一旦这两个问题只能靠数组位置或开发者记忆回答，状态闭包就没有真正成立。

---

## 13.1 一个 ndarray 为什么装不下完整的运行语义

数值数组当然重要。搜索算法需要矩阵运算，梯度方法需要张量，批量 Provider 也希望连续内存和统一 shape。问题不在于使用 ndarray，而在于让 ndarray 同时承担数值载体、领域身份、评价归属和最终结果四种责任。

考虑一个生产调度任务。数组 `[2, 0, 1]` 可以表示三项作业的顺序，也可以表示三台机器的指派，还可以只是某种连续随机键编码。只有 Representation 知道它采用哪种解释、是否需要稳定排序、如何处理并列值，以及 metadata 中是否记录工艺路线版本。若 Problem 直接接收裸数组并自行猜测，它事实上接管了表示权；若 Adapter 根据业务字段读取数组位置，它又同时接管了领域语义。表面上省去了对象转换，实际是角色边界已经消失。

机器学习中的情况更隐蔽。两个状态拥有完全相同的浮点 values，但 metadata 分别指定 `activation="relu"` 与 `activation="tanh"`；或者 values 都是一组系数，metadata 却分别指向不同的 feature schema、符号表达式结构或条件分支。数值比较得到相等，decode 后的模型却不等价。此时若框架只用 `np.array_equal` 判断更新后的状态是否仍对应旧候选，它可能把旧模型的验证损失绑定到新模型上。

反方向的错误也存在：两个 values 不同，却可能 decode 成同一个领域候选。例如离散编码在 repair 后落到同一合法方案，神经网络参数存在对称置换，符号表达式经过规范化后得到同一棵表达式树。字节不同不必然意味着语义不同。因此，“同一性”既不能一律退化为对象地址，也不能一律退化为数组相等；它必须由最了解 decode 语义的 Representation 提供默认判断，必要时再由具体领域收紧。

这正是四阶段对象需要分开的原因。UnknownState 回答“策略正在操纵什么”；Candidate 回答“领域实际将评价什么”；Feedback 回答“评价观察到了什么”；Result 回答“运行最终承诺交付什么”。它们可能共享底层数据，却具有不同所有者、不同合法操作和不同时间语义。

把这条区别写进框架以后，许多原先模糊的问题会变得可判定。repair 改变的是待评价状态，还是仅修正领域候选？缓存键应依据原始 proposal、repair 后状态还是 decode 后对象？评价异常发生时，预算已经为哪个 identity 计费？Adapter update 后产生的新状态能否继承旧 Feedback？最终输出应包含已评价最优候选，还是更新后尚未评价的最新状态？这些问题不能由 ndarray 的 dtype 和 shape 回答，只能由明确的阶段对象与转换关系回答。

---

## 13.2 UnknownState：它不是“未知类型”，而是尚待解释的决策状态

UnknownState 这个名字容易产生误解。它不是说框架完全不知道对象类型，也不是 `Any` 的另一种写法；它表示框架知道这里有一份可被策略生成、扰动、保存和恢复的状态，却不应越过 Representation 去断言它在领域中的含义。这个“未知”是对共享运行层而言的语义克制。

当前共享类型把 UnknownState 表达为 `values + metadata`。values 提供适合数值计算的主体，metadata 携带影响解释但不适合强塞进同一个浮点向量的结构信息。二者共同构成状态，而不是“values 是真状态、metadata 只是日志”。如果一个字段会改变 decode 结果、repair 规则、坐标布局或后续评价，它就属于语义状态的一部分。

```python
state = UnknownState(
    values=[0.12, -0.44, 0.87],
    metadata={
        "model_family": "piecewise_linear",
        "active_branch": "high_load",
        "feature_schema": "traffic.features.v3",
    },
)
```

这里的三个浮点数只有在 model family、active branch 和 feature schema 都确定时才能被正确解释。删掉 metadata 后，数组仍可被 NumPy 读取，语义却已经不可恢复。一个安全序列化器若只保住 values，不能声称完成了 UnknownState 的 round trip；一个 checkpoint 若恢复了参数，却没有恢复参数布局，也不能声称恢复了训练状态。

metadata 并不意味着可以无限堆放任意对象。它首先应该可规范化、可版本化，并尽量只包含解释 state 所需的轻量信息。大型模型、数据集、历史和缓存仍应通过引用进入 Snapshot 或 Artifact；打开的文件句柄、线程锁、GPU session 和数据库连接更不属于状态 payload。否则 UnknownState 会从语义信封膨胀为新的万能容器，重新制造第十二章已经否定的隐式依赖。

共享层当前为 UnknownState 提供了版本化 protocol payload：版本、values 与 metadata 可以交给安全 codec；Redis SnapshotStore 也对这一共享协议类型设有正式编解码分支。这个实现事实 **S** 说明 UnknownState 已经不必像普通未知 Python 对象那样退化成 `repr` 字符串。但它不意味着任意自定义候选类型都自动安全。没有正式 codec 的对象在 safe serializer 中仍可能只能保留类型名与文本表示；文本能够展示，不能用于等价恢复。

UnknownState 还需要区分三种常被混称为“版本”的东西。protocol version 说明 payload 字段怎样读取；representation version 说明 values 和 metadata 怎样 decode；state revision 说明这份状态位于一次运行的哪个演化位置。当前 protocol payload 已有显式版本，而后两种关系还必须由更上层合同、指纹、快照 metadata 与 lineage 共同表达。把 schema version 写成 1，并不会自动证明它属于哪个 Representation，也不会自动证明它比另一份状态更新。第十四章会专门处理这些身份与时间问题，本章先确立：凡是会影响状态解释的信息，都不能在 UnknownState 边界上被丢掉。

---

## 13.3 Candidate：被评价的是领域对象，不是它的运输外壳

UnknownState 之所以存在，是因为策略最方便操作的表示与领域真正能够评价的对象往往不同。Candidate 就出现在这次转换之后。它可能是一套生产计划、一个模型实例、一棵符号表达式、一组超参数配置、一张图结构或一个仿真输入。Candidate 不是一定要在共享包中拥有名为 `Candidate` 的统一 dataclass；更重要的是，框架在语义上承认“状态”和“由状态解释出的领域对象”是两个阶段。

这项区别让 Representation 的责任变得清楚。decode 不是无关紧要的格式转换，而是从策略空间进入领域事实空间的边界。它要确定坐标布局、离散选择、条件分支、结构组装和必要的类型恢复；encode 则尝试把领域对象投回可操作状态，但不必在所有领域都存在完美逆变换；repair 负责让状态或候选满足表示层可维护的合法性，不负责替 Problem 决定业务目标，也不应替 Adapter 搜索更优方案。

同一 UnknownState 在不同 Representation 下可以生成完全不同的 Candidate；即使 Representation 相同，若 decode 依赖的 schema、数据视图或 component override 不同，Candidate 也可能变化。因此一个可复现的候选身份不能只记录 values，还要能够指向 Representation 标识、表示版本和所有 decode-relevant context。这里的 context 不是整个运行字典，而是经过合同声明、真正参与解释的最小投影。

例如，外层搜索为一个内层训练 Case 生成状态 `[2, 128, 0.1]`。它可能被解释为“两层网络、隐藏宽度 128、dropout 0.1”，也可能因为第一维使用枚举表而表示“XGBoost、128 棵树、学习率 0.1”。如果外层直接把数组交给内层 Trainer 内部字段，双方共享了一段无法审计的私有编码。正确边界是：外层把候选状态及正式 component overrides 交给内层标准入口，内层自己的 Representation 负责 materialize 领域候选；跨框架 Bridge 只负责运输和结果投影，不替两边核心解释对方的私有结构。

Candidate 还解释了为什么评价 hook 应围绕修复与解码后的真实对象建立一致语义。如果 `on_evaluate_start` 观察的是原始 proposal，而 Problem 评价的是 repair 后状态，日志中声称的 candidate 与真实花费预算的 candidate 就不一致。框架可以同时保留 proposed state、repaired state 和 materialized candidate，但必须给它们不同名称和关联身份，不能让一个 `candidate` 变量在不同 hook 中悄悄改变含义。

当前 mlblack 的评价路径先 repair UnknownState，再 decode 成 model，最后把 model、repaired state 与 context 交给 LearningProblem；这条源码路径 **S** 已经体现了阶段分离。与此同时，公共 hook 当前接收到的对象和记录到何种身份，仍需由具体插件合同和运行证据确认，不能仅凭方法顺序推断所有审计链都已闭合。更一般地说，Candidate 是领域评价的对象；UnknownState 是 Candidate 的可操作表示；二者的映射属于 Representation，而不属于共享底座、Provider 或 Adapter。

---

## 13.4 Feedback：它是一条带主语和条件的评价事实

很多实现把 Feedback 简化为一个 objective 数组，仿佛评价只是在候选后面追加几列数字。这种表示对最小单目标优化足够，却无法覆盖机器学习的梯度与残差、多目标优化的约束、外部仿真的诊断信号，也无法说明数字对应哪个候选、哪份数据和哪次运行。

更准确的理解是：Feedback 是一句有主语、有条件、有逻辑时间的陈述。它表达“候选 C 在评价规范 E、数据或场景 D、资源与随机条件 R 下，产生了这些目标、约束、指标、梯度、残差和信号”。objectives 只是其中最常进入策略更新的一部分，不是整条事实。

共享 Feedback 当前包含 objectives、constraints、gradients、loss、metrics、residuals、signals 与 info。这个结构提供了一条跨语义层的轻量运输表面 **S**，但各字段仍有明确边界。objectives 是策略要优化的有方向量；constraints 表达约束函数或违反条件，不应与日志指标混在一起；metrics 是用于解释、报告或二次决策的命名量；gradients 必须说明相对于哪一个 state 坐标系；residuals 保留更细的观测误差结构；signals 可承载控制或诊断提示；info 则是有限的附加说明。把所有内容塞进 metrics 虽然灵活，却会让 Adapter 不知道哪些值可参与更新，让 Result builder 也无法判断哪些是正式结论。

目标和约束也不能只靠 shape 解释。约束数组 `[0.0, 2.1]` 究竟表示第二个约束违反 2.1，还是原始 constraint value 需要结合方向判断？nsgablack 常将多个约束进一步投影为 scalar violation，跨框架 Trainer evaluator 也会对正部求和得到外层 violation；这是一种明确的结果投影，不等于原始 constraints 消失。若只保存聚合标量，后续可以进行可行性排序，却无法解释是哪条约束失败，也难以复算另一种 penalty。

梯度的归属要求更严格。一个模型在 repair 后改变了参数布局，若梯度仍被解释为相对于 repair 前 values，就算长度相同也不能更新；一个 batch gradient 若行顺序与 candidate 顺序错位，数值有限并不代表合法。Feedback 因而必须与 exact evaluated state 对齐，必要时还要携带 representation fingerprint、evaluation id、data revision、seed 或 provider execution id。当前共享 dataclass 没有把这些全部提升为一等字段，可以暂存在规范 info/envelope 中；从长期设计看，将核心 identity 继续藏在自由字典里只是过渡方案 **D**。

Feedback 的 `ok` 也不能被误解为完整成功判据。当前实现以 objectives 非空判断最小可用性，这适合轻量共享协议；正式 Case 仍要验证目标数量、有限性、约束 cardinality、梯度 shape、required metrics 和 Provider 状态。一个 objectives 非空但来自超时 fallback 的对象，若没有明确 status，就可能被当成真实评价；一个包含 NaN 的目标数组也可能通过“非空”检查。协议对象提供结构，Problem 和评价边界提供领域合法性，二者不能互相替代。

最重要的是，Feedback 一经产生就是对已经发生的评价事实的记录。后续 Bias 可以依据显式政策形成 adjusted feedback，Adapter 可以消费它，Result 可以选择性汇总它，但任何变换都应保留原反馈与派生反馈的关系。否则“模型真实损失”“约束惩罚后的搜索分数”和“报告展示指标”会被同一个字段反复覆盖，最后没人能还原 Adapter 当时依据什么做出更新。

---

## 13.5 批量评价：数量对齐只是底线，身份对齐才是目标

单个候选的归属关系还可以由调用栈维持；进入批量评价以后，数组位置往往被当作默认 identity。候选矩阵第 i 行对应 objectives 第 i 行、violations 第 i 项，这项约定简单而高效，但它只有在整批候选从提出到返回都没有过滤、重排、重试、缓存命中或部分失败时才天然成立。

预算截断已经足以打破这种假设。Adapter 提出八个状态，控制平面只接受前五个；如果 Adapter 仍保留八项内部索引，而评价链只返回五份 Feedback，update 的每一行都可能对应错误的交叉、变异或策略账本。共享 BatchDisposition 用 proposed count、accepted indices、reason 和 reservation id 表达这次处置；当前 nsgablack 的 Solver 会在预算或表示过滤改变批量时通知 Adapter，Composite、DE 与多策略 Adapter 再按实际接纳集合修正内部状态。这是运行闭包中的必要对账，不是性能优化。

部分失败更复杂。假设四个候选并行派发，0 和 2 成功，1 超时，3 在取消到达前已经开始执行。返回两份成功 Feedback 并不能说明它们对应前两个候选；返回四行并用零填补失败又会把错误伪装成业务值。一个完整的 batch outcome 至少要表达每个输入的 identity、disposition、执行是否开始、成功反馈或结构化错误，以及真实消耗。BatchDisposition 能表达控制平面接受了谁，却不等于完整 per-item execution outcome；后者仍是需要在评价协议中进一步固化的设计方向 **D**。

即使数量没有变化，策略更新也可能重排或选择状态。mlblack 当前在 evaluate_population 后首先检查 population 与 Feedback 数量相等，然后保存 evaluated population/feedback；Adapter update 完成后再读取 Adapter 的权威 population，并通过 Representation.equivalent 或默认状态指纹尝试把反馈对齐到仍然等价的状态。找不到完整一一对应关系时，函数返回空 feedback，而不是把位置相同的旧反馈强贴到新状态上。这项源码事实 **S** 很关键：宁可承认“权威状态尚未被评价”，也不能制造一份看似完整但归属错误的快照。

不过，指纹匹配本身也不是万能答案。若一批中存在多个语义等价的重复候选，单靠 fingerprint 只能建立一种可用匹配，无法说明哪个评价任务产生了哪份带随机性的 Feedback；若评价是随机的，同一 Candidate 在不同 seed、数据切分或 Provider revision 下会产生不同反馈。因此批量合同最终还需要 candidate instance identity 与 evaluation identity：语义等价回答“能否视为同一种候选”，实例身份回答“这次事实究竟来自哪一次评价”。这两层身份将在下一章展开。

批量验证因此应按三层进行。第一层验证 shape 与 cardinality，例如 N 个候选必须形成 N 个 outcome，M 个 objectives 必须形成 N×M；第二层验证 accepted/rejected/failed 的处置关系，确保 Adapter 与预算账本同步；第三层验证 candidate identity 与 feedback identity 的一一绑定。只做第一层可以防止明显越界，不能防止等长错位。

---

## 13.6 update 之后：权威状态变化了，旧 Feedback 不会自动跟过去

评价结束不是一代运行的结束。Feedback 的目的通常是驱动 Adapter 更新，而 update 正是最容易把“已评价对象”和“当前权威对象”混为一谈的时点。

在梯度训练中，状态 θ₀ 被 decode、评价并得到梯度 g₀；Adapter 执行 `θ₁ = θ₀ - ηg₀`。此时 g₀ 是在 θ₀ 上观察到的反馈，θ₁ 只是由它推导出的新状态，尚未自动拥有 θ₁ 的 loss。在进化搜索中，当前种群与 offspring 被评价后，Adapter 可能执行环境选择，得到一个重排、裁剪甚至混合的新权威种群；只有那些与已评价项保持语义等价的成员才能沿用相应 Feedback。若 Adapter 还会局部搜索或生成新的内部状态，新的成员必须等待下一次评价。

这说明运行中至少要区分两组关系：`evaluated_state -> feedback` 是已经发生的事实，`authoritative_state` 是 update 后下一阶段应读取的当前状态。二者可以重合，也可以部分重合或完全不同。快照若只保存 authoritative population，却同时附上 update 前按位置排列的 objectives，就构造出了一份内部自相矛盾的记录；快照若只保存 evaluated population，又会把 Adapter 已完成的环境选择遗漏掉。正确记录需要同时保留两者，或明确声明当前权威状态的 feedback 尚未对齐。

LearningSolver 直接复用 nsgablack 的 population snapshot 与权威提交语义：在 Adapter update 后读取 Adapter 权威 population，验证 population、objectives 与 violations 的 N×M/N 关系，再写入代级快照；ML 层只补充 UnknownState/Feedback/模型 Artifact 的语义投影。[S] 因而不变量只有一份：**提交点必须位于策略更新之后，但已评估事实不能因权威状态变化而被伪造。**

这条规则还解释了为什么 propose_context 与 update_context 必须分开。propose 前的 evaluation count、best 和 snapshot ref 描述的是上一提交点；一批评价结束后，计数、最佳值和评价引用已经变化。若把旧 context 原样传给 update，策略阶段切换和预算控制会晚一代生效。上下文不是 Candidate 或 Feedback 的替代品，但它决定这些对象处于哪个运行时点；复用旧 context 等于用旧逻辑时间解释新反馈。

“最佳状态”也必须遵守同一原则。一个 Trainer 可以在每个已评价候选上更新 best_state 与 best_feedback，这个 best 表示截至当前评价事实观察到的最优；Adapter update 产生的未评价状态即使数值看起来更有希望，也不能直接成为带 best_feedback 的最佳结果。优化侧的 Pareto front 同样应由已验证的 objectives/constraints 支撑，而不是由尚未评价的预测状态冒充。代理模型的预测可以形成 prediction 或 signal，但必须与真实 Feedback 分层。

因此，权威状态唯一并不意味着系统里只能存在一份状态。系统可以同时保留 proposed、repaired、evaluated、updated、selected 和 committed 对象；“唯一”指每个逻辑时点和用途都有明确权威来源，且状态之间存在可追踪转换。试图通过只留一个 `self.population` 简化实现，往往只是把这些差异藏进赋值顺序。

---

## 13.7 Result：它是运行承诺的终态投影，不是最后一个内存对象

当循环停止时，框架需要把运行内部状态变成对调用者稳定的 Result。最省事的做法是返回 `self.population`、`best_model` 或最后一次 step 的字典；这会让调用者拿到某个对象，却无法知道它是否已经评价、是否是权威提交、为什么被选中，以及失败或提前停止对它有什么影响。

Result 与运行状态的根本区别在于承诺范围。运行状态服务于下一步计算，可以包含候选池、策略账本、缓存与临时指标；Result 服务于 Case 边界，必须说明运行是否成功、交付的最终状态或模型是什么、使用什么选择规则、对应哪些正式反馈，以及证据和大对象在哪里。Result 可以引用 Snapshot 和 Artifact，但不应把两者的全部内容无差别复制进自身。

优化与机器学习的 Result 也不能被一个毫无语义的 `output: Any` 抹平。当前 nsgablack 的 OptimizationResult 提供 Pareto solutions/objectives、generation/evaluation/elapsed/converged 及可选 history 和质量指标；当前共享 TrainerResult 提供 best state、best model、best objectives、best feedback、history、population snapshot 与 report。这些字段体现了不同语义层的终态投影 **S**：优化结果围绕可行解与前沿，训练结果围绕已评价状态、模型和反馈。跨 Case 的 CaseRunResult 再以更中立的 status、output、artifacts、elapsed、exit code 和 error 信封运输它们。

不过，字段存在不等于结果闭包已经成立。OptimizationResult 若只返回数组而没有 snapshot、run identity 或选择依据，调用者仍难以追溯；TrainerResult.best_model 若无法通过 best_state、Representation 和 Artifact 复现，就只是进程内便利对象；history 若包含大型可变对象，会让 Result 失去轻量稳定边界。理想 Result 至少应具备终态状态、正式反馈、运行状态、证据引用、schema/version 和选择解释。哪些字段内联、哪些通过引用交付，由大小、生命周期和跨边界需求决定。

复合运行尤其考验 Result 语义。`CaseStageRunner` 依次执行多个独立子 Case 时，最终结果来自最后阶段、指定 output stage 还是聚合器，必须由复合合同决定；不能因为父对象恰好有 `best_state` 字段就返回空值。外层 nsgablack 把内层 TrainerResult 投影为 `(objectives, violation)` 时，也只是为外层搜索提取所需反馈，不能把这对数组称为完整的内层结果。正式 Bridge 通过 `CaseRunRequest` 创建独立 Trainer、派生子 ResourceContext、要求返回完整结果，再由 projector 提取目标和约束违反 **S**；内层 Artifact、report 与审计引用仍应由 Result/Case 边界保留，而不是在投影时丢失。

运行失败时同样可以有 Result，但它不是伪造的成功结果。失败 Result 应携带 status、error phase、已提交状态引用、已消耗预算和可恢复位置；如果没有任何合法最终候选，best_state 就应明确为空，而不是返回零向量。取消、超时和部分成功也需要独立状态。Result 的责任不是保证每次都有漂亮答案，而是忠实封装这次运行最终能够承诺的事实。

---

## 13.8 从语义往返到可验证协议

把四阶段对象分开以后，序列化就不再只是“能否 dump”。真正的 round trip 要求对象经过保存与读取后仍能参与相同的 decode、equivalence、feedback alignment 和结果解释。若写入前是 UnknownState，读取后变成字符串；若 metadata 中的 tuple 变成含义不同的 list；若 dtype、shape 或 schema revision 丢失；若 Result 中的引用无法解析，那么字节读取成功也不代表语义恢复成功。

当前共享 Redis safe serializer 会为 UnknownState 写入正式 protocol marker，并在读取时调用版本化 payload 恢复；ndarray 也保存 dtype 与 shape。这是针对已注册共享协议类型的源码保障 **S**。对于未注册对象，safe 路径仍会回退为 `repr/type`，读取后得到文本。这种行为适合诊断展示，不适合作为 checkpoint 恢复。框架必须区分“可安全记录”与“可等价重建”：前者允许降级为可读描述，后者必须有正式 codec，且不能静默降级。

状态指纹提供另一层验证。mlblack 当前默认指纹把连续 values 的 dtype、shape、bytes 与规范化 metadata 一并送入 SHA-256，Representation 还可以覆盖 `fingerprint()` 与 `equivalent()` 来表达领域等价。这避免了只比较数值的明显错误 **S**。但指纹不是序列化 codec，也不是安全签名，更不是时间版本。它只能在约定的规范化规则下辅助判断语义身份；若 metadata 含有只能用 `repr` 表示的对象，跨进程稳定性仍可能不足，具体 Representation 应提供更严格的规范化规则。

最小正确协议可以用一个往返性质表示：

```text
s1 = UnknownState(values, metadata)
p  = encode_protocol(s1)
s2 = decode_protocol(p)

required:
    schema_compatible(p)
    equivalent(s1, s2)
    decode(s1) ≡ decode(s2)
```

这里的最后一个等价不是要求 Python 对象地址相同，而是要求对当前任务有意义的领域行为相同。对于模型，它可能意味着架构、参数布局与输出语义一致；对于调度方案，它可能意味着同一作业顺序与资源分配；对于符号表达式，它可能允许规范化后的代数等价。等价判据必须由 Representation 或领域合同定义，不能由 SnapshotStore 猜测。

整条状态—反馈链还需要一组可执行验证。UnknownState 合同测试应覆盖 values、metadata、dtype、shape 和协议版本的往返；Representation 测试应覆盖 decode-relevant metadata 改变时 fingerprint 是否改变，以及声明为等价的不同编码是否正确归并；评价测试应覆盖单点和 batch cardinality、部分失败、预算截断与 Feedback 字段合法性；更新测试应证明未评价的新状态不会继承旧反馈；Result 测试应证明终态引用、最佳反馈和运行 status 相互一致；Redis 或远程路径必须做真实 backend 往返，不能用内存存储结果代替。

这些验证并非都已具备运行证据。当前源码提供 UnknownState codec、默认语义指纹、Feedback 结构、BatchDisposition、更新后权威状态解析和两类 Result 表面，可标记为 **S**；它们是否覆盖所有 Adapter、Provider、复合 Trainer、远程 Worker 和历史 schema，仍需相应合同测试 **T** 与真实运行 **R** 逐项证明。per-item batch outcome、核心 identity 一等字段以及跨 Result 的完整证据引用，在形成稳定公共协议前应标记为 **D**，不能因为白皮书定义了理想关系就宣称框架已经全部实现。

至此，第十二章提出的 I/O 合同有了真正的语义对象：不是“数组进去、数组出来”，而是状态被解释为候选，候选产生有归属的反馈，策略据此改变权威状态，运行再把已提交事实投影为结果。可还有一个问题被本章有意保留：即使 values、metadata 和 schema 都一致，我们怎样区分两次独立提出的同类候选，怎样表示评价前、评价后、更新后与提交后的先后关系，又怎样防止旧 handle 在新一代仍被当作当前状态？

下一章将把身份、逻辑时间、版本与 lineage 单独展开。只有为 run、case、stage、generation、candidate 和 evaluation 建立稳定坐标，`equivalent` 才不会被误当成“就是同一次”，Feedback 才能准确找到主语，Snapshot 也才能证明自己记录的是哪个提交点。

本章确立的四阶段关系属于 **I：状态闭包的基本不变量**；当前共享类型、codec、指纹、对齐与提交路径提供 **S：源码证据**；批量逐项 outcome 和更完整的 identity envelope 属于 **D：待收口设计**。本章的出口不是新增四个名词，而是一条禁止错误继承的规则：**状态可以产生候选，候选可以产生反馈，反馈可以推动新状态，但反馈绝不能仅凭位置或数值相似被自动继承，结果也不能仅凭“最后留在内存里”获得权威性。**
