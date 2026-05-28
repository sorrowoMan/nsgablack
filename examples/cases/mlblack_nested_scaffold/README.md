# mlblack_nested_scaffold（nsgablack 外层 + mlblack 内层）

`mlblack_nested_scaffold` 验证 nsgablack 与 mlblack 的标准嵌套组合方式。

## 这个 case 验证什么

- nsgablack 负责 outer search，搜索内层训练超参数。
- mlblack 负责 inner train-flow assembly 和模型评估。
- case 明确保持框架边界：outer orchestration 不硬编码 mlblack 内部细节。
- 当前 outer problem 调整 XGBoost-style 配置，并返回验证质量与模型复杂度。

## 是否使用 mlblack

使用。inner runtime 是 mlblack train/evaluation flow。

## nsgablack 侧能力

- 通过 `build_solver.py` 组装标准 outer solver。
- 用 outer decision vector 表示内层 ML training configuration。
- 多目标搜索 accuracy/complexity tradeoff。
- 保持 `problem/`、`pipeline/`、`adapter/`、`solver/` scaffold 边界。

## mlblack 侧能力

- supervised tabular training 的 inner train-flow assembly。
- 通过 `--fold-col` 做 fold-aware evaluation。
- 将 model metrics 投影回 nsgablack objectives。

## 搜索变量（Search variables）

| 变量 | 含义 |
|---|---|
| `n_estimators` | Boosting 轮数。 |
| `max_depth` | Tree depth / 结构复杂度。 |
| `learning_rate` | Boosting step size。 |
| `subsample` | 行采样比例。 |
| `colsample_bytree` | 特征采样比例。 |
| `reg_lambda` | L2 正则强度。 |

## 目标和指标（Objectives / Metrics）

| 目标 | 含义 |
|---|---|
| `rmse_test` | 内层 mlblack test/fold RMSE，返回给 outer problem。 |
| `model_complexity` | 由 estimator count 和 depth 构造的复杂度代理。 |

## 结构（Structure）

| 路径 | 作用 |
|---|---|
| `build_solver.py` | 标准 outer assembly 和 CLI entry。 |
| `problem/outer_problem.py` | 解码 outer variables，并调用 inner mlblack runner。 |
| `pipeline/` | Outer representation pipeline。 |
| `adapter/` | Outer search configuration。 |
| `solver/` | Solver defaults 和 assembly helpers。 |

## 运行

Smoke run：

```powershell
python examples/cases/mlblack_nested_scaffold/build_solver.py --generations 1 --batch-size 4 --fold-col test_fold_1
```

Fuller search：

```powershell
python examples/cases/mlblack_nested_scaffold/build_solver.py --generations 6 --batch-size 10 --fold-col test_fold_1
```

关键参数：

- `--mlblack-root`：mlblack repo root 路径。
- `--csv-path`：traffic table CSV。
- `--fold-col`：fold split，例如 `test_fold_1` 到 `test_fold_10`。
- `--run-dir`：case output root。

## 预期信号（Expected signal）

有效运行应该找到更低 `rmse_test` 的内层训练配置，同时通过 `model_complexity` 展示更大模型的成本。
