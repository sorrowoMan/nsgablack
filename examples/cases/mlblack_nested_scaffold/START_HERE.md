# START_HERE

## 1) 这个 case 验证什么

`mlblack_nested_scaffold` 验证标准 nsgablack-outer / mlblack-inner 工作流。

- nsgablack 搜索内层训练超参数。
- mlblack 执行 supervised train/evaluation flow。
- Objectives 展示 test RMSE 与 model complexity 的权衡。

变量、指标、结构和预期信号见 `README.md`。

## 2) Smoke run

```powershell
python examples/cases/mlblack_nested_scaffold/build_solver.py --generations 1 --batch-size 4 --fold-col test_fold_1
```

## 3) Fuller search

```powershell
python examples/cases/mlblack_nested_scaffold/build_solver.py --generations 6 --batch-size 10 --fold-col test_fold_1
```

## 4) 关键参数

| 参数 | 含义 |
|---|---|
| `--mlblack-root` | mlblack repo root 路径。 |
| `--csv-path` | Traffic table CSV。 |
| `--fold-col` | Fold split，例如 `test_fold_1`。 |
| `--run-dir` | Case output root。 |

## 5) 关键指标

| 目标 | 含义 |
|---|---|
| `rmse_test` | 内层 mlblack test/fold RMSE。 |
| `model_complexity` | 由 estimator count 和 depth 构造的复杂度代理。 |

## 6) 预期信号

有效运行应该改善 `rmse_test`，并让 accuracy/complexity tradeoff 变得可见。
