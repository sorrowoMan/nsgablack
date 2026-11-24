# 内层组件计算：回传、守卫与观察桥

TaskInnerRuntimeEvaluator是**低层进程内组件**接缝，不是完整子Case边界。完整内层优化/训练Case必须通过CaseRuntime.invoke或CaseInnerRuntimeEvaluator获得独立身份、子L0授权、预算与Artifact发布。本书只装配一个无状态解析计算，不创建私有Solver循环，不把它冒称GA+VNS嵌套。本轮仅源码与静态核对，未执行算法、组件或服务。

## lifecycle.inner_component · 一个外层候选对应一次解析内层计算

**什么时候用：** Problem评估需要一个已明确语义的组件计算结果，再将其投影为外层目标；想观察旧on_inner_guard/on_inner_result桥具体消费什么。这里不需要内层算法搜索。

**先准备什么：** 完整复制 `nsgablack/examples/cases/catalog_recipes` Project，保留默认stage_1/composite、Project L0与规范入口。需当前框架、NumPy。候选x是一个二维外层设计；内层解析响应y不是替换x的新候选，也没有新内层SolutionPool。

**放在哪：** 下列路径相对 `cases/composite/`。新增完整Problem、pipeline、adapter、plugin文件，最后完整替换builder。Project根使用原run_project.py，不另起内层运行器。

**接入步骤：** 新建problem/response_component.py：

```python
import numpy as np
from nsgablack.core import BlackBoxProblem


def solve_response(inner_problem, inner_solver, context):
    if inner_solver is not None:
        raise ValueError("this recipe is a pure component, not a hidden Solver")
    target = np.asarray(inner_problem["target"], dtype=float)
    # Analytic argmin_y ||y-target||² + .25*||y||².
    y = target / 1.25
    cost = float(np.sum((y-target)**2) + .25*np.sum(y**2))
    return {"status": "completed", "response": y.tolist(), "cost": cost}


class ResponseProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="analytic_response_design", dimension=2,
            bounds=[(-2., 2.)] * 2, objectives=["response_plus_design_cost"])

    def build_inner_task(self, candidate, context):
        return {"inner_problem": {"target": np.asarray(candidate, dtype=float).tolist()},
            "run_inner": solve_response}

    def evaluate_from_inner_result(self, candidate, result, context):
        if result["status"] != "completed":
            raise ValueError("the response component did not complete")
        x = np.asarray(candidate, dtype=float)
        return [float(result["cost"]) + .05*float(x @ x)], 0.

    def evaluate(self, candidate):
        raise RuntimeError("the declared inner runtime must handle this candidate")

    def evaluate_constraints(self, candidate):
        x = np.asarray(candidate, dtype=float)
        return np.maximum(-2.-x, 0.) + np.maximum(x-2., 0.)
```

y只是内层组件输出，外层仍评价x；按解析式，cost=.2*||x||²，外层目标=.25*||x||²。不要把y写成x的候选身份，也不要把这个目标说成y本身的评分。

新建pipeline/response_pipeline.py与adapter/response_search.py：

```python
# pipeline/response_pipeline.py
from nsgablack.representation import RepresentationPipeline, UniformInitializer, ClipRepair


def build_pipeline():
    return RepresentationPipeline(initializer=UniformInitializer(-2., 2.),
        repair=ClipRepair(-2., 2.))
```

```python
# adapter/response_search.py
from nsgablack.adapters import GaussianSearchAdapter, GaussianSearchConfig


def build_adapter():
    return GaussianSearchAdapter(config=GaussianSearchConfig(population_size=2,
        mutation_scale=.15, initialization="center", objective_aggregation="sum",
        random_seed=17))
```

新建plugins/response_bridges.py。显式保留三个实际组件对象供报告读取：

```python
import numpy as np
from nsgablack.core.nested_solver import InnerRuntimeConfig, TaskInnerRuntimeEvaluator
from nsgablack.plugins import (ContractBridgePlugin, BridgeRule,
    TimeoutBudgetPlugin, TimeoutBudgetConfig)
from nsgablack.plugins.base import Plugin
from nsgablack.utils.engineering.file_io import atomic_write_json

ALLOW_OVERWRITE = True
MAX_CALLS = 100


def build_components():
    runtime = TaskInnerRuntimeEvaluator(config=InnerRuntimeConfig(
        source_layer="component", target_layer="outer", fallback_penalty=1e6,
        warn_on_failure=True, max_retries=0, per_call_timeout_ms=None))
    bridge = ContractBridgePlugin(rules=[
        BridgeRule("cost", "last_component_cost", target_layer="outer")],
        allow_overwrite=ALLOW_OVERWRITE)
    budget = TimeoutBudgetPlugin(config=TimeoutBudgetConfig(
        layer="component", max_calls=MAX_CALLS, time_budget_ms=60000., fail_closed=True))
    return runtime, bridge, budget


class ResponseReport(Plugin):
    def __init__(self, runtime, bridge, budget, output):
        super().__init__(name="response_report")
        self.runtime, self.bridge, self.budget, self.output = runtime, bridge, budget, output

    def on_solver_finish(self, result):
        control = self.solver
        incumbent = control.get_incumbent()
        selected = None
        if incumbent is not None:
            values = np.asarray(incumbent.candidate, dtype=float)
            selected = {"candidate": values.tolist(),
                "expected": [.25 * float(values @ values)],
                "objectives": np.asarray(incumbent.objectives).tolist()}
        self.payload = {"run_id": control.run_session.run_id,
            "runtime_stats": dict(self.runtime.stats), "bridge": self.bridge.get_report(),
            "budget": self.budget.get_report(),
            "layer_observation": dict(getattr(control, "_layer_contexts", {})),
            "bridge_log": list(getattr(control, "_bridge_log", [])), "incumbent": selected}

    def on_solver_finalized(self, result):
        atomic_write_json(self.output, self.payload)
```

完整替换build_solver.py：

```python
from pathlib import Path
from nsgablack.core import ComposableSolver, FeasibleEvaluationAcceptance
from nsgablack.project import apply_solver_component_overrides
from .adapter.response_search import build_adapter
from .pipeline.response_pipeline import build_pipeline
from .problem.response_component import ResponseProblem
from .plugins.response_bridges import build_components, ResponseReport


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config:
        raise ValueError("edit explicit response component factories")
    runtime, bridge, budget = build_components()
    problem = ResponseProblem()
    problem.inner_runtime_evaluator = runtime
    solver = ComposableSolver(problem=problem, representation_pipeline=build_pipeline(),
        adapter=build_adapter(), resource_context=resource_context,
        evaluation_acceptance_policy=FeasibleEvaluationAcceptance())
    solver.set_bias_module(None, enable=False)
    solver.set_random_seed(17)
    solver.set_max_steps(4)
    solver.set_max_step_attempts(16)
    solver.add_plugin(bridge)
    solver.add_plugin(budget)
    solver.add_plugin(ResponseReport(runtime, bridge, budget,
        Path(__file__).resolve().parents[2] / "results" / "inner_component.json"))
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

## lifecycle.inner_contract · 回传、预算边界与两种变体

runtime放在problem.inner_runtime_evaluator，不是add_plugin；bridge/budget才是生命周期插件。执行链在普通Problem回退路径中先询问inner runtime，依次构造task、dispatch on_inner_guard、调用纯组件、dispatch on_inner_result、Problem显式映射。若另装一个覆盖所有候选的评估Provider，这条回退链可能不发生；不能仅看插件存在就认定接线生效。

ContractBridge只读result顶层cost；写入solver._layer_contexts和_bridge_log是兼容观察通道，不是权威Snapshot、共享ContextStore、池成员或子CaseArtifact。缺字段略过，transform异常会计dropped并继续；不适合承载必须存在的硬评估事实。真正决定目标的仍是evaluate_from_inner_result。报告明确把这个字典命名为layer_observation。

TimeoutBudget的max_calls实际数的是on_inner_result包：失败且没有结果包的调用、内部重试不计入_calls。time_budget_ms是从solver init起累计墙钟门禁，只在调用前看；它不强制中断正在执行的组件。fail_closed=False意味着超限仍允许执行，不能称“硬预算”。本例max_retries=0、无线程超时，避免把同一个有副作用操作重试。可选per_call_timeout_ms用线程停止等待，不能强杀Python线程；这不是安全子进程隔离。

三个组件的旧stats、Bridge层字典和计时器没有在此构成持久预算/恢复权威，本文只声明新鲜有限运行。需要跨恢复严格预算、Case取消/截止时间、内层模型/搜索资源时，改用完整CaseRuntime请求和正式预算授权，而不是把这些字段装进私有context假装契约闭合。

**怎样判断接对：** inner_component.json的runtime success/calls、bridge packets/writes与budget calls来自真实对象；incumbent.objectives应与expected一致。layer_observation只反映已收到的最近包，不能拿它当incumbent的配套结果；多候选情况下最后包与最终最好可以不同。原始约束与fallback violation仍经过硬准入，没有软Bias擦除。报告只在正式finalized后写观察副本。

**运行入口：** 副本根 `python run_project.py --check --build-check`，随后 `python run_project.py`。确认本次Case成功和run_id后读results/inner_component.json；本轮没有运行。

### 变体一：桥只保留第一次结果，而目标继续按每候选计算

**目的：** 明确观察缓存与真实反馈的权威区别。

**改在哪里：** plugins/response_bridges.py只替换常量。

```python
ALLOW_OVERWRITE = False
```

**行为变化：** layer_observation保留首个cost，后续同键计dropped；正式目标仍由每次完整result映射，不受桥缓存影响。**限制：** 不能从这个观察字典得出“当前最好”或“最后一次”的结论。

### 变体二：只允许一个结果包之后的组件调用

**目的：** 看清旧守卫数的是什么，而非误当全局求值预算。

**改在哪里：** 同文件只替换常量。

```python
MAX_CALLS = 1
```

**行为变化：** 第一包之后的guard阻止组件，runtime给有限fallback目标和正违反量，raw准入拒绝该行。**限制：** 外层评估尝试仍消耗预算；零接纳不制造generation，可能先碰16次物理尝试上限。不要把这种阻止写成一次成功的内层求解；生产硬预算应走正式Case授权。

源码：core/nested_solver.py、core/solver_helpers/evaluation_helpers.py、plugins/domain_backends/contract_bridge.py与timeout_budget.py。TaskInnerRuntimeEvaluator可承接组件计算，不代表任意私有inner_solver.run都自动具备完整Case语义。
