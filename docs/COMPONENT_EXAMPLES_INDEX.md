# Component -> Example Map

> 目的：让每个组件都能在示例里“对号入座”，方便快速定位用法与组合方式。

## 覆盖策略（阶段性）
- Bias：统一用 `examples/bias_gallery_demo.py` 覆盖全部 `bias.*`（按 catalog key 选择）。
- Plugin：统一用 `examples/plugin_gallery_demo.py` 覆盖全部 `plugin.*`（按 catalog key 选择）。
- Adapter / Representation / Wiring：优先用“真实可运行模板”覆盖，缺口逐步补齐。

## Adapters

- `SimulatedAnnealingAdapter` -> `examples/template_continuous_constrained.py`, `examples/template_knapsack_binary.py`
- `VNSAdapter` -> `examples/dynamic_multi_strategy_demo.py`, `examples/template_tsp_permutation.py`
- `StrategyRouterAdapter` -> `examples/dynamic_multi_strategy_demo.py`, `examples/multi_strategy_coop_demo.py`
- `MOEADAdapter` -> `examples/template_multiobjective_pareto.py`, `examples/template_portfolio_pareto.py`
- `TrustRegionDFOAdapter` -> `examples/trust_region_dfo_demo.py`
- `TrustRegionSubspaceAdapter` -> `examples/trust_region_subspace_demo.py`
- `TrustRegionNonSmoothAdapter` -> `examples/trust_region_nonsmooth_demo.py`
- `TrustRegionMODFOAdapter` -> `examples/trust_region_mo_dfo_demo.py`
- `MASAdapter` -> `examples/mas_demo.py`
- `CompositeAdapter` -> `examples/composable_solver_fusion_demo.py`
- `RoleAdapter` / `RoleRouterAdapter` -> `examples/role_adapters_demo.py`
- `AStarAdapter` -> `examples/astar_demo.py`
- `MOAStarAdapter` -> `examples/moa_star_demo.py`

## Pipelines / Representations

- Continuous (Uniform/Clip/ContextGaussian) -> `examples/template_continuous_constrained.py`
- Binary + Capacity repair -> `examples/template_knapsack_binary.py`
- Permutation + 2-opt -> `examples/template_tsp_permutation.py`
- Graph (connectivity/degree repair) -> `examples/template_graph_path.py`
- Matrix row/col sum repair -> `examples/template_assignment_matrix.py`, `examples/template_production_schedule_simple.py`
- Simplex repair (sum=1) -> `examples/template_portfolio_pareto.py`
- DynamicRepair -> `examples/dynamic_repair_demo.py`
- ProjectionRepair -> `examples/dynamic_penalty_projection_demo.py`

- `ParallelRepair` -> `examples/parallel_repair_demo.py`

## Biases

- 全部 `bias.*` -> `examples/bias_gallery_demo.py`
- 动态惩罚偏置 -> `examples/dynamic_penalty_projection_demo.py`, `examples/template_continuous_constrained.py`
- 风险偏置（CVaR）-> `examples/risk_bias_demo.py`
- 结构先验 -> `examples/structure_prior_mo_demo.py`

## Plugins

- 全部 `plugin.*` -> `examples/plugin_gallery_demo.py`
- `BenchmarkHarnessPlugin` -> 多数示例（如 `examples/dynamic_multi_strategy_demo.py`）
- `ModuleReportPlugin` -> 多数示例（如 `examples/dynamic_multi_strategy_demo.py`）
- `DynamicSwitchPlugin` -> `examples/dynamic_multi_strategy_demo.py`
- `ParetoArchivePlugin` -> `examples/template_multiobjective_pareto.py`, `examples/template_portfolio_pareto.py`
- `MonteCarloEvaluationProviderPlugin` -> `examples/monte_carlo_dp_robust_demo.py`
- `MultiFidelityEvaluationProviderPlugin` -> `examples/multi_fidelity_demo.py`
- `SurrogateEvaluationProviderPlugin` -> `examples/surrogate_plugin_demo.py`
- `SensitivityAnalysisPlugin` -> `examples/dynamic_multi_strategy_demo.py`

## Wiring Helpers

- `utils/wiring/ray_parallel.py` -> `examples/ray_parallel_demo.py`
- `adapter.vns` + `repr.context_switch` -> `examples/template_tsp_permutation.py`
- `plugin.benchmark_harness` -> 多数模板/示例
- `plugin.module_report` -> 多数模板/示例
- `plugin.dynamic_switch` -> `examples/dynamic_multi_strategy_demo.py`

## Problem Templates (ready-to-run)

- Continuous constrained -> `examples/template_continuous_constrained.py`
- Binary knapsack -> `examples/template_knapsack_binary.py`
- TSP permutation -> `examples/template_tsp_permutation.py`
- Graph path/repair -> `examples/template_graph_path.py`
- Assignment matrix -> `examples/template_assignment_matrix.py`
- Production scheduling (simple) -> `examples/template_production_schedule_simple.py`
- Portfolio Pareto -> `examples/template_portfolio_pareto.py`
- Multi-objective Pareto -> `examples/template_multiobjective_pareto.py`

## Tools

- `solver.blank` -> `examples/blank_solver_plugin_demo.py`, `examples/blank_vs_composable_demo.py`
- `solver.composable` -> `examples/composable_solver_fusion_demo.py`
- `solver.nsga2` -> `examples/nsga2_solver_demo.py`
- `tool.parallel_evaluator` -> `examples/parallel_evaluator_demo.py`
- `tool.context_keys` -> `examples/context_keys_demo.py`
- `tool.context_schema` -> `examples/context_schema_demo.py`
- `tool.logging` -> `examples/logging_demo.py`
- `tool.metrics` -> `examples/metrics_demo.py`
- `tool.dynamic_cli_signal` -> `examples/dynamic_cli_signal_demo.py`
