# START_HERE

## 1) 这个 case 验证什么

`automl` 验证 nsgablack 的 black-box AutoML recipe search。

- nsgablack 搜索 model family、hyperparameters 和 preprocessing choice。
- scikit-learn 执行 estimator fitting 与 cross-validation scoring。
- 当前 runtime path 不使用 mlblack。

指标、结构、mlblack 状态和能力信号见 `README.md`。

## 2) 验证 assembly

```powershell
python run_solver.py --check
```

## 3) 运行

```powershell
python run_solver.py
```

## 4) 关键指标

| 指标 | 含义 |
|---|---|
| `1 - cv_accuracy` | 解码后的 AutoML recipe 的 cross-validation classification error。 |

## 5) 预期信号

有效运行应该找到比 arbitrary/default recipes 更低的 CV error，同时 estimator logic 不进入 Solver/Adapter。
