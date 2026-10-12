# Adapter 契约卡（全量）

2026-10-08，按当前源码的类声明生成；含 31 个原主干 Adapter 类，非 Catalog 数量统计。

Unit 由算法管线构建、Adapter 操作；组合器委托各子 binding。详细行为见 [算法 Unit 说明](../guides/ALGORITHM_UNITS_CN.md)。

## AStarAdapter

- Unit：`nsgablack.search_node`；Recovery：`L1`。
- 所需构建操作：`fresh`, `spawn`。
- `context_requires`：`generation`。
- `context_provides`：空。
- `context_mutates`：空。
- 恢复边界：Restores node Units, open/closed frontier and pending parent identities.

## AlgorithmAdapter

- Unit：`external`；Recovery：`L0`。
- 所需构建操作：由子 Adapter 声明或无自有构建操作。
- `context_requires`：空。
- `context_provides`：空。
- `context_mutates`：空。
- 恢复边界：No adapter-owned runtime state is guaranteed to roundtrip.

## AsyncEventDrivenAdapter

- Unit：`delegated`；Recovery：`L2`。
- 所需构建操作：由子 Adapter 声明或无自有构建操作。
- `context_requires`：`generation`。
- `context_provides`：`event_queue`, `event_inflight`, `event_archive`, `event_history`, `event_shared`。
- `context_mutates`：`event_queue`, `event_inflight`, `event_archive`, `event_history`, `event_shared`。
- 恢复边界：Restores event state plus stable strategy population partitions, tokens, and child adapter states.

## CompositeAdapter

- Unit：`delegated`；Recovery：`L2`。
- 所需构建操作：由子 Adapter 声明或无自有构建操作。
- `context_requires`：空。
- `context_provides`：空。
- `context_mutates`：空。
- 恢复边界：Restores stable child population partitions, tokens, and child adapter states.

## DifferentialEvolutionAdapter

- Unit：`nsgablack.differential_population`；Recovery：`L2`。
- 所需构建操作：`initialize`。
- `context_requires`：`generation`。
- `context_provides`：`strategy_id`, `adapter_best_score`, `adapter_best_x`, `adapter_best_objectives`。
- `context_mutates`：空。
- 恢复边界：Restores internal population/objectives/violations for deterministic continuation.

## EliteRetentionAdapter

- Unit：`nsgablack.elite_archive`；Recovery：`L2`。
- 所需构建操作：`initialize`。
- `context_requires`：空。
- `context_provides`：空。
- `context_mutates`：空。
- 恢复边界：Delegates population authority and checkpoints a bounded elite archive.

## FixedCandidateAdapter

- Unit：`nsgablack.candidate_unit`；Recovery：`L0`。
- 所需构建操作：`fresh`。
- `context_requires`：空。
- `context_provides`：空。
- `context_mutates`：空。
- 恢复边界：Restores current candidate Unit and construction identity; evaluation authority remains with Solver.

## GaussianSearchAdapter

- Unit：`nsgablack.trajectory`；Recovery：`L1`。
- 所需构建操作：`initialize`。
- `context_requires`：空。
- `context_provides`：`mutation_sigma`, `adapter_best_score`。
- `context_mutates`：空。
- 恢复边界：Restores incumbent, feasibility evidence, and exact RNG state.

## GradientDescentAdapter

- Unit：`nsgablack.poll`；Recovery：`L1`。
- 所需构建操作：`initialize`, `poll`。
- `context_requires`：空。
- `context_provides`：`mutation_sigma`, `adapter_best_score`。
- `context_mutates`：空。
- 恢复边界：Restores point, learning rate, probe identities and actual displacement structure.

## GradientOptimizerAdapter

- Unit：`nsgablack.parameters`；Recovery：`L1`。
- 所需构建操作：`initialize`, `optimizer_slots`。
- `context_requires`：空。
- `context_provides`：`mutation_sigma`, `adapter_best_score`。
- `context_mutates`：空。
- 恢复边界：Restores current parameters, optimizer moments, and step index.

## MASAdapter

- Unit：`nsgablack.model_search`；Recovery：`L1`。
- 所需构建操作：`initialize`。
- 所需 builder 方法：`create_model`。
- `context_requires`：`generation`。
- `context_provides`：空。
- `context_mutates`：空。
- 恢复边界：Restores adaptive center; surrogate cache is rebuilt from adapter history.

## MOAStarAdapter

- Unit：`nsgablack.pareto_label`；Recovery：`L1`。
- 所需构建操作：`fresh`。
- `context_requires`：`generation`。
- `context_provides`：空。
- `context_mutates`：空。
- 恢复边界：Restores Pareto labels, frontier, pending parent identities and goals through the Unit codec.

## MOEADAdapter

- Unit：`nsgablack.decomposition`；Recovery：`L2`。
- 所需构建操作：`initialize`, `decomposition`。
- `context_requires`：`generation`。
- `context_provides`：`moead_subproblem`, `moead_weight`, `moead_neighbor_mode`。
- `context_mutates`：空。
- 恢复边界：Restores decomposition population (pop_X/pop_F/pop_V), ideal point, weights and neighborhood. get_state()/set_state() cover scalar parameters; get_population_snapshot()/set_population_snapshot() handle the full solution array.

## MultiRoleControllerAdapter

- Unit：`delegated`；Recovery：`L2`。
- `context_requires`：`generation`。
- `context_provides`：`role`, `role_index`, `role_reports`, `candidate_roles`。
- `context_mutates`：`role_reports`, `candidate_roles`。
- 恢复边界：Restores stable role population partitions, tokens, and role adapter states.

## MultiStrategyControllerAdapter

- Unit：`delegated`；Recovery：`L2`。
- `context_requires`：`generation`。
- `context_provides`：`shared`, `strategy`, `strategy_id`, `role`, `role_index`, `role_adapter`, `task`, `phase`, `region_id`, `region_bounds`, `seeds`, `role_reports`, `candidate_roles`, `candidate_units`, `unit_tasks`, `strategy_instances`。
- 调用作用域：`StrategyTask.from_context(context)` 是局部任务读取面；角色/策略/阶段/区域旧键从原任务统一派生。`unit_tasks` 为按路径组织的轻量摘要，`strategy_instances` 为子实例观测；全局不再展示最后一个子任务。候选来源读取 `StrategyOrigin.from_candidate(state)`。
- `context_mutates`：`shared`, `role_reports`, `candidate_roles`, `candidate_units`, `unit_tasks`。
- 恢复边界：Restores controller policy/accounting state plus stable per-unit population partitions, tokens, and child adapter states.

## NSGA2Adapter

- Unit：`nsgablack.population`；Recovery：`L2`。
- 所需构建操作：`initialize`。
- `context_requires`：空。
- `context_provides`：`adapter_best_x`, `adapter_best_objectives`, `adapter_best_score`。
- `context_mutates`：空。
- 恢复边界：Restores population/objectives/violations and ranking state for deterministic continuation.

## NSGA3Adapter

- Unit：`nsgablack.reference_population`；Recovery：`L2`。
- 所需构建操作：`initialize`, `reference_directions`。
- `context_requires`：空。
- `context_provides`：`adapter_best_x`, `adapter_best_objectives`, `adapter_best_score`, `mo_weights`。
- `context_mutates`：空。
- 恢复边界：Inherits NSGA-II population snapshot roundtrip (get_state/set_state + get_population_snapshot/set_population_snapshot). Reference directions are restored through the configured Unit codec.

## PatternSearchAdapter

- Unit：`nsgablack.poll`；Recovery：`L1`。
- 所需构建操作：`initialize`, `poll`。
- `context_requires`：空。
- `context_provides`：`mutation_sigma`, `adapter_best_score`。
- `context_mutates`：空。
- 恢复边界：Restores incumbent, step size and pipeline-built poll geometry.

## RoleAdapter

- Unit：`delegated`；Recovery：`L2`。
- 所需构建操作：由子 Adapter 声明或无自有构建操作。
- `context_requires`：空。
- `context_provides`：`role`, `role_adapter`。
- `context_mutates`：空。
- 恢复边界：Transparently delegates population/token authority and inner adapter state restore.

## RoleRouterAdapter

- Unit：`delegated`；Recovery：`L2`。
- 所需构建操作：由子 Adapter 声明或无自有构建操作。
- `context_requires`：`generation`。
- `context_provides`：`role`, `role_index`, `role_reports`, `candidate_roles`。
- `context_mutates`：`role_reports`, `candidate_roles`。
- 恢复边界：Restores stable role population partitions, tokens, and role adapter states.

## SPEA2Adapter

- Unit：`nsgablack.population`；Recovery：`L2`。
- 所需构建操作：`initialize`。
- `context_requires`：空。
- `context_provides`：空。
- `context_mutates`：空。
- 恢复边界：Inherits NSGA-II population snapshot roundtrip and SPEA2 selection parameters.

## SimulatedAnnealingAdapter

- Unit：`nsgablack.trajectory`；Recovery：`L1`。
- 所需构建操作：`initialize`。
- `context_requires`：`generation`。
- `context_provides`：`temperature`, `mutation_sigma`。
- `context_mutates`：空。
- 恢复边界：Restores trajectory Unit, annealing temperature and local RNG state.

## SingleTrajectoryAdaptiveAdapter

- Unit：`nsgablack.trajectory`；Recovery：`L1`。
- 所需构建操作：`initialize`。
- `context_requires`：`generation`。
- `context_provides`：`single_traj_state`, `single_traj_sigma`。
- `context_mutates`：`single_traj_state`, `single_traj_sigma`。
- 恢复边界：Restores trajectory incumbent/best state and adaptive sigma history.

## StrategyChainAdapter

- Unit：`delegated`；Recovery：`L2`。
- 所需构建操作：由子 Adapter 声明或无自有构建操作。
- `context_requires`：`generation`。
- `context_provides`：`phase`, `strategy`, `strategy_id`。
- `context_mutates`：空。
- 恢复边界：Restores current phase index, per-phase step counter, and child adapter states.

## StrategyRouterAdapter

- Unit：`delegated`；Recovery：`L2`。
- 所需构建操作：由子 Adapter 声明或无自有构建操作。
- `context_requires`：`generation`。
- `context_provides`：`shared`, `strategy`, `strategy_id`, `role`, `role_index`, `role_adapter`, `task`, `phase`, `region_id`, `region_bounds`, `seeds`, `role_reports`, `candidate_roles`, `candidate_units`, `unit_tasks`。
- `context_mutates`：`shared`, `role_reports`, `candidate_roles`, `candidate_units`, `unit_tasks`。
- 恢复边界：Restores controller policy/accounting state plus stable per-unit population partitions, tokens, and child adapter states.

## TrustRegionBaseAdapter

- Unit：`nsgablack.local_region`；Recovery：`L1`。
- `context_requires`：空。
- `context_provides`：空。
- `context_mutates`：空。
- 恢复边界：Restores center/radius/best score and subclass extra state.

## TrustRegionDFOAdapter

- Unit：`nsgablack.local_region`；Recovery：`L1`。
- 所需构建操作：`initialize`。
- `context_requires`：`generation`。
- `context_provides`：空。
- `context_mutates`：空。
- 恢复边界：Restores center/radius/best score and subclass extra state.

## TrustRegionMODFOAdapter

- Unit：`nsgablack.local_region`；Recovery：`L1`。
- 所需构建操作：`initialize`。
- `context_requires`：`generation`。
- `context_provides`：空。
- `context_mutates`：空。
- 恢复边界：Restores center/radius/best score and subclass extra state.

## TrustRegionNonSmoothAdapter

- Unit：`nsgablack.local_region`；Recovery：`L1`。
- 所需构建操作：`initialize`。
- `context_requires`：`generation`。
- `context_provides`：空。
- `context_mutates`：空。
- 恢复边界：Restores center/radius/best score and subclass extra state.

## TrustRegionSubspaceAdapter

- Unit：`nsgablack.local_region`；Recovery：`L1`。
- 所需构建操作：`initialize`, `basis`。
- `context_requires`：`generation`。
- `context_provides`：空。
- `context_mutates`：空。
- 恢复边界：Restores center/radius/best score and subclass extra state.

## VNSAdapter

- Unit：`nsgablack.candidate_unit`；Recovery：`L1`。
- 所需构建操作：`fresh`, `spawn`。
- 附加槽位 `neighborhood` 构建操作：`initialize`。
- `context_requires`：`generation`。
- `context_provides`：`vns_k`, `mutation_sigma`。
- `context_mutates`：空。
- 恢复边界：Restores neighborhood structure, incumbent/pending Units and identity counter.
