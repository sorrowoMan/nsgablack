# START_HERE

## 1) 这个 case 验证什么

`causal_discovery` 验证 DAG structure recovery 可以作为 black-box optimization。

- nsgablack 用 DE 搜索 flattened adjacency matrix。
- CallableBias（Kahn topological sort）强制 acyclicity；CallableBias（L1 norm）鼓励 sparsity。
- 当前 runtime path 不使用 mlblack。

指标、结构、mlblack 状态和能力信号见 `README.md`。

## 2) 验证 assembly

```powershell
python run_solver.py --check
```

## 3) 运行

```powershell
python build_solver.py --mode pc --n-vars 6 --seed 42
```

## 4) 关键指标

| 指标 | 含义 |
|---|---|
| SHD | Structural Hamming Distance：estimated DAG 与 true DAG 之间的 edge 差异数。 |
| BIC score | Bayesian Information Criterion：balance fit to data vs model complexity。 |

## 5) 预期信号

有效运行应该在合理 SHD 内恢复 synthetic DAG，且所有候选最终都是 acyclic。
