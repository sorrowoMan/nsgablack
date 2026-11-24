# 候选变化、问题修复与成员状态：四个装配扩展

以下变体承接各组件已有主例。每次在完整标准Project副本上只应用一个变体；不要把四个片段全部塞进同一Case。所有步骤沿用原Project的L0与Case入口，不在装配时创建Unit或另外调用evaluate。

## extension.repr.gaussian_mutation

### 变体一：只扰动第一个坐标，并保留可恢复的随机状态

**目的：** 第二个坐标已经由业务规则确定，只希望变异步骤微调第一个连续参数。仅把sigma调小仍会扰动所有坐标；下面包装现成GaussianMutation，不重写随机采样，也不在变异里做问题修复。

**改在哪里：** 复制完整`examples/cases/assembled_ga_vns/`。新增`cases/hybrid_search/pipeline/coordinate_mutation.py`，内容如下。包装器拥有一个独立高斯实例，显式转发随机种子与数据状态，不能把同一个包装器交给两个Adapter。

```python
import numpy as np
from nsgablack.representation import GaussianMutation


class FirstCoordinateGaussian:
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()

    def __init__(self, sigma):
        self.noise = GaussianMutation(sigma=sigma)

    def checkpoint_identity(self):
        return {"name": "first_coordinate_gaussian", "version": 1,
                "noise": self.noise.checkpoint_identity()}

    def set_random_seed(self, seed):
        self.noise.set_random_seed(seed)

    def get_state(self):
        return {"noise": self.noise.get_state()}

    def set_state(self, state):
        self.noise.set_state(state["noise"])

    def mutate(self, candidate, context=None):
        draft = np.asarray(candidate, dtype=float).copy()
        if draft.ndim != 1 or not len(draft):
            raise ValueError("a nonempty numeric vector is required")
        draft[:1] = self.noise.mutate(draft[:1], context)
        return draft
```

在该Case的`adapter/composition.py`加入下面完整工厂，把原`build_adapter(settings)`里创建`ga`的那一段替换为`ga = build_coordinate_ga(settings)`。VNS、角色、精修输入、返回竞争与后面的return全部保留。

```python
from nsgablack.adapters import NSGA2Adapter
from nsgablack.representation import UniformInitializer
from nsgablack.units import UnitBinding
from ..pipeline.coordinate_mutation import FirstCoordinateGaussian
from ..pipeline.population import AgePopulationBuilder


def build_coordinate_ga(settings):
    return NSGA2Adapter(
        name="ga", population_size=settings.population_size,
        offspring_size=settings.population_size,
        initializer=UniformInitializer(-4.0, 4.0),
        mutator=FirstCoordinateGaussian(settings.ga_sigma),
        unit_binding=UnitBinding(AgePopulationBuilder()),
    )
```

**运行与检查：** 在Project副本执行`python run_project.py --check --build-check`，再执行`python run_project.py --group plan`。`results/plan/trace.json`保留原GA→VNS→GA阶段；`initial.operation_contracts`中GA的变异绑定应为FirstCoordinateGaussian。单独验证叶组件时，对输入`[0.5,0.9]`调用mutate应返回新数组，第二项仍为0.9，输入不变；保存get_state、调用一次、恢复后再调用，结果应相同。这是随机状态检查，不能把这次叶调用的数组直接当成池内已评估版本。

**行为变化与限制：** 只有该mutator本身固定其输入的后续坐标。GA交叉可能已改变第二个坐标，VNS仍能改变它，问题repair也仍有最终处理权；若要全流程冻结某坐标，需要对应的候选/问题契约，不能据此声称整个搜索固定了第二项。这里不新增上下文键，不创建Unit，不把原始目标改为扰动幅度。

## extension.repr.pipeline

### 变体一：从独立边界裁剪改为两个比例总和为一

**目的：** 把两个变量解释为资源分配比例。两个坐标分别在[0,1]内仍可能总和超过1，因此仅ClipRepair不足；问题定义与问题修复要一起变。

**改在哪里：** 复制完整`examples/cases/catalog_fixed_candidate/`。将`cases/fixed/problem/__init__.py`替换为下方完整文件，保留原adapter、Trace与Project资源配置。

```python
import numpy as np
from nsgablack.core import BlackBoxProblem


class AllocationProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="two_shares", dimension=2,
                         bounds=[(0.0, 1.0), (0.0, 1.0)],
                         objectives=["squared_norm"])

    def evaluate(self, candidate):
        values = np.asarray(candidate, dtype=float)
        return float(np.sum(values ** 2))

    def evaluate_constraints(self, candidate):
        values = np.asarray(candidate, dtype=float)
        return np.array([max(0.0, abs(float(values.sum()) - 1.0) - 1e-9)])


def build_problem():
    return AllocationProblem()
```

将同Case的`pipeline/main.py`完整替换为下方文件；`pipeline/__init__.py`仍导出build_pipeline。该单位单纯形中每项自然不超过1，因此此处的边界与总和投影兼容。

```python
from nsgablack.representation import RepresentationPipeline, ProjectionRepair


def build_pipeline():
    return RepresentationPipeline(
        repair=ProjectionRepair(low=0.0, high=1.0,
                                sum_target=1.0, nonnegative=True),
    )
```

最后在原`build_solver.py`中，将传给build_adapter的`candidate=options.get("candidate", (0.25, 0.75))`改为`candidate=options.get("candidate", (0.4, 1.2))`，其余工厂不变。这仍由直属FixedSeed给初值，所以新Pipeline不必另配initializer。

**运行与检查：** 在该Project副本执行`python run_project.py --check --build-check`和`python run_project.py --no-record`。实际送评的数值应接近`[0.1,0.9]`，总和接近1；Trace中的raw目标应接近0.82，违反量为0，提交和求值仍各1次。不能沿用原例0.625的检查。检查读取实际池反馈，不再调用Problem.evaluate。

**行为变化与限制：** 这是改变问题可行域及ProblemRepair，不是给Adapter增加另一套管线。原提案token在repair后保持，但候选版本与目标按最终数组交付。该配方只说明本例单位单纯形；一般上下限、多个耦合约束或整数比例不一定能靠一次ProjectionRepair满足，不能用一次成功结果证明任意问题的联合可行性。不要同时启用原例的Pipeline随机初始化变体，因为这里未装配initializer。

## extension.tool.unit_binding

### 变体一：在装配时检查结构兼容性，仍保持Unit懒创建

**目的：** 给已有GA装自定义成员结构时，尽早发现把轨迹、区域或错误schema接成种群的问题。检查builder声明不需要初始化候选，也不必等实际运行到第一代才发现装配不匹配。

**改在哪里：** 复制`examples/cases/assembled_ga_vns/`，保留`pipeline/population.py`中的AgePopulationBuilder。在`cases/hybrid_search/adapter/composition.py`加入以下完整工厂，把原`ga = NSGA2Adapter(...)`整段替换为`ga = build_checked_ga(settings)`；VNS、池任务和外层计划不变。

```python
from nsgablack.adapters import NSGA2Adapter
from nsgablack.representation import UniformInitializer, GaussianMutation
from nsgablack.units import UnitBinding, PopulationUnit
from ..pipeline.population import AgePopulationBuilder


def build_checked_ga(settings):
    binding = UnitBinding(AgePopulationBuilder(), name="ga_age_structure")
    binding.require(PopulationUnit.schema, operations=("initialize",),
                    builder_methods=("dump", "restore"))
    ga = NSGA2Adapter(
        name="ga", population_size=settings.population_size,
        offspring_size=settings.population_size,
        initializer=UniformInitializer(-4.0, 4.0),
        mutator=GaussianMutation(settings.ga_sigma),
        unit_binding=binding,
    )
    assert ga.algorithm_unit is None
    return ga
```

**运行与检查：** 在副本执行`python run_project.py --check --build-check`再执行`python run_project.py --group plan`。装配检查应成功；`binding.describe_requirement(PopulationUnit.schema, operations=("initialize",))`的match应为declared-compatible，因为年龄schema明确声明兼容基础种群，而不是两个schema完全相同。实际运行仍由GA首次使用时构建Unit，原报告继续显示member_age。

**行为变化与限制：** 此变体新增明确的装配检查与稳定binding名称，不改变GA选择规则。若拿TrajectoryUnitBuilder替换AgePopulationBuilder，require必须拒绝，而非为了检查调用build。compatible_schemas只说明算法可消费该结构，不允许把基础PopulationUnit的checkpoint自动恢复成年龄结构；本变体改变了binding名称，不能直接复用原名称下的旧checkpoint。多个GA实例应各自创建binding和运行Unit，不能用共享可写Unit复用数据。

## extension.tool.population_unit

### 变体一：同时维护年龄与入群时的选择分数

**目的：** 分析成员是在什么选择压力下进入种群的。入群时的分数是历史状态，不应在后续反馈刷新时被覆盖，也不能被当成当前候选的raw目标；因此它与可丢弃的UnitFeature缓存不同。

**改在哪里：** 复制`examples/cases/assembled_ga_vns/`。保留`cases/hybrid_search/pipeline/population.py`现有AgePopulationUnit与AgePopulationBuilder，在文件末尾追加以下完整类。两个新字段按同一PopulationChange映射维护；初始化尚无反馈时用known=False表达未知，0只是存储占位，不表示已评分为零。

```python
from dataclasses import dataclass, field
import numpy as np
from nsgablack.units import UnitSchema


@dataclass
class EnrollmentPopulationUnit(AgePopulationUnit):
    entry_score: np.ndarray = field(default_factory=lambda: np.zeros(0))
    entry_score_known: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=bool))
    member_fields = (*AgePopulationUnit.member_fields, "entry_score", "entry_score_known")
    schema = UnitSchema(
        "assembled_ga_vns.enrollment_population",
        required_fields=(*AgePopulationUnit.schema.required_fields,
                         "entry_score", "entry_score_known"),
        candidate_projection=False,
    )

    def on_members_changed(self, change):
        updates = super().on_members_changed(change)
        scores, known = [], []
        for previous, incoming in zip(change.previous_member_indices,
                                      change.incoming_member_indices):
            if previous is not None:
                scores.append(float(self.entry_score[previous]))
                known.append(bool(self.entry_score_known[previous]))
            else:
                has_feedback = change.incoming_objectives is not None
                scores.append(float(change.incoming_objectives[incoming, 0])
                              if has_feedback else 0.0)
                known.append(has_feedback)
        return {**updates, "entry_score": np.asarray(scores, dtype=float),
                "entry_score_known": np.asarray(known, dtype=bool)}

    def validate(self):
        super().validate()
        if self.entry_score_known.dtype.kind != "b":
            raise ValueError("entry_score_known must be boolean")
        if not np.all(np.isfinite(self.entry_score[self.entry_score_known])):
            raise ValueError("known entry scores must be finite")


class EnrollmentPopulationBuilder(AgePopulationBuilder):
    unit_type = EnrollmentPopulationUnit
```

在`adapter/composition.py`把AgePopulationBuilder的导入和`UnitBinding(AgePopulationBuilder())`同时改为EnrollmentPopulationBuilder；其它算法、问题、变化和计划全部保留。原报告仍可读取继承的member_age，不会因为增加历史字段就要求改GA内部代码。

**运行与检查：** 执行`python run_project.py --group plan`。在实际GA拥有的`algorithm_unit`上只读查看entry_score/entry_score_known，长度应与population_members一致；不要为查看而ensure_unit。规则可单独核对：旧成员分数[5,6]，选择第二个旧成员和分数4的新成员，结果应为[6,4]；如果后来只刷新当前反馈为[60,40]，入群历史仍为[6,4]。这是维护规则示意，当前目录运行标签仍以独立收据为准。

**行为变化与限制：** incoming_objectives是该Adapter本次的选择视图，这个例子只记录其第一目标，不改raw、不自动做多目标排序，也不用于决定成员去留。若要保存入群时raw证据，应设计明确的原始来源字段，不能把此值改名为raw。继承的纯数据codec保存全部dataclass字段，恢复不重放on_members_changed；旧AgePopulation的checkpoint没有这些新字段和schema，不能猜值迁移。各字段随真实成员操作、步骤回滚和codec恢复，而不是通过共享context维护另一份种群。
