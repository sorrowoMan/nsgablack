# 用普通函数装配 GA、VNS、MOEA/D 与池档案

默认分组包含三个独立、可执行的标准 Case；另有独立的 partition 分组。Pipeline 先向母池生成未评估候选，Adapter 按需建立自己的 Unit；完整变化、Pool 选择和接纳后档案维护分别装配在各自明确的位置。修复、求值、候选身份、事务、checkpoint 和 L0 继续使用原框架。

- [ga_search](cases/ga_search/adapter/workflow.py)：一次父代配对共享一次随机掩码，返回两个独立后代；普通 `Pool -> Pool` 规则做环境选择。
- [vns_search](cases/vns_search/adapter/workflow.py)：当前点与 reference 池共同产生邻域，原 VNS 决定更新与邻域切换。
- [moead_search](cases/moead_search/adapter/workflow.py)：按方向自由安排交叉与扰动顺序，原 MOEA/D 维护权重、理想点与邻域替换。

三个 Case 都把 elite 维护绑定到**本批硬接纳之后**，每次真实叶更新执行一次。没有增加算法 Plugin、候选数据库或第二套运行循环。

## 单独运行位置分区

[ga_partition](cases/ga_partition/adapter/workflow.py) 使用相同标准脚手架和GA生存选择入口：

```python
selected, remaining = partition(pool, by=choose_twenty, rng=rng)
needed = count - len(selected)
members = selected.concat(remaining.take(range(needed)))
Pool(parent=members, name="elite").inject(members.take(range(len(selected))), replace=True)
Pool(parent=pool, name="reserve").inject(remaining.take(range(needed, len(remaining))), replace=True)
return members
```

普通choose可以只返回一个Pool，也可以一次交付主Pool与具名副Pool映射。partition对非空输入只调用一次规则，同时返回所选与有序位置补集；
它不改源、不建具名子池、不创建候选、不求值。本例明确使用raw目标和的精英规则，不冒充默认NSGA-II的Pareto留存。

```powershell
python run_project.py --group partition --check --build-check
python run_selection_outputs_and_report.py
python run_selection_outputs_and_report.py --report-only
```

默认种群100、后代80、3步。首次实际GA输入100得到20+80；后两次输入180得到20+160，
再从剩余取80维持100个成员。正式BudgetController限定260次求值，分区观察不额外求值。
本轮去掉该Case的maintenance绑定，elite从最终members取；reserve首轮为空仍创建，之后精确替换为80个未选位置。
主结果由Unit应用，副结果由既有池事务发布。独立结果写入 [SELECTED_OUTPUTS_RESULTS.md](SELECTED_OUTPUTS_RESULTS.md) 和
`results/selection_outputs_summary.json`；[PARTITION_RESULTS.md](PARTITION_RESULTS.md)保留前次基础分区历史，不覆盖默认三Case结果。

只读观察按提交后的精确引用重建相同确定性分区，核对真实GA已应用的位置、补集与源不变；
只保存引用和标量数据，不把Pool活对象留过作用域。小配置的正式Case测试见 `tests/test_pool_partition_project.py` 和 `tests/test_pool_selection_outputs_project.py`。

## 可选：serial → multi 的工作池继承

ga_partition 的 `CaseConfig` 现提供 `working_pool: str | None = None`。
设置为 `"workspace"` 时，已有 PipelineSource 用本次初始候选的准确引用创建普通区域；
外层 StrategyChainAdapter 绑定这个名字，内部 Router 不再重复指定，GA 的 PoolTaskSpec 省略 select 即继承。
默认 None 保持原装配。

```python
StrategyChainAdapter(
    name="workspace_workflow", working_pool="workspace",
    phases=[SerialPhaseSpec("search", router)],
)
```

Source/工作区建立、Unit 按需构建、运行与 L0 都走同一标准 Case。
工作池引用历史候选，不等于 GA 成员，也不自动替代 elite/reserve/ga_trials 的显式输出。
真实小配置运行与 checkpoint 见 `tests/test_composite_working_pool_project.py`：
30 个区域种子加 1 个根池外种子，实际只从区域取初始化输入，3 次提交、50 次求值；
工作区有 80 条引用，GA 保留 30 名成员。第 2 次提交的 checkpoint 恢复仅再执行 10 次求值。

## 正式运行

在本目录执行：

```powershell
python run_project.py --check --build-check
python run_and_report.py
python run_and_report.py --report-only
python -m nsgablack project doctor --path . --strict --build --catalog-audit --profile framework-core --format json
```

`run_project.py` 是标准 Project CLI；`run_and_report.py` 调用正式 `execute_project`，核对同次运行结果。`--report-only` 不运行算法。Project 串行执行三个独立 Case；每个 Case 使用独立池、运行身份和 Project L0 发放的 CPU 资源。它不是三者之间直接交接候选的融合示例。

## 母池先出现，Unit 按需建立

三个 Case 的问题 Pipeline 都只装配 UniformInitializer 与 ClipRepair，没有默认 Pipeline mutator。

[PipelineSource](pool_source.py) 在正式 `on_solver_init` 中调用公开 `solver.init_population(count, context)`：只生成并登记母池候选，不创建算法 Unit，不设虚假分数，也不求值。它把初始精确引用加入普通 `reference` 集合，再创建空 `elite` 集合。

Case 内 Router 用 `PoolTaskSpec(mode="initialize", count=...)` 冻结输入。VNS 从3个种子中取1个；GA与MOEA/D各从8个中取6个。未用种子仍留在母池，不把初始池大小当作算法容量。

额外读取的普通子池由 `change_sources` 声明。VNS/MOEA-D 的变化会读 reference，并明确开放母池；GA 变化只用被正式交付的父代，维护函数只额外读取 elite。

启动桥保存运行身份和完成标志。恢复不会重放初始化，也不会为观察/检查构造 Unit。

## GA：一对父代，两个孩子

[完整代码](cases/ga_search/adapter/workflow.py) 中的变化函数：

```python
def paired_change(request, *, rng):
    a, b = request.parents[:2]
    mask = rng.random(a.shape) < .5
    children = (np.where(mask, a, b), np.where(mask, b, a))
    return ChangeBatchResult(results=tuple(
        ChangeResult(child + rng.normal(0., .1, child.shape),
            source_refs=request.source_refs[:2],
            outputs=(PoolOutput("ga_trials", create=True),))
        for child in children[:min(2, request.max_outputs)]))
```

每次调用共享一次掩码，分别交付互补孩子。`request.max_outputs` 是本次剩余许可，不是池容量。每个孩子独立派生 token，经过正常 repair、预算和 BatchDisposition；不会继承父解分数，也不把二维数组猜成多个孩子。完整变化替换本叶的原变化配方，不再隐式叠加原交叉/变异。

普通 `choose_survivors(pool, *, count, rng)` 读取 `pool.objectives/violations`，复用 FastNonDominatedSort 的约束支配层，末层用拥挤度裁剪，返回 `pool.take(indices)`。实际装配用 `functools.partial` 固定 Case 的种群容量。

这里的 Pool 保留实际交付行的精确引用和位置。相同数值、同一引用在两个位置出现，都不等于槽位可以合并。选择反馈与 `raw_feedback()` 分开；本例没有用目标和替换 GA 的 Pareto 选择。

## VNS 与 MOEA/D：完整变化不变成新生命周期

VNS 的普通函数把当前点与 reference 候选组合，再按 sigma 生成邻域。原 VNS 仍负责起点求值、比较、当前点和邻域切换；一次变化函数交付一个候选，批次循环仍由叶 Adapter 管理。

MOEA/D 的普通函数读取默认父代与方向参数，偶数方向先交叉后扰动，奇数方向先扰动再交叉。方向子池、权重、邻域、理想点、槽位替换和最终方向竞争都保留。两个原始目标始终是两列；方向标量不写回 raw。

两个函数也声明 `PoolOutput`，让接纳提案进入各自 trials 普通集合。它记录被硬接纳的提案，不冒充算法最终选择成员。

## 本批反馈直接进入 elite

三个 Case 都使用相同形状的普通维护函数：

```python
def maintain_elite(request, *, rng):
    kept = request.pool.subpool("elite").merge(request.accepted).top(
        20, key=elite_key)
    return (request.pool.replace_members("elite", kept.refs),)

adapter.set_pool_maintenance(maintain_elite)
```

`elite_key` 明确按 raw 可行性、违反量、目标和做稳定排序。它是参考档案的规则，不改变 GA 的 Pareto 生存选择或 MOEA/D 的方向比较。

- `request.accepted` 只包含本批交给当前消费者、已硬接纳的精确版本，不等于最终成员。
- `request.pool.main()` 仍只枚举此前公开数据；不会因此看到其他任务的 pending。
- 维护每个真实叶更新一次，不随孩子重复调用；只合并旧elite与本批accepted，不重扫全部历史。
- 计划和提案输出、Pool manifest、Authority Snapshot 在原步骤中一起提交。失败恢复；零接纳不独立提交维护。
- 成员真的改变才推进 revision，view_id保持；移出集合只解除其保留关系，不删除其他使用者的候选。
- 同目标冲突以及 append/replace 同名冲突继续拒绝，因此 elite 和 trials 分开。

这解决了旧示例的“一步延迟”：最后一批反馈也能立即参加档案维护，无需等待下一次 change。

## 观察与证据

[WorkflowTrace](workflow_trace.py) 只观察已提交状态，不控制算法、不更新池、不额外调用 Problem。报告验证以下事实：

- 初始母池先存在、Unit仍未创建；逻辑提交连续，正式求值次数一致。
- 输入交接保留精确母池版本，派生新提案身份；额外来源能按精确版本读取。
- 原始目标与本例解析问题一致，候选满足边界。
- 每步 elite 恰好等于旧成员与本批accepted按显式规则选出的前20；view_id不变，revision仅随成员变化。
- GA两个孩子保留精确父代来源，输出token互不相同；MOEA/D发布6个方向视图，GA发布1个普通population视图。
- Project L0授权在实际Case内生效。

当前实跑见 [RESULTS.md](RESULTS.md)，原始观察在 `results/*.json`。这些观察文件不替代 Authority Snapshot、Artifact 收据或可传输 checkpoint，不作为算法优越性 benchmark。

## 恢复与版本

本次使用 `pool_workflow_pilot.source/v4`、`pool_workflow_pilot.trace/v3`，与旧的静态change维护语义明确区分。
Source 兼容未绑定工作池的 source/v3 状态；配置了 working_pool 时，恢复状态必须携带同一绑定，不能把旧的全局来源状态解释成区域来源。
其他旧版本需显式迁移，不把旧档案时序静默解释成新行为。

`tests/test_pool_workflow_pilot_resume.py` 会复制真实Project，三个Case各运行到第6步，从第3步正式checkpoint恢复。恢复时禁止重新初始化；已有引用原样保留，新提案正常派生身份，后续数值轨迹、raw反馈、Unit状态、档案与绑定身份一致。


## 双GA共享精英池

```powershell
python run_project.py --group parallel_archive
```

该独立分组复用 ga_search 标准 Case，两个独立 GA 每实例 6 个成员、4 个后代，运行 4 个逻辑步骤。
各 GA 不写共享档案；Router 的 pool_maintenance 只在本轮子更新返回后维护 elite 一次。
当前精英规则明确为原始约束优先、原始目标和排序，是示例规则而非默认Pareto选择。
初始母池仍由问题 Pipeline 生成，不因两个算法而复制存储。

成功运行 composite_archive_20261112_v2：36 次真实求值，两分支各 6 个最终成员，历史精英池 20 项。
摘要见 results/parallel_archive_summary.json；报告中的 members_by_owner 给出两实例精确成员。
原 final 字段仍报告第一个叶的结果，不能将它误认为两个算法的总种群。
本例是同一 Solver 内的逻辑并行，不开启两个独立 Case 或远端线程。
