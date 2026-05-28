# 代码机制概念对齐总索引

状态：工作草案  
范围：`nsgablack` 与 `mlblack` 两个框架的主干代码机制。  
目的：逐模块说明“代码里叫什么、社区一般叫什么、你的框架差异点是什么”。

## 阅读方式

这组文档不是 API reference，也不是逐行源码注释。它按机制簇对齐：

1. 先看本文件，理解分组。
2. 看 `01_nsgablack_control_plane.zh-CN.md`，理解优化控制平面。
3. 看 `02_nsgablack_strategy_representation_bias.zh-CN.md`，理解算法策略、候选表示和偏置。
4. 看 `03_nsgablack_runtime_catalog_project.zh-CN.md`，理解运行治理、catalog、doctor、artifact surface。
5. 看 `04_mlblack_learning_flow.zh-CN.md`，理解学习流、schema、trainer、artifact。
6. 看 `05_mlblack_symbolic_and_mechanisms.zh-CN.md`，理解符号学习、机制组件、结构发现。
7. 看 `06_cross_framework_prediction_decision.zh-CN.md`，理解两个框架如何联动。
8. 看 `07_deep_dive_backlog.zh-CN.md`，按任务包继续逐文件深挖。

## 覆盖口径

### nsgablack

| 机制簇 | 代表路径 | 社区大类 |
| --- | --- | --- |
| 控制平面 | `core/blank_solver.py`, `core/composable_solver.py`, `core/evolution_solver.py` | black-box optimization loop, solver orchestration |
| 问题接口 | `core/base.py` | black-box problem, objective/constraint oracle |
| 算法策略 | `adapters/algorithm_adapter.py`, `adapters/*/adapter.py` | search policy, evolutionary operator, optimizer strategy |
| 候选表示 | `representation/base.py`, `representation/*.py` | genotype-phenotype mapping, repair, encoding |
| 偏置系统 | `bias/core/*`, `bias/domain/*`, `bias/algorithmic/*`, `bias/surrogate/*` | inductive bias, prior, heuristic guidance |
| 插件能力 | `plugins/base.py`, `plugins/runtime/*`, `plugins/evaluation/*`, `plugins/ops/*` | callbacks, middleware, lifecycle extension |
| 嵌套求解 | `core/nested_solver.py`, `plugins/solver_backends/*` | nested optimization, backend bridge, inner evaluator |
| 状态面 | `core/state/*`, `utils/context/*` | runtime state, snapshot store, lineage reference |
| Catalog/Doctor | `catalog/*`, `project/doctor*` | component registry, discoverability, structural lint |

### mlblack

| 机制簇 | 代表路径 | 社区大类 |
| --- | --- | --- |
| 训练流 | `core/orchestration/workflow.py`, `workflow/orchestrator.py` | ML workflow, staged experiment |
| 装配配置 | `config/assembly.py`, `config/registry.py`, `config/defaults.py` | component registry, declarative assembly |
| Schema/Numericizer | `schema/*`, `numericizer/*` | data schema, feature encoder, semantic-to-numeric layer |
| Pipeline | `pipeline/*` | preprocessing, feature transformation, representation pipeline |
| Trainer family | `core/common/base_trainer.py`, `core/*/trainer_family.py`, `core/trainers/*` | estimator, learner, model family |
| Artifact | `core/artifacts/*` | model artifact, fitted estimator, deployable predictor |
| Capability/Plugin | `core/orchestration/capabilities.py`, `plugins/*` | callback, lifecycle capability, side-effect plugin |
| Symbolic stack | `core/symbolic/*`, `core/symbolic/feature_space/*` | symbolic regression, basis discovery, program search |
| Execution/Resource | `core/execution/*` | resource context, execution backend, budgeted training |
| Experiment/Catalog | `experiment/*`, `catalog/*` | experiment tracking, catalog UI, registry surface |

## 对齐原则

| 原则 | 含义 |
| --- | --- |
| 不按算法名堆砌 | 优先解释机制所在的架构层，而不是只说“这是某算法实现”。 |
| 不把你的命名强行翻译成一个词 | 很多机制同时对应 ML、optimization、experiment engineering 中的多个概念。 |
| 说明差异点 | 每个机制都要说明它不是普通调包，而是改变了边界、生命周期或组合协议。 |
| 保留你的术语 | 你的术语如 surface、assembly、locked core、evaluation proxy 有价值，但要映射到社区语言。 |
| 为实证服务 | 对齐不是为了好看，而是为了后续写 benchmark、paper、答辩和 README。 |

## 当前粒度

当前版本是“主干机制级对齐”，不是最终逐函数级解释。它已经覆盖两个框架的核心分层，但很多细节机制可以继续按 `07_deep_dive_backlog.zh-CN.md` 分批加深。

## 总体一句话

中文：

> `nsgablack` 把外层搜索、候选表示、评估治理和运行审计框架化；`mlblack` 把内层拟合、代理评估、符号结构发现和 artifact/report 框架化。二者通过 evaluation proxy、resource context、run surface 和 artifact contract 连接，形成预测-决策一体化栈。

英文：

> `nsgablack` provides the outer search, representation, evaluation governance, and runtime audit layer; `mlblack` provides the inner learning, surrogate evaluation, symbolic structure discovery, and artifact/report layer. They connect through evaluation proxies, resource contexts, run surfaces, and artifact contracts.
