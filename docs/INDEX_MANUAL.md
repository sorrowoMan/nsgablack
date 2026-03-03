# 组件说明书（单文件索引）
本文件用于一次性展示框架已实现的核心组件与工程能力。
使用建议：先通过 Catalog 搜索定位，再从本说明书查看结构与伙伴组件。

## 如何检索
```powershell
python -m nsgablack catalog search <关键词>
python -m nsgablack catalog show <key>
```

补充索引：
- `docs/user_guide/CONTEXT_CONTRACTS.md`：Context 契约（requires/provides/mutates）


## 类别说明（简要）
- **Suite**：权威组合（推荐装配方式）
- **Adapter**：搜索策略内核（算法逻辑）
- **Bias**：偏好/软约束（可开关、可比较）
- **Representation**：表示/初始化/变异/修复（硬约束优先）
- **Plugin**：运行/评估/运维能力层
- **Tool**：工具入口/辅助组件
- **Example**：示例与演示（非 API）

## Suite 列表
| Key | Title | Summary | Tags | Companions | Import |
|---|---|---|---|---|---|
| `suite.active_learning_surrogate` | attach_active_learning_surrogate | 权威装配：主动学习代理评估 + 报告。 / Authority wiring: active-learning surrogate evaluation + reporting. | active_learning, authority, bundle, frontier, suite, surrogate | plugin.surrogate_eval | `nsgablack.utils.suites:attach_active_learning_surrogate` |
| `suite.benchmark_harness` | attach_benchmark_harness | 权威装配：BenchmarkHarness统一输出口径。 / Authority wiring: BenchmarkHarness output protocol. | authority, benchmark, bundle, comparison, protocol, suite | plugin.benchmark_harness | `nsgablack.utils.suites:attach_benchmark_harness` |
| `suite.dynamic_switch` | attach_dynamic_switch | 权威装配：动态切换插件，用于运行时策略/权重切换。 / Authority wiring: dynamic switch plugin for runtime strategy/weight switching. | authority, bundle, dynamic, suite, switch | - | `nsgablack.utils.suites.dynamic_switch:attach_dynamic_switch` |
| `suite.mas` | attach_mas | 权威装配：MAS + 模型插件 + 报告。 / Authority wiring: MAS + model plugin + reporting. | authority, bundle, local_search, mas, suite, surrogate | adapter.mas, plugin.mas_model, plugin.benchmark_harness, plugin.module_report | `nsgablack.utils.suites:attach_mas` |
| `suite.module_report` | attach_module_report | 权威装配：ModuleReport审计/消融。 / Authority wiring: ModuleReport audit/ablation. | ablation, audit, authority, bundle, report, suite | plugin.module_report, plugin.benchmark_harness | `nsgablack.utils.suites:attach_module_report` |
| `suite.moead` | attach_moead | 权威装配：MOEA/D适配器 + Pareto归档。 / Authority wiring: MOEA/D adapter + Pareto archive. | authority, bundle, moead, multiobjective, suite | adapter.moead, plugin.pareto_archive | `nsgablack.utils.suites:attach_moead` |
| `suite.monte_carlo_robustness` | attach_monte_carlo_robustness | 权威装配：Monte Carlo评估 + 鲁棒性偏置。 / Authority wiring: MC evaluation + robustness bias. | authority, bundle, mc, robustness, suite | plugin.monte_carlo_eval, bias.robustness | `nsgablack.utils.suites:attach_monte_carlo_robustness` |
| `suite.multi_fidelity_eval` | attach_multi_fidelity_eval | 权威装配：多保真评估 + 报告。 / Authority wiring: multi-fidelity evaluation + reporting. | authority, bundle, evaluation, frontier, multi_fidelity, suite | plugin.multi_fidelity_eval | `nsgablack.utils.suites:attach_multi_fidelity_eval` |
| `suite.multi_strategy` | attach_multi_strategy_coop | 权威装配：多策略协同（角色/预算/共享状态）。 / Authority wiring: multi-strategy cooperation with roles/budgets/shared state. | authority, bundle, cooperation, multi_strategy, parallel, suite | adapter.multi_strategy, plugin.pareto_archive | `nsgablack.utils.suites:attach_multi_strategy_coop` |
| `suite.nsga2_engineering` | attach_nsga2_engineering | 权威装配：NSGA-II工程化插件集（日志/精英/多样性）。 / Authority wiring: NSGA-II engineering bundle (logging/elite/diversity). | authority, bundle, engineering, nsga2, plugins, suite | plugin.elite, plugin.convergence_monitor, plugin.diversity_init, plugin.benchmark_harness | `nsgablack.utils.suites:attach_nsga2_engineering` |
| `suite.ray_parallel` | attach_ray_parallel | 权威装配：Ray并行评估/调度。 / Authority wiring: Ray parallel evaluation/scheduling. | authority, bundle, distributed, parallel, ray, suite | plugin.profiler, plugin.benchmark_harness | `nsgablack.utils.suites:attach_ray_parallel` |
| `suite.risk_cvar` | attach_risk_cvar | 权威装配：MC评估 + CVaR风险偏置。 / Authority wiring: MC evaluation + CVaR risk bias. | authority, bundle, cvar, frontier, risk, suite | plugin.monte_carlo_eval, bias.risk | `nsgablack.utils.suites:attach_risk_cvar` |
| `suite.robust_dfo` | attach_robust_dfo | 权威装配：DFO + MC评估 + 鲁棒偏置。 / Authority wiring: DFO + MC eval + robustness bias. | authority, bundle, dfo, frontier, mc, robustness, suite | adapter.trust_region_dfo, plugin.monte_carlo_eval, bias.robustness | `nsgablack.utils.suites:attach_robust_dfo` |
| `suite.sa` | attach_simulated_annealing | 权威装配：SA适配器 + 推荐算子。 / Authority wiring: SA adapter + recommended operators. | authority, bundle, sa, simulated_annealing, suite | adapter.sa, repr.context_gaussian | `nsgablack.utils.suites:attach_simulated_annealing` |
| `suite.structure_prior_mo` | attach_structure_prior_mo | 权威装配：结构先验 + 多目标组合。 / Authority wiring: structure-prior + multi-objective bundle. | authority, bundle, frontier, multiobjective, structure, suite | bias.structure_prior, adapter.moead | `nsgablack.utils.suites:attach_structure_prior_mo` |
| `suite.surrogate_assisted_ea` | attach_surrogate_assisted_ea | 权威装配：代理辅助进化搜索。 / Authority wiring: surrogate-assisted evolutionary search. | authority, bundle, evolutionary, frontier, suite, surrogate | plugin.surrogate_eval | `nsgablack.utils.suites:attach_surrogate_assisted_ea` |
| `suite.surrogate_model_lab` | attach_surrogate_model_lab | 权威装配：代理模型家族实验室。 / Authority wiring: surrogate model family lab bundle. | authority, bundle, frontier, model_type, suite, surrogate | plugin.surrogate_eval | `nsgablack.utils.suites:attach_surrogate_model_lab` |
| `suite.trust_region_dfo` | attach_trust_region_dfo | 权威装配：信赖域DFO + 报告插件。 / Authority wiring: trust-region DFO + reporting. | authority, bundle, dfo, local_search, suite, trust_region | adapter.trust_region_dfo, plugin.benchmark_harness, plugin.module_report | `nsgablack.utils.suites:attach_trust_region_dfo` |
| `suite.trust_region_mo_dfo` | attach_trust_region_mo_dfo | 权威装配：多目标DFO + Pareto + 报告。 / Authority wiring: MO DFO + Pareto + reporting. | , , authority, bundle, frontier, multiobjective, suite, trust_region | adapter.trust_region_mo_dfo, plugin.pareto_archive | `nsgablack.utils.suites:attach_trust_region_mo_dfo` |
| `suite.trust_region_nonsmooth` | attach_trust_region_nonsmooth | 权威装配：非光滑信赖域 + 报告插件。 / Authority wiring: nonsmooth trust-region + reporting. | authority, bundle, local_search, nonsmooth, suite, trust_region | adapter.trust_region_nonsmooth, plugin.benchmark_harness, plugin.module_report | `nsgablack.utils.suites:attach_trust_region_nonsmooth` |
| `suite.trust_region_subspace` | attach_trust_region_subspace | 权威装配：子空间信赖域 + 报告插件。 / Authority wiring: subspace trust-region + reporting. | authority, bundle, local_search, subspace, suite, trust_region | adapter.trust_region_subspace, plugin.benchmark_harness, plugin.module_report | `nsgablack.utils.suites:attach_trust_region_subspace` |
| `suite.trust_region_subspace_frontier` | attach_trust_region_subspace_frontier | 权威装配：子空间信赖域前沿组合 + 报告。 / Authority wiring: subspace trust-region frontier bundle. | , , authority, bundle, frontier, subspace, suite, trust_region | adapter.trust_region_subspace, plugin.subspace_basis | `nsgablack.utils.suites:attach_trust_region_subspace_frontier` |
| `suite.trust_region_subspace_learned` | attach_trust_region_subspace_learned | 权威装配：子空间信赖域 + 学习基底(PCA/SVD)。 / Authority wiring: subspace trust-region + learned basis (PCA/SVD). | authority, bundle, learned, subspace, suite, trust_region | adapter.trust_region_subspace, plugin.subspace_basis, plugin.benchmark_harness, plugin.module_report | `nsgablack.utils.suites:attach_trust_region_subspace_learned` |
| `suite.vns` | attach_vns | 权威装配：VNS适配器 + 多邻域算子。 / Authority wiring: VNS adapter + multi-neighborhood operators. | authority, bundle, local_search, suite, vns | adapter.vns, repr.context_gaussian, repr.context_switch | `nsgablack.utils.suites:attach_vns` |

## Adapter 列表
| Key | Title | Summary | Tags | Companions | Import |
|---|---|---|---|---|---|
| `adapter.astar` | AStarAdapter | A*搜索内核：可配置邻居、启发式与目标判定。 / Adapter: A* core with pluggable neighbors/heuristic/goal. | adapter, astar, core, graph, heuristic, pathfinding, strategy | - | `nsgablack.adapters.astar:AStarAdapter` |
| `adapter.composite` | CompositeAdapter | 组合适配器：合并多个适配器候选，并处理冲突。 / Adapter: composite adapter merging proposals and resolving conflicts. | adapter, composition, core, strategy | - | `nsgablack.adapters.algorithm_adapter:CompositeAdapter` |
| `adapter.mas` | MASAdapter | Model-and-Search：交替建模与搜索。 / Adapter: model-and-search alternating model update + search. | adapter, core, local_search, mas, strategy, surrogate | - | `nsgablack.adapters:MASAdapter` |
| `adapter.moa_star` | MOAStarAdapter | 多目标A*：Pareto标签与支配剪枝，面向多目标路径。 / Adapter: MOA* with Pareto labels and dominance pruning. | adapter, astar, core, graph, heuristic, multiobjective, pareto, strategy | - | `nsgablack.adapters.moa_star:MOAStarAdapter` |
| `adapter.moead` | MOEADAdapter | MOEA/D分解内核：权重向量 + 邻域替换。 / Adapter: MOEA/D decomposition core with weight vectors and neighborhood replacement. | adapter, core, decomposition, moead, multiobjective, strategy | plugin.pareto_archive, suite.moead | `nsgablack.adapters:MOEADAdapter` |

| `adapter.de` | DifferentialEvolutionAdapter | 差分进化适配器：变异/交叉/贪心替换。/ Adapter: Differential Evolution with greedy replacement. | adapter, core, de, differential_evolution, evolutionary, strategy | - | `nsgablack.adapters:DifferentialEvolutionAdapter` |
| `adapter.gradient_descent` | GradientDescentAdapter | 梯度下降适配器：有限差分估计梯度并局部精修。/ Adapter: finite-difference gradient descent local refinement. | adapter, core, gradient, gradient_descent, local_search, strategy | - | `nsgablack.adapters:GradientDescentAdapter` |
| `adapter.nsga2` | NSGA2Adapter | NSGA-II 适配器：非支配排序 + 拥挤距离选择。/ Adapter: NSGA-II with non-dominated sorting and crowding selection. | adapter, core, evolutionary, multiobjective, nsga2, strategy | - | `nsgablack.adapters:NSGA2Adapter` |
| `adapter.nsga3` | NSGA3Adapter | NSGA-III 适配器：参考点引导的 niching 选择。/ Adapter: NSGA-III with reference-point niching. | adapter, core, evolutionary, multiobjective, nsga3, strategy | - | `nsgablack.adapters:NSGA3Adapter` |
| `adapter.pattern_search` | PatternSearchAdapter | 模式搜索适配器：坐标方向试探与步长自适应。/ Adapter: coordinate pattern search with adaptive step size. | adapter, core, local_search, pattern_search, strategy | - | `nsgablack.adapters:PatternSearchAdapter` |
| `adapter.spea2` | SPEA2Adapter | SPEA2 适配器：强度值与密度估计联合选择。/ Adapter: SPEA2 with strength and density fitness. | adapter, core, evolutionary, multiobjective, spea2, strategy | - | `nsgablack.adapters:SPEA2Adapter` |
| `adapter.multi_role_controller` | MultiRoleControllerAdapter | 多角色控制器：共享上下文与预算分配，统一调度各角色。 / Adapter: multi-role controller with shared context and budget scheduling. | adapter, composition, controller, core, roles, strategy | - | `nsgablack.adapters.role_adapters:MultiRoleControllerAdapter` |
| `adapter.multi_strategy` | MultiStrategyControllerAdapter | 多策略协同控制器：统一调度、共享状态与动态预算。 / Adapter: multi-strategy controller with unified scheduling/shared state/dynamic budgets. | adapter, controller, cooperation, core, multi_strategy, parallel, roles, strategy | suite.multi_strategy, plugin.pareto_archive | `nsgablack.adapters:MultiStrategyControllerAdapter` |
| `adapter.role` | RoleAdapter | 角色适配器：附加角色元数据与配额，用于分工协同。 / Adapter: role wrapper with metadata and candidate quotas for cooperation. | adapter, composition, core, roles, strategy | - | `nsgablack.adapters.role_adapters:RoleAdapter` |
| `adapter.sa` | SimulatedAnnealingAdapter | 模拟退火内核：温度调度 + Metropolis接受。 / Adapter: SA core with temperature schedule and Metropolis acceptance. | adapter, core, local_search, sa, simulated_annealing, strategy | repr.context_gaussian, suite.sa | `nsgablack.adapters:SimulatedAnnealingAdapter` |
| `adapter.trust_region_dfo` | TrustRegionDFOAdapter | 信赖域DFO内核：无梯度局部搜索。 / Adapter: trust-region derivative-free local search. | adapter, core, dfo, local_search, strategy, trust_region | - | `nsgablack.adapters:TrustRegionDFOAdapter` |
| `adapter.trust_region_mo_dfo` | TrustRegionMODFOAdapter | 多目标信赖域DFO：权重标度/帕累托精修。 / Adapter: MO trust-region DFO with scalarization. | adapter, core, dfo, multiobjective, strategy, trust_region | - | `nsgablack.adapters:TrustRegionMODFOAdapter` |
| `adapter.trust_region_nonsmooth` | TrustRegionNonSmoothAdapter | 非光滑信赖域：支持Linf聚合等非光滑目标。 / Adapter: non-smooth trust-region with Linf aggregation. | adapter, core, local_search, nonsmooth, strategy, trust_region | - | `nsgablack.adapters:TrustRegionNonSmoothAdapter` |
| `adapter.trust_region_subspace` | TrustRegionSubspaceAdapter | 子空间/低秩信赖域：适用高维局部搜索。 / Adapter: subspace/low-rank trust-region search for high-D. | adapter, core, dfo, strategy, subspace, trust_region | - | `nsgablack.adapters:TrustRegionSubspaceAdapter` |
| `adapter.vns` | VNSAdapter | VNS局部搜索内核：多邻域分阶段精修。 / Adapter: VNS local search core with multi-neighborhood refinement. | adapter, core, local_search, refinement, stage, strategy, vns | repr.context_gaussian, repr.context_switch, suite.vns | `nsgablack.adapters:VNSAdapter` |

## Bias 列表
| Key | Title | Summary | Tags | Companions | Import |
|---|---|---|---|---|---|
| `bias.bayesian_convergence` | BayesianConvergenceBias | 贝叶斯收敛偏置：在可信区间内收敛。 / Specialized bias: converge within posterior confidence. | bayesian, bias, convergence, specialized | - | `nsgablack.bias.specialized.bayesian_biases:BayesianConvergenceBias` |
| `bias.bayesian_exploration` | BayesianExplorationBias | 贝叶斯探索偏置：优先高不确定区域。 / Specialized bias: favor uncertain regions. | bayesian, bias, exploration, specialized | - | `nsgablack.bias.specialized.bayesian_biases:BayesianExplorationBias` |
| `bias.bayesian_guidance` | BayesianGuidanceBias | 贝叶斯引导偏置：用代理/先验引导搜索。 / Specialized bias: Bayesian-guided exploration. | bayesian, bias, guidance, specialized | - | `nsgablack.bias.specialized.bayesian_biases:BayesianGuidanceBias` |
| `bias.callable` | CallableBias | 可调用偏置：用户函数作为偏置。 / Domain bias: user callable bias function. | bias, callable, domain | - | `nsgablack.bias.domain.callable_bias:CallableBias` |
| `bias.cmaes` | CMAESBias | CMA-ES偏置：协方差自适应搜索。 / Algorithmic bias: CMA-ES covariance adaptation. | algorithmic, bias, cma-es, cmaes, covariance, strategy | - | `nsgablack.bias.algorithmic.cma_es:CMAESBias` |
| `bias.cmaes_adaptive` | AdaptiveCMAESBias | 自适应CMA-ES偏置：协方差/步长自适应。 / Algorithmic bias: adaptive CMA-ES tuning. | adaptive, algorithmic, bias, cmaes | - | `nsgablack.bias.algorithmic.cma_es:AdaptiveCMAESBias` |
| `bias.constraint` | ConstraintBias | 约束偏置：将规则/约束显式注入评分。 / Domain bias: inject constraints into scoring. | bias, constraint, domain | - | `nsgablack.bias.domain.constraint:ConstraintBias` |
| `bias.convergence` | ConvergenceBias | 收敛偏置：优先收敛与精修。 / Algorithmic bias: convergence acceleration. | algorithmic, bias, convergence, exploitation, schedule | - | `nsgablack.bias.algorithmic.convergence:ConvergenceBias` |
| `bias.convergence_adaptive` | AdaptiveConvergenceBias | 自适应收敛偏置：动态平衡探索与收敛。 / Algorithmic bias: adaptively balance exploration vs convergence. | adaptive, algorithmic, bias, convergence | - | `nsgablack.bias.algorithmic.convergence:AdaptiveConvergenceBias` |
| `bias.convergence_late_stage` | LateStageConvergenceBias | 后期收敛偏置：末期加速收敛与精修。 / Algorithmic bias: accelerate late-stage convergence. | algorithmic, bias, convergence, late_stage | - | `nsgablack.bias.algorithmic.convergence:LateStageConvergenceBias` |
| `bias.convergence_multi_stage` | MultiStageConvergenceBias | 多阶段收敛偏置：分阶段切换探索/开发策略。 / Algorithmic bias: multi-stage convergence scheduling. | algorithmic, bias, convergence, multi_stage | - | `nsgablack.bias.algorithmic.convergence:MultiStageConvergenceBias` |
| `bias.convergence_precision` | PrecisionBias | 精度偏置：强调局部精修与数值稳定。 / Algorithmic bias: emphasize precision and local refinement. | algorithmic, bias, convergence, precision | - | `nsgablack.bias.algorithmic.convergence:PrecisionBias` |
| `bias.diversity` | DiversityBias | 多样性偏置：维持解集分散。 / Algorithmic bias: diversity maintenance. | algorithmic, bias, diversity, exploration, niching | - | `nsgablack.bias.algorithmic.diversity:DiversityBias` |
| `bias.diversity_adaptive` | AdaptiveDiversityBias | 自适应多样性偏置：根据状态调节多样性压力。 / Algorithmic bias: adaptively adjust diversity pressure. | adaptive, algorithmic, bias, diversity | - | `nsgablack.bias.algorithmic.diversity:AdaptiveDiversityBias` |
| `bias.diversity_crowding` | CrowdingDistanceBias | 拥挤距离偏置：利用拥挤度喜好稀疏/边界解。 / Algorithmic bias: favor sparse/frontier solutions via crowding distance. | algorithmic, bias, crowding, diversity | - | `nsgablack.bias.algorithmic.diversity:CrowdingDistanceBias` |
| `bias.diversity_niche` | NicheDiversityBias | 小生境多样性偏置：基于niche划分维持分散。 / Algorithmic bias: niche-based diversity preservation. | algorithmic, bias, diversity, niching | - | `nsgablack.bias.algorithmic.diversity:NicheDiversityBias` |
| `bias.diversity_sharing` | SharingFunctionBias | 共享函数偏置：通过适应度共享抑制过度聚集。 / Algorithmic bias: fitness sharing to reduce crowding. | algorithmic, bias, diversity, sharing | - | `nsgablack.bias.algorithmic.diversity:SharingFunctionBias` |
| `bias.dynamic_penalty` | DynamicPenaltyBias | 动态惩罚偏置：随违反程度调节惩罚强度。 / Domain bias: dynamic penalty for constraint violation. | bias, constraint, domain, dynamic, penalty, schedule | - | `nsgablack.bias.domain.dynamic_penalty:DynamicPenaltyBias` |
| `bias.engineering_constraint` | EngineeringConstraintBias | 工程约束偏置：工程规范/规则约束。 / Domain bias: engineering rule constraints. | bias, constraint, domain, engineering | - | `nsgablack.bias.specialized.engineering:EngineeringConstraintBias` |
| `bias.engineering_design` | EngineeringDesignBias | 工程设计偏置：工程可制造性/公差偏好。 / Domain bias: engineering design constraints/priors. | bias, domain, engineering | - | `nsgablack.bias.domain.engineering:EngineeringDesignBias` |
| `bias.engineering_precision` | EngineeringPrecisionBias | 工程精度偏置：精度/公差优先。 / Domain bias: precision/tolerance bias. | bias, domain, engineering, precision | - | `nsgablack.bias.specialized.engineering:EngineeringPrecisionBias` |
| `bias.engineering_robustness` | EngineeringRobustnessBias | 工程鲁棒偏置：对扰动稳健。 / Domain bias: robustness to perturbations. | bias, domain, engineering, robustness | - | `nsgablack.bias.specialized.engineering:EngineeringRobustnessBias` |
| `bias.feasibility` | FeasibilityBias | 可行性偏置：优先可行解/修复倾向。 / Domain bias: prioritize feasibility. | bias, domain, feasibility | - | `nsgablack.bias.domain.constraint:FeasibilityBias` |
| `bias.graph_coloring` | GraphColoringBias | 图着色偏置：减少冲突色。 / Specialized bias: graph coloring bias. | bias, coloring, graph, specialized | - | `nsgablack.bias.specialized.graph.base:GraphColoringBias` |
| `bias.graph_coloring_constraint` | GraphColoringConstraintBias | 着色约束偏置：着色合法性约束。 / Specialized bias: coloring constraints. | bias, coloring, constraint, graph, specialized | - | `nsgablack.bias.specialized.graph.constraints:GraphColoringConstraintBias` |
| `bias.graph_community` | CommunityDetectionBias | 社区结构偏置：增强社区划分。 / Specialized bias: community structure bias. | bias, community, graph, specialized | - | `nsgablack.bias.specialized.graph.base:CommunityDetectionBias` |
| `bias.graph_composite_constraint` | CompositeGraphConstraintBias | 复合图约束偏置：多约束组合。 / Specialized bias: composite graph constraints. | bias, composite, constraint, graph, specialized | - | `nsgablack.bias.specialized.graph.constraints:CompositeGraphConstraintBias` |
| `bias.graph_connectivity` | ConnectivityBias | 连通性偏置：鼓励图连通。 / Specialized bias: graph connectivity. | bias, connectivity, graph, specialized | - | `nsgablack.bias.specialized.graph.base:ConnectivityBias` |
| `bias.graph_constraint` | GraphConstraintBias | 图结构约束偏置：通用图结构约束。 / Specialized bias: graph structural constraints. | bias, constraint, graph, specialized | - | `nsgablack.bias.specialized.graph.constraints:GraphConstraintBias` |
| `bias.graph_degree_distribution` | DegreeDistributionBias | 度分布偏置：匹配目标度分布。 / Specialized bias: target degree distribution. | bias, degree, graph, specialized | - | `nsgablack.bias.specialized.graph.base:DegreeDistributionBias` |
| `bias.graph_hamiltonian_constraint` | HamiltonianPathConstraintBias | 哈密顿路径约束偏置：访问全部节点。 / Specialized bias: Hamiltonian path constraints. | bias, constraint, graph, hamiltonian, specialized | - | `nsgablack.bias.specialized.graph.constraints:HamiltonianPathConstraintBias` |
| `bias.graph_matching_constraint` | MatchingConstraintBias | 匹配约束偏置：匹配合法性约束。 / Specialized bias: matching constraints. | bias, constraint, graph, matching, specialized | - | `nsgablack.bias.specialized.graph.constraints:MatchingConstraintBias` |
| `bias.graph_max_flow` | MaxFlowBias | 最大流偏置：提高可达流量。 / Specialized bias: max-flow preference. | bias, graph, max_flow, specialized | - | `nsgablack.bias.specialized.graph.base:MaxFlowBias` |
| `bias.graph_path_constraint` | PathConstraintBias | 路径约束偏置：路径合法性/可达性。 / Specialized bias: path constraints. | bias, constraint, graph, path, specialized | - | `nsgablack.bias.specialized.graph.constraints:PathConstraintBias` |
| `bias.graph_shortest_path` | ShortestPathBias | 最短路径偏置：优先更短路径。 / Specialized bias: shortest path preference. | bias, graph, shortest_path, specialized | - | `nsgablack.bias.specialized.graph.base:ShortestPathBias` |
| `bias.graph_sparsity` | SparsityBias | 稀疏偏置：偏向稀疏图结构。 / Specialized bias: graph sparsity. | bias, graph, sparsity, specialized | - | `nsgablack.bias.specialized.graph.base:SparsityBias` |
| `bias.graph_tree_constraint` | TreeConstraintBias | 树结构约束偏置：树结构约束。 / Specialized bias: tree constraints. | bias, constraint, graph, specialized, tree | - | `nsgablack.bias.specialized.graph.constraints:TreeConstraintBias` |
| `bias.graph_tsp_constraint` | TSPConstraintBias | TSP约束偏置：巡回路径合法性。 / Specialized bias: TSP constraints. | bias, constraint, graph, specialized, tsp | - | `nsgablack.bias.specialized.graph.constraints:TSPConstraintBias` |
| `bias.levy` | LevyFlightBias | Levy飞行偏置：长跳跃探索。 / Algorithmic bias: Levy-flight exploration. | algorithmic, bias, exploration, levy, random_walk | - | `nsgablack.bias.algorithmic.levy_flight:LevyFlightBias` |
| `bias.local_gd` | GradientDescentBias (LocalSearch) | 局部梯度偏置：局部梯度精修。 / Specialized bias: local gradient refinement. | bias, gradient_descent, local_search, specialized | - | `nsgablack.bias.specialized.local_search:GradientDescentBias` |
| `bias.local_line_search` | LineSearchBias | 线搜索偏置：步长线搜索与调度。 / Specialized bias: line-search step control. | bias, line_search, local_search, specialized | - | `nsgablack.bias.specialized.local_search:LineSearchBias` |
| `bias.local_nelder_mead` | NelderMeadBias | Nelder-Mead偏置：单纯形局部搜索。 / Specialized bias: Nelder-Mead simplex refinement. | bias, local_search, nelder_mead, specialized | - | `nsgablack.bias.specialized.local_search:NelderMeadBias` |
| `bias.local_newton` | NewtonMethodBias | 牛顿偏置：二阶近似加速局部收敛。 / Specialized bias: Newton-style refinement. | bias, local_search, newton, specialized | - | `nsgablack.bias.specialized.local_search:NewtonMethodBias` |
| `bias.local_quasi_newton` | QuasiNewtonBias | 拟牛顿偏置：有限记忆/拟牛顿更新。 / Specialized bias: quasi-Newton refinement. | bias, local_search, quasi_newton, specialized | - | `nsgablack.bias.specialized.local_search:QuasiNewtonBias` |
| `bias.local_trust_region` | TrustRegionBias | 信赖域偏置：局部可信区域内搜索。 / Specialized bias: trust-region refinement. | bias, local_search, specialized, trust_region | - | `nsgablack.bias.specialized.local_search:TrustRegionBias` |
| `bias.manufacturing` | ManufacturingBias | 制造偏置：工艺/产线可行性倾向。 / Domain bias: manufacturing feasibility. | bias, domain, manufacturing | - | `nsgablack.bias.domain.engineering:ManufacturingBias` |
| `bias.preference` | PreferenceBias | 偏好偏置：编码业务偏好与权重。 / Domain bias: encode preferences/weights. | bias, domain, preference | - | `nsgablack.bias.domain.constraint:PreferenceBias` |
| `bias.production_constraint` | ProductionConstraintBias | 生产约束偏置：产线/工艺约束。 / Domain bias: production constraints. | bias, constraint, domain, production | - | `nsgablack.bias.specialized.production.scheduling:ProductionConstraintBias` |
| `bias.production_continuity` | ProductionContinuityBias | 生产连续性偏置：减少切换/中断。 / Domain bias: production continuity. | bias, continuity, domain, production | - | `nsgablack.bias.specialized.production.scheduling:ProductionContinuityBias` |
| `bias.production_diversity` | ProductionDiversityBias | 生产多样性偏置：产品/方案多样性。 / Domain bias: production diversity. | bias, diversity, domain, production | - | `nsgablack.bias.specialized.production.scheduling:ProductionDiversityBias` |
| `bias.production_scheduling` | ProductionSchedulingBias | 生产排程偏置：排程优先与负载平衡。 / Domain bias: production scheduling preference. | bias, domain, production, scheduling | - | `nsgablack.bias.specialized.production.scheduling:ProductionSchedulingBias` |
| `bias.pso` | ParticleSwarmBias | 粒子群偏置：惯性/群体吸引引导。 / Algorithmic bias: PSO inertia/social guidance. | algorithmic, bias, particle_swarm, pso, strategy, swarm | - | `nsgablack.bias.algorithmic.pso:ParticleSwarmBias` |
| `bias.pso_adaptive` | AdaptivePSOBias | 自适应PSO偏置：动态惯性与学习因子。 / Algorithmic bias: adaptive PSO parameters. | adaptive, algorithmic, bias, pso | - | `nsgablack.bias.algorithmic.pso:AdaptivePSOBias` |
| `bias.resource_constraint` | ResourceConstraintBias | 资源约束偏置：资源容量/消耗约束。 / Domain bias: resource capacity constraints. | bias, domain, resource | - | `nsgablack.bias.domain.scheduling:ResourceConstraintBias` |
| `bias.risk` | RiskBias | 风险偏置：支持CVaR/最坏情况风险控制。 / Domain bias: risk-aware scoring (CVaR/worst-case). | bias, cvar, domain, risk, worst_case | - | `nsgablack.bias.domain.risk_bias:RiskBias` |
| `bias.robustness` | RobustnessBias | 鲁棒性偏置：针对扰动的稳定性评估。 / Algorithmic bias: robustness-oriented scoring under perturbations. | bias, mc, robustness, signal_driven, algorithmic | plugin.monte_carlo_eval, suite.monte_carlo_robustness | `nsgablack.bias.algorithmic.signal_driven.robustness:RobustnessBias` |
| `bias.rule_based` | RuleBasedBias | 规则偏置：基于规则的加权/惩罚。 / Domain bias: rule-based weighting/penalty. | bias, domain, rule | - | `nsgablack.bias.domain.constraint:RuleBasedBias` |
| `bias.safety` | SafetyBias | 安全偏置：风险/安全约束优先。 / Domain bias: safety/risk prioritization. | bias, domain, safety | - | `nsgablack.bias.domain.engineering:SafetyBias` |
| `bias.scheduling` | SchedulingBias | 排程偏置：任务顺序/负载平衡。 / Domain bias: scheduling preference. | bias, domain, scheduling | - | `nsgablack.bias.domain.scheduling:SchedulingBias` |
| `bias.structure_prior` | StructurePriorBias | 结构先验偏置：注入结构/对称偏好。 / Domain bias: structure/symmetry prior. | bias, domain, prior, structure, symmetry | - | `nsgablack.bias.domain.structure_prior:StructurePriorBias` |
| `bias.surrogate_control` | SurrogateControlBias | 代理控制偏置：代理评估控制探索。 / Specialized bias: surrogate-guided control. | bias, control, specialized, surrogate | - | `nsgablack.bias.surrogate.base:SurrogateControlBias` |
| `bias.surrogate_phase_schedule` | PhaseScheduleBias | 阶段调度偏置：分阶段切换代理/真实评估。 / Specialized bias: phase scheduling for surrogate/true eval. | bias, schedule, specialized, surrogate | - | `nsgablack.bias.surrogate.phase_schedule:PhaseScheduleBias` |
| `bias.surrogate_uncertainty_budget` | UncertaintyBudgetBias | 不确定预算偏置：按不确定度分配评估预算。 / Specialized bias: uncertainty-aware evaluation budget. | bias, specialized, surrogate, uncertainty | - | `nsgablack.bias.surrogate.uncertainty_budget:UncertaintyBudgetBias` |
| `bias.tabu` | TabuSearchBias | 禁忌搜索偏置：记忆路线防止返回。 / Algorithmic bias: tabu memory to avoid cycling. | bias, memory, strategy, tabu, algorithmic | - | `nsgablack.bias.algorithmic.tabu_search:TabuSearchBias` |
| `bias.time_window` | TimeWindowBias | 时间窗偏置：满足时窗与时序约束。 / Domain bias: time window constraints. | bias, domain, time_window | - | `nsgablack.bias.domain.scheduling:TimeWindowBias` |
| `bias.uncertainty_exploration` | UncertaintyExplorationBias | 不确定探索偏置：优先高不确定区域。 / Algorithmic bias: explore high-uncertainty regions. | bias, exploration, signal_driven, uncertainty, algorithmic | - | `nsgablack.bias.algorithmic.signal_driven.uncertainty_exploration:UncertaintyExplorationBias` |

## Representation 列表
| Key | Title | Summary | Tags | Companions | Import |
|---|---|---|---|---|---|
| `repr.binary` | BinaryInitializer | 表示组件：BinaryInitializer。 / Representation: BinaryInitializer. | binary, bit, initializer | - | `nsgablack.representation.binary:BinaryInitializer` |
| `repr.context_gaussian` | ContextGaussianMutation | 表示组件：ContextGaussianMutation。 / Representation: ContextGaussianMutation. | context, continuous, mutation, vns | adapter.vns | `nsgablack.representation.continuous:ContextGaussianMutation` |
| `repr.context_switch` | ContextSwitchMutator | 表示组件：ContextSwitchMutator。 / Representation: ContextSwitchMutator. | context, discrete, mutation, switch, vns | adapter.vns | `nsgablack.representation:ContextSwitchMutator` |
| `repr.continuous` | UniformInitializer | 表示组件：UniformInitializer。 / Representation: UniformInitializer. | continuous, initializer, real | - | `nsgablack.representation.continuous:UniformInitializer` |
| `repr.dynamic_repair` | DynamicRepair | 表示组件：DynamicRepair。 / Representation: DynamicRepair. | dynamic, pipeline, repair | - | `nsgablack.representation.dynamic:DynamicRepair` |
| `repr.graph` | GraphEdgeInitializer | 表示组件：GraphEdgeInitializer。 / Representation: GraphEdgeInitializer. | graph, initializer, network | - | `nsgablack.representation.graph:GraphEdgeInitializer` |
| `repr.integer` | IntegerInitializer | 表示组件：IntegerInitializer。 / Representation: IntegerInitializer. | discrete, initializer, integer | - | `nsgablack.representation.integer:IntegerInitializer` |
| `repr.matrix` | IntegerMatrixInitializer | 表示组件：IntegerMatrixInitializer。 / Representation: IntegerMatrixInitializer. | grid, initializer, matrix | - | `nsgablack.representation.matrix:IntegerMatrixInitializer` |
| `repr.permutation` | PermutationInitializer | 表示组件：PermutationInitializer。 / Representation: PermutationInitializer. | discrete, initializer, permutation, tsp | - | `nsgablack.representation.permutation:PermutationInitializer` |
| `repr.pipeline` | RepresentationPipeline | 表示组件：RepresentationPipeline。 / Representation: RepresentationPipeline. | core, pipeline, representation | - | `nsgablack.representation:RepresentationPipeline` |
| `repr.projection_repair` | ProjectionRepair | 表示组件：ProjectionRepair。 / Representation: ProjectionRepair. | bounds, pipeline, projection, repair, simplex | - | `nsgablack.representation.continuous:ProjectionRepair` |
| `representation.parallel_repair` | ParallelRepair | 表示组件：ParallelRepair。 / Representation: ParallelRepair. | parallel, pipeline, repair | - | `nsgablack.representation:ParallelRepair` |

## Plugin 列表
| Key | Title | Summary | Tags | Companions | Import |
|---|---|---|---|---|---|
| `plugin.adaptive_parameters` | AdaptiveParametersPlugin | 插件：AdaptiveParametersPlugin。 / Plugin: AdaptiveParametersPlugin. | adaptive, parameters, plugin | - | `nsgablack.utils.plugins:AdaptiveParametersPlugin` |
| `plugin.benchmark_harness` | BenchmarkHarnessPlugin | 插件：BenchmarkHarnessPlugin。 / Plugin: BenchmarkHarnessPlugin. | benchmark, comparison, logging, protocol | suite.benchmark_harness | `nsgablack.utils.plugins:BenchmarkHarnessPlugin` |
| `plugin.convergence_monitor` | ConvergencePlugin | 插件：ConvergencePlugin。 / Plugin: ConvergencePlugin. | convergence, monitor, plugin | - | `nsgablack.utils.plugins:ConvergencePlugin` |
| `plugin.diversity_init` | DiversityInitPlugin | 插件：DiversityInitPlugin。 / Plugin: DiversityInitPlugin. | diversity, init, plugin | - | `nsgablack.utils.plugins:DiversityInitPlugin` |
| `plugin.dynamic_switch` | DynamicSwitchPlugin | 插件：DynamicSwitchPlugin。 / Plugin: DynamicSwitchPlugin. | context, dynamic, plugin, switch | - | `nsgablack.utils.plugins.dynamic_switch:DynamicSwitchPlugin` |
| `plugin.elite` | BasicElitePlugin | 插件：BasicElitePlugin。 / Plugin: BasicElitePlugin. | archive, elite, plugin | - | `nsgablack.utils.plugins:BasicElitePlugin` |
| `plugin.mas_model` | MASModelPlugin | 插件：MASModelPlugin。 / Plugin: MASModelPlugin. | mas, surrogate | - | `nsgablack.utils.plugins:MASModelPlugin` |
| `plugin.memory` | MemoryPlugin | 插件：MemoryPlugin。 / Plugin: MemoryPlugin. | engineering, memory, plugin | - | `nsgablack.utils.plugins:MemoryPlugin` |
| `plugin.module_report` | ModuleReportPlugin | 插件：ModuleReportPlugin。 / Plugin: ModuleReportPlugin. | ablation, audit, bias, report | suite.module_report, plugin.benchmark_harness | `nsgablack.utils.plugins:ModuleReportPlugin` |
| `plugin.monte_carlo_eval` | MonteCarloEvaluationPlugin | 插件：MonteCarloEvaluationPlugin。 / Plugin: MonteCarloEvaluationPlugin. | evaluation, mc, signal | bias.robustness, suite.monte_carlo_robustness | `nsgablack.utils.plugins:MonteCarloEvaluationPlugin` |
| `plugin.multi_fidelity_eval` | MultiFidelityEvaluationPlugin | 插件：MultiFidelityEvaluationPlugin。 / Plugin: MultiFidelityEvaluationPlugin. | evaluation, frontier, multi_fidelity, plugin | - | `nsgablack.utils.plugins:MultiFidelityEvaluationPlugin` |
| `plugin.pareto_archive` | ParetoArchivePlugin | 插件：ParetoArchivePlugin。 / Plugin: ParetoArchivePlugin. | archive, multiobjective, pareto | adapter.moead, suite.moead | `nsgablack.utils.plugins:ParetoArchivePlugin` |
| `plugin.profiler` | ProfilerPlugin | 插件：ProfilerPlugin。 / Plugin: ProfilerPlugin. | audit, performance, profile, throughput | plugin.benchmark_harness, plugin.module_report | `nsgablack.utils.plugins:ProfilerPlugin` |
| `plugin.subspace_basis` | SubspaceBasisPlugin | 插件：SubspaceBasisPlugin。 / Plugin: SubspaceBasisPlugin. | cluster, dfo, pca, random, sparse_pca, subspace, svd | - | `nsgablack.utils.plugins:SubspaceBasisPlugin` |
| `plugin.surrogate_eval` | SurrogateEvaluationPlugin | 插件：SurrogateEvaluationPlugin。 / Plugin: SurrogateEvaluationPlugin. | evaluation, optional, surrogate | - | `nsgablack.utils.plugins:SurrogateEvaluationPlugin` |

## Tool 列表
| Key | Title | Summary | Tags | Companions | Import |
|---|---|---|---|---|---|
| `solver.blank` | SolverBase | 工具：SolverBase。 / Tool: SolverBase. | base, blank, solver | - | `nsgablack.core.blank_solver:SolverBase` |
| `solver.composable` | ComposableSolver | 工具：ComposableSolver。 / Tool: ComposableSolver. | adapter, composition, solver | - | `nsgablack.core.composable_solver:ComposableSolver` |
| `solver.nsga2` | EvolutionSolver | 工具：EvolutionSolver。 / Tool: EvolutionSolver. | evolutionary, nsga2, solver | - | `nsgablack.core.evolution_solver:EvolutionSolver` |
| `tool.context_keys` | Context Keys | 工具：Context Keys。 / Tool: Context Keys. | context, keys, schema, tool | - | `nsgablack.utils.context:context_keys` |
| `tool.context_schema` | MinimalEvaluationContext | 工具：MinimalEvaluationContext。 / Tool: MinimalEvaluationContext. | context, parallel, schema, tool | tool.context_keys | `nsgablack.utils.context:MinimalEvaluationContext` |
| `tool.dynamic_cli_signal` | CLISignalProvider | 工具：CLISignalProvider。 / Tool: CLISignalProvider. | cli, dynamic, signal, tool | - | `nsgablack.utils.dynamic:CLISignalProvider` |
| `tool.logging` | configure_logging | 工具：configure_logging。 / Tool: configure_logging. | engineering, logging, tool | - | `nsgablack.utils.engineering:configure_logging` |
| `tool.metrics` | pareto_filter | 工具：pareto_filter。 / Tool: pareto_filter. | analysis, metrics, pareto, tool | - | `nsgablack.utils.analysis:pareto_filter` |
| `tool.parallel_evaluator` | ParallelEvaluator | 工具：ParallelEvaluator。 / Tool: ParallelEvaluator. | evaluation, parallel, tool | - | `nsgablack.utils.parallel:ParallelEvaluator` |

## Example 列表
| Key | Title | Summary | Tags | Companions | Import |
|---|---|---|---|---|---|
| `example.astar` | astar_demo | 示例：astar_demo。 / Example: astar_demo. | astar, demo, example, graph, search | - | `nsgablack.examples_registry:astar_demo` |
| `example.bias_gallery` | bias_gallery_demo | 示例：bias_gallery_demo。 / Example: bias_gallery_demo. | bias, demo, example, gallery | - | `nsgablack.examples_registry:bias_gallery_demo` |
| `example.context_keys` | context_keys_demo | 示例：context_keys_demo。 / Example: context_keys_demo. | context, demo, example, keys | - | `nsgablack.examples_registry:context_keys_demo` |
| `example.context_schema` | context_schema_demo | 示例：context_schema_demo。 / Example: context_schema_demo. | context, demo, example, schema | - | `nsgablack.examples_registry:context_schema_demo` |
| `example.dynamic_cli_signal` | dynamic_cli_signal_demo | 示例：dynamic_cli_signal_demo。 / Example: dynamic_cli_signal_demo. | cli, demo, dynamic, example, signal | - | `nsgablack.examples_registry:dynamic_cli_signal_demo` |
| `example.dynamic_multi_strategy` | dynamic_multi_strategy_demo | 示例：dynamic_multi_strategy_demo。 / Example: dynamic_multi_strategy_demo. | demo, dynamic, example, multi_strategy, switch | - | `nsgablack.examples_registry:dynamic_multi_strategy_demo` |
| `example.logging` | logging_demo | 示例：logging_demo。 / Example: logging_demo. | demo, example, logging, tool | - | `nsgablack.examples_registry:logging_demo` |
| `example.metrics` | metrics_demo | 示例：metrics_demo。 / Example: metrics_demo. | demo, example, metrics, pareto | - | `nsgablack.examples_registry:metrics_demo` |
| `example.moa_star` | moa_star_demo | 示例：moa_star_demo。 / Example: moa_star_demo. | demo, example, moa_star, pareto, search | - | `nsgablack.examples_registry:moa_star_demo` |
| `example.monte_carlo_robust` | monte_carlo_dp_robust_demo | 示例：monte_carlo_dp_robust_demo。 / Example: monte_carlo_dp_robust_demo. | demo, example, monte_carlo, robust | - | `nsgablack.examples_registry:monte_carlo_dp_robust_demo` |
| `example.multi_fidelity` | multi_fidelity_demo | 示例：multi_fidelity_demo。 / Example: multi_fidelity_demo. | demo, example, multi_fidelity | - | `nsgablack.examples_registry:multi_fidelity_demo` |
| `example.nsga2_solver` | nsga2_solver_demo | 示例：nsga2_solver_demo。 / Example: nsga2_solver_demo. | demo, example, nsga2, solver, suite | - | `nsgablack.examples_registry:nsga2_solver_demo` |
| `example.parallel_evaluator` | parallel_evaluator_demo | 示例：parallel_evaluator_demo。 / Example: parallel_evaluator_demo. | demo, evaluation, example, parallel | - | `nsgablack.examples_registry:parallel_evaluator_demo` |
| `example.parallel_repair` | parallel_repair_demo | 示例：parallel_repair_demo。 / Example: parallel_repair_demo. | demo, example, parallel, pipeline, repair | - | `nsgablack.examples_registry:parallel_repair_demo` |
| `example.plugin_gallery` | plugin_gallery_demo | 示例：plugin_gallery_demo。 / Example: plugin_gallery_demo. | demo, example, gallery, plugin | - | `nsgablack.examples_registry:plugin_gallery_demo` |
| `example.risk_bias` | risk_bias_demo | 示例：risk_bias_demo。 / Example: risk_bias_demo. | bias, demo, example, risk | - | `nsgablack.examples_registry:risk_bias_demo` |
| `example.role_adapters` | role_adapters_demo | 示例：role_adapters_demo。 / Example: role_adapters_demo. | adapter, demo, example, multi_role, role | - | `nsgablack.examples_registry:role_adapters_demo` |
| `example.surrogate_plugin` | surrogate_plugin_demo | 示例：surrogate_plugin_demo。 / Example: surrogate_plugin_demo. | demo, example, plugin, surrogate | - | `nsgablack.examples_registry:surrogate_plugin_demo` |
| `example.template_assignment` | template_assignment_matrix | 示例：template_assignment_matrix。 / Example: template_assignment_matrix. | assignment, example, matrix, repair, template | - | `nsgablack.examples_registry:template_assignment_matrix` |
| `example.template_continuous` | template_continuous_constrained | 示例：template_continuous_constrained。 / Example: template_continuous_constrained. | bias, constraint, continuous, example, pipeline, template | - | `nsgablack.examples_registry:template_continuous_constrained` |
| `example.template_graph_path` | template_graph_path | 示例：template_graph_path。 / Example: template_graph_path. | example, graph, path, repair, template | - | `nsgablack.examples_registry:template_graph_path` |
| `example.template_knapsack` | template_knapsack_binary | 示例：template_knapsack_binary。 / Example: template_knapsack_binary. | binary, example, knapsack, repair, template | - | `nsgablack.examples_registry:template_knapsack_binary` |
| `example.template_mo_pareto` | template_multiobjective_pareto | 示例：template_multiobjective_pareto。 / Example: template_multiobjective_pareto. | example, moead, multiobjective, pareto, template | - | `nsgablack.examples_registry:template_multiobjective_pareto` |
| `example.template_portfolio` | template_portfolio_pareto | 示例：template_portfolio_pareto。 / Example: template_portfolio_pareto. | example, mo, pareto, portfolio, template | - | `nsgablack.examples_registry:template_portfolio_pareto` |
| `example.template_production_simple` | template_production_schedule_simple | 示例：template_production_schedule_simple。 / Example: template_production_schedule_simple. | example, matrix, production, schedule, template | - | `nsgablack.examples_registry:template_production_schedule_simple` |
| `example.template_tsp` | template_tsp_permutation | 示例：template_tsp_permutation。 / Example: template_tsp_permutation. | 2opt, example, permutation, template, tsp | - | `nsgablack.examples_registry:template_tsp_permutation` |
| `example.trust_region_dfo` | trust_region_dfo_demo | 示例：trust_region_dfo_demo。 / Example: trust_region_dfo_demo. | demo, dfo, example, trust_region | - | `nsgablack.examples_registry:trust_region_dfo_demo` |
| `example.trust_region_subspace` | trust_region_subspace_demo | 示例：trust_region_subspace_demo。 / Example: trust_region_subspace_demo. | demo, example, subspace, trust_region | - | `nsgablack.examples_registry:trust_region_subspace_demo` |
