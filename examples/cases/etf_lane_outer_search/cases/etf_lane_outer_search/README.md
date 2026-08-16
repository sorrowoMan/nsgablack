# etf_lane_outer_search（ETF Lane 外层搜索）

`etf_lane_outer_search` 验证 nsgablack 对 mlblack ETF multi-strategy lane configuration 的 outer search 能力。

## 这个 case 验证什么

- nsgablack 搜索 ETF walk-forward evaluation 的 portfolio/lane configuration knobs。
- mlblack 提供 ETF temporal forecast data/model/evaluation surface。
- Inner evaluation 聚合大规模 ETF panel 的 walk-forward 和 multi-seed results。
- Objectives 展示 return、drawdown、turnover 和 rank-IC stability 之间的 tradeoffs。

## 是否使用 mlblack

使用。Inner path 现在调用标准 mlblack integration surface：

- `mlblack.integrations.etf_temporal_forecast.WalkForwardSpec`
- `mlblack.integrations.etf_temporal_forecast.run_etf_walkforward_multi_seed`
- 默认数据：`C:\Users\hp\Desktop\mlblack\runs\etf_temporal_forecast\cache\multi_etf_returns_momodel_kaggle.parquet`

## nsgablack 侧能力

- 17 维 outer search vector，控制 lane weights、portfolio thresholds 和 model toggles。
- 对 walk-forward portfolio metrics 做 multi-objective optimization。
- 使用 `run_solver.py` 标准 case scaffold 入口。

## mlblack 侧能力

- ETF temporal forecast data 和 feature pipeline。
- Walk-forward multi-seed evaluation。
- Inner model choices，包括 ridge、hist-gradient boosting、random forest 和 `mlp_sklearn` toggles。
- Portfolio 与 rank-IC metric computation。

## 搜索变量（Search variables）

Outer vector 控制 lane alphas、top-k selection、thresholds、blend modes，以及 ridge/random-forest/MLP-torch evaluation paths 的 model toggles。

## 目标和指标（Objectives / Metrics）

| 目标 | 含义 |
|---|---|
| `weighted_neg_net_sharpe` | Return/risk objective；sign flip 后越低代表 net Sharpe 越好。 |
| `weighted_max_drawdown_abs` | Drawdown risk penalty。 |
| `weighted_turnover_proxy` | Trading churn/cost proxy。 |
| `weighted_neg_rank_ic_mean` | Rank-IC quality objective；sign flip 后越低代表 mean rank IC 越高。 |
| `weighted_rank_ic_std` | Rank-IC stability penalty。 |

## 结构（Structure）

| 路径 | 作用 |
|---|---|
| `run_solver.py` | CLI entry。 |
| `build_solver.py` | 被 CLI 使用时的标准 assembly entry。 |
| `problem/outer_problem.py` | 解码 lane genome，并调用 mlblack walk-forward evaluation。 |
| `pipeline/` | Outer representation pipeline。 |
| `adapter/` | Outer search configuration。 |
| `solver/` | Solver defaults 和 assembly helpers。 |

## 运行

```powershell
python examples\cases\etf_lane_outer_search\run_project.py --check
python examples\cases\etf_lane_outer_search\run_project.py --suite-id etf_outer_v1
```

## 当前 reconnect smoke 指标

`python examples\cases\etf_lane_outer_search\run_project.py --suite-id etf_reconnect_smoke_fixed --pop-size 4 --offspring-size 2 --generations 1 --seeds 42 --wf-max-folds 1 --wf-max-train-panel-rows 4000 --wf-max-test-panel-rows 1600 --baseline-models ridge` 已验证 nsgablack 外层能调用新的 mlblack ETF 标准 case：

| 指标 | smoke 值 |
|---|---:|
| evaluation_count | `8` |
| best_score | `1.0921645143` |
| `composite_test_rmse_mean` | `0.0103530581` |
| `composite_direction_accuracy_mean` | `0.505` |
| `composite_rank_ic_mean` | `0.0723950625` |
| `composite_rank_ic_std` | `0.0` |
| `composite_hit_rate_mean` | `0.5` |
| `composite_net_sharpe_proxy_mean` | `-0.5582782523` |
| `composite_max_drawdown_abs_mean` | `0.0492606124` |
| `composite_turnover_proxy_mean` | `0.5570207121` |

这个 smoke 只用于验证跨框架接入；正式研究运行应增加 folds、seeds、models 和 generations。

## 预期信号（Expected signal）

有效运行应该提升 net Sharpe 或 rank IC，同时不能只靠增加 turnover、drawdown 或 instability 来换取表面收益。
