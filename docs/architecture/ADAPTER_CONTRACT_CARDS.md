# Adapter 契约卡（全量）

这份表是 adapter 层的统一契约视图，核心目的是把“能组合”变成“可审计”。

列说明：

- `Recovery`：checkpoint 恢复等级（L0/L1/L2）
- `Requires/Provides/Mutates`：Context 合同
- `Recovery Notes`：恢复边界（恢复到什么程度）

| Adapter | Recovery | Requires | Provides | Mutates | Recovery Notes |
| --- | --- | --- | --- | --- | --- |
| AStarAdapter | L0 | generation | - | - | Checkpoint restores summary only (best/found), not full open/closed frontier. |
| AsyncEventDrivenAdapter | L1 | generation | event_queue, event_inflight, event_archive, event_history, event_shared | event_queue, event_inflight, event_archive, event_history, event_shared | Restores queue/inflight/archive/history snapshots; external side effects are not replayed. |
| CompositeAdapter | L1 | - | - | - | Restores child adapter snapshots via adapter.get_state()/set_state(). |
| DifferentialEvolutionAdapter | L2 | generation | strategy_id, adapter_best_score, best_x, best_objective | - | Restores internal population/objectives/violations for deterministic continuation. |
| GradientDescentAdapter | L1 | - | mutation_sigma, adapter_best_score | - | Restores current point/score and learning rate; finite-difference probe cache is recomputed. |
| MASAdapter | L1 | generation | - | - | Restores adaptive center; surrogate/model cache is expected from context providers. |
| MOAStarAdapter | L0 | generation | - | - | Checkpoint restores summary only; label/open structures are not reconstructed. |
| MOEADAdapter | L0 | generation | moead_subproblem, moead_weight, moead_neighbor_mode | - | No adapter-owned runtime state is guaranteed to roundtrip. |
| RoleRouterAdapter | L1 | generation | role, role_index, role_reports, candidate_roles | role_reports, candidate_roles | Restores child role adapter snapshots keyed by role name. |
| StrategyRouterAdapter | L0 | generation | shared, strategy, strategy_id, role, role_index, role_adapter, task, phase, region_id, region_bounds, seeds, role_reports, candidate_roles, candidate_units, unit_tasks | shared, role_reports, candidate_roles, candidate_units, unit_tasks | No adapter-owned runtime state is guaranteed to roundtrip. |
| NSGA2Adapter | L2 | - | best_x, best_objective | - | Restores population/objectives/violations and ranking state for deterministic continuation. |
| NSGA3Adapter | L2 | - | best_x, best_objective, mo_weights | - | Restores population/objectives/violations and ranking state for deterministic continuation. |
| PatternSearchAdapter | L1 | - | mutation_sigma, adapter_best_score | - | Restores incumbent point/score and step size; direction samples are regenerated. |
| RoleAdapter | L1 | - | role, role_adapter | - | Restores role metadata and delegates inner adapter state restore. |
| SPEA2Adapter | L2 | - | - | - | Inherits NSGA-II population snapshot roundtrip and SPEA2 selection parameters. |
| SimulatedAnnealingAdapter | L1 | generation | temperature, mutation_sigma | - | Restores annealing temperature and incumbent state; random stream continues from solver RNG state. |
| SingleTrajectoryAdaptiveAdapter | L1 | generation | single_traj_state, single_traj_sigma | single_traj_state, single_traj_sigma | Restores trajectory incumbent/best state and adaptive sigma history. |
| TrustRegionDFOAdapter | L1 | generation | - | - | Restores center/radius/best score and subclass extra state. |
| TrustRegionMODFOAdapter | L1 | generation | - | - | Restores center/radius/best score and subclass extra state. |
| TrustRegionNonSmoothAdapter | L1 | generation | - | - | Restores center/radius/best score and subclass extra state. |
| TrustRegionSubspaceAdapter | L1 | generation | - | - | Restores center/radius/best score and subclass extra state. |
| VNSAdapter | L1 | generation | vns_k, mutation_sigma | - | Restores neighborhood index and incumbent state; candidate batch cache is recomputed. |

## A*/MOA* 语义边界（重点）

- 当前两者定位是 `A*-inspired frontier search`，不是“默认严格教科书 A* 证明模式”。
- 多目标场景默认走工程可组合语义，不承诺单一全局最优。
- 如果需要严格单目标证明模式，需在问题定义、代价定义、启发式前提和停止规则上额外收紧。
