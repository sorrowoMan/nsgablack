# START_HERE

## 1) 这个 case 验证什么

`arima_order_search` 验证 nsgablack 对离散整数搜索空间的黑箱优化能力。

- nsgablack DE（差分进化）在连续空间搜索 (p, d, q)。
- `IntegerRepair` 把连续候选向量取整/裁剪为合法 ARIMA 阶数。
- `ARIMAOrderProblem` 调用 statsmodels ARIMA 拟合，返回 AIC。

完整指标、结构、效果对比见 `README.md`。

## 2) 验证 assembly

```powershell
python build_solver.py --check
```

## 3) 运行搜索

```powershell
python build_solver.py --seed 42 --pop-size 20 --max-steps 80
```

## 4) 关键指标

| 指标 | 含义 |
|---|---|
| `DE best order` | nsgablack DE 搜索到的 (p, d, q) |
| `DE best AIC` | 对应模型的 AIC，越低越好 |
| `Grid search best` | 穷举网格搜索的 (p, d, q)，作为 baseline 对比 |
| `pmdarima order` | pmdarima auto_arima 的结果（可选） |

## 5) 预期信号

有效运行应命中或接近真实阶数 `(2, 1, 2)`，AIC 接近或低于网格搜索最优值。
