# causal_discovery（因果发现：PC + LiNGAM）

`causal_discovery` 验证因果结构发现可以表达为黑盒优化。nsgablack DE 搜索 DAG 邻接矩阵，CallableBias 注入无环约束。

## 是否使用 mlblack

不使用。该 case 是纯 nsgablack。

## 这个 case 验证什么

因果发现被表达为组合优化：在变量间搜索有向边的 DAG 邻接矩阵：

- PC 模式：搜索二元邻接矩阵，BIC 评分最小化。
- LiNGAM 模式：搜索连续边权重，残差非高斯独立性最大化。
- CallableBias（Kahn 拓扑排序）强制无环约束。
- SparsityBias 偏好稀疏图结构。

## 搜索向量

| 模式 | 向量 | 范围 |
|---|---|---|
| PC | 扁平邻接矩阵 (n² 维) | `[0, 1]`，`> 0.5` 视为存在边 |
| LiNGAM | 扁平边权重 (n² 维) | `[-3.0, 3.0]`，包含方向和强度 |

## 目标和指标

| 目标 | 方向 | 含义 |
|---|---|---|
| BIC score (PC) | minimize | 模型拟合 + 复杂度惩罚 |
| residual MSE (LiNGAM) | minimize | 非高斯残差依赖的代理 |
| SHD | minimize | 与真实 DAG 的结构汉明距离 |

## 组件组合

| 层 | 组件 | 来源 |
|---|---|---|
| Problem | CausalDiscoveryProblem (PC/LiNGAM) | 自定义 |
| Representation | IntegerMatrixInitializer + ContextGaussianMutation + ClipRepair | 框架 repr.matrix + repr.continuous |
| Adapter | DifferentialEvolutionAdapter | 框架 adapter.de |
| Bias | CallableBias (Kahn acyclicity) + inline sparsity penalty | 框架 bias.callable |

## 效果对比

| Method | v | recovered | SHD | Time |
|---|---|---|---|---|
| nsgablack DE (PC) | 5 | 2 edges | 4 (0 correct, 2 extra, 2 missed) | 0.79s |

因果发现是困难的组合问题——在 5 变量、2 条真边的设置下，SHD=4 说明 DE 没有被引向正确的因果方向。无环约束通过 CallableBias 正确注入（未产生循环），但评分函数（BIC）不足以区分因果方向。未来方向：结合条件独立性检验作为更精细的评分信号。

## 结构

| 路径 | 作用 |
|---|---|
| `build_solver.py` | Assembly entry + 合成 DAG 生成 + SHD 对比。 |
| `problem/causal_discovery_problem.py` | BIC/残差评分 + evaluate_constraints 循环检测。 |
| `tests/test_causal_discovery.py` | 循环检测、评分、bias、约束的单元测试。 |

## 运行和验证

```powershell
python run_solver.py --seed 42 --n-vars 5 --pop-size 20 --max-steps 100 --mode pc
python run_solver.py --mode lingam --seed 123 --n-vars 5 --pop-size 20 --max-steps 100
python -m pytest tests/ -v
```
