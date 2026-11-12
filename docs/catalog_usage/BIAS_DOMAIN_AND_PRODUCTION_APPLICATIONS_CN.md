# 工程、生产与场景波动：先说明数据源，再解释软成本

每节使用 `examples/cases/bias_gallery` 完整Project的独立副本，互不叠加同名文件。原default组、Project L0和规范Case入口保持。以下只做源码核对，未执行算法、场景采样、模型或命令；实际可用主例与旧类迁移分别标注。

## domain.shared_report · 共用成员与最后反馈报告

以下路径相对 `cases/bias_gallery/`。每个主例提供 `problem/domain.py`、`bias/domain_scores.py`、`pipeline/domain_pipeline.py` 完整文件；新增 `plugins/domain_report.py`：

```python
import json
import numpy as np
from nsgablack.plugins.base import Plugin
from nsgablack.utils.engineering.file_io import atomic_write_text
from ..bias.domain_scores import expected_delta


def json_value(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"not a numeric report value: {type(value).__name__}")


class DomainReport(Plugin):
    def __init__(self, search, output):
        super().__init__(name="domain_bias_report")
        self.search, self.output = search, output

    def on_solver_finish(self, result):
        control = self.solver
        refs = tuple(self.search.get_population_solution_refs(control) or ())
        if refs:
            raw_f, raw_v = control.solution_pool.read_raw_feedback(refs)
            _, selected_f, selected_v = self.search.get_population_snapshot()
            members = dict(candidates=control.read_solutions(refs).numeric_matrix.tolist(),
                raw_objectives=raw_f.tolist(), raw_violations=raw_v.tolist(),
                selection_objectives=selected_f.tolist(), selection_violations=selected_v.tolist())
        else:
            members = None
        last = control.get_last_feedback_batch()
        last_payload = None
        if last is not None:
            expected = [expected_delta(item) for item in last.items]
            last_payload = dict(
                raw=last.raw_objectives.tolist(), selection=last.objectives.tolist(),
                raw_violations=last.raw_violations.tolist(),
                metrics=[dict(item.metrics) for item in last.items],
                delta_matches=bool(np.allclose(
                    last.objectives[:, 0] - last.raw_objectives[:, 0], expected)),
            )
        self.payload = dict(run_id=control.run_session.run_id,
            evaluations=control.evaluation_count, steps=control.run_progress_steps,
            refs=[ref.as_dict() for ref in refs], members=members, last=last_payload)

    def on_solver_finalized(self, result):
        atomic_write_text(self.output, json.dumps(self.payload, ensure_ascii=False,
            allow_nan=False, indent=2, default=json_value))
```

Report只重算本例公式，不再调用Bias或Problem。finalized后写本地副本，不创建新权威产物。最后反馈含全部已评估行，不等于最终成员或全部接纳行；没有成员时保留None，不伪造空矩阵维数。

## domain.shared_assembly · 完整薄入口与公开硬门

新增 `adapter/domain_search.py`：

```python
from nsgablack.adapters import NSGA2Adapter


def build_adapter():
    return NSGA2Adapter(population_size=12, offspring_size=6, crossover_rate=0.0)
```

本例由问题Pipeline提供初始化、变异与修复；关闭算术交叉，使生产整数布局完全由所选算子维护。初始化仍先经正常repair/evaluate/admission建立成员，不在builder里创建Unit。

完整替换 `build_solver.py`：

```python
from pathlib import Path
from nsgablack.core import ComposableSolver, FeasibleEvaluationAcceptance
from .adapter.domain_search import build_adapter
from .bias.domain_scores import build_bias, attach_evaluation
from .pipeline.domain_pipeline import build_pipeline
from .plugins.domain_report import DomainReport
from .problem.domain import build_problem


def build_solver(run_id=None, *, strategy=None, quickstart=False,
                 resource_context=None, component_overrides=None):
    if strategy not in (None, "", "default", "none") or component_overrides:
        raise ValueError("this recipe binds one explicit domain definition")
    search = build_adapter()
    solver = ComposableSolver(problem=build_problem(), adapter=search,
        representation_pipeline=build_pipeline(), resource_context=resource_context,
        plugin_strict=True, snapshot_strict=True,
        evaluation_acceptance_policy=FeasibleEvaluationAcceptance())
    solver.set_random_seed(17)
    solver.set_max_steps(6)
    solver.set_max_step_attempts(40)
    solver.set_bias_module(build_bias(), enable=True)
    attach_evaluation(solver)
    solver.add_plugin(DomainReport(search,
        Path(__file__).resolve().parents[2] / "results" / "domain_scores.json"))
    return solver
```

在Case的context_keys.json注册 `["metrics.case.domain_x"]`；已有数组保留并追加去重。场景mc_*已由共享底座登记。各主例的attach_evaluation完整定义在其评分文件，不遗漏隐式挂载。

**运行入口：** Project副本根执行 `python run_project.py --check --build-check`，再执行 `python run_project.py`。检查本轮 `results/domain_scores.json` 的run_id和Project终态；构造通过不是评分/硬门/恢复验证。40次物理尝试是活性保护，不是40次逻辑提交；硬接纳可能导致成员未填满或提前结束。

## domain.continuous_pipeline · 二维连续候选的完整问题管线

新建 `pipeline/domain_pipeline.py`：

```python
from nsgablack.representation import (
    RepresentationPipeline, UniformInitializer, GaussianMutation, ClipRepair,
)


def build_pipeline():
    return RepresentationPipeline(initializer=UniformInitializer(-2., 2.),
        mutator=GaussianMutation(sigma=.3), repair=ClipRepair(-2., 2.))
```

## domain.soft_limit_problem · 软/硬上限的完整问题定义

新增 `problem/domain.py` 完整文件：

```python
import numpy as np
from blackbase.types import Feedback
from nsgablack.core import BlackBoxProblem


class SoftLimitSphere(BlackBoxProblem):
    context_provides = ("problem_data",)

    def __init__(self, hard_limit=False):
        super().__init__(name="soft_limit_sphere", dimension=2,
            bounds=[(-2., 2.)] * 2, objectives=["sphere"])
        self.hard_limit = bool(hard_limit)

    def evaluate(self, x, context):
        a = np.asarray(x, dtype=float)
        excess = max(0., float(a[0]) - .5)
        context["problem_data"] = {"constraint_violations": [excess]}
        return Feedback(objectives=[float(a @ a)], metrics={"case.domain_x": a.tolist()})

    def evaluate_constraints(self, x):
        return np.array([max(0., float(x[0]) - .5)]) if self.hard_limit else np.empty(0)


def build_problem():
    return SoftLimitSphere(hard_limit=False)
```

此处problem_data是这一次本地调用的轻量数据，不写共享ContextStore；不是把constraints改名后就假定Bias会自动读。本文没有另挂评估Provider，因此Problem的本地上下文会到同次Bias边界；换Provider须重新明确同一候选的指标交接，不能照搬这个可变局部桥。

## bias.feasibility · 明确给出当次违反向量，才有软成本

**什么时候用：** 希望给某个超出量加可解释软罚，同时分清它和真正硬接纳的差别。FeasibilityBias不会自行调用Problem.evaluate_constraints。

**先准备什么：** 共用正式Project、Report和薄builder；候选2维[-2,2]，raw目标平方和。基线把x0>.5当软要求，尚不是Problem硬约束。

**放在哪：** Problem使用本书domain.soft_limit_problem的完整文件，Pipeline使用domain.continuous_pipeline完整文件；评分工厂如下，完整保存为 `bias/domain_scores.py`：

```python
from nsgablack.bias import BiasModule, FeasibilityBias


def build_bias():
    module = BiasModule()
    module.cache_enabled = False
    module.add(FeasibilityBias(weight=1., feasibility_threshold=1e-6, penalty_scale=10.))
    return module


def attach_evaluation(solver):
    return None


def expected_delta(feedback):
    excess = max(0., float(feedback.metrics["case.domain_x"][0]) - .5)
    return 0. if excess < 1e-6 else 10. * excess
```

**接入步骤：** 按共用builder接上这三个文件。FeasibilityBias只读problem_data.constraint_violations，默认缺失时返回0；硬门实际读raw_violations。compute内部乘weight，外层再乘，本例用1避免平方系数误解。mandatory不赋予准入权限。

**怎样判断接对：** members.raw_violations基线全0，软超限可能留存；last.delta_matches按阈值与10倍超出量核对。最后反馈里case.domain_x属于各自候选；不能用一份全局违反量给整批加相同罚。raw平方和不变，selection增加软成本。

**运行入口：** 共用正式Project命令，未执行。

### 变体一：升级成真正Problem硬条件

**目的：** 由raw条件决定能否进入Adapter更新。**改在哪里：** 只完整替换Problem工厂：

```python
def build_problem():
    return SoftLimitSphere(hard_limit=True)
```

**行为变化：** 评估发生后，x0超限提案由raw硬门拒绝；软成本仍独立计算。**限制：** 这不是FeasibilityBias产生硬拒绝，ClipRepair也没修到半平面；成员容量和逻辑步数可能不足。按本轮终态与raw违反量判断，不把软成本为0当作全局约束证明。

## bias.engineering_constraint · 显式几何超出量，不自动成为安全认证

**什么时候用：** 已有明确且便宜的违反函数，想按安全系数放大其软成本。它不替代真实工程仿真、材料模型或硬可行性门。

**先准备什么：** 使用上一节SoftLimitSphere和Pipeline的完整独立副本、共用Report/builder。直接使用domain.soft_limit_problem与domain.continuous_pipeline两节的完整Problem/Pipeline；实际超出量仍为max(0,x0-.5)，默认软条件。

**放在哪：** 完整替换 `bias/domain_scores.py`：

```python
from nsgablack.bias import BiasModule
from nsgablack.bias.specialized.engineering import EngineeringConstraintBias


def upper_excess(x):
    return max(0., float(x[0]) - .5)


def build_bias():
    module = BiasModule()
    module.cache_enabled = False
    component = EngineeringConstraintBias(weight=1., safety_factor=1.5)
    component.add_engineering_constraint(upper_excess, "geometry", weight=2.,
                                         description="explicit coordinate upper excess")
    module.add(component)
    return module


def attach_evaluation(solver):
    return None


def expected_delta(feedback):
    return 3. * upper_excess(feedback.metrics["case.domain_x"])
```

**接入步骤：** 其余完整文件与共用装配不动。本类compute内外也重复乘总体weight，使用1；单条constraint weight2与safety_factor1.5构成3倍超出量。constraint_type在当前循环只用于记录，不会按strength/geometry自动选择物理模型。不要预填非空constraint_types后再add，列表与实际函数的zip位置需要对齐。

函数异常会被旧实现转换成有限1000倍单条权重的软罚，**不会fail-closed成求值异常**。安全关键失败应由Problem/Provider明确传播，不靠此分支。get_constraint_status的有历史分支引用未定义self.violations，本例Report不调用它；不能展示该方法为已验证统计API。

**怎样判断接对：** last.delta_matches应按3倍超出量核对，raw仍平方和。这个系数只是软损失放大，不是物理安全系数认证；原始违反量与评分历史互不替代。

**运行入口：** 共用正式Project命令，未执行或模拟工程后端。

### 变体一：把约束权重改为1，降低相对影响

**目的：** 分清总体weight、函数weight和安全放大三个位置。**改在哪里：** 在上述工厂add_engineering_constraint那行将weight改成1，同时完整替换公式读取：

```python
def expected_delta(feedback):
    return 1.5 * upper_excess(feedback.metrics["case.domain_x"])
```

**行为变化：** 选择增量减半，raw不变；仍不是硬约束。**限制：** 不通过改总体weight=.5来假定只减半，因为总体weight当前会被重复相乘。

## bias.production_constraint · 三种生产软成本共同接到整数计划

**什么时候用：** 想解释 `bias.production_constraint`、`bias.production_diversity`、`bias.production_continuity` 的真实公式。这里是两机器三天的小型数量计划，不是用户原有多产品、到料、BOM数量、切换与提前期模型的替代。

**先准备什么：** 共用Project/Report/builder的独立副本。候选扁平6维，reshape为2×3，每项0..3整数；BOM把两机器关联到同一材料A，inventory_data[A]=4。该旧约束按**活跃机器日次数**耗材，不按数量乘BOM用料，不能用于复杂排程的真实库存账。

**放在哪：** `problem/domain.py` 完整内容：

```python
import numpy as np
from blackbase.types import Feedback
from nsgablack.core import BlackBoxProblem


class TinyPlan(BlackBoxProblem):
    def __init__(self, hard_limits=False):
        super().__init__(name="tiny_integer_plan", dimension=6,
            bounds=[(0, 3)] * 6, objectives=["quantity_error"])
        self.hard_limits = bool(hard_limits)
        self.target = np.array([[1., 1., 0.], [0., 1., 1.]])

    def evaluate(self, x):
        a = np.asarray(x, dtype=float)
        return Feedback(objectives=[float(np.sum((a.reshape(2, 3) - self.target) ** 2))],
                        metrics={"case.domain_x": a.tolist()})

    def evaluate_constraints(self, x):
        if not self.hard_limits:
            return np.empty(0)
        active = np.asarray(x).reshape(2, 3) > 0
        return np.array([max(0., float(active.sum(axis=0).max()) - 1.),
                         max(0., float(active.sum()) - 4.)])


def build_problem():
    return TinyPlan(hard_limits=False)
```

`pipeline/domain_pipeline.py` 完整内容：

```python
from nsgablack.representation import (
    RepresentationPipeline, IntegerInitializer, IntegerMutation, IntegerRepair,
)


def build_pipeline():
    return RepresentationPipeline(initializer=IntegerInitializer(low=0, high=3),
        mutator=IntegerMutation(sigma=1., low=0, high=3), repair=IntegerRepair(low=0, high=3))
```

`bias/domain_scores.py` 完整内容：

```python
import numpy as np
from nsgablack.bias import BiasModule
from nsgablack.bias.specialized.production.scheduling import (
    ProductionConstraintBias, ProductionDiversityBias, ProductionContinuityBias,
)


def build_bias():
    module = BiasModule()
    module.cache_enabled = False
    module.add(ProductionConstraintBias(
        machine_bom={"M0": ["A"], "M1": ["A"]}, inventory_data={"A": 4},
        machine_ids=["M0", "M1"], days=3, max_machines_per_day=1, weight=1.))
    module.add(ProductionDiversityBias(weight=.1))
    module.add(ProductionContinuityBias(machine_ids=["M0", "M1"], days=3, weight=.2))
    return module


def attach_evaluation(solver):
    return None


def expected_delta(feedback):
    a = np.asarray(feedback.metrics["case.domain_x"], dtype=float)
    plan = np.round(a).astype(int).reshape(2, 3)
    active = plan > 0
    if np.any(active.sum(axis=0) > 1) or active.sum() > 4:
        constraint = 1e12
    else:
        bursts = 0
        for row in active:
            transitions = np.diff(np.r_[0, row, 0])
            starts = np.flatnonzero(transitions == 1)
            ends = np.flatnonzero(transitions == -1)
            bursts += int(np.sum(ends - starts <= 1))
        constraint = (float(np.mean(np.abs(a - np.round(a))))
            + 10. * float(np.mean(np.abs(np.diff(plan, axis=1)))) + 5. * bursts / 2.)
    return constraint - .1 * float(np.var(a)) + .2 * float(np.sum(np.abs(np.diff(active, axis=1))))
```

**接入步骤：** 三类都实际挂载。Constraint的1e12是有限软罚，不是硬拒绝；Diversity是**单个计划坐标的方差奖励**，不是种群多样性，不依赖PopulationUnit；Continuity只数开/关变化，不数产品切换。三类compute未再乘各自总体weight，基类各乘一次。IntegerRepair使本例的小数罚通常为0；天数至少2，避免对空diff求均值。

**怎样判断接对：** members候选长度6且整数范围0..3，raw是目标数量误差，selection叠加上述三项；last.delta_matches核对同批公式。raw违反量基线0，可能仍保留被1e12软罚的计划，不能解释为库存/机器硬条件已满足。生产方差奖励与连续开机成本可能互相拉扯，这是明确加权选择，不是算法会自动理解业务优先级。

**运行入口：** 共用正式Project命令，未执行生产优化或现有复杂排程Case。

### 变体一：用原始机器日/材料计数作硬门

**目的：** 对这个小型示例，真正拒绝并行开机或活跃次数超限。**改在哪里：** 完整替换Problem工厂：

```python
def build_problem():
    return TinyPlan(hard_limits=True)
```

**行为变化：** raw约束独立表达两项超出，FeasibleEvaluationAcceptance只接纳满足者。**限制：** 可能出现零接纳或部分填充，40次尝试不是成功保证；上述耗材计数仍不是BOM数量/多产品模型，不能拿它替换已有真实业务Problem。

## bias.robustness · 消费每候选的场景标准差

**什么时候用：** 原始目标是随机场景均值，希望在均值之外惩罚波动。RobustnessBias本身不采样，也不自己重复调用Problem。

**先准备什么：** 共用独立Project、NumPy与框架。二维[-2,2]候选；MonteCarlo正式Provider对每个候选采样8次，mean/std均是长度1数组。原始目标为这些场景的均值，不是无噪声解析期望。

**放在哪：** `problem/domain.py` 完整文件：

```python
import numpy as np
from nsgablack.core import BlackBoxProblem


class ScenarioCost(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="scenario_cost", dimension=2,
            bounds=[(-2., 2.)] * 2, objectives=["scenario_mean_cost"])

    def evaluate(self, x):
        a = np.asarray(x, dtype=float)
        return float(np.sum((a - 1.) ** 2) + (.1 + abs(a[0])) * np.random.normal())


def build_problem():
    return ScenarioCost()
```

Pipeline完整使用本书domain.continuous_pipeline的Uniform/Gaussian/Clip工厂；不是整数版本。`bias/domain_scores.py` 完整文件：

```python
import numpy as np
from nsgablack.bias import BiasModule
from nsgablack.bias.algorithmic.signal_driven.robustness import RobustnessBias
from nsgablack.plugins.evaluation.monte_carlo_evaluation import (
    MonteCarloEvaluationProviderPlugin, MonteCarloEvaluationConfig,
)

POWER = 1.


def build_bias():
    module = BiasModule()
    module.cache_enabled = False
    module.add(RobustnessBias(weight=.2, aggregate="mean", power=POWER))
    return module


def attach_evaluation(solver):
    solver.add_plugin(MonteCarloEvaluationProviderPlugin(
        config=MonteCarloEvaluationConfig(mc_samples=8, reduce="mean", random_seed=7)))


def expected_delta(feedback):
    deviation = float(np.mean(np.asarray(feedback.metrics["mc_std"], dtype=float)))
    return .04 * deviation ** POWER
```

**接入步骤：** 共用builder只attach一次Provider。compute先乘weight=.2，外层再乘，实际增量是.04*std；本页明确这个实现差异，不按构造参数假定一次权重。mc_std来自同一候选真实场景反馈，缺失会返回0/警告；必须通过报告检查来源，不能只看未报错。Provider的random_seed不保证Problem里全局np.random噪声状态的checkpoint重放，本例未作可复现性声明。

**怎样判断接对：** last.metrics每行有mc_samples=8和mc_mean/mc_std/mc_min/mc_max；last.raw对应mc_mean，last.selection=mean+.04*std，delta_matches应true。控制面evaluation_count是送评候选数，不等于8倍场景Problem调用数。最终成员raw可能来自不同随机批次，不用无噪声平方和替代其已记录测量。

**运行入口：** 共用Project命令，未执行蒙特卡洛。正权重惩罚波动不是全局鲁棒最优或概率安全保证。

### 变体一：对聚合标准差使用平方成本

**目的：** 更强地压制大波动。**改在哪里：** 仅将同文件POWER改为：

```python
POWER = 2.
```

**行为变化：** 本单目标例为.04*std²；expected_delta与真实工厂同时改变。**限制：** 多目标aggregate=mean再平方不等于逐目标方差均值；这里没更换聚合器，量纲也已改变。仍不在Bias中私自采样。

## migration.bias.domain_placeholders · 六个旧领域名称未装配

**什么时候用：** 命中 `bias.safety`、`bias.manufacturing`、`bias.scheduling`、`bias.resource_constraint`、`bias.time_window`、`bias.engineering_design`，期待自动落实安全、制造或排程语义。前五类compute当前直接返回0；EngineeringDesign只查OptimizationContext的stress_values/allowable_stress属性，标准BiasModule不会把problem_data任意字段自动提升为这些属性，manufacturing_tolerance也未参与compute。

**先准备什么：** 要表达一个明确的软上限，可用本书Feasibility/EngineeringConstraint完整Case；要表达真实生产模型，应保留自己的Problem和数据。六旧类未装配，也不把这里的2×3玩具计划当作复杂排程。

**放在哪：** 已知简单违反函数放Case的bias/domain_scores.py；真正硬约束放Problem.evaluate_constraints，经raw门接纳；真实制造公差修复放问题Pipeline；全局硬资源lease仍由Project L0负责，不能用ResourceConstraintBias名字代替授权。

**接入步骤：** 采用配套《领域软评分》完整ConstraintBias配方，明确函数输入是当前候选、返回非负超出量、总体weight=1；报告核对selection-raw。时间窗可写显式 `max(0,start-window_end)` 软函数，但不是占位SchedulingBias已实现；多产品/跨日物料必须继续在Problem明确定义，不在Bias临时藏业务搜索。

**怎样判断接对：** 实际装配列表中应出现ConstraintBias或本文明确可用组件，不能出现六个旧名称并宣称安全生效。期望值按业务函数核对，raw门与软罚分别检查。把空对象挂上后总罚0并不能证明没有风险。

**运行入口：** 使用配套完整bias_gallery Project的规范命令；旧六类不提供正常运行保证。

### 变体一：软条件改为硬条件

**目的：** 决定是否允许不可行候选参与更新。**改在哪里：** 采用配套完整LimitedSphere Problem与替换导入，保留FeasibleEvaluationAcceptance。**行为变化：** 真正raw违反量控制接纳。**限制：** 没有给占位类补功能，也不是工程安全认证。

## migration.bias.engineering_history · 两个旧精度/鲁棒类未装配

**什么时候用：** 命中 `bias.engineering_precision` 或 `bias.engineering_robustness`，期望看到可靠数值精度或场景鲁棒统计。

**先准备什么：** 精度搜索使用配套正式有限差分Adapter Case；场景波动使用本书RobustnessBias+MonteCarlo完整Case，不把旧类add进去。

**放在哪：** 真实扰动评估属于正式Problem/Provider，每项预算与证据明确；Bias只消费每候选统计。不能将eval_func放进problem_data后让评分暗中再次调用它。

**接入步骤：** EngineeringPrecision的首段估计只计算坐标加1e-8后的自身差值，再把历史“估计”的变化当精度；读取的base_fitness没有用于目标敏感度，不是舍入误差或目标函数精度测量。返回符号还会奖励较大的precision_deficit。EngineeringRobustness有eval_func时直接评估基准加多个扰动、硬裁[0,1]，没有时返回0；正的1/(1+variance)加到最小化目标会使更稳点更贵。compute内外重复加权也不能忽略。见 `bias/specialized/engineering.py`。

**怎样判断接对：** 场景统计通过本书Robustness主例的mc_*与delta_matches核对；有限差分通过配套Report确认起点/探针/下降点评估。两者都没有声称“测到了机器浮点精度”，也不恢复旧类的私有历史。

**运行入口：** 本书场景Case或配套finite_difference组，明确选择一种；旧两类未运行。

### 变体一：只观察波动，不改变选择

**目的：** 先验证统计来源。**改在哪里：** 在Robustness主例的build_bias中把weight改为0，并把expected_delta改为返回0；Provider与Report保留。**行为变化：** mean/std仍由正式场景评估生成，raw=selection。**限制：** 不省8次场景调用，不等于鲁棒优化或精度控制。

## migration.bias.uncertainty_exploration · 当前旧类未装配，负奖励应显式接消费者

**什么时候用：** 想奖励代理不确定性，命中UncertaintyExplorationBias。当前dataclass未调用AlgorithmicBias基类初始化，缺少enabled/跟踪字段；普通BiasModule装配不能被描述为已正常生效。本页不在Case中手工补这些基类私有字段。

**先准备什么：** 使用配套SurrogateEvaluationProvider完整DE Case，确保每候选Feedback.metrics确有surrogate_std；不是蒙特卡洛std，也不能用某个全局常数假装预测不确定性。

**放在哪：** 在配套完整builder挂Provider之后、return之前，用以下公开CallableBias实际消费该指标。原Report/Pipeline/Adapter/Project L0保留；旧类不add。

**接入步骤：**

```python
import numpy as np
from nsgablack.bias import BiasModule, CallableBias


def uncertainty_reward(x, context):
    values = np.asarray(context.metrics["surrogate_std"], dtype=float)
    if not values.size or not np.all(np.isfinite(values)):
        raise ValueError("finite per-candidate surrogate_std is required")
    return max(0., float(values.mean()))


def attach_uncertainty_preference(control):
    module = BiasModule()
    module.cache_enabled = False
    module.add(CallableBias("explicit_uncertainty_reward", uncertainty_reward,
                            weight=.2, mode="reward"))
    control.set_bias_module(module, enable=True)
```

在配套build_solver的attach_evaluation(control)之后实际调用attach_uncertainty_preference(control)。暖启阶段Provider尚未产生surrogate_std的行不能强行执行该严格版本；因此此接线只用于配套已预建SimplifiedModel、min_train_samples=0且全部行有明确uncertainty的变体，主例暖启不套用。本配套模型的.2是不确定性接口演示常数，明确不是已校准误差。

**怎样判断接对：** Report的last_selection比last_raw低.2×该行surrogate_std均值；无统计时明确报错，不以静默0声称成功。该操作只是选择软奖励，不能让raw近似值变成真值；原保真标记仍需保留。

**运行入口：** 配套的完整预建预测器变体Project命令，未运行模型或算法。`usage_status=migration_reference`表示旧UncertaintyExplorationBias未装配，不把CallableBias替代当作旧实现已修复。

### 变体一：只保留不确定性观察

**目的：** 区分统计可见与探索政策生效。**改在哪里：** 不调用attach_uncertainty_preference，保留配套ProviderReport与明确统计源。**行为变化：** Provider仍返回逐候选surrogate_std，raw与selection一致。**限制：** 不进行不确定性奖励，也没有修复旧dataclass或保证预测误差。

依据：`bias/domain/constraint.py`、`bias/domain/engineering.py`、`bias/domain/scheduling.py`、`bias/specialized/engineering.py`、`bias/specialized/production/scheduling.py`、`bias/algorithmic/signal_driven/robustness.py`、`uncertainty_exploration.py`及共用求值/Bias边界。所有边界均针对当前实现，不把名称当功能证明。
