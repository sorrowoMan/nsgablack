# tsp_vrp（旅行商 / 车辆路径问题）

`tsp_vrp` 验证排列组合优化可以使用框架图约束 bias 解决。nsgablack SA + 内置排列编码 + TSP/哈密顿约束，无需自定义 representation 或 bias。

## 是否使用 mlblack

不使用。该 case 是纯 nsgablack。

## 这个 case 验证什么

TSP 被表达为排列搜索：

- PermutationInitializer（框架 repr.permutation）编码访问顺序。
- SimulatedAnnealing 接受/拒绝新排列。
- TSPConstraintBias 惩罚违反 TSP 约束（如重复/遗漏城市）。
- HamiltonianPathConstraintBias 强化哈密顿路径语义（每个城市恰好访问一次并返回）。

能力信号：框架已有图约束 bias，排列组合优化几乎不需自定义代码。

## 搜索向量

| 变量 | 编码 | 解码 |
|---|---|---|
| 排列 (n cities) | PermutationInitializer | argsort → 城市访问顺序 |

## 目标和指标

| 目标 | 方向 | 含义 |
|---|---|---|
| 总里程 | minimize | Σ distance(city_i, city_{i+1}) + distance(city_n, city_0) |

## 组件组合

| 层 | 组件 | 来源 |
|---|---|---|
| Problem | TSPProblem | 自定义 |
| Representation | PermutationInitializer + ContextGaussianMutation | 框架 repr.permutation + repr.context_gaussian |
| Adapter | SimulatedAnnealingAdapter | 框架 adapter.sa |
| Bias | TSPConstraintBias + HamiltonianPathConstraintBias | 框架 bias.graph_tsp_constraint + bias.graph_hamiltonian_constraint |

## 效果对比

| Method | 总里程 | Time | vs NN |
|---|---|---|---|
| Nearest-Neighbor 贪心 | 339.38 | <0.01s | baseline |
| nsgablack SA | 313.02 | 4.95s | **+7.8%** |

15 个城市、20 个候选、2000 步下，SA 持续优于贪心基线 7-8%。排列编码 + 图约束 bias 的组合展示了框架在组合优化上的即插即用能力。

## 结构

| 路径 | 作用 |
|---|---|
| `build_solver.py` | Assembly entry + 随机城市生成 + NN vs SA 对比。 |
| `problem/tsp_problem.py` | 排列解码 + 总里程计算。 |

## 运行和验证

```powershell
python run_solver.py --seed 42 --n-cities 15 --pop-size 20 --max-steps 2000
python -m nsgablack project doctor --path . --strict --format problem
```
