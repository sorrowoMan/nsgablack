# 两种选择视图：显式增量与方向投影

PreferenceDelta解释某个原目标坐标加了什么软偏好；ObjectiveProjection解释一组原目标如何变成局部比较坐标。两者都不改变候选身份、Problem定义或池中的raw反馈。本页只做源码与静态核对，没有执行算法、模型或外部服务。

## core.preference_delta · 实际声明并消费增量，而不是创建一个孤立值

**什么时候用：** 需要给每次软评分写出可审计的key/delta/reason；用户能从报告回答“为什么这个点的选择分数不同于原始评估”。它不是选择器、repair、候选生成器或硬约束。

**先准备什么：** 完整复制 `examples/cases/bias_gallery` Project，保留default/main/bias_gallery、Project L0、规范入口和包。用二维数值Problem，原始sphere成本与一个独立硬限制；不绑定任何算法Unit，因此这是候选本身的软偏好，不冒充群体多样性。

**放在哪：** 下列路径相对cases/bias_gallery。新增完整Problem/Pipeline/Bias/Report文件，完整替换builder；不把PreferenceDelta对象直接add到普通BiasModule。

**接入步骤：**

```python
# problem/delta_sphere.py
import numpy as np
from blackbase.types import Feedback
from nsgablack.core import BlackBoxProblem


class DeltaSphere(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="explicit_delta_sphere", dimension=2,
            bounds=[(-2., 2.)]*2, objectives=["sphere"])

    def evaluate(self, x):
        a = np.asarray(x, dtype=float)
        return Feedback(objectives=[float(a @ a)], metrics={"case.delta_x": a.tolist()})

    def evaluate_constraints(self, x):
        return [max(0., float(np.asarray(x)[0]) - .5)]
```

```python
# pipeline/delta_pipeline.py
from nsgablack.representation import (RepresentationPipeline,
    UniformInitializer, GaussianMutation, ClipRepair)


def build_pipeline():
    return RepresentationPipeline(initializer=UniformInitializer(-2., 2.),
        mutator=GaussianMutation(sigma=.25), repair=ClipRepair(-2., 2.))
```

```python
# bias/explicit_delta.py
import numpy as np
from blackbase.preferences import PreferenceDelta

CENTER = 1.


class CenterCostPreference:
    name = "case_center_cost"
    preference_keys = ("objectives.0",)
    context_requires = context_provides = context_mutates = context_cache = ()

    def __init__(self, weight=.3):
        self.weight, self.center = float(weight), CENTER

    def preferences(self, candidate, feedback, context):
        x = np.asarray(candidate, dtype=float)
        return (PreferenceDelta("objectives.0", self.weight * float((x[0]-self.center)**2),
            f"soft coordinate preference toward x0={self.center}"),)
```

该对象结构上满足blackbase.PreferenceProvider：声明可写preference_keys，返回PreferenceDelta序列。正式project_bias_feedback识别这个Protocol，对已声明的objectives.N加delta，再保留第一份raw_evaluation和增量链。每个delta必须finite且reason非空；未声明key、越界目标或伪造约束写入会被拒绝。不会把 `PreferenceDelta(...)` 当一个自动执行评分的组件。

本例正delta是最小化成本：越靠近center越少加罚；不是正奖励，也不是两次乘weight。原始sphere和硬x0<=.5保持自己的事实；center=1故意在硬限制外，偏好不能因此打开raw接纳门。repair只修复盒边界，硬业务限制由Problem与FeasibleEvaluationAcceptance守住。

Case的context_keys.json合并以下声明，保留已有其它键。报告与完整builder在下一节，一起保存后才是可装配Case。

```json
["metrics.case.delta_x"]
```

**怎样判断接对：** 每个最后送评行应满足selection=raw+.3*(x0-center)²，info.preference_deltas准确记录objectives.0及reason。raw_violation>0行即使选择分数较好也不能成为接纳成员；成员顺序读NSGA真实refs。空接纳不制造逻辑代，也不抹掉已发生评估。

**运行入口：** 保存下一节文件后，副本根 `python run_project.py --check --build-check` 再 `python run_project.py`，读取results/explicit_delta.json。六步只是教学上限，没有本轮运行或收敛声明。

### 变体一：偏好中心改到硬限制内部

**目的：** 区分软目标与硬接纳，即使两者方向一致也保持独立。

**改在哪里：** bias/explicit_delta.py只替换常量，下一节报告从实际实例读center，不要保留旧常量公式。

```python
CENTER = -.5
```

**行为变化：** 软成本转为靠近-.5较小；硬限制仍x0<=.5。**限制：** 不改变Problem最小点、不保证最终最优或可行成员已经填满容量；需要实际运行验证。

## core.preference_host · 完整报告与薄builder

```python
# plugins/delta_report.py
import numpy as np
from nsgablack.plugins.base import Plugin
from nsgablack.utils.engineering.file_io import atomic_write_json


class DeltaReport(Plugin):
    def __init__(self, search, preference, output):
        super().__init__(name="explicit_delta_report")
        self.search, self.preference, self.output = search, preference, output

    def on_solver_finish(self, result):
        control = self.solver
        batch = control.get_last_feedback_batch()
        rows = []
        if batch is not None:
            for i, item in enumerate(batch.items):
                x = np.asarray(item.metrics["case.delta_x"], dtype=float)
                expected = self.preference.weight * float((x[0]-self.preference.center)**2)
                rows.append({"x": x.tolist(), "raw": batch.raw_objectives[i].tolist(),
                    "raw_violation": float(batch.raw_violations[i]),
                    "selection": batch.objectives[i].tolist(),
                    "deltas": list(item.info.get("preference_deltas", ())),
                    "matches": bool(np.isclose(batch.objectives[i, 0]-batch.raw_objectives[i, 0], expected))})
        refs = tuple(self.search.get_population_solution_refs(control) or ())
        raw_f, raw_v = control.solution_pool.read_raw_feedback(refs) if refs else (None, None)
        self.payload = {"run_id": control.run_session.run_id, "last_rows": rows,
            "member_refs": [ref.as_dict() for ref in refs],
            "member_raw": None if raw_f is None else raw_f.tolist(),
            "member_raw_violations": None if raw_v is None else raw_v.tolist()}

    def on_solver_finalized(self, result):
        atomic_write_json(self.output, self.payload)
```

```python
# build_solver.py
from pathlib import Path
from nsgablack.adapters import NSGA2Adapter
from nsgablack.core import ComposableSolver, FeasibleEvaluationAcceptance
from nsgablack.project import apply_solver_component_overrides
from .bias.explicit_delta import CenterCostPreference
from .pipeline.delta_pipeline import build_pipeline
from .plugins.delta_report import DeltaReport
from .problem.delta_sphere import DeltaSphere


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config:
        raise ValueError("edit explicit delta recipe factories")
    search = NSGA2Adapter(name="population", population_size=6,
        offspring_size=4, crossover_rate=0.)
    preference = CenterCostPreference(weight=.3)
    solver = ComposableSolver(problem=DeltaSphere(), representation_pipeline=build_pipeline(),
        adapter=search, resource_context=resource_context,
        evaluation_acceptance_policy=FeasibleEvaluationAcceptance())
    solver.set_bias_module(preference, enable=True)
    solver.set_random_seed(17)
    solver.set_max_steps(6)
    solver.set_max_step_attempts(24)
    solver.add_plugin(DeltaReport(search, preference,
        Path(__file__).resolve().parents[2] / "results" / "explicit_delta.json"))
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

这里的PreferenceProvider是软偏好协议，不是评估Provider或Plugin，也不拥有Unit；构造常量由Case固定，没有可变历史。若以后加历史/随机记忆，必须额外实现实际状态生命周期，不能从本例无状态对象推断已支持恢复。报告在finalized后写入，旧观察文件不证明本次成功，先核对Case/run_id。

源码：blackbase/preferences.py的PreferenceDelta/PreferenceProvider/preserve_feedback_evidence，nsgablack/core/solver_helpers/bias_helpers.py的声明校验与投影，core/evaluation_acceptance.py的raw门。

## core.objective_projection · MOEA/D方向发布与两层精修的真实应用

**什么时候用：** 多目标Problem不变，但每个方向的局部算法需要按固定权重/参考点比较。投影是一个明确可传输的比较框架，不是新Problem或把母池目标永久压成一维。

**先准备什么：** 完整复制 `examples/cases/assembly_workbench` Project，保留DirectionsConfig、directions Case的Problem/Pipeline、原DirectionTrace、所有包与Project L0。只运行directions组，不运行default的其它优化和真正内层Case。候选x是一维，raw目标为 `[(x-1)²,(x+1)²]`，原始约束abs(x)<=2。DirectionsConfig默认3方向、bootstrap2步、local2步、router_budget6；不要只复制工厂。

**放在哪：** 完整替换cases/directions/adapter/composition.py；下一节给完整builder及观察插件。保留原pipeline的ClipRepair(-2,2)和problem/two_targets.py。默认按三个方向串行粗精修→细精修→返回竞争。

**接入步骤：**

```python
# cases/directions/adapter/composition.py
from nsgablack.adapters import (MOEADAdapter, VNSAdapter, PatternSearchAdapter,
    SearchPlanAdapter, StrategySpec, MultiStrategyConfig, PoolTaskSpec,
    subpools, serial, stage)
from nsgablack.representation import UniformInitializer, GaussianMutation, ContextGaussianMutation

DECOMPOSITION = "tchebycheff"


def fine_results(control, context):
    return control.adapter.get_pool_task_results(control, "fine")


def build_adapter(settings):
    moead = MOEADAdapter(name="direction_owner", population_size=settings.directions,
        batch_size=3, neighborhood_size=3, decomposition=DECOMPOSITION,
        random_seed=settings.seed, initializer=UniformInitializer(-2., 2.),
        mutator=GaussianMutation(sigma=.3))
    coarse = VNSAdapter(name="coarse_vns", batch_size=1, base_sigma=.35,
        restart_on_stagnation=False, mutator=ContextGaussianMutation(base_sigma=.35))
    fine = PatternSearchAdapter(name="fine_pattern", max_directions=1, step_size=.08)
    return SearchPlanAdapter(serial(
        stage("moead", steps=settings.bootstrap_steps, label="search"),
        stage("coarse"), stage("fine"), stage("moead", label="return")),
        strategies=[
            StrategySpec(moead, "moead", pool_task=PoolTaskSpec(fine_results,
                mode="compete", phases=("return",), count="all", shuffle=False)),
            StrategySpec(coarse, "coarse", pool_task=PoolTaskSpec(subpools.all(moead),
                count=1, steps=settings.local_steps, output=None, shuffle=False)),
            StrategySpec(fine, "fine", pool_task=PoolTaskSpec(subpools.all(coarse),
                count=1, steps=settings.local_steps, output=None, shuffle=False))],
        config=MultiStrategyConfig(total_batch_size=settings.router_budget, adapt_weights=False),
        name="direction_plan")
```

MOEA/D按自己的已评估成员发布方向视图，metadata.projection是ObjectiveProjection.as_dict；created_by是实例所有权路径。VNS任务开始冻结各方向引用/权重/参考点，基准和新邻域都按同一个投影。细精修读coarse发布的派生视图，继承同一比较框架，不再次套一层标量化。SearchPlan的前后屏障保留，all不是等待或“无限可读”授权。

`weighted_sum`是F@weights；`tchebycheff`是max(abs(F-reference)*weights)。ObjectiveProjection本身不自动归一权重；MOEA/D的方向生成决定自己的权重。Tchebycheff需要同维有限reference，weighted_sum不接受reference。apply拒绝带subpool_projection标记的重复投影，保留第一份raw_objectives/raw_violations；约束按可行性比较，不加入标量目标混淆含义。这里完全没有把1维分数回写母池两列目标。

**怎样判断接对：** 原DirectionTrace的summary.json中views、tasks、result_receipts、final_results与final_population都有真实来源。最终母池raw两列，方向projection参数按视图显示；接回MOEA/D时使用**当前**子问题规则竞争，不拿冻结的旧参考点替换当前ideal。下一节ProjectionAudit只做已保存raw值上的算术核对，不重新求值，不送回Adapter，也不构造新候选。

**运行入口：** 副本根 `python run_project.py --group directions --check --build-check`，再 `python run_project.py --group directions`。读取results/directions/summary.json与projection_audit.json；本轮未运行。

### 变体一：方向改用加权和，其它交接保持一致

**目的：** 改MOEA/D和自动发布视图共同使用的真实比较规则，而不只改观察器公式。

**改在哪里：** 同composition.py只改常量。

```python
DECOMPOSITION = "weighted_sum"
```

**行为变化：** 所有该实例新发布方向的method变为weighted_sum、reference为空，VNS与细精修实际消费该解释。**限制：** 这会改变搜索语义，不保证更好；旧tchebycheff checkpoint与新规则不可混用，不把线性权重当作任意非凸Pareto面的覆盖保证。

## core.projection_host · 完整装配与只读投影算术审计

新建cases/directions/plugins/projection_audit.py。这里实际使用ObjectiveProjection.from_dict/apply；构造的临时Feedback只是对已读raw做独立算术检查，不代表再次执行Problem，也没有成为新EvaluationEvent或发布目标。

```python
from pathlib import Path
import numpy as np
from blackbase.types import Feedback
from nsgablack.core import ObjectiveProjection
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.adapters.subpools import adapter_path
from nsgablack.plugins.base import Plugin
from nsgablack.utils.engineering.file_io import atomic_write_json


class ProjectionAudit(Plugin):
    def __init__(self, owner, output_dir):
        super().__init__(name="projection_arithmetic_audit")
        self.owner, self.output_dir = owner, Path(output_dir)

    def on_solver_finish(self, result):
        control, rows = self.solver, []
        pool = control.solution_pool
        path = adapter_path(control.adapter, self.owner)
        for name in pool.subpools_created_by(path):
            metadata = pool.subpool_metadata(name)
            projection = ObjectiveProjection.from_dict(metadata["projection"])
            refs = tuple(pool.subpool_refs(name))
            raw_f, raw_v = pool.read_raw_feedback(refs)
            saved = OptimizationFeedbackBatch.from_feedback(
                tuple(Feedback(objectives=row) for row in raw_f), violations=raw_v)
            projected = projection.apply(saved)
            w = np.asarray(projection.weights)
            expected = (raw_f @ w if projection.method == "weighted_sum" else
                np.max(np.abs(raw_f-np.asarray(projection.reference))*w, axis=1))
            rows.append({"view": name, "descriptor": pool.subpool_descriptor(name),
                "projection": projection.as_dict(), "refs": [r.as_dict() for r in refs],
                "raw": raw_f.tolist(), "score": projected.objectives.tolist(),
                "matches": bool(np.allclose(projected.objectives[:, 0], expected)),
                "raw_retained": bool(np.array_equal(projected.raw_objectives, raw_f)),
                "violations_retained": bool(np.array_equal(projected.raw_violations, raw_v))})
        self.payload = {"run_id": control.run_session.run_id, "current_direction_views": rows}

    def on_solver_finalized(self, result):
        atomic_write_json(self.output_dir / "projection_audit.json", self.payload)
```

这里审计的是结束时MOEA/D**当前**方向视图。PoolTask结果收据里的冻结projection可能来自更早参考点，应由原DirectionTrace单独呈现；两者数值不同不能据此误报任务投影失效。

完整替换cases/directions/build_solver.py，保留原正式strict发布观察器，不把新的JSON替代原summary Artifact：

```python
from pathlib import Path
from nsgablack.core import ComposableSolver
from nsgablack.plugins import ParetoArchivePlugin
from nsgablack.project import apply_solver_component_overrides
from .adapter.composition import build_adapter
from .config import DirectionsConfig
from .pipeline import build_pipeline
from .plugins import DirectionTrace
from .plugins.projection_audit import ProjectionAudit
from .problem import build_problem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    overrides = dict(component_overrides or {})
    settings = DirectionsConfig(**{**dict(config or {}), **dict(overrides.pop("config", {}))})
    if settings.refinement_layout != "serial" or settings.direction_sample is not None:
        raise ValueError("this recipe explicitly uses all directions and serial refiners")
    output = (Path(settings.output_dir) if settings.output_dir is not None else
        Path(__file__).resolve().parents[2] / "results" / "directions")
    root = build_adapter(settings)
    owner = next(unit.adapter.inner for unit in root.units if unit.role == "moead")
    solver = ComposableSolver(problem=build_problem(), representation_pipeline=build_pipeline(),
        adapter=root, resource_context=resource_context, plugin_strict=True, snapshot_strict=True)
    solver.set_bias_module(None, enable=False)
    solver.set_random_seed(settings.seed)
    solver.set_max_steps(settings.max_steps)
    solver.add_plugin(ParetoArchivePlugin())
    solver.add_plugin(DirectionTrace(output_dir=output, settings=settings))
    solver.add_plugin(ProjectionAudit(owner, output))
    apply_solver_component_overrides(solver, overrides)
    return solver
```

Probe不调用builder/ensure_unit，不持有可写Unit或将另一算法结构搬入自己的作用域。ProjectionAudit JSON是观察产物，summary仍由原DirectionTrace在正式Case finalization中发布。旧结果文件必须核对本次run_id；源码核对不等于行为运行验收。

源码：core/state/pool_views.py、adapters/moead/adapter.py的_publish_direction_views/_g、adapters/pool_tasks.py的冻结任务/继承投影/最终收据，assembly_workbench/directions原factory/config/trace。
