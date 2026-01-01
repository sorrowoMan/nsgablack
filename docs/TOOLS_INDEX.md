# 工具索引

生成时间: 2026-01-01 18:53:55

## core（核心）

- core/base.py
  - 类: BlackBoxProblem (L1)
- core/base_solver.py
  - 类: SolverConfig (L150), OptimizationResult (L176), BaseSolver (L199)
- core/convergence.py
  - 函数: evaluate_convergence_svm (L87), evaluate_convergence_cluster (L122), log_and_maybe_evaluate_convergence (L154)
- core/diversity.py
  - 类: DiversityAwareInitializerBlackBox (L9)
- core/elite.py
  - 类: IntelligentHistoryManager (L9), AdvancedEliteRetention (L568)
- core/problems.py
  - 类: SphereBlackBox (L12), ZDT1BlackBox (L22), ZDT3BlackBox (L44), DTLZ2BlackBox (L67), ExpensiveSimulationBlackBox (L124), NeuralNetworkHyperparameterOptimization (L144), EngineeringDesignOptimization (L199), BusinessPortfolioOptimization (L236), SphereBlackBox (L384), ZDT1BlackBox (L397), ExpensiveSimulationBlackBox (L422), NeuralNetworkHyperparameterOptimization (L445), EngineeringDesignOptimization (L501), BusinessPortfolioOptimization (L538)
  - 函数: demo_sphere_blackbox (L267), demo_zdt1_blackbox (L273), demo_expensive_simulation (L279), optimize_neural_network (L288), optimize_engineering_design (L305), optimize_business_portfolio (L315), analyze_results (L325)
- core/solver.py
  - 类: BlackBoxSolverNSGAII (L85)

## solvers（求解器）

- solvers/bayesian_optimizer.py
  - 类: AcquisitionFunction (L32), ExpectedImprovement (L44), UpperConfidenceBound (L64), ProbabilityOfImprovement (L74), KnowledgeGradient (L85), BayesianOptimizer (L97)
  - 函数: bayesian_optimize (L495)
- solvers/hybrid_bo.py
  - 类: HybridBO_NSGA (L40), AdaptiveBOOptimizer (L239), BatchBayesianOptimizer (L373)
  - 函数: hybrid_optimize (L454), adaptive_bayesian_optimize (L462), batch_bayesian_optimize (L469)
- solvers/moead.py
  - 类: BlackBoxSolverMOEAD (L76)
  - 函数: create_moead_solver (L552)
- solvers/monte_carlo.py
  - 类: DistributionSpec (L36), StochasticProblem (L56), MonteCarloEvaluator (L91), MonteCarloOptimizer (L138), SurrogateMonteCarloOptimizer (L260)
  - 函数: optimize_with_monte_carlo (L429), optimize_with_surrogate_mc (L439)
- solvers/multi_agent.py
  - 类: AgentPopulation (L110), MultiAgentBlackBoxSolver (L129)
- solvers/surrogate.py
  - 类: EnsembleSurrogate (L44), SurrogateAssistedNSGAII (L101)
  - 函数: run_surrogate_assisted (L564)
- solvers/vns.py
  - 类: BlackBoxSolverVNS (L21)

## multi_agent（多智能体）

- multi_agent/__init__.py
  - 函数: create_multi_agent_optimizer (L31), get_available_roles (L44), get_default_config (L48)
- multi_agent/bias/profiles.py
  - 类: BiasProfile (L13), DynamicBiasProfile (L69), BiasLibrary (L167), BiasProfileFactory (L354)
  - 函数: get_bias_profile (L330), create_adaptive_profile (L335)
- multi_agent/core/role.py
  - 类: AgentRole (L13), RoleCharacteristics (L35), RoleRegistry (L54), RoleFactory (L210)
  - 函数: get_role_description (L257), suggest_role_config (L273)
- multi_agent/examples/production_scheduling.py
  - 函数: run_production_scheduling_example (L20), analyze_results (L123), visualize_production_results (L160), save_results (L256), demonstrate_bias_system (L324), main (L386)
- multi_agent/strategies/advisory.py
  - 类: AdvisoryMethod (L18), Advisory (L29), BaseAdvisoryStrategy (L40), BayesianAdvisoryStrategy (L92), MLAdvisoryStrategy (L242), EnsembleAdvisoryStrategy (L370), AdvisoryStrategyFactory (L474)
  - 函数: create_advisory_strategy (L502)
- multi_agent/strategies/role_bias_combinations.py
  - 类: BiasConfig (L36), RoleBiasCombinationManager (L44)
  - 函数: get_default_bias_combinations (L356), create_role_bias_profiles (L366)
- multi_agent/strategies/search_strategies.py
  - 类: SearchMethod (L13), SearchStrategy (L39), DifferentialEvolutionStrategy (L64), EvolutionaryStrategy (L136), PatternSearchStrategy (L187), ApproximateGradientStrategy (L237), HillClimbingStrategy (L299), SimulatedAnnealingStrategy (L345), MemeticStrategy (L394), RandomSearchStrategy (L434), SearchStrategyFactory (L450)

## utils（工具）

- utils/array_utils.py
  - 类: SafeArrayAccess (L184)
  - 函数: safe_array_index (L9), safe_slice_bounds (L62), safe_array_concat (L92), safe_array_reshape (L118), validate_array_bounds (L155), safe_get_element (L282), safe_get_row (L287), safe_get_2d_element (L294)
- utils/experiment.py
  - 类: ExperimentResult (L8), ExperimentTracker (L85)
- utils/fast_non_dominated_sort.py
  - 类: FastNonDominatedSort (L12)
  - 函数: fast_non_dominated_sort_optimized (L244), get_pareto_front_indices (L278), count_non_dominated_solutions (L284), is_pareto_optimal (L290)
- utils/feature_selection.py
  - 类: UniversalFeatureSelector (L9)
- utils/headless.py
  - 类: CallableSingleObjectiveProblem (L20)
  - 函数: run_headless_single_objective (L38)
- utils/imports.py
  - 类: ImportManager (L12), ImportWarning (L238), MissingDependencyError (L243)
  - 函数: safe_import (L121), check_optional_dependency (L127), get_import_status (L132), import_numpy (L138), import_matplotlib (L143), import_sklearn (L148), import_numba (L153), import_joblib (L158), import_plotly (L163), import_core (L169), import_bias (L188), import_solvers (L213), import_utils (L226), is_jupyter_notebook (L256), is_headless (L267), get_package_root (L278), add_to_path (L283)
- utils/manifold_reduction.py
  - 类: PCAReducer (L9), KernelPCAReducer (L49), PLSReducer (L89), AutoencoderReducer (L133)
  - 函数: prepare_pca_reduced_problem (L201), prepare_kpca_reduced_problem (L236), prepare_pls_reduced_problem (L276), prepare_autoencoder_reduced_problem (L312), prepare_active_subspace_reduced_problem (L350)
- utils/memory_manager.py
  - 类: MemoryManager (L15), SmartArrayCache (L183), OptimizationMemoryOptimizer (L295)
  - 函数: get_global_memory_manager (L426), monitor_and_optimize_memory (L434), memory_monitoring (L451)
- utils/numba_helpers.py
  - 函数: fast_is_dominated (L26)
- utils/parallel_evaluator.py
  - 类: ParallelEvaluator (L31), SmartEvaluatorSelector (L481)
  - 函数: create_parallel_evaluator (L467)
- utils/parallel_runs.py
  - 函数: run_headless_in_parallel (L59), run_vns_in_parallel (L154)
- utils/reduced.py
  - 类: ReducedMultiObjectiveProblem (L20)
  - 函数: build_pca_reduced_multiobjective_problem (L44)
- utils/representation/base.py
  - 类: EncodingPlugin (L11), RepairPlugin (L19), InitPlugin (L24), MutationPlugin (L29), RepresentationPipeline (L35)
- utils/representation/binary.py
  - 类: BinaryInitializer (L14), BitFlipMutation (L22), BinaryRepair (L33), BinaryCapacityRepair (L41)
- utils/representation/continuous.py
  - 类: UniformInitializer (L14), GaussianMutation (L23), ClipRepair (L36)
- utils/representation/graph.py
  - 类: GraphEdgeInitializer (L14), GraphEdgeMutation (L33), GraphConnectivityRepair (L66), GraphDegreeRepair (L111)
- utils/representation/integer.py
  - 类: IntegerInitializer (L39), IntegerRepair (L57), IntegerMutation (L81)
- utils/representation/matrix.py
  - 类: IntegerMatrixInitializer (L25), IntegerMatrixMutation (L41), MatrixRowColSumRepair (L53), MatrixSparsityRepair (L92), MatrixBlockSumRepair (L117)
- utils/representation/permutation.py
  - 类: RandomKeyPermutationDecoder (L13), RandomKeyInitializer (L22), RandomKeyMutation (L31), PermutationInitializer (L42), PermutationSwapMutation (L51), PermutationInversionMutation (L62), PermutationRepair (L73), PermutationFixRepair (L84), TwoOptMutation (L102), OrderCrossover (L127), PMXCrossover (L137)
- utils/safe_import_enhanced.py
  - 类: SafeImportError (L13)
  - 函数: verify_module (L18), safe_import_with_fallback (L48), get_import_path_context (L139), log_import_attempt (L161)
- utils/solver_extensions.py
  - 类: ParallelEvaluationMixin (L26), SolverEnhancementMixin (L162)
  - 函数: integrate_parallel_evaluation (L256), create_parallel_solver (L366)
- utils/visualization.py
  - 类: SolverVisualizationMixin (L14)

## surrogate（代理模型）

- surrogate/base.py
  - 类: BaseSurrogateModel (L13), CompositeSurrogateModel (L252)
- surrogate/evaluators.py
  - 类: SurrogateEvaluator (L17)
- surrogate/features.py
  - 类: FeatureExtractor (L15), IdentityExtractor (L56), ScalingExtractor (L63), PCATExtractor (L89), PolynomialExtractor (L113), InteractionExtractor (L135), PipelineExtractor (L174), ProblemSpecificExtractor (L202), FeatureExtractorFactory (L306)
- surrogate/manager.py
  - 类: SurrogateManager (L16), SklearnSurrogate (L388), ManagerSurrogate (L417)
- surrogate/strategies.py
  - 类: SurrogateStrategy (L14), RandomStrategy (L60), AdaptiveStrategy (L83), MultiSurrogateStrategy (L160), BayesianStrategy (L239), SurrogateStrategyFactory (L357)
- surrogate/trainer.py
  - 类: TrueEvaluator (L17), ProductionEvaluator (L34), SurrogateTrainer (L71)
  - 函数: example_surrogate_training (L459)

## ml（机器学习）

- ml/checkpoint_manager.py
  - 类: CheckpointManager (L27)
- ml/data_processor.py
  - 类: DataProcessor (L28), FeatureEngineer (L451)
- ml/evaluation_tools.py
  - 类: ModelEvaluator (L33)
- ml/ml_models.py
  - 类: ModelManager (L19)
- ml/model_manager.py
  - 类: BaseModelWrapper (L29), RandomForestWrapper (L83), GradientBoostingWrapper (L100), EnsembleWrapper (L115), ModelManager (L151)

## algorithms（算法）


## architecture（架构）


## development（开发）
