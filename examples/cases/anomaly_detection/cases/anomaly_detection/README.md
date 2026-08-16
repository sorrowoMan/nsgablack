# anomaly_detection（异常检测：LOF + Isolation Forest）

`anomaly_detection` 验证异常检测算法的超参数可以作为黑盒优化问题。nsgablack DE 搜索 LOF/IsolationForest 参数，ConstraintBias 强制污染率范围。

## 是否使用 mlblack

不使用。该 case 是纯 nsgablack。

## 这个 case 验证什么

异常检测超参数调优被表达为黑盒搜索：

- DE 在 k_neighbors 和 contamination 上搜索（LOF 模式）。
- 或在 n_estimators、max_samples、max_features 上搜索（IsolationForest 模式）。
- ConstraintBias 确保污染率在合理范围 [0.01, 0.5]。
- 目标为 ROC-AUC（最大化异常检测能力）。

## 搜索向量

| 模式 | 变量 | 范围 |
|---|---|---|
| LOF | k_neighbors | [2, 100] |
| LOF | contamination | [0.01, 0.5] |
| iForest | n_estimators | [50, 500] |
| iForest | max_samples | [0.1, 1.0] |
| iForest | max_features | [0.1, 1.0] |

## 目标和指标

| 目标 | 方向 | 含义 |
|---|---|---|
| ROC-AUC | maximize | 异常检测区分能力 |

## 组件组合

| 层 | 组件 | 来源 |
|---|---|---|
| Problem | LOFProblem / IsolationForestProblem | 自定义 |
| Representation | UniformInitializer + ContextGaussianMutation + ClipRepair | 框架 repr.continuous |
| Adapter | DifferentialEvolutionAdapter | 框架 adapter.de |
| Bias | ConstraintBias | 框架 bias.constraint |

## 效果对比

| Method | ROC-AUC | Time |
|---|---|---|
| sklearn LOF (default k=20) | 1.0000 | 0.002s |
| nsgablack DE → LOF (k=57) | 1.0000 | 3.10s |

在简单合成数据集上两者表现相同（ROC-AUC=1.0）。DE 发现了与 sklearn 默认值不同的最优超参数（k=57 vs k=20），两者都完美区分了异常点。难点在于构造硬数据集使参数搜索产生有意义的区分。

## 结构

| 路径 | 作用 |
|---|---|
| `build_solver.py` | Assembly entry + 合成异常数据 + DE vs sklearn 对比。 |
| `problem/isolation_forest_problem.py` | LOF/iForest 超参数评分。 |

## 运行和验证

```powershell
python build_solver.py --seed 42 --n-samples 200 --n-outliers 10 --pop-size 15 --max-steps 50 --mode lof
python build_solver.py --mode iforest
```
