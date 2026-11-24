# 三种算法怎样保留自己的语义

本 Project 用同步贝叶斯优化、CMA-ES 和 MAP-Elites 验证三类不同的算法结构。公共算法组件位于 `nsgablack.adapters`、`nsgablack.units` 和 `nsgablack.representation`；三个 Case 负责问题、候选管线和显式装配。

验收关注候选身份、观测、整批更新、档案、回滚与恢复，不比较三个不同问题上的算法性能。

## 运行

在仓库根目录执行：

```powershell
python examples/cases/algorithm_semantics/run_project.py --check --build-check
python examples/cases/algorithm_semantics/run_and_report.py
```

第二条调用正式 `execute_project`，串行运行三个 Case，将实际 Project 结果保存到 `results/project_run.json`。报告脚本不实现搜索、资源调度或第二套运行循环。

单独运行或并行运行：

```powershell
python examples/cases/algorithm_semantics/run_project.py --group synchronous_bo
python examples/cases/algorithm_semantics/run_project.py --group cmaes_distribution
python examples/cases/algorithm_semantics/run_project.py --group map_elites_archive
python examples/cases/algorithm_semantics/run_project.py --group parallel
```

Project 提供三线程、三个 worker 的 CPU 总授权；每个 Case 请求一线程、一个 worker。Case 的 Pool 和运行身份独立，parallel 不建立跨 Case 可写母池。

## 从装配入口读代码

- [BO](cases/synchronous_bo/build_solver.py)：[问题](cases/synchronous_bo/problem/)、[管线](cases/synchronous_bo/pipeline/)、[算法装配](cases/synchronous_bo/adapter/)。
- [CMA-ES](cases/cmaes_distribution/build_solver.py)：[问题](cases/cmaes_distribution/problem/)、[管线](cases/cmaes_distribution/pipeline/)、[算法装配](cases/cmaes_distribution/adapter/)。
- [MAP-Elites](cases/map_elites_archive/build_solver.py)：[问题](cases/map_elites_archive/problem/)、[管线](cases/map_elites_archive/pipeline/)、[算法装配](cases/map_elites_archive/adapter/)。

每个 build_solver 接收 `resource_context` 与 `component_overrides`。参数集中在本 Case 的 config.py；build_trainer/run_trainer 保留薄别名。

## 同步 BO：模型、采集规则和采集搜索器

本例最小化 `f(x)=(x-0.25)^2`，范围 `[0,1]`。先真实评估 0 和 1，再由固定 RBF GP 与 LCB 在网格中挑选下一真实评估点。

```python
from nsgablack.adapters import (
    BayesianOptimizationAdapter, FixedRBFPosterior,
    LowerConfidenceBound, GridAcquisitionOptimizer,
)

adapter = BayesianOptimizationAdapter(
    model=FixedRBFPosterior(), acquisition=LowerConfidenceBound(beta=2.0),
    optimizer=GridAcquisitionOptimizer(grid=((0.25,), (0.5,), (0.75,))),
)
```

预测、采集价值和真实目标分别保留含义。采集搜索不增加 Problem 的求值次数；Bias 的选择分数也不改变模型使用的 raw Y。

训练数据读取正式完整 Evaluation Event，包含已评估但未被接纳的行。checkpoint 携带经过验证的训练证据闭包；恢复不伪造新 Journal 事件、不重跑 Problem。

源码：[Adapter](../../../adapters/bayesian_optimization/adapter.py)、[数值组件](../../../adapters/bayesian_optimization/components.py)、[观测消费者](../../../adapters/bayesian_optimization/evidence.py)、[Unit](../../../units/bayesian.py)。

首版限定同步、单目标、固定参数 GP；采集函数和搜索器要求显式无状态。带求值接管的 Provider 不属于真实数据保证范围；真实异步、联合 q-batch、自动超参数训练及跨算法观测共享尚未承诺。

## CMA-ES：采样、排名与分布更新

默认二维问题最小化 `(x0-0.2)^2+(x1+0.1)^2`，运行三轮，每轮四次真实求值、两个正权重重组父代。

```python
from nsgablack.adapters import (
    CMAESAdapter, CMAParameters, GaussianCohortSampler,
    StableObjectiveRanking, PositiveCMAUpdate,
)

parameters = CMAParameters(population_size=4, parents=2)
adapter = CMAESAdapter(
    [0.0, 0.0], sigma=0.5, parameters=parameters,
    sampler=GaussianCohortSampler(seed=42), ranking=StableObjectiveRanking(),
    updater=PositiveCMAUpdate(parameters),
)
```

Unit 保存均值、完整协方差、步长、演化路径与本轮采样关系。四次观测与两个重组父代分别保留；尚未评估的新均值不能充当已评估结果。

首版要求完整 cohort：changed repair 在送评前拒绝，预算或硬接纳造成残缺时拒绝分布更新，已经发生的求值成本保留。不会将 lambda 静默缩小。

源码：[Adapter](../../../adapters/cmaes/adapter.py)、[公式组件](../../../adapters/cmaes/components.py)、[Unit](../../../units/cmaes.py)。范围为单目标、正权重、无约束排名；不支持跨步骤攒齐残缺 cohort。候选经过统一 Pool，但尚未声明 PoolTask initialize/refine/compete 输入模式。

## MAP-Elites：描述符、格子、竞争与生成器

本例在 `[0,1]^2` 最小化 `(x0-0.2)^2+(x1-0.8)^2`。描述符为坐标，每维以 0.5 分成两格；五个候选经过同格竞争，最终冠军为 B/C/D。

```python
from nsgablack.adapters import (
    MapElitesAdapter, MapElitesConfig, IdentityDescriptor, GridCells,
    MinimizeObjective, SequenceEmitter,
)

adapter = MapElitesAdapter(
    MapElitesConfig(batch_size=5), descriptor=IdentityDescriptor(), cells=GridCells(),
    competition=MinimizeObjective(),
    emitter=SequenceEmitter(((.1,.1), (.4,.4), (.6,.4), (.6,.8), (.8,.2))),
)
```

SequenceEmitter 提供可手算的有限夹具；GaussianArchiveEmitter 从档案生成后继，针对性测试也实际执行该路径。

档案 Unit 唯一维护格子冠军，Pool 发布冠军的精确引用视图。raw 反馈和档案缓存须一致；修复跨格后按实际候选重新定位。普通生成器的部分接纳可逐条更新格子。

源码：[Adapter](../../../adapters/map_elites/adapter.py)、[档案组件](../../../adapters/map_elites/components.py)、[Unit](../../../units/map_elites.py)。生成器首版负责产生候选，尚未接入 CMA emitter 自适应反馈；不能把有整批反馈要求的生成器任意接入后就认为语义成立。仅显式 exhausted 才据此结束，临时空提案属于等待。

## 验证和实际结果

```powershell
python -m pytest tests/test_bayesian_semantics.py tests/test_cmaes_semantics.py tests/test_map_elites_semantics.py tests/test_algorithm_semantics_project.py -q
```

验证覆盖真实目标与模型值分离、修复最终版本、部分接纳、原索引对齐、失败回滚、求值成本保留、正式文件 checkpoint 和多实例所有权。

详细判据见 [语义验收设计](../../../docs/architecture/ALGORITHM_SEMANTIC_ACCEPTANCE_CN.md)，实际执行记录见 [结果](RESULTS_CN.md)。本地观察 JSON 与正式 Project ArtifactBinding 分开标明，文件名不充当权威引用。
