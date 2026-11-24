# ProblemRepair 与 UnitRepair 共同验收

实现核对：2026-10-09。属于 nsgablack 优化语义，复用现有步骤事务与 Unit codec。

两类 repair 独立装配，成功针对同一版本的候选与 Unit 判定。能保证声明检查全部通过，不能保证任意候选都可修好，也不证明验证函数的数学正确性。

## 接口与装配

- ProblemRepair：`repair(candidate, context)` 处理数值候选；只读 `validate(semantic_candidate, context) -> bool` 检查最终 UnknownState，包括 metadata。数组返回保留原行 metadata；显式 UnknownState 可改变语义内容。
- UnitRepair：`repair(unit, evidence, context) -> CandidateBatch` 可以修改 codec 复制出的临时 Unit、返回改动后的候选；只读 `validate(unit, evidence, context) -> bool` 检查双方一致性。evidence 是所属 Adapter 原提案坐标中的 ProposalRepair。纯结构修复可返回 `evidence.after`。
- 部分接纳扩展：`project_admission(baseline, draft, evidence, disposition, context) -> Unit`。它在 Adapter 的 `on_proposal_disposition` **之后**运行。baseline 是完整的修复前 Unit，draft 是已修复、已由 Adapter 按接纳结果整理过 pending 坐标的 Unit，两者均脱离真实所有者。evidence/disposition 仍使用该所有者的原始提案坐标；不能再次拿原始索引裁剪 draft。组件保留 draft 的接纳坐标，只投影与接纳相关的修复效果。此方法可选，但绑定 UnitRepair 后出现部分接纳而未提供时明确报错并回滚。
- 两者是 Protocol，无须继承。必须保留维度、行数、顺序、token 和 Unit 身份。UnitRepair 不得擅自放宽算法半径、容量或其他约束；更新特征缓存也不等于完成验证。

在标准 Case 定义组件，由 build_solver.py 装配：

```python
from nsgablack.representation import RepresentationPipeline, JointRepairPolicy
from nsgablack.core import ComposableSolver

# 这些对象由 Case 的组件工厂提供。
adapter.set_unit_repair(unit_repair)
pipeline = RepresentationPipeline(repair=problem_repair)
solver = ComposableSolver(
    problem, adapter=adapter, representation_pipeline=pipeline,
    joint_repair_policy=JointRepairPolicy(max_rounds=1),
)
```

EvolutionSolver 同样支持该参数。各叶 Adapter 可选择不同 UnitRepair，共享问题管线。恢复时须重新装配一致配置。

当前 UnitRepair 的可写范围是叶 Adapter 的 algorithm_unit，须有对应 UnitBinding；其他 pending/路径映射仍由 on_proposal_repair 对账。只有 proposal_units、没有上述入口的自定义 Adapter 不能直接绑定此接口，继续使用原对账协议。

未开启 JointRepairPolicy 时保留原有一次问题修复加 owner 对账，不声称它证明完整问题可行性。配置 UnitRepair 却未启用共同验收时，Doctor 与步骤入口均拒绝。

## 协调与失败

1. propose 后按预算裁剪，只处理获准送评行，保留原提案索引和 token。修复前捕获活跃所有者及其组合祖先的局部 RuntimeParticipant 快照；默认仅 ProblemRepair 的路径也捕获，不能只保护显式 UnitRepair。
2. ProblemRepair 生成候选版本。每轮重新绑定语义 provenance，不按数值相等或旧 individual_id 推测身份。
3. 路由给实际所有者，复制其 Unit，调用 UnitRepair。失败轮不改真实 Unit。
4. 对 UnitRepair 之后的最终候选执行问题 validate，对候选和 Unit 草稿执行 Unit validate；不复用旧版本的通过结论。
5. 双侧通过后，再经 codec 脱离草稿引用交还所有者，执行 on_proposal_repair。对账不得改已验证候选或路由；随后再次验证 Unit。
6. 成功后才求值。此时 Unit 仍是步骤事务中的暂态，允许送评不等于接纳。
7. 最终处置到来后，先恢复零接纳子树的修复前局部参与者状态，包含 Unit 和 owner 对账改动；保持原始 pending 坐标供普通处置处理。即使兄弟策略提交，这些被拒绝的修改也不能留下。已消耗的评估成本与证据不回滚。
8. 根 Adapter 只接收一次最终 `on_proposal_disposition`，由它整理接纳坐标。全部接纳保留修复效果；部分接纳且绑定 UnitRepair 时，再调用 project_admission。最后重验接纳后的 Unit，才进入 Adapter.update 和权威发布。

Adapter 可通过 `admission_unit_fields` 声明由 disposition 整理的 Unit 字段。投影不得改写这些字段；内置有限差分声明 probes/directions/displacements，DE 声明 target_indices/target_scores，MOEA/D 声明 pending_indices/pending_modes。声明格式在装配和 Doctor 检查，实际内容在投影前后核对。自定义 Unit 的其余关系仍须由 validate 验证，框架不推断任意结构的裁剪方式，也不重跑 repair。

DE 与 MOEA/D 明确允许 trial 候选经 repair 替换：DE 保留原目标索引和提案时比较基线，MOEA/D 保留子问题与邻域身份，update 使用新候选的正式反馈；它们没有依赖旧 trial 数值的路径代价或位移。这个声明不能推广到 A*、有限差分等有对应结构依赖的 Adapter。

每轮 Unit 草稿从 propose 后的所有者状态重新复制；前轮候选可进入下一轮，失败草稿的结构修改不累积。默认一轮，可显式增加 max_rounds。重复候选与 Unit 内容报告 repair_cycle，次数耗尽报告 repair_round_limit，对账破坏 Unit 有效性报告 owner_reconciliation_invalid。

validator 返回 false 是预期不兼容：整步回滚后，在独立决策事务中调用根 Adapter 的 `on_joint_repair_rejected(control, report)`。JointRepairPolicy.on_rejection 默认 stop，返回 rejected 并请求停止；retry 显式允许下一物理尝试，用户须保证提案条件有变化，否则回滚 RNG 后仍可能重复。advance 只沿 failures 指定的 owner 路径寻找串行阶段，优先推进最内层可推进的阶段。先规划全部受影响分支，任一分支不可推进就不执行整组计划；执行异常、非法返回或取消则整组恢复。不跳过无关分支，不计入逻辑提交。自定义根 Adapter 可覆盖该决策，但不得伪造 committed 或已完成的 evaluation。

串行阶段的切换只改变调度状态，退出阶段的 teardown 延后到决策或步骤提交之后。待清理阶段进入 checkpoint 队列；逐个尝试清理，失败保留为重试项并写入 AdapterCommitReport，不能把已经生效的调度决定伪装成回滚。当前进程成功清理过的子 Adapter 不在最终 teardown 重复清理；恢复时 setup 重新创建资源，不能持久化并沿用这个进程内成功标记。事务不撤销第三方回调已经产生的外部副作用，故规划和可回滚决策阶段必须避免此类操作。

失败报告保留 owner_path、Unit 身份、所有者局部及根提案索引、token 和具体失败原因；不会仅以同名类或角色寻找责任方。轮次及所有者边界调用已有 checkpoint_case_runtime，复用 Project cancellation/deadline；它不能强行中断正在执行的任意 Python 回调。

签名/身份错误、validator 修改输入、普通回调异常传播并回滚，不伪装成数学不可行。回滚失败也不会返回普通 rejected。

## 版本、组合与范围

共同验收报告保存 candidate_revision、具有 codec 的 Unit 内容 revision、轮数和双方结果。候选版本包含数值、metadata、token，是内容标识而非安全凭证。成功报告进入 StepOutcome，再随持久 EvaluationDisposition 保存；未求值的修复拒绝只生成步骤报告，不制造 Evaluation Event。

报告中的 unit_revisions 对应送评前；admission 中的 unit_revision 对应最终接纳及 disposition 对账后、update 前。两者允许不同，不能用前者证明被拒绝的修复效果已提交。

proposal_repair_children 描述直接子层的索引和局部 context，原对账与新修复共用它。Composite、Role、RoleRouter、串行、事件驱动、多策略和 Elite 包装已接入。按 token 合并，验证每行恰好一个所有者；不按数值或 Unit 类型归属。

报告描述送评边界的声明检查，不表示 update 后整个 Unit 与送评前逐字相同。初始化、独立调用 mutate/repair、update 内新造状态是其他阶段，不自动进入提案协调。

- 问题 validate 应覆盖声明要在送评前保证的约束，不隐式调用 Problem.evaluate、Provider 或消耗评估预算。只有正式评估能得知的硬约束仍使用 raw 反馈的 FeasibleEvaluationAcceptance，不可用恒真预检伪装完整可行性。
- 不自动安装硬可行性门。允许搜索不可行区域的算法保留其原始违反量与接纳政策。
- 两侧可能没有交集；协调层不扩半径、改约束或重跑搜索。
- Unit 草稿变化通过既有内容依赖使特征失效；旧 objectives/violations 不能由修复回执重新认证。轨迹和区域的候选关联分数保存于 Unit 的 candidate_feedback，依赖变化后不再用于比较；相关 Unit schema 已升级 v2，旧 v1 不自动恢复，见 [Unit 特征维护](UNIT_FEATURES_CN.md)。
- 组件不应有隐式搜索历史；有状态组件须另接正式事务/checkpoint，不自动复制任意对象图。共享组件对象仍共享内部状态。
- Doctor 的 joint-repair-contract-invalid 只检查装配、签名和支持的所有权，不执行回调；外部副作用、验证完备性和收敛性不在保证内。

ML Case 使用 `LearningSolver(..., problem_validator=validate_final_state, joint_repair_policy=JointRepairPolicy())`。验证函数接收最终 UnknownState 与 ML context；既有 ModelRepresentation.repair 仍拥有修复，bridge 不猜测某个模型是否可行，也不自动调用评估。未显式提供验证函数时，共同验收检查拒绝该装配。

GradientOptimizerAdapter 对账时同步最终参数与语义 metadata；投影保留历史梯度矩，但清除已变化候选的旧分数，后续梯度来自最终候选的正式评估。尚未物化和释放的 Provider 参数引用不能直接接受修复替换。

测试：`tests/test_joint_repair.py`、`tests/test_joint_repair_orchestration.py`、`tests/test_joint_repair_project.py`；既有编排记录：`artifacts/audit/joint-repair-orchestration-20261009/`。后续候选反馈、真实 Adapter 部分接纳与调度事务测试在 `tests/test_repair_boundaries.py`，证据独立保存在 `artifacts/audit/repair-boundary-20261009/`。
