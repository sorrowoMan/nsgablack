# trust_region_dfo（Trust Region DFO 适配器）

验证非默认 Adapter——使用 TrustRegionDFOAdapter 替代 NSGA2，证明 Solver 与 Adapter 的解耦。

## 是否使用 mlblack

不使用。纯 nsgablack。

## 这个 case 验证什么

Adapter 层的可替换性：
- 单目标 Sphere 问题
- 不使用默认 NSGA2 Adapter，改用 TrustRegionDFOAdapter
- `solver.set_adapter()` 在 assembly 层注入

能力信号：Solver 不绑定特定 Adapter。任何符合 `AlgorithmAdapter` 契约的适配器都可以通过 scaffold 的标准装配路径接入。

## 搜索向量

| 变量 | 含义 | 范围 |
|---|---|---|
| x_i | 第 i 维连续变量 | [-5.0, 5.0] |

## 目标和指标

| 目标 | 方向 | 含义 |
|---|---|---|
| sphere | minimize | Σ x_i² |

## 组件组合

| 层 | 组件 | 来源 |
|---|---|---|
| Problem | SphereProblem | 自定义（继承 BlackBoxProblem） |
| Representation | RepresentationPipeline (GaussianMutation) | 框架 representation/ |
| Adapter | TrustRegionDFOAdapter | 框架 adapters/trust_region_dfo |

## 结构

| 路径 | 作用 |
|---|---|
| `problem/example_problem.py` | SphereProblem 定义 |
| `problem/config.py` | 注册 `sphere` key |
| `build_solver.py` | Scaffold 装配入口 |

## 运行和验证

```powershell
cd C:\Users\hp\Desktop\nsgablack
python examples\cases\trust_region_dfo\run_project.py --check
python examples\cases\trust_region_dfo\run_project.py
```
