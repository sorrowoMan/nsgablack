# residual_boosting（残差增强）

`residual_boosting` 是一个双框架能力 case：nsgablack 搜索 residual boosting recipe，mlblack 负责内层 base/residual training 语义。

## 是否使用 mlblack

使用。这个 case 明确验证 nsgablack + mlblack integration。

mlblack components used：

- `SerialTrainer`：按顺序执行 base stage 和 residual stage。
- `StageSpec` / `CompletionPolicy`：描述 stage wiring 和 one-step closed-form fitting。
- `ArtifactRef`：把 base model artifact 传给 residual stage。
- `NumericDataView` / `train_valid_split`：负责 tabular train/validation data semantics。
- `ModelConditionedTargetComponent`：根据 base model 构造 residual targets。
- `SupervisedRegressionProblem`：评估 validation regression metrics。
- `LinearPointModel`：表示拟合后的 base/residual linear models。
- `PredictionIntegrationComponent.additive`：组合 base + residual predictions。

nsgablack components used：

- `EvolutionSolver` / NSGA-style default search loop。
- `RepresentationPipeline`，包含 `UniformInitializer`、`GaussianMutation`、`ClipRepair`。
- 通过 `build_solver.py`、`config.py`、`assembly.py` 和 registries 使用标准 scaffold assembly。

## 这个 case 验证什么

这不只是 runnable demo。它验证 nsgablack 可以搜索 outer recipe，同时 mlblack 保留 staged residual boosting flow 的 ML 语义。

能力信号：

- Outer search 可以选择 regularization、residual weight 和 residual feature mode。
- Inner mlblack serial trainer 把 base model artifact 传入 residual stage。
- Residual targets 由 mlblack 构造，而不是硬编码在 nsgablack orchestration 中。
- Additive prediction integration 由 mlblack regression problem 评估。
- Pareto tradeoff 暴露 validation error 与 recipe complexity 的权衡。

## Recipe vector（配方向量）

| 变量 | 含义 | 范围 |
|---|---|---:|
| `x0` | base model L2 regularization | `[0.0, 0.8]` |
| `x1` | residual model L2 regularization | `[0.0, 0.8]` |
| `x2` | residual prediction weight | `[0.0, 1.5]` |
| `x3` | residual feature mode switch：raw vs enriched | `[0.0, 1.0]` |

`x3 < 0.5` 选择 raw residual features；`x3 >= 0.5` 选择带 nonlinear terms 的 enriched residual features。

## 目标和指标（Objectives / Metrics）

| 目标 | 方向 | 含义 |
|---|---|---|
| `valid_mse` | minimize | Integrated prediction model 的 validation mean squared error。 |
| `recipe_complexity` | minimize | 来自 active residual weights、residual feature mode 和 residual weight magnitude 的复杂度代理。 |

额外打印信号：

- decoded recipe
- mlblack serial stage names
- `problem.last_report` 中的 integrated model description

## 效果对比（Expected effect comparison）

Synthetic dataset 上的代表性 fixed-point comparison：

| Recipe | `valid_mse` | `recipe_complexity` | 解释 |
|---|---:|---:|---|
| base only | `4.193453` | `0.500000` | Linear base 无法建模 nonlinear target。 |
| raw residual, weight=1 | `4.193453` | `1.500000` | Residual stage 存在，但缺少 nonlinear residual features。 |
| enriched residual, weight=0.5 | `1.050285` | `7.500000` | Nonlinear features 有帮助，但 residual contribution 权重不足。 |
| enriched residual, weight=1 | `0.006224` | `8.000000` | Residual boosting 恢复了 nonlinear signal。 |

关键点是：只接上 residual stage 不够；必须正确组合 mlblack residual target 与 enriched feature semantics，nsgablack 才能观察到效果提升。

## 结构（Structure）

| 路径 | 作用 |
|---|---|
| `build_solver.py` | 唯一 solver assembly entry。 |
| `run_solver.py` | 围绕 `build_solver` 的 thin CLI wrapper。 |
| `problem/example_problem.py` | Black-box recipe problem，以及 mlblack serial training flow。 |
| `problem/config.py` | Problem registry 和 dataset parameters。 |
| `pipeline/config.py` | 四维 recipe representation pipeline。 |
| `solver/config.py` | 用于 example validation 的 smoke-sized solver profile。 |
| `catalog/entries.toml` | Case-local project catalog entries。 |

## 运行和验证

```powershell
python run_solver.py --check
python run_solver.py --quickstart
python -m nsgablack project doctor --path . --strict --format problem
```

预期输出包含：

- `best_valid_mse`
- `recipe_complexity`
- `best_recipe`
- `mlblack_serial_stages=['base_linear', 'residual_linear']`
