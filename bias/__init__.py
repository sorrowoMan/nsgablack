"""
偏置系统 - NSGABlack优化生态系统的核心组件

该包提供了一个全面的偏置系统，将算法层面的关注点与领域知识分离，
实现智能化、自适应的优化能力。

偏置系统核心思想：
- 算法偏置：控制"如何搜索"，引导搜索策略和优化行为
- 领域偏置：控制"搜索什么"，融入业务知识和约束条件
- 分离管理：算法偏置可动态调整，领域偏置全局固定
- 智能组合：支持多种偏置的协同工作和自适应权重调整

版本2.0 - 重构架构：
- core/: 基础类和管理器核心组件
- algorithmic/: 算法层面的偏置实现
- domain/: 领域特定的偏置实现
- managers/: 高级管理和分析工具
- specialized/: 专门的偏置类型（贝叶斯、图等）
- utils/: 工具函数和兼容性支持

快速开始：
    from nsgablack.bias import create_universal_bias_manager, quick_bias_setup

    # 创建预配置的偏置管理器
    manager = create_universal_bias_manager()

    # 或者为特定问题类型快速设置
    manager = quick_bias_setup(problem_type="engineering")

主要特性：
1. 双层架构：算法偏置和领域偏置分离管理
2. 自适应能力：算法偏置可根据优化状态动态调整
3. 效果评估：内置偏置效果量化分析框架
4. 元学习支持：基于历史数据自动选择最优偏置组合
5. 高度可扩展：支持自定义偏置和约束条件
6. 算法无关：可与任何优化算法无缝集成
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
        OptimizationContext,        # 优化上下文
        create_bias                 # 偏置工厂函数
    )

    from .core.manager import (
        UniversalBiasManager,       # 通用偏置管理器
        AlgorithmicBiasManager,     # 算法偏置管理器
        DomainBiasManager          # 领域偏置管理器
    )

    from .core.registry import (
        BiasRegistry,               # 偏置注册表
        get_bias_registry,          # 获取注册表
        register_algorithmic_bias,  # 注册算法偏置
        register_domain_bias,       # 注册领域偏置
        register_bias_factory       # 注册偏置工厂
    )

    # 算法偏置导入
    from .algorithmic import (
        DiversityBias,              # 多样性偏置
        AdaptiveDiversityBias,      # 自适应多样性偏置
        ConvergenceBias,            # 收敛性偏置
        AdaptiveConvergenceBias,    # 自适应收敛性偏置
        PrecisionBias,              # 精度偏置
        RobustnessBias,             # 鲁棒性偏置
        SimulatedAnnealingBias,     # 模拟退火偏置
        ParticleSwarmBias,          # PSO偏置
        AdaptivePSOBias,            # 自适应PSO偏置
        CMAESBias,                  # CMA-ES偏置
        AdaptiveCMAESBias,          # 自适应CMA-ES偏置
        TabuSearchBias,             # 禁忌搜索偏置
        LevyFlightBias,             # Levy飞行偏置
        NSGA2Bias,                  # NSGA-II偏置
        AdaptiveNSGA2Bias,          # 自适应NSGA-II偏置
        DifferentialEvolutionBias,  # 差分进化偏置
        PatternSearchBias,          # 模式搜索偏置
        GradientDescentBias,        # 梯度下降偏置
    )

    # 领域偏置导入
    from .domain import (
        ConstraintBias,             # 约束偏置
        FeasibilityBias,            # 可行性偏置
        PreferenceBias,             # 偏好偏置
        RuleBasedBias,              # 基于规则的偏置
        CallableBias,               # 可调用规则偏置（快速规则）
    )

    # 高级管理器导入
    from .managers import (
        AdaptiveAlgorithmicManager, # 自适应算法管理器
        MetaLearningBiasSelector,   # 元学习偏置选择器
        BiasEffectivenessAnalyzer   # 偏置效果分析器
    )

    # 分析器导入（新增）
    try:
        from .analytics import BiasAnalytics
    except ImportError:
        BiasAnalytics = None

    # 专门偏置导入（可选模块）
    try:
        from .specialized.bayesian import (
            BayesianGuidanceBias,    # 贝叶斯引导偏置
            BayesianExplorationBias, # 贝叶斯探索偏置
            BayesianConvergenceBias  # 贝叶斯收敛偏置
        )
        # 统一命名为BayesianBias
        BayesianBias = BayesianGuidanceBias
    except ImportError:
        BayesianBias = None

    try:
        from .specialized.local_search import (
            GradientDescentBias,     # 梯度下降偏置
            NewtonMethodBias,       # 牛顿法偏置
            LineSearchBias,         # 线搜索偏置
            TrustRegionBias,        # 信赖域偏置
            NelderMeadBias          # 单纯形法偏置
        )
        # 统一命名为LocalSearchBias（使用梯度下降作为代表）
        LocalSearchBias = GradientDescentBias
    except ImportError:
        LocalSearchBias = None

    # 工程应用偏置导入
    try:
        from .specialized.engineering import (
            EngineeringPrecisionBias,    # 工程精度偏置
            EngineeringConstraintBias,   # 工程约束偏置
            EngineeringRobustnessBias    # 工程鲁棒性偏置
        )
    except ImportError:
        EngineeringPrecisionBias = None
        EngineeringConstraintBias = None
        EngineeringRobustnessBias = None

    # 生产调度偏置导入
    try:
        from .specialized.production.scheduling import ProductionSchedulingBiasManager
    except ImportError:
        ProductionSchedulingBiasManager = None

    NEW_STRUCTURE_AVAILABLE = True
    LEGACY_AVAILABLE = False

except ImportError as e:
    # 如果新架构不完整，抛出错误
    print(f"错误：新的偏置结构不完整: {e}")
    print("请确保所有核心组件都已正确安装。")
    NEW_STRUCTURE_AVAILABLE = False
    LEGACY_AVAILABLE = False
    raise

__version__ = "2.0.0-restructured"

# Export new structure (no legacy fallback)
_BiasBase = BiasBase
_AlgorithmicBias = AlgorithmicBias
_DomainBias = DomainBias
_OptimizationContext = OptimizationContext
_UniversalBiasManager = UniversalBiasManager

# Import compatibility adapter
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

    # Compatibility adapter
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

    # Domain biases (if available)
    'ConstraintBias',
    'FeasibilityBias',
    'PreferenceBias',
    'RuleBasedBias',
    'CallableBias',

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

    # Legacy compatibility
    'BaseBias',  # Legacy name for BiasBase
]

# Aliases for backward compatibility
BaseBias = _BiasBase
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
        get_bias_system_info,
        migrate_legacy_bias
    )
except ImportError:
    # If helpers are not available, create stub functions
    create_universal_bias_manager = None
    quick_bias_setup = None
    get_bias_system_info = None
    migrate_legacy_bias = None
