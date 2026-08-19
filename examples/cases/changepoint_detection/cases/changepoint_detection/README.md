# changepoint_detection（变点检测）

`changepoint_detection` 验证 nsgablack 通过最小化 segmented residual variance 来搜索时间序列 changepoint positions。

## 是否使用 mlblack

不使用。当前 case 是 nsgablack-only 的 time-series segmentation 示例。

mlblack 不在当前 active runtime path 中。未来如果升级，可以使用 mlblack forecasting / rolling-origin Problems 来评估 segment-aware forecasters。

## 这个 case 验证什么

Changepoint detection 被表达为 black-box continuous/integer optimization：

- nsgablack 搜索最多 `max_changepoints` 个 candidate positions。
- Problem 对候选位置做 sort、clip 和 uniquify。
- 每个 segment 按段内均值计算 residual sum of squares。
- 更低的 average segmented residual cost 表示 structural break placement 更好。

## 搜索向量（Search vector）

| 变量 | 含义 | 范围 |
|---|---|---|
| `x_i` | candidate changepoint position | `[5, n - 5]` |

向量在评分前会被排序和去重。

## 目标和指标（Objectives / Metrics）

| 目标 | 方向 | 含义 |
|---|---|---|
| segmented RSS / `n` | minimize | 在 proposed changepoints 切分信号后的 mean residual cost。 |

有用的额外信号：

- `get_changepoints(x)` 解码出的 changepoints
- clip/deduplication 后的 unique changepoints 数量

## 结构（Structure）

| 路径 | 作用 |
|---|---|
| `build_solver.py` | 标准 scaffold assembly entry。 |
| `run_solver.py` | check/run 的 CLI wrapper。 |
| `problem/changepoint_problem.py` | 真正的 changepoint objective。 |
| `problem/example_problem.py` | Scaffold placeholder，不是能力实现。 |
| `pipeline/config.py` | Candidate position representation pipeline。 |
| `solver/config.py` | Solver profile registry。 |
| `catalog/entries/<kind>.toml` | Case-local scaffold catalog entries。 |

## 能力信号（Capability signal）

有效运行应该把 changepoints 放到接近真实 structural breaks 的位置，并相比任意切分点降低 segmented residual cost。框架信号是 nsgablack 可以把 sequence segmentation 当作通用 black-box problem 来解，而不把 time-series logic 写进 Adapter/Solver。

## 运行和验证

```powershell
python run_solver.py --check
python run_solver.py
python -m nsgablack project doctor --path . --strict --format problem
```
