# NewtonSolverProviderPlugin（原理与用法）

## 1) 原理
`NewtonSolverProviderPlugin` 基于 `scipy.optimize.root(method="hybr")`：
- 目标：求解 `residual(z)=0`
- 可选使用 Jacobian（Problem 提供时）
- 输出求解状态：残差范数、迭代步数、成功标志

## 2) 适用场景
- 隐式方程规模中小到中等
- Jacobian 可得或数值条件较好
- 你需要稳定的一阶求根基线

## 3) 参数建议
- `tol`: `1e-6 ~ 1e-9`（越小越严格，耗时越高）
- `max_iter`: `50 ~ 300`
- `fallback_to_problem_eval`: 生产建议开

## 4) 使用示例
```python
from nsgablack.plugins import NewtonSolverProviderPlugin, NumericalSolverConfig

solver.add_plugin(
    NewtonSolverProviderPlugin(
        config=NumericalSolverConfig(
            tol=1e-8,
            max_iter=120,
            fallback_to_problem_eval=True,
        )
    )
)
```

## 5) 关键输出字段
- `metrics.implicit_residual`
- `metrics.implicit_iters`
- `metrics.implicit_success`

