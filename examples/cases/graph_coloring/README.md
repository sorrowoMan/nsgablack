# graph_coloring（图着色）

`graph_coloring` 验证 nsgablack 搜索 graph color assignments，并同时惩罚 adjacency conflicts 和 color count。

## 是否使用 mlblack

不使用。当前 case 是 nsgablack-only combinatorial optimization 示例。

mlblack 不在当前 active runtime path 中，因为该问题没有 ML training/evaluation component。

## 这个 case 验证什么

Graph coloring 被表达为 black-box discrete assignment optimization：

- nsgablack 为每个 node 搜索一个 color coordinate。
- 坐标会被 cast 为 integer colors，并对 `max_colors` 取模。
- Edge conflicts 被重罚。
- 在冲突受控后，进一步最小化 distinct colors 数量。

## 搜索向量（Search vector）

| 变量 | 含义 | 范围 / 解码 |
|---|---|---|
| `x_i` | node `i` 的 color | `[0, max_colors)`，cast to `int` 后 modulo `max_colors` |

## 目标和指标（Objectives / Metrics）

| 目标 | 方向 | 含义 |
|---|---|---|
| `conflicts * 1000 + n_colors` | minimize | Lexicographic-style scalar penalty：先消除 conflicts，再减少 color count。 |

有用的额外信号：

- conflict count
- number of colors used
- final coloring feasibility

## 结构（Structure）

| 路径 | 作用 |
|---|---|
| `build_solver.py` | 标准 scaffold assembly entry。 |
| `run_solver.py` | check/run 的 CLI wrapper。 |
| `problem/coloring_problem.py` | 真正的 graph-coloring objective。 |
| `problem/example_problem.py` | Scaffold placeholder，不是能力实现。 |
| `pipeline/config.py` | Node-color representation pipeline。 |
| `solver/config.py` | Solver profile registry。 |
| `catalog/entries.toml` | Case-local scaffold catalog entries。 |

## 能力信号（Capability signal）

有效运行应该先把 conflict count 推向 0，再减少 color 数量。框架信号是 generic nsgablack search 可以处理 discrete graph assignments，而不需要 graph-specific Solver logic。

## 运行和验证

```powershell
python run_solver.py --check
python run_solver.py
python -m nsgablack project doctor --path . --strict --format problem
```
