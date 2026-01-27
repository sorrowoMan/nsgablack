# 偏置索引

生成时间: 2026-01-24 21:45:15

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
- bias/algorithmic/moead.py
  - 类: MOEADDecompositionBias (L25), AdaptiveMOEADBias (L260)
- bias/algorithmic/nsga2.py
  - 类: NSGA2Bias (L19), AdaptiveNSGA2Bias (L149), DiversityPreservingNSGA2Bias (L235)
  - 函数: compute_pareto_rank (L302), compute_crowding_distance (L342)
- bias/algorithmic/nsga3.py
  - 类: NSGA3ReferencePointBias (L27), AdaptiveNSGA3Bias (L353)
- bias/algorithmic/pattern_search.py
  - 类: PatternSearchBias (L21), AdaptivePatternSearchBias (L217), CoordinateDescentBias (L303)
  - 函数: generate_pattern_search_point (L371), generate_coordinate_descent_points (L393)
- bias/algorithmic/pso.py
  - 类: ParticleSwarmBias (L19), AdaptivePSOBias (L64)
- bias/algorithmic/signal_driven/robustness.py
  - 类: RobustnessBias (L24)
- bias/algorithmic/simulated_annealing.py
  - 类: SimulatedAnnealingBias (L19), AdaptiveSABias (L186), MultiObjectiveSABias (L305)
- bias/algorithmic/spea2.py
  - 类: SPEA2StrengthBias (L27), AdaptiveSPEA2Bias (L261), HybridSPEA2NSGA2Bias (L369)
- bias/algorithmic/tabu_search.py
  - 类: TabuSearchBias (L18)
- bias/algorithmic/template_algorithmic_bias.py
  - 类: ExampleAlgorithmicBias (L9)

## core（核心）

- bias/core/base.py
  - 类: BiasInterface (L15), OptimizationContext (L37), BiasBase (L98), AlgorithmicBias (L305), DomainBias (L359), BiasManager (L402)
  - 函数: create_bias (L457)
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
- bias/domain/template_domain_bias.py
  - 类: ExampleDomainBias (L9)

## managers（管理器）

- bias/managers/adaptive_manager.py
  - 类: OptimizationState (L16), AdaptiveAlgorithmicManager (L27)
- bias/managers/analytics.py
  - 类: MetricType (L33), BiasEffectivenessMetrics (L49), BiasEffectivenessAnalyzer (L92)
- bias/managers/meta_learning_selector.py
  - 类: ProblemFeatures (L28), BiasRecommendation (L53), ProblemFeatureExtractor (L63), MetaLearningBiasSelector (L155)

## root（根目录）

- bias/analytics.py
  - 类: BiasAnalytics (L14)
- bias/bias_module.py
  - 类: BiasModule (L50)
  - 函数: proximity_reward (L743), improvement_reward (L749), create_bias_module (L755), from_universal_manager (L760)
- bias/library.py
  - 类: BiasFactory (L45), BiasComposer (L111)
  - 函数: create_bias_manager_from_template (L131), quick_engineering_bias (L163), quick_ml_bias (L167), quick_financial_bias (L171)

## specialized（专用偏置）

- bias/specialized/bayesian.py
  - 类: SimpleBayesianOptimizer (L25), BayesianGuidanceBias (L50), BayesianExplorationBias (L397), BayesianConvergenceBias (L526), BayesianAdvisor (L642)
  - 函数: create_bayesian_guidance_bias (L618), create_bayesian_exploration_bias (L623), create_bayesian_convergence_bias (L628), create_bayesian_suite (L633)
- bias/specialized/engineering.py
  - 类: EngineeringPrecisionBias (L38), EngineeringConstraintBias (L171), EngineeringRobustnessBias (L304)
  - 函数: create_engineering_bias_suite (L428), create_engineering_constraint_bias (L466)
- bias/specialized/graph/abstract.py
  - 类: GraphType (L27), SolutionEncoding (L40), GraphMetadata (L51), ValidationResult (L61), AbstractGraphProblem (L73), PermutationGraphProblem (L115), TSPProblem (L180), HamiltonianPathProblem (L229), BinaryEdgesGraphProblem (L278), SpanningTreeProblem (L311), PartitionGraphProblem (L419), GraphColoringProblem (L444), GraphProblemFactory (L503), CompositeGraphProblem (L542)
- bias/specialized/graph/base.py
  - 类: GraphStructure (L31), GraphUtils (L73), GraphBias (L153), ConnectivityBias (L166), SparsityBias (L197), DegreeDistributionBias (L217), ShortestPathBias (L266), MaxFlowBias (L320), GraphColoringBias (L355), CommunityDetectionBias (L387), GraphBiasFactory (L431)
- bias/specialized/graph/constraints.py
  - 类: GraphConstraintViolation (L32), ValidationResult (L38), GraphConstraintBias (L51), TSPConstraintBias (L83), PathConstraintBias (L178), TreeConstraintBias (L262), GraphColoringConstraintBias (L378), MatchingConstraintBias (L436), HamiltonianPathConstraintBias (L503), GraphConstraintFactory (L580), CompositeGraphConstraintBias (L615)
- bias/specialized/local_search.py
  - 类: GradientDescentBias (L26), NewtonMethodBias (L170), LineSearchBias (L293), TrustRegionBias (L411), NelderMeadBias (L547), QuasiNewtonBias (L649)
  - 函数: create_gradient_descent_suite (L728), create_newton_suite (L736), create_hybrid_local_suite (L744), create_derivative_free_suite (L753)
- bias/specialized/production/scheduling.py
  - 类: ProductionSchedulingBiasManager (L40), ProductionConstraintBias (L166), ProductionDiversityBias (L341), ProductionContinuityBias (L368), ProductionOptimizationContext (L419), ProductionSchedulingBias (L443)
  - 函数: create_production_bias_system (L513)

## surrogate

- bias/surrogate/base.py
  - 类: SurrogateBiasContext (L9), SurrogateControlBias (L39)
- bias/surrogate/phase_schedule.py
  - 类: PhaseScheduleBias (L9)
- bias/surrogate/template_surrogate_bias.py
  - 类: ExampleSurrogateBias (L7)
- bias/surrogate/uncertainty_budget.py
  - 类: UncertaintyBudgetBias (L10)

## utils（工具）

- bias/utils/helpers.py
  - 函数: create_universal_bias_manager (L11), quick_bias_setup (L44), get_bias_system_info (L113), migrate_legacy_bias (L143)
