# Numerical Solver Base（原理与用法）

## 1) 作用
`NumericalSolverPlugin` 是“隐式方程评估接管器”：
- 当 Problem 提供隐式系统 hook 时，插件先做数值求解，再回填 objective/violation。
- 当 hook 不存在时，不接管，保持默认 `problem.evaluate` 路径。

## 2) Problem 侧接口（必须/可选）
- 必须：
  - `evaluate_from_implicit_solution(x, solution, eval_context)`
- 可选：
  - `build_implicit_system(x, eval_context)` -> `{"residual", "x0", "jacobian"}`
  - `evaluate_constraints_from_implicit_solution(...)`

## 3) 插件内部流程
1. 提取隐式系统（`residual/x0/jacobian`）  
2. 调用 `solve_backend(...)`  
3. 用 `evaluate_from_implicit_solution(...)` 计算 objective  
4. 计算 violation（优先 implicit constraints，否则回退默认 constraints）  
5. 写入 metrics：`implicit_residual/iters/success`  
6. 返回 `(objectives, violation)`

## 4) 失败策略
- `fallback_to_problem_eval=True`：数值求解失败时回退到 `problem.evaluate`。
- `warn_on_failure=True`：打印告警，便于排障。

## 5) 最小接入示例
```python
from nsgablack.plugins import NumericalSolverConfig, NewtonSolverPlugin

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

