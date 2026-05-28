# NSGABlack

`nsgablack` 是一个多目标优化工程框架。它的核心不是“再封装一个 NSGA-II”，而是把复杂优化实验拆成可治理的系统：问题定义、候选表示、搜索策略、偏置引导、评估链路、运行状态、审计报告和可发现组件索引。
为什么复杂优化实验会“悄悄退化”，以及我如何试图让它变得可见。

这是一个  **仍在快速演化中的实验性框架** 。

我分享它是为了讨论思想，而不是作为已完成的产品。

算法解构的优化生态框架：把“问题/表示/偏好/策略/工程能力”解耦，让你能更快、更稳地把新点子落地到真实问题上。
它适合处理这类问题：目标不止一个，约束会互相冲突，评估过程可能很贵，策略可能需要多算法协同，运行结果需要可复现、可解释、可回放。

一句话定位：

> `nsgablack` 负责外层 optimization orchestration：候选生成、Pareto/frontier 管理、多策略/多 solver 编排、嵌套评估触发、运行治理与审计。

## 1. 它解决什么问题

复杂优化实验经常不是坏在“算法不会写”，而是坏在系统边界不清：

- 搜索策略、业务规则、可行性修复、日志和 checkpoint 混在一个主循环里。
- 想加多策略、并行、代理评估或内层求解时，只能继续堆 `if/else`。
- 结果变化后，无法判断是 adapter、representation、bias、plugin、inner runtime 还是随机性导致的。
- 组件越来越多，但不知道哪些是主干能力，哪些只是 example 或历史 demo。

`nsgablack` 的设计目标是把这些问题工程化拆开，让一次优化实验至少能回答：

- 这次 problem 的目标和约束是什么？
- 候选解用什么 representation 流转？
- 哪个 adapter 负责 propose/update？
- 哪些 bias 在软引导搜索？
- 评估是否被 provider/plugin 短路？
- population/objectives/violations 写到了哪里？
- 哪些组件真正参与了运行？
- 两次实验结构到底差在哪？

## 2. 当前架构总图

框架主干可以理解为“优化运行内核 + 系统治理面”。核心对象如下：

| 对象 | 主要职责 | 边界 |
| --- | --- | --- |
| `Problem` | 定义目标、约束、bounds、evaluate 语义，也可以挂 `inner_runtime_evaluator` | 不负责搜索策略 |
| `Solver` | 控制平面，负责生命周期、评估入口、状态访问、插件调度、RNG | 不硬塞具体算法策略 |
| `Adapter` | 策略平面，负责 `propose/update`，可替换为 NSGA、DE、VNS、SA、TR、多策略路由等 | 不接管日志、checkpoint、审计 |
| `RepresentationPipeline` | 候选解表示平面，负责 init/mutate/repair/encode/decode | `repair` 只做可行性兜底，不写业务策略 |
| `BiasModule` | 软引导平面，表达领域偏好、算法偏好、surrogate 信号、seed bias | 不替代 objective/constraint |
| `Plugin` | 能力平面，负责并行、统计、短路评估、trace、checkpoint、report、backend、storage | 不改写算法语义 |
| `ContextStore` | 轻量运行状态，保存 canonical key 和 `*_ref` | 不长期保存大对象 |
| `SnapshotStore` | 大对象快照，保存 population/objectives/violations/history/trace 等 | 不承担小字段语义治理 |
| `Catalog` | 组件发现、usage、companions、context contract、profile 过滤 | 不替代源码和测试 |
| `Project Doctor / Run Inspector` | 项目体检、结构审计、差异解释、运行回放 | 不替代正式装配边界 |

标准一代流程是：

```text
adapter.propose(...)
  -> representation init/mutate/repair/encode/decode
  -> evaluate_individual(...) / evaluate_population(...)
  -> adapter.update(...)
  -> plugin lifecycle hooks
  -> context/snapshot persistence
```

## 3. Solver 继承链

当前主干求解器有三层语义：

| 类 | 定位 | 说明 |
| --- | --- | --- |
| `core/blank_solver.py::SolverBase` | 控制底座 | 生命周期、插件调度、context/snapshot、评估入口、RNG；默认不内置优化策略 |
| `core/composable_solver.py::ComposableSolver` | adapter 驱动的 step 编排 | 将候选生成和反馈更新委托给 `AlgorithmAdapter` |
| `core/evolution_solver.py::EvolutionSolver` | 进化式默认实现 | 默认 NSGA-II adapter、Pareto 管理、并行评估、种群代际语义 |

关键 API：

```python
solver.set_adapter(adapter)
solver.evaluate_individual(x)
solver.evaluate_population(population)
solver.write_population_snapshot(population, objectives, violations)
solver.read_snapshot(snapshot_key)
solver.set_context_store(store)
solver.set_snapshot_store(store)
```

## 4. Depth × Breadth 工作流

当前 `nsgablack` 不是只有“横向多算法”，也支持“纵向嵌套评估”。这两件事必须区分。

### 4.1 Depth：层级嵌套

Depth 指 L1/L2/L3 这类嵌套评估链路：

```text
L1 outer optimization
  -> L2 inner evaluation workflow
    -> L3 numerical solver / backend
```

当前推荐口径不是旧的 `InnerSolverPlugin`，而是：

| 组件 | 作用 |
| --- | --- |
| `problem.inner_runtime_evaluator` | 外层 problem 在评估阶段触发内层运行 |
| `TaskInnerRuntimeEvaluator` | 标准内层运行适配器，支持 task/problem/solver/backend 形式 |
| `ContractBridgePlugin` | 把内层结果桥接回外层 context，可跨层写回目标字段 |
| `TimeoutBudgetPlugin` | 限制内层调用次数、总耗时和失败行为，避免嵌套失控 |
| `NewtonSolverProviderPlugin` / `BroydenSolverProviderPlugin` | L3 数值求解能力，可作为评估工具接入 |

最小理解：内层求解是 problem 评估语义的一部分，运行治理和追溯由 plugin 承担。

实际案例可看：

- `examples/cases/supply_adjustment_nested/`
- `examples/cases/mlblack_symbolic_consensus_scaffold/`
- `examples/_misc_examples/nested_three_layer_demo.py`（历史/兼容 demo）

### 4.2 Breadth：同层协同

Breadth 指同一层上的多策略、多 adapter、多 bias、多 plugin 协作。

常见形式：

| 形式 | 说明 |
| --- | --- |
| `StrategyRouterAdapter` | 多策略提案者 + 统一评估 + 统一反馈 |
| `StrategySpec` | 给每个策略声明 name、adapter、weight、enabled |
| `MultiStrategyConfig` | 控制 batch、权重自适应、phase schedule 等 |
| Bias 组合 | 领域偏好 + 算法偏好 + surrogate 信号共同软引导 |
| Plugin 组合 | 缓存、容错、报告、审计、统计、trace 协同工作 |

历史 demo 可看：`examples/_misc_examples/dynamic_multi_strategy_demo.py`。

### 4.3 多 solver 编排不是 adapter 策略

`Solver Orchestration` 管理多套 solver 并行或串行运行。它只做三件事：

- 调度。
- 资源校验。
- 结果汇总。

它不做策略逻辑，也不接管评估。策略仍然属于 adapter，嵌套评估仍然属于 problem-side inner runtime。

资源计算规则中，若外层并行资源为 `a`，每个外层 worker 触发内层资源为 `b`，嵌套总资源上界为：

```text
total = a + a * b
```

超预算应直接报错，不静默降级、不私自排队。

## 5. 评估链路

评估入口有两条：

```python
evaluate_individual(x)
evaluate_population(population)
```

两条路径都可以被插件或 provider 短路，但必须满足契约：

- 单点评估返回合法 objective/violation。
- 批量评估返回数量必须与候选数量对齐。
- 短路逻辑必须显式、可审计。
- Bias apply 在统一评估链中只发生一次，provider 内部不得重复 apply bias。
- 训练代理模型的数据应使用 raw objectives，避免 double-bias。

这条规则对 surrogate provider、近似评估、并行评估尤其重要。

## 6. Context / Snapshot 状态治理

`nsgablack` 明确区分轻量 context 和重型 snapshot。

| 存储面 | 放什么 | 禁止什么 |
| --- | --- | --- |
| `ContextStore` | 轻量字段、canonical key、`snapshot_key`、`population_ref`、`pareto_*_ref` | 长期直接塞 population/objectives/violations/history |
| `SnapshotStore` | population、objectives、violations、history、trace、sequence graph、artifact 等大对象 | 用作散乱小字段存储 |

Context 字段必须走 `core/state/context_keys.py` 的 canonical key。组件通过以下字段声明契约：

```text
context_requires
context_provides
context_mutates
context_cache
context_notes
requires_metrics
```

这些契约会被 Catalog、Doctor、Run Inspector 和 Context 页消费，用来回答：

- 谁提供了这个字段？
- 谁消费了这个字段？
- 谁最后修改了它？
- 哪些组件漏配了 companion？

状态读写原则：

- 读 population/objectives/violations 优先从 snapshot 或 adapter state 读。
- 写回优先走 adapter `set_population*`，再走 `solver.write_population_snapshot(...)`。
- Plugin/Adapter 不应直接写 `solver.population = ...` 等镜像字段。

## 7. Plugin 与 Wiring

Plugin 是能力层，不是策略层。

适合写成 plugin 的能力：

- 并行评估、批处理、线程/进程安全保护。
- Benchmark 输出、progress、summary。
- ModuleReport、bias contribution、structure snapshot。
- 统计信号写回 context，供 signal-driven bias 使用。
- checkpoint、trace、OpenTelemetry、storage、external backend。
- 评估短路 provider、Monte Carlo 评估、Pareto 归档。

不适合写成 plugin 的能力：

- 搜索策略过程，那是 Adapter。
- 硬约束可行化，那是 RepresentationPipeline。
- 业务偏好和软约束，那是 BiasModule。

Wiring 用来解决“容易漏配”的问题。比如某个 adapter 需要特定 representation mutator，某个 signal-driven bias 需要统计插件，某个报告面需要 module report + benchmark harness。Catalog 的 companions 和 usage 字段就是为这个服务。

## 8. Run Inspector：结构审计系统

Run Inspector 不是“画曲线 UI”，而是优化实验的结构审计和差异解释系统。

它可以在运行前和运行后回答：

- 当前 solver 装了哪些 adapter、pipeline、bias、plugin？
- 哪些组件可启用/禁用，哪些是固定项？
- 有哪些 missing companions？
- 两次运行的 structure hash 是否相同？
- 两次实验到底差在哪？
- 调用了哪些组件路径？有没有短路或分支？
- context 字段由谁提供、谁消费、谁最后写入？
- Project Doctor strict 下还有哪些契约问题？

启动方式：

```powershell
python -m nsgablack run_inspector --entry build_solver.py:build_solver
python -m nsgablack run_inspector --empty --workspace .
```

使用约束：`build_solver()` 必须只做装配，不应在 UI Load 时触发重计算。重任务应延迟到 `run()` 或 `evaluate()`。

## 9. Catalog 口径

Catalog 是正式可发现性 surface，不是文档装饰。

常用能力：

- `search/list/show` 查找 adapter、bias、plugin、representation、suite、tool、example、doc。
- 查看 usage profile：use_when、minimal_wiring、required_companions、config_keys、example_entry。
- 查看 context contract：requires、provides、mutates、cache、notes。
- 通过 `profile` 区分框架主干与示例文档。

两个 profile：

| profile | 用途 |
| --- | --- |
| `default` | 完整口径，包含 example/doc，适合教学、模板和案例查找 |
| `framework-core` | 主干口径，排除 example/doc 和 examples_registry 导向条目，适合架构审计和主干盘点 |

涉及“是否属于框架主干”的判断，必须显式带：

```powershell
python -m nsgablack catalog list --profile framework-core --kind adapter
python -m nsgablack catalog search nsga2 --profile framework-core --limit 20
python -m nsgablack catalog show adapter.nsga2 --profile framework-core
```

完整口径对照：

```powershell
python -m nsgablack catalog list --profile default --kind example
python -m nsgablack catalog list --profile framework-core --kind example
```

## 10. 标准项目脚手架

创建项目：

```powershell
python -m nsgablack project init my_project
cd my_project
python -m nsgablack project doctor --path . --build --strict
python build_solver.py
```

`my_project` 是框架级起步模板、参考骨架、兼容层或用户私有项目孵化位。正式 example、demo、benchmark runner、cross-framework case 不应继续长期落在仓库根部 `my_project/`。

正式案例建议放在：

```text
examples/cases/<case>/
  problem/             # 问题定义、目标、约束、数据/场景契约
  pipeline/            # 候选流转、representation、evaluation chain、数据处理链
  config/              # 可声明、可复现的装配配置
  adapter/             # 项目局部策略组件，可选
  bias/                # 领域偏置、算法偏置、seed bias
  plugins/             # trace/report/checkpoint/backend/storage 能力
  reporting/           # summary、表格、图、审计输出
  build_solver.py      # 薄组装入口
  run_solver.py        # 薄运行入口
  project_registry.py  # 项目局部 catalog，可选
```

示例文件本身应是薄入口、兼容层或教学调用层。真实装配逻辑应进入 problem/pipeline/config/plugins/bias/reporting 等标准层。

## 11. 与 mlblack 的关系

`nsgablack` 和 `mlblack` 的边界是外层优化与内层学习/代理评估的边界。

| 框架 | 主要职责 |
| --- | --- |
| `nsgablack` | 外层 optimization orchestration，负责候选生成、Pareto/frontier、solver fanout、outer evaluation budget、多策略/多 solver/嵌套评估治理 |
| `mlblack` | 内层 learning/evaluation proxy，负责数据到数值、trainer family、artifact、metrics、capability lifecycle、audit/report surface |

跨框架资源边界：

- `nsgablack` L0 owns inter-solver and outer-evaluation resource scheduling。
- `mlblack` L0 owns intra-evaluation compute backend。
- 嵌套时，`mlblack` 必须服从 `nsgablack` 注入的 `ResourceContext`。
- 跨框架 case 不能在 example 文件里私下写死 `cuda:0`、线程数或 inner backend。

相关仓库：<https://github.com/sorrowoMan/mlblack>

## 12. 常用命令

安装与入口：

```powershell
python -m pip install -U pip
python -m pip install -e .[dev]
python -m nsgablack --help
```

项目体检：

```powershell
python -m nsgablack project doctor --path . --strict --format problem
python -m nsgablack project doctor --path . --build --strict
```

本地项目 catalog：

```powershell
python -m nsgablack project catalog list --path .
python -m nsgablack project catalog search pipeline --path .
python -m nsgablack project catalog search vns --path . --global
```

Run Inspector：

```powershell
python -m nsgablack run_inspector --entry build_solver.py:build_solver
```

## 13. 目录结构

| 路径 | 作用 |
| --- | --- |
| `core/` | Solver 主干、评估入口、状态访问、nested runtime、context/snapshot |
| `adapters/` | NSGA2/3、SPEA2、MOEA/D、VNS、SA、DE、TR、A*、MAS、多策略等策略组件 |
| `representation/` | 候选表示、初始化、变异、修复、编码解码 |
| `bias/` | domain / algorithmic / surrogate bias 与 bias manager/facade |
| `plugins/` | runtime/evaluation/system/ops/storage/backends/models 能力层 |
| `catalog/` | 可发现性索引、profile/filter、DB materialization、UI 支撑 |
| `project/` | project init、doctor、local catalog、结构治理 |
| `examples/cases/` | 正式案例脚手架 |
| `examples/_misc_examples/` | 兼容/历史 demo，不作为新机制默认落点 |
| `docs/` | 架构、用户指南、索引、集成说明 |
| `tests/` | 回归测试与契约测试 |

## 14. 推荐阅读顺序

1. `README.md`：项目定位和当前入口。
2. `AGENTS.md`：协作规则、四层边界、状态协议、示例落点规则。
3. `docs/standard_scaffold_tutorial/README.md`：从 CLI 创建项目到组件配置、编排和验收的标准脚手架教程。
4. `docs/FEATURES_OVERVIEW.md`：能力总览。
5. `docs/user_guide/DEPTH_BREADTH_WORKFLOW.md`：深度嵌套与广度协同。
6. `docs/user_guide/INNER_SOLVER_BACKENDS.md`：problem-side inner runtime。
7. `docs/architecture/SOLVER_ORCHESTRATION.md`：多 solver 编排与资源契约。
8. `docs/user_guide/CONTEXT_CONTRACTS.md`：context key 与契约治理。
9. `docs/user_guide/RUN_INSPECTOR.md`：结构审计和差异解释。
10. `examples/cases/*/README.md`：正式案例。

## 15. 当前状态

`nsgablack` 仍在快速演化，但主干边界已经明确：Solver 控制生命周期，Adapter 承载搜索策略，Representation 处理候选表示，Bias 做软引导，Plugin 做运行能力，Context/Snapshot 做状态治理，Catalog/Doctor/Run Inspector 做可发现与审计。

如果要新增机制，先判断它属于哪一层；如果要新增案例，优先落在 `examples/cases/<case>/`；如果要判断主干能力，使用 `framework-core` catalog 口径。
