# 中文白皮书 V2 行文蓝图

## 一句话主线

读者跟随一个“预测驱动的多目标生产调度系统”，从业务问题出发，逐层构造 Problem、Representation、Adapter、Solver、Trainer、Project、L0 和生产运行闭环；每一章都消费上一章产物，并为下一章留下一个明确工程问题。

## 贯穿案例

工厂需要安排多台机器未来若干天的产量。目标包括提高产出、降低物料短缺、减少机器切换、平滑每日产量和降低预测风险。基础排程由 nsgablack 搜索；mlblack 根据历史数据预测机器耗时和故障概率；blackbase 负责任务编排、资源授权、状态、预算、并行和恢复。

该案例分三个可递进版本：

1. `V0`：纯 nsgablack、单进程、确定性规则评估。
2. `V1`：引入 mlblack 预测模型，外层排程候选调用内层预测/训练 Case。
3. `V2`：Project 级并行、共享预算、Redis Snapshot、外部 Worker、取消、恢复和审计。

## 全书因果链

1. 业务目标若不先变成清晰 Problem，后续所有组件都会越层。
2. Problem 有了以后，还需要 Representation 才能定义候选怎样流转。
3. 候选能流转以后，Adapter 才能提出和更新，Solver 才能形成单 Case 闭环。
4. 单 Case 能跑以后，必须先解决评估、预算、Context 和 Snapshot 的正确性，否则复杂化只会放大错误。
5. 状态正确以后，再加入 Plugin、Controller、Pipeline 并行和策略组合。
6. 优化闭环稳定以后，引入 mlblack 的预测模型与 Artifact。
7. 两个语义 Case 都独立闭合以后，Project 才能安全组合它们并发放 L0 资源。
8. 跨框架组合成立以后，再处理嵌套预算、取消、租约、外部 Worker 和恢复。
9. 最后才讨论 Catalog、Doctor、Dashboard 和长期演进，因为它们消费的是已经可靠的运行事实。

## 章节统一写法

每章必须包含以下要素，而不是只给概念摘要：

- **上一章留下的问题**：说明本章为什么出现。
- **本章交付物**：读完能得到哪个文件、对象、协议或测试。
- **机制推演**：从输入到输出逐步说明状态变化。
- **完整示例**：以贯穿案例给出可复制代码或明确标注的核心伪代码。
- **错误实现**：展示至少一个真实反例及其静默后果。
- **调试方法**：遇到问题先观察什么、怎样定位到哪一层。
- **验收测试**：给出输入、预期输出和关键断言。
- **进阶变体**：说明扩展到并行、嵌套或外部后端时哪些不变量仍然成立。
- **源码锚点**：指出当前三仓的权威模块。
- **通向下一章**：明确下一个工程问题。

## 新版卷章结构

### 第一部：把业务问题变成可运行语义

1. 为什么需要统一框架栈：从一次失败的排程运行开始。
2. 建模：决策变量、目标、约束和 Feedback。
3. 表示：候选怎样初始化、修复、编码、解码和辨认身份。
4. 单 Case 装配：Problem + Representation + Adapter + Solver。

### 第二部：让单 Case 运行结果可信

5. Solver 生命周期：propose/evaluate/update 的真实时间轴。
6. 评估链：shape、Provider、批量部分失败、预算账本和错误边界。
7. 状态：Context、Snapshot、Artifact 与权威提交。
8. Plugin、Controller、Bias：能力、控制和软引导怎样不越层。

### 第三部：加入机器学习语义

9. mlblack 单 Trainer：DataView、UnknownState、Representation、Head、Problem、Feedback。
10. 模型组合：Pipeline、Backend Session、SerialTrainer 和 Artifact。

### 第四部：从单 Case 到复杂 Project

11. Project -> Case -> Scaffold：装配、资源 grant、Stage 和结果传递。
12. 外层优化 + 内层 ML：component overrides、ArtifactRef 和共享预算。
13. 并行与取消：Pool、输入隔离、merge、timeout、run fence。
14. 外部 Worker：Transport、Lease、heartbeat、fencing 和幂等。

### 第五部：生产化与演进

15. Checkpoint、恢复、Replay、随机性和可观测性。
16. 自定义 Adapter、Plugin、Provider 和 Backend 的完整方法。
17. 测试、Doctor、Catalog 与发布验收。
18. 架构演进：兼容层、schema 版本、性能与安全边界。

## 深度标准

正文目标不是“每个名词都出现”，而是让读者可以独立完成以下任务：

- 写出一个合法多目标 Problem，并解释每个目标与约束的尺度。
- 写出 Representation 和 Adapter，确保更新后权威种群能被 Snapshot 捕获。
- 设计部分失败不退款的硬预算评估链。
- 通过正式 Case 把 mlblack Trainer 嵌入外层优化，而不 import 私有实现。
- 证明并行分支受 ResourceContext 限制、输入隔离、merge 确实执行。
- 解释线程 timeout 为什么不等于强制停止，并阻止晚到写入。
- 在 Redis safe serializer 下往返恢复 UnknownState。
- 从 manifest、trace、Snapshot 和 Artifact 还原一次运行的因果链。

