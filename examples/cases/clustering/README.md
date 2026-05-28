# Clustering Benchmark（聚类基准）

`clustering` 验证聚类可以被表达为 centroid assignments/locations 上的 black-box optimization，而不是必须写成专门的聚类算法实现。

## 这个 case 验证什么

- nsgablack 使用通用 black-box optimizers 求解 clustering objective。
- Differential Evolution 可以在 Solver 中没有聚类专用逻辑的情况下，收敛到 sklearn KMeans-like SSE。
- Simulated Annealing 作为 single-trajectory baseline，用于对比稳定性。
- 当前不使用 mlblack；这是 optimization-only benchmark。

## 是否使用 mlblack

不使用。该 case 比较 nsgablack optimizers 与 sklearn KMeans 在 clustering objective 上的表现。

## nsgablack 能力体现

- 对 clustering loss 做通用 black-box optimization。
- Differential Evolution 与 Simulated Annealing 的 adapter comparison。
- Representation/problem separation：聚类语义留在 Problem，不进入 Adapter/Solver。

## 指标和目标（Metrics / Objectives）

| 指标 | 含义 |
|---|---|
| SSE | 到所分配 centroid 的平方距离和，越低越好。 |
| vs sklearn | 相对 sklearn KMeans baseline 的比例。 |
| runtime | 每种方法的 wall-clock 对比。 |
| convergence by steps | 展示 DE 随预算增加如何接近 sklearn-like solution。 |

## Benchmark results（基准结果）

5 个随机种子平均：

| Method | Avg SSE | vs sklearn | Avg Time |
|---|---:|---:|---:|
| sklearn KMeans (Lloyd) | 1224.8 | baseline | 0.13s |
| nsgablack DE | 1331.6 | 1.087x | 0.91s |
| nsgablack SA | 4310.6 | 3.52x | 0.79s |

DE 随 step budget 收敛：

| DE steps | SSE | vs sklearn |
|---|---:|---:|
| 100 | 1541.9 | 1.21x |
| 200 | 1301.5 | 1.02x |
| 400 | 1275.8 | 1.0003x |
| 800 | 1275.4 | 1.0000x |

## 结构（Structure）

| 路径 | 作用 |
|---|---|
| `clustering_problem.py` | Black-box clustering objective。 |
| `ALGORITHM_DECOMPOSITION.md` | 将算法族拆解为 capability cases 的方法论说明。 |
| benchmark scripts/files | 运行 sklearn、DE 和 SA 对比。 |

## 预期信号（Expected signal）

有效运行应该显示 DE 随预算增加接近 sklearn KMeans-quality SSE，证明框架可以将聚类表达为可复用的 black-box optimization problem。SA 可能不稳定，因为 single trajectory 更容易陷入较差局部极小值。
