# nsgablack — 模块化说明与完整使用指南

## 目录

1. [框架概览](#1-框架概览)
2. [快速上手](#2-快速上手)
3. [核心类与约束处理](#3-核心类与约束处理)
4. [Bias 模块：智能搜索引导](#4-bias-模块智能搜索引导)
5. [并行批量运行与元优化](#5-并行批量运行与元优化)
6. [典型应用场景速览](#6-典型应用场景速览)
7. [参数参考表](#7-参数参考表按参数详尽)

---

## 1. 框架概览

本仓库提供了一个**面向"黑箱函数/工程仿真"的优化与分析框架**，围绕以下几个核心目标设计：

- **统一抽象**：用一个统一的 `BlackBoxProblem` 抽象，把"目标函数 + 约束 + 变量边界"打包起来，便于在不同优化算法之间复用
- **多种优化器**：提供 NSGA-II 与 VNS 等多种优化器，实现从全局多目标搜索到局部多邻域搜索的完整链路
- **双模式运行**：同时支持**可视化交互**（调试、教学）和**无界面 headless 运行**（批量实验、服务器部署、云端任务）
- **智能优化**：借助历史解、多样性初始化、精英管理、ML 模型与降维工具，在复杂工程问题上逐步"积累经验"、提升搜索效率
- **高性能**：通过并行批量运行、元优化与可选 Numba 加速，在保证易用性的前提下尽可能挖掘 CPU 性能

### 1.1 模块一览

| 模块                                  | 说明                                                                                                                         |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `nsgablack/base.py`                 | `BlackBoxProblem`基类，统一问题接口（`evaluate`, `get_num_objectives`）                                                |
| `nsgablack/solver.py`               | `BlackBoxSolverNSGAII`：NSGA-II 求解器核心，包含选择/交叉/变异、非支配排序、历史记录与收敛判定                             |
| `nsgablack/surrogate.py`            | `SurrogateAssistedNSGAII`：代理模型辅助的 NSGA-II，支持 GP/RBF/RF/Ensemble 模型，包含模型保存/加载、质量监控、在线学习功能 |
| `nsgablack/vns.py`                  | `BlackBoxSolverVNS`：可配置多邻域与变尺度策略的 VNS 单/多目标（标量化）求解器                                              |
| `nsgablack/visualization.py`        | `SolverVisualizationMixin`：Matplotlib UI 与绘图混入，提供交互控件（运行/停止/参数调整）                                   |
| `nsgablack/diversity.py`            | `DiversityAwareInitializerBlackBox`：多样性感知的候选解采样与种群初始化，支持历史解存取                                    |
| `nsgablack/elite.py`                | `AdvancedEliteRetention`：自适应精英保留/替换策略，可配置替换比与权重                                                      |
| `nsgablack/convergence.py`          | 收敛日志与评估工具（SVM/聚类方法评估收敛簇）                                                                                 |
| `nsgablack/headless.py`             | 无界面运行辅助：`CallableSingleObjectiveProblem` 和 `run_headless_single_objective`                                      |
| `nsgablack/metaopt.py`              | 遗传算法元优化模块：自动搜索 NSGA-II 超参数，支持多指标与多后端                                                              |
| `nsgablack/problems.py`             | 若干内置示例问题（Sphere, ZDT1, 仿真、NN 超参、工程设计、投资组合）                                                          |
| `nsgablack/exmaple.py`              | 附加工具：特征选择、PCA/KPCA/PLS/ActiveSubspace/Autoencoder 降维接口与示例流程                                               |
| `nsgablack/__init__.py`             | 对外统一导出常用类和函数                                                                                                     |
| `nsgablack/ml_models.py`            | ML 模型管理：`ModelManager`，负责训练/保存/续训/加载机器学习模型（joblib 持久化）                                          |
| `nsgablack/ml_guided_ga_example.py` | ML-guided GA 示例：`ClassifierHistoryAwareInitializer`、`ClassifierHistoryAwareReducedInitializer`与完整流水线示例       |
| `nsgablack/bias.py`                 | `BiasModule`：可扩展的优化偏向模块，通过奖函数和罚函数引导搜索方向，支持自定义奖励/惩罚策略                                |

### 1.2 主要特点

- **统一的黑箱问题抽象**：
  - 通过 `BlackBoxProblem` 统一封装"目标函数 + 约束 + 变量边界"，支持单目标、多目标和带不等式约束的问题；
  - 约束采用 Deb 风格的违背度统一处理，可行解优先，其次违背度更小者更优，用户不必关心内部策略切换。

- **NSGA-II 与 VNS 双优化核心**：
  - `BlackBoxSolverNSGAII`：完整实现多目标 NSGA-II，包括选择/交叉/变异、非支配排序、拥挤距离和精英保留，适合 Pareto 前沿搜索；
  - `BlackBoxSolverVNS`：轻量的 Variable Neighborhood Search（VNS）实现，支持多种邻域类型与尺度策略，适合快速单目标或标量化多目标局部搜索；
  - 两者都基于同一 `BlackBoxProblem` 抽象，便于在不同优化器之间切换和对比。

- **代理模型辅助优化 (Surrogate-Assisted)**：
  - `SurrogateAssistedNSGAII`：专为**昂贵黑箱函数**（如耗时仿真）设计；
  - 支持 **Gaussian Process (GP)**、**RBF 网络**、**Random Forest (RF)** 和 **Ensemble（集成）** 四种代理模型；
  - 采用"少量真实评估 + 大量代理评估"的策略，显著减少真实函数调用次数（通常可节省 80%-90% 的时间）；
  - 支持单目标和多目标优化，自动管理模型训练与更新；
  - **功能**：
    - 模型保存/加载：避免重复训练，支持跨会话复用模型；
    - 质量监控：自动计算 R²、RMSE 指标，检测模型退化并触发重训练；
    - 在线学习：增量更新模型，减少训练时间；
    - 多模型集成：GP+RF+RBF 加权平均，根据验证集性能动态调整权重，提高预测鲁棒性。

- **Headless + GUI 双模式运行**：
  - `run_headless_single_objective` 提供完全无界面、可脚本化的单目标优化接口，适合服务器、云端和批量实验；
  - `SolverVisualizationMixin` 结合 Matplotlib，提供交互式 GUI：可视化种群、Pareto 前沿，支持通过按钮/文本框动态调整 `pop_size`、`max_generations`、变异率等；
  - 通过参数 `plot` / `plot_enabled` 可以灵活切换，无需改动核心求解代码。

- **多样性感知初始化与历史复用**：
  - `DiversityAwareInitializerBlackBox` 支持基于历史解文件的多样性采样，可在高质量解附近增强探索、同时避免过度聚集；
  - 提供候选池大小、相似度阈值、拒绝概率等可调参数，并支持 LHS/随机多种采样策略；
  - 历史解可跨实验重复利用，实现"经验积累"，在多批次实验中逐渐提升初始化质量。

- **智能精英保留策略**：
  - `AdvancedEliteRetention` 提供自适应精英保留/替换机制，而不是简单固定比例的"精英复制"：
    - 根据代数进度、适应度变化和多样性等因素动态调整精英替换比例；
    - 支持配置 `min_replace_ratio`、`max_replace_ratio` 和权重，以平衡"exploitation / exploration"。
  - 在长时间运行时更有利于避免早熟收敛。

- **并行批量运行（CPU 多核友好）**：
  - `nsgablack.parallel_runs` 提供 `run_headless_in_parallel` 与 `run_vns_in_parallel`，基于 `concurrent.futures` 实现：
    - 默认采用多进程（`ProcessPoolExecutor`），充分利用多核 CPU；
    - 支持多线程后端（`backend="thread"`）以适应 I/O 密集或外部仿真场景。
  - 适合真实工程中"多起几把取最好的一把"的需求，显著提升找到高质量解的概率；
  - 内置对 `tqdm` 的可选支持，在安装后可自动显示总任务进度条。

- **元优化：自动调节 GA/NSGA-II 超参数**：
  - 通过 `nsgablack.metaopt` 提供 `bayesian_meta_optimize`、`SolverHyperParams` 等工具：
    - 支持多种损失汇总策略（`single` / `weighted_sum` / `hypervolume` / `eps_constraint`）；
    - 支持多后端（`skopt`、`optuna` TPE/CMA），可针对不同问题特性选择合适的元优化算法。
  - 可自动搜索 `pop_size`, `max_generations`, `mutation_rate`, `crossover_rate` 等超参数，减少手工试错。

- **可选 Numba 加速的核心算子**：
  - 在 `nsgablack.numba_helpers` 中提供 `@njit` 加速的 `fast_is_dominated`，并在 `BlackBoxSolverNSGAII.is_dominated_vectorized` 中自动接入：
    - 若安装了 `numba`，中大种群、多目标场景下非支配排序开销显著减少；
    - 未安装或运行失败会自动回退到 numpy 实现，无需用户干预。
  - 对于长时间、多代数优化任务，可以显著降低总运行时间。

- **ML-guided 与特征选择/降维工作流**：
  - 通过 `ModelManager` + `ml_guided_ga_example`，支持训练/保存/续训分类器，用于在初始化阶段过滤"明显劣质解"，实现 ML-guided GA；
  - `exmaple.py` 提供 `UniversalFeatureSelector` 及一系列 PCA/KPCA/PLS/ActiveSubspace/Autoencoder 降维工具：
    - 支持从高维特征空间中自动筛选重要特征或构造低维表示；
    - 提供"构造降维问题 → 在降维空间优化 → 映射回原空间"的完整示例流程。
  - 适合高维工程问题、数据驱动建模等场景。

- **Bias 模块：智能搜索引导**：
  - `BiasModule` 提供可扩展的优化偏向系统，通过**奖函数（Reward）**和**罚函数（Penalty）**引导遗传算法的搜索方向；
  - 核心思想：
    - 罚函数（权重 1.0-10.0）：惩罚不良解，避免往更差的方向优化；
    - 奖函数（权重 0.01-0.1）：奖励优质解，引导快速收敛到好的方向；
    - 历史跟踪：记录最优解并基于历史信息智能引导。
  - 已集成到 `BlackBoxSolverNSGAII`、`SurrogateAssistedNSGAII`、`BlackBoxSolverVNS` 三大求解器；
  - 内置 6 种奖励函数和 3 种罚函数，支持自定义扩展；
  - 提供 `create_standard_bias` 便捷构造函数，一行代码启用标准配置；
  - 适合约束优化、多目标优化、需要快速收敛的场景。

- **工程友好的日志与收敛评估**：
  - `convergence.log_and_maybe_evaluate_convergence` 提供统一的最优解日志记录与 SVM/聚类式收敛评估；
  - 支持阈值触发（例如历史解数达到 `threshold` 时自动评估），并将结果保存到 CSV 文件，便于后续分析或可视化；
  - 与 `run_headless_single_objective` 的 `evaluate_convergence` 参数无缝集成，一行代码即可在批量实验中积累"收敛历史"。

- **完善的测试与示例**：
  - `tests/` 目录包含对 headless、VNS、ML 模型管理、并行批量运行等模块的单元测试，方便在修改后进行快速回归；
  - 多个示例脚本（工程设计、投资组合、NN 超参数、降维示例、`surrogate_example.py`、`demo_parallel_sphere.py` 等）覆盖从玩具问题到工程级问题的典型用法，适合作为你自己项目的模板。

---

## 2. 快速上手

### 2.1 安装与依赖

#### 核心依赖

```bash
pip install -r requirements.txt
```

**必需依赖**：
- `numpy` - 数值计算
- `scipy` - 科学计算
- `matplotlib` - 可视化
- `scikit-learn` - 机器学习工具

**可选依赖**：
- `numba` - JIT 加速（推荐，可显著提升大规模优化性能）
- `optuna` - 元优化 TPE/CMA 后端
- `tqdm` - 进度条显示
- `joblib` - 模型持久化

#### 快速安装

```bash
# 基础安装
pip install numpy scipy matplotlib scikit-learn

# 完整安装（包含所有可选功能）
pip install numpy scipy matplotlib scikit-learn numba optuna tqdm joblib
```

### 2.2 最简单的单目标 headless 示例

```python
import numpy as np
from nsgablack.headless import run_headless_single_objective

def sphere(x):
    """Sphere 函数：最小值在原点，f(0,0,0) = 0"""
    x = np.asarray(x, dtype=float)
    return np.sum(x ** 2)

# 定义变量边界
bounds = [(-5, 5)] * 3  # 3维问题，每维范围 [-5, 5]

# 运行优化
res = run_headless_single_objective(
    objective=sphere,
    bounds=bounds,
    pop_size=40,
    max_generations=50,
)

print("最优解:", res["x"])
print("最优值:", res["fun"])
# 输出示例：
# 最优解: [-0.0012  0.0034 -0.0021]
# 最优值: 1.89e-05
```

### 2.3 使用内置问题 + NSGA-II 可视化

```python
from nsgablack.problems import ZDT1BlackBox
from nsgablack.solver import BlackBoxSolverNSGAII

# 创建多目标测试问题（ZDT1）
problem = ZDT1BlackBox(dimension=10)

# 创建求解器
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 80
solver.max_generations = 100

# 方式1：交互式可视化（需要图形界面）
solver.initialize_population()
solver.update_pareto_solutions()
solver.start_animation()  # 打开 GUI 窗口，可通过按钮控制运行

# 方式2：无界面运行
solver.initialize_population()
for _ in range(solver.max_generations):
    solver.animate(frame=None)

print(f"找到 {len(solver.pareto_solutions['individuals'])} 个 Pareto 最优解")
```

### 2.4 使用 VNS（Variable Neighborhood Search）快速搜索

`nsgablack/vns.py` 中提供了简洁可配置的 `BlackBoxSolverVNS`，适合：

- 单目标问题的快速局部+多邻域搜索；
- 多目标问题在需要时做标量化近似（内部做等权重线性组合）。

以 Sphere 函数为例：

```python
from nsgablack.problems import SphereBlackBox
from nsgablack.vns import BlackBoxSolverVNS

problem = SphereBlackBox(dimension=2)
solver = BlackBoxSolverVNS(problem)

# 关键参数
solver.max_iterations = 200     # 外层迭代次数上限
solver.k_max = 5                # 邻域层数
solver.neighborhood_type = "gaussian"  # "gaussian" | "coordinate" | "uniform"
solver.scale_schedule = "linear"       # "linear" | "geometric"
solver.shake_scale = 0.2        # 高斯扰动基础尺度
solver.base_step = 0.1          # 对坐标/均匀邻域的基础步长（按区间放大）
solver.local_search_iters = 30  # 每次局部搜索迭代步数

result = solver.run()
print("best f:", result["best_f"])
print("evaluations:", result["evaluations"])
```

你也可以直接调用示例函数：

```python
from nsgablack.examples import optimize_with_vns

solver, result = optimize_with_vns()
```

### 2.5 代理模型辅助优化（昂贵函数）

对于计算成本高昂的问题（如每次评估需数秒或数分钟），可以使用 `SurrogateAssistedNSGAII` 或便捷函数 `run_surrogate_assisted`。

#### 基础使用

```python
from nsgablack.surrogate import run_surrogate_assisted
from nsgablack.problems import SphereBlackBox
import time

# 模拟昂贵问题
class ExpensiveSphere(SphereBlackBox):
    def evaluate(self, x):
        time.sleep(0.05)  # 模拟耗时
        return super().evaluate(x)

problem = ExpensiveSphere(dimension=5)

# 运行代理模型辅助优化
result = run_surrogate_assisted(
    problem,
    surrogate_type='gp',       # 'gp', 'rbf', 'rf', 'ensemble'
    real_eval_budget=200,      # 真实评估预算
    initial_samples=30,        # 初始样本数
    max_generations=50
)

print(f"最优解: {result['pareto_objectives'][0]}")
print(f"真实评估次数: {result['real_eval_count']}")
```

#### 模型保存/加载

避免重复训练，保存训练好的代理模型：

```python
from nsgablack.surrogate import SurrogateAssistedNSGAII

solver = SurrogateAssistedNSGAII(problem, surrogate_type='gp')
solver.real_eval_budget = 200
solver.run()

# 保存模型
solver.save_surrogate('models/my_surrogate.pkl')

# 下次运行时加载
solver2 = SurrogateAssistedNSGAII(problem, surrogate_type='gp')
solver2.load_surrogate('models/my_surrogate.pkl')
# 继续优化或直接使用
```

#### 质量监控

自动监控模型质量，当R²低于阈值时触发重训练：

```python
solver = SurrogateAssistedNSGAII(problem, surrogate_type='rf')
solver.enable_quality_check = True
solver.quality_threshold = 0.6  # R²阈值
solver.run()

# 查看质量历史
for metric in solver.model_metrics:
    print(f"代 {metric['generation']}: R²={metric['r2']:.3f}, RMSE={metric['rmse']:.3f}")
```

#### 在线学习

使用增量学习减少训练时间：

```python
solver = SurrogateAssistedNSGAII(problem, surrogate_type='rf')
# 在 _train_surrogate 中自动使用增量学习
# 只训练新增的数据点
solver.run()
```

#### 多模型集成

组合 GP、RF、RBF 三种模型，提高预测鲁棒性：

```python
result = run_surrogate_assisted(
    problem,
    surrogate_type='ensemble',  # 使用集成模型
    real_eval_budget=200,
    initial_samples=30
)

# 集成模型会自动根据验证集性能调整各模型权重
print(f"最优解: {result['pareto_objectives'][0]}")
```

---

## 3. 核心类与约束处理

本节介绍核心抽象 `BlackBoxProblem`、`BlackBoxSolverNSGAII` 以及约束处理约定。

### 3.1 BlackBoxProblem：问题抽象

`BlackBoxProblem` 是所有优化问题的基类，提供统一接口：

**核心方法**：
- `evaluate(x)` - 计算目标函数值（必须实现）
- `evaluate_constraints(x)` - 计算约束违背度（可选）
- `get_num_objectives()` - 返回目标数量

**约束处理规则**：
- 约束函数返回 `g(x)`，满足 `g(x) ≤ 0` 为可行
- 自动采用 Deb 约束支配规则：可行解优先，不可行解按违背度排序

### 3.2 BlackBoxProblem (`nsgablack/base.py`)

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `name` | str | `"黑箱问题"` | 问题名称，用于日志/可视化标题 |
| `dimension` | int | `2` | 设计变量维度 |
| `bounds` | dict\|None | `None` | 变量边界字典 `{ 'x0':[min,max], ...}`；None 时默认每维 [-5,5] |

方法：

- `evaluate(x)`：必须实现，建议支持单点 `(d,)` 与批量 `(n,d)` 输入。
- `evaluate_constraints(x)`：可选实现，返回约束违背度数组 `g(x)`；约定 `g(x) <= 0` 为满足约束，`g(x) > 0` 为违反程度，内部会自动对正值求和生成标量违背度并用于 Deb 约束支配规则（可行解优先，其次违背更小者更优）。
- `get_num_objectives()`：返回目标数（默认 1）。

**一个带约束的简单示例：**

```python
import numpy as np
from nsgablack.base import BlackBoxProblem


class MyConstrainedProblem(BlackBoxProblem):
  """示例：最小化 x0^2 + x1^2，带两个约束：

  1) x0 + x1 <= 1
  2) x0 >= 0.2
  """

  def __init__(self):
    super().__init__("带约束示例", dimension=2)
    self.bounds = {"x0": [0.0, 1.0], "x1": [0.0, 1.0]}

  def evaluate(self, x):
    x = np.asarray(x, dtype=float)
    return np.sum(x**2)

  def evaluate_constraints(self, x):
    x = np.asarray(x, dtype=float)
    g1 = x[0] + x[1] - 1.0   # <= 0 为可行
    g2 = 0.2 - x[0]          # <= 0 为可行 (x0 >= 0.2)
    return np.array([g1, g2], dtype=float)
```

### 3.3 BlackBoxSolverNSGAII (`nsgablack/solver.py`)

| 参数/属性 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `problem` | BlackBoxProblem | 必需 | 问题实例 |
| `pop_size` | int | `80` | 种群大小（建议偶数） |
| `max_generations` | int | `150` | 最大代数 |
| `crossover_rate` | float | `0.85` | 交叉概率 |
| `mutation_rate` | float | `0.15` | 变异概率 |
| `initial_mutation_range` | float | `0.8` | 初始变异幅度 |
| `enable_diversity_init` | bool | `False` | 是否启用多样性初始化 |
| `use_history` | bool | `False` | 是否加载历史解用于初始化 |
| `enable_elite_retention` | bool | `True` | 是否启用精英保留模块 |
| `diversity_params` | dict | 见下文 | 包含 `candidate_size`, `similarity_threshold`, `rejection_prob`, `sampling_method` |

常用方法/返回字段：

- `initialize_population()`、`evaluate_population(pop)`、`selection()`、`crossover(parents)`、`mutate(offspring)`、`non_dominated_sorting()`。
- 运行结果存放在 `population`, `objectives`, `pareto_solutions`, `history` 等属性中。

**在 NSGA-II 中使用带约束问题：**

```python
from nsgablack.solver import BlackBoxSolverNSGAII
from my_module import MyConstrainedProblem  # 参考上面的约束示例

problem = MyConstrainedProblem()
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 60
solver.max_generations = 120

solver.initialize_population()
for _ in range(solver.max_generations):
  solver.animate(frame=None)  # 在无 GUI 环境中循环调用 animate

print("当前代:", solver.generation)
print("Pareto 解个数:", 0 if solver.pareto_solutions is None else len(solver.pareto_solutions["individuals"]))
```

### 3.4 DiversityAwareInitializerBlackBox (`nsgablack/diversity.py`)

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `problem` | BlackBoxProblem | 必需 | 问题实例 |
| `history_size` | int | `1000` | 历史解缓存大小 |
| `similarity_threshold` | float | `0.1` | 归一化欧氏距离阈值，用于判断相似性 |
| `rejection_prob` | float | `0.7` | 若相似则按此概率拒绝候选 |

主要方法：`initialize_diverse_population(pop_size=100, candidate_size=1000, sampling_method='lhs')`、`add_to_history(solution, fitness)`、`load_history(path)`、`save_history(path)`。

### 3.5 AdvancedEliteRetention (`nsgablack/elite.py`)

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `max_generations` | int | 必需 | 最大代数，用于进度相关计算 |
| `population_size` | int | 必需 | 种群大小 |
| `initial_retention_prob` | float | `0.9` | 基础保留概率 |
| `min_replace_ratio` | float | `0.05` | 最小替换比 |
| `max_replace_ratio` | float | `0.6` | 最大替换比 |
| `replacement_weights` | dict\|None | `None` | 自定义权重，控制替换比例的组成项 |

主要方法：`calculate_elite_retention_probability(...)`、`get_elite_replacement_ratio(retention_prob=None)`、`set_replacement_config(...)`。

### 3.6 `run_headless_single_objective` (`nsgablack/headless.py`)

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `objective` | callable | 必需 | 接受 `(d,)` 返回标量（应可被向量化） |
| `bounds` | list[tuple] | 必需 | 每个变量的 `(min,max)` |
| `pop_size` | int | `80` | 种群大小 |
| `max_generations` | int | `150` | 最大代数 |
| `mutation_rate` | float | `0.15` | 变异率 |
| `crossover_rate` | float | `0.85` | 交叉率 |
| `enable_diversity_init` | bool | `False` | 是否启用多样性初始化 |
| `enable_elite_retention` | bool | `True` | 是否启用精英保留 |
| `plot` | bool | `False` | 是否启用绘图（交互式） |
| `maximize` | bool | `False` | 是否做最大化（内部会取负再最小化） |
| `use_history` | bool | `False` | 是否加载历史解 |
| `history_file` | str\|None | `None` | 历史数据文件路径 |
| `evaluate_convergence` | bool | `False` | 是否在结束后评估收敛性 |
| `evaluation_method` | str | `'svm'` | `'svm'` / `'cluster'` / `'both'` |
| `evaluation_threshold` | int | `30` | 触发自动评估所需的最小历史解数 |

返回值：`{'x': best_x, 'fun': best_f, 'solver': solver_instance, 'evaluation': eval_info_or_None}`。

### 3.7 收敛评估 (`nsgablack/convergence.py`)

| 函数 | 说明 |
| --- | --- |
| `log_and_maybe_evaluate_convergence(best_x, best_f, bounds, log_file=None, threshold=30, method='svm')` | 将最优解追加到收敛日志并在达到阈值时执行 SVM/聚类等评估，返回评估结果字典 |

### 3.8 UniversalFeatureSelector & 降维器（概览）

UniversalFeatureSelector（见 `exmaple.py`）提供：

- `collect_data(objective,bounds,initial_samples=100,method='lhs')`
- `analyze_features(X,y,methods=None)` — `mutual_info` / `random_forest` / `correlation` / `variance`
- `smart_feature_selection(X,y,reduction_method='cumulative',threshold=0.95,min_features=1,max_features=None)`
- `prepare_reduced_problem(...)` / `optimize_with_feature_selection(...)` — 返回 `reduced_objective`, `reduced_bounds`, `expand_to_full` 等。

降维器（PCA/KPCA/PLS/ActiveSubspace/Autoencoder）构造函数通常参数：`objective_func, bounds, n_components, initial_samples, sampling_method` 以及具体超参，返回字典 `{ 'reduced_objective', 'reduced_bounds', 'expand_to_full', '..._model', 'samples_info' }`。

---

**示例：在降维空间运行优化并映射回原空间**

（`exmaple.py` 中流程）

1. 使用 `UniversalFeatureSelector` 或 `prepare_pca_reduced_problem` 等构造降维问题（返回 `reduced_objective`，`reduced_bounds`，`expand_to_full`）
2. 使用 `run_headless_single_objective` 或任意优化器在 `reduced_bounds` 上运行 `reduced_objective`
3. 使用 `expand_to_full` 将最优解映射回原始空间

示例伪代码：

```python
# 1) 构造降维问题
from nsgablack.exmaple import prepare_pca_reduced_problem
reduced = prepare_pca_reduced_problem(original_func, bounds, n_components=3)

# 2) 在降维空间运行无界面优化
res = run_headless_single_objective(reduced['reduced_objective'], reduced['reduced_bounds'], max_generations=200)

# 3) 映射回原空间
full_x = reduced['expand_to_full'](res['x'])
```

**开发者提示与建议**

- 若在无头环境（如服务器）运行，请关闭绘图（`plot_enabled=False` 或不使用 `SolverVisualizationMixin`）。
- 历史数据文件（由 `DiversityAwareInitializerBlackBox` 管理）可以跨实验复用以提高初始化多样性。
- 为关键算子（选择/交叉/变异/非支配排序）补充单元测试会显著提高可维护性。

**API 参数表（详尽）**

- `BlackBoxProblem` (`nsgablack/base.py`)

  - 构造: `BlackBoxProblem(name="黑箱问题", dimension=2, bounds=None)`
  - 方法:
    - `evaluate(self, x)` — 必须由子类实现，支持向量化（接收形状为 (n, d) 的 X 返回 (n, m) 或接收单点返回长度 m 的目标或标量）。
    - `get_num_objectives(self)` — 默认返回 `1`，多目标问题应返回目标数。
- `BlackBoxSolverNSGAII` (`nsgablack/solver.py`)

  - 构造: `BlackBoxSolverNSGAII(problem: BlackBoxProblem)`
  - 重要属性（可读写）:
    - `problem` : `BlackBoxProblem` 实例
    - `variables` : 变量名列表
    - `num_objectives` : 目标数 (int)
    - `dimension` : 变量维度 (int)
    - `var_bounds` : 字典 `{var: [min, max]}`
    - `pop_size` : 种群大小 (default: 80)
    - `max_generations` : 最大代数 (default: 150)
    - `crossover_rate` : 交叉概率 (default: 0.85)
    - `mutation_rate` : 变异概率 (default: 0.15)
    - `initial_mutation_range` : 初始变异幅度 (default: 0.8)
    - `enable_diversity_init` : 是否使用多样性初始化 (bool)
    - `use_history` : 是否加载历史解 (bool)
    - `enable_elite_retention` : 是否启用精英保留 (bool)
    - `diversity_params` : dict, 包含 `candidate_size`, `similarity_threshold`, `rejection_prob`, `sampling_method`
    - `elite_manager` : `AdvancedEliteRetention` 实例
    - `pareto_solutions`, `population`, `objectives`, `history` 等运行时结果
  - 关键方法:
    - `initialize_population()` — 随机或基于 `DiversityAwareInitializerBlackBox` 初始化种群
    - `evaluate_population(population)` — 返回目标数组
    - `non_dominated_sorting()` — 返回 rank、crowding_distance、fronts
    - `selection()`, `crossover(parents)`, `mutate(offspring)` — 遗传算子
    - `run_algorithm(event)` / `stop_algorithm(event)` — GUI 控件调用
    - `animate(frame)` — 每代迭代逻辑（可在无界面循环中反复调用）
- `SolverVisualizationMixin` (`nsgablack/visualization.py`)

  - 通过 `_init_visualization()` 创建 Matplotlib UI
  - 交互控件: `btn_run`, `btn_stop`, `btn_reset`, `pop_box`, `gen_box`, `mutation_slider`, `elite_slider` 等
  - 可调用方法: `toggle_plot`, `toggle_diversity_init`, `toggle_history`, `update_plot_dynamic`, `start_animation`, `stop_animation`
- `DiversityAwareInitializerBlackBox` (`nsgablack/diversity.py`)

  - 构造: `DiversityAwareInitializerBlackBox(problem, history_size=1000, similarity_threshold=0.1, rejection_prob=0.7)`
  - 主要方法:
    - `initialize_diverse_population(pop_size=100, candidate_size=1000, sampling_method='lhs')` — 从候选集中选择高质量且足够多样的个体
    - `add_to_history(solution, fitness)`, `save_history(file_path=None)`, `load_history(file_path=None)`, `clear_history()`
    - `is_similar_to_history(candidate)` — 判断给定解是否与历史近似
- `AdvancedEliteRetention` (`nsgablack/elite.py`)

  - 构造: `AdvancedEliteRetention(max_generations, population_size, initial_retention_prob=0.9, min_replace_ratio=0.05, max_replace_ratio=0.6, replacement_weights=None)`
  - 主要方法:
    - `calculate_elite_retention_probability(current_generation, current_best_fitness, population_fitnesses, population)` — 返回 [0.05,0.95] 范围内的保留概率
    - `get_elite_replacement_ratio(retention_prob=None)` — 根据上次计算的因子与权重返回替换比例
    - `set_replacement_config(min_ratio, max_ratio, weights)` — 更新最小/最大替换比与权重
- `run_headless_single_objective` (`nsgablack/headless.py`)

  - 常用签名与默认值（部分关键参数）:
    - `run_headless_single_objective(objective, bounds, *, pop_size=80, max_generations=150, mutation_rate=0.15, crossover_rate=0.85, enable_diversity_init=False, enable_elite_retention=True, plot=False, maximize=False, use_history=False, history_file=None, seed_history_rate=0.3, name="降维后单目标黑箱", convergence_log_file=None, evaluate_convergence=False, evaluation_method='svm', evaluation_threshold=30, min_replace_ratio=None, max_replace_ratio=None, replacement_weights=None)`
  - 返回值: 字典 `{'x': best_x, 'fun': best_f, 'solver': solver, 'evaluation': eval_info}`
    - `best_x`: 最优参数向量
    - `best_f`: 最优目标值（若 `maximize=True` 则已做符号调整）
    - `solver`: 运行结束时的 `BlackBoxSolverNSGAII` 实例（含历史、pareto 等）
    - `evaluation`: 若 `evaluate_convergence=True`，包含 `log_and_maybe_evaluate_convergence` 的结果（详见下）或 `None`
- `BlackBoxSolverVNS` (`nsgablack/vns.py`)

  - 构造: `BlackBoxSolverVNS(problem: BlackBoxProblem)`
  - 重要属性（可读写）:
    - `problem`: `BlackBoxProblem` 实例
    - `dimension`, `variables`, `bounds`: 直接来自 `problem`
    - `max_iterations`: 外层迭代上限（默认 200）
    - `k_max`: 最大邻域层数（默认 5）
    - `neighborhood_type`: 邻域类型字符串：
      - `"gaussian"`：各维高斯扰动（默认）
      - `"coordinate"`：随机选若干坐标做有界步长扰动
      - `"uniform"`：在以当前解为中心的超立方体内做均匀扰动
    - `scale_schedule`: 扰动尺度随邻域层数的变化策略：
      - `"linear"`：线性放大，`scale = shake_scale * (1 + 0.8*(k-1))`
      - `"geometric"`：几何放大，`scale = shake_scale * 1.3**(k-1)`
    - `shake_scale`: 高斯扰动的基础标准差（默认 0.2）
    - `base_step`: 对坐标/均匀邻域的基础步长，相对于每维区间长度缩放（默认 0.1）
    - `local_search_iters`: 每次局部搜索迭代次数（默认 30）
    - `evaluation_count`: 已调用 `problem.evaluate` 的次数
    - `best_x`, `best_f`: 搜索过程中记录到的当前全局最好解与其标量目标值
    - `history`: 列表 `(iter_index, current_f)`，可用于简单收敛曲线绘制
  - 关键方法:
    - `run()` — 按“shake + 局部搜索 + 多邻域切换”策略执行 VNS，返回字典：

      ```python
      {
        'best_x': np.ndarray,      # 维度为 problem.dimension
        'best_f': float,           # 标量化后的最优目标值
        'evaluations': int,        # 评估次数
        'history': list[(int,float)]
      }
      ```
- `SurrogateAssistedNSGAII` (`nsgablack/surrogate.py`)

  - 构造: `SurrogateAssistedNSGAII(problem, surrogate_type='gp')`
  - 参数:
    - `surrogate_type`: `'gp'` (高斯过程), `'rbf'` (径向基), `'rf'` (随机森林), `'ensemble'` (集成模型)。
  - 重要属性:
    - `real_eval_budget` (int): 真实评估次数预算 (默认 200)。
    - `initial_samples` (int): 初始真实评估样本数 (默认 50)。
    - `update_interval` (int): 代理模型更新频率 (默认 10 代)。
    - `real_evals_per_gen` (int): 每代选择进行真实评估的个体数 (默认 5)。
    - `enable_quality_check` (bool): 是否启用质量监控 (默认 True)。
    - `quality_threshold` (float): R² 阈值，低于此值触发重训练 (默认 0.5)。
    - `model_metrics` (list): 记录每次训练的质量指标 (R²、RMSE、代数、样本数)。
  - 新增方法:
    - `save_surrogate(path)`: 保存代理模型到文件 (.pkl 或 .joblib)。
    - `load_surrogate(path)`: 从文件加载代理模型。
    - `_compute_model_quality(X, y)`: 计算模型质量指标 (R²、RMSE)。
    - `_check_model_quality()`: 检查模型质量，返回是否需要重训练。
  - 便捷函数: `run_surrogate_assisted(problem, surrogate_type='gp', real_eval_budget=200, ...)`。
- 收敛与评估 (`nsgablack/convergence.py`)

  - `log_and_maybe_evaluate_convergence(best_x, best_f, bounds, log_file=None, threshold=30, method='svm')`
    - 作用: 将最优解追加到收敛日志文件并在样本数量满足 `threshold` 时执行评估
    - 返回: 包括 `{'evaluated': bool, 'file': path, ...}`，当 `method=='svm'` 返回 `{'ready', 'method', 'auc', 'compact', 'ok', 'n_pos', 'n_neg'}`；`'cluster'` 返回簇分析结果；`'both'` 返回两者

**示例输出（示例）**

下面示例输出为基于代码逻辑构造的典型打印/返回样本（用于 README 展示），并非实际运行日志，但反映模块输出结构和字段含义。

- 交互式运行（`BlackBoxSolverNSGAII`）在控制台的进度打印示例：

```
[进度] 第0代 | 最优适应度: 12.345678 | 最优解: [ 0.123456, -1.234567, 2.345678, ...]
[进度] 第100代 | 最优适应度: 0.987654 | 最优解: [ 0.012345, -0.123456, 1.234567, ...]
运行完成: 共计评估次数: 9600
Pareto最优解数量: 37
```

- 无界面（headless）执行例子返回结构示例：

```python
{
  'x': array([ 0.0234, -1.2345, 2.3456, ...]),
  'fun': 0.987654321,
  'solver': <nsgablack.solver.BlackBoxSolverNSGAII object at 0x...>,
  'evaluation': {
      'evaluated': False,          # 未达到评估阈值时
      'count': 12,
      'threshold': 30,
      'file': '.../history/all_converged_solutions.csv'
  }
}
```

- 当 `evaluate_convergence=True` 且使用 SVM 评估时，可能得到的 `evaluation` 示例：

```python
{
  'evaluated': True,
  'file': '.../history/all_converged_solutions.csv',
  'method': 'svm',
  'auc': 0.91234,
  'compact': 0.2345,
  'ok': True,
  'n_pos': 120,
  'n_neg': 14400
}
```

- 在 `exmaple.py` 的智能降维示例中，控制台可能打印的摘要（示例）:

```
方法1: 累计重要性阈值方法
正在评估 40 个初始样本...
进行互信息分析...
进行随机森林分析...
进行相关性分析...
进行方差分析...
累计重要性方法: 达到90.0%重要性需要 3 个特征
智能降维结果:
  原始维度: 8
  降维后维度: 3
  降维比例: 62.5%
  选定特征索引: [1, 3, 6]

阶段3: 在降维空间优化
使用默认进化策略优化器
迭代 0, 最优值: 5.123456
迭代 10, 最优值: 0.987654
...
阶段4: 结果映射
优化完成!
原始最优解: [ 0.5, -0.12, 0.67, 0.5, 0.5, 0.5, 1.23, 0.5]
原始最优值: 0.987654
```

以上示例展示了典型字段与日志语句，README 中保留这些示例便于用户理解返回格式、日志与如何解析运行结果。

---

## 真实运行示例（headless 快速验证）

下面为在当前工作环境中运行的真实短示例（3 维 Sphere 函数，种群 20、代数 10），运行脚本为 `tmp_headless_test.py`，其输出为终端截取：

```
Starting headless sphere test (pop=20, gens=10)...
=== RESULT ===
x = [-0.05124025 -0.62003353  0.26481033]
fun = 0.45719165095707265
Done.
```

说明：

- `x` 为找到的最优解向量（原空间）。
- `fun` 为目标函数值（Sphere 函数，越小越好）。

该快速测试脚本路径：

```
c:\Users\hp\Desktop\新建文件夹 (7)\tmp_headless_test.py
```

你可以复制该脚本并修改 `pop_size`, `max_generations` 等参数，作为快速回归/环境验证用例。

**模型持久化示例**

在使用 ML-guided 示例（`nsgablack.ml_guided_ga_example`）运行训练/续训时，分类器模型会被保存在工作目录下的 `ml_models/` 子目录中。
每个模型文件采用 `joblib` 存储，内容为字典：`{'clf', 'scaler', 'X_hist', 'y_hist', 'meta'}`，`meta` 字段包含 `created_at`、`updated_at`、`training_runs`、`model_tag`、`bad_frac` 等。

示例（你机器上的路径会有所不同）：

```
C:\Users\hp\Desktop\新建文件夹 (7)\ml_models\Sphere函数_(d=8)_d8.joblib
```

要获取模型信息（路径/样本数/元数据），可以使用 `ModelManager.get_model_info(problem_name, dimension, model_tag)`。

---

**模型持久化与持续训练（ModelManager）**

本项目提供了 `ModelManager`（见 `nsgablack/ml_models.py`）用于管理分类器模型的训练、保存与继续训练。下面是快速参考与使用示例。

- 目的：把每次采样训练得到的机器学习模型持久化到磁盘，以便后续运行可以加载并在已有历史样本上继续训练，从而实现“持续训练/增量更新”策略。
- 默认存储目录：在当前工作目录下创建 `ml_models/` 子目录（可通过 `ModelManager(model_dir=...)` 指定其它目录）。
- 存储格式：每个 model 文件为 `joblib`，内容为字典：`{'clf', 'scaler', 'X_hist', 'y_hist', 'meta'}`。
- `meta` 字段包含：`created_at`, `updated_at`, `training_runs`, `model_tag`, `bad_frac`, `version` 等，便于审计与复现。

示例代码：训练/续训并读取模型

```python
from nsgablack import ModelManager

# 准备数据（X: ndarray (n,d), y_scores: ndarray (n,) 为用于标注好/坏的标量评分）
mm = ModelManager(model_dir='./ml_models', max_history=5000)
problem_name = 'MyProblem'
dimension = 8

# train_or_update：如果已有模型则合并历史样本并重训练，否则新训练并保存
clf_wrapper, scaler, model_path = mm.train_or_update(problem_name, dimension, X, y_scores,
                           bad_frac=0.25, model_tag='exp1')
print('模型已保存到：', model_path)

# 只加载已存在的 wrapper（不做重新训练）
existing = mm.get_wrapper_if_exists(problem_name, dimension, model_tag='exp1')
if existing is not None:
  probs = existing.predict_proba(X[:5])

# 获取人类可读的模型信息
info = mm.get_model_info(problem_name, dimension, model_tag='exp1')
print(info)
```

**如何在你的代码中导入新模块与类**

- `ModelManager` 已导出到包顶层（见 `nsgablack/__init__.py`），你可以直接：

```python
from nsgablack import ModelManager
```

- 初始化器与示例代码位于 `nsgablack.ml_guided_ga_example`，可按需直接导入：

```python
from nsgablack.ml_guided_ga_example import (
  ClassifierHistoryAwareInitializer,
  ClassifierHistoryAwareReducedInitializer,
)

# 用法示例
# init = ClassifierHistoryAwareInitializer(problem, clf=clf_wrapper, bad_prob_thresh=0.6)
# reduced_init = ClassifierHistoryAwareReducedInitializer(reduced_problem, base_initializer=init, expand_fn=expand_to_full)
```

说明：`ClassifierHistoryAwareInitializer` 在原空间进行 classifier + history 判定；
`ClassifierHistoryAwareReducedInitializer` 是一个适配器，用于在降维空间采样但在原空间执行判定（通过 `expand_fn` 映射）。

实践建议：

- `model_tag`：建议为每个不同实验或重要超参配置指定唯一 `model_tag`（例如包含日期/超参或哈希），避免不同策略的模型被覆盖或混淆。
- `bad_frac`：默认会把 `bad_frac` 加入 model id（若不显式传入 `model_tag`），你也可以通过 `include_bad_frac_in_id=False` 在 `train_or_update` 中关闭此行为。
- `max_history`：控制历史样本合并时保留的上限（`ModelManager(..., max_history=5000)`），避免模型文件膨胀。

测试与 CI：

- 已添加单元测试 `tests/test_ml_models.py` 用于验证 `ModelManager.train_or_update` 的新建与续训行为；你可以通过 `pytest -q` 运行全部测试。

以上示例展示了如何把机器学习模型作为“先验/过滤器”长期保存并在后续实验中继续利用，从而让 ML-guided GA 在多次实验中积累知识，减少劣质解的评估浪费。

---

## 4. Bias 模块：智能搜索引导

### 4.1 概述

Bias 模块是一个可扩展的优化偏向系统，通过**奖函数（Reward）**和**罚函数（Penalty）**来引导遗传算法的搜索方向。

**核心思想**：

| 类型 | 权重范围 | 作用 |
|------|---------|------|
| **罚函数** | 1.0 - 10.0 | 惩罚不良解，避免往更差的方向优化 |
| **奖函数** | 0.01 - 0.1 | 奖励优质解，引导快速收敛到好的方向 |
| **历史跟踪** | - | 记录最优解并基于历史信息智能引导 |

**设计原则**：
- ✓ 奖函数权重远小于罚函数权重，避免过度引导导致早熟收敛
- ✓ 配合 VNS 等方法可以跳出局部最优
- ✓ 支持单目标和多目标优化
- ✓ 已集成到三大求解器：NSGA-II、Surrogate、VNS

### 4.2 快速开始

#### 基础使用（标准配置）

```python
from nsgablack.base import BlackBoxProblem
from nsgablack.solver import BlackBoxSolverNSGAII
from nsgablack.bias import create_standard_bias
import numpy as np

# 定义问题
class MyProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="MyProblem", dimension=2,
                        bounds={'x0': (-5, 5), 'x1': (-5, 5)})

    def evaluate(self, x):
        return np.sum(x**2)

problem = MyProblem()

# 创建求解器
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 40
solver.max_generations = 50

# 启用 bias 模块（使用标准配置）
solver.enable_bias = True
solver.bias_module = create_standard_bias(problem,
                                         reward_weight=0.05,
                                         penalty_weight=1.0)

# 运行优化
result = solver.run()
```

#### 自定义奖励函数

```python
from nsgablack.bias import BiasModule

# 创建 bias 模块
bias = BiasModule()

# 添加自定义奖励：奖励接近目标点的解
def proximity_reward(x):
    target = np.array([1.0, 1.0])
    distance = np.linalg.norm(x - target)
    return np.exp(-distance)  # 距离越近奖励越大

bias.add_reward(proximity_reward, weight=0.1, name="proximity")

# 应用到求解器
solver.enable_bias = True
solver.bias_module = bias
```

#### 约束优化

```python
# 定义带约束的问题
class ConstrainedProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="Constrained", dimension=2,
                        bounds={'x0': (-2, 2), 'x1': (-2, 2)})

    def evaluate(self, x):
        return x[0]**2 + x[1]**2

    def evaluate_constraints(self, x):
        # g(x) <= 0 为可行
        return np.array([1 - x[0] - x[1]])  # x + y >= 1

problem = ConstrainedProblem()

# 使用标准 bias（自动包含约束罚函数）
solver = BlackBoxSolverNSGAII(problem)
solver.enable_bias = True
solver.bias_module = create_standard_bias(problem,
                                         reward_weight=0.05,
                                         penalty_weight=5.0)  # 更高的罚函数权重
```

### 4.3 内置函数库

#### 奖励函数（6种）

| 函数名 | 功能 | 主要参数 | 适用场景 |
|--------|------|---------|---------|
| `proximity_reward` | 接近历史最优解奖励 | `best_x`, `scale`, `normalize` | 引导向已知好解靠近 |
| `improvement_reward` | 目标改进速度奖励 | `f_current`, `f_previous`, `scale` | 奖励快速改进 |
| `feasibility_depth_reward` | 深度可行性奖励 | `constraint_values`, `scale` | 约束优化，奖励远离边界 |
| `diversity_reward` | 多样性贡献奖励 | `x`, `population`, `scale`, `k` | 保持种群多样性 |
| `gradient_alignment_reward` | 梯度对齐奖励 | `x`, `gradient`, `direction`, `scale` | 利用梯度信息 |

#### 罚函数（3种）

| 函数名 | 功能 | 主要参数 | 适用场景 |
|--------|------|---------|---------|
| `constraint_penalty` | 标准约束罚函数 | `constraint_values`, `scale` | 约束优化 |
| `boundary_penalty` | 边界惩罚 | `x`, `bounds`, `scale` | 防止越界 |
| `stagnation_penalty` | 停滞惩罚 | `generation`, `last_improvement_gen`, `scale` | 促进探索 |

### 4.4 已集成的求解器

Bias 模块已集成到以下求解器：

1. **BlackBoxSolverNSGAII** (`solver.py`) - 主要的 NSGA-II 求解器
2. **SurrogateAssistedNSGAII** (`surrogate.py`) - 代理模型辅助优化
3. **BlackBoxSolverVNS** (`vns.py`) - 变邻域搜索

使用方式完全一致：

```python
# NSGA-II
solver = BlackBoxSolverNSGAII(problem)
solver.enable_bias = True
solver.bias_module = bias

# Surrogate
solver = SurrogateAssistedNSGAII(problem, surrogate_type='gp')
solver.enable_bias = True
solver.bias_module = bias

# VNS
solver = BlackBoxSolverVNS(problem)
solver.enable_bias = True
solver.bias_module = bias
```

### 4.5 参数调优建议

#### 权重配置表

| 场景 | 奖励权重 | 罚函数权重 | 说明 |
|------|---------|-----------|------|
| **保守引导** | 0.01 - 0.03 | 1.0 - 3.0 | 轻微引导，适合探索性搜索 |
| **标准配置** | 0.05 - 0.1 | 5.0 - 10.0 | 平衡引导，推荐起点 |
| **激进引导** | 0.1 - 0.2 | 10.0+ | 强引导，快速收敛但可能早熟 |

#### 调优流程

```
1. 从标准配置开始 (reward=0.05, penalty=1.0)
   ↓
2. 观察收敛行为
   ↓
3. 调整策略：
   - 收敛太慢 → 增加奖励权重
   - 早熟收敛 → 减少奖励权重或增加种群多样性
   - 约束违背严重 → 增加罚函数权重
```

### 4.6 完整示例

查看 `nsgablack/bias_example.py` 获取更多示例：

```bash
python -m nsgablack.bias_example
```

示例包括：

1. 基础使用 - 标准 bias 配置
2. 自定义奖励函数（Rosenbrock）
3. 约束优化
4. 多目标优化（ZDT1）
5. VNS + Bias（Rastrigin）

### 4.7 API 参考

**BiasModule**

```python
class BiasModule:
    def add_penalty(self, func: Callable, weight: float = 1.0, name: str = "")
    def add_reward(self, func: Callable, weight: float = 0.05, name: str = "")
    def compute_bias(self, x: np.ndarray, f_original: float,
                    individual_id: Optional[int] = None) -> float
    def update_history(self, x: np.ndarray, f: float)
    def clear()
```

**create_standard_bias**

```python
def create_standard_bias(problem,
                        reward_weight: float = 0.05,
                        penalty_weight: float = 1.0) -> BiasModule
```

创建包含以下功能的标准 bias 模块：

- 约束罚函数
- 接近最优解奖励
- 深度可行性奖励

---

## 5. 并行批量运行与元优化

本节首先介绍如何在 CPU 多核环境中**并行多次运行 GA / VNS**，然后介绍 GA 超参数的元优化模块。

### 5.1 并行批量运行 (`nsgablack/parallel_runs.py`)

在真实工程问题中，单次 GA/VNS 运行往往带有较强随机性：不同随机种子可能得到不同的局部最优解。为了更稳健地找到更好的解，本项目提供了一个简单的“多实验批量运行”模块：`nsgablack.parallel_runs`。

它基于 Python 标准库 `concurrent.futures`，默认使用 **多进程 (`ProcessPoolExecutor`)**，充分利用 CPU 多核。接口设计保持尽量简单：

- `run_headless_in_parallel`: 并行多次调用 `run_headless_single_objective`
- `run_vns_in_parallel`: 并行多次调用 `BlackBoxSolverVNS.run`

#### 5.1.1 接口说明

```python
from nsgablack.parallel_runs import run_headless_in_parallel, run_vns_in_parallel
```

**`run_headless_in_parallel`**

```python
run_headless_in_parallel(
    objective,
    bounds,
    n_runs: int = 4,
    backend: {"process", "thread"} = "process",
    max_workers: int | None = None,
    **solver_kwargs,
) -> dict
```

- `objective` : callable
  - 单目标函数，接受形如 `(d,)` 或 `(n,d)` 的数组，返回标量；必须是**顶层定义函数**（可被多进程序列化）。
- `bounds` : list[tuple]
  - 每个变量的 `(min, max)`。
- `n_runs` : int
  - 要独立运行的总次数（例如 `n_runs=8` 表示 8 次独立 GA 试验）。
- `backend` : `"process"` / `"thread"`
  - `"process"` 使用多进程（推荐用于 **CPU 密集型数值优化**）；
  - `"thread"` 使用多线程（若目标函数主要是 I/O 或外部仿真，可考虑）。
- `max_workers` : int | None
  - 并发 worker 数量；None 时由执行器自行决定（通常等于 CPU 核数）。
- `**solver_kwargs`
  - 其余关键字参数传给 `run_headless_single_objective`，如 `pop_size`, `max_generations`, `mutation_rate`, `enable_diversity_init` 等。

返回值为一个字典：

```python
{
  "results": [
    {"index": 0, "x": best_x_0, "fun": best_f_0, "raw": 原始返回字典},
    {"index": 1, "x": best_x_1, "fun": best_f_1, "raw": ...},
    ...
  ],
  "best_index": int | None,  # fun 最小的一次的索引
  "best_x": ndarray | None,
  "best_fun": float | None,
}
```

**`run_vns_in_parallel`**

```python
run_vns_in_parallel(
    problem_factory,
    n_runs: int = 4,
    backend: {"process", "thread"} = "process",
    max_workers: int | None = None,
    **solver_kwargs,
) -> dict
```

- `problem_factory` : callable
  - 无参函数，每次调用返回一个新的 `BlackBoxProblem` 实例：

    ```python
    from nsgablack.problems import SphereBlackBox

    def problem_factory():
        return SphereBlackBox(dimension=5)
    ```
  - 这样可以避免不同进程/线程共享同一个问题对象导致的状态干扰。
- 其余参数与 `run_headless_in_parallel` 类似：`n_runs`, `backend`, `max_workers`, `**solver_kwargs`。
- `**solver_kwargs` 会通过 `setattr(solver, key, value)` 方式设置到内部的 `BlackBoxSolverVNS` 实例上，例如 `max_iterations`, `k_max`, `neighborhood_type` 等。

返回值结构与 `run_headless_in_parallel` 完全一致。

#### 5.1.2 简单示例：Sphere 函数并行优化

**并行多次运行 GA（`run_headless_single_objective`）**

```python
import numpy as np
from nsgablack.parallel_runs import run_headless_in_parallel


def sphere(x):
    x = np.asarray(x, dtype=float)
    return float(np.sum(x ** 2))


if __name__ == "__main__":  # Windows / 云服务器上使用多进程时建议加
    bounds = [(-5.0, 5.0)] * 5

    summary = run_headless_in_parallel(
        objective=sphere,
        bounds=bounds,
        n_runs=6,              # 独立运行 6 次 GA
        backend="process",    # 多进程并行，利用多核 CPU
        max_generations=40,
        pop_size=30,
        enable_diversity_init=False,
        enable_elite_retention=False,
        use_history=False,
        evaluate_convergence=False,
    )

    print("总运行次数:", len(summary["results"]))
    print("best run index:", summary["best_index"])
    print("best fun:", summary["best_fun"])
    print("best x:", summary["best_x"])
```

**并行多次运行 VNS**

```python
from nsgablack.parallel_runs import run_vns_in_parallel
from nsgablack.problems import SphereBlackBox


def problem_factory():
    return SphereBlackBox(dimension=5)


if __name__ == "__main__":
    summary = run_vns_in_parallel(
        problem_factory=problem_factory,
        n_runs=6,
        backend="process",
        max_iterations=200,
        k_max=5,
    )

    print("总运行次数:", len(summary["results"]))
    print("best run index:", summary["best_index"])
    print("best fun:", summary["best_fun"])
    print("best x:", summary["best_x"])
```

**实践建议：**

- 对于纯数值的黑箱目标函数（大量 numpy/scipy 运算），推荐 `backend="process"`，更好利用 CPU 多核；
- 若目标函数内部主要是 I/O 或外部仿真调用（阻塞时间远大于计算时间），可以尝试 `backend="thread"`；
- 在 Windows 和大多数云服务器环境中，使用多进程时请始终在脚本入口加上 `if __name__ == "__main__":` 保护，避免子进程重复导入并递归创建进程。

---

## 5.2 元优化模块：自动调节 NSGA-II 参数 (`nsgablack/metaopt.py`)

本模块提供**高级元优化**能力，用于自动寻找 GA / NSGA-II 的优秀超参数配置，特点：

- 支持多种多目标汇总指标：
  - `single`：单目标或多目标求和（默认）。
  - `weighted_sum`：按给定权重对多目标加权求和。
  - `hypervolume`：基于参考点的 Hypervolume 近似（越大越好，内部取负供最小化）。
  - `eps_constraint`：以第一个目标为主，其他目标超过 ε 时增加罚项。
- 支持多种后端：
  - `skopt`：基于高斯过程的贝叶斯优化 (`gp_minimize`)，适合精细搜索。
  - `tpe`：基于 Optuna 的 TPE 采样，适合非平滑/噪声较大的情形。
  - `cma`：基于 Optuna 的 CMA-ES 采样，偏向连续空间全局搜索。
- 内建简单可视化：
  - `plot_metaopt_history(history)`：绘制损失收敛曲线和“超参数 vs 损失”的散点图，帮助理解搜索行为。

### 关键类型与函数

**SolverHyperParams**

```python
from nsgablack.metaopt import SolverHyperParams

hp = SolverHyperParams(pop_size=80, max_generations=150, crossover_rate=0.85, mutation_rate=0.15)
hp.apply_to(solver)  # 一键应用超参数
```

**default_search_space()**

- 返回 `(dimensions, decoder)`：
  - `dimensions`：适用于 skopt 的搜索空间 `[Integer, Integer, Real, Real]`。
  - `decoder(x)`：把搜索向量 `[pop_size, max_generations, crossover_rate, mutation_rate]` 转为 `SolverHyperParams` 实例。

**bayesian_meta_optimize(...)**

```python
from nsgablack.metaopt import bayesian_meta_optimize

result = bayesian_meta_optimize(
    base_problem_factory=lambda: BusinessPortfolioOptimization(dimension=5),
    n_calls=25,
    n_initial_points=8,
    n_repeats=1,
    random_seed=42,
    objective_type="weighted_sum",   # 或 "single" / "hypervolume" / "eps_constraint"
    backend="skopt",                 # 或 "tpe" / "cma"
)

best = result["best_params"]
print("最优 GA 超参数:")
print(best)
```

返回字段：

- `best_params`: `SolverHyperParams`，记录 `pop_size`, `max_generations`, `crossover_rate`, `mutation_rate`。
- `best_loss`: 搜索过程中最小的 loss 值。
- `backend_result`: 对应后端原始结果对象（`skopt.OptimizeResult` 或 `optuna.study.Study`）。
- `history`: 列表，元素形如 `{ "params": {...}, "loss": float }`，可直接传给 `plot_metaopt_history` 可视化。

**plot_metaopt_history(history)**

```python
from nsgablack.metaopt import plot_metaopt_history

result = bayesian_meta_optimize(...)
plot_metaopt_history(result["history"])
```

效果：

- 第一幅图：loss 随试验编号变化，用于观察收敛趋势。
- 后续子图：`pop_size` / `max_generations` / `crossover_rate` / `mutation_rate` 与 loss 的散点关系，便于判断哪些区域表现更好。

> 注：若未安装 `matplotlib`，函数会直接返回而不抛错。

### 多目标指标说明

- **single**：
  - 单目标：直接取最优目标值。
  - 多目标：对多个目标求和后取最小值，适合作为快速近似。
- **weighted_sum**：
  - 适用于不同目标量纲相近、且你希望显式指定权重的场景。
  - 使用方式：在调用 `bayesian_meta_optimize` 时传入 `weights=np.array([...])`。
- **hypervolume**：
  - 利用近似 Hypervolume 衡量 Pareto 前沿质量。内部实现为参考点主导体积的简单求和近似，用于相对比较而非严格 HV 计算。
  - 需要提供较合理的 `reference_point`，否则会导致 volume 失真（不传则自动用当前解的 max + 1 作为参考点）。
- **eps_constraint**：
  - 适合“一个主目标 + 若干约束目标”的情况：以第 0 个目标为主，对于其它目标超过 ε 的部分施加罚项。
  - 使用方式：指定 `eps=...`。例如 `eps=0.05` 表示允许其他目标最多 0.05 的值，超过部分按 `1e3` 的系数加到主目标上。

### 后端选择建议

- `skopt` (GP): 对于维度较低、目标较平滑的问题表现好；可以利用 acquisition function (`EI`) 高效探索。
- `tpe`: 更鲁棒于噪声和离散/不规则搜索空间，适合未知结构的黑箱问题。
- `cma`: 适合连续变量较多、对全局搜索有较强需求的场景。

使用 TPE/CMA 后端需要安装 `optuna`：

```bash
pip install optuna
```

若未安装 `optuna`，调用 `backend="tpe"` 或 `backend="cma"` 会抛出清晰错误提示。

---

## 5.3 可选 Numba 加速：核心非支配判定

为提升 NSGA-II 在中大规模种群、多目标场景下的性能，项目提供了一个可选的 Numba 加速层：`nsgablack.numba_helpers`。

- 若环境中安装了 `numba`（你已经可以通过 `pip install numba` 完成安装），`BlackBoxSolverNSGAII` 会自动使用 `@njit` 加速的非支配判定函数 `fast_is_dominated`；
- 若未安装或 numba 在当前平台不可用，则自动回退到原来的纯 numpy 实现，功能完全不受影响。

内部机制简述：

- `nsgablack/numba_helpers.py` 中定义：

  ```python
  try:
    from numba import njit
    NUMBA_AVAILABLE = True
  except Exception:
    NUMBA_AVAILABLE = False

    def njit(*args, **kwargs):  # 占位装饰器
      def wrapper(f):
        return f
      return wrapper


  @njit(cache=True)
  def fast_is_dominated(obj: np.ndarray) -> np.ndarray:
    ...  # 针对 (N,M) 目标矩阵的双层循环非支配判定
  ```
- 在 `BlackBoxSolverNSGAII.is_dominated_vectorized` 中：

  ```python
  from .numba_helpers import fast_is_dominated, NUMBA_AVAILABLE

  def is_dominated_vectorized(self, obj_matrix):
    if obj_matrix.ndim == 1:
      obj = obj_matrix.reshape(-1, 1)
    else:
      obj = obj_matrix

    if NUMBA_AVAILABLE and fast_is_dominated is not None:
      try:
        return fast_is_dominated(obj)
      except Exception:
        pass  # 任何 numba 相关异常一律回退

    # 回退到原有 numpy 实现
    ...
  ```

这样设计的优点：

- 对于用户：
  - **不强制依赖 numba**：默认安装 `requirements.txt` 即可使用全部功能；
  - 若额外安装 `numba`，核心非支配排序会自动获得 JIT 加速；
  - 任何 numba 或编译器异常都被安全捕获，不会影响求解流程。
- 对于高维/大种群场景：
  - 当种群规模较大（例如 `pop_size >= 200` 且 `max_generations` 较高）时，`fast_is_dominated` 能显著减少每代非支配判定的时间开销；
  - 由于第一次调用会触发 JIT 编译，**建议在长时间运行前先做一个短小的“预热”调用**，让编译开销提前支付。

安装 numba（可选）：

```bash
pip install numba
```

> 提示：在某些平台（特别是非 x86 架构或受限环境）上，numba 可能无法正常安装或运行，此时本库会自动退化为纯 numpy 路径，无需额外配置。

### 快速对比示例

在仓库根目录有脚本 `run_metaopt_example.py`，其内容类似：

```python
from nsgablack.metaopt import quick_demo_metaopt

if __name__ == "__main__":
    quick_demo_metaopt()
```

`quick_demo_metaopt()` 将：

1. 使用 `skopt` 后端对投资组合示例问题做一次元优化；
2. 若环境中安装了 `optuna`，再使用 TPE 后端做一次对比；
3. 打印两者的最优超参数和对应 loss；
4. 调用 `plot_metaopt_history` 绘制搜索历史，可视化损失收敛和“超参数 vs 损失”的关系。

---

## 6. 典型应用场景速览

本节给出几个常用场景的最小可运行示例代码，方便直接拷贝到脚本里使用。

### 6.1 工程梁设计优化（多目标 + 约束）

```python
from nsgablack.problems import EngineeringDesignOptimization
from nsgablack.solver import BlackBoxSolverNSGAII

problem = EngineeringDesignOptimization(dimension=3)
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 40
solver.max_generations = 80
solver.enable_diversity_init = True

solver.initialize_population()
for _ in range(solver.max_generations):
  solver.animate(frame=None)

print("评估次数:", solver.evaluation_count)
print("Pareto 解个数:", len(solver.pareto_solutions["individuals"]))
```

### 6.2 投资组合优化（收益-风险平衡）

```python
from nsgablack.problems import BusinessPortfolioOptimization
from nsgablack.solver import BlackBoxSolverNSGAII

problem = BusinessPortfolioOptimization(dimension=5)
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 60
solver.max_generations = 120
solver.enable_diversity_init = True

solver.initialize_population()
for _ in range(solver.max_generations):
  solver.animate(frame=None)

pareto = solver.pareto_solutions
print("Pareto 解示例 (前 3 个):")
for x, f in list(zip(pareto["individuals"], pareto["objectives"]))[:3]:
  print("weights =", x, " objectives =", f)
```

### 6.3 神经网络超参数多目标优化

```python
from nsgablack.problems import NeuralNetworkHyperparameterOptimization
from nsgablack.solver import BlackBoxSolverNSGAII

problem = NeuralNetworkHyperparameterOptimization(dimension=4)
solver = BlackBoxSolverNSGAII(problem)
solver.pop_size = 50
solver.max_generations = 100
solver.enable_diversity_init = True

solver.initialize_population()
for _ in range(solver.max_generations):
  solver.animate(frame=None)

pareto = solver.pareto_solutions
print("找到的 Pareto 解个数:", len(pareto["individuals"]))
```

---

## 7. 参数参考表（按参数，详尽）

下面按参数逐项列出主要类/函数的参数、类型、默认值与简要说明，便于直接查阅并正确调用接口。

1) `BlackBoxProblem(name: str = "黑箱问题", dimension: int = 2, bounds: dict | None = None)`

- `name` (str): 问题名称，用于日志与可视化标题。默认 "黑箱问题"。
- `dimension` (int): 变量维度（设计变量个数）。默认 2。
- `bounds` (dict | None): 变量边界字典，形如 `{ 'x0': [min, max], 'x1':[min,max], ... }`。默认 None（自动设为 [-5,5]）。
- 返回/方法: `evaluate(x)` 必须由子类实现，建议支持向量化输入（shape=(n,d)）与单点输入；`get_num_objectives()` 返回目标数（默认为 1）。

2) `BlackBoxSolverNSGAII(problem: BlackBoxProblem)` — 重要构造字段与可配置参数

- `problem` (BlackBoxProblem): 必需。需实现 `evaluate`。
- `pop_size` (int, default=80): 种群大小。推荐为偶数。
- `max_generations` (int, default=150): 最大代数。
- `crossover_rate` (float, default=0.85): 交叉概率 (0-1)。
- `mutation_rate` (float, default=0.15): 变异概率 (0-1)。
- `initial_mutation_range` (float, default=0.8): 变异幅度缩放基准。
- `enable_diversity_init` (bool, default=False): 若 True 使用 `DiversityAwareInitializerBlackBox` 初始化。
- `use_history` (bool, default=False): 与 `enable_diversity_init` 联动，是否加载历史解文件。
- `enable_elite_retention` (bool, default=True): 启用自适应精英保留。
- `diversity_params` (dict): 可配置键：`candidate_size` (int)、`similarity_threshold` (float)、`rejection_prob` (float)、`sampling_method` ('lhs'|'random')。示例默认 `{ 'candidate_size': 500, 'similarity_threshold': 0.05, 'rejection_prob': 0.6, 'sampling_method':'lhs' }`。
- `elite_manager` (AdvancedEliteRetention): 管理精英替换策略，可调用 `set_replacement_config` 修改替换比与权重。
- 常用方法/返回字段:
  - `initialize_population()` — 基于 `enable_diversity_init` 与 `diversity_params` 初始化。
  - `evaluate_population(population)` — 输入 (N, d) 返回 (N, m) 或 (N,) 目标数组。
  - `selection()`, `crossover(parents)`, `mutate(offspring)` — 遗传算子，可覆盖或替换。
  - `non_dominated_sorting()` — 返回 `(rank, crowding_distance, fronts)`。
  - 运行时字段: `population` (np.ndarray), `objectives` (np.ndarray), `pareto_solutions` (dict), `history` (list) 等。

3) `DiversityAwareInitializerBlackBox(problem, history_size: int = 1000, similarity_threshold: float = 0.1, rejection_prob: float = 0.7)`

- `history_size` (int): 保存历史解的最大条目数。
- `similarity_threshold` (float): 判定新候选与历史相似的阈值（单位为归一化欧氏距离）。
- `rejection_prob` (float): 若相似，按概率拒绝该候选。
- 主要方法:
  - `initialize_diverse_population(pop_size=100, candidate_size=1000, sampling_method='lhs')` — 先在候选集中评估，再按 crowding/dist 等剔重并返回 (pop, fitness)。
  - `set_history_file(path)`, `save_history(path=None)`, `load_history(path=None)`, `clear_history()`, `add_to_history(solution, fitness)`。

4) `AdvancedEliteRetention(max_generations: int, population_size: int, initial_retention_prob: float = 0.9, min_replace_ratio: float = 0.05, max_replace_ratio: float = 0.6, replacement_weights: dict | None = None)`

- `initial_retention_prob` (float): 基础保留概率。
- `min_replace_ratio`, `max_replace_ratio` (float): 替换比例范围。
- `replacement_weights` (dict): 自定义权重（例如 `{'stagnation_neg':0.45, 'diversity_neg':0.35}`），用于 `get_elite_replacement_ratio` 计算。
- 主要方法: `calculate_elite_retention_probability(current_generation, current_best_fitness, population_fitnesses, population)` 返回 [0.05,0.95]，`get_elite_replacement_ratio(retention_prob=None)`。

5) `run_headless_single_objective(objective, bounds, *, pop_size=80, max_generations=150, mutation_rate=0.15, crossover_rate=0.85, enable_diversity_init=False, enable_elite_retention=True, plot=False, maximize=False, use_history=False, history_file=None, seed_history_rate=0.3, name="降维后单目标黑箱", convergence_log_file=None, evaluate_convergence=False, evaluation_method='svm', evaluation_threshold=30, min_replace_ratio=None, max_replace_ratio=None, replacement_weights=None, show_progress=False)`

- `objective` (callable): 接受数组 (d,) 返回标量或单目标；若传入向量化输入，调用方应保证返回合适形状。
- `bounds` (list[tuple]): 每个变量的 (min, max)。例如 `[(0,1),( -5,5), ...]`。
- `pop_size`, `max_generations`, `mutation_rate`, `crossover_rate`: 如上。
- `enable_diversity_init`/`use_history`: 启用多样性初始化并可加载历史。
- `plot` (bool): 若 True，会启用 `SolverVisualizationMixin` 的绘图（通常在交互式环境使用）。
- `show_progress` (bool): 若 True 且 `plot=False`，在主循环中尝试使用 `tqdm.trange` 展示每一代的进度（若环境未安装 `tqdm`，自动退回普通循环）。
- `maximize` (bool): 若 True，将目标取负值并以最小化器运行，返回的 `fun` 会被修正为最大化后的值。
- `evaluate_convergence` (bool): 若 True，会在结束后调用 `log_and_maybe_evaluate_convergence`（将最优解附加到收敛日志并在样本达到阈值时评估）。
- 返回结构: `{'x': best_x, 'fun': best_f, 'solver': solver_instance, 'evaluation': eval_info_or_None}`。

6) 收敛评估函数（`nsgablack/convergence.py`）

- `log_and_maybe_evaluate_convergence(best_x, best_f, bounds, log_file=None, threshold=30, method='svm')`
  - `log_file` (str | None): 收敛日志路径，默认 `history/all_converged_solutions.csv`。
  - `threshold` (int): 最少需多少条历史解才触发自动评估。
  - `method` (str): `'svm'` / `'cluster'` / `'both'`。
  - 返回: 含 `evaluated` (bool) 字段；若 `evaluated==True`，会包含评估结果字段（如 `auc`, `compact` 等）。

7) `SolverVisualizationMixin`（常用控件与回调）

- 常见交互控件：`btn_run`（开始）、`btn_stop`（停止）、`btn_reset`（重置）、`pop_box`（更改 `pop_size`）、`gen_box`（更改 `max_generations`）、`mutation_slider`（更改 `mutation_rate`）、`elite_slider`（更改 `elite_retention_prob`）等。
- 若要在无头环境使用，请确保 `plot_enabled=False` 或不调用 `_init_visualization()`。

8) `UniversalFeatureSelector` 与降维器（概览）

- `UniversalFeatureSelector`（见 `exmaple.py`）参数：
  - `optimizer` (BlackBoxOptimizer 或 None)：用于在降维空间执行优化；若为 None，会在 optimize 时创建默认 `SimpleEvolutionaryOptimizer`。
  - `feature_names` (list[str] | None)：特征名称，用于可视化输出。
  - 主要方法：`collect_data(objective, bounds, initial_samples=100, method='lhs')`, `analyze_features(X,y,methods=None)`, `smart_feature_selection(X,y, reduction_method='cumulative', threshold=0.95, min_features=1, max_features=None)`, `prepare_reduced_problem(...)`, `optimize_with_feature_selection(...)`。
- PCA/KPCA/PLS/ActiveSubspace/Autoencoder 的构建函数（如 `prepare_pca_reduced_problem`）通常接受：`objective_func`, `bounds`, `n_components`, `initial_samples`, `sampling_method`, 以及特定 reducer 的超参（如 kernel、decoder_alpha、epochs 等），返回字典包含 `reduced_objective`, `reduced_bounds`, `expand_to_full`, `*_model`, `samples_info`。

---
