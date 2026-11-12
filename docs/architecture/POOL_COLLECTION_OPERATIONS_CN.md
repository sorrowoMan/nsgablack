# Pool 集合操作：选解、分组与成员维护

最后按代码核对：2026-10-21。实现为 `adapters/change_pool.py`、
`adapters/change_outputs.py` 与 `core/state/solution_pool.py`。
本轮补齐“从哪些集合挑解”和“怎样维护这些集合”，继续复用现有身份、事务与存储。
当前另有调用期 `source.chosen(rule)`、`Pool(parent=..., name=...)` 与 `target.inject(source, replace=True)`
简写，先见 [接口手册第 0 节](POOL_API_REFERENCE_CN.md#0-当前试作选择一个-pool注入另一个-pool)。
具名简写仅接入 survivor 与成员维护；下面的显式 PoolEdit 路径仍用于按提案接纳绑定的普通 change。

## 1. 三类动作的边界

- **查询**返回只读的精确引用选择，不生成候选、持久子池或 Unit。
- **成员维护**改变普通子池的成员关系，保留池身份；不会删除候选值。
- **候选变化**继续由普通 change 函数产生新提案，经过正式修复、评估和接纳。

本轮没有引入含糊的 `map`。筛选既有版本与生成新候选具有不同身份语义。
也没有把查询方法变成算法运行循环；操作顺序、调用条件和比较规则由算法配方决定。

## 2. 只读选择

从 `request.pool.main(...)`、`subpool(name)`、`read(refs)` 获得选择。
已有 `refs/values/candidates/raw_feedback/take/random/merge` 继续有效，新接口为：

- `where(predicate)`：`predicate(selection)` 返回长度 N 的一维 bool mask。
- `order_by(key, *, reverse=False)`：`key(selection)` 返回有限实数 `(N,)` 或 `(N,K)`。
  多列按词典序比较，列 0 优先；完整并列保留原顺序，降序同样稳定。
- `top(n, *, key=..., reverse=False)`：必须显式给出比较规则，默认取最小键；数量不足取现有全部。
- `intersection(*others)`、`difference(*others)`：按精确 SolutionRef 比较，保留左侧顺序与重数。
- `groups(size)`：按连续顺序划分临时选择，保留不足 size 的尾组，不创建持久子池或 Unit。

`where/order_by` 不隐含求值。回调可读取已存在的原始反馈或候选数据，不能把读取当成新评估。
空集合不执行回调；`top(0, key=...)` 也不执行比较函数。非法 mask、数量或 NaN/inf 排序键明确报错。
所有集合必须来自同一调用作用域，函数返回后访问失效；任务来源限制同样适用。

例如用原始反馈明确指定可行性优先、违反量其次、原始目标和再次：

```python
import numpy as np


def raw_elite_key(selection):
    objectives, violations = selection.raw_feedback()
    return np.column_stack((violations > 0,
                            np.maximum(violations, 0),
                            objectives.sum(axis=1)))


# 在普通 change 内：
source = request.pool.main(stage="accepted")
kept = source.top(20, key=raw_elite_key)
groups = kept.groups(5)
```

目标和是此例的显式档案规则，不是多目标默认排序，也不替代 MOEA/D 方向比较。
需要 Pareto 排名时，先计算 rank 等显式键；需要方向标量等准则时，提供对应键。
相同数值不同身份、同 token 的不同版本不会自动合并。
`merge` 按精确引用去重；种群槽位与方向任务需要的重数不应通过全局集合合并来表达。

## 3. 普通函数返回成员变更计划

只读访问不会直接写共享池。通过以下方法创建 `PoolEdit` 数据计划：

- `request.pool.replace_members(name, refs, create=False)`：精确替换为这些成员，保留明确提供的顺序与重数。
  create 是关键字参数；显式 create=True 时，可冻结缺失前提并在提交时创建普通集合，也可创建空集合。
- `update_members(name, add=(), remove=())`：移除指定成员，再追加新成员。
- `remove_members(name, refs)`：只解除指定成员关系。
- `trim_members(name, limit)`：按已有顺序保留前 limit 个，不隐含优劣排序。

已有目标必须是已提交且声明允许访问的普通 `candidate_collection`。
计划冻结 pool/name/view_id/revision/ancestors；缺失目标则冻结 pool_id/name/absent，提交前出现同名目标即拒绝。
创建不扩大读取范围，受限任务必须声明目标公共名；成员引用也必须属于本次允许读取的范围。
算法发布的 population 结果视图、MOEA/D 投影视图仍由原所有者维护。

```python
from nsgablack.adapters import ChangeResult, PoolOutput


def change(request, *, rng):
    old = request.pool.subpool("elite")
    accepted = request.pool.main(stage="accepted")
    kept = old.merge(accepted).top(20, key=raw_elite_key)
    edit = request.pool.replace_members("elite", kept.refs)
    child = request.candidate + rng.normal(0, .1, request.candidate.shape)
    return ChangeResult(child,
        outputs=(PoolOutput("trials", create=True),), edits=(edit,))
```

这里用**调用前已发布反馈**维护下一轮的精英集合。本轮 child 尚未求值，不参加这次排序。
当前批次送评、接纳后，计划与 `trials` 输出一起进入现有步骤事务。
至少一条携带该计划的提案被接纳才执行计划；全部拒绝不改变集合。
若需要按本步新反馈立即选优，所属 Adapter 可在正式 update 内使用下面的成员 API；
本轮没有把读取未来反馈的能力塞进 change，也没有新增一套评估回调引擎。

同批相同计划只执行一次；同目标不同计划明确冲突。
同一步对同一池同时 append 输出与 replace 编辑也拒绝，避免顺序造成覆盖。
指令绑定本次提案 token，派生交接不重放祖先编辑。
目标同名重建、revision 改变或引用不可用时失败并回滚，不静默追读最新版本。

## 4. 数据层成员 API

在初始化或算法所属步骤事务中，可直接使用：

```python
expected = pool.subpool_descriptor("elite")
pool.update_subpool_members("elite", add=added_refs, remove=removed_refs,
                            expected=expected)
```

其他操作是 `replace_subpool_members(name, refs, expected=...)`、
`remove_from_subpool(name, refs, expected=...)` 与 `trim_subpool(name, limit, expected=...)`。
同一步需要组合增删时使用一次 update；写入暂存后不重新向公共读取面索取描述符。

方法均返回最终有序引用 tuple。只有实际成员顺序/内容改变才推进 revision；view_id 保持不变。
引用全体先校验再写。当前步骤内只有已接纳候选可作为私有新增成员，未评草稿不可混入。
`expected` 对直接受控所有者可省略，普通 change 计划始终使用冻结描述符。
移除不存在的成员、add/remove 重叠、非法引用、准备发布后写入都会明确失败。

修改期间集合不可对外读取，只有随 Pool manifest 和 Authority Snapshot 成功提交后才可读。
成员关系、引用保护和 revision 复用既有步骤回滚/checkpoint；没有第二份候选值或独立事务。
关闭集合或移除成员不删除候选，物理回收仍由其他引用、历史 pin 和现有保留策略决定。

既有 `create_subpool` 与精确 replace 保留重复引用供方向任务坐标使用。
update 保留已有重数，只对新增项去重；移除一个引用会移除它在本集合中的所有出现。
trim 原样保留前缀，空更新不会折叠坐标。需要修改某个重复位置时，显式构造所需顺序再 replace；
任务冻结队列仍由任务所有者维护。

## 5. 观察与成本

`request.pool.describe()` 返回池身份、冻结时点与当前允许访问的子池名。
`describe(name)` 返回冻结 descriptor、成员数量、kind、created_by 和 projection。
这些是脱离的只读索引信息，不读候选大值，不创建 Unit，不改变池。

选择与集合运算先处理引用；候选和原始反馈按实际读取加载。
比较函数实际读取的候选或原始反馈会记录输入依赖；只按引用组织不加载值。
全历史排序的成本随历史增长。
实际装配可用具名来源集合限制比较范围，本例只验证小规模运行，不声称大池性能。

本轮未新增加权抽样、通用新提案批量生成、成员 TTL 或新的物理回收策略。
这些扩展应继续沿明确来源、精确版本和所属事务收敛。

## 6. 运行与验证

标准例子见 [pool_workflow_pilot](../../examples/cases/pool_workflow_pilot/README.md)。
其精英池采用上述一轮边界，验证 view_id 稳定、revision 只在成员变化时推进、原始反馈不改写。

2026-10-20 按最终实现验证：

- 28 个测试模块：**437 passed**，280.24 秒。覆盖集合查询、重复坐标、成员计划、
  预算/部分接纳/零接纳、权限与身份漂移、步骤回滚、嵌套投影、池保留、正式 Case 恢复、
  算子装配、repair、评估接纳/shape/原始反馈及 SnapshotStore。
- 其中成员编辑端到端模块含 13 项；两个真实 Case 均从第 3 次提交 checkpoint 继续到第 6 步。
  保存的精确引用不变；后续新提案派生新身份，数值轨迹、原始反馈与算法状态一致。
- 60 条 warning 来自既有 MOEA/D 可选档案、VNS 未装配变化能力和旧 mutator 上下文声明提示；
  没有失败断言。这是上述选定模块的结果，不是全仓库测试或大池性能结论。
- 示例 Project 的 default / framework-core 严格 `--build --catalog-audit` 均为
  **0 errors、0 warnings、17 infos**，各 26 项 completed。
- 仓库根 framework-core 静态 Doctor 为 **0 errors、0 warnings、194 infos**，
  517 completed、97 skipped；根命令未使用 `--build`，不代表全部 Case 已运行。

实际 Project run：`20261020T032825Z-647414b80a`。
VNS 为 10 步/28 次求值，MOEA/D 为 10 步/33 次求值并发布 6 个方向视图；
两个 trials 集合各有 27 个接纳提案，elite 各有 20 个成员、revision 为 10，view_id 保持不变。
详见 [运行结果](../../examples/cases/pool_workflow_pilot/RESULTS.md)。
