# Unit：保留候选，扩展算法特征，维护一致性

实现日期：2026-10-09。所属层为 nsgablack；本次不改 BlackBase 共享运行协议或 mlblack 语义。

需要在 mutate 中读取 Unit 字段或特征时，使用 [UnitInputSpec / UnitInputs](UNIT_OPERATOR_INPUTS_CN.md)。该说明同时规定统一 repair 的执行阶段；mutate 不再隐含修复。

## 运行主线

初始候选可来自初始化器、已有候选或随机采样。问题管线按声明处理候选；算法管线通过 UnitBinding 保留候选并扩展算法信息。Adapter 决定执行何种搜索操作，得到临时提案，经 repair 对账后求值。Bias 形成选择反馈，Adapter 决定是否纳入当前 Unit。构建 Unit 不隐含候选编码；Unit codec 只处理持久状态。

变异和 repair 之后必须重新满足问题处理契约，并维护受影响特征。NSGA-II 对交叉/变异、MOEA/D 对 pipeline 变异使用独立父代副本。待接纳提案不能通过算子的原地写入修改当前种群；失败仍由已有步骤事务恢复 Unit。

## 用户如何使用

内置 Unit 提供 `FeatureUnit` 能力。给现有 Unit 添加特征，只需声明依赖及纯计算：

```python
from nsgablack.units import UnitFeature

center = UnitFeature(
    "population.center", ("population",),
    lambda data: data["population"].mean(axis=0),
)
value = unit.feature(center)
```

这不改变候选表示，也不调用 Problem。`compute` 只接收脱离的数据，数组/容器为只读输入，不能拿到 Solver、Provider 或整个 Adapter。计算结果也通过闭合数据 codec 脱离。Python 闭包不是沙箱；不得隐藏外部写入、搜索决策或求值。

缓存按真实 Unit 对象隔离。读取会检查 unit_id、schema 及声明依赖的内容；即便旧代码原地修改数组，也不会命中旧依赖下的结果。同名特征更换声明对象时重新计算。更换/恢复 Unit 后不沿用旧缓存。

`unit.feature(spec, cache=False)` 强制完整计算；`unit.clear_features()` 释放当前缓存。依赖必须是显式 dataclass 数据字段，不能通过属性暗读另一个特征。特征计算期间的嵌套特征调用会被拒绝；计算期间依赖改变也不能发布结果。

## 轨迹与区域的候选关联反馈

TrajectoryUnit、PollUnit、ParameterUnit、RegionUnit 的 `candidate_feedback` 保存显式的 value/dependencies/revision 记录。Gaussian 的 best_score/best_violation 依赖 best 与 candidate_metadata；SA、PatternSearch、有限差分的 current_score 依赖 current；信赖域的 best_score 依赖 center。Adapter 的这些属性是同一 Unit 数据的访问入口，不再另存一份可写分数。

候选被替换或数组、metadata 被原地修改后，依赖内容不一致的属性读取返回 None；旧记录随 codec 保留其旧版本，读取不会悄悄重签。依赖 candidate_feedback 的 UnitFeature 遇到过期记录报错。修复后的新候选须按算法规则获得新反馈，不能继承原候选的比较资格。

这里保存的是声明为 selection 的候选关联数值，不证明其来自真实 Problem 求值。例如有限差分的 current_score 仍是方向采样代理值。GradientOptimizer 的上一轮评估分数、历史最佳指标与梯度矩是算法历史，不能误标为更新后参数的当前目标值；本改动没有把所有历史度量都迁入候选反馈。

**恢复兼容性：**`nsgablack.trajectory`、`nsgablack.poll`、`nsgablack.parameters`、`nsgablack.local_region` 的 Unit schema 已从 v1 升为 v2，candidate_feedback 成为必需字段。UnitBinding 拒绝旧 v1 契约，不能把缺失的版本关联自动解释为已验证反馈。本轮没有自动迁移器，也不会在恢复时重跑评估。旧 checkpoint 需使用匹配旧版本的软件，或显式重新开始；自定义 codec/兼容 builder 应同步声明新契约。

## 反馈阶段与归属

`feedback_view` 必须为 `none`、`raw` 或 `selection`，与 Unit 的 `feature_feedback_fields` 声明一致。当前 PopulationUnit 的 objectives/violations 是 selection；不得把它们标成 raw。自定义 Unit 若保存 raw 字段，应分别声明其归属及有效性。未评估的排序特征抛错，不把缺失反馈当作零。

PopulationUnit 分别记录 objectives 与 violations 所属的数值种群版本；之后若种群改变，选择特征会要求重新评估并附加完整反馈。只赋值其中一个字段，不能为另一个旧字段背书。在两次赋值之间再次改变候选，也不能凑出一个有效反馈对。

`feedback_field_revisions` 与汇总的 `feedback_population_revision` 随 codec 保存，恢复不会重新认证部分更新的反馈。旧 payload 只有共享版本时沿用该版本；两个版本字段都没有时按既有对齐契约接入，无法追溯旧文件中未记录的修改。这些版本检测数值候选的变化，不证明反馈来自真实 Problem，也不替代 token 身份与接纳契约。

完成求值后，使用明确的 Unit 操作维护这组数据：

```python
# 对当前整个种群重新求值后，成对附加反馈。
unit.attach_feedback(objectives, violations)

# Adapter 已决定哪些提案替换哪些成员；按同一行序传入全部数据。
unit.replace_evaluated_rows(
    target_indices, accepted_candidates, accepted_objectives, accepted_violations,
    candidate_tokens=accepted_tokens,
)
```

`replace_evaluated_rows` 先验证现有反馈有效性，再在副本中校验并完成更新，最后发布候选、反馈、token 和版本；输入错误不会留下部分行更新。同一索引重复出现时按输入次序替换，最后一行生效，数值相等也不会吞掉新 token。该操作维护 Unit 的局部一致性，选择权仍属于 Adapter，整步回滚仍属于 RuntimeParticipant 事务；它不提供跨线程原子性。

DE、MOEA/D 的接纳替换已使用这个操作。DE 保留提案时的比较基线；MOEA/D 保留历史 ideal 与邻域定义，随机更新顺序只打乱索引副本。NSGA-II、NSGA-III、SPEA2 的环境选择，以及 DE 的评分和 MOEA/D 的提案/更新入口，会拒绝数值候选已改变但反馈未更新的状态。

Bias 的参考 Unit 应明确为本次决策所依据的状态。PopulationView 已带实例路径、身份和 revision，是一次读取的脱离值；保存的旧视图继续代表旧状态，实时入口应重新取得视图。不要在同一批偏好计算中并发修改它的所有者。

常见依赖顺序为：原始求值 → 基于明确反馈视图的特征 → Bias → 选择反馈 → Adapter 接纳/更新。依赖 selection 的排序不能反过来隐式生成同一轮 selection Bias。需要上一轮排序时使用明确的旧状态；需要固定点迭代时由 Adapter 显式编排。

## 已接入的特征

- `PopulationUnit.pairwise_distances()`：按需生成欧氏距离矩阵。同形状下仅重算变动行涉及的距离；增删成员或维度变化时完整重算。重复数值仍是不同成员，距离相同不改变 token 身份。
- `SELECTION_RANKING`：基于 selection objectives/violations 的非支配等级与拥挤距离。NSGA-II 已消费该特征；改变反馈会自动重算。初始化尚无反馈时 Adapter 的临时抽样策略仍由 Adapter 决定。
- `PopulationView.pairwise_distances()`：在只读快照上按需计算。整体种群多样性及变化评分复用它；逐候选的新颖性仍直接计算到参考种群的距离，避免为了单次查询强制分配平方级矩阵。

自定义 `UnitFeature.update(inputs, previous_inputs, previous_value)` 可提供增量维护，结果必须与同一输入的 `compute(inputs)` 相同；更新失败会传播，不发布旧结果冒充新值。框架不在每次生产调用中重复计算来证明等价，需行为测试验证。

## 缓存、算法状态与成本

特征缓存不是 dataclass 字段，因此现有 Unit codec、步骤回滚和 checkpoint 不持久化它。父路径、历史最佳、优化器动量等原有声明字段仍照常保存，恢复不隐式重跑搜索。缓存清空后结果应可从所属权威输入重算。

距离矩阵占 O(n²) 空间；只在用户或算法请求时建立。缓存依赖检查也有读取、复制和摘要成本，不宣称对所有规模都更快。这里采用按需重算/增量更新，不构建额外依赖图调度系统。共享一个 Unit 的写入与读取由所属 Adapter 串行安排；这不是跨线程同步机制。

当前机制支持内置 Unit 和显式扩展字段；已接入 NSGA-II 排序及种群几何，并闭合 DE、MOEA/D 的候选/反馈/身份更新。自定义种群 Unit 应继承 PopulationUnit，保留这些操作和版本 codec。其他 Adapter 的自有派生字段仍由其实现维护，不能据此声称所有旧字段已经自动获得失效机制。

## 验证

`tests/test_unit_features.py` 对比增量维护与完整重算，覆盖多实例、原地修改、成员重排/增删、只读结果、缓存关闭、反馈视图区分、过期反馈拒绝、嵌套计算拒绝、codec 往返、NSGA-II 回滚及 repair 后拒绝提案。Doctor 对 Adapter 声明的 `unit_features` 检查字段依赖与反馈视图，错误码为 `unit-feature-contract-invalid`，不执行特征函数。

相关测试、Doctor scope/coverage、两个 Catalog profile 的实际结果记录于 `artifacts/audit/unit-features-20261009/`。没有运行性能 benchmark，不把功能测试推导为加速结论。

后续一致性修复由 `tests/test_population_unit_updates.py` 覆盖：部分反馈赋值与恢复、无效替换不改当前状态、重复目标与 token 对齐、DE/MOEA/D 回滚、MOEA/D 原地变异和只读邻域、五类种群 Adapter 的真实运行与恢复。执行结果单独保存在 `artifacts/audit/unit-features-followup-20261009/`，不覆盖上一轮证据。
