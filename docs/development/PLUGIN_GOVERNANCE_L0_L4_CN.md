# 插件与控制面重构说明（L0/L3/L4）

## 1. 分层结论
- `L0`：执行加速基础设施（不改语义）。示例：GPU、并行、向量化、精确缓存。
- `L1/L2`：观测与治理插件（消费运行信息，不接管求解语义）。
- `L3`：运行控制器（何时做什么）。通过 `register_controller()` 接入。
- `L4`：评估语义替换（谁来评估）。通过 `register_evaluation_provider()` 接入。
- 内层求解器：独立 SolverRuntime（非插件），通过 `NestedSolverEvaluator` 进入外层评估。

## 2. 硬约束
- 禁止插件实现 `evaluate_individual/evaluate_population` 作为评估短路入口。
- 同一控制域只能有一个 owner；冲突直接报错（strict）。
- 近似评估默认关闭：`EvaluationMediatorConfig.allow_approximate=False`。
- 语义改变必须在 L4；L0 只做语义保持的工程加速。

## 3. 运行时接线顺序（标准脚手架）
1. Problem
2. Pipeline
3. Bias
4. Solver + Adapter
5. Controllers (L3)
6. Evaluation Providers (L4)
7. Observers / Governance Plugins
8. Project Plugins
9. Checkpoint
10. L0 Acceleration Backend

## 4. 内层求解器契约
- 请求结构：`InnerSolveRequest`（候选、外层代数、预算、父级契约）。
- 返回结构：`InnerSolveResult`（目标、约束、状态、成本）。
- 握手规则：内层声明 `accepted_parent_contracts`，外层 `parent_contract` 必须匹配。
- 预算规则：外层每次调用显式声明预算，内层返回实际成本用于回写统计。
