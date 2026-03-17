# 公共 API 表面（自动提取）

本文件列出代码库中的公共类及其公共方法（由代码自动提取）。
用于支持 API 命名评审与一致性检查。

> 说明：API 标识符（类名、方法名、路径）保留英文原文，仅文档说明中文化。

## 公共入口

- `core/__init__.py`
- `adapters/__init__.py`
- `plugins/__init__.py`
- `representation/__init__.py`

## 可讨论改名清单（命名建议/疑似难记点）

> 用法：该清单用于评审“是否更易记、是否更语义化、是否与全局命名风格一致”。
> 约定：仅列建议，不立即破坏兼容；建议配套别名与弃用周期。

| 位置                                    | 当前名称                            | 类型   | 命名建议/疑似难记点                                 | 候选新名称                                         |
| --------------------------------------- | ----------------------------------- | ------ | --------------------------------------------------- | -------------------------------------------------- |
| `core/blank_solver.py`                | `blank_solver`                    | 模块名 | “blank”语义弱，不直观体现“基础控制平面”         | `base_solver` / `control_plane_solver`         |
| `core/blank_solver.py`                | `SolverBase`                      | 类名   | 与 `base.py` 的“base”语义可能重叠               | `BaseSolver`                                     |
| `core/evolution_solver.py`            | `set_solver_hyperparams`          | 方法名 | `set_` + `hyperparams` 长且不统一               | `configure_hyperparams`                          |
| `core/blank_solver.py`                | `set_bias_enabled`                | 方法名 | 双动词结构（set+enable）不自然                      | `set_bias_enabled` / `enable_bias`             |
| `core/blank_solver.py`                | `resolve_best_snapshot`           | 方法名 | `resolve` 在代码库内语义不统一（取值/推断/合并）  | `get_best_snapshot`                              |
| `core/blank_solver.py`                | `read_snapshot`                   | 方法名 | 与 `write_population_snapshot` 动词不对称         | `load_snapshot`                                  |
| `adapters/multi_strategy/adapter.py`  | `StrategyRouterAdapter`           | 类名   | “ControllerAdapter”双角色叠加，记忆负担高         | `MultiStrategyAdapter`                           |
| `adapters/serial_strategy/adapter.py` | `SerialStrategyControllerAdapter` | 类名   | 与上项同类问题，后缀冗长                            | `SerialStrategyAdapter`                          |
| `adapters/role_adapters/adapter.py`   | `RoleRouterAdapter`               | 类名   | 命名较长，且“Controller”职责边界不清              | `MultiRoleAdapter`                               |
| `representation/context_mutators.py`  | `ContextSelectMutator`            | 类名   | “Switch”语义偏离（按 key 选择 vs 条件切换）       | `ContextKeyMutator`                              |
| `representation/context_mutators.py`  | `ContextRouterMutator`            | 类名   | 与 `Switch` 边界可能重叠，易混淆                  | `ContextDispatchMutator`                         |
| `representation/orchestrator.py`      | `PipelineOrchestrator`            | 类名   | 若未来扩展到 encode/decode，`Pipeline` 范围需明确 | `RepresentationOrchestrator`                     |
| `plugins/system/checkpoint_resume.py` | `CheckpointResumePlugin`          | 类名   | “Checkpoint+Resume”并列，读起来像两个插件         | `CheckpointPlugin`                               |
| `plugins/system/memory_optimize.py`   | `MemoryPlugin`                    | 类名   | 文件名与类名语义粒度不一致                          | `MemoryOptimizePlugin` / `MemoryMonitorPlugin` |
| `plugins/evaluation/*`                | `build_provider`                  | 方法名 | `build` 与 `register/get` 体系未完全对齐        | `create_provider`                                |

> 评审建议：优先统一“动词集合（set/get/create/register/enable）”与“后缀集合（Adapter/Plugin/Orchestrator）”，再批量改名。

## 方法/API 统一提案（你关注的核心）

当前痛点是“同一语义，不同类用不同命名”：

- 按 `context` 选策略：有的叫 `switch`，有的叫 `router`，有的塞进 `multi_strategy`
- 串行执行策略：有 `serial`，但在 adapter 层又出现另一套“controller”命名
- 多策略组合：有“strategy/role/controller”多套术语并存

## 公共类与方法

### `adapters/algorithm_adapter.py`

- `AlgorithmAdapter`
  Methods: `resolve_config`, `create_local_rng`, `setup`, `propose`, `update`, `teardown`, `get_state`, `set_state`, `validate_population_snapshot`, `set_population`, `coerce_candidates`, `get_context_contract`, `get_runtime_context_projection`, `get_runtime_context_projection_sources`
- `CompositeAdapter`
  Methods: `setup`, `propose`, `update`, `teardown`, `get_state`, `set_state`, `get_context_contract`

### `adapters/astar/adapter.py`

- `AStarAdapter`
  Methods: `setup`, `propose`, `update`, `get_state`, `set_state`

### `adapters/async_event_driven/adapter.py`

- `AsyncEventDrivenAdapter`
  Methods: `setup`, `teardown`, `propose`, `update`, `get_runtime_context_projection`, `get_runtime_context_projection_sources`, `get_state`, `set_state`

### `adapters/differential_evolution/adapter.py`

- `DifferentialEvolutionAdapter`
  Methods: `setup`, `propose`, `update`, `set_population`, `get_population`, `get_runtime_context_projection`, `get_runtime_context_projection_sources`, `get_state`, `set_state`

### `adapters/gradient_descent/adapter.py`

- `GradientDescentAdapter`
  Methods: `setup`, `propose`, `update`, `get_runtime_context_projection`, `get_runtime_context_projection_sources`, `get_state`, `set_state`

### `adapters/mas/adapter.py`

- `MASAdapter`
  Methods: `propose`, `update`, `get_state`, `set_state`

### `adapters/moa_star/adapter.py`

- `MOAStarAdapter`
  Methods: `setup`, `propose`, `update`, `get_state`, `set_state`

### `adapters/moead/adapter.py`

- `MOEADAdapter`
  Methods: `setup`, `teardown`, `propose`, `update`, `get_runtime_context_projection`, `get_runtime_context_projection_sources`, `get_state`, `set_state`, `get_population`, `set_population`

### `adapters/multi_strategy/adapter.py`

- `StrategyRouterAdapter`
  Methods: `setup`, `teardown`, `propose`, `update`, `get_runtime_context_projection`, `get_runtime_context_projection_sources`, `get_context_contract`

### `adapters/nsga2/adapter.py`

- `NSGA2Adapter`
  Methods: `setup`, `propose`, `update`, `set_population`, `get_population`, `get_runtime_context_projection`, `get_runtime_context_projection_sources`, `get_state`, `set_state`

### `adapters/nsga3/adapter.py`

- `NSGA3Adapter`
  Methods: `setup`

### `adapters/pattern_search/adapter.py`

- `PatternSearchAdapter`
  Methods: `setup`, `propose`, `update`, `get_runtime_context_projection`, `get_runtime_context_projection_sources`, `get_state`, `set_state`

### `adapters/role_adapters/adapter.py`

- `RoleRouterAdapter`
  Methods: `setup`, `propose`, `update`, `teardown`, `get_state`, `set_state`, `get_runtime_context_projection`, `get_runtime_context_projection_sources`
- `RoleAdapter`
  Methods: `setup`, `propose`, `update`, `teardown`, `get_state`, `set_state`, `get_context_contract`

### `adapters/serial_strategy/adapter.py`

- `SerialStrategyControllerAdapter`
  Methods: `setup`, `teardown`, `propose`, `update`, `get_state`, `set_state`

### `adapters/simulated_annealing/adapter.py`

- `SimulatedAnnealingAdapter`
  Methods: `setup`, `propose`, `update`, `get_state`, `set_state`, `get_runtime_context_projection`, `get_runtime_context_projection_sources`

### `adapters/single_trajectory_adaptive/adapter.py`

- `SingleTrajectoryAdaptiveAdapter`
  Methods: `setup`, `propose`, `update`, `get_state`, `set_state`, `get_runtime_context_projection`, `get_runtime_context_projection_sources`

### `adapters/trust_region_base/adapter.py`

- `TrustRegionBaseAdapter`
  Methods: `setup`, `propose`, `update`, `get_state`, `set_state`

### `adapters/vns/adapter.py`

- `VNSAdapter`
  Methods: `setup`, `propose`, `update`, `get_runtime_context_projection`, `get_runtime_context_projection_sources`, `get_state`, `set_state`

### `core/base.py`

- `BlackBoxProblem`
  Methods: `evaluate`, `evaluate_constraints`, `is_valid`, `get_num_objectives`, `is_multiobjective`

### `core/blank_solver.py`

- `SolverBase`
  Methods: `set_context_store`, `set_snapshot_store`, `set_context_store_backend`, `set_snapshot_store_backend`, `bias_module`, `bias_module`, `init_bias_module`, `representation_pipeline`, `representation_pipeline`, `enable_bias_module`, `add_plugin`, `remove_plugin`, `get_plugin`, `set_plugin_order`, `request_plugin_order`, `validate_plugin_order`, `validate_control_plane`, `set_adapter`, `set_strategy_controller`, `set_phase_controller`, `set_bias_module`, `set_bias_enabled`, `set_representation_pipeline`, `has_bias_support`, `has_numba_support`, `register_controller`, `register_evaluation_provider`, `register_acceleration_backend`, `get_acceleration_backend`, `set_max_steps`, `set_generation`, `increment_evaluation_count`, `set_best_snapshot`, `set_pareto_snapshot`, `resolve_best_snapshot`, `set_solver_hyperparams`, `init_candidate`, `mutate_candidate`, `repair_candidate`, `encode_candidate`, `decode_candidate`, `initialize_population`, `write_population_snapshot`, `read_snapshot`, `set_random_seed`, `fork_rng`, `get_rng_state`, `set_rng_state`, `build_context`, `get_context`, `evaluate_individual`, `evaluate_population`, `request_stop`, `setup`, `step`, `teardown`, `run`

### `core/composable_solver.py`

- `ComposableSolver`
  Methods: `set_adapter`, `set_adapters`, `setup`, `teardown`, `step`, `select_best`

### `core/evolution_solver.py`

- `EvolutionSolver`
  Methods: `representation_pipeline`, `representation_pipeline`, `set_adapter`, `set_solver_hyperparams`, `set_context_store`, `set_snapshot_store`, `set_context_store_backend`, `set_snapshot_store_backend`, `evaluate_population`, `initialize_population`, `setup`, `step`, `non_dominated_sorting`, `selection`, `crossover`, `mutate`, `environmental_selection`, `update_pareto_solutions`, `record_history`, `run`

### `core/nested_solver.py`

- `InnerRuntimeEvaluator`
  Methods: `can_handle`, `evaluate`
- `TaskInnerRuntimeEvaluator`
  Methods: `can_handle`, `evaluate`

### `core/solver_helpers/component_scheduler.py`

- `ComponentDependencyScheduler`
  Methods: `register_component`, `unregister_component`, `snapshot_rules`, `restore_rules`, `set_constraints`, `validate_constraints`, `resolve_order`, `resolve_order_strict`

### `plugins/base.py`

- `Plugin`
  Methods: `get_context_contract`, `create_local_rng`, `attach`, `detach`, `enable`, `disable`, `configure`, `get_config`, `on_solver_init`, `on_population_init`, `on_generation_start`, `on_generation_end`, `on_step`, `on_solver_finish`, `get_report`, `get_population_snapshot`, `commit_population_snapshot`
- `PluginManager`
  Methods: `set_event_hook`, `register`, `unregister`, `get`, `enable`, `disable`, `set_execution_order`, `trigger`, `dispatch`, `on_solver_init`, `on_population_init`, `on_generation_start`, `on_generation_end`, `on_step`, `on_solver_finish`, `list_plugins`, `clear`

### `plugins/evaluation/broyden_solver_plugin.py`

- `BroydenSolverProviderPlugin`
  Methods: `solve_backend`

### `plugins/evaluation/evaluation_model.py`

- `EvaluationModelProviderPlugin`
  Methods: `evaluate_model`, `evaluate_individual_runtime`, `build_provider`

### `plugins/evaluation/gpu_evaluation_template.py`

- `GpuEvaluationTemplateProviderPlugin`
  Methods: `evaluate_population_runtime`, `build_provider`

### `plugins/evaluation/monte_carlo_evaluation.py`

- `MonteCarloEvaluationProviderPlugin`
  Methods: `evaluate_population_runtime`, `build_provider`

### `plugins/evaluation/multi_fidelity_evaluation.py`

- `MultiFidelityEvaluationProviderPlugin`
  Methods: `evaluate_population_runtime`, `build_provider`

### `plugins/evaluation/newton_solver_plugin.py`

- `NewtonSolverProviderPlugin`
  Methods: `solve_backend`

### `plugins/evaluation/numerical_solver_base.py`

- `NumericalSolverProviderPlugin`
  Methods: `solve_backend`, `evaluate_individual_runtime`, `get_report`, `build_provider`

### `plugins/evaluation/surrogate_evaluation.py`

- `SurrogateEvaluationProviderPlugin`
  Methods: `evaluate_population_runtime`, `build_provider`


  Methods: `on_solver_init`, `on_generation_end`, `on_context_build`


  Methods: `on_generation_end`, `on_context_build`

### `plugins/ops/benchmark_harness.py`

- `BenchmarkHarnessPlugin`
  Methods: `on_solver_init`, `on_generation_end`, `on_solver_finish`

### `plugins/ops/decision_trace.py`

- `DecisionTracePlugin`
  Methods: `on_solver_init`, `on_generation_end`, `on_solver_finish`, `record_decision`

### `plugins/ops/module_report.py`

- `ModuleReportPlugin`
  Methods: `on_solver_init`, `on_solver_finish`

### `plugins/ops/otel_tracing.py`

- `OpenTelemetryTracingPlugin`
  Methods: `on_solver_init`, `on_solver_finish`

### `plugins/ops/profiler.py`

- `ProfilerPlugin`
  Methods: `on_solver_init`, `on_generation_start`, `on_generation_end`, `on_solver_finish`

### `plugins/ops/sensitivity_analysis.py`

- `SensitivityAnalysisPlugin`
  Methods: `run_study`

### `plugins/ops/sequence_graph.py`

- `SequenceGraphPlugin`
  Methods: `on_solver_init`, `on_generation_end`, `on_solver_finish`, `on_context_build`, `record_event`


  Methods: `on_solver_init`, `on_population_init`, `on_generation_start`, `on_context_build`, `on_generation_end`, `on_solver_finish`


  Methods: `on_solver_init`, `on_context_build`, `on_generation_end`, `get_report`
- `CompanionPhaseScheduler`
  Methods: `should_trigger`


  Methods: `on_solver_init`, `on_population_init`, `on_generation_start`, `on_context_build`, `on_generation_end`, `on_solver_finish`, `get_convergence_info`

### `plugins/runtime/diversity_init.py`

- `DiversityInitPlugin`
  Methods: `on_solver_init`, `on_population_init`, `on_generation_start`, `on_generation_end`, `on_solver_finish`, `is_similar`, `should_accept`

### `plugins/runtime/dynamic_switch.py`

- `DynamicSwitchPlugin`
  Methods: `should_switch`, `select_switch_mode`, `soft_switch`, `hard_switch`

### `plugins/runtime/elite_retention.py`

- `BasicElitePlugin`
  Methods: `on_solver_init`, `on_population_init`, `on_generation_start`, `on_context_build`, `on_generation_end`, `on_solver_finish`
- `HistoricalElitePlugin`
  Methods: `on_solver_init`, `on_population_init`, `on_generation_start`, `on_context_build`, `on_generation_end`, `on_solver_finish`

### `plugins/runtime/pareto_archive.py`

- `ParetoArchivePlugin`
  Methods: `on_generation_end`

### `plugins/solver_backends/backend_contract.py`

- `BackendSolver`
  Methods: `solve`

### `plugins/solver_backends/contract_bridge.py`

- `ContractBridgePlugin`
  Methods: `on_inner_result`, `get_report`

### `plugins/solver_backends/copt_backend.py`

- `CoptBackend`
  Methods: `solve`

### `plugins/solver_backends/ngspice_backend.py`

- `NgspiceBackend`
  Methods: `solve`

### `plugins/solver_backends/timeout_budget.py`

- `TimeoutBudgetPlugin`
  Methods: `on_solver_init`, `on_inner_guard`, `on_inner_result`, `get_report`

### `plugins/storage/mysql_run_logger.py`

- `MySQLRunLoggerPlugin`
  Methods: `on_solver_finish`

### `plugins/system/async_event_hub.py`

- `AsyncEventHubPlugin`
  Methods: `on_generation_start`, `on_generation_end`, `record_event`, `commit`, `get_committed_context`, `get_report`

### `plugins/system/boundary_guard.py`

- `BoundaryGuardPlugin`
  Methods: `on_generation_end`, `get_report`

### `plugins/system/checkpoint_resume.py`

- `CheckpointResumePlugin`
  Methods: `on_solver_init`, `on_generation_end`, `on_solver_finish`, `save_checkpoint`, `resume`, `get_report`

### `plugins/system/memory_optimize.py`

- `MemoryPlugin`
  Methods: `on_solver_init`, `on_population_init`, `on_generation_start`, `on_generation_end`, `on_solver_finish`, `get_memory_usage`

### `representation/base.py`

- `ContinuousRepresentation`
  Methods: `add_constraint`, `check_constraints`, `encode`, `decode`, `repair`
- `CrossoverPlugin`
  Methods: `crossover`
- `EncodingPlugin`
  Methods: `encode`, `decode`
- `InitPlugin`
  Methods: `initialize`
- `IntegerRepresentation`
  Methods: `add_constraint`, `check_constraints`, `encode`, `decode`, `repair`
- `MixedRepresentation`
  Methods: `encode`, `decode`
- `MutationPlugin`
  Methods: `mutate`
- `ParallelRepair`
  Methods: `repair`, `repair_batch`
- `PermutationRepresentation`
  Methods: `encode`, `decode`, `generate_random`
- `RepairPlugin`
  Methods: `repair`
- `RepresentationPipeline`
  Methods: `get_context_contract`, `init`, `mutate`, `repair_one`, `encode_batch`, `decode_batch`, `repair_batch`, `mutate_batch`, `decode`, `encode`

### `representation/binary.py`

- `BinaryCapacityRepair`
  Methods: `repair`
- `BinaryInitializer`
  Methods: `initialize`
- `BinaryRepair`
  Methods: `repair`
- `BitFlipMutation`
  Methods: `mutate`

### `representation/constraints.py`

- `BoundConstraint`
  Methods: `check`, `repair`

### `representation/context_mutators.py`

- `ContextRouterMutator`
  Methods: `mutate`
- `ContextSelectMutator`
  Methods: `mutate`
- `SerialMutator`
  Methods: `mutate`

### `representation/continuous.py`

- `ClipRepair`
  Methods: `repair`
- `ContextGaussianMutation`
  Methods: `mutate`
- `GaussianMutation`
  Methods: `mutate`
- `PolynomialMutation`
  Methods: `mutate`
- `ProjectionRepair`
  Methods: `repair`
- `SBXCrossover`
  Methods: `crossover`
- `UniformInitializer`
  Methods: `initialize`

### `representation/dynamic.py`

- `DynamicRepair`
  Methods: `repair`

### `representation/graph.py`

- `GraphConnectivityRepair`
  Methods: `repair`
- `GraphDegreeRepair`
  Methods: `repair`
- `GraphEdgeInitializer`
  Methods: `initialize`
- `GraphEdgeMutation`
  Methods: `mutate`

### `representation/integer.py`

- `IntegerInitializer`
  Methods: `initialize`
- `IntegerMutation`
  Methods: `mutate`
- `IntegerRepair`
  Methods: `repair`

### `representation/matrix.py`

- `IntegerMatrixInitializer`
  Methods: `initialize`
- `IntegerMatrixMutation`
  Methods: `mutate`
- `MatrixBlockSumRepair`
  Methods: `repair`
- `MatrixRowColSumRepair`
  Methods: `repair`
- `MatrixSparsityRepair`
  Methods: `repair`

### `representation/orchestrator.py`

- `PipelineOrchestrator`
  Methods: `mutate`, `repair`

### `representation/permutation.py`

- `OrderCrossover`
  Methods: `crossover`
- `PMXCrossover`
  Methods: `crossover`
- `PermutationFixRepair`
  Methods: `repair`
- `PermutationInitializer`
  Methods: `initialize`
- `PermutationInversionMutation`
  Methods: `mutate`
- `PermutationRepair`
  Methods: `repair`
- `PermutationSwapMutation`
  Methods: `mutate`
- `RandomKeyInitializer`
  Methods: `initialize`
- `RandomKeyMutation`
  Methods: `mutate`
- `RandomKeyPermutationDecoder`
  Methods: `decode`, `encode`
- `TwoOptMutation`
  Methods: `mutate`
