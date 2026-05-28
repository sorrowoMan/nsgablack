# 01. nsgablack 控制平面对齐

覆盖路径：

- `core/base.py`
- `core/blank_solver.py`
- `core/composable_solver.py`
- `core/evolution_solver.py`
- `core/evaluation_runtime.py`
- `core/control_plane.py`
- `core/runtime_governance.py`
- `core/solver_helpers/*`

## 1. `BlackBoxProblem`

| 代码叫法 | 社区常用叫法 | 机制含义 | 你的差异点 |
| --- | --- | --- | --- |
| `BlackBoxProblem.evaluate(x)` | objective oracle / black-box function | 给候选解返回目标值。 | 作为 solver 的唯一问题评估入口，避免算法直接知道业务问题。 |
| `evaluate_constraints(x)` | constraint violation oracle | 返回约束违反程度。 | 统一单点/批量约束接口，便于多算法、多插件共享。 |
| `is_valid(x)` | feasibility check | 检查边界和约束。 | 把 bounds 与 constraints 合并为候选合法性协议。 |
| `get_num_objectives()` | objective dimension query | 暴露目标数量。 | 让 solver/adapter 不依赖具体 problem 子类。 |
| `evaluation_count` wrapper | evaluation budget counter | 记录评估次数。 | 在问题类子类化时自动包裹 evaluate，减少业务代码侵入。 |

可对外表达：

> `BlackBoxProblem` is the objective/constraint oracle boundary. It separates domain evaluation from search control.

## 2. `SolverBase`

| 代码叫法 | 社区常用叫法 | 机制含义 | 你的差异点 |
| --- | --- | --- | --- |
| `SolverBase` | optimization control plane / solver runtime | 管生命周期、评估入口、状态、RNG、插件、context/snapshot。 | 不承载具体算法策略，避免 solver 退化成算法大杂烩。 |
| `plugin_manager` | callback manager / middleware dispatcher | 调度插件生命周期和短路能力。 | 插件是能力层，不是算法层。 |
| `representation_pipeline` | genotype-phenotype pipeline | 候选初始化、修复、编码、解码。 | solver 只调用统一接口，不知道具体表示细节。 |
| `bias_module` | inductive bias / prior / heuristic guidance | 搜索软引导。 | 偏置和算法分离，避免把业务策略塞进 adapter。 |
| `context_store` | runtime context store | 存轻量运行状态和引用。 | 与 snapshot 分离，防止大对象污染上下文。 |
| `snapshot_store` | snapshot/artifact state store | 存 population/objectives/history/trace 等大对象。 | 通过 `_ref` 传递大对象，形成可回放状态链。 |
| `fork_rng()` / component RNG | seeded stochastic stream / random state management | 给组件可控随机源。 | 便于复现实验和组件级随机隔离。 |
| `evaluate_individual` / `evaluate_population` | evaluation gateway | 统一单点/批量评估入口。 | 插件可接管评估，但返回 shape 必须守约。 |

可对外表达：

> `SolverBase` is not an optimizer implementation. It is the runtime control plane that governs evaluation, state, plugins, reproducibility, and representation boundaries.

## 3. `ComposableSolver`

| 代码叫法 | 社区常用叫法 | 机制含义 | 你的差异点 |
| --- | --- | --- | --- |
| `ComposableSolver.adapter` | search policy / optimizer strategy | 把候选生成与反馈更新委托给 adapter。 | solver 负责流程，adapter 负责策略。 |
| `adapter.propose(...)` | candidate generation / ask step | 产生候选解。 | 和评估、状态、插件生命周期解耦。 |
| `adapter.update(...)` | feedback update / tell step | 接收目标和约束反馈。 | 支持 ask-tell 风格，适合进化算法、局部搜索、HPO。 |
| `coerce_candidates` + `normalize_candidates` | candidate shape normalization | 统一候选输出格式。 | 降低自定义 adapter 接入错误。 |
| representation repair pass | repair/projection operator | adapter 产物统一经过 representation 修复。 | 防止算法绕过候选表示协议。 |
| `_update_best` / scalarizer | incumbent tracking / scalarized summary | 用标量摘要记录 best_x。 | 多目标 Pareto 管理和 best summary 分离。 |

可对外表达：

> `ComposableSolver` implements an ask-tell optimization shell. Search logic lives in adapters; evaluation and runtime governance remain in the solver.

## 4. `EvolutionSolver`

| 代码叫法 | 社区常用叫法 | 机制含义 | 你的差异点 |
| --- | --- | --- | --- |
| `EvolutionSolver` | evolutionary algorithm runtime | 进化范式默认 solver。 | 默认可挂 NSGA2 adapter，但不把 NSGA2 写死为唯一语义。 |
| Pareto 管理 | non-dominated sorting / Pareto archive | 管理多目标非支配前沿。 | 与插件、snapshot、并行评估对齐。 |
| parallel evaluation | batch/parallel fitness evaluation | 批量并行评估 population。 | 通过统一评估入口和 shape validation 管理并行结果。 |

可对外表达：

> `EvolutionSolver` is a default evolutionary runtime built on the same control-plane contracts, not a special one-off NSGA script.

## 5. 评估治理

| 代码叫法 | 社区常用叫法 | 机制含义 | 你的差异点 |
| --- | --- | --- | --- |
| `EvaluationMediator` | evaluation router / provider arbitration | 调度真实评估、近似评估、插件短路。 | 让 surrogate/cache/provider 不直接侵入 solver。 |
| `EvaluationProvider` | evaluator backend / model-based evaluator | 提供某种评估能力。 | 支持 strict conflict 和 approximate 控制。 |
| plugin short-circuit | callback takeover / middleware interception | 插件提前返回评估结果。 | 允许 surrogate、cache、remote backend 接管，但必须守 shape。 |
| shape validation | contract validation | 检查 objectives/violations 对齐。 | 对复杂评估链非常关键，避免 silent bug。 |

可对外表达：

> Evaluation is treated as a governed runtime path, not just `problem.evaluate` calls scattered through algorithms.

## 6. 控制器与运行治理

| 代码叫法 | 社区常用叫法 | 机制含义 | 你的差异点 |
| --- | --- | --- | --- |
| `ControlArbiter` | control-plane arbitration | 多控制器冲突协调。 | 将 stop/budget/switch 这类控制语义从算法中抽离。 |
| `RuntimeController` | runtime governance layer | 统一运行控制入口。 | 便于后续接 budget、switch、resource policy。 |
| `ConvergenceMonitor` | convergence detector | 收敛监控。 | 是控制能力，不是 adapter 内部私有逻辑。 |
| `AdaptiveParametersGovernor` | adaptive parameter scheduler | 自适应参数治理。 | 作为 runtime governor，而不是每个算法各写一套。 |
| `CompanionOrchestrator` | companion process/controller | 辅助控制或伴随模块编排。 | 支持外部能力挂载但不污染 solver 主流程。 |

## 7. `solver_helpers`

| 代码叫法 | 社区常用叫法 | 机制含义 | 你的差异点 |
| --- | --- | --- | --- |
| `evaluation_helpers` | evaluation utility layer | 封装评估、bias、plugin 组合。 | 把复杂评估路径从 `SolverBase` 中拆出。 |
| `snapshot_helpers` | snapshot IO helpers | 处理 population snapshot 读写。 | 稳定大对象生命周期协议。 |
| `context_helpers` | runtime context projection | 构造对外 context view。 | 汇总 solver/adapter/plugin 的运行切片。 |
| `component_scheduler` | component dependency scheduling | 组件顺序与依赖管理。 | 插件/组件顺序不完全依赖注册顺序。 |
| `result_helpers` | run result builder | 统一 run 输出。 | 让 artifact/report/replay 更容易接入。 |

## 8. 这一层的核心价值

| 传统写法 | 你的写法 |
| --- | --- |
| 算法循环里直接 evaluate、log、checkpoint、repair。 | solver 控制生命周期，adapter 管策略，representation 管候选，plugin 管能力。 |
| population/objectives 直接塞 dict。 | 大对象进 snapshot，context 只放 ref。 |
| 每个算法自己处理随机数、状态和恢复。 | solver 统一 RNG、状态和 checkpoint 接口。 |
| surrogate/cache/remote eval 写进算法 if/else。 | evaluation mediator + plugin/provider 接管评估路径。 |

