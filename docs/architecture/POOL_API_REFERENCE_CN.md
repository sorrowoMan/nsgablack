# Pool 与 Adapter 接口手册：当前方法与关键待补能力

最后按源码核对：2026-10-21。

本文直接列出“有什么方法、输入输出是什么、能表达什么”，并给出建议补充的具体接口形状。
**标为“当前”的名称存在于源码；标为“建议”的名称尚未实现，不可直接导入或调用。**

最新讨论已收敛为 [统一 Pool 数据结构与基础操作](POOL_DATA_MODEL_AND_OPERATIONS_CN.md)：
用户层以 Pool 表示解集合，选择规则接收并返回 Pool，all/筛选/合并结果继续使用同一接口。
当前已导出 Pool（复用 ChangeSelection），并接通 GA 的 Pool 生存选择、批量后代和本批成员维护。
GA survivor 还支持一次返回主 Pool 与命名副 Pool，精确替换或创建普通集合，见 11.4。
2026-10-21 增加 `chosen`、空草稿构造及 `inject`：下面的 0 节先给当前可用写法。
组合器现支持 `working_pool` 绑定与嵌套继承，见 0.5；池任务省略 select 时使用最近组合区域。
`partition` 也已实现：一次选择同时交回按输入位置对应的选中与未选中部分，详见 4.4。
统一 Store 门面、专用 Pareto 便捷函数等仍是后续设计，不因这个别名自动实现。

实现取舍另见 [最小完善方案](POOL_MINIMAL_EVOLUTION_PLAN_CN.md)。

## 0. 当前试作：选择一个 Pool，注入另一个 Pool

这组方法运行在**实际回调内**。不需要为精英分流再定义组件类，也不需要手写引用和成员计划。
下面保留已有算法的选择规则，只改变结果如何组织和交付：

```python
from nsgablack.adapters import Pool


def choose(pool, *, rng):
    members = pool.chosen(select_members, rng=rng)
    elite = Pool(parent=members, name="elite")
    elite.inject(members.chosen(select_elite, rng=rng), replace=True)
    return members


ga.set_selector(choose)
```

`select_members(Pool[, *, rng]) -> Pool` 必须选择算法要求的准确成员数；
`select_elite` 是用户定义的纯选择规则，例如返回输入的 `top(20, key=explicit_key)`。
框架不根据 elite 名字猜排序，也不把多目标自动相加。选择反馈来自本次算法请求，原始评估仍在 `raw_feedback()`。

### 0.1 三个接口与默认含义

```python
source.chosen(rule, *, rng=None)        # -> Pool，纯选择，不改变 source
Pool(parent=source_or_scope, name=None)  # -> 空的调用期草稿
target.inject(source, *, replace=False)  # -> target，先改草稿，提交后发布具名目标
```

- `chosen` 非空输入调用规则一次，空输入不调用、不消耗 RNG；始终校验普通同步函数签名。
  返回必须保留本次输入来源。规则可显式重采样，重复出现映回原坐标；最终 survivor 仍拒绝重复同一原位置。
  规则内部禁止 inject。它只选既有候选，不求值、不生成新提案。
- 构造总是空草稿，不读取同名旧成员，不单独创建持久集合；首次 inject 才登记计划。
  `name=None` 是临时工作集合；有 name 是精确公共目标名，同 scope 同名构造共享一份草稿。
- 默认追加保留旧成员的重数，新加入的精确版本只增加一次。
  例如旧 `[x,x,y]` 追加 `[x,z,z]` 得到 `[x,x,y,z]`。
  首次向**已有**具名目标追加，须有旧目标的读取授权；不能借可写名字扩大输入范围。
- `replace=True` 表示精确最终成员，包括顺序和重数；注入空 Pool 表示清空。
  它可以不读旧成员，适合 survivor 的精英分流。数值相等不替代身份相等。
- `snapshot = target.all()` 固定当前草稿，后续 inject 不改变 snapshot。
  同一反馈 root 的派生操作可保留临时分数；合并不同反馈框架后，不能自动读取 `.objectives`，应显式指定 raw 或统一比较规则。
- `parent` 仅提供调用作用域与局部来源。它不生成持久 parent/ancestors，不继承比较投影，不配置返回地址或执行顺序。

### 0.2 历史档案只收最终成员

```python
def maintain_archive(request, *, rng):
    if request.members is None:
        raise ValueError("this archive requires a population result")
    names = request.pool.describe()["subpools"]
    old = (request.pool.subpool("archive") if "archive" in names
           else request.members.take(()))
    combined = old.merge(request.members)
    best = combined.chosen(select_by_raw, rng=rng)
    Pool(parent=request.pool, name="archive").inject(best, replace=True)


ga.set_pool_maintenance(maintain_archive)
```

`select_by_raw` 必须明确使用统一规则，例如原始约束、目标或明确计算的 Pareto rank。
`request.members` 是算法最终选择，不等于本批所有接纳提案；轨迹算法没有种群时为 None。
任务内仍要在 `change_sources` 声明准确公共名 archive，包括目标尚未创建时。
维护函数使用具名 inject 后可返回 None；既没有自动计划也没有显式序列返回，仍会报错。

### 0.3 当前可用范围

具名 inject 首版接入 **GA survivor 与 pool_maintenance**，复用已有 PoolEdit 收集和 Authority/Pool 事务。
同一草稿连续操作合为一个最终计划；不同回调写同名目标仍校验冲突，不采用最后写者覆盖。
主成员非法、Unit 更新失败、目标漂移或后续发布失败，副池与 Unit 一起回滚；真实求值消耗保留。
本地草稿可读不等于其他 Adapter 已可读；公共成员仍在原事务提交后可见。

普通 change/propose 继续显式返回 `ChangeResult.edits`，使计划绑定实际接纳的提案。
本次同时修正该路径对 `create=True` 的预检；不将自动 inject 悄悄扩展到提案阶段。
没有装配期 `Pool(parent=...)` 句柄，没有直接 `vns(pool)` 执行语法；VNS 继续通过现有 PoolTask/Router 读取提交后的集合。
普通具名集合只持久化候选引用，不持久化本次选择分数；恢复不重跑 chosen 或 inject。
本次选择、维护和临时集合在回调结束后失效，不得保存活 Pool 供下一代读取。

真实代码见 `pool_workflow_pilot` 的 ga_partition、ga_search 的 members 档案模式，
以及 `assembled_ga_vns` 的 elite 模式；它们继续沿用标准 Project/Case 入口。

### 0.4 本次执行验证（2026-10-21）

相关测试合计 **269 项通过**，其中 266 项同组运行、3 个标准 Project 模块各在独立进程运行。
这次未宣称全仓库测试或完整历史缺陷全部修复。

- 新增 `test_pool_chosen_inject.py`：31 项，覆盖纯规则、重复出现、草稿快照、同名连续注入、追加授权、
  算法视图拒绝、跨回调冲突、零接纳、失败回滚与真实求值计数。chosen 与 partition 使用同一调用级纯选择护栏，
  不能通过另一个 scope 的草稿绕过 inject 禁令。
- 新增 `test_change_pool_creation.py`：13 项，覆盖 VNS/MOEA-D 标量和 GA 批量创建、空池、目标/来源授权、
  目标漂移、非前缀部分接纳、零接纳及 checkpoint。修复的是普通 change 预检错误，不改变提案接纳语义。
- 既有选择、成员维护、PoolEdit、父代、普通变化、Catalog/脚手架和 GA→VNS 回归同组执行，合计 266 项。
- 标准 Project 的三个独立测试：种群拆分实际 40 次评估；精英作为下一轮父代实际 50 次评估；
  最终成员档案与原 accepted 档案分别实际 14 次评估。均检查真实调用、预算结算和已发布成员。
  GA→VNS elite 小配置的实际精修与恢复包含在 266 项中，完整 elite 路径 7 次提交、20 次评估。
- `pool_workflow_pilot` 与 `assembled_ga_vns` 执行 strict Doctor，包含 `--build --catalog-audit --profile framework-core`，
  均为 0 error、0 warning；分别 29/10 info，全部覆盖项 completed。

核心验证命令（仓库根目录）：

```powershell
python -m pytest tests/test_pool_chosen_inject.py tests/test_change_pool_creation.py tests/test_pool_selection_outputs_integration.py tests/test_pool_final_members_maintenance.py tests/test_pool_survivor_selection.py tests/test_pool_partition.py tests/test_pool_partition_integration.py tests/test_pool_selection_outputs.py tests/test_pool_selection_methods.py tests/test_pool_edit_plans.py tests/test_pool_change_access_policy.py tests/test_pool_parent_selection.py tests/test_plain_change_contracts.py tests/test_operation_catalog_and_scaffold.py tests/test_assembled_ga_vns_elite.py -q -o addopts=
python -m pytest tests/test_pool_partition_project.py -q -o addopts=
python -m pytest tests/test_pool_selection_outputs_project.py -q -o addopts=
python -m pytest tests/test_pool_member_archive_project.py -q -o addopts=
python -m nsgablack project doctor --path examples/cases/pool_workflow_pilot --strict --build --catalog-audit --profile framework-core --format json
python -m nsgablack project doctor --path examples/cases/assembled_ga_vns --strict --build --catalog-audit --profile framework-core --format json
```

### 0.5 当前：multi / serial 的工作池与子流程默认来源

组合器绑定一个普通候选区域，子组合默认继承；显式绑定更近的区域时，以内层为准。
候选仍存于同一个 Solver `SolutionPool`，区域仅保存精确版本引用，不另建数据库、事务或运行循环。

```python
from nsgablack.adapters import (
    MultiStrategyConfig, NSGA2Adapter, PoolTaskSpec, RoleSpec,
    SerialPhaseSpec, StrategyChainAdapter, StrategyRouterAdapter,
)

ga = NSGA2Adapter(population_size=30, offspring_size=10)
group = StrategyRouterAdapter(
    roles=[RoleSpec("search", ga, pool_task=PoolTaskSpec(
        mode="initialize", shuffle=False))],
    config=MultiStrategyConfig(total_batch_size=30, adapt_weights=False),
)
flow = StrategyChainAdapter(
    [SerialPhaseSpec("search", group)], working_pool="workspace")
```

前提：准备阶段已经在这个 Solver 的池中创建并提交普通集合 workspace。
构造、setup、Doctor 都不会替用户创建集合或构建 Unit。名字使用精确公共名，不加 Router 命名空间。
工作池绑定可通过构造参数或运行前 `set_working_pool(name)` 设置；第一次提案尝试后不允许改成另一绑定。
脚手架的 `multi(...)`、`serial(...)`、`group(...)` 同样接受关键字 `working_pool`。
单孩子且显式绑定时仍保留组合器，避免优化解包丢失工作区域；未绑定时保持旧行为。

默认输入规则：

- `working_pool=None` 表示继承最近上层组合的绑定；没有绑定时维持 Solver 根池来源。
- `PoolTaskSpec(select=None)` 从当前工作区域中读取公开候选，在请求开始时冻结具体输入队列。
- 显式 select 保留原规则：字符串仍使用任务命名空间，具名回调仍返回准确引用，方向选择仍保留投影解释。
- 工作区域不会自动给裸 Adapter 添加 initialize/refine/compete 任务；输入使用方式仍由已有 PoolTaskSpec 声明。
- 直属普通 change 与维护函数中的 `request.pool.main()` 也指向本次工作区域，
  但任务仍须声明 `change_allow_main=True`；具名 donor 的 `change_sources` 和嵌套交集规则不变。

结果归属规则：

- 本批已硬接纳的候选按精确 accepted receipt 归入最近组合工作池，沿用原步骤提交点。
  外层 P、内层 Q 时自动归入 Q；P 不因包住 Q 就自动收到全部候选。继承同 P 时只登记一次。
- 输入精英池与工作池可以不同。读取精英作为 VNS 起点，不自动把全部邻域写回精英池。
- 工作池收录接纳候选，不等于算法最终成员，也不等于组合明确交付的最终结果。
  向上层、其他组合或外部结果池的交付继续使用已有输出和竞争规则。
- 同一步显式追加同一工作池可与自动追加合并；显式精确替换同名工作池与自动追加冲突，整步拒绝。
  本轮不引入覆盖优先级。精选应写 elite 等其他集合。
- 同轮普通读取只看已提交版本；并行角色不会互读尚未提交的候选，串行跨步骤继续依赖原阶段调度。

恢复与检查：绑定名字和本次轻量描述符进入已有 Adapter checkpoint/步骤快照。
repair、disposition、update 始终沿原提案的区域，后续全局 ctx 投影不能改变它。
同名集合被删除重建后不会静默改用新集合；正常成员提交的 revision 推进允许继续。
旧状态缺少绑定字段仅兼容未显式绑定配置；恢复先校验配置再恢复孩子，队列不重新抽样。
Doctor 检查声明名字形状，运行时检查目标存在、已发布且属于普通集合，检查不执行初始化。

标准演示是 `pool_workflow_pilot` 的 ga_partition 可选配置：
`working_pool="workspace"` 时 Source 用已有初始引用创建区域，外层 Chain 绑定，内部 Router 和 GA 任务继承。
默认配置仍为 None。真实隔离与恢复验证见 `test_composite_working_pool_project.py`：
30 个区域种子加 1 个根池外种子，3 次提交、50 次求值，区域保存 30 初始加 50 接纳引用，GA 仍为 30 个成员；
从第 2 次提交恢复时，只执行剩余 10 次求值，不重播种子或历史观察记录。

这次能力只处理组合区域。前面讨论的重复 100 轮、停滞触发、精修最终结果交付，
仍由原 ctx 条件与任务编排分别声明，工作池绑定不会偷偷加入这些行为。

### 0.6 工作池绑定的执行验证（2026-10-21）

本轮验证按以下分组执行，组间包含重复测试，不把数字相加当作独立用例总数：

- 工作池专项 `test_composite_working_pool.py`：29 项通过，包含最近区域继承、显式来源、
  硬接纳后入池、部分接纳、同名重建拒绝、运行前 setter、两种 Catalog profile、只读 Doctor、
  原提案 context 保护，以及池已暂存后下游失败的 Authority/区域/Adapter 回滚。
- 工作池与既有修复、接纳、步骤事务、Pool 维护和脚手架契约组：137 项通过。
  此组执行时专项仍为 25 项，后来补充的 4 项已包含在上述专项 29 项中。
- 池任务、子池、包装器、变化权限、PoolEdit 和懒加载 Unit 回归：98 项通过，6 条现有配置提示。
  其中两个旧测试原先直接改尚未创建的精英 Unit，现改为显式 ensure_unit 后准备测试档案；
  没有放宽运行时懒加载保护，也没有改变原断言。
- 较大的 300 个候选分配给 30 个、每个容量 100 的种群场景已单独通过，实际执行 3030 次求值；
  最后的小步回归排除该慢用例，没有重复运行。
- 标准 Project 工作区与既有恢复组：5 项通过。工作区隔离实跑为 30 个区域种子加 1 个区域外种子，
  3 次提交、50 次求值；第 2 次提交恢复后仅再求值 10 次。
- 对启用工作池的真实临时 Project 执行 strict Doctor，包含 build 与 framework-core Catalog audit：
  0 error、0 warning、29 info，40 个覆盖项 completed、0 skipped。

可复核的核心命令（仓库根目录）：

```powershell
python -m pytest tests/test_composite_working_pool.py -q -o addopts=
python -m pytest tests/test_composite_working_pool_project.py tests/test_pool_workflow_pilot_resume.py -q -o addopts=
python -m pytest tests/test_pool_task_allocation.py tests/test_subpool_tasks.py tests/test_pool_wrapper_contracts.py tests/test_pool_change_access_policy.py tests/test_pool_edit_orchestration.py tests/test_lazy_unit_elite.py tests/test_lazy_unit_activation.py -k "not test_300_candidates_seed_30_independent_populations_of_100" -q -o addopts=
python -m nsgablack project doctor --path <已启用working_pool的Project副本> --strict --build --catalog-audit --profile framework-core --format json
```

这轮验证覆盖工作区域的输入、提案、反馈、发布、回滚与恢复；不代表全仓库测试通过，
也不构成算法优越性或性能 benchmark。

## 1. 先分清三个调用位置

- `request.pool`：普通 change 函数中的 `ChangePool`，只读访问候选，并生成成员编辑计划。
- `selection`：`ChangeSelection`，表示本次调用内一组有顺序的精确候选引用，提供抽样、过滤和排序。
- `solver.solution_pool`：实际 `SolutionPool`，提供存储、子池成员和生命周期操作，由初始化代码或实际状态所有者受控使用。

另外，`subpools.all(adapter)` 是装配时声明“选这个 Adapter 创建的视图”的方法，返回选择计划。
它与 `selection.random(...)` 抽取候选是两种操作。

普通算法函数优先使用前两种对象。底层写入不能直接替代正式提案、修复、评估和提交。

## 2. 当前：先看一个完整普通函数

以下函数使用当前真实 API，可作为 VNS 或 MOEA/D 的完整 change。
前提是 `elite` 已存在且已提交；在池任务内还须声明相应来源权限。

```python
import numpy as np
from nsgablack.adapters import ChangeResult, PoolOutput


def elite_key(selection):
    objectives, violations = selection.raw_feedback()
    return np.column_stack((
        violations > 0,
        np.maximum(violations, 0),
        objectives.sum(axis=1),
    ))


def change(request, *, rng):
    pool = request.pool
    old_elite = pool.subpool("elite")
    evaluated = pool.main(stage="accepted")
    kept = old_elite.merge(evaluated).top(20, key=elite_key)

    child = request.candidate + rng.normal(0, 0.1, request.candidate.shape)
    return ChangeResult(
        child,
        outputs=(PoolOutput("trials", create=True),),
        edits=(pool.replace_members("elite", kept.refs),),
    )
```

这段代码表达：已有反馈选精英、生成一个孩子、接纳后把孩子加入 trials，并提交精英成员计划。
目标和是示例明确选择的档案规则，不是多目标默认优劣关系。
本轮 child 尚未评估，不参加这次精英排序。读取初始未评估种子也不会自动生成反馈。

## 3. 当前：从哪里取解

下面的方法都属于 `request.pool`：

```python
pool.main(*, region="main", stage=None, source=None)  # -> ChangeSelection
pool.subpool(name)                                   # -> ChangeSelection
pool.read(refs)                                      # -> ChangeSelection
pool.describe(name=None)                             # -> 只读元数据
pool.timestamp                                      # -> SolutionStamp
```

### 3.1 母池、具名集合与精确引用

```python
all_visible = request.pool.main()
evaluated = request.pool.main(stage="accepted")
seeds = request.pool.main(stage="initial")
elite = request.pool.subpool("elite")
parents = request.pool.read(request.source_refs)
```

- `main()` 默认不按 stage 筛选，因此可能同时包含种子与已评估版本。
- `source` 匹配记录的来源字符串，不等于按 Adapter 的 created_by 所有权路径筛选。
- `subpool(name)` 要求目标在调用开始时已提交且当前任务有权访问。
- `read(refs)` 只组织引用，不自动加载候选值，也不生成新身份。
- 返回后的读取仍受本次调用作用域限制，不能把 selection 留到下一步继续使用。

### 3.2 看清现在有什么

```python
inventory = request.pool.describe()
names = inventory["subpools"]
stamp = inventory["timestamp"]

info = request.pool.describe("elite")
count = info["members"]
identity = info["descriptor"]
kind = info["kind"]
creator = info["created_by"]
projection = info["projection"]
```

这是冻结的只读索引信息，不加载候选大值，也不构造 Unit。
当前 `main()` 没有 `since=` 参数；时间戳也不表示自动订阅后续新增解。

## 4. 当前：对一组解做什么

这些方法属于上一步返回的 `selection`：

```python
selection.refs                                  # -> tuple[SolutionRef, ...]
selection.values                                # -> 只读数值矩阵 (N, D)
selection.candidates                            # -> 语义候选 tuple
selection.raw_feedback()                        # -> (objectives, violations)
len(selection)                                  # -> 引用位置数量

selection.take(indices)                         # -> ChangeSelection
selection.random(n, *, rng)                     # -> ChangeSelection
selection.where(predicate)                     # -> ChangeSelection
selection.order_by(key, *, reverse=False)        # -> ChangeSelection
selection.top(n, *, key, reverse=False)          # -> ChangeSelection
selection.merge(*others)                        # -> ChangeSelection
selection.intersection(*others)                 # -> ChangeSelection
selection.difference(*others)                   # -> ChangeSelection
selection.groups(size)                          # -> tuple[ChangeSelection, ...]
```

### 4.1 抽样、指定位置和分组

```python
source = request.pool.subpool("reference")
sample = source.random(2, rng=rng)
reordered = sample.take([1, 0])
chunks = source.groups(100)
```

`random` 无放回抽取位置，n 大于可选位置数量会报错；n=0 允许。
引用本身重复时，不同位置仍可能指向同一候选版本。
`take` 使用当前选择内的局部位置，可以重排，也可以明确保留重复位置。
`groups(100)` 按当前顺序切组并保留尾组，只返回临时选择，不创建子池或种群 Unit。

### 4.2 过滤与明确排序

```python
def feasible(selection):
    _, violations = selection.raw_feedback()
    return violations <= 0


def first_objective(selection):
    objectives, _ = selection.raw_feedback()
    return objectives[:, 0]


source = request.pool.main(stage="accepted")
feasible_only = source.where(feasible)
ordered = feasible_only.order_by(first_objective)
best = feasible_only.top(20, key=first_objective)
largest = feasible_only.top(5, key=first_objective, reverse=True)
```

- predicate 接收整个 selection 一次，返回长度 N 的一维 bool mask。
- key 返回有限实数 `(N,)` 或 `(N, K)`；多列按词典序比较，列 0 优先。
- 默认小键在前；完整并列保持原顺序，降序也稳定。
- top 数量不足时返回现有全部，不补解；top(0) 不执行 key。
- 空选择可以传递给这些操作；直接读取空选择的 values/candidates/raw_feedback 会报错。
- raw_feedback 读取原始 Problem 结果，不自动应用 Bias 或 MOEA/D 方向投影，也不调用 evaluate。

### 4.3 集合操作

```python
a = request.pool.subpool("a")
b = request.pool.subpool("b")
combined = a.merge(b)
shared = a.intersection(b)
only_a = a.difference(b)
```

merge 按精确 SolutionRef 去重，保留首次出现顺序。
intersection/difference 保留左侧顺序与符合条件的重复位置。
相同数值不同身份、同 token 不同版本不会自动合并。
参与运算的选择必须来自同一次调用作用域。

### 4.4 当前：一次选择拆出两部分

```python
from nsgablack.adapters import partition


def choose_elite(pool):
    # 明确采用第一目标；不是默认 Pareto 规则。
    return pool.top(20, key=lambda p: p.objectives[:, 0])


def choose_survivors(pool):
    elite, others = partition(pool, by=choose_elite)
    return elite.concat(others.take(range(100 - len(elite))))


ga.set_selector(choose_survivors)  # 该例要求至少 100 个输入，survivor count=100。
```

`partition(pool, *, by, rng=None) -> tuple[Pool, Pool]` 不修改来源。
by 接收临时只读 Pool，返回从该参数派生的 Pool；不能返回旧 pool、重新 read 的同引用集合或索引数组。
非空时只调用一次；空输入交回两个空视图，不调用 by、不消耗 rng。
可用 `by(pool)` 或 `by(pool, *, rng)`，后者需要 RNG 时须显式传入 NumPy Generator。
参数/签名在调用前检查，规则内部异常直接传播，不重试。空输入可以省略不会使用的 required rng。

- selected 顺序遵守 by；remaining 保留当前输入的相对顺序。
- 按输入位置取补集，长度之和等于原输入；同引用的不同出现可以分在两边。
- by 重复选择同一局部位置会报错，不静默去重。
- 两边立即映回调用者原坐标，所以可继续 concat、嵌套 partition 或交给原 survivor 位置。
- 临时重编号不能把外层重复位置伪装成两个合法生存槽位。
- 有显式选择反馈时按输入顺序及重数传递；没有时保持缺失，raw_feedback 的含义不变。
- 不自动建立子池/Unit、求值或写成员；访问有效期仍属于外层调用。

例如输入 `[x, y, x]`，选第一个位置，remaining 为 `[y, x]`。
`source.difference(selected)` 则为 `[y]`，因为 difference 按精确引用移除全部匹配出现。
二者表达不同操作；remaining 也不意味着淘汰或删除候选。

## 5. 当前：普通函数怎样维护池成员

下面属于 `request.pool`，返回 `PoolEdit`，不会立即写池：

```python
pool.replace_members(name, refs, *, create=False)   # 精确替换，可显式创建缺失普通集合
pool.update_members(name, *, add=(), remove=())     # 增删组合
pool.remove_members(name, refs)                    # 移除指定引用
pool.trim_members(name, limit)                     # 保留当前顺序前 limit 项
```

```python
elite = request.pool.subpool("elite")
kept = elite.top(20, key=elite_key)
edit = request.pool.replace_members("elite", kept.refs)

return ChangeResult(child, edits=(edit,))
```

同一次调用的 add/remove/trim 都以冻结成员为基础。需要组合变更时，优先返回一次 update 或最终 replace；
不要把多个互相矛盾的中间替换计划交给提交端猜顺序。

- 只能编辑允许读取的普通 candidate_collection，不能改算法拥有的结果/投影视图。
- 默认要求目标已存在；create=True 显式冻结缺失前提，不立即写池，可创建空集合。任务仍须声明目标名。
- replace 保留调用者给出的顺序与重数；trim 不排序。
- update 保留旧成员重数，只对新追加项去重；remove 移除该引用的全部出现。
- 未知删除、add/remove 重叠、同目标冲突计划会报错。
- 计划冻结目标 view_id/revision；同名重建或版本漂移不能重定向写入。
- 当前只有携带计划的提案被接纳，计划才有机会随步骤提交；零接纳不发布。

## 6. 当前：普通 change 的输入和返回

### 6.1 ChangeRequest 的字段

```python
request.parents       # 非空只读二维数值矩阵；算法提供的默认父代
request.candidate     # parents 第一行，即默认锚点
request.source_refs   # 与默认父代对齐的精确引用；取决于实际消费者交付
request.parameters    # 算法参数，只读数据；VNS 与 MOEA/D 内容不同
request.context       # 本次调用的轻量标量上下文
request.unit_id       # 实际所有者交付的 Unit 身份，可为 None
request.pool          # 本次普通函数的池访问能力
```

函数签名是 `function(request, *, rng)`。随机数使用所属 Adapter 提供的 rng。
普通函数遵守无隐藏可变运行状态的约定；有状态组件使用已有显式绑定与 codec。

### 6.2 ChangeResult、PoolOutput 与 PoolEdit

当前公开导入：

```python
from nsgablack.adapters import ChangeRequest, ChangeResult, PoolOutput, PoolEdit

ChangeResult(candidate, *, source_refs=None, outputs=(), edits=())
PoolOutput(name, *, create=False)
PoolEdit(name, members, *, expected=descriptor)
```

- candidate：本次产生的一个候选，不继承父解分数。
- source_refs：显式补充的精确来源；不会抹掉框架提供的默认父代与实际读取依赖。
- outputs：同一个接纳候选要进入哪些普通集合。
- edits：对已有普通集合的成员计划。

`PoolOutput("trials", create=True)` 允许接纳后创建该集合；默认 create=False 要求目标已存在。
输出复用同一个已评估版本，不为每个目的池复制一份候选。
输出集合可能包含算法最终没有选中的试探解。
同名集合不能在同一步既 append 又 replace。

通常使用 `pool.replace_members(...)` 生成 PoolEdit，无需自己拼 descriptor。
普通 change 当前只返回一个候选；outputs 不是多后代返回接口。

## 7. 当前：实际 SolutionPool 的受控接口

本节 `pool = solver.solution_pool`，不是前面的 `request.pool`。
写入由初始化、实际所属 Adapter 或控制面在合法阶段执行。普通 change 使用返回计划的方式。

### 7.1 选引用、读取值与原始反馈

```python
pool.select(*, at=None, region="main", stage="accepted",
            source=None, limit=None, subpool=None)    # -> tuple[SolutionRef, ...]
pool.read(refs, *, allow_pending=False)              # -> CandidateBatch
pool.read_raw_feedback(refs, *, allow_pending=False)  # -> (F_raw, V_raw)
pool.read_provenance(refs, *, allow_pending=False)    # -> tuple[dict | None, ...]
```

与 ChangePool.main 不同，底层 select 默认 stage="accepted"。
limit 是按当前顺序截取，不表示最好或最新。
at 只限制候选写入时点，不能重建某个历史时刻的子池成员。
指定 subpool 后使用该集合成员，不再按 region 过滤。
read 保留给定顺序、重数和身份；空 refs 读取候选时报错。
allow_pending 是所属事务内部能力，不是跨任务访问许可。

### 7.2 创建、识别和维护普通子池

```python
pool.create_subpool(name, refs=(), *, metadata=None)  # -> name
pool.has_subpool(name)                               # -> bool
pool.published_subpool_names()                       # -> tuple[str, ...]
pool.subpool_refs(name, *, allow_pending=False)       # -> tuple[SolutionRef, ...]
pool.subpool_metadata(name)                          # -> dict
pool.subpool_descriptor(name)                        # -> dict

pool.replace_subpool_members(name, refs, *, expected=None)                 # -> tuple
pool.update_subpool_members(name, *, add=(), remove=(), expected=None)      # -> tuple
pool.remove_from_subpool(name, refs, *, expected=None)                     # -> tuple
pool.trim_subpool(name, limit, *, expected=None)                           # -> tuple
pool.add_to_subpool(name, refs)                                           # -> None
pool.drop_subpool(name)                                                   # -> None
```

受控所有者可以这样更新：

```python
pool = solver.solution_pool
expected = pool.subpool_descriptor("elite")
members = pool.update_subpool_members(
    "elite", add=added_refs, remove=removed_refs, expected=expected,
)
```

create_subpool 只创建引用集合；同名存在时报错。metadata 不能冒充算法投影或任意修改保留身份字段。
descriptor 只为已提交视图生成，包含 pool_id/name/view_id/revision/ancestors。
has_subpool=True 不保证该集合已经公开可读。
即使 subpool_refs(allow_pending=True)，也仍过滤未发布候选记录，不能据此读取任意当前 accepted。
实际成员变化保持 view_id 并推进 revision；空更新不折叠重复坐标。
移除成员或 drop_subpool 不删除其他使用者持有的候选，也不级联删除派生后代。

### 7.3 子池关系、创建者与时间

```python
pool.children_subpools(parent, *, recursive=False)  # -> tuple[str, ...]
pool.projection_subpools(created_by)                # -> tuple[str, ...]
pool.subpools_created_by(created_by)                # -> tuple[str, ...]
pool.timestamp                                     # -> SolutionStamp
pool.stamp_for(ref)                                 # -> SolutionStamp
```

parent 可以是当前名称或冻结 descriptor；父子关系按 view_id/ancestors 查，不按字符串前缀猜。
低层 created_by 要求稳定 Adapter 实例路径序列；传 Adapter 对象应使用下一节的高层选择计划。
SolutionStamp 是运行身份加逻辑序号，不是墙钟秒数。

### 7.4 候选入池、消费游标与保留

```python
solver.store_solutions(batch, *, stage="initial", region="main",
                       source=None, feedback=None, provenance=None)  # -> tuple[SolutionRef, ...]

pool.bind_input(refs)                                 # -> 输入 key
pool.input_remaining(key)                             # -> int
pool.take_input(key)                                  # -> SolutionRef，推进游标
pool.take_inputs(key, count)                          # -> tuple，推进游标
pool.settle_input(key, proposed_count, accepted_indices)  # -> None

pool.retain(owner, refs)                              # -> None
pool.release(owner)                                   # -> None
solver.set_solution_pool_retention(policy)             # -> None
```

store_solutions 是受控存储入口，不调用 evaluate，不自动把任意数组变成带合法提案身份的候选。
它补齐来源、代数和尝试信息，底层使用 `pool.put(...)`。普通变化函数不自行调用这条路径。

消费游标主要交给 PoolTask/Router 管理。take 会改变进度；settle 按最终接纳位置保留未接纳输入。
耗尽不会自动随机补解。
retain 替换该 owner 的完整保留根，不是追加；不要占用框架的 subpool/、adapter/ 名称空间。
解除持有不代表立即物理删除。保留策略在首次发布前配置，例如：

```python
from nsgablack.core.state.pool_retention import PoolRetentionPolicy

solver.set_solution_pool_retention(
    PoolRetentionPolicy(idle_steps=20, retained_publications=2),
)
```

idle_steps 按提交步数计算，不是秒数，也不负责算法淘汰规则。

## 8. 当前：Adapter 怎样选择池、使用方向视图

### 8.1 选择由某个实例创建的视图

```python
from nsgablack.adapters import subpools

all_directions = subpools.all(moead)
some_directions = subpools.random(20, moead)
```

这里 moead 是具体实例。返回的是 SubpoolSelection 计划，不是20个候选、候选矩阵或立即可遍历的视图列表。
请求开始时才解析该实例已发布的视图；权重、参考点和起点按任务规则冻结。
random 数量表示视图数量，来源不足时服从 PoolTaskSpec 的不足策略。
all/random 不提供阶段完成屏障，调度由 Router 明确指定。

### 8.2 PoolTaskSpec 的实际能力

```python
from nsgablack.adapters import PoolTaskSpec, RoleSpec

task = PoolTaskSpec(
    select=subpools.all(moead),
    mode="refine",
    count=1,
    steps=5,
    output="refined",
    on_insufficient="wait",
    shuffle=False,
    change_sources=("elite",),
    change_allow_main=False,
)
role = RoleSpec("local", vns, pool_task=task)
```

这是装配片段，moead/vns 须是所属 Adapter 树内的实例；角色仍需放入正式 Router。

- select=None：取母池；字符串：选具名集合；命名回调：返回明确引用；SubpoolSelection：按创建实例选视图。
- mode="initialize"：按输入建立算法起点/结构；mode="refine"：逐起点运行局部任务；mode="compete"：交回支持该模式的算法竞争。
- count 为数量或 "all"。select=subpools.all/random(...) 时，每个视图总取 count 个种子，再按 distribution 分给 worker；shared 明确重复同一批任务。
- select="普通集合" 走普通来源分配：partition 通常先取 count × workers 个，再分给各 worker；不能把两条路径的 count 混读成“每个 worker 每个方向各取一次”。
- steps 是每个精修任务的逻辑提交上限，包含起点正式评估所占步骤。
- distribution 可为 partition、independent、shared；视图任务只使用 partition/shared。
- on_insufficient 可为 error、wait、available，不需要另外发明空池处理机制。
- request_key 可用稳定命名回调区分同阶段的重复触发；运行中的请求不会被新选择静默覆盖。
- phases 限制任务启用阶段；output 收集接纳提案，不保证只包含最终最优解。

名称规则必须区分：select 字符串和 output 使用任务/Router 命名空间；
change_sources、PoolOutput 使用精确公开名称，不自动增加同一前缀。
内层来源声明不能扩大祖先任务权限。

当前 NSGA-II/III、SPEA2、MOEA/D 支持 initialize/compete；DE 当前只有 initialize。
只有声明精修/重启与相应投影能力的消费者才能 refine 投影视图。
Provider GradientOptimizer 不支持普通目标投影；A*/MOA* 的 new_root 不能当成通用局部精修。

完整真实装配可直接查看：

- [GA → VNS → GA 返回竞争](../../examples/cases/assembled_ga_vns/cases/hybrid_search/adapter/composition.py)。
- [MOEA/D → VNS → VNS 嵌套精修](../../examples/cases/assembled_moead_nested/cases/direction_refinement/adapter/composition.py)。

### 8.3 读取算法最终交付的引用

对这些明确支持结果交付的实例，可以在运行提交后读取：

```python
population_refs = ga.get_population_solution_refs(solver)
direction_member_refs = moead.get_population_solution_refs(solver)
refined_refs = vns.get_pool_refinement_results(solver)

if refined_refs:
    refined = solver.solution_pool.read(refined_refs)
    objectives, violations = solver.solution_pool.read_raw_feedback(refined_refs)
```

种群引用按实际成员/槽位顺序返回，精修结果由该算法明确交付。
不要把 trials/output 的所有接纳提案当成最终结果，也不要用 get_solution_pool_roots 的保留根顺序代替成员顺序。
不支持种群结果接口的 Adapter 可返回 None；这不是所有算法都拥有的种群抽象。

## 9. 当前：行为装配方法有哪些

```python
adapter.get_operation_contract()      # -> 四类行为中真实声明的角色和当前绑定
adapter.set_initializer(component)
adapter.set_parent_selector(component)
adapter.set_mutator(component)
adapter.set_selector(component)
adapter.set_repair(component)
adapter.set_change(function)
```

这些入口存在于共用行为装配层，但每个叶 Adapter 只允许自身实际声明的角色。
先读 get_operation_contract，再判断能装配什么；包装层不自动广播到全部子 Adapter。

- set_change 接受普通 `function(request, *, rng)`；VNS、MOEA/D 消费单个结果，NSGA-II/III、SPEA2 也支持批量完整变化，详见第 10 节。
- NSGA-II 的完整 change 与原交叉/变异配方互斥；未绑定时保留默认算法。
- set_selector 可接收普通 Pool→Pool 函数；已有对象组件仍消费带 purpose 的 SelectionRequest 并返回局部索引，详见第 11 节。
- parent_selector 选择父代，返回精确 SolutionRef；不能把它与生存选择的局部索引混用。
- set_repair 绑定 UnitRepair 的适用消费者，不代替问题 Pipeline 的 ProblemRepair。
- 完整 change 与直属 mutator、具名 Pipeline mutation 互斥。

已有组件可以直接装配，例如 NSGA-II 的跨池父代选择：

```python
from nsgablack.adapters import MixedPoolParentSelector

ga.set_parent_selector(MixedPoolParentSelector(
    pool_name="elite", pool_fraction=0.25,
))
```

这要求 elite 已存在并允许读取；它改变父代来源，不会自动改变 GA 的交叉/变异顺序。
自定义有状态组件仍须提供显式 checkpoint 身份与状态 codec。

## 10. 当前：一次普通变化交付多个后代

### 10.1 返回接口

`ChangeBatchResult(results=())` 从 `nsgablack.adapters` 导入，接收有序的逐后代声明：

```python
ChangeBatchResult(
    (
        ChangeResult(child1, source_refs=(a_ref, b_ref),
                     outputs=(PoolOutput("trials", create=True),)),
        ChangeResult(child2, source_refs=(a_ref, b_ref),
                     outputs=(PoolOutput("trials", create=True),)),
    )
)
```

- 每项 ChangeResult 保存独立候选、source_refs、outputs 和可选静态 edits，不自行构造 token。
- change_source_refs 记录逐孩子声明，change_input_refs 保留默认父代和实际读取的完整计算依赖。
- 批次本身不隐含共同接纳，也没有一个由“第一个孩子成功”触发的共享 edits。
- `ChangeBatchResult()` 是明确的空提案，不触发自动重试或维护发布。

同一次调用共享所属 Adapter 提供的 rng，只调用用户函数一次。
NSGA-II/III、SPEA2 可消费多个后代；request.max_outputs 是本次剩余后代许可。
超额返回明确拒绝，不静默丢弃。VNS/MOEA-D 的标量变化仍要求恰好一个候选，不能混入任意批量。

### 10.2 普通交叉函数

```python
def crossover_pair(request, *, rng):
    a, b = request.parents[:2]
    a_ref, b_ref = request.source_refs[:2]
    mask = rng.random(a.shape) < 0.5
    c1 = np.where(mask, a, b)
    c2 = np.where(mask, b, a)
    children = (ChangeResult(c1, source_refs=(a_ref, b_ref)),
                ChangeResult(c2, source_refs=(a_ref, b_ref)))
    return ChangeBatchResult(children[:request.max_outputs])


ga.set_change(crossover_pair)
```

GA 先经正式初始化评估建立精确成员，再调用完整变化函数；可配合已有 parent_selector 指定父代。
未绑定时保留原配方；绑定后不能再悄悄叠加原交叉/变异。
孩子默认独立接纳，继续用原始坐标经过预算、repair 和 BatchDisposition；允许只接纳其中一个。
原生数量受限的 Adapter 不必接受任意 N，超出契约应明确拒绝。

## 11. 当前：普通 Pool 选择与评估后成员维护

### 11.1 复用已有选择位置

最新收敛见 [统一 Pool 讨论第 13 节](POOL_DATA_MODEL_AND_OPERATIONS_CN.md)。
GA 的 set_selector 现在支持普通 `choose(pool) -> Pool`，也可显式接受 `rng` 关键字。
它在原生 survivor 位置运行一次，返回结果按原始局部坐标交给 PopulationUnit。
已有 `selector.select(request, *, rng)` 返回索引的组件继续支持。
普通函数仅在具备精确引用的真实 GA 路径可用，旧数组手工导入不猜身份。
Pool 是现有 ChangeSelection 的公开别名，all/take/filter/sample/sort/concat/merge 继续返回 Pool。
concat 保留顺序与重数，merge 按精确引用去重；不同原始位置上的同一引用仍可区分。
`.objectives/.violations/selection_feedback()` 为本次已有选择反馈，`.raw_feedback()` 为原始求值。

```python
def choose(pool):
    # 示例明确采用第一目标，仅用于演示精确位置；不是默认 Pareto 规则。
    return pool.sort(lambda p: p.objectives[:, 0]).take(range(100))

ga.set_selector(choose)  # 本例要求实际 survivor count=100。
```

批次维护也不能藏进任意 selector：VNS 基准可能不调用它，MOEA/D 槽位比较则可能调用多次。

NSGA-II/III、SPEA2、VNS、MOEA-D 额外支持明确的批次集合维护绑定：

```python
adapter.set_pool_maintenance(function)

def function(request, *, rng):
    ...
    return (edit1, edit2)  # tuple[PoolEdit, ...]；空 tuple 表示不修改
```

PoolMaintenanceRequest 交付：

- request.pool：本次维护的只读池访问能力，main 仍只枚举此前公开记录。
- request.accepted：本步交付给当前消费者的已接纳候选 Pool，可读取精确引用、候选、选择反馈与 raw feedback。
- request.members：本叶完成选择/替换后的有序最终种群 Pool；NSGA-II/III、SPEA2、MOEA/D 支持，VNS 为 None。
  保留准确版本、槽位重数与所属种群的选择反馈，不包含所有被接纳但淘汰的试探。MOEA/D 仍是多目标槽位集合。
- request.objectives/violations：本批已经计算的选择反馈，只读且按 accepted 对齐。
- request.parameters["subpool_projection"]：任务已有投影（如有），不把方向标量冒充 raw。
- request.context：调用内轻量上下文。

不增加可写 Solver/Unit 入口，不增加独立池循环。
每个实际所属 Adapter 更新批次调用一次，不按每个孩子或槽位重复维护。

### 11.2 使用本批新反馈维护精英

```python
def maintain_elite(request, *, rng):
    old = request.pool.subpool("elite")
    kept = old.merge(request.accepted).top(20, key=elite_key)
    return (request.pool.replace_members("elite", kept.refs),)


ga.set_pool_maintenance(maintain_elite)
```

这个示例要求 old 与 accepted 处在**同一次维护作用域**，可合并且可返回受控成员计划。
实现通过精确 accepted 引用授予同调用读取能力，贯穿读入、生成 PoolEdit 和提交校验；
不扩大普通 main 的可见范围，不允许读取其他任务的 pending 数据。

request.accepted 表示硬接纳，不等于算法最终保留。
维护全局试探档案可使用它；维护最终成员档案则应明确使用所属 Adapter 的结果输入。
例中的 elite_key 用 raw 排序；方向任务需要明确复用冻结比较规则，不能改写 raw。

维护“历代最终成员档案”时改用明确的 members 输入：

```python
def maintain_member_archive(request, *, rng):
    if request.members is None:
        raise ValueError("this archive requires a population result")
    names = request.pool.describe()["subpools"]
    old = request.pool.subpool("archive") if "archive" in names else request.members.take(())
    kept = old.merge(request.members).top(20, key=elite_key)
    return (request.pool.replace_members("archive", kept.refs, create=True),)


ga.set_pool_maintenance(maintain_member_archive)
```

本例 elite_key 显式读取 raw 并定义排序，不是自动 Pareto 档案。
同一维护 scope 交付历史集合和实际最终成员，包括已不在下一次 offered 中的历史解；
无需再跑一次 survivor，最后一个提交步骤也能归档。创建 archive 前，任务同样声明 change_sources=("archive",)。
accepted 与 members 的 .objectives/.violations 各自保持已有选择视图；跨 root merge 不自动拼投影分数。
未发布成员只准本叶本批 accepted，其余必须已公开；自有成员授权不会放开母池或兄弟 pending。
可运行配方另见脚手架的 maintain_member_archive；标准 ga_search 支持 config={"archive_source": "members"}。

### 11.3 执行与冲突规则

- 在正式求值、硬接纳之后，实际 Adapter.update 完成算法决策时执行；同一 Authority/Pool manifest 提交前统一应用。
- 返回计划复用现有成员操作和身份校验；同目标冲突、append/replace 冲突继续拒绝。
- 失败回滚算法更新、成员与发布游标，真实求值和预算消耗保留。
- 维护不另计 generation，不额外求值，不重复触发代钩子。
- 没有提案、预算为零、零接纳或整个搜索步骤不提交时，不单独提交维护。
- 独立于搜索步骤的池维护发布，本轮不提供。

### 11.4 当前：一次选择交付主成员与命名副结果

NSGA-II/III、SPEA2 的正式 survivor 位置现在也接受：

```python
from nsgablack.adapters import partition


def first_objective(pool):
    return pool.objectives[:, 0]


def select_members(pool):
    # 本例明确按第一目标取最多 100 个，不是默认 Pareto 规则。
    return pool.top(100, key=first_objective)


def choose(pool, *, rng):
    members, remaining = partition(pool, by=select_members, rng=rng)
    elite = members.top(20, key=first_objective)
    return members, {"elite": elite, "reserve": remaining}


ga.set_selector(choose)  # 与该例配套的 population_size=100。
```

它允许在一个普通函数内分组、重排、嵌套规则，再一次交付结果：

- members 仍交给实际 Adapter 更新 Unit，数量必须符合本次请求，主选择不能重复一个输入位置。
- 命名副结果交给普通集合，表示精确替换而非追加；目标不存在时创建，空结果也能创建空池。
- 副结果只要求来自同一 offered root/scope，可来自 members 或 remaining，并保留显式顺序与重数。
- 副结果不能是新生成的候选、重新 read 的同引用 Pool、其他调用的 Pool 或算法拥有的结果/投影视图。
- 原 `return members` 和对象 selector 的局部索引返回仍然可用。

框架不重新调用 choose，也不重新评估分数。选择 scope 结束前将副结果转成已有 PoolEdit，
与 Unit 更新、逐提案 PoolOutput 在原控制面统一验证和提交；目标身份/版本漂移或同目标冲突拒绝。
不存在目标使用 pool_id/name/absent 前提，目标中途出现不能让旧计划改写它。
函数返回后不能继续持有这些活 Pool 读取；正式集合和 Unit 随现有 checkpoint 保存与恢复。
任务下一次变化若要读取这些副池，仍须声明相应 change_sources；命名输出不会扩大输入权限或开放未提交读取。

这是已有 survivor 更新内的命名分流，不是任意时刻的池写入入口。
VNS candidate、SA proposal_order、MOEA/D replacement 等目的不接受这种副结果；
空提案/零接纳仍不单独提交，独立池维护和任意 Unit 写入仍未开放。
本批 accepted 档案可继续使用 11.2 的维护入口；从最终成员选精英则直接在这里计算，无需重做生存选择。

注意：副结果名称与 change_sources 使用精确公共名，PoolTaskSpec 的字符串 select/output 则加任务命名空间；
不能假定三处写同一个 elite 就自然连通。省略副结果保留旧集合，显式空 Pool 才清空；
当前精英快照也不等于历代最终成员累计档案。启动、命名与下一步实际消费的核查见
[数据模型第 18.4 节](POOL_DATA_MODEL_AND_OPERATIONS_CN.md#184-易用性核查局部选择已自然输出到下一步还需闭环)。

## 12. 哪些名字现在不应假定存在

- `pool.random(...)`：当前应在 selection 上调用 random；实际 SolutionPool 没有这个通用方法。
- `pool.evaluate(...)`：当前没有“读取池就自动求值”的接口，送评仍走控制面。
- `selection.beunit()`：当前不存在；分组不隐含结构构建，Unit 仍由所属 Adapter 按需创建。
- `selection.map(fn)`：当前不存在通用新候选批量生成语义；普通数组计算可在 change 内完成。
- `request.pool.main(since=...)`：当前不支持；底层时间与游标已有，尚无该便捷查询。
- `subpools.children(...)`：当前高层没有这个选择方法；低层已有 children_subpools。

当前已接通批量返回与提交前成员维护两个闭环。更多检索别名、增量索引、TTL、缓存和通用流程语言，
等具体场景或性能证据要求时再决定，不把它们当成上述基础用法的前置条件。
Pareto、档案、多样性、禁忌与指标是否已接入，以及必要的选择连接接口，另见第 14–16 节。

## 13. 阅读与验证范围

当前实现包含批量变化、精确 Pool 生存选择、本批成员维护与按输入位置拆分。
真实 Project、输出与验证见 [普通函数试作](POOL_WORKFLOW_PILOT_CN.md)及其 Project README。
第 14–16 节中明确标为建议的专用 Pareto 工具仍未实施。

此前批量变化与成员维护一轮的实际验证（分组有交集，不相加作为总数）：

- 批量/Pool选择/真实GA步骤/repair/硬接纳/事务/任务/正式恢复：153 passed，5 条已有配置提示。
- 父代授权/来源声明/三 Case 恢复/Catalog 与只读 Doctor 检查：105 passed。
- Unit 成员/共同修复/Provider COW/共享快照/并行：79 passed，5 条已有 MOEA/D 档案提示。
- 丰富反馈的单点、批量与 Provider 短路路径：12 passed。
- 三 Case 的 Project build-check、实际 run 与 report-only 成功；VNS/MOEA-D/GA 各 10 步，分别求值 28/33/42 次。
- 对该 Project 的 default 与 framework-core 严格 Doctor（build、catalog-audit）各为 0 error、0 warning、23 info，33 completed，无 skip。

2026-10-20 按位置拆分的验证分组如下，四组互不重复，共 173 项通过：

- `test_pool_partition.py`：30 项，含重复引用、局部重排/分组/嵌套、选择/raw 反馈隔离、RNG、空输入、作用域和精确 accepted 权限。
- `test_pool_partition_integration.py`：3 项，真实步骤内同 manifest 成员发布、非法重复槽位回滚/输入游标恢复，以及正式 checkpoint 续跑。
- `test_operation_catalog_and_scaffold.py` 与 `test_pool_partition_project.py`：26 项，两个 Catalog profile 可导入、脚手架同接口，实际标准 Case 30+10=40 次求值且预算归零。
- 既有 Pool 选择/GA 工作流与恢复/成员计划/访问权限/种群行为装配：114 项相关回归通过，9 条已有 MOEA/D 未配置档案提示。

这里单测和集成测试共 33 项，Catalog/脚手架/Project 测试 26 项，既有回归 114 项；
与上面历史分组有交集，不将两轮数字继续累加。100 个成员的完整运行见 Project 的分区运行记录。

新的标准 `ga_partition` Case 已经正式运行：3 步，求值预算和实际求值均为 260（100+80+80），
首次输入 100 拆为 20+80，后两次输入 180 各拆为 20+160；每步按示例规则保留 100 个成员。
拆分新增求值为 0，原候选与精确引用不变，Project L0 授权实际生效。
运行号为 `20261020T091247Z-09b7ca0a97`，见 [分区运行记录](../../examples/cases/pool_workflow_pilot/PARTITION_RESULTS.md)。
对现有四 Case Project 的 default/framework-core 严格 Doctor（build、catalog-audit）
均为 0 error、0 warning、29 info，40 completed，无 skip；这是 Project 规则覆盖，不是任意算法正确性的证明。

随后，一次选择交付命名副结果的本轮验证为四个互不重复的分组，共 154 项通过：

- `test_pool_selection_outputs.py`：22 项，三族 GA、最终成员内精英、reserve 分流、创建/精确替换、空池和返回边界。
- `test_pool_selection_outputs_integration.py`：8 项，repair/预算/非前缀接纳/Unit 扩展字段、冲突回滚与正式 checkpoint。
- Catalog/脚手架及两个小配置 Project：28 项，小配置实际 40 次求值、预算归零。
- 既有 survivor、partition、成员计划、GA 流程和种群装配：96 项。其间三个 checkpoint 测试遇到默认临时目录创建失败，改用工作区内独立 basetemp 后重跑通过；没有改测试断言绕过。

正式命名副结果运行号 `20261020T094239Z-4e167ad5e7`，3 步、预算与实际求值均为 260。
每次保留 100 个主成员及其中 20 个 elite，reserve 首轮为空、后两轮各 80 个；不绑定独立 maintenance。
副结果新增求值为 0，精确位置、空池创建、已有池身份、Unit 及 L0 绑定均核对通过。
见 [实际运行记录](../../examples/cases/pool_workflow_pilot/SELECTED_OUTPUTS_RESULTS.md)。
本次 default/framework-core 严格 Doctor（build、catalog-audit）也均为 0 error、0 warning、29 info，40 completed。
这些分组与前面历史验证有交集，不继续累加；正式运行和 report-only 单独记录，不算额外测试项。

继续接通精英消费与历史最终成员档案，本轮以下分组互不重复，共 **249 项通过**：

- `test_ga_pool_workflow.py`、`test_pool_edit_plans.py`、`test_pool_change_access_policy.py`、
  `test_pool_selection_outputs.py`、`test_pool_selection_outputs_integration.py`、`test_pool_survivor_selection.py`：79 项。
  首跑78项通过，唯一 checkpoint 用例因 basetemp 父目录不存在未执行；换用已有工作区父目录后单独重跑通过。
- Catalog/脚手架、操作契约检查、集合成员、成员编辑事务、父代选择、Unit组合、Bias硬接纳边界：149 项。
- `test_pool_final_members_maintenance.py`：15 项，历史输入与最终成员、故意淘汰更好accepted、repair/部分接纳/预算、
  创建空集合、目标漂移回滚、正式恢复、VNS None、MOEA/D重复槽位、受限权限与错误成员契约。
- `test_pool_selection_outputs_project.py` 与既有 `test_pool_partition_project.py`：各1项；分别独立进程通过。
  联跑曾暴露既有 workflow_trace 模块缓存串场，未把它当算法失败或改断言绕过；新标准Case测试显式隔离该共享模块。
- `test_assembled_ga_vns_elite.py`：3 项，默认模式兼容、精英输入精确冻结/实际消费/返回竞争、精修中途正式checkpoint。
- `test_pool_member_archive_project.py`：1 项，正式Case的 members/默认accepted 两模式各3步、14次真实求值，
  每步核对历史档案输入、报告与有效L0，搜索轨迹和最终Unit一致；非法archive_source在构建时拒绝。

79与149分组中的8条提示均是已有MOEA/D未装Pareto档案配置提示；未执行全仓测试或性能benchmark。
新成员/精英测试与此前154项有交集，249不与历史数字相加；精英Case代理额外重跑的8项事务回归也不重复计数。

正式精英繁殖运行 `20261020T151028Z-0bc1637e3c`：3步、260次求值，160个后代均核对来自上一提交elite且具有新身份，
读父代新增求值0，默认三个Case历史结果未覆盖，详见 [繁殖运行记录](../../examples/cases/pool_workflow_pilot/SELECTED_OUTPUTS_RESULTS.md)。
GA→精英20→VNS→GA 运行 `20261020T151220Z-1e7953d4ff`：43步、128次求值（48+40+40），
来源精确冻结、原始反馈未改、聚合40提案返回竞争，详见 [精修运行记录](../../examples/cases/assembled_ga_vns/ELITE_RESULTS.md)。
两例构建检查、正式运行与report-only通过；受影响Project严格build/catalog Doctor均0 error/0 warning：
pool_workflow_pilot为29 info、40 completed，assembled_ga_vns为10 info、19 completed，无skip。
GA/VNS Project两种Catalog profile均核对；公共Catalog导入与脚手架测试也覆盖default/framework-core。

这些是行为与恢复验证，不是算法优越性或性能 benchmark。

源码入口：

- [ChangePool / ChangeSelection / ChangeResult](../../adapters/change_pool.py)。
- [partition 按输入位置拆分](../../adapters/pool_partition.py)。
- [ChangeRequest 与普通函数桥接](../../adapters/change.py)。
- [成员计划与输出发布](../../adapters/change_outputs.py)。
- [SolutionPool](../../core/state/solution_pool.py)。
- [PoolTaskSpec](../../adapters/pool_tasks.py) 与 [subpools](../../adapters/subpools.py)。
- [Adapter 行为装配](../../adapters/operations.py) 与 [父代选择](../../adapters/parent_selection.py)。

源码契约、Catalog、脚手架与示例随本轮同步；仍不能把标明建议的名称当成现有实现。

## 14. 现有能力是否真的接入了 Pool

接入不要求每个数值函数都接收 Pool 对象。需要核对的是：输入来自哪里、计算后是否仍能找到同一候选版本、
谁决定成员、状态如何提交和恢复，以及下一段算法能否消费。
下面是源码静态结论，不是本次新运行的测试结果。

### 14.1 NSGA-II 的 Pareto 排序、拥挤度：经 Unit 与成员绑定接通

当前真实接口包括：

```python
from nsgablack.utils.performance.fast_non_dominated_sort import (
    FastNonDominatedSort, get_pareto_front_indices,
)

fronts, ranks = FastNonDominatedSort.sort(objectives, violations)
indices = get_pareto_front_indices(objectives, violations)
distances = FastNonDominatedSort.calculate_crowding_distance(objectives, front_indices)
```

这些计算返回数组或局部索引，这是合适的数学接口。
NSGA-II 根据选中位置更新 PopulationUnit，并同步对齐 population_pool_bindings，再发布精确成员视图。
所以“计算内部仍用数组”不意味着没有接 Pool。

但当前任意 ChangeSelection 上没有正式的 pareto_front/pareto_select 方法。
用户若想从某个具名池选前沿，要做第 15 节所示的引用保真桥接。

源码：[排序与拥挤度](../../utils/performance/fast_non_dominated_sort.py)、
[Unit 排名特征](../../units/population_features.py)、
[成员引用对齐](../../adapters/population_pool_refs.py)、[NSGA-II 选择](../../adapters/nsga2/adapter.py)。

### 14.2 ParetoArchive：已保留候选身份，尚未成为统一池来源

当前 ParetoArchivePlugin 保存分段 X/F/V、CandidateBatch、语义候选和 token，
按目标标签隔离比较，并输出 token 对齐的 PopulationSnapshot；EvolutionSolver 也有正式 Pareto Snapshot。
不能把它们说成仅保存裸数组、已经丢失全部身份。

当前缺口是：档案没有保存并发布对应的精确 SolutionRef 集合，因而不能直接作为普通 PoolTask 来源。
需要从档案挑解再搜索时，token 不能代替 pool_id/record_id/row/token 共同确定的版本。
不应通过候选值或目标值反向查找引用。

现有插件在 on_generation_committed 更新报告档案；
若把它改成可供搜索消费的池档案，必须明确成员所有者、精确引用、保留根与提交位置。
不能在原提交结束后补写同一 Pool manifest，造成档案与 Authority Snapshot 分叉。

源码：[ParetoArchivePlugin](../../plugins/runtime/pareto_archive.py)、
[EvolutionSolver](../../core/evolution_solver.py)、[身份测试源码](../../tests/test_pareto_archive_identity.py)。

### 14.3 EliteRetention：精确引用已接通，公开来源与选择规则尚不通用

EliteRetentionAdapter 从 accepted_solution_ref 保存精确引用，再次提案时按引用读取，并声明档案保留根。
它自己的 Unit、RNG 和档案参与恢复，因此已有实质池接入。

不过它维护的是私有精英档案，没有自动发布用户可按名称读取的 elite 集合；
当前排序采用违反量与目标和，也不等于 Pareto 档案。
需要完善的是可装配的成员选择与可选公开输出，不是重写候选存储。
旧精英 Plugin 入口已是兼容转发，不应重复计算为另一套独立算法。

源码：[EliteRetentionAdapter](../../adapters/elite_retention/adapter.py)、
[兼容入口](../../plugins/runtime/elite_retention.py)。

### 14.4 多样性与 Bias：Unit 内比较已接通，任意池比较需要明确来源

PopulationDiversityPreference 支持候选在某 Unit 中、Unit 整体、Unit 变化三类比较。
UnitPreferenceBias 当前只把 candidate-in-Unit 偏好桥接到 Bias 选择评分；整体与变化评分由 Adapter 策略显式消费。
它从所属 Adapter 获取只读 UnitView，并校验实例身份；不负责候选持有与成员替换。
这种经 Unit 的接入是合理的，不需要把多样性状态搬进 Pool。

旧 DiversityBias 仍使用声明的 population Snapshot，是受控旧入口，但不是“可任意指定子池”。
若需求是“候选相对 elite 池有多新颖”，需要补的是偏好的显式参考来源绑定：
接收精确引用及其只读值，并声明距离、归一化和如何按身份排除自己。
不能用共享 context 中恰好残留的一份 population 来猜参考对象。

源码：[显式 Unit 偏好](../../bias/preferences.py)、
[旧多样性偏好](../../bias/algorithmic/diversity.py)。

### 14.5 Tabu：私有接纳记忆已有事务保障，尚非共享禁忌池

TabuSearchBias 记录 token 和数值副本，在正式接纳后、提交前更新，状态随步骤回滚。
当前含义是“对历史已接纳提案附近的候选施加软惩罚”，不等于完整禁忌搜索或硬拒绝门。

如果只需要小型私有记忆，当前形式可以成立。
若要求多个算法共享一个具名禁忌集合，再接第 11 节的成员维护和显式只读参考来源。
禁忌对象是候选、移动还是属性，以及过期规则，仍由算法明确指定，不能由 Pool 名字自动决定。

源码：[TabuSearchBias](../../bias/algorithmic/tabu_search.py)、
[Bias 步骤状态](../../core/state/bias_state.py)。

### 14.6 HV、IGD、日志与结果：计算可接，外部交付保持独立协议

当前 hypervolume_2d 与 igd 是可复用的数组函数，selection.raw_feedback 已能提供输入。
缺少便捷桥接不等于指标不能使用池数据。HV 当前只支持二维。
调用者须明确可行性过滤、原始或任务比较视图，以及参考点/参考前沿。

日志和可视化可以选择记录 view descriptor、revision 与指标配置，用于追溯；
无需把整池复制进日志，也无需把日志变成候选权威。

SolverResult 已保留正式 token/求值/来源校验；大结果继续走 Artifact/DataRef。
其中 best_solution_ref 是外部 DataRef，不是运行内 SolutionRef，不能因为“统一接 Pool”就替换类型。
跨 Case、跨运行交付仍遵守现有结果与 Artifact 协议。

源码：[指标](../../utils/analysis/metrics.py)、
[SolverResult](../../core/solver_result.py)、
[benchmark 观察](../../plugins/ops/benchmark_harness.py)。

## 15. 当前就能写的 Pareto 与指标连接代码

下面是利用现有 API 编写的普通辅助函数，不是新增框架方法。
前提是输入候选已评估，并具有一致、可比较的目标与约束含义。
目标列数相同不自动证明目标含义相同。

### 15.1 约束支配第一层保留精确引用

```python
from nsgablack.utils.performance.fast_non_dominated_sort import get_pareto_front_indices


def constrained_front(selection):
    if not len(selection):
        return selection
    objectives, violations = selection.raw_feedback()
    indices = get_pareto_front_indices(objectives, violations)
    return selection.take(indices)


# 在普通 change 调用内：
source = request.pool.main(stage="accepted")
front = constrained_front(source)
refs = front.refs
```

现有排序按可行性优先并比较违反量；当全部不可行时，第一层可能是违反量最小的一组。
若只要可行前沿，应先用 where 明确过滤可行候选。
关键是 take(indices) 保留版本引用，不能用 pareto_filter 返回的目标数组倒推原候选。

### 15.2 计算指标无需重新评估

```python
from nsgablack.utils.analysis.metrics import hypervolume_2d


def raw_feasible_hv(selection, reference_point):
    if not len(selection):
        return 0.0
    objectives, violations = selection.raw_feedback()
    return hypervolume_2d(
        objectives[violations <= 0], reference_point=reference_point,
    )
```

这是原始反馈上、明确可行性过滤后的二维指标；不生成提案、不调用 Problem，也不修改成员。
比较多轮指标时应保持参考点和比较含义一致。
指标输入所属视图和版本可作为观察信息记录，不必建立另一份可写状态。

## 16. 建议补充的能力接口：连接已有功能

### 16.1 引用保真的 Pareto 选择（建议，尚未实现）

如果将第 15 节的桥接收敛成正式公共工具，建议优先提供以下两个明确用途：

```python
# 建议 API，当前不存在这些公共函数。
pareto_front(selection, *, feedback="raw", feasible_only=True)
# -> 第一非支配层的 ChangeSelection；默认先排除不可行候选。

pareto_select(selection, count, *, feedback="raw")
# -> 按约束支配层逐层取用，最后一层按拥挤度裁剪的 ChangeSelection。
```

二者含义不同：前沿只含第一层，其数量可能少于环境选择需要的 count；
环境选择在输入足够时继续从后续层补足 count，输入不足则返回实际可用数量，不生成新解。
按最新统一接口目标，这类选择的用户层输入输出均为 Pool；上面的 ChangeSelection 名称描述现有桥接基础，
不意味着未来继续要求用户区分两套解集合类型。
名称、导出位置和细节尚待实现时确定，不需要再增加第二套 Pareto 数学实现。
底层复用现有索引排序与拥挤度函数，桥接层只负责明确反馈含义和保持引用对齐。

普通 top 的多列 key 是词典序，不等于 Pareto 分层；
拥挤度可能包含边界无穷值，也不能直接绕过当前 top 的有限 key 校验。
正式工具应按已有拥挤度语义裁剪并明确并列规则，不偷偷改成目标和。
第一版可只支持 raw；其他比较视图须显式绑定且可比较，不能仅凭一个字符串自动猜测。

### 16.2 公开 Pareto 档案复用成员维护入口（建议，尚未实现）

```python
# 建议用法；依赖第 11 节和上述 Pareto 工具，当前不能直接运行。
def maintain_pareto(request, *, rng):
    old = request.pool.subpool("pareto")
    combined = old.merge(request.accepted)
    front = pareto_front(combined, feedback="raw", feasible_only=True)
    return (request.pool.replace_members("pareto", front.refs),)
```

这把已有前沿与本步接纳提案合并、筛选，再以引用集合交付下一段算法。
该普通集合须预先创建，权限和受限 accepted 校验仍服从第 11 节。
不再让私有 Plugin 档案与具名 Pool 档案同时声称拥有同一个可写成员事实。
如需迁移旧档案，应从生成时同步持有精确引用，不能事后按 token 或数值补造版本。

档案成员变化必须在原事务中发布，保留根保护引用，退出成员后交由现有保留策略回收。
随后由已有 PoolTaskSpec/Router 读取该集合、安排精修，并把返回候选交给原算法竞争。
这才是“Pareto 选择 → 档案 → 精修 → 算法采纳”的完整连接。

### 16.3 其他能力优先复用三种输入输出形状

- selection → selection：Pareto、精英、距离筛选等，返回原版本的精确引用选择。
- selection → 数值或只读特征：HV、IGD、距离、分布统计等，只读计算。
- selection → PoolEdit：维护档案成员，发布继续复用所属事务。

Bias 或选择策略如果还需要一个参考集合，应额外显式绑定只读来源；
比较规则继续归偏好或算法所有，Unit 结构继续归所属 Adapter。
不需要为每个指标增加 Pool 方法，也不需要把所有算法插件换一个名字变成池组件。

下一步接口验收应增加一个实际用例：从多个已声明来源选出 Pareto 前沿，
发布具名档案，交给 VNS 等精修，再由原种群算法按自己的规则采纳。
同时检查相同数值不同身份、不可行候选、原始/Bias 视图、目标含义变化、失败回滚和保留回收。

## 17. 最新收敛：统一 Pool 输入输出

此前把存储入口、具名子池与临时 Selection 分开，是当前实现事实。
新的用户层目标是让“选出的这一批解”仍然是 Pool，规则可以直接定义允许留下来的 Pool：

```python
# Pool→Pool 普通规则已实现；下面的 pareto_select 工具仍未实现。
def choose(pool: Pool) -> Pool:
    return pareto_select(pool, count=100)


survivors = choose(parents.concat(offspring))
```

统一 Pool 不复制存储；all/take/sample/filter/sort/合并返回引用视图。
指标仍返回数值，成员更新仍返回提交计划，分组返回多个 Pool。
选择作用于原始位置，不能通过同值匹配或全局去重丢失槽位关系。

具名快照、比较框架、作用域、创建/更新入口与基本方法的建议签名，统一见
[Pool 数据结构与基础操作](POOL_DATA_MODEL_AND_OPERATIONS_CN.md)。
旧示例保留当前可用 API，不把未来门面名称混入现有运行命令。

## 18. 选择之后的交付点：审查与后续状态

2026-10-20 继续核对当前实现后，必要缺口集中在已有阶段之间：

- 维护 request 已有本批选择 F/V，accepted Pool 尚未携带这份显式反馈，同一 choose 不能直接复用。
- 维护 request 有 accepted，没有实际所有者最终选定的成员输入；11.4 现可直接在选择内从 survivors 交付档案，无需独立维护 request。
- 普通 Pool→Pool 函数的 GA survivor 路径已经接上；VNS/SA/MOEA-D 的其他选择 purpose 尚缺 exact offered Pool，现有装配不应让不支持的输入形式到运行时才报错。
- 11.4 的命名副结果已能从 offered 旧 refs 或本批 accepted 创建集合，包括空集合；其他成员助手的创建与受控解除仍未完整开放。
- Unit 槽位相关变化需要实际父代位置映射；同一引用的两个出现不能仅靠 refs 区分。普通数值变化不必强制消费这部分信息。
- 无新提案时的纯成员提交没有独立入口；需要先明确进度、逻辑时间与发布规则，不能用假候选或额外求值触发。

source_refs 是因果声明，不自动选择或合并 UnknownState metadata；显式 with_values 已能表达语义基底。
共享档案由一个明确所有者归并，MOEA/D 返回范围也须显式解释，不应靠更多查询方法解决。

完整的 26 类场景、源码定位、最小完善顺序及待验证组合见
[Pool 数据结构第 17 节](POOL_DATA_MODEL_AND_OPERATIONS_CN.md#17-选择之后变化入池与-unit-更新能否自然接上)。
本节起于静态审查，随后已按 11.4 的实现更新相关状态；其余待补项不能因选择副结果落地而被视为完成。


## 从选择 Pool 读取 Unit 成员字段

NSGA-II/III、SPEA2 的生存选择已自动提供本实例 Unit 的 `member_fields`。
用户只写选择规则，不需要捕获 Adapter/Solver 或按 SolutionRef 建字典：

```python
from functools import partial
import numpy as np

def choose(pool, *, count):
    ages = pool.member_field("age", default=0)
    order = np.lexsort((np.arange(len(pool)), pool.objectives[:, 0], ages >= 2))
    return pool.take(order[:count])

ga.set_selector(choose)  # 框架提供本次实际 count，不再重复绑定容量
```

前提是 Unit 已声明并维护 age；此方法不创建 Unit，不定义年龄增长策略。
`default` 只用于本次新提案，不把拼错字段或缺少所有者伪装为零。
仅读取已有成员时可以省略 default；存在新提案却未指定时明确报错。
底层按本次 offered 位置绑定 Unit 槽位，同一候选重复出现也能拥有不同成员属性。
`take/all/concat`（同根）、`chosen`、`partition` 保留属性坐标；跨根 concat 不猜属性归属，读取报错。
返回数值 ndarray 或不可变数据 tuple，均脱离 Unit；数值 default 须匹配单成员形状。
属性只属于调用期选择视图，不写入候选原始记录，不增加 checkpoint 状态。
选择结束后保存的数据仍可使用，保留的活 Pool 不能再读取。
最终成员维护回调的 request.members 也提供该绑定；request.accepted、历史子池及任意 change Pool 不推断成员归属。
新增所有者接入时由其提供一次通用 member_rows（旧槽位下标或新提案 None），不按字段各写一套。


## 从最终成员分组、聚合、挑精英、入池

下面放在 Case 的 adapter 模块，用 `ga.set_pool_maintenance(maintain_elite)` 装配。
前提：该种群 Unit 已声明并维护 age；回调在成员更新之后执行，读取的是更新后的年龄。

```python
from nsgablack.adapters import Pool, partition

def maintain_elite(request, *, rng):
    members = request.members
    young, old = partition(members, by=lambda p: p.where(
        lambda q: q.member_field("age", default=0) < 2))
    young_elite = young.top(10, key=lambda p: p.objectives[:, 0])
    old_elite = old.top(10, key=lambda p: p.objectives[:, 0])
    elite = young_elite.concat(old_elite)
    Pool(parent=members, name="elite").inject(elite, replace=True)
```

这是“按第一目标分别保留两组精英”的具体算法规则，不冒充 Pareto 选择。
两组同源，合并后仍可读原来的成员属性和选择评分；不足十个时保留实际数量。
空结果也允许形成空精英集合。这里不需要返回 PoolEdit，具名 inject 已交付原事务。
入池不改变最终种群；下一阶段通过已有 PoolTaskSpec 读取提交后的 elite。
本回调不启动精修器，也不建立另一套运行循环。

若再合并历史档案，应先在各自来源完成依赖成员属性的选择，然后显式按 raw_feedback
或统一的自定义评分排序。历史候选没有“当前 Unit 成员年龄”，不能默认解释成 0。
同一引用占多个槽位时，concat 保留它们；merge 则按引用去重，不能用来保留全部槽位属性。

验证：test_pool_member_fields.py 包括真实 Solver 的最终成员分组与具名发布、
发布计划之后故障回滚（已求值预算不回滚）、文件 checkpoint 恢复并继续，
以及跨根合并的明确评分要求。不能将这些测试解释为任意多算法编排均已验证。

本轮验收：129 项相关测试首轮 128 通过，1 项旧错误文案匹配失败；保留原提示前缀后，失败项及 8 项成员字段测试共 9 项复验通过。标准 pool_workflow_pilot Case 装配/运行测试通过；Doctor/build 结果见 results/pool_maintenance_fields_doctor.json。


## 2026-11-12 连续操作核查：已修复与剩余缺口

### 本轮修复

1. 普通 `set_selector(choose)` 允许签名 `choose(pool, *, count[, rng])`，count 来自
   本次 SelectionRequest。初始化不足、预算裁剪和部分接纳不会要求用户同步修改另一处容量。
   未声明 count 的旧函数保持原调用；显式 partial(..., count=固定值) 保留旧固定数量语义，
   若与本次请求数量冲突仍报错，不偷偷覆盖用户配置。采用自动 count 的绑定身份为
   pool_selection/v2，旧函数及显式固定 partial 仍为 v1；旧 checkpoint 不自动改解释。
   chosen/partition 中的普通规则仍仅接收 Pool 与可选 rng，数量由外层选择函数传入。
2. member_field 整数默认值不能将 uint64 成员悄悄转成 float64。没有共同精确整数类型时拒绝；
   整数与浮点默认值混合也检查是否丢失整数精度。已有成员的原始 dtype 不因无关 default 而改变。
3. 字段与默认数据复用 Unit 的封闭数据 codec，支持嵌套数组、NumPy 标量及文本成员序列；
   不经过 feature digest，不复制 Adapter/Solver 对象图。最终成员可直接 member_field("age")。
4. 标准脚手架 adapter/operator_example.py 提供 choose_young_members 普通函数，
   可通过 selector=choose_young_members 绑定；仍需装配声明 age 的 UnitBinding。

### 仍需完善的内容，不等同于任意 Pool 已具备所有能力

- **父代槽位交接已补首轮实现。** NSGA-II/III、SPEA2 父代请求的 members 现可返回 Pool，
  完整 change 的 parent_pool 交付相应字段；见下节。旧引用列表遇到重复成员仍拒绝猜槽位。
  任意跨来源 Pool 拼接尚不自动成为父代槽位选择；直接 mutator 继续使用既有 UnitInputSpec，
  没有把完整 change 的新参数自动广播给每一种变异器。
- **跨所有者聚合应先确定比较语义。** 普通 Pool 可以合并值和引用；成员年龄、方向评分不属于
  全局候选属性。当前先在各自来源筛选，再用显式 raw key 统一排序即可；不存在自动通用投影。
- **Router 内的共同档案已补统一归并位置。** 在 Router 上绑定一次 pool_maintenance，
  在本批子更新完成后读取各自最终成员，再发布一次成员计划；详见下节。
  子写者与父写者冲突仍拒绝；独立 Case/异步远端结果和无送评纯成员提交不在此次范围。
- **接收“所有接纳提案”和“每个精修任务最终选择”应在教程中并列给出。** 运行接口已区分它们，
  但用户仍容易把 output 历史当作最优结果。不能靠统一命名掩盖实际不同含义。
- **成员字段读取成本尚未独立测量。** 每次调用冻结已声明字段，连续 take/chosen/partition
  共享冻结数据和位置映射。字段很多或很大时仍需测量，不宣称该扩展没有复制成本。

本轮验证专门增加部分接纳初始化后从 2 个成员补到 4 个的真实 Solver 运行、
最大 uint64 在排序/重复槽位中的精确性、嵌套数据只读及旧固定数量绑定兼容。
这些边界属于用户连续使用的必要条件；无需再增加更多同义池操作。

本次最终验证：125 passed，4 条既有 MOEA/D 未装档案提示；正式 modification_tasks Project 运行 modifications_pool_continuity_20261112 状态 ok。pool_workflow_pilot 严格 Doctor/build 为 0 errors、0 warnings、28 infos；Catalog default 与 framework-core 的 tool.pool 均读取成功。未跑全仓测试和性能比较。


## 父代选择 → 完整变化：同一 Pool 槽位贯穿

NSGA-II/III、SPEA2 的正式父代选择请求增加 `request.members`：有序 Pool，
包含本 Unit 的真实成员槽位、选择反馈和声明字段。与生命周期内其它 Pool 一样，调用结束失效。
父代选择器仍使用既有组件入口 select(request, *, pool, rng)，pool 参数保留旧的底层候选访问含义。

下面可直接放入标准 Case 的 adapter 模块。年龄由 pipeline/population_example.py 中的
AgePopulationUnit/AgePopulationBuilder 声明、更新；不在父代选择器里再维护年龄。

```python
import numpy as np

class YoungMemberParents:
    stateless = True

    def checkpoint_identity(self):
        return {"name": "young_member_parents", "age_limit": 2}

    def select(self, request, *, pool, rng):
        eligible = request.members.where(lambda p: p.member_field("age") < 2)
        if not len(eligible):
            eligible = request.members
        return eligible.sample(request.count, rng=rng, replace=True)


def age_scaled_change(request, *, rng):
    ages = request.parent_pool.member_field("age")
    center = request.parents.mean(axis=0)
    sigma = .05 / (1 + float(np.max(ages)))
    return center + rng.normal(0., sigma, center.shape)
```

在本 Case 的 build_solver.py 中装配（problem、pipeline 沿用本 Case 定义）：

```python
from nsgablack.adapters import NSGA2Adapter
from nsgablack.units import UnitBinding
from .pipeline.population_example import AgePopulationBuilder
from .adapter.operator_example import YoungMemberParents, age_scaled_change

adapter = NSGA2Adapter(
    population_size=100, offspring_size=100,
    unit_binding=UnitBinding(AgePopulationBuilder()),
    parent_selector=YoungMemberParents(), change=age_scaled_change,
)
# 在本 Case 原有 ComposableSolver(problem, adapter=adapter,
# representation_pipeline=pipeline) 处交付；保持原正式 run_solver 入口。
```

这只是明确的自定义 GA 规则：年轻优先选父代、父代均值加年龄相关扰动，不冒充经典 NSGA-II 默认变化。
没有外部父代时，parent_pool.member_field 不需要 default。读取的年龄与本次父代顺序一一对应；
两个槽位引用同一候选也不会合并。parent_member_indices 给出本次所属 Unit 的槽位下标，
属于提案时点的来源证据，不能拿它寻址未来成员。默认锦标赛也保留实际选中的下标。

### 外部父代与旧组件

旧组件仍可返回有序 SolutionRef。引用在本种群中唯一时绑定该槽位；不在本种群中时为外部父代，
其 parent_member_indices 项为 None。请求本身缺 members 的旧独立组件调用继续可用。
同一引用对应本种群多个槽位时，旧列表无法指定哪个槽位，因此在送评前报错，
请改用 request.members.take(...) 或 sample(...) 返回 Pool；不按数值或先出现者猜测。

MixedPoolParentSelector 的旧引用返回保持原接口：若本种群故意含重复引用且选中了该引用，
同样执行上述明确拒绝。任意跨根 concat 的结果目前不能直接当作有完整槽位证据的父代返回；
跨外部来源继续使用明确引用，并服从任务 change_sources/change_allow_main。

对外部父代读取成员属性须显式补值，例如
`request.parent_pool.member_field("age", default=0)`；这是变化规则为外部父代选择的临时解释，
不把年龄写到外部候选或历史子池中。parent_pool 没有跨来源统一的选择评分；需要统一比较时用
raw_feedback 或变化函数自己的显式规则。

完整 change 保留原 parents 数值矩阵、source_refs 与 request.pool 来源查询接口。
parent_pool 只增加精确父代的调用期读取，不创建额外候选，不创建 RuntimeParticipant，
不新增 checkpoint 状态或调度器。默认数值交叉/变异路径保留父代槽位来源，
但普通 mutate(candidate, context) 不会突然多收到 parent_pool 参数。

测试见 test_parent_member_handoff.py：覆盖三个种群 Adapter、同候选不同槽位属性、
默认锦标赛、外部父代显式默认值、部分接纳、失败回滚、作用域关闭及文件 checkpoint 恢复继续。

父代交接最终验收：首组相关回归 135 passed（4 条既有 MOEA/D 档案提示），脚手架与默认数值路径补充组 32 passed；最后补充父代下标一致性校验后专项 8 passed。各组有重叠，不相加。正式 modification_tasks Project 收据 modifications_parent_handoff_20261112 为 ok；pool_workflow_pilot 严格 Doctor/build 为 0 errors、0 warnings、28 infos，父代请求 Catalog default/framework-core 均读取成功。未运行全仓测试或性能 benchmark。


## Router 多分支共享档案：一个归并所有者

把 `set_pool_maintenance` 绑定在 StrategyRouterAdapter 上，即可在本批子更新完成后归并。
回调不会广播到孩子，不要求孩子分别维护同一档案。构造参数 `pool_maintenance=...` 等价。

```python
from nsgablack.adapters import Pool, StrategyRouterAdapter, RoleSpec, NSGA2Adapter
import numpy as np


def archive_key(pool):
    f, v = pool.raw_feedback()
    # 本例显式采用约束优先、再按第一目标；不是通用多目标Pareto规则。
    return np.column_stack((v > 0., np.maximum(v, 0.), f[:, 0]))


def maintain_shared(request, *, rng):
    names = request.pool.describe()["subpools"]
    old = request.pool.subpool("elite") if "elite" in names else request.members.take(())
    selected = old.merge(request.members).top(20, key=archive_key)
    Pool(parent=request.pool, name="elite").inject(selected, replace=True)

router = StrategyRouterAdapter(
    roles=[RoleSpec("first", NSGA2Adapter()), RoleSpec("second", NSGA2Adapter())],
    pool_maintenance=maintain_shared,
)
# 在本 Case 的 build_solver 中交给原 ComposableSolver；Problem/Pipeline 由本 Case 定义。
```

回调继续使用 PoolMaintenanceRequest：

- `accepted`：本 Router 实际收到的接纳候选，不等于任何子算法最终成员。
- `members_by_owner`：以正式 Adapter 实例所有权路径为键、各算法最终成员 Pool 为值的只读映射。
  每份视图保留该所有者的选择评分、真实槽位及 member_fields。可先逐算法按年龄等属性筛选。
- `members`：上述成员按稳定顺序聚合的引用 Pool，保留重复候选/槽位，不将异质种群拼成权威矩阵。
  不提供统一选择评分或成员属性；统一排序需明确 raw key 或自定义共同解释。
- `pool`：原调用期受控来源与写计划入口。已有档案、新接纳版本和合法自有成员可组合。
  成员读取授权不扩大其它具名池或母池的权限。

只收集本次收到非空接纳的直属子树；嵌套时展开其仍持有种群的叶所有者，
因此不保证这些子树内每个叶子本轮均执行过。无种群的轨迹算法不冒充种群，
不会出现在 members_by_owner 中；若要归档轨迹提案，显式使用 accepted。
需要等待跨轮任务完成时，仍由已有 Router/PoolTask 阶段规则指定，归并回调本身不构成阶段屏障。

### 提交与恢复

每次实际非空 Router.update 最多调用一次，所有子更新已返回；零接纳、等待及取消不单独运行维护。
计划加入原 collecting_pool_edits，与子算法状态、Pool manifest 和 Authority Snapshot 一起提交。
任意子更新或归并失败，全步回滚；已发生的求值和预算消耗保留。
子算法若另写同一档案并给出不同计划，继续按原规则报冲突，不由父回调覆盖它。

归并组件身份/codec 保存到 Router 原 checkpoint 与步骤快照；新字段仅在实际绑定时出现，
旧无绑定 Router 的状态格式保持可读。更换回调后恢复旧绑定会在恢复子算法前明确拒绝。
所有 Pool 只在回调内可读，checkpoint 不保存活 Pool；RNG 沿用 Router 的既有可恢复 RNG。
这支持一个 Solver 里的逻辑并行分支，不是跨独立 Case 或多机异步提交的合并事务。

### 可运行 Project

`examples/cases/pool_workflow_pilot` 新增独立 parallel_archive 分组，复用 ga_search 标准 Case。
两个 GA 分别持有 6 个成员、每轮各提出 4 个后代，父 Router 维护一个历代精英池。

```powershell
python examples/cases/pool_workflow_pilot/run_project.py --group parallel_archive
```

正式运行 composite_archive_20261112_v2：4 个逻辑提交、36 次真实求值，最后两个分支各 6 个成员，
精英池保留 20 个精确候选版本。对照报告见该 Project 的 results/parallel_archive_summary.json。
最初一次运行因旧 builder 未消费 config override 失败，修正为正式构建前消费 config 后成功；失败收据保留。
用户层的维护函数在 [Case adapter/workflow.py](../../examples/cases/pool_workflow_pilot/cases/ga_search/adapter/workflow.py)，
参数与装配仍在同 Case 内闭合，L0 grant 由 Project 提供。

共享档案本轮验收：64 项 Router/策略状态与原维护回归通过；补充组 34 项（含 11 个新归并场景）通过；绑定/步骤事务/父代交接组 82 项通过。最后将所有权路径查询改为单次树遍历，并去掉调用期维护数据无用途的 feature digest，专项及原最终成员维护共 26 项复验通过。各组有重叠，不累计。严格 Project Doctor/build 为 0 errors、0 warnings、28 infos；parallel_archive 的正式 build-check 和 Catalog default/framework-core 均成功。未运行全仓测试或性能 benchmark。
