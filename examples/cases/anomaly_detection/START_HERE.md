# START_HERE

## 1) 这个 case 验证什么

`anomaly_detection` 验证 anomaly detection 超参数选优可以作为 black-box optimization。

- nsgablack DE 搜索 LOF 和 IsolationForest 的超参数。
- Objective 是 ROC-AUC（maximize，框架 minimize -ROC-AUC）。
- Baseline 是 sklearn LOF / IsolationForest 默认参数。

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
| ROC-AUC | 在 labeled anomalies 上的 detection ROC-AUC。 |

## 5) 预期信号

有效运行应该让 nsgablack DE 搜索到的超参数产生高于 sklearn 默认参数的 ROC-AUC，且不需要 manual grid search。
