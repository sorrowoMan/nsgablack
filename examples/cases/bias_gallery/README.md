# bias_gallery（偏置系统演示）

验证 nsgablack 的 Bias 系统——通过 catalog 选择偏置，挂载到 Solver，在评估中软调整反馈。

## 是否使用 mlblack

不使用。纯 nsgablack。

## 这个 case 验证什么

Bias 系统的装配路径：
- 单目标 Sphere 问题
- 通过 catalog 注册和选择不同 bias（CallableBias、DynamicPenaltyBias 等）
- Bias 在评估后对 feedback 做软调整（不替代硬约束）

能力信号：Bias 系统可以通过标准 scaffold 的 `bias_key` 参数装配，无需手动构建 BiasModule。

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
| Adapter | NSGA2Adapter | 框架 adapters/nsga2 |
| Bias | 通过 catalog 选择 | 框架 bias/ |

## 结构

| 路径 | 作用 |
|---|---|
| `problem/example_problem.py` | SphereProblem 定义 |
| `problem/config.py` | 注册 `sphere` key |
| `bias/domain/` | 项目级 bias 注册 |
| `build_solver.py` | Scaffold 装配入口 |

## 运行和验证

```powershell
cd C:\Users\hp\Desktop\nsgablack
python examples\cases\bias_gallery\run_solver.py --check
python examples\cases\bias_gallery\run_solver.py
```
