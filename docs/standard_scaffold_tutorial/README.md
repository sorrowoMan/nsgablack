# nsgablack 标准脚手架教程

这组文档面向第一次把真实优化问题接入 `nsgablack` 的使用者。目标不是解释某个算法，而是教你按框架语言搭一个可维护、可审计、可继续扩展的优化项目。

`nsgablack` 的第一原则是四层边界清楚：

| 层 | 负责什么 | 标准对象 | 不应该做什么 |
| --- | --- | --- | --- |
| Solver | 生命周期、评估入口、状态读写、插件调度 | `EvolutionSolver`、`ComposableSolver` | 不写具体搜索策略 |
| Adapter | 候选生成与反馈更新 | `AlgorithmAdapter.propose/update` | 不写 checkpoint/report |
| Representation | 候选表示、初始化、变异、修复、编解码 | `RepresentationPipeline` | 不把业务目标藏进 repair |
| Plugin | 运行能力、审计、后端、短路评估、checkpoint | lifecycle hook、evaluation hook | 不重写算法语义 |

最小心智模型：

```text
Spec 保存参数
Registry 保存可选组件
Builder 把 Spec 变成对象
build_solver 选择 key 并挂载
solver.run / evaluate_* 执行
Context/Snapshot/Catalog/Report 负责审计
```

标准装配顺序：

```text
problem
  -> representation pipeline
  -> bias
  -> solver core
  -> adapter / search orchestration
  -> evaluation runtime
  -> runtime profile / L0 backend
  -> flow plugins
  -> ops plugins / observability
  -> checkpoint / state
```

推荐阅读顺序：

1. [00_assembly_api_reference.md](00_assembly_api_reference.md)：全部标准装配 API 速查，包括 solver surface、`group/multi/serial/event/event_case`、资源、context/snapshot。
2. [01_create_and_run.md](01_create_and_run.md)：从 CLI 创建项目，到第一次检查、运行和读结果。
3. [02_component_configuration.md](02_component_configuration.md)：逐层解释每个组件怎么配置、放在哪里、用什么 API 挂载、怎么验收。
4. [03_orchestration_language.md](03_orchestration_language.md)：单策略、多策略、串行阶段、事件驱动、嵌套评估、组件参数外层优化怎么写。
5. [04_validation_catalog_and_evolution.md](04_validation_catalog_and_evolution.md)：doctor、catalog、Run Inspector、snapshot/context 审计、长期扩展检查清单。
6. [05_cross_framework_coordination.md](05_cross_framework_coordination.md)：`nsgablack` outer 与 `mlblack` inner 的职责边界、payload、report 和失败模式。
7. [06_l0_parallel_resource_patterns.md](06_l0_parallel_resource_patterns.md)：L0 task/resource/backend 协议、并行组装、CPU/GPU 资源、Redis worker、artifact/data transport、TTL/heartbeat。
8. [../architecture/L0_RESOURCE_ORCHESTRATION.md](../architecture/L0_RESOURCE_ORCHESTRATION.md)：L0 资源层、GPU lease、SQLiteLeaseStore 和跨框架 `ResourceContext` 注入。

## 标准 API 语言

`nsgablack` 的使用体验应该像一组统一动词，而不是每个模块各写一套入口：

```python
solver.set_adapter(adapter)
solver.set_representation_pipeline(pipeline)
solver.add_plugin(plugin)
solver.evaluate_individual(x)
solver.evaluate_population(population)
solver.write_population_snapshot(population, objectives, violations)
solver.read_snapshot(snapshot_key)
solver.set_context_store(store)
solver.set_snapshot_store(store)
```

这组动词就是标准装配语言。项目侧尽量通过这些 API 挂载组件，而不是在 example 文件里绕过主干流程。

## 正式 case 落点

正式 example、benchmark、cross-framework case 应放在：

```text
examples/cases/<case>/
```

`my_project/` 只作为 starter template、reference skeleton、compatibility layer 或用户私有孵化位。不要把完整实验脚手架长期塞进 `my_project/`。

## 和 mlblack 的分工

| 框架 | 负责范围 |
| --- | --- |
| `nsgablack` | 外层优化、候选生成、Pareto/frontier、多策略、多 solver、outer budget、嵌套评估触发 |
| `mlblack` | 内层学习/评估代理、数据数值化、trainer family、artifact、metrics、flow report |

跨框架时，`nsgablack` 注入外层资源上下文和评估预算，`mlblack` 在内层消费该上下文。不要在 example 文件里私下写死 GPU、线程数、trainer 后端或路径。
