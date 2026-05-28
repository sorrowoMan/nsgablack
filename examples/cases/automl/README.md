# automl（AutoML 黑箱配方搜索）

`automl` 验证 nsgablack 对小型 AutoML design space 的黑箱搜索能力；搜索空间混合了模型族、超参数和预处理选择。

## 是否使用 mlblack

不使用。当前 case 是 nsgablack + scikit-learn 示例。

拟合和评估的模型是 scikit-learn estimators。mlblack 不在当前 active runtime path 中；如果后续升级为 mlblack 验证 case，本节应明确列出使用的 mlblack Trainer / Problem / Pipeline components。

## 这个 case 验证什么

AutoML 被表达为 black-box optimization：

- nsgablack 搜索 mixed continuous/discrete recipe vector。
- Problem 将一个坐标解码为 model family。
- 其他坐标解码为 model hyperparameters 和 preprocessing toggles。
- Objective 是所选 estimator 的 cross-validation error。

## 搜索向量（Search vector）

| 变量 | 含义 | 范围 / 解码 |
|---|---|---|
| `x0` | model family | `0`: logistic regression, `1`: decision tree, `2`: random forest |
| `x1` | continuous hyperparameter | 根据模型族解码为 `C`、split proxy 或 tree-count proxy |
| `x2` | depth / model-size proxy | 类整数 depth 或 complexity value |
| `x3` | preprocessing switch | `> 0.5` 启用 `StandardScaler` |

## 目标和指标（Objectives / Metrics）

| 目标 | 方向 | 含义 |
|---|---|---|
| `1 - cv_accuracy` | minimize | 3-fold cross-validation classification error。 |

无法 fit/evaluate 的候选返回 `1.0`，使 invalid recipes 被成功候选支配。

## 结构（Structure）

| 路径 | 作用 |
|---|---|
| `build_solver.py` | 标准 scaffold assembly entry。 |
| `run_solver.py` | check/run 的 CLI wrapper。 |
| `problem/automl_problem.py` | 真正的 AutoML black-box objective。 |
| `problem/example_problem.py` | Scaffold placeholder，不是能力实现。 |
| `pipeline/config.py` | Representation init/mutate/repair configuration。 |
| `solver/config.py` | Solver profile registry。 |
| `catalog/entries.toml` | Case-local scaffold catalog entries。 |

## 能力信号（Capability signal）

有效运行应该找到比 arbitrary/default recipes 更低的 cross-validation error。重点不是哪个 estimator 胜出，而是 nsgablack 能在 Solver 不理解 estimator 内部细节的情况下优化 heterogeneous AutoML recipe。

## 运行和验证

```powershell
python run_solver.py --check
python run_solver.py
python -m nsgablack project doctor --path . --strict --format problem
```
