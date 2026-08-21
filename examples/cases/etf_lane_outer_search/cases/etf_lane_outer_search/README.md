# etf_lane_outer_search（ETF Lane 外层搜索）

`etf_lane_outer_search` 验证 nsgablack 对 mlblack ETF multi-strategy lane configuration 的 outer search 能力。

## 这个 case 验证什么

- nsgablack 搜索 ETF walk-forward evaluation 的 portfolio/lane configuration knobs。
- mlblack 提供 ETF temporal forecast data/model/evaluation surface。
- Inner evaluation 聚合大规模 ETF panel 的 walk-forward 和 multi-seed results。
- Objectives 展示 return、drawdown、turnover 和 rank-IC stability 之间的 tradeoffs。

## 跨框架调用边界

外层 Problem 不直接导入或调用 mlblack 的 trainer/provider。每次候选评估都会构造正式的
`CaseRunRequest`，通过注入的 Case runtime 调用同一 Project 下的
`etf_lane_evaluation` Trainer Case。共享层由此统一派生父子 lineage、资源授权、预算、
deadline/cancellation，并用版本化 `TrainerResult` 信封返回结果。

`etf_lane_evaluation` 才负责调用 mlblack 的 ETF walk-forward 语义组件。数据位置由
`dataset_url` 或 mlblack 的正式数据发现机制决定；示例不依赖机器专属绝对路径。

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
| `run_solver.py` | 外层 Case 的 CLI 入口。 |
| `build_solver.py` | 外层 Solver 的 canonical assembly entry。 |
| `problem/outer_problem.py` | 解码 lane genome，并通过 Case runtime 调用正式子 Case。 |
| `pipeline/` | Outer representation pipeline。 |
| `adapter/` | Outer search configuration。 |
| `../etf_lane_evaluation/` | 独立可装配的 mlblack Trainer Case。 |

## 运行

```powershell
python examples\cases\etf_lane_outer_search\run_project.py --check --build-check
python examples\cases\etf_lane_outer_search\run_project.py
```

默认配置是可执行的 smoke profile：外层 `pop_size=4`、`generations=1`，内层使用单个
seed、单个 walk-forward fold 和 `ridge` baseline。正式研究运行应显式增加 folds、seeds、
models 和 generations，且继续由 Project L0 为父子 Case 发放资源。

## 预期信号（Expected signal）

有效运行应该提升 net Sharpe 或 rank IC，同时不能只靠增加 turnover、drawdown 或 instability 来换取表面收益。
