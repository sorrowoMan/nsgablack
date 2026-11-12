# 当前架构的 Catalog：从想法到可检查装配

Catalog 提供“装配实验台”工作区，按“定义问题 → 装配算法 → 运行结果”展开。可以先用自然语言让 AI 生成可编辑的变量、目标和约束，再选择已接入组件、编辑 Pool 交接与编排。三个步骤共用版本化 [框架实验引导 Skill](../../catalog/skills/framework-experiment-guide/SKILL.md)；草案显式应用，试跑另行启动。自定义连续公式问题、装配、正式项目源码、Project 下载和小预算试跑共享同一份文档。入口为左侧“工作区”，详见 [实验台使用与边界](CATALOG_LAB_CN.md)。

Catalog 回答的是：这个想法由谁负责、对应哪个公开组件、怎样装配、可调用什么、目前不支持什么，以及去哪个标准 Case 看完整行为。条目说明不等于运行证明；实验台通过独立 worker 执行正式 Project，并展示对应收据。整数、外部数据与任意 Python Problem 尚未接入在线定义入口，不能由 AI 捏造成可直接运行的公式。

本说明对应当前的 Problem、候选 Pipeline、SolutionPool、Unit／UnitBinding、Adapter、Bias、Plugin 分工。现有 key、kind 和 import 路径继续有效；本轮通过原有 `CatalogEntry.contract` 增加装配说明，避免为了展示而改动运行时职责。

## 1. 先看角色，再看类名

例如 `repr.unit_population` 仍属于 `kind="representation"`，因为这是已公开的兼容索引。它的新装配角色是 `unit_builder`：由 Adapter 通过独立 UnitBinding 按需调用，不应放进问题 Pipeline 当 initializer、encoder 或 repair。

`tool.solution_pool` 的角色是 `pool_store`，负责运行内候选版本和区域；`tool.pool` 的角色是 `pool_view`，表达一次调用中的有序引用选择。二者可以协作，但不是两套候选存储。`tool.population_unit` 保存具体算法的成员与扩展字段，`adapter.search_plan` 表达搜索编排，不能因为都标作 tool／adapter 就忽略这些差别。

kind 仍用于稳定分类和兼容过滤；role 用于解释当前组件在装配中承担的职责。没有新增说明的旧条目，role 回退为原 kind，不根据类名猜测算法能力。

## 2. 四个说明字段

条目在 TOML 中使用现有 contract：

```toml
contract = { catalog = { role = "unit_builder", concepts = ["自定义Unit", "种群扩展字段"], operations = ["build", "dump", "restore"], boundaries = ["结构由所属 Adapter 按需创建；恢复不重跑 builder。"] } }
```

- `role`：装配角色，一个非空字符串。
- `concepts`：用户可能提出的想法和术语，例如“替换采集函数”“种群扩展字段”。
- `operations`：已有运行方法、属性或该装配表面的操作词；不是构造参数，也不是新授予的运行权限。
- `boundaries`：明确职责、不支持的组合和必要前提。出现“不支持”不表示组件完全不可用，而是调用者不能把另一种算法语义偷偷套进来。

三个列表仅包含非空字符串。它们复用原条目的摘要、装配片段、companions 和示例入口；不另存第二份实现，也不改变接纳、资源、事务或恢复行为。

`config_keys` 继续表示构造／装配参数。例如 SolutionPool 的构造面是 `snapshots/run_id`，`create_subpool/read_raw_feedback` 属于 operations；调用内 Pool 的公开构造面是 `parent/name`，`chosen/inject/top` 属于操作。

`companions` 提供相关条目的双向导航，不是“把所有相关部件一起启用”。同一个角色可以有替代实现；每次装配只选择所需部件，并遵守当前 Adapter 的输入和状态契约。

## 3. 从四个实际想法出发

### 贝叶斯引导：先区分软偏好和真实 BO

搜索“贝叶斯引导”时，至少应能看到两类结果：

- `bias.bayesian_guidance` 等历史／距离软评分。当前内置辅助模型是占位实现，不能当作 GP posterior 或完整 BO。
- `adapter.bayesian_optimization` 及 `tool.bo_model/tool.bo_acquisition/tool.bo_acquisition_optimizer`。它们分别承担真实观测、数值后验、采集价值和采集搜索。

例如只改采集强度，不修改真实目标：

```python
from nsgablack.adapters.bayesian_optimization import (
    BayesianOptimizationAdapter, LowerConfidenceBound,
)

adapter = BayesianOptimizationAdapter(acquisition=LowerConfidenceBound(beta=2.0))
```

这是可装配片段，仍需放入已有 Case 的 build_solver。完整标准 Case 为：

```powershell
python examples/cases/algorithm_semantics/cases/synchronous_bo/run_solver.py --check
python examples/cases/algorithm_semantics/cases/synchronous_bo/run_solver.py
```

首版只支持同步单目标、固定参数模型及明确的真实 Problem 路径，不接受 EvaluationProvider 或评估决定插件；采集函数和优化器要求显式 stateless。模型预测、采集值和真实目标始终分开。q-batch、真实异步 pending、随机超参数训练及完整约束 BO 不在当前承诺内。

### 种群加一个字段：找 Unit 的维护规则

从 `tool.population_unit` 看成员结构，再到 `tool.population_change` 看旧成员／新成员映射，最后到 `tool.unit_binding` 与 `repr.unit_population` 看构建和恢复。

新增逐成员字段时，声明 `member_fields`，通过只读 `on_members_changed(change)` 返回对齐更新；Adapter 负责选择哪些成员，Unit 负责维护未知于 Adapter 的字段。不能只加一个数组后假设所有父类操作都会自动理解它。

完整示例是带成员年龄字段的标准 Case：

```powershell
python examples/cases/assembly_workbench/cases/hybrid_search/run_solver.py --check
```

相关说明见 [Unit 成员操作](UNIT_MEMBER_OPERATIONS_CN.md)。Catalog 的 builder 条目不表示检查时就会构造 Unit。

### GA 后 VNS 精修：分开编排、取解和返回竞争

从 `adapter.search_plan` 找 serial/multi/repeat；从 `tool.pool_task_spec` 找输入和每起点额度；从 `tool.subpools` 找指定 Adapter 创建的视图。`Pool.chosen` 只选择已有引用，不会隐含启动 VNS，也不会因为创建一个精英池就自动改变 GA 成员。

先查精确任务与来源，再看：

```powershell
python examples/cases/solution_pool/cases/pool_refinement/run_solver.py --check
python examples/cases/assembly_workbench/cases/hybrid_search/run_solver.py --check
```

前者说明多角色池精修；后者说明自然 GA→VNS→同 GA 返回竞争。停滞触发需要显式运行条件／指标或既有阶段策略，普通 serial 顺序不会自行判断“局部最优”。`subpools.all/random` 也不隐含等待屏障。

### 换 CMA 采样或 MAP 描述符：不用替换整个算法

`adapter.cmaes` 关联采样、排名、分布更新与 `tool.cma_unit`。采样器保留 RNG／游标，完整 cohort 共同更新分布；预算或硬接纳裁掉行时明确拒绝残缺更新，不能改变 lambda 后继续称同一算法。其新均值没有真实评估时不是可交付的最好候选。

`adapter.map_elites` 关联描述符、格子映射、同格竞争、生成器和 `tool.map_elites_unit`。档案冠军在 Unit，Pool 只展示准确引用；描述符不是目标或普通多样性 Bias。首版 emitter 仅提出候选，没有完整 cohort 反馈接口，因此不能宣称已经支持 CMA emitter。

```powershell
python examples/cases/algorithm_semantics/cases/cmaes_distribution/run_solver.py --check
python examples/cases/algorithm_semantics/cases/map_elites_archive/run_solver.py --check
```

## 4. 查询口径和证据状态

教学、完整 Case、文档导航使用 `--profile default`；只审框架公开组件使用 `--profile framework-core`。后者排除 example/doc 与 examples 导向条目，主干条目中 examples 路径也按原规则过滤，不表示示例从仓库消失。

```powershell
python -m nsgablack catalog search "贝叶斯引导" --profile default
python -m nsgablack catalog show tool.bo_acquisition --profile default
python -m nsgablack catalog show tool.unit_binding --profile framework-core
```

装配说明需要区分三种事情：

- 说明／模板：还包含需要用户填写的依赖，或只是操作提示。
- `signature-checked`：片段语法与组件构造签名可绑定；不代表已经执行完整 Case。
- 运行结果：必须另看对应测试、Case 的实际产物、执行记录与 commit。Catalog 不把源码中的说明文字升级成通过记录。

即使 Case 有行为测试，也不等于该算法已经证明收敛或优于其他实现。当前算法验收边界见 [三种算法的语义验收](ALGORITHM_SEMANTIC_ACCEPTANCE_CN.md)。

字段来自同一份 TOML contract；Python 查询、CLI、Dashboard、数据库 materialization 与生成文档应消费同一解释。索引是否过期由现有 fingerprint/读取路由检查，不能用“服务器能打开页面”替代内容和版本一致性。

## 5. 本地使用

```powershell
python -m nsgablack catalog ui --profile default --kind all --source-mode off --host 127.0.0.1 --port 8615 --headless
```

浏览器访问 `http://127.0.0.1:8615`。顶部直接搜索名称或用途，也可点“贝叶斯优化”“GA + VNS 编排”“解池操作”“扩展 Unit”。左侧选择目录范围与分类，展开字段筛选后可用“相关概念”和“职责”继续缩小结果。概念可以跨 kind 查找，既有分类与导入路径保持有效。

中间表格单击选择组件，右侧先给出用途与可复制的最小接线，再展示方法、装配参数、支持边界和配方结构状态；非空 Context／Artifact／phase 声明收进“契约与依赖”。“关系”和“来源”保留导航、返回栈与链接。概念／职责筛选写入原有 deep-link，刷新后恢复。`off` 使用源码索引，不读取数据库。

排序、列方案、显示窗口和结果折叠在侧栏“显示设置”；列表底部“显示更多组件”可扩展窗口，不再把全部目录硬截为 250 项。本地连接设置位于“数据源与项目”；服务器只读版固定框架来源，不显示不可用的路径和数据库控件。

`companions` 是导航关系；`required_companions` 只认显式依赖声明，不再从所有关联项推断“必须同时装配”。源码 quick-add 更新摘要时，未显式修改的 contract、metadata、Artifact／phase 声明继续保留；显式 `contract={}` 才清空它。

详情文件中的声明先合并，再执行 profile 过滤、装配说明生成、同步和摘要计算。源摘要 schema 为 `nsgablack.catalog.source.v3`，包含完整 contract 与语义 metadata。修改外部详情后须 refresh／reload Catalog；旧摘要不能被视为当前来源的新鲜缓存。数据库 `only` 仍以已发布数据库为准，`prefer` 校验其来源摘要。

### 联合 ML 目录

安装 mlblack 后，可在服务端显式选择其公开目录：

```powershell
$env:NSGABLACK_CATALOG_PROVIDERS='mlblack=mlblack.catalog.registry:get_catalog'
python -m nsgablack catalog ui --profile default --kind all --source-mode off
```

原生组件 key 不变；ML 组件以 `mlblack.` 为前缀，例如 `mlblack.codec.linear_point`、`mlblack.integration.learning_solver`。名称、原始 kind、契约、模型布局和用法仍归 mlblack 定义，关联链接一起转换；页面来源标记读取 `metadata.catalog_framework`，原 key 保存在 `metadata.catalog_original_key`。可以直接搜索 LinearPointCodec、NeuralGraphCodec 或 LearningSolver，并在 Codec、Head、数据视图、模型、Trainer 等分类浏览。

这不是把 Codec 当作 Unit，也不是把训练过程当作 Bias。联合的是可发现性入口，语义和装配仍由所属框架决定；ML 未声明的接线保持未验证，不套用优化组件的配方。已配置的来源加载失败会阻止发布，避免静默漏掉半套目录；未配置来源时，nsgablack 仍能独立使用。

数据库部署将联合全集一次物化，再核对两个 profile 的完整摘要。不能先同步 NSGA 再同步 ML：每次发布会清理不在本次全集内的条目。migration 10 增加语义 metadata 字段，须由 writer 在网页升级前迁移；只读网页不会尝试修改表。

侧栏按用途收拢为八组：算法策略、问题与偏好、数据与候选管线、模型与编解码、装配与编排、运行与后端、协议与工具、示例与文档。每组先展示整组组件，再通过组内细分选择原始类型。Codec、Head、Provider等不再是三十多个平铺一级入口。

这些分组只负责导航，不改写组件原始kind、归属、事实摘要或profile过滤。`kind=group:model`等链接是UI范围，旧`kind=codec`链接继续有效；同一范围下列表、搜索与字段筛选遵守相同类型集合，八组并集等于完整profile且互不重复。未知新类型暂归协议与工具，仍能从全部组件找到。framework-core中的示例与文档显示0项，不因此泄露已被profile排除的条目。

## 6. 本次执行验证（2026-10-22）

- Catalog、CLI、作用域、存储、脚手架和编排关联回归：**203 passed**。覆盖两种 profile、配置／方法分离、概念搜索、字段筛选、详情文件同步／摘要、关联补全与 quick-add 不丢契约。
- 浏览器：`python -m pytest tests/test_catalog_dashboard_e2e.py -q`，**3 passed**。使用本地 Streamlit 与无头 Edge，验证页面协议、选择切换、概念筛选、说明展示及链接刷新恢复。
- 根目录严格 Doctor（`--catalog-audit --profile framework-core`）：**0 error / 0 warning**，582 项 completed、106 项 skipped。跳过项没有被计作通过；未对全部 Case 执行 build。
- 三算法标准 Project 在 `default` 与 `framework-core` 各执行 `--strict --build --catalog-audit`：均 **0 error / 0 warning**，各 33 项 completed、0 项 skipped。
- MySQL／PostgreSQL 存储使用本地 SQLite 驱动适配器执行查询、索引与往返测试，迁移验证语句与幂等跳过；**没有连接真实数据库引擎执行迁移**。

本次验证不修改搜索运行语义，不代表任意自定义算法正确、收敛或优于其他实现。这一轮记录的是本地验收；独立服务器预览的打包、访问和受限模式见 [部署说明](../../deployment/catalog/README.md)。


## 7. AI 资料整理

AI 整理属于 Catalog 的可选资料发布能力，不进入 Solver、Adapter 或评估生命周期。它读取公开组件声明、受限源码片段及正式示例，生成中文用途、输入输出、装配思路、注意事项、关联组件和资料缺项。网页展示时固定标明“解释性说明，未进行运行验收”；接口、参数、实际能力和测试结果仍由原来源决定。

侧栏进度按当前profile和数据库实际资料统计，区分待办、过期、完成；后台另显示最近检查时间及退避或暂停原因。浏览与刷新不启动模型；暂停不能因为数量对账而显示为正在运行。当前先复用已有资料、离线列出具体缺项，再决定是否需要小范围付费整理，见 [资料维护说明](../catalog_usage/LOCAL_MATERIAL_MAINTENANCE_CN.md)。AI资料齐全也不表示组件的运行示例全部通过。

事实索引与生成说明分别保存。`catalog_knowledge` 只保存派生资料，身份由组件 key、源码证据摘要、模型和提示版本共同确定；同身份不可改写，历史版本保留。生成说明不会改变 `CatalogEntry` 或 source.v3 的事实摘要。

镜像构建时准备源码证据和 `knowledge-sources.json`。出处有真实文件路径、行号与片段摘要，公开 re-export 静态跟踪到实际声明；不会为整理构造 Unit、执行组件、读取密钥或运行样例。每份资料包有字符和文件大小上限，模型输出须通过字段、既有组件 key 和出处 ID 检查。结构检查不能证明文字的算法语义正确。

首版使用 DeepSeek JSON 输出，服务端凭据只授予独立 writer 任务。网页只有数据库 SELECT 和固定镜像源码索引，不持有 AI key，也不在浏览或搜索时调用模型。没有说明的条目标记待整理；摘要不匹配的旧说明标记过期并隐藏正文；生成失败保留事实索引和已成功的其他说明。

明确执行的增量整理复用精确身份，普通入口默认每批最多20项、并发3。这个上限约束组件尝试数，不是硬金额预算；单项可能包含生成、独立复审、纠正及有限网络重试。后续优先按实际使用缺口选择具体组件，不能为了计数填满而重写已有指南。普通页面刷新不会触发付费请求。

服务器任务与来源核对见 [部署说明](../../deployment/catalog/README.md)。旧 `catalog/ai_assistant.py` 的示例浮窗未接入这套发布流程，不会启动本机5001端口或将浏览器请求发往客户端localhost。

模型输出未通过字段或边界校验时，依据同一冻结证据进行有限纠正；独立复审的格式修正不能丢弃实质问题或改成批准。不放宽接纳规则。已收到的成功响应会合并用量，但失败 HTTP 的完整记账仍有缺口，不能用成功记录代替全部服务端账单。

## 8. 在组件详情中查看使用示例

搜索列表增加“使用示例”状态。打开组件后，概览先展示输入准备、关键装配代码、操作步骤、运行命令、依赖、可改参数与预期输出。完整脚手架通过关联 Project 复用，避免为每个组件再复制一套工程。

- **已运行示例**：存在与当前发布源码、示例命令一致的成功执行收据，单独展示实际输出和运行时间。
- **示例待验证**：已找到源码或声明入口，尚无匹配当前版本的运行收据。预期输出不能作为实际结果。
- **装配片段**：仅有组件声明的接线片段，片段不保证能单独运行。
- **待补示例／入口失效**：缺少示例，或声明入口不能对应当前源码，明确显示缺项。

精讲示例在 `catalog/example_manifests/*.toml` 维护，明确关联真正装配的组件与代码行；现有 `example_entry` 自动关联但保留“来自声明”的区别。索引构建只读公开源码，不导入组件、不构造 Unit。ML 示例按真实 Codec、Head、Problem、Trainer 接线，不借同类组件替代。

部署离线执行白名单小型 Project，保留正式 Project/Case/L0 授权和结果发布路径；不在网页执行用户代码。执行收据绑定源码闭包、完整发布摘要、固定命令、退出码和结果摘要。索引与收据是派生资料，不改变 Catalog 事实、算法状态或原始反馈。它们证明特定配置运行成功，不证明算法数学性质或全部参数组合。

AI 只读取精讲示例的真实静态片段及预期说明，不读取执行收据来宣称验收成功。新增片段可在本地直接盘点与展示，网页继续隐藏已过期 AI 正文；资料过期或计数未满不构成自动付费执行的授权。服务器批量整理目前已停用，新实现的执行边界及上线范围见 [资料维护说明](../catalog_usage/LOCAL_MATERIAL_MAINTENANCE_CN.md)。
