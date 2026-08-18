# Black Framework Stack 中文白皮书：框架本体版目录

## 编排说明：这份目录为什么这样排

这本白皮书的对象不是某个算法，也不是某个案例，而是一套“复杂计算任务怎样被表达、运行、组合和证明可信”的框架。

因此目录不能按仓库文件夹平铺，也不能按一个业务故事展开。它必须同时遵守两条逻辑。

第一条是**概念依赖**：先解释框架面对的复杂性，再建立基本抽象；抽象稳定以后才能定义协议；协议形成以后才有运行时；单个运行单元闭合以后才可以讨论组合；复杂组合出现以后，预算、并发、取消、恢复等工程问题才有准确语境；最后才能讨论实践和演进。

第二条是**运行因果**：声明 -> 装配 -> 授权 -> 提议 -> 表示 -> 评估 -> 更新 -> 提交 -> 控制 -> 结果 -> 恢复。白皮书介绍任何组件时，都要把它放回这条因果链，而不是孤立列 API。

全书的结构因而是：

```mermaid
flowchart LR
  A[复杂性与设计压力] --> B[框架本体与职责边界]
  B --> C[共享协议与运行底座]
  C --> D1[nsgablack 优化语义]
  C --> D2[mlblack 机器学习语义]
  D1 --> E[统一组合与嵌套]
  D2 --> E
  E --> F[正确性、资源与可靠性]
  F --> G[使用方法与模式库]
  G --> H[扩展、治理与演进]
```

案例只承担“解释和验证”作用。生产调度适合说明多目标、约束和 repair；ETF 时序预测适合说明 DataView、Trainer 和 Artifact；符号正交搜索适合说明跨框架嵌套；parallel repair 适合说明 Pipeline 分支隔离；distributed worker 适合说明 Transport、Lease 与 Fence。没有一个案例会被迫覆盖所有机制。

---

# 卷首　先建立判断框架

## 第一章　这套框架究竟是什么

本章回答定位问题：为什么它不是算法库、训练库、工作流系统或 Dashboard，却会同时包含这些系统的一部分。

拟设小节：

1. 从“求一个结果”到“运行一个可解释的计算系统”。
2. 算法正确、实现正确、运行正确三者的区别。
3. 优化、机器学习、仿真与外部系统为什么会在同一个 Project 中相遇。
4. 框架的主要对象：决策、状态、反馈、资源、能力和产物。
5. 框架明确不负责的事情：替代业务建模、替代外部后端、用 Catalog 证明质量。

这一章不进入类和目录。它建立读者后续判断一项能力是否“属于框架”的尺度。

## 第二章　复杂性从哪里来

本章不抽象地说“工程很复杂”，而是把复杂性拆成可识别来源：

1. 语义复杂性：目标、约束、模型、指标和偏好彼此不同。
2. 组合复杂性：多阶段、多算法、多模型、外层与内层相互嵌套。
3. 时间复杂性：评估前、评估后、更新后和提交后的状态并不相同。
4. 资源复杂性：线程、设备、预算、租约和外部配额有授权关系。
5. 失败复杂性：部分成功、重试、超时、取消、晚到结果和恢复。
6. 证据复杂性：日志、Context、Snapshot、Artifact 与最终 Result 必须对齐。

每种复杂性都会配一个不同案例，说明它怎样在小型演示中被隐藏、又怎样在真实运行中暴露。

## 第三章　框架的基本公理

这一章提出全书反复使用的设计不变量，而不是口号。

1. 语义归属唯一：共享底座、优化语义、ML 语义和外部后端各有边界。
2. 授权来源唯一：Project L0 是全局资源和共享预算的权威。
3. 状态来源唯一：每个时间点必须能指出权威 population/model/state。
4. Context 轻量：大对象通过 Snapshot 或 Artifact 传递。
5. Case 闭合：每个 Case 可独立装配、运行、失败、恢复和审计。
6. 组合不破坏局部契约：嵌套后内层仍是标准 Case。
7. 发生过的成本不能被抹除：预算按真实 dispatch/consumption 记账。
8. 取消是能力契约：线程取消、进程终止和远程取消不能混为一谈。
9. 声明不等于执行：配置、Catalog 和文档必须由运行路径证明。
10. 结果必须带因果证据：Result、Snapshot、Artifact 与 Audit 指向同一运行事实。

后续章节不是重新发明规则，而是逐一实现和检验这些公理。

## 第四章　三个仓库与一个外部边界

在前三章建立判断标准之后，本章才正式介绍 blackbase、nsgablack、mlblack 与 Provider/Bridge 的分工。

重点不是列目录，而是处理边界争议：

1. Project 编排为什么属于 blackbase，而不是任一语义层。
2. Pareto、约束和候选搜索为什么属于 nsgablack。
3. DataView、Codec、Head、Trainer 与 Artifact 为什么属于 mlblack。
4. Redis、COPT、ngspice、Ray、Kubernetes 和对象存储为什么必须通过外部表面接入。
5. 跨仓能力怎样先在 blackbase 定义共享合同，再由语义层适配。
6. 迁移期 forwarder 与权威实现怎样区分。

本章会用十余个“这个功能应该放哪”判断题，使职责边界成为可操作方法。

---

# 第一部　共享本体：所有运行都建立在什么之上

## 第五章　Project、Case、Scaffold：运行结构的三种尺度

本章先建立统一运行单元：Project 负责跨 Case 的顺序、并行和授权；Case 是最小独立运行闭包；Scaffold 是 Case 的标准组织和装配形式。

主要内容：

1. 为什么 Solver 与 Trainer 处在相同 Case 层级。
2. `build_solver.py` 与 `run_solver.py` 为什么必须唯一。
3. `.case kind=solver|trainer` 改变什么、不改变什么。
4. Case 独立闭合的六项条件。
5. Stage、Group、Case 的层级关系。
6. Case 何时应拆分，何时仍属于一个内部 Pipeline。
7. `mode=build` 与 `mode=cli` 的运行差异。
8. 标准目录不是美学，而是 Doctor、装配和嵌套的共同依据。

案例会分别取自纯优化 Case、纯 Trainer Case 和多 Case Project，避免用一种目录解释所有情况。

## 第六章　组件、合同与依赖声明

本章建立组件层共同语言。

1. ComponentContract 的目的：描述语义和能力，而不是替代类型系统。
2. Context `requires/provides/mutates/cache` 的含义。
3. 资源 requirement、Backend capability 与数据 I/O contract 的区别。
4. 注册、装配、运行三阶段为什么要分开。
5. 组件 identity、version、configuration 与 runtime state。
6. optional capability 怎样 fail fast 或 soft fallback。
7. 合同冲突怎样在 build-check 前暴露。

本章将用 Pipeline Operator、Plugin、Adapter 和 ML Head 四种不同组件比较“合同”在不同语义中的表现。

## 第七章　共享协议类型：UnknownState、Feedback、Snapshot 与 Result

这一章说明为什么跨 Case、跨框架、跨进程传递的不是任意 Python 对象。

1. UnknownState 的 values 与 metadata。
2. Feedback 中 objectives、constraints、gradients、residuals 与 metrics 的边界。
3. PopulationSnapshot 代表哪个时间点。
4. TrainerResult/运行 Result 如何承载最终语义。
5. 协议 payload 与领域对象的转换。
6. fingerprint、equivalent 与稳定 identity。
7. schema version 与向后兼容。
8. JSON-compatible 不等于语义可恢复。

案例包括 Redis safe serializer 下 UnknownState 退化成字符串，以及数值相同、metadata 不同的模型被错误复用 Feedback。

## 第八章　Context、Snapshot、Artifact 与 Event

本章系统建立四种状态载体，而不是零散给出“Context 轻量”的规则。

1. Context：当前运行切片和轻量引用。
2. Snapshot：运行中的大状态与一致性提交。
3. Artifact：跨运行保存的可复现产物。
4. Event：描述发生过什么的不可变证据。
5. 四者的读写频率、寿命、所有权与序列化差异。
6. Snapshot envelope、Handle、Record 与版本。
7. ArtifactRef/DataRef 如何跨 Stage 注入。
8. Event 怎样关联 run/case/stage/generation/candidate。
9. 大对象治理与违规处理。
10. 从 Event + Snapshot + Manifest 恢复因果链。

本章会使用种群、训练模型、评估历史、Pareto 前沿、数据集和 trace 等多种对象逐一归类。

## 第九章　Plugin 生命周期与统一事件模型

Plugin 是共享能力层，因此要在优化与 ML 语义之前单独解释。

1. 十个统一 hook 的时序与参数。
2. PluginManager 的优先级、执行顺序和 strict/soft 模式。
3. `on_context_build` 的链式变换。
4. evaluate hook 与评估短路接口的区别。
5. Capability 到 Plugin 的映射。
6. Plugin 状态、checkpoint 与 report。
7. side effect、幂等和 teardown。
8. 错误由 Plugin 产生、被 Plugin 观察和被 Plugin 恢复的差异。

这里会分别使用 checkpoint、trace、评估计时、外部日志和恢复插件说明同一生命周期怎样承载不同能力。

## 第十章　ResourceContext 与 L0 授权模型

本章建立资源语义，为后面的并行和分布式运行奠定基础。

1. requirement、offer、grant 与实际 resolved backend。
2. threads、workers、GPU、device token、memory、namespace 和 budget。
3. Project L0 为什么拥有授权，而 Case 只能消费。
4. `derive_child()` 的单调收窄。
5. CPU oversubscribe 与 GPU sharing policy。
6. requested、granted、resolved、fallback 的审计区别。
7. 嵌套 Case 的资源继承。
8. 资源不足时的排队、波次与失败策略。
9. ResourceContext 更新与实际 Session 同步。

案例包括本地线程、多个 Trainer 竞争设备、外层搜索调用内层训练，以及“审计显示 GPU、实际仍在 CPU”的分叉。

---

# 第二部　共享运行内核：声明怎样变成一次执行

## 第十一章　从 Project 入口到 Case 对象

沿着真实调用路径解释 `run_project.py -> project_runner -> runtime config -> stage -> lease -> load_case_builder -> build_case -> run_case`。

1. Project 配置怎样被加载和规范化。
2. Case kind 与 builder target 怎样解析。
3. import context 与 Case 模块隔离。
4. ResourceContext 和 component overrides 怎样注入。
5. build-check 与正式运行的共同点和差异。
6. Solver/Trainer 的默认执行方法怎样选择。
7. Case 输出怎样被标准化。
8. 构建失败与运行失败如何进入 Manifest。

本章是源码级运行导览，使用 blackbase 的实际入口作为证据。

## 第十二章　Stage 编排、依赖与 Artifact 传递

1. serial、parallel、external 三种 Stage policy。
2. 同一 Stage 内独立性为何是硬约束。
3. 跨 Stage Artifact registry。
4. input_artifacts 的显式注入。
5. failure_policy：fail_fast 与 continue。
6. skipped Case 的结果语义。
7. Stage DAG 与循环依赖。
8. resume 时怎样跳过已完成且指纹一致的 Case。
9. 配置指纹与源码指纹。

案例不局限于生产调度，会比较模型训练流水线、并行 benchmark 与数据准备项目。

## 第十三章　Pipeline Slot Kernel

本章把 Pipeline 视为共享编排语言，而不是 Representation 的别名。

1. PipelineSpec、PipelineSlotSpec 与 Operator registry。
2. slot 到 method 的映射。
3. serial 的值传递与上下文投影。
4. router 的选择条件与 strict 模式。
5. parallel 的分支模型。
6. merge：mean、sum、concat、first、last、list 与自定义合并。
7. Operator 签名绑定，为什么不能捕获 TypeError 猜参数。
8. Pipeline report 与 branch failure。
9. nsgablack Representation 和 mlblack DataPipeline 的适配方式。

案例分别使用多分支变异、特征分支融合和按任务类型路由 Head。

## 第十四章　预算、Reservation 与共享 Authority

预算单独成章，因为它既不是普通计数器，也不只属于评估函数。

1. 预算的类型：evaluation、cost、time、tokens 与外部配额。
2. Project Authority 与 Case 视图。
3. reserve、start、complete、fail、release 的状态机。
4. 部分失败时哪些额度可退。
5. 批量 Provider 怎样按候选计数。
6. 并发 reservation 怎样避免超卖。
7. 内层 Case 怎样共享外层预算。
8. Controller 怎样根据预算请求停止。
9. 报告中 consumed 与 successful 为什么必须分开。

核心案例是批量评估部分失败；扩展案例包括付费 API、内层训练 step 和远程仿真任务。

## 第十五章　Pool、Lease 与执行权

1. PoolScheduler 怎样把并发变成受控资源。
2. 本地线程/进程与外部 Worker 的区别。
3. ResourceLease 的获得、续租、释放和过期。
4. heartbeat 与失联检测。
5. fence token 为什么比“租约是否过期”更重要。
6. 嵌套并行如何防止线程乘法。
7. 独占 device token。
8. 资源波次与公平性。
9. Lease audit 与泄漏诊断。

案例包括多 Case 并行、嵌套评估以及旧 Worker 租约过期后仍尝试提交结果。

## 第十六章　Task Transport 与外部 Worker

1. TaskEnvelope、TaskResult 与 WorkerDescriptor。
2. publish、claim、ack、nack、retry 和 dead letter。
3. visibility timeout 与 task lease。
4. task lease 和 Project resource lease 的不同职责。
5. idempotency key 与重复投递。
6. deadline、cancel 与 late result。
7. SQLite 与 Redis transport 的适用范围。
8. namespace、凭据脱敏与审计。
9. 外部 Worker 怎样加载并运行标准 Case，而不是私有函数。
10. 恢复时怎样重新发现未完成任务。

本章将以 distributed worker 示例和故障时序为证据。

## 第十七章　Run Manifest、Check Output 与结果表面

1. Manifest 为什么不是日志副本。
2. Project/Stage/Case 状态机。
3. source/config fingerprint。
4. effective resources 与实际组件。
5. Artifact registry 与输出摘要。
6. 错误、跳过、取消和降级怎样表示。
7. check、build-check、run summary 的不同证据强度。
8. Result 与 Manifest 怎样相互引用。
9. resume-from 的安全判断。

这一章完成共享底座。接下来分别进入优化和机器学习语义层。

---

# 第三部　nsgablack：优化与搜索语义怎样闭合

## 第十八章　Optimization Problem：决策空间、目标与约束

1. 决策变量与候选空间。
2. 单目标、多目标与目标方向。
3. 硬约束、软约束与 penalty objective。
4. feasibility 与 constraint violation 的统一表示。
5. bounds、dimension 与动态问题。
6. deterministic/stochastic evaluation。
7. 无标签运筹问题与监督学习任务的区别。
8. 目标尺度、归一化和聚合风险。
9. Problem 的测试方法。

案例池包括生产调度、TSP/VRP、投资组合、图路径和外部仿真优化。

## 第十九章　Representation：候选语义的唯一入口

1. init、mutate、repair、encode、decode。
2. continuous、integer、binary、permutation、graph、matrix。
3. 混合变量与条件结构。
4. repair 的职责边界。
5. shape 与 dtype 稳定。
6. fingerprint 与候选 identity。
7. 随机性来源和批量方法。
8. RepresentationPipeline 与 Slot Kernel。
9. Context 依赖声明。
10. 并行下的不可变/复制语义。

不同表示使用不同案例，不把所有问题压进一个生产排程矩阵。

## 第二十章　Solver：控制平面与生命周期

1. SolverBase、ComposableSolver、EvolutionSolver 的继承责任。
2. setup、initialize、generation、finish、teardown。
3. generation、evaluation_count、best 与 stop state。
4. propose_context 与 update_context。
5. Plugin dispatch 与 Controller boundary。
6. RNG 和 runtime context projection。
7. 公共 evaluate API。
8. Result 构造。
9. Solver 不应承担的算法逻辑。

本章通过一代完整时序把前面共享底座与优化语义连接起来。

## 第二十一章　Adapter：搜索策略的统一合同

1. `propose()` 与 `update()`。
2. `get_state()/set_state()`。
3. `get_population()/set_population()`。
4. runtime context projection。
5. 权威 population 的判定。
6. batch size、策略状态与阶段切换。
7. stateless、trajectory、population-based Adapter。
8. Adapter 与 Representation 的协作。
9. Adapter 与 Problem 的隔离。
10. 自定义 Adapter 的完整验收。

案例会并列随机搜索、NSGA-II、MOEA/D、VNS、模拟退火、信赖域与 A*，突出共同合同与差异，而不是逐个讲算法教科书。

## 第二十二章　评估链：从候选到可信反馈

1. 单候选入口。
2. population/batch 入口。
3. Problem、Provider 和 Plugin 短路的解析顺序。
4. candidate dimension validation。
5. objectives 与 violations 的 shape/cardinality。
6. `None` 的未处理语义。
7. evaluate hooks。
8. evaluation_count 与 Budget Authority。
9. 部分失败和 error marker。
10. evaluation snapshot。
11. 并行评估的顺序和 identity 对齐。

这是运行正确性的核心章节，会给出完整反例和测试，而不是只列规则。

## 第二十三章　约束、可行性与 Repair 的三角关系

1. Problem constraint 是事实。
2. repair 是候选变换。
3. Adapter feasibility policy 是选择策略。
4. penalty 与 Bias 的边界。
5. strict feasible 与 allow infeasible update。
6. feasibility-first、epsilon constraint 与 stochastic ranking。
7. 动态约束和外部可行性检查。
8. 约束重复编码的风险。

生产调度适合这里作为主要案例，但会与图着色、组合约束和数值约束对照。

## 第二十四章　多目标、Pareto 与环境选择

1. dominance、non-dominated sorting 与 crowding。
2. Pareto front 与 archive 的区别。
3. objectives shape 对 Pareto 的影响。
4. NSGA-II/III、SPEA2、MOEA/D 的策略差异。
5. 约束支配。
6. 环境选择后的权威种群。
7. Archive Plugin 与 Adapter 状态的边界。
8. 从 Pareto 集选择业务方案。
9. 多目标报告与可视化的证据来源。

## 第二十五章　Bias：不改变硬语义的软引导

1. Bias 与目标、约束、repair 的区别。
2. algorithmic、domain、surrogate bias。
3. 初始化、排序、探索与开发信号。
4. 动态权重和阶段调度。
5. 不确定性与风险偏好。
6. Bias Context Contract。
7. 缓存与并行隔离。
8. bias audit。
9. `ignore_constraint_violation_when_bias` 的风险。

案例包括生产连续性、风险规避、代理不确定性和结构先验。

## 第二十六章　Controller 与运行治理

1. RuntimeController 的 collect/resolve。
2. budget、stopping、strategy、resources 等控制域。
3. BudgetController、PatienceController 和动态切换。
4. 信号冲突与优先级。
5. 动作怎样映射到 `request_stop()` 或策略更新。
6. Controller 状态的 checkpoint。
7. Controller 何时读取最新 Context。
8. 注册但未进入 run loop 的静默失效。
9. 控制决策审计。

## 第二十七章　多策略、嵌套 Solver 与搜索组合

1. StrategyChain、router 与 phase schedule。
2. 多 Adapter 并行提出候选。
3. role-based/multi-agent 搜索。
4. inner solver 作为评估能力。
5. NestedSolver 的预算和状态边界。
6. 多层搜索的 candidate/result identity。
7. 何时拆成多个 Case，何时保留在一个 Solver。
8. 多策略融合与 Pareto 一致性。
9. 搜索组合的测试方法。

这一章结束 nsgablack 语义层，并为跨框架嵌套留下接口。

---

# 第四部　mlblack：机器学习语义怎样闭合

## 第二十八章　DataView、Spec 与数据边界

1. 为什么 Trainer 不应直接依赖任意 DataFrame。
2. Numeric、Sequence、TimeSeries、Image、Graph、Contrastive DataView。
3. feature、target、split 与 metadata。
4. train/valid/test 与 walk-forward。
5. DataRef 与数据血缘。
6. 数据 schema、缺失值和 dtype。
7. supervised、unsupervised 与无 target 任务。
8. DataView 怎样进入 LearningProblem，而不进入 Adapter。

案例包括线性回归、ETF 时序、图学习和无监督降维。

## 第二十九章　Data Pipeline 与特征语义

1. DataPipelineComponent 的 fit/transform。
2. fit state 与数据泄漏。
3. numericizer、target codec 与 feature space。
4. 条件 Pipeline 和模型条件目标变换。
5. Slot Kernel 在 ML Pipeline 中的使用。
6. 多分支特征、router 与 merge。
7. Pipeline Artifact 与复现。
8. 数据 Pipeline 和 ModelRepresentation 的边界。

## 第三十章　UnknownState、Representation 与 Codec

1. 模型状态为什么使用 UnknownState。
2. values 与结构 metadata。
3. ModelRepresentation 的 init/decode/encode/repair/mutate。
4. Codec 如何映射线性、树、神经图和符号模型。
5. ParameterLayout。
6. fingerprint/equivalent。
7. 条件结构与可变长度状态。
8. safe serializer 往返。
9. Representation 与 Backend capability。

## 第三十一章　Head：输出语义不是最后一层数组

1. point、interval、probability、distribution、piecewise、symbolic head。
2. prediction shape 与语义 shape。
3. 校准、置信区间和不确定性。
4. 多输出、多任务与条件 Head。
5. Head 与 loss/metric 的关系。
6. Head contract 与模型组合。
7. decode 后输出如何进入 LearningProblem。

不同 Head 使用不同小型案例，避免把所有输出语义塞进一个模型。

## 第三十二章　LearningProblem 与 Feedback

1. candidate/model、DataView 与 Context 的输入关系。
2. objectives、constraints、metrics、gradients、residuals。
3. 训练目标与报告指标的区别。
4. regression、classification、interval、time-series、symbolic Problem。
5. multi-objective learning。
6. stochastic feedback 与重复评估。
7. Feedback identity 对齐。
8. Problem 不负责的优化策略。

## 第三十三章　Trainer：机器学习控制平面

1. BlankTrainer 生命周期。
2. ComposableTrainer 的 propose/evaluate/update。
3. setup、fit、run、evaluate、teardown。
4. `run()` 动态转发与继承语义。
5. population、feedback、best state/model。
6. Plugin/Capability 生命周期映射。
7. Context/Snapshot 提交。
8. ResourceContext 与 Backend Session。
9. TrainerResult 与 report。
10. Trainer 与 Solver 的同级关系及差异。

## 第三十四章　OptimizerAdapter 与训练策略

1. OptimizerAdapter 合同。
2. gradient descent、evolution、black-box 和混合策略。
3. gradients/residuals capability。
4. Adapter 权威 state。
5. state/population checkpoint。
6. feedback alignment。
7. 学习率、阶段和停止策略。
8. Adapter 不读取业务数据的原因。

## 第三十五章　Provider、ComputeBackend 与 Session

1. Provider 是什么，不是什么。
2. numpy、torch、jax、tensorflow 等 Backend capability。
3. ComputeBackendSpec/Session。
4. requested、resolved、device policy 与 fallback。
5. ResourceContext 更新后的 Session 同步。
6. required 与 preferred capability。
7. Provider 的 batch、timeout、cancel 和 error contract。
8. 外部模型服务与远程训练 Provider。
9. Backend report 与性能证据。

## 第三十六章　模型组合与 I/O Contract

1. PredictionInputSpec 与 PredictionOutputSpec。
2. 主模型 + 残差模型。
3. stacking 与 boosting-like 组合。
4. 多模态 late fusion。
5. 专家模型与 router。
6. 同 shape 不同语义的错误。
7. 中间 Artifact 与阶段依赖。
8. 组合模型的评估和部署边界。

## 第三十七章　CaseStageRunner 与阶段闭包

1. StageSpec 与 CompletionPolicy。
2. 子 Trainer 的完整生命周期。
3. 父级 ResourceContext 派生。
4. Artifact 注入与提取。
5. final output stage 与聚合策略。
6. best state/model/feedback 的采用。
7. 子阶段失败时的 finally teardown。
8. `fit()` 与 `run()` 一致性。
9. 何时内部 phase 应升级为多个 Project Case。

## 第三十八章　Artifact、模型产物与可复现报告

1. ModelArtifact 与 TypedModelArtifact。
2. TrainerStateArtifact、RunReport、ArtifactBundle。
3. 模型对象、Spec、参数、数据 lineage 和指标。
4. Snapshot 与 Artifact 的边界。
5. save/load 与 schema version。
6. 外部对象存储。
7. 安全加载与环境依赖。
8. Artifact viewer 的职责边界。

## 第三十九章　神经图、时序与符号学习的特殊语义

本章不做模型百科，而是说明这些模型族如何复用前述合同。

1. NeuralGraphRepresentation 与 ParameterLayout。
2. Transformer/CNN/GNN 的结构状态。
3. 时序 DataView、walk-forward 与 temporal Head。
4. symbolic grammar、function pool、expression codec。
5. 符号 gradients、graph cache 与 path memory。
6. 哪些能力留在 mlblack，哪些搜索交给 nsgablack。
7. 模型族新增时的接入判断。

---

# 第五部　统一组合：两个语义层怎样构成更大的运行结构

## 第四十章　组合闭包：Case 为什么可以同时是外层和内层

1. 独立运行与被调用不是两套接口。
2. 标准 request/result payload。
3. component overrides。
4. ResourceContext 派生。
5. Artifact/Snapshot refs。
6. inner error 与 outer Feedback。
7. nested lineage。
8. 组合后生命周期仍然完整。
9. 什么时候用函数短路，什么时候运行完整 Case。

## 第四十一章　外层优化、内层 ML

1. 超参数搜索。
2. 模型结构搜索。
3. 特征/Head/训练预算搜索。
4. 预测辅助决策优化。
5. inner Trainer result 到 objectives/violations 的映射。
6. 训练 Artifact 的缓存与复用。
7. 共享预算和资源。
8. 数据泄漏与公平比较。
9. nsgablack 不 import mlblack 私有实现。

案例分别选用 AutoML、神经结构搜索、ETF lane search 和预测驱动决策，而不是绑定单一生产场景。

## 第四十二章　外层 ML、内层优化与交替系统

1. 学习任务调用数值求解器或结构搜索。
2. differentiable 与 black-box inner optimization。
3. 交替训练/优化。
4. bilevel 与 nested objective。
5. 内层近似解对外层 Feedback 的影响。
6. budget、warm start 和 Artifact reuse。
7. 避免在 Trainer 内创建私有 Project。

## 第四十三章　符号正交嵌套：复杂组合的完整解剖

以现有符号正交系统作为大型案例，但只在这一章集中展开。

1. Stage 1 basis search。
2. 内层参数拟合。
3. orthogonality、stability、complexity 与 rank。
4. Stage 2 task expression search。
5. basis Artifact handoff。
6. graph cache、path memory 与 replay。
7. 外层 nsgablack、内层 mlblack 的职责边界。
8. 两阶段资源、预算和结果 lineage。

## 第四十四章　多 Solver、多 Trainer 与多 Lane 协同

1. serial stages。
2. independent parallel benchmark。
3. cooperative multi-lane search。
4. ensemble training。
5. shared Artifact 与禁止共享的可变 state。
6. lane-level resources 与 fairness。
7. consensus、selection 与 aggregation。
8. Project 编排和 Solver 内多策略的边界。

## 第四十五章　跨 Case 状态、资源与预算继承

把组合问题收口为三类跨边界事实：

1. 状态怎样通过 Ref 而不是对象本体传递。
2. 资源怎样单调收窄。
3. 预算怎样共享而不复制。
4. cancellation/deadline 怎样传播。
5. seed 与 namespace 怎样派生。
6. error 与 retry 由哪一层拥有。
7. result/manifest 怎样记录父子 lineage。

---

# 第六部　正确性与可靠性：复杂组合为什么仍然可信

## 第四十六章　权威状态与时间语义

1. propose 前、evaluate 后、update 后、snapshot 后。
2. update_context 为什么必须重建。
3. Adapter/Trainer 权威 state。
4. evaluated candidate 与 selected population。
5. stale handle。
6. Feedback identity。
7. Result、Snapshot、Artifact 对齐。
8. 一致性提交点。

本章集中处理“对象都存在，但代表不同时间”的静默错误。

## 第四十七章　验证边界与数据完整性

1. dimension、dtype、shape、cardinality。
2. objectives/violations。
3. batch provider。
4. metadata 与 fingerprint。
5. Artifact schema。
6. Context field governance。
7. Task payload。
8. 严格模式与软错误。
9. fail-fast 的边界。

## 第四十八章　错误所有权与恰好一次分发

1. 底层附加 phase 后抛出。
2. 公共入口 error boundary。
3. dispatched marker。
4. `run()` 与直接 public evaluate。
5. Plugin on_error。
6. retry owner。
7. aggregate parallel errors。
8. cleanup/teardown 的 finally。
9. 错误报告结构。

## 第四十九章　并发隔离、取消与晚到写

1. 共享 ndarray/context 的竞态。
2. copy、read-only 与受控 shared handles。
3. ThreadPoolExecutor worker 上限。
4. cooperative cancellation event。
5. `future.cancel()` 的真实含义。
6. still_running 报告。
7. run token/namespace fence。
8. process/worker 强隔离。
9. merge 后关闭写权限。

## 第五十章　Checkpoint、恢复与 Replay

1. Checkpoint 完整状态集合。
2. 一致性提交。
3. Project Manifest resume。
4. Solver/Trainer/Adapter/RNG/Controller/Plugin state。
5. 连续运行与恢复运行比较。
6. Replay 的事件来源。
7. 决策回放与重新执行。
8. 外部不可重放副作用。
9. schema migration。

## 第五十一章　确定性、随机性与实验可比性

1. root seed 与层级派生。
2. 并行完成顺序不应决定随机序列。
3. Provider stochasticity。
4. Backend nondeterminism。
5. 多 seed 报告。
6. cache 与 fingerprint。
7. benchmark fairness。
8. reproducible Artifact 所需环境信息。

## 第五十二章　序列化、安全与外部边界

1. safe serializer 与 pickle 风险。
2. UnknownState/ndarray codec。
3. HMAC/完整性。
4. 凭据与 URL 脱敏。
5. Artifact 安全加载。
6. Provider 身份与权限。
7. namespace 隔离。
8. 不可信 payload validation。
9. 审计保留与隐私。

## 第五十三章　可观测性与运行证据

1. log、metric、trace、event、report 的区别。
2. run/case/stage/candidate/task/snapshot/artifact correlation。
3. 预算、资源、Provider 和 branch 指标。
4. Run Inspector 的数据来源。
5. Dashboard 为什么是投影层。
6. 性能分析与业务指标分离。
7. 降级、fallback 和 late write 的可见性。
8. 一次运行的最小证据包。

---

# 第七部　使用方法：从需求选择正确的框架路径

## 第五十四章　任务分类与入口选择

1. 纯优化。
2. 纯监督学习。
3. 无监督学习。
4. 数据分析/Profiling。
5. 预测辅助优化。
6. 模型结构搜索。
7. 数值仿真与外部后端。
8. 多 Case 工作流。
9. 什么时候不需要完整 Project。

本章提供决策树，但每个分支链接到前面的原理，而不是孤立配方。

## 第五十五章　从空目录构造标准 Project

一步步使用 CLI 和模板创建 Project、添加 solver/trainer Case、实现 builder、声明资源、运行 Doctor/check/build-check。这里才给完整新手教程，因为读者已经理解每个文件为什么存在。

## 第五十六章　优化 Case 方法集

用多个短案例分别展示连续、多目标、组合、图、约束、动态、代理辅助和外部仿真问题。每个案例只突出最适合它的机制，并说明可扩展路线。

## 第五十七章　ML Case 方法集

用线性回归、分类、区间预测、ETF 时序、降维、神经图和符号学习分别展示 DataView、Head、Trainer、Backend 与 Artifact 的不同组合。

## 第五十八章　跨框架 Project 方法集

包含超参搜索、模型结构搜索、预测驱动优化、符号两阶段学习、多模型 benchmark 和多 Lane 协同。每个模式给出 Project DAG、资源/预算边界和结果协议。

## 第五十九章　本地、Redis 与外部 Worker 部署路径

从内存单进程开始，逐步迁移到文件 Snapshot、Redis Context/Snapshot、SQLite/Redis Transport、外部 Worker 和对象存储。每一步说明增加了什么能力、带来了什么失败模式。

## 第六十章　故障排查手册

按症状组织：预算异常、策略晚切换、Snapshot stale、shape 错位、Redis 恢复失败、资源声明与实际后端分叉、并行不确定、timeout 后污染、子 Case 空结果、Artifact 层级错误、Doctor 与运行不一致。

---

# 第八部　扩展、治理与长期演进

## 第六十一章　新增 Adapter 的完整过程

从归属、合同、状态、population、Context projection、checkpoint、并行、测试到 Catalog/文档，给出一个真实完整实现与审查方法。

## 第六十二章　新增 Representation、Bias 与 Plugin

分别解释三类扩展的不同风险，给出错误版本和修正版本，不把它们压缩成相同模板。

## 第六十三章　新增 Provider、Backend 与 Bridge

重点覆盖 capability、资源、Session、batch、timeout、cancel、幂等、序列化、安全和审计。外部系统不是“套一个函数”即可接入。

## 第六十四章　新增模型族、Head 与 LearningProblem

说明怎样综合考虑 DataView、Codec、Representation、Head、Problem、Trainer、Artifact 和 nsgablack 搜索集成，而不是只加一个模型类。

## 第六十五章　测试体系与故障注入

1. unit、contract、integration、live backend、benchmark。
2. 单点/批量/短路/Snapshot 最小矩阵。
3. 部分失败预算。
4. 并发竞态与 late write。
5. Redis codec。
6. 租约过期和 Worker 重试。
7. checkpoint/replay。
8. 跨框架资源继承。
9. 性能回归。

## 第六十六章　Doctor、Catalog 与示例治理

1. Doctor 的结构/构建/运行证据边界。
2. default 与 framework-core Catalog profile。
3. Catalog entry 不等于装配。
4. 示例必须使用正式 Scaffold。
5. `my_project` 与正式 examples 的边界。
6. README 组件声明与 build-check 对齐。
7. 文档口径与源码不一致的处理。

## 第六十七章　API 稳定性、兼容层与迁移

1. public surface。
2. schema/API semantic versioning。
3. forwarder 的使用期限。
4. deprecation 与 migration guide。
5. blackbase 收口顺序。
6. 模板、Doctor、Catalog、示例同步。
7. dirty worktree 与发布版本证据。

## 第六十八章　性能工程

1. 先测评估成本还是框架开销。
2. batch 与 vectorization。
3. Pool 选择。
4. Snapshot 粒度和序列化成本。
5. Context 复制。
6. cache identity。
7. Backend warmup。
8. 嵌套 fanout。
9. benchmark 设计与误区。

## 第六十九章　当前边界、已知缺口与演进路线

最终章严格区分三类内容：当前源码已实现且有验证；当前结构已存在但运行证据不足；下一阶段建议。讨论进程级取消、分布式一致性、Provider 生态、schema registry、Artifact store、性能与安全加固，但不把路线图写成现有能力。

---

# 附录体系

## 附录 A　术语与本体词典

按“运行结构、语义组件、状态、资源、控制、产物、分布式”分组解释术语，给出容易混淆的反例。

## 附录 B　公共 API 与源码锚点

按正文依赖顺序列出三个仓库的权威模块、类型、方法、适配层和迁移 forwarder。

## 附录 C　生命周期时序全集

包含 Solver、Trainer、Plugin、Project Stage、外部 Worker、嵌套 Case、Checkpoint/Resume 的完整时序图。

## 附录 D　Context Key 与 Contract 索引

列出规范 key、owner、类型、生命周期、是否允许进入 Store、对应 Snapshot/Artifact 引用。

## 附录 E　Snapshot、Artifact、Task 与 Result Schema

给出字段级协议、版本、JSON 示例和 codec 说明。

## 附录 F　配置与命令参考

Project CLI、Case CLI、Doctor、Catalog、Redis、Worker、恢复和常用诊断命令。

## 附录 G　测试与发布清单

分别提供组件、Case、Project、外部 Provider、分布式运行和版本发布清单。

## 附录 H　案例索引

按机制索引正式 examples：哪个案例证明哪项能力、运行入口是什么、需要什么可选依赖、验证范围到哪里。

## 附录 I　架构决策记录

记录为何统一 builder、为何 Context 轻量、为何 L0 授权属于 Project、为何共享 Kernel 落在 blackbase、为何取消采用协作式语义等关键 ADR。
