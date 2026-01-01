# 偏置索引

生成时间: 2026-01-01 18:53:55

## algorithmic（算法偏置）

- bias/algorithmic/cma_es.py
  - 类: CMAESBias (L19), AdaptiveCMAESBias (L75)
- bias/algorithmic/convergence.py
  - 类: ConvergenceBias (L13), AdaptiveConvergenceBias (L52), PrecisionBias (L117), LateStageConvergenceBias (L154), MultiStageConvergenceBias (L189)
- bias/algorithmic/differential_evolution.py
  - 类: DifferentialEvolutionBias (L21), AdaptiveDEBias (L260), MultiObjectiveDEBias (L334)
  - 函数: generate_de_trial (L387)
- bias/algorithmic/diversity.py
  - 类: DiversityBias (L18), AdaptiveDiversityBias (L110), NicheDiversityBias (L211), CrowdingDistanceBias (L297), SharingFunctionBias (L360)
- bias/algorithmic/gradient_descent.py
  - 类: GradientDescentBias (L21), MomentumGradientDescentBias (L309), AdaptiveGradientDescentBias (L376), AdamGradientBias (L450)
  - 函数: generate_gradient_descent_point (L539)
- bias/algorithmic/levy_flight.py
  - 类: LevyFlightBias (L17)
- bias/algorithmic/nsga2.py
  - 类: NSGA2Bias (L19), AdaptiveNSGA2Bias (L149), DiversityPreservingNSGA2Bias (L235)
  - 函数: compute_pareto_rank (L302), compute_crowding_distance (L342)
- bias/algorithmic/pattern_search.py
  - 类: PatternSearchBias (L21), AdaptivePatternSearchBias (L217), CoordinateDescentBias (L303)
  - 函数: generate_pattern_search_point (L371), generate_coordinate_descent_points (L393)
- bias/algorithmic/pso.py
  - 类: ParticleSwarmBias (L19), AdaptivePSOBias (L64)
- bias/algorithmic/simulated_annealing.py
  - 类: SimulatedAnnealingBias (L19), AdaptiveSABias (L186), MultiObjectiveSABias (L305)
- bias/algorithmic/tabu_search.py
  - 类: TabuSearchBias (L18)

## core（核心）

- bias/core/base.py
  - 类: OptimizationContext (L13), BiasBase (L74), AlgorithmicBias (L178), DomainBias (L225), BiasManager (L268)
  - 函数: create_bias (L323)
- bias/core/manager.py
  - 类: BiasManagerMixin (L24), AlgorithmicBiasManager (L131), DomainBiasManager (L247), UniversalBiasManager (L341)
- bias/core/registry.py
  - 类: BiasRegistry (L14)
  - 函数: get_bias_registry (L291), register_algorithmic_bias (L296), register_domain_bias (L314), register_bias_factory (L332)

## domain（领域偏置）

- bias/domain/constraint.py
  - 类: ConstraintBias (L18), FeasibilityBias (L134), PreferenceBias (L191), RuleBasedBias (L270)
- bias/domain/engineering.py
  - 类: EngineeringDesignBias (L13), SafetyBias (L47), ManufacturingBias (L61)
- bias/domain/scheduling.py
  - 类: SchedulingBias (L12), ResourceConstraintBias (L26), TimeWindowBias (L40)

## managers（管理器）

- bias/managers/adaptive_manager.py
  - 类: OptimizationState (L16), AdaptiveAlgorithmicManager (L27)
- bias/managers/analytics.py
  - 类: MetricType (L33), BiasEffectivenessMetrics (L49), BiasEffectivenessAnalyzer (L92)
- bias/managers/meta_learning_selector.py
  - 类: ProblemFeatures (L29), BiasRecommendation (L54), ProblemFeatureExtractor (L64), MetaLearningBiasSelector (L156)

## root（根目录）

- bias/__init__.py
  - 函数: create_universal_bias_manager (L246), quick_bias_setup (L276), get_bias_system_info (L343), migrate_legacy_bias (L377)
- bias/bias.py
  - 类: BiasModule (L17)
  - 函数: proximity_reward (L146), improvement_reward (L169), feasibility_depth_reward (L185), diversity_reward (L206), gradient_alignment_reward (L231), constraint_penalty (L259), boundary_penalty (L277), stagnation_penalty (L301), create_standard_bias (L321)
- bias/bias_compatibility.py
  - 类: BackwardCompatibleBiasModule (L15)
  - 函数: create_standard_bias (L124), proximity_reward (L161), improvement_reward (L167), feasibility_depth_reward (L175), diversity_reward (L188), constraint_penalty (L207), boundary_penalty (L214), stagnation_penalty (L226)
- bias/bias_library_algorithmic.py
  - 类: DiversityBias (L111), ConvergenceBias (L141), ExplorationBias (L164), PrecisionBias (L196), AdaptiveDiversityBias (L222), MemoryGuidedBias (L271), GradientApproximationBias (L346), AdaptiveConvergenceBias (L384), PopulationDensityBias (L437), PatternBasedBias (L473), TemperatureControlBias (L532), PatternLearner (L562), AlgorithmicBiasFactory (L601)
  - 函数: create_exploration_focused_bias (L675), create_convergence_focused_bias (L684), create_balanced_bias (L693), create_high_precision_bias (L702), create_adaptive_bias (L711)
- bias/bias_library_domain.py
  - 类: ConstraintBias (L102), PreferenceBias (L147), ObjectiveBias (L177), EngineeringDesignBias (L209), FinancialBias (L285), MLHyperparameterBias (L351), SupplyChainBias (L447), SchedulingBias (L512), PortfolioBias (L579), EnergyOptimizationBias (L675), DomainBiasFactory (L732), ConstraintBasedBias (L794), HealthcareBias (L902), RoboticsBias (L935)
  - 函数: create_engineering_bias (L815), create_ml_bias (L836), create_financial_bias (L858), create_supply_chain_bias (L875), create_healthcare_bias (L892)
- bias/bias_v2.py
  - 类: AlgorithmicBiasManager (L57), DomainBiasManager (L65), UniversalBiasManager (L73)
  - 函数: create_universal_bias_manager (L189), list_available_algorithmic_biases (L208), list_available_domain_biases (L213)

## specialized（专用偏置）

- bias/specialized/bayesian.py
  - 类: SimpleBayesianOptimizer (L25), BayesianGuidanceBias (L50), BayesianExplorationBias (L397), BayesianConvergenceBias (L526), BayesianAdvisor (L642)
  - 函数: create_bayesian_guidance_bias (L618), create_bayesian_exploration_bias (L623), create_bayesian_convergence_bias (L628), create_bayesian_suite (L633)
- bias/specialized/engineering.py
  - 类: EngineeringPrecisionBias (L38), EngineeringConstraintBias (L171), EngineeringRobustnessBias (L304)
  - 函数: create_engineering_bias_suite (L423), create_engineering_constraint_bias (L461)
- bias/specialized/graph/abstract.py
  - 类: GraphType (L27), SolutionEncoding (L40), GraphMetadata (L51), ValidationResult (L61), AbstractGraphProblem (L73), PermutationGraphProblem (L115), TSPProblem (L180), HamiltonianPathProblem (L229), BinaryEdgesGraphProblem (L278), SpanningTreeProblem (L311), PartitionGraphProblem (L419), GraphColoringProblem (L444), GraphProblemFactory (L503), CompositeGraphProblem (L542)
- bias/specialized/graph/base.py
  - 类: GraphStructure (L32), GraphUtils (L74), GraphBias (L154), ConnectivityBias (L167), SparsityBias (L198), DegreeDistributionBias (L218), ShortestPathBias (L267), MaxFlowBias (L321), GraphColoringBias (L356), CommunityDetectionBias (L388), GraphBiasFactory (L432)
- bias/specialized/graph/constraints.py
  - 类: GraphConstraintViolation (L32), ValidationResult (L38), GraphConstraintBias (L51), TSPConstraintBias (L83), PathConstraintBias (L178), TreeConstraintBias (L262), GraphColoringConstraintBias (L378), MatchingConstraintBias (L436), HamiltonianPathConstraintBias (L503), GraphConstraintFactory (L580), CompositeGraphConstraintBias (L615)
- bias/specialized/local_search.py
  - 类: GradientDescentBias (L26), NewtonMethodBias (L170), LineSearchBias (L293), TrustRegionBias (L411), NelderMeadBias (L547), QuasiNewtonBias (L649)
  - 函数: create_gradient_descent_suite (L728), create_newton_suite (L736), create_hybrid_local_suite (L744), create_derivative_free_suite (L753)
- bias/specialized/production/scheduling.py
  - 类: ProductionSchedulingBiasManager (L46), ProductionConstraintBias (L172), ProductionDiversityBias (L347), ProductionContinuityBias (L374), ProductionOptimizationContext (L425), ProductionSchedulingBias (L449)
  - 函数: create_production_bias_system (L519)
