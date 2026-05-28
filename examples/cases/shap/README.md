# shap（Kernel SHAP 黑箱归因优化）

`shap` 验证 nsgablack 通过最小化 Shapley-kernel-weighted reconstruction error 来搜索 Kernel SHAP attribution values。

## 是否使用 mlblack

可选 upstream only。当前 active problem 接受任何暴露 `predict` 的模型，因此被解释模型可以来自 mlblack，也可以来自 scikit-learn。

当前 mlblack 角色：

- case runtime 内部不强制需要 mlblack。
- 已训练的 mlblack model 可以作为被解释的 prediction model 传入。

nsgablack 角色：

- 搜索 attribution vector `phi`。
- 将 coalition reconstruction error 作为 black-box objective 评估。
- 可以将搜索结果与 closed-form weighted least-squares SHAP solution 对比。

## 这个 case 验证什么

Kernel SHAP 被表达为 optimization problem：

- 每个 candidate 是 `[phi_0, phi_1, ..., phi_n]`。
- 预采样 coalitions 定义目标点的 masked versions。
- 模型预测每个 coalition hybrid。
- nsgablack 最小化 weighted reconstruction error。

代码还暴露 `analytical_solution()`，作为 closed-form weighted least-squares baseline。

## 搜索向量（Search vector）

| 变量 | 含义 |
|---|---|
| `phi_0` | intercept / base contribution |
| `phi_i` | feature `i` 的 contribution |

Bounds 根据 coalition model outputs 的幅度推导。

## 目标和指标（Objectives / Metrics）

| 目标 | 方向 | 含义 |
|---|---|---|
| weighted reconstruction error | minimize | 在 sampled coalitions 上最小化 `sum_w (f(z) - phi_0 - sum_i phi_i z_i)^2`。 |

有用的对比信号：

- final weighted reconstruction error
- 到 `analytical_solution()` 的距离
- feature attribution ranking 的稳定性

## 结构（Structure）

| 路径 | 作用 |
|---|---|
| `build_solver.py` | 标准 scaffold assembly entry。 |
| `run_solver.py` | check/run 的 CLI wrapper。 |
| `problem/shap_problem.py` | 真正的 Kernel SHAP optimization objective。 |
| `problem/example_problem.py` | Scaffold placeholder，不是能力实现。 |
| `pipeline/config.py` | Attribution vector representation pipeline。 |
| `solver/config.py` | Solver profile registry。 |
| `catalog/entries.toml` | Case-local scaffold catalog entries。 |

## 能力信号（Capability signal）

关键是 search adapter 是否能恢复较低 reconstruction error，并得到接近 analytical weighted least-squares solution 的 attribution values。在这个 case 中，search 是 validation path；analytical solution 是 baseline/reference。

## 运行和验证

```powershell
python run_solver.py --check
python run_solver.py
python -m nsgablack project doctor --path . --strict --format problem
```
