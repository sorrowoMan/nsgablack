# 06. nsgablack / mlblack 跨框架预测-决策联动对齐

跨框架联动的标准形态是“Project 调度 Case，Case 调用 Case”。外层可以是搜索 Case，也可以是学习 Case；内层同理。差异来自语义组件，而不是目录形态。

## 总体模型

| 概念 | 当前含义 |
| --- | --- |
| Project | 顶层实验与资源授权边界 |
| Case | 一个可独立运行、可被嵌套调用的标准脚手架 |
| outer candidate | 外层 Case 生成的决策、结构、配置或模型候选 |
| inner result | 内层 Case 返回的 objectives、violations、metrics、artifact refs 与 audit |
| result projector | 把内层结果投影成外层可消费目标的组件 |
| ResourceContext | Project L0 授权后的有效资源上下文 |
| run surface | 入口、配置、产物、审计、artifact 的统一记录面 |

## 嵌套接口

| 对象 | 社区概念 | 当前职责 |
| --- | --- | --- |
| `InnerSolveRequest` | inner evaluation request | 携带候选、预算、命名空间、资源上下文 |
| `InnerSolveResult` | inner evaluation response | 返回目标、约束、状态、成本、payload |
| `InnerRuntimeEvaluator` | nested evaluator | 构建并运行内层 Case |
| `TaskInnerRuntimeEvaluator` | task-based runtime | 把内层 Case 封装成可调度任务 |
| `evaluate_from_inner_result` | result projection | 在 problem/evaluation 层投影结果 |
| guard plugin | budget gate | 审计或限制嵌套调用 |

## mlblack 作为评估 Case

mlblack Case 暴露 ML 语义能力：

- 数据视图、Spec、Codec
- Trainer 或 evaluator
- Head 与 metric
- Artifact builder
- Audit/report surface

它不接管外层 population、Pareto archive 或搜索预算。外层也不读取内层实现细节。

## nsgablack 作为搜索 Case

nsgablack Case 暴露优化语义能力：

- candidate representation
- adapter search policy
- objectives/violations projection
- Pareto 与多目标治理
- search trace 与 checkpoint

它通过标准 payload 调用内层 Case，而不是直接 import 内层私有对象。

## 资源边界

| 规则 | 含义 |
| --- | --- |
| Project L0 declares resources | 全局资源池只在 Project 层声明 |
| Case requests resources | 每个 Case 声明局部需求 |
| ResourceContext is injected | 顶层运行时把授权后的上下文传给 Case |
| Case reports effective context | Case 必须记录实际使用的后端、设备、线程与 fallback |

Adapter、Trainer、Plugin 都只能表达本地意图；它们不拥有全局 lease。

## 准确表达

推荐说法：

> 学习系统作为可审计的 Case 提供拟合、评估和 artifact；优化系统作为可审计的 Case 提供候选搜索和目标治理。两者通过标准候选协议、结果 payload、资源上下文和 run surface 对齐。编排与资源授权属于共享 substrate。

这句话同时覆盖“nsgablack 外层调用 mlblack 内层”和“mlblack 外层调用其他 Case 内层”的场景。
