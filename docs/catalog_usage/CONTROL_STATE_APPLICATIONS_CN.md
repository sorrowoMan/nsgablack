# 控制面、步骤状态与结果发布：一份完整的搜索 Case

这本书教的是如何接入已有控制面，不让用户再实现一次运行循环。本轮只核对源码、接口和文档代码；没有执行本书的求解、恢复或故障注入。`RuntimeParticipant` 的外层 Mapping 检查不能证明嵌套对象安全。

## control.state.owner · 给搜索增加可恢复的本地计数

**什么时候用：** 一个自定义搜索语义需要保存自己的少量状态，同时参加步骤异常回滚和 checkpoint；还想在运行结束时核对逻辑步数、实际尝试和权威快照。不是给 Unit、锁或数据库连接添加通用 deepcopy。

**先准备什么：** 独立复制完整 `examples/cases/bias_gallery/` Project，保留 Project/L0/default 组、规范入口与 Case 包。使用当前 nsgablack、blackbase、NumPy，保留 `problem/example_problem.py::SphereProblem`。以下两个连续章节是一套文件。代码默认 EvolutionSolver 的 NSGA-II，二维候选、12个成员、6个逻辑提交预算。

**放在哪：** 新建 `cases/bias_gallery/runtime/local_state.py`、`plugins/control_report.py`，替换本 Case 的 build_solver.py。runtime 只声明自己的状态，不申请新资源；现有 Project 发放 resource_context。

**接入步骤：** local_state.py 完整内容：

```python
from blackbase.runtime import RuntimeParticipant
from nsgablack.core.semantic_extension import SolverSemanticExtension


class LocalState:
    name = "case.local_state"

    def __init__(self):
        self.started = 0
        self.committed = 0

    def get_state(self):
        return dict(started=int(self.started), committed=int(self.committed))

    def set_state(self, state):
        if set(state) != {"started", "committed"}:
            raise ValueError("unexpected local state schema")
        self.started, self.committed = int(state["started"]), int(state["committed"])

    def snapshot_step_state(self):
        return self.get_state()

    def restore_step_state(self, state):
        self.set_state(state)

    def commit_step_state(self, state):
        return None

    def step_transaction_children(self):
        return ()


class LocalSemantics(SolverSemanticExtension):
    name = "case.local_semantics"

    def __init__(self, state):
        if not isinstance(state, RuntimeParticipant):
            raise TypeError("state must implement the explicit transaction protocol")
        self.state = state

    def prepare_run(self, solver):
        self.state.set_state(dict(started=0, committed=0))

    def before_step(self, solver):
        self.state.started += 1

    def after_step_committed(self, solver, outcome):
        self.state.committed += 1

    def checkpoint_components(self, solver):
        return {"case_local_state": self.state}
```

同一个 state 用两种正式接缝登记：register_state_participant 提供步骤异常恢复；extension.checkpoint_components 提供有稳定名称的持久状态。两者不是自动互相推导。快照只包含本类两个整数，capture 只读；没有复制 solver、Adapter 或 __dict__。父级若拥有独立子参与者，应在 step_transaction_children 中列出它，不能把孩子状态再塞进自己的快照。

started 是进入 before_step 的正常尝试计数；异常回滚会恢复它，但正常 idle/rejected 的策略状态并不一概回滚，因此不要把它命名成“已提交代数”。committed 在语义提交之后增加；这个后置回调失败也不能撤销已提交的评估和代数。全局实际尝试仍以 RunSession 为准，它有意不参加步骤回滚。

SolverSemanticExtension 不接管 propose/update/接纳；它提供显式语义扩展点。普通算法改法应优先使用 Adapter、Unit、Pipeline；日志优先用 Plugin。此例不需要额外 context 键，也不把计数当成另一份调度权威。

## control.state.wiring · 完整装配、观察与检查

plugins/control_report.py 完整内容：

```python
import json
from pathlib import Path
from blackbase.participation import ParticipationContract
from nsgablack.plugins.base import Plugin


class ControlReport(Plugin):
    participation = ParticipationContract(vetoes=("finalization",))

    def __init__(self, state, output):
        super().__init__(name="case_control_report")
        self.state, self.output = state, Path(output)

    def on_solver_finish(self, result):
        solver = self.solver
        edge = solver.get_population_authority_identity()
        self.payload = dict(run_id=solver.run_session.run_id,
            local=self.state.get_state(), progress=solver.export_run_progress_state(),
            population_mode=solver.population_authority.mode,
            publication=None if edge is None else edge.as_dict(),
            population_is_owner=solver.population is solver.population_authority.population,
            result_tag=result.get("case_report", {}))

    def on_solver_finalization_prepare(self, result):
        if self.state.committed <= 0:
            raise ValueError("this recipe requires at least one committed search step")

    def on_solver_finalized(self, result):
        self.payload["finalization"] = result.get("finalization")
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(json.dumps(self.payload, ensure_ascii=False,
            allow_nan=False, indent=2), encoding="utf-8")
```

这个 ParticipationContract 只授予 finalization 否决；观察不需要决定权限。observe 默认放开不表示成本为零，写文件仍需自己选择是否装配。finalized 才写的文件是本地报告副本，不是 ArtifactProvider 发布收据；若通知写盘失败，已封存结果不会因此变成未提交。

build_solver.py 完整内容：

```python
from pathlib import Path
from blackbase.runtime import FinalizationHooks
from nsgablack.core import EvolutionSolver, ComposableSolver
from nsgablack.core.blank_solver import SolverBase
from nsgablack.adapters import NSGA2Adapter
from nsgablack.representation import RepresentationPipeline, UniformInitializer, GaussianMutation, ClipRepair
from nsgablack.utils.engineering import configure_logging
from .problem.example_problem import SphereProblem
from .runtime.local_state import LocalState, LocalSemantics
from .plugins.control_report import ControlReport

MODE = "evolution"


def prepare_result(result):
    return {**dict(result), "case_report": {"purpose": "control_state_wiring"}}


def build_solver(run_id=None, *, strategy=None, quickstart=False,
                 resource_context=None, component_overrides=None):
    if strategy not in (None, "", "default", "none") or component_overrides:
        raise ValueError("use the explicit MODE and components of this recipe")
    configure_logging(level="INFO", json_format=True, force=False)
    pipeline = RepresentationPipeline(initializer=UniformInitializer(-5., 5.),
        mutator=GaussianMutation(sigma=.15), repair=ClipRepair(-5., 5.))
    common = dict(problem=SphereProblem(dimension=2), representation_pipeline=pipeline,
                  resource_context=resource_context, plugin_strict=True, snapshot_strict=True)
    if MODE == "evolution":
        solver = EvolutionSolver(**common, pop_size=12, max_generations=6, parallel=False)
    elif MODE == "composable":
        solver = ComposableSolver(**common,
            adapter=NSGA2Adapter(population_size=12, offspring_size=6))
    else:
        raise ValueError("unknown solver mode")
    if not isinstance(solver, SolverBase):
        raise TypeError("expected the shared optimization lifecycle")
    solver.set_random_seed(17)
    solver.set_max_steps(6)
    solver.set_bias_module(None, enable=False)
    state = LocalState()
    solver.register_state_participant(state)
    solver.register_semantic_extension(LocalSemantics(state))
    solver.finalization_hooks = FinalizationHooks(prepare_result=prepare_result)
    solver.add_plugin(ControlReport(state, Path(__file__).resolve().parents[2]
                                   / "results" / "control.json"))
    return solver
```

EvolutionSolver 提供进化配置和默认 NSGA-II，ComposableSolver 明确接一个 Adapter；两者都使用 SolverBase 的运行资源、生命周期和状态门面。SolverBase.step 本身抛 NotImplementedError，不能把它当成已经带算法的求解器。这里通过真正子类消费它，不建议用户为了换算法去覆盖基类运行循环。

PopulationAuthority 已由 Solver 构造并登记；solver.population/objectives 等只是同一 owner 的视图。不自行 new 一份 owner 接管当前种群，不从日志回填权威数组。RunSession 也由 Solver 创建；export_run_progress_state 导出可传输进度，RLock/排队回调/墙钟起点不会跟着复制。尝试、消耗和耗时不能因为一步失败被抹去。

FinalizationHooks 的 prepare_result 这里只增加普通结果元信息，不写文件、不发布模型。它发生在 finishing/teardown 前；严格发布否决仍由 Plugin 的 finalization_prepare 实现。要实现外部 Artifact 事务，prepare/freeze/abort 三个口必须成组，且不能同时指定 publish；仅把三种函数放进这个容器并不会自动创建存储事务。本例没有冒充 Artifact 实现。

**怎样判断接对：** 本次正式 Case 成功后看 results/control.json。run_id 应对应本次运行；population_is_owner 为 true；committed 与本次正常搜索提交相符，progress 中实际尝试可以更多；publication 是当前正式权威边。result_tag 的 purpose 来自 prepare_result；finalization 来自正式封存通知。不要用旧文件或 started 推断成功；本轮没有验证故障回滚/恢复。configure_logging 只在无现有 handler 时安装格式器，force=False 不会强制改宿主日志，看到非 JSON 不代表算法失败。

**运行入口：** 完整副本根先 `python run_project.py --check --build-check`，再 `python run_project.py`。只需要检查装配时执行第一条；第二条才产生真实求解结果。不要直接循环调用 solver.step，也不要从本地报告再次恢复一个正在运行的对象。

### 变体一：显式 Adapter 工厂

**目的：** 使用同一控制面接缝，但独立选择算法与种群预算。**改在哪里：** build_solver.py 的 MODE 改为以下值，其余文件原样保留。

```python
MODE = "composable"
```

**行为变化：** Adapter 使用显式 NSGA2Config，非 EvolutionSolver 默认附加状态。**限制：** 两种配置不承诺逐随机数相同；切换类型后不要加载旧模式 checkpoint。

### 变体二：对小预算取消严格发布否决

**目的：** 某些合法诊断流程可能没有搜索提交，不适合本例的“必须有提交”门槛。**改在哪里：** ControlReport 中改写以下声明和方法。

```python
participation = ParticipationContract()

def on_solver_finalization_prepare(self, result):
    return None
```

**行为变化：** 观察和报告继续，零提交不会被本观察器否决。**限制：** 这不改变 Problem 失败、快照错误或全局完成策略；不能用它吞掉主流程错误。

源码核对：core/semantic_extension.py、core/state/run.py、core/state/population_authority.py、core/solver_helpers/run_helpers.py、blackbase.runtime 与 blackbase.participation。
