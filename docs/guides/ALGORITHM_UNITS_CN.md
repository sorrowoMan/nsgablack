# 算法管线构建 Unit，Adapter 操作 Unit

日期：2026-10-08。本轮覆盖原审查清单中的全部 31 个主干 Adapter 类（含基类和兼容类），
以及 19 个非模板示例策略、70 份模板副本。数量来自源码盘点，不是 Catalog 算法种类统计。

## 职责与边界

自定义成员字段优先继承基础 Unit，声明 member_fields 并实现一个 on_members_changed 钩子。NSGA-II/III/SPEA2 由 Adapter 选成员、Unit 统一维护；DE/MOEA/D 复用局部替换入口。已实现的 age 示例、明确来源映射与恢复边界见 [Unit 成员维护](../architecture/UNIT_MEMBER_OPERATIONS_CN.md)。

变异组件可通过 [UnitInputSpec](../architecture/UNIT_OPERATOR_INPUTS_CN.md) 声明字段与特征依赖。mutate 只生成提案，repair 由控制面在预算裁剪后执行一次；直接调用 propose 的测试或工具须显式补齐修复/对账阶段。

Unit 保留候选本体或候选集合，并扩展算法需要的特征和状态；这不是候选编解码。内置 Unit 已提供 `feature(UnitFeature)`，按声明依赖维护派生结果；NSGA-II 排序和种群距离已接入。用法、反馈阶段及缓存/持久状态的区别见 [Unit 特征维护](../architecture/UNIT_FEATURES_CN.md)。

- Problem 仍使用现有目标/约束评价协议；问题管线负责表示、初始化、修复和可行性处理。
- 算法管线构建算法操作的结构，包括节点、标签、种群、方向、探针、参数槽位和几何结构。
- Adapter 操作这些结构，决定扩展、排序、接受、更新和何时重建。Builder 不评价目标、不决定接受规则。
- mlblack 继续提供模型语义、Codec、训练/评价与 Provider；本次未修改 mlblack 或 blackbase。
- Unit 不是 Adapter + pipeline 的组合包，也不包含线程池、session、全局资源租约或完整 Solver。

候选型 Unit 和复合 Unit 不强行共用一种投影：

1. `UnitBuildRequest` 用于单候选结构，Unit 必须提供 `to_candidate()`；数值和 UnknownState metadata 必须保持。
2. `StructureBuildRequest` 用于种群、参数槽位、局部区域等复合结构；schema 声明 `candidate_projection=False`。
   构建请求只携带脱离后的数据，不传入 Provider/session。不能把整个种群展平成一个假候选。

## 各 Adapter 的正式结构

### 图搜索

- **AStarAdapter**：`SearchNodeUnit` / `SearchNodeBuilder`。节点包含 g/h/f、父 key 和父 Unit ID。
- **MOAStarAdapter**：`ParetoLabelUnit` / `ParetoLabelBuilder`。保留向量代价、多标签身份和有效位。
- 两者的代价、优先级、支配判断和前沿操作仍在 Adapter。构建器不得改写 Adapter 给出的 g/h/f。
- 持久 checkpoint 和步骤回滚现在都保存完整前沿、pending 父关系与自定义 Unit codec 数据，恢复等级为 L1。

### 轨迹与候选

- **VNSAdapter**：`CandidateUnitBuilder` 构建当前/提案候选；独立 `NeighborhoodUnitBuilder` 构建邻域尺度序列。
  `k`、接受判断和重启由 Adapter 控制。可以独立传入 `unit_binding` 和 `neighborhood_binding`。
- **SimulatedAnnealingAdapter、SingleTrajectoryAdaptiveAdapter、GaussianSearchAdapter**：`TrajectoryUnitBuilder`。
  当前点/最优点及已支持的语义 envelope 存入 Unit；温度、成功率窗口、步数、接受规则和 RNG 保留在 Adapter。
- **FixedCandidateAdapter**：`CandidateUnitBuilder`。每次只构建和送评一个候选，不引入虚构优化循环。
- **PatternSearchAdapter**：`PollUnitBuilder`。管线按指定坐标建立方向结构，Adapter 决定采样坐标、步长和接受。

### 种群与分解

- **NSGA2Adapter、SPEA2Adapter**：`PopulationUnitBuilder`；Unit 内 X/F/V 与 candidate tokens 行对齐。
- **NSGA3Adapter**：`ReferencePopulationBuilder`；额外构建并保存参考方向，恢复不重新生成参考点。
- **DifferentialEvolutionAdapter**：`DifferentialPopulationBuilder`；额外保存 target indices 和逐 trial 基线分数。
- **MOEADAdapter**：`DecompositionUnitBuilder`；额外构建邻接结构和 ideal 存储，保存权重、子问题与提案模式对应关系。
- 选择、变异、交叉、Pareto 排序、标量化和 replacement 仍由 Adapter 执行。SPEA2 没有因此被扩写成新算法。
- 原来的 `population/objectives/violations` 等属性通过 `UnitField` 直接读写同一份 Unit 数据。
  Solver 的 CandidateBatch、token 和 Population Snapshot 仍是控制面权威协议，没有第二份平行候选身份系统。

### 专用计算结构

- **GradientDescentAdapter**：`PollUnitBuilder` 保存坐标/符号配对、方向及 repair 后实际位移。
  Adapter 按存活的完整探针对计算差分，继续保留原有“最佳探针分数作为接受代理”的策略。
- **GradientOptimizerAdapter**：`ParameterUnitBuilder` 分配参数及 Adam/AdamW 动量槽位；
  梯度裁剪、衰减、动量更新和参数步进仍在 Adapter。
  Provider live StateRef、资源上下文、COW 与清理债务仍走原有显式事务协议，通用 Unit codec 不复制服务对象。
- **TrustRegionBaseAdapter、TrustRegionDFOAdapter、TrustRegionMODFOAdapter、TrustRegionNonSmoothAdapter、TrustRegionSubspaceAdapter**：
  `RegionUnitBuilder` 保存中心、基和权重；子空间 QR/SVD/PCA 等几何构建进入管线。
  刷新时机、采样、半径增减和目标聚合仍在 Adapter。没有额外宣称实现二次模型、bundle 法或子梯度法。
- **MASAdapter**：`ModelSearchUnitBuilder` 保存中心和训练历史，并提供模型工厂。
  模型拟合时机、探索/利用和候选排序仍由 Adapter 决定。Unit codec 本身不重新训练模型；
  原有 MAS 恢复逻辑仍可按保存的历史显式重建模型。
- **EliteRetentionAdapter**：`ArchiveUnitBuilder` 保存有界精英记录；搜索更新和排序仍在 wrapper。

### 组合与兼容类

**AlgorithmAdapter** 提供绑定/校验/组合审计契约；**CompositeAdapter、RoleAdapter、RoleRouterAdapter、
StrategyChainAdapter、StrategyRouterAdapter、AsyncEventDrivenAdapter** 委托各子 Adapter 的独立 binding。
组合器的 range、分区、角色、阶段和事件关联继续使用既有事务协议，不包装成同一种搜索 Unit。

**MultiStrategyControllerAdapter、MultiRoleControllerAdapter** 继承正式 router 的委托方式。
原 `UnitSpec` 改为 `StrategyInstanceSpec`，旧名称保留兼容 alias；该类型表示执行实例，与算法操作 Unit 分开。

## 最小装配

以下代码放在标准 Case 的 pipeline/adapter 模块，由 `build_solver.py` 组装：

```python
from nsgablack.adapters import NSGA3Adapter, VNSAdapter, CompositeAdapter
from nsgablack.representation import ReferencePopulationBuilder, NeighborhoodUnitBuilder
from nsgablack.units import UnitBinding

adapter = CompositeAdapter([
    NSGA3Adapter(unit_binding=UnitBinding(ReferencePopulationBuilder())),
    VNSAdapter(neighborhood_binding=UnitBinding(NeighborhoodUnitBuilder())),
])
```

主干具体 Adapter 均有默认 binding；通过 `unit_binding=` 或构建完成、setup 之前的
`set_unit_binding()` 替换。绑定是实例级配置，不能用它隐式热切换正在运行的算法。
各子 Adapter 可用不同构建器，不需要重写 Solver 的全局问题管线。

## 装配对齐与显式兼容

Adapter 声明所需 `unit_schema`、`unit_build_operations`，必要时声明 `unit_builder_methods`。
多个结构槽位通过 `additional_unit_schemas/additional_unit_build_operations` 声明。
builder 声明实际输出 `schema` 与 `supported_operations`；跨 schema 使用时还须声明完整的
`compatible_schemas`。装配会同时核对结构契约、构建操作和必要工厂方法。

兼容关系具有方向性：实际结构必须包含所需字段，候选投影种类一致，目标 schema 的名称、版本及
字段契约必须精确匹配显式声明。不会仅按 Python 继承或同名字段推断兼容，也不会自动接受新版本。
声明兼容意味着构建器作者承诺相应字段的语义、操作和状态更新规则可替换；领域正确性仍需对应验证。

例如 `ReferencePopulationBuilder` 显式兼容基础 `PopulationUnit.schema`，可用于 NSGA2、SPEA2 和 NSGA3：

```python
from nsgablack.adapters import NSGA2Adapter, NSGA3Adapter
from nsgablack.representation import ReferencePopulationBuilder
from nsgablack.units import UnitBinding

binding = UnitBinding(ReferencePopulationBuilder())
nsga2 = NSGA2Adapter(unit_binding=binding)
nsga3 = NSGA3Adapter(unit_binding=binding)
```

两者共用无状态构建器，各自拥有独立 Unit。反向把基础种群 builder 提供给 NSGA3 会失败，
因为它没有声明参考种群契约与 `reference_directions` 构建操作。
仅声明正确的 schema 仍不足够：缺少操作会在首次构建之前报错；MAS 的 builder 缺少
`create_model()` 也会在装配时报错。构建期还会拒绝未声明的操作。

`get_unit_contracts()` 的 `alignment` 显示所需 schema、实际匹配方式（exact 或 declared-compatible）、
所需/可用操作及工厂方法。Solver 装配、setup 前后与 Doctor `--build` 共用同一校验入口，
包括组合树和 VNS 的额外邻域槽位。
未声明 Unit 契约的旧式自定义 Adapter 保留兼容入口，不计为已经验证 Unit 对齐的组件。

兼容关系只用于选择构建器。checkpoint 继续保存**实际结构 schema 与 codec binding**，
恢复必须精确匹配；不能因为两个结构可被同一个 Adapter 消费，就相互解释其 checkpoint。
已有的 schema/binding 恢复信封没有添加能力字段，装配审计与持久结构身份分开维护。

## 使用 pipeline kernel

```python
from nsgablack.representation import ReferencePopulationBuilder, build_pipeline_kernel

builder = ReferencePopulationBuilder()
kernel = build_pipeline_kernel(
    {"slots": [{"slot": "build_unit", "operators": ["structure"], "method": "build"}]},
    operator_registry={"structure": builder},
)
binding = kernel.bind_units(builder, name="my_case.reference_units/v1")
```

槽必须存在，runner 绑定必须有稳定名称。恢复只走 codec，不重放 build_unit 槽。
若配置改变结构解释或恢复方式，应升级 schema 或 binding 名称中的版本。
名称不会自动哈希整个 config，调用方负责保持版本语义一致。
`bind_units(..., operations=(...))` 可显式描述 runner 的构建操作；省略时继承 builder 的声明。
当 runner 比 builder 的能力更少时，必须按实际支持范围收窄声明。

## 自定义构建器与恢复

每个 builder 声明 `schema/supported_operations` 并实现 `build / dump / restore`。
继承现有 builder 可复用其操作声明；自定义全新 builder 必须列出支持的操作。
结构必须有稳定 `unit_id` 和必要字段。
候选 Unit 保持输入值及语义；复合 Unit 可声明 `validate()` 检查矩阵与索引关系。

复合结构推荐继承相应 dataclass，并让 builder 的 `unit_type` 指向它。
`StructureUnitBuilder` 只编解码显式数据字段，支持数值数组、语义候选、映射、序列与简单标量；
不使用 pickle 或 deepcopy 整个 Adapter。自定义数据类型需要相应 codec。

`UnitBackedAdapter` 将旧数值属性映射到唯一 Unit，并统一保存 `algorithm_unit`。
具体类的 `_get_algorithm_state/_set_algorithm_state` 负责原有策略状态与兼容字段；
新 checkpoint 中旧数值字段可能与 codec 载荷重复，但运行时通过 `UnitField` 只有一份结构数据。
恢复先处理兼容字段，再安装 codec 恢复的完整 Unit，并刷新派生视图。存在特殊 Provider/模型事务时，
使用 `_snapshot_algorithm_step_state/_restore_algorithm_step_state` 保留原有清理和回滚协议。
旧 checkpoint 的数值字段继续可读。新 checkpoint 保存 codec 载荷以恢复自定义字段。

Unit ID 是 Adapter 内的身份；组合时连同稳定组件路径解释。它不是 Solver 的 candidate token。
`get_unit_contracts()` 输出轻量绑定说明，不把完整 Unit 数据塞入 context。

## 明确的行为变化

- 控制面 repair 后、评估前调用 `on_proposal_repair(control, ProposalRepair, context)`。
  before/after 保留数值、语义 metadata 和 token；proposal_indices 是原始提案索引，不能用接纳后的索引解释。
  复合 Adapter 必须按 proposal ranges 和本地选择映射转发；CandidateProposerAdapter 自动以同 Unit ID 重建。
- A*/MOA* `repair_policy` 默认 `reject`：repair 在评估前被拒绝；直接 update 的变化检查仍保留。
  领域允许重解释父子边时可显式选 `recompute`，重新计算边代价；这不自动证明邻接合法。
- 信赖域 repair 后仍须位于当前采样区域；subspace 还校验子空间，不允许 repair 静默改变搜索几何。
- 有限差分默认 `repair_policy="coordinate"`，使用实际正负探针间距；退化为同一点的方向不贡献梯度。
  repair 改动其他坐标时明确拒绝。`reject` 进一步要求步长也保持不变。
- EliteRetention 在装配/执行前检查内层是否允许替换候选；A*、MOA*、有限差分、DE、MOEA/D、
  GradientOptimizer 等带位置/状态关联的提案不能被静默替换。组合树中的不兼容子算法也会被检查。
  保留概率或比例为零时不注入。
- NSGA3/SPEA2 继承构造现在使用已经解析的 config，避免关键字配置被默认配置覆盖。
- VNS `current_x` getter 仍返回副本；原地改 getter 的返回值不会改变当前 Unit，应使用 setter。
- Unit 装配检查包含构建操作和必要工厂方法；自定义构建器需要同步声明这些能力。
- 种群反馈与 token 不能脱离种群；DE target 必须是范围内的整数索引；MOEA/D 的权重、邻接、
  ideal 与子问题记录需维度对齐。保留 setup 前从公开 population snapshot 引导初始化的路径。

## 示例与模板

- `examples/cases/algorithm_units/` 是标准 Project，包含候选构建和符号 Beam 两个独立 Case。
  两者都实际装配 build_unit 槽；problem、pipeline、adapter 分文件落位。
- 原符号 Beam 单文件改为兼容薄入口。其他 13 个旧候选策略转入候选 Case 的 adapter 模块，旧导入路径保留。
- 生产排程的随机/局部策略使用 CandidateProposerAdapter；greedy/ACO 使用 ScheduleUnitBuilder。
  管线构建机器/日期/材料索引和信息素初值，贪心选择、蒸发、沉积仍在 Adapter。
- GMM 的 WarmStartVNS 从 build_solver 中移到 adapter/，在阶段首次提案时取上一阶段 incumbent，
  避免所有子 Adapter 预先 setup 导致 warm start 读取过早。
- 70 份现有模板使用公共候选构建入口；新 solver scaffold 也附带 unit_example.py。
  模板最近提案不是 L2 权威种群，不能按字段名虚报恢复等级。

## 检查与验证

Catalog：14 个 `repr.unit_*` builder 属于 `framework-core`，同时出现在 `default`。
两个新 Case 只属于 `default` 的 example 口径。Solver 与 Doctor 共用绑定校验入口，
覆盖已物化的子组件；工厂在 setup 物化后再校验。

执行记录见本页末尾的最终验证记录。原始逐项设计及实施对照见
[UNIT_ADAPTER_PIPELINE_DESIGN_CN.md](../architecture/UNIT_ADAPTER_PIPELINE_DESIGN_CN.md)。

本轮没有运行性能 benchmark；结构编解码会产生数据拷贝，不能把功能回归通过表述为性能无损证明。

## 最终验证记录（2026-10-08）

全量命令 `python -m pytest -q --disable-warnings --maxfail=3 --durations=8`：
**1169 passed、6 skipped、6 warnings，耗时 541.10 秒**。
覆盖 Unit、复合结构、A*/MOA*、步骤事务、状态恢复、候选身份、Provider 资源事务、扩展点及 Case 装配。
其中 Unit 提取专项 46 项，本次装配兼容专项新增 30 项，合计 76 项；包含真实求解步骤、
JSON checkpoint、失败回滚、替换构建器、构建输入隔离、参数槽位、实际探针位移与正式 Case，
以及显式兼容、方向性、版本约束、缺失操作/工厂、组合槽位和结构关系校验。
它们已计入全量结果，不重复相加。

全量复验还覆盖了 Case 导入隔离修复与更新后的文档契约检查。Case 内新增模块使用局部导入，
跨 Case 测试使用正式 `case_import_context`，避免旧 Case 包的路径注入使其他 Case 加载错误模块。

静态与装配检查：

- `python -m nsgablack project doctor --path . --strict --format problem`：通过，覆盖 43 个 Project、54 个 Case。
- 两个新 Case 分别执行 `project doctor --strict --build --format problem`：通过；
  输出包含 `adapter-unit-bindings-ok`、实际 binding 名称及所需/可用构建操作的 `alignment`。
- Catalog 在 `default` 与 `framework-core` 下的 `list/search/show`：通过。
  两种口径均有 14 个 Unit builder；framework-core 无 example/doc 导向条目。
- `git diff --check`：通过。

此前 Unit 提取阶段另已验证：新建 Project / Case 的严格结构 Doctor、构建器导入、
两个示例仅属于 default，以及 `python examples/cases/algorithm_units/run_project.py --check --build-check`。
后者核对实际 Adapter、问题管线和生效的 Project L0 ResourceContext。

本轮保留工作区原有的其他未提交改动；验收结果来自这个工作区，不是干净 HEAD 的基准比较。
