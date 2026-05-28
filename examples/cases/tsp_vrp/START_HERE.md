# START_HERE

## 1) 这个 case 验证什么

`tsp_vrp` 验证 combinatorial route optimization 可以作为 black-box optimization。

- nsgablack 用 SA 搜索 city visitation permutation。
- Random-keys encoding 保证 valid permutation，无需 explicit repair。
- 当前 runtime path 不使用 mlblack。

指标、结构、mlblack 状态和能力信号见 `README.md`。

## 2) 验证 assembly

```powershell
python run_solver.py --check
```

## 3) 运行

```powershell
python build_solver.py --n-cities 20 --pop-size 30 --max-steps 2000
```

## 4) 关键指标

| 指标 | 含义 |
|---|---|
| 总里程 | 访问所有城市并返回起点的总路径长度。 |
| vs Nearest-Neighbor | 相对于贪心基线的改进百分比。 |

## 5) 预期信号

有效运行应该让 SA 路线明显短于 Nearest-Neighbor 贪心基线。
