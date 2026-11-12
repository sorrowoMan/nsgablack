# Catalog 全组件用法审阅与修复记录

日期：2026-10-26。口径为启用 ML 公共 provider 的 framework scope；同时核对 `default` 与 `framework-core`。源码、用法卡、组件调用检查、正式 Project 执行收据分别记录，不互相代替。

## 用法可读性与关系修复（同日后续）

用户实际阅读后发现，字段非空的用法仍可能缺少可照做的说明。复核发现：280条NSGA manifest仅有6种inputs，222条首个输出是同一句泛化文字；ML 277项的顶层关系字段大量缺失，其中已有显式契约未公开到统一字段。这些问题使“片段存在”的覆盖检查不足以说明上手体验。

- 重写20个重点用法节，包括NSGA-II、VNS、MOEA/D、BO、固定候选、UnitBinding、PopulationUnit、Pool、两种高斯变化、Bias、MonteCarlo/Pareto插件，以及ML数据、Codec、Representation和LearningSolver。每节写明输入、文件落点、接入步骤和具体检查方法。其它片段解释可识别的外部变量来源；仍缺具体前提或检查方法时明确标注待补充。
- 页面默认先显示准备和装配位置，再给代码与接入步骤；通用Project起步说明、完整Project及运行收据保留独立折叠入口。只读教学展示没有新增在线试跑。
- 538条文档manifest改用组件章节锚点，插入新说明不会使后续组件引用错误行段。构建后仍记录精确实际行号、源文件与片段摘要；输入/步骤/输出从同一正文解析，不让旧泛化元数据遮住具体说明。
- ML所属registry规范投影显式context/artifact/phase声明，保留原始contract；描述字典及普通backend provides不猜作上下文。另修正MonteCarlo参数与RiskBias真实输入说明及可选配套关系。
- 用法关系只从显式导入与实际调用、静态导出链和已核对专属文档建立，双向显示来源位置；不把仅导入、名称相似或代码同现当强制依赖。源码和数据库查询共用同一解释，遵守profile边界。
- 最终source统计：default 557项中368项已有某类可追溯关系，framework-core 495项中366项；真实用法调用有353对组件关系，共享契约有664条有向键关系。尚有129项主干条目未找到此范围内的关系证据，不能据此断言不可组合，也不填造关联。
- 本地338项相关回归、ML所属7项投影测试、20个教学页展示检查通过；严格Doctor为0 error/0 warning、214 info，未启用`--build`。修前/修后静态清单、验证和边界记录位于`.pytest_cache/catalog-usage-relations-20261026/`。

完整入门路线见[第一次装配](CATALOG_FIRST_ASSEMBLY_CN.md)。下面保留上一阶段的来源覆盖记录，其中“有专门用法”只表示有绑定片段，不表示每条都已达到本节教学标准。

## 覆盖结论

审阅前真实目录为 default 558 项、framework-core 496 项。旧示例索引只收录 532 个 TOML 声明，漏掉 26 个动态 ML backend/capability；286 项没有示例关联，真正带输入、步骤、代码和预期结果的用法只覆盖 24 个组件。另有 222 项的既有装配片段被泛导航引用遮住。

本轮移除了一个没有实现的重复旧索引：`mlblack.nsgablack_symbolic.symbolic_basis_artifact`，现用 `mlblack.nsgablack_symbolic.orthogonal_basis_set_artifact`。当前有效目录为：

- default **557 项，557 项有专门用法**。
- framework-core **495 项，495 项有专门用法**。
- 合计 627 个示例记录：622 个源码绑定记录、5 个本次镜像实际重跑成功的正式示例记录；0 个失效源引用、0 个未核查记录。

组件与示例不是一一对应：同一真实实现的语义别名可共享片段，一个正式 Project 也可确实装配多个组件。5 个正式执行记录只覆盖对应的 24 个组件，不能据此宣称 557 项都完成训练或完整 Solver 验证。

逐组件正文见 [使用说明](CATALOG_COMPONENT_EXAMPLES_CN.md)及其三份分册。逐 key 的审阅与覆盖清单保存在 `.pytest_cache/catalog-component-examples-20261026/` 的 `exhaustive-audit.json`（修复前）、`final-audit.json`（修复后）和三组 `*-review.json`；可按指南重新生成全量审计。

## 内容与实现修正

- nsgablack 全部 280 项有用法卡，包含 225 个装配／回调片段、41 个文档角色和 14 个正式 Project 角色。修正 174 条原声明，并纠正最后一处占位 checkpoint 入口；修正内容包含必需参数、泛导航、Provider 的 `create_provider` 名称和 MonteCarlo 的 `mc_samples` 参数。
- ML 数据／Head／Codec／模型／管线／preset 等 140 项有 121 个片段。Estimator 显式提供 factory，时序窗口与未来目标分开，非 MLP 后端说明 Trainer/L0 前提，外部存储写明连接依赖。
- ML 其余 137 项包含 26 个动态后端条目。修正诊断工厂 import，以及 6 个 traffic 示例的全限定正式 `build_solver` 入口；不添加伪兼容函数。
- 三个 surrogate control 工具返回控制更新映射，当前没有正式自动消费者。目录不再把它们当标量评分 Bias，旧的 `bias_module.add(control)` 示例已替换为明确的 `apply(context)` 用法。
- 实测发现普通 callable Bias 注册走不存在的 `RuleBasedBias(rule_func=...)` 参数。已改为正式 `CallableBias`，并拒绝将已知控制映射对象装进标量评分链；行为检查验证权重、上下文、奖励和原始目标不被修改。
- 多行代码的缩进曾在共享 TOML loader、usage 富化、detail overlay 及页面 fallback 中丢失。代码字段现在保留缩进和空白行；标签与分类值仍按原规则规范化。显式装配片段不会被第二份内置 recipe 覆盖。
- Markdown 示例按正文与 Python 围栏排版；只有泛入口时仍显示组件自身装配片段。一般脚手架说明不再伪装成“以 .md 结尾的一整句路径”。

## 检查范围

全量回归 **338 passed**，包含所有当前组件的 source index、用法完整性与语法、逐项页面渲染、SQL 语义往返、CLI、正式 recipe、Bias／接纳与 Snapshot 回归。共享 BlackBase loader 的另外 **8 项测试通过**。根 strict Doctor/catalog audit 为 0 error、0 warning、214 info，不是全 Case build。

分组检查的数字有重叠，不相加成总测试数：

- nsgablack：460 次导入／调用签名检查、125 个装配检查、28 个纯值／结构操作检查；未因此生成完整 Solver `executed` 收据。
- ML 第一组：121 项片段检查通过，其中 103 个实际组件调用、14 个 preset 仅构造、4 个涉及外部／可选环境的记录仅静态检查；未启动训练。
- ML 第二组：137 段语法及 import、203 个直接调用签名、87 个方法签名；42 个轻量 CPU 片段实际通过，95 个需要 Case 输入或可选环境的片段仅静态与接口核对。
- 镜像构建通过正式 Project 重跑 GA、VNS、MOEA/D 池工作流、ML 线性回归、Risk Bias 五个示例；不是任意执行目录里的命令。
- 最终候选及正式页面各对实际 MySQL 双 profile 进行 18 次 AppTest，覆盖既有运行收据，以及新补的 A*、控制映射、ML Problem 和动态 backend 用法；浏览示例时模型调用、Unit 构建、Solver 运行均为零。

所有示例由当前接口与真实源码整理，本轮没有调用 DeepSeek API 自动生成或虚构运行结果。

## 尚未被这轮证明的事

可选 JAX/Torch/外部数据源、完整训练和所有长预算算法没有逐项运行；卡片逐项列出前提。控制映射工具有独立用法，不等于已经接上自动控制消费者。

另发现当前机器上旧 SymbolicPathMemory SQLite 文件缺少 `total_delta_score` 列。本轮用隔离临时数据库验证当前组件，不对该旧库进行迁移；旧持久数据的迁移问题单列，不能被“示例已补齐”掩盖。

## 发布保护

发布构建必须用正式 Catalog 快照包含动态条目；新增组件若没有完整用法卡会使构建失败。发布后再用实际数据库逐项核对，避免只检查五个代表条目。

更新前已只读备份独立 Catalog 库 12 张表、15,129 行到服务器私有目录 `/opt/framework-catalog/backups/20261026T022922Z-component-examples/`。网页仍只用原 reader 授权；同步使用短期 writer 进程，不把 writer 或模型凭据交给网页。仅 simon 可见的原网关规则保留，原 AI 账本不清零。

正式镜像为 `nsgablack-catalog:component-examples-6af22cfabd97`，发布目录为 `/opt/framework-catalog/releases/20261026T025647Z-component-examples-6af22cfabd97`。reader、AI、worker 均 healthy、restart_count=0；账本保留 32 条预留。原网关 ID 与本轮切换前一致，其他既有容器 ID 无变化；匿名普通入口401、可信未绑定入口403。这里没有声称重新完成真实 simon 浏览器会话确认。

正式页面 default 显示 519 个“用法示例”、24 个“已运行示例”、14 个有正式入口但尚无本版执行收据的“示例待验证”；framework-core 显示 471 个“用法示例”和24个“已运行示例”，没有缺例条目。新组件若缺输入、步骤、依赖或预期输出，后续构建会直接失败，避免覆盖再次漂移。
