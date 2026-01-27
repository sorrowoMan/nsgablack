# ============================================================================
# 核心基础模块
# ============================================================================
from .base import BlackBoxProblem

# Legacy note: benchmark/toy problems live in `core/problems.py` but are *not*
# part of the stable Core API surface. Import them directly when needed:
# `from nsgablack.core import problems as problems` or `from nsgablack.core.problems import ...`

# ============================================================================
# 求解器（支持依赖注入）
# ============================================================================
from .solver import BlackBoxSolverNSGAII
from .blank_solver import BlankSolverBase
from .adapters import AlgorithmAdapter, CompositeAdapter, RoleAdapter, MultiRoleControllerAdapter
from .composable_solver import ComposableSolver

# ============================================================================
# 辅助工具
# ============================================================================

# ============================================================================
# 接口定义（新：解决循环依赖）
# ============================================================================
from .interfaces import (
    # 核心接口
    BiasInterface,
    RepresentationInterface,
    VisualizationInterface,
    PluginInterface,
    OptimizationContext,
    # 检查函数
    has_bias_module,
    has_representation_module,
    has_visualization_module,
    has_numba,
    # 工厂函数
    load_bias_module,
    load_representation_pipeline,
    create_bias_context,
)

__all__ = [
    # 核心问题类
    'BlackBoxProblem',

    # 求解器
    'BlackBoxSolverNSGAII',
    'BlankSolverBase',
    'AlgorithmAdapter',
    'CompositeAdapter',
    'ComposableSolver',
    'RoleAdapter',
    'MultiRoleControllerAdapter',

    # 辅助工具

    # 接口定义（新）
    'BiasInterface',
    'RepresentationInterface',
    'VisualizationInterface',
    'PluginInterface',
    'OptimizationContext',

    # 检查函数
    'has_bias_module',
    'has_representation_module',
    'has_visualization_module',
    'has_numba',

    # 工厂函数
    'load_bias_module',
    'load_representation_pipeline',
    'create_bias_context',
]


_LEGACY_PROBLEM_EXPORTS = {
    "SphereBlackBox",
    "ZDT1BlackBox",
    "ZDT3BlackBox",
    "DTLZ2BlackBox",
    "ExpensiveSimulationBlackBox",
    "NeuralNetworkHyperparameterOptimization",
    "EngineeringDesignOptimization",
    "BusinessPortfolioOptimization",
}


def __getattr__(name):  # pragma: no cover
    if name in _LEGACY_PROBLEM_EXPORTS:
        import warnings

        warnings.warn(
            f"nsgablack.core.{name} is a legacy benchmark helper; "
            "prefer importing from nsgablack.deprecated.legacy.core.problems explicitly (not part of core stability promise).",
            DeprecationWarning,
            stacklevel=2,
        )
        from ..deprecated.legacy.core import problems as _problems

        return getattr(_problems, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
