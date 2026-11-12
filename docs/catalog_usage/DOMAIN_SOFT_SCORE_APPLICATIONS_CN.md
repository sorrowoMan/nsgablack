# 领域 Bias：把偏好写成成本，并核对 raw 与选择反馈

本页实际同时装配 `PreferenceBias`、`RuleBasedBias`、`ConstraintBias` 和 `StructurePriorBias`。四者都只增加或减少选择分数；初始化、变化和生存决策仍由 NSGA-II 负责。下面按当前源码编写，没有执行文中算法、命令或外部模型，也没有生成运行收据。

## bias.preference · 四种软评分共用一条真实求值链

**什么时候用：** 原问题仍是二维平方和，但希望搜索兼顾接近一个偏好点、避免某些坐标区域、两个分量尽量接近。需要分别看见原始目标和额外代价，且保留之后把某条要求升级为硬约束的入口。

`bias.rule_based` 适合可明确写出条件和代价的规则；`bias.constraint` 汇总非负违反函数；`bias.structure_prior` 在明确坐标对或分组上计算结构差异。它们没有自动读取业务需求，也不会自行创建池、选择精英或修改 Unit。

**先准备什么：** 复制完整 `examples/cases/bias_gallery/` Project，在副本中修改本节文件。依赖当前 nsgablack、blackbase、NumPy；保留原 `project_config.py`、`run_project.py`、`cases/bias_gallery/__init__.py` 和规范 Case 运行入口。Project 的 default 组调用 bias_gallery，L0 发放 ResourceContext。原 `problem/example_problem.py::SphereProblem(dimension=2)` 接受 `(2,)` 候选，原始目标 `x0²+x1²`，没有硬约束。

**放在哪：** 新建本 Case 的 `bias/soft_scores.py`、`adapter/soft_search.py`、`pipeline/soft_pipeline.py`、`plugins/soft_report.py`，完整替换本 Case 的 `build_solver.py`。各包已有 `__init__.py`，以下均直接从子模块导入，不要求覆盖其旧注册表或导出。

**接入步骤：** 先用默认种群搜索提供候选，再用问题管线 ClipRepair 保证数值边界，Problem 给出 raw，四个 Bias 的标量和只加到选择目标。保留原有单一求值、接纳和提交事务，不在 Bias 内再调用 Problem。

`cases/bias_gallery/bias/soft_scores.py` 完整内容：

```python
import numpy as np
from nsgablack.bias import (
    BiasModule, PreferenceBias, RuleBasedBias, ConstraintBias, StructurePriorBias,
)


def preference_cost(x):
    return 0.25 * float(np.sum((np.asarray(x) - np.array([1., -1.])) ** 2))


def upper_excess(x):
    return max(0., float(x[0]) - 0.5)


def expected_costs(x):
    a, b = np.asarray(x, dtype=float)
    return dict(
        preference=preference_cost(x),
        rule_based=0.3 * max(0., -float(b)),
        constraint=3. * upper_excess(x),
        structure_prior=0.1 * abs(float(a - b)),
    )


def build_bias():
    module = BiasModule()
    module.cache_enabled = False
    preference = PreferenceBias(weight=1., preference_functions=[preference_cost])
    rules = RuleBasedBias(weight=1.)
    rules.add_rule(
        condition=lambda x, ctx: float(x[1]) < 0.,
        action=lambda x: 0.3 * max(0., -float(x[1])),
        priority=10, description="negative second coordinate has a soft cost",
    )
    constraint = ConstraintBias(weight=1., penalty_factor=3.)
    constraint.add_constraint(upper_excess, weight=1., constraint_type="hard")
    structure = StructurePriorBias(pairs=[(0, 1)], mode="pair", weight=0.1)
    for component in (preference, rules, constraint, structure):
        if not module.add(component):
            raise RuntimeError("cannot attach declared soft-scoring component")
    return module
```

这里的 `constraint_type="hard"` 是该旧类内部的**惩罚倍数标签**，只把 upper_excess 乘以 3。它不写 `raw_violations`，也不拒绝 `x0 > 0.5`。源码注释把 ConstraintBias 描述成“确保满足硬约束”，这个说法超出了实现；真正的硬语义必须在 Problem 与接纳策略定义，见变体二。

违反函数必须保持纯读取：该类在记录违反统计时还会再调用约束函数，本例 upper_excess 没有副作用。不要把数据库写入、预算扣减、随机抽样或候选修改藏在违反函数里，也不要把历史统计条数当作正式求值次数。

评分方向按源码理解：BiasModule 最终计算 `selection = raw + total_bias`，本例为最小化，正值是成本。PreferenceBias 的 `preference_functions` 返回值直接相加；它没有 CallableBias 的 `mode="reward"` 开关。因此这里主动返回非负距离成本。不能把“越喜欢越大”的奖励直接传进去。

权重也不能只看构造签名：PreferenceBias、RuleBasedBias、ConstraintBias 的 `compute` 内已乘 `self.weight`，共同基类 `compute_with_tracking` 又乘一次。当前实现这三类会出现权重平方；本例显式用 1，把所需系数写进函数或 penalty_factor。StructurePriorBias 的内置 pair/group 计算不乘 weight，基类再乘一次，本例只乘 0.1。这个差异是现有实现的限制，教程没有把它隐瞒成统一一次权重，也没有修改核心评分接口。`module.add(existing_bias, weight=...)` 不覆盖已有对象的权重；参数式 `weight` 只用于包装裸函数等路径。

`RuleBasedBias` 按 priority 从高到低遍历，**所有命中规则都累加**，不是首个命中返回或责任仲裁。这里仅用一个规则，避免把它误当成 if/elif。两个规则描述若相同，统计字典可能覆盖同名项，不宜用统计字典推导候选证据。

## bias.preference_installation · 接线、结果与两种改变

本节接续上节的四种 Bias 工厂，两个来源段落属于同一完整示例。

`cases/bias_gallery/adapter/soft_search.py` 完整内容：

```python
from nsgablack.adapters import NSGA2Adapter
from nsgablack.representation import UniformInitializer, GaussianMutation


def build_adapter():
    return NSGA2Adapter(
        name="soft_search", population_size=12, offspring_size=6,
        initializer=UniformInitializer(-5., 5.),
        mutator=GaussianMutation(sigma=0.3),
    )
```

`cases/bias_gallery/pipeline/soft_pipeline.py` 完整内容：

```python
from nsgablack.representation import RepresentationPipeline, ClipRepair


def build_pipeline():
    return RepresentationPipeline(repair=ClipRepair(-5., 5.))
```

直属初始化与变异由实际 Adapter 调用；管线只提供问题修复。Unit 仍由 Adapter 首次实际使用时创建，不在 builder、观察器或 Bias 工厂里提前 ensure_unit。这四个 Bias 只读当前候选，因而不必人为绑定一个参考种群。

`cases/bias_gallery/plugins/soft_report.py` 完整内容：

```python
import json
from pathlib import Path
import numpy as np
from nsgablack.plugins.base import Plugin
from ..bias.soft_scores import expected_costs


class SoftScoreReport(Plugin):
    def __init__(self, search, output):
        super().__init__(name="soft_score_report")
        self.search, self.output = search, Path(output)

    def on_solver_finish(self, result):
        control = self.solver
        refs = self.search.get_population_solution_refs(control)
        values = control.read_solutions(refs).numeric_matrix
        raw_f, raw_v = control.solution_pool.read_raw_feedback(refs)
        _, selection_f, selection_v = self.search.get_population_snapshot()
        components = [expected_costs(x) for x in values]
        expected = np.asarray([sum(row.values()) for row in components])
        actual = selection_f[:, 0] - raw_f[:, 0]
        self.payload = dict(
            run_id=control.run_session.run_id,
            evaluations=control.evaluation_count,
            refs=[ref.as_dict() for ref in refs],
            candidates=values.tolist(), raw_objectives=raw_f.tolist(),
            raw_violations=raw_v.tolist(),
            selection_objectives=selection_f.tolist(),
            selection_violations=selection_v.tolist(),
            expected_components=components,
            delta_matches=bool(np.allclose(actual, expected, rtol=1e-9, atol=1e-9)),
        )

    def on_solver_finalized(self, result):
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(json.dumps(self.payload, ensure_ascii=False,
            allow_nan=False, indent=2), encoding="utf-8")
```

报告只重算本例四条无状态公式，不再次调用 Bias.compute、Problem 或 Provider，避免改变调用统计。它按同一组精确成员引用读取 raw，再与该成员当时的选择反馈对齐。这里没有代际调度/动态参考；若增加它们，不能用最后一代参数反算历史选择分数。

`cases/bias_gallery/build_solver.py` 完整内容，只负责接线：

```python
from pathlib import Path
from nsgablack.core import ComposableSolver, FeasibleEvaluationAcceptance
from .adapter.soft_search import build_adapter
from .bias.soft_scores import build_bias
from .pipeline.soft_pipeline import build_pipeline
from .plugins.soft_report import SoftScoreReport
from .problem.example_problem import SphereProblem


def build_solver(run_id=None, *, strategy=None, quickstart=False,
                 resource_context=None, component_overrides=None):
    if strategy not in (None, "", "default", "none") or component_overrides:
        raise ValueError("this guide uses its explicitly declared components")
    search = build_adapter()
    solver = ComposableSolver(
        problem=SphereProblem(dimension=2), adapter=search,
        representation_pipeline=build_pipeline(), resource_context=resource_context,
        plugin_strict=True, snapshot_strict=True,
        evaluation_acceptance_policy=FeasibleEvaluationAcceptance(),
    )
    solver.set_random_seed(17)
    solver.set_max_steps(6)
    solver.set_bias_module(build_bias(), enable=True)
    solver.add_plugin(SoftScoreReport(search, Path(__file__).resolve().parents[2]
                                    / "results" / "soft_scores.json"))
    return solver
```

默认 `ignore_constraint_violation_when_bias` 即便将选择违反量软化，FeasibleEvaluationAcceptance 仍读取原始违反量；本例无硬约束，raw 违反量全为 0，因此该门不限制候选。不能通过这例声称已验证了有约束过滤。初始化和后续变化都走正式送评流程；不用手写优化循环，也不把池里的历史分数当新评估。

**怎样判断接对：** 从本次 Project 的终态开始，读取 `results/soft_scores.json` 并核对 run_id。每行 raw 目标应为候选平方和；raw_violations 应为 0。selection_objectives 应等于 raw 加上 expected_components 四项，delta_matches 应为 true。成员顺序、refs 和反馈行必须一致。即使最后没保留 `x0 > 0.5`，也不能据此推断软惩罚实现了硬拒绝；有限随机预算同样不保证收敛到某个精确坐标。Solver incumbent、NSGA2 最终成员和未被选中的已接纳历史是不同结果面，不互相代替。

**运行入口：** 在复制的 Project 根目录执行下面命令。第一条构建检查只检查装配，不证明评分行为；第二条才会实际求解。本轮没有执行它们。

```powershell
python run_project.py --check --build-check
python run_project.py
```

报告在成功最终发布通知后才写本地 JSON，不是独立 Authority 或可传输 checkpoint。失败时旧 JSON 不会自动消失，须看本轮 run_id；发布后观察文件写入失败也不能解释为算法步骤回滚。

### 变体一：把“接近偏好点”改成有界奖励

**目的：** 明确奖励也能表达，但必须给最小化选择视图一个负增量，而不是假定类名自动翻转方向。

**改在哪里：** 仅替换 `bias/soft_scores.py` 的 preference_cost；build_bias、expected_costs 和报告都会复用它，不另改工厂。

```python
def preference_cost(x):
    distance2 = float(np.sum((np.asarray(x) - np.array([1., -1.])) ** 2))
    return -0.5 / (1. + distance2)
```

**行为变化：** preference 项进入 `[-0.5,0)`，接近 `(1,-1)` 时选择成本降得更多；raw 平方和不变。delta_matches 仍应成立，但 selection 可以小于 raw。保存两次不同 run_id 的报告比较，不能拿“选择分数更小”当“原问题目标一定更好”。

**限制：** 仍是软偏好，不改变硬可行性；奖励的尺度要与原目标量纲一起判断。此函数不读取 context.metrics，也不自动给每个目标单独设置愿望水平。PreferenceBias 的 aspiration_levels 会读取 `metrics['obj_<name>']`，缺失时使用 0；标准求值链不保证自动提供这些特定名字，本例因此没有使用该入口。

### 变体二：把 x0 上限升级成真正硬条件

**目的：** 允许 Problem 定义 `x0 <= 0.5`，由原始违反量控制能否进入 Adapter 更新；软偏好仍独立存在。

**改在哪里：** 新建 `cases/bias_gallery/problem/limited_sphere.py`，完整内容如下；在本节 builder 将 SphereProblem 的导入改为最后所示导入，其它代码保持原样。先使用主例的 preference_cost，避免同时改变两个因素。

```python
import numpy as np
from .example_problem import SphereProblem


class LimitedSphere(SphereProblem):
    def evaluate_constraints(self, candidate):
        x = np.asarray(candidate, dtype=float)
        return np.array([max(0., float(x[0]) - 0.5)])
```

builder 的替换导入为：

```python
from .problem.limited_sphere import LimitedSphere as SphereProblem
```

**行为变化：** 评估仍会发生，违反上限的提案消耗求值但被 FeasibleEvaluationAcceptance 拒绝，不进入最终成员。部分接纳经 BatchDisposition 对齐，未接纳行不被伪装成未评估。正常完整初始化后，最终成员 `x0 <= 0.5 + 1e-9`，raw_violations 不超过接纳容差。Bias 的 constraint 项可能在极小容差区间有非零值；它不负责宣布可行，也不把 raw 改成 0。

**限制：** ClipRepair 仍只裁剪到 `[-5,5]`，不会主动修到半平面；严格接纳可能让初始化需要更多尝试，不能保证每次都填满 12 个成员。这个变体是在同一正式求值事务上换 Problem，不会让 ConstraintBias 的 `mandatory` 或 `constraint_type` 变成准入权限。需要直接修复到半平面时，应另写并验证 ProblemRepair，不能偷偷在 Bias 中改候选。

源码对照：`bias/domain/constraint.py`、`bias/domain/structure_prior.py`、`bias/core/base.py::compute_with_tracking`、`bias/core/manager.py`、`bias/bias_module.py`、`core/solver_helpers/bias_helpers.py`、`core/evaluation_acceptance.py` 与 `examples/cases/bias_gallery/project_config.py`。关于权重、ConstraintBias 的“硬”标签及 aspiration 缺省值的限制，均来自实际实现，不是通用算法结论。
