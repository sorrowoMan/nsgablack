# START_HERE

## 1) 这个 case 验证什么

`gmm_em_vs_de` 验证 GMM 参数估计可以作为 black-box optimization。

- GMM 参数搜索被分解为 DE（全局探索）→ VNS（局部精修）两阶段策略链。
- Objective 是 negative log-likelihood（minimize）。
- Baseline 是 sklearn GaussianMixture（EM）。

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
| NLL | 在合成数据上的 GMM negative log-likelihood。 |

## 5) 预期信号

有效运行应该让 DE→VNS 策略链的 NLL 接近 sklearn EM baseline，且不需要 specialized EM machinery。
