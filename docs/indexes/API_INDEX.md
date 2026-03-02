# API Index (Strict)

This index lists the concrete API entrypoints and their locations. It is intentionally explicit.
Use this as the definitive map for import paths and stable entrypoints.

---

## 1) Core solver entrypoints

- `core/solver.py`
  - `EvolutionSolver`
- `core/composable_solver.py`
  - `ComposableSolver`
- `core/blank_solver.py`
  - `SolverBase`

## 2) Problem / interfaces

- `core/base.py`
  - `BlackBoxProblem`
- `core/interfaces.py`
  - `BiasInterface`, `RepresentationInterface`, `PluginInterface`, `VisualizationInterface`

## 3) Representation pipeline

- `representation/base.py`
  - `RepresentationPipeline`
  - `ParallelRepair`
- `representation/__init__.py` (common plugins)
  - `UniformInitializer`, `GaussianMutation`, `ContextGaussianMutation`, `ClipRepair`, `ProjectionRepair`
  - `DynamicRepair`
  - `IntegerInitializer`, `IntegerMutation`, `IntegerRepair`
  - `PermutationInitializer`, `PermutationRepair`, `PermutationFixRepair`, `PermutationSwapMutation`, `PermutationInversionMutation`, `TwoOptMutation`
  - `OrderCrossover`, `PMXCrossover`, `RandomKeyInitializer`, `RandomKeyMutation`, `RandomKeyPermutationDecoder`
  - `BinaryInitializer`, `BinaryRepair`, `BitFlipMutation`, `BinaryCapacityRepair`
  - `GraphEdgeInitializer`, `GraphEdgeMutation`, `GraphConnectivityRepair`, `GraphDegreeRepair`
  - `IntegerMatrixInitializer`, `IntegerMatrixMutation`, `MatrixRowColSumRepair`, `MatrixSparsityRepair`, `MatrixBlockSumRepair`
  - `BoundConstraint`, `ContextSwitchMutator`

## 4) Bias system

- `bias/bias_module.py`
  - `BiasModule`
- `bias/core/base.py`
  - `BiasBase`, `AlgorithmicBias`, `DomainBias`, `OptimizationContext`
- `bias/core/manager.py`
  - `UniversalBiasManager`, `AlgorithmicBiasManager`, `DomainBiasManager`
- `bias/core/registry.py`
  - `BiasRegistry`, `get_bias_registry`, `register_algorithmic_bias`, `register_domain_bias`, `register_bias_factory`
- `bias/__init__.py`
  - re-exports of common biases and managers

## 5) Adapter system (ComposableSolver)

- `core/adapters/__init__.py`
  - `AlgorithmAdapter`, `CompositeAdapter`
  - `RoleAdapter`, `MultiRoleControllerAdapter`
  - `VNSAdapter`, `VNSConfig`
  - `MOEADAdapter`, `MOEADConfig`
  - `SimulatedAnnealingAdapter`, `SAConfig`
  - `MultiStrategyControllerAdapter`, `MultiStrategyConfig`, `StrategySpec`, `RoleSpec`
  - `AStarAdapter`, `AStarConfig`
  - `MOAStarAdapter`, `MOAStarConfig`
  - `TrustRegionDFOAdapter`, `TrustRegionDFOConfig`
  - `TrustRegionMODFOAdapter`, `TrustRegionMODFOConfig`
  - `TrustRegionSubspaceAdapter`, `TrustRegionSubspaceConfig`
  - `TrustRegionNonSmoothAdapter`, `TrustRegionNonSmoothConfig`
  - `TrustRegionBaseAdapter` (shared trust-region base in `core/adapters/trust_region_base.py`)
  - `SingleTrajectoryAdaptiveAdapter` (in `core/adapters/single_trajectory_adaptive.py`)
  - `AsyncEventDrivenAdapter` (in `core/adapters/async_event_driven.py`)
  - `MASAdapter`, `MASConfig`

## 6) Plugins (capabilities)

- `plugins/__init__.py`
  - `Plugin`, `PluginManager`
  - `BasicElitePlugin`, `HistoricalElitePlugin`
  - `DiversityInitPlugin`
  - `ConvergencePlugin`
  - `MemoryPlugin`
  - `AdaptiveParametersPlugin`
  - `SurrogateEvaluationPlugin`, `SurrogateEvaluationConfig`
  - `MultiFidelityEvaluationPlugin`, `MultiFidelityEvaluationConfig`
  - `MonteCarloEvaluationPlugin`, `MonteCarloEvaluationConfig`
  - `ParetoArchivePlugin`, `ParetoArchiveConfig`
  - `BenchmarkHarnessPlugin`, `BenchmarkHarnessConfig`
  - `ModuleReportPlugin`, `ModuleReportConfig`
  - `ProfilerPlugin`, `ProfilerConfig`
  - `DynamicSwitchPlugin`
  - `SensitivityAnalysisPlugin`, `SensitivityAnalysisConfig`, `SensitivityParam`
  - `MASModelPlugin`, `MASModelConfig`
  - `SubspaceBasisPlugin`, `SubspaceBasisConfig`
  - `CheckpointResumePlugin`, `CheckpointResumeConfig`

## 7) Suites (authority wiring)

- `utils/suites/__init__.py`
  - `attach_monte_carlo_robustness`
  - `attach_moead`
  - `attach_simulated_annealing`
  - `attach_vns`
  - `attach_multi_strategy_coop`
  - `attach_benchmark_harness`
  - `attach_module_report`
  - `attach_nsga2_engineering`
  - `attach_ray_parallel`
  - `attach_dynamic_switch`
  - `attach_trust_region_mo_dfo`
  - `attach_trust_region_subspace_frontier`
  - `attach_active_learning_surrogate`
  - `attach_robust_dfo`
  - `attach_surrogate_assisted_ea`
  - `attach_surrogate_model_lab`
  - `attach_structure_prior_mo`
  - `attach_multi_fidelity_eval`
  - `attach_risk_cvar`
  - `attach_checkpoint_resume`

## 8) Catalog (discoverability)

- `catalog/registry.py`
  - `Catalog` registry and entries
- `catalog/entries.toml`
  - external entries source
- CLI:
  - `python -m nsgablack catalog search <query>`
  - `python -m nsgablack catalog show <key>`

## 9) Run Inspector (UI)

- `utils/viz/visualizer_tk.py`
  - `launch_from_entry(entry)`
  - `launch_from_builder(build_solver)`
  - `maybe_launch_ui(build_solver)`

## 10) Parallel evaluation

- `utils/parallel/evaluator.py`
  - `ParallelEvaluator`
- `utils/parallel/integration.py`
  - integration helpers for solver wiring

## 11) Engineering / runtime utilities

- `utils/engineering/config_loader.py`
- `utils/engineering/logging_config.py`
- `utils/engineering/experiment.py`
- `utils/engineering/file_io.py` — `atomic_write_json` (crash-safe JSON writes)
- `utils/engineering/schema_version.py` — `stamp_schema`, `schema_check`, `require_schema`, `SCHEMA_VERSIONS`
- `utils/runtime/dependencies.py`
- `utils/runtime/imports.py`
- `utils/context/context_schema.py`
- `utils/context/context_keys.py`
- `utils/context/context_field_governance.py` — `is_canonical_context_key`, `CONTEXT_FIELD_SCHEMA_NAME/VERSION`
- `utils/context/context_contracts.py` — `collect_solver_contracts`, `detect_context_conflicts`, `get_component_contract`

---

Notes:
- For stability promises, see `docs/project/STABLE_API_SURFACE.md`.
- For discoverability, see `docs/user_guide/catalog.md`.
- For decomposition rules, see `DECOMPOSITION_RULES.md`.
