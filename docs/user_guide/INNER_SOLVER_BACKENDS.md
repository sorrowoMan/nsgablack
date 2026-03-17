# Inner Solver Runtime（问题契约版）

本页说明新的内层求解模式：**不再使用 `InnerSolverPlugin`**，统一改为 `problem.inner_runtime_evaluator`。

## 1. 目标
- 外层 Solver 仍按标准循环工作。
- 内层求解作为 `Problem` 评估语义的一部分执行。
- 运行治理与追溯仍由插件层完成（如 `ContractBridgePlugin`、`TimeoutBudgetPlugin`）。

## 2. 关键对象
- `TaskInnerRuntimeEvaluator`（`nsgablack.core.nested_solver`）
- `InnerRuntimeConfig`（重试、超时、fallback、层标签）
- `problem.inner_runtime_evaluator`（挂载点）

## 3. 推荐接线
1. `solver.add_plugin(TimeoutBudgetPlugin(...))`
2. `solver.add_plugin(ContractBridgePlugin(...))`
3. `solver.problem.inner_runtime_evaluator = TaskInnerRuntimeEvaluator(config=...)`

## 4. 运行钩子
- evaluator 会调用：
  - `build_inner_task`
  - 或 `build_inner_problem/build_inner_solver/build_inner_backend/run_inner_solver`
- evaluator 会触发：
  - `on_inner_guard`（预算/门禁）
  - `on_inner_result`（桥接回写）

## 5. 示例
- `examples/nested_three_layer_demo.py`
- `examples/ngspice_inner_demo.py`
