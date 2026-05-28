# dynamic_strategy（动态策略切换：VNS+SA + DynamicSwitchPlugin）

验证 DynamicSwitchPlugin——运行期根据信号在多种策略间切换。

## 是否使用 mlblack

不使用。纯 nsgablack。

## 这个 case 验证什么

动态策略切换的装配路径：
- StrategyRouterAdapter 管理 VNS + SA 双策略
- DynamicSwitchPlugin 根据收敛信号自动切换策略权重
- SensitivityAnalysisPlugin 提供参数敏感性分析

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
| Adapter | StrategyRouterAdapter (VNS + SA) | 框架 adapters/multi_strategy |
| Plugin | DynamicSwitchPlugin | 框架 plugins/runtime |

## 运行

```powershell
cd C:\Users\hp\Desktop\nsgablack
python examples\cases\dynamic_strategy\run_solver.py --check
```
