# 以 Unit 为中心理解搜索与偏好

实现核对：2026-10-12。公开入口为 `nsgablack.units`、`nsgablack.bias` 和 `UnitBackedAdapter.preference_view()`。

## 1. Unit 是候选的算法特征扩展与一致性维护单元

候选先经过问题管线，满足本问题的表示与处理契约；是否必须满足全部硬约束由搜索策略决定。Unit 保留候选本体或候选集合，按算法需要扩展距离、排序、路径关系、区域信息等。它类似于数组上的算法信息扩展，不要求把候选转换成另一种编码。取出其中的候选即可求值，只有问题表示确实需要转换时才调用 encode/decode。Unit 的 checkpoint codec 则是持久状态协议，与候选编码不同。

一个相同数值候选，可以是不同父路径下的节点、不同群体中的成员，或不同区域内的试探点。多样性属于“候选相对于哪个种群状态”的关系；不能把不同实例的分数混成一个无归属的候选属性。

框架的职责关系是：

- Problem 定义原始目标和约束。
- 问题 Pipeline 处理候选；算法 Pipeline 通过 UnitBinding 构建结构。
- Unit 保存候选及算法扩展信息，维护相关操作的不变量。
- Adapter 决定结构如何演进，拥有搜索状态与决策。
- Bias 表达可选偏好，输出由 Adapter 的选择策略消费。
- Plugin 提供声明的观察、评估接入、持久化和发布能力。

这是一组职责关系，不是六个组件依次执行。Unit 不接管 Solver 生命周期、资源授权或 Plugin 调度。比较规则也不全部属于 Bias：算法定义要求的支配/生存规则仍由算法策略负责。

## 2. 可选的四种评价范围

普通 Bias 在求值反馈边界表达选择偏好即可；需要群体信息时绑定一个明确的参考 Unit。以下接口用于确有比较需求的策略，不要求每个 Bias 都实现整体 Unit 或变化评价。

`PreferenceQuery` 校验评价对象和依赖的组合：

| scope | 对象 | 必需输入 | 含义 |
| --- | --- | --- | --- |
| `candidate` | 一个候选 | candidate，可选 token | 候选本身的偏好 |
| `candidate_in_unit` | 候选与结构的关系 | candidate、unit，可选 token | 候选在这个 Unit 中的新颖性等 |
| `unit` | 整个结构 | unit | 群体覆盖度等整体偏好 |
| `unit_transition` | 同一结构的变化 | unit、proposed_unit | 一次替换/扩展带来的偏好增益 |

比较两个 Unit 可以分别评价它们，由 Adapter 在语义兼容的分数间决定；不把两个独立 Unit 冒充同一结构的前后状态。transition 要求 owner_path、unit_id、schema 相同。

候选查询保留 UnknownState 的语义 metadata，同时提供只读 `numeric_candidate`。内置距离评分消费数值投影，自定义偏好可读取候选语义；纯数值输入也支持。该入口要求有限的一维数值投影，不冒充无数值投影的任意领域对象协议。

`PreferenceScore(value, direction, reason)` 明确值、`minimize/maximize` 方向和原因。投影到当前最小化选择目标时调用 `minimization_delta()`。raw objectives/violations 不变。该数值接口不宣称覆盖任意部分序；算法自身的不可比关系不应强行压成此分数。

通过 UnitPreferenceBias 接入的评分器须为纯评分器；其可变依赖应来自显式视图。不要把状态转移藏进 evaluate 或闭包。若自定义偏好确实拥有记忆，应像 Tabu 一样声明并接入独立的状态/事件契约；Python 回调检查不构成副作用沙箱。

## 3. UnitView 是只读依赖，不是第二个权威状态

`UnitView.capture(unit, binding, owner_path=...)` 经过已有 UnitBinding 校验与 codec，生成脱离后的只读值，包含：

- `owner_path`：组合中的实例路径；同类型的两个 Adapter 必须有不同路径。
- `unit_id` 和 `schema`：结构身份与语义。
- `revision`：当前 codec 内容的摘要，内容变化后改变。
- `payload`：不可变的显式 codec 数据；不复制锁、Provider 或整个 Adapter 对象图。

`PopulationView` 额外给出不可写的数值矩阵和对齐的成员 token。准备态群体可能尚未获得 token；此时以 `None` 显式表示未知，`membership_identity_complete=False`。未知身份成员仍参与距离计算，不伪造正式候选身份。

行是当前 view/revision 内的成员槽位，token 是候选身份，二者不是同一个概念。MOEA/D 可将同一候选放入多个子问题槽位，因此允许重复 token，不为槽位伪造新候选身份。整体多样性按占据的行计算，重复候选的距离仍为零；候选查询携带已知 token 时，排除该候选占据的全部槽位。需要按子问题或唯一候选集合度量时，应另选明确的偏好策略，不隐式去重。

只有查询 token 与成员的已知 token 相同才排除自身。数值相等、维度相同或 Unit 类型相同均不能代替身份。

`UnitBackedAdapter.preference_view(owner_path=...)` 提供便捷入口；具有 population 字段的已声明结构生成 PopulationView，其他结构生成 UnitView。自定义 Adapter 可自行提供正式视图入口。视图是一次读取，不能长期缓存后假装仍为当前结构。

## 4. 用户怎样装配

在标准 Case 中，偏好工厂放 `bias/`；在 `build_solver.py` 中使用已组装的 Adapter 完成绑定。单个群体的新颖性偏好只需要：

```python
from nsgablack.bias import BiasModule, PopulationDiversityPreference, UnitPreferenceBias

# adapter 是本 Case 已组装的 UnitBackedAdapter，例如 NSGA2Adapter。
bias_module = BiasModule()
bias_module.add(UnitPreferenceBias.from_adapter(
    PopulationDiversityPreference(),
    adapter,
    owner_path=("search",),
    weight=0.1,
))
solver.set_bias_module(bias_module)
```

此绑定每次读取指定 Adapter 的 Unit；不会从一个全局 population 猜测目标。`owner_path` 标识参考 Unit；可选 `apply_to_paths` 单独声明哪些提案实例消费此偏好。两者可以不同，均不是资源/L0 路径。checkpoint 保存参考身份和候选作用范围，恢复时拒绝改绑或改范围。

可运行的完整装配已放入 `examples/cases/bias_gallery/`。通过 `python examples/cases/bias_gallery/run_project.py --check` 检查 Project，再使用同一入口运行；Case 内还装配了具有提交记忆的 Tabu 偏好。

**多策略装配：** 未填写 `apply_to_paths`（默认空元组）时，保持 Solver 全局作用。限定角色/子实例时传入完整的 StrategyOrigin 实例路径，例如：

```python
bias_module.add(UnitPreferenceBias.from_adapter(
    PopulationDiversityPreference(), reference_adapter,
    owner_path=("reference",),
    apply_to_paths=(("unit:explorer:0",),),
    name="explorer_diversity", weight=0.1,
))
```

路径按段前缀匹配：该实例及其嵌套后代适用，相邻实例不适用。正式候选来源由 `StrategyOrigin.from_candidate` 验证，不读取全局 role/strategy_id 观测，不按数值相等猜来源。没有来源的独立 evaluate 或 setup 初始化不属于已限定的提案范围，返回零偏好；来源存在但格式/祖先关系错误时传播异常。范围外不读取参考 Unit。调用中的 `OptimizationContext.candidate_state` 每次从对应的语义记录取得，不沿用上一候选，也不写入 ContextStore。

此限定只消费已经存在的 StrategyOrigin，不为缺少该来源的 Composite/串行提案猜造角色路径。同名偏好在 BiasModule 中会覆盖；为多个范围装配独立 Bias 时须给不同 name。自定义 view provider 的外部可变状态仍由其所有者负责。旧 UnitPreferenceBias 状态若缺少作用范围字段，按绑定契约不匹配拒绝，不静默推断恢复范围。

整体结构或结构操作的偏好由 Adapter 直接消费：

```python
from nsgablack.bias import PreferenceQuery

before = adapter.preference_view(owner_path=("search",))
# after 是同一身份的候选结构的脱离视图，由 Adapter 明确构建。
gain = PopulationDiversityPreference().evaluate(PreferenceQuery(
    "unit_transition", unit=before, proposed_unit=after,
))
# 是否采用该结构由 Adapter 决定；evaluate 不执行替换。
```

PopulationDiversityPreference 当前实现欧氏最近邻新颖性、整体平均最近邻距离和前后差值，输出为 maximize。度量前的领域归一化需由所用结构/策略明确处理，不隐式改变单位。

## 5. 评分与记忆更新是不同事件

TabuSearchBias 现在的确切记忆含义为 **已提交步骤中通过接纳门的提案**，不是所有算过分的候选，也不是算法最终保留下来的全部成员。

流程为：纯评分 → 接纳 → Adapter.update → 暂存记忆更新 → 步骤提交。后续提交失败时，记忆随已有 RuntimeParticipant 回滚。单独调用 evaluate 不记录历史；拒绝的候选不记入。若领域需要“所有实际评估过的候选”或“最终访问的状态”语义，应使用另一个明确命名的记忆策略。

BiasModule 的 get_state/set_state 通过现有 checkpoint_components 保存显式组件状态；Tabu 有独立数据 codec，按已记住的 token 避免窗口内重复登记。新运行先清理记忆，恢复信封随后恢复它。这里没有对任意第三方对象做 deepcopy。

启用有状态偏好后，checkpoint 缺少 Bias 组件或所保存记忆不合法会拒绝恢复，包括非 strict 配置。此前未保存偏好记忆的 checkpoint 不能假装完成精确续跑；需要明确重新开始该搜索。

标记 `stateful_preference=True` 的组件必须声明 get_state/set_state，并显式禁用旧标量缓存；Doctor 检查这项契约。此标记不意味着框架已经识别并迁移所有旧自适应 Bias 的内部状态。

声明 `objective_independent=True` 的偏好，在整个 BiasModule 均满足此条件时，每候选计算一次增量，应用到各目标。旧的目标相关 CallableBias 继续按原接口逐目标计算。Unit 偏好和 Tabu 默认绕过旧标量缓存，避免同代结构/记忆变化命中旧结果。

## 6. 兼容与失败语义

- 旧 DiversityBias 修正为负距离奖励；不再按数值相等排除成员。需要识别自身时使用 PopulationView。
- 旧 population_ref 依赖不能把缺失、不可读或 partitioned snapshot 当作正常空种群；使用明确 Unit 绑定。
- 声明的 Unit 偏好执行失败抛 PreferenceContractError，不能因 plugin_strict=False 静默禁用偏好。
- 本次没有把 DynamicSwitch、ParetoArchive 或 DiversityInit 全部重写。它们的职责拆分仍按专项审计处理，不能因为有了 UnitView 就声称这些迁移已完成。
- 数值评估 Provider、日志和 checkpoint 仍可以使用 Plugin 生命周期。内部存在算法计算不等于拥有搜索决定权。

## 7. 验证入口

以下 205 项与 Doctor 数量是前一轮偏好接入的历史记录。后续特征维护实现及独立验收见 [Unit 特征维护](UNIT_FEATURES_CN.md)，不能把旧计数当作本次运行结果。

`tests/test_unit_preferences.py` 覆盖四种评价范围、同类型多实例、只读视图、准备态成员、身份排除、方向、同代视图更新、Tabu 纯评分、步骤回滚、恢复和真实 NSGA-II 绑定。评估证据与硬接纳继续由 `tests/test_bias_acceptance_boundary.py` 验证。

本轮最终针对相关功能执行 205 项测试，全部通过（8 条 warning）。另外早期运行过 Solver、并行和 Snapshot 基础子集。没有运行全仓全量测试或 benchmark。

仓库严格 Doctor（含 framework-core Catalog 审计）：0 error、0 warning、168 info；coverage 为 443 completed、85 skipped。跳过项主要是未启用全仓 build 的 59 项、25 项无 Case-local Catalog 的登记检查，以及 1 项框架仓登记范围说明。

严格 `--build`：algorithm_units 为 0 error、0 warning、16 info；bias_gallery 为 0 error、0 warning、9 info。bias_gallery 的正式 Project `--check` 成功，行为测试通过正式 load_case_builder/build_case/run_case 路径运行了实际偏好。

Catalog 的 default/framework-core 两口径，共 14 条 show/list/search 命令成功。验证摘要、完整 Doctor coverage 和 JUnit 结果保存在 `artifacts/audit/unit-preference-20261009/`，入口为 `validation.json`。这些证据覆盖指定产品面，不能替代对任意自定义回调、所有旧 Bias 或全部 Plugin 的验证。
