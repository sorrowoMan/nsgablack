# GA一次选择交付成员、精英与剩余，精英参与下一代生成

运行Project的`partition`分组，默认3步，种群100、后代80。

`choose_survivors`是普通生存选择函数。规则只计算一次，主成员与副结果都来自同一offered Pool：

```python
selected, remaining = partition(pool, by=choose_twenty, rng=rng)
needed = count - len(selected)
members = selected.concat(remaining.take(range(needed)))
return members, {
    "elite": members.take(range(len(selected))),
    "reserve": remaining.take(range(needed, len(remaining))),
}
```

`choose_twenty`明确按raw可行性、违反量、目标和挑20个。初始输入100因此得到20+80；后两步父代100与新后代80一起交付，输入180得到20+160，再从剩余中取前80，使最终种群保持100。这个显式规则不宣称等价于默认NSGA-II Pareto环境选择。

partition本身不改源Pool、不更新Unit、不求值、不创建具名子池。它返回调用者坐标中的两个Pool。GA根据主结果的位置更新Unit，控制面把副结果保存到普通具名集合，二者属于同一步事务；缺失集合创建，已有集合精确替换。

本Case不再绑定pool_maintenance。elite明确来自最终100个members，而非“所有硬接纳提案”；reserve首轮为空也会创建，之后每轮精确保存80个未选位置。初始空elite由PipelineSource提供，因此同时演示已有集合替换与缺失reserve创建。副结果不增加求值，也不复制候选值。旧的只返回Pool写法继续有效，具名副结果仅适用于survivor目的。

`elite`现在是实际父代来源，而非只保存展示结果：

```python
ga = NSGA2Adapter(
    population_size=settings.population_size,
    offspring_size=settings.offspring_size,
    change=paired_change,
    parent_selector=MixedPoolParentSelector("elite", pool_fraction=1.0),
)
# PoolTask仍显式声明来源权限：change_sources=("elite",)。
```

初始化步骤先评估100个初始候选，再提交100个成员、其中20个elite和空reserve；此时不从空elite抽父代。
第二步起，每次变化从**上一提交**的elite有放回抽取两个精确引用，交叉并扰动后产生新身份的孩子。
读取父代不再求值父代，80个新孩子正常经过repair、求值和接纳，再由choose更新下一轮成员及副池。
本例使用`pool_fraction=1.0`使来源可直接核对，不宣称这比与普通种群父代混合更优；调整比例不改变装配形式。
默认预算仍是100+80+80=260，三个步骤分别得到members/elite/reserve为100/20/0、100/20/80、100/20/80。
父代允许重复抽取；主成员不能重复选择同一offered位置。elite是每轮精确替换的成员快照，不是累计历史档案。

`PartitionTrace` v2在提交后只读复核确定性分区：精确引用、所选与补集位置、实际生存成员、elite/reserve的精确成员与稳定池身份、输入值与引用不变，以及未新增Problem调用或预算预留。
新观察还按上一提交elite逐项核对每个后代的`change_source_refs/change_input_refs`和新token；报告只保存脱离的引用数据，不保存Pool活对象，不接管选择。
v1历史观察不能作为新副结果契约的checkpoint静默恢复；已生成的旧v2运行文件不会凭代码更新自动补出新父代证据。

正式执行：在Project目录运行`python run_selection_outputs_and_report.py`，只读复核已有结果加`--report-only`。本轮结果写入`SELECTED_OUTPUTS_RESULTS.md`和`results/selection_outputs_summary.json`；完整观察另存`results/ga_partition_selection_outputs.json`。默认三个Case的演示结果不覆盖；前次分区观察保存在`results/ga_partition_baseline.json`，原`PARTITION_RESULTS.md`保留历史记录。
