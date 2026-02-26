# Inner Solver Backends / 内层求解编排插件

本页介绍 `plugins/solver_backends/` 的三个插件：`InnerSolverPlugin`、`ContractBridgePlugin`、`TimeoutBudgetPlugin`。

## 1. 目标
把“多层嵌套求解”标准化：
- 外层（L1）仍按普通 Solver 工作。
- 内层（L2/L3）作为评估流程被调用。
- 关键字段由 bridge 直接回写到目标层（例如 L3 -> L1）。

## 2. 三个插件的职责

### 2.1 `InnerSolverPlugin`
- 触发点：`evaluate_individual`
- 作用：执行内层任务并产出 `inner_result`
- 支持 Hook：
  - `build_inner_problem`
  - `build_inner_solver`
  - `run_inner_solver`
  - 或 `build_inner_task`（直接返回任务 mapping）

### 2.2 `ContractBridgePlugin`
- 触发点：`on_inner_result`
- 作用：按 `BridgeRule` 把内层字段写入目标层 context
- 典型规则：
  - `BridgeRule("l3_residual", "l3_residual", target_layer="L1")`
  - `BridgeRule("status", "inner_status", target_layer="L1")`

### 2.3 `TimeoutBudgetPlugin`
- 触发点：`on_inner_guard`
- 作用：限制内层调用次数和累计耗时
- 常用配置：
  - `max_calls`
  - `time_budget_ms`
  - `fail_closed`（超限后是否阻断）

## 3. Context 合约字段
- InnerSolver 提供：
  - `metrics.inner_elapsed_ms`
  - `metrics.inner_status`
  - `metrics.inner_calls`
- Bridge 会 mutates 目标层字段（由规则定义）。
- Timeout 插件会提供预算状态字段（用于审计）。

## 4. 最小接入顺序（建议）
1. 先挂 `TimeoutBudgetPlugin`（先门禁）。
2. 再挂 `ContractBridgePlugin`（定义桥接规则）。
3. 最后挂 `InnerSolverPlugin`（执行内层流程）。

## 5. 示例入口
- 代码示例：`examples/nested_three_layer_demo.py`
- Catalog：
  - `plugin.inner_solver`
  - `plugin.contract_bridge`
  - `plugin.inner_timeout_budget`
