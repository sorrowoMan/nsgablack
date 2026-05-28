# single_trajectory（单轨迹自适应搜索）

验证 SingleTrajectoryAdaptiveAdapter——单个解的迭代优化。

## 是否使用 mlblack

不使用。纯 nsgablack。

## 这个 case 验证什么

单轨迹适配器的装配路径：
- 只维护一个候选解，迭代精修
- 自适应调整步长和探索策略

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
| Adapter | SingleTrajectoryAdaptiveAdapter | 框架 adapters/single_trajectory_adaptive |

## 运行

```powershell
cd C:\Users\hp\Desktop\nsgablack
python examples\cases\single_trajectory\run_solver.py --check
```
