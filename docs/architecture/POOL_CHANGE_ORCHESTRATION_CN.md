# 池驱动的变化编排：来源、操作顺序与输出

最后核对：2026-10-20。实现位于 `adapters/change.py`、`change_pool.py`、
`change_outputs.py` 与 `pool_tasks.py`，面向 VNS、MOEA/D 的完整 `change`。

后续新增的只读选择、成员管理与 `ChangeResult.edits` 见 [Pool 集合操作](POOL_COLLECTION_OPERATIONS_CN.md)。

## 1. 默认配方与可装配边界

VNS 默认围绕当前点产生邻域；MOEA/D 的旧直属 mutator 默认追加在 DE trial 之后。
完整变化函数可以自行选择输入集合、调用多个普通操作函数、调整先后与分支，
再声明接纳后的输出集合，无需修改算法源码或为每一步创建基类。

Adapter 继续维护算法状态和决策规则。VNS 的邻域切换、改善比较，以及 MOEA/D 的方向、
参考点、邻域替换与 nr 限制保持原义。池提供候选版本与引用集合；入池本身不替换算法成员。
每次函数调用仍返回一个候选，本轮没有把所有 Adapter 改成任意数量输出的流程解释器。

## 2. 最小装配

```python
import numpy as np
from nsgablack.adapters import ChangeResult, PoolOutput, VNSAdapter


def change(request, *, rng):
    reference = request.pool.subpool("elite").random(1, rng=rng).values[0]
    center = .8 * request.candidate + .2 * reference
    child = center + rng.normal(0., request.parameters["sigma"], center.shape)
    return ChangeResult(child, outputs=(PoolOutput("trials", create=True),))


adapter = VNSAdapter(change=change)
```

`elite` 必须在读取前存在并已提交，是否挑选精英由创建方决定。
`trials` 在变化函数返回时尚未创建，外部只能在步骤成功提交后读取。
直接返回一个候选仍有效，无需使用 `ChangeResult`。
完整 change 与直属 mutator、具名 Pipeline mutation 互斥，不隐式执行共享默认变异。

## 3. 跨池取解与操作顺序

调用内的 `request.pool` 提供：

- `main(region="main", stage=None, source=None)`：按冻结运行时点选择已发布母池候选。
- `subpool(name)`：使用调用开始时冻结的子池身份和成员版本。
- `read(refs)`：使用精确 `SolutionRef`，不追读相同 token 的未来版本。

返回的局部选择对象提供：

- `refs`、`len(selection)`：引用与数量，不加载候选值。
- `values`：按需加载脱离、只读的数值矩阵。
- `candidates`：脱离的语义候选。
- `raw_feedback()`：原始 Problem 目标与约束；未评估种子没有反馈，读取时报错。
- `take(indices)`、`random(n, rng=rng)`：局部选择、无放回抽样。
- `merge(other, ...)`：按精确引用合并，不按数值相等去重。

例如 MOEA/D 可以从不同来源取得三个 donor，再自由组合 DE 和扰动：

```python
def change(request, *, rng):
    a = request.pool.main(stage="accepted").random(1, rng=rng)
    b = request.pool.subpool("reference").random(2, rng=rng)
    parents = a.merge(b).values
    if len(parents) < 3:
        raise ValueError("this recipe needs three distinct donor versions")
    trial = parents[0] + .5 * (parents[1] - parents[2])
    child = trial + rng.normal(0., .1, trial.shape)
    return ChangeResult(child, outputs=(PoolOutput("trials", create=True),))
```

要先变异 donor 再执行 DE，就先对 `parents` 生成变异后的局部数组，再计算差分。
交叉两池、按状态切换、组合多个普通函数，都由这份配方表达。
它可以使用 Adapter 默认提供的 parents、方向参数与当前 Unit ID，也可以使用额外来源。
中间计算数组是局部草稿，不因每次算术操作而自动新增 Snapshot 或公共子池。
需要新分数时仍须经过正式评估链；本函数不接管修复、预算或评估生命周期。

## 4. 池任务的来源声明

直接运行叶 Adapter 时，完整 change 可查询本 Solver 已提交的池数据。
在 Router 的 `PoolTaskSpec` 中，默认只授权任务冻结的输入与实际调用者当前父代。
额外来源在装配时声明：

```python
PoolTaskSpec(mode="initialize", count=6,
             change_sources=("reference",), change_allow_main=True)
```

`change_sources` 使用**精确公开子池名**，不追加任务命名空间；原 `select/output` 的相对名称规则保持原样。
额外来源成员在每次变化调用开始时冻结，后续调用可看到后来已提交的更新。
这不改变任务起点、方向权重与参考点在请求开始时冻结的规则。
任务初始化结束后继续运行，仍服从同一来源声明。

嵌套任务的额外池名称与母池权限取祖先声明的交集，内层不能扩大范围。
新声明进入 assembly identity；缺少字段或配置不同的旧 checkpoint 需显式迁移。
范围由调用内 ContextVar 传递，不进入 ContextStore。这是接口契约，不是任意 Python 副作用沙箱。

## 5. 接纳后输出与事务

`ChangeResult(candidate, source_refs=None, outputs=(), edits=())` 可声明额外精确来源、输出集合与普通成员编辑计划。
`PoolOutput(name, create=False)` 默认要求目标存在；只有 `create=True` 才允许创建。
候选正常进入母池；outputs 增加命名集合成员关系，复用同一已评估版本，不复制候选值。

目标只允许普通 `candidate_collection`，不能直接写入算法最终结果视图或 MOEA/D 投影视图。
已有目标冻结 pool/name/view_id/revision，原本不存在的目标也冻结缺席事实。
同名重建或步骤内修改目标时明确失败，不静默重定向。

执行顺序：

1. 返回候选和目的地声明，先验证目标，不提前创建输出集合。
2. 正常问题修复与 ProposalRepair 对账、预算裁剪、评估、硬接纳。
3. 登记接纳候选与原始反馈，通知原提案 Adapter 更新。
4. 按精确 accepted refs 汇总输出，每个目标统一追加一次。
5. 池 manifest 与 Authority Snapshot 提交后，命名输出才对外可读。

`trials` 是接纳提案集合，可以包含算法没有选中的试探解；最终选择继续由原结果视图表达。
零接纳不创建目标，部分接纳只交付最终接纳行，异常由现有步骤事务回滚。
输出指令绑定本次提案 token，派生交接不重放祖先指令。
集合不自动裁剪；退出集合与物理回收继续服从池保留契约。

## 6. 身份、恢复与成本

新提案派生 token，修复保持 token。默认父代引用、实际读取的额外候选/原始反馈引用与
显式 `source_refs` 进入 `change_input_refs`，表示调用提供的数据依赖，不证明每行都参与公式。
来源证据不自动成为永久保留根。

池访问在函数结束后关闭，不能保留到后续步骤继续寻址。
已提交记录身份集合按索引共享缓存，子池只冻结描述符和引用，数值按实际选择读取。
不会为每个方向复制整份母池候选；局部计算数组仍由操作本身分配。
RNG、池集合、任务进度复用已有 checkpoint/步骤事务，没有新增运行循环或资源授权者。

## 7. 示例与验证

完整标准 Project 见 [pool_workflow_pilot](../../examples/cases/pool_workflow_pilot/README.md)。
VNS 使用当前点和 `reference`；MOEA/D 使用已接纳母池和 `reference`，按方向选择两种变化顺序。
它们分别把接纳变化提案交到 `vns_trials`、`moead_trials`，原始多目标反馈不被标量替代。

以下为 2026-10-20 首轮跨池编排验证记录；后续集合维护扩展及其最新结果见
[Pool 集合操作](POOL_COLLECTION_OPERATIONS_CN.md)。

- 综合 28 模块：**439 passed**，138.17 秒；包括普通变化、Unit/算子装配、任务来源限制、
  两个真实 Case 的 checkpoint 恢复、repair、步骤事务、池保留、评估准入/shape/反馈和 SnapshotStore。
- 跨池编排与只读访问专项：**25 passed**，3.14 秒；包含同名目标重建拒绝、修复后最终版本输出，
  以及受限任务只冻结声明视图的检查。
- 任务分配/子池/嵌套/投影专项：**102 passed、1 deselected**，169.57 秒。
  唯一未完成项为 30×100 种群分配样例，先前运行超过四分钟后停止；未宣称该项通过。
  各测试组有重叠，不累计通过次数，也不是全仓库测试结果。
- 综合组 30 条 warning 来自既有可选 ParetoArchive 与旧 mutator 上下文声明提示，没有失败断言。
- 标准 Project 的 default / framework-core 严格 `--build --catalog-audit` 均为
  **0 errors、0 warnings、17 infos**，26 项 completed。
- 仓库根 framework-core 静态 Doctor 为 0 errors、0 warnings、194 infos，
  517 completed、97 skipped。根命令没有 `--build`，不代表所有 Case 都已执行。

首轮 Project run：`20261020T030238Z-6238ff1450`。
VNS 10 步/28 次求值，`vns_trials` 27 个接纳提案；
MOEA/D 10 步/33 次求值，`moead_trials` 27 个接纳提案、6 个方向视图、原始目标保持两列。
示例 [RESULTS.md](../../examples/cases/pool_workflow_pilot/RESULTS.md) 随后续运行更新，保存最新结果。
这验证装配和数据交付，不据此声称算法性能优越性。
