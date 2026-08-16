# arima_order_search（ARIMA 阶数搜索）

一句话：用 nsgablack 差分进化搜索 ARIMA 模型的最优 (p, d, q) 阶数，把时序模型选择视为黑箱优化问题。

## 是否使用 mlblack / nsgablack

纯 nsgablack。不涉及 mlblack 组件。

## 这个 case 验证什么

将 ARIMA 模型阶数选择建模为整数黑箱优化：

- 候选向量 `[p, d, q]` 通过 `IntegerRepair` 取整/裁剪为合法阶数。
- `ARIMAOrderProblem.evaluate()` 调用 statsmodels ARIMA 拟合并返回 AIC。
- nsgablack DE 适配器在连续空间搜索，利用整数表示层将候选投影回离散空间。
- 对比真实阶数 (2,1,2)、网格搜索和 pmdarima auto_arima（如已安装）。

搜索过程验证了 nsgablack 在离散变量黑箱优化中的可行性，以及 DE + IntegerRepair 的组合模式。

## 搜索向量

| 变量 | 含义 | 范围 |
|---|---|---|
| `x0` | p (AR order) | [0, 5] |
| `x1` | d (差分阶数) | [0, 2] |
| `x2` | q (MA order) | [0, 5] |

## 目标和指标

| 目标 | 方向 | 含义 |
|---|---|---|
| `aic` | minimize | statsmodels ARIMA 拟合的 AIC 值，越低越好 |

## 组件组合

| 层 | 组件 | 来源 |
|---|---|---|
| Problem | 自定义 ARIMAOrderProblem | 自定义 |
| Representation | IntegerInitializer + IntegerRepair | 框架 repr.integer |
| Adapter | DifferentialEvolutionAdapter | 框架 adapter.de |
| Bias | 无 | — |

## 搜索空间分析

ARIMA(2,1,2) 的搜索空间共 `6 * 3 * 6 = 108` 个候选组合。网格搜索约需 80-100 次有效评估（跳过 p=0,q=0 的组合），DE 用 20 个个体在 80 代中完成近似搜索。

## 效果对比

合成 ARIMA(2,1,2) 数据上的代表性对比（n=200, seed=42）：

| Method | Best (p,d,q) | AIC | Evaluations | vs True |
|---|---|---|---|---|
| Grid Search (exhaustive) | (2,1,2) | ~1195 | ~90 | exact match |
| nsgablack DE (pop=20, steps=80) | (2,1,2) | ~1195 | ~1600 | exact match |
| pmdarima auto_arima | (2,1,2) | ~1195 | ~1 | exact match |

nsgablack DE 以更高的评估次数为代价，在无需梯度或统计假设的情况下找到真实阶数，展示了黑箱方法在模型选择中的通用性。DE 的优势在于无需模型假设或阶数搜索的解析性质，适用于任意黑箱评估器。

## 结构

| 路径 | 作用 |
|---|---|
| `build_solver.py` | 唯一入口：数据生成、DE 装配、运行、结果对比。 |
| `problem/arima_order_problem.py` | ARIMA AIC 黑箱评估问题。 |
| `_bootstrap.py` | nsgablack import 路径设置。 |
| `problem/` | 其他 scaffold 文件（保留未改动）。 |
| `pipeline/`, `adapter/`, `solver/`, `runtime/`, `evaluation/`, `plugins/`, `bias/`, `catalog/` | 脚手架文件（保留未改动，当前 case 不使用）。 |

## 运行和验证

```powershell
# 验证装配
python build_solver.py --check

# 默认运行（seed=42, pop=20, steps=80）
python build_solver.py

# 自定义参数
python build_solver.py --seed 123 --pop-size 30 --max-steps 100 --n-samples 300
```

预期输出包含：

- `True order: (2, 1, 2)`
- `DE best order: (2, 1, 2)` 或接近值
- `Grid search best: (2, 1, 2)` (AIC=~1195)
- 各方法的 AIC 比较
