# 第一卷　可信复杂计算与统一框架原理

第一卷建立整套开发白皮书的论证语言。它不是从 `Solver`、`Adapter` 或三个仓库开始介绍，而是先回答复杂计算为什么不能只交付一个数值答案，再依次建立闭包、不变量、责任角色、外部计算边界和领域语义。只有这些前提成立，后半卷才进入框架落位、工作尺度、角色、合同、状态、身份、信息载体与控制对象。

本卷同时限定两条彼此对应的反过度设计原则：因果溯源以声明、策略和信任边界内的有限证据闭合，不追求无限还原世界历史；运行收尾以 ownership、责任转交和可验证的 delegated cleanup 闭合，不重新实现语言运行时、操作系统、容器、驱动与 Backend 已经承担的物理回收。统一框架要补的是这些底层机制之间缺失的跨边界语义，而不是把已经存在的计算机基础设施再造一遍。

## 已有正文

1. [从答案到可信运行](chapters/01_从答案到可信运行.md)
2. [六类复杂性怎样相互放大](chapters/02_六类复杂性怎样相互放大.md)
3. [五种闭包：全书要证明什么](chapters/03_五种闭包_全书要证明什么.md)
4. [十条架构不变量](chapters/04_十条架构不变量.md)
5. [谁拥有正在形成的答案：从通用反馈系统到计算角色](chapters/05_谁拥有正在形成的答案_从通用反馈系统到计算角色.md)
6. [求值不是学习，调用也不是编排：外部计算处在什么位置](chapters/06_求值不是学习_调用也不是编排_外部计算处在什么位置.md)
7. [为什么优化与学习成为两种一等闭环](chapters/07_为什么优化与学习成为两种一等闭环.md)
8. [统一而不混同：共享控制不等于共享领域语义](chapters/08_统一而不混同_共享控制不等于共享领域语义.md)
9. [三仓一边界：统一框架如何落到工程](chapters/09_三仓一边界_统一框架如何落到工程.md)
10. [工作尺度：Project、Stage、Case、Scaffold 与 Pipeline](chapters/10_工作尺度_Project_Stage_Case_Scaffold_与_Pipeline.md)
11. [角色本体：Problem、Representation、Adapter、Controller、Plugin 与 Backend](chapters/11_角色本体_Problem_Representation_Adapter_Controller_Plugin_与_Backend.md)
12. [合同本体：类型、能力、上下文、资源与 I/O](chapters/12_合同本体_类型_能力_上下文_资源与_IO.md)
13. [状态与反馈：UnknownState、Candidate、Feedback 和 Result](chapters/13_状态与反馈_UnknownState_Candidate_Feedback_和_Result.md)
14. [身份、时间与版本：同一个值为什么不是同一个状态](chapters/14_身份_时间与版本_同一个值为什么不是同一个状态.md)
15. [五类信息载体：Context、Snapshot、Artifact、Event 与 Manifest](chapters/15_五类信息载体_Context_Snapshot_Artifact_Event_与_Manifest.md)
16. [控制对象：资源、预算、截止时间、取消与错误](chapters/16_控制对象_资源_预算_截止时间_取消与错误.md)

第 17 章“生命周期代数：setup、run、commit、teardown 与恢复”仍待编写。

全书分卷关系见 [V6 总目录](../CONTENTS.md)，迁移完成度见 [迁移状态](../MIGRATION_STATUS.md)。
