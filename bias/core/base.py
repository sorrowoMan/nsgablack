"""
偏置系统基础类和接口定义

该模块定义了偏置系统的基础抽象类，包括不同类型偏置的基类和上下文管理。
偏置系统是NSGABlack优化库的核心创新，实现算法策略与领域知识的分离。
"""

import numpy as np
from typing import Dict, List, Any, Optional, Protocol
from abc import ABC, abstractmethod


class OptimizationContext:
    """
    优化上下文信息类

    封装当前优化状态的所有相关信息，包括：
    - 当前代数、个体、种群
    - 性能指标、历史数据
    - 优化状态标志（停滞、收敛、约束违反等）

    该类为偏置计算提供必要的上下文环境。
    """

    def __init__(
        self,
        generation: int,                                    # 当前优化代数
        individual: np.ndarray,                              # 当前评估的个体
        population: Optional[List[np.ndarray]] = None,      # 当前种群
        metrics: Optional[Dict[str, float]] = None,          # 性能指标字典
        history: Optional[List] = None,                      # 历史记录
        problem_data: Optional[Dict[str, Any]] = None        # 问题特定数据
    ):
        self.generation = generation                          # 优化代数
        self.individual = individual                          # 当前个体
        self.population = population if population is not None else []  # 种群
        self.metrics = metrics or {}                         # 性能指标
        self.history = history or []                         # 历史记录
        self.problem_data = problem_data or {}               # 问题数据

        # 派生的上下文状态标志
        self.is_stuck = False                                # 是否陷入停滞
        self.is_converging = False                           # 是否正在收敛
        self.is_violating_constraints = False                 # 是否违反约束

    def set_stuck_status(self, is_stuck: bool):
        """
        设置优化停滞状态

        Args:
            is_stuck: 是否停滞（连续多代无改进）
        """
        self.is_stuck = is_stuck

    def set_convergence_status(self, is_converging: bool):
        """
        设置收敛状态

        Args:
            is_converging: 是否正在收敛（快速向最优解靠近）
        """
        self.is_converging = is_converging

    def set_constraint_violation(self, is_violating: bool):
        """
        设置约束违反状态

        Args:
            is_violating: 当前个体是否违反约束
        """
        self.is_violating_constraints = is_violating


class BiasBase(ABC):
    """
    所有偏置类型的抽象基类

    定义了所有偏置必须实现的通用接口。偏置系统支持：
    - 算法偏置：控制搜索策略和优化行为
    - 领域偏置：融入业务知识和约束条件

    偏置值将作为适应度函数的调整项，引导优化过程。
    """

    def __init__(self, name: str, weight: float = 1.0, description: str = ""):
        """
        初始化偏置基类

        Args:
            name: 偏置名称，用于标识和管理
            weight: 偏置权重，控制偏置强度
            description: 偏置描述，说明其用途和效果
        """
        self.name = name                                     # 偏置名称
        self.weight = weight                                 # 偏置权重
        self.description = description                        # 偏置描述
        self.enabled = True                                  # 是否启用
        self.usage_count = 0                                # 使用次数统计
        self.total_bias_value = 0.0                         # 累计偏置值

    @abstractmethod
    def compute(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算给定个体和上下文的偏置值（抽象方法）

        Args:
            x: 被评估的个体（决策变量向量）
            context: 当前优化上下文信息

        Returns:
            计算得到的偏置值

        Note:
            子类必须实现此方法以定义具体的偏置逻辑
        """
        pass

    def compute_with_tracking(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算偏置值并跟踪使用统计信息

        Args:
            x: 被评估的个体
            context: 优化上下文

        Returns:
            加权后的偏置值（偏置值 × 权重）

        Note:
            此方法会自动跟踪使用次数和累计偏置值，用于效果分析
        """
        if not self.enabled:
            return 0.0                                    # 禁用时返回0

        # 调用具体偏置计算方法
        bias_value = self.compute(x, context)
        self.usage_count += 1                              # 增加使用计数
        self.total_bias_value += abs(bias_value)           # 累加偏置值

        return bias_value * self.weight                      # 返回加权偏置值

    def enable(self):
        """启用偏置"""
        self.enabled = True

    def disable(self):
        """禁用偏置"""
        self.enabled = False

    def set_weight(self, weight: float):
        """
        设置偏置权重

        Args:
            weight: 新的权重值（必须非负）
        """
        self.weight = max(0.0, weight)

    def get_average_bias(self) -> float:
        """
        获取平均偏置值

        Returns:
            平均偏置值（总偏置值 / 使用次数）
        """
        return self.total_bias_value / max(1, self.usage_count)

    def reset_statistics(self):
        """重置使用统计信息"""
        self.usage_count = 0
        self.total_bias_value = 0.0

    def __str__(self) -> str:
        """字符串表示"""
        return f"{self.name}(weight={self.weight}, enabled={self.enabled})"


class AlgorithmicBias(BiasBase):
    """
    算法偏置基类

    算法偏置控制搜索策略和优化行为，典型特征：
    - 可自适应调整权重
    - 基于优化状态动态变化
    - 引导搜索方向和探索-开发平衡

    例如：多样性偏置、收敛偏置、模拟退火偏置等
    """

    def __init__(
        self,
        name: str,
        weight: float = 1.0,
        adaptive: bool = True,                               # 是否自适应
        description: str = ""
    ):
        """
        初始化算法偏置

        Args:
            name: 偏置名称
            weight: 初始权重
            adaptive: 是否自适应调整权重
            description: 偏置描述
        """
        super().__init__(name, weight, description)
        self.bias_type = 'algorithmic'                      # 偏置类型标识
        self.adaptive = adaptive                             # 自适应标志
        self.initial_weight = weight                         # 初始权重（用于重置）

    def is_adaptive(self) -> bool:
        """
        检查是否为自适应偏置

        Returns:
            True if the bias can adapt its weight during optimization
        """
        return self.adaptive

    def reset_to_initial_weight(self):
        """重置权重到初始值"""
        self.weight = self.initial_weight


class DomainBias(BiasBase):
    """
    领域偏置基类

    领域偏置融入业务知识和约束条件，典型特征：
    - 代表强制性业务规则
    - 权重通常固定不变
    - 处理约束、偏好、领域知识

    例如：工程约束偏置、安全规范偏置、业务规则偏置等
    """

    def __init__(
        self,
        name: str,
        weight: float = 1.0,
        mandatory: bool = False,                              # 是否为强制偏置
        description: str = ""
    ):
        """
        初始化领域偏置

        Args:
            name: 偏置名称
            weight: 偏置权重
            mandatory: 是否为强制约束
            description: 偏置描述
        """
        super().__init__(name, weight, description)
        self.bias_type = 'domain'                           # 偏置类型标识
        self.mandatory = mandatory                           # 强制标志

    def is_mandatory(self) -> bool:
        """
        检查是否为强制偏置

        Returns:
            True if the bias represents mandatory constraints
        """
        return self.mandatory


# Protocol for bias managers (Python接口定义)
class BiasManager(Protocol):
    """
    偏置管理器协议定义

    定义了偏置管理器必须实现的标准接口，确保不同实现的兼容性。
    """

    def add_bias(self, bias: BiasBase):
        """
        添加偏置到管理器

        Args:
            bias: 要添加的偏置对象
        """
        ...

    def remove_bias(self, name: str) -> bool:
        """
        根据名称移除偏置

        Args:
            name: 偏置名称

        Returns:
            True if successfully removed, False if not found
        """
        ...

    def compute_total_bias(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        计算总偏置值

        Args:
            x: 被评估的个体
            context: 优化上下文

        Returns:
            总偏置值
        """
        ...

    def get_bias(self, name: str) -> Optional[BiasBase]:
        """
        根据名称获取偏置对象

        Args:
            name: 偏置名称

        Returns:
            偏置对象，如果不存在则返回None
        """
        ...


# Factory function for creating biases (偏置工厂函数)
def create_bias(
    bias_type: str,
    name: str,
    weight: float = 1.0,
    **kwargs
) -> BiasBase:
    """
    创建偏置实例的工厂函数

    Args:
        bias_type: 偏置类型 ('algorithmic' 或 'domain')
        name: 偏置名称
        weight: 偏置权重
        **kwargs: 额外的初始化参数

    Returns:
        创建的偏置实例

    Raises:
        ValueError: 当偏置类型不支持时

    Example:
        algo_bias = create_bias('algorithmic', 'diversity', weight=0.2)
        domain_bias = create_bias('domain', 'constraint', weight=1.0, mandatory=True)
    """
    if bias_type.lower() == 'algorithmic':
        return AlgorithmicBias(name, weight, **kwargs)
    elif bias_type.lower() == 'domain':
        return DomainBias(name, weight, **kwargs)
    else:
        raise ValueError(f"不支持的偏置类型: {bias_type}。支持的类型: 'algorithmic', 'domain'")