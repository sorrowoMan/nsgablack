# plugins/solver_backends

## 目录职责 / Responsibility
- 中文：放“内层求解编排”插件，负责层级调度、跨层回写、调用预算控制。
- English: Hosts nested solver orchestration plugins: layer scheduling, cross-layer write-back, and budget guard.

## 典型场景 / Typical Use Cases
- L1 外层只做总体优化；L2/L3 作为内层评估流程。
- 在 `evaluate_individual` 中触发内层求解并回写关键字段到外层 context。
- 对内层调用次数和耗时做硬门禁，避免评估失控。

## 模块说明 / Module Overview
- `inner_solver.py`
  - `InnerSolverPlugin`: 在外层评估时触发内层任务执行（L1 -> L2/L3）。
  - 支持 `build_inner_problem/build_inner_solver/run_inner_solver` 或 `build_inner_task` 钩子。
- `contract_bridge.py`
  - `ContractBridgePlugin`: 将内层结果字段按规则桥接到目标层 context（例如 L3 结果直写 L1）。
- `timeout_budget.py`
  - `TimeoutBudgetPlugin`: 为内层执行做调用次数/总耗时限制，支持 fail-open/fail-closed。

## 与 evaluation 的边界 / Boundary with `plugins/evaluation`
- 中文：`evaluation` 关心“如何评估”；`solver_backends` 关心“评估流程怎么编排到多层”。
- English: `evaluation` focuses on evaluation method; `solver_backends` focuses on multi-layer orchestration.
