# Numerical Solver Plugins / 数值求解插件

本页介绍 `plugins/evaluation/newton_solver_plugin.py` 里的三个核心类，以及它们和 Problem 契约的对接方式。

## 1. 设计定位
- `NumericalSolverPlugin`：抽象基类。把“隐式方程求解”接入 `evaluate_individual`。
- `NewtonSolverPlugin`：Newton 风格（`scipy.optimize.root` / hybr）。
- `BroydenSolverPlugin`：Broyden 风格（`scipy.optimize.broyden1`）。

它们都属于“评估工具插件”，不是外层搜索策略。

## 2. Problem 侧需要提供什么
插件会查找这些 Hook（可选）：
- `build_implicit_system(x, eval_context)` -> mapping
  - `residual`: Callable, 必填
  - `x0`: 初值，可选
  - `jacobian`: 雅可比，可选
- `evaluate_from_implicit_solution(x, solution, eval_context)` -> objective(s), 必填
- `evaluate_constraints_from_implicit_solution(...)` -> constraints, 可选

若 `evaluate_from_implicit_solution` 不存在，插件不会接管评估。

## 3. Context 合约字段
- requires: `problem`
- mutates: `metrics`
- provides:
  - `metrics.implicit_residual`
  - `metrics.implicit_iters`
  - `metrics.implicit_success`

## 4. 失败与降级
- 求解失败时支持 fallback 到 `problem.evaluate`（可配置）。
- 可设置 `warn_on_failure` 输出告警，便于排查。

## 5. 最小接入示例
```python
from nsgablack.plugins import NewtonSolverPlugin, NumericalSolverConfig

solver.add_plugin(
    NewtonSolverPlugin(
        config=NumericalSolverConfig(
            tol=1e-8,
            max_iter=100,
            fallback_to_problem_eval=True,
            warn_on_failure=True,
        )
    )
)
```

## 6. 何时用它
- 目标/约束依赖隐式方程（残差=0）求解。
- 想保留外层优化框架不变，只替换“内部评估器”。
