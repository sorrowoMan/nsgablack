# BroydenSolverPlugin（原理与用法）

## 1) 原理
`BroydenSolverPlugin` 基于 `scipy.optimize.broyden1`：
- 属于拟牛顿求根（不显式构造完整 Jacobian）
- 通过迭代更新近似信息，降低 Jacobian 依赖

## 2) 适用场景
- Jacobian 难构造或构造成本高
- 你希望比纯 Newton 更轻量的求根路径
- 作为 Newton 的并行对照或回退策略

## 3) 参数建议
- `tol`: `1e-6 ~ 1e-8`
- `max_iter`: `80 ~ 300`
- 对噪声较大的 residual，可适当放宽 `tol`

## 4) 使用示例
```python
from nsgablack.plugins import BroydenSolverPlugin, NumericalSolverConfig

solver.add_plugin(
    BroydenSolverPlugin(
        config=NumericalSolverConfig(
            tol=1e-7,
            max_iter=150,
            fallback_to_problem_eval=True,
        )
    )
)
```

## 5) 与 Newton 的选型建议
- 默认先用 Newton（收敛基线更直观）
- Jacobian 不可得/不稳定时优先试 Broyden
- 实战中可双插件做 A/B，对比 residual 与收敛成本

