# 从正式 Case 工厂替换 BO、CMA-ES 与 MAP-Elites 组件

三节分别使用现有 `examples/cases/algorithm_semantics` 的三个独立 Case。先复制完整 Project，保留 Project L0、标准运行入口和各 Case 的 Problem/Pipeline/报告插件。下文按仓库原位置标注；每节可独立采用，不要求先读其它节。本页没有执行算法、拟合模型或生成运行收据。

组件在 `adapter/__init__.py` 构造并传给 Adapter，由正式 `build_solver.py` 调用；没有假设存在 `set_model/set_sampler/set_emitter`。UnitBinding 只绑定构建与恢复规则，不创建运行 Unit。`algorithm_unit` 在实际使用前允许为 None，不为观察提前调用 ensure_unit 或手动 new Unit。

## tool.bo_model · 将后验、采集函数和采集搜索接到实际 BO 消费者

**什么时候用：** 想改变代理后验、探索规则或可选候选网格，又保留原 Case 的真实求值、观测来源核对和结果报告。此主例共用 `tool.bo_model/tool.bo_acquisition/tool.bo_acquisition_optimizer/tool.bo_unit`，不用在 Problem 里手工调用模型选点。

**先准备什么：** 使用完整 algorithm_semantics Project 的 `cases/synchronous_bo`，依赖当前 nsgablack、blackbase、NumPy。原 Problem 接收 `(1,)`，raw 目标为 `(x-0.25)^2`，Pipeline 将点修复到 `[0,1]`。CaseConfig 的 max_steps=4、bias_weight=0、checkpoint_every=1 保留；output_dir 未配置时输出到 Project 的 `results/synchronous_bo`。下面工厂的初始点 shape `(2,1)`，候选网格 `(3,1)`；单个 posterior 查询返回 mean/std 两个长度为网格行数的一维数组。

**放在哪：** 替换 `cases/synchronous_bo/adapter/__init__.py`；再按下方完整 builder 保持实际调用。保留原 problem、pipeline、bias、BOReport 与标准 run_solver.py，不另建搜索循环。

**接入步骤：** `adapter/__init__.py` 完整内容：

```python
from nsgablack.adapters.bayesian_optimization import (
    BayesianOptimizationAdapter, BayesianOptimizationConfig,
    FixedRBFConfig, FixedRBFPosterior,
    LowerConfidenceBound, GridAcquisitionOptimizer,
)
from nsgablack.units import UnitBinding
from nsgablack.representation.bayesian_builder import BayesianUnitBuilder


def build_adapter():
    model = FixedRBFPosterior(FixedRBFConfig(
        length_scale=0.25, variance=1.0,
        observation_variance=0.0, jitter=1e-8,
    ))
    return BayesianOptimizationAdapter(
        BayesianOptimizationConfig(initial_points=((0.0,), (1.0,))),
        model=model,
        acquisition=LowerConfidenceBound(beta=2.0),
        optimizer=GridAcquisitionOptimizer(grid=((0.25,), (0.5,), (0.75,))),
        unit_binding=UnitBinding(BayesianUnitBuilder()),
    )
```

`cases/synchronous_bo/build_solver.py` 完整内容：

```python
from pathlib import Path
from nsgablack.core import ComposableSolver
from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin
from nsgablack.project import apply_solver_component_overrides
from .adapter import build_adapter
from .bias import build_bias
from .config import BOCaseConfig
from .pipeline import build_pipeline
from .plugins import BOReport
from .problem import QuadraticProblem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    settings = BOCaseConfig(**{**dict(config or {}), **dict(overrides.pop("config", {}))})
    output = (Path(settings.output_dir) if settings.output_dir else
              Path(__file__).resolve().parents[2] / "results" / "synchronous_bo")
    solver = ComposableSolver(QuadraticProblem(), adapter=build_adapter(),
        representation_pipeline=build_pipeline(), bias_module=build_bias(settings.bias_weight),
        resource_context=resource_context, snapshot_strict=True, plugin_strict=True)
    solver.set_random_seed(13)
    solver.set_max_steps(settings.max_steps)
    solver.add_plugin(CheckpointResumePlugin(config=CheckpointResumeConfig(
        checkpoint_dir=str(output / "checkpoints"), save_every=settings.checkpoint_every,
        save_on_finish=True, keep_last=8,
        trusted_roots=(str((output / "checkpoints").resolve()),))))
    solver.add_plugin(BOReport(output))
    apply_solver_component_overrides(solver, overrides)
    return solver
```

Adapter 首次执行时按需建立 BayesianOptimizationUnit，先送评 initial_points。随后从本实例完整、已核对的 Evaluation Event 读取训练数据，用 `model.spawn()` 创建独立缓存并调用 fit(X,y)：X 是已评估坐标矩阵，y 是 raw 单目标向量。数据不从最后一批 accepted_refs 猜回，可包含有完整真实评估证据但未接纳的行。首版拒绝注册的 EvaluationProvider 和接管评估的 Plugin，不把近似结果冒充直接 Problem 观测。

GridAcquisitionOptimizer 调 `model.posterior(grid)`，LCB 返回 `mean-beta*std`，稳定 argmin 再交付 `(候选矩阵, 报告字典)`；不能只返回一个裸点。网格选点不调用 Problem，报告里的 acquisition 不是 raw 目标或 Bias 分数。选中的实际候选仍经 Pipeline/预算/求值/接纳；修复后的值才进入真实观测。固定 GP 不自动训练超参数，observation_variance 是协方差里的观测噪声项，不会给 Problem 增加随机噪声。

**怎样判断接对：** 读取本次 `results/synchronous_bo/report.json` 或同内容的 summary.json，核对 run_id 与标准 Case 终态。`observations[].x/y/violation/candidate_token/identity/event_ref` 对应真实评估证据；本 Problem 的 y 应满足平方公式。`model_revision` 是数据改变后的模型修订，不是求值次数；`observations` 是 Unit 的数据集，不等于当前接纳成员。

`last_acquisition.grid/mean/std/acquisition/selected_index` 说明最近一次选点：按索引取网格行，核对采集值是 LCB 公式。该报告保留当次提案时的预测，最终加入新观测后不会自动重写成最新 posterior。`raw_best` 是观测 y 的最小值；`evaluations/problem_calls/logical_steps/resource_binding_current` 供同次运行对账。Bias 可能改变 Solver 选择视图，但不能把模型 y 换成 Bias 值；Solver incumbent 也不等于最低 acquisition。

**运行入口：** 从仓库根目录使用已有单 Case 分组；包装脚本调用正式 execute_project，并记录实际 Project ArtifactBinding。

```powershell
python examples/cases/algorithm_semantics/run_and_report.py --group synchronous_bo --output results/bo_component_run.json
```

Project JSON 的 cases 中可核对该 Case 的 summary 发布与封存信息；本地 report/summary 文件不代替权威引用。配置变更后不要加载解释不同的旧 checkpoint。

### 变体一：让下一真实评估优先消除模型不确定性

**目的：** 需要优先补采模型最不确定的网格位置，暂时不按预测均值偏向低目标位置。这是换采集策略，不是修改 Problem。

**改在哪里：** 完整替换本节 adapter/__init__.py；builder 和报告插件不变，新增规则实际传入 acquisition。

```python
import numpy as np
from nsgablack.adapters.bayesian_optimization import (
    BayesianOptimizationAdapter, FixedRBFPosterior, GridAcquisitionOptimizer,
)
from nsgablack.units import UnitBinding
from nsgablack.representation.bayesian_builder import BayesianUnitBuilder


class HighestUncertainty:
    component_state_mode = "stateless"

    def describe(self):
        return {"type": "case.highest_latent_std/v1"}

    def __call__(self, mean, std):
        del mean
        return -np.asarray(std, dtype=float)


def build_adapter():
    return BayesianOptimizationAdapter(
        model=FixedRBFPosterior(), acquisition=HighestUncertainty(),
        optimizer=GridAcquisitionOptimizer(grid=((0.25,), (0.5,), (0.75,))),
        unit_binding=UnitBinding(BayesianUnitBuilder()),
    )
```

**行为变化：** 搜索器仍最小化 acquisition，因此 `-std` 选最大 std，平局沿网格顺序。报告 acquisition 应为负 std，不能再按 LCB 公式解释；mean 仍保留作观察，真实 y 仍来自原 Problem。

**限制：** 本例声明稳定 describe 和无状态语义，不支持内部计数器偷偷改变策略；有状态 acquisition 目前被 Adapter 拒绝。有限网格可能重复选择已观测点，不保证连续空间最优、信息增益最优或运行效果改善。

来源：[可替换组件](../../adapters/bayesian_optimization/components.py)、[真实消费者与组件约束](../../adapters/bayesian_optimization/adapter.py)、[观测来源](../../adapters/bayesian_optimization/evidence.py)、[正式 BOReport](../../examples/cases/algorithm_semantics/cases/synchronous_bo/plugins/__init__.py)。

## tool.cma_sampler · 把整批采样、raw 排名与分布更新装在一起

**什么时候用：** 要替换 CMA 的采样或分布更新，同时保持“同一分布下完整一批观测”的含义。本节共用 `tool.cma_sampler/tool.cma_ranking/tool.cma_update/tool.cma_unit`，不把更新后的均值当作已评估解。

**先准备什么：** 使用 algorithm_semantics 的 `cases/cmaes_distribution`。默认 fixture=None，原 Problem 接收二维向量并返回到 `(0.2,-0.1)` 的平方距离，raw 反馈 `(lambda,1)`、违反量 `(lambda,)`；原 IdentityRepair 不改变点。CMASettings 保留 seed=19、max_steps=3、evaluation_budget=None；Project L0 传 ResourceContext。fixture=scalar 时原 builder 选一维问题，工厂必须同步维度，下面保留这个实际分支。

**放在哪：** 替换 `cases/cmaes_distribution/adapter/__init__.py`，原 build_solver 调用 build_adapter(settings)。下面同时给出完整薄 builder，保留报告、checkpoint 与可选预算控制器。

**接入步骤：** `adapter/__init__.py`：

```python
from nsgablack.adapters.cmaes import (
    CMAESAdapter, CMAParameters, GaussianCohortSampler,
    StableObjectiveRanking, PositiveCMAUpdate,
)
from nsgablack.units import UnitBinding
from nsgablack.representation.cmaes_builder import CMAUnitBuilder


def build_adapter(settings):
    scalar = settings.fixture == "scalar"
    fixed = ([[[-1.], [0.], [1.], [2.]]] if scalar else
             [[[-1., 0.], [0., 1.], [1., 0.], [0., -1.]]]
             if settings.fixture == "matrix" else ())
    parameters = (CMAParameters(weights=(0.5, 0.5), cc=0.5, cs=0.5,
                               c1=0.25, cmu=0.25, damping=1.0)
                  if scalar else CMAParameters(population_size=4, parents=2))
    return CMAESAdapter(
        [0.] if scalar else [0., 0.], sigma=1.0 if scalar else 0.5,
        parameters=parameters,
        sampler=GaussianCohortSampler(settings.seed, fixed_batches=fixed),
        ranking=StableObjectiveRanking(), updater=PositiveCMAUpdate(parameters),
        unit_binding=UnitBinding(CMAUnitBuilder()),
    )
```

`cases/cmaes_distribution/build_solver.py`：

```python
from pathlib import Path
from nsgablack.core import ComposableSolver
from nsgablack.core.control_plane import BudgetController
from nsgablack.plugins import CheckpointResumeConfig, CheckpointResumePlugin
from nsgablack.project import apply_solver_component_overrides
from .adapter import build_adapter
from .config import CMASettings
from .pipeline import build_pipeline
from .plugins import DistributionReport
from .problem import QuadraticProblem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    settings = CMASettings(**{**dict(config or {}), **dict(overrides.pop("config", {}))})
    output = (Path(settings.output_dir) if settings.output_dir else
              Path(__file__).resolve().parents[2] / "results" / "cmaes_distribution")
    solver = ComposableSolver(QuadraticProblem(1 if settings.fixture == "scalar" else 2),
        adapter=build_adapter(settings), representation_pipeline=build_pipeline(),
        resource_context=resource_context, snapshot_strict=True, plugin_strict=True)
    solver.set_random_seed(settings.seed)
    solver.set_max_steps(settings.max_steps)
    if settings.evaluation_budget is not None:
        solver.register_controller(BudgetController(max_evaluations=settings.evaluation_budget))
    checkpoints = output / "checkpoints"
    solver.add_plugin(CheckpointResumePlugin(config=CheckpointResumeConfig(
        checkpoint_dir=str(checkpoints), save_every=1, keep_last=10, save_on_finish=True,
        trusted_roots=(str(checkpoints.resolve()),))))
    solver.add_plugin(DistributionReport(output))
    apply_solver_component_overrides(solver, overrides)
    return solver
```

工厂中的 mean 是 `(d,)`，sigma 是正标量，未传 covariance 时使用 `(d,d)` 单位阵。每次采样器 sample(lambda,d) 返回标准正态坐标 z；Adapter 按当前 covariance 与 sigma 变换为候选，不把 z 直接当 Problem 输入。lambda=4 是完整 cohort，parents=2 是更新使用的重组数量，不是只评估两行。

StableObjectiveRanking 读取完整 raw 单目标反馈，有限、无正违反量才接受，返回覆盖全部四行的稳定排序；同分保留提案顺序。PositiveCMAUpdate 接收脱离的分布、offsets 与完整 ranking，返回 mean/covariance/sigma/path_c/path_sigma/iteration/h_sigma。Adapter 验证整包推进再写自己的 CMAUnit，不由组件发布候选。Adapter 与 updater 共用同一 parameters，不能只改其中一边的 mu 或权重。

CMAUnit 在实际 propose 取分布时才按需创建。变更 repair 会破坏采样关系，当前 Adapter 明确拒绝；不要把 IdentityRepair 换成 Clip 后宣称同一分布仍成立。预算或硬接纳裁掉部分 cohort 也会拒绝更新，已发生求值成本保留，不会自动缩小 lambda 或跨步拼批。只换排名器也不能因此获得完整约束 CMA 策略。

**怎样判断接对：** 看 Project 的 `results/cmaes_distribution/summary.json`，核对本次 run_id 和最终状态。`mean/covariance/sigma/path_c/path_sigma/iteration` 是已提交分布，mean 尚未因“被算出来”就获得求值事实。`cohort_count` 是末批观测数，`selected_indices` 是末批原提案序号中的重组行，不是硬接纳索引或全部历史。`best_candidate/best_objective` 来自 Unit 保存的实际 raw 观测；不能用新 mean 覆盖它，也不能泛称它是任意 Bias 下 Solver incumbent。

`evaluations/problem_calls/logical_steps` 分开核对；分布迭代不等于候选求值行数。默认完整三步时每步四行，但不要用配置计算的12冒充本次实际回执；失败、预算截断应读真实结果。正式 summary 还由 DistributionReport 在 Case finalization transaction 发布，文件副本与 Project ArtifactBinding 分别核对。

**运行入口：** 用已有单 Case 分组，保留原 Project 资源与最终发布。

```powershell
python examples/cases/algorithm_semantics/run_and_report.py --group cmaes_distribution --output results/cma_component_run.json
```

### 变体一：固定第一批标准坐标，之后继续随机采样

**目的：** 排查一轮分布更新时，先固定可手算的标准正态坐标，再让后续轮次恢复普通采样；不是把整次优化改成固定答案列表。

**改在哪里：** 保留本节 adapter 的所有导入，完整替换 build_adapter。只用于默认二维 fixture=None；不要在一维问题上套二维前缀。

```python
def build_adapter(settings):
    if settings.fixture is not None:
        raise ValueError("this fixed-prefix recipe uses the default two-dimensional Case")
    parameters = CMAParameters(population_size=4, parents=2)
    fixed = (((-1., 0.), (0., 1.), (1., 0.), (0., -1.)),)
    return CMAESAdapter(
        [0., 0.], sigma=0.5, parameters=parameters,
        sampler=GaussianCohortSampler(settings.seed, fixed_batches=fixed),
        ranking=StableObjectiveRanking(), updater=PositiveCMAUpdate(parameters),
        unit_binding=UnitBinding(CMAUnitBuilder()),
    )
```

**行为变化：** 第一批 z 明确为 `(4,2)`；实际候选仍经当前均值、协方差和 sigma 变换。固定前缀消费完后 sampler 用自己的 seeded RNG 采样，游标与 RNG 随所属 Adapter 保存、回滚和恢复；solver.set_random_seed 不替代这个组件 seed。

**限制：** 固定批次 shape 必须同时匹配 lambda 与维度，否则拒绝。summary 只保存末批摘要；默认三步结束后不能把 selected_indices 当成第一批排名。要检查首批须有意识地设置 Case max_steps=1，并读这次新结果，不能在事后重跑 Problem 来伪造当时反馈。组件解释改变后不沿用旧 checkpoint。

来源：[采样/排名/更新组件](../../adapters/cmaes/components.py)、[完整 cohort 消费与拒绝边界](../../adapters/cmaes/adapter.py)、[CMAUnit 字段](../../units/cmaes.py)、[正式 DistributionReport](../../examples/cases/algorithm_semantics/cases/cmaes_distribution/plugins/__init__.py)。

## tool.map_descriptor · 描述符、格子、同格竞争与 emitter 必须一起接对

**什么时候用：** 希望保留不同行为区域的冠军，并分别替换“如何描述行为、如何定位格子、谁赢同格竞争、候选从哪里来”。主例和变体共同使用 `tool.map_descriptor/tool.map_cells/tool.map_competition/tool.map_sequence_emitter/tool.map_gaussian_emitter/tool.map_elites_unit`。

**先准备什么：** 使用 algorithm_semantics 的 `cases/map_elites_archive`。原 Problem 接收二维候选，最小化到 `(0.2,0.8)` 的平方距离；Pipeline 只做 `[0,1]` ClipRepair。ArchiveConfig 保留 seed=31、batch_size=5、max_steps=3；Project 提供 CPU ResourceContext。行为描述符不是 raw 目标，本例恰好用实际候选的两个坐标。结果目录默认是 Project 的 `results/map_elites_archive`。

**放在哪：** 替换 `cases/map_elites_archive/adapter/__init__.py` 并保留下方完整 build_solver；基线继续使用原 Pipeline、Problem 和 ArchiveSummary。变体会同时替换 pipeline/main.py，为随机 emitter 真正提供初始化来源。

**接入步骤：** `adapter/__init__.py` 完整内容：

```python
from nsgablack.adapters.map_elites import (
    MapElitesAdapter, MapElitesConfig, IdentityDescriptor,
    GridCells, MinimizeObjective, SequenceEmitter,
)
from nsgablack.units import UnitBinding
from nsgablack.representation.map_elites_builder import MapElitesUnitBuilder


def build_adapter(settings):
    return MapElitesAdapter(
        MapElitesConfig(batch_size=settings.batch_size, random_seed=settings.seed),
        descriptor=IdentityDescriptor(indices=(0, 1)),
        cells=GridCells(lower=(0., 0.), upper=(1., 1.), bins=(2, 2)),
        competition=MinimizeObjective(objective=0, tolerance=0.0),
        emitter=SequenceEmitter(((0.1, 0.1), (0.4, 0.4), (0.6, 0.4),
                                 (0.6, 0.8), (0.8, 0.2))),
        unit_binding=UnitBinding(MapElitesUnitBuilder()),
    )
```

`cases/map_elites_archive/build_solver.py`：

```python
from pathlib import Path
from nsgablack.core import ComposableSolver
from nsgablack.project import apply_solver_component_overrides
from .adapter import build_adapter
from .config import ArchiveConfig
from .pipeline import build_pipeline
from .problem import build_problem
from .plugins import ArchiveSummary


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    settings = ArchiveConfig(**{**dict(config or {}), **dict(overrides.pop("config", {}))})
    solver = ComposableSolver(problem=build_problem(), representation_pipeline=build_pipeline(),
        adapter=build_adapter(settings), resource_context=resource_context,
        plugin_strict=True, snapshot_strict=True)
    solver.set_random_seed(settings.seed)
    solver.set_max_steps(settings.max_steps)
    output = (Path(settings.output_dir) if settings.output_dir is not None else
              Path(__file__).resolve().parents[2] / "results" / "map_elites_archive")
    solver.add_plugin(ArchiveSummary(output))
    apply_solver_component_overrides(solver, overrides)
    return solver
```

SequenceEmitter.emit 交付至多 batch_size 个序列点，不评估、不竞争；它有自己的 cursor，由实际 Adapter 绑定保存，不能把同一个可变 emitter 实例交给多个所有者。序列耗尽后显式 exhausted=True，Adapter 返回 terminal，不制造空 generation。因此默认 max_steps=3 是上限，不要求五点序列一定提交三步。

MapElitesUnit 在 propose/update 真正需要档案时创建。候选经过 repair、求值和接纳后，Adapter 按精确 Pool 版本读取实际点与 raw feedback，再调用 descriptor.describe(candidate, feedback)、cells.locate(descriptor)、competition.quality(raw_objectives) 和 prefer。IdentityDescriptor 返回 `(2,)`，必须与 GridCells 的两维上下界/bins 对齐。内部格半开，上域边界1归最后格，越界 descriptor 拒绝，不静默夹入格子。

MinimizeObjective 先比较可行性与正违反量，再按指定 raw 目标判断同格优劣，完全并列保留已有冠军；tolerance 要求新质量严格低于旧质量减该值。它在硬接纳后决定档案留存，不替代接纳策略，不是 Bias，也不跨格做 Pareto 筛选。Unit 唯一保存冠军；Pool archive 视图只引用准确版本，不能通过写视图替换 Unit 决策。

**怎样判断接对：** 读取本次 `results/map_elites_archive/summary.json`。`cells/candidates/costs/refs` 同序，每个 cell 一名冠军；在两维各2格的配置中档案最多4个条目，不保证填满。costs 是指定 raw 质量，按原平方公式核对候选，不能用 cell 编号当目标。`components.archive_size/accepted_observations/archive_replacements` 分别是档案大小、接纳观测量与插入/替换次数；后者也统计原先空格的新冠军，不仅统计击败旧冠军。

`evaluations/problem_calls/logical_steps/run_id/pool_id` 用于同次运行对账，冠军数不等于累计求值量；SequenceEmitter 正常耗尽可以少于 max_steps。Solver incumbent 是另一个全局结果，不能代替所有格冠军。ArchiveSummary 在正式 finalization prepare 核对 Authority/Pool 并发布 summary，finalized 后写本地文件；run_and_report 记录实际 summary ArtifactBinding，旧文件不能证明本次发布。

**运行入口：** 使用已有单 Case 分组，不运行另两个独立 Case。

```powershell
python examples/cases/algorithm_semantics/run_and_report.py --group map_elites_archive --output results/map_component_run.json
```

### 变体一：从档案冠军产生随机后继，空档案由 Pipeline 提供种子

**目的：** 从有限演示点序列切换为持续从冠军附近采样；保留原描述符、格子和竞争规则，避免只换 emitter 却没有首批候选来源。

**改在哪里：** 完整替换本 Case 的 adapter/__init__.py 与 pipeline/main.py。原 pipeline/__init__.py 已导出 build_pipeline，builder 无需改变。

```python
from nsgablack.adapters.map_elites import (
    MapElitesAdapter, MapElitesConfig, IdentityDescriptor,
    GridCells, MinimizeObjective, GaussianArchiveEmitter,
)
from nsgablack.units import UnitBinding
from nsgablack.representation.map_elites_builder import MapElitesUnitBuilder


def build_adapter(settings):
    return MapElitesAdapter(
        MapElitesConfig(batch_size=settings.batch_size, random_seed=settings.seed),
        descriptor=IdentityDescriptor(indices=(0, 1)),
        cells=GridCells(lower=(0., 0.), upper=(1., 1.), bins=(2, 2)),
        competition=MinimizeObjective(objective=0, tolerance=0.0),
        emitter=GaussianArchiveEmitter(sigma=0.1),
        unit_binding=UnitBinding(MapElitesUnitBuilder()),
    )
```

`pipeline/main.py`：

```python
from nsgablack.representation import (
    RepresentationPipeline, UniformInitializer, ClipRepair,
)


def build_pipeline():
    return RepresentationPipeline(
        initializer=UniformInitializer(low=0.0, high=1.0),
        repair=ClipRepair(low=0.0, high=1.0),
    )
```

**行为变化：** 空档案时 emitter 调正式 init_population 取得 Pipeline 种子；有冠军后从档案随机选准确版本并加高斯扰动，随后仍走统一 repair/评估。修复可能改变行为格，按最终实际候选重新定位。GaussianArchiveEmitter 不声明有限序列 exhausted，结束仍由原 max_steps/预算等正式控制。

**限制：** 不能承诺档案覆盖或目标改善。新增 initializer 是真实必需接线，单独设置 emitter.sigma 不会生成空档案种子。描述符、格子或组件解释改动后不把旧档案 checkpoint 当成同一实验继续；首版 emitter 只有生成协议，不因能构造一个有反馈需求的 emitter 就自动接入其自适应 update。

来源：[四类组件及两个 emitter](../../adapters/map_elites/components.py)、[实际反馈与档案消费者](../../adapters/map_elites/adapter.py)、[MapElitesUnit](../../units/map_elites.py)、[正式 ArchiveSummary](../../examples/cases/algorithm_semantics/cases/map_elites_archive/plugins/__init__.py)。
