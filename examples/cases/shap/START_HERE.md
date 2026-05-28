# START_HERE

## 1) 这个 case 验证什么

`shap` 验证 Kernel SHAP 可以作为 black-box attribution optimization problem。

- nsgablack 搜索 attribution vector `phi`。
- prediction model 只要暴露 `predict`，可以来自 mlblack 或 scikit-learn。
- 当前 runtime path 中 mlblack 只是 optional upstream。

指标、结构、mlblack 状态、analytical baseline 和能力信号见 `README.md`。

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
| weighted reconstruction error | sampled coalitions 上的 Shapley-kernel-weighted error。 |

## 5) 预期信号

有效运行应该接近 closed-form weighted least-squares solution，并产生稳定的 feature attribution ranking。
