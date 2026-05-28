# dynamic_repair（动态修复策略）

验证 DynamicRepair——两阶段修复随代数切换，早期宽裁剪、后期紧裁剪。

## 是否使用 mlblack

不使用。纯 nsgablack。

## 这个 case 验证什么

DynamicRepair 的阶段化修复策略：
- Stage 1 (gen 0-19): ClipRepair [-2, 2] — 宽范围探索
- Stage 2 (gen 20+): ClipRepair [-1, 1] — 紧范围精修
- TrustRegionDFOAdapter 驱动搜索

能力信号：RepresentationPipeline 的 repair 策略可以根据代数动态切换，不需要修改 adapter。

## 搜索向量

| 变量 | 含义 | 范围 |
|---|---|---|
| x_i | 第 i 维 | 动态变化 [-2,2] → [-1,1] |

## 目标和指标

| 目标 | 方向 | 含义 |
|---|---|---|
| sphere | minimize | Σ x_i² |

## 组件组合

| 层 | 组件 | 来源 |
|---|---|---|
| Problem | SphereProblem | 自定义 |
| Representation | DynamicRepair + ClipRepair | 框架 representation/dynamic |
| Adapter | TrustRegionDFOAdapter | 框架 adapters/trust_region_dfo |

## 结构

| 路径 | 作用 |
|---|---|
| `problem/example_problem.py` | SphereProblem |
| `build_solver.py` | DynamicRepair + TrustRegionDFO 装配 |

## 运行

```powershell
cd C:\Users\hp\Desktop\nsgablack
python examples\cases\dynamic_repair\run_solver.py --check
```
