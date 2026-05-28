# START_HERE

## 1) 这个 case 验证什么

`clustering` 验证聚类可以作为 black-box optimization problem。

- nsgablack 优化 clustering objective，不在 solver 中嵌入 Lloyd/KMeans 逻辑。
- Differential Evolution 与 sklearn KMeans、Simulated Annealing 做对比。
- 当前 runtime path 不使用 mlblack。

Benchmark results、指标和能力信号见 `README.md`。

## 2) 关键指标

| 指标 | 含义 |
|---|---|
| SSE | 到所分配 centroid 的平方距离和，越低越好。 |

## 3) Baseline signal

| Method | Avg SSE | vs sklearn |
|---|---:|---:|
| sklearn KMeans | 1224.8 | baseline |
| nsgablack DE | 1331.6 | 1.087x |
| nsgablack SA | 4310.6 | 3.52x |

## 4) 预期信号

有效运行应该显示 DE 随 step budget 增加逐渐接近 sklearn-like SSE，而 SA 展示 single-trajectory local search 在该目标上的弱点。
