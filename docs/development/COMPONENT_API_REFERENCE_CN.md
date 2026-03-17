# 组件 API 全览（用途 + 用法 + 一致性检查）

> 目标：给 `nsgablack` 做一份可直接审阅的组件 API 参考，重点回答“这个方法干什么、什么时候调用、怎么用、命名是否一致”。
> 范围：框架核心组件（`core` / `adapters` / `plugins` / `representation` / `bias` / `utils/context`）。

---

## 1. 分层与调用主线

- **Solver（控制平面）**：驱动生命周期、评估入口、快照读写、插件分发。
- **Adapter（算法策略）**：负责 `propose/update`，不直接改写 solver 主循环。
- **Representation（表示层）**：负责 `init/mutate/repair/encode/decode`。
- **Plugin（能力层）**：观察、记录、守护、编排，不替代算法本体。
- **Bias（软引导）**：附加偏置分数，不替代硬约束修复。
- **Context/Snapshot（状态层）**：小字段放 context，大对象放 snapshot。

标准调用链（单代）通常是：
`solver.step()` → `adapter.propose()` → `solver.evaluate_population()` → `adapter.update()` → `plugins.on_generation_end()`。

---

## 2. Core：Solver API（重点）

### 2.1 `core/blank_solver.py::SolverBase`

#### 生命周期与控制

| 方法 | 用途 | 怎么用 |
|---|---|---|
| `setup()` | 初始化 solver 运行态与插件钩子前置阶段 | 通常不手动调，由 `run()` 触发 |
| `step()` | 执行单代优化步骤（可被子类覆盖） | 调试时可单步调用 |
| `teardown()` | 收尾、释放资源、写终态信息 | 通常由 `run()` 自动触发 |
| `run()` | 主入口，完整生命周期 | `result = solver.run(max_generations=..., seed=...)` |
| `request_stop()` | 提前终止运行 | 外部控制器/插件触发软停机 |
| `set_max_steps()` | 设置步数上限 | 快速限制实验长度 |
| `set_generation()` | 强制设置当前代数 | 续跑/恢复时使用 |

#### 插件与控制平面

| 方法 | 用途 | 怎么用 |
|---|---|---|
| `add_plugin()` / `remove_plugin()` / `get_plugin()` | 管理插件实例 | `solver.add_plugin(ParetoArchivePlugin())` |
| `set_plugin_order()` / `request_plugin_order()` / `validate_plugin_order()` | 管理插件执行顺序 | 对多插件冲突做显式排序 |
| `validate_control_plane()` | 检查控制平面配置冲突 | 启动前自检 |
| `register_controller()` | 注册 runtime 控制器 | 给 stopping/switch/budget 等域挂控制器 |
| `set_adapter()` | 设置算法适配器 | `solver.set_adapter(VNSAdapter(...))` |
| `set_strategy_controller()` / `set_phase_controller()` | 挂控制策略组件 | 多阶段编排场景 |

#### 评估入口

| 方法 | 用途 | 怎么用 |
|---|---|---|
| `evaluate_individual()` | 单点评估入口（支持插件/provider短路） | 单测或在线评估调试 |
| `evaluate_population()` | 批量评估入口（支持并行/短路） | adapter 通常走这个 |
| `increment_evaluation_count()` | 维护评估计数 | 一般内部调用 |

#### 表示层桥接

| 方法 | 用途 | 怎么用 |
|---|---|---|
| `set_representation_pipeline()` | 注入表示流水线 | `solver.set_representation_pipeline(pipeline)` |
| `init_candidate()` | 候选初始化桥接 | adapter 内部调用 |
| `mutate_candidate()` | 候选变异桥接 | adapter 内部调用 |
| `repair_candidate()` | 候选修复桥接 | adapter 内部调用 |
| `encode_candidate()` / `decode_candidate()` | 表示变换桥接 | 需要编码空间切换时用 |
| `initialize_population()` | 初始化种群 | 启动阶段核心步骤 |

#### Bias / Context / Snapshot

| 方法 | 用途 | 怎么用 |
|---|---|---|
| `set_bias_module()` / `set_bias_enabled()` | 注入并启停偏置 | `solver.set_bias_enabled(True)` |
| `set_context_store()` / `set_snapshot_store()` | 存储后端接入 | 生产环境建议显式配置 |
| `set_context_store_backend()` / `set_snapshot_store_backend()` | 快速切后端 | dev/prod 切换 |
| `build_context()` / `get_context()` | 生成当前上下文 | 插件或调试读取 |
| `write_population_snapshot()` / `read_snapshot()` | 大对象快照读写 | 避免把大数组塞 context |
| `set_best_snapshot()` / `set_pareto_snapshot()` / `resolve_best_snapshot()` | 最优状态快照管理 | 可回放与外部审计 |

#### RNG / 后端

| 方法 | 用途 | 怎么用 |
|---|---|---|
| `set_random_seed()` / `fork_rng()` | 随机流管理 | 可复现实验 |
| `get_rng_state()` / `set_rng_state()` | RNG 状态回放 | checkpoint 场景 |
| `register_evaluation_provider()` | 注册 L4 评估提供器 | surrogate/multi-fidelity |
| `register_acceleration_backend()` / `get_acceleration_backend()` | 加速后端注册/获取 | 并行或硬件加速接入 |

---

### 2.2 `core/composable_solver.py::ComposableSolver`

| 方法 | 用途 | 怎么用 |
|---|---|---|
| `set_adapter()` / `set_adapters()` | 单/多 adapter 组合 | 快速切换算法 |
| `setup()` / `step()` / `teardown()` | 组合式运行生命周期 | 常由 `run()` 调用 |
| `select_best()` | 在候选中选最优 | 自定义挑选规则时复用 |

### 2.3 `core/evolution_solver.py::EvolutionSolver`

| 方法 | 用途 | 怎么用 |
|---|---|---|
| `non_dominated_sorting()` | 非支配排序 | 多目标排序核心 |
| `selection()` / `crossover()` / `mutate()` | 进化算子流程 | 子类可覆盖 |
| `environmental_selection()` | 环境选择 | 保持种群质量与多样性 |
| `update_pareto_solutions()` | 更新 Pareto 集 | 多目标核心输出 |
| `record_history()` | 记录历史曲线 | 可视化与分析 |

---

## 3. Adapters：策略层 API

### 3.1 统一契约（所有 Adapter 都应满足）

| 方法 | 用途 | 调用时机 |
|---|---|---|
| `setup(solver, context)` | 运行前初始化内部状态 | solver `setup` 阶段 |
| `propose(solver, context)` | 生成候选解批次 | 每代 `step` 前半 |
| `update(solver, candidates, objectives, violations, context)` | 吸收评估反馈、更新状态 | 每代评估后 |
| `teardown(solver, context)` | 收尾 | solver `teardown` |
| `get_state()` / `set_state()` | 状态可恢复 | checkpoint / resume |
| `get_population()` / `set_population()` | 与运行态种群同步 | runtime 插件写回 |
| `get_runtime_context_projection()` | 暴露运行态切片给插件/UI | 可观测性 |
| `get_context_contract()` | 声明 context requires/provides/mutates | doctor 与冲突检查 |

### 3.2 主要适配器（按用途）

- **单轨迹/局部**：`VNSAdapter`、`SimulatedAnnealingAdapter`、`PatternSearchAdapter`、`GradientDescentAdapter`、`SingleTrajectoryAdaptiveAdapter`
- **多目标群体**：`NSGA2Adapter`、`NSGA3Adapter`、`SPEA2Adapter`、`MOEADAdapter`
- **编排型**：`RoleRouterAdapter`、`StrategyRouterAdapter`、`AsyncEventDrivenAdapter`
- **图搜索/其它**：`AStarAdapter`、`MOAStarAdapter`、`MASAdapter`
- **信赖域家族**：`TrustRegionDFOAdapter`、`TrustRegionMODFOAdapter`、`TrustRegionSubspaceAdapter`、`TrustRegionNonSmoothAdapter`

最小示例：

```python
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.adapters import VNSAdapter

solver = ComposableSolver(problem=problem, adapter=VNSAdapter(), representation_pipeline=pipeline)
result = solver.run(max_generations=50, seed=7)
```

---

## 4. Plugins：能力层 API

### 4.1 `plugins/base.py::Plugin`

| 方法 | 用途 | 怎么用 |
|---|---|---|
| `attach()` / `detach()` | 插件附着/脱离 solver | `add_plugin` 时自动触发 |
| `enable()` / `disable()` | 运行时启停 | 灰度控制 |
| `configure()` / `get_config()` | 插件参数配置 | 外部注入配置 |
| `get_context_contract()` | 上下文契约声明 | doctor/冲突检测 |
| `create_local_rng()` | 插件局部随机流 | 可复现性 |
| `on_solver_init()` | solver 初始化后 | 建立初始状态 |
| `on_population_init()` | 初代种群建立后 | 统计/过滤 |
| `on_generation_start()` | 每代开始 | 动态参数更新 |
| `on_step()` | 每步中间钩子 | 细粒度记录 |
| `on_generation_end()` | 每代结束 | 报告/归档 |
| `on_solver_finish()` | 运行结束 | 收尾输出 |
| `get_report()` | 输出插件报告 | UI/日志/审计 |
| `get_population_snapshot()` / `commit_population_snapshot()` | 统一读写种群快照 | 避免直接读 solver 大字段 |

### 4.2 `plugins/base.py::PluginManager`

| 方法 | 用途 |
|---|---|
| `register/unregister/get` | 插件注册与查找 |
| `set_execution_order` | 插件顺序控制 |
| `trigger/dispatch` | 事件分发 |
| `on_*` 系列 | 生命周期批量转发 |
| `list_plugins/clear` | 管理与清理 |

### 4.3 常用插件组

- **ops/observability**：`BenchmarkHarnessPlugin`、`DecisionTracePlugin`、`ModuleReportPlugin`、`ProfilerPlugin`
- **system**：`CheckpointResumePlugin`、`MemoryPlugin`、`BoundaryGuardPlugin`、`AsyncEventHubPlugin`
- **evaluation providers**：`SurrogateEvaluationProviderPlugin`、`MultiFidelityEvaluationProviderPlugin`、`MonteCarloEvaluationProviderPlugin`
- **solver backends**：`CoptBackend`、`NgspiceBackend`、`ContractBridgePlugin`

最小示例：

```python
from nsgablack.plugins import ParetoArchivePlugin, CheckpointResumePlugin

solver.add_plugin(ParetoArchivePlugin())
solver.add_plugin(CheckpointResumePlugin())
```

---

## 5. Representation：表示层 API

### 5.1 `representation/base.py::RepresentationPipeline`

| 方法 | 用途 | 怎么用 |
|---|---|---|
| `init(context)` | 批量初始化候选 | 初始化种群时调用 |
| `mutate(x, context)` / `mutate_batch(...)` | 变异 | adapter `propose` 中调用 |
| `repair_one(x, context)` / `repair_batch(...)` | 修复约束和非法结构 | 评估前最后防线 |
| `encode(x)` / `decode(x)` | 编码与解码 | 不同搜索空间转换 |
| `encode_batch/decode_batch` | 批量编码/解码 | 提升吞吐 |
| `get_context_contract()` | 契约声明 | doctor 校验 |

### 5.2 基础插件接口（算子接口）

| 接口类 | 方法 |
|---|---|
| `InitPlugin` | `initialize` |
| `MutationPlugin` | `mutate` |
| `RepairPlugin` | `repair` |
| `EncodingPlugin` | `encode`, `decode` |
| `CrossoverPlugin` | `crossover` |

### 5.3 常见算子

- **continuous**：`UniformInitializer`、`GaussianMutation`、`ContextGaussianMutation`、`ClipRepair`、`ProjectionRepair`
- **integer/matrix/permutation/binary/graph**：对应 `initializer/mutate/repair` 组件均遵循同一接口。
- **orchestration**：`PipelineOrchestrator.mutate/repair`（串行、路由、动态策略统一编排）。

最小示例：

```python
from nsgablack.representation import RepresentationPipeline, UniformInitializer, ContextGaussianMutation, ClipRepair

pipeline = RepresentationPipeline(
    initializer=UniformInitializer(low=-5, high=5),
    mutator=ContextGaussianMutation(base_sigma=0.3, low=-5, high=5),
    repair=ClipRepair(low=-5, high=5),
)
```

---

## 6. Bias：偏置系统 API

### 6.1 `bias/core/base.py`

| 类/接口 | 方法 | 用途 |
|---|---|---|
| `BiasInterface` | `compute/get_name/get_weight/set_weight/enable/disable` | 统一偏置契约 |
| `BiasBase` | `compute(abstract)`、`compute_with_tracking()`、`get_context_contract()` | 偏置基类与统计追踪 |
| `OptimizationContext` | `set_stuck_status/set_convergence_status/set_constraint_violation` | 偏置感知优化状态 |

### 6.2 `bias/core/manager.py`

| 类 | 关键方法 | 用途 |
|---|---|---|
| `AlgorithmicBiasManager` | `add_algorithmic_bias`、`compute_total_bias`、`adapt_weights` | 算法偏置管理与自适应 |
| `DomainBiasManager` | `add_domain_bias`、`compute_total_bias` | 领域规则偏置管理 |
| `UniversalBiasManager` | 统一增删查与总偏置计算 | facade 下层核心 |

### 6.3 `bias/bias_module.py::BiasModule`

| 方法 | 用途 |
|---|---|
| `add()` | 添加偏置（对象/字典/函数） |
| `compute_bias()` / `compute_bias_vector()` | 计算单点/向量偏置 |
| `set_context_store()` / `set_snapshot_store()` | 与 context/snapshot 集成 |
| `set_cache_backend()` 等缓存配置 | 控制偏置缓存 |
| `get_context_contract()` | 汇总下游偏置契约 |

最小示例：

```python
from nsgablack.bias import BiasModule

bias_module = BiasModule()
solver.set_bias_module(bias_module)
solver.set_bias_enabled(True)
```

---

## 7. Context / Snapshot：状态契约 API

- 统一 key：`core/state/context_keys.py`（不要手写字符串常量）。
- 大对象写入：`SnapshotStore.write(...)`，上下文仅放 `_ref/snapshot_key`。
- 读取优先：`snapshot -> adapter state -> solver field`。
- 推荐入口：
  - `solver.read_snapshot(...)`
  - `Plugin.get_population_snapshot(...)`
  - `Plugin.commit_population_snapshot(...)`

---

## 8. 组件 API 是否“合理/正确”的审查标准

### 8.1 判定标准

- **语义一致**：方法名动词和行为一致（例如 `get_*` 只取值、不做复杂推断）。
- **契约一致**：接口签名稳定，`context_contract` 能声明依赖与副作用。
- **边界一致**：算法逻辑留在 Adapter；能力增强放 Plugin；候选结构处理在 Representation。
- **状态一致**：大对象 snapshot 化；context 仅存轻量字段。

### 8.2 现状结论（基于当前仓库）

- 主干 API 已基本形成统一逻辑。
- 存在少量历史命名与文档对照残留（多在 development 审计文档），不影响主运行链路。
- `SolverBase` 仍有少数历史方法名（如 `resolve_best_snapshot`），建议后续通过别名+弃用周期平滑收敛。

---

## 9. 常用调用模板

### 9.1 最小可运行模板

```python
solver = ComposableSolver(problem=problem, adapter=adapter, representation_pipeline=pipeline)
solver.add_plugin(ParetoArchivePlugin())
result = solver.run(max_generations=50, seed=7)
```

### 9.2 多组件组合模板

```python
solver.set_bias_module(bias_module)
solver.set_bias_enabled(True)
solver.register_evaluation_provider(surrogate_provider)
solver.add_plugin(CheckpointResumePlugin())
solver.add_plugin(DecisionTracePlugin())
```

---

## 10. 你可以怎么审这份表

- 先看 `core` 与 `adapters`：确认“策略在 adapter，控制在 solver”。
- 再看 `plugins`：确认是否有越权替代算法语义。
- 再看 `representation`：确认 `repair` 是否只做硬约束底线。
- 最后看 `bias/context/snapshot`：确认状态落盘和缓存策略是否符合你的工程要求。

---

## 11. 全量枚举索引（逐类逐方法）

- 全量检索表见：`docs/development/COMPONENT_API_INDEX_FULL_CN.md`
- 该文件按“模块 / 类 / 方法 / 用途 / 用法”逐条展开，适合做命名审计、职责对齐与重构拆分设计。
