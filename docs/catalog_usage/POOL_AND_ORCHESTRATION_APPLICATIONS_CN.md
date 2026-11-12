# 解池与搜索编排：从基础用法改成自己的流程

这份应用稿沿现有 Project 的工厂和回调讲解，不新增运行器。所有例子均按当前源码核对；本轮没有执行文中的算法、测试、模型或命令，不把既有结果文件当成改动后的运行收据。

先分清三个不同对象：`SolutionPool` 保存运行内候选的精确版本；调用内 `Pool` 表示本次获准读取的有序引用集合；`PoolTaskSpec` 告诉实际 Adapter 怎样消费这些引用。`SearchPlanAdapter`、`StrategyChainAdapter` 和 `StrategyRouterAdapter` 负责调度，池对象本身不执行算法。

文中“替换函数”均指指定 Case 文件内的同名工厂或回调。外层 `build_solver.py`、`run_project.py`、Problem、问题修复和 Project L0 继续使用原入口。每个变体单独应用；改变了观察插件依赖的池名、角色名或结果结构时，也要同步该 Case 的观察函数，不能把旧报告当作新配方的验收。

## tool.solution_pool · 先供给候选，再按精确版本读取

**什么时候用：** 想把一批初始化候选交给 GA，或在观察/结果阶段核对原始目标、候选身份和来源。池不是另一份种群数组；两个算法读取同一候选，也各自保留自己的 Unit 和选择状态。

**先准备什么：** 使用正式 [pool_workflow_pilot/ga_partition](../../examples/cases/pool_workflow_pilot/cases/ga_partition/build_solver.py)。其 `CaseConfig` 默认有 `source_count=100`、`population_size=100`、`offspring_size=80`，三个数量分别表示源候选数、GA 容量和后代上限。`PipelineSource` 在 Solver 已有池之后调用正式初始化，登记 `stage="initial"` 的版本；它不求值，所以不能读取这些种子的 raw feedback 当作已评估结果。

**放在哪：** 保留该 Case `build_solver.py` 对 `PipelineSource` 的挂载。下面第一段是对原挂载行的工厂化写法；第二段是提交后观察或最终结果整理函数。`settings` 来自该 Case 的 CaseConfig，`control` 是同一次运行的 Solver，`owner` 是同工厂创建并持有当前成员的实际 GA 实例。

**接入步骤：**

```python
from .plugins import PipelineSource

def attach_initial_source(solver, settings):
    solver.add_plugin(PipelineSource(
        settings.source_count, working_pool=settings.working_pool,
    ))
```

在原 `build_solver` 中用 `attach_initial_source(solver, settings)` 替换原来那一行 `solver.add_plugin(PipelineSource(...))`，只挂一次。原插件已经保存运行身份、seeded 标志和恢复状态，不要另写一个每次 init 都重新播种的钩子。

```python
def read_current_members(control, owner):
    refs = tuple(owner.get_population_solution_refs(control))
    if not refs:
        return None
    batch = control.read_solutions(refs)
    raw_f, raw_v = control.solution_pool.read_raw_feedback(refs)
    return {"refs": refs, "batch": batch,
            "raw_objectives": raw_f, "raw_violations": raw_v}
```

这只读取已提交成员：`batch.numeric_matrix` 是 `(n,d)`，语义候选和 token 与 refs 同序，原始目标/违反量分别是 `(n,m)/(n,)`。普通根 `select(stage="accepted")` 是接纳历史，不是 GA 当前成员顺序。当前 Case 的观察器通过已有 `workflow_worker(solver.adapter).inner` 找实际叶实例；其它拓扑应从自己的工厂保留 owner，不能按类型名猜唯一实例。

**怎样判断接对：** 原 [workflow_trace.py](../../examples/cases/pool_workflow_pilot/workflow_trace.py) 记录 `initial.initial_refs`、`records[*].accepted_count` 和最终 `result.refs/candidates/raw_objectives/raw_violations/provenance`。初始化引用应先存在；GA 消费后才有已评估成员引用。不要把 initial 的数量写成真实求值次数。

**运行入口：** `python examples/cases/pool_workflow_pilot/run_project.py --group partition`。这里只给出现有正式入口，本轮未执行。

**配套组件 key：** `tool.pool_task_spec`、`tool.pool`、`adapter.nsga2`、`adapter.multi_strategy`。

**接口依据与验证状态：** [SolutionPool.select/read/read_raw_feedback](../../core/state/solution_pool.py)、[PipelineSource.on_solver_init](../../examples/cases/pool_workflow_pilot/pool_source.py)、[WorkflowTrace](../../examples/cases/pool_workflow_pilot/workflow_trace.py)；源码核对。

### 变体一：观察固定时点之前的已接纳历史

**目的：** 比较两个提交时点之间新增加了哪些精确版本，而不是每次读到不断增长的历史。

**改在哪里：** 在 Case 的提交后观察函数中保存当时的 `pool.timestamp`；把它作为下面函数的 `stamp` 参数传入。stamp 属于同一运行，不能把另一次运行的时钟拿来筛选。

```python
def read_accepted_at(control, stamp):
    pool = control.solution_pool
    refs = pool.select(at=stamp, stage="accepted")
    if not refs:
        return {"refs": (), "batch": None, "raw_feedback": None}
    return {"refs": refs, "batch": pool.read(refs),
            "raw_feedback": pool.read_raw_feedback(refs)}
```

**行为变化：** select 只选不晚于该逻辑时点的已发布版本；读取保留原 token 和版本，不派生新提案，不增加求值。

**限制：** 这是历史筛选，不是历史快照永久保留承诺。启用了闲置回收时，长期需要的引用还须按已有保留契约保护；读取空选择不能推断候选维数。不要把这个函数放进普通 change 去扩大任务读权限。

### 变体二：把源候选放进 workspace，让后续组合在该区域工作

**目的：** 同一 Solver 里明确隔离某个组合的工作来源，避免默认读取根区域的全部公开候选。

**改在哪里：** 在 ga_partition 的 `build_solver.py` 把构造 settings 的原行改成下面这一行，其余组装保留。原 `build_adapter(settings)` 已有 Chain 绑定分支，原 PipelineSource 也已接受同一字段。

```python
settings = CaseConfig(**{**dict(config or {}), "working_pool": "workspace"})
```

**行为变化：** 正式 Source 在首次提案前用已有 initial 引用创建普通 workspace；Chain 绑定它，内层 Router 与省略 select 的初始化任务继承该区域。新接纳候选进入最近绑定区域，池仍只保存一份候选版本。

**限制：** working_pool 必须是已发布的普通集合，名字不是“创建指令”。不要把已有算法结果视图拿来当可写工作区；首次提案后不能换绑定。读 `records[*].working_pool.refs` 与 descriptor 核对区域，不据根 accepted 历史推断区域成员。

## tool.pool · 一次选择交回成员，同时组织精英或档案

**什么时候用：** 已有一批可比较的候选，想用普通函数选择成员，并把最终成员中的精英交到具名集合。这里的 Pool 是本次回调的有序引用视图，不是任意时刻都能创建的永久容器。

**先准备什么：** 使用 [assembled_ga_vns 的 GA 生存选择](../../examples/cases/assembled_ga_vns/cases/hybrid_search/adapter/composition.py)，通过正式 Project 的 `--group elite` 或 `--group plan` 启用成套精英配置；自行配置时，须在构造原 settings 时令 `refinement_source="elite"` 并满足该 Case 的配置校验。默认 `refinement_source="population"` 不会挂载本节 selector。函数输入 pool 由 NSGA2 的 survivor 请求提供，包含当前比较用的 objectives/violations。`count` 是应保留的成员数，`elite_count` 不能被当成池容量。单目标例子的选择键可以明确用当前选择反馈；多目标仍保留非支配排序与拥挤度。

**放在哪：** 同 Case 的 `adapter/composition.py`，替换/保留它现有的 `choose_members_and_elite` 与 `selection_key`。工厂中已有 `ga.set_selector(partial(...))`，无需再开另一个选择循环。

**接入步骤：** 以下完整回调保留 NSGA 的默认比较规则，再从实际生存成员中分流精英：

```python
import numpy as np
from nsgablack.adapters import Pool
from nsgablack.utils.performance.fast_non_dominated_sort import FastNonDominatedSort

def selection_key(pool):
    return np.column_stack((pool.violations > 0.,
                            np.maximum(pool.violations, 0.),
                            pool.objectives[:, 0]))

def choose_members_and_elite(pool, *, count, elite_count, rng):
    fronts, _ = FastNonDominatedSort.sort(pool.objectives, pool.violations)
    indices = []
    for front in fronts:
        remaining = count - len(indices)
        if len(front) <= remaining:
            indices.extend(front)
        else:
            distances = FastNonDominatedSort.calculate_crowding_distance(
                pool.objectives, list(front))
            indices.extend(sorted(front, key=lambda i: float(distances[i]),
                                  reverse=True)[:remaining])
        if len(indices) == count:
            break
    members = pool.take(indices)
    elite = members.chosen(
        lambda offered: offered.top(elite_count, key=selection_key), rng=rng)
    Pool(parent=members, name="ga_elite").inject(elite, replace=True)
    return members
```

在原工厂用 `partial(choose_members_and_elite, count=settings.population_size, elite_count=settings.elite_count)` 交给 `ga.set_selector`。`chosen` 只做纯选择，不能在它的规则内部 inject；具名 inject 在外层 survivor 回调交付原池事务。`replace=True` 精确替换副池成员，不会给它偷偷追加整份旧集合。

**怎样判断接对：** 本次主返回值仍是 GA 最终成员。Pool 只在本次回调作用域内可读，不保留活 `members` 等待提交后再读。该次 GA 提交后的既有观察回调可用其 `control`（本 Case 的 solver）与装配时保留的真实 `ga` 实例，通过 `ga.get_population_solution_refs(control)` 取得当前成员引用，再与 `control.solution_pool.subpool_refs("ga_elite")` 核对；副池引用应全部属于同次最终成员。原 elite/plan 观察记录的 `elite.refs`、`ga_member_refs` 也可用于核对。Unit 更新或后续提交失败时，副池不能提前成为下游输入。

**运行入口：** `python examples/cases/assembled_ga_vns/run_project.py --group elite` 或 `--group plan`，按原 Case 配置选择。未执行。

**配套组件 key：** `adapter.nsga2`、`tool.solution_pool`、`tool.population_change`、`tool.pool_task_spec`。

**接口依据与验证状态：** [ChangeSelection.chosen/inject/take/top](../../adapters/change_pool.py)、[GA survivor 的接缝](../../adapters/selection_pool.py)、上述正式 GA 工厂；源码核对。

### 变体一：一次分区，同时保留精英和未入选候选

**目的：** 希望主成员、精英副池和 reserve 都来自同一次选择，避免再独立抽一次导致结果对不上。

**改在哪里：** 使用正式 [pool_workflow_pilot/ga_partition/adapter/workflow.py](../../examples/cases/pool_workflow_pilot/cases/ga_partition/adapter/workflow.py)。下段可替换该文件的选择回调；同时把现有 partial 的参数补为 `elite_count=20`。原父代选择器继续读取公开名 elite。

```python
import numpy as np
from nsgablack.adapters import Pool, partition

def raw_key(pool):
    f, v = pool.raw_feedback()
    return np.column_stack((v > 0., np.maximum(v, 0.), np.sum(f, axis=1)))

def choose_survivors(pool, *, count, elite_count, rng):
    quota = min(elite_count, count, len(pool))
    selected, remaining = partition(
        pool, by=lambda offered: offered.top(quota, key=raw_key), rng=rng)
    needed = min(count, len(pool)) - len(selected)
    members = selected.concat(remaining.take(range(needed)))
    Pool(parent=members, name="elite").inject(selected, replace=True)
    reserve = remaining.take(range(needed, len(remaining)))
    Pool(parent=pool, name="reserve").inject(reserve, replace=True)
    return members
```

**行为变化：** selected 与 remaining 是按原输入位置分出的两部分；选中部分优先进入成员，剩余部分补足容量，再将未进入成员的部分交给 reserve。原 Case 默认 100 成员、80 后代，`PartitionTrace` 会读取 `selection_outputs.elite/reserve`、来源位置和下一轮父引用。

**限制：** 这里明确改成“raw 可行性、违反量、目标和”的规则，不声称仍是 NSGA 默认多目标排序。改变规则后应同步原 `PartitionTrace` 所导入的 `choose_twenty` 或其只读核对函数，否则观察器还会按旧规则核对；框架不会因为代码语法合法替你改报告。相同数值不同身份不自动合并；最终 survivor 也不能重复选择同一个输入位置。

### 变体二：历史档案只合并最终成员

**目的：** 保留曾成为正式成员的候选，排除“虽被硬接纳、但同次生存选择已淘汰”的试探。

**改在哪里：** 使用 `pool_workflow_pilot/cases/ga_search`，先在它的 [build_solver.py](../../examples/cases/pool_workflow_pilot/cases/ga_search/build_solver.py) 中，把原 `settings = CaseConfig(**dict(config or {}))` 替换为下面这一行。`config` 是该正式 Case builder 已有的参数，`CaseConfig` 也已导入；保留其它配置，只明确启用成员档案模式：

```python
settings = CaseConfig(**{**dict(config or {}), "archive_source": "members"})
```

再在同 Case 的 [adapter/workflow.py](../../examples/cases/pool_workflow_pilot/cases/ga_search/adapter/workflow.py) 中保留或替换下面的 `maintain_final_members` 实现；`elite_key` 显式比较原始可行性、违反量和目标和。

```python
import numpy as np
from nsgablack.adapters import Pool

def elite_key(pool):
    f, v = pool.raw_feedback()
    return np.column_stack((v > 0., np.maximum(v, 0.), np.sum(f, axis=1)))

def maintain_final_members(request, *, rng):
    if request.members is None:
        raise ValueError("this archive requires a population's final members")
    names = request.pool.describe()["subpools"]
    old = (request.pool.subpool("elite") if "elite" in names
           else request.members.take(()))
    merged = old.merge(request.members)
    kept = merged.chosen(lambda offered: offered.top(20, key=elite_key), rng=rng)
    Pool(parent=request.pool, name="elite").inject(kept, replace=True)
```

该文件的原 `build_adapter(settings)` 已在创建 `ga` 后绑定维护回调，保留下面这一处接线，不要再挂第二个维护回调：

```python
ga.set_pool_maintenance(
    maintain_final_members if settings.archive_source == "members" else maintain_elite
)
```

这里的 `ga` 和 `settings` 都来自原 `build_adapter`。默认配置是 `archive_source="accepted"`，仅替换函数正文不会切换模式；上面的配置修改使工厂实际选择 `maintain_final_members`。其余 GA 选择器、Router、Source 和正式 Project 入口保持原接线。

**行为变化：** 在本实际叶 update 已完成算法成员选择后，maintenance 合并历史 elite 与 `request.members`，再写一个精确替换计划。它不同于原 accepted 模式合并 `request.accepted`。`merge` 按精确 SolutionRef 去重，不按参数数值去重。

**限制：** 保留任务原有 `change_sources=("elite",)`，否则受限任务不能读取旧档案。跨反馈来源合并后显式用 raw 比较；不能假定旧池仍携带当前 GA 的选择分数。Pool 作用域在回调返回后失效，不把 request 或活 Pool 存进下一代状态。

## tool.subpools · 按实际算法实例选择结果视图

**什么时候用：** 局部算法需要精修某个 MOEA/D 实例发布的方向，或接着精修上一层已经完成的结果。选择依据是具体实例，而不是类名、候选生产者名字或你拼出的子池字符串前缀。

**先准备什么：** 使用 [assembly_workbench/directions](../../examples/cases/assembly_workbench/cases/directions/adapter/composition.py)：一维候选、两个最小化目标、3 个 MOEA/D 方向；先有完整已评估 bootstrap，再派发 coarse/fine。`settings` 是该 Case 的 DirectionsConfig，包含 local_steps；`moead` 与 `coarse` 都是同一工厂创建并放入同一所有权树的实例。

**放在哪：** 仍在 directions 的 `adapter/composition.py`。下面将原 coarse StrategySpec 的构造提取成一个有明确参数的函数；原 strategies 列表的对应项用 `build_coarse_spec(moead, coarse, settings)` 替换。

**接入步骤：**

```python
from nsgablack.adapters import PoolTaskSpec, StrategySpec, subpools

def build_coarse_spec(moead, coarse, settings):
    return StrategySpec(coarse, "coarse", pool_task=PoolTaskSpec(
        subpools.all(moead), mode="refine", count=1,
        steps=settings.local_steps, output=None, shuffle=False,
    ))
```

`subpools.all(moead)` 在请求开始时选择该实例已发布的方向视图；`count=1` 表示每个方向取一个起点。权重、参考点、候选引用和视图身份在本请求冻结。`all` 不隐含等待，原 plan 中先 `stage("moead", steps=settings.bootstrap_steps)` 的屏障必须保留。

**怎样判断接对：** 原 `results/directions/summary.json` 有 `views`、`tasks`、`result_receipts`、`final_results` 和 `final_population`；逐视图看 created_by、projection 和 descriptor，最终原始目标仍是两列。该文件由实际完成的 Case 生成，旧文件不代表本轮执行。

**运行入口：** `python examples/cases/assembly_workbench/run_project.py --group directions`。未执行。

**配套组件 key：** `adapter.moead`、`adapter.vns`、`tool.pool_task_spec`、`adapter.search_plan`。

**接口依据与验证状态：** [SubpoolSelection 与 subpools](../../adapters/subpools.py)、[PoolTaskAdapter 视图分发](../../adapters/pool_tasks.py)、上述 directions 工厂与 [DirectionTrace](../../examples/cases/assembly_workbench/cases/directions/plugins/trace.py)；源码核对。

### 变体一：每轮只抽两个方向

**目的：** 方向很多、局部预算有限，希望每次请求精修有限个方向，不先复制一批新候选。

**改在哪里：** 将上面的 coarse spec 工厂替换为以下版本，或直接使用现有 Project `random_directions` 组的 `direction_sample=2` 配置。

```python
from nsgablack.adapters import PoolTaskSpec, StrategySpec, subpools

def build_coarse_spec(moead, coarse, settings):
    return StrategySpec(coarse, "coarse", pool_task=PoolTaskSpec(
        subpools.random(2, moead), count=1, steps=settings.local_steps,
        output=None, shuffle=False,
    ))
```

**行为变化：** 抽的是 2 个结果视图，count 仍是每视图起点数；抽样与冻结队列随请求和 checkpoint 保持。现有入口为 `--group random_directions`，该组还同步了 Case 的选中方向数与总步数计算。

**限制：** 不把 `subpools.random(20, ga)` 解释成从一个 GA population 视图里抽 20 个成员。普通 NSGA population 通常是一份视图；成员数量由 PoolTaskSpec.count 控制。抽样数不能超过当时可用视图数；改工厂时同步 DirectionsConfig.direction_sample，避免运行预算和报告仍按全部方向计算。

### 变体二：细精修读取粗精修的最终视图

**目的：** 先让 VNS 在各方向粗搜，再由 PatternSearch 对本次粗搜的最终选择继续细搜。

**改在哪里：** 在同一个 directions 工厂中保留 coarse 实例，把 fine StrategySpec 写成下面的完整工厂返回值；plan 仍是 `serial(stage("coarse"), stage("fine"))`，最后才让 MOEA/D 返回竞争。

```python
from nsgablack.adapters import (
    PatternSearchAdapter, PoolTaskSpec, StrategySpec, subpools,
)

def build_fine_spec(coarse, settings):
    fine = PatternSearchAdapter(name="fine_pattern", max_directions=1,
                                step_size=0.08)
    return StrategySpec(fine, "fine", pool_task=PoolTaskSpec(
        subpools.all(coarse), count=1, steps=settings.local_steps,
        output=None, shuffle=False,
    ))
```

**行为变化：** 来源是粗精修实例发布的派生视图，保留父级、祖先、精确版本和冻结投影；不是回头读取 MOEA/D 原始起点，也不是取粗搜历次接纳的全部提案。原方向 Case 的 serial 布局正使用这条路径。

**限制：** fine 必须在 coarse 本请求完成并提交之后取视图。若改成并列 `multi(stage("coarse"), stage("fine"))`，fine 应读同一个原始 directions 来源，不能在同一步依赖 coarse 尚未发布的结果；现有 `parallel_refiners` 组已按此区别接线。

## tool.pool_task_spec · 声明输入怎么被算法消费

**什么时候用：** “这批引用拿来初始化、逐个精修，还是交回现有种群竞争”需要明确表达时。它配置消费语义，不建立第二个 Solver，也不把其它 Adapter 的 Unit 当候选解码。

**先准备什么：** 用 `pool_workflow_pilot/ga_partition` 已挂载的 Source 提供初始版本。`settings.population_size` 是本 GA 的容量；源引用数由 source_count 另定。NSGA2 支持 initialize/compete，VNS 支持以 initialize 接起点并进行 refine；不能仅换一个类名就假定它支持任意池任务。

**放在哪：** Case 的 `adapter/workflow.py`。下面函数生成原 RoleSpec 中的初始化任务；在原工厂把 `pool_task=PoolTaskSpec(...)` 改成 `pool_task=initial_task(settings)`，保留 GA、Router、Source 及已有选择函数。

**接入步骤：**

```python
from nsgablack.adapters import PoolTaskSpec

def initial_task(settings):
    return PoolTaskSpec(
        mode="initialize", count=settings.population_size,
        shuffle=False, change_sources=("elite",),
    )
```

省略 select 时读取最近组合的 working_pool；没有绑定时读根公开来源，包括 initial 种子。请求开始时确定引用队列，算法经正常 repair/evaluate/admission 逐步消费；零接纳不会把相应输入当作已经完成。initialize 完成后继续算法自己的搜索，不因为下一阶段到了就再初始化。

**怎样判断接对：** `WorkflowTrace.records[*].task` 是该 worker 的实际 task_status，最终 result.refs 是算法真正选择的成员。读取任务状态与读取结果分开：正在运行的 refine 请求没有可交付的最终结果，完成并提交后才可读取。

**运行入口：** `python examples/cases/pool_workflow_pilot/run_project.py --group partition`。未执行。

**配套组件 key：** `adapter.pool_task`、`tool.solution_pool`、`tool.subpools`、`adapter.multi_strategy`、`adapter.search_plan`。

**接口依据与验证状态：** [PoolTaskSpec 与 PoolTaskAdapter](../../adapters/pool_tasks.py)、ga_partition 的 [工厂](../../examples/cases/pool_workflow_pilot/cases/ga_partition/adapter/workflow.py) 与 [Source](../../examples/cases/pool_workflow_pilot/pool_source.py)；源码核对。

### 变体一：明确读取 reference；不足时先用现有种子

**目的：** 源候选少于容量时，希望先消费已经准备好的部分，不静默制造新引用或要求初始池一定等于种群容量。

**改在哪里：** 同一 workflow.py 定义下面命名选择函数和任务工厂，再把 source_count 配成所需实际供给数，例如 20。保留原 population_size=100 和后续 offspring_size 的独立含义。

```python
from nsgablack.adapters import PoolTaskSpec

def reference_refs(control, context):
    del context
    return control.solution_pool.subpool_refs("reference")

def initial_task(settings):
    return PoolTaskSpec(
        reference_refs, mode="initialize", count=settings.population_size,
        on_insufficient="available", shuffle=False, change_sources=("elite",),
    )
```

**行为变化：** 命名函数返回准确公开名 reference 的引用，不把它解析成任务命名空间下的相对名称。不足时用当前可用输入；普通 population 视图不自带“已填满 100”的屏障。

**限制：** available 的空输入会结束空请求而不创建结果集合；wait 则保留等待语义。名字不存在仍是错误，不是空池等待。若保留原 PartitionTrace/统计断言，源数量假设也要同步；该变体没有在本轮运行验收。

### 变体二：只把本轮 VNS 最终选择交回 GA

**目的：** 不让历轮 output 的累计接纳历史冒充“本轮精修结果”，并且无需为交付最终选择强制保留聚合 output。

**改在哪里：** 使用 `assembled_ga_vns` 的 plan 分支：保留原 `select_current_refinement_results` 命名函数，它调用 SearchPlan 根的 `get_pool_task_results(control, "vns")`。用下面工厂返回的两个 spec 替换 plan 的 strategies；ga/vns/source 均由同一原工厂创建。

```python
from nsgablack.adapters import PoolTaskSpec, StrategySpec

def task_specs(ga, vns, source, settings):
    return [
        StrategySpec(ga, "ga", pool_task=PoolTaskSpec(
            select_current_refinement_results, mode="compete",
            phases=("return",), count="all", shuffle=False)),
        StrategySpec(vns, "vns", pool_task=PoolTaskSpec(
            source, mode="refine", count="all", steps=settings.local_steps,
            output=None, shuffle=False)),
    ]
```

**行为变化：** 每个起点有自己的有界精修，steps 包含先评估基准的一步；最终结果视图仍发布，output=None 只是不保留一个累计提案池。返回 GA 时重新评估并按 GA 自己的规则竞争，不把 VNS 的标量评分直接安装为 GA 原始反馈。

**限制：** 这是 SearchPlan 根的方法，不假定普通 Router 或 Chain 也有同签名。普通 Router 的 refine worker 可通过该 PoolTaskAdapter 实例自己的 `get_pool_task_results(control)` 读取；先按角色定位真实 worker。本变体去掉了原名为 refined 的聚合池，原 trace 对 `ga_vns/refined` 的固定读取也必须同步为最终结果引用，不能原封不动保留那段报告代码。

## adapter.search_plan · 用局部完成表达 GA → 精修 → 返回竞争

**什么时候用：** 想有限重复整个流程，并等待每个精修任务真正完成；不想按“全局第几代”手算各子任务进度。

**先准备什么：** 使用 [assembled_ga_vns 的 plan 分支](../../examples/cases/assembled_ga_vns/cases/hybrid_search/adapter/composition.py)。其已有 DemoConfig、GA/VNS 构造、AgePopulationBuilder、精英选择回调，以及 `select_current_refinement_results`。下段完整计划工厂明确接收这两个实际实例与来源，不在每个 stage 重新实例化算法。

**放在哪：** 在原 composition.py 加下面函数，把 plan 分支原 `return SearchPlanAdapter(...)` 改成 `return build_plan(ga, vns, source, settings)`。原 source 的 population/elite 分支和其它组件工厂保持。

**接入步骤：**

```python
from nsgablack.adapters import (
    MultiStrategyConfig, PoolTaskSpec, SearchPlanAdapter, StrategySpec,
    repeat, serial, stage,
)

def build_plan(ga, vns, source, settings):
    body = serial(
        stage("ga", steps=settings.ga_steps, label="ga"),
        stage("vns", label="vns"),
        stage("ga", label="return"),
    )
    return SearchPlanAdapter(
        repeat(times=settings.rounds, body=body),
        strategies=[
            StrategySpec(ga, "ga", pool_task=PoolTaskSpec(
                select_current_refinement_results, mode="compete",
                phases=("return",), count="all", shuffle=False)),
            StrategySpec(vns, "vns", pool_task=PoolTaskSpec(
                source, mode="refine", count="all", steps=settings.local_steps,
                output="refined", shuffle=False)),
        ],
        config=MultiStrategyConfig(total_batch_size=settings.proposal_budget,
                                   adapt_weights=False),
        name="ga_vns",
    )
```

`stage("ga", steps=...)` 是该叶有接纳更新的局部额度；VNS 和 return 叶省略 stage.steps，等待对应 PoolTask 本请求完成。名字 ga 在计划中出现两次，仍是同一个 ga 实例。role/strategy 名称必须与 plan 的 owner 名称准确匹配。

**怎样判断接对：** 原 `results/plan/trace.json` 的 `records[*].execution_plan.cursor/completed/tasks` 记录计划游标与各任务进度，return 记录的 selected_return 是本轮结果；`aggregate_return` 是累计接纳历史。等待、空控制切换不产生额外逻辑 generation。

**运行入口：** `python examples/cases/assembled_ga_vns/run_project.py --group plan`。该组已同步 schedule、rounds、种群规模和预算；未执行。

**配套组件 key：** `adapter.nsga2`、`adapter.vns`、`tool.pool_task_spec`、`tool.subpools`、`adapter.multi_strategy`。

**接口依据与验证状态：** [SearchPlanAdapter 与 SearchProgress](../../adapters/search_plan.py)、上述 plan 工厂与 [DemoConfig.max_steps/proposal_budget](../../examples/cases/assembled_ga_vns/cases/hybrid_search/config.py)；源码核对。

### 变体一：把两个精修分支改成并列调度

**目的：** 两个精修器分别探索同一组 MOEA/D 方向，再把它们的本轮结果一起交回方向所有者。

**改在哪里：** 使用 `assembly_workbench/directions` 原工厂，它已有 coarse/fine 两个实例及返回选择函数。保留原完整工厂，只把 refinement_layout 配为 parallel；下面是这两种布局在原工厂内的计划差别。

```python
from nsgablack.adapters import multi, serial, stage

def refinement_body(*, layout):
    if layout == "parallel":
        return multi(stage("coarse"), stage("fine"))
    if layout == "serial":
        return serial(stage("coarse"), stage("fine"))
    raise ValueError("layout must be serial or parallel")
```

**行为变化：** 并列布局中 coarse/fine 都从原 directions 取冻结输入，return 汇合两个最终结果；串行布局 fine 读取 coarse 的派生最终视图。现有 `--group parallel_refiners` 与 `--group directions` 已分别接好这两套来源和返回函数。

**限制：** 不是把 serial 单词机械换成 multi 就完成依赖改造；同时要保留原工厂对 fine 来源和 `parallel_results/fine_results` 返回函数的分支。multi 是同一 Solver 内的逻辑并列调度，不自行创建线程或额外 L0 grant。DirectionsConfig 对并列布局的 router_budget 有专门检查，不能声称同一数值预算一定产生同样候选数。

### 变体二：GA 达到明确停滞条件时提前转去精修

**目的：** 给 GA 一段最大局部额度，同时允许它在本叶反馈连续不改善后提前完成；精修任务仍完整等待。

**改在哪里：** 在 assembled_ga_vns 的同一 composition.py 中定义下面命名函数，保留基础 build_plan 的 body/strategies/config，将两个策略字典参数加到 SearchPlanAdapter 构造。只对 label="ga" 的普通搜索叶生效。

```python
def batch_raw_best(feedback):
    return float(feedback.raw_objectives[:, 0].min())

def ga_stalled(progress):
    return progress.updates >= 4 and progress.stagnant_updates >= 3

def conditions_for_ga():
    return {"until": {"ga": ga_stalled},
            "metrics": {"ga": batch_raw_best}}
```

在基础构造中传 `**conditions_for_ga()`；ga_steps 仍是上限，必须给条件留下足够额度。使用单目标原始反馈是本例明确选择，不由框架猜多目标标量化。

原 Project 的 plan 组把 ga_steps 设成 2，达不到本条件要求的最少 4 次更新。要应用此变体，在该 Project 的 `project_config.py` 把已有 PLAN_DEMO_CONFIG 整体改为下面的小配置，其它 STAGES/GROUPS 不变；DemoConfig 会据此重算外层提交上限：

```python
PLAN_DEMO_CONFIG = {
    "schedule": "plan", "rounds": 2,
    "population_size": 6, "ga_steps": 12, "local_steps": 2,
    "local_batch": 1, "refinement_source": "elite", "elite_count": 2,
}
```

**行为变化：** metric 消费该叶自己的已接纳反馈子批，SearchProgress.stagnant_updates 统计本 activation 的不改善更新。条件提前完成当前 GA 叶；下一轮 activation 重新统计条件，复用算法已有状态。

**限制：** 回调必须是稳定模块中的命名普通函数；不能把运行中的 Solver/Provider 捕进闭包。refine/compete 任务叶禁止用 until 提前抛弃进行中的输入；对它们不能再加 stage.steps。原 DemoConfig.max_steps 是外层提交上限，不表示条件必然触发，也不表示已经验证性能收益。

## adapter.serial_strategy · 用阶段包住现有算法或 Router

**什么时候用：** 已有可运行的子 Adapter/Router，要按阶段依次执行，或者在外层绑定共同工作区域。真实 Catalog key 是 adapter.serial_strategy，类名才是 StrategyChainAdapter。

**先准备什么：** 从 ga_partition 的原 build_adapter 中拿到已经构造好的 router；它负责 GA 的池初始化与选择。`settings.working_pool` 若非 None，必须由同 Case 的 PipelineSource 在首次提案前创建并发布普通集合。

**放在哪：** `pool_workflow_pilot/cases/ga_partition/adapter/workflow.py` 的工厂末尾。以下辅助函数对应其现有可选 Chain 分支；用 `return wrap_workflow(router, settings)` 替换原返回分支即可。

**接入步骤：**

```python
from nsgablack.adapters import SerialPhaseSpec, StrategyChainAdapter

def wrap_workflow(router, settings):
    if settings.working_pool is None:
        return router
    return StrategyChainAdapter(
        name="workspace_workflow", working_pool=settings.working_pool,
        phases=[SerialPhaseSpec("search", router)],
    )
```

这里 phase 没有限定正数 steps，继续由外层 Solver 的预算决定持续多久。外层 Chain 的工作区域被内层 Router 继承；这不会自动给裸子 Adapter 添加池任务。需要取池输入的仍是内层已有 PoolTaskSpec。

**怎样判断接对：** 既有 WorkflowTrace 用 `step_transaction_children()` 穿过单阶段 Chain，再读取真实 worker；设置 workspace 后，PartitionTrace 会多记 working_pool.descriptor/refs。它不会为了观察构造 Unit。阶段名与最终种群所有者不同，不能仅凭“当前阶段切了”就假定已经有新种群发布。

**运行入口：** `python examples/cases/pool_workflow_pilot/run_project.py --group partition`，先应用 solution_pool 节的 workspace 配置才会进入该分支。未执行。

**配套组件 key：** `adapter.multi_strategy`、`tool.pool_task_spec`、`tool.solution_pool`。

**接口依据与验证状态：** [SerialPhaseSpec/SerialStrategyConfig/StrategyChainAdapter](../../adapters/serial_strategy/adapter.py)、上述 ga_partition 工厂与 [workflow_worker](../../examples/cases/pool_workflow_pilot/workflow_trace.py)；源码核对。

### 变体一：阶段满两次接纳更新后明确结束

**目的：** 希望这个局部工作流自行完成，而不是最后一个阶段无限继续到外层 Solver 的总预算。

**改在哪里：** 替换上面的 wrap_workflow；保持原 settings.max_steps 至少能容纳两次更新和完成通知，Source 与工作区域创建不变。

```python
from nsgablack.adapters import SerialPhaseSpec, StrategyChainAdapter

def wrap_workflow(router, settings):
    return StrategyChainAdapter(
        name="workspace_workflow", working_pool=settings.working_pool,
        phases=[SerialPhaseSpec("search", router, steps=2)],
        repeat_last=False,
    )
```

**行为变化：** 本阶段每次真正 update 后推进局部计数，达到 2 后结束 Chain；完成通知的空控制尝试不再算一代。repeat_last 默认是 True，显式 False 才表达这里的有限结束。

**限制：** 不要用小于输入完成所需的任意步数切断进行中的 PoolTask。该示例只有一个 phase，原观察器支持；若把它改为多 phase，原 workflow_worker 明确只接受单阶段 Chain，需要换成能区分新拓扑的观察器，不能忽略它抛出的错误。

### 变体二：后续阶段改用不同算法，但单独声明是否交接候选

**目的：**先运行已有多角色探索，再依次运行 VNS 与信赖域的独立策略阶段，学习 Chain 的实际串行职责。

**改在哪里：** 使用正式 [super_topology/outer_search/adapter/topology.py](../../examples/cases/super_topology_orchestration/cases/outer_search/adapter/topology.py)，该文件已有 `_exploration_router()`。下段可作为其 build_topology_adapter 的较短替换；使用的是该 Case 原数据、问题管线与资源上下文，不移到 ga_partition 的单阶段观察器下。

```python
from nsgablack.adapters import (
    SerialPhaseSpec, StrategyChainAdapter, TrustRegionDFOAdapter,
    TrustRegionDFOConfig, VNSAdapter, VNSConfig,
)

def build_topology_adapter():
    return StrategyChainAdapter(
        phases=[
            SerialPhaseSpec("explore", _exploration_router(), steps=1),
            SerialPhaseSpec("vns_refine", VNSAdapter(VNSConfig(
                batch_size=1, k_max=1, base_sigma=0.08)), steps=1),
            SerialPhaseSpec("trust_region_refine", TrustRegionDFOAdapter(
                TrustRegionDFOConfig(batch_size=1, initial_radius=0.15,
                                     include_center=True, random_seed=211)), steps=1),
        ],
        name="explore_then_refine", repeat_last=False,
    )
```

**行为变化：** 同一时刻只把提案与反馈交给当前阶段，保留各阶段子实例自己的状态；原正式文件还有后续 DE 阶段，这里明确移除了它。同步该文件的 describe_topology()，使显示的实际阶段列表相符。

**限制：** phase 名含 refine 不会自动读取前一阶段种群，裸阶段排序不等于 GA→VNS 池精修。若要精确候选交接，须像 search_plan 节一样加入正式池任务/冻结来源；本段没有把这个缺失藏在名字里。super_topology 是含内层 Case 的完整 Project，先读其 README 与资源需求；这里只静态说明本地拓扑替换，不把它称作本轮已运行示例。

## adapter.multi_strategy · 一个角色下装配多个独立搜索实例

**什么时候用：** 多种搜索角色需要共享一次 Solver 的评估与调度，并按角色配额分配提案机会。它负责调用上下文和反馈路由，不把角色数当线程数，也不把实例的 Unit 共享成一个可写种群。

**先准备什么：** 以 super_topology 的 `_exploration_router()` 为锚点：`neighborhood_explorer` 有两个 VNS，`region_probe` 有一个 TrustRegionDFO。该 Case 的候选管线负责 `[0,1]` 初始化、上下文高斯变化和 ClipRepair；维数由它自己的模型设计 Problem 声明。不要把下面工厂直接拿到“只有 repair、没有初始化”的另一个 Case 中使用。

**放在哪：** 替换 `super_topology_orchestration/cases/outer_search/adapter/topology.py` 中同名探索工厂；保留该文件其它构造与外层 Case。命名工厂每次返回一个新 Adapter，避免 n_units>1 复用同一可变实例。

**接入步骤：** 以下将原两个 lambda 工厂写成可定位的函数，并保留默认组合；新参数只属于本 Case 的工厂，不是新增框架 API。

```python
from nsgablack.adapters import (
    MultiStrategyConfig, RoleSpec, StrategyRouterAdapter,
    TrustRegionDFOAdapter, TrustRegionDFOConfig, VNSAdapter, VNSConfig,
)

def make_explorer(unit_id):
    return VNSAdapter(VNSConfig(batch_size=2, k_max=2, base_sigma=0.18),
                      name=f"explore_vns_{unit_id}")

def make_probe(unit_id):
    return TrustRegionDFOAdapter(TrustRegionDFOConfig(
        batch_size=2, initial_radius=0.3, include_center=True,
        random_seed=100 + unit_id), name=f"explore_tr_{unit_id}")

def _exploration_router(*, n_explorers=2, total_batch_size=3,
                        explorer_weight=2.0, probe_weight=1.0,
                        adapt_weights=False):
    return StrategyRouterAdapter(
        roles=[
            RoleSpec("neighborhood_explorer", make_explorer,
                     n_units=n_explorers, weight=explorer_weight),
            RoleSpec("region_probe", make_probe, n_units=1, weight=probe_weight),
        ],
        config=MultiStrategyConfig(
            total_batch_size=total_batch_size, adapt_weights=adapt_weights,
            phase_schedule=(("explore", -1),),
            phase_roles={"explore": ["neighborhood_explorer", "region_probe"]},
        ),
        name="multi_role_exploration",
    )
```

Router 先按有效角色权重分配 total_batch_size，再把角色额度分给该角色的独立实例。每个调用有 StrategyTask；返回的 repair、disposition、feedback 仍沿原提案所有者路由。该例没有 PoolTask，因此不要据此推断精确池起点、逐成员精修或返回竞争已经配置。

**怎样判断接对：** 对实际探索 Router 读取 `get_state()["units"]` 与 `unit_reports`，核对角色、unit_id、adapter_name 和各自 n_candidates；观察切片用 `get_runtime_context_projection(control)` 的 strategy_instances。保留角色命名后，原 describe_topology 也须反映正确 n_units。这些读取不应构建新 Unit；运行权重与初始配置权重是不同事实。

**运行入口：** 原正式 Project 为 `python examples/cases/super_topology_orchestration/run_project.py`；它还包含其它 Case，实际执行前须按其 README 核对整个 Project 的工作与资源。本轮未执行。

**配套组件 key：** `adapter.vns`、`adapter.trust_region_dfo`、`adapter.serial_strategy`、`repr.context_gaussian`、`tool.pool_task_spec`。

**接口依据与验证状态：** [RoleSpec/StrategySpec/MultiStrategyConfig 与预算分配](../../adapters/multi_strategy/adapter.py)、上述正式 topology 工厂与 [共享候选管线](../../examples/cases/super_topology_orchestration/cases/outer_search/pipeline/main.py)；源码核对。

### 变体一：把两个邻域实例增加到四个

**目的：** 增加同角色独立搜索状态的数量，而不是把同一 Adapter 对象放进四个槽位。

**改在哪里：** 在同 topology.py 的 build_topology_adapter 中，explore 阶段改成下面辅助工厂的返回值；基础 `_exploration_router` 采用本节完整定义。

```python
from nsgablack.adapters import SerialPhaseSpec

def exploration_phase():
    return SerialPhaseSpec("explore", _exploration_router(
        n_explorers=4, total_batch_size=6,
    ), steps=1)
```

**行为变化：** 四次 make_explorer 调用产生四个不同 VNS 实例，角色配额再分给它们；总提案额度从 3 提高到 6。实例独立并不意味着增加了 CPU 线程或 Project lease。

**限制：** 总预算太小可能让某些实例本步分不到配额；提案上限不是承诺用满。还要同步 describe_topology 的 units 数、外层预算和资源规划。不要传 `RoleSpec(..., adapter=VNSAdapter(), n_units=4)` 期待它自动复制状态。

### 变体二：固定偏重区域探测，或显式开启自适应权重

**目的：** 在实例数量不变时改变角色获得提案机会的比例，并能区分手工配额与运行中学习到的权重。

**改在哪里：** 同一 explore 阶段选择下面一种构造；不是同时创建两个同名阶段。

```python
from nsgablack.adapters import SerialPhaseSpec

def exploration_phase(*, adaptive=False):
    router = _exploration_router(
        total_batch_size=6, explorer_weight=1.0, probe_weight=3.0,
        adapt_weights=adaptive,
    )
    return SerialPhaseSpec("explore", router, steps=1)
```

**行为变化：** adaptive=False 按显式权重分配；True 允许 Router 用已有改善统计调整后续有效权重。角色配额仍受实例各自能产生多少候选的限制，例如 TrustRegion 的本地 batch_size=2 不因分到更大配额就必然产生更多候选。

**限制：** 一个只有一步的 explore 阶段主要演示配额装配，不能据此声称自适应已经改善搜索。当前 [outer_search/solver/case.py](../../examples/cases/super_topology_orchestration/cases/outer_search/solver/case.py) 的 run 明确调用 `solver.run(max_steps=4, max_step_attempts=8)`；只改 config.py 的 MAX_STEPS 不会自动扩大这个入口。若要观察多次适应，除阶段 steps 外还须同步这个正式 Case 的调用上限与报告对阶段的核对，不能只切一个布尔值就称为闭合的长实验。unit_tasks/strategy_instances 是观察摘要，不由外部改字典来偷偷调度。精确候选共享仍须另加 PoolTask，不能用角色权重替代交接声明。
