# Black Framework Stack 中文白皮书

blackbase + nsgablack + mlblack：从统一运行底座到优化搜索与机器学习语义

版本：工程架构与实践版 0.1  
生成日期：2026-08-16  
主版本：中文

## 阅读目录

1. 卷首：这套框架真正解决什么（规范）
2. 第一卷：统一框架栈与职责边界（规范）
3. 第二卷：运行闭环与正确性语义（规范）
4. 第三卷：工程可靠性与生产化（规范）
5. 第四卷：从入门到进阶的学习路径（规范）
6. 第五卷：实现锚点与协议索引（实现）
7. 架构思想：为什么必须解耦（说明）
8. 概念映射：从问题到运行表面（说明）
9. Project、Case 与标准脚手架（规范）
10. Context 契约（规范）
11. Context 字段治理（规范）
12. BlackBase Project Runtime（实现）
13. Redis 任务传输（实现）
14. 验证、Doctor、Catalog 与长期演进（实践）
15. Slot Kernel 最小规范（实践）
16. 自定义 Adapter（实践）
17. 自定义 Bias（实践）
18. Plugin 十钩子生命周期（实践）
19. Pipeline 编排与组件设计（实践）
20. 复杂模型组合与 I/O Contract（实践）
21. ML 验收、Catalog 与 Artifact（实践）
22. Benchmark、Dashboard 与资源审计（参考）
23. ML Slot Kernel 最小规范（实践）
24. ML 自定义 Adapter（实践）
25. ML 自定义 Bias（实践）
26. ML Plugin 生命周期（实践）
27. ML Pipeline 编排与组件设计（实践）
28. Plugin 系统使用指南（参考）
29. 并行评估（参考）
30. Run Inspector（参考）
31. 组件拆分规则（规范）
32. 稳定 API 表面（规范）

---

# 卷首：这套框架真正解决什么

> 文档状态：规范。本章为白皮书原创主卷。

## 0.1 白皮书的核心判断

Black Framework Stack 不是把几个算法、几个训练器和一个任务队列拼在一起。它试图解决的是一个更难、也更容易在工程中被低估的问题：当一个计算任务同时包含搜索、训练、仿真、约束、并行、嵌套调用、状态持久化和外部后端时，怎样让每一层仍然拥有清晰的语义，怎样让执行结果可解释、可复现、可停止、可恢复，怎样避免“看起来跑通”却在预算、状态或资源上悄悄失真。

这种问题通常不会在十几行演示代码里出现。它会在项目逐渐复杂之后暴露出来：一次评估由本地函数变成远程仿真；一个候选需要启动一个内层训练任务；不同算法开始并行提出方案；运行中需要动态切换策略；一次失败可能只完成了批量评估的一半；超时分支虽然不再等待，却仍在后台写入旧状态；内存快照正常，换成 Redis 后自定义状态却变成了字符串。每一个局部实现都可能“合理”，但组合起来以后，系统是否仍然正确，取决于框架有没有把边界和生命周期写成真正的运行协议。

因此，本白皮书不把算法数量、Catalog 条目数或 Dashboard 页面数量作为主角。它首先解释运行架构：谁拥有控制权，谁发放资源，谁对预算负责，候选在什么时刻被认为已经消耗评估，Adapter 更新时读取的是哪个时间点的上下文，快照保存的是评估前候选还是更新后的权威种群，插件异常由哪一层分发，取消和超时是否能阻止晚到写入。只有这些语义稳定之后，算法、模型、Provider 和可视化能力才有可靠的承载面。

## 0.2 三个仓库不是三个孤岛

统一框架栈由三个职责不同的仓库组成。

`blackbase` 是共享 substrate。这里的 substrate 可以理解为“不同语义框架都必须依赖、但不应各自复制的一组运行底座”：Project、Case、标准脚手架、Context、Snapshot、ResourceContext、L0 资源授权、共享 Pipeline Slot Kernel、统一 Plugin 生命周期和跨 Case 轻量协议类型。它不负责决定怎样做 Pareto 选择，也不负责定义一个神经网络怎样解码。

`nsgablack` 是优化与搜索语义层。它负责 Solver 生命周期、候选生成与反馈更新、目标与约束、种群与前沿、Adapter 策略、RepresentationPipeline、Bias 以及搜索审计。名字里虽然有 NSGA，但框架并不等于 NSGA-II；进化搜索只是众多 Adapter 范式之一。

`mlblack` 是机器学习语义层。它负责 DataView、数据 Pipeline、ModelRepresentation、Codec、Head、LearningProblem、Trainer、Provider、ComputeBackend 和 Artifact。它可以在一个 Project 中作为外层 Case，也可以作为优化候选的内层评估器，但它不应该重新发明私有的 Project 调度器或全局资源池。

这三者的关系不是上层简单调用下层，而是“共享底座 + 两种语义层”。一个项目可以只有 nsgablack Case，也可以只有 mlblack Case，还可以让外层 nsgablack 搜索模型结构、内层 mlblack 拟合参数。无论哪种组合，Project 级资源授权、Case 入口、上下文与快照协议都应保持一致。

## 0.3 白皮书的读者

如果你是第一次使用框架，可以先建立三个直觉。第一，Problem 说明“什么算好”，Representation 说明“候选是什么”，Adapter 说明“下一步怎么找”；不要把三者写进同一个循环。第二，Context 是轻量运行视图，不是对象仓库；种群、模型、大数组、历史和 trace 应进入 Snapshot 或 Artifact。第三，Case 只声明资源需求，真正的资源授权来自 Project L0。

如果你准备扩展框架，重点阅读组件边界、公共契约和错误所有权。自定义 Adapter 必须闭合 `propose/update` 语义；自定义 Plugin 必须尊重生命周期和上下文契约；自定义 Provider 必须返回合法 shape，并在资源、超时和异常上给出可审计行为；共享能力优先落在 blackbase，而不是在两个语义仓库里各复制一份。

如果你负责生产运行或架构审查，重点阅读预算、快照、并行、取消、租约、外部 Worker 和回放。工程上最危险的不是显式崩溃，而是静默错位：旧上下文导致策略晚一代切换，旧快照被当成当前种群，半批失败后已消耗预算被退还，线程超时后继续写状态，或者资源审计显示 GPU 而实际 Session 仍在 CPU。

## 0.4 四条阅读路线

入门路线从“统一框架栈与职责边界”开始，然后阅读“Project、Case 与标准脚手架”“Slot Kernel 最小规范”“自定义 Adapter”“Plugin 生命周期”。读完以后，应当能够创建一个独立 Case，完成装配、检查和一次最小运行。

优化路线重点阅读 Solver、评估链、Adapter、Representation、Bias、Pareto、并行评估和嵌套 Case。目标不是记住所有类，而是能准确回答一次 generation 中每个状态变化发生在哪里，以及哪一个对象拥有最终权威状态。

机器学习路线重点阅读 Trainer、UnknownState、Feedback、ModelRepresentation、Codec、Head、LearningProblem、Artifact 和模型组合 I/O Contract。进阶部分会解释结构搜索、参数拟合、多阶段残差、符号学习与优化层如何组合。

生产化路线重点阅读 Context/Snapshot/Artifact、ResourceContext、预算、租约、任务传输、取消、错误边界、Checkpoint、Replay、Doctor 和 Run Inspector。读完以后，应当能设计一次运行的审计证据，而不只是得到一个最终分数。

## 0.5 本文怎样区分事实、规范与建议

白皮书中的“规范”来自当前协作规则和公共契约，它描述代码新增或改造时必须保持的边界。“实现”来自当前源码，可以定位到具体模块、类型或方法；如果本次没有执行相应测试，只代表静态分析确认，不等同于运行验证。“实践”来自当前教程和正式脚手架，提供可复制路径。“建议”表示下一阶段值得收口的工程方向，不能当成已经存在的能力。

这一区分很重要。一个漂亮的架构图可以表达意图，却不能证明线程池受到了 ResourceContext 的约束；一份 README 可以写着支持快照恢复，却不能证明安全序列化能往返恢复自定义状态。白皮书会尽量把“应该怎样”“代码现在怎样”“已经验证到什么程度”分开书写。

## 0.6 什么叫运行闭环

所谓闭环，不是某个函数返回了结果，而是一次运行拥有完整的因果链：Project 发放资源，Case 通过正式 builder 构造 Solver 或 Trainer，控制平面启动生命周期，策略提出候选，Representation 维护候选语义，评估入口验证输入输出并消耗预算，策略用最新上下文更新权威状态，权威状态写入快照，插件获得一致事件，停止控制器能在正确时刻请求终止，结果与 Artifact 能说明本次运行用了什么资源、什么组件、什么版本和什么随机性来源。

如果任何一环缺失，系统可能仍能打印“成功”，但无法回答关键问题。例如，Adapter 已经完成环境选择，Solver 却保存了评估前候选；这时 Checkpoint 可写、Redis 可读、Dashboard 可展示，但它们共同保存的是错误状态。又例如，批量评估预留了十次预算，第六个候选报错，框架若撤销整个 reservation，就等于把已经调用过 Provider 的五次计算从账本里抹掉。闭环要求状态和现实发生过的计算一致。

## 0.7 设计精妙与工程严谨并不冲突

这套框架的设计确实具有很强的组合性：Solver、Adapter、Representation、Bias、Plugin 相互正交；Project、Case、Scaffold 允许复杂任务分解；Slot Kernel 可以串行、并行和路由；nsgablack 与 mlblack 能在外层搜索和内层训练之间嵌套。精妙之处不在于类型很多，而在于复杂结构可以由少数稳定协议组合出来。

但组合性越强，越需要严格的工程语义。一个可替换 Adapter 只有在权威状态接口一致时才真正可替换；一个通用 Pipeline 只有在并行输入隔离、资源授权、合并规则和取消写栅栏明确时才真正通用；一个插件生命周期只有在错误最多且至少分发一次时才真正可靠。工程严谨不是给精妙设计加负担，而是让设计在复杂运行中仍然成立。

## 0.8 白皮书不承诺什么

框架不会替代业务建模。它不能自动替你定义有意义的决策变量、目标、约束、训练标签或评估指标。它也不会因为有 Catalog 就保证组件质量，因为“能被发现”与“运行正确”是两个问题。

框架不会把任意外部系统假装成本地函数。仿真器、数据库、对象存储、Ray、Kubernetes、云 GPU 或商业求解器都需要正式 Provider、Bridge 或 Runtime Surface；身份、权限、配额、超时和幂等语义必须显式处理。

框架也不承诺线程超时能够强制杀死 Python 代码。线程模型中的取消通常是协作式：框架设置取消事件，在阶段边界检查，并通过 run token 或 namespace 拒绝晚到写入。需要强隔离时，应使用进程、Worker 或外部执行后端。

## 0.9 最重要的十个问题

阅读后续章节时，可以不断用以下问题检验设计：

1. 这个能力应该属于共享底座、优化语义、ML 语义，还是外部 Provider？
2. 当前对象是声明资源需求，还是拥有资源授权？
3. Context 中的字段是轻量事实还是大对象本体？
4. 谁拥有候选、种群或模型状态的最终权威版本？
5. 预算在“预留、实际发起、成功完成、未使用退还”之间怎样记账？
6. Adapter 或策略读取的是评估前上下文还是评估后的最新上下文？
7. 同一个异常会由哪一个公共边界分发，怎样保证不会重复触发恢复动作？
8. 并行分支是否共享可变输入、Context 或运行句柄？
9. 超时后仍在运行的分支能否写入已经结束的运行命名空间？
10. 最终 Result、Snapshot、Artifact 与 Audit 是否描述同一个真实状态？

如果一个复杂设计能持续回答这十个问题，它才不仅“看起来先进”，而是真正可以被使用、扩展和运维。

---

# 第一卷：统一框架栈与职责边界

> 文档状态：规范。本章为白皮书原创主卷。

## 1.1 从“算法库”转向“运行系统”

传统算法库的核心问题是“某个算法怎样计算”。工程框架的核心问题则是“许多可替换组件怎样在同一套生命周期和资源约束下协作”。这两个问题的尺度不同。前者关注数学步骤，后者还必须处理装配、状态、失败、并行、恢复、审计和跨任务依赖。

nsgablack 最初容易被名字理解为一个多目标进化算法集合，但当前统一架构把它放在更准确的位置：它是优化和搜索语义层。算法实现是 Adapter；Solver 是控制平面；Representation 维护候选的编码、解码和修复；Problem 定义目标、约束和边界；Plugin 承载运行能力；Project substrate 负责跨 Case 编排与 L0 授权。这样一来，NSGA-II、差分进化、模拟退火、信赖域、A* 或多策略链都可以通过相同的运行协议进入系统。

mlblack 也不是另起炉灶的训练脚本集合。它把机器学习任务拆成稳定的语义组件：DataView 描述数据视图，Pipeline 执行数据变换，ModelRepresentation 将 UnknownState 解码为模型或模型规格，Codec 管理结构化参数，Head 定义点预测、区间、概率或符号输出语义，LearningProblem 计算 Feedback，Trainer 执行单个训练任务，Artifact 保存可复现结果。

blackbase 的出现是架构收口的结果。当两个语义层都需要 ContextStore、SnapshotStore、ResourceContext、Project Runtime、Plugin 生命周期和 Pipeline Kernel 时，复制意味着两套看似相同但细节不同的协议。共享底座的目标，是让这些“与优化或 ML 业务无关、但决定运行正确性”的能力只有一个权威实现。

## 1.2 四个层级与一个外部边界

统一栈可以按职责分成四个内部层级。

第一层是 Project L0。它拥有资源授权、全局预算、租约、命名空间、跨 Case 顺序和并行扇出。它回答“这个项目最多可以使用多少线程、哪些设备 token、多少评估或费用预算、哪些 Case 可以同时运行”。L0 不是某个 Solver 或 Trainer 的配置字段，而是上级发放的事实。

第二层是 Case Runtime。一个 Case 是最小的独立可运行单元，可以是 Solver 也可以是 Trainer。Case 声明 requirement，接收有效 ResourceContext，使用标准 builder 装配组件，执行一个闭合任务，并返回结构化结果、ArtifactRef 和审计信息。Case 可以作为 Project 的顶层阶段，也可以被另一个 Case 作为内层评估调用。

第三层是语义控制平面。nsgablack 对应 Solver，mlblack 对应 Trainer。它们负责单个任务的生命周期、上下文构建、评估入口、插件调度、状态提交和结果构造，但不拥有 Project 级全局资源。

第四层是可替换语义组件，包括 Adapter、Representation、Problem、Bias、Plugin、Data Pipeline、Codec、Head、Provider 等。组件应当通过明确的输入输出和 Context Contract 协作，而不是互相读取私有字段。

外部边界是 Domain Backend。商业求解器、仿真器、数据库、对象存储、向量索引、Ray、Kubernetes 和云服务都不应该进入核心语义层。它们通过 Provider、Bridge 或 Runtime Surface 接入，对连接、认证、超时、序列化、幂等和故障策略负责。

## 1.3 功能归属的判断方法

新增能力前先问“它改变的是什么语义”。如果它改变候选如何提出、怎样选择、怎样维护 Pareto 前沿，它属于 nsgablack。如果它改变数据怎样表示、模型怎样解码、输出怎样解释、训练反馈怎样计算，它属于 mlblack。如果它改变跨 Case 编排、上下文/快照协议、资源授权、任务传输、共享生命周期，它属于 blackbase。如果它依赖某个外部系统的连接和运行特性，它属于 Provider 或 Bridge。

这个判断方法可以防止最常见的架构漂移。例如，GPU 设备选择不应隐藏在某个 Trainer 内部，因为设备授权来自 L0；Trainer 可以根据授权选择兼容 Backend，并报告实际结果。又例如，nsgablack 不应直接 import mlblack 的具体 Trainer 类来实现内层训练；它应该发送结构化 inner request、component overrides、ResourceContext 和 ArtifactRef，让 mlblack 标准 Case 自己完成装配。

跨仓能力的通用契约应先落到 blackbase，再由两个语义层分别适配。Pipeline 并行 merge 就是典型例子：serial、parallel、router 是共享编排语义，不应在 nsgablack 和 mlblack 各维护一套。优化侧可以把它用于候选的 init/mutate/repair，ML 侧可以把它用于特征分支或模型组合，但并行输入隔离、worker 上限、取消和 merge 规则应一致。

## 1.4 Project -> Case -> Standard Scaffold

统一目录规则不是审美偏好，而是运行闭包。Project 目录包含 `project_config.py`、`run_project.py` 和 `cases/`。`project_config.py` 描述 Case 顺序、并行组和 L0 资源；`run_project.py` 是项目正式入口。每个 `cases/<case_name>/` 都是独立标准脚手架，能够单独构造、检查和运行。

标准 Case 使用统一目录：`problem/`、`pipeline/`、`adapter/`、`bias/`、`plugins/`、`evaluation/`、`runtime/`、`solver/`，以及顶层的 `config.py`、`build_solver.py` 和 `run_solver.py`。Solver 与 Trainer 处在相同抽象层级，因此目录形状不应分叉。`.case` 中的 `kind=solver|trainer` 只决定语义分类和默认执行方法，不改变规范入口。

`build_solver.py` 是唯一规范装配入口。即使 Case 的主体是 Trainer，`build_trainer.py` 也只是 `build_solver` 的薄别名。`run_solver.py` 是唯一规范 CLI/debug 入口，`run_trainer.py` 只转发到其 `main`。这一规则让 Project Runtime 无需猜测多个互相分叉的入口，也让 Doctor 能审查真正的装配面。

规范 builder 应接收 `resource_context` 与 `component_overrides`。前者传递 Project L0 的有效授权，后者支持外层 Case 在不依赖内层私有实现的前提下覆写正式组件。builder 返回 Solver 或 Trainer 对象，Project Runtime 再根据 Case kind 调用 `run()` 或 `fit()`。

## 1.5 为什么 Case 必须独立闭合

一个 Case 只有在以下条件都成立时才算闭合：它能从正式 builder 构造；组件注册与装配都能在 Case 内定位；资源需求可以声明并被注入；输入通过结构化 payload 或 ArtifactRef 进入；输出通过 Result、Snapshot 或 ArtifactRef 离开；错误和生命周期能够被统一边界捕获；检查输出能说明实际装配了什么。

独立闭合并不意味着不能嵌套。相反，外层 Case 调用内层 Case 时，内层仍然保留自己的边界。外层优化候选可以改变内层模型规格，但不应穿透到内层 Trainer 的私有字段；外层只提供正式 overrides。内层可以返回 RMSE、约束、模型 Artifact 和审计字段，外层再把它们映射成优化目标。

这使多 Solver、多 Trainer 和混合任务具有同一种组织形式。阶段顺序和并行属于 Project；每个阶段内部的搜索或训练属于 Case；每个 Case 内的候选或数据流属于 Solver/Trainer 与 Pipeline。边界清楚以后，系统不需要针对“嵌套训练”“多算法融合”“符号两阶段搜索”分别发明一套特殊运行器。

## 1.6 blackbase 的共享协议

blackbase 的 Context 子系统提供 ContextStore、ContextContract、规范 key、schema、事件和字段治理。它的职责不是保存任意 Python 对象，而是提供轻量、可审计、可序列化的运行视图。一个 Contract 可以声明组件需要、提供、修改或缓存哪些字段，Doctor 和运行时据此检查隐式依赖。

Snapshot 子系统承载大对象和代级状态。SnapshotHandle/Record 将 key、版本、时间和 payload 联系起来；内存、文件或 Redis 后端提供不同持久化范围。安全序列化需要对共享协议类型建立正式 codec，例如 UnknownState 不能在 Redis 往返时退化成 `repr` 字符串。

Resource 子系统提供 ResourceContext、ResourceRequirement、PoolScheduler、Budget Authority、Lease Store 和 Transport。ResourceContext 是不可越权的有效授权视图；`derive_child()` 用于内层 Case 收窄资源。预算是共享原子状态，不应在每个 Solver 中复制一个局部计数。租约与 heartbeat 用于外部 Worker 或分布式资源，fence 用于拒绝过期持有者继续写入。

Kernel 子系统提供 PipelineSpec、PipelineSlotSpec 和 PipelineOrchestrator。Slot 可以使用 serial、parallel 或 router policy；parallel 可以声明 merge。运行时必须限制 worker 数、隔离可变 value/context、正确调用 Operator 签名，并在超时或取消后阻止晚到分支写入运行句柄。

Plugin 子系统提供统一十钩子生命周期和 PluginManager。nsgablack 原生 Plugin 与 mlblack 旧 Capability 可以映射到同一事件语义，从而让 checkpoint、trace、评估观察、错误处理和报告不再各自拥有不同调用顺序。

共享 Types 包含 UnknownState、Feedback、PopulationSnapshot 和 TrainerResult。这些类型只携带跨边界所需的轻量协议数据，不承载某个语义层的算法私有逻辑。

## 1.7 nsgablack 的正交组件

Problem 负责决策空间、目标、约束和评估语义。它不决定搜索策略。一个 Problem 可以被多个 Adapter 复用，允许公平比较算法；同一个 Adapter 也可以面对不同 Problem，只要候选和反馈契约一致。

Solver 是生命周期与控制平面。它管理 generation、evaluation_count、停止请求、RNG、插件、Context/Snapshot 访问和公共评估入口。它不应该膨胀成“所有算法的共同父类实现”，否则每加一个策略都要修改控制平面。

Adapter 通过 `propose(solver, context)` 和 `update(solver, candidates, feedback, context)` 表达策略，其中正式反馈是 `OptimizationFeedbackBatch`，并可向纯数值算法投影为 objectives / violations。候选批次同时保留 UnknownState 语义视图、ndarray 数值视图与 token/provenance。进阶 Adapter 还应实现 state、population 和 context projection 接口，以支持 checkpoint、权威种群提交和审计。Adapter 更新后的 population 是代级快照的首选权威来源。

RepresentationPipeline 是候选流转的唯一入口，负责 init、mutate、repair、encode 和 decode。它保证候选 shape 与语义稳定。Repair 只做可行性兜底，不应偷偷执行完整业务搜索；否则算法控制权会从 Adapter 泄漏到表示层。

Bias 是软引导层，可以注入先验、偏好、风险、探索或收敛信号，但不能取代硬约束。Plugin 是运行能力层，可以记录、存储、观测、控制或短路评估，但不能改变算法核心选择语义。

## 1.8 mlblack 的语义链

mlblack 用 UnknownState 表示尚未解码的模型状态。UnknownState 不只是数值向量，还包含会影响 decode 的 metadata。因此候选等价性不能只比较 values；Representation 的 `fingerprint()` 或 `equivalent()` 必须覆盖语义 metadata，避免把旧 Feedback 错绑到数值相同但结构不同的新模型。

ModelRepresentation 定义 init、decode、encode、repair、mutate 和批量版本。Codec 负责结构化参数与扁平状态之间的变换，Head 负责输出语义。LearningProblem 消费解码后的候选和 DataView，返回 Feedback，其中可以包含 objectives、constraints、gradients、residuals 和 metrics。

LearningSolver 不是第二套控制平面，而是把 ML 的 DataView、Codec、Problem、Provider、Artifact 与 `fit()`/`TrainerResult` 词汇投影到 nsgablack Solver。propose/evaluate/update 统一由 nsgablack AlgorithmAdapter 驱动。多个具有独立生命周期的学习任务必须作为标准子 Case，通过 BlackBase `CaseStageRunner` 与 `CaseRunRequest` 组合；完整子 Case 的结果、Artifact、资源与 lineage 均由公共执行信封闭合。

Artifact 与 Snapshot 有不同生命周期。Snapshot 用于运行内或恢复时的状态，Artifact 是对外可复现产物，通常包含模型、规格、报告、血缘和必要元数据。大型阶段产物通过 ArtifactRef 注入后续 Case，避免复制进 Context。

## 1.9 外部 Provider 与 Bridge

外部能力接入首先要明确它提供的是评估、训练、存储、传输还是执行。Provider 应对外暴露稳定输入输出，不让核心框架依赖具体 SDK。Bridge 负责类型转换、资源映射和错误标准化。Runtime Surface 负责连接与生命周期，例如创建 Session、检查 capability、释放资源和报告实际后端。

一个成熟 Provider 至少应说明：输入是否可批量；返回 shape；候选是否逐个触发 hook；失败发生时哪些调用已经真实发起；是否幂等；预算按发起还是完成计数；超时能否终止执行；外部任务如何取消；结果和异常怎样关联 run token；序列化是否保留协议类型。

把这些问题藏起来，会让核心框架在本地小样例中正常、在真实后端中失真。正式 Bridge 的价值并不只是少写几行调用代码，而是把外部系统的不确定性压缩为可审计契约。

## 1.10 常见反模式

第一类反模式是私有编排：在 example 中手写线程池、阶段顺序和资源分配，绕开 Project Runtime。这样做短期快，长期会让检查、审计和嵌套全部失效。

第二类反模式是大对象进入 Context：把 population、objectives、history、模型或 trace 直接塞入 ContextStore。它会造成复制、序列化、并发覆盖和长期膨胀，应改为 Snapshot/Artifact + 引用。

第三类反模式是语义越层：Adapter 直接读业务数据，Plugin 改写选择逻辑，Repair 执行完整搜索，Trainer 分配全局 GPU，nsgablack import mlblack 私有 Trainer。这些写法都让组件无法独立替换。

第四类反模式是把声明当成执行：spec 写了 merge 不代表 merge 真被调用；配置写了 GPU 不代表 Session 使用了 GPU；Controller 注册了不代表生命周期真的执行 resolve；Catalog 能列出组件不代表 builder 实际装配。任何“支持”都需要沿入口到输出追踪真实路径。

第五类反模式是兼容层无限增长。迁移期 forwarder 可以保留旧 import，但新能力必须落在权威实现，兼容层不应继续承担新语义。否则共享底座只是名义上的，分叉仍会继续。

## 1.11 架构收口的判断标准

统一框架栈是否真正收口，可以用四项标准判断。

其一，所有复杂项目都能用同一种 Project/Case/Scaffold 形状表达，不再需要特例入口。其二，共享资源、状态和生命周期只有 blackbase 一个权威实现，两个语义层只保留适配和专属逻辑。其三，外层与内层通过结构化 payload、ResourceContext、Snapshot/ArtifactRef 和 component overrides 通信，不穿透私有对象。其四，运行输出能同时说明声明、有效授权、实际后端、装配组件和最终权威状态。

这四项都成立时，框架的组合深度才会转化为可维护性：新算法、新模型、新 Provider 或新项目只是增加语义组件，而不是再增加一套运行世界。

---

# 第二卷：运行闭环与正确性语义

> 文档状态：规范。本章为白皮书原创主卷。

## 2.1 一代运行不是一个函数，而是一条时间轴

在优化系统中，“一代”经常被简化成 `propose -> evaluate -> update`。这三个动作是骨架，但工程上必须把时间点继续拆开，因为预算、上下文、插件、快照和停止判断都依赖它们的先后关系。

标准时间轴应当是：构建评估前上下文；触发 generation start；Adapter 提出候选；Representation 对候选执行必要的编码、修复和验证；评估入口预留预算并逐项或批量发起真实评估；验证 objectives 与 violations 的 shape；提交已实际消耗的预算与 evaluation_count；构建评估后上下文；Adapter 使用最新上下文更新权威状态；从 Adapter 读取权威 population；验证并提交代级 Snapshot；触发 step 和 generation end；Controller 根据最新状态解析控制动作；若未停止则进入下一代。

这个顺序不是唯一可能的实现形式，但语义必须等价。尤其不能用评估前 Context 调用 Adapter.update，也不能在 Adapter.update 之前把候选当成最终种群写入 Snapshot。

## 2.2 propose_context 与 update_context

Adapter.propose 需要看到评估前状态：当前 generation、已经消耗的 evaluation_count、上代 best、当前种群引用、资源授权和策略阶段。它据此决定提出多少候选、使用哪个策略、是否探索或开发。

评估结束后，系统事实发生了变化。evaluation_count 已增加，best 可能更新，评估结果快照已经生成，预算余量也可能跨越策略阈值。因此 Adapter.update 必须接收重新构建的 update_context。若直接复用 propose_context，即使 Solver 内部计数已经更新，Context 中仍然可能保留旧值；策略链使用 `setdefault()` 或只读映射时，不会自动被 Solver 新状态覆盖。

这种滞后很隐蔽。例如预算 100，评估前计数 90，本批 20 个候选。实际完成后已经达到 110，但 Adapter.update 看到的仍是 90，于是阶段切换、退火计划或停止策略晚一代触发。单次运行看似只差一代，嵌套任务中却可能放大成大量额外训练或仿真。

正确做法是显式区分两个上下文。propose_context 只代表提出候选时的世界；update_context 在评估提交后重新构建，带上最新计数、best、反馈引用和运行事件。Context 名称不一定必须进入公共 API，但时间语义必须存在。

## 2.3 评估入口是系统的会计边界

Problem 或 Provider 负责计算目标，但公共评估入口负责保证计算能被框架安全使用。它至少承担候选验证、hook、Provider 选择、返回值标准化、shape 验证、预算记账、evaluation_count、错误标记和评估快照。

单目标输出也必须满足明确 shape。若系统声明 `num_objectives=2`，Provider 返回一个数，框架不能凭猜测交给 Adapter。可选策略只有两类：按明确规则补齐，或者立即报错；默认更安全的是报错。候选维度同样需要验证，避免 Representation 与 Problem 对决策变量数量理解不同。

批量 Provider 的输出必须检查为 `N x M`，其中 N 对应候选数，M 对应目标数；violations 必须与 N 对齐，并具有约定的约束维度。若 Provider 返回单个向量、转置矩阵、缺少行或多出行，直接传给 Adapter 会造成候选和反馈错配。

Provider 短路不能绕过运行语义。批量 Provider 路径仍需增加 evaluation_count、触发约定的 evaluate hooks、写入评估快照并遵守预算。是否逐候选触发 hook 可以由协议声明，但不能在不同路径中无声改变。

## 2.4 `None` 不是合法评估结果

插件或 Provider 常用 `None` 表示“我不接管，请继续默认路径”。这是一种链式责任语义，而不是一个目标值。因此评估调度必须区分“未处理”与“处理后返回空结果”。

安全规则是：Provider 没有接管时，继续调用下一个 Provider 或 Problem；如果所有入口都没有产生合法 Feedback，公共评估 API 应报出契约错误。不能把 `None` 转成零目标或空数组，否则 Adapter 会把缺失评估当成有效最优值。

同样，Plugin 的 `on_evaluate_start` 和 `on_evaluate_end` 是观察或增强钩子，除非插件明确实现正式短路接口，否则返回值不应被误认为评估结果。

## 2.5 硬预算的四本账

硬评估预算不能只维护一个“成功次数”计数，因为现实执行存在并发和部分失败。至少要区分四个数量：已预留数量、已实际发起数量、成功完成数量、尚未发起且可以退还的数量。

预留解决并发超卖问题。多个 Worker 在发起评估前原子地占用额度，确保总发起数不会超过上限。实际发起表示 Problem、Provider 或外部任务已经被调用，这部分成本已经发生，无论最终成功、超时还是报错，都不能退还。成功完成用于统计有效反馈和成功率。未使用数量只包含 reservation 中还没有开始的部分，异常时可以释放。

例如一次顺序 fallback 预留 3 次，前两个候选已经真实调用，第三个在调用前因为上游错误终止。系统应记账为实际消耗 2、成功视结果而定、退还 1。若第三个已经调用后报错，则三次都应计入消耗。取消整个 reservation 会把真实成本抹掉，反复触发即可突破硬预算。

共享 Project 预算还要跨 Case 生效。外层搜索调用内层训练时，不能让外层和每个内层分别拥有同样的局部上限。Budget Authority 应位于 L0，由父级生成或注入共享 token，子 Context 只获得收窄后的视图。这样“项目最多一万次评估”才是全局事实，而不是每个 Case 各一万次。

## 2.6 evaluation_count 的定义

`evaluation_count` 必须有唯一口径。建议把它定义为“已经实际发起并归属本次运行的候选评估数”，而不是“成功返回的目标数”。这与硬预算的成本语义一致，也避免失败评估免费。

批量 Provider 一次处理 N 个候选时，evaluation_count 增加 N，而不是增加 1；如果 Provider 明确把整个 batch 作为单次计费单元，则应使用另一个 provider_call_count 指标，不要混淆候选评估数。

异步执行中，计数应在 dispatch 事实确定时提交，或由 reservation ledger 原子转换为 started。成功数、失败数和取消数可以另记。这样 Controller、策略阶段和报告都能使用同一口径。

## 2.7 Controller 必须真正进入生命周期

注册 Controller 不等于控制逻辑已经执行。运行循环需要在约定时机调用 RuntimeController 的公共入口，并把返回动作映射为 Solver 行为。

共享 Controller 可以使用 `collect/resolve` 模型：collect 收集各控制域信号，resolve 按优先级和冲突规则产生动作。调用侧不能只尝试不存在的 `apply_slot/run_slot` 并静默跳过。预算 Controller 读取的 key 必须与 Context 实际 key 一致，例如 `evaluation_count`，不能一边写 `total_evaluations` 一边读另一个名字。

停止动作也要跨域归一。预算域产生 `{"stop": 1}`，与 stopping 域产生 stop，本质上都应映射到 `request_stop()`。如果只处理某一个域，预算已耗尽却仍不会停止。控制动作的最终应用位置应单一、可审计，并记录 controller、输入信号、解析结果和停止原因。

## 2.8 Adapter.update 后的权威状态

评估候选并不一定等于下一代种群。NSGA-II 会把父代和子代做环境选择，策略链可能切换阶段，局部搜索可能接受或拒绝候选，Trainer Adapter 可能直接产生新的 current_state。因此 Snapshot 不能默认保存“刚刚评估的 candidates”。

代级提交的正确语义是：Adapter.update 完成；通过标准接口读取 Adapter 权威 population/state；若 Adapter 没有提供，则按明确回退顺序读取 Solver/Trainer；验证数量、shape、对象类型和反馈对齐；写入 population snapshot；更新 latest snapshot handle；让后续 Context 引用最新 handle。

`_latest_snapshot_handle` 不能只在 `None` 时写入。第一次快照后，每一代都必须更新引用，否则所有后续 Context 会持续指向旧快照。快照 key 可以包含 generation 或版本，handle 则代表当前权威提交。

mlblack 也遵循同一规则。LearningSolver 在 nsgablack Adapter.update 之后读取 Adapter 的权威 population，而不是继续保存评估前状态；`get_population/set_population` 与 runtime state 合同由统一 AlgorithmAdapter 提供。

## 2.9 反馈与候选的语义对齐

Feedback 只有绑定到它实际评估的候选时才有效。数值向量相等不总能证明候选相同，因为 UnknownState.metadata 可能参与解码：同一组 values 在不同层结构、激活函数、条件分支或特征规格下可以代表不同模型。

ModelRepresentation 应提供稳定的 `fingerprint(state)` 和 `equivalent(a, b)`。默认 fingerprint 至少覆盖 values 与会影响 decode 的规范化 metadata。Adapter 更新产生新状态后，如果状态 identity 变化，就不能沿用旧 Feedback；若完全等价，可以安全对齐。

Fingerprint 还服务于缓存、去重、Artifact 血缘和回放。它不能依赖不稳定的 Python `repr`、字典插入顺序或进程地址。metadata 需要递归规范化，数组、序列、映射和标量采用稳定表示。

## 2.10 Snapshot、Context 与 Artifact 的三种时间尺度

Context 描述当前运行切片，适合 generation、step、evaluation_count、best 摘要、资源引用、snapshot key、artifact ref 等小字段。它更新频繁，要求轻量复制和可审计。

Snapshot 保存运行中的大状态，例如种群、objectives、violations、模型参数、优化器状态和历史片段。它支持 checkpoint、恢复、阶段传递和 replay，但通常仍归属于某次运行命名空间。

Artifact 是可复现交付物，时间尺度长于单次运行。它可以包含模型、规格、训练报告、数据血缘、指标、后端信息和关联 Snapshot。ArtifactRef 允许跨 Stage 或 Case 传递而不把对象本体塞入 Context。

通用 Snapshot payload 需要固定 envelope。写入时把 payload 包成共享字段，读取时解包，避免调用侧用动态 snapshot_key 再包一层导致 `{snapshot_key: payload}` 结构泄漏。安全 Redis serializer 对 UnknownState 等共享类型应使用正式 codec，序列化 `values + metadata` 并在读取时恢复对象，而不是只保存 type 和 repr。

## 2.11 Context 的大对象隔离

仅靠文档要求“不放大对象”不够，Context 构建和写回路径需要守卫。读取 ContextStore 后交给 Plugin 时，可以创建轻量副本；Plugin 返回后，治理层检查禁止字段和尺寸，再写回 Store。population、objectives、violations、history、trace、模型和大型数组应被剥离或转成 SnapshotRef。

大对象治理不能误伤必要的小型结构。判断应结合 key registry、对象类型和尺寸阈值，并允许正式引用类型。发生违规时，严格模式可以报错；宽松模式应记录审计事件并拒绝写入，而不是悄悄把大对象保存下来。

跨并行分支时，Context 还应复制或提供只读语义。把同一个可变 dict 传给多个线程会产生竞态，即使每个 Operator 只修改一个看似无关的 key。runtime handle 等少数共享对象可以保留，但必须通过受控 wrapper 和取消写栅栏访问。

## 2.12 插件生命周期与错误所有权

统一插件生命周期包括 solver init、population init、generation start、evaluate start、evaluate end、step、generation end、solver finish、error 和 context build。Manager 按优先级和明确执行顺序触发，严格模式决定插件异常是否中止主运行。

错误所有权应遵循“公共边界最多且至少分发一次”。底层评估函数可以附加 phase、candidate id、provider 等上下文后重新抛出，但不要同时触发 on_error；最外层公共入口负责分发。如果 `run()` 捕获到已经分发过的异常，通过 marker 识别并避免再次触发。

这一规则还要覆盖直接调用 `evaluate_population()` 的用户。若只有 run loop 负责 on_error，外部调用公共评估 API 会得到零次通知。把 error boundary 放到每个公共入口，并使用 dispatched marker，才能同时满足直接调用和完整运行。

错误事件应包含 phase、run id、generation/step、candidate identity、resource context 摘要和是否已消耗预算。恢复 Plugin 可以据此决定 checkpoint、重试或降级，但恢复动作本身也必须幂等，避免同一异常重复执行两三次。

## 2.13 Operator 调用不能靠捕获 TypeError 猜签名

Pipeline Operator 可能接受 `(value, context)`、`(value)` 或零参数。错误实现会依次调用三种形式，并在捕获 `TypeError` 后尝试下一种。但如果 Operator 确实接受两个参数，只是在函数体内部抛出 TypeError，框架就会误判为签名不匹配并再次执行。

对于写数据库、更新计数器或保存 Artifact 的 Operator，这会造成重复副作用，并掩盖真实堆栈。正确方式是使用 `inspect.signature(...).bind(...)` 或等价绑定判断，在执行前确定哪一种参数形式合法。只有绑定失败才能尝试下一种；函数体抛出的 TypeError 必须原样传播。

对于无法可靠 introspect 的可调用对象，应采用明确约定或注册时声明签名，不要用执行失败当作控制流。

## 2.14 并行 Pipeline 的确定性条件

parallel 模式不是把几个函数提交给 ThreadPoolExecutor 就完成了。它至少需要满足资源受控、输入隔离、Context 隔离、合并确定、错误可见、取消协作和晚写拒绝。

worker 数应读取有效 ResourceContext.threads，并允许注入 Project 的 PoolScheduler/executor；不能无参数创建默认线程池绕过 L0。每个分支得到独立 value 副本，尤其是 ndarray 可能被原地修改；Context 也应复制，只有明确的只读或 fenced runtime handles 可以共享。

merge policy 必须真正执行。`mean`、`sum`、`concat`、`first`、`last`、`list` 不能只存在于 spec；parallel 分支返回后，Kernel 根据 policy 合并并验证兼容 shape。自定义 merge 也应通过正式 registry，不允许在两个语义层分别加私有分支。

并行错误需要明确 partial result 语义。严格模式通常在任一分支失败时抛出包含 branch failure 的聚合异常；宽松模式可以保留成功分支，但报告必须说明缺失分支和 merge 降级。返回顺序应按 spec 顺序，而不是 future 完成顺序，以保证可复现。

## 2.15 timeout 是协作式取消

Python 正在运行的线程无法被 `future.cancel()` 强制终止。因此 timeout 只能表示主调度器停止等待，并发出取消信号。框架应设置共享 cancellation event，Operator 和 stage boundary 定期检查；parallel report 区分 cancelled、completed、failed 和 still_running。

更关键的是晚到写入。超时分支可能保留 ContextStore、SnapshotStore、Artifact writer 或外部 Session，主流程返回后继续写。Kernel 应为本次并行运行生成 run token/namespace，通过 fenced handle 检查 token 是否仍有效。超时、取消或 merge 完成关闭 token 后，迟到分支的写操作被拒绝并记录为 late write。

如果业务要求真正停止计算，应使用可终止进程、外部 Worker 或支持取消的远程后端。框架必须如实报告取消能力，不能把“停止等待”描述成“任务已停止”。

## 2.16 Trainer 的闭环

LearningSolver 复用 nsgablack 的单任务生命周期：setup、on_solver_init、step 循环、on_solver_finish、teardown 和 error boundary。`fit()` 是面向 ML 用户的结果投影，不建立第二套循环；标准 Case 的 `run()` 仍由同一 Solver 生命周期执行。

LearningSolver 的一轮就是标准 Solver 一轮：Adapter propose，Representation repair/decode，LearningProblem evaluate，Feedback bias 调整，Adapter update，权威状态提交，best 更新和 Plugin hook。资源 Context 变化时，ComputeBackendSession 必须原子同步或禁止后改；不能审计显示新授权而实际 Session 保持旧设备。

完整子 Trainer 组合由 BlackBase Case 协议承担：`CaseStageRunner` 为每个 Stage 创建 `CaseRunRequest`，派生 ResourceContext 与 cancellation lineage，注入 ArtifactRef，执行完整子生命周期，收集 `CaseRunResult`，并按声明策略选择输出。父 Case 自身的 init/finish/error/teardown 同样不能缺失。

结果策略可以是“最后成功阶段”“指定 output stage”或“显式聚合器”，但必须写入 Contract。父级 best_state、best_model、best_feedback 和 report 应采用这一策略，不能子阶段都成功而最终返回空字段。

## 2.17 运行闭环的验收问题

一次实现审查至少应回答：候选在何时验证；预算在何时预留和消费；Provider 部分失败怎样记账；evaluation_count 的唯一口径是什么；update_context 是否包含最新状态；Adapter 权威 population 怎样读取；Snapshot handle 是否每代更新；Plugin on_error 是否恰好一次；parallel worker 是否受 L0 授权；timeout 后晚写怎样拒绝；Result、Snapshot 和 Artifact 是否引用同一最终状态。

这些问题比“测试是否全绿”更接近运行正确性的本质。测试应当围绕它们构造反例，而不是只覆盖顺利执行的 happy path。

---

# 第三卷：工程可靠性与生产化

> 文档状态：规范。本章为白皮书原创主卷。

## 3.1 可靠性从“权威来源唯一”开始

复杂系统失真往往不是因为完全没有状态，而是因为同一事实有多个来源。线程数同时存在于 Project 配置、Case runtime、Solver 参数和 Backend Session；种群同时存在于 Solver、Adapter、Context 和 Snapshot；预算同时存在于外层 Solver、内层 Trainer 和任务队列；停止状态同时存在于 Controller、Plugin 和 run loop。

生产化的第一原则是为每类事实指定唯一权威来源。Project L0 是资源授权和共享预算的权威；Adapter 是算法更新后 population/state 的优先权威；Context 只是当前视图；Snapshot 是已提交状态；Artifact 是对外结果；Controller resolve 是控制动作的权威解析点。其他副本只能由权威来源投影，不能反向竞争。

当权威来源清楚以后，许多设计选择会自然收敛。例如，Backend Session 不应自行扩大设备范围，因为 ResourceContext 是授权；Snapshot 不应从评估前 candidates 构造，因为 Adapter 已经改变了状态；Dashboard 不应从零散日志猜测运行组件，因为 build-check 和 runtime report 可以给出权威装配清单。

## 3.2 ResourceContext 是授权，不是建议

ResourceContext 应表示“这个 Case 实际被允许使用的资源”，而不是用户期望。典型字段包括 threads、device_tokens、namespace、backend hint、budget 引用、lease 信息和父级 lineage。Case 可以读取并收窄它，但不能静默扩大。

子 Case 使用 `derive_child()` 获得资源视图。派生规则应满足单调收窄：子 threads 不超过父 threads；子 device token 是父集合的子集；子预算来自同一 Authority 且额度受限；namespace 继承父 run lineage 并增加子作用域。任何无法满足的 required capability 应 fail fast，而不是悄悄改用更多本地资源。

“声明资源”与“实际资源”必须同时可见。Project 配置可以声明希望使用 GPU，但 Backend Session 解析后可能因为设备不可用而回退 CPU。报告应同时记录 requested、granted、resolved 和 fallback reason。只有这样，性能差异和可复现性问题才有证据。

## 3.3 PoolScheduler 与本地并行

PoolScheduler 把线程或执行槽作为受控资源，而不是让组件随意创建 executor。Project L0 根据总量创建或注入池，Case 得到受限入口，Pipeline 或评估器按有效 threads 设置 worker 上限。

本地并行应避免嵌套超卖。外层 Project 并行运行四个 Case、每个 Case 又创建八线程，会从配置中的八线程膨胀到三十二甚至更多。资源派生需要把父级 fanout 与子级并行综合考虑；默认可以平均分配或按 requirement 分配，必要时保留一部分协调线程。

Pool 任务应携带 run id、case id、namespace、resource context 摘要和 cancellation token。返回结果不仅有 value，还应包含状态、耗时、异常信息和审计字段。调用侧不应只拿到裸 Future，否则很难把失败与资源事实关联。

## 3.4 Lease、heartbeat 与 fence

当资源跨进程或跨机器时，仅靠内存计数不够。Lease Store 记录资源授予者、持有者、有效期和版本；Worker 定期 heartbeat 续租；过期租约可以被回收。

但回收本身不能阻止旧 Worker 继续执行。网络分区后，旧 Worker 可能不知道租约已失效，而新 Worker 已获得同一资源。Fence 通过单调 token 或租约版本解决这个问题：每次写入 Context、Snapshot、Artifact 或任务结果时都验证当前 token。旧 token 即使持有有效连接，也会被拒绝。

`ResourceLeaseGuard` 可以在本地后台检查租约有效性，并在关键边界调用 `assert_current()`。这不是对所有副作用的魔法保护；外部数据库或对象存储仍需要把 fence token 传入其写协议，或使用带条件的版本写入。

## 3.5 TaskEnvelope、Transport 与外部 Worker

任务传输的目标不是把 Python 对象随便 pickle 到 Redis。正式 TaskEnvelope 应包含 task id、run/case/stage lineage、payload schema、resource requirement、budget token、deadline、attempt、idempotency key 和 trace context。Worker 返回 TaskResult，明确 success、failure、cancelled、timed_out 或 rejected。

队列至少需要可见性超时、ack/nack、重试上限、死信策略和幂等约束。Worker 领取任务后获得 lease；执行前再次检查 deadline 和预算；结果写入时验证 run token 与 lease fence。调度器不能仅凭队列消息消失就认定成功。

Redis 可以承载队列、Context 或 Snapshot，但三者命名空间和数据模型应分离。Context 是小键值，Snapshot 是版本化大 payload，Task Transport 是状态机。共用 Redis 实例不等于共用同一 key 结构。

安全序列化应默认禁止任意 pickle。JSON/MessagePack 等安全格式需要为 ndarray、UnknownState、Feedback、SnapshotHandle 等共享类型提供显式 codec。无法识别的对象应报错或保存受限描述，不能静默降级后仍声称可恢复。

## 3.6 Checkpoint、恢复与 Replay

Checkpoint 的完整性取决于状态边界。至少需要 Solver/Trainer 控制状态、Adapter state、权威 population、反馈/目标/约束、RNG state、Controller state、资源和后端摘要、Plugin 必要状态、版本和 schema。只保存 population 并不能保证恢复后行为一致。

Checkpoint 应在一致性点提交。一次 generation 中间保存，可能出现 population 已更新而 evaluation_count 未提交，或预算已消耗而 Snapshot 仍是旧版。更稳妥的方式是在 Adapter.update、权威状态 Snapshot 和代级 hook 之间定义原子提交顺序，并用 manifest 指向已完成的版本。

Replay 与恢复不同。恢复的目标是继续计算，Replay 的目标是解释过去发生了什么。Decision trace 应记录候选 identity、策略选择、评估输入摘要、反馈、控制动作、Snapshot ref、随机种子派生和外部结果引用。Replay 可以只读取事件并重建决策序列，也可以在受控模式重新执行并比较差异。

随机性需要层级化。Project 提供 root seed，Case、Stage、Adapter、Pipeline branch 和 Worker 使用稳定派生，而不是都共享一个全局 RNG。并行任务的 seed 应由逻辑身份派生，不依赖完成顺序。这样改变 worker 数不会自动改变随机序列语义。

## 3.7 ComputeBackendSession 的一致性

mlblack 的 ComputeBackendSession 负责把请求的后端、设备策略和 capability requirements 解析为实际执行环境。Session 创建以后，如果 Trainer 的 ResourceContext 被替换，Session 也必须重建或重新校验；否则审计与执行分叉。

一个可靠 setter 应以原子顺序处理：验证新授权；关闭或迁移旧 Session；按新 Context 构建 Session；解析所需 capability；更新 runtime context projection；失败时恢复旧状态或保持显式未就绪。更严格的设计可以禁止 setup 后更改 ResourceContext，让 builder 在构造时一次性注入。

Backend fallback 不能静默。若 request 是“GPU preferred”，回退 CPU 可以继续，但报告要记录；若 request 是“GPU required”，不可用时应 fail fast。Provider 或 Representation 可以通过 capability contract 声明 `supports_gradient`、`supports_sparse`、`supports_autodiff` 等要求，由 Session 统一验证。

## 3.8 Error Boundary、重试与幂等

错误处理不是“catch Exception 然后继续”。需要先分类：输入契约错误通常不可重试；瞬时网络错误可以按策略重试；预算不足和取消是控制状态；租约失效是 fence 拒绝；Operator 业务错误应保留原堆栈；插件 soft error 可以降级但必须记录。

重试只能在幂等边界内进行。纯评估函数容易重试，写 Artifact、提交外部任务或扣费 Provider 则需要 idempotency key。一次 attempt 的预算如何计算也要明确：如果外部调用已经发起，重试通常再次消耗预算，不能只按最终成功一次计数。

Error event 的结构化字段应包含异常类型、message、phase、attempt、candidate fingerprint、provider、resource context、budget ledger、snapshot ref 和 dispatched marker。日志字符串可以作为展示，但不能成为唯一机器可读证据。

## 3.9 可观测性不是把日志打满

运行可观测性应围绕因果链，而不是输出数量。至少需要 run、case、stage、generation/step、candidate、task、snapshot 和 artifact 的关联 id。Trace 可以跨 Project Runtime、Case、Solver/Trainer、Provider 和 Worker 传播。

关键指标包括：候选评估发起/成功/失败/取消数，预算已预留/已消耗/已退还，generation/step 耗时，Provider 延迟，parallel branch 状态，merge 降级，snapshot 写入与读取，lease 丢失，late write 拒绝，Backend fallback 和资源利用率。

Run Inspector 应从正式 runtime report、event store 和 Snapshot/Artifact manifest 读取，而不是依赖某个插件的私有内存。Dashboard 可以帮助浏览，但它是投影层；数据不一致时应回到权威运行事件和状态提交。

## 3.10 Doctor 的作用与边界

Doctor 是静态与构建期规则检查器。它可以检查 Project/Case 目录、规范入口、builder 签名、组件注册、Context 大对象风险、运行时资源声明、Catalog 条目和示例装配一致性。`--build-check` 可以实际构造 Case，验证配置不是空声明。

Doctor 不能替代运行测试。它无法仅靠扫描证明半批失败预算正确、线程超时不会晚写、Redis codec 能往返恢复 UnknownState 或 Adapter Snapshot 是更新后状态。因此 Doctor 输出要区分 structural pass、build pass 和 runtime verification。

Catalog 也只负责可发现性。`framework-core` profile 用于主干审计，排除 example/doc；`default` profile 用于完整浏览。组件被 Catalog 找到，仍需要 Contract、测试和真实装配证据。

## 3.11 版本、Schema 与迁移

Context key、Snapshot envelope、TaskEnvelope、Artifact schema 和 Case result payload 都应有版本。新增可选字段可以向后兼容；重命名或改变语义需要迁移器或版本分支。读取端应拒绝无法安全解释的未来版本，而不是尽力猜测。

兼容 forwarder 的目标是给旧 import path 迁移时间，不是永久维护双实现。权威实现应在 blackbase 或所属语义仓库；forwarder 只导入和适配，不继续增加新逻辑。迁移完成标准包括代码引用、模板、Doctor、文档和示例都指向新表面。

版本报告应记录三个包版本、工作树状态或 commit、schema 版本、Python 版本、可选依赖、Backend 版本和 Project manifest。对于未提交工作树，报告应明确 dirty，而不是生成看似可复现但无法回到同一源码的 Artifact。

## 3.12 生产拓扑建议

小型本地运行可以使用单 Project Runtime、内存 Context/Snapshot 和受控线程池。此模式部署简单，适合算法开发，但进程退出后状态消失，线程无法强制取消。

需要恢复的单机运行可以使用文件或 Redis Snapshot、持久事件和显式 Checkpoint。应测试进程中断、部分写入和 schema 升级。若 Redis 使用 safe serializer，需要覆盖所有共享协议类型往返测试。

多 Worker 运行需要 Task Transport、Lease Store、heartbeat、fence token、共享 Budget Authority 和 Artifact/Object Store。调度器只负责授权与状态机，Worker 负责执行正式 Case；不能让 Worker 自己扩大资源或创建新的全局预算。

Kubernetes、Ray 或云 Batch 等外部执行后端，应作为 blackbase Project/Transport 的 Provider，而不是把其 SDK 散落在 Solver/Trainer。外部系统的 Job ID、取消能力、重试和费用应进入统一审计。

## 3.13 发布前故障演练

生产发布前应主动构造故障，而不是只跑正常 benchmark。建议覆盖：批量评估第 N 个失败；Provider 返回错误 shape；预算只剩少于 batch 的额度；Adapter.update 后状态改变；Snapshot 后端临时不可用；Redis 安全序列化往返 UnknownState；Plugin 在不同 hook 报错；外部 Worker 租约过期；parallel 分支原地修改 ndarray；Operator 函数体抛 TypeError；timeout 分支晚到写；ResourceContext 更新但 Backend 不可用；子 Case 失败并检查 teardown 与结构化失败信封。

每个演练都要检查三类结果：运行是否按预期停止或降级；预算、状态和资源账本是否符合事实；报告能否解释发生了什么。仅断言抛出某个异常不足以证明闭环。

## 3.14 可靠性的最终标准

可靠框架不是“从不失败”，而是失败时不丢失事实、不扩大权限、不污染新状态、不重复副作用，并给出足够证据恢复或解释。它允许 Provider 超时、Worker 消失、插件降级和部分任务失败，但不允许这些事件被折叠成一个模糊的成功/失败布尔值。

当资源授权、预算记账、权威状态、取消边界和 Artifact 血缘都能对齐时，框架才具备承载长期复杂运行的基础。此后增加 Dashboard、Catalog 或更多算法才真正有价值，因为展示和发现的对象已经是可靠事实。

---

# 第四卷：从入门到进阶的学习路径

> 文档状态：规范。本章为白皮书原创主卷。

## 4.1 第一阶段：先跑通一个标准 Case

第一次使用时，不建议从复杂 Adapter 或分布式后端开始。先建立一个 Project，添加一个 Solver Case，只使用本地内存状态和单线程评估。目标是看清正式入口与生命周期，而不是追求算法效果。

典型流程如下：

```powershell
python -m nsgablack project new demo_project
Set-Location demo_project
python -m nsgablack project add-case sphere_search --type solver
python -m nsgablack project doctor --path . --build --strict
python run_project.py --check --build-check
python run_project.py
```

生成后先阅读 `project_config.py`、`run_project.py` 和 `cases/sphere_search/build_solver.py`。确认 Project 只负责跨 Case 编排与 L0，Case builder 负责组件装配，Problem、Pipeline、Adapter 和 Plugin 分别位于自己的目录。

最小 Problem 定义决策变量、边界、目标与约束。最小 Representation 能初始化、修复和解码候选。最小 Adapter 可以复用现有 NSGA2 或简单随机策略。第一次运行只挂一个观测 Plugin，打印 generation、evaluation_count 和 best 摘要。

验收时不要只看最终分数。检查 `--check` 是否识别 Case kind，`--build-check` 是否列出实际 adapter/providers/plugins，运行 summary 是否包含有效 ResourceContext、backend、namespace 和 snapshot 引用。

## 4.2 第二阶段：理解 Solver 四层边界

把同一个 Problem 分别交给两个 Adapter，验证 Problem 没有依赖算法内部字段。再把同一个 Adapter 与两个 Representation 组合，验证 Adapter 只通过候选协议工作。最后写一个 Plugin 观察 lifecycle，确认它不参与选择。

自定义 Adapter 的最小骨架是：

```python
class MyAdapter(AlgorithmAdapter):
    def propose(self, solver, context):
        # 读取轻量上下文和自身状态，返回候选序列。
        return candidates

    def update(self, solver, candidates, feedback, context):
        objectives, violations = feedback
        # 使用评估后的最新 context，更新 Adapter 权威状态。
        self.population = selected_population

    def get_population(self):
        return self.population
```

`propose()` 不应直接执行 Problem 评估；`update()` 不应写外部数据库；`get_population()` 应返回更新后的权威种群。若 Adapter 需要 checkpoint，再实现 `get_state()/set_state()`；若需要在 Context 中展示阶段、温度或策略权重，实现 runtime context projection。

Representation 的学习重点不是“怎样随机生成向量”，而是保持候选语义。对 permutation、graph、matrix 或混合变量，repair 必须保证基本合法性，fingerprint 必须稳定，decode 必须只依赖 state 和明确 Context。业务目标仍由 Problem 计算。

Bias 适合表达先验和软偏好。例如，在候选初始化时偏向某个区域，在排序时增加风险惩罚，或根据不确定性调节探索强度。硬约束仍应由 Problem/constraint violation 表达，不能仅靠 Bias“希望”候选可行。

## 4.3 第三阶段：完整理解评估链

为同一个 Case 分别测试四条路径：单候选 Problem 评估、种群批量评估、Plugin/Provider 短路、批量部分失败。记录每条路径的 objectives shape、violations shape、evaluation_count、预算账本、hook 次数和 snapshot。

如果引入批量 Provider，先写 Contract：输入候选 shape；输出 `N x M`；约束维度；是否逐候选触发 hooks；异常时返回部分结果还是整体失败；预算按候选还是 batch 计；是否支持 timeout/cancel。

评估错误测试应直接调用公共 `evaluate_individual()` 和 `evaluate_population()`，同时也通过 `run()` 触发。两种入口都应让 on_error 恰好一次。不要只测完整运行，因为用户和嵌套 Case 可能直接使用公共评估 API。

对硬预算，构造“预算剩余 2、请求 3 个候选”和“预留 3、第二个真实调用后失败”的用例。检查已经开始的评估不被退还，未开始部分才释放。若使用外部 Provider，还要检查 attempt 和幂等 key。

## 4.4 第四阶段：把状态迁移到 Snapshot

初始样例常把 population 放在对象字段中，这在单进程运行可以工作。下一步应接入 SnapshotStore，让 Context 只保存 handle/key。每代 Adapter.update 后提交权威 population，并验证 read-back 与 Adapter 当前状态一致。

首先使用 InMemorySnapshotStore，理解 envelope 与 handle。然后使用 File 或 Redis 后端，验证类型和 metadata 往返。对 UnknownState，读取后应仍是结构化对象或协议 payload，不能变成字符串。

Checkpoint 练习可以在第 K 代保存 Solver/Adapter/RNG/Controller 状态，重建新对象后继续运行。比较连续运行与恢复运行的事件序列、最终 fingerprint 和预算计数。若并行执行导致完成顺序不同，也应通过逻辑 seed 派生保持决策语义稳定。

## 4.5 第五阶段：掌握 Slot Kernel

Slot Kernel 用一个小型 spec 描述 Pipeline 内部编排。serial 适合可解释顺序变换；parallel 适合多个独立分支；router 根据 Context 选择一个分支。nsgablack 可以把 slot 映射到 init/mutate/repair/encode/decode，mlblack 可以映射到 fit/transform 或特征/模型分支。

一个并行 slot 的概念配置如下：

```python
pipeline_spec = {
    "slots": {
        "mutate": {
            "mode": "parallel",
            "operators": ["gaussian", "levy", "structure_prior"],
            "merge": "concat",
            "timeout_seconds": 5.0,
        }
    }
}
```

注册表把名称映射到 Operator。运行时从 ResourceContext 得到 worker 上限，为每个分支复制输入和可变 Context，按 spec 顺序收集，再执行 merge。Operator 内部应检查 cancellation event；任何写 Snapshot/Artifact 的句柄都通过 run fence。

学习时先实现 serial，再改 parallel，最后增加 router。每一步都固定输入和 root seed，比较输出与事件报告。若 parallel 结果不稳定，优先检查原地修改、共享 Context、完成顺序和 RNG，而不是直接增加锁。

## 4.6 第六阶段：进入 mlblack 单 Trainer

机器学习入门从 NumericDataView 和一个线性点预测任务开始。通过 `build_trainer()` 选择 preset，运行 `fit()` 并读取 TrainerResult。然后依次替换 Representation、Head 和 Problem，观察哪些语义发生变化。

```python
import numpy as np

from mlblack.assembly import build_trainer
from mlblack.pipeline.data_views import train_valid_split

X = np.linspace(-1, 1, 64).reshape(-1, 1)
y = 1.5 + 2.0 * X[:, 0]
data = train_valid_split(X, y, feature_names=("x0",))

trainer = build_trainer(
    {
        "preset": "orthogonal_linear_point",
        "run_name": "linear_demo",
        "params": {"learning_rate": 0.05},
    },
    data=data,
)
result = trainer.fit(max_steps=50)
print(result.report["best_score"])
```

下一步检查 UnknownState：values 是可优化数值，metadata 保存结构或解码条件。修改 metadata 后，`fingerprint()` 应改变。再检查 Feedback：objectives 是优化信号，metrics 是解释信号，constraints 表达不可违反的条件，residuals/gradients 提供特定 Adapter 能力。

ComputeBackendSession 练习应分别声明 CPU preferred、GPU preferred 和 GPU required，观察 requested/granted/resolved。不要把本机 CUDA 序号硬编码到 Case；使用 Project resource token 映射。

## 4.7 第七阶段：模型组合与 Artifact

复杂模型不是把多个 estimator 塞进一个 list。组合前先定义 PredictionInputSpec 和 PredictionOutputSpec，明确每个组件消费什么 shape、返回点预测/概率/区间还是 embedding，以及融合方式允许什么语义。

典型模式包括：主模型 + 同输入残差模型，不同输入的多模态 late fusion，stacking，boosting-like 多轮残差，专家路由和结构条件 Head。每个阶段应产生 ArtifactRef，后续 Stage 通过正式注入读取，而不是把 fitted model 放进 Context。

单个 ML Case 内共享生命周期的顺序步骤使用 Trainer phase 或 DataPipeline。多个可独立运行的模型比较、超参搜索或跨数据任务应拆成多个 Case，由 Project/`CaseStageRunner` 编排。判断标准不是文件数量，而是每个单元是否具有独立生命周期、资源需求和 Artifact。

## 4.8 第八阶段：跨框架嵌套

跨框架最常见结构是外层 nsgablack 搜索模型结构或超参数，内层 mlblack Trainer 拟合并返回指标。外层候选通过 component overrides 转成内层 Spec；Project L0 派生 ResourceContext 和预算；内层返回 Feedback、ArtifactRef 和 audit payload；外层 Problem 将其映射为 objectives/violations。

伪代码如下：

```python
def evaluate_outer_candidate(candidate, context):
    request = {
        "component_overrides": decode_search_state(candidate),
        "resource_context": context["resource_context"].derive_child(
            namespace="inner_fit"
        ),
        "artifact_inputs": context.get("artifact_refs", {}),
    }
    result = run_inner_case(request)
    return {
        "objectives": [result.metrics["rmse"], result.metrics["complexity"]],
        "violations": [result.metrics.get("constraint_violation", 0.0)],
        "artifact_refs": result.artifact_refs,
    }
```

真正实现时应使用标准 Case request/result 类型，而不是直接调用私有 `trainer._something`。内层失败要明确是否消耗外层评估预算，Artifact 写入要带父 run lineage，取消事件要跨边界传播。

## 4.9 第九阶段：复杂编排

在掌握单 Case 后，再组合多 Case Project。常见模式包括串行数据准备 -> 训练 -> 评估，多个算法并行 benchmark，外层搜索 -> 内层训练，符号基础搜索 -> 条件任务表达式搜索，以及多个资源异构 Lane 的协作。

Project 配置负责阶段与资源，不把算法内部循环写进去。每个 Case 保持独立 build-check；Artifact/Snapshot refs 是依赖边；ResourceContext 是授权边；Result payload 是语义边。这样复杂项目可以画成清晰 DAG，也能单独重放失败 Case。

并行多 Case 时先计算资源扇出。例如总 threads=16，四个 Case 并行，每个最多 4；若每个 Case 内还有 parallel slot，应从 4 中继续分配，而不是再次开 4。GPU token 通常独占或按明确共享策略分配，不能只靠环境变量竞争。

## 4.10 第十阶段：生产化验收

生产化前执行三层验收。第一层是静态规则：Doctor strict、规范入口、Context/Snapshot 规则、Catalog `framework-core` 口径。第二层是构建检查：每个 Case builder 能构造，实际组件和有效资源能输出。第三层是运行契约：评估、预算、快照、并行、取消、恢复和错误演练。

建议为每个正式 Case 维护一个最小验证矩阵：单点评估、批量评估、Provider 短路、Snapshot 往返、checkpoint 恢复、固定 seed、资源收窄、错误一次分发。含 parallel 的 Case 增加输入隔离、merge、timeout、late write；含外部 Worker 的 Case 增加 lease、重试和幂等。

发布的 Run Artifact 至少包含：Project/Case manifest，实际装配组件，版本和 dirty 状态，root seed 与派生策略，有效 ResourceContext，Backend requested/resolved，预算账本，最终 SnapshotRef，模型或结果 ArtifactRef，关键指标和错误/降级事件。

## 4.11 组件开发清单

新增组件前先归属。共享运行能力放 blackbase；搜索策略放 nsgablack Adapter；模型语义放 mlblack；外部系统放 Provider/Bridge。再定义 Contract：输入、输出、Context requires/provides/mutates、资源需求、错误、状态与序列化。

实现后检查生命周期：谁 setup，谁 teardown；失败时是否 finally；是否能 checkpoint；是否需要 fingerprint；是否产生大对象；是否有外部副作用；重试是否幂等；取消是否协作；审计投影包含什么。

最后把组件接入正式 scaffold、Doctor 和 Catalog。Catalog 只做发现，README 的组件表必须与 build-check 实际装配一致，禁止示例声称使用某组件但 builder 没有挂载。

## 4.12 推荐的进阶专题顺序

完成以上路线后，可以按兴趣进入专题。算法方向可深入多目标环境选择、策略链、代理辅助、多保真、信赖域与图搜索；ML 方向可深入 NeuralGraph、条件模型、概率/区间 Head、时序、符号表达式与多阶段残差；运行方向可深入 Redis Snapshot、外部 Worker、Lease/Fence、分布式预算和 OpenTelemetry；工程方向可深入 schema 演进、Artifact lineage、回放与故障注入。

无论走哪条路线，都应回到同一个问题：新增复杂性是否通过已有正式协议组合出来，还是偷偷创建了第二套运行逻辑。前者会增强框架，后者只会增加下一个需要收口的遗留系统。

---

# 第五卷：实现锚点与协议索引

> 文档状态：实现。本章为白皮书原创主卷。

## 5.1 怎样使用这一卷

这一卷不是完整 API 文档，而是阅读源码的入口图。路径以三个仓库根目录为基准。公共契约优先阅读类型、抽象类和 builder，再进入具体实现；不要从某个 example 反推框架语义。

当前三个仓库均处于活跃演进且工作树可能包含未提交改动。路径和方法代表本白皮书生成时的实现锚点，未来重构时应同步更新 manifest 与本索引。

## 5.2 blackbase：Project Runtime

`blackbase/src/blackbase/project/runtime.py` 是标准 Case 装配和 L0 运行时的重要入口。重点类型与函数包括：

- `ProjectRuntimeConfig`：加载 Project 级运行配置。
- `ProjectL0Runtime`：管理 Case 资源授权、租约与有效 ResourceContext。
- `ResourceLeaseGuard`：检查租约是否仍是当前版本。
- `load_case_builder()`：解析标准 `build_solver.py` 入口。
- `load_case_kind()`：读取 `.case` 的 solver/trainer 语义。
- `load_case_resource_request()`：读取 Case requirement。
- `build_case()`：向 builder 注入 ResourceContext 与 component overrides。
- `run_case()`：按 Case kind 选择标准运行方法。

`blackbase/src/blackbase/project/project_runner.py` 负责 Project 入口；`execution.py`、`case_execution.py` 负责阶段和 Case 执行；`external_worker.py` 负责外部 Worker；`run_manifest.py` 负责运行清单与恢复事实。

阅读顺序建议为：`runtime.py` 的配置与资源 -> `project_runner.py` 的入口 -> `execution.py` 的 stage policy -> `case_execution.py` 的单 Case 生命周期 -> `run_manifest.py` 的结果提交。

## 5.3 blackbase：资源、预算、租约与传输

`blackbase/src/blackbase/resources/context.py` 定义 `ResourceContext`、`derive_child()` 和资源审计。任何 Case 内部资源使用都应能追溯到这里的有效授权。

`resources/budget.py` 定义共享预算 Authority 与 reservation 语义。审查评估预算时，应沿 Solver/Trainer 评估入口追踪到共享 Authority，确认 started/consumed/released 的事实没有被局部计数替代。

`resources/pool.py` 提供 `PoolScheduler` 与任务结果。Pipeline parallel 和并行评估应注入或使用受控 Pool，而不是无参数创建线程池。

`resources/lease_store.py` 提供内存、SQLite 或 Redis 等租约后端与 fencing。`resources/transport.py` 提供 TaskEnvelope、TaskResult 和 TaskTransport。多机执行时，任务 lease 与 Project resource lease 是不同职责，两者不能混用。

## 5.4 blackbase：Context 与 Snapshot

`blackbase/src/blackbase/context/context_keys.py` 是规范 key 注册表；`context_contracts.py` 描述组件需要、提供和修改的字段；`context_field_governance.py` 负责字段治理；`context_store.py` 提供存储后端。

`snapshot_store.py` 定义 `SnapshotHandle`、`SnapshotRecord`、`SnapshotStore` 以及内存、文件、Redis 实现。重点检查：

- `wrap_snapshot_payload()` 与 `unwrap_snapshot_payload()` 是否保持通用 payload 单层语义；
- safe serializer 是否为 ndarray、UnknownState 等协议类型提供正式 codec；
- TTL、key namespace 和 read-after-write 是否一致；
- Redis 错误在 strict/soft 模式下怎样暴露；
- Snapshot 版本和 run lineage 是否进入 handle。

## 5.5 blackbase：Pipeline Kernel

`blackbase/src/blackbase/kernel/spec.py` 定义 `PipelineSlotSpec` 与 `PipelineSpec`。Slot 的主要字段是 mode、operators、router、merge、timeout 与 method 映射。

`kernel/orchestrator.py` 定义 `PipelineOrchestrator`。关键路径包括：

- `_run_serial()`：按声明顺序执行；
- `_run_parallel()`：分支调度、资源上限、输入/Context 隔离和超时；
- `_merge_parallel_results()`：mean/sum/concat/first/last/list 等合并；
- `_run_router()`：根据 Context 选择 Operator；
- `_invoke_operator_callable()`：在执行前绑定签名，避免 TypeError 重复执行；
- `_PipelineRunControl` 与 `_CancellationFencedHandle`：协作取消和晚写拒绝；
- `build_pipeline_kernel()`：把 spec 与 registry 组合为正式 Kernel。

并行正确性审查应同时看 spec、orchestrator 和调用侧传入的 ResourceContext/Pool，不能只看 `_run_parallel()` 内部。

## 5.6 blackbase：统一 Plugin 与共享 Types

`blackbase/src/blackbase/plugin/base.py` 定义 `PluginBase` 和 `PluginManager`。十个主要钩子是 `on_solver_init`、`on_population_init`、`on_generation_start`、`on_evaluate_start`、`on_evaluate_end`、`on_step`、`on_generation_end`、`on_solver_finish`、`on_error`、`on_context_build`。

`blackbase/src/blackbase/types.py` 定义跨层协议：

- `UnknownState`：数值 values 与语义 metadata；
- `Feedback`：目标、约束及附加学习信号；
- `PopulationSnapshot`：候选、反馈与代级元数据；
- `TrainerResult`：训练控制平面的标准结果。

共享类型的序列化应使用 `to_protocol_payload()/from_protocol_payload()` 或等价正式方法，不依赖任意对象 pickle。

## 5.7 nsgablack：Solver 主干

`nsgablack/core/blank_solver.py` 中的 `SolverBase` 是生命周期、公共评估入口、Context/Snapshot、Plugin、RNG 和停止控制的基础。文件较大时应结合 `core/solver_helpers/` 阅读，不要只按类体顺序浏览。

`core/composable_solver.py` 的 `ComposableSolver` 引入 Adapter propose/update。重点检查 `step()`：propose_context、评估、update_context、Adapter 权威 population 和 Snapshot 提交的顺序。

`core/evolution_solver.py` 的 `EvolutionSolver` 提供进化范式默认实现、并行评估、环境选择、Pareto 和 history。它应与 Adapter 同步，而不是形成第二套互相竞争的种群状态。

`core/control_plane.py` 定义 RuntimeController 与控制域解析；`core/controllers.py` 包含预算、耐心或策略控制器。`core/solver_helpers/run_helpers.py` 负责把 controller 解析结果应用到停止请求和运行循环。

## 5.8 nsgablack：评估与快照 Helpers

`core/solver_helpers/evaluation_helpers.py` 是高风险文件。审查点包括候选维度、目标/约束 shape、Provider 短路、批量计数、预算 reservation、部分失败、hook 和 error marker。

`core/solver_helpers/snapshot_helpers.py` 负责 resolve/commit population snapshot。写入前必须读取 Adapter 更新后的权威状态。`context_helpers.py` 构建轻量 Context 并执行大对象治理。`store_helpers.py` 处理 Store 注入与访问。

`candidate_helpers.py` 与 Representation 交互；`bias_helpers.py` 应用软引导；`result_helpers.py` 构造运行输出；`control_plane_helpers.py` 连接 Controller。Helper 的划分是为了降低 SolverBase 体积，但公共语义仍由 Solver 生命周期统一拥有。

## 5.9 nsgablack：Adapter、Representation、Bias、Plugin

`adapters/algorithm_adapter.py` 定义 Adapter 抽象与推荐状态接口。具体算法位于 `adapters/<algorithm>/adapter.py`。新增算法时先实现最小 propose/update，再实现 population、state 和 context projection。

`representation/base.py` 定义 Representation 基础；`representation/orchestrator.py` 与 `representation/pipeline_kernel.py` 连接共享 Slot Kernel；continuous、integer、binary、permutation、graph、matrix 等模块提供不同候选语义。

`bias/core/base.py`、`bias/core/manager.py` 和 `bias/facade.py` 是 Bias 主入口。algorithmic、domain、surrogate 是不同来源的软引导，不应替代 Problem 约束。

`plugins/base.py` 应主要作为共享 Plugin 的重导出/适配面；具体能力位于 runtime、evaluation、ops、storage、system 和 domain_backends。外部求解器或仿真器优先通过 `plugins/domain_backends/` 的正式契约接入。

## 5.10 mlblack：Trainer 主干

`mlblack/integrations/nsgablack_control.py` 定义 `LearningSolver`。它将 ModelRepresentation、LearningProblem、ComputeBackendSession 与 TrainerResult 投影到 nsgablack `ComposableSolver`，不再定义 ML 私有控制平面。

`blackbase.project.case_stages` 定义公共 `CaseStageRunner` 与 Stage 执行协议；`blackbase.project.invocation` 关闭父子 identity、ResourceContext、预算、取消、Artifact 注入和结构化结果。审查重点是完整生命周期、finally teardown、阶段结果收集，以及失败与输出均不绕过 `CaseRunResult`。

优化策略统一由 `nsgablack.adapters.AlgorithmAdapter` 定义；`core/problem.py` 定义 LearningProblem；`core/representation.py` 定义 ModelRepresentation、fingerprint 与 equivalent；`core/backend_session.py` 定义 ComputeBackendSpec/Session。

## 5.11 mlblack：数据、模型与产物

`mlblack/pipeline/` 提供 DataPipeline、DataView、数据源、numericizer、特征空间、条件组合、时序和符号 Pipeline。`pipeline/slot_kernel.py` 把共享 blackbase Kernel 映射到 ML 组件。

`representations/codecs/` 负责模型状态编码；`representations/heads/` 负责点、区间、概率、分布、条件与符号输出；`representations/neural_graph.py` 提供 NeuralGraph 模型规格到 UnknownState 的表示。

`core/artifacts.py` 定义 ModelArtifact、TrainerStateArtifact、RunReport、ArtifactBundle 和 ArtifactBuilder。Artifact 保存可复现语义，不应成为运行 Context 的大对象容器。

`assembly/builders.py` 的 `build_trainer()` 是配置到正式 Trainer 的装配入口。Case 层仍以 `build_solver.py` 为规范入口，再由其调用 mlblack assembly。

## 5.12 跨框架集成锚点

显式 nsgablack 集成位于 `mlblack/integrations/`，避免让 mlblack core 反向依赖优化层。`integrations/nsgablack_symbolic/` 包含符号基础搜索、任务表达式搜索、Artifact、缓存、路径记忆和回放；`integrations/nsgablack_neural/` 包含神经结构搜索桥接。

外层 nsgablack Problem 应只依赖集成层公开 builder/request/result，不读取 Trainer 私有字段。资源通过 ResourceContext，模型通过 ArtifactRef，候选覆写通过 component overrides，指标通过 Feedback/result payload。

## 5.13 变更时应同步检查的表面

改变公共运行规则时，至少同步检查五个表面：权威实现、旧路径 forwarder、Project/Case 模板、Doctor 规则、文档与示例。若改变 Catalog 发现口径，再检查 default 与 framework-core 两个 profile。

改变评估链时，至少验证单候选、批量、Provider 短路、部分失败和 Snapshot。改变并行 Kernel 时，至少验证 serial 不回归、parallel merge、资源上限、输入隔离、取消、late write 和 Operator TypeError。改变 Trainer 生命周期时，至少验证 `fit()`、`run()`、子阶段错误和最终 Result。

---

# 架构思想：为什么必须解耦

> 文档状态：说明；来源：`nsgablack/docs/concepts/FRAMEWORK_PHILOSOPHY.md`。本节按当前工作树合订；如与原创主卷或实时源码冲突，以原创主卷标注的规范和实时源码为准。

一句话定位：NSGABlack 是统一框架栈里的优化搜索语义层，是一个“基于算法解构的可重组优化系统”。

当前第一原则：

- `nsgablack` 与 `mlblack` 共享 Project / Case / Scaffold / L0 substrate。
- `nsgablack` 负责 Solver / Adapter / Representation / Bias / Plugin / Pareto 等优化搜索语义。
- `mlblack` 负责 Trainer / DataView / Spec / Codec / Head / Artifact 等机器学习语义。
- 编排、资源授权、嵌套 Case 调用属于 substrate，不属于任一语义层的私有能力。

这里的“算法解构”不是指强行规定拆法，而是提供足够通用的扩展点，让同一算法可以从不同维度被拆开、复用、再拼装：
- 表示与算子维度：`RepresentationPipeline`（编码/初始化/变异/修复/解码）
- 偏好与软约束维度：`BiasModule` / `UniversalBiasManager`（奖励/惩罚/阶段调度/搜索倾向）
- 搜索策略维度：`AlgorithmAdapter` / `CompositeAdapter`（propose/update）
- 横切能力维度：`Plugin` / `PluginManager`（日志、早停、短路评估、checkpoint、实验追踪等）
- 编排与资源维度：Project / Case / L0 substrate（stage、group、fanout、ResourceContext、nested Case）

## 愿景

- 任何优化算法都能接入，且接入成本低。
- 算法之间可以轻松融合，支持“组合式”构建。
- 一次实现、多处复用，避免为每个新算法重写基础设施。

## 设计原则

1. 解耦：问题定义、流程控制、表示编码、策略偏好、辅助能力相互独立。
2. 可选：偏置、管线、插件都是可选模块，不强制绑定到某种算法。
3. 可组合：多个偏置、多个适配器、多个插件可以组合工作。
4. 可迁移：旧结构可以保留兼容入口，但正式入口收敛到 Project / Case / Scaffold。
5. 可编排：多 solver、多 trainer、嵌套评估和资源授权由 substrate 表达，而不是塞进某个算法层。

## 分层结构

### 1) 问题层（Problem）
- 统一入口：`BlackBoxProblem`。
- `evaluate()` 为必须实现。
- `evaluate_constraints()` 可选；硬约束更推荐放在管线修复，软约束放偏置。

### 2) 求解器层（Solver Bases）
- 标准求解器：`EvolutionSolver`（固定流程）。
- 空白底座：`SolverBase`（不提供流程，完全由插件/子类实现）。
- 可组合求解器：`ComposableSolver`（流程由 Adapter 驱动，评估/调度由底座统一处理）。

### 3) 表示层（Representation Pipeline）
- 负责编码/初始化/变异/修复/解码。
- 特别适合承载硬约束与可行解构造。

### 4) 偏置层（Bias System）
- 表达软约束与搜索倾向（奖励/惩罚/偏好）。
- 适合表达“方向性策略”，不适合接管“硬流程”。

### 5) 插件层（Plugins）
- 负责流程外能力：日志、监控、早停、短路评估、checkpoint、report、backend 接入。
- 插件可以观察和增强生命周期，但不拥有跨 Case 编排和全局资源授权。

### 6) 算法适配层（Algorithm Adapter）
- 只处理“提出候选 + 消化反馈”。
- 让算法逻辑模块化，便于复用、组合、对比。

### 7) 共享 substrate（Project / Case / Scaffold / L0）
- Project 负责跨 Case 顺序、并行、资源池和正式入口。
- Case 是一个独立 Solver / Trainer / evaluator scaffold。
- L0 发放 `ResourceContext`，Case 只消费 grant 和输出 audit。

## 典型工作流程

1. 定义问题（`BlackBoxProblem`）。
2. 选择底座：
   - 固定流程：`EvolutionSolver`
   - 特殊流程：`SolverBase`
   - 可组合算法：`ComposableSolver`
3. 装配模块：
   - 表示管线（编码/初始化/修复）
   - 偏置系统（软约束/方向性引导）
   - 插件（日志、调度、早停、阶段切换）
4. 在 Project 层声明 stages/groups/L0 resource grant。
5. 运行并收集结果。

## “该放在哪里”的选择指南

- 编码/操作算子 → 表示管线
- 硬约束/可行化 → 管线修复或流程拒绝
- 软约束/偏好 → 偏置
- Case 内搜索流程控制（接受准则/阶段切换） → Adapter 或插件
- 跨 Case 编排和资源授权 → Project / L0 substrate
- 可复用算法逻辑 → Adapter
- 一次性特殊流程 → SolverBase + 插件

## 为什么这样设计

- 可复用性更强：算法逻辑、编码、约束、策略可以分别复用。
- 融合更容易：组合适配器可以把多个算法并行/串联融合。
- 协作更清晰：每个模块专注做一件事，减少相互污染。

## 约束策略建议

- 硬约束：优先在管线修复或流程拒绝。
- 软约束：放偏置，支持权重与阶段调度。
- 混合约束：硬约束先保证可行，再用偏置做优化倾向。

## 复用与融合

- 偏置复用：同一偏置可跨算法共享。
- 管线复用：同一编码/修复可跨算法共享。
- 算法复用：Adapter 作为可复用模块，可组合为新算法。

## 取舍

- 解耦与可组合提高了复用能力，但理解成本更高。
- 适配器和插件提供了两条路线：
  - 简单直观 → SolverBase + 插件
  - 工程化复用 → ComposableSolver + Adapter

---

# 概念映射：从问题到运行表面

> 文档状态：说明；来源：`nsgablack/docs/concepts/FRAMEWORK_CONCEPT_MAPPING.zh-CN.md`。本节按当前工作树合订；如与原创主卷或实时源码冲突，以原创主卷标注的规范和实时源码为准。

状态：工作草案  
用途：把框架内部命名翻译成机器学习、优化、AutoML、符号学习和实验工程社区更常用的表达。  
边界：本文不替代 API 文档；它用于对外叙事、论文/报告写作、答辩介绍和后续 benchmark 设计。

## 1. 总体定位

| 你的框架叫法 | 社区常用叫法 | 你的差异点 |
| --- | --- | --- |
| `nsgablack` | black-box optimization framework / multi-objective optimization framework / algorithm configuration framework | 不只是 NSGA 算法库，而是把外层搜索、候选表示、评估链、插件能力、运行记录和项目脚手架统一起来。 |
| `mlblack` | surrogate modeling framework / ML workflow framework / model assembly framework | 不只是训练模型，而是把 schema、numericizer、pipeline、trainer、artifact、audit 和 report 统一为可装配训练流。 |
| `nsgablack -> mlblack` | prediction-decision integration / model-based optimization / learning-augmented optimization / AutoML for inner evaluators | 外层优化搜索决策、结构、预算和配置；内层学习框架执行拟合、代理评估、符号发现和证据产出。 |
| Outer solver / inner evaluation | bilevel optimization / nested optimization / algorithm configuration / hyperparameter optimization | 内层不一定是简单目标函数，可以是完整训练流、符号搜索流或多阶段实验。 |
| 标准脚手架 surface | reproducible experiment surface / application scaffold / workflow entrypoint | 把“跑了哪个入口、挂了哪些组件、产出了什么 artifact”变成可审计记录。 |

## 2. nsgablack 优化侧

| 你的框架叫法 | 社区常用叫法 | 你的差异点 |
| --- | --- | --- |
| `Solver` | optimization loop / control plane / search orchestrator | 控制生命周期、评估入口、状态管理和插件调度，不把具体算法策略写死。 |
| `Adapter` | search policy / optimizer strategy / algorithm operator | 通过 `propose/update` 解耦搜索策略，可挂 NSGA2、MOEA/D、SPEA2、DE、SA、VNS 等。 |
| `RepresentationPipeline` | encoding/decoding pipeline / genotype-phenotype mapping / repair operator | 候选表示、修复、编码和解码独立于 solver 与 adapter。 |
| `Plugin` | callback / middleware / capability extension / lifecycle hook | 日志、checkpoint、短路评估、runtime 观测、backend 接入都作为能力层挂载。 |
| `Bias` | inductive bias / prior / heuristic guidance / soft constraint | 不是硬约束替代，而是对搜索过程的软引导。 |
| `evaluate_individual` | single-candidate evaluation | 单点评估入口，可被插件或内层 runtime 接管。 |
| `evaluate_population` | batch evaluation / vectorized evaluation | 批量评估入口，强调返回 shape 与候选数量对齐。 |
| `ContextStore` | runtime context / lightweight state store | 存轻量状态、引用、指标和控制信息。 |
| `SnapshotStore` | artifact store / state snapshot / large-object store | population、objectives、trace 等大对象走 snapshot 引用，避免污染 context。 |
| `context_keys` | state schema / typed runtime keys | 用集中 key 管理运行状态，减少隐式字段和字符串漂移。 |
| `context_contracts` | component IO contract / data contract / lifecycle contract | 声明组件需要、提供、修改和缓存哪些上下文字段。 |
| `Catalog` | component registry / discoverability index / model card index | 组件可发现、可筛选，并区分 `default` 与 `framework-core` 口径。 |
| `Project Doctor` | static checker / project health check / lint for framework contracts | 检查脚手架、契约、目录边界和项目健康状态。 |
| `Run Inspector` | experiment inspector / run audit tool | 面向运行记录、上下文、组件装配和 artifact 的诊断入口。 |
| `TaskInnerRuntimeEvaluator` | nested evaluator / inner solver bridge / evaluation backend adapter | 将外层候选映射为内层任务，并把内层结果投影回外层目标。 |
| `Runtime surface tracker` | experiment lineage tracker / run registry | 记录 surface、assembly、run、artifact，使跨框架运行可对比。 |

## 3. mlblack 学习侧

| 你的框架叫法 | 社区常用叫法 | 你的差异点 |
| --- | --- | --- |
| `TrainFlowSpec` | training workflow spec / experiment config | 用声明式 spec 组织数据、模型、能力和输出。 |
| `run_train_flow` | training pipeline runner / fit-evaluate-persist workflow | 不只 fit，而是包含数据准备、训练、评估、持久化和报告。 |
| `SemanticTrainFlowSpec` | schema-aware training workflow / semantic ML pipeline | 从语义 schema 进入 numericizer，再到 pipeline 和 trainer。 |
| `Numericizer` | feature encoder / tabular encoder / semantic-to-numeric transform | 把语义字段转成模型可用数值表示，是 schema 与模型之间的正式边界。 |
| `Pipeline` | preprocessing pipeline / feature transformation pipeline | 类似 sklearn pipeline，但作为框架装配层的一部分。 |
| `Trainer` | estimator / learner / model family implementation | ridge、xgboost、torch MLP、symbolic trainer 等作为可注册训练器。 |
| `Artifact` | trained model artifact / deployable model object / fitted estimator | 统一 predict、uncertainty、validity、save/load 与 metadata。 |
| `FlowCapability` | callback / plugin / training capability | 生命周期能力，如 checkpoint、resource、report、experiment tracker。 |
| `LifecycleRuntime` | hook dispatcher / workflow lifecycle engine | 管理 flow/stage 事件、capability 调度和 lifecycle report。 |
| `ExperimentOrchestrator` | staged workflow orchestrator / experiment runner | 把实验拆成多个 stage，并记录 stage payload 与 lifecycle report。 |
| `ContextStore + SnapshotStore` | ML runtime state plane / experiment state backend | 和 nsgablack 对齐的状态面，支持 memory/sqlite/redis 等后端。 |
| `ModelSpec` | model subspace spec / target-feature view | 指定某个模型使用哪些 feature 和 target 子空间。 |
| `Experiment tracker` | ML experiment tracking / metric store | 记录 run、event、metric、artifact，类似轻量 MLflow/W&B 思路。 |
| `Report writer` | experiment reporter / artifact summarizer | 将训练结果、指标和配置投影为可读报告。 |

## 4. 符号学习与结构发现

| 你的框架叫法 | 社区常用叫法 | 你的差异点 |
| --- | --- | --- |
| `symbolic_stagewise` | stagewise symbolic regression / greedy symbolic model building | 分阶段增加 symbolic terms，强调预算、beam 和结构控制。 |
| `orthogonal basis search` | basis function discovery / sparse symbolic regression / dictionary learning | 关注相对正交、残差解释能力和 basis 组合。 |
| `basis consensus` | ensemble model selection / stability selection / consensus clustering | 从多次 symbolic run 中寻找稳定 core basis。 |
| `locked core` | fixed support refinement / warm-start with selected structure | 将稳定 basis 固定或注入后续 refinement，减少搜索漂移。 |
| `exact term recovery` | symbolic recovery accuracy / ground-truth structure recovery | 用于已知真值 benchmark，评估是否找回真实表达式项。 |
| `family-level recovery` | semantic family recovery / equivalence-class recovery | 不只看字符串等价，也看函数族或语义层面的恢复。 |
| `phase-equivalent recovery` | equivalence-aware symbolic matching | 处理周期、相位、等价表达式导致的“形式不同但意义接近”。 |
| `residual-guided search` | residual fitting / boosting-like symbolic search | 用当前模型解释不了的残差来引导下一批结构候选。 |
| `path memory` | search memory / tabu memory / prior over structures | 把历史搜索路径、候选和效果变成下一轮搜索的先验。 |
| `semantic novelty` | diversity regularization / novelty search / anti-redundancy | 候选不仅要拟合目标，也要避免语义重复。 |
| `SymbolicOuterEvaluationProxy` | black-box evaluator for symbolic candidates / surrogate evaluation protocol | 给外层 solver 暴露统一 evaluate 接口，而不泄露内部训练细节。 |

## 5. 预测-决策联动

| 你的框架叫法 | 社区常用叫法 | 你的差异点 |
| --- | --- | --- |
| `mlblack evaluation proxy` | surrogate model / learned evaluator / response surface | 可以是完整训练流或符号搜索流，不只是一个静态回归器。 |
| 外层搜索 inner config | hyperparameter optimization / algorithm configuration / AutoML | nsgablack 搜 trainer 参数、basis 参数、预算、结构开关和资源策略。 |
| 外层搜索 representation program | neural architecture search / program synthesis / feature construction search | 候选可以是组件组合、表征程序或符号结构。 |
| 外层多目标目标向量 | multi-objective model selection | 同时优化误差、结构恢复、复杂度、稳定性、成本等目标。 |
| inner result projection | metric projection / objective shaping / scalarization interface | 将内层丰富报告压成外层可优化的 objectives/violations。 |
| resource context 注入 | resource-aware optimization / budgeted learning / constrained HPO | 外层负责预算和资源边界，内层遵守注入的资源上下文。 |
| runtime summary 打印生效配置 | experiment audit / reproducibility report | 让资源、组件、后端和命名空间可审计。 |

## 6. 实验治理与可复现

| 你的框架叫法 | 社区常用叫法 | 你的差异点 |
| --- | --- | --- |
| `SurfaceRecord` | experiment entry record / workflow surface record | 说明跑的是哪个正式入口和脚手架 surface。 |
| `AssemblyRecord` | component composition record / configuration manifest | 说明实际挂载了哪些 solver、trainer、pipeline、plugin、bias。 |
| `RunRecord` | experiment run record | 记录一次具体运行的 subject、signature、状态和结果。 |
| `ArtifactRecord` | artifact lineage record | 记录模型、报告、checkpoint、trace 等产物及其来源。 |
| `assembly_signature` | reproducibility hash / configuration fingerprint | 用于比较两次运行是否装配一致。 |
| `artifact_signature` | artifact fingerprint / content identity | 用于追踪产物身份和复现链路。 |
| `replay` | experiment replay / deterministic rerun | 通过配置、snapshot、artifact 和 lineage 尽可能复现运行。 |
| `strict / soft-error` | fail-fast mode / warning mode | 外部资源或插件失败时可选择严格失败或软错误记录。 |
| `doctor --strict` | contract test / structural validation | 在运行前检查脚手架和契约，减少隐藏错误。 |

## 7. 和常见框架的关系

| 参照对象 | 社区定位 | 你的关系 |
| --- | --- | --- |
| `pymoo` / `DEAP` | evolutionary optimization libraries | nsgablack 更强调工程生命周期、插件、snapshot、catalog 和跨框架评估，而不只是算法实现。 |
| `Optuna` / `Ray Tune` | HPO / experiment tuning frameworks | nsgablack 可以覆盖 HPO，但候选表示、内层 solver、符号结构和多目标治理更通用。 |
| `sklearn Pipeline` | preprocessing + estimator pipeline | mlblack 借鉴 pipeline 思路，但加入 schema、numericizer、artifact、capability lifecycle 和运行审计。 |
| `MLflow` / `W&B` | experiment tracking | 你的 runtime surface 更贴近框架内部 assembly 和 artifact lineage，可作为轻量追踪层。 |
| `PySR` / symbolic regression tools | symbolic regression engine | mlblack 的 symbolic 部分不只是表达式搜索，还包含 basis consensus、locked core、outer orchestration 和 audit surface。 |
| AutoML / NAS 系统 | automatic model/architecture search | 你的外层 nsgablack 能搜索模型族、训练预算、符号结构、表征组件和决策参数。 |

## 8. 对外表达建议

可以把两个框架合起来描述为：

> `nsgablack` is the outer decision and search orchestration layer; `mlblack` is the inner learning, surrogate, symbolic modeling, artifact and audit layer. Together they form a reproducible prediction-decision integration stack.

中文可以说：

> nsgablack 提供外层搜索与决策语义；mlblack 提供内层拟合、代理评估、符号结构发现、artifact 与审计语义；预算、运行治理和跨 case 编排属于共享 Project / Case / Scaffold / L0 substrate。两者通过 evaluation proxy、resource context、run surface 和 artifact contract 连接。

## 9. 后续可补的证据表

| 需要证明的问题 | 建议实验 |
| --- | --- |
| 外层搜索是否优于固定 inner config | 对比 fixed config、random search、grid search、Bayesian optimization、nsgablack outer search。 |
| consensus 是否提升符号结构稳定性 | 多 seed、不同噪声、不同样本量下比较 single run 与 consensus/locked core。 |
| artifact/replay 是否真的提升可复现性 | 固定 run surface 后重跑，检查 assembly signature、metrics 和 artifact 差异。 |
| 多目标是否必要 | 单目标 RMSE、RMSE+复杂度、RMSE+结构恢复+复杂度三组消融。 |
| resource context 是否可审计 | 比较不同 worker/GPU/budget 配置下 runtime summary 与 run record 的一致性。 |

---

# Project、Case 与标准脚手架

> 文档状态：规范；来源：`nsgablack/docs/user_guide/PROJECT_SCAFFOLD.md`。本节按当前工作树合订；如与原创主卷或实时源码冲突，以原创主卷标注的规范和实时源码为准。

这份文档只回答一件事：如何用统一 Project / Case / Scaffold / L0 substrate 快速起一个可运行项目。

## 1. 一条命令创建

```powershell
python -m nsgablack project new my_project
cd my_project
python -m nsgablack project add-case my_case --type solver
```

`--type solver` 和 `--type trainer` 生成相同目录。差异只在 catalog kind 和语义组件，不在编排资格。

## 2. 会生成什么

```text
my_project/
  project_config.py        # stages/groups/dependencies + Project L0
  run_project.py           # formal entry, grants ResourceContext
  README.md
  START_HERE.md
  cases/
    my_case/
      build_solver.py      # canonical assembly
      build_trainer.py     # alias only
      run_solver.py        # case debug CLI
      run_trainer.py       # alias only
      config.py
      problem/
      pipeline/
      adapter/
      bias/
      plugins/
      evaluation/
      runtime/             # requirement/profile/audit
      solver/
```

## 3. 第一轮检查

```powershell
python -m nsgablack project doctor --path . --build --strict
python run_project.py
```

Doctor 会检查：

- Project / Case / Scaffold 目录和关键入口是否齐全
- case `build_solver()` 是否可实例化
- 组件契约是否清晰（如 `context_requires/provides/mutates`）
- context/snapshot 大对象边界是否符合协议

## 4. Project L0 怎么写

`project_config.py` 中声明可用资源和 case requirement：

```python
L0 = {
    "namespace": "my_project",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "strict"},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
}

STAGES = [
    {
        "name": "main",
        "cases": ["my_case"],
        "policy": "serial",
        "resource_requests": {
            "my_case": {"threads": 1, "gpus": 0, "backend": "local"},
        },
    },
]
```

规则：case 声明需求，Project L0 发放 `ResourceContext`，组件只消费 grant。

## 5. 本地 Catalog 怎么用

```powershell
python -m nsgablack project catalog list --path .
python -m nsgablack project catalog search pipeline --path .
python -m nsgablack project catalog search vns --path . --global
```

涉及主干能力判断时使用 framework-core：

```powershell
python -m nsgablack catalog list --profile framework-core --kind adapter
```

## 6. 用 Run Inspector 看结构

```powershell
python -m nsgablack run_inspector --entry cases/my_case/build_solver.py:build_solver
```

## 7. 常见问题

- 目标目录非空时报错：换新目录，或显式 `--force` 覆盖模板文件。
- `project doctor` 不可用：先确认当前安装的是最新本地代码（建议在仓库根目录 `python -m pip install -e .`）。
- 导入失败：优先检查是否从项目根运行 `run_project.py`，或 case debug 时是否在 case 目录运行 `run_solver.py --check`。

---

# Context 契约

> 文档状态：规范；来源：`nsgablack/docs/user_guide/CONTEXT_CONTRACTS.md`。本节按当前工作树合订；如与原创主卷或实时源码冲突，以原创主卷标注的规范和实时源码为准。

本文档说明 NSGABlack 的 context 契约机制：组件声明自己需要什么、写入什么，并由工具链做一致性检查。

---

## 1) 为什么要有 Context 契约

目标不是“限制算法”，而是保证三件事：

- 组件之间字段可对齐（不靠猜）
- 运行前可审计（Doctor / Inspector 能发现缺口）
- 结果可解释（知道字段由谁提供、谁消费）

---

## 2) 组件声明字段（统一接口）

所有组件都使用同一组契约字段：

- `context_requires`: 读取依赖
- `context_provides`: 新增输出
- `context_mutates`: 原地修改
- `context_cache`: 仅缓存字段
- `context_notes`: 语义说明
- `requires_metrics`: 当组件依赖 `context.metrics` 时，声明具体指标键（字段级）

说明：

- `provides` 表示“创建/首次提供”
- `mutates` 表示“更新已有字段”
- Inspector 的 Providers 视图 = `provides + mutates`
- `requires_metrics` 会被归一为 `metrics.<key>` 参与契约对齐与搜索

---

## 3) Canonical Key 规则（强制）

必须使用 `nsgablack.core.state.context_keys` 中的标准 key，禁止随意新造同义字段名。

常见标准 key（本轮已统一）：

- 协同调度：`candidate_roles`、`candidate_units`、`unit_tasks`
- 运行状态：`running`、`evaluation_count`
- 参数自适应：`mutation_rate`、`crossover_rate`
- 快照字段：`individual`、`metadata`、`snapshot_key`、`population_ref`、`pareto_solutions_ref`、`pareto_objectives_ref`、`sequence_graph_ref`

治理规则：

- 新字段先加到 `context_keys.py`（常量 + `CANONICAL_CONTEXT_KEYS`）
- 同步到 `context_schema.py`（生命周期分类）
- 再在组件契约里引用常量，不写裸字符串

---

## 4) 读写行为与声明关系

声明是“语义契约”，真正写入发生在运行阶段：

- Adapter：通常通过 `get_runtime_context_projection()` 投影运行字段
- Plugin：推荐在 `on_context_build()` 写入可观察字段
- Solver：提供快照引用字段（如 `snapshot_key`、`population_ref/objectives_ref/constraint_violations_ref`）

因此：

- 仅声明不等于自动写值
- 声明 + 运行写入共同构成“可审计证据”

---

## 5) 工具链校验（你会看到什么）

- `project doctor --strict`
  - 检查结构、注册、契约完整性
  - 检查 context 相关守卫（含镜像依赖等）
- `tools/context_field_guard.py`
  - 检查 catalog/契约中的非 canonical key
- Run Inspector / Context 页
  - 显示字段生命周期、声明来源、最后写入者
  - 可按字段联动查看 Providers/Consumers

---

## 6) 新增字段的最小流程

1. 在 `core/state/context_keys.py` 增加常量并加入 canonical 集合  
2. 在 `core/state/context_schema.py` 增加字段定义（category/replayable）  
3. 在组件内使用常量更新 `context_requires/provides/mutates/cache`  
4. 运行：
   - `python -m tools.context_field_guard`
   - `python -m nsgablack project doctor --path <project> --strict`

---

## 7) 示例

```python
from nsgablack.plugins.base import Plugin
from nsgablack.core.state.context_keys import KEY_MUTATION_RATE, KEY_CROSSOVER_RATE


class MyAdaptivePlugin(Plugin):
    context_requires = ()
    context_provides = ()
    context_mutates = (KEY_MUTATION_RATE, KEY_CROSSOVER_RATE)
    context_cache = ()
    context_notes = "Writes adaptive runtime rates for audit."
```

---

## 8) State Governance（状态治理）

Context 契约之上，还有一层更底层的状态治理规则——它约束的是 **population / objectives / constraint_violations 的读写路径**：

- **读取**：统一使用 `get_population_snapshot(solver)` 或 `solver.read_snapshot()`（快照引用 → store）
- **写入**：统一使用 `commit_population_snapshot(solver, ...)`（adapter-first：有 adapter 时写 adapter，无 adapter 时同步写 solver）
- **禁止**：Plugin / Adapter 不得直接写 `solver.population = ...` 等镜像字段（Doctor `--strict` 会检查 `solver-mirror-write` 和 `plugin-direct-solver-state-access`）

> 参考：`docs/user_guide/CONTEXT_FIELD_RULES.md` 与
> `docs/standard_scaffold_tutorial/04_validation_catalog_and_evolution.md`

---

## 9) 一句话原则

先定义语义，再实现逻辑；字段必须可对齐、可追踪、可审计。

---

# Context 字段治理

> 文档状态：规范；来源：`nsgablack/docs/user_guide/CONTEXT_FIELD_RULES.md`。本节按当前工作树合订；如与原创主卷或实时源码冲突，以原创主卷标注的规范和实时源码为准。

> context_field_schema_name: blackbase.context_field.v1  
> context_field_schema_version: 1.1.0

本规范用于约束 Context 字段治理，避免同义字段漂移、隐式写入和不可审计状态。

## 1. 目标

- 字段可读：看到 key 就能理解语义。
- 字段可追：能定位声明者、写入者、读取者。
- 字段可演进：新增字段不破坏既有组件。

## 2. 命名规则（必须）

- 使用小写蛇形，优先复用 `core/state/context_keys.py` 常量。
- 不允许同义词并存（例如 `obj` 与 `objectives` 同时存在）。
- 不允许随意缩写进入长期代码。
- 新 key 必须先声明常量，再进入组件契约。

## 3. 生命周期规则（必须）

字段需明确生命周期：

- `input`：问题输入或静态配置
- `runtime`：运行时状态
- `cache`：性能缓存，不保证可重放
- `custom`：临时/扩展字段（后续应收敛）

## 3.1 Context vs Snapshot 决策表（必须）

| 数据类型 | 放置位置 | 典型例子 | 说明 |
|---|---|---|---|
| 小字段、控制信号、契约依赖 | Context | `generation`、`phase_id`、`snapshot_key`、`population_ref` | 组件协作与可审计主通道 |
| 大对象、频繁读写数组 | SnapshotStore | `population`、`objectives`、`constraint_violations`、`pareto_*` | 不直接塞入 Context，避免膨胀和后端压力 |
| 需要跨组件共享的大对象 | Context 放引用 + Snapshot 放实体 | `population_ref -> snapshot_key` | Context 只传指针，读取走 `read_snapshot()` |
| 组件私有临时变量 | 组件内部 | 局部缓存、单次中间值 | 不写 Context，不写 Snapshot |

## 4. 组件契约规则（必须）

所有涉及字段读写的组件都要显式声明：

- `context_requires`
- `context_provides`
- `context_mutates`
- `context_cache`
- `context_notes`

`doctor --strict` 与 Run Inspector 会据此审计。

最低模板要求（建议直接复制）：

```python
class MyComponent:
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Explain what/why for context interactions.",)
```

其中 `context_requires/context_provides/context_mutates` 是核心三字段，必须明确写出（可以为空元组）。

## 5. 写入来源规则（必须）

- `last_writer` 必须来自可追踪证据（事件流/投影/构建写入记录）。
- `declared_by` 仅表示“声明写入者”，不能替代真实写入来源。

## 6. 新字段接入流程

1. 在 `context_keys.py` 增加 `KEY_XXX`。
2. 在相关组件补齐 `context_*` 契约。
3. 在 Run Inspector 校验字段可见性与归因。
4. 运行 `project doctor --strict` 与测试。
5. 更新文档/变更记录。

## 7. CI 门禁

CI 需至少包含：

- `tests/test_context_key_alignment.py`
- `tests/test_schema_version.py`
- `python tools/context_field_guard.py --strict`

---

# Context Field Naming and Evolution Rules

This document defines hard governance rules for Context key lifecycle and compatibility.

## Required controls

- Canonical keys must come from `context_keys.py`.
- Every component that touches context must declare explicit contracts.
- Field provenance must be evidence-based (declared vs actual writer separated).
- CI must reject non-canonical key drift.

## Versioning

- `context_field_schema_name = blackbase.context_field.v1`
- `context_field_schema_version = 1.1.0`

When semantics break compatibility, bump schema version and provide migration guidance.

---

# BlackBase Project Runtime

> 文档状态：实现；来源：`blackbase/PROJECT_RUNTIME_CN.md`。本节按当前工作树合订；如与原创主卷或实时源码冲突，以原创主卷标注的规范和实时源码为准。

blackbase 是 `nsgablack + mlblack` 统一框架栈的 Project / Case / Scaffold / L0 substrate。它负责跨 Case 编排、资源授权、执行隔离、artifact 传递和恢复记录；优化搜索语义仍属于 nsgablack，ML 训练语义仍属于 mlblack。

## Stage 执行

`project_config.py` 中的 Stage 支持两种策略：

- `policy="serial"`：按声明顺序在主进程执行。
- `policy="parallel"`（兼容名 `run_all_in_parallel`）：在相互隔离的子进程中执行 Case。
- `policy="external"`（兼容名 `external_workers`）：通过耐久 transport 交给独立 worker 进程执行。

并行 Stage 的 Case 必须使用标准 `build_solver.py` 装配入口和 `mode="build"`。CLI fanout 没有可靠的进程内对象与 artifact 注入契约，因此运行时会明确拒绝并行 `mode="cli"`，不会静默退化成串行。

同一并行 Stage 内的 Case 被视为互相独立。它们可以消费先前 Stage 注册的 `DataRef`，不能依赖同一 Stage 中尚未完成的 Case。需要依赖关系时，应拆成两个 Stage。

```python
STAGES = [
    {
        "name": "search_and_fit",
        "policy": "parallel",
        "failure_policy": "fail_fast",
        "max_workers": 2,
        "cases": ["search_case", "fit_case"],
        "resource_requests": {
            "search_case": {"workers": 1, "threads": 2},
            "fit_case": {"workers": 1, "threads": 2},
        },
    },
]
```

Project L0 在父进程中先发放 lease，再提交子进程。所有活动 lease 的 workers、threads、GPU、memory 和独占 device token 会做聚合校验；资源不足时，调度器形成资源允许的执行波次，而不是超额授权。

## 失败语义

`failure_policy="fail_fast"` 会在观察到第一个失败后停止启动新 Case；已经运行的 Case 会完成并归还 lease，尚未启动的 Case 会产生明确的 `skipped` 结果。`failure_policy="continue"` 则继续执行可以运行的 Case。

Case 输出跨进程时必须是 JSON 兼容数据、`DataRef`、Path、支持 `tolist()` 的数组，或实现 `as_dict()` 的对象。不可安全传输的对象会让该 Case 明确失败。

## Artifact 传递

Case 在结果的 `artifact_refs` 或 `artifacts` 字段返回命名引用：

```python
return {
    "artifact_refs": {
        "model": {"uri": "s3://bucket/model.bin", "kind": "model"},
    },
}
```

后续 Stage 通过正式 key 注入：

```python
{
    "name": "evaluate",
    "cases": ["evaluator"],
    "input_artifacts": {
        "evaluator": {"model": "trainer.model"},
    },
}
```

消费方 Case 必须实现 `set_input_artifacts(refs)`。运行时只传引用，不把模型、population、数据集等大对象塞进 context。

## Manifest 与恢复

实际运行默认原子写入：

```text
.blackbase/runs/<run-id>/manifest.json
```

Manifest 包含 Project、group、framework、运行状态、每个 Case 的状态/耗时/错误、artifact registry，以及配置和 Case 源码指纹。它不持久化任意运行对象或完整大输出。

```powershell
python run_project.py --run-id first-attempt
python run_project.py --resume-from first-attempt
```

恢复时，先前成功的 Case 标记为 `resumed` 并跳过执行；它们的 artifact 引用会重新注册，失败或未启动的 Case 会重新运行。只要 `project_config.py`、Case Python 源码、`.case`、group 或 framework 发生变化，指纹校验就会拒绝恢复，避免用旧运行状态驱动新代码。

调试时可用 `--no-record` 关闭记录；`--check` 本身不会创建运行记录，也不能与 `--resume-from` 同时使用。

## 外部 worker

外部执行仍由 Project L0 先发放 lease。Project 将标准 Case payload、资源 requirement、`ResourceContext`、输入 `DataRef` 和重试上限写入 transport；worker 只能 claim 自己的 `WorkerDescriptor` 能满足的任务。

当前提供 SQLite 参考后端，适用于同机多进程或共享文件系统上的 worker。它具备：

- 原子 claim，同一个任务不会同时授权给两个 worker；
- worker/task 心跳和 lease token；
- worker 崩溃后的 lease 过期回收；
- `max_retries` 控制的 at-least-once 重试；
- 幂等 task id、耐久结果和严格 JSON payload；
- 无兼容 worker 时的明确 queue timeout，不会退化成本地执行。

Project 配置：

```python
{
    "name": "external_fit",
    "policy": "external",
    "cases": ["fit_case"],
    "external": {
        "backend": "sqlite",
        "transport_path": ".blackbase/external_tasks.sqlite",
        "queue_timeout_seconds": 30,
        "poll_interval_seconds": 0.05,
        "max_retries": 1,
    },
}
```

先启动 worker，再运行 Project：

```powershell
python -m blackbase.project.external_worker `
  --project-root . `
  --transport .blackbase/external_tasks.sqlite `
  --worker-id worker-1 `
  --threads 4

python run_project.py
```

worker 会拒绝 payload 中不等于 `--project-root` 的路径，防止 transport 中的任务越权执行其他本地项目。SQLite 后端不伪装成网络集群；真正跨机器且没有共享文件系统时，应实现同一个 `TaskTransport` 契约的 Redis、数据库或云队列 provider。

## 耐久 L0 lease 与 fencing

新建 Project 默认使用 SQLite 作为 L0 lease authority：

```python
L0 = {
    "lease_backend": "sqlite",
    "lease_path": ".blackbase/l0_leases.sqlite",
    "lease_ttl_seconds": 30,
    "lease_heartbeat_seconds": 10,
}
```

每次授权都获得 namespace 内单调递增的 `fencing_token`。资源预算校验、过期 lease 回收、token 发放和 lease 写入在一个 SQLite 写事务中完成，因此多个 Project 进程不能同时抢到同一份最后资源。活动 Case 由 Project 或 external worker 续租；只有 `lease_id + fencing_token` 仍为当前授权时才能续租、释放或提交结果。

这条约束解决三类运行时遗留问题：

- Project 崩溃后，旧 lease 到期自动释放资源，不永久占用预算；
- 旧 worker 即使晚到，也不能用已失效 token 覆盖新一轮运行结果；
- 恢复运行遇到仍为 `leased` 的外部任务时，会接管原 task 和原 lease，不重复申请资源或重复执行 Case。

worker 在提交 `TaskResult` 前必须再次校验 Project fence，并在结果 metadata 中写入验证标记和 token。Project 对 durable authority 下缺少该证明、token 不一致或本地 Case 已失去 fence 的结果一律拒收。

为兼容已有 Project，未声明 `lease_backend` 的旧配置暂时保持进程内 `memory` authority；需要崩溃恢复、外部 worker 或多个 Project 进程共享预算时，应显式迁移到上述 SQLite 配置。`project doctor --strict` 会检查 backend、path、TTL 与 heartbeat 的静态配置。

### 跨机器 Redis lease authority

SQLite authority 适合同机进程或共享文件系统。没有共享文件系统的多机 worker 应把 Project L0 authority 切换到 Redis：

```python
L0 = {
    "namespace": "my_project",
    "lease_backend": "redis",
    "lease_redis_url_env": "BLACKBASE_REDIS_URL",
    "lease_ttl_seconds": 30,
    "lease_heartbeat_seconds": 10,
}
```

Project 与 worker 都通过声明的环境变量读取 Redis URL。URL 不会写入 `ResourceContext`、check 输出或运行 manifest；上下文只传 authority backend、namespace、环境变量名、TTL 与 heartbeat。也可以在受控环境中使用 `L0.lease_redis_url`，但不建议把带凭据 URL 提交到仓库。

Redis authority 在 namespace 级分布式锁内完成过期回收、活动租约聚合校验和 fencing token 发放，再用 Redis transaction 一次提交 lease、审计索引与下一个 token。因此多个 Project 进程共享同一 namespace 时，不会同时拿到最后一份资源。

worker 示例：

```powershell
$env:BLACKBASE_REDIS_URL = "redis://redis-host:6379/0"
python -m blackbase.project.external_worker `
  --project-root . `
  --backend redis `
  --redis-url $env:BLACKBASE_REDIS_URL `
  --namespace my_project:external_tasks
```

如果 task transport 与 lease authority 使用不同 Redis，可额外传 `--lease-redis-url`。生产环境应由 secret manager 或进程环境注入连接信息。

---

# Redis 任务传输

> 文档状态：实现；来源：`blackbase/REDIS_TASK_TRANSPORT_CN.md`。本节按当前工作树合订；如与原创主卷或实时源码冲突，以原创主卷标注的规范和实时源码为准。

`RedisTaskTransport` 是 blackbase 的跨进程、跨机器任务传输实现。它和
`SQLiteTaskTransport` 遵循同一个 `TaskTransport` 契约，负责原子认领、任务租约、
worker 心跳、失败重试、过期租约回收、取消、结果等待和状态审计。Solver、Trainer
以及业务 Case 不应直接依赖 Redis 命令。

## Project 外部 Stage

```python
{
    "name": "external_fit",
    "policy": "external",
    "cases": ["fit_case"],
    "external": {
        "backend": "redis",
        "redis_url": "redis://127.0.0.1:6379/0",
        "namespace": "my_project:external_tasks",
        "queue_timeout_seconds": 30,
        "poll_interval_seconds": 0.05,
        "max_retries": 1,
    },
}
```

worker 使用同一 URL 与 namespace：

```powershell
python -m blackbase.project.external_worker `
  --project-root . `
  --backend redis `
  --redis-url redis://127.0.0.1:6379/0 `
  --namespace my_project:external_tasks `
  --worker-id worker-1 `
  --threads 4
```

`redis_url` 可能包含凭据，因此 Project 的 check 输出和 manifest 只记录 backend 与
namespace，不回显 URL。部署时应通过受控配置注入 URL，不要把生产凭据提交到仓库。

## Redis Project L0 authority

`RedisTaskTransport` 只负责任务 broker；跨机器资源预算与结果 fencing 由独立的
`RedisLeaseStore` 负责。多机 Project 应同时配置：

```python
L0 = {
    "namespace": "my_project",
    "lease_backend": "redis",
    "lease_redis_url_env": "BLACKBASE_REDIS_URL",
    "lease_ttl_seconds": 30,
    "lease_heartbeat_seconds": 10,
}
```

task transport namespace 与 lease namespace 是两种不同职责：前者定位队列，后者定义
共享资源预算和 fencing 序列。它们可以使用同一个 Redis 服务，但不能把 task lease
误当作 Project resource lease。worker 必须同时续租两者，并在提交结果前再次验证
Project fencing token。

## 真实 Redis 集成测试

默认测试套件不会依赖外部 Redis；设置专用测试 URL 后会启用真实服务测试：

```powershell
$env:BLACKBASE_TEST_REDIS_URL = "redis://127.0.0.1:6379/15"
pytest tests/test_redis_live_integration.py -q
```

测试使用随机 namespace，覆盖并发 admission、TTL/fencing、完整 Project external
worker 往返、task lease 崩溃恢复和 stale owner 拒绝，并只清理自身 namespace，
不会执行 `FLUSHDB`。

## 崩溃恢复边界

Project 为每个外部 Case 使用确定性 task id：

```text
project:<run-id>:<stage-name>:<case-name>
```

任务提交成功后，Project 会立即把 task id 和 broker 状态写入 manifest。即使进程恰好
在“broker 已提交、manifest 尚未写入”的窗口崩溃，恢复运行仍可根据旧 run id 推导 task
id 并与 transport 对账：

- `succeeded`：直接恢复 worker 结果与 artifact，不重复执行；
- `leased`：复用原任务的 `ResourceContext` 与 L0 fencing lease，等待原任务结束，避免重复授权和并发重复执行；
- `queued`：取消旧排队任务，再用新一轮 Project L0 grant 提交；
- `failed/cancelled/missing`：按新运行重新提交。

恢复得到的 Case 状态为 `resumed`。如果结果来自旧任务，审计中的 `ResourceContext`
使用 worker 实际执行时的上下文，而不是伪装成恢复进程新申请的上下文。

## nsgablack 兼容面

`blackbase.resources.RedisL0RuntimeBackend` 是统一 Redis
`TaskTransport` 的兼容 facade。旧的 `submit/claim/complete/get_result` 调用外形仍然保留，
但 claim token 只能由同一个 worker 进程持有和完成。新的 worker 代码应优先使用
`task_transport`、`claim_task()` 和 `complete_claim()`，以便显式处理 lease 与心跳。

---

# 验证、Doctor、Catalog 与长期演进

> 文档状态：实践；来源：`nsgablack/docs/standard_scaffold_tutorial/04_validation_catalog_and_evolution.md`。本节按当前工作树合订；如与原创主卷或实时源码冲突，以原创主卷标注的规范和实时源码为准。

标准脚手架不是“能跑就行”。它必须能回答这些问题：

- 这次运行装了哪些组件？
- 参数来自哪个 Spec/Registry？
- 哪些组件读写了 context？
- 大对象写到了哪个 snapshot？
- 两次运行结构差异是什么？
- 新增机制应该归到哪一层？

## 1. 最小检查命令

在项目目录内：

```powershell
python run_project.py --check --build-check
python -m nsgablack project doctor --path . --build --strict --format problem
```

如果只想调试单个 Case，可以进入 `cases/<case>/` 后运行
`python run_solver.py --check`。这不是正式复现入口；正式运行和资源授权始终从 Project root 的
`run_project.py` 开始。

框架主干 catalog：

```powershell
python -m nsgablack catalog list --profile framework-core --kind adapter
python -m nsgablack catalog list --profile framework-core --kind plugin
python -m nsgablack catalog search nsga2 --profile framework-core --limit 20
```

项目 catalog：

```powershell
python -m nsgablack project catalog list --path .
python -m nsgablack project catalog search pipeline --path .
python -m nsgablack project catalog search vns --path . --global
```

Run Inspector：

```powershell
python -m nsgablack run_inspector --entry build_solver.py:build_solver
```

建议把检查拆成日常三档：

| 档位 | 什么时候跑 | 命令 |
| --- | --- | --- |
| quick | 每改一层组件后 | `python run_project.py --check --build-check` |
| strict | 合并前或机制变更后 | `python -m nsgablack project doctor --path . --build --strict --format problem` |
| audit | 文档、catalog、case 准备发布前 | `run_inspector` + `project catalog` + `framework-core catalog` |

如果某次改动涉及评估链、snapshot、catalog 或 L0 资源，不能只跑 quick。

## 2. doctor 输出怎么读

`project doctor` 的核心不是格式检查，而是契约检查。常见类型：

| 类型 | 含义 | 处理优先级 |
| --- | --- | --- |
| import/build error | 装配入口无法导入或无法 build | 最高 |
| scaffold structure | 标准目录或文件缺失 | 高 |
| context contract | context key/读写声明不清晰 | 高 |
| snapshot policy | 大对象直接写 context | 高 |
| catalog registration | 组件可发现性不足 | 中 |
| example/case placement | 示例落点不符合规范 | 中 |
| warning | 暂不破坏运行，但影响可维护性 | 视情况 |

处理原则：

1. 先修 import/build error。
2. 再修 problem/pipeline/adapter/plugin 的层级边界。
3. 再修 context/snapshot。
4. 最后补 catalog 和文档。

不要因为优化结果正常就忽略 doctor。doctor 报的是长期维护风险。

## 3. 新增组件检查清单

新增 `Problem`：

- `dimension` 与 bounds 数量一致。
- `evaluate(x)` 返回 objective 维度稳定。
- `evaluate_constraints(x)` 返回 violation 维度稳定。
- 异常输入有明确 fallback 或异常。
- 目标和约束含义写在 config 或 docs 中。

新增 `RepresentationPipeline`：

- initializer 输出 shape 稳定。
- mutator 尊重 bounds/context。
- repair 只做可行性兜底，不做业务搜索。
- encode/decode 可序列化。
- typed genome 的字段可以写进 report。

新增 `Adapter`：

- `propose(solver, context)` 只产生候选。
- `update(...)` 只消费反馈。
- 提供 `get_state/set_state` 以支持 checkpoint。
- 不把 population/history 长期塞 context。
- 多策略组合时不依赖全局变量。

新增 `Plugin`：

- lifecycle hook 幂等。
- 写 context 使用 canonical key 或清晰前缀。
- 大对象写 snapshot。
- 短路评估返回 shape 合法。
- 外部资源失败支持 soft/strict 模式。

新增 `Bias`：

- 明确是软引导。
- 记录启用状态和风险。
- 不替代 objective/constraint。

新增 `L0 Resource` 或跨框架资源能力：

- `ResourceRequest`、`ResourceOffer`、`ResourceLease` 字段可序列化。
- GPU 资源落到具体 `device_tokens`，不是只写 `gpus: 1`。
- 多进程时使用共享 lease store，例如 `SQLiteLeaseStore`。
- 如果启用 TTL，heartbeat 由 runner/worker 管理，不进入业务 trainer。
- `ResourceContext` 写入 summary/runtime_state，便于审计。

## 4. 单点、批量、短路评估必须同时验证

涉及评估链改动时，至少验证三条路径：

```python
# 单点
obj = solver.evaluate_individual(x)

# 批量
objs = solver.evaluate_population(population)

# 插件短路
plugin.evaluate_population(solver, population, context)
```

验收标准：

| 路径 | 必须满足 |
| --- | --- |
| 单点 | objective/violation shape 稳定 |
| 批量 | 返回数量与 population 数量一致 |
| 短路 | 和普通评估同 shape、同方向、同失败语义 |

如果短路评估返回的是缓存结果，也要在 report 中说明缓存命中率和 miss fallback。

## 5. Context/Snapshot 审计规则

不要：

```python
context["population"] = population
context["objectives"] = objectives
context["history"] = huge_history
context["trace"] = huge_trace
```

应该：

```python
snapshot_key = solver.write_population_snapshot(population, objectives, violations)
context["population_ref"] = snapshot_key
```

读取优先级：

```text
snapshot -> adapter state -> solver lightweight mirror
```

写回优先级：

```text
adapter.set_population* -> solver.write_population_snapshot -> context *_ref
```

最小审计字段建议：

| 字段 | 说明 |
| --- | --- |
| `snapshot_key` | 大对象位置 |
| `kind` | population/objectives/trace/artifact |
| `generation` | 产生时刻 |
| `producer` | 哪个组件写入 |
| `schema_version` | 未来兼容 |

## 6. Catalog profile 口径

| profile | 用途 |
| --- | --- |
| `framework-core` | 主干盘点，排除 example/doc |
| `default` | 完整口径，包含 example/doc |

任何“这个组件是不是主干能力”的结论，都必须显式使用：

```powershell
python -m nsgablack catalog list --profile framework-core --kind adapter
python -m nsgablack catalog search <keyword> --profile framework-core --limit 20
```

教学、示例和模板查找才使用 `default`：

```powershell
python -m nsgablack catalog list --profile default --kind example
```

## 7. 项目本地 catalog entry 怎么写

项目侧只在 `catalog/entries/<kind>.toml` 注册本地组件；运行时 Python registry 已删除。示例：

```toml
[[entries]]
key = "project.pipeline.offloading"
kind = "pipeline"
summary = "Offloading policy genome pipeline with bounded continuous variables."
status = "project"
owner = "project"

[entries.metadata]
mount_plane = "representation"
mount_point = "solver.set_representation_pipeline"
use_when = "候选解是卸载比例、安全等级等连续变量。"
contract_consumes = []
contract_provides = []
contract_mutates = []
```

最小要求：

- key 全局可读，不要叫 `test1`。
- kind 明确。
- summary 说明做什么。
- mount point 说明怎么挂载。
- contract 字段说明 context 读写。

## 8. Run Inspector 看什么

Run Inspector 的目标是解释 wiring：

| 面板/信息 | 看什么 |
| --- | --- |
| solver | solver 类型、生命周期入口 |
| adapter | 当前策略、是否多策略/串行/事件驱动 |
| representation | pipeline 是否挂载、context contract |
| plugins | 生命周期插件和评估短路插件 |
| context | 轻量状态 key |
| snapshot | 大对象引用 |
| diff | 两次装配差异 |

如果 Run Inspector 无法快速加载，通常说明 `build_solver()` 做了重计算。修法是把重计算移动到：

- `solver.run()` 阶段。
- `problem.evaluate()` 阶段。
- evaluation provider。
- plugin runtime hook。

建议在报告中至少记录这些 wiring 字段：

| 字段 | 来源 | 目的 |
| --- | --- | --- |
| `run_id` | CLI / build_solver | 区分运行 |
| `problem_key` | build config | 解释目标和约束 |
| `pipeline_key` | build config | 解释候选表示 |
| `adapter_profile` | adapter config | 解释搜索策略 |
| `bias_key` | bias config | 解释软先验 |
| `plugin_keys` | plugin config | 解释运行能力 |
| `resource_context` | L0 | 解释 CPU/GPU 授权 |
| `snapshot_refs` | SnapshotStore | 定位大对象 |

这些字段不是为了好看，而是为了之后能回答“为什么这次结果和上次不同”。

## 9. 标准 case 落点

正式 example、benchmark、cross-framework case 放：

```text
examples/cases/<project>/
```

推荐结构：

```text
examples/cases/<project>/
  README.md
  project_config.py
  run_project.py
  cases/
    <case>/
      build_solver.py
      run_solver.py
      problem/
      pipeline/
      bias/
      plugins/
      reporting/
      tests/
```

Project root is the formal reproduction surface. Case root is the single
Solver/Trainer assembly surface.

Legacy single-case examples used to look like:

```text
examples/cases/<case>/
  README.md
  build_solver.py
  run_solver.py
  config/
    schema.py
  problem/
    outer_problem.py
    inner_bridge.py
  pipeline/
    genome.py
  bias/
  plugins/
  reporting/
  tests/
```

That shape is compatibility material. New examples and migrated examples must
use the Project wrapper.

不要把完整 case 长期放到：

```text
my_project/<case>
```

`my_project/` 只作为 starter template、参考骨架、兼容层或个人孵化位。

迁移检查清单：

- `my_project/<case>` 中的完整装配逻辑迁到 `examples/cases/<project>/cases/<case>`。
- 旧入口只保留 thin wrapper 或 compatibility note。
- `build_solver.py` 不堆 problem/pipeline/plugin 细节。
- case 内部按 `problem/pipeline/config/reporting` 分层。
- 跨框架 case 通过正式 surface 传 ResourceContext。

## 10. 新机制落点决策树

当你想新增一个机制，先问：

| 问题 | 如果答案是 yes | 落点 |
| --- | --- | --- |
| 它改变候选生成策略吗？ | yes | Adapter |
| 它改变候选表示、decode 或 repair 吗？ | yes | RepresentationPipeline |
| 它只是软偏好或初始引导吗？ | yes | Bias |
| 它只是运行能力、记录、恢复、后端或副作用吗？ | yes | Plugin |
| 它改变目标或约束吗？ | yes | Problem/Evaluation |
| 它只是并行、设备、backend 或资源池吗？ | yes | L0 runtime/plugin |
| 它调度多个 solver 实例吗？ | yes | solver orchestration |
| 它控制内层组件参数吗？ | yes | representation decode + component_overrides + bridge |

如果一个文件同时做三件以上事情，通常说明边界错了。

## 11. 版本演进建议

推荐演进顺序：

1. 先跑单策略 baseline。
2. 再加真实 problem constraints。
3. 再加 representation typed genome。
4. 再加 bias seeds。
5. 再加多策略 adapter。
6. 再加 plugin trace/report/checkpoint。
7. 再加 nested inner runtime。
8. 最后做多 solver orchestration 和资源调度。

每一步都要保持可回退、可审计、可解释。不要一开始就把多 solver、嵌套训练、GPU、Redis、复杂 report 全部混在一起，否则失败时无法定位是哪一层的问题。

推荐把长期演进拆成版本号：

| 版本 | 内容 | 风险控制 |
| --- | --- | --- |
| v0 | 单 problem + 单 pipeline + 单 adapter | 只看 shape 和 smoke |
| v1 | 加真实约束和基础 report | 检查 objective/violation 方向 |
| v2 | 加 typed representation 或 component_overrides | report 记录 decode 结果 |
| v3 | 加 adapter group / serial group | trace 记录候选来源和 phase |
| v4 | 加 checkpoint/snapshot | 验证恢复后 adapter state |
| v5 | 加 nested inner runtime | inner report 和 outer objective 对齐 |
| v6 | 加 L0 lease / GPU / 多进程 | active lease、ResourceContext 可审计 |
| v7 | 加多 solver orchestration | 每个 solver profile 独立 summary |

每升一个版本，只新增一个主机制。效果变差时先回退最近版本，而不是同时调 problem、pipeline、adapter 和 plugin。

## 12. 提交前最小清单

- 是否保持 Solver / Adapter / Representation / Plugin 边界？
- 是否避免大对象直写 context？
- 若改评估链，是否验证单点/批量/插件短路？
- 若改 catalog，是否验证 `default` 与 `framework-core`？
- 若新增 example/case，是否放在 `examples/cases/<project>/cases/<case>/`，并有 Project 外层？
- 是否运行 `project doctor --strict --format problem` 并确认无新增 error？

---

# Slot Kernel 最小规范

> 文档状态：实践；来源：`nsgablack/docs/standard_scaffold_tutorial/08_slot_kernel_minimal_spec.md`。本节按当前工作树合订；如与原创主卷或实时源码冲突，以原创主卷标注的规范和实时源码为准。

本章是可直接照抄的“从空 Case 到可运行”手册，目标是把 `pipeline/main.py` 变成真正可运行的统一编排入口。

## 0. 先讲清语义边界

`nsgablack` 与 `mlblack` 在 pipeline 语义上**不一样**，但共享同一个 slot kernel 编排契约。

- `nsgablack` pipeline 语义：搜索表示流（`init/mutate/repair/encode/decode`）
- `mlblack` pipeline 语义：训练数据/模型语义流（`transform/codec/head`）
- 共享点：都用一个 `pipeline/main.py` 主入口 + slot spec + operator registry

所以“统一”的是编排内核，不是把两个框架的语义混成一套。

---

## 1. 从空项目开始

在项目根目录执行：

```powershell
python -m nsgablack project new demo_slot_kernel_nsga
cd demo_slot_kernel_nsga
python -m nsgablack project add-case search_case --type solver --framework nsgablack
```

此时目录里会有：

```text
demo_slot_kernel_nsga/
  project_config.py
  run_project.py
  cases/
    search_case/
      build_solver.py
      pipeline/
        main.py
```

---

## 2. 用 CLI 生成 pipeline 内部算子

### 2.1 生成主入口（如果还没生成）

```powershell
python -m nsgablack project add-component --case search_case --kind pipeline --slot main --name main
```

### 2.2 生成 mutate / repair 算子

```powershell
python -m nsgablack project add-component --case search_case --kind pipeline --slot mutate --name gaussian_mutate
python -m nsgablack project add-component --case search_case --kind pipeline --slot repair --name clip_repair
```

会自动落到：

```text
cases/search_case/pipeline/operators/mutate/gaussian_mutate.py
cases/search_case/pipeline/operators/repair/clip_repair.py
```

---

## 3. `pipeline/main.py` 最小可运行装配

把 `cases/search_case/pipeline/main.py` 调整为如下结构（核心是两个输入：`pipeline_spec` + `pipeline_operators`）：

```python
from typing import Any, Mapping
from nsgablack.representation import PipelineSpec, build_pipeline_kernel


def build_pipeline(*, resource_context: Mapping[str, Any] | None = None, component_overrides: Mapping[str, Any] | None = None):
    del resource_context
    overrides = dict(component_overrides or {})
    registry = dict(overrides.get("pipeline_operators", {}) or {})
    spec = PipelineSpec.from_value(
        overrides.get("pipeline_spec", {"key": "default", "slots": ()})
    )
    kernel = build_pipeline_kernel(spec, operator_registry=registry)
    return kernel.representation_pipeline
```

---

## 4. 三种模式的完整 spec 示例

下面三组 spec 可以直接塞进 `component_overrides["pipeline_spec"]` 使用。

### 4.1 serial（串行）

```python
pipeline_spec = {
    "key": "serial_search",
    "slots": (
        {
            "slot": "mutate",
            "mode": "serial",
            "operators": ("gaussian_mutate", "clip_repair"),
        },
    ),
}
```

语义：先 `gaussian_mutate`，再 `clip_repair`。

### 4.2 parallel（并行分支 + merge）

```python
pipeline_spec = {
    "key": "parallel_search",
    "slots": (
        {
            "slot": "mutate",
            "mode": "parallel",
            "operators": ("wide_mutate", "local_mutate"),
            "merge": "mean",  # last/first/list/sum/mean/concat
        },
    ),
}
```

语义：两个分支都基于同一个输入跑，然后按 `merge` 合并。

### 4.3 router（按 context 路由）

```python
pipeline_spec = {
    "key": "router_search",
    "slots": (
        {
            "slot": "mutate",
            "mode": "router",
            "selector_key": "phase",
            "routes": {
                "explore": "wide_mutate",
                "exploit": "local_mutate",
            },
            "default_operator": "local_mutate",
            "strict": True,
        },
    ),
}
```

语义：`context["phase"]` 决定走哪个算子。

---

## 5. method 覆写（高级但很实用）

默认 slot 会映射到默认方法名（如 `mutate` slot 调 `mutate()`）。  
如果你要调用自定义方法，可在 slot 里加 `method`：

```python
{
  "slot": "head",
  "method": "predict",
  "operators": ("head_main",),
}
```

这在跨框架时尤其重要（例如 ml 侧 head 经常是 `predict/forward`）。

---

## 6. 运行时如何注入 spec 与 registry

在 `build_solver(...)` 里，把 `component_overrides` 透传给 `build_pipeline(...)`。

示意：

```python
pipeline_overrides = {
    "pipeline_spec": pipeline_spec,
    "pipeline_operators": {
        "gaussian_mutate": GaussianMutate(),
        "clip_repair": ClipRepair(),
        "wide_mutate": WideMutate(),
        "local_mutate": LocalMutate(),
    },
}
pipeline = build_pipeline(component_overrides=pipeline_overrides)
```

---

## 7. 可复制的验证步骤

```powershell
python run_project.py --check --build-check
python -m nsgablack project doctor --path . --build --strict --format problem
```

建议至少验证：

1. serial 路径输出 shape 稳定
2. parallel merge 输出 shape 稳定
3. router 在不同 context 下路由正确

---

## 8. 常见错误与修复

### 错误 1：`pipeline operator not found`

原因：`pipeline_spec` 里写了名字，但 `pipeline_operators` 没注册。  
修复：统一命名，确保 spec/registry 一致。

### 错误 2：parallel merge 报错

原因：分支输出 shape 不兼容，或 merge 策略不匹配。  
修复：先用 `list` 收集，再检查每个分支输出；确认后再改 `mean/sum/concat`。

### 错误 3：router strict 模式 KeyError

原因：`selector_key` 在 context 中缺失或 route 未配置。  
修复：补 `default_operator`，或改 `strict=False`，或保证 context 注入。

---

## 9. 你可以直接复用的“起步组合”

### 组合 A：稳妥基线

- `mutate`: serial
- `repair`: serial
- 优先可复现

### 组合 B：探索/开发双模

- `mutate`: router(`phase=explore/exploit`)
- `repair`: serial
- 便于阶段策略切换

### 组合 C：多分支变异

- `mutate`: parallel + `merge=mean`
- `repair`: serial
- 适合多策略融合

---

## 10. 本章结论

`nsgablack` pipeline 的正确姿势是：

- Case 级只有一个 `pipeline/main.py`
- pipeline 内部用 slot kernel 组合算子
- 编排逻辑显式、可审计、可替换

这就是“统一 substrate + 搜索语义层”的可运行落地方式。

---

# 自定义 Adapter

> 文档状态：实践；来源：`nsgablack/docs/standard_scaffold_tutorial/09_custom_adapter.md`。本节按当前工作树合订；如与原创主卷或实时源码冲突，以原创主卷标注的规范和实时源码为准。

本章目标：从空 Case 出发，写一个最小可运行的自定义 Adapter，并能通过 `--check` + doctor。

## 0. 先明确 Adapter 边界

Adapter 负责“搜索策略语义”，核心只有两件事：

1. `propose(...)` 生成候选
2. `update(...)` 消费反馈并更新内部状态

Adapter 不负责：

- 全局编排（Project substrate 负责）
- 全局资源发放（Project L0 负责）
- 运行能力（Plugin 负责）

---

## 1. 创建 case 与 adapter 文件

```powershell
python -m nsgablack project new demo_adapter_nsga
cd demo_adapter_nsga
python -m nsgablack project add-case my_solver --type solver --framework nsgablack
python -m nsgablack project add-component --case my_solver --kind adapter --name my_adapter
```

生成文件：

```text
cases/my_solver/adapter/my_adapter.py
```

---

## 2. 写最小可运行 Adapter

下面是可运行骨架（重点是接口形状和状态结构）：

```python
from __future__ import annotations

import numpy as np


class MyAdapter:
    def __init__(self, population_size: int = 16, sigma: float = 0.1, seed: int = 42):
        self.population_size = int(population_size)
        self.sigma = float(sigma)
        self.rng = np.random.default_rng(int(seed))
        self._population = None
        self._objectives = None
        self._violations = None

    def propose(self, control, context):
        # 首次：从 control.problem.dimension 构造初始群体
        if self._population is None:
            dim = int(getattr(control.problem, "dimension", 8))
            self._population = self.rng.normal(0.0, 1.0, size=(self.population_size, dim))
            return self._population

        # 后续：围绕当前群体做高斯扰动
        noise = self.rng.normal(0.0, self.sigma, size=self._population.shape)
        return self._population + noise

    def update(self, control, candidates, feedback, context):
        objectives, violations = feedback
        # 最小策略：保留本代候选并记录反馈
        self._population = np.asarray(candidates, dtype=float)
        self._objectives = np.asarray(objectives, dtype=float)
        self._violations = np.asarray(violations, dtype=float).reshape(-1)

    # --- 推荐实现：checkpoint 友好 ---
    def get_state(self):
        return {
            "population": None if self._population is None else self._population.tolist(),
            "objectives": None if self._objectives is None else self._objectives.tolist(),
            "violations": None if self._violations is None else self._violations.tolist(),
            "sigma": self.sigma,
        }

    def set_state(self, state):
        payload = dict(state or {})
        self.sigma = float(payload.get("sigma", self.sigma))
        pop = payload.get("population")
        obj = payload.get("objectives")
        vio = payload.get("violations")
        self._population = None if pop is None else np.asarray(pop, dtype=float)
        self._objectives = None if obj is None else np.asarray(obj, dtype=float)
        self._violations = None if vio is None else np.asarray(vio, dtype=float).reshape(-1)
```

---

## 3. 在 `build_solver.py` 挂载 Adapter

核心是：

```python
solver = ...
solver.set_adapter(MyAdapter(...))
```

示意（你自己的 `build_solver.py` 按本 Case 风格写）：

```python
from .adapter.my_adapter import MyAdapter

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    del config, resource_context, component_overrides
    solver = make_solver_somehow()
    solver.set_adapter(MyAdapter(population_size=24, sigma=0.05))
    return solver
```

---

## 4. 三种常见 Adapter 进阶形态

### 4.1 单策略（最稳）

- 一个 propose
- 一个 update
- 适合基线与回归测试

### 4.2 多策略 router（阶段切换）

结合 context key：

```text
phase=explore -> 大步长策略
phase=exploit -> 小步长策略
```

### 4.3 多策略并行（候选融合）

- 多个策略分别 propose
- 合并后统一 evaluate/update
- 注意返回 shape 与追踪来源字段

---

## 5. 验证步骤（必须跑）

```powershell
python run_project.py --check --build-check
python -m nsgablack project doctor --path . --build --strict --format problem
```

建议额外做一次短跑（小迭代）确保 propose/update 真执行。

---

## 6. 常见坑

1. `propose` 返回 list of object / shape 不稳  
   修复：统一返回 `np.ndarray` 或 solver 可消费的固定结构。

2. `update` 不记录 population，下一代 propose 无法延续  
   修复：保存 `_population`。

3. 在 adapter 里直接写大对象进 context  
   修复：大对象走 snapshot/ref；context 只留轻量字段。

4. adapter 里偷偷做资源申请  
   修复：只消费 `resource_context`，不申请全局资源。

---

# 自定义 Bias

> 文档状态：实践；来源：`nsgablack/docs/standard_scaffold_tutorial/10_custom_bias.md`。本节按当前工作树合订；如与原创主卷或实时源码冲突，以原创主卷标注的规范和实时源码为准。

本章讲如何在不破坏边界的前提下，做“可解释的软引导”。

## 1. Bias 的职责

Bias 负责：

- 偏好引导
- 先验注入
- 软约束倾向

Bias 不负责：

- 重写 objective/constraint 定义（Problem 负责）
- 取代 Adapter 搜索策略（Adapter 负责）
- 全局编排与资源发放（Project substrate / L0 负责）

---

## 2. 创建 Bias 文件

```powershell
python -m nsgablack project add-component --case my_solver --kind bias --name my_bias
```

---

## 3. 最小 Bias 示例

```python
class MyBias:
    def __init__(self, alpha: float = 0.1):
        self.alpha = float(alpha)

    def apply(self, candidates, context=None):
        # 示例：轻微收缩，避免过大步长
        return candidates * (1.0 - self.alpha)
```

---

## 4. 三种常见 Bias 设计

### 4.1 初始化偏置

- 影响初始群体分布
- 不影响 objective 定义

### 4.2 候选排序偏置

- 在同质量候选中优先某类结构
- 例如更平滑、更稀疏、更低成本

### 4.3 探索-开发偏置

- 根据 `phase` 改变偏好
- 例如 `explore` 增强多样性，`exploit` 增强局部收敛

---

## 5. 挂载建议

常见做法：

- 在 adapter 内读取 bias manager（推荐）
- 或在 solver propose/update 前后显式调用

关键是：Bias 影响路径必须可审计，不能“静默生效”。

---

## 6. 审计字段建议

每次运行至少记录：

- bias key
- bias 参数
- 启用阶段（哪些 generation/phase）
- 与无 bias 基线差异（最好有指标）

---

## 7. 常见坑

1. Bias 做成硬约束替代  
   修复：硬约束仍在 Problem/repair。

2. Bias 逻辑写进 repair 导致边界混乱  
   修复：repair 仅做可行性兜底，策略偏好放 bias/adapter。

3. Bias 改写 context 大对象  
   修复：只写轻量元数据，重对象走 snapshot/artifact。

---

# Plugin 十钩子生命周期

> 文档状态：实践；来源：`nsgablack/docs/standard_scaffold_tutorial/11_custom_plugin_hooks.md`。本节按当前工作树合订；如与原创主卷或实时源码冲突，以原创主卷标注的规范和实时源码为准。

本章是“能直接抄”的插件说明书，覆盖 10 个统一钩子与一个可运行样例。

## 0. 插件定位

Plugin 是能力层，不是算法层。

Plugin 负责：

- 观测
- 审计
- 持久化
- 报告

Plugin 不负责：

- 改写 Adapter 的 propose/update 语义
- 接管 Project 编排

---

## 1. 10 个统一钩子

按生命周期顺序：

1. `on_solver_init(self, solver)`
2. `on_population_init(self, population, objectives, violations)`
3. `on_generation_start(self, generation)`
4. `on_evaluate_start(self, candidate, context=None)`
5. `on_evaluate_end(self, candidate, feedback, context=None)`
6. `on_step(self, solver, generation)`
7. `on_generation_end(self, generation)`
8. `on_solver_finish(self, result)`
9. `on_error(self, error, context=None)`
10. `on_context_build(self, context) -> context`

---

## 2. 创建 Plugin 文件

```powershell
python -m nsgablack project add-component --case my_solver --kind plugin --name trace_audit_plugin
```

---

## 3. 可运行完整样例（10 钩子全实现）

```python
from __future__ import annotations

import time
from typing import Any, Dict, Optional

from nsgablack.plugins.base import Plugin


class TraceAuditPlugin(Plugin):
    context_requires = ()
    context_provides = ("plugin.trace.events",)
    context_mutates = ("metrics.plugin_trace_count",)
    context_cache = ()
    context_notes = "记录关键生命周期事件，并输出轻量审计统计。"

    def __init__(self, name: str = "trace_audit_plugin"):
        super().__init__(name=name, priority=100)
        self.events = []
        self._t0 = None

    def _push(self, event: str, payload: Optional[Dict[str, Any]] = None):
        self.events.append(
            {
                "ts": time.time(),
                "event": event,
                "payload": dict(payload or {}),
            }
        )

    def on_solver_init(self, solver):
        self._t0 = time.time()
        self._push("on_solver_init", {"solver": type(solver).__name__})

    def on_population_init(self, population, objectives, violations):
        n = len(population) if population is not None else 0
        self._push("on_population_init", {"population_size": int(n)})

    def on_generation_start(self, generation: int):
        self._push("on_generation_start", {"generation": int(generation)})

    def on_evaluate_start(self, candidate, context: Optional[Dict[str, Any]] = None):
        self._push("on_evaluate_start", {"has_context": isinstance(context, dict)})

    def on_evaluate_end(self, candidate, feedback, context: Optional[Dict[str, Any]] = None):
        self._push("on_evaluate_end", {"feedback_type": type(feedback).__name__})

    def on_step(self, solver, generation: int):
        self._push("on_step", {"generation": int(generation)})

    def on_generation_end(self, generation: int):
        self._push("on_generation_end", {"generation": int(generation)})

    def on_solver_finish(self, result: Dict[str, Any]):
        elapsed = 0.0 if self._t0 is None else time.time() - self._t0
        self._push("on_solver_finish", {"elapsed_s": float(elapsed)})

    def on_error(self, error: BaseException, context: Optional[Dict[str, Any]] = None):
        self._push("on_error", {"error": f"{type(error).__name__}: {error}"})

    def on_context_build(self, context: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(context or {})
        out.setdefault("plugin.trace.events", len(self.events))
        metrics = dict(out.get("metrics", {}) or {})
        metrics["plugin_trace_count"] = int(len(self.events))
        out["metrics"] = metrics
        return out

    def get_report(self):
        return {
            "events_total": len(self.events),
            "last_event": None if not self.events else self.events[-1]["event"],
        }
```

---

## 4. 在 build_solver 中挂载

```python
from .plugins.trace_audit_plugin import TraceAuditPlugin

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    del config, resource_context, component_overrides
    solver = make_solver_somehow()
    solver.add_plugin(TraceAuditPlugin())
    return solver
```

---

## 5. 三类插件实战模式

### 5.1 观测型

- trace
- module report
- profiler

重点在低开销与结构化输出。

### 5.2 控制型

- early-stop/budget guard
- timeout guard

重点在严格失败策略与可审计原因。

### 5.3 存储型

- checkpoint
- artifact exporter
- experiment logger

重点在 snapshot/artifact 边界清晰。

---

## 6. 必须遵守的安全线

1. 短路评估必须保证返回 shape 合法。  
2. plugin 异常默认 soft-error，除非显式 strict。  
3. 不把大对象直接写 context。  
4. 不在 plugin 中私建全局资源池。  

---

## 7. 快速自检命令

```powershell
python run_project.py --check --build-check
python -m nsgablack project doctor --path . --build --strict --format problem
```

若是评估链相关 plugin，务必补测：

- 单点评估路径
- 批量评估路径
- plugin 短路路径

---

# Pipeline 编排与组件设计

> 文档状态：实践；来源：`nsgablack/docs/standard_scaffold_tutorial/12_pipeline_orchestration_and_component_design.md`。本节按当前工作树合订；如与原创主卷或实时源码冲突，以原创主卷标注的规范和实时源码为准。

本章是“设计规范 + 可运行习惯”的组合手册。

## 1. 目录粒度标准

Case 级只有一个 pipeline 主入口：

```text
pipeline/main.py
```

细粒度算子落到：

```text
pipeline/operators/<slot>/<operator>.py
```

推荐 slots（搜索语义向）：

- `init`
- `mutate`
- `repair`
- `encode`
- `decode`
- `custom`

---

## 2. 组件粒度标准（什么时候拆文件）

一个 operator 文件建议满足：

1. 单一职责
2. 输入输出稳定
3. 可独立单测
4. 可复用于多个 Case

应避免：

- 一个 `main.py` 写几百行 if/else 策略逻辑
- 同时混入数据准备、搜索策略、报告逻辑

---

## 3. 编排模式建议

### 3.1 serial：可解释优先

适合：

- 基线
- 需要严格顺序的处理链

### 3.2 parallel：多分支探索

适合：

- 多种变异/修复候选并行产生
- 需要融合不同策略输出

注意：

- 提前约定 merge 策略
- 提前统一分支输出 shape

### 3.3 router：按 context 路由

适合：

- 不同阶段（explore/exploit）
- 不同任务标签（task_kind）

注意：

- `selector_key` 明确
- route 完整
- strict/fallback 策略明确

---

## 4. 典型完整示例（可直接改造）

```python
pipeline_spec = {
    "key": "search_v1",
    "slots": (
        {"slot": "init", "mode": "serial", "operators": ("uniform_init",)},
        {"slot": "mutate", "mode": "router", "selector_key": "phase",
         "routes": {"explore": "wide_mutate", "exploit": "local_mutate"},
         "default_operator": "local_mutate"},
        {"slot": "repair", "mode": "serial", "operators": ("clip_repair", "project_repair")},
        {"slot": "encode", "mode": "serial", "operators": ("typed_encode",)},
        {"slot": "decode", "mode": "serial", "operators": ("typed_decode",)},
    ),
}
```

---

## 5. 与 Adapter / Problem 的边界协作

- pipeline：处理表示流转
- adapter：控制候选生成与反馈更新
- problem：定义 objective/constraint 语义

不要把：

- objective 逻辑塞进 pipeline
- mutate 策略塞进 problem
- 数据修复策略塞进 adapter 大杂烩

---

## 6. 运行与审计建议

每次调整 pipeline spec 后，建议输出：

- 生效 `pipeline_spec.key`
- 每个 slot 的 mode
- 每个 slot 的 operators 列表

如果开了 parallel/router，再额外输出：

- parallel merge 策略
- router selector_key 与命中 route

---

## 7. 快速检查清单

- [ ] Case 仅一个 pipeline 主入口
- [ ] 每个 slot 的 operator 都在 registry 可解析
- [ ] serial/parallel/router 参数完整
- [ ] strict/fallback 行为明确
- [ ] doctor 无新增错误
- [ ] `--check --build-check` 能通过

---

# 复杂模型组合与 I/O Contract

> 文档状态：实践；来源：`mlblack/docs/standard_scaffold_tutorial/03_model_composition_and_io_contract.md`。本节按当前工作树合订；如与原创主卷或实时源码冲突，以原创主卷标注的规范和实时源码为准。

这一章是当前教程的核心增强：`mlblack` 现在可以严谨表达多模型组合，但不把组合训练顺序写成私有运行器。组合模型负责 inference/evaluation 语义；训练顺序、并行和资源属于共享 Project substrate。详见 [04_nsgablack_orchestration_and_resource_layers.md](04_nsgablack_orchestration_and_resource_layers.md)。

## 1. 核心原则

```text
复杂模型不是复杂 trainer。
复杂模型 = 多个 component model + 显式 I/O contract + prediction integration spec。
```

不要写：

```text
HybridTrainer
ResidualPrivateRunner
MultiModalTrainer
StackingRuntime
BoostingFlow
```

应该写：

```text
ModelConditionedTargetComponent:
  用已训练模型生成下一阶段数据/目标。

IntegratedPredictionModel:
  用显式 I/O contract 路由输入，并组合多个已训练模型的输出。

Project stage/group/serial:
  决定这些 component model 如何训练、何时训练、并行还是串行。
```

## 2. 两个核心组件

### 2.1 ModelConditionedTargetComponent

位置：

```text
mlblack.pipeline.model_conditioning
```

用途：训练下一阶段前，调用已经训练好的模型。

残差：

```text
y_next = y - main_model.predict(X)
```

stacking：

```text
X_next = [X, main_model.predict(X)]
y_next = y
```

distillation：

```text
y_next = teacher_model.predict(X)
```

### 2.2 IntegratedPredictionModel

位置：

```text
mlblack.models.composition
```

用途：把多个已训练模型组合成最终模型。

```text
final.predict(inputs)
  -> route each component input
  -> component.predict(component_input)
  -> validate output shape
  -> integrate predictions
```

当前支持：

```text
additive / sum / residual_sum
mean / average
```

后续可以扩展：learned linear fusion、gated fusion、router fusion、probability calibration fusion、rank fusion。

## 3. I/O Contract 为什么必要

不能假设所有 component 都吃同一个 `X`。

| 场景 | component 输入 |
| --- | --- |
| 残差 | main 和 residual 都吃同一个 numeric X |
| stacking | stage2 吃 `[X, stage1_pred]` |
| 多模态 | text 吃 token ids，image 吃 NCHW tensor，tabular 吃 numeric matrix |
| 主线 + 修正器 | main 吃全局特征，correction 吃局部特征 |
| 专家模型 | 每个 expert 吃自己的特征子集或模态 |

所以组合模型必须显式声明：

```text
component name -> input key
input kind
input ndim
input n_features
output kind
row alignment requirement
```

## 4. PredictionInputSpec

```python
from mlblack.models import PredictionInputSpec

PredictionInputSpec(
    key="tabular",
    kind="numeric_array",
    ndim=2,
    n_features=16,
    required=True,
)
```

字段：

| 字段 | 含义 |
| --- | --- |
| `key` | 从 `predict(inputs)` 的 mapping 里取哪个 key |
| `kind` | `numeric_array` / `array` / `tensor_like` / `any` |
| `ndim` | 维度要求，例如 tabular=2、image=4、tokens=2 |
| `n_features` | 2D numeric 输入的 feature 数 |
| `required` | 缺失时是否报错 |

## 5. PredictionOutputSpec

当前 integration 消费的是 point vector：

```text
允许:
  shape=(n,)
  shape=(n, 1)

拒绝:
  shape=(n, k), k>1
  row count 不一致
```

这保证 additive / mean 不会误把多维 logits、embedding 或 interval 当作 scalar prediction 直接相加。

## 6. 同输入残差模型

训练阶段：

```python
from mlblack.pipeline import ModelConditionedTargetComponent
from mlblack.presets import build_orthogonal_linear_point_trainer

# stage 1 已经由某个 trainer 得到 main_model
residual_data = ModelConditionedTargetComponent().build(
    data,
    reference_model=main_model,
)

residual_trainer = build_orthogonal_linear_point_trainer(
    residual_data,
    learning_rate=0.2,
    energy_threshold=None,
)
residual_result = residual_trainer.fit(max_steps=120)
```

整合阶段：

```python
from mlblack.models import PredictionIntegrationComponent

final_model = PredictionIntegrationComponent.additive(
    component_order=("main", "residual"),
).compose(
    {"main": main_model, "residual": residual_result.best_model},
)

prediction = final_model.predict(X_numeric)
```

解释：

```text
非 mapping 输入会作为 shared input 给每个 component。
final = main.predict(X) + residual.predict(X)
```

## 7. 不同输入多模态模型

```python
from mlblack.models import (
    PredictionIOContract,
    PredictionInputSpec,
    PredictionIntegrationComponent,
)

io_contract = PredictionIOContract.by_component({
    "tabular": PredictionInputSpec(key="tabular", ndim=2, n_features=12),
    "image": PredictionInputSpec(key="image", ndim=4),
    "text": PredictionInputSpec(key="input_ids", ndim=2),
})

final_model = PredictionIntegrationComponent.additive(
    component_order=("tabular", "image", "text"),
    weights={"tabular": 0.4, "image": 0.3, "text": 0.3},
    io_contract=io_contract,
).compose({
    "tabular": tabular_model,
    "image": image_model,
    "text": text_model,
})

prediction = final_model.predict({
    "tabular": X_tabular,
    "image": X_image,
    "input_ids": X_tokens,
})
```

这个模型不关心三个 component 是怎么训练出来的。可能是：

```text
tabular_model: orthogonal linear / tree / MLP
image_model: tiny CNN / pretrained wrapper
text_model: tiny Transformer / pretrained wrapper
```

训练顺序由共享 Project substrate 控制；如果训练选择本身需要优化搜索，再由 `nsgablack` 语义 Case 提供外层搜索。

## 8. Stacking

Stage 1：训练 base model。

```python
base_result = base_trainer.fit(max_steps=50)
base_model = base_result.best_model
```

Stage 2：把 base prediction 追加成 feature。

```python
from mlblack.pipeline import ModelConditionedTargetComponent, ModelConditionedTargetConfig

stack_data = ModelConditionedTargetComponent(
    reference_model=base_model,
    config=ModelConditionedTargetConfig(
        mode="identity",
        reference_name="base",
        append_prediction_feature=True,
        prediction_feature_name="base_pred",
    ),
).build(data)

meta_trainer = build_orthogonal_linear_point_trainer(stack_data)
meta_result = meta_trainer.fit(max_steps=80)
```

最终模型有两种方式：

```text
方式 A:
  只使用 meta_model，并在推理前重复同样的 feature transform。

方式 B:
  写一个 composition wrapper，先调用 base_model 生成 base_pred，再调用 meta_model。
```

当前已有能力覆盖方式 A。方式 B 后续可作为 `SequentialPredictionModel` 扩展，仍然是 model semantic，不是私有运行器。

## 9. Boosting-like 多轮残差

概念：

```text
model_0 fits y
model_1 fits y - model_0(X)
model_2 fits y - model_0(X) - model_1(X)
...
final = sum_i model_i
```

落层：

```text
Project serial stages:
  stage i decides whether to train another residual learner and with what budget

mlblack:
  ModelConditionedTargetComponent builds residual target
  IntegratedPredictionModel additive-composes learned models
```

伪代码：

```python
components = {}
current_integrated = None
current_data = data

for i in range(num_rounds):
    trainer = build_trainer(stage_specs[i], current_data)
    result = trainer.fit(max_steps=stage_steps[i])
    components[f"round_{i}"] = result.best_model

    current_integrated = PredictionIntegrationComponent.additive(
        component_order=tuple(components),
    ).compose(components)

    current_data = ModelConditionedTargetComponent().build(
        data,
        reference_model=current_integrated,
    )
```

注意：这个循环如果是正式工程，不应在 `mlblack` 主干里做成私有运行器；应在 Project stage 编排里做。

## 10. 主线 + 修正器

```text
main_model:
  学全局趋势，例如低频、线性、物理主项。

correction_model:
  学局部误差，例如非线性、小区域、异常模式。

final:
  main + alpha * correction
```

```python
final_model = PredictionIntegrationComponent.additive(
    component_order=("main", "correction"),
    weights={"main": 1.0, "correction": 0.3},
).compose({
    "main": main_model,
    "correction": correction_model,
})
```

`alpha` 可以固定，也可以作为外层搜索 Case 的候选字段。

## 11. 专家模型 + Late Fusion

```text
expert_a: handles small x range
expert_b: handles large x range
expert_c: handles sparse or high-noise region
fusion: weighted mean or learned gate
```

当前可做：

```text
weighted additive / mean fusion
```

后续扩展：

```text
GatedIntegratedPredictionModel:
  gate_model.predict(X) -> weights per row
  final = sum_i gate_i(X) * expert_i(X)
```

这仍然属于 `mlblack.models.composition`，不是私有运行器。

## 12. Contract fail-fast 示例

```python
io_contract = PredictionIOContract.by_component({
    "image": PredictionInputSpec(key="image", ndim=4),
})

model.predict({"image": X_2d})
# raises: component 'image' input must be 4D
```

```python
class BadModel:
    def predict(self, X):
        return np.ones((len(X), 3))

# additive expects point vector, so this fails.
```

Fail-fast 是必须的。组合模型如果默默广播或 reshape，会让 outer search 学到错误反馈。

## 13. Artifact

组合模型会输出 `integrated_model` artifact：

```python
from mlblack.core import ArtifactBuilder

bundle = ArtifactBuilder().build(trainer_like, result_like)
assert bundle.model_artifact.describe()["artifact_type"] == "integrated_model"
```

推荐 metadata：

```text
component model names
component artifact refs
integration kind
weights
I/O contract
orchestration_owner = project_substrate
source stage ids
```

## 14. 多阶段残差编排示例（Project substrate + mlblack Cases）

核心模式见 [04_nsgablack_orchestration_and_resource_layers.md](04_nsgablack_orchestration_and_resource_layers.md) 的串行阶段部分，每个 stage 执行：

1. Project runner 按 stage 调用标准 Case builder，并注入 `resource_context`
2. 内层不关心 data 来源，统一构造，不同 stage 雖然数据不同
3. ResourceContext 垂直流通，mlblack case 消费并审计 grant
4. Artifact 水平流转、序列传递
5. 最后 IntegratedPredictionModel 整合

---

## 15. 什么时候要新增新组件

| 需求 | 新增位置 |
| --- | --- |
| 新融合公式 | `PredictionIntegrationSpec` / composition model |
| 行级动态 gate | composition model + gate model |
| 多输出融合 | `PredictionOutputSpec` 扩展 |
| 顺序调用模型 | sequential model wrapper |
| 训练阶段编排 | Project substrate，不进 mlblack |
| 多设备分配 | shared Project L0 substrate，不进 mlblack 语义组件 |
| artifact 跨阶段 | Project substrate，不进 mlblack |

---

## 参考

- 嵌套编排完整设计：[04_nsgablack_orchestration_and_resource_layers.md](04_nsgablack_orchestration_and_resource_layers.md)

---

# ML 验收、Catalog 与 Artifact

> 文档状态：实践；来源：`mlblack/docs/standard_scaffold_tutorial/06_validation_catalog_artifacts.md`。本节按当前工作树合订；如与原创主卷或实时源码冲突，以原创主卷标注的规范和实时源码为准。

这一章讲怎么判断一个组件或 case 是否符合架构。重点不是“能不能跑”，而是能不能审计、复现、查询和长期演进。

## 1. 最小验收命令

```powershell
python -m pytest -q tests
python -c "from mlblack.project import run_project_doctor, format_doctor_report; print(format_doctor_report(run_project_doctor('.', strict=True)))"
```

常见专项：

```powershell
python -m pytest -q tests\test_model_integration.py
python -m pytest -q tests\test_neural_graph_codec.py
python -m pytest -q tests\test_symbolic_nsgablack_integration.py
```

## 2. Doctor 检查什么

Doctor 关注：

```text
context contract key 是否注册
component contract 是否可解析
是否重新出现私有运行器、私有调度器、私有资源申请等禁用口径
core/resource 是否仍为 passive ResourceContext
single-trainer assembly 是否没有外层编排字段
catalog 是否能解析组件
```

Doctor 不是性能测试，也不能替代 case smoke。

## 3. Context contract

组件应声明：

```python
context_requires = (...)
context_optional = (...)
context_provides = (...)
context_mutates = (...)
context_cache = (...)
requires_metrics = (...)
metrics_fallback = "strict"
context_notes = "..."
```

规则：

```text
requires:
  必须存在，否则组件不能正确运行。

optional:
  有则使用，没有也能运行。

provides:
  组件完成后对外提供什么。

mutates:
  会修改的状态边界。

cache:
  可复用但非语义必需的缓存。
```

## 4. Catalog

Catalog 的目标是组件发现，不是私有执行面。

应能查到：

```text
trainer
adapter
representation
problem
pipeline
backend capability
dashboard
artifact viewer
model composition component
```

推荐新增组件时加 catalog entry：

```text
key: model.integrated_prediction
kind: model
tags: composition, integration, residual, stacking
summary: Combines named fitted model predictions without owning training orchestration.
```

## 5. Artifact 边界

Artifact 应回答：

```text
这个模型/表达式是什么？
怎么得到的？
用了哪些组件？
数据和资源上下文是什么？
核心指标是什么？
能否恢复/重放？
```

不要把 artifact 写成 adapter side effect。应由 trainer result、problem build artifact hook、ArtifactBuilder 或 reporting layer 统一生成。

## 6. Artifact 类型

| artifact | 必备信息 |
| --- | --- |
| model | model type, family, head, representation |
| integrated_model | component refs, integration spec, I/O contract |
| neural_graph | graph spec, parameter layout, audit maps |
| tree/xgboost | estimator params, fitted state summary |
| symbolic_model | expression, canonical payload, recovery report |
| trainer_state | adapter/trainer state signature |
| run_report | metrics, resources, components |

## 7. Snapshot vs Context

Context 只放轻量字段：

```text
run_name
step
resource.*
best_score
artifact_ref
snapshot_key
small metrics
```

大对象进 snapshot/artifact：

```text
population
full history
model object
large arrays
trace
attention maps
symbolic graph cache
```

## 8. Dashboard

Dashboard 是查看面，不是执行面。

| dashboard | 用途 |
| --- | --- |
| catalog dashboard | 看组件和 contract |
| backend matrix | 看 backend capability |
| artifact viewer | 看 typed artifact |
| experiment dashboard | 查 runs/metrics |
| benchmark dashboard | 多 run 聚合 |

## 9. Case summary 验收

正式 case summary 至少包含：

```text
suite_id
protocol
config
stage reports
effective resource context
component reports
artifact refs
best record
failure records
runtime summary
```

组合模型 case 还应包含：

```text
component model names
component artifact refs
PredictionIOContract
PredictionIntegrationSpec
integration metrics
```

符号 case 还应包含：

```text
canonical key
truth recovery
family recovery
phase equivalence
basis artifact lineage
```

## 10. 禁止回归检查

每次大改后，人工检查是否出现：

```text
mlblack.private_orchestrator
mlblack.private_runtime
ResourceRequest
PrivateResourceAllocator
StageRunner
HybridTrainer
MultiModalPrivateRunner
ResidualPrivateRunner
adapter directly reads X/y
problem directly chooses backend by get_backend("torch")
codec silently switches backend
```

出现这些通常说明边界开始倒退。

## 11. 新组件 PR 检查表

```text
[ ] 归属层是否明确
[ ] 是否声明 context contract
[ ] 是否避免 adapter 直接读数据
[ ] 是否避免大对象写 context
[ ] 是否有 describe()
[ ] 是否能进 catalog 或文档索引
[ ] 是否有至少一个 smoke/unit test
[ ] 是否能被 ArtifactBuilder 或 reporting surface 描述
[ ] 是否没有新增 mlblack 私有编排或私有 L0
```

## 12. 推荐验证矩阵

| 改动 | 最小验证 |
| --- | --- |
| pipeline/data | `tests/test_pipeline_datasets.py` + doctor |
| model composition | `tests/test_model_integration.py` |
| neural graph | `tests/test_neural_graph_codec.py` |
| backend | `tests/test_compute_backend_session.py` + backend matrix |
| symbolic | `tests/test_symbolic_nsgablack_integration.py` |
| docs only | rg links + optional doctor |
| cross-framework case | case `--check` |

---

# Benchmark、Dashboard 与资源审计

> 文档状态：参考；来源：`mlblack/docs/standard_scaffold_tutorial/07_benchmark_dashboard_resource.md`。本节按当前工作树合订；如与原创主卷或实时源码冲突，以原创主卷标注的规范和实时源码为准。

这一章讲工程化运行面：如何跑 benchmark、如何看 dashboard、如何审计资源上下文，以及如何区分 benchmark runner 和正式 case。

## 1. Benchmark 第一原则

Benchmark 不应复制 case 装配逻辑。

```text
正确:
  benchmark runner 调用正式 case surface，多次运行并聚合结果。

错误:
  benchmark runner 重新实现 stage1/stage2 problem、artifact schema、resource handling。
```

## 2. Benchmark 输出结构

推荐：

```text
examples/cases/benchmarks/runs/<benchmark_id>/
  benchmark_summary.json
  benchmark_dashboard.html
  runs/
    <suite_id_0>/...
    <suite_id_1>/...
```

`benchmark_summary.json` 至少包含：

```text
benchmark_id
case
protocol
repeats
seeds
config projection
resource context
per-run scores
aggregate statistics
artifact refs
failure records
```

## 3. 指标聚合

推荐记录：

| 指标 | 用途 |
| --- | --- |
| mean / std | 稳定性 |
| min / max | 极端情况 |
| median | 抗异常 |
| success rate | 可用性 |
| failure kind count | 失败归因 |
| wall time | 性能 |
| artifact write time | 工程开销 |

## 4. 资源审计

`ResourceAuditPlugin` 只记录外部注入的资源上下文。

```python
spec = {
    "preset": "orthogonal_linear_point",
    "resource_context": {
        "device": "cpu",
        "threads": 1,
        "namespace": "benchmark.run.0",
    },
    "plugins": ["resource_audit"],
}
```

Report 中应该看到：

```text
resources.device
resources.threads
resources.namespace
compute_backend.resolved_name
```

## 5. L0 边界

| 能力 | 归属 |
| --- | --- |
| outer solver fanout | shared Project substrate |
| worker pool | shared Project L0 substrate |
| GPU/CPU lease | shared Project L0 substrate |
| backend/thread/process scheduling | shared Project L0 substrate |
| inner compute backend | mlblack trainer/backend |
| resource audit | mlblack Plugin |

`mlblack` 可以遵守 `ResourceContext`，不能自己授权资源。

## 6. Dashboard 类型

| dashboard | 来源 | 展示 |
| --- | --- | --- |
| catalog | `mlblack.catalog` | 组件、contract、tags |
| backend matrix | `mlblack.catalog.backend_dashboard` | backend capability |
| artifact viewer | `mlblack.catalog.artifacts` | artifact schema |
| experiment | `mlblack.catalog.experiment` | run records |
| benchmark | benchmark runner/reporting | 多 run 聚合 |

## 7. Artifact viewer 最低要求

普通 model artifact：

```text
model_type
family/head
representation summary
problem summary
adapter summary
metrics
resources
```

integrated model artifact：

```text
component names
component model types
component artifact refs
PredictionIntegrationSpec
PredictionIOContract
weights
final metrics
```

symbolic artifact：

```text
final expression
canonical expression
truth recovery
family recovery
phase equivalence
lineage
```

neural graph artifact：

```text
graph spec
parameter layout
audit maps / summaries
backend
optimizer state summary
```

## 8. Smoke 验证矩阵

基础：

```powershell
python -m pytest -q tests
python -c "from mlblack.project import run_project_doctor, format_doctor_report; print(format_doctor_report(run_project_doctor('.', strict=True)))"
```

单 trainer：

```powershell
python examples\cases\orthogonal_point_demo\run_project.py --check --build-check
```

组合模型：

```powershell
python -m pytest -q tests\test_model_integration.py
```

神经图：

```powershell
python -m pytest -q tests\test_neural_graph_codec.py
```

符号 nested：

```powershell
python examples\cases\symbolic_orthogonal_nested\run_project.py --check --build-check
python -m pytest -q tests\test_symbolic_nsgablack_integration.py
```

## 9. Benchmark 分类

| 类型 | 目的 | 规模 |
| --- | --- | --- |
| smoke benchmark | 能跑通 | 1-2 runs，小 steps |
| regression benchmark | 防退化 | 固定 seeds，中等 steps |
| stress benchmark | 找瓶颈 | 大 population/steps |
| backend benchmark | 比较后端 | numpy/jax/tf/torch matrix |
| composition benchmark | 比较组合模式 | baseline/residual/stacking/fusion |
| symbolic recovery benchmark | 看 truth/family/phase recovery | synthetic truth set |

## 10. 组合模型 benchmark 示例

```text
case: residual_vs_baseline
runs:
  baseline linear
  baseline orthogonal
  main + residual
  main + residual + residual2
  stacking base_pred feature
metrics:
  train/valid mse
  complexity
  component count
  total fit time
  artifact size
```

关键：benchmark runner 只组合正式 case surface，不重新写训练逻辑。

## 11. Backend benchmark 示例

```text
same MLP spec:
  numpy inference/loss
  jax functional grad
  tensorflow GradientTape
  torch backprop

record:
  capability support
  fit status
  loss after N steps
  wall time
  failure reason
```

不要为了比较而让 backend 假装支持不存在的 capability。

## 12. 报告字段建议

正式 benchmark report：

```json
{
  "benchmark_id": "...",
  "protocol": "mlblack.benchmark.v1",
  "case": "...",
  "runs": [],
  "aggregate": {
    "valid.mse.mean": 0.0,
    "valid.mse.std": 0.0,
    "success_rate": 1.0
  },
  "resources": {},
  "artifacts": {},
  "failures": []
}
```

## 13. 发布前建议

```text
[ ] tests 全量通过
[ ] doctor ok
[ ] catalog/dashboard 可导出
[ ] artifact viewer 能展示新增 artifact
[ ] benchmark small 至少一轮成功
[ ] failure records 可读
[ ] 资源上下文可审计
```

---

# ML Slot Kernel 最小规范

> 文档状态：实践；来源：`mlblack/docs/standard_scaffold_tutorial/09_slot_kernel_minimal_spec.md`。本节按当前工作树合订；如与原创主卷或实时源码冲突，以原创主卷标注的规范和实时源码为准。

本章是 mlblack 的中文实战手册，重点是：

1. 明确和 nsgablack 的 pipeline 语义差异  
2. 保持共享 slot kernel 编排契约  
3. 给出可直接运行的多组示例

## 0. 先把差异说清楚

两边都用一个 `pipeline/main.py` + slot spec，但语义不同：

- `nsgablack`：搜索表示流（`init/mutate/repair/encode/decode`）
- `mlblack`：训练语义流（`transform/codec/head`）

所以：

- 编排统一（slot kernel）
- 组件语义不同（搜索 vs codec/head）

---

## 1. 从空项目开始（trainer case）

```powershell
python -m nsgablack project new demo_slot_kernel_ml
cd demo_slot_kernel_ml
python -m nsgablack project add-case my_trainer --type trainer --framework mlblack
```

---

## 2. 用 CLI 创建 pipeline 内部组件

```powershell
python -m nsgablack project add-component --case my_trainer --kind pipeline --slot main --name main
python -m nsgablack project add-component --case my_trainer --kind pipeline --slot transform --name zscore_transform
python -m nsgablack project add-component --case my_trainer --kind pipeline --slot codec --name linear_codec
python -m nsgablack project add-component --case my_trainer --kind pipeline --slot head --name point_head
```

---

## 3. `pipeline/main.py` 装配范式（可抄）

```python
from typing import Any, Mapping
from mlblack.pipeline import PipelineSpec, build_pipeline_kernel


def build_pipeline(*, resource_context: Mapping[str, Any] | None = None, component_overrides: Mapping[str, Any] | None = None):
    del resource_context
    overrides = dict(component_overrides or {})
    registry = dict(overrides.get("pipeline_operators", {}) or {})
    spec = PipelineSpec.from_value(
        overrides.get("pipeline_spec", {"key": "trainer_default", "slots": ()})
    )
    kernel = build_pipeline_kernel(spec, operator_registry=registry, transform_slot="transform")
    return kernel.data_pipeline
```

---

## 4. 三种模式实战示例

### 4.1 serial：标准单链训练流

```python
pipeline_spec = {
    "key": "train_serial_v1",
    "slots": (
        {"slot": "transform", "mode": "serial", "operators": ("zscore_transform", "feature_build")},
        {"slot": "codec", "mode": "serial", "operators": ("linear_codec",)},
        {"slot": "head", "mode": "serial", "method": "predict", "operators": ("point_head",)},
    ),
}
```

### 4.2 parallel：多特征分支融合

```python
pipeline_spec = {
    "key": "train_parallel_feature_v1",
    "slots": (
        {
            "slot": "transform",
            "mode": "parallel",
            "operators": ("trend_branch", "seasonal_branch"),
            "merge": "mean",
        },
        {"slot": "codec", "mode": "serial", "operators": ("linear_codec",)},
    ),
}
```

### 4.3 router：按任务类型切 head

```python
pipeline_spec = {
    "key": "train_router_head_v1",
    "slots": (
        {"slot": "transform", "mode": "serial", "operators": ("zscore_transform",)},
        {"slot": "codec", "mode": "serial", "operators": ("linear_codec",)},
        {
            "slot": "head",
            "mode": "router",
            "method": "predict",
            "selector_key": "task_kind",
            "routes": {
                "point": "point_head",
                "interval": "interval_head",
                "prob": "probability_head",
            },
            "default_operator": "point_head",
        },
    ),
}
```

---

## 5. operator registry 示例

```python
pipeline_operators = {
    "zscore_transform": ZScoreTransform(),
    "feature_build": FeatureSpaceBuild(),
    "trend_branch": TrendBranchTransform(),
    "seasonal_branch": SeasonalBranchTransform(),
    "linear_codec": LinearCodec(),
    "point_head": PointHead(),
    "interval_head": IntervalHead(),
    "probability_head": ProbabilityHead(),
}
```

---

## 6. 重点：`method` 字段为什么必须掌握

mlblack 的 head 往往不是 `decode()`，而是 `predict()` 或 `forward()`。  
因此要显式指定：

```python
{"slot": "head", "method": "predict", ...}
```

否则会出现“slot 存在但方法名不匹配”的隐性错误。

---

## 7. 可直接执行的验证

```powershell
python run_project.py --check --build-check
python -m mlblack project doctor --path . --strict
```

建议额外做三类单测：

1. serial transform 链
2. parallel merge 行为
3. head router 路由行为

---

## 8. 常见错误

1. `head` 未设置 `method` 导致调用不到 `predict`
2. parallel 分支输出结构不一致导致 merge 失败
3. router `selector_key` 和 context 字段不匹配
4. 把编排写进 trainer 私有 runner（违反统一 substrate 口径）

---

## 9. 本章结论

mlblack 的 pipeline 确实和 nsgablack 不同（它是 codec/head 语义流），  
但两者应该共享同一个 slot kernel 编排契约，这样才能做到：

- 框架统一
- 语义清晰
- 可嵌套编排
- 可审计运行

---

# ML 自定义 Adapter

> 文档状态：实践；来源：`mlblack/docs/standard_scaffold_tutorial/10_custom_adapter.md`。本节按当前工作树合订；如与原创主卷或实时源码冲突，以原创主卷标注的规范和实时源码为准。

虽然 mlblack 语义是训练/模型，但 Adapter 仍然是“更新策略层”，不是私有编排层。

## 1. Adapter 边界

Adapter 可以负责：

- 参数更新策略
- 候选状态更新策略
- 与 feedback 对齐的优化步

Adapter 不应该负责：

- Project stage 编排
- 全局资源调度
- 训练数据读取与清洗主流程

---

## 2. 创建文件

```powershell
python -m nsgablack project add-component --case my_trainer --kind adapter --name my_trainer_adapter
```

---

## 3. 最小骨架（可运行思路）

```python
class MyTrainerAdapter:
    def propose(self, trainer, context):
        # 返回当前需要评估/更新的状态候选
        ...

    def update(self, trainer, candidates, objectives, violations, context):
        # 使用反馈更新内部状态
        ...
```

如果你是梯度类训练，可把 propose 理解为“当前参数态”，update 理解为“一次优化步”。

---

## 4. 挂载示例

```python
trainer = ...
trainer.set_adapter(MyTrainerAdapter(...))
```

---

## 5. 建议做的三层验证

1. `--check --build-check`：装配面正常  
2. `project doctor`：结构面正常  
3. 小步训练 smoke：更新面正常

```powershell
python run_project.py --check --build-check
python -m mlblack project doctor --path . --strict
```

---

## 6. 常见坑

1. Adapter 直接读取原始训练数据  
   修复：数据语义由 pipeline/problem 暴露给 trainer，不在 adapter 私读。

2. Adapter 内部自建资源池  
   修复：只消费 `resource_context`。

3. 把多 Case 编排逻辑塞进 Adapter  
   修复：上移到 Project substrate。

---

# ML 自定义 Bias

> 文档状态：实践；来源：`mlblack/docs/standard_scaffold_tutorial/11_custom_bias.md`。本节按当前工作树合订；如与原创主卷或实时源码冲突，以原创主卷标注的规范和实时源码为准。

mlblack 的 Bias 常用于训练语义中的软引导，例如：

- objective 权重偏置
- 参数尺度偏置
- 分支策略偏置

## 1. 创建 Bias 组件

```powershell
python -m nsgablack project add-component --case my_trainer --kind bias --name my_training_bias
```

## 2. 设计原则

- 偏置是 soft guidance，不是硬约束替代
- 不应静默改变任务定义
- 不应拥有编排/资源权限

## 3. 典型场景

### 3.1 多目标训练权重偏置

例如 point + interval 的组合中，早期强调稳定性，后期强调精度。

### 3.2 状态正则偏置

例如对参数范数做软惩罚，引导更稳定更新。

### 3.3 分支路由偏置

例如某些 task_kind 更倾向某类 head 或 codec。

## 4. 审计建议

至少记录：

- bias 名称与参数
- 生效阶段
- 与无 bias 基线对比

---

# ML Plugin 生命周期

> 文档状态：实践；来源：`mlblack/docs/standard_scaffold_tutorial/12_custom_plugin_hooks.md`。本节按当前工作树合订；如与原创主卷或实时源码冲突，以原创主卷标注的规范和实时源码为准。

mlblack capability 与 nsgablack plugin lifecycle 是统一映射关系。  
本章给你一个可以直接照抄的 10 钩子样例。

## 1. 先创建插件文件

```powershell
python -m nsgablack project add-component --case my_trainer --kind plugin --name trainer_audit_plugin
```

## 2. 10 钩子清单（统一）

1. `on_solver_init`
2. `on_population_init`
3. `on_generation_start`
4. `on_evaluate_start`
5. `on_evaluate_end`
6. `on_step`
7. `on_generation_end`
8. `on_solver_finish`
9. `on_error`
10. `on_context_build`

在 mlblack 语义下，可以把 generation/step 看成训练 step 生命周期映射。

## 3. 可运行样例（全钩子）

```python
from __future__ import annotations

import time
from typing import Any, Dict, Optional

from nsgablack.plugins.base import Plugin


class TrainerAuditPlugin(Plugin):
    def __init__(self, name: str = "trainer_audit_plugin"):
        super().__init__(name=name, priority=80)
        self.events = []
        self._t0 = None

    def _log(self, event: str, payload: Optional[Dict[str, Any]] = None):
        self.events.append({"ts": time.time(), "event": event, "payload": dict(payload or {})})

    def on_solver_init(self, solver):
        self._t0 = time.time()
        self._log("on_solver_init", {"solver": type(solver).__name__})

    def on_population_init(self, population, objectives, violations):
        self._log("on_population_init", {"n": 0 if population is None else len(population)})

    def on_generation_start(self, generation: int):
        self._log("on_generation_start", {"generation": generation})

    def on_evaluate_start(self, candidate, context=None):
        self._log("on_evaluate_start")

    def on_evaluate_end(self, candidate, feedback, context=None):
        self._log("on_evaluate_end", {"feedback_type": type(feedback).__name__})

    def on_step(self, solver, generation: int):
        self._log("on_step", {"generation": generation})

    def on_generation_end(self, generation: int):
        self._log("on_generation_end", {"generation": generation})

    def on_solver_finish(self, result):
        elapsed = 0.0 if self._t0 is None else time.time() - self._t0
        self._log("on_solver_finish", {"elapsed_s": elapsed})

    def on_error(self, error: BaseException, context=None):
        self._log("on_error", {"error": f"{type(error).__name__}: {error}"})

    def on_context_build(self, context):
        out = dict(context or {})
        out["plugin.trainer_audit.events"] = len(self.events)
        return out
```

## 4. 挂载

```python
trainer = ...
trainer.add_plugin(TrainerAuditPlugin())
```

## 5. 推荐插件实战组合

1. `TrainerAuditPlugin`：生命周期审计  
2. 资源审计插件：记录 ResourceContext 生效值  
3. artifact/report 插件：输出训练产物索引  
4. checkpoint 插件：恢复能力

## 6. 必须遵守

- plugin 只扩展能力，不改训练语义定义
- short-circuit 评估时输出形状必须合法
- 大对象用 snapshot/artifact ref，不塞 context

---

# ML Pipeline 编排与组件设计

> 文档状态：实践；来源：`mlblack/docs/standard_scaffold_tutorial/13_pipeline_orchestration_and_component_design.md`。本节按当前工作树合订；如与原创主卷或实时源码冲突，以原创主卷标注的规范和实时源码为准。

本章聚焦 mlblack 的 pipeline 设计实践：它是 codec/head 语义流，不是搜索表示流。

## 1. 结构标准

Case 级单入口：

```text
pipeline/main.py
```

内部算子：

```text
pipeline/operators/transform/*.py
pipeline/operators/codec/*.py
pipeline/operators/head/*.py
pipeline/operators/custom/*.py
```

## 2. 语义层分工

- `transform`：DataView/特征/目标变换
- `codec`：模型参数状态编码解码
- `head`：输出语义（point/interval/probability/other）

不要把这些直接混进 trainer 主循环。

## 3. 编排模式实践

### serial

标准训练链：

```text
transform -> codec -> head
```

### parallel

特征并行分支：

```text
branch_a(transform) + branch_b(transform) -> merge -> codec -> head
```

### router

按任务或场景切换：

```text
task_kind=point -> point_head
task_kind=interval -> interval_head
task_kind=prob -> probability_head
```

## 4. 组件设计建议

每个 operator 文件最好满足：

- 单一职责
- 稳定输入输出
- 明确 method（例如 `predict` / `forward`）
- 可单测

## 5. 与 nsgablack 的统一点

统一点：

- 同一 slot kernel contract
- 同一 project/case/scaffold/L0 substrate

差异点：

- nsgablack 强调搜索表示
- mlblack 强调 codec/head 训练语义

## 6. 可运行检查清单

- [ ] `pipeline/main.py` 是唯一主入口
- [ ] slot spec 和 registry 一致
- [ ] head slot 的 `method` 明确
- [ ] `--check --build-check` 通过
- [ ] doctor 严格模式通过

---

# Plugin 系统使用指南

> 文档状态：参考；来源：`nsgablack/docs/user_guide/PLUGIN_SYSTEM.md`。本节按当前工作树合订；如与原创主卷或实时源码冲突，以原创主卷标注的规范和实时源码为准。

Plugin 是 NSGABlack 的能力层：它负责并行、记录、监控、缓存等工程能力；它不承载算法策略过程，不写业务规则。

这一页讲的是：
- 什么时候该写 Plugin
- Plugin 读写什么（context keys）
- 如何把“容易漏配的伙伴组件”收敛成 Wiring

## 1. 什么时候用 Plugin

适合 Plugin 的事：
- 并行评估、批处理、线程/进程安全保护
- 统一实验口径输出（progress.csv + summary.json）
- 运行审计与“模块贡献可查”（modules.json + bias.json/bias.md）
- 统计信号写回 context（供 signal-driven bias 使用）
- 观测与治理（日志、追踪、审计、恢复）

不适合 Plugin 的事：
- 策略过程（那是 Adapter：propose/update）
- 硬约束可行化（优先在 RepresentationPipeline：init/mutate/repair）
- 业务偏好/软约束（优先在 BiasModule）

## 2. Plugin 如何通信：context keys

框架把“运行中的事实”都放在 `context`：
- Plugin 读取事实做统计/输出
- Plugin 也可以把新事实写回 context（例如 metrics），供后续组件使用

建议你优先复用 `core/state/context_keys.py` 里的规范 key，避免不同组件各写一套。

## 3. 避免漏配：用 Wiring

真实开发最容易犯的错不是“不会写”，而是“漏配”：
- 少挂一个记录插件 -> 没有可对比数据
- 少挂一个 mutator -> 算法退化但不报错
- 少写一个 context key -> signal-driven bias 失效

因此推荐把“必配组合”收敛成 Wiring，例如：
- `plugin.benchmark_harness`：统一实验口径输出
- `plugin.module_report`：模块清单 + 偏置贡献报告（自动把 artifacts 注入 benchmark summary）
- `adapter.vns` + `repr.context_gaussian` / `repr.context_switch`：VNS 相关的必配伙伴契约

补充：若通过 Run Inspector（`utils/viz/visualizer_tk.py`）启动，ModuleReport 会自动写入 `ui_snapshot`（包含 wiring 快照与路径），便于复盘“运行前到底勾选了什么”。

## 4. Catalog：发现你有哪些 Plugin/Wiring

```powershell
python -m nsgablack catalog search plugin
python -m nsgablack catalog search plugin
python -m nsgablack catalog show plugin.benchmark_harness
python -m nsgablack catalog show plugin.module_report
```

如果你遇到 `No module named nsgablack`：

```powershell
python -m pip install -e .
```

或快速试用：

```powershell
$env:PYTHONPATH=".."
python -m nsgablack catalog search plugin
```

## 5. Bias 统一 apply 规则（L4 provider 必读）

核心原则：**Bias 在每个候选解的评估生命周期中只 apply 一次。**

对于普通插件，Bias 由求解器主循环统一 apply（NSGA-II 在 `_evaluate_individual` 内部、ComposableSolver 在 evaluate step）。

对于 L4 `EvaluationProvider`（如 surrogate provider），由于 provider 进入评估中介链，关键约束是：

- `_true_evaluate()` 内部**不得** apply bias，只返回 raw objectives
- 调用并行评估器时传入 `enable_bias=False, bias_module=None`
- 训练代理模型的数据必须存储 raw objectives（未偏置）
- Bias apply 只发生在统一评估链中，且**仅此一次**

这样保证无论走原生 problem 评估还是 L4 provider，bias 都恰好 apply 一次，不会 double-bias。

> 参考：`docs/guides/DECOUPLING_CAPABILITIES.md` 与
> `docs/standard_scaffold_tutorial/04_validation_catalog_and_evolution.md`

## 6. 参考入口

- 端到端流程：`docs/standard_scaffold_tutorial/01_create_and_run.md`
- Catalog/Wiring Helpers：`docs/user_guide/catalog.md`
- 解耦导读：`docs/guides/DECOUPLING_CAPABILITIES.md`

## 7. OpenTelemetry tracing 插件（可选）

用于把关键运行路径变成 trace span（`evaluate` / `adapter` / `plugin event`），快速定位慢点和失败链路。

```python
from nsgablack.plugins import OpenTelemetryTracingPlugin, OpenTelemetryTracingConfig

solver.add_plugin(
    OpenTelemetryTracingPlugin(
        config=OpenTelemetryTracingConfig(
            service_name="nsgablack-exp",
            console_export=True,              # 本地调试
            otlp_http_endpoint="",            # 例如 http://127.0.0.1:4318/v1/traces
        )
    )
)
```

可检索：

```powershell
python -m nsgablack catalog show plugin.otel_tracing
```

---

# 并行评估

> 文档状态：参考；来源：`nsgablack/docs/user_guide/parallel_evaluation.md`。本节按当前工作树合订；如与原创主卷或实时源码冲突，以原创主卷标注的规范和实时源码为准。

并行评估属于共享 L0 substrate 的执行能力，不属于某个 Solver、Adapter 或示例脚本的私有能力。

当前推荐口径：

- Project 声明可用 CPU/thread/GPU/worker/service backend。
- Case 声明评估需求。
- `run_project.py` 发放 `ResourceContext`。
- Case 内的 solver/plugin/wiring 只消费生效 grant，并在报告中写出实际 backend 与 fallback。

## 1. Project 声明资源

```python
L0 = {
    "backend": "local",
    "resource_pool": {
        "threads": 16,
        "device_tokens": ("logical-gpu-a",),
    },
    "policy": {
        "failure_policy": "soft",
    },
}

resource_requests = {
    "main_case": {"threads": 4},
}
```

不要在 Case 代码里硬编码 `cuda:0`、全局线程池或本机 worker 名称。

## 2. Case 消费 grant

```python
def build_solver(config=None, *, resource_context=None, component_overrides=None):
    solver = make_solver(config)

    runtime = build_runtime_from_context(resource_context)
    attach_parallel_evaluation(
        solver,
        backend=runtime.evaluation_backend,
        max_workers=runtime.max_workers,
        audit=runtime.audit_payload(),
    )

    return solver
```

Case 可以选择 thread/process/Ray/remote backend，但选择依据必须来自 `resource_context` 和本地 runtime profile。若 fallback 到串行评估，必须写入 run summary 或 module report。

## 3. 单 Case 调试

独立调试时可以直接使用本地 evaluator：

```python
from nsgablack.utils.parallel import ParallelEvaluator

with ParallelEvaluator(backend="process", max_workers=4) as evaluator:
    objectives, violations = evaluator.evaluate_population(population, problem)
```

这只是调试路径。正式运行仍应从 Project L0 grant 进入。

## 4. 推荐实践

- 评估函数保持可序列化、无副作用。
- 大 payload 走 Snapshot 或 Artifact ref，不塞进 Context。
- 并行失败策略由 Project 给默认值，Case 可以局部降级但必须审计。
- 嵌套 Case 不能扩大 parent grant，只能使用 parent 派生的 child grant。
- `framework-core` 架构审计时使用 `python -m nsgablack catalog ... --profile framework-core`。

## 5. 相关入口

- `COMPUTE_FLOW_GUIDE_CN.md`
- `../standard_scaffold_tutorial/06_l0_parallel_resource_patterns.md`
- `../architecture/L0_RESOURCE_ORCHESTRATION.md`
- `../architecture/L0_TASK_RESOURCE_BACKEND_ARCHITECTURE.md`

---

# Run Inspector

> 文档状态：参考；来源：`nsgablack/docs/user_guide/RUN_INSPECTOR.md`。本节按当前工作树合订；如与原创主卷或实时源码冲突，以原创主卷标注的规范和实时源码为准。

Run Inspector 是 NSGABlack 的“结构审计”界面。
它不是画曲线的 UI，而是让你在运行前就看见 **算法结构、组件搭配、缺失伙伴、实验快照**。
UI 变更记录见：`docs/changelog/RUN_INSPECTOR_CHANGELOG.md`（每次界面行为变化都会追加）。

> 适用场景：
> - 多算法/多偏置/多插件组合时，避免“跑完才发现漏配”
> - 实验对比时，快速确认两次实验的结构差异
> - 运行后复盘：看清楚“当时到底勾选了什么”

---

## 1. 启动方式

```bash
python -m nsgablack run_inspector --entry examples/cases/dynamic_strategy/cases/dynamic_strategy/build_solver.py:build_solver
```

- `--entry` 指向你的 `build_solver()` 函数。
- 运行后，会读取当前 solver wiring，并展示可开关的组件。

Run Inspector 的 Load 会直接调用 `build_solver()` 构建 wiring。
为避免 UI 加载触发重计算，`build_solver()` 必须只做装配，重任务延迟到 `run()` / `evaluate()`。

空启动模式（先用 Catalog 搜索，再 Load 文件）：

```bash
python -m nsgablack run_inspector --empty --workspace .
```

在 UI 顶部可直接：
- `Load`：选择/输入 `*.py` + 函数名（默认 `build_solver`）后加载
- `Refresh`：代码改动后重新读取当前 entry
- `View`：一键切换工作视图（单击按钮即可）
  - `Build(装配)`：Details / Catalog / Context（找组件与字段对齐）
  - `Run(实验)`：Run / Decision / Sequence / Repro / Contribution / Trajectory / Catalog（执行、回放、复现与对比）
  - `Audit(审计)`：Details / Decision / Sequence / Repro / Context / Doctor / Contribution（排障与治理）
  - 注意：三种视图是**分工视图，不是层层累加**

---

## 2. 界面总览（你会看到什么）

左侧：**结构清单（wiring）**
- Solver / Adapter / Pipeline / Bias / Plugin
- 每个条目可勾选启用/禁用（固定项会灰显）

中间：**History（实验记录）**
- 每次 Run 会写入一条记录
- 自动显示 run_id、状态、结果、结构 hash

右侧：**功能面板（Tabs）**
- Details：单个组件详情 + Health
- Run：运行控制 + Run ID
- Decision：决策路径回放（why/when）
- Sequence：交互顺序图（序列去重，只看结构，不看数值）
- Repro：复现包加载/对比/按包重跑
- Contribution：模块贡献、对比、结构 hash 图谱
- Trajectory：策略权重轨迹（dynamic_switch）
- Catalog：组件搜索入口
- Context：上下文字段生命周期与归因
- Doctor：项目结构/契约体检
  - `Strict` 模式下会额外显示守卫计数：`mirror`（solver 镜像写入）与 `plugin-state`（插件直接访问 solver population/objectives/violations）

---

## 3. 结构清单（wiring）怎么用

### 3.1 勾选 / 取消勾选
- Bias、Pipeline、Plugin 通常可开关
- Adapter 本体通常固定（灰显）
- 多策略协同会显示 `strategy: xxx`

### 3.2 缺失伙伴提示
- 缺失伙伴不会污染列表文本
- 进入 Details 时会显示 **Health: WARN**
- Health 仅在 Details 面板显示（避免噪音）

> 例：Signal-driven bias 没有挂评估插件时，会提示 WARN

---

## 4. 运行与快照

### 4.1 Run ID
- 默认：时间戳
- 也可手动输入，用于区分实验

### 4.2 Seed Override（可选）
- Run 页支持输入 `Seed Override`（可留空）
- 留空：沿用 solver 当前 seed 策略（例如 `seed=None` 的随机模式）
- 填整数：在点击 Run 时先调用 `solver.set_random_seed(seed)` 再开始运行

### 4.3 Snapshot（结构快照）
每次运行会写入：
```
runs/visualizer/<run_id>.json
```
包含：
- adapter / pipeline / bias / plugins
- enabled 状态
- strategies / weights
- structure_hash（结构哈希）

---

## 5. Delta-first 对比（核心功能）

在 Contribution 页 → Compare：
1. 选择两个 run_id
2. 点击 Diff
3. 左侧列表会 **高亮差异项**（淡蓝底）
4. Diff 面板会显示具体差异

这可以直接回答：
> “这两次实验到底差在哪？”

---

## 6. 结构哈希图谱（Structure Hash Map）

Contribution 页新增：
- 按结构 hash 分组
- 快速判断哪些 run 是 **结构等价** 的

用途：
- 发现“重复实验”
- 找出结构相同但结果不同的 run

---

## 7. 交互顺序图（Sequence）

Sequence 页展示“组件交互顺序图”，只关注 **调用顺序**，不关心数值输出。

- 去重逻辑：相同顺序只累计 `count`
- 典型用途：发现短路路径、分支路径、插件抢占导致的流程偏移
- 输出文件：`runs/<run_id>.sequence_graph.json`
- 子标签：`List`（序列列表）、`Trie`（前缀树视图）、`Trace`（并发时序明细）
- Trace 模式：`off/sample/full`（默认 `off`），建议测试/诊断时开启
- Trace 内部视图：`Events`（逐事件）与 `By Thread/Task`（线程/任务聚合）

前置条件：
- 启用 `SequenceGraphPlugin`（默认 observability wiring 已包含）

---

## 8. Bias 贡献与趋势

Contribution 页还会显示：
- 每个 bias 的 total / count / avg
- 点击 bias 可查看 per-call / per-generation 细节

这用于回答：
> “是哪个偏置主导了结果？”

---

## 9. 策略权重轨迹（Trajectory）

如果启用了 `dynamic_switch`：
- Trajectory 页会绘制权重变化曲线
- 支持多策略自动扩展

用途：
- 观察策略切换是否合理
- 验证动态协同逻辑

---

## 10. Catalog 搜索（可发现性）

Catalog 页：
- 支持关键词搜索
- 可过滤 kind（plugin / bias / adapter / example 等）
- `Scope` 支持 `all / project / framework`（全部 / 本地项目组件 / 框架内组件）
- 选中条目会显示 `How to Use`（适用场景、最小接线、必配组件、配置键、示例入口）
- 选中条目会显示 `Context Contract`（requires/provides/mutates/cache/notes；为空也会显示 `(none)`）
- Context 选中字段后可直接联动：
  - `Providers`：默认打开字段小窗并聚焦提供者（`context_provides + context_mutates`）
  - `Consumers`：默认打开字段小窗并聚焦需求者（`context_requires`）
- Context 还支持 `Window`（非模态），可连续查看字段归因
- 字段小窗支持组件交互：选中组件可查看 `Contract + Catalog Intro`，双击组件可打开主界面 `Details`
- 小窗底部不放操作按钮（保持轻量）；需要搜索时直接回主界面 Catalog
- 字段小窗右侧会显示组件 `Contract + Catalog Intro`（摘要/用途/最小接线），便于不翻源码快速理解

用于快速回答：
> “这个功能到底有没有？”

---

## 11. Context 字段治理（本轮重点）

Context 页现在按 canonical key 做统一显示与联动。重点字段包括：

- 协同调度：`candidate_roles`、`candidate_units`、`unit_tasks`
- 运行状态：`running`、`evaluation_count`
- 参数自适应：`mutation_rate`、`crossover_rate`
- 快照字段：`individual`、`metadata`、`pareto_solutions`、`pareto_objectives`

建议用法：

- 先在 Context 页选字段，看 `declared_by / last_writer`
- 再点 `Providers / Consumers / Window` 做字段级追踪
- 对同一字段做 Catalog 联动，检查是否缺必要组件

配套门禁：

- `project doctor --strict`：结构与契约体检
- `python -m tools.context_field_guard`：非 canonical key 守卫

---

## 12. 常见问题

**Q1：为什么结构哈希为空？**
- 旧快照可能没有 `structure_hash`，现在会自动计算

**Q2：我禁用了某策略，但动态权重还在变？**
- dynamic_switch 输出的是“运行中权重轨迹”
- 如果禁用了 strategy，权重应显示为 off / 0

**Q3：为什么提示 missing companion？**
- 提示通常来自 Catalog 的 `companions` 规则（需要搭配的 plugin/adapter）。
- 如果你已经手动完成等价装配，刷新后提示会消失。

---

## 13. 最重要的正确理解

Run Inspector 不是“好看 UI”，而是：

> **优化实验的结构审计与差异解释系统**

如果你能在运行前确认结构正确，运行后确认结构差异，
你的实验就不再是“凭感觉调参”，而是 **可解释的结构实验**。

---

## 14. 推荐阅读顺序（完整学习路径）

建议按下面顺序看，避免“只会点 UI，不理解结构”：

1. `docs/user_guide/DEPTH_BREADTH_PATTERNS.md`
   - 先建立框架总图：深度（嵌套层级）+ 广度（多策略协同）。
2. `docs/user_guide/INNER_SOLVER_BACKENDS.md`
   - 再理解内层编排：`problem.inner_runtime_evaluator` / `ContractBridgePlugin` / `TimeoutBudgetPlugin`。
3. `docs/user_guide/NUMERICAL_SOLVER_PLUGINS.md`
   - 再看数值求解：`NewtonSolverProviderPlugin` / `BroydenSolverProviderPlugin`。
4. `docs/user_guide/REDIS_CONTEXT_BACKEND.md`
   - 理解 context 后端切换：memory / redis、TTL、容器工作流与常见错误。
5. `docs/standard_scaffold_tutorial/07_nested_orchestration_standard.md`
   - 最后理解标准 Project / Case / Scaffold 下的嵌套评估。
6. 回到本页（Run Inspector）
   - 用 Catalog/Context/Doctor 验证你的装配是否与契约一致。

---

# 组件拆分规则

> 文档状态：规范；来源：`nsgablack/docs/project/DECOMPOSITION_RULES.md`。本节按当前工作树合订；如与原创主卷或实时源码冲突，以原创主卷标注的规范和实时源码为准。

这一页是“可快速查找”的总纲：你不需要记住所有文件在哪，但需要记住**拆解边界**与**配套规则**，这样无论你怎么拆，都不会把系统拆坏。

如果你只记一条：**底座保持纯净；能力通过扩展点组合进来；成套能力必须提供 Wiring。**

## 1. 四类扩展点 + 一个权威组合

### RepresentationPipeline（表示与算子）
- 负责：编码/解码、初始化、变异、修复（以及可行性构造这类“硬约束”）
- 特点：更像“数据流管线”，可复用性极强
- 典型问题：VNS/邻域类方法需要随阶段切换邻域算子，可用 `ContextSelectMutator` 这类 wrapper

### Bias（偏好/倾向/软约束）
- 负责：把“方向性策略”表达成可叠加的评分/惩罚/调度；典型是软约束、偏好、阶段权重
- 不负责：复杂流程控制、候选生成主循环（否则会把 bias 变成隐形算法）
- 特例：**信号驱动偏置**（需要插件/套件提供 metrics），见 `docs/user_guide/signal_driven_bias.md`

### Adapter（策略内核）
- 负责：搜索策略的“最小闭环”—— `propose()` 提候选、`update()` 吃反馈
- 目标：把“算法核心”沉淀成可复用模块，并可用 `CompositeAdapter` 做融合/嵌套
- 不负责：并行、日志、实验追踪等横切能力（这些应留给 Plugin）

### Plugin（胶水/调度/横切能力）
- 负责：日志、监控、早停、阶段切换、动态调参、统计信号注入、并行评估调用、实验记录……
- 特点：最灵活、也最容易“长成上帝对象”，所以要靠契约/护栏约束副作用边界

### Wiring（权威组合 / Recipe）
- 负责：把“必须成套才有意义”的能力做成一键装配入口，避免漏配导致隐性 bug
- 例子：`MonteCarloEvaluationProviderPlugin` + `RobustnessBias` 就应该用 wiring 固化（事实标准）

## 2. 伙伴组件（companions）是什么

当一个能力“单独存在意义不大”或“漏配会退化/报错”时，需要明确它的伙伴组件：

- `Bias` 依赖某些 metrics：推荐对应的 Plugin/Wiring
- `Adapter` 依赖某个 representation 的 context 变异：推荐对应的 mutator wrapper
- `Plugin` 与某个 adapter/bias 形成权威组合：推荐对应的 Wiring

伙伴信息有两层：

1) 运行期护栏：缺配件时给出 `RuntimeWarning`（warn-once / strict 可选）
2) 可发现性：在 catalog 里用 `companions` 软链接，让用户“搜到一个就能顺藤摸瓜”

## 3. 接口级护栏（必须遵守）

扩展点的“输入/输出/副作用边界”不是口头约定，而是工程契约：

- 见 `docs/user_guide/EXTENSION_CONTRACTS.md`
- 对于新拆解的组件，推荐至少写一个最小测试用例（import + 运行 + 关键字段/shape 校验）

## 4. 新拆一个算法：如何让它可发现

框架提供 catalog/recipes 作为“可发现性层”：

- 使用说明：`docs/user_guide/catalog.md`
- 不想改源码：把条目按 kind 写进 `catalog/entries/<kind>.toml` 或 `NSGABLACK_CATALOG_PATH`

## 5. 更细的工程检查清单

如果你要“按规范落地一个新拆解算法”，优先按这些入口逐项检查：

- `docs/user_guide/EXTENSION_CONTRACTS.md`
- `docs/standard_scaffold_tutorial/04_validation_catalog_and_evolution.md`
- `docs/project/AUTHORITATIVE_EXAMPLES.md`


## 6. Catalog 搜索的中英文支持（开发约定）
- `catalog search` 支持中英文关键字，靠 `catalog/registry.py` 的 `_expand_token_groups` 做别名映射。
- 新增能力/领域词汇时，**同时更新 alias map**，保证中文检索命中。
- 推荐用 `python -m nsgablack catalog search <query>` 自检中文/英文搜索一致性。
- 新增条目需提供中英双语 `summary`，避免中文用户看不到条目含义。

---

# 稳定 API 表面

> 文档状态：规范；来源：`nsgablack/docs/project/STABLE_API_SURFACE.md`。本节按当前工作树合订；如与原创主卷或实时源码冲突，以原创主卷标注的规范和实时源码为准。

本文件把“对外可依赖的稳定入口”收敛成一页，配合：
- `docs/project/API_STABILITY_POLICY.md`
- `docs/project/CORE_STABILITY.md`
- `catalog/registry.py`

## 1) 最推荐入口（Discoverability）

- CLI：`python -m nsgablack catalog search <query>`
- API：
  - `from nsgablack.catalog import get_catalog`
  - `get_catalog().search(...) / list(...) / get(key)`

## 2) 权威装配（Wiring Helpers）

原则：用户优先依赖 `utils/wiring` 下的 `attach_*` 入口，因为它代表“官方推荐的组合方式”。

- `plugin.benchmark_harness` -> `nsgablack.utils.wiring:attach_benchmark_harness`
- `plugin.module_report` -> `nsgablack.utils.wiring:attach_module_report`
- `utils/wiring/ray_parallel.py` -> `nsgablack.utils.wiring:attach_ray_parallel`（可选依赖）

## 3) 能力层（Plugins）

原则：插件应当是“可插拔、可审计、尽量不改控制流”。

- `plugin.benchmark_harness` -> `nsgablack.utils.plugins:BenchmarkHarnessPlugin`
- `plugin.module_report` -> `nsgablack.utils.plugins:ModuleReportPlugin`
- `plugin.profiler` -> `nsgablack.utils.plugins:ProfilerPlugin`
- `plugin.pareto_archive` -> `nsgablack.utils.plugins:ParetoArchivePlugin`

## 4) 策略层（Adapters）

原则：策略/控制器优先走 adapter；core solver 尽量保持生命周期稳定。

- `adapter.vns` -> `nsgablack.adapters:VNSAdapter`
- `adapter.sa` -> `nsgablack.adapters:SimulatedAnnealingAdapter`
- `adapter.moead` -> `nsgablack.adapters:MOEADAdapter`
- `adapter.multi_strategy` -> `nsgablack.adapters:StrategyRouterAdapter`

## 5) 工程工具（Tools）

- `tool.parallel_evaluator` -> `nsgablack.utils.parallel:ParallelEvaluator`
- `tool.context_keys` -> `nsgablack.core.state:context_keys`
- `tool.context_schema` -> `nsgablack.core.state:MinimalEvaluationContext`

## 6) 明确不承诺稳定的范围

- 历史 `deprecated/legacy/` 内容（目录已从仓库清理；如需追溯请查看 git 历史）
- solver 内部字段/私有方法（除非 wiring/plugin 明确依赖并写入稳定文档）

---
