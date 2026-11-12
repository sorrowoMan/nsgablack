# 搜索装配的四个可照做扩展

这些变体承接各组件已有主例，均使用现有标准 Project 的独立副本。
复制整个 Project，保留 `run_project.py`、`project_config.py`、Case 入口与 Problem/Pipeline；
下方说明改动的具体文件。不要直接改安装包中的算法源码，也不要把代码块拼成另一个运行器。
本轮已在本地副本通过正式 Project/L0 路径执行，目录的执行标签仍由当前发布的独立运行收据决定。

## extension.adapter.composite

### 变体一：一个种群加一条轨迹，各自搜索后统一送评

**目的：** 在同一个二维平方和问题上，同时观察 GA 的种群搜索与 VNS 的单点邻域搜索。
与主例的两个 NSGA2 相比，这次组合的是不同结构：GA 保留四个成员，VNS 保留一个当前点。
二者分别起步；这不是“VNS 从 GA 精英开始精修”。

**改在哪里：** 复制 `examples/cases/catalog_recipes/`，将副本
`cases/composite/build_solver.py` 完整替换为下面内容。原 `problem/` 与 `pipeline/` 不变，
仍使用二维 `[-2,2]` 问题与共享问题修复。Project 的默认组只运行此 Case。

```python
from nsgablack.adapters import CompositeAdapter, NSGA2Adapter, VNSAdapter
from nsgablack.project.starter import build_starter_solver
from nsgablack.project import apply_solver_component_overrides
from nsgablack.representation import (
    ContextGaussianMutation, GaussianMutation, UniformInitializer,
)
from .pipeline import build_pipeline
from .problem import build_problem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    ga = NSGA2Adapter(name="population", population_size=4, offspring_size=4,
                     mutator=GaussianMutation(sigma=0.3))
    vns = VNSAdapter(name="trajectory", batch_size=1, k_max=3,
        initializer=UniformInitializer(-2.0, 2.0),
        base_sigma=0.15, restart_on_stagnation=False,
        mutator=ContextGaussianMutation(base_sigma=0.15))
    solver = build_starter_solver(problem=build_problem(), pipeline=build_pipeline(),
        resource_context=resource_context, max_steps=2)
    solver.set_adapter(CompositeAdapter([ga, vns]))
    apply_solver_component_overrides(solver, component_overrides)
    return solver
```

**行为变化：** 每个逻辑步骤收集 GA 的四行和 VNS 的一行提案，统一经过同一个问题修复与求值，
再按原提案来源回传反馈。首步中 VNS 的一行是建立基准，下一步才是其邻域。
GA 的种群与 VNS 的轨迹分别更新；共同的 SolutionPool 不会自动让它们使用同一成员。

**运行与检查：** 在副本 Project 根目录执行：

```powershell
python run_project.py --check --build-check
python run_project.py --no-record
```

实际装配应显示 Composite、NSGA2 与 VNS，资源由 Project 发放。
在不另加预算或接纳筛选时，本轮副本实跑为 **2 次提交、10 次求值**。
若选择主例 README 中的正式 Case 程序式检查方式，已运行的
`solver.adapter.adapters[0]` 是 GA，第二个孩子是 VNS：前者按成员引用读取种群，
后者用 `get_current_candidates()` 读自己的当前候选。
根 `get_population_snapshot()` 仍不能冒充统一种群；轨迹也不应填进 GA 的矩阵。

**限制：** Composite 的子调用是同步分派，不因此创建两个计算线程。
没有 GA→VNS 的交接任务，也没有统一的孩子间生存选择。
若要比较“各自搜”和“先全局再精修”，后者须另用 SearchPlan/PoolTask，不能靠改这个列表的顺序实现。
更换预算、初始化方式或 VNS 批量后，不再沿用上述求值次数。

## extension.adapter.nsga2

### 变体一：只从最终成员维护一个有历史的两条折衷解档案

**目的：** 将“本批候选已被硬接纳”与“最终被 GA 留下”区分开。
这里的 `elite` 普通池只归并历次最终成员，按明确的原始双目标和留下两条，
不把刚评估却被生存选择淘汰的试探直接入档，也不改变 NSGA2 本身的非支配/拥挤度选择。

**改在哪里：** 复制 `examples/cases/pool_workflow_pilot/`。
在副本 `cases/ga_search/adapter/workflow.py` 保留现有 imports、`paired_change`、
`choose_survivors` 和 `elite_key`，完整替换 `maintain_final_members` 与 `build_adapter` 为下方两个函数。
这些保留函数就在同一文件：前两个负责变化与种群生存；`elite_key` 读取 raw feedback，
按可行性、违反量、双目标和排序。新工厂固定绑定下列档案规则，不再根据旧 `archive_source` 分支切换。

```python
from functools import partial
from nsgablack.adapters import (
    MultiStrategyConfig, NSGA2Adapter, Pool, PoolTaskSpec,
    RoleSpec, StrategyRouterAdapter,
)


def maintain_final_members(request, *, rng):
    if request.members is None:
        raise ValueError("this archive requires the owning population's final members")
    old = request.pool.subpool("elite")
    kept = old.merge(request.members).chosen(
        lambda offered: offered.top(2, key=elite_key), rng=rng)
    archive = Pool(parent=request.pool, name="elite")
    archive.inject(kept, replace=True)


def build_adapter(settings):
    ga = NSGA2Adapter(name="ga", population_size=settings.population_size,
        offspring_size=settings.offspring_size, change=paired_change)
    ga.set_selector(partial(choose_survivors, count=settings.population_size))
    ga.set_pool_maintenance(maintain_final_members)
    return StrategyRouterAdapter(name="ga_workflow", roles=[RoleSpec("search", ga,
        pool_task=PoolTaskSpec(mode="initialize", count=settings.population_size,
                              shuffle=False, change_sources=("elite",)))],
        config=MultiStrategyConfig(total_batch_size=max(settings.population_size,
            settings.offspring_size), adapt_weights=False))
```

**输入从哪里来：** `settings` 是本 Case 的 `CaseConfig`；`request` 与 `rng` 在叶 Adapter 完成更新后由框架提供，
不手工构造。该 Project 的 `PipelineSource` 已在启动时创建普通空池 `elite`。
`change_sources=("elite",)` 保持明确读取授权；回调不会为了建立档案去枚举未授权的母池。
本变体不同时绑定原 `maintain_elite`，避免两个规则争写同名池。

**行为变化：** `request.members` 是本次环境选择后的准确六个成员，不是 `request.accepted`。
把旧档案和这些成员合并，再发布最多两条精确引用；同一候选退出种群也可因档案引用而继续保留。
`inject(..., replace=True)` 产生原事务中的普通池成员更新，失败仍随步骤回滚，不另起一次维护提交。
不会把档案反向注入 GA、自动让 VNS 精修它，或另调 evaluate。

**运行与检查：** 在副本 Project 根目录执行以下命令；默认组还会串行运行原 VNS 与 MOEA/D Case。

```powershell
python run_project.py --check --build-check
python run_project.py --no-record
```

读取 `results/ga_search.json`：`final.elite.refs` 是两条历史档案引用，`result.refs` 是 GA 的六个最终成员；
它们不能互相替代。该默认规模的本轮实跑为 **10 次提交、42 次求值、六个最终成员、两条档案引用**。
`accepted.refs`、`change_output.refs` 则是接纳历史/变化输出，不应按其条数冒充最终成员数。
`initial.unit_exists` 应为 false，读取说明或挂载回调不提前创建 Unit。

**限制：** 这个档案显式偏好双目标和，可能淘汰 Pareto 前沿的极端点；它不是完整 Pareto 档案。
原有 ParetoArchivePlugin 继续维护自己的原始非支配档案，不要把两者起同一个语义名字。
多目标权重、最大化方向或约束排序改变时，应改真实 `elite_key` 并说明，不能让框架猜。
checkpoint 仍要求相同回调与配置；旧工厂的档案日志不能当作本变体结果。

## extension.adapter.moead

### 变体一：同一批方向交给两个独立精修器，等双方完成后一起返回竞争

**目的：** 比较 VNS 与 Pattern Search 对同一方向起点的不同搜索，而不是让 Pattern Search 继续 VNS 的后继。
这是与主例串行精修不同的算法编排：两支各自形成结果，原 MOEA/D 最后比较全部结果。

**改在哪里：** 复制 `examples/cases/assembly_workbench/`。
该 Project 已有 `parallel_refiners` 组，可直接运行，配置会给 `DirectionsConfig.refinement_layout="parallel"`。
若希望把这个装配固定写清楚，可在副本 `cases/directions/adapter/composition.py` 保留其它帮助函数，
将 `parallel_results` 和 `build_adapter` 完整替换为下方内容。imports 已包含下列公开类和函数。

```python
from nsgablack.adapters import (
    MOEADAdapter, MultiStrategyConfig, PatternSearchAdapter, PoolTaskSpec,
    SearchPlanAdapter, StrategySpec, VNSAdapter, multi, serial, stage, subpools,
)
from nsgablack.representation import (
    ContextGaussianMutation, GaussianMutation, UniformInitializer,
)


def parallel_results(control, context):
    del context
    root = control.adapter
    return (root.get_pool_task_results(control, "coarse")
            + root.get_pool_task_results(control, "fine"))


def build_adapter(settings):
    if settings.refinement_layout != "parallel":
        raise ValueError("use the parallel_refiners Project group for this variant")
    moead = MOEADAdapter(
        name="direction_owner", population_size=settings.directions, batch_size=3,
        neighborhood_size=3, decomposition="tchebycheff", random_seed=settings.seed,
        initializer=UniformInitializer(-2.0, 2.0),
        mutator=GaussianMutation(sigma=0.3))
    coarse = VNSAdapter(name="coarse_vns", batch_size=1, base_sigma=0.35,
        restart_on_stagnation=False,
        mutator=ContextGaussianMutation(base_sigma=0.35))
    fine = PatternSearchAdapter(name="fine_pattern", max_directions=1, step_size=0.08)
    directions = (subpools.all(moead) if settings.direction_sample is None
                  else subpools.random(settings.direction_sample, moead))
    return SearchPlanAdapter(
        serial(stage("moead", steps=settings.bootstrap_steps, label="search"),
               multi(stage("coarse"), stage("fine")),
               stage("moead", label="return")),
        strategies=[
            StrategySpec(moead, "moead", pool_task=PoolTaskSpec(
                parallel_results, mode="compete", phases=("return",), shuffle=False)),
            StrategySpec(coarse, "coarse", pool_task=PoolTaskSpec(
                directions, count=1, steps=settings.local_steps, output=None, shuffle=False)),
            StrategySpec(fine, "fine", pool_task=PoolTaskSpec(
                directions, count=1, steps=settings.local_steps, output=None, shuffle=False)),
        ], config=MultiStrategyConfig(
            total_batch_size=settings.router_budget, adapt_weights=False),
        name="direction_plan")
```

**行为变化：** 两支读的都是 `moead` 的已发布方向视图，每份取一个起点，各自冻结该任务的权重与参考点。
这里 fine 的输入是 `directions`，不是串行主例的 `subpools.all(coarse)`。
`multi` 等两支的 PoolTask 完成，再进入 return；`parallel_results` 只交本请求的最终选择，
按 coarse、fine 的顺序保留六条结果引用，不拿历次接纳试探替代最终选择。

**运行与检查：** 在副本 Project 根目录执行：

```powershell
python run_project.py --group parallel_refiners --check --build-check
python run_project.py --group parallel_refiners --no-record
```

默认三方向的本轮正式 Project 实跑为 **9 次提交、27 次求值、六条最终返回**。
查看 `results/directions/summary.json`：`refinement_layout` 为 parallel，`returned_roles` 为 coarse/fine；
`views.coarse` 与 `views.fine` 的 parent 均指向 MOEA/D 方向视图，
而不是 fine 的 parent 指向 coarse。`final_results.raw_objectives` 和 `final_population.raw_objectives` 仍有两列。
返回阶段重新评估六条候选，再由原 MOEA/D 根据自己的当前方向规则替换，未改 Problem。

**限制：** 这里的并行是同一 Solver 内两个分支共同推进，不因此增加线程、Solver 或 L0 授权。
默认 `router_budget=6` 容纳完整返回；增大方向数须一并核对配置约束与返回量。
不能把方向标量写回母池原始目标，也不能把两个精修器的 Unit 互换。
单纯给 fine 换成不支持投影任务的 Adapter 仍应拒绝；任务装配统一不代表算法能力相同。

## extension.adapter.vns

### 变体一：邻域变化显式读取参考子池，同时输出接纳的试探历史

**目的：** 不只对当前点加高斯噪声，而是让当前点向一个明确参考池中的候选靠近，再沿随机方向走一步。
这是变化算子的职责；VNS 继续决定当前点、比较、接受与邻域切换，不把这些决定搬进 Pipeline 或 Bias。

**改在哪里：** 使用 `examples/cases/pool_workflow_pilot/` 的独立副本。
其中 `cases/vns_search/adapter/workflow.py` 已实现这一变体。保留它的 `elite_key/maintain_elite`，
需要按自己的邻域修改时，完整替换 `neighborhood_change` 和 `build_adapter`：

```python
import numpy as np
from nsgablack.adapters import (
    ChangeResult, MultiStrategyConfig, PoolOutput, PoolTaskSpec,
    RoleSpec, StrategyRouterAdapter, VNSAdapter,
)


def neighborhood_change(request, *, rng):
    if len(request.source_refs) != 1 or request.parents.flags.writeable:
        raise ValueError("expected one immutable, exactly identified parent")
    direction = rng.normal(size=request.candidate.shape)
    direction /= max(float(np.linalg.norm(direction)), 1e-12)
    reference = request.pool.subpool("reference").random(1, rng=rng).values[0]
    center = 0.8 * request.candidate + 0.2 * reference
    child = center + float(request.parameters["sigma"]) * direction
    return ChangeResult(child, outputs=(PoolOutput("vns_trials", create=True),))


def build_adapter(settings):
    worker = VNSAdapter(name="vns", batch_size=settings.batch_size, k_max=3,
        base_sigma=0.15, scale=1.7, max_sigma=0.7,
        restart_on_stagnation=False, change=neighborhood_change)
    worker.set_pool_maintenance(maintain_elite)
    return StrategyRouterAdapter(name="vns_workflow", roles=[RoleSpec("search", worker,
        pool_task=PoolTaskSpec(mode="initialize", count=1, shuffle=False,
            change_sources=("reference", "elite"), change_allow_main=True))],
        config=MultiStrategyConfig(total_batch_size=settings.batch_size, adapt_weights=False))
```

同一文件已从NumPy导入 `np`，并从 `nsgablack.adapters` 导入这段使用的公开类；
`request`、`rng` 和 `sigma` 由 VNS 的正式 change 调用提供。
Project 里的 `PipelineSource` 先通过问题管线生成三个初值，创建 `reference` 引用集合及空 `elite` 集合；
不是由 change 凭空初始化这些池。工厂的 `change_sources` 是实际读取声明，不能只在函数里写池名却不授权。

**行为变化：** 初次起点仍正常修复、评估，随后每次变化从被冻结输入允许的参考池读一个候选。
`request.candidate` 是草稿输入，不原位改写父解；返回的新提案独立派生身份，repair 保留该提案token。
`PoolOutput` 只有在本提案已评估、接纳并提交后才入 `vns_trials`；不会把未评估草稿写成公开解。
此处绑定完整 `change`，不会再叠加原高斯 mutator。

**运行与检查：** 副本 Project 根目录运行 `python run_project.py --check --build-check`，
再运行 `python run_project.py --no-record`；默认组还包括 GA、MOEA/D 两个独立 Case。
读取 `results/vns_search.json`：本轮默认配置实跑 **10 次提交、28 次求值**，
`result.refs` 一条是 VNS 最终任务选择，`change_output.refs` 为27条接纳试探历史。
前者不等于当前点的所有历史，后者也不保证每条都改善目标。
`result.raw_objectives` 与候选重新按 Problem 公式计算应一致，不要用输出池条数宣称精修成功。

**限制：** `reference` 是初始候选的参考集合，不自动成为精英池；参考候选不要求已经带有可比较分数，
这里仅使用候选数值。若要按参考分数挑选，必须先通过正式求值取得对应反馈。
任务读取权限不会因为存在同名池而自动放宽；本例的 `change_allow_main=True` 只允许本任务声明的区域。
物理存储、身份、预算、处置与回滚仍由现有运行时维护，不在 change 内绕过它们。
