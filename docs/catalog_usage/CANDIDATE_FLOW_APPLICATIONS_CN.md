# 候选数据流：算子路由、问题修复和Unit修复的完整接线

本文各例采用完整 `examples/cases/catalog_recipes` 的独立副本，保留default组的composite Case、Project L0、包与规范入口。不是新增解释器，也不把数据管线变成Adapter调度器。仅核对源码/AST/接口；没有运行算法、训练、数据库、API或服务。

## flow.host · 两个独立Case共用的报告与薄构造

以下路径相对副本的cases/composite。新增plugins/flow_report.py；报告读已提交的精确引用与raw反馈，不为看字段而初始化Unit。

```python
from nsgablack.plugins.base import Plugin
from nsgablack.utils.engineering.file_io import atomic_write_json

class FlowReport(Plugin):
    def __init__(self, search, output):
        super().__init__(name="candidate_flow_report")
        self.search, self.output = search, output
    def on_solver_finish(self, result):
        control = self.solver
        refs = tuple(self.search.get_pool_refinement_results(control))
        batch = control.read_solutions(refs)
        raw_f, raw_v = control.solution_pool.read_raw_feedback(refs)
        last = control.get_last_feedback_batch()
        self.payload = {"run_id": control.run_session.run_id,
            "refs": [ref.as_dict() for ref in refs], "candidates": batch.numeric_matrix.tolist(),
            "raw_objectives": raw_f.tolist(), "raw_violations": raw_v.tolist(),
            "last_raw": None if last is None else last.raw_objectives.tolist(),
            "runtime": self.search.get_runtime_context_projection(control)}
    def on_solver_finalized(self, result):
        atomic_write_json(self.output, self.payload)
```

新增solver/flow.py。这是被规范builder实际调用的构造函数，不是第二套run循环：

```python
from pathlib import Path
from nsgablack.core import ComposableSolver
from ..plugins.flow_report import FlowReport

def build_flow(problem, pipeline, search, *, resource_context, joint_repair_policy=None):
    solver = ComposableSolver(problem=problem, representation_pipeline=pipeline,
        adapter=search, resource_context=resource_context,
        joint_repair_policy=joint_repair_policy, plugin_strict=True, snapshot_strict=True)
    solver.set_bias_module(None, enable=False)
    solver.set_random_seed(17)
    solver.set_max_steps(6)
    solver.set_max_step_attempts(20)
    solver.add_plugin(FlowReport(search, Path(__file__).resolve().parents[1]/"results"/"flow.json"))
    return solver
```

每例完整替换规范build_solver.py并显式导入build_flow。副本根先 `python run_project.py --group default --check --build-check`，再 `python run_project.py --group default`。本次cases/composite/results/flow.json才是对应运行的观察副本；核对run_id与正式Case状态。没有新权威Artifact或恢复信封，未生成运行收据。

## flow.routing · 按局部k路由变化，先变化再收缩，最后统一repair

**什么时候用：** VNS每个邻域使用不同方向，组合两个确定性变化，同时按全局已提交generation收紧新提案范围。ContextDispatchMutator选择叶算子，PipelineOrchestrator编排一次候选处理，不选择下一个Adapter。

**先准备什么：** 本书共用完整Project和报告。候选二维，Problem边界[-5,5]，单目标平方和。k来自本VNS局部上下文，generation来自Solver主进度；两者均已注册，不在共享context存数组。六逻辑步只作接线预算。

**放在哪：** 新增pipeline/routed.py，完整替换problem/__init__.py和build_solver.py；不改旧pipeline注册表，builder直接导入新build_pipeline。原pipeline/main.py仍存在但不被本builder调用。

**接入步骤：** 叶算子只声明实际mutate能力；装配时验证能力而不执行mutate。实例没有内部随机/计数状态。

```python
# cases/composite/pipeline/routed.py
import numpy as np
from blackbase.representation import RepresentationCapabilities, representation_capabilities
from blackbase.kernel import OrchestrationPolicy
from nsgablack.context_keys import KEY_VNS_K
from nsgablack.representation import (RepresentationPipeline, ContextDispatchMutator,
    DynamicRepair, PipelineOrchestrator, ClipRepair)

class InitialPoint:
    def initialize(self, problem, context):
        return np.array([2., -2.])

class AxisShift:
    representation_capabilities = RepresentationCapabilities(frozenset({"mutate"}))
    def __init__(self, sign):
        self.sign = float(sign)
    def mutate(self, candidate, context=None):
        return np.asarray(candidate, dtype=float)+self.sign*np.array([.2, -.1])

class Contraction:
    representation_capabilities = RepresentationCapabilities(frozenset({"mutate"}))
    def mutate(self, candidate, context=None):
        return .8*np.asarray(candidate, dtype=float)

def build_pipeline():
    positive, negative = AxisShift(1.), AxisShift(-1.)
    for operator in (positive, negative, Contraction()):
        if not representation_capabilities(operator).supports("mutate"):
            raise TypeError("a real mutate method is required")
    route = ContextDispatchMutator(routes={"0": positive, "1": negative},
        selector_key=KEY_VNS_K, strict=True)
    data_flow = PipelineOrchestrator(mutate_policy=OrchestrationPolicy(mode="serial",
        operators=(route, Contraction())), repair_operator=DynamicRepair(
            stages=((0, ClipRepair(-5., 5.)), (3, ClipRepair(-1., 1.)))))
    return RepresentationPipeline(initializer=InitialPoint(), mutator=data_flow, repair=data_flow)
```

```python
# cases/composite/problem/__init__.py
import numpy as np
from nsgablack.core import BlackBoxProblem

class RoutingProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=2, bounds=[(-5., 5.)]*2, objectives=["squared_norm"])
    def evaluate(self, candidate):
        values = np.asarray(candidate, dtype=float)
        return [float(values@values)]
    def evaluate_constraints(self, candidate):
        return [float(np.maximum(np.abs(np.asarray(candidate))-5., 0.).sum())]

def build_problem():
    return RoutingProblem()
```

```python
# cases/composite/build_solver.py
from nsgablack.adapters import VNSAdapter, VNSConfig
from .pipeline.routed import build_pipeline
from .problem import build_problem
from .solver.flow import build_flow

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config or component_overrides:
        raise ValueError("edit the declared routing recipe explicitly")
    search = VNSAdapter(config=VNSConfig(batch_size=1, k_max=1,
        restart_on_stagnation=False))
    return build_flow(build_problem(), build_pipeline(), search, resource_context=resource_context)
```

serial依次传递route结果再收缩；输出不是两个候选批次。VNS产生提案后，控制面预算裁剪，再走repair这个独立slot一次；mutator不手工repair。DynamicRepair只影响阈值之后新提案，不自动重评/删除旧成员或将Problem边界改成[-1,1]。本例确定性叶子不需要RNG传播，不能据此推断任意有状态嵌套wrapper可checkpoint。

**怎样判断接对：** 本次flow.json候选为二维、raw目标等于坐标平方和、raw违反量为0。k=0/1才命中两个路由；没有default_mutator时，未知k明确抛KeyError。generation阈值以已提交主流程计数为准，不按尝试次数/各VNS局部k计数。RepresentationCapabilities只证明声明与方法存在，不证明算法或数学性质；它不要求叶算子伪装init/encode/decode。

**运行入口：** 使用共用正式default组入口，原L0负责资源；本例serial不创建线程池或自发申请并行。不是先外部运行两个算子再把结果强塞Solver。

### 变体一：先收缩再沿选定方向移动

**目的：** 展示变化的顺序确实改变候选，不能把它们当无序组件集合。**改在哪里：** pipeline/routed.py中build_pipeline完整替换为下列函数，保留原imports/classes：

```python
def build_pipeline():
    route = ContextDispatchMutator(routes={"0": AxisShift(1.), "1": AxisShift(-1.)},
        selector_key=KEY_VNS_K, strict=True)
    data_flow = PipelineOrchestrator(mutate_policy=OrchestrationPolicy(mode="serial",
        operators=(Contraction(), route)), repair_operator=DynamicRepair(
            stages=((0, ClipRepair(-5., 5.)), (3, ClipRepair(-1., 1.)))))
    return RepresentationPipeline(initializer=InitialPoint(), mutator=data_flow, repair=data_flow)
```

**行为变化：** 原 `.8*(x+d)` 变成 `.8*x+d`，d由局部k决定；最终仍同一个问题repair。**限制：** 确定性不代表顺序可交换；generic wrapper不传UnitInputs，需Unit的叶变异须走所属Adapter的正式接缝，不能藏在这个wrapper里。

## flow.joint_repair · Problem与Unit对同一最终提案共同验收

**什么时候用：** 问题要求0..1，而搜索结构只允许候选在0..cap，并且结构current必须与最终版本一致。问题修复后再做Unit修改，还要重新验证问题，不能仅相信最后一个回调没报错。

**先准备什么：** 本书共用完整Project的第二份独立副本。一维平方目标、确定性初点.8、Gaussian population_size=1。单行是明确限制，避免凭空宣称已支持任意部分接纳投影。UnitRepair只处理本叶TrajectoryUnit草稿，不能挂到容器或其它半径算法。

**放在哪：** 替换config.py、problem/__init__.py、build_solver.py，新建pipeline/joint.py。保留共用报告/solver/flow.py；原路由例文件不启用。两个Protocol用真实实现满足，不实例化Protocol本身。

**接入步骤：** config.py：

```python
CAP = .5
```

```python
# cases/composite/pipeline/joint.py
import numpy as np
from blackbase.types import CandidateBatch
from nsgablack.representation import RepresentationPipeline, ProblemRepair, UnitRepair

class Box:
    def initialize(self, problem, context):
        return np.array([.8])
    def repair(self, candidate, context):
        return np.clip(np.asarray(candidate, dtype=float), 0., 1.)
    def validate(self, candidate, context):
        values = candidate.as_array()
        return bool(values.shape == (1,) and np.all(np.isfinite(values))
                    and np.all((values >= 0.) & (values <= 1.)))

class CappedTrajectory:
    def __init__(self, cap):
        self.cap = float(cap)
        if not 0. < self.cap <= 1.:
            raise ValueError("cap must intersect the declared Problem interval")
    def repair(self, unit, evidence, context):
        if len(evidence.after.semantic_states) != 1:
            raise ValueError("this repair only supports the declared single proposal")
        result = CandidateBatch.from_candidates([
            state.with_values(np.clip(state.as_array(), 0., self.cap))
            for state in evidence.after.semantic_states],
            candidate_tokens=evidence.after.candidate_tokens)
        unit.current = result.numeric_matrix[0].copy()
        return result
    def validate(self, unit, evidence, context):
        values = evidence.after.numeric_matrix
        return bool(values.shape == (1, 1) and np.all(np.isfinite(values))
                    and np.all((values >= 0.) & (values <= self.cap))
                    and np.array_equal(unit.current, values[0]))

def build_pipeline():
    box = Box()
    if not isinstance(box, ProblemRepair):
        raise TypeError("expected repair plus read-only semantic validate")
    return RepresentationPipeline(initializer=box, repair=box)

def build_unit_repair(cap):
    repair = CappedTrajectory(cap)
    if not isinstance(repair, UnitRepair):
        raise TypeError("expected structure repair and read-only validation")
    return repair
```

```python
# cases/composite/problem/__init__.py
import numpy as np
from nsgablack.core import BlackBoxProblem

class BoundedSquare(BlackBoxProblem):
    def __init__(self):
        super().__init__(dimension=1, bounds=[(0., 1.)], objectives=["square"])
    def evaluate(self, candidate):
        return [float(np.asarray(candidate)[0]**2)]
    def evaluate_constraints(self, candidate):
        x = np.asarray(candidate, dtype=float)
        return [float(np.maximum(-x, 0.).sum()+np.maximum(x-1., 0.).sum())]

def build_problem():
    return BoundedSquare()
```

```python
# cases/composite/build_solver.py
from nsgablack.adapters import GaussianSearchAdapter
from nsgablack.representation import JointRepairPolicy
from .config import CAP
from .pipeline.joint import build_pipeline, build_unit_repair
from .problem import build_problem
from .solver.flow import build_flow

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config or component_overrides:
        raise ValueError("this repair recipe declares one leaf and one proposal")
    search = GaussianSearchAdapter(population_size=1, mutation_scale=.2,
                                   objective_aggregation="first")
    search.set_unit_repair(build_unit_repair(CAP))
    return build_flow(build_problem(), build_pipeline(), search,
        resource_context=resource_context, joint_repair_policy=JointRepairPolicy(max_rounds=1))
```

JointRepair使用baseline/draft；UnitRepair不修改真实owner，返回批次保留token/行数/维度。控制面验证Problem与Unit接受的是同一个最终版本，再通知原Adapter对账、求值、接纳和update；步失败按正式参与者回滚。此组件没有计数器/RNG/服务状态，不另造一套checkpoint。

**怎样判断接对：** 本次flow.json最终一行0..CAP，raw平方目标与该版本一致，违反量0；初点.8应先被限制到CAP而不是沿用.8分数。步骤证据的joint_repair应verified，正式Event/Disposition保留相应收据；本地flow.json只是最终选择观察，没有宣称自己导出了完整证据。没有Problem/Provider调用之前的非法组合不能因Unit.validate成功而放行。

**运行入口：** 同共用正式default组入口，保留Project L0。若改成多行，必须实现匹配算法的project_admission并保留Adapter已经压缩的坐标；本单行例没有这项能力，不把它推广为种群/多方向/取消恢复证明。零接纳由现有事务恢复baseline，不自行重置全局预算。

### 变体一：允许更大的结构区域，仍由同一Problem定义原始目标

**目的：** 将Unit的局部上限从.5放宽到.8，而不改变问题0..1的可行性。**改在哪里：** config.py完整替换：

```python
CAP = .8
```

**行为变化：** 初点.8可完整保留，后续Gaussian候选仍要经过两个验证器。**限制：** 不是关闭ProblemRepair，也不允许cap>1“帮忙通过”；需不相交范围时应得到显式拒绝，不能靠无限repair循环或清零约束掩盖。

## flow.operator_binding · 有状态DE选择器由真实所有者保存，不复制对象图

**什么时候用：** 比较target/trial时既要严格改善才替换，又想保留已完成比较次数用于解释运行；该计数属于选择器状态，必须跟所属DE的步骤回滚/checkpoint走。

**先准备什么：** 《EVOLUTIONARY_ALGORITHM_APPLICATIONS_CN.md》的adapter.de完整配方，独立assembled_parallel_cases副本/de_bowl，原二维BowlProblem、12成员/12批、资源与Project结果入口。原DE工厂由规范builder实际调用，不给共享selector对象绑定多个实例。

**放在哪：** 完整替换adapter/search.py；将原build_solver.py保存为base_solver.py，再保存下面的薄规范入口。新建plugins/binding_report.py。原DE数据/Problem/Pipeline与其它SA Case不改。

**接入步骤：** checkpoint_identity只含稳定规则；计数在get_state/set_state中显式维护。set_selector/构造参数会自动创建OperatorBinding，不手工叠加第二个绑定所有者。

```python
# cases/de_bowl/adapter/search.py
from nsgablack.adapters import DifferentialEvolutionAdapter, DEConfig
from nsgablack.representation import UniformInitializer
from ..config import POPULATION_SIZE, BATCH_SIZE

class ComparisonCounter:
    stateless = False
    def __init__(self):
        self.count = 0
    def checkpoint_identity(self):
        return {"schema": "case.strict_de_counter/v1", "tie": "keep_target"}
    def get_state(self):
        return {"count": self.count}
    def set_state(self, state):
        count = state["count"]
        if type(count) is not int or count < 0:
            raise ValueError("comparison count must be a nonnegative integer")
        self.count = count
    def select(self, request, *, rng):
        if request.purpose != "replacement" or request.count != 1:
            raise ValueError("this selector only compares a frozen target and trial")
        if request.scores is None or len(request.scores) != 2:
            raise ValueError("two proposal-time scores are required")
        self.count += 1
        return [1 if request.scores[1] < request.scores[0] else 0]

def build_adapter():
    return DifferentialEvolutionAdapter(name="de_bowl",
        initializer=UniformInitializer(-4., 4.), selector=ComparisonCounter(),
        config=DEConfig(population_size=POPULATION_SIZE, batch_size=BATCH_SIZE,
            differential_weight=.7, crossover_rate=.9,
            strategy="rand1bin", objective_aggregation="sum"))
```

```python
# cases/de_bowl/plugins/binding_report.py
from nsgablack.adapters.operator_binding import OperatorBinding
from nsgablack.plugins.base import Plugin
from nsgablack.utils.engineering.file_io import atomic_write_json

class BindingReport(Plugin):
    def __init__(self, search, output):
        super().__init__(name="operator_binding_report")
        self.search, self.output = search, output
    def on_solver_finish(self, result):
        binding = self.search.get_local_operator_bindings()["selector"]
        if not isinstance(binding, OperatorBinding):
            raise TypeError("expected the real Adapter-owned binding")
        self.payload = {"run_id": self.solver.run_session.run_id,
                        "selector": binding.get_state()}
    def on_solver_finalized(self, result):
        atomic_write_json(self.output, self.payload)
```

```python
# cases/de_bowl/build_solver.py
from pathlib import Path
from .base_solver import build_solver as build_base_solver
from .plugins.binding_report import BindingReport

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if component_overrides:
        raise ValueError("this recipe inspects its declared DE owner")
    solver = build_base_solver(config=config, resource_context=resource_context,
                               component_overrides=component_overrides)
    solver.add_plugin(BindingReport(solver.adapter,
        Path(__file__).resolve().parents[2]/"results"/"operator_binding.json"))
    return solver
```

OperatorBinding仅复制组件codec返回的有限值，不deepcopy锁/Session；恢复核对schema/method/module/class/identity/stateless。它不独立运行或申请资源，DE把operator_bindings状态纳入自己的事务。真实get_local_operator_bindings只给本地所有者，不能沿wrapper乱猜孩子。

**怎样判断接对：** 新results/operator_binding.json有schema=nsgablack.operator_binding/v1、method=select、stateless=False与state.count非负整数。初始化不一定调用replacement；失败尝试已回滚的比较不应留在count，不能先验地写成generation×batch_size。已有原Project的DE最佳结果仍以正式本次输出为准，计数不改变raw目标。

**运行入口：** 原assembled_parallel_cases的正式run_project.py或原run_and_report.py；该原报告针对DE预算仍按实际配置核对，SA独立运行。没有本章运行/失败注入/checkpoint执行收据。

### 变体一：只保留稳定规则，不记比较次数

**目的：** 不需要观测状态时复用原无状态严格比较器。**改在哪里：** 将本节ComparisonCounter类完整替换为下面类，工厂仍调用同名构造：

```python
class ComparisonCounter:
    stateless = True
    def checkpoint_identity(self):
        return {"schema": "case.strict_de_stateless/v1", "tie": "keep_target"}
    def select(self, request, *, rng):
        if request.purpose != "replacement" or request.count != 1:
            raise ValueError("replacement pair required")
        if request.scores is None or len(request.scores) != 2:
            raise ValueError("two proposal-time scores required")
        return [1 if request.scores[1] < request.scores[0] else 0]
```

**行为变化：** 选择结果保持规则，binding的state为空、stateless=True，报告不再有count。**限制：** 两类identity不同，旧有状态checkpoint不能假装兼容；声明stateless却偷偷维护计数会违反契约，绑定不是任意Python副作用沙箱。

源码：representation/base.py、context_mutators.py、dynamic.py、orchestrator.py、repair_contracts.py；共享blackbase.kernel编排与blackbase.representation能力声明；adapters/gaussian_search、differential_evolution、operations.py、operator_binding.py和core联合修复控制面。本页没有运行这些配方或修复核心实现。
