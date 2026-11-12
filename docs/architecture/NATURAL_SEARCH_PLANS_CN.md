# 自然搜索编排：串行、并行与重复

2026-10-21。本文描述已经接入现有 Router 的首版能力；复杂场景推演仍见
[讨论第 39 节](ORCHESTRATION_WITH_INCREMENTAL_UNITS_DISCUSSION_CN.md#39-自然编排先确定场景再决定写法)。

**反向审计后的补充：第 7 节记录重入、旧 Router/Chain 混用、取消对账、权重恢复、
结果身份与历史保留的修复。精修器提前正常终止仍明确拒绝；独立无送评的数据编辑阶段仍未开放。
通过已列组合的行为验证，不等于任意自定义 Python 组件自动满足契约。**

## 1. 最小写法

```python
from nsgablack.adapters import (
    SearchPlanAdapter, StrategySpec, stage, serial, multi, repeat,
)

plan = repeat(
    times=100,
    body=serial(
        stage("ga", steps=100),
        stage("vns", steps=30),
    ),
)

adapter = SearchPlanAdapter(
    plan,
    strategies=[StrategySpec(ga, "ga"), StrategySpec(vns, "vns")],
)
```

`ga` 和 `vns` 是已经装配好的算法实例。计划里的名字引用 StrategySpec.name，
不是类名，也不在每轮复制实例。这个例子只规定运行次序与额度：
GA 保留原种群继续搜索，VNS 保留原轨迹继续搜索。
若希望 VNS 每轮从 GA 最新结果开始，需要按第 3 节绑定池任务。

`steps` 是该位置实际收到非空接纳反馈并更新的次数。
等待、失败、零接纳、兄弟算法工作与纯阶段切换都不占它的额度。
重复一百轮、每轮一百加三十次更新，在没有提前结束、预算耗尽等情况时是 13,000 次逻辑提交。
它不是 13,000 次 Problem 调用：一次更新可能评估多个候选。
Solver 的全局额度仍单独配置，需足以容纳预期工作；例如 run(max_steps=13001)
可为这个固定额度例子及末尾终止检查留出空间。全局上限可以提前停止计划，不被 repeat 自动扩大。

## 2. 组合与生命周期

`serial(a, b)` 等 a 完成再运行 b；`multi(a, b)` 等全部必要分支完成，
先完成的分支暂停；`repeat(times=n, body=...)` 重开主体的局部额度。
这些结构可以在同一棵 ExecutionPlan 值树内互相嵌套：

```python
plan = repeat(times=10, body=multi(
    serial(stage("ga", steps=100), stage("vns", steps=30)),
    repeat(times=2, body=serial(
        stage("moead", steps=20), stage("sa", steps=10),
    )),
))
```

这与“将一个已经构建的 SearchPlanAdapter 或旧 Chain 作为父计划的叶，然后再次激活它”不同。
后者通过 `on_schedule_activation(control, activation_id)` 通知当前局部调用。
已完成的子计划只重开游标，未完成子计划保留冻结请求继续执行；不重放 setup 或重建 Unit。
旧 Chain 作为可重复的子组合时，将孩子退休延后到所属组合最终结束，详见第 7.1 节。

每个名字仍只装配一个实例。`multi` 不建立线程，不替代 Project L0 授权，
也不承诺每个孩子各占一个 worker。候选仍由 Router 收集，经过 Solver 原评估与提交路径。
并行预算不足以覆盖所有活动分支时轮流分配，避免无界分支使兄弟饥饿。

同一名字可以在串行不同位置出现。例如 `ga → vns → ga` 的两处 ga 引用同一算法状态。
两个可能同时活动的分支不能占用同一个名字；同一个可变 Adapter 对象也不能换两个名字重复装配。
需要两个独立 GA 时，显式构造 ga_a 与 ga_b。

setup 每次运行只建立一次干净基线；循环和暂停不重放 setup，也不为观察创建 Unit。
新一轮只重开执行位置，改变搜索起点走已有 PoolTask/restart_search。
所有孩子最终由唯一 owner 结束；退出局部阶段不提前 teardown 后续还会使用的算法。

同一 Plan 树内，局部正常终止先交给直接父级：serial 推进，multi 等待其余分支，repeat 完成本轮。
整个计划完成才正常结束根 Solver。旧 Chain 消费子计划的正常完成并进入下一阶段；
旧 Router 在收集候选时即检查空分支取消，并先向已提案兄弟发送零接纳处置，防止被取消的候选继续送评。
Solver 的停止请求和全局预算继续使用原控制面。
空提案只说明当前没有候选，不能推断任务完成；没有完成证据时仍是等待。

## 3. 真正的 GA → VNS → GA 候选交接

假设 Case 已装配 ga、vns，并由 GA 的既有成员选择回调维护普通精英池。
下面两个命名函数声明精修来源与当前轮结果，不在编排函数里重新实现算法：

```python
def elite_members(control, context):
    # 该集合已由 GA 的选择/更新事务发布。
    return control.solution_pool.subpool_refs("elite")


def refined_this_round(control, context):
    return control.adapter.get_pool_task_results(control, "vns")


plan = repeat(times=100, body=serial(
    stage("ga", steps=100),
    stage("vns"),
    stage("ga", label="return"),
))

adapter = SearchPlanAdapter(plan, strategies=[
    StrategySpec(ga, "ga", pool_task=PoolTaskSpec(
        select=refined_this_round, mode="compete", phases=("return",),
    )),
    StrategySpec(vns, "vns", pool_task=PoolTaskSpec(
        select=elite_members, mode="refine", count="all",
        steps=30, output="refined_history", shuffle=False,
    )),
])
```

上述片段还需从 nsgablack.adapters 导入 PoolTaskSpec。
如果主 Case 已有更高层组合，来源函数应显式引用正确的所属计划实例，
不能假设任意嵌套场景中 `control.adapter` 都是当前计划。
完整脚手架与实际运行见 [GA/VNS Project](../../examples/cases/assembled_ga_vns/PLAN_CN.md)。

这里省略 stage.steps 表示等待这次池任务全部完成。
PoolTaskSpec.steps=30 是每个起点的接纳更新次数，包含起点基准；二十个起点通常需要六百次任务更新。
不要同时给精修阶段填 stage.steps=30，以免误把整个阶段上限当成每个起点额度。
首版对实际启用的 refine/compete 叶拒绝有限正 steps 与 until，避免未完成请求被算进下一轮。
显式 steps=0 可以跳过，不会建立请求。

label 区分同一算法的调用位置：ga 阶段透传正常搜索，return 阶段执行 compete。
GA 只保留一个拥有者，返回竞争没有复制种群或第二套生命周期。
refine/compete 每次新激活得到新请求身份；暂停、重试和恢复保留身份。
initialize 的默认一次性初始化语义不变，不因循环而偷偷重取种子。
若给 initialize 阶段的有限额度不足以交付完整输入，更新明确报错并回滚，不丢弃剩余输入；
可改为省略 steps 等待初始化完成，再进入有额度的普通搜索位置。

`get_pool_task_results(control, role)` 读取当前请求各起点最终选择的精确 SolutionRef。
它要求结果视图已经提交；未完成、未发布、非 refine 都拒绝读取；显式 available 的零起点任务返回空元组。
它不读取累计 output 历史，也不按 token 找未来版本。
原 PoolTaskAdapter 同样提供 `get_pool_task_results(control)`，可用于已有 Router 装配。
结果收据绑定发布时的 pool_id/view_id/revision、解释、创建者与有序成员引用。
同名重建、修改成员或修订不被当成原结果；缺失/变更明确报错，不按数值寻找替代品。
`output=None` 仍发布最终结果，但不创建累计接纳历史；显式 output 才保留该历史。
旧轮结果视图仍是保留根，消费完后使用原池释放方法，不由下一轮自动删除其他消费者的数据。

结果提交后，GA 通过正常 compete 消费并竞争。请求完成进度和池输入游标随原事务保存；
已提交的返回不会在恢复后作为新请求重复结算。失败重试仍可能再次求值，成本继续记录。

## 4. 停滞时切换

首版支持“本阶段运行到条件成立，再进入精修”的暂停式编排：

```python
def quality(feedback):
    return float(feedback.raw_objectives[:, 0].min())


def stagnant(progress):
    return progress.stagnant_updates >= 20


adapter = SearchPlanAdapter(
    plan,
    strategies=specs,
    until={"ga": stagnant},
    metrics={"ga": quality},
)
```

这个 quality 示例明确用于最小化单目标。多目标需装配自己的质量指标；框架不默认为目标求和。
回调键是 stage.label（默认同 role 名）。metric 接收本算法本次实际接纳反馈，返回有限标量，越小越好。
SearchProgress 包含 name、label、activation_id、updates、last_metric、best_metric、stagnant_updates。
首次样本建立基准，此后二十个不改善的新样本才达到二十次停滞。

until 只在本位置有新的已提交更新后检查。VNS 工作或空轮询不增加 GA 的停滞样本。
条件异常传播；返回值必须为 bool，不能把异常吞成不匹配。
下一轮重新建立本阶段观察窗口；这是“继续 GA，再积累新的停滞样本”的重复策略，
没有隐藏的忙时请求队列，也不表示必须先改善才能重新武装。
条件函数与指标函数须为可辨识的命名纯函数；隐藏在闭包或全局变量里的可变历史不由框架保存。

本轮没有实现 GA 继续运行时的独立事件订阅器、竞赛完成、无限循环或任意事件补跑队列。
这些仍需明确其搜索意图，不能仅给现有 EventCase 更名后声称等价。

## 5. 恢复、事务与当前边界

BlackBase ExecutionCursor 保存有限执行树的位置、局部进度、祖先轮次与激活身份；
nsgablack 把它和条件观察放进原 Adapter 快照/checkpoint。
实际算法与池任务仍是 Router 的独立事务孩子；父级局部步骤快照不重复包含孩子 checkpoint。
已验证路径中，失败恢复本次游标、Unit、任务与池计划，真实求值和预算保留。
`adapt_weights=True` 的实际 StrategySpec/RoleSpec.weight 同时进入步骤快照与 checkpoint；
父 update 后指标异常也会恢复实际调度权重。fresh setup 恢复初始权重。

恢复核对计划指纹、策略拓扑、条件与指标身份，继续原请求和冻结输入，不重新抽精英。
预算轮转位置也被恢复。计划结构、叶额度与条件绑定的改变被现有指纹检查约束；
父 Router 另核对 MultiStrategyConfig、初始权重、enabled/n_units 和可识别回调声明，详见第 7.6 节。
运行检查与 Doctor 使用 search-plan-contract-invalid 检查可读声明和当前游标，不执行算法或创建 Unit。

纯控制切换可以保留现有 Adapter 状态而不增加逻辑代。
选精英、inject、替换成员等实际数据操作继续附着在已有选择/更新提交中。
**独立、无送评的任意 Pool 编辑阶段仍未开放**；idle 会拒绝池发布，不能借它偷交数据。
整个计划还受 Solver 的 max_steps、物理尝试上限、取消和 deadline 约束。

基础测试、池任务测试与安全测试分别位于 tests/test_search_plan.py、
tests/test_search_plan_pool_tasks.py、tests/test_search_plan_safety.py；正式 Project 恢复见
tests/test_search_plan_project.py。运行证据及命令见示例 PLAN_CN.md。

内部池包装通过直接声明 catalog_owner_type=PoolTaskAdapter 归属公开组件；
Doctor 验证它确为实际基类且已按对象身份注册，标记不自动继承，也不放过任意未注册子类。
该声明只说明发现与装配归属，不证明算法行为等价。

## 6. 首轮实现的验证记录

以下是首轮执行的历史证据，不覆盖第 7 节后来发现的交界场景，不能作为任意组合正确性的证明。

2026-10-21 执行的相关回归命令为：

```powershell
python -m pytest tests/test_search_plan.py tests/test_search_plan_pool_tasks.py tests/test_search_plan_safety.py tests/test_search_plan_catalog.py tests/test_multi_strategy_controller_adapter.py tests/test_strategy_task_contract.py tests/test_adapter_step_transactions.py tests/test_composite_working_pool.py tests/test_checkpoint_resume_plugin.py tests/test_pool_task_allocation.py tests/test_projection_subpools.py -q -k "not test_300_candidates_seed_30_independent_populations_of_100"
```

结果：197 passed、1 deselected。随后补充“不暗含全局精英种子”的用例，并重新运行四个
test_search_plan 测试文件，66 passed（与前一组重叠，不相加）。
独立 BlackBase 游标／事务组 60 passed；正式 Project 与原 default／elite 模式共 6 passed。
两种 Catalog profile 均能通过 catalog show adapter.search_plan 找到同一正式组件。
实际 plan 装配的严格 Doctor 为 0 error、0 warning，覆盖 19 completed、0 skipped。

最初未排除旧的三千成员用例，约七分钟后仍在运行，已停止该 pytest 进程并按上面命令重跑其余回归。
该用例没有完成，不算通过；本轮也不宣称完成该压力规模的性能验证。
测试提示主要来自有意使用固定变异器或未安装 ParetoArchivePlugin 的既有测试配置。

## 7. 反向审计后的边界补齐

2026-10-21。以下先记录原问题，再说明实现选择与验收。前一轮只读发现已转为代码修改，
不能再把首版通过的两轮示例当作全部交界场景的证明。新增验证见
`tests/test_schedule_activation.py`、`tests/test_router_policy_state.py`、
`tests/test_pool_task_result_identity.py`。

### 7.1 重入只重开局部编排，不重启算法

原问题：子 SearchPlan 完成一次后不重开；旧 Chain 直接上抛子 terminal；
旧 Router 只在整个提案为空时查询孩子结果，可能吞掉一支的取消。
先消费池种子的支路还可能没有收到零接纳处置，导致输入游标与叶状态分叉。

现在使用 `on_schedule_activation(control, activation_id)` 作为内部调度通知：

- 普通算法默认保留状态；Role 包装透明转发。
- 旧 Router、Composite 与 RoleRouter 沿稳定孩子路径转发通知，并在发现空分支取消时立即对账已提案的兄弟。
- 已完成的子 SearchPlan 在新父激活中只重建游标、局部观察与轮转位置。
  未完成的子计划即使进入新的父时间片，也保留旧执行 scope、冻结种子与请求身份继续执行。
- 子 PoolTask 的请求身份包含执行 scope，防止内层游标重新从第零轮开始时撞上旧请求。
- Chain 消费子组合正常完成后推进下一阶段；最后阶段正常完成才报告本组合完成。
  `repeat_last=False` 的有限配额现在确实结束 Chain，不再停在末阶段继续运行。
- 被父计划调用的 Chain 将阶段退休延后到所属组合最终 teardown；
  不尝试恢复已经关闭的 Provider/session。已经退休过孩子的独立 Chain 拒绝事后改作可重复子组合。
- Router 遇到取消或显式 stop，立即阻止兄弟继续送评，并按原 ranges/context 向已提案孩子发送零接纳。
  这仍走原 BatchDisposition，不引入第二份回滚列表或提交权威。

上述 scope、完成状态和停止结果随原步骤快照／checkpoint 保存。
通知本身不建立 Unit、不增加 Problem 调用或逻辑代。所有新 scope 变化发生在原步骤事务内。

验收覆盖：同一 GA Unit 两轮复用、子计划中途换父时间片仍续同一任务、第二次激活中途恢复、
重开后异常回滚、旧 Chain 的后继阶段实际工作、重复 Chain 不提前 teardown，
以及 VNS 消费种子后遭兄弟取消、保存恢复后继续同一个精确输入。

### 7.2 单个起点的提前结束仍明确拒绝

原问题：Plan 会把内层精修器 terminal 当成整批 PoolTask 完成，剩余种子留在 running 队列。

现在 PoolTask 自己解释内层结果。运行中的精修任务收到普通 terminal 会抛出
`pool task inner terminal before request completion is unsupported`，不越过剩余种子，
不发布假的最终结果，不制造空 committed 步骤；cancel 与明确 stop 仍原样传递。
内置 VNS 当前不以这种方式提前报告普通 terminal，原正式示例继续使用每起点额度。

这是明确限制，不是已实现“任意叶提前成功后自动处理下一起点”。
未来若支持，必须让当前起点结果发布与剩余队列推进进入合法数据提交；不能只把异常删除。
测试冻结两个种子，在首个基准更新后注入正常 terminal，验证整步失败并保留同一请求与未处理种子。

### 7.3 自适应权重属于 Router 运行状态

原问题：`_adapt_weights()` 修改实际 StrategySpec/RoleSpec.weight，快照只保存统计与 RNG。
父 update 后 metric 失败时，统计会回滚，实际调度权重却可能留在失败后的值。

现在初始声明与运行权重分开：

- 首次 setup／状态捕获或恢复时冻结配置；此前仍可完成装配调整。
- `policy_weights` 保存实际参与分配的可变 weight；步骤失败与 checkpoint 恢复均应用到原 spec 对象。
- fresh setup 恢复冻结的初始权重，不将上次运行结果误当成新初始值。
- `policy_identity` 核对 MultiStrategyConfig、初始权重、enabled、n_units 与所有者顺序。
  运行中的 weight 不进入配置身份，否则一次正常自适应就会破坏自己的恢复。

验收直接检查失败后的实际 weight、下一次额度分配及恢复后的候选轨迹；
覆盖 StrategySpec 与 RoleSpec，不只比较遗漏字段的 get_state。

### 7.4 最终结果交付绑定原发布身份

原问题：只验证名称存在与 published，删除后同名重建可能把其他候选当成本请求结果交付。

发布最终结果时记录只读收据：pool_id、名称、view_id、revision、祖先、kind、creator、
projection、slot 和有序精确 SolutionRef。读取时向唯一 Pool authority 核对这些值。
收据没有候选副本或独立可写成员集合。

同名重建、相同 view_id 但新 revision、成员／投影解释变化、跨 Pool 读取均拒绝；
数值相同也不能替代 token／版本。未提交视图不可读取。
保存恢复后仍保留这些限制；缺失/改变不当作空任务成功。

### 7.5 交付最终解不强制保留全部试探历史

现在 `output=None` 也发布各起点最终选择视图；getter 不再要求 output。
显式配置 output 时，继续保留累计接纳提案，兼容已有归档用途。
两者都不是自动垃圾回收声明：最终结果视图本身仍是保留根，其他 Unit 和消费者也可能持有引用。

只要最终视图未释放，idle retention 不会删除尚待消费结果。
消费后使用已有 `drop_subpool`／保留声明释放对应引用；不会自动删除其他消费者或嵌套后代的根。
没有添加独立 GC、自动移除旧轮结果或“已完成即可删除”的隐式规则。
因此存储成本仍随保留的结果视图、候选版本和证据增长，不承诺总存储恒定。
规模性能需要单独测量，不能用“视图不复制候选”代替。
回收验收已经覆盖：显式删除最终视图并释放种子持有后，经后续正常提交，无其他拥有者的最终候选精确读取失败；
消费者保留或 VNS Unit 仍使用的候选继续可读。原收据不能复活已释放视图。

### 7.6 恢复与行为变化

Router checkpoint 为 `nsgablack.strategy_router_state/v4`，步骤快照为
`nsgablack.strategy_router_step_transaction/v3`。缺失调度声明／运行权重的旧状态明确要求迁移。
已启动 PoolTask 若缺最终结果收据也明确拒绝，不按池名称猜回原身份。
SearchPlan 状态另保存父激活与执行 scope；Chain 新状态保存局部完成与重入信息。
Chain 恢复同时核对 repeat_last、各阶段额度与 advance_when 的声明，载荷中的 phase_steps 不能覆盖装配额度。

装配完成后不直接修改 cfg 字段；需要改变调度策略应重建装配或显式迁移。
回调身份检查兼容既有命名函数与 lambda，核对 Python 代码、默认参数和可证明为纯值的闭包参数。
活对象捕获只标明类型边界，不遍历 session、外部服务或任意 callback 对象图；纯函数和外部状态责任仍需组件遵守。
改变隐藏全局状态不能被解释为框架证明了恢复等价。

此前修复 Router 最低份额越界，也改变部分未越界配置的分配：
总额 64、权重 2:1，旧规则 43/21，新规则 42/22。
相同随机种子的旧实验可能因此产生不同轨迹，应记录配置与版本；不承诺逐步复现旧算法输出。

### 7.7 验收范围

源码入口：计划与 scope 在 `adapters/search_plan.py`，旧 Router/Chain 在各自 adapter.py，
任务与结果收据在 `adapters/pool_tasks.py`；统一求值和提交仍在原 ComposableSolver。
BlackBase 的纯游标和 Project L0 没有被复制为新的执行引擎。

新增测试针对实际边界：求值是否真的停止、同一 Unit 是否保留、下一次分配是否恢复、
结果是否仍为原视图、未消费结果是否可读。既有正式 Project 继续检查两轮 GA/VNS/GA 的真实交接与中途恢复。
独立无评估 Pool 编辑、任意自定义精修器提前成功，以及被外部任意 Python 副作用破坏的组件不在支持保证内。

## 8. 本次补齐后的验证记录

2026-10-21，在第 7 节实现补齐后重新执行：

```powershell
python -m pytest tests/test_schedule_activation.py tests/test_schedule_policy_identity.py tests/test_router_policy_state.py tests/test_pool_task_result_identity.py tests/test_search_plan.py tests/test_search_plan_safety.py tests/test_search_plan_pool_tasks.py tests/test_search_plan_catalog.py -q
```

151 passed。包括本次 86 项生命周期、恢复配置、实际权重、结果身份与回收验证，
以及现有 65 项计划／池任务／Catalog 回归。

```powershell
python -m pytest tests/test_multi_strategy_controller_adapter.py tests/test_strategy_task_contract.py tests/test_adapter_step_transactions.py tests/test_composite_working_pool.py tests/test_checkpoint_resume_plugin.py tests/test_pool_task_allocation.py tests/test_projection_subpools.py -q -k "not test_300_candidates_seed_30_independent_populations_of_100"
```

132 passed、1 deselected。三千成员压力用例仍未验证，不宣称完成规模性能验收。

```powershell
python -m pytest tests/test_adapter_config_construction.py tests/test_search_plan_project.py tests/test_assembled_ga_vns_elite.py -q -o addopts=
```

15 passed，其中正式 Project 与旧 default/elite 运行恢复占 6 项。
两轮计划继续得到 14 次提交、36 次求值，精修中途 checkpoint 恢复后只执行剩余工作。
配置测试改为通过 CandidateBatch 取数值投影，不再把带身份的 UnknownState 当数组下标读取。
池初始化测试将 phase_policy 放到 setup 前，遵守冻结声明契约。

另运行嵌套精修、复合种群权威、repair 与反馈四组：55 项通过，1 项仍匹配旧的
“no projection pool task with output” 文案。已同步该断言并单独重跑，1 项通过；
没有放宽“裸 VNS 不能冒充投影视图生产者”的检查。

实际 plan builder 的严格 Doctor 使用 --build、--catalog-audit 和 framework-core：
0 error、0 warning、10 info，19 个覆盖项 completed、0 skipped。
这些是所列配置与故障窗口的行为证据，不替代算法数学性质或任意组件副作用的证明。
