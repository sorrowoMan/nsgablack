# START_HERE

## 1) 这个 case 验证什么

`wrapper_fs` 验证 nsgablack 的 wrapper feature selection。

- nsgablack 搜索 binary feature mask。
- scikit-learn 通过 cross-validation 评估选中的 feature subset。
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
| `-cv_score` | 选中 feature subset 的 negative mean cross-validation score。 |

## 5) 预期信号

有效运行应该在选择部分特征的同时降低 validation loss，并且 estimator logic 不进入 nsgablack Solver/Adapter。
