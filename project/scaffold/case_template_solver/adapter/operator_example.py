"""可选的独立算法操作装配；不会自动修改当前 Case 或替换默认选择规则。

在 build_solver 中创建 adapter 后，经既有入口交付：
    component_overrides={"adapter": build_operator_adapter()}
也可注册为当前 Case 的 builder：
    register_adapter_builder("operator_nsga2", lambda params: build_operator_adapter(**params))

parent_pool 指向运行中已经发布的具名子池；它不创建精英档案，也不负责排序。
该池必须在首次父代选择前存在且非空。省略 parent_pool 保留 NSGA-II 默认父代选择。
algorithm 可选 nsga2/nsga3/spea2/de/moead/sa/vns。默认问题 Pipeline
仍提供初始化和问题修复；initializer=UniformInitializer(...) 可显式替换候选生成。
PoolTask 输入和暖启动始终优先于 initializer，不因装配初始化组件而忽略输入池。
selector 仅在显式传入时覆盖对应选择位置：NSGA 的 survivor、DE/MOEA/D 的
replacement、SA 的 proposal_order、VNS 的 candidate；SA 仍执行 Metropolis。
parent_pool 只适用于 NSGA 父代来源，与上述评估后选择是不同契约。
每次调用创建独立的有状态 mutator，不能把同一实例同时交给另一 Adapter 或 Pipeline。
DE 的变异是差分 trial 后处理；MOEA/D 保留方向、邻域和 nr，不换成全局种群选择。
NSGA/VNS/MOEA-D 可传 change=普通函数；签名 function(request, *, rng)，本叶不再
执行默认变化。NSGA 还允许 ChangeBatchResult(results=(ChangeResult(...), ...))，
每次最多返回 request.max_outputs 个孩子；单候选叶不自动变成任意批量算法。
函数可组合交叉/扰动顺序，不需要继承或手写 codec。与显式 mutator/具名变异互斥。

完整变化也可通过调用期只读池选择额外来源，输出去向另行声明：
    from nsgablack.adapters import ChangeResult, PoolOutput

    def cross_with_elite(request, *, rng):
        elite = request.pool.subpool("elite").random(1, rng=rng)
        child = (request.candidate + elite.values[0]) / 2
        child = child + rng.normal(0, 0.01, child.shape)
        return ChangeResult(child, source_refs=elite.refs,
                            outputs=(PoolOutput("offspring", create=True),))

elite 必须在调用开始时已经发布。request.pool.main() 可选母池，take/random/merge
保留精确候选版本；raw_feedback() 只读原始求值，不自动投影或替代重新评估。
PoolTask 内额外具名来源须由 change_sources 声明，母池须显式 change_allow_main=True。
低层直接构造的 ChangeRequest 可以没有 pool；正常 Solver 调用才提供此能力。
request.pool 与选择对象不可留待函数返回后使用，候选只在访问 values 等数据时加载。
选择还支持 where、显式key的order_by/top、intersection/difference及groups；不隐含求值。
普通集合维护使用计划：
    kept = request.pool.main(stage="accepted").top(20, key=raw_elite_key)
    edit = request.pool.replace_members("elite", kept.refs)
    return ChangeResult(child, edits=(edit,))
raw_elite_key(selection) 显式读取原始反馈并返回(N,)或(N,K)排序键；不会猜多目标比较。
elite 须预先创建并在PoolTask中声明允许访问；计划基于调用前已发布版本，接纳后才统一应用。
完整写法见 docs/architecture/POOL_COLLECTION_OPERATIONS_CN.md。
本批求值后的档案维护可以单独绑定，每个真实叶 update 只调用一次：
    def maintain_elite(request, *, rng):
        kept = request.pool.subpool("elite").merge(request.accepted).top(20, key=raw_elite_key)
        return (request.pool.replace_members("elite", kept.refs),)
    adapter.set_pool_maintenance(maintain_elite)
request.accepted 是本批硬接纳结果，不等于算法最终成员；这项受限读取权限不会扩大 main。
种群最终成员另由 request.members 交付，保留真实顺序与选择反馈；VNS 等轨迹算法为 None。
需要历代最终成员档案时，可绑定下面的 maintain_member_archive；规则显式按 raw 可行性/目标和排序。
Pool(parent=request.pool, name=...) 构造本次调用的空草稿；inject(..., replace=True)
声明精确成员，缺失集合创建、已有集合替换。构造但不注入不会创建；PoolTask 仍须声明准确公共池名。
不同 root 的 merge 不自动合成一种选择评分，合并历史档案时显式读取 raw。
NSGA 的 selector 也可以是 choose(pool, *, rng)->Pool 普通函数；应返回输入的准确位置子集，
例如 pool.take(indices)，不把同值候选或重复槽位混为一谈。原选择组件的局部索引协议保留。
需要同时得到所选与剩余时，用partition(pool, by=choose, rng=rng)，只计算一次规则，
返回两个同作用域的Pool；它按位置取补集，不等于difference的精确引用差集。
下面的choose_with_partition是显式首目标精英示例，不会默认替换NSGA的Pareto规则：
    from functools import partial
    adapter.set_selector(partial(choose_with_partition, count=population_size))
若希望同一次选择还交付精英与剩余普通池，使用choose_with_outputs：
    adapter.set_selector(partial(choose_with_outputs, count=population_size))
它返回members，并用Pool(parent=..., name=...).inject(selected, replace=True)声明副池。
主结果仍决定Unit成员；副结果仅可引用同一offered Pool的准确位置，可为空，均随步骤提交。
source.chosen(rule, rng=rng)在非空输入上执行一次同步选择，不隐含求值；同调用内可继续读取草稿，
外部只在提交后读到结果。parent表示调用来源，不改变持久parent/ancestors或自动继承投影。
这只适用于GA生存选择，不让其它purpose暗中创建档案，不保存运行期Pool活对象。
ChangeResult 的输出只是声明，控制面在正常 repair/评估/接纳之后写入；失败步骤回滚，
拒绝提案不入池，未提交输出不可读。输出收集接纳提案，不冒充本轮最终最优解或 Unit 成员。
本例不装配 UnitRepair；启用它必须在正式 build_solver 中同时装配 JointRepairPolicy
和支持只读 validate 的 ProblemRepair，不能仅给 Adapter 塞一个 repair 回调。
职责与更多装配见 docs/architecture/ADAPTER_OPERATION_BOUNDARIES_CN.md。
"""
from nsgablack.adapters import (
    DifferentialEvolutionAdapter, MixedPoolParentSelector, MOEADAdapter,
    NSGA2Adapter, NSGA3Adapter, Pool, SimulatedAnnealingAdapter, SPEA2Adapter, VNSAdapter,
    partition,
)
from nsgablack.representation.continuous import ContextGaussianMutation, GaussianMutation
import numpy as np


def _first_objective(pool):
    return pool.objectives[:, 0]


def choose_with_partition(pool, *, count, elite_count=2, rng=None):
    """显式首目标精英+其余位置；返回Pool由实际Adapter应用。"""
    count = min(count, len(pool))
    def choose_elite(offered):
        return offered.top(min(elite_count, count), key=_first_objective)
    selected, remaining = partition(pool, by=choose_elite, rng=rng)
    return selected.concat(remaining.take(range(count - len(selected))))


def choose_with_outputs(pool, *, count, elite_count=2, rng=None):
    """主成员照常返回；精英与剩余注入本地草稿，随原步骤提交。"""
    count = min(count, len(pool))
    def choose_elite(offered):
        return offered.top(min(elite_count, count), key=_first_objective)
    selected, remaining = partition(pool, by=choose_elite, rng=rng)
    needed = count - len(selected)
    members = selected.concat(remaining.take(range(needed)))
    elite = Pool(parent=members, name="elite")
    elite.inject(members.take(range(len(selected))), replace=True)
    reserve = Pool(parent=pool, name="reserve")
    reserve.inject(remaining.take(range(needed, len(remaining))), replace=True)
    return members


def _raw_archive_key(pool):
    objectives, violations = pool.raw_feedback()
    return np.column_stack((violations > 0., np.maximum(violations, 0.), objectives.sum(axis=1)))


def choose_young_members(pool, *, count):
    """示例规则：年轻优先、再按第一目标；count由实际生存请求提供。

    所属Unit须声明并维护age。不是默认NSGA-II环境选择。
    build_operator_adapter(selector=choose_young_members)直接绑定，无需重复容量。
    """
    age = pool.member_field("age", default=0)
    key = np.column_stack((age >= 2, pool.objectives[:, 0]))
    return pool.top(count, key=lambda offered: key)


class YoungMemberParents:
    """按本种群成员年龄筛选父代，抽样结果保留实际槽位。"""
    stateless = True

    def checkpoint_identity(self):
        return {"name": "young_member_parents", "age_limit": 2}

    def select(self, request, *, pool, rng):
        eligible = request.members.where(lambda p: p.member_field("age") < 2)
        if not len(eligible):
            eligible = request.members
        return eligible.sample(request.count, rng=rng, replace=True)


def age_scaled_change(request, *, rng):
    """完整变化示例：从对齐父代属性决定扰动尺度，不自行repair或求值。"""
    ages = request.parent_pool.member_field("age")
    center = request.parents.mean(axis=0)
    sigma = .05 / (1 + float(np.max(ages)))
    return center + rng.normal(0., sigma, center.shape)


def maintain_member_archive(request, *, rng, name="archive", count=20):
    """历史+本轮最终成员；显式raw目标和示例，不是默认Pareto规则。

    同样可绑定router.set_pool_maintenance(maintain_member_archive)，
    在子更新汇合后统一归并；此时members只有引用，排序显式读取raw。
    """
    if request.members is None:
        raise ValueError("member archive requires an evaluated population result")
    names = request.pool.describe()["subpools"]
    previous = request.pool.subpool(name) if name in names else request.members.take(())
    kept = previous.merge(request.members).chosen(
        lambda offered: offered.top(count, key=_raw_archive_key), rng=rng)
    archive = Pool(parent=request.pool, name=name)
    archive.inject(kept, replace=True)


def build_operator_adapter(*, algorithm="nsga2", population_size=8, offspring_size=8,
                           mutation_sigma=0.1, parent_pool=None, pool_fraction=0.5,
                           initializer=None, mutator=None, selector=None, change=None,
                           pool_maintenance=None, adapter_params=None):
    factories = {"nsga2": NSGA2Adapter, "nsga3": NSGA3Adapter, "spea2": SPEA2Adapter,
                 "de": DifferentialEvolutionAdapter, "moead": MOEADAdapter,
                 "sa": SimulatedAnnealingAdapter, "vns": VNSAdapter}
    if algorithm not in factories:
        raise ValueError(f"Unsupported operator example algorithm: {algorithm!r}")
    nsga = algorithm in {"nsga2", "nsga3", "spea2"}
    if parent_pool is not None and not nsga:
        raise ValueError("parent_pool belongs to NSGA parent selection, not trial or neighbor selection")
    pool_consumers = {"nsga2", "nsga3", "spea2", "vns", "moead"}
    if change is not None and algorithm not in pool_consumers:
        raise ValueError("ordinary complete change requires an explicit NSGA/VNS/MOEA-D consumer")
    if pool_maintenance is not None and algorithm not in pool_consumers:
        raise ValueError("pool maintenance requires an explicit NSGA/VNS/MOEA-D consumer")
    if change is not None and mutator is not None:
        raise ValueError("choose complete change or the separate mutator")
    params = dict(adapter_params or {})
    if "repair" in params:
        raise ValueError("Assemble UnitRepair with JointRepairPolicy and ProblemRepair.validate in build_solver")
    defaults = ({"population_size": population_size, "offspring_size": offspring_size} if nsga else
                {"population_size": population_size, "batch_size": offspring_size}
                if algorithm in {"de", "moead"} else {"batch_size": offspring_size})
    adapter = factories[algorithm](**{**defaults, **params})
    if change is not None:
        adapter.set_change(change)
    else:
        if mutator is None:
            mutator = (ContextGaussianMutation(base_sigma=mutation_sigma) if algorithm in {"sa", "vns"}
                       else GaussianMutation(sigma=mutation_sigma))
        adapter.set_mutator(mutator)
    if initializer is not None:
        adapter.set_initializer(initializer)
    if selector is not None:
        adapter.set_selector(selector)
    if pool_maintenance is not None:
        adapter.set_pool_maintenance(pool_maintenance)
    if parent_pool is not None:
        adapter.set_parent_selector(MixedPoolParentSelector(parent_pool, pool_fraction=pool_fraction))
    return adapter
