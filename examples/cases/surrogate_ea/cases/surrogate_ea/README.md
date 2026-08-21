# surrogate_ea（代理模型辅助进化）

验证 L4 评估层——用 `SurrogateEvaluationProviderPlugin` 做代理评估，减少昂贵真实评估次数。

## 是否使用 mlblack

不使用。纯 nsgablack。

## 这个 case 验证什么

L4 评估运行时的代理模型装配：
- 单目标 Sphere 问题
- `SurrogateEvaluationProviderPlugin` 注册为 L4 EvaluationProvider
- 代理模型在 `semantic_mode="approximate"` 模式下对候选做快速近似评估
- 真实评估作为 fallback 路径

能力信号：L4 评估层可以通过 `EvaluationMediator` 注册多个 provider，按优先级和语义模式自动选择。

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
| L4 | SurrogateEvaluationProviderPlugin | 框架 plugins/evaluation |

## 结构

| 路径 | 作用 |
|---|---|
| `problem/example_problem.py` | SphereProblem 定义 |
| `problem/config.py` | 注册 `sphere` key |
| `evaluation/` | L4 评估 provider 注册 |
| `build_solver.py` | Scaffold 装配入口 |

## 运行和验证

```powershell
# 先进入 nsgablack 仓库根目录
python examples\cases\surrogate_ea\run_project.py --check
python examples\cases\surrogate_ea\run_project.py
```
