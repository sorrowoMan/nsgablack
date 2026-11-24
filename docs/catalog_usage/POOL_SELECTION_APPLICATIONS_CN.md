# Pool 选择、父代交接与精确版本：把“选哪些”写成可读代码

本页直接使用现有正式 Project，既不增加私有运行循环，也不调用模型。三个对象要分清：`SolutionPool` 是运行内版本存储；`Pool`（`ChangeSelection` 的公开别名）是一次回调内的有序引用视图；`SelectionRequest` / `ParentSelectionRequest` 是算法发出的不同决策请求。以下只经源码核对，未运行改装后的算法，未产生运行收据。

## tool.pool_partition · 一次生存选择，交回成员并写精英池

**什么时候用：** 希望 GA 先保留明确的两个精英，再从其余候选补足成员；下一轮从上轮已提交精英抽父代。精英池保存引用，不复制解，不把子池当另一套种群。

**先准备什么：** 复制完整 `examples/cases/pool_workflow_pilot` Project。需要当前 nsgablack、blackbase 与 NumPy。使用它的 `cases/ga_search/`，保留原 TwoCenters Problem、UniformInitializer/ClipRepair、CaseConfig 和 Project L0。默认源数8、种群容量6、后代4、逻辑步数10、seed37分别配置。二维候选的 raw 目标是到 `(-1,0)` 与 `(1,0)` 的平方距离；源种子尚未求值。

**放在哪：** 完整替换 `cases/ga_search/adapter/workflow.py`；原 `build_solver.py` 仍从这个模块导入 `build_adapter`，无需改它。原 PipelineSource 在正式启动钩子生成种子并创建空 elite，Router 初始化成员；第一轮送评后才有可抽取父代。

**接入步骤：** 保存下方完整文件。

```python
from functools import partial
import numpy as np
from nsgablack.adapters import (
    ChangeBatchResult, ChangeResult, MixedPoolParentSelector, MultiStrategyConfig,
    NSGA2Adapter, Pool, PoolOutput, PoolTaskSpec, RoleSpec,
    StrategyRouterAdapter, partition,
)


def raw_key(pool):
    objectives, violations = pool.raw_feedback()
    return np.column_stack((violations > 0.0, np.maximum(violations, 0.0),
                            np.sum(objectives, axis=1)))


def choose_survivors(pool, *, count, rng):
    quota = min(2, count, len(pool))
    elite, rest = partition(
        pool, by=lambda offered: offered.top(quota, key=raw_key), rng=rng)
    needed = min(count, len(pool)) - len(elite)
    members = elite.concat(rest.take(range(needed)))
    reserve = rest.take(range(needed, len(rest)))
    Pool(parent=members, name="elite").inject(elite, replace=True)
    Pool(parent=pool, name="reserve").inject(reserve, replace=True)
    return members


def paired_change(request, *, rng):
    if len(request.parents) != 2 or len(request.source_refs) != 2:
        raise ValueError("this change requires two exactly identified parents")
    left, right = request.parents
    mask = rng.random(left.shape) < 0.5
    children = (np.where(mask, left, right), np.where(mask, right, left))
    return ChangeBatchResult(results=tuple(
        ChangeResult(child + rng.normal(0.0, 0.1, child.shape),
            source_refs=request.source_refs,
            outputs=(PoolOutput("ga_trials", create=True),))
        for child in children[:request.max_outputs]
    ))


def build_adapter(settings):
    ga = NSGA2Adapter(name="ga", population_size=settings.population_size,
        offspring_size=settings.offspring_size, change=paired_change,
        parent_selector=MixedPoolParentSelector("elite", pool_fraction=1.0))
    ga.set_selector(partial(choose_survivors, count=settings.population_size))
    return StrategyRouterAdapter(name="ga_workflow", roles=[
        RoleSpec("search", ga, pool_task=PoolTaskSpec(
            mode="initialize", count=settings.population_size, shuffle=False,
            change_sources=("elite",),
        )),
    ], config=MultiStrategyConfig(
        total_batch_size=max(settings.population_size, settings.offspring_size),
        adapt_weights=False,
    ))
```

这份生存规则**有意改变默认 NSGA-II 环境选择**：只有前两个位置按 raw 可行性、违反量、目标和排序，其余按 offered 的输入次序补齐。它不是 Pareto 前沿选择，`rest` 也不是“所有不好的解”。想保留默认多目标选择时用下一节的变体，不把目标和偷换成默认多目标含义。

`partition` 对非空 Pool 只调用规则一次，返回选中位置及位置补集。规则内只选，外层才 inject；补集按原位置计算，同一个精确引用在不同输入位置出现时仍是不同 occurrence。`concat` 保留位置、顺序和重数，不按数值去重；最终生存返回仍禁止重复原位置。`Pool.all()` 也是 Pool，范围只是当前视图，不会扩大到母池。

具名 `Pool(parent=..., name=...)` 是空调用期草稿；inject 在本次选择后生成 PoolEdit，随成员 Unit 和原步骤事务一起提交。`replace=True` 将 elite/reserve 精确替换，空 reserve 也可创建；不是立刻让下游看到结果。`parent` 不重新定义持久父子拓扑或交还路径。不得缓存这些 Pool 活对象在下一次回调使用。

父代选择与生存选择是两个接缝。MixedPoolParentSelector 收到 ParentSelectionRequest：有序 population_refs、对应 rank/crowding、count 和标量 context；另有 pool/rng 显式参数。这里每次需要两个父代，pool_fraction=1.0 都从上一轮公开 elite 有放回抽取，因此可能是同一精确引用两次。它不把父代纳入当前 Unit，也不增加求值。PoolTask 的 change_sources 仍必须声明 elite，不能因返回的是合法引用就绕过任务范围。把比例改成0.5时，两父代配额四舍五入为一个 elite、一个当前成员锦标赛位置，不是每次独立抛硬币。

**怎样判断接对：** 查看本次 Project 终态与中央 `results/ga_search.json` 的 run_id；旧文件不等于本次成功。`result.refs` 是最终6个成员，`final.elite.refs` 应最多2个且属于同次成员；`change_output` 的 ga_trials 是后续硬接纳孩子，不等于最终成员。孩子 provenance 的 `metadata.change_source_refs` 是两个父代版本；它们可能离开最终 Unit，不要以 token 或坐标相等追读其它版本。原 WorkflowTrace 不显示 reserve；如需额外检查，在同 Case 的提交后观察钩子读 `solver.solution_pool.subpool_refs("reserve")`，不要在 init 读取尚不存在的 reserve。elite、reserve 来自同一 offered 集合，二者不交叉；首轮 reserve 可以为空。默认10步足以进入变化；只跑初始化时 ga_trials 尚不存在，原观察器的最终输出读取不适用。

**运行入口：** 在原 Project 的 project_config.py 末尾追加下方分组，保留原 L0、STAGES/GROUPS；从仓库根运行命令。不要用原 `run_and_report.py`，它针对三个原 Case 的特定默认归档规则。

```python
STAGES.append({
    "name": "ga_selection", "cases": ["ga_search"], "policy": "serial",
    "resource_requests": {
        "ga_search": {"threads": 1, "gpus": 0, "backend": "local"},
    },
})
GROUPS["selection"] = {"stages": ["ga_selection"]}
```

```powershell
python examples/cases/pool_workflow_pilot/run_project.py --group selection
```

本节与紧接的变体节一起构成完整用法。来源：[Pool 与反馈](../../adapters/change_pool.py)、[位置分区](../../adapters/pool_partition.py)、[独立父代请求](../../adapters/parent_selection.py)、[原正式 builder](../../examples/cases/pool_workflow_pilot/cases/ga_search/build_solver.py)。

## pool.selection.variants · 换比较规则，不改候选存储或执行循环

本节接续 `tool.pool_partition` 主例；每个变体独立应用，不叠加。

### 变体一：保留 Pareto 生存选择，只从最终成员取精英

**目的：** 恢复非支配排序与拥挤度选择，再从实际最终成员分出两个按 raw 目标和排序的精英。

**改在哪里：** 在同一个 adapter/workflow.py 增加导入，完整替换 choose_survivors；其它工厂、raw_key 与 paired_change 保留。

```python
from nsgablack.utils.performance.fast_non_dominated_sort import FastNonDominatedSort


def choose_survivors(pool, *, count, rng):
    objectives, violations = pool.selection_feedback()
    fronts, _ = FastNonDominatedSort.sort(objectives, violations)
    selected = []
    for front in fronts:
        remaining = count - len(selected)
        if len(front) <= remaining:
            selected.extend(front)
        else:
            distance = FastNonDominatedSort.calculate_crowding_distance(objectives, front)
            selected.extend(sorted(front, key=lambda row: (-distance[row], row))[:remaining])
        if len(selected) == count:
            break
    members = pool.take(selected)
    elite = members.chosen(lambda offered: offered.top(2, key=raw_key), rng=rng)
    _, reserve = partition(pool, by=lambda offered: offered.take(selected), rng=rng)
    Pool(parent=members, name="elite").inject(elite, replace=True)
    Pool(parent=pool, name="reserve").inject(reserve, replace=True)
    return members
```

**行为变化：** 主成员使用本消费者的 selection feedback；elite 用 raw，明确这是两项决策。反馈无 Bias 时两者可相同，不能据此将接口视为同一个。reserve 是未生存位置而非未硬接纳候选，子池仍在同一步提交。

**限制：** 两目标和只用于精英池的定向规则；这不意味着两个精英代表整个 Pareto 前沿。拥挤距离的无穷边界只在排序键中处理，没有作为要求有限数值的 Pool.top key 传入。

### 变体二：用正式 SelectionRequest 对象组件做单目标优先选择

**目的：** 当明确要优先改善第一目标时，使用既有可独立装配的选择器，而不是普通 Pool 回调。

**改在哪里：** 在主例模块增加以下完整无状态类及绑定辅助函数；在 build_adapter 中将原 ga.set_selector 绑定行改为 `bind_first_objective_survivors(ga)`。保留原父代选择器及声明。

```python
from nsgablack.adapters import FeasibilityFirstSelection, SelectionRequest


class FirstObjectiveSurvivors:
    stateless = True

    def checkpoint_identity(self):
        return {"kind": "first-objective-survivors", "objective_index": 0}

    def select(self, request, *, rng):
        if not isinstance(request, SelectionRequest) or request.purpose != "survivor":
            raise ValueError("this component only owns survivor selection")
        if request.pool is None:
            raise ValueError("exact Pool rows are required for named outputs")
        indices = FeasibilityFirstSelection(objective_index=0).select(request, rng=rng)
        members = request.pool.take(indices)
        elite = members.top(2, key=raw_key)
        return members, {"elite": elite}


def bind_first_objective_survivors(ga):
    ga.set_selector(FirstObjectiveSurvivors())
```

在 build_adapter 中调用 `bind_first_objective_survivors(ga)` 替换原绑定行，而不是把 ga 当成模块级已定义变量。对象的 select 接收完整 SelectionRequest；普通函数则经桥接只接收 Pool。这里目的必须是 survivor，其候选、目标、违反量、count、parameters、轻量 context 和可选 Pool 均由 NSGA2 生成，用户不手造请求。

**行为变化：** 选择器按可行性、违反量、第一目标和原位置排序；有 request.scores 时该组件优先使用 scores，本 GA 请求没有该字段。返回 `(members, {"elite": elite})` 自动交付同一生存请求的具名副结果，不用另加维护回调。elite 在初轮建立，后续父代仍可读取。

**限制：** 此变体改变原多目标生存语义；FeasibilityFirstSelection 读取 request 的**选择反馈**，不是原始约束接纳门。硬可行性接纳仍由 FeasibleEvaluationAcceptance 的 raw 规则负责。此变体不再更新 reserve，主例创建过的旧 reserve 可能保留旧内容；在独立 Project 副本应用本变体，不将旧 reserve 作为本轮结果。

### 变体三：自己定义父代规则，仍返回精确引用

**目的：** 从当前种群中，按 rank 后 crowding 选同一个最佳成员作两个父代，检验父代接口而无需修改 Adapter。

**改在哪里：** 在主例模块增加完整类，工厂的 parent_selector 参数改为 RankedParents()；主例生存函数保留。

```python
from nsgablack.adapters import ParentSelectionRequest


class RankedParents:
    stateless = True

    def checkpoint_identity(self):
        return {"kind": "ranked-parents", "tie_break": "original-position"}

    def select(self, request, *, pool, rng):
        del rng
        if not isinstance(request, ParentSelectionRequest):
            raise TypeError("parent selector requires the formal request")
        pool.read(request.population_refs)
        best = min(range(len(request.population_refs)),
                   key=lambda row: (request.rank[row], -request.crowding[row], row))
        return (request.population_refs[best],) * request.count
```

**行为变化：** 不读 elite，只用当前 Unit 成员及其脱离后的排名；重复父代由规则明确允许，孩子仍生成新身份。首次初始化不调用父代选择。

**限制：** 这可能使搜索过早收敛，只用于说明可替换接缝，不承诺算法更好。该组件无内部计数，stateless 与身份声明相符；有历史状态时还须实现 Mapping 状态 codec 并随所属 Adapter 回滚/恢复。父代接口输出 SolutionRef，不是生存请求的局部行号。

来源：[SelectionRequest 与选择器](../../adapters/selection.py)、[NSGA2 正式消费位置](../../adapters/nsga2/adapter.py)、[父代范围验证](../../tests/test_ga_parent_access.py)；仅源码核对。

## tool.solution_ref · 提交后核对精确成员和逻辑时点

**什么时候用：** 想保存“这一轮选中的到底是哪一个版本”，并在有限运行中开启闲置回收。SolutionRef 的 pool_id、record_id、row、candidate_token 共同寻址；token 单独不是版本地址，row 不是数组压缩后的新编号。SolutionStamp 的 run_id/sequence 是运行内逻辑时点，不是墙上时间。

**先准备什么：** 在上述主例的独立 Project 副本继续。原 Source、Router、GA 与两孩子提案保持，使用默认 max_steps=10。新增观察器继承原有只读 WorkflowTrace，复用其有界历史、get_state/set_state 和运行身份复位；不让插件发起求值或建立 Unit。

**放在哪：** 新建 `cases/ga_search/plugins/identity_trace.py`，完整内容如下。替换同 Case 的 build_solver.py 为下方薄装配。保留上一节配置的 selection 分组。原中央报告 `results/ga_search.json` 会包含新增观察字段；不再另建重复报告权威。

**接入步骤：**

```python
from nsgablack.core import SolutionRef, SolutionStamp
from workflow_trace import WorkflowTrace, workflow_worker


class IdentityTrace(WorkflowTrace):
    def __init__(self, *, max_steps):
        super().__init__(case_name="ga_search", max_steps=max_steps)

    def _observe(self):
        result = super()._observe()
        solver, pool = self.solver, self.solver.solution_pool
        leaf = workflow_worker(solver.adapter).inner
        refs = tuple(leaf.get_population_solution_refs(solver) or ())
        stamp_data = pool.timestamp.as_dict()
        stamp = SolutionStamp.from_dict(stamp_data)
        recovered = tuple(SolutionRef.from_dict(ref.as_dict()) for ref in refs)
        if recovered != refs:
            raise ValueError("reference serialization changed identity or order")
        accepted = pool.select(at=stamp, stage="accepted")
        if any(ref not in accepted for ref in refs):
            raise ValueError("current members are missing from the committed time window")
        result["identity_audit"] = {
            "stamp": stamp_data,
            "member_refs": [ref.as_dict() for ref in recovered],
            "accepted_at_stamp_count": len(accepted),
            "publication": pool.publication_ref(),
        }
        if refs:
            batch = pool.read(recovered)
            raw_f, raw_v = pool.read_raw_feedback(recovered)
            if tuple(batch.candidate_tokens) != tuple(ref.candidate_token for ref in recovered):
                raise ValueError("candidate token order differs from the exact references")
            result["identity_audit"].update(
                raw_objectives=raw_f.tolist(), raw_violations=raw_v.tolist())
        return result
```

`cases/ga_search/build_solver.py` 完整内容：

```python
from nsgablack.core import ComposableSolver, PoolRetentionPolicy
from nsgablack.plugins import ParetoArchivePlugin
from nsgablack.project import apply_solver_component_overrides
from .adapter.workflow import build_adapter
from .config import CaseConfig
from .pipeline import build_pipeline
from .plugins import PipelineSource
from .plugins.identity_trace import IdentityTrace
from .problem import build_problem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    settings = CaseConfig(**dict(config or {}))
    solver = ComposableSolver(problem=build_problem(),
        representation_pipeline=build_pipeline(), adapter=build_adapter(settings),
        resource_context=resource_context, plugin_strict=True, snapshot_strict=True)
    solver.set_random_seed(settings.seed)
    solver.set_max_steps(settings.max_steps)
    solver.set_solution_pool_retention(PoolRetentionPolicy(
        idle_steps=max(20, settings.max_steps + 1), retained_publications=2))
    solver.add_plugin(PipelineSource(settings.source_count))
    solver.add_plugin(ParetoArchivePlugin())
    solver.add_plugin(IdentityTrace(max_steps=settings.max_steps))
    apply_solver_component_overrides(solver, component_overrides)
    return solver
```

retention 必须在首次池发布前配置；控制面验证实际 Adapter 及子级已声明保留根，不遍历任意对象猜存活解。idle_steps 是连续未被声明使用的已提交步数，retained_publications 是自动保留的发布闭包窗口，二者都不是候选容量。普通子池成员、活跃 Unit、未消费输入等仍保护解；ga_trials 累积全部接纳孩子，因此本例**不能用来证明存储量已降低**。

本例故意让闲置宽限长于运行，以保留原 WorkflowTrace 对历史父引用的完整读取。不将未保护历史当成永久可读：若以后延长运行或把 idle_steps 改为2，原观察器对已回收祖先的读取可能失败，要先收缩历史需求或正式声明保留；仅把引用写进日志不会保留其值。实际物理删除在提交后由共享回收执行，不能在 observer/change 手动 collect_garbage。

**怎样判断接对：** `initial.identity_audit.member_refs` 可为空，种子数量不等于已评估成员数。每条 `records[].identity_audit` 的 run_id 应与报告一致；sequence 可跳号，不能要求等于 generation，回滚后不复用旧时点。member_refs 顺序等于当时真实成员，raw 数组与其逐行对齐。`accepted_at_stamp_count` 是该时点仍在池索引中的接纳历史，不能当“从开始以来永不减少”的总评估计数。publication 是发布 Snapshot 身份，不拿它替代 candidate refs。

**运行入口：** 仍使用 `python examples/cases/pool_workflow_pilot/run_project.py --group selection`。本页未执行；从报告读到字段不等于已证明任何数学性质或压缩收益。

来源：[身份、时点与保留实现](../../core/state/solution_pool.py)、[回收参数](../../core/state/pool_retention.py)、[Solver 根声明检查](../../core/blank_solver.py)、[原观察状态 codec](../../examples/cases/pool_workflow_pilot/workflow_trace.py)。下节给出同一接口的只读历史变体。

## pool.identity.variant · 逻辑时点过滤不等于历史值保留

### 变体一：读某条观察记录之前仍存活的接纳版本

**目的：** 用已序列化的逻辑时点筛选来源，而不是按最新 token 猜曾经的状态。

**改在哪里：** 在同 Case 的 `plugins/identity_trace.py` 追加完整函数；仅在同一次运行的提交后观察函数中调用，把一条先前 `identity_audit.stamp` 作为 saved_stamp，control 为该 Case 的 solver。它是可复用读取辅助函数，不新增 CLI 或私有搜索循环。

```python
def read_surviving_history_at(control, saved_stamp):
    stamp = SolutionStamp.from_dict(saved_stamp)
    pool = control.solution_pool
    refs = pool.select(at=stamp, stage="accepted")
    if not refs:
        return {"refs": [], "candidates": [], "raw_objectives": [], "raw_violations": []}
    batch = pool.read(refs)
    objectives, violations = pool.read_raw_feedback(refs)
    return {
        "refs": [ref.as_dict() for ref in refs],
        "candidates": batch.numeric_matrix.tolist(),
        "raw_objectives": objectives.tolist(),
        "raw_violations": violations.tolist(),
    }
```

**行为变化：** 只读不晚于该运行时点、当前仍可见的已接纳版本，不重新求值、不刷新闲置寿命。使用其它 run_id 的 stamp 会报错，不静默读取另一次运行。

**限制：** at 只提供筛选截止，不“复活”已经退休的行，也不承诺历史时点的完整集合。需要永久值闭包时应使用正式可传输 checkpoint；需要本地旧发布恢复闭包则用既有 publication pin 协议并明确释放，不能依靠日志里的 refs。这里没有展示恢复和 pin 的执行，所以不将这份源码示例标为恢复验证。
