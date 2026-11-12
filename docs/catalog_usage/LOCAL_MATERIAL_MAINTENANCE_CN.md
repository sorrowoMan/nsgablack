# Catalog 资料维护：先复用，再补缺口

更新时间：2026-10-27。

查看目录、搜索、刷新和本地资料盘点不应消耗模型额度。已有源码用法和数据库 AI 说明先复用；需要改进的是具体缺项，不是为了把 AI 计数填满而重新生成全部组件。

服务器的 `framework-catalog-curation.timer` 已停止并取消开机启用，整理 service 与专用整理 worker 均未运行。已保存的说明仍可读取。下述执行保护的线上版本以 [部署记录](../../deployment/catalog/DEPLOYED_CN.md) 为准；本地测试通过与服务器发布分别验收。

## 1. 哪些资料可以直接用

来源指南、AI 说明、运行收据是三个独立维度：

- 完整来源指南可以直接展示和照着核对，不需要先经模型改写才有价值。
- AI 说明复用其精确条目、来源摘要、模型和规则版本对应的缓存；新来源有冲突时不能沿用为当前事实。
- 静态片段不等于完整教程。应明确缺少的输入准备、装配位置、调用步骤或结果读法。
- 运行成功必须有匹配版本与命令的收据。代码可解析、来源相同或 AI 审核通过都不能替代运行证明。

页面主概览按“详细用法、迁移说明、导航、待补资料”分别计数，明确写为全部索引的范围。
迁移说明用于交代当前限制及替代接线，导航用于找到文档或项目入口；这两类不计为详细教程，也不表示相应组件已经可直接装配。
未知资料类别计入待补，不能显示为已经完善。

AI 缓存与后台状态位于默认收起的“资料维护详情”，按当前目录范围列出“可复用、已过期、未生成、校验未通过”，
不再用缓存命中率作为资料完成进度。未登记范围与空范围各自说明，不回退成全部索引。
源码或规则变化后，旧记录仍保留，但只有匹配当前来源和审核规则的内容才可复用；浏览或刷新不会启动生成。

首次冻结盘点的本地索引含 557 项：47 项有主例和实质变体，14 项有完整主例，441 项只有来源片段，另外 55 项是文档或 Project/Case 导航。174 项片段中的前提或结果说明仍含占位内容。这是改进前的索引快照；后续新增资料的数量以重新生成的 plan 为准，不表示全部组件已经完善。

### 2026-10-27：剩余313项的完整核对

此次从上一批的313项来源片段继续，全部直接读取本地源码编写，没有请求DeepSeek或其它外部模型。新增38本中文用法材料、107条聚焦示例记录；同一完整Case可绑定它实际消费的多个组件，不机械复制107个运行循环。

313项中，246项补成有完整装配与实质变体的用法，67项补成明确迁移说明。后者揭示的是旧类空实现、隐式重新求值、未闭合的模型/Artifact恢复或生命周期/资源接线等真实问题；它们不算原组件已修复，也不能标成可直接装配。迁移页给出实际入口、限制、已有替代用法及还需补的实现。

当前本地557项索引的实际分类为：422项带变体的详细用法、13项完整主例、67项迁移说明、41项文档导航、14项Project/Case导航。来源片段0项、缺少来源0项、占位字段0项。framework-core仍为495项。完整字段只证明资料结构与源码绑定，不证明数学性质或运行结果。

关键用法入口：

- [Unit成员字段、派生特征与只读输入](UNIT_MEMBER_INPUT_APPLICATIONS_CN.md)，以及[不同算法的真实UnitBinding](UNIT_BINDING_FAMILIES_APPLICATIONS_CN.md)。
- [候选变化、问题修复与Unit修复](CANDIDATE_FLOW_APPLICATIONS_CN.md)，[PreferenceDelta与方向投影](CORE_PREFERENCE_PROJECTION_APPLICATIONS_CN.md)。
- [角色、事件、精英组合](ORCHESTRATION_ADAPTER_APPLICATIONS_CN.md)，[PoolSearch与PoolTask接线](ORCHESTRATION_POOL_TASK_APPLICATIONS_CN.md)。
- [控制面状态、参与者和正式结果准备](CONTROL_STATE_APPLICATIONS_CN.md)，[上下文、Redis、交互信号和并行工具](RUNTIME_UTILITY_APPLICATIONS_CN.md)。
- [神经表格Case](ML_NEURAL_TABULAR_APPLICATIONS_CN.md)、[时序模型](ML_NEURAL_TEMPORAL_APPLICATIONS_CN.md)、[文本与视觉输入](ML_NEURAL_TEXT_VISION_APPLICATIONS_CN.md)、[本地预训练模型边界](ML_NEURAL_PRETRAINED_APPLICATIONS_CN.md)。
- [传统估计器](ML_CLASSICAL_ESTIMATOR_APPLICATIONS_CN.md)、[预测模型](ML_CLASSICAL_FORECAST_APPLICATIONS_CN.md)、[单次诊断和配置消费](ML_DIAGNOSTIC_SCHEMA_APPLICATIONS_CN.md)。
- [符号、正交模型](ML_SYMBOLIC_ORTHOGONAL_APPLICATIONS_CN.md)、[条件模型](ML_CONDITIONAL_APPLICATIONS_CN.md)、[ML正式桥与完整子Case](ML_FRAMEWORK_BRIDGE_APPLICATIONS_CN.md)。
- [ML目录数据库、网页和离线导出](ML_CATALOG_SERVICE_APPLICATIONS_CN.md)，[旧交通诊断的科学与资源边界](ML_TRAFFIC_DIAGNOSTIC_BOUNDARIES_CN.md)。

本次同时撤下37个旧Bias和5个旧Plugin卡片的失效挂载代码；原5个多样性迁移卡片继续使用原来的唯一指导注入，不另建第二套来源。目录显式区分详细用法、迁移说明和运行收据；页面另外展示整个来源索引的覆盖数量，不把手写资料冒充数据库AI审核记录。MLBlack原生目录网页摘要函数的错误调用也已修正并用隔离测试核对。

针对性检查共515项通过，包含新用法的源码完整性、Python语法、已知API、迁移卡片、索引和页面规则；MLBlack摘要接口另有1项回归检查通过。严格framework-core Doctor源码审计0错误/0警告，未构建求解器。Unit成员主例另外在独立正式Project副本通过`--check --build-check`，只检查装配与L0绑定，未执行搜索；其余本轮新Case没有运行算法、训练、外部数据服务或外部数据库。

另抽查30个实际Streamlit组件页面，核对对应主例/迁移材料、来源覆盖计数和无渲染异常；浏览时拦截模型发送口，确认调用0次。本地预览健康检查返回200。

资料索引与逐项账本位于本地`.pytest_cache/catalog-offline-20261027/`，是可重新生成的维护产物。离线整理收尾时更新到了本地8632预览；之后的服务器发布单独记录在[部署记录](../../deployment/catalog/DEPLOYED_CN.md)。服务器AI缓存计数不会因源码文档完成而自动增加，也无需为填满那个计数再调用模型。

## 2. 只在本地生成缺口清单

已经有示例索引时，无需重新构建，直接运行：

```powershell
python -m nsgablack.catalog.material_plan --input .catalog/examples.json --output .catalog/material-plan.json
```

其中 `.catalog/examples.json` 是实际导出的示例索引路径。若尚无索引，可使用现有静态构建入口：

```powershell
python -m nsgablack.catalog.examples build --root nsgablack=C:/Users/hp/Desktop/nsgablack --root blackbase=C:/Users/hp/Desktop/blackbase --root mlblack=C:/Users/hp/Desktop/mlblack --index .catalog/examples.json
```

完整发布使用的动态 provider 条目须同时提供同版公开 Catalog 快照 `--catalog-json`；没有它时，上述命令只盘点所提供仓库的静态声明，不保证与服务器的条目总数一致。已有的同版运行收据也只通过正式索引构建入口导入，不自行补写“已执行”。

可选地把已经导出的 AI 记录一起盘点：

```powershell
python -m nsgablack.catalog.material_plan --input .catalog/examples.json --ai-records .catalog/ai-records.json --output .catalog/material-plan.json
```

不提供 `--output` 时，工具只向标准输出打印 JSON。它不会连接模型或数据库，不导入组件，不执行教程代码，也不会把资料写成新的 AI 审核记录。

清单逐条保留选中来源、代码范围、声明摘要与缺项。`fields` 给出可复用文字和占位文字，`gaps` 标出待补字段，`proof` 区分来源声明与执行证据。AI 导出记录的共享文件摘要相同，只能证明共享部分相符，不能证明完整生成 packet 仍为当前版本。

字符数和 UTF-8 字节数是真实输入规模，不是 token 数或金额估算。共享片段按每个条目计入，汇总可能重复计算。

## 3. 如何按缺口完善

先处理用户确实用不起来的条目：缺输入和装配位置、只给对象名而没有对象来源、结果只有“得到组件”等。每个主例至少说明：从哪个正式 Case 开始、修改哪些完整文件、如何接线、怎样运行、从什么字段读出结果。变体需说明修改位置、影响及限制。

本轮新增的例子是 [有限差分方向精修](FINITE_DIFFERENCE_APPLICATION_CN.md)：复用现有正式 Project，给出配置、薄 builder、结果观察器、运行入口和全部方向变体。它目前经过静态源码核对，没有新增运行收据。

后续按具体缺口补充了以下应用，均沿用正式 Project，并区分来源核对与实际运行：

- [候选算子](CANDIDATE_OPERATOR_APPLICATIONS_CN.md)：多项式变异、SBX 交叉和并行问题修复，明确实际消费位置与操作顺序。
- [观察插件](OBSERVABILITY_PLUGIN_APPLICATIONS_CN.md)：内存、基准 CSV/JSON、调用序列图和运行结构跟踪，给出真实文件/字段读法。
- [Unit 多样性偏好](POPULATION_PREFERENCE_APPLICATIONS_CN.md)：显式绑定实际种群，同时说明五个旧多样性类尚未完成的迁移边界。
- [Pool 回调](POOL_CALLBACK_APPLICATION_CN.md)：双后代变化、接纳后输出与最终成员归档共用一份完整接线，并给出接纳历史归档变体。
- [单轨迹步长适应](ADAPTIVE_TRAJECTORY_APPLICATION_CN.md)：让 sigma 真正进入变异，分别读取当前点、历史最好和交付引用。
- [BO／CMA-ES／MAP-Elites 的组件接线](ALGORITHM_COMPONENT_APPLICATIONS_CN.md)：实际装配模型、采集、采样、排序、分布更新、描述符、档案和发射器。
- [ML 时序与概率输出](ML_FORECASTING_APPLICATIONS_CN.md)：时间切分、滚动起点、概率 Head 的 NLL，以及正式 Artifact 蓝图交付。
- [ML 异质输入](ML_STRUCTURED_INPUT_APPLICATIONS_CN.md)：图像、图和偏好对的实际 DataView、Problem、Provider 与正式 Case 接线。
- [ML 后端契约查询](ML_BACKEND_CONTRACT_APPLICATIONS_CN.md)：读取四后端的能力声明、检查消费者需求并显式选择。22 条 capability 是契约声明，共用查询示例，不表示 22 个独立算法已运行。
- [Pool 选择、父代和精确版本](POOL_SELECTION_APPLICATIONS_CN.md)：一次位置分区交付真实成员与精英副池，替换父代规则，核对 SolutionRef/逻辑时点，并说明保留窗口不能复活已回收值。
- [候选布局](CANDIDATE_LAYOUT_APPLICATIONS_CN.md)：连续单纯形、整数矩阵、二进制边与排列各用真实兼容的来源、变化、修复和 Problem，不把数组布局等同算法 Unit。
- [ML 表格任务](ML_TABULAR_APPLICATIONS_CN.md)：完整接通线性/NumPy MLP 回归、二/多分类和两种区间输出，明确参数块、目标与指标、模型蓝图和正式结果引用。
- [领域软评分](DOMAIN_SOFT_SCORE_APPLICATIONS_CN.md)：四种 Bias 真正加入同一求值链，逐项核对 raw 与选择差值；说明重复加权、规则累加和“hard”惩罚标签的现有实现限制，另给真正硬准入变体。
- [ML 数据准备链](ML_DATA_PIPELINE_APPLICATIONS_CN.md)：训练词表、显式标签编码、选列与缩放、一步时序窗口和实际 Provider 消费的小批调度，不以验证集拟合准备状态。
- [ML 模型组合](ML_MODEL_COMPOSITION_APPLICATIONS_CN.md)：分段路由、冻结预测器的温度校准、两种输入口径的预测整合，保留真实模型块和 Artifact 蓝图。
- [结构化局部搜索](STRUCTURED_LOCAL_SEARCH_APPLICATIONS_CN.md)：多目标权重、非光滑聚合、子空间参考样本和 MAS 代理筛选，区别预测、实际求值、当前中心和已评估最好结果。
- [外部观察](EXTERNAL_OBSERVABILITY_APPLICATIONS_CN.md)：MySQL 的 finishing 单次插入与实际表字段、OpenTelemetry 控制台跨度和导出边界；本轮未连接数据库或 Collector。

这些后续资料由当前协作 AI 直接读本地源码编写与交叉复核，没有启动 DeepSeek 批量整理，也不把它们伪装成数据库 AI 审核记录。四个领域 Bias 的公开参数、最小接线和边界随指南一起校正；完整来源、AI 审核与实际运行继续分别计数。

目录的“详细用法”表示来源具有完整主例字段和可解析代码；“用法片段”仍需补上下文，两者均不等于运行成功。判断与离线盘点共用同一实现，按示例索引版本缓存，不在每行渲染时重新扫描源码。

不应为没有实际使用场景的条目机械添加相同段落，也不应因为已有 47 份完整指南就让模型重新改写这 47 份。

## 4. 付费执行的边界

新的本地实现要求逐层显式授权：

- `DeepSeekGenerator` 默认不发送请求；实际发送须明确传入 `allow_paid_requests=True`。仅配置 Key 不构成执行授权。
- `catalog.curate run` 与部署 `runtime.py curate` 必须同时有 `--execute` 和非空 `--keys`。旧的自动选择待办入口不再默认启动付费。
- `runtime.py sync` 只同步事实，即使设置旧 `NSGABLACK_CATALOG_CURATE_ON_SYNC=1` 也不启动模型。
- `complete_catalog.py` 默认只读本地账本并输出计划，不探测 Docker、不连接数据库、不预留尝试。显式执行后默认只提交一批，扩大范围须另给 `--max-batches`；等待不会刷新这次调用的批数许可。
- `auto_curate.py` 的模型执行和 completion worker 的宿主、容器入口都要求明确执行。旧 timer 命令不会被自动补上授权。

一批仍可含多个组件；单项仍可能有生成、独立复审、格式修正和有限网络重试。因此**一批或一个组件都不是 token/金额硬上限**。完整失败 HTTP 用量记账仍有缺口，已有报告不能当作完整账单。后续如果需要模型补缺，先确定具体组件、必要输入和可接受开销，再运行小范围任务；本轮没有执行这些付费步骤。

这些保护不改变实验台交互式 AI 的独立服务，也不启动或停止其用户请求。
