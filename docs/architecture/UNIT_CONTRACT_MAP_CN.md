# Unit 契约职责与组合验收

按实现与行为测试核对：2026-10-12。规范以 [运行契约](RUNTIME_CONTRACTS_CN.md) 为入口。本清单归纳现有接口，不增加新的运行类型。以下 18 项是职责组；一组可能包含声明与对应的传输值。

## 18 个职责组

| 概念 | 解决的问题 | 所有者与消费者 | 状态、坐标与失败处理 |
|---|---|---|---|
| Unit | 在候选本体之外保存算法关系、特征和必要状态 | 叶 Adapter 拥有；结构操作维护数据；Adapter 作搜索决定 | 持久字段进入实际 Unit codec，随 Adapter 回滚。Unit 不拥有全局运行循环 |
| UnitBinding | 将构建方式、持久 codec 和可选构建 runner 绑定在一起 | Case 装配；Adapter 构建与恢复 Unit | Binding 是声明；可变 Unit 状态另有所有者。恢复走 codec，不重跑 builder |
| UnitSchema | 表达结构类型、版本和必需字段 | Builder 声明；Binding、Adapter 和恢复入口检查 | 相同父类不代表相同 schema；不匹配直接拒绝，不能猜迁移 |
| UnitView / PopulationView | 向偏好提供脱离的只读结构及实例身份 | Adapter 按 owner_path 捕获；Preference 消费 | 调用局部值；路径、Unit ID、schema 和 revision 区分实例。行是槽位，允许同候选 token 占多个槽位；不能反向写回权威 |
| UnitInputSpec / UnitInputs | 明确变异算子实际读取哪些 Unit 数据 | 算子声明依赖；实际叶 Adapter 捕获输入；算子消费 | 输入按该叶的绑定提供，不从共享 context 找 Unit；输入脱离且只读，依赖错误传播 |
| UnitFeature | 计算距离、排序等可重建的派生结果 | Unit 实例管理缓存；算子、偏好或 Adapter 读取 | 明确字段依赖与反馈视图；内容变更后失效。缓存不进入 checkpoint，不能代替历史状态 |
| candidate_feedback | 将分数与它对应的候选内容绑定 | 轨迹、区域等 Unit 保存；Adapter 比较或特征读取 | 分数、依赖和内容版本一起持久化；候选变化后旧分数不能继续排名，不隐式重新评估 |
| member_fields / on_members_changed | 扩展成员字段如何随行选择、替换和清空维护 | 自定义 PopulationUnit 声明；基础结构操作调用 | 回调只读原 Unit并返回数据；草稿验证后整组发布。持久值随所属 Adapter 回滚，不注册第二个事务所有者 |
| PopulationChange | 最终成员分别来自哪一个旧成员或传入行 | 结构操作产生；成员维护钩子消费 | 操作内局部索引及只读 incoming 候选/反馈/token/metadata/provenance，每行恰有一个来源；不表达准入，不进入共享存储或 checkpoint |
| ProblemRepair | 候选是否满足已声明的问题约束 | 问题 Pipeline 拥有；候选处理及共同验收调用 | 修改候选；预检 validate 只读。不能代替只能通过正式评估得知的硬约束 |
| UnitRepair | 候选修改后，算法结构的不变量如何成立 | 实际叶 Adapter 绑定；共同验收消费 | 修改 codec 草稿并保留候选身份。部分接纳须显式 project_admission，不能再次裁剪 Adapter pending |
| JointRepairPolicy | 问题与结构修复如何共同接受同一个最终版本 | Solver 控制面协调；两侧 validator 验证 | 有界协调与拒绝决策；baseline/draft 是步骤局部状态。它不发放资源，不增加第二套全局事务 |
| ProposalRepair | 送评前，同一提案被改成了什么 | 控制面生成；原提案所有者及复合路由消费 | before/after、token、原提案索引和完整 proposed_count；无法重建结构时拒绝求值 |
| BatchDisposition | 预算与接纳最终保留哪些原提案 | 控制面组合；Adapter 整理 pending 和接纳结构 | 索引属于原提案空间；组合层转为子所有者坐标。不能用它替代修复通知 |
| PreferenceQuery / PreferenceScore | 比较什么，以及评分方向与理由是什么 | Adapter 或 Bias 发起；偏好实现评分 | candidate、candidate_in_unit、unit、unit_transition 明确作用范围；评分本身不拥有搜索决定权 |
| UnitPreferenceBias | 将候选相对明确 Unit 的偏好注入选择视图 | Bias 显式绑定参考 Unit，apply_to_paths 可限定候选来源；评估反馈投影消费 | 参考身份与消费范围独立并进入恢复校验。保留 raw 求值；不能改写硬可行性准入。普通偏好无需强制使用此接口 |
| StrategyTask | 当前子实例收到什么角色、阶段、区域和预算任务 | 组合 Adapter 生成；实际策略及原提案回调消费 | 调用任务保持原预算和实例路径；不能被接纳统计或全局观测 context 覆盖 |
| StrategyOrigin | 候选来自哪条嵌套实例路径 | 组合提案产生；反馈、对账和来源观察消费 | 来源随语义候选/token 保存；同类型、同 Unit ID 不能替代 owner_path |

实现入口：`units/contracts.py`、`units/views.py`、`units/operator_inputs.py`、`units/features.py`、`units/collections.py`、`units/population_operations.py`、`adapters/unit_backed.py`、`adapters/proposal_repair.py`、`adapters/strategy_task.py`、`representation/repair_contracts.py`、`core/joint_repair.py`、`bias/preferences.py`。`BatchDisposition` 的协议归 BlackBase。

## 相邻概念为何分别存在

`ProposalRepair` 回答“同一提案变了什么”，`BatchDisposition` 回答“哪些提案获准进入更新”，`PopulationChange` 回答“更新后的成员来自哪些行”。它们跨越不同阶段、拥有不同索引空间，不是同一事实的三份权威。

`UnitFeature` 保存可重建的计算缓存；`candidate_feedback` 保存已发生的求值或比较与当前候选的关联；`member_fields` 可以保存 age 等不可从当前矩阵重建的历史。它们都可能是数组，但数据形状不决定生命周期。

`UnitView` 用于比较主体和实例身份；`UnitInputs` 是一次算子调用所需的依赖集合。两者复用脱离规则，但消费者契约不同；不要让算子获得全部可变 Unit，也不要将只读 view 变成新的状态所有者。

判定重复时，应寻找“同一事实有两个可写所有者”或“同一次坐标转换在两个阶段重复执行”。仅有术语相邻、都涉及状态或都调用 codec，不足以证明应合并。

## 三种坐标不能混用

例如根提案为 `[p0, p1, p2, p3]`，最终接纳 `[p1, p3]`：

```text
ProposalRepair / BatchDisposition：原提案索引 1、3
Adapter.update 的输入：             [p1, p3]
PopulationChange 的 incoming：      本次操作的局部索引 0、1
Candidate token：                  始终保留 p1、p3 的语义身份
```

`apply_selection` 的选择索引指向 `[旧成员, 本次 incoming]`；它的来源映射再指出最终每行的局部来源。`replace_evaluated_rows` 的输入还可能已被 Adapter 的改善判断筛选，或者把一个提案重复送入多个 MOEA/D 槽位。因此不能强行让所有成员操作的 incoming 索引都等于原提案索引，也不能用数值相等反推身份。

## 状态如何共同工作

它们不是五套相互竞争的步骤事务：

- BlackBase 步骤事务恢复所属组件的可回滚状态。
- Unit 成员维护在所属 Adapter 的 Unit codec 内，不单独注册参与者，不新增提交阶段。
- 共同修复的 baseline/draft 处理正常的零接纳和部分接纳；异常仍交给外层步骤事务恢复。
- 证据 Journal 保留已经发生的求值与处置事实，失败时也不擦除；预算消耗同样保留。
- Provider successor 状态和 slot 在失败时释放；成功提交后再清理被替代的 predecessor，清理错误按现有报告处理。

正常零接纳恢复成员和修复效果，然后 disposition 消费并清空本次 pending；它不应重新安装上一轮 pending。异常回滚则恢复整个步骤前的 Adapter 快照。二者恢复范围不同。

成员钩子按结构操作调用，一次尝试允许多次合法操作。age 示例只计 `selection`，不把修复草稿、反馈刷新或局部替换算成一次环境选择。数学上应如何维护自定义历史仍由该 Unit 声明；框架不能根据字段名推断。

## 组合验收与覆盖范围

`tests/test_unit_member_composition.py` 沿实际 `Solver.step()` 和 `CheckpointResumePlugin.save_checkpoint/resume` 验证以下边界：

1. NSGA-II、DE、MOEA/D：共同修复修改提案，接纳非连续原索引 `(1, 3)`，检查 token、metadata、局部成员来源、age 和发布 destination 一致。
2. 三类 Adapter：成员已更新、权威 Snapshot 已 staging 后注入异常，检查 Unit 与权威恢复，求值次数和 durable 失败事件保留；再次证据对账不重跑 Problem、repair 或成员维护。
3. 三类 Adapter：零接纳丢弃修复效果，不执行成员更新，消费本次 pending。
4. 三类 Adapter：通过正式 checkpoint 恢复成员字段及结构历史，不重放修复、成员钩子或 Problem；MOEA/D 也必须遵守 setup 后恢复的共同顺序。
5. 嵌套的两个同类型 NSGA-II 实例，允许相同 Unit ID，由不同角色路径隔离；左侧提交、右侧零接纳，右侧成员字段不被左侧更新污染，正式 checkpoint 恢复保留这两个不同分区。
6. 种群 Adapter 与 Provider 梯度 Adapter 共用一轮步骤：共同修复、部分接纳、成员维护与真实 Adapter 的 transition/materialize/release 调用协同；提交只释放旧 slot，失败只释放新 slot，失败求值证据保留。

预算先裁剪 4 个提案中的前 3 个，再只接纳原索引 1 的场景也已覆盖：修复证据仍报告完整 proposed_count=4，最终成员操作只收到一个 incoming，使用局部索引 0。

第 6 项使用确定性的 Provider 协议测试替身，不证明外部服务的实际存储、并发或梯度数学正确性。所有测试只说明其参数化场景成立，不代表任意五种机制的组合、任意 Python 副作用、所有算法和全部示例均已验证。现有单项测试继续提供更细的边界证据。

后续边界由 `tests/test_unit_scope_and_member_inputs.py`、`test_unit_preferences.py` 与 `test_sa_adapter.py` 验证：重复候选 token 的 MOEA/D 槽位可以生成偏好视图；成员维护读取只读 incoming 数据及父代来源，跨 NSGA-II/DE/MOEA/D 的更新、codec 和回滚保留字段；参考 Unit 与候选作用范围分别声明，单点/批量/Provider、同值嵌套提案与独立副本不混淆；SA 初始点评分经过普通 repair/接纳/事务和 checkpoint，下一轮劣邻居不再必然接纳。验证命令、实际 coverage/skipped 与范围记录在 `artifacts/audit/unit-followup-20261012/`。

## 本轮收口标准

本轮不新增词汇或事务所有者。退出条件是上述组合测试及受影响回归通过、Doctor 的实际作用域和跳过项记录清楚、原工作区与本轮增量各有可恢复提交。后续若一个算法无法用现有职责表达，应先给出具体候选、不变量、所有者与失败场景，再决定是否需要新接口。

Git 检查点记录当前状态，不能补出此前未提交的中间历史。忽略文件、外部存储和其他仓库不自动进入 nsgablack 提交；本次本地检查点范围和验证记录保存在 `artifacts/audit/unit-composition-20261012/`。
