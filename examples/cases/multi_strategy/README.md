# multi_strategy（多策略合作：VNS + SA）

验证 StrategyRouterAdapter——多个适配器并行合作，共享 archive，按权重自适应。

## 是否使用 mlblack

不使用。纯 nsgablack。

## 这个 case 验证什么

StrategyRouterAdapter 的多策略合作：
- VNS（权重 0.6）+ SA（权重 0.4）并行搜索
- `adapt_weights=True` 根据改进历史自动调整权重
- 共享 best_x / best_score，各策略独立 propose/update

## 搜索向量

| 变量 | 含义 | 范围 |
|---|---|---|
| x_i | 第 i 维 | [-5.0, 5.0] |

## 目标和指标

| 目标 | 方向 | 含义 |
|---|---|---|
| sphere | minimize | Σ x_i² |

## 组件组合

| 层 | 组件 | 来源 |
|---|---|---|
| Problem | SphereProblem | 自定义 |
| Adapter | StrategyRouterAdapter (VNS + SA) | 框架 adapters/multi_strategy |
| Representation | RepresentationPipeline | 框架 |

## 结构

| 路径 | 作用 |
|---|---|
| `problem/example_problem.py` | SphereProblem |
| `build_solver.py` | StrategyRouterAdapter 装配 |

## 运行

```powershell
cd C:\Users\hp\Desktop\nsgablack
python examples\cases\multi_strategy\run_solver.py --check
python examples\cases\multi_strategy\run_solver.py
```
