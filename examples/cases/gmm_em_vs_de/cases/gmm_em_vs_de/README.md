# gmm_em_vs_de（高斯混合模型：EM vs DE→VNS）

`gmm_em_vs_de` 验证 GMM 拟合可以表达为黑盒优化。nsgablack DE→VNS 两阶段搜索 (μ,Σ,π) 参数，sklearn EM 作为专业基线。

## 是否使用 mlblack

不使用。该 case 是纯 nsgablack。

## 这个 case 验证什么

GMM 被表达为连续参数空间的黑盒搜索，不借助 EM 算法的解析更新：

- nsgablack StrategyChainAdapter 编排 DE（全局探索）→ VNS（局部精修）。
- NelderMeadBias 在评估中软推单纯形局部精修。
- Problem 计算负对数似然作为目标。

能力信号：黑盒搜索可以在完全不知道 EM 更新公式的情况下逼近 GMM 似然。

## 搜索向量

| 变量 | 含义 | 范围 |
|---|---|---|
| μ_i | 第 i 个成分的均值向量 (d 维) | `[data_min, data_max]` |
| σ_i | 第 i 个成分的对角协方差 | `[0.1, 5.0]` |
| π_i | 第 i 个成分的混合权重 | softmax 归一化 |

维度 = k × d × 3（均值 + 协方差对角 + 混合权重）。

## 目标和指标

| 目标 | 方向 | 含义 |
|---|---|---|
| NLL | minimize | `-Σ log Σ_k π_k N(x | μ_k, σ_k)` |

## 组件组合

| 层 | 组件 | 来源 |
|---|---|---|
| Problem | GMMProblem | 自定义 |
| Representation | UniformInitializer + ContextGaussianMutation + ClipRepair | 框架 repr.continuous |
| Adapter | StrategyChainAdapter: Phase1=DE, Phase2=WarmStartVNS | 框架 adapter.serial_strategy |
| Bias | NelderMeadBias | 框架 bias.local_nelder_mead |

## 效果对比

| Method | NLL | Time | vs EM |
|---|---|---|---|
| sklearn GaussianMixture (EM) | 1161.69 | 0.25s | baseline |
| nsgablack DE→VNS | 1924.98 | 0.43s | 1.66× |

DE→VNS 的 NLL 约为 EM 的 1.66 倍——这是预期的：黑盒搜索不利用 EM 的解析梯度，但可以在没有领域知识的情况下逼近。策略链证明了 nsgablack 可以编排多阶段搜索。

## 结构

| 路径 | 作用 |
|---|---|
| `build_solver.py` | Assembly entry + benchmark CLI。 |
| `problem/gmm_problem.py` | GMM NLL 计算。 |
| `catalog/entries/<kind>.toml` | Case-local catalog entries。 |

## 运行和验证

```powershell
python run_solver.py --seed 42 --k 3 --n-samples 300 --pop-size 20 --max-steps 80
python -m nsgablack project doctor --path . --strict --format problem
```
