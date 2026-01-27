"""
核心接口定义 - 隔离具体实现

这个文件定义所有核心接口，不依赖任何具体实现。
使用 Protocol 类型提供结构化子类型，避免循环依赖。

设计原则：
1. 接口隔离：定义最小依赖接口
2. 依赖注入：solver 通过接口接收依赖，而非直接导入
3. 可选依赖：所有外部模块都是可选的
4. 类型安全：使用 Protocol 提供类型提示
"""

from typing import Protocol, Any, Optional, List, Dict, Callable
from abc import ABC, abstractmethod
import numpy as np


# ============================================================================
# 偏置系统接口
# ============================================================================

class OptimizationContext(Protocol):
    """
    优化上下文接口

    提供优化过程中的状态信息，用于偏置计算。
    """
    generation: int
    population: List[np.ndarray]
    objectives: List[np.ndarray]
    best_individual: Optional[np.ndarray]
    best_objective: Optional[float]

    def get_statistics(self) -> Dict[str, float]:
        """获取统计信息"""
        ...


class BiasInterface(Protocol):
    """
    偏置系统接口

    定义偏置计算和管理的最小接口。
    """

    def compute_bias(self,
                     x: np.ndarray,
                     context: Any) -> float:
        """
        计算偏置值

        Args:
            x: 当前个体
            context: 优化上下文

        Returns:
            偏置值（正=惩罚，负=奖励）
        """
        ...

    def add_bias(self,
                 bias: Any,
                 weight: float = 1.0,
                 name: Optional[str] = None) -> bool:
        """
        添加偏置

        Args:
            bias: 偏置对象
            weight: 权重
            name: 可选名称

        Returns:
            是否成功添加
        """
        ...

    def is_enabled(self) -> bool:
        """检查是否启用"""
        ...

    def enable(self) -> None:
        """启用偏置系统"""
        ...

    def disable(self) -> None:
        """禁用偏置系统"""
        ...


# ============================================================================
# 表示管道接口
# ============================================================================

class RepresentationInterface(Protocol):
    """
    表示管道接口

    定义编码、初始化、变异、修复的统一接口。
    """

    def init(self,
             problem: Any,
             context: Optional[Any] = None) -> np.ndarray:
        """
        初始化单个个体（与 RepresentationPipeline.init 对齐）。

        Args:
            problem: 问题实例
            context: 可选上下文

        Returns:
            初始化后的个体
        """
        ...

    def initialize(self,
                   problem: Any,
                   pop_size: int,
                   context: Optional[Any] = None) -> List[np.ndarray]:
        """
        初始化种群

        Args:
            problem: 问题实例
            pop_size: 种群大小
            context: 可选上下文

        Returns:
            初始化的个体列表
        """
        ...

    def mutate(self,
               x: np.ndarray,
               context: Optional[Any] = None) -> np.ndarray:
        """
        变异操作

        Args:
            x: 待变异个体
            context: 可选上下文

        Returns:
            变异后的个体
        """
        ...

    def repair(self,
               x: np.ndarray,
               context: Optional[Any] = None) -> np.ndarray:
        """
        修复操作（可选）

        Args:
            x: 待修复个体
            context: 可选上下文

        Returns:
            修复后的个体
        """
        ...

    def encode(self,
               x: Any,
               context: Optional[Any] = None) -> np.ndarray:
        """
        编码操作（可选）

        Args:
            x: 待编码对象
            context: 可选上下文

        Returns:
            编码后的数组
        """
        ...

    def decode(self,
               x: np.ndarray,
               context: Optional[Any] = None) -> Any:
        """
        解码操作（可选）

        Args:
            x: 待解码数组
            context: 可选上下文

        Returns:
            解码后的对象
        """
        ...


# ============================================================================
# 可视化接口
# ============================================================================

class VisualizationInterface(Protocol):
    """
    可视化接口

    定义优化结果可视化的统一接口。
    """

    def plot_pareto_front(self,
                         solutions: List[np.ndarray],
                         objectives: List[np.ndarray],
                         save_path: Optional[str] = None) -> None:
        """
        绘制 Pareto 前沿

        Args:
            solutions: 解列表
            objectives: 目标值列表
            save_path: 可选保存路径
        """
        ...

    def plot_convergence(self,
                        history: List[float],
                        save_path: Optional[str] = None) -> None:
        """
        绘制收敛曲线

        Args:
            history: 历史最优值
            save_path: 可选保存路径
        """
        ...

    def plot_diversity(self,
                      population: List[np.ndarray],
                      save_path: Optional[str] = None) -> None:
        """
        绘制种群多样性

        Args:
            population: 当前种群
            save_path: 可选保存路径
        """
        ...


# ============================================================================
# 插件接口
# ============================================================================

class PluginInterface(Protocol):
    """
    Plugin lifecycle interface.

    This protocol supports both legacy and current hook names.
    """

    # Legacy hook names
    def on_initialization(self, solver: Any) -> None:
        ...

    def on_completion(self, solver: Any) -> None:
        ...

    # Current hook names
    def on_solver_init(self, solver: Any) -> None:
        ...

    def on_population_init(self, population: Any, objectives: Any, violations: Any) -> None:
        ...

    def on_generation_start(self, generation: int) -> None:
        ...

    def on_generation_end(self, generation: int) -> None:
        ...

    def on_step(self, solver: Any, generation: int) -> None:
        ...

    def on_solver_finish(self, result: Dict[str, Any]) -> None:
        ...


class ExperimentResultInterface(Protocol):
    """
    实验结果接口

    定义实验结果的存储和导出接口。
    """

    def add_result(self, key: str, value: Any) -> None:
        """添加结果"""
        ...

    def save(self, path: str) -> None:
        """保存结果"""
        ...

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        ...


# ============================================================================
# 快速检查函数
# ============================================================================

def has_bias_module() -> bool:
    """检查 bias 模块是否可用"""
    try:
        from ..bias import BiasModule
        return True
    except ImportError:
        return False


def has_representation_module() -> bool:
    """?? representation ??????"""
    try:
        from ..representation import RepresentationPipeline  # noqa: F401
        return True
    except ImportError:
        return False

def has_visualization_module() -> bool:
    """检查 visualization 模块是否可用"""
    try:
        import matplotlib  # noqa: F401
        from ..utils.viz import SolverVisualizationMixin  # noqa: F401
        return True
    except ImportError:
        return False


def has_numba() -> bool:
    """检查 numba 是否可用"""
    try:
        import numba
        return True
    except ImportError:
        return False


# ============================================================================
# 工厂函数 - 安全加载可选模块
# ============================================================================

def load_bias_module() -> Optional['BiasInterface']:
    """
    安全加载 bias 模块

    Returns:
        BiasModule 实例或 None
    """
    try:
        from ..bias import BiasModule
        return BiasModule()
    except ImportError:
        return None


def load_representation_pipeline(config: Optional[Dict] = None) -> Optional["RepresentationInterface"]:
    """
    ???? representation pipeline

    Args:
        config: ??????

    Returns:
        RepresentationPipeline ??? None
    """
    try:
        from ..representation import RepresentationPipeline
        if config:
            return RepresentationPipeline(**config)
        return RepresentationPipeline()
    except ImportError:
        return None

def create_bias_context(generation: int,
                       population: List[np.ndarray],
                       objectives: List[np.ndarray],
                       best_individual: Optional[np.ndarray] = None,
                       best_objective: Optional[float] = None) -> Any:
    """
    创建优化上下文对象

    这是一个简单的上下文实现，用于兼容性。

    Args:
        generation: 当前代数
        population: 当前种群
        objectives: 目标值列表
        best_individual: 最优个体
        best_objective: 最优目标值

    Returns:
        上下文对象
    """
    class SimpleContext:
        def __init__(self):
            self.generation = generation
            self.population = population
            self.objectives = objectives
            self.best_individual = best_individual
            self.best_objective = best_objective

        def get_statistics(self):
            return {
                'generation': generation,
                'population_size': len(population),
                'best_objective': best_objective
            }

    return SimpleContext()


# ============================================================================
# 类型别名
# ============================================================================

# 为了向后兼容，提供类型别名
BiasModuleType = BiasInterface
RepresentationPipelineType = RepresentationInterface
VisualizationMixinType = VisualizationInterface
PluginType = PluginInterface


__all__ = [
    # 接口定义
    'OptimizationContext',
    'BiasInterface',
    'RepresentationInterface',
    'VisualizationInterface',
    'PluginInterface',
    'ExperimentResultInterface',

    # 检查函数
    'has_bias_module',
    'has_representation_module',
    'has_visualization_module',
    'has_numba',

    # 工厂函数
    'load_bias_module',
    'load_representation_pipeline',
    'create_bias_context',

    # 类型别名
    'BiasModuleType',
    'RepresentationPipelineType',
    'VisualizationMixinType',
    'PluginType',
]
