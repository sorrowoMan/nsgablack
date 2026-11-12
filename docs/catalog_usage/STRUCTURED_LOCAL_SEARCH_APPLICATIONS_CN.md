# 结构化局部搜索：方向权重、非光滑聚合、低维区域与模型筛选

以下四个配方分别修改四个既有正式 Project 的独立副本。所有代码只经源码核对，没有执行本页算法、拟合代理模型、调用外部模型或生成运行收据。它们共用求值、修复、池版本和提交事务，但不因此共享可写 Unit。

## structured.local.host · 四个正式 Case 共用的接线与观察

四节各使用自己的 Project：`trust_region_mo`、`trust_region_nonsmooth`、`trust_region_subspace`、`mas_search`，对应路径均为 `examples/cases/<project>/cases/<project>/`。复制整个 Project，保留原 project_config.py、run_project.py、L0、所有包目录及规范 Case 运行入口。原 default 组已调用同名唯一 Case，无需另造分组。下文文件路径均相对此 Case。

四个原演示 builder 都默认使用8维 Sphere，前三者只跑2步、MAS只跑1步；这不足以说明多目标、非光滑、子空间学习或模型筛选。下文显式替换 Problem、工厂和 builder，不把原演示已有 JSON 当作新配方的证据。

每个副本新建 `plugins/local_report.py`，完整内容：

```python
from collections import Counter
from pathlib import Path
from nsgablack.plugins.base import Plugin
from nsgablack.utils.engineering.file_io import atomic_write_json


class LocalSearchReport(Plugin):
    def __init__(self, search, output):
        super().__init__(name="local_search_report")
        self.search, self.output = search, Path(output)

    def on_solver_finish(self, result):
        control, search = self.solver, self.search
        refs = tuple(search.get_pool_refinement_results(control))
        if not refs:
            raise RuntimeError("the local search has no evaluated selected result")
        pool = control.solution_pool
        values = control.read_solutions(refs).numeric_matrix
        raw_f, raw_v = pool.read_raw_feedback(refs)
        state = search.get_state()
        selected = state.get("pool_refinement", state.get("pool_results"))
        details = {key: state[key] for key in (
            "center", "radius", "best_score", "weights", "basis", "steps",
            "sample_refs", "history_refs", "surrogate_present", "surrogate_fitted",
        ) if key in state}
        unit = getattr(search, "algorithm_unit", None)
        details["basis_method"] = getattr(unit, "basis_method", None)
        if "history_x" in state:
            details["history_count"] = len(state["history_x"])
        stages = Counter(record.get("transform_stage", "") for record in
                         pool.read_provenance(pool.select(stage="accepted")))
        self.payload = {
            "run_id": control.run_session.run_id,
            "evaluations": control.evaluation_count,
            "steps": control.run_progress_steps,
            "refs": [ref.as_dict() for ref in refs],
            "candidates": values.tolist(),
            "raw_objectives": raw_f.tolist(), "raw_violations": raw_v.tolist(),
            "selected": selected, "details": details,
            "accepted_transform_stages": dict(stages),
        }

    def on_solver_finalized(self, result):
        atomic_write_json(self.output, self.payload)
```

get_state 是正式状态导出，此处只摘取可解释字段；不会修改状态或构造 Unit。报告在 finishing 读取已提交选择，成功 finalized 通知后写本地文件；不是额外的权威 Artifact 或恢复信封。所有配方保持有界短运行，未启用闲置回收，才适合这里读取全部接纳来源的观察方式。

每个副本的 `build_solver.py` 都完整替换为：

```python
from pathlib import Path
from nsgablack.core import ComposableSolver
from .adapter.structured import build_adapter
from .pipeline import build_pipeline
from .plugins.local_report import LocalSearchReport
from .problem import build_problem


def build_solver(run_id=None, *, strategy=None, quickstart=False,
                 resource_context=None, component_overrides=None):
    if strategy not in (None, "", "none", "default") or component_overrides:
        raise ValueError("this recipe uses its explicit component factories")
    search = build_adapter()
    solver = ComposableSolver(
        problem=build_problem(), adapter=search,
        representation_pipeline=build_pipeline(), resource_context=resource_context,
        plugin_strict=True, snapshot_strict=True,
    )
    solver.set_random_seed(17)
    solver.set_max_steps(12)
    solver.add_plugin(LocalSearchReport(search,
        Path(__file__).resolve().parent / "results" / "local_search.json"))
    return solver
```

各节新建 `adapter/structured.py`，完整替换 `problem/__init__.py`；Pipeline 只替换原 `pipeline/main.py::build_pipeline`，保留 build_unit_binding/run_pipeline_slot，以保留原包导出。所有 Pipeline 工厂使用下面这份完整实现，其中边界与四节 Problem 的 `[-2,2]` 一致：

```python
def build_pipeline(*, resource_context=None, component_overrides=None):
    from nsgablack.representation import RepresentationPipeline, UniformInitializer, ClipRepair
    if component_overrides:
        raise ValueError("this recipe uses its declared problem pipeline")
    return RepresentationPipeline(
        initializer=UniformInitializer(-2., 2.), repair=ClipRepair(-2., 2.))
```

这些 Adapter 自己生成邻域，不消费 Pipeline mutator；多挂一个 GaussianMutation 不会自动替换它们的采样。本文不装配 `set_repair`：它表示 UnitRepair，不能用问题 ClipRepair 冒充。

**运行入口：** 进入各自 Project 副本根目录：

```powershell
python run_project.py --group default --check --build-check
python run_project.py --group default
```

第一条只执行构造检查。实际运行后读本次 `cases/<case_name>/results/local_search.json`，核对 run_id 与 Project 终态；失败不自动清除旧文件。本文未执行两条命令。配方不是对比四算法性能的基准，各自 Problem 不同。

## adapter.trust_region_mo_dfo · 固定方向的两目标局部搜索

**什么时候用：** 两个 raw 目标都需要保留，但本次局部搜索有明确权衡，例如80%侧重第一目标。这里是加权局部搜索，不自动输出完整 Pareto 前沿；ParetoArchivePlugin 若需要另行装配，不是此 Adapter 运作前提。

**先准备什么：** 使用共用接线节的 `trust_region_mo` Project 副本、当前 NumPy/nsgablack/blackbase。候选 `(2,)`、raw 反馈 `(n,2)`、违反量 `(n,)`。原8维单目标 Sphere 被下面的 TwoCenters 显式替换。

**放在哪：** 下方 Problem 是 `problem/__init__.py` 整文件，工厂是新增 `adapter/structured.py` 整文件。其余完整文件与运行入口使用共用接线节。

**接入步骤：**

```python
import numpy as np
from nsgablack.core import BlackBoxProblem


class TwoCenters(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="weighted_two_centers", dimension=2,
            bounds=[(-2., 2.)] * 2, objectives=["left_distance", "right_distance"])

    def evaluate(self, x):
        a = np.asarray(x, dtype=float)
        return np.array([(a[0] + 1.) ** 2 + a[1] ** 2,
                         (a[0] - 1.) ** 2 + a[1] ** 2])


def build_problem():
    return TwoCenters()
```

```python
from nsgablack.adapters import TrustRegionMODFOAdapter, TrustRegionMODFOConfig
from nsgablack.representation import RegionUnitBuilder
from nsgablack.units import UnitBinding


def build_adapter():
    return TrustRegionMODFOAdapter(
        name="weighted_local", unit_binding=UnitBinding(RegionUnitBuilder()),
        config=TrustRegionMODFOConfig(
            batch_size=6, initial_radius=.4, min_radius=1e-6, max_radius=1.,
            include_center=True, weight_method="fixed", fixed_weights=(.8, .2),
            radius_expand=1.5, radius_shrink=.7, success_tolerance=1e-8,
            random_seed=17,
        ))
```

真实配置字段是 weight_method/fixed_weights。权重必须有限、非负、长度等于目标数、总和正，随后归一化；它不是 MOEA/D 的100个方向槽位。RegionUnitBuilder 是实际传入的结构构建及 codec，构造 UnitBinding 不提前构造 Unit；中心、权重和反馈关联归本 Adapter 实例，半径适应仍归 Adapter。

先评估一个起点；之后每批6行含中心与5个盒内采样，原始目标保持两列，普通本地分数为 `.8*f0+.2*f1+1e6*violation`。中心自己也走送评，而不是免费复用旧结果。候选先裁到问题边界，统一问题 repair 后仍须在当前中心半径的无穷范数盒内；超出则整步拒绝，不能拿旧中心代价继续运行。问题边界与 ClipRepair 相同，本例裁剪不会把候选推到另一个区域。

改进超过 success_tolerance 才移动中心并扩大半径；否则收缩到 min_radius，下界不自动终止。历史最好可能比“满足移动容差”的当前中心略好，交付 get_pool_refinement_results 的精确已评估最好引用，不把 center 数值伪装成全部结果。

**怎样判断接对：** `local_search.json` 的 candidates 每行2维，raw_objectives 两列与公式相符、raw_violations 为0；details.weights 应是 `[.8,.2]`。selected.current/best 的 score 与权衡一致，details.radius 在配置范围内。该固定加权问题的已知极小点为 `(-.6,0)`，但12步不保证到达。Solver 最终 incumbent 默认按其自身目标聚合，可能与 Adapter 的加权选择不同；不要用 Solver 的目标和验证本地权重是否生效。

**运行入口：** 在 trust_region_mo Project 副本执行共用两条命令。本轮没有运行结果或收据。

### 变体一：每次普通更新采样一个新方向

**目的：** 让普通局部运行在不同方向间探索，同时正确重评分保留的历史目标向量。

**改在哪里：** 完整替换 `adapter/structured.py` 的 build_adapter，前面的 imports 和 Problem 保留。

```python
def build_adapter():
    return TrustRegionMODFOAdapter(
        name="changing_direction", unit_binding=UnitBinding(RegionUnitBuilder()),
        config=TrustRegionMODFOConfig(
            batch_size=6, initial_radius=.4, max_radius=1.,
            include_center=True, weight_method="dirichlet", random_seed=17,
        ))
```

**行为变化：** 普通运行改变方向时，当前/最好保留的 raw 选择目标向量在同一新权重下重评分，不能拿上轮标量直接比较。details.weights 是最后一个方向，不代表每轮都相同。**限制：** 不是完整方向档案；只保留算法声明的选择，不能事后保证找到了所有方向最优。作为原生 PoolTask 输入时本任务权重冻结；外部投影任务直接使用任务投影而非本地加权，不在此裸 Adapter 配方里隐式启动这些任务。

## adapter.trust_region_nonsmooth · 明确最小化绝对残差之和或最大值

**什么时候用：** 原目标含绝对值或最大值，需要不消费梯度的有界局部搜索。NonSmooth 的实质在本地目标聚合；它没有自动生成次梯度、光滑近似或严格的非光滑模型证明。

**先准备什么：** 共用 `trust_region_nonsmooth` Project 副本、NumPy/nsgablack/blackbase。候选 `(2,)`，Problem 返回两个**非负**绝对残差目标。本地 Linf 与 Solver 默认目标和可能有不同最优点。

**放在哪：** 替换 `problem/__init__.py`；新增完整 `adapter/structured.py`。统一 Pipeline、报告、薄 builder 与 Project L0 使用共用接线节。

**接入步骤：**

```python
import numpy as np
from nsgablack.core import BlackBoxProblem


class AbsoluteResiduals(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="absolute_residuals", dimension=2,
            bounds=[(-2., 2.)] * 2, objectives=["right_residual", "left_residual"])

    def evaluate(self, x):
        a = np.asarray(x, dtype=float)
        return np.array([abs(a[0] - 1.) + .1 * abs(a[1]),
                         abs(a[0] + 1.) + .1 * abs(a[1])])


def build_problem():
    return AbsoluteResiduals()
```

```python
from nsgablack.adapters import TrustRegionNonSmoothAdapter, TrustRegionNonSmoothConfig


def build_adapter():
    return TrustRegionNonSmoothAdapter(
        name="maximum_absolute_residual", config=TrustRegionNonSmoothConfig(
            batch_size=6, initial_radius=.4, min_radius=1e-6, max_radius=1.,
            score_mode="linf", include_center=True, success_tolerance=1e-6,
            radius_expand=1.3, radius_shrink=.7, random_seed=17,
        ))
```

真实字段为 score_mode，支持明确写 l1/linf。linf 算 `max(abs(objectives))`，l1 算 `sum(abs(objectives))`，再加违反量罚值。对于可为负的原始目标，取绝对值会改变原问题含义，不是通用的“最小化多个目标”；本例因此主动返回非负残差。

采样、单独基准、中心/半径适应、L∞盒内修复检查与前节共享正式实现。它不会调用 Pipeline mutator。共同 UnitRepair 若需要另按正式联合修复协议装配，不在此偷偷执行第二轮问题修复。

**怎样判断接对：** layout 为2维，raw反馈两列，零违反。报告 selected.current/best.score 应是两列最大值；details.best_score 表示当前中心分数，不是所有历史结果。已知 Linf 理想点 `(0,0)`，本地分数1；目标和的理想点包含整个 `x0∈[-1,1],x1=0`，不能用 Solver incumbent 落在此区间就证明 Linf 找到了平衡点。只验证公式和精确引用，不声称有限搜索收敛。

**运行入口：** trust_region_nonsmooth Project 副本的共用命令，检查本次 local_search.json。

### 变体一：明确改成 L1 总绝对残差

**目的：** 区分“照顾最坏残差”和“降低残差总量”。

**改在哪里：** 同一 adapter/structured.py 完整替换 build_adapter，保留其 imports 及 Problem。

```python
def build_adapter():
    return TrustRegionNonSmoothAdapter(
        name="sum_absolute_residuals", config=TrustRegionNonSmoothConfig(
            batch_size=6, initial_radius=.4, max_radius=1., score_mode="l1",
            include_center=True, random_seed=17,
        ))
```

**行为变化：** selected 分数改为两个绝对残差之和，最优集合变成上述区间；raw两列保持不变。**限制：** 不比较两个实验的 scalar score 数字大小来判断谁更好，它们的优化含义已经不同。外部投影 PoolTask 会使用其冻结标量与可行性次序，不再额外对投影结果取绝对值；本配方没有装配池任务，所以没有声称验证该路径。

## adapter.trust_region_subspace · 只用本算法实际接纳的样本建低维区域

**什么时候用：** 变量多，希望本次局部提案集中在一个低维线性子空间，并按本算法实际得到的样本定期更新基；不是读取任意全局 population 数组来猜方向。

**先准备什么：** 共用 `trust_region_subspace` Project 副本、当前 NumPy/nsgablack/blackbase。候选6维，单一非负各向异性平方目标；子空间秩2。PCA/SVD模式用NumPy，本文不启用额外 sklearn SparsePCA/KMeans 后端。

**放在哪：** `problem/__init__.py` 与新增 `adapter/structured.py` 完整代码如下；共享 builder/Pipeline/报告按接线节保存。

**接入步骤：**

```python
import numpy as np
from nsgablack.core import BlackBoxProblem


class AnisotropicBowl(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="anisotropic_bowl", dimension=6,
            bounds=[(-2., 2.)] * 6, objectives=["bowl_cost"])

    def evaluate(self, x):
        a = np.asarray(x, dtype=float)
        return float(a[0] ** 2 + 4. * a[1] ** 2 + .1 * np.sum(a[2:] ** 2))


def build_problem():
    return AnisotropicBowl()
```

```python
from nsgablack.adapters import TrustRegionSubspaceAdapter, TrustRegionSubspaceConfig
from nsgablack.representation import RegionUnitBuilder
from nsgablack.units import UnitBinding


def build_adapter():
    return TrustRegionSubspaceAdapter(
        name="pca_region", unit_binding=UnitBinding(RegionUnitBuilder()),
        config=TrustRegionSubspaceConfig(
            batch_size=6, initial_radius=.4, min_radius=1e-6, max_radius=1.,
            subspace_dim=2, basis_method="pca", min_samples=8, sample_limit=32,
            resample_every=2, include_center=True, random_seed=17,
        ))
```

先用起点建立已评估中心。样本不足8条时实际使用随机正交基；之后按刷新时机从 `_sample_refs` 指向的本任务已接纳候选建 PCA 基，最多保留32个精确引用。这里的样本是全部硬接纳试探，包括未成为中心者；不是“只用改善点”。历史按引用保存与回收根对齐，不把来源数值相等当作同一版本。

基为 `(6,2)`，采样 `center + radius * basis @ z`，z每坐标在[-1,1]。这是基坐标的L∞盒，不是半径为radius的欧氏球。遇边界时沿原射线缩短，避免逐坐标clip把点移出子空间。之后统一ProblemRepair若改变点，必须同时满足子空间残差和基坐标半径检查，否则拒绝。任意 repair 并不因此都可兼容。

本地普通分数为目标和加违反量罚值；支持投影任务的冻结比较，但本例未装配投影任务。RegionUnitBuilder 实际传入并负责基构造/codec；只有调度刷新属于Adapter。不保证从候选分布的PCA一定找到目标最敏感方向，也不是梯度主动子空间估计。

**怎样判断接对：** local_search.json 的 candidates 每行6维、raw单列与公式一致；details.basis为6×2，details.basis_method 初期可random，充足样本刷新后可pca；details.sample_refs不超过32。普通PCA/QR生成正交基，可另在自己的只读观察计算 B.T@B 核对接近2×2单位阵；本页没有执行这个数值断言。min_samples是参考阈值，不是评估器的固定批屏障，sample_limit必须至少覆盖min_samples。报告 selected.best 为实际已评估版本，不把基向量或中心方向当候选结果。

**运行入口：** trust_region_subspace Project 副本的共用命令。没有新增运行、恢复或几何数值验证收据。

### 变体一：持续使用随机子空间

**目的：** 在同一问题上移除数据驱动建基，单独观察随机区域和刷新频率的影响。

**改在哪里：** 完整替换 build_adapter，保留 imports、Problem、共享报告和Pipeline。

```python
def build_adapter():
    return TrustRegionSubspaceAdapter(
        name="random_region", unit_binding=UnitBinding(RegionUnitBuilder()),
        config=TrustRegionSubspaceConfig(
            batch_size=6, initial_radius=.4, max_radius=1., subspace_dim=2,
            basis_method="random", min_samples=8, sample_limit=32,
            resample_every=1, include_center=True, random_seed=17,
        ))
```

**行为变化：** 每轮邻域提案刷新随机基，details.basis_method保持random；不会因历史足够就切PCA。**限制：** 同seed不保证与主例相同轨迹，随机抽样次数已改变；k若设为6就不再降维，设为2也不保证12步覆盖所有变量方向。稀疏PCA/cluster路径可能回退PCA或随机基，不可仅看配置字符串判断实际方法。

## adapter.mas · 代理模型只筛候选，真实评估仍逐项发生

**什么时候用：** 想在局部随机探索中加入一个轻量拟合器，优先提交模型预测较好的点；它不是替代 Problem 的 EvaluationProvider，也不是把模型预测写进池 raw 反馈。

**先准备什么：** 共用 `mas_search` Project 副本、NumPy/nsgablack/blackbase，以及框架已声明的 scikit-learn CPU依赖。这里明确使用5近邻回归，不使用原默认200棵随机森林，不下载模型，不连接外部推理服务。候选2维，单目标。

**放在哪：** 下方 Problem 整体替换 `problem/__init__.py`，工厂是新增 `adapter/structured.py`，其余使用共用接线。原1步演示只建立基准，本配方的12步上限才允许达到拟合阈值并提出模型引导的后续批次。

**接入步骤：**

```python
import numpy as np
from nsgablack.core import BlackBoxProblem


class OffsetBowl(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="mas_offset_bowl", dimension=2,
            bounds=[(-2., 2.)] * 2, objectives=["offset_cost"])

    def evaluate(self, x):
        a = np.asarray(x, dtype=float)
        return float((a[0] - .4) ** 2 + 2. * (a[1] + .7) ** 2)


def build_problem():
    return OffsetBowl()
```

```python
from nsgablack.adapters import MASAdapter, MASConfig
from nsgablack.representation import ModelSearchUnitBuilder
from nsgablack.units import UnitBinding


def build_adapter():
    return MASAdapter(name="knn_assisted",
        unit_binding=UnitBinding(ModelSearchUnitBuilder()), config=MASConfig(
            batch_size=6, exploration_ratio=.5, enable_surrogate=True,
            surrogate_model_type="knn", surrogate_min_train_samples=5,
            surrogate_max_train_samples=32, surrogate_retrain_every_call=True,
            random_seed=17,
        ))
```

首步只评估一个起点；后续每批6个：3个探索点，另3个在模型未拟合前也按随机邻域产生。模型可用后，从9个内部候选预测值里挑3个提交。内部预测不是9次 Problem 求值；被挑出的6个仍走正式repair/evaluate/admission。探索和候选池噪声尺度当前固定为0.5，不消费Pipeline mutator或VNS sigma；模型筛选发生在最终边界裁剪之前，不能将预测排序当作裁剪后真实排序。

每次更新把本批分数最好者设为新中心，**不要求它优于旧中心**；历史最好另保存在selected.best并作为精确交付。拟合数据来自实际接纳反馈，X/Y/refs按相同窗口裁剪到32。本例无Bias且只有一个原目标，因此模型目标与raw一致；增加Bias后训练的是消费者收到的选择目标，不能自动宣称仍是raw代理。ModelSearchUnitBuilder 实际绑定并提供模型工厂，活模型不被塞进Unit codec；恢复按已保存历史重建/拟合，不把sklearn对象图deepcopy成checkpoint。

**怎样判断接对：** local_search.json 的候选2维、raw单列等于公式；details.history_count不超过32，history_refs同长；surrogate_present只表示已创建对象，surrogate_fitted才表示拟合状态。accepted_transform_stages若有mas_exploit，说明有该生成路径的候选被正式接纳，不证明预测准确。拟合/预测异常可能记录soft-error并回退，故不能只凭enable_surrogate=True或“样本数超过5”断言代理确实生效。selected.current可能比best差；交付refs对应best已评估候选，不拿当前center代替它。

**运行入口：** mas_search Project 副本的共用命令。本文没有训练近邻模型或执行该算法，不能把这些预期字段说成实测性能。

### 变体一：关闭代理，只保留同一中心移动规则

**目的：** 查看模型筛选这部分是否必要，避免同时更换整个算法或Problem。

**改在哪里：** 完整替换 build_adapter，前面的 imports 与Problem保留。

```python
def build_adapter():
    return MASAdapter(name="unassisted_search",
        unit_binding=UnitBinding(ModelSearchUnitBuilder()), config=MASConfig(
            batch_size=6, exploration_ratio=.5, enable_surrogate=False,
            surrogate_model_type="knn", surrogate_min_train_samples=5,
            surrogate_max_train_samples=32, random_seed=17,
        ))
```

**行为变化：** 不创建/训练代理，所有邻域提案走mas_explore；该实现关闭代理时也不积累训练历史，因此history_count为0，而不是继续采集32条待训练样本。**限制：** 同seed轨迹会因不再生成内部9点候选池而改变，不能据单次不同结果判断统计优越性。这里仍移动到每批最好者，不因此变成只接受改进的VNS。MAS支持普通/投影池精修，但本配方只装配裸Adapter；外部投影的标量含义和任务交还仍由PoolTask/Router正式声明。

实现依据：`adapters/trust_region_base/adapter.py`、`trust_region_mo_dfo/adapter.py`、`trust_region_nonsmooth/adapter.py`、`trust_region_subspace/adapter.py`、`mas/adapter.py`，`adapters/pool_results.py`、`representation/structure_builders.py`、`utils/surrogate/vector_surrogate.py`、`utils/surrogate/trainer.py`。可发现性只是索引，真实配置和行为以这些实现为准；本页不把源码核对当作运行收据。
