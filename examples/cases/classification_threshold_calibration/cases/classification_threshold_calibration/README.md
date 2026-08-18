# classification_threshold_calibration（分类阈值校准）

`classification_threshold_calibration` 是双框架能力 case：nsgablack 搜索 classification operating point，mlblack 提供 probability-model evaluation 和 classification metrics 语义。

## 是否使用 mlblack

使用。这个 case 明确验证 nsgablack + mlblack integration。

mlblack components used：

- `NumericDataView` / `train_valid_split`：提供 tabular train/validation data semantics。
- `LinearPointModel`：表示作为 probability base 的 fixed logit model。
- `SupervisedClassificationProblem`：计算 log-loss、F1、precision、recall、accuracy、AUC 和 average precision。
- `UnknownState`：把 outer threshold/temperature recipe 带入 mlblack evaluation。

nsgablack components used：

- `EvolutionSolver` / NSGA-style default search loop。
- `RepresentationPipeline`，包含 `UniformInitializer`、`GaussianMutation`、`ClipRepair`。
- 通过 `build_solver.py`、`config.py`、`??????` 和 registries 使用标准 scaffold assembly。

## 这个 case 验证什么

这个 case 验证与 residual boosting 不同的 hybrid pattern：nsgablack 不训练分类器，而是在 mlblack-evaluated probability model 周围搜索 decision policy。

能力信号：

- Outer search 移动 operating threshold 和 temperature。
- mlblack 使用 classification metrics 评估 resulting probability model。
- Pareto tradeoff 暴露 calibration quality、F1 quality 和 intervention cost。
- 不同 thresholds 产生不同 precision/recall/intervention behavior。

## Calibration vector（校准向量）

| 变量 | 含义 | 范围 |
|---|---|---:|
| `x0` | operating threshold | `[0.05, 0.95]` |
| `x1` | probability temperature | `[0.35, 3.0]` |

Threshold 被实现为 probability model 中的 operating-point shift，因此会影响 `predict_proba`、`predict` 和 mlblack classification metrics。

## 目标和指标（Objectives / Metrics）

| 目标 | 方向 | 含义 |
|---|---|---|
| `valid_log_loss` | minimize | 来自 `SupervisedClassificationProblem` 的 mlblack validation log-loss。 |
| `f1_loss` | minimize | `1 - valid_f1`，越低代表 F1 越好。 |
| `intervention_rate` | minimize | Validation samples 中被预测为 positive 的比例。 |

额外打印信号：

- decoded threshold/temperature recipe
- validation F1
- validation precision
- validation recall

## 效果对比（Expected effect comparison）

Synthetic dataset 上的代表性 fixed-point comparison：

| Recipe | `log_loss` | `F1` | `precision` | `recall` | `intervention` | 解释 |
|---|---:|---:|---:|---:|---:|---|
| threshold=0.50, T=1.00 | `0.532556` | `0.619048` | `0.928571` | `0.464286` | `0.194444` | Conservative default，precision 高但 recall 低。 |
| threshold=0.70, T=1.00 | `0.590010` | `0.068966` | `1.000000` | `0.035714` | `0.013889` | 过于保守，几乎不预测 positives。 |
| threshold=0.25, T=0.40 | `0.463438` | `0.800000` | `0.666667` | `1.000000` | `0.583333` | Recall-heavy policy，intervention 更高。 |
| threshold≈0.274, T≈0.382 | `0.436811` | `0.830769` | `0.729730` | `0.964286` | `0.513889` | Search-selected tradeoff 同时改善 F1 和 log-loss。 |

关键点是：nsgablack 优化 decision policy variables，而 mlblack 保持 classification metric semantics。

## 结构（Structure）

| 路径 | 作用 |
|---|---|
| `build_solver.py` | 唯一 solver assembly entry。 |
| `run_solver.py` | 围绕 `build_solver` 的 thin CLI wrapper。 |
| `problem/example_problem.py` | 围绕 mlblack classification feedback 的 black-box threshold/temperature problem。 |
| `problem/config.py` | Problem registry 和 dataset parameters。 |
| `pipeline/config.py` | 二维 calibration representation pipeline。 |
| `solver/config.py` | 用于 example validation 的 smoke-sized solver profile。 |
| `catalog/entries/<kind>.toml` | Case-local project catalog entries。 |

## 运行和验证

```powershell
python run_solver.py --check
python run_solver.py --quickstart
python -m nsgablack project doctor --path . --strict --format problem
```

预期输出包含：

- `valid_log_loss`
- `f1_loss`
- `intervention_rate`
- `best_recipe`
- `valid_f1`、`precision`、`recall`
