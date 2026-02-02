# ============================================================================
# 核心基础模块
# ============================================================================
from .base import BlackBoxProblem

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
