# plugins/evaluation

## 目录职责
- 放“评估阶段增强”能力：评估加速、数值求解、评估模型封装。
- 不负责跨层编排；跨层桥接放在 `plugins/solver_backends/`。

## 本次拆分（每个数值求解器独立插件）
- `numerical_solver_base.py`
  - `NumericalSolverPlugin`（公共评估接管逻辑）
  - `NumericalSolverConfig`
- `newton_solver_plugin.py`
  - `NewtonSolverPlugin`（`scipy.optimize.root` / `hybr`）
- `broyden_solver_plugin.py`
  - `BroydenSolverPlugin`（`scipy.optimize.broyden1`）

## 触发时机
- 主要在 `evaluate_individual` 阶段接管评估。
- Problem 提供隐式方程 hook 时生效，否则返回 `None`，不干扰默认评估。

## 契约摘要
- requires: `problem`
- mutates: `metrics`
- provides:
  - `metrics.implicit_residual`
  - `metrics.implicit_iters`
  - `metrics.implicit_success`

