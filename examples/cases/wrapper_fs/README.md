# wrapper_fs（Wrapper Feature Selection）

`wrapper_fs` 验证 nsgablack 围绕外部 estimator 搜索 binary feature mask 的 wrapper feature selection 能力。

## 是否使用 mlblack

不使用。当前 case 直接使用 scikit-learn model evaluation。

mlblack 不在当前 active runtime path 中。未来如果升级为 mlblack 版本，可以将 fitted-estimator scoring 交给 `SupervisedEstimatorFitRegressionProblem` 或其他显式 mlblack Problem。

## 这个 case 验证什么

Wrapper feature selection 被表达为 black-box subset optimization：

- nsgablack 搜索输入特征上的 mask。
- Problem 用 `> 0.5` threshold 解码每个坐标。
- 被选中的 columns 传给 estimator。
- Cross-validation score 作为 objective。

## 搜索向量（Search vector）

| 变量 | 含义 | 范围 / 解码 |
|---|---|---|
| `x_i` | feature `i` 是否被选中 | `[0.0, 1.0]`，当 `x_i > 0.5` 时选中 |

选择少于两个特征的 candidates 会收到较大 penalty。

## 目标和指标（Objectives / Metrics）

| 目标 | 方向 | 含义 |
|---|---|---|
| `-cv_score` | minimize | 配置的 estimator/scoring pair 的 negative mean cross-validation score。 |

默认代码支持任何 scikit-learn compatible estimator 和 scoring string。

## 结构（Structure）

| 路径 | 作用 |
|---|---|
| `build_solver.py` | 标准 scaffold assembly entry。 |
| `run_solver.py` | check/run 的 CLI wrapper。 |
| `problem/feature_selection_problem.py` | 真正的 wrapper feature-selection objective。 |
| `problem/example_problem.py` | Scaffold placeholder，不是能力实现。 |
| `pipeline/config.py` | Mask-vector initialization、mutation、repair。 |
| `solver/config.py` | Solver profile registry。 |
| `catalog/entries.toml` | Case-local scaffold catalog entries。 |

## 能力信号（Capability signal）

有效运行应该在只选择部分特征的同时降低 validation/cross-validation loss。框架信号是 nsgablack 能优化 feature subsets，而不把 estimator logic 嵌入 Solver 或 Adapter。

## 运行和验证

```powershell
python run_solver.py --check
python run_solver.py
python -m nsgablack project doctor --path . --strict --format problem
```
