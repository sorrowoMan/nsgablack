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
    from bias import create_universal_bias_manager, quick_bias_setup

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
        SimulatedAnnealingBias,     # 模拟退火偏置
        ParticleSwarmBias,          # PSO偏置
        AdaptivePSOBias,            # 自适应PSO偏置
        CMAESBias,                  # CMA-ES偏置
        AdaptiveCMAESBias,          # 自适应CMA-ES偏置
        TabuSearchBias,             # 禁忌搜索偏置
        LevyFlightBias              # Levy飞行偏置
    )

    # 领域偏置导入
    from .domain import (
        ConstraintBias,             # 约束偏置
        FeasibilityBias,            # 可行性偏置
        PreferenceBias,             # 偏好偏置
        RuleBasedBias              # 基于规则的偏置
    )

    # 高级管理器导入
    from .managers import (
        AdaptiveAlgorithmicManager, # 自适应算法管理器
        MetaLearningBiasSelector,   # 元学习偏置选择器
        BiasEffectivenessAnalyzer   # 偏置效果分析器
    )

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

except ImportError as e:
    # 如果新架构不完整，回退到旧结构
    print(f"警告：新的偏置结构尚不可用，使用旧版结构: {e}")
    NEW_STRUCTURE_AVAILABLE = False

# Legacy compatibility - KEEP OLD IMPORTS WORKING
try:
    from .bias_base import BaseBias, OptimizationContext  # Legacy base classes
    from .bias import BiasModule  # v1.0 interface
    from .bias_v2 import (
        AlgorithmicBiasManager as LegacyAlgorithmicBiasManager,
        DomainBiasManager as LegacyDomainBiasManager,
        UniversalBiasManager as LegacyUniversalBiasManager
    )
    from .bias_library_algorithmic import ALGORITHMIC_BIAS_LIBRARY
    from .bias_library_domain import DOMAIN_BIAS_LIBRARY
    LEGACY_AVAILABLE = True
except ImportError:
    print("Warning: Legacy bias modules not available")
    ALGORITHMIC_BIAS_LIBRARY = {}
    DOMAIN_BIAS_LIBRARY = {}
    LEGACY_AVAILABLE = False

__version__ = "2.0.0-restructured"

# Determine which classes to export based on availability
if NEW_STRUCTURE_AVAILABLE:
    # Export new structure
    _BiasBase = BiasBase
    _AlgorithmicBias = AlgorithmicBias
    _DomainBias = DomainBias
    _OptimizationContext = OptimizationContext
    _UniversalBiasManager = UniversalBiasManager
else:
    # Fallback to legacy
    _BiasBase = BaseBias if 'BaseBias' in locals() else object
    _AlgorithmicBias = object
    _DomainBias = object
    _OptimizationContext = OptimizationContext if 'OptimizationContext' in locals() else object
    _UniversalBiasManager = LegacyUniversalBiasManager if 'LegacyUniversalBiasManager' in locals() else object

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
    'SimulatedAnnealingBias',
    'ParticleSwarmBias',
    'AdaptivePSOBias',
    'CMAESBias',
    'AdaptiveCMAESBias',
    'TabuSearchBias',
    'LevyFlightBias',

    # Domain biases (if available)
    'ConstraintBias',
    'FeasibilityBias',
    'PreferenceBias',
    'RuleBasedBias',

    # Advanced managers (if available)
    'AdaptiveAlgorithmicManager',
    'MetaLearningBiasSelector',
    'BiasEffectivenessAnalyzer',

    # Engineering biases (if available)
    'EngineeringPrecisionBias',
    'EngineeringConstraintBias',
    'EngineeringRobustnessBias',

    # Production scheduling (if available)
    'ProductionSchedulingBiasManager',

    # Legacy compatibility
    'ALGORITHMIC_BIAS_LIBRARY',
    'DOMAIN_BIAS_LIBRARY',
    'BaseBias',  # Legacy name for BiasBase
    'BiasModule'  # v1.0 interface
]

# Aliases for backward compatibility
BiasBase = _BiasBase
AlgorithmicBias = _AlgorithmicBias
DomainBias = _DomainBias
OptimizationContext = _OptimizationContext
UniversalBiasManager = _UniversalBiasManager

# Convenience functions for quick bias setup
def create_universal_bias_manager() -> 'UniversalBiasManager':
    """
    Create a pre-configured universal bias manager with common biases.

    Returns:
        UniversalBiasManager: Configured bias manager
    """
    if not NEW_STRUCTURE_AVAILABLE:
        print("Warning: Using legacy bias manager")
        return LegacyUniversalBiasManager() if LEGACY_AVAILABLE else None

    manager = UniversalBiasManager()

    # Add common algorithmic biases
    try:
        manager.add_algorithmic_bias(DiversityBias(weight=0.1))
        manager.add_algorithmic_bias(ConvergenceBias(weight=0.05))
        manager.add_algorithmic_bias(SimulatedAnnealingBias(weight=0.1))
    except Exception as e:
        print(f"Warning: Could not add standard biases: {e}")

    # Add basic domain bias (users can add specific constraints)
    try:
        manager.add_domain_bias(ConstraintBias(weight=1.0))
    except Exception as e:
        print(f"Warning: Could not add constraint bias: {e}")

    return manager


def quick_bias_setup(
    problem_type: str = "general",
    add_constraints: bool = True,
    add_adaptive: bool = True
) -> 'UniversalBiasManager':
    """
    Quick bias setup for different problem types.

    Args:
        problem_type: Type of problem ('general', 'engineering', 'scheduling', 'constrained')
        add_constraints: Whether to add constraint bias
        add_adaptive: Whether to add adaptive manager

    Returns:
        UniversalBiasManager: Configured bias manager
    """
    if not NEW_STRUCTURE_AVAILABLE:
        print("Warning: Using legacy bias manager for quick setup")
        return create_universal_bias_manager()

    manager = UniversalBiasManager()

    # Problem-specific bias configurations
    try:
        if problem_type == "general":
            if 'DiversityBias' in globals():
                manager.add_algorithmic_bias(DiversityBias(weight=0.1))
            if 'ConvergenceBias' in globals():
                manager.add_algorithmic_bias(ConvergenceBias(weight=0.05))

        elif problem_type == "engineering":
            # 使用专门的工程应用偏置
            if 'EngineeringPrecisionBias' in globals():
                manager.add_algorithmic_bias(EngineeringPrecisionBias(weight=0.15))
            elif 'PrecisionBias' in globals():
                manager.add_algorithmic_bias(PrecisionBias(weight=0.15))

            if 'AdaptiveDiversityBias' in globals():
                manager.add_algorithmic_bias(AdaptiveDiversityBias(weight=0.1))

            # 添加工程约束偏置（强制性的）
            if 'EngineeringConstraintBias' in globals():
                manager.add_domain_bias(EngineeringConstraintBias(safety_factor=1.5))
            elif 'ConstraintBias' in globals():
                manager.add_domain_bias(ConstraintBias(weight=1.0, penalty_factor=15.0))

        elif problem_type == "scheduling":
            if 'DiversityBias' in globals():
                manager.add_algorithmic_bias(DiversityBias(weight=0.15))
            if 'SimulatedAnnealingBias' in globals():
                manager.add_algorithmic_bias(SimulatedAnnealingBias(weight=0.2))

        elif problem_type == "constrained":
            if 'AdaptiveDiversityBias' in globals():
                manager.add_algorithmic_bias(AdaptiveDiversityBias(weight=0.2))

        # Add constraint bias if requested
        if add_constraints and 'ConstraintBias' in globals():
            manager.add_domain_bias(ConstraintBias(weight=0.5, penalty_factor=20.0))

    except Exception as e:
        print(f"Warning: Could not configure biases for problem type '{problem_type}': {e}")

    return manager


# System information
def get_bias_system_info() -> dict:
    """
    Get information about the bias system.

    Returns:
        dict: System information
    """
    info = {
        'version': __version__,
        'new_structure_available': NEW_STRUCTURE_AVAILABLE,
        'legacy_available': LEGACY_AVAILABLE
    }

    if NEW_STRUCTURE_AVAILABLE:
        try:
            registry = get_bias_registry()
            info.update({
                'algorithmic_biases': registry.list_algorithmic_biases(),
                'domain_biases': registry.list_domain_biases(),
                'bias_factories': registry.list_bias_factories(),
                'categories': registry.list_categories()
            })
        except Exception as e:
            info['registry_error'] = str(e)

    if LEGACY_AVAILABLE:
        info.update({
            'algorithmic_bias_library_size': len(ALGORITHMIC_BIAS_LIBRARY),
            'domain_bias_library_size': len(DOMAIN_BIAS_LIBRARY)
        })

    return info


def migrate_legacy_bias(legacy_bias_config: dict) -> 'BiasBase':
    """
    Migrate legacy bias configuration to new structure.

    Args:
        legacy_bias_config: Legacy bias configuration

    Returns:
        BiasBase: New bias instance
    """
    if not NEW_STRUCTURE_AVAILABLE:
        raise RuntimeError("New structure not available for migration")

    bias_type = legacy_bias_config.get('type', 'algorithmic')
    bias_name = legacy_bias_config.get('name', 'migrated_bias')
    weight = legacy_bias_config.get('weight', 1.0)
    params = legacy_bias_config.get('params', {})

    try:
        if bias_type == 'algorithmic':
            from .core.base import AlgorithmicBias
            return AlgorithmicBias(bias_name, weight, **params)
        elif bias_type == 'domain':
            from .core.base import DomainBias
            return DomainBias(bias_name, weight, **params)
        else:
            raise ValueError(f"Unknown bias type: {bias_type}")
    except Exception as e:
        print(f"Warning: Could not migrate bias {bias_name}: {e}")
        return None
