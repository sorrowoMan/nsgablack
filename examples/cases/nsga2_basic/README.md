# nsga2_basic（NSGA-II 基础求解器 + 精英保留 + 模块报告）

最简 NSGA-II 求解器演示——验证标准 scaffold 能装配 problem + representation pipeline + NSGA2 adapter + plugins。

## 是否使用 mlblack

不使用。纯 nsgablack。

## 这个 case 验证什么

标准脚手架的最简装配路径：
- `BlackBoxProblem` 子类定义双目标 Sphere 问题
- `RepresentationPipeline` 提供 Gaussian 变异 + Clip 修复
- NSGA2 Adapter 驱动多目标搜索
- `BasicElitePlugin` 保留精英个体，`ModuleReportPlugin` 输出模块报告

能力信号：scaffold 的 `build_solver` → `--check` → `run_solver` 全链路通畅。

## 搜索向量

| 变量 | 含义 | 范围 |
|---|---|---|
| x_i | 第 i 维连续变量 | [-5.0, 5.0] |

## 目标和指标

| 目标 | 方向 | 含义 |
|---|---|---|
| sphere | minimize | Σ x_i² |
| shifted_sphere | minimize | Σ (x_i - 1.5)² |

## 组件组合

| 层 | 组件 | 来源 |
|---|---|---|
| Problem | BiObjectiveSphereProblem | 自定义（继承 BlackBoxProblem） |
| Representation | RepresentationPipeline (GaussianMutation) | 框架 representation/ |
| Adapter | NSGA2Adapter | 框架 adapters/nsga2 |
| Plugin | BasicElitePlugin, ModuleReportPlugin | 框架 plugins/ |

## 效果对比

本 case 是 scaffold 装配验证，非算法性能对比。关键指标：

| 指标 | 值 |
|---|---|
| assembly --check | ok |
| 完整求解 | 收敛到 Pareto front |

## 结构

| 路径 | 作用 |
|---|---|
| `problem/example_problem.py` | BiObjectiveSphereProblem 定义 |
| `problem/config.py` | 注册 `biosphere` key |
| `build_solver.py` | Scaffold 装配入口 + plugin 挂载 |

## 运行和验证

```powershell
cd C:\Users\hp\Desktop\nsgablack
python examples\cases\nsga2_basic\run_solver.py --check
python examples\cases\nsga2_basic\run_solver.py
```
