# Adapter 行为的装配边界

2026-10-20 扩展[池驱动变化编排](POOL_CHANGE_ORCHESTRATION_CN.md)：普通函数可以从已提交池中额外取解，
调整变化顺序，并声明接纳后输出集合；任务输入范围和原算法比较规则保持明确。

2026-10-20 新增 [VNS / MOEA-D 普通函数与池输入试作](POOL_WORKFLOW_PILOT_CN.md)：
`change=function` 可替换完整候选变化，函数按自己的数据连接组合交叉/扰动，
由内部桥接保存身份；不是在原 DE 后追加 mutator。Pool 内核和正式评估/提交路径沿用现状。

初始化、变化、选择、修复可以作为理解 Adapter 的四类行为。Adapter 决定何时执行行为，组件提供具体方法，Unit 维护算法结构。四类是职责分类，不是所有算法必须依次执行的四个阶段，也不是要求所有算法拥有四个相同签名的方法。

Problem 仍然定义原始目标和约束；问题 Pipeline 负责候选的数据处理与问题修复；Solver 控制面维持候选身份、预算、求值、接纳和提交。把搜索方法装配给 Adapter，不会把这些控制职责交给搜索组件。

## 统一的装配入口

每个实际消费者用 `operation_methods` 声明已实现的角色，通过 `set_initializer`、`set_mutator`、`set_parent_selector`、`set_selector`、`set_repair` 装配。`get_operation_contract()` 返回四类中的真实可装配角色与当前绑定；缺少的角色表示没有该通用入口，不代表算法缺少相应思想。组件仅在调用方真正消费它后才算接入，不会凭声明自动生成算法。

例如标准 Case 的装配函数可直接构造：

```python
from nsgablack.adapters import VNSAdapter
from nsgablack.representation import UniformInitializer, ContextGaussianMutation

adapter = VNSAdapter(
    initializer=UniformInitializer(-1.0, 1.0),
    mutator=ContextGaussianMutation(base_sigma=0.1),
)
# 通过既有 component_overrides={"adapter": adapter} 交付给 Case builder。
# 问题 Pipeline 可只提供数据处理与问题修复。
```

组件提供非空 `checkpoint_identity()`。没有持久搜索状态时显式 `stateless=True`，否则实现返回数据 Mapping 的 `get_state/set_state`。UniformInitializer、GaussianMutation 与 ContextGaussianMutation 已提供 RNG codec；独立绑定时由所属 Adapter 捕获，不意味着旧 Pipeline 自动保存所有叶组件状态。组件不得把锁、executor、Provider session 或闭包对象图塞入 codec。

## 多处选择与可替换规则

“选择”是一个行为类别，一个 Adapter 中可以存在多处选择。当前 `parent_selector` 专门决定父代来源；offer-row `selector` 的请求 purpose 明确指定 survivor、replacement、candidate 或 proposal_order。它不取代所有 `if`、`argmin`、邻域推进或停止判断。

`SelectionRequest` 保存脱离且只读的候选矩阵、选择反馈、可选算法分数、请求数量与参数；返回的是本请求内有序、唯一、合法范围的整数索引。它不直接提供可写 Unit/Solver，也不把方向分数写入原始求值。需要参考 Unit 时另声明 `UnitInputSpec`，实现 `select(request, *, rng, unit)`；参考结构初始时可能为空，待选候选在 request 中，不可默认二者行数相同。

NSGA 的 selector 负责生存选择；DE/MOEA/D 是当前目标槽位与 trial 的二选一；SA 的 selector 返回完整考察排列，仍逐行经过 Metropolis；VNS/Single/Pattern 的 selector 提名候选，仍经过改善或投影约束守卫。`FeasibilityFirstSelection` 是显式选择的可行性/分数排序策略，未装配时保留算法默认规则；它不是通用 Pareto 或退火规则。

以后可以用类似 `@operation("selection", purpose="parent")` 的装饰器标明函数用途并检查声明。本轮没有增加这个 API：Python 装饰器标记函数/类，不能替任意代码片段自动推导依赖、状态与可复用性。只有需要独立替换的规则才值得提取组件，其余控制逻辑继续留在清楚命名的方法中。

## Unit 的归属与按需创建

Unit 的运行实例由具体 Adapter 拥有，问题 Pipeline 不为每个候选提前构造所有算法结构。`UnitBinding` 仅装配 builder、codec 与可选 runner；提供构建能力与执行构建是两个动作。种群 Unit、当前点 Unit、节点图等按算法自己的实际输入建立，不共用另一 Adapter 的可写结构。

`UnitBackedAdapter` 构造及 setup/fresh reset 后允许 `algorithm_unit=None`。首次真实需要结构时调用 `ensure_unit()`：不存在则构建，已存在则返回同一实例；后续成员维护、暂停后继续不会重复初始化。显式 reset 解除旧结构，下一次实际需要才创建。已有状态的结构重建操作与图搜索产生新节点仍是算法的必要工作，不属于重复初始化。

checkpoint 和步骤快照显式保存尚未创建的状态、稳定 `unit_id` 与绑定契约；失败前没有 Unit，回滚后也没有 Unit。恢复已有结构只调用声明的 codec，不重新调用构建 runner。配置不同的 schema/binding 在尚未创建时也须拒绝恢复，不能把“没有值”误解为“没有契约”。显式缺席的信封不得同时交付活跃种群数据；旧数值导入与该缺席状态分开解释。

组合器不把未创建子 Unit 的空数值视图发布为 population partition，避免提交时回写空分区而意外启动未调度的算法。池精修零接纳后可以显式重启到 Unit 缺席；处置校验仍核对稳定身份，审计用 `null` 表示缺席，不能为校验重建结构。有候选被接纳却丢失结构，或零接纳后改变身份，均须拒绝并按原步骤事务回滚。

观察、运行投影、`get_operator_unit()`、偏好绑定与 Doctor 不得调用 `ensure_unit()` 来填补数据。未创建的单 Unit 偏好视图返回 `None`，真正执行该偏好时报告未激活依赖；声明 `apply_to_paths` 的偏好仍先检查候选消费范围。字段读取返回本族声明的空默认值，不形成另一份可写状态；列表、字典和数组的空默认视图不可原位修改，显式写入真实字段或修改成员前应先取得 `ensure_unit()` 的实际结构，避免对临时空容器写入后静默丢失。Doctor 可以读取 builder 显式声明的 `unit_type` 检查字段、反馈视图与特征依赖，不计算特征或创建实例；动态类型未声明的值级要求留到真实调用检查。

UnitRepair 在装配阶段只要求实际叶所有权、UnitBinding 与可检查的字段声明，不要求先造一个空 Unit；修复执行仍必须有当前提案所属的真实结构，并走原共同验收和事务。

## 初始化的统一含义

初始化是算法请求一个或多个起点。独立 initializer 可以更换起点生成方法，但不能覆盖本次任务已经声明的池输入。显式 Pool intake、来源时点、游标与精确 SolutionRef 仍由原控制路径管理；读取一个种子与生成一个新提案是不同操作。组件不直接登记全局池，不拥有额外资源授权。

初始化产物仍须经过正常 repair、求值与接纳。种群容量、初始取解配额、池历史数量、后代批次大小分别配置。初始化组件不负责填满所有池，不从一次未接纳结果推断算法已经建立了有效基准。

独立绑定具有显式配置身份与状态 codec。仅在实际绑定组件时进行组件播种；无绑定的旧运行保持原随机流。组件状态随实际叶 Adapter 的步骤事务和 checkpoint 保存，恢复不通过重跑 initializer 来重建已存在的状态。

## 种群算法

NSGA-II、NSGA-III、SPEA2 的父代来源选择与环境选择有不同职责。前者返回精确父代引用，后者消费已评估候选并决定 Unit 成员；不能因为都叫“选择”就共享一个模糊接口。交叉、变异属于候选变化，成员数组与扩展行字段仍由 PopulationUnit 统一维护。

DE 的差分供体、目标槽位和交叉掩码共同定义一次变化。MOEA/D 的方向、邻域、权重与参考点定义比较框架；变化后的候选仍由当前方向规则决定是否替换。可装配的叶方法必须保留这些依赖，不能把普通单候选 mutator 当作完整 DE 或 MOEA/D 策略。

跨算法父代来源通过 Pool 引用交接，不能把另一 Adapter 的种群排名作为当前算法排名。MOEA/D 发布的投影子池提供比较任务，不改写母池 raw feedback。接收方选择反馈视图的责任仍由显式任务契约承担。

## 单轨迹与邻域算法

SA 的变化与温度下的接纳是两种方法；VNS 的变化与邻域推进也不同。装配候选变化组件并不取走温度、邻域计数或停滞策略的所有权。选择组件只能消费当前请求提供的候选、反馈和参数，不能通过 Solver 闭包修改阶段或共享权威。

VNS 拥有当前候选 Unit、待评候选 Units 和独立邻域 Unit。它的 `get_operator_unit()` 返回当前候选结构，而不是一个包含全部待评候选的单一 `algorithm_unit`。因此它不能直接绑定现有单 Unit 的 UnitRepair。其 `on_proposal_repair` 仍按原提案索引重建各待评 Unit，保留 Unit ID。若以后开放可装配结构修复，需要先定义多 Unit 草稿与部分接纳的正式目标契约。

VNS 的辅助邻域 Unit 同样按需创建，构造与 fresh setup 不调用候选或邻域 builder。首次实际提案建立所需结构，后续步骤与暂停继续复用；任务 restart 可以保留已建立的静态邻域几何。冷态 checkpoint 保存显式缺席、包含辅助槽位的绑定契约及邻域构建参数身份，恢复只核对声明，不计算尺度。旧 active checkpoint 若有完整 Unit codec，仍走 codec 恢复；只有 `current_x` 数值或缺少邻域结构的 active 存档须显式迁移，禁止靠恢复时重跑 builder 补出状态。

## A* 与 MOA*

本轮为 A* 与 MOA* 开放独立 initializer。已有 `start_state` 与 initializer 都是根来源，同时指定会报错。显式池种子仍须选择 `pool_start_policy="new_root"`；已有路径不能通过新种子静默替换。

这两个算法已有明确的领域装配点：`neighbors`、`edge_cost`、`heuristic`、`goal_test`、`state_key`。变化产生的不是无关系数组，而是带父节点、路径代价和标签关系的候选。选择操作属于 frontier／closed 集合与支配关系，不能由普通候选排序接口替代。

ProblemRepair 可能改变邻居的含义。默认 `repair_policy="reject"` 拒绝变化；显式 `recompute` 重新解释父边，并在消费反馈时重建启发值和标签关系。框架不替领域证明修复后的边仍合法。图搜索不开放普通 mutator、普通候选 selector 或单 `algorithm_unit` 的 UnitRepair；不支持的直接绑定必须拒绝。

起点初始化组件的状态同时进入步骤快照和正式 checkpoint。恢复前验证绑定身份，不以再次调用根生成器代替恢复。节点与标签仍通过各自 Unit codec 保存。

## 信赖域四族

DFO、多目标 DFO、nonsmooth、subspace 共用信赖域行为骨架。本轮开放 initializer 和结构 repair；repair 仍是既有 UnitRepair／JointRepair 契约，问题修复仍由问题 Pipeline 管理。

变化保持原生 typed sampler：中心、半径、box 或子空间基矩阵共同定义候选区域。DFO、多目标和 nonsmooth 使用无穷范数 box；subspace 同时约束子空间残差与基坐标半径。任意候选 mutator 可能移出区域，本轮不把它作为通用装配点。

选择还决定中心迁移与半径扩张／收缩，不能只返回一个“最好候选”就省略这些状态变化。新起点先建立已评估基准，再生成邻域。修复后的最终候选仍须通过算法自己的区域对账；UnitRepair 不能改大半径以假装满足约束。

## 有限差分 GradientDescent

本轮开放 initializer 与 UnitRepair。变化仍由原生 poll 结构管理：同一维度的正负探针、实际位移、对应反馈共同决定有限差分。预算或接纳后只有完整配对可以参与梯度估计。估计得到的下降点是新提案，需要下一次独立 repair／求值后才能替换当前中心。

普通 mutator 或不理解配对关系的 selector 会破坏这个契约，因此本轮拒绝。ProblemRepair 不仅可能改值，还可能改差分几何；原生对账仍检查坐标方向与实际步长，UnitRepair 不能绕过该验证。

## GradientOptimizer 与 Provider

本轮不扩展 GradientOptimizer 的直接算子装配。它的变化依赖求值返回的梯度、优化器 moments，以及可选 Provider transition。Provider 状态通过 StateRef 寻址，转换受 ResourceContext 授权，步骤失败与提交使用现有 COW／清理队列协议。

将目标标量化并不自动变换梯度。普通投影子池不能假装提供正确梯度；有活 Provider 参数状态时也不能直接 repair 数值投影而不对账。后续若拆优化器变化，必须使用显式梯度／状态转换请求，不能把 Provider gateway 包装成普通 mutator 并复制其对象图。

## MAS

本轮开放 initializer 与 UnitRepair，探索噪声、surrogate 候选生成与预测预筛保留原生实现。MAS 同时存在两种选择：送评前的 surrogate 预筛，以及真实反馈后当前点的选择。二者的输入和证据不同，不声明为同一通用 selector。

受投影任务控制的比较框架与 surrogate 训练数据也必须分别解释。原始目标、投影比较值和预测值不能混为一种反馈。模型运行对象不进入通用绑定 codec；已有显式历史与模型重建协议仍负责恢复。

## FixedCandidate 与自定义 CandidateProposer

FixedCandidate 本轮只开放 initializer，每次依旧通过正式控制路径评估一个候选。它没有搜索变异或环境选择，不为统一外观添加空操作。repair 后的实际接纳值仍与精确池引用同步保存。

CandidateProposer 是自定义提案的基类，负责可复用 Unit 构建与修复对账，不知道子类如何初始化、变化、选择或保留候选。因此基类不自动开放四类绑定；子类明确消费某组件后才能声明支持，并保存其状态和真实保留根。

## 包装与组合

Composite、RoleRouter、StrategyRouter、串行 Chain、Async event 编排拥有子 Adapter 的调用、任务与反馈路由。它们不拥有一个隐含的全局变异或环境选择方法。新组件应装配在实际叶实例或实例工厂，根层不广播绑定到全部后代。

Role、Elite 等单 inner 包装即使能透明转发 population 或结果，也不因此自动支持所有操作绑定。默认拒绝未声明支持的角色；需要转发时必须明确实际所有者，状态只归一处。Elite 的注入还须服从 `can_replace_proposals`，不能替换图搜索、有限差分等带结构因果的提案。

## 修复的统一边界

“Adapter 的修复”在本轮表示所属算法 Unit 的修复装配，`set_repair` 绑定既有 UnitRepair。它要求实际叶有 `algorithm_unit` 与 UnitBinding，并遵守共同验收、部分接纳投影与回滚。A*、MOA*、VNS 等不同结构仍使用其原生提案对账，不伪称已经支持单 UnitRepair。

ProblemRepair 管问题可行性，UnitRepair 管算法结构。两者都可能改候选，因此共同修复必须验证同一最终版本；不能以最后一个 repair 的返回值作为唯一成功依据。默认评估前问题修复仍在预算裁剪后执行一次。绑定组件不会获得额外求值、接纳或发布权。

所有未支持角色均应在装配时明确拒绝。能够按四类描述一个算法，不等于已经开放四类任意替换；已实现的接缝、原生 typed 接口和拒绝原因须分别报告。

操作声明审查只检查角色、真实绑定方法、可绑定签名与状态归属，不执行算子、identity 或状态捕获方法。Unit 依赖优先用已有实例检查；尚未创建时可用 builder 的显式数据类型检查可证明的声明，不执行初始化或特征计算来填补检查面。真正调用选择器时仍严格捕获并验证实际所有者的只读 UnitInputs，不能从“初始化前未发现错误”推断任意字段依赖都已通过验证。

## Unit 按需创建的综合验收

2026-10-19，Windows／Python 3.13.2：UnitBackedAdapter 与共享检查、处置、恢复路径的最终同批综合回归 **915 项通过**，覆盖 49 个测试模块；这不是全仓库测试数量。52 条 warning 为测试中缺少可选 archive／mutator 或显式装配组合的能力提示。下文较早的 619／113 等批次与本批重叠，不累计为独立用例。

其中新增的生命周期专项共 31 项，入口为：

```powershell
python -m pytest tests/test_lazy_unit_activation.py tests/test_lazy_unit_elite.py tests/test_lazy_unit_inspection.py tests/test_lazy_unit_admission.py -q --tb=short
```

这些用例已包含在上述综合批次，验证延迟阶段／角色、等候池输入、连续步骤复用、自定义成员维护、未创建状态与稳定身份恢复、只读检查、精英 archive 首次使用、零接纳及身份守卫。完整种群交付、原始反馈／来源、Provider slot 生命周期、联合修复与所有原有结果断言也纳入综合验证。主动修改 Unit 的旧测试改为显式 `ensure_unit()`；未删除或放宽其算法结果断言。

严格 Doctor 再次以 `--strict --catalog-audit --profile framework-core --format json` 检查仓库根，结果 **0 error、0 warning、175 info**，覆盖 **463 completed、90 skipped**；未启用 `--build`。Catalog／脚手架组另实际构建并运行标准 DE／VNS Case。

最后补齐 VNS 辅助邻域 Unit 后，针对该变更的 **260 项通过**（其中新增 23 项），包括真实投影池、嵌套精修、结构兼容与恢复；它们与 915 项存在重叠，不累计为独立用例。专项命令：

```powershell
python -m pytest tests/test_lazy_vns_units.py tests/test_vns_adapter.py tests/test_vns_adapter_warnings.py tests/test_trajectory_operation_assembly.py tests/test_local_pool_refiners.py tests/test_trust_region_pool_tasks.py tests/test_algorithm_units.py tests/test_adapter_state_recovery_contract.py tests/test_unit_binding_compatibility.py tests/test_compound_algorithm_units.py -q --tb=short
```

VNS 最终源码下再执行 `test_operation_catalog_and_scaffold.py` 与 `test_runtime_surface_tracker.py`，**16 项通过**，确认标准 Case 装配运行及装配观测仍有效；严格 Doctor 同时复核仍为 **0 error、0 warning**。

## 行为装配阶段的结构族验证

`tests/test_structured_operation_assembly.py` 在九个实际 Adapter 上验证独立初始化、显式池输入优先、异常后绑定与算法基准共同回滚、配置身份不匹配拒绝、正式 checkpoint 恢复与继续运行。六个拥有单一算法 Unit 的族另外验证 UnitRepair 经既有共同修复执行并参与回滚；图搜索／Fixed 拒绝单 UnitRepair。信赖域仍验证问题修复不能将候选移出采样区域。

2026-10-19，Windows／Python 3.13.2：结构族最终 **102 项通过**，包括算法 payload 在恢复绑定后才拒绝时的组件状态补偿，以及直接初始化返回 UnknownState 时语义 metadata、token、provenance 与精确池引用的保留。最后核验发现 FixedCandidate 曾在构建 Unit 前丢失初始化语义，已修复；A*／MOA* 的 `project_root` 原路径通过同类回归。

最后一次针对性复核命令：

```powershell
python -m pytest tests/test_structured_operation_assembly.py tests/test_fixed_candidate_adapter.py tests/test_proposal_repair.py -q --tb=short
```

结果 **123 项通过**（结构族 102、FixedCandidate 2、ProposalRepair 19）。该复核在下述综合回归之后执行，包含最后的 FixedCandidate 修复及新增 3 个回归；未声称重新运行全部 622 个用例。

## 综合验证与范围

同日综合回归 **619 项通过**，覆盖本轮种群／轨迹／结构族装配、只读选择请求、Catalog 与生成脚手架、Pool 父代选择、直接变异、Unit 输入、共享 Pipeline、步骤事务、checkpoint、ProblemRepair／JointRepair、成员更新、局部池精修、MOEA/D、信赖域、图搜索、最终处置、Provider 生命周期与运行契约。39 条 warning 均为测试中未装配 ParetoArchivePlugin 的 MOEA/D 显式提示；它们不表示断言失败。本次未运行整个仓库的所有测试，也未据此声明算法数学性质或性能优越性。

最后的公共契约子集重新执行 **90 项通过**，包含 `test_operation_contract_inspection.py`、`test_adapter_operation_requests.py`、`test_direct_mutation_binding.py` 和 `test_pool_parent_selection.py`；它们与 619 项重叠，不累计为独立用例。

仓库根严格 Doctor 命令：

```powershell
python -m nsgablack project doctor --path . --strict --catalog-audit --profile framework-core --format json
```

结果为 **0 error、0 warning、175 info**；覆盖记录 **463 项 completed、90 项 skipped**。本命令未加 `--build`，不能据此声称全部示例已经装配运行。独立的 Catalog／脚手架测试已实际生成 DE 与 VNS 标准 Case，并通过 Project 的 L0、`build_case` 和 `run_case` 验证。

## Unit 按需创建的检查面验证

同日后续改动执行以下检查面回归，共 **113 项通过**：

```powershell
python -m pytest tests/test_lazy_unit_inspection.py tests/test_operator_binding_contracts.py tests/test_operation_contract_inspection.py tests/test_unit_features.py tests/test_joint_repair.py tests/test_unit_preferences.py -q --tb=short
```

新增 6 项直接记录构建 runner 的调用次数，验证只读契约检查、checkpoint/步骤状态捕获、种群/运行投影读取、偏好绑定、UnitRepair 装配均不构建未激活 Unit；缺失字段仍报告契约错误。Unit 偏好真正消费未激活依赖时明确拒绝，限定消费范围不命中时不读取依赖。原共同修复与偏好身份测试保留全部原断言，显式需要结构的测试先调用 ensure_unit。此处只记录检查面验证，不替代整体延后启动、暂停继续与回滚验证。
