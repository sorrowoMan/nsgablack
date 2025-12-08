"""
偏置系统模块 - Bias System

提供算法偏置和业务偏置的双重架构实现，用于引导优化过程。

主要组件：
- BaseBias: 偏置基类和优化上下文
- AlgorithmicBias: 算法层面的偏置（如多样性、收敛性）
- DomainBias: 业务领域的偏置（如约束、偏好）
- BiasLibrary: 预定义的偏置库
- BiasManager: 偏置管理器，支持动态组合和权重调整

版本：
- v1.0: 基础偏置系统 (bias.py)
- v2.0: 双重架构，算法/业务分离 (bias_v2.py)

使用示例：
    from bias import BiasManager, AlgorithmicBias, DomainBias

    # 创建偏置管理器
    manager = BiasManager()

    # 添加算法偏置
    manager.add_algorithmic_bias("diversity", weight=0.5)

    # 添加业务偏置
    manager.add_domain_bias("constraint", weight=1.0)

    # 应用偏置
    biased_solution = manager.apply_bias(solution, context)
"""

# 导入核心类
from .bias_base import BaseBias, AlgorithmicBias, DomainBias, OptimizationContext

# 导入v1.0兼容接口
from .bias import BiasModule

# 导入v2.0主要接口
from .bias_v2 import (
    AlgorithmicBiasManager,
    DomainBiasManager,
    UniversalBiasManager
)

# 导入兼容层
# from .bias_compatibility import (
#     migrate_v1_to_v2,
#     wrap_v1_bias_as_v2,
#     get_bias_stats,
#     clear_all_caches
# )

# 导入偏置库（可选导入）
try:
    from .bias_library_algorithmic import (
        ALGORITHMIC_BIAS_LIBRARY,
        DiversityBias,
        ConvergenceBias,
        ExplorationBias,
        PrecisionBias,
        AdaptiveDiversityBias,
        MemoryGuidedBias,
        GradientApproximationBias,
        AdaptiveConvergenceBias,
        PopulationDensityBias,
        PatternBasedBias,
        TemperatureControlBias
    )
    from .bias_library_domain import (
        DOMAIN_BIAS_LIBRARY,
        ConstraintBias,
        PreferenceBias,
        ObjectiveBias,
        EngineeringDesignBias,
        FinancialBias,
        MLHyperparameterBias,
        SupplyChainBias,
        SchedulingBias,
        PortfolioBias,
        EnergyOptimizationBias,
        HealthcareBias,
        RoboticsBias
    )
    _HAS_BIAS_LIBRARIES = True
except ImportError:
    _HAS_BIAS_LIBRARIES = False
    # 如果导入失败，创建空的类以避免错误
    DiversityBias = None
    ConvergenceBias = None
    ExplorationBias = None
    PrecisionBias = None
    ConstraintBias = None
    PreferenceBias = None
    ObjectiveBias = None

# 版本信息
__version__ = "2.0.0"
__author__ = "NSGA Black Team"

# 导出的公共接口
__all__ = [
    # 核心类
    "BaseBias",
    "AlgorithmicBias",
    "DomainBias",
    "OptimizationContext",

    # v1.0接口（向后兼容）
    "BiasModule",

    # v2.0主要接口
    "AlgorithmicBiasManager",
    "DomainBiasManager",
    "UniversalBiasManager",

    # 兼容性
    # "migrate_v1_to_v2",
    # "wrap_v1_bias_as_v2",
    # "get_bias_stats",
    # "clear_all_caches",
]

# 导入局部优化偏置
try:
    from .bias_local_optimization import (
        GradientDescentBias, NewtonMethodBias, LineSearchBias,
        TrustRegionBias, NelderMeadBias, QuasiNewtonBias,
        create_gradient_descent_suite, create_newton_suite,
        create_hybrid_local_suite, create_derivative_free_suite
    )
    _HAS_LOCAL_OPTIMIZATION = True
    __all__.extend([
        "GradientDescentBias", "NewtonMethodBias", "LineSearchBias",
        "TrustRegionBias", "NelderMeadBias", "QuasiNewtonBias",
        "create_gradient_descent_suite", "create_newton_suite",
        "create_hybrid_local_suite", "create_derivative_free_suite"
    ])
except ImportError:
    _HAS_LOCAL_OPTIMIZATION = False

# 导入贝叶斯偏置
try:
    from .bias_bayesian import (
        BayesianGuidanceBias,
        BayesianExplorationBias,
        BayesianConvergenceBias,
        create_bayesian_guidance_bias,
        create_bayesian_exploration_bias,
        create_bayesian_convergence_bias,
        create_bayesian_suite
    )
    _HAS_BAYESIAN_BIAS = True
    __all__.extend([
        "BayesianGuidanceBias",
        "BayesianExplorationBias",
        "BayesianConvergenceBias",
        "create_bayesian_guidance_bias",
        "create_bayesian_exploration_bias",
        "create_bayesian_convergence_bias",
        "create_bayesian_suite"
    ])
except ImportError:
    _HAS_BAYESIAN_BIAS = False

# 如果有偏置库，也导出
if _HAS_BIAS_LIBRARIES:
    __all__.extend([
        "ALGORITHMIC_BIAS_LIBRARY",
        "DOMAIN_BIAS_LIBRARY",
        # 算法偏置
        "DiversityBias",
        "ConvergenceBias",
        "ExplorationBias",
        "PrecisionBias",
        "AdaptiveDiversityBias",
        "MemoryGuidedBias",
        "GradientApproximationBias",
        "AdaptiveConvergenceBias",
        "PopulationDensityBias",
        "PatternBasedBias",
        "TemperatureControlBias",
        # 业务偏置
        "ConstraintBias",
        "PreferenceBias",
        "ObjectiveBias",
        "EngineeringDesignBias",
        "FinancialBias",
        "MLHyperparameterBias",
        "SupplyChainBias",
        "SchedulingBias",
        "PortfolioBias",
        "EnergyOptimizationBias",
        "HealthcareBias",
        "RoboticsBias"
    ])