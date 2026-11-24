# 从 Catalog 条目到第一个正式装配

Catalog 帮你找到组件；真正使用它，需要把组件接进一个 Case 的工厂，并从外层 Project 运行。本页沿两个现有标准 Project 说明这一步怎么做。所有路径和接口按当前源码核对，本轮没有执行优化、训练或试运行；下面命令是留给实际运行时使用的入口。

先选与你任务相符的一条路线：只有决策变量、目标和约束的优化问题，看第一条；有特征与监督目标、需要拟合预测模型，看第二条。优化问题不要求凭空补一个训练标签列。

## 路线一：二维优化，GA 搜索后由 VNS 精修

先打开 [assembled_ga_vns 的说明](../../examples/cases/assembled_ga_vns/README.md)。它已经具备 Project → Case → Standard Scaffold，不需要先写自己的循环。

这个例子里，一个候选是二维向量 `x=(x0,x1)`，每个值在 `[-4,4]`；原始目标是 `(x0-2)^2+(x1+1)^2`，只有一个最小化目标。`population_size` 是 GA 成员容量，`local_batch` 是 VNS 每次提出的邻域候选数；二者都不是池容量。

### 第一步：先看 Problem，确定数组每一列是什么

打开 [problem/quadratic.py](../../examples/cases/assembled_ga_vns/cases/hybrid_search/problem/quadratic.py)。其中 `dimension=2` 决定单个数值候选 shape 为 `(2,)`，`evaluate` 定义真实目标，`evaluate_constraints` 定义原始违反量。

要替换成自己的业务问题，先把决策变量、单位、上下界、目标方向和违反量说清楚，再改此处。不要先挑一个算法，再把不相干的业务表格直接当成种群矩阵。

### 第二步：把“怎么产生候选”和“候选是否合法”接到各自位置

打开 [adapter/composition.py](../../examples/cases/assembled_ga_vns/cases/hybrid_search/adapter/composition.py)。`build_adapter(settings)` 创建了两个实际算法实例：

- GA 使用 `NSGA2Adapter`，直属初始化为 `UniformInitializer(-4,4)`，直属变异为 `GaussianMutation`。
- VNS 使用 `VNSAdapter`，直属变化为 `ContextGaussianMutation`，读取本次 VNS 的邻域尺度。

再打开 [pipeline/main.py](../../examples/cases/assembled_ga_vns/cases/hybrid_search/pipeline/main.py)。它只装配 `BoxRepair`，负责问题边界。共享 Pipeline 没有初始化或变异槽位，并不表示 GA/VNS 没有变化操作；它们分别归实际 Adapter 持有。

如果只想改变 GA 扰动尺度，调整 Case [config.py](../../examples/cases/assembled_ga_vns/cases/hybrid_search/config.py) 的 `ga_sigma`；如果要改变 VNS 尺度，调整 `vns_sigma`，保留 ContextGaussianMutation 读取局部尺度的接线。改变量上下界时，应同步核对 Problem、初始化组件和问题 repair，不能只改其中一处。

对应 Catalog 用法见 [adapter.nsga2、adapter.vns 和 repr.gaussian_mutation](../catalog_usage/NSGABLACK_COMPONENT_USAGE_CN.md)。条目的代码是这些工厂中的装配片段；它不会自动运行。

### 第三步：看清 GA 怎么把成员交给 VNS

同一 `composition.py` 中的 `subpools.all(ga)` 选择这个 GA 实例发布的成员视图，`PoolTaskSpec(..., count="all")` 显式要求逐成员精修。VNS 每个起点先通过正式修复和重新求值建立本任务基准，后续再比较邻域。

本例区分两个输出：`output="refined"` 保存精修期间接纳的提案历史；父级 `get_pool_task_results(control, "vns")` 交付本轮任务最终选中的精确引用。将结果交回 GA 后，GA 仍按自己的规则竞争保留，不能把局部算法的全部历史当作最终种群。

仅写 `stage("ga")` 后接 `stage("vns")` 并没有表达候选交接；原例的池任务、来源和返回竞争接线应一起保留。调度阶段仍由 Router/SearchPlan 决定，SolutionPool 不代替调度器。

### 第四步：在规范装配入口找齐所有自由变量

打开 [build_solver.py](../../examples/cases/assembled_ga_vns/cases/hybrid_search/build_solver.py)。这里的来源关系是明确的：

- `settings` 由同 Case 的 `DemoConfig` 根据配置建立。
- `problem` 由 `build_problem()` 创建，规定评估含义。
- `pipeline` 由 `build_pipeline()` 创建，处理问题候选。
- `adapter` 由 `build_adapter(settings)` 创建，拥有搜索决策与 Unit。
- `resource_context` 作为函数参数从外层 Project L0 注入。
- `solver` 是此函数构造的 `ComposableSolver`，随后设置种子、提交预算并挂载观察插件。

因此在某条用法里看到 `solver.add_plugin(...)`，应放在此函数构造 Solver 之后、`return solver` 之前；看到 `mutator=...`，应放进实际拥有该变化的 Adapter 工厂，不能在一个全局脚本里先假定这些变量存在。

### 第五步：从 Project 运行，再核对反馈与身份

在 nsgablack 仓库根目录，正式入口为：

```powershell
python examples/cases/assembled_ga_vns/run_project.py --group plan
```

这个组由 [project_config.py](../../examples/cases/assembled_ga_vns/project_config.py) 声明，使用共享 L0 发放资源，并运行已有有限搜索计划。它是实际优化命令；本页没有替你执行。

运行后应先判断：提交步数与实际评估数是否分别记录、GA/VNS 的真实绑定是否出现、精修输入输出是否指向正确的候选版本、最终成员与目标/违反量是否行对齐。该 Project 以 `results/plan/` 保存此组的结果。仓库里已有结果可能来自旧运行，不能把它们当成本次修改后产生的收据。

若需要额外软偏好，在 Case `bias/` 工厂装配 `bias.callable`，保留 Problem 原始评价；若需要跨代非支配档案，在 Case `plugins/` 装配 `plugin.pareto_archive`。偏好和档案都不能替代原始目标或硬约束接纳。

若任务关心随机场景风险，另看正式 `examples/cases/risk_bias` Project 和用法页的 `bias.risk`。这个 Bias 依赖评估 Provider 为每个候选给出的 `mc_mean/mc_std/mc_min/mc_max`；仅把 RiskBias 加进模块却未提供指标，可能安静地返回 0。先接场景评估，再判断风险评分是否生效。

## 路线二：两列数值特征，线性回归模型

使用 mlblack 的现有 `examples/cases/catalog_codec_demo` Project。路径以下相对 mlblack 仓库；它与 nsgablack 使用同一套 Project/Case 层级。

### 第一步：数据工厂决定特征布局

`cases/linear_point/pipeline/main.py::build_pipeline` 生成固定种子的公开合成数据：`X_train` 为 `(24,2)`，`y_train` 为 `(24,)`，真实公式为 `1+2*x0-0.5*x1`，特征顺序为 `("x0","x1")`。

换成自己的数据时，先构造相同契约的 `NumericDataView`，不要把标签拼进特征列；有验证集时成对提供 `X_valid/y_valid`。DataView 描述数据，LearningProblem 才定义训练与验证反馈。

### 第二步：Representation 声明模型状态，不预跑初始化

`cases/linear_point/build_solver.py` 使用 `data.n_features` 创建 `LinearPointRepresentation`。默认 PointHead 与 LinearPointCodec 的参数布局为 `[intercept,w0,w1]`，模型候选 shape 为 `(3,)`。Codec 解码这些参数产生线性预测模型，不会替你训练；Adapter Unit 保存的是搜索结构，也不是模型 Codec。

读取 `representation.dimension` 即可获得维数。先构造 LearningSolver 和 SolutionPool，再由正式初始化创建带运行身份的 UnknownState，不能为了猜 shape 提前采样一个初值。

### 第三步：在 build_solver 接好问题和算法

`problem/__init__.py::build_problem(data)` 返回 `SupervisedRegressionProblem`；本例没有验证集，所以配置 `use_valid_objective=False`。`adapter/__init__.py::build_adapter` 用正式 `build_optimization_adapter("gradient.sgd", learning_rate=...)` 创建梯度算法。

`build_solver.py` 只负责把 Problem、Representation、Adapter 和 `resource_context` 传给 `build_learning_solver`，再设置种子与预算。它不在函数中调用 `fit()`。`build_trainer.py` 只把 `build_solver` 导出为别名，不能复制一套训练逻辑。

具体用法见 [NumericDataView、LinearPointCodec、LinearPointRepresentation 与 LearningSolver](../catalog_usage/MLBLACK_COMPONENT_USAGE_CN.md)。这几节给出了工厂输入、shape、输出含义和各自源码位置。

### 第四步：从 ML Project 交付结果

在 mlblack 仓库根目录，正式入口为：

```powershell
python examples/cases/catalog_codec_demo/run_project.py --no-record
```

当前配置为 1 线程、0 GPU、最多 3 个提交步，不需要模型账号或 Torch。它用于核对装配与求值，不是收敛性能实验；本轮没有执行该命令。

正式 ML 结果应能交付已评估 `best_state`、对应 `best_model` 或模型 DataRef、`best_feedback/best_objectives`、report 和 Artifact 引用。先核对模型与反馈绑定到同一候选身份，再看评价值。仅看到 `NumericDataView.describe()`、`codec.decode()` 或工厂返回一个 Solver，均不表示训练已完成。

## 不确定该改哪一行时

先写一句具体目标，例如“只把 GA 的扰动从 0.45 改为 0.2，保留问题与 VNS”，然后沿该 Case 的 `config.py → adapter/工厂 → build_solver.py` 找到实际消费者。若目标是“新增一个目标”或“改变特征列数”，则先从 Problem 或 DataView/Representation 布局开始，并核对下游 shape。

读 Catalog 时依次核对“先准备什么、放在哪、接入步骤、怎样判断接对”。配套组件 key 是需要一起考虑的装配关系；代码中出现一个类名不代表目录已登记同名 key，目录有条目也不表示当前 Case 已装配或运行过它。
