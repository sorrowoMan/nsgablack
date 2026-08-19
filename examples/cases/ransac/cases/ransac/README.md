# ransac（鲁棒子集选择）

`ransac` 验证 nsgablack 通过搜索 inlier mask 来做 RANSAC-style robust linear regression。

## 是否使用 mlblack

不使用。当前 case 是 nsgablack-only robust fitting 示例，使用 NumPy least squares。

mlblack 不在当前 active runtime path 中。未来如果升级，可以把 fitted model scoring 交给 `SupervisedRegressionProblem` 或 estimator-fit Problem。

## 这个 case 验证什么

RANSAC 被表达为 subset optimization：

- nsgablack 为每个 sample 搜索一个 mask coordinate。
- 坐标大于 `0.5` 的样本视为 inliers。
- Problem 在选中的 inliers 上做 least squares fit。
- Objective 是 selected inlier set 上的 residual sum of squares。

## 搜索向量（Search vector）

| 变量 | 含义 | 范围 / 解码 |
|---|---|---|
| `x_i` | sample `i` 是否为 inlier | `[0.0, 1.0]`，当 `x_i > 0.5` 时为 inlier |

少于 20 个 inliers 的 candidates 会收到较大 penalty。

## 目标和指标（Objectives / Metrics）

| 目标 | 方向 | 含义 |
|---|---|---|
| inlier RSS | minimize | Selected inliers 上的 least-squares residual sum of squares。 |

有用的额外信号：

- selected inliers 数量
- fitted coefficient stability
- outlier rejection behavior

## 结构（Structure）

| 路径 | 作用 |
|---|---|
| `build_solver.py` | 标准 scaffold assembly entry。 |
| `run_solver.py` | check/run 的 CLI wrapper。 |
| `problem/ransac_problem.py` | 真正的 inlier-mask objective。 |
| `problem/example_problem.py` | Scaffold placeholder，不是能力实现。 |
| `pipeline/config.py` | Mask-vector representation pipeline。 |
| `solver/config.py` | Solver profile registry。 |
| `catalog/entries/<kind>.toml` | Case-local scaffold catalog entries。 |

## 能力信号（Capability signal）

有效运行应该在存在 outliers 的情况下找到 residual cost 较低的 inlier subset。框架信号是 nsgablack 可以在没有专门 RANSAC Adapter 的情况下解决 robust subset selection。

## 运行和验证

```powershell
python run_solver.py --check
python run_solver.py
python -m nsgablack project doctor --path . --strict --format problem
```
