# 池交接：准备恢复组合与逐起点任务分开装配

本书复用ORCHESTRATION_ADAPTER_APPLICATIONS_CN的完整正式host：catalog_recipes Project副本、composite Case、Plateau Problem、问题管线、完整builder与OrchestrationReport。每节在自己的独立副本应用，均只替换adapter/composition.py。没有运行搜索、执行模型或调用服务。

## orchestration.pool_search · 先准备足够候选，再运行两个私有种群

**什么时候用：** 单轨迹算法先产出起点，两种群独立接手；检测停滞后唤醒单轨迹，再将其新候选送回种群竞争。这个专用状态机不是任意DAG，也不是完整子Case嵌套。

**先准备什么：** 完成host全部文件。当前PoolSearchSpec要求接收方同时支持initialize和compete；SA需支持显式restart及initialize。候选是同一个二维Problem，Project只授权本Case一份资源，不因三个搜索实例分配三次lease。

**放在哪：** 完整替换Case的adapter/composition.py。

**接入步骤：**

```python
from nsgablack.adapters import (PoolSearchAdapter, PoolSearchSpec,
    NSGA2Adapter, SPEA2Adapter, SimulatedAnnealingAdapter)
from nsgablack.representation import (UniformInitializer,
    GaussianMutation, ContextGaussianMutation)

INITIAL_COUNT = 3
MAX_STEPS = 10


def build_bundle():
    producer = SimulatedAnnealingAdapter(name="seed_and_recovery_sa",
        batch_size=3, initial_temperature=.4, cooling_rate=.9, base_sigma=.04,
        initializer=UniformInitializer(-.15, .15),
        mutator=ContextGaussianMutation(base_sigma=.04))
    a = NSGA2Adapter(name="population_a", population_size=3, offspring_size=2,
        crossover_rate=0., mutator=GaussianMutation(sigma=.04))
    b = SPEA2Adapter(name="population_b", population_size=3, offspring_size=2,
        mutator=GaussianMutation(sigma=.04))
    root = PoolSearchAdapter(producer,
        [PoolSearchSpec(a, initial_count=INITIAL_COUNT),
         PoolSearchSpec(b, initial_count=INITIAL_COUNT)],
        stagnation_steps=1, recovery_steps=2, restart_recovery=True,
        name="pooled_search")
    return root, {"producer": producer, "population_a": a, "population_b": b}, []
```

preparing阶段只调用producer，累计**被接纳且提交**的候选数达到两份initial_count之和后才转search。初始SA先评估基准点，所以一次调用不必交足batch_size行。此处6是分发的最低准备量，池可存更多记录，Unit容量仍各3。按准备时点的引用顺序切成不相交输入；值相等不能替代不同身份。预算裁剪/部分接纳不提前消耗未处理输入。

search阶段两个种群各消费输入并独立运行。输入未完成不计停滞；默认metric是本批 `min(sum(raw_objectives)+1e6*raw_violation)`，与选择偏好无关。一次未改善达到stagnation_steps=1就进入recovery。默认恢复seed是本组合最新已发布候选，**不是最优候选**；producer.restart_search后按自己的SA语义运行2次更新。

return阶段取恢复开始之后由本组合发布的新候选，对每个种群建立compete输入，**重新评估并按接收方规则竞争**。它不把SA温度/Unit交给种群，也不保证新候选最终留在种群。完成后回search。整个步骤、原提案repair/disposition、各子状态、输入游标与池发布共用原控制面事务；这里没有另一个求值循环。

**怎样判断接对：** orchestration.json的records[*].phase可看到提交后的preparing/search/recovery/return切换，owners分别列实际Unit与种群精确成员。producer没有L2成员refs并不表示没运行；看其runtime温度/当前点。任何根accepted记录数都不能代替三个算法的当前成员。多个候选数值在平坦区同为0，也有独立SolutionRef版本。10步只是观察窗口，不保证所有平台、参数或接纳策略都完成相同次数恢复。

**运行入口：** host副本根 `python run_project.py --check --build-check` 后 `python run_project.py`。原始实物参考为examples/cases/assembled_pool_recovery，本书新配方未运行，不引用它已有结果文件当收据。

### 变体一：初始输入量增加，种群容量保持3

**目的：** 区分池输入配额与算法容量，观察接收方在初始化时处理更多已授权候选。

**改在哪里：** 同一个完整工厂仅修改常量。

```python
INITIAL_COUNT = 4
```

**行为变化：** preparing至少积累8个接纳候选，两种群各获得4个初始化引用，各自仍按容量3选成员。**限制：** 准备更慢、评估更多，MAX_STEPS=10可能不足观察完整恢复；这不构成池容量4或最优性的证明。

## orchestration.pool_task · 两个VNS逐起点精修，冻结同一批输入

**什么时候用：** 从已存在的普通具名池读取多个起点，给两个独立单轨迹算法分工；每个起点都先重新评估，之后做有限邻域，并交回各任务最终选择。

**先准备什么：** 完整host。根池已由Solver创建；本Case启动插件只调用正式init_population再创建一个普通reference引用集合，不构建算法Unit、不预填反馈。后续初始化候选必须经过正式repair/evaluate/admission才能成为已评估解。

**放在哪：** 新增 `plugins/task_source.py`，完整替换adapter/composition.py；host builder已按extras顺序挂载插件，无需新增手工调用。

**接入步骤：**

```python
# cases/composite/plugins/task_source.py
from collections.abc import Mapping
from nsgablack.plugins.base import Plugin


class TaskSource(Plugin):
    def __init__(self, count):
        super().__init__(name="task_source")
        self.count, self.run_id, self.seeded = count, None, False

    def on_solver_init(self, solver):
        run_id = solver.run_session.run_id
        if self.run_id == run_id and self.seeded:
            return
        if solver.run_session.resume_loaded:
            raise ValueError("restored task source has no completed seed state")
        self.run_id, self.seeded = run_id, False
        solver.init_population(self.count, solver.build_context())
        solver.solution_pool.create_subpool("reference",
            solver.solution_pool.select(stage="initial"))
        self.seeded = True

    def get_state(self):
        return {"schema": "case.task_source/v1", "count": self.count,
            "run_id": self.run_id, "seeded": self.seeded}

    def set_state(self, state):
        if (not isinstance(state, Mapping) or state.get("schema") != "case.task_source/v1"
                or state.get("count") != self.count or type(state.get("seeded")) is not bool):
            raise ValueError("invalid task source state")
        if state["seeded"] and not isinstance(state.get("run_id"), str):
            raise ValueError("completed source needs run identity")
        self.run_id, self.seeded = state.get("run_id"), state["seeded"]
```

```python
# cases/composite/adapter/composition.py
from nsgablack.adapters import (StrategyRouterAdapter, RoleSpec,
    MultiStrategyConfig, PoolTaskSpec, VNSAdapter, VNSConfig, StrategyTask)
from nsgablack.representation import ContextGaussianMutation
from ..plugins.task_source import TaskSource

TRAJECTORY_STEPS = 3
OUTPUT = "admitted_trials"
MAX_STEPS = 20


class TaskAwareMutation(ContextGaussianMutation):
    def mutate(self, candidate, context=None):
        task = StrategyTask.from_context(context)
        if task.budget < 1 or task.role != "local":
            raise ValueError("expected a positive local proposal task")
        return super().mutate(candidate, context)


def make_local(unit_id):
    return VNSAdapter(VNSConfig(batch_size=2, k_max=2, base_sigma=.06,
        restart_on_stagnation=False), name=f"local_{unit_id}",
        mutator=TaskAwareMutation(base_sigma=.06))


def build_bundle():
    root = StrategyRouterAdapter(roles=[RoleSpec("local", make_local, n_units=2,
        pool_task=PoolTaskSpec("reference", mode="refine", count="all",
            distribution="partition", steps=TRAJECTORY_STEPS, shuffle=False,
            output=OUTPUT))], config=MultiStrategyConfig(
                total_batch_size=4, adapt_weights=False), name="local_workers")
    owners = {f"local_{unit.unit_id}": unit.adapter.inner for unit in root.units}
    return root, owners, [TaskSource(4)]
```

RoleSpec实际由Router包成两个PoolTaskAdapter；它们分别有独立VNS与任务状态，不是传同一个VNS对象两次。reference必须启动时已经存在；字符串不是创建指令。count=all表示选定这批4个引用，partition按worker分配，不是每worker都重复全部起点。每个起点steps=3包含基准重新求值的一步，余下两步才提出邻域；并非“三次变化外加基准”。任务开始冻结输入，不在每步重新读取增长中的reference。

TaskAwareMutation实际消费本次StrategyTask；预算是Router原分配提案额度，接纳后不会改写它。结构与投影不保存在这个调用上下文里。Router的候选附带嵌套StrategyOrigin；报告在完成任务的精确最终版本上读取from_candidate，不能从数值相同或共享role键反推来源。Task id属于调用，owner_path属于实例；两者均不是Project Case identity或SolutionRef。

output=admitted_trials累计保存接纳过的候选；**不是最终结果池**。真正交付用每个worker.get_pool_task_results(control)，它要求本请求done并验证结果视图身份/修订/解释/有序引用。host报告仅在done后读取，且将final_origins和final_refs同序保存。读不到完成结果就不能把中途的最后一行冒充最好候选。

新邻域通过正式管线repair再评估，ProposalRepair先对账，BatchDisposition再处理预算/接纳索引，update只吃接纳行。任务持有的访问范围不允许mutator任意读取其它池；将来跨池变化须显式change_sources/change_allow_main，不能在普通回调里读取根池绕过声明。本例没有额外donor权限。

**怎样判断接对：** report tasks中的两worker role相同、unit_id不同、冻结request与进度分开；done任务有final_refs/final_origins，引用数对应该worker完成起点的最终选择数。owners.local_*只有轨迹，refs为空合法。不同worker即使提出相同数值，也不能合并来源身份。root运行结束若仍running不算此精修请求完成；20是上限，不应写成必有20代。

**运行入口：** 同一副本根 `python run_project.py --check --build-check` 后 `python run_project.py`，读取orchestration.json。参考现有pool_workflow_pilot与assembled_ga_vns的正式任务接线，本文新Case未运行。

### 变体一：每个起点只做基准重新评估

**目的：** 验证任务配额“包括起点”而非隐式额外赠送一步。

**改在哪里：** 同composition.py只替换常量。

```python
TRAJECTORY_STEPS = 1
```

**行为变化：** 每个起点重新评估后立即交付已评估最终选择，不执行TaskAwareMutation；原始initial引用和正式接纳版本分别有自己的身份语义。**限制：** 这是接线基线，不是VNS已经做过局部搜索；任务output仍可能保存这些基准接纳记录。

### 变体二：不累计所有试探记录，仍交付最终结果

**目的：** 区分最终选择交付与可选历史输出，控制额外引用集合。

**改在哪里：** 在完整工厂文件中只修改OUTPUT，PoolTaskSpec已显式读取它。

```python
OUTPUT = None
```

**行为变化：** 不再维护该累计历史名，完成请求的get_pool_task_results与final_refs仍可使用。**限制：** 底层池保留策略与Snapshot回收另有职责；省略历史不等于物理删除全部未选解。

源码：adapters/pool_search.py、pool_tasks.py、multi_strategy/adapter.py、strategy_task.py；examples/cases/pool_workflow_pilot/pool_source.py提供恢复不重复播种模式。
