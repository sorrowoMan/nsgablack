# START_HERE

## 1) 这个 case 验证什么

`changepoint_detection` 验证 nsgablack 通过 black-box search 做 time-series segmentation。

- nsgablack 搜索 changepoint positions。
- Objective 评估 segmented residual variance。
- 当前 runtime path 不使用 mlblack。

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
| segmented RSS / `n` | 在 proposed changepoints 切分信号后的 mean residual cost。 |

## 5) 预期信号

有效运行应该把 changepoints 放到接近 structural breaks 的位置，并相比任意切分点降低 segmented residual cost。
