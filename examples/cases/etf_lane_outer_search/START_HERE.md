# START_HERE

## 1) 这个 case 验证什么

`etf_lane_outer_search` 验证 nsgablack 对 mlblack ETF walk-forward lane configurations 的搜索能力。

- nsgablack 搜索 lane weights、thresholds、blend modes 和 model toggles。
- mlblack 评估 ETF temporal forecast walk-forward metrics。
- Objectives 平衡 Sharpe、drawdown、turnover 和 rank-IC stability。

结构、指标和预期信号见 `README.md`。

## 2) 验证 assembly

```powershell
python examples\cases\etf_lane_outer_search\run_solver.py --check
```

## 3) 运行

```powershell
python examples\cases\etf_lane_outer_search\run_solver.py --suite-id etf_outer_v1
```

## 4) 关键指标

| 目标 | 含义 |
|---|---|
| `weighted_neg_net_sharpe` | Sign flip 后的 net Sharpe 目标。 |
| `weighted_max_drawdown_abs` | Drawdown risk。 |
| `weighted_turnover_proxy` | Trading churn/cost proxy。 |
| `weighted_neg_rank_ic_mean` | Sign flip 后的 mean rank-IC 目标。 |
| `weighted_rank_ic_std` | Rank-IC stability penalty。 |

## 5) 预期信号

有效运行应该展示 portfolio-quality tradeoffs，而不是只优化单一 accuracy metric。
