# COMPONENT API INDEX (framework-core)

Generated at: 2026-10-26 10:45:59

2026-10-30 增量补充（其余条目仍保留上述生成时点）：

## `tool.case_inner_runtime_evaluator`
Kind: tool
Title: CaseInnerRuntimeEvaluator
Import: `nsgablack.core:CaseInnerRuntimeEvaluator`
Role: case_evaluator
Runtime operations: evaluate, evaluate_batch
Summary: 完整标准内层 Case 的候选评估；显式投影，批次并发由 Project L0 授权。
Config keys: case_name, projector, max_workers, artifact_bindings, resource_request, budget_request, component_overrides_factory, timeout_seconds, termination
Use when: 外层候选需要完整内层求解后才能评价，或要把一批内层 Case 接到外部 Worker。
Boundaries: 不传可写 Pool/Unit；有 Provider 时保留原仲裁；多机资源不能复制父本机 grant。
Usage: [装配、预算、收据与限制](../architecture/STATE_COST_AND_NESTED_EXECUTION_CN.md)

## `adapter.search_plan`
Kind: adapter
Title: SearchPlanAdapter
Import: `nsgablack.adapters:SearchPlanAdapter`
Role: orchestration
Concepts: GA停滞VNS精修 | GA加VNS | 串行并行 | 多重嵌套 | 编排 | 有限循环
Runtime operations: stage, serial, multi, repeat
Boundaries: 复用共享 ExecutionPlan/ExecutionCursor 与 Router，不再建立资源授权者。 | 停滞触发须显式 until/metrics 或既有阶段策略，serial 顺序本身不推断停滞。 | 精修阶段等待 PoolTask 本请求完成；控制切换不制造逻辑 generation。
Summary: 自然搜索编排：共享可恢复游标表达串行、并行和有限循环；复用唯一算法实例、Router评估与池任务，不手算全局代数。
Tags: adapter, core, composition, orchestration, serial, multi, repeat, pool
Context requires: generation
Context provides: solution_working_pool, shared, strategy, strategy_id, role, role_index, role_adapter, task, phase, region_id, region_bounds, seeds, role_reports, candidate_roles, candidate_units, unit_tasks, strategy_instances
Context mutates: shared, role_reports, candidate_roles, candidate_units, unit_tasks
Context notes: Orchestrates multi-strategy/multi-role cooperation and injects strategy task context. | Shared state is updated every step and exposed via runtime context projection. | StrategyTask owns invocation-local role/strategy/phase/region/seeds aliases; runtime task summaries and strategy_instances are observation only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: plan, strategies, config, working_pool, until, metrics, name, priority
Use when: 重复GA→精修→同GA返回竞争，或需要任意层级serial/multi/repeat与局部额度时。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import SearchPlanAdapter, StrategySpec, stage, serial, repeat | plan = repeat(times=100, body=serial(stage('ga', steps=100), stage('vns', steps=30))) | solver.set_adapter(SearchPlanAdapter(plan, strategies=[StrategySpec(ga, 'ga'), StrategySpec(vns, 'vns')])) | # Pool精修叶省略steps，使用PoolTaskSpec.steps指定每起点额度，等待本次任务全部完成。
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.fixed_candidate`
Kind: adapter
Title: FixedCandidateAdapter
Import: `nsgablack.adapters.fixed_candidate:FixedCandidateAdapter`
Role: adapter
Summary: 固定候选评估策略：把 Representation 生成的单个候选送入标准 Solver 生命周期，不创建第二套控制循环。 / One-shot fixed-candidate evaluation through the canonical Solver lifecycle.
Tags: adapter, core, one-shot, evaluation, provider-neutral
Context notes: Requests and evaluates one initialized candidate per solver step. | Does not mutate, fit, sample, or select a backend.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: initializer
Use when: 诊断、验证或闭式任务仍需统一 cancellation、resource、plugin、result 与 lineage 语义时。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | import numpy as np | from nsgablack.adapters import FixedCandidateAdapter | class FixedSeed: |     stateless = True |     def checkpoint_identity(self): return {'name': 'fixed_seed', 'version': 1} |     def initialize(self, problem, context): return np.array([0.25, 0.75]) | adapter = FixedCandidateAdapter(initializer=FixedSeed()) | solver.set_adapter(adapter)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.gradient_optimizer`
Kind: adapter
Title: GradientOptimizerAdapter
Import: `nsgablack.adapters.gradient_optimizer:GradientOptimizerAdapter`
Role: adapter
Summary: 通用一阶优化：SGD/Adam/AdamW 消费 Provider 梯度，支持普通池精修并交付已评估任务最佳；目标单独投影不冒充梯度变换。Provider slot 事务与资源授权保留原边界。
Tags: adapter, core, gradient, sgd, adam, adamw, provider-neutral, state-transition
Context provides: mutation_sigma, adapter_best_score
Context notes: Device/backend selection belongs to the Evaluation Provider and Project L0 grant.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: config, name, priority, state_gateway, prefer_provider_transition
Use when: Problem/Evaluation Provider 能返回 Feedback.gradients 时。 | 需要让同一个 SGD/Adam/AdamW 策略跨 NumPy、Torch、JAX 或解析梯度 Provider 复用时。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters.gradient_optimizer import GradientOptimizerAdapter | adapter = GradientOptimizerAdapter() | solver.set_adapter(adapter)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.gaussian_search`
Kind: adapter
Title: GaussianSearchAdapter
Import: `nsgablack.adapters.gaussian_search:GaussianSearchAdapter`
Role: adapter
Summary: 高斯随机搜索：支持直接 initializer/结构 repair 与池精修；高斯采样分布仍由算法维护，不声称消费通用 mutator 或 selector。
Tags: adapter, core, black-box, stochastic, gaussian, provider-neutral
Context provides: mutation_sigma, adapter_best_score
Context notes: Candidate decoding and estimator fitting never belong to this Adapter.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: population_size, mutation_scale, initializer, repair
Use when: Problem 只能返回目标/约束，无法提供梯度时。 | 需要在模型参数、结构编码或外部 estimator spec 上复用同一种轻量黑盒搜索时。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import GaussianSearchAdapter, GaussianSearchConfig | adapter = GaussianSearchAdapter(GaussianSearchConfig(population_size=8, mutation_scale=0.1)) | solver.set_adapter(adapter)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.role`
Kind: adapter
Title: RoleAdapter
Import: `nsgablack.adapters.role_adapters:RoleAdapter`
Role: adapter
Summary: 角色包装器：元数据与候选配额协作。 / Adapter: role wrapper with metadata and candidate quotas for cooperation.
Tags: adapter, composition, core, roles, strategy
Context provides: role, role_adapter
Context notes: Role wrapper: injects role metadata and delegates propose/update to inner adapter.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: role, inner, name, priority, max_candidates, context_requires, companions, recommended_suite, strict_contract
Use when: 需要替换或新增搜索策略时
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import RoleAdapter, NSGA2Adapter | role = RoleAdapter('explorer', NSGA2Adapter(), name='coarse') | solver.set_adapter(role)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.multi_role_controller`
Kind: adapter
Title: MultiRoleControllerAdapter
Import: `nsgablack.adapters.role_adapters:MultiRoleControllerAdapter`
Role: adapter
Summary: 多角色控制器：共享上下文与预算调度。 / Adapter: multi-role controller with shared context and budget scheduling.
Tags: adapter, composition, controller, core, roles, strategy
Context requires: generation
Context provides: role, role_index, role_reports, candidate_roles
Context mutates: role_reports, candidate_roles
Context notes: Controller for RoleAdapter set: dispatches candidates and returns role-scoped feedback.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: roles, name, priority
Use when: 需要替换或新增搜索策略时
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import RoleAdapter, NSGA2Adapter, VNSAdapter | from nsgablack.adapters.role_adapters import MultiRoleControllerAdapter | roles = [RoleAdapter('population', NSGA2Adapter()), RoleAdapter('local', VNSAdapter())] | solver.set_adapter(MultiRoleControllerAdapter(roles))
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.composite`
Kind: adapter
Title: CompositeAdapter
Import: `nsgablack.adapters.algorithm_adapter:CompositeAdapter`
Role: adapter
Summary: 组合适配器：合并提案并处理冲突。 / Adapter: composite adapter merging proposals and resolving conflicts.
Tags: adapter, composition, core, strategy
Context notes: Composite adapter: unions child adapter contracts.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: adapters, name, priority
Use when: 需要替换或新增搜索策略时
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import CompositeAdapter, NSGA2Adapter, VNSAdapter | solver.set_adapter(CompositeAdapter([NSGA2Adapter(), VNSAdapter()]))
Methods: propose=ok, update=ok, get_state=ok, set_state=ok, get_population=missing, set_population=missing
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.astar`
Kind: adapter
Title: AStarAdapter
Import: `nsgablack.adapters.astar:AStarAdapter`
Role: adapter
Summary: A* 搜索内核：UnitBinding 构建节点，Adapter 决定扩展与优先级；显式 pool_start_policy='new_root' 从池初始化并保留节点精确版本，不继承旧路径代价。
Tags: adapter, astar, core, graph, heuristic, pathfinding, strategy
Context requires: generation
Context notes: Consumes context for neighbor expansion / heuristic / goal callbacks.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: pool_start_policy, cost_mode, repair_policy
Use when: 需要替换或新增搜索策略时
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | import numpy as np | from nsgablack.adapters import AStarAdapter | def neighbors(state, context): |     return [np.asarray(state) + 1.0] | adapter = AStarAdapter(neighbors=neighbors, start_state=np.array([0.0]), |     goal_test=lambda state, context: state[0] >= 3, |     edge_cost=lambda parent, child, context: 1.0) | solver.set_adapter(adapter)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.moa_star`
Kind: adapter
Title: MOAStarAdapter
Import: `nsgablack.adapters.moa_star:MOAStarAdapter`
Role: adapter
Summary: 多目标 A*：Pareto 标签与支配剪枝；显式 pool_start_policy='new_root' 接入单个池种子，保留精确路径引用，不接受通用标量投影。
Tags: adapter, astar, core, graph, heuristic, multiobjective, pareto, strategy
Context requires: generation
Context notes: Consumes context for neighbor expansion / heuristic / goal callbacks in multi-objective A*.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: pool_start_policy, cost_mode, repair_policy
Use when: 需要替换或新增搜索策略时
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | import numpy as np | from nsgablack.adapters import MOAStarAdapter | def neighbors(state, context): |     return [np.asarray(state) + 1.0] | adapter = MOAStarAdapter(neighbors=neighbors, start_state=np.array([0.0]), |     goal_test=lambda state, context: state[0] >= 3, |     edge_cost=lambda parent, child, context: np.array([1.0, 0.5])) | solver.set_adapter(adapter)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.async_event_driven`
Kind: adapter
Title: AsyncEventDrivenAdapter
Import: `nsgablack.adapters.async_event_driven:AsyncEventDrivenAdapter`
Role: adapter
Summary: 事件队列编排：驱动 propose/update。 / Adapter: event-queue orchestration for propose/update.
Tags: adapter, async, context, controller, event, multi_strategy, orchestration
Context requires: generation
Context provides: event_queue, event_inflight, event_archive, event_history, event_shared
Context mutates: event_queue, event_inflight, event_archive, event_history, event_shared
Context cache: event_history, event_inflight
Context notes: Queue-based controller; strategy-level updates are driven by completion events.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: total_batch_size, target_queue_size, bootstrap_events_per_strategy, max_queue_size, refill_events_per_completion
Use when: 需要异步时序语义（事件流）而非代级同步时。 / Need async temporal semantics (event stream) instead of generation-level sync. | 需要多策略协同且可审计事件历史时。 / Need multi-strategy coordination with auditable event history.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import AsyncEventDrivenAdapter, EventStrategySpec, NSGA2Adapter, VNSAdapter | strategies = [EventStrategySpec(NSGA2Adapter(), 'global'), EventStrategySpec(VNSAdapter(), 'local')] | solver.set_adapter(AsyncEventDrivenAdapter(strategies))
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.single_trajectory_adaptive`
Kind: adapter
Title: SingleTrajectoryAdaptiveAdapter
Import: `nsgablack.adapters.single_trajectory_adaptive:SingleTrajectoryAdaptiveAdapter`
Role: adapter
Summary: 单轨迹自适应搜索：可直接装配初始化、变化、结构修复；selector 的 candidate 选择只选本批候选，接受与步长适应仍由 Adapter 决定。
Tags: adapter, adaptive, local_search, single_trajectory, strategy
Context requires: generation
Context provides: single_traj_state, single_traj_sigma
Context mutates: single_traj_state, single_traj_sigma
Context notes: Maintains one active trajectory; adapts mutation_sigma from success rate.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: batch_size, initial_sigma, target_success_rate, restart_patience, accept_worse_prob, initializer, mutator, selector, repair
Use when: 需要比种群方法更轻量的单轨迹搜索时。 / Need a lighter single-trajectory search than population-based methods. | 需要快速迭代并自动调整局部步长时。 / Need fast iteration with automatic local step-size adjustment.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import SingleTrajectoryAdaptiveAdapter, SingleTrajectoryAdaptiveConfig | solver.set_adapter(SingleTrajectoryAdaptiveAdapter(SingleTrajectoryAdaptiveConfig()))
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.de`
Kind: adapter
Title: DifferentialEvolutionAdapter
Import: `nsgablack.adapters:DifferentialEvolutionAdapter`
Role: adapter
Summary: 差分进化：保留差分供体与交叉，直属 mutator 只处理 trial；selector 在 replacement 位置比较 trial 与提案时冻结目标，不做全局种群选择。
Tags: adapter, core, de, differential_evolution, evolutionary, strategy
Context requires: generation
Context provides: strategy_id, adapter_best_score, adapter_best_x, adapter_best_objectives
Context notes: DE adapter maintains internal population state and performs greedy replacement. | Population write-back is exposed through set_population_snapshot().
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: population_size, batch_size, differential_weight, crossover_rate, strategy, objective_aggregation, initializer, mutator, selector, repair
Use when: 连续变量优化且希望简单稳定的差分变异时 | 需要快速基线而非复杂控制逻辑时
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import DifferentialEvolutionAdapter | from nsgablack.representation import UniformInitializer, GaussianMutation | solver.set_adapter(DifferentialEvolutionAdapter(initializer=UniformInitializer(), mutator=GaussianMutation(sigma=0.05))) | # selector is optional: select one row from [proposal-time target, evaluated trial].
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.gradient_descent`
Kind: adapter
Title: GradientDescentAdapter
Import: `nsgablack.adapters:GradientDescentAdapter`
Role: adapter
Summary: 有限差分精修：起点、成对探针、下降提案各自评估；支持普通／投影池任务，不把探针分数套给未评估的新点。
Tags: adapter, core, gradient, gradient_descent, local_search, strategy
Context provides: mutation_sigma, adapter_best_score
Context notes: Finite-difference local search; emits current step size in context.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: learning_rate, epsilon, max_directions, lr_growth, lr_decay, min_lr, objective_aggregation, repair_policy, initializer, repair
Use when: 需要在候选附近做快速局部下降精修时 | 可以接受有限差分带来的额外评估开销时
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import GradientDescentAdapter | solver.set_adapter(GradientDescentAdapter())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.mas`
Kind: adapter
Title: MASAdapter
Import: `nsgablack.adapters:MASAdapter`
Role: adapter
Summary: Model-and-Search：支持普通／投影池精修，明确起点与任务最佳；代理模型历史按精确版本保存和裁剪，不隐式借其他算法的全局最优点。
Tags: adapter, core, local_search, mas, strategy, surrogate
Context requires: generation
Context notes: Optional model-assisted search using internal surrogate.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: batch_size, exploration_ratio, enable_surrogate, surrogate_model_type, surrogate_min_train_samples, surrogate_max_train_samples, surrogate_retrain_every_call, random_seed
Use when: 希望在线更新轻量模型并引导局部搜索时 | 评估昂贵，想优先在模型建议区域探索时
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import MASAdapter | solver.set_adapter(MASAdapter())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.moead`
Kind: adapter
Title: MOEADAdapter
Import: `nsgablack.adapters:MOEADAdapter`
Role: adapter
Summary: MOEA/D：方向与邻域仍归 Adapter，自动发布投影子池；change=普通函数可替换完整变化并组合交叉/变异，或独立装配 initializer/mutator/repair；replacement selector 保留目标方向权重、ideal 与 nr 限制。
Tags: adapter, core, decomposition, moead, multiobjective, strategy
Context requires: generation
Context provides: moead_subproblem, moead_weight, moead_neighbor_mode
Context notes: MOEA/D writes decomposition subproblem metadata into context for variation/repair plugins.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: population_size, neighborhood_size, batch_size, delta, nr, decomposition, variation, de_F, de_CR, random_seed, initializer, mutator, selector, repair, change, pool_maintenance
Use when: 多目标问题希望用分解子问题并行推进时 | 需要稳定的邻域协同更新而非全局排序时
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import MOEADAdapter | from nsgablack.representation import GaussianMutation | solver.set_adapter(MOEADAdapter(mutator=GaussianMutation(sigma=0.1))) | # Omit selector to retain feasibility-first directional replacement and nr.
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.multi_strategy`
Kind: adapter
Title: StrategyRouterAdapter
Import: `nsgablack.adapters:StrategyRouterAdapter`
Role: adapter
Summary: 多策略控制器：StrategyTask 隔离子任务，StrategyOrigin 记录来源；working_pool 绑定普通工作区，未指定输入的池任务继承最近组合来源，新接纳候选进入最近工作区。
Tags: adapter, controller, cooperation, core, multi_strategy, parallel, roles, strategy
Context requires: generation
Context provides: solution_working_pool, shared, strategy, strategy_id, role, role_index, role_adapter, task, phase, region_id, region_bounds, seeds, role_reports, candidate_roles, candidate_units, unit_tasks, strategy_instances
Context mutates: shared, role_reports, candidate_roles, candidate_units, unit_tasks
Context notes: Orchestrates multi-strategy/multi-role cooperation and injects strategy task context. | Shared state is updated every step and exposed via runtime context projection. | StrategyTask owns invocation-local role/strategy/phase/region/seeds aliases; runtime task summaries and strategy_instances are observation only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: roles, working_pool, total_batch_size, phase_schedule, seed
Use when: 需要编排多策略单元并共享状态时 | 需要支持自适应权重的协同控制时
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import StrategyRouterAdapter, StrategySpec, NSGA2Adapter, VNSAdapter | strategies = [StrategySpec(NSGA2Adapter(), 'global'), StrategySpec(VNSAdapter(), 'local')] | solver.set_adapter(StrategyRouterAdapter(strategies))
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.nsga2`
Kind: adapter
Title: NSGA2Adapter
Import: `nsgablack.adapters:NSGA2Adapter`
Role: adapter
Summary: NSGA-II：独立装配初始化、变化、父代来源与结构修复；parent_selector 返回精确引用，selector 的 survivor 位置返回合并种群行号，省略时保留非支配排序与拥挤度。
Tags: adapter, core, evolutionary, multiobjective, nsga2, strategy
Context provides: adapter_best_x, adapter_best_objectives, adapter_best_score
Context notes: Population-based NSGA-II adapter with propose/update loop.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: population_size, offspring_size, crossover_rate, objective_aggregation, initializer, selector, repair, parent_selector, mutator, change, pool_maintenance
Use when: 标准多目标演化基线，需要稳健 Pareto 前沿维护时 | 希望在收敛与多样性之间取得平衡时 | 需要混合已发布子池父代或直接装配变异组件，而不重写整个 Adapter 时
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import NSGA2Adapter | solver.set_adapter(NSGA2Adapter())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.nsga3`
Kind: adapter
Title: NSGA3Adapter
Import: `nsgablack.adapters:NSGA3Adapter`
Role: adapter
Summary: NSGA-III：参考点生存选择；继承 NSGA 独立初始化、变化、精确父代与结构修复，显式 selector 覆盖 survivor 位置，默认保留参考方向生态位。
Tags: adapter, core, evolutionary, multiobjective, nsga3, strategy
Context provides: adapter_best_x, adapter_best_objectives, adapter_best_score, mo_weights
Context notes: NSGA-III style adapter with reference-point niching in environmental selection.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: population_size, offspring_size, divisions, crossover_rate, objective_aggregation, initializer, mutator, parent_selector, selector, repair, change, pool_maintenance
Use when: 高维多目标（>=3 目标）需要参考点引导覆盖时 | 希望提升前沿分布均匀性时
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import NSGA3Adapter | solver.set_adapter(NSGA3Adapter())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.pattern_search`
Kind: adapter
Title: PatternSearchAdapter
Import: `nsgablack.adapters:PatternSearchAdapter`
Role: adapter
Summary: 坐标模式搜索：初始化与结构修复可独立装配，candidate selector 选已评估轮询点；坐标几何、实际位移与步长更新仍属于算法。
Tags: adapter, core, local_search, pattern_search, strategy
Context provides: mutation_sigma, adapter_best_score
Context notes: Coordinate pattern search with adaptive step-size.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: max_directions, step_size, expansion, contraction, min_step, objective_aggregation, initializer, selector, repair
Use when: 目标不可导或噪声较大，梯度不可用时 | 需要轻量坐标方向搜索作为局部改进器时
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import PatternSearchAdapter | solver.set_adapter(PatternSearchAdapter())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.sa`
Kind: adapter
Title: SimulatedAnnealingAdapter
Import: `nsgablack.adapters:SimulatedAnnealingAdapter`
Role: adapter
Summary: 模拟退火：独立装配初始化、变化与结构修复；selector 仅通过 proposal_order 重排本批邻域，Metropolis 接受与温度调度仍由 Adapter 执行。
Tags: adapter, core, local_search, sa, simulated_annealing, strategy
Context requires: generation
Context provides: temperature, mutation_sigma
Context notes: SA writes temperature and optional sigma into context for mutator scheduling.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: batch_size, initial_temperature, cooling_rate, min_temperature, base_sigma, sigma_temperature_scale, objective_aggregation, random_seed, initializer, mutator, selector, repair
Use when: 需要允许小概率接受劣解以跳出局部最优时 | 希望通过温度控制探索-收敛节奏时
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import SimulatedAnnealingAdapter | from nsgablack.representation import ContextGaussianMutation | solver.set_adapter(SimulatedAnnealingAdapter(mutator=ContextGaussianMutation())) | # Omit selector to retain the native proposal order and Metropolis rule.
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.spea2`
Kind: adapter
Title: SPEA2Adapter
Import: `nsgablack.adapters:SPEA2Adapter`
Role: adapter
Summary: SPEA2：强度与密度生存选择；继承独立初始化、变化、精确父代与结构修复，selector 明确覆盖 survivor 而非父代来源。
Tags: adapter, core, evolutionary, multiobjective, spea2, strategy
Context notes: SPEA2 adapter using strength + density fitness for environmental selection.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: population_size, offspring_size, crossover_rate, objective_aggregation, archive_size, k_nearest, initializer, mutator, parent_selector, selector, repair, change, pool_maintenance
Use when: 需要精英保留 + 强度密度联合选择时 | 希望作为 NSGA 系列的对照方法时
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import SPEA2Adapter | solver.set_adapter(SPEA2Adapter())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.trust_region_dfo`
Kind: adapter
Title: TrustRegionDFOAdapter
Import: `nsgablack.adapters:TrustRegionDFOAdapter`
Role: adapter
Summary: 信赖域无梯度精修：支持普通／投影池任务，起点先评估，邻域修复守半径，交付精确已评估结果。
Tags: adapter, core, dfo, local_search, strategy, trust_region
Context requires: generation
Context notes: Trust-region local search; context is only used as runtime metadata.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: batch_size, initial_radius, min_radius, max_radius
Use when: 目标不可导且需要稳定局部改进时 | 希望在受控半径内做无梯度精修时
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import TrustRegionDFOAdapter | solver.set_adapter(TrustRegionDFOAdapter())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.trust_region_mo_dfo`
Kind: adapter
Title: TrustRegionMODFOAdapter
Import: `nsgablack.adapters:TrustRegionMODFOAdapter`
Role: adapter
Summary: 多目标信赖域 DFO：原生任务冻结权重，外部投影采用冻结任务规则；普通换方向先重评分历史向量，支持精确池结果。
Tags: adapter, core, dfo, multiobjective, strategy, trust_region
Context requires: generation
Context notes: Optional key mo_weights can provide external scalarization weights.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: batch_size, initial_radius, scalarization, weights
Use when: 多目标问题需要局部信赖域精修并保持 Pareto 导向时 | 希望把多目标优化与局部 DFO 结合时
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import TrustRegionMODFOAdapter | solver.set_adapter(TrustRegionMODFOAdapter())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.trust_region_nonsmooth`
Kind: adapter
Title: TrustRegionNonSmoothAdapter
Import: `nsgablack.adapters:TrustRegionNonSmoothAdapter`
Role: adapter
Summary: 非光滑信赖域：原生 Linf 聚合；投影池任务采用明确比较坐标，保留原始反馈与精确结果。
Tags: adapter, core, local_search, nonsmooth, strategy, trust_region
Context requires: generation
Context notes: Non-smooth trust-region search with L1/Linf objective aggregation.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: batch_size, initial_radius, min_radius, aggregation
Use when: 目标非光滑或带 max/Linf 类聚合项时 | 需要比纯随机局部扰动更稳的非光滑精修时
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import TrustRegionNonSmoothAdapter | solver.set_adapter(TrustRegionNonSmoothAdapter())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.trust_region_subspace`
Kind: adapter
Title: TrustRegionSubspaceAdapter
Import: `nsgablack.adapters:TrustRegionSubspaceAdapter`
Role: adapter
Summary: 子空间信赖域：使用本任务实际接纳的有界参考样本，裁剪保持子空间；支持普通／投影池精修与精确引用保留。
Tags: adapter, core, dfo, strategy, subspace, trust_region
Context requires: generation
Context notes: Adapter schedules basis refresh from its own accepted task samples; the algorithm pipeline constructs the basis.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: batch_size, subspace_dim, basis_method, min_samples, sample_limit, initial_radius, resample_every
Use when: 高维变量空间需要降维后再做局部精修时 | 希望把评估预算聚焦到主导子空间时
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import TrustRegionSubspaceAdapter | solver.set_adapter(TrustRegionSubspaceAdapter())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.vns`
Kind: adapter
Title: VNSAdapter
Import: `nsgablack.adapters:VNSAdapter`
Role: adapter
Summary: VNS 多邻域精修：change=普通函数可组合完整邻域变化；或独立 initializer/mutator 与 candidate selector。改进判断和邻域切换仍归 VNS；未声明通用结构 repair 角色。
Tags: adapter, core, local_search, refinement, stage, strategy, vns
Context requires: generation
Context provides: vns_k, mutation_sigma
Context notes: VNS writes neighborhood index/sigma into per-step context for mutator consumption. | Use context-aware mutator to make neighborhood switching effective.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: batch_size, base_sigma, scale, max_sigma, k_max, accept_tolerance, restart_on_stagnation, objective_aggregation, initializer, mutator, selector, change, pool_maintenance
Use when: 需要以局部精修为主，并可逐步扩大/切换邻域时 | 希望用少量评估预算做稳定改进时
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import VNSAdapter | from nsgablack.representation import ContextGaussianMutation | solver.set_adapter(VNSAdapter(mutator=ContextGaussianMutation())) | # Omit selector to retain the native candidate comparison; the problem pipeline repairs proposals.
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.serial_strategy`
Kind: adapter
Title: StrategyChainAdapter
Import: `nsgablack.adapters:StrategyChainAdapter`
Role: adapter
Summary: 串行策略控制器：按 phase 顺序切换子 Adapter；working_pool 绑定公共普通集合，子组合可继承或显式覆盖，输入来源与精选输出仍分别声明。
Tags: adapter, controller, core, phase, serial, strategy
Context requires: generation
Context provides: phase, strategy, strategy_id, solution_working_pool
Context notes: Serial phase scheduler; delegates propose/update to active adapter.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: phases, phase_schedule, repeat_last, working_pool
Use when: 需要把探索、开发等多段策略按阶段顺序串联时 | 需要让 phase 成为可审计运行语义时
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import StrategyChainAdapter, SerialPhaseSpec, NSGA2Adapter, VNSAdapter | phases = [SerialPhaseSpec('global', NSGA2Adapter(), steps=5), SerialPhaseSpec('local', VNSAdapter(), steps=3)] | solver.set_adapter(StrategyChainAdapter(phases))
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.elite_retention`
Kind: adapter
Title: EliteRetentionAdapter
Import: `nsgablack.adapters.elite_retention:EliteRetentionAdapter`
Role: adapter
Summary: 在正式步骤事务内注入精英派生候选，并透明委托内层 Adapter 权威状态。
Tags: adapter, elite, retention, wrapper, transactional
Context notes: Delegates context to the inner Adapter; elite archive and RNG remain in explicit Unit/checkpoint state.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: retention_probability, retention_ratio, history_size, mutation_scale
Use when: 需要精英派生搜索且必须保留 Candidate token、Evaluation Event 与回滚语义时。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | EliteRetentionAdapter(NSGA2Adapter(), EliteRetentionConfig())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.bayesian_optimization`
Kind: adapter
Title: BayesianOptimizationAdapter
Import: `nsgablack.adapters:BayesianOptimizationAdapter`
Role: adapter
Concepts: 贝叶斯引导 | 贝叶斯优化 | 替换采集函数 | 真实观测与成员分离
Runtime operations: synchronize_observations
Boundaries: 仅同步单目标；首版仅无 EvaluationProvider/评估决定插件的真实 Problem 路径。 | 固定参数模型从证据重建；采集/优化器首版须 stateless。 | 不支持真实异步 pending、联合 q-batch、随机超参数训练或完整约束 BO。
Summary: 同步单目标贝叶斯优化：固定RBF后验、LCB与网格提案组件；消费真实完整Event，模型观测与成员分离，支持可传输证据闭包恢复。首版不承诺异步或联合q-batch。
Tags: adapter, core, bayesian, surrogate, observations
Context notes: Consumes verified Evaluation Events and Adapter-owned Unit data; no shared context keys.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: config, model, acquisition, optimizer, unit_binding, name, priority
Use when: 需要明确区分真实观测、预测与评估价值，并以模型提出昂贵真实评估的候选时。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import BayesianOptimizationAdapter | solver.set_adapter(BayesianOptimizationAdapter())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.cmaes`
Kind: adapter
Title: CMAESAdapter
Import: `nsgablack.adapters:CMAESAdapter`
Role: adapter
Concepts: CMA-ES | 搜索分布 | 替换采样器 | 整批更新
Boundaries: 正权重无约束单目标完整协方差；不得静默缩小 lambda。 | 改变候选的 repair 在送评前拒绝；残缺 cohort 保留成本后报错。 | 未声明 PoolTask initialize/refine/compete；运行提案仍走统一解池。
Summary: 正权重完整协方差CMA-ES：采样、排名、分布更新分别装配；保存演化路径和完整cohort，严格拒绝改变候选的repair及残缺更新。
Tags: adapter, core, cma-es, covariance, cohort
Context notes: CMA distribution and cohort relations are local Unit data; no shared context writes.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: mean, sigma, covariance, parameters, sampler, ranking, updater, seed, name, unit_binding
Use when: 连续单目标无约束搜索，需要按整批排名自适应搜索分布时。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import CMAESAdapter | solver.set_adapter(CMAESAdapter([0.0, 0.0], sigma=0.5))
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.map_elites`
Kind: adapter
Title: MapElitesAdapter
Import: `nsgablack.adapters:MapElitesAdapter`
Role: adapter
Concepts: MAP-Elites | 质量多样性 | 按行为保留精英 | 替换描述符 | 格子档案
Boundaries: Unit 唯一拥有冠军；Pool 仅发布精确引用视图。 | 描述符来自最终送评候选；硬接纳和档案留存分开。 | 首版 emitter 无完整 cohort 反馈接口，不宣称支持 CMA emitter。
Summary: MAP-Elites：描述符、格子映射、冠军竞争与生成器分别装配；Unit唯一维护格子冠军，Pool发布精确成员视图，支持逐条竞争与事务恢复。
Tags: adapter, core, quality-diversity, archive, descriptor
Context notes: Archive decisions use actual evaluated candidates and raw feedback; no shared context writes.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: config, descriptor, cells, competition, emitter, unit_binding, name, priority
Use when: 希望保留行为区域内各自的高质量解，而非将描述符当目标或软偏好时。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import MapElitesAdapter | solver.set_adapter(MapElitesAdapter())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.bo_model`
Kind: tool
Title: FixedRBFPosterior
Import: `nsgablack.adapters.bayesian_optimization:FixedRBFPosterior`
Role: model
Concepts: 贝叶斯引导 | 贝叶斯优化 | 替换后验模型
Runtime operations: fit, posterior, spawn, describe
Boundaries: 零均值固定参数 RBF GP；不执行超参数训练。 | 预测不是真实目标；component_state_mode=rebuild 从核对后的观测重建缓存。
Summary: 可独立装配的 FixedRBFPosterior；职责、限制和已有标准 Case 见下列契约。
Tags: core, model
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: config
Use when: 贝叶斯引导 | 贝叶斯优化 | 替换后验模型
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters.bayesian_optimization import BayesianOptimizationAdapter, FixedRBFPosterior | adapter = BayesianOptimizationAdapter(model=FixedRBFPosterior())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.bo_acquisition`
Kind: tool
Title: LowerConfidenceBound
Import: `nsgablack.adapters.bayesian_optimization:LowerConfidenceBound`
Role: acquisition
Concepts: 替换采集函数 | 贝叶斯引导 | LCB | 探索与开发
Runtime operations: __call__, describe
Boundaries: LCB=mean-beta*std，当前最小化采集值。 | 求值前提案价值不是 Bias 或原目标；首版 stateless。
Summary: 可独立装配的 LowerConfidenceBound；职责、限制和已有标准 Case 见下列契约。
Tags: core, acquisition
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: beta
Use when: 替换采集函数 | 贝叶斯引导 | LCB | 探索与开发
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters.bayesian_optimization import BayesianOptimizationAdapter, LowerConfidenceBound | adapter = BayesianOptimizationAdapter(acquisition=LowerConfidenceBound(beta=2.0))
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.bo_acquisition_optimizer`
Kind: tool
Title: GridAcquisitionOptimizer
Import: `nsgablack.adapters.bayesian_optimization:GridAcquisitionOptimizer`
Role: acquisition_optimizer
Concepts: 替换采集搜索 | 网格提案 | 贝叶斯优化
Runtime operations: minimize, describe
Boundaries: 有限网格稳定 argmin，不是连续全局最优证明。 | 不调用真实 Problem、不消耗真实评估预算；首版 stateless。
Summary: 可独立装配的 GridAcquisitionOptimizer；职责、限制和已有标准 Case 见下列契约。
Tags: core, acquisition-optimizer
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: grid
Use when: 替换采集搜索 | 网格提案 | 贝叶斯优化
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters.bayesian_optimization import BayesianOptimizationAdapter, GridAcquisitionOptimizer | adapter = BayesianOptimizationAdapter(optimizer=GridAcquisitionOptimizer(grid=((0.25,), (0.5,), (0.75,))))
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.cma_sampler`
Kind: tool
Title: GaussianCohortSampler
Import: `nsgablack.adapters.cmaes:GaussianCohortSampler`
Role: sampler
Concepts: 替换采样器 | CMA-ES | 搜索分布
Runtime operations: sample, get_state, set_state, reset
Boundaries: fixed_batches 仅是显式夹具前缀，不是默认性能配置。 | RNG/游标由唯一 Adapter 保存和回滚。
Summary: 可独立装配的 GaussianCohortSampler；职责、限制和已有标准 Case 见下列契约。
Tags: core, sampler
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: seed, fixed_batches
Use when: 替换采样器 | CMA-ES | 搜索分布
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters.cmaes import CMAESAdapter, GaussianCohortSampler | adapter = CMAESAdapter([0.0, 0.0], sampler=GaussianCohortSampler(seed=19))
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.cma_ranking`
Kind: tool
Title: StableObjectiveRanking
Import: `nsgablack.adapters.cmaes:StableObjectiveRanking`
Role: ranking
Concepts: 替换排名 | CMA-ES | 稳定并列
Runtime operations: rank
Boundaries: 完整 cohort 的无约束单目标 raw 排名；同分保留提案顺序。 | 不把硬接纳裁剪当作 mu 重组选择；组件 stateless。
Summary: 可独立装配的 StableObjectiveRanking；职责、限制和已有标准 Case 见下列契约。
Tags: core, ranking
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 替换排名 | CMA-ES | 稳定并列
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters.cmaes import CMAESAdapter, StableObjectiveRanking | adapter = CMAESAdapter([0.0, 0.0], ranking=StableObjectiveRanking())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.cma_update`
Kind: tool
Title: PositiveCMAUpdate
Import: `nsgablack.adapters.cmaes:PositiveCMAUpdate`
Role: distribution_update
Concepts: CMA-ES | 整批更新 | 替换分布更新
Runtime operations: update
Boundaries: 正权重 rank-one+rank-mu 更新，包含演化路径和步长。 | 必须与 Adapter 共享同一 CMAParameters 解释和完整 cohort。
Summary: 可独立装配的 PositiveCMAUpdate；职责、限制和已有标准 Case 见下列契约。
Tags: core, distribution-update
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: parameters
Use when: CMA-ES | 整批更新 | 替换分布更新
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters.cmaes import CMAESAdapter, PositiveCMAUpdate | from nsgablack.adapters.cmaes import CMAParameters | parameters = CMAParameters(population_size=4, parents=2) | adapter = CMAESAdapter([0.0, 0.0], parameters=parameters, updater=PositiveCMAUpdate(parameters))
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.map_descriptor`
Kind: tool
Title: IdentityDescriptor
Import: `nsgablack.adapters.map_elites:IdentityDescriptor`
Role: descriptor
Concepts: 替换描述符 | MAP-Elites | 行为区域
Runtime operations: describe
Boundaries: 描述符不是目标，也不是普通多样性 Bias。 | 使用 repair 后实际候选；首版描述符须 stateless。
Summary: 可独立装配的 IdentityDescriptor；职责、限制和已有标准 Case 见下列契约。
Tags: core, descriptor
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: indices
Use when: 替换描述符 | MAP-Elites | 行为区域
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters.map_elites import MapElitesAdapter, IdentityDescriptor | adapter = MapElitesAdapter(descriptor=IdentityDescriptor(indices=(0, 1)))
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.map_cells`
Kind: tool
Title: GridCells
Import: `nsgablack.adapters.map_elites:GridCells`
Role: cell_mapping
Concepts: 替换格子划分 | MAP-Elites | 行为区域
Runtime operations: locate
Boundaries: 内格半开；上边界归最后一格，越界拒绝。 | 不同格子配置不能直接解释旧 checkpoint。
Summary: 可独立装配的 GridCells；职责、限制和已有标准 Case 见下列契约。
Tags: core, cell-mapping
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: lower, upper, bins
Use when: 替换格子划分 | MAP-Elites | 行为区域
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters.map_elites import MapElitesAdapter, GridCells | adapter = MapElitesAdapter(cells=GridCells(lower=(0.0, 0.0), upper=(1.0, 1.0), bins=(2, 2)))
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.map_competition`
Kind: tool
Title: MinimizeObjective
Import: `nsgablack.adapters.map_elites:MinimizeObjective`
Role: archive_competition
Concepts: 替换档案竞争 | MAP-Elites | 保留精英
Runtime operations: quality, prefer
Boundaries: 先可行性，再同格指定 raw 目标；并列保留已有冠军。 | 这是硬接纳之后的档案留存，不是 EvaluationAcceptancePolicy。
Summary: 可独立装配的 MinimizeObjective；职责、限制和已有标准 Case 见下列契约。
Tags: core, archive-competition
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: objective, tolerance
Use when: 替换档案竞争 | MAP-Elites | 保留精英
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters.map_elites import MapElitesAdapter, MinimizeObjective | adapter = MapElitesAdapter(competition=MinimizeObjective(objective=0, tolerance=0.0))
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.map_sequence_emitter`
Kind: tool
Title: SequenceEmitter
Import: `nsgablack.adapters.map_elites:SequenceEmitter`
Role: emitter
Concepts: 替换生成器 | 确定性候选序列 | MAP-Elites
Runtime operations: emit, get_state, set_state
Boundaries: 有限序列用于可检查示例，耗尽后局部完成。 | 游标由唯一 Adapter 保存/回滚，不是随机优化策略。
Summary: 可独立装配的 SequenceEmitter；职责、限制和已有标准 Case 见下列契约。
Tags: core, emitter
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: points
Use when: 替换生成器 | 确定性候选序列 | MAP-Elites
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters.map_elites import MapElitesAdapter, SequenceEmitter | adapter = MapElitesAdapter(emitter=SequenceEmitter(((0.1, 0.1), (0.4, 0.4), (0.6, 0.4), (0.6, 0.8), (0.8, 0.2))))
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.map_gaussian_emitter`
Kind: tool
Title: GaussianArchiveEmitter
Import: `nsgablack.adapters.map_elites:GaussianArchiveEmitter`
Role: emitter
Concepts: 替换生成器 | 档案变异 | MAP-Elites
Runtime operations: emit
Boundaries: 从档案冠军派生候选；空档案要求问题管线 initializer。 | RNG由 Adapter 提供；未实现 CMA emitter 的完整批次反馈。
Summary: 可独立装配的 GaussianArchiveEmitter；职责、限制和已有标准 Case 见下列契约。
Tags: core, emitter
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: sigma
Use when: 替换生成器 | 档案变异 | MAP-Elites
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters.map_elites import MapElitesAdapter, GaussianArchiveEmitter | adapter = MapElitesAdapter(emitter=GaussianArchiveEmitter(sigma=0.1)) | # Also provide solver RepresentationPipeline(initializer=UniformInitializer(...)) for an empty archive.
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.unit_view`
Kind: tool
Title: UnitView
Import: `nsgablack.units:UnitView`
Role: tool
Summary: 按实例路径、Unit 身份和 revision 交付脱离只读视图；PopulationView 提供成员能力。
Tags: unit, preference, identity, readonly
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: owner_path, unit_id, schema, revision
Use when: 比较结构或让偏好读取明确的算法结构时。
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | import numpy as np | from nsgablack.units import PopulationUnit, UnitBinding | from nsgablack.representation import PopulationUnitBuilder | from nsgablack.units.views import PopulationView | from nsgablack.bias import PreferenceQuery, PopulationDiversityPreference | unit = PopulationUnit('reference', population=np.array([[0., 0.], [1., 1.]])) | view = PopulationView.capture(unit, UnitBinding(PopulationUnitBuilder()), owner_path=('reference',)) | score = PopulationDiversityPreference().evaluate(PreferenceQuery('unit', unit=view)) | print(score.value, score.direction)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.preference_query`
Kind: tool
Title: PreferenceQuery
Import: `nsgablack.bias:PreferenceQuery`
Role: tool
Summary: 显式区分 candidate、candidate_in_unit、unit、unit_transition 四种评价范围。
Tags: unit, bias, comparison, contract
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: scope, candidate, candidate_token, unit, proposed_unit
Use when: 由 Adapter 明确消费候选、结构或结构变化的偏好时。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias import PreferenceQuery | query = PreferenceQuery('unit', unit=view)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.population_diversity`
Kind: bias
Title: PopulationDiversityPreference
Import: `nsgablack.bias:PopulationDiversityPreference`
Role: bias
Summary: 纯评分：候选最近邻新颖性、群体平均最近邻距离及同一 Unit 的变化增益。
Tags: unit, bias, diversity, population
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要明确群体实例、成员身份和偏好方向时。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias import PopulationDiversityPreference | score = PopulationDiversityPreference().evaluate(query)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.unit_preference`
Kind: bias
Title: UnitPreferenceBias
Import: `nsgablack.bias:UnitPreferenceBias`
Role: bias
Summary: 绑定参考 Unit，并可按 StrategyOrigin 实例路径限定候选，将偏好投影为选择增量。
Tags: unit, bias, binding, selection
Context notes: Reads an explicitly bound detached Unit view; emits selection guidance.
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: name, weight, owner_path, apply_to_paths
Use when: 在标准 Case 中装配依赖 Unit 的可选选择偏好时。
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | from nsgablack.bias import UnitPreferenceBias, PopulationDiversityPreference | bias_module.add(UnitPreferenceBias.from_adapter(PopulationDiversityPreference(), adapter, owner_path=('search',)))
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.module`
Kind: bias
Title: BiasModule
Import: `nsgablack.bias:BiasModule`
Role: bias
Summary: 统一聚合算法偏置与领域偏置的运行门面。 / Runtime facade that aggregates algorithmic and domain biases.
Tags: bias, core, facade, manager
Context notes: Bias facade: aggregates algorithmic/domain bias contracts.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: cache_backend, cache_ttl_seconds, cache_key_prefix, cache_context_keys, cache_include_generation
Use when: 需要把多个软引导机制组合到统一 Solver 生命周期时。 / Need to compose multiple soft-guidance mechanisms into one Solver lifecycle.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias import BiasModule | solver.set_bias_module(BiasModule())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.diversity_adaptive`
Kind: bias
Title: AdaptiveDiversityBias
Import: `nsgablack.bias.algorithmic.diversity:AdaptiveDiversityBias`
Role: bias
Summary: 自适应调整多样性压力。 / Algorithmic bias: adaptively adjust diversity pressure.
Tags: adaptive, algorithmic, bias, diversity
Context requires: population_ref
Context notes: Algorithmic bias: reads metrics and outputs scalar guidance.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.algorithmic.diversity import AdaptiveDiversityBias | bias_module.add(AdaptiveDiversityBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.diversity_niche`
Kind: bias
Title: NicheDiversityBias
Import: `nsgablack.bias.algorithmic.diversity:NicheDiversityBias`
Role: bias
Summary: 基于小生境的多样性保持。 / Algorithmic bias: niche-based diversity preservation.
Tags: algorithmic, bias, diversity, niching
Context notes: Algorithmic bias: reads metrics and outputs scalar guidance.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.algorithmic.diversity import NicheDiversityBias | bias_module.add(NicheDiversityBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.diversity_crowding`
Kind: bias
Title: CrowdingDistanceBias
Import: `nsgablack.bias.algorithmic.diversity:CrowdingDistanceBias`
Role: bias
Summary: 基于拥挤距离偏好稀疏/前沿解。 / Algorithmic bias: favor sparse/frontier solutions via crowding distance.
Tags: algorithmic, bias, crowding, diversity
Context requires: population_ref
Context notes: Algorithmic bias: reads metrics and outputs scalar guidance.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.algorithmic.diversity import CrowdingDistanceBias | bias_module.add(CrowdingDistanceBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.diversity_sharing`
Kind: bias
Title: SharingFunctionBias
Import: `nsgablack.bias.algorithmic.diversity:SharingFunctionBias`
Role: bias
Summary: 适应度共享以降低拥挤。 / Algorithmic bias: fitness sharing to reduce crowding.
Tags: algorithmic, bias, diversity, sharing
Context requires: population_ref
Context notes: Algorithmic bias: reads metrics and outputs scalar guidance.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.algorithmic.diversity import SharingFunctionBias | bias_module.add(SharingFunctionBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.convergence_adaptive`
Kind: bias
Title: AdaptiveConvergenceBias
Import: `nsgablack.bias.algorithmic.convergence:AdaptiveConvergenceBias`
Role: bias
Summary: 自适应平衡探索与收敛。 / Algorithmic bias: adaptively balance exploration vs convergence.
Tags: adaptive, algorithmic, bias, convergence
Context notes: Algorithmic bias: reads metrics and outputs scalar guidance.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.algorithmic.convergence import AdaptiveConvergenceBias | bias_module.add(AdaptiveConvergenceBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.convergence_precision`
Kind: bias
Title: PrecisionBias
Import: `nsgablack.bias.algorithmic.convergence:PrecisionBias`
Role: bias
Summary: 强调精度与局部精修。 / Algorithmic bias: emphasize precision and local refinement.
Tags: algorithmic, bias, convergence, precision
Context notes: Algorithmic bias: reads metrics and outputs scalar guidance.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.algorithmic.convergence import PrecisionBias | bias_module.add(PrecisionBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.convergence_late_stage`
Kind: bias
Title: LateStageConvergenceBias
Import: `nsgablack.bias.algorithmic.convergence:LateStageConvergenceBias`
Role: bias
Summary: 加速后期收敛。 / Algorithmic bias: accelerate late-stage convergence.
Tags: algorithmic, bias, convergence, late_stage
Context requires: generation
Context notes: Algorithmic bias: reads metrics and outputs scalar guidance.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.algorithmic.convergence import LateStageConvergenceBias | bias_module.add(LateStageConvergenceBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.convergence_multi_stage`
Kind: bias
Title: MultiStageConvergenceBias
Import: `nsgablack.bias.algorithmic.convergence:MultiStageConvergenceBias`
Role: bias
Summary: 多阶段收敛调度。 / Algorithmic bias: multi-stage convergence scheduling.
Tags: algorithmic, bias, convergence, multi_stage
Context requires: generation
Context notes: Algorithmic bias: reads metrics and outputs scalar guidance.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.algorithmic.convergence import MultiStageConvergenceBias | bias_module.add(MultiStageConvergenceBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.pso_adaptive`
Kind: bias
Title: AdaptivePSOBias
Import: `nsgablack.bias.algorithmic.pso:AdaptivePSOBias`
Role: bias
Summary: 自适应 PSO 参数。 / Algorithmic bias: adaptive PSO parameters.
Tags: adaptive, algorithmic, bias, pso
Context requires: generation
Context notes: Reads context fields: generation, metrics; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.algorithmic.pso import AdaptivePSOBias | bias_module.add(AdaptivePSOBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.cmaes_adaptive`
Kind: bias
Title: AdaptiveCMAESBias
Import: `nsgablack.bias.algorithmic.cma_es:AdaptiveCMAESBias`
Role: bias
Summary: 按代数调节已有分布距离偏好的强度；不执行 CMA-ES 的分布更新。 / Scheduled distribution-distance preference; not a CMA-ES optimizer.
Tags: adaptive, algorithmic, bias, cmaes
Context requires: generation
Context notes: Reads context fields: generation, metrics; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.algorithmic.cma_es import AdaptiveCMAESBias | bias_module.add(AdaptiveCMAESBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.constraint`
Kind: bias
Title: ConstraintBias
Import: `nsgablack.bias.domain.constraint:ConstraintBias`
Role: bias
Summary: 将约束显式注入评分。 / Domain bias: inject constraints into scoring.
Tags: bias, constraint, domain
Context requires: generation
Context notes: Reads context fields: generation; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.domain.constraint import ConstraintBias | bias_module.add(ConstraintBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.feasibility`
Kind: bias
Title: FeasibilityBias
Import: `nsgablack.bias.domain.constraint:FeasibilityBias`
Role: bias
Summary: 可行性优先。 / Domain bias: prioritize feasibility.
Tags: bias, domain, feasibility
Context requires: problem_data
Context notes: Reads context fields: problem_data; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.domain.constraint import FeasibilityBias | bias_module.add(FeasibilityBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.preference`
Kind: bias
Title: PreferenceBias
Import: `nsgablack.bias.domain.constraint:PreferenceBias`
Role: bias
Summary: 编码偏好/权重。 / Domain bias: encode preferences/weights.
Tags: bias, domain, preference
Context notes: Reads context fields: metrics; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.domain.constraint import PreferenceBias | bias_module.add(PreferenceBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.rule_based`
Kind: bias
Title: RuleBasedBias
Import: `nsgablack.bias.domain.constraint:RuleBasedBias`
Role: bias
Summary: 规则驱动的加权/惩罚。 / Domain bias: rule-based weighting/penalty.
Tags: bias, domain, rule
Context requires: generation
Context notes: Reads context fields: generation; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.domain.constraint import RuleBasedBias | bias_module.add(RuleBasedBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.callable`
Kind: bias
Title: CallableBias
Import: `nsgablack.bias.domain.callable_bias:CallableBias`
Role: bias
Summary: 用户可调用偏置函数。 / Domain bias: user callable bias function.
Tags: bias, callable, domain
Context requires: problem_data
Context notes: Reads context fields: problem_data; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias import BiasModule | from nsgablack.bias.domain.callable_bias import CallableBias | bias_module = BiasModule() | bias_module.add(CallableBias('near_zero', lambda x: float((x*x).sum()), weight=0.1)) | solver.set_bias_module(bias_module)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.engineering_design`
Kind: bias
Title: EngineeringDesignBias
Import: `nsgablack.bias.domain.engineering:EngineeringDesignBias`
Role: bias
Summary: 工程设计约束/先验。 / Domain bias: engineering design constraints/priors.
Tags: bias, domain, engineering
Context requires: problem_data
Context notes: Reads context fields: problem_data; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.domain.engineering import EngineeringDesignBias | bias_module.add(EngineeringDesignBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.safety`
Kind: bias
Title: SafetyBias
Import: `nsgablack.bias.domain.engineering:SafetyBias`
Role: bias
Summary: 安全/风险优先。 / Domain bias: safety/risk prioritization.
Tags: bias, domain, safety
Context requires: problem_data
Context notes: Reads context fields: problem_data; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.domain.engineering import SafetyBias | bias_module.add(SafetyBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.manufacturing`
Kind: bias
Title: ManufacturingBias
Import: `nsgablack.bias.domain.engineering:ManufacturingBias`
Role: bias
Summary: 制造可行性约束。 / Domain bias: manufacturing feasibility.
Tags: bias, domain, manufacturing
Context requires: problem_data
Context notes: Reads context fields: problem_data; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.domain.engineering import ManufacturingBias | bias_module.add(ManufacturingBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.scheduling`
Kind: bias
Title: SchedulingBias
Import: `nsgablack.bias.domain.scheduling:SchedulingBias`
Role: bias
Summary: 调度偏好。 / Domain bias: scheduling preference.
Tags: bias, domain, scheduling
Context requires: problem_data
Context notes: Reads context fields: problem_data; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.domain.scheduling import SchedulingBias | bias_module.add(SchedulingBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.resource_constraint`
Kind: bias
Title: ResourceConstraintBias
Import: `nsgablack.bias.domain.scheduling:ResourceConstraintBias`
Role: bias
Summary: 资源容量约束。 / Domain bias: resource capacity constraints.
Tags: bias, domain, resource
Context requires: problem_data
Context notes: Reads context fields: problem_data; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.domain.scheduling import ResourceConstraintBias | bias_module.add(ResourceConstraintBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.time_window`
Kind: bias
Title: TimeWindowBias
Import: `nsgablack.bias.domain.scheduling:TimeWindowBias`
Role: bias
Summary: 时间窗约束。 / Domain bias: time window constraints.
Tags: bias, domain, time_window
Context requires: problem_data
Context notes: Reads context fields: problem_data; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.domain.scheduling import TimeWindowBias | bias_module.add(TimeWindowBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.bayesian_guidance`
Kind: bias
Title: BayesianGuidanceBias
Import: `nsgablack.bias.specialized.bayesian_biases:BayesianGuidanceBias`
Role: soft_preference
Concepts: 贝叶斯引导 | 历史引导 | 贝叶斯偏好
Runtime operations: compute
Boundaries: 这是历史/距离类软评分；内置辅助模型是占位，不是 GP posterior 或完整贝叶斯优化。 | 不会替代模型、采集函数与真实评估事件；真实 BO 使用 adapter.bayesian_optimization。
Summary: 历史引导软偏好；内置模型为占位辅助，不构成完整贝叶斯优化。 / Historical guidance preference with a placeholder model; not a Bayesian optimizer.
Tags: bayesian, bias, guidance, specialized
Context requires: dynamic, generation, individual, population_ref
Context notes: Reads context fields: dynamic, generation, individual, metrics, population_ref; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.specialized.bayesian_biases import BayesianGuidanceBias | bias_module.add(BayesianGuidanceBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.bayesian_exploration`
Kind: bias
Title: BayesianExplorationBias
Import: `nsgablack.bias.specialized.bayesian_biases:BayesianExplorationBias`
Role: soft_preference
Concepts: 贝叶斯引导 | 历史引导 | 贝叶斯偏好
Runtime operations: compute
Boundaries: 这是历史/距离类软评分；内置辅助模型是占位，不是 GP posterior 或完整贝叶斯优化。 | 不会替代模型、采集函数与真实评估事件；真实 BO 使用 adapter.bayesian_optimization。
Summary: 偏好高不确定区域。 / Specialized bias: favor uncertain regions.
Tags: bayesian, bias, exploration, specialized
Context requires: generation, population_ref
Context notes: Reads context fields: generation, population_ref; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.specialized.bayesian_biases import BayesianExplorationBias | bias_module.add(BayesianExplorationBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.bayesian_convergence`
Kind: bias
Title: BayesianConvergenceBias
Import: `nsgablack.bias.specialized.bayesian_biases:BayesianConvergenceBias`
Role: soft_preference
Concepts: 贝叶斯引导 | 历史引导 | 贝叶斯偏好
Runtime operations: compute
Boundaries: 这是历史/距离类软评分；内置辅助模型是占位，不是 GP posterior 或完整贝叶斯优化。 | 不会替代模型、采集函数与真实评估事件；真实 BO 使用 adapter.bayesian_optimization。
Summary: 在后验置信区间内收敛。 / Specialized bias: converge within posterior confidence.
Tags: bayesian, bias, convergence, specialized
Context notes: Reads context fields: metrics; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.specialized.bayesian_biases import BayesianConvergenceBias | bias_module.add(BayesianConvergenceBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.engineering_precision`
Kind: bias
Title: EngineeringPrecisionBias
Import: `nsgablack.bias.specialized.engineering:EngineeringPrecisionBias`
Role: bias
Summary: 精度/公差偏置。 / Domain bias: precision/tolerance bias.
Tags: bias, domain, engineering, precision
Context notes: Reads context fields: metrics; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.specialized.engineering import EngineeringPrecisionBias | bias_module.add(EngineeringPrecisionBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.engineering_constraint`
Kind: bias
Title: EngineeringConstraintBias
Import: `nsgablack.bias.specialized.engineering:EngineeringConstraintBias`
Role: bias
Summary: 工程规则约束。 / Domain bias: engineering rule constraints.
Tags: bias, constraint, domain, engineering
Context requires: generation
Context notes: Reads context fields: generation; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.specialized.engineering import EngineeringConstraintBias | bias_module.add(EngineeringConstraintBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.engineering_robustness`
Kind: bias
Title: EngineeringRobustnessBias
Import: `nsgablack.bias.specialized.engineering:EngineeringRobustnessBias`
Role: bias
Summary: 对扰动的鲁棒性。 / Domain bias: robustness to perturbations.
Tags: bias, domain, engineering, robustness
Context requires: problem_data
Context notes: Reads context fields: problem_data; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.specialized.engineering import EngineeringRobustnessBias | bias_module.add(EngineeringRobustnessBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.local_gd`
Kind: bias
Title: GradientDescentBias (LocalSearch)
Import: `nsgablack.bias.specialized.local_search:GradientDescentBias`
Role: bias
Summary: 局部梯度精修。 / Specialized bias: local gradient refinement.
Tags: bias, gradient_descent, local_search, specialized
Context requires: problem_data
Context notes: Reads context fields: problem_data; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.specialized.local_search import GradientDescentBias | bias_module.add(GradientDescentBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.local_newton`
Kind: bias
Title: NewtonMethodBias
Import: `nsgablack.bias.specialized.local_search:NewtonMethodBias`
Role: bias
Summary: 牛顿式精修。 / Specialized bias: Newton-style refinement.
Tags: bias, local_search, newton, specialized
Context notes: Reads context fields: metrics; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.specialized.local_search import NewtonMethodBias | bias_module.add(NewtonMethodBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.local_line_search`
Kind: bias
Title: LineSearchBias
Import: `nsgablack.bias.specialized.local_search:LineSearchBias`
Role: bias
Summary: 线搜索步长控制。 / Specialized bias: line-search step control.
Tags: bias, line_search, local_search, specialized
Context notes: Reads context fields: metrics; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.specialized.local_search import LineSearchBias | bias_module.add(LineSearchBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.local_trust_region`
Kind: bias
Title: TrustRegionBias
Import: `nsgablack.bias.specialized.local_search:TrustRegionBias`
Role: bias
Summary: 信赖域精修。 / Specialized bias: trust-region refinement.
Tags: bias, local_search, specialized, trust_region
Context notes: Reads context fields: metrics; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.specialized.local_search import TrustRegionBias | bias_module.add(TrustRegionBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.local_nelder_mead`
Kind: bias
Title: NelderMeadBias
Import: `nsgablack.bias.specialized.local_search:NelderMeadBias`
Role: bias
Summary: Nelder-Mead 单纯形精修。 / Specialized bias: Nelder-Mead simplex refinement.
Tags: bias, local_search, nelder_mead, specialized
Context notes: Reads context fields: metrics; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.specialized.local_search import NelderMeadBias | bias_module.add(NelderMeadBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.local_quasi_newton`
Kind: bias
Title: QuasiNewtonBias
Import: `nsgablack.bias.specialized.local_search:QuasiNewtonBias`
Role: bias
Summary: 拟牛顿精修。 / Specialized bias: quasi-Newton refinement.
Tags: bias, local_search, quasi_newton, specialized
Context notes: Reads context fields: metrics; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.specialized.local_search import QuasiNewtonBias | bias_module.add(QuasiNewtonBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.graph_connectivity`
Kind: bias
Title: ConnectivityBias
Import: `nsgablack.bias.specialized.graph.base:ConnectivityBias`
Role: bias
Summary: 图连通性约束。 / Specialized bias: graph connectivity.
Tags: bias, connectivity, graph, specialized
Context notes: No explicit context dependency; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | import numpy as np | from nsgablack.bias.specialized.graph.base import GraphStructure | graph = GraphStructure(num_nodes=3, num_edges=2, edge_list=[(0,1,1.), (1,2,1.)]) | from nsgablack.bias.specialized.graph.base import ConnectivityBias | from nsgablack.bias import BiasModule | bias_module = BiasModule() | bias_module.add(ConnectivityBias(graph=graph)) | solver.set_bias_module(bias_module)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.graph_sparsity`
Kind: bias
Title: SparsityBias
Import: `nsgablack.bias.specialized.graph.base:SparsityBias`
Role: bias
Summary: 图稀疏性偏置。 / Specialized bias: graph sparsity.
Tags: bias, graph, sparsity, specialized
Context notes: No explicit context dependency; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | import numpy as np | from nsgablack.bias.specialized.graph.base import GraphStructure | graph = GraphStructure(num_nodes=3, num_edges=2, edge_list=[(0,1,1.), (1,2,1.)]) | from nsgablack.bias.specialized.graph.base import SparsityBias | from nsgablack.bias import BiasModule | bias_module = BiasModule() | bias_module.add(SparsityBias(graph=graph)) | solver.set_bias_module(bias_module)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.graph_degree_distribution`
Kind: bias
Title: DegreeDistributionBias
Import: `nsgablack.bias.specialized.graph.base:DegreeDistributionBias`
Role: bias
Summary: 目标度分布约束。 / Specialized bias: target degree distribution.
Tags: bias, degree, graph, specialized
Context notes: No explicit context dependency; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | import numpy as np | from nsgablack.bias.specialized.graph.base import GraphStructure | graph = GraphStructure(num_nodes=3, num_edges=2, edge_list=[(0,1,1.), (1,2,1.)]) | from nsgablack.bias.specialized.graph.base import DegreeDistributionBias | from nsgablack.bias import BiasModule | bias_module = BiasModule() | bias_module.add(DegreeDistributionBias(graph=graph)) | solver.set_bias_module(bias_module)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.graph_shortest_path`
Kind: bias
Title: ShortestPathBias
Import: `nsgablack.bias.specialized.graph.base:ShortestPathBias`
Role: bias
Summary: 最短路径偏好。 / Specialized bias: shortest path preference.
Tags: bias, graph, shortest_path, specialized
Context notes: No explicit context dependency; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | import numpy as np | from nsgablack.bias.specialized.graph.base import GraphStructure | graph = GraphStructure(num_nodes=3, num_edges=2, edge_list=[(0,1,1.), (1,2,1.)]) | from nsgablack.bias.specialized.graph.base import ShortestPathBias | from nsgablack.bias import BiasModule | bias_module = BiasModule() | bias_module.add(ShortestPathBias(graph=graph, source=0, target=2)) | solver.set_bias_module(bias_module)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.graph_max_flow`
Kind: bias
Title: MaxFlowBias
Import: `nsgablack.bias.specialized.graph.base:MaxFlowBias`
Role: bias
Summary: 最大流偏好。 / Specialized bias: max-flow preference.
Tags: bias, graph, max_flow, specialized
Context notes: No explicit context dependency; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | import numpy as np | from nsgablack.bias.specialized.graph.base import GraphStructure | graph = GraphStructure(num_nodes=3, num_edges=2, edge_list=[(0,1,1.), (1,2,1.)]) | from nsgablack.bias.specialized.graph.base import MaxFlowBias | from nsgablack.bias import BiasModule | bias_module = BiasModule() | bias_module.add(MaxFlowBias(graph=graph, source=0, sink=2)) | solver.set_bias_module(bias_module)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.graph_coloring`
Kind: bias
Title: GraphColoringBias
Import: `nsgablack.bias.specialized.graph.base:GraphColoringBias`
Role: bias
Summary: 图着色偏置。 / Specialized bias: graph coloring bias.
Tags: bias, coloring, graph, specialized
Context notes: No explicit context dependency; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | import numpy as np | from nsgablack.bias.specialized.graph.base import GraphStructure | graph = GraphStructure(num_nodes=3, num_edges=2, edge_list=[(0,1,1.), (1,2,1.)]) | from nsgablack.bias.specialized.graph.base import GraphColoringBias | from nsgablack.bias import BiasModule | bias_module = BiasModule() | bias_module.add(GraphColoringBias(graph=graph)) | solver.set_bias_module(bias_module)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.graph_community`
Kind: bias
Title: CommunityDetectionBias
Import: `nsgablack.bias.specialized.graph.base:CommunityDetectionBias`
Role: bias
Summary: 社区结构偏置。 / Specialized bias: community structure bias.
Tags: bias, community, graph, specialized
Context notes: No explicit context dependency; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | import numpy as np | from nsgablack.bias.specialized.graph.base import GraphStructure | graph = GraphStructure(num_nodes=3, num_edges=2, edge_list=[(0,1,1.), (1,2,1.)]) | from nsgablack.bias.specialized.graph.base import CommunityDetectionBias | from nsgablack.bias import BiasModule | bias_module = BiasModule() | bias_module.add(CommunityDetectionBias(graph=graph)) | solver.set_bias_module(bias_module)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.graph_constraint`
Kind: bias
Title: GraphConstraintBias
Import: `nsgablack.bias.specialized.graph.constraints:GraphConstraintBias`
Role: bias
Summary: 图结构约束。 / Specialized bias: graph structural constraints.
Tags: bias, constraint, graph, specialized
Context requires: problem_data
Context notes: Reads context fields: problem_data; outputs scalar bias only.
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | from nsgablack.bias import BiasModule | from nsgablack.bias.specialized.graph.constraints import GraphConstraintBias, ValidationResult | class NonnegativeGraphValues(GraphConstraintBias): |     def validate_constraints(self, x, context): |         valid = bool((x >= 0.).all()) |         return ValidationResult(is_valid=valid) | bias_module = BiasModule() | bias_module.add(NonnegativeGraphValues(name='nonnegative_graph_values')) | solver.set_bias_module(bias_module)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.graph_tsp_constraint`
Kind: bias
Title: TSPConstraintBias
Import: `nsgablack.bias.specialized.graph.constraints:TSPConstraintBias`
Role: bias
Summary: TSP 约束。 / Specialized bias: TSP constraints.
Tags: bias, constraint, graph, specialized, tsp
Context notes: No explicit context dependency; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | import numpy as np | from nsgablack.bias.specialized.graph.constraints import TSPConstraintBias | from nsgablack.bias import BiasModule | bias_module = BiasModule() | bias_module.add(TSPConstraintBias(num_cities=3)) | solver.set_bias_module(bias_module)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.graph_path_constraint`
Kind: bias
Title: PathConstraintBias
Import: `nsgablack.bias.specialized.graph.constraints:PathConstraintBias`
Role: bias
Summary: 路径约束。 / Specialized bias: path constraints.
Tags: bias, constraint, graph, path, specialized
Context notes: No explicit context dependency; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | import numpy as np | from nsgablack.bias.specialized.graph.constraints import PathConstraintBias | from nsgablack.bias import BiasModule | bias_module = BiasModule() | bias_module.add(PathConstraintBias(num_nodes=3, start_node=0, end_node=2)) | solver.set_bias_module(bias_module)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.graph_tree_constraint`
Kind: bias
Title: TreeConstraintBias
Import: `nsgablack.bias.specialized.graph.constraints:TreeConstraintBias`
Role: bias
Summary: 树结构约束。 / Specialized bias: tree constraints.
Tags: bias, constraint, graph, specialized, tree
Context notes: No explicit context dependency; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | import numpy as np | from nsgablack.bias.specialized.graph.constraints import TreeConstraintBias | from nsgablack.bias import BiasModule | bias_module = BiasModule() | bias_module.add(TreeConstraintBias(num_nodes=3)) | solver.set_bias_module(bias_module)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.graph_coloring_constraint`
Kind: bias
Title: GraphColoringConstraintBias
Import: `nsgablack.bias.specialized.graph.constraints:GraphColoringConstraintBias`
Role: bias
Summary: 着色约束。 / Specialized bias: coloring constraints.
Tags: bias, coloring, constraint, graph, specialized
Context notes: No explicit context dependency; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | import numpy as np | from nsgablack.bias.specialized.graph.constraints import GraphColoringConstraintBias | from nsgablack.bias import BiasModule | bias_module = BiasModule() | bias_module.add(GraphColoringConstraintBias(adjacency_matrix=np.array([[0,1,0],[1,0,1],[0,1,0]]))) | solver.set_bias_module(bias_module)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.graph_matching_constraint`
Kind: bias
Title: MatchingConstraintBias
Import: `nsgablack.bias.specialized.graph.constraints:MatchingConstraintBias`
Role: bias
Summary: 匹配约束。 / Specialized bias: matching constraints.
Tags: bias, constraint, graph, matching, specialized
Context notes: No explicit context dependency; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | import numpy as np | from nsgablack.bias.specialized.graph.constraints import MatchingConstraintBias | from nsgablack.bias import BiasModule | bias_module = BiasModule() | bias_module.add(MatchingConstraintBias(num_nodes=4)) | solver.set_bias_module(bias_module)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.graph_hamiltonian_constraint`
Kind: bias
Title: HamiltonianPathConstraintBias
Import: `nsgablack.bias.specialized.graph.constraints:HamiltonianPathConstraintBias`
Role: bias
Summary: 哈密顿路径约束。 / Specialized bias: Hamiltonian path constraints.
Tags: bias, constraint, graph, hamiltonian, specialized
Context notes: No explicit context dependency; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | import numpy as np | from nsgablack.bias.specialized.graph.constraints import HamiltonianPathConstraintBias | from nsgablack.bias import BiasModule | bias_module = BiasModule() | bias_module.add(HamiltonianPathConstraintBias(num_nodes=3)) | solver.set_bias_module(bias_module)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.graph_composite_constraint`
Kind: bias
Title: CompositeGraphConstraintBias
Import: `nsgablack.bias.specialized.graph.constraints:CompositeGraphConstraintBias`
Role: bias
Summary: 复合图约束。 / Specialized bias: composite graph constraints.
Tags: bias, composite, constraint, graph, specialized
Context notes: No explicit context dependency; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | import numpy as np | from nsgablack.bias.specialized.graph.constraints import TSPConstraintBias | from nsgablack.bias.specialized.graph.constraints import CompositeGraphConstraintBias | from nsgablack.bias import BiasModule | bias_module = BiasModule() | bias_module.add(CompositeGraphConstraintBias(constraints=[TSPConstraintBias(num_cities=3)])) | solver.set_bias_module(bias_module)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.surrogate_control`
Kind: tool
Title: SurrogateControlBias
Import: `nsgablack.bias.surrogate.base:SurrogateControlBias`
Role: tool
Summary: 代理控制策略：返回控制更新映射；当前没有正式自动消费者，不能加入标量BiasModule。
Tags: bias, control, specialized, surrogate
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要独立计算代理阶段或不确定性控制建议映射时；当前无正式自动消费者，不可加入标量BiasModule。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.surrogate import SurrogateBiasContext | context = SurrogateBiasContext(generation=5, max_generations=10, population=None, |     surrogate_manager=None, surrogate_ready=False, n_training_samples=0, |     model_quality={}, real_eval_count=0, surrogate_eval_count=0, |     prefilter={}, score_bias={}, surrogate_eval={}, constraint_eval={}) | from nsgablack.bias.surrogate import SurrogateControlBias | updates = SurrogateControlBias().apply(context) | assert updates == {}
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.surrogate_phase_schedule`
Kind: tool
Title: PhaseScheduleBias
Import: `nsgablack.bias.surrogate.phase_schedule:PhaseScheduleBias`
Role: tool
Summary: 代理控制策略：返回控制更新映射；当前没有正式自动消费者，不能加入标量BiasModule。
Tags: bias, schedule, specialized, surrogate
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要独立计算代理阶段或不确定性控制建议映射时；当前无正式自动消费者，不可加入标量BiasModule。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.surrogate import SurrogateBiasContext | context = SurrogateBiasContext(generation=5, max_generations=10, population=None, |     surrogate_manager=None, surrogate_ready=False, n_training_samples=0, |     model_quality={}, real_eval_count=0, surrogate_eval_count=0, |     prefilter={}, score_bias={}, surrogate_eval={}, constraint_eval={}) | from nsgablack.bias.surrogate import PhaseScheduleBias | policy = PhaseScheduleBias([{'start':0., 'end':1., 'updates':{'prefilter':{'enabled':True, 'ratio':1.0}}}]) | updates = policy.apply(context) | assert updates['prefilter']['ratio'] == 1.0
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.surrogate_uncertainty_budget`
Kind: tool
Title: UncertaintyBudgetBias
Import: `nsgablack.bias.surrogate.uncertainty_budget:UncertaintyBudgetBias`
Role: tool
Summary: 代理控制策略：返回控制更新映射；当前没有正式自动消费者，不能加入标量BiasModule。
Tags: bias, specialized, surrogate, uncertainty
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要独立计算代理阶段或不确定性控制建议映射时；当前无正式自动消费者，不可加入标量BiasModule。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.surrogate import SurrogateBiasContext | context = SurrogateBiasContext(generation=5, max_generations=10, population=None, |     surrogate_manager=None, surrogate_ready=False, n_training_samples=0, |     model_quality={}, real_eval_count=0, surrogate_eval_count=0, |     prefilter={}, score_bias={}, surrogate_eval={}, constraint_eval={}) | from nsgablack.bias.surrogate import UncertaintyBudgetBias | updates = UncertaintyBudgetBias().apply(context) | assert updates['prefilter']['ratio'] == 1.0
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.production_constraint`
Kind: bias
Title: ProductionConstraintBias
Import: `nsgablack.bias.specialized.production.scheduling:ProductionConstraintBias`
Role: bias
Summary: 生产约束。 / Domain bias: production constraints.
Tags: bias, constraint, domain, production
Context requires: problem_data
Context notes: Reads context fields: problem_data; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.specialized.production.scheduling import ProductionConstraintBias | from nsgablack.bias import BiasModule | bias_module = BiasModule() | bias_module.add(ProductionConstraintBias(machine_bom={'A':['material']}, inventory_data={'material':100.}, machine_ids=['A'], days=2)) | solver.set_bias_module(bias_module)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.production_diversity`
Kind: bias
Title: ProductionDiversityBias
Import: `nsgablack.bias.specialized.production.scheduling:ProductionDiversityBias`
Role: bias
Summary: 生产多样性偏好。 / Domain bias: production diversity.
Tags: bias, diversity, domain, production
Context notes: Reads context fields: metrics; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.specialized.production.scheduling import ProductionDiversityBias | bias_module.add(ProductionDiversityBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.production_continuity`
Kind: bias
Title: ProductionContinuityBias
Import: `nsgablack.bias.specialized.production.scheduling:ProductionContinuityBias`
Role: bias
Summary: 生产连续性偏好。 / Domain bias: production continuity.
Tags: bias, continuity, domain, production
Context notes: Reads context fields: metrics; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.specialized.production.scheduling import ProductionContinuityBias | from nsgablack.bias import BiasModule | bias_module = BiasModule() | bias_module.add(ProductionContinuityBias(machine_ids=['A','B'], days=2)) | solver.set_bias_module(bias_module)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.cmaes`
Kind: bias
Title: CMAESBias
Import: `nsgablack.bias.algorithmic.cma_es:CMAESBias`
Role: bias
Summary: 读取已有 mean/cov/sigma 计算分布距离软偏好；不执行协方差自适应。 / Distribution-distance preference using supplied state; no CMA-ES covariance update.
Tags: algorithmic, bias, cma-es, cmaes, covariance, strategy
Context requires: problem_data
Context notes: Reads context fields: metrics, problem_data; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.algorithmic.cma_es import CMAESBias | bias_module.add(CMAESBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.convergence`
Kind: bias
Title: ConvergenceBias
Import: `nsgablack.bias.algorithmic.convergence:ConvergenceBias`
Role: bias
Summary: 收敛加速。 / Algorithmic bias: convergence acceleration.
Tags: algorithmic, bias, convergence, exploitation, schedule
Context requires: generation, population_ref
Context notes: Algorithmic bias: reads metrics and outputs scalar guidance.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.algorithmic.convergence import ConvergenceBias | bias_module.add(ConvergenceBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.diversity`
Kind: bias
Title: DiversityBias
Import: `nsgablack.bias.algorithmic.diversity:DiversityBias`
Role: bias
Summary: 旧单种群距离奖励（最小化负增量）；新装配推荐显式 UnitPreferenceBias。
Tags: algorithmic, bias, diversity, exploration, niching
Context requires: population_ref
Context notes: Algorithmic bias: reads metrics and outputs scalar guidance.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.algorithmic.diversity import DiversityBias | bias_module.add(DiversityBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.dynamic_penalty`
Kind: bias
Title: DynamicPenaltyBias
Import: `nsgablack.bias.domain.dynamic_penalty:DynamicPenaltyBias`
Role: bias
Summary: 约束违反的动态惩罚。 / Domain bias: dynamic penalty for constraint violation.
Tags: bias, constraint, domain, dynamic, penalty, schedule
Context requires: problem_data
Context notes: Reads context fields: problem_data; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias import BiasModule | from nsgablack.bias.domain.dynamic_penalty import DynamicPenaltyBias | bias_module = BiasModule() | bias_module.add(DynamicPenaltyBias(penalty_func=lambda x: max(0.0, float(x.sum())-1.0), weight=0.1)) | solver.set_bias_module(bias_module)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.levy`
Kind: bias
Title: LevyFlightBias
Import: `nsgablack.bias.algorithmic.levy_flight:LevyFlightBias`
Role: bias
Summary: Levy 飞行探索。 / Algorithmic bias: Levy-flight exploration.
Tags: algorithmic, bias, exploration, levy, random_walk
Context requires: generation, population_ref
Context notes: Reads context fields: generation, metrics, population_ref; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.algorithmic.levy_flight import LevyFlightBias | bias_module.add(LevyFlightBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.pso`
Kind: bias
Title: ParticleSwarmBias
Import: `nsgablack.bias.algorithmic.pso:ParticleSwarmBias`
Role: bias
Summary: 相对给定最好位置的距离软偏好；不维护粒子速度或执行完整 PSO。 / Distance preference to supplied best positions; no particle dynamics.
Tags: algorithmic, bias, particle_swarm, pso, strategy, swarm
Context requires: problem_data
Context notes: Reads context fields: metrics, problem_data; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.algorithmic.pso import ParticleSwarmBias | bias_module.add(ParticleSwarmBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.risk`
Kind: bias
Title: RiskBias
Import: `nsgablack.bias.domain.risk_bias:RiskBias`
Role: bias
Summary: 风险感知评分（CVaR/最坏情况）。 / Domain bias: risk-aware scoring (CVaR/worst-case).
Tags: bias, cvar, domain, risk, worst_case
Context requires: problem_data
Context notes: Reads context fields: problem_data; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.domain.risk_bias import RiskBias | bias_module.add(RiskBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.robustness`
Kind: bias
Title: RobustnessBias
Import: `nsgablack.bias.algorithmic.signal_driven.robustness:RobustnessBias`
Role: bias
Summary: 扰动下的鲁棒性评分。 / Algorithmic bias: robustness-oriented scoring under perturbations.
Tags: bias, mc, robustness, signal_driven, algorithmic
Context notes: Reads context fields: metrics; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.algorithmic.signal_driven.robustness import RobustnessBias | bias_module.add(RobustnessBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.structure_prior`
Kind: bias
Title: StructurePriorBias
Import: `nsgablack.bias.domain.structure_prior:StructurePriorBias`
Role: bias
Summary: 结构/对称先验。 / Domain bias: structure/symmetry prior.
Tags: bias, domain, prior, structure, symmetry
Context requires: problem_data
Context notes: Reads context fields: problem_data; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.domain.structure_prior import StructurePriorBias | bias_module.add(StructurePriorBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.tabu`
Kind: bias
Title: TabuSearchBias
Import: `nsgablack.bias.algorithmic.tabu_search:TabuSearchBias`
Role: bias
Summary: 只读禁忌评分；记忆记录已提交步骤中接纳的提案，通过 BiasModule 参与回滚与恢复。
Tags: bias, memory, strategy, tabu, algorithmic
Context notes: Scores against committed admitted-candidate memory; evaluation is read-only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.algorithmic.tabu_search import TabuSearchBias | bias_module.add(TabuSearchBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `bias.uncertainty_exploration`
Kind: bias
Title: UncertaintyExplorationBias
Import: `nsgablack.bias.algorithmic.signal_driven.uncertainty_exploration:UncertaintyExplorationBias`
Role: bias
Summary: 优先探索高不确定区域。 / Algorithmic bias: explore high-uncertainty regions.
Tags: bias, exploration, signal_driven, uncertainty, algorithmic
Context notes: Reads context fields: metrics; outputs scalar bias only.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在不改动硬约束的前提下注入软偏好引导时。 / Need to inject soft preference guidance without changing hard constraints.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.bias.algorithmic.signal_driven.uncertainty_exploration import UncertaintyExplorationBias | bias_module.add(UncertaintyExplorationBias())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.catalog_curate`
Kind: tool
Title: Catalog AI 资料整理
Import: `nsgablack.catalog.curate:curate_packets`
Role: catalog_maintenance
Concepts: AI资料整理 | 自动整理 | 组件说明 | 源码证据 | 增量发布
Runtime operations: curate_packets
Boundaries: 解释性说明不是运行验收；接口和能力仍由源码声明决定。 | 按源码摘要、模型和提示版本复用；网页不持有AI凭据，也不触发生成。 | 每批limit约束新整理条目数，不是硬金额预算。
Summary: 依据受限源码证据增量整理组件用途、输入输出、装配思路与资料缺项；生成说明独立保存，不改运行契约。
Tags: catalog, ai, documentation, incremental, deepseek
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: packets, store, generator, model, limit, workers, keys
Use when: AI资料整理 | 自动整理组件说明 | 检查过期说明与缺项
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | from nsgablack.catalog.curate import curate_packets | # 由独立 writer 任务读取证据包与私密模型配置；网页只读取整理结果。
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.unit_binding`
Kind: tool
Title: UnitBinding
Import: `nsgablack.units:UnitBinding`
Role: unit_binding
Concepts: UnitBinding | Unit结构构建 | 自定义Unit | 种群扩展字段
Runtime operations: build, dump, restore, require, validate
Boundaries: build 不是候选 encode；恢复不调用随机 builder。 | 绑定不拥有运行循环、全局授权或可变算法状态。
Summary: 无状态 builder、显式 codec 与可选 runner 的装配绑定；运行结构由 Adapter 按需创建。
Tags: core, unit-binding
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: builder, runner, name, operations
Use when: UnitBinding | Unit结构构建 | 自定义Unit | 种群扩展字段
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.units import UnitBinding | from nsgablack.representation import PopulationUnitBuilder | binding = UnitBinding(PopulationUnitBuilder())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.population_unit`
Kind: tool
Title: PopulationUnit
Import: `nsgablack.units:PopulationUnit`
Role: unit
Concepts: 种群扩展字段 | PopulationUnit | 自定义种群 | 成员对齐
Runtime operations: initialize_population, apply_selection, clear_population, attach_feedback, replace_evaluated_rows, require_current_feedback, on_members_changed
Boundaries: apply_selection 执行 Adapter 给出的索引，不定义生存策略。 | 新增行字段须声明 member_fields 并维护；Adapter 不猜测未知字段。
Summary: 种群候选、反馈、token 与扩展成员字段的单一结构；Adapter 选择成员，Unit 原子维护对齐。
Tags: core, unit
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: unit_id, population, objectives, violations, candidate_tokens, feedback_population_revision, feedback_field_revisions
Use when: 种群扩展字段 | PopulationUnit | 自定义种群 | 成员对齐
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | import numpy as np | from nsgablack.units import PopulationUnit, UnitFeature, FeatureUnit | unit = PopulationUnit('demo', population=np.array([[0., 1.], [1., 0.]])) | center = UnitFeature('center', ('population',), lambda data: data['population'].mean(axis=0)) | assert isinstance(unit, FeatureUnit) | value = unit.feature(center) | print(value)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.bo_unit`
Kind: tool
Title: BayesianOptimizationUnit
Import: `nsgablack.units:BayesianOptimizationUnit`
Role: unit
Concepts: 真实观测与成员分离 | BO观测状态
Boundaries: 训练证据闭包不能仅从最后接受成员重建。
Summary: 由实际 Adapter 按需持有的算法结构，经显式 codec 回滚与恢复。
Tags: core, unit
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: unit_id
Use when: 真实观测与成员分离 | BO观测状态
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | import numpy as np | from nsgablack.units import BayesianOptimizationUnit, UnitBinding, StructureBuildRequest | from nsgablack.representation.bayesian_builder import BayesianUnitBuilder | binding = UnitBinding(BayesianUnitBuilder()) | unit = binding.build(StructureBuildRequest('demo', parameters={'values': {}})) | assert isinstance(unit, BayesianOptimizationUnit)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.cma_unit`
Kind: tool
Title: CMAUnit
Import: `nsgablack.units:CMAUnit`
Role: unit
Concepts: CMA-ES | 搜索分布 | 整批更新
Boundaries: 分布参数不是逐成员字段；未评估均值不能当作已评估候选。
Summary: 由实际 Adapter 按需持有的算法结构，经显式 codec 回滚与恢复。
Tags: core, unit
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: unit_id
Use when: CMA-ES | 搜索分布 | 整批更新
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | import numpy as np | from nsgablack.units import CMAUnit, UnitBinding, StructureBuildRequest | from nsgablack.representation.cmaes_builder import CMAUnitBuilder | binding = UnitBinding(CMAUnitBuilder()) | unit = binding.build(StructureBuildRequest('demo', parameters={'values': {'mean': np.zeros(2), 'covariance': np.eye(2), 'path_c': np.zeros(2), 'path_sigma': np.zeros(2)}})) | assert isinstance(unit, CMAUnit)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.map_elites_unit`
Kind: tool
Title: MapElitesUnit
Import: `nsgablack.units:MapElitesUnit`
Role: unit
Concepts: MAP-Elites | 格子档案 | 按行为保留精英
Boundaries: Unit 唯一维护冠军；Pool archive 仅是精确引用视图。
Summary: 由实际 Adapter 按需持有的算法结构，经显式 codec 回滚与恢复。
Tags: core, unit
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: unit_id
Use when: MAP-Elites | 格子档案 | 按行为保留精英
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | import numpy as np | from nsgablack.units import MapElitesUnit, UnitBinding, StructureBuildRequest | from nsgablack.representation.map_elites_builder import MapElitesUnitBuilder | binding = UnitBinding(MapElitesUnitBuilder()) | unit = binding.build(StructureBuildRequest('demo', parameters={'values': {}})) | assert isinstance(unit, MapElitesUnit)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.problem_repair`
Kind: tool
Title: ProblemRepair
Import: `nsgablack.representation:ProblemRepair`
Role: tool
Summary: 问题修复 Protocol：修复候选并只读验证最终语义版本，与 UnitRepair 共同验收。
Tags: repair, problem, contract, validation
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: repair, validate
Use when: 需要在 UnitRepair 修改候选后重新确认问题约束时。
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | # Implement repair(candidate, context) and validate(semantic_candidate, context) -> bool | pipeline = RepresentationPipeline(repair=problem_repair)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.unit_repair`
Kind: tool
Title: UnitRepair
Import: `nsgablack.representation:UnitRepair`
Role: tool
Summary: Unit 修复 Protocol：修改 codec 草稿，验证最终候选与结构；部分接纳投影在 Adapter disposition 之后执行，保留已整理坐标。
Tags: repair, unit, contract, validation
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: repair, validate, project_admission
Use when: 有 algorithm_unit/UnitBinding 的叶 Adapter 需要独立结构修复组件时。
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | # Implement repair(unit, evidence, context) -> CandidateBatch and validate(unit, evidence, context) -> bool | # Partial admission: project_admission receives a draft already compacted by Adapter disposition | adapter.set_unit_repair(unit_repair)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.joint_repair_policy`
Kind: tool
Title: JointRepairPolicy
Import: `nsgablack.representation:JointRepairPolicy`
Role: tool
Summary: 显式启用 ProblemRepair/UnitRepair 共同验收；有限轮协调，零接纳恢复局部状态；拒绝后串行推进须整体规划、事务执行。
Tags: repair, unit, problem, transaction
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: max_rounds, on_rejection
Use when: 必须在送评前同时满足已声明的问题约束和 Unit 不变量时。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.representation import JointRepairPolicy | solver = ComposableSolver(problem, adapter=adapter, representation_pipeline=pipeline, joint_repair_policy=JointRepairPolicy(max_rounds=1))
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.change_request`
Kind: tool
Title: ChangeRequest
Import: `nsgablack.adapters:ChangeRequest`
Role: tool
Summary: NSGA/VNS/MOEA-D 普通完整变化函数的只读输入：父候选矩阵、精确引用、Unit参数、max_outputs及调用期request.pool。读取来源保持精确版本；批量消费者明确许可孩子数量，池访问不进入checkpoint。
Tags: core, change, plain-function, readonly, solution-pool, nsga2, vns, moead
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: parents, source_refs, parameters, context, unit_id, pool, max_outputs
Use when: 直接安排交叉、变异与跨池父代来源；NSGA可一次交付多个独立后代，单候选叶仍保持原生数量约束。
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | def change(request, *, rng): return request.candidate + rng.normal(0, 0.1, request.candidate.shape) | adapter = VNSAdapter(change=change) | # request.pool.subpool('elite').random(1, rng=rng).values reads committed exact versions lazily. | # Task-scoped access permits only the frozen inputs and explicitly declared change_sources/change_allow_main. | # Return ChangeResult(candidate, outputs=(PoolOutput('offspring', create=True),)) for accepted-proposal delivery.
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.change_result`
Kind: tool
Title: ChangeResult
Import: `nsgablack.adapters:ChangeResult`
Role: tool
Summary: 普通 change 的可选返回：单个候选、可选精确 source_refs 与 PoolOutput 目标。读取依赖自动保留，声明来源不能绕过任务范围；评估、硬接纳与池事务仍由控制面执行。
Tags: core, change, plain-function, solution-pool, provenance, output
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: candidate, source_refs, outputs, edits
Use when: 需要声明输出子池或补充精确源版本；只返回候选时不必包装。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import VNSAdapter, ChangeResult, PoolOutput | def change(request, *, rng): |     child = request.candidate + rng.normal(0., 0.1, request.candidate.shape) |     return ChangeResult(child, outputs=(PoolOutput('trials', create=True),)) | adapter = VNSAdapter(change=change)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.pool_output`
Kind: tool
Title: PoolOutput
Import: `nsgablack.adapters:PoolOutput`
Role: tool
Summary: change 的具名普通引用集合输出声明：缺省要求目标已存在，create=True 允许控制面在接纳后创建；声明本身不写池，不允许把候选追加进算法投影视图。
Tags: core, change, solution-pool, output, transaction
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: name, create
Use when: 将已接纳的新提案交付现有或显式创建的普通子池，保持提交后才可见与失败回滚。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import VNSAdapter, ChangeResult, PoolOutput | def change(request, *, rng): |     child = request.candidate + rng.normal(0., 0.1, request.candidate.shape) |     return ChangeResult(child, outputs=(PoolOutput('trials', create=True),)) | adapter = VNSAdapter(change=change)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.pool_edit`
Kind: tool
Title: PoolEdit
Import: `nsgablack.adapters:PoolEdit`
Role: tool
Summary: 普通子池的精确成员替换计划，冻结目标身份和revision；replace_members(create=True)也可冻结缺失目标并创建。经change的静态edits或每批更新后maintenance提交，复用生存choose副结果的同一计划事务，不直接写算法结果视图。
Tags: core, solution-pool, collection, transaction, revision
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: name, members, expected
Use when: 在普通变化函数中按已发布反馈更新精英集合、移除或裁剪成员。
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | from nsgablack.adapters import ChangeResult | def change(request, *, rng): |     members = request.pool.main(stage='accepted').take(range(2)) |     edit = request.pool.replace_members('elite', members.refs, create=True) |     return ChangeResult(request.candidate, edits=(edit,))
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.change_selection`
Kind: tool
Title: ChangeSelection
Import: `nsgablack.adapters.change_pool:ChangeSelection`
Role: pool_view
Concepts: Pool对象 | 兼容选择视图
Runtime operations: take, random, merge, where, order_by, top, intersection, difference, groups
Boundaries: ChangeSelection 是公开 Pool 的兼容类型名，不建立第二套候选存储。
Summary: 公开Pool的兼容类型名：调用内有序精确引用选择；保留旧take/random/where/top用法，复用同一引用存储与授权，不产生第二套候选集合。
Tags: core, solution-pool, selection, readonly, collection
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: parent, name
Use when: 用少量普通函数表达取解规则，保留候选身份、来源权限与冻结时点。
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | source = request.pool.subpool('elite') | selected = source.where(predicate).top(5, key=explicit_key) | groups = selected.groups(2) | # predicate(selection) returns (N,) bool; key(selection) returns finite (N,) or (N,K) scores.
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.pool`
Kind: tool
Title: Pool
Import: `nsgablack.adapters:Pool`
Role: pool_view
Concepts: 解池选择 | 选择精英 | 创建精英池 | Pool对象 | 入池 | 选择后变化
Runtime operations: chosen, inject, all, take, concat, merge, top, where, order_by, intersection, difference, groups, selection_feedback, raw_feedback
Boundaries: Pool 是一次调用内的有序引用视图，不是新的持久 SnapshotStore。 | parent 提供调用范围，不表示持久拓扑或自动调度算法。 | 具名 inject 在生存选择或成员维护中交付原池事务，不能改写算法投影视图。
Summary: 调用内候选集合：chosen执行纯选择，Pool(parent=..., name=...)创建空草稿，inject追加或显式精确替换。GA生存选择或成员维护将具名副Pool草稿交给原池事务；不改raw、不扩读权限、不创建调度器。旧主Pool和具名副Pool映射返回仍支持。
Tags: core, solution-pool, selection, transaction, identity
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: parent, name
Use when: 用普通choose函数选择已有解；需要时同时交付最终成员中的精英或未选位置，不重复执行选择。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import Pool | def choose(pool, *, rng): |     members = pool.chosen(select_members, rng=rng) |     Pool(parent=members, name='elite').inject(members.take(range(min(2, len(members)))), replace=True) |     return members | ga.set_selector(choose) | # Named inject: survivor or maintenance only; append to an existing target requires declared read access. | # parent supplies call scope, not persistent topology or automatic Adapter dispatch.
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.pool_partition`
Kind: tool
Title: partition
Import: `nsgablack.adapters:partition`
Role: tool
Summary: 对非空Pool调用一次普通choose，空输入不调用；返回所选位置与有序补集两个Pool。重复引用的不同位置分别处理，结果映回原调用者坐标；不改成员、不建子池、不求值。
Tags: core, solution-pool, selection, readonly, position
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: pool, by, rng
Use when: 同时需要精英与其余候选，避免重复计算选择规则或用引用集合差误删重复槽位。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import partition | selected, remaining = partition(pool, by=choose_elite, rng=rng) | # choose_elite(Pool[, *, rng]) -> Pool; it runs once for nonempty input. | # Both views retain caller scope; save refs/data rather than live Pool objects.
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.change_batch_result`
Kind: tool
Title: ChangeBatchResult
Import: `nsgablack.adapters:ChangeBatchResult`
Role: tool
Summary: 一次完整变化的有序多个ChangeResult；每个孩子独立派生身份、修复、预算和接纳坐标。实际消费者给出max_outputs，不能让单候选算法隐式接收任意批量。
Tags: core, change, batch, provenance, nsga2
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: results
Use when: 一对父代共享一次随机交叉，交付两个相关但身份独立的后代。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import NSGA2Adapter, ChangeBatchResult, ChangeResult | def change(request, *, rng): |     parent = request.parents[0] |     noise = rng.normal(0., 0.1, parent.shape) |     children = (ChangeResult(parent + noise), ChangeResult(parent - noise)) |     return ChangeBatchResult(children[:request.max_outputs]) | adapter = NSGA2Adapter(change=change)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.pool_maintenance_request`
Kind: tool
Title: PoolMaintenanceRequest
Import: `nsgablack.adapters:PoolMaintenanceRequest`
Role: tool
Summary: 实际叶Adapter更新后的只读维护输入：受限来源、本批accepted及有序最终种群members；轨迹算法members为None。二者保留各自选择反馈，合并历史显式使用raw；返回PoolEdit与同一Authority/manifest提交，不开放其他pending或重复求值。
Tags: core, solution-pool, maintenance, transaction, readonly
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: pool, accepted, objectives, violations, parameters, context, members
Use when: 按本批接纳试探或本轮最终成员分别维护历史精英/Pareto集合，不把档案计算塞入每个change。
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | def maintain(request, *, rng): |     if request.members is None: raise ValueError('population result required') |     old = request.pool.subpool('archive') if 'archive' in request.pool.describe()['subpools'] else request.members.take(()) |     kept = old.merge(request.members).top(20, key=raw_key) |     return (request.pool.replace_members('archive', kept.refs, create=True),) | adapter.set_pool_maintenance(maintain) | # Declare exact public name archive in enclosing PoolTask.change_sources, including before creation.
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.operator_binding`
Kind: tool
Title: OperatorBinding
Import: `nsgablack.adapters.operator_binding:OperatorBinding`
Role: tool
Summary: 独立初始化、变化、选择或结构修复的身份与状态绑定；由实际叶 Adapter 一并 checkpoint/回滚，有状态组件只允许一个绑定所有者。
Tags: core, operator, checkpoint, ownership
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: component, method
Use when: 实现支持独立算子装配的 Adapter；用户通常通过 Adapter setter 绑定组件。
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | adapter.set_mutator(mutator) | adapter.set_parent_selector(selector) | # Components declare checkpoint_identity() and stateless=True or get_state()/set_state().
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.parent_selection_request`
Kind: tool
Title: ParentSelectionRequest
Import: `nsgablack.adapters.parent_selection:ParentSelectionRequest`
Role: tool
Summary: 父代选择输入：有序精确种群引用、脱离的只读 rank/crowding、请求数量及轻量调用上下文。
Tags: core, operator, selection, solution-pool, readonly
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: population_refs, rank, crowding, count, context
Use when: 编写返回 SolutionRef 序列的父代选择器；不把本地整数索引当成跨池候选。
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | from nsgablack.adapters import NSGA2Adapter | class FirstParents: |     stateless = True |     def checkpoint_identity(self): return {'name': 'first_parents', 'version': 1} |     def select(self, request, *, pool, rng): |         return tuple(request.population_refs[i % len(request.population_refs)] for i in range(request.count)) | adapter = NSGA2Adapter(parent_selector=FirstParents())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.mixed_pool_parent_selector`
Kind: tool
Title: MixedPoolParentSelector
Import: `nsgablack.adapters.parent_selection:MixedPoolParentSelector`
Role: tool
Summary: 从本种群 rank/crowding 锦标赛与已发布具名子池混合抽取父代，返回准确引用；不修改环境选择或创建精英池。
Tags: core, operator, selection, solution-pool, nsga2
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: pool_name, pool_fraction
Use when: 希望只替换 NSGA-II 的父代来源，保留交叉、变异、评估和生存选择时。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import MixedPoolParentSelector, NSGA2Adapter | adapter = NSGA2Adapter() | adapter.set_parent_selector(MixedPoolParentSelector('elite', pool_fraction=0.5)) | # Publish a nonempty named 'elite' pool before the first parent-selection call.
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `repr.gaussian_mutation`
Kind: representation
Title: GaussianMutation
Import: `nsgablack.representation.continuous:GaussianMutation`
Role: representation
Summary: 高斯变异：可直接绑定明确消费 mutator 的 Adapter，或接既有 Pipeline；DE 的直属变化在差分 trial 后执行，随机状态随实际所有者恢复。
Tags: core, continuous, mutation, operator, checkpoint
Context notes: Gaussian mutation uses local sigma/bounds; no context I/O.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: sigma, low, high
Use when: 需要为 NSGA、DE、MOEA/D 或轨迹算法独立指定可恢复变异；动态邻域优先考虑 ContextGaussianMutation。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import NSGA2Adapter | from nsgablack.representation.continuous import GaussianMutation | adapter = NSGA2Adapter() | adapter.set_mutator(GaussianMutation(sigma=0.1)) | # Do not share this stateful instance with another Adapter or the pipeline.
Methods: init=missing, mutate=ok, repair=missing, encode=missing, decode=missing
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.selection_request`
Kind: tool
Title: SelectionRequest
Import: `nsgablack.adapters.selection:SelectionRequest`
Role: tool
Summary: 评估后只读行选择请求：survivor 保留成员、replacement 比较槽位、candidate 选本批候选、proposal_order 重排本批；不承担父代引用选择或硬接纳。
Tags: core, operator, selection, readonly, purpose
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: purpose, candidates, objectives, violations, count, scores, parameters, context, pool
Use when: 编写明确消费算法比较视图与参数的 selector，而不直接修改 Adapter/Unit；MOEA/D 必须使用该方向提供的分数。
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | from nsgablack.adapters import DifferentialEvolutionAdapter | class FirstOffered: |     stateless = True |     def checkpoint_identity(self): return {'name': 'first_offered', 'version': 1} |     def select(self, request, *, rng): |         if request.purpose != 'replacement': raise ValueError('replacement only') |         return list(range(request.count)) | adapter = DifferentialEvolutionAdapter(selector=FirstOffered())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.feasibility_first_selection`
Kind: tool
Title: FeasibilityFirstSelection
Import: `nsgablack.adapters.selection:FeasibilityFirstSelection`
Role: tool
Summary: 显式可行性优先行选择：使用算法提供的 scores 或指定目标；不自动装配，也不等价于 NSGA Pareto 选择、Metropolis 或硬可行性接纳。
Tags: core, operator, selection, feasibility, stateless
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: objective_index, constraint_tolerance
Use when: 确实希望覆盖已声明选择位置的策略时；首先明确该 Adapter 请求的 purpose 与 scores 含义。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import DifferentialEvolutionAdapter, FeasibilityFirstSelection | adapter = DifferentialEvolutionAdapter(selector=FeasibilityFirstSelection()) | # Explicitly overrides target/trial replacement; omit selector to retain the native policy.
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `plugin.runtime_surface_tracker`
Kind: plugin
Title: RuntimeSurfaceTrackerPlugin
Import: `nsgablack.plugins:RuntimeSurfaceTrackerPlugin`
Role: plugin
Summary: 将装配、运行和产物记录写入正式运行面。 / Persist assembly, run, and artifact records to the formal runtime surface.
Tags: audit, catalog, plugin, runtime, surface, tracking
Context notes: Materializes SurfaceRecord/AssemblyRecord/RunRecord/ArtifactRecord into the resolved experiment DB target and injects run_surface into the solver result.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: db_path, namespace, tag, project_root, surface_key, surface_label, print_summary
Use when: 需要让 UI、审计或工具链消费可追踪的运行装配记录时。 / Need traceable runtime assembly records for UI, audit, or tooling.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.plugins import RuntimeSurfaceTrackerPlugin | solver.add_plugin(RuntimeSurfaceTrackerPlugin())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `plugin.checkpoint_resume`
Kind: plugin
Title: CheckpointResumePlugin
Import: `nsgablack.plugins.system.checkpoint_resume:CheckpointResumePlugin`
Role: plugin
Summary: 代级检查点与失败后恢复。 / Plugin: generation checkpointing and resume-after-failure.
Tags: checkpoint, plugin, recovery, resume, runtime, state
Context provides: checkpoint.latest_path, checkpoint.last_loaded_path
Context mutates: checkpoint.latest_path
Context cache: checkpoint.latest_path
Context notes: Persists solver/adapter/plugin state with optional RNG restore; supports latest/path resume.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: checkpoint_dir, file_prefix, save_every, save_on_finish, keep_last, auto_resume, resume_from, restore_plugin_state, restore_rng_state, strict, hmac_env_var, unsafe_allow_unsigned, trusted_roots
Use when: 需要在中断后从最近状态恢复时。 / Need resume from latest state after interruption. | 需要阶段快照用于调试/审计时。 / Need stage snapshots for debugging/audit.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.plugins import CheckpointResumePlugin, CheckpointResumeConfig | solver.add_plugin(CheckpointResumePlugin(config=CheckpointResumeConfig(auto_resume=True)))
Methods: on_solver_init=missing, on_population_init=missing, on_generation_start=missing, on_step=missing, on_generation_end=missing, on_solver_finish=ok
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `plugin.monte_carlo_eval`
Kind: plugin
Title: MonteCarloEvaluationProviderPlugin
Import: `nsgablack.plugins.evaluation.monte_carlo_evaluation:MonteCarloEvaluationProviderPlugin`
Role: plugin
Summary: 基于扰动的蒙特卡洛评估与指标统计。 / Plugin: perturbation-based Monte Carlo evaluation with metrics.
Tags: evaluation, mc, robustness, plugin
Context provides: metrics.mc_samples, metrics.mc_mean, metrics.mc_std, metrics.mc_min, metrics.mc_max
Context mutates: metrics
Context notes: Per-candidate Monte Carlo evaluation returns reduced objectives and statistics in Feedback.metrics; the shared evaluation boundary projects metrics for Bias.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: n_samples, noise_std, aggregation, seed, parallel
Use when: 需要超越单次幸运结果的鲁棒性对比时。 / Need robustness comparison beyond single lucky outcomes. | 扰动/噪声下需要统计意义的评估时。 / Need statistically meaningful evaluation under perturbations/noise.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.plugins import MonteCarloEvaluationProviderPlugin, MonteCarloEvaluationConfig | provider = MonteCarloEvaluationProviderPlugin(config=MonteCarloEvaluationConfig(mc_samples=16)).create_provider() | solver.register_evaluation_provider(provider)
Methods: on_solver_init=missing, on_population_init=missing, on_generation_start=missing, on_step=missing, on_generation_end=missing, on_solver_finish=missing
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `plugin.surrogate_eval`
Kind: plugin
Title: SurrogateEvaluationProviderPlugin
Import: `nsgablack.plugins.evaluation.surrogate_evaluation:SurrogateEvaluationProviderPlugin`
Role: plugin
Summary: 代理辅助评估并输出不确定性指标。 / Plugin: surrogate-assisted evaluation with uncertainty metrics.
Tags: evaluation, surrogate, plugin
Context provides: metrics.surrogate_std
Context mutates: metrics
Context notes: Uses surrogate prediction with partial true evaluations; optionally writes surrogate uncertainty into context.metrics.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: train_interval, warmup_evals, uncertainty_threshold, model_type, fallback_on_error
Use when: 真实评估昂贵，需要代理预筛选时。 / True eval is expensive; need surrogate pre-screening. | 需要降低整体评估成本时。 / Need to reduce overall evaluation cost.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.plugins import SurrogateEvaluationProviderPlugin, SurrogateEvaluationConfig | solver.register_evaluation_provider(SurrogateEvaluationProviderPlugin(config=SurrogateEvaluationConfig()).create_provider())
Methods: on_solver_init=missing, on_population_init=missing, on_generation_start=missing, on_step=missing, on_generation_end=missing, on_solver_finish=missing
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `plugin.multi_fidelity_eval`
Kind: plugin
Title: MultiFidelityEvaluationProviderPlugin
Import: `nsgablack.plugins.evaluation.multi_fidelity_evaluation:MultiFidelityEvaluationProviderPlugin`
Role: plugin
Summary: 多保真评估：低/高保真切换。 / Plugin: multi-fidelity evaluation switching between low/high fidelity.
Tags: evaluation, multi_fidelity, plugin
Context notes: Runs low/high-fidelity mixed evaluation and returns objectives/violations; does not write context fields by default.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: low_fidelity_ratio, switch_step, budget, fallback_to_high_fidelity
Use when: 评估成本高且存在低保真代理可用时。 / Eval cost is high and low-fidelity proxies are available. | 需要粗到细的评估流程时。 / Need coarse-to-fine evaluation.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.plugins import MultiFidelityEvaluationProviderPlugin, MultiFidelityEvaluationConfig | solver.register_evaluation_provider(MultiFidelityEvaluationProviderPlugin(config=MultiFidelityEvaluationConfig()).create_provider())
Methods: on_solver_init=missing, on_population_init=missing, on_generation_start=missing, on_step=missing, on_generation_end=missing, on_solver_finish=missing
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `plugin.newton_solver`
Kind: plugin
Title: NewtonSolverProviderPlugin
Import: `nsgablack.plugins.evaluation.newton_solver_plugin:NewtonSolverProviderPlugin`
Role: plugin
Summary: Newton 求解插件：评估阶段的非线性方程求解。 / Newton solver plugin: nonlinear equation solving during evaluation.
Tags: evaluation, solver, nonlinear, newton, plugin
Context requires: problem
Context provides: metrics.implicit_residual, metrics.implicit_iters, metrics.implicit_success
Context mutates: metrics
Context notes: Requires problem hooks build_implicit_system(x, ctx) and evaluate_from_implicit_solution(x, y, ctx).
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: tol, max_iter, fallback_to_problem_eval, warn_on_failure
Use when: 评估需要求解隐式非线性方程时。 / Use when evaluation requires solving implicit nonlinear equations. | 希望替换求解器插件而不改外层循环时。 / Use when you want solver-plugin replacement without touching outer loop.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.plugins import NewtonSolverProviderPlugin, NumericalSolverConfig | solver.register_evaluation_provider(NewtonSolverProviderPlugin(config=NumericalSolverConfig(tol=1e-8, max_iter=100)).create_provider())
Methods: on_solver_init=missing, on_population_init=missing, on_generation_start=missing, on_step=missing, on_generation_end=missing, on_solver_finish=missing
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `plugin.broyden_solver`
Kind: plugin
Title: BroydenSolverProviderPlugin
Import: `nsgablack.plugins.evaluation.broyden_solver_plugin:BroydenSolverProviderPlugin`
Role: plugin
Summary: Broyden 求解插件：评估阶段的无 Jacobian 非线性求解。 / Broyden solver plugin: Jacobian-free nonlinear solving in evaluation.
Tags: evaluation, solver, nonlinear, broyden, plugin
Context requires: problem
Context provides: metrics.implicit_residual, metrics.implicit_iters, metrics.implicit_success
Context mutates: metrics
Context notes: Same problem hooks as NewtonSolverProviderPlugin; useful when Jacobian is unavailable.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: tol, max_iter, fallback_to_problem_eval, warn_on_failure
Use when: Jacobian 不可用或不稳定时。 / Use when Jacobian is unavailable or unstable. | 偏好无 Jacobian 的非线性后端时。 / Use when a Jacobian-free nonlinear backend is preferred.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.plugins import BroydenSolverProviderPlugin, NumericalSolverConfig | solver.register_evaluation_provider(BroydenSolverProviderPlugin(config=NumericalSolverConfig(tol=1e-7, max_iter=120)).create_provider())
Methods: on_solver_init=missing, on_population_init=missing, on_generation_start=missing, on_step=missing, on_generation_end=missing, on_solver_finish=missing
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `plugin.contract_bridge`
Kind: plugin
Title: ContractBridgePlugin
Import: `nsgablack.plugins.domain_backends.contract_bridge:ContractBridgePlugin`
Role: plugin
Summary: 契约桥接插件：跨层映射内层结果字段。 / Contract bridge plugin: maps inner result fields across layers.
Tags: evaluation, nested, bridge, contract, plugin
Context mutates: metadata.layers
Context notes: Consumes on_inner_result packets and writes mapped keys into solver._layer_contexts.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: rules, allow_overwrite
Use when: 需要跨层回写（如 L3 -> L1）时。 / Use when cross-layer write-back is required (e.g., L3 -> L1). | 内外层契约必须保持解耦时。 / Use when inner/outer contracts must stay decoupled.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.plugins import ContractBridgePlugin, BridgeRule | solver.add_plugin(ContractBridgePlugin(rules=[BridgeRule('objective', 'inner_objective', target_layer='L1')]))
Methods: on_solver_init=missing, on_population_init=missing, on_generation_start=missing, on_step=missing, on_generation_end=missing, on_solver_finish=missing
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `plugin.inner_timeout_budget`
Kind: plugin
Title: TimeoutBudgetPlugin
Import: `nsgablack.plugins.domain_backends.timeout_budget:TimeoutBudgetPlugin`
Role: plugin
Summary: 内层超时/预算插件：限制内层调用次数与耗时。 / Inner timeout/budget plugin: bounds inner calls and runtime.
Tags: evaluation, nested, timeout, budget, plugin
Context notes: Provides on_inner_guard/on_inner_result for call/time budget control.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: layer, max_calls, time_budget_ms, fail_closed
Use when: 嵌套评估需遵守硬性调用/时间预算时。 / Use when nested evaluation must obey hard call/time budgets. | 内层失败不应阻塞外层优化时。 / Use when inner failures should not stall outer optimization.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.plugins import TimeoutBudgetPlugin, TimeoutBudgetConfig | solver.add_plugin(TimeoutBudgetPlugin(config=TimeoutBudgetConfig(layer='L2', max_calls=200, time_budget_ms=30000)))
Methods: on_solver_init=ok, on_population_init=missing, on_generation_start=missing, on_step=missing, on_generation_end=missing, on_solver_finish=missing
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `runtime.inner_evaluator`
Kind: plugin
Title: TaskInnerRuntimeEvaluator
Import: `nsgablack.core.nested_solver:TaskInnerRuntimeEvaluator`
Role: plugin
Summary: 问题侧内层运行评估器：通过 problem.inner_runtime_evaluator 执行嵌套评估。 / Problem-side inner runtime evaluator: executes nested evaluation through problem.inner_runtime_evaluator.
Tags: runtime, nested, inner, evaluation, contract
Context requires: problem
Context provides: metrics.inner_calls, metrics.inner_status, metrics.inner_elapsed_ms
Context mutates: metrics
Context notes: Configured at problem level (solver.problem.inner_runtime_evaluator), not via solver.add_plugin().
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: source_layer, target_layer, fallback_penalty, warn_on_failure, max_retries, per_call_timeout_ms, retry_backoff_ms
Use when: 评估本身是嵌套的优化流程时。 / Evaluation itself is a nested optimization workflow. | 需要 L1/L2/L3 分层评估契约时。 / You need L1/L2/L3 layered evaluation contracts.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.core.nested_solver import InnerRuntimeConfig, TaskInnerRuntimeEvaluator | solver.problem.inner_runtime_evaluator = TaskInnerRuntimeEvaluator(config=InnerRuntimeConfig(source_layer='L2', target_layer='L1'))
Methods: on_solver_init=missing, on_population_init=missing, on_generation_start=missing, on_step=missing, on_generation_end=missing, on_solver_finish=missing
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `plugin.pareto_archive`
Kind: plugin
Title: ParetoArchivePlugin
Import: `nsgablack.plugins.runtime.pareto_archive:ParetoArchivePlugin`
Role: plugin
Summary: 维护非支配档案与共享前沿状态。 / Plugin: maintain non-dominated archive and shared frontier state.
Tags: archive, pareto, runtime, plugin
Context notes: Reads solver population/objectives/violations or compatible committed Adapter population partitions; updates runtime pareto snapshot (pareto_solutions/pareto_objectives). Objective-space labelling creates isolated segments; dominance is only compared within a segment.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: max_size, deduplicate, dominance_eps, export_path
Use when: 多目标优化需要稳定维护 Pareto 前沿时。 / Need stable maintenance of Pareto front in MOO. | 需要共享档案用于多策略协同时。 / Need shared archive for multi-strategy coordination.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.plugins import ParetoArchivePlugin, ParetoArchiveConfig | solver.add_plugin(ParetoArchivePlugin(config=ParetoArchiveConfig(max_size=200)))
Methods: on_solver_init=missing, on_population_init=missing, on_generation_start=missing, on_step=missing, on_generation_end=missing, on_solver_finish=ok
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `plugin.benchmark_harness`
Kind: plugin
Title: BenchmarkHarnessPlugin
Import: `nsgablack.plugins.ops.benchmark_harness:BenchmarkHarnessPlugin`
Role: plugin
Summary: 标准化基准产物与指标协议。 / Plugin: standardized benchmark artifacts and metric protocol.
Tags: benchmark, ops, report, plugin
Context notes: Collects benchmark metrics and writes run artifacts; does not depend on fixed context keys.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: output_dir, run_id, overwrite, log_every, save_population
Use when: 需要统一实验输出格式（CSV/JSON）时。 / Need unified experiment output format (CSV/JSON). | 需要跨运行对比与批量复现时。 / Need cross-run comparison and batch reproduction.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.plugins import BenchmarkHarnessPlugin, BenchmarkHarnessConfig | solver.add_plugin(BenchmarkHarnessPlugin(config=BenchmarkHarnessConfig(output_dir='runs')))
Methods: on_solver_init=ok, on_population_init=missing, on_generation_start=missing, on_step=missing, on_generation_end=missing, on_solver_finish=ok
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `plugin.module_report`
Kind: plugin
Title: ModuleReportPlugin
Import: `nsgablack.plugins.ops.module_report:ModuleReportPlugin`
Role: plugin
Summary: 模块级审计与贡献报告。 / Plugin: module-level audit and contribution report.
Tags: ops, audit, ablation, plugin
Context notes: Builds module/bias reports from solver state and writes JSON/Markdown artifacts.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: output_dir, run_id, write_markdown, include_contracts, include_hash
Use when: 需要组件贡献/消融报告时。 / Need component contribution/ablation reports. | 需要每次实验的接线追踪时。 / Need wiring trace for each experiment.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.plugins import ModuleReportPlugin, ModuleReportConfig | solver.add_plugin(ModuleReportPlugin(config=ModuleReportConfig(output_dir='runs')))
Methods: on_solver_init=ok, on_population_init=missing, on_generation_start=missing, on_step=missing, on_generation_end=missing, on_solver_finish=ok
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `plugin.profiler`
Kind: plugin
Title: ProfilerPlugin
Import: `nsgablack.plugins.ops.profiler:ProfilerPlugin`
Role: plugin
Summary: 运行时性能剖析：阶段延迟与吞吐。 / Plugin: runtime profiling for stage latency and throughput.
Tags: ops, profile, performance, plugin
Context notes: Profiles runtime/per-generation timings and writes profile artifact.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: log_interval, include_plugin_breakdown, output_path, enabled_events
Use when: 怀疑评估插件/调度成为瓶颈时。 / Suspect evaluation plugins/scheduling as bottlenecks. | 需要性能证据支持优化决策时。 / Need performance evidence for optimization decisions.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.plugins import ProfilerPlugin, ProfilerConfig | solver.add_plugin(ProfilerPlugin(config=ProfilerConfig()))
Methods: on_solver_init=ok, on_population_init=missing, on_generation_start=missing, on_step=missing, on_generation_end=ok, on_solver_finish=ok
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `plugin.dynamic_switch`
Kind: plugin
Title: DynamicSwitchPlugin
Import: `nsgablack.plugins.runtime.dynamic_switch:DynamicSwitchPlugin`
Role: plugin
Summary: 信号驱动的运行模式/策略切换。 / Plugin: signal-driven runtime mode/strategy switching.
Tags: runtime, dynamic, switch, plugin
Context provides: dynamic, phase_id
Context mutates: dynamic, phase_id
Context notes: Builds runtime switch context with dynamic signals and phase id; applies soft/hard switch callbacks and syncs solver dynamic state.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: should_switch_fn, soft_switch_fn, hard_switch_fn, signal_provider, config
Use when: 需要根据收敛状态调整策略权重时。 / Need to adjust strategy weights based on convergence state. | 需要显式阶段切换（探索/利用）时。 / Need explicit phase switching (explore/exploit).
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.plugins import DynamicSwitchPlugin | plugin = DynamicSwitchPlugin(should_switch_fn=lambda solver, context: False, |     soft_switch_fn=lambda solver, context: None) | solver.add_plugin(plugin)
Methods: on_solver_init=missing, on_population_init=missing, on_generation_start=missing, on_step=missing, on_generation_end=missing, on_solver_finish=missing
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `plugin.async_event_hub`
Kind: plugin
Title: AsyncEventHubPlugin
Import: `nsgablack.plugins.system.async_event_hub:AsyncEventHubPlugin`
Role: plugin
Summary: 统一异步事件队列与提交边界。 / Plugin: unified async event queue and commit boundary.
Tags: system, async, event, plugin
Context provides: context_events
Context mutates: context_events
Context notes: Use generation_end commit to avoid half-written snapshots during UI/report reads.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: mode, commit_policy, max_pending, drop_policy, events_key
Use when: 需要为异步插件/策略提供统一提交边界时。 / Need a unified commit boundary for async plugins/strategies. | 需要 context 事件回放/审计时。 / Need context event replay/audit.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.plugins import AsyncEventHubPlugin, AsyncEventHubConfig | solver.add_plugin(AsyncEventHubPlugin(cfg=AsyncEventHubConfig(commit_policy='generation_end')))
Methods: on_solver_init=missing, on_population_init=missing, on_generation_start=missing, on_step=missing, on_generation_end=ok, on_solver_finish=missing
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `plugin.mysql_run_logger`
Kind: plugin
Title: MySQLRunLoggerPlugin
Import: `nsgablack.plugins.storage.mysql_run_logger:MySQLRunLoggerPlugin`
Role: plugin
Summary: 将运行元数据与报告路径落库到 MySQL。 / Plugin: persist run metadata and report paths to MySQL.
Tags: storage, mysql, database, plugin
Context notes: Reads solver/result metadata and writes run record to external MySQL table.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: host, port, user, password, database, table, connect_timeout
Use when: 多人协作需要集中检索实验资产时。 / Need centralized search of experiment assets for collaboration. | 批量运行需要统一数据库落库时。 / Need unified DB storage for batch runs.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.plugins import MySQLRunLoggerPlugin, MySQLRunLoggerConfig | solver.add_plugin(MySQLRunLoggerPlugin(config=MySQLRunLoggerConfig(database='nsgablack')))
Methods: on_solver_init=missing, on_population_init=missing, on_generation_start=missing, on_step=missing, on_generation_end=missing, on_solver_finish=ok
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `plugin.diversity_init`
Kind: plugin
Title: DiversityInitPlugin
Import: `nsgablack.plugins.runtime.diversity_init:DiversityInitPlugin`
Role: plugin
Summary: 通过重复/相似性控制提升初始多样性。 / Plugin: improve initial population diversity by duplicate/similarity control.
Tags: runtime, diversity, initializer, plugin
Context notes: Uses solver/population state to improve initialization diversity; does not persist context fields.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: similarity_threshold, rejection_prob
Use when: 初始种群重复或覆盖不足时。 / Initial population is repetitive/insufficient coverage. | 需要更广的早期探索时。 / Need broader early exploration.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.plugins import DiversityInitPlugin | solver.add_plugin(DiversityInitPlugin())
Methods: on_solver_init=ok, on_population_init=ok, on_generation_start=ok, on_step=missing, on_generation_end=ok, on_solver_finish=ok
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `plugin.elite`
Kind: plugin
Title: BasicElitePlugin (deprecated compatibility bridge)
Import: `nsgablack.plugins.runtime.elite_retention:BasicElitePlugin`
Role: plugin
Summary: 旧精英 Plugin 的迁移桥；attach 时将现有 Adapter 包装为事务型 EliteRetentionAdapter，不直接写 population authority。
Tags: compat, deprecated, elite, migration, plugin, retention
Context notes: Compatibility-only assembly bridge; population authority remains Adapter-owned.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: retention_prob, retention_ratio
Use when: 迁移仍调用 BasicElitePlugin 的旧装配代码时；新代码直接使用 adapter.elite_retention。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.plugins import BasicElitePlugin  # deprecated; remove_in=1.0.0 | solver.add_plugin(BasicElitePlugin())  # migrates to EliteRetentionAdapter
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `plugin.memory`
Kind: plugin
Title: MemoryPlugin
Import: `nsgablack.plugins.system.memory_optimize:MemoryPlugin`
Role: plugin
Summary: 周期清理内存并记录内存指标快照。 / Plugin: periodic memory cleanup with memory metric snapshots.
Tags: system, memory, runtime, plugin
Context notes: Optimizes solver memory usage and snapshots memory metrics; mutates solver temp_data/population arrays in-place for cleanup.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: cleanup_interval, enable_auto_gc
Use when: 长时间运行存在内存增长风险时。 / Long runs risk memory growth. | 并行评估导致内存压力较大时。 / Parallel evaluation causes high memory pressure.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.plugins import MemoryPlugin | solver.add_plugin(MemoryPlugin())
Methods: on_solver_init=ok, on_population_init=ok, on_generation_start=ok, on_step=missing, on_generation_end=ok, on_solver_finish=ok
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `plugin.gpu_eval_template`
Kind: plugin
Title: GpuEvaluationTemplateProviderPlugin
Import: `nsgablack.plugins.evaluation.gpu_evaluation_template:GpuEvaluationTemplateProviderPlugin`
Role: plugin
Summary: 最小 GPU 评估短路模板插件。 / Minimal GPU evaluation short-circuit template plugin.
Tags: plugin, evaluation, gpu, template, short_circuit
Context requires: problem
Context provides: metrics.gpu_backend, metrics.gpu_calls, metrics.gpu_fallbacks
Context mutates: metrics
Context notes: Returns None when backend/hook unavailable, so solver keeps default path.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: preferred_backend, device, fallback_to_solver_eval, warn_on_fallback
Use when: 需要最小 GPU 批量评估短路插件并具备安全回退时。 / Need a minimal GPU batch-evaluation short-circuit plugin with safe fallback.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.plugins import GpuEvaluationTemplateProviderPlugin | solver.register_evaluation_provider(GpuEvaluationTemplateProviderPlugin().create_provider())
Methods: on_solver_init=missing, on_population_init=missing, on_generation_start=missing, on_step=missing, on_generation_end=missing, on_solver_finish=missing
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `plugin.otel_tracing`
Kind: plugin
Title: OpenTelemetryTracingPlugin
Import: `nsgablack.plugins.ops.otel_tracing:OpenTelemetryTracingPlugin`
Role: plugin
Summary: OpenTelemetry 追踪：评估/适配器/插件运行事件。 / OpenTelemetry tracing for evaluate/adapter/plugin runtime events.
Tags: ops, observability, otel, tracing, plugin
Context requires: generation
Context notes: Emit spans for evaluate calls, adapter propose/update, and plugin event dispatch.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: service_name, service_version, configure_provider, console_export, otlp_http_endpoint, trace_evaluate, trace_adapter, trace_plugin_events
Use when: 需要端到端运行轨迹与求解器生命周期瓶颈诊断时。 / Need end-to-end runtime traces and bottleneck diagnosis across solver lifecycle.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.plugins import OpenTelemetryTracingPlugin, OpenTelemetryTracingConfig | solver.add_plugin(OpenTelemetryTracingPlugin(config=OpenTelemetryTracingConfig(console_export=True)))
Methods: on_solver_init=ok, on_population_init=missing, on_generation_start=missing, on_step=missing, on_generation_end=missing, on_solver_finish=ok
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `plugin.decision_trace`
Kind: plugin
Title: DecisionTracePlugin
Import: `nsgablack.plugins.ops.decision_trace:DecisionTracePlugin`
Role: plugin
Summary: 确定性决策路径追踪与回放产物（JSONL + 摘要）。 / Deterministic decision-path trace and replay artifacts (JSONL + summary).
Tags: ops, audit, replay, decision, plugin
Context requires: generation
Context provides: decision_trace_ref
Context mutates: decision_trace_ref
Context notes: Record decision events with reason_code/inputs/thresholds/evidence/outcome for replay.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: output_dir, run_id, overwrite, flush_every, capture_evaluate, capture_adapter, capture_plugin_events, include_context_events
Use when: 需要解释在特定代发生回退/预算/代理决策的原因时。 / Need to explain why fallback/budget/surrogate decisions happened at specific generations.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.plugins import DecisionTracePlugin, DecisionTraceConfig | solver.add_plugin(DecisionTracePlugin(config=DecisionTraceConfig(output_dir='runs', run_id='demo')))
Methods: on_solver_init=ok, on_population_init=missing, on_generation_start=missing, on_step=missing, on_generation_end=missing, on_solver_finish=ok
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `plugin.sequence_graph`
Kind: plugin
Title: SequenceGraphPlugin
Import: `nsgablack.plugins.ops.sequence_graph:SequenceGraphPlugin`
Role: plugin
Summary: 记录组件交互顺序并输出序列图产物。 / Record unique component interaction orders and write sequence-graph artifacts.
Tags: ops, audit, sequence, graph, timeline, plugin
Context provides: sequence_graph_ref
Context mutates: sequence_graph_ref
Context notes: Captures order-only interaction sequences (values ignored) and outputs a compact JSON graph.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: output_dir, run_id, overwrite, flush_every, boundary_groups, ignore_patterns, max_sequence_length, max_sequences, capture_adapter, capture_evaluate_population, capture_evaluate_individual, capture_plugin_events, trace_mode, trace_sample_rate, trace_max_events, trace_seed
Use when: 需要验证组件交互顺序、识别短路路径或审计编排流程时。 / Need to verify component interaction order, detect short-circuit paths, or audit orchestration flow.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.plugins import SequenceGraphPlugin, SequenceGraphConfig | solver.add_plugin(SequenceGraphPlugin(config=SequenceGraphConfig(output_dir='runs', run_id='demo')))
Methods: on_solver_init=ok, on_population_init=missing, on_generation_start=missing, on_step=missing, on_generation_end=missing, on_solver_finish=ok
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `plugin.sensitivity_analysis`
Kind: plugin
Title: SensitivityAnalysisPlugin
Import: `nsgablack.plugins.ops.sensitivity_analysis:SensitivityAnalysisPlugin`
Role: plugin
Summary: 敏感性分析插件：批量执行参数 sweep 并产出聚合 study artifact。 / Run parameter sweeps and publish aggregated study artifacts.
Tags: analysis, plugin, sensitivity, study, sweep
Context notes: Runs multi-run sensitivity studies and writes aggregated study artifacts.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: output_dir, run_id, seed, params, patch_benchmark_run_id, overwrite_benchmark, metric_fn
Use when: 需要比较参数变化对结果与稳定性的影响时 | 需要把批量实验收敛为统一 study artifact 时
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.plugins.ops.sensitivity_analysis import SensitivityAnalysisPlugin, SensitivityAnalysisConfig, SensitivityParam | study = SensitivityAnalysisPlugin(config=SensitivityAnalysisConfig( |     params=[SensitivityParam(path='adapter.cfg.base_sigma', values=[0.05, 0.15])])) | solver.add_plugin(study) | def run_authorized_study(build_solver): |     return study.run_study(build_solver)
Methods: on_solver_init=missing, on_population_init=missing, on_generation_start=missing, on_step=missing, on_generation_end=missing, on_solver_finish=missing
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `repr.unit_candidate`
Kind: representation
Title: CandidateUnitBuilder
Import: `nsgablack.representation:CandidateUnitBuilder`
Role: unit_builder
Concepts: Unit结构构建 | 自定义Unit | UnitBinding | 算法结构恢复
Runtime operations: build, dump, restore
Boundaries: 装配 builder 不创建运行 Unit；恢复走 codec，不重新随机构建。 | 不初始化候选、不执行问题 repair、不计算目标或决定成员选择。
Summary: 保留候选语义的轻量 Unit 构建器；由 Adapter 经独立 UnitBinding 使用，构建与恢复不执行搜索或求值。
Tags: core, unit, candidate, construction, codec
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: VNS 等轨迹算法需要独立的操作结构构建绑定时。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | VNSAdapter(unit_binding=UnitBinding(CandidateUnitBuilder()))
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `repr.unit_search_node`
Kind: representation
Title: SearchNodeBuilder
Import: `nsgablack.representation:SearchNodeBuilder`
Role: unit_builder
Concepts: Unit结构构建 | 自定义Unit | UnitBinding | 算法结构恢复
Runtime operations: build, dump, restore
Boundaries: 装配 builder 不创建运行 Unit；恢复走 codec，不重新随机构建。 | 不初始化候选、不执行问题 repair、不计算目标或决定成员选择。
Summary: A* 节点、父关联和代价存储的独立 Unit 构建器；边代价计算、扩展与优先级仍归 Adapter，不进入问题 Pipeline。
Tags: core, unit, astar, graph, construction, codec
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要替换 A* 节点结构，而保留搜索策略时。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | AStarAdapter(neighbors=neighbors, unit_binding=UnitBinding(SearchNodeBuilder()))
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `representation.parallel_repair`
Kind: representation
Title: ParallelRepair
Import: `nsgablack.representation:ParallelRepair`
Role: representation
Summary: 表示组件：ParallelRepair。 / Representation: ParallelRepair.
Tags: parallel, pipeline, repair
Context requires: candidate.unknown_state
Context provides: candidate.repaired_state
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要接入表示层的初始化/变异/修复行为时。 / Need to wire representation initializer/mutator/repair behavior.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.representation import RepresentationPipeline, ParallelRepair | from nsgablack.representation.continuous import ProjectionRepair | repair = ParallelRepair(ProjectionRepair(low=0.0, high=1.0), backend='thread', max_workers=1) | pipeline = RepresentationPipeline(repair=repair)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `representation.sbx_crossover`
Kind: representation
Title: SBXCrossover
Import: `nsgablack.representation.continuous:SBXCrossover`
Role: representation
Summary: 连续变量的模拟二进制交叉（SBX）。 / Representation: simulated binary crossover (SBX).
Tags: representation, crossover, sbx, continuous, bounds, nsga2
Context notes: SBX uses bounds (constructor or context).
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: eta_c, low, high
Use when: 需要在表示管线中使用连续变量的 SBX 交叉时。 / Need SBX crossover for continuous variables in representation pipeline.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.representation import RepresentationPipeline | from nsgablack.representation.continuous import SBXCrossover | pipeline = RepresentationPipeline(crossover=SBXCrossover(eta_c=15.0, low=0., high=1.))
Methods: init=missing, mutate=missing, repair=missing, encode=missing, decode=missing
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `representation.polynomial_mutation`
Kind: representation
Title: PolynomialMutation
Import: `nsgablack.representation.continuous:PolynomialMutation`
Role: representation
Summary: 连续变量多项式变异。 / Representation: polynomial mutation for continuous variables.
Tags: representation, mutation, polynomial, continuous, bounds, nsga2
Context notes: Polynomial mutation uses bounds (constructor or context).
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: eta_m, mutation_rate, low, high
Use when: 需要在表示管线中使用连续变量多项式变异时。 / Need polynomial mutation for continuous variables in representation pipeline.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.representation import RepresentationPipeline | from nsgablack.representation.continuous import PolynomialMutation | pipeline = RepresentationPipeline(mutator=PolynomialMutation(eta_m=20.0, low=0., high=1.))
Methods: init=missing, mutate=ok, repair=missing, encode=missing, decode=missing
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `repr.binary`
Kind: representation
Title: BinaryInitializer
Import: `nsgablack.representation.binary:BinaryInitializer`
Role: representation
Summary: 表示组件：BinaryInitializer。 / Representation: BinaryInitializer.
Tags: binary, bit, initializer
Context notes: Initializer is pure random Bernoulli sampling; no context I/O.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要接入表示层的初始化/变异/修复行为时。 / Need to wire representation initializer/mutator/repair behavior.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.representation import RepresentationPipeline | from nsgablack.representation.binary import BinaryInitializer | pipeline = RepresentationPipeline(initializer=BinaryInitializer(probability=0.5))
Methods: init=missing, mutate=missing, repair=missing, encode=missing, decode=missing
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `repr.context_gaussian`
Kind: representation
Title: ContextGaussianMutation
Import: `nsgablack.representation.continuous:ContextGaussianMutation`
Role: representation
Summary: 读取声明的 sigma_key 的可恢复高斯变异；可直接装配到 VNS/SA 等实际变化消费者，读取调用局部邻域参数并随所属 Adapter 回滚。
Tags: context, continuous, mutation, vns, operator, checkpoint
Context requires: mutation_sigma
Context notes: Reads mutation sigma from context; used by adaptive/VNS/SA style adapters.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: base_sigma, sigma_key, low, high
Use when: 需要 VNS 邻域或 SA 温度调度真正作用于变化尺度，而非固定高斯扰动时。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.representation.continuous import ContextGaussianMutation | from nsgablack.adapters import VNSAdapter | adapter = VNSAdapter(mutator=ContextGaussianMutation(base_sigma=0.1)) | # Keep this stateful instance owned by one Adapter or one Pipeline slot.
Methods: init=missing, mutate=ok, repair=missing, encode=missing, decode=missing
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `repr.context_switch`
Kind: representation
Title: ContextSelectMutator
Import: `nsgablack.representation:ContextSelectMutator`
Role: representation
Summary: 表示组件：ContextSelectMutator。 / Representation: ContextSelectMutator.
Tags: context, discrete, mutation, switch, vns
Context requires: vns_k
Context notes: Reads neighborhood index from context and dispatches to the matching mutator.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要接入表示层的初始化/变异/修复行为时。 / Need to wire representation initializer/mutator/repair behavior.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.representation import RepresentationPipeline, ContextSelectMutator | from nsgablack.representation.continuous import GaussianMutation | operator = ContextSelectMutator([GaussianMutation(sigma=0.05), GaussianMutation(sigma=0.2)]) | pipeline = RepresentationPipeline(mutator=operator)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `repr.continuous`
Kind: representation
Title: UniformInitializer
Import: `nsgablack.representation.continuous:UniformInitializer`
Role: representation
Summary: 连续均匀候选生成器：可直接绑定 Adapter 的 initializer 或放入既有 Pipeline，显式 RNG codec 支持恢复；池输入与暖启动优先。
Tags: continuous, initializer, real, operator, checkpoint
Context notes: Uniform initializer uses constructor bounds only; no context I/O.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: low, high
Use when: 希望独立配置算法初始候选来源，同时保留问题管线编解码和硬约束修复时。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.representation.continuous import UniformInitializer | from nsgablack.adapters import NSGA2Adapter | adapter = NSGA2Adapter(initializer=UniformInitializer(low=-1.0, high=1.0)) | # PoolTask intake and warm starts retain priority; initialization is not Unit construction.
Methods: init=missing, mutate=missing, repair=missing, encode=missing, decode=missing
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `repr.dynamic_repair`
Kind: representation
Title: DynamicRepair
Import: `nsgablack.representation.dynamic:DynamicRepair`
Role: representation
Summary: 表示组件：DynamicRepair。 / Representation: DynamicRepair.
Tags: dynamic, pipeline, repair
Context requires: generation
Context notes: Selects repair stage by generation from context.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要接入表示层的初始化/变异/修复行为时。 / Need to wire representation initializer/mutator/repair behavior.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.representation import RepresentationPipeline | from nsgablack.representation.dynamic import DynamicRepair | from nsgablack.representation.continuous import ProjectionRepair | pipeline = RepresentationPipeline(repair=DynamicRepair([(0, ProjectionRepair(low=0., high=1.)), (20, ProjectionRepair(low=0.2, high=0.8))]))
Methods: init=missing, mutate=missing, repair=ok, encode=missing, decode=missing
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `repr.graph`
Kind: representation
Title: GraphEdgeInitializer
Import: `nsgablack.representation.graph:GraphEdgeInitializer`
Role: representation
Summary: 表示组件：GraphEdgeInitializer。 / Representation: GraphEdgeInitializer.
Tags: graph, initializer, network
Context requires: num_nodes
Context notes: Reads number of graph nodes from context when problem metadata is absent.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要接入表示层的初始化/变异/修复行为时。 / Need to wire representation initializer/mutator/repair behavior.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.representation import RepresentationPipeline | from nsgablack.representation.graph import GraphEdgeInitializer | pipeline = RepresentationPipeline(initializer=GraphEdgeInitializer(num_nodes=4, density=0.3))
Methods: init=missing, mutate=missing, repair=missing, encode=missing, decode=missing
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `repr.integer`
Kind: representation
Title: IntegerInitializer
Import: `nsgablack.representation.integer:IntegerInitializer`
Role: representation
Summary: 表示组件：IntegerInitializer。 / Representation: IntegerInitializer.
Tags: discrete, initializer, integer
Context notes: Optionally reads context bounds when low/high are not explicitly configured.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要接入表示层的初始化/变异/修复行为时。 / Need to wire representation initializer/mutator/repair behavior.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.representation import RepresentationPipeline | from nsgablack.representation.integer import IntegerInitializer | pipeline = RepresentationPipeline(initializer=IntegerInitializer(low=0, high=10))
Methods: init=missing, mutate=missing, repair=missing, encode=missing, decode=missing
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `repr.matrix`
Kind: representation
Title: IntegerMatrixInitializer
Import: `nsgablack.representation.matrix:IntegerMatrixInitializer`
Role: representation
Summary: 表示组件：IntegerMatrixInitializer。 / Representation: IntegerMatrixInitializer.
Tags: grid, initializer, matrix
Context notes: Optionally reads matrix shape from context when rows/cols are not explicitly set.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要接入表示层的初始化/变异/修复行为时。 / Need to wire representation initializer/mutator/repair behavior.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.representation import RepresentationPipeline | from nsgablack.representation.matrix import IntegerMatrixInitializer | pipeline = RepresentationPipeline(initializer=IntegerMatrixInitializer(rows=2, cols=3, low=0, high=5))
Methods: init=missing, mutate=missing, repair=missing, encode=missing, decode=missing
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `repr.permutation`
Kind: representation
Title: PermutationInitializer
Import: `nsgablack.representation.permutation:PermutationInitializer`
Role: representation
Summary: 表示组件：PermutationInitializer。 / Representation: PermutationInitializer.
Tags: discrete, initializer, permutation, tsp
Context notes: Permutation initializer uses problem dimension only; no context I/O.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要接入表示层的初始化/变异/修复行为时。 / Need to wire representation initializer/mutator/repair behavior.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.representation import RepresentationPipeline | from nsgablack.representation.permutation import PermutationInitializer | pipeline = RepresentationPipeline(initializer=PermutationInitializer())
Methods: init=missing, mutate=missing, repair=missing, encode=missing, decode=missing
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `repr.pipeline`
Kind: representation
Title: RepresentationPipeline
Import: `nsgablack.representation:RepresentationPipeline`
Role: representation
Summary: 共享问题候选管线；支持默认变异与 Adapter 显式选择的具名算子，无需复制修复/编解码。
Tags: core, pipeline, representation
Context requires: candidate.unknown_state
Context provides: candidate.model
Context mutates: candidate.repaired_state
Context notes: Aggregates context contracts from configured pipeline operators.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: initializer, mutator, mutation_operators, repair, encoder, decoder
Use when: 需要接入表示层的初始化/变异/修复行为时。 / Need to wire representation initializer/mutator/repair behavior.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.representation import RepresentationPipeline | pipeline = RepresentationPipeline(mutator=default_mutator, repair=problem_repair, mutation_operators={'local': local_mutator}) | adapter.set_mutation_operator('local')  # bind the leaf consumer; other adapters may use the default
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `repr.projection_repair`
Kind: representation
Title: ProjectionRepair
Import: `nsgablack.representation.continuous:ProjectionRepair`
Role: representation
Summary: 表示组件：ProjectionRepair。 / Representation: ProjectionRepair.
Tags: bounds, pipeline, projection, repair, simplex
Context notes: Projection is driven by constructor/config values; no context I/O by default.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要接入表示层的初始化/变异/修复行为时。 / Need to wire representation initializer/mutator/repair behavior.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.representation import RepresentationPipeline | from nsgablack.representation.continuous import ProjectionRepair | pipeline = RepresentationPipeline(repair=ProjectionRepair(low=0., high=1., sum_target=1.0))
Methods: init=missing, mutate=missing, repair=ok, encode=missing, decode=missing
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `repr.context_dispatch`
Kind: representation
Title: ContextDispatchMutator
Import: `nsgablack.representation:ContextDispatchMutator`
Role: representation
Summary: 表示组件：按 strategy/phase 路由不同 mutator。 / Dispatch mutators by strategy or phase context.
Tags: context, dispatch, mutation, phase, representation, strategy
Context requires: strategy_id, phase
Context notes: Reads a selector key from context and dispatches mutator by route name.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: routes, selector_key, default_mutator, strict
Use when: 需要让表示层依据 phase 或 strategy_id 自动切换算子时
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.representation import RepresentationPipeline, ContextDispatchMutator | from nsgablack.representation.continuous import GaussianMutation | operator = ContextDispatchMutator(routes={'local': GaussianMutation(sigma=0.05)}, default_mutator=GaussianMutation(sigma=0.2)) | pipeline = RepresentationPipeline(mutator=operator)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `repr.pipeline_orchestrator`
Kind: representation
Title: PipelineOrchestrator
Import: `nsgablack.representation:PipelineOrchestrator`
Role: representation
Summary: 表示层编排控制器：统一 mutate/repair 的串行、路由与动态 phase 策略。 / Phase-aware mutate and repair orchestration controller.
Tags: context, controller, orchestrator, phase, pipeline, representation
Context requires: vns_k, strategy_id, phase, generation
Context notes: Optimization representation facade; execution semantics are owned by blackbase.kernel.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: mutate_policy, repair_policy, mutator, repair_operator, strict
Use when: 需要把 phase-aware 算子路由放在表示层正式协议中时
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.representation import RepresentationPipeline, PipelineOrchestrator | from nsgablack.representation.continuous import GaussianMutation | operator = PipelineOrchestrator(mutator=GaussianMutation(sigma=0.1)) | pipeline = RepresentationPipeline(mutator=operator)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `repr.unit_pareto_label`
Kind: representation
Title: ParetoLabelBuilder
Import: `nsgablack.representation:ParetoLabelBuilder`
Role: unit_builder
Concepts: Unit结构构建 | 自定义Unit | UnitBinding | 算法结构恢复
Runtime operations: build, dump, restore
Boundaries: 装配 builder 不创建运行 Unit；恢复走 codec，不重新随机构建。 | 不初始化候选、不执行问题 repair、不计算目标或决定成员选择。
Summary: ParetoLabelBuilder：独立算法结构与显式状态 codec 的构建器，由所属 Adapter 通过 UnitBinding 按需使用；不属于问题候选管线。
Tags: core, unit, structure, construction, codec
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 为对应 Adapter 定制操作结构或恢复 codec
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.units import UnitBinding | from nsgablack.representation import ParetoLabelBuilder | binding = UnitBinding(ParetoLabelBuilder())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `repr.unit_trajectory`
Kind: representation
Title: TrajectoryUnitBuilder
Import: `nsgablack.representation:TrajectoryUnitBuilder`
Role: unit_builder
Concepts: Unit结构构建 | 自定义Unit | UnitBinding | 算法结构恢复
Runtime operations: build, dump, restore
Boundaries: 装配 builder 不创建运行 Unit；恢复走 codec，不重新随机构建。 | 不初始化候选、不执行问题 repair、不计算目标或决定成员选择。
Summary: 独立轨迹结构构建器：schema v2 保存候选关联反馈与依赖版本，旧 v1 不自动恢复；Adapter 通过 UnitBinding 按需创建。
Tags: core, unit, structure, construction, codec
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 为对应 Adapter 定制操作结构或恢复 codec
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.units import UnitBinding | from nsgablack.representation import TrajectoryUnitBuilder | binding = UnitBinding(TrajectoryUnitBuilder())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `repr.unit_poll`
Kind: representation
Title: PollUnitBuilder
Import: `nsgablack.representation:PollUnitBuilder`
Role: unit_builder
Concepts: Unit结构构建 | 自定义Unit | UnitBinding | 算法结构恢复
Runtime operations: build, dump, restore
Boundaries: 装配 builder 不创建运行 Unit；恢复走 codec，不重新随机构建。 | 不初始化候选、不执行问题 repair、不计算目标或决定成员选择。
Summary: PollUnitBuilder：独立算法结构与显式状态 codec 的构建器，由所属 Adapter 通过 UnitBinding 按需使用；不属于问题候选管线。
Tags: core, unit, structure, construction, codec
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 为对应 Adapter 定制操作结构或恢复 codec
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.units import UnitBinding | from nsgablack.representation import PollUnitBuilder | binding = UnitBinding(PollUnitBuilder())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `repr.unit_parameters`
Kind: representation
Title: ParameterUnitBuilder
Import: `nsgablack.representation:ParameterUnitBuilder`
Role: unit_builder
Concepts: Unit结构构建 | 自定义Unit | UnitBinding | 算法结构恢复
Runtime operations: build, dump, restore
Boundaries: 装配 builder 不创建运行 Unit；恢复走 codec，不重新随机构建。 | 不初始化候选、不执行问题 repair、不计算目标或决定成员选择。
Summary: ParameterUnitBuilder：独立算法结构与显式状态 codec 的构建器，由所属 Adapter 通过 UnitBinding 按需使用；不属于问题候选管线。
Tags: core, unit, structure, construction, codec
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 为对应 Adapter 定制操作结构或恢复 codec
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.units import UnitBinding | from nsgablack.representation import ParameterUnitBuilder | binding = UnitBinding(ParameterUnitBuilder())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `repr.unit_population`
Kind: representation
Title: PopulationUnitBuilder
Import: `nsgablack.representation:PopulationUnitBuilder`
Role: unit_builder
Concepts: Unit结构构建 | 自定义Unit | UnitBinding | 算法结构恢复
Runtime operations: build, dump, restore
Boundaries: 装配 builder 不创建运行 Unit；恢复走 codec，不重新随机构建。 | 不初始化候选、不执行问题 repair、不计算目标或决定成员选择。
Summary: PopulationUnitBuilder：独立算法结构与显式状态 codec 的构建器，由所属 Adapter 通过 UnitBinding 按需使用；不属于问题候选管线。
Tags: core, unit, structure, construction, codec
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 为对应 Adapter 定制操作结构或恢复 codec
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.units import UnitBinding | from nsgablack.representation import PopulationUnitBuilder | binding = UnitBinding(PopulationUnitBuilder())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `repr.unit_reference_population`
Kind: representation
Title: ReferencePopulationBuilder
Import: `nsgablack.representation:ReferencePopulationBuilder`
Role: unit_builder
Concepts: Unit结构构建 | 自定义Unit | UnitBinding | 算法结构恢复
Runtime operations: build, dump, restore
Boundaries: 装配 builder 不创建运行 Unit；恢复走 codec，不重新随机构建。 | 不初始化候选、不执行问题 repair、不计算目标或决定成员选择。
Summary: 参考种群结构构建器，显式兼容基础 Population 契约，可由 NSGA2/SPEA2/NSGA3 经独立 UnitBinding 使用；不承担搜索策略。
Tags: core, unit, structure, construction, codec
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 为对应 Adapter 定制操作结构或恢复 codec
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.units import UnitBinding | from nsgablack.representation import ReferencePopulationBuilder | binding = UnitBinding(ReferencePopulationBuilder())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `repr.unit_differential_population`
Kind: representation
Title: DifferentialPopulationBuilder
Import: `nsgablack.representation:DifferentialPopulationBuilder`
Role: unit_builder
Concepts: Unit结构构建 | 自定义Unit | UnitBinding | 算法结构恢复
Runtime operations: build, dump, restore
Boundaries: 装配 builder 不创建运行 Unit；恢复走 codec，不重新随机构建。 | 不初始化候选、不执行问题 repair、不计算目标或决定成员选择。
Summary: DifferentialPopulationBuilder：独立算法结构与显式状态 codec 的构建器，由所属 Adapter 通过 UnitBinding 按需使用；不属于问题候选管线。
Tags: core, unit, structure, construction, codec
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 为对应 Adapter 定制操作结构或恢复 codec
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.units import UnitBinding | from nsgablack.representation import DifferentialPopulationBuilder | binding = UnitBinding(DifferentialPopulationBuilder())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `repr.unit_decomposition`
Kind: representation
Title: DecompositionUnitBuilder
Import: `nsgablack.representation:DecompositionUnitBuilder`
Role: unit_builder
Concepts: Unit结构构建 | 自定义Unit | UnitBinding | 算法结构恢复
Runtime operations: build, dump, restore
Boundaries: 装配 builder 不创建运行 Unit；恢复走 codec，不重新随机构建。 | 不初始化候选、不执行问题 repair、不计算目标或决定成员选择。
Summary: DecompositionUnitBuilder：独立算法结构与显式状态 codec 的构建器，由所属 Adapter 通过 UnitBinding 按需使用；不属于问题候选管线。
Tags: core, unit, structure, construction, codec
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 为对应 Adapter 定制操作结构或恢复 codec
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.units import UnitBinding | from nsgablack.representation import DecompositionUnitBuilder | binding = UnitBinding(DecompositionUnitBuilder())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `repr.unit_region`
Kind: representation
Title: RegionUnitBuilder
Import: `nsgablack.representation:RegionUnitBuilder`
Role: unit_builder
Concepts: Unit结构构建 | 自定义Unit | UnitBinding | 算法结构恢复
Runtime operations: build, dump, restore
Boundaries: 装配 builder 不创建运行 Unit；恢复走 codec，不重新随机构建。 | 不初始化候选、不执行问题 repair、不计算目标或决定成员选择。
Summary: 独立区域结构构建器：schema v2 关联中心反馈与依赖版本，旧 v1 不自动恢复；半径与搜索决策仍归 Adapter。
Tags: core, unit, structure, construction, codec
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 为对应 Adapter 定制操作结构或恢复 codec
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.units import UnitBinding | from nsgablack.representation import RegionUnitBuilder | binding = UnitBinding(RegionUnitBuilder())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `repr.unit_model_search`
Kind: representation
Title: ModelSearchUnitBuilder
Import: `nsgablack.representation:ModelSearchUnitBuilder`
Role: unit_builder
Concepts: Unit结构构建 | 自定义Unit | UnitBinding | 算法结构恢复
Runtime operations: build, dump, restore
Boundaries: 装配 builder 不创建运行 Unit；恢复走 codec，不重新随机构建。 | 不初始化候选、不执行问题 repair、不计算目标或决定成员选择。
Summary: ModelSearchUnitBuilder：独立算法结构与显式状态 codec 的构建器，由所属 Adapter 通过 UnitBinding 按需使用；不属于问题候选管线。
Tags: core, unit, structure, construction, codec
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 为对应 Adapter 定制操作结构或恢复 codec
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.units import UnitBinding | from nsgablack.representation import ModelSearchUnitBuilder | binding = UnitBinding(ModelSearchUnitBuilder())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `repr.unit_archive`
Kind: representation
Title: ArchiveUnitBuilder
Import: `nsgablack.representation:ArchiveUnitBuilder`
Role: unit_builder
Concepts: Unit结构构建 | 自定义Unit | UnitBinding | 算法结构恢复
Runtime operations: build, dump, restore
Boundaries: 装配 builder 不创建运行 Unit；恢复走 codec，不重新随机构建。 | 不初始化候选、不执行问题 repair、不计算目标或决定成员选择。
Summary: ArchiveUnitBuilder：独立算法结构与显式状态 codec 的构建器，由所属 Adapter 通过 UnitBinding 按需使用；不属于问题候选管线。
Tags: core, unit, structure, construction, codec
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 为对应 Adapter 定制操作结构或恢复 codec
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.units import UnitBinding | from nsgablack.representation import ArchiveUnitBuilder | binding = UnitBinding(ArchiveUnitBuilder())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `repr.unit_neighborhood`
Kind: representation
Title: NeighborhoodUnitBuilder
Import: `nsgablack.representation:NeighborhoodUnitBuilder`
Role: unit_builder
Concepts: Unit结构构建 | 自定义Unit | UnitBinding | 算法结构恢复
Runtime operations: build, dump, restore
Boundaries: 装配 builder 不创建运行 Unit；恢复走 codec，不重新随机构建。 | 不初始化候选、不执行问题 repair、不计算目标或决定成员选择。
Summary: NeighborhoodUnitBuilder：独立算法结构与显式状态 codec 的构建器，由所属 Adapter 通过 UnitBinding 按需使用；不属于问题候选管线。
Tags: core, unit, structure, construction, codec
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 为对应 Adapter 定制操作结构或恢复 codec
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.units import UnitBinding | from nsgablack.representation import NeighborhoodUnitBuilder | binding = UnitBinding(NeighborhoodUnitBuilder())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.pool_search`
Kind: adapter
Title: PoolSearchAdapter
Import: `nsgablack.adapters:PoolSearchAdapter`
Role: adapter
Summary: 池驱动优化组合：单解准备候选、独立种群搜索、停滞唤醒与返回竞争；使用既有 Solver 事务。
Tags: adapter, core, solution-pool, composition, stagnation
Context requires: solution_pool_time
Context provides: phase, task, solution_input_ref, solution_input_mode
Context notes: Pool prepare/search/recovery/return; explicit timestamped inputs and private child Units.
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: producer, searches, stagnation_steps, recovery_steps, restart_recovery, metric, recovery_selector
Use when: 需要按候选来源时点组合单解与种群算法，同时保持各 Unit 私有状态时。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import PoolSearchAdapter, PoolSearchSpec | adapter = PoolSearchAdapter(producer, [PoolSearchSpec(population_a, initial_count=120), PoolSearchSpec(population_b, initial_count=80)])
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `adapter.pool_task`
Kind: adapter
Title: PoolTaskAdapter
Import: `nsgablack.adapters:PoolTaskAdapter`
Role: adapter
Summary: 为现有多角色调度绑定候选子池、逐起点精修进度与返回引用；子算法沿用正式步骤事务。
Tags: adapter, core, solution-pool, subpool, composition
Context provides: role, role_adapter
Context notes: Role wrapper: injects role metadata and delegates propose/update to inner adapter.
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: inner, spec, role, worker, workers, namespace
Use when: 需要从种群结果中选取多个起点，分配给独立局部搜索实例，再返回种群竞争时。
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | from nsgablack.adapters import PoolTaskSpec, RoleSpec | role = RoleSpec('local', vns_factory, n_units=2, pool_task=PoolTaskSpec(select_refs, count='all', steps=5, output='refined'))
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.pool_task_spec`
Kind: tool
Title: PoolTaskSpec
Import: `nsgablack.adapters:PoolTaskSpec`
Role: pool_task
Concepts: GA停滞VNS精修 | GA加VNS | MOEA/D精修 | 池任务 | 算法返回竞争
Boundaries: select=None 使用最近工作区域；指定具名子池时要求其已存在。 | 被消费 Adapter 必须声明对应池输入模式；不能仅换类名认定支持。 | 返回候选由接收算法重新评估和竞争，不复制另一个算法的 Unit。
Summary: 明确母池或具名视图输入；按算法实例选择普通／投影结果视图，递归发布冻结来源与精确选择，沿用角色调度和恢复。
Tags: core, solution-pool, subpool, role, refinement
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: select, mode, steps, output, request_key, phases, count, distribution, on_insufficient, shuffle, change_sources, change_allow_main
Use when: 通过 RoleSpec/StrategySpec 在既有 Router 中装配池任务时。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.adapters import PoolTaskSpec | task = PoolTaskSpec(mode='initialize') | local = PoolTaskSpec('elite', count='all', steps=5) | # Additional donors for a plain change function are explicit public names. | task = PoolTaskSpec(mode='initialize', change_sources=('reference',), change_allow_main=True)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.solution_pool`
Kind: tool
Title: SolutionPool
Import: `nsgablack.core:SolutionPool`
Role: pool_store
Concepts: 解池 | 母池 | 子池 | 候选身份 | 候选版本 | 运行时点
Runtime operations: select, read, read_raw_feedback, create_subpool, add_to_subpool, drop_subpool, replace_subpool_members, update_subpool_members, remove_from_subpool, trim_subpool, subpool_metadata, projection_subpools, subpools_created_by, subpool_descriptor, children_subpools, publish_projection_subpool, publish_subpool_view
Boundaries: SolutionPool 保存不可原位改写的候选版本与引用区域；Unit 保存算法结构与关系。 | 解除子池成员不等于删除仍被其他消费者引用的候选。 | 池容量不是 population_size；操作可见性服从原步骤提交事务。
Summary: 运行内具名候选区域与引用子池；不可原位改写版本、逻辑时间与输入游标，可选显式引用保护和闲置回收。
Tags: core, solution-pool, snapshot, identity, transaction
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: snapshots, run_id
Use when: 需要显式存取、共享或按运行时点选择候选，且不传递其他算法的完整 Unit 时。
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | pool = solver.solution_pool | refs = pool.select(at=pool.timestamp, stage='accepted') | batch = solver.read_solutions(refs)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.subpools`
Kind: tool
Title: Adapter Result View Selectors
Import: `nsgablack.adapters:subpools`
Role: view_selector
Concepts: 选择算法结果视图 | 方向子池 | 按来源选子池 | MOEA/D精修
Runtime operations: all, random
Boundaries: 返回运行时选择计划；创建者是 Adapter 实例路径，不是类型名。 | all/random 不隐含等待屏障，不创建尚不存在的结果视图。
Summary: 按真实算法实例选择全部或随机 N 个普通／投影结果视图；冻结候选版本、父级与可选比较参数。
Tags: core, solution-pool, subpool, moead, projection, refinement
Wiring status: unverified
Wiring notes: 签名不可验证: TypeError
Config keys: (none)
Use when: 局部算法消费 NSGA／DE 种群、MOEA/D 方向，或继续消费上一层明确交付的结果时。
Minimal wiring: # recipe-status: unverified; 签名不可验证: TypeError | from nsgablack.adapters import PoolTaskSpec, subpools | task = PoolTaskSpec(subpools.random(20, adapter1), steps=3, output='refined') | next_task = PoolTaskSpec(subpools.all(coarse_vns), steps=3, output='fine')
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.objective_projection`
Kind: tool
Title: ObjectiveProjection
Import: `nsgablack.core:ObjectiveProjection`
Role: tool
Summary: 可传输的 weighted_sum/tchebycheff 比较坐标；原始目标与约束证据保留。
Tags: core, solution-pool, projection, feedback
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: method, weights, reference
Use when: 扩展方向投影生产者或检查冻结的比较参数时。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.core import ObjectiveProjection | projection = ObjectiveProjection('weighted_sum', (0.8, 0.2))
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.solution_ref`
Kind: tool
Title: SolutionRef
Import: `nsgablack.core:SolutionRef`
Role: tool
Summary: 同时定位候选身份和池记录版本的值引用；不以数值相等反查身份。
Tags: solution-pool, candidate, identity, version
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: pool_id, record_id, row, candidate_token
Use when: 在多个算法间传递明确的候选来源版本时。
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | refs = solver.store_solutions(candidate_batch) | batch = solver.read_solutions(refs)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.solution_stamp`
Kind: tool
Title: SolutionStamp
Import: `nsgablack.core:SolutionStamp`
Role: tool
Summary: 运行身份与池逻辑序号定义可见截止点；失败后保留时钟高水位，墙钟不参与排序。
Tags: solution-pool, logical-time, run, recovery
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: run_id, sequence, generation, attempt
Use when: 锁定串行、恢复或融合的候选来源时点时。
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | stamp = solver.solution_pool.timestamp | refs = solver.solution_pool.select(at=stamp)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.pool_retention_policy`
Kind: tool
Title: PoolRetentionPolicy
Import: `nsgablack.core:PoolRetentionPolicy`
Role: tool
Summary: 按已提交步数回收无人持有候选，保留指定发布窗口与显式固定的值闭包；不限制池容量。
Tags: core, solution-pool, retention, snapshot, recovery
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: idle_steps, retained_publications
Use when: 长期运行需要释放闲置候选存储，且 Adapter 已显式声明全部活引用时。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.core import PoolRetentionPolicy | solver.set_solution_pool_retention(PoolRetentionPolicy(idle_steps=20, retained_publications=2))
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.strategy_task`
Kind: tool
Title: StrategyTask
Import: `nsgablack.adapters:StrategyTask`
Role: tool
Summary: 多策略子任务：实例路径、阶段、原提案预算和局部区域/种子。
Tags: composition, contract, strategy, tool
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: owner_path, task_id, phase, budget, region_id, seeds
Use when: 子 Adapter 需要读取组合器分配的任务时。
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | from nsgablack.adapters import StrategyTask | task = StrategyTask.from_context(context)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.strategy_origin`
Kind: tool
Title: StrategyOrigin
Import: `nsgablack.adapters:StrategyOrigin`
Role: tool
Summary: 候选从外到内的策略来源，与 CandidateBatch/token 一起保存和筛选。
Tags: composition, contract, provenance, tool
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: owner_path, task_id, proposal_index
Use when: 查询数值相同候选各自的角色、实例和提案行来源时。
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | from nsgablack.adapters import StrategyOrigin | route = StrategyOrigin.from_candidate(batch.semantic_states[index])
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.runtime_participant`
Kind: tool
Title: RuntimeParticipant
Import: `blackbase.runtime:RuntimeParticipant`
Role: tool
Summary: 通用步骤事务参与者；局部快照、恢复、子参与者与提交后清理。
Tags: runtime-contract, authority, tool
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: snapshot_step_state, restore_step_state, commit_step_state, step_transaction_children
Use when: 新增有状态运行组件时。
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | from blackbase.runtime import RuntimeParticipant | solver.register_state_participant(component)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.representation_capabilities`
Kind: tool
Title: RepresentationCapabilities
Import: `blackbase.representation:RepresentationCapabilities`
Role: tool
Summary: 候选管线显式操作能力声明。
Tags: runtime-contract, authority, tool
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: operations, codec_deterministic, repair_idempotent
Use when: 组装 codec、搜索或 repair 的任意子集时。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from blackbase.representation import RepresentationCapabilities | RepresentationCapabilities(frozenset({'init', 'repair'}))
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.participation_contract`
Kind: tool
Title: ParticipationContract
Import: `blackbase.participation:ParticipationContract`
Role: tool
Summary: Plugin 与 Controller 的建议、决定和否决域。
Tags: runtime-contract, authority, tool
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: advises, decides, vetoes
Use when: 组件接管评估或参与严格结果发布时。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from blackbase.participation import ParticipationContract | ParticipationContract(vetoes=('finalization',))
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.preference_delta`
Kind: tool
Title: PreferenceDelta
Import: `blackbase.preferences:PreferenceDelta`
Role: tool
Summary: 保留原始反馈的偏好增量值。
Tags: runtime-contract, authority, tool
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: key, delta, reason
Use when: Bias 需要解释选择目标投影时。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from blackbase.preferences import PreferenceDelta | PreferenceDelta('objectives.0', -0.5, 'domain preference')
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.population_authority`
Kind: tool
Title: PopulationAuthority
Import: `nsgablack.core.state.population_authority:PopulationAuthority`
Role: tool
Summary: 运行内 population、身份、分区与发布游标所有者。
Tags: runtime-contract, authority, tool
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: mode, population, candidate_batch, partitions, snapshot_handle
Use when: 扩展权威状态或检查回滚边界时。
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | from nsgablack.core.state.population_authority import PopulationAuthority | authority = solver.population_authority
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.run_session`
Kind: tool
Title: RunSession
Import: `nsgablack.core.state.run:RunSession`
Role: tool
Summary: 运行身份、进度、预算、恢复队列与结果所有者。
Tags: runtime-contract, authority, tool
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: run_id, generation, result
Use when: 语义扩展需要恢复或读取运行进度时。
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | from nsgablack.core.state.run import RunSession | run = solver.run_session
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.finalization_hooks`
Kind: tool
Title: FinalizationHooks
Import: `blackbase.runtime:FinalizationHooks`
Role: tool
Summary: 结果准备和事务发布的显式注册入口。
Tags: runtime-contract, authority, tool
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: prepare_result, prepare, freeze, abort, publish
Use when: 结果或 Artifact 需要在 teardown 后发布时。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from blackbase.runtime import FinalizationHooks | solver.finalization_hooks = FinalizationHooks(prepare=prepare, freeze=freeze, abort=abort)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.semantic_extension`
Kind: tool
Title: SolverSemanticExtension
Import: `nsgablack.core.semantic_extension:SolverSemanticExtension`
Role: tool
Summary: 提交前语义准备与提交后投影扩展。
Tags: runtime-contract, authority, tool
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: name, before_step, after_step_committed
Use when: 扩展 ML 等语义但复用共享 step 事务时。
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | from nsgablack.core.semantic_extension import SolverSemanticExtension | solver.register_semantic_extension(extension)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.dynamic_cli_signal`
Kind: tool
Title: CLISignalProvider
Import: `nsgablack.utils.dynamic:CLISignalProvider`
Role: tool
Summary: CLISignalProvider 工具。 / CLISignalProvider.
Tags: cli, dynamic, signal, tool
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在流程装配或诊断中使用该工具时。 / Need this utility/tool in workflow assembly or diagnostics.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.utils.dynamic import CLISignalProvider | CLISignalProvider()
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.context_store_redis`
Kind: tool
Title: RedisContextStore
Import: `nsgablack.core.state.context_store:RedisContextStore`
Role: tool
Summary: Context 后端工具：RedisContextStore（共享状态，可选 TTL）。 / Context backend tool: RedisContextStore for shared context state with optional TTL.
Tags: context, redis, store, tool, backend, ttl
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: context_store_backend, context_store_redis_url, context_store_key_prefix, context_store_ttl_seconds
Use when: 需要 Redis 作为 context 存储/共享状态用于运行、回放或分布式时。 / Need Redis-backed context storage/shared state for runs, replay, or distributed workers.
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | from nsgablack.core.state.context_store import create_context_store | store = create_context_store(backend='redis', redis_url='redis://127.0.0.1:6379/0', key_prefix='nsgablack:run', ttl_seconds=30)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `solver.blank`
Kind: tool
Title: SolverBase
Import: `nsgablack.core.blank_solver:SolverBase`
Role: tool
Summary: 工具：SolverBase。 / Tool: SolverBase.
Tags: base, blank, solver
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在流程装配或诊断中使用该工具时。 / Need this utility/tool in workflow assembly or diagnostics.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.core.blank_solver import SolverBase | solver = SolverBase(problem=problem, representation_pipeline=pipeline)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `solver.composable`
Kind: tool
Title: ComposableSolver
Import: `nsgablack.core.composable_solver:ComposableSolver`
Role: tool
Summary: 工具：ComposableSolver。 / Tool: ComposableSolver.
Tags: adapter, composition, solver
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在流程装配或诊断中使用该工具时。 / Need this utility/tool in workflow assembly or diagnostics.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.core.composable_solver import ComposableSolver | solver = ComposableSolver(problem=problem, representation_pipeline=pipeline, adapter=adapter)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `solver.nsga2`
Kind: tool
Title: EvolutionSolver
Import: `nsgablack.core.evolution_solver:EvolutionSolver`
Role: tool
Summary: 工具：EvolutionSolver。 / Tool: EvolutionSolver.
Tags: evolutionary, nsga2, solver
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在流程装配或诊断中使用该工具时。 / Need this utility/tool in workflow assembly or diagnostics.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.core.evolution_solver import EvolutionSolver | solver = EvolutionSolver(problem=problem, representation_pipeline=pipeline)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.context_keys`
Kind: tool
Title: Context Keys
Import: `blackbase.context:context_keys`
Role: tool
Summary: 工具：Context Keys。 / Tool: Context Keys.
Tags: context, keys, schema, tool
Wiring status: unverified
Wiring notes: 签名不可验证: TypeError
Config keys: (none)
Use when: 需要在流程装配或诊断中使用该工具时。 / Need this utility/tool in workflow assembly or diagnostics.
Minimal wiring: # recipe-status: unverified; 签名不可验证: TypeError | from blackbase.context import context_keys | from nsgablack.context_keys import KEY_GENERATION | def read_generation(context): |     return context.get(KEY_GENERATION, 0)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.context_schema`
Kind: tool
Title: MinimalEvaluationContext
Import: `nsgablack.core.state:MinimalEvaluationContext`
Role: tool
Summary: 工具：MinimalEvaluationContext。 / Tool: MinimalEvaluationContext.
Tags: context, parallel, schema, tool
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在流程装配或诊断中使用该工具时。 / Need this utility/tool in workflow assembly or diagnostics.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.core.state import MinimalEvaluationContext | local = MinimalEvaluationContext(generation=0, individual_id=0, |     constraints=[], constraint_violation=0.0) | print(local.individual_id)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.logging`
Kind: tool
Title: configure_logging
Import: `nsgablack.utils.engineering:configure_logging`
Role: tool
Summary: 工具：configure_logging。 / Tool: configure_logging.
Tags: engineering, logging, tool
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在流程装配或诊断中使用该工具时。 / Need this utility/tool in workflow assembly or diagnostics.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.utils.engineering import configure_logging | configure_logging()
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.metrics`
Kind: tool
Title: pareto_filter
Import: `nsgablack.utils.analysis:pareto_filter`
Role: tool
Summary: 工具：pareto_filter。 / Tool: pareto_filter.
Tags: analysis, metrics, pareto, tool
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在流程装配或诊断中使用该工具时。 / Need this utility/tool in workflow assembly or diagnostics.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.utils.analysis import pareto_filter | front = pareto_filter([[1.0, 2.0], [2.0, 1.0], [3.0, 3.0]]) | print(front)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.parallel_evaluator`
Kind: tool
Title: ParallelEvaluator
Import: `nsgablack.utils.parallel:ParallelEvaluator`
Role: tool
Summary: 工具：ParallelEvaluator。 / Tool: ParallelEvaluator.
Tags: evaluation, parallel, tool
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: (none)
Use when: 需要在流程装配或诊断中使用该工具时。 / Need this utility/tool in workflow assembly or diagnostics.
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.utils.parallel import ParallelEvaluator | ParallelEvaluator()
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.population_change`
Kind: tool
Title: PopulationChange
Import: `nsgablack.units:PopulationChange`
Role: member_change
Concepts: 种群扩展字段 | 成员变化传播 | 成员对齐 | 新增Unit字段
Boundaries: Adapter 决定成员，Unit 按来源映射维护声明字段。 | 只读 on_members_changed 不执行选择、评估或修改原 Unit。
Summary: 成员操作的明确来源映射：Adapter 决策，Unit 对齐候选/反馈/token 并维护自定义行字段。
Tags: unit, population, members, provenance
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: operation, previous_count, incoming_count, previous_member_indices, incoming_member_indices
Use when: 自定义种群成员字段，需要随选择或替换维护时。
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | from dataclasses import dataclass, field | import numpy as np | from nsgablack.units import PopulationUnit | @dataclass | class AgePopulation(PopulationUnit): |     age: object = field(default=None) |     member_fields = ('age',) |     def on_members_changed(self, change): |         return {'age': np.array([0 if i is None else self.age[i] |             for i in change.previous_member_indices])}
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.unit_input_spec`
Kind: tool
Title: UnitInputSpec
Import: `nsgablack.units:UnitInputSpec`
Role: unit_dependency
Concepts: Unit依赖 | 种群扩展字段 | 算子读取Unit
Boundaries: 依赖由实际叶 Adapter 捕获；共享 context 不用于猜测 Unit 所有者。
Summary: 变异算子显式声明 Unit 字段与特征，由实际 Adapter 提供脱离只读输入。
Tags: unit, operator, dependency, readonly
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: fields, features, feedback_view, schema
Use when: 变异需要读取种群、区域或其他 Unit 信息时。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.units import UnitInputSpec | unit_inputs = UnitInputSpec(fields=('population',)) | # Define mutate(candidate, context, *, unit); read unit.fields['population']
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.unit_inputs`
Kind: tool
Title: UnitInputs
Import: `nsgablack.units:UnitInputs`
Role: unit_dependency
Concepts: Unit依赖 | 种群扩展字段 | 算子读取Unit
Boundaries: 依赖由实际叶 Adapter 捕获；共享 context 不用于猜测 Unit 所有者。
Summary: 调用局部的只读 Unit 字段/特征投影，携带 unit_id、schema 和依赖版本。
Tags: unit, operator, readonly
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: unit_id, schema, revision, fields, features
Use when: 读取算子声明的 Unit 依赖，不暴露可写 Unit 或 Solver 时。
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | from nsgablack.units import UnitInputSpec | class TowardCenter: |     stateless = True |     unit_inputs = UnitInputSpec(fields=('population',)) |     def checkpoint_identity(self): return {'name': 'toward_center', 'version': 1} |     def mutate(self, candidate, context, *, unit): |         return candidate + 0.1 * (unit.fields['population'].mean(axis=0) - candidate) | adapter.set_mutator(TowardCenter())
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.unit_feature`
Kind: tool
Title: UnitFeature
Import: `nsgablack.units:UnitFeature`
Role: unit_feature
Concepts: Unit依赖 | 种群扩展字段 | 算子读取Unit
Boundaries: 依赖由实际叶 Adapter 捕获；共享 context 不用于猜测 Unit 所有者。
Summary: 候选/集合的算法特征声明：显式字段依赖、raw/selection 反馈视图和可选增量更新。
Tags: unit, feature, dependency, cache
Wiring status: signature-checked
Wiring notes: 仅通过语法和构造签名检查；不等于行为已验证
Config keys: name, depends_on, compute, feedback_view, update
Use when: 给 Unit 添加按依赖变化维护的派生特征时。
Minimal wiring: # recipe-status: signature-checked; 仅通过语法和构造签名检查；不等于行为已验证 | from nsgablack.units import UnitFeature | feature = UnitFeature('center', ('population',), lambda data: data['population'].mean(axis=0)) | center = unit.feature(feature)
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `tool.feature_unit`
Kind: tool
Title: FeatureUnit
Import: `nsgablack.units:FeatureUnit`
Role: unit_feature_base
Concepts: Unit派生特征 | 增量特征 | 特征失效
Runtime operations: feature, clear_features
Boundaries: 只读派生缓存不是另一份权威成员；缓存不进入 checkpoint。
Summary: Unit 的按需派生特征能力：按实例隔离、校验依赖内容、只读结果、缓存不进入 checkpoint。
Tags: unit, feature, readonly, cache
Wiring status: guidance
Wiring notes: 片段未直接构造该组件
Config keys: (none)
Use when: 使用或扩展内置 Unit 的派生特征维护能力时。
Minimal wiring: # recipe-status: guidance; 片段未直接构造该组件 | value = unit.feature(feature) | fresh = unit.feature(feature, cache=False) | unit.clear_features()
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.assembly.build_trainer`
Kind: assembly
Title: build_trainer
Import: `mlblack.assembly.builders:build_trainer`
Role: assembly
Summary: Builds one ML trainer Case surface; orchestration belongs to the shared Project substrate.
Tags: scaffold, trainer, inner-training
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.bias.branch_policy`
Kind: bias
Title: BranchPolicyBias
Import: `mlblack.bias.policies:BranchPolicyBias`
Role: bias
Summary: Exposes branch preferences for conditional/piecewise representations.
Tags: soft-preference, conditional, branch
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.bias.dynamic_pool`
Kind: bias
Title: DynamicPoolBias
Import: `mlblack.bias.policies:DynamicPoolBias`
Role: bias
Summary: Projects a context-dependent candidate/model pool hint.
Tags: soft-preference, pool, event
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.bias.l2_scale`
Kind: bias
Title: L2ScaleBias
Import: `mlblack.bias.policies:L2ScaleBias`
Role: bias
Summary: Expose a dynamic L2 scale to problems/adapters through context.
Tags: bias, policies
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.bias.noop`
Kind: bias
Title: NoopBias
Import: `mlblack.bias.policies:NoopBias`
Role: bias
Summary: Soft preference component for optimization feedback/context.
Tags: bias, policies
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.bias.objective_policy`
Kind: bias
Title: ObjectivePolicyBias
Import: `mlblack.bias.policies:ObjectivePolicyBias`
Role: bias
Summary: Context-aware objective reweighting policy.
Tags: soft-preference, multi-objective, policy
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.bias.objective_weight`
Kind: bias
Title: ObjectiveWeightBias
Import: `mlblack.bias.policies:ObjectiveWeightBias`
Role: bias
Summary: Reweights objective dimensions before adapter update.
Tags: soft-preference, multi-objective
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.bias.optimization`
Kind: bias
Title: OptimizationBias
Import: `mlblack.bias.base:OptimizationBias`
Role: bias
Summary: Soft preference component for optimization feedback/context.
Tags: bias, base
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.bias.state_l2`
Kind: bias
Title: StateL2Bias
Import: `mlblack.bias.policies:StateL2Bias`
Role: bias
Summary: Adds a soft L2 penalty to feedback objectives.
Tags: soft-preference, regularization
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.capability.experiment_tracker`
Kind: capability
Title: ExperimentTrackerCapability
Import: `mlblack.capabilities.tracking:ExperimentTrackerCapability`
Role: capability
Summary: Records fit/step/evaluation events to an experiment store.
Tags: experiment, sqlite, run-record
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.capability.resource_audit`
Kind: capability
Title: ResourceAuditCapability
Import: `mlblack.capabilities.resource_audit:ResourceAuditCapability`
Role: capability
Summary: Audits effective ResourceContext during fit.
Tags: l0, resource, audit
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.catalog.materialize_db`
Kind: catalog
Title: materialize catalog DB
Import: `mlblack.catalog.store:materialize_catalog_db`
Role: catalog
Summary: Materializes the authoritative TOML catalog into a SQLite DB snapshot.
Tags: catalog, sqlite, materialize
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.catalog.query`
Kind: catalog
Title: catalog query
Import: `mlblack.catalog.query:query_catalog`
Role: catalog
Summary: Search catalog entries with facets and deep-link payload.
Tags: catalog, facet, deep-link
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.catalog.query_db`
Kind: catalog
Title: DB-only catalog query
Import: `mlblack.catalog.query:query_catalog_db`
Role: catalog
Summary: Query a materialized catalog DB without loading the TOML source surface.
Tags: catalog, sqlite, db-only, facet
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.catalog.resolve_store`
Kind: catalog
Title: resolve_catalog_store
Import: `mlblack.catalog.store:resolve_catalog_store`
Role: catalog
Summary: Resolves SQLite or PostgreSQL catalog stores from URL/path/env configuration.
Tags: catalog, sqlite, postgresql, db-only
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.catalog.store_postgresql`
Kind: catalog
Title: PostgresCatalogStore
Import: `mlblack.catalog.store:PostgresCatalogStore`
Role: catalog
Summary: PostgreSQL implementation of the DB-only catalog store surface.
Tags: catalog, postgresql, db-only
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.catalog.store_sqlite`
Kind: catalog
Title: SQLiteCatalogStore
Import: `mlblack.catalog.store:SQLiteCatalogStore`
Role: catalog
Summary: SQLite implementation of the DB-only catalog store surface.
Tags: catalog, sqlite, db-only
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.codec.estimator_spec`
Kind: codec
Title: EstimatorSpecCodec
Import: `mlblack.representations.codecs.estimators:EstimatorSpecCodec`
Role: codec
Summary: External estimator-spec codec with typed mechanism metadata.
Tags: codec, representations, codecs, estimators
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.codec.linear_point`
Kind: codec
Title: LinearPointCodec
Import: `mlblack.representations.codecs.linear:LinearPointCodec`
Role: codec
Summary: Raw linear parameter codec used by headed representations.
Tags: codec, representations, codecs, linear
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.codec.neural_graph`
Kind: codec
Title: NeuralGraphCodec
Import: `mlblack.representations.codecs.neural.base:NeuralGraphCodec`
Role: codec
Summary: Decode a flat parameter state into a neural model from NeuralGraphSpec.
Tags: codec, representations, codecs, neural, base
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.codec.neural_tabular_tabnet_spec`
Kind: codec
Title: NeuralGraphSpec.tabular_tabnet
Import: `mlblack.representations.codecs.neural.specs:NeuralGraphSpec.tabular_tabnet`
Role: codec
Summary: 构建 TabNet 风格表格深度学习的 NeuralGraphSpec 路由，含特征 Transformer、注意力掩码和 GLU 激活。
Tags: neural, tabular, tabnet, attention, backend-route
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.codec.neural_temporal_deepar_spec`
Kind: codec
Title: NeuralGraphSpec.temporal_deepar
Import: `mlblack.representations.codecs.neural.specs:NeuralGraphSpec.temporal_deepar`
Role: codec
Summary: 构建 DeepAR 风格概率预测的 NeuralGraphSpec 路由，LSTM 主干输出 mu 和 log_sigma 分布参数。
Tags: neural, time-series, temporal, deepar, probabilistic, backend-route
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.codec.neural_temporal_lstm_spec`
Kind: codec
Title: NeuralGraphSpec.temporal_lstm
Import: `mlblack.representations.codecs.neural.specs:NeuralGraphSpec.temporal_lstm`
Role: codec
Summary: 构建 LSTM 风格序列预测的 NeuralGraphSpec 路由，通过后端神经网络降层执行。
Tags: neural, time-series, temporal, lstm, backend-route
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.codec.neural_temporal_nbeats_spec`
Kind: codec
Title: NeuralGraphSpec.temporal_nbeats
Import: `mlblack.representations.codecs.neural.specs:NeuralGraphSpec.temporal_nbeats`
Role: codec
Summary: 构建 N-BEATS 风格堆叠残差块预测的 NeuralGraphSpec 路由，通过后端神经网络降层执行。
Tags: neural, time-series, temporal, nbeats, backend-route
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.codec.neural_temporal_patchtst_spec`
Kind: codec
Title: NeuralGraphSpec.temporal_patchtst
Import: `mlblack.representations.codecs.neural.specs:NeuralGraphSpec.temporal_patchtst`
Role: codec
Summary: 构建 PatchTST 风格补丁嵌入 + Transformer 编码器预测的 NeuralGraphSpec 路由。
Tags: neural, time-series, temporal, patchtst, transformer, backend-route
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.codec.neural_temporal_tcn_spec`
Kind: codec
Title: NeuralGraphSpec.temporal_tcn
Import: `mlblack.representations.codecs.neural.specs:NeuralGraphSpec.temporal_tcn`
Role: codec
Summary: 构建 TCN 风格序列预测的 NeuralGraphSpec 路由，通过后端神经网络降层执行。
Tags: neural, time-series, temporal, tcn, backend-route
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.codec.neural_temporal_tft_spec`
Kind: codec
Title: NeuralGraphSpec.temporal_tft
Import: `mlblack.representations.codecs.neural.specs:NeuralGraphSpec.temporal_tft`
Role: codec
Summary: 构建 Temporal Fusion Transformer (TFT) 风格的 NeuralGraphSpec 路由，含门控残差网络和可解释多头自注意力。
Tags: neural, time-series, temporal, tft, attention, backend-route
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.codec.neural_temporal_transformer_spec`
Kind: codec
Title: NeuralGraphSpec.temporal_transformer
Import: `mlblack.representations.codecs.neural.specs:NeuralGraphSpec.temporal_transformer`
Role: codec
Summary: 构建时序 Transformer 预测的 NeuralGraphSpec 路由，通过后端神经网络降层执行。
Tags: neural, time-series, temporal, transformer, backend-route
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.codec.orthogonal_linear_point`
Kind: codec
Title: OrthogonalLinearPointCodec
Import: `mlblack.representations.codecs.linear:OrthogonalLinearPointCodec`
Role: codec
Summary: Orthogonal-feature linear parameter codec.
Tags: codec, representations, codecs, linear
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.codec.symbolic_expression`
Kind: codec
Title: SymbolicExpressionCodec
Import: `mlblack.representations.codecs.symbolic:SymbolicExpressionCodec`
Role: codec
Summary: Fixed symbolic expression codec.
Tags: codec, representations, codecs, symbolic
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.codec.symbolic_multi_expression`
Kind: codec
Title: SymbolicMultiExpressionCodec
Import: `mlblack.representations.codecs.symbolic:SymbolicMultiExpressionCodec`
Role: codec
Summary: Fixed multi-expression codec used by basis-set heads.
Tags: codec, representations, codecs, symbolic
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.codec.tunable_parameter`
Kind: codec
Title: TunableParameterSpec
Import: `mlblack.representations.codecs.estimators:TunableParameterSpec`
Role: codec
Summary: TunableParameterSpec(name: 'str', low: 'float' = 0.0, high: 'float' = 1.0, integer: 'bool' = False)
Tags: codec, representations, codecs, estimators
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.conditional.binary_gate`
Kind: conditional
Title: BinaryGate
Import: `mlblack.pipeline.conditional.primitives:BinaryGate`
Role: conditional
Summary: BinaryGate(feature_index: 'int' = 0, threshold: 'float' = 0.0)
Tags: conditional, pipeline, primitives
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.conditional.composer`
Kind: conditional
Title: PrimitiveFeatureComposer
Import: `mlblack.pipeline.conditional.composer:PrimitiveFeatureComposer`
Role: conditional
Summary: Composes conditional primitives into deterministic feature transforms.
Tags: composer, feature-engineering, piecewise
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.conditional.conditional`
Kind: conditional
Title: ConditionalPrimitive
Import: `mlblack.pipeline.conditional.primitives:ConditionalPrimitive`
Role: conditional
Summary: Auto-discovered mlblack component `conditional.conditional`.
Tags: conditional, pipeline, primitives
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.conditional.conditional_primitive`
Kind: conditional
Title: ConditionalPrimitiveSpec
Import: `mlblack.pipeline.conditional.primitives:ConditionalPrimitiveSpec`
Role: conditional
Summary: Declarative conditional primitive used by symbolic grammar lowering.
Tags: conditional, pipeline, primitives
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.conditional.hinge_feature`
Kind: conditional
Title: HingeFeature
Import: `mlblack.pipeline.conditional.primitives:HingeFeature`
Role: conditional
Summary: HingeFeature(feature_index: 'int' = 0, knot: 'float' = 0.0, side: 'str' = 'right')
Tags: conditional, pipeline, primitives
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.conditional.one_hot_gate`
Kind: conditional
Title: OneHotGate
Import: `mlblack.pipeline.conditional.primitives:OneHotGate`
Role: conditional
Summary: OneHotGate(feature_index: 'int' = 0, values: 'Sequence[float]' = <factory>)
Tags: conditional, pipeline, primitives
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.conditional.primitive_feature_composer`
Kind: conditional
Title: PrimitiveFeatureComposer
Import: `mlblack.pipeline.conditional.composer:PrimitiveFeatureComposer`
Role: conditional
Summary: PrimitiveFeatureComposer(primitives: 'Sequence[ConditionalPrimitive | Mapping[str, Any] | str]', include_original: 'bool' = True, metadata: 'Mapping[str, Any]' = <factory>)
Tags: conditional, pipeline, composer
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.conditional.primitives`
Kind: conditional
Title: Conditional Primitives
Import: `mlblack.pipeline.conditional.primitives:ConditionalPrimitive`
Role: conditional
Summary: Reusable conditional feature and routing primitives.
Tags: binary-gate, soft-gate, hinge, onehot
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.conditional.route_then_formula_composer`
Kind: conditional
Title: RouteThenFormulaComposer
Import: `mlblack.pipeline.conditional.composer:RouteThenFormulaComposer`
Role: conditional
Summary: Composable condition descriptor for representation builders.
Tags: conditional, pipeline, composer
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.conditional.shared_backbone_residual_composer`
Kind: conditional
Title: SharedBackboneResidualComposer
Import: `mlblack.pipeline.conditional.composer:SharedBackboneResidualComposer`
Role: conditional
Summary: SharedBackboneResidualComposer(backbone: 'Any', residual_branches: 'Sequence[Any]', router: 'Any | None' = None, metadata: 'Mapping[str, Any]' = <factory>)
Tags: conditional, pipeline, composer
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.conditional.soft_gate`
Kind: conditional
Title: SoftGate
Import: `mlblack.pipeline.conditional.primitives:SoftGate`
Role: conditional
Summary: SoftGate(feature_index: 'int' = 0, threshold: 'float' = 0.0, temperature: 'float' = 1.0)
Tags: conditional, pipeline, primitives
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.core.provider_backed_learning`
Kind: core
Title: ProviderBackedLearningProblem
Import: `mlblack.core.provider_problem:ProviderBackedLearningProblem`
Role: core
Summary: 保留 ML Problem 语义并通过 BlackBase EvaluationGateway 绑定 Provider 的正式 Problem facade。
Tags: core, problem, evaluation-provider, blackbase, l0
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.core.functional_gradient_learning`
Kind: core
Title: FunctionalGradientLearningProblem
Import: `mlblack.core.provider_problem:FunctionalGradientLearningProblem`
Role: core
Summary: 在 ML Problem/Provider 边界生成函数式梯度，交由 NSGABlack gradient.* Adapter 消费。
Tags: core, problem, evaluation-provider, jax, tensorflow, gradient
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.core.artifact_bundle`
Kind: core
Title: ArtifactBundle
Import: `mlblack.core.artifacts:ArtifactBundle`
Role: core
Summary: Final output bundle with explicit product boundaries.
Tags: core, artifacts
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.core.capability`
Kind: core
Title: Capability
Import: `mlblack.core.capability:Capability`
Role: core
Summary: ML semantic Plugin with fit-oriented hook names.
Tags: core, capability
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.core.diagnostic`
Kind: core
Title: DiagnosticProblem
Import: `mlblack.core.diagnostic:DiagnosticProblem`
Role: core
Summary: Problem surface for a single non-search ML diagnostic evaluation.
Tags: core, diagnostic
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.core.diagnostic_representation`
Kind: core
Title: DiagnosticRepresentation
Import: `mlblack.core.diagnostic:DiagnosticRepresentation`
Role: core
Summary: 诊断 Case 的固定语义候选表示；控制生命周期由 NSGABlack FixedCandidateAdapter 提供。
Tags: core, diagnostic, representation, one-shot
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.core.estimator_state_artifact`
Kind: core
Title: EstimatorStateArtifact
Import: `mlblack.core.artifacts:EstimatorStateArtifact`
Role: core
Summary: EstimatorStateArtifact(name: 'str', model: 'Any', family: 'str' = '', head: 'str' = 'point', representation: 'Mapping[str, Any]' = <factory>, metadata: 'Mapping[str, Any]' = <factory>, artifact_type: 'str' = 'estimator_state', estimator_state: 'Mapping[str, Any]' = <factory>)
Tags: core, artifacts
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.core.head_block`
Kind: core
Title: HeadBlock
Import: `mlblack.core.head:HeadBlock`
Role: core
Summary: Contiguous parameter block consumed by an output head.
Tags: core, head
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.core.integrated_model_artifact`
Kind: core
Title: IntegratedModelArtifact
Import: `mlblack.core.artifacts:IntegratedModelArtifact`
Role: core
Summary: IntegratedModelArtifact(name: 'str', model: 'Any', family: 'str' = '', head: 'str' = 'point', representation: 'Mapping[str, Any]' = <factory>, metadata: 'Mapping[str, Any]' = <factory>, artifact_type: 'str' = 'integrated_model')
Tags: core, artifacts
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.core.learning`
Kind: core
Title: LearningProblem
Import: `mlblack.core.problem:LearningProblem`
Role: core
Summary: 定义数据相关的 loss、指标与约束；具有拟合或内层求解准备的模型，须用 restore_model_for_evaluation 从已保存证据恢复。
Tags: core, problem
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.core.model`
Kind: core
Title: ModelRepresentation
Import: `mlblack.core.representation:ModelRepresentation`
Role: core
Summary: 解释候选的模型含义，提供 Codec、布局与修复；维度来自模型布局，真实初始化在共享 Pool 建立后的运行阶段执行。
Tags: core, representation
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.core.model_artifact`
Kind: core
Title: ModelArtifact
Import: `mlblack.core.artifacts:ModelArtifact`
Role: core
Summary: Serializable boundary around the trained model payload.
Tags: core, artifacts
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.core.neural_graph_artifact`
Kind: core
Title: NeuralGraphArtifact
Import: `mlblack.core.artifacts:NeuralGraphArtifact`
Role: core
Summary: NeuralGraphArtifact(name: 'str', model: 'Any', family: 'str' = '', head: 'str' = 'point', representation: 'Mapping[str, Any]' = <factory>, metadata: 'Mapping[str, Any]' = <factory>, artifact_type: 'str' = 'neural_graph', graph_spec: 'Mapping[str, Any]' = <factory>, parameter_layout: 'Mapping[str, Any]' = <factory>, head_artifact: 'Mapping[str, Any]' = <factory>, audit_artifact: 'Mapping[str, Any]' = <factory>, graph_spec_digest: 'str' = '', parameter_layout_digest: 'str' = '')
Tags: core, artifacts
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.core.output`
Kind: core
Title: OutputHead
Import: `mlblack.core.head:OutputHead`
Role: core
Summary: Decoder-side output semantics.
Tags: core, head
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.core.representation_pipeline`
Kind: core
Title: RepresentationPipeline
Import: `mlblack.core.representation:RepresentationPipeline`
Role: core
Summary: Unknown-state encoder/decoder, equivalent to nsgablack Representation.
Tags: core, representation
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.core.run_report`
Kind: core
Title: RunReport
Import: `mlblack.core.artifacts:RunReport`
Role: core
Summary: Auditable run summary distinct from artifact and trainer state.
Tags: core, artifacts
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.core.sklearn_mlp_artifact`
Kind: core
Title: SklearnMLPArtifact
Import: `mlblack.core.artifacts:SklearnMLPArtifact`
Role: core
Summary: SklearnMLPArtifact(name: 'str', model: 'Any', family: 'str' = '', head: 'str' = 'point', representation: 'Mapping[str, Any]' = <factory>, metadata: 'Mapping[str, Any]' = <factory>, artifact_type: 'str' = 'sklearn_mlp')
Tags: core, artifacts
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.core.symbolic_interval_artifact`
Kind: core
Title: SymbolicIntervalArtifact
Import: `mlblack.core.artifacts:SymbolicIntervalArtifact`
Role: core
Summary: SymbolicIntervalArtifact(name: 'str', model: 'Any', family: 'str' = '', head: 'str' = 'point', representation: 'Mapping[str, Any]' = <factory>, metadata: 'Mapping[str, Any]' = <factory>, artifact_type: 'str' = 'symbolic_interval')
Tags: core, artifacts
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.core.symbolic_model_artifact`
Kind: core
Title: SymbolicModelArtifact
Import: `mlblack.core.artifacts:SymbolicModelArtifact`
Role: core
Summary: SymbolicModelArtifact(name: 'str', model: 'Any', family: 'str' = '', head: 'str' = 'point', representation: 'Mapping[str, Any]' = <factory>, metadata: 'Mapping[str, Any]' = <factory>, artifact_type: 'str' = 'symbolic_model')
Tags: core, artifacts
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.core.torch_model_artifact`
Kind: core
Title: TorchModelArtifact
Import: `mlblack.core.artifacts:TorchModelArtifact`
Role: core
Summary: TorchModelArtifact(name: 'str', model: 'Any', family: 'str' = '', head: 'str' = 'point', representation: 'Mapping[str, Any]' = <factory>, metadata: 'Mapping[str, Any]' = <factory>, artifact_type: 'str' = 'torch_model')
Tags: core, artifacts
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.core.trainer_state_artifact`
Kind: core
Title: TrainerStateArtifact
Import: `mlblack.core.artifacts:TrainerStateArtifact`
Role: core
Summary: Checkpoint-style trainer state payload.
Tags: core, artifacts
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.core.tree_ensemble_artifact`
Kind: core
Title: TreeEnsembleArtifact
Import: `mlblack.core.artifacts:TreeEnsembleArtifact`
Role: core
Summary: TreeEnsembleArtifact(name: 'str', model: 'Any', family: 'str' = '', head: 'str' = 'point', representation: 'Mapping[str, Any]' = <factory>, metadata: 'Mapping[str, Any]' = <factory>, artifact_type: 'str' = 'tree_ensemble')
Tags: core, artifacts
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.core.typed_model_artifact`
Kind: core
Title: TypedModelArtifact
Import: `mlblack.core.artifacts:TypedModelArtifact`
Role: core
Summary: TypedModelArtifact(name: 'str', model: 'Any', family: 'str' = '', head: 'str' = 'point', representation: 'Mapping[str, Any]' = <factory>, metadata: 'Mapping[str, Any]' = <factory>, artifact_type: 'str' = 'model')
Tags: core, artifacts
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.core.xg_boost_artifact`
Kind: core
Title: XGBoostArtifact
Import: `mlblack.core.artifacts:XGBoostArtifact`
Role: core
Summary: XGBoostArtifact(name: 'str', model: 'Any', family: 'str' = '', head: 'str' = 'point', representation: 'Mapping[str, Any]' = <factory>, metadata: 'Mapping[str, Any]' = <factory>, artifact_type: 'str' = 'xgboost')
Tags: core, artifacts
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.dashboard.artifact_html`
Kind: dashboard
Title: artifact dashboard export
Import: `mlblack.catalog.artifacts:export_artifact_html`
Role: dashboard
Summary: Exports a static HTML viewer for typed mlblack artifacts.
Tags: artifact, symbolic, html, report
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.dashboard.backend_matrix_html`
Kind: dashboard
Title: backend capability matrix export
Import: `mlblack.catalog.backend_dashboard:export_backend_matrix_html`
Role: dashboard
Summary: Exports a static HTML matrix of backend capability support.
Tags: backend, capability, matrix, html, report
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.dashboard.catalog_html`
Kind: dashboard
Title: catalog dashboard export
Import: `mlblack.catalog.dashboard:export_catalog_html`
Role: dashboard
Summary: Exports a lightweight HTML catalog report.
Tags: catalog, html, report
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.dashboard.catalog_streamlit`
Kind: dashboard
Title: catalog Streamlit dashboard
Import: `mlblack.catalog.dashboard:launch_catalog_dashboard`
Role: dashboard
Summary: Launches an interactive Streamlit catalog dashboard similar to the nsgablack catalog UI.
Tags: catalog, streamlit, web, dashboard, db-only
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.dashboard.catalog_web`
Kind: dashboard
Title: catalog query web app
Import: `mlblack.catalog.web_app:serve_catalog_web`
Role: dashboard
Summary: Serves a lightweight catalog query UI and JSON API without external web dependencies.
Tags: catalog, web, query, db-only
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.dashboard.experiment_html`
Kind: dashboard
Title: experiment dashboard export
Import: `mlblack.catalog.experiment.dashboard:export_experiment_html`
Role: dashboard
Summary: Exports a lightweight HTML experiment record report.
Tags: experiment, html, report
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.data_view.graph`
Kind: data_view
Title: GraphDataView
Import: `mlblack.pipeline.data_views.graph:GraphDataView`
Role: data_view
Summary: Dense graph tensors for small GNN smoke tasks.
Tags: data_view, pipeline, data_views, graph
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.data_view.image`
Kind: data_view
Title: ImageDataView
Import: `mlblack.pipeline.data_views.image:ImageDataView`
Role: data_view
Summary: Image tensors in NCHW layout.
Tags: data_view, pipeline, data_views, image
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.data_view.image_contrastive_pair`
Kind: data_view
Title: ImageContrastivePairDataView
Import: `mlblack.pipeline.data_views.contrastive:ImageContrastivePairDataView`
Role: data_view
Summary: Anchor/positive/negative image triples for retrieval smoke tasks.
Tags: data_view, pipeline, data_views, contrastive
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.data_view.numeric`
Kind: data_view
Title: NumericDataView
Import: `mlblack.pipeline.data_views.numeric:NumericDataView`
Role: data_view
Summary: Prepared numeric supervised data consumed by LearningProblem implementations.
Tags: data_view, pipeline, data_views, numeric
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.data_view.preference_pair`
Kind: data_view
Title: PreferencePairDataView
Import: `mlblack.pipeline.data_views.sequence:PreferencePairDataView`
Role: data_view
Summary: Token-id pairs for preference/DPO-style training.
Tags: data_view, pipeline, data_views, sequence
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.data_view.time_series`
Kind: data_view
Title: TimeSeriesDataView
Import: `mlblack.pipeline.data_views.time_series:TimeSeriesDataView`
Role: data_view
Summary: Ordered univariate time-series data with optional exogenous features.
Tags: data_view, pipeline, data_views, time_series
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.experiment.query`
Kind: experiment
Title: experiment query
Import: `mlblack.catalog.experiment.query:query_experiments`
Role: experiment
Summary: Query SQLite experiment records with simple filters and facets.
Tags: experiment, sqlite, facet
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.head.binary_logistic`
Kind: head
Title: BinaryLogisticHead
Import: `mlblack.representations.heads.probability:BinaryLogisticHead`
Role: head
Summary: Wraps a scalar logit decoder as binary predict_proba output.
Tags: classification, probability, logistic
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.head.center_radius_interval`
Kind: head
Title: CenterRadiusIntervalHead
Import: `mlblack.representations.heads.interval:CenterRadiusIntervalHead`
Role: head
Summary: Interval head: center base model + positive radius base model.
Tags: head, representations, heads, interval
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.head.interval`
Kind: head
Title: IntervalHead
Import: `mlblack.representations.heads.interval:IntervalHead`
Role: head
Summary: Interval head: lower base model + upper base model.
Tags: head, representations, heads, interval
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.head.negative_binomial`
Kind: head
Title: NegativeBinomialHead
Import: `mlblack.representations.heads.distribution:NegativeBinomialHead`
Role: head
Summary: NegativeBinomialHead(alpha_transform: 'str' = 'softplus')
Tags: head, representations, heads, distribution
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.head.normal`
Kind: head
Title: NormalHead
Import: `mlblack.representations.heads.distribution:NormalHead`
Role: head
Summary: NormalHead(sigma_transform: 'str' = 'softplus')
Tags: head, representations, heads, distribution
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.head.piecewise`
Kind: head
Title: PiecewiseHead
Import: `mlblack.representations.heads.conditional:PiecewiseHead`
Role: head
Summary: Allocates one base decoder block per branch and returns a PiecewiseModel.
Tags: conditional, piecewise, branch
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.head.point`
Kind: head
Title: PointHead
Import: `mlblack.representations.heads.point:PointHead`
Role: head
Summary: Point-output head: one base model, direct predict output.
Tags: head, representations, heads, point
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.head.poisson`
Kind: head
Title: PoissonHead
Import: `mlblack.representations.heads.distribution:PoissonHead`
Role: head
Summary: PoissonHead(rate_transform: 'str' = 'softplus')
Tags: head, representations, heads, distribution
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.head.probability_calibration`
Kind: head
Title: ProbabilityCalibrationHead
Import: `mlblack.representations.heads.probability:ProbabilityCalibrationHead`
Role: head
Summary: Base probability/logit model plus one temperature parameter.
Tags: head, representations, heads, probability
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.head.softmax`
Kind: head
Title: SoftmaxHead
Import: `mlblack.representations.heads.probability:SoftmaxHead`
Role: head
Summary: Allocates one base decoder block per class and returns softmax probabilities.
Tags: classification, probability, multiclass
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.head.symbolic_basis_set`
Kind: head
Title: SymbolicBasisSetHead
Import: `mlblack.representations.heads.symbolic:SymbolicBasisSetHead`
Role: head
Summary: Multi-symbol head that splits one state into expression blocks.
Tags: head, representations, heads, symbolic
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.head.two_model_interval`
Kind: head
Title: TwoModelIntervalHead
Import: `mlblack.representations.heads.interval:TwoModelIntervalHead`
Role: head
Summary: Interval head: lower base model + upper base model.
Tags: head, representations, heads, interval
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.integration.hf_sft`
Kind: integration
Title: build_hf_sft_solver
Import: `mlblack.integrations.hf_sft:build_hf_sft_solver`
Role: integration
Summary: 真实 HF + PEFT 会话 SFT：复用 LearningSolver、EvaluationGateway 与 Case Artifact，完整 fit 是一次评估，非逐 optimizer step 回滚。
Tags: integration, sft, peft, lora, causal-lm, provider
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.integration.nsgablack_gradient`
Kind: integration
Title: build_gradient_trainer
Import: `mlblack.integrations.nsgablack_gradient:build_gradient_trainer`
Role: integration
Summary: 稳定 method ID 装配：nsgablack GradientOptimizerAdapter + mlblack Problem/Provider + BlackBase L0/StateRef runtime。
Tags: integration, nsgablack, gradient, provider, trainer
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.integration.nsgablack_optimization`
Kind: integration
Title: build_optimization_adapter
Import: `mlblack.integrations.nsgablack_optimization:build_optimization_adapter`
Role: integration
Summary: 把 ML 用户词汇解析为稳定优化方法标识，并装配 nsgablack 的 provider-neutral Adapter。
Tags: integration, nsgablack, optimization, stable-method, adapter
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.integration.learning_solver`
Kind: integration
Title: LearningSolver
Import: `mlblack.integrations.nsgablack_control:LearningSolver`
Role: integration
Summary: ML 语义 facade：复用共享 Pool、Unit、编排和唯一 Solver 生命周期；v7 状态保存池值闭包，正式 checkpoint 保存 ML 最佳反馈绑定。
Tags: integration, nsgablack, control-plane, trainer-facade
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.integration.ml_learning_problem_bridge`
Kind: integration
Title: MLLearningProblemBridge
Import: `mlblack.integrations.nsgablack_control:MLLearningProblemBridge`
Role: integration
Summary: 把 MLBlack LearningProblem 的模型/状态/Feedback 语义投影为 NSGABlack BlackBoxProblem。
Tags: integration, nsgablack, problem, feedback
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.integration.ml_representation_bridge`
Kind: integration
Title: MLRepresentationBridge
Import: `mlblack.integrations.nsgablack_control:MLRepresentationBridge`
Role: integration
Summary: 在仓库边界转换 UnknownState 与 ndarray；模型布局、初始化、修复和解码仍由 ML Codec 独占。
Tags: integration, nsgablack, representation, codec
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.integration.nsgablack_learning_case_evaluator`
Kind: integration
Title: NsgablackLearningCaseEvaluator
Import: `mlblack.integrations.nsgablack_learning_case:NsgablackLearningCaseEvaluator`
Role: integration
Summary: Invoke a complete ML semantic child Case through the shared CaseRuntime.
Tags: integration, nsgablack, learning_case, case_runtime
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.integration.pretrained_checkpoint_mapper`
Kind: integration
Title: PretrainedCheckpointMapper
Import: `mlblack.integrations.transformers_bridge:PretrainedCheckpointMapper`
Role: integration
Summary: Map an external checkpoint state_dict into an mlblack neural graph.
Tags: integration, integrations, transformers_bridge
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.integration.pretrained_model_bridge`
Kind: integration
Title: PretrainedModelBridge
Import: `mlblack.integrations.transformers_bridge:PretrainedModelBridge`
Role: integration
Summary: Lazy pretrained-model loader for external-model/component use cases.
Tags: integration, integrations, transformers_bridge
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.integration.pretrained_tokenizer_bridge`
Kind: integration
Title: PretrainedTokenizerBridge
Import: `mlblack.integrations.transformers_bridge:PretrainedTokenizerBridge`
Role: integration
Summary: Lazy bridge to HuggingFace tokenizers.
Tags: integration, integrations, transformers_bridge
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.arimasarimax`
Kind: model
Title: ARIMASARIMAXSpec
Import: `mlblack.models.time_series:ARIMASARIMAXSpec`
Role: model
Summary: Declarative ARIMA/SARIMAX order and fitting options.
Tags: model, models, time_series
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.arimasarimax_forecast`
Kind: model
Title: ARIMASARIMAXForecastModel
Import: `mlblack.models.time_series:ARIMASARIMAXForecastModel`
Role: model
Summary: Fitted ARIMA/SARIMAX-style forecaster with a numpy ARX fallback route.
Tags: model, models, time_series
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.binary_logistic_probability`
Kind: model
Title: BinaryLogisticProbabilityModel
Import: `mlblack.models.probability:BinaryLogisticProbabilityModel`
Role: model
Summary: Probability wrapper around a scalar logit model.
Tags: model, models, probability
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.center_radius_interval`
Kind: model
Title: CenterRadiusIntervalModel
Import: `mlblack.models.outputs:CenterRadiusIntervalModel`
Role: model
Summary: Interval predictor built from center and radius models.
Tags: model, models, outputs
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.estimator_spec`
Kind: model
Title: EstimatorSpecModel
Import: `mlblack.models.estimators:EstimatorSpecModel`
Role: model
Summary: Decoded external estimator specification.
Tags: model, models, estimators
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.fitted_estimator`
Kind: model
Title: FittedEstimatorModel
Import: `mlblack.models.estimators:FittedEstimatorModel`
Role: model
Summary: Prediction wrapper around an already fitted external estimator.
Tags: model, models, estimators
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.integrated_prediction`
Kind: model
Title: IntegratedPredictionModel
Import: `mlblack.models.composition:IntegratedPredictionModel`
Role: model
Summary: Combines named fitted model predictions without owning training orchestration.
Tags: composition, integration, residual, stacking
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.interval_prediction`
Kind: model
Title: IntervalPredictionModel
Import: `mlblack.models.outputs:IntervalPredictionModel`
Role: model
Summary: Two-bound interval predictor built from lower and upper models.
Tags: model, models, outputs
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.lag_estimator_forecast`
Kind: model
Title: LagEstimatorForecastModel
Import: `mlblack.models.time_series:LagEstimatorForecastModel`
Role: model
Summary: Forecast wrapper around an already-fitted lag-feature estimator.
Tags: model, models, time_series
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.linear_autoregressive_fit_spec`
Kind: model
Title: LinearAutoregressiveFitSpec
Import: `mlblack.models.time_series:LinearAutoregressiveFitSpec`
Role: model
Summary: Declarative AR/ARX closed-form fitting request materialized by the time-series Problem.
Tags: model, models, time_series, fit-spec, closed-form
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.linear_autoregressive_forecast`
Kind: model
Title: LinearAutoregressiveForecastModel
Import: `mlblack.models.time_series:LinearAutoregressiveForecastModel`
Role: model
Summary: Linear AR/ARX-style forecaster fitted on lagged windows.
Tags: model, models, time_series
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.linear_point`
Kind: model
Title: LinearPointModel
Import: `mlblack.models.linear:LinearPointModel`
Role: model
Summary: Decoded point model: f(x) = intercept + X @ weights.
Tags: model, models, linear
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.naive_forecast`
Kind: model
Title: NaiveForecastModel
Import: `mlblack.models.time_series:NaiveForecastModel`
Role: model
Summary: Naive, seasonal-naive, or moving-average univariate forecaster.
Tags: model, models, time_series
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.negative_binomial_distribution`
Kind: model
Title: NegativeBinomialDistributionModel
Import: `mlblack.models.distributions:NegativeBinomialDistributionModel`
Role: model
Summary: NegativeBinomialDistributionModel(mu_model: 'Any', alpha_model: 'Any', alpha_transform: 'str' = 'softplus', metadata: 'Mapping[str, Any]' = <factory>)
Tags: model, models, distributions
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.normal_distribution`
Kind: model
Title: NormalDistributionModel
Import: `mlblack.models.distributions:NormalDistributionModel`
Role: model
Summary: NormalDistributionModel(mu_model: 'Any', sigma_model: 'Any', sigma_transform: 'str' = 'softplus', metadata: 'Mapping[str, Any]' = <factory>)
Tags: model, models, distributions
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.numpy_mlp_point`
Kind: model
Title: NumpyMLPPointModel
Import: `mlblack.models.neural:NumpyMLPPointModel`
Role: model
Summary: Small decoded MLP point model backed by numpy arrays.
Tags: model, models, neural
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.orthogonal_feature_map`
Kind: model
Title: OrthogonalFeatureMap
Import: `mlblack.models.linear:OrthogonalFeatureMap`
Role: model
Summary: Data-side feature map used by decoded point models.
Tags: model, models, linear
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.orthogonal_linear_point`
Kind: model
Title: OrthogonalLinearPointModel
Import: `mlblack.models.linear:OrthogonalLinearPointModel`
Role: model
Summary: Decoded point model: f(x) = intercept + Q(x) @ weights.
Tags: model, models, linear
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.piecewise`
Kind: model
Title: PiecewiseModel
Import: `mlblack.models.conditional:PiecewiseModel`
Role: model
Summary: PiecewiseModel(router: 'Router', branch_models: 'Sequence[Any]', default_branch: 'int' = 0, metadata: 'Mapping[str, Any]' = <factory>)
Tags: model, models, conditional
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.poisson_distribution`
Kind: model
Title: PoissonDistributionModel
Import: `mlblack.models.distributions:PoissonDistributionModel`
Role: model
Summary: PoissonDistributionModel(rate_model: 'Any', rate_transform: 'str' = 'softplus', metadata: 'Mapping[str, Any]' = <factory>)
Tags: model, models, distributions
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.prediction_input`
Kind: model
Title: PredictionInputSpec
Import: `mlblack.models.composition:PredictionInputSpec`
Role: model
Summary: Input requirement for one component model inside an integrated model.
Tags: model, models, composition
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.prediction_integration`
Kind: model
Title: PredictionIntegrationSpec
Import: `mlblack.models.composition:PredictionIntegrationSpec`
Role: model
Summary: How named model predictions are combined into one prediction.
Tags: model, models, composition
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.prediction_integration_component`
Kind: model
Title: PredictionIntegrationComponent
Import: `mlblack.models.composition:PredictionIntegrationComponent`
Role: model
Summary: Builds IntegratedPredictionModel from named fitted component models.
Tags: composition, integration, residual, stacking, component
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.prediction_io`
Kind: model
Title: PredictionIOContract
Import: `mlblack.models.composition:PredictionIOContract`
Role: model
Summary: I/O contract for routing inputs and validating component predictions.
Tags: model, models, composition
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.prediction_output`
Kind: model
Title: PredictionOutputSpec
Import: `mlblack.models.composition:PredictionOutputSpec`
Role: model
Summary: Output requirement consumed by the integration strategy.
Tags: model, models, composition
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.probability_calibration`
Kind: model
Title: ProbabilityCalibrationModel
Import: `mlblack.models.conditional:ProbabilityCalibrationModel`
Role: model
Summary: Simple probability calibration wrapper.
Tags: model, models, conditional
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.router`
Kind: model
Title: Router
Import: `mlblack.models.conditional:Router`
Role: model
Summary: Auto-discovered mlblack component `model.router`.
Tags: model, models, conditional
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.softmax_probability`
Kind: model
Title: SoftmaxProbabilityModel
Import: `mlblack.models.probability:SoftmaxProbabilityModel`
Role: model
Summary: Probability wrapper around one scalar logit model per class.
Tags: model, models, probability
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.statsmodels_sarimax_forecast`
Kind: model
Title: StatsmodelsSARIMAXForecastModel
Import: `mlblack.models.time_series:StatsmodelsSARIMAXForecastModel`
Role: model
Summary: Forecast wrapper around a fitted statsmodels SARIMAXResults object.
Tags: model, models, time_series
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.symbolic_basis_set`
Kind: model
Title: SymbolicBasisSetModel
Import: `mlblack.models.symbolic:SymbolicBasisSetModel`
Role: model
Summary: Decoded multi-expression output used by orthogonal basis search.
Tags: model, models, symbolic
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.symbolic_expression`
Kind: model
Title: SymbolicExpressionModel
Import: `mlblack.models.symbolic:SymbolicExpressionModel`
Role: model
Summary: Decoded symbolic point model with fitted parameter values.
Tags: model, models, symbolic
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.temperature_calibrated_probability`
Kind: model
Title: TemperatureCalibratedProbabilityModel
Import: `mlblack.models.probability:TemperatureCalibratedProbabilityModel`
Role: model
Summary: Temperature calibration wrapper for probability-capable models.
Tags: model, models, probability
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.model.threshold_router`
Kind: model
Title: ThresholdRouter
Import: `mlblack.models.conditional:ThresholdRouter`
Role: model
Summary: Route rows by threshold bins on one feature column.
Tags: model, models, conditional
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.nsgablack_neural.transformer_spec_search`
Kind: nsgablack_neural
Title: TransformerSpecSearchProblem
Import: `mlblack.integrations.nsgablack_neural.transformer_spec_search:TransformerSpecSearchProblem`
Role: nsgablack_neural
Summary: nsgablack-facing problem for outer TransformerSpec search.
Tags: nsgablack_neural, integrations, transformer_spec_search
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.nsgablack_neural.transformer_spec_search_space`
Kind: nsgablack_neural
Title: TransformerSpecSearchSpace
Import: `mlblack.integrations.nsgablack_neural.transformer_spec_search:TransformerSpecSearchSpace`
Role: nsgablack_neural
Summary: Auto-discovered mlblack component `nsgablack_neural.transformer_spec_search_space`.
Tags: nsgablack_neural, integrations, transformer_spec_search
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.nsgablack_symbolic.basis_conditioned_symbolic_task`
Kind: nsgablack_symbolic
Title: BasisConditionedSymbolicTaskProblem
Import: `mlblack.integrations.nsgablack_symbolic.task_symbolic_problem:BasisConditionedSymbolicTaskProblem`
Role: nsgablack_symbolic
Summary: nsgablack-compatible Stage 2 problem.
Tags: nsgablack_symbolic, integrations, task_symbolic_problem
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.nsgablack_symbolic.expression_graph_cache`
Kind: nsgablack_symbolic
Title: ExpressionGraphCache
Import: `mlblack.integrations.nsgablack_symbolic.graph_cache:ExpressionGraphCache`
Role: nsgablack_symbolic
Summary: Reusable cache for symbolic expression values and derivative expressions.
Tags: nsgablack_symbolic, integrations, graph_cache
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.nsgablack_symbolic.function_pool_index_search_space`
Kind: nsgablack_symbolic
Title: FunctionPoolIndexSearchSpace
Import: `mlblack.integrations.nsgablack_symbolic.search_space:FunctionPoolIndexSearchSpace`
Role: nsgablack_symbolic
Summary: Index-coded outer search space over a symbolic FunctionPool.
Tags: nsgablack_symbolic, integrations, search_space
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.nsgablack_symbolic.orthogonal_basis_outer`
Kind: nsgablack_symbolic
Title: OrthogonalBasisOuterProblem
Import: `mlblack.integrations.nsgablack_symbolic.orthogonal_problem:OrthogonalBasisOuterProblem`
Role: nsgablack_symbolic
Summary: nsgablack-compatible Stage 1 problem for symbolic basis search.
Tags: nsgablack_symbolic, integrations, orthogonal_problem
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.nsgablack_symbolic.orthogonal_basis_set_artifact`
Kind: nsgablack_symbolic
Title: OrthogonalBasisSetArtifact
Import: `mlblack.integrations.nsgablack_symbolic.artifacts:OrthogonalBasisSetArtifact`
Role: nsgablack_symbolic
Summary: Stage 1 output boundary consumed by Stage 2.
Tags: nsgablack_symbolic, integrations, artifacts
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.nsgablack_symbolic.symbolic_basis_consensus_analyzer`
Kind: nsgablack_symbolic
Title: SymbolicBasisConsensusAnalyzer
Import: `mlblack.integrations.nsgablack_symbolic.basis_consensus:SymbolicBasisConsensusAnalyzer`
Role: nsgablack_symbolic
Summary: Artifact/report capability for basis consensus and overlap.
Tags: nsgablack_symbolic, integrations, basis_consensus
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.nsgablack_symbolic.symbolic_branch_evaluator`
Kind: nsgablack_symbolic
Title: SymbolicBranchEvaluator
Import: `mlblack.integrations.nsgablack_symbolic.evaluation:SymbolicBranchEvaluator`
Role: nsgablack_symbolic
Summary: Branch/regime audit evaluator for fitted symbolic task artifacts.
Tags: nsgablack_symbolic, integrations, evaluation
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.nsgablack_symbolic.symbolic_candidate_scorer`
Kind: nsgablack_symbolic
Title: SymbolicCandidateScorer
Import: `mlblack.integrations.nsgablack_symbolic.search_policy:SymbolicCandidateScorer`
Role: nsgablack_symbolic
Summary: Candidate scoring policy for nsgablack symbolic outer search.
Tags: nsgablack_symbolic, integrations, search_policy
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.nsgablack_symbolic.symbolic_expression_audit_producer`
Kind: nsgablack_symbolic
Title: SymbolicExpressionAuditProducer
Import: `mlblack.integrations.nsgablack_symbolic.expression_audit:SymbolicExpressionAuditProducer`
Role: nsgablack_symbolic
Summary: Produces symbolic artifact audit sections from expressions and term metadata.
Tags: nsgablack_symbolic, integrations, expression_audit
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.nsgablack_symbolic.symbolic_fold_evaluator`
Kind: nsgablack_symbolic
Title: SymbolicFoldEvaluator
Import: `mlblack.integrations.nsgablack_symbolic.evaluation:SymbolicFoldEvaluator`
Role: nsgablack_symbolic
Summary: Lightweight fold evaluator for symbolic artifacts.
Tags: nsgablack_symbolic, integrations, evaluation
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.nsgablack_symbolic.symbolic_orthogonal_nested_suite`
Kind: nsgablack_symbolic
Title: SymbolicOrthogonalNestedSuite
Import: `mlblack.integrations.nsgablack_symbolic.builders:SymbolicOrthogonalNestedSuite`
Role: nsgablack_symbolic
Summary: Serial Stage 1 -> Stage 2 symbolic plan surface.
Tags: nsgablack_symbolic, integrations, builders
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.nsgablack_symbolic.symbolic_overfit_guard`
Kind: nsgablack_symbolic
Title: SymbolicOverfitGuard
Import: `mlblack.integrations.nsgablack_symbolic.overfit_guard:SymbolicOverfitGuard`
Role: nsgablack_symbolic
Summary: Scores train/validation drift for symbolic structure search.
Tags: nsgablack_symbolic, integrations, overfit_guard
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.nsgablack_symbolic.symbolic_path_memory`
Kind: nsgablack_symbolic
Title: SymbolicPathMemory
Import: `mlblack.integrations.nsgablack_symbolic.path_memory:SymbolicPathMemory`
Role: nsgablack_symbolic
Summary: Persistent memory for symbolic structure search paths.
Tags: nsgablack_symbolic, integrations, path_memory
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.nsgablack_symbolic.symbolic_replay_record_builder`
Kind: nsgablack_symbolic
Title: SymbolicReplayRecordBuilder
Import: `mlblack.integrations.nsgablack_symbolic.replay:SymbolicReplayRecordBuilder`
Role: nsgablack_symbolic
Summary: Builds JSON-compatible replay records for nested symbolic candidates.
Tags: nsgablack_symbolic, integrations, replay
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.nsgablack_symbolic.symbolic_structure_guard`
Kind: nsgablack_symbolic
Title: SymbolicStructureGuard
Import: `mlblack.integrations.nsgablack_symbolic.structure_guard:SymbolicStructureGuard`
Role: nsgablack_symbolic
Summary: Outer-search structural guard for symbolic candidates.
Tags: nsgablack_symbolic, integrations, structure_guard
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.nsgablack_symbolic.symbolic_task_artifact`
Kind: nsgablack_symbolic
Title: SymbolicTaskArtifact
Import: `mlblack.integrations.nsgablack_symbolic.artifacts:SymbolicTaskArtifact`
Role: nsgablack_symbolic
Summary: Stage 2 task-expression artifact.
Tags: nsgablack_symbolic, integrations, artifacts
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.numericizer.default`
Kind: numericizer
Title: DefaultNumericizer
Import: `mlblack.pipeline.numericizer.default:DefaultNumericizer`
Role: numericizer
Summary: Converts schema-backed raw rows into NumericDataView.
Tags: data, schema, feature-space
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.numericizer.default_numericizer`
Kind: numericizer
Title: DefaultNumericizer
Import: `mlblack.pipeline.numericizer.default:DefaultNumericizer`
Role: numericizer
Summary: DefaultNumericizer(plan: 'NumericizationPlan')
Tags: numericizer, pipeline, default
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.numericizer.target`
Kind: numericizer
Title: TargetCodec
Import: `mlblack.pipeline.numericizer.target_codec:TargetCodec`
Role: numericizer
Summary: TargetCodec(kind: 'str' = 'numeric', classes: 'Sequence[Any]' = (), metadata: 'Mapping[str, Any]' = <factory>)
Tags: numericizer, pipeline, target_codec
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.numericizer.vocabulary_tokenizer`
Kind: numericizer
Title: VocabularyTokenizer
Import: `mlblack.pipeline.numericizer.text:VocabularyTokenizer`
Role: numericizer
Summary: Small local tokenizer/numericizer for transformer smoke tasks.
Tags: numericizer, pipeline, text
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.pipeline.conditional_primitive_feature`
Kind: pipeline
Title: ConditionalPrimitiveFeatureComponent
Import: `mlblack.pipeline.feature_space:ConditionalPrimitiveFeatureComponent`
Role: pipeline
Summary: Append deterministic conditional primitive features to NumericDataView.
Tags: pipeline, feature_space
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.pipeline.data_pipeline`
Kind: pipeline
Title: DataPipelineComponent
Import: `mlblack.pipeline.base:DataPipelineComponent`
Role: pipeline
Summary: Data pipeline component.
Tags: pipeline, base
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.pipeline.numeric_batch_schedule`
Kind: pipeline
Title: NumericBatchSchedule
Import: `mlblack.pipeline.datasets:NumericBatchSchedule`
Role: pipeline
Summary: 可恢复的数值 batch/epoch 调度器；拥有 shuffle、cursor 和 epoch 状态，不拥有优化算法。
Tags: pipeline, batch, epoch, shuffle, checkpoint
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.pipeline.data_pipeline_chain`
Kind: pipeline
Title: DataPipeline
Import: `mlblack.pipeline.base:DataPipeline`
Role: pipeline
Summary: Ordered data preparation chain for a trainer assembly.
Tags: pipeline, data, chain, fit-transform
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.pipeline.feature_space`
Kind: pipeline
Title: FeatureSpaceComponent
Import: `mlblack.pipeline.feature_space:FeatureSpaceComponent`
Role: pipeline
Summary: Records feature-space metadata in the data pipeline.
Tags: pipeline, feature-space, metadata
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.pipeline.hive_query_source`
Kind: pipeline
Title: HiveQuerySource
Import: `mlblack.pipeline.sources:HiveQuerySource`
Role: pipeline
Summary: Run a SQL query against HiveServer2 and materialise the result set.
Tags: pipeline, sources
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.pipeline.identity`
Kind: pipeline
Title: IdentityComponent
Import: `mlblack.pipeline.components:IdentityComponent`
Role: pipeline
Summary: Data pipeline component.
Tags: pipeline, components
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.pipeline.jdbc_query_source`
Kind: pipeline
Title: JDBCQuerySource
Import: `mlblack.pipeline.sources:JDBCQuerySource`
Role: pipeline
Summary: Run a SQL query against any JDBC data source and materialise the result.
Tags: pipeline, sources
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.pipeline.model_conditioned_target`
Kind: pipeline
Title: ModelConditionedTargetComponent
Import: `mlblack.pipeline.model_conditioning:ModelConditionedTargetComponent`
Role: pipeline
Summary: Builds next-stage targets by calling an existing model, e.g. y - model.predict(X).
Tags: pipeline, residual, model-conditioned, stage-surface
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.pipeline.model_conditioned_target_builder`
Kind: pipeline
Title: ModelConditionedTargetBuilder
Import: `mlblack.pipeline.model_conditioning:ModelConditionedTargetBuilder`
Role: pipeline
Summary: Transforms data by calling an already-trained reference model.
Tags: pipeline, model_conditioning
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.pipeline.model_conditioned_target_config`
Kind: pipeline
Title: ModelConditionedTargetConfig
Import: `mlblack.pipeline.model_conditioning:ModelConditionedTargetConfig`
Role: pipeline
Summary: Configuration for building a next-stage target from a reference model.
Tags: pipeline, residual, model-conditioned, config
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.pipeline.numeric_batch_loader`
Kind: pipeline
Title: NumericBatchLoader
Import: `mlblack.pipeline.datasets:NumericBatchLoader`
Role: pipeline
Summary: Batch iterator over a NumericDataView.
Tags: pipeline, datasets
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.pipeline.row_dataset_stream`
Kind: pipeline
Title: RowDatasetStream
Import: `mlblack.pipeline.datasets:RowDatasetStream`
Role: pipeline
Summary: Lightweight row streaming surface for local or external datasets.
Tags: pipeline, datasets
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.pipeline.s3_parquet_source`
Kind: pipeline
Title: S3ParquetSource
Import: `mlblack.pipeline.sources:S3ParquetSource`
Role: pipeline
Summary: Read a Parquet dataset from S3 or an S3-compatible store (MinIO, etc.).
Tags: pipeline, sources
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.pipeline.seasonal_decomposition`
Kind: pipeline
Title: SeasonalDecompositionConfig
Import: `mlblack.pipeline.time_series:SeasonalDecompositionConfig`
Role: pipeline
Summary: STL-like additive seasonal decomposition configuration.
Tags: pipeline, time_series
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.pipeline.seasonal_decomposition_result`
Kind: pipeline
Title: SeasonalDecompositionResult
Import: `mlblack.pipeline.time_series:SeasonalDecompositionResult`
Role: pipeline
Summary: Trend, seasonal and residual arrays aligned to the original series.
Tags: pipeline, time_series
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.pipeline.select_columns`
Kind: pipeline
Title: SelectColumnsComponent
Import: `mlblack.pipeline.components:SelectColumnsComponent`
Role: pipeline
Summary: SelectColumnsComponent(columns: 'Sequence[int]' = ())
Tags: pipeline, components
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.pipeline.source.hive_query`
Kind: pipeline
Title: HiveQuerySource
Import: `mlblack.pipeline.sources:HiveQuerySource`
Role: pipeline
Summary: Execute SQL against HiveServer2 and materialise results into a NumericDataView.
Tags: pipeline, source, hive, sql, cloud
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.pipeline.source.jdbc_query`
Kind: pipeline
Title: JDBCQuerySource
Import: `mlblack.pipeline.sources:JDBCQuerySource`
Role: pipeline
Summary: Generic JDBC query source — Postgres, MySQL, Oracle, etc. — into NumericDataView.
Tags: pipeline, source, jdbc, sql, relational
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.pipeline.source.s3_parquet`
Kind: pipeline
Title: S3ParquetSource
Import: `mlblack.pipeline.sources:S3ParquetSource`
Role: pipeline
Summary: Read Parquet datasets from S3 or S3-compatible stores (MinIO) into a NumericDataView.
Tags: pipeline, source, s3, parquet, cloud
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.pipeline.stl_seasonal_decomposition`
Kind: pipeline
Title: STLSeasonalDecompositionComponent
Import: `mlblack.pipeline.time_series:STLSeasonalDecompositionComponent`
Role: pipeline
Summary: STL-like deterministic seasonal decomposition for TimeSeriesDataView.
Tags: pipeline, time_series
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.pipeline.time_series_window`
Kind: pipeline
Title: TimeSeriesWindowConfig
Import: `mlblack.pipeline.time_series:TimeSeriesWindowConfig`
Role: pipeline
Summary: Lag-window configuration for converting a series into supervised rows.
Tags: pipeline, time_series
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.pipeline.time_series_windowing`
Kind: pipeline
Title: TimeSeriesWindowingComponent
Import: `mlblack.pipeline.time_series:TimeSeriesWindowingComponent`
Role: pipeline
Summary: Convert TimeSeriesDataView into a lagged NumericDataView.
Tags: pipeline, time_series
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.pipeline.tokenized_text_dataset_builder`
Kind: pipeline
Title: TokenizedTextDatasetBuilder
Import: `mlblack.pipeline.datasets:TokenizedTextDatasetBuilder`
Role: pipeline
Summary: Build token-id NumericDataView objects from text datasets.
Tags: pipeline, datasets
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.pipeline.z_score_normalize`
Kind: pipeline
Title: ZScoreNormalizeComponent
Import: `mlblack.pipeline.components:ZScoreNormalizeComponent`
Role: pipeline
Summary: ZScoreNormalizeComponent(eps: 'float' = 1e-12, with_mean: 'bool' = True, with_std: 'bool' = True)
Tags: pipeline, components
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.preset.mlp_regression`
Kind: preset
Title: MLP regression preset
Import: `mlblack.presets.neural:build_mlp_regression_trainer`
Role: preset
Summary: ML 词汇入口：optimizer=sgd/adam/adamw 内部解析为 nsgablack 通用梯度 Adapter 与 mlblack Torch Evaluation Provider。
Tags: neural, mlp, gradient, torch-provider, nsgablack, preset
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.preset.arima_sarimax_forecast`
Kind: preset
Title: ARIMA/SARIMAX forecast preset
Import: `mlblack.presets.time_series:build_arima_sarimax_forecast_trainer`
Role: preset
Summary: ARIMA/SARIMAX 规格由 Codec 解码，并在 LearningSolver 生命周期内由 TimeSeries Problem/Provider 拟合。
Tags: time-series, arima, sarimax, preset
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.preset.baseline_forecast_search`
Kind: preset
Title: baseline forecast search preset
Import: `mlblack.presets.time_series:build_baseline_forecast_search_trainer`
Role: preset
Summary: 对 naive/季节性-naive/移动平均预测策略进行随机搜索。
Tags: time-series, baseline, naive, random-search, preset
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.preset.linear_autoregressive_forecast`
Kind: preset
Title: linear autoregressive forecast preset
Import: `mlblack.presets.time_series:build_linear_autoregressive_forecast_trainer`
Role: preset
Summary: 线性自回归拟合规格由 Codec 解码，闭式拟合在 LearningSolver 的 TimeSeries Problem 边界执行。
Tags: time-series, linear, autoregressive, preset
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.preset.orthogonal_logistic_classification`
Kind: preset
Title: orthogonal logistic classification preset
Import: `mlblack.presets.classification:build_orthogonal_logistic_classification_trainer`
Role: preset
Summary: Orthogonal linear logits with binary probability head and classification metrics.
Tags: classification, logistic, orthogonal
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.preset.tabular_tabnet_classification`
Kind: preset
Title: tabular TabNet classification preset
Import: `mlblack.presets.neural:build_tabular_tabnet_classification_trainer`
Role: preset
Summary: TabNet 表格分类预设：TabularNeuralClassificationProblem 定义交叉熵/指标，TorchEvaluationProvider 执行 autograd，nsgablack GradientOptimizerAdapter 执行稳定优化方法。
Tags: neural, tabular, tabnet, classification, preset
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.preset.tabular_tabnet_regression`
Kind: preset
Title: tabular TabNet regression preset
Import: `mlblack.presets.neural:build_tabular_tabnet_regression_trainer`
Role: preset
Summary: TabNet 表格回归预设：TabularNeuralRegressionProblem 定义 MSE/指标，TorchEvaluationProvider 执行 autograd，nsgablack GradientOptimizerAdapter 执行稳定优化方法。
Tags: neural, tabular, tabnet, regression, preset
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.preset.temporal_deepar_forecast`
Kind: preset
Title: temporal DeepAR forecast preset
Import: `mlblack.presets.neural:build_temporal_deepar_forecast_trainer`
Role: preset
Summary: DeepAR 风格概率预测预设：LSTM 主干输出高斯分布参数，经 ML Problem + TorchEvaluationProvider + nsgablack GradientOptimizerAdapter 训练。
Tags: neural, time-series, temporal, deepar, probabilistic, preset
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.preset.temporal_lstm_forecast`
Kind: preset
Title: temporal LSTM forecast preset
Import: `mlblack.presets.neural:build_temporal_lstm_forecast_trainer`
Role: preset
Summary: LSTM 神经序列预测预设，经 Temporal Problem + TorchEvaluationProvider + nsgablack GradientOptimizerAdapter 训练。
Tags: neural, time-series, temporal, lstm, preset
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.preset.temporal_nbeats_forecast`
Kind: preset
Title: temporal N-BEATS forecast preset
Import: `mlblack.presets.neural:build_temporal_nbeats_forecast_trainer`
Role: preset
Summary: N-BEATS 风格堆叠残差块预测预设，经 ML Problem + TorchEvaluationProvider + nsgablack GradientOptimizerAdapter 训练。
Tags: neural, time-series, temporal, nbeats, preset
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.preset.temporal_patchtst_forecast`
Kind: preset
Title: temporal PatchTST forecast preset
Import: `mlblack.presets.neural:build_temporal_patchtst_forecast_trainer`
Role: preset
Summary: PatchTST 补丁嵌入 + Transformer 编码器预测预设，经 ML Problem + TorchEvaluationProvider + nsgablack GradientOptimizerAdapter 训练。
Tags: neural, time-series, temporal, patchtst, transformer, preset
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.preset.temporal_tcn_forecast`
Kind: preset
Title: temporal TCN forecast preset
Import: `mlblack.presets.neural:build_temporal_tcn_forecast_trainer`
Role: preset
Summary: TCN 神经序列预测预设，经 Temporal Problem + TorchEvaluationProvider + nsgablack GradientOptimizerAdapter 训练。
Tags: neural, time-series, temporal, tcn, preset
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.preset.temporal_tft_forecast`
Kind: preset
Title: temporal TFT forecast preset
Import: `mlblack.presets.neural:build_temporal_tft_forecast_trainer`
Role: preset
Summary: Temporal Fusion Transformer 预测预设，含门控残差网络和可解释多头自注意力，经统一 Problem/Provider/GradientOptimizer 路径训练。
Tags: neural, time-series, temporal, tft, attention, preset
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.preset.temporal_transformer_forecast`
Kind: preset
Title: temporal Transformer forecast preset
Import: `mlblack.presets.neural:build_temporal_transformer_forecast_trainer`
Role: preset
Summary: Transformer 神经序列预测预设，经 Temporal Problem + TorchEvaluationProvider + nsgablack GradientOptimizerAdapter 训练。
Tags: neural, time-series, temporal, transformer, preset
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.problem.fixed_symbolic_regression`
Kind: problem
Title: FixedSymbolicRegressionProblem
Import: `mlblack.problems.symbolic:FixedSymbolicRegressionProblem`
Role: problem
Summary: Regression evaluator for fixed symbolic expression decoders.
Tags: problem, problems, symbolic
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.problem.orthogonal_basis_evaluation`
Kind: problem
Title: OrthogonalBasisEvaluationProblem
Import: `mlblack.problems.symbolic:OrthogonalBasisEvaluationProblem`
Role: problem
Summary: Evaluate a fitted symbolic basis set for orthogonality objectives.
Tags: problem, problems, symbolic
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.problem.piecewise_regression`
Kind: problem
Title: PiecewiseRegressionProblem
Import: `mlblack.problems.conditional:PiecewiseRegressionProblem`
Role: problem
Summary: Regression evaluator with branch distribution metrics for piecewise models.
Tags: problem, problems, conditional
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.problem.rolling_origin_forecasting`
Kind: problem
Title: RollingOriginForecastingProblem
Import: `mlblack.problems.time_series:RollingOriginForecastingProblem`
Role: problem
Summary: Rolling-origin evaluator for horizon-specific forecast quality.
Tags: problem, problems, time_series
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.problem.supervised_classification`
Kind: problem
Title: SupervisedClassificationProblem
Import: `mlblack.problems.classification:SupervisedClassificationProblem`
Role: problem
Summary: Evaluator for classification accuracy and log-loss objectives.
Tags: classification, probability, log-loss
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.problem.tabular_neural_classification`
Kind: problem
Title: TabularNeuralClassificationProblem
Import: `mlblack.problems.neural:TabularNeuralClassificationProblem`
Role: problem
Summary: 表格 NeuralGraph 分类语义：定义交叉熵、验证目标和分类指标，由 EvaluationProvider 执行 backend loss/autograd。
Tags: problem, neural, tabular, classification, differentiable
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.problem.tabular_neural_regression`
Kind: problem
Title: TabularNeuralRegressionProblem
Import: `mlblack.problems.neural:TabularNeuralRegressionProblem`
Role: problem
Summary: 表格 NeuralGraph 回归语义：定义 MSE、验证目标和回归指标，由 EvaluationProvider 执行 backend loss/autograd。
Tags: problem, neural, tabular, regression, differentiable
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.problem.supervised_estimator_fit`
Kind: problem
Title: SupervisedEstimatorFitRegressionProblem
Import: `mlblack.problems.supervised:SupervisedEstimatorFitRegressionProblem`
Role: problem
Summary: Fits decoded estimator specs and scores the fitted estimator.
Tags: tree, xgboost, artifact
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.problem.supervised_estimator_fit_regression`
Kind: problem
Title: SupervisedEstimatorFitRegressionProblem
Import: `mlblack.problems.supervised:SupervisedEstimatorFitRegressionProblem`
Role: problem
Summary: Evaluator that fits decoded external estimator specs before scoring.
Tags: problem, problems, supervised
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.problem.supervised_interval_regression`
Kind: problem
Title: SupervisedIntervalRegressionProblem
Import: `mlblack.problems.supervised:SupervisedIntervalRegressionProblem`
Role: problem
Summary: Evaluator for decoded interval-output models.
Tags: problem, problems, supervised
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.problem.supervised_regression`
Kind: problem
Title: SupervisedRegressionProblem
Import: `mlblack.problems.supervised:SupervisedRegressionProblem`
Role: problem
Summary: Data-dependent evaluator for point regression.
Tags: regression, gradient, residuals
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.problem.temporal_neural_forecasting`
Kind: problem
Title: TemporalNeuralForecastingProblem
Import: `mlblack.problems.neural:TemporalNeuralForecastingProblem`
Role: problem
Summary: Evaluate temporal neural graph models (LSTM/TCN/Transformer) for sequence forecasting.
Tags: problem, problems, neural
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.problem.temporal_neural_probabilistic_forecasting`
Kind: problem
Title: TemporalNeuralProbabilisticForecastingProblem
Import: `mlblack.problems.neural:TemporalNeuralProbabilisticForecastingProblem`
Role: problem
Summary: Evaluate temporal neural graph models with negative log-likelihood loss for probabilistic forecasting.
Tags: problem, problems, neural
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.problem.temporal_neural_rolling_origin`
Kind: problem
Title: TemporalNeuralRollingOriginProblem
Import: `mlblack.problems.neural:TemporalNeuralRollingOriginProblem`
Role: problem
Summary: Rolling-origin evaluation for temporal neural graph forecasters.
Tags: problem, problems, neural
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.problem.time_series_forecasting`
Kind: problem
Title: TimeSeriesForecastingProblem
Import: `mlblack.problems.time_series:TimeSeriesForecastingProblem`
Role: problem
Summary: Evaluator for univariate time-series forecasting models.
Tags: problem, problems, time_series
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.problem.tiny_cnn_image_classification`
Kind: problem
Title: TinyCNNImageClassificationProblem
Import: `mlblack.problems.neural:TinyCNNImageClassificationProblem`
Role: problem
Summary: Evaluate tiny CNN image classification heads.
Tags: problem, problems, neural
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.problem.tiny_cnn_image_contrastive`
Kind: problem
Title: TinyCNNImageContrastiveProblem
Import: `mlblack.problems.neural:TinyCNNImageContrastiveProblem`
Role: problem
Summary: Triplet contrastive/retrieval loss over tiny CNN embedding heads.
Tags: problem, problems, neural
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.problem.tiny_gnn_graph_classification`
Kind: problem
Title: TinyGNNGraphClassificationProblem
Import: `mlblack.problems.neural:TinyGNNGraphClassificationProblem`
Role: problem
Summary: Evaluate tiny GNN graph classification heads.
Tags: problem, problems, neural
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.problem.tiny_transformer_classification`
Kind: problem
Title: TinyTransformerClassificationProblem
Import: `mlblack.problems.neural:TinyTransformerClassificationProblem`
Role: problem
Summary: Evaluate tiny Transformer classification heads with torch autograd.
Tags: problem, problems, neural
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.problem.tiny_transformer_dpo_preference`
Kind: problem
Title: TinyTransformerDPOPreferenceProblem
Import: `mlblack.problems.neural:TinyTransformerDPOPreferenceProblem`
Role: problem
Summary: DPO-style preference loss over chosen/rejected token sequences.
Tags: problem, problems, neural
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.problem.tiny_transformer_language_model`
Kind: problem
Title: TinyTransformerLanguageModelProblem
Import: `mlblack.problems.neural:TinyTransformerLanguageModelProblem`
Role: problem
Summary: Evaluate tiny Transformer LM heads on next-token prediction.
Tags: problem, problems, neural
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.problem.training_proxy`
Kind: problem_bridge
Title: MLBlackTrainingProxy
Import: `mlblack.problems.proxy:MLBlackTrainingProxy`
Role: problem_bridge
Summary: Framework-neutral proxy for outer optimizers invoking mlblack inner training.
Tags: cross-framework, proxy, training-contract
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.problem_bridge.ml_black_training`
Kind: problem_bridge
Title: MLBlackTrainingProxy
Import: `mlblack.problems.proxy:MLBlackTrainingProxy`
Role: problem_bridge
Summary: Framework-neutral proxy for outer optimizers.
Tags: problem_bridge, problems, proxy
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.provider.torch_evaluation`
Kind: provider
Title: TorchEvaluationProvider
Import: `mlblack.backends.torch_neural.evaluation_provider:TorchEvaluationProvider`
Role: provider
Summary: Torch 评估 Provider：在 Project L0 grant 内执行 ML Problem 的 loss/autograd/device 语义，并持有版本化参数、梯度与 optimizer slot；优化方法仍由 nsgablack Adapter 选择。
Tags: provider, torch, autograd, evaluation, l0, gradient, state-transition, materialization
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.provider.arimasarimax`
Kind: provider
Title: ARIMASARIMAXProvider
Import: `mlblack.models.time_series:ARIMASARIMAXProvider`
Role: provider
Summary: Provider that fits ARIMA/SARIMAX specs through numpy or statsmodels.
Tags: provider, models, time_series
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.representation.baseline_forecast`
Kind: representation
Title: BaselineForecastRepresentation
Import: `mlblack.representations.time_series:BaselineForecastRepresentation`
Role: representation
Summary: UnknownState -> Naive/seasonal-naive/moving-average forecast model.
Tags: representation, representations, time_series
Wiring status: unverified
Wiring notes:
Methods: init=ok, mutate=missing, repair=ok, encode=missing, decode=ok
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.representation.baseline_forecast_search`
Kind: representation
Title: BaselineForecastSearchConfig
Import: `mlblack.representations.time_series:BaselineForecastSearchConfig`
Role: representation
Summary: Search space for simple univariate forecasting baselines.
Tags: representation, representations, time_series
Wiring status: unverified
Wiring notes:
Methods: init=missing, mutate=missing, repair=missing, encode=missing, decode=missing
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.representation.estimator_spec`
Kind: representation
Title: EstimatorSpecRepresentation
Import: `mlblack.representations.estimator_specs:EstimatorSpecRepresentation`
Role: representation
Summary: Unknown vector decoded into a typed external estimator spec.
Tags: tree, xgboost, sklearn, codec
Wiring status: unverified
Wiring notes:
Methods: init=ok, mutate=missing, repair=ok, encode=ok, decode=ok
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.representation.forecast_model_spec`
Kind: representation
Title: ForecastModelSpecRepresentation
Import: `mlblack.representations.time_series:ForecastModelSpecRepresentation`
Role: representation
Summary: Single-candidate Codec that decodes a declarative forecast fit spec; fitting belongs to the ML Problem/Provider.
Tags: representation, representations, time_series, codec, fit-spec
Wiring status: unverified
Wiring notes:
Methods: init=ok, mutate=missing, repair=ok, encode=ok, decode=ok
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.representation.linear_point`
Kind: representation
Title: LinearPointRepresentation
Import: `mlblack.representations.linear_point:LinearPointRepresentation`
Role: representation
Summary: Unknown vector -> raw linear model with pluggable output head.
Tags: representation, representations, linear_point
Wiring status: unverified
Wiring notes:
Methods: init=ok, mutate=missing, repair=ok, encode=ok, decode=ok
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.representation.neural_graph`
Kind: representation
Title: NeuralGraphRepresentation
Import: `mlblack.representations.neural_graph:NeuralGraphRepresentation`
Role: representation
Summary: Unknown vector -> configured neural graph model.
Tags: representation, representations, neural_graph
Wiring status: unverified
Wiring notes:
Methods: init=ok, mutate=missing, repair=ok, encode=missing, decode=ok
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.representation.orthogonal_linear`
Kind: representation
Title: OrthogonalPointLinearRepresentation
Import: `mlblack.representations.orthogonal_point:OrthogonalPointLinearRepresentation`
Role: representation
Summary: Unknown vector decoded through orthogonal feature map and output head.
Tags: linear, orthogonal, head
Wiring status: unverified
Wiring notes:
Methods: init=ok, mutate=missing, repair=ok, encode=ok, decode=ok
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.representation.orthogonal_point_linear`
Kind: representation
Title: OrthogonalPointLinearRepresentation
Import: `mlblack.representations.orthogonal_point:OrthogonalPointLinearRepresentation`
Role: representation
Summary: Unknown vector -> orthogonal linear model with pluggable output head.
Tags: representation, representations, orthogonal_point
Wiring status: unverified
Wiring notes:
Methods: init=ok, mutate=missing, repair=ok, encode=ok, decode=ok
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.representation.piecewise`
Kind: representation
Title: PiecewiseRepresentation
Import: `mlblack.representations.conditional:PiecewiseRepresentation`
Role: representation
Summary: Concatenates branch states and decodes a routed piecewise model.
Tags: conditional, piecewise, router
Wiring status: unverified
Wiring notes:
Methods: init=ok, mutate=missing, repair=ok, encode=missing, decode=ok
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.representation.symbolic_basis_set`
Kind: representation
Title: SymbolicBasisSetRepresentation
Import: `mlblack.representations.symbolic:SymbolicBasisSetRepresentation`
Role: representation
Summary: Fixed multi-expression symbolic candidate -> basis-set output.
Tags: representation, representations, symbolic
Wiring status: unverified
Wiring notes:
Methods: init=ok, mutate=missing, repair=ok, encode=missing, decode=ok
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.representation.symbolic_expression`
Kind: representation
Title: SymbolicExpressionRepresentation
Import: `mlblack.representations.symbolic:SymbolicExpressionRepresentation`
Role: representation
Summary: Fixed symbolic expression -> point/interval/probability head.
Tags: representation, representations, symbolic
Wiring status: unverified
Wiring notes:
Methods: init=ok, mutate=missing, repair=ok, encode=ok, decode=ok
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.schema.scaffold_config`
Kind: schema
Title: ScaffoldConfig
Import: `mlblack.assembly.schema.spec:ScaffoldConfig`
Role: schema
Summary: Top-level JSON-compatible scaffold contract.
Tags: schema, config, scaffold
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.symbolic_pipeline.candidate_term`
Kind: symbolic_pipeline
Title: CandidateTerm
Import: `mlblack.pipeline.symbolic.function_space:CandidateTerm`
Role: symbolic_pipeline
Summary: Materialized symbolic candidate term produced by a function-space pipeline.
Tags: symbolic_pipeline, pipeline, symbolic, function_space
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.symbolic_pipeline.dynamic_function_pool_pipeline`
Kind: symbolic_pipeline
Title: DynamicFunctionPoolPipeline
Import: `mlblack.pipeline.symbolic.dynamic_pool:DynamicFunctionPoolPipeline`
Role: symbolic_pipeline
Summary: Residual/gradient/budget/gate aware symbolic pool updater.
Tags: symbolic_pipeline, pipeline, symbolic, dynamic_pool
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.symbolic_pipeline.function_pool`
Kind: symbolic_pipeline
Title: FunctionPool
Import: `mlblack.pipeline.symbolic.function_space:FunctionPool`
Role: symbolic_pipeline
Summary: Current active symbolic candidate pool.
Tags: symbolic_pipeline, pipeline, symbolic, function_space
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.symbolic_pipeline.function_pool_pipeline`
Kind: symbolic_pipeline
Title: FunctionPoolPipeline
Import: `mlblack.pipeline.symbolic.pool_pipeline:FunctionPoolPipeline`
Role: symbolic_pipeline
Summary: Symbolic search-space pipeline.
Tags: symbolic_pipeline, pipeline, symbolic, pool_pipeline
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.symbolic_pipeline.function_space`
Kind: symbolic_pipeline
Title: FunctionSpace
Import: `mlblack.pipeline.symbolic.function_space:FunctionSpace`
Role: symbolic_pipeline
Summary: Declarative symbolic search-space plus a materialized active pool.
Tags: symbolic_pipeline, pipeline, symbolic, function_space
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.symbolic_pipeline.function_space_provider`
Kind: symbolic_pipeline
Title: FunctionSpaceProvider
Import: `mlblack.pipeline.symbolic.function_space:FunctionSpaceProvider`
Role: symbolic_pipeline
Summary: Contract marker for components that produce symbolic function pools.
Tags: symbolic_pipeline, pipeline, symbolic, function_space
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.symbolic_pipeline.pair_grammar_rule`
Kind: symbolic_pipeline
Title: PairGrammarRule
Import: `mlblack.pipeline.symbolic.primitives:PairGrammarRule`
Role: symbolic_pipeline
Summary: PairGrammarRule(key: 'str', activation_family: 'str', output_family: 'str', complexity: 'float', build_expr: 'PairExprBuilder', evaluate_values: 'PairValueBuilder', build_name: 'PairNameBuilder', initial_enabled: 'bool' = True, dynamic_enabled: 'bool' = True)
Tags: symbolic_pipeline, pipeline, symbolic, primitives
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.symbolic_pipeline.primitive_registry`
Kind: symbolic_pipeline
Title: PrimitiveRegistry
Import: `mlblack.pipeline.symbolic.primitives:PrimitiveRegistry`
Role: symbolic_pipeline
Summary: PrimitiveRegistry(unary_specs: 'tuple[UnaryPrimitiveSpec, ...]', pair_rules: 'tuple[PairGrammarRule, ...]')
Tags: symbolic_pipeline, pipeline, symbolic, primitives
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.symbolic_pipeline.unary_primitive`
Kind: symbolic_pipeline
Title: UnaryPrimitiveSpec
Import: `mlblack.pipeline.symbolic.primitives:UnaryPrimitiveSpec`
Role: symbolic_pipeline
Summary: UnaryPrimitiveSpec(key: 'str', activation_family: 'str', output_family: 'str', complexity: 'float', build_expr: 'UnaryExprBuilder', evaluate_values: 'UnaryValueBuilder', build_name: 'NameBuilder', initial_enabled: 'bool' = True, dynamic_enabled: 'bool' = True)
Tags: symbolic_pipeline, pipeline, symbolic, primitives
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.trainer.learning_solver`
Kind: trainer
Title: LearningSolver
Import: `mlblack.integrations.nsgablack_control:LearningSolver`
Role: trainer
Summary: 复用 NSGABlack 的 Pool、Unit 和求解生命周期；fit/TrainerResult 投影 ML 结果，状态与正式 checkpoint 保留候选及最佳反馈身份。
Tags: trainer, ml-semantics, nsgablack, single-control-plane
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.trainer.diagnostic_solver`
Kind: trainer
Title: build_diagnostic_solver
Import: `mlblack.integrations.nsgablack_diagnostic:build_diagnostic_solver`
Role: trainer
Summary: 通过 NSGABlack FixedCandidateAdapter 运行一次 ML 诊断，不建立私有 Trainer 循环。
Tags: trainer, diagnostic, one-shot, nsgablack
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.backend.jax`
Kind: backend
Title: jax
Import: `mlblack.backends.registry:get_backend`
Role: backend
Summary: Backend catalog entry for jax.
Tags: backend, jax
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.backend_capability.jax.tensor`
Kind: backend_capability
Title: jax.tensor
Import: `mlblack.backends.registry:get_backend`
Role: backend_capability
Summary: Backend catalog entry for jax.tensor.
Tags: backend, jax
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.backend_capability.jax.neural_lowering`
Kind: backend_capability
Title: jax.neural_lowering
Import: `mlblack.backends.registry:get_backend`
Role: backend_capability
Summary: Backend catalog entry for jax.neural_lowering.
Tags: backend, jax
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.backend_capability.jax.losses`
Kind: backend_capability
Title: jax.losses
Import: `mlblack.backends.registry:get_backend`
Role: backend_capability
Summary: Backend catalog entry for jax.losses.
Tags: backend, jax
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.backend_capability.jax.autograd`
Kind: backend_capability
Title: jax.autograd
Import: `mlblack.backends.registry:get_backend`
Role: backend_capability
Summary: Backend catalog entry for jax.autograd.
Tags: backend, jax
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.backend_capability.jax.optimizers`
Kind: backend_capability
Title: jax.optimizers
Import: `mlblack.backends.registry:get_backend`
Role: backend_capability
Summary: Backend catalog entry for jax.optimizers.
Tags: backend, jax
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.backend_capability.jax.artifacts`
Kind: backend_capability
Title: jax.artifacts
Import: `mlblack.backends.registry:get_backend`
Role: backend_capability
Summary: Backend catalog entry for jax.artifacts.
Tags: backend, jax
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.backend.numpy`
Kind: backend
Title: numpy
Import: `mlblack.backends.registry:get_backend`
Role: backend
Summary: Backend catalog entry for numpy.
Tags: backend, numpy
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.backend_capability.numpy.tensor`
Kind: backend_capability
Title: numpy.tensor
Import: `mlblack.backends.registry:get_backend`
Role: backend_capability
Summary: Backend catalog entry for numpy.tensor.
Tags: backend, numpy
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.backend_capability.numpy.neural_lowering`
Kind: backend_capability
Title: numpy.neural_lowering
Import: `mlblack.backends.registry:get_backend`
Role: backend_capability
Summary: Backend catalog entry for numpy.neural_lowering.
Tags: backend, numpy
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.backend_capability.numpy.losses`
Kind: backend_capability
Title: numpy.losses
Import: `mlblack.backends.registry:get_backend`
Role: backend_capability
Summary: Backend catalog entry for numpy.losses.
Tags: backend, numpy
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.backend_capability.numpy.artifacts`
Kind: backend_capability
Title: numpy.artifacts
Import: `mlblack.backends.registry:get_backend`
Role: backend_capability
Summary: Backend catalog entry for numpy.artifacts.
Tags: backend, numpy
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.backend.tensorflow`
Kind: backend
Title: tensorflow
Import: `mlblack.backends.registry:get_backend`
Role: backend
Summary: Backend catalog entry for tensorflow.
Tags: backend, tensorflow
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.backend_capability.tensorflow.tensor`
Kind: backend_capability
Title: tensorflow.tensor
Import: `mlblack.backends.registry:get_backend`
Role: backend_capability
Summary: Backend catalog entry for tensorflow.tensor.
Tags: backend, tensorflow
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.backend_capability.tensorflow.neural_lowering`
Kind: backend_capability
Title: tensorflow.neural_lowering
Import: `mlblack.backends.registry:get_backend`
Role: backend_capability
Summary: Backend catalog entry for tensorflow.neural_lowering.
Tags: backend, tensorflow
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.backend_capability.tensorflow.losses`
Kind: backend_capability
Title: tensorflow.losses
Import: `mlblack.backends.registry:get_backend`
Role: backend_capability
Summary: Backend catalog entry for tensorflow.losses.
Tags: backend, tensorflow
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.backend_capability.tensorflow.autograd`
Kind: backend_capability
Title: tensorflow.autograd
Import: `mlblack.backends.registry:get_backend`
Role: backend_capability
Summary: Backend catalog entry for tensorflow.autograd.
Tags: backend, tensorflow
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.backend_capability.tensorflow.optimizers`
Kind: backend_capability
Title: tensorflow.optimizers
Import: `mlblack.backends.registry:get_backend`
Role: backend_capability
Summary: Backend catalog entry for tensorflow.optimizers.
Tags: backend, tensorflow
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.backend_capability.tensorflow.artifacts`
Kind: backend_capability
Title: tensorflow.artifacts
Import: `mlblack.backends.registry:get_backend`
Role: backend_capability
Summary: Backend catalog entry for tensorflow.artifacts.
Tags: backend, tensorflow
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.backend.torch`
Kind: backend
Title: torch
Import: `mlblack.backends.registry:get_backend`
Role: backend
Summary: Backend catalog entry for torch.
Tags: backend, torch
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.backend_capability.torch.tensor`
Kind: backend_capability
Title: torch.tensor
Import: `mlblack.backends.registry:get_backend`
Role: backend_capability
Summary: Backend catalog entry for torch.tensor.
Tags: backend, torch
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.backend_capability.torch.neural_lowering`
Kind: backend_capability
Title: torch.neural_lowering
Import: `mlblack.backends.registry:get_backend`
Role: backend_capability
Summary: Backend catalog entry for torch.neural_lowering.
Tags: backend, torch
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.backend_capability.torch.autograd`
Kind: backend_capability
Title: torch.autograd
Import: `mlblack.backends.registry:get_backend`
Role: backend_capability
Summary: Backend catalog entry for torch.autograd.
Tags: backend, torch
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.backend_capability.torch.optimizers`
Kind: backend_capability
Title: torch.optimizers
Import: `mlblack.backends.registry:get_backend`
Role: backend_capability
Summary: Backend catalog entry for torch.optimizers.
Tags: backend, torch
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.backend_capability.torch.losses`
Kind: backend_capability
Title: torch.losses
Import: `mlblack.backends.registry:get_backend`
Role: backend_capability
Summary: Backend catalog entry for torch.losses.
Tags: backend, torch
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None

## `mlblack.backend_capability.torch.artifacts`
Kind: backend_capability
Title: torch.artifacts
Import: `mlblack.backends.registry:get_backend`
Role: backend_capability
Summary: Backend catalog entry for torch.artifacts.
Tags: backend, torch
Wiring status: unverified
Wiring notes:
Health: import_ok=None context_ok=True methods_ok=True params_ok=None
