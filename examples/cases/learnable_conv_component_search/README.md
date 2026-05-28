# Learnable Conv Component Search（可学习卷积组件搜索）

`learnable_conv_component_search` 验证 nsgablack 对 learnable convolution component 的 outer search，并由 mlblack inner refinement surface 评估。

## 这个 case 验证什么

- nsgablack 搜索 symbolic/typed convolution structure choices。
- mlblack 通过正式的 `learnable_conv_component_demo` surface 评估选中结构。
- case 将 outer structure search 与 inner coefficient refinement 分开。
- Objectives 衡量 prediction quality、generalization、structural complexity 和 kernel recovery。

## 是否使用 mlblack

使用。Inner evaluation 调用正式 mlblack example surface：

- `examples/cases/learnable_conv_component_demo`

被优化的 mlblack pipeline override 是：

- `pipeline.learnable_conv1d`

## nsgablack 侧能力

- Convolution component structure 的 outer genome。
- 搜索 kernel shape、stride、padding、pooling、output mode、input inclusion 和 symbolic basis terms。
- 在 test error、generalization gap、feature complexity、kernel recovery 之间做多目标权衡。

## mlblack 侧能力

- Learnable 1D convolution component evaluation。
- 通过 demo surface 做 inner coefficient refinement。
- 将 feature/kernel performance metrics 投影回 outer problem。

## 搜索变量（Search variables）

| 变量族 | 含义 |
|---|---|
| kernel rows/cols | Convolution kernel 的结构形状。 |
| stride | 卷积组件的 step size。 |
| padding | Boundary handling。 |
| pooling | 下游 aggregation choice。 |
| output mode | Component outputs 如何暴露给模型。 |
| include input | 是否保留 raw input 与 learned features 并行。 |
| symbolic basis terms | Inner refinement surface 使用的候选 basis structure。 |

## 目标和指标（Objectives / Metrics）

| 目标 | 含义 |
|---|---|
| `test_rmse` | 主要 held-out prediction error。 |
| `generalization_gap` | Train/test mismatch penalty。 |
| `feature_complexity` | 选中 component/feature structure 的成本。 |
| `kernel_recovery_penalty` | 未能恢复目标 kernel structure 的惩罚。 |

## 结构（Structure）

| 路径 | 作用 |
|---|---|
| `run_solver.py` | CLI entry。 |
| `build_solver.py` | 被 CLI 使用时的标准 assembly entry。 |
| `case_scaffold/problem/outer_problem.py` | 解码 outer genome，并调用 inner refinement。 |
| `case_scaffold/pipeline/` | Outer structure genome 的 representation pipeline。 |
| `case_scaffold/config/` | CLI/config surface。 |
| `case_scaffold/orchestration/` | Solver assembly 和 strategy selection。 |

## 运行

```powershell
python -m examples.cases.learnable_conv_component_search.run_solver --pop-size 4 --offspring-size 4 --generations 1
```

## 预期信号（Expected signal）

有效运行应该降低 `test_rmse` 和 kernel recovery penalty，同时避免只靠增加 feature complexity 或过拟合 inner refinement surface 来获胜。
