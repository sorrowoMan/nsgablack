"""
Bias system for NSGABlack.

This package provides a modular bias system to separate domain preferences
and algorithmic search signals from the core solver loop.

Key ideas:
- Algorithmic bias: how to search.
- Domain bias: what to prefer.
- Bias modules are optional and composable.
"""

from typing import TYPE_CHECKING

# Type hints for TYPE_CHECKING
if TYPE_CHECKING:
    from .core.base import BiasBase as _BiasBase
    from .core.manager import UniversalBiasManager as _UniversalBiasManager

# 核心组件导入 - 新的组织架构
try:
    from .core.base import (
        BiasBase,                    # 偏置基类
        AlgorithmicBias,            # 算法偏置基类
        DomainBias,                 # 领域偏置基类
        OptimizationContext,        # 优化上下?
        create_bias                 # 偏置工厂函数
    )

    from .core.manager import (
        UniversalBiasManager,       # 通用偏置管理?
        AlgorithmicBiasManager,     # 算法偏置管理?
        DomainBiasManager          # 领域偏置管理?
    )

    from .core.registry import (
        BiasRegistry,               # 偏置注册?
        get_bias_registry,          # 获取注册?
        register_algorithmic_bias,  # 注册算法偏置
        register_domain_bias,       # 注册领域偏置
        register_bias_factory       # 注册偏置工厂
    )

    # 算法偏置导入
    from .algorithmic import (
        DiversityBias,              # 多样性偏?
        AdaptiveDiversityBias,      # 自应多样性偏?
        ConvergenceBias,            # 收敛性偏?
        AdaptiveConvergenceBias,    # 自应收敛性偏?
        PrecisionBias,              # 精度偏置
        RobustnessBias,             # 鲁棒性偏?        SimulatedAnnealingBias,     # 模拟逢火偏?        ParticleSwarmBias,          # PSO偏置
        AdaptivePSOBias,            # 自应PSO偏置
        CMAESBias,                  # CMA-ES偏置
        AdaptiveCMAESBias,          # 自应CMA-ES偏置
        TabuSearchBias,             # 禁忌搜索偏置
        LevyFlightBias,             # Levy飞行偏置
        NSGA2Bias,                  # NSGA-II偏置
        AdaptiveNSGA2Bias,          # 自应NSGA-II偏置
        DifferentialEvolutionBias,  # 差分进化偏置
        PatternSearchBias,          # 模式搜索偏置
        GradientDescentBias,        # 梯度下降偏置
        UncertaintyExplorationBias, # 不确定驱动探索偏?
    )

    # 领域偏置导入
    from .domain import (
        ConstraintBias,             # 约束偏置
        FeasibilityBias,            # 可行性偏?        PreferenceBias,             # 偏好偏置
        RuleBasedBias,              # 基于规则的偏?        CallableBias,               # 可调用规则偏置（快规则）
        DynamicPenaltyBias,         # 动惯罚偏?
        StructurePriorBias,         # 结构先验偏置
        RiskBias,                   # 鲁棒/风险偏置
    )

    # 高级管理器导?
    from .managers import (
        AdaptiveAlgorithmicManager, # 自应算法管理?
        MetaLearningBiasSelector,   # 元学习偏置择?
        BiasEffectivenessAnalyzer   # 偏置效果分析?
    )

    # 分析器导入（新增?
    try:
        from .analytics import BiasAnalytics
    except ImportError:
        BiasAnalytics = None

    # 专门偏置导入（可选模块）
    try:
        from .specialized.bayesian_biases import (
            BayesianGuidanceBias,    # 贝叶斯引导偏?
            BayesianExplorationBias, # 贝叶斯探索偏?
            BayesianConvergenceBias  # 贝叶斯收敛偏?
        )
        # 统一命名为BayesianBias
        BayesianBias = BayesianGuidanceBias
    except Exception:
        BayesianBias = None

    try:
        from .specialized.local_search import (
            GradientDescentBias,     # 梯度下降偏置
            NewtonMethodBias,       # 牛顿法偏?
            LineSearchBias,         # 线搜索偏?
            TrustRegionBias,        # 信赖域偏?
            NelderMeadBias          # 单纯形法偏置
        )
        # 统一命名为LocalSearchBias（使用梯度下降作为代表）
        LocalSearchBias = GradientDescentBias
    except Exception:
        LocalSearchBias = None

    # 工程应用偏置导入
    try:
        from .specialized.engineering import (
            EngineeringPrecisionBias,    # 工程精度偏置
            EngineeringConstraintBias,   # 工程约束偏置
            EngineeringRobustnessBias    # 工程鲁棒性偏?
        )
    except Exception:
        EngineeringPrecisionBias = None
        EngineeringConstraintBias = None
        EngineeringRobustnessBias = None

    # 生产调度偏置导入
    try:
        from .specialized.production.scheduling import ProductionSchedulingBiasManager
    except Exception:
        ProductionSchedulingBiasManager = None

    NEW_STRUCTURE_AVAILABLE = True

except ImportError as e:
    # 如果新架构不完整，抛出错?
    print(f"错误：新的偏置结构不完整: {e}")
    print("Please ensure all core components are installed correctly.")
    NEW_STRUCTURE_AVAILABLE = False
    raise

__version__ = "2.0.0-restructured"

# Export new structure
_BiasBase = BiasBase
_AlgorithmicBias = AlgorithmicBias
_DomainBias = DomainBias
_OptimizationContext = OptimizationContext
_UniversalBiasManager = UniversalBiasManager

# Bias module facade
try:
    from .bias_module import (
        BiasModule,
        create_bias_module,
        from_universal_manager,
        proximity_reward,
        improvement_reward,
    )
except ImportError:
    BiasModule = None
    create_bias_module = None
    from_universal_manager = None
    proximity_reward = None
    improvement_reward = None

# Public API
__all__ = [
    # Core classes
    'BiasBase',
    'AlgorithmicBias',
    'DomainBias',
    'OptimizationContext',
    'UniversalBiasManager',
    'AlgorithmicBiasManager',
    'DomainBiasManager',
    'create_bias',

    # Bias module facade
    'BiasModule',
    'create_bias_module',
    'from_universal_manager',
    'proximity_reward',
    'improvement_reward',

    # Registry system (if available)
    'get_bias_registry',
    'register_algorithmic_bias',
    'register_domain_bias',
    'register_bias_factory',

    # Algorithmic biases (if available)
    'DiversityBias',
    'AdaptiveDiversityBias',
    'ConvergenceBias',
    'AdaptiveConvergenceBias',
    'PrecisionBias',
    'RobustnessBias',
    'SimulatedAnnealingBias',
    'ParticleSwarmBias',
    'AdaptivePSOBias',
    'CMAESBias',
    'AdaptiveCMAESBias',
    'TabuSearchBias',
    'LevyFlightBias',
    'NSGA2Bias',
    'AdaptiveNSGA2Bias',
    'DifferentialEvolutionBias',
    'PatternSearchBias',
    'GradientDescentBias',
    'UncertaintyExplorationBias',

    # Domain biases (if available)
    'ConstraintBias',
    'FeasibilityBias',
    'PreferenceBias',
    'RuleBasedBias',
    'CallableBias',
    'DynamicPenaltyBias',
    'StructurePriorBias',
    'RiskBias',

    # Advanced managers (if available)
    'AdaptiveAlgorithmicManager',
    'MetaLearningBiasSelector',
    'BiasEffectivenessAnalyzer',

    # Analytics (if available)
    'BiasAnalytics',

    # Engineering biases (if available)
    'EngineeringPrecisionBias',
    'EngineeringConstraintBias',
    'EngineeringRobustnessBias',

    # Production scheduling (if available)
    'ProductionSchedulingBiasManager',

]

BiasBase = _BiasBase
AlgorithmicBias = _AlgorithmicBias
DomainBias = _DomainBias
OptimizationContext = _OptimizationContext
UniversalBiasManager = _UniversalBiasManager

# Import helper functions from utils/helpers
try:
    from .utils.helpers import (
        create_universal_bias_manager,
        quick_bias_setup,
        get_bias_system_info
    )
except ImportError:
    # If helpers are not available, create stub functions
    create_universal_bias_manager = None
    quick_bias_setup = None
    get_bias_system_info = None

