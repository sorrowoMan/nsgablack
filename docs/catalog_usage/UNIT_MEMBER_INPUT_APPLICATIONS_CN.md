# Unit 成员字段、派生特征与只读算子输入：一个能照着改的 GA

本例同时回答三件事：成员重排后如何维护自己的字段；几何量怎样按需计算；变异怎样读取所属算法的结构。它们通过正式 NSGA-II 接缝组合，没有在 context 建第二份种群。主例已在独立完整 Project 副本通过 `--check --build-check`，变体只经源码核对；未执行算法或生成运行收据。

## tool.population_change · 给每个成员维护连续生存年龄

**什么时候用：** 想在最终成员中记录一个自定义 age，并让初始化、新成员加入、淘汰、重排与恢复沿用同一规则；再让变化算子读取当前种群中心。age 不参与本例的选择，只用于核对联动。

**先准备什么：** 复制完整 `examples/cases/bias_gallery/` Project。保留原 Project/L0/default 组与规范运行入口、Case 包、`problem/example_problem.py::SphereProblem`。使用二维候选、原始平方和目标和 `[-5,5]` 边界，依赖当前 nsgablack/blackbase/NumPy。

**放在哪：** 新建 `cases/bias_gallery/pipeline/member_unit.py`、`pipeline/member_operator.py`、`pipeline/member_pipeline.py`、`adapter/member_search.py`、`plugins/member_report.py`，完整替换同 Case 的 build_solver.py。按下面两个连续章节保存，不用覆盖原包注册表；builder 直接导入这些明确模块。

**接入步骤：** `pipeline/member_unit.py` 完整内容：

```python
from dataclasses import dataclass, field
import numpy as np
from nsgablack.representation import PopulationUnitBuilder
from nsgablack.units import PopulationChange, PopulationUnit, UnitSchema


@dataclass
class AgePopulation(PopulationUnit):
    age: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=int))
    member_fields = ("age",)
    schema = UnitSchema("case.member_age", required_fields=(
        *PopulationUnit.schema.required_fields, "age"), candidate_projection=False)

    def on_members_changed(self, change: PopulationChange):
        increment = int(change.operation == "selection")
        return {"age": np.asarray([
            0 if old is None else self.age[old] + increment
            for old in change.previous_member_indices
        ], dtype=int)}


class AgeBuilder(PopulationUnitBuilder):
    unit_type = AgePopulation
    compatible_schemas = (PopulationUnit.schema,)
```

`change.previous_member_indices` 与最终新成员行序一致，None 表示本次新进入的成员。保留下来的旧位置才读取 self.age；incoming_* 提供本次候选、反馈、token、metadata 与 provenance 的对齐来源。本例不需要新成员的业务标签，所以不去 context 猜。局部 replacement 不代表经历一轮环境选择，未被替换的行不增龄；新行总为0。数字相同不代表同一成员。

hook 返回完整的扩展行字段，不改 change 或 self，也不手动改 X/F/V。PopulationUnit 验证长度并维护基类数组、token 和反馈版本；NSGA-II 只决定选哪些位置，不了解 age 公式。它是声明在 codec 中的持久算法状态，不是可丢失缓存。Unit 不单独变成 RuntimeParticipant，拥有它的 Adapter 负责步骤快照和恢复。

`pipeline/member_operator.py` 完整内容：

```python
import numpy as np
from nsgablack.units import UnitFeature, UnitInputSpec, UnitInputs


CENTER = UnitFeature("case.population_center", ("population",),
    lambda fields: fields["population"].mean(axis=0), feedback_view="none")


class PullToCenter:
    unit_inputs = UnitInputSpec(fields=("population",), features=(CENTER,))

    def mutate(self, candidate, context, *, unit: UnitInputs):
        values = np.asarray(candidate, dtype=float)
        if len(unit.fields["population"]) == 0:
            raise ValueError("center mutation needs evaluated population members")
        return 0.8 * values + 0.2 * unit.features[CENTER.name]
```

CENTER 只依赖候选坐标，所以 feedback_view="none"。若读取 objectives/violations，应声明 selection，不能把 PopulationUnit 的选择反馈冒充 raw。UnitFeature 只接收声明字段的脱离值；不求值、不递归读其它特征，也不隐藏搜索决策。PopulationUnit 已继承 FeatureUnit，缓存由具体 Unit 实例持有，依赖内容变化后重新计算；不进 checkpoint。age 要持久化，center 可重算，两者不能混为一类。

UnitInputSpec 是依赖声明；UnitInputs 是该次实际捕获的只读值，含 unit_id/schema/revision/fields/features。实际 NSGA2 调用 mutate_candidate 时由自己的 Unit 捕获，不由用户手造、不从全局 context 查“当前种群”。输入不是待选批次，也不授予写 Unit 或 Pool 的权限。

下一节给出完整真实消费者、观察器与运行入口。源码依据：`units/population_operations.py`、`units/features.py`、`units/operator_inputs.py`、`representation/structure_builders.py` 以及正式 scaffold 的 population_example.py。

## unit.member_inputs_wiring · 把结构与算子接到同一个实例

`pipeline/member_pipeline.py` 完整内容：

```python
from nsgablack.representation import RepresentationPipeline, UniformInitializer, ClipRepair
from .member_operator import PullToCenter


def build_pipeline():
    return RepresentationPipeline(initializer=UniformInitializer(-5., 5.),
        mutator=PullToCenter(), repair=ClipRepair(-5., 5.))
```

`adapter/member_search.py` 完整内容：

```python
from nsgablack.adapters import NSGA2Adapter
from nsgablack.units import UnitBinding
from ..pipeline.member_unit import AgeBuilder


def build_adapter():
    return NSGA2Adapter(population_size=12, offspring_size=6,
        unit_binding=UnitBinding(AgeBuilder()))
```

装配时只有规则，没有运行 Unit；首次实际使用才创建 AgePopulation。初始化先正常 repair/evaluate/admission 后建立成员，再调用需要种群的变化。默认 GA 仍可以先做自己的交叉，之后才调用这里的 Pipeline 变异；本例不是用 set_change 取代整个变化流程。mutate 本身不重复执行问题 repair。

`plugins/member_report.py` 完整内容：

```python
import json
from pathlib import Path
import numpy as np
from nsgablack.plugins.base import Plugin
from nsgablack.units import FeatureUnit, UnitInputs
from nsgablack.bias import PopulationDiversityPreference, PreferenceQuery
from ..pipeline.member_operator import CENTER, PullToCenter


class MemberReport(Plugin):
    def __init__(self, search, output):
        super().__init__(name="member_report")
        self.search, self.output = search, Path(output)

    def on_solver_finish(self, result):
        unit = self.search.algorithm_unit
        if unit is None or not isinstance(unit, FeatureUnit):
            raise RuntimeError("the declared Unit was never activated")
        captured = PullToCenter.unit_inputs.capture(unit)
        if not isinstance(captured, UnitInputs):
            raise TypeError("expected detached Unit inputs")
        center = unit.feature(CENTER)
        fresh = unit.feature(CENTER, cache=False)
        view = self.search.preference_view(owner_path=("age_search",))
        whole = PopulationDiversityPreference().evaluate(PreferenceQuery("unit", unit=view))
        refs = self.search.get_population_solution_refs(self.solver)
        self.payload = dict(run_id=self.solver.run_session.run_id,
            refs=[ref.as_dict() for ref in refs],
            tokens=list(unit.candidate_tokens), population=unit.population.tolist(),
            age=unit.age.tolist(), center=center.tolist(),
            cached_equals_fresh=bool(np.allclose(center, fresh)),
            captured_readonly=not captured.fields["population"].flags.writeable,
            input_revision=captured.revision, diversity=whole.value)

    def on_solver_finalized(self, result):
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(json.dumps(self.payload, ensure_ascii=False,
            allow_nan=False, indent=2), encoding="utf-8")
```

这里实际消费 PreferenceQuery，只将整体 Unit 最近邻距离作为观察，不给候选加 Bias，也不把“整个种群分散”偷换成“某个候选应该被接纳”。读取 preference_view 与 algorithm_unit 不会为了检查而创建结构。on_solver_finish 读取已提交状态，finalized 后写本地副本，不手动发起恢复。

`build_solver.py` 完整内容：

```python
from pathlib import Path
from nsgablack.core import ComposableSolver
from .adapter.member_search import build_adapter
from .pipeline.member_pipeline import build_pipeline
from .plugins.member_report import MemberReport
from .problem.example_problem import SphereProblem


def build_solver(run_id=None, *, strategy=None, quickstart=False,
                 resource_context=None, component_overrides=None):
    if strategy not in (None, "", "default", "none") or component_overrides:
        raise ValueError("this guide uses the declared Unit and operator")
    search = build_adapter()
    solver = ComposableSolver(problem=SphereProblem(dimension=2), adapter=search,
        representation_pipeline=build_pipeline(), resource_context=resource_context,
        plugin_strict=True, snapshot_strict=True)
    solver.set_random_seed(17)
    solver.set_max_steps(6)
    solver.set_bias_module(None, enable=False)
    solver.add_plugin(MemberReport(search, Path(__file__).resolve().parents[2]
                                  / "results" / "members.json"))
    return solver
```

**怎样判断接对：** 核对本次正式 Case 终态及 results/members.json 的 run_id。12行候选、tokens、refs、age 应同序；age 为非负整数，新进入的位置为0，留存者只按实际 selection 调用增龄，不能假定等于全局代数。center 应为最终 population 的列均值，cached_equals_fresh/captured_readonly 为 true。input_revision 是捕获依赖摘要，不是全局 generation。diversity 只是最终整体几何观察；拉向中心可能降低分散程度，本例不承诺搜索更好。

**运行入口：** 在完整 Project 副本根执行 `python run_project.py --check --build-check`，再执行 `python run_project.py`。前者只构造，不创建运行 Unit 或验证 age 演进；后者才求解。本轮只执行了第一条，确认实际组件是 NSGA2Adapter/PullToCenter/ClipRepair/member_report 且 L0 绑定生效，第二条没有运行。旧 JSON 不代表本次成功；codec 恢复和失败回滚仍需独立行为验证，不能凭装配检查宣称已通过。

### 变体一：只读自定义 age，让高龄参考群体加大回拉

**目的：** 展示新增字段如何变成实际算子输入，而不让 Adapter 硬编码认识它。

**改在哪里：** 完整替换 member_operator.py 中 PullToCenter，保留 CENTER、全部工厂和报告。

```python
class PullToCenter:
    unit_inputs = UnitInputSpec(fields=("population", "age"), features=(CENTER,))

    def mutate(self, candidate, context, *, unit: UnitInputs):
        if len(unit.fields["population"]) == 0:
            raise ValueError("center mutation needs existing members")
        strength = 0.4 if float(np.mean(unit.fields["age"])) >= 2. else 0.2
        values = np.asarray(candidate, dtype=float)
        return (1. - strength) * values + strength * unit.features[CENTER.name]
```

**行为变化：** 读取明确 age 后，回拉比例按本所有者当前成员的平均年龄改变；候选仍经过同一问题修复和评估。报告捕获也使用新的 spec，因此真实包含 age。

**限制：** 这个算子已依赖 AgePopulation，不能直接复用到没有 age 的普通 PopulationUnit，更不能接到 VNS 的单候选 Unit；缺依赖会报错，不回退为0。平均年龄是明确算法规则，不代表停滞证据或收敛证明。

### 变体二：只观察结构，移除中心变化

**目的：** 保留成员联动和特征报告，比较一个不消费 Unit 输入的普通变化。

**改在哪里：** 完整替换 member_pipeline.py；其余文件不变。

```python
from nsgablack.representation import (
    RepresentationPipeline, UniformInitializer, GaussianMutation, ClipRepair,
)


def build_pipeline():
    return RepresentationPipeline(initializer=UniformInitializer(-5., 5.),
        mutator=GaussianMutation(sigma=.3), repair=ClipRepair(-5., 5.))
```

**行为变化：** 变化不再读取 center/age；报告阶段仍通过同一个实际 Unit 捕获并计算这些值，因此可以核对算法状态与观察的边界。

**限制：** 改变随机消费后不期待同 seed 有同轨迹；报告捕获 spec 只是只读观察，不代表该 GaussianMutation 声称需要 Unit。不要因此把观察字段塞进长期 context 或把派生缓存当 checkpoint 内容。
