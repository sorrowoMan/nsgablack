# Black Framework Stack 中文白皮书：章节设计稿

## 这本书准备怎么讲

全书不从类名和目录开始，也不把 blackbase、nsgablack、mlblack 分成三本互不相干的手册。

它从一次“结果出来了，但运行其实不可信”的优化任务开始。读者先看见问题：预算计错、快照过期、并行分支晚到写入、内层训练越权使用资源。随后我们把这次运行拆开，理解框架为什么形成现在的边界；再从零搭出一个单 Case；等单 Case 的状态与评估可信以后，才加入 ML、Project 编排、并行、嵌套和外部 Worker。最后回到生产环境，说明怎样测试、恢复、审计和继续扩展。

贯穿案例是一套“预测驱动的多目标生产调度系统”：

- nsgablack 搜索未来若干天的机器排程；
- mlblack 根据历史数据预测加工耗时、故障概率与交付风险；
- blackbase 负责 Project、Case、资源、预算、状态、并行和任务传输；
- 系统从本地单进程逐步演进为可恢复、可并行、可嵌套的工程运行。

这样安排的目的，是让每一章都回答上一章自然产生的问题，而不是“这一章轮到介绍某个模块”。

---

# 序章　一次“成功”运行，为什么不能相信

先展示一个很像真实项目的运行：程序正常退出，Pareto 前沿也画出来了，日志和快照都有。但深入检查后发现，Adapter 更新时读的是评估前上下文；第三个候选失败后，前两个已经发生的评估成本被退还；快照保存的是环境选择前的候选；一个超时线程在主流程结束后继续写旧状态。

序章不急着解释所有类，而是建立全书的问题意识：框架的价值不是“把算法跑起来”，而是让结果、状态、预算和真实发生过的计算一致。

序章会留下一个问题：如果不能把所有逻辑继续塞在同一个循环里，这套系统应该怎样拆？

---

# 第一部　先看懂整台机器

## 第一章　为什么是三个仓库，而不是一个万能框架

这一章从职责冲突讲起：搜索策略、模型语义和运行底座为什么不能放在同一层。然后自然引出三个仓库的分工：blackbase 管共享运行事实，nsgablack 管优化搜索语义，mlblack 管机器学习语义。

不会只给一张职责表，而会拿同一个需求逐项判断归属。例如“GPU 选择”“Pareto 环境选择”“模型输出区间”“Redis Snapshot codec”“外部仿真器连接”分别该放在哪里，放错以后会造成什么依赖。

本章结束时，读者应能判断一个新功能属于哪一层。下一章进一步回答：这些层在一次真实运行里到底怎样连起来。

## 第二章　沿着一次运行走到底

以一代生产排程搜索为线索，从 `run_project.py` 进入 Project Runtime，经由标准 Case builder 构造 Solver，再走过 `propose -> representation -> evaluate -> update -> snapshot -> controller -> result`。

这一章只建立全局时序，不提前陷入实现细节。每一步都标出输入、输出、状态所有者和生命周期钩子，并同时给出 mlblack Trainer 的对应位置。

读完以后，读者会知道“谁在什么时候拥有控制权”。下一章开始真正建模：在框架运行之前，业务问题怎样成为严格的 Problem。

---

# 第二部　亲手搭出一个可信的优化 Case

## 第三章　先把业务问题说清楚：变量、目标与约束

从生产调度的机器数、日期、物料、产量和库存出发，逐步定义候选矩阵。解释为什么“最大产出”要转成最小化目标，为什么物料短缺既可以是硬约束也可以成为惩罚目标，以及多目标之间的尺度怎样影响选择。

本章会给出一份完整 `ProductionSchedulingProblem` 的精简实现，手算一个小候选的 objectives 与 violations，并展示一个常见错误：把同一业务规则同时写进 repair、penalty 和 constraint，导致三次惩罚。

本章交付一个可独立测试的 Problem。下一章解决“候选怎样保持合法、怎样在不同组件间流动”。

## 第四章　候选不是数组：Representation 与 Pipeline

围绕排程矩阵讲解 init、mutate、repair、encode、decode。用物料不足和机器切换两个例子，区分 repair 的可行性兜底与搜索策略的职责。

基础部分实现串行 Pipeline：初始化 -> 变异 -> 修复。进阶部分再引入 Slot Kernel 的 serial、parallel、router，但只讨论候选流，不提前讲线程和资源。

本章会比较“原地修改 ndarray”和“返回新候选”在并行场景中的差异，也会说明候选 fingerprint 为什么不能只看数值。

本章交付一个稳定的候选协议。下一章才能讨论 Adapter 怎样利用它搜索。

## 第五章　Adapter 负责搜索，Solver 负责运行

先写一个最小随机搜索 Adapter，再把它升级为保留精英的策略，最后对照 NSGA-II/MOEAD/VNS 等 Adapter 的共同接口。重点解释 `propose()`、`update()`、`get_population()`、`get_state()` 各自解决什么问题。

本章会完整走一代：评估前 Context 怎样进入 propose，Feedback 怎样进入 update，Adapter 为什么是更新后权威 population 的首选来源。反例是让 Solver 和 Adapter 各维护一套种群，最终快照与算法状态分叉。

本章交付一个能运行的 ComposableSolver。下一章开始处理最容易被“能跑”掩盖的评估正确性。

## 第六章　评估不是函数调用，而是一条会计链

这一章集中讲单点评估、批量 Provider、插件短路、shape 验证、evaluation_count 和硬预算。

核心案例是“预留 3 次评估，前两个已调用，第三个失败”。我们会分别记录 reserved、started、completed、refundable，推导为什么只能退还未开始部分。还会展示批量输出转置、violations 数量不匹配、Provider 返回 `None` 等错误怎样在入口处被拦截。

本章会给出可执行的测试思路，而不是一句“需要校验 shape”。下一章承接评估产生的大量状态，解释它们应该放在哪里。

## 第七章　Context、Snapshot 与 Artifact：三种状态，三种寿命

从一代运行产生的 generation、best、population、history、模型和报告出发，逐项判断它们属于 Context、Snapshot 还是 Artifact。

本章会实际写一次代级提交：`adapter.update -> resolve authoritative population -> validate -> write snapshot -> update handle`，并复现“latest handle 只写一次”导致后续 Context 永远引用旧快照的问题。

随后比较内存、文件和 Redis Snapshot，说明安全序列化如何保存 UnknownState 的 values 与 metadata，而不是退化成字符串。

本章交付一条可恢复的状态链。下一章讨论不改变算法语义的扩展能力怎样进入生命周期。

## 第八章　Plugin、Bias 与 Controller：三个容易混淆的扩展面

用同一个需求分别判断三种实现：记录评估耗时属于 Plugin；偏向连续生产属于 Bias；预算耗尽请求停止属于 Controller。

本章逐步实现一个审计 Plugin、一个平滑生产 Bias 和一个 BudgetController。十个 Plugin hook 不再做清单式介绍，而是放入完整生命周期时序中，解释错误由哪一层分发、为什么同一异常不能触发两三次 on_error。

本章还会展示 RuntimeController 注册后却没有进入 run loop 的静默失效，以及 stop 信号怎样统一映射到 `request_stop()`。

到这里，一个纯 nsgablack 单 Case 已经完整而可信。下一部开始加入机器学习。

---

# 第三部　把机器学习放进正确的位置

## 第九章　mlblack 的问题不是“怎么 fit”，而是模型语义怎样闭合

以“预测机器加工耗时”为任务，构造 DataView、UnknownState、ModelRepresentation、Head、LearningProblem、Feedback 和 Trainer。解释 values 与 metadata 如何共同决定模型，为什么反馈对齐必须使用 fingerprint/equivalent。

本章会从最小线性模型开始，给出一次 propose、decode、evaluate、update 的完整流动，并把它与前面的 Solver 时序对照。读者会看到 Solver 与 Trainer 同级，但 Problem 和 Feedback 的语义不同。

本章交付一个单 Trainer。下一章解决模型组合、Backend 和阶段产物。

## 第十章　模型组合、Backend Session 与 SerialTrainer

先做“主模型 + 残差模型”，再扩展到多模态分支和专家融合。每次组合前先定义 Input/Output Contract，避免形状正确但语义错误。

本章会解释 ComputeBackendSession 怎样从 ResourceContext 解析 requested、granted、resolved，以及为什么 setter 更新资源后必须同步 Session。随后实现一个两阶段 SerialTrainer，说明子 Trainer 的 setup、finish、error、teardown 和最终 Result 怎样汇总。

反例包括 `run = fit` 的静态绑定、子阶段成功但父级 best 为空、Artifact 多包一层和更新前状态被写入快照。

本章交付模型 Artifact。下一部把优化 Case 与训练 Case 放进同一个 Project。

---

# 第四部　从两个独立 Case 到一个复杂 Project

## 第十一章　Project -> Case -> Scaffold：复杂结构的骨架

先把排程搜索和耗时预测拆成两个可独立运行的 Case，再由 Project 定义 Stage、依赖和资源请求。解释为什么 `build_solver.py` 是统一规范入口，Trainer Case 也不另建一套目录。

本章会写出完整 `project_config.py`、两个 Case builder 和 `run_project.py`，并展示 check 与 build-check 应该看到什么。还会解释 `mode=cli` 与 `mode=build` 的区别，以及并行 Stage 为什么不能依赖同 Stage 未完成 Case 的 Artifact。

本章交付一个串行 Project。下一章把 ML 从前置模型变成外层候选的内层评估。

## 第十二章　外层优化调用内层训练：真正的跨框架嵌套

外层候选决定模型特征、训练预算或风险权重；内层 mlblack Case 拟合模型并返回 RMSE、故障概率和 ArtifactRef；外层把它们映射为调度目标。

本章会明确 inner request/result payload、component overrides、ResourceContext 派生、ArtifactRef 注入和共享 Budget Authority。会给出一个完整时序，说明 nsgablack 为什么不能 import mlblack Trainer 私有字段。

反例是每个内层 Trainer 都创建自己的预算和线程池，使外层一百个候选变成一百倍资源。下一章解决这种组合进入并行后的确定性问题。

## 第十三章　并行、merge、timeout 与晚到写入

先让三个变异分支 parallel，再让多个候选并行评估，最后让多个 Case 并行。逐层说明 worker 上限从哪里来、value/context 怎样隔离、结果为何按 spec 顺序 merge。

本章会复现两个真实竞态：多个分支原地修改同一 ndarray；线程 timeout 后仍通过旧 SnapshotStore 句柄写入。随后引入 cancellation event、run token 和 fenced handle。

还会解释为什么 `future.cancel()` 不能强杀正在运行的 Python 线程，以及什么时候必须换进程或外部 Worker。

本章交付受 L0 约束的本地并行。下一章把执行扩展到进程外和机器外。

## 第十四章　外部 Worker、Task Transport 与 Lease Fence

从一个 Redis TaskEnvelope 出发，走过 publish、claim、heartbeat、execute、commit、ack 和 retry。区分任务 lease 与 Project resource lease，说明 visibility timeout、幂等 key 和死信队列各自解决什么问题。

本章会演示 Worker 网络中断后旧 lease 过期、新 Worker 接管，而旧 Worker 晚到提交结果的场景；fencing token 怎样拒绝旧写入。

还会讨论凭据脱敏、安全序列化和多机共享预算。到这里，贯穿案例具备分布式运行能力。最后一部处理长期运行与演进。

---

# 第五部　让系统经得起失败和变化

## 第十五章　Checkpoint、恢复、Replay 与随机性

从“进程在第 17 代崩溃”开始，列出恢复真正需要的状态：Solver/Trainer、Adapter、population、Feedback、RNG、Controller、Plugin、预算、资源与 schema。

本章会定义一致性提交点，比较继续运行与决策回放，给出 Project root seed 到 Case、Stage、Adapter、Branch、Worker 的稳定派生方法。读者将实际比较连续运行与恢复运行的 candidate fingerprint。

本章交付可恢复、可解释的运行记录。下一章讨论怎样安全扩展框架。

## 第十六章　自定义组件的完整方法，而不是模板抄写

分别以一个 Adapter、一个 Plugin、一个批量 Provider 和一个外部 Backend 为例，走完“归属判断 -> Contract -> 生命周期 -> 状态 -> 资源 -> 错误 -> 序列化 -> 测试 -> Scaffold/Catalog”全过程。

重点不是给四段空类，而是解释新增能力时怎样避免创建第二套运行逻辑。每个例子都包含错误版本、修正版本和最小验收矩阵。

本章交付一套可复用的扩展决策方法。下一章把所有机制收进发布流程。

## 第十七章　测试、Doctor、Catalog 与发布验收

从测试金字塔讲到运行契约矩阵：单候选、批量、Provider 短路、Snapshot、部分失败预算、并行 merge、timeout、late write、Redis codec、SerialTrainer 生命周期、跨 Case 资源收窄。

Doctor 负责什么、不能证明什么；Catalog 的 default 与 framework-core 口径怎样使用；build-check 怎样验证“配置声明”真的变成“实际装配”。Dashboard 放在最后，因为它只能展示已经可靠的事实。

本章最终给出贯穿案例的发布清单和故障演练脚本。

## 第十八章　框架下一步怎样演进

回到最初的设计问题，讨论共享能力继续向 blackbase 收口、兼容 forwarder 退出、schema 版本、Provider 生态、进程级取消、分布式状态和性能优化。

这一章会明确区分“当前已经实现”“目前只在静态结构上成立”“下一阶段建议”，避免路线图被误读为现有能力。

全书在这里闭环：从一次不可信的成功运行，走到一套能够解释自己为什么可信、也知道自己边界在哪里的运行系统。

---

# 附录设计

## 附录 A　公共 API 与源码锚点

按实际阅读顺序列出 blackbase、nsgablack、mlblack 的核心文件、类型和方法，不重复正文解释。

## 附录 B　Context Key、Snapshot Envelope 与 Result Payload

提供字段级速查、版本和序列化示例。

## 附录 C　命令与排障索引

按“创建、检查、运行、恢复、Redis、并行、Catalog”组织命令，并链接到正文解释。

## 附录 D　术语表

解释 Project、Case、Scaffold、L0、Adapter、Representation、Feedback、Artifact、Lease、Fence 等术语及容易混淆的近义概念。

