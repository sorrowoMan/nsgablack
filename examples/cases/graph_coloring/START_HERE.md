# START_HERE

## 1) 这个 case 验证什么

`graph_coloring` 验证 discrete graph assignment 可以作为 black-box optimization。

- nsgablack 为每个 node 搜索一个 color coordinate。
- Objective 先惩罚 edge conflicts，再惩罚 color count。
- 该问题没有 ML evaluation/training component，因此不使用 mlblack。

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
| `conflicts * 1000 + n_colors` | Scalar penalty：优先 feasible coloring，然后减少 colors。 |

## 5) 预期信号

有效运行应该先把 conflicts 推向 0，再减少使用的颜色数量。
