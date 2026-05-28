# nsgablack 组件导读索引

这组 guide 用来回答“这个机制应该放在哪一层”。它不是 API 参考，也不是完整教程，而是组件边界、职责拆分和标准脚手架阅读路径的索引。

如果只想快速搭项目，先看 `docs/standard_scaffold_tutorial/README.md`。如果你在判断一个功能到底应该写进 `Adapter`、`RepresentationPipeline`、`Problem`、`Bias` 还是 `Plugin`，先看本页。

## 1. 当前架构组件索引

| 组件 | 一句话定义 | 负责什么 | 不负责什么 | 详解入口 |
| --- | --- | --- | --- | --- |
| Solver | 控制平面 | 生命周期、评估入口、插件调度、context/snapshot 访问 | 具体搜索策略 | `../standard_scaffold_tutorial/02_component_configuration.md` |
| Problem | 目标与约束平面 | `evaluate`、`evaluate_constraints`、outer objective/violation 投影 | 候选生成、可行性修复、并行调度 | `DECOUPLING_PROBLEM.md` |
| RepresentationPipeline | 候选表示平面 | init、mutate、repair、encode、decode、bounds、typed genome | objective 公式、搜索策略、报告副作用 | `DECOUPLING_REPRESENTATION.md` |
| Adapter | 搜索策略平面 | `propose/update`、策略状态、候选来源 | 硬约束、业务评估、checkpoint/report | `DECOUPLING_ADAPTER.md` |
| Bias | 软引导平面 | domain prior、seed、软偏好、候选倾向 | 硬约束替代、业务目标替代 | `DECOUPLING_BIAS.md` |
| Plugin | 能力平面 | trace、checkpoint、event signal、短路评估、report、backend、监控 | 改写搜索算法语义 | `DECOUPLING_CAPABILITIES.md` |
| L0 Resource | 资源与并行平面 | CPU/thread/GPU/device token、lease、heartbeat、ResourceContext | trainer 业务逻辑、objective 公式 | `../standard_scaffold_tutorial/06_l0_parallel_resource_patterns.md` |
| ContextStore | 轻量运行状态 | generation、signal、snapshot ref、轻量 key | population/history/artifact 大对象 | `../standard_scaffold_tutorial/04_validation_catalog_and_evolution.md` |
| SnapshotStore | 大对象引用层 | population、objectives、trace、artifact、frontier 大对象 | 高频轻量 signal | `../standard_scaffold_tutorial/04_validation_catalog_and_evolution.md` |
| Catalog | 可发现性索引 | 组件 key、kind、mount point、contract、profile | 运行时调度 | `../standard_scaffold_tutorial/04_validation_catalog_and_evolution.md` |
| Run Inspector | 装配审计入口 | 查看 solver/problem/pipeline/adapter/plugin/resource wiring | 代替测试或 doctor | `../standard_scaffold_tutorial/04_validation_catalog_and_evolution.md` |
| Inner Bridge | 嵌套评估桥 | outer candidate -> inner task -> inner result -> outer objective | inner solver 私有实现 | `../standard_scaffold_tutorial/03_orchestration_language.md` |

## 2. 旧 guide 如何对齐当前标准脚手架

`DECOUPLING_*` 系列是较早期写的组件边界文档，核心思想仍然有效；现在应把它们理解成标准脚手架教程的“边界解释层”。

| 旧 guide | 当前对应层 | 现在主要配合阅读 |
| --- | --- | --- |
| `DECOUPLING_ADAPTER.md` | Adapter / strategy plane | `../standard_scaffold_tutorial/03_orchestration_language.md` |
| `DECOUPLING_REPRESENTATION.md` | RepresentationPipeline / typed genome | `../standard_scaffold_tutorial/02_component_configuration.md` |
| `DECOUPLING_PROBLEM.md` | Problem / evaluation projection | `../standard_scaffold_tutorial/02_component_configuration.md` 和 `../standard_scaffold_tutorial/05_cross_framework_coordination.md` |
| `DECOUPLING_BIAS.md` | Bias / soft guidance | `../standard_scaffold_tutorial/02_component_configuration.md` |
| `DECOUPLING_CAPABILITIES.md` | Plugin / capability / wiring | `../standard_scaffold_tutorial/03_orchestration_language.md` 和 `../standard_scaffold_tutorial/04_validation_catalog_and_evolution.md` |
| `PRODUCTION_SCHEDULING_WALKTHROUGH.md` | 早期端到端案例说明 | 适合作为“为什么先 pipeline、再 bias、再 adapter”的叙事例子 |

## 3. 常见问题应该看哪里

| 问题 | 先看 |
| --- | --- |
| 什么是 pipeline，为什么硬约束优先放 pipeline | `DECOUPLING_REPRESENTATION.md` |
| 为什么 adapter 只做 propose/update | `DECOUPLING_ADAPTER.md` |
| problem 为什么不负责 repair 或并行 | `DECOUPLING_PROBLEM.md` |
| bias 和 constraint 有什么区别 | `DECOUPLING_BIAS.md` |
| plugin 为什么适合写 event signal | `DECOUPLING_CAPABILITIES.md` |
| event strategy 怎么读取多个插件信号 | `../standard_scaffold_tutorial/03_orchestration_language.md` |
| nested inner solver 为什么也是完整 scaffold | `../standard_scaffold_tutorial/03_orchestration_language.md` |
| GPU lease、ResourceContext、heartbeat 怎么分层 | `../standard_scaffold_tutorial/06_l0_parallel_resource_patterns.md` |
| 如何验证新增组件没有破坏边界 | `../standard_scaffold_tutorial/04_validation_catalog_and_evolution.md` |

## 4. nsgablack 与 mlblack 同名词提醒

跨框架时最容易混淆的是同名词。

| 词 | nsgablack 中的含义 | mlblack 中的含义 |
| --- | --- | --- |
| pipeline | 候选解表示管线，负责 init/mutate/repair/encode/decode | 数据/特征表示管线，负责 zscore、orthogonal、learnable operator 等 |
| adapter | 优化搜索策略，负责 propose/update | 无直接等价；不要把 mlblack trainer 叫 adapter |
| plugin | solver 生命周期能力、event、checkpoint、report、短路评估 | flow capability，负责训练流程生命周期副作用 |
| problem | outer objective/constraint evaluator | problem/evaluation proxy 或数据任务定义的一部分 |
| ResourceContext | outer solver 或 evaluation 的资源授权 | inner flow/trainer 消费的资源上下文 |
| component_overrides | outer genome 解码后的内层组件参数 | flow/trainer/pipeline/capability 的可审计覆盖参数 |

跨框架文档见 `../standard_scaffold_tutorial/05_cross_framework_coordination.md`。

## 5. 新增机制落点速查

| 如果你要做的事是 | 优先落点 |
| --- | --- |
| 改候选怎么生成 | Adapter |
| 改候选是否合法、怎么修复 | RepresentationPipeline |
| 改目标和约束 | Problem |
| 加先验、seed、偏好 | Bias |
| 加 trace、checkpoint、event signal、report | Plugin |
| 加 CPU/GPU/并行/lease | L0 Resource |
| 外层控制内层参数 | Representation decode + component_overrides + bridge |
| 同时跑多个 solver profile | Solver orchestration |
| inner 也是完整优化器 | nested solver scaffold |

如果一个新文件同时做三件以上事情，通常说明组件边界已经混在一起，应先拆回上面的层级。
